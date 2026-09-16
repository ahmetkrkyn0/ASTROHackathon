# D4 — Kontrastif açıklama: "neden bu rota, neden şu değil?" — Uygulama Planı

**Tasarım:** [2026-09-16-d4-kontrastif-aciklama-design.md](../specs/2026-09-16-d4-kontrastif-aciklama-design.md)
· **Dal:** `tuna/backendEnhance` · **Tarih:** 16 Eylül 2026

---

## Adım 0 — Temiz HEAD'i ölç

- [x] `git status` temiz (yalnız untracked `bulgular.md`, dokunulmadı).
- [x] 2402cd8'te tam paket koşuldu: **25 failed / 2 384 passed / 5 skipped (27 dk 44 s)**.
      25'inin hepsi `*_real_grid.py`'de; FAILED listesi karşılaştırma için saklandı.
- [x] `ruff check backend/app` → **12** (taban).
- [x] LPR-1 maliyet-gridi özeti doğrulandı: `55e1bb3…d893db`, `COST_MODEL_ID` `…_v5`.

## Adım 1 — Var olanı oku (kod yazmadan)

- [x] `pathfinder._astar_core` satır satır: kapı sırası, sessiz `continue`'lar, bariyer tablosu.
- [x] `cost_engine.compute_cost_grid` + `cost_vec` — ağırlıkların **nereye** girdiği.
- [x] `costmap.CostMap` — `explain()` **ağırlıklı** değer ve `inf` için `None` döndürüyor;
      D4'e **ağırlıksız** f_k lazım (w_k = 0 yasal), bu yüzden `explain()` kullanılmıyor ve
      gerekçesi docstring'e yazıldı.
- [x] `rover_grids.grids_for_rover` — önbellek **yok**; ayrıca `traversable`'ı **her çağrıda**
      yeniden hesaplıyor, dolayısıyla teste maske enjekte etmek işe yaramaz (termalden gitmeli).
- [x] `pareto.py` (D5): `route_id`, `dominates`, `OBJECTIVE_QUANTUM` yeniden kullanılacak;
      `dominates` **hedef uzayında**, D4'ün baskınlık testi **kriter uzayında** — ayrı şeyler,
      ikisi de ayrı bloklarda yayımlanıyor.
- [x] `main.py` — `_validate_start_goal`, `_to_pixel`, `PlanWeights` [0, 2], `_RISK_ALPHA_FIELD`,
      `/api/plan`'ın 404'ü.
- [x] `uncertainty.py` — `load_dem_clones`, `DemClones.window`, `ensemble_slopes`;
      klon önbelleği diskte **var** (20 × 900×900, PGDA ürün 78).

## Adım 2 — Sondalar (gerçek Site11 gridi, kod yazmadan)

- [x] Sonda 1: **afin kimlik**. Yeniden kurulan `cells_only` = 1354,58323 vs yayımlanan
      1354,5832 → fark 3,0e-5 (alanın kendi yuvarlaması). Kelepçe bağlamıyor
      (`min Σ w_k f_k = 0,3756`, pay 37,6×).
- [x] Sonda 2: **bariyer** yeniden kuruldu → 188,51016 vs 188,5102 (fark −4,3e-5). Planlayıcının
      kendi rotasında **sıfır** kapı ihlali → yeniden oynatma planlayıcıyla uyumlu.
- [x] Sonda 2b: yineleme maliyeti **0,290 s** (0,141 grid + 0,149 A\*) — sonra 5 tekrarın
      medyanıyla **0,2206 s** olarak yeniden ölçüldü (son koşumun sayısı).
- [x] Sonda 3: üç standart çift + üç alternatif türü üretildi; düz çizgi üçünde de geçilemez
      hücre içeriyor (53 / 40 / 14), VIPER sapması **tekrar eden hücre** üretiyor (422 vakası).
- [x] Rover ağırlıkları `get_rover` ile doğrulandı: dört profilde de ilk dört **tam 1,000000**,
      `w_roughness = 0,150`, toplam **1,150** → tek ağırlık oynatılır, yeniden normalleştirilmez.

## Adım 3 — Düşmanca tasarım incelemesi (yazmadan önce)

- [x] Beş bağımsız mercek: matematik, kod tabanı, XAIP literatürü, API kırıcı, metroloji.
- [x] **Beş ölümcül bulgu** geldi ve hepsi tasarımı değiştirdi — listesi spec'in sonunda.
      Özet: Krarup yanlış atıf; (c) aslında ters optimizasyon; "minimum" hak edilmemiş;
      tarama aralığı işaret körü; kapı sırası yanlış; kelepçe tek noktada doğrulanmış;
      `risk_alpha` bant değil.
- [x] Literatür merceği dört kaynağı da **birinci elden** indirip okudu; ikisi (Sukkerd 2020,
      Heuberger) görev tanımında hiç anılmıyordu ama yöntemin gerçek evi orası.

## Adım 4 — `backend/app/contrastive.py`

