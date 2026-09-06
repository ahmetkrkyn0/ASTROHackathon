# B3 — DEM hata yayılımı: NASA'nın DEM klonlarıyla Monte Carlo — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → B3](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** A4 (ufuk küpü iki ölçekli, `body_track_for_series`), A1 (safe haven — kullanılmıyor, bkz. kapsam dışı), B5 (`route_legs`, `RouteSky`, `simulate_runs`, `_distribution`) — tamamlandı.
**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`, `.gitignore`, `README.md`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

LunaPath'in her katmanı tek bir yükseklik modelinden türer: bir eğim, bir
ufuk, bir gölge. NASA GSFC Planetary Geodesy (Barker, Mazarico vd.) her
5 m/px güney kutbu DEM'i için **Z-belirsizlik haritası, eğim-belirsizlik
haritası ve 100 istatistiksel klon** yayınlıyor (PGDA ürün 78). Bu özellik
Site11'in gerçek klonlarını planlama penceresi için indirir, her klondan
eğim, geçilebilirlik ve yakın-alan ufkunu türetir ve

* hücre başına **P(geçilebilir)** (rover'a göre) ve eğim σ'sı,
* dilim başına **P(aydınlık, t)**,
* bir `/api/plan-4d` rotası için enerji / süre / gölge saatinde **%5–%95
  bandı** ve rotanın klonlar arasında geçilebilir kalma olasılığı

üretir. Hiçbir sayı uydurulmaz: hata alanı NASA'nın kendi ürünüdür, klonlar
gerçek dosyalardır, her ölçüm Site11 gridinde koşturulup okunur.

Tek cümlelik iddia: **NASA'nın yayınladığı hata klonları doğrudan LunaPath'in
kendi türetim zincirine (aynı eğim operatörü, aynı geçilebilirlik kuralı, aynı
ufuk yürüyücüsü, aynı enerji aritmetiği) N kez sokulur; çıktı olasılık
katmanları ve rota metriklerinde güven bandıdır.**

## Fizik / veri notu — klon dosyaları ne içeriyor (4 Eylül 2026 sondası)

`Site11_final_adj_5mpp_0001_err.tif` dosyası adına rağmen **tam bir yüzey
DEM'idir**, hata alanı değil: pencere içinde 528,8–954,6 m (yüzey DEM'i
528,8–954,5 m), yüzeyle korelasyon 1,0000. Hata gerçekleşmesi
`klon − surf` farkıdır:

| Nicelik (500×500 pencere) | Ölçülen |
|---|---|
| `klon₁ − surf` ortalama / std | −0,014 m / **0,448 m** |
| `toterr` (NASA Z belirsizliği) medyan / ortalama / p95 | 0,373 / 0,407 / 0,743 m |
| RMS(`klon₁ − surf`) / RMS(`toterr`) | 0,4485 / 0,4490 m |
| std(`(klon₁ − surf) / toterr`) | **1,002** |
| Uzamsal korelasyon, 5 / 10 / 25 / 50 / 100 m gecikme | 0,88 / 0,69 / 0,34 / 0,12 / 0,00 |
| std(eğim(klon₁) − eğim(surf)) | 1,87° |
| `slperr` (NASA eğim belirsizliği) medyan / ortalama | 1,73° / 1,82° |

Yani klon = `surf + toterr · ξ`, ξ birim varyanslı ve ~100 m'de
dekorele olan bir alan. NASA'nın ürün sayfasındaki "medyan RMS Z hatası
0,30–0,50 m, eğim hatası 1,5–2,5°" aralığı bu pencerede doğrulanıyor.
Dosyalar şeritli (1 satır/blok), sıkıştırmasız float32, 3200×3200,
`Accept-Ranges: bytes`; sunucu tek bağlantıda ~170 KB/s, dört paralel
bağlantıda ~545 KB/s veriyor (ölçüldü). Tam dosya 41 MB → tek bağlantıda
4 dk 17 s; bu yüzden klon başına yalnızca gereken satır bandı okunur.

**Hangi belirsizlik nereye yayılır:**

| Türev | Klonlanan girdi | Sabit tutulan | Gerekçe |
|---|---|---|---|
| Eğim, geçilebilirlik | Pencere (500×500) | Termal alan (`thermal`, `thermal_min`) | Geçilebilirlik kapısı eğim + soğuk-uç sıcaklığı; termal heat1d modelidir, eğime zayıf bağlı ve pahalı — B3'te eğim belirsizliği hedeflenir |
| Ufuk → gölge | Pencere + **1 km yakın-alan dolgusu** (900×900) | 1 km ötesi: yüzey DEM'inin 10 km bağlamı ve LOLA 40 m uzak alan | Bir sırtın δz hatası ufku δz/d kadar kaydırır: 0,45 m → 100 m'de 0,26°, 1 km'de 0,026°, 10 km'de 0,003°. Kutupta Güneş ~0,009°/h yükselir; 1 km ötesinin ihmal edilen katkısı ≲ 3 h aydınlanma kayması, 10 km ötesininki ≲ 0,3 h. 11 no'lu belge §2.3'ün "ufuk menzili" sınırlaması burada belirsizlik olarak **açıkça raporlanır** (`far_field_held_fixed`, `neglected_horizon_shift_deg_max`) |
| Dünya görünürlüğü, safe haven | — | Hepsi | Dünya yüksekliği ±7°; DTE uzak ufukla belirlenir, klonlanmıyor. Kapsam dışı |

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Rolü |
|---|---|---|
| Eğim operatörü (`np.gradient` → `arctan(hypot)`) | `data_loader.load_and_preprocess_dem` içi → **`slope_deg_from_elevation`** olarak dışarı alınır (davranış aynı) | Klon başına eğim, üretim eğimiyle aynı formülle |
| `compute_traversability_bool` | `traversability.py` | Klon başına maske; `P_traversable` gerçek planlayıcı kuralıyla tutarlı |
| `grids_for_rover` | `rover_grids.py` | Rover'ın `slope_max_deg`'i; belirsizlik katmanları rover başına önbelleklenir |
| `horizon_map`, `march_distances_cells` | `horizon.py` | Yakın/uzak adım kümeleri ve stride'lı ROI ile klon ufku |
| `far_field_horizon`, `read_pds_polar_dem`, `_matching_raw_dem` | `scripts/build_horizon_cache.py` | Uzak alan bir kez, yüzeyden; pencere doğrulaması |
| `illuminated_mask`, `body_track_for_series` | `illumination.py`, `illumination_series.py` | Klon küplerinden P(aydınlık, t) |
| `coarsen_grid`, `coarsen_traversable` | `cost_cube.py` | Kaba maske ve eğim (plan-4d ile aynı indirgeme) |
| `route_legs`, `RouteSky`, `simulate_runs`, `_nominal_samples`, `sample_perturbations`, `_distribution`, `wilson_interval` | `stress_test.py` | Rota bandı: klon başına legler + gökyüzü + nominal koşum; isteğe bağlı SHERPA birleşimi |
| `terrain_manifest`, `TERRAIN_LAYERS`, `LAYER_UNITS`, `encode_layer_f32` | `terrain.py` | Yeni katmanların manifest ve f32 yayını |
| `layer_validity`, `weakest_validity` | `metadata`, `traversability.py` | Provenance |

## Bileşenler

### 1. `scripts/build_dem_clone_cache.py` — kurulum betiği

```
python scripts/build_dem_clone_cache.py                 # Site11, 20 klon, 1 km dolgu, 4 iş parçacığı
python scripts/build_dem_clone_cache.py --n-clones 100
python scripts/build_dem_clone_cache.py --near-range-m 1000 --workers 4 --site Site11
python scripts/build_dem_clone_cache.py --synthetic     # yalnızca ağ yoksa; provenance "synthetic"
python scripts/build_dem_clone_cache.py --skip-horizons # yalnızca eğim/geçilebilirlik önbelleği
```

Adımlar:
1. `metadata.json` (pencere, `window_offset`), `elevation_grid.npy`; yüzey
   DEM'i `_matching_raw_dem` ile doğrulanır (pencere = işlenmiş grid).
2. `toterr` ve `slperr` pencereleri `/vsicurl/` ile okunur →
   `dem_elevation_sigma.npy`, `dem_slope_sigma_nasa.npy` (500×500 float32).
3. Klonlar `i = 1..N`: `/vsicurl/…/Clones/Site11_final_adj_5mpp_{i:04d}_err.tif`
   dolgulu pencere (`pad = near_range_m / res` = 200 px → 900×900) rasterio
   pencereli okuma, `ThreadPoolExecutor(workers)`; mevcut `dem_clones.npy`
   varsa eksik indeksler eklenir (artımlı: 20 → 100). Klon başına sağlama:
   `klon − surf` ortalaması (|·| < 0,1 m) ve RMS'inin `toterr` RMS'ine oranı
   (0,7–1,3) — pencerenin doğru klonu olduğunun kanıtı; meta'ya yazılır.
   Çıktı `dem_clones.npy` (N, 900, 900) float32 + `dem_clones_meta.json`
   (site, ürün URL'si, klon indeksleri ve URL'leri, pencere/dolgu/ofset,
   tarih, klon başına istatistik ve sha256, `provenance: "nasa_pgda_clones"`).
4. Ufuk (`--skip-horizons` verilmezse): plan-4d'nin blok merkezleri
   (`stride = coarsen = 4`, ofset 2) için
   * `steps = march_distances_cells(res, 10 km, 200)`; yakın adımlar
     `≤ pad`, uzak adımlar `> pad` (birleşimi tam küme);
   * **uzak küp bir kez**: yüzey DEM'inin 10 km bağlamında uzak adımlar +
     LOLA 40 m uzak alan (`far_field_horizon`, `horizon_map_meta.json`
     parametreleriyle) → `dem_surf_horizon_far.npy` (72, 125, 125);
   * yüzeyin yakın küpü aynı dolgulu pencere üzerinde → `max(yakın, uzak)`
     üretim küpünün stride hücreleriyle **birebir** olmalı (aynı adımlar,
     aynı bağlam); fark meta'ya yazılır (`surf_check_max_abs_deg`), 1e-3°
     üstü ise betik durur;
   * klon başına yakın küp → `max(yakın_i, uzak)` → `dem_clone_horizons.npy`
     (N, 72, 125, 125) + `dem_clone_horizons_meta.json` (stride, ofset, hücre
     satır/sütunları, `near_range_m`, uzak alan sağlayıcısı, süreler,
     `neglected_horizon_shift_deg_max = median(toterr) / near_range_m` rad→°).
5. `.gitignore`: `*.npy` zaten; iki meta dosyası mutlak yol taşımasa da
   diğer önbellek metaları gibi eklenir. README'ye bir satır.

`--synthetic`: ağ yoksa `synthetic_clones(surf, toterr, n, seed)` —
`surf + toterr · ξ`, ξ Gauss çekirdekli (σ = 2 hücre) beyaz gürültü, birim
varyansa normalize; `provenance: "synthetic"`, `toterr` da yoksa betik
durur (uydurma σ yok).

### 2. `app/uncertainty.py` — yeni modül (saf, FastAPI'siz)

```python
DEM_CLONES_FILENAME, DEM_CLONES_META_FILENAME, ELEVATION_SIGMA_FILENAME,
SLOPE_SIGMA_NASA_FILENAME, CLONE_HORIZONS_FILENAME, CLONE_HORIZONS_META_FILENAME,
SURF_HORIZON_FAR_FILENAME
PGDA_SITE_URL, clone_url(site, i), toterr_url(site), slperr_url(site)

