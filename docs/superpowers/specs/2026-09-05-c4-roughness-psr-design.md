# C4 — Ölçülmüş pürüzlülük katmanı (LOLA LDRM) ve PGDA PSR maskesi — Tasarım Belgesi

**Tarih:** 5 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → C4](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** A4'ün PGDA rasteri ↔ 5 m grid ko-registrasyon şablonu (`scripts/earth_visibility_validation.py`, `rasterio.warp.reproject`), B3'ün `/vsicurl/` pencere indirme şablonu (`scripts/build_dem_clone_cache.py`), maliyet yolu (`cost_engine.compute_cost_grid` skaler referans ↔ `cost_vec`; `costmap.default_cost_map`; `cost_cube.build_cost_cube`; `rover_grids.grids_for_rover`), `data_loader`'ın opsiyonel katman kuralı ("yok, UNKNOWN değil"), `terrain.TERRAIN_LAYERS` manifesti, B2'nin `COST_MODEL_ID` / SHA-256 kilidi kalıbı.
**Kapsam:** `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

LunaPath'in bugün tek `MEASURED` katmanı `elevation`'dır; eğim, bakı, gölge, termal ve
maliyet ondan türetilir veya modellenir. Yüzeyin **pürüzlülüğü** hiçbir yerde yoktur;
11 no'lu belge "80 m/px'te 30 cm'lik kaya görünmez" der, 12 no'lu belge pürüzlülüğün
bunun **istatistiksel vekili** olduğunu söyler. NASA GSFC (Barker vd., PSJ 4:183, 2023;
PGDA ürün 90, DOI 10.60903/gsfcpgda-lola-spole) güney kutbu için LOLA spot artıklarından
**ölçülmüş** çok-tabanlı pürüzlülük haritaları (LDRM) ve 20 m/px **PSR haritası** (LPSR)
yayınlıyor. C4 ikisini de planlama penceresine ko-registre eder:

1. **`roughness`** — LDRM 100 m tabanlı pürüzlülük (metre), `MEASURED`; **beşinci maliyet
   kriteri `f_roughness`** olarak ağırlıklı toplama girer (`w_roughness`).
2. **`psr`** — LPSR ikili maskesi, `MEASURED`; planlamaya **girmez**, katman + hücre kartı +
   bizim `shadow_ratio`'dan türeyen "karanlık" hücrelerle **doğrulama** olarak yayımlanır.

Tek cümlelik iddia (sunum): **"İki katmanımız artık NASA'nın ölçülmüş ürünleridir: LOLA LDRM
hektometre ölçekli pürüzlülüğü beşinci kriter olarak gride girdi, PGDA PSR maskesi bizim
gölge modelimizle Site11'de Jaccard 0,83 (20 m blokta 0,91) örtüşüyor; pürüzlülük kriteri
Ay gecesi rotasını değiştirdi, gündüz rotasını neredeyse değiştirmedi."** (Sayılar ölçüldü;
aşağıda ve raporda.)

## İddia sınırı (her yanıtta)

- LDRM pürüzlülüğü LOLA spot artıklarından **ölçülmüştür**, ama ürün **50 m/px** posting ve
  **100 m taban** iledir; bizim grid 5 m/px. Bir 5 m hücreye yazılan değer, o hücreyi kapsayan
  50 m pikselin **100 m tabanlı blok istatistiğidir**, hücrenin kendi pürüzlülüğü değildir.
  "30 cm kaya görünür oldu" **denmez**; "hektometre ölçekli pürüzlülük ölçülmüş katman olarak
  girdi" denir. Katman etiketi `MEASURED`.
- `f_roughness`'ın [0, 1]'e eşlemesi bir **istatistiksel ölçektir** (`MODEL`): hücrenin
  pürüzlülüğünün 80–90°S bölgesindeki 50 m pikseller arasındaki **persentil sırası**. Rover
  kataloğunda kaynaklı bir "tolere edilebilir pürüzlülük" (yer açıklığı, tekerlek çapı) alanı
  yoktur ve uydurulmadı; ölçek rover'dan bağımsızdır.
- `w_roughness = 0,15` bir **varsayımdır** (hiçbir profil için yayımlanmış pürüzlülük ağırlığı
  yok); raporda 0–0,3 taranır (sonda 3'te 0,5'e kadar), hassasiyet gösterilir.
- Diviner kaya bolluğu **kullanılamaz** (kapsam ±70–80°; Powell vd. 2023) — "kaya bolluğu
  kullanıyoruz" denmez.
- PSR maskesi ölçülmüş üründür; bizim `shadow_ratio ≥ 0,99` hücrelerimizle örtüşmesi bir
  **doğrulama sayısıdır**, iyi çıkmasa da yazılır. LDRM'nin yayımlanmış piksel σ'sı yok
  (LDSM'nin var, LDRM'nin yok): pürüzlülüğün B2 kuyruğu yoktur, her α'da nominal değeri okunur.

## Kaynak / yöntem notu

| Ürün | Dosya (pgda.gsfc.nasa.gov/data/LOLA_20mpp/) | Tanım (ürün sayfası, 5 Eylül 2026) |
|---|---|---|
| Pürüzlülük | `LDRM_80S_50MPP_ADJ_ROUGH_100M.TIF` (616 MB; 12 160² px, 50 m/px, COG 512² deflate, float32, NaN) | *"LOLA Digital Roughness Map (LDRM, in meters). This is the spread of height residuals of individual LOLA spots around a plane fit to the LDEM within a circular window whose diameter is equal to a baseline of \*M meters."* Tabanlar 100/200/400/800/1600 m; ayrıca `_SLP_*M` (fit düzleminin eğimi, derece), `_RMSD_*M` (merkez–halka RMS sapması), `_H` (Hurst üssü), 1000 m/px'te `_CLASS` (k-means), `_AVGROUGH`, `_SPSLP`, `_ROUGH_RGB`. **Dizinde LDRM 80S için yalnızca 50 m/px ve 1000 m/px var** (araştırma belgesindeki "50–1000 m/px" bir aralık değil, iki üründür). |
| PSR | `LPSR_80S_20MPP_ADJ.TIF` (148 MB; 30 400² px, 20 m/px, COG, float32 0/1, NaN) | *"All PSRs (N=506349): PSR map"*; CSV/SHP eşleri (509 349 özellik; > 1 km² olanlar `_1km2`). |

- CRS: iki ürün de `Moon (2015) - Sphere / Ocentric / South Polar` — polar stereografik, küre
  1 737 400 m, `lat_0 −90`, `lon_0 0`, sahte doğu/kuzey 0; bizim `metadata.json` CRS'i aynı
  projeksiyon parametreleriyle ("unnamed" adlarıyla). Betik parametreleri karşılaştırır, ad
  farkını yok sayar ve eşitliği meta'ya yazar.
- Ürünlerin transformu `(50, 0, −304 000 | 0, −50, 304 000)` ve `(20, 0, −304 000 | 0, −20,
  304 000)`; GMT `node_offset=1`, `AREA_OR_POINT=Area` (piksel alan; köşe transformu).
- Bizim pencere: `metadata.json` origin (−32 500, 11 000), 500×500 @ 5 m → x ∈ [−32 500, −30 000],
  y ∈ [8 500, 11 000]. **Doğrulandı:** `Site11_final_adj_5mpp_surf.tif` transformu
  `(5, 0, −45 000 | 0, −5, 23 000)`, `t·(col 2500, row 2400) = (−32 500, 11 000)` — origin
  pencerenin **sol-üst köşesidir** (`process_lunar_data.py` `win_transform.c/.f`). A4'ün
  `destination_transform` yardımcısı origin'i hücre **merkezi** sayıp yarım hücre kaydırıyordu;
  2,5 m'lik bu fark A4'ün 60 m ürünü ve C4'ün 50/20 m ürünleri için piksel-altıdır (sonuçları
  değiştirmez) ama burada köşe kuralı kullanılır ve not düşülür.
- Pencere ürün pikselinde: 50 m'de satır 5860–5910 / sütun 5430–5480 (50×50 px), 20 m'de
  14 650–14 775 / 13 575–13 700 (125×125 px); ikisi de **tek bir 512² COG tile'ına** düşer →
  `/vsicurl/` ile pencere okuma ~1 MB/ürün, 2–11 s (ölçüldü). Kenar payı 2 px (50 m) / 5 px (20 m).
- Barker vd. 2023 PSJ 4:183 (10.3847/PSJ/acf3e1); PSJ 2025 kuzey/güney pürüzlülük çalışması
  (10.3847/PSJ/adbc9d: > 10° eğimlerde 50–200 m tabanda pürüzlülük artıyor); Kreslavsky vd. 2013;
  Rosenburg vd. 2011. PSR: Mazarico vd. 2011 (Icarus 211) yöntem ailesi.

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Bu tasarımda rolü |
|---|---|---|
| `rasterio.warp.reproject`, `from_origin` | `scripts/earth_visibility_validation.py` | Ko-registrasyon aynı çağrı; `Resampling.nearest` |
| `/vsicurl/` pencere okuma, `_VSICURL_ENV`, paralel işçiler, sağlama-yoksa-yazma | `scripts/build_dem_clone_cache.py` | İndirme şablonu; sağlama = LDRM eğimi ↔ bizim blok eğimi |
| Opsiyonel katman yükleme (`_load_earth_visibility`), şekil reddi, "yok ≠ UNKNOWN" | `data_loader.py`, `test_layer_validity.py` | `_load_roughness`, `_load_psr` aynı kalıp |
| `CostMap`/`CostLayer`/`PlanContext`, `explain`, `_cell_context` | `costmap.py` | `RoughnessLayer` eklenir; explain otomatik |
| `compute_cost_grid` ↔ `cost_vec` parite testleri | `cost_engine.py`, `cost_vec.py`, `test_review_fixes.py` | `f_roughness` ↔ `f_roughness_grid` aynı kalıp |
| `build_cost_cube` blok kabalaştırma (`how="max"` eğim ve σ_θ için) | `cost_cube.py` | Pürüzlülük de `max` |
| `grids_for_rover` yeniden hesaplama/etiketleme | `rover_grids.py` | Pürüzlülük + ölçek gride girer, `cost_criteria` damgası |
| `terrain_manifest`, `encode_layer_f32`, `binary_layer_headers` | `terrain.py` | İki yeni katman; validity manifestte |
| `weakest_validity` | `traversability.py` | `cost` etiketi girdilerin en zayıfıdır: pürüzlülük girince **yükselmez** (`DERIVED` kalır) — araştırma belgesindeki "cost MODEL'e yükselir" cümlesi termal düzeltilince geçerli, C4'te değil |
| `slip_model` / `risk` rota blokları | `main._slip_block_2d/_4d`, `risk.risk_block` | `roughness` bloğu aynı yerlerde |
| `--json` önce / `--from-json` rapor kalıbı | `scripts/risk_sweep_report.py` | `scripts/roughness_psr_report.py` |

---

## Sondalar (5 Eylül 2026; atılabilir betikler, sayılar buraya)

**Sonda 1 — ürün, pencere, ko-registrasyon.** Dizin/boyutlar yukarıda. Pencere okumaları:
LDRM 100 m 54×54 px, NaN 0, min 0,125 / medyan 0,827 / maks 4,871 m; 200 m medyan 1,72;
400 m 3,41; 800 m 8,09; 1600 m 24,0 m; Hurst medyan 0,93; LDRM `SLP_100M` medyan 10,1°;
PSR 135×135 px, değerler {0, 1}, NaN 0. Nearest ile 5 m'e: 2 500 benzersiz blok (50×50 → 10×10
hücre), NaN 0. **Kayıt kontrolü:** LDRM `SLP_100M` (fit düzleminin eğimi) ↔ bizim 5 m eğimin
50 m blok ortalaması Spearman **0,989** — ko-registrasyon doğru. Bölgesel örnek: 36 tile (her
eksende her 4. tile), 9 437 184 sonlu piksel, 59 s / 4 bağlantı; 80–90°S dağılımı p5 0,267 /
p50 0,572 / p95 1,359 / p99 2,177 / maks 55,2 m (log10 ort. −0,235, std 0,217).

**Sonda 2 — H-4 kontrolü ve normalizasyon.** Spearman(pürüzlülük, eğim) 5 m hücrelerde
**0,213** (bilinear 0,261); 50 m blokta blok-ort. eğimle 0,227, blok-maks ile 0,321;
LPR-1 `f_slope` ile 0,183. Kriter eğimin yeniden ifadesi **değil** (H-4'te enerji–eğim
1,000 idi). PSJ 2025 bulgusu Site11'de zayıf ama yönü doğru: eğim kutuları 0–5 / 5–10 / 10–15 /
15–20 / > 20° → medyan pürüzlülük 0,72 / 0,76 / 0,81 / 0,91 / 1,08 m. Adaylar (Site11 hücreleri):
(a) **bölgesel ECDF sırası:** p5 0,23 / p50 0,78 / p95 0,98 / p99 0,994 — tüm [0, 1]'e yayılıyor,
doygunluk yok; (b) log-doğrusal bölgesel p5–p95: hücrelerin %14,9'u 1,0'da doyuyor;
(c) grid-göreli persentil: pencereler arası karşılaştırılamaz; (d) doğrusal `r / 63,2 m`
(ürün maks): Site11 p95 **0,028** → atıl. **Karar (a).**

**Sonda 2 — PSR ↔ gölge.** PSR hücresi 14 016 (%5,6; 876 adet 20 m piksel). `shadow_ratio ≥ 0,99`
16 363 hücre; Jaccard **0,830**, PSR'ın yakalanan payı 0,983, karanlık hücrelerin PSR'da olan
payı 0,842 (eşik 0,90 → 0,685; 0,95 → 0,765; 1,0 → 0,833). 20 m blok düzeyinde (4×4 blok-ort.
gölge ≥ 0,99) Jaccard **0,912**. PSR içinde ort. `shadow_ratio` 0,998 (p1 0,953; medyan 1,0),
dışında 0,629. PSR içinde `thermal_min` medyanı ve p95'i **−183,15 °C** (90 K PSR tabanı),
dışında medyan −98,6 °C; `thermal_min ≤ −180` 16 406 hücrenin 13 761'i PSR'da. LPR-1
temel maskesinde PSR içinde geçilebilir hücre **83** (14 016'nın %0,6'sı): termal kapı PSR'ı
zaten kapatıyor.

**Sonda 3 — aday ağırlıkla 2-B rota (doğrudan `astar`, maliyet = nominal + w·f):**

| Çift | w = 0,05 | 0,10 | 0,15 | 0,20 | 0,30 | 0,50 |
|---|---|---|---|---|---|---|
| LPR-1 (358,494)→(206,426), 156 nokta, rota ort. pürüzlülük 1,04 m | örtüşme 1,00 | 1,00 | **0,97** | 0,97 | 0,97 | 0,75 (ort. 1,02) |
| LPR-1 Ay gecesi (186,34)→(494,450), 420 nokta, 0,75 m | **0,20** (ort. 0,69) | 0,05 (0,67) | **0,05 (0,66)** | 0,04 | 0,08 | 0,08 (0,62; 422 nokta) |
| VIPER (358,494)→(206,426), 156 nokta, 1,04 m | 1,00 | 1,00 | **1,00** | 0,87 | 0,87 | 0,87 |
| VIPER kısa (358,494)→(346,462), 33 nokta, 0,68 m | 1,00 | 1,00 | **1,00** | 0,83 | 0,83 | 0,83 |

Kriter atıl değil, etkisi rotaya bağlı: Ay gecesi çifti 0,05'te bile yer değiştiriyor (mesafe
aynı 2 737 m, rota ort. pürüzlülük −%8), gündüz çifti 0,15'e kadar hiç, sonra %3.

---

## Tasarım kararları

1. **Ürün:** `LDRM_80S_50MPP_ADJ_ROUGH_100M` (en kısa taban, en ince posting) **tek** grid
   katmanı. Diğer tabanlar (200–1600 m), Hurst ve `SLP_100M` yalnızca **rapor** için
   önbelleğe (`roughness_baselines.npz`, 50 m ham pencereler) alınır; manifeste girmez (YAGNI).
   `RMSD`, `CLASS`, `RGB` indirilmez.
2. **Ko-registrasyon:** `Resampling.nearest` — her 5 m hücre onu kapsayan 50 m pikselin
   değerini **aynen** alır (blok istatistiği; bilinear ölçülmemiş blok-içi gradyan üretirdi;
   PSR ikili kalmalı). Hedef transform `from_origin(origin_x, origin_y, 5, 5)` (köşe kuralı).
   CRS eşitliği projeksiyon parametreleriyle (`proj`, `lat_0`, `lon_0`, `R`, `x_0`, `y_0`)
   kontrol edilir; sağlamazsa betik **yazmaz**. Kayıt sağlaması: `SLP_100M` ↔ blok-ort. eğim
   Spearman ≥ 0,9 şartı (ölçüldü 0,989); sağlamazsa yazmaz.
3. **Normalizasyon (MODEL):** `f_roughness(r) = F̂_80S(r)` — 80–90°S bölgesinin 50 m
   piksellerinden alınan tabakalı örneğin (her eksende her 4. 512² tile; 36 tile; ~9,4 M piksel)
   ampirik CDF'i, **201 kantil düğümü** (p = 0, 0,005, …, 1) olarak `roughness_meta.json["scale"]`
   içinde; `f = np.interp(r, düğümler, p)`, düğümler kesin artan (eşitler birleştirilir),
   aralık dışı 0 / 1'e kenetlenir. NaN pürüzlülük → **0,5** (bölgesel medyan; "bilinmiyor =
   tipik"; Site11'de NaN yok, kural sentetik testte). Ölçek rover'dan bağımsız, pencereden
   bağımsız, veriden gelir; kodda sabit yoktur. Bir pürüzlülük gridi **ölçeksiz** maliyete
   giremez (`ValueError`).
4. **Ağırlık:** `w_roughness` beşinci anahtar: `cost_engine._WEIGHT_KEYS`, `default_weights`,
   `constants.ROVERS[*]["w_roughness"] = 0,15` (dört rover; varsayım, yorumla),
   `MODELLED_FIELDS`, `rover_default_weights`, `W_ROUGHNESS`, `main.PlanWeights.w_roughness`
   (`[0, 2]`), `scenarios.MISSION_PROFILES[*]["weights"]["w_roughness"] = C.W_ROUGHNESS`,
   `/api/layers` ve `/api/terrain` sorgu parametresi. **Diğer dört ağırlık yeniden
   ölçeklenmez** (toplam 1,15): (a) pürüzlülük terimi salt **eklemeli** kalır, önce/sonra farkı
   yalnız yeni kritere atfedilir; (b) `PlanWeights` hiçbir zaman birim toplam istemedi;
   (c) 11 no'lu belge bu ağırlıkların AHP olmadığını (matris/CR yok) tespit etti — korunacak
   bir tutarlılık oranı yok. `wait_cost` `w_roughness` okumaz (beklerken pürüzlülük birikmez).
5. **`COST_MODEL_ID` → `weighted_cell_cost_shadow_aware_energy_slip_roughness_v5`**
   (bump notu kalıbıyla): katman varken varsayılan ağırlıkla grid değişir. SHA kilidi
   (`test_risk_sweep_real_grid`) v5 özetleriyle güncellenir **ve** ikinci bir kilit eklenir:
   pürüzlülük katmanı temel gridlerden çıkarılınca özet **eski v4 değerlerine** (`0e74607d…`,
   `8788936c…`) döner — dört terim bit-eşit korunmuştur.
6. **Katman yokken:** `roughness_grid.npy` yoksa katman yok, `RoughnessLayer` eklenmez,
   `metadata["cost_criteria"] = ["slope", "energy", "shadow", "thermal"]`, `cost_weights`
   `w_roughness`'ı taşır ama yanıtın `roughness.applied` alanı `false` ve `reason` dolu.
   Temiz klon ve 16×16 fixture'lar böyle koşar; mevcut testler değişmeden geçer (anahtar
   kümesi sayan üç test hariç, aşağıda).
7. **PSR planlamaya girmez** — katman, hücre kartında `in_psr`, `GET /api/psr-validation`.
   Gerekçe: VIPER'ın bilimsel hedefi PSR **içidir** ("PSR = geçilmez" kapısı yanlış); termal
   kapı Site11 PSR hücrelerinin %99,4'ünü zaten kapatıyor (83 / 14 016 geçilebilir); gölge ve
   termal kriterler karanlığı zaten fiyatlıyor (çifte sayım).
8. **4-B küp:** pürüzlülük dilimden bağımsız; `build_cost_cube(roughness, roughness_scale)`
   ince gridi `how="max"` ile kabalaştırır (eğim ve σ_θ ile aynı tutucu kural: bloğun en
   pürüzlü 50 m pikseli). İkisi birlikte verilir ya da hiç.
9. **B2 kancası:** `risk.sigma_sources`'a, yalnız katman yüklüyken, `roughness: {"source":
   "none", "reason": "LDRM has no published per-pixel sigma …"}`; `criteria` bloğu (slope/
   energy) **değişmez** — pürüzlülük kuyruğu yoktur, her α'da nominal okunur.

## Bileşenler

### 1. `app/roughness.py` — yeni modül

```
ROUGHNESS_CACHE_FILENAME = "roughness_grid.npy"      ROUGHNESS_META_FILENAME = "roughness_meta.json"
PSR_CACHE_FILENAME       = "psr_grid.npy"            PSR_META_FILENAME       = "psr_meta.json"
ROUGHNESS_BASELINES_FILENAME = "roughness_baselines.npz"   # rapor için ham 50 m pencereler
LDRM_PRODUCT, LDRM_BASELINE_M = 100, LDRM_RESOLUTION_M = 50, LPSR_PRODUCT, LPSR_RESOLUTION_M = 20
PGDA_PRODUCT_URL = "https://pgda.gsfc.nasa.gov/products/90", DATA_DOI, ldrm_url(baseline, kind), lpsr_url()
ROUGHNESS_LAYER_VALIDITY = "MEASURED"; ROUGHNESS_SCALE_VALIDITY = "MODEL"
ROUGHNESS_CLAIM, PSR_CLAIM, ROUGHNESS_REFERENCES, NAN_ROUGHNESS_F = 0.5

@dataclass(frozen=True) RoughnessScale:
    knots: tuple[float, ...]; probs: tuple[float, ...]; kind = "regional_ecdf"; source: str; n_samples: int
    from_meta(meta) -> RoughnessScale  (ValueError: eksik/kısa/artmayan düğüm)
    to_meta() -> dict
    f(r: float) -> float            # np.interp; NaN -> 0.5; skaler referans
    f_grid(r: ndarray) -> ndarray   # aynı np.interp çağrısı; bit-eşit
same_projection(crs_a, crs_b) -> bool          # parametre karşılaştırması (rasterio CRS.to_dict)
psr_shadow_overlap(psr, shadow_ratio, thermal_min=None, threshold=0.99) -> dict
    n_psr, psr_fraction, n_dark, threshold, n_intersection, n_union, jaccard,
    psr_recall (PSR ∩ dark / PSR), dark_precision (PSR ∩ dark / dark), false_positive_fraction (1 − precision),
    mean_shadow_inside_psr, mean_shadow_outside_psr, thermal_min_median_inside_psr / _outside_psr (varsa)
route_roughness_summary(values_m, f_values, in_psr) -> dict   # mean/max m, mean f, cells_in_psr, n
roughness_block(applied, weight, route=None, reason=None) -> dict   # yanıt bloğu
```

### 2. `app/cost_engine.py`, `app/cost_vec.py`

- `_WEIGHT_KEYS += "w_roughness"`, `default_weights` beş anahtar, `COST_MODEL_ID` v5.
- `f_roughness(roughness_m, scale) -> float` (skaler referans, `scale.f`); `cost_vec.f_roughness_grid(grid, scale)` (`scale.f_grid`).
- `compute_cost_grid(..., roughness_grid=None, roughness_scale=None)`: ikisi birlikte
  (yalnız grid → `ValueError`; şekil uyumsuz → `ValueError`); varsa `+ w_roughness ·
  f_roughness_grid`. NaN pürüzlülük hücreyi **geçilmez yapmaz** (0,5 okunur); `invalid`
  maskesi değişmez.
- `total_edge_cost` (eski skaler kenar maliyeti; planlayıcı kullanmıyor) değişmez — belgede not.

### 3. `app/costmap.py`

- `PlanContext.roughness: ndarray | None = None`, `roughness_scale: RoughnessScale | None = None`;
  `_cell_context` dilimler.
- `RoughnessLayer(weight, validity="MEASURED", scale)`: `contribution = f_roughness_grid(ctx.roughness, scale)`;
  `ctx.roughness is None` → `ValueError` (katman eklenmişse bağlam onu taşımalı).
- `default_cost_map(rover, weights, layer_validity, risk_alpha, roughness_scale=None)`: `scale`
  verilmişse beşinci katman `validity.get("roughness", "MEASURED")` ile eklenir; yoksa dört katman.

### 4. `app/cost_cube.py` — `build_cost_cube(..., roughness=None, roughness_scale=None)`; `how="max"`.

### 5. `app/rover_grids.py` — `grids_for_rover`: `base_grids.get("roughness")` ve
`RoughnessScale.from_meta(metadata["roughness"])` maliyete girer; `metadata["cost_criteria"]`
damgalanır; `needs_cost_recompute` koşulları aynen (v5 kimliği eski gridleri zaten yeniler).

### 6. `app/pathfinder.py` — `_resolve_cost_grid` yeniden hesaplarken pürüzlülük + ölçeği geçirir.

### 7. `app/data_loader.py` — `_load_roughness(d, shape)` → (grid float64 m, meta dict);
`_load_psr(d, shape)` → (grid float64 0/1, meta). Şekil uymazsa `ValueError` (katman adı +
betik adı); pürüzlülük meta'sı yok ya da `scale` eksikse `ValueError` (ölçeksiz katman
maliyete giremez). `validity["roughness"] = validity["psr"] = "MEASURED"`;
`metadata["roughness"]`, `metadata["psr"]` meta; yükleme anındaki `compute_cost_grid`
pürüzlülüğü alır; `metadata["cost_criteria"]`.

### 8. `app/terrain.py` — `TERRAIN_LAYERS += ("roughness", "psr")`; `LAYER_UNITS`
`"m"` / `"boolean"`; açıklamalar (taban ve iddia sınırı bir cümlede).

### 9. `app/constants.py`, `app/scenarios.py` — yukarıdaki karar 4.

### 10. `app/main.py` — yalnızca ekleme

| Uç | Değişiklik |
|---|---|
| `PlanWeights` | `w_roughness: float = W_ROUGHNESS`, doğrulayıcıya eklenir (422 dışında) |
| `GET /api/layers/{roughness,psr}` | `valid_layers`'a eklenir; yüklü değilse 404 + `scripts/build_roughness_cache.py`; `w_roughness` sorgu parametresi |
| `GET /api/terrain` | `w_roughness` parametresi; katmanlar varsa manifestte (otomatik) |
| `GET /api/cell-telemetry` | `PlanContext`/`default_cost_map` pürüzlülük + ölçekle → `cost_breakdown.roughness`; yeni alanlar `roughness_m`, `f_roughness`, `in_psr` (katman yoksa `null`) |
| `POST /api/plan`, `POST /api/plan-4d` | `roughness` bloğu: `applied`, `validity: "MEASURED"`, `scale_validity: "MODEL"`, `product`, `baseline_m`, `resolution_m`, `weight`, `route` (`mean_roughness_m`, `max_roughness_m`, `mean_f_roughness`, `cells_in_psr`, `n_cells`; 4-B'de blok-maks pürüzlülük), `claim`; katman yoksa `applied: false` + `reason` |
| `GET /api/psr-validation?threshold=0.99` | `psr_shadow_overlap` çıktısı + `validity` (psr MEASURED, shadow_ratio'nun etiketi), ürün/kaynak; `psr` katmanı yoksa 404 + betik adı |
| `/api/risk*` | `_risk_sources`: katman varken `sigma_sources.roughness` (karar 9) |
| `/api/profiles`, `/api/rovers` | Ağırlık sözlükleri `w_roughness` taşır (otomatik) |

### 11. Betikler

- `scripts/build_roughness_cache.py` — `--processed-dir`, `--baselines 100,200,400,800,1600`
  (ilki grid katmanı; diğerleri + `H` + `SLP_100M` `roughness_baselines.npz`'e), `--n-workers 4`,
  `--pad-px 2`, `--regional-every 4`, `--skip-regional` (mevcut meta'daki ölçeği korur),
  `--force`. Adımlar: (1) `metadata.json` penceresi ve CRS; (2) ürün başlıkları `/vsicurl/`
  ile, CRS parametre eşitliği (değilse **çık**); (3) pencere okumaları paralel; (4) nearest
  reprojeksiyon 5 m'e; (5) kayıt sağlaması `SLP_100M` ↔ blok-ort. `slope_grid.npy` Spearman
  ≥ 0,9 (değilse **yazma**); (6) bölgesel örnek → 201 kantil; (7) yaz: `roughness_grid.npy`
  (float32 m), `roughness_meta.json` (ürün, URL, taban, çözünürlük, `fetched_utc`, pencere
  piksel/transform, CRS kanıtı, resampling, sağlama sayıları, `scale`, iddia), `psr_grid.npy`
  (float32 0/1), `psr_meta.json`, `roughness_baselines.npz`. Dosya varsa atlar.
- `scripts/roughness_psr_report.py` → `docs/research/roughness_psr_report.md` (`--json` önce,
  `--from-json`, `--skip-4d`, `--n-runs 1000`): (1) ürün/pencere/ko-registrasyon (CRS, transform,
  çözünürlük oranı, sağlama Spearman); (2) pürüzlülük dağılımı (100–1600 m, Hurst), Site11 ↔
  bölge kantilleri, Spearman(pürüzlülük, eğim) 5 m ve 50 m, eğim kutuları; `f_roughness`
  dağılımı; ağırlık taraması ile grid Spearman(maliyet_v5, maliyet_v4); (3) PSR ↔ `shadow_ratio`
  (eşik taraması, 20 m blok, termal taban); (4) standart çiftlerde önce/sonra: 2-B dört çift
  `/api/plan` `w_roughness ∈ {0, 0,05, 0,10, 0,15, 0,20, 0,30}` (örtüşme, mesafe, süre, Wh,
  min SOC, rota ort./maks pürüzlülük, PSR hücresi); 4-B üç rota `/api/plan-4d` (0 ve 0,15)
  + `/api/stress-test` 1 000 koşum; (5) `f_roughness`'ın explain payı (rota hücrelerinde
  ortalama katkı / toplam); (6) okuma, sunum cümlesi, iddia sınırı. "Önce" = `w_roughness=0`
  (aynı v5 kodu; katman katkısı sıfır → grid v4 ile bit-eşit, kilitle kanıtlı).

### 12. `.gitignore` — `roughness_meta.json`, `psr_meta.json`, `roughness_baselines.npz`
(yerel yol/zaman damgası taşırlar; `*.npy` zaten kapsanıyor).

## Veri akışı

```
PGDA COG (50 m LDRM, 20 m LPSR) ──/vsicurl/ tek tile──► build_roughness_cache.py
   ├─ CRS parametre eşitliği, SLP_100M ↔ blok eğim Spearman ≥ 0,9 (sağlama; değilse yazma)
   ├─ nearest → 5 m: roughness_grid.npy (m) + roughness_meta.json (scale: bölgesel ECDF 201 düğüm)
   └─ nearest → 5 m: psr_grid.npy (0/1) + psr_meta.json ; roughness_baselines.npz (rapor)
data_loader ──► grids["roughness"], grids["psr"], metadata["roughness"/"psr"], validity MEASURED
   └─► compute_cost_grid(+ roughness, scale) ──► cost (v5), metadata["cost_criteria"]
rover_grids.grids_for_rover ──► aynı (rover/ağırlık/α ile)
costmap.default_cost_map(scale) ──► RoughnessLayer ──► explain["roughness"] ──► /api/cell-telemetry
cost_cube.build_cost_cube(roughness blok-maks, scale) ──► /api/plan-4d
/api/terrain, /api/layers/{roughness,psr}?format=f32 ; /api/psr-validation ; /api/plan* roughness bloğu
```

## Hata davranışı

- Önbellek yok → katman yok; hiçbir uç düşmez; `/api/layers/{roughness,psr}` ve
  `/api/psr-validation` 404 + betik adı; plan yanıtı `roughness.applied: false`.
- Şekil uyumsuz önbellek, `scale`'siz pürüzlülük meta'sı → yüklemede `ValueError` (katman adı +
  betik adı); `/api/load-preprocessed` bunu 500 yerine mevcut kalıbıyla iletir.
- `compute_cost_grid` gride ölçeksiz pürüzlülük → `ValueError`; `RoughnessLayer` bağlamda
  pürüzlülük yok → `ValueError`.
- Betik: CRS uyumsuz / sağlama düşük → yazmaz, nedenini basar, 1 ile çıkar; ağ hatası 3 deneme.

## Test stratejisi

- **Birim (`test_roughness.py`, çekirdeksiz/önbelleksiz):** `RoughnessScale` meta gidiş-dönüş,
  monotonluk, [0, 1], NaN → 0,5, eşit düğüm birleştirme, bozuk meta reddi; `f_roughness` ↔
  `f_roughness_grid` 20 000 rastgele değerde `np.array_equal` (aynı `np.interp`); aralık dışı
  kenetleme; `same_projection` (ürün WKT'si ↔ bizim WKT; ad farkı yok sayılır; farklı `lat_0`
  reddi); `psr_shadow_overlap` elle 4×4 (Jaccard, recall, precision, ortalamalar);
  `route_roughness_summary` elle; iddia sabitleri ("MEASURED", "MODEL", "not a measurement of
  the cell").
- **Maliyet yolu (`test_roughness_cost.py`):** `compute_cost_grid` pürüzlülüksüz ↔ dört terimli
  yerel referans `np.array_equal`; pürüzlülüklü ↔ dört terim + `w·f` `assert_allclose(1e-12)`;
  `w_roughness=0` ↔ pürüzlülüksüz bit-eşit; ölçeksiz grid ve şekil hatası `ValueError`; NaN
  pürüzlülük hücreyi geçilmez yapmaz; ağırlık duyarlılığı (0,15 vs 0,30 farklı grid);
  `resolve_weights` beş anahtar; `default_cost_map(scale)` beş katman ve `explain["roughness"]`
  = `w·f`; `_cell_context` dilimleme; `build_cost_cube` blok-maks ↔ dilim başına referans;
  yalnız biri verilirse `ValueError`; `grids_for_rover` pürüzlülük + `cost_criteria` +
  `cost_weights["w_roughness"]`; profiller/katalog beş anahtar.
- **Yükleyici (`test_layer_validity.py` eki):** ikisi varken yükleme (MEASURED, meta), yokken
  yok (validity/metadata'da anahtar yok), şekil reddi, ölçeksiz meta reddi.
- **API (`test_roughness_api.py`, 16×16):** katmansız: `/api/plan` 200 + `roughness.applied
  false`, `/api/cell-telemetry` `roughness_m null`, `/api/layers/roughness` 404 betik adı,
  `/api/psr-validation` 404; katmanlı (fixture'a enjekte): manifest iki katman MEASURED, f32
  gidiş-dönüş, hücre kartı `cost_breakdown.roughness` + `in_psr`, plan bloğu `route`,
  `PlanWeights.w_roughness=3` → 422, `w_roughness=0` → katkı 0, `/api/psr-validation` alanları,
  `/api/profiles` ve `/api/rovers` `w_roughness`.
- **Gerçek grid (`test_roughness_real_grid.py`, skip: önbellek/grid/çekirdek):** katman
  sonlu, m ≥ 0; `f` ∈ [0, 1]; Spearman(pürüzlülük, eğim) < 0,9 (eğimin yeniden ifadesi değil;
  iddia bu, sayı raporda); `psr_shadow_overlap` alanları [0, 1]; standart çiftler `/api/plan`
  200 + blok `applied`; `/api/psr-validation` 200; **SHA kilitleri:** v5 özetleri (LPR-1,
  VIPER) ve pürüzlülüksüz temel gridlerle **v4 özetleri**.
- **Uyarlanan mevcut testler:** `test_rover_grids` ve `test_scenarios` anahtar kümeleri (+
  `w_roughness`), `test_review3_fixes::test_h4_cost_model_id_was_bumped` (`_v5`),
  `test_risk_sweep_real_grid` özet sabitleri.

## Kapsam dışı (bilinçli)

- PSR maskesinin geçilebilirliğe/maliyete girmesi (karar 7); PSR shapefile/CSV (TIF yeter).
- `RMSD`, `CLASS`, `AVGROUGH`, `SPSLP`, `RGB` ürünleri; Hurst ve diğer tabanlar yalnız raporda.
- Rover'a bağlı pürüzlülük toleransı (kaynaklı alan yok); pürüzlülük σ'sı / B2 kuyruğu (ürün yok).
- Frontend görselleştirmesi (arkadaşın dalı); yalnızca sözleşme belgesi.
- `total_edge_cost` skaler kenar maliyetine pürüzlülük (planlayıcı kullanmıyor).

## Uygulama sırasında bulunanlar ve ölçümler (5 Eylül 2026)

**Önbellek (`scripts/build_roughness_cache.py`, 5 Eylül 02:31 UTC).** Dokuz pencere
(5 taban + Hurst + `SLP_100M` + PSR) 4 bağlantıyla 10 s; bölgesel örnek 36 tile / 9 437 184
piksel 29 s. CRS parametre eşitliği sağlandı (`Moon (2015) - Sphere / Ocentric / South Polar`
≡ `unnamed`); kayıt sağlaması Spearman **0,989** (2 500 blok; medyanlar 10,4° / 10,1°). Gride
2 500 benzersiz blok, NaN 0; PSR 14 016 hücre (876 ürün pikseli), NaN 0. Ölçek 201 düğüm
(0,038 … 55,2 m); bölge p5 0,267 / p50 0,572 / p95 1,359 / p99 2,177 m.

**SHA-256 kilitleri (`test_roughness_real_grid.py`, `test_risk_sweep_real_grid.py`).**
Katmanla (v5, `w_roughness` 0,15): LPR-1 `55e1bb3cd3b9…`, VIPER `593f8e46730a…`; katman
temel gridlerden çıkarılınca **ve** `w_roughness = 0` ile: v4 `0e74607d668e…` / `8788936cee3f…`
birebir — dört terim dokunulmadı, beşinci terim salt eklemeli.

**Bulunan hata (sapma).** İlk sondada LPR-1 için katman çıkarılmış temel grid v4 yerine v5
özetini verdi: `grids_for_rover` rover/ağırlık/maske/model/α eşleşince depolanan (yükleyicinin
pürüzlülüklü) maliyeti aynen kullanıyordu. `cost_criteria` damgası yalnız bir metadata alanı
olmaktan çıkıp **yeniden-hesap koşuluna** girdi (`rover_grids`, `pathfinder._resolve_cost_grid`);
iki test (`test_a_stored_cost_grid_is_not_reused_when_the_criteria_it_summed_differ`,
`test_pathfinder_does_not_reuse_a_cost_grid_whose_criteria_differ`) önce kırmızı, sonra yeşil.
`test_pathfinder`'ın damgalı fixture'ı `cost_criteria` da taşıyor.

**Ölçüm (Site11; `scripts/roughness_psr_report.py` →
[roughness_psr_report.md](../../research/roughness_psr_report.md)):**

| Ölçüm | Değer |
|---|---|
| Pürüzlülük 100 m (5 m grid) | p5 0,40 / p50 0,83 / p95 1,78 / maks 4,87 m; 200 m 1,69, 400 m 3,30, 800 m 7,80, 1 600 m 23,6 m (medyan); Hurst 0,52 / 0,92 / 1,29 |
| `f_roughness` Site11 | p5 0,23 / p25 0,54 / p50 0,78 / p75 0,91 / p95 0,98; ≥ 0,99 %2,3, ≤ 0,01 %0,2 |
| H-4: Spearman(pürüzlülük, eğim) | 5 m **0,213**; 50 m blok-ort. 0,227, blok-maks 0,321; `f_slope` ile 0,18 (LPR-1) / 0,14 (VIPER) |
| Eğim kutuları → medyan pürüzlülük | 0–5° 0,72 · 5–10° 0,76 · 10–15° 0,81 · 15–20° 0,91 · >20° 1,08 m |
| Maliyet gridi, w = 0,15 ↔ w = 0 | Spearman 0,959 (LPR-1) / 0,945 (VIPER); ort. +%24,5 / +%22,6; kriterin hücre payı ort. %19 / %18 (p95 %31 / %28) |
| PSR ↔ `shadow_ratio ≥ 0,99` | Jaccard **0,830**, recall 0,983, precision 0,842 (eşik 0,90 → 0,685; 0,95 → 0,765; 1,0 → 0,833); 20 m blokta **0,912** |
| PSR içi | ort. gölge 0,998 (p1 0,953), `thermal_min` medyanı −183,15 °C; `≤ −180 °C` 16 406 hücrenin 13 761'i PSR'da; geçilebilir LPR-1 83 / VIPER 78 |
| 2-B LPR-1 gündüz (358,494)→(206,426) | w ≤ 0,10 aynı rota (156 nokta, 0,910 km, 1,623 h, 597,2 Wh, SOC 94,31); w ≥ 0,15 örtüşme 0,97, 596,9 Wh |
| 2-B LPR-1 Ay gecesi (186,34)→(494,450) | w 0,05 örtüşme 0,20; **w 0,15 örtüşme 0,05**, rota pürüzlülük 0,75 → 0,66 m, mesafe 2,727 km aynı, 1 465,7 → 1 519,4 Wh (+%3,7), 4,366 → 4,429 h, SOC 87,10 → 85,91 |
| 2-B VIPER standart | w ≤ 0,20 aynı (5,403 h, 2 741,8 Wh, 57,64); w 0,30 örtüşme 0,87, 2 747,8 Wh |
| 2-B VIPER kısa leg | w ≤ 0,15 aynı (33 nokta, 1,551 h, 920,3 Wh, 84,62); w ≥ 0,20 örtüşme 0,83, 920,8 Wh |
| 4-B LPR-1 28 Eyl (w 0 → 0,15) | aynı 41 hamle, 2,979 h, SOC %92,5, rota pürüzlülük 1,10 / 2,31 m; B5 %100 / %99,8 |
| 4-B LPR-1 Ay gecesi 13 Eyl | 116 hamle, örtüşme 0,89, 6,749 h, %67,4, pürüzlülük 0,72 → 0,71 m; B5 %98,8 / %88,8 aynı |
| 4-B VIPER kısa leg 30 May 2027 | aynı 8 hamle, 2,235 h, %72,3; B5 %99,6 / %95,0 |
| Süreler | 2-B 0,2–1,6 s; 4-B 3–20 s; stres testi 1 000 koşum rota başına birkaç saniye |

**Bulgular.**
- Kriter atıl değil ve eğimin kopyası değil (0,21); ama Site11'de dört standart çiftten
  yalnız **Ay gecesi** çiftini belirgin değiştiriyor — ve orada daha düz zemini **+54 Wh /
  −1,2 pt SOC** ile satın alıyor: gölge/enerji kriterleri ile pürüzlülük kriteri farklı
  rotaları tercih ediyor, ağırlıklı toplam aradaki dengeyi kuruyor. Gündüz çiftleri 5 m
  gridde zaten en pürüzsüz koridoru kullanıyor (rota ort. f 0,83 = ortamın ortalaması).
- 4-B'de (coarsen 4, blok-maks) hiçbir rota hamle/varış/SOC/B5 değiştirmedi; Ay gecesi
  rotası bloklarının %11'i yer değiştirdi.
- PSR maskesi bizim gölge modelimizle hücrede 0,83, ürün çözünürlüğünde 0,91 örtüşüyor;
  kalan fark 20 m piksel kenarları + örnekleme farkı. `thermal_min`'in 90 K tabanı PSR
  içinde tutarlı (medyan −183,15 °C). PSR'ı geçilebilirliğe sokmak gereksiz: termal kapı
  zaten %99,4'ünü kapatıyor.
- Ürünün 50 m ham penceresindeki medyan (0,817) ile griddeki (0,827) fark kenar payından.

**Sapmalar (spec'e göre).** `cost_criteria` yeniden-hesap koşulu (yukarıda); `_risk_sources`'a
pürüzlülük kaynağı yalnız katman varken; 4-B bloğunda WAIT tekrarları atılır (`n_cells` = hamle + 1),
blok PSR'a "değiyorsa" sayılır; `roughness_block.product_url` ve `references` alanları eklendi;
`RoughnessLayer(weight, scale, validity)` imzası (ölçek zorunlu); B2'nin v4 kilidi katmansız temel
gride taşındı (`_four_term_base`); `total_edge_cost` değişmedi.

**Testler.** 26 birim + 30 maliyet yolu + 16 API + 6 yükleyici + 10 skip-korumalı gerçek grid;
uyarlanan on mevcut test (beş ağırlık, v5 kimliği, damgalı fixture'lara `cost_criteria` — ilk tam paket koşumunda iki damgalı fixture (`test_plan_endpoint`, `test_risk_cost`) bu yüzden kırıldı ve damgalandı —, v4 kilidi katmansız temelde). Tam paket: **1 338 passed, 2 skipped** (12 min 55 s tek başına; tek uyarı `test_visibility_validation`'ın, önceden var).
