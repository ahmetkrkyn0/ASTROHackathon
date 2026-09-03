# 3-B veri sözleşmesi

Frontend'in three.js ile gerçek bir arazi sahnesi kurması için backend'in
yayınladığı veri. **Mevcut hiçbir çağrı değişmedi** — `fetchLayer` ve JSON
`/api/layers` aynen çalışıyor; buradaki her şey onların yanına eklendi.

Neden gerekti: JSON katmanı 500×500 gridi ~4,25 MB metin olarak taşıyor ve
65 536 hücrelik tavana takılıyor, bu yüzden frontend hep `downsample=2` ile
250×250 çekiyordu. Aynı alan float32 olarak **1,00 MB** — kırpılmış JSON
önizlemesinden bile küçük. Tavan ikili yolda uygulanmıyor.

---

## Kurulum — bir kez

Zaman serisi, ufuk küpü cache'i olmadan **çalışmaz**. Sessizce bozulmaz:
`shadow_model.model` alanı `"static"` der ve `reason` neyin eksik olduğunu
yazar. Ama animasyon istiyorsan bunu bir kez çalıştır:

```bash
python scripts/build_horizon_cache.py
```

Birkaç dakika sürer, `lunapath/data/processed/horizon_map.npy` yazar
(69 MiB, `(72, 500, 500)`). `.gitignore`'da — türetilmiş artefakt, depoya
girmiyor, her geliştirici kendi makinesinde üretir.

---

## Üç uç nokta

### 1. `GET /api/terrain` — sahne manifestosu

Tek çağrı. Bir bayt grid çekmeden önce sahneyi kurmak için gereken her şey.

```jsonc
{
  "grid":   { "rows": 500, "cols": 500, "resolution_m": 5.0,
              "span_m": [2500.0, 2500.0], "cells": 250000 },
  "georeference": {
    "origin": { "x": -32500.0, "y": 11000.0 },
    "crs": "PROJCS[\"unnamed\",...Polar_Stereographic...]",
    "window_offset": { "row": 2400, "col": 2500 },
    "row_axis": "north-to-south",
    "col_axis": "west-to-east"
  },
  "elevation": { "min_m": 528.82, "max_m": 954.47, "relief_m": 425.65,
                 "vertical_exaggeration_suggested": 1.5 },
  "binary_format": {
    "dtype": "float32", "endian": "little", "order": "row-major",
    "nodata": "NaN", "bytes_per_layer": 1000000,
    "decode": "new Float32Array(await (await fetch(url)).arrayBuffer())"
  },
  "rover":   { "id": "lpr_1", "name": "LPR-1" },
  "weights": { "w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19 },
  "layers": {
    "elevation": { "units": "m", "validity": "MEASURED",
                   "min": 528.82, "max": 954.47, "nodata": 0,
                   "binary_url": "/api/layers/elevation?format=f32&rover_id=lpr_1",
                   "json_url":   "/api/layers/elevation" }
    // slope, aspect, thermal, thermal_min, shadow_ratio, cost, traversable
  }
}
```

`binary_url`'leri **olduğu gibi** `fetch` et. Sorgu dizesini elle kurma —
`cost` ve `traversable` rover'a ve ağırlıklara bağlı, manifest bunları zaten
URL'ye gömüyor.

Parametreler: `rover_id`, `w_slope`, `w_energy`, `w_shadow`, `w_thermal`.

### 2. `GET /api/layers/{ad}?format=f32` — ham grid

Başlıksız `Float32Array`. Çözme kodunun tamamı:

```js
const buf = new Float32Array(await (await fetch(url)).arrayBuffer())
```

`format` yazılmazsa varsayılan `json` — eski davranış birebir korunuyor.
`downsample` (1–50) ikili yolda da çalışıyor, ama gerekmiyor: tam grid 1 MB.