@dataclass DemClones: elevation (N, R, C) float32 [dolgulu], pad: int, shape (H, W), meta: dict
    .window -> (N, H, W) görünüm
load_dem_clones(processed_dir) -> DemClones | None          # eksikse None, bozuksa ValueError
load_clone_horizons(processed_dir) -> (cubes (N, A, h, w) memmap, meta) | (None, None)
synthetic_clones(surface, sigma_z, n, seed, correlation_cells=2.0) -> (N, H, W)

near_far_steps(resolution_m, near_range_m, max_range_m, max_steps) -> (near, far)
ensemble_slopes(clones_window, resolution_m) -> (N, H, W)      # slope_deg_from_elevation
traversable_probability(slopes, thermal, elevation, rover, thermal_min) -> (P (H, W) float32, masks (N, H, W) bool)
slope_sigma(slopes) -> (H, W) float32                          # ddof = 0
uncertainty_layers_for_grids(grids, rover_id) -> (layers | None, info)   # önbellekli (processed_dir, mtime, rover, slope_max)
    # layers: p_traversable, slope_sigma, elevation_sigma, slope_sigma_nasa, clone_traversable (N, H, W)
    # info: model "nasa_pgda_clones" | "synthetic" | "unavailable" + reason, n_clones, pedigree
with_uncertainty_layers(grids, rover_id) -> grids  # kopya + layer_validity + metadata["dem_uncertainty"]

