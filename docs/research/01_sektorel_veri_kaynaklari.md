# 01 — Sektörel Projelerde Veriler

> **Soru:** Gerçek Ay/gezegen yüzey projeleri hangi veriyi, hangi formatta, hangi disiplinle kullanıyor? LunaPath bunun neresinde?
>
> **Kısa cevap:** LunaPath bugün **tek bir DEM'den türetilmiş 7 katman** kullanıyor ve bunların 2'si (termal, gölge) fiziksel ölçüm değil, elevasyondan uydurulmuş proxy. Sektör ise **çok kaynaklı, sürümlenmiş, izlenebilir, belirsizliği nicelenmiş** veri kullanıyor — ve bu verinin neredeyse tamamı halka açık ve ücretsiz. Boşluk teknik yetenek değil, **veri disiplini** boşluğudur.

---

## 1. LunaPath'in mevcut veri durumu (dürüst envanter)

| Katman | Kaynak | Gerçek ölçüm mü? | Dosya |
|---|---|---|---|
| `elevation_grid` | LOLA `LDEM_80S_80MPP_ADJ` | ✅ Evet (altimetri) | `process_lunar_data.py:45` |
| `slope_grid` | `np.gradient(elevation)` | 🟡 Türetilmiş (yöntem bağımlı) | `process_lunar_data.py:132` |
| `aspect_grid` | `np.gradient(elevation)` | 🟡 Türetilmiş | `process_lunar_data.py:139` |
| `shadow_ratio_grid` | `1 - elev_norm` | ❌ **Proxy — fiziksel temeli yok** | `process_lunar_data.py:148` |
| `thermal_grid` | Elevasyon + aspect + komşu farkı | ❌ **Sentetik** | `backend/app/thermal_grid.py` |
| `traversability_grid` | slope > 25° veya T < −150 °C | 🟡 Kural tabanlı | `backend/app/traversability.py` |
| `cost_grid` | 4 penalty ağırlıklı toplam | 🟡 Model çıktısı | `backend/app/cost_engine.py:296` |

**Kritik gözlem:** Zincirin **tamamı tek bir girdiden** (elevasyon) türüyor. Bu, katmanlar arasında yapay bir korelasyon üretir: `shadow_ratio` ve `thermal` matematiksel olarak `elevation`'ın monoton fonksiyonlarıdır. Yani maliyet fonksiyonunda 4 bağımsız kriter varmış gibi görünse de, gerçekte **~2 bağımsız bilgi kanalı** (elevasyon ve eğim) vardır. Bu, AHP ağırlıklarının anlamını zayıflatır ve "4 profil neden benzer rota üretiyor?" sorusunun (`referans_belgesi_2.md` §11'de not edilmiş) asıl nedenidir.

> **Bu, çözülmesi gereken 1 numaralı veri problemidir.** Ağırlıkları oynatmak çözmez; bağımsız veri kanalı eklemek çözer.

---

## 2. Sektör gerçek misyonlarda ne kullanıyor?

### 2.1 Ay güney kutbu için fiili standart veri yığını

Artemis dönemi iniş bölgesi analizlerinde (ör. Artemis III aday bölge çalışmaları) tekrar tekrar aynı dörtlü kullanılıyor:

| Ürün | Çözünürlük | Ne için | Erişim |
|---|---|---|---|
| **LOLA LDEM (kutup)** | 20 m/px (85°S–90°S), 10/40/60/120/240 m çeşitleri | Topografya, eğim, ufuk hattı | PDS Geosciences / PGDA |
| **LOLA 5 m/px site DEM'leri** | 5 m/px, 27 aday bölge | Yüksek çözünürlük yerel analiz | [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) |
| **SfS 5 m/px SDEM'ler** | 5 m/px, 13 Artemis III bölgesi, >4500 km² | LOLA iz aralarını doldurma | [PGDA #104](https://pgda.gsfc.nasa.gov/products/104) |
| **LROC NAC kutup mozaiği** | ~1 m/px | Kaya/krater tespiti, hazard | LROC / USGS Astropedia |
| **LROC WAC** | 100 m/px | Bağlam, hillshade | LROC |
| **LOLA illumination / PSR** | 240 m (→65°), 120 m (→75°), 60 m (→85°), PSR 20 m | Aydınlanma oranı, kalıcı gölge | [imbrium.mit.edu ILLUMINATION](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION) |
| **Diviner tbol / treg / rock abundance** | 128 ppd (~250 m ekvatorda) | Yüzey sıcaklığı, termal atalet | PDS4 `urn:nasa:pds:lro_diviner_derived1` |
| **CRaTER** | Yörünge zaman serisi | Radyasyon ortamı | PDS / LRO |

