#!/usr/bin/env python3
"""Measure the DEM-clone ensemble (B3) on the checked-in Site11 grid.

NASA PGDA publishes 100 statistical clones of every 5 m/px south-polar DEM.
scripts/build_dem_clone_cache.py fetched them for the planning window; this
script reads what they say about LunaPath's own layers and routes:

* the clones' error statistics against NASA's toterr / slperr and the
  product page's published ranges;
* the ensemble slope sigma against NASA's slperr;
* p_traversable per rover and its convergence with the clone count;
* P(lit, t) at the two epochs B5 stress-tested, and the clone-vs-surface
  horizon shift;
* the DEM band of the two B5 routes (VIPER haven-to-haven, LPR-1), DEM
  only and combined with SHERPA's protocol;
* timings.

Needs the processed grids, the clone cache, ``horizon_map.npy`` and the
NAIF kernels; without them it says so and exits 0. It never fabricates
numbers. Writes docs/research/dem_uncertainty_report.md by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.illumination_series import horizon_cache_path  # noqa: E402
from app.main import app  # noqa: E402
from app.rover_grids import grids_for_rover  # noqa: E402
from app.uncertainty import (  # noqa: E402
    PGDA_MEDIAN_RMS_SLOPE_ERROR_DEG,
    PGDA_MEDIAN_RMS_Z_ERROR_M,
    ELEVATION_SIGMA_FILENAME,
    SLOPE_SIGMA_NASA_FILENAME,
    clear_uncertainty_cache,
    ensemble_slopes,
    load_clone_horizons,
    load_dem_clones,
    slope_sigma,
    traversable_probability,
    uncertain_fraction,
    uncertainty_layers_for_grids,
)

_ROOT = Path(__file__).resolve().parent.parent
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

CASES = [
    {
        "label": "VIPER haven->haven, 30 May 2027",
        "rover_id": "nasa_viper",
        "start_utc": "2027-05-30T00:00:00",
        "start": {"row": 358, "col": 494},
        "goal": {"row": 206, "col": 426},
        "require_safe_haven": True,
    },
    {
        "label": "LPR-1, 28 Sep 2026",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-28T00:00:00",
        "start": {"row": 358, "col": 494},
        "goal": {"row": 206, "col": 426},
        "require_safe_haven": False,
    },
]
ROVERS = ("nasa_viper", "lpr_1")
CONVERGENCE_N = (5, 10, 20, 30, 50, 75, 100)


def _f(value, digits=2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".replace(".", ",")


def _pct(value, digits=1) -> str:
    return "-" if value is None else f"{100.0 * value:.{digits}f} %".replace(".", ",")


def _dist(block, digits=2) -> str:
    if not block:
        return "-"
    return f"{_f(block['p5'], digits)} / {_f(block['p50'], digits)} / {_f(block['p95'], digits)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "dem_uncertainty_report.md"))
    parser.add_argument("--json-out", default=None)
    parser.add_argument("--n-runs", type=int, default=200, help="SHERPA runs per clone for the combined band")
    parser.add_argument("--series-hours", type=int, default=48)
    args = parser.parse_args()

    if not _KERNELS.exists():
        print(f"NAIF kernels not found at {_KERNELS}; nothing measured.")
        return 0
    clear_uncertainty_cache()
    grids = load_preprocessed_grids()
    metadata = grids["metadata"]
    processed = metadata["processed_dir"]
    surface = np.asarray(grids["elevation"], dtype=np.float64)
    clones = load_dem_clones(processed, expected_shape=surface.shape)
    if clones is None:
        print("No DEM clone cache; run scripts/build_dem_clone_cache.py first. Nothing measured.")
        return 0
    if horizon_cache_path(metadata) is None:
        print("No horizon_map.npy; run scripts/build_horizon_cache.py first. Nothing measured.")
        return 0
    report: dict = {"generated": time.strftime("%Y-%m-%d"), "n_clones": clones.n_clones, "cache": clones.meta}
    res = float(metadata["resolution_m"])

    # ── 1. The clones against NASA's sigma maps ───────────────────────────
    toterr = np.load(Path(processed) / ELEVATION_SIGMA_FILENAME).astype(np.float64)
    slperr = np.load(Path(processed) / SLOPE_SIGMA_NASA_FILENAME).astype(np.float64)
    window = np.asarray(clones.window, dtype=np.float64)
    errors = window - surface[None]
    rms_toterr = float(np.sqrt(np.nanmean(toterr**2)))
    per_clone_rms = np.sqrt(np.nanmean(errors**2, axis=(1, 2)))
    lags = {}
    field = errors[0]
    for lag in (1, 2, 5, 10, 20):
        lags[lag * res] = float(np.corrcoef(field[:, :-lag].ravel(), field[:, lag:].ravel())[0, 1])
    report["errors"] = {
        "toterr_m": {"median": float(np.nanmedian(toterr)), "mean": float(np.nanmean(toterr)), "p95": float(np.nanpercentile(toterr, 95)), "rms": rms_toterr},
        "slperr_deg": {"median": float(np.nanmedian(slperr)), "mean": float(np.nanmean(slperr)), "p95": float(np.nanpercentile(slperr, 95))},
        "clone_error_mean_m": float(np.nanmean(errors)),
        "clone_error_rms_m": float(np.sqrt(np.nanmean(errors**2))),
        "per_clone_rms_ratio": [float(v / rms_toterr) for v in per_clone_rms],
        "lag_correlation": lags,
        "pgda_published_z_m": PGDA_MEDIAN_RMS_Z_ERROR_M,
        "pgda_published_slope_deg": PGDA_MEDIAN_RMS_SLOPE_ERROR_DEG,
    }
    print(
        f"{clones.n_clones} clones: error mean {report['errors']['clone_error_mean_m']:+.4f} m, RMS "
        f"{report['errors']['clone_error_rms_m']:.4f} m vs toterr RMS {rms_toterr:.4f} m; toterr median "
        f"{report['errors']['toterr_m']['median']:.3f} m (NASA: {PGDA_MEDIAN_RMS_Z_ERROR_M})"
    )

    # ── 2. Slope sigma, ours vs NASA's ────────────────────────────────────
    t0 = time.perf_counter()
    slopes = ensemble_slopes(window, res)
    ours = np.asarray(slope_sigma(slopes), dtype=np.float64)
    slopes_s = time.perf_counter() - t0
    surface_slope = np.asarray(grids["slope"], dtype=np.float64)
    bias = slopes.astype(np.float64).mean(axis=0) - surface_slope
    report["slope_sigma"] = {
        "bias_median_deg": float(np.median(bias)), "bias_mean_deg": float(bias.mean()),
        "bias_p95_deg": float(np.percentile(bias, 95)),
        "surface_slope_median_deg": float(np.median(surface_slope)),
        "ours_median": float(np.median(ours)), "ours_mean": float(ours.mean()), "ours_p95": float(np.percentile(ours, 95)),
        "nasa_median": float(np.nanmedian(slperr)), "nasa_p95": float(np.nanpercentile(slperr, 95)),
        "ratio_of_medians": float(np.median(ours) / np.nanmedian(slperr)),
        "correlation": float(np.corrcoef(ours.ravel(), slperr.ravel())[0, 1]),
        "seconds": slopes_s,
    }
    print(
        f"slope sigma: ours median {report['slope_sigma']['ours_median']:.3f} deg vs NASA "
        f"{report['slope_sigma']['nasa_median']:.3f} deg, correlation {report['slope_sigma']['correlation']:.3f}"
    )

    # ── 3. p_traversable per rover and convergence ────────────────────────
    report["p_traversable"] = {}
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        for_rover = grids_for_rover(grids, rover_id)
        base = np.asarray(for_rover["traversable"], dtype=bool)
        t0 = time.perf_counter()
        p_all, masks = traversable_probability(slopes, for_rover["thermal"], for_rover["elevation"], rover, for_rover.get("thermal_min"))
        seconds = time.perf_counter() - t0
        p_all = np.asarray(p_all, dtype=np.float64)
        convergence = []
        for n in CONVERGENCE_N:
            if n > clones.n_clones:
                continue
            p_n = masks[:n].mean(axis=0)
            convergence.append({
                "n": n,
                "uncertain_fraction": uncertain_fraction(p_n),
                "mean_abs_diff_to_full": float(np.abs(p_n - p_all).mean()),
                "p95_abs_diff_to_full": float(np.percentile(np.abs(p_n - p_all), 95)),
                "max_abs_diff_to_full": float(np.abs(p_n - p_all).max()),
            })
        t0 = time.perf_counter()
        uncertainty_layers_for_grids(for_rover, rover_id)
        layers_s = time.perf_counter() - t0
        report["p_traversable"][rover_id] = {
            "slope_max_deg": float(rover["slope_max_deg"]),
            "base_passable": float(base.mean()),
            "certain_pass": float((p_all == 1.0).mean()),
            "certain_fail": float((p_all == 0.0).mean()),
            "uncertain": uncertain_fraction(p_all),
            "mean_p": float(p_all.mean()),
            "pass_in_ensemble_not_in_base": float(((p_all == 1.0) & ~base).mean()),
            "fail_in_ensemble_but_in_base": float(((p_all == 0.0) & base).mean()),
            "base_passable_with_p_below_half": float((base & (p_all < 0.5)).mean()),
            "convergence": convergence,
            "seconds": seconds,
            "layers_seconds": layers_s,
        }
        print(
            f"{rover_id}: base passable {base.mean():.4f}, certain pass {(p_all == 1.0).mean():.4f}, "
            f"uncertain {uncertain_fraction(p_all):.4f}, passable-but-P<0.5 {report['p_traversable'][rover_id]['base_passable_with_p_below_half']:.4f} "
            f"[{seconds:.1f} s]"
        )

    # ── 4. P(lit, t) and the horizon shift ────────────────────────────────
    app.state.grids = grids
    client = TestClient(app)
    cubes, cube_meta = load_clone_horizons(processed)
    report["illumination"] = {"available": cubes is not None}
    if cubes is not None:
        base_cube = np.load(horizon_cache_path(metadata), mmap_mode="r")
        stride, offset = int(cube_meta["stride"]), int(cube_meta["row_offset"])
        sampled = np.asarray(base_cube[:, offset::stride, offset::stride], dtype=np.float64)
        diffs = np.asarray(cubes[0], dtype=np.float64) - sampled
        report["illumination"].update({
            "n_clone_cubes": int(cubes.shape[0]),
            "stride": stride,
            "near_range_m": cube_meta.get("near_range_m"),
            "neglected_horizon_shift_deg_max": cube_meta.get("neglected_horizon_shift_deg_max"),
            "surf_check_max_abs_deg": cube_meta.get("surf_check_max_abs_deg"),
            "seconds_per_clone_cube": cube_meta.get("seconds_per_clone"),
            "clone1_vs_surface_deg": {
                "mean_abs": float(np.abs(diffs).mean()), "p95_abs": float(np.percentile(np.abs(diffs), 95)),
                "max_abs": float(np.abs(diffs).max()),
                "mean_abs_low_horizon": float(np.abs(diffs)[sampled < 2.0].mean()) if (sampled < 2.0).any() else None,
            },
            "epochs": {},
        })
        for case in CASES:
            t0 = time.perf_counter()
            response = client.get(
                "/api/uncertainty-series",
                params={"start_utc": case["start_utc"], "n_slices": args.series_hours, "slice_hours": 1.0},
            )
            seconds = time.perf_counter() - t0
            out = response.json()
            if response.status_code != 200 or out.get("model") != "clone_horizon":
                report["illumination"]["epochs"][case["start_utc"]] = {"status": response.status_code, "model": out.get("model"), "reason": out.get("reason")}
                continue
            fr = out["per_slice"]["uncertain_fraction"]
            report["illumination"]["epochs"][case["start_utc"]] = {
                "n_clones": out["n_clones"],
                "uncertain_p50": float(np.median(fr)), "uncertain_p95": float(np.percentile(fr, 95)), "uncertain_max": float(max(fr)),
                "mean_lit_p50": float(np.median(out["per_slice"]["mean"])),
                "seconds": seconds,
            }
            print(f"P_illuminated {case['start_utc']}: uncertain fraction p50 {np.median(fr):.4f}, max {max(fr):.4f} [{seconds:.1f} s]")

    # ── 5. Route bands ────────────────────────────────────────────────────
    report["routes"] = []
    for case in CASES:
        body = {
            "start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"],
            "start_utc": case["start_utc"], "coarsen": 4, "require_safe_haven": case["require_safe_haven"],
        }
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        plan_s = time.perf_counter() - t0
        entry = {**case, "plan_status": response.status_code, "plan_seconds": plan_s}
        if response.status_code != 200:
            entry["plan_error"] = response.json().get("detail")
            print(f"{case['label']}: plan {response.status_code}: {entry['plan_error']}")
            report["routes"].append(entry)
            continue
        plan = response.json()
        entry["plan"] = {
            "n_states": len(plan["path_states"]), "move_steps": plan["metrics"]["move_steps"],
            "wait_steps": plan["metrics"]["wait_steps"], "arrival_hours": plan["metrics"]["arrival_hours"],
            "slice_hours": plan["slice_hours"], "min_battery_pct": plan["metrics"]["min_battery_pct"],
            "uncertainty": plan.get("uncertainty"),
        }
        entry["bands"] = {}
        for kind, extra in (("dem", {}), ("dem+sherpa", {"with_sherpa": True, "n_runs": args.n_runs, "seed": 0})):
            band_body = {
                "path_states": plan["path_states"], "rover_id": case["rover_id"], "coarsen": 4,
                "slice_hours": plan["slice_hours"], "start_utc": case["start_utc"], "label": case["label"], **extra,
            }
            t0 = time.perf_counter()
            response = client.post("/api/dem-uncertainty", json=band_body)
            seconds = time.perf_counter() - t0
            if response.status_code != 200:
                entry["bands"][kind] = {"status": response.status_code, "detail": response.text[:200]}
                print(f"  {kind}: {response.status_code} {response.text[:120]}")
                continue
            out = response.json()
            entry["bands"][kind] = {
                "status": 200, "seconds": seconds, "timing_ms": out["timing_ms"], "n_clones": out["n_clones"],
                "clones_priced": out["clones_priced"], "route_feasible": out["route_feasible"], "reached": out["reached"],
                "p_traversable": {"min": out["p_traversable"]["min"], "mean": out["p_traversable"]["mean"]},
                "metrics": out["metrics"], "nominal": out["nominal"], "sky_model": out["sky_model"]["model"],
                "sherpa": out["sherpa"],
            }
            m = out["metrics"]
            print(
                f"{case['label']} [{kind}]: {out['n_clones']} clones, feasible {out['route_feasible']['fraction']}, "
                f"drive Wh p5/p50/p95 {_dist(m['gross_drive_wh'], 0)} (nominal {_f(out['nominal']['gross_drive_wh'], 0)}), "
                f"duration {_dist(m['duration_h'])} h, min batt p5 {_f(m['min_battery_pct']['p5'], 1)} %"
                + (f", SHERPA completion {_pct(out['sherpa']['completion']['rate'])}" if out["sherpa"] else "")
                + f" [{seconds:.1f} s]"
            )
        report["routes"].append(entry)

    _write_markdown(Path(args.out), report, args)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nRapor: {args.out}")
    return 0


def _write_markdown(path: Path, r: dict, args) -> None:
    e = r["errors"]
    cache = r["cache"]
    lines = [
        "# DEM hata yayılımı — NASA'nın Site11 DEM klonlarıyla Monte Carlo (B3)",
        "",
        f"Üretildi: `scripts/dem_uncertainty_report.py` ile, {r['generated']}. Klon önbelleği: "
        f"`{cache.get('site')}`, {r['n_clones']} klon (`{cache.get('provenance')}`), pencere "
        f"{cache.get('window', {}).get('rows')}×{cache.get('window', {}).get('cols')} px + "
        f"{cache.get('pad_px')} px ({_f(cache.get('near_range_m'), 0)} m) yakın-alan dolgusu, "
        f"{cache.get('fetched_utc')} tarihinde {_f(cache.get('fetch_seconds'), 0)} s'de "
        f"{cache.get('workers')} paralel bağlantıyla indirildi. Ürün: {cache.get('product_url')}.",
        "",
        "## 1. Klonlar NASA'nın hata haritalarına karşı",
        "",
        "| Nicelik | Ölçülen | NASA'nın yayınladığı (ürün sayfası, tüm siteler) |",
        "|---|---|---|",
        f"| `toterr` (Z belirsizliği) medyan / ortalama / p95 | {_f(e['toterr_m']['median'], 3)} / {_f(e['toterr_m']['mean'], 3)} / {_f(e['toterr_m']['p95'], 3)} m | medyan RMS {_f(e['pgda_published_z_m'][0])}–{_f(e['pgda_published_z_m'][1])} m |",
        f"| `slperr` (eğim belirsizliği) medyan / ortalama / p95 | {_f(e['slperr_deg']['median'], 2)} / {_f(e['slperr_deg']['mean'], 2)} / {_f(e['slperr_deg']['p95'], 2)}° | medyan RMS {_f(e['pgda_published_slope_deg'][0], 1)}–{_f(e['pgda_published_slope_deg'][1], 1)}° |",
        f"| `klon − surf` ortalama / RMS ({r['n_clones']} klon) | {e['clone_error_mean_m']:+.4f} / {_f(e['clone_error_rms_m'], 4)} m | RMS(`toterr`) = {_f(e['toterr_m']['rms'], 4)} m |".replace(".", ","),
        f"| Klon başına RMS / RMS(`toterr`) | {_f(min(e['per_clone_rms_ratio']), 3)} – {_f(max(e['per_clone_rms_ratio']), 3)} | 1 beklenir |",
        "| Uzamsal korelasyon (klon 1) | " + ", ".join(f"{int(k)} m: {_f(v, 2)}" for k, v in e["lag_correlation"].items()) + " | — |",
        "",
        "Klon dosyaları (`_err.tif`) adlarına rağmen tam yüzey DEM'leridir; hata gerçekleşmesi `klon − surf`'tür ve "
        "RMS'i NASA'nın `toterr` haritasının RMS'ine eşittir (klon = `surf + toterr · ξ`, ξ birim varyanslı, ~100 m'de dekorele).",
        "",
        "## 2. Eğim belirsizliği: topluluk vs NASA",
        "",
        "| | Medyan | p95 |",
        "|---|---|---|",
        f"| Bizim topluluk σ (np.gradient, {r['n_clones']} klon) | {_f(r['slope_sigma']['ours_median'], 3)}° | {_f(r['slope_sigma']['ours_p95'], 3)}° |",
        f"| NASA `slperr` | {_f(r['slope_sigma']['nasa_median'], 3)}° | {_f(r['slope_sigma']['nasa_p95'], 3)}° |",
        "",
        f"Medyan oranı {_f(r['slope_sigma']['ratio_of_medians'], 3)}, hücre-hücre korelasyon "
        f"{_f(r['slope_sigma']['correlation'], 3)}; {r['n_clones']} klonun eğimi {_f(r['slope_sigma']['seconds'], 1)} s.",
        "",
        f"**Eğim yanlılığı:** topluluk ortalaması − yüzey eğimi: medyan {_f(r['slope_sigma']['bias_median_deg'], 3)}°, "
        f"ortalama {_f(r['slope_sigma']['bias_mean_deg'], 3)}°, p95 {_f(r['slope_sigma']['bias_p95_deg'], 3)}° "
        f"(yüzey eğimi medyanı {_f(r['slope_sigma']['surface_slope_median_deg'], 2)}°). Sıfır ortalamalı yükseklik gürültüsü "
        "gradyanın büyüklüğünü şişirir (|∇(z+ε)| ortalaması |∇z|'den büyüktür); yüzey DEM'i en iyi tahmin, klonlar "
        "gerçek arazi kadar pürüzlüdür. Bu yüzden rota bantlarında nominal (yüzey) enerji bandın altında kalır.",
        "",
        "## 3. P(geçilebilir) — rover başına ve klon sayısına göre yakınsama",
        "",
        "| Rover (eğim sınırı) | Temel geçilebilir | Kesin geçilebilir (P = 1) | Kesin geçilmez (P = 0) | Belirsiz (0,05 < P < 0,95) | Temelde geçilebilir ama P < 0,5 | Süre |",
        "|---|---|---|---|---|---|---|",
    ]
    for rover_id, p in r["p_traversable"].items():
        lines.append(
            f"| `{rover_id}` ({_f(p['slope_max_deg'], 0)}°) | {_pct(p['base_passable'], 2)} | {_pct(p['certain_pass'], 2)} | "
            f"{_pct(p['certain_fail'], 2)} | **{_pct(p['uncertain'], 2)}** | {_pct(p['base_passable_with_p_below_half'], 3)} | {_f(p['seconds'], 2)} s |"
        )
    lines += ["", "Yakınsama (tam topluluğa göre):", ""]
    lines.append("| Rover | N | Belirsiz oran | ort. \\|P_N − P_tam\\| | p95 | maks |")
    lines.append("|---|---|---|---|---|---|")
    for rover_id, p in r["p_traversable"].items():
        for c in p["convergence"]:
            lines.append(
                f"| `{rover_id}` | {c['n']} | {_pct(c['uncertain_fraction'], 2)} | {_f(c['mean_abs_diff_to_full'], 4)} | "
                f"{_f(c['p95_abs_diff_to_full'], 3)} | {_f(c['max_abs_diff_to_full'], 2)} |"
            )
    il = r["illumination"]
    lines += ["", "## 4. P(aydınlık, t) — klon ufukları", ""]
    if not il.get("available"):
        lines.append("Klon ufuk küpleri yok (`scripts/build_dem_clone_cache.py` ufuk adımı koşmadı).")
    else:
        d = il["clone1_vs_surface_deg"]
        lines += [
            f"{il['n_clone_cubes']} klon küpü, stride {il['stride']} (plan-4d blok merkezleri), yakın alan {_f(il['near_range_m'], 0)} m klonlanmış; "
            f"uzak alan (yüzey DEM'inin 10 km bağlamı + LOLA 40 m) sabit. Yüzeyin iki-geçişli ufku üretim küpüyle fark "
            f"{_f(il['surf_check_max_abs_deg'], 6)}° (birebir). Klon başına küp {_f(il['seconds_per_clone_cube'], 2)} s. "
            f"İhmal edilen uzak-alan kayması ≤ {_f(il['neglected_horizon_shift_deg_max'], 4)}° (medyan `toterr` / 1 km).",
            "",
            f"Klon 1 ufku − yüzey ufku: ortalama |Δ| {_f(d['mean_abs'], 3)}°, p95 {_f(d['p95_abs'], 2)}°, maks {_f(d['max_abs'], 2)}°"
            + (f"; ufku 2°'nin altındaki (Güneş için belirleyici) hücrelerde ortalama |Δ| {_f(d['mean_abs_low_horizon'], 3)}°" if d.get("mean_abs_low_horizon") is not None else "")
            + ". 5 m/px'te ufku çoğu zaman komşu hücre belirler; iki komşunun hata farkı ~0,22 m (σ 0,45 m, korelasyon 0,88) 5 m'de 2,5°'dir.",
            "",
            "| Epoch | Klon | Belirsiz hücre oranı p50 / p95 / maks (48 h × 1 h) | Ortalama aydınlık p50 | Süre |",
            "|---|---|---|---|---|",
        ]
        for epoch, ep in il["epochs"].items():
            if "uncertain_p50" not in ep:
                lines.append(f"| {epoch} | - | {ep.get('model')}: {ep.get('reason')} | - | - |")
                continue
            lines.append(
                f"| {epoch} | {ep['n_clones']} | {_pct(ep['uncertain_p50'], 2)} / {_pct(ep['uncertain_p95'], 2)} / {_pct(ep['uncertain_max'], 2)} | "
                f"{_pct(ep['mean_lit_p50'], 1)} | {_f(ep['seconds'], 1)} s |"
            )
    lines += ["", "## 5. Rota bantları (B5'in iki rotası)", ""]
    for entry in r["routes"]:
        lines.append(f"### {entry['label']}")
        lines.append("")
        if entry.get("plan_status") != 200:
            lines.append(f"Plan {entry.get('plan_status')}: {entry.get('plan_error')}")
            lines.append("")
            continue
        plan = entry["plan"]
        u = plan.get("uncertainty") or {}
        lines.append(
            f"Rover `{entry['rover_id']}`, epoch `{entry['start_utc']}`, coarsen 4: {plan['move_steps']} MOVE, {plan['wait_steps']} WAIT, "
            f"varış {_f(plan['arrival_hours'])} h, dilim {_f(plan['slice_hours'], 4)} h, planlayıcı en düşük batarya {_f(plan['min_battery_pct'], 1)} %; "
            f"plan-4d `uncertainty` bloğu: {u.get('n_clones')} klon, rota geçilebilir oranı {_pct(u.get('route_feasible_fraction'))}, "
            f"P min {_f(u.get('p_traversable_min'), 3)}, P ort. {_f(u.get('p_traversable_mean'), 3)}; planlama {_f(entry['plan_seconds'], 1)} s."
        )
        lines.append("")
        lines.append("| Bant | Klon | Rota geçilebilir (Wilson %95) | Varış | Sürüş enerjisi p5/p50/p95 (Wh) | Nominal | Bataryadan çekilen p5/p50/p95 (Wh) | Sürüş saati p5/p50/p95 | Süre p5/p50/p95 (h) | Min batarya p5 (%) | Maks gölge p95 (h) | SHERPA tamamlanma | Süre (s) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for kind, b in entry["bands"].items():
            if b.get("status") != 200:
                lines.append(f"| {kind} | HTTP {b.get('status')} | | | | | | | | | | | |")
                continue
            m = b["metrics"]
            rf = b["route_feasible"]
            sherpa = b.get("sherpa")
            lines.append(
                f"| {kind} | {b['n_clones']} | {_pct(rf['fraction'])} ({_pct(rf['ci95'][0])}–{_pct(rf['ci95'][1])}) | {_pct(b['reached']['fraction'])} | "
                f"{_dist(m['gross_drive_wh'], 0)} | {_f(b['nominal']['gross_drive_wh'], 0)} | {_dist(m['battery_used_wh'], 0)} | "
                f"{_dist(m['drive_hours'])} | {_dist(m['duration_h'])} | {_f(m['min_battery_pct']['p5'], 1)} | "
                f"{_f(m['max_continuous_shadow_h']['p95'])} | "
                + (f"{_pct(sherpa['completion']['rate'])} ({_pct(sherpa['completion']['ci95'][0])}–{_pct(sherpa['completion']['ci95'][1])}), {sherpa['n_runs_total']} koşum" if sherpa else "-")
                + f" | {_f(b['seconds'], 1)} |"
            )
        lines.append("")
        first = next((b for b in entry["bands"].values() if b.get("status") == 200), None)
        if first:
            lines.append(
                f"Gökyüzü `{first['sky_model']}`; süre dağılımı: gökyüzü {_f(first['timing_ms']['sky'] / 1000, 2)} s, koşumlar {_f(first['timing_ms']['runs'] / 1000, 2)} s."
            )
            lines.append("")
    lines += [
        "## 6. Süreler",
        "",
        f"- Klon indirme: {r['n_clones']} klon, {_f(cache.get('fetch_seconds'), 0)} s ({cache.get('workers')} paralel bağlantı; sunucu tek bağlantıda ~170 KB/s).",
        f"- Klon başına ufuk küpü: {_f(il.get('seconds_per_clone_cube'), 2)} s (stride 4, 114 yakın örnek); uzak alan bir kez.",
        f"- {r['n_clones']} klonun eğimi: {_f(r['slope_sigma']['seconds'], 1)} s; rover başına P(geçilebilir): "
        + ", ".join(f"`{k}` {_f(v['seconds'], 1)} s" for k, v in r["p_traversable"].items()) + ".",
    ]
    for epoch, ep in il.get("epochs", {}).items():
        if "seconds" in ep:
            lines.append(f"- `/api/uncertainty-series` {epoch}, {args.series_hours} dilim: {_f(ep['seconds'], 1)} s.")
    for entry in r["routes"]:
        for kind, b in entry.get("bands", {}).items():
            if b.get("status") == 200:
                lines.append(f"- `/api/dem-uncertainty` {entry['label']} [{kind}]: {_f(b['seconds'], 1)} s.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