illuminated_probability(cubes, az_deg, elev_deg) -> (h, w) float32
illuminated_probability_series(cubes, track) -> (T, h, w) float32
uncertain_fraction(p, lo=0.05, hi=0.95) -> float

route_traversable_probability(masks, cells, coarsen) -> (per_state (S,), feasible (N,) bool)
route_band(states, clone_slopes_coarse, resolution_m, rover, slice_hours, skies, initial_soc_frac,
           sherpa=None) -> dict   # klon başına route_legs + nominal simulate_runs → dağılımlar
```

`route_band` klon başına: `route_legs(states, slope_i, res, rover, slice_hours)`
(geçilebilirlik doğrulaması yok — rota rota; klonun rotayı geçilmez
sayması ayrıca `route_feasible` olarak raporlanır; ≥ 90° kenar → klon
`unpriceable` sayılıp banttan düşer), `simulate_runs(legs_i, sky_i, rover,
_nominal_samples(soc0))` → `duration_h`, `drive_hours = Σ travel_h`,
`gross_drive_wh = Σ traction·travel`, `battery_used_wh = soc0·e_cap −
final`, `min_battery_pct`, `final_battery_pct`, `max_continuous_shadow_h`,
`reached`. Dağılımlar `stress_test._distribution` (p5/p50/p95/mean/std/
min/max/n). Yüzey DEM'iyle aynı hesap `nominal` olarak yanında.

SHERPA birleşimi (`sherpa = {n_runs, seed, perturbations}` verilirse): her
klon için `sample_perturbations(rng(seed + i), n_runs)` → `simulate_runs`;
koşumlar havuzlanır → `completion` Wilson CI, `duration_h`, `min_battery_pct`
dağılımı. Varsayılan **yalnızca DEM bandı** (SHERPA σ = 0): bant tümüyle
DEM'e atfedilebilir olsun diye; birleşik sonuç isteğe bağlı ve ayrı anahtarda.

### 3. API

**Katmanlar** (`GET /api/terrain`, `GET /api/layers/{ad}?format=f32&rover_id=`)
— klon önbelleği varsa manifestte, yoksa listelenmez; `/api/layers` 404 +
kurulum talimatı (earth_visibility kalıbı):

| Katman | Birim | Geçerlilik | Anlam |
|---|---|---|---|
| `p_traversable` | fraction | DERIVED | Klonların bu rover için hücreyi geçilebilir saydığı oran |
| `slope_sigma` | deg | DERIVED | Klon eğimlerinin std'si (bizim topluluk) |
| `elevation_sigma` | m | MODEL | NASA `toterr` (PGDA ürün 78) — ölçüm değil, NASA'nın hata modeli |
| `slope_sigma_nasa` | deg | MODEL | NASA `slperr` |

`metadata.dem_uncertainty`: kaynak, ürün URL'si, klon sayısı, pencere,
tarih, `provenance`, `far_field_held_fixed`, `near_range_m`,
`neglected_horizon_shift_deg_max` — NASA-STD-7009 "Results Uncertainty"
için girdi pedigree'si.

**`GET /api/uncertainty-series?start_utc&n_slices&slice_hours&format`** —
`p_illuminated` (T, 125, 125) klon ufuk küplerinin stride gridinde; JSON:
`n_clones`, `grid {rows, cols, resolution_m, stride, row_offset, col_offset}`,
`model` (`clone_horizon` | `unavailable` + reason), `sun` izi, dilim başına
`mean` ve `uncertain_fraction` (0,05 < P < 0,95), `binary_url`; f32 yolu
`/api/illumination-series` ile aynı başlıklar (`X-Series-*`).

**`POST /api/dem-uncertainty`** — rota bandı. İstek `/api/stress-test`
ile aynı çekirdek (`path_states`, `rover_id`, `coarsen`, `slice_hours`,
`start_utc`, `initial_soc_pct`) + `n_clones` (≤ mevcut; varsayılan hepsi),
`with_sherpa` (bool, varsayılan false), `n_runs` (1..5000, varsayılan 200),
`seed`, `perturbations`, `label`. Yanıt:

```json
{"label": null, "rover_id": "nasa_viper", "n_clones": 20, "clones_priced": 20,
 "route": {"n_states": 41, "move_steps": 40, "wait_steps": 0, "planned_duration_h": 7.36},
 "route_feasible": {"count": 17, "fraction": 0.85, "ci95": [..]},
 "reached": {"count": 20, "fraction": 1.0, "ci95": [..]},
 "p_traversable": {"min": 0.85, "mean": 0.98, "per_state": [1.0, ...]},
 "metrics": {"duration_h": {"p5":..,"p50":..,"p95":..,"mean":..,"std":..,"min":..,"max":..,"n":20},
             "drive_hours": {}, "gross_drive_wh": {}, "battery_used_wh": {},
             "min_battery_pct": {}, "final_battery_pct": {}, "max_continuous_shadow_h": {}},
 "nominal": {"duration_h":..,"drive_hours":..,"gross_drive_wh":..,"battery_used_wh":..,
             "min_battery_pct":..,"final_battery_pct":..,"max_continuous_shadow_h":..,"reached": true},
 "sky_model": {"model": "clone_horizon|static", "time_varying": true, "n_slices": 120, "reason": null,
               "far_field_held_fixed": true, "near_range_m": 1000.0},
 "sherpa": null,
 "provenance": {"model": "nasa_pgda_clones", "product_url": "...", "n_clones_available": 20},
 "timing_ms": {"sky": .., "runs": .., "total": ..}}
