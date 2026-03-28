# LunaPath — Proje Referans ve Geliştirme Belgesi

> **Bu belgenin amacı:** Proje ekibinde her modülü geliştiren kişinin ortak bir zemin üzerinden ilerleyebilmesi için hazırlanmış iç teknik referanstır. Submit edilecek döküman değildir. Modül geliştiricileri bu belgeyi LLM'lerine veya IDE'lerine doğrudan bağlam olarak verebilir.
>
> **Versiyon:** 1.0 — Hackathon Başlangıç Kararları
>
> **Durum:** Temel kararlar netleştirilmiş. Kontrollü açık alanlar ayrıca işaretlenmiştir.

---

## 1. Projenin Özeti

LunaPath, Ay yüzeyinde görev yapan otonom keşif araçları için termal güvenlik ve enerji verimliliğini birlikte optimize eden adaptif bir rota planlama sistemidir.

Klasik rota planlama "en kısa yolu bul" problemini çözer. LunaPath bunu "görevi tamamlamak için en güvenli ve sürdürülebilir yolu bul" problemine dönüştürür. Yani mesafe tek kriter değildir; eğim, yüzey zorluğu, termal risk ve enerji maliyeti maliyet fonksiyonuna dahildir.

**Temel iddia:** Aynı başlangıç-bitiş noktası için üretilen "kısa ama riskli" rota ile "daha uzun ama termal olarak güvenli" rota arasındaki farkı sayısal olarak göstermek ve ikinci rotanın neden görev başarısı için daha iyi bir seçim olduğunu kanıtlamak.

---

## 2. Problem Tanımı

### 2.1 Neden Bu Problem Önemli

Ay yüzeyinde, özellikle güney kutbuna yakın bölgelerde iki tür tehlikeli alan bulunur:

- **PSR (Permanently Shadowed Regions):** Güneş ışığı hiç ulaşmayan, sıcaklığın –200°C altına düşebildiği krater tabanları ve derin gölgeli bölgeler.
- **Yüksek eğimli geçitler:** Rover'ın batarya kapasitesini ve mekanik yükünü kritik düzeyde artıran alanlar.

Bu koşullarda "en kısa rota" neredeyse her zaman donanım arızası riskini beraberinde getirir. Rover'ın hedefe ulaşması yetmez; yolda görev dışı kalmaması da aynı derecede kritiktir.

### 2.2 Mevcut Çözümlerin Nesi Eksik

Standart path planning algoritmaları (Dijkstra, A*, RRT) engelden kaçar ve mesafeyi minimize eder. Termal risk, enerji maliyeti veya donanım toleransı bu algoritmalarda birinci sınıf kriter olarak ele alınmaz. LunaPath bu boşluğu doldurmayı hedefler.

### 2.3 LunaPath'in Değer Önerisi

> Rover sadece ilerlemez; sağlıklı kalarak ilerler.

---

## 3. Teknik Kararlar (Netleştirilmiş)

Bu bölümdeki kararlar sabittir. Geliştirme sırasında bu kararlarla çelişen alternatif yaklaşımlar üretilmemelidir.

### 3.1 Sistem Çalışma Modu: Semi-Dynamic / Adaptif

Sistem **tamamen statik** (sadece görev öncesi planlama) değildir; **tam gerçek zamanlı** (sürekli sensör okuyan ağır otonomi) da değildir.

Seçilen mod: **Event-triggered replanning** (olay tetiklemeli yeniden planlama)

| Aşama | Davranış |
|---|---|
| Görev başlangıcı | İlk rota hesaplanır ve kullanıcıya sunulur |
| Görev sırasında (normal) | Rota sabit kalır, sistem izler |
| Olay tetiklendiğinde | Koşul değişimi algılanır, yeniden planlama çalıştırılır |
| Yeniden planlama sonrası | Güncellenmiş rota çıktısı üretilir |

Tetikleyici olaylar (demo aşamasında kullanıcı tarafından manuel, ileride otomatik):
- Rota üzerinde bir noktada termal riskin eşik değeri aşması
- Yeni bir engelin güzergaha eklenmesi
- Enerji maliyetinin kabul edilemez düzeye çıkması

**Geliştirici notu:** İlk iterasyonda olay tetikleyicisi manuel (frontend slider/buton) olacak. Otomatik tetikleme ikinci fazda ele alınacak.

---

