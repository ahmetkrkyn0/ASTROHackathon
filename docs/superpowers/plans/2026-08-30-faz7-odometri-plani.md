# Faz 7 — Odometri ve Konum Belirleme Entegrasyon Planı

> **Durum:** PLAN — kod yazılmadı. Bu belge yalnızca *ne yapılacağını* tarif eder.
> **Tarih:** 2026-08-30 · **Branch:** `backend/physics`
> **Kaynak:** `docs/research/` (research.zip içeriği) + bu plan için yapılan sektörel web araştırması

---

## 0. Yönetici özeti — tek paragraf

LunaPath bugün **global planlayıcı**dır: yörünge DEM'inden rota üretir ve `Corridor`
sözleşmesiyle yayınlar. Ama bu koridorun *içinde rover'ın nerede olduğunu* kimse
söylemiyor. `replan_triggers.py` içindeki iki tetikleyici — `corridor_violation`
ve `localization_uncertainty` — girdi olarak **poz ve kovaryans** bekliyor,
fakat bu değerleri üreten hiçbir şey yok; testlerde elle besleniyorlar. Faz 7,
bu boşluğu kapatır: LunaPath'e bir **poz alıcı arayüzü** (odometri tüketicisi) ve
sahip olduğu yörünge DEM'ini kullanan bir **mutlak konum sıfırlama** yeteneği ekler.
Kritik nokta: **LunaPath odometri algoritması yazmaz** — bu kapsam dışıdır ve
dürüstlük ilkesine aykırı olur. LunaPath, dışarıdan gelen odometriyi *tüketen* ve
kendi DEM'iyle *doğrulayan* taraftır.

---

## 1. Önce düzeltme — kullanıcının ETH Zürich varsayımı

Kullanıcı "odometride ETH Zürich'in kullandığı yöntemler var, yıldız konumu gibi"
dedi. Araştırma bunu **kısmen doğrulamıyor**. Üç ayrı şeyin karıştığı anlaşılıyor:

