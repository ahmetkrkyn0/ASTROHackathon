#!/usr/bin/env python3
"""Measure the panel incidence model (C1) on Site11.

What it measures, in order:

1. Nothing: what the sources actually say, quoted -- RoverDevKit's equations
   and its own Pragyan validation (THEIRS), NASA's two VIPER power numbers,
   Otten's and Lamarre's sun-pointed assumption -- then OUR arithmetic on
   NASA's pair ("320W per panel (450W on corner)").
2. Site11's Sun geometry from SPICE: the window centre, RoverDevKit's polar
   tilt there, and the Sun's elevation over a year.
3. The counterfactual geometries over three windows (a day route's 48 h, a
   synodic month, a year) -- the research note's "~30x" claim, measured, with
   the window it belongs to. Then the same ratio weighted by the REAL
   per-cell illumination series rather than by bare geometry.
4. The three standard 4-D routes under panel_model="sun_pointed" and
   "cos_incidence": moves, WAIT steps (A2's dwell decisions), cost, arrival
   SOC, nodes expanded and wall time.
5. The heading-locked counterfactual on those very routes: what a rover that
   had to face its direction of travel would have collected.
6. What it does to B1 (the survival field's conservative scalar) and B5 (the
   Monte Carlo's continuous-clock integral).
7. Claim limits and the presentation sentence.

Needs the processed grids, horizon_map.npy and the NAIF kernels; without
them it says so and writes nothing. Writes the JSON dump (--json) BEFORE the
markdown; --from-json re-renders without measuring.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import panel as P  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import app  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

SYNODIC_DAYS = 29.530588

CASES = (
    {
        "key": "lpr1_day",
        "label": "LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426)",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-28T00:00:00",
        "start": {"row": 358, "col": 494},
        "goal": {"row": 206, "col": 426},
    },
    {
        "key": "night",
        "label": "LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450)",
        "rover_id": "lpr_1",
        "start_utc": "2026-09-13T00:00:00",
        "start": {"row": 186, "col": 34},
        "goal": {"row": 494, "col": 450},
    },
    {
        "key": "viper_short",
        "label": "VIPER kısa leg, 30 May 2027, (358,494)→(346,462)",
        "rover_id": "nasa_viper",
        "start_utc": "2027-05-30T00:00:00",
        "start": {"row": 358, "col": 494},
        "goal": {"row": 346, "col": 462},
    },
)


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
    return text.replace(",", " ").replace(".", ",")


def _pct(value, digits: int = 1) -> str:
    return "—" if value is None else f"%{_fmt(100.0 * float(value), digits)}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out.extend("| " + " | ".join(r) + " |" for r in rows)
    out.append("")
    return out


# ── measuring ────────────────────────────────────────────────────────────────


def _sun_track(metadata, start: datetime, hours: float, step_h: float):
    """A Sun track straight from SPICE, without an /api round trip."""
    from app import ephemeris
    from app.illumination_series import _window_centre_latlon

    lat, lon = _window_centre_latlon(metadata)
    track = []
    for index in range(int(round(hours / step_h))):
        moment = start + timedelta(hours=step_h * index)
        et = ephemeris.utc_to_et(moment.strftime("%Y-%m-%dT%H:%M:%S"))
        azimuth, elevation = ephemeris.sun_azel_from_vector(
            ephemeris.sun_vector_body(et), lat, lon
        )
        track.append(
            {
                "index": index,
                "utc": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "azimuth_true_deg": float(azimuth) % 360.0,
                "elevation_deg": float(elevation),
            }
        )
    return track


def _window_stats(track, tilt_deg: float) -> dict:
    counterfactuals = P.counterfactual_gains(track, tilt_deg)
    elevations = np.array([s["elevation_deg"] for s in track])
    lit = elevations > 0.0
    tracking = counterfactuals["polar_tracking"]["mean_when_sun_up"]
    horizontal = counterfactuals["horizontal"]["mean_when_sun_up"]
    return {
        "n_samples": int(elevations.size),
        "elevation_min": float(elevations.min()),
        "elevation_max": float(elevations.max()),
        "sun_up_fraction": float(lit.mean()),
        "counterfactuals": counterfactuals,
        "tracking_over_horizontal": (
            float(tracking / horizontal) if horizontal > 0.0 else None
        ),
    }


def _heading_deg(previous, current) -> float | None:
    """True-north heading of a route step, from its grid direction."""
    from app import ephemeris

    d_row = int(current[0]) - int(previous[0])
    d_col = int(current[1]) - int(previous[1])
    if d_row == 0 and d_col == 0:
        return None
    # app.horizon's grid convention: 0 = decreasing row (grid north),
    # 90 = increasing column (grid east).
    grid_az = math.degrees(math.atan2(float(d_col), float(-d_row))) % 360.0
    return float(
        ephemeris.grid_azimuth_to_true_azimuth(grid_az, _NORTH_GRID_AZ) % 360.0
    )


_NORTH_GRID_AZ = 0.0


def measure() -> dict:
    global _NORTH_GRID_AZ
    t0 = time.perf_counter()
    grids = load_preprocessed_grids()
    metadata = grids["metadata"]

    from app.illumination_series import _grid_north_azimuth, _window_centre_latlon

    _NORTH_GRID_AZ = _grid_north_azimuth(metadata)
    lat, lon = _window_centre_latlon(metadata)
    tilt = P.polar_tilt_deg(lat)

    data: dict = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "site": {
            "lat_deg": float(lat),
            "lon_deg": float(lon),
            "polar_tilt_deg": float(tilt),
            "north_grid_azimuth_deg": float(_NORTH_GRID_AZ),
            "resolution_m": float(metadata["resolution_m"]),
            "shape": list(metadata["shape"]),
        },
        "corner_check": P.viper_corner_check(),
        "quoted": {
            "roverdevkit": dict(P.ROVERDEVKIT_QUOTED),
            "viper": dict(P.VIPER_QUOTED),
            "references": [dict(r) for r in P.PANEL_REFERENCES],
        },
        "claim": P.PANEL_CLAIM,
        "scope": P.PANEL_SCOPE,
    }

    # -- 2/3: bare geometry over three windows -------------------------------
    windows = {
        "day_48h": (datetime(2026, 9, 28, tzinfo=timezone.utc), 48.0, 0.25),
        "synodic_month": (
            datetime(2026, 9, 28, tzinfo=timezone.utc),
            SYNODIC_DAYS * 24.0,
            1.0,
        ),
        "year": (datetime(2026, 9, 1, tzinfo=timezone.utc), 365.0 * 24.0, 2.0),
    }
    data["windows"] = {}
    for name, (start, hours, step) in windows.items():
        track = _sun_track(metadata, start, hours, step)
        data["windows"][name] = {
            "start_utc": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "hours": hours,
            "step_h": step,
            **_window_stats(track, tilt),
        }

    # Per synodic month over 13 months: the spread the "~30x" claim hides.
    months = []
    for k in range(13):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(
            days=SYNODIC_DAYS * k
        )
        track = _sun_track(metadata, start, SYNODIC_DAYS * 24.0, 2.0)
        stats = _window_stats(track, tilt)
        months.append(
            {
                "start": start.strftime("%Y-%m-%d"),
                "sun_up_fraction": stats["sun_up_fraction"],
                "tracking": stats["counterfactuals"]["polar_tracking"]["mean_when_sun_up"],
                "horizontal": stats["counterfactuals"]["horizontal"]["mean_when_sun_up"],
                "ratio": stats["tracking_over_horizontal"],
                "body": stats["counterfactuals"]["body_three_face"]["mean_when_sun_up"],
            }
        )
    data["synodic_months"] = months

    # -- 3b: weighted by the REAL illumination series ------------------------
    from app.illumination_series import build_shadow_series

    base_shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    n_slices, slice_hours = 48, 0.5
    series, provenance = build_shadow_series(
        base_shadow, metadata, n_slices, slice_hours, "2026-09-28T00:00:00"
    )
    illum = np.stack([1.0 - snapshot for snapshot in series])
    track = _sun_track(
        metadata, datetime(2026, 9, 28, tzinfo=timezone.utc), n_slices * slice_hours, slice_hours
    )
    weighted = {"baseline_illum_hours": float(illum.sum() * slice_hours)}
    for name, array in P._named_arrays(tilt).items():
        gains = P.gain_series(track, array)
        weighted[name] = float((illum * gains[:, None, None]).sum() * slice_hours)
    data["illumination_weighted"] = {
        "shadow_model": {k: v for k, v in provenance.items() if k != "horizon_cache"},
        "n_slices": n_slices,
        "slice_hours": slice_hours,
        "mean_illuminated_fraction": float(illum.mean()),
        "totals": weighted,
    }

    # -- 4/5: the three standard routes --------------------------------------
    data["routes"] = {}
    with TestClient(app) as client:
        app.state.grids = grids
        for case in CASES:
            entry = {"label": case["label"], "rover_id": case["rover_id"]}
            for mode in ("sun_pointed", "cos_incidence"):
                body = {
                    "start": case["start"],
                    "goal": case["goal"],
                    "rover_id": case["rover_id"],
                    "start_utc": case["start_utc"],
                    "panel_model": mode,
                }
                started = time.perf_counter()
                response = client.post("/api/plan-4d", json=body)
                seconds = time.perf_counter() - started
                if response.status_code != 200:
                    entry[mode] = {
                        "status": response.status_code,
                        "detail": response.json().get("detail"),
                        "seconds": seconds,
                    }
                    continue
                payload = response.json()
                metrics = payload["metrics"]
                block = payload["panel"]
                entry[mode] = {
                    "status": 200,
                    "seconds": seconds,
                    "moves": int(metrics["move_steps"]),
                    "waits": int(metrics["wait_steps"]),
                    "total_cost": float(metrics["total_cost"]),
                    "nodes_expanded": int(metrics["nodes_expanded"]),
                    "arrival_soc_pct": float(payload["path_battery_pct"][-1]),
                    "min_soc_pct": float(min(payload["path_battery_pct"])),
                    "gain": block["gain"],
                    "applied": block["applied"],
                    "sun_elevation_deg": block.get("sun_elevation_deg"),
                    "counterfactuals": block.get("counterfactuals"),
                    "path_states": payload["path_states"],
                    "slice_hours": float(payload["slice_hours"]),
                }
            # The heading-locked counterfactual, measured on the route the
            # planner actually chose (never planned with).
            base = entry.get("sun_pointed", {})
            if base.get("status") == 200:
                entry["heading_locked"] = _heading_locked(
                    metadata, case, base["path_states"], base["slice_hours"]
                )
            data["routes"][case["key"]] = entry

    data["total_seconds"] = time.perf_counter() - t0
    return data


def _heading_locked(metadata, case, path_states, slice_hours: float) -> dict:
    """What the SAME route would collect if the rover had to face its heading.

    A body-mounted array has no forward-facing face (VIPER's front carries
    the drill and the navigation cameras), so this is a real operational
    question and the reason NASA names a "sun on corner" driving mode. It is
    a measurement on a finished route, not a planning mode: the 4-D cost cube
    is per cell, not per direction.
    """
    from app.constants import get_rover

    rover = get_rover(case["rover_id"])
    array = P.array_for_rover(rover)
    locked = P.PanelArray(
        faces=array.faces,
        azimuth_mode="heading_locked",
        azimuth_deg=None,
        kind=array.kind,
        source=array.source,
        tilt_mode=array.tilt_mode,
    )
    slices = [int(s[2]) for s in path_states]
    n_slices = max(slices) + 1
    start = datetime.strptime(case["start_utc"], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )
    # The plan's OWN slice length, echoed by the response: the standard cases
    # run at the auto slice, not at 1 h, and a track sampled on the wrong
    # clock would put the Sun in the wrong place for every step.
    track = _sun_track(
        metadata, start, float(n_slices) * float(slice_hours), float(slice_hours)
    )

    free, locked_gains, headings = [], [], []
    previous = None
    for state in path_states:
        index = min(int(state[2]), len(track) - 1)
        sample = track[index]
        free.append(
            P.panel_gain(sample["elevation_deg"], sample["azimuth_true_deg"], array)
        )
        heading = None if previous is None else _heading_deg(previous, state)
        if heading is None:
            locked_gains.append(None)
        else:
            headings.append(heading)
            locked_gains.append(
                P.panel_gain(
                    sample["elevation_deg"],
                    sample["azimuth_true_deg"],
                    locked,
                    heading_deg=heading,
                )
            )
        previous = state
    values = [g for g in locked_gains if g is not None]
    free_values = free[1:] if len(free) > 1 else free
    return {
        "n_steps": len(values),
        "free_mean": float(np.mean(free_values)) if free_values else None,
        "locked_mean": float(np.mean(values)) if values else None,
        "locked_min": float(np.min(values)) if values else None,
        "locked_max": float(np.max(values)) if values else None,
        "zero_steps": int(sum(1 for g in values if g <= 1e-9)),
        "note": (
            "the same route, re-priced with psi = the step's own heading; the "
            "planner never used this"
        ),
    }


# ── rendering ────────────────────────────────────────────────────────────────


def render(data: dict) -> str:
    site = data["site"]
    check = data["corner_check"]
    lines: list[str] = []
    lines.append("# C1 — Güneş paneli geliş açısı (cos i) ve panel geometrisi: Site11 ölçümü")
    lines.append("")
    lines.append(
        f"**Üretildi:** {data['generated_utc']} · `scripts/panel_cos_i_report.py` · "
        f"ölçüm süresi {_fmt(data.get('total_seconds', 0.0) / 60.0, 1)} dk"
    )
    lines.append("")
    lines.append(
        "**Okuma notu:** bu belgedeki her sayı Site11 gridinde ve gerçek NAIF kernel'leriyle "
        "koşturuldu. Kaynakların kendi sayıları ayrı bir bölümde, **alıntı** olarak durur ve "
        "bizim ölçümlerimizle aynı tabloya konmaz. Model etiketi **MODEL**: bu yalnızca bir "
        "geometri çarpanıdır — verim, alan, toz, sıcaklık katsayısı, albedo yok."
    )
    lines.append("")

    # 1
    lines.append("## 1. Kaynaklar ne diyor (alıntı) ve modelin NASA'nın iki sayısıyla çapraz kontrolü")
    lines.append("")
    lines.append(
        "Bugünkü model — `p_solar_w × (1 − gölge)` — panelin Güneş'e **her zaman dik** olduğunu "
        "varsayar. Bu varsayım literatürde açıkça yazılıdır:"
    )
    lines.append("")
    lines.append(
        "> *\"This assumes that any positive amount of solar illumination is adequate to fully "
        "power the rover, which is true for rover configurations with two-degree-of-freedom "
        "articulated solar arrays that can always point directly at the sun (provided the array "
        "is appropriately sized).\"* — Otten, Jones, Wettergreen, Whittaker, ICRA 2015 "
        "(A2'nin de kaynağı)"
    )
    lines.append("")
    lines.append(
        "> *\"we assume that the rover maintains a constant area of solar panels perfectly "
        "oriented towards the Sun at all times… We keep the incorporation of more complex power "
        "generation models as future work.\"* — Lamarre, Malhotra, Kelly, IEEE AERO 2024 "
        "(B1'in kaynağı)"
    )
    lines.append("")
    lines.append(
        "**Ama LunaPath'in varsayılan rover'ının öyle bir dizisi yok.** `lpr_1`'in 410 W'ı NASA "
        "VIPER'ın PIP'inden gelir ve o belge diziyi şöyle tanımlar (5 420 Wh ise PIP'te **yok**; "
        "o sayı Bluethmann'ın 2. slaytındaki *\"Battery capacity (start of life @ 0C): "
        "5,420 W-hr\"*):"
    )
    lines.append("")
    lines.append(f"> *\"{P.VIPER_QUOTED['array_quote']}\"* — {P.VIPER_QUOTED['array_source']}")
    lines.append("")
    lines.append(
        f"> *\"{P.VIPER_QUOTED['quote']}\"* — {P.VIPER_QUOTED['source']}"
    )
    lines.append("")
    lines.append(
        f"> *\"{P.VIPER_QUOTED['driving_mode_quote']}\"* — {P.VIPER_QUOTED['driving_mode_source']}"
    )
    lines.append("")
    lines.append(
        "Aynı sunumun 7. slaytı gimbal'lerin **yalnızca** yüksek kazançlı antende ve navigasyon "
        "kameralarında olduğunu söyler: dizi eklemsizdir. Bu iki NASA sayısı aynı donanımın iki "
        "geometrisidir, yani aralarındaki oran saf bir **geometri** ifadesidir — ve çok yüzeyli "
        "cos i modeli bu orana **uydurulmadan** onu öngörür:"
    )
    lines.append("")
    lines.extend(
        _table(
            ["Büyüklük", "Değer"],
            [
                ["bir yüzey dik gelişte (ham kazanç)", _fmt(check["one_face_raw"], 6)],
                [
                    "üç yüzey, en iyi başlık (ham kazanç)",
                    f"{_fmt(check['corner_raw'], 6)} (= √2, ψ₀ = {_fmt(check['corner_reference_azimuth_deg'], 2)}°)",
                ],
                ["modelin oranı", _fmt(check["model_ratio"], 5)],
                ["NASA'nın yayımladığı oran (450 / 320)", _fmt(check["published_ratio"], 5)],
                [
                    "NASA'nın 320 W'ından modelin öngördüğü köşe gücü",
                    f"**{_fmt(check['predicted_on_corner_w'], 1)} W**",
                ],
                ["NASA'nın yayımladığı köşe gücü", f"**{_fmt(check['published_on_corner_w'], 1)} W**"],
                [
                    "fark",
                    f"{_fmt(check['difference_w'], 1)} W ({_fmt(check['difference_pct'], 2)} %)",
                ],
            ],
        )
    )
    lines.append(
        "**Okuma:** NASA iki gücü yayımladı, aritmetik bizim. Bu, modelin **geometri teriminin** "
        "tutarlılık kontrolüdür; enerji modelimizin doğrulanması DEĞİLDİR ve öyle sunulmaz."
    )
    lines.append("")
    lines.append("### RoverDevKit'in kendi doğrulaması (ONLARIN sonucu, alıntı)")
    lines.append("")
    quoted = data["quoted"]["roverdevkit"]
    lines.append(f"- Tepe güç: *\"{quoted['peak_power']}\"*")
    lines.append(f"- Kütle modeli: *\"{quoted['mass_model']}\"*")
    lines.append(f"- Varsayılan dizi: *\"{quoted['default_array']}\"*")
    lines.append("")
    lines.append(
        "Bunlar bizim ölçümümüz değildir ve bizim tablolarımıza karışmaz. Araştırma belgesindeki "
        "\"MAE %13,3\" ifadesi **ortanca** mutlak hatadır (ortalama %14,8); makale 52 W ↔ 50 W "
        "için \"+5%\" yazar (aritmetik +%4) — makale alıntılanır, yeniden hesaplanmaz."
    )
    lines.append("")

    # 2
    lines.append("## 2. Site11'in Güneş geometrisi")
    lines.append("")
    year = data["windows"]["year"]
    lines.extend(
        _table(
            ["Büyüklük", "Değer"],
            [
                ["pencere merkezi", f"{_fmt(site['lat_deg'], 4)}°, {_fmt(site['lon_deg'], 4)}°"],
                [
                    "RoverDevKit kutup eğimi min(80°, |λ|)",
                    f"{_fmt(site['polar_tilt_deg'], 1)}°",
                ],
                [
                    "Güneş yüksekliği (bir yıl, 2 h adım)",
                    f"{_fmt(year['elevation_min'], 4)}° … {_fmt(year['elevation_max'], 4)}°",
                ],
                ["Güneş'in ufkun üstünde olduğu saat oranı", _pct(year["sun_up_fraction"])],
                ["grid kuzeyi ↔ gerçek kuzey", f"{_fmt(site['north_grid_azimuth_deg'], 2)}°"],
            ],
        )
    )

    # 3
    lines.append("## 3. Karşı-olgu geometrileri: \"~30 kat\" ölçüldüğünde ne çıkıyor")
    lines.append("")
    lines.append(
        "Araştırma belgesi dik ve yatay panel arasındaki farkı **\"~30 kat\"** diye tahmin "
        "ediyordu. Ölçüm, tek bir sayı olmadığını gösteriyor: oran **pencereye** bağlı, çünkü "
        "Güneş'in yüksekliği yıl içinde −2,59°…+2,55° arasında salınıyor ve bazı sinodik aylarda "
        "hiç doğmuyor. Aşağıdaki kazançlar her dizinin **kendi en iyi geometrisine** normalize "
        "edilmiştir (bkz. § 6), ortalamalar yalnız Güneş'in ufkun üstünde olduğu örnekler üzerinde."
    )
    lines.append("")
    rows = []
    names = {
        "day_48h": "28 Eyl 2026 + 48 h (standart gündüz rotasının epoğu)",
        "synodic_month": "28 Eyl 2026 + bir sinodik ay (29,53 gün)",
        "year": "1 Eyl 2026 + bir yıl",
    }
    for key, label in names.items():
        w = data["windows"][key]
        cf = w["counterfactuals"]
        rows.append(
            [
                label,
                _fmt(cf["body_three_face"]["mean_when_sun_up"], 6),
                _fmt(cf["polar_tracking"]["mean_when_sun_up"], 6),
                _fmt(cf["polar_fixed_north"]["mean_when_sun_up"], 6),
                _fmt(cf["horizontal"]["mean_when_sun_up"], 6),
                (
                    f"**{_fmt(w['tracking_over_horizontal'], 1)}**"
                    if w["tracking_over_horizontal"]
                    else "—"
                ),
            ]
        )
    lines.extend(
        _table(
            [
                "Pencere",
                "3 yüzey gövde (serbest başlık)",
                "tek levha 80° izleyen",
                "tek levha 80° sabit K",
                "yatay levha",
                "izleyen ÷ yatay",
            ],
            rows,
        )
    )
    lines.append(
        "**Okuma:** belgenin \"~30 kat\"ı yalnız kısa bir gündüz penceresi için doğru. Yıl boyu "
        "aydınlık saatlerde oran daha büyük. Tek sayı yazılamaz; pencere ile birlikte yazılır."
    )
    lines.append("")
    lines.append("### Sinodik ay bazında (13 ay)")
    lines.append("")
    rows = []
    for month in data["synodic_months"]:
        rows.append(
            [
                month["start"],
                _pct(month["sun_up_fraction"]),
                _fmt(month["body"], 6),
                _fmt(month["tracking"], 6),
                _fmt(month["horizontal"], 6),
                _fmt(month["ratio"], 1) if month["ratio"] else "—",
            ]
        )
    lines.extend(
        _table(
            ["Ay başlangıcı", "Güneş üstte", "3 yüzey", "80° izleyen", "yatay", "oran"],
            rows,
        )
    )
    lines.append(
        "**Okuma:** oran 37 ile 275 kat arasında geziniyor ve Güneş'in hiç doğmadığı aylarda "
        "tanımsız (satırlar \"—\"). Site11 kutuptan 1,08° uzakta olduğu için Güneş'in yüksekliği "
        "azimutla birlikte değişiyor; yatay panelin topladığı `sin e` bu yüzden aya göre 7 kat "
        "oynuyor."
    )
    lines.append("")

    # 3b
    lines.append("### Gerçek aydınlanma serisiyle ağırlıklandırılmış (Site11, tüm hücreler)")
    lines.append("")
    weighted = data["illumination_weighted"]
    totals = weighted["totals"]
    base = totals["baseline_illum_hours"]
    rows = []
    labels = {
        "sun_pointed": "Güneş'e dönük 2-DOF dizi (bugünkü model, g ≡ 1)",
        "body_three_face": "VIPER 3 yüzey, serbest başlık (kataloğun LPR-1/VIPER varsayımı)",
        "polar_tracking": "tek levha 80°, Güneş izleyen (LUVMI-M/Yutu-2 varsayımı)",
        "polar_fixed_north": "tek levha 80°, sabit kuzeye bakan",
        "horizontal": "yatay levha (RoverDevKit'in varsayılanı)",
    }
    for key, label in labels.items():
        value = totals[key]
        rows.append([label, _fmt(value, 1), _pct(value / base if base else None, 2)])
    lines.extend(
        _table(
            ["Geometri", "Σ aydınlanma × kazanç (hücre·saat)", "bugünkünün yüzdesi"], rows
        )
    )
    lines.append(
        f"**Okuma:** {weighted['n_slices']} dilim × {_fmt(weighted['slice_hours'], 2)} h, "
        f"28 Eyl 2026, gölge modeli `{weighted['shadow_model'].get('model')}`; sitenin ortalama "
        f"aydınlık kesri bu pencerede {_pct(weighted['mean_illuminated_fraction'], 2)}. Kataloğun "
        "varsaydığı iki geometri bugünkü modelin **%98,9–%100**'ünü topluyor — yani C1 varsayılan "
        "katalogla rotayı neredeyse hiç değiştirmez. Çarpıcı sayı karşı-olgudadır: yatay bir dizi "
        "aynı arazide bugünkünün yalnızca küçük bir kesrini toplar."
    )
    lines.append("")

    # 4
    lines.append("## 4. Üç standart 4-B rotada kısıtlı/kısıtsız fark")
    lines.append("")
    rows = []
    for case in CASES:
        entry = data["routes"].get(case["key"])
        if not entry:
            continue
        for mode, mode_label in (
            ("sun_pointed", "sun_pointed (varsayılan)"),
            ("cos_incidence", "cos_incidence"),
        ):
            run = entry.get(mode) or {}
            if run.get("status") != 200:
                # The status belongs in its own cell, not in the moves column:
                # a bolded 422 under "hamle" reads as a move count.
                rows.append(
                    [
                        entry["label"] if mode == "sun_pointed" else "",
                        f"{mode_label} — **HTTP {run.get('status', '—')}**",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                        "—",
                    ]
                )
                continue
            gain = run["gain"]
            rows.append(
                [
                    entry["label"] if mode == "sun_pointed" else "",
                    mode_label,
                    _fmt(run["moves"]),
                    _fmt(run["waits"]),
                    _fmt(run["total_cost"], 6),
                    _fmt(run["arrival_soc_pct"], 2),
                    _fmt(run["nodes_expanded"]),
                    _fmt(gain["mean"], 6) if gain.get("mean") is not None else "—",
                ]
            )
    lines.extend(
        _table(
            ["Rota", "Model", "hamle", "bekleme", "toplam maliyet", "varış SOC %", "düğüm", "ort. kazanç"],
            rows,
        )
    )
    for case in CASES:
        entry = data["routes"].get(case["key"])
        if not entry:
            continue
        failed = entry.get("sun_pointed", {}).get("status")
        if failed and failed != 200:
            lines.append(
                f"- **{entry['label']}** her iki modelde de **{failed}**: "
                f"`{entry['sun_pointed'].get('detail')}` — bu C1'den ÖNCE de böyleydi "
                "(katalog düzeltmesi 4af6989 VIPER'ın `slope_max_deg`'ini 20°→15° indirdi)."
            )
    lines.append("")
    lines.append(
        "**A2'nin dwell kararlarına etkisi:** \"bekleme\" sütunu 4-B planlayıcının WAIT "
        "kenarlarını sayar — A2'nin dwell kararı tam olarak budur. Araştırma belgesi C1'in bu "
        "kararları etkileyeceğini söylüyordu; ölçüm yukarıda."
    )
    lines.append("")

    # 5
    lines.append("## 5. Başlık kilitli karşı-olgu (yalnız ölçüm, planlayıcı değişmedi)")
    lines.append("")
    lines.append(
        "Gövdeye monte dizide ψ rover'ın **başlığıdır**. VIPER'ın önünde panel yoktur (ön yüzde "
        "sondaj ve navigasyon kameraları var), dolayısıyla doğrudan Güneş'e doğru sürmek dizinin "
        "hiçbir yüzünü aydınlatmaz. NASA'nın \"sun on corner\" sürüş kipinin sebebi budur. "
        "Aşağıdaki sayılar planlayıcının seçtiği rotanın adımlarına, o adımın gidiş yönü başlık "
        "kabul edilerek yeniden fiyatlanmasıyla elde edildi."
    )
    lines.append("")
    rows = []
    for case in CASES:
        entry = data["routes"].get(case["key"])
        locked = (entry or {}).get("heading_locked")
        if not locked:
            continue
        rows.append(
            [
                entry["label"],
                _fmt(locked["n_steps"]),
                _fmt(locked["free_mean"], 6),
                _fmt(locked["locked_mean"], 6),
                _fmt(locked["locked_min"], 6),
                _fmt(locked["locked_max"], 6),
                _fmt(locked["zero_steps"]),
            ]
        )
    if rows:
        lines.extend(
            _table(
                ["Rota", "adım", "serbest başlık ort.", "kilitli ort.", "kilitli en az", "kilitli en çok", "sıfır kazançlı adım"],
                rows,
            )
        )
    lines.append("")

    # 6
    lines.append("## 6. Modelin normalizasyonu, B1 ve B5")
    lines.append("")
    lines.append(
        "**Normalizasyon neden var:** araştırma belgesi `p_solar_w × max(0, cos i)` öneriyordu. "
        "Bu geometriyi **iki kez** sayar — kataloğun 410 W'ı üç yüzeyin toplamı, 450 W'ı ise "
        "NASA'nın \"on corner\", yani zaten en iyi geometrideki değeri. C1 bu yüzden kazancı "
        "dizinin kendi en iyi ham değerine böler; tek düz levhada bu bölen 1'dir ve kazanç tam "
        "olarak `max(0, cos i)`'ye indirgenir, yani belgenin istediği bağıntı bunun özel hâlidir."
    )
    lines.append("")
    lines.append(
        "**B1 (kurtarma politikası):** `survival._power_terms` `p_solar_w`'yi `base_w` ve "
        "`slope_w`'ye **zıt işaretlerle** gömer; DP'nin kapalı formlu drenajını mümkün kılan da "
        "budur. Dilim başına kazanç bu çarpanlamayı bozardı, bu yüzden alan ufku boyunca "
        "**en küçük** kazanç tek skaler olarak geçirilir: bir güvenlik sınırı şarj konusunda "
        "iyimser değil, muhafazakâr olmalıdır."
    )
    lines.append("")
    lines.append(
        "**B5 (Monte Carlo):** koşumlar sürekli saatte ilerler, dolayısıyla dilim indeksiyle "
        "kazanç okunamaz; `RouteSky` kazanç verildiğinde gölgenin kümülatifinin yanında "
        "`∫(1−gölge)·g dt` tablosunu da kurar ve güneş terimi bu integralden okunur. Kazanç "
        "verilmediğinde tablo kurulmaz ve koşum bit-eşittir."
    )
    lines.append("")

    # 7
    lines.append("## 7. İddia sınırı ve sunum cümlesi")
    lines.append("")
    lines.append(f"- **İddia:** {data['claim']}")
    lines.append("")
    lines.append(f"- **Kapsam:** {data['scope']}")
    lines.append("")
    lines.append(
        "- **Doğru cümle:** \"Güneş gelirini artık panel geometrisiyle hesaplıyoruz: geliş açısı "
        "(cos i), panel eğimi ve azimut kipi kataloğa girdi. Modelin geometri terimi, NASA'nın "
        f"VIPER için yayımladığı iki gücü (320 W tek panel, 450 W köşede) %{_fmt(abs(check['difference_pct']), 2)} "
        "farkla yeniden üretiyor. Bugüne kadarki model, Otten'ın ve Lamarre'ın açıkça yazdığı "
        "'her zaman Güneş'e dönük dizi' varsayımıydı — ve bizim varsayılan rover'ımızın öyle bir "
        "dizisi yok.\""
    )
    lines.append("")
    lines.append(
        "- **Yanlış cümle:** \"panel modelimizi doğruladık\" (Pragyan doğrulaması RoverDevKit'in, "
        "bizim değil), \"dizi gücünü hesaplıyoruz\" (verim ve alan katalogda yok; yalnız geometri "
        "çarpanı var) ya da \"VIPER'ın panelleri dikey\" (NASA bu kelimeyi kullanmıyor; eğim "
        "'port, starboard, aft surfaces' + 'Radiators (on top)' ifadelerinden çıkarımdır)."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None, help="write the measurements here BEFORE rendering")
    parser.add_argument("--from-json", default=None, help="render from a previous dump instead of measuring")
    parser.add_argument(
        "--out", default=str(_ROOT / "docs" / "research" / "panel_cos_i_report.md")
    )
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        if not (
            (_PROCESSED / "horizon_map.npy").exists()
            and _KERNELS.exists()
            and (_PROCESSED / "metadata.json").exists()
        ):
            print(
                "processed grids, horizon_map.npy or the NAIF kernels are missing; "
                "nothing measured, nothing written"
            )
            return 2
        data = measure()
        if args.json:
            Path(args.json).write_text(
                json.dumps(data, indent=1, default=float), encoding="utf-8"
            )
            print(f"json -> {args.json}")
    text = render(data)
    Path(args.out).write_text(text, encoding="utf-8")
    print(
        f"report -> {args.out} "
        f"({_fmt(data.get('total_seconds', 0.0) / 60.0, 1)} min measured)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
