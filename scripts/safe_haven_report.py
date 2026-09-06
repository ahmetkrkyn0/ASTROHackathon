#!/usr/bin/env python3
"""Measure LunaPath's Safe Haven map on the checked-in grid, per rover (A1).

VIPER's rule (Shirley & Balaban 2022): a safe haven is a place where, while
the Earth is below the horizon, the continuous shadow never exceeds the
rover's minimum-power endurance (50 h for VIPER) and the rover can generate
power while parked. LunaPath carries the endurance per rover as
``h_max_shadow_h`` (LPR-1 50 h, NASA VIPER 96 h, LUVMI-M 4 h, Yutu-2 2 h),
so the same site yields a different map for each profile -- this script
measures how much, and how it changes from one lunar day to the next
(NASA's own maps are per lunar day: the phase between the Earth's setting
and the Sun's drifts by about two days a month).

There is no external product to validate the map against (the rule itself
is NASA's); what this reports is the map's size, the driving time to the
nearest haven, and the endurance a rover would need for the site to offer
havens at all. Needs the processed grids, ``horizon_map.npy`` and the NAIF
kernels; without them it says so and exits 0. It never fabricates numbers.

Writes a Markdown report (default docs/research/safe_haven_report.md).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.constants import ROVERS, get_rover  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.illumination_series import _parse_start_utc, horizon_cache_path  # noqa: E402
from app.rover_grids import grids_for_rover  # noqa: E402
from app.safe_haven import (  # noqa: E402
    DEFAULT_SAFE_HAVEN_SPAN_HOURS,
    DEFAULT_SAFE_HAVEN_STEP_HOURS,
    build_safe_haven_map,
    safe_haven_for_grids,
    safe_haven_mask,
)

_ROOT = Path(__file__).resolve().parent.parent
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

_NO_HORIZON = """
Ufuk kubu bulunamadi (horizon_map.npy, islenmis gridlerin yaninda).

Once scripts/build_horizon_cache.py calistirin. Bu script ufuk kubu olmadan
safe haven haritasi uretmez.
"""

_NO_KERNELS = f"""
NAIF cekirdekleri bulunamadi: {_KERNELS}

