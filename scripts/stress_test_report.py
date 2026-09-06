#!/usr/bin/env python3
"""Run SHERPA's Monte Carlo traverse evaluation on real LunaPath routes (B5).

VIPER's planning team stress-tests every strategic plan against truncated
Gaussians on start time (sigma 2 h), initial battery (20 percent), power
draw (20 percent) and effective speed (20 / 30 / 40 / 50 percent), under an
operator policy -- ahead: hold; behind: skip charge breaks, drive through
shadow -- and reads off the distribution of completion, time-to-sun-shadow,
time-to-DSN-shadow and time-to-0-SOC (Shirley & Balaban 2022). This script
plans real routes on the checked-in Site11 grid with /api/plan-4d, runs
/api/stress-test on each with the four speed sigmas VIPER used and a DSN
outage sensitivity, and writes the numbers down.

Needs the processed grids, ``horizon_map.npy`` and the NAIF kernels; without
them it says so and exits 0. It never fabricates numbers.

Writes a Markdown report (default docs/research/stress_test_report.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.illumination_series import horizon_cache_path  # noqa: E402
from app.main import app  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

_NO_HORIZON = """
Ufuk kubu bulunamadi (horizon_map.npy, islenmis gridlerin yaninda).

Once scripts/build_horizon_cache.py calistirin. Bu script ufuk kubu olmadan
stres testi kosmaz.
"""

_NO_KERNELS = f"""
NAIF cekirdekleri bulunamadi: {_KERNELS}