Yanıt başlıkları (hepsi CORS'ta açık, tarayıcıdan okunabilir):

| Başlık | Örnek | Ne |
|---|---|---|
| `X-Layer-Rows` / `X-Layer-Cols` | `500` / `500` | dizi boyutu |
| `X-Layer-Resolution-M` | `5.0` | **dönen gridin** adımı (downsample dahil) |
| `X-Layer-Min` / `X-Layer-Max` | `528.82` / `954.47` | sonlu değer aralığı — renk rampası için |
| `X-Layer-Nodata` | `39937` | NaN hücre sayısı |
| `X-Layer-Validity` | `MEASURED` | ölçüm mü model mi |
| `X-Layer-Dtype` / `-Endian` / `-Order` | `float32` / `little` / `row-major` | tel biçimi |

Katmanlar: `elevation`, `slope`, `aspect`, `thermal`, `thermal_min`,
`shadow_ratio`, `cost`, `traversable`.

### 3. `GET /api/illumination-series` — zaman serisi

`format=json` (varsayılan) manifest döner; `format=f32&field=shadow` veya
`field=surface_temp_c` `(T, rows, cols)` ikili küp döner.

```
/api/illumination-series?start_utc=2026-09-01T00:00:00&n_slices=24&slice_hours=1&downsample=2
```

```jsonc
{
  "slices": 24, "slice_hours": 1.0, "start_utc": "2026-09-01T00:00:00",
  "grid": { "rows": 250, "cols": 250, "resolution_m": 10.0, "downsample": 2 },
  "shadow_model": { "model": "spice_horizon", "time_varying": true,
                    "horizon_cache": ".../horizon_map.npy" },
  "thermal_model": { "recipe": "shadowed_equilibrium_c per slice, then relax_surface_c",
                     "tau_s": 3600.0, "validity": "UNCALIBRATED" },
  "sun": [ { "index": 0, "utc": "2026-09-01T00:00:00Z",
             "azimuth_true_deg": 59.09, "azimuth_grid_deg": 308.87,
             "elevation_deg": 0.49 } ],
  "fields": {
    "shadow":         { "units": "fraction", "min": 0.0, "max": 1.0, "binary_url": "..." },
    "surface_temp_c": { "units": "degC", "min": -183.15, "max": 20.0, "binary_url": "..." }
  },
  "binary_format": { "order": "slice-major, then row-major", "shape": [24, 250, 250] }
}
```

**`shadow_model`'i kontrol et.** `time_varying: false` ise animasyon yok ve
`reason` sebebini söyler (epoch verilmedi, ya da ufuk cache'i yok). Donuk bir
küpü fizik diye göstermeyin.

Bütçe: `T × satır × sütun × 4` bayt, tavan 64 MiB. Aşarsan 422 gelir ve hata
**hangi `downsample`'ın sığacağını yazar**.

---

## Tel biçimi — üçü için de aynı

- **little-endian float32**, satır öncelikli (C order). Seride önce dilim,
  sonra satır.
- **No-data yalnızca NaN.** Backend `+inf`'i de NaN'a çeviriyor — `cost`
  katmanında 39 937 hücre geçilemez ve float32 sonsuzluğu renk rampasına ya
  da vertex konumuna taşırsa sahne sessizce bozulur, hata vermez.
- Dizi uzunluğu tam olarak `rows × cols` (seride `T × rows × cols`).

---

## İki tuzak

**1. Eksen yönü.** Satır 0 gridin **kuzey** kenarı, sütun 0 **batı** kenarı.
`PlaneGeometry` XY'de kurulup bu unutulursa saha **aynalı** çizilir ve tamamen
makul görünür. Manifest bunu `georeference.row_axis` / `col_axis` alanlarında
söylüyor.

**2. NaN vertex.** Tek bir NaN vertex three.js'te **mesh'in tamamını**
render'dan düşürür. `elevation` bu gridde NaN içermiyor (ölçüldü: 0 hücre),
ama koda yine de taban değerine sabitleyen bir kontrol koy — grid değişirse
sessizce kaybolan bir sahneyle uğraşmayasın.

---

## Ölçüler

| | |
|---|---|
| Kaynak | PGDA **Site11 — de Gerlache Rim**, LOLA 5 m/px (Barker+ 2021) |
| Pencere | ham DTM'de row=2400, col=2500 |
| Merkez | 88,920° G / 287,328° D |
| Grid | 500×500 @ 5 m/px |
| Açıklık | 2500 m × 2500 m |
| Kabartı | 425,7 m (528,8 → 954,5 m) |
| Oran | 1:5,9 — öneri **1,5** (hafif abartma) |
| Katman başına | 1,00 MB float32 |
| `cost` NaN | 39 937 hücre (geçilemez) |

> **Pencere neden bu?** Altı PGDA sitesinin tamamında 500×500'lük tüm
> pencereler tarandı (4700+ aday) ve *kabartıya* değil, kabartının ne
> kadarının **gerçek arazi yapısı** olduğuna göre sıralandı. Önceki pencere
> (Site01 row=0 col=700) 1064 m kabartı taşıyordu ama bunun %94,7'si tek bir
> eğik düzlemdi — 19,3°'lik bir rampa, yani 3B sahnede eğik bir tabaka gibi
> görünüyordu. Bu pencere **%0,3 düzlem**: kabartının neredeyse tamamı krater
> çanağı, rim ve sırt. Ayrıca planlayıcı için gerçek engeller taşıyor: 5 adet
> ≥50 hücrelik bariyer, en büyüğü 8,6 hektar. Enlem de gerçek kutup rejiminde
> (Güneş yüksekliği ~1,2°), yani gölge fiziği anlamlı.

---

## Çalışan three.js bağlaması

```js
const manifest = await (await fetch('/api/terrain')).json()
const { rows, cols, resolution_m } = manifest.grid
const { min_m, vertical_exaggeration_suggested: vx } = manifest.elevation

// Yükseklik alanı. Yük tam olarak rows*cols float32.
const heights = new Float32Array(
  await (await fetch(manifest.layers.elevation.binary_url)).arrayBuffer()
)

// PlaneGeometry'nin vertex sırası, sol üstten başlayan satır öncelikli
// düzendir -- yani float32 dizisiyle indeks indeks aynı. widthSegments
// sütunları, heightSegments satırları verir.
const geometry = new THREE.PlaneGeometry(
  cols * resolution_m, rows * resolution_m, cols - 1, rows - 1
)
const position = geometry.attributes.position
for (let i = 0; i < heights.length; i++) {
  const h = heights[i]
  // NaN vertex mesh'in tamamını render'dan düşürür. Tabana sabitle.
  position.setZ(i, (Number.isNaN(h) ? min_m : h) - min_m)
}
position.needsUpdate = true
geometry.computeVertexNormals()

// Herhangi bir katmanla renklendir: aynı uzunluk, aynı sıra, indeks indeks.
const slope = new Float32Array(
  await (await fetch(manifest.layers.slope.binary_url)).arrayBuffer()
)
const { min, max } = manifest.layers.slope
const colors = new Float32Array(slope.length * 3)
for (let i = 0; i < slope.length; i++) {
  const t = Number.isNaN(slope[i]) ? 0 : (slope[i] - min) / (max - min)
  colors[i * 3]     = t          // dikleştikçe kırmızıya
  colors[i * 3 + 1] = 1 - t
  colors[i * 3 + 2] = 0.35
}
geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

const mesh = new THREE.Mesh(
  geometry,
  new THREE.MeshStandardMaterial({ vertexColors: true })
)
// Düzlemi yatır: +Z yükseklik olur, satır 0 -Z'ye yani kuzeye düşer.
mesh.rotation.x = -Math.PI / 2
mesh.scale.z = vx                 // manifest 1.0 öneriyor; slider buradan
scene.add(mesh)

// Güneş: gölgeleri üreten serinin ta kendisinden konumlanıyor.
const series = await (await fetch(
  '/api/illumination-series?start_utc=2026-09-01T00:00:00&n_slices=24&slice_hours=1&downsample=2'
)).json()

const sun = new THREE.DirectionalLight(0xfff6e5, 3.0)
scene.add(sun)

function placeSun(slice) {
  if (!series.sun.length) return          // NAIF çekirdekleri yok
  const { azimuth_grid_deg: az, elevation_deg: el } = series.sun[slice]
  const a = THREE.MathUtils.degToRad(az)
  const e = THREE.MathUtils.degToRad(el)
  // Grid azimutu kuzeyden saat yönünde. Yatırmadan sonra kuzey -Z, doğu +X.
  sun.position.set(
    Math.sin(a) * Math.cos(e),
    Math.sin(e),
    -Math.cos(a) * Math.cos(e)
  ).multiplyScalar(20000)
}
placeSun(0)

// Animasyon: gölge küpünü bir kez çek, dilimleri doku olarak geçir.
if (series.shadow_model.time_varying) {
  const cube = new Float32Array(
    await (await fetch(series.fields.shadow.binary_url)).arrayBuffer()
  )
  const [T, sr, sc] = series.binary_format.shape
  const sliceOf = (t) => cube.subarray(t * sr * sc, (t + 1) * sr * sc)
  // sliceOf(t) -> DataTexture, placeSun(t) ile birlikte ilerlet.
}
```

---

## Rota 3-B'de

`/api/plan` yanıtındaki her waypoint zaten `altitude_m` taşıyor
(`backend/app/serializer.py:245`), yani polyline doğrudan mesh'in üstüne
oturuyor. Ayrı bir yükseklik sorgusu gerekmiyor — `altitude_m - min_m`
alıp `vx` ile ölçekle, mesh ile aynı referansta olur.

---

## `/api/plan-4d` — batarya ve gölge dayanımı (3 Eylül 2026 eki)

Ay gecesine denk gelen bir `start_utc` ile plan artık **reddedilmiyor**.
Eskiden küp, yüzey sıcaklığı −150 °C'nin altına düşen her hücreyi o dilimde
geçilmez sayıyordu; gecede bu haritanın tamamıydı ("1.257.052 edges led
into cells with no finite cost"). Geçilebilirliği artık rover'ın kendi
zarfı belirliyor: planlayıcı her durumda bataryayı ve kesintisiz gölge
saatini taşıyor.

**İstek** — yeni, opsiyonel alan:

```json
{ "start": {...}, "goal": {...}, "start_utc": "2026-09-07T00:00:00",
  "initial_soc_pct": 1.0 }
```

`initial_soc_pct` ∈ (0, 1], varsayılan 1.0. Rota, bataryayı rover'ın
`soc_min_pct` rezervinin (LPR-1 için %20) altına düşüremez; rezervin altında
başlamak yalnızca güneşte bekleyerek şarj olunabiliyorsa geçerlidir.

**Yanıt** — eklenen alanlar (mevcut alanlar aynen duruyor):

| Alan | Tip | Anlamı |
|---|---|---|
| `path_battery_pct` | `number[]` | `path_states` ile aynı uzunlukta; her durumda batarya yüzdesi |
| `path_dark_hours` | `number[]` | Her duruma varışta birikmiş kesintisiz gölge saati (aydınlık hücrede sıfırlanır) |
| `metrics.min_battery_pct` | `number` | Rota boyunca en düşük batarya |
| `metrics.final_battery_pct` | `number` | Hedefte batarya |
| `metrics.max_continuous_shadow_h` | `number` | Rotadaki en uzun kesintisiz gölge; her zaman ≤ `h_max_shadow_h` |
| `metrics.energy_drawn_wh`, `metrics.energy_charged_wh` | `number` | Bataryadan çekilen / güneşten giren enerji |
| `metrics.edges_rejected.soc_floor` | `number` | Rezervi ihlal edeceği için reddedilen geçişler |
| `metrics.edges_rejected.shadow_endurance` | `number` | Gölge dayanımını aşacağı için reddedilen geçişler |
| `metrics.envelope_tracked` | `boolean` | Her zaman `true` (endpoint gölge küpünü daima geçirir) |

**404 mesajı** artık önce zarfı söyler ("… edges would have drained the
battery below the 20 percent reserve …") ve site tüm ufuk boyunca karanlıksa
bunu ekler ("The site is in darkness for the entire 6.8 h horizon …"). Gün
doğumu civarında (bu grid için 18–22 Eylül) planın beklemesi gerekir; varsayılan
ufuk yalnızca rotanın kendi süresi kadardır, bu yüzden böyle tarihlerde
`horizon_hours` (ör. 120) ve `slice_hours` (ör. 0.5) gönderin.

Süre: gerçek gridde varsayılan ayarlarla gece ve gündüz planı ~10 s.

## Dünya görünürlüğü — DTE katmanı (4 Eylül 2026 eki, A4)

VIPER kuralı: rover **Dünya ile doğrudan radyo görüş hattı (Direct-to-Earth)**
varken sürer. Backend artık Güneş için yaptığı ufuk hesabını Dünya için de
yapıyor; çıktı bir katman, bir zaman serisi, bir planlayıcı kısıtı ve bir
replan girdisi olarak yayınlanıyor. Kutupta Dünya'nın yüksekliği ±7°
arasında ~27 günlük periyotla salınır, yani bu alan **günler** ölçeğinde
değişir; Güneş gibi saatler ölçeğinde değil.

**Kurulum — bir kez** (ufuk küpünden sonra):

```bash
python scripts/build_earth_visibility_cache.py        # ~2 dk, 18,6 yıllık ortalama
```

`earth_visibility_grid.npy` + `earth_visibility_meta.json` yazar; yüklemede
`earth_visibility` katmanı olarak görünür. Ufuk küpünü uzak alanla yeniden
kurmak için (bkz. aşağıdaki not) LOLA 40 m kutup DEM'i gerekir:
`scripts/build_horizon_cache.py --force` (`lunapath/data/raw/ldem_85s_40m.img`
varsa otomatik kullanır).

### `GET /api/terrain` ve `GET /api/layers/earth_visibility`

Katman yüklüyse manifestte `layers.earth_visibility` (`units: "fraction"`,
`validity: "DERIVED"`) görünür; değeri örneklenen sürenin Dünya'yı gören kesri
(0–1). Yüklü değilse manifestte **yoktur** ve `/api/layers/earth_visibility`
404 ile hangi scripti koşturacağını söyler.

### `GET /api/earth-series` — zaman serisi

`/api/illumination-series` ile aynı parametreler ve aynı bütçe. Tek alan:
`earth_visible` (dilim başına 1.0 görüyor / 0.0 görmüyor).

```
/api/earth-series?start_utc=2026-09-07T00:00:00&n_slices=28&slice_hours=24&downsample=2
```

```jsonc
{
  "slices": 28, "slice_hours": 24.0, "start_utc": "2026-09-07T00:00:00",
  "grid": { "rows": 250, "cols": 250, "resolution_m": 10.0, "downsample": 2 },
  "earth_model": { "model": "spice_horizon", "time_varying": true, "horizon_cache": "..." },
  "earth": [ { "index": 0, "utc": "2026-09-07T00:00:00Z",
               "azimuth_true_deg": 74.2, "azimuth_grid_deg": 1.5,
               "elevation_deg": 5.9, "visible_fraction": 0.81 } ],
  "fields": { "earth_visible": { "units": "fraction", "min": 0.0, "max": 1.0, "binary_url": "..." } },
  "binary_format": { "order": "slice-major, then row-major", "shape": [28, 250, 250] }
}
```

**`earth_model`'i kontrol et.** Üç dürüst durum var: `spice_horizon`
(epoch + ufuk küpü + çekirdek), `static` (epoch yok; uzun dönem katmanı her
dilimde tekrarlanır, `reason` söyler) ve `unavailable` (hiçbir alan
hesaplanamadı: `fields` boştur, ikili istek **404** döner, sıfırlarla dolu
küp asla gelmez). `earth[i].visible_fraction` o dilimde gridin bağlantılı
kesri — zaman çizelgesinde "site ne zaman bağlantıyı kaybediyor" bundan okunur.

### `POST /api/plan-4d` — kısıt ve rapor

İstek, yeni opsiyonel alan: `"require_earth_visibility": true` (varsayılan
`false`). Açıkken her MOVE yalnızca varış diliminde Dünya'yı gören bir hücreye
yapılabilir; **bekleme hiçbir yerde kısıtlanmaz** (kural sürüş içindir).
`start_utc` ve ufuk küpü olmadan istenirse 422.

Yanıt — eklenen alanlar:

| Alan | Tip | Anlamı |
|---|---|---|
| `earth_model` | nesne | `shadow_model` ile aynı üçlü: `spice_horizon` / `static` / `unavailable` + `reason` |
| `path_earth_visible` | `boolean[] \| null` | `path_states` ile aynı uzunlukta; hücre o dilimde Dünya'yı görüyor mu. Alan yoksa `null` (asla hepsi-`true` liste değil) |
| `metrics.moves_out_of_earth_view` | `number \| null` | Dünya'yı görmeyen hücreye varan MOVE sayısı |
| `metrics.earth_visibility_enforced` | `boolean` | Kısıt uygulandı mı |
| `metrics.edges_rejected.earth_visibility` | `number` | Kısıt yüzünden reddedilen geçişler |

404 mesajı kısıt rotayı kapattıysa bunu söyler ("… edges would have driven the
rover into a cell with no Earth visibility …") ve bağlantının ufuk boyunca
hiç açılmadığını ya da kaç saat sonra açıldığını ekler.

### `GET /api/comm-window`, `POST /api/replan`, `POST /api/pose`

`comm_minutes_remaining` artık hesaplanıyor. `GET /api/comm-window?row=&col=&utc=`:

```jsonc
{ "utc": "2026-09-07T00:00:00Z", "row": 250, "col": 250,
  "visible_now": true, "minutes_remaining": 4380.0, "minutes_until_visible": null,
  "next_change_utc": "2026-09-10T01:00:00Z", "search_limited": false,
  "trigger_minutes_remaining": 4380.0,
  "earth_elevation_deg": 5.9, "earth_azimuth_true_deg": 74.2,
  "earth_azimuth_grid_deg": 1.5, "horizon_deg": -0.8 }
```

`trigger_minutes_remaining` her zaman sayıdır: bağlantı varken kapanmaya kalan
dakika (arama 14 günü aşarsa arama uzunluğu, `search_limited: true` ile "en
az"); bağlantı yokken **0** — VIPER bağlantısız sürmez, tetikleyici ateşlenir.
Ufuk küpü yoksa 409.

`POST /api/replan` gövdesine `"utc": "..."` ekleyince, `state` içinde
`comm_minutes_remaining` yoksa backend bunu `current` hücresinden hesaplar;
verilmişse **ezmez**. `POST /api/pose` aynısını `pose.timestamp_utc` ve
`pose.x_m/y_m` ile kendiliğinden yapar. İki yanıt da hesaplanan pencereyi
`comm_window` alanında döner (hesaplanamadıysa `null`, tetikleyici `skipped`).

### Not — ufuk küpü artık iki ölçekli

Bu katmanı NASA'nın LOLA "average Earth visibility" ürünüyle karşılaştırmak
(`scripts/earth_visibility_validation.py`, rapor
`docs/research/earth_visibility_validation.md`) 10 km ışın menzilinin uzak
ufku kestiğini gösterdi: krater kenarından ufuk 10 km içinde −20°'ye düşüyor
ve karşı duvar hiç görülmüyordu. `build_horizon_cache.py` artık LOLA 40 m
kutup DEM'i üzerinde 10–150 km arasını da tarıyor ve iki geçişin en büyüğünü
alıyor. Bu **`shadow_ratio` serisini de etkiler** (Güneş ±2° yükseklikte aynı
uzak ufka bağlıdır); yeniden kurulmuş küple aydınlanma döngüsü ölçümleri
değişebilir.

## Değişmeyenler

`fetchLayer`, `/api/plan`, `/api/plan-4d` (mevcut alanları), `/api/cell-telemetry`,
`/api/profiles`, `/api/rovers` — hepsi aynen. `format` opsiyonel ve
varsayılanı `json`.
