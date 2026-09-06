# B3 — DEM hata yayılımı (NASA klonlarıyla Monte Carlo) — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** NASA PGDA'nın Site11 DEM klonlarını planlama penceresi için
indirip her klondan eğim, geçilebilirlik ve yakın-alan ufkunu türeterek
`P_traversable`, `slope_sigma`, `P_illuminated[t]` katmanlarını ve bir
`/api/plan-4d` rotası için enerji/süre/gölge bandını (%5–%95) yayınlamak;
provenance NASA-STD-7009 "Results Uncertainty" için girdi pedigree'sini taşır.

**Architecture:** `scripts/build_dem_clone_cache.py` klon pencerelerini
(1 km dolgulu), `toterr`/`slperr`'i ve stride-4 klon ufuk küplerini
`lunapath/data/processed/` altına yazar. `app/uncertainty.py` (saf) bunları
tembel ve önbellekli yükler; eğim → geçilebilirlik zinciri üretimle aynı
fonksiyonlardır; rota bandı B5'in `route_legs` + `simulate_runs`'ını klon
başına nominal koşumla kullanır. `main.py` yalnızca ekleme yapar: dört katman
manifestte, `GET /api/uncertainty-series`, `POST /api/dem-uncertainty`,
plan yanıtlarında `uncertainty` bloğu (klon varken).

**Spec:** [2026-09-04-b3-dem-uncertainty-design.md](../specs/2026-09-04-b3-dem-uncertainty-design.md)

**Tech Stack:** Python 3.11, FastAPI, NumPy, SciPy (`ndimage.gaussian_filter`), rasterio (`/vsicurl/`), spiceypy, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Mevcut `/api/plan`, `/api/plan-4d`, `/api/terrain`, `/api/layers` alanları
  aynen; yalnızca ekleme. Klon önbelleği yokken hiçbir yanıt değişmez.
- `load_and_preprocess_dem`'in eğim çıktısı bit-bit aynı kalır
  (`slope_deg_from_elevation` dışarı alınır, formül değişmez).
- TDD: her görevde önce başarısız test, sonra kod.
- Çekirdeksiz / klonsuz temiz klonda tüm yeni testler koşar; gerçek grid
  testleri `skip`-korumalı.
- Sayı uydurma yok: `--synthetic` yalnızca `toterr` varsa ve `provenance:
  "synthetic"` ile.
