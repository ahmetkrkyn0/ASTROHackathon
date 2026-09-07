#!/usr/bin/env python3
"""Measure the recovery policy and the chance constraint (B1) on Site11.

What it measures, in order:

1. Nothing: the formulation and Lamarre et al.'s own figures, quoted.
2. The survival field on the standard 4-D pairs (LPR-1 day 28 Sep 2026,
   LPR-1 lunar night 13 Sep 2026, NASA VIPER short leg 30 May 2027): state
   count, time bin, compute time, the P_safe distribution over the
   traversable blocks at the first bin, swept over the fault rate
   (0 / 0.2 / 0.5 per km) and, where the A1 map has havens, over the strict
   haven safe set.
3. The beta sweep: /api/plan-4d with max_failure_probability in
   {none, 0.10, 0.05, 0.02} -- moves, arrival, minimum SOC, execution
   failure probability, refused moves, overlap with the unconstrained
   route, planner time with and without the field.
4. Predicted versus realised: the policy rolled out in continuous time
   (survival.rollout, n runs) from the start and along the unconstrained
   plan, and SHERPA (B5) with the fault event on the fixed route.
   Conservativeness is reported, not adjusted.
5. Recovery suggestions on the lunar-night pair: from the start via
   /api/replan and from a mid-route state.
6. Claim limits and the presentation sentence.

Needs the processed grids, horizon_map.npy and the NAIF kernels; without
them it says so and writes nothing. Writes the JSON dump (--json) BEFORE
the markdown; --from-json re-renders without measuring.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import main as main_module  # noqa: E402
from app import survival as S  # noqa: E402
from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import app  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

COARSEN = 4
START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
VIPER_SHORT_GOAL = {"row": 346, "col": 462}
NIGHT_START = {"row": 186, "col": 34}
NIGHT_GOAL = {"row": 494, "col": 450}

CASES = (
    {"key": "lpr1_day", "label": "LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426)", "rover_id": "lpr_1",
     "start_utc": "2026-09-28T00:00:00", "start": START, "goal": GOAL, "extra": {}},
    {"key": "night", "label": "LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450)", "rover_id": "lpr_1",
     "start_utc": "2026-09-13T00:00:00", "start": NIGHT_START, "goal": NIGHT_GOAL, "extra": {}},
    {"key": "viper_short", "label": "VIPER kısa leg, 30 May 2027, (358,494)→(346,462)", "rover_id": "nasa_viper",
     "start_utc": "2027-05-30T00:00:00", "start": START, "goal": VIPER_SHORT_GOAL, "extra": {}},
)


# ── formatting ───────────────────────────────────────────────────────────────


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "evet" if value else "hayır"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}".replace(",", " ")
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def _pct(value, digits: int = 2) -> str:
    return "—" if value is None else _fmt(100.0 * float(value), digits) + " %"


def _beta_label(beta) -> str:
    return "yok" if beta is None else _fmt(beta, 2)


def _overlap(a, b) -> float | None:
    if not a or not b:
        return None
    sa = {tuple(s[:2]) for s in a}
    sb = {tuple(s[:2]) for s in b}
    return len(sa & sb) / max(1, len(sa | sb))


# ── measurements ─────────────────────────────────────────────────────────────


def _field_stats(field: S.SurvivalField, start_block, e_cap: float) -> dict:
    """The P_safe distribution over the traversable blocks at the first bin,
    full and half battery, and the start block's own value."""
    # Impassable blocks carry 0 with ACTION_NONE everywhere; count the blocks
    # any move can leave from or that are safe themselves.
    mask = field.tables.allowed.any(axis=0) | np.isfinite(field.safe_soc_min_wh)
    out = {}
    for label, soc in (("full", 1.0), ("half", 0.5)):
        k = field.soc_bin(soc * e_cap)
        values = field.p_safe[0, :, :, k][mask].astype(np.float64)
        out[label] = {
            "n_blocks": int(values.size),
            "mean": round(float(values.mean()), 4) if values.size else None,
            "median": round(float(np.median(values)), 4) if values.size else None,
            "fraction_at_least_0_95": round(float(np.mean(values >= 0.95)), 4) if values.size else None,
            "fraction_at_least_0_5": round(float(np.mean(values >= 0.5)), 4) if values.size else None,
            "fraction_zero": round(float(np.mean(values <= 0.0)), 4) if values.size else None,
            "start_p_safe": round(float(field.p_safe[0, start_block[0], start_block[1], k]), 4),
        }
    info = field.info()
    return {
        **{k: info[k] for k in ("step_hours", "slices_per_bin", "n_bins", "horizon_hours", "n_soc_bins",
                                "soc_bin_wh", "n_states", "nbytes", "safe_cells", "compute_s")},
        "p_safe": out,
        "passable_blocks_counted": int(mask.sum()),
    }


