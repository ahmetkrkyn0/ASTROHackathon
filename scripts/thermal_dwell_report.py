#!/usr/bin/env python3
"""Measure the thermal dwell model (C6) on Site11.

What it measures, in order:

1. Nothing: JSC's unlimited-operations envelope and tolerable entrenched
   time as quoted from ICES-2025-376, then OUR envelope matrix from the
   heat1d cache (GET /api/thermal-envelope) for LPR-1 and NASA VIPER, with
   and without the thermostat assumption.
2. Site11's equilibrium inner temperature per rover (the static reading D3
   made) and the standard routes' inner temperature integrated with the
   lag: does LP-R04/R05 still fail, and when.
3. The dwell cube on the three standard 4-D pairs (LPR-1 day 28 Sep 2026,
   LPR-1 lunar night 13 Sep 2026, NASA VIPER short leg 30 May 2027):
   unlimited / cold / hot fractions, the finite median, compute time, and
   the share of blocks where B1's 10 h fault hold would outlast the dwell.
4. The constraint: /api/plan-4d with require_thermal_dwell under both
   heater models -- 200 with moves/arrival/SOC/waits, or the reasoned 404
   with the refused count.
5. Entrenchment: /api/replan at the lunar-night start and at a mid-route
   cell, entrenched 0.1 / 0.25 / 0.5 / 1.0 h -- both countdowns and the level.
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

from app import thermal_dwell as TD  # noqa: E402
from app.constants import FAULT_RECOVERY_HOURS_ASSUMED, get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import _shift_utc, app  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

CASES = (
    {"key": "lpr1_day", "label": "LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426)", "rover_id": "lpr_1",
     "start_utc": "2026-09-28T00:00:00", "start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426}},
    {"key": "night", "label": "LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450)", "rover_id": "lpr_1",
     "start_utc": "2026-09-13T00:00:00", "start": {"row": 186, "col": 34}, "goal": {"row": 494, "col": 450}},
    {"key": "viper_short", "label": "VIPER kısa leg, 30 May 2027, (358,494)→(346,462)", "rover_id": "nasa_viper",
     "start_utc": "2027-05-30T00:00:00", "start": {"row": 358, "col": 494}, "goal": {"row": 346, "col": 462}},
)
ROVERS = ("lpr_1", "nasa_viper", "luvmi_m")
ENTRENCHED_HOURS = (0.1, 0.25, 0.5, 1.0)


# ── formatting ───────────────────────────────────────────────────────────────


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "evet" if value else "hayır"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}".replace(",", " ")
    if isinstance(value, float) and not np.isfinite(value):
        return "∞" if value > 0 else "−∞"
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def _pct(value, digits: int = 1) -> str:
    return "—" if value is None else _fmt(100.0 * float(value), digits) + " %"


def _row(cells) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def _table(header, rows) -> list[str]:
    out = [_row(header), _row(["---"] * len(header))]
    out.extend(_row(r) for r in rows)
    return out


# ── measurement ──────────────────────────────────────────────────────────────


def _site_statistics(grids) -> dict:
    thermal = np.asarray(grids["thermal"], dtype=np.float64)
    cold_end = np.asarray(grids["thermal_min"], dtype=np.float64)
    passable = np.asarray(grids["traversable"], dtype=bool)
    out: dict = {
        "traversable_cells": int(passable.sum()),
        "surface_peak": {"min": float(thermal[passable].min()), "median": float(np.median(thermal[passable])), "max": float(thermal[passable].max())},
        "surface_cold_end": {"min": float(cold_end[passable].min()), "median": float(np.median(cold_end[passable])), "max": float(cold_end[passable].max())},
        "rovers": {},
    }
    for rid in ROVERS:
        rover = get_rover(rid)
        env = TD.rover_envelope(rover)
        entry: dict = {
            "name": rover["name"],
            "tau_s": rover.get("thermal_tau_s"),
            "envelope": None if env is None else env.as_dict(),
            "nominal_inner_c": TD.nominal_inner_c(rover),
            "unavailable_reason": TD.dwell_unavailable_reason(rover),
        }
        for name, surface in (("peak", thermal), ("cold_end", cold_end)):
            inner = TD.inner_target_c(surface[passable], rover)
            stats = {"inner_min": float(inner.min()), "inner_median": float(np.median(inner)), "inner_max": float(inner.max())}
            if env is not None:
                inside = (inner >= env.lo) & (inner <= env.hi)
                stats.update(
                    fraction_inside=float(inside.mean()),
                    fraction_cold=float((inner < env.lo).mean()),
                    fraction_hot=float((inner > env.hi).mean()),
                )
                if entry["tau_s"]:
                    hours, _s, _c = TD.exit_time_h(np.full(inner.shape, TD.nominal_inner_c(rover)), inner, env, float(entry["tau_s"]))
                    finite = hours[np.isfinite(hours)]
                    stats.update(
                        dwell_unlimited_fraction=float(np.isinf(hours).mean()),
                        dwell_finite_median_h=None if finite.size == 0 else float(np.median(finite)),
                        dwell_finite_p95_h=None if finite.size == 0 else float(np.percentile(finite, 95)),
                        dwell_under_fault_hold_fraction=float((hours < FAULT_RECOVERY_HOURS_ASSUMED).mean()),
                    )
            entry[name] = stats
        if env is not None and entry["tau_s"]:
            for label, surface_c in (("psr_floor", -183.15), ("gate", -150.0), ("minus_100", -100.0)):
                target = float(TD.inner_target_c(np.array([surface_c]), rover)[0])
                hours, _s, _c = TD.exit_time_h(np.array([TD.nominal_inner_c(rover)]), np.array([target]), env, float(entry["tau_s"]))
                entry[f"dwell_{label}_h"] = None if not np.isfinite(hours[0]) else float(hours[0])
        out["rovers"][rid] = entry
    return out


def _plan(client, case: dict, **extra) -> tuple[int, dict, float]:
    body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"], "start_utc": case["start_utc"], **extra}
    t0 = time.perf_counter()
    response = client.post("/api/plan-4d", json=body)
    return response.status_code, response.json(), time.perf_counter() - t0


def _route_summary(payload: dict) -> dict:
    metrics = payload["metrics"]
    block = payload["thermal_dwell"]
    inner = payload.get("path_inner_c") or []
    return {
        "moves": metrics["move_steps"],
        "wait_steps": metrics["wait_steps"],
        "arrival_hours": metrics.get("arrival_hours"),
        "min_battery_pct": metrics["min_battery_pct"],
        "final_battery_pct": metrics["final_battery_pct"],
        "nodes_expanded": metrics["nodes_expanded"],
        "planner_ms": metrics["computation_time_ms"],
        "refused_thermal": metrics["edges_rejected"].get("thermal_dwell"),
        "enforced": metrics["thermal_dwell_enforced"],
        "states_past_thermal_dwell": metrics.get("states_past_thermal_dwell"),
        "min_dwell_margin_h": metrics.get("min_dwell_margin_h"),
        "max_stay_h": metrics.get("max_stay_h"),
        "cube": block.get("cube"),
        "cube_compute_ms": (block.get("dwell_model") or {}).get("compute_ms"),
        "cube_n_states": (block.get("dwell_model") or {}).get("n_states"),
        "route": block.get("route"),
        "inner_min_c": None if not inner else min(inner),
        "inner_final_c": None if not inner else inner[-1],
        "n_states": len(payload["path_states"]),
        "slice_hours": payload["slice_hours"],
        "n_slices": payload["n_slices"],
        "heater_model": block.get("heater_model"),
        "safety_r04_r05_r12": {
            e["id"]: {"rho": e.get("rho"), "satisfied": e.get("satisfied"), "applicable": e.get("applicable")}
            for e in payload.get("safety_margins", {}).get("requirements", [])
            if e["id"] in ("LP-R04", "LP-R05", "LP-R12")
        },
    }


def _fault_hold_fraction(client, case: dict) -> dict:
    """Share of passable blocks whose dwell at the first slice is shorter
    than B1's 10 h fault hold, from the coarse layer (12 h lookahead)."""
    params = {"start_utc": case["start_utc"], "rover_id": case["rover_id"], "lookahead_hours": 12.0, "format": "f32", "field": "max_dwell_h"}
    t0 = time.perf_counter()
    response = client.get("/api/thermal-dwell", params=params)
    seconds = time.perf_counter() - t0
    if response.status_code != 200:
        return {"status": response.status_code, "detail": response.json().get("detail")}
    values = np.frombuffer(response.content, dtype="<f4").astype(np.float64)
    finite = values[np.isfinite(values)]
    return {
        "status": 200,
        "blocks": int(finite.size),
        "fraction_under_fault_hold": float(np.mean(finite < FAULT_RECOVERY_HOURS_ASSUMED)),
        "fraction_open_ended_12h": float(np.mean(finite >= 12.0 - 1e-6)),
        "median_h": float(np.median(finite)),
        "seconds": seconds,
    }


