# 08 — Global / Local Rotalandırma ve Hesaplama Yükü

> **Soru:** LunaPath'in planlayıcısı ne kadar pahalı? Nerede koşacak — yerde mi, rover'da mı? Global ve yerel katmanlar arasındaki iş bölümü ne olmalı? Zaman ekseni eklenince maliyet ne olur?
>
> **Kısa cevap:** Hesaplama yükü, LunaPath'te **hiç konuşulmamış ama mimariyi belirleyen** kısıttır. Bugünkü A* bir masaüstünde çalışıyor; uçuş bilgisayarında ~400–1000× daha az bütçe var. İyi haber: LunaPath'in maliyet fonksiyonu **tamamen ön-hesaplanabilir** — 8 yönlü maliyet dizisi olarak vektörleştirilirse A*'ın iç döngüsü saf dizi okumasına iner ve 10–100× hızlanır. Kötü haber: zaman ekseni eklenince problem boyutu **K katına** çıkar ve tek düz grid çözümü çöker; hiyerarşi zorunlu hale gelir.

---

## 1. Bugünkü yükün anatomisi

### 1.1 Problem boyutu

| Büyüklük | Değer |
|---|---|
| Grid | 500 × 500 = **250.000 düğüm** |
| Komşuluk | 8-yönlü → **~2.000.000 kenar** |
| Katman sayısı | 7 |
| Bellek (float64) | 7 × 250.000 × 8 B = **14 MB** |
| Bellek (float32) | **7 MB** |
| Performans hedefi (referans belge §8, Aşama 3) | 500×500'de **< 2 saniye** |

### 1.2 Kenar başına gerçek maliyet

`total_edge_cost` (`cost_engine.py:252`) her kenar için şunları çağırıyor:

| Bileşen | Transandantal işlem |
|---|---|
| `f_slope` | 1 `exp` |
| `f_energy` | `sin`, `cos`, `cos`, 1 bölme (+ mesafe hesabı) |
| `f_shadow` | 2 `exp` |
| `f_thermal` | 4 `exp` (iki sigmoid çifti) |
| `log_barrier_penalty` | 5 `log` |
| **Toplam** | **~15 transandantal + ~20 aritmetik işlem** |

Bir düğüm genişletmesi 8 kenar → **~120 transandantal işlem**. Tam genişletme (worst case) → **~30 milyon transandantal işlem** + Python fonksiyon çağrı ek yükü.

**Saf Python'da fonksiyon çağrı ek yükü baskın:** kenar başına ~6 fonksiyon çağrısı × ~1 µs ≈ 6 µs → düğüm başına ~50 µs → 250.000 düğüm için **~12 saniye**. Yani mevcut mimari, kötü senaryoda 2 saniye hedefini **6× aşar**. (Gerçekte A* hedefe doğru heuristic ile daha az düğüm genişletir; `nodes_expanded` metriği kodda zaten mevcut — bunu **ölçün ve raporlayın.**)

---

## 2. En yüksek getirili optimizasyon: maliyeti tamamen ön-hesapla

Bu, LunaPath'in yapısındaki **kullanılmamış büyük bir fırsat**. Maliyet bileşenlerini ayrıştırın:

| Bileşen | Neye bağlı | Ön-hesaplanabilir mi? |
|---|---|---|
| `f_slope(θ_ab)` | Sadece a ve b hücrelerinin geometrisi | ✅ **Evet** — yön başına bir dizi |
| `f_energy(θ_ab, d)` | Aynı | ✅ **Evet** |
| `f_shadow(H)` | **Kümülatif** gölge süresi | ❌ Yola bağlı |
| `f_thermal(T_b)` | Sadece hedef hücre | ✅ **Evet** — tek dizi |
| `log_barrier(θ, SOC, T_iç)` | SOC ve T_iç **kümülatif** | ❌ Yola bağlı |

**Kritik gözlem:** `f_slope`, `f_energy` ve `f_thermal` — yani ağırlıkların **%85.8'i** (0.409 + 0.259 + 0.190) — tamamen yola bağımsızdır ve önceden hesaplanabilir.