Gunes ve Dunya konumlari SPICE ile hesaplanir; cekirdekler olmadan rota ve
stres testi uretilmez. Kurulum icin docs/frontend/3b-veri-sozlesmesi.md
"Kurulum" bolumune bakin.
"""

#: The routes. VIPER: the haven-to-haven pair the A1 probe used on the lunar
#: day where a tenth of the site qualifies (coarse (89,123) -> (51,106)).
#: LPR-1: a lit, linked epoch after the September 2026 night and Earthset.
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


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".replace(".", ",")


def _pct(rate: dict | None) -> str:
    if rate is None:
        return "-"
    lo, hi = rate["ci95"]
    return f"{100 * rate['rate']:.1f} % ({100 * lo:.1f}–{100 * hi:.1f})".replace(".", ",")


def _metric(block: dict | None, key: str, digits: int = 2) -> str:
    if block is None:
        return "-"
    return _fmt(block.get(key), digits)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--n-runs", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sigmas", type=float, nargs="*", default=[0.2, 0.3, 0.4, 0.5])
    parser.add_argument("--dsn-probability", type=float, default=0.1)
    parser.add_argument("--dsn-mean-h", type=float, default=4.0)
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "stress_test_report.md"))
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    if not _KERNELS.exists():
        print(_NO_KERNELS)
        return 0
    grids = load_preprocessed_grids()
    if horizon_cache_path(grids["metadata"]) is None:
        print(_NO_HORIZON)
        return 0

    app.state.grids = grids
    client = TestClient(app)
    report: list[dict] = []

    for case in CASES:
        rover = get_rover(case["rover_id"])
        body = {
            "start": case["start"],
            "goal": case["goal"],
            "rover_id": case["rover_id"],
            "start_utc": case["start_utc"],
            "coarsen": 4,
            "require_safe_haven": case["require_safe_haven"],
        }
        t0 = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        plan_s = time.perf_counter() - t0
        entry = {**case, "plan_status": response.status_code, "plan_seconds": plan_s}
        if response.status_code != 200:
            entry["plan_error"] = response.json().get("detail")
            print(f"{case['label']}: plan {response.status_code}: {entry['plan_error']}")
            report.append(entry)
            continue
        plan = response.json()
        entry["plan"] = {
            "n_states": len(plan["path_states"]),
            "move_steps": plan["metrics"]["move_steps"],
            "wait_steps": plan["metrics"]["wait_steps"],
            "arrival_hours": plan["metrics"]["arrival_hours"],
            "slice_hours": plan["slice_hours"],
            "min_battery_pct": plan["metrics"]["min_battery_pct"],
            "min_haven_margin_h": plan["metrics"].get("min_haven_margin_h"),
            "time_to_dsn_shadow_min_h": plan["metrics"].get("time_to_dsn_shadow_min_h"),
            "time_to_zero_soc_min_h": plan["metrics"].get("time_to_zero_soc_min_h"),
        }
        print(
            f"{case['label']}: plan {entry['plan']['move_steps']} moves, "
            f"{entry['plan']['wait_steps']} waits, {entry['plan']['arrival_hours']:.2f} h "
            f"[{plan_s:.1f} s]"
        )

        runs: list[dict] = []
        variants = [("speed_sigma", s, {"speed_sigma": s}) for s in args.sigmas]
        variants.append(
            (
                "dsn",
                args.dsn_probability,
                {
                    "speed_sigma": args.sigmas[0],
                    "dsn_outage_probability": args.dsn_probability,
                    "dsn_outage_mean_h": args.dsn_mean_h,
                },
            )
        )
        for kind, value, perturbations in variants:
            stress_body = {
                "path_states": plan["path_states"],
                "rover_id": case["rover_id"],
                "coarsen": 4,
                "slice_hours": plan["slice_hours"],
                "start_utc": case["start_utc"],
                "n_runs": args.n_runs,
                "seed": args.seed,
                "perturbations": perturbations,
                "label": f"{case['label']} {kind}={value}",
            }
            t0 = time.perf_counter()
            response = client.post("/api/stress-test", json=stress_body)
            wall_s = time.perf_counter() - t0
            if response.status_code != 200:
                print(f"  {kind}={value}: stress test {response.status_code}: {response.text[:200]}")
                runs.append({"kind": kind, "value": value, "status": response.status_code})
                continue
            out = response.json()
            m = out["metrics"]
            run = {
                "kind": kind,
                "value": value,
                "status": 200,
                "wall_seconds": wall_s,
                "timing_ms": out["timing_ms"],
                "sky_model": out["sky_model"]["model"],
                "safe_haven_model": out["safe_haven_model"]["model"],
                "rates": out["rates"],
                "failures": out["failures"],
                "duration_h": m["duration_h"],
                "duration_normalized": m["duration_normalized"],
                "min_battery_pct": m["min_battery_pct"],
                "max_continuous_shadow_h": m["max_continuous_shadow_h"],
                "time_to_sun_shadow_min_h": m["time_to_sun_shadow_min_h"],
                "time_to_dsn_shadow_min_h": m["time_to_dsn_shadow_min_h"],
                "time_to_zero_soc_min_h": m["time_to_zero_soc_min_h"],
                "dsn_shadow_events": m["dsn_shadow_events"],
                "states_past_haven_deadline": m["states_past_haven_deadline"],
                "outages": out["outages"],
                "nominal": out["nominal"],
                "verdict": out["verdict"]["text"],
            }
            runs.append(run)
            print(
                f"  {kind}={value:<4} completion {_pct(out['rates']['completion'])}  "
                f"full {_pct(out['rates']['full_success'])}  "
                f"duration p50/p95 {_metric(m['duration_h'], 'p50')}/{_metric(m['duration_h'], 'p95')} h  "
                f"min batt p5 {_metric(m['min_battery_pct'], 'p5')} %  "
                f"[{wall_s:.1f} s]"
            )
        entry["runs"] = runs
        report.append(entry)

    _write_markdown(Path(args.out), report, args)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nRapor: {args.out}")
    return 0


def _write_markdown(path: Path, report: list[dict], args) -> None:
    lines = [
        "# Monte Carlo traverse stres testi — SHERPA protokolü Site11 rotalarında (B5)",
        "",
        f"Üretildi: `scripts/stress_test_report.py` ile, {time.strftime('%Y-%m-%d')}. "
        f"Koşum sayısı {args.n_runs}, tohum {args.seed}. Dağılımlar Shirley & Balaban 2022: "
        "başlangıç gecikmesi σ 2 h, başlangıç bataryası σ %20 (aşağı), güç çekişi σ %20 (yukarı), "
        "etkin hız σ %20/30/40/50 (aşağı, taban 0,25). DSN kesintisi için yayınlanmış oran yok; "
        f"duyarlılık p = {args.dsn_probability}, ortalama {args.dsn_mean_h} h.",
        "",
        "Oranlar Wilson %95 güven aralığıyla. `tam başarı` = hedefe varış ∧ batarya hiç rezervin "
        "altına inmedi ∧ (haven alanları biliniyorsa) hiçbir durumda Dünya batış süresi aşılmadı.",
        "",
    ]
    for entry in report:
        lines.append(f"## {entry['label']}")
        lines.append("")
        lines.append(
            f"Rover `{entry['rover_id']}`, epoch `{entry['start_utc']}`, başlangıç "
            f"({entry['start']['row']}, {entry['start']['col']}) → hedef "
            f"({entry['goal']['row']}, {entry['goal']['col']}) (ince piksel), coarsen 4, "
            f"`require_safe_haven` = {str(entry['require_safe_haven']).lower()}."
        )
        lines.append("")
        if entry.get("plan_status") != 200:
            lines.append(f"Plan {entry.get('plan_status')}: {entry.get('plan_error')}")
            lines.append("")
            continue
        plan = entry["plan"]
        lines.append(
            f"Plan: {plan['move_steps']} MOVE, {plan['wait_steps']} WAIT, varış "
            f"{_fmt(plan['arrival_hours'])} h, dilim {_fmt(plan['slice_hours'], 4)} h, en düşük batarya "
            f"{_fmt(plan['min_battery_pct'], 1)} %, haven marjı {_fmt(plan['min_haven_margin_h'], 1)} h, "
            f"DSN marjı {_fmt(plan['time_to_dsn_shadow_min_h'], 1)} h, 0-SOC marjı "
            f"{_fmt(plan['time_to_zero_soc_min_h'], 1)} h; planlama {_fmt(entry['plan_seconds'], 1)} s."
        )
        lines.append("")
        lines.append(
            "| Varyant | Tamamlanma | Rezerv içinde | Tam başarı | Rezerv ihlali | Batarya / gölge / ufuk | "
            "Süre p50 / p95 (h) | Normalize p95 | Min batarya p5 (%) | Maks gölge p95 (h) | "
            "DSN marjı min p5 (h) | 0-SOC marjı p5 (h) | Süre (s) |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for run in entry.get("runs", []):
            if run.get("status") != 200:
                lines.append(f"| {run['kind']} = {run['value']} | HTTP {run['status']} | | | | | | | | | | | |")
                continue
            label = (
                f"hız σ {int(100 * run['value'])} %"
                if run["kind"] == "speed_sigma"
                else f"DSN p = {run['value']} (hız σ {int(100 * args.sigmas[0])} %)"
            )
            f = run["failures"]
            lines.append(
                f"| {label} | {_pct(run['rates']['completion'])} | "
                f"{_pct(run['rates']['reached_within_reserve'])} | {_pct(run['rates']['full_success'])} | "
                f"{_pct(run['rates']['reserve_breached'])} | "
                f"{f['battery_depleted']} / {f['shadow_endurance']} / {f['horizon_exceeded']} | "
                f"{_metric(run['duration_h'], 'p50')} / {_metric(run['duration_h'], 'p95')} | "
                f"{_metric(run['duration_normalized'], 'p95')} | "
                f"{_metric(run['min_battery_pct'], 'p5', 1)} | "
                f"{_metric(run['max_continuous_shadow_h'], 'p95')} | "
                f"{_metric(run['time_to_dsn_shadow_min_h'], 'p5', 1)} | "
                f"{_metric(run['time_to_zero_soc_min_h'], 'p5', 1)} | "
                f"{_fmt(run['wall_seconds'], 1)} |"
            )
        lines.append("")
        first = next((r for r in entry.get("runs", []) if r.get("status") == 200), None)
        if first is not None:
            nominal = first["nominal"]
            lines.append(
                f"Nominal koşum (tüm çarpanlar 1): süre {_fmt(nominal['duration_h'])} h, en düşük batarya "
                f"{_fmt(nominal['min_battery_pct'], 1)} %, maks gölge {_fmt(nominal['max_continuous_shadow_h'])} h, "
                f"DSN marjı {_fmt(nominal['time_to_dsn_shadow_min_h'], 1)} h. Karar: {first['verdict']} Gökyüzü `{first['sky_model']}`, "
                f"safe haven `{first['safe_haven_model']}`. Süre dağılımı: gökyüzü "
                f"{_fmt(first['timing_ms']['sky'] / 1000.0, 2)} s, koşumlar "
                f"{_fmt(first['timing_ms']['runs'] / 1000.0, 2)} s."
            )
            lines.append("")
            dsn = next((r for r in entry["runs"] if r.get("kind") == "dsn" and r.get("status") == 200), None)
            if dsn is not None and dsn["outages"]["dsn"]["runs"]:
                lines.append(
                    f"DSN kesintisi duyarlılığı: {dsn['outages']['dsn']['runs']} koşumda kesinti, ortalama pencere "
                    f"{_fmt(dsn['outages']['dsn']['mean_window_h'])} h, ortalama bekleme "
                    f"{_fmt(dsn['outages']['dsn']['mean_hold_h'])} h."
                )
                lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