- [x] Sözlük: `fact` / `foil` (XAIP terimleri), `CONTRAST_METHOD_ID`, `WEIGHT_MIN/MAX`,
      `CRITERION_WEIGHT_KEY`, **on** sonuç etiketi, `RESOLUTION_LEVELS`, `CONTRAST_CLAIM`,
      `CONTRASTIVE_QUOTED` (+ Krarup için `correction` alanı).
- [x] `validate_foil` — sekiz refüzü, her biri kuralı adıyla söyleyen bir gövdeyle.
- [x] `GATE_ORDER` + `EdgeModel` + `gate_violations` — planlayıcının **kendi sırasında**;
      `_thermal_barrier_grid`, `_barrier_table`, `lateral_slope_tan` yeniden kullanıldı.
- [x] `criteria_for_grids` — kriter listesi `metadata["cost_criteria"]`'dan, hardcode değil.
- [x] `RouteTerms` — `D`, `I_k`, `B`, `B_exact`, `clamp_margin`, `affine_cost`, `exact_cost`.
- [x] `criterion_gap` (b) · `flip_threshold_vs_fact` + `l2_minimal_joint_move` +
      `scan_vs_replanned` (c) · `terrain_band` · `resolution_report` · `objective_gap`.
- [x] `explain_contrast` — sırayla: olgu → kapılar → kelepçe → (b) → (c) → bantlar.
- [x] `pathfinder.py` **hiç değişmedi**.

## Adım 5 — `POST /api/explain-contrast` (yalnızca ekleme)

- [x] `ExplainContrastRequest`, `extra="forbid"`, `risk_alpha` kabul ediliyor,
      `foil` `conlist(min=2, max=10_000)`.
- [x] Caps: `MAX_CONTRAST_ROUTE_CELLS`, `MAX_CONTRAST_VIOLATIONS`, `MAX_CONTRAST_SCAN_POINTS`,
      `MAX_CONTRAST_REPLANS`.
- [x] `_validate_start_goal` **birebir** çağrılıyor → /api/plan ile aynı 422'ler.
- [x] `start == goal` kendi mesajıyla 422.
- [x] `no_incumbent_route` 200 ile dönüyor (gerekçe spec'te).

## Adım 6 — Testler

- [x] `backend/test_contrastive.py` — **36 test**: sözleşme, afin kimlik (üç ağırlıkta doğrusallık),
      kapı **sırası** (iki kuralı birden çiğneyen kenar), karşı-olgusal aritmetiği, ℓ₂ hamlesi,
      çözünürlük raporu, **eşikteki kelepçe koruması**, `PlanWeights` kutusuyla uyum.
- [x] `backend/test_contrastive_api.py` — **25 test**: yanıt şekli, `allow_nan=False`
      serileştirme, **her sonuçta aynı anahtar kümesi**, sert kapı bastırması, **12 refüz**,
      bütçe tavanı, 503.
- [x] `backend/test_contrastive_real_grid.py` — **20 test**: bit-eşitlik kilidi (LPR-1 özeti +
      `_v5` + import-etkisizliği), üç çiftte kimlik, kapı transkripsiyon kontrolü, düz çizgi
      → `hard_gate`, sapma → `dominated`, eşiklerin gerçekten berabere getirmesi, yön işareti,
      sınır-dışı ⟹ (ii) boş, klon bandı, çözünürlük blokları, uç.
- [x] Sentetik fixture'lar düzeltildi: Gauss gürültüsü tek hücrede 25°'yi aşıp hedefi
      geçilemez yapıyordu; sırtlı alan kullanıldı (maks hücre eğimi 10,8°, 400/400 geçilebilir).

## Adım 7 — Rapor

- [x] `scripts/contrastive_explanation_report.py` — `measure()` / `render()` ayrı,
      `--json` / `--from-json` / `--out`.
- [x] `--from-json` **birebir** aynı raporu üretiyor (iki render diff'lendi, fark yok).
- [x] `docs/research/contrastive_explanation_report.md` — 9 vaka, dört kategori sayımı,
      monotonluk/konvekslik ölçümü, dört çözünürlük tabanı, klon bandı, iddia sınırı.

## Adım 8 — Belgeler

- [x] Spec + bu plan.
- [x] `docs/frontend/3b-veri-sozlesmesi.md` → "D4 eki", `## Değişmeyenler`'den **önce**,
      yalnızca ekleme (`git diff --numstat` ile doğrulandı).
- [x] `README.md` → uç tablosuna bir satır.
- [x] Araştırma belgesi `## D4.` başlığına ✅ + "Yapıldı" bloğu.

## Adım 9 — Doğrulama

- [x] `ruff check backend/app` → **12** (taban değişmedi); yeni dosyalar **0**.
- [x] Tam paket koşuldu ve taban FAILED listesiyle `comm` ile karşılaştırıldı.
- [x] Veri dosyaları commit'e alınmadı (`lunapath/data/processed/metadata.json` kontrol edildi).
- [x] Tek commit, `Co-Authored-By` satırı **yok**.