```python
# backend/app/precompute.py (yeni)
import numpy as np

DIRS = [(-1,-1), (-1,0), (-1,1), (0,-1), (0,1), (1,-1), (1,0), (1,1)]

def precompute_edge_costs(elev, slope, thermal, res_m, weights):
    """8 yon icin (H, W) maliyet dizisi uret. Tamamen vektorel.
    A*'in ic dongusu bundan sonra sadece dizi okumasi yapar.

    Donus: dict[(dr,dc)] -> (H, W) float32 array
           edge_cost[(dr,dc)][r, c] = (r,c)'den (r+dr, c+dc)'ye gitme maliyeti
    """
    H, W = elev.shape
    f_th = f_thermal_vec(thermal)          # node-bazli, bir kez
    out = {}
    for dr, dc in DIRS:
        d_m = res_m * (2 ** 0.5 if dr and dc else 1.0)
        # kaydirilmis yukseklik farkindan gercek gecis egimi
        dz = shift(elev, dr, dc) - elev
        theta = np.degrees(np.arctan(np.abs(dz) / d_m))
        cost = (weights["w_slope"]  * f_slope_vec(theta)
              + weights["w_energy"] * f_energy_vec(theta, d_m)
              + weights["w_thermal"] * shift(f_th, dr, dc))
        cost[theta > 25.0] = np.inf          # hard constraint
        out[(dr, dc)] = cost.astype(np.float32)
    return out
```

**Maliyet:** 8 × 250.000 = 2M vektörel değerlendirme → numpy'da **~50–200 ms, bir kez**.
**Kazanç:** A*'ın iç döngüsü `cost = edge_cost[(dr,dc)][r, c]` — tek dizi indeksleme. Yola bağlı terimler (`f_shadow`, `log_barrier`) sadece **gerçekten genişletilen** düğümlerde hesaplanır.

Bu değişiklikle **2 saniye hedefi rahatça tutulur** ve `numba` bile gerekmeyebilir. Ayrıca **çoklu profil koşumu bedavaya yakın hale gelir**: 4 profil = 4 farklı ağırlık seti = 4 kez ön-hesaplama (toplam ~1 s) ama ardından 4 A* koşumu çok hızlı. `/api/compare` endpoint'inin performansı doğrudan iyileşir.

> **Uyarı — geometrik doğruluk:** Mevcut kod eğimi `np.gradient` ile hücre-merkezli hesaplıyor, sonra kenar için kullanıyor. Yukarıdaki ön-hesaplama **kenar boyunca gerçek yükseklik farkını** kullanıyor — bu daha doğrudur ve rotanın gerçek tırmanış açısını temsil eder. Geçiş yaparken metrikler değişecektir; bu bir hata değil, **düzeltmedir** ve belgelenmelidir.

---

## 3. Hiyerarşi: neden zorunlu, nasıl kurulur

### 3.1 Boyut patlaması

| Senaryo | Düğüm sayısı | Bellek (float32, 8 yön) | Değerlendirme |
|---|---|---|---|
| Bugün: 80 m, 40 km, statik | 250 K | 8 MB | ✅ Rahat |
| 20 m, 40 km, statik | **4 M** | 128 MB | 🟡 Masaüstünde tamam, uçuşta sınırda |
| 5 m, 40 km, statik | **64 M** | 2 GB | ❌ Düz grid çöker |
| 80 m, 40 km, **24 zaman adımı** | 6 M | 192 MB | 🟡 |
| 80 m, 40 km, **168 zaman adımı** (1 hafta, saatlik) | **42 M** | 1.3 GB | ❌ |
| 20 m + 48 zaman adımı | **192 M** | 6 GB | ❌❌ |

**Sonuç net:** LunaPath'in yol haritasındaki iki hedef — daha yüksek çözünürlük ([02](02_goruntu_isleme.md)) ve zaman ekseni ([07](07_termal_veri.md)) — **düz grid mimarisiyle birlikte imkânsızdır.** Hiyerarşi bir optimizasyon değil, **mimari zorunluluktur**.

### 3.2 Önerilen üç seviyeli mimari