def measure_fields(client: TestClient, grids: dict, case: dict, rates: list[float]) -> dict:
    """The field for every fault rate (leg set) and, where the A1 map has
    havens, the strict haven set; the plan's own horizon is used."""
    out: dict = {"rates": {}, "haven": None}
    rover = get_rover(case["rover_id"])
    e_cap = float(rover["e_cap_wh"])
    goal = (case["goal"]["row"], case["goal"]["col"])
    start_block = (case["start"]["row"] // COARSEN, case["start"]["col"] // COARSEN)
    for rate in rates:
        body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"],
                "start_utc": case["start_utc"], "report_survival": True, "failure_rate_per_km": rate, **case["extra"]}
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        plan_s = time.perf_counter() - t0
        if response.status_code != 200:
            out["rates"][str(rate)] = {"status": response.status_code, "detail": response.json().get("detail")}
            continue
        p = response.json()
        block = p["survival"]
        horizon = block["field"]["horizon_hours"]
        options = main_module._SurvivalOptions(rate_per_km=rate, recovery_h=block["failure_model"]["recovery_h"], safe_set="leg")
        field, info, _geometry, _slice = main_module._survival_model_for_grids(
            grids, case["rover_id"], case["start_utc"], goal, COARSEN, options, horizon
        )
        stats = _field_stats(field, start_block, e_cap) if field is not None else {"reason": info.get("reason")}
        out["rates"][str(rate)] = {
            "status": 200,
            "plan_s_with_field": round(plan_s, 2),
            "route": block["route"],
            "shadow_model": (block.get("shadow_model") or {}).get("model"),
            "haven_model": (block.get("haven_model") or {}).get("model"),
            "coarse_haven_cells": (block.get("haven_model") or {}).get("coarse_safe_haven_cells"),
            "field": stats,
            "moves": p["metrics"]["move_steps"],
            "arrival_hours": p["metrics"]["arrival_hours"],
        }
    # The strict haven set, where the map has any haven.
    haven_cells = None
    for entry in out["rates"].values():
        if isinstance(entry, dict) and entry.get("coarse_haven_cells"):
            haven_cells = entry["coarse_haven_cells"]
    if haven_cells:
        response = client.get("/api/survival", params={
            "start_utc": case["start_utc"], "rover_id": case["rover_id"], "safe_set": "haven",
            "horizon_hours": 24.0, "soc_pct": 1.0, "coarsen": COARSEN,
        })
        if response.status_code == 200:
            j = response.json()
            out["haven"] = {"status": 200, "summary": j["summary"], "safe_cells": j["survival_model"]["safe_cells"],
                            "n_states": j["survival_model"]["n_states"], "compute_s": j["survival_model"]["compute_s"]}
        else:
            out["haven"] = {"status": response.status_code, "detail": response.json().get("detail")}
    else:
        out["haven"] = {"status": None, "reason": "A1 haritasında bu epokta kaba haven bloğu yok (katı küme boş, P_safe ≡ 0)"}
    return out


def measure_beta_sweep(client: TestClient, case: dict, betas: list[float]) -> dict:
    out: dict = {}
    base_body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"],
                 "start_utc": case["start_utc"], **case["extra"]}
    t0 = time.perf_counter()
    plain = client.post("/api/plan-4d", json=base_body)
    plain_s = time.perf_counter() - t0
    nominal_states = plain.json().get("path_states") if plain.status_code == 200 else None
    out["none"] = _plan_entry(plain, plain_s, nominal_states, nominal_states)
    for beta in [None, *betas]:
        body = dict(base_body, report_survival=True)
        if beta is not None:
            body["max_failure_probability"] = beta
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        first_s = time.perf_counter() - t0
        t1 = time.perf_counter()
        client.post("/api/plan-4d", json=body)  # the field is cached now: planner time alone
        second_s = time.perf_counter() - t1
        label = "reported" if beta is None else str(beta)
        out[label] = _plan_entry(response, first_s, nominal_states, None if response.status_code != 200 else response.json()["path_states"])
        out[label]["plan_s_cached_field"] = round(second_s, 2)
    return out


