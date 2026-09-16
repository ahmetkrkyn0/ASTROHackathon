# D5 — Ağırlık simpleksi taraması ve baskın-olmayan rota ailesi — Uygulama Planı

**Tasarım:** [2026-09-16-d5-pareto-cephesi-design.md](../specs/2026-09-16-d5-pareto-cephesi-design.md)
· **Dal:** `tuna/backendEnhance` · **Tarih:** 16 Eylül 2026

---

## Adım 0 — Temiz HEAD'i ölç

- [x] `git status` temiz (yalnız untracked `bulgular.md`, dokunulmadı).
- [x] a627b05'te tam paket koşuldu: **25 failed / 2 318 passed / 5 skipped (32 dk 25 s)**.
      25'inin hepsi `*_real_grid.py`'de; FAILED listesi karşılaştırma için saklandı.
- [x] `ruff check backend/app` → **12** (taban).

## Adım 1 — Var olanı oku (kod yazmadan)

- [x] `backend/app/risk.py` + `/api/risk-sweep` (B2 deseni: istek şeması, entry-başına `error`,
      `plan_ms`, `claim`/`references`).
- [x] `backend/app/profile_comparison.py` — **`ai_tools.py:34` import ediyor**; genişletilmeyecek.
- [x] `backend/app/rover_grids.py` — `grids_for_rover`'da **hiç önbellek yok**; ağırlık başına tam
      yeniden hesap. Önbellek patlaması riski yok, CPU maliyeti var.
- [x] `cost_engine.resolve_weights` — normalizasyon **yok**, kısmi override rover varsayılanına düşer.
- [x] Hedef alanları: üçü `summary`, biri `astar_metrics`; **termal bir ceza, marj değil**.
- [x] Rover ağırlıkları `get_rover` ile doğrulandı: dört profilde de ilk dört **tam 1,0**.

## Adım 2 — Literatürü birinci elden oku

- [x] Boyd & Vandenberghe §4.7.4, Das & Dennis 1997, Könen & Stiglmayr 2025 (terminoloji),
      Miettinen slaytı — hepsi verbatim alındı.
- [x] ETH `lunar_planner` (arXiv:2406.16376, MIT): **aynı yöntem** (`α+β+γ=1`) — doğrudan emsal.
- [x] Lavin arXiv:1505.05947 okundu: **rota cephesi üretmiyor**, tek rota döndürüyor. Araştırma
      belgesinin atfı düzeltildi.
- [x] RoverDevKit arXiv:2606.21755 okundu: ağırlıklı-toplam karşılaştırması **yok**; o atıf
      kullanılmadı.
- [x] "duality gap" terimi **reddedildi**; doğru terim supported/unsupported.

## Adım 3 — Sondalar (gerçek Site11 gridi)

- [x] Sonda 1-2: dört senaryo × 25 vektör → 15-24 farklı rota, **1-2** baskın-olmayan.
- [x] Sonda 3: 10 alternatif hedef kümesi → hepsi çöküyor (hedef seçimimizin artefaktı değil).
- [x] Sonda 4: bütçe eğrisi 9 → 211 vektör; cephe **1 → 4**. İlk manşet düzeltildi.
- [x] Sonda 5: B2 CVaR bandı aynı rotada α=0,5'te **+%16,90** → cephe bandın ~1/94'ü.

## Adım 4 — Düşmanca tasarım incelemesi (yazmadan önce)

- [x] Beş bağımsız lens; yayımlanmadan düzeltilenler spec'in
      "Düşmanca incelemenin düzelttikleri" bölümünde.

## Adım 5 — `backend/app/pareto.py`

- [x] `simplex_samples` (normalize `standard_exponential`, `include_corners`), `route_id`,
      `dominance_epsilon`, `dominates`, `non_dominated`, `objectives_from`,
      `solve_weight_vector`, `sweep`, `diagnostics`.
- [x] `PARETO_OBJECTIVES` (kaynak + birim + **yön** + not), `OBJECTIVE_QUANTUM`,
      `PARETO_METHOD/COMPLETENESS/CLAIM`, `PARETO_QUOTED`, `PARETO_REFERENCES`.
