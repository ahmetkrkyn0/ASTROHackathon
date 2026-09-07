#!/usr/bin/env python3
"""Run LunaPath on MoonPlanBench (D2) and write the comparison report.

Every map of every variant under the benchmark cache goes through the four
modes of app.benchmark (pure-distance Dijkstra with the benchmark's motion
model, the same with LunaPath's corner-cutting rule, LunaPath A* with a
single criterion, LunaPath A* with the rover's default weights) and, when
``--reference-dir`` points at a local clone of PlanetaryPathBench, through
the benchmark's own PythonRobotics Dijkstra / A* / Theta*. Metrics follow
PathBench's definitions; the paper's Table 1 is printed beside them as a
quotation, never mixed with a measurement.

Writes the JSON dump (--json) BEFORE the markdown; --from-json re-renders
without running anything. --maps N runs the first N maps of each variant.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.benchmark import (  # noqa: E402
    CODE_LICENSES,
    DATA_LICENSE,
    MODE_LABELS,
    MODES,
    MOONPLANBENCH_DIR,
    PAPER_ARXIV,
    PAPER_AUTHORS,
    PAPER_DATE,
    PAPER_TITLE,
    PAPER_URL,
    REPO_COMMIT,
    REPO_URL,
    run_benchmark,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_ROOT = Path(__file__).resolve().parent.parent
PAPER_ROW_ORDER = ("Dijkstra", "ThetaStar", "AStar", "RRT", "Dynamic RRT", "RRT Connect")


def _fmt(value, digits: int = 2) -> str:
    """Decimal comma, like the other Turkish reports; a dash for nothing."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "evet" if value else "hayır"
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    text = f"{float(value):,.{digits}f}"
    return text.replace(",", " ").replace(".", ",")


def _pct(value) -> str:
    return "—" if value is None else _fmt(value, 1) + " %"


def _mode_rows(variant_block: dict, modes: list[str]) -> list[tuple[str, dict]]:
    return [(f"`{mode}` — {MODE_LABELS.get(mode, mode)}", variant_block["aggregates"][mode]) for mode in modes]


def _section_data(report: dict) -> list[str]:
    meta = report.get("meta")
    lines = [
        "## 1. Veri kimliği, lisans, biçim",
        "",
        "| | |",
        "|---|---|",
        f"| Makale | {PAPER_TITLE} — {PAPER_AUTHORS}, arXiv:{PAPER_ARXIV} ({PAPER_DATE}), {PAPER_URL} |",
        f"| Kod deposu | {REPO_URL} @ `{REPO_COMMIT[:12]}` (veri depoda değil; README Google Drive'a yönlendirir) |",
        f"| Veri lisansı | {DATA_LICENSE} |",
        f"| Kod lisansları | {CODE_LICENSES} |",
        "| Biçim | `.npy` uint8, sıfır olmayan = dolu (`run.py`: `occ = grid != 0`); ham DEM yayımlanmamış |",
        "| Hücre boyutu | LDEM ürününün yerel çözünürlüğü × 64 (makale § 3.1.2'nin altörnekleme çarpanı; dosya adından türetilir) |",
        "| Başlangıç / hedef | benchmark'ın `adapters/_common.auto_select_start_goal` kuralı yeniden uygulandı (en büyük 8-bağlantılı boş bileşen; (satır, sütun) en küçük başlangıç; en uzak hedef) |",
        f"| Zaman sınırı | {_fmt(report.get('timeout_s'), 0)} s (benchmark protokolü; burada koşu kesilmez, aşan koşu başarısız sayılır) |",
        f"| Rover (LunaPath modları) | `{report.get('rover_id')}` — eğim sınırı düz haritada etkisiz |",
    ]
    if meta:
        lines.append(f"| Sağlama | `moonplanbench_meta.json`: {meta.get('n_files')} dosya, SHA-256 dosya başına; indirme {meta.get('fetched_utc')} |")
    else:
        lines.append("| Sağlama | sağlama yok (haritaların yanında `moonplanbench_meta.json` bulunamadı) |")
    lines += ["", "| Varyant | Eşik | Harita | Şekil | Hücre (m) | Boş % | Başlangıç (satır, sütun) | Hedef | Düz mesafe (hücre) |", "|---|---|---|---|---|---|---|---|---|"]
    for variant, block in report["variants"].items():
        for m in block["maps"]:
            if "skipped" in m:
                lines.append(f"| {variant} | {block['slope_threshold_deg']}° | `{m['map']}` | {m['shape'][0]}×{m['shape'][1]} | {_fmt(m.get('cell_size_m'), 0)} | {_fmt(100 * m['free_fraction'], 1)} | atlandı: {m['skipped']} | | |")
                continue
            lines.append(
                f"| {variant} | {block['slope_threshold_deg']}° | `{m['map']}` | {m['shape'][0]}×{m['shape'][1]} | {_fmt(m.get('cell_size_m'), 0)} | "
                f"{_fmt(100 * m['free_fraction'], 1)} | ({m['start_rc'][0]}, {m['start_rc'][1]}) | ({m['goal_rc'][0]}, {m['goal_rc'][1]}) | {_fmt(m['original_distance_cells'])} |"
            )
    return lines