**Doğruluk figürleri (PGDA 5 m/px ürünleri, LunaPath'in belirsizlik bütçesi için kullanılabilir):**
- Medyan RMS yükseklik hatası: **0.30–0.50 m**
- Medyan RMS eğim hatası: **1.5–2.5°**
- İz geolokasyon belirsizliği: yatay ~10–20 cm, düşey ~2–4 cm
- Her site için **100 "clone" dosyası** (istatistiksel topluluk) → belirsizlik yayılımı için doğrudan kullanılabilir

> **Bu son madde LunaPath için altın değerinde.** 100 clone ile Monte Carlo koşup "rota, DEM belirsizliği altında ne kadar kararlı?" sorusuna sayısal cevap verebilirsiniz. Hiçbir hackathon projesi bunu yapmaz; jüri/hakem için bu tek başına ayırt edici bir kanıttır.

### 2.2 Eğimin "türetilmiş" olması bir detay değil

`np.gradient` (2. mertebe merkezi fark) eğimi **düzleştirir**. Sektörde eğim, misyon gereksinimine bağlı olarak farklı **baseline**'larda hesaplanır:

- **Rover tekerlek tabanı ölçeği** (~1–2 m): devrilme ve tırmanma limiti için
- **Araç boyu ölçeği** (~2–5 m): gövde açıklığı için
- **Bölgesel ölçek** (~20–100 m): enerji ve rota için

LunaPath 80 m'de tek bir eğim üretiyor ve bunu 25° hard-limit ile karşılaştırıyor. **80 m baseline'da 25° eğim, 2 m baseline'da 40°+ olabilir.** Yani mevcut `traversable` maskesi sistematik olarak **iyimser**.

**Reçete:** Eğimi tek sayı olarak değil, **ölçek-bağımlı üçlü** olarak üretin:

```python
# lunapath/src/slope_multiscale.py (yeni)
def slope_at_baseline(elev, res_m, baseline_m):
    """Belirtilen baseline'da eğim (derece). Adyacent-point yerine
    baseline ölçeğinde sonlu fark kullanır."""
    k = max(1, int(round(baseline_m / res_m)))
    dz_dy = (elev[2*k:, :] - elev[:-2*k, :]) / (2 * k * res_m)
    dz_dx = (elev[:, 2*k:] - elev[:, :-2*k]) / (2 * k * res_m)
    # ... pad + birleştir
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy)))

SLOPE_BASELINES_M = {"vehicle": 5.0, "regional": 80.0}
```

80 m DEM'de `vehicle` baseline'ı **hesaplanamaz** — bu da tam olarak 5 m/px ürüne geçme gerekçenizdir. Bunu belgeleyin: "80 m veride araç ölçeği eğim gözlemlenemez, bu nedenle traversability alt-tahminlidir."

---

## 3. Sektörel veri disiplini: LunaPath'te olmayan 7 pratik

Gerçek projelerde veriyi "indir ve kullan" değil, **yönetilen bir varlık** olarak ele alırlar. ECSS'in yazılım (ECSS-E-ST-40C), ürün güvencesi (ECSS-Q-ST-80C) ve makine öğrenmesi (ECSS-E-HB-40-02A, 15 Kasım 2024) belgeleri bunu şart koşar.

### 3.1 Veri kaynağı künyesi (provenance)

**Sektörde:** Her ürün için mission/instrument/product ID, sürüm, DOI, üretim tarihi, işleme seviyesi (raw/calibrated/derived) kayıtlı.

**LunaPath'te:** `metadata.json` sadece origin/resolution/shape/crs tutuyor. Kaynak dosya adı bile yok.

**Reçete — `metadata.json` v2 şeması:**

```json
{
  "schema_version": "2.0",
  "generated_utc": "2026-08-10T12:00:00Z",
  "generator": { "script": "process_lunar_data.py", "git_sha": "3e22809" },
  "grid": {
    "shape": [500, 500], "resolution_m": 80.0,
    "crs_wkt": "PROJCS[\"Moon (2015) - Sphere ... \"]",
    "origin": { "x": 176000.0, "y": 48000.0 },
    "window_offset": { "row": 3200, "col": 6000 },
    "nodata": "NaN"
  },
  "sources": [
    {
      "layer": "elevation",
      "product_id": "LDEM_80S_80MPP_ADJ",
      "instrument": "LRO/LOLA",
      "processing_level": "derived",
      "native_resolution_m": 80.0,
      "archive": "PDS Geosciences Node",
      "doi": null,
      "sha256": "<dosya hash'i>",
      "license": "Public domain (NASA)",
      "retrieved_utc": "2026-07-01T00:00:00Z"
    },
    {
      "layer": "thermal",
      "product_id": "SYNTHETIC:elevation_aspect_proxy_v1",
      "instrument": null,
      "processing_level": "model",
      "physical_validity": "NOT_MEASURED",
      "model_ref": "docs/lunapath_referans_belgesi_2.md#32",
      "known_limitations": [
        "ray-tracing yok", "horizon masking yok",
        "zamana bağlı değişim yok", "elevasyonla yapay korelasyon"
      ]
    }
  ],
  "uncertainty": {
    "elevation_rms_m": null,
    "slope_rms_deg": null,
    "note": "80 m ürün için resmi belirsizlik yayınlanmadı; 5 m ürünlerde 0.30-0.50 m / 1.5-2.5 deg"
  }
}
```

`physical_validity: "NOT_MEASURED"` alanı **kritik**: sentetik olanı sentetik olarak işaretlemek, projeyi zayıflatmaz, güvenilir yapar. Frontend bunu okuyup katman üstünde "SENTETİK" badge'i gösterebilir.

### 3.2 Sürümleme ve tekrar-üretilebilirlik

**Sektörde:** Aynı girdi + aynı kod = bit-bit aynı çıktı. Ürünler `v1.0`, `v1.1` olarak arşivlenir, eski sürümler silinmez.

**LunaPath'te:** `process_lunar_data.py` her koşumda `data/processed/*.npy` üzerine yazıyor. Hangi sürümle üretildiği kayıtlı değil. `find_action_window()` deterministik ama bu hiçbir yerde iddia edilmemiş.

**Reçete:**
- Çıktı dizinini içeriğe göre adlandır: `data/processed/<dem_sha8>_<res>m_<win_r>_<win_c>/`
- `metadata.json`'a `git_sha` yaz
- CI'da "aynı girdi → aynı hash" testi (regression guard):

```python
# backend/test_pipeline_determinism.py (yeni)
def test_pipeline_is_deterministic(tmp_path):
    a = run_pipeline(SMALL_FIXTURE_DEM)
    b = run_pipeline(SMALL_FIXTURE_DEM)
    for k in a: assert np.array_equal(a[k], b[k], equal_nan=True)
```

- Büyük ikili dosyalar için **DVC** veya **git-lfs**; `.npy` dosyaları repoya girmemeli (`.gitignore` kontrolü yapın).

### 3.3 Katman hizalama sözleşmesi (alignment contract)

**Sektörde:** Farklı enstrümanlardan gelen ürünler tek bir "reference frame + projection + grid" üzerine resample edilir; her adım loglanır.

`docs/ay_termal_navigasyon_proje_dokumani.md` §10.1 Risk 2 bu riski zaten tanımlamış ama kod bunu **doğrulamıyor** — çünkü tek kaynak var, hizalama sorunu henüz doğmadı. Diviner ve illumination ekleyince **hemen** doğacak:

- LOLA 80 m: polar stereographic, MOON_ME, R = 1737400 m küre
- Diviner GHRM: 128 ppd **silindirik (cylindrical)** projeksiyon, 70°S–70°N → **kutup için ayrı kutup ürünü gerekir**
- Illumination: polar stereographic ama 60/120/240 m

**Reçete — hizalama kapısı (gate):**

```python
# lunapath/src/align.py (yeni)
REQUIRED = ("crs_wkt", "resolution_m", "shape", "origin")

def assert_aligned(*metas):
    ref = metas[0]
    for m in metas[1:]:
        for k in REQUIRED:
            if m[k] != ref[k]:
                raise ValueError(f"Hizalama ihlali: {k}: {m[k]} != {ref[k]}")

def reproject_to_reference(src_path, ref_meta, resampling):
    """rasterio.warp.reproject ile referans grid'e getir.
    Kategorik maskeler (PSR, traversable) icin nearest,
    surekli alanlar (T, illumination) icin bilinear."""
```

**Resampling kuralı** (sık yapılan hata): PSR maskesini bilinear ile resample ederseniz 0.37 gibi anlamsız değerler çıkar. Kategorik → `nearest`; sürekli → `bilinear`/`cubic`; **downsampling'de sürekli alanlar için `average`** (rasterio `Resampling.average`), çünkü nokta örnekleme aliasing üretir. Mevcut kodda `find_action_window` doğru şekilde `Resampling.average` kullanıyor (`process_lunar_data.py:75`) — bu iyi, aynı disiplini diğer katmanlara taşıyın.

### 3.4 Belirsizlik bütçesi

**Sektörde:** Her katmanın hatası nicelenir ve karar zincirinde yayılır. "Eğim 24.8°" değil, "eğim 24.8° ± 2.1°" denir.

**LunaPath'te:** Hiç yok. 25° hard-limit, hatasız bir ölçüm varsayıyor. RMS eğim hatası 1.5–2.5° ise, 25° limitine **±2.5° bant** eklemek zorunludur.

**Reçete — üç bölgeli karar:**

| Durum | Kural |
|---|---|
| `slope + 2σ < 25°` | Geçilebilir (yüksek güven) |
| `slope - 2σ < 25° ≤ slope + 2σ` | **Belirsiz** → yüksek maliyet + "yerel doğrulama gerekli" bayrağı |
| `slope - 2σ ≥ 25°` | Geçilemez |

Bu, ikili maskeyi **üçlü** yapar ve `traversability.py`'de tek satırlık bir değişikliktir ama savunulabilirlik açısından büyük bir sıçramadır. Mars 2020 ENav'ın ACE (Approximate Clearance Evaluation) algoritması tam olarak bu mantıkla çalışır: kesinlik yerine **clearance/güvenlik payı** değerlendirir.

### 3.5 Veri sözleşmesi (data contract) — modüller arası

`ay_termal_navigasyon_proje_dokumani.md` §12 "erken sabitlenmesi gerekenler" listesi doğru ama şema olarak yazılmamış. Sektörde bu bir **makine-okunabilir şemadır** (JSON Schema / Pydantic / Protobuf).

**Reçete:** `backend/app/schemas.py` (yeni) — tüm grid'ler için tek doğrulayıcı:

```python
from pydantic import BaseModel, Field
from typing import Literal

class LayerSpec(BaseModel):
    name: str
    dtype: Literal["float32", "float64", "bool", "uint8"]
    units: str                      # "m", "deg", "degC", "dimensionless", "bool"
    valid_min: float | None
    valid_max: float | None
    nodata: Literal["nan", "sentinel", "mask"]
    physical_validity: Literal["MEASURED", "DERIVED", "MODEL", "NOT_MEASURED"]

LAYER_SPECS = {
  "elevation":    LayerSpec(name="elevation", dtype="float64", units="m",
                            valid_min=-10000, valid_max=10000, nodata="nan",
                            physical_validity="MEASURED"),
  "slope":        LayerSpec(name="slope", dtype="float64", units="deg",
                            valid_min=0, valid_max=90, nodata="nan",
                            physical_validity="DERIVED"),
  "thermal":      LayerSpec(name="thermal", dtype="float64", units="degC",
                            valid_min=-250, valid_max=130, nodata="nan",
                            physical_validity="NOT_MEASURED"),
  # ...
}

def validate_layer(name, arr):
    spec = LAYER_SPECS[name]
    assert str(arr.dtype) == spec.dtype, f"{name}: dtype {arr.dtype}"
    finite = arr[np.isfinite(arr)]
    if spec.valid_min is not None:
        assert finite.min() >= spec.valid_min, f"{name}: min {finite.min()}"
    # ...
```

Bu, `print_validation()`'ın (`process_lunar_data.py:250`) **yazdırmak** yerine **kırmak** (fail) versiyonudur. Şu an validasyon konsola bakan insana güveniyor; CI'ya güvenmeli.

### 3.6 Birim ve işaret konvansiyonu

Sektörde en pahalı hatalar birim hatalarıdır (Mars Climate Orbiter, 1999). LunaPath'te riskli noktalar:

| Alan | Şu anki durum | Risk |
|---|---|---|
| Sıcaklık | °C (`thermal_grid`) | Ay literatürünün **tamamı Kelvin** kullanır. Diviner ürünleri K. Çeviri hatası kaçınılmaz. |
| Aspect | 0°=Kuzey, saat yönü | Ay güney kutbunda "kuzey" = kutuptan dışa. Güneş azimutu ile karıştırma riski yüksek. |
| Gölge | `shadow_ratio` [0,1] boyutsuz **ama** `f_shadow(H_hours)` saat bekliyor | İki farklı büyüklük aynı isimle dolaşıyor |

**Reçete:**
1. **İç temsilde Kelvin'e geçin**, sadece UI'da °C gösterin. `constants.py`'de `BAT_OP_MIN_K = 273.15` vb.
2. Değişken isimlerine birim ekleyin: `shadow_ratio_dimensionless`, `shadow_hours_cum_h`. `cost_engine.py`'de `edge_shadow_hours` zaten doğru adlandırılmış — bu deseni her yere yayın.
3. Aspect için açık bir docstring: "0° = grid-kuzeyi (+row azalan yön), saat yönünde artar, güneş azimutu ile aynı referans değildir."

### 3.7 Lisans ve atıf

NASA PDS ürünleri kamu malı ancak **atıf beklenir**; bazı türev ürünler (ör. Zenodo'daki SfS SDEM'ler) CC lisanslıdır ve DOI ile atıf zorunludur. Kaguya/JAXA ürünlerinin ayrı kullanım koşulları vardır.

**Reçete:** `docs/DATA_LICENSES.md` (yeni) — her ürün için satır: ürün, sağlayıcı, lisans, atıf metni, DOI, indirme tarihi. README'deki "*Uzay verilerinin lisans ve kullanım koşullarına uygun kullanın*" uyarısı iyi bir niyet beyanı ama **uygulanabilir bir kayıt değil**.

---

## 4. Boşluk analizi ve öncelikli yol haritası

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| G1 | Tüm katmanlar tek girdiden türüyor (yapay korelasyon) | 🔴 Çok yüksek — maliyet fonksiyonunun anlamı zayıf | Orta | **P0** |
| G2 | Termal veri sentetik | 🔴 Çok yüksek — projenin ana iddiası | Orta | **P0** |
| G3 | Gölge modeli fiziksel değil | 🔴 Yüksek | Düşük | **P0** |
| G4 | Provenance / sürümleme yok | 🟠 Yüksek (savunulabilirlik) | Düşük | **P0** |
| G5 | Belirsizlik bütçesi yok | 🟠 Yüksek | Orta | P1 |
| G6 | Eğim tek ölçekte, iyimser | 🟠 Orta-yüksek | Orta | P1 |
| G7 | Hizalama doğrulaması yok | 🟠 Orta (yeni veri gelince kritik) | Düşük | P1 |
| G8 | Şema/validasyon CI'da kırmıyor | 🟡 Orta | Düşük | P1 |
| G9 | Kelvin/°C karmaşası | 🟡 Orta | Düşük | P1 |
| G10 | Lisans kaydı yok | 🟡 Düşük-orta | Çok düşük | P2 |

### P0 paketi — "veriyi gerçek yap" (tahmini 2–3 gün, 1 kişi)

1. **Diviner tbol kutup ürününü indir ve hizala** → `thermal_grid`'i gerçek ölçümle değiştir, sentetiği `thermal_grid_synthetic.npy` olarak yanında tut (ablasyon için gerekli, bkz. [03](03_sentetik_minimum_veri.md)).
2. **LOLA illumination/PSR ürününü indir ve hizala** → `shadow_ratio`'yu gerçek average-illumination ile değiştir.
3. **`metadata.json` v2 şemasına geç** (§3.1) — `physical_validity` alanı dahil.
4. **`assert_aligned` kapısını ekle** ve pipeline'da çağır.
5. **Korelasyon raporu üret:** 7 katmanın çift-yönlü Pearson/Spearman matrisi. Hedef: `|corr(thermal, elevation)| < 0.8`. Bugün bu değer ~1.0'a yakın olmalı (kodda zaten `generate_thermal_grid` doğrudan `elev_norm`'dan türüyor); gerçek Diviner ile 0.4–0.7 bandına düşmesi beklenir.

