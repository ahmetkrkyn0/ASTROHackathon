#!/usr/bin/env python3
"""Measure the slip calibration (C3) on the checked-in Site11 grid.

Runs the standard routes -- VIPER's haven-to-haven pair on 2027-05-30 under
the leg rule, LPR-1's 2026-09-28 pair, LPR-1's lunar-night pair on
2026-09-13 -- twice: with the catalogue's slip curves applied (the build as
shipped) and with every profile's `slip_curve` removed in-process (the
slip-free model every earlier report measured). For each it reads back what
/api/plan-4d, /api/stress-test (SHERPA, 1 000 runs) and /api/plan say:
slices and horizon, arrival, battery, D3's margins, B5's completion, the 2-D
simulation's energy, and the `slip_model` block's own accounting of the
hours and Wh slip added. It also compares the old default-horizon bound
(BFS moves x slowest conceivable edge) with the fastest-route bound the
endpoint now uses.

Needs the processed grids, horizon_map.npy and the NAIF kernels; without
them it says so and exits 0. It never fabricates numbers. Writes
docs/research/slip_calibration_report.md by default.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.constants import ROVERS, get_rover  # noqa: E402
from app.cost_engine import edge_travel_time_s  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import (  # noqa: E402
    DEFAULT_HORIZON_WAIT_PAD_SLICES,
    MAX_PLAN_4D_SLICES,
    PlanWeights,
    _coarse_geometry,
    app,
)
from app.pathfinder_4d import gated_move_count  # noqa: E402
from app.rover_grids import grids_for_rover  # noqa: E402
from app.safe_haven import gated_shortest_drive  # noqa: E402
from app.slip_model import (  # noqa: E402
    MAX_SLIP_RATIO,
    SLIP_MODEL_ID,
    SLIP_MODEL_VALIDITY,
    curve_table,
)

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

COARSEN = 4
START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
CASES = [
    {
        "key": "viper",
        "label": "VIPER haven→haven, 30 May 2027",
        "rover_id": "nasa_viper",
        "start_utc": "2027-05-30T00:00:00",
        "start": START,
        "goal": GOAL,
        "extra": {"require_safe_haven": True},
        "stress": True,
        # Under the slip curve the standard leg is refused (battery reserve);
        # these say what it would take. Run for both variants.
        "relaxations": [
            ("haven kuralı yok", {"require_safe_haven": False}),
            ("24 h ufuk (güneşte bekleme serbest)", {"horizon_hours": 24.0}),
        ],
    },
    {
        # The nearest haven-to-haven leg that the slip curve leaves feasible
        # for VIPER (found by scanning the haven map from the standard start
        # by drive time): 8 coarse moves, ends at a haven.
        "key": "viper_short",
        "label": "VIPER kısa leg (358,494)→(346,462), 30 May 2027",
        "rover_id": "nasa_viper",
        "start_utc": "2027-05-30T00:00:00",
        "start": START,
        "goal": {"row": 346, "col": 462},
        "extra": {"require_safe_haven": True},
        "stress": True,
    },
    {
        "key": "lpr1",
        "label": "LPR-1, 28 Eyl 2026",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-28T00:00:00",
        "start": START,
        "goal": GOAL,
        "extra": {},
        "stress": True,
    },
    {
        "key": "night",
        "label": "LPR-1 Ay gecesi, 13 Eyl 2026",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-13T00:00:00",
        "start": {"row": 186, "col": 34},
        "goal": {"row": 494, "col": 450},
        "extra": {},
        "stress": False,
    },
]
VARIANTS = (("with_slip", "slip'li (C3)"), ("slip_free", "slip'siz (önce)"))
MARGIN_IDS = ("LP-R01", "LP-R02", "LP-R06", "LP-R07")


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _pct(rate: dict | None) -> str:
    if not rate:
        return "—"
    lo, hi = rate["ci95"]
    return f"{100 * rate['rate']:.1f} % ({100 * lo:.1f}–{100 * hi:.1f})".replace(".", ",")


def _fresh_grids() -> dict:
    """Load the grids and force the cost grid to be rebuilt under the CURRENT
    catalogue, so neither variant reuses the other's grid from disk."""
    grids = load_preprocessed_grids()
    grids.pop("cost", None)
    grids["metadata"]["cost_model"] = "rebuild-for-report"
    return grids


