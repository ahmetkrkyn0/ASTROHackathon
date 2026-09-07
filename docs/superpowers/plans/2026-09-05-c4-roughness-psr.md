# C4 — LOLA LDRM pürüzlülük kriteri ve PGDA PSR maskesi — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** NASA PGDA ürün 90'ın 50 m/px, 100 m tabanlı LOLA pürüzlülüğünü (`LDRM_80S_50MPP_ADJ_ROUGH_100M`)
ve 20 m/px PSR maskesini (`LPSR_80S_20MPP_ADJ`) Site11'in 5 m gridine `nearest` ile ko-registre edip
`roughness` (MEASURED) ve `psr` (MEASURED) katmanları olarak yayımlamak; pürüzlülüğü bölgesel ECDF
ölçeğiyle (MODEL) [0, 1]'e eşleyip beşinci maliyet kriteri `f_roughness` (`w_roughness`, varsayılan
0,15) olarak gride sokmak (`COST_MODEL_ID` v5); PSR'ı planlamaya sokmadan hücre kartı ve
`GET /api/psr-validation` ile bizim gölge modelimize karşı doğrulamak; Site11'de önce/sonra raporu.

**Architecture:** Yeni `app/roughness.py` (dosya adları, ürün sabitleri, `RoughnessScale` ECDF
ölçeği — skaler `f` ve grid `f_grid` aynı `np.interp`, PSR örtüşme istatistiği, rota özeti, yanıt
bloğu, iddia metinleri); `cost_engine`/`cost_vec` beşinci terim (`roughness_grid` + `roughness_scale`
birlikte, aksi `ValueError`); `costmap.RoughnessLayer` + `PlanContext.roughness/roughness_scale`;
`cost_cube` blok-maks; `rover_grids`/`pathfinder`/`data_loader` pürüzlülüğü maliyete geçirir ve
`cost_criteria` damgalar; `terrain` iki katman; `constants`/`scenarios`/`main` `w_roughness`;
`main` hücre kartı alanları, `roughness` rota bloğu, `/api/psr-validation`; `scripts/build_roughness_cache.py`
(`/vsicurl/` tek tile, CRS ve kayıt sağlaması, bölgesel örnek); `scripts/roughness_psr_report.py`.