def _section_metrics(report: dict) -> list[str]:
    modes = report["modes"]
    reference = report.get("reference", {})
    lines = [
        "## 2. Metrik tablosu",
        "",
        "Tanımlar PathBench'in (`basic_testing.get_results`, `analyzer`): başarı = son hücre hedefe eşit; yol = ardışık hücreler arası Öklid toplamı (hücre); "
        "adım/yol/süre/düzgünlük/açıklık **yalnız başarılı** koşuların ortalaması; hedefe kalan ve bellek tüm koşuların. "
        "Makale satırları **alıntı** (arXiv 2512.21438v1 Tablo 1; süreleri yazarların dizüstünde PathBench tekrar oynatması dahil ölçüldü, bizimkilerle karşılaştırılmaz).",
        "",
    ]
    if reference.get("status") == "run":
        lines += ["Referans satırları: benchmark'ın kendi PythonRobotics planlayıcıları, bu makinede, yerel PlanetaryPathBench klonundan (Theta* için ham herhangi-açı uzunluğu parantezde; ölçülen uzunluk PathBench gibi Bresenham ile döşenmiş iz).", ""]
    else:
        lines += [f"Referans planlayıcılar koşturulmadı: {reference.get('status', 'bilinmiyor')}.", ""]
    header = "| Planlayıcı | Başarı | Yol (hücre) | Yol (km) | Süre ort. (s) | Süre maks (s) | Hedefe kalan (hücre) | Adım | Düzgünlük (rad/hamle) | Açıklık (hücre) | Bellek (MB) | Düğüm |"
    sep = "|---|---|---|---|---|---|---|---|---|---|---|---|"
    lines += ["Bellek sütunu yalnız `--memory` geçişiyle dolar (§ 5); süre sütunları tracemalloc kapalı ölçümdür.", ""]
    for variant, block in report["variants"].items():
        n = len([m for m in block["maps"] if "skipped" not in m])
        lines += [f"### {variant} ({block['slope_threshold_deg']}° eşik, {n} harita)", "", header, sep]
        for label, agg in _mode_rows(block, modes):
            km = None if agg.get("mean_length_m") is None else agg["mean_length_m"] / 1000.0
            mb = None if agg.get("mean_memory_kb") is None else agg["mean_memory_kb"] / 1000.0
            lines.append(
                f"| {label} | {_pct(agg['success_rate_pct'])} | {_fmt(agg['mean_length_cells'])} | {_fmt(km, 1)} | {_fmt(agg['mean_time_s'], 3)} | {_fmt(agg['max_time_s'], 3)} | "
                f"{_fmt(agg['mean_dist_left'], 1)} | {_fmt(agg['mean_steps'], 1)} | {_fmt(agg['mean_smoothness'], 4)} | {_fmt(agg['mean_clearance'])} | {_fmt(mb, 1)} | {_fmt(agg['mean_nodes_expanded'], 0)} |"
            )
        for name, agg in block.get("reference_aggregates", {}).items():
            raw = [m["reference"][name].get("length_cells_raw") for m in block["maps"] if "skipped" not in m and m["reference"][name].get("success")]
            raw_mean = sum(raw) / len(raw) if raw else None
            length = _fmt(agg["mean_length_cells"]) + (f" (ham {_fmt(raw_mean)})" if name == "ThetaStar" and raw_mean is not None else "")
            mb = None if agg.get("mean_memory_kb") is None else agg["mean_memory_kb"] / 1000.0
            lines.append(
                f"| referans PythonRobotics {name} (bu makine) | {_pct(agg['success_rate_pct'])} | {length} | — | {_fmt(agg['mean_time_s'], 3)} | {_fmt(agg['max_time_s'], 3)} | "
                f"{_fmt(agg['mean_dist_left'], 1)} | {_fmt(agg['mean_steps'], 1)} | {_fmt(agg['mean_smoothness'], 4)} | {_fmt(agg['mean_clearance'])} | {_fmt(mb, 1)} | — |"
            )
        paper = report.get("paper_table_1", {}).get(variant, {})
        for name in PAPER_ROW_ORDER:
            row = paper.get(name)
            if not row:
                continue
            lines.append(
                f"| makale {name} (alıntı) | {_pct(row['success_rate_pct'])} | {_fmt(row['length_cells'])} | — | {_fmt(row['time_s'])} | — | {_fmt(row['dist_left'], 1)} | — | — | — | — | — |"
            )
        lines.append("")
    return lines