- [x] Mahsur rotalar **dışlanıyor**; rotalar **hücre dizisiyle** tekilleştiriliyor.

## Adım 6 — `POST /api/pareto` (yalnızca ekleme)

- [x] `ParetoRequest` (`n_samples` ≤ `MAX_PARETO_SAMPLES`=40, `seed`, `include_corners`, `epsilon`).
- [x] `MAX_PARETO_SAMPLES`, `DEFAULT_PARETO_SEED` sabitleri gerekçeleriyle.
- [x] `_active_grids` → 503, `_to_pixel`/`_validate_start_goal` → 422; B2 ile aynı sözleşme.

## Adım 7 — Testler

- [x] `backend/test_pareto.py` — 25 birim (simpleks, tekrarlanabilirlik, 1-ULP dirichlet farkı,
      rota kimliği, dominans, epsilon/kuantum, sabit eksen, Spearman).
- [x] `backend/test_pareto_api.py` — 22 API (bloklar, yön alanları, sayımlar, tekilleştirme,
      determinizm, `pareto_front` **yok**, 422 bataryası, 503).
- [x] `backend/test_pareto_real_grid.py` — 19 gerçek grid (**v5 SHA kilidi**, `COST_MODEL_ID`,
      nominal rota `astar` ile aynı, cephe iç tutarlılığı, teşhislerin dürüstlüğü).
- [x] Üçü birlikte: **66 passed**.

## Adım 8 — Bayat etiket düzeltmesi

- [x] 7 "AHP" yorumu/docstring'i düzeltildi (`costmap`, `cost_engine` ×5, `pathfinder` ×2).
      Yalnız metin; tek ifade değişmedi.

## Adım 9 — Rapor, belgeler, doğrulama

- [x] `scripts/pareto_front_report.py` (`--json` / `--from-json` / `--out`).
- [x] `docs/research/pareto_front_report.md` üretildi; `--from-json` **birebir** yeniden üretiyor.
- [x] Sözleşme eki (`## Değişmeyenler`'den ÖNCE, yalnızca ekleme), README satırı,
      araştırma belgesine ✅ + "Yapıldı".
- [x] `ruff`: yeni dosyalar **0**, `backend/app` **12** (değişmedi).
- [x] Tam paket: **25 failed / 2 384 passed / 5 skipped (26 dk 59 s)**; FAILED listesi
      a627b05'inkiyle (**25 failed / 2 318 passed**) `comm` ile karşılaştırıldı ve
      **birebir aynı** çıktı. 2 318 + 66 = 2 384.

---

## Sapmalar

1. **`include_corners` planda yoktu.** Ölçüm simpleksin bir köşesinin cephede olduğunu gösterdi;
   iç bölgeden çekilen vektörler onu bulamıyor. Varsayılan `False`, uçta ve rapor betiğinde açılıyor.
2. **Mahsur rotalar dışlandı, yalnız işaretlenmedi.** Totalleri yalnız yürüyebildikleri öneki
   anlattığı için erken başarısız olarak cepheye girerlerdi.
3. **`completeness` "convex_hull_only" değil "no_guarantee" oldu.** Ağırlıklar hedefleri değil
   kriterleri skalerleştirdiği için dışbükeylik teoremi burada hiç uygulanmıyor; "yalnız dışbükey
   kabuk" demek sahip olmadığımız bir garantiyi iddia etmek olurdu.
4. **Yanıt `pareto_front` anahtarı taşımıyor.** Üretilen şey `non_dominated`.
5. **İlk manşet ("cephe tek noktaya çöküyor") yayımlanmadı**; bütçe eğrisi onu düşürdü.
6. **Raporda bir hata bulundu ve düzeltildi** (cephe genişliği yerine tüm rotaların genişliği
   basılıyordu); artık iki sütun yan yana.
7. **Hipervolüm yapılmadı** — 1-4 elemanlı, gürültü içindeki bir cephede darlığı gizlerdi.
8. **`pymoo` eklenmedi** (C5'in `pandas` emsali); 4-B tarama kapsam dışı (B2'nin sınırı).
