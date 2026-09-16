#!/usr/bin/env python3
"""Measure the cold-battery, heater-power and hibernation models (C2) on Site11.

What it measures, in order:

1. Nothing: what the sources actually say, quoted -- NASA Glenn's 200 K
   freeze point and recovery, ISRO's 14 days at -160 C, Surveyor 1's six
   cycles, NASA JSC's Stefan-Boltzmann law and their 26 percent -- then OUR
   arithmetic reproducing that 26 percent from their own law.
2. The catalogue calibration: the one heater coefficient each law needs, read
   out of p_heater_w under a stated sizing assumption, and the radiating area
   that implies.
3. Whether "dark means cold" is true on Site11. It is not, and the number is
   the point of the whole feature.
4. The three heater models compared cell by cell over the real grid: the
   SIGNED distribution, because the temperature law is not a bound on the
   exposure law in either direction.
5. The deliverable-capacity curve and the sweep of its unsourced shape.
6. The endurance: the catalogue's own internal inconsistency, and what the
   ratio model does with it.
7. Hibernation: the four profiles' dormant draws, and the three standard 4-D
   routes under every switch.
8. Claim limits and the presentation sentence.

Sections 1, 2, 5, 6 and the hibernation ranking need only the catalogue.
Sections 3, 4 and the routes need the processed grids and the NAIF kernels;
without them the script says so and writes nothing. Writes the JSON dump
(--json) BEFORE the markdown; --from-json re-renders without measuring.
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

from app import battery as B  # noqa: E402
from app.constants import ROVERS, THERMAL_MIN_TRAVERSABLE_C, get_rover  # noqa: E402
from app.cost_cube import hibernate_cost, wait_cost  # noqa: E402
from app.cost_engine import housekeeping_power_w, resolve_weights  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.main import app  # noqa: E402
from app.thermal_dwell import rover_envelope  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_KERNELS = _ROOT / "kernels" / "lunapath.tm"

ROUTES = (
    {
        "key": "lpr1_day",
        "label": "LPR-1, gunduz (28 Eyl 2026)",
        "body": {
            "start": {"row": 358, "col": 494},
            "goal": {"row": 206, "col": 426},
            "rover_id": "lpr_1",
            "start_utc": "2026-09-28T00:00:00",
        },
    },
    {
        "key": "lpr1_night",
        "label": "LPR-1, Ay gecesi (13 Eyl 2026)",
        "body": {
            "start": {"row": 186, "col": 34},
            "goal": {"row": 494, "col": 450},
            "rover_id": "lpr_1",
            "start_utc": "2026-09-13T00:00:00",
        },
    },
    {
        "key": "viper_short",
        "label": "NASA VIPER, kisa leg (30 May 2027)",
        "body": {
            "start": {"row": 358, "col": 494},
            "goal": {"row": 346, "col": 462},
            "rover_id": "nasa_viper",
            "start_utc": "2027-05-30T00:00:00",
        },
    },
)

SWITCHES = (
    ("default", {}),
    ("radiative", {"heater_model": "thermostat_assumed", "heater_power_model": "radiative"}),
    ("delta_t", {"heater_model": "thermostat_assumed", "heater_power_model": "delta_t"}),
    ("derated", {"battery_model": "temperature_derated"}),
    ("hibernate", {"allow_hibernate": True}),
    (
        "all_on",
        {
            "heater_model": "thermostat_assumed",
            "heater_power_model": "radiative",
            "battery_model": "temperature_derated",
            "allow_hibernate": True,
        },
    ),
)


def _sci(value) -> str:
    return "-" if value is None else f"{float(value):.4e}"


def _f(value, digits=3):
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "evet" if value else "hayir"
    try:
        return f"{float(value):,.{digits}f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


# ── the measurements ────────────────────────────────────────────────────────


def measure_catalogue() -> dict:
    """Sections 1, 2, 5, 6 and the hibernation ranking: catalogue only."""
    rows = []
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        envelope = rover_envelope(rover)
        coefficients = B.heater_coefficients(rover)
        available, hibernate_reason = B.hibernation_available(rover)
        rows.append(
            {
                "id": rover_id,
                "name": rover["name"],
                "p_heater_w": rover["p_heater_w"],
                "p_idle_w": rover["p_idle_w"],
                "p_shadow_w": rover["p_shadow_w"],
                "p_hibernate_w": rover["p_hibernate_w"],
                "e_cap_wh": rover["e_cap_wh"],
                "soc_min_pct": rover["soc_min_pct"],
                "h_max_shadow_h": rover["h_max_shadow_h"],
                "thermal_tau_s": rover["thermal_tau_s"],
                "envelope_lo": None if envelope is None else envelope.lo,
                "envelope_hi": None if envelope is None else envelope.hi,
                "envelope_lo_component": None if envelope is None else envelope.lo_component,
                "rating_c": B.battery_rating_c(rover),
                "curve_reason": B.usable_fraction_unavailable_reason(rover),
                "k_a": None if coefficients is None else coefficients.k_a,
                "es_a": None if coefficients is None else coefficients.es_a,
                "implied_area_m2": (
                    None if coefficients is None else coefficients.es_a / B.STEFAN_BOLTZMANN
                ),
                "hibernation": available,
                "hibernation_reason": hibernate_reason,
                "dark_rate": B.hibernate_dark_rate(rover) if available else None,
                # The endurance the catalogue's own capacity and shadow draw imply,
                # against the endurance it publishes.
                "implied_endurance_h": (
                    float(rover["e_cap_wh"]) * (1.0 - float(rover["soc_min_pct"]))
                    / housekeeping_power_w(1.0, rover)
                ),
            }
        )

    # The unsourced shape, swept. Reported as a sensitivity, never tuned.
    shape_rows = []
    lpr = get_rover("lpr_1")
    for exponent in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0):
        shape_rows.append(
            {
                "exponent": exponent,
                "f_at_minus_10": B.usable_fraction(-10.0, lpr, exponent),
                "f_at_minus_20": B.usable_fraction(-20.0, lpr, exponent),
                "f_at_minus_40": B.usable_fraction(-40.0, lpr, exponent),
                "h_at_minus_20": B.shadow_endurance_h(5420.0, -20.0, lpr, exponent),
                "h_at_minus_40": B.shadow_endurance_h(5420.0, -40.0, lpr, exponent),
            }
        )

    # The two heater laws across the surfaces Site11 actually offers.
    heater_rows = []
    for surface in (-150.0, -130.0, -110.0, -90.0, -70.0, -50.0, -30.0, -10.0, 0.0):
        row = {"surface_c": surface}
        for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
            rover = get_rover(rover_id)
            row[f"{rover_id}_delta_t"] = B.heater_power_w(surface, rover, "delta_t")
            row[f"{rover_id}_radiative"] = B.heater_power_w(surface, rover, "radiative")
        heater_rows.append(row)

    # What a dormant hour costs against a waiting hour, on the objective.
    cost_rows = []
    for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
        rover = get_rover(rover_id)
        weights = resolve_weights(None, rover)
        cost_rows.append(
            {
                "id": rover_id,
                "wait_dark": wait_cost(0.0, 1.0, rover, weights),
                "hibernate_dark": hibernate_cost(0.0, 1.0, rover, weights),
            }
        )

    return {
        "rovers": rows,
        "shape_sweep": shape_rows,
        "heater_by_surface": heater_rows,
        "dormant_vs_wait": cost_rows,
        "jsc_check": B.jsc_survival_temperature_check(),
        "nasa_glenn_quoted": dict(B.NASA_GLENN_QUOTED),
        "jsc_quoted": dict(B.JSC_QUOTED),
        "viper_quoted": dict(B.VIPER_QUOTED),
        "evidence_limit": dict(B.HIBERNATION_EVIDENCE_LIMIT),
        "freeze_c": B.BATTERY_FREEZE_C,
        "sizing_surface_c": THERMAL_MIN_TRAVERSABLE_C,
    }


def measure_grid(grids) -> dict:
    """Sections 3 and 4: is 'dark means cold' true, and what the laws do here."""
    from scipy.stats import spearmanr

    traversable = np.asarray(grids["traversable"], dtype=bool)
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[traversable]
    surface = np.asarray(grids["thermal"], dtype=np.float64)[traversable]
    finite = np.isfinite(shadow) & np.isfinite(surface)

    correlation = float(spearmanr(shadow[finite], surface[finite]).correlation)
    pockets = []
    for shadow_max, surface_max in ((0.2, -100.0), (0.3, -80.0), (0.5, -50.0)):
        mask = finite & (shadow < shadow_max) & (surface < surface_max)
        pockets.append(
            {
                "shadow_below": shadow_max,
                "surface_below_c": surface_max,
                "cells": int(mask.sum()),
                "pct": 100.0 * float(mask.sum()) / float(traversable.sum()),
            }
        )

    laws = []
    for rover_id in ("lpr_1", "nasa_viper", "cnsa_yutu_2"):
        rover = get_rover(rover_id)
        old = np.clip(shadow, 0.0, 1.0) * float(rover["p_heater_w"])
        for model in ("delta_t", "radiative"):
            new = B.heater_power_w_grid(surface, rover, model)
            delta = new - old
            good = np.isfinite(delta)
            laws.append(
                {
                    "id": rover_id,
                    "model": model,
                    "more_cells": int((delta[good] > 1e-9).sum()),
                    "more_pct": 100.0 * float((delta[good] > 1e-9).sum()) / float(good.sum()),
                    "less_cells": int((delta[good] < -1e-9).sum()),
                    "max_excess_w": float(np.max(delta[good])),
                    "max_deficit_w": float(np.min(delta[good])),
                    "mean_delta_w": float(np.mean(delta[good])),
                }
            )

    return {
        "traversable_cells": int(traversable.sum()),
        "thermal_field": grids["metadata"].get("thermal_field"),
        "window_offset": grids["metadata"].get("window_offset"),
        "surface_min_c": float(np.nanmin(surface)),
        "surface_median_c": float(np.nanmedian(surface)),
        "surface_max_c": float(np.nanmax(surface)),
        "shadow_min": float(np.nanmin(shadow)),
        "shadow_median": float(np.nanmedian(shadow)),
        "shadow_max": float(np.nanmax(shadow)),
        "spearman_shadow_surface": correlation,
        "lit_but_cold": pockets,
        "heater_laws": laws,
    }


def measure_routes(grids) -> dict:
    """Section 7: the three standard routes under every switch."""
    out = {}
    with TestClient(app) as client:
        app.state.grids = grids
        for route in ROUTES:
            out[route["key"]] = {"label": route["label"], "cases": {}}
            for name, extra in SWITCHES:
                started = time.perf_counter()
                response = client.post("/api/plan-4d", json={**route["body"], **extra})
                elapsed = time.perf_counter() - started
                row = {"status": response.status_code, "seconds": round(elapsed, 1)}
                if response.status_code == 200:
                    payload = response.json()
                    metrics = payload["metrics"]
                    row.update(
                        moves=metrics["move_steps"],
                        waits=metrics["wait_steps"],
                        hibernates=metrics.get("hibernate_steps"),
                        nodes=metrics["nodes_expanded"],
                        cost=metrics["total_cost"],
                        arrival=metrics["arrival_slice"],
                        max_dark_h=metrics.get("max_continuous_shadow_h"),
                        min_soc=min(payload["path_battery_pct"]),
                        end_soc=payload["path_battery_pct"][-1],
                        hibernate_hours=metrics.get("hibernate_hours"),
                        hibernate_dark_hours=metrics.get("hibernate_dark_hours"),
                        coldest_inner_c=metrics.get("coldest_inner_c"),
                        beyond_evidence=metrics.get("hibernation_beyond_cited_evidence"),
                        applied=payload["battery"]["applied"],
                    )
                else:
                    row["detail"] = str(response.json().get("detail", ""))[:400]
                out[route["key"]]["cases"][name] = row
                print(f"  {route['key']:12s} {name:10s} {row.get('status')}", flush=True)
    return out


def measure() -> dict:
    started = time.perf_counter()
    grids = load_preprocessed_grids()
    data = {
        "catalogue": measure_catalogue(),
        "grid": measure_grid(grids),
        "routes": measure_routes(grids),
    }
    data["total_seconds"] = time.perf_counter() - started
    return data


# ── the report ──────────────────────────────────────────────────────────────


def render(data: dict) -> str:
    catalogue = data["catalogue"]
    grid = data.get("grid") or {}
    routes = data.get("routes") or {}
    lines: list[str] = []
    add = lines.append

    add("# C2 — Batarya soğuk davranışı, hibernasyon ve karanlık dayanımı: ölçüm raporu")
    add("")
    window = grid.get("window_offset") or {}
    window_text = (
        f"({window.get('row')}, {window.get('col')})" if window else "bilinmiyor"
    )
    add("**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Saha:** Site11, "
        f"pencere {window_text}, {_f(grid.get('traversable_cells'), 0)} geçilebilir hücre")
    add("")
    add("**Etiket: MODEL, kalibre edilmemiş.** Bu katalogdaki hiçbir rover sıcaklığa bağlı "
        "kapasite eğrisi, ısıtıcı iletkenliği, ışıma alanı, termostat set noktası ya da "
        "hibernasyon dayanımı yayımlamıyor. Aşağıdaki her katsayı ya doğrudan bir katalog "
        "alanından okundu ya da `\"assumption:\"` ile başlayan kendi kaynak dizesini taşıyor. "
        "NASA Glenn'in, ISRO'nun ve NASA JSC'nin sayıları **onlarındır**; alıntı olarak "
        "durur, bizim ölçümümüzle karıştırılmaz.")
    add("")
    add("---")
    add("")

    # 1
    add("## 1. Kaynaklar ne diyor (alıntı), ve JSC'nin sayısının çapraz kontrolü")
    add("")
    quoted = catalogue["nasa_glenn_quoted"]
    add("**NASA Glenn (Oeftering, Bennett vd., 2021 Space Power Workshop, NTRS 20210011101) — alıntı:**")
    add("")
    add(f"- *\"{quoted['freeze_quote']}\"* · *\"{quoted['voltage_quote']}\"* · *\"{quoted['recovery_quote']}\"*")
    add(f"- Vakumda: *\"{quoted['vacuum_trials']}\"* (~{_f(quoted['vacuum_chamber_mtorr'], 0)} mtorr, "
        f"kriyosoğutucu ~{_f(quoted['vacuum_hold_k'], 0)} K)")
    add(f"- 1 atm LN2'de: {quoted['ln2_trials']}; soğuk daldırma {_f(quoted['ln2_cold_soak_k'], 0)} K")
    add(f"- ISRO: {quoted['isro_cells']}, {_f(quoted['isro_temperature_c'], 0)} °C'de "
        f"{quoted['isro_days']} gün — *\"{quoted['isro_result']}\"*")
    add(f"- Surveyor: *\"{quoted['surveyor_1']}\"*")
    add(f"- Diviner grafiğinde NASA'nın kendi etiketi: *\"{quoted['diviner_label']}\"*")
    add("")
    jsc = catalogue["jsc_quoted"]
    add("**NASA JSC / Jacobs (Slusser, Wilcox, Hernandez, TFAWS23-PT-52) — alıntı:**")
    add("")
    add(f"- Yasa: `{jsc['law']}`")
    add(f"- *\"{jsc['t4_quote']}\"*")
    add(f"- *\"{jsc['survival_temperature_quote']}\"*")
    add(f"- *\"{jsc['battery_mass_quote']}\"*")
    add(f"- Karşı görüş (hibernasyona): *\"{jsc['hibernation_caution']}\"*")
    add("")
    check = catalogue["jsc_check"]
    add("**Çapraz kontrol (bizim aritmetiğimiz, onların yasası ve onların sayısı üstünde):**")
    add("")
    add("| T_env | `1 − (250⁴−T_env⁴)/(270⁴−T_env⁴)` |")
    add("|---|---|")
    for row in check["by_environment"]:
        add(f"| {_f(row['t_env_k'], 0)} K | %{_f(row['predicted_reduction_pct'], 2)} |")
    add("")
    add(f"JSC'nin yayımladığı **%{_f(check['quoted_pct'], 0)}**'ya karşı bizim okumamız "
        f"**%{_f(check['predicted_pct'], 2)}**; fark **{_f(check['difference_pct_points'], 2)}** puan. "
        "Isıtıcı katsayısı bu oranda sadeleşiyor, yani bu **yasanın** kontrolüdür, bizim "
        "kalibrasyonumuzun değil. C1'in `viper_corner_check`'i ne yapıyorsa bu da onu yapıyor.")
    add("")

    # 2
    add("## 2. Katalog kalibrasyonu: tek katsayı, `p_heater_w`'den okunuyor")
    add("")
    add("JSC'nin denklemi `εσA` üçlüsünü tek bir çarpım olarak taşıyor, ve modele giren de o "
        "tek çarpım: hiçbir yerde ε ya da A ayrı ayrı uydurulmuyor. Çarpım, ısıtıcının "
        f"modelin geçilebilir saydığı en soğuk yüzeyde ({_f(catalogue['sizing_surface_c'], 0)} °C) "
        "set noktasını tam tutacak kadar büyük olduğu **varsayımından** okunuyor.")
    add("")
    add("| Profil | `p_heater_w` | set noktası | `kA` (W/K) | `εσA` (W/K⁴) | ε=1'de ima edilen A |")
    add("|---|---|---|---|---|---|")
    for row in catalogue["rovers"]:
        add(f"| {row['name']} | {_f(row['p_heater_w'], 0)} W | {_f(row['envelope_lo'], 1)} °C "
            f"({row['envelope_lo_component']}) | {_f(row['k_a'], 6)} | "
            f"{_sci(row['es_a'])} | "
            f"{_f(row['implied_area_m2'], 4)} m² |")
    add("")
    add("**Bulgu.** İma edilen alanlar çok küçük — LPR-1 için 450 kg'lık bir araçta "
        f"{_f(catalogue['rovers'][0]['implied_area_m2'], 4)} m². Bu, katalogdaki `p_heater_w`'nin bir "
        "**gece-hayatta-kalma** ısıtıcısı değil bir **idame** ısıtıcısı olduğunu söylüyor ve "
        "JSC'nin 500 kg'lık araç için \">400 kg batarya\" bulgusuyla aynı yöne işaret ediyor. "
        "Katalog değiştirilmedi; bulgu yazıldı.")
    add("")
    add("### İki yasanın gerçek yüzey sıcaklıklarındaki farkı (W)")
    add("")
    add("| Yüzey | LPR-1 `delta_t` | LPR-1 `radiative` | VIPER `delta_t` | VIPER `radiative` | Yutu-2 `delta_t` | Yutu-2 `radiative` |")
    add("|---|---|---|---|---|---|---|")
    for row in catalogue["heater_by_surface"]:
        add(f"| {_f(row['surface_c'], 0)} °C | {_f(row['lpr_1_delta_t'], 2)} | {_f(row['lpr_1_radiative'], 2)} | "
            f"{_f(row['nasa_viper_delta_t'], 2)} | {_f(row['nasa_viper_radiative'], 2)} | "
            f"{_f(row['cnsa_yutu_2_delta_t'], 2)} | {_f(row['cnsa_yutu_2_radiative'], 2)} |")
    add("")
    add("İkisi boyutlandırma noktasında **tam olarak** eşit (varsayım öyle kuruyor); başka her "
        "yerde dördüncü kuvvet doğrusal formun üstünde kalıyor. Araştırma belgesi doğrusal "
        "formu istedi; belgenin kendi gösterdiği kaynak T⁴'ü yazıyor. İkisi de sunuluyor.")
    add("")

    # 3
    if grid:
        add("## 3. \"Karanlık = soğuk\" Site11'de doğru mu? Hayır.")
        add("")
        add("Bugünkü ısıtıcı terimi gölge oranıyla ölçekleniyor, yani karanlığın soğukluğun "
            "vekili olduğunu varsayıyor. Gönderilen pencerede ölçüldü:")
        add("")
        add("| Büyüklük | min | medyan | maks |")
        add("|---|---|---|---|")
        add(f"| yüzey sıcaklığı ({grid.get('thermal_field')}) | {_f(grid['surface_min_c'], 2)} °C | "
            f"{_f(grid['surface_median_c'], 2)} °C | {_f(grid['surface_max_c'], 2)} °C |")
        add(f"| gölge oranı | {_f(grid['shadow_min'], 4)} | {_f(grid['shadow_median'], 4)} | "
            f"{_f(grid['shadow_max'], 4)} |")
        add("")
        add(f"**Spearman(gölge oranı, yüzey sıcaklığı) = {_f(grid['spearman_shadow_surface'], 4)}.**")
        add("")
        add("Yani bu alanda gölge oranı, yüzey sıcaklığı hakkında **hiçbir şey** söylemiyor — "
            "yaklaşık olarak değil, sıfır. Aydınlık ama soğuk cepler var:")
        add("")
        add("| Gölge oranı < | Yüzey < | hücre | oran |")
        add("|---|---|---|---|")
        for row in grid["lit_but_cold"]:
            add(f"| {_f(row['shadow_below'], 1)} | {_f(row['surface_below_c'], 0)} °C | "
                f"{_f(row['cells'], 0)} | %{_f(row['pct'], 2)} |")
        add("")
        add("> **Uyarı, çünkü bu istatistik meselesidir:** buradaki yüzey alanı uzun vadeli "
            "`sunlit_peak` istatistiğidir. 4-B hattının okuduğu dilim başına seri farklı bir "
            "alandır ve korelasyonu farklı olabilir. Ölçüm burada yazılı olan alanındır.")
        add("")

        # 4
        add("## 4. Üç ısıtıcı modelinin işaretli farkı (tüm geçilebilir hücreler)")
        add("")
        add("İlk taslak \"yeni model her zaman ≤ eski model\" diye bir sınır iddia ediyordu. "
            "Ölçüm çürüttü ve iddia **geri çekildi**: iki model sıralanabilir değil, biri "
            "maruz kalmayı öbürü sıcaklığı okuyor.")
        add("")
        add("| Profil | Model | yeni > eski | oran | en büyük fazla | en büyük eksik | ortalama |")
        add("|---|---|---|---|---|---|---|")
        for row in grid["heater_laws"]:
            add(f"| {row['id']} | `{row['model']}` | {_f(row['more_cells'], 0)} | %{_f(row['more_pct'], 2)} | "
                f"{_f(row['max_excess_w'], 2)} W | {_f(row['max_deficit_w'], 2)} W | {_f(row['mean_delta_w'], 3)} W |")
        add("")
        add("Başarısızlık sınıfı **soğuk ama aydınlık** hücrelerdir: bugünkü terim orada "
            "ısıtıcıyı hiç çalıştırmıyor, sıcaklık tabanlı terim çalıştırıyor.")
        add("")

    # 5
    add("## 5. Teslim edilebilir kapasite eğrisi ve kaynaksız şeklinin süpürülmesi")
    add("")
    add(f"Soğuk uç {_f(catalogue['freeze_c'], 2)} °C (200 K, NASA Glenn'den **alıntı**, bir rover "
        "bataryasına taşınması etiketli varsayım). Sıcak uç profilin kendi beyan ettiği "
        "`bat_op_min_c`'si — LPR-1 ve VIPER'da **tam olarak 0 °C**, yani NASA'nın 5 420 Wh'ı "
        "verdiği sıcaklıkla çakışıyor. Aradaki **şeklin hiçbir kaynağı yok**; varsayılan "
        "doğrusal ve aşağıda süpürülüyor, ayarlanmıyor.")
    add("")
    add("| Üs | f(−10 °C) | f(−20 °C) | f(−40 °C) | dayanım(−20 °C) | dayanım(−40 °C) |")
    add("|---|---|---|---|---|---|")
    for row in catalogue["shape_sweep"]:
        add(f"| {_f(row['exponent'], 2)} | {_f(row['f_at_minus_10'], 4)} | {_f(row['f_at_minus_20'], 4)} | "
            f"{_f(row['f_at_minus_40'], 4)} | {_f(row['h_at_minus_20'], 2)} s | {_f(row['h_at_minus_40'], 2)} s |")
    add("")
    add("**Araştırma belgesinin \"0 °C'de ~%85\" tahmini kullanılmadı.** Kaynağı yok, ve "
        "`e_cap_wh` zaten 0 °C'de verilmiş bir kapasite olduğu için 0 °C'de %85 demek aynı "
        "iskontoyu ikinci kez uygulamak olurdu.")
    add("")
    add("> **Sınır:** yayımlanmış COTS 18650 deşarj eğrileri düz değil dışbükeydir, yani "
        "doğrusal varsayım karamsar olmaktan çok **iyimser** olabilir. Bu bir yön beyanıdır, "
        "ölçülmüş bir sayı değil; ölçmediğimiz için tablo üssü süpürüyor.")
    add("")

    # 6
    add("## 6. Dayanım: katalogun kendi tutarsızlığı")
    add("")
    add("| Profil | kapasite | rezerv | tam-gölge W | **ima edilen** dayanım | **yayımlanan** `h_max_shadow_h` |")
    add("|---|---|---|---|---|---|")
    for row in catalogue["rovers"]:
        reserve = float(row["e_cap_wh"]) * float(row["soc_min_pct"])
        add(f"| {row['name']} | {_f(row['e_cap_wh'], 0)} Wh | {_f(reserve, 0)} Wh | "
            f"{_f(float(row['p_shadow_w']), 0)} W | {_f(row['implied_endurance_h'], 2)} s | "
            f"**{_f(row['h_max_shadow_h'], 1)} s** |")
    add("")
    add("**NASA VIPER'ın kataloğu kendi içinde tutarsız:** 50 s × 130 W = 6 500 Wh, 5 420 Wh'lik "
        "paketi rezervsiz bile aşıyor. Açıklama, NASA'nın 50 saatinin **min-power modunda** "
        f"olması (Shirley & Balaban: gölgede matkapla {_f(catalogue['viper_quoted']['drilling_in_shadow_h'], 1)} s, "
        f"min-power modda {_f(catalogue['viper_quoted']['min_power_shadow_h'], 0)} s), `p_shadow_w`'nin ise "
        "normal gölge çekişi olması: iki farklı mod, iki farklı sayı.")
    add("")
    add("Bu yüzden dinamik dayanım `min(yayımlanan, ima edilen)` **değildir**. O biçim VIPER'ın "
        "dayanımını bayrak açılır açılmaz %33 kısar ve \"tam şarjda yayımlanan sabiti verir\" "
        "iddiasını yanlışlardı. Model **oransal**: yayımlanan dayanımı, bu durumun rezervin "
        "üstünde hâlâ teslim edebildiği kesirle ölçekler — dört profilde de tam şarj + rating "
        "sıcaklığında **tam olarak** yayımlanan sabiti verir. Tutarsızlık düzeltilmedi, **ölçüm "
        "olarak** buraya yazıldı.")
    add("")

    # 7
    add("## 7. Hibernasyon")
    add("")
    add("| Profil | `p_hibernate_w` | `p_shadow_w` | oran (karanlık saati hızı) | uygulanabilir mi |")
    add("|---|---|---|---|---|")
    for row in catalogue["rovers"]:
        reason = "" if row["hibernation"] else " — `p_hibernate_w` beyan edilmemiş"
        add(f"| {row['name']} | {'-' if row['p_hibernate_w'] is None else _f(row['p_hibernate_w'], 0) + ' W'} | "
            f"{_f(float(row['p_shadow_w']), 0)} W | {_f(row['dark_rate'], 4)} | "
            f"{'evet' if row['hibernation'] else 'hayır' + reason} |")
    add("")
    add("**LPR-1'in \"hibernasyonu\" ısıtıcılarını çalıştırmaktan pahalı** (108 W'a karşı 65 W). "
        "Bu bir veri hatası değil, tanım farkı: proje referans belgesi modu \"idle + heater + "
        "termal yönetim\" diye tanımlıyor, yani bu bir **idame** modu. NASA Glenn'in *pasif* "
        "hibernasyonunda yükler kapanır ve batarya izole edilir; çekiş neredeyse sıfırdır. "
        "Model katalogdaki modu uygular ve farkı söyler; katalog düzeltilmedi.")
    add("")
    add("| Profil | karanlıkta bekleme (birim maliyet) | karanlıkta hibernasyon | hibernasyon daha ucuz mu |")
    add("|---|---|---|---|")
    for row in catalogue["dormant_vs_wait"]:
        add(f"| {row['id']} | {_f(row['wait_dark'], 6)} | {_f(row['hibernate_dark'], 6)} | "
            f"{'evet' if row['hibernate_dark'] < row['wait_dark'] else 'hayır'} |")
    add("")
    add("İki profilde hibernasyon beklemeden **ucuz**. Kapısız bir kenar bu yüzden planlayıcıyı "
        "güneşin altında şekerleme yapmaya iterdi; kenar bu nedenle **karanlıkta başlar ve "
        "aydınlıkta biter** — ikincisi NASA'nın kendi mimarisi (*\"Solar Array output triggers "
        "a 'Dawn Mode'\"*), bizim icadımız değil.")
    add("")
    limit = catalogue["evidence_limit"]
    add(f"**Alıntılanan kanıtın menzili:** en soğuk {_f(limit['coldest_cited_c'], 1)} °C "
        f"({_f(limit['coldest_cited_k'], 0)} K), en uzun {_f(limit['longest_cited_h'], 0)} s (14 gün). "
        "Bundan daha soğuk ya da daha uzun bir hibernasyon planlanır ama yanıt "
        "`beyond_cited_evidence` ile bunun kanıtın dışına çıktığını söyler.")
    add("")

    if routes:
        add("### Üç standart 4-B rota, her anahtar altında")
        add("")
        for key, entry in routes.items():
            add(f"**{entry['label']}**")
            add("")
            add("| Anahtar | durum | hamle | bekleme | hibernasyon | düğüm | maliyet | en düşük SOC | sürekli karanlık | duvar saati (sn) |")
            add("|---|---|---|---|---|---|---|---|---|---|")
            for name, row in entry["cases"].items():
                if row["status"] != 200:
                    add(f"| `{name}` | **{row['status']}** | — | — | — | — | — | — | — | {_f(row['seconds'], 1)} |")
                    continue
                add(f"| `{name}` | 200 | {_f(row['moves'], 0)} | {_f(row['waits'], 0)} | "
                    f"{_f(row['hibernates'], 0)} | {_f(row['nodes'], 0)} | {_f(row['cost'], 4)} | "
                    f"%{_f(row['min_soc'], 1)} | {_f(row['max_dark_h'], 3)} s | {_f(row['seconds'], 1)} |")
            add("")
            for name, row in entry["cases"].items():
                if row["status"] != 200:
                    add(f"- `{name}` reddi: {row.get('detail', '')}")
            add("")

    # 8
    add("## 8. İddia sınırı")
    add("")
    add("- **NASA Glenn'in, ISRO'nun, Surveyor'un ve NASA JSC'nin sayıları onlarındır.** "
        "Hiçbiri bizim ölçüm tablomuza konmadı ve hiçbiri için \"biz doğruladık\" denmedi. "
        "Tek istisna § 1'deki çapraz kontroldür ve o da **onların yasasının** bizim okumamızla "
        "tutarlılığını gösterir, yeni bir ölçüm değildir.")
    add("- **200 K bir HÜCRE ölçümüdür.** 18650 hücrelerinde ölçüldü; bu katalogdaki hiçbir "
        "profil hücre formatını, kimyasını ya da donma noktasını yayımlamıyor. Bir rover "
        "bataryasına taşınması C3'ün taşınmış kayma çapalarındaki gibi etiketli varsayımdır.")
    add("- **Eğrinin şekli kaynaksızdır** ve ayarlanmadı; § 5 süpürüyor.")
    add("- **`k` ve `A` ayrı ayrı türetilmedi.** Yalnızca `εσA` çarpımı, yalnızca `p_heater_w`'den, "
        "yalnızca etiketli bir boyutlandırma varsayımıyla.")
    add("- **`p_hibernate_w` kaynaksızdır.** C2 onu ilk kez okunan bir girdi hâline getirdiği "
        "için ev kuralı gereği kendi `\"assumption:\"` dizesini kazandı.")
    add("- **LUVMI-M için üç modelin hiçbiri uygulanmıyor** ve nedeni her yanıtta yazılı: "
        "beyan ettiği batarya alt sınırı (−100 °C) alıntılanan donma noktasının altında, ve "
        "`p_hibernate_w` ile `thermal_tau_s` beyan etmiyor. Değer uydurulmadı.")
    add("- **İki kaynak birbiriyle çelişiyor.** NASA Glenn hibernasyonu savunur (kanıtı "
        "**hücrelere** dair), NASA JSC uyarır (uyarısı **aviyoniğe** dair). Model hibernasyonda "
        "hangi bileşenin sınırının aşıldığını adlandırır; çelişki gizlenmedi.")
    add("- **Modellenmeyenler:** şarj tarafı soğuk kısıtı, iç direnç, yaşlanma, çevrim ömrü, "
        "hücre dengeleme, gerçek bir gövde termal modeli. Yoklukları burada yazılı.")
    add("- **SHERPA marjları** (`safe_haven.route_margins`) nominal şarj ve sabit idame gücü "
        "üzerinden hesaplanır, yani derate açıkken planlayıcının kendi sayıları değildir. "
        "Yanıttaki `battery.route.margins_use_nameplate_charge` bunu söyler.")
    add("")
    add("**Sunum cümlesi.** \"Bataryanın soğukta ne kadarını verebildiğini, ısıtıcının kaç watt "
        "çektiğini ve rover'ın gece boyunca uyuyup şafakta uyanmasını modelliyoruz — ısıtıcı "
        "yasası NASA JSC'nin kendi Stefan-Boltzmann denklemi, hibernasyon mimarisi NASA "
        "Glenn'in 'dawn mode'u, donma eşiği onların 200 K ölçümü. Bizim olan: katalogdan "
        "okunan tek katsayı, planlayıcıdaki eylem, ve hepsinin nerede biteceğini söyleyen "
        "sınır.\"")
    add("")
    add("---")
    add("")
    add(f"*Ölçüm süresi: {_f(data.get('total_seconds', 0.0) / 60.0, 1)} dakika. "
        "Üretici betik: [`scripts/battery_hibernation_report.py`](../../scripts/battery_hibernation_report.py) "
        "(`--json` ham çıktı, `--from-json` ölçmeden yeniden render).*")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None, help="write the measurements here BEFORE rendering")
    parser.add_argument("--from-json", default=None, help="render from a previous dump instead of measuring")
    parser.add_argument(
        "--out", default=str(_ROOT / "docs" / "research" / "battery_hibernation_report.md")
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
        f"({_f(data.get('total_seconds', 0.0) / 60.0, 1)} min measured)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
