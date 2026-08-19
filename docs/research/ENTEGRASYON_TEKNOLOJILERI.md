# LunaPath — Entegrasyon Teknolojileri Haritası

**Amaç:** `KAYNAK_HARITASI.md`'deki her kaynağı tek tek inceleyip, **mevcut LunaPath koduna neyin, nasıl, hangi eforla entegre edilebileceğini** somutlaştırmak. Bu belge kaynak listesini tekrar etmez; her kaynağı bir *teknoloji* olarak ele alır ve **hangi dosyaya / fonksiyona dokunacağını** söyler.

**Bağlam:** LunaPath şu an çalışan bir prototip — FastAPI + A* + AHP maliyet motoru + çoklu rover kataloğu + React kokpit + rasterio DEM hattı. Ama iki katman **sentetik**:

- `backend/app/thermal_grid.py → generate_thermal_grid()` — dosyanın kendi başlığı "**Synthetic** thermal grid". Sıcaklığı yükseklik + bakıdan uyduruyor.
- `lunapath/src/process_lunar_data.py → make_shadow_ratio_grid()` — gölge oranı = `1.0 - normalize(yükseklik)`. Yani gölge, gerçek ufuk/aydınlanma değil, sadece "alçak = karanlık" varsayımı.

Bu belgedeki entegrasyonların **çoğu bu iki noktayı gerçek fiziğe bağlamak** üzerine kurulu. Bir de projenin eksik olan **zaman boyutunu** ve **robotik ekosistem bağlantısını (ROS 2 / LiDAR)** ekleyen teknolojiler var.

---

## Kapsam notu

Bu belge `KAYNAK_HARITASI.md` (A–G grupları) temellidir. Buna ek olarak **iki yeni bölüm** eklenmiştir:

- **BÖLÜM 4 — ROS 2 ekosistemi**
- **BÖLÜM 5 — LiDAR ve 3B algı**

Bu ikisi kaynak haritasında yalnızca dağınık dipnotlar hâlinde geçiyordu (F1 Artemis sim, F3 LuSNAR'ın LiDAR'ı, G3 VIPER yazılımı) ama entegrasyon açısından **kendi başlarına birer karar noktası**. Bu yüzden ayrı bölüm oldular.

`docs/research/01`–`10` gerçekleştirme setinde duran ama **bu aşamada kapsam dışı bırakılan** konular (radyasyon katmanı, pürüzlülük/kaya kriterleri, hesaplama bütçesi, veri disiplini, ablasyon protokolü, MMGIS/uçuş yazılımı konumlandırması) belgenin sonunda **tek tablo hâlinde işaretlenmiştir** — silinmediler, sonraki aşamaya bırakıldılar.

---

## Entegrasyon katmanları (efor sınıflandırması)

| Katman | Anlam | 1 aya sığar mı? |
|---|---|---|
| **T1 — Tak-çalıştır** | Açık kaynak kütüphane/veri, doğrudan import veya indir. Kod yazımı minimal. | ✅ Evet, bu ay |
| **T2 — Yöntem uyarlaması** | Kodu değil *fikri/formülü* alıp kendi modülümüze gömüyoruz. | ✅ Kısmen, seçmeli |
| **T3 — Mimari genişletme** | Yeni boyut/katman ekliyor (ör. zaman ekseni, iki katmanlı planlayıcı). Ciddi iş. | ⚠️ Çekirdeği evet, tamamı Faz 2 |
| **T4 — Faz 2 / doğrulama** | Sunulacak ama bu ay yapılmayacak; ya da harici gerçeklik kontrolü. | 🔵 Anlatı / kalibrasyon |

---

## Hedef mimari — hangi teknoloji nereye takılıyor

```
                    ┌──────────────────────────────────────────────┐
   VERİ (T1)        │ LOLA DEM · MIT Imbrium AVGVISIB / LPSR ·      │
                    │ Diviner Polar Resource Products              │
                    └────────────────────┬─────────────────────────┘
                                         │ rasterio + reproject + Window
                    ┌────────────────────▼─────────────────────────┐
   FİZİK (T1)       │ heat1d (termal) · SpiceyPy (efemeris) ·       │
                    │ ufuk ray-marching (gölge)                    │
                    └────────────────────┬─────────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────────┐
   MALİYET (T2)     │ CostMap / CostLayer + explain()               │
                    │ (Nav2 costmap katman deseni)                  │
                    │ eğim · enerji · gölge · termal                │
                    └────────────────────┬─────────────────────────┘
                                         │
                    ┌────────────────────▼─────────────────────────┐
   PLANLAMA (T3)    │ çok kriterli A* (mevcut kod)                  │
                    │ + zaman ekseni & BEKLE kenarı (3ST-A*)        │
                    └────────────────────┬─────────────────────────┘
                                         │ ⬅ KORİDOR SÖZLEŞMESİ ⮕
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
┌───────▼────────┐            ┌──────────▼──────────┐          ┌──────────▼─────────┐
│ ARAYÜZ         │            │ ROS 2 (BÖLÜM 4)     │          │ YEREL KATMAN       │
│ FastAPI +      │            │ lunapath_ros:       │          │ (BÖLÜM 5, Faz 2)   │
│ React kokpit   │            │ action server ·     │          │ LiDAR → yerel DEM  │
│ (mevcut)       │            │ grid_map · rosbag2 ·│          │ → arc/DWA/MPC      │
│                │            │ RViz2 / Foxglove    │          │ (koridor içinde)   │
└────────────────┘            └─────────────────────┘          └────────────────────┘
```

---

# BÖLÜM 1 — Tak-çalıştır teknolojiler (T1)

Bunlar bu ay içinde koda gerçekten girebilecek olanlar. Öncelik burada.

## 1.1 `heat1d` — Gerçek termal fizik (kaynak B2) 🔴 EN YÜKSEK ÖNCELİK

**Ne olduğu:** Paul Hayne'in (Diviner bilim ekibi) 1B regolit termal difüzyon modeli. Artık olgun bir Python paketi: `pip install heat1d`. **MIT lisanslı** (repo README'sinde doğrulandı). Hayne vd. (2017) formülasyonuna dayanıyor; Apollo 15/17 ısı akısı deneyleri ve Diviner radyometresine karşı **doğrulanmış** model ailesinden.

**Neden bu projenin en kritik entegrasyonu:** `thermal_grid.py`'nin tamamının yerine geçer. Ve iş şansımıza, `heat1d`'nin güncel sürümü tam da bizim elimizdeki veriyle çalışıyor. README'nin ilan ettiği yetenekler:

- **Dört sayısal çözücü** — Explicit, Implicit, Crank-Nicolson ve **Fourier-matris** (frekans uzayı). Fourier-matris çözücü diurnal döngüyü ~100 ms'de çözüyor; 500×500 grid için hücre-hücre koşmayı **pratikte mümkün** kılan şey bu.
- **Eğimli yüzey ışıması** — `slope` + `azimuth` (bizde `slope_grid` + `aspect_grid` zaten piksel piksel var). Eğik-yüzey insolasyonu + **öz-gölgeleme** + çevre düz araziden dolaylı ısıtma.
- **PSR (kalıcı gölge) krater modeli** — çukur-tabanlı kraterler. Güney kutbu için birebir; bizim en soğuk hücrelerimiz bunlar.
- **JPL Horizons / SPICE entegrasyonu** — gerçek efemeris ile aydınlanma (aşağıda 1.2 ile birleşiyor).
- **Sıcaklığa bağlı özellikler** (radyatif `T³` terimli iletkenlik) + **derinliğe bağlı profiller**.

**Entegrasyon (somut):**

```python
# yeni: backend/app/thermal_grid.py (generate_thermal_grid'in yerine)
import numpy as np, planets
from heat1d import Model, Configurator

def thermal_from_heat1d(lat, slope_deg, aspect_deg):
    cfg = Configurator(solver="crank-nicolson")   # ya da Fourier-matris
    m = Model(planet=planets.Moon, lat=np.deg2rad(lat), ndays=1,
              slope=np.deg2rad(slope_deg), slope_az=np.deg2rad(aspect_deg),
              config=cfg)
    m.run()
    return m.T[:, 0]   # yüzey sıcaklığı (yerel zamanın fonksiyonu, K)
```

- **Basit yol (bu ay):** Enlem güney kutbunda ~sabit; her hücre için `(slope, aspect)` → tepe/dip yüzey sıcaklığı tablosu üret, `thermal_grid`'i bununla doldur. Statik ama **gerçek fizik**.
- **İleri yol:** SPICE zamanıyla `T_surface(x, y, t)` → zaman boyutu (Bölüm 3'teki 4B planlayıcının termal bacağı).

> ⚠️ **Sürüm tuzağı:** PyPI'daki yayınlanmış sürüm (0.3.1, 2020) yukarıdaki özelliklerin çoğunu **içermiyor** olabilir. Eğimli yüzey, PSR krateri ve Fourier-matris çözücüsü README'de listeleniyor ama paket sürümüyle eşleşmesi doğrulanmalı. **Kurulumdan sonra ilk iş `Model.__init__` imzasına bakıp `slope`/`slope_az` parametrelerinin gerçekten var olduğunu doğrulamak olmalı**; yoksa GitHub `main`'den kurun (`pip install git+https://github.com/phayne/heat1d`).

**Dokunduğu yerler:** `thermal_grid.py` (tamamen), dolaylı olarak `cost_engine.f_thermal()` ve `traversability.py` (artık gerçek `-150 °C` eşiği anlamlı olur), `constants.py` (rover `thermal_offset_*`/`thermal_tau_s` değerleri artık uydurma değil, modelle kalibre edilebilir).

**Efor:** Statik sürüm 1–2 gün. Bu, projenin özgünlük/ciddiyet iddiasını en çok yükselten tek hamle.

---

## 1.2 `SpiceyPy` — Zaman boyutunun temeli (kaynak B4) 🟠

**Ne olduğu:** NASA NAIF SPICE araç setinin (CSPICE) Python sarmalayıcısı. `pip install spiceypy`. MIT lisanslı, aktif bakımlı (AndrewAnnex). Gezegen/uydu konumları, referans çerçeveleri, zaman dönüşümleri için endüstri standardı.

**Neden kritik:** Projede **zaman ekseni yok** — bütün gölge/termal statik. SPICE, güneşin azimut/yükseklik açısını **zamanın fonksiyonu** olarak verir. `I(x, y, t)` aydınlanma alanının "t"si buradan gelir.

**Entegrasyon (somut):**

```python
import spiceypy as spice
spice.furnsh("kernels/lunapath.tm")   # meta-kernel: LSK + SPK + PCK + FK
et = spice.str2et("2026-11-15 12:00")
sun_vec, _ = spice.spkpos("SUN", et, "MOON_ME", "LT+S", "MOON")  # Ay-sabit çerçeve
# sun_vec + yerel yüzey normali → güneş yükseklik/azimut açısı (her hücre için)
# alternatif: spice.ilumin(...) doğrudan solar incidence/emission/phase verir
```

Gereken çekirdekler (kernels), NAIF'ten ücretsiz: `naif0012.tls` (leapseconds), `de440s.bsp` (gezegen efemerisi), `moon_pa_de440_200625.bpc` (gövde yönelimi), `moon_de440_220930.tf` (çerçeveler).

> **Repo hijyeni:** Çekirdekler toplamda birkaç yüz MB. **Repoya koymayın** — `scripts/fetch_kernels.py` yazıp `.gitignore`'a ekleyin.

**İlginç doğrulama:** Sun-Synchronous makalesi (A2) de "Kasım–Aralık 2026 için saatlik güneş görünürlüğünü efemeristen hesapladı" diyor — aynı yöntem.

**Dokunduğu yerler:** Yeni `backend/app/ephemeris.py`. Çıktısı ufuk hesabıyla (1.3) birleşip aydınlanma alanını besler.

**Efor:** Çekirdek kurulumu + temel güneş-vektörü fonksiyonu 1 gün. Zaman boyutunu planlayıcıya bağlamak T3 (Bölüm 3).

---

## 1.3 Ufuk (horizon) açısı hesabı — Mazarico yöntemi (kaynak B3) 🟠

**Ne olduğu:** Her pikselden N azimutta ışın atıp (Mazarico ~720 görüş hattı, 0.5° aralık) maksimum ufuk yükseklik açısını bulmak. Topografyadan bir kez hesaplanır, sonra sabit kalır.

**Neden kritik:** `make_shadow_ratio_grid()`'in (`1 - elev_norm`) gerçek karşılığı. **Bir hücre gölgede mi?** sorusunun doğru cevabı: güneş yükseklik açısı (SPICE'tan) < o azimuttaki ufuk açısı (topografyadan) ise gölgede.