```
┌─ SEVİYE A: MİSYON PLANLAMA (kaba uzay + zaman) ──────────────────┐
│  Grid  : 160–320 m (mevcut 80 m'nin 2–4× kabası)                 │
│  Zaman : saatlik, 1–7 gün ufuk                                   │
│  Boyut : ~15K hücre × 168 adım ≈ 2.5 M durum → yönetilebilir     │
│  Soru  : "Hangi gün, hangi saatte, hangi kaba koridordan?"        │
│  Çıktı : zaman damgalı kaba waypoint dizisi + bekleme kararları   │
│  Algo  : zaman-genişletilmiş graf üzerinde A* / Dijkstra          │
└──────────────────────────┬───────────────────────────────────────┘
                           │ kaba koridor + zaman penceresi
┌─ SEVİYE B: KORİDOR PLANLAMA (LunaPath'in bugünkü işi) ───────────┐
│  Grid  : 20–80 m, sadece koridor bandı (±500 m)                  │
│  Zaman : sabit (Seviye A'nın verdiği pencere içinde)             │
│  Boyut : ~25K–100K hücre → hızlı                                 │
│  Soru  : "Koridor içinde hangi hücrelerden?"                     │
│  Çıktı : Corridor sözleşmesi ([05](05_engel_kacinma.md) §4.1)     │
│  Algo  : çok kriterli A* (mevcut kod)                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │ waypoint + açıklık + bütçe
┌─ SEVİYE C: YEREL (kapsam dışı, arayüz tanımlı) ──────────────────┐
│  Grid  : 0.1–0.5 m, 5–20 m ufuk                                  │
│  Algo  : arc/DWA/MPC + hazard detection → [05]                   │
└─────────────────────────────────────────────────────────────────┘
```

**Neden bu bölünme doğru:** Her seviye kendi ölçeğinde **doğru soruyu** soruyor. Zamanı kaba uzayda çözmek (Seviye A) doğrudur çünkü aydınlanma saatler ölçeğinde değişir ve 80 m'lik detay bu kararı etkilemez. Uzayı ince çözmek (Seviye B) doğrudur çünkü kaya/eğim metrelerde değişir ve zaman bu kararı etkilemez.

Bu, koridor tabanlı hiyerarşik yaklaşımın literatürdeki karşılığıdır ve lunar micro-rover risk-farkında coverage planlama çalışmasının global (offline DEM maliyeti, `β` terimi) + local (gerçek zamanlı miyopik algılama) ayrımıyla aynı felsefeyi paylaşır: `mc = α(mc_static + mc_visited·V_i) + β·mc_DEM`, burada `α + β = 1` ile arazi-farkındalık ve kapsama verimliliği arasında ayar yapılıyor.

### 3.3 Zaman-genişletilmiş graf: somut formülasyon

Seviye A için durum: `(hücre, zaman_dilimi)`. Kenarlar:

```python
# Hareket kenari: (cell_i, t) -> (cell_j, t + travel_time)
# Bekleme kenari: (cell_i, t) -> (cell_i, t + 1)   <- KRITIK
```

**Bekleme kenarı olmadan bu problem çözülemez.** Ay kutbunda doğru cevap sıklıkla *"bekle, güneş gelsin, sonra geç"*dir. Literatürde bu açıkça modelleniyor: rover'ın aşırı ısı girdisinden kaçınmak için **beklemesine izin verilir**; kısıtlar statik (arazi eğimi) ve yola-bağlı (rover termal ve güç durumu) tiplere ayrılır, çevresel girdiler (Ay'daki ısı akısı ve aydınlanma) ise **zamana bağlıdır**.

Bekleme kenarının maliyeti:

```python
def wait_cost(cell, t, dt_h, illum_frac, rover):
    """Beklemek bedava degildir: idle guc + termal drift.
    Aydinlikta bekleme SOC'yi ARTIRIR (sarj) -> negatif enerji maliyeti.
    Golgede bekleme hem SOC hem sicaklik kaybettirir."""
    solar_in = rover["P_SOLAR_W"] * illum_frac[cell]
    net_w = solar_in - rover["P_IDLE_W"] - rover["P_HEATER_W"]
    d_soc = net_w * dt_h / rover["E_CAP_WH"]
    return (w_energy * max(0.0, -d_soc)
            + w_shadow * f_shadow_increment(1.0 - illum_frac[cell], dt_h)
            + w_thermal * thermal_drift_penalty(cell, dt_h))
```