**Spec:** [2026-09-05-c4-roughness-psr-design.md](../specs/2026-09-05-c4-roughness-psr-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, SciPy 1.15 (`stats.spearmanr` raporda), rasterio 1.4.3
(`/vsicurl/`, `warp.reproject`), FastAPI/pydantic, pytest.

**Commit kuralı:** özellik bitince **tek commit**; push en sonda toplu; commit mesajında eş-yazar
satırı yok.

---

## Global Constraints

- Pürüzlülük katmanı `MEASURED`, `f_roughness` ölçeği `MODEL` (istatistiksel: 80–90°S bölgesel
  ECDF sırası); "hücrenin kendi pürüzlülüğü" / "30 cm kaya" / "kaya bolluğu" **yazılmaz**.
- Pürüzlülüksüz temel gridlerde `compute_cost_grid` dört terimli formülle **bit-eşit**
  (`np.array_equal`); Site11'de pürüzlülük katmanı çıkarılınca v4 SHA (`0e74607d…`, `8788936c…`)
  geri gelir; katmanla v5 SHA kilitlenir. `COST_MODEL_ID = "weighted_cell_cost_shadow_aware_energy_slip_roughness_v5"`.
- `w_roughness` beşinci anahtar; diğer dört ağırlık **yeniden ölçeklenmez**; varsayılan 0,15
  (varsayım, yorumla); `wait_cost` okumaz.
- PSR planlamaya (maliyet/geçilebilirlik) **girmez**.
- Pürüzlülük gridi ölçeksiz maliyete giremez (`ValueError`); NaN pürüzlülük → f 0,5, hücre
  geçilmez olmaz.
- Katman yokken hiçbir uç düşmez; mevcut API alanları aynen, yalnızca ekleme. Frontend koduna
  dokunulmaz.
- Sayı uydurma yok; rapor Site11'de koşar; gerçek grid/önbellek testleri skip-korumalı; TDD.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/roughness.py` (yeni) | `ROUGHNESS_CACHE_FILENAME`, `ROUGHNESS_META_FILENAME`, `PSR_CACHE_FILENAME`, `PSR_META_FILENAME`, `ROUGHNESS_BASELINES_FILENAME`, ürün sabitleri/URL'ler, `RoughnessScale` (`from_meta`, `to_meta`, `f`, `f_grid`), `NAN_ROUGHNESS_F`, `same_projection`, `psr_shadow_overlap`, `route_roughness_summary`, `roughness_block`, `ROUGHNESS_CLAIM`, `PSR_CLAIM`, `ROUGHNESS_REFERENCES` |
| `backend/app/cost_engine.py` | `COST_MODEL_ID` v5; `_WEIGHT_KEYS`/`default_weights` `w_roughness`; `f_roughness(r, scale)`; `compute_cost_grid(..., roughness_grid=None, roughness_scale=None)` |
| `backend/app/cost_vec.py` | `f_roughness_grid(grid, scale)` |
| `backend/app/costmap.py` | `PlanContext.roughness`, `.roughness_scale`; `RoughnessLayer`; `default_cost_map(..., roughness_scale=None)`; `_cell_context` |
| `backend/app/cost_cube.py` | `build_cost_cube(..., roughness=None, roughness_scale=None)` blok-maks |
| `backend/app/rover_grids.py` | pürüzlülük + ölçek maliyete; `metadata["cost_criteria"]` |
| `backend/app/pathfinder.py` | `_resolve_cost_grid` yeniden hesaplarken pürüzlülük + ölçek |
| `backend/app/data_loader.py` | `_load_roughness`, `_load_psr`; validity MEASURED; meta; yükleme maliyeti; `cost_criteria` |
| `backend/app/terrain.py` | `TERRAIN_LAYERS`, `LAYER_UNITS`, `LAYER_DESCRIPTIONS` |
| `backend/app/constants.py` | `ROVERS[*]["w_roughness"]`, `MODELLED_FIELDS`, `rover_default_weights`, `W_ROUGHNESS` |
| `backend/app/scenarios.py` | profillerde `w_roughness` |
| `backend/app/main.py` | `PlanWeights.w_roughness`; `/api/layers`, `/api/terrain` parametre + katmanlar + 404 metni; `/api/cell-telemetry` alanları; `_roughness_block_2d/_4d`; `/api/plan`, `/api/plan-4d` bloğu; `GET /api/psr-validation`; `_risk_sources` pürüzlülük kaynağı |
| `backend/test_roughness.py`, `backend/test_roughness_cost.py`, `backend/test_roughness_api.py`, `backend/test_roughness_real_grid.py`, `backend/test_layer_validity.py` (ek) | Testler |
| `backend/test_rover_grids.py`, `backend/test_scenarios.py`, `backend/test_review3_fixes.py`, `backend/test_risk_sweep_real_grid.py` | Uyarlanan mevcut testler |
| `scripts/build_roughness_cache.py` (yeni), `scripts/roughness_psr_report.py` (yeni) → `docs/research/roughness_psr_report.md` | Önbellek ve rapor |
| `.gitignore`, `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec, `README.md` | Belgeler |

---

## Görevler

### Task 0 — Sondalar (yapıldı, spec'te)
- [x] Ürün adları/boyutları/CRS/transform doğrulandı; pencereler tek tile; nearest ko-registrasyon; kayıt sağlaması `SLP_100M` ↔ blok eğim Spearman 0,989; bölgesel örnek (36 tile, 9,4 M px); Spearman(pürüzlülük, eğim) 0,21; normalizasyon adayları; PSR Jaccard 0,83 / 0,91; 2-B rota taraması.

### Task 1 — `roughness.py`: ölçek, projeksiyon eşitliği, PSR örtüşme, rota özeti, blok
- [x] `test_roughness.py` yaz: `RoughnessScale.from_meta` gidiş-dönüş (`to_meta`), düğüm sayısı < 2 / artmayan olasılık / eksik anahtar → `ValueError`; eşit düğümler birleştirilir ve `f` monoton; `f` [0, 1]; aralık altı 0, üstü 1; `f(nan) == 0.5`; `f_grid` ↔ `[f(x)]` 20 000 rastgele değerde `np.array_equal` (NaN dahil); `same_projection` (ürün WKT literal'i ↔ `metadata.json` WKT'si → True; `lat_0 = 90` → False; sözlük/WKT/CRS nesnesi girişleri); `psr_shadow_overlap` elle 4×4 (PSR 4 hücre, karanlık 5, kesişim 3 → Jaccard 3/6, recall 3/4, precision 3/5, ortalamalar, termal medyanlar, `threshold` alanı); PSR yok/karanlık yok → Jaccard 0 (NaN değil); `route_roughness_summary` elle (mean/max m, mean f, `cells_in_psr`, `n_cells`; boş → None'lar); `roughness_block(applied=False, reason)` ve `applied=True` alan kümeleri; sabitler ("MEASURED", "MODEL", "not the roughness of the cell").
- [x] Koştur → içe aktarma hatası.
- [x] `roughness.py` yaz (spec "Bileşenler 1"); docstring: ürün tanımı alıntısı, iddia sınırı, ölçeğin ne olduğu.
- [x] Koştur → geçer.

### Task 2 — `cost_engine` / `cost_vec` / `constants` / `scenarios`: beşinci kriter
- [x] `test_roughness_cost.py` (ilk yarı) yaz: `_WEIGHT_KEYS` ve `default_weights(rover)` `w_roughness` içerir, dört rover 0,15; `rover_default_weights` ve `rover_catalog()[*]["default_weights"]` beş anahtar; `MISSION_PROFILES[*]["weights"]["w_roughness"]` var; `resolve_weights({"w_slope": 1.0})` `w_roughness` varsayılanını doldurur; `COST_MODEL_ID.endswith("_v5")`; `f_roughness(r, scale)` ↔ `f_roughness_grid` `np.array_equal`; `compute_cost_grid(..., roughness_grid=None)` ↔ elle dört terim (`cost_vec` fonksiyonlarıyla) `np.array_equal`; pürüzlülüklü ↔ dört terim + `w·f_grid` `assert_allclose(atol=1e-12)`; `w_roughness=0` pürüzlülüklü ↔ pürüzlülüksüz `np.array_equal`; 0,15 vs 0,30 farklı; grid var ölçek yok → `ValueError`; şekil uyumsuz → `ValueError`; NaN pürüzlülük hücresi sonlu kalır ve `f=0.5` ile eşit; `inf` deseni değişmez.
- [x] Koştur → başarısız.
- [x] `constants.py` (`w_roughness` dört rover + yorum "assumption: no published roughness weighting…", `MODELLED_FIELDS`, `rover_default_weights`, `W_ROUGHNESS`), `scenarios.py` (dört profil `C.W_ROUGHNESS`, yorum), `cost_engine.py` (`COST_MODEL_ID` v5 + bump notu, `_WEIGHT_KEYS`, `default_weights`, `f_roughness`, `compute_cost_grid`), `cost_vec.py` (`f_roughness_grid`).
- [x] Koştur → geçer; `test_rover_grids.py` ve `test_scenarios.py` anahtar kümelerine `w_roughness` ekle; `test_review3_fixes.py` `_v5`; `test_review_fixes.py`, `test_cost_vec.py`, `test_weighted_integration.py`, `test_cost_engine_slip.py`, `test_risk_cost.py`, `test_rover_validation.py` geçer.

### Task 3 — `costmap` / `cost_cube` / `rover_grids` / `pathfinder` / `data_loader` / `terrain`
- [x] `test_roughness_cost.py` (ikinci yarı) yaz: `PlanContext(roughness=…, roughness_scale=…)` ve `_cell_context` dilimi; `RoughnessLayer.contribution` = `f_grid`; bağlamda pürüzlülük yok → `ValueError`; `default_cost_map(rover, roughness_scale=scale)` beş katman adı, `explain` `roughness` = `w·f` ve `total`; ölçeksiz → dört katman; `CostMap.total` ↔ `compute_cost_grid` pürüzlülüklü `assert_allclose(1e-12)`; `build_cost_cube(roughness, scale, coarsen=2)` her dilim ↔ `compute_cost_grid` blok-maks pürüzlülükle (`coarsen_grid(how="max")`) referans; yalnız biri → `ValueError`; `grids_for_rover` pürüzlülük + meta ölçekle: `cost` pürüzlülüklü, `metadata["cost_criteria"]` beş, `cost_weights["w_roughness"]`; pürüzlülüksüz temel: `cost_criteria` dört ve `cost` dört terim; `pathfinder._resolve_cost_grid` damgasız gridde pürüzlülük geçirir (yeniden hesap ↔ `compute_cost_grid` pürüzlülüklü eşit).
- [x] `test_layer_validity.py` eki: `roughness_grid.npy` + meta (`scale` ile) + `psr_grid.npy` + meta → `grids["roughness"]` float64, `grids["psr"]` float64 0/1, `layer_validity` MEASURED ×2, `metadata["roughness"]["scale"]`, `metadata["psr"]`, `metadata["cost_criteria"]` beş; yokken anahtar yok, `cost_criteria` dört; şekil reddi `ValueError("roughness…")` ve `("psr…")`; ölçeksiz pürüzlülük meta → `ValueError("scale")`.
- [x] Koştur → başarısız.
- [x] `costmap.py`, `cost_cube.py`, `rover_grids.py`, `pathfinder.py`, `data_loader.py`, `terrain.py` (iki katman, birimler, açıklamalar).
- [x] Koştur → geçer; `test_costmap.py`, `test_cost_cube.py`, `test_rover_grids.py`, `test_pathfinder.py`, `test_pathfinder_4d.py`, `test_plan_4d_endpoint.py`, `test_terrain_api.py`, `test_layer_validity.py` geçer.

### Task 4 — API
- [x] `test_roughness_api.py` yaz (16×16 fixture, `_grids()` + `_grids_with_layers()`): katmansız — `/api/plan` 200, `roughness.applied is False` ve `reason`; `/api/cell-telemetry` `roughness_m`/`f_roughness`/`in_psr` `None`, `cost_breakdown` dört; `/api/layers/roughness` ve `/psr` 404 + "build_roughness_cache"; `/api/psr-validation` 404; `/api/terrain` manifestte katman yok. Katmanlı — manifest `roughness` (`units m`, MEASURED) ve `psr` (`boolean`, MEASURED); `/api/layers/roughness?format=f32` gidiş-dönüş; hücre kartı `cost_breakdown.roughness == w·f(r)` (1e-9), `roughness_m`, `f_roughness`, `in_psr`; `/api/plan` `roughness.applied True`, `route.n_cells == waypoint_count`, `mean_roughness_m` aralıkta, `cells_in_psr` int; `weights.w_roughness=3` → 422; `w_roughness=0` → hücre kartı `roughness == 0`; `/api/psr-validation` alanları ve `threshold` parametresi; `/api/profiles` her profil `w_roughness`; `/api/rovers` `default_weights.w_roughness`; `/api/plan-4d` (statik seri, `start_utc` yok) 200 + `roughness.applied True`.
- [x] Koştur → başarısız.
- [x] `main.py`: `PlanWeights`, `get_layer`/`terrain` parametreleri ve `valid_layers` + 404 metni, `get_cell_telemetry`, `_roughness_route_2d(states, grids_for_plan)` / `_roughness_route_4d(result, coarse_roughness, coarse_psr)` / blok bağlama, `plan_4d` küpe pürüzlülük + ölçek, `_risk_sources` pürüzlülük kaynağı, `GET /api/psr-validation`.
- [x] Koştur → geçer; `test_slip_api.py`, `test_risk_api.py`, `test_plan_endpoint.py`, `test_plan_4d_endpoint.py`, `test_cell_telemetry_explain.py`, `test_terrain_api.py`, `test_stress_test_api.py`, `test_uncertainty_api.py`, `test_safe_haven_api.py` geçer.

### Task 5 — Önbellek betiği, gerçek grid testi, rapor
- [x] `scripts/build_roughness_cache.py` yaz (spec "Bileşenler 11"); koştur (`--baselines 100,200,400,800,1600`); meta'ları oku (CRS kanıtı, kayıt Spearman, ölçek düğümleri, PSR sayımı).
- [x] `test_roughness_real_grid.py` (skip: `metadata.json` + `roughness_grid.npy` + `psr_grid.npy`; 4-B için ufuk + çekirdek): katman sonlu ve ≥ 0, `f` ∈ [0, 1], Spearman(pürüzlülük, eğim) < 0,9, `psr_shadow_overlap` alanları [0, 1], `metadata["roughness"]["registration_check"]["spearman"] ≥ 0.9`; standart dört 2-B çift `/api/plan` 200 + `roughness.applied`; `/api/psr-validation` 200; v5 SHA kilidi (LPR-1, VIPER) ve pürüzlülüksüz temel gridle v4 SHA; `test_risk_sweep_real_grid.py` sabitleri v5 + v4 (katmansız) ikilisine çevir.
- [x] Koştur → geçer (özetleri oku, sabitlere yaz).
- [x] `scripts/roughness_psr_report.py` → `docs/research/roughness_psr_report.md` (`--json` önce, `--from-json`, `--skip-4d`, `--n-runs 1000`; bölümler spec "Bileşenler 11"). Koştur (4-B bölümü tek başına), sayıları oku.

### Task 6 — Belgeler ve kapanış
- [x] `.gitignore` üç satır; `docs/frontend/3b-veri-sozlesmesi.md` C4 eki ("## Değişmeyenler" öncesi, B2 ekinin ardına): katmanlar/manifest/f32, `PlanWeights.w_roughness`, hücre kartı alanları, `roughness` bloğu, `/api/psr-validation`, ölçülen örnek, iddia sınırı.
- [x] Araştırma belgesinde C4 başlığına ✅ + "Yapıldı" blok alıntısı; README Veri satırı (B2'nin altına).
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler" (tablolar, SHA'lar, sapmalar, test sayıları).
- [x] Tam paket `cd backend && python -m pytest` (1 338 passed, 2 skipped, 12:55) (arka planda, tek başına); ruff yeni dosyalarda temiz; tek commit (eş-yazar satırı yok); hafıza dosyası (C4 yapıldı + hash, sıradaki D2).