def _plan_entry(response, plan_s: float, nominal_states, states) -> dict:
    if response.status_code != 200:
        return {"status": response.status_code, "detail": response.json().get("detail"), "plan_s": round(plan_s, 2)}
    p = response.json()
    m = p["metrics"]
    block = p.get("survival") or {}
    route = block.get("route") or {}
    return {
        "status": 200,
        "plan_s": round(plan_s, 2),
        "moves": m["move_steps"],
        "waits": m.get("wait_steps"),
        "arrival_hours": m["arrival_hours"],
        "min_soc": min(p["path_battery_pct"]),
        "final_soc": p["path_battery_pct"][-1],
        "nodes_expanded": m.get("nodes_expanded"),
        "execution_failure_probability": m.get("execution_failure_probability"),
        "min_recovery_prob": m.get("min_recovery_prob"),
        "start_recovery_prob": m.get("start_recovery_prob"),
        "moves_refused": route.get("moves_refused"),
        "overlap": _overlap(states, nominal_states),
        "path_states": states,
        "n_slices": p["n_slices"],
        "slice_hours": p["slice_hours"],
        "field": block.get("field"),
        "computation_time_ms": m.get("computation_time_ms"),
    }


def measure_validation(client: TestClient, grids: dict, case: dict, sweep: dict, n_runs: int, seed: int, skip_sherpa: bool) -> dict:
    """Predicted vs realised for the default fault model (0.2 / km, 10 h)."""
    out: dict = {}
    rover = get_rover(case["rover_id"])
    e_cap = float(rover["e_cap_wh"])
    goal = (case["goal"]["row"], case["goal"]["col"])
    start_block = (case["start"]["row"] // COARSEN, case["start"]["col"] // COARSEN)
    reported = sweep.get("reported") or {}
    if reported.get("status") != 200:
        return {"reason": "unconstrained plan with a field unavailable", "detail": reported.get("detail")}
    horizon = reported["field"]["horizon_hours"]
    options = main_module._SurvivalOptions(safe_set="leg")
    field, info, _geometry, _slice = main_module._survival_model_for_grids(
        grids, case["rover_id"], case["start_utc"], goal, COARSEN, options, horizon
    )
    if field is None:
        return {"reason": info.get("reason")}
    t0 = time.perf_counter()
    policy_only = S.rollout(field, start_block, e_cap, n_runs, seed)
    policy_only["seconds"] = round(time.perf_counter() - t0, 2)
    t0 = time.perf_counter()
    along_plan = S.rollout(field, start_block, e_cap, n_runs, seed + 1, plan_states=reported["path_states"])
    along_plan["seconds"] = round(time.perf_counter() - t0, 2)
    along_plan["planner_execution_failure"] = reported["execution_failure_probability"]
    along_plan["planner_conservative"] = bool(
        reported["execution_failure_probability"] + 1e-9 >= along_plan["failure_rate"]
    )
    out["policy_only"] = policy_only
    out["along_plan"] = along_plan
    bounded = None
    for key in ("0.05", "0.02", "0.1"):
        entry = sweep.get(key)
        if entry and entry.get("status") == 200:
            bounded = (key, entry)
            break
    if bounded is not None:
        key, entry = bounded
        run = S.rollout(field, start_block, e_cap, n_runs, seed + 2, plan_states=entry["path_states"])
        run["beta"] = float(key)
        run["planner_execution_failure"] = entry["execution_failure_probability"]
        run["planner_conservative"] = bool(entry["execution_failure_probability"] + 1e-9 >= run["failure_rate"])
        out["along_bounded_plan"] = run
    if not skip_sherpa:
        for label, faults in (("no_faults", 0.0), ("faults", field.rate_per_km)):
            body = {
                "path_states": reported["path_states"], "rover_id": case["rover_id"], "start_utc": case["start_utc"],
                "slice_hours": reported["slice_hours"], "coarsen": COARSEN, "n_runs": n_runs, "seed": seed,
                "perturbations": {"fault_rate_per_km": faults, "fault_recovery_h": field.recovery_h},
            }
            t0 = time.perf_counter()
            response = client.post("/api/stress-test", json=body)
            seconds = time.perf_counter() - t0
            if response.status_code != 200:
                out[f"sherpa_{label}"] = {"status": response.status_code, "detail": response.json().get("detail")}
                continue
            s = response.json()
            out[f"sherpa_{label}"] = {
                "status": 200,
                "seconds": round(seconds, 2),
                "completion": s["rates"]["completion"]["rate"],
                "completion_ci95": s["rates"]["completion"]["ci95"],
                "within_reserve": s["rates"]["reached_within_reserve"]["rate"],
                "full_success": s["rates"]["full_success"]["rate"],
                "failures": s["failures"],
                "faults": s["faults"],
                "duration_p50": s["metrics"]["duration_h"]["p50"],
                "duration_p95": s["metrics"]["duration_h"]["p95"],
            }
        # Faults only: every SHERPA sigma at zero, so the fixed-route risk is the fault model's alone.
        body = {
            "path_states": reported["path_states"], "rover_id": case["rover_id"], "start_utc": case["start_utc"],
            "slice_hours": reported["slice_hours"], "coarsen": COARSEN, "n_runs": n_runs, "seed": seed,
            "perturbations": {"start_delay_sigma_h": 0.0, "initial_soc_sigma": 0.0, "power_draw_sigma": 0.0,
                              "speed_sigma": 0.0, "fault_rate_per_km": field.rate_per_km, "fault_recovery_h": field.recovery_h},
        }
        response = client.post("/api/stress-test", json=body)
        if response.status_code == 200:
            s = response.json()
            out["sherpa_faults_only"] = {
                "status": 200,
                "completion": s["rates"]["completion"]["rate"],
                "completion_ci95": s["rates"]["completion"]["ci95"],
                "failures": s["failures"],
                "faults": s["faults"],
                "planner_execution_failure": reported["execution_failure_probability"],
            }
    return out


def measure_suggestions(client: TestClient, grids: dict, case: dict, sweep: dict) -> dict:
    out: dict = {}
    reported = sweep.get("reported") or {}
    body = {"current": case["start"], "goal": case["goal"], "rover_id": case["rover_id"],
            "state": {"actual_soc": 1.0}, "force": True, "utc": case["start_utc"], "recovery_policy": True}
    response = client.post("/api/replan", json=body)
    if response.status_code == 200:
        j = response.json()
        out["replan_start"] = j.get("recovery_suggestion")
        out["replan_survival_model"] = {k: v for k, v in (j.get("survival_model") or {}).items() if k in ("model", "reason", "n_states", "horizon_hours", "compute_s")}
    else:
        out["replan_start"] = {"status": response.status_code, "detail": response.json().get("detail")}
    if reported.get("status") == 200:
        states = reported["path_states"]
        goal = (case["goal"]["row"], case["goal"]["col"])
        rover = get_rover(case["rover_id"])
        e_cap = float(rover["e_cap_wh"])
        options = main_module._SurvivalOptions(safe_set="leg")
        field, _info, _geometry, _slice = main_module._survival_model_for_grids(
            grids, case["rover_id"], case["start_utc"], goal, COARSEN, options, reported["field"]["horizon_hours"]
        )
        if field is not None:
            mid = len(states) // 2
            r, c, t = states[mid]
            plan = client.post("/api/plan-4d", json={"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"],
                                                     "start_utc": case["start_utc"], "report_survival": True}).json()
            soc = plan["path_battery_pct"][mid] / 100.0
            out["mid_route"] = {
                "state": [r, c, t],
                "soc_frac": round(soc, 4),
                "suggestion": S.recovery_suggestion(field, r, c, soc * e_cap, COARSEN, t),
                "suggestion_half_battery": S.recovery_suggestion(field, r, c, 0.5 * e_cap, COARSEN, t),
                "suggestion_after_10h_fault": S.recovery_suggestion(
                    field, r, c, soc * e_cap - field.recovery_drain_wh(r, c, t * field.slice_hours), COARSEN,
                    int(round((t * field.slice_hours + field.recovery_h) / field.slice_hours)),
                ),
            }
    return out


