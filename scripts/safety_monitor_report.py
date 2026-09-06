#!/usr/bin/env python3
"""Measure the formal safety monitor (D3) on the checked-in Site11 grid.

Runs the same routes B5 and B3 measured -- VIPER's haven-to-haven plan on
2027-05-30 and LPR-1's on 2026-09-28 -- through /api/plan-4d, the
/api/compare profiles for both rovers, SHERPA's stress test on the two
4-D routes, and a telemetry trace through /api/safety-check, and reads
back what the requirement catalogue says: robustness per requirement, the
smallest margin, where along the route it sits, the boolean verdicts the
old constraint check gave next to the signed margins, the robustness
distribution under SHERPA's perturbations, timings, and whether RTAMT and
the built-in engine agreed.

Needs the processed grids, horizon_map.npy and the NAIF kernels; without
them it says so and exits 0. It never fabricates numbers. Writes
docs/research/safety_monitor_report.md by default.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app import safety_monitor as sm  # noqa: E402
from app.constants import get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.illumination_series import horizon_cache_path  # noqa: E402
from app.main import app  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

START = {"row": 358, "col": 494}
GOAL = {"row": 206, "col": 426}
CASES = [
    {
        "label": "VIPER haven->haven, 30 May 2027",
        "rover_id": "nasa_viper",
        "start_utc": "2027-05-30T00:00:00",
        "require_safe_haven": True,
    },
    {
        "label": "LPR-1, 28 Sep 2026",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-28T00:00:00",
        "require_safe_haven": False,
    },
]
N_RUNS = 1000
SEED = 0


def _fmt(value, digits: int = 2) -> str:
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _yes(value) -> str:
    if value is None:
        return "—"
    return "evet" if value else "**hayır**"


def _worst(entry) -> str:
    worst = entry.get("worst_at")
    if worst is None:
        return "—"
    where = f"#{worst['index']} @ {_fmt(worst['hours'], 2)} h"
    if "row" in worst:
        where += f" ({worst['row']}, {worst['col']})"
    return where


def _threshold(entry) -> str:
    threshold = entry.get("threshold")
    if threshold is None:
        return "—"
    if isinstance(threshold, list):
        return f"{_fmt(threshold[0], 0)}…{_fmt(threshold[1], 0)}"
    return _fmt(threshold, 0 if float(threshold).is_integer() else 2)


def _requirement_table(block) -> list[str]:
    lines = [
        "| ID | Gereksinim | ρ | Birim | ρ/ölçek | Sağlandı | Eşik (kaynak) | En kötü nokta | Motor |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in block["requirements"]:
        if not entry["applicable"]:
            lines.append(
                f"| {entry['id']} | `{entry['name']}` | — | {entry['unit']} | — | uygulanamaz | — | {entry['reason']} | — |"
            )
            continue
        rho = "+∞ (açık uçlu)" if entry["open_ended"] else _fmt(entry["rho"], 2)
        satisfied = _yes(entry["satisfied"]) if not entry["pending"] else "beklemede"
        if entry.get("boundary"):
            satisfied += " (sınır)"
        lines.append(
            f"| {entry['id']} | `{entry['name']}` | {rho} | {entry['unit']} | {_fmt(entry['rho_normalized'], 3)} | "
            f"{satisfied} | {_threshold(entry)} ({entry['threshold_source']}) | {_worst(entry)} | {entry['engine']} |"
        )
    margin = block["min_margin"]
    lines.append("")
    lines.append(
        f"Karar **{block['verdict']}**; uygulanabilir {block['n_applicable']}, ihlal {block['n_violated']}"
        + (f" ({', '.join(block['violated'])})" if block["violated"] else "")
        + (
            f"; en küçük marj **{margin['id']}** ρ = {_fmt(margin['rho'], 2)} {margin['unit']} "
            f"(ρ/ölçek {_fmt(margin['rho_normalized'], 3)})."
            if margin
            else "."
        )
    )
    cross = block["monitor"]["cross_check"]
    lines.append(
        f"Motor `{block['monitor']['engine']}`"
        + (f" (rtamt {block['monitor']['rtamt_version']})" if block["monitor"]["rtamt_version"] else "")
        + (f", yerleşik motorla en büyük fark {cross['max_abs_diff']:g}" if cross else "")
        + f"; iz: {block['monitor']['trace']['n_samples']} örnek, {_fmt(block['monitor']['trace']['duration_h'], 2)} h."
    )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "safety_monitor_report.md"))
    parser.add_argument("--n-runs", type=int, default=N_RUNS)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    try:
        grids = load_preprocessed_grids()
    except Exception as exc:  # noqa: BLE001
        print(f"processed grids not available: {exc}")
        return 0
    if not _KERNELS.exists():
        print(f"NAIF kernels not found at {_KERNELS}; nothing measured")
        return 0
    if not Path(horizon_cache_path(grids["metadata"])).exists():
        print("horizon_map.npy not found; nothing measured")
        return 0

    app.state.grids = grids
    client = TestClient(app)
    report: dict = {
        "engine": {
            "rtamt_available": sm.rtamt_available(),
            "rtamt_version": sm.rtamt_version(),
        },
        "plan4d": [],
        "compare": [],
        "stress": [],
        "safety_check": {},
    }
    try:
        from importlib.metadata import version

        report["engine"]["antlr_version"] = version("antlr4-python3-runtime")
    except Exception:  # noqa: BLE001
        report["engine"]["antlr_version"] = None

    # ── 1. The two 4-D routes ─────────────────────────────────────────
    for case in CASES:
        body = {
            "start": START,
            "goal": GOAL,
            "rover_id": case["rover_id"],
            "start_utc": case["start_utc"],
            "coarsen": 4,
            "require_safe_haven": case["require_safe_haven"],
        }
        started = time.perf_counter()
        response = client.post("/api/plan-4d", json=body)
        elapsed = time.perf_counter() - started
        entry = {"case": case, "status": response.status_code, "plan_s": round(elapsed, 2)}
        if response.status_code != 200:
            entry["detail"] = response.json().get("detail")
            report["plan4d"].append(entry)
            print(f"{case['label']}: plan-4d {response.status_code}: {entry['detail']}")
            continue
        payload = response.json()
        # The monitor's own cost: rebuild its trace evaluation from the response.
        block = payload["safety_margins"]
        entry.update(
            {
                "metrics": payload["metrics"],
                "n_states": len(payload["path_states"]),
                "slice_hours": payload["slice_hours"],
                "block": block,
                "path_states": payload["path_states"],
                "earth_model": payload["earth_model"].get("model"),
                "haven_model": payload["safe_haven_model"].get("model"),
            }
        )
        report["plan4d"].append(entry)
        print(f"{case['label']}: {block['verdict']} in {elapsed:.1f} s, min margin {block['min_margin']}")

        # SHERPA's runs on the same route, for the robustness distribution.
        stress_body = {
            "path_states": payload["path_states"],
            "rover_id": case["rover_id"],
            "coarsen": 4,
            "slice_hours": payload["slice_hours"],
            "start_utc": case["start_utc"],
            "n_runs": args.n_runs,
            "seed": args.seed,
        }
        started = time.perf_counter()
        stress = client.post("/api/stress-test", json=stress_body)
        stress_s = time.perf_counter() - started
        if stress.status_code == 200:
            data = stress.json()
            rover = get_rover(case["rover_id"])
            floor = float(rover["soc_min_pct"]) * 100.0
            h_max = float(rover["h_max_shadow_h"])
            battery = data["metrics"]["min_battery_pct"]
            dark = data["metrics"]["max_continuous_shadow_h"]
            report["stress"].append(
                {
                    "case": case,
                    "n_runs": data["n_runs"],
                    "seconds": round(stress_s, 2),
                    "r02": None if battery is None else {k: battery[k] - floor for k in ("p5", "p50", "p95")},
                    "r01": None if dark is None else {"p5": h_max - dark["p95"], "p50": h_max - dark["p50"], "p95": h_max - dark["p5"]},
                    "r02_plan": next(e["rho"] for e in block["requirements"] if e["id"] == "LP-R02"),
                    "r01_plan": next(e["rho"] for e in block["requirements"] if e["id"] == "LP-R01"),
                    "completion": data["rates"]["completion"],
                    "reserve_breached": data["rates"]["reserve_breached"],
                }
            )
        else:
            report["stress"].append({"case": case, "status": stress.status_code, "detail": stress.json().get("detail")})

    # ── 2. /api/compare, both rovers ──────────────────────────────────
    for rover_id in ("nasa_viper", "lpr_1"):
        started = time.perf_counter()
        response = client.post(
            "/api/compare",
            json={"start": [START["row"], START["col"]], "goal": [GOAL["row"], GOAL["col"]], "rover_id": rover_id},
        )
        elapsed = time.perf_counter() - started
        entry = {"rover_id": rover_id, "status": response.status_code, "seconds": round(elapsed, 2)}
        if response.status_code == 200:
            payload = response.json()
            entry["results"] = [
                {
                    "profile_id": r["profile_id"],
                    "error": r.get("error"),
                    "constraint_check": r.get("constraint_check"),
                    "summary": r.get("simulation_summary"),
                    "block": r.get("safety_margins"),
                }
                for r in payload["results"]
            ]
            entry["comparison"] = payload["comparison"]
        report["compare"].append(entry)
        print(f"compare {rover_id}: {response.status_code} in {elapsed:.1f} s")

    # ── 3. /api/safety-check on a telemetry trace ─────────────────────
    samples = []
    for i in range(500):
        t = i * 0.1
        samples.append(
            {
                "t_h": t,
                "soc_pct": 90.0 - 0.1 * i,
                "inner_temp_c": 5.0 + 10.0 * ((i // 50) % 2),
                "in_shadow": (i // 100) % 2 == 1,
                "slope_deg": 6.0 + (i % 7),
                "lateral_slope_deg": 2.0 + (i % 5),
                "moving": i % 4 != 0,
                "earth_link_h": 40.0 - 0.05 * i,
                "haven_margin_h": 30.0 - 0.02 * i,
                "dist_to_goal_m": max(0.0, 1996.0 - 4.0 * i),
            }
        )
    timings = {}
    for engine in ("builtin", "rtamt"):
        if engine == "rtamt" and not sm.rtamt_available():
            continue
        started = time.perf_counter()
        response = client.post("/api/safety-check", json={"rover_id": "nasa_viper", "samples": samples, "engine": engine})
        timings[engine] = {"ms": round((time.perf_counter() - started) * 1000.0, 1), "status": response.status_code}
        if response.status_code == 200:
            timings[engine]["verdict"] = response.json()["safety_margins"]["verdict"]
            timings[engine]["min_margin"] = response.json()["safety_margins"]["min_margin"]
    report["safety_check"] = {"n_samples": len(samples), "timings": timings}

    _write_markdown(Path(args.out), report, args)
    print(f"wrote {args.out}")
    return 0


def _write_markdown(path: Path, report: dict, args) -> None:
    lines: list[str] = []
    engine = report["engine"]
    lines.append("# Formal güvenlik gereksinimleri — FRETISH + STL robustness monitörü Site11 rotalarında (D3)")
    lines.append("")
    lines.append(
        f"Üretildi: `scripts/safety_monitor_report.py` ile, {time.strftime('%Y-%m-%d')}. Motor: "
        + (
            f"RTAMT {engine['rtamt_version']} (ANTLR runtime {engine['antlr_version']}) + yerleşik değerlendirici, her istekte çapraz kontrol"
            if engine["rtamt_available"]
            else "yalnızca yerleşik değerlendirici (rtamt kurulu değil)"
        )
        + ". Gereksinimler `docs/requirements/lunapath.fret.json` (FRETISH, elle STL'e çevrildi; FRET aracı kullanılmadı). "
        "Her sonuç **bu rotanın çalışma-zamanı izlemesidir**; hiçbir sonuç model checking ile ispat değildir."
    )
    lines.append("")
    lines.append("ρ ≥ 0 sağlandı, ρ < 0 ihlal; |ρ| gereksinimin biriminde marj. ρ/ölçek: eşik (tek taraflı), yarı genişlik (aralık), 24 h (Dünya/haven), rota uzunluğu (hedef) ile bölünmüş birimsiz kıyas anahtarı.")
    lines.append("")
    lines.append(
        "Okuma notu: LP-R04/LP-R05'in iç sıcaklığı statik termal katman (`thermal_field: sunlit_peak`, gölgeye bağlı) artı "
        "`cost_engine.surface_to_inner`'ın rover ofsetidir (LPR-1/VIPER: soğuk dalda +60 K, sıcak dalda −40 K); ısıtıcı gücü "
        "enerji modelinde sayılır ama bu sıcaklık modelinde ısıtma yoktur. Bir termal ihlal, rota kadar bu modelin rover zarfıyla "
        "tutarsızlığını da ölçer. LP-R09'da `—` ile `hayır`: sonlu Dünya batışına karşı ulaşılabilir haven yok (sınırsız ihlal)."
    )
    lines.append("")

    lines.append("## 1. 4-B planlar (`/api/plan-4d`)")
    for entry in report["plan4d"]:
        case = entry["case"]
        lines.append("")
        lines.append(f"### {case['label']}")
        lines.append("")
        if entry["status"] != 200:
            lines.append(f"plan-4d {entry['status']}: {entry.get('detail')}")
            continue
        metrics = entry["metrics"]
        lines.append(
            f"Rover `{case['rover_id']}`, epoch `{case['start_utc']}`, ({START['row']}, {START['col']}) → ({GOAL['row']}, {GOAL['col']}), "
            f"coarsen 4, `require_safe_haven` = {str(case['require_safe_haven']).lower()}; "
            f"{metrics.get('move_steps')} MOVE, {metrics.get('wait_steps')} WAIT, varış {_fmt(metrics.get('arrival_hours'), 2)} h, "
            f"dilim {_fmt(entry['slice_hours'], 4)} h, {entry['n_states']} durum; Dünya modeli `{entry['earth_model']}`, haven `{entry['haven_model']}`; planlama {_fmt(entry['plan_s'], 1)} s."
        )
        lines.append("")
        lines.extend(_requirement_table(entry["block"]))

    lines.append("")
    lines.append("## 2. SHERPA koşumlarında robustness dağılımı (`/api/stress-test`)")
    lines.append("")
    lines.append(
        f"{args.n_runs} koşum, tohum {args.seed}, B5'in varsayılan dağılımları. ρ aritmetikle: LP-R02 = `min_battery_pct − soc_min`, "
        "LP-R01 = `h_max_shadow_h − max_continuous_shadow_h` (koşum başına; p5/p50/p95 dağılımdan). LP-R10 = tamamlanma oranı."
    )
    lines.append("")
    lines.append("| Rota | Plan ρ LP-R02 (pp) | SHERPA ρ LP-R02 p5 / p50 / p95 | Plan ρ LP-R01 (h) | SHERPA ρ LP-R01 p5 / p50 / p95 | Rezerv ihlali | Tamamlanma (LP-R10) | Süre (s) |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for entry in report["stress"]:
        if "n_runs" not in entry:
            lines.append(f"| {entry['case']['label']} | — | {entry.get('status')}: {entry.get('detail')} | — | — | — | — | — |")
            continue
        r02, r01 = entry["r02"], entry["r01"]
        completion = entry["completion"]
        breached = entry["reserve_breached"]
        lines.append(
            f"| {entry['case']['label']} | {_fmt(entry['r02_plan'], 1)} | "
            + (f"{_fmt(r02['p5'], 1)} / {_fmt(r02['p50'], 1)} / {_fmt(r02['p95'], 1)}" if r02 else "—")
            + f" | {_fmt(entry['r01_plan'], 1)} | "
            + (f"{_fmt(r01['p5'], 1)} / {_fmt(r01['p50'], 1)} / {_fmt(r01['p95'], 1)}" if r01 else "—")
            + f" | {_fmt(100 * breached['rate'], 1)} % | {_fmt(100 * completion['rate'], 1)} % ({_fmt(100 * completion['ci95'][0], 1)}–{_fmt(100 * completion['ci95'][1], 1)}) | {_fmt(entry['seconds'], 1)} |"
        )

    lines.append("")
    lines.append("## 3. 2-B profiller (`/api/compare`): ikili karar vs marj")
    for entry in report["compare"]:
        lines.append("")
        lines.append(f"### Rover `{entry['rover_id']}` ({_fmt(entry['seconds'], 1)} s)")
        lines.append("")
        if entry["status"] != 200:
            lines.append(f"compare {entry['status']}")
            continue
        lines.append("| Profil | Karar | En küçük marj | LP-R01 ρ (h) | `max_shadow_h` ikili | LP-R02 ρ (pp) | `min_soc` ikili | LP-R06 ρ (°) | LP-R07 ρ (°) | LP-R10 | LP-R11 ρ (pp) |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for result in entry["results"]:
            if result["error"] or not result["block"]:
                lines.append(f"| `{result['profile_id']}` | hata: {result['error']} | | | | | | | | | |")
                continue
            block = result["block"]
            by_id = {e["id"]: e for e in block["requirements"]}
            check = result["constraint_check"] or {}
            margin = block["min_margin"]

            def rho(rid):
                e = by_id[rid]
                return _fmt(e["rho"], 2) if e["applicable"] and e["rho"] is not None else "—"

            def binary(key):
                verdict = (check.get(key) or {}).get("satisfied")
                limit = (check.get(key) or {}).get("limit")
                return f"{_yes(verdict)} (sınır {limit})" if limit is not None else "— (sınır yok)"

            lines.append(
                f"| `{result['profile_id']}` | {block['verdict']} | {margin['id']} {_fmt(margin['rho'], 2)} {margin['unit']} | "
                f"{rho('LP-R01')} | {binary('max_shadow_h')} | {rho('LP-R02')} | {binary('min_soc')} | {rho('LP-R06')} | {rho('LP-R07')} | "
                f"{_yes(by_id['LP-R10']['satisfied'])} | {rho('LP-R11')} |"
            )
        ranking = entry["comparison"]["safety_margin_ranking"]
        lines.append("")
        lines.append(
            "Sıralama (`comparison.safety_margin_ranking`, en güvenli önce): "
            + ", ".join(
                f"`{r['label']}` ({r['verdict']}, {r['min_margin']['id']} ρ/ölçek {_fmt(r['min_margin']['rho_normalized'], 3)})"
                if r["min_margin"]
                else f"`{r['label']}` ({r['verdict']})"
                for r in ranking
            )
            + f". `largest_min_margin_profile`: `{entry['comparison']['largest_min_margin_profile']}`."
        )

    lines.append("")
    lines.append("## 4. `/api/safety-check` süresi")
    lines.append("")
    check = report["safety_check"]
    lines.append(f"{check['n_samples']} örnekli sentetik telemetri izi, 11 gereksinim:")
    lines.append("")
    lines.append("| Motor | Süre (ms) | Karar | En küçük marj |")
    lines.append("|---|---|---|---|")
    for engine_name, timing in check["timings"].items():
        margin = timing.get("min_margin")
        lines.append(
            f"| `{engine_name}` | {_fmt(timing['ms'], 0)} | {timing.get('verdict')} | "
            + (f"{margin['id']} ρ = {_fmt(margin['rho'], 2)} {margin['unit']}" if margin else "—")
            + " |"
        )
    lines.append("")
    lines.append("Kaynak: NASA FRET (Giannakopoulou vd. 2020), RTAMT (Ničković & Yamaguchi 2020), Donzé & Maler 2010. Tasarım: `docs/superpowers/specs/2026-09-04-d3-formal-safety-design.md`.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