def _entrenchment(client, case: dict, current: dict, utc: str, label: str) -> dict:
    out: dict = {"label": label, "current": current, "utc": utc, "levels": []}
    for hours in ENTRENCHED_HOURS:
        body = {"current": current, "goal": case["goal"], "rover_id": case["rover_id"], "utc": utc, "state": {"entrenched_hours": hours}}
        t0 = time.perf_counter()
        payload = client.post("/api/replan", json=body).json()
        block = payload.get("entrenchment") or {}
        out["levels"].append(
            {
                "entrenched_hours": hours,
                "overall": block.get("overall"),
                "thermal": None if block.get("thermal") is None else {k: block["thermal"].get(k) for k in ("tolerable_h", "remaining_h", "level", "side", "component", "open_ended", "initial_inner_c")},
                "haven": None if block.get("haven") is None else {k: block["haven"].get(k) for k in ("tolerable_h", "remaining_h", "level", "hours_until_earthset", "time_to_safe_haven_h", "note")},
                "replanned": payload.get("replanned"),
                "fired": [t["trigger_id"] for t in payload.get("triggers", [])],
                "seconds": time.perf_counter() - t0,
            }
        )
        if not out.get("shadow_model"):
            out["shadow_model"] = block.get("shadow_model")
            out["entrenchment_model"] = payload.get("entrenchment_model")
    return out