### 3.2 Veri Modeli: Pre-loaded Environmental Layers

Sistem **canlı API'den veri çekmez.** Tüm çevresel veri, sistem başlatılmadan önce katman dosyaları olarak hazırlanır ve yüklenir.

Kullanılacak katmanlar:

| Katman | Kaynak | Format | Durum |
|---|---|---|---|
| Topoğrafya / Yükseklik (DEM) | NASA LOLA | GeoTIFF veya numpy array | Kullanılacak |
| Eğim haritası | DEM'den türetilir | 2D array | Hesaplanacak |
| PSR / Gölge alanları | Bilinen statik PSR veri seti | Binary maske katmanı | Statik (basitleştirilmiş) |
| Termal risk haritası | PSR + model kural tabanlı | Float array | Hesaplanacak |
| Yüzey zorluğu (traversability) | Eğim + kaya yoğunluğu heuristiği | Float array | Hesaplanacak |

**Önemli:** Anlık ve tam fizik tabanlı gölge hesabı şu aşamada kapsam dışıdır. Gölge/PSR bileşeni "statik risk maskesi" olarak temsil edilir. Bu bileşen projenin **kontrollü açık alanlarından** biridir (bkz. Bölüm 9).

---

### 3.3 Optimizasyon Algoritması: Multi-Criteria Weighted A*

Sistem klasik en kısa yol problemi çözmez. Kullanılan algoritma **çok kriterli maliyet fonksiyonuyla çalışan A* türevidir.**

#### Maliyet Fonksiyonu

```
total_cost(n) = g(n) + h(n)

g(n) = Σ [ w_dist * dist(i, i+1)
         + w_slope * slope_cost(i)
         + w_thermal * thermal_risk(i)
         + w_energy * traversal_energy(i) ]

h(n) = w_dist * euclidean_distance(n, goal)
```

| Ağırlık | Anlamı | Varsayılan |
|---|---|---|
| `w_dist` | Mesafe maliyeti | 1.0 |
| `w_slope` | Eğim maliyeti | Ayarlanacak |
| `w_thermal` | Termal risk cezası | Ayarlanacak |
| `w_energy` | Enerji/geçiş zorluğu | Ayarlanacak |

Bu ağırlıklar **frontend slider'larından** kullanıcı tarafından ayarlanabilecektir. Farklı ağırlık kombinasyonları farklı rota stratejileri üretecek ve demo'da bu kontrast gösterilecektir.

**Termal risk "yasaklayıcı" mı, "cezalandırıcı" mı?**
Seçilen yaklaşım: **Cezalandırıcı maliyet + yumuşak yasaklama.**
- Termal risk skoru 0.0–1.0 arasında normalize edilir.
- `thermal_risk > 0.9` olan hücreler geçilemez olarak işaretlenir (hard constraint).
- `0.5 < thermal_risk < 0.9` olan hücreler yüksek cezalı ama geçilebilir kalır (soft penalty).

---

### 3.4 Termal Güvenlik Modeli

#### Referans Rover Seçimi (Araştırma Aşamasında)

