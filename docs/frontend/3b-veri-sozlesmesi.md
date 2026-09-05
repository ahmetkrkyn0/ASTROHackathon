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

## Safe Haven — VIPER'ın leg kuralı (4 Eylül 2026 eki, A1)

VIPER'ın traverse'i "leg"lerden oluşur ve her leg bir **Safe Haven**'da
biter: Dünya ufkun altındayken (ayın ~2 haftası) rover komut alamaz, o
dönemi tek başına atlatabileceği bir yerde park etmiş olmalıdır. NASA'nın
tanımı birebir: *Dünya ufkun altındayken kesintisiz gölge süresi rover'ın
dayanımını (`h_max_shadow_h`: LPR-1 50 h, VIPER 96 h, LUVMI-M 4 h, Yutu-2
2 h) aşmayan ve hareketsiz beklerken güç üretebilen (pencerede en az bir kez
aydınlanan), geçilebilir hücre.* Backend bunu bir sinodik ay (708,7 h, 2 h
adım) boyunca Güneş + Dünya serilerinden hesaplar; katman **rover'a ve
epoch'a bağlıdır**, bu yüzden manifestte değil ayrı bir uçta yayınlanır.

**Ölçülen gerçek (Site11):** Dünya'nın olmadığı iki hafta, sitenin tamamının
~6,5 gün karanlık kaldığı Ay gecesiyle çakışıyor; en kısa Dünya-yok karanlık
Ay gününe göre 40–186 h. Safe haven **nadir**: LPR-1 için yalnızca Kasım
2026'da ~40 hücre, VIPER için en iyi Ay günü (Mayıs sonu 2027) ~%11, LUVMI-M
ve Yutu-2 için hiç. Sıfır hücreli bir yanıt hata değil, kuralın cevabıdır;
`max_dark_hours_without_dte` katmanı "havene ne kadar yakın" gradyanını
her zaman taşır. Ayrıntı: `docs/research/safe_haven_report.md`.

### `GET /api/safe-haven?start_utc=&rover_id=` — harita ve dört ikili katman

```
/api/safe-haven?start_utc=2027-05-30T00:00:00&rover_id=nasa_viper
```

```jsonc
{
  "rover_id": "nasa_viper", "rover_name": "NASA VIPER", "h_max_shadow_h": 96.0,
  "start_utc": "2027-05-30T00:00:00Z", "span_hours": 708.7, "step_hours": 2.0, "n_steps": 355,
  "safe_haven_model": { "model": "spice_horizon", "rule": "...", "horizon_cache": "...",
                        "time_to_haven_finite_fraction": 0.992 },
  "safe_haven_fraction": 0.115, "safe_haven_cells": 22837, "traversable_cells": 198575,
  "earth_below_fraction": 0.696,
  "grid": { "rows": 500, "cols": 500, "resolution_m": 5.0, "downsample": 1 },
  "fields": {
    "safe_haven":                 { "units": "bool",  "min": 0, "max": 1,    "nodata": 0, "binary_url": "..." },
    "max_dark_hours_without_dte": { "units": "hours", "min": 62, "max": 710, "nodata": 0, "binary_url": "..." },
    "earth_below_hours":          { "units": "hours", "min": 298, "max": 710, "nodata": 0, "binary_url": "..." },
    "time_to_safe_haven":         { "units": "hours", "min": 0, "max": 8.98, "nodata": 53071, "binary_url": "..." }
  },
  "binary_format": { "dtype": "float32", "endian": "little", "order": "row-major", "shape": [500, 500], "nodata": "NaN" }
}
```

`format=f32&field=<ad>` ile her katman `/api/layers` ile aynı tel biçiminde
gelir (`X-Layer-*` başlıkları, `downsample` desteklenir). `safe_haven` 1/0;
`time_to_safe_haven` saat, geçilemez ya da hiçbir havene ulaşamayan hücrede
**NaN** (`nodata` bu ikisinin toplamı; yukarıdaki örnekte 51 425 geçilemez +
1 646 ulaşamayan).
`start_utc` zorunlu (422). Ufuk küpü / çekirdek yoksa JSON
`safe_haven_model.model = "unavailable"` + `reason`, `fields` boş; ikili istek
**404** — sıfırlarla dolu grid asla gelmez. İlk hesap ~4 s, sonra önbellek
(rover + epoch başına).

### `GET /api/cell-telemetry?...&start_utc=` — hücre kartı

`start_utc` verilince yanıt `safe_haven` nesnesi taşır:

```jsonc
{ "safe_haven": { "is_safe_haven": true, "max_dark_hours_without_dte_h": 64.0,
                  "earth_below_hours": 300.0, "time_to_safe_haven_h": 0.0, "h_max_shadow_h": 96.0 },
  "safe_haven_model": { "model": "spice_horizon", ... } }
```

`time_to_safe_haven_h` en yakın havene sürüş saati (`null`: ulaşılamaz).
`start_utc` yoksa `safe_haven: null` ve `safe_haven_model.reason` söyler.

### `POST /api/plan-4d` — kural ve marjlar

İstek, yeni opsiyonel alan: `"require_safe_haven": true` (varsayılan `false`).
Kural, her durumda (başlangıç, her MOVE varışı **ve her WAIT**):
`time_to_safe_haven(hücre) ≤ Dünya batışına kalan saat(dilim, hücre)`.
Dünya o hücrede zaten görünmüyorsa kalan saat 0'dır — yalnızca haven olan
hücrelere izin verilir (bağlantısız rover park hâlinde olmalı). Batış, plan
ufkunun içinde Dünya küpünden, dışında 14 günlük ön-bakıştan (1 h adım)
bulunur; ön-bakışta batış yoksa süre açık uçludur (`null`) ve kural bağlamaz.

Yanıt — eklenen alanlar:

| Alan | Tip | Anlamı |
|---|---|---|
| `safe_haven_model` | nesne | `spice_horizon` (+ `coarse_safe_haven_cells`, `earthset_lookahead`) veya `unavailable` + `reason` |
| `path_time_to_haven_h` | `(number\|null)[] \| null` | Her durumda en yakın havene sürüş saati (`null`: ulaşılamaz) |
| `path_hours_until_earthset` | `(number\|null)[] \| null` | Her durumda Dünya bağlantısının kalan saati (`null`: ufuk + ön-bakışta batış yok) |
| `path_haven_margin_h` | `(number\|null)[] \| null` | İkisinin farkı; negatifse rover o anda havene yetişemez |
| `metrics.min_haven_margin_h` | `number \| null` | Rotadaki en dar sonlu marj |
| `metrics.states_past_haven_deadline` | `number \| null` | Marjı negatif durum sayısı (kural açıkken her zaman 0) |
| `metrics.ends_at_safe_haven` | `boolean \| null` | Hedef bir haven mi (leg kuralı) |
| `metrics.safe_haven_enforced` | `boolean` | Kural uygulandı mı |
| `metrics.edges_rejected.safe_haven_deadline` | `number` | Kural yüzünden reddedilen geçişler |
| `metrics.time_to_sun_shadow_min_h`, `_mean_h` | `number \| null` | SHERPA: durumun hücresi bir sonraki karanlığa kaç saat sonra girer (min / ort; ufuk boyunca aydınlıksa sayılmaz) |
| `metrics.time_to_dsn_shadow_min_h` | `number \| null` | SHERPA: rotadaki en kısa kalan Dünya bağlantısı |
| `metrics.time_to_zero_soc_min_h` | `number` | SHERPA: rover o an tam gölgede dursa bataryanın sıfıra inme süresi (en küçüğü) |

