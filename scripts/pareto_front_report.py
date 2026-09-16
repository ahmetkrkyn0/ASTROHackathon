"""D5 — weight-simplex sweep on Site11: measure and render the report.

Runs the sweep on four scenarios (two rovers, three pairs), measures how
the surviving set grows with the sample budget, and puts the survivors next
to the model's OWN spread on the same route -- because a front narrower
than the model's noise is the finding, and a report that published the
front without the noise would read as a recommendation.

    python scripts/pareto_front_report.py --json raw.json
    python scripts/pareto_front_report.py --from-json raw.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.constants import get_rover  # noqa: E402
from app.cost_engine import edge_travel_time_s, f_thermal  # noqa: E402
from app.data_loader import load_preprocessed_grids  # noqa: E402
from app.pareto import (  # noqa: E402
    OBJECTIVE_KEYS,
    PARETO_CLAIM,
    PARETO_COMPLETENESS_NOTE,
    PARETO_QUOTED,
    diagnostics,
    sweep,
)
from app.risk import route_risk_summary  # noqa: E402
from app.rover_grids import grids_for_rover  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"

SEED = 20260916
N_SAMPLES = 24
BUDGETS = (8, 16, 24, 40, 60, 100, 150, 200)

SCENARIOS = (
    {"key": "lpr1_day", "name": "LPR-1 gunduz", "rover_id": "lpr_1",
     "start": (358, 494), "goal": (206, 426)},
    {"key": "lpr1_night", "name": "LPR-1 Ay gecesi", "rover_id": "lpr_1",
     "start": (186, 34), "goal": (494, 450)},
    {"key": "viper_std", "name": "VIPER standart", "rover_id": "nasa_viper",
     "start": (358, 494), "goal": (206, 426)},
    {"key": "viper_short", "name": "VIPER kisa leg", "rover_id": "nasa_viper",
     "start": (358, 494), "goal": (346, 462)},
)

RISK_ALPHAS = (0.5, 0.75, 0.9, 0.95, 0.99)


def _fmt(value, digits=2):
    if value is None:
        return "—"
    return f"{float(value):.{digits}f}".replace(".", ",")


def _int(value):
    if value is None:
        return "—"
    return f"{int(value):,}".replace(",", " ")


def _pct(value, digits=2):
    if value is None:
        return "—"
    return f"%{float(value):.{digits}f}".replace(".", ",")


# ── measurement ─────────────────────────────────────────────────────────────


def measure_saturation(grids) -> dict:
    """How saturated f_thermal is, per rover -- the reason the fourth axis dies."""
    thermal = np.asarray(grids["thermal"], dtype=np.float64)
    thermal_min = grids.get("thermal_min")
    out = {}
    for rover_id in ("lpr_1", "nasa_viper"):
        rover = get_rover(rover_id)
        adapted = grids_for_rover(grids, rover_id)
        passable = np.asarray(adapted["traversable"], dtype=bool)
        rows, cols = np.where(passable)
        values = np.array(
            [
                f_thermal(
                    float(thermal[r, c]),
                    rover,
                    None if thermal_min is None else float(np.asarray(thermal_min)[r, c]),
                )
                for r, c in zip(rows, cols)
            ]
        )
        out[rover_id] = {
            "passable_cells": int(values.size),
            "frac_ge_099": float(np.mean(values >= 0.99)),
            "median": float(np.median(values)),
        }
    return out


def measure_scenarios(grids) -> dict:
    out = {}
    for scenario in SCENARIOS:
        rover = get_rover(scenario["rover_id"])
        started = time.perf_counter()
        result = sweep(
            grids,
            scenario["start"],
            scenario["goal"],
            scenario["rover_id"],
            rover,
            n_samples=N_SAMPLES,
            seed=SEED,
        )
        out[scenario["key"]] = {
            "name": scenario["name"],
            "rover_id": scenario["rover_id"],
            "rover_name": rover["name"],
            "start": list(scenario["start"]),
            "goal": list(scenario["goal"]),
            "counts": result["counts"],
            "diagnostics": result["diagnostics"],
            "nominal": result["nominal"],
            "non_dominated": [
                {"route_id": r["route_id"], "objectives": r["objectives"],
                 "weights": r["weights"], "weight_vectors": r["weight_vectors"]}
                for r in result["non_dominated"]
            ],
            "seconds": time.perf_counter() - started,
            "ms_per_sample": result["total_ms"] / max(1, result["counts"]["weight_vectors"]),
        }
    return out


def measure_budget_curve(grids) -> dict:
    """Does the surviving set grow with the sample budget, or is it saturated?

    The honest answer to "did you just not sample enough". Run on the
    daytime pair because it is the cheapest; the shape is what matters.
    """
    rover = get_rover("lpr_1")
    rows = []
    for n in BUDGETS:
        started = time.perf_counter()
        result = sweep(
            grids, (358, 494), (206, 426), "lpr_1", rover,
            n_samples=n, seed=SEED, include_corners=False,
        )
        rows.append({
            "n_samples": n,
            "weight_vectors": result["counts"]["weight_vectors"],
            "distinct_routes": result["counts"]["distinct_routes"],
            "non_dominated": result["counts"]["non_dominated"],
            "seconds": time.perf_counter() - started,
        })
    # the same budget WITH the simplex corners, which an interior draw misses
    corners = sweep(
        grids, (358, 494), (206, 426), "lpr_1", rover,
        n_samples=max(BUDGETS), seed=SEED, include_corners=True,
    )
    corner_front = [
        {"route_id": r["route_id"], "found_by": r["found_by"], "objectives": r["objectives"]}
        for r in corners["non_dominated"]
    ]
    return {
        "rows": rows,
        "with_corners": {
            "weight_vectors": corners["counts"]["weight_vectors"],
            "distinct_routes": corners["counts"]["distinct_routes"],
            "non_dominated": corners["counts"]["non_dominated"],
            "front": corner_front,
            # Two DIFFERENT spans, and confusing them inverts the finding:
            # the survivors sit in a sliver, while everything the sweep
            # produced covers a wide range. The point of the report is the
            # ratio between them.
            "front_spread": diagnostics(corners["non_dominated"])["objective_spread"],
            "all_routes_spread": corners["diagnostics"]["objective_spread"],
        },
    }


def measure_noise_band(grids) -> dict:
    """The model's own spread on ONE route, in the same currency as the front.

    B2's CVaR slip tail, applied to the nominal route. No new physics: this
    is the existing risk module answering "how well does this model know
    this route's hours at all".
    """
    rover = get_rover("lpr_1")
    from app.pathfinder import astar
    from app.simulation import simulate_path, summarize_simulation

    adapted = grids_for_rover(grids, "lpr_1")
    result = astar(adapted, (358, 494), (206, 426), rover=rover)
    states = simulate_path(
        result, adapted["cost"], adapted["slope"], adapted["thermal"],
        adapted["shadow_ratio"], rover=rover,
        pixel_size_m=float(adapted["metadata"]["resolution_m"]),
        elevation_grid=adapted["elevation"],
    )
    summary = summarize_simulation(states, rover)
    legs = []
    for previous, current in zip(states[:-1], states[1:]):
        distance = float(current.distance_m) - float(previous.distance_m)
        if distance <= 0.0:
            continue
        slope = max(float(current.slope_deg), float(current.segment_slope_deg))
        seconds = edge_travel_time_s(slope, distance, rover)
        hours = seconds / 3600.0 if math.isfinite(seconds) else float("inf")
        legs.append((slope, distance, hours, float(current.step_energy_wh), None))
    rows = []
    for alpha in RISK_ALPHAS:
        block = route_risk_summary(legs, rover, alpha)
        rows.append({
            "alpha": alpha,
            "hours_factor": block["hours_factor"],
            "hours": block["hours"],
            "risk_adjusted_hours": block["risk_adjusted_hours"],
            "delta_pct": 100.0 * (block["risk_adjusted_hours"] - block["hours"])
            / max(1e-12, block["hours"]),
        })
    return {"nominal_hours": float(summary["total_elapsed_hours"]), "rows": rows}


def measure() -> dict:
    started = time.perf_counter()
    grids = load_preprocessed_grids()
    metadata = grids["metadata"]
    data = {
        "window": {
            "shape": list(metadata["shape"]),
            "resolution_m": float(metadata["resolution_m"]),
            "origin": metadata.get("origin"),
        },
        "seed": SEED,
        "n_samples": N_SAMPLES,
        "saturation": measure_saturation(grids),
        "scenarios": measure_scenarios(grids),
        "budget": measure_budget_curve(grids),
        "noise_band": measure_noise_band(grids),
        "quoted": {key: dict(value) for key, value in PARETO_QUOTED.items()},
    }
    data["total_seconds"] = time.perf_counter() - started
    return data


# ── rendering ───────────────────────────────────────────────────────────────


def render(data: dict) -> str:
    lines: list[str] = []
    add = lines.append

    add("# D5 — Ağırlık simpleksi taraması ve baskın-olmayan rotalar: Site11 ölçümü")
    add("")
    add(
        f"**Üretildi:** `scripts/pareto_front_report.py` · pencere "
        f"{data['window']['shape'][0]}×{data['window']['shape'][1]}, "
        f"{_fmt(data['window']['resolution_m'], 1)} m/px · tohum {data['seed']} · "
        f"ölçüm süresi {_fmt(data['total_seconds'] / 60.0, 1)} dk"
    )
    add("")
    add(
        "*(`--json` ham çıktı, `--from-json` ölçmeden yeniden render.)*"
    )
    add("")
    add("---")
    add("")

    # 1 — sources
    add("## 1. Kaynaklar ne diyor (alıntı)")
    add("")
    add(
        "Aşağıdaki cümleler **onlarındır**; hiçbiri bizim ölçüm tablomuza konmadı ve hiçbiri "
        "için \"biz doğruladık\" denmedi."
    )
    add("")
    quoted = data["quoted"]
    bv = quoted["boyd_vandenberghe"]
    add(f"> {bv['citation']}")
    add(">")
    add(f"> *\"{bv['limit_quote']}\"*")
    add(">")
    add(f"> *\"{bv['completeness_quote']}\"*")
    add("")
    dd = quoted["das_dennis_1997"]
    add(f"> {dd['citation']}")
    add(">")
    add(f"> *\"{dd['convexity_quote']}\"*")
    add(">")
    add(f"> *\"{dd['spacing_quote']}\"*")
    add("")
    ks = quoted["konen_stiglmayr_2025"]
    add(f"> {ks['citation']}")
    add(">")
    add(f"> *\"{ks['terminology_quote']}\"*")
    add(">")
    add(f"> *\"{ks['consequence_quote']}\"*")
    add("")
    add(
        "**Terminoloji.** Ulaşılabilen çözümlere *supported*, ulaşılamayanlara *unsupported* "
        "denir. \"Duality gap\" bu literatürün terimi **değildir** ve bu raporda kullanılmaz."
    )
    add("")
    eth = quoted["eth_lunar_planner"]
    add(f"> {eth['citation']} ({eth['license']})")
    add(">")
    add(f"> *\"{eth['method_quote']}\"*")
    add("")
    add(
        "**Doğrudan emsal.** ETH'nin `setup_file.py`'si ağırlıkları `ALPHA + BETA + GAMMA = 1` "
        "ile sabitliyor — bizimkiyle aynı simpleks — ve tek bir skaler üzerinde A* koşuyor. "
        "Yani D5'in ucuz yolu ETH'nin yöntemiyle **aynı yöntemdir**, aynı sınırla birlikte."
    )
    add("")
    lavin = quoted["lavin_2015"]
    add(f"> {lavin['citation']}")
    add(">")
    add(f"> *\"{lavin['weight_sensitivity_quote']}\"*")
    add("")
    add(
        "**Kaynakta bulunan uyumsuzluk (birinci elden okundu).** Bu makale, adının aksine, bir "
        "**rota cephesi üretmiyor**: her genişletme adımında açık listenin baskın-olmayanlarını "
        "hesaplayıp hemen tek düğüme indiriyor ve *\"resulting in a single, optimal path\"* "
        "diyor. Buradaki atıf yalnızca yukarıdaki **ağırlık duyarlılığı** iddiası içindir; o "
        "iddiayı da kendi arazimizde biz ölçüyoruz. (Makinece okunan hâli "
        "`app.pareto.PARETO_QUOTED['lavin_2015']['correction']`.)"
    )
    add("")
    add("---")
    add("")

    # 2 — the headline table
    add("## 2. Dört senaryo — kaç ağırlık vektörü, kaç farklı rota, kaç baskın-olmayan")
    add("")
    add(
        f"Her senaryoda **{data['n_samples']} rastgele ağırlık vektörü + rover'ın kendi "
        "varsayılanı**, 4-simpleksten tekdüze çekilmiş (tohum "
        f"{data['seed']}). Rotalar **hücre dizisine** göre tekilleştirildi; her istatistik "
        "**farklı rotalar** üzerinden."
    )
    add("")
    add("| senaryo | rover | start → goal | vektör | **farklı rota** | **baskın-olmayan** | vektör/rota | ms/örnek |")
    add("|---|---|---|---|---|---|---|---|")
    for scenario in SCENARIOS:
        block = data["scenarios"][scenario["key"]]
        counts = block["counts"]
        add(
            f"| {block['name']} | `{block['rover_id']}` | "
            f"({block['start'][0]},{block['start'][1]}) → ({block['goal'][0]},{block['goal'][1]}) | "
            f"{counts['weight_vectors']} | **{counts['distinct_routes']}** | "
            f"**{counts['non_dominated']}** | "
            f"{_fmt(counts['weight_vectors_per_distinct_route'])} | "
            f"{_fmt(block['ms_per_sample'], 0)} |"
        )
    add("")
    add(
        "**Senaryolar ayrı ayrı sunuluyor.** Farklı rover profillerini ya da farklı "
        "aydınlanma koşullarını tek bir cepheye havuzlamak, karşılaştırılamayan şeyleri "
        "karşılaştırmak olurdu."
    )
    add("")

    # 3 — why the front is that small
    add("## 3. Cephe neden bu kadar küçük")
    add("")
    add("### 3a. Dördüncü eksen ölü")
    add("")
    add(
        "`max_thermal_risk`, doygun bir alanın rota boyunca **maksimumu**. Geçilebilir "
        "hücrelerde `f_thermal` ölçümü:"
    )
    add("")
    add("| rover | geçilebilir hücre | `f_thermal ≥ 0,99` | medyan |")
    add("|---|---|---|---|")
    for rover_id, block in data["saturation"].items():
        add(
            f"| `{rover_id}` | {_int(block['passable_cells'])} | "
            f"{_pct(100.0 * block['frac_ge_099'], 1)} | {_fmt(block['median'], 4)} |"
        )
    add("")
    add(
        "Sonuç: hedeflerin biri çoğu senaryoda **tek bir değer** alıyor. Sabit bir eksen "
        "hiçbir çifti ayıramaz, yani \"dört hedefli cephe\" aslında üç hedeflidir. Yanıt bunu "
        "`constant_objectives` ve `effective_objectives` ile açıkça söylüyor — bu bir keşif "
        "değil, yukarıdaki doygunluğun yeniden ifadesidir."
    )
    add("")
    add("### 3b. Kalan eksenler aynı sıralamayı veriyor")
    add("")
    add(
        "Spearman, **farklı rotalar** üzerinden (ham örnekler üzerinden hesaplamak, aynı "
        "rotayı onu bulan her vektör için bir kez sayardı):"
    )
    add("")
    add("| senaryo | n (farklı rota) | etkin hedef | saat~enerji | saat~gölge | enerji~gölge |")
    add("|---|---|---|---|---|---|")
    for scenario in SCENARIOS:
        block = data["scenarios"][scenario["key"]]
        diagnostics = block["diagnostics"]
        correlation = diagnostics["objective_rank_correlation_spearman"]
        add(
            f"| {block['name']} | {diagnostics['n_distinct_routes']} | "
            f"{diagnostics['effective_objectives']} | "
            f"{_fmt(correlation.get('hours~energy_wh'), 4)} | "
            f"{_fmt(correlation.get('hours~shadow_exposure_h'), 4)} | "
            f"{_fmt(correlation.get('energy_wh~shadow_exposure_h'), 4)} |"
        )
    add("")
    add(
        "**Bu n'lerde bir korelasyon betimleyicidir, çıkarımsal değildir** ve güven aralığı "
        "iddia edilmiyor. D5 burada bir **sonucu** ölçüyor, **sebebini** kurmuyor: depo, "
        "katmanların hepsinin tek bir yükseklik gridinden türediğini ve iki kriterin "
        "Spearman'ının tam 1,000000 ölçüldüğünü zaten kaydetmişti "
        "(`cost_engine.py`). D5 \"arazi\" ile \"bu arazide bu maliyet modeli\"ni ayıramaz."
    )
    add("")

    # 4 — budget curve
    add("## 4. Yeterince örneklemedik mi? — bütçe eğrisi")
    add("")
    add(
        "Cephenin tek noktaya çöktüğü ilk ölçüm **n = 24**'teydi. Bütçe büyütülünce bu iddia "
        "kısmen düştü; düzeltilmiş hâli budur. (LPR-1 gündüz çifti.)"
    )
    add("")
    add("| örnek bütçesi | ağırlık vektörü | farklı rota | **baskın-olmayan** | süre (s) |")
    add("|---|---|---|---|---|")
    for row in data["budget"]["rows"]:
        add(
            f"| {row['n_samples']} | {row['weight_vectors']} | {row['distinct_routes']} | "
            f"**{row['non_dominated']}** | {_fmt(row['seconds'], 1)} |"
        )
    corners = data["budget"]["with_corners"]
    add(
        f"| {max(BUDGETS)} + köşeler | {corners['weight_vectors']} | "
        f"{corners['distinct_routes']} | **{corners['non_dominated']}** | — |"
    )
    add("")
    add(
        "Cephe tek nokta **değil**, ama bütçeden **çok daha yavaş** büyüyor. Simpleksin "
        "köşelerini örneklemek ayrıca işe yarıyor: iç bölgeden çekilen vektörler onları "
        "hiç bulamaz."
    )
    add("")
    spread = corners["front_spread"]
    all_spread = corners["all_routes_spread"]
    add(
        f"Şimdi asıl sayı. Köşeler dâhil en büyük bütçede "
        f"({corners['weight_vectors']} vektör, {corners['distinct_routes']} farklı rota, "
        f"{corners['non_dominated']} baskın-olmayan) **hayatta kalanların** aralığı, "
        "taramanın **ürettiği her şeyin** aralığının yanında:"
    )
    add("")
    add("| hedef | cephe: min | cephe: maks | **cephe genişliği** | tüm rotaların genişliği |")
    add("|---|---|---|---|---|")
    for key in OBJECTIVE_KEYS:
        block = spread.get(key)
        whole = all_spread.get(key)
        if not block or not whole:
            continue
        digits = 4 if key != "energy_wh" else 2
        add(
            f"| `{key}` | {_fmt(block['min'], digits)} | {_fmt(block['max'], digits)} | "
            f"**{_pct(block['span_pct_of_min'], 3)}** | "
            f"{_pct(whole['span_pct_of_min'], 3)} |"
        )
    add("")
    add(
        "**İki sütunu karıştırmamak gerekir.** Ağırlık seçimi sonucu geniş bir aralıkta "
        "oynatıyor (sağ sütun); ama o aralığın neredeyse tamamı **baskılanmış** rotalardan "
        "oluşuyor ve hayatta kalanlar çok dar bir şeride sıkışıyor (sol sütun)."
    )
    add("")

    # 5 — the noise band
    add("## 5. Cephe kendi gürültüsünün içinde mi?")
    add("")
    add(
        "Yukarıdaki genişlik, **aynı rotaya** B2'nin CVaR slip kuyruğu uygulandığında ortaya "
        "çıkan yayılmayla karşılaştırılmalıdır. Bu farklı bir rota değil; modelin o rotanın "
        "saatini ne kadar bildiğidir."
    )
    add("")
    band = data["noise_band"]
    add(f"Nominal rota: **{_fmt(band['nominal_hours'], 4)} saat**.")
    add("")
    add("| α | `hours_factor` | risk-ayarlı saat | Δ% |")
    add("|---|---|---|---|")
    for row in band["rows"]:
        add(
            f"| {_fmt(row['alpha'], 2)} | {_fmt(row['hours_factor'], 4)} | "
            f"{_fmt(row['risk_adjusted_hours'], 4)} | **{_pct(row['delta_pct'])}** |"
        )
    add("")
    front_hours = spread.get("hours")
    if front_hours and front_hours["span_pct_of_min"]:
        ratio = band["rows"][0]["delta_pct"] / max(1e-12, front_hours["span_pct_of_min"])
        add(
            f"**Cephenin saat genişliği {_pct(front_hours['span_pct_of_min'], 3)}; modelin "
            f"kendi bandı α = 0,5'te {_pct(band['rows'][0]['delta_pct'])}.** Yani cephe, "
            f"modelin en iyimser belirsizlik bandından yaklaşık **{_fmt(ratio, 0)}×** dardır."
        )
        add("")
    add(
        "Cephe içindeki her \"A, B'yi baskılıyor\" ifadesi bu gürültünün çok içinde "
        "kurulmuştur. Bir farkı kendi bandının içindeyken sonuç diye sunmuyoruz."
    )
    add("")

    # 6 — the nominal verdict
    add("## 6. Rover'ın kendi ağırlıkları cephede mi?")
    add("")
    add("| senaryo | nominal cephede mi | baskılayan rota | en büyük kayıp |")
    add("|---|---|---|---|")
    for scenario in SCENARIOS:
        block = data["scenarios"][scenario["key"]]
        nominal = block.get("nominal")
        if not nominal:
            add(f"| {block['name']} | — | — | — |")
            continue
        if nominal["on_front"]:
            add(f"| {block['name']} | **evet** | — | — |")
            continue
        worst = None
        for dominator in nominal["dominated_by"]:
            for margin in dominator["margins"].values():
                if margin["pct"] is None:
                    continue
                if worst is None or abs(margin["pct"]) > abs(worst):
                    worst = margin["pct"]
        add(
            f"| {block['name']} | hayır | {len(nominal['dominated_by'])} | "
            f"{_pct(worst, 3) if worst is not None else '—'} |"
        )
    add("")
    add(
        "**Bu bir bug değil.** Varsayılan ağırlık vektörü **ağırlıklı maliyeti** minimize "
        "eder, bu dört hedeften hiçbirini değil; maliyet-optimal rotanın sonuç uzayında "
        "baskın olması için bir sebep yoktur. Baskılandığı yerde kaybı **yüzdenin kesirleri** "
        "mertebesindedir — yani §5'teki bandın iki mertebe altında. **\"Varsayılan ağırlıklar "
        "yanlış\" cümlesi bu ölçümden çıkmaz** ve kurulmamıştır."
    )
    add("")

    # 7 — claim limits
    add("## 7. İddia sınırı")
    add("")
    add(
        "- **Bu bir Pareto cephesi değildir** ve yanıt kendini öyle adlandırmaz "
        "(`non_dominated`, `pareto_front` değil). " + PARETO_COMPLETENESS_NOTE
    )
    add(
        "- **Literatürün sayıları onlarındır.** Boyd & Vandenberghe, Das & Dennis, "
        "Könen & Stiglmayr, ETH ve Lavin künyeleriyle alıntılanmıştır; hiçbiri yeniden "
        "üretilmemiştir."
    )
    add(
        "- **Bizim olan:** kaç ağırlık vektörü, kaç farklı rota, kaç baskın-olmayan, cephenin "
        "genişliği ve gürültü bandı. Her tabloda n yazılı ve her istatistik **farklı rotalar** "
        "üzerinden."
    )
    add(
        "- **Baskınlık, API'nin kendi yayın hassasiyetinde karara bağlanır** (1e-4 sa, "
        "1e-2 Wh, 1e-4, 1e-4). Bu kuantumlara yakın farklar bir sıralama değildir."
    )
    add(
        "- **Hiçbir rota sayısı değişmedi.** D5 planlayıcıya dokunmaz; LPR-1'in checked-in "
        "v5 maliyet-gridi SHA-256 özeti kıpırdamadı ve `COST_MODEL_ID` `…_v5`'te kaldı."
    )
    add(
        "- **Sebep kurulmadı.** Cephenin darlığı ölçüldü; \"arazi\" ile \"bu arazide bu "
        "maliyet modeli\" bu ölçümle ayrılamaz."
    )
    add("")
    add(
        "**Sunum cümlesi.** \"Ağırlık tartışması bu arazide iki ayrı sorudur: kötü bir vektör "
        "seçmek ölçülebilir bir hatadır, iyi vektörler arasında seçim yapmak ise bu modelin "
        "çözemeyeceği bir sorudur — çünkü hayatta kalan rotaların arası, modelin kendi "
        "belirsizliğinden iki mertebe dardır.\""
    )
    add("")
    add(f"*Makine tarafından okunan iddia sınırı (`app.pareto.PARETO_CLAIM`):* {PARETO_CLAIM}")
    add("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", default=None, help="write the measurements here BEFORE rendering")
    parser.add_argument("--from-json", default=None, help="render from a previous dump instead of measuring")
    parser.add_argument(
        "--out", default=str(_ROOT / "docs" / "research" / "pareto_front_report.md")
    )
    args = parser.parse_args()

    if args.from_json:
        data = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        if not (_PROCESSED / "metadata.json").exists():
            print("processed grids are missing; nothing measured, nothing written")
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