```
ufuk_haritası(x, y, azimut)   ← topografyadan, 1 kez  (numpy/numba ray-marching)
güneş(azimut, yükseklik)      ← SPICE'tan, t'nin fonksiyonu
─────────────────────────────────────────────────────────────
I(x, y, t) = 1 eğer güneş_yükseklik(t) > ufuk(x, y, güneş_azimut(t)) değilse 0
```

```python
def horizon_elevation_map(elev, res_m, n_azimuth=72, max_range_m=50_000):
    """Her piksel icin, her azimutta ufuk yukseklik acisi (derece).
    Yontem: her azimut icin ray-marching; ilerledikce max(atan((z_j - z_0)/d_j)).
    Kure egriligi duzeltmesi: z_eff = z_j - d_j^2 / (2 * R_moon)"""
```

> **Hesap yükü uyarısı:** 500×500 grid × 360 azimut × 625 adım (50 km / 80 m) = **~56 milyar işlem** → saf Python imkânsız. Çözümler: azimutu 72'ye (5°) düşür, `numba.njit(parallel=True)` kullan, ya da **hazır aydınlanma ürününü al (1.4) ve kendi hesabını sadece koridorda yap.**

> ⭐ **İki ürün, tek çekirdek:** Bu ray-marching kodu, **§5.6'daki sanal LiDAR** taramasının da çekirdeğidir. Bir kez yazın, iki yerde kullanın.

**Dokunduğu yerler:** `lunapath/src/process_lunar_data.py` → `make_shadow_ratio_grid`'i bununla değiştir. `cost_engine.f_shadow()` artık gerçek gölge maruziyetiyle beslenir (bkz. sondaki kritik not).

**Efor:** numba ile vektörize ufuk hesabı 2–3 gün. Alternatif: 1.4 ile kestirme.

---

## 1.4 MIT Imbrium aydınlanma ürünleri — Hazır gerçek veri (kaynak B1) 🔴

**Ne olduğu:** `imbrium.mit.edu` üzerinden LRO-LOLA türevi, **doğrudan indirilebilir** kutup ürünleri:

- **AVGVISIB** — ortalama **Güneş** ve **Dünya** aydınlanması, 240 / 120 / 60 m/piksel, kutup stereografik. (Ufuk hesabını yapmadan gerçek aydınlanma!)
- **LPSR** — kalıcı gölge bölgesi maskeleri, 240 / 120 / 60 m/piksel.
- **SLDEM2015** (+ slope + azimuth) ve **LDAM** (albedo haritaları).
- **Diviner Polar Resource Products** (PDS'te) — **ortalama/maksimum yüzey sıcaklığı** + su buzu derinliği.

Format: IMG / JP2 + LBL/XML etiketleri — **rasterio/GDAL ile okunur** (hattımız zaten rasterio kullanıyor, sıfır yeni bağımlılık).

**Neden çift değerli:**
1. **AVGVISIB** → `make_shadow_ratio_grid`'in yerine gerçek ortalama aydınlanma. Ufuk hesabına gerek kalmadan (1.3'e kestirme).
2. **Diviner sıcaklıkları** → `heat1d` çıktımızın **harici doğrulaması**. "Modelimiz Diviner ölçümünü şu hatayla yeniden üretiyor" demek WP-5 için altın.

**Dikkat:** Mevcut penceremiz `origin (176000, 48000)`, 80 m/px, 500×500. Imbrium ürünlerine **ko-registrasyon** (yeniden örnekleme/kırpma) gerekir — rasterio `reproject` + `Window` ile.

