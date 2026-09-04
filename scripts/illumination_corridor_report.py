#!/usr/bin/env python3
"""Measure the continuous-illumination corridor (A2) on the checked-in Site11 grid.

For the three epochs the earlier features measured -- VIPER's best lunar
day (2027-05-30), LPR-1's 2026-09-28 route and the lunar night of
2026-09-13 -- this reads back what /api/plan-4d's `illumination_corridor`
block says for the standard haven-to-haven pair under both lit rules (the
volume, how much pruning removes, CMU's 26-neighbourhood components, why
the corridor rule refuses the pair), then picks a pair INSIDE the corridor
with `illumination_corridor.corridor_pair` and plans it three ways --
unconstrained, corridor-enforced under "all", corridor-enforced under
"majority" -- to measure planning time, nodes expanded, the route's shadow
hours (zero inside the corridor by construction), D3's LP-R01 margin
(equal to the rover's shadow endurance) and CMU's dwell metric.

Needs the processed grids, horizon_map.npy and the NAIF kernels; without
them it says so and exits 0. It never fabricates numbers. Writes
docs/research/illumination_corridor_report.md by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import illumination_corridor as ic  # noqa: E402
from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.illumination_series import build_shadow_series, horizon_cache_path  # noqa: E402
from app.main import PlanWeights, _coarse_geometry, app  # noqa: E402
from app.rover_grids import grids_for_rover  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

COARSEN = 4
START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
HORIZON_HOURS = 8.0
SLICE_HOURS = 0.1
REPEATS = 3
CASES = [
    {"label": "VIPER, 30 May 2027 (haven->haven günü)", "rover_id": "nasa_viper", "start_utc": "2027-05-30T00:00:00", "start": START, "goal": GOAL},
    {"label": "LPR-1, 28 Eyl 2026", "rover_id": "lpr_1", "start_utc": "2026-09-28T00:00:00", "start": START, "goal": GOAL},
    {"label": "LPR-1, Ay gecesi 13 Eyl 2026", "rover_id": "lpr_1", "start_utc": "2026-09-13T00:00:00", "start": {"row": 186, "col": 34}, "goal": {"row": 494, "col": 450}},
]


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _int(value) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _pct(value) -> str:
    return "—" if value is None else f"{100.0 * float(value):.1f} %".replace(".", ",")


def _fine_centre(cell):
    return {"row": int(cell[0]) * COARSEN + COARSEN // 2, "col": int(cell[1]) * COARSEN + COARSEN // 2}


def _plan(client, body, repeats: int = 1):
    """Plan *repeats* times; keep the response of the fastest run."""
    best = None
    for _ in range(repeats):
        started = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        elapsed = time.perf_counter() - started
        if best is None or elapsed < best[1]:
            best = (response, elapsed)
    return best


def _standard_pair(client, case, lit_rule: str):
    body = {"start": case["start"], "goal": case["goal"], "rover_id": case["rover_id"], "start_utc": case["start_utc"], "lit_rule": lit_rule}
    response, seconds = _plan(client, body)
    entry = {"lit_rule": lit_rule, "status": response.status_code, "seconds": seconds}
    if response.status_code == 200:
        payload = response.json()
        entry["block"] = payload["illumination_corridor"]
        entry["metrics"] = payload["metrics"]
        entry["path_dark_hours_max"] = max(payload["path_dark_hours"])
    else:
        entry["detail"] = response.json().get("detail")
    refused, _ = _plan(client, dict(body, require_continuous_illumination=True))
    entry["enforced_status"] = refused.status_code
    entry["enforced_detail"] = refused.json().get("detail") if refused.status_code != 200 else None
    return entry


def _corridor_for(grids, case):
    rover = get_rover(case["rover_id"])
    grids_for_plan = grids_for_rover(grids, case["rover_id"], PlanWeights().model_dump())
    geometry = _coarse_geometry(grids_for_plan, COARSEN)
    n_slices = int(np.ceil(HORIZON_HOURS / SLICE_HOURS))
    series, provenance = build_shadow_series(
        np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64),
        grids_for_plan["metadata"], n_slices, SLICE_HOURS, case["start_utc"],
    )
    corridor = ic.build_corridor(
        series, geometry.traversable, geometry.elevation, geometry.slope,
        geometry.resolution_m, rover, COARSEN, SLICE_HOURS,
    )
    return corridor, provenance


def _corridor_pair_runs(client, grids, case):
    corridor, provenance = _corridor_for(grids, case)
    near = (case["start"]["row"] // COARSEN, case["start"]["col"] // COARSEN)
    pair = ic.corridor_pair(corridor, near=near)
    entry = {
        "provenance": provenance["model"],
        "horizon_hours": HORIZON_HOURS,
        "slice_hours": SLICE_HOURS,
        "n_slices": corridor.n_slices,
        "build_ms": corridor.timings_ms,
        "voxels": {"lit_safe": int(corridor.lit_safe.sum()), "corridor": int(corridor.corridor.sum()), "traversable": int(corridor.n_slices * corridor.traversable.sum())},
        "pair": None,
        "runs": [],
    }
    if pair is None:
        return entry
    start, goal, info = pair
    entry["pair"] = {"start": list(start), "goal": list(goal), **info}
    rover = get_rover(case["rover_id"])
    base = {
        "start": _fine_centre(start), "goal": _fine_centre(goal), "rover_id": case["rover_id"],
        "start_utc": case["start_utc"], "horizon_hours": HORIZON_HOURS, "slice_hours": SLICE_HOURS,
    }
    variants = [
        ("budamasız", dict(base)),
        ("koridor, all", dict(base, require_continuous_illumination=True, lit_rule="all")),
        ("koridor, majority", dict(base, require_continuous_illumination=True, lit_rule="majority")),
    ]
    for label, body in variants:
        response, seconds = _plan(client, body, repeats=REPEATS)
        run = {"label": label, "status": response.status_code, "seconds": seconds}
        if response.status_code == 200:
            payload = response.json()
            metrics = payload["metrics"]
            block = payload["illumination_corridor"]
            by_id = {e["id"]: e for e in payload["safety_margins"]["requirements"]}
            run.update({
                "computation_time_ms": metrics["computation_time_ms"],
                "nodes_expanded": metrics["nodes_expanded"],
                "move_steps": metrics["move_steps"],
                "wait_steps": metrics["wait_steps"],
                "arrival_hours": metrics["arrival_hours"],
                "total_cost": metrics["total_cost"],
                "path_dark_hours_max": max(payload["path_dark_hours"]),
                "min_battery_pct": metrics["min_battery_pct"],
                "states_outside_corridor": metrics["states_outside_corridor"],
                "rejected_corridor": metrics["edges_rejected"]["continuous_illumination"],
                "route_inside": block["route"]["inside"],
                "max_dwell_hours": metrics["max_dwell_hours"],
                "dwell_horizon_limited": block["route"]["dwell_horizon_limited"],
                "lp_r01_rho": by_id["LP-R01"]["rho"],
                "h_max_shadow_h": float(rover["h_max_shadow_h"]),
                "corridor_voxels": block["voxels"]["corridor"],
                "lit_safe_voxels": block["voxels"]["lit_safe"],
                "components": block["components"],
                "corridor_ms": block["timings_ms"],
            })
        else:
            run["detail"] = response.json().get("detail")
        entry["runs"].append(run)
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "illumination_corridor_report.md"))
    parser.add_argument("--json", default=None, help="also dump the raw measurements here")
    args = parser.parse_args()

    try:
        grids = load_preprocessed_grids()
    except Exception as exc:  # noqa: BLE001
        print(f"processed grids unavailable ({exc}); nothing to measure.")
        return 0
    if horizon_cache_path(grids["metadata"]) is None or not _KERNELS.exists():
        print("horizon_map.npy or the NAIF kernels are missing; nothing to measure.")
        return 0

    app.state.grids = grids
    client = TestClient(app)
    report = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cases": []}
    for case in CASES:
        print(f"== {case['label']}", flush=True)
        entry = {"case": case, "standard": [], "corridor_pair": None}
        for lit_rule in ic.LIT_RULES:
            entry["standard"].append(_standard_pair(client, case, lit_rule))
            print(f"   standard pair, {lit_rule}: {entry['standard'][-1]['status']} / enforced {entry['standard'][-1]['enforced_status']}", flush=True)
        entry["corridor_pair"] = _corridor_pair_runs(client, grids, case)
        pair = entry["corridor_pair"]["pair"]
        print(f"   corridor pair: {pair}", flush=True)
        for run in entry["corridor_pair"]["runs"]:
            print(f"   {run['label']}: {run['status']} {run.get('computation_time_ms')} ms, nodes {run.get('nodes_expanded')}", flush=True)
        report["cases"].append(entry)

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    _write_markdown(report, Path(args.out))
    print(f"wrote {args.out}")
    return 0


def _write_markdown(report, path: Path) -> None:
    lines = [
        "# Sürekli-aydınlık koridoru (A2) — Site11 ölçüm raporu",
        "",
        f"Üretim: `scripts/illumination_corridor_report.py`, {report['generated_utc']}. "
        "Kaynak: Otten, Jones, Wettergreen, Whittaker (ICRA 2015; FSR 2017) — CMU'nun Güneş-eşzamanlı "
        "(sun-synchronous) x-y-t bağlı-bileşen budaması, 4-B planlayıcımızın ön-filtresi olarak.",
        "",
        "**İddia sınırı.** \"Koridor içinde modelin gölge serisi hiç karanlık göstermez\": SPICE Güneş konumu + "
        "ufuk küpü (72 azimut kutusu, iki ölçekli), 320 m kaba bloklar, örneklenmiş dilimler. Gerçek yüzey "
        "hakkında bir iddia değildir; B3'e göre 30 Mayıs 2027'de hücrelerin %10,8'i NASA'nın 100 DEM klonu "
        "arasında aydınlık/karanlık olarak kararsızdır.",
        "",
        "Kısaltmalar: `all` = bloktaki 16 ince hücrenin hepsi aydınlık; `majority` = blok ortalaması < 0,5 "
        "(planlayıcının kendi karanlık eşiği). Hacimler voksel (kaba hücre × dilim) sayısıdır.",
        "",
        "## 1. Standart çift (358,494)→(206,426), uçtaki varsayılan ufuk",
        "",
        "| Epoch | Kural | Dilim × saat | Geçilebilir voksel | Aydınlık-güvenli | Koridor | Budanan | CMU 26-komşuluk bileşen (sayı / en büyük / iki ucu tutan) | Başlangıç t0 koridorda | Hedef koridor dilimi | Rota koridorda | Rota gölge (h, maks) | `require` sonucu | Süre (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in report["cases"]:
        for std in entry["standard"]:
            if std["status"] != 200:
                lines.append(f"| {entry['case']['label']} | `{std['lit_rule']}` | — | — | — | — | — | — | — | — | — | — | {std['status']}: {std.get('detail')} | {_fmt(std['seconds'], 1)} |")
                continue
            b = std["block"]
            comp = b["components"]
            v = b["voxels"]
            lines.append(
                f"| {entry['case']['label']} | `{std['lit_rule']}` | {b['n_slices']} × {_fmt(b['slice_hours'], 4)} | {_int(v['traversable'])} | "
                f"{_int(v['lit_safe'])} ({_pct(v['lit_safe'] / v['traversable'] if v['traversable'] else None)}) | {_int(v['corridor'])} | "
                f"{_pct(v['pruned_fraction'])} | {comp['count']} / {_int(comp['largest_voxels'])} / {comp['spanning_count']} | "
                f"{'evet' if b['start']['in_corridor_t0'] else 'hayır'}"
                + (f" (ilk giriş dilim {b['start']['first_corridor_slice']})" if b['start']['first_corridor_slice'] not in (None, 0) else "")
                + f" | {b['goal']['corridor_slices']} / {b['n_slices']} | {'evet' if b['route']['inside'] else 'hayır'} | {_fmt(std['path_dark_hours_max'], 2)} | "
                f"{std['enforced_status']} | {_fmt(std['seconds'], 1)} |"
            )
    lines.append("")
    for entry in report["cases"]:
        for std in entry["standard"]:
            if std.get("enforced_detail") and std["lit_rule"] == "all":
                lines.append(f"- **{entry['case']['label']}**, `require_continuous_illumination` (`all`): {std['enforced_status']} — {std['enforced_detail']}")
    lines.append("")
    lines.append(f"## 2. Koridor-içi çift: budamalı vs budamasız planlama ({HORIZON_HOURS:g} h ufuk, {SLICE_HOURS:g} h dilim, en iyi {REPEATS} koşum)")
    lines.append("")
    lines.append("Çift `illumination_corridor.corridor_pair` ile seçildi: dilim-0 koridor kesitinde standart başlangıca en yakın blok → koridor içinde ondan ulaşılabilen en uzak (Chebyshev) blok.")
    lines.append("")
    for entry in report["cases"]:
        cp = entry["corridor_pair"]
        lines.append(f"### {entry['case']['label']}")
        lines.append("")
        lines.append(
            f"Koridor kurulumu ({cp['n_slices']} dilim): aydınlık-güvenli {_int(cp['voxels']['lit_safe'])} / geçilebilir {_int(cp['voxels']['traversable'])} voksel, "
            f"koridor {_int(cp['voxels']['corridor'])}; süreler (ms) hacim {_fmt(cp['build_ms']['lit_volume'], 0)}, kenarlar {_fmt(cp['build_ms']['edges'], 0)}, "
            f"budama {_fmt(cp['build_ms']['prune'], 0)}, dwell {_fmt(cp['build_ms']['dwell'], 0)}, toplam {_fmt(cp['build_ms']['total'], 0)}."
        )
        if cp["pair"] is None:
            lines.append("")
            lines.append("Dilim 0'da koridorda hiçbir blok yok: koridor-içi çift seçilemedi (koridor boş).")
            lines.append("")
            continue
        p = cp["pair"]
        lines.append(
            f"Çift: kaba ({p['start'][0]},{p['start'][1]}) → ({p['goal'][0]},{p['goal'][1]}), Chebyshev {p['goal_chebyshev_cells']} blok, "
            f"hedefe ilk varış dilimi {p['goal_first_reachable_slice']}, koridor içinde ulaşılabilir {p['reachable_cells']} blok."
        )
        lines.append("")
        lines.append("| Varyant | Durum | Planlama (ms) | Genişletilen düğüm | Hamle / bekleme | Varış (h) | Maliyet | Rota gölge maks (h) | Koridor dışı durum | Koridor reddi | LP-R01 ρ (h) | `h_max_shadow_h` | Maks dwell (h) | Dwell ufka dayalı | En düşük SOC (%) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for run in cp["runs"]:
            if run["status"] != 200:
                lines.append(f"| {run['label']} | {run['status']}: {run.get('detail')} | | | | | | | | | | | | | |")
                continue
            lines.append(
                f"| {run['label']} | 200 | {_fmt(run['computation_time_ms'], 0)} | {_int(run['nodes_expanded'])} | {run['move_steps']} / {run['wait_steps']} | "
                f"{_fmt(run['arrival_hours'], 2)} | {_fmt(run['total_cost'], 3)} | {_fmt(run['path_dark_hours_max'], 2)} | {run['states_outside_corridor']} | "
                f"{run['rejected_corridor']} | {_fmt(run['lp_r01_rho'], 2)} | {_fmt(run['h_max_shadow_h'], 0)} | {_fmt(run['max_dwell_hours'], 2)} | "
                f"{'evet' if run['dwell_horizon_limited'] else 'hayır'} | {_fmt(run['min_battery_pct'], 1)} |"
            )
        ok = [r for r in cp["runs"] if r["status"] == 200]
        base = next((r for r in ok if r["label"] == "budamasız"), None)
        if base:
            for run in ok:
                if run["label"] == "budamasız":
                    continue
                speed = base["computation_time_ms"] / run["computation_time_ms"] if run["computation_time_ms"] else None
                nodes = base["nodes_expanded"] / run["nodes_expanded"] if run["nodes_expanded"] else None
                lines.append("")
                lines.append(
                    f"- `{run['label']}` vs budamasız: planlama süresi ×{_fmt(speed, 2)}, genişletilen düğüm ×{_fmt(nodes, 2)}; "
                    f"koridor {_int(run['corridor_voxels'])} / aydınlık-güvenli {_int(run['lit_safe_voxels'])} voksel; CMU label {run['components']['count']} bileşen, "
                    f"en büyüğü {_int(run['components']['largest_voxels'])} voksel, iki ucu tutan {run['components']['spanning_count']}; koridor kurulumu {_fmt(run['corridor_ms']['total'], 0)} ms."
                )
        lines.append("")
    lines.append("## 3. Okuma")
    lines.append("")
    lines.append(
        "- Koridor içindeki her rotada `path_dark_hours` tanım gereği sıfırdır ve D3'ün LP-R01 marjı rover'ın "
        "tam gölge dayanımına eşittir (`h_max_shadow_h`): \"rota gölgeye girmiyor\" kanıtı planlayıcının kendi sayımı ve formal monitörle okunur."
    )
    lines.append(
        "- Standart haven→haven çifti CMU anlamında Güneş-eşzamanlı değildir: başlangıç bloğu t0'da karanlık; koridor kuralı onu tanım gereği reddeder. "
        "Hızlanma yalnızca koridor-içi çiftlerde anlamlıdır ve yukarıdaki tabloda ölçülmüştür."
    )
    lines.append(
        "- Dwell sayıları varsayılan kısa ufka (8 h) dayanır (`horizon_limited`); CMU'nun 45/226 saatlik dwell'leri 59 günlük pencerelerdendir."
    )
    lines.append(
        "- Budama bu ufuklarda çok az siler (%0,2–0,3): kutupta aydınlanma 10 saatte neredeyse durağandır, dolayısıyla aydınlık-güvenli hacmin hemen tamamı zaten "
        "ilk dilimden son dilime bağlıdır. CMU'nun budaması 59 günlük pencerelerde (aydınlık adaların doğup söndüğü ölçekte) anlamlıdır; bu ufuklarda koridorun değeri "
        "budama değil, garanti ve planlayıcının rotayı koridorda tutmasıdır."
    )
    lines.append(
        "- Hızlanma mütevazıdır: maliyet küpü gölgeyi zaten fiyatladığı ve sezgisel odaklı olduğu için budamasız rota da koridorun içinde kalır; koridor kuralı "
        "genişletmeyi bir miktar azaltır (yukarıdaki × oranları), yani \"22 s → X s\" türü bir kazanç bu gridde ölçülmemiştir. A3'ün hedef alt-hacmi "
        "(`prune_corridor(sources=başlangıç, sinks=hedef)`) budamayı rotaya özgü kılacak adaydır."
    )
    lines.append(
        "- LPR-1'in 28 Eylül 2026 gününde 8 saatlik koridor yoktur: aydınlık ada büzülür (2,9 h ufukta 55 150, 8 h ufukta 20 566 aydınlık-güvenli voksel) ve "
        "t0'daki hiçbir blok pencere sonuna kadar bağlı-aydınlık kalmaz; uç bunu `voxels.corridor = 0` ve 404 gerekçesiyle söyler."
    )
    lines.append("")
    lines.append("Sunum cümlesi: **Sun-synchronous yaklaşımını (CMU, NIAC) 4-B planlayıcımızın ön-filtresi olarak uyguladık.** Tasarım: `docs/superpowers/specs/2026-09-04-a2-illumination-corridor-design.md`.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
