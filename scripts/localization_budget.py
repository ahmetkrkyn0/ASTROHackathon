#!/usr/bin/env python3
"""How often must the rover stop for an absolute fix on a REAL route?

Plans a route on the shipped processed grid, builds its corridor, and
compares the corridor's actual half-widths against the uncertainty
growth of each odometry source in app.localization_budget. The output
answers the operational question the Phase 7 plan poses: is the corridor
LunaPath produces wide enough for a real odometry stack to fly it, and
for how long between resets?

The report states its own limits: drift rates are literature figures
from other vehicles on other terrain, the growth model is linear because
percent-of-distance is the form those figures come in, and none of this
is calibrated against this rover on this regolith.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.constants import get_rover  # noqa: E402
from app.corridor import build_corridor  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.localization_budget import (  # noqa: E402
    DRIFT_RATES,
    budget_for_source,
)
from app.pathfinder import astar  # noqa: E402


def _fmt_m(value: float) -> str:
    if value == float("inf"):
        return "sinirsiz"
    if value >= 1000.0:
        return f"{value / 1000.0:.2f} km"
    return f"{value:.0f} m"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rover-id", default="lpr_1")
    # The same traversable pair the LiDAR comparison uses on the shipped
    # 500x500 / 5 m-px grid.
    parser.add_argument("--start", type=int, nargs=2, default=(150, 150))
    parser.add_argument("--goal", type=int, nargs=2, default=(400, 400))
    parser.add_argument("--sigma0", type=float, default=1.0,
                        help="1-sigma position uncertainty right after an "
                        "absolute fix, metres.")
    parser.add_argument("--out", default="docs/research/localization_budget.md")
    args = parser.parse_args()

    grids = load_preprocessed_grids()
    rover = get_rover(args.rover_id)
    start, goal = tuple(args.start), tuple(args.goal)

    plan = astar(grids, start, goal, rover=rover)
    if plan["error"]:
        raise SystemExit(f"planning failed: {plan['error']}")

    corridor = build_corridor(plan["path_pixels"], grids, rover)
    widths = list(corridor.half_width_m)
    median_w = statistics.median(widths)
    min_w = min(widths)
    route_m = float(plan["metrics"]["total_distance_m"])

    budgets = [
        budget_for_source(source, rate, median_w, sigma_0_m=args.sigma0, note=note)
        for source, rate, note in DRIFT_RATES
    ]
    worst_case = [
        budget_for_source(source, rate, min_w, sigma_0_m=args.sigma0, note=note)
        for source, rate, note in DRIFT_RATES
    ]

    lines = [
        "# Lokalizasyon belirsizlik butcesi",
        "",
        f"*Uretim: `scripts/localization_budget.py` - {date.today().isoformat()}*",
        "",
        f"Rota: `{start}` -> `{goal}`, {args.rover_id}, "
        f"{route_m / 1000.0:.2f} km, {len(widths)} segment.",
        "",
        f"Koridor yari genisligi: medyan **{median_w:.1f} m**, "
        f"minimum **{min_w:.1f} m**.",
        f"Sifirlama sonrasi baslangic belirsizligi (sigma_0): {args.sigma0:.1f} m.",
        "",
        "`check_localization_uncertainty` tetikleyicisi, kovaryans koridor",
        "yari genisligini astiginda ATES ALIR. Asagidaki mesafeler, her",
        "kaynagin NOMINAL calisirken bile bu tetikleyiciyi garantiyle",
        "atesleyecegi yol uzunlugudur - yani iki mutlak konum sifirlamasi",
        "arasindaki azami mesafe butcesi.",
        "",
        "## Medyan koridor genisligine gore",
        "",
        "| Odometri kaynagi | Drift orani | Sifirlamasiz mesafe | Rota buna sigar mi? |",
        "|---|---|---|---|",
    ]
    for budget in budgets:
        fits = "evet" if budget.distance_m >= route_m else "**hayir**"
        lines.append(
            f"| {budget.source} | %{100.0 * budget.drift_rate:g} | "
            f"{_fmt_m(budget.distance_m)} | {fits} |"
        )
    lines += [
        "| skyline/sun-sensor sifirlamali | fix'ler arasinda birikir | "
        "her guvenilir fix'te sifirlanir | evet (fix araligina bagli) |",
        "",
        "## En dar segmente gore (kotu durum)",
        "",
        "| Odometri kaynagi | Sifirlamasiz mesafe |",
        "|---|---|",
    ]
    for budget in worst_case:
        lines.append(f"| {budget.source} | {_fmt_m(budget.distance_m)} |")

    lines += [
        "",
        "## Kaynaklar",
        "",
    ]
    for _source, _rate, note in DRIFT_RATES:
        lines.append(f"- {note}")

    lines += [
        "",
        "## Sinirlar - bu tablo ne DEGILDIR",
        "",
        "- Drift oranlari baska araclarin baska zeminlerdeki yayinlanmis",
        "  degerleridir; bu rover ve bu regolit icin kalibre edilmemistir.",
        "- Buyume modeli dogrusaldir (`sigma = sigma_0 + oran x mesafe`),",
        "  cunku yayinlanan rakamlar 'mesafenin yuzdesi' bicimindedir;",
        "  gercek hata buyumesi arazi bagimli ve kismen stokastiktir.",
        "- 'Sifirlamasiz mesafe' bir garanti degil, tetikleyicinin nominal",
        "  kosulda dahi atesleyecegi ust siniridir.",
        "- Skyline sifirlamasi yalnizca `ambiguity_ratio` esigi gecen",
        "  guvenilir eslesmelerde drift'i sifirlar; duz arazide fix",
        "  reddedilir ve butce dead-reckoning/VO satirlarina geri duser",
        "  (bkz. `backend/app/skyline.py`).",
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