**Dokunduğu yerler:** `process_lunar_data.py` (yeni indir+kırp adımı), `data_loader.py` (yeni grid'i yükle), `metadata.json`.

**Efor:** İndir + ko-registrasyon 1–2 gün. Bu ve `heat1d`, "sentetik veri" eleştirisini tümden kapatan ikili.

---

## 1.5 ETH `lunar_planner` — Baseline & çalınacak fikirler (kaynak A1) 🔴

**Ne olduğu:** `github.com/leggedrobotics/lunar_planner` (Richter ve ark., iSpaRo 2024, arXiv 2406.16376). **LunaPath'in en yakın akrabası**: A* tabanlı, **çok katmanlı maliyet**, objektifler arası **ayarlanabilir ağırlıklar**. Python 3.8+ + GDAL. İki araç: `PathCreator` + `PathAnalysis`. **MIT lisanslı.**

**Kritik farklar (bunlar bizim özgünlük argümanımız):**

| Boyut | ETH lunar_planner | LunaPath |
|---|---|---|
| Bölge | Ekvatoral (Aristarchus, Herodotus Mons) | **Güney kutbu** |
| Aydınlanma | ✅ Var | ✅ Gölge/termal çekirdek |
| **Termal kriter** | ❌ **Yok** | ✅ **Var** (bugün sentetik) |
| Bilimsel değer katmanı | ✅ Var (QuickMap element yoğunluğu) | ❌ Yok |
| İstatistiksel yol analizi | ✅ `PathAnalysis` aracı | ❌ Yok |
| Çoklu rover profili | ❌ Tek (quadruped) | ✅ 4 rover kataloğu |
| Maliyet formülasyonu | Ağırlıklı katman toplamı | **Log-barrier + AHP** |

> **Tablonun söylediği tek şey:** LunaPath'in gerçek farkı **termal kriter** ve **çoklu rover profili**. Termal kolon bugün sentetik → §1.1'i uygulamak, tablodaki tek gerçek farkı *gerçek* yapmak demek.

**Entegre edilebilecek fikirler (kodu değil, yaklaşımı):**
1. **`PathAnalysis` istatistiksel analiz** — bizde yok. Rota üzerinde dağılım istatistikleri (eğim histogramı, risk yüzdeleri) sunmak jüri için güçlü. `simulation.summarize_simulation()`'ı bu yönde genişlet.
2. **Bilimsel-değer maliyet katmanı** — AHP ağırlıklarına 5. bir eksen olarak "bilim ilgisi" eklenebilir (opsiyonel misyon profili).

**Neden ayrıca kritik:** Jüri "bunun benzeri var mı?" derse cevap hazır olmalı. Karşılaştırma **baseline**'ı olarak da kullanılır (WP-5).

**Dokunduğu yerler:** Doğrudan kod entegrasyonu **yok** (mimari referans + baseline). `serializer.py`/`simulation.py` analitik çıktıları zenginleştirmek için ilham.

**Efor:** Kurup çalıştırıp kıyaslama: 1 gün. Fikir uyarlaması seçime bağlı.

---

## 1.6 Path-Planning Derlemesi — Literatür zırhı (kaynak A3) 🟠

**Ne olduğu:** *"A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration"* (MDPI RS 2025, 17/11/1924). Algoritmaları **kısıt-odaklı** sınıflandırıyor (graf arama, potansiyel alan, örnekleme, DWA, biyo-esinli); **aydınlanma ve sıcaklık dalgalanmalarını** açıkça ele alıyor.

**Entegrasyon:** Kod değil, **rapor mühimmatı.** (a) "İlgili Çalışmalar" bölümü buradan çıkar. (b) **A\*'ı neden seçtiğimizin** gerekçesi: örnekleme/DRL yerine deterministik + optimal + açıklanabilir. Jüri "neden A*?" derse cevap bu derlemeye dayanır.

**Efor:** Okuma. Kod yok.

---

# BÖLÜM 2 — Yöntem uyarlamaları (T2)

Kütüphane değil; formülü/fikri alıp kendi modülümüze gömüyoruz. Seçmeli — ama **2.5 ve 2.6, BÖLÜM 4 ve 5'in ön koşuludur.**

## 2.1 Dağıtık Güvenlik-Haritası (kaynak A4) 🟠

**Fikir:** İkili (0/1) geçilebilirlik yerine **dereceli güvenlik haritası**. Bir hücre "geçilir" değil, "%70 güvenli" olur.

**Entegrasyon:** `traversability.py` şu an sert eşik (`slope > max` → 0). Bunu yumuşak bir güvenlik skoruna çevir; `cost_engine`'e ek bir "güvenlik cezası" katmanı olarak gir. AHP'ye doğal oturur ve §2.5'teki `CostLayer` yapısına birebir uyar.

## 2.2 Derin Olasılıksal Geçilebilirlik + Test-anı Adaptasyon (kaynak C2) 🟠

**Fikir:** Tekerlek kayması (slip) dağılımını gözlemden öğrenip **belirsizliği planlamaya** sokmak. "Belirsizliği kısıt değil, **rehber** olarak kullan."

**Entegrasyon:** ThermalNet/geçilebilirlik tasarımını etkiler — çıktı tek sayı değil, dağılım (ortalama + varyans). `simulation.py`'deki enerji/risk tahminine belirsizlik bandı eklenebilir. Faz 2'ye yakın ama fikir bugün mimariyi şekillendirir.

## 2.3 Şans-kısıtlı planlama (kaynak A5) 🟠

**Fikir:** "Bu rotanın başarı olasılığı %95" diyebilmek. Lamarre, Malhotra & Kelly (2024, arXiv 2401.08558) bunu Cabeus krateri / LCROSS bölgesinde **stokastik erişilebilirlik** analiziyle kuruyor. **LunaPath'in en yakın akademik komşusu — atıf zorunlu.**

**Entegrasyon:** Maliyet fonksiyonunu olasılıksal sarmalamak — deterministik `cost_engine`'in üstüne şans kısıtı katmanı. **1 ayda tam uygulanamaz → Faz 2 olarak sun.**

## 2.4 CISRU yazılım mimarisi (kaynak D3) 🟡

**Fikir:** Platformdan bağımsız robotik yazılım paketi (ERGO/ADE mirası, ASTRA 2023, arXiv 2311.03122). **Yazılım mimarisi** referansı — modül sınırlarını nasıl çizeceğimiz için.

**Entegrasyon:** Doğrudan kod değil; backend modül ayrımı için desen. **BÖLÜM 4'teki "iş mantığı ROS'a sızmaz" disipliniyle aynı aileden.**

## 2.5 `CostMap` / `CostLayer` + `explain()` — Nav2 costmap deseni 🔴 YENİ · **BÖLÜM 4'ün ön koşulu**

**Ne olduğu:** ROS 2 Nav2'nin `nav2_costmap_2d` mimarisinin **fikri** (kodu değil): costmap tek bir dizi değil, üst üste binen **katmanlar**dır (static, obstacle, inflation…), her katman kendi güncelleme döngüsüne sahiptir; sonunda birleştirilir.

**Neden LunaPath'e kritik:** Bugün `compute_cost_grid()` her şeyi tek seferde hesaplayıp donduruyor. Yeni bir kriter eklemek (güvenlik skoru, bilim değeri, aydınlanma) her seferinde bu fonksiyonu kesip biçmek demek. Katmanlı yapıya geçmek:

```python
# backend/app/costmap.py (yeni)
from typing import Protocol, Literal

class CostLayer(Protocol):
    name: str
    validity: Literal["MEASURED", "DERIVED", "MODEL", "SYNTHETIC"]
    weight: float
    def contribution(self, ctx: PlanContext) -> np.ndarray: ...
    def is_static(self) -> bool: ...      # True -> bir kez hesapla, cache'le

class CostMap:
    def __init__(self, layers: list[CostLayer]): ...
    def total(self, ctx) -> np.ndarray: ...
    def explain(self, row, col, ctx) -> dict[str, float]:
        """Bu hucrenin maliyetine hangi katman ne kadar katki yapti?"""
        return {L.name: float(L.weight * L.contribution(ctx)[row, col]) for L in self.layers}
```

> ⭐ **`explain()` metodu, LunaPath'in "neden bu rota seçildi" hedefinin doğru teknik cevabıdır** ve mevcut `/api/cell-telemetry` (`main.py:279`) endpoint'inin doğal uzantısıdır. Açıklanabilirlik zaten projenin en güçlü yanı; bu onu somut bir API alanına dönüştürür.

**ROS 2 bağlantısı:** Her `CostLayer`, §4.4'te `grid_map` katmanına birebir eşlenir. Bu refaktör yapılmazsa ROS tarafı katmanları tek tek elle yayınlamak zorunda kalır.

**Dokunduğu yerler:** yeni `backend/app/costmap.py`, `cost_engine.py` (katmanlara bölünür), `main.py` (`/api/cell-telemetry` genişler).

**Efor:** 2–3 gün. Refaktör riski var ama **testler mevcut olduğu için güvenli** (`test_cost_engine.py` regresyon ağı).

## 2.6 Koridor sözleşmesi — `Corridor` şeması 🔴 YENİ · **BÖLÜM 5'in arayüzü**

**Ne olduğu:** LunaPath'in çıktısı bugün bir **piksel dizisi**. Bir yerel planlayıcının (ROS 2 tarafı, LiDAR tarafı) ihtiyacı bu değil.

```python
# backend/app/schemas.py (yeni)
class Corridor(BaseModel):
    """Global planlayicinin yerel planlayiciya verdigi sozlesme."""
    waypoints: list[tuple[float, float]]        # metre, proje CRS'inde
    half_width_m: list[float]                   # segment basina izinli yanal sapma
    max_slope_deg: list[float]                  # segment bazli egim limiti
    thermal_budget_K_s: list[float]             # segment icin ayrilan termal stres butcesi
    energy_budget_wh: list[float]               # segment icin ayrilan enerji
    time_window_utc: list[tuple[str, str]]      # segmentin gecerli oldugu zaman penceresi
    fallback_points: list[tuple[float, float]]  # en yakin safe haven / bekleme noktasi
    replan_triggers: dict                       # hangi kosulda global'e geri don (§2.7)
```

`half_width_m` bedavaya gelir — `scipy` zaten kurulu:

```python
from scipy.ndimage import distance_transform_edt
clearance_m = distance_transform_edt(traversable) * resolution_m
half_width  = [min(clearance_m[r, c], MAX_CORRIDOR_HALF_WIDTH_M) for r, c in path]
```

> ⭐ **Bu şema, LunaPath'i "rota çizen bir demo"dan "bir otonomi yığınının üst katmanı"na dönüştürür** — kod yazmadan, sadece çıktı formatını doğru tanımlayarak. Ve **BÖLÜM 4 (ROS 2) ile BÖLÜM 5 (LiDAR) arasındaki tek gerçek arayüzdür.**

**ROS 2 karşılığı:** `waypoints` → `nav_msgs/Path`; geri kalanı özel `lunapath_msgs/Corridor` mesajı (§4.3).

**Efor:** 1 gün. **Getiri/efor oranı belgedeki en yüksek kalemlerden.**

## 2.7 Replan tetikleyici taksonomisi (kaynak A4-kritik/D2 — ESA ADAM) 🟠 YENİ

ESA ADE'nin ADAM modülü "tehlike tanındığında planı otonom değiştir" diyor ama tetikleyicileri saymıyor. Somut liste:

| Tetikleyici | Eşik önerisi | Aksiyon |
|---|---|---|
| Bilinmeyen engel tespit edildi | Yerel planlayıcı koridoru terk etmek zorunda | Global replan (segment) |
| SOC bütçeden sapma | Gerçek SOC < planlanan SOC − %10 | Global replan + `energy_saver` profiline geç |
| İç sıcaklık sapması | `T_iç`, tahminden 5 K aşağıda | Global replan + `shadow_traverse` profiline geç |
| Zaman kayması | Plan zamanından >30 dk sapma | **Aydınlanma değişti** → global replan zorunlu |
| İletişim penceresi kapanıyor | Dünya görünürlüğü < X dk | Konservatif moda geç |
| Konum belirsizliği | Kestirim kovaryansı > koridor yarı genişliği | Dur, lokalizasyon düzelt |

> **Bu tablonun kendisi bir çıktıdır.** `backend/app/replan_triggers.py` olarak kodlanır, her tetikleyici için bir birim testi yazılır, `/api/replan` endpoint'i bunları tüketir. **BÖLÜM 5'teki LiDAR geri besleme döngüsünün üst ucu budur.** i-SAIRAS 2020 ADE bildirisi ücretsiz PDF — taksonomiyi oradan zenginleştirin.

**Efor:** 1–2 gün (tetikleyiciler + testler + `/api/replan`).

---

# BÖLÜM 3 — Mimari genişletme: Zaman boyutu & iki katman (T3)

Projenin en büyük eksiği ve en büyük fırsatı. **4B planlayıcı** (WP-4) burada.

## 3.1 Sun-Synchronous 3STU-Net / 3ST-A* — 4B planlayıcının pusulası (kaynak A2/B5) 🔴

**Ne olduğu:** *"A Spatiotemporal U-Net-Based Data Preprocessing Pipeline for Sun-Synchronous Path Planning"* (MDPI RS 2025, 17/9/1589, Chang'E-7 bağlamı). İki bileşen:

- **3STU-Net** — uzay-zamansal U-Net (zaman-dilimi + zaman-serisi alt ağları), 2.5B aydınlanma verisini önişliyor, iyi aydınlanan bölgeleri buluyor.
- **3ST-A\*** — 3B uzay-zamansal durum uzayında **zamana-bağlı** arama; eğim + mesafe + aydınlanmayı tek sezgisel maliyette birleştiriyor. Saatlik güneş görünürlüğü efemeristen.

**Neden bu projenin merkez referansı:**
- **Özgünlük konumlandırması:** "4B planlayıcı" fikrimiz literatürde var → "biz ilkiz" **diyemeyiz**, ama "X'in yaklaşımını temel aldık, şurada farklılaşıyoruz" diyebiliriz (çok daha güçlü).
- **Farklılaşma eksenlerimiz:** (a) **çoklu rover profili** (onlar tek), (b) **log-barrier + AHP** maliyet, (c) **BEKLE (WAIT) kenarı**, (d) farklı termal model (heat1d fiziği), (e) **koridor sözleşmesi** (§2.6).

**Entegrasyon (bizim 4B A\*):**
```
Durum: (satır, sütun, zaman_dilimi)
Kenarlar: 8 komşu (mekânsal) + BEKLE (aynı hücre, t → t+1)
Maliyet: cost_engine + zaman-bağlı aydınlanma/termal (heat1d + SPICE'tan)
```

**Bekleme kenarının maliyeti — beklemek bedava değildir:**

```python
def wait_cost(cell, t, dt_h, illum_frac, rover):
    """Aydinlikta bekleme SOC'yi ARTIRIR (sarj) -> negatif enerji maliyeti.
    Golgede bekleme hem SOC hem sicaklik kaybettirir."""
    solar_in = rover["p_solar_w"] * illum_frac[cell]
    net_w = solar_in - rover["p_idle_w"] - rover["p_heater_w"]
    d_soc = net_w * dt_h / rover["e_cap_wh"]
    return (w_energy  * max(0.0, -d_soc)
          + w_shadow  * f_shadow_increment(1.0 - illum_frac[cell], dt_h)
          + w_thermal * thermal_drift_penalty(cell, dt_h))
```

> ⭐ **Bu, LunaPath'e eklenebilecek en yüksek bilimsel değerli tek özelliktir.** "Beklemek bir karardır" fikri, projeyi statik rota çizen bir araçtan **zaman-uzay görev planlayıcısına** dönüştürür ve mevcut sabitlerin (`p_solar_w`, `p_idle_w`, `p_heater_w`, `soc_min_pct`) hepsini anlamlı hale getirir. Bugün bu sabitler kodda duruyor ama **planlama kararını hiç etkilemiyor.**

- `pathfinder.py::astar` → durum uzayına zaman ekseni ekle (2B grid → 3B grid).
- `cost_engine.compute_cost_grid` → `cost_grid[t]` (zaman-dilimli maliyet küpü).
- **U-Net kısmını atlayabiliriz** — o, veri önişleme *verimliliği* için; bizim 500×500'de doğrudan hesap yeterli. (U-Net'i "gelecek iş" olarak anmak yeter.)

> ⚠️ **Ölçek uyarısı:** 500×500 × 168 zaman adımı = **42 M durum**, float32 8 yönlü maliyetle **~1.3 GB**. Düz grid burada çöker. Bu ay için **kaba grid (160–320 m) + az sayıda zaman dilimi (12–24)** ile başlayın; tam ölçek Faz 2.

**Kabul kriteri:** Bir senaryoda planlayıcı **"beklemeyi seçtiğini"** gösteriyor (aydınlık gelene kadar bekle → sonra geç). Tek başına güçlü bir demo.

**Efor:** Çekirdek 4B A* + BEKLE kenarı **bu ayın ana teknik hedefi olabilir** (T3). Tam ölçek Faz 2.

## 3.2 Risk-Aware Coverage — İki katmanlı mimari (kaynak C3/D1) 🟠

**Ne olduğu:** Santra, Uno, Kudo, Yoshida (Tohoku, arXiv 2404.18721). **Global veriyi lokal topografik özniteliklerle hareket maliyetinde birleştiriyor:** `mc = α(mc_static + mc_visited·V_i) + β·mc_DEM`, `α + β = 1`. Mikro-rover (CLOVER, 7 kg), **VLP-16 LiDAR**, HDL graph SLAM, ROS 1, CoppeliaSim + **gerçek analog saha testi** (lokalizasyon MAE 0.41 / 0.32 m).

**Neden çift değerli:**
1. Bizim 80 m global vs metre-altı lokal ayrımının **maliyet düzeyinde nasıl birleştirileceğini** gösteriyor → §2.6 koridor sözleşmesinin akademik gerekçesi.
2. **BÖLÜM 5'in (LiDAR) referans implementasyonu** — gerçek donanımla, gerçek arazide. LunaPath'ten ileride olduğu tek nokta bu; dürüstçe söylemek güç kazandırır.

**Entegrasyon:** Mimari karar — 80 m global planlayıcı (bizde var) + metre-altı lokal katman (Faz 2). AYAP-2'deki çözünürlük uçurumunun cevabı.

## 3.3 ESA ADE (OG10) — Yeniden planlama (kaynak A4-kritik/D2) 🟠

**Ne olduğu:** `h2020-ade.gmv.com`. ERGO (OG2) otonomi çerçevesi. **ADAM** (Autonomous Decision Making Module) nominal planı otonom değiştiriyor. Hedef: 6 saatte >1 km otonom traverse.

**Entegrasyon:** "Rota planla, bitti" modelinin ötesi. Gerçek misyonda plan **yeniden planlanır**. Bizim sistemde: §2.7'deki tetikleyiciler + yeni bir `/api/replan` uç noktası — küçük ama etkili bir demo. Avrupa referans mimarisi olarak sunumda "endüstri şurada, biz buradayız" için.

**Dokunduğu yerler:** `main.py` (yeni `/api/replan`), `simulation.py` (tetik koşulu), yeni `replan_triggers.py`. **Faz 2 anlatısı**, ama basit bir versiyonu bu ay gösterilebilir.

---

# BÖLÜM 4 — ROS 2 ekosistemi entegrasyonu 🔴 YENİ BÖLÜM

> Kaynak haritasında bu konu yalnızca dipnotlarda geçiyordu (F1 `artemis_mission_simulator` "ROS2 Ay dijital ikizi", G3 VIPER yazılımı). Oysa entegrasyon açısından **kendi başına bir karar noktası** ve LunaPath'in konumlandırmasını doğrudan güçlendiriyor.

## 4.0 Neden ROS 2 — üç gerekçe

**1. Hedef misyonun fiili standardı bu.** VIPER'ın (kaynak G3) yer tarafı hakkında açık kaynaklarda geçen ifade: *"VIPER'ın Dünya tabanlı operasyon araçlarının, hesaplama modüllerinin ve yüksek doğruluklu simülasyonlarının çoğu **ROS 2 ve Gazebo** tabanlıdır."* Yani LunaPath'in referans senaryosu olan kutup misyonunun **kendi yer planlama araçları ROS 2 üzerine kurulu.** Bu, ROS 2 hizalamasını "iyi mühendislik" olmaktan çıkarıp **konumlandırma argümanına** dönüştürüyor.

**2. Space ROS var ve NASA destekli.** ROS 2'den türetilmiş, güvenlik-kritik uzay robotiği için sertleştirilmiş açık kaynak çatı (NASA + Blue Origin + Open Robotics). Demoları arasında Canadarm2, Curiosity ve **Ay arazisi** var. ROS 2 API'siyle uyumlu olduğu için **bugün ROS 2 için yazdığınız şey yarın Space ROS'ta çalışır.**

**3. Nav2'nin costmap deseni zaten bizim ihtiyacımız.** §2.5'te ödünç aldığımız katmanlı costmap mimarisi Nav2'nin fikri. `grid_map` ise bizim 7 katmanımızın hazır taşıyıcısı.

> ⚠️ **Ama dikkat:** ROS 2'ye girmek **otomatik olgunluk vermez.** Yanlış yapılırsa "FastAPI'nin üstüne gereksiz bir katman" olur. Aşağıdaki karar matrisi neyi alıp neyi almayacağımızı netleştiriyor.

## 4.1 Karar matrisi — neyi al, neyi desen olarak al, neyi alma

| Bileşen | Karar | Gerekçe |
|---|---|---|
| **`rclpy` (ROS 2 Python istemcisi)** | ✅ **AL** (ince kabuk) | `backend/app/*` zaten saf fonksiyon; düğüm ~150 satır |
| **`grid_map_msgs/msg/GridMap`** | ✅ **AL** (sadece mesaj) | C++ kütüphanesine gerek yok; mesajı rclpy'den doldur |
| **`nav_msgs/msg/Path`** | ✅ **AL** | Koridor waypoint'lerinin standart karşılığı |
| **`rosbag2`** | ✅ **AL** | ⭐ Tekrar-üretilebilirlik kanıtı, çok ucuz |
| **RViz2 / Foxglove** | ✅ **AL** | Bedava 3B görselleştirme + jüri demosu |
| **Nav2 `costmap_2d` mimarisi** | 🟡 **DESEN OLARAK AL** | Kod değil tasarım (§2.5) — sıfır bağımlılık |
| **Nav2 planner plugin (C++)** | 🔵 **ERTELE** | `pluginlib` **C++ only**; Python planlayıcı doğrudan takılamaz (§4.5) |
| **Nav2 controller / BT / recovery** | ❌ **ALMA** | Bunlar yerel katman işi; LunaPath global planlayıcı |
| **Space ROS** | 🔵 **ANLATI** | Faz 2; bugün modül sınırı disiplini olarak yeterli |
| **Gazebo / Isaac Sim** | ❌ **ALMA (bu ay)** | GPU + kurulum + odak dağılması |
| **`rosbridge_suite` + React** | ❌ **ALMA (bu ay)** | FastAPI zaten çalışıyor; ikinci arayüz maliyeti |

> **Özet:** ROS 2 tarafı **ek bir arayüz**tir, mevcut FastAPI'nin **yerine geçmez.** Aynı çekirdek fonksiyonlar iki kabuktan servis edilir.

## 4.2 Sürüm seçimi — hangi ROS 2 dağıtımı

| Dağıtım | Çıkış | EOL | Ubuntu | Değerlendirme |
|---|---|---|---|---|
| **Jazzy Jalisco** | 23 May 2024 | May 2029 (LTS) | 24.04 | ⭐ **ÖNERİ** — `grid_map`, Nav2, `elevation_mapping_cupy` hepsinin `jazzy` dalı hazır |
| Kilted Kaiju | 23 May 2025 | **Ara 2026** | 24.04 | ❌ 4 ay sonra EOL — seçmeyin |
| **Lyrical Luth** | 22 May 2026 | May 2031 (LTS) | 26.04 | 🟡 En yeni LTS, ama **3 aylık** — üçüncü taraf paket kapsaması henüz olgunlaşmadı |
| Humble Hawksbill | 23 May 2022 | May 2027 | 22.04 | 🟡 Yaygın ama ömrü kısalıyor |

**Karar: Jazzy Jalisco.** Gerekçe: 2029'a kadar destek + ekosistem paketlerinin **hepsinin** `jazzy` dalı var. Lyrical Luth'a Faz 2'de geçilir (LTS→LTS geçişi düşük riskli).

> ⚠️ **Windows uyarısı — bu projeyi doğrudan etkiliyor.** Depo Windows'ta geliştiriliyor; ROS 2 Jazzy'nin birinci sınıf platformu Ubuntu 24.04. **Çözüm: WSL2 + Ubuntu 24.04, ya da Docker (`osrf/ros:jazzy-desktop`).** Bu, ekipten **bir gün** alabilir — takvime yazın, sürprize dönüşmesin. Python çekirdeği (FastAPI + A*) Windows'ta kalmaya devam eder; sadece ROS düğümü Linux'ta koşar.

## 4.3 `lunapath_ros` — somut paket tasarımı

```
lunapath_ros/
├── lunapath_ros/
│   ├── planner_node.py        # rclpy Node: PlanTraverse action server
│   ├── grid_publisher.py      # katmanlari grid_map_msgs/GridMap olarak yayinla
│   ├── corridor_publisher.py  # Corridor -> nav_msgs/Path + lunapath_msgs/Corridor
│   └── conversions.py         # (row,col) <-> map frame; metadata -> GridMapInfo
├── msg/
│   ├── RoverProfile.msg
│   ├── MissionWeights.msg
│   ├── PlanMetrics.msg
│   └── Corridor.msg
├── action/
│   └── PlanTraverse.action
├── launch/lunapath.launch.py
├── package.xml
└── setup.py
```

**Action tanımı — Nav2 konvansiyonuyla hizalı:**

```
# PlanTraverse.action
geometry_msgs/PoseStamped start
geometry_msgs/PoseStamped goal
string rover_id
MissionWeights weights
builtin_interfaces/Time epoch          # 4B planlayici icin (§3.1)
bool use_start
---
# Hata kodlari Nav2 ComputePathToPose ile ayni semantikte:
uint16 NONE=0
uint16 START_OUTSIDE_MAP=203
uint16 GOAL_OUTSIDE_MAP=204
uint16 START_OCCUPIED=205              # bizde: baslangic gecilebilir degil
uint16 GOAL_OCCUPIED=206
uint16 TIMEOUT=207
uint16 NO_VALID_PATH=208
nav_msgs/Path path
Corridor corridor
PlanMetrics metrics
builtin_interfaces/Duration planning_time
uint16 error_code
string error_msg
---
float32 progress
uint32 nodes_expanded
```

> **Neden Nav2'nin hata kodlarını taklit ediyoruz:** `nav2_msgs/action/ComputePathToPose` tam olarak bu alanlara sahip (`path`, `planning_time`, `error_code`, `error_msg` + `NO_VALID_PATH=208` gibi kodlar). Aynı semantiği kullanmak, §4.5'teki C++ shim'i **bire bir eşleme** haline getirir ve "standarda hizalıyız" demenin somut kanıtıdır. Mevcut `main.py`'de bu hatalar zaten HTTP 422/404 olarak var — sadece kod eşlemesi yazılacak.

**Düğümün kendisi ince olmalı:**

```python
# planner_node.py — is mantigi YOK, sadece kabuk
from backend.app.pathfinder import astar
from backend.app.simulation import simulate_path, summarize_simulation
from backend.app.constants import get_rover

class LunaPathPlanner(Node):
    def execute_callback(self, goal_handle):
        req = goal_handle.request
        start = conversions.pose_to_rc(req.start, self.metadata)
        goal  = conversions.pose_to_rc(req.goal,  self.metadata)
        result = astar(self.grids, start, goal,
                       weights=conversions.weights_msg_to_dict(req.weights),
                       rover=get_rover(req.rover_id))
        ...
```

> ⭐ **Kritik disiplin: iş mantığı asla ROS düğümüne sızmaz.** `backend/app/cost_engine.py` zaten saf fonksiyonlardan oluşuyor — bu iyi bir şans. Aynı çekirdek iki kabuktan servis edilir: FastAPI ve ROS 2 action server. Bu, CISRU'nun (§2.4) önerdiği platformdan bağımsız modül sınırının kod düzeyinde karşılığıdır.

**Çerçeve (frame) ve konvansiyon tuzağı:**

- REP-103: ROS **ENU** kullanır — x doğu, y kuzey, z yukarı; birim metre, sağ el kuralı.
- Bizim grid `(row, col)`; `row` güneye doğru artıyor. `conversions.py` bu ekseni **çevirmek zorunda.**
- REP-105 çerçeve ağacı: `map` → `odom` → `base_link`. Bizim `map` çerçevemiz: **Moon (2015) Sphere, South Polar Stereographic**, origin = grid (0,0) köşesi. `metadata.json`'daki `origin (176000, 48000)` bu dönüşümün girdisidir — `serializer.py::pixel_to_lonlat` zaten bu işi yapıyor, yeniden yazmayın, sarın.

## 4.4 `grid_map` — katmanların taşıyıcısı

**Ne olduğu:** ANYbotics'in evrensel 2.5B çok katmanlı harita kütüphanesi (BSD-3). Katman başına bir `Float32MultiArray`; `elevation`, `variance`, `friction`, `traversability`, `surface_normal` gibi katmanlar için tasarlanmış. `jazzy`, `rolling`, `humble` dalları aktif.

**Neden LunaPath'e mükemmel oturuyor:** Bizim katmanlarımız zaten bu şekil:

| LunaPath katmanı | `grid_map` layer | Kaynak |
|---|---|---|
| `elevation` | `elevation` | LOLA (§1.4) |
| `slope` | `slope` | türetilmiş |
| `aspect` | `aspect` | türetilmiş |
| `thermal` | `temperature` | **heat1d** (§1.1) |
| `shadow_ratio` | `illumination` | **AVGVISIB / ufuk** (§1.3–1.4) |
| `traversable` | `traversability` | §2.1 (dereceli) |
| `cost` | `cost` | `CostMap.total()` (§2.5) |
| *(opsiyonel)* `clearance` | `clearance` | `distance_transform_edt` (§2.6) |

**Bedava gelen yetenekler:**
- `grid_map` → `PointCloud2` / `OccupancyGrid` / `costmap_2d` dönüşümleri hazır → **RViz2'de 3B yüzey grafiği bedava.**
- `grid_map_filters` — morfoloji, normal hesabı, eşikleme; filtre zinciri YAML'den konfigüre edilir.
- Dairesel tampon ile haritayı rover'ı takip edecek şekilde kaydırma — yerel katman için (BÖLÜM 5).

> ⚠️ **Klasik hata:** `grid_map_msgs/GridMap` verisi `Float32MultiArray` içinde **sütun-öncelikli** sıralanır ve `dim` etiketleri (`column_index` / `row_index`) numpy'nin varsayılan satır-öncelikli düzeninin tersidir. Yanlış doldurursanız **RViz'de harita 90° dönmüş görünür** — bu, hatanın klasik belirtisidir. `conversions.py`'de `np.asfortranarray` + eksen çevirme yapın ve **bir birim testi yazın** (bilinen bir asimetrik desen → beklenen mesaj).

**Efor:** 1 gün (yayıncı + dönüşüm testi).

## 4.5 Nav2 — desen mi, gerçek entegrasyon mu?

**Teknik gerçek:** Nav2 planlayıcıları `nav2_core::GlobalPlanner`'dan türeyen ve `pluginlib` ile yüklenen **C++ eklentileridir**. `pluginlib` C++'a özeldir. **Python bir planlayıcı doğrudan Nav2 eklentisi olamaz.** Bu, çoğu tanıtımda geçiştirilen ama mimariyi belirleyen bir kısıttır.

Üç yol var:

| Yol | Ne | Efor | Ne zaman |
|---|---|---|---|
| **(a) Desen ödünç alma** | `costmap_2d` katman mimarisini `CostMap`/`CostLayer` olarak uygula (§2.5) | 2–3 gün | ✅ **Bu ay** |
| **(b) Paralel action server** | `PlanTraverse` action (§4.3); Nav2 ile **yan yana** koşar, BT'den çağrılabilir | 2–3 gün | ✅ **Bu ay** |
| **(c) İnce C++ shim eklentisi** | `nav2_core::GlobalPlanner` implementasyonu, `createPlan()` içinden action client ile bizim düğüme sorar | 3–5 gün | 🔵 Faz 2 |

**(c)'nin iskeleti** (Faz 2 için, ama tasarımı bugün söylenebilir):

```cpp
// lunapath_nav2_plugin/src/lunapath_planner.cpp
class LunaPathPlanner : public nav2_core::GlobalPlanner {
  void configure(parent, name, tf, costmap_ros) override {
      client_ = rclcpp_action::create_client<PlanTraverse>(node_, "plan_traverse");
  }
  nav_msgs::msg::Path createPlan(const PoseStamped& start,
                                 const PoseStamped& goal) override {
      // Python tarafina action gonder, nav_msgs/Path olarak geri al
  }
};
```

> **Neden (c) Faz 2:** Nav2'nin `costmap_2d`'si `uint8` doluluk ızgarasıdır; bizim maliyetimiz `float32` çok kriterli bir alandır. Gerçek entegrasyon, maliyet modelini Nav2'nin veri modeline sıkıştırmayı gerektirir — **bilgi kaybı.** Doğru mimari, `grid_map`'i taşıyıcı yapıp Nav2'yi sadece yerel katman için kullanmaktır.

**⭐ Bedava baseline fırsatı:** Nav2'nin `SmacPlanner2D` / `SmacPlannerHybrid` eklentileri aynı ızgarada A*/Hybrid-A* koşar. Aynı DEM'de **Nav2 SmacPlanner2D vs LunaPath çok kriterli A\*** kıyaslaması, ETH `lunar_planner` (§1.5) baseline'ının yanına ikinci bir karşılaştırma koyar — ve "endüstri standardı planlayıcı bu rotayı seçiyor, biz şunu, fark şu" demek jüri karşısında güçlü.

## 4.6 Space ROS — anlatı katmanı

**Ne olduğu:** ROS 2'den türetilmiş, güvenlik-kritik uzay robotiği için sertleştirilmiş çatı. NASA + Open Robotics + Blue Origin ortaklığı; ROS 2 API'siyle uyumlu, platform/proje bağımsız. Demoları: Canadarm2, Curiosity rover, **Ay arazisi**. Yol haritasında uçuş nitelemesi ve ticari bir Ay lander'ında gösterim hedefleniyor.

**LunaPath için ne yapmalı:** Bugün **hiçbir şey kurmayın.** Ama mimari belgeye şu cümleyi yazın:

> *"LunaPath'in planlama çekirdeği saf Python fonksiyonlarından oluşur ve I/O'dan ayrıktır. ROS 2 kabuğu (`lunapath_ros`) bu çekirdeği bir action server olarak servis eder. Space ROS, ROS 2 API'siyle uyumlu olduğu için bu kabuk, uçuş nitelemesi gereken bir bağlama taşındığında yeniden yazılmaz — yalnızca yeniden derlenir."*

Bu tek paragraf konumlandırma açısından orantısız kazanç sağlar ve **hiçbir kurulum maliyeti yoktur.**

## 4.7 Görselleştirme ve kayıt — en ucuz kazanç

| Araç | Ne verir | Efor |
|---|---|---|
| **RViz2** | `grid_map` 3B yüzey grafiği, `nav_msgs/Path`, `PointCloud2` | Yarım gün (config) |
| **Foxglove Studio** | Web tabanlı; canlı + `rosbag2` oynatma; **jüri demosu için RViz'den iyi** | Yarım gün |
| **`rosbag2`** | Her plan isteğini/cevabını kaydet | ⭐ Yarım gün |

> ⭐ **`rosbag2` disiplini tek başına bir olgunluk kanıtıdır.** "Her plan koşumu bir `rosbag2` kaydıdır; girdi grid'leri, istek, ara metrikler ve çıktı rotası zaman damgalı olarak saklanır ve aynen tekrar oynatılabilir." Bu cümle, tekrar-üretilebilirlik iddiasını **yarım günde** verir.

**Not:** Mevcut React + three.js kokpiti **kalır.** ROS görselleştirmesi geliştirici/jüri için ikinci bir pencere; son kullanıcı arayüzü değil.

## 4.8 Simülatör köprüsü — bu ay kurmayın, bağlantıyı tanımlayın

| Simülatör | Temel | ROS | Lisans | Karar |
|---|---|---|---|---|
| **`artemis_mission_simulator`** (kaynak F1) | simülatör-agnostik | **ROS 2** | Açık | 🟡 Güney kutbu dijital ikizi; WP-5 3B görselleştirme adayı |
| **OmniLRS** | NVIDIA Isaac Sim | ROS 1 + **ROS 2** | **BSD-3** | ⭐ Faz 2'de sentetik LiDAR/kamera için **birinci tercih**. Ortamlar: Lunalab (analog dijital ikiz), Lunaryard (prosedürel), **LargeScale (gerçek DEM'ler)** |
| **LunarSim** | — | **ROS 2** | Açık | 🟡 OmniLRS'e hafif alternatif, CV odaklı |
| **Gazebo Harmonic** | ODE/DART/Bullet | ROS 2 | Apache 2.0 | ✅ Hafif ihtiyaç + **VIPER yer araçlarıyla hizalı** |