- `inf`/`NaN` JSON'a sızmaz; aynı `seed` aynı sonuç.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/data_loader.py` | `slope_deg_from_elevation(elevation, resolution_m)` (refactor, davranış aynı) |
| `backend/app/horizon.py` | `horizon_map(..., stride=1, steps_cells=None)` — stride'lı ROI ve açık adım kümesi |
| `backend/app/uncertainty.py` | Yeni: dosya adları/URL'ler, `DemClones`, yükleyiciler, `synthetic_clones`, `near_far_steps`, `ensemble_slopes`, `traversable_probability`, `slope_sigma`, `uncertainty_layers_for_grids`, `with_uncertainty_layers`, `illuminated_probability(_series)`, `uncertain_fraction`, `route_traversable_probability`, `route_band` |
| `backend/app/terrain.py` | `LAYER_UNITS`, `LAYER_DESCRIPTIONS`, `TERRAIN_LAYERS` — dört yeni katman |
| `backend/app/main.py` | `/api/terrain`, `/api/layers` (yeni katmanlar), `GET /api/uncertainty-series`, `POST /api/dem-uncertainty`, `/api/plan` ve `/api/plan-4d` `uncertainty` bloğu |
| `scripts/build_dem_clone_cache.py` | Kurulum betiği (indirme, sağlama, ufuk klonları, meta) |
| `scripts/dem_uncertainty_report.py` | Rapor betiği → `docs/research/dem_uncertainty_report.md` |
| `backend/test_uncertainty.py`, `backend/test_uncertainty_api.py`, `backend/test_uncertainty_real_grid.py` | Testler |
| `.gitignore`, `README.md`, `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec | Belgeler |

---

## Görevler

### Task 0 — Eğim operatörü ve stride'lı ufuk (altyapı refactor'ları)
- [x] `test_uncertainty.py`: `slope_deg_from_elevation` rastgele yüzeyde `np.degrees(np.arctan(hypot(np.gradient(e, res))))` ile birebir; `load_and_preprocess_dem` çıktısı (mevcut testler) yeşil.
- [x] Test: `horizon_map(elev, res, roi, stride=s)` = `horizon_map(elev, res, roi)[:, ::s, ::s]`; `steps_cells` verilince `march_distances_cells` yok sayılır; `near_far_steps` birleşimi tam küme, yakın ≤ pad; `max(horizon(near), horizon(far))` = tam küp (sentetik tümsekler).
- [x] `data_loader.slope_deg_from_elevation`; `horizon_map(stride, steps_cells)`; `uncertainty.near_far_steps`.

### Task 1 — Klon önbelleği veri modeli ve sentetik klonlar
- [x] Test: `synthetic_clones(surface, sigma_z, n, seed)` → şekil (n, H, W); ortalama(klon − yüzey) ≈ 0; std oranı ≈ 1 (±0,15); lag-1 korelasyon > 0,5; seed tekrarı; `sigma_z` None/negatif → `ValueError`.
- [x] Test: `load_dem_clones(tmp)` yok → None; meta + `.npy` yazılınca `DemClones.window` şekli (N, H, W) ve dolgu doğru; şekil uyuşmazlığı → `ValueError`. `load_clone_horizons` aynı kalıp.
- [x] Test: `clone_url("Site11", 7)` = `…/Clones/Site11_final_adj_5mpp_0007_err.tif`; `toterr_url`, `slperr_url`.
- [x] `uncertainty.py`: sabitler, `DemClones`, `load_dem_clones`, `load_clone_horizons`, `write_dem_clones` (betik ve testler için), `synthetic_clones`, URL yardımcıları.

### Task 2 — P_traversable, slope_sigma ve katman önbelleği
- [x] Test: `ensemble_slopes` = klon başına `slope_deg_from_elevation`; `traversable_probability` 3 klonlu el yapımı yığın → P ∈ {0, 1/3, 2/3, 1}, maskeler `compute_traversability_bool` ile birebir, NaN → 0, `thermal_min` kapısı, rover eşiği; `slope_sigma` = `np.std(axis=0)` float32.
- [x] Test: `uncertainty_layers_for_grids(grids, rover_id)` tmp `processed_dir`'de sentetik önbellekle → dört katman + `clone_traversable`, `info.model = "synthetic"`, ikinci çağrı önbellek isabeti (aynı nesne); klon yokken `(None, {"model": "unavailable", "reason": …})`; `with_uncertainty_layers` kopyada `layer_validity` (DERIVED/MODEL) ve `metadata["dem_uncertainty"]`; klon yokken girdi aynen döner.
- [x] `uncertainty.py`: `ensemble_slopes`, `traversable_probability`, `slope_sigma`, `_cache`, `clear_uncertainty_cache`, `uncertainty_layers_for_grids`, `with_uncertainty_layers`.

### Task 3 — P_illuminated ve rota olasılıkları
- [x] Test: `illuminated_probability` 3 klon (ufuk 10/20/30° tek azimut) Güneş 15° → 1/3, 25° → 2/3, 35° → 1; sentinel hücrede `elev > 0` kuralı; `illuminated_probability_series(cubes, track)` şekli (T, h, w); `uncertain_fraction` bilinen değer.
- [x] Test: `route_traversable_probability(masks, cells, coarsen)` → hücre başına P ve `feasible (N,)`; coarsen bloğu VE.
- [x] `uncertainty.py`: üç fonksiyon.

### Task 4 — Rota bandı
- [x] Test: özdeş klonlar → her metrikte p5 = p50 = p95 = nominal, `clones_priced = N`; eğimi klon indeksiyle artan yığın → `duration_h` ve `gross_drive_wh` klon sırasıyla artan, p95 > p5; ≥ 90° kenarlı klon `clones_priced`'dan düşer; statik gökyüzünde `reached` sayımı; `sherpa={n_runs, seed}` → `completion` Wilson, seed tekrarı; JSON'da `inf` yok.
- [x] `uncertainty.py`: `route_band(states, clone_slopes_coarse, resolution_m, rover, slice_hours, skies, initial_soc_frac, sherpa=None, nominal_slope=None, nominal_sky=None)`.

### Task 5 — Katmanlar ve manifest
- [x] `test_uncertainty_api.py`: `/api/terrain` manifestte `p_traversable`, `slope_sigma`, `elevation_sigma`, `slope_sigma_nasa` (units/validity/binary_url) + `dem_uncertainty` pedigree; klonsuz manifest değişmez; `/api/layers/p_traversable?format=f32` başlıklar ve `X-Layer-Validity: DERIVED`, `elevation_sigma` MODEL, json yolu; klonsuz 404 talimatlı; `rover_id` etkisi (LPR-1 25° vs VIPER 20° → P farklı).
- [x] `terrain.py` sözlükleri; `main.py` `get_layer`/`terrain`'de `with_uncertainty_layers`.

### Task 6 — `GET /api/uncertainty-series`
- [x] Test: ufuk klonu yokken 200 + `model: unavailable` + reason (seri yok); sentetik küplerle (stride 4, 4×4 hücre) `p_illuminated` şekli, `uncertain_fraction` listesi, `grid.stride`, f32 başlıkları `X-Series-*`; epoch yokken `unavailable`.
- [x] `main.py`: uç; Güneş izi `body_track_for_series`; SPICE hatası → `unavailable`.

### Task 7 — `POST /api/dem-uncertainty` ve plan blokları
- [x] Test: 200 şeması (statik gökyüzü, sentetik klonlar), `metrics.*.n = n_clones`, `nominal`, `route_feasible`, `p_traversable.per_state` uzunluğu; 422 (bozuk `path_states`, `n_clones` > mevcut → 422 gerekçeli); `with_sherpa` → `sherpa.completion`; `label` yankısı; klonsuz 404.
- [x] Test: `/api/plan` ve `/api/plan-4d` klonla `uncertainty` bloğu (`n_clones`, `p_traversable_min/mean`, `route_feasible_fraction`, `model`, `band_url`); klonsuz alan yok; diğer alanlar aynen (mevcut `test_plan_endpoint*`, `test_plan_4d_endpoint` yeşil).
- [x] `main.py`: `DemUncertaintyRequest`, uç, `_route_uncertainty_block` yardımcısı, plan/plan-4d ekleri.

### Task 8 — Kurulum betiği ve gerçek önbellek
- [x] `scripts/build_dem_clone_cache.py`: argümanlar, yüzey doğrulaması, `toterr`/`slperr`, paralel klon indirme (artımlı), sağlama, meta; ufuk: uzak küp bir kez (`far_field_horizon` + yüzey 10 km bağlamı, uzak adımlar), yüzey yakın küpü kontrolü (`surf_check_max_abs_deg`), klon küpleri; `--synthetic`, `--skip-horizons`, `--force`.
- [x] Site11'de koştur: `--n-clones 20` (arka planda), ardından mümkünse daha fazla; süreleri ve sağlamaları meta'dan oku. (20 → 100 klon artımlı; 100/100 sağlama OK, yüzey kontrolü 0,0°.)
- [x] `.gitignore` (iki meta), README satırı.

### Task 9 — Gerçek grid testleri ve rapor
- [x] `test_uncertainty_real_grid.py` (skip-guarded): klon − surf istatistikleri; `slope_sigma` vs `slperr`; `P_traversable` özellikleri; yüzey stride küpü ≡ üretim küpü; VIPER rotası `/api/dem-uncertainty` < 30 s, `clone_horizon`.
- [x] `scripts/dem_uncertainty_report.py` → `docs/research/dem_uncertainty_report.md` (toterr/slperr, klon istatistikleri, P_traversable özeti ve N yakınsaması, P_illuminated belirsiz oranı, iki rota bandı, süreler).

### Task 10 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` B3 eki ("## Değişmeyenler" öncesi).
- [x] Araştırma belgesinde B3 başlığına ✅ + "Yapıldı" blok alıntısı (ölçümlerle, sapmalarla).
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler".
- [x] Tam test paketi (953 passed, 1 skipped, 7:17); tek commit (eş-yazar satırı yok); hafıza dosyası güncellemesi.