def _section_success(report: dict) -> list[str]:
    modes = report["modes"]
    lines = [
        "## 3. Başarı oranı farkları ve nedenleri",
        "",
        "Benchmark'ın referans planlayıcıları (PythonRobotics `verify_node`) çapraz hamlede yalnız hedef hücreye bakar: iki dolu hücre arasından köşe keserek geçmek serbesttir. "
        "LunaPath ve nav2 baseline bunu reddeder (iki kardinal komşu da boş olmalı). Aşağıda `dijkstra_cut` ile bağlantılı olup `dijkstra_nocut` ile bağlantısız kalan haritalar: makalenin %100'ünün bu haritalarda sıfır genişlikli çapraz aralıklardan geçmeye dayandığı yerler.",
        "",
    ]
    for variant, block in report["variants"].items():
        maps = [m for m in block["maps"] if "skipped" not in m]
        cut_only = [m["map"] for m in maps if m["results"].get("dijkstra_cut", {}).get("success") and "dijkstra_nocut" in m["results"] and not m["results"]["dijkstra_nocut"]["success"]]
        nobody = [m["map"] for m in maps if "dijkstra_cut" in m["results"] and not m["results"]["dijkstra_cut"]["success"]]
        lp_worse = [
            m["map"] for m in maps
            if m["results"].get("dijkstra_nocut", {}).get("success") and any(not m["results"][mode]["success"] for mode in modes if mode.startswith("lunapath"))
        ]
        timeouts = [(m["map"], mode) for m in maps for mode in modes if m["results"][mode]["timed_out"]]
        lines.append(f"- **{variant}:** yalnız köşe-kesmeyle bağlantılı {len(cut_only)}/{len(maps)} harita" + (f": `{'`, `'.join(cut_only)}`" if cut_only else "") + ".")
        if nobody:
            lines.append(f"  - hiçbir modelde bağlantılı olmayan: `{'`, `'.join(nobody)}`.")
        if lp_worse:
            lines.append(f"  - saf Dijkstra (kesmesiz) yol bulurken LunaPath'in bulamadığı: `{'`, `'.join(lp_worse)}` — kural dışı bir fark; incelenmeli.")
        else:
            lines.append("  - kesmesiz Dijkstra'nın yol bulduğu her haritada LunaPath'in iki modu da yol buldu: fark köşe-kesme kuralındadır, planlayıcıda değil.")
        if timeouts:
            lines.append(f"  - 60 s'yi aşan koşular: {', '.join(f'`{m}`/{mode}' for m, mode in timeouts)}.")
        else:
            lines.append("  - 60 s'yi aşan koşu yok.")
    return lines + [""]