**Karar:** Bu ay simülatör **kurmayın**. GPU + kurulum + öğrenme eğrisi ekibin odağını dağıtır. Bunun yerine **simülatör çıktılarını (veri setlerini) kullanın** — §5.5.

> **Ama OmniLRS'in LargeScale ortamını not edin:** **Gerçek DEM'leri** geometry clip map ile yüksek çözünürlüğe çıkarıyor. Bizim 80 m LOLA penceremiz doğrudan girdi olabilir — Faz 2'de "aynı arazi, iki ölçek" demosu için hazır bir köprü.

## 4.9 Efor, risk ve kabul kriterleri

| İş | Efor | Getiri | Katman |
|---|---|---|---|
| `rosbag2` kayıt disiplini | 0.5 gün | ⭐⭐⭐ | T1 |
| `grid_map` yayıncı + RViz2 config | 1 gün | ⭐⭐ | T1 |
| `conversions.py` + birim testleri (eksen/çerçeve) | 1 gün | ⭐⭐ | T1 |
| `PlanTraverse` action server (`planner_node.py`) | 2 gün | ⭐⭐ | T1 |
| Foxglove demo sahnesi | 0.5 gün | ⭐⭐ | T1 |
| Nav2 `SmacPlanner2D` baseline kıyası | 1 gün | ⭐⭐ | T1 |
| C++ shim eklentisi | 3–5 gün | ⭐ | T3/Faz 2 |
| Space ROS | 0 gün (anlatı) | ⭐⭐ | T4 |