def measure(skip_envelope: bool, heaters: tuple[str, ...]) -> dict:
    grids = load_preprocessed_grids()
    app.state.grids = grids
    client = TestClient(app)
    started = time.perf_counter()
    data: dict = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quoted": TD.JSC_QUOTED,
        "claim": TD.THERMAL_DWELL_CLAIM,
        "scope": TD.THERMAL_DWELL_SCOPE,
        "site": _site_statistics(grids),
        "envelope": {},
        "cases": {},
        "entrenchment": [],
    }

    if not skip_envelope:
        for rid in ("lpr_1", "nasa_viper"):
            for heater in heaters:
                response = client.get("/api/thermal-envelope", params={"rover_id": rid, "heater_model": heater})
                key = f"{rid}:{heater}"
                if response.status_code != 200:
                    data["envelope"][key] = {"status": response.status_code, "detail": response.json().get("detail")}
                    continue
                payload = response.json()
                cells = payload["cells"]
                sampled = [c for c in cells if c["verdict"] != "unsampled"]
                hot = [c for c in cells if c["verdict"] == "hot_limited"]
                data["envelope"][key] = {
                    "status": 200,
                    "counts": payload["counts"],
                    "meta": payload["meta"],
                    "surface_max_c": max(c["surface_c_max"] for c in sampled) if sampled else None,
                    "hot_surface_max_c": max(c["surface_c_max"] for c in hot) if hot else None,
                    "hot_surface_min_c": min(c["surface_c_max"] for c in hot) if hot else None,
                    "axes": payload["axes"],
                    "cells": cells,
                }

    for case in CASES:
        entry: dict = {"label": case["label"], "rover_id": case["rover_id"], "start_utc": case["start_utc"], "runs": {}}
        status, payload, seconds = _plan(client, case)
        entry["runs"]["report_only"] = {"status": status, "seconds": seconds, **(_route_summary(payload) if status == 200 else {"detail": payload.get("detail")})}
        for heater in heaters:
            status, payload, seconds = _plan(client, case, require_thermal_dwell=True, heater_model=heater)
            run: dict = {"status": status, "seconds": seconds, "heater_model": heater}
            if status == 200:
                run.update(_route_summary(payload))
            else:
                run["detail"] = payload.get("detail")
            entry["runs"][f"enforced:{heater}"] = run
        entry["fault_hold"] = _fault_hold_fraction(client, case)
        data["cases"][case["key"]] = entry

    night = CASES[1]
    data["entrenchment"].append(_entrenchment(client, night, night["start"], night["start_utc"], "Ay gecesi başlangıcı"))
    report = data["cases"]["night"]["runs"]["report_only"]
    if report.get("status") == 200:
        status, payload, _s = _plan(client, night)
        states = payload["path_states"]
        pixels = payload["path_pixels"]
        mid = len(states) // 2
        utc = _shift_utc(night["start_utc"], float(states[mid][2]) * float(payload["slice_hours"]))
        data["entrenchment"].append(
            _entrenchment(client, night, {"row": int(pixels[mid][0]), "col": int(pixels[mid][1])}, utc, f"Ay gecesi rota ortası (durum #{mid}, dilim {states[mid][2]})")
        )
    day = CASES[0]
    data["entrenchment"].append(_entrenchment(client, day, day["start"], day["start_utc"], "LPR-1 gündüz başlangıcı"))
    data["total_seconds"] = time.perf_counter() - started
    return data