def _margins(block: dict | None) -> dict[str, float | None]:
    out: dict[str, float | None] = {rid: None for rid in MARGIN_IDS}
    if not block:
        return out
    for req in block.get("requirements", []):
        if req.get("id") in out:
            out[req["id"]] = req.get("rho")
    return out


def _horizon_bounds(grids: dict, case: dict, slice_hours: float) -> dict:
    """The old default-horizon bound (moves x slowest edge) and the new one
    (fastest route), both under the catalogue as currently patched."""
    rover = get_rover(case["rover_id"])
    grids_for_plan = grids_for_rover(grids, case["rover_id"], PlanWeights().model_dump())
    geometry = _coarse_geometry(grids_for_plan, COARSEN)
    cs = (case["start"]["row"] // COARSEN, case["start"]["col"] // COARSEN)
    cg = (case["goal"]["row"] // COARSEN, case["goal"]["col"] // COARSEN)
    moves = gated_move_count(geometry.traversable, cs, cg, geometry.elevation, geometry.resolution_m, rover)
    diag_m = geometry.resolution_m * math.sqrt(2.0)
    worst_s = edge_travel_time_s(float(rover["slope_max_deg"]), diag_m, rover)
    per_move = max(1, int(math.ceil(worst_s / 3600.0 / slice_hours)))
    old_bound = (moves or 0) * per_move + DEFAULT_HORIZON_WAIT_PAD_SLICES
    drive = gated_shortest_drive(
        geometry.traversable, geometry.elevation, geometry.slope, geometry.resolution_m, rover, cs, cg
    )
    hours, fast_moves = drive if drive is not None else (None, None)
    new_bound = (
        None if hours is None else int(math.ceil(hours / slice_hours)) + fast_moves + DEFAULT_HORIZON_WAIT_PAD_SLICES
    )
    return {
        "bfs_moves": moves,
        "worst_edge_slices": per_move,
        "old_bound": old_bound,
        "fastest_hours": hours,
        "fastest_moves": fast_moves,
        "new_bound": new_bound,
    }


def _plan_4d(client: TestClient, case: dict, extra: dict) -> dict:
    body = {
        "start": case["start"],
        "goal": case["goal"],
        "rover_id": case["rover_id"],
        "start_utc": case["start_utc"],
        **case["extra"],
        **extra,
    }
    started = time.perf_counter()
    response = client.post("/api/plan-4d", json=body)
    seconds = time.perf_counter() - started
    entry: dict = {"status": response.status_code, "plan_s": seconds, "request": extra}
    if response.status_code != 200:
        entry["detail"] = response.json().get("detail")
        return entry
    payload = response.json()
    metrics = payload["metrics"]
    entry.update(
        {
            "n_slices": payload["n_slices"],
            "slice_hours": payload["slice_hours"],
            "horizon_hours": payload["horizon_hours"],
            "move_steps": metrics["move_steps"],
            "wait_steps": metrics["wait_steps"],
            "arrival_hours": metrics["arrival_hours"],
            "min_battery_pct": min(payload["path_battery_pct"]),
            "max_dark_h": max(payload["path_dark_hours"]),
            "ends_at_safe_haven": metrics.get("ends_at_safe_haven"),
            "nodes_expanded": metrics["nodes_expanded"],
            "computation_time_ms": metrics["computation_time_ms"],
            "margins": _margins(payload.get("safety_margins")),
            "slip": payload["slip_model"],
            "path_states": payload["path_states"],
        }
    )
    return entry


def _run_case(client: TestClient, grids: dict, case: dict, n_runs: int, seed: int) -> dict:
    from app.cost_cube import auto_slice_hours

    rover = get_rover(case["rover_id"])
    grids_for_plan = grids_for_rover(grids, case["rover_id"], PlanWeights().model_dump())
    # The endpoint's own auto slice, so the horizon bounds can be compared
    # even when the plan itself is refused.
    slice_hours = auto_slice_hours(
        grids_for_plan["slope"], grids_for_plan["traversable"],
        resolution_m=float(grids_for_plan["metadata"]["resolution_m"]) * COARSEN, rover=rover,
    )
    entry = _plan_4d(client, case, {})
    entry["horizon"] = _horizon_bounds(grids, case, entry.get("slice_hours") or slice_hours)
    entry["relaxations"] = []
    for label, extra in case.get("relaxations", []):
        print(f"    relaxation: {label} ...", flush=True)
        relaxed = _plan_4d(client, case, extra)
        relaxed["label"] = label
        relaxed.pop("path_states", None)
        entry["relaxations"].append(relaxed)
    payload_states = entry.pop("path_states", None)
    if case["stress"] and entry["status"] == 200:
        stress_body = {
            "path_states": payload_states,
            "rover_id": case["rover_id"],
            "start_utc": case["start_utc"],
            "slice_hours": entry["slice_hours"],
            "coarsen": COARSEN,
            "n_runs": n_runs,
            "seed": seed,
        }
        started = time.perf_counter()
        stress = client.post("/api/stress-test", json=stress_body)
        entry["stress_s"] = time.perf_counter() - started
        if stress.status_code == 200:
            out = stress.json()
            entry["stress"] = {
                "completion": out["rates"]["completion"],
                "within_reserve": out["rates"]["reached_within_reserve"],
                "full_success": out["rates"]["full_success"],
                "nominal_duration_h": out["nominal"]["duration_h"],
                "nominal_min_battery_pct": out["nominal"]["min_battery_pct"],
                "nominal_reached": out["nominal"]["reached"],
                "verdict": out["verdict"]["text"],
            }
        else:
            entry["stress"] = {"error": stress.json().get("detail")}
    started = time.perf_counter()
    plan2d = client.post("/api/plan", json={"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"]})
    entry["plan2d_s"] = time.perf_counter() - started
    if plan2d.status_code == 200:
        p = plan2d.json()
        summary = p["summary"]
        entry["plan2d"] = {
            "distance_km": summary["total_distance_km"],
            "hours": summary["total_elapsed_hours"],
            "energy_wh": summary["total_energy_consumed_wh"],
            "solar_wh": summary["total_solar_energy_wh"],
            "min_battery_pct": summary["min_battery_pct"],
            "max_slope_deg": max(summary["max_slope_deg"], summary["max_segment_slope_deg"]),
            "margins": _margins(p.get("safety_margins")),
            "slip": p["slip_model"],
        }
    else:
        entry["plan2d"] = {"error": plan2d.json().get("detail")}
    return entry


def _run_variant(client: TestClient, slip_enabled: bool, n_runs: int, seed: int) -> dict:
    saved = {rid: cfg["slip_curve"] for rid, cfg in ROVERS.items()}
    try:
        if not slip_enabled:
            for cfg in ROVERS.values():
                cfg["slip_curve"] = None
        grids = _fresh_grids()
        app.state.grids = grids
        results = {}
        for case in CASES:
            print(f"  {case['label']} ...", flush=True)
            results[case["key"]] = _run_case(client, grids, case, n_runs, seed)
        return results
    finally:
        for rid, curve in saved.items():
            ROVERS[rid]["slip_curve"] = curve
        app.state.grids = None


def _ratio(after, before) -> str:
    if after is None or before is None or not before:
        return "—"
    return f"×{after / before:.2f}".replace(".", ",")


def _write_markdown(path: Path, report: dict, args) -> None:
    lines: list[str] = []
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append("# Slip kalibrasyonu (C3) — Site11 önce/sonra raporu\n")
    lines.append(
        f"Üretim: `scripts/slip_calibration_report.py`, {stamp}. Model `{SLIP_MODEL_ID}`, "
        f"etiket `{SLIP_MODEL_VALIDITY}`, kap {_fmt(MAX_SLIP_RATIO, 1)}. Monte Carlo {args.n_runs} koşum, tohum {args.seed}.\n"
    )
    lines.append(
        "**İddia sınırı.** Eğri **ölçülmüş değil, literatüre bağlı bir MODEL**: VIPER'ın PSJ 2025'te "
        "yayımlanan mobilite tasarım gereksinimi (\"a maximum of 40% slip up a maximum slope of 15°\"; "
        "GRC-1 simülantı, %15–20 bağıl yoğunluk — bir üst sınır, tipik değer değil) ile Yutu-2'nin "
        "Chang'e-4'te ölçülmüş slip oranı (0 … −0,075, ≤ 8,86° eğimlerde, çoğunlukla skid; Nature "
        "Communications 2024) çapalardır; çapalar arası ve ötesi üstel biçim ile çapaların diğer "
        "rover'lara aktarımı **varsayımdır** ve katalogda `assumption:` ile yazılıdır. Kutup regolitinde "
        "ölçülmüş slip yoktur; Diviner termal atalet modülasyonu (Cunningham RSS 2017) yalnızca kancadır.\n"
    )

    # 1. anchors
    lines.append("## 1. Çapalar ve kaynaklar\n")
    lines.append("| Rover | Eğim | Slip μ | σ | Tür | Kaynak |")
    lines.append("|---|---|---|---|---|---|")
    for rid, cfg in ROVERS.items():
        for anchor in cfg["slip_curve"]:
            lines.append(
                f"| `{rid}` | {_fmt(anchor.slope_deg, 2)}° | {_fmt(anchor.slip, 4)} | {_fmt(anchor.sigma, 4)} | "
                f"`{anchor.kind}` | {anchor.source} |"
            )
    lines.append("")

    # 2. curve table
    lines.append("## 2. Eğri (0/5/10/15/20/25°): slip μ (σ) · süre/enerji çarpanı 1/(1−μ)\n")
    header = "| Eğim | " + " | ".join(f"`{rid}`" for rid in ROVERS) + " |"
    lines.append(header)
    lines.append("|---|" + "---|" * len(ROVERS))
    tables = {rid: curve_table(get_rover(rid)) for rid in ROVERS}
    for i, slope in enumerate((0, 5, 10, 15, 20, 25)):
        cells = []
        for rid in ROVERS:
            row = tables[rid][i]
            limit = "" if row["within_slope_limit"] else " (eğim sınırı dışı)"
            cells.append(f"{_fmt(row['slip'], 3)} ({_fmt(row['sigma'], 3)}) · ×{_fmt(row['time_energy_factor'], 2)}{limit}")
        lines.append(f"| {slope}° | " + " | ".join(cells) + " |")
    lines.append("")

    # 3. 4-D before/after
    lines.append("## 3. Standart rotalar, `/api/plan-4d`: slip'siz → slip'li\n")
    lines.append(
        "| Rota | Varyant | Dilim × saat | Ufuk (h) | Hamle / bekleme | Varış (h) | En düşük SOC (%) | Maks gölge (h) | "
        "LP-R01 ρ (h) | LP-R02 ρ (pct) | LP-R06 ρ (°) | LP-R07 ρ (°) | Rota ort. / maks slip | Slip'in eklediği saat / Wh | Mesafe çarpanı | Düğüm | Planlama (s) |"
    )
    lines.append("|---|" + "---|" * 16)
    def _plan_row(label: str, vlabel: str, e: dict) -> str:
        if e["status"] != 200:
            return f"| {label} | {vlabel} | **{e['status']}** ({_fmt(e['plan_s'], 1)} s): {e.get('detail')} |" + " — |" * 14
        m = e["margins"]
        r = e["slip"]["route"]
        haven = "" if e.get("ends_at_safe_haven") is None else (" (havende biter)" if e["ends_at_safe_haven"] else " (havende bitmez)")
        return (
            f"| {label} | {vlabel} | {e['n_slices']} × {_fmt(e['slice_hours'], 4)} | {_fmt(e['horizon_hours'])} | "
            f"{e['move_steps']} / {e['wait_steps']} | {_fmt(e['arrival_hours'])}{haven} | {_fmt(e['min_battery_pct'], 1)} | "
            f"{_fmt(e['max_dark_h'])} | {_fmt(m['LP-R01'])} | {_fmt(m['LP-R02'])} | {_fmt(m['LP-R06'])} | {_fmt(m['LP-R07'])} | "
            f"{_fmt(r['mean_slip'], 3)} / {_fmt(r['max_slip'], 3)} | {_fmt(r['extra_hours'])} / {_fmt(r['extra_drawn_wh'], 0)} | "
            f"{_fmt(r['distance_factor'], 3)} | {_int(e['nodes_expanded'])} | {_fmt(e['plan_s'], 1)} |"
        )

    for case in CASES:
        for variant, vlabel in reversed(VARIANTS):
            e = report[variant][case["key"]]
            lines.append(_plan_row(case["label"], vlabel, e))
            for relaxed in e.get("relaxations", []):
                lines.append(_plan_row(case["label"], f"{vlabel}, {relaxed['label']}", relaxed))
    lines.append("")

    # 4. stress
    lines.append(f"## 4. B5 Monte Carlo (SHERPA, {args.n_runs} koşum, tohum {args.seed})\n")
    lines.append("| Rota | Varyant | Tamamlanma | Rezerv içinde | Tam başarı | Nominal süre (h) | Nominal en düşük SOC (%) | Karar |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case in CASES:
        if not case["stress"]:
            continue
        for variant, vlabel in reversed(VARIANTS):
            e = report[variant][case["key"]]
            s = e.get("stress")
            if not s or "error" in (s or {}):
                lines.append(f"| {case['label']} | {vlabel} | — | — | — | — | — | {(s or {}).get('error', e.get('detail'))} |")
                continue
            lines.append(
                f"| {case['label']} | {vlabel} | {_pct(s['completion'])} | {_pct(s['within_reserve'])} | {_pct(s['full_success'])} | "
                f"{_fmt(s['nominal_duration_h'])} | {_fmt(s['nominal_min_battery_pct'], 1)} | {s['verdict']} |"
            )
    lines.append("")

    # 5. 2-D
    lines.append("## 5. Aynı çiftler, `/api/plan` (2-B simülasyon)\n")
    lines.append("| Rota | Varyant | Mesafe (km) | Süre (h) | Tüketim (Wh) | Güneş (Wh) | En düşük SOC (%) | Maks sürüş eğimi (°) | LP-R02 ρ | Rota ort. slip | Slip'in eklediği saat / Wh |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for case in CASES:
        for variant, vlabel in reversed(VARIANTS):
            e = report[variant][case["key"]]
            p = e.get("plan2d") or {}
            if "error" in p or not p:
                lines.append(f"| {case['label']} | {vlabel} | {p.get('error', e.get('detail'))} |" + " — |" * 9)
                continue
            r = p["slip"]["route"]
            lines.append(
                f"| {case['label']} | {vlabel} | {_fmt(p['distance_km'], 3)} | {_fmt(p['hours'])} | {_fmt(p['energy_wh'], 0)} | "
                f"{_fmt(p['solar_wh'], 0)} | {_fmt(p['min_battery_pct'], 1)} | {_fmt(p['max_slope_deg'], 1)} | "
                f"{_fmt(p['margins']['LP-R02'])} | {_fmt(r['mean_slip'], 3)} | {_fmt(r['extra_hours'])} / {_fmt(r['extra_drawn_wh'], 0)} |"
            )
    lines.append("")

    # 6. horizon
    lines.append(f"## 6. Varsayılan ufuk: eski sınır (BFS hamle × en yavaş kenar) ↔ yeni sınır (en hızlı rota); tavan {MAX_PLAN_4D_SLICES}\n")
    lines.append("| Rota | Varyant | BFS hamle | En yavaş kenar (dilim) | Eski sınır (dilim) | En hızlı rota (h / hamle) | Yeni sınır (dilim) | Uçtaki `n_slices` |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for case in CASES:
        for variant, vlabel in reversed(VARIANTS):
            e = report[variant][case["key"]]
            h = e.get("horizon")
            if not h:
                continue
            over = " **(tavan üstü)**" if h["old_bound"] > MAX_PLAN_4D_SLICES else ""
            served = _int(e.get("n_slices")) if e["status"] == 200 else f"— ({e['status']})"
            lines.append(
                f"| {case['label']} | {vlabel} | {h['bfs_moves']} | {h['worst_edge_slices']} | {h['old_bound']}{over} | "
                f"{_fmt(h['fastest_hours'])} / {h['fastest_moves']} | {h['new_bound']} | {served} |"
            )
    lines.append("")

    # 7. reading
    lines.append("## 7. Okuma\n")
    for case in CASES:
        a = report["with_slip"][case["key"]]
        b = report["slip_free"][case["key"]]
        if a["status"] != 200 or b["status"] != 200:
            note = [f"slip'siz {b['status']}, slip'li **{a['status']}**"]
            for relaxed in a.get("relaxations", []):
                if relaxed["status"] == 200:
                    r = relaxed["slip"]["route"]
                    note.append(
                        f"{relaxed['label']}: 200 — {relaxed['move_steps']} hamle / {relaxed['wait_steps']} bekleme, "
                        f"varış {_fmt(relaxed['arrival_hours'])} h, en düşük SOC %{_fmt(relaxed['min_battery_pct'], 1)}, "
                        f"ort. slip {_fmt(r['mean_slip'], 3)}, slip'in eklediği {_fmt(r['extra_hours'])} h / {_fmt(r['extra_drawn_wh'], 0)} Wh"
                    )
                else:
                    note.append(f"{relaxed['label']}: {relaxed['status']}")
            pa, pb = a.get("plan2d") or {}, b.get("plan2d") or {}
            if "hours" in pa and "hours" in pb:
                note.append(
                    f"2-B: süre {_fmt(pb['hours'])} → {_fmt(pa['hours'])} h, tüketim {_fmt(pb['energy_wh'], 0)} → {_fmt(pa['energy_wh'], 0)} Wh "
                    f"({_ratio(pa['energy_wh'], pb['energy_wh'])}), en düşük SOC %{_fmt(pb['min_battery_pct'], 1)} → %{_fmt(pa['min_battery_pct'], 1)}"
                )
            lines.append(f"- **{case['label']}**: " + "; ".join(note) + ".")
            continue
        r = a["slip"]["route"]
        parts = [
            f"varış {_fmt(b['arrival_hours'])} → {_fmt(a['arrival_hours'])} h ({_ratio(a['arrival_hours'], b['arrival_hours'])})",
            f"en düşük SOC %{_fmt(b['min_battery_pct'], 1)} → %{_fmt(a['min_battery_pct'], 1)}",
            f"hamle {b['move_steps']} → {a['move_steps']}, bekleme {b['wait_steps']} → {a['wait_steps']}",
            f"rota ortalama slip {_fmt(r['mean_slip'], 3)} (maks {_fmt(r['max_slip'], 3)} @ {_fmt(r['max_slip_slope_deg'], 1)}°), slip'in eklediği {_fmt(r['extra_hours'])} h / {_fmt(r['extra_drawn_wh'], 0)} Wh",
            f"LP-R02 ρ {_fmt(b['margins']['LP-R02'])} → {_fmt(a['margins']['LP-R02'])} pct",
            f"dilim {b['n_slices']} × {_fmt(b['slice_hours'], 4)} h → {a['n_slices']} × {_fmt(a['slice_hours'], 4)} h",
        ]
        if a.get("stress") and b.get("stress") and "error" not in a["stress"] and "error" not in b["stress"]:
            parts.append(
                f"B5 tamamlanma {_pct(b['stress']['completion'])} → {_pct(a['stress']['completion'])}, "
                f"tam başarı {_pct(b['stress']['full_success'])} → {_pct(a['stress']['full_success'])}, "
                f"nominal en düşük SOC %{_fmt(b['stress']['nominal_min_battery_pct'], 1)} → %{_fmt(a['stress']['nominal_min_battery_pct'], 1)}"
            )
        pa, pb = a.get("plan2d") or {}, b.get("plan2d") or {}
        if "hours" in pa and "hours" in pb:
            parts.append(
                f"2-B: süre {_fmt(pb['hours'])} → {_fmt(pa['hours'])} h, tüketim {_fmt(pb['energy_wh'], 0)} → {_fmt(pa['energy_wh'], 0)} Wh "
                f"({_ratio(pa['energy_wh'], pb['energy_wh'])}), en düşük SOC %{_fmt(pb['min_battery_pct'], 1)} → %{_fmt(pa['min_battery_pct'], 1)}"
            )
        lines.append(f"- **{case['label']}**: " + "; ".join(parts) + ".")
    lines.append("")
    lines.append(
        "Sunum cümlesi: **Slip eğrimiz VIPER'ın 15°/%40 tasarım kısıtına ve Yutu-2'nin ölçülmüş regolit "
        "parametrelerine bağlı.** Tasarım: `docs/superpowers/specs/2026-09-04-c3-slip-calibration-design.md`."
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "slip_calibration_report.md"))
    parser.add_argument("--json", default=None, help="also dump the raw measurements as JSON (written before the markdown)")
    parser.add_argument("--from-json", default=None, help="render the markdown from a previous --json dump instead of measuring")
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    # The labels carry Turkish and arrows; a cp1252 console must not abort the run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        _write_markdown(Path(args.out), report, args)
        print(f"wrote {args.out} from {args.from_json}")
        return 0

    missing = [str(p) for p in (_PROCESSED / "metadata.json", _PROCESSED / "horizon_map.npy", _KERNELS) if not p.exists()]
    if missing:
        print("cannot measure: missing " + ", ".join(missing))
        print("run the P1 pipeline, scripts/build_horizon_cache.py and scripts/fetch_kernels.py first")
        return 0

    client = TestClient(app)
    report: dict = {}
    for variant, label in VARIANTS:
        print(f"variant {label}", flush=True)
        report[variant] = _run_variant(client, variant == "with_slip", args.n_runs, args.seed)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    _write_markdown(Path(args.out), report, args)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