**Riskler:**
- 🔴 **WSL2/Docker kurulumu** bir gün yiyebilir (Windows ekibi). Önceden yapın.
- 🟠 **Kapsam kayması:** ROS 2 çekici bir tavşan deliğidir. Sınırı net çizin — *iş mantığı asla ROS'a sızmaz*.
- 🟡 `grid_map` eksen/sıralama tuzağı (§4.4) — birim testle kapatın.

**Kabul kriterleri:**
- [ ] `ros2 action send_goal /plan_traverse ...` çalışıyor ve `nav_msgs/Path` dönüyor
- [ ] RViz2'de katmanlar `grid_map` olarak görünüyor, harita **dönmemiş**
- [ ] Bir plan koşumu `rosbag2` ile kaydedilip aynen oynatılabiliyor
- [ ] `backend/app/` içinde tek bir `import rclpy` yok (çekirdek temiz)
- [ ] Nav2 `SmacPlanner2D` ile karşılaştırma tablosu üretilmiş

---

# BÖLÜM 5 — LiDAR, nokta bulutu ve 3B algı 🔴 YENİ BÖLÜM

> Kaynak haritasında LiDAR yalnızca F3 (LuSNAR'ın 128-ışın LiDAR'ı) ve C3/D1 (VLP-16 kullanan Risk-Aware Coverage) içinde dolaylı geçiyordu. `KAYNAK_HARITASI` §H (tehlike tespiti) bilinçli olarak boş bırakılmıştı. Bu bölüm o boşluğu **dürüst bir kapsam çerçevesiyle** dolduruyor.

## 5.0 Dürüst çerçeve — LiDAR LunaPath'in neresine giriyor

**LiDAR bir global planlayıcı teknolojisi değildir.** LunaPath 80 m/px yörünge DEM'i üzerinde, yerde, görev öncesi çalışır. LiDAR 0.05–0.5 m ölçekte, rover üzerinde, gerçek zamanlı çalışır. LiDAR **Hazard Detection** ve **Local Path Planning** katmanına aittir — bizim katmanımıza değil.

"LiDAR'ı LunaPath'e eklemek" iki farklı şey demektir ve bunları karıştırmak sunumdaki en büyük risktir:

| | Ne demek | Ne zaman |
|---|---|---|
| **(A) Tüketici olarak** | LunaPath'in **koridor sözleşmesi** (§2.6), LiDAR tabanlı bir yerel planlayıcıya girdi olur. LiDAR bizim çıktımızı **tüketir.** | ✅ **Bu ay** — şema işi, §2.6'nın devamı |
| **(B) Üretici olarak** | LiDAR verisi LunaPath'in maliyet katmanlarını **besler** (yerel DEM, pürüzlülük, kaya). | 🔵 Faz 2 — ama §5.6 ile bugün prova edilebilir |

> **Sunumda kullanılacak dürüst cümle:** *"LunaPath'te LiDAR yok, çünkü LunaPath rover'ın üstünde çalışmıyor. Ama LiDAR'lı bir yerel planlayıcının ihtiyaç duyduğu her şeyi — koridor, açıklık payı, termal ve enerji bütçesi, zaman penceresi, geri dönüş noktaları — tanımlanmış bir sözleşme olarak üretiyoruz."*

## 5.1 Ay'da LiDAR gerçeği — uçmuş donanım

Bu tablo, "LiDAR Ay'da çalışır mı?" sorusunun kanıta dayalı cevabıdır.

