# A4 — Dünya görünürlüğü (DTE) katmanı ve iletişim gölgesi — Tasarım Belgesi

**Tarih:** 3 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → A4](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

VIPER'da rota planlamanın asıl kısıtı Güneş değil, **Dünya görünürlüğü**dür:
teleoperasyon yalnızca Direct-to-Earth (DTE) bağlantı varken mümkündür.
LunaPath'te Dünya vektörü hiçbir yerde hesaplanmıyor; `replan_triggers.check_comm_window`
girdisini (`comm_minutes_remaining`) dışarıdan bekliyor.

Tek cümlelik iddia: **Güneş için zaten var olan SPICE + ufuk-küpü boru hattı,
`SUN` yerine `EARTH` ile ikinci kez koşturulur; çıkan alan bir katman, bir zaman
serisi, bir planlayıcı kısıtı ve bir replan girdisi olarak yayınlanır ve
NASA'nın 18,6 yıllık ölçülmüş ürünüyle (PGDA 69) sayısal olarak karşılaştırılır.**

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Bu tasarımda rolü |
|---|---|---|
| `spkpos("SUN", et, "MOON_ME", "LT+S", "MOON")` | `ephemeris.sun_vector_body` | Gövde adı parametreleştirilir; `EARTH` aynı çağrıdır |
| `sun_azel_from_vector`, `true_north_grid_azimuth`, `true_azimuth_to_grid_azimuth` | `ephemeris.py` | Aynen; Dünya için de geçerli |
| `illuminated_mask(horizon, az, el)` | `illumination.py` | "Gök cismi yerel ufkun üstünde mi?" — Dünya için birebir aynı geometri, sentinel kuralı dahil |
| `horizon_map.npy` (72, 500, 500) | `illumination_series.horizon_cache_path` | Tek ufuk küpü, iki gök cismi |
| `sun_track_for_series`, `_window_centre_latlon` | `illumination_series.py` | Gövde parametreli ortak yardımcıya çıkarılır |
| `/api/illumination-series` bütçe kontrolleri, `X-Series-*` başlıkları, `encode_layer_f32` | `main.py`, `terrain.py` | Paralel `/api/earth-series` aynı sözleşmeyi kullanır |
| `astar_4d` zarf takibi (batarya, gölge saati), `REJECTION_KEYS`, `no_path_reason_4d` | `pathfinder_4d.py` | Yeni `earth_visibility` red anahtarı aynı kalıba eklenir |
| `check_comm_window`, `evaluate_triggers_detailed` | `replan_triggers.py` | Değişmez; artık gerçek girdi alır |
| `thermal_validation.thermal_comparison`, `scripts/diviner_validation.py` | — | Aynı desen: saf karşılaştırma fonksiyonu + reprojeksiyon yapan script |

## Fizik notu

Dünya'nın Ay güney kutbundan görünen yükseklik açısı libration nedeniyle
yaklaşık ±7° arasında, ~27 günlük periyotla salınır; azimutu ise
sub-Earth boylamı (±8°) etrafında döner. Bu grid için ölçüm (Site11, pencere
merkezi −88,920°, −72,672°; 7 Eylül – 4 Ekim 2026): Dünya gerçek azimut
67,6°–78,0°, yükseklik −6,5°…+7,0°; grid-kuzey azimutu 287,3° olduğundan
Dünya'nın grid azimutu −5°…+5° (kuzey ufuk kutusu). 4 Eylül 2026'da
yükseklik +7,1° (döngünün tepesi). Yani Dünya görünürlüğü **saatler değil
günler** ölçeğinde değişir ve ufkun yalnızca kuzey kutusu belirleyicidir. Ürün,
Mazarico vd. (2011) ile aynı ufuk yöntemini kullanır; karşılaştırma bu yüzden
anlamlıdır.

---

## Bileşenler

### 1. `app/ephemeris.py` — gövde parametreli vektör

- `body_vector_body(body: str, et, meta_kernel) -> np.ndarray` — `spkpos(body, …)`.
- `sun_vector_body(et)` → `body_vector_body("SUN", et)` (imza ve çıktı aynen).
- `earth_vector_body(et)` → `body_vector_body("EARTH", et)`.

### 2. `app/illumination_series.py` — gövde parametreli iz

- `_grid_north_azimuth(metadata) -> float` (mevcut iki kopyadaki kod tek yere).
- `body_track_for_series(metadata, n_slices, slice_hours, start_utc, body="SUN")`
  — mevcut `sun_track_for_series` gövdesi; çıktı sözlüğü **aynen**
  (`index, utc, azimuth_true_deg, azimuth_grid_deg, elevation_deg`).
- `sun_track_for_series(...)` → `body_track_for_series(..., body="SUN")`.

### 3. `app/earth_visibility.py` — yeni modül

```
EARTH_VISIBILITY_CACHE_FILENAME = "earth_visibility_grid.npy"
EARTH_VISIBILITY_META_FILENAME  = "earth_visibility_meta.json"

earth_track_for_series(metadata, n_slices, slice_hours, start_utc) -> list[dict]
earth_visible_mask(horizon_deg, earth_az_grid_deg, earth_elev_deg) -> (H, W) bool
build_earth_visibility_series(base_fraction, metadata, n_slices, slice_hours, start_utc)
    -> (series: list[(H, W) float64 1.0/0.0], provenance: dict)
long_run_earth_visibility(horizon, metadata, start_utc, span_days, step_hours, progress=False)
    -> (fraction: (H, W) float32, info: dict)
comm_window(horizon, metadata, row, col, utc, step_minutes=30.0, max_hours=336.0) -> dict
comm_window_from_metadata(metadata, row, col, utc) -> dict | None
```

**`build_earth_visibility_series` kuralı** (`build_shadow_series` ile aynı dürüstlük):

| Durum | `series` | `provenance` |
|---|---|---|
| epoch + ufuk küpü + çekirdek | dilim başına ikili maske | `{"model": "spice_horizon", "time_varying": true, "horizon_cache", "start_utc"}` |
| yukarıdakilerden biri yok, `base_fraction` var | `[base] * n` | `{"model": "static", "time_varying": false, "reason": …}` |
| hiçbiri yok | `[]` | `{"model": "unavailable", "time_varying": false, "reason": …}` |

`comm_window` çıktısı:

```jsonc
{ "utc": "...", "visible_now": true,
  "minutes_remaining": 4380.0,          // görünürken: batışa kalan; görünmezken: 0.0
  "minutes_until_visible": null,        // görünmezken: doğuşa kalan
  "next_change_utc": "...", "search_limited": false,
  "earth_elevation_deg": 6.6, "earth_azimuth_true_deg": 107.0,
  "earth_azimuth_grid_deg": 357.0, "horizon_deg": -18.9 }
```

`minutes_remaining` görünmezken **0.0**'dır: `check_comm_window(0.0)` tetiklenir —
DTE yokken planı yeniden değerlendirmek VIPER kuralıdır.

### 4. `app/data_loader.py` — opsiyonel katman

`load_preprocessed_grids`: `earth_visibility_grid.npy` varsa `grids["earth_visibility"]`
(float64), `layer_validity["earth_visibility"] = "DERIVED"`, yan dosya
`earth_visibility_meta.json` varsa `metadata["earth_visibility"]` altına. Yoksa
hiçbir anahtar eklenmez (katman "yok" demek, "UNKNOWN" demek değil).

### 5. `app/terrain.py` — manifest

`TERRAIN_LAYERS` sonuna `earth_visibility`; `LAYER_UNITS` `fraction`;
`LAYER_DESCRIPTIONS` bir cümle. `terrain_manifest` mevcut olmayan katmanı zaten
atlıyor.

### 6. `app/pathfinder_4d.py` — kısıt ve raporlama

`astar_4d(..., earth_visible_cube=None, require_earth_visibility=False)`:

- `REJECTION_KEYS` + `"earth_visibility"`.
- MOVE kenarı: `require_earth_visibility` ve varış hücresi varış diliminde
  Dünya'yı görmüyorsa reddet. WAIT her yerde serbest (VIPER kuralı sürüş içindir).
- Sonuç: `path_earth_visible: list[bool] | None`, `metrics.moves_out_of_earth_view`,
  `metrics.earth_visibility_enforced`.
- `no_path_reason_4d`: "N edges would have driven the rover out of Earth
  visibility (require_earth_visibility)".

### 7. `app/visibility_validation.py` — saf karşılaştırma

`visibility_comparison(model_frac, reference_frac, threshold=0.5)` →
`rmse, mae, bias, pearson_r, n_compared, disagreement_pct` (eşikte anlaşmazlık).

### 8. `app/main.py` — uçlar

| Uç | Değişiklik |
|---|---|
| `GET /api/layers/earth_visibility` | `valid_layers`'a eklenir; katman yüklü değilse 404 ve `scripts/build_earth_visibility_cache.py` işaret edilir |
| `GET /api/terrain` | katman varsa manifestte görünür (otomatik) |
| `GET /api/earth-series` | `/api/illumination-series` ile aynı parametreler; JSON: `slices, slice_hours, start_utc, grid, earth_model, earth[] (iz + visible_fraction), fields.earth_visible, binary_format`; `format=f32&field=earth_visible` ikili küp; model `unavailable` iken ikili istek 404 |
| `POST /api/plan-4d` | istek `require_earth_visibility: bool=false`; yanıt `path_earth_visible`, `earth_model`, `metrics.moves_out_of_earth_view`, `metrics.earth_visibility_enforced`; kısıt istenip seri `unavailable` ise 422 |
| `GET /api/comm-window?row&col&utc` | `comm_window` sonucu; ufuk küpü yoksa 409 |
| `POST /api/replan` | istek `utc: str|None`; `state.comm_minutes_remaining` yoksa ve `utc` + ufuk varsa hesaplanır; yanıt `comm_window` |
| `POST /api/pose` | `pose.timestamp_utc` + `pose.x_m/y_m` ile aynı doldurma; yanıt `comm_window` |

Bütçe kontrolü iki seri ucunda ortak `_check_series_budget` yardımcısına alınır;
hata metinleri değişmez.

### 9. Scriptler

- `scripts/build_earth_visibility_cache.py` — `horizon_map.npy` + çekirdeklerle
  `long_run_earth_visibility` koşturur; varsayılan 1 yıl / 1 saat (8 766 örnek);
  `--span-days 6798.4` ile 18,6 yıl. `earth_visibility_grid.npy` + meta yazar.
- `scripts/earth_visibility_validation.py` — PGDA `AVGVISIB_85S_060M_201608_EARTH.TIF`
  (24,9 MB, `lunapath/data/raw/`, gitignored) referansını 60 m'ye blok-ortalanmış
  modelimizle karşılaştırır; `docs/research/earth_visibility_validation.md` yazar.
  Referans dosya yoksa nasıl alınacağını yazar ve 0 ile çıkar; **asla veri uydurmaz**.

---

## Veri akışı

```
kernels ──► earth_vector_body(et) ──► sun_azel_from_vector ──► true→grid azimut
                                                                    │
horizon_map.npy ─────────────────────────────► illuminated_mask ◄───┘
        │                                             │
        │   (script, 8 766 örnek)                     │ (istek başına n_slices)
        ▼                                             ▼
earth_visibility_grid.npy ──► /api/layers, /api/terrain    build_earth_visibility_series
                                                          ├─► /api/earth-series
                                                          └─► /api/plan-4d (küp, kısıt, rapor)
horizon_map.npy (mmap, tek hücre) ──► comm_window ──► /api/comm-window, /api/replan, /api/pose
```

## Hata davranışı

- Çekirdek/ufuk yokken hiçbir uç düşmez: seri `static`/`unavailable` der,
  plan kısıtsız devam eder (kısıt açıkça istenmişse 422), comm-window 409.
- SPICE hataları `build_shadow_series` ile aynı gerekçeyle geniş yakalanır ve
  `reason`'a yazılır.

## Test stratejisi

- Saf geometri ve seri mantığı: `spiceypy` yerine **monkeypatch** ile senaryolu
  Dünya vektörü (yükseklik +5° → −5°), geçici `processed_dir` içinde küçük
  `horizon_map.npy`. Çekirdeksiz temiz klonda koşar.
- Uç sözleşmeleri: `test_terrain_api.py` / `test_plan_4d_endpoint.py` deseniyle,
  `main.build_earth_visibility_series` monkeypatch'lenerek.
- Gerçek grid: `test_earth_visibility_real_grid.py`, `horizon_map.npy` ve çekirdek
  yoksa `skip`; Dünya yüksekliği ±7° bandında, 30 günlük seride hem görünen hem
  görünmeyen dilim var, `comm_window` süreleri seriyle tutarlı.
- Doğrulama: `visibility_comparison` sentetik grid testi; script çıktısı belgeye.

## Uygulama sırasında bulunanlar (4 Eylül 2026)

Doğrulama adımı (madde 9) ilk koşumda model ortalaması 0,94, referans 0,34 ve
**negatif** korelasyon verdi. Kök neden araştırması iki önceden var olan sorunu
ortaya çıkardı; ikisi de bu özelliğin kapsamında kapatıldı.

1. **Yerel veri ile izlenen metadata farklı sitedeydi.** `elevation_grid.npy`
   ham Site01 DEM'inin (satır 0, sütun 700) penceresiyle birebir aynıydı; oysa
   31 Ağustos'taki `fea37ef` commit'i `metadata.json`'ı Site11 konumuna
   (origin −32 500 / 11 000, pencere 2400/2500) çevirmişti ve `.npy` dosyaları
   gitignore'da olduğundan bu makinede yenilenmemişti. Sonuç: pencere merkezi
   40 km yanlış yerde, gerçek-kuzey → grid-kuzey dönüşümü 37° hatalı, referans
   yanlış yerden örneklenmiş. Çözüm: Site11 DEM'i (PGDA, 41 MB) indirildi, P1
   hattı `--row-offset 2400 --col-offset 2500` ile yeniden koşturuldu;
   `build_horizon_cache.py` artık ham DEM'deki pencerenin işlenmiş gridle
   eşleştiğini doğruluyor ve eşleşmezse **reddediyor**.
2. **10 km ışın menzili uzak ufku kesiyordu.** Doğru konumda desen örtüştü
   (r = 0,63, 0,5 eşiğinde anlaşmazlık %3) ama model 1,0 derken referans
   0,57'de tavan yapıyordu: krater kenarından ufuk 10 km içinde −20°'ye düşüyor,
   karşı duvar ve ötesindeki plato hiç görülmüyordu; Dünya'nın yüksekliği ±7°
   bandında olduğundan görünürlüğü tam da o uzak ufuk belirler (Güneş için
   ±2° ile daha da kritik). Çözüm: `horizon_map` `min_range_m` parametresi
   aldı; `build_horizon_cache.py` LOLA 40 m kutup DEM'i (`ldem_85s_40m.img`,
   PDS Geosciences, 115 MB) üzerinde 10–150 km arasını ikinci geçişle tarıyor,
   iki DEM arasındaki datum farkını pencere üzerinden ölçüp düzeltiyor
   (ölçüldü: +0,3 m, korelasyon 0,998) ve küp iki geçişin en büyüğü oluyor.
   Kaynak: `horizon_map_meta.json`.

