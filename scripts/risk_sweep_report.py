#!/usr/bin/env python3
"""Measure the CVaR risk appetite (B2) on the checked-in Site11 grid.

What it measures, in order:

1. The closed form itself (phi(z_alpha) / (1 - alpha)) and the slip curve
   read at each alpha, with C3's anchor spread alone and with the median
   slope sigma of NASA's DEM clones (B3) carried in by the delta method.
2. The whole fine grid, per rover: the clone slope sigma, the CVaR slip
   (median, share at the 0.9 cap), the share of cells whose slope tail hits
   the rover's limit, the Spearman correlation of the alpha-ranked cost grid
   with the nominal one, the share of cells whose energy criterion
   saturates, and the thermal criterion's saturation (why the thermal tail
   is a hook, not a criterion).
3. /api/risk-sweep on the standard 2-D pairs: every route's nominal-physics
   metrics, its overlap with the nominal route, and every route re-priced at
   every alpha (the risk matrix).
4. /api/plan-4d with risk_alpha on the standard 4-D routes, each followed
   by /api/stress-test (SHERPA, 1 000 runs): does a higher alpha buy a route
   that survives more of the Monte Carlo, and at what nominal cost.

Needs the processed grids and the DEM clone cache for 1-3, plus
horizon_map.npy and the NAIF kernels for 4; without the latter it says so
and skips section 4. It never fabricates numbers. Writes the JSON dump
(--json) BEFORE the markdown; --from-json re-renders without measuring.
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
from scipy.stats import spearmanr  # noqa: E402

from app.constants import get_rover  # noqa: E402
from app.cost_engine import compute_cost_grid  # noqa: E402
from app.cost_vec import f_energy_cell_grid, f_thermal_grid  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import app  # noqa: E402
from app.risk import (  # noqa: E402
    RISK_CLAIM,
    RISK_MEASURE_ID,
    cvar_multiplier,
    slip_cvar,
    slip_cvar_array,
    slip_stats_array,
    slope_cvar_array,
)
from app.rover_grids import grids_for_rover  # noqa: E402
from app.slip_model import MAX_SLIP_RATIO, slip_stats  # noqa: E402
from app.uncertainty import uncertainty_layers_for_grids  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

COARSEN = 4
ALPHAS = (0.5, 0.9, 0.99)
START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
VIPER_SHORT_GOAL = {"row": 346, "col": 462}
NIGHT_START = {"row": 186, "col": 34}
NIGHT_GOAL = {"row": 494, "col": 450}

PAIRS_2D = [
    {"key": "lpr1", "label": "LPR-1, (358,494)→(206,426)", "rover_id": "lpr_1", "start": START, "goal": GOAL},
    {"key": "night", "label": "LPR-1, Ay gecesi çifti (186,34)→(494,450)", "rover_id": "lpr_1", "start": NIGHT_START, "goal": NIGHT_GOAL},
    {"key": "viper", "label": "VIPER, (358,494)→(206,426)", "rover_id": "nasa_viper", "start": START, "goal": GOAL},
    {"key": "viper_short", "label": "VIPER kısa leg (358,494)→(346,462)", "rover_id": "nasa_viper", "start": START, "goal": VIPER_SHORT_GOAL},
]
CASES_4D = [
    {"key": "lpr1", "label": "LPR-1, 28 Eyl 2026, (358,494)→(206,426)", "rover_id": "lpr_1", "start_utc": "2026-09-28T00:00:00", "start": START, "goal": GOAL, "extra": {}, "stress": True},
    {"key": "night", "label": "LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450)", "rover_id": "lpr_1", "start_utc": "2026-09-13T00:00:00", "start": NIGHT_START, "goal": NIGHT_GOAL, "extra": {}, "stress": True},
    {"key": "viper_short", "label": "VIPER kısa leg, 30 May 2027, (358,494)→(346,462), haven kuralı", "rover_id": "nasa_viper", "start_utc": "2027-05-30T00:00:00", "start": START, "goal": VIPER_SHORT_GOAL, "extra": {"require_safe_haven": True}, "stress": True},
]


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _pct(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"%{100.0 * float(value):.{digits}f}".replace(".", ",")


def _int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _signed(value, digits: int = 3) -> str:
    if value is None:
        return "—"
    return f"{float(value):+.{digits}f}".replace(".", ",")


def _alpha_label(alpha) -> str:
    return "None" if alpha is None else _fmt(alpha, 2 if alpha != 0.999 else 3)


# ── 1. closed form and curve ────────────────────────────────────────────────


def measure_closed_form(sigma_theta_median: float | None) -> dict:
    multipliers = {str(a): cvar_multiplier(a) for a in (0.5, 0.9, 0.99, 0.999)}
    rover = get_rover("lpr_1")
    rows = []
    for slope in (0.0, 5.0, 10.0, 15.0, 20.0):
        mu, sigma = slip_stats(slope, rover)
        row = {"slope_deg": slope, "mu": mu, "sigma_c3": sigma}
        for a in ALPHAS:
            row[f"c3_{a}"] = slip_cvar(slope, a, rover)
            row[f"c3b3_{a}"] = None if sigma_theta_median is None else slip_cvar(slope, a, rover, sigma_theta_median)
        rows.append(row)
    return {"multipliers": multipliers, "curve": rows, "sigma_theta_median": sigma_theta_median}


# ── 2. grid level ───────────────────────────────────────────────────────────


def measure_grid(grids: dict, rover_id: str) -> dict:
    rover = get_rover(rover_id)
    nominal = grids_for_rover(grids, rover_id)
    trav = np.asarray(nominal["traversable"], dtype=bool)
    slope = np.asarray(nominal["slope"], dtype=np.float64)
    shadow = np.asarray(nominal["shadow_ratio"], dtype=np.float64)
    thermal = np.asarray(nominal["thermal"], dtype=np.float64)
    thermal_min = None if nominal.get("thermal_min") is None else np.asarray(nominal["thermal_min"], dtype=np.float64)
    cost_nominal = np.asarray(nominal["cost"], dtype=np.float64)
    out: dict = {"rover_id": rover_id, "n_traversable": int(trav.sum())}

    t0 = time.perf_counter()
    layers, info = uncertainty_layers_for_grids(grids, rover_id)
    out["uncertainty_s"] = round(time.perf_counter() - t0, 2)
    sigma = None if layers is None else np.asarray(layers["slope_sigma"], dtype=np.float64)
    out["slope_sigma"] = None
    if sigma is not None:
        out["slope_sigma"] = {
            "source": info.get("model"),
            "n_clones": info.get("n_clones"),
            "median_deg": float(np.nanmedian(sigma[trav])),
            "p95_deg": float(np.nanpercentile(sigma[trav], 95)),
        }
    mu, _sigma_slip = slip_stats_array(slope, rover)
    out["slip_mu_median"] = float(np.median(mu[trav]))
    out["cap_fraction_mu"] = float(np.mean(mu[trav] >= MAX_SLIP_RATIO))
    e_nom = f_energy_cell_grid(slope, rover, shadow)
    out["energy_saturated_nominal"] = float(np.mean(e_nom[trav] >= 1.0))

    per_alpha = {}
    for a in ALPHAS:
        s_c3 = slip_cvar_array(slope, a, rover)
        s_all = slip_cvar_array(slope, a, rover, sigma)
        tail_slope = slope_cvar_array(slope, a, sigma, rover)
        cost_a = compute_cost_grid(
            slope, thermal, shadow, float(nominal["metadata"]["resolution_m"]), traversable=trav,
            weights=nominal["metadata"]["cost_weights"], rover=rover, thermal_min_grid=thermal_min,
            risk_alpha=a, slope_sigma_grid=sigma,
        )
        finite = np.isfinite(cost_a) & np.isfinite(cost_nominal)
        e_a = f_energy_cell_grid(slope, rover, shadow, risk_alpha=a, slope_sigma=sigma)
        per_alpha[str(a)] = {
            "multiplier": cvar_multiplier(a),
            "slip_cvar_median_c3": float(np.median(s_c3[trav])),
            "slip_cvar_median": float(np.median(s_all[trav])),
            "cap_fraction": float(np.mean(s_all[trav] >= MAX_SLIP_RATIO)),
            "slope_at_limit_fraction": float(np.mean(tail_slope[trav] >= float(rover["slope_max_deg"]))),
            "spearman_vs_nominal": float(spearmanr(cost_a[finite], cost_nominal[finite]).correlation),
            "cost_mean_rel_change": float(np.mean((cost_a[finite] - cost_nominal[finite]) / cost_nominal[finite])),
            "cost_max_rel_change": float(np.max((cost_a[finite] - cost_nominal[finite]) / cost_nominal[finite])),
            "energy_saturated": float(np.mean(e_a[trav] >= 1.0)),
        }
    out["alpha"] = per_alpha

    ft = f_thermal_grid(thermal, rover, thermal_min)
    v = ft[trav]
    thermal_block = {
        "f_ge_0.99": float(np.mean(v >= 0.99)),
        "f_ge_0.9": float(np.mean(v >= 0.9)),
        "median": float(np.median(v)),
        "peak_median_c": float(np.median(thermal[trav])),
        "min_median_c": None if thermal_min is None else float(np.median(thermal_min[trav])),
    }
    if thermal_min is not None:
        sigma_t = (thermal - thermal_min) / 4.0
        cold = thermal_min - sigma_t * cvar_multiplier(0.9)
        va = f_thermal_grid(thermal, rover, cold)[trav]
        thermal_block["f_ge_0.99_cold_tail_0.9"] = float(np.mean(va >= 0.99))
        thermal_block["mean_change_cold_tail_0.9"] = float(np.mean(va - v))
    out["thermal"] = thermal_block
    return out


# ── 3. 2-D sweep ────────────────────────────────────────────────────────────


def measure_sweep(client: TestClient, pair: dict) -> dict:
    t0 = time.perf_counter()
    response = client.post(
        "/api/risk-sweep",
        json={"start": pair["start"], "goal": pair["goal"], "rover_id": pair["rover_id"], "alphas": list(ALPHAS)},
    )
    seconds = time.perf_counter() - t0
    if response.status_code != 200:
        return {"status": response.status_code, "detail": response.json().get("detail"), "seconds": seconds}
    payload = response.json()
    rows = []
    for entry in payload["results"]:
        summary = entry.get("summary") or {}
        slip = (entry.get("slip_model") or {}).get("route") or {}
        risk = (entry.get("risk") or {}).get("route") or {}
        rows.append(
            {
                "alpha": entry["risk_alpha"],
                "error": entry.get("error"),
                "waypoints": summary.get("waypoint_count"),
                "distance_km": summary.get("total_distance_km"),
                "hours": summary.get("total_elapsed_hours"),
                "energy_wh": summary.get("total_energy_consumed_wh"),
                "min_soc": summary.get("min_battery_pct"),
                "mean_slip": slip.get("mean_slip"),
                "max_slip": slip.get("max_slip"),
                "mean_slip_cvar": risk.get("mean_slip_cvar"),
                "risk_adjusted_hours": risk.get("risk_adjusted_hours"),
                "max_slope_cvar_deg": risk.get("max_slope_cvar_deg"),
                "overlap": entry.get("overlap_with_nominal"),
                "plan_ms": entry.get("plan_ms"),
            }
        )
    return {
        "status": 200,
        "seconds": seconds,
        "rows": rows,
        "risk_matrix": payload["risk_matrix"],
        "comparison": payload["comparison"],
        "slope_sigma_source": payload["sigma_sources"]["slope"]["source"],
    }


# ── 4. 4-D routes + SHERPA ──────────────────────────────────────────────────


def _overlap(a, b) -> float | None:
    if a is None or b is None:
        return None
    sa = {tuple(p[:2]) for p in a}
    sb = {tuple(p[:2]) for p in b}
    return len(sa & sb) / max(1, len(sa | sb))


def measure_4d(client: TestClient, case: dict, n_runs: int, seed: int) -> dict:
    out: dict = {}
    nominal_states = None
    for alpha in (None, *ALPHAS):
        body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"], "start_utc": case["start_utc"], **case["extra"]}
        if alpha is not None:
            body["risk_alpha"] = alpha
        label = _alpha_label(alpha)
        print(f"    plan-4d alpha={label} ...", flush=True)
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        plan_s = time.perf_counter() - t0
        if response.status_code != 200:
            out[label] = {"status": response.status_code, "detail": response.json().get("detail"), "plan_s": plan_s}
            continue
        p = response.json()
        if alpha is None:
            nominal_states = p["path_states"]
        slip = p["slip_model"]["route"]
        risk = p["risk"].get("route") or {}
        entry = {
            "status": 200,
            "plan_s": plan_s,
            "n_slices": p["n_slices"],
            "slice_hours": p["slice_hours"],
            "moves": p["metrics"]["move_steps"],
            "waits": p["metrics"].get("wait_steps"),
            "arrival_hours": p["metrics"]["arrival_hours"],
            "min_soc": min(p["path_battery_pct"]),
            "nodes_expanded": p["metrics"].get("nodes_expanded"),
            "mean_slip": slip["mean_slip"],
            "max_slip": slip["max_slip"],
            "max_slip_slope_deg": slip["max_slip_slope_deg"],
            "risk_criteria": p["risk"]["criteria"],
            "slope_sigma_source": p["risk"]["sigma_sources"]["slope"]["source"],
            "mean_slip_cvar": risk.get("mean_slip_cvar"),
            "max_slip_cvar": risk.get("max_slip_cvar"),
            "max_slope_cvar_deg": risk.get("max_slope_cvar_deg"),
            "drive_hours": risk.get("hours"),
            "risk_adjusted_hours": risk.get("risk_adjusted_hours"),
            "overlap": _overlap(p["path_states"], nominal_states),
            "ends_at_haven": p["metrics"].get("ends_at_safe_haven"),
        }
        if case["stress"]:
            t1 = time.perf_counter()
            stress = client.post(
                "/api/stress-test",
                json={
                    "path_states": p["path_states"], "rover_id": case["rover_id"], "start_utc": case["start_utc"],
                    "slice_hours": p["slice_hours"], "coarsen": COARSEN, "n_runs": n_runs, "seed": seed,
                },
            )
            entry["stress_s"] = time.perf_counter() - t1
            if stress.status_code == 200:
                s = stress.json()
                entry["stress"] = {
                    "completion": s["rates"]["completion"]["rate"],
                    "within_reserve": s["rates"]["reached_within_reserve"]["rate"],
                    "full_success": s["rates"]["full_success"]["rate"],
                    "nominal_min_battery_pct": s["nominal"]["min_battery_pct"],
                    "nominal_duration_h": s["nominal"]["duration_h"],
                }
            else:
                entry["stress"] = {"error": stress.json().get("detail")}
        out[label] = entry
    return out


# ── markdown ────────────────────────────────────────────────────────────────


def _write_markdown(path: Path, report: dict, args) -> None:
    L: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L.append("# CVaR risk iştahı (B2) — Site11 α taraması raporu\n")
    L.append(
        f"Üretildi: {stamp} (`scripts/risk_sweep_report.py`). Ölçü `{RISK_MEASURE_ID}`: "
        "normal dağılım için `CVaR_α = μ + σ·φ(z_α)/(1−α)`. α yalnızca **sıralama maliyetine** girer "
        "(eğim kriteri `min(slope_max, θ + σ_θ·m_α)`, enerji kriteri `CVaR_α(slip)`); süre, batarya, "
        "D3 marjları ve B5 Monte Carlo **ortalama** slip fiziğidir. `risk_alpha` verilmemişse "
        "(None) grid bugünkü v4 gridiyle bit-eşittir; **α = 0,5 ortalama değildir** (μ + 0,798σ). "
        f"Monte Carlo {args.n_runs} koşum, tohum {args.seed}.\n"
    )
    L.append(f"**İddia sınırı:** {RISK_CLAIM}\n")

    cf = report["closed_form"]
    L.append("## 1. Kapalı form ve eğri\n")
    L.append("| α | z_α | m_α = φ(z_α)/(1−α) |\n|---|---|---|")
    from scipy.special import ndtri

    for a, m in cf["multipliers"].items():
        L.append(f"| {a.replace('.', ',')} | {_fmt(float(ndtri(float(a))), 3)} | **{_fmt(m, 3)}** |")
    L.append("")
    sig = cf["sigma_theta_median"]
    L.append(
        f"LPR-1/VIPER eğrisi (2 çapa) α'da; C3 σ yalnız ve C3 ⊕ B3 (medyan σ_θ = {_fmt(sig, 2)}°, delta yöntemi); kap 0,9:\n"
    )
    L.append("| θ (°) | μ | σ_C3 | s_0,5 | s_0,9 | s_0,99 | s_0,5 (⊕B3) | s_0,9 (⊕B3) | s_0,99 (⊕B3) |\n|---|---|---|---|---|---|---|---|---|")
    for row in cf["curve"]:
        L.append(
            f"| {_fmt(row['slope_deg'], 0)} | {_fmt(row['mu'], 3)} | {_fmt(row['sigma_c3'], 3)} | "
            + " | ".join(_fmt(row[f'c3_{a}'], 3) for a in ALPHAS)
            + " | "
            + " | ".join(_fmt(row[f'c3b3_{a}'], 3) for a in ALPHAS)
            + " |"
        )
    L.append("")

    L.append("## 2. Site11 ince gridi (500×500): kuyruklar ve maliyet sıralaması\n")
    for rover_id, g in report["grid"].items():
        rover = get_rover(rover_id)
        L.append(f"### {rover['name']} (`{rover_id}`, eğim sınırı {rover['slope_max_deg']}°; geçilebilir hücre {_int(g['n_traversable'])})\n")
        ss = g.get("slope_sigma")
        if ss:
            L.append(f"- Eğim σ_θ (B3, {ss['n_clones']} klon, `{ss['source']}`): medyan **{_fmt(ss['median_deg'], 2)}°**, p95 {_fmt(ss['p95_deg'], 2)}°.")
        else:
            L.append("- Eğim σ_θ: klon önbelleği yok — eğim kriteri nominal, slip kuyruğu yalnız C3 σ.")
        L.append(f"- Slip μ medyanı {_fmt(g['slip_mu_median'], 3)}; μ kapıda {_pct(g['cap_fraction_mu'])}; enerji kriteri 1,0'da doymuş {_pct(g['energy_saturated_nominal'])} (nominal).")
        L.append("")
        L.append("| α | m_α | CVaR slip medyanı (C3 / ⊕B3) | slip kapıda | eğim kuyruğu sınırda | Spearman (maliyet ↔ nominal) | maliyet ort. / maks bağıl değişim | enerji doymuş |\n|---|---|---|---|---|---|---|---|")
        for a in ALPHAS:
            r = g["alpha"][str(a)]
            L.append(
                f"| {_fmt(a)} | {_fmt(r['multiplier'], 3)} | {_fmt(r['slip_cvar_median_c3'], 3)} / {_fmt(r['slip_cvar_median'], 3)} | "
                f"{_pct(r['cap_fraction'])} | {_pct(r['slope_at_limit_fraction'])} | {_fmt(r['spearman_vs_nominal'], 4)} | "
                f"+{_pct(r['cost_mean_rel_change'])} / +{_pct(r['cost_max_rel_change'])} | {_pct(r['energy_saturated'])} |"
            )
        t = g["thermal"]
        L.append("")
        L.append(
            f"Termal kriter (`f_thermal`, iki uç): geçilebilir hücrelerin **{_pct(t['f_ge_0.99'])}**'inde ≥ 0,99, "
            f"{_pct(t['f_ge_0.9'])}'inde ≥ 0,9 (medyan {_fmt(t['median'], 4)}; tepe medyanı {_fmt(t['peak_median_c'], 1)} °C, "
            f"soğuk uç medyanı {_fmt(t['min_median_c'], 1)} °C). Aralık/4'ü σ sayan soğuk kuyruk (α = 0,9) doygunluğu "
            f"**{_pct(t.get('f_ge_0.99_cold_tail_0.9'))}**'e çıkarır (ortalama değişim +{_fmt(t.get('mean_change_cold_tail_0.9'), 3)}): "
            "doygunluk ekler, ayrım eklemez → termal CVaR **uygulanmadı** (kanca, `risk.thermal_cvar_cold_c`).\n"
        )

    L.append("## 3. `/api/risk-sweep` — 2-B ince grid, standart çiftler\n")
    L.append("Her satır kendi rotasının **ortalama-slip fiziği**dir (α süreyi değiştirmez); örtüşme = nominal rotayla hücre Jaccard'ı.\n")
    for pair in PAIRS_2D:
        sw = report["sweep"].get(pair["key"])
        L.append(f"### {pair['label']} (`{pair['rover_id']}`)\n")
        if not sw or sw.get("status") != 200:
            L.append(f"Tarama başarısız: {sw}\n")
            continue
        L.append(f"Eğim σ kaynağı: `{sw['slope_sigma_source']}`; dört plan {_fmt(sw['seconds'], 1)} s.\n")
        L.append("| α | nokta | mesafe (km) | süre (h) | tüketim (Wh) | min SOC | ort. / maks slip (μ) | ort. CVaR slip | risk-ayarlı sürüş saati | maks eğim kuyruğu (°) | örtüşme | plan (ms) |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in sw["rows"]:
            if r["error"]:
                L.append(f"| {_alpha_label(r['alpha'])} | — | {r['error']} |")
                continue
            L.append(
                f"| {_alpha_label(r['alpha'])} | {_int(r['waypoints'])} | {_fmt(r['distance_km'], 3)} | {_fmt(r['hours'], 3)} | {_fmt(r['energy_wh'], 1)} | "
                f"{_fmt(r['min_soc'], 2)} | {_fmt(r['mean_slip'], 3)} / {_fmt(r['max_slip'], 3)} | {_fmt(r['mean_slip_cvar'], 3)} | "
                f"{_fmt(r['risk_adjusted_hours'], 3)} | {_fmt(r['max_slope_cvar_deg'], 1)} | {_fmt(r['overlap'], 2)} | {_int(r['plan_ms'])} |"
            )
        m = sw["risk_matrix"]
        L.append("")
        L.append("Risk matrisi — her rota (satır) her α'da (sütun) yeniden fiyatlandı, risk-ayarlı sürüş saati:\n")
        L.append("| rota α \\ değerlendirme α | " + " | ".join(_fmt(a) for a in m["eval_alphas"]) + " |\n|---|" + "---|" * len(m["eval_alphas"]))
        for ra, row in zip(m["route_alphas"], m["risk_adjusted_hours"]):
            L.append(f"| {_alpha_label(ra)} | " + " | ".join(_fmt(v, 3) for v in row) + " |")
        comp = sw.get("comparison") or {}
        if comp:
            L.append("")
            L.append(
                "Nominale göre Δ: "
                + "; ".join(
                    f"α = {_fmt(d['risk_alpha'])}: mesafe {_signed(d['distance_km'])} km, süre {_signed(d['hours'])} h, "
                    f"tüketim {_signed(d['energy_wh'], 1)} Wh, min SOC {_signed(d['min_battery_pct'], 2)} pt, "
                    f"ort. slip {_signed(d['mean_slip'], 4)}, maks slip {_signed(d['max_slip'], 4)}"
                    for d in comp["deltas"]
                )
                + f". α = {_fmt(comp['evaluated_at_alpha'])}'da en düşük risk-ayarlı sürüş saatini taşıyan rota: "
                + ("**nominal** (α rotaları kuyrukta daha pahalı)" if comp["lowest_risk_adjusted_hours_alpha"] is None else f"α = {_fmt(comp['lowest_risk_adjusted_hours_alpha'])}")
                + f" ({_fmt(comp['lowest_risk_adjusted_hours'], 3)} h).\n"
            )

    L.append("## 4. `/api/plan-4d` + B5 stres testi (SHERPA) — standart rotalar, coarsen 4\n")
    if report.get("routes_4d") is None:
        L.append(f"Atlandı: {report.get('routes_4d_reason')}\n")
    else:
        for case in CASES_4D:
            res = report["routes_4d"].get(case["key"])
            L.append(f"### {case['label']} (`{case['rover_id']}`)\n")
            if not res:
                L.append("Ölçülmedi.\n")
                continue
            L.append("| α | dilim × saat | hamle / bekleme | varış (h) | min SOC | ort. / maks slip (μ) | ort. / maks CVaR slip | maks eğim kuyruğu (°) | sürüş h → risk-ayarlı | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | B5 nominal min SOC | düğüm | plan (s) |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for label, e in res.items():
                if e.get("status") != 200:
                    L.append(f"| {label} | **{e.get('status')}** | {e.get('detail')} |")
                    continue
                st = e.get("stress") or {}
                b5 = "—" if not st or "error" in st else f"{_pct(st['completion'])} / {_pct(st['within_reserve'])} / {_pct(st['full_success'])}"
                L.append(
                    f"| {label} | {e['n_slices']} × {_fmt(e['slice_hours'], 4)} | {e['moves']} / {e['waits']} | {_fmt(e['arrival_hours'], 3)} | {_fmt(e['min_soc'], 1)} | "
                    f"{_fmt(e['mean_slip'], 3)} / {_fmt(e['max_slip'], 3)} | {_fmt(e['mean_slip_cvar'], 3)} / {_fmt(e['max_slip_cvar'], 3)} | {_fmt(e['max_slope_cvar_deg'], 1)} | "
                    f"{_fmt(e['drive_hours'], 2)} → {_fmt(e['risk_adjusted_hours'], 2)} | {_fmt(e['overlap'], 2)} | {b5} | {_fmt(st.get('nominal_min_battery_pct'), 1) if st else '—'} | {_int(e['nodes_expanded'])} | {_fmt(e['plan_s'], 1)} |"
                )
            L.append("")

    L.append("## 5. Okuma\n")
    L.append(_reading(report))
    L.append("")
    L.append(
        "**Kaynaklar:** STEP — Fan, Otsu, Kitahara, Zhang, Agha-mohammadi, RSS 2021 (arXiv 2103.02828; genişletilmiş 2303.01614); "
        "Endo, Taniai, Ishigami, ICRA 2023 (arXiv 2303.01169) — *\"%11 → %95 başarı, maksimum slip %92,9 → %63,7\"* onların **sentetik** "
        "deneylerinin sayılarıdır, bu raporun değil; Rockafellar & Uryasev 2000 (kapalı form). Slip σ: C3 çapaları (varsayım); eğim σ: NASA PGDA "
        "Site11 DEM klonları (B3, DERIVED); termal σ: kaynak yok.\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")


def _reading(report: dict) -> str:
    parts = []
    g = report["grid"].get("lpr_1")
    if g:
        a99 = g["alpha"]["0.99"]
        parts.append(
            f"- **Grid:** α = 0,99'da CVaR slip medyanı {_fmt(g['slip_mu_median'], 3)} → {_fmt(a99['slip_cvar_median'], 3)}, hücrelerin {_pct(a99['cap_fraction'])}'i 0,9 kapısında, "
            f"eğim kuyruğu hücrelerin {_pct(a99['slope_at_limit_fraction'])}'inde sınıra dayanıyor; maliyet sıralaması nominale Spearman {_fmt(a99['spearman_vs_nominal'], 3)} "
            f"(ortalama +{_pct(a99['cost_mean_rel_change'])}). Enerji kriteri α = 0,99'da hücrelerin {_pct(a99['energy_saturated'])}'inde doyuyor "
            f"(nominal {_pct(g['energy_saturated_nominal'])}) — C3'ün slip'siz ölçek kararının bedeli."
        )
    for pair in PAIRS_2D:
        sw = report["sweep"].get(pair["key"])
        if not sw or sw.get("status") != 200 or not sw.get("comparison"):
            continue
        d = sw["comparison"]["deltas"][-1]
        winner = sw["comparison"]["lowest_risk_adjusted_hours_alpha"]
        parts.append(
            f"- **2-B, {pair['label']}:** α = 0,99 rotası nominalle {_pct(d['overlap_with_nominal'], 0)} örtüşüyor; tüketim {_signed(d['energy_wh'], 1)} Wh, "
            f"süre {_signed(d['hours'])} h, mesafe {_signed(d['distance_km'])} km, min SOC {_signed(d['min_battery_pct'], 2)} pt, "
            f"ort. slip {_signed(d['mean_slip'], 4)}, maks slip {_signed(d['max_slip'], 4)}. α = 0,99'da en düşük risk-ayarlı sürüş saatini "
            + ("**nominal rota** taşıyor: ağırlıklı kriterler kuyruk süresini minimize etmez." if winner is None else f"α = {_fmt(winner)} rotası taşıyor.")
        )
    routes = report.get("routes_4d") or {}
    for case in CASES_4D:
        res = routes.get(case["key"])
        if not res:
            continue
        nom = res.get("None", {})
        hi = res.get(_alpha_label(0.99), {})
        if nom.get("status") == 200 and hi.get("status") == 200:
            sn, sh = nom.get("stress") or {}, hi.get("stress") or {}
            parts.append(
                f"- **4-B, {case['label']}:** nominal {nom['moves']} hamle / {_fmt(nom['arrival_hours'], 2)} h / min SOC {_fmt(nom['min_soc'], 1)}; "
                f"α = 0,99: {hi['moves']} hamle / {_fmt(hi['arrival_hours'], 2)} h / {_fmt(hi['min_soc'], 1)} (örtüşme {_fmt(hi['overlap'], 2)}); "
                f"B5 tamamlanma {_pct(sn.get('completion'))} → {_pct(sh.get('completion'))}, rezerv içinde {_pct(sn.get('within_reserve'))} → {_pct(sh.get('within_reserve'))}, "
                f"tam başarı {_pct(sn.get('full_success'))} → {_pct(sh.get('full_success'))}; risk-ayarlı sürüş saati (α = 0,99) {_fmt(hi['risk_adjusted_hours'], 2)} vs nominal sürüş {_fmt(hi['drive_hours'], 2)}."
            )
    parts.append(
        "- **Sunum cümlesi (ölçülene göre doldurulur):** \"Risk iştahı α'yı JPL'in STEP ve Keio'nun CVaR yaklaşımıyla maliyete bağladık; "
        "α arttıkça planlayıcı slip ve eğim kuyruğu geniş hücrelerden kaçıyor. Site11'de etkisi yukarıdaki tablolardaki kadardır — nominal fizikte "
        "kazanç küçük, rota değişimi belirgin; MODEL etiketli dağılımların dönüşümüdür, ölçülmüş risk değildir.\""
    )
    return "\n".join(parts)


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(_ROOT / "docs" / "research" / "risk_sweep_report.md"))
    parser.add_argument("--json", default=None, help="also dump the raw measurements as JSON (written before the markdown)")
    parser.add_argument("--from-json", default=None, help="render the markdown from a previous --json dump instead of measuring")
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--skip-4d", action="store_true", help="skip the plan-4d + stress-test section")
    args = parser.parse_args()

    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        _write_markdown(Path(args.output), report, args)
        print(f"re-rendered {args.output}")
        return 0

    if not (_PROCESSED / "metadata.json").exists():
        print(f"processed grids not found under {_PROCESSED}; nothing measured, nothing written.")
        return 0

    t_all = time.perf_counter()
    grids = load_preprocessed_grids()
    report: dict = {"n_runs": args.n_runs, "seed": args.seed}

    print("grid level ...", flush=True)
    report["grid"] = {rid: measure_grid(grids, rid) for rid in ("lpr_1", "nasa_viper")}
    ss = report["grid"]["lpr_1"].get("slope_sigma")
    report["closed_form"] = measure_closed_form(None if ss is None else ss["median_deg"])

    app.state.grids = grids
    client = TestClient(app)
    print("2-D sweeps ...", flush=True)
    report["sweep"] = {}
    for pair in PAIRS_2D:
        print(f"  {pair['label']} ...", flush=True)
        report["sweep"][pair["key"]] = measure_sweep(client, pair)

    if args.skip_4d:
        report["routes_4d"] = None
        report["routes_4d_reason"] = "--skip-4d"
    elif not (_PROCESSED / "horizon_map.npy").exists() or not _KERNELS.exists():
        report["routes_4d"] = None
        report["routes_4d_reason"] = "horizon_map.npy veya NAIF çekirdekleri yok; 4-B rotalar ve stres testi ölçülmedi"
    else:
        print("4-D routes + SHERPA ...", flush=True)
        report["routes_4d"] = {}
        for case in CASES_4D:
            print(f"  {case['label']} ...", flush=True)
            report["routes_4d"][case["key"]] = measure_4d(client, case, args.n_runs, args.seed)
    app.state.grids = None
    report["total_seconds"] = round(time.perf_counter() - t_all, 1)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
        print(f"wrote {args.json}")
    _write_markdown(Path(args.output), report, args)
    print(f"wrote {args.output} in {report['total_seconds']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