| Sistem | Nerede | Ne yaptı | Somut sayılar |
|---|---|---|---|
| **Chang'e-3 L3DIS** (Lazer 3B Görüntüleme Sensörü) | Chang'e-3 lander (2013) ve sonraki Chang'e landerları | **Dünyada ilk**: lazer 3B görüntülemeyle bir gök cismine **otonom engel kaçınmalı yumuşak iniş** | Bir lazer demetinden bölünmüş **16 alt demet**, iki eksenli galvanometrik ayna taraması, **4 kare/s** 3B arazi; demet başına **5 µJ**, **50 kHz** tekrar frekansı, **33 mm** alıcı çapı, menzil doğruluğu **<0.15 m**, FOV **29° × 33°**. ~**100 m** irtifada askıda kalırken iniş bölgesinin nokta bulutunu alıp düz alan seçiyor |
| **NASA NDL** (Navigation Doppler Lidar, Langley) | Intuitive Machines **IM-1** (Şub 2024), Astrobotic Peregrine | İniş sırasında **hız + irtifa** ölçümü (haritalama değil) | Uçuş rekonstrüksiyonu: lidar ile modellenen ölçümler arasında **~5 m** ve **~0.5 m/s** uyum; ölçümler uçuş öncesi beklentiyi aşan menzillerde geçerli kaldı |
| **Yüzeyde sürüş için LiDAR** | — | ❌ **Ay yüzeyinde henüz uçmadı** | Yutu-2 (kaynak G1) görsel SLAM + stereo kullanıyor |
| **VLP-16 LiDAR** | Risk-Aware Coverage (kaynak C3/D1) | Global+lokal hibrit, HDL graph SLAM | **Dünya'da analog saha testi**: kaplama %80 (killi) / %65 (kumlu), lokalizasyon MAE **0.41 / 0.32 m**, CLOVER 7 kg mikro-rover |

> ⭐ **Sunum cümlesi:** *"Ay'a **inişte** LiDAR uçtu ve çalıştı — Chang'e-3'ün L3DIS'i 15 cm doğrulukla otonom engel kaçınması yaptı, NASA'nın NDL'i IM-1'de 5 m / 0.5 m/s doğruluk gösterdi. Ay **yüzeyinde sürüş için** LiDAR henüz uçmadı. Bu ayrımı bilmek, LiDAR'ı doğru katmana yerleştirmemizi sağlıyor."*

## 5.2 Kutupta neden LiDAR — ve neden zor

**Neden cazip:** Güney kutbunda güneş ufkun **~1.5°** üzerinde; PSR'de görünür ışık **hiç yok**. Kamera tabanlı stereo/VO bu rejimde kırılıyor: doku yok, keskin gölge, aşırı dinamik aralık, doygunluk, güneşe doğrudan bakış. **LiDAR kendi ışığını taşır** → aydınlanmadan bağımsızdır. Bu, kaynak E1'in (SuperPoint+LightGlue) çözmeye çalıştığı problemin donanım tarafındaki cevabıdır.

**Neden yine de zor:**

| Zorluk | Etki | LunaPath'te modellenebilir mi? |
|---|---|---|
| Alçak güneş açısı + PSR'de optik girişim | Eski nesil LiDAR ve kameralar etkileniyor; yeni nesil (tarayıcı lidar, flash ladar, lazer triangülasyon) araştırılıyor | 🟡 Kalitatif |
| Regolit düşük albedo | Menzil bütçesi Dünya'dakinden dar | ❌ Sensör modeli gerekir |
| **Toz** (elektrostatik yapışkan) | Optik pencere kirlenmesi → **zamanla performans düşüşü** | 🟡 Zaman-bağlı degradasyon faktörü |
| **Güç** — aktif sensör | Sürekli güç tüketimi | ✅ **EVET** — doğrudan bizim enerji modelimize girer |
| **Termal** — 40 K'ye inen PSR | Lazer diyot/dedektör ısıtma gerektirir | ✅ **EVET** — `p_heater_w` artar |

> ⭐ **Özgün katkı fırsatı — "LiDAR taşımak bir enerji/termal karardır".**
>
> `constants.py`'ye rover profillerine `sensor_payload_w` (ve gerekiyorsa `sensor_heater_w`) alanı ekleyip **aynı rotayı LiDAR'lı ve LiDAR'sız profille koşmak**, LunaPath'in tam da yapmak için var olduğu türden bir trade-off analizidir:
>
> *"LiDAR taşımak PSR'de görmenizi sağlar ama sürekli güç çeker ve 40 K'de ısıtıcı ister. LunaPath, bu iki profilin aynı haritada ürettiği rotaları ve enerji bütçelerini yan yana koyar."*
>
> **Efor: yarım gün** (bir sabit + bir karşılaştırma koşumu). Bu, LiDAR'ı LunaPath'e *gerçekten* ekleyebileceğiniz **tek yerdir** — çünkü LunaPath'in konusu sensör değil, **kaynak bütçesi**. Ve maliyeti neredeyse sıfır.

## 5.3 Veri zinciri — LiDAR nokta bulutundan koridora

```
LiDAR taramasi (sensor_msgs/PointCloud2)
   │
   │ 1. Odometri / kayit          → KISS-ICP veya LIO-SAM         → poz (6-DoF)
   │ 2. Birikim + voxel filtre    → Open3D / PCL                  → yerel nokta bulutu
   │ 3. 2.5B yukseklik haritasi   → grid_map / elevation_mapping   → 0.05–0.2 m yerel DEM
   │ 4. Oznitelik cikarimi        → egim · purüzlülük · basamak    → yerel maliyet katmanlari
   ▼
YEREL PLANLAYICI: arc ornekleme / DWA / MPC
   ▲                                          │
   │                                          │ koridor ihlali / bilinmeyen engel
   │ KORİDOR SÖZLEŞMESİ (§2.6)                ▼
   └──────────────────────────────── REPLAN TETİKLEYİCİSİ (§2.7) ──→ LunaPath
```

**Kritik gözlem:** Bu zincirin **LunaPath'e bağlandığı tek nokta koridor sözleşmesidir** — iki yönde. Aşağı doğru kısıt, yukarı doğru replan tetikleyicisi. §2.6 ve §2.7 yapıldığında LiDAR entegrasyonunun *arayüz tarafı* biter; geri kalanı yerel katman implementasyonudur.

**Adım 3 için hazır referans:** Kaynak E1'in deposu (Stanford-NavLab, Lunar Autonomy Challenge birincisi) tam bu zinciri kamera ile kuruyor: 180×180 geometrik ızgara (hücre yüksekliği = z medyanı) + kaya haritası (majority voting) + sabit-eğrilikli **yay (arc) örnekleme** yerel planlayıcı. **Kodu açık.** LiDAR yerine kamera kullanıyor ama mimari birebir aynı — yerel katmanı sıfırdan yazmayın.

## 5.4 Yazılım yığını

| Katman | Araç | Lisans | Değerlendirme |
|---|---|---|---|
| **Nokta bulutu işleme** | **Open3D** | MIT | ⭐ Python-native; voxel downsample, normal, düzlem segmentasyonu, ICP. LunaPath'in Python hattına en uygun |
| | **PDAL** | BSD | ⭐ Nokta bulutu → raster (DEM) pipeline; **GDAL ailesinden** — mevcut rasterio hattımızla aynı ekosistem |
| | PCL | BSD | C++; ROS ekosisteminin klasiği |
| **LiDAR odometri / SLAM** | **KISS-ICP** | **MIT** | ⭐ **ÖNERİ.** LiDAR-only, sensör-agnostik, az parametre, ROS 2 düğümü var. Zayıflık: sabit-hız varsayımı karmaşık hareketi modelleyemiyor |
| | **LIO-SAM** | BSD-3 | LiDAR-inertial, faktör grafı (GTSAM), loop closure |
| | **FAST-LIO2** | ⚠️ **GPL-2.0** | Daha doğru (sıkı-bağlı IEKF) ama **lisans riski** — aşağıya bakın |
| | GLIM / MAD-ICP / DLIO / GenZ-ICP | çeşitli | 2025 benchmark'larında öne çıkanlar |
| **Yükseklik haritası** | **`grid_map`** | BSD-3 | ⭐ §4.4 ile aynı kütüphane — tek veri modeli, iki ölçek |
| | **`elevation_mapping_cupy`** | — (repo) | ⭐⭐ GPU'da yükseklik haritalama + **öğrenilmiş geçilebilirlik filtresi**, yükseklik drift telafisi, ray-casting ile görünürlük temizliği. ROS 2 portları var |
| **Kayıt/oynatma** | `rosbag2` | Apache 2.0 | §4.7 |

> ⚠️ **LİSANS UYARISI — bu gerçek bir risk.** **FAST-LIO2 GPL-2.0 lisanslıdır.** LunaPath **MIT**'tir. GPL'li bir kütüphaneyi link'lerseniz MIT dağıtımınız sorun yaşar. Faz 2'de LiDAR odometrisi seçerken **KISS-ICP (MIT)** veya **LIO-SAM (BSD-3)** tercih edin. Seçimden önce repo `LICENSE` dosyasıyla **doğrulayın** — lisanslar sürümler arası değişebilir.

> ⭐ **Anlatı bağlantısı:** `elevation_mapping_cupy`, ETH Zürich **Robotic Systems Lab** ürünü — yani `lunar_planner`'ı (§1.5, kaynak A1) yazan **aynı laboratuvar**. "Global planlayıcımızın en yakın akrabası ETH'nin `lunar_planner`'ı; yerel katmana geçtiğimizde yine aynı laboratuvarın `elevation_mapping_cupy`'sini kullanacağız" demek, teknoloji seçiminin rastgele olmadığını gösterir.

## 5.5 Veri — LiDAR donanımı olmadan LiDAR çalışmak

| Kaynak | İçerik | LunaPath için |
|---|---|---|
| **LuSNAR** (kaynak F3, arXiv 2407.06512) | Unreal Engine tabanlı **9 Ay sahnesi** (topografik engebe ve nesne yoğunluğuna göre ayrılmış); yüksek çözünürlüklü **stereo görüntü çiftleri**, **LiDAR nokta bulutları**, yoğun derinlik haritaları, panoramik semantik etiketler, rover pozu. Benchmark: semantik segmentasyon, 3B rekonstrüksiyon, otonom navigasyon | ⭐ **Faz 2'nin LiDAR verisi çözülmüş.** Kaynak haritasında 108 GB / 128-ışın LiDAR olarak kayıtlı — **bu iki sayıyı makaleden teyit edin**, özet metinde geçmiyor |
| **POLAR-Sim** (kaynak F2) | NASA POLAR setinin dijital ikizi; 13 senaryo, kamera/güneş/pozlama/aktif aydınlatma ayarlanabilir; **23.000 etiket** (kaya/gölge/krater) | 🟡 Etiketli sentetik; LiDAR yok ama aydınlanma rejimi gerçek |
| **OmniLRS** (§4.8) | Isaac Sim; sentetik LiDAR + kamera üretebilir; gerçek DEM'lerden LargeScale ortam | 🔵 GPU şart |

## 5.6 ⭐ Bu ay yapılabilecek: yörünge DEM'inden "sanal LiDAR"

**Fikir:** LiDAR donanımı yok, simülatör kurmuyoruz, ama **koridor sözleşmesinin gerçekten bir yerel planlayıcıyı besleyip beslemediğini test etmek** istiyoruz. Yörünge DEM'i üzerinde ray-marching yaparak sentetik bir tarama üretmek bunu sağlar — ve **§1.3'teki ufuk hesabının aynı çekirdeğini kullanır.**

```python
# lunapath/src/virtual_lidar.py (yeni)
def virtual_scan(elev, res_m, pose_rc, yaw_rad,
                 n_azimuth=180, n_elevation=16,
                 max_range_m=30.0, fov_v_deg=30.0):
    """Yorunge DEM'i uzerinde ray-marching ile sentetik LiDAR taramasi.
    Ufuk hesabinin (§1.3) ayni cekirdegi -- tek kod, iki urun.

    Donus: (N, 3) nokta bulutu, rover-merkezli ENU koordinatlarinda.
    ROS 2 tarafinda sensor_msgs/PointCloud2 olarak yayinlanabilir (§4.3).
    """
```

**Ne kazandırır:**
1. **Arayüz testi** — koridor sözleşmesi bir yerel-katman tüketicisine gerçekten yetiyor mu? Cevabı ancak bir tüketici yazınca öğrenirsiniz.
2. **Kod tekrar kullanımı** — ufuk hesabı (§1.3) + sanal LiDAR: **bir ray-marching çekirdeği, iki ürün.**
3. **Demo gücü** — nokta bulutu + koridor + rota aynı 3B sahnede. Frontend'de `three.js` **zaten var**; RViz2 tarafında `PointCloud2` bedava.
4. **`elevation_mapping` zincirinin provası** — sanal nokta bulutu → `grid_map` → yerel geçilebilirlik hattı, gerçek LiDAR gelmeden test edilir.