```

Klon gökyüzü yalnızca `coarsen == stride` (4) ve epoch + çekirdek varken;
aksi halde `static` (uzun-dönem `shadow_ratio` sütunları, plan-4d/stress-test
kalıbı) ve `reason` söyler. Dünya/haven sütunları bantta yok (kapsam dışı).

**`/api/plan` ve `/api/plan-4d` yanıtı** — yalnızca ekleme, yalnızca klon
önbelleği varken: `"uncertainty": {"n_clones", "p_traversable_min",
"p_traversable_mean", "route_feasible_fraction", "model", "band_url":
"/api/dem-uncertainty"}` (plan-4d'de kaba maskeler `coarsen_traversable` ile,
plan'da ince maskeler). Simülasyon yok; maliyet milisaniye. Klon yoksa alan
**yok** (mevcut testler ve istemciler etkilenmez).

### 4. `scripts/dem_uncertainty_report.py` → `docs/research/dem_uncertainty_report.md`

Gerçek gridde: (a) `toterr` dağılımı (medyan/p95) vs NASA'nın 0,30–0,50 m;
(b) `klon − surf` istatistikleri; (c) `slope_sigma` (bizim) vs `slperr`
(NASA) — medyan, korelasyon; (d) `P_traversable` özeti rover başına
(VIPER 20°, LPR-1 25°): kesin geçilebilir / kesin geçilmez / belirsiz hücre
oranı; klon sayısına yakınsama N = 5/10/15/20/… (mevcut N'e göre): belirsiz
oran ve `mean |P_N − P_max|`; (e) `P_illuminated` VIPER (30 May 2027) ve
LPR-1 (28 Eyl 2026) epoch'larında 48 h × 1 h: belirsiz hücre oranı p50/p95;
(f) rota bantları: B5'teki iki rota (aynı çiftler, tarihler, coarsen 4) —
DEM bandı ve SHERPA birleşimi; (g) süreler. Çekirdek/klon yoksa açıklayıp
0 ile çıkar.

## Veri akışı

```
PGDA Site11 klon i  ──/vsicurl/ dolgulu pencere──►  dem_clones.npy (N, 900, 900)
toterr, slperr      ──────────────────────────────►  dem_elevation_sigma.npy, dem_slope_sigma_nasa.npy
surf 10 km bağlam + LOLA 40 m ──uzak adımlar──────►  dem_surf_horizon_far.npy (72, 125, 125)
klon i dolgulu pencere ──yakın adımlar, stride 4──►  max(·, uzak) ──► dem_clone_horizons.npy (N, 72, 125, 125)