> **Bu, LunaPath'e eklenebilecek en yüksek bilimsel değerli tek özelliktir.** "Beklemek bir karardır" fikri, projeyi statik rota çizen bir araçtan **zaman-uzay görev planlayıcısına** dönüştürür ve mevcut sabitlerin (`P_SOLAR_W`, `P_IDLE_W`, `P_HEATER_W`, `SOC_MIN_PCT`) hepsini anlamlı hale getirir. Bugün bu sabitler kodda duruyor ama planlama kararını etkilemiyor.

---

## 4. Nerede koşacak? Yer vs rover

### 4.1 İletişim gerçekliği

| Büyüklük | Değer |
|---|---|
| Dünya–Ay tek yön ışık süresi | ~1.28 s |
| Gidiş-dönüş | ~2.6 s |
| Pratik komut çevrimi (DSN planlama, yer işleme, operatör onayı) | **saatler** |
| Pragyan operasyonel gerçeklik | Her hareket için navcam verisi Dünya'ya indirilip DEM üretiliyor; **tek komutta en fazla ~5 m** |
| Kutupta Dünya görünürlüğü | Topografyaya bağlı, kesintili |

**Sonuç:** Işık süresi problem değil; **operasyonel çevrim** problem. 2.6 saniyelik gecikme bir joystick için bile tolere edilebilir, ama gerçek operasyonlarda çevrim saatler sürer.

### 4.2 İş bölümü kararı

| Seviye | Nerede | Gerekçe |
|---|---|---|
| **A — Misyon planlama** | 🌍 **YERDE** | Saatler-günler ufuk; yer bilgisayarı sınırsız; insan onayı gerekir |
| **B — Koridor planlama** | 🌍 **YERDE** (ana), 🛰️ rover'da (yedek/replan) | Yerde tam kalite; rover'da kısıtlı bütçeyle segment replan |
| **C — Yerel** | 🛰️ **ROVER'DA** (zorunlu) | Saniyeler; Dünya'ya sorulamaz |

**LunaPath'in doğru konumu Seviye A + B, yerde.** Bu, projeyi zayıflatmaz — Pragyan bugün tam olarak böyle çalışıyor ve VIPER gibi kutup misyonlarında görev öncesi termal/enerji kısıtlı planlama, yer tarafında yapılan **kritik** bir iştir.

### 4.3 Onboard bütçe: sayılarla

Rover'da koşturma iddiası kurarsanız, karşı karşıya olduğunuz gerçek:

| Platform | Performans | Not |
|---|---|---|
| **RAD750** (LRO, Curiosity, Perseverance, JWST) | **110–200 MHz**, ~**266 MIPS** | 20 yıldır BLEO misyonlarının fiili standardı |
| Modern dizüstü (çok çekirdek + SIMD) | ~10⁵ MIPS mertebesi | **~400–1000× fark** |
| **PIC64-HPSC** (NASA HPSC / Microchip + SiFive RISC-V) | **26.000 DMIPS**, **1 TFLOPS** bf16 / **2 TOPS** int8, 3U SpaceVPX | Geleneksel uzay işlemcilerine göre **~100×**; sanallaştırma, AI, TSN Ethernet, PCIe, CXL 2.0, post-kuantum kripto |

**PIC64-HPSC'nin ilan edilen kullanım senaryolarından biri doğrudan** "Ay yüzeyinde rover hazard avoidance gibi gerçek zamanlı görevleri yerel işlem gücüyle yürütmek" olarak tanımlanıyor. Yani LunaPath'in yerel katman hayali, **2020'lerin ikinci yarısında donanım olarak mümkün hale geliyor** — ama bugünün uçan donanımında değil.

**Somut bütçe egzersizi (belgede olması gereken):**

```
Varsayım: RAD750 sınıfı, planlayıcıya CPU'nun %20'si ayrılmış, 10 s bütçe
→ etkin ~530 M komut

Ön-hesaplanmış maliyetle A*, düğüm başına ~50 komut (dizi okuma + heap)
→ ~10 M düğüm genişletmesi bütçesi

500×500 grid, hedef-yönlü heuristic ile tipik ~%20 genişletme = 50 K düğüm
→ ✅ RAHAT SIĞAR (bütçenin %0.5'i)

2000×2000 (20 m) grid, %20 genişletme = 800 K düğüm
→ ✅ Sığar (bütçenin %8'i)

Zaman-genişletilmiş (168 adım), %5 genişletme = 2.1 M düğüm
→ 🟡 Sınırda; bellek (1.3 GB) asıl darboğaz
```