> ⚠️ **Sınırı dürüstçe söyleyin — bu kritik.** 80 m DEM'den üretilen sanal tarama, gerçek LiDAR'ın gördüğü **30 cm'lik kayayı göremez.** Bu bir **arayüz testidir, algı simülasyonu değildir.** Bunu belgeye ve sunuma açıkça yazın.

**Efor:** 2 gün (ufuk çekirdeği zaten varsa 1 gün).

## 5.7 Kapsam kararı ve efor özeti

| İş | Katman | Efor | Karar |
|---|---|---|---|
| Koridor sözleşmesi (§2.6) — LiDAR tarafının tükettiği şey | T2 | 1 gün | ✅ **Bu ay** |
| Replan tetikleyicileri (§2.7) — LiDAR tarafının ürettiği şey | T2 | 1–2 gün | ✅ **Bu ay** |
| `sensor_payload_w` + LiDAR'lı/LiDAR'sız profil kıyası (§5.2) | T2 | 0.5 gün | ✅ **Bu ay** — ⭐ özgün |
| Sanal LiDAR (§5.6) | T2 | 1–2 gün | ✅ **Bu ay** (opsiyonel, demo değeri yüksek) |
| Ay'da LiDAR gerçeği tablosu (§5.1) — sunum mühimmatı | — | 0 gün | ✅ Hazır |
| LuSNAR indir + nokta bulutu → `grid_map` hattı | T4 | 3–5 gün | 🔵 Faz 2 |
| KISS-ICP / LIO-SAM ile odometri | T4 | 5+ gün | 🔵 Faz 2 |
| `elevation_mapping_cupy` (GPU) | T4 | 5+ gün | 🔵 Faz 2 |
| Gerçek LiDAR donanımı | — | — | ❌ Kapsam dışı |

**Kabul kriterleri:**
- [ ] Belgede ve sunumda "LiDAR yok, çünkü yerel katman kapsam dışı" cümlesi net; "otonom navigasyon" iddiası hiçbir yerde geçmiyor
- [ ] Koridor sözleşmesi yayımlanmış ve bir tüketici (sanal LiDAR veya sahte yerel planlayıcı) tarafından tüketiliyor
- [ ] LiDAR'lı/LiDAR'sız rover profili karşılaştırması sayısal olarak sunulmuş
- [ ] Sanal LiDAR'ın çözünürlük sınırı belgede açıkça yazılı

---

# BÖLÜM 6 — Doğrulama & kalibrasyon (T4)

Kod entegrasyonu değil; rover profillerimizi **gerçekliğe** bağlar. `constants.py` kataloğunu doğrular.

## 6.1 Yutu-2 (Chang'e-4) — Uçmuş, gerçek veri (kaynak G1) 🟠 EN DEĞERLİ

Ay'ın uzak yüzünde 5+ yıl; görsel SLAM + rota planlama + rover kontrolü ile **Ay'daki en olgun otonomi**. Gerçek hız, gerçek günlük mesafe, gerçek operasyon kısıtları. `constants.py`'de `cnsa_yutu_2` profili **zaten var** — ama **doğrulanmalı**. WP-5 hedefi: *"Modelimiz Yutu-2'nin bilinen günlük ilerleme hızını şu hatayla yeniden üretiyor."* Herhangi bir simülasyondan güçlü.

## 6.2 Pragyan (Chandrayaan-3) — Güney kutbuna yakın (kaynak G2) 🟠

69.4°G, 2023. Kısa ömür (1 Ay günü), termal sınırlı — **AYAP-2 profiline en yakın gerçek misyon.** **Yer-döngülü (ground-in-the-loop)**: her hareket için navcam verisi Dünya'ya indirilip DEM üretiliyor, komut başına **~5 m**.

> ⭐ **Bu, LunaPath'in konumlandırmasının kanıtıdır.** Pragyan seviyesinde bir yer-döngü mimarisi **hâlâ operasyonel gerçeklik.** Yani LunaPath'in "görev öncesi planlama aracı" konumlandırması zayıflık değil, **sektörle uyum**.

## 6.3 VIPER açık kaynak yazılımı (kaynak G3) 🟡

NASA'nın kutup rover yazılımını açması. `constants.py`'de `nasa_viper` profili var. Kutup misyonu operasyon mantığı referansı. **Yer araçları ROS 2 + Gazebo** — §4.0'ın birinci gerekçesi buradan geliyor. (Not: VIPER 2024'te iptal edildi, 2025'te Blue Origin ile diriltildi, 2027 hedefi.)

## 6.4 EMRS saha testi (kaynak G4) 🟡

*European Moon Rover System* analog saha testi (arXiv 2411.13978). **Traverse performansı, tekerlek sapması, ulaşım maliyeti (cost of transport)** ölçümleri. Bizim `simulation.py` enerji modelini **gerçek ölçümle kıyaslamak** için.

**Entegrasyon (6.1–6.4):** Yeni test dosyası — `backend/test_rover_validation.py` — profil çıktılarını yayımlanmış gerçek değerlerle karşılaştıran assert'ler. `constants.py` değerlerini bu kaynaklara dayandır.

---

# BÖLÜM 7 — Faz 2: Algı, SLAM, veri setleri (T4)

Bu ay **yapılmayacak**, ama sunumda "sonraki adım" olarak anlatılacak. BÖLÜM 5 ile birlikte okunur — bunlar yerel katmanın bileşenleridir.

## 7.1 SuperPoint + LightGlue — Aydınlanma-dayanıklı algı (kaynak E1) 🟠

Stanford-NavLab/lunar_autonomy_challenge. **Lunar Autonomy Challenge birincisi**, açık kod. Stereo görsel odometri + pose graph SLAM (GTSAM); **SuperPoint** (keypoint) + **LightGlue** (eşleme) — aşırı aydınlanma değişimine dayanıklı oldukları için seçildiler. Sonuç: santimetre seviyesi lokalizasyon.

**Güzel bağlantı:** Ay'da klasik SIFT/ORB neden çöker (keskin gölge, ara ton yok, alçak güneş açısı) — cevabı bu. **"Aydınlanma sadece enerji değil, algı problemidir"** tezi sunumdaki aydınlanma vurgusunu güçlendirir. §5.2'deki "LiDAR kendi ışığını taşır" argümanının donanım tarafındaki ikizidir.

## 7.2 LunarLoc — Landmark konumlandırma (kaynak E2) 🟡

arXiv 2506.16940. Kaya (boulder) landmark'larının zero-shot segmentasyonu → graf tabanlı eşleme. **Santimetre-altı** çoklu oturum konumlandırma.

## 7.3 Visual SLAM + DEM Anchoring — Drift azaltma (kaynak E3) 🟡

arXiv 2603.17229. DEM'den türetilen yükseklik + yüzey-normali kısıtlarını poz grafiğine sokup drift'i azaltıyor (Unreal + Etna analog). **Bizim DEM'imize doğrudan bağlanır** — elimizdeki veri bu yöntemin girdisidir.

## 7.4 Eğitim veri setleri: POLAR-Sim + LuSNAR (kaynak F2/F3) 🟡

- **POLAR-Sim** (arXiv 2309.12397): NASA POLAR seti + 13 senaryonun dijital ikizi; kamera/güneş/pozlama/aktif aydınlatma ayarlanabilir; 23.000 etiket (kaya/gölge/krater).
- **LuSNAR**: UE tabanlı 9 sahne; stereo + **LiDAR** + derinlik + semantik + poz (§5.5).

**Değeri:** "1 ayda etiketli veri bulamazsın" endişesini yumuşatır. Faz 2'nin eğitim verisi **çözülmüş** demek.

## 7.5 Artemis Mission Simulator (kaynak F1) 🟡

`jasmeet0915/artemis_mission_simulator` — ROS 2 Ay dijital ikizi. WP-5 3D görselleştirme veya Faz 2 algı verisi için. Ayrıntı §4.8'de.

---

# ÖZET: Kaynak → LunaPath modülü → efor

| Kaynak | Teknoloji | Dokunduğu dosya | Katman | Öncelik |
|---|---|---|---|---|
| **B2** heat1d | Gerçek termal fizik | `thermal_grid.py` (tümü) | T1 | 🔴🔴 |
| **B1** MIT Imbrium | Gerçek aydınlanma + Diviner doğrulama | `process_lunar_data.py`, `data_loader.py` | T1 | 🔴 |
| **B4** SpiceyPy | Zaman boyutu (güneş konumu) | yeni `ephemeris.py` | T1 | 🟠 |
| **B3** Ufuk hesabı | Gerçek gölge (+ sanal LiDAR çekirdeği) | `make_shadow_ratio_grid` | T1 | 🟠 |
| **A1** ETH lunar_planner | Baseline + `PathAnalysis` fikri | `simulation.py`, `serializer.py` (ilham) | T1 | 🔴 |
| **A3** Path-Planning derleme | Literatür / A* gerekçesi | rapor | — | 🟠 |
| **A4** Güvenlik haritası | Dereceli geçilebilirlik | `traversability.py`, `cost_engine.py` | T2 | 🟠 |
| **C2** Olasılıksal geçilebilirlik | Belirsizlik bandı | `simulation.py` | T2 | 🟠 |
| **A5** Şans kısıtı | Olasılıksal maliyet | `cost_engine.py` sarmalama | T2 | 🟠 (Faz 2) |
| **D3** CISRU | Yazılım mimarisi deseni | backend modül sınırları | T2 | 🟡 |
| **— (yeni)** CostMap + `explain()` | Katmanlı maliyet · **ROS 2 ön koşulu** | yeni `costmap.py`, `main.py` | T2 | 🔴 |
| **— (yeni)** Koridor sözleşmesi | **LiDAR/yerel katman arayüzü** | yeni `schemas.py` | T2 | 🔴 |
| **A4/D2** Replan tetikleyicileri | Yeniden planlama | yeni `replan_triggers.py`, `/api/replan` | T2 | 🟠 |
| **A2/B5** 3STU-Net / 3ST-A* | 4B planlayıcı + **BEKLE kenarı** | `pathfinder.py`, `cost_engine.py` | T3 | 🔴 |
| **C3/D1** Risk-aware coverage | İki katmanlı mimari | mimari karar | T3 | 🟠 |
| **A4/D2** ESA ADE | Yeniden planlama mimarisi | `main.py` | T3 | 🟠 |
| **G3 + yeni** `lunapath_ros` action server | ROS 2 arayüzü | yeni paket (çekirdek değişmez) | T1/T3 | 🔴 |
| **— (yeni)** `grid_map` | Katman taşıyıcısı + RViz2 | `lunapath_ros/grid_publisher.py` | T1 | 🟠 |
| **— (yeni)** Nav2 | Desen (bugün) / C++ shim (Faz 2) | `costmap.py` / yeni plugin | T2/T3 | 🟠 |
| **— (yeni)** Space ROS | Anlatı + modül disiplini | mimari belge | T4 | 🟡 |
| **— (yeni)** rosbag2 + Foxglove | Tekrar-üretilebilirlik + demo | launch/config | T1 | 🟠 |
| **F1** Artemis sim / OmniLRS | Simülatör köprüsü | — | T4 | 🟡 |
| **— (yeni)** Ay'da LiDAR gerçeği | Sunum mühimmatı | rapor | — | 🟠 |
| **— (yeni)** `sensor_payload_w` | **LiDAR = enerji/termal kararı** ⭐ özgün | `constants.py` | T2 | 🟠 |
| **C3/D1 + yeni** LiDAR yazılım yığını | Yerel katman (⚠️ GPL riski) | — | T4 | 🟡 |
| **F3** LuSNAR | Faz 2 LiDAR verisi | — | T4 | 🟡 |
| **B3 + yeni** Sanal LiDAR | Arayüz testi + demo | yeni `virtual_lidar.py` | T2 | 🟠 |
| **G1** Yutu-2 | Gerçek doğrulama | yeni `test_rover_validation.py` | T4 | 🟠🟠 |
| **G2** Pragyan | Kutup kalibrasyonu + konumlandırma | `constants.py` | T4 | 🟠 |
| **G3** VIPER yazılımı | Ops mantığı + ROS 2 hizası | `constants.py` | T4 | 🟡 |
| **G4** EMRS | Enerji modeli kıyası | `simulation.py` | T4 | 🟡 |
| **E1** SuperPoint+LightGlue | Algı (Faz 2) | — | T4 | 🟠 |
| **E2** LunarLoc | Konumlandırma (Faz 2) | — | T4 | 🟡 |
| **E3** Visual SLAM DEM | Drift azaltma (Faz 2) | — | T4 | 🟡 |
| **F2** POLAR-Sim | Eğitim verisi (Faz 2) | — | T4 | 🟡 |

