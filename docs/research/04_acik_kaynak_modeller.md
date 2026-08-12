# 04 — Açık Kaynak Model ve Araç Ekosistemi

> **Soru:** LunaPath'i gerçekleştirmek için neyi sıfırdan yazmalı, neyi hazır almalı? Hangi açık kaynak modeller ve araçlar var, lisansları ne, hangisi uçuşa/akademiye uygun?
>
> **Kısa cevap:** LunaPath'in yol haritasındaki işlerin **neredeyse hiçbiri sıfırdan yazılmak zorunda değil.** Termal model (heat1d), ufuk/aydınlanma hesabı (SPICE + ASP), simülatör (OmniLRS), veri seti (POLAR, LuSNAR), planlama altyapısı (Nav2, OMPL), uçuş yazılımı çatısı (cFS, F´), foundation model (Prithvi/Clay/TerraMind + TerraTorch) — hepsi açık ve olgun. Asıl karar **neyi almayacağınız**: her bağımlılık bir bakım ve nitelendirme yüküdür.

---

## 1. Mevcut bağımlılık envanteri (ve değerlendirmesi)

```
backend/requirements.txt   fastapi 0.115.6, uvicorn 0.34.0, rasterio 1.4.3,
                           numpy 2.2.1, scipy 1.15.0, pyproj 3.7.2, httpx
lunapath/requirements.txt  rasterio, numpy, matplotlib, scipy   (pin YOK)
frontend/package.json      react 18, three 0.183, vite 5, typescript 5
```

| Bulgu | Değerlendirme |
|---|---|
| Backend pin'li, `lunapath/` pin'siz | 🟠 Tutarsız. `lunapath/requirements.txt` de pin'lenmeli; aksi halde tekrar-üretilebilirlik ([01](01_sektorel_veri_kaynaklari.md) §3.2) kırılır |
| `rasterio` + `pyproj` seçimi | ✅ Doğru. GDAL ekosisteminin Pythonic yüzü; planetary CRS desteği var |
| Ağır ML/CV yığını yok | ✅ Şu an doğru — gereksiz ağırlık taşınmıyor |
| Harita için Leaflet yok, **three.js** var | 🟡 Referans belge Leaflet planlıyor (§10), kod three.js'e geçmiş. Belge güncellenmeli. 3D görselleştirme için three.js daha güçlü ama coğrafi CRS desteği yok — piksel uzayında çalışmak zorunda |
| `matplotlib` sadece `lunapath/` içinde | ✅ Doğru ayrım (offline görselleştirme backend'e sızmıyor) |
| Lock dosyası yok (`requirements.txt` ≠ lock) | 🟠 `pip-tools` / `uv` ile `requirements.lock` üretin |
| SBOM yok | 🟡 Uzay/savunma bağlamında beklenir; `pip-audit` + `cyclonedx-py` ile 10 dakikalık iş |

**P0 aksiyonu:** `lunapath/requirements.txt`'i pin'le, tek bir `requirements.lock` üret, `pip-audit` CI adımı ekle.

---

## 2. Gezegen bilimi veri araç zinciri

Bu katmanda **hiçbir şey yazmayın** — 30 yıllık, doğrulanmış araçlar var.

| Araç | Ne yapar | Lisans | LunaPath'te nerede |
|---|---|---|---|
| **GDAL / rasterio** | Raster I/O, reproject, resample | MIT/X (GDAL: MIT-benzeri) | ✅ Kullanılıyor |
| **pyproj / PROJ** | CRS dönüşümleri (planetary CRS dahil) | MIT / X-11 | ✅ Kullanılıyor (`serializer.py`) |
| **SpiceyPy** (NAIF SPICE sarmalayıcı) | **Efemeris, güneş/Dünya pozisyonu, ışık geometrisi** | MIT (SpiceyPy); SPICE toolkit kendi lisansı | ❌ **Eksik — zaman ekseni için zorunlu** |
| **USGS ISIS** | Gezegen görüntü kalibrasyonu, kamera modelleri, projeksiyon | Public domain (US Gov) | ❌ NAC işlerseniz gerekli |
| **Ames Stereo Pipeline (ASP)** | Stereo DEM üretimi, SfS, bundle adjustment, **`sun_position`/gölge araçları** | Apache 2.0 | ❌ SfS/stereo yapacaksanız |
| **planetarypy / pvl** | PDS3/PDS4 etiket okuma | BSD/MIT | 🟡 PDS4 ürünlerine geçince gerekli |
| **GeoPandas / shapely** | ROI shapefile'ları (PGDA ürünleriyle gelir) | BSD | 🟡 Faydalı |
| **xarray + zarr** | Çok boyutlu (zaman × y × x) etiketli dizi, chunk'lı I/O | Apache 2.0 | ❌ **Zaman ekseni eklendiğinde neredeyse zorunlu** |
| **rioxarray** | rasterio ↔ xarray köprüsü | Apache 2.0 | 🟡 |

### 2.1 Neden SpiceyPy kritik

LunaPath'in en büyük yapısal eksiği zaman ekseni ([03](03_sentetik_minimum_veri.md) §2.1-P5). Zamanı doğru yapmanın tek ciddi yolu **efemeris**tir. SPICE ile:

```python
import spiceypy as spice
spice.furnsh("kernels/lunapath.tm")   # meta-kernel: LSK, PCK, SPK

def sun_azel_at(et, lon_deg, lat_deg):
    """Verilen efemeris zamaninda (et), Ay yuzeyindeki bir noktada
    Gunes'in azimut/elevasyonunu dondurur. MOON_ME sabit gövde çerçevesi."""
    # subsolar / illumination geometry:
    _, _, solar_inc, emission, phase = spice.ilumin(
        "Ellipsoid", "MOON", et, "MOON_ME", "LT+S", "SUN", point_xyz)
    return 90.0 - np.degrees(solar_inc), azimuth_from(...)
```

Gerekli kernel'lar (NAIF'ten ücretsiz): `naif0012.tls` (leapseconds), `pck00011.tpc` / `moon_pa_de440_200625.bpc` (gövde yönelimi), `de440s.bsp` (gezegen efemerisi), `moon_de440_220930.tf` (çerçeveler).