# ── rendering ────────────────────────────────────────────────────────────────


def _envelope_table(entry: dict) -> list[str]:
    axes = entry["axes"]
    el_edges = axes["el_deg"]["edges"]
    sp_edges = axes["s_par_deg"]["edges"]
    cells = {(c["el_bin"], c["s_par_bin"]): c for c in entry["cells"]}
    letters = {"unlimited": "S", "cold_limited": "s", "hot_limited": "h", "unsampled": "·"}
    sp_cols = list(range(0, len(sp_edges) - 1, 2))
    header = ["yükseklik \\ s_par (°)"] + [_fmt(0.5 * (sp_edges[j] + sp_edges[j + 1]), 1) for j in sp_cols]
    rows = []
    for i in range(len(el_edges) - 1):
        row = [_fmt(0.5 * (el_edges[i] + el_edges[i + 1]), 2)]
        for j in sp_cols:
            c = cells[(i, j)]
            if c["verdict"] == "unsampled":
                row.append("·")
            else:
                row.append(f"{letters[c['verdict']]} {_fmt(c['surface_c_max'], 0)}")
        rows.append(row)
    return _table(header, rows)


def render(data: dict) -> str:
    q = data["quoted"]
    site = data["site"]
    lines: list[str] = []
    lines.append("# Termal operasyon zarfı ve tolere edilebilir saplanma süresi — C6 raporu")
    lines.append("")
    lines.append(
        f"Üretildi {data['generated_utc']} · `python scripts/thermal_dwell_report.py` (Site11, coarsen 4; toplam "
        f"{_fmt(data.get('total_seconds', 0.0) / 60.0, 1)} dk). Sayıların hepsi bu makinede koşturulup okundu; "
        "JSC'nin sayıları **alıntıdır** ve ayrı tabloda durur."
    )
    lines.append("")
    lines.append(
        "Okuma notu: termal model MODEL/UNCALIBRATED'dır (heat1d tepe LUT'u + gölge bağlaması, regolit gevşemesi "
        "kalibre edilmemiş, iç sıcaklık ofsetleri kataloğun MODELLED alanları). Isıtıcı sıcaklık modeline yalnız "
        "`heater_model=\"thermostat_assumed\"` **varsayımıyla** girer; varsayılan `none`. Hiçbir yerde termal doğruluk "
        "iddiası yoktur (Diviner karşılaştırması C5'in işi)."
    )
    lines.append("")

    # 1. JSC vs ours
    lines.append("## 1. JSC'nin zarfı (alıntı) ve bizim zarf matrisimiz (heat1d, Site11 enlemi)")
    lines.append("")
    lines.append("**Alıntı (ICES-2025-376, Slusser vd. 2025):**")
    lines.append("")
    lines.append(f"- Kutupta maksimum Güneş yüksekliği **{_fmt(q['max_polar_sun_elevation_deg'], 1)}°**; {q['sun_elevation_rule']}.")
    lines.append(f"- Zarf eksenleri: {q['envelope_axes']}.")
    lines.append(f"- Durum matrisi **{q['case_matrix']}** ({q['case_matrix_note']}); {q['components_screened']}.")
    ex = q["aft_exceedance_example"]
    lines.append(f"- AFT aşım örneği: {ex['component']}, AFT {_fmt(ex['aft_c'], 0)} °C, model {_fmt(ex['modelled_c'], 0)} °C → **{_fmt(ex['exceedance_c'], 0)} °C aşım** ({ex['note']}).")
    lines.append(f"- Tolere edilebilir saplanma süresi: {q['tolerable_entrenched_time']}. Kısıtlar: {q['entrenched_time_caveats']}.")
    lines.append(f"- Araç: {q['tool']}; haven geceleri {_fmt(q['safe_haven_night_hours']['shortest'], 0)}–{_fmt(q['safe_haven_night_hours']['typical_range'][1], 0)} h.")
    lines.append("")
    lines.append(
        "**Bizim matrisimiz:** JSC'nin açısal ekseni rover başlığına göre Güneş azimutudur (rover gövdesi/TMS modeli "
        "gerektirir; LunaPath'te yok). Bizim eksenlerimiz **Güneş yüksekliği × Güneş'e paralel eğim bileşeni** "
        "(`s_par = atan(tan s · cos(az_Güneş − bakı))`, pozitif = Güneş'e bakan); heat1d transient'i (13 Ay günü, "
        "crank-nicolson) her adımda kutulanır, kutu başına **maksimum** yüzey sıcaklığı alınır; iç sıcaklık kataloğun "
        "ofsetleriyle, karar en dar zarfa göre. Aynı yöntem, bizim model; karşılaştırma değil."
    )
    lines.append("")
    if not data["envelope"]:
        lines.append("_Zarf önbelleği ölçülmedi (`--skip-envelope`)._")
    for key, entry in data["envelope"].items():
        rid, heater = key.split(":")
        rover = get_rover(rid)
        lines.append(f"### {rover['name']} — `heater_model={heater}`")
        lines.append("")
        if entry.get("status") != 200:
            lines.append(f"Uç {entry.get('status')}: {entry.get('detail')}")
            lines.append("")
            continue
        counts = entry["counts"]
        meta = entry["meta"]
        lines.append(
            f"heat1d: enlem {_fmt(meta.get('lat_deg'), 4)}°, eğimler {meta.get('slopes_deg')}, {_fmt(meta.get('n_samples'))} örnek, "
            f"{_fmt(meta.get('bins_visited'))}/{_fmt(meta.get('bins_total'))} kutu örneklendi, yüzey {_fmt(meta.get('surface_c_min'), 1)}…"
            f"{_fmt(meta.get('surface_c_max'), 1)} °C, Güneş yüksekliği {_fmt(meta.get('el_deg_min'), 2)}…{_fmt(meta.get('el_deg_max'), 2)}°, "
            f"{_fmt(meta.get('seconds'), 1)} s."
        )
        lines.append("")
        lines.append(
            f"Kararlar: **sınırsız {counts['unlimited']}**, soğuk-sınırlı {counts['cold_limited']}, sıcak-sınırlı {counts['hot_limited']}, "
            f"örneklenmedi {counts['unsampled']}. En sıcak yüzey {_fmt(entry['surface_max_c'], 1)} °C"
            + (
                f"; 'sıcak-sınırlı' kutuların yüzeyi {_fmt(entry['hot_surface_min_c'], 1)}…{_fmt(entry['hot_surface_max_c'], 1)} °C "
                "— hepsi 0 °C altı: ofset modelinin soğuk dalı (+60 K) bu bandı 35 °C üstüne atar; gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok."
                if entry["hot_surface_max_c"] is not None
                else "; sıcak-sınırlı kutu yok."
            )
        )
        lines.append("")
        lines.append("Kutu harfi: S sınırsız, s soğuk-sınırlı, h sıcak-sınırlı, · örneklenmedi; sayı kutunun maks yüzey sıcaklığı (°C); s_par sütunlarının her ikincisi.")
        lines.append("")
        lines.extend(_envelope_table(entry))
        lines.append("")

    # 2. site statistics and D3 revisited
    lines.append("## 2. Site11'de denge iç sıcaklığı ve D3'ün bulgusu dinamikle")
    lines.append("")
    lines.append(
        f"Geçilebilir {_fmt(site['traversable_cells'])} ince hücre; yüzey tepe {_fmt(site['surface_peak']['min'], 1)}…{_fmt(site['surface_peak']['max'], 1)} °C "
        f"(medyan {_fmt(site['surface_peak']['median'], 1)}), soğuk uç {_fmt(site['surface_cold_end']['min'], 1)}…{_fmt(site['surface_cold_end']['max'], 1)} °C "
        f"(medyan {_fmt(site['surface_cold_end']['median'], 1)})."
    )
    lines.append("")
    rows = []
    for rid, r in site["rovers"].items():
        env = r["envelope"]
        peak, cold = r["peak"], r["cold_end"]
        rows.append([
            r["name"],
            "—" if env is None else f"[{_fmt(env['lo_c'], 0)}, {_fmt(env['hi_c'], 0)}] ({env['lo_component']})",
            _fmt(r["tau_s"], 0) if r["tau_s"] else "yok",
            _fmt(r["nominal_inner_c"], 1),
            f"{_fmt(peak['inner_min'], 1)} / {_fmt(peak['inner_median'], 1)} / {_fmt(peak['inner_max'], 1)}",
            _pct(peak.get("fraction_inside")) + f" (soğuk {_pct(peak.get('fraction_cold'))}, sıcak {_pct(peak.get('fraction_hot'))})",
            _pct(cold.get("fraction_inside")),
            "—" if r.get("dwell_psr_floor_h") is None else f"{_fmt(r['dwell_psr_floor_h'] * 60.0, 1)} dk",
            "—" if peak.get("dwell_finite_median_h") is None else f"{_fmt(peak['dwell_finite_median_h'], 2)} h / {_pct(peak.get('dwell_unlimited_fraction'))}",
            "—" if cold.get("dwell_under_fault_hold_fraction") is None else _pct(cold["dwell_under_fault_hold_fraction"]),
        ])
    lines.extend(_table(
        ["Rover", "Zarf (°C)", "τ (s)", "T₀", "İç @tepe min / med / maks", "Zarf içi @tepe", "Zarf içi @soğuk uç", "PSR tabanına dwell", "Dwell @tepe medyan / sınırsız", "10 h bekleme > dwell (@soğuk uç)"],
        rows,
    ))
    lines.append("")
    lines.append(
        "Okuma: D3 statik katmanla LP-R04/R05'i her rotada ihlal buldu (VIPER 30 May 2027 elektronik −7,96 °C, batarya −27,96 °C; "
        "LPR-1 28 Eyl 2026 −17,96 / −27,96 °C — D3 raporundan). Dinamikle soru \"ne kadar sonra\" olur: aşağıdaki tablo standart "
        "rotalarda iç sıcaklığın rota boyunca entegrasyonunu verir (başlangıç T₀ nominal, hedef varılan bloğun yüzeyi)."
    )
    lines.append("")
    rows = []
    for key, case in data["cases"].items():
        run = case["runs"]["report_only"]
        if run.get("status") != 200:
            rows.append([case["label"], f"{run.get('status')}: {run.get('detail')}", "", "", "", "", ""])
            continue
        inner = (run.get("route") or {}).get("inner") or {}
        s = run["safety_r04_r05_r12"]
        rows.append([
            case["label"],
            f"{_fmt(run['moves'])} / {_fmt(run['arrival_hours'], 3)} h / {_fmt(run['n_states'])}",
            f"{_fmt(inner.get('min_c'), 2)} / {_fmt(inner.get('max_c'), 2)}",
            "—" if inner.get("first_exit_h") is None else f"{_fmt(inner['first_exit_h'], 3)} h ({inner.get('side')}, {inner.get('component')})",
            f"{_fmt(inner.get('states_outside'))} / {_fmt(run['n_states'])}",
            f"{_fmt(run['inner_final_c'], 2)}",
            f"R04 {_fmt((s.get('LP-R04') or {}).get('rho'), 2)} / R05 {_fmt((s.get('LP-R05') or {}).get('rho'), 2)} / R12 {_fmt((s.get('LP-R12') or {}).get('rho'), 2)}",
        ])
    lines.extend(_table(
        ["Rota", "Hamle / varış / durum", "İç min / maks (°C)", "İlk zarf çıkışı", "Zarf dışı durum", "Varışta iç (°C)", "D3 ρ (statik) R04 / R05; R12 (dwell marjı, h)"],
        rows,
    ))
    lines.append("")

    # 3. dwell cubes
    lines.append("## 3. max_dwell küpü: üç rota, dilim 0")
    lines.append("")
    rows = []
    for key, case in data["cases"].items():
        run = case["runs"]["report_only"]
        cube = run.get("cube") or {}
        fh = case.get("fault_hold") or {}
        rows.append([
            case["label"],
            f"{_fmt(run.get('n_slices'))} × {_fmt(run.get('slice_hours'), 4)} h",
            _fmt(run.get("cube_n_states")),
            _fmt(run.get("cube_compute_ms"), 0) + " ms",
            _fmt(cube.get("traversable_blocks")),
            _pct(cube.get("fraction_unlimited")),
            _pct(cube.get("fraction_cold_limited")),
            _pct(cube.get("fraction_hot_limited")),
            "—" if cube.get("finite_median_h") is None else f"{_fmt(cube['finite_median_h'], 3)} h (p5 {_fmt(cube.get('finite_p5_h'), 3)}, p95 {_fmt(cube.get('finite_p95_h'), 3)})",
            "—" if fh.get("status") != 200 else f"{_pct(fh['fraction_under_fault_hold'])} (12 h katman, {_fmt(fh['seconds'], 1)} s)",
        ])
    lines.extend(_table(
        ["Rota", "Dilim", "Durum (t₀ × blok)", "Küp süresi", "Blok", "Sınırsız", "Soğuk-sınırlı", "Sıcak-sınırlı", "Sonlu dwell medyanı", f"B1'in {_fmt(FAULT_RECOVERY_HOURS_ASSUMED, 0)} h beklemesi > dwell"],
        rows,
    ))
    lines.append("")
    lines.append(
        "Okuma: 'sınırsız' = hedef iç sıcaklık zarf içinde (ufuk boyunca çıkmıyor); soğuk-sınırlı = gölge/soğuk yüzey; "
        "sıcak-sınırlı = ofset modelinin −25…0 °C yüzey bandı. Son sütun B1'in 10 saatlik arıza beklemesinin (varsayım) "
        "termal olarak dayanılamayacak blok kesridir — B1'in DP'sine bağlanmadı (B1 spec'i), yalnız sayı verildi."
    )
    lines.append("")

    # 4. constraint
    lines.append("## 4. Kısıt: `require_thermal_dwell` iki ısıtıcı modelinde")
    lines.append("")
    rows = []
    for key, case in data["cases"].items():
        for run_key, run in case["runs"].items():
            if run_key == "report_only":
                label = "kısıtsız (rapor)"
            else:
                label = f"kısıt, `{run['heater_model']}`"
            if run.get("status") == 200:
                rows.append([
                    case["label"], label, "200",
                    f"{_fmt(run['moves'])} / {_fmt(run['wait_steps'])}",
                    f"{_fmt(run['arrival_hours'], 3)} h",
                    f"{_fmt(run['min_battery_pct'], 1)} / {_fmt(run['final_battery_pct'], 1)} %",
                    _fmt(run.get("refused_thermal")),
                    f"{_fmt(run['nodes_expanded'])} / {_fmt(run['planner_ms'] / 1000.0, 1)} s",
                    f"{_fmt(run['inner_min_c'], 1)} °C",
                ])
            else:
                detail = (run.get("detail") or "")
                thermal_part = detail.split("Thermal dwell:")[-1].strip() if "Thermal dwell:" in detail else detail
                rows.append([case["label"], label, str(run.get("status")), "—", "—", "—", "—", f"{_fmt(run.get('seconds'), 1)} s", thermal_part[:220]])
    lines.extend(_table(["Rota", "Mod", "HTTP", "Hamle / bekleme", "Varış", "Min / son SOC", "Termal ret", "Düğüm / süre", "Rota iç min ya da 404 gerekçesi"], rows))
    lines.append("")
    lines.append(
        "Okuma: kısıt iç sıcaklığın **kendisini** etiket ekseni olarak taşır (kalış süresini değil): ilk sürümdeki 'kalış ≤ dwell' "
        "kuralını planlayıcı iki karanlık blok arasında ileri-geri hamleyle boşa çıkarıyordu (testte bulundu); gölgede kıpırdanmak da "
        "soğutur. `none` altında Site11'de rota gölgeden geçiyorsa çeyrek saat mertebesinde çıkış kaçınılmazdır; `thermostat_assumed` "
        "soğuk yanı ısıtıcıya bırakır (VARSAYIM) ve yalnız sıcak yan kalır."
    )
    lines.append("")

    # 5. entrenchment
    lines.append("## 5. Saplanma geri sayımı (`/api/replan`, `state.entrenched_hours`)")
    lines.append("")
    lines.append(
        "Okuma: iki geri sayım vardır — bloğun **termal** dwell'i (bu özellik) ve JSC'nin tanımı olan **haven penceresi** "
        "(A4 Dünya bağlantısı − A1 en yakın haven'a sürüş). A1'in bulgusu gereği LPR-1'in Site11'de **hiçbir epokta ulaşılabilir "
        "haven'ı yok** (Ay gecesi başlangıcında Dünya bağlantısı da yok): haven bütçesi 0 h, yani JSC'nin saati saplanmadan önce "
        "dolmuş sayılır ve `overall` her saplanma süresinde **fail** verir. Termal sütun tek başına okunmalı: 0,1 h → ok, "
        "0,25 h → warning (bütçenin ~%50'si), 0,5 h → fail. Seviye eşikleri (%50/%80/%100) bizim seçimimizdir."
    )
    lines.append("")
    for ent in data["entrenchment"]:
        lines.append(f"### {ent['label']} — piksel ({ent['current']['row']}, {ent['current']['col']}), {ent['utc']}")
        lines.append("")
        sm = ent.get("shadow_model") or {}
        lines.append(f"Gölge serisi: {sm.get('model')}" + (f" ({sm.get('reason')})" if sm.get("reason") else "") + ".")
        lines.append("")
        rows = []
        for lv in ent["levels"]:
            th = lv.get("thermal") or {}
            hv = lv.get("haven")
            ov = lv.get("overall") or {}
            rows.append([
                f"{_fmt(lv['entrenched_hours'], 2)} h",
                "—" if not th else ("∞" if th.get("open_ended") else f"{_fmt(th.get('tolerable_h'), 3)} h ({th.get('side')}/{th.get('component')})"),
                "—" if not th else ("∞" if th.get("open_ended") else _fmt(th.get("remaining_h"), 3) + " h"),
                "yok" if hv is None else ("∞" if hv.get("tolerable_h") is None else f"{_fmt(hv['tolerable_h'], 2)} h (Dünya {_fmt(hv.get('hours_until_earthset'), 1)} h − haven {_fmt(hv.get('time_to_safe_haven_h'), 2)} h)"),
                f"**{ov.get('level')}** ({ov.get('limiting') or '—'})",
                _fmt(lv.get("replanned")),
                ", ".join(lv.get("fired") or []) or "—",
                f"{_fmt(lv.get('seconds'), 2)} s",
            ])
        lines.extend(_table(["Saplanma", "Termal bütçe", "Termal kalan", "Haven penceresi", "Seviye (sınırlayıcı)", "Replan", "Ateşleyen", "Süre"], rows))
        lines.append("")

    # 6. claim
    lines.append("## 6. İddia sınırı ve sunum cümlesi")
    lines.append("")
    lines.append(f"- **İddia:** {data['claim']}")
    lines.append(f"- **Kapsam:** {data['scope']}")
    lines.append(
        "- **Doğru cümle:** \"NASA JSC'nin VIPER için kullandığı iki çerçeveyi — sınırsız operasyon zarfı ve tolere edilebilir "
        "saplanma süresi — LunaPath'in kendi termal modeliyle kurduk: heat1d transient'inden Güneş yüksekliği × Güneş'e paralel "
        "eğim zarfı, rover kataloğunun zaman sabitiyle iç sıcaklık dinamiği, her blok için max_dwell, planlayıcıda zarf dışına "
        "çıkan geçişleri reddeden kısıt, saplanma anından itibaren termal + haven geri sayımı (warning/critical/fail). Model "
        "kalibre edilmemiş; ısıtıcı yalnız etiketli varsayımla girer; JSC'nin sayıları alıntı.\""
    )
    lines.append(
        "- **Yanlış cümle:** \"VIPER'ın termal zarfını yeniden ürettik\" (rover gövdesi yok, Thermal Desktop yok, 60+ bileşen yok) "
        "ya da \"iç sıcaklık tahminimiz doğrulandı\" (Diviner karşılaştırması yok; C5)."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None, help="write the measurements here BEFORE rendering")
    parser.add_argument("--from-json", default=None, help="render from a previous dump instead of measuring")
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "thermal_dwell_report.md"))
    parser.add_argument("--skip-envelope", action="store_true")
    parser.add_argument("--heater", default="none,thermostat_assumed", help="comma-separated heater models to enforce with")
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        if not ((_PROCESSED / "horizon_map.npy").exists() and _KERNELS.exists() and (_PROCESSED / "metadata.json").exists()):
            print("processed grids, horizon_map.npy or the NAIF kernels are missing; nothing measured, nothing written")
            return 2
        heaters = tuple(h.strip() for h in args.heater.split(",") if h.strip())
        data = measure(args.skip_envelope, heaters)
        if args.json:
            Path(args.json).write_text(json.dumps(data, indent=1, default=float), encoding="utf-8")
            print(f"json -> {args.json}")
    text = render(data)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"report -> {args.out} ({_fmt(data.get('total_seconds', 0.0) / 60.0, 1)} min measured)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