---

# ÖNERİLEN ENTEGRASYON SIRASI

**Bu ay gerçekten koda girecekler — sırayla:**

1. 🔴 **Gölge terimi düzeltmesi** — `compute_cost_grid` içindeki `f_shadow` ölçek hatası (bkz. "Kritik notlar"). **Yarım gün**, ama ağırlığı 0.142 olan bir kriterin bugün maliyete ~%0.01 katkı yaptığı anlamına geliyor. Diğer her şeyden önce.
2. 🔴🔴 **heat1d** kur (sürüm tuzağına dikkat), statik gerçek termal grid üret → `thermal_grid.py`'yi değiştir. *(WP-1/WP-3, tek en yüksek getirili hamle)*
3. 🔴 **MIT Imbrium AVGVISIB + Diviner PRP** indir, ko-registre et → gerçek aydınlanma + termal doğrulama. *(WP-1/WP-5)*
4. 🟠 **SpiceyPy** çekirdekleri kur, güneş-vektörü fonksiyonu yaz. *(WP-2)*
5. 🔴 **`CostMap` + `explain()` refaktörü** → hem yeni katmanların yeri, hem ROS 2 tarafının ön koşulu.
6. 🔴 **Koridor sözleşmesi + replan tetikleyicileri + `/api/replan`** → BÖLÜM 4 ve 5'in arayüzü.
7. 🔴 **4B A\* çekirdeği** — `pathfinder.py`'ye zaman ekseni + BEKLE kenarı (3ST-A* pusulasıyla). *(WP-4, ana teknik hedef)*
8. 🔴 **`lunapath_ros`** — action server + `grid_map` yayıncısı + `rosbag2`. *(WSL2/Docker kurulumunu bir hafta önceden halledin.)*
9. 🟠 **`sensor_payload_w`** + LiDAR'lı/LiDAR'sız profil karşılaştırması. *(yarım gün, ⭐ özgün)*
10. 🔴 **ETH `lunar_planner`** + **Nav2 SmacPlanner2D** baseline kıyası. *(WP-5, iki bağımsız karşılaştırma)*
11. 🟠 **Yutu-2 / Pragyan doğrulaması** — `test_rover_validation.py`. *(WP-0/WP-5)*
12. 🟠 **Sanal LiDAR** (opsiyonel) — koridor arayüz testi + 3B demo.

**Sunumda anlatılacak ama yapılmayacak (Faz 2):** şans kısıtı (A5) · Nav2 C++ shim eklentisi · Space ROS · LiDAR yazılım yığını ve LuSNAR · algı yığını (E1–E3) · simülatör kurulumu (F1/OmniLRS).

---

## Sonraki aşamaya bırakılanlar

`docs/research/01`–`10` setinde ayrıntılı işlenmiş, bu belgede **bilinçli olarak kapsam dışı** tutulan konular. Kaybolmadılar; sırası geldiğinde ilgili belgeden alınacaklar.

| Konu | Nerede duruyor | Neden şimdi değil |
|---|---|---|
| **Radyasyon katmanı** (SVF + SEP senaryosu) | [06](06_radyasyon_verisi.md) | Yeni bir fizik ekseni; termal ve zaman ekseni oturmadan sıra gelmez |
| **Pürüzlülük + kaya bolluğu** kriterleri | [02](02_goruntu_isleme.md) §2.5, [07](07_termal_veri.md) | `CostMap` (§2.5) hazır olunca ucuz; ama önce mevcut 4 kriter doğru çalışmalı |
| **Maliyet ön-hesaplama + float32 + numba** | [08](08_global_local_rotalama_yuku.md) §2 | Performans; mevcut ölçekte darboğaz değil |
| **Üç seviyeli hiyerarşi / karo piramidi** | [08](08_global_local_rotalama_yuku.md) §3 | Ancak zaman ekseni + yüksek çözünürlük birlikte gelince zorunlu olur |
| **Anytime A* + admissibility testi** | [08](08_global_local_rotalama_yuku.md) §5–6 | Optimallik iddiasının kanıtı; rapor aşamasında |
| **Hesaplama bütçesi analizi** (RAD750/HPSC) | [08](08_global_local_rotalama_yuku.md) §4.3 | Sadece hesap tablosu; sunum haftasında yarım gün |
| **Slip / terramekanik düzeltmesi** | [05](05_engel_kacinma.md) §3.1 | Enerji modeli kalibrasyonu; EMRS (§6.4) verisiyle birlikte |
| **Safe haven erişilebilirliği** | [05](05_engel_kacinma.md) §4.4 | Şans kısıtının (§2.3) ucuz kuzeni; Faz 2 |
| **Footprint erozyonu** | [05](05_engel_kacinma.md) §6 | 80 m hücrede `k=1` çıkıyor — bugün etkisiz |
| **Veri disiplini** (provenance, lock, SBOM, lisans) | [01](01_sektorel_veri_kaynaklari.md), [04](04_acik_kaynak_modeller.md) §1, §8 | Hijyen; teslim öncesi yarım gün |
| **A/B/C/D ablasyon protokolü** | [03](03_sentetik_minimum_veri.md) §4.2 | Gerçek veri (§1.1, §1.4) girdikten **sonra** anlamlı |
| **NASA-STD-7009 skorkart / TRL beyanı** | [09](09_olgunluk_kiyaslama.md) | Sunum çerçevesi; rapor aşamasında |
| **MMGIS eklentisi · cFS/F´ · Moon Trek ayrışması** | [10](10_sektorel_projeler_envanteri.md), [04](04_acik_kaynak_modeller.md) §6 | Konumlandırma; kod işi değil |
| **AYAP-2 misyon-bağımsızlığı + çok noktalı tur** | [`../rover_project/AYAP2_ANALIZ.md`](../rover_project/AYAP2_ANALIZ.md) | Ayrı bir kapsam kararı gerektiriyor |

---

## Kritik notlar

- **A2 = B5** (aynı Sun-Synchronous makalesi; hem planlama hem termal başlığına giriyor).
- **A6** (ZRHT/载人航天 kısıtlar makalesi) linki **404** — DOI doğrulanmalı, entegrasyon planına dahil edilmedi.
- **E3** kaynak listesinde iki kez geçiyor (aynı makale, `arxiv 2603.17229`).
- **§H** (tehlike tespiti) `KAYNAK_HARITASI`'nda bilinçli boş bırakılmıştı → bu belgede **BÖLÜM 5** olarak, dürüst kapsam çerçevesiyle dolduruldu.
- **`heat1d` sürüm tuzağı:** PyPI'daki 0.3.1 (2020) README'deki özellikleri içermeyebilir → `Model.__init__` imzasını kurulumdan sonra **doğrulayın**; gerekirse GitHub `main`'den kurun.
- **FAST-LIO2 GPL-2.0** — MIT projemize bulaşma riski. KISS-ICP (MIT) veya LIO-SAM (BSD-3) tercih edin; seçimden önce `LICENSE` dosyasını **doğrulayın**.
- **LuSNAR spesifikasyonu:** kaynak haritasında "108 GB, 128-ışın LiDAR" kayıtlı ama makale özetinde geçmiyor → **teyit edin**.
- **`grid_map` eksen sırası:** sütun-öncelikli + `column_index`/`row_index` etiketleri; yanlış doldurma RViz'de 90° dönmüş harita üretir → **birim test yazın**.
- **ROS 2 sürüm:** **Jazzy Jalisco** (LTS→2029) önerilir. Kilted Kaiju Aralık 2026'da EOL. Lyrical Luth (May 2026 LTS) çok yeni.
- **Windows/WSL2:** depo Windows'ta; ROS 2 Jazzy Ubuntu 24.04 ister → WSL2 veya `osrf/ros:jazzy-desktop`. **Bir gün planlayın.**

### 🔴 Kod okumasından çıkan bulgu: gölge terimi pratikte ölü

Bu belgedeki iddiaları koda karşı doğrularken bir hata bulundu:

- `cost_engine.f_shadow(H_hours)` (satır 82) **kümülatif** gölge saati bekliyor; `h_max_shadow_h` ile normalize ediyor (LPR-1 için **50 saat**).
- `cost_engine.total_edge_cost()` (satır 276) bunu doğru şekilde `H_cumulative_hours` ile çağırıyor.
- Ama planlayıcının gerçekte kullandığı yol `compute_cost_grid()` (satır 341–348) ve orada `f_shadow`'a **tek kenarlık** değer gidiyor: `local_shadow_h = edge_shadow_hours(...)`.
- `pathfinder.py` kenar maliyetini `distance × (1 + (cost_grid[u] + cost_grid[v]) / 2)` ile hesaplıyor — yani **`total_edge_cost` değil, `compute_cost_grid` çıktısı** kullanılıyor.

**Sayısal sonuç (LPR-1, 80 m hücre, `v_max_ms = 0.2`, düz arazi):**

```
tek kenar suresi    = 80 / 0.2 = 400 s = 0.111 saat
f_shadow(0.111)     = (exp(3 × 0.111 / 50) − 1) / (exp(3) − 1) ≈ 0.00035
w_shadow katkisi    = 0.142 × 0.00035 ≈ 0.00005
```

Tipik hücre maliyeti O(0.1–1) mertebesinde olduğuna göre, **gölge kriteri toplam maliyete ~%0.01 katkı yapıyor** — yani AHP ağırlıklarında 0.142 pay verilmiş bir kriter, planlama kararını **fiilen hiç etkilemiyor.**

**Neden bu önemli:** LunaPath'in ana iddiası "gölge ve termal farkındalıklı planlama". Dört kriterden biri sessizce devre dışı.

**İki çözüm yolu:**
1. **Kısa vadeli (yarım gün):** `compute_cost_grid` içindeki `f_shadow` çağrısını hücre-yerel gölge yoğunluğu ölçeğine göre yeniden normalize edin (kenar süresi değil, hücrenin gölge oranı × tipik ikamet süresi), ya da `w_shadow`'u bu ölçeğe göre yeniden kalibre edin. Her iki durumda da **doğrulama tablosuna bir satır ekleyin.**
2. **Doğru çözüm (§3.1 ile birlikte):** `f_shadow` kümülatiftir — yani **yola bağlıdır**. Doğru yeri statik `cost_grid` değil, A*'ın **durum bilgili** genişletme adımıdır. Zaman ekseni (§3.1) eklendiğinde `H` doğal olarak durumun bir parçası olur ve terim kendiliğinden anlamlanır.

---

*Bu belge `KAYNAK_HARITASI.md` (12 Ağustos 2026) üzerine kuruludur; BÖLÜM 4 (ROS 2) ve BÖLÜM 5 (LiDAR) ek araştırmayla yazılmıştır. Açık kaynak sürümleri, lisanslar ve veri ürünleri değişir — **entegrasyondan önce güncel lisans/sürümü doğrulayın.** ROS 2 dağıtım tarihleri ve destek pencereleri Ağustos 2026 itibarıyla geçerlidir.*