**Kernel'lar toplamda birkaç yüz MB'tır** — repoya koymayın, indirme script'i yazın.

### 2.2 Ufuk (horizon) hesabı — kendiniz yazmalı mısınız?

Aydınlanma haritası hazır ürün olarak indirilebiliyor ([01](01_sektorel_veri_kaynaklari.md)), ama **kendi DEM'iniz üzerinde arbitrary zamanda** aydınlanma istiyorsanız ufuk hesabı gerekir. Bu, yazmanız gereken **ender** bileşenlerden biridir çünkü tam olarak sizin grid'inize özel.

Standart algoritma (Mazarico vd.'nin kutup illumination çalışmalarında kullanılan yaklaşımın basitleştirilmiş hali):

```python
def horizon_elevation_map(elev, res_m, n_azimuth=360, max_range_m=50_000):
    """Her piksel icin, her azimutta ufuk yukseklik acisi (derece).
    Cikti: (n_azimuth, H, W) — buyuk! chunk'la veya azaltilmis azimutla calis.

    Yontem: her azimut icin ray-marching; ilerledikce
    max(atan((z_j - z_0) / d_j)) izlenir.
    Kure egriligi duzeltmesi: z_eff = z_j - d_j^2 / (2 R_moon)
    """
```

**Hesap yükü uyarısı:** 500×500 grid, 360 azimut, 625 adım (50 km / 80 m) = **56 milyar işlem** → saf Python imkânsız. Çözümler:
- Azimut sayısını 72'ye (5°) düşür → 11 milyar
- `numba.njit(parallel=True)` veya `cupy` (GPU)
- **En pratik:** hazır illumination ürününü kullan, kendi hesabını sadece küçük koridorlarda yap

Bu, [08](08_global_local_rotalama_yuku.md)'in ana temasının bir örneğidir: doğru cevap "her yerde her şeyi hesapla" değil, **hiyerarşi**dir.

---

## 3. Termal modelleme — hazır açık kaynak

| Araç | Ne yapar | Lisans | Değerlendirme |
|---|---|---|---|
| **heat1d** ([github.com/phayne/heat1d](https://github.com/phayne/heat1d)) | 1-B gezegen termal modeli (Hayne'in kendi kodu, Diviner ekibi) | Açık (repo lisansını doğrulayın) | ⭐ **En yüksek getirili tek bağımlılık.** Diviner türev ürünlerinin arkasındaki model ailesinden |
| **KRC** (Mars/Ay termal modeli, USGS) | Termofiziksel model | Public domain | 🟡 Fortran; kurulum eforu var |
| **Hayne et al. 2017 H-parametresi** | Derinliğe bağlı yoğunluk/iletkenlik modeli | Yayın | ⭐ Parametre kaynağı olarak kullan |

`heat1d` ile LunaPath'in kazandığı şey: **sıcaklığı bir harita olarak okumak yerine, bir rover'ın gölgeye girip çıkarken yüzey/derinlik sıcaklık geçmişini simüle etmek.** Bu, `THERMAL_TAU_S = 7200` gibi tek bir zaman sabitini fiziksel bir modelle değiştirir → detay [07](07_termal_veri.md).

---

## 4. Simülatörler — LunaPath'e ne kadar gerekli?

| Simülatör | Temel | Öne çıkan | Lisans | LunaPath için |
|---|---|---|---|---|
| **OmniLRS** ([github.com/OmniLRS/OmniLRS](https://github.com/OmniLRS/OmniLRS), [arXiv 2309.08997](https://ar5iv.labs.arxiv.org/html/2309.08997)) | NVIDIA Isaac Sim / Omniverse | **Hızlı prosedürel Ay arazi üretimi, çok-robot, sentetik veri pipeline'ı, ROS1+ROS2 binding** | Açık kaynak (repo) | ⭐ Sentetik görüntü/veri gerekirse **birinci tercih** |
| **LunarSim** ([github.com/PUTvision/LunarSim](https://github.com/PUTvision/LunarSim)) | — | Yüksek görsel doğruluk, ROS 2, CV algoritma geliştirme odaklı | Açık kaynak | 🟡 OmniLRS'e alternatif, daha hafif |
| **Isaac Lab / Isaac Sim** | Omniverse | Yüksek doğruluklu fizik, RL eğitim çatısı | Ücretsiz (NVIDIA lisansı), GPU şart | 🟡 RL yapacaksanız |
| **Gazebo (Harmonic)** | ODE/DART/Bullet | Olgun, hafif, eklenti mimarisi | Apache 2.0 | ✅ Hafif ihtiyaçlar için |
| **CoppeliaSim + Bullet** | — | Lunar micro-rover coverage çalışmasında kullanıldı ([arXiv 2404.18721](https://arxiv.org/html/2404.18721v1)) | Ücretsiz (edu) / ticari | 🟡 |
| **Project Chrono** | Çoklu-cisim + granüler (DEM/SPH) | POLAR-Sim'in arkasındaki motor; **tekerlek-regolit etkileşimi** | BSD-3 | ⭐ Terramekanik ciddiyet isterseniz |
| **CARLA türevi "Lunar Simulator"** | CARLA | Ay için uyarlanmış | MIT (CARLA) | 🟢 Niş |

### 4.1 Karar: LunaPath simülatöre girmeli mi?

**Hayır — mevcut kimlik için gerekli değil.** LunaPath bir **görev öncesi planlama / karar destek** aracıdır ([09](09_olgunluk_kiyaslama.md)); simülatör, rover üzeri otonomi geliştirirseniz gerekir. Simülatöre girmek:

- ➕ Sentetik görüntü/LiDAR üretir, ML eğitimi mümkün olur, yerel planlayıcı test edilebilir
- ➖ GPU + kurulum + öğrenme eğrisi (Isaac Sim'de günler), ekip odağını dağıtır, sim2real yükü doğar

**Önerilen orta yol:** Simülatör kurmayın, ama **simülatör çıktılarını (veri setleri) kullanın**. LuSNAR (108 GB, hazır UE sahneleri) ve POLAR-Sim, simülatör kurmadan sentetik veri erişimi sağlar.

---

## 5. Planlama ve navigasyon kütüphaneleri

| Kütüphane | Ne verir | Lisans | Değerlendirme |
|---|---|---|---|
| **ROS 2 + Nav2** | Global/local planner ayrımı, costmap_2d katman mimarisi, recovery behaviors, behavior tree | Apache 2.0 | ⭐ **Mimari şablon olarak paha biçilmez** (kod olarak almasanız da) |
| **OMPL** | Örnekleme tabanlı planlayıcılar (RRT*, PRM, BIT*) | BSD-3 | 🟡 Grid tabanlı problemde gereksiz |
| **`networkx`** | Genel graf algoritmaları | BSD | ❌ Referans belge doğru reddetmiş ("çok ağır") |
| **`heapq` (stdlib)** | Öncelik kuyruğu | PSF | ✅ Kullanılıyor, doğru seçim |
| **`numba`** | JIT ile A* çekirdeğini 10–100× hızlandırma | BSD-2 | ⭐ **En düşük maliyetli performans kazancı** |
| **`scikit-image`** | Morfoloji, mesafe dönüşümü (`distance_transform_edt` → koridor açıklığı!) | BSD-3 | ⭐ `path_corridor_clearance_m` için hazır |
| **`pathfinding` / `python-astar`** | Hazır A* | MIT | ❌ Kendi maliyet modelinizle uyumsuz; kendi A*'ınız doğru karar |

### 5.1 Nav2'nin costmap katman mimarisini ödünç alın

Nav2'nin en değerli fikri kodu değil, **deseni**: costmap tek bir dizi değil, üst üste binen **katmanlar** (static, obstacle, inflation, ...) ve her katman kendi güncelleme döngüsüne sahip. LunaPath'te bugün `cost_grid` tek seferde hesaplanıp donuyor (`compute_cost_grid`). Katmanlı yapıya geçmek:

```python
# backend/app/costmap.py (yeni)
class CostLayer(Protocol):
    name: str
    validity: Literal["MEASURED", "DERIVED", "MODEL"]
    def contribution(self, ctx: PlanContext) -> np.ndarray: ...
    def is_static(self) -> bool: ...   # True -> bir kez hesapla, cache'le

class CostMap:
    def __init__(self, layers: list[CostLayer]): ...
    def total(self, ctx) -> np.ndarray:
        # static katmanlar cache'ten, dinamikler her cagrida
        ...
    def explain(self, row, col, ctx) -> dict[str, float]:
        """Bu hucrenin maliyetine hangi katman ne kadar katki yapti?"""
```

**`explain()` metodu, LunaPath'in "neden bu rota seçildi" hedefinin ([ay_termal_navigasyon_proje_dokumani.md](../ay_termal_navigasyon_proje_dokumani.md) §8 Modül 8) doğru teknik cevabıdır** ve mevcut `/api/cell-telemetry` endpoint'inin (`main.py:279`) doğal uzantısıdır.

---

## 6. Uçuş yazılımı çatıları (uçuş iddiası kurarsanız)

| Çatı | Sahip | Lisans | Not |
|---|---|---|---|
| **NASA cFS (core Flight System)** | NASA GSFC | Apache 2.0 | Uçuşta kanıtlanmış; app tabanlı mimari; HPSC ile birlikte tanıtılıyor |
| **F´ (F Prime)** | NASA JPL | Apache 2.0 | Küçük uçuş sistemleri; **Ingenuity'de uçtu**; C++; öğrenmesi cFS'ten kolay |
| **Basilisk** | ASU/LASP | ISC | Astrodinamik simülasyon çatısı |
| **NASA 42** | GSFC | NOSA | Tutum/dinamik simülasyonu |
| **KubOS / Zephyr / RTEMS / VxWorks** | Çeşitli | Çeşitli / ticari | RTOS katmanı |

**LunaPath için tavsiye:** Kod olarak benimsemeyin. Ama mimari belgede **"onboard tarafa taşınırsa F´ veya cFS app'i olarak paketlenir"** cümlesini kurun ve modül sınırlarınızı buna uygun tutun (saf fonksiyonlar, I/O'dan ayrık çekirdek). Bu tek cümle, olgunluk algısını ciddi biçimde yükseltir ve zaten mevcut kod yapısıyla uyumludur (`cost_engine.py` saf fonksiyonlardan oluşuyor — bu iyi).

---

## 7. Açık kaynak ML modelleri

### 7.1 Coğrafi/uzaktan algılama foundation model'leri

Şu an üretime hazır sayılan üçlü ve destek araçları:

| Model | Geliştiren | Ne için | Erişim |
|---|---|---|---|
| **Prithvi-EO-2.0** | NASA + IBM | Genel EO temel modeli; **yörüngede çalışan ilk coğrafi foundation model** | Hugging Face, açık |
| **Clay v1.5** | Clay Foundation | Farklı kaynak/çözünürlüklere esnek | Açık |
| **TerraMind** | IBM + ESA (2025) | **Çok-modlu**: optik + SAR + **DEM** ortak eğitim | Açık |
| **DOFA** | — | Frekans-farkında mimari, çapraz-sensör genelleme | Açık |
| **SatMAE / ScaleMAE** | — | Masked autoencoder; etiketsiz görüntüden temsil | Açık |
| **TerraTorch** ([torchgeo/terratorch](https://github.com/torchgeo/terratorch)) | — | **Yukarıdakilerin tümü için fine-tune araç kiti** | Apache 2.0 |

**Kritik uyarı — bunlar Dünya modelleridir.** Prithvi HLS/Sentinel çok-bantlı Dünya verisiyle, 13 yıllık gözlem üzerine eğitildi. Ay'da:
- Bant yapısı uyuşmaz (NAC tek kanallı pankromatik)
- İstatistikler uyuşmaz (albedo, kontrast, gölge rejimi tamamen farklı)
- Ön-eğitim domain'i uzak → transfer kazancı belirsiz

**Yine de denemeye değer** çünkü fine-tune maliyeti düşük ve literatür ön-eğitimli başlatmanın rastgele başlatmadan **daha hızlı yakınsadığını** gösteriyor. Ama **iddia etmeden önce ölçün** — baseline olarak ImageNet-önceden-eğitimli bir ResNet/ViT ve sıfırdan bir UNet mutlaka bulunsun ([02](02_goruntu_isleme.md) §3.2'deki ViT vs UNet karşılaştırması tam bu deseni izliyor).

### 7.2 Görev-özel modeller

| Model | Görev | Not |
|---|---|---|
| **YOLOv5/v8/v11** | Kaya (boulder) tespiti | Ay kaya tespiti literatürü **YOLOv5s6 fine-tune** ile çalışıyor; ~12.000 etiketli kaya açık ✅ |
| **SAM / SAM 2** | Sıfır-shot segmentasyon | Prompt tabanlı; etiketleme hızlandırıcı olarak ideal (insanı %10 işe indirir) |
| **DINOv2/v3** | Kendini-denetimli görsel temsil | Ay görüntüsünde etiketsiz ön-eğitim için güçlü aday |
| **UNet / SegFormer / Mask2Former** | Semantik segmentasyon | LuSNAR benchmark'ı bunlarla kıyaslanıyor |
| **Depth Anything v2** | Monokular derinlik | Stereo çalışmadığında (kutupta doku yok) ilginç yedek |

### 7.3 LunaPath'e ML **eklemeli mi?**

`lunapath_referans_belgesi_2.md` ML'i scope dışına almış (§9: *"Scope dışı — zaman kalırsa: cost weight suggestion (Nelder-Mead)"*). **Bu karar doğruydu ve büyük ölçüde hâlâ doğru.** Ancak "gerçekleştirme" fazında iki ML fırsatı gerçekten yüksek getirili:

**(a) Kaya tespiti (denetimli, offline, yörünge görüntüsü)** — düşük risk, açık eğitim verisi, doğrudan yeni bir bağımsız veri kanalı üretir. **Öneri: yap.**

**(b) Ağırlık öğrenme / tercih öğrenme (inverse RL)** — "operatörün seçtiği rotalardan ağırlıkları öğren". Bilimsel olarak çekici ama **veri yok** (operatör tercihi yok). **Öneri: yapma**, ama AHP ağırlıklarına **duyarlılık analizi** yap (bu, ML olmadan aynı soruyu cevaplar).

**Yapmayın listesi:**
- ❌ End-to-end RL ile rota üretimi. Literatürde var ([Learning-Based End-to-End Path Planning for Lunar Rovers](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/), [Deep Learning Approach to Lunar Rover Global Path Planning](https://www.mdpi.com/1424-8220/24/3/844)) ama LunaPath'in güçlü yanı **açıklanabilirlik**tir; RL bunu yok eder ve ECSS safety cage gereksinimini zorlaştırır.
- ❌ LLM ile "rota açıklaması üretmek". Cazip görünür, hiçbir teknik değer katmaz, hallucination riski taşır. `explain()` (§5.1) deterministik ve daha güçlü.

---

## 8. Lisans, ihracat ve atıf

| Konu | Kural | LunaPath aksiyonu |
|---|---|---|
| **Proje lisansı** | MIT (repoda mevcut) | ✅ Uygun; permissive |
| **GPL bulaşması** | GPL'li bir kütüphaneyi link'lerseniz MIT dağıtımınız sorun yaşar | Bağımlılık lisanslarını tarayın (`pip-licenses`) |
| **NASA yazılımı** | Genellikle Apache 2.0 veya NOSA; NOSA GPL-uyumlu değildir | cFS/F´ Apache 2.0 → sorun yok; 42 NOSA → dikkat |
| **NVIDIA Isaac** | Kendi EULA'sı, ücretsiz ama açık kaynak değil | Kullanırsanız README'de belirtin |
| **Veri lisansları** | NASA PDS kamu malı, atıf beklenir; Zenodo türevleri CC-BY olabilir; JAXA/Kaguya ayrı koşullar | `docs/DATA_LICENSES.md` → [01](01_sektorel_veri_kaynaklari.md) §3.7 |
| **ITAR / EAR** | Uzay yazılımı bazı yargı alanlarında ihracat kontrolüne tabidir. **Açık kaynak, kamuya açık akademik veri ve genel amaçlı algoritmalar tipik olarak kapsam dışıdır**, ancak spesifik rover uçuş yazılımı olabilir | Şu an risk yok (kamu verisi + genel algoritma). Gerçek bir rover programına bağlanırsa **hukuki danışmanlık gerekir** — bunu bir riskler maddesi olarak kaydedin |

---

## 9. Seçim matrisi — LunaPath için nihai öneri

| Katman | Al (adopt) | Yazma | Erteleme (defer) |
|---|---|---|---|
| Raster I/O & CRS | ✅ rasterio, pyproj | — | — |
| Efemeris/geometri | ✅ **SpiceyPy** (+ NAIF kernel'ları) | — | — |
| Zaman-boyutlu dizi | ✅ **xarray** (+ zarr) | — | — |
| Termal fizik | ✅ **heat1d** | — | KRC |
| Ufuk/aydınlanma | 🟡 hazır ürün al; koridor için **kendi ray-marching**'ini yaz (numba) | — | Tam-alan ufuk hesabı |
| Hızlandırma | ✅ **numba** | — | Cython, GPU |
| Morfoloji/mesafe | ✅ **scikit-image** | — | — |
| Kaya tespiti | ✅ **YOLO + açık Ay kaya veri seti** | — | Krater tespiti |
| Foundation model | 🟡 **TerraTorch + Prithvi** (deneysel, ölçerek) | — | Kendi ön-eğitim |
| Etiketleme | ✅ **SAM 2** (hızlandırıcı) | — | — |
| Costmap mimarisi | 🟡 **Nav2 deseni** (kod değil, tasarım) | ✅ Kendi `CostMap` sınıfı | Nav2 entegrasyonu |
| Planlayıcı çekirdeği | — | ✅ **Kendi A*/D* Lite** (maliyet modeli özel) | OMPL |
| Simülatör | ❌ Kurmayın | — | OmniLRS (ML'e girerseniz) |
| Veri setleri | ✅ POLAR, POLAR-Sim, LuSNAR (indir, kullan) | — | — |
| Uçuş yazılımı | ❌ | — | F´ / cFS (uçuş iddiası doğarsa) |
| ML rota planlama | ❌ Yapmayın | — | — |

---

## 10. Yol haritası

### P0 (yarım gün)
1. `lunapath/requirements.txt` pin'le, `requirements.lock` üret
2. `pip-audit` + `pip-licenses` CI adımı
3. README'ye "üçüncü taraf bileşenler ve lisansları" bölümü

### P1 (2–4 gün)
4. **SpiceyPy + kernel indirme script'i** → güneş azimut/elevasyon fonksiyonu (zaman ekseninin temeli)
5. **numba** ile A* çekirdeği JIT — ölçülmüş öncesi/sonrası benchmark ile
6. **scikit-image** `distance_transform_edt` → `path_corridor_clearance_m` metriği
7. `CostMap` + `CostLayer` refaktörü, `explain()` dahil

### P2 (5–10 gün)
8. **heat1d** entegrasyonu → [07](07_termal_veri.md)
9. Koridor için numba ray-marching ufuk hesabı
10. Kaya tespiti (YOLO fine-tune) → [02](02_goruntu_isleme.md)
11. Mimari belgeye "F´/cFS uyumlu modül sınırları" bölümü

### Kabul kriterleri
- [ ] Tüm bağımlılıklar pin'li, lock dosyası var, SBOM üretilebiliyor
- [ ] Lisans envanteri belgeli, GPL bulaşması yok
- [ ] `spiceypy` ile verilen bir UTC zamanında güneş azimut/elevasyon üretilebiliyor
- [ ] A* benchmark'ı öncesi/sonrası ölçülmüş (hedef: 500×500'de <500 ms)
- [ ] `CostMap.explain(row, col)` her katmanın katkısını döndürüyor

---

## Kaynaklar

- [OmniLRS: A Photorealistic Simulator for Lunar Robotics (arXiv 2309.08997)](https://ar5iv.labs.arxiv.org/html/2309.08997) · [GitHub](https://github.com/OmniLRS/OmniLRS)
- [LunarSim (GitHub, PUTvision)](https://github.com/PUTvision/LunarSim)
- [POLAR-Sim (arXiv 2309.12397)](https://arxiv.org/abs/2309.12397)
- [LuSNAR dataset (GitHub)](https://github.com/zqyu9/LuSNAR-dataset) · [arXiv 2407.06512](https://arxiv.org/abs/2407.06512)
- [heat1d — Thermal model for planetary science (phayne)](https://github.com/phayne/heat1d)
- [Hayne et al. (2017), Global regolith thermophysical properties, JGR Planets](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/2017JE005387)
- [TerraTorch — GFM fine-tuning toolkit](https://github.com/torchgeo/terratorch)
- [Awesome Remote Sensing Foundation Models](https://github.com/Jack-bo1220/Awesome-Remote-Sensing-Foundation-Models)
- [NASA Prithvi — first geospatial foundation model in orbit](https://science.nasa.gov/science-research/ai-foundation-model-in-orbit/)
- [Global Lunar Boulder Map from NAC using Deep Learning (JGR Planets 2025)](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JE008981)
- [Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/)
- [A Deep Learning Approach to Lunar Rover Global Path Planning (Sensors 24(3), 844)](https://www.mdpi.com/1424-8220/24/3/844)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [The Dawn of the HPSC Era in Space Computing (Microchip white paper)](https://ww1.microchip.com/downloads/aemDocuments/documents/MPU64/ProductDocuments/SupportingCollateral/Dawn-of-HPSC-Era-in-Space-Computing-White-Paper.pdf)
- [cFS on HPSC (NTRS 20250000356)](https://ntrs.nasa.gov/api/citations/20250000356/downloads/Powell-cFS-2025-HPSC_for2025Jan29.pdf)