def _section_multi(report: dict) -> list[str]:
    lines = [
        "## 4. Çok kriterli mod ne satın alıyor",
        "",
        "Haritalar yalnızca eğim/pürüzlülük eşikli occupancy: gölge, termal, slip, pürüzlülük ve Dünya görünürlüğü katmanı yok, ham DEM de yayımlanmamış (eğim türetilemez). "
        "Adaptör eğimi ve gölgeyi 0, termali sabit verir; dört (beş) kriterin hepsi sabit kalır ve maliyet gridi tek değerdir. Araştırma belgesindeki \"çok kriterli maliyetin getirdiği X % gölge azalması\" cümlesi bu benchmark'ta **kurulamaz**.",
        "",
        "| Varyant | Maliyet gridi benzersiz değer (min–maks, harita başına) | `lunapath_single` = `lunapath_multi` uzunluk (harita) | Aynı hücre dizisi (harita) |",
        "|---|---|---|---|",
    ]
    for variant, block in report["variants"].items():
        maps = [m for m in block["maps"] if "skipped" not in m]
        uniq = [m["cost_grid_unique_values"] for m in maps]
        both = [m for m in maps if "lunapath_single" in m["results"] and "lunapath_multi" in m["results"]]
        same_len = sum(
            1 for m in both
            if m["results"]["lunapath_single"]["success"] == m["results"]["lunapath_multi"]["success"]
            and (not m["results"]["lunapath_single"]["success"] or abs(m["results"]["lunapath_single"]["length_cells"] - m["results"]["lunapath_multi"]["length_cells"]) < 1e-6)
        )
        same_steps = sum(1 for m in both if m["results"]["lunapath_single"].get("steps") == m["results"]["lunapath_multi"].get("steps"))
        rng = f"{min(uniq)}–{max(uniq)}" if uniq else "—"
        lines.append(f"| {variant} | {rng} | {same_len}/{len(both)} | adım sayısı eşit {same_steps}/{len(both)} (hücre dizisi eşitlik kırma yüzünden farklı olabilir) |")
    lines += ["", "Okuma: tek değerli gridde LunaPath A* en kısa yol aramasıdır; ağırlık seti yalnız sabitin büyüklüğünü (ve heap'teki eşitlik kırmayı) değiştirir. Çok kriterli modun ne satın aldığı yalnız bizim katmanlarımızın olduğu Site11'de ölçülebilir (nav2 baseline, C4 raporu).", ""]
    return lines