# ── markdown ─────────────────────────────────────────────────────────────────


def _section_formulation(report: dict) -> list[str]:
    q = S.LAMARRE_QUOTED
    return [
        "## 1. Formülasyon ve Lamarre ile farklar",
        "",
        "Durum `x = (zaman kutusu, kaba blok, SOC kutusu)`; eylemler planlayıcının 8 hamlesi + bir kutu bekle; "
        "`V_k(x) = 1_{X\\O}(x) + 1_{O\\S}(x) · min_a max_φ Σ_o p_o · V_{k+1}(φ(f_o(x,a)))` (başarısızlık olasılığı; güvenli 0, "
        "başarısız 1); `P_safe = 1 − V`. Arıza: Poisson α/km, sürüş iki yarı, üç sonuç (`e^{−αρ}`, `1 − e^{−αρ/2}` kaynakta, "
        "`e^{−αρ/2} − e^{−αρ}` hedefte), R saat bekleme ev-içi güçte. Planlayıcı her etikette yürütme hayatta-kalma çarpanı taşır "
        "(`surv' = surv · (p0 + p1·P_safe(f1) + p2·P_safe(f2))`) ve `1 − surv > β` olan hamleyi reddeder.",
        "",
        "| | Lamarre vd. (alıntı) | LunaPath B1 (ölçüm) |",
        "|---|---|---|",
        f"| Durum sayısı | {_fmt(q['states_experiment_1'])} (deney 1) / {_fmt(q['states_experiment_3'])} (deney 3) | Site11 coarsen 4: bkz. § 2 (tavan {_fmt(S.MAX_SURVIVAL_STATES)}) |",
        f"| Zaman kutusu | {q['time_bin_s']['experiment_3']} s (deney 3), {q['time_bin_s']['aero_roi_1']} s (AERO ROI 1) | plan diliminin `m` katı, otomatik (bkz. § 2) |",
        f"| Enerji kutusu | {q['energy_bin_wh']['experiment_3']} Wh (deney 3), {q['energy_bin_wh']['aero_roi_1']} Wh (AERO) | `e_cap / 20` (LPR-1 271 Wh, VIPER katalog) |",
        f"| Bekleme eylemi | {q['wait_action_s']} s | bir DP kutusu |",
        "| Arıza oranı α | 1/1 000 m (deney 1), 1/5 000 m (deney 3, AERO) | **varsayım** 0,2/km (Lamarre'den), 0 ve 0,5 süpürülür |",
        f"| Toparlanma R | {q['recovery_s']['experiment_1']} s / {q['recovery_s']['experiment_3']} s | **varsayım** 10 h |",
        "| Güvenli küme | haven'da Ay gecesini geçecek SOC (ζ_h(t)) | `leg`: hedef bloğu ≥ rezerv ∪ haven ≥ rezerv + tam-gölge ev-içi × h_max; `haven`: yalnız haven (Lamarre) |",
        "| Zaman / enerji eşlemesi | φ_L/φ_U min-max, alt enerji kutusu; sonsuz ufuk yakınsayana dek | her eylem ≥ 1 kutu (tek geriye geçiş); φ_L/φ_U `floor ≥ 1` hamlelerde ve planlayıcı okumasında; enerji **kutu merkezleri arasında doğrusal ara değer** (Lamarre'nin 'interpolation map'i — alt-kutu eşlemesi 20 m hamlede her karanlık hamleyi tam kutu düşürüyordu, spec) |",
        "| Karanlık saati / termal | durumda yok / yok | durumda yok (yalnız toparlanma beklemesinde R > h_max karanlıkta ölümcül) / yok (C6) |",
        "| Şans kısıtı | yörünge düzeyi, TEMPEST geriye arama, waypoint'ler | tek leg, etiket-koyan A*'da yürütme çarpanı, β başlangıçta optimal politika sınırı |",
        f"| Doğrulama | {_fmt(q['monte_carlo_trials']['experiment_3'])} MC (deney 3); β = {_pct(q['aero_beta'], 0)} → gerçekleşen {_pct(q['aero_realised_failure'], 1)} ({_fmt(q['monte_carlo_trials']['aero_roi_1'])} deneme) | politika rollout'u ve SHERPA arıza olaylı, {_fmt(report['n_runs'])} koşum (bkz. § 4) |",
        f"| Risk-sınırlı plan bedeli | +{q['aero_risk_bounded_extra']['km']} km, +{q['aero_risk_bounded_extra']['hours']} h (β = 5 %, 21 km) | bkz. § 3 |",
        "",
        "Belgedeki \"tahmin %0,4–9,8 / gerçekleşen %0,0–4,6\" aralığı makale HTML'inde doğrulanamadı; alıntı olarak belgede kalır. "
        "gplanetary-nav deposunda kurtarma politikası kodu yoktur (yalnız harita/graf/güneş kütüphanesi); formülasyon makalelerden alındı.",
        "",
    ]