Hedef: Açık kaynak teknik dökümanlarda ulaşılabilir gerçek bir rover referansı seçmek. Aday rover'lar:
- **NASA VIPER** (Ay güney kutbu misyonu için tasarlanmış, en uygun bağlam)
- **Yutu-2** (Chang'e-4, gerçek görev verisi mevcut)
- **ESA PROSPECT** bağlantılı rover çalışmaları

Seçim kriteri: Termal tolerans sınırları (min/max çalışma sıcaklığı, kritik bileşenler için sınırlar) hakkında güvenilir ve atıf yapılabilir kaynak bulunması.

Eğer tatmin edici referans verisi bulunamazsa kullanılacak yedek model:

```python
# Literatür temelli genel rover termal profili (yedek)
THERMAL_PROFILE = {
    "safe_range_C": (-40, +60),         # Nominal çalışma aralığı
    "caution_range_C": (-80, -40),      # Kısıtlı çalışma, risk var
    "critical_below_C": -100,           # Bu altı geçilemez
    "cumulative_exposure_limit_min": 15 # Tehlikeli bölgede max bekleme
}
```

**Geliştirici notu:** Bu modelin savunulabilirliği önemlidir. Rover seçildiğinde bu dosya güncellenecek. Hangi rover seçildiği veya hangi varsayımlar kullanıldığı rapora not olarak eklenmeli.

---

### 3.5 Enerji Modeli

Tam batarya fiziği veya güneş paneli simülasyonu yapılmayacaktır. Seçilen yaklaşım: **Traversal cost tabanlı yaklaşık enerji modeli.**

```python
def energy_cost(slope_deg, distance_m, surface_difficulty):
    base = distance_m
    slope_penalty = base * (slope_deg / 10.0) ** 1.5
    surface_penalty = base * surface_difficulty  # 0.0–1.0
    return base + slope_penalty + surface_penalty
```

Bu model "daha dik = daha pahalı, daha zor yüzey = daha pahalı" mantığını uygular. Mutlak joule/watt değil; **göreli enerji maliyeti karşılaştırması** için kullanılır.

---

### 3.6 ML/AI Bileşeni

Proje "AI-assisted" olarak tanımlanmaktadır. Bu ifadenin teknik karşılığı:

- **Çekirdek path planning:** Weighted A* (heuristik arama, ML değil)
- **AI bileşeni:** Yardımcı katman — aşağıdaki alanlardan biri seçilecektir:

| Seçenek | Ne yapar | Karmaşıklık |
|---|---|---|
| Traversability scoring | Yüzey görüntüsü/verisinden geçilebilirlik skoru tahmin eder | Orta |
| Risk zone classification | Hücreleri risk sınıfına atar (safe/caution/danger) | Düşük-Orta |
| Cost weight tuning | Senaryo tipine göre ağırlıkları öneren basit model | Düşük |
| Replanning trigger prediction | Yeniden planlama gerekip gerekmeyeceğini önceden tahmin eder | Yüksek |

**Karar:** ML bileşeninin tam olarak hangi alt problemde kullanılacağı **kontrollü açık alan** olarak devam etmektedir. Ekip bu seçeneği hackathon'un ilk 12 saatinde netleştirmelidir.

**Geliştirici notu:** AI bileşeni abartılmamalı. "Bu sistemin her şeyi ML yapıyor" değil; "A* kararlarını destekleyen bir yardımcı AI katmanı var" çerçevesi korunmalıdır.

---

### 3.7 Otonomi Seviyesi

Sistem simülasyon ortamında **tamamen otonom** davranır:

- Rota üretme, risk değerlendirme, yeniden planlama kararlarını bağımsız alır.
- Operatör paneli izleme ve demo amaçlıdır; sistemin kararına müdahale etmez.
- Doğru ifade: `"fully autonomous at decision level within the simulation environment"`

Bu tanım gerçek saha/donanım entegrasyonu iddiası içermez. Simülasyon sınırları içinde geçerlidir.

---

## 4. Sistem Mimarisi

### 4.1 Yüksek Seviye Bileşen Diyagramı

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│   Mission Control Panel (React)                             │
│   - Başlangıç/bitiş nokta seçimi                           │
│   - Ağırlık slider'ları (w_thermal, w_slope, w_energy)     │
│   - Harita / rota görselleştirme                           │
│   - Senaryo değişimi / yeniden planlama tetikleyicisi      │
│   - Karşılaştırma paneli (güvenli rota vs. kısa rota)      │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP (REST)
┌───────────────────▼─────────────────────────────────────────┐
│                       BACKEND API                           │
│   FastAPI (Python)                                          │
│   - /plan   → ilk rota hesaplama                           │
│   - /replan → olay tetiklemeli yeniden planlama            │
│   - /compare → kısa rota vs. güvenli rota karşılaştırması  │
│   - /layers → çevresel katman verisi                       │
└───────────────────┬─────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                   CORE ENGINE (Python)                      │
│                                                             │
│  ┌──────────────────┐   ┌────────────────────────────────┐  │
│  │  Data Layer      │   │  Path Planning Engine          │  │
│  │  - DEM loader    │   │  - Multi-Criteria A*           │  │
│  │  - Risk map gen  │   │  - Cost function               │  │
│  │  - Thermal layer │   │  - Heuristic                   │  │
│  │  - Slope calc    │   │  - Grid management             │  │
│  └──────────────────┘   └────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────┐   ┌────────────────────────────────┐  │
│  │  Thermal Model   │   │  AI/ML Module (yardımcı)       │  │
│  │  - Rover profile │   │  - Traversability / Risk score │  │
│  │  - Risk scoring  │   │  - (alan netleşme sürecinde)   │  │
│  │  - PSR mask      │   │                                │  │
│  └──────────────────┘   └────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Replanning Manager                                  │   │
│  │  - Trigger detection                                 │   │
│  │  - Delta evaluation (mevcut rota hâlâ geçerli mi?)  │   │
│  │  - Yeni rota hesaplama + diff üretimi               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────┐
│                  PRE-LOADED DATA FILES                      │
│   /data/dem/          → LOLA DEM dosyaları                  │
│   /data/thermal/      → Termal risk katmanları              │
│   /data/psr/          → PSR maske dosyaları                 │
│   /data/scenarios/    → Demo senaryoları (JSON)             │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Veri Akışı — Normal Rota Hesaplama

```
1. Frontend → POST /plan
   { start: [lat, lon], goal: [lat, lon], weights: {thermal, slope, energy} }

2. Backend → Data Layer'ı yükle
   DEM, slope_map, thermal_map, psr_mask grid olarak belleğe al

3. Backend → Cost function hesapla
   Her grid hücresi için: cost = f(distance, slope, thermal_risk, energy)

4. Backend → A* çalıştır
   Multi-criteria cost fonksiyonu ile en düşük toplam maliyetli yolu bul

5. Backend → Çıktı üret
   { path: [...], total_cost: {...}, risk_profile: {...}, comparison: {...} }

6. Frontend → Görselleştir
   Rota haritada çizilir, risk profili panelde gösterilir
```

### 4.3 Veri Akışı — Yeniden Planlama

```
1. Kullanıcı olay tetikler (slider, buton) VEYA sistem olay algılar
   Örnek: "Rota üzerindeki X noktasında termal risk eşiği aşıldı"

2. Frontend → POST /replan
   { current_path: [...], trigger: "thermal_spike", affected_node: [i, j] }

3. Backend → Delta evaluation
   Mevcut rotanın geri kalanı hâlâ güvenli mi? Değilse ne kadarı etkilendi?

4. Backend → Partial veya full replan
   Etkilenen segmenti yeniden hesapla

5. Backend → Diff çıktısı
   { old_path_segment: [...], new_path_segment: [...], reason: "...", metrics_delta: {...} }

6. Frontend → Karşılaştırmalı göster
   Eski ve yeni rota segment overlay'i, neden değiştiği açıklaması
```

---

## 5. Modüller ve Sorumluluklar

Her modülü geliştiren kişi bu tabloyu bağlam olarak kullanabilir.

### Modül 1 — Data Layer & Preprocessing

**Ne yapar:** Ham veri dosyalarını (DEM, PSR, termal parametreler) okur, normalize eder, grid yapısına dönüştürür ve diğer modüllerin kullanabileceği numpy array'ler üretir.

**Girdi:**
- LOLA GeoTIFF veya CSV formatında DEM
- PSR binary maske dosyası
- Rover termal profil parametreleri (JSON/YAML)

**Çıktı:**
```python
{
  "elevation_grid": np.ndarray,   # shape: (H, W), metre cinsinden
  "slope_grid": np.ndarray,       # shape: (H, W), derece cinsinden
  "thermal_risk_grid": np.ndarray,# shape: (H, W), 0.0–1.0 normalize
  "psr_mask": np.ndarray,         # shape: (H, W), bool
  "traversability_grid": np.ndarray, # shape: (H, W), 0.0–1.0
  "metadata": {
    "resolution_m": float,        # Hücre başına metre
    "origin_lat": float,
    "origin_lon": float,
    "shape": (int, int)
  }
}
```

**Kritik kararlar:**
- Grid çözünürlüğü **50–100m/hücre** aralığında olacak (demo performansı için downsampling gerekli)
- Koordinat sistemi: LOLA pixel frame → coğrafi koordinat dönüşümü bu modülde yapılacak
- Veri normalize edilmiş formatta tutulacak; raw değerler ayrı dosyada kalacak

**Teknoloji önerisi:** `rasterio`, `numpy`, `scipy.ndimage` (eğim hesabı için)

**Bağımlılıklar:** Yok (bağımsız modül, diğerleri buna bağımlı)

---

### Modül 2 — Multi-Criteria A* Path Planning Engine

**Ne yapar:** Data Layer'dan aldığı grid'ler üzerinde çok kriterli maliyet fonksiyonu ile A* koşturur. Başlangıç-bitiş noktası verildiğinde en düşük maliyetli rotayı döndürür.

**Girdi:**
```python
{
  "grids": DataLayerOutput,        # Modül 1 çıktısı
  "start": (int, int),             # Grid koordinatları (row, col)
  "goal": (int, int),
  "weights": {
    "w_dist": float,
    "w_slope": float,
    "w_thermal": float,
    "w_energy": float
  },
  "hard_block_threshold": float    # Bu değer üstü hücreler geçilemez (ör. 0.9)
}
```

**Çıktı:**
```python
{
  "path": [(int, int), ...],        # Grid koordinat listesi
  "path_geo": [(float, float), ...],# Coğrafi koordinat listesi
  "total_distance_m": float,
  "total_thermal_exposure": float,
  "total_energy_cost": float,
  "max_slope_deg": float,
  "node_count": int,
  "computation_time_ms": float
}
```

**Kritik kararlar:**
- Heuristic fonksiyonu: Euclidean distance × `w_dist` (admissible kalması için sadece mesafe bileşeni)
- Hard block: `thermal_risk > hard_block_threshold` hücreleri A*'a kapalı düğüm olarak verilir
- Grid boyutu ~500×500 hücre hedefleniyor; bu boyutta A* performansı test edilmeli

**Teknoloji önerisi:** Saf Python veya `heapq` ile custom A*. `networkx` ağır olabilir, kaçınılmalı. İleride `numpy` vektörizasyonu ile hızlandırılabilir.

**Bağımlılıklar:** Modül 1 (Data Layer)

---

### Modül 3 — Thermal Risk Model

**Ne yapar:** Seçilen rover profilini ve çevresel verileri alarak her grid hücresi için termal risk skoru üretir. Data Layer bu skoru kullanarak `thermal_risk_grid`'i doldurur.

**Rover profil yapısı (JSON):**
```json
{
  "rover_id": "VIPER-simplified",
  "source": "NASA VIPER mission docs (sadeleştirilmiş)",
  "thermal_limits": {
    "operating_min_C": -40,
    "operating_max_C": 60,
    "caution_min_C": -80,
    "critical_min_C": -100,
    "survival_min_C": -150
  },
  "psr_exposure_limit_minutes": 15,
  "thermal_mass_factor": 1.0
}
```

**Risk skoru hesaplama mantığı:**
```python
def thermal_risk_score(cell_temp_C, psr_flag, rover_profile):
    if cell_temp_C < rover_profile["critical_min_C"]:
        return 1.0  # Hard block
    elif cell_temp_C < rover_profile["caution_min_C"]:
        # Caution zone — lineer interpolasyon
        risk = normalize(cell_temp_C, caution_min, critical_min)
        return 0.5 + risk * 0.4  # 0.5–0.9 arası
    elif psr_flag:
        return 0.3  # PSR ama kabul edilebilir sıcaklık
    else:
        return 0.0  # Güvenli
```

**Kontrollü açık alan:** Sıcaklık verisi statik/modelled olacak. Gerçek anlık sıcaklık akışı yok.

**Teknoloji önerisi:** Saf Python + numpy vektörel işlemler.

**Bağımlılıklar:** Modül 1 ham verisi + rover profil JSON

---

### Modül 4 — Replanning Manager

**Ne yapar:** Mevcut rotanın geçerliliğini sürekli kontrol eder (veya olay geldiğinde kontrol eder). Yeniden planlama gerekiyorsa hangi segmentin değişeceğini belirler ve Modül 2'yi çağırır.

**Girdi (olay tetiklendiğinde):**
```python
{
  "current_path": [(int, int), ...],
  "trigger_type": "thermal_spike" | "new_obstacle" | "energy_budget",
  "trigger_location": (int, int),    # Hangi hücrede olay oldu
  "updated_grids": DataLayerOutput   # Güncellenmiş veri (koşul değişiminden sonra)
}
```

**Çıktı:**
```python
{
  "replan_needed": bool,
  "affected_segment_start": int,   # Path listesindeki index
  "old_segment": [(int, int), ...],
  "new_segment": [(int, int), ...],
  "reason": str,
  "metrics_delta": {
    "distance_delta_m": float,
    "thermal_delta": float,
    "energy_delta": float
  }
}
```

**Kritik karar:** İlk fazda delta evaluation basit tutulacak: "tetik noktasından hedefe kadar olan segment yeniden hesaplanır." Tam partial replanning optimizasyonu ikinci faz.

**Teknoloji önerisi:** Python, Modül 2'yi çağırır.

**Bağımlılıklar:** Modül 2 (A* engine) + Modül 1 (güncel grid)

---

### Modül 5 — FastAPI Backend

**Ne yapar:** Tüm core engine modüllerini HTTP API olarak dışarı açar.

**Endpoint listesi:**

```
POST /api/plan
  Body: { start, goal, weights }
  Response: PathResult

POST /api/replan
  Body: { current_path, trigger_type, trigger_location, scenario_update }
  Response: ReplanResult

POST /api/compare
  Body: { start, goal }
  Response: { safe_path: PathResult, short_path: PathResult, comparison_metrics: {...} }

GET /api/layers
  Query: ?region=south_pole_demo
  Response: Serialized grid metadata (harita render için)

GET /api/scenarios
  Response: Mevcut demo senaryoları listesi

POST /api/scenarios/{id}/apply
  Body: {}
  Response: Güncellenmiş grid state
```

**Teknoloji önerisi:** `FastAPI` + `uvicorn`. CORS middleware eklenecek (React frontend için). Response formatı JSON.

**Bağımlılıklar:** Modül 1, 2, 4. Modül 3 Modül 1'in içinde.

---

### Modül 6 — Frontend (React)

**Ne yapar:** Mission Control Panel olarak çalışır. Kullanıcının rotayı görselleştirmesini, parametreleri ayarlamasını, senaryoları tetiklemesini ve karşılaştırma yapmasını sağlar.

**Bileşenler:**

| Bileşen | İşlev |
|---|---|
| `MapView` | Ay yüzeyi grid/haritası, rota overlay'i |
| `ControlPanel` | Ağırlık slider'ları, başlat/yeniden planla butonları |
| `MetricsPanel` | Termal risk, enerji, mesafe, karşılaştırma |
| `EventLog` | Yeniden planlama geçmişi, tetikleyiciler |
| `ScenarioSelector` | Demo senaryolarını yükle/tetikle |
| `ComparisonView` | Güvenli rota vs. kısa rota yan yana |

**Harita notu:** Leaflet.js kullanılabilir ancak standart tile layer değil; backend'den gelen grid verisi canvas layer veya GeoJSON overlay olarak render edilecek. Alternatif: `deck.gl` veya saf canvas. Bu karar modül geliştiricisine bırakılmıştır.

**Teknoloji önerisi:** React + Leaflet.js veya deck.gl + Chart.js (metrik grafikleri için) + Tailwind CSS

**Bağımlılıklar:** Modül 5 (API)

---

### Modül 7 — ML/AI Bileşeni (Araştırma Aşamasında)

**Durum:** Bu modülün tam problemi netleşme sürecindedir. Aşağıdaki seçeneklerden biri hackathon başında seçilecektir.

**Seçenek A — Traversability Scoring:**
Grid hücrelerini görsel/sayısal özelliklerden geçilebilirlik skoru ile sınıflandırır.
Öneri: Basit Random Forest veya gradient boosting, eğim + yüzey zorluğu özellik vektörü.

**Seçenek B — Risk Zone Classification:**
Hücreleri safe/caution/danger olarak etiketler. Termal modelin çıktısını doğrular veya zenginleştirir.
Öneri: Küçük CNN veya sklearn classifier, pre-trained ağırlıklar tercih edilir.

**Seçenek C — Cost Weight Suggestion:**
Senaryo tipine (keşif, acil, enerji koruma) göre ağırlık önerir.
Öneri: Kural tabanlı veya çok basit regresyon modeli.

**Teknoloji önerisi:** `scikit-learn` veya `PyTorch` (küçük model). Seçim yapıldıktan sonra bu bölüm güncellenecek.

---

## 6. Veri Modeli (API Kontrakt)

### 6.1 Temel Tipler

```python
# Koordinat: (row, col) grid formatı
GridCoord = Tuple[int, int]

# Coğrafi koordinat
GeoCoord = Tuple[float, float]  # (lat, lon)

# Ağırlık seti
Weights = {
    "w_dist": float,      # 0.0–2.0
    "w_slope": float,     # 0.0–2.0
    "w_thermal": float,   # 0.0–2.0
    "w_energy": float     # 0.0–2.0
}

# Rota sonucu
PathResult = {
    "path_geo": List[GeoCoord],
    "total_distance_m": float,
    "total_thermal_exposure": float,
    "total_energy_cost": float,
    "max_slope_deg": float,
    "risk_breakdown": {
        "safe_cells": int,
        "caution_cells": int,
        "danger_cells": int
    },
    "computation_time_ms": float
}
```

### 6.2 Karşılaştırma Çıktısı

```python
ComparisonResult = {
    "safe_path": PathResult,
    "shortest_path": PathResult,
    "delta": {
        "distance_overhead_pct": float,   # Güvenli rota ne kadar daha uzun
        "thermal_reduction_pct": float,   # Termal risk ne kadar azaldı
        "energy_delta_pct": float,        # Enerji farkı
        "recommendation": str             # "safe_path_preferred" | "paths_equivalent"
    }
}
```

---

## 7. Demo Senaryosu

### 7.1 Demo Alanı

**Hibrit yaklaşım:** Ay güney kutbu bölgesine benzer topoğrafik karaktere sahip, ancak kontrollü demo için termal/risk katmanları simüle edilmiş alan.

Demo alanı özellikleri:
- Derin krater (PSR alanı, yüksek termal risk)
- Orta eğimli geçit
- Güneşli düzlük (güvenli alan)
- Net başlangıç ve bitiş noktası: kısa yol krateri geçiyor, güvenli yol krater etrafını dolaşıyor

### 7.2 Demo Akışı

```
Adım 1 — Başlangıç:
  Kullanıcı haritada start ve goal seç.
  Varsayılan ağırlıklar ile /compare çağrısı yapılır.
  Ekranda iki rota gösterilir: kısa (kırmızı) ve güvenli (yeşil).
  MetricsPanel farkı sayısal gösterir.

Adım 2 — Ağırlık Deneyi:
  Kullanıcı w_thermal slider'ı düşürür → Sistem "daha riskli" rotaya kayar.
  w_thermal artırılır → Sistem uzun ama güvenli rotayı seçer.
  Bu dinamik özelliğin önemi anlatılır.

Adım 3 — Yeniden Planlama:
  Kullanıcı "thermal event" butonuna basar.
  Mevcut güvenli rotanın bir segmentinde termal risk yükseltilir.
  /replan çağrısı yapılır.
  Ekranda eski segment ve yeni segment ayrı renkte gösterilir.
  "Neden değişti" açıklaması EventLog'a düşer.

Adım 4 — Karşılaştırma Özeti:
  ComparisonView açılır.
  "Kısa rota %23 daha kısa AMA termal riskini %67 artırıyor" formatında özet.
```

---

## 8. Başarı Metrikleri

Sistem başarısı tek metrikle ölçülmez. Demo ve değerlendirmede şu kombinasyon kullanılacaktır:

| Metrik | Hesaplama | Beklenen Sonuç |
|---|---|---|
| Termal risk azalımı | `(short_thermal - safe_thermal) / short_thermal` | > %30 azalma |
| Enerji maliyeti farkı | `(safe_energy - short_energy) / short_energy` | < %20 artış (kabul edilebilir overhead) |
| Rota uzunluğu farkı | `(safe_dist - short_dist) / short_dist` | Gösterim amaçlı, negatif kabul edilmez |
| Yeniden planlama tepki süresi | `replan_computation_time_ms` | < 2000ms (demo için hedef) |
| Hard-blocked hücre oranı | `danger_cells / total_path_cells` | Güvenli rotada 0 olmalı |

---

## 9. Kontrollü Açık Alanlar

Bu alanlar kasıtlı olarak belirsiz bırakılmıştır. Üretim değerlendirmelerinde "araştırma gerektiren alan" olarak sunulacaktır.

| Alan | Mevcut Durum | Neden Açık |
|---|---|---|
| Gerçek zamanlı gölge hesabı | Statik PSR maskesi kullanılıyor | Güneş açısına bağlı dinamik model karmaşık, kapsam dışı |
| Benchmark rover'ın nihai adı | VIPER araştırılıyor, henüz confirm değil | Açık kaynak veri yeterliliğine bağlı |
| ML bileşeninin alt problemi | 3 seçenek var, hackathon başında seçilecek | Ekip kararı ve zaman kısıtına bağlı |
| Veri katmanı son çözünürlüğü | 50–100m hedefleniyor | Performans testine bağlı |
| Frontend harita motoru | Leaflet.js veya deck.gl | Grid render performansına bağlı |

---

## 10. Teknoloji Stack (Öneri)

> Bu stack önerisidir. Modül geliştiricisi kendi gereksinimlerine göre değiştirebilir, ancak değişiklik takımla paylaşılmalıdır.

| Katman | Önerilen | Alternatif |
|---|---|---|
| Backend API | FastAPI (Python) | Flask |
| Path Planning | Saf Python + heapq | Cython optimizasyonu |
| Veri işleme | numpy + rasterio | GDAL doğrudan |
| ML bileşeni | scikit-learn | PyTorch (küçük model) |
| Frontend framework | React | — |
| Harita/görselleştirme | Leaflet.js | deck.gl, Mapbox |
| Grafik/metrik | Chart.js | Recharts |
| Stil | Tailwind CSS | — |
| API test | Postman / httpie | — |
| Veri formatı | GeoTIFF, JSON, numpy .npy | — |

---

## 11. Geliştirme Ortamı Notları

### Koordinat Sistemi Dönüşümü (Kritik)

LOLA DEM verisi piksel koordinat sisteminde gelir. Leaflet coğrafi koordinat (lat/lon) bekler. Bu dönüşüm **Data Layer modülünde** yapılmalı ve tüm modüller aynı koordinat sistemini kullanmalıdır.

```python
def pixel_to_geo(row, col, metadata):
    lat = metadata["origin_lat"] + row * metadata["resolution_deg"]
    lon = metadata["origin_lon"] + col * metadata["resolution_deg"]
    return lat, lon
```

### Grid Boyutu ve Performans

Ham LOLA verisi çok yüksek çözünürlüklüdür. Demo için:
- Hedef: 500×500 veya 1000×1000 grid
- A* bu boyuttaki grid üzerinde Python'da 500ms–2s aralığında çalışmalı
- Eğer çok yavaşsa: öncelikle JIT (numba) veya scipy.sparse düşünülmeli

### Demo Senaryo Dosyaları

`/data/scenarios/` klasöründe JSON formatında hazırlanacak:
```json
{
  "scenario_id": "south_pole_demo_v1",
  "description": "Krater etrafı navigasyon, termal event ile yeniden planlama",
  "grid_region": "south_pole_500x500",
  "start_grid": [50, 50],
  "goal_grid": [450, 450],
  "thermal_events": [
    {
      "trigger_step": 2,
      "location": [200, 220],
      "new_thermal_risk": 0.95
    }
  ]
}
```

---

## 12. Sıkça Karşılaşılabilecek Teknik Sorunlar

| Sorun | Çözüm |
|---|---|
| A* çok yavaş | Grid'i downsample et, heapq yerine priority queue kütüphanesi kullan |
| LOLA veri koordinatı kayması | Metadata'daki origin ve resolution değerlerini dikkatlice doğrula |
| Leaflet'te grid render yavaş | Canvas layer kullan, GeoJSON yerine rasterize et |
| Termal risk tüm haritada 0 | PSR maskesi yanlış yüklenmiş, kontrol et |
| Replan çok uzun süre alıyor | Partial replan uygula, sadece etkilenen segmenti yeniden hesapla |
| Frontend-backend CORS hatası | FastAPI'ye `CORSMiddleware` ekle |

---

## 13. Proje Durumu Özeti

| Bileşen | Durum |
|---|---|
| Problem tanımı | ✅ Netleşti |
| Sistem mimarisi | ✅ Netleşti |
| Optimizasyon algoritması | ✅ Multi-criteria A* |
| Termal model yaklaşımı | ✅ Netleşti (rover seçimi araştırılıyor) |
| Enerji modeli | ✅ Netleşti (traversal cost) |
| Sistem çalışma modu | ✅ Semi-dynamic / event-triggered |
| Demo senaryosu | ✅ Hibrit (gerçek topo + simüle risk) |
| Başarı metrikleri | ✅ Çok metrikli karşılaştırma |
| ML bileşeni alt problemi | 🔄 Araştırma aşamasında |
| Gölge/PSR tam modeli | 🔄 Basitleştirilmiş (geliştirilebilir) |
| Veri katmanı son formatı | 🔄 Test edilecek |
| Harita render motoru | 🔄 Frontend kararı |

---

*Bu belge projenin yaşayan referans dokümanıdır. Teknik karar değişikliklerinde ilgili bölüm güncellenmeli ve tarih notu düşülmelidir.*