yükleme (lazy, önbellekli): load_dem_clones → ensemble_slopes → compute_traversability_bool ×N
   → p_traversable, slope_sigma, clone_traversable   →  /api/terrain, /api/layers, plan(+4d).uncertainty
load_clone_horizons + body_track_for_series(SUN) → illuminated_mask ×N → /api/uncertainty-series
route: coarsen_grid(slope_i,"max") → route_legs_i ; cube_i[:, rows, cols] → shadow_i → simulate_runs → bant
```

## Test stratejisi

- `test_uncertainty.py` (saf, sentetik, çekirdeksiz):
  - `slope_deg_from_elevation` eski satır-içi formülle birebir (`load_and_preprocess_dem` davranışı değişmez; `test_data_loader`-benzeri mevcut testler yeşil).
  - `synthetic_clones`: ortalama ≈ yüzey, std ≈ σ_z (hücre başına oran ~1), komşu korelasyonu > 0,5, seed tekrarı; σ_z yoksa `ValueError`.
  - `near_far_steps`: birleşim = tam küme, kesişim ≤ 1 adım, yakın ≤ pad.
  - `horizon_map(stride=…)` = tam çıktının `[..., o::s, o::s]` dilimi; `steps_cells` ile `max(yakın, uzak)` = tam küp (sentetik tümsekli arazi).
  - `traversable_probability`: 3 klonlu el yapımı yığın → P ∈ {0, 1/3, 2/3, 1}; NaN → 0; termal kapı sabit; rover eşiği (20° vs 25°) etkisi.
  - `slope_sigma` = `np.std(axis=0)`.
  - `illuminated_probability`: 3 klon, tek azimutta 10/20/30° ufuk, Güneş 15° → 1/3, 25° → 2/3; sentinel kuralı korunur; seri şekli (T, h, w); `uncertain_fraction` bilinen değer.
  - `route_traversable_probability`: hücre başına P ve `feasible` doğru; `coarsen` bloğu VE.
  - `route_band`: özdeş klonlar → p5 = p50 = p95 = nominal; eğimi artan klonlar → süre ve enerji artan sırada; ≥ 90° kenarlı klon `clones_priced`'dan düşer; `reached` sayımı; SHERPA birleşimi seed tekrarı ve `completion` Wilson.
  - `load_dem_clones`: eksik → None; şekil uyuşmazlığı → ValueError; meta okunur.
  - `uncertainty_layers_for_grids`: tmp `processed_dir`'e sentetik önbellek yazılır → katmanlar, `info.model`, önbellek isabeti; klon yokken `unavailable`.
- `test_uncertainty_api.py` (sentetik grid, tmp önbellek, statik gökyüzü):
  - `/api/terrain` manifestte 4 katman + `dem_uncertainty` pedigree; klon yokken yok.
  - `/api/layers/p_traversable?format=f32` başlıklar, `X-Layer-Validity: DERIVED`; `elevation_sigma` MODEL; klon yokken 404 talimatlı.
  - `/api/uncertainty-series` klon ufku yokken `unavailable` + reason; sentetik küplerle (stride 4) şekil, `uncertain_fraction`, f32 başlıkları.
  - `/api/dem-uncertainty` 200 şeması (static gökyüzü), 422 (bozuk `path_states`), `n_clones` sınırı, `with_sherpa`, `label`; klon yokken 404.
  - `/api/plan` ve `/api/plan-4d` `uncertainty` bloğu klonla var, klonsuz yok; mevcut alanlar aynen.
- `test_uncertainty_real_grid.py` (skip-guarded; klon önbelleği + ufuk + çekirdek):
  - `klon − surf` |ortalama| < 0,1 m, RMS/toterr RMS ∈ (0,8; 1,2); `slope_sigma` medyanı `slperr` medyanının 0,5–2 katı.
  - `P_traversable` ∈ [0, 1]; belirsiz hücre oranı > 0; `p = 1` hücrelerin hepsi temel maskede geçilebilir.
  - Klon ufuk meta `surf_check_max_abs_deg` ≤ 1e-3; yüzey küpünün stride hücreleri üretim küpüyle birebir.
  - VIPER rotası `/api/dem-uncertainty` < 30 s, `clone_horizon` gökyüzü, bant `n = N`, nominal süre ≈ plan varış saati (±1 dilim).

## Hata davranışı

- Klon önbelleği yoksa: katmanlar listelenmez, `/api/layers/<yeni>` 404 +
  betik adı, `/api/uncertainty-series` ve `/api/dem-uncertainty` 404 +
  talimat, plan yanıtlarında `uncertainty` alanı yok. 500 yok.
- Klon var, ufuk klonu yok: `p_*` katmanları ve plan blokları çalışır;
  seri `unavailable`, bant `static` gökyüzü + `reason`.
- Şekil uyuşmazlığı (grid değişmiş): `ValueError` → yükleyici `unavailable`
  + reason (earth_visibility kalıbı gibi yeniden derleme talimatı).
- `inf`/`NaN` JSON'a sızmaz; aynı `seed` aynı sonuç; klon indeksleri meta'da.

## Kapsam dışı (bilinçli)

- Termal alanın klonlanması (heat1d pahalı; termal kapı sabit).
- Dünya görünürlüğü / safe haven / Earthset belirsizliği (uzak ufuk; klonlanmıyor).
- 1 km ötesi yakın-alan ve LOLA 40 m uzak alan belirsizliği (sabit; ihmal edilen kayma sınırı raporlanır).
- Planlayıcının kendisinin `P_traversable` ile planlaması (B1/B2 risk-farkında planlama konusu); burada yalnızca değerlendirme.
- B5'ten kalan planlayıcı dilim-yuvarlama enerji notu (dokunulmadı).

## Uygulama sırasında bulunanlar ve ölçümler (4 Eylül 2026)

**Klon dosyaları tam DEM'dir.** `_err.tif` adına rağmen her klon tam bir
yüzey DEM'i; hata gerçekleşmesi `klon − surf`. Doğrulama pencerede: 100
klonun tümü kontrolü geçti — `klon − surf` ortalaması −0,024…−0,002 m,
klon başına RMS / RMS(`toterr`) 0,975–1,027 (Bölüm "Fizik / veri notu"ndaki
ilk sondayla tutarlı). `toterr` medyanı 0,373 m, NASA'nın ürün sayfasındaki
0,30–0,50 m aralığının içinde; `slperr` medyanı 1,73° (1,5–2,5°).

**İndirme.** Sunucu tek bağlantıda ~170 KB/s (tam dosya 41 MB → 4 dk 17 s);
dört paralel bağlantı 3,2× ölçekleniyor (545 KB/s). Klon başına yalnızca
dolgulu satır bandı (900 satır × 12,8 KB ≈ 11,5 MB) `/vsicurl/` ile okundu:
ilk 20 klon 452 s, geri kalan 80 klon artımlı ikinci koşuda 1.889 s. Tam dosya indirme/saklama yapılmadı; önbellek (100, 900, 900)
float32 = 324 MB.

**`np.rint` eşitlik kırılması — iki-geçişli ufuk ilk denemede üretim küpüyle
0,27° farklıydı.** Yakın geçiş dolgulu 900×900 klon dizisinde koşunca
1,125 M (azimut, hücre) çiftinin 1.116'sı (%0,1) üretim küpünden 0,27°'ye
kadar saptı; hepsi cos/sin = ±0,5 azimutlarında (120°, 150°, 240°, 300°,
330°). Neden: ışın örneği `rint(satır + d·adım)` ile yuvarlanıyor; `.5`
eşitliklerinde küçük dizide 203,50000000000003 → 204, büyük bağlam
dizisinde aynı değer 2003,5 → 2004 (bankacı yuvarlaması) — kayan noktanın
küçük büyüklükte taşıdığı fazlalık büyük büyüklükte kayboluyor. Çözüm:
yakın geçiş, dolgulu klonu üretim bağlamıyla **aynı mutlak indekslerde** bir
NaN tuvale gömerek koşuluyor (`_canvas`); yüzeyin `max(yakın, uzak)` küpü
üretim küpüyle **tam 0,0°** farkla eşleşiyor (`surf_check_max_abs_deg =
0.0`, meta'da). `horizon_map` değiştirilmedi — üretim küpünün kendisi de
aynı yuvarlamayı taşıyor; değiştirmek her ufuk tabanlı katmanı yeniden
üretmeyi gerektirirdi (ayrı madde).

**Klon ufku yüzey ufkundan ortalama 0,70° sapıyor** (klon 1, 72 azimut ×
125² hücre: ortalama |Δ| 0,70°, p95 3,1°, maks 24°; ufku 2°'nin altındaki
hücrelerde ortalama |Δ| 0,27°). 5 m/px'te ufku çoğu zaman komşu hücre
belirler ve iki komşunun hata farkı σ√(2(1−0,88)) ≈ 0,22 m → 5 m'de 2,5°.
Bu, tasarımdaki 0,5° tahmininden büyük ve gerçek bir bulgu: yakın ufuk
belirsizliği uzak ufuk belirsizliğinden (≤ 0,02°) iki mertebe büyük; Güneş
için belirleyici düşük ufuklu hücrelerde 0,27°, kutupta ~30 saatlik
aydınlanma başlangıcı kaymasına denk. Gerçek-grid testi bu ölçüme göre
sınırlandı (< 5°).

**Klon eğimleri yüzey eğiminden sistematik olarak yüksek.** Sıfır
ortalamalı yükseklik gürültüsü gradyanın büyüklüğünü şişirir (E|∇(z+ε)| >
|∇z|); yüzey DEM'i en iyi tahmin, klonlar gerçek arazi kadar pürüzlü. Bu
yüzden rota bantlarında nominal (yüzey) sürüş enerjisi bandın **altında**
kalıyor: VIPER rotasında nominal 2.127 Wh, bant p5 ≥ 2.257 Wh. Sunumda
cümle: "en iyi tahmin DEM'inde planlanan enerji, olası arazilerin hepsinden
iyimser". Lewis 2021'in (JAMT) arkeolojik en-düşük-maliyet-yol bulgusuyla
aynı yönde.

**Süre bandı B5 politikası yüzünden dar.** `duration_h` "önde iken planlanan
kalkışa kadar bekle" kuralını izler; eğim hatası dilim boşluğunu aşmadıkça
varış saati değişmez (VIPER 7,27 h her klonda). DEM'e duyarlı metrikler
`drive_hours` ve `gross_drive_wh`; ikisi de raporlanıyor, sözleşme belgesi
bunu söylüyor.

**Blok-VE kuralı rotayı hiçbir klonda tam geçilebilir bırakmıyor.** VIPER
rotası 41 kaba hücre × 16 ince hücre; kaba geçilebilirlik plan-4d'nin kendi
kuralıyla (tüm ince hücreler ≤ 20°) hesaplanınca `route_feasible = 0/N`, en
düşük hücre P'si 0,2 — rota eğim sınırına yaslanıyor. LPR-1 (25°) için
100/100. Bu, planlayıcının kaba maskeyi "kesin" saymasının ne kadar kırılgan
olduğunu sayıyla gösteriyor (B1/B2'ye girdi).

**Sentetik klon etiketi.** Sentetik önbellekten türeyen `p_traversable` ve
`slope_sigma` `SYNTHETIC` etiketlenir (yükseklik-vekili gölge kuralı);
`elevation_sigma`/`slope_sigma_nasa` NASA ürünü olarak `MODEL` (ölçüm değil,
NASA'nın hata modeli).

**Termal alan sabit, Dünya klonlanmadı** (tasarımdaki gibi); provenance
bloğu üçünü de açıkça söylüyor (`thermal_field_held_fixed`,
`far_field_held_fixed`, `earth_visibility_cloned: false`).

**Ölçümler (Site11, 100 klon, 4 Eylül 2026; `scripts/dem_uncertainty_report.py` →
[dem_uncertainty_report.md](../../research/dem_uncertainty_report.md)):**

| Ölçüm | Değer |
|---|---|
| Klon önbelleği | 100 klon, (100, 900, 900) float32 = 324 MB; 100 ufuk küpü (100, 72, 125, 125) = 429 MiB, klon başına 2,52 s; yüzey kontrolü 0,0° |
| `klon − surf` | ortalama −0,011 m, RMS 0,449 m = RMS(`toterr`) 0,449 m; `toterr` medyanı 0,373 m (NASA 0,30–0,50), `slperr` medyanı 1,73° (NASA 1,5–2,5) |
| Eğim σ (bizim vs NASA) | medyan 1,516° vs 1,726° (oran 0,878, hücre korelasyonu 0,418); p95 1,99° vs 2,71° |
| Eğim yanlılığı (topluluk ort. − yüzey) | medyan +0,158°, ortalama +0,179°, p95 +1,85° (yüzey eğimi medyanı 10,5°) |
| `P_traversable` VIPER (20°) | temel geçilebilir %79,4; kesin geçilebilir %68,6, kesin geçilmez %16,9, **belirsiz %8,2**; temelde geçilebilir ama P < 0,5: %0,9 |
| `P_traversable` LPR-1 (25°) | temel %84,0; kesin %80,7 / %14,6, belirsiz %2,8; P < 0,5: %0,4 |
| Yakınsama (VIPER, tam topluluğa göre ort. \|ΔP\| / maks) | N=5: 0,014 / 0,85; N=20: 0,0068 / 0,35; N=50: 0,0034 / 0,18; N=75: 0,0019 / 0,11 |
| `P_illuminated` 30 May 2027, 48 h | belirsiz hücre oranı p50 **%10,8**, maks %13,3; ortalama aydınlık %35 |
| `P_illuminated` 28 Eyl 2026, 48 h | p50 %0, maks %2,5 (site karanlık) |
| Klon ufku − yüzey ufku | ortalama \|Δ\| 0,70°, p95 3,1°; ufku < 2° hücrelerde 0,27°; ihmal edilen uzak alan ≤ 0,021° |
| VIPER haven→haven bandı (100 klon) | sürüş enerjisi p5/p50/p95 **2.258 / 2.293 / 2.334 Wh**, nominal 2.127 Wh; bataryadan çekilen 3.203 / 3.238 / 3.278 Wh; min batarya p5 %18,0; rota geçilebilir **1/100** (Wilson %0,2–5,5), en düşük hücre P 0,27; nominal koşumda varış 100/100 |
| VIPER + SHERPA (200 koşum × 100 klon) | tamamlanma **%17,8** (CI 17,3–18,4), B5'te yüzey DEM'iyle %29,6 |
| LPR-1 bandı (100 klon) | sürüş enerjisi 538 / 546 / 556 Wh, nominal 506; rota geçilebilir 99/100; SHERPA ile tamamlanma %100 |
| Süreler | `/api/uncertainty-series` 48 dilim 0,2–0,4 s; `/api/dem-uncertainty` 1,1–3,8 s (100 klon); plan-4d 6,6–10,5 s |

**Sapmalar (tasarımdan):**
- Yakın geçiş dolgulu klon dizisinde değil, üretim bağlamıyla aynı
  indekslerdeki NaN tuvalde koşuluyor (yukarıdaki yuvarlama bulgusu);
  `horizon_map`'e `stride` ve `steps_cells` eklendi, `march_distances_cells`
  değişmedi.
- `uncertainty_layers_for_grids` katman sözlüğüne `clone_slopes` (N, H, W)
  da koyuyor (rota bandı kaba eğimleri buradan alıyor; yayınlanmıyor).
- `route_band` imzası: `skies` tek `RouteSky` ya da klon başına liste;
  `nominal_slope`/`nominal_sky` ayrı; `sherpa` sözlüğü `{n_runs, seed,
  perturbations}`; yanıtta `per_clone` listeleri ve `failures` eklendi.
- `GET /api/uncertainty-series` `n_clones` parametresi aldı (ilk n klon;
  100 küp 450 MB olduğundan klon başına döngüyle hesaplanıyor).
- `/api/dem-uncertainty` gökyüzü sütunları kaba hücrenin **blok-merkez** ince
  hücresinden (klon küplerinin stride gridi; dilim başına 0/1); plan-4d'nin
  küpü 16 ince hücrenin ortalamasıdır. Nominal gökyüzü üretim küpünün aynı
  merkez hücrelerinden — iki taraf aynı tanımla karşılaştırılıyor;
  `sky_model.columns` bunu söylüyor.
- `route_feasible` Wilson aralığıyla; `reached` (nominal koşumda varış)
  ayrı raporlanıyor.
- `/api/plan` bloğu ince hücrelerde (`coarsen` 1), `/api/plan-4d` bloğu kaba
  (blok-VE) hücrelerde; `band_url` ikisinde de var.
- 100 klonun tamamı indirildi (tasarımdaki "N = 20 ile başla" uygulandı,
  sonra artımlı olarak 100'e çıkarıldı); klon ufuk küpleri de 100 klon için
  üretildi (klon başına 2,8 s).
- `/api/compare` ve `/api/plan`'a simülasyonlu band eklenmedi (yalnızca
  ucuz geçilebilirlik bloğu); band `/api/dem-uncertainty`'de.