Kural istenip harita/batış küpü hesaplanamıyorsa 422. 404 mesajı kuralın
kapattığı geçiş sayısını, kaba griddeki haven sayısını ve başlangıcın kendi
marjını söyler ("… the start block is 2.10 h from the nearest with 61.0 h of
Earth link left"). `require_earth_visibility` ile birlikte açılınca plan
VIPER'ın iki kuralını da taşır.

## Monte Carlo stres testi — SHERPA "Traverse Evaluation" (4 Eylül 2026 eki, B5)

VIPER'ın planlama ekibi her planı binlerce kez, kesik Gauss dağılımlarıyla
bozarak yürütür ve metriklerin **dağılımını** raporlar. `/api/plan-4d`'nin
verdiği rota artık aynı protokolle stres testine sokulabiliyor: aynı fizik
(planlayıcının çekiş/idare/güneş aritmetiği), rota-yerel gerçek gökyüzü,
SHERPA'nın dağılımları (gecikme σ 2 h; batarya σ %20 aşağı; güç σ %20 yukarı;
hız σ %20/30/40/50 aşağı, taban 0,25; DSN kesintisi ve SEP olayı olasılıkla,
varsayılan 0) ve operatör politikası: önde iken planlanan kalkışa kadar bekle,
geride iken şarj molasını atla ve gölgeden bataryayla geç.

### `POST /api/stress-test`

İstek — `/api/plan-4d` yanıtındaki `path_states` ve planı şekillendiren alanlar:

```json
{ "path_states": [[89,123,0],[88,122,2], ...],
  "rover_id": "nasa_viper", "coarsen": 4, "slice_hours": 0.0956,
  "start_utc": "2027-05-30T00:00:00", "initial_soc_pct": 1.0,
  "n_runs": 1000, "seed": 0, "label": "haven to haven",
  "perturbations": { "speed_sigma": 0.3, "dsn_outage_probability": 0.1 } }
```