> **Bu tablo LunaPath'in en güçlü olgunluk kanıtlarından biri olabilir.** "Algoritmamız uçuş bilgisayarı sınıfı bir platformda hesaplama bütçesinin %X'ini kullanır" cümlesi, hiçbir hackathon projesinin söylemediği bir şeydir ve söylemek için **sadece bir hesap tablosu** gerekir.

### 4.4 Bellek darboğazı

Uçuş bilgisayarlarında RAM tipik olarak **128–512 MB** mertebesindedir (RAD750 sistemleri). LunaPath:

| Konfigürasyon | Bellek | Uçuşta? |
|---|---|---|
| 500×500, float32, 7 katman + 8 yön maliyet | ~15 MB | ✅ Rahat |
| 2000×2000, float32 | ~240 MB | 🟡 Sınırda |
| Zaman-genişletilmiş 168 adım | 1.3 GB | ❌ Hayır |

**Reçete:** `float64` → `float32` geçişi tek satırlık bir değişiklikle belleği yarıya indirir ve termal/eğim hassasiyeti için `float32` (7 anlamlı basamak) **fazlasıyla** yeterlidir. Mevcut pipeline `float64` kullanıyor (`process_lunar_data.py` "P1 grid standardı" olarak `float64` seçmiş) — bunu gözden geçirin. Elevasyon için `float32` ~0.001 m çözünürlük verir; LOLA'nın kendi belirsizliği 0.30–0.50 m'dir.

---

## 5. Anytime planlama: sert zaman limitiyle nasıl baş edilir

Onboard senaryoda bütçe aşılırsa ne olacak? İki kötü seçenek ve bir iyi seçenek:

| Yaklaşım | Sonuç |
|---|---|
| ❌ Bitene kadar koş | Zaman limiti ihlali → görev yazılımı watchdog |
| ❌ Kes ve rota yok | Rover bekler → enerji/termal kayıp |
| ✅ **Anytime (ARA\*)** | Gevşetilmiş heuristic (`ε > 1`) ile hızlı bir **suboptimal ama geçerli** rota bul, kalan zamanla `ε`'yi 1'e doğru azaltarak iyileştir |

ARA*'ın LunaPath için avantajı: `ε`-suboptimal garanti verir. Yani *"bütçe dolduğunda elimizdeki rota, optimalin en fazla %20 üzerindedir"* diyebilirsiniz. Bu, uzay yazılımında **kanıtlanabilir sınır** anlamına gelir ve deterministik kesme davranışından çok daha savunulabilirdir.

**Uygulama maliyeti düşük:** mevcut A*'a `epsilon` parametresi + dış döngü:

```python
def anytime_astar(grids, start, goal, weights, budget_ms, eps_schedule=(3.0, 2.0, 1.5, 1.2, 1.0)):
    best, t0 = None, time.perf_counter()
    for eps in eps_schedule:
        remaining = budget_ms - (time.perf_counter() - t0) * 1000
        if remaining <= 0: break
        r = astar(grids, start, goal, weights, h_weight=eps, deadline_ms=remaining)
        if r["path_pixels"]:
            best = r | {"suboptimality_bound": eps}
    return best
```

**`suboptimality_bound` alanını `PathResult.metrics`'e ekleyin.** Bu, tek bir alanla olgunluk sinyali verir.

---

## 6. Ölçüm planı (benchmark)

`pathfinder.py` zaten `computation_time_ms` ve `nodes_expanded` raporluyor — **altyapı hazır, kullanılmıyor.** Eksik olan sistematik ölçüm:

```python
# backend/test_planner_benchmark.py (yeni)
CASES = [
    # (grid_boyutu, start-goal mesafesi, profil, engel yogunlugu)
    (100, "kisa",  "balanced",       "dusuk"),
    (500, "orta",  "balanced",       "orta"),
    (500, "uzun",  "energy_saver",   "orta"),
    (500, "uzun",  "shadow_traverse","yuksek"),
    (2000,"uzun",  "balanced",       "orta"),
]

def test_benchmark_table(benchmark_writer):
    """Cikti: docs/research/planner_benchmark.md
    Kolonlar: case, nodes_expanded, expansion_ratio, time_ms,
              time_per_node_us, path_length, cost, peak_memory_mb"""
```

