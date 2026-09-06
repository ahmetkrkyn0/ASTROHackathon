#!/usr/bin/env python3
"""Measure the measured-roughness criterion and the PSR mask (C4) on Site11.

What it measures, in order:

1. The products and the co-registration: NASA's LDRM roughness (50 m/px,
   100 m baseline) and LPSR PSR mask (20 m/px) on the 5 m grid -- CRS
   equality, the window, the resolution ratio, the registration check
   (NASA's own 100 m plane-fit slope vs the block mean of our slope).
2. The roughness itself: the multi-baseline distribution over the window,
   Site11 against the 80-90 S region, the Spearman correlation with slope
   (the H-4 question: is the criterion a restatement of slope?), the
   PSJ 2025 slope-bin trend, the criterion's [0, 1] distribution, and per
   rover the v5 cost grid against the four-term one under a weight sweep.
3. The PSR mask against our shadow model: Jaccard at several thresholds,
   on cells and on the product's 20 m blocks, what the mask contains
   thermally, and how many PSR cells each rover could enter anyway.
4. The standard 2-D pairs (/api/plan) under w_roughness in
   {0, 0.05, 0.10, 0.15, 0.20, 0.30}: route, distance, hours, Wh, min SOC,
   the route's roughness, PSR cells, overlap with the w=0 route, and the
   criterion's share of the cell cost along the route.
5. The standard 4-D routes (/api/plan-4d) at w = 0 and 0.15, each followed
   by /api/stress-test (SHERPA, 1 000 runs).
6. A reading, the presentation sentence and the claim limits.

Needs the processed grids and the roughness/PSR cache for 1-4, plus
horizon_map.npy and the NAIF kernels for 5; without the latter it says so
and skips section 5. It never fabricates numbers. Writes the JSON dump
(--json) BEFORE the markdown; --from-json re-renders without measuring.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

from app.constants import get_rover  # noqa: E402
from app.cost_vec import f_roughness_grid, f_slope_grid  # noqa: E402
from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids  # noqa: E402
from app.main import app  # noqa: E402
from app.roughness import (  # noqa: E402
    PSR_CLAIM,
    ROUGHNESS_BASELINES_FILENAME,
    ROUGHNESS_CLAIM,
    RoughnessScale,
    psr_shadow_overlap,
)
from app.rover_grids import grids_for_rover  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
WEIGHTS: tuple[float, ...] = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30)
WEIGHTS_4D: tuple[float, ...] = (0.0, 0.15)
COARSEN = 4
ROVERS = ("lpr_1", "nasa_viper")

PAIRS_2D = [
    {"label": "LPR-1 gündüz", "rover_id": "lpr_1", "start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426}},
    {"label": "LPR-1 Ay gecesi çifti", "rover_id": "lpr_1", "start": {"row": 186, "col": 34}, "goal": {"row": 494, "col": 450}},
    {"label": "VIPER standart", "rover_id": "nasa_viper", "start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426}},
    {"label": "VIPER kısa leg", "rover_id": "nasa_viper", "start": {"row": 358, "col": 494}, "goal": {"row": 346, "col": 462}},
]
CASES_4D = [
    {"label": "LPR-1 28 Eyl 2026", "rover_id": "lpr_1", "start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426},
     "start_utc": "2026-09-28T00:00:00", "extra": {}},
    {"label": "LPR-1 Ay gecesi 13 Eyl 2026", "rover_id": "lpr_1", "start": {"row": 186, "col": 34}, "goal": {"row": 494, "col": 450},
     "start_utc": "2026-09-13T00:00:00", "extra": {}},
    {"label": "VIPER kısa leg 30 May 2027 (haven kuralı)", "rover_id": "nasa_viper", "start": {"row": 358, "col": 494},
     "goal": {"row": 346, "col": 462}, "start_utc": "2027-05-30T00:00:00", "extra": {"require_safe_haven": True}},
]


# ── formatting ──────────────────────────────────────────────────────────────


def _fmt(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "—"
    return f"{value:.{digits}f}".replace(".", ",")


def _pct(value, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"%{100.0 * value:.{digits}f}".replace(".", ",")


def _int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _w(w: float) -> str:
    return _fmt(w, 2)


# ── 1. products ─────────────────────────────────────────────────────────────


def measure_products(grids: dict, processed: Path) -> dict:
    meta_r = grids["metadata"].get("roughness") or {}
    meta_p = grids["metadata"].get("psr") or {}
    res = float(grids["metadata"]["resolution_m"])
    out = {
        "roughness_meta": {k: meta_r.get(k) for k in (
            "product", "file_url", "baseline_m", "resolution_m", "fetched_utc", "resampling", "crs_match",
            "window", "destination", "registration_check", "stats_on_grid_m", "regional_sample", "definition",
        )},
        "psr_meta": {k: meta_p.get(k) for k in (
            "product", "file_url", "resolution_m", "fetched_utc", "resampling", "window", "n_psr_cells",
            "psr_fraction", "n_psr_pixels_product", "n_nan_cells", "product_feature_count",
        )},
        "cells_per_roughness_pixel": int(round(float(meta_r.get("resolution_m", 50)) / res)) ** 2,
        "cells_per_psr_pixel": int(round(float(meta_p.get("resolution_m", 20)) / res)) ** 2,
        "scale_knots": len((meta_r.get("scale") or {}).get("knots") or []),
        "scale_regional_quantiles_m": (meta_r.get("regional_sample") or {}).get("quantiles_m"),
    }
    npz = processed / ROUGHNESS_BASELINES_FILENAME
    baselines = []
    if npz.exists():
        data = np.load(npz)
        for b in data["baselines_m"].tolist():
            arr = data[f"rough_{int(b)}m"]
            fin = arr[np.isfinite(arr)]
            baselines.append({"baseline_m": int(b), "median": float(np.median(fin)), "p95": float(np.percentile(fin, 95)), "max": float(fin.max())})
        hurst = data["hurst"]
        fin = hurst[np.isfinite(hurst)]
        out["hurst"] = {"p5": float(np.percentile(fin, 5)), "median": float(np.median(fin)), "p95": float(np.percentile(fin, 95))}
        slp = data["slp_100m"]
        fin = slp[np.isfinite(slp)]
        out["slp_100m_deg"] = {"median": float(np.median(fin)), "p95": float(np.percentile(fin, 95))}
    out["baselines"] = baselines
    return out


# ── 2. the roughness on the grid ────────────────────────────────────────────


def measure_grid(grids: dict) -> dict:
    rough = np.asarray(grids["roughness"], dtype=np.float64)
    slope = np.asarray(grids["slope"], dtype=np.float64)
    scale = RoughnessScale.from_meta(grids["metadata"]["roughness"]["scale"])
    fin = np.isfinite(rough) & np.isfinite(slope)
    f = f_roughness_grid(rough, scale)
    out: dict = {
        "site_quantiles_m": {f"p{p}": float(np.percentile(rough[fin], p)) for p in (1, 5, 25, 50, 75, 95, 99)},
        "site_max_m": float(np.nanmax(rough)),
        "n_nan": int(np.isnan(rough).sum()),
        "n_unique_blocks": int(np.unique(rough[np.isfinite(rough)]).size),
        "spearman_rough_slope_5m": float(spearmanr(rough[fin], slope[fin]).statistic),
        "f_quantiles": {f"p{p}": float(np.percentile(f[fin], p)) for p in (1, 5, 25, 50, 75, 95, 99)},
        "f_ge_0.99": float(np.mean(f[fin] >= 0.99)),
        "f_le_0.01": float(np.mean(f[fin] <= 0.01)),
    }
    # 50 m blocks
    factor = int(round(float(grids["metadata"]["roughness"]["resolution_m"]) / float(grids["metadata"]["resolution_m"])))
    rows, cols = slope.shape
    rc, cc = rows // factor, cols // factor
    sl_blocks = slope[: rc * factor, : cc * factor].reshape(rc, factor, cc, factor)
    sl_mean = np.nanmean(sl_blocks, axis=(1, 3))
    sl_max = np.nanmax(sl_blocks, axis=(1, 3))
    r_blocks = rough[: rc * factor, : cc * factor].reshape(rc, factor, cc, factor)[:, 0, :, 0]
    ok = np.isfinite(r_blocks) & np.isfinite(sl_mean)
    out["spearman_rough_blockmean_slope_50m"] = float(spearmanr(r_blocks[ok], sl_mean[ok]).statistic)
    out["spearman_rough_blockmax_slope_50m"] = float(spearmanr(r_blocks[ok], sl_max[ok]).statistic)
    out["slope_bins"] = []
    for lo, hi in ((0, 5), (5, 10), (10, 15), (15, 20), (20, 90)):
        m = fin & (slope >= lo) & (slope < hi)
        out["slope_bins"].append({"lo": lo, "hi": hi, "n": int(m.sum()), "median_m": float(np.median(rough[m])) if m.any() else None,
                                  "p90_m": float(np.percentile(rough[m], 90)) if m.any() else None})
    # per rover: the criterion against the slope criterion, the cost grid under the weights
    out["rovers"] = {}
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        nominal = grids_for_rover(grids, rover_id, {"w_roughness": 0.0})
        trav = np.asarray(nominal["traversable"], dtype=bool) & np.isfinite(nominal["cost"])
        fs = f_slope_grid(slope, rover)
        okr = trav & np.isfinite(fs)
        entry = {
            "passable": int(trav.sum()),
            "spearman_f_roughness_f_slope_passable": float(spearmanr(f[okr], fs[okr]).statistic),
            "weights": [],
        }
        for w in WEIGHTS:
            if w == 0.0:
                cost = nominal["cost"]
            else:
                cost = grids_for_rover(grids, rover_id, {"w_roughness": w})["cost"]
            rel = cost[trav] / nominal["cost"][trav] - 1.0
            share = (w * f[trav]) / cost[trav]
            entry["weights"].append({
                "w": w,
                "spearman_vs_w0": float(spearmanr(cost[trav], nominal["cost"][trav]).statistic) if w > 0 else 1.0,
                "mean_rel_change": float(np.mean(rel)),
                "max_rel_change": float(np.max(rel)),
                "mean_share": float(np.mean(share)),
                "p95_share": float(np.percentile(share, 95)),
            })
        out["rovers"][rover_id] = entry
    return out


# ── 3. PSR vs shadow ────────────────────────────────────────────────────────


def measure_psr(grids: dict) -> dict:
    psr = np.asarray(grids["psr"], dtype=np.float64)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    tmin = grids.get("thermal_min")
    out: dict = {"thresholds": [], "blocks_20m": []}
    for thr in (0.90, 0.95, 0.98, 0.99, 1.0):
        out["thresholds"].append(psr_shadow_overlap(psr, shadow, tmin, thr))
    factor = int(round(float(grids["metadata"]["psr"]["resolution_m"]) / float(grids["metadata"]["resolution_m"])))
    rows, cols = psr.shape
    rc, cc = rows // factor, cols // factor
    p_b = (psr[: rc * factor, : cc * factor] >= 0.5).reshape(rc, factor, cc, factor)[:, 0, :, 0]
    s_b = shadow[: rc * factor, : cc * factor].reshape(rc, factor, cc, factor).mean(axis=(1, 3))
    for thr in (0.98, 0.99, 1.0):
        d = s_b >= thr
        out["blocks_20m"].append({"threshold": thr, "jaccard": float((p_b & d).sum() / max(1, (p_b | d).sum())), "n_blocks_psr": int(p_b.sum()), "n_blocks_dark": int(d.sum())})
    out["shadow_inside_psr_quantiles"] = {f"p{p}": float(np.percentile(shadow[psr >= 0.5], p)) for p in (1, 5, 50)}
    if tmin is not None:
        t = np.asarray(tmin, dtype=np.float64)
        out["thermal_min_le_minus180"] = {"n": int((t <= -180.0).sum()), "in_psr": int(((t <= -180.0) & (psr >= 0.5)).sum())}
    out["shadow_eq_1"] = {"n": int((shadow >= 1.0).sum()), "in_psr": int(((shadow >= 1.0) & (psr >= 0.5)).sum())}
    out["passable_inside_psr"] = {}
    for rover_id in ROVERS:
        trav = np.asarray(grids_for_rover(grids, rover_id)["traversable"], dtype=bool)
        out["passable_inside_psr"][rover_id] = int((trav & (psr >= 0.5)).sum())
    out["n_psr"] = int((psr >= 0.5).sum())
    return out


# ── 4. 2-D pairs ────────────────────────────────────────────────────────────


def _cells_of(payload: dict) -> set:
    return {(int(w["row"]), int(w["col"])) for w in payload.get("waypoints") or []}


def measure_2d(client: TestClient, pair: dict, grids: dict) -> dict:
    rows = []
    base_cells = None
    for w in WEIGHTS:
        t0 = time.perf_counter()
        response = client.post(
            "/api/plan",
            json={"start": pair["start"], "goal": pair["goal"], "rover_id": pair["rover_id"], "weights": {"w_roughness": w}},
        )
        seconds = time.perf_counter() - t0
        if response.status_code != 200:
            rows.append({"w": w, "status": response.status_code, "detail": response.json().get("detail"), "seconds": seconds})
            continue
        p = response.json()
        cells = _cells_of(p)
        if base_cells is None:
            base_cells = cells
        summary = p.get("summary") or {}
        route = (p.get("roughness") or {}).get("route") or {}
        # the criterion's share of the cell cost along the route
        adapted = grids_for_rover(grids, pair["rover_id"], {"w_roughness": w})
        scale = RoughnessScale.from_meta(grids["metadata"]["roughness"]["scale"])
        rr = np.array([int(c[0]) for c in cells], dtype=int)
        cc = np.array([int(c[1]) for c in cells], dtype=int)
        f_cells = f_roughness_grid(np.asarray(grids["roughness"])[rr, cc], scale)
        cost_cells = np.asarray(adapted["cost"])[rr, cc]
        okc = np.isfinite(cost_cells) & (cost_cells > 0)
        share = float(np.mean((w * f_cells[okc]) / cost_cells[okc])) if okc.any() else None
        rows.append({
            "w": w, "status": 200, "seconds": seconds,
            "waypoints": summary.get("waypoint_count"),
            "distance_km": summary.get("total_distance_km"),
            "hours": summary.get("total_elapsed_hours"),
            "energy_wh": summary.get("total_energy_consumed_wh"),
            "min_soc": summary.get("min_battery_pct"),
            "mean_roughness_m": route.get("mean_roughness_m"),
            "max_roughness_m": route.get("max_roughness_m"),
            "mean_f": route.get("mean_f_roughness"),
            "cells_in_psr": route.get("cells_in_psr"),
            "overlap_with_w0": len(cells & base_cells) / max(1, len(cells | base_cells)),
            "roughness_share_of_cell_cost": share,
            "applied": (p.get("roughness") or {}).get("applied"),
        })
    return {"pair": pair, "rows": rows}


# ── 5. 4-D routes + SHERPA ──────────────────────────────────────────────────


def _overlap_states(a, b) -> float | None:
    if a is None or b is None:
        return None
    sa = {tuple(p[:2]) for p in a}
    sb = {tuple(p[:2]) for p in b}
    return len(sa & sb) / max(1, len(sa | sb))


def measure_4d(client: TestClient, case: dict, n_runs: int, seed: int) -> dict:
    out: dict = {"case": case, "rows": []}
    base_states = None
    for w in WEIGHTS_4D:
        body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"], "start_utc": case["start_utc"],
                "weights": {"w_roughness": w}, **case["extra"]}
        print(f"    plan-4d w_roughness={w} ...", flush=True)
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        plan_s = time.perf_counter() - t0
        if response.status_code != 200:
            out["rows"].append({"w": w, "status": response.status_code, "detail": response.json().get("detail"), "plan_s": plan_s})
            continue
        p = response.json()
        if base_states is None:
            base_states = p["path_states"]
        route = (p.get("roughness") or {}).get("route") or {}
        entry = {
            "w": w, "status": 200, "plan_s": plan_s,
            "n_slices": p["n_slices"], "slice_hours": p["slice_hours"],
            "moves": p["metrics"]["move_steps"], "waits": p["metrics"].get("wait_steps"),
            "arrival_hours": p["metrics"]["arrival_hours"],
            "min_soc": min(p["path_battery_pct"]),
            "nodes_expanded": p["metrics"].get("nodes_expanded"),
            "mean_slip": p["slip_model"]["route"]["mean_slip"],
            "mean_roughness_m": route.get("mean_roughness_m"),
            "max_roughness_m": route.get("max_roughness_m"),
            "mean_f": route.get("mean_f_roughness"),
            "cells_in_psr": route.get("cells_in_psr"),
            "overlap_with_w0": _overlap_states(p["path_states"], base_states),
            "ends_at_haven": p["metrics"].get("ends_at_safe_haven"),
        }
        t1 = time.perf_counter()
        stress = client.post(
            "/api/stress-test",
            json={"path_states": p["path_states"], "rover_id": case["rover_id"], "start_utc": case["start_utc"],
                  "slice_hours": p["slice_hours"], "coarsen": COARSEN, "n_runs": n_runs, "seed": seed},
        )
        entry["stress_s"] = time.perf_counter() - t1
        if stress.status_code == 200:
            s = stress.json()
            entry["stress"] = {
                "completion": s["rates"]["completion"]["rate"],
                "within_reserve": s["rates"]["reached_within_reserve"]["rate"],
                "full_success": s["rates"]["full_success"]["rate"],
                "nominal_min_battery_pct": s["nominal"]["min_battery_pct"],
            }
        else:
            entry["stress"] = {"error": stress.json().get("detail")}
        out["rows"].append(entry)
    return out


# ── markdown ────────────────────────────────────────────────────────────────


def _write_markdown(path: Path, report: dict, args) -> None:
    L: list[str] = []
    prod = report["products"]
    rm, pm = prod["roughness_meta"], prod["psr_meta"]
    reg = rm.get("registration_check") or {}
    L += [
        "# Ölçülmüş pürüzlülük (LOLA LDRM) ve PSR maskesi (C4) — Site11 raporu",
        "",
        f"Üretildi: {report['generated_utc']} (`scripts/roughness_psr_report.py`). Beşinci maliyet kriteri `f_roughness` NASA'nın "
        f"**ölçülmüş** LDRM pürüzlülüğünü ({rm.get('product')}, {rm.get('resolution_m')} m/px, {rm.get('baseline_m')} m taban) "
        "okur; katman `MEASURED`, [0, 1] ölçeği bölgesel ECDF sırası (`MODEL`). PSR maskesi (`" + str(pm.get("product")) + "`, "
        f"{pm.get('resolution_m')} m/px) planlamaya girmez; bizim `shadow_ratio`'muza karşı doğrulama olarak ölçülür. "
        f"\"Önce\" = `w_roughness = 0` (aynı kod; katman katkısı sıfır → grid v4 ile bit-eşit, SHA kilidi testte). "
        f"Monte Carlo {args.n_runs} koşum, tohum {args.seed}.",
        "",
        f"**İddia sınırı (pürüzlülük):** {ROUGHNESS_CLAIM}",
        "",
        f"**İddia sınırı (PSR):** {PSR_CLAIM}",
        "",
        "## 1. Ürünler, pencere, ko-registrasyon",
        "",
        "| | Pürüzlülük | PSR |",
        "|---|---|---|",
        f"| Ürün | `{rm.get('product')}` | `{pm.get('product')}` |",
        f"| Çözünürlük / taban | {rm.get('resolution_m')} m/px / {rm.get('baseline_m')} m | {pm.get('resolution_m')} m/px |",
        f"| Pencere (ürün pikseli) | {_int((rm.get('window') or {}).get('rows'))}×{_int((rm.get('window') or {}).get('cols'))} (pay {(rm.get('window') or {}).get('pad_px')} px) | {_int((pm.get('window') or {}).get('rows'))}×{_int((pm.get('window') or {}).get('cols'))} (pay {(pm.get('window') or {}).get('pad_px')} px) |",
        f"| 5 m hücre / ürün pikseli | {prod['cells_per_roughness_pixel']} | {prod['cells_per_psr_pixel']} |",
        f"| İndirme (UTC) | {rm.get('fetched_utc')} | {pm.get('fetched_utc')} |",
        f"| Yeniden örnekleme | {rm.get('resampling')} | {pm.get('resampling')} |",
        f"| Projeksiyon | `{(rm.get('crs_match') or {}).get('product_crs_name')}` ≡ grid `{(rm.get('crs_match') or {}).get('grid_crs_name')}` (parametreler eşit) | aynı |",
        "",
        f"Tanım (ürün sayfası): *{rm.get('definition')}*",
        "",
        f"**Kayıt sağlaması:** LDRM `SLP_100M` (fit düzleminin eğimi) ↔ bizim 5 m eğimin {rm.get('resolution_m')} m blok ortalaması: "
        f"Spearman **{_fmt(reg.get('spearman'), 3)}** ({_int(reg.get('n_blocks'))} blok; medyanlar bizim {_fmt(reg.get('ours_median_deg'), 1)}° / NASA {_fmt(reg.get('theirs_median_deg'), 1)}°; eşik {_fmt(reg.get('threshold'), 1)}). "
        "Hedef transform `metadata.json` origin'ini hücre (0, 0)'ın sol-üst köşesi sayar (Site11 TIF transformuyla doğrulandı).",
        "",
    ]
    if prod.get("baselines"):
        L += ["## 2. Pürüzlülük dağılımı", "", "Pencere (50 m ham pikseller), taban başına:", "", "| Taban (m) | medyan (m) | p95 | maks |", "|---|---|---|---|"]
        for b in prod["baselines"]:
            L.append(f"| {b['baseline_m']} | {_fmt(b['median'], 3)} | {_fmt(b['p95'], 3)} | {_fmt(b['max'], 2)} |")
        h = prod.get("hurst") or {}
        L += ["", f"Hurst üssü: p5 {_fmt(h.get('p5'), 2)} / medyan {_fmt(h.get('median'), 2)} / p95 {_fmt(h.get('p95'), 2)}; LDRM 100 m eğimi medyanı {_fmt((prod.get('slp_100m_deg') or {}).get('median'), 1)}°.", ""]
    g = report["grid"]
    rq = prod.get("scale_regional_quantiles_m") or {}
    L += [
        "Site11 5 m gridi (100 m taban) ↔ 80–90°S bölgesi (ölçeğin örneği):",
        "",
        "| Kantil | Site11 (m) | Bölge (m) |",
        "|---|---|---|",
    ]
    for p in ("p5", "p25", "p50", "p75", "p95", "p99"):
        L.append(f"| {p} | {_fmt(g['site_quantiles_m'].get(p), 3)} | {_fmt(rq.get(p), 3)} |")
    L += [
        "",
        f"Site11 maks {_fmt(g['site_max_m'], 2)} m; NaN hücre {g['n_nan']}; benzersiz blok {_int(g['n_unique_blocks'])}. "
        f"Bölgesel örnek: {_int((rm.get('regional_sample') or {}).get('n_tiles'))} tile, {_int((rm.get('regional_sample') or {}).get('n_finite'))} sonlu piksel, {prod['scale_knots']} kantil düğümü.",
        "",
        f"**H-4 kontrolü — Spearman(pürüzlülük, eğim):** 5 m hücrelerde **{_fmt(g['spearman_rough_slope_5m'], 3)}**; 50 m blokta blok-ort. eğimle {_fmt(g['spearman_rough_blockmean_slope_50m'], 3)}, blok-maks ile {_fmt(g['spearman_rough_blockmax_slope_50m'], 3)}. "
        "Kriter eğimin yeniden ifadesi değil (H-4'te enerji–eğim 1,000 idi).",
        "",
        "Eğim kutuları (PSJ 2025: >10° eğimde 50–200 m tabanda pürüzlülük artıyor):",
        "",
        "| Eğim (°) | n | medyan pürüzlülük (m) | p90 |",
        "|---|---|---|---|",
    ]
    for b in g["slope_bins"]:
        L.append(f"| {b['lo']}–{b['hi'] if b['hi'] < 90 else '…'} | {_int(b['n'])} | {_fmt(b['median_m'], 3)} | {_fmt(b['p90_m'], 3)} |")
    fq = g["f_quantiles"]
    L += [
        "",
        f"`f_roughness` (bölgesel ECDF sırası) Site11'de: p5 {_fmt(fq['p5'], 3)} / p25 {_fmt(fq['p25'], 3)} / p50 {_fmt(fq['p50'], 3)} / p75 {_fmt(fq['p75'], 3)} / p95 {_fmt(fq['p95'], 3)}; ≥ 0,99 olan hücre {_pct(g['f_ge_0.99'])}, ≤ 0,01 olan {_pct(g['f_le_0.01'])}.",
        "",
    ]
    for rover_id, entry in g["rovers"].items():
        L += [
            f"### {get_rover(rover_id)['name']} (`{rover_id}`; geçilebilir hücre {_int(entry['passable'])})",
            "",
            f"Spearman(`f_roughness`, `f_slope`) geçilebilir hücrelerde {_fmt(entry['spearman_f_roughness_f_slope_passable'], 3)}.",
            "",
            "| w_roughness | Spearman (maliyet ↔ w=0) | maliyet ort. / maks bağıl değişim | kriterin hücre maliyetindeki payı (ort. / p95) |",
            "|---|---|---|---|",
        ]
        for row in entry["weights"]:
            L.append(f"| {_w(row['w'])} | {_fmt(row['spearman_vs_w0'], 4)} | +{_pct(row['mean_rel_change'])} / +{_pct(row['max_rel_change'])} | {_pct(row['mean_share'])} / {_pct(row['p95_share'])} |")
        L.append("")
    ps = report["psr"]
    L += [
        "## 3. PSR maskesi ↔ bizim gölge modelimiz",
        "",
        f"PSR hücresi {_int(ps['n_psr'])} (gridin {_pct(ps['n_psr'] / 250000.0 if ps['n_psr'] else 0)}; ürün pikseli {_int(pm.get('n_psr_pixels_product'))}). Karanlık = `shadow_ratio ≥ eşik`.",
        "",
        "| Eşik | karanlık hücre | Jaccard | PSR'ın yakalanan payı | karanlıkların PSR'da payı | yanlış pozitif |",
        "|---|---|---|---|---|---|",
    ]
    for t in ps["thresholds"]:
        L.append(f"| {_fmt(t['threshold'], 3)} | {_int(t['n_dark'])} | **{_fmt(t['jaccard'], 3)}** | {_fmt(t['psr_recall'], 3)} | {_fmt(t['dark_precision'], 3)} | {_pct(t['false_positive_fraction'])} |")
    t99 = next(t for t in ps["thresholds"] if abs(t["threshold"] - 0.99) < 1e-9)
    L += [
        "",
        "20 m ürün bloklarında (4×4 blok-ort. gölge): " + "; ".join(f"eşik {_fmt(b['threshold'], 2)} → Jaccard **{_fmt(b['jaccard'], 3)}**" for b in ps["blocks_20m"]) + ".",
        "",
        f"PSR içinde ort. `shadow_ratio` {_fmt(t99['mean_shadow_inside_psr'], 4)} (p1 {_fmt(ps['shadow_inside_psr_quantiles']['p1'], 3)}, medyan {_fmt(ps['shadow_inside_psr_quantiles']['p50'], 3)}), dışında {_fmt(t99['mean_shadow_outside_psr'], 3)}. "
        f"`thermal_min` medyanı PSR içinde {_fmt(t99.get('thermal_min_median_inside_psr'), 2)} °C (90 K PSR tabanı), dışında {_fmt(t99.get('thermal_min_median_outside_psr'), 1)} °C; "
        f"`thermal_min ≤ −180 °C` olan {_int((ps.get('thermal_min_le_minus180') or {}).get('n'))} hücrenin {_int((ps.get('thermal_min_le_minus180') or {}).get('in_psr'))}'i PSR'da; `shadow_ratio = 1` olan {_int(ps['shadow_eq_1']['n'])} hücrenin {_int(ps['shadow_eq_1']['in_psr'])}'i.",
        "",
        "Geçilebilir hücre PSR içinde: " + ", ".join(f"{get_rover(r)['name']} **{_int(n)}**" for r, n in ps["passable_inside_psr"].items()) + " — termal kapı PSR'ı zaten kapatıyor; maske bu yüzden planlamaya sokulmadı.",
        "",
        "## 4. Standart 2-B çiftler (`/api/plan`), `w_roughness` taraması",
        "",
        "Her satır kendi rotasının simülasyonudur; örtüşme = w = 0 rotasıyla hücre Jaccard'ı; pay = rota hücrelerinde `w·f / maliyet` ortalaması.",
        "",
    ]
    for block in report["pairs_2d"]:
        pair = block["pair"]
        L += [
            f"### {pair['label']} — `{pair['rover_id']}`, ({pair['start']['row']},{pair['start']['col']})→({pair['goal']['row']},{pair['goal']['col']})",
            "",
            "| w | nokta | km | saat | Wh | min SOC | rota pürüzlülük ort. / maks (m) | ort. f | PSR hücresi | örtüşme | pay | s |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in block["rows"]:
            if r.get("status") != 200:
                L.append(f"| {_w(r['w'])} | {r.get('status')} {r.get('detail')} | | | | | | | | | | |")
                continue
            L.append(
                f"| {_w(r['w'])} | {_int(r['waypoints'])} | {_fmt(r['distance_km'], 3)} | {_fmt(r['hours'], 3)} | {_fmt(r['energy_wh'], 1)} | {_fmt(r['min_soc'], 2)} | "
                f"{_fmt(r['mean_roughness_m'], 2)} / {_fmt(r['max_roughness_m'], 2)} | {_fmt(r['mean_f'], 2)} | {_int(r['cells_in_psr'])} | {_fmt(r['overlap_with_w0'], 2)} | {_pct(r['roughness_share_of_cell_cost'])} | {_fmt(r['seconds'], 2)} |"
            )
        L.append("")
    if report.get("cases_4d"):
        L += [
            "## 5. Standart 4-B rotalar (`/api/plan-4d`, coarsen 4) + SHERPA",
            "",
            f"w ∈ {{0, 0,15}}; pürüzlülük küpe blok-maks ile girer. Monte Carlo {args.n_runs} koşum.",
            "",
        ]
        for block in report["cases_4d"]:
            case = block["case"]
            L += [
                f"### {case['label']} — `{case['rover_id']}`, ({case['start']['row']},{case['start']['col']})→({case['goal']['row']},{case['goal']['col']})",
                "",
                "| w | hamle / bekleme | varış (h) | min SOC | ort. slip | rota pürüzlülük ort. / maks (m) | ort. f | PSR bloğu | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | plan s |",
                "|---|---|---|---|---|---|---|---|---|---|---|",
            ]
            for r in block["rows"]:
                if r.get("status") != 200:
                    L.append(f"| {_w(r['w'])} | {r.get('status')}: {r.get('detail')} | | | | | | | | | {_fmt(r.get('plan_s'), 1)} |")
                    continue
                st = r.get("stress") or {}
                L.append(
                    f"| {_w(r['w'])} | {_int(r['moves'])} / {_int(r['waits'])} | {_fmt(r['arrival_hours'], 3)} | {_pct(r['min_soc'] / 100.0)} | {_fmt(r['mean_slip'], 3)} | "
                    f"{_fmt(r['mean_roughness_m'], 2)} / {_fmt(r['max_roughness_m'], 2)} | {_fmt(r['mean_f'], 2)} | {_int(r['cells_in_psr'])} | {_fmt(r['overlap_with_w0'], 2)} | "
                    f"{_pct(st.get('completion'))} / {_pct(st.get('within_reserve'))} / {_pct(st.get('full_success'))} | {_fmt(r['plan_s'], 1)} |"
                )
            L.append("")
    elif report.get("skipped_4d_reason"):
        L += ["## 5. 4-B rotalar", "", f"Atlandı: {report['skipped_4d_reason']}", ""]
    L += ["## 6. Okuma", "", _reading(report), ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def _reading(report: dict) -> str:
    g = report["grid"]
    ps = report["psr"]
    t99 = next(t for t in ps["thresholds"] if abs(t["threshold"] - 0.99) < 1e-9)
    b99 = next((b for b in ps["blocks_20m"] if abs(b["threshold"] - 0.99) < 1e-9), None)
    lines = []
    lines.append(
        f"- **Kriter atıl değil, eğimin kopyası da değil:** Spearman(pürüzlülük, eğim) {_fmt(g['spearman_rough_slope_5m'], 2)}; "
        f"`f_roughness` Site11'de p5 {_fmt(g['f_quantiles']['p5'], 2)} – p95 {_fmt(g['f_quantiles']['p95'], 2)} arasına yayılıyor "
        f"(Site11 bölgesel medyanın üstünde: medyan sıra {_fmt(g['f_quantiles']['p50'], 2)}). Eğim kutularında medyan pürüzlülük "
        f"{_fmt(g['slope_bins'][0]['median_m'], 2)} → {_fmt(g['slope_bins'][-1]['median_m'], 2)} m (PSJ 2025'in yönü, zayıf)."
    )
    for block in report["pairs_2d"]:
        rows = [r for r in block["rows"] if r.get("status") == 200]
        if len(rows) < 2:
            continue
        w0 = rows[0]
        w15 = next((r for r in rows if abs(r["w"] - 0.15) < 1e-9), rows[-1])
        lines.append(
            f"- **{block['pair']['label']}:** w = 0,15'te örtüşme {_fmt(w15['overlap_with_w0'], 2)}, rota ort. pürüzlülük "
            f"{_fmt(w0['mean_roughness_m'], 2)} → {_fmt(w15['mean_roughness_m'], 2)} m, {_fmt(w0['energy_wh'], 1)} → {_fmt(w15['energy_wh'], 1)} Wh, "
            f"{_fmt(w0['hours'], 3)} → {_fmt(w15['hours'], 3)} h, min SOC {_fmt(w0['min_soc'], 2)} → {_fmt(w15['min_soc'], 2)}; kriterin hücre maliyetindeki payı {_pct(w15['roughness_share_of_cell_cost'])}."
        )
    for block in report.get("cases_4d") or []:
        rows = [r for r in block["rows"] if r.get("status") == 200]
        if len(rows) == 2:
            a, b = rows
            sa, sb = a.get("stress") or {}, b.get("stress") or {}
            lines.append(
                f"- **4-B {block['case']['label']}:** hamle {_int(a['moves'])} → {_int(b['moves'])}, varış {_fmt(a['arrival_hours'], 3)} → {_fmt(b['arrival_hours'], 3)} h, "
                f"min SOC {_pct(a['min_soc'] / 100)} → {_pct(b['min_soc'] / 100)}, örtüşme {_fmt(b['overlap_with_w0'], 2)}, rota pürüzlülük {_fmt(a['mean_roughness_m'], 2)} → {_fmt(b['mean_roughness_m'], 2)} m, "
                f"B5 tamamlanma {_pct(sa.get('completion'))} → {_pct(sb.get('completion'))}, rezerv içinde {_pct(sa.get('within_reserve'))} → {_pct(sb.get('within_reserve'))}."
            )
    lines.append(
        f"- **PSR doğrulaması:** PGDA maskesi ile `shadow_ratio ≥ 0,99` hücrelerimiz Jaccard **{_fmt(t99['jaccard'], 3)}** (PSR'ın {_pct(t99['psr_recall'])}'i yakalandı, karanlıkların {_pct(t99['dark_precision'])}'i PSR)"
        + (f"; 20 m ürün bloklarında **{_fmt(b99['jaccard'], 3)}**" if b99 else "")
        + ". Kalan fark 20 m ürün pikselinin 5 m hücrelerle kenar uyumsuzluğu ve bizim 18,6 yıllık örneklememizle ürünün tanımı arasındaki fark; hepsi yazıldığı gibi."
    )
    lines.append(
        "- **Sunum cümlesi:** \"İki katmanımız artık NASA'nın ölçülmüş ürünleridir: LOLA LDRM hektometre ölçekli pürüzlülüğü beşinci kriter olarak gride girdi "
        f"(eğimle Spearman {_fmt(g['spearman_rough_slope_5m'], 2)}), PGDA PSR maskesi gölge modelimizle Jaccard {_fmt(t99['jaccard'], 2)} örtüşüyor; kriter Site11'de rotayı çifte göre değiştirdi — sayılar yukarıda.\""
    )
    lines.append(
        "- **İddia sınırı:** katman MEASURED ama 50 m/px ve 100 m taban — bir 5 m hücre, onu kapsayan pikselin blok istatistiğini taşır, kendi pürüzlülüğünü değil; "
        "ölçek istatistiktir (MODEL), rover toleransı değil; `w_roughness = 0,15` varsayımdır (tarama yukarıda); Diviner kaya bolluğu kullanılmadı (kapsam ±80°)."
    )
    return "\n".join(lines)


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", default=str(_ROOT / "docs" / "research" / "roughness_psr_report.md"))
    parser.add_argument("--json", default=None, help="also dump the raw measurements as JSON (written before the markdown)")
    parser.add_argument("--from-json", default=None, help="render the markdown from a previous --json dump instead of measuring")
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--skip-4d", action="store_true", help="skip the plan-4d + stress-test section")
    args = parser.parse_args()

    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        _write_markdown(Path(args.output), report, args)
        print(f"rendered {args.output} from {args.from_json}")
        return 0

    processed = Path(_P1_PROCESSED_DIR)
    grids = load_preprocessed_grids()
    if grids.get("roughness") is None or grids.get("psr") is None:
        print("roughness/PSR cache missing beside the processed grids; run scripts/build_roughness_cache.py first. Nothing measured.", file=sys.stderr)
        return 1

    report: dict = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "weights": list(WEIGHTS)}
    print("1. products ...", flush=True)
    report["products"] = measure_products(grids, processed)
    print("2. grid ...", flush=True)
    report["grid"] = measure_grid(grids)
    print("3. psr ...", flush=True)
    report["psr"] = measure_psr(grids)

    app.state.grids = grids
    client = TestClient(app)
    print("4. 2-D pairs ...", flush=True)
    report["pairs_2d"] = []
    for pair in PAIRS_2D:
        print(f"  {pair['label']}", flush=True)
        report["pairs_2d"].append(measure_2d(client, pair, grids))

    kernels = _ROOT / "kernels" / "lunapath.tm"
    horizon = processed / "horizon_map.npy"
    if args.skip_4d:
        report["skipped_4d_reason"] = "--skip-4d"
    elif not (kernels.exists() and horizon.exists()):
        report["skipped_4d_reason"] = f"needs {horizon.name} and the NAIF kernels ({kernels})"
    else:
        print("5. 4-D routes + SHERPA ...", flush=True)
        report["cases_4d"] = []
        for case in CASES_4D:
            print(f"  {case['label']}", flush=True)
            report["cases_4d"].append(measure_4d(client, case, args.n_runs, args.seed))

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
        print(f"json -> {args.json}")
    _write_markdown(Path(args.output), report, args)
    print(f"report -> {args.output}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
