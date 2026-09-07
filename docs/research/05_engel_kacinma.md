# 05 — Engel Kaçınma

> **Soru:** LunaPath'te engel kaçınma var mı? Gerçek rover'lar bunu nasıl yapıyor? LunaPath'e ne eklenmeli, neresi kapsam dışı bırakılmalı?
>
> **Kısa cevap:** LunaPath'te **engel kaçınma yok** — sadece bir *engel maskesi* var (`traversability_grid`). Bu ikisi aynı şey değildir. Engel maskesi "haritada bildiğim engelleri atla" der; engel kaçınma "yolda karşılaştığım bilinmeyen engelden kurtul" demektir. Gerçek rover'lar bunu **iki ayrı katmanda** yapar ve LunaPath şu an sadece üst katmanı temsil ediyor. Dürüst konumlandırma: LunaPath **global planlayıcıdır**; engel kaçınma onun **tüketicisidir**, parçası değil.

---

## 1. Terminolojiyi netleştir (bu, sunumda en çok karışan yer)

| Terim | Ne yapar | Zaman ölçeği | LunaPath'te |
|---|---|---|---|
| **Traversability analysis** | Haritadan "burası geçilebilir mi" | Offline | ✅ Var (`traversability.py`) |
| **Global path planning** | Başlangıç→hedef optimal rota | Offline / dakikalar | ✅ Var (`pathfinder.py` A*) |
| **Local path planning** | Sonraki 5–20 m için yörünge | Saniyeler | ❌ Yok |
| **Hazard detection** | Sensörle anlık tehlike tespiti | 0.1–2 s | ❌ Yok |
| **Obstacle avoidance** | Tespit edilen tehlikeden kaçınma manevrası | 0.1–2 s | ❌ Yok |
| **Replanning** | Yeni bilgiyle global rotayı güncelleme | Saniyeler–dakikalar | 🟡 Kısmi (`/api/replan` endpoint'i planlanmış) |
| **Recovery / safe haven** | Sıkışma/kritik durumda kurtarma | Dakikalar–saatler | 🟡 Belgede var, kodda yok |

**LunaPath'in şu an yaptığı iş satır 1–2'dir.** `main.py`'de `/api/replan` referans belgede tanımlı ama endpoint listesinde görünmüyor — bu, en yakın genişleme noktasıdır.

---

## 2. Gerçek rover'lar nasıl yapıyor?

### 2.1 MER/MSL kuşağı: GESTALT

Mars keşif rover'larının otonom navigasyon çekirdeği **GESTALT** (Grid-based Estimation of Surface Traversability Applied to Local Terrain) yaklaşımıdır. Temel fikir:

1. Stereo görüntüden **yerel yükseklik haritası** (local elevation map) üret
2. Her hücre için bir **"goodness"** skoru hesapla: eğim, pürüzlülük, basamak yüksekliği, veri yoğunluğu
3. Rover'ın **fiziksel ayak izini** (footprint) hücrenin üzerine yerleştir ve o footprint'in güvenliğini değerlendir
4. Aday **yay (arc)** hareketlerini goodness haritası üzerinde puanla
5. En iyi yayı seç, kısa mesafe (0.5–1 m) sür, tekrar et

**Kritik tasarım kararı:** GESTALT hücre-bazlı değil, **footprint-bazlı** değerlendirir. Rover 2 m genişse, 1 m'lik bir kaya bir hücreyi değil, footprint'i etkiler. LunaPath'te bu hiç modellenmiyor: hücre maliyeti tek bir noktanın maliyetidir, rover'ın gövdesi yoktur.

### 2.2 Mars 2020 (Perseverance): ENav + ACE

Perseverance'ın **ENav** (Enhanced Navigation) yazılımı GESTALT'ın evrimi:

- Aday yolları **sıralar**, sonra en yüksek sıralı yolları **ACE** (Approximate Clearance Evaluation) algoritmasıyla güvenlik açısından değerlendirir
- Üç bütünleşik yetenek: **HazDet** (navcam ile engel tespiti + otomatik alternatif rota), **VO** (görsel odometri ile hareket kestirimi), ve **"Thinking-While-Driving"** — sürerken aynı anda VO yapıp arazi haritası üretip yay harmanlama/seçme
- Ölçek kanıtı: **Sol 1312 (28 Ekim 2024) itibarıyla 32.1 km sürüşün ~%90'ı ENav ile arazi değerlendirilerek yapıldı**

**ACE'nin fikri LunaPath için doğrudan alınabilir:** ACE, kesin bir "geçilebilir/geçilemez" ikilisi yerine **açıklık (clearance) payı** hesaplar. Bu, [01](01_sektorel_veri_kaynaklari.md) §3.4'te önerilen belirsizlik bandı yaklaşımının aynısıdır ve LunaPath'e 20 satır kodla girer.

### 2.3 Ay tarafındaki durum: otonomi seviyeleri çok farklı

| Rover | Otonomi seviyesi | Kanıt |
|---|---|---|
| **Yutu-2** (Chang'e-4, 2019–) | 🟢 En yüksek Ay otonomisi: **görsel SLAM + rota planlama + rover kontrolü**; öncülü Yutu'ya göre lokalizasyon, haritalama, otonom navigasyon ve hareket planlamada belirgin ilerleme; 6+ yıl operasyon | Yayınlanmış görsel lokalizasyon çalışmaları |
| **Pragyan** (Chandrayaan-3, 2023) | 🟡 **Yer-döngüde (ground-in-the-loop)**: her hareket için navigasyon kamerası verisi Dünya'ya indirilip DEM üretiliyor, sonra komut gidiyor; tek komutta **en fazla ~5 m** | Basında ve teknik değerlendirmelerde belirtildi |
| **CADRE** (JPL, IM-3 ile, pencere 2026'ya uzanıyor) | 🟢 **Çok-robot dağıtık otonomi** teknoloji gösterimi; her rover el bagajı boyutunda, 2 stereo kamera + navigasyon sensörleri + multistatik GPR; doğrudan komut almadan işbirliği | JPL CADRE sayfası |
| **Tenacious** (ispace M2, 2025) | 🟡 Lander'a yakın, dairesel, **saniyede birkaç cm**; misyon iniş anomalisiyle kayboldu | ispace açıklamaları |
| **VIPER** (2027 hedefi, Blue Moon MK1) | 🟢 Kutup, PSR'a girme, matkap; termal/enerji kısıtlı planlama | NASA/Blue Origin |

**LunaPath için önemli çıkarım:** Ay'da Pragyan seviyesinde bir yer-döngü mimarisi **hâlâ operasyonel gerçeklik**. Bu, LunaPath'in "görev öncesi planlama aracı" konumlandırmasının **zayıflık değil, sektörle uyum** olduğu anlamına gelir. Pragyan tarzı bir operasyonda LunaPath'in ürettiği rota, insan operatörün karar destek girdisidir — bu tam olarak gerçek bir ihtiyaçtır.

---

## 3. Ay kutbuna özel engel kaçınma zorlukları

| Zorluk | Neden Ay kutbunda daha kötü | Etkisi |
|---|---|---|
| **Güneş ufukta (~1.5°)** | Uzun, keskin gölgeler arazi özelliklerini saklar | Stereo korelasyon başarısız; gölge = "bilgi yok" bölgesi |
| **Dinamik aralık** | Aydınlık kaya + kalıcı gölge aynı karede | HDR zorunlu; doygunluk/gürültü |
| **Doku yokluğu** | Feature-sparse regolit | VO ve stereo drift |
| **Doğrudan güneşe bakış** | Rover ufka doğru bakınca güneş kadraja girer | Flare, kör bölge |
| **Gölge içi görüş** | Sinyal ≈ gürültü | Aktif aydınlatma (LED/lazer) veya termal kamera gerekir |
| **Toz** | Elektrostatik yapışkan regolit, optik yüzey kirlenmesi | Zamanla performans düşüşü |
| **Slip** | Eğimli, gevşek regolit | Kat edilen mesafe ≠ komut edilen mesafe |
| **İletişim penceresi** | Kutupta Dünya görünürlüğü topografyaya bağlı | Yer-döngü mimarisi kesintiye girer |
| **Termal** | Gölgede kalma süresi donanımı sınırlar | Kaçınma manevrası **termal bütçeyi** harcar |

**Son madde LunaPath için özgün bir katkı fırsatı:** Klasik engel kaçınma literatüründe kaçınma manevrasının maliyeti "ekstra mesafe"dir. Ay kutbunda kaçınma manevrasının maliyeti **ekstra gölge süresi ve termal stres**tir. Yani:

> *"Engelden kaçınmak için 40 m sağa saptım" → "bu sapma beni 8 dakika daha gölgede tuttu, iç sıcaklığım 3 K düştü, termal bütçemin %6'sını harcadım."*

Bu, LunaPath'in maliyet modelinin **yerel katmana taşınmış hali**dir ve literatürde az işlenmiş bir açıdır. Ayırt edici özellik olarak öne çıkarılabilir.

### 3.1 Slip / terramekanik

Regolit üzerinde eğim arttıkça **slip oranı üstel olarak artar** (lunar micro-rover coverage çalışması bunu pitch açısıyla traversability metriği olarak kullanıyor). Bu, LunaPath'in enerji modelinde eksik:

```python
# cost_engine.py: f_energy su an sadece egim ve mesafeye bakiyor
# Eksik: slip nedeniyle harcanan bosa enerji
def slip_ratio(theta_deg: float, soil="regolith") -> float:
    """Kabaca: i = i0 * exp(k * theta). Literaturde kalibrasyon gerekir.
    i=0.2 -> komut edilen 1 m icin gercekte 0.8 m ilerlenir."""
    return min(0.9, 0.02 * math.exp(0.11 * theta_deg))

def effective_distance(d_m, theta_deg):
    return d_m / (1.0 - slip_ratio(theta_deg))
```

`slip_ratio(20°) ≈ 0.18` → 20° eğimde enerji ve süre **%22 daha yüksek**. Bu, `f_energy`'nin sistematik olarak iyimser olduğu anlamına gelir. Düzeltme tek satırlıktır ve fiziksel gerekçesi güçlüdür.

---

## 4. LunaPath için önerilen iki katmanlı mimari

```
┌────────────────────────────────────────────────────────────────┐
│  KATMAN 1 — GLOBAL (LunaPath'in bugünkü işi)                   │
│  Girdi : yörünge verisi (DEM, Diviner, illumination, PSR, NAC)  │
│  Çıktı : koridor + waypoint dizisi + termal/enerji bütçesi      │
│  Ölçek : 20–80 m hücre, 10–40 km, saatler-günler                │
│  Yer   : YERDE (görev öncesi) veya rover'da (nadiren)           │
│  Algo  : çok kriterli A* / D* Lite                              │
└──────────────────────────┬─────────────────────────────────────┘
                           │ koridor + bütçe + fallback noktaları
┌──────────────────────────▼─────────────────────────────────────┐
│  KATMAN 2 — LOKAL (kapsam dışı, arayüz tanımlı)                 │
│  Girdi : stereo/LiDAR + koridor kısıtı + kalan bütçe            │
│  Çıktı : yay/yörünge komutu (0.5–20 m)                          │
│  Ölçek : 0.1–0.5 m hücre, 5–20 m, saniyeler                     │
│  Yer   : ROVER'DA                                               │
│  Algo  : GESTALT/ENav benzeri arc değerlendirme, DWA veya MPC    │
└────────────────────────────────────────────────────────────────┘
```

### 4.1 Katman 1'in Katman 2'ye vermesi gereken şey — "koridor sözleşmesi"

LunaPath'in çıktısı bugün bir **piksel dizisi**. Bu, yerel planlayıcı için yeterli değil. Yerel planlayıcının ihtiyacı:

```python
# backend/app/schemas.py'ye eklenecek
class Corridor(BaseModel):
    """Global planlayicinin yerel planlayiciya verdigi sozlesme."""
    waypoints: list[tuple[float, float]]     # metre, proje CRS'inde
    half_width_m: list[float]                # her segment icin izinli yanal sapma
    max_slope_deg: list[float]               # segment bazli egim limiti
    thermal_budget_K_s: list[float]          # segment icin ayrilan termal stres butcesi
    energy_budget_wh: list[float]            # segment icin ayrilan enerji
    time_window_utc: list[tuple[str, str]]   # segmentin gecerli oldugu zaman penceresi
    fallback_points: list[tuple[float, float]]  # en yakin safe haven / bekleme noktasi
    replan_triggers: dict                    # hangi kosulda global'e geri don
```

**Bu şema, LunaPath'i "rota çizen bir demo"dan "bir otonomi yığınının üst katmanı"na dönüştürür** — kod yazmadan, sadece çıktı formatını doğru tanımlayarak. Olgunluk açısından bu, en yüksek getirili düşük-maliyetli hamledir.

`half_width_m` nasıl hesaplanır: `scikit-image`'ın `distance_transform_edt` fonksiyonu ile, `traversable=False` hücrelere olan mesafe → rota üzerindeki her noktada mevcut açıklık.

```python
from scipy.ndimage import distance_transform_edt

clearance_m = distance_transform_edt(traversable) * resolution_m
half_width = [min(clearance_m[r, c], MAX_CORRIDOR_HALF_WIDTH_M) for r, c in path]
```

### 4.2 Replanning: D* Lite mi, A*'ı yeniden koşmak mı?

Referans belge D* Lite'ı seçenek olarak listeliyor. Dürüst değerlendirme:

| Yöntem | Ne zaman kazanır | LunaPath için |
|---|---|---|
| **A*'ı sıfırdan koş** | Grid küçük, değişim büyük, hesap bütçesi var | ✅ 500×500'de bugün en pratik. Ölçün: mevcut A* zaten `computation_time_ms` raporluyor |
| **D* Lite** | Grid büyük, **lokal ve seyrek** değişim, tekrarlı planlama | 🟡 Rover üzeri gerçek zamanlı senaryoda değerli; yerde offline planlamada kazancı sınırlı |
| **Segment replanning** | Rotanın sadece bir kısmı bozulmuş | ✅ Ucuz ve yeterli — referans belgede zaten "basit segment replanning" olarak planlanmış |
| **Anytime (ARA*)** | Sert zaman limiti var, "yeterince iyi" cevap lazım | ⭐ Onboard senaryoda **doğru** cevap → [08](08_global_local_rotalama_yuku.md) |

**Öneri:** D* Lite'ı "yapacağız" diye söz vermeyin. Bunun yerine:
1. Mevcut A* koşum süresini **ölçün** (zaten metriklerde var)
2. Segment replanning'i uygulayın (basit, ölçülebilir)
3. Belgeye şu cümleyi yazın: *"Grid boyutu 2000×2000'e çıkarsa veya onboard tekrarlı planlama gerekirse D* Lite'a geçiş için mimari hazırdır; mevcut ölçekte A*'ın tam koşumu X ms sürüyor ve D* Lite'ın karmaşıklık ek yükünü haklı çıkarmıyor."*

Bu, "D* Lite yaptık" demekten daha güçlü bir mühendislik ifadesidir çünkü **ölçüme dayanır.**

### 4.3 Replanning tetikleyicileri (somut liste)

Referans belge "event-triggered replanning" diyor ama tetikleyicileri saymıyor. Somut liste:

| Tetikleyici | Eşik önerisi | Aksiyon |
|---|---|---|
| Bilinmeyen engel tespit edildi | Yerel planlayıcı koridoru terk etmek zorunda | Global replan (segment) |
| SOC bütçeden sapma | Gerçek SOC < planlanan SOC − %10 | Global replan + profil `energy_saver`'a geç |
| İç sıcaklık sapması | T_iç, tahminden 5 K aşağıda | Global replan + `shadow_traverse` profiline geç |
| Slip birikimi | Kat edilen/komut edilen < 0.75 | Yerel yeniden kalibrasyon + eğim limitini düşür |
| Zaman kayması | Plan zamanından >30 dk sapma | **Aydınlanma değişti** → global replan zorunlu |
| SEP olayı uyarısı | Radyasyon eşiği → [06](06_radyasyon_verisi.md) | Safe haven'a git, bekle |
| İletişim penceresi kapanıyor | Dünya görünürlüğü < X dk | Konservatif moda geç |
| Konum belirsizliği | Kestirim kovaryansı > koridor yarı genişliği | Dur, lokalizasyon düzelt |

**Bu tablonun kendisi bir çıktıdır.** `backend/app/replan_triggers.py` olarak kodlanabilir ve her tetikleyici için bir birim testi yazılabilir. Jüri/hakem karşısında "replanning yapıyoruz" demenin somut kanıtı budur.

### 4.4 Safe haven mantığı — belgede var, kodda yok

`ay_termal_navigasyon_proje_dokumani.md` §6.7 bunu açık soru olarak bırakmış. Karar önerisi: **safe haven'ı zorunlu kısıt yapın, opsiyon değil.**

Gerekçe: LPR-1 sabitlerinde `H_MAX_SHADOW_H = 50` ve `H_DESIGN_SHADOW_H = 70` var. Bu, "50 saatten fazla gölgede kalırsan öl" demek. Bir rota bu limiti aşmıyorsa bile, **rota üzerindeki her noktadan 50 saat içinde bir güvenli noktaya erişilebilir olmalıdır** — aksi halde rota tek bir arıza ile ölümcül hale gelir.

Bu, klasik planlamada **"return-to-safety reachability"** kısıtıdır ve şöyle formüle edilir:

```python
def is_recoverable(node, illumination_grid, cost_grid, t_now, rover) -> bool:
    """Bu node'dan, kalan enerji ve H_MAX_SHADOW ile
    aydinlik/sarj bolgesine erisilebilir mi?
    Geriye dogru Dijkstra ile 'safe set'e mesafe hesapla."""
```

**Uygulama tavsiyesi:** Safe set'e mesafeyi **bir kez** çok kaynaklı Dijkstra ile hesaplayıp grid olarak saklayın (`recovery_cost_grid`). Sonra A* içinde `if recovery_cost[node] > remaining_budget: skip` tek satırlık bir kontrol olur. Hesaplama maliyeti: bir Dijkstra koşumu = A* ile aynı mertebede.

Bu, literatürdeki chance-constrained/reachability tabanlı yaklaşımlarla aynı ailedendir: Lamarre, Malhotra ve Kelly'nin güneş enerjili rover için PSR keşfi çalışması ([arXiv 2401.08558](https://arxiv.org/abs/2401.08558), IEEE AERO 2024), bilinen ortalama oranlarda rastgele arızaları hesaba katan bir **şans kısıtlı (chance-constrained) görev-seviyesi planlama** problemi kuruyor ve **stokastik erişilebilirlik (stochastic reachability) analizi** ile güvenli geçiş politikaları buluyor; Cabeus krateri / LCROSS çarpma bölgesinde çok günlük uzun menzilli sürüşlerle doğruluyor.

> **Bu, LunaPath'in en yakın akademik komşusudur.** Aynı problemi, aynı bölgede, daha ileri bir formülasyonla çözüyor. Bunu bilmek ve atıf vermek, LunaPath'i literatüre bağlar; görmezden gelmek jüri karşısında risk oluşturur.

---

## 5. Boşluk analizi

| # | Boşluk | Etki | Efor | Öncelik |
|---|---|---|---|---|
| O1 | "Engel kaçınma var" izlenimi verilirken yok | 🔴 Yüksek (savunulabilirlik) | Çok düşük | **P0** |
| O2 | Rover footprint modellenmiyor (nokta olarak ele alınıyor) | 🟠 Yüksek | Düşük | **P0** |
| O3 | Koridor/açıklık çıktısı yok | 🟠 Yüksek | Düşük | **P1** |
| O4 | Slip modellenmiyor → enerji iyimser | 🟠 Orta-yüksek | Çok düşük | **P1** |
| O5 | Replanning tetikleyicileri tanımlı değil | 🟠 Orta-yüksek | Düşük | **P1** |
| O6 | Safe haven erişilebilirlik kısıtı yok | 🟠 Yüksek | Orta | **P1** |
| O7 | Yerel planlayıcı arayüzü tanımsız | 🟡 Orta | Düşük | P1 |
| O8 | Yerel planlayıcı yok | 🟡 Kapsam kararı | Yüksek | P2/kapsam dışı |

---

## 6. Yol haritası

### P0 — dürüstlük + footprint (1 gün)
1. README/sunum dilinden "engel kaçınma" ifadesini çıkar veya "harita tabanlı engel maskesi (yerel kaçınma kapsam dışı)" olarak düzelt
2. **Footprint kontrolü ekle:** hücre değerlendirmesini `k×k` pencereye çevir (rover genişliği / hücre boyutu). 80 m hücrede rover 1 hücreden küçük → footprint = 1 hücre, ama **bunu kodda açıkça belirt** ki 5 m'ye geçince otomatik doğru davransın:

```python
# traversability.py
def footprint_traversable(traversable, rover_width_m, res_m):
    """Rover ayak izi kadar bir pencerede TUM hucreler gecilebilir olmali.
    scipy.ndimage.minimum_filter ile erosion."""
    k = max(1, int(np.ceil(rover_width_m / res_m)))
    if k == 1:
        return traversable  # cozunurluk rover'dan kaba: footprint modellenemez
    return minimum_filter(traversable.astype(np.uint8), size=k).astype(bool)
```

### P1 — koridor + kısıtlar (3–5 gün)
3. `Corridor` şeması + `distance_transform_edt` ile `half_width_m`
4. `slip_ratio` → `f_energy` düzeltmesi + doğrulama tablosu
5. `replan_triggers.py` + her tetikleyici için birim testi
6. `recovery_cost_grid` (safe haven erişilebilirlik) + A*'da tek satır kısıt
7. `/api/replan` endpoint'ini gerçekten uygula (segment replanning)
8. Metriklere ekle: `min_corridor_clearance_m`, `max_recovery_cost_h`, `slip_adjusted_energy_wh`

**Kabul kriteri (P1):** Aynı senaryoda "safe haven kısıtı kapalı" ve "açık" iki rota üretilip karşılaştırılıyor. Kısıt açıkken rota daha uzun ama her noktadan kurtarılabilir olduğu **sayısal olarak gösteriliyor** (`max_recovery_cost_h < H_MAX_SHADOW_H`).

### P2 — yerel katman (kapsam kararı; önerilen: kapsam dışı, arayüz tanımlı)
9. OmniLRS/LunarSim ile sentetik stereo → yerel hazard haritası
10. GESTALT benzeri arc değerlendirme veya MPC
11. Koridor sözleşmesi üzerinden Katman 1 ↔ Katman 2 kapalı döngü testi

---

## 7. Kabul kriterleri

- [ ] Belge ve sunumda global/lokal ayrımı net; "engel kaçınma" iddiası yok veya kapsamı belirtilmiş
- [ ] Footprint erozyonu kodda mevcut ve çözünürlük sınırı belgelenmiş
- [ ] `Corridor` şeması yayınlanmış, `half_width_m` üretiliyor
- [ ] Slip düzeltmesi `f_energy`'de, doğrulama tablosu güncellenmiş
- [ ] 8 replanning tetikleyicisi kodlu ve test edilmiş
- [ ] `recovery_cost_grid` üretiliyor, safe haven kısıtı açık/kapalı karşılaştırması var
- [ ] Lamarre vd. (2024) ve ENav/ACE literatürüne atıf yapılmış

---

## Kaynaklar

- [Mars 2020 Autonomous Rover Navigation (Semantic Scholar)](https://www.semanticscholar.org/paper/MARS-2020-AUTONOMOUS-ROVER-NAVIGATION-McHenry-Abcouwer/c20138d836a7359ca83b8a35aafed060abe46b53)
- [Autonomous robotics is driving Perseverance rover's progress on Mars (Science Robotics)](https://www.science.org/doi/10.1126/scirobotics.adi3099)
- [Driving Farther and Faster With Autonomous Navigation (NASA Science)](https://science.nasa.gov/missions/mars-2020-perseverance/driving-farther-and-faster-with-autonomous-navigation-and-helicopter-scouting)
- [Surface System Software and Rover Navigation — JPL Robotics](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/surface-system-software-and-rover-navigation/)
- [Lamarre, Malhotra, Kelly (2024), Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover, IEEE AERO (arXiv 2401.08558)](https://arxiv.org/abs/2401.08558)
- [Risk-Aware Coverage Path Planning for Lunar Micro-Rovers (arXiv 2404.18721)](https://arxiv.org/html/2404.18721v1)
- [A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration (Remote Sensing 17(11), 1924)](https://www.mdpi.com/2072-4292/17/11/1924)
- [Deep Probabilistic Traversability with Test-time Adaptation (arXiv 2409.00641)](https://arxiv.org/pdf/2409.00641)
- [Vision Based Obstacle Detection Using Rover Stereo Images (ISPRS)](https://isprs-archives.copernicus.org/articles/XLII-2-W13/1471/2019/isprs-archives-XLII-2-W13-1471-2019.pdf)
- [CADRE — JPL](https://www.jpl.nasa.gov/missions/cadre/)
- [A precise visual localisation method for the Chinese Chang'e-4 Yutu-2 rover (Photogrammetric Record)](https://www.researchgate.net/profile/Youqing-Ma/publication/339552801_A_precise_visual_localisation_method_for_the_Chinese_Chang'e-4_Yutu-2_rover)
- [Breadboarding the European Moon Rover System: analogue field test campaign (arXiv 2411.13978)](https://arxiv.org/pdf/2411.13978)