`slice_hours` zorunludur (plan yanıtının `slice_hours`'u); `perturbations`
opsiyonel ve alan alan üstüne yazar (`start_delay_sigma_h`,
`initial_soc_sigma`, `power_draw_sigma`, `speed_sigma`,
`speed_multiplier_floor`, `z_max`, `dsn_outage_probability`,
`dsn_outage_mean_h`, `sep_event_probability`, `sep_event_mean_h`);
`n_runs` 1–20.000, `n_bins` 5–100. Aynı `seed` aynı sonucu verir.

Yanıt:

| Alan | Tip | Anlamı |
|---|---|---|
| `route` | nesne | `n_states`, `move_steps`, `wait_steps`, `planned_duration_h`, `odometry_m`, `ends_at_safe_haven` (`null`: haven alanı yok) |
| `sky_model` | nesne | `spice_horizon` (+ `n_slices_extended`, `horizon_hours_extended`, `earthset_lookahead_hours`) veya `static` + `reason` (epoch/ufuk/çekirdek yok; gecikmenin etkisi olmaz) |
| `safe_haven_model` | nesne | A1 haritasının kaynağı veya `unavailable` + `reason` |
| `rates.completion` | `{count, rate, ci95:[lo,hi]}` | Hedefe canlı varan koşumlar, Wilson %95 aralığıyla |
| `rates.reached_within_reserve` | aynı | …ve bataryası hiç `soc_min_pct` rezervinin altına inmeyenler |
| `rates.full_success` | aynı | …ve (haven alanları biliniyorsa) hiçbir durumda Dünya batış süresi aşılmayanlar |
| `rates.reserve_breached` | aynı | Rezervin altına inen koşumlar |
| `failures` | nesne | İlk arıza nedeni sayıları: `battery_depleted`, `shadow_endurance`, `horizon_exceeded` |
| `metrics.<ad>` | `{mean,std,p5,p50,p95,min,max,n} \| null` | `duration_h`, `duration_normalized`, `odometry_m`, `min_battery_pct`, `final_battery_pct`, `max_continuous_shadow_h`, `time_to_sun_shadow_min_h`/`_mean_h`, `time_to_dsn_shadow_min_h`, `time_to_zero_soc_min_h`, `dsn_shadow_events`, `dsn_shadow_hours`, `states_past_haven_deadline`, örneklenen girdiler (`start_delay_h`, `speed_multiplier`, `power_multiplier`, `initial_soc_pct`). `null` = hiçbir koşumda tanımlı değil (ör. Dünya serisi yokken DSN marjı) |
| `histograms.<ad>` | `{edges, counts}` | `n_bins` kutu; süre, batarya, gölge ve marjlar için |
| `per_state` | nesne | `arrival_h` ve `battery_pct` için `p5/p50/p95` listeleri (durum başına; ölen koşumlar `null`), `alive_fraction` — rota boyunca "fan chart" için |
| `outages` | nesne | `dsn` / `sep`: `runs`, `mean_window_h`, `mean_hold_h` |
| `nominal` | nesne | Tüm çarpanlar 1, gecikme 0: `reached`, `duration_h`, `min_battery_pct`, `final_battery_pct`, `max_continuous_shadow_h`, marjlar |
| `verdict` | nesne | `reaches_goal_at_95pct`, `full_success_at_95pct` (Wilson alt sınırı ≥ 0,95), `haven_rule_known`, `text` |
| `perturbations` | nesne | Kullanılan parametreler + `source` |
| `timing_ms` | nesne | `sky`, `runs`, `total` |

Hatalar: `path_states` bozuksa (sınır dışı, komşu olmayan, geçilmez hücre,
dilim sırası, 0'dan başlamıyor) 422 gerekçeli; grid yüklü değilse 503.

Ölçülen (Site11, 1.000 koşum): VIPER haven→haven planı (30 Mayıs 2027,
40 hareket, 7,4 h, planlayıcıya göre en düşük batarya %32) → `completion`
0,296 (CI 0,269–0,325), hız σ %50'de 0,158; 704 koşum batarya tükenmesi;
`nominal.min_battery_pct` 23,2 (planlayıcı dilim yuvarlamasındaki bekleme
idaresini saymıyor). LPR-1 28 Eylül 2026 rotası (2,2 h) → `completion` 1,0
(CI 0,996–1,0), `min_battery_pct.p5` 52, `full_success` 0 çünkü o Ay gününde
haven yok (`states_past_haven_deadline` = 41/41, `verdict.text` söyler).
Süre: gökyüzü 0,8–2,1 s + koşumlar 0,06–0,6 s; plan-4d ayrıca 8–10 s.

İki rotayı kıyaslamak: iki çağrı, `label` ile; `rates.full_success.ci95`
ve `verdict` kıyas anahtarıdır ("hangisi %95 güvenle varıyor").

## DEM belirsizliği — NASA'nın DEM klonlarıyla olasılık katmanları (4 Eylül 2026 eki, B3)

NASA GSFC (PGDA ürün 78) her 5 m/px güney kutbu DEM'i için Z-belirsizlik
(`toterr`), eğim-belirsizlik (`slperr`) haritaları ve 100 istatistiksel klon
yayınlıyor. `scripts/build_dem_clone_cache.py` Site11 klonlarını planlama
penceresi için (1 km yakın-alan dolgusuyla) indirir, plan-4d'nin blok
merkezlerinde klon başına ufuk küpü üretir; backend bunlardan hücre başına
**P(geçilebilir)**, dilim başına **P(aydınlık)** ve rota başına **DEM bandı**
türetir. Klon önbelleği yoksa aşağıdakilerin hiçbiri görünmez; mevcut
alanlar değişmez.

### `GET /api/terrain` ve `GET /api/layers/{ad}?format=f32&rover_id=`

Manifestte dört yeni katman (yalnızca önbellek varken) ve üst düzey
`dem_uncertainty` pedigree bloğu:

| Katman | Birim | `validity` | Anlam |
|---|---|---|---|
| `p_traversable` | fraction | DERIVED (sentetik önbellekte SYNTHETIC) | Klonların bu rover için hücreyi geçilebilir saydığı oran; 1 kesin geçilebilir, 0 kesin değil, 0,05–0,95 belirsiz |
| `slope_sigma` | deg | DERIVED | Klon eğimlerinin std'si (bizim topluluk, `np.gradient`) |
| `elevation_sigma` | m | MODEL | NASA `toterr` — ölçüm değil, NASA'nın hata modeli |
| `slope_sigma_nasa` | deg | MODEL | NASA `slperr` |

`p_traversable` rover'a bağlıdır (`rover_id` eğim sınırını seçer);
`binary_url` bunu taşır. `dem_uncertainty`: `model`
(`nasa_pgda_clones` | `synthetic`), `site`, `product_url`, `reference`,
`n_clones`, `clone_indices`, `window_offset`, `near_range_m`, `sigma`
(toterr/slperr istatistikleri), `error_across_clones`,
`thermal_field_held_fixed: true`, `far_field_held_fixed: true`,
`earth_visibility_cloned: false`, `clone_horizons` (stride, ihmal edilen
ufuk kayması sınırı, yüzey kontrolü). Önbellek yokken `/api/layers/<yeni>`
404 + betik adı.

### `GET /api/uncertainty-series?start_utc=&n_slices=&slice_hours=&n_clones=&format=`

Klon ufuk küplerinin gridinde (stride 4 → 125×125, 20 m) dilim başına
`p_illuminated`:

| Alan | Anlam |
|---|---|
| `model` | `clone_horizon` veya `unavailable` + `reason` (küp/epoch/çekirdek yok; f32 için 404) |
| `n_clones`, `clone_indices` | Kullanılan klonlar (`n_clones` ile ilk n; varsayılan hepsi) |
| `grid` | `rows`, `cols`, `resolution_m`, `stride`, `row_offset`, `col_offset` — ince gridde ilk hücrenin yeri (blok merkezi) |
| `per_slice.mean`, `per_slice.uncertain_fraction` | Dilim başına ortalama P ve 0,05 < P < 0,95 hücre oranı |
| `sun` | Güneş izi (`/api/illumination-series` ile aynı biçim) |
| `fields.p_illuminated.binary_url` | f32: `X-Series-*` başlıkları, `[T, rows, cols]` slice-major |
| `far_field_held_fixed`, `near_range_m`, `neglected_horizon_shift_deg_max` | Ne klonlanmadı ve bunun üst sınırı |

### `POST /api/dem-uncertainty`

İstek — `/api/stress-test` çekirdeği + klon alanları:

```json
{ "path_states": [[89,123,0],[88,122,2], ...],
  "rover_id": "nasa_viper", "coarsen": 4, "slice_hours": 0.0956,
  "start_utc": "2027-05-30T00:00:00", "initial_soc_pct": 1.0,
  "n_clones": 100, "with_sherpa": false, "n_runs": 200, "seed": 0,
  "perturbations": null, "label": "haven to haven" }
```

`n_clones` ≤ önbellekteki sayı (aşarsa 422); `with_sherpa` verilirse her
klonda `n_runs` SHERPA koşumu havuzlanır (`perturbations` B5'teki gibi).

Yanıt:

| Alan | Anlam |
|---|---|
| `n_clones`, `clones_priced`, `unpriceable` | Kullanılan klon; fiyatlanan (≥ 90° kenar → düşer, indeksleri listede) |
| `route` | `n_states`, `move_steps`, `wait_steps`, `planned_duration_h`, `odometry_m` |
| `route_feasible` | `{count, fraction, ci95}` — rotanın **her** kaba hücresinin (16 ince hücrenin VE'si) geçilebilir kaldığı klon oranı, Wilson %95 |
| `reached` | Nominal (σ = 0) koşumda hedefe varan klon oranı |
| `p_traversable` | `min`, `mean`, `per_state[]` — rota hücrelerinde P |
| `metrics.<ad>` | `{p5,p50,p95,mean,std,min,max,n}`: `duration_h`, `drive_hours`, `gross_drive_wh`, `battery_used_wh`, `min_battery_pct`, `final_battery_pct`, `max_continuous_shadow_h` — klonlar arası band |
| `per_clone` | Aynı metriklerin klon başına listeleri + `reached`, `clone_index` |
| `nominal` | Yüzey DEM'iyle aynı hesap (aynı anahtarlar + `reached`) |
| `failures` | Nominal koşumda ilk arıza sayıları |
| `sky_model` | `clone_horizon` (klon küpleri, `columns` açıklaması) veya `static` + `reason`; `n_slices`, `far_field_held_fixed`, `near_range_m` |
| `sherpa` | `null` veya `{n_runs_per_clone, n_runs_total, seed, completion{count,rate,ci95}, failures, metrics, perturbations}` |
| `provenance` | `model`, `product_url`, `reference`, `n_clones_available`, `clone_indices`, neyin sabit tutulduğu |
| `timing_ms` | `sky`, `runs`, `total` |

`duration_h` B5 politikasını izler (önde iken planlanan kalkışa kadar bekle):
eğim hatası süreye ancak dilim boşluğunu aşınca yansır; DEM'e duyarlı
metrikler `drive_hours` ve `gross_drive_wh`'dir.

### `POST /api/plan` ve `POST /api/plan-4d` — `uncertainty` bloğu

Yalnızca klon önbelleği varken (yoksa alan **yok**):

```json
"uncertainty": { "model": "nasa_pgda_clones", "n_clones": 100, "coarsen": 4,
                 "p_traversable_min": 0.2, "p_traversable_mean": 0.92,
                 "route_feasible_fraction": 0.0,
                 "band_url": "/api/dem-uncertainty", "product_url": "..." }
```

`/api/plan`'da ince hücrelerde (`coarsen` 1), `/api/plan-4d`'de kaba
hücrelerde (blok VE'si). Simülasyon yok; maliyet milisaniye.

Ölçülen (Site11, 100 NASA klonu, 4 Eylül 2026): `p_traversable` VIPER için
hücrelerin %68,6'sında 1, %16,9'unda 0, **%8,2'sinde belirsiz** (LPR-1
%2,8); `slope_sigma` medyanı 1,52° (NASA `slperr` 1,73°). 30 Mayıs 2027
epoch'unda `p_illuminated` 48 dilimde hücrelerin p50 %10,8'ini kararsız
bırakıyor. VIPER haven→haven rotası: `gross_drive_wh` p5/p50/p95
2.258 / 2.293 / 2.334 Wh, `nominal` 2.127 Wh (klon eğimleri yüzeyden
sistematik yüksek: gürültü gradyanı şişirir); `route_feasible` 1/100;
`with_sherpa` tamamlanma 0,178 (B5'te 0,296). Süre: seri 0,2–0,4 s, bant
1–4 s (100 klon), plan bloğu milisaniye.

## Formal güvenlik marjları — FRETISH + STL robustness (4 Eylül 2026 eki, D3)

Güvenlik gereksinimleri NASA FRET'in yapılandırılmış doğal dili FRETISH
kalıbında elle yazıldı ([docs/requirements/lunapath.fret.json](../requirements/lunapath.fret.json),
[README](../requirements/README.md)), STL'e elle çevrildi ve her planlanan rota
bu formüllere karşı **robustness** (ρ) ile denetleniyor: ρ ≥ 0 sağlandı,
ρ < 0 ihlal, |ρ| gereksinimin biriminde marj (saat / °C / yüzde puanı /
derece / metre). Motor RTAMT 0.3.5 (kuruluysa) + yerleşik değerlendirici,
her istekte çapraz kontrol. İddia sınırı her yanıtta: **çalışma-zamanı
izleme, model checking ile ispat değil** (`monitor.claim`). Mevcut alanlar
değişmedi; aşağıdakiler yalnızca eklendi.

### `POST /api/plan`, `POST /api/plan-4d`, `POST /api/compare`, `POST /api/plan-multi` — `safety_margins` bloğu

Plan yanıtının üst düzeyinde; compare/plan-multi'de her sonucun içinde
(simülasyonu düşen sonuçta alan yok).

```json
"safety_margins": {
  "monitor": { "engine": "rtamt", "rtamt_version": "0.3.5",
               "cross_check": { "engine": "builtin", "max_abs_diff": 0.0 },
               "semantics": "discrete-time offline STL, space robustness ...",
               "trace": { "kind": "4d", "n_samples": 41, "duration_h": 7.36, "complete": true,
                          "stranded": false, "extended_h": null, "thermal_source": "static_layer", "..." : "..." },
               "recharge_deadline_h": 6.0,
               "claim": "checked by runtime monitoring of the planned trace ...; not proven by model checking ...",
               "requirements_file": "docs/requirements/lunapath.fret.json" },
  "requirements": [
    { "id": "LP-R01", "name": "shadow_endurance", "class": "safety", "applicable": true, "reason": null,
      "engine": "rtamt", "rho": 91.45, "unit": "h", "rho_normalized": 0.953, "satisfied": true,
      "boundary": false, "open_ended": false, "pending": false,
      "threshold": 96.0, "rover_parameter": "h_max_shadow_h", "threshold_source": "rover",
      "signal": "shadow_continuous_h", "scope": null,
      "worst_at": { "index": 40, "hours": 7.36, "row": 51, "col": 106 },
      "fretish": "The rover shall always satisfy shadow_continuous_h <= h_max_shadow_h",
      "stl": "always (shadow_continuous_h <= 96)" }, "..."
  ],
  "min_margin": { "id": "LP-R06", "rho": 0.48, "unit": "deg", "rho_normalized": 0.024 },
  "n_applicable": 11, "n_violated": 2, "violated": ["LP-R04", "LP-R05"], "verdict": "violated"
}
```

| Alan | Anlam |
|---|---|
| `monitor.engine` | `rtamt` ya da `builtin`; `cross_check.max_abs_diff` iki motorun en büyük farkı (rtamt yokken `null`) |
| `monitor.trace` | `kind` (`2d` / `4d` / `telemetry`), örnek sayısı, süre, `complete` (çevrimiçi prefikste false), `stranded`, `extended_h` (mahsur kalan 2-B izin bir Ay günü uzatması), kaynak notları |
| `requirements[].rho`, `unit` | Robustness ve birimi; `null` + `open_ended: true` = +∞ (Dünya batışı ön-bakışta yok); `null` + `satisfied: false` + `reason: "unbounded violation"` = −∞ (sonlu batış, ulaşılabilir haven yok) |
| `rho_normalized` | ρ / ölçek (eşik, yarı genişlik, 24 h ya da rota uzunluğu) — yalnızca kıyas anahtarı |
| `satisfied` | `true` / `false` / `null` (uygulanamaz ya da `pending`: hedefe varış çevrimiçi izde henüz karar yok); `boundary: true` ρ = 0 |
| `applicable`, `reason` | Sinyal izde yok (2-B'de Dünya/haven), kapsam hiç tutmuyor (hedefe varılmadı → LP-R11) ya da rover zarfı yok (LUVMI-M `elec_op_*`) |
| `threshold`, `rover_parameter`, `threshold_source` | Rover kataloğundan (`rover`), katalog sabiti (`catalogue`, LP-R03'ün 6 h'i) ya da `fixed` (0) |
| `worst_at` | Marjın en küçük olduğu örnek: durum/adım indeksi, saat, hücre |
| `engine` (gereksinim) | Tek örnekli kapsamda (varış) RTAMT çalışmaz → `builtin` |
| `min_margin` | `safety` sınıfı, sonlu ρ'lu gereksinimler arasında en küçük `rho_normalized` |
| `verdict` | `satisfied` / `violated` / `pending` / `not_evaluated` |

Gereksinimler (eşikler rover'dan): LP-R01 gölge dayanımı (h), LP-R02 SOC ≥
rezerv (pp), LP-R03 rezerv altında ≤ 6 h şarjsız (h), LP-R04 elektronik
termal zarfı (°C), LP-R05 batarya termal zarfı (°C), LP-R06 adım eğimi (°),
LP-R07 yanal eğim (°), LP-R08 hareket halindeyken Dünya bağlantısı (h;
yalnızca 4-B/telemetri), LP-R09 haven leg kuralı (h; 4-B/telemetri), LP-R10
hedefe varış (m, sınıf `mission`), LP-R11 varışta SOC (pp). 2-B izlerde R08/R09
`applicable: false`.

### `comparison.safety_margin_ranking` (`/api/compare`)

```json
"safety_margin_ranking": [ { "label": "balanced", "verdict": "violated", "n_violated": 1,
                             "min_margin": { "id": "LP-R05", "rho": -46.04, "unit": "degC", "rho_normalized": -2.631 } }, "..." ],
"largest_min_margin_profile": "balanced"
```

Sıra: sağlananlar en büyük min-marjla önce, sonra `pending`, sonra
ihlalliler (az ihlal, az negatif), en sonda değerlendirilemeyenler. Mevcut
`shortest_profile` / `safest_profile` / `most_efficient_profile` /
`recommendation` aynen.

### `POST /api/safety-check` — telemetri izi

```json
{ "rover_id": "nasa_viper",
  "samples": [ { "t_h": 0.0, "soc_pct": 100, "inner_temp_c": 10, "in_shadow": false, "slope_deg": 5,
                 "lateral_slope_deg": 3, "moving": false, "earth_link_h": 30, "haven_margin_h": 12,
                 "dist_to_goal_m": 400 }, "..." ],
  "complete": true, "stranded": false, "engine": "auto", "recharge_deadline_h": 6.0 }
```

`t_h` zorunlu ve artmayan olamaz; `surface_temp_c` verilirse iç sıcaklığa
çevrilir, `shadow_ratio` (> 0,2) ya da `in_shadow`; sayısal sinyaller ya
her örnekte ya hiçbirinde; booleanlar eksikse false; bilinmeyen anahtarlar
`ignored_keys`'te. Yanıt: `rover_id`, `n_samples`, `signals_present`,
`ignored_keys`, `safety_margins`. 422: boş liste, geri giden zaman,
`NaN`, bilinmeyen `engine`, `engine: "rtamt"` kurulu değilken (sessiz düşme
yok). `complete: false` → LP-R10 `pending`.

Ölçülen (Site11, 4 Eylül 2026, [safety_monitor_report.md](../research/safety_monitor_report.md)):
VIPER haven→haven 30 May 2027 planında gölge marjı 91,45 h, SOC 12,06 pp,
adım eğimi 0,48°, yanal 1,19°, Dünya bağlantısı 199,93 h, haven 199,80 h;
LP-R04/R05 ihlal (iç sıcaklık −7,96 / −27,96 °C, statik termal katman +
ofset modeli). LPR-1 28 Eyl 2026'da LP-R09 sınırsız ihlal (haven yok, bağlantı
184,6 h sonra biter). `/api/compare` 4 profil 0,8–1,0 s; `/api/safety-check`
500 örnek 12–15 ms yerleşik, 28–48 ms RTAMT; iki motor farkı 0.

## Sürekli-aydınlık koridoru — CMU'nun x-y-t bağlı-bileşen budaması (4 Eylül 2026 eki, A2)

CMU'nun Güneş-eşzamanlı (sun-synchronous) rota yaklaşımı (Otten, Jones,
Wettergreen, Whittaker; ICRA 2015 / FSR 2017) 4-B planlayıcının ön-filtresi
olarak uygulandı: aydınlanma serisi + kaba geçilebilirlik `(t, satır, sütun)`
ikili hacmine dönüştürülür, planlayıcının kendi kenarları (aynı kapılar, aynı
hamle süresi `d = ceil(kenar süresi / dilim)`) üzerinde ileri (ilk dilimden
erişilemeyen kökler) ve geri (son dilime ulaşamayan çıkmazlar) budanır; kalan
hacim **koridor**dur. `require_continuous_illumination` ile bulunan rotanın her
durumu koridorun içindedir ve `path_dark_hours` tanım gereği sıfırdır. **İddia
sınırı:** "koridor içinde modelin gölge serisi hiç karanlık göstermez" —
SPICE + ufuk küpü, 320 m bloklar, örneklenmiş dilimler; gerçek yüzey hakkında
değil (B3: 30 Mayıs 2027'de hücrelerin %10,8'i DEM klonları arasında
kararsız). Mevcut alanlar değişmedi; aşağıdakiler yalnızca eklendi.

### `POST /api/plan-4d` — iki yeni istek alanı

| Alan | Varsayılan | Anlam |
|---|---|---|
| `require_continuous_illumination` | `false` | Koridor kuralını uygula: başlangıç ilk dilimde koridorda olmalı, bekleme yalnızca koridor vokseline, hamle boyunca iki blok da aydınlık kalmalı. `start_utc` + ufuk küpü gerekir; gölge modeli `static` ise **422**. |
| `lit_rule` | `"all"` | `"all"`: bloktaki 16 ince hücrenin hepsi aydınlık (muhafazakâr). `"majority"`: blok ortalaması `< 0,5` (planlayıcının karanlık eşiği). |

### `POST /api/plan-4d` — `illumination_corridor` bloğu (her zaman) ve metrikler

```json
"illumination_corridor": {
  "enforced": false, "lit_rule": "all", "lit_rule_definition": "...", "edge_rule": "...", "pruning": "...",
  "n_slices": 100, "slice_hours": 0.0956, "grid": { "rows": 125, "cols": 125, "resolution_m": 320.0 },
  "voxels": { "traversable": 1031400, "lit_safe": 417294, "corridor": 416646,
              "corridor_fraction_of_lit_safe": 0.998, "pruned_fraction": 0.002 },
  "slices": { "first_lit": 0, "last_lit": 99, "lit_safe_cells_t0": 4160, "corridor_cells_t0": 4154, "corridor_cells_last": 4170 },
  "components": { "method": "scipy.ndimage.label, 26-neighbourhood (CMU's flood fill)",
                  "count": 50, "largest_voxels": 379720, "largest_fraction": 0.91, "spanning_count": 44 },
  "start": { "cell": [89, 123], "in_corridor_t0": false, "first_corridor_slice": null },
  "goal": { "cell": [51, 106], "corridor_slices": 0, "reachable_in_corridor": false, "first_reachable_slice": null },
  "route": { "inside": false, "states_inside": 0, "states_total": 41, "moves_outside": 40, "waits_outside": 0,
             "path_dark_hours_max": 4.546, "max_dwell_hours": 0.0, "dwell_horizon_limited": false,
             "dwell_opportunities": [] },
  "provenance": { "shadow_model": "spice_horizon", "time_varying": true, "start_utc": "2027-05-30T00:00:00",
                  "claim": "Inside the corridor the model's shadow series never shows a dark block ...",
                  "uncertainty_note": "B3: on 2027-05-30, 10.8 percent of cells are undecided ...", "reference": "Otten ... ICRA 2015; FSR 2017" },
  "timings_ms": { "lit_volume": 69, "edges": 6, "prune": 56, "dwell": 4, "total": 135, "components_ms": 39, "reach_ms": 0 }
}
```

| Alan | Anlam |
|---|---|
| `voxels` | Kaba hücre × dilim sayıları: geçilebilir hacim, aydınlık-ve-geçilebilir hacim, koridor; `pruned_fraction` = iki geçişin sildiği oran |
| `slices` | İlk/son aydınlık dilim; t0'daki aydınlık ve koridor hücre sayısı; son dilimdeki koridor hücreleri |
| `components` | CMU'nun 26-komşuluk flood-fill'i (`ndimage.label`) — kıyas için: bileşen sayısı, en büyüğü, ilk ve son dilime dokunan ("iki ucu tutan") sayısı |
| `start` / `goal` | Kaba hücre; başlangıç t0'da koridorda mı, ilk koridor dilimi; hedef kaç dilim koridorda, başlangıçtan koridor içinde ulaşılabilir mi, ilk varış dilimi |
| `route` | Rota koridorda mı, içerideki durum sayısı, dışarıdaki hamle/bekleme sayısı, `path_dark_hours` maksimumu, **dwell** (CMU metriği: hücrenin o durumdan itibaren kesintisiz koridorda kaldığı saat), `horizon_limited` = ufuk kesti; en iyi 3 fırsat |
| `provenance` | Gölge modeli (`spice_horizon` / `static` + `reason`), iddia sınırı, B3 uyarısı, kaynak |
| `metrics.max_dwell_hours` | = `route.max_dwell_hours` (koridor yoksa `null`) |
| `metrics.states_outside_corridor`, `metrics.moves_outside_corridor` | Rotanın koridor dışında kalan durum/hamle sayısı (uygulanınca 0) |
| `metrics.continuous_illumination_enforced`, `metrics.edges_rejected.continuous_illumination` | Kural uygulandı mı; kuralın reddettiği geçiş sayısı |

Kural uygulanıp koridor kapalıysa (başlangıç karanlık, hedef koridor içinde
ulaşılamaz, hiç aydınlık yok) **404** ve `detail` koridor sayılarını söyler
("Continuous-illumination corridor (lit_rule=all): 416646 of 417294 ...; the
start block is never inside the corridor; the goal block is inside the corridor
for 0 of 100 slices and is not reachable from the start inside it.").

### `GET /api/illumination-corridor?start_utc=&rover_id=&n_slices=&slice_hours=&coarsen=4&lit_rule=all&format=json|f32&field=corridor|lit_safe|dwell_hours`

Koridor küpü, `/api/illumination-series` tel biçimiyle: `float32`, little
endian, **dilim-major sonra satır-major**, şekil `[T, satır, sütun]` ama
**kaba grid** (`resolution_m` = ince × `coarsen`, 320 m). Üç alan: `corridor`
(1 içeride), `lit_safe` (budama öncesi aydınlık-ve-geçilebilir), `dwell_hours`
(o dilimden itibaren koridorda kalınan saat). Başlıklar: `X-Series-Field`,
`X-Series-Slices`, `X-Series-Rows`, `X-Series-Cols`, `X-Series-Coarsen`,
`X-Series-Lit-Rule`, `X-Series-Resolution-M`, `X-Series-Dtype`,
`X-Series-Endian`, `X-Series-Order`. JSON manifest: `n_slices`, `slice_hours`
(+ `slice_hours_source`: `auto` / `request`), `horizon_hours`, `coarsen`,
`lit_rule`, `grid`, `shadow_model`, `corridor` (yukarıdaki blok, `start`/`goal`
`null`), `fields{}.binary_url`, `binary_format`. `start_utc` yoksa seri
`static` etiketiyle üretilir (küp yine gelir; garanti anlamı yoktur).

Frontend'in çizebileceği: koridor küpünü `(t, satır, sütun)` voksel bulutu ya da
dilim başına maske olarak sahneye, planlayıcı rotasının `path_states`'ini
(kaba `(satır, sütun, dilim)`) aynı eksenlerde üstüne; `dwell_hours` ile
"burada X saat aydınlıkta beklenebilir" ısı haritası; `route.dwell_opportunities`
ile rota üzerinde bekleme noktaları; `start`/`goal` bloklarındaki
`first_corridor_slice` / `first_reachable_slice` ile "ne zaman başlanmalı"
göstergesi. Sahne zamanı `t × slice_hours` saattir.

Ölçülen (Site11, 4 Eylül 2026,
[illumination_corridor_report.md](../research/illumination_corridor_report.md)):
VIPER'ın 30 Mayıs 2027 gününde varsayılan 9,6 h ufukta kaba hacmin %40,5'i
aydınlık-güvenli (`all`; `majority` %45,8), iki geçişli budama yalnızca
%0,2'sini siliyor (10 saatte kutup aydınlanması neredeyse durağan); CMU label
50 bileşen, en büyüğü %91. Standart haven→haven çifti koridor dışında
(başlangıç t0'da karanlık, hedef hiç aydınlık değil, rota 4,55 h gölge) →
`require` 404. Koridor-içi çift (kaba (105,89)→(94,27), 62 blok ≈ 19,8 km,
7,9 h, 62 hamle): `path_dark_hours` tümü 0, LP-R01 ρ = 96 h, en düşük SOC
%93,6, dwell 8 h (ufka dayalı); planlama budamasız 7 233 düğüm, koridorla
6 467 (×1,12). LPR-1 28 Eylül 2026'da 8 saatlik koridor yok (aydınlık ada
büzülüyor); Ay gecesi 13 Eylül 2026'da hiçbir voksel aydınlık değil. Koridor
kurulumu 100 dilimde ~0,14 s (`all`) / ~0,29 s (`majority`), 246 dilimde
~0,3 s.

## Slip modeli — Yutu-2 ölçümü ve VIPER tasarım kısıtıyla kalibrasyon (4 Eylül 2026 eki, C3)

`slip_model.py` artık `UNCALIBRATED` değil: eğri **kaynaklı çapalardan**
geçer ve **tek noktadan** modele bağlıdır — `cost_engine.edge_travel_time_s`
komutlanan mesafeyi tekerlek mesafesine çevirir (`d → d / (1 − slip(eğim))`),
bu yüzden süre ve enerji birlikte büyür ve planlayıcı (2-B ve 4-B),
simülatör, koridor bütçeleri, Monte Carlo (B5), safe-haven süreleri (A1) ve
koridor dilimleri (A2) aynı sayıyı görür. Çapalar: **VIPER** mobilite tasarım
gereksinimi *"a maximum of 40% slip up a maximum slope of 15°"* (PSJ 2025;
GRC-1 simülantı, %15–20 bağıl yoğunluk — bir **üst sınır**, tipik değer
değil) ve **Yutu-2**'nin Chang'e-4'te **ölçülmüş** slip oranı (0 … −0,075,
en fazla 8,86° eğimde, çoğunlukla skid; Nature Communications 2024).
Çapalar arası ve ötesi biçim üstel (log-doğrusal), kap 0,9; `|eğim|`
simetrik. **İddia sınırı:** eğri **ölçülmüş değil, literatüre bağlı bir
MODEL**dir; "kutup regolitinde ölçüldü" denmez. Kendi verisi olmayan
profiller (LPR-1, LUVMI-M) ve rover'lar arası aktarımlar katalogda
`kind: "assumption"` ve `source: "assumption: …"` ile yazılıdır; kaynağı
olmayan çapa yoktur.

**Mevcut alanlar değişmedi, ama sayılar değişti:** `/api/plan` ve
`/api/plan-4d`'nin süre, enerji, `path_battery_pct`, `metrics.arrival_hours`,
`safety_margins` (LP-R02), `/api/stress-test` dağılımları, `/api/safe-haven`
`time_to_safe_haven_h`, `/api/plan-4d` `n_slices`/`slice_hours` (otomatik
dilim medyan eğimdeki slip kadar uzar) artık slip'i içerir; slip'siz eski
raporların sayıları (B5, B3, D3, A2, A1) yeniden üretilmedi, önce/sonra
farkı `docs/research/slip_calibration_report.md`'dedir. Maliyet gridi kimliği
`weighted_cell_cost_shadow_aware_energy_slip_v4`.

### `GET /api/rovers` — her rover'da `slip_model` ve `declared_only.regolith`

```json
"slip_model": {
  "applied": true,
  "validity": "MODEL",
  "model_id": "anchored_loglinear_v1",
  "max_slip_ratio": 0.9,
  "claim": "Literature-anchored MODEL, not a measurement: ...",
  "anchors": [
    {"slope_deg": 0.0, "slip": 0.0375, "sigma": 0.01875, "kind": "assumption",
     "source": "assumption: flat-ground slip transferred from Yutu-2's Chang'e-4 measurement ... | Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip ratios are between 0 and -0.075' ... Nature Communications 2024 (PMC11258293) ..."},
    {"slope_deg": 15.0, "slip": 0.40, "sigma": 0.20, "kind": "design_constraint",
     "source": "VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' ... PSJ 2025 (10.3847/PSJ/add13f) sect. 3.5 and 3.2 ..."}
  ],
  "table": [
    {"slope_deg": 0.0,  "slip": 0.0375, "sigma": 0.0188, "time_energy_factor": 1.039, "within_slope_limit": true},
    {"slope_deg": 5.0,  "slip": 0.083,  "sigma": 0.041,  "time_energy_factor": 1.09,  "within_slope_limit": true},
    {"slope_deg": 10.0, "slip": 0.182,  "sigma": 0.091,  "time_energy_factor": 1.22,  "within_slope_limit": true},
    {"slope_deg": 15.0, "slip": 0.40,   "sigma": 0.20,   "time_energy_factor": 1.67,  "within_slope_limit": true},
    {"slope_deg": 20.0, "slip": 0.881,  "sigma": 0.44,   "time_energy_factor": 8.4,   "within_slope_limit": true},
    {"slope_deg": 25.0, "slip": 0.9,    "sigma": 0.45,   "time_energy_factor": 10.0,  "within_slope_limit": false}
  ],
  "references": [{"id": "viper_psj_2025", "title": "...", "url": "...", "used_for": "..."}, "..."]
},
"declared_only": {
  "...": "...",
  "regolith": {
    "site": "Chang'e-4 landing region, Von Karman crater (lunar far side)",
    "internal_friction_angle_deg": [21.5, 42.0], "cohesion_pa": [520, 3154],
    "sinkage_exponent": [0.87, 1.0], "mean_wheel_sinkage_mm": 8.0, "wheel_sinkage_range_mm": [5.0, 15.0],
    "bearing_strength_kpa": 4.0, "max_slope_driven_deg": 8.86, "slip_ratio_range": [-0.075, 0.0],
    "validity": "MEASURED at the Chang'e-4 site (far-side mare), not at the pole",
    "source": "Nature Communications 2024 (PMC11258293) ...", "read_by": "nothing"
  }
}
```

| Alan | Anlam |
|---|---|
| `slip_model.validity` | Her zaman `"MODEL"` (`"MEASURED"` asla). `applied` `false` ise profil eğri bildirmiyor demektir (katalogda böyle profil yok; elle kurulan profiller için). |
| `slip_model.anchors[*]` | `slope_deg`, `slip` (μ), `sigma` (σ, B2 için), `kind ∈ measured / measured_bound / design_constraint / assumption`, `source` (zorunlu; aktarılanlar `"assumption: "` ile başlar ve özgün kaynağı `|` sonrasında taşır). |
| `slip_model.table[*]` | Eğri 0/5/10/15/20/25°'de: `slip`, `sigma`, `time_energy_factor = 1/(1−slip)`, `within_slope_limit` (rover'ın `slope_max_deg`'i içinde mi). Yukarıdaki örnek VIPER (0° Yutu-2 aktarımı + 15° kendi kısıtı); Yutu-2'nin kendi eğrisi üç çapalı (0 / 8,86 / 15°), 20°'de kap. |
| `slip_model.claim`, `references` | İddia sınırı cümlesi ve dört kaynak (PSJ 2025, Nat. Comms 2024, Sci. Robotics 2022, Cunningham RSS 2017 — sonuncusu yalnızca kanca). |
| `declared_only.regolith` | Yutu-2: ölçülmüş Bekker-tipi aralıklar (Chang'e-4, kutup değil); VIPER: GRC-1 test yatağı (`simulant`, `relative_density_pct`, `validity: "GROUND_TEST …"`); LPR-1 / LUVMI-M `null`. `read_by: "nothing"` — hiçbir formül okumaz, referanstır. |

### `POST /api/plan`, `POST /api/plan-4d`, `/api/compare.results[*]`, `/api/plan-multi.results[*]` — `slip_model` bloğu

```json
"slip_model": {
  "applied": true,
  "validity": "MODEL",
  "model_id": "anchored_loglinear_v1",
  "route": {
    "moves": 40, "skipped_edges": 0,
    "mean_slip": 0.21, "max_slip": 0.62, "max_slip_slope_deg": 17.8,
    "distance_factor": 1.31,
    "extra_hours": 1.9, "extra_drawn_wh": 640.0
  },
  "claim": "Literature-anchored MODEL, not a measurement: ..."
}
```

| Alan | Anlam |
|---|---|
| `route.moves` | Sayılan sürüş kenarı (4-B: MOVE sayısı; 2-B: adım sayısı). `skipped_edges`: süresi sonlu olmayan kenarlar (normalde 0). |
| `route.mean_slip`, `max_slip`, `max_slip_slope_deg` | Mesafe ağırlıklı ortalama slip; en yüksek slip ve hangi eğimde. 4-B'de kenar eğimi iki kaba bloğun (blok-maks) ortalaması, 2-B'de sürülen eğim (`max(hücre, segment)`). |
| `route.distance_factor` | Σ d/(1−s) / Σ d — tekerleklerin yerden ne kadar fazla döndüğü. |
| `route.extra_hours`, `extra_drawn_wh` | Slip'in **bu rotaya** eklediği saat ve çekilen Wh (`t = t0/(1−s)` ⇒ eklenen `t·s`; enerji süreyle orantılı olduğundan `E·s`). Bir "slip'siz" yanıt üretmeden önce/sonra farkını verir. 4-B'de Wh, gölge küpünün iki bloktaki ortalama maruziyetiyle planlayıcının kendi kenar enerjisidir. |

**Ölçülen örnek (Site11, `docs/research/slip_calibration_report.md`):** LPR-1 28 Eyl 2026, (358,494)→(206,426), `/api/plan-4d`: varış 2,16 → 2,98 h (×1,38), en düşük SOC %96,2 → %92,5, `slip_model.route`: `mean_slip` 0,326, `max_slip` 0,537 @ 16,9°, `extra_hours` 0,75, `extra_drawn_wh` 321, `distance_factor` 1,53; otomatik dilim 0,0287 → 0,0359 h; B5 nominal en düşük SOC %97,9 → %94,5. Ay gecesi rotası 5,35 → 6,75 h (×1,26), SOC %72,7 → %67,4. **VIPER'ın standart haven→haven leg'i slip'li modelde 404** (283 148 kenar bataryayı %20 rezervin altına düşürürdü; haven kuralsız ve 24 h ufukla da 404) — slip'siz plan zaten %32 SOC'de bitiyor ve B5 koşumların yalnızca %1,4'ünü rezerv içinde buluyordu; en yakın uygulanabilir leg (358,494)→(346,462): 8 hamle, 1,53 → 2,23 h, SOC %85,4 → %72,3, SHERPA tam başarı %99,7 → %95,0. 2-B `/api/plan`: VIPER 4,33 → 5,40 h, 2 156 → 2 742 Wh (×1,27), SOC %67,2 → %57,6 (`extra_hours` 1,08, `extra_drawn_wh` 587); LPR-1 1,30 → 1,62 h, 469 → 597 Wh.

**Frontend'in çizebileceği (kod değişmeden):** rover kartında `slip_model.table`
(0–25° eğri; `within_slope_limit` dışı satırlar soluk) ve çapaların
`kind`/`source` etiketi; rota kartında `slip_model.route.extra_hours` ve
`extra_drawn_wh` ("slip'in payı") ile `mean_slip`; her sayının yanında
`validity: MODEL` etiketi (FRONTEND_YAPISI kuralı: etiketsiz gösterilmez).
`declared_only.regolith` bir "referans" sekmesi.

## Risk iştahı — CVaR tabanlı risk-farkında maliyet (5 Eylül 2026 eki, B2)

Bir hücrenin maliyeti artık isteğe bağlı olarak **dağılımın kuyruğundan** okunabilir.
C3 her slip çapasına bir `σ` koymuştu (`slip_stats(θ) → (μ, σ)`), B3 her hücreye
NASA'nın 100 DEM klonundan bir eğim belirsizliği `σ_θ` üretmişti; B2 bu iki dağılımın
"en kötü (1−α)'lık kuyruğunun ortalamasını" (Conditional Value-at-Risk,
`CVaR_α = μ + σ·φ(z_α)/(1−α)`) **sıralama maliyetine** bağlar. Yöntem JPL'in STEP'i
(Fan vd., RSS 2021; DARPA SubT'de sahada) ve Keio'nun Endo vd. ICRA 2023 çalışmasıdır;
Endo'nun "%11 → %95 başarı" sayıları **onların sentetik deneylerinden**dir, bizim etkimiz
Site11'de ölçülüdür ([risk_sweep_report.md](../research/risk_sweep_report.md)).

Kurallar:

- `risk_alpha` **verilmezse** (`null`) grid bugünkü grid ile **bit-eşittir** (v4;
  Site11'de SHA-256 kilidiyle test edilir). **α = 0,5 ortalama DEĞİLDİR**:
  `CVaR_0,5 = μ + 0,798σ`. Nominal = alan yok.
- α yalnızca **sıralamayı** değiştirir: eğim kriteri `min(slope_max, θ + σ_θ·m_α)`
  okur (`θ > slope_max → geçilmez` kapısı nominal θ'da kalır; geçilebilirlik α'dan
  bağımsız), enerji kriteri hücreyi `CVaR_α(slip)` ile fiyatlar (σ = C3 çapa yayılımı ⊕
  B3 eğim σ'sının delta yöntemiyle slip'e taşınması). **Süre, batarya, `path_battery_pct`,
  `safety_margins`, `/api/stress-test`, koridor bütçeleri, safe-haven süreleri ortalama
  slip fiziğidir** — aynı rota her α'da aynı saati verir.
- **İddia sınırı:** CVaR, `MODEL` etiketli dağılımların bir dönüşümüdür; "ölçülmüş risk"
  denmez. Slip σ'sı varsayımdır (Yutu-2 aralık/4; diğer çapalara aktarılmış bağıl yayılım
  0,5), eğim σ'sı NASA klonlarından DERIVED'dır, termal σ'nın kaynağı yoktur — termal
  CVaR **uygulanmadı** (kanca: `risk.thermal_cvar_cold_c`; Site11'de `f_thermal` zaten
  hücrelerin %73'ünde (LPR-1) / %54'ünde (VIPER) 0,99'a doymuş).
- Klon önbelleği yoksa eğim kriteri nominal kalır, slip kuyruğu yalnız C3 σ'sını taşır ve
  yanıt bunu söyler (`sigma_sources.slope.source: "none"`, `criteria.slope: "nominal"`).

### `POST /api/plan`, `POST /api/plan-4d` — yeni istek alanı `risk_alpha`

```json
{"start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426}, "rover_id": "lpr_1",
 "start_utc": "2026-09-28T00:00:00", "risk_alpha": 0.9}
```

| Alan | Anlam |
|---|---|
| `risk_alpha` | İsteğe bağlı, `[0.5, 0.999]`; dışı 422. Verilmezse nominal grid. `/api/compare` ve `/api/plan-multi` bu alanı almaz (görev profilleri nominal). |

### `POST /api/plan`, `POST /api/plan-4d` — `risk` bloğu (her zaman)

```json
"risk": {
  "alpha": 0.9, "applied": true, "validity": "MODEL",
  "measure": "cvar_normal_closed_form_v1", "multiplier": 1.755,
  "scope": "ranking cost only: ...; travel time, battery, safety margins ... use the mean ...",
  "criteria": {"slope": "cvar", "energy": "cvar"},
  "sigma_sources": {
    "slip":  {"source": "C3 anchors: sigma per anchor (Yutu-2's measured 0..0.075 range read as +-2 sigma; ...) plus the slope sigma carried into slip by the delta method", "validity": "MODEL",
              "relative_spread_at_anchors": [{"slope_deg": 0.0, "sigma_over_mu": 0.5}, {"slope_deg": 15.0, "sigma_over_mu": 0.5}]},
    "slope": {"source": "dem_clones", "model": "pgda_clones", "n_clones": 100, "validity": "DERIVED", "product_url": "https://pgda.gsfc.nasa.gov/products/78"}
  },
  "route": {
    "moves": 42, "skipped_edges": 0,
    "mean_slip_mu": 0.313, "mean_slip_cvar": 0.51, "max_slip_cvar": 0.9, "max_slip_cvar_slope_deg": 16.9,
    "max_slope_cvar_deg": 19.6, "slope_sigma_known_fraction": 1.0,
    "hours": 2.23, "risk_adjusted_hours": 3.4, "hours_factor": 1.52,
    "drawn_wh": 970.0, "risk_adjusted_drawn_wh": 1480.0
  },
  "claim": "CVaR of MODEL-labelled distributions, not a measured risk: ..."
}
```

| Alan | Anlam |
|---|---|
| `alpha`, `applied`, `multiplier` | İstenen α (`null` = nominal, `applied: false`, `route: null`); `multiplier = φ(z_α)/(1−α)` (0,5 → 0,798; 0,9 → 1,755; 0,99 → 2,665). |
| `criteria` | Hangi kriter kuyruğu okudu: `slope` yalnızca eğim σ (klon önbelleği) varken `"cvar"`, aksi hâlde `"nominal"`; `energy` α verildiyse `"cvar"`. |
| `sigma_sources.slip` | C3 çapalarının bağıl yayılımı (varsayım) + delta yöntemi; `validity: MODEL`. Eğrisiz profilde `"none: ..."`. |
| `sigma_sources.slope` | `"dem_clones"` (B3; `model`, `n_clones`, `validity: DERIVED`) ya da `"none"` (+ `reason`). |
| `route.mean_slip_mu`, `mean_slip_cvar`, `max_slip_cvar`, `max_slip_cvar_slope_deg` | Rotanın ortalama slip'i (μ, mesafe ağırlıklı) ve aynı rotanın α'daki CVaR slip'i; en yüksek kuyruk slip'i ve eğimi (kap 0,9). |
| `route.max_slope_cvar_deg`, `slope_sigma_known_fraction` | Rota boyunca eğim kuyruğunun maksimumu (rover'ın `slope_max_deg`'inde kapalı; σ yoksa nominal maks); σ'sı bilinen kenar oranı. |
| `route.hours` → `risk_adjusted_hours`, `hours_factor`; `drawn_wh` → `risk_adjusted_drawn_wh` | Rotanın **ortalama-slip sürüş saati/Wh'si** ve aynı rotanın kuyruk slip'iyle yeniden fiyatlanmış hâli (`t_α = t·(1−μ)/(1−s_α)`). Planlayıcının saati değişmez; bu "kuyrukta ne kadar zaman/enerji satın alındı" sorusunun cevabıdır. 4-B'de Wh gölge küpünün ortalama maruziyetiyle, 2-B'de simülasyonun `step_energy_wh`'siyle. |
| `scope`, `claim`, `validity` | Nereye girdiği; iddia sınırı; her zaman `MODEL`. |

### `POST /api/risk-sweep` — risk iştahı sürgüsü (2-B, yan yana)

```json
{"start": {"row": 358, "col": 494}, "goal": {"row": 206, "col": 426}, "rover_id": "lpr_1",
 "alphas": [0.5, 0.9, 0.99], "include_nominal": true}
```

```json
{
  "start": [358, 494], "goal": [206, 426], "rover_id": "lpr_1", "planner": "2d",
  "alphas": [null, 0.5, 0.9, 0.99],
  "results": [
    {"risk_alpha": null, "error": null, "waypoints": [{"row": 358, "col": 494, "...": "..."}],
     "summary": {"total_distance_km": 0.91, "total_elapsed_hours": 1.62, "total_energy_consumed_wh": 597.2, "min_battery_pct": 94.3, "...": "..."},
     "astar_metrics": {"...": "..."}, "slip_model": {"...": "..."}, "risk": {"alpha": null, "applied": false, "...": "..."},
     "overlap_with_nominal": 1.0, "plan_ms": 420.0},
    {"risk_alpha": 0.99, "...": "...", "overlap_with_nominal": 0.49, "plan_ms": 290.0}
  ],
  "risk_matrix": {"route_alphas": [null, 0.5, 0.9, 0.99], "eval_alphas": [0.5, 0.9, 0.99],
                  "risk_adjusted_hours": [[1.9, 2.4, 3.1], "..."], "mean_slip_cvar": ["..."], "max_slope_cvar_deg": ["..."]},
  "comparison": {"nominal": {"distance_km": 0.91, "hours": 1.62, "energy_wh": 597.2, "min_battery_pct": 94.3, "mean_slip": 0.175, "max_slip": 0.586},
                 "deltas": [{"risk_alpha": 0.5, "distance_km": 0.0, "hours": -0.003, "energy_wh": -1.4, "min_battery_pct": 0.01, "mean_slip": -0.0001, "max_slip": -0.023, "overlap_with_nominal": 0.81}, "..."],
                 "evaluated_at_alpha": 0.99, "lowest_risk_adjusted_hours_alpha": 0.99, "lowest_risk_adjusted_hours": 2.9},
  "validity": "MODEL", "measure": "cvar_normal_closed_form_v1", "sigma_sources": {"...": "..."},
  "claim": "...", "note": "risk_alpha omitted (null) is the nominal grid ...; alpha = 0.5 is mu + 0.798 sigma, NOT the mean ...", "references": ["..."]
}
```

| Alan | Anlam |
|---|---|
| `alphas` (istek) | 1–6 değer, her biri `[0.5, 0.999]`; tekrarlar atılır, sıra korunur. `include_nominal` (varsayılan `true`) nominal rotayı da ekler. |
| `results[*]` | Her α için 2-B plan + simülasyon: `waypoints` (`/api/plan`'ın `waypoints` biçimi), `summary` (kendi rotasının **ortalama-slip fiziği**), `astar_metrics`, `slip_model`, `risk`, `overlap_with_nominal` (hücre Jaccard'ı; nominal yoksa `null`), `plan_ms`. Rota bulunamazsa `error` dolu, `waypoints: []`. |
| `risk_matrix` | Her rota (satır, `route_alphas`) her α'da (sütun, `eval_alphas`) yeniden fiyatlanır: `risk_adjusted_hours`, `mean_slip_cvar`, `max_slope_cvar_deg`. "α rotası kuyrukta gerçekten bir şey satın aldı mı?" sorusu aynı zeminde cevaplanır. |
| `comparison` | Nominal rotanın metrikleri ve her α rotasının nominale göre Δ'sı (mesafe, saat, Wh, min SOC, ort./maks slip, örtüşme); `lowest_risk_adjusted_hours_alpha`: en yüksek α'da en düşük risk-ayarlı saati taşıyan rota (`null` = nominal). `include_nominal: false` ya da nominal rota yoksa `null`. |
| `planner` | Her zaman `"2d"`; 4-B için `/api/plan-4d`'ye `risk_alpha` verilir. |

**Ölçülen örnek (Site11, [risk_sweep_report.md](../research/risk_sweep_report.md)):** eğim σ_θ medyanı 1,54° (100 NASA klonu); α = 0,99'da CVaR slip medyanı 0,20 → 0,50, hücrelerin %27'si 0,9 kapısında, maliyet sıralaması nominale Spearman 0,985 (LPR-1). `/api/risk-sweep` LPR-1 (358,494)→(206,426): α = 0,99 rotası nominalle %49 örtüşüyor, tüketim 597 → 593 Wh, maks slip 0,586 → 0,563, min SOC +0,07 pt; risk matrisi α = 0,99'da nominal rotanın risk-ayarlı sürüş saatini 3,38 h, α = 0,99 rotasınınkini 3,70 h veriyor (kuyrukta nominal daha ucuz — ağırlıklı kriterler kuyruk süresini minimize etmez). Ay gecesi çifti: −26 Wh, +18 m, min SOC +0,39 pt, kuyrukta α rotası kazanıyor (5,53 vs 5,56 h). VIPER kısa leg: α rotası maks slip'i **yükseltiyor** (0,594 → 0,627). 4-B (`/api/plan-4d`, coarsen 4): LPR-1 28 Eyl α ∈ {0,5, 0,9, 0,99} aynı 42 hamlelik rotayı seçiyor (nominal 41, örtüşme %55), varış 2,98 h aynı, min SOC %92,5 → %93,1, B5 tamamlanma %100 aynı; VIPER kısa leg her α'da aynı rota. Etki **küçük** ve öyle gösterilmeli; sayılar `MODEL` etiketlidir.

**Frontend'in çizebileceği (kod değişmeden):** rota panelinde bir "risk iştahı" sürgüsü
(`null` / 0,5 / 0,9 / 0,99) → `/api/risk-sweep` sonuçlarını üst üste çizip
`comparison.deltas`'ı ve `risk_matrix`'i tablo olarak göstermek; her rota kartında
`risk.route.mean_slip_cvar` ve `risk_adjusted_hours` ("kuyrukta +X h") ile
`criteria`/`sigma_sources` etiketleri; her sayının yanında `validity: MODEL`
(FRONTEND_YAPISI kuralı). Sürgüde 0,5'i "nominal" diye etiketlemeyin — nominal `null`'dır.

## Değişmeyenler

`fetchLayer`, `/api/plan`, `/api/plan-4d` (mevcut alanları), `/api/cell-telemetry`,
`/api/profiles`, `/api/rovers` — hepsi aynen. `format` opsiyonel ve
varsayılanı `json`.
