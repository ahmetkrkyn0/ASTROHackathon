# LunaPath — Proje Referans ve Geliştirme Belgesi

> **Bu belgenin amacı:** Proje ekibinde her modülü geliştiren kişinin ortak bir zemin üzerinden ilerleyebilmesi için hazırlanmış iç teknik referanstır. Submit edilecek döküman değildir. Modül geliştiricileri bu belgeyi LLM'lerine veya IDE'lerine doğrudan bağlam olarak verebilir.
>
> **Versiyon:** 2.0 — Simülasyon & Kod Fazı (Matematik Finalize Edildi)
>
> **Önceki Versiyon:** 1.0 — Hackathon Başlangıç Kararları
>
> **Matematiksel Referans:** LunaPath_Final_Report_v3.2 (tüm formüller peer-review'den geçmiş final hali)
>
> **Durum:** Matematik donduruldu. Tüm sabitler, formüller ve ağırlıklar finalize. Artık simülasyon ve kod fazındayız.

---

## DEĞİŞİKLİK ÖZETİ (v1.0 → v2.0)

| Alan | v1.0 Durumu | v2.0 Durumu |
|---|---|---|
| Rover referansı | "Araştırılıyor" | ✅ LPR-1 (VIPER/MoonRanger bazlı), tüm parametreler sabitlendi |
| Maliyet fonksiyonu | Basit ağırlıklı toplam | ✅ 4-modüllü MRU [0,1] + Log-barrier + AHP ağırlıkları |
| Termal model | Kural-tabanlı risk skoru | ✅ Çift-sigmoid penalty + offset denge modeli + **sentetik termal grid** |
| Enerji modeli | `(slope/10)^1.5` heuristik | ✅ F_net kalibrasyonlu μ(θ) + fizik-bazlı |
| Gölge modeli | Statik PSR maskesi | ✅ Kümülatif üstel model + elevation proxy |
| AHP ağırlıkları | "Ayarlanacak" | ✅ Gradyan-bazlı: [0.409, 0.259, 0.142, 0.190] |
| Demo senaryoları | 1 genel demo | ✅ **1 DEM × 4 senaryo** (misyon profilleri) |
| ML bileşeni | "Seçenek araştırılıyor" | ⏳ Scope dışı — zaman kalırsa eklenecek |
| Sistem durumu | Planlama fazı | **→ Simülasyon & kod fazı** |

---

## 1. Projenin Özeti

LunaPath, Ay yüzeyinde görev yapan otonom keşif araçları için termal güvenlik ve enerji verimliliğini birlikte optimize eden adaptif bir rota planlama sistemidir.

Klasik rota planlama "en kısa yolu bul" problemini çözer. LunaPath bunu "görevi tamamlamak için en güvenli ve sürdürülebilir yolu bul" problemine dönüştürür. Mesafe tek kriter değildir; eğim, enerji, gölge ve termal risk maliyet fonksiyonuna dahildir — her biri fizik-bazlı modelle hesaplanır ve MRU [0,1] normalizasyonuyla tutarlı hale getirilir.

**Temel iddia:** Aynı başlangıç-bitiş noktası için farklı misyon profilleriyle (Enerji Tasarrufu, Hızlı Keşif, Gölge Geçiş, Dengeli) üretilen rotaların nasıl farklılaştığını ve her birinin hangi trade-off'ları yaptığını sayısal ve görsel olarak göstermek.

---

## 2. Netleştirilmiş Teknik Kararlar (Donmuş)

Bu bölümdeki tüm kararlar **sabittir**. v3.2 raporu ile tam uyumludur. Geliştirme sırasında bu kararlarla çelişen yaklaşımlar üretilmemelidir.

### 2.1 Referans Rover: LPR-1

Rover seçimi tamamlandı. LPR-1 (LunaPath Reference Rover), NASA VIPER ve CMU MoonRanger'dan türetilmiş kurgusal bir araçtır. Tüm sayısal değerler gerçek uzay araçlarına dayanır.

**SABİT DEĞERLER — Bu değerler constants.py'de aynen kullanılacak:**

```python
# ===== LPR-1 ROVER SABİTLERİ (v3.2 Final) =====

# Mekanik
ROVER_MASS_KG = 450              # VIPER: 447 kg roving mass
GRAVITY_MOON = 1.62              # m/s² (Ay yerçekimi)
V_MAX_MS = 0.2                   # m/s (VIPER: 0.72 km/h)

# Enerji
P_BASE_W = 200                   # W (düz zemin sürüş gücü)
P_PEAK_W = 450                   # W (peak güç)
E_CAP_WH = 5420                  # Wh (batarya kapasitesi @ 0°C start of life)
P_IDLE_W = 40                    # W (gölgede idle: elektronik + iletişim)
P_HEATER_W = 25                  # W (Kapton ısıtıcılar)
P_SHADOW_W = 65                  # W (idle + heater, aktif gölge sürüşü)
P_HIBERNATE_W = 108              # W (hibernate mod: idle + heater + termal yönetim)
P_SOLAR_W = 410                  # W (güneş paneli, NASA PIP TBR conservative)
REGEN_EFFICIENCY = 0.10          # %10 (Ay regolith gerçekliği — ESKİ: 0.30)

# Eğim Limitleri
SLOPE_COMFORTABLE_DEG = 15       # Rahat operasyon limiti
SLOPE_MAX_DEG = 25               # Mutlak limit (>25° = INF cost)
SLOPE_LATERAL_MAX_DEG = 18       # Devrilme limiti

# Gölge / Batarya
H_MAX_SHADOW_H = 50              # saat (NASA operasyonel limit — ESKİ: 96)
H_DESIGN_SHADOW_H = 70           # saat (safe haven tasarım kriteri)
SOC_MIN_PCT = 0.20               # Minimum batarya eşiği (%20)

# Termal
THERMAL_TAU_S = 7200             # saniye (termal zaman sabiti — ESKİ: 1800)
THERMAL_OFFSET_COLD = 60         # °C (T_surface < 0°C → T_eq = T_surface + 60)
THERMAL_OFFSET_HOT = -40         # °C (T_surface ≥ 0°C → T_eq = T_surface - 40)
BAT_OP_MIN_C = 0                 # Batarya operasyon min
BAT_OP_MAX_C = 35                # Batarya operasyon max
ELEC_OP_MIN_C = -10              # Elektronik operasyon min
ELEC_OP_MAX_C = 40               # Elektronik operasyon max

# Enerji Modeli
F_NET_N = 210                    # N (net çekiş kuvveti, iki bağımsız kalibrasyondan)
MU_COEFF = 3.471                 # = m * g_M / F_net (enerji çarpanı katsayısı)

# AHP Default Ağırlıklar (v3.2 gradyan-bazlı)
W_SLOPE = 0.409
W_ENERGY = 0.259
W_SHADOW = 0.142
W_THERMAL = 0.190

# Log-Barrier
LOG_BARRIER_MU = 0.1             # μ parametresi (ayarlanabilir, başlangıç değeri)
```

### 2.2 Maliyet Fonksiyonu (Final)

Sistem çok kriterli maliyet fonksiyonuyla çalışan A* kullanır. Her edge'in maliyeti 4 penalty bileşeninin AHP-ağırlıklı toplamı artı log-barrier cezasıdır.

```
C(a→b) = w₁·f_slope(θ) + w₂·f_energy(θ,d) + w₃·f_shadow(H) + w₄·f_thermal(T) + J_penalty

Eğer θ > 25° → C = INF (geçilemez)
Aksi halde   → C = max(0.01, C)
```

**Edge vs. Node ayrımı (KRİTİK):**
- f_slope ve f_energy → **edge-bazlı** (iki düğüm arasındaki geçişe bağlı)
- f_shadow ve f_thermal → **node-bazlı** (hedef düğümün konumuna bağlı)

### 2.3 Her Bir Penalty Fonksiyonunun Tam Tanımı

Aşağıda her penalty'nin implementasyon-hazır formülasyonu verilmiştir. Tüm değerler [0,1] MRU aralığındadır.

#### 2.3.1 f_slope — Eğim Penalty

```python
import math

def f_slope(theta_deg):
    """
    Sigmoid bazlı eğim penalty'si. MRU [0,1].
    theta_deg: iki düğüm arasındaki eğim açısı (derece)
    """
    if theta_deg > 25.0:
        return float('inf')  # GEÇILEMEZ
    return 1.0 / (1.0 + math.exp(-0.4 * (theta_deg - 15.0)))
```

**Doğrulama tablosu:**
| θ | f_slope | Durum |
|---|---|---|
| 5° | 0.018 | Güvenli |
| 10° | 0.119 | Rahat |
| 15° | 0.500 | Geçiş noktası |
| 20° | 0.881 | Tehlikeli |
| 25° | 0.982 | Limit |
| >25° | ∞ | HARD FAIL |

#### 2.3.2 f_energy — Enerji Penalty

```python
import math

def f_energy(theta_deg, d_m):
    """
    Fizik-bazlı enerji penalty'si. MRU [0,1].
    theta_deg: eğim açısı (derece)
    d_m: iki düğüm arası yatay mesafe (metre, grid çözünürlüğü)
    
    Dönüş: edge enerji tüketiminin batarya yüzdesine oranı
    """
    theta_rad = math.radians(theta_deg)
    
    # Güç çarpanı (F_net kalibrasyonlu)
    mu = 1.0 + 3.471 * math.sin(theta_rad)
    
    # Hız modeli (final seçim: sadece geometrik yavaşlama)
    v = 0.2 * math.cos(theta_rad)  # m/s
    
    # Gerçek yüzey mesafesi
    L = d_m / math.cos(theta_rad)  # metre
    
    # Geçiş süresi
    t_s = L / v  # saniye
    
    # Enerji tüketimi
    E_wh = 200.0 * mu * t_s / 3600.0  # Wh
    
    # MRU normalizasyon (batarya yüzdesi)
    return E_wh / 5420.0
```

**⚠️ ÖNEMLİ NOT:** Per-edge f_energy değerleri (50m grid'de ~0.003–0.006) diğer penalty'lere kıyasla çok küçüktür. Bu fiziksel olarak doğrudur — tek bir adım bataryanın %0.3-0.6'sını tüketir. Enerji etkisi kümülatiftir ve uzun rotalarda fark yaratır. Lokal karar seviyesinde slope ve thermal dominant olacaktır. Bu **tasarım tercihidir**, hata değildir.

#### 2.3.3 f_shadow — Gölge Penalty

```python
import math

def f_shadow(H_hours):
    """
    Kümülatif üstel gölge penalty'si. MRU [0,1].
    H_hours: rota boyunca toplam gölge süresi (saat)
    
    H_max = 50 saat (NASA operasyonel limit)
    lambda = 3 (üstel keskinlik)
    """
    LAMBDA = 3.0
    H_MAX = 50.0
    
    if H_hours >= H_MAX:
        return 1.0
    if H_hours <= 0:
        return 0.0
    
    return (math.exp(LAMBDA * H_hours / H_MAX) - 1.0) / (math.exp(LAMBDA) - 1.0)
```

**Gölge süresi tahmini (elevation proxy — DEM'den):**

```python
def estimate_shadow_hours(elev_norm, delta_t_hours):
    """
    elev_norm: normalize edilmiş elevasyon [0,1] (0=en alçak, 1=en yüksek)
    delta_t_hours: bu node'da geçirilen süre (saat)
    
    ⚠️ Bu bir KABA PROXY'dir — elevasyon gölgenin nedeni değil sonucudur.
    Offline illumination fraction haritası her zaman tercih edilmelidir.
    
    Dönüş: boyutsuz karanlık oranı × süre = gölge süresi katkısı (saat)
    """
    darkness_ratio = 1.0 - elev_norm  # boyutsuz [0,1]
    return darkness_ratio * delta_t_hours  # saat
```

**Doğrulama tablosu:**
| H (saat) | f_shadow | Risk |
|---|---|---|
| 0 | 0.000 | Yok |
| 12 | 0.055 | Düşük |
| 25 | 0.182 | Orta |
| 37 | 0.430 | Yüksek |
| 50 | 1.000 | Ölümcül |

#### 2.3.4 f_thermal — Termal Penalty

```python
import math

def sigmoid(x):
    if x > 500: return 1.0
    if x < -500: return 0.0
    return 1.0 / (1.0 + math.exp(-x))

def f_thermal(T_surface_C):
    """
    Çift-sigmoid termal penalty. MRU [0,1].
    T_surface_C: yüzey sıcaklığı (°C)
    
    Önce yüzey → iç sıcaklık dönüşümü yapılır,
    sonra batarya (%60) ve elektronik (%40) bileşenleri hesaplanır.
    """
    # Yüzey → iç sıcaklık dönüşümü (offset modeli)
    if T_surface_C < 0:
        T_inner = T_surface_C + 60  # ısıtıcılar aktif
    else:
        T_inner = T_surface_C - 40  # radyatör aktif
    
    # Batarya penalty (op. range: 0°C – 35°C)
    S_bat = sigmoid(0.3 * (0 - T_inner)) + sigmoid(0.3 * (T_inner - 35))
    
    # Elektronik penalty (op. range: -10°C – 40°C)
    S_elk = sigmoid(0.25 * (-10 - T_inner)) + sigmoid(0.25 * (T_inner - 40))
    
    # Ağırlıklı bileşim
    return 0.6 * S_bat + 0.4 * S_elk
```

**Doğrulama tablosu:**
| T_yüzey | T_iç | f_thermal | Durum |
|---|---|---|---|
| +60°C | +20°C | 0.011 | İdeal |
| -30°C | +30°C | 0.140 | Kabul edilebilir |
| -100°C | -40°C | 1.000 | Saturate (tehlike) |
| -180°C | -120°C | 1.000 | Saturate (ölümcül) |

#### 2.3.5 J_penalty — Log-Barrier (Katı Kısıtlar)

```python
import math

def log_barrier_penalty(theta_along, theta_lateral, soc, T_inner, mu=0.1):
    """
    Log-barrier ceza fonksiyonu. Limitlere yaklaştıkça → +∞.
    Boyutsuz slack formülasyonu: ln(1 - current/limit).
    
    mu: barrier şiddeti (küçük = daha sert duvar)
    """
    terms = []
    
    # Eğim (along-path < 25°)
    slack_slope = 1.0 - theta_along / 25.0
    if slack_slope <= 0: return float('inf')
    terms.append(math.log(slack_slope))
    
    # Lateral eğim (< 18°)
    slack_lat = 1.0 - theta_lateral / 18.0
    if slack_lat <= 0: return float('inf')
    terms.append(math.log(slack_lat))
    
    # SOC (> %20)
    slack_soc = 1.0 - 0.20 / soc if soc > 0 else -float('inf')
    if slack_soc <= 0: return float('inf')
    terms.append(math.log(slack_soc))
    
    # İç sıcaklık alt (-20°C < T)
    slack_t_low = (T_inner + 20) / 115.0
    if slack_t_low <= 0: return float('inf')
    terms.append(math.log(slack_t_low))
    
    # İç sıcaklık üst (T < 95°C)
    slack_t_high = (95 - T_inner) / 115.0
    if slack_t_high <= 0: return float('inf')
    terms.append(math.log(slack_t_high))
    
    return -mu * sum(terms)
```

### 2.4 AHP Ağırlıkları (Donmuş)

```
w = [w_slope, w_energy, w_shadow, w_thermal] = [0.409, 0.259, 0.142, 0.190]
```

Bu ağırlıklar penalty fonksiyonlarının gradyanlarından türetilmiştir. Frontend slider'ları bu ağırlıkları [0, 2] aralığında değiştirir. Slider default konumları: [0.818, 0.518, 0.284, 0.380].

---

## 3. SENTETİK TERMAL GRİD ÜRETİMİ (YENİ — v2.0)

DEM dosyasında yüzey sıcaklık verisi yok. Bu veriyi kendimiz üretiyoruz. Yaklaşım: DEM'deki elevasyon ve eğim verisinden fiziksel olarak anlamlı bir sentetik yüzey sıcaklık haritası türetmek.

### 3.1 Neden Sentetik?

Ay güney kutbunda yüzey sıcaklığını belirleyen iki ana faktör var: güneş görüş açısı (incidence angle) ve gölge süresi. İkisini de DEM'den tahmin edebiliriz — mükemmel değil, ama hackathon scope'unda savunulabilir.

### 3.2 Termal Grid Üretim Algoritması

```python
import numpy as np

def generate_thermal_grid(elevation_grid, slope_grid, aspect_grid, resolution_m):
    """
    DEM verisinden sentetik yüzey sıcaklık haritası üretir.
    
    Girdiler:
        elevation_grid: (H, W) float array, metre cinsinden elevasyon
        slope_grid:     (H, W) float array, derece cinsinden eğim
        aspect_grid:    (H, W) float array, derece cinsinden bakış yönü (0°=Kuzey, saat yönü)
        resolution_m:   grid çözünürlüğü (metre)
    
    Çıktı:
        thermal_grid:   (H, W) float array, °C cinsinden yüzey sıcaklığı
    
    Fiziksel Varsayımlar (Ay Güney Kutbu):
        - Güneş ufuktan ~1.5° ile gelir (çok alçak açı)
        - Güneş kabaca kuzeyden gelir (güney kutbunda)
        - Alçak bölgeler → daha fazla gölge → daha soğuk
        - Kuzeye bakan yamaçlar → daha fazla güneş → daha sıcak
        - Güneye bakan yamaçlar → daha az güneş → daha soğuk
        - Düz alanlar → nötr sıcaklık
    
    ⚠️ SINIRLAMALAR:
        - Bu gerçek bir termal model DEĞİLDİR. Ray-tracing veya ephemeris kullanmaz.
        - Horizon masking yok — komşu tepelerin gölgesi hesaplanmaz.
        - Zamana bağlı değişim yok — statik anlık snapshot.
        - Jüri sunumunda bu sınırlamalar açıkça belirtilmelidir.
    """
    H, W = elevation_grid.shape
    
    # === ADIM 1: Normalize elevasyon [0, 1] ===
    elev_min = np.nanmin(elevation_grid)
    elev_max = np.nanmax(elevation_grid)
    elev_norm = (elevation_grid - elev_min) / (elev_max - elev_min + 1e-10)
    
    # === ADIM 2: Baz sıcaklık — elevasyon bazlı ===
    # Mantık: Ay güney kutbunda alçak bölgeler PSR'a daha yakın → daha soğuk
    # Yüksek tepeler güneş alır → daha sıcak
    # Aralık: -180°C (en alçak/gölgeli) ile +80°C (en yüksek/aydınlık)
    T_min_base = -180.0  # PSR taban sıcaklığı
    T_max_base = 80.0    # Güneşli tepe sıcaklığı
    T_base = T_min_base + elev_norm * (T_max_base - T_min_base)
    
    # === ADIM 3: Aspect (bakış yönü) düzeltmesi ===
    # Güneş kuzeyden gelir → kuzeye bakan yamaçlar (aspect ~0° veya ~360°) daha sıcak
    # Güneye bakan yamaçlar (aspect ~180°) daha soğuk
    # cos(aspect) kullanımı: aspect=0° → cos=1 (kuzey, sıcak), aspect=180° → cos=-1 (güney, soğuk)
    aspect_rad = np.radians(aspect_grid)
    sun_factor = np.cos(aspect_rad)  # [-1, +1]
    
    # Eğim etkisi: dik yamaçlar bakış yönünden daha fazla etkilenir
    # Düz alan (slope=0) → sun_factor etkisiz
    slope_weight = np.clip(slope_grid / 25.0, 0.0, 1.0)  # normalize [0,1]
    
    # Aspect düzeltmesi: maksimum ±40°C (dik, kuzeye bakan yamaç vs güneye bakan)
    T_aspect_delta = sun_factor * slope_weight * 40.0
    
    # === ADIM 4: Lokal gölge proxy (komşu piksel yükseklik farkı) ===
    # Bir pikselin kuzey komşusu kendisinden yüksekse → güneşi engelliyor olabilir
    # Bu çok kaba bir horizon masking proxy'si
    shadow_penalty = np.zeros_like(elevation_grid)
    if H > 1:
        # Kuzey yönünden (üst satır) gelen gölge
        height_diff = np.zeros_like(elevation_grid)
        height_diff[1:, :] = elevation_grid[:-1, :] - elevation_grid[1:, :]
        # Pozitif fark = kuzey komşu daha yüksek = gölge olasılığı
        shadow_penalty = np.clip(height_diff / (resolution_m * 0.1), 0, 1) * (-30.0)
    
    # === ADIM 5: Birleştirme ===
    T_surface = T_base + T_aspect_delta + shadow_penalty
    
    # Fiziksel sınırlar: Ay yüzeyinde -250°C ile +130°C arası
    T_surface = np.clip(T_surface, -250.0, 130.0)
    
    return T_surface.astype(np.float32)
```

### 3.3 Termal Grid Doğrulama Kontrolleri

Üretilen termal grid'in anlamlı olduğunu doğrulamak için şu kontrolleri yapın:

```python
def validate_thermal_grid(thermal_grid, elevation_grid):
    """Termal grid'in fiziksel sınırlar içinde olduğunu doğrula."""
    
    print(f"Sıcaklık aralığı: {thermal_grid.min():.1f}°C — {thermal_grid.max():.1f}°C")
    print(f"Ortalama: {thermal_grid.mean():.1f}°C")
    print(f"Medyan: {np.median(thermal_grid):.1f}°C")
    
    # Beklenecekler:
    # - Min: -180°C civarı (krater tabanları)
    # - Max: +80°C civarı (güneşli tepeler)
    # - Ortalama: -50°C civarı (güney kutbu genel ortalaması)
    
    # Korelasyon kontrolü: elevasyon ile sıcaklık pozitif korelasyonlu olmalı
    corr = np.corrcoef(elevation_grid.flatten(), thermal_grid.flatten())[0, 1]
    print(f"Elevasyon-sıcaklık korelasyonu: {corr:.3f} (>0.5 beklenir)")
    
    # Risk dağılımı
    n_safe = np.sum(thermal_grid > -30)   # T_iç > +30°C → güvenli bölge
    n_caution = np.sum((thermal_grid <= -30) & (thermal_grid > -100))
    n_danger = np.sum(thermal_grid <= -100)
    total = thermal_grid.size
    print(f"Güvenli: {n_safe/total*100:.1f}%, Dikkat: {n_caution/total*100:.1f}%, Tehlikeli: {n_danger/total*100:.1f}%")
```

---

## 4. VERİ PİPELINE'I — DEM'DEN GRİD'LERE

### 4.1 Girdi: NASA LOLA DEM

DEM dosyası GeoTIFF formatında. Ay güney kutbu polar stereographic projeksiyonunda.

### 4.2 Preprocessing Pipeline

```python
import rasterio
import numpy as np
from scipy.ndimage import uniform_filter

def load_and_preprocess_dem(dem_path, target_resolution_m=50):
    """
    Ham DEM'i tüm grid katmanlarına dönüştürür.
    
    Çıktı: dict ile tüm grid'ler + metadata
    """
    with rasterio.open(dem_path) as src:
        elevation_raw = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        native_resolution = abs(transform.a)  # piksel başına metre (yaklaşık)
    
    # === Downsampling (performans için) ===
    if native_resolution < target_resolution_m:
        factor = int(target_resolution_m / native_resolution)
        # Block-average downsampling (scipy filter + stride)
        elevation = uniform_filter(elevation_raw, size=factor)[::factor, ::factor]
        actual_resolution = native_resolution * factor
    else:
        elevation = elevation_raw
        actual_resolution = native_resolution
    
    # === NoData handling ===
    elevation = np.where(elevation < -1e6, np.nan, elevation)
    
    # === Eğim hesaplama (derece) ===
    dy, dx = np.gradient(elevation, actual_resolution)
    slope = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))
    
    # === Aspect hesaplama (derece, 0°=Kuzey, saat yönü) ===
    aspect = np.degrees(np.arctan2(-dx, dy))  # atan2(-dx, dy) → kuzey=0
    aspect = (aspect + 360) % 360             # [0, 360) aralığına getir
    
    # === Termal grid (sentetik) ===
    thermal = generate_thermal_grid(elevation, slope, aspect, actual_resolution)
    
    # === Shadow proxy grid ===
    elev_norm = (elevation - np.nanmin(elevation)) / (np.nanmax(elevation) - np.nanmin(elevation) + 1e-10)
    shadow_ratio = 1.0 - elev_norm  # boyutsuz karanlık oranı [0,1]
    
    # === Traversability (geçilebilirlik) ===
    # Eğim > 25° → geçilemez, termal < -150°C → geçilemez
    traversable = np.ones_like(elevation, dtype=bool)
    traversable[slope > 25.0] = False
    traversable[thermal < -150.0] = False
    traversable[np.isnan(elevation)] = False
    
    return {
        "elevation": elevation,
        "slope": slope,
        "aspect": aspect,
        "thermal": thermal,
        "shadow_ratio": shadow_ratio,
        "traversable": traversable,
        "metadata": {
            "resolution_m": actual_resolution,
            "shape": elevation.shape,
            "transform": transform,
            "crs": str(crs),
            "dem_source": dem_path
        }
    }
```

### 4.3 Koordinat Dönüşümü (Piksel ↔ Coğrafi)

```python
def pixel_to_geo(row, col, transform):
    """Grid (row, col) → coğrafi (x, y) dönüşümü."""
    x = transform.c + col * transform.a + row * transform.e
    y = transform.f + col * transform.d + row * transform.e
    return x, y

def geo_to_pixel(x, y, transform):
    """Coğrafi (x, y) → grid (row, col) dönüşümü."""
    col = int((x - transform.c) / transform.a)
    row = int((y - transform.f) / transform.e)
    return row, col
```

**⚠️ KRİTİK:** LOLA verisi polar stereographic projeksiyonda. Leaflet WGS84 lat/lon bekler. Frontend'de `L.CRS.Simple` kullanın veya proj4js ile dönüşüm yapın. Detay Bölüm 7'de.

---

## 5. SENARYO SİSTEMİ — 1 DEM × 4 SENARYO

### 5.1 Konsept

Tek bir DEM dosyası yüklenir. Aynı harita üzerinde **4 farklı misyon profili** ile rota hesaplanır. Her profil farklı ağırlık seti ve kısıtlar kullanır. Demo'da bunların karşılaştırması yapılır.

### 5.2 Misyon Profilleri (Tanım)

```python
MISSION_PROFILES = {
    "balanced": {
        "name": "Dengeli Keşif",
        "description": "Tüm riskleri dengeli şekilde dikkate alan standart mod",
        "weights": {
            "w_slope": 0.409,
            "w_energy": 0.259,
            "w_shadow": 0.142,
            "w_thermal": 0.190
        },
        "constraints": {
            "max_shadow_h": 40,      # 50h × %80 güvenlik marjı
            "max_slope_deg": 25,
            "max_energy_wh": 4000,   # 5420 × %74 reserve
            "min_soc": 0.20
        },
        "color": "#3B82F6",  # mavi (frontend'de rota rengi)
        "priority": "Tüm kriterlerde kabul edilebilir denge"
    },
    
    "energy_saver": {
        "name": "Enerji Tasarrufu",
        "description": "Batarya korunmasını maksimize eden mod — dönüş enerjisi kritik",
        "weights": {
            "w_slope": 0.250,
            "w_energy": 0.450,
            "w_shadow": 0.150,
            "w_thermal": 0.150
        },
        "constraints": {
            "max_shadow_h": 30,
            "max_slope_deg": 20,     # Daha muhafazakâr eğim limiti
            "max_energy_wh": 2500,   # Çok düşük enerji bütçesi
            "min_soc": 0.35          # Yüksek SOC rezervi
        },
        "color": "#22C55E",  # yeşil
        "priority": "Minimum enerji tüketimi"
    },
    
    "fast_recon": {
        "name": "Hızlı Keşif",
        "description": "Zaman kısıtlı — en kısa rotayı bul, riskleri tolere et",
        "weights": {
            "w_slope": 0.500,
            "w_energy": 0.150,
            "w_shadow": 0.100,
            "w_thermal": 0.250
        },
        "constraints": {
            "max_shadow_h": 50,      # Tam limiti kullan
            "max_slope_deg": 25,
            "max_energy_wh": 5000,   # Neredeyse tam batarya
            "min_soc": 0.10          # Düşük SOC toleransı
        },
        "color": "#EF4444",  # kırmızı
        "priority": "Minimum mesafe/süre"
    },
    
    "shadow_traverse": {
        "name": "Gölge Geçiş",
        "description": "Gölgeli bölgeden geçmek zorunlu — termal güvenlik kritik",
        "weights": {
            "w_slope": 0.200,
            "w_energy": 0.150,
            "w_shadow": 0.300,
            "w_thermal": 0.350
        },
        "constraints": {
            "max_shadow_h": 45,
            "max_slope_deg": 25,
            "max_energy_wh": 4000,
            "min_soc": 0.25
        },
        "color": "#A855F7",  # mor
        "priority": "Termal güvenlik + gölge yönetimi"
    }
}
```

### 5.3 Senaryo Dosya Formatı (JSON)

```json
{
    "scenario_id": "south_pole_nobile_v1",
    "dem_file": "LOLA_SP_20m.tif",
    "description": "Nobile bölgesi — krater çevresi navigasyon",
    "grid_resolution_m": 50,
    "start_point": {"row": 50, "col": 50, "label": "Güneşli tepe - Base Camp"},
    "goal_point": {"row": 450, "col": 400, "label": "Krater yakını - Araştırma Noktası"},
    "profiles_to_run": ["balanced", "energy_saver", "fast_recon", "shadow_traverse"],
    "expected_outcomes": {
        "balanced": "Krater etrafından orta mesafeli rota",
        "energy_saver": "En geniş dolaşma, düz alandan geçiş",
        "fast_recon": "Krater kenarına yakın, kısa ama riskli",
        "shadow_traverse": "Gölge bölgeden geçen ama termal olarak güvenli"
    }
}
```

### 5.4 Senaryo Çalıştırma Akışı

```
1. DEM yükle → preprocess → tüm grid'ler hazır
2. Kullanıcı start/goal seçer (veya JSON'dan yükler)
3. Her profil için ayrı A* çalıştır (4 kez)
4. 4 rota + metriklerini döndür
5. Frontend: 4 rotayı aynı harita üzerinde farklı renklerle göster
6. Karşılaştırma tablosu: mesafe, enerji, max eğim, gölge süresi, hesaplama süresi
```

---

## 6. SİSTEM MİMARİSİ (Güncellenmiş)

### 6.1 Yüksek Seviye Bileşen Diyagramı

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                     │
│   - Harita (Leaflet.js) — DEM heatmap + 4 rota overlay     │
│   - Profil seçici: checkbox/toggle ile profil açma/kapama   │
│   - Slider paneli: ağırlık override (opsiyonel)             │
│   - Karşılaştırma tablosu: 4 profilin metrikleri           │
│   - Start/Goal seçimi: haritada tıklama                    │
│   - Senaryo yükleme: dropdown                              │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP (REST API)
┌───────────────────▼─────────────────────────────────────────┐
│                   BACKEND (FastAPI)                          │
│                                                             │
│  POST /api/plan                                             │
│    Body: { start, goal, profile_id }                        │
│    → Tek profil ile tek rota                                │
│                                                             │
│  POST /api/plan-multi                                       │
│    Body: { start, goal, profiles: ["balanced", ...] }       │
│    → Birden fazla profil ile birden fazla rota              │
│                                                             │
│  POST /api/compare                                          │
│    Body: { start, goal }                                    │
│    → 4 profilin tamamı + karşılaştırma metrikleri          │
│                                                             │
│  GET  /api/layers?layer=elevation|slope|thermal|shadow      │
│    → Grid katmanını frontend'e render için gönder           │
│                                                             │
│  GET  /api/scenarios                                        │
│    → Mevcut senaryo listesi                                │
│                                                             │
│  POST /api/scenarios/{id}/load                              │
│    → Senaryo DEM'ini yükle, grid'leri hazırla              │
│                                                             │
│  POST /api/replan                                           │
│    Body: { current_path, trigger, profile_id }              │
│    → Event-triggered yeniden planlama                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                   CORE ENGINE (Python)                       │
│                                                             │
│  ┌──────────────────┐   ┌──────────────────────────────┐    │
│  │ data_loader.py   │   │ cost_engine.py               │    │
│  │ - DEM okuma      │   │ - f_slope()                  │    │
│  │ - Downsampling   │   │ - f_energy()                 │    │
│  │ - Slope/aspect   │   │ - f_shadow()                 │    │
│  │ - Termal grid    │   │ - f_thermal()                │    │
│  │ - Shadow ratio   │   │ - log_barrier_penalty()      │    │
│  │ - Traversability │   │ - total_edge_cost()          │    │
│  └──────────────────┘   └──────────────────────────────┘    │
│                                                             │
│  ┌──────────────────┐   ┌──────────────────────────────┐    │
│  │ pathfinder.py    │   │ scenarios.py                 │    │
│  │ - A* algoritması │   │ - Senaryo yükleme            │    │
│  │ - Heuristic      │   │ - Profil yönetimi            │    │
│  │ - Grid traversal │   │ - Karşılaştırma metrikleri   │    │
│  │ - Path metrics   │   │ - JSON I/O                   │    │
│  └──────────────────┘   └──────────────────────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ constants.py                                         │   │
│  │ Tüm rover parametreleri + fizik sabitleri             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                   DATA FILES                                │
│   /data/dem/          → LOLA GeoTIFF DEM dosyaları          │
│   /data/scenarios/    → Senaryo JSON'ları                   │
│   /data/cache/        → Preprocessing cache (.npy)          │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 API Response Formatları

```python
# Tek rota sonucu
PathResult = {
    "profile_id": str,              # "balanced", "energy_saver", etc.
    "profile_name": str,            # "Dengeli Keşif"
    "path_pixels": List[List[int]], # [[row, col], ...]
    "path_geo": List[List[float]],  # [[x, y], ...] (projeksiyonlu koordinat)
    "color": str,                   # "#3B82F6"
    "metrics": {
        "total_distance_m": float,
        "total_energy_wh": float,
        "max_slope_deg": float,
        "total_shadow_hours": float,
        "max_thermal_risk": float,
        "path_length_nodes": int,
        "computation_time_ms": float
    }
}

# Karşılaştırma sonucu
CompareResult = {
    "scenario_id": str,
    "start": [int, int],
    "goal": [int, int],
    "results": List[PathResult],  # 4 profil sonucu
    "comparison": {
        "shortest_profile": str,       # En kısa rotayı üreten profil
        "safest_profile": str,         # En düşük risk toplam
        "most_efficient_profile": str, # En az enerji
        "recommendation": str          # Genel önerme metni
    }
}
```

---

## 7. FRONTEND NOTLARI

### 7.1 Harita Render

LOLA verisi polar stereographic projeksiyonda. Leaflet normalde WGS84 lat/lon bekler. İki seçenek var:

**Seçenek A (ÖNERİLEN — Basit):** `L.CRS.Simple` kullanarak piksel koordinat sisteminde çalış. Haritayı düz bir resim gibi göster. Overlay'ler piksel (row, col) ile çizilir. Coğrafi anlam yerine grid indeksleri kullanılır.

**Seçenek B (Gelişmiş):** `proj4leaflet` ile polar stereographic → WGS84 dönüşümü yap. Gerçek lat/lon göster. Daha karmaşık ama jüride daha etkileyici.

### 7.2 Katman Render

Backend'den gelen grid verileri canvas tile olarak render edilmeli. GeoJSON çok ağır olur. Yaklaşım:

```
1. Backend → GET /api/layers?layer=thermal → PNG (renklendirilmiş) veya raw float array
2. Frontend → Canvas overlay ile harita üzerine bindirme
3. Rota çizimi: L.Polyline ile her profilin path_pixels'ini çiz
```

### 7.3 UI Bileşenleri

| Bileşen | İşlev | Öncelik |
|---|---|---|
| MapView | DEM + rota overlay + 4 renkli rota | 🔴 Zorunlu |
| ProfileSelector | 4 profilden hangilerinin gösterildiğini seç | 🔴 Zorunlu |
| ComparisonTable | Metrikleri yan yana karşılaştır | 🔴 Zorunlu |
| SliderPanel | Ağırlık override (custom profil) | 🟡 İstenir |
| ScenarioLoader | JSON senaryolarını yükle | 🟡 İstenir |
| ReplanButton | Event-triggered yeniden planlama | 🟢 Bonus |

---

## 8. UYGULAMA PLANI — DETAYLI

### AŞAMA 0: Proje İskeleti ve Sabitler (⏱️ ~2 saat)

**Kim:** Backend geliştirici

**Ne yapılacak:**
1. Proje dizin yapısı oluştur:
   ```
   lunapath/
   ├── backend/
   │   ├── app/
   │   │   ├── main.py          # FastAPI app
   │   │   ├── constants.py     # Tüm sabitler (§2.1'den kopyala)
   │   │   ├── cost_engine.py   # 4 penalty + log-barrier
   │   │   ├── data_loader.py   # DEM preprocessing
   │   │   ├── pathfinder.py    # A* implementasyonu
   │   │   ├── scenarios.py     # Senaryo/profil yönetimi
   │   │   └── thermal_grid.py  # Sentetik termal grid üretimi
   │   ├── data/
   │   │   ├── dem/             # DEM dosyaları
   │   │   ├── scenarios/       # JSON senaryo dosyaları
   │   │   └── cache/           # Preprocessing cache
   │   └── requirements.txt
   ├── frontend/
   │   ├── src/
   │   │   ├── components/
   │   │   │   ├── MapView.jsx
   │   │   │   ├── ProfileSelector.jsx
   │   │   │   ├── ComparisonTable.jsx
   │   │   │   └── SliderPanel.jsx
   │   │   └── App.jsx
   │   └── package.json
   └── README.md
   ```
2. `constants.py`'yi §2.1'deki değerlerle doldur
3. `requirements.txt`: fastapi, uvicorn, rasterio, numpy, scipy
4. FastAPI boilerplate: CORS middleware, health check endpoint

**Çıktı:** Boş ama çalışan proje iskeleti.

### AŞAMA 1: Data Pipeline (⏱️ ~3 saat)

**Kim:** Backend geliştirici

**Ne yapılacak:**
1. `data_loader.py` — §4.2'deki `load_and_preprocess_dem()` fonksiyonunu implemente et
2. `thermal_grid.py` — §3.2'deki `generate_thermal_grid()` fonksiyonunu implemente et
3. DEM dosyasını yükle, downsample et, tüm grid'leri üret
4. Cache mekanizması: ilk yüklemede `.npy` olarak kaydet, sonraki çalıştırmalarda cache'den oku

**Test:** Tek DEM dosyası için tüm grid'lerin boyut ve değer aralıklarını doğrula (§3.3'teki `validate_thermal_grid`).

**Çıktı:** DEM → 6 grid (elevation, slope, aspect, thermal, shadow_ratio, traversable) pipeline'ı çalışıyor.

### AŞAMA 2: Cost Engine (⏱️ ~3 saat)

**Kim:** Backend geliştirici (veya paralelde ikinci kişi)

**Ne yapılacak:**
1. `cost_engine.py` — §2.3'teki tüm fonksiyonları implemente et:
   - `f_slope(theta_deg)` → sigmoid
   - `f_energy(theta_deg, d_m)` → F_net kalibrasyonlu
   - `f_shadow(H_hours)` → kümülatif üstel
   - `f_thermal(T_surface_C)` → çift sigmoid
   - `log_barrier_penalty(...)` → boyutsuz slack
   - `total_edge_cost(node_a, node_b, grids, weights, H_cumulative)` → birleşik maliyet
2. Her fonksiyonu §2.3'teki doğrulama tablolarıyla test et

**Test:** Doğrulama tabloları ile birebir eşleşme. f_slope(15°)=0.500, f_shadow(25)=0.182, vs.

**Çıktı:** Bağımsız test edilebilir, doğrulanmış cost engine.

### AŞAMA 3: A* Pathfinder (⏱️ ~4 saat)

**Kim:** Backend geliştirici

**Ne yapılacak:**
1. `pathfinder.py` — Multi-criteria A* implementasyonu:
   ```python
   def astar(grids, start, goal, weights, constraints):
       """
       8-yönlü grid A*.
       - grids: preprocessing çıktısı
       - weights: profil ağırlıkları
       - constraints: max_shadow_h, max_slope_deg, max_energy_wh, min_soc
       
       Dönüş: PathResult dict
       """
   ```
2. Heuristic: Euclidean mesafe × minimum edge cost (admissible)
3. 8-yönlü komşuluk (diyagonal mesafe: d × √2)
4. Traversable maske kontrolü (geçilemez pikselleri atla)
5. Kümülatif H (gölge süresi) tracking: her node'da güncelle
6. Path metrics hesaplama: toplam mesafe, enerji, max eğim, gölge süresi

**Performans hedefi:** 500×500 grid'de <2 saniye.

**Test:** Basit 100×100 grid'de düz alan, eğimli alan ve engellenmiş alanlarda beklenen rotaları doğrula.

**Çıktı:** Çalışan A* pathfinder, profil ağırlıklarıyla rota üretiyor.

### AŞAMA 4: Senaryo Sistemi + API Endpoints (⏱️ ~2 saat)

**Kim:** Backend geliştirici

**Ne yapılacak:**
1. `scenarios.py` — §5.2'deki `MISSION_PROFILES` dict'ini tanımla
2. Senaryo JSON okuma/yazma
3. `POST /api/plan-multi` endpoint: start, goal, profiles listesi al → her biri için A* çalıştır → sonuçları döndür
4. `POST /api/compare` endpoint: 4 profil çalıştır + karşılaştırma metrikleri hesapla
5. `GET /api/layers` endpoint: grid verisini PNG veya JSON olarak döndür

**Test:** `curl` veya Postman ile tüm endpoint'leri test et. 4 farklı rota sonucu döndüğünü doğrula.

**Çıktı:** Tam çalışan API. Frontend bağlanmaya hazır.

### AŞAMA 5: Frontend — Harita ve Rota Görselleştirme (⏱️ ~4 saat)

**Kim:** Frontend geliştirici

**Ne yapılacak:**
1. `MapView.jsx` — Leaflet.js ile DEM heatmap render + 4 renkli rota polyline
2. `ProfileSelector.jsx` — Checkbox'larla profil göster/gizle toggle
3. `ComparisonTable.jsx` — 4 profilin metriklerini tablo olarak göster
4. Start/Goal seçimi: haritada tıklama ile seçim

**Kritik:** L.CRS.Simple kullan (başlangıçta). Piksel koordinatlarıyla çalış.

**Çıktı:** Haritada DEM gösterimi + 4 farklı renkte rota + karşılaştırma tablosu.

### AŞAMA 6: Slider Panel + Custom Profil (⏱️ ~2 saat)

**Kim:** Frontend geliştirici

**Ne yapılacak:**
1. `SliderPanel.jsx` — 4 slider (w_slope, w_energy, w_shadow, w_thermal)
2. Slider aralığı: [0, 2], default pozisyonları: [0.818, 0.518, 0.284, 0.380]
3. Slider değiştiğinde `POST /api/plan` ile custom ağırlıklarla yeni rota hesapla
4. Profil preset butonları: slider'ları otomatik ayarla

**Çıktı:** Kullanıcı slider'larla ağırlıkları değiştirip rotanın nasıl değiştiğini gerçek zamanlı görebiliyor.

### AŞAMA 7: Polish + Demo Hazırlığı (⏱️ ~2 saat)

**Kim:** Tüm ekip

**Ne yapılacak:**
1. Senaryo JSON dosyasını hazırla (anlamlı start/goal noktaları seç)
2. Performans optimizasyonu (grid cache, preprocessing bir kere)
3. UI polish: renk tutarlılığı, loading state'ler, hata handling
4. Demo script hazırla: "Önce balanced göster → energy_saver'a geç → farkı açıkla"
5. Jüri için konuşma noktaları: "VIPER-bazlı referans rover", "peer-reviewed formüller"

---

## 9. KONTROLLÜ AÇIK ALANLAR

| Alan | Mevcut Durum | Plan |
|---|---|---|
| Gerçek zamanlı gölge | Elevation proxy kullanılıyor | ⚪ Scope dışı, disclaimer ile belgelenmiş |
| ML bileşeni | Scope'tan çıkarıldı | ⚪ Zaman kalırsa: cost weight suggestion (Nelder-Mead) |
| Horizon masking | Yok | ⚪ Gelecek iterasyon |
| Replanning | Basit segment replanning | 🟡 Aşama 6 sonrasında zaman kalırsa |
| Solar degradasyon | Yok | ⚪ Gelecek iterasyon |

---

## 10. TEKNOLOJİ STACK (Final)

| Katman | Seçim | Not |
|---|---|---|
| Backend API | FastAPI + uvicorn | — |
| Path Planning | Python + heapq (A*) | networkx yok — çok ağır |
| DEM işleme | rasterio + numpy + scipy | — |
| Termal grid | numpy (sentetik üretim) | §3.2'deki algoritma |
| Frontend | React | — |
| Harita | Leaflet.js (L.CRS.Simple) | Piksel koordinat sistemi |
| Grafik/metrik | Chart.js veya Recharts | Karşılaştırma için |
| Stil | Tailwind CSS | — |
| Veri formatı | GeoTIFF → numpy .npy (cache) | — |

---

## 11. SIKÇA KARŞILAŞILACAK SORUNLAR

| Sorun | Çözüm |
|---|---|
| A* çok yavaş (>5s) | Grid'i 100m'ye downsample et. heapq yeterli olmazsa `sortedcontainers` veya Cython dene |
| DEM'de NaN bölgeleri | `traversable` mask'e ekle, A* bu pikselleri atlasın |
| Termal grid'de tüm değerler çok soğuk | `generate_thermal_grid`'deki T_min_base ve T_max_base'i ayarla. Aspect hesabını kontrol et |
| 4 rota çok benzer çıkıyor | Profil ağırlıkları arasındaki kontrast yeterli değil. w_energy'yi artır veya constraints'i daralt |
| Leaflet'te grid render çok yavaş | Canvas layer kullan, tile-based render yap. Grid'i 200×200'e bile düşürebilirsin — demo için yeterli |
| Frontend-backend CORS | FastAPI'ye `CORSMiddleware(allow_origins=["*"])` ekle |
| Rota haritanın dışına çıkıyor | Start/goal grid sınırları içinde mi kontrol et. Boundary check ekle |
| Eğim hesabında NaN'ler | `np.gradient` edge piksellerinde sorun çıkarabilir. NaN'leri sıfırla veya pad et |
| Log-barrier'da ln(0) hatası | slack ≤ 0 kontrolü ekle → INF döndür (§2.3.5'te zaten var) |

---

## 12. DOSYA/BELGE İLİŞKİSİ

| Dosya | İçerik | Kime Gerekli |
|---|---|---|
| `LPR1_Rover_Spesifikasyon_Belgesi.pdf` | Rover spec + sabit değerler + referanslar | Jüri sunumu, rapor yazımı |
| `LunaPath_Final_Report_v3_2.md` | Tam matematiksel formülasyon (peer-reviewed) | Akademik referans, formül detayı lazım olduğunda |
| **Bu belge** (`lunapath_referans_belgesi_2.md`) | İmplementasyon rehberi + çalışan kod şablonları | **Geliştirme sırasında ana referans** |

---

*Bu belge projenin yaşayan referans dokümanıdır. Versiyon: 2.0 — Simülasyon & Kod Fazı. Matematik dondurulmuştur (v3.2). Teknik karar değişikliklerinde ilgili bölüm güncellenmeli ve tarih notu düşülmelidir.*