**Raporlanması gereken metrikler:**

| Metrik | Neden |
|---|---|
`nodes_expanded / total_nodes` | Heuristic'in ne kadar etkili olduğu (**admissibility kanıtı**) |
`time_per_node_us` | Platform bağımsız karşılaştırma birimi |
`peak_memory_mb` | Uçuş bütçesi analizi için |
`precompute_ms` vs `search_ms` | Ön-hesaplama kazancını göstermek |
`suboptimality_bound` | Anytime modda |
`replan_ms` | Segment replanning maliyeti (tam koşumla karşılaştırma) |

### 6.1 Heuristic admissibility — sessiz bir risk

Referans belge heuristic'i şöyle tanımlıyor: *"Euclidean mesafe × minimum edge cost (admissible)"*.

**Bu iddianın kanıtlanması gerekir.** `min_edge_cost` gerçekten tüm kenarların alt sınırı mı? Maliyet fonksiyonunda `max(0.01, C)` clamp'ı var (`C = max(0.01, C)`), yani teorik minimum 0.01'dir. Heuristic `0.01 × euclid_distance / cell_size` kullanıyorsa admissible'dır ama **çok gevşektir** (neredeyse Dijkstra'ya döner → yavaş). Daha sıkı bir alt sınır kullanılıyorsa admissibility bozulabilir → **optimal olmayan rota, "optimal" olarak sunulur.**

**Aksiyon:** Bir test yazın:

```python
def test_heuristic_is_admissible(grids, weights):
    """Rastgele 1000 (node, goal) cifti icin:
    h(node, goal) <= gercek_optimal_maliyet(node, goal)
    Gercek optimal: geriye dogru Dijkstra ile tam cozum."""
```

Bu, "optimal rota buluyoruz" iddiasının **tek geçerli kanıtıdır** ve şu an yok.

---

## 7. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| C1 | Hesaplama bütçesi hiç analiz edilmemiş | 🟠 Yüksek (olgunluk) | Düşük | **P0** |
| C2 | Maliyet ön-hesaplanmıyor (10–100× kayıp) | 🟠 Yüksek | Orta | **P0/P1** |
| C3 | Heuristic admissibility kanıtlanmamış | 🔴 Yüksek (optimallik iddiası) | Düşük | **P0** |
| C4 | Benchmark tablosu yok (altyapı hazırken) | 🟠 Orta-yüksek | Düşük | **P0** |
| C5 | Hiyerarşi yok → yüksek çözünürlük ve zaman imkânsız | 🔴 Yüksek (yol haritası blokajı) | Yüksek | **P1** |
| C6 | Zaman-genişletilmiş graf ve **bekleme kenarı** yok | 🔴 Yüksek (bilimsel değer) | Yüksek | **P1** |
| C7 | Anytime/suboptimality sınırı yok | 🟡 Orta | Düşük | P1 |
| C8 | `float64` bellek israfı | 🟡 Orta | Çok düşük | P1 |
| C9 | Onboard/yer iş bölümü belgelenmemiş | 🟠 Orta-yüksek | Çok düşük | **P0** |

---

## 8. Yol haritası

### P0 — "ölç ve belgele" (1–2 gün, kod değişikliği minimal)
1. **Benchmark tablosu üret** (§6) → `docs/research/planner_benchmark.md`
2. **Heuristic admissibility testi** yaz ve geçir (§6.1)
3. **Hesaplama bütçesi analizi** belgele (§4.3) — RAD750 ve HPSC karşılaştırmalı tablo
4. **Yer/rover iş bölümü** bölümünü mimari belgeye ekle (§4.2)

### P1 — "hızlandır ve hiyerarşiye geç" (5–8 gün)
5. **`precompute_edge_costs`** (§2) — öncesi/sonrası benchmark ile
6. `float64` → `float32`
7. Anytime A* + `suboptimality_bound` metriği (§5)
8. **Seviye A/B ayrımı**: kaba grid (160–320 m) + zaman-genişletilmiş graf + **bekleme kenarı** (§3.3)
9. Koridor daraltma (Seviye A çıktısı → Seviye B girdisi)
10. Segment replanning + `replan_ms` ölçümü