def _section_fields(report: dict) -> list[str]:
    lines = ["## 2. Site11'de durum uzayı, süre ve `P_safe` dağılımı (coarsen 4, leg kümesi)", ""]
    lines += ["| Çift | α (1/km) | Kutu (h) | m | Kutu sayısı | Ufuk (h) | Durum | MB | DP (s) | plan-4d + alan (s) | Gölge | Haven blok | P_safe ort. (tam SOC) | ≥ 0,95 | ≥ 0,5 | = 0 | Başlangıç P_safe (tam / yarım SOC) | Yürütme riski (rota) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, block in report["fields"].items():
        label = next(c["label"] for c in CASES if c["key"] == key)
        for rate, entry in block["rates"].items():
            if entry.get("status") != 200:
                lines.append(f"| {label} | {_fmt(float(rate), 1)} | {entry.get('status')}: {entry.get('detail')} | | | | | | | | | | | | | | | |")
                continue
            f = entry["field"]
            full = f["p_safe"]["full"]
            half = f["p_safe"]["half"]
            lines.append(
                f"| {label} | {_fmt(float(rate), 1)} | {_fmt(f['step_hours'], 3)} | {f['slices_per_bin']} | {f['n_bins']} | {_fmt(f['horizon_hours'], 1)} | "
                f"{_fmt(f['n_states'])} | {_fmt(f['nbytes'] / 2**20, 0)} | {_fmt(f['compute_s'], 1)} | {_fmt(entry['plan_s_with_field'], 1)} | {entry['shadow_model']} | "
                f"{_fmt(entry.get('coarse_haven_cells') or 0)} | {_fmt(full['mean'], 3)} | {_pct(full['fraction_at_least_0_95'], 1)} | {_pct(full['fraction_at_least_0_5'], 1)} | "
                f"{_pct(full['fraction_zero'], 1)} | {_fmt(full['start_p_safe'], 4)} / {_fmt(half['start_p_safe'], 4)} | {_pct(entry['route']['execution_failure_probability'], 3)} |"
            )
    lines += ["", "**Katı (Lamarre) güvenli küme — yalnız haven blokları, 24 h ufuk, tam SOC:**", ""]
    for key, block in report["fields"].items():
        label = next(c["label"] for c in CASES if c["key"] == key)
        haven = block.get("haven") or {}
        if haven.get("status") == 200:
            s = haven["summary"]
            lines.append(f"- {label}: {_fmt(haven['safe_cells'])} güvenli blok, {_fmt(haven['n_states'])} durum, DP {_fmt(haven['compute_s'], 1)} s; "
                         f"P_safe ort. {_fmt(s['mean_p_safe'], 3)}, ≥ 0,95: {_pct(s['fraction_at_least_0_95'], 1)}, ≥ 0,5: {_pct(s['fraction_at_least_0_5'], 1)}, = 0: {_pct(s['fraction_zero'], 1)}.")
        elif haven.get("status") is None:
            lines.append(f"- {label}: {haven.get('reason')}.")
        else:
            lines.append(f"- {label}: {haven.get('status')}: {haven.get('detail')}.")
    lines.append("")
    return lines


def _section_beta(report: dict) -> list[str]:
    lines = ["## 3. β süpürmesi — `/api/plan-4d` `max_failure_probability` (α = 0,2/km, R = 10 h)", "",
             "| Çift | β | Durum | Hamle | Bekle | Varış (h) | Min SOC | Yürütme riski | Min P_safe | Başlangıç P_safe | Reddedilen hamle | Nominalle örtüşme | Düğüm | plan-4d (s) ilk / önbellekli alan |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, sweep in report["beta"].items():
        label = next(c["label"] for c in CASES if c["key"] == key)
        for beta_key, entry in sweep.items():
            beta_label = {"none": "yok (alan yok)", "reported": "yok (alan var)"}.get(beta_key, beta_key.replace(".", ","))
            if entry.get("status") != 200:
                detail = (entry.get("detail") or "")[:220]
                lines.append(f"| {label} | {beta_label} | {entry.get('status')} | — | — | — | — | — | — | — | — | — | — | {_fmt(entry.get('plan_s'), 1)} — {detail} |")
                continue
            lines.append(
                f"| {label} | {beta_label} | 200 | {entry['moves']} | {entry['waits']} | {_fmt(entry['arrival_hours'], 3)} | {_pct(entry['min_soc'] / 100.0, 1)} | "
                f"{_pct(entry['execution_failure_probability'], 3)} | {_fmt(entry['min_recovery_prob'], 4)} | {_fmt(entry['start_recovery_prob'], 4)} | "
                f"{_fmt(entry.get('moves_refused'))} | {_pct(entry['overlap'], 0)} | {_fmt(entry.get('nodes_expanded'))} | {_fmt(entry['plan_s'], 1)} / {_fmt(entry.get('plan_s_cached_field'), 1)} |"
            )
    lines.append("")
    return lines


def _section_validation(report: dict) -> list[str]:
    lines = ["## 4. Tahmin edilen vs gerçekleşen risk (α = 0,2/km, R = 10 h)", "",
             f"Politika rollout'u (`survival.rollout`, sürekli saat/SOC, {_fmt(report['n_runs'])} koşum, Wilson %95): (a) başlangıçtan yalnız politika — DP'nin `V(start)`'ı ile; "
             "(b) önce kısıtsız plan, arızadan sonra politika — planlayıcının yürütme riski ile; (c) β planı varsa aynı. SHERPA (B5, 1 000 koşum): sabit rota, arıza olayı eklenmiş "
             "(rota değişmez; planlayıcının tahmini optimal kurtarma varsayar, bire bir karşılaştırılmaz).", "",
             "| Çift | Ölçüm | Tahmin | Gerçekleşen | Wilson %95 | Güvenli / başarısız / ufuk | Ort. arıza | Konservatif? | s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for key, block in report["validation"].items():
        label = next(c["label"] for c in CASES if c["key"] == key)
        if "reason" in block:
            lines.append(f"| {label} | — | {block.get('reason')} {block.get('detail') or ''} | | | | | | |")
            continue
        for name, title, predicted_key in (("policy_only", "(a) yalnız politika", "predicted_failure"),
                                            ("along_plan", "(b) plan + politika", "planner_execution_failure"),
                                            ("along_bounded_plan", "(c) β planı + politika", "planner_execution_failure")):
            run = block.get(name)
            if not run:
                continue
            title2 = title + (f" (β = {_fmt(run['beta'], 2)})" if name == "along_bounded_plan" else "")
            conservative = run.get("conservative") if name == "policy_only" else run.get("planner_conservative")
            lines.append(
                f"| {label} | {title2} | {_pct(run[predicted_key], 3)} | {_pct(run['failure_rate'], 3)} | {_pct(run['wilson_low'], 2)}–{_pct(run['wilson_high'], 2)} | "
                f"{run['safe']} / {run['failed']} / {run['horizon']} | {_fmt(run['mean_faults'], 3)} | {_fmt(conservative)} | {_fmt(run.get('seconds'), 1)} |"
            )
        for name, title in (("sherpa_no_faults", "SHERPA, arıza yok"), ("sherpa_faults", "SHERPA + arıza"), ("sherpa_faults_only", "SHERPA yalnız arıza (σ = 0)")):
            s = block.get(name)
            if not s:
                continue
            if s.get("status") != 200:
                lines.append(f"| {label} | {title} | — | {s.get('status')}: {s.get('detail')} | | | | | |")
                continue
            failed = 1.0 - s["completion"]
            fails = ", ".join(f"{k} {v}" for k, v in s["failures"].items() if v)
            lines.append(
                f"| {label} | {title} | {_pct(s.get('planner_execution_failure'), 3) if name == 'sherpa_faults_only' else '—'} | {_pct(failed, 3)} | "
                f"{_pct(1 - s['completion_ci95'][1], 2)}–{_pct(1 - s['completion_ci95'][0], 2)} | tamamlanma {_pct(s['completion'], 1)}; {fails or 'başarısızlık yok'} | "
                f"{_fmt(s['faults'].get('mean_faults'), 3)} ({s['faults'].get('runs_with_fault')} koşumda) | — | {_fmt(s.get('seconds'), 1)} |"
            )
    lines.append("")
    return lines


def _suggestion_line(s: dict | None) -> str:
    if not s or "action_name" not in s:
        return "—" if not s else f"{s.get('status')}: {s.get('detail')}"
    target = s.get("target_pixel")
    return (f"**{s['action_name']}** → blok {s.get('target_block')} (piksel {target}); P_safe şimdi {_fmt(s['p_safe_now'], 4)}, "
            f"sonra {_fmt(s.get('p_safe_next'), 4)}; SOC {_pct(s.get('soc_frac'), 0)}, t = {_fmt(s.get('hours'), 2)} h")


def _section_suggestions(report: dict) -> list[str]:
    lines = ["## 5. Kurtarma politikası örnekleri", ""]
    for key, block in report["suggestions"].items():
        label = next(c["label"] for c in CASES if c["key"] == key)
        lines.append(f"**{label}**")
        lines.append("")
        lines.append(f"- `/api/replan` (`recovery_policy: true`, başlangıç, tam SOC): {_suggestion_line(block.get('replan_start'))}")
        mid = block.get("mid_route")
        if mid:
            lines.append(f"- Rota ortası durum {mid['state']} (SOC {_pct(mid['soc_frac'], 1)}): {_suggestion_line(mid['suggestion'])}")
            lines.append(f"- Aynı durum, yarım batarya: {_suggestion_line(mid['suggestion_half_battery'])}")
            lines.append(f"- Aynı blokta 10 h arıza beklemesinden sonra: {_suggestion_line(mid['suggestion_after_10h_fault'])}")
        lines.append("")
    return lines


def _reading(report: dict) -> list[str]:
    return [
        "## 6. İddia sınırı ve sunum cümlesi",
        "",
        f"- {S.SURVIVAL_CLAIM}",
        f"- Kapsam: {S.SURVIVAL_SCOPE}",
        "- Zaman kutusu plan diliminin katı ve her eylem en az bir kutu sürer: DP'nin saati gerçek saatten **yavaştır** (kötümser); yürütme riski bu yüzden SHERPA'nın "
        "sabit-rota gerçekleşmesinden yukarıda çıkabilir ve bu bir hata değil, ayrıklaştırmanın yönüdür. Tersi (tahmin < gerçekleşen) olduğunda satır \"konservatif: hayır\" der.",
        "- Sayıların tamamı Site11'de bu betikle koşturulup okundu; Lamarre'nin sayıları § 1'de alıntıdır.",
        "",
        "**Sunum cümlesi:** \"Toronto STARS'ın reach-avoid formülasyonunu LunaPath'in kendi kaba gridi, SPICE gölge serisi ve enerji fiziği üzerinde kurduk: her (zaman, blok, SOC) "
        "durumundan güvenli kümeye ulaşma olasılığı ve kurtarma politikası 40 M–70 M durumda 1–2 dakikada hesaplanıyor; 4-B planlayıcı 'görev başarısızlık olasılığı ≤ β' kısıtını taşıyor; "
        "tahmin edilen risk politikayı izleyen Monte Carlo ile denetlendi. Arıza oranı bir varsayımdır ve öyle etiketlenir.\"",
        "",
    ]


def render_markdown(report: dict) -> str:
    lines = [
        "# Kurtarma politikası ve şans-kısıtlı 4-B planlama (B1) — LunaPath raporu",
        "",
        f"Üretildi: {report['generated_utc']} (`scripts/recovery_policy_report.py`, toplam {_fmt(report.get('total_seconds'), 0)} s). "
        f"Site11 (500 × 500 × 5 m), coarsen {COARSEN}; Monte Carlo {_fmt(report['n_runs'])} koşum, tohum {report['seed']}. "
        f"Arıza modeli: α ∈ {{{', '.join(_fmt(r, 1) for r in report['rates'])}}} 1/km, R = 10 h (**varsayım**: {S.FAILURE_MODEL_SOURCE}).",
        "",
        f"**İddia sınırı:** {S.SURVIVAL_CLAIM}",
        "",
    ]
    lines += _section_formulation(report)
    lines += _section_fields(report)
    lines += _section_beta(report)
    lines += _section_validation(report)
    lines += _section_suggestions(report)
    lines += _reading(report)
    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(_ROOT / "docs" / "research" / "recovery_policy_report.md"))
    parser.add_argument("--json", default=None, help="dump the raw measurements as JSON (written before the markdown)")
    parser.add_argument("--from-json", default=None, help="render the markdown from a previous --json dump instead of measuring")
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--betas", default="0.10,0.05,0.02")
    parser.add_argument("--rates", default="0,0.2,0.5")
    parser.add_argument("--cases", default=",".join(c["key"] for c in CASES))
    parser.add_argument("--skip-sherpa", action="store_true")
    args = parser.parse_args()

    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        Path(args.output).write_text(render_markdown(report) + "\n", encoding="utf-8")
        print(f"re-rendered {args.output}")
        return 0

    if not (_PROCESSED / "metadata.json").exists() or not (_PROCESSED / "horizon_map.npy").exists() or not _KERNELS.exists():
        print(f"processed grids, horizon_map.npy or NAIF kernels not found under {_PROCESSED} / {_KERNELS}; nothing measured, nothing written.")
        return 0

    betas = [float(b) for b in args.betas.split(",") if b.strip()]
    rates = [float(r) for r in args.rates.split(",") if r.strip()]
    keys = [k.strip() for k in args.cases.split(",") if k.strip()]
    cases = [c for c in CASES if c["key"] in keys]

    t_all = time.perf_counter()
    grids = load_preprocessed_grids()
    app.state.grids = grids
    client = TestClient(app)
    report: dict = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_runs": args.n_runs, "seed": args.seed, "betas": betas, "rates": rates,
        "fields": {}, "beta": {}, "validation": {}, "suggestions": {},
    }
    for case in cases:
        print(f"[fields] {case['label']} ...", flush=True)
        report["fields"][case["key"]] = measure_fields(client, grids, case, rates)
        print(f"[beta] {case['label']} ...", flush=True)
        report["beta"][case["key"]] = measure_beta_sweep(client, case, betas)
        print(f"[validation] {case['label']} ...", flush=True)
        report["validation"][case["key"]] = measure_validation(client, grids, case, report["beta"][case["key"]], args.n_runs, args.seed, args.skip_sherpa)
        print(f"[suggestions] {case['label']} ...", flush=True)
        report["suggestions"][case["key"]] = measure_suggestions(client, grids, case, report["beta"][case["key"]])
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    app.state.grids = None
    report["total_seconds"] = round(time.perf_counter() - t_all, 1)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        print(f"wrote {args.json}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(report) + "\n", encoding="utf-8")
    print(f"wrote {out} in {report['total_seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