**Kabul kriteri:** `python lunapath/src/process_lunar_data.py` çalıştığında, çıktı `metadata.json` içinde en az 3 farklı `instrument` değeri (`LRO/LOLA`, `LRO/Diviner`, `LRO/LOLA-illumination`) bulunması ve korelasyon matrisinin `docs/` altına yazılması.

### P1 paketi — "veriyi savunulabilir yap" (tahmini 3–4 gün)

6. Çok ölçekli eğim (§2.2) + belirsizlik bandı (§3.4) → üçlü traversability
7. `schemas.py` + CI'da kıran validasyon
8. Kelvin geçişi
9. 100-clone Monte Carlo ile rota kararlılığı raporu (5 m/px bölgeye geçilirse)

### P2 paketi — "veriyi ölçeklenebilir yap"

10. DVC/git-lfs, `DATA_LICENSES.md`, çok bölgeli senaryo kütüphanesi (Shackleton, Nobile, de Gerlache, Malapert), tile-tabanlı işleme (bellek sınırı için)

---

## 5. Somut indirme rehberi

> Dosya adları ve yollar zamanla değişebilir; her indirmede `sha256` ve tarih kaydedin.

| İhtiyaç | Nereden | Not |
|---|---|---|
| Kutup DEM 20 m | PDS Geosciences LOLA RDR / [PGDA #81](https://pgda.gsfc.nasa.gov/products/81) (South Pole LOLA DEM Mosaic) | Mevcut 80 m'den 4× iyi; hesap yükü 16× |
| Site DEM 5 m + **100 clone** | [PGDA #78](https://pgda.gsfc.nasa.gov/products/78) | 27 site; GeoTIFF; belirsizlik ürünleri dahil |
| SfS SDEM 5 m (13 bölge) | [PGDA #104](https://pgda.gsfc.nasa.gov/products/104), Zenodo `10.5281/zenodo.17954508` | Eleve + hillshade + ortomozaik + eğim + roughness |
| Aydınlanma & PSR | [imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION) | 60/120/240 m; hem Güneş hem **Dünya** aydınlanması (iletişim penceresi için!) |
| PSR 20 m (en yeni) | Barker vd. 2023, [A New View of the Lunar South Pole from LOLA](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1) / [PGDA #90](https://pgda.gsfc.nasa.gov/products/90) | Belirsizlik tahminleri ile |
| Diviner sıcaklık | PDS4 bundle `urn:nasa:pds:lro_diviner_derived1`, DOI `10.17189/wj0s-w188` | Detay: [07](07_termal_veri.md) |
| SLDEM2015 (global bağlam) | [PGDA #54](https://pgda.gsfc.nasa.gov/products/54) | LOLA+Kaguya TC birleşik, 59 m/px |
| LROC NAC / WAC | LROC arşivi, USGS Astropedia | Detay: [02](02_goruntu_isleme.md) |

**Dünya aydınlanma katmanı gözden kaçmasın:** LunaPath'in bugünkü modelinde iletişim/veri indirme kısıtı yok. Kutupta Dünya görünürlüğü topografyaya bağlıdır ve gerçek görev planlamasında **birinci sınıf kısıttır** (komut alma, telemetri gönderme). Bu, maliyet fonksiyonuna 5. bir kriter olarak eklenebilecek, veri olarak **hazır bekleyen** bir ayırt edici özelliktir.

---

## 6. Sektörel veri disiplinini standarda bağlama

Akademik/jüri savunması için "biz keyfimize göre değil, standarda göre yaptık" demek güçlüdür:

| Standart | İlgili kısım | LunaPath'te karşılığı |
|---|---|---|
| **PDS4** | Ürün etiketleme, `Product_Observational`, birim sözlüğü | `metadata.json` v2'yi PDS4 alan adlarına yakın tutun |
| **ECSS-E-ST-40C** | Yazılım gereksinim/tasarım/V&V yaşam döngüsü | Modül contract'ları, test piramidi |
| **ECSS-Q-ST-80C** | Yazılım ürün güvencesi | Kritiklik sınıfı beyanı |
| **ECSS-E-HB-40-02A** (15 Kas 2024) | **ML nitelendirme el kitabı** — veri hazırlama, temsil edicilik, V&V, kritiklik B/C/D, "safety cage" mimarisi | ML eklerseniz zorunlu okuma → [04](04_acik_kaynak_modeller.md) |
| **ISO 19115 / OGC** | Coğrafi metadata | CRS/WKT kaydı |

> ECSS ML el kitabı **sentetik veriyi yasaklamaz**; veri seçiminin gerekçelendirilmesini, temsil ediciliğin gösterilmesini ve AI bileşeninin etrafına deterministik bir "safety cage" konmasını ister. LunaPath'in hard-constraint + log-barrier yapısı zaten bir safety cage'in embriyosudur — bunu bu isimle anlatmak, mimariyi standarda bağlar.

---

## 7. Kabul kriterleri (bu belgenin "bitti" tanımı)

- [ ] `metadata.json` v2 şeması yürürlükte, en az 3 bağımsız enstrüman kaynağı listeli
- [ ] Hiçbir katman `physical_validity: NOT_MEASURED` değilken "gerçek veri" olarak sunulmuyor (UI badge dahil)
- [ ] `assert_aligned` + `validate_layer` CI'da kırıyor
- [ ] Katman korelasyon matrisi üretiliyor ve `|corr(thermal, elevation)| < 0.8`
- [ ] `docs/DATA_LICENSES.md` mevcut
- [ ] Pipeline determinizm testi geçiyor
- [ ] Eğim ve traversability belirsizlik bandıyla üçlü

---

## Kaynaklar

- [High-Resolution LOLA Topography for Lunar South Pole Sites — PGDA #78](https://pgda.gsfc.nasa.gov/products/78)
- [Enhanced Topography Models with Shape-from-Shading — PGDA #104](https://pgda.gsfc.nasa.gov/products/104)
- [South Pole LOLA DEM Mosaic — PGDA #81](https://pgda.gsfc.nasa.gov/products/81)
- [A New View of the Lunar South Pole from LOLA — PGDA #90](https://pgda.gsfc.nasa.gov/products/90)
- [High-resolution Lunar Topography (SLDEM2015) — PGDA #54](https://pgda.gsfc.nasa.gov/products/54)
- [Barker et al. (2023), A New View of the Lunar South Pole from LOLA, PSJ](https://iopscience.iop.org/article/10.3847/PSJ/acf3e1)
- [LOLA illumination products (polar stereographic) — MIT Imbrium](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION)
- [Mazarico et al. (2014), Illumination conditions at the lunar south pole using high resolution DTMs from LOLA, Icarus](https://www.sciencedirect.com/science/article/abs/pii/S0019103514004278)
- [LRO Diviner Global High-Resolution Mosaics (ODE/WUSTL)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [Lunar Surface Data Book (ACD-50044 Rev A), NTRS](https://ntrs.nasa.gov/api/citations/20230007818/downloads/ACD-50044%20Lunar%20Surface%20Data%20Book%20Rev%20A.pdf)
- [ECSS-E-HB-40-02A Machine Learning Qualification Handbook (15 Kasım 2024)](https://ecss.nl/wp-content/uploads/2024/12/ECSS-E-HB-40-02A(15November2024).pdf)
- [ESA AI STAR — ECSS ML Qualification Handbook tanıtımı](https://www.aistar.esa.int/advancing-the-european-space-industry-with-ai-introduction-to-the-ecss-e-hb-40-02a-machine-learning-qualification-handbook)
- [Lunar South Pole Atlas — LPI/USRA](https://www.lpi.usra.edu/lunar/lunar-south-pole-atlas/)