def _section_time(report: dict) -> list[str]:
    modes = report["modes"]
    memory_pass = bool(report.get("memory_pass"))
    lines = [
        "## 5. Süre ve bellek",
        "",
        "Bizim sürelerimiz planlayıcı çağrısının duvar saati (bu makine), `tracemalloc` kapalı. "
        + ("Bellek, aynı koşunun `tracemalloc` açık ikinci geçişindeki tepe değeridir; o geçişin süresi ayrı sütunda — tracemalloc bellek ayırmayı izlerken Python'u belirgin yavaşlatır. "
           if memory_pass else "Bellek ölçülmedi (`--memory` verilmedi). ")
        + "PathBench simülasyonu **tracemalloc açıkken** zamanlar ve süreye hücre hücre tekrar oynatmayı da katar (yazarların i7-1355U dizüstü, Python 3.8); makale MoonPlanBench için bellek vermiyor.",
        "",
        "| Varyant | Planlayıcı | Süre ort. (s) | Süre maks (s) | Süre, tracemalloc açık (s) | Bellek ort. (MB) | Düğüm ort. | Aşan koşu |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for variant, block in report["variants"].items():
        for mode in modes:
            agg = block["aggregates"][mode]
            mb = None if agg.get("mean_memory_kb") is None else agg["mean_memory_kb"] / 1000.0
            lines.append(f"| {variant} | `{mode}` | {_fmt(agg['mean_time_s'], 3)} | {_fmt(agg['max_time_s'], 3)} | {_fmt(agg.get('mean_time_s_traced'), 3)} | {_fmt(mb, 1)} | {_fmt(agg['mean_nodes_expanded'], 0)} | {agg['n_timed_out']} |")
        for name, agg in block.get("reference_aggregates", {}).items():
            lines.append(f"| {variant} | referans {name} | {_fmt(agg['mean_time_s'], 3)} | {_fmt(agg['max_time_s'], 3)} | — | — | — | {agg['n_timed_out']} |")
        paper = report.get("paper_table_1", {}).get(variant, {})
        for name in ("Dijkstra", "ThetaStar", "AStar"):
            if name in paper:
                lines.append(f"| {variant} | makale {name} (alıntı; tracemalloc açık, tekrar oynatma dahil) | {_fmt(paper[name]['time_s'])} | — | — | — | — | — |")
    lines += ["", "Harita başına en yavaş LunaPath koşuları:", ""]
    slow = []
    for variant, block in report["variants"].items():
        for m in block["maps"]:
            if "skipped" in m:
                continue
            for mode in modes:
                if mode.startswith("lunapath"):
                    slow.append((m["results"][mode]["time_s"], variant, m["map"], mode, m["results"][mode].get("nodes_expanded")))
    for t, variant, name, mode, nodes in sorted(slow, reverse=True)[:5]:
        lines.append(f"- {variant}/`{name}` `{mode}`: {_fmt(t, 1)} s, {_fmt(nodes, 0)} düğüm")
    if not slow:
        lines.append("- (LunaPath modu koşturulmadı)")
    return lines + [""]


def _section_claim(report: dict) -> list[str]:
    variants = report["variants"]
    modes = report["modes"]

    def rate(variant: str, mode: str):
        agg = variants[variant]["aggregates"].get(mode)
        return None if agg is None else agg["success_rate_pct"]

    cut = ", ".join(f"{v.split('-')[-1]}°: {_fmt(variants[v]['aggregates']['dijkstra_cut']['mean_length_cells'])}" for v in variants if "dijkstra_cut" in variants[v]["aggregates"])
    paper = ", ".join(f"{v.split('-')[-1]}°: {_fmt(report.get('paper_table_1', {}).get(v, {}).get('Dijkstra', {}).get('length_cells'))}" for v in variants)
    nocut_mode = "lunapath_multi" if "lunapath_multi" in modes else ("dijkstra_nocut" if "dijkstra_nocut" in modes else None)
    nocut = ", ".join(f"{v.split('-')[-1]}°: {_pct(rate(v, nocut_mode))}" for v in variants) if nocut_mode else "—"
    return [
        "## 6. İddia sınırı ve sunum cümlesi",
        "",
        "- Bu benchmark **yalnızca eğim (+ pürüzlülük) eşikli occupancy** gridleridir; hücre 320 m – 7 680 m (bölgesel ölçek, rover ölçeği değil). Başarı, bir hareket modeli altında bağlantılılık ve en kısa yol ölçümüdür; rota planlamasının fizik/termal/gölge boyutlarını ölçmez.",
        "- Makalenin %100'ü köşe-kesmeye izin veren hareket modeline bağlıdır; LunaPath'in güvenlik kuralıyla başarı oranı düşer ve bu **saklanmaz**, iki satır ayrı ayrı verilir.",
        "- Makaleden alınan her sayı \"alıntı\" etiketlidir; süreler makineler arası karşılaştırılmaz.",
        "- Öğrenilmiş planlayıcılar koşturulmadı; \"öğrenme tabanlı modeller gezegen arazisine genellemiyor\" bulgusu makalenin kendi sonucudur (§ 3.3, § 4.2.3: Radish'te WPN dışında hiçbiri yol bulamadı, WPN 10× yavaş; Ay/Mars tablolarında öğrenilmiş satır yok) ve öğrenilmiş planlayıcı kullanmama kararımızın literatür dayanağı olarak **alıntı** kalır.",
        "",
        f"**Sunum cümlesi:** \"Bağımsız, yalnızca eğim eşikli bir occupancy benchmark'ında (MoonPlanBench, {sum(len([m for m in b['maps'] if 'skipped' not in m]) for b in variants.values())} harita) benchmark'ın hareket modeliyle en kısa yol uzunluklarını makalenin Dijkstra satırıyla aynen ürettik ({cut}; makale {paper}); "
        f"LunaPath'in köşe-kesme yasağıyla başarı {nocut} — makalenin %100'ü, düşük eşikli varyantta iki dolu hücre arasından çapraz geçmeye dayanıyor. Çok kriterli maliyet bu haritalarda tek değerdir; gölge/termal kazancı burada ölçülemez, Site11'de ölçülür.\"",
        "",
        f"Makine-okunur iddia (`app.benchmark.CLAIM`): {report.get('claim', '')}",
        "",
        "## Kaynaklar",
        "",
        f"- {PAPER_TITLE} — {PAPER_AUTHORS}, arXiv:{PAPER_ARXIV}, {PAPER_URL}",
        f"- {REPO_URL} (commit `{REPO_COMMIT}`); PathBench (Toma vd., BSD-3); PythonRobotics (Sakai vd., MIT)",
        "",
    ]


def _relative_to_repo(path: str | None) -> str:
    if not path:
        return "—"
    try:
        return Path(path).resolve().relative_to(_ROOT).as_posix()
    except ValueError:
        return Path(path).name


def render_markdown(report: dict) -> str:
    reference = report.get("reference", {})
    lines = [
        "# MoonPlanBench dış benchmark (D2) — LunaPath raporu",
        "",
        f"Üretildi: {report.get('generated_utc')} (`scripts/moonplanbench_runner.py`). Veri: `{_relative_to_repo(report.get('data_dir'))}`. "
        f"Modlar: {', '.join(f'`{m}`' for m in report['modes'])}. Referans planlayıcılar: {'koşturuldu' if reference.get('status') == 'run' else 'koşturulmadı'} ({reference.get('status')}).",
        "",
        "**İddia sınırı:** haritalar yalnızca eğim/pürüzlülük eşikli occupancy gridleridir (gölge, termal, slip, pürüzlülük, Dünya görünürlüğü katmanı yok; ham DEM yok); hücre 320 m – 7 680 m; "
        "LunaPath'in çok kriterli maliyet gridi bu haritalarda tek değerdir ve planlayıcı kendi güvenlik kurallarıyla en kısa yol aramasına indirgenir. Benchmark'ın referans planlayıcıları köşe-kesmeye izin verir, LunaPath vermez. Makale sayıları alıntıdır.",
        "",
    ]
    lines += _section_data(report) + [""]
    lines += _section_metrics(report)
    lines += _section_success(report)
    lines += _section_multi(report)
    lines += _section_time(report)
    lines += _section_claim(report)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=MOONPLANBENCH_DIR)
    parser.add_argument("--maps", type=int, default=None, help="run only the first N maps of each variant (quick mode)")
    parser.add_argument("--modes", default=",".join(MODES), help="comma-separated subset of " + ", ".join(MODES))
    parser.add_argument("--reference-dir", default=None, help="local clone of PlanetaryPathBench; adds the benchmark's own planners")
    parser.add_argument("--rover", default="lpr_1")
    parser.add_argument("--memory", action="store_true", help="second pass per mode under tracemalloc for peak memory (slower)")
    parser.add_argument("--json", default=None, help="dump the raw results as JSON (written before the markdown)")
    parser.add_argument("--from-json", default=None, help="render the markdown from a previous --json dump instead of running")
    parser.add_argument("--output", default=str(_ROOT / "docs" / "research" / "moonplanbench_report.md"))
    args = parser.parse_args(argv)

    if args.from_json:
        report = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
    else:
        modes = [m.strip() for m in args.modes.split(",") if m.strip()]
        t0 = time.perf_counter()
        try:
            report = run_benchmark(
                args.data_dir, modes=modes, max_maps=args.maps, reference_dir=args.reference_dir,
                rover_id=args.rover, progress=lambda msg: print(f"  {msg}", flush=True), memory=args.memory,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"cannot run: {exc}")
            return 1
        print(f"ran in {time.perf_counter() - t0:.0f} s")
        if args.json:
            Path(args.json).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"wrote {args.json}")

    markdown = render_markdown(report)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown + "\n", encoding="utf-8")
    print(f"wrote {out}")
    for variant, block in report["variants"].items():
        summary = ", ".join(f"{mode} {_pct(block['aggregates'][mode]['success_rate_pct'])}" for mode in report["modes"])
        print(f"  {variant}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