Sonuç (Site11, 18,6 yıl / saatlik, 163 162 örnek; referans PGDA 69, 60 m):

| Ölçek | RMSE | MAE | Bias | Pearson r | Anlaşmazlık (0,5) | n |
|---|---|---|---|---|---|---|
| 60 m (12×12 blok ort.) | 0,087 | 0,063 | −0,062 | 0,960 | %9,4 | 1 681 |
| 5 m (referans enterpole) | 0,101 | 0,064 | −0,062 | 0,934 | %9,4 | 250 000 |

Düzeltmeler öncesi aynı karşılaştırma RMSE 0,665 / r −0,16 idi. Kalan −0,06
bias modelin referanstan biraz **daha az** görünürlük vermesidir; olası
kaynaklar 5 m DEM'in ek ayrıntısı ve uzak alanın 40 m çözünürlüğü. Uzak alan
ufku (azimut, hücre) çiftlerinin %27,5'inde ortalama 4,2° yükseltti. Tam
rapor: `docs/research/earth_visibility_validation.md`.

## Kapsam dışı (bilinçli)

- Araştırma belgesindeki 3(b) "PSR girişleri hariç" maddesi: VIPER'ın PSR
  geziler için DTE kuralını nasıl gevşettiği kaynakta netleşmediğinden bu turda
  yok; `require_earth_visibility=false` varsayılanı zaten kısıtsız planlar.
- Frontend görselleştirmesi (arkadaşın dalı); yalnızca sözleşme belgesi güncellenir.