| İddia | Gerçek durum | Kaynak |
|---|---|---|
| ETH Zürich odometride yıldız konumu kullanıyor | ❌ **Doğrulanmadı.** ETH RSL'in Ay ile ilgili işi `leggedrobotics/lunar_planner` — bu bir **global rota planlayıcı**, odometri sistemi değil. ETH'nin odometri işi (CompSLAM, open3d_slam, ANYmal state estimation) **LiDAR/görsel/atalet** tabanlıdır, göksel değil | [lunar_planner](https://github.com/leggedrobotics/lunar_planner) · [CompSLAM arXiv 2505.06483](https://arxiv.org/pdf/2505.06483) |
| Güneş/yıldız konumundan yönelim | ✅ **Doğru, ama ETH değil — CMU/Astrobotic MoonRanger.** "Stereo görsel odometri + **güneş sensörü** ile bağımsız yönelim." Bu zaten `10_sektorel_projeler_envanteri.md` §C2'de kayıtlı | [CMU RI](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) |
| Yüzeyde **star tracker** | ⚠️ Yüzey rover'larında yaygın değil; standart çözüm **güneş sensörü / güneş pusulası**. Göksel + ufuk eşleme birlikte araştırılıyor (AAS 25-358) ama uçmuş donanım değil | [AAS 25-358](https://www.researchgate.net/publication/390847776_AAS_25-358_CELESTIAL_AND_HORIZON_MATCHING_NAVIGATION_TECHNIQUES_FOR_LUNAR_SURFACE_OPERATIONS) |

**Ama kullanıcının sezgisi doğru yeri işaret ediyor.** Ay'da **manyetik alan yok →
pusula yok**. Mutlak yönelim gerçekten göksel bir referanstan gelmek zorunda ve bu,
Faz 7'nin en özgün parçasıdır — çünkü LunaPath'te **SPICE efemerisi (`ephemeris.py`)
zaten var**: güneşin azimut/yükseklik açısını zamanın fonksiyonu olarak biliyoruz.
Yani LunaPath, bir güneş sensörü ölçümünü *doğrulayabilecek* referansa zaten sahip.

**Güneş sensörü doğruluğu (literatür):** tipik ±3°, gelişmiş algoritmalarla
0.09° (1σ). JPL Mars Yard testlerinde artımlı odometriye göre yönelim
kestiriminde **3–4 kat iyileşme**. ([Furgale, Sun Sensor Navigation, TAES](https://furgalep.github.io/sbib/furgale_taes10.pdf))

---

## 2. Sektörel inceleme — kim odometriyi nasıl yapıyor

### 2.1 Uçmuş / sahada kanıtlanmış

| Misyon / sistem | Yöntem | Sayısal sonuç | Ders |
|---|---|---|---|
| **MER (Spirit/Opportunity)** | Tekerlek odometri + IMU, üstüne **Visual Odometry** | Ölü hesap hatası kat edilen mesafenin **~%10'u**; VO bunu telafi ediyor, öngörülmeyen slip'i otonom tespit ediyor | Ölü hesap tek başına yetmez — **%10 hata koridor yarı genişliğini hızla aşar** |
| **MSL / M2020 (Perseverance)** | VO + ENav/AutoNav; slip motor akımı + görsel | Perseverance VO'da ATE/yol uzunluğu **%0.22–2.45**; tek sol'da en uzun otonom sürüş 347.7 m | Görsel odometri iki mertebe daha iyi ama **hâlâ birikimli** |
| **MoonRanger (CMU/Astrobotic)** | Stereo VO + **güneş pusulası**; iletişim-kesintili keşif | 2029 misyonu | Ay'da mutlak yönelim = **güneş**. LunaPath'in SPICE hattı bunun yer tarafındaki ikizidir |
| **Yutu-2 (Chang'e-4)** | Görsel SLAM + stereo | Ay'ın uzak yüzünde 5+ yıl | Uçmuş en olgun Ay otonomisi; `constants.py`'de profili zaten var |
| **CLOVER mikro-rover (Tohoku)** | VLP-16 LiDAR + HDL graph SLAM | Analog saha lokalizasyon **MAE 0.41 m (killi) / 0.32 m (kumlu)** | Gerçekçi hedef büyüklük mertebesi |

### 2.2 Akademik / açık kaynak (2025–2026 sınırı)

| Sistem | Yöntem | Sonuç | Lisans / ROS 2 |
|---|---|---|---|
| **Stanford NavLab — Lunar Autonomy Challenge birincisi** | Stereo VO: **SuperPoint** + **LightGlue** → PnP RANSAC → **GTSAM** poz grafı + loop closure | Lokalizasyon **0.04–0.06 m RMSE**; 180×180 grid @ 15 cm; sabit-eğrilikli **arc** yerel planlayıcı | Açık: [Stanford-NavLab/lunar_autonomy_challenge](https://github.com/Stanford-NavLab/lunar_autonomy_challenge) |
| **Visual SLAM + DEM Anchoring** (aynı grup, IEEE Aerospace 2026) | DEM'den türetilen **yükseklik ve yüzey-normali faktörleri** poz grafına giriyor → mutlak yüzey kısıtı | Baseline SLAM'e göre ATE tutarlı biçimde düşüyor; UE simülasyon + **Etna analog** | [arXiv 2603.17229](https://arxiv.org/abs/2603.17229) |
| **ShadowNav** (JPL + Sydney) | **Krater landmark** eşleme; harici aydınlatıcı + stereo; parçacık filtresi | Hedef: mutlak hata **<10 m** (gezegen rover'ları için tipik gereksinim); karanlık/PSR'de çalışır | [arXiv 2301.04630](https://arxiv.org/abs/2301.04630) |
| **Skyline / Horizon Matching** (ALPER, IEEE) | Panoramadan **ufuk çizgisi** çıkar → DEM'den üretilen referans ufuklarla eşle | İniş sonrası konum başlatma + GNC doğrulama | [ALPER](https://www.sciencedirect.com/science/article/pii/S0094576525006186) |
| **LunarLoc** | Kaya (boulder) segmentasyonu → graf eşleme | Santimetre-altı, çoklu oturum | [arXiv 2506.16940](https://arxiv.org/pdf/2506.16940) |
| **KISS-ICP** | LiDAR-only odometri, parametresiz | — | **MIT** ✅ · ROS 2 ✅ · `pip install kiss-icp` |
| **LIO-SAM** | LiDAR-inertial, faktör grafı | — | BSD-3 ✅ |
| **FAST-LIO2** | Sıkı-bağlı IEKF | Daha doğru | ⚠️ **GPL-2.0 — MIT projemiz için lisans riski** |

### 2.3 Bu incelemeden çıkan üç karar

1. **Odometri algoritması yazmayacağız.** Stanford 0.04 m RMSE'yi 8 kameralı bir
   yığınla aldı; bunu bir hackathon fazında yeniden üretmek gerçekçi değil ve
   `03_sentetik_minimum_veri.md`'nin dürüstlük ilkesine aykırı.
2. **LunaPath'in özgün katkısı DEM tarafında.** Yukarıdaki tablonun *en üstteki iki
   akademik satırı* (DEM anchoring, skyline matching) **yörünge DEM'i gerektiriyor** —
   ve LunaPath'in elinde olan tek şey budur. Rakiplerin çoğu DEM'i dışarıdan almak
   zorunda; biz zaten üstünde oturuyoruz.
3. **`horizon.py` bedava bir skyline motorudur.** `horizon_map()` bugün
   `(n_azimuth, H, W)` bir dizi döndürüyor: *her hücre için, her azimutta ufuk
   yükseklik açısı*. Skyline matching'in referans veritabanı **tam olarak budur.**
   Faz 1'de gölge hesabı için yazıldı; Faz 5'te sanal LiDAR için tekrar kullanılıyor;
   Faz 7'de **üçüncü ürününü** verir. Tek çekirdek, üç ürün.

---

## 3. Kapsam — ne yapacağız, ne yapmayacağız

### ✅ Kapsam içi

| # | İş | Neden |
|---|---|---|
| T1 | `PoseEstimate` şeması — odometri girişinin sözleşmesi | `replan_triggers.py` bunu zaten bekliyor, tanımı yok |
| T2 | `localization.py` — koridor içi konum takibi (çapraz mesafe, ilerleme, kovaryans) | İki tetikleyicinin gerçek girdisi |
| T3 | `slip_model.py` — eğime bağlı slip → enerji/süre düzeltmesi | Araştırmanın **P1** bulgusu; `f_energy` sistematik iyimser |
| T4 | `skyline.py` — `horizon_map()`'ten mutlak konum sıfırlama (DEM anchoring'in bizim versiyonu) | ⭐ Özgün katkı; sıfır yeni veri |
| T5 | `/api/pose` endpoint + ROS 2 `nav_msgs/Odometry` aboneliği | Kabuk entegrasyonu; `pose_to_pixel` yarısı hazır |
| T6 | `localization_budget.py` — belirsizlik büyüme modeli + sıfırlama gerekliliği raporu | "Ne zaman durup lokalize olmalı" sorusunun cevabı |

### ❌ Kapsam dışı (ve bunu açıkça söyleyeceğiz)

- Gerçek VO/SLAM implementasyonu (SuperPoint, GTSAM, KISS-ICP kurulumu)
- Gerçek kamera/LiDAR/IMU donanımı veya sürücüsü
- Krater tespiti (ShadowNav tarzı) — algı problemi, kapsam dışı
- Gerçek güneş sensörü donanımı — **ama SPICE ile beklenen güneş açısını üretmek kapsam içi**

> **Sunumda geçecek cümle:** *"LunaPath odometri üretmez; odometri tüketir ve
> yörünge DEM'iyle doğrular. Ürettiğimiz şey, bir odometri yığınının LunaPath'e
> nasıl bağlanacağının sözleşmesi ve DEM'imizin bu yığının drift'ini nasıl
> sıfırlayabileceğinin kanıtıdır."*

---

## 4. Görev planı

### Task 1 — `backend/app/pose.py`: `PoseEstimate` sözleşmesi

**Amaç:** Odometrinin LunaPath'e giriş formatını tanımlamak. `Corridor` çıkışın
sözleşmesiyse, `PoseEstimate` girişin sözleşmesidir — **simetrik çift**.

```python
class PoseEstimate(BaseModel):
    """Yerel katmandan (VO/SLAM/odometri) gelen poz kestirimi."""
    x_m: float                      # proje CRS metre
    y_m: float
    heading_deg: float              # grid-kuzeyinden saat yonu (aspect_grid ile ayni)
    covariance_m: float             # 1-sigma yatay konum belirsizligi
    heading_covariance_deg: float
    timestamp_utc: str
    source: Literal["dead_reckoning", "visual_odometry",
                    "lidar_odometry", "skyline_fix", "sun_sensor"]
    distance_travelled_m: float     # komut edilen degil, kat edildigi *iddia edilen*
```

**Kritik tasarım kararı:** `source` alanı zorunlu. Ölü hesaptan gelen bir poz ile
skyline eşlemeden gelen bir poz **aynı güvenilirlikte değildir** ve tetikleyiciler
buna göre davranmalı. Bu, `layer_validity` deseninin (Faz 1) poz tarafındaki ikizi.

**Testler:** `heading_deg` konvansiyonunun `make_aspect_grid` ile aynı olduğu;
negatif kovaryansın reddedildiği; bilinmeyen `source` değerinin reddedildiği.

---

### Task 2 — `backend/app/localization.py`: koridor içi takip

**Amaç:** Poz + `Corridor` → "koridorun neresindeyim, ne kadar saptım".

```python
def project_onto_corridor(pose, corridor) -> CorridorFix
# CorridorFix: segment_index, lateral_offset_m, along_track_m,
#              progress_fraction, half_width_at_pose_m, inside: bool
```

Bu fonksiyon **`check_corridor_violation` ve `check_localization_uncertainty`'nin
eksik girdi üreticisidir.** Bugün testler `lateral_offset_m`'yi elle veriyor;
Task 2'den sonra gerçek bir pozdan hesaplanacak.

Ayrıca `evaluate_triggers`'a besleme yardımcısı:

```python
def trigger_state_from_pose(pose, corridor, plan_state) -> dict
```

**Testler:** koridor merkezindeki poz → `lateral_offset_m ≈ 0`; koridoru terk eden
poz → `corridor_violation` fires; `covariance_m > half_width_m` →
`localization_uncertainty` fires. Segment sınırında projeksiyonun atlamadığı.

---

### Task 3 — `backend/app/slip_model.py`: slip ve enerji dürüstlüğü

**Amaç:** Araştırmanın **P1** bulgusu (`05_engel_kacinma.md` §3.1): `f_energy`
slip'i yok sayıyor, dolayısıyla **sistematik olarak iyimser**.

```python
def slip_ratio(slope_deg: float) -> float:
    """i = i0 * exp(k * theta), regolit icin kaba kalibrasyon.
    slip_ratio(20 derece) ~ 0.18 -> enerji ve sure %22 daha yuksek."""

def effective_distance_m(distance_m: float, slope_deg: float) -> float:
    return distance_m / (1.0 - slip_ratio(slope_deg))
```

**Odometriyle bağlantısı — bu Task'ın asıl gerekçesi budur:** slip, *komut edilen
mesafe ile kat edilen mesafe arasındaki farktır*. Yani slip **ölçülebilir bir
odometri sinyalidir**. Yeni tetikleyici:

```python
SLIP_ACCUMULATION_THRESHOLD = 0.75   # 05_engel_kacinma.md tetikleyici tablosu
def check_slip_accumulation(travelled_m, commanded_m) -> TriggerResult
```

**Dürüstlük notu (belgeye yazılacak):** `i0=0.02, k=0.11` katsayıları **kalibre
edilmemiş literatür yaklaşımıdır**, Ay regoliti için ölçülmüş değil. Bu bir
*düzeltme yönü* iddiasıdır, *büyüklük* iddiası değil. `layer_validity` desenine
uygun olarak `slip_model_validity = "UNCALIBRATED"` etiketlenir.

**Testler:** `slip_ratio(0) ≈ i0`; monotonluk; 0.9 tavanı; `effective_distance`
düz zeminde ≈ girdi; `slip_ratio(20°)` beklenen %22 fazla enerjiyi veriyor.

---

### Task 4 — `backend/app/skyline.py`: DEM'den mutlak konum ⭐

**Amaç:** Faz 7'nin özgün katkısı. Rover'ın gördüğü ufuk profilini, DEM'den
üretilmiş referans ufuklarla eşleyerek **drift'siz mutlak konum** vermek.

**Neden bu bizde neredeyse bedava:** `horizon_map()` zaten *her hücre için her
azimutta ufuk açısı* döndürüyor. Skyline matching'in referans veritabanı budur.
Yapılacak tek şey, gözlenen bir ufuk profilini bu küpte aramak.

```python
def match_skyline(observed_horizon_deg,   # (n_azimuth,) gozlem
                  horizon_cube,           # (n_azimuth, H, W) horizon_map() ciktisi
                  search_mask=None,       # koridor cevresine sinirla
                  ) -> SkylineFix:
    """Gozlenen ufuk profilini DEM referans kupuyle esle.
    Skor: azimut ekseninde SSD; en iyi hucre + ikinci-en-iyi orani guven olcusu."""
# SkylineFix: row, col, x_m, y_m, score, confidence, ambiguity_ratio
```

Ek olarak, **yönelim** için SPICE köprüsü:

```python
def expected_sun_angles(timestamp_utc, lat, lon) -> tuple[float, float]:
    """ephemeris.py'yi kullanarak beklenen gunes azimut/yukseklik acisi.
    Bir gunes sensoru olcumu bununla karsilastirilarak mutlak heading verir --
    Ay'da manyetik pusula olmadigi icin mutlak yonelimin tek yolu budur."""
```

**Sınırın dürüstçe belirtilmesi (zorunlu):** 5 m/px DEM'den üretilen ufuk profili,
gerçek bir kameranın gördüğü ufuk çizgisinin **düşük geçirgen filtrelenmiş**
halidir. Yakın alan topografyası (< birkaç yüz metre) temsil edilmez. Bu bir
**arayüz ve fizibilite kanıtıdır, konum belirleme ürünü değildir.** Belirsiz
arazide (düz plato) `ambiguity_ratio` yüksek çıkar ve fonksiyon bunu **söylemek
zorundadır** — sessizce yanlış hücre döndürmek yasak.

**Testler:** sentetik DEM'de bilinen bir hücrenin ufkunu al → `match_skyline`
o hücreyi bulmalı; gürültü eklenince hâlâ komşulukta kalmalı; düz (özniteliksiz)
DEM'de `ambiguity_ratio` yüksek olmalı; `search_mask` arama alanını gerçekten
daraltmalı.

---

### Task 5 — Kabuk entegrasyonu: `/api/pose` + ROS 2 odometri aboneliği

**FastAPI tarafı:**

```
POST /api/pose   ->  PoseEstimate al, aktif Corridor'a projekte et,
                     evaluate_triggers() kostur,
                     {corridor_fix, fired_triggers, recommended_action} dondur
```

Mevcut `POST /api/replan` bu çıktıyı tüketecek şekilde bağlanır — böylece
**kapalı döngü** ilk kez uçtan uca kurulmuş olur: poz → sapma → tetikleyici → replan.

**ROS 2 tarafı (`lunapath_ros`):**

- `nav_msgs/Odometry` aboneliği (herhangi bir odometri düğümü — KISS-ICP dahil — bunu yayınlar)
- `conversions.py`: `odometry_to_pose_estimate()` — **`pose_to_pixel()` zaten var**, yarısı hazır
- Tetiklenen tetikleyiciler `lunapath_msgs/ReplanTrigger` olarak yayınlanır (yeni mesaj)

**Neden `nav_msgs/Odometry`:** bu, hangi odometri algoritmasının kullanıldığından
bağımsız standart arayüz. KISS-ICP takarsanız da, Stanford'un stereo VO'sunu
takarsanız da LunaPath tarafı değişmez. **Sözleşme temelli tasarımın bütün amacı bu.**

---

### Task 6 — `scripts/localization_budget.py`: belirsizlik bütçesi raporu

**Amaç:** "Ne kadar sürede bir durup mutlak konum almalıyım?" sorusunu sayıyla
cevaplamak — ve bunu **koridor yarı genişliğine** bağlamak.

Model: `sigma(d) = sigma_0 + drift_rate * d`, literatür drift oranlarıyla:
ölü hesap **%10**, görsel odometri **%0.2–2.5** (bkz. §2.1).

Rapor (`docs/research/localization_budget.md`) şu tabloyu üretir:

| Odometri kaynağı | Drift oranı | Koridor yarı genişliği (medyan) | Sıfırlamasız gidilebilecek mesafe |
|---|---|---|---|
| Ölü hesap (tekerlek+IMU) | %10 | *plandan* | *hesaplanır* |
| Görsel odometri (M2020 sınıfı) | %0.5 | *plandan* | *hesaplanır* |
| VO + skyline sıfırlama | drift sıfırlanır | — | koridor boyu |

**Bu tablo bir sunum silahıdır:** LunaPath'in ürettiği koridor genişliğinin,
gerçek bir odometri yığınının hata bütçesiyle **uyumlu olup olmadığını** gösterir.
Koridor çok darsa, plan uygulanamaz — bunu önceden bilmek gerekir.

---

## 5. Bağımlılıklar ve sıra

```
Task 1 (PoseEstimate)
   |-> Task 2 (localization.py) --> Task 5 (kabuklar) --> Task 6 (butce raporu)
   `-> Task 3 (slip_model.py)   --> Task 5
Task 4 (skyline.py)  <- horizon.py'ye bagli (Faz 1'de hazir), digerlerinden bagimsiz
```

- **Zorunlu sıra:** T1 → T2 → T5. T6, T2 ve T3'ten sonra.
- **Paralelleştirilebilir:** T3 ve T4, T2'den bağımsız.
- **Önkoşul:** Faz 1 (`horizon.py`, `ephemeris.py`) ✅ hazır · Faz 2 (`Corridor`) ✅ hazır · Faz 4 (ROS 2 kabuğu) ✅ hazır
- **Faz 5 ile ilişki:** Faz 5'in `virtual_lidar.py`'si Task 4 ile aynı ray-marching çekirdeğini kullanır. İkisi birlikte yapılırsa çekirdek bir kez optimize edilir.

**Efor tahmini (tek geliştirici, seri):**

| Task | Efor |
|---|---|
| T1 `pose.py` | 0.5 gün |
| T2 `localization.py` | 1 gün |
| T3 `slip_model.py` | 0.5 gün |
| T4 `skyline.py` ⭐ | 2 gün |
| T5 kabuk entegrasyonu | 1.5 gün |
| T6 bütçe raporu | 0.5 gün |
| **Toplam** | **6 gün** (T3‖T4 paralel: ~5 gün) |

---

## 6. Riskler

| Risk | Etki | Azaltım |
|---|---|---|
| Skyline matching düz arazide belirsiz | 🟠 T4 sonuç vermez | `ambiguity_ratio` **zorunlu çıktı**; belirsizlik yüksekse fonksiyon "eşleşme yok" der. Başarısızlık sessiz değil, raporlu |
| Slip katsayıları kalibre değil | 🟠 Yanlış sayı iddiası | `slip_model_validity="UNCALIBRATED"`; belgede ve API çıktısında etiketli. Yön iddiası ✅, büyüklük iddiası ❌ |
| `horizon_map()` bellek yükü — `(72, H, W)` float32 | 🟡 500×500'de ~72 MB, kabul edilebilir; daha büyük grid'de sorun | Arama `search_mask` ile koridor çevresine sınırlanır; küp zaten diskte cache'li |
| Poz konvansiyon karışıklığı (heading sıfır noktası) | 🔴 Faz 2'nin C2 bulgusunun tekrarı | `grid_frame.py` deseni: tek kanonik dönüşüm, `pose.py`'de docstring'e yazılı, asimetrik fixture ile birim testi |
| GPL bulaşması (FAST-LIO2) | 🔴 MIT dağıtımı riski | Faz 7 hiçbir odometri kütüphanesini **link etmiyor** — yalnızca `nav_msgs/Odometry` mesajı tüketiyor. Lisans yüzeyi sıfır |

---

## 7. Kabul kriterleri

- [ ] `PoseEstimate` şeması tanımlı, `source` alanı zorunlu, testleri geçiyor
- [ ] `replan_triggers.py`'nin `corridor_violation` ve `localization_uncertainty`
      tetikleyicileri artık **gerçek bir pozdan** besleniyor — elle verilen sayıdan değil
- [ ] Yeni `slip_accumulation` tetikleyicisi + birim testi
- [ ] `slip_ratio(20°)` düzeltmesinin `f_energy`'ye etkisi sayısal tabloyla gösterilmiş
- [ ] `match_skyline()` sentetik DEM'de bilinen hücreyi buluyor; düz arazide
      **belirsizliği rapor ediyor**
- [ ] `POST /api/pose` → tetikleyici → `POST /api/replan` kapalı döngüsü uçtan uca test edilmiş
- [ ] ROS 2 tarafı `nav_msgs/Odometry` abone oluyor; hiçbir odometri kütüphanesi bağımlılık değil
- [ ] `docs/research/localization_budget.md` üretilmiş; koridor genişliği ile drift bütçesi karşılaştırılmış
- [ ] Belgede ve sunumda **"LunaPath odometri üretmez, tüketir ve DEM'iyle doğrular"**
      cümlesi net; hiçbir yerde SLAM/VO yaptığımız iddiası geçmiyor
- [ ] `skyline.py` çözünürlük sınırı (5 m/px DEM ≠ kamera ufku) belgede açıkça yazılı

---

## 8. Kaynaklar

**Sektörel araştırma (bu plan için yapıldı):**

1. [Full Stack Navigation, Mapping, and Planning for the Lunar Autonomy Challenge](https://arxiv.org/html/2603.17232v1) — Stanford NavLab, birinci; 0.04–0.06 m RMSE; [kod](https://github.com/Stanford-NavLab/lunar_autonomy_challenge)
2. [Visual SLAM with DEM Anchoring for Lunar Surface Navigation](https://arxiv.org/abs/2603.17229) — Dai, Casadesus Vila, Gao; IEEE Aerospace 2026
3. [ShadowNav: Crater-Based Localization](https://arxiv.org/abs/2301.04630) — JPL + Sydney; <10 m mutlak hata hedefi
4. [Sun Sensor Navigation for Planetary Rovers: Theory and Field Testing](https://furgalep.github.io/sbib/furgale_taes10.pdf) — Furgale; ±3°, JPL Mars Yard'da 3–4× iyileşme
5. [MoonRanger Passes Key NASA Review](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) — CMU; stereo VO + güneş pusulası
6. [CompSLAM (ETH RSL)](https://arxiv.org/pdf/2505.06483) · [lunar_planner (ETH RSL)](https://github.com/leggedrobotics/lunar_planner) — ETH'nin gerçek işi
7. [KISS-ICP](https://github.com/PRBonn/kiss-icp) — MIT, ROS 2, `pip install kiss-icp`
8. [ALPER: Vision based absolute localization](https://www.sciencedirect.com/science/article/pii/S0094576525006186) — Skyline Matching
9. [Two years of Visual Odometry on the MER](https://onlinelibrary.wiley.com/doi/10.1002/rob.20184) — Maimone; %10 ölü hesap hatası

**Repo içi:**

- `docs/research/ENTEGRASYON_TEKNOLOJILERI.md` §2.6 (Corridor), §2.7 (tetikleyiciler), §5.3–5.4 (odometri yığını), §7.1–7.3 (algı/SLAM)
- `docs/research/05_engel_kacinma.md` §3.1 (slip), tetikleyici tablosu
- `docs/research/10_sektorel_projeler_envanteri.md` §A1 (ETH), §C2 (MoonRanger)

---

## 9. Sonraki adım

Bu plan onaylanırsa yürütme sırası: **T1 → T2 → T3 → T5 → T6**, T4 paralel.
Her task kendi commit'i, kendi testleriyle — `superpowers:executing-plans` deseni.
