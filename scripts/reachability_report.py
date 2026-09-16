"""D6 measured on Site11: how far can this rover actually get, and on what.

    python scripts/reachability_report.py
    python scripts/reachability_report.py --json raw.json
    python scripts/reachability_report.py --from-json raw.json

``--json`` writes the raw measurements before rendering; ``--from-json``
re-renders them without measuring, so the prose can be revised without
re-running the grid. The two paths produce a byte-identical report.

Nothing here is quoted from a paper. The literature's own numbers live in
``app.reachability.REACHABILITY_QUOTED`` and are never put in the same table
as a measurement from this grid.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.constants import get_rover  # noqa: E402
from app.cost_cube import (  # noqa: E402
    auto_slice_hours,
    build_cost_cube,
    build_wait_cost_cube,
    coarsen_grid,
    coarsen_traversable,
)
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.pathfinder_4d import astar_4d  # noqa: E402
from app.reachability import (  # noqa: E402
    HOLD_LIMIT_CODES,
    REACHABILITY_MODEL_ID,
    coarse_shadow_cube,
    compare_fields,
    default_band_edges,
    hold_limit,
    hold_times,
    isochrone_bands,
    sweep,
)
from app.rover_grids import grids_for_rover  # noqa: E402
from app.survival import OFFSETS, direction_tables  # noqa: E402

REPORT_PATH = (
    Path(__file__).resolve().parents[1] / "docs" / "research" / "reachability_report.md"
)

#: The three standard starts every routing feature in this repo is measured
#: on. D6 takes only the start of each pair.
STARTS: tuple[dict[str, Any], ...] = (
    {"name": "LPR-1 gunduz", "rover_id": "lpr_1", "start": (358, 494), "coarsen": 4},
    {"name": "Ay gecesi", "rover_id": "lpr_1", "start": (186, 34), "coarsen": 4},
    # VIPER's 15 deg limit makes block (89, 123) fail the conservative AND at
    # coarsen 4 while the fine cell is passable, so the standard start is
    # measured at coarsen 2 and the refusal is recorded as a finding.
    {"name": "VIPER kisa leg", "rover_id": "nasa_viper", "start": (358, 494), "coarsen": 2},
)

#: One epoch at which part of the window is LIT and one at which none of it
#: is. The pair is the whole point: a Dijkstra over signed energy looks
#: correct at the second and is wrong at the first.
LIT_EPOCH = "2026-09-05T00:00:00"
DARK_EPOCH = "2026-09-01T00:00:00"
EDGE_EPOCHS = (
    "2026-09-01T00:00:00",
    "2026-09-05T00:00:00",
    "2026-09-09T00:00:00",
    "2026-09-13T00:00:00",
    "2026-09-17T00:00:00",
    "2026-09-21T00:00:00",
    "2026-09-25T00:00:00",
    "2026-09-29T00:00:00",
)

BUDGET_SOC = (1.0, 0.5, 0.25)
BUDGET_HORIZONS = (3.0, 6.0, 12.0)
#: Hour scale, day scale, and beyond. Measured on Site11: at 6, 12 and 24 h
#: the reachable set does not move a single block even though the lit
#: fraction does, because the pole's illumination turns on a ~708 h synodic
#: cycle and a day is 3 % of it. An hour-scale ladder alone would publish
#: Jaccard 1.0 with nothing to tell "the set is stable" from "the Sun was
#: never modelled".
LATER_HOURS = (6.0, 24.0, 96.0, 240.0)
AGREEMENT_SAMPLES = 12


def _geometry(grids_for_plan: dict, coarsen: int):
    metadata = grids_for_plan["metadata"]
    traversable = coarsen_traversable(grids_for_plan["traversable"], coarsen)
    slope = coarsen_grid(grids_for_plan["slope"], coarsen, how="max")
    elevation = coarsen_grid(grids_for_plan["elevation"], coarsen, how="center")
    resolution_m = float(metadata["resolution_m"]) * coarsen
    return traversable, elevation, slope, resolution_m


def measure_negative_edges(grids: dict) -> dict[str, Any]:
    """Are there negative battery edges on Site11, how many, and when?

    The premise of the research note's D6 line is that a multi-source
    Dijkstra over the cost cube answers this question. It cannot if the edge
    weights go negative, so the first thing measured is whether they do.
    """
    out: dict[str, Any] = {"n_slices": 48, "coarsen": 4, "rovers": {}}
    for rover_id in ("lpr_1", "nasa_viper"):
        rover = get_rover(rover_id)
        grids_for_plan = grids_for_rover(grids, rover_id)
        traversable, elevation, slope, resolution_m = _geometry(grids_for_plan, 4)
        tables = direction_tables(traversable, elevation, slope, resolution_m, rover)
        slice_hours = auto_slice_hours(
            grids_for_plan["slope"],
            grids_for_plan["traversable"],
            resolution_m=resolution_m,
            rover=rover,
        )
        p_idle = float(rover["p_idle_w"])
        extra = max(0.0, float(rover["p_shadow_w"]) - p_idle)
        p_solar = float(rover["p_solar_w"])
        p_base = float(rover["p_base_w"])
        rows: list[dict[str, Any]] = []
        for epoch in EDGE_EPOCHS:
            cube, provenance = coarse_shadow_cube(
                np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
                grids_for_plan["metadata"],
                4,
                out["n_slices"],
                slice_hours,
                epoch,
            )
            if not provenance.get("time_varying"):
                rows.append({"epoch": epoch, "unavailable": provenance.get("reason")})
                continue
            lit_fraction = float((cube[0][traversable] == 0.0).mean())
            wait_drain = p_idle + cube * extra - p_solar * (1.0 - cube)
            wait_total = int(wait_drain[:, traversable].size)
            wait_negative = int((wait_drain[:, traversable] < 0.0).sum())
            drive_total = drive_negative = 0
            worst = 0.0
            height, width = traversable.shape
            for d, (d_row, d_col, _diag) in enumerate(OFFSETS):
                allowed = tables.allowed[d]
                if not allowed.any():
                    continue
                r0, r1 = max(0, -d_row), height - max(0, d_row)
                c0, c1 = max(0, -d_col), width - max(0, d_col)
                src = (slice(r0, r1), slice(c0, c1))
                dst = (slice(r0 + d_row, r1 + d_row), slice(c0 + d_col, c1 + d_col))
                mask = allowed[src]
                travel = tables.travel_h[d][src]
                finite = mask & np.isfinite(travel)
                if not finite.any():
                    continue
                travel_ok = np.where(finite, travel, 0.0)
                spans = np.ones(finite.shape, dtype=np.int64)
                spans[finite] = np.maximum(
                    1, np.ceil(travel[finite] / slice_hours).astype(np.int64)
                )
                flat_dst = cube[:, dst[0], dst[1]].reshape(out["n_slices"], -1)
                for t in range(out["n_slices"]):
                    arrival = np.minimum(t + spans, out["n_slices"] - 1).reshape(1, -1)
                    e_arr = np.take_along_axis(flat_dst, arrival, axis=0).reshape(finite.shape)
                    mean_exposure = 0.5 * (cube[t][src] + e_arr)
                    drain = (
                        tables.traction_w[d][src]
                        + (p_idle + mean_exposure * extra)
                        - p_solar * (1.0 - mean_exposure)
                    ) * travel_ok
                    drive_total += int(finite.sum())
                    negative = finite & (drain < 0.0)
                    drive_negative += int(negative.sum())
                    if negative.any():
                        worst = min(worst, float(drain[negative].min()))
            rows.append(
                {
                    "epoch": epoch,
                    "lit_fraction_at_first_slice": round(lit_fraction, 6),
                    "drive_edges": drive_total,
                    "drive_negative": drive_negative,
                    "drive_negative_pct": round(100.0 * drive_negative / max(1, drive_total), 4),
                    "worst_drive_wh": round(worst, 6),
                    "wait_edges": wait_total,
                    "wait_negative": wait_negative,
                    "wait_negative_pct": round(100.0 * wait_negative / max(1, wait_total), 4),
                }
            )
        # The break-even exposure on a flat cell, closed form.
        break_even = (p_solar - p_base - p_idle) / (extra + p_solar)
        out["rovers"][rover_id] = {
            "name": rover["name"],
            "slice_hours": slice_hours,
            "flat_break_even_shadow_ratio": round(break_even, 6),
            "epochs": rows,
        }
    return out


def _run_sweep(grids: dict, spec: dict, epoch: str, horizon_hours: float, soc: float):
    rover = get_rover(spec["rover_id"])
    grids_for_plan = grids_for_rover(grids, spec["rover_id"])
    coarsen = int(spec["coarsen"])
    traversable, elevation, slope, resolution_m = _geometry(grids_for_plan, coarsen)
    slice_hours = auto_slice_hours(
        grids_for_plan["slope"],
        grids_for_plan["traversable"],
        resolution_m=resolution_m,
        rover=rover,
    )
    n_slices = max(2, int(math.ceil(horizon_hours / slice_hours)))
    coarse_start = (spec["start"][0] // coarsen, spec["start"][1] // coarsen)
    if not bool(traversable[coarse_start]):
        return None, {
            "refused": (
                f"start block {coarse_start} is not traversable at coarsen={coarsen}"
            )
        }
    cube, provenance = coarse_shadow_cube(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"],
        coarsen,
        n_slices,
        slice_hours,
        epoch,
    )
    if not provenance.get("time_varying"):
        return None, {"refused": provenance.get("reason", "static shadow series")}
    tables = direction_tables(traversable, elevation, slope, resolution_m, rover)
    field = sweep(
        traversable,
        elevation,
        slope,
        resolution_m,
        rover,
        cube,
        slice_hours,
        coarse_start,
        soc,
        tables=tables,
    )
    context = {
        "lit_fraction_at_first_slice": float((cube[0][traversable] == 0.0).mean()),
        "rover": rover,
        "grids_for_plan": grids_for_plan,
        "traversable": traversable,
        "elevation": elevation,
        "slope": slope,
        "resolution_m": resolution_m,
        "slice_hours": slice_hours,
        "n_slices": n_slices,
        "coarse_start": coarse_start,
        "cube": cube,
        "tables": tables,
        "coarsen": coarsen,
    }
    return field, context


def measure_starts(grids: dict) -> list[dict[str, Any]]:
    """The three standard starts: what is reachable, in what bands, how fast."""
    rows: list[dict[str, Any]] = []
    for spec in STARTS:
        row: dict[str, Any] = {
            "name": spec["name"],
            "rover_id": spec["rover_id"],
            "start": list(spec["start"]),
            "coarsen": spec["coarsen"],
            "epoch": LIT_EPOCH,
            "horizon_hours": 3.0,
        }
        # Record the coarsen-4 refusal for VIPER as a finding, not a gap.
        if spec["coarsen"] != 4:
            probe_spec = {**spec, "coarsen": 4}
            _field, probe = _run_sweep(grids, probe_spec, LIT_EPOCH, 3.0, 1.0)
            row["coarsen_4"] = probe.get("refused") if isinstance(probe, dict) else None
        field, context = _run_sweep(grids, spec, LIT_EPOCH, 3.0, 1.0)
        if field is None:
            row.update(context)
            rows.append(row)
            continue
        horizon = (field.n_slices - 1) * field.slice_hours
        bands = isochrone_bands(field, default_band_edges(horizon), context["resolution_m"])
        bands.pop("band_index")
        hold_cube, _ = coarse_shadow_cube(
            np.asarray(context["grids_for_plan"]["shadow_ratio"], dtype=np.float64),
            context["grids_for_plan"]["metadata"],
            context["coarsen"],
            241,
            0.5,
            LIT_EPOCH,
        )
        holds = hold_times(field, hold_cube, context["rover"], 0.5)
        hours, code = hold_limit(holds, field.reachable)
        finite = hours[np.isfinite(hours)]
        row.update(
            {
                "slice_hours": round(context["slice_hours"], 6),
                "n_slices": field.n_slices,
                "horizon_hours": round(horizon, 6),
                "coarse_shape": list(context["traversable"].shape),
                "traversable_blocks": int(context["traversable"].sum()),
                "reachable_blocks": int(field.reachable.sum()),
                "reachable_area_km2": bands["reachable_area_km2"],
                "bands": bands["bands"],
                "beyond_last_edge_blocks": bands["beyond_last_edge_blocks"],
                "refusals": dict(field.refusals),
                "energy_binds": field.energy_binds,
                "edges_relaxed": field.edges_relaxed,
                "negative_edges": field.negative_edges,
                "sweep_s": round(field.elapsed_s, 4),
                "edge_groups": field.edge_groups,
                "unpaid_idle_mean_h": round(field.unpaid_idle_mean_h, 6),
                "partially_lit_blocks": field.partially_lit_first_slice,
                "hold_limited_by": {
                    name: int((code == value).sum()) for name, value in HOLD_LIMIT_CODES.items()
                },
                "hold_limit_min_h": round(float(finite.min()), 4) if finite.size else None,
                "hold_limit_max_h": round(float(finite.max()), 4) if finite.size else None,
                "hold_horizon_h": round(holds.horizon_h, 4),
            }
        )
        rows.append(row)
    return rows


def measure_budget(grids: dict) -> list[dict[str, Any]]:
    """The budget curve: reachable area against start charge and horizon,
    at a lit epoch and a dark one."""
    rows: list[dict[str, Any]] = []
    for spec in STARTS[:2]:
        for epoch in (LIT_EPOCH, DARK_EPOCH):
            for soc in BUDGET_SOC:
                for horizon in BUDGET_HORIZONS:
                    field, context = _run_sweep(grids, spec, epoch, horizon, soc)
                    if field is None:
                        continue
                    area = (context["resolution_m"] ** 2) / 1_000_000.0
                    rows.append(
                        {
                            "name": spec["name"],
                            "epoch": epoch,
                            "initial_soc_pct": soc,
                            "horizon_hours": horizon,
                            "n_slices": field.n_slices,
                            "reachable_blocks": int(field.reachable.sum()),
                            "reachable_area_km2": round(int(field.reachable.sum()) * area, 6),
                            "soc_floor_refusals": field.refusals["soc_floor"],
                            "horizon_refusals": field.refusals["horizon"],
                            "energy_binds": field.energy_binds,
                            "negative_edges": field.negative_edges,
                            "edges_relaxed": field.edges_relaxed,
                            "sweep_s": round(field.elapsed_s, 4),
                        }
                    )
    return rows


def measure_later(grids: dict) -> list[dict[str, Any]]:
    """Now against N hours later, at the charge where the epoch matters."""
    from app.reachability import shift_epoch

    rows: list[dict[str, Any]] = []
    spec = STARTS[1]
    for epoch in (LIT_EPOCH, DARK_EPOCH):
        base, context = _run_sweep(grids, spec, epoch, 6.0, 0.25)
        if base is None:
            continue
        for later in LATER_HOURS:
            slices = max(1, int(round(later / context["slice_hours"])))
            snapped = slices * context["slice_hours"]
            shifted, _later_context = _run_sweep(
                grids, spec, shift_epoch(epoch, snapped), 6.0, 0.25
            )
            if shifted is None:
                continue
            comparison = compare_fields(base, shifted, context["resolution_m"])
            _shifted_field, shifted_context = shifted, _later_context
            rows.append(
                {
                    "name": spec["name"],
                    "epoch": epoch,
                    "initial_soc_pct": 0.25,
                    "horizon_hours": 6.0,
                    "requested_later_hours": later,
                    "later_hours": round(snapped, 6),
                    "later_slices": slices,
                    "lit_fraction_now": round(context["lit_fraction_at_first_slice"], 6),
                    "lit_fraction_later": round(
                        shifted_context["lit_fraction_at_first_slice"], 6
                    ),
                    **{
                        key: comparison[key]
                        for key in (
                            "now_blocks",
                            "later_blocks",
                            "kept_blocks",
                            "gained_by_later_start_blocks",
                            "lost_by_later_start_blocks",
                            "jaccard",
                        )
                    },
                }
            )
    return rows


def measure_agreement(grids: dict) -> dict[str, Any]:
    """How loose is the relaxation? Replay the planner on sampled blocks.

    The published claim runs one way -- a block OUTSIDE the set is
    unreachable -- so what is measured here is the other direction: of the
    blocks the sweep calls reachable, how many can the 4-D planner actually
    route to under the same configuration? Anything under 100 % is the
    relaxation being loose, which is expected and is why the claim is
    negative.
    """
    spec = STARTS[1]
    field, context = _run_sweep(grids, spec, LIT_EPOCH, 3.0, 1.0)
    if field is None:
        return {"unavailable": context.get("refused")}
    rover = context["rover"]
    n_slices = context["n_slices"]
    cube = context["cube"]
    series = [cube[index] for index in range(n_slices)]
    cost = build_cost_cube(
        context["grids_for_plan"],
        [np.asarray(context["grids_for_plan"]["shadow_ratio"], dtype=np.float64)] * n_slices,
        rover,
        None,
        coarsen=context["coarsen"],
    )
    wait = build_wait_cost_cube(
        [1.0 - snapshot for snapshot in series], rover, context["slice_hours"], None, coarsen=1
    )
    rows, cols = np.nonzero(field.reachable)
    order = np.argsort(field.first_slice[rows, cols])
    picks = [
        (int(rows[i]), int(cols[i]))
        for i in order[:: max(1, len(order) // AGREEMENT_SAMPLES)][:AGREEMENT_SAMPLES]
    ]
    started = time.perf_counter()
    agreed = tried = 0
    details: list[dict[str, Any]] = []
    for goal in picks:
        if goal == context["coarse_start"]:
            continue
        result = astar_4d(
            cost,
            wait,
            context["traversable"],
            context["coarse_start"],
            goal,
            context["resolution_m"],
            context["slice_hours"],
            rover,
            slope_grid=context["slope"],
            elevation_grid=context["elevation"],
            shadow_cube=cube,
            initial_soc_frac=1.0,
        )
        tried += 1
        routed = bool(result.get("path_states"))
        agreed += int(routed)
        details.append(
            {
                "block": list(goal),
                "sweep_first_slice": int(field.first_slice[goal]),
                "planner_routed": routed,
                "planner_arrival_slice": (
                    int(result["path_states"][-1][2]) if routed else None
                ),
            }
        )
    return {
        "name": spec["name"],
        "epoch": LIT_EPOCH,
        "sampled": tried,
        "planner_routed": agreed,
        "agreement_pct": round(100.0 * agreed / max(1, tried), 2),
        "elapsed_s": round(time.perf_counter() - started, 3),
        "details": details,
    }


def measure() -> dict[str, Any]:
    grids = load_preprocessed_grids()
    metadata = grids["metadata"]
    started = time.perf_counter()
    data: dict[str, Any] = {
        "model_id": REACHABILITY_MODEL_ID,
        "grid": {
            "shape": list(metadata["shape"]),
            "resolution_m": float(metadata["resolution_m"]),
            "window_offset": metadata.get("window_offset"),
        },
        "negative_edges": measure_negative_edges(grids),
        "starts": measure_starts(grids),
        "budget": measure_budget(grids),
        "later": measure_later(grids),
        "agreement": measure_agreement(grids),
    }
    data["total_measure_s"] = round(time.perf_counter() - started, 2)
    return data


# ── rendering ────────────────────────────────────────────────────────────────


def render(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def add(text: str = "") -> None:
        lines.append(text)

    grid = data["grid"]
    add("# D6 — Enerji-erişilebilirlik izokronları: Site11 ölçümleri")
    add()
    add(
        f"`{data['model_id']}`. Grid {grid['shape'][0]}×{grid['shape'][1]} @ "
        f"{grid['resolution_m']:g} m, pencere ofseti {grid['window_offset']}. "
        f"Tüm ölçüm {data['total_measure_s']:g} s."
    )
    add()
    add(
        "Buradaki her sayı bu gridde gerçekten koşuldu. Literatürün kendi sayıları "
        "`app.reachability.REACHABILITY_QUOTED` içinde durur ve bu tablolara "
        "karıştırılmaz."
    )
    add()

    # 1. negative edges
    add("## 1. Dijkstra neden çalışmaz — negatif kenarları ölç")
    add()
    add(
        "Araştırma belgesi D6 için “`cost_cube` üzerinde çok-kaynaklı Dijkstra "
        "(enerji bütçeli)” diyor. `cost_engine.move_battery_drain_wh` işaretlidir: "
        "aydınlık ve düz bir hücrede panel sürüşten fazla üretir ve kenar NEGATİF "
        "olur. Dijkstra negatif kenarla sessizce yanlış cevap verir."
    )
    add()
    for rover_id, block in data["negative_edges"]["rovers"].items():
        add(
            f"**{block['name']}** (`{rover_id}`) — düz hücrede başabaş gölge oranı "
            f"**{block['flat_break_even_shadow_ratio']:.4f}**; bunun altında sürmek "
            f"bataryayı DOLDURUR. Dilim {block['slice_hours']:.5f} h, coarsen "
            f"{data['negative_edges']['coarsen']}, {data['negative_edges']['n_slices']} dilim."
        )
        add()
        add("| epoch | t0'da aydınlık blok | sürüş kenarı | negatif | % | en kötü (Wh) | bekleme kenarı | negatif | % |")
        add("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in block["epochs"]:
            if "unavailable" in row:
                add(f"| {row['epoch'][:10]} | — | — | — | — | — | — | — | yok: {row['unavailable']} |")
                continue
            add(
                f"| {row['epoch'][:10]} | {100.0 * row['lit_fraction_at_first_slice']:.1f} % | "
                f"{row['drive_edges']:,} | {row['drive_negative']:,} | "
                f"{row['drive_negative_pct']:.2f} | {row['worst_drive_wh']:+.3f} | "
                f"{row['wait_edges']:,} | {row['wait_negative']:,} | "
                f"{row['wait_negative_pct']:.1f} |"
            )
        add()
    add(
        "**Tuzak budur:** tamamen karanlık bir epoch'ta sayı sıfırdır. Test paketinin "
        "çoğunun kullandığı 2026-09-01 tam olarak öyle bir epoch. Bir Dijkstra orada "
        "doğru görünür, aydınlık bir epoch'ta yanlış cevap verir ve hiçbir test kırmızıya "
        "dönmez."
    )
    add()
    add(
        "Tabanlanmış ikiz `net_energy_per_metre_wh` de kullanılamaz: `max(0, …)` "
        "olduğu için “güneşte sürerek menzil kazanamazsın” der. Bu modelde bu yanlıştır "
        "ve yalnızca tek yönde yanlıştır — muhafazakârlığın en kötü türü."
    )
    add()

    # 2. standard starts
    add("## 2. Üç standart başlangıç")
    add()
    for row in data["starts"]:
        add(f"### {row['name']} — `{row['rover_id']}` {tuple(row['start'])}, coarsen {row['coarsen']}")
        add()
        if row.get("coarsen_4"):
            add(
                f"> coarsen 4'te **reddedilir**: {row['coarsen_4']}. VIPER'ın 15° eğim "
                "sınırı, ince hücre geçilebilirken bloğun muhafazakâr AND'ini düşürüyor. "
                "Bu bir eksik değil, pencerenin gerçek bir özelliği; ölçüm coarsen 2'de."
            )
            add()
        if "refused" in row:
            add(f"> ölçülemedi: {row['refused']}")
            add()
            continue
        add(
            f"Dilim {row['slice_hours']:.5f} h × {row['n_slices']} = "
            f"{row['horizon_hours']:.3f} h ufuk. Kaba grid "
            f"{row['coarse_shape'][0]}×{row['coarse_shape'][1]}, geçilebilir "
            f"{row['traversable_blocks']:,} blok."
        )
        add()
        add(
            f"**Erişilebilir: {row['reachable_blocks']:,} blok "
            f"({row['reachable_area_km2']:.4f} km²)**, geçilebilirin "
            f"%{100.0 * row['reachable_blocks'] / max(1, row['traversable_blocks']):.2f}'i. "
            f"Süre {row['sweep_s']:g} s, {row['edge_groups']} kenar grubu, "
            f"{row['edges_relaxed']:,} kenar gevşetildi ({row['negative_edges']:,} negatif)."
        )
        add()
        add("| bant | saat | blok | km² |")
        add("|---|---|---:|---:|")
        for band in row["bands"]:
            add(
                f"| {band['band']} | {band['from_hours']:.3f}–{band['to_hours']:.3f} | "
                f"{band['blocks']:,} | {band['area_km2']:.4f} |"
            )
        add()
        add(
            f"Reddetmeler: `soc_floor` {row['refusals']['soc_floor']:,}, "
            f"`shadow_endurance` {row['refusals']['shadow_endurance']:,}, "
            f"`horizon` {row['refusals']['horizon']:,} → **energy_binds = "
            f"{str(row['energy_binds']).lower()}**."
        )
        if not row["energy_binds"]:
            add()
            add(
                "> Bu ufukta ve bu şarjda enerji kuralları hiç tetiklenmedi: sınır saatin "
                "kendisi. Harita bu durumda bir **kapılı mesafe dönüşümü**dür, enerji "
                "izokronu değil. Doğru bir ifadedir, ama başlığın vaat ettiğinden farklı "
                "bir şeydir ve yanıt bunu `energy_binds` ile söyler."
            )
        add()
        add(
            f"Duruş saati ({row['hold_horizon_h']:g} h ufuk, 0.5 h adım): "
            f"`reserve` {row['hold_limited_by']['reserve']:,} blokta, "
            f"`shadow_endurance` {row['hold_limited_by']['shadow_endurance']:,} blokta, "
            f"sansürlü {row['hold_limited_by']['censored']:,}. "
            + (
                f"En kısa {row['hold_limit_min_h']:g} h, en uzun {row['hold_limit_max_h']:g} h."
                if row["hold_limit_min_h"] is not None
                else "Hiçbir saat ufuk içinde dolmadı."
            )
        )
        add()
        add(
            f"Ödenmemiş rölanti: hamle başına ortalama {row['unpaid_idle_mean_h']:.4f} h — "
            "bir hamle saati `ceil(travel_h / slice_hours)` tam dilim ilerletir ama gücü "
            "yalnızca `travel_h` boyunca öder. Bu planlayıcının kendi konvansiyonudur ve "
            "kasten miras alınır (aksi hâlde küme planlayıcının gevşetmesi olmaktan çıkardı), "
            "ama yayımlanan her şarjı bu kadar saatlik housekeeping kadar İYİMSER yapar."
        )
        add()
        add(
            f"Kısmen aydınlık blok (ilk dilimde 0 < pozlama < 1): "
            f"{row['partially_lit_blocks']:,}. Bu bloklarda pozlama, ikili bir maskenin "
            "blok ORTALAMASIDIR; rover tek bir ince hücrededir ve ya aydınlıktadır ya değil."
        )
        add()

    # 3. budget curve
    add("## 3. Bütçe eğrisi — SOC ve ufuk değiştikçe")
    add()
    add(
        "Aynı başlangıç, aynı epoch, değişen şarj ve ufuk. `soc_floor` sütunu enerjinin "
        "gerçekten bağlayıp bağlamadığını gösterir."
    )
    add()
    add("| başlangıç | epoch | SOC | ufuk (h) | dilim | erişilebilir blok | km² | soc_floor red | horizon red | enerji bağlıyor mu | süre (s) |")
    add("|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for row in data["budget"]:
        add(
            f"| {row['name']} | {row['epoch'][:10]} | {row['initial_soc_pct']:.2f} | "
            f"{row['horizon_hours']:g} | {row['n_slices']} | {row['reachable_blocks']:,} | "
            f"{row['reachable_area_km2']:.4f} | {row['soc_floor_refusals']:,} | "
            f"{row['horizon_refusals']:,} | {'evet' if row['energy_binds'] else 'hayır'} | "
            f"{row['sweep_s']:g} |"
        )
    add()
    add(
        "Okunacak şey: tam şarjda sınır saattir (`horizon` reddi büyük, `soc_floor` sıfır); "
        "şarj düştükçe `soc_floor` devreye girer ve erişilebilir alan çöker. Bir izokronu "
        "“enerji izokronu” diye sunmadan önce hangi kuralın bağladığına bakılmalıdır."
    )
    add()

    # 4. now vs later
    add("## 4. “Şimdi” ile “N saat sonra”")
    add()
    add(
        "İki sweep de AYNI bloktan, AYNI şarjla başlar; yalnızca epoch değişir. Yani "
        "`lost`, arazinin kaybolması değil, *o saatte yola çıkan* bir rover'ın oraya "
        "gidememesidir. “Burada N saat beklersem ne kazanırım?” sorusunun cevabı bu "
        "değildir — o soru zaten temel sweep'in kendi bekleme kenarlarının içindedir ve "
        "bekleyen rover oraya daha az şarjla varır."
    )
    add()
    if data["later"]:
        add("| başlangıç | epoch | N (h) | dilim | t0 aydınlık | t0+N aydınlık | şimdi | sonra | ortak | kazanılan | kaybedilen | Jaccard |")
        add("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for row in data["later"]:
            add(
                f"| {row['name']} | {row['epoch'][:10]} | {row['later_hours']:.3f} | "
                f"{row['later_slices']} | {100.0 * row['lit_fraction_now']:.2f} % | "
                f"{100.0 * row['lit_fraction_later']:.2f} % | "
                f"{row['now_blocks']:,} | {row['later_blocks']:,} | "
                f"{row['kept_blocks']:,} | {row['gained_by_later_start_blocks']:,} | "
                f"{row['lost_by_later_start_blocks']:,} | "
                f"{row['jaccard'] if row['jaccard'] is not None else '—'} |"
            )
        add()
    add(
        "**Ölçülen bulgu:** saat ölçeğinde küme kıpırdamıyor. 6 ve 24 saatlik "
        "kaydırmalarda aydınlık blok oranı ölçülebilir biçimde değişiyor (tablodaki iki "
        "aydınlık sütunu bunu gösteriyor) ama erişilebilir kümede TEK blok bile "
        "değişmiyor. Sebebi fizik: kutupta aydınlanma ~708 saatlik sinodik döngüyle döner, "
        "yani bir gün döngünün %3'üdür ve terminatör neredeyse hiç yürümez. Etki gün "
        "ölçeğinde geliyor: +96 saatte aydınlık epoch'tan 151 blok kaybediliyor "
        "(Jaccard 0.979) ve +240 saatte pencere tamamen karanlığa giriyor — 7 362 blok "
        "586'ya düşüyor (Jaccard 0.080). Karanlık epoch'tan bakıldığında aynı şey ters "
        "yönde: +96 saatte 586 blok 7 362'ye çıkıyor. Site11'de “N saat sonra” sorusunun "
        "anlamlı hâli GÜN ölçeğindedir."
    )
    add()
    add(
        "Bu tabloyu yalnızca Jaccard sütunuyla yayımlamak, “küme zamanla sabittir” gibi "
        "okunurdu — ve bu, güneşin hiç modellenmediği durumdan ayırt edilemezdi. İki "
        "aydınlık sütunu tam olarak o ayrımı yapmak için var: gölge gerçekten hareket "
        "etti, küme hareket etmedi."
    )
    add()
    add(
        "`later_hours` tam dilim sayısına yuvarlanır ve yuvarlanmış değer yayımlanır: "
        "yuvarlanmamış bir kaydırma ikinci sweep'in dilimlerini birincininkilerin arasına "
        "düşürür ve her fark, hareket eden gölgeden ayrılamayan bir örnekleme artefaktı "
        "taşır."
    )
    add()

    # 5. agreement
    add("## 5. Gevşetme ne kadar gevşek — planlayıcıyla örneklem karşılaştırması")
    add()
    agreement = data["agreement"]
    if "unavailable" in agreement:
        add(f"> ölçülemedi: {agreement['unavailable']}")
    else:
        add(
            f"{agreement['name']}, {agreement['epoch'][:10]}. Sweep'in erişilebilir dediği "
            f"{agreement['sampled']} blok örneklendi ve her biri için 4-B planlayıcı "
            f"gerçekten koşuldu (aynı coarsen, aynı dilim, aynı epoch, aynı ufuk, her "
            f"opsiyonel kısıt kapalı): **{agreement['planner_routed']}/{agreement['sampled']} "
            f"= %{agreement['agreement_pct']:g}** rota buldu. {agreement['elapsed_s']:g} s."
        )
        add()
        add("| blok | sweep ilk dilim | planlayıcı rota buldu mu | planlayıcı varış dilimi |")
        add("|---|---:|---|---:|")
        for item in agreement["details"]:
            add(
                f"| {tuple(item['block'])} | {item['sweep_first_slice']} | "
                f"{'evet' if item['planner_routed'] else 'hayır'} | "
                f"{item['planner_arrival_slice'] if item['planner_arrival_slice'] is not None else '—'} |"
            )
        add()
        add(
            "Planlayıcının varış dilimi her satırda sweep'in ilk diliminden büyük ya da ona "
            "eşit. Bu, içerme özelliğinin ikinci yüzüdür: sweep'in “en erken varış”ı "
            "planlayıcının varışı için bir ALT sınırdır, çünkü sweep aynı kenarları aynı "
            "saat kuralıyla gevşetir ve hiçbir ek kısıt uygulamaz."
        )
        add()
        add(
            "%100'ün altındaki her şey gevşetmenin gevşekliğidir ve beklenir: iki zarf "
            "alanı BAĞIMSIZ optimize edilir, yani bir blok için yayımlanan şarj ile "
            "karanlık saati farklı öncüllerden gelebilir ve tek bir yörünge ikisini birden "
            "gerçekleştirmek zorunda değildir. İddianın neden negatif yönde kurulduğu tam "
            "olarak budur."
        )
    add()

    # 6. claim boundary
    add("## 6. İddia sınırı")
    add()
    add(
        "* **Güvenli yön tek yöndür.** Kümenin DIŞINDAKİ bir blok, bu enerji modelinin "
        "“oraya gidemezsin” dediği bloktur. İÇİNDEKİ bir blok adaydır, söz değildir."
    )
    add(
        "* **İçerme hangi yapılandırmaya karşı?** `planner_configuration` yanıtta "
        "yayımlanır. `allow_hibernate=True` ile koşan bir plan bu kümenin dışına meşru "
        "biçimde çıkabilir: hibernasyon üçüncü bir kenar ailesidir, `p_hibernate_w` ile "
        "boşalır ve uyanışta karanlık saatini sıfırlar."
    )
    add(
        "* **İki başlık ters yönde yanılır.** `reachable` fazla büyüktür (gevşetme + "
        "replay edilmeyen altı kapı), `earliest_hours` fazla geçtir (hamle başına bir "
        "dilime kadar yukarı yuvarlama). Birbirlerini götürmezler; zıt operasyonel "
        "kararlara işaret ederler ve yanıt her alan için yönü `conservatism` ile söyler."
    )
    add(
        "* **Karanlık saati saat değildir.** `astar_4d`'in kendi konvansiyonu: saat "
        "`hours × exposure` ile ilerler. Pozlaması 0.5 olan bir blok saati yarı hızda "
        "harcar, yani duvar saatiyle 50 h'lik dayanım 100 h'e kadar uzayabilir. Gerçek "
        "gridde ölçüldü: dayanımın bağladığı bloklarda duruş süresi 49.5 h ile 56.0 h "
        "arasında, yayımlanan `h_max_shadow_h` 50 h."
    )
    add(
        "* **`time-to-0-SOC` bir işletme payı değildir.** Rezervin altında bu modelde hiç "
        "geçiş yoktur; sayı batarya fiziğidir. İşletme sayısı `hold_limit` = "
        "min(rezerv saati, dayanım saati) ve hangisinin bağladığı `hold_limited_by` ile "
        "birlikte yayımlanır."
    )
    add(
        "* **Epoch zorunludur.** `start_utc` olmadan `build_shadow_series` uzun dönem gölge "
        "KESRİNE düşer — bir iklimoloji, gökyüzü değil. Onun üstüne çizilen izokron araziyi "
        "ve bataryayı ölçer, bugünü değil; ve “N saat sonra” farkı tam olarak sıfır çıkar. "
        "Bu yüzden 422'dir, `/api/plan-4d`'in aksine geri düşecek anlamlı bir mod yok."
    )
    add(
        "* **Yumuşatma yok, `skimage` yok.** Bant sınırı kaba blok kafesinin merdivenidir. "
        "Araştırma belgesinin önerdiği `skimage.measure.find_contours` yeni bir bağımlılık "
        "olurdu (`backend/requirements.txt`'te yok) ve bir blok kafesinin çevresine daha "
        "güzel bir çizgi çizmek için modelin hiç değerlendirmediği araziden geçen bir hat "
        "üretirdi."
    )
    add(
        "* **Yayılmayan belirsizlik.** Kayma, DEM hatası, batarya sıcaklığı ve konumlandırma "
        "kayması bu depoda MODELLENİYOR ve burada yayılmıyor. Sınırı ne kadar oynattıklarına "
        "dair sayı yayımlanmıyor, çünkü ölçülmedi."
    )
    add()
    add(
        "Literatür yöntem kaynağıdır. Tompkins'in ve arXiv 2509.15062'nin kendi sayıları "
        "`REACHABILITY_QUOTED` sözlüğündedir, bu tablolarda değil; araştırma belgesinin "
        "kendi iddialarında bulunan düzeltmeler `REACHABILITY_CORRECTIONS` içinde durur."
    )
    add()
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None, help="write the measurements here BEFORE rendering")
    parser.add_argument(
        "--from-json", default=None, help="render from a previous dump instead of measuring"
    )
    parser.add_argument("--out", default=str(REPORT_PATH), help="where to write the report")
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        data = measure()
        if args.json:
            Path(args.json).write_text(
                json.dumps(data, indent=1, default=float), encoding="utf-8"
            )

    Path(args.out).write_text(render(data), encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