Gunes ve Dunya konumlari SPICE ile hesaplanir; cekirdekler olmadan harita
uretilmez. Kurulum icin docs/frontend/3b-veri-sozlesmesi.md "Kurulum" bolumune bakin.
"""


def _percentiles(values: np.ndarray) -> dict[str, float | None]:
    if values.size == 0:
        return {"mean": None, "median": None, "p90": None, "max": None}
    return {
        "mean": float(np.mean(values)),
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "max": float(np.max(values)),
    }


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}".replace(".", ",")


def _endurance_for(dark: np.ndarray, share: float) -> float | None:
    """Endurance (h) at which *share* of the lit, traversable cells qualify."""
    if dark.size == 0:
        return None
    return float(np.percentile(dark, 100.0 * share))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--start-utc", default="2026-09-07T00:00:00")
    parser.add_argument("--span-hours", type=float, default=DEFAULT_SAFE_HAVEN_SPAN_HOURS)
    parser.add_argument("--step-hours", type=float, default=DEFAULT_SAFE_HAVEN_STEP_HOURS)
    parser.add_argument("--months", type=int, default=13, help="lunar days to sweep from start-utc")
    parser.add_argument("--rovers", nargs="*", default=list(ROVERS))
    parser.add_argument("--out", default=str(_ROOT / "docs" / "research" / "safe_haven_report.md"))
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    if not _KERNELS.exists():
        print(_NO_KERNELS)
        return 0
    grids = load_preprocessed_grids()
    metadata = grids["metadata"]
    cache_path = horizon_cache_path(metadata)
    if cache_path is None:
        print(_NO_HORIZON)
        return 0

    # ── the given lunar day, per rover ─────────────────────────────────────
    rows_out: list[dict] = []
    site: dict = {}
    for rover_id in args.rovers:
        rover = get_rover(rover_id)
        t0 = time.perf_counter()
        layers, tts, info = safe_haven_for_grids(
            grids, rover_id, args.start_utc,
            span_hours=args.span_hours, step_hours=args.step_hours,
        )
        elapsed = time.perf_counter() - t0
        if layers is None:
            print(f"{rover_id}: safe haven map unavailable: {info.get('reason')}")
            return 0
        traversable = np.asarray(grids_for_rover(grids, rover_id)["traversable"], dtype=bool)
        finite = np.isfinite(tts) & traversable
        dark = layers["max_dark_hours_without_dte"][traversable]
        row = {
            "rover_id": rover_id,
            "name": rover["name"],
            "h_max_shadow_h": float(rover["h_max_shadow_h"]),
            "traversable_cells": int(traversable.sum()),
            "safe_haven_cells": int(info["safe_haven_cells"]),
            "safe_haven_fraction": float(info["safe_haven_fraction"]),
            "reachable_fraction": float(finite.sum() / max(1, traversable.sum())),
            "time_to_haven_h": _percentiles(tts[finite]),
            "max_dark_without_dte_h": _percentiles(dark),
            "min_dark_without_dte_h": float(dark.min()) if dark.size else None,
            "cells_over_endurance": int((dark > float(rover["h_max_shadow_h"])).sum()),
            "never_lit_cells": int((~layers["ever_lit"] & traversable).sum()),
            "seconds": elapsed,
        }
        rows_out.append(row)
        print(
            f"{rover['name']:<18} endurance {row['h_max_shadow_h']:>5.0f} h  "
            f"havens {row['safe_haven_cells']:>6d} / {row['traversable_cells']} "
            f"({100 * row['safe_haven_fraction']:.2f}%)  "
            f"tts median {_fmt(row['time_to_haven_h']['median'])} h  "
            f"reachable {100 * row['reachable_fraction']:.1f}%  [{elapsed:.1f} s]"
        )
        if not site:
            below = layers["earth_below_hours"]
            site = {
                "earth_below_fraction": float(info["earth_below_fraction"]),
                "earth_below_hours": _percentiles(below[traversable]),
                "n_steps": int(info["n_steps"]),
            }

    # ── the sweep: one lunar day after another ─────────────────────────────
    # One tally per month (the Sun and the Earth do not care which rover is
    # asking); each rover's mask is the tally against its own endurance and
    # its own traversable mask.
    horizon = np.load(cache_path, mmap_mode="r")
    reference = get_rover(args.rovers[0])
    traversables = {
        rover_id: np.asarray(grids_for_rover(grids, rover_id)["traversable"], dtype=bool)
        for rover_id in args.rovers
    }
    start = _parse_start_utc(args.start_utc)
    sweep: list[dict] = []
    for month in range(int(args.months)):
        epoch = start + timedelta(hours=args.span_hours * month)
        epoch_utc = epoch.strftime("%Y-%m-%dT%H:%M:%S")
        layers, info = build_safe_haven_map(
            horizon, metadata, traversables[args.rovers[0]], reference, epoch_utc,
            span_hours=args.span_hours, step_hours=args.step_hours,
        )
        any_traversable = np.zeros(layers["ever_lit"].shape, dtype=bool)
        for mask in traversables.values():
            any_traversable |= mask
        lit_dark = layers["max_dark_hours_without_dte"][layers["ever_lit"] & any_traversable]
        entry = {
            "start_utc": epoch_utc,
            "earth_below_fraction": float(info["earth_below_fraction"]),
            "ever_lit_fraction": float(layers["ever_lit"][any_traversable].mean()),
            "min_dark_without_dte_h": float(lit_dark.min()) if lit_dark.size else None,
            "endurance_for_1pct_h": _endurance_for(lit_dark, 0.01),
            "endurance_for_10pct_h": _endurance_for(lit_dark, 0.10),
            "endurance_for_50pct_h": _endurance_for(lit_dark, 0.50),
            "safe_haven_fraction": {},
        }
        for rover_id in args.rovers:
            rover = get_rover(rover_id)
            mask = safe_haven_mask(
                layers["max_dark_hours_without_dte"], layers["ever_lit"],
                traversables[rover_id], float(rover["h_max_shadow_h"]),
            )
            entry["safe_haven_fraction"][rover_id] = float(
                mask[traversables[rover_id]].mean()
            )
        sweep.append(entry)
        print(
            f"{epoch_utc[:10]}  min dark {_fmt(entry['min_dark_without_dte_h'], 0)} h  "
            f"endurance for 1%/10%/50%: {_fmt(entry['endurance_for_1pct_h'], 0)} / "
            f"{_fmt(entry['endurance_for_10pct_h'], 0)} / {_fmt(entry['endurance_for_50pct_h'], 0)} h  "
            + "  ".join(
                f"{rid} {100 * frac:.2f}%" for rid, frac in entry["safe_haven_fraction"].items()
            )
        )

    # ── the report ─────────────────────────────────────────────────────────
    span_days = args.span_hours / 24.0
    lines = [
        "# Safe Haven haritasi -- rover profiline ve Ay gunune gore olcum (A1)",
        "",
        f"Uretildi: `scripts/safe_haven_report.py`. Pencere: {args.start_utc} baslangic, "
        f"{_fmt(args.span_hours, 1)} saat ({_fmt(span_days, 1)} gun, bir sinodik ay), "
        f"adim {_fmt(args.step_hours, 1)} saat ({site.get('n_steps')} ornek). "
        f"Grid: {metadata['shape'][0]}x{metadata['shape'][1]} @ {metadata['resolution_m']} m "
        "(Site11, de Gerlache rim), ufuk kubu iki olcekli (5 m yakin + LOLA 40 m uzak, 150 km).",
        "",
        "Kural (NASA VIPER, Shirley & Balaban 2022; Ennico-Smith vd. 2023): *Dunya ufkun "
        "altindayken kesintisiz golge suresi rover'in dayanimini (`h_max_shadow_h`) "
        "asmayan ve pencere icinde en az bir kez aydinlanan, gecilebilir hucre*. "
        "Karanlik yalnizca Dunya'nin gorunmedigi adimlarda sayilir; Dunya gorunurken "
        "rover komutla baska yere tasinabilir.",
        "",
        f"## Ay gunu {args.start_utc[:10]} -- site",
        "",
        "| Olcum | Deger |",
        "|---|---|",
        f"| Dunya-yok adim kesri (tum hucreler, ortalama) | {_fmt(100 * site['earth_below_fraction'], 1)} % |",
        f"| Dunya-yok saat, gecilebilir hucreler (medyan / p90 / maks) | "
        f"{_fmt(site['earth_below_hours']['median'], 0)} / {_fmt(site['earth_below_hours']['p90'], 0)} / "
        f"{_fmt(site['earth_below_hours']['max'], 0)} h |",
        "",
        f"## Ay gunu {args.start_utc[:10]} -- rover profiline gore",
        "",
        "| Rover | Dayanim (h) | Gecilebilir | Safe haven | Kesir | SH'a ulasabilen | tts medyan / p90 (h) | "
        "Dunya-yok karanlik min / medyan / p90 (h) | Dayanimi asan | Hic aydinlanmayan | Sure (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows_out:
        tts_p = row["time_to_haven_h"]
        dark_p = row["max_dark_without_dte_h"]
        lines.append(
            f"| {row['name']} | {row['h_max_shadow_h']:g} | {row['traversable_cells']} | "
            f"{row['safe_haven_cells']} | {_fmt(100 * row['safe_haven_fraction'])} % | "
            f"{_fmt(100 * row['reachable_fraction'], 1)} % | "
            f"{_fmt(tts_p['median'])} / {_fmt(tts_p['p90'])} | "
            f"{_fmt(row['min_dark_without_dte_h'], 0)} / {_fmt(dark_p['median'], 0)} / {_fmt(dark_p['p90'], 0)} | "
            f"{row['cells_over_endurance']} | {row['never_lit_cells']} | {_fmt(row['seconds'], 1)} |"
        )
    lines += [
        "",
        "Sutunlar: *Safe haven* = kurali saglayan gecilebilir hucre sayisi; *SH'a ulasabilen* = "
        "kapili surus grafi uzerinden (adim egimi, yanal egim, kose kesme) sonlu surede bir SH'a "
        "varabilen gecilebilir hucrelerin kesri; *tts* = en yakin SH'a surus suresi "
        "(`edge_travel_time_s`, egime bagli, aydinlanmadan bagimsiz); *Dayanimi asan* = "
        "Dunya-yok karanligi dayanimdan uzun olan gecilebilir hucreler; *Hic aydinlanmayan* = "
        "pencere boyunca hic Gunes gormeyen gecilebilir hucreler (kural geregi SH olamaz).",
        "",
        f"## Ay gunune gore tarama ({len(sweep)} sinodik ay)",
        "",
        "Dunya'nin batis-dogus dongusu (~27,3 gun) ile Gunes'inki (29,5 gun) arasindaki faz "
        "her ay ~2 gun kayar; bu yuzden NASA safe haven haritalarini Ay gunu basina uretir. "
        "*Gerekli dayanim*: aydinlanan gecilebilir hucrelerin %1 / %10 / %50'sinin SH sayilmasi "
        "icin rover'in tasimasi gereken kesintisiz-golge dayanimi.",
        "",
        "| Ay gunu | Dunya-yok kesri | Aydinlanan kesir | En kisa Dunya-yok karanlik (h) | "
        "Gerekli dayanim %1 / %10 / %50 (h) | "
        + " | ".join(f"SH {get_rover(rid)['name']} ({get_rover(rid)['h_max_shadow_h']:g} h)" for rid in args.rovers)
        + " |",
        "|---|---|---|---|---|" + "---|" * len(args.rovers),
    ]
    for entry in sweep:
        lines.append(
            f"| {entry['start_utc'][:10]} | {_fmt(100 * entry['earth_below_fraction'], 1)} % | "
            f"{_fmt(100 * entry['ever_lit_fraction'], 1)} % | {_fmt(entry['min_dark_without_dte_h'], 0)} | "
            f"{_fmt(entry['endurance_for_1pct_h'], 0)} / {_fmt(entry['endurance_for_10pct_h'], 0)} / "
            f"{_fmt(entry['endurance_for_50pct_h'], 0)} | "
            + " | ".join(f"{_fmt(100 * entry['safe_haven_fraction'][rid])} %" for rid in args.rovers)
            + " |"
        )
    lines += [
        "",
        "Yorum: bu sitede Dunya'nin ufkun altinda oldugu iki hafta, sitenin tamaminin "
        "gunlerce karanlik kaldigi Ay gecesiyle cakisir; bu yuzden safe haven **nadirdir** -- "
        "NASA'nin VIPER icin soyledigi gibi (\"SH'lar misyonu uzatan asil kaynaktir ve azdir\"). "
        "Dayanim kisaldikca harita buzulur; ayni site, ayni ay, dort farkli SH kumesi. "
        "Dis dogrulama urunu yoktur; kural ve esikler NASA belgelerinden birebir alinmistir.",
        "",
        "Yeniden uretmek: `python scripts/safe_haven_report.py --start-utc "
        f"{args.start_utc} --months {args.months}` (ufuk kubu ve NAIF cekirdekleri gerekir).",
        "",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "site": site, "rovers": rows_out, "sweep": sweep,
                    "start_utc": args.start_utc, "span_hours": args.span_hours,
                    "step_hours": args.step_hours,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