**Kabul kriteri (P1):**
- Benchmark tablosu ön-hesaplama öncesi/sonrası **ölçülmüş hızlanmayı** gösteriyor
- Zaman-genişletilmiş planlayıcı, bir senaryoda **"beklemeyi seçtiğini"** gösteriyor (aydınlık gelene kadar bekle → sonra geç). Bu, tek başına güçlü bir demo.
- 20 m grid'de plan süresi < 5 s
- Hesaplama bütçesi tablosu belgede

### P2
11. Numba/Cython ile çekirdek JIT (ön-hesaplama yetmezse)
12. D* Lite (ölçüm gerektiriyorsa — [05](05_engel_kacinma.md) §4.2)
13. cFS/F´ app paketleme iskeleti ([04](04_acik_kaynak_modeller.md) §6)

---

## 9. Sunumda kullanılacak cümleler

- *"Maliyet fonksiyonumuzun %86'sı yola bağımsızdır ve tamamen ön-hesaplanabilir. Bu sayede A*'ın iç döngüsü saf dizi okumasına indi ve 500×500 grid'de plan süresi X ms'ye düştü."*
- *"Planlayıcımız, RAD750 sınıfı bir uçuş bilgisayarında hesaplama bütçesinin tahmini %0.5'ini kullanır. Yeni nesil HPSC platformlarında (26.000 DMIPS, 1 TFLOPS) zaman-genişletilmiş planlama da onboard mümkün hale gelir."*
- *"Zamanı kaba uzayda, uzayı sabit zamanda çözüyoruz. Bu bir kısıtlama değil, doğru ayrıştırma: aydınlanma saatlerde değişir, kaya metrelerde."*
- *"Planlayıcımız beklemeyi bir karar olarak modelliyor. Bazen doğru cevap 'daha hızlı git' değil, 'dur, güneş gelsin, sonra geç'tir."*
- *"Anytime modunda bütçe dolduğunda elimizdeki rotanın optimale göre kanıtlanmış bir üst sınırı var — deterministik kesme yerine ε-suboptimal garanti."*

---

## Kaynaklar

- [Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover (arXiv 2401.08558, IEEE AERO 2024)](https://arxiv.org/abs/2401.08558)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers Leveraging Global and Local Environmental Data (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration (Remote Sensing 17(11), 1924)](https://www.mdpi.com/2072-4292/17/11/1924)
- [A Deep Learning Approach to Lunar Rover Global Path Planning Using Environmental Constraints and Rover Internal Resource Status (Sensors 24(3), 844)](https://www.mdpi.com/1424-8220/24/3/844)
- [Mars 2020 Autonomous Rover Navigation](https://www.semanticscholar.org/paper/MARS-2020-AUTONOMOUS-ROVER-NAVIGATION-McHenry-Abcouwer/c20138d836a7359ca83b8a35aafed060abe46b53)
- [RAD750 SpaceWire-Enabled Flight Computer for LRO (SpaceWire Conference 2007)](https://klabs.org/DEI/Processor/PowerPC/rad750/papers/spacewire_con_2007.pdf)
- [PIC64-HPSC Series — Microchip](https://www.microchip.com/en-us/products/microprocessors/64-bit-mpus/pic64-hpsc)
- [Microchip: Highest Performance 64-bit HPSC MPU Family for Autonomous Space Computing](https://www.microchip.com/en-us/about/news-releases/products/microchip-unveils-industrys-highest-performance-64-bit-hpsc-mpu)
- [The Dawn of the HPSC Era in Space Computing (white paper)](https://ww1.microchip.com/downloads/aemDocuments/documents/MPU64/ProductDocuments/SupportingCollateral/Dawn-of-HPSC-Era-in-Space-Computing-White-Paper.pdf)
- [HPSC for Lunar and Planetary Missions (NTRS 20250002070)](https://ntrs.nasa.gov/api/citations/20250002070/downloads/Powell-LPSC-2024-HPSC_for2025Mar12%2002252025_v2.pdf)
- [NASA HPSC program page](https://www.nasa.gov/game-changing-development-projects/high-performance-spaceflight-computing-hpsc)
- [Surface System Software and Rover Navigation — JPL Robotics](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/surface-system-software-and-rover-navigation/)
