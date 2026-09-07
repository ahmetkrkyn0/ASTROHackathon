# 10 — Sektörel Ay Rota Planlama Projeleri Envanteri

> **Amaç:** Şu anda gerçekten var olan, kullanılan veya yayınlanmış Ay yüzeyi rota/traverse planlama projelerini tek yerde toplamak. Her kayıt için: **kim yaptı, ne kullandı, ne yaptı, kod açık mı, kaynak nerede.**
>
> **Nasıl okunur:** Her kayıtta `🔓` = kod/veri açık, `🔒` = kapalı/kurum içi, `📄` = yayın var kod yok. `⭐` = LunaPath'in doğrudan ödünç alabileceği/karşılaştırması gereken kayıt.
>
> **Doğruluk notu:** Aşağıdaki bilgiler açık web kaynaklarından derlendi. Depo yıldız sayıları, sürümler ve misyon tarihleri değişkendir; **kullanmadan önce bağlantıdan teyit edin.** Fetch edilemeyen (403/paywall) kaynaklarda ayrıntı seviyesi düşüktür ve bu belirtilmiştir.
>
> **Tarih:** 10 Ağustos 2026

---

## Özet: manzaranın şekli

Araştırmanın en önemli çıkarımı şu: **Ay rota planlama alanı üç ayrı dünyaya bölünmüş ve bu dünyalar birbirini pek okumuyor.**

| Dünya | Kim | Ne yapıyor | Kod |
|---|---|---|---|
| **1. Kurum operasyon araçları** | NASA JPL/Ames, ESA | Gerçek misyonları planlıyor; olgun, ağır, GIS-merkezli | Kısmen açık (MMGIS, xGDS) |
| **2. Akademik planlayıcılar** | Üniversiteler (ETH, CMU, Toronto, Çin) | Algoritma yeniliği; çok kriterli, zaman-farkında | Nadiren açık |
| **3. Ticari rover şirketleri** | Lunar Outpost, Astrobotic, ispace, Astrolab | Uçan donanım + kapalı otonomi yığını | Kapalı |

**LunaPath'in konumu:** 2. dünyada (akademik planlayıcı), ama 1. dünyanın araçlarını (MMGIS/Moon Trek) hiç kullanmıyor ve 2. dünyadaki en yakın rakiplerini ([09](09_olgunluk_kiyaslama.md) §2.2) referans almıyor. Bu envanterin işi o boşluğu kapatmak.

---

## A. Açık kaynak, doğrudan Ay rota planlama

### A1. ⭐🔓 `leggedrobotics/lunar_planner` — ETH Zürich Robotic Systems Lab

**LunaPath'e en yakın açık kaynak proje. Mutlaka incelenmeli.**

| | |
|---|---|
| **Kim** | ETH Zürich, Robotic Systems Lab (Julia Richter vd.) |
| **Ne** | Gezegen araştırmacıları için Ay misyon planlamasını basitleştiren araç: **rota planlama** + **rota analizi** |
| **Yaklaşım** | Dört bacaklı (quadruped) robot için **çok amaçlı (multi-objective) global rota planlama optimizasyonu**; enerji verimliliği ve aydınlanma dikkate alınıyor |
| **Veri** | 3 hazır bölge: Aristarchus Irregular Mare Patch, Aristarchus Central Peak, Herodotus Mons; ek haritalar wiki'den indirilebilir |
| **Stack** | Python 3.8+, **GDAL**, GUI; Linux/macOS/Windows; Ubuntu ve Windows için hazır ikili dosyalar (Git LFS) |
| **Lisans** | **MIT** |
| **Yayın** | Richter vd., *Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot*, iSpaRo 2024 |
| **Kaynak** | [GitHub](https://github.com/leggedrobotics/lunar_planner) · [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) |

**LunaPath ile karşılaştırma:**

| | LunaPath | lunar_planner |
|---|---|---|
| Çok kriterli maliyet | ✅ 4 kriter (eğim/enerji/gölge/termal) | ✅ Çok amaçlı optimizasyon |
| Termal kriter | ✅ (sentetik) | ❌ |
| Aydınlanma | 🟡 Elevasyon proxy | ✅ |
| GUI | ✅ Web (React) | ✅ Masaüstü |
| Rota analizi | 🟡 Metrikler | ✅ Ayrı analiz aracı |
| Platform | Tekerlekli rover | Dört bacaklı robot |
| Lisans | MIT | MIT |

> **Aksiyon:** Bu depoyu klonlayıp `path analysis tool` kısmını inceleyin. LunaPath'in metrik seti ile karşılaştırıp eksik metrikleri alın. **Termal kriter LunaPath'in gerçek farkı** — bunu net söyleyebilmek için rakibin ne yapmadığını bilmek gerekir.

### A2. ⭐🔓 `Stanford-NavLab/lunar_autonomy_challenge` — Stanford NavLab

**Lunar Autonomy Challenge birincisi. Uçtan uca çalışan bir Ay otonomi yığını, açık kaynak.**

| | |
|---|---|
| **Kim** | Stanford NavLab |
| **Ne** | NASA/JHU-APL Lunar Autonomy Challenge için tam yığın: lokalizasyon + haritalama + planlama |
| **Lokalizasyon** | Stereo görsel odometri + **pose graph SLAM**; **SuperPoint** (keypoint) + **LightGlue** (eşleme); GTSAM ile Levenberg-Marquardt, loop closure |
| **Haritalama** | Semantik etiketli 3D landmark'lardan iki harita: **geometrik harita** (180×180 grid, hücre yüksekliği = z medyanı) ve **kaya haritası** (majority voting) |
| **Planlama** | **Global:** lander etrafında yapılandırılmış spiral (iç içe 3×3 grid hücrelerinin çevresi). **Lokal:** sabit-eğrilikli **yay (arc) örnekleme**, hedef waypoint'e en yakın ve engelsiz yayı seç |
| **Segmentasyon** | **U-Net++**, simülatör görüntüleriyle fine-tune |
| **Sensör** | 8 monokrom kamera (ön/arka stereo çift, yan, kol üstü), her biri LED ışıklı + IMU |
| **Aydınlanma stratejisi** | Öğrenilmiş feature eşleme; SuperPoint+LightGlue **aşırı aydınlanma değişimine dayanıklı** olduğu için seçildi |
| **Sonuç** | Santimetre seviyesi lokalizasyon: **RMSE 0.038–0.061 m**; yarışma **1. sırası** |
| **Kaynak** | [GitHub](https://github.com/Stanford-NavLab/lunar_autonomy_challenge) · [arXiv 2603.17232](https://arxiv.org/html/2603.17232v1) |

> **Aksiyon:** LunaPath'in **eksik olduğu yerin** ([05](05_engel_kacinma.md) Katman 2) referans implementasyonu bu. Yerel yay-örnekleme planlayıcı ve LED'li kamera yaklaşımı, "kutupta perception nasıl yapılır" sorusunun somut cevabı. Kod okumak, sıfırdan yazmaktan hızlı.

### A3. 🔓 `NASA-AMMOS/MMGIS` — NASA JPL AMMOS

| | |
|---|---|
| **Kim** | NASA JPL, AMMOS (Advanced Multi-Mission Operations System) |
| **Ne** | **Multi-Mission Geographic Information System** — Dünya, Ay ve gezegen görselleştirme, araştırma, bilim, **planlama ve operasyon** için web tabanlı haritalama ve mekânsal veri altyapısı |
| **Kullanım** | Mars'ın tam ölçekli haritalanması için üretildi; Perseverance, Ingenuity, Curiosity rota izleri önyüklü demo |
| **Neden önemli** | LunaPath'in frontend'inin yeniden icat etmeye çalıştığı şeyin **gerçek misyon-sınıfı** hali |
| **Kaynak** | [GitHub](https://github.com/NASA-AMMOS/MMGIS) |

> **Aksiyon:** LunaPath'i MMGIS'e **rakip** değil, **eklenti** olarak konumlandırma seçeneğini değerlendirin. LunaPath backend'i bir planlama servisi olarak kalıp, görselleştirmeyi MMGIS'e bırakmak hem eforu düşürür hem "misyon araç zincirine entegre" iddiası verir. Bu, [09](09_olgunluk_kiyaslama.md)'daki *Use History* faktörünü yükseltir.

### A4. 🔓 `jasmeet0915/artemis_mission_simulator`

| | |
|---|---|
| **Ne** | ROS 2 tabanlı, **simülatör-agnostik Ay güney kutbu dijital ikizi**; Artemis misyonlarını simüle etmek için |
| **Amaç** | Rover, drone, humanoid ve diğer Ay yüzey sistemleri için plug-and-play test alanı |
| **Kaynak** | [GitHub](https://github.com/jasmeet0915/artemis_mission_simulator) · [Open Robotics Discourse duyurusu](https://discourse.openrobotics.org/t/introducing-artemis-mission-simulator-attempting-to-simulate-nasas-artemis-missions-on-moon-before-they-actually-go/55387) |

### A5. 🔓 Küçük ölçekli / öğrenci depoları (düşük olgunluk, referans amaçlı)

| Depo | Ne | Not |
|---|---|---|
| [`rakshanda33/Lunar-Navigation-Path-Planner`](https://github.com/rakshanda33/Lunar-Navigation-Path-Planner) | Güney kutbunda güneş enerjili rover için 100 m+ güvenli rota; **Chandrayaan görüntüsü**; engelden kaçınma + 10+ bilimsel durak; arazi ve güneş maruziyeti optimizasyonu | LunaPath'e konsept olarak yakın, ölçek çok küçük |
| [`alessioborgi/MoonBot-Navigation`](https://github.com/alessioborgi/MoonBot-Navigation) | C++; **Dijkstra** rota planlama + SLAM + engel tespiti + gripper | Robotik odaklı |
| [`knamatame0729/ORBSLAM3-Semantic-Mapping`](https://github.com/knamatame0729/ORBSLAM3-Semantic-Mapping) | Semantik segmentasyon + ORB-SLAM3 → rover tabanlı **Ay arazi haritalama**, 3D semantik harita | Perception tarafı |
| `chandrabhraman/lunar-rover-path-planning` | MATLAB tabanlı Ay rover rota planlama | [MATLAB Central](https://www.mathworks.com/matlabcentral/fileexchange/128759-lunar-rover-path-planning) · *ayrıntılar doğrulanmadı* |
| `iamLakshikaTanwar/bah2026-ps8` | Chandrayaan-2 radar ile yüzey altı su-buzu + **rota planlama, DEM, enerji-farkında rover traverse planlama** | Hackathon projesi (BAH 2026) |

> **Dürüst değerlendirme:** A5'teki depolar LunaPath'ten daha olgun değil. Bunları **rakip** değil, "bu problemin popüler olduğunun kanıtı" olarak görün. LunaPath'in gerçek rakipleri A1, A2 ve D bölümündeki yayınlardır.

---

## B. Kurum araçları (NASA / ESA)

### B1. ⭐🔓 NASA Moon Trek (Solar System Treks Project, JPL)

| | |
|---|---|
| **Kim** | NASA JPL, Solar System Treks Project (SSTP) |
| **Ne** | Tarayıcı tabanlı gezegen veri görselleştirme ve analiz portalı |
| **Araçlar** | **Görüş hattı (line of sight) analizi**, **traverse rota planlama**, **3D traverse rota görselleştirme** |
| **Hedef** | *"Moon Trek'in en yeni araçları Artemis dönemi Ay misyon planlaması ve keşfi için hedeflenmiştir"* |
| **Kaynak** | [trek.nasa.gov/moon](https://trek.nasa.gov/moon/) · [EGU 2023 bildirisi (ADS)](https://ui.adsabs.harvard.edu/abs/2023EGUGA..25..969L/abstract) |

> **Bu, LunaPath'in en doğrudan kurumsal karşılığıdır ve NASA tarafından ücretsiz sunulmaktadır.** Moon Trek'te traverse planlama zaten var. **LunaPath'in ayrışması gereken yer tam burası:** Moon Trek geometrik/görsel planlama yapar; LunaPath **fizik-temelli çok kriterli maliyet + rover donanım sağlığı** getirir. Sunumda bu karşılaştırmayı **kendiniz** yapın — jüri yapmadan önce.

### B2. 🔓 NASA Ames xGDS — Exploration Ground Data Systems

| | |
|---|---|
| **Kim** | NASA Ames Research Center, Intelligent Robotics Group (IRG) |
| **Ne** | NASA analog saha deneylerini destekleyen yazılım araçları; iki ana ürün: **xGDS Web Tools** ve **VERVE** (Visual Environment for Remote Virtual Exploration) |
| **Yetenek** | Gözlem notları, enstrüman verisi, fotoğraf, video, örneklerin zaman ve haritalanmış konumunu senkronize ederek hızlı bilimsel karar desteği |
| **⭐ Kritik detay** | *"Araçlar, süre ve kat edilen mesafeyi tahmin etmek için **basit bir araç yetenek modeli** (ör. hız, veri toplama aktiviteleri) içeren bir **traverse planlayıcı** sağlar"* |
| **Kaynak** | [NASA Ames xGDS](https://ti.arc.nasa.gov/tech/asr/groups/intelligent-robotics/xgds/) · [NTRS Overview](https://ntrs.nasa.gov/api/citations/20190025706/downloads/20190025706.pdf) · [Acta Astronautica 90:268](https://www.sciencedirect.com/science/article/pii/S0094576512000057) |

> **Aksiyon:** xGDS'in traverse planlayıcısı **"basit bir araç yetenek modeli"** kullanıyor. LunaPath'in modeli bundan **çok daha zengin** (fizik-temelli enerji, termal, log-barrier). Bu, LunaPath'in katkısını konumlandırmak için mükemmel bir karşılaştırma noktasıdır: *"Mevcut analog planlama araçları basit hız/mesafe modelleri kullanıyor; biz fizik-temelli çok kriterli bir maliyet modeli getiriyoruz."*

### B3. 🔒 JPL RSVP — Robot Sequencing and Visualization Program

| | |
|---|---|
| **Kim** | NASA JPL |
| **Ne** | Mars rover hareketlerinin **tamamının** planlandığı operasyon yazılımı: yüzeyde sürüş + karmaşık robotik kol/turret etkileşimleri |
| **Miras** | Mars Pathfinder → MER → MSL → Mars 2020 |
| **M2020 eklentileri** | **MobSketch**, **ArmSketch** (sekans otomasyonu), **SSim** (flight-software-in-the-loop simülasyon), hedef değerlendirme ve rafinasyon |
| **Kod** | 🔒 Kapalı |
| **Kaynak** | [RSVP for MSL](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/rsvp-msl/) · [RSVP Mars 2020](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-2020-rover/rsvp-mars-2020/) |

> **Neden önemli:** LunaPath'in "operatör karar desteği" konumlandırması için **altın standart referans**. RSVP'nin varlığı, insan-döngüde rota planlama araçlarının gerçek ve vazgeçilmez olduğunu kanıtlar ([09](09_olgunluk_kiyaslama.md) §2.3).

### B4. ⭐ NASA VIPER'ın yer yazılımı — **açık kaynak yığın kullanıyor**

Bu, envanterin en çarpıcı bulgularından biri:

| | |
|---|---|
| **Misyon** | VIPER (Volatiles Investigating Polar Exploration Rover), Ay güney kutbu; iptal (2024) → diriltildi (2025), Blue Moon MK1 ile 2027 hedefi |
| **Yer araçları** | *"VIPER'ın Dünya tabanlı operasyon araçlarının, hesaplama modüllerinin ve yüksek doğruluklu simülasyonlarının çoğu **ROS 2 ve Gazebo** tabanlıdır"* |
| **Telemetri/analiz** | **NASA Open MCT** (web tabanlı telemetri görüntüleme) VIPER dahil misyonlarda kullanılıyor |
| **Alıntı** | *"VIPER yerde ROS kullanıyor — bu kadar çok insanın bu kadar düzenli kullandığı bir şey"* |
| **Kaynak** | [MIT Technology Review: NASA's next lunar rover will run open-source software](https://www.technologyreview.com/2021/04/12/1022420/nasa-lunar-rover-viper-open-source-software/) |

> **LunaPath için stratejik sonuç:** Ay kutup misyonunun **kendi yer planlama araçları ROS 2 + Gazebo üzerine kurulu.** Yani LunaPath'in [04](04_acik_kaynak_modeller.md)'te "ROS 2/Nav2 desenini ödünç al" tavsiyesi, sadece iyi mühendislik değil — **hedef misyonun fiili standardıyla hizalanmak** anlamına geliyor. Bunu sunumda söylemek konumlandırmayı ciddi biçimde güçlendirir.

### B5. 🔓 Space ROS — NASA + Blue Origin + Open Robotics

| | |
|---|---|
| **Ne** | ROS 2'den türetilmiş, **güvenlik-kritik uzay robotiği** için sertleştirilmiş açık kaynak çatı; ROS 2 API'sine uyumlu, platform/proje bağımsız |
| **Kim** | NASA, Open Robotics, Blue Origin ortaklığı (Blue Origin–NASA anlaşmasıyla başladı) |
| **Demolar** | Canadarm2, Curiosity rover, **Ay arazisi** |
| **Kaynak** | [github.com/space-ros](https://github.com/space-ros) · [space.ros.org](https://space.ros.org/pages/faq.html) · [AIAA SciTech 2023](https://arc.aiaa.org/doi/10.2514/6.2023-2709) · [NTRS PDF](https://ntrs.nasa.gov/api/citations/20220017761/downloads/Space_ROS_SciTech.pdf) |

### B6. 📄 ESA ADE (OG10) — Autonomous Decision Making in Very Long Traverses

| | |
|---|---|
| **Kim** | H2020, GMV koordinasyonlu; DFKI Bremen, Oxford vd. (ESA Space Robotics Technologies SRC kümesi) |
| **Hedef** | Gezegen rover keşfi için kapsamlı otonom sistem: **sol başına ≥1 km** traverse, bilimsel veri toplamayı maksimize etme, nominal ve beklenmedik durumlarda uygun kararlar, her an güvenliği sağlama |
| **Ana bileşen** | **ADAM** (Autonomous Decision Making Module) — ilginç özellik bulunduğunda veya **çevresel tehlike tanındığında** nominal planı otonom ve güvenli şekilde değiştirir |
| **Kaynak** | [h2020-ade.gmv.com](https://h2020-ade.gmv.com/) · [DFKI proje sayfası](https://robotik.dfki-bremen.de/en/research/projects/ade-og10.html) · [i-SAIRAS 2020 bildirisi](https://www.hou.usra.edu/meetings/isairas2020fullpapers/pdf/5033.pdf) · [CORDIS 821988](https://cordis.europa.eu/project/id/821988) |

> **Aksiyon:** ADAM'ın "tehlike tanındığında planı değiştir" mantığı, LunaPath'in [05](05_engel_kacinma.md) §4.3'teki **replanning tetikleyicileri** tablosunun kurumsal karşılığıdır. i-SAIRAS bildirisi ücretsiz PDF — tetikleyici taksonomisini oradan alıp LunaPath'e uyarlayın.

### B7. 📄 ESA EMRS — European Moon Rover System

| | |
|---|---|
| **Ne** | Gelecek karmaşık Ay misyonları için modüler, çok amaçlı rover |
| **Durum** | **Breadboard + analog saha test kampanyası** yapıldı |
| **Neden önemli** | TRL 3 → 4/5 yolculuğunun somut örneği ([09](09_olgunluk_kiyaslama.md)) |
| **Kaynak** | [arXiv 2411.13978](https://arxiv.org/pdf/2411.13978) |

### B8. 🔒/📄 Space Applications Services — LUVMI / LUVMI-X / LUVMI-M

| | |
|---|---|
| **Kim** | Space Applications Services (BE), ESA fonlu + ticari |
| **Ne** | Düşük kütleli, modüler, genişletilebilir Ay rover platform ailesi; yük taşıma ve mobilite |
| **Otonomi** | **Tele-operasyonlu, opsiyonel otonom modlar** — daha hızlı traverse ve **PSR'a girerken güvenlik** için |
| **⭐ LunaPath bağlantısı** | **`LUVMI-M`, LunaPath'in rover kataloğunda mevcut** (`constants.py`) — yani projeniz zaten gerçek bir Avrupa rover platformunu parametrize ediyor. Bunu vurgulayın. |
| **Kaynak** | [spaceapplications.com/products/lunar-rover-luvmi-x](https://www.spaceapplications.com/products/lunar-rover-luvmi-x) · [Yeni misyon duyuruları](https://www.spaceapplications.com/news/space-applications-services-expands-lunar-rover-development-with-new-commercial-and-esa-funded-missions) |

---

## C. Ticari şirket projeleri (uçmuş / uçacak)

Bu bölümdeki otonomi yazılımlarının hiçbiri açık kaynak değil. Değeri: **hangi yeteneklerin gerçekten uçtuğunu** göstermesi.

### C1. ⭐ Lunar Outpost — MAPP (Mobile Autonomous Prospecting Platform)

| | |
|---|---|
| **Kim** | Lunar Outpost (US) |
| **Misyon** | **Lunar Voyage 1**, Mart 2025, Intuitive Machines IM-2 lander ile |
| **Sonuç** | **İlk ABD ticari rover'ı Ay yüzeyine ulaştı**; ancak lander yan yattığı için rover **dışarı çıkamadı** |
| **⭐ Kritik detay** | Buna rağmen alt sistemler **TRL 9** doğrulaması aldı: **navigasyon bilgisayarı**, **otonom termal kontrol sistemi**, **stereo kameralar**, güç yönetimi. *"Ana otonomi sistemleri ve yazılımı TRL 9'a ulaştı."* |
| **İş modeli** | "Rover-as-a-service" — tek seferlik misyon değil, müşteri için veri üretimi; NASA ve DoD ilgisi |
| **Kaynak** | [NASASpaceflight: Lunar Outpost MAPP](https://www.nasaspaceflight.com/2025/12/lunar-outpost-mapp/) · [MAPP ürün sayfası](https://www.lunaroutpost.com/mapp) · [Lunar Voyage 1 Update](https://www.lunaroutpost.com/post/lunar-voyage-1-update) · [Space.com misyon kontrol](https://www.space.com/astronomy/moon/we-are-ready-to-drive-take-a-look-inside-lunar-outposts-moon-rover-mission-control-photos) |

> **LunaPath için en anlamlı kayıt bu.** "Otonom **termal kontrol** sistemi" TRL 9 aldı — yani **termal yönetim, ticari Ay rover'larında zaten birinci sınıf bir otonomi problemi.** LunaPath'in termal odağı moda değil, sektörün gerçek gündemi. Bu cümleyi sunuma koyun.

### C2. Astrobotic + CMU — MoonRanger

| | |
|---|---|
| **Kim** | Carnegie Mellon Üniversitesi + Astrobotic (+ NASA Ames işbirliği); teknik liderlik: William "Red" Whittaker |
| **Ne** | Bavul boyutunda otonom Ay rover'ı; NASA LSITP kapsamında **5.6 M$** sözleşme |
| **Otonomi** | Ay yüzeyinin **3D haritalarını** oluşturuyor; **uzun menzilli ve iletişim-kesintili (communication-denied) keşif** gösterimi; **stereo kamera ile görsel odometri + güneş sensörü** ile bağımsız yönelim |
| **⭐ LunaPath bağlantısı** | LPR-1 referans rover'ı **VIPER ve MoonRanger'dan türetildi** (`lunapath_referans_belgesi_2.md` §2.1) |
| **Kaynak** | [CMU RI: MoonRanger Passes Key NASA Review](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) · [Astrobotic: Final Production](https://www.astrobotic.com/astrobotics-moonranger-moves-into-final-production/) · [Astrobotic: $5.6M sözleşme](https://www.astrobotic.com/astrobotic-awarded-5-6-million-nasa-contract-to-deliver-autonomous-moon-rover/) |

> **"İletişim-kesintili keşif"** MoonRanger'ın tanımlayıcı yeteneği ve LunaPath'in [08](08_global_local_rotalama_yuku.md) §4'teki yer/rover iş bölümü tartışmasının tam merkezinde. Kutupta Dünya görünürlüğü kesintili olduğu için bu bir lüks değil zorunluluk.

### C3. Venturi Astrolab — FLEX Rover

| | |
|---|---|
| **Ne** | Robotik kargo taşıma + gelecekte mürettebatlı; Artemis dönemi lojistiği için **sürekli** yüzey operasyonu |
| **Otonomi** | **Üç sürüş modu: mürettebatlı, uzaktan (remote), tam otonom** |
| **Tasarım ömrü** | Bakımsız **10 yıla kadar** |
| **Kaynak** | [Payload Field Guide: Lunar Rovers](https://payloadspace.com/payload-field-guide-lunar-rovers/) · [SpaceNews: ground transportation contracts](https://spacenews.com/companies-race-to-win-ground-transportation-contracts-for-the-moon/) |

### C4. ispace + Toyota

| | |
|---|---|
| **Durum** | ispace Mission 2 (Resilience + **Tenacious** mikro-rover) Haziran 2025'te lazer telemetre (LRF) anomalisiyle çakıldı |
| **Yeni gelişme** | **Toyota**, ispace'in yeni nesil küçük rover geliştirmesine teknik değerlendirme ve sistem tasarımı desteği veriyor |
| **Ayrıca** | JAXA + Toyota **"Lunar Cruiser"** basınçlı rover: astronot yokken **otonom çalışacak** — sürekli keşif ve mobilite |
| **Kaynak** | [ispace: Toyota desteği](https://ispace-inc.com/news-en/?p=7983) · [Toyota LUNAR CRUISER](https://global.toyota/en/mobility/technology/lunarcruiser/index.html) · [ispace Mission 2 durum](https://ispace-inc.com/news-en/?p=7664) |

### C5. NASA JPL — CADRE

| | |
|---|---|
| **Ne** | 3 adet el bagajı boyutunda rover; **çok-robot dağıtık otonomi** teknoloji gösterimi |
| **Sensör** | 2 stereo kamera + navigasyon sensörleri + **multistatik yer-nüfuz radarı (GPR)** |
| **Uçuş** | IM-3 ile Reiner Gamma; pencere 2026'ya uzanıyor |
| **Otonomi iddiası** | Mission control'den **doğrudan komut almadan** işbirliği içinde veri toplama |
| **Kaynak** | [JPL CADRE](https://www.jpl.nasa.gov/missions/cadre/) · [NASA: Mini Rover Team Packed](https://www.nasa.gov/missions/tech-demonstration/cadre/nasas-mini-rover-team-is-packed-for-lunar-journey/) |

---

## D. Akademik planlayıcılar (LunaPath'in gerçek rakipleri)

### D1. ⭐📄 Lamarre, Malhotra & Kelly (2024) — Şans kısıtlı PSR keşfi

| | |
|---|---|
| **Ne** | Güneş enerjili rover ile Ay gölgeli bölge keşfi için **görev-seviyesi** rota planlama |
| **Yöntem** | **Şans kısıtlı (chance-constrained)** planlama problemi; bilinen ortalama oranlarda rastgele arızalar; mevcut planlama teknikleri + **stokastik erişilebilirlik (stochastic reachability)** analizi ile güvenli geçiş politikaları |
| **Doğrulama** | **Cabeus krateri** yörünge arazi ve aydınlanma haritaları; **LCROSS çarpma bölgesinde çok günlük, uzun menzilli sürüşler** |
| **Yayın** | IEEE Aerospace Conference (AERO'24), Big Sky MT, 2–9 Mart 2024 |
| **Kaynak** | [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) |

> **LunaPath'in en yakın komşusu.** Aynı problem, aynı tür bölge, daha ileri (stokastik) formülasyon. **Atıf zorunlu.** [09](09_olgunluk_kiyaslama.md) Aşama III madde 28: aynı bölgede senaryoyu tekrarlayıp doğrudan karşılaştırma yapmak.

### D2. ⭐📄 Distributed Safety-Map Path Planning (Remote Sensing 2025)

*"A Safe and Efficient Global Path-Planning Method Considering Multiple Environmental Factors of the Moon Using a Distributed Computation Strategy"*

| | |
|---|---|
| **Güvenlik kriterleri** | **Arazi eğimi, pürüzlülük (roughness), aydınlanma, kaya bolluğu (rock abundance)** ile bir güvenlik değerlendirme kural seti |
| **Yöntem** | **DPPS-STP** — güvenlik-haritası **karo piramidi (tile pyramid)** tabanlı dağıtık rota planlama stratejisi |
| **Algoritma** | **OC-WHT-A\*** — hash tablosu tabanlı open/closed listelerle **ağırlıklı A\***, **Spark cluster** üzerinde |
| **Sonuç** | Tehlikeli node sayısını azaltıyor, krater engellerinden kaçınıyor; uzun mesafeli görevlerde tek makineli OC-WHT-A*'a göre **ortalama 11.5× hızlanma** |
| **Kaynak** | [MDPI Remote Sensing 17(5), 924](https://www.mdpi.com/2072-4292/17/5/924) *(tam metin fetch edilemedi; ayrıntılar özet/arama snippet'inden)* |

> **LunaPath için üç ders:** (1) **Pürüzlülük ve kaya bolluğu** kriter olarak kullanılıyor — LunaPath'te ikisi de yok ([02](02_goruntu_isleme.md) §2.5, [07](07_termal_veri.md) §2.2 `ra`). (2) **Karo piramidi**, [08](08_global_local_rotalama_yuku.md) §3'teki hiyerarşi ihtiyacının somut çözümü. (3) Hız problemi gerçek ve çözümü dağıtım — LunaPath'in ön-hesaplama yaklaşımı ([08](08_global_local_rotalama_yuku.md) §2) daha hafif bir alternatif.

### D3. ⭐📄 Sun-Synchronous Path Planning (Remote Sensing 2025)

*"A Spatiotemporal U-Net-Based Data Preprocessing Pipeline for Sun-Synchronous Path Planning in Lunar South Polar Exploration"*

| | |
|---|---|
| **Konu** | Ay güney kutbunda **güneş-senkron** rota planlama için **uzamsal-zamansal (spatiotemporal) U-Net** tabanlı veri ön işleme hattı |
| **Neden kritik** | Başlık, LunaPath'in **en büyük eksiğini** (zaman ekseni, [08](08_global_local_rotalama_yuku.md) §3.3) doğrudan hedefliyor |
| **Kaynak** | [MDPI Remote Sensing 17(9), 1589](https://www.mdpi.com/2072-4292/17/9/1589) · DOI `10.3390/rs17091589` *(tam metin fetch edilemedi — **okunması gereken ilk yayın**)* |

> **Aksiyon: Bu yayını okuyun.** "Güneş-senkron rota planlama" = rover'ı güneşin hareketiyle senkronize hareket ettirmek, yani sürekli aydınlıkta kalmak. Kutup için doğru cevap büyük olasılıkla budur ve LunaPath'in `shadow_traverse` profili bunun kaba bir yaklaşımıdır.

### D4. 📄 Diğer önemli yayınlar

| Yayın | Katkı | Kaynak |
|---|---|---|
| **Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration** (2025) | Alanın taksonomisi; aydınlanma ve sıcaklık dalgalanmaları vurgusu; sabah/akşam ve yüksek enlem aydınlanmasının güç verimliliğine etkisi | [Remote Sensing 17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) |
| **Review of Global Path Planning Algorithms for Lunar Rovers Considering Spatiotemporal Constraints** (2026) | **Uzamsal-zamansal kısıtlar** özelinde derleme | [SciEngine ZRHT](https://www.sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012) |
| **A robust method for large-scale route optimization on lunar surface utilizing a multi-level map model** | **Çok seviyeli harita modeli** ile büyük ölçekli rota optimizasyonu → hiyerarşi | [Chinese J. Aeronautics](https://www.sciencedirect.com/science/article/pii/S1000936124005442) |
| **Risk-Aware Coverage Path Planning for Lunar Micro-Rovers** | Global (PDS DEM) + local (VLP-16 LiDAR) hibrit; **gerçek saha testi**; CLOVER 7 kg rover, ROS1, CoppeliaSim | [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) |
| **A Deep Learning Approach to Lunar Rover Global Path Planning Using Environmental Constraints and Rover Internal Resource Status** | Statik + zaman-değişken + yola-bağlı kısıtlar; **rover'ın beklemesine izin veriyor**; RL ile kaynak-kısıtlı en kısa yol | [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844) |
| **Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot** | A1'in yayını | [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) |
| **Learning-Based End-to-End Path Planning for Lunar Rovers with Safety Constraints** | Uçtan uca öğrenilmiş planlama | [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/) |
| **Deep Probabilistic Traversability with Test-time Adaptation** | Belirsizlik-farkında gezegen rover navigasyonu | [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) |
| **LunarLoc: Segment-Based Global Localization on the Moon** | Segment tabanlı global lokalizasyon | [arXiv 2506.16940](https://arxiv.org/pdf/2506.16940) |
| **Visual SLAM with DEM Anchoring for Lunar Surface Navigation** | Yörünge DEM'ine sabitlenmiş SLAM ile drift sıfırlama | [arXiv 2603.17229](https://arxiv.org/pdf/2603.17229) |
| **Transferable Deep RL for Cross-Domain Navigation: from Farmland to the Moon** | Domain transfer ile Ay navigasyonu | [arXiv 2510.23329](https://arxiv.org/pdf/2510.23329) |
| **CISRU: robotics software suite for rover-rover and astronaut-rover interaction** | Çok-ajan Ay/Mars robotik yazılım paketi | [arXiv 2311.03122](https://arxiv.org/pdf/2311.03122) |

---

## E. Yarışma: Lunar Autonomy Challenge (NASA + JHU/APL + Caterpillar)

| | |
|---|---|
| **Kim** | NASA, Johns Hopkins APL, **Caterpillar Inc.**, Embodied AI; APL tarafından NASA için yönetiliyor |
| **Simülatör** | **Unreal Engine + CARLA** özel Ay sürümü; gerçekçi araç dinamiği, fotogerçekçi Ay arazisi |
| **Görev** | Simüle lander etrafındaki **27 m × 27 m** bölgeyi haritalamak; araç: NASA **ISRU Pilot Excavator (IPEx)** rover'ının dijital ikizi (4 tekerlek, diferansiyel direksiyon, **8 monokrom kamera**) |
| **Kapsam** | 2025 sürümü **sadece haritalama** (kazı dahil değil) |
| **Ölçek** | Nitelemede **31 takım**, 15 eyaletten **229 öğrenci**; final Şubat 2025 sonrası, kazananlar Mayıs 2025 |
| **Kaynak** | [lunar-autonomy-challenge.jhuapl.edu](https://lunar-autonomy-challenge.jhuapl.edu/) · [Challenge dokümantasyonu](https://lunar-autonomy-challenge.jhuapl.edu/Challenge-Documentation/index.php) · [NASA STMD seçilen takımlar](https://www.nasa.gov/directorates/stmd/lunar-autonomy-challenge-selected-teams) |

> **LunaPath ekibi için doğrudan fırsat:** Bu, tam olarak sizin profilinizdeki bir yarışma (öğrenci ekibi, Ay otonomisi, simülatör tabanlı). Birinci olan takımın kodu açık (A2). Gelecek çağrıları takip edin — LunaPath'in kod tabanı buraya taşınabilir bir temel.

---

## F. Planlama için altyapı: simülatörler, veri setleri, araçlar

Bu bölüm [04](04_acik_kaynak_modeller.md) ile örtüşür; burada sadece **envanter satırları** olarak veriliyor.

| Ad | Ne | Lisans/erişim | Kaynak |
|---|---|---|---|
| **OmniLRS** | Isaac Sim tabanlı Ay robotiği simülatörü; prosedürel arazi, çok-robot, sentetik veri hattı, ROS1+ROS2 | Açık | [GitHub](https://github.com/OmniLRS/OmniLRS) · [arXiv 2309.08997](https://ar5iv.labs.arxiv.org/html/2309.08997) |
| **LunarSim** | Yüksek görsel doğruluk + ROS 2, CV algoritma geliştirme | Açık | [GitHub](https://github.com/PUTvision/LunarSim) |
| **Space Robotics Bench (SRB)** | Isaac Sim üzerine uzay robotiği görev/ortam koleksiyonu | Açık | [andrejorsula.github.io/space_robotics_bench](https://andrejorsula.github.io/space_robotics_bench) |
| **PANGU** | Dundee Üniversitesi/ESA gezegen-asteroit sahne üretim aracı | ESA/lisanslı | [pangu.software](https://pangu.software) |
| **Ames Stereo Pipeline** | DTM, ortogörüntü, 3D nokta bulutu üretimi (stereo + SfS) | Apache 2.0 | [GitHub](https://github.com/NeoGeographyToolkit/StereoPipeline) |
| **NASA POLAR / POLAR Traverse** | Gerçek HDR stereo, kutup benzeri aydınlanma | Açık | [POLAR](https://ti.arc.nasa.gov/dataset/IRG_PolarDB/) · [Traverse](https://ti.arc.nasa.gov/dataset/PolarTrav/) |
| **POLAR-Sim** | POLAR'ın digital twin'i + **23.000 etiket** | Açık | [arXiv 2309.12397](https://arxiv.org/abs/2309.12397) · [Dryad](https://datadryad.org/dataset/doi:10.5061/dryad.ksn02v7hf) |
| **LuSNAR** | 108 GB, 9 UE sahne, stereo+LiDAR+IMU, semantik/derinlik/poz | Açık | [GitHub](https://github.com/zqyu9/LuSNAR-dataset) |
| **cFS / F´** | NASA uçuş yazılımı çatıları | Apache 2.0 | [cFS](https://cfs.gsfc.nasa.gov) · [F´](https://fprime.jpl.nasa.gov) |
| **awesome-space-robotics** | Uzay robotiği kaynak listesi (küratörlü) | Açık | [GitHub](https://github.com/AndrejOrsula/awesome-space-robotics) |
| **heat1d** | Gezegen 1-B termal modeli (Diviner ekibi) | Açık | [GitHub](https://github.com/phayne/heat1d) |

---

## G. LunaPath vs sektör: kim ne kullanmış tablosu

| Proje | DEM | Aydınlanma | Sıcaklık | Pürüzlülük | Kaya | Zaman ekseni | Bekleme kararı | Stokastik | Yerel planlayıcı | Kod |
|---|---|---|---|---|---|---|---|---|---|---|
| **LunaPath (bugün)** | ✅ LOLA 80 m | 🟡 Proxy | 🟡 Sentetik | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | 🔓 MIT |
| **LunaPath (Aşama II hedefi)** | ✅ 5–20 m | ✅ LOLA | ✅ Diviner | ✅ SfS | ✅ `ra` | 🟡 L2 | ❌ | ❌ | 🟡 Arayüz | 🔓 |
| ETH `lunar_planner` (A1) | ✅ | ✅ | ❌ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | 🔓 MIT |
| Stanford NavLab (A2) | ❌ (in-situ) | — | ❌ | ✅ | ✅ | — | ❌ | ❌ | ✅ Arc | 🔓 |
| NASA Moon Trek (B1) | ✅ | ✅ | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | ❌ | 🔓 Portal |
| NASA xGDS (B2) | ✅ | 🟡 | ❌ | ❌ | ❌ | ✅ Süre | ❌ | ❌ | ❌ | 🔓 |
| Lamarre vd. (D1) | ✅ | ✅ | 🟡 | ❌ | ❌ | ✅ Çok günlük | ✅ | ✅ **Şans kısıtlı** | ❌ | 📄 |
| DPPS-STP (D2) | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | 📄 |
| Sun-Synchronous (D3) | ✅ | ✅ | 🟡 | ? | ? | ✅ | ? | ? | ❌ | 📄 |
| Risk-Aware Coverage (D4) | ✅ | ❌ | ❌ | ✅ Pitch | ✅ LiDAR | ❌ | ❌ | ❌ | ✅ Bug | 📄 |
| Sensors 24(3) 844 (D4) | ✅ | ✅ | ✅ Isı akısı | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | 📄 |

### Tablonun söylediği üç şey

1. **LunaPath'in özgün olduğu tek kolon "Sıcaklık"** — ve o kolon bugün sentetik. [07](07_termal_veri.md)'yi uygulamak, tablodaki tek gerçek farkı **gerçek** yapmak demektir. Bu, tüm yol haritasının en yüksek getirili işidir.
2. **Pürüzlülük ve kaya, rakiplerin çoğunda var, LunaPath'te yok.** İkisi de indirilebilir ürünle geliyor (SfS roughness, Diviner `ra`) — yani düşük efor, doğrudan rekabet paritesi.
3. **Zaman ekseni + bekleme kararı, en olgun üç çalışmanın (D1, D3, Sensors 844) ortak özelliği.** LunaPath'te ikisi de yok. Bu, alanın "state of the art" çizgisi ve LunaPath'in en belirgin geride kaldığı yer.

---

## H. Doğrudan ödünç alınabilecek 10 şey (öncelik sıralı)

| # | Ne | Kimden | Neden | Efor |
|---|---|---|---|---|
| 1 | **Rota analizi araç seti** ve metrikleri | ETH `lunar_planner` (A1) | Aynı problemi çözen MIT lisanslı kod; metrik setinizi tamamlar | Düşük |
| 2 | **Pürüzlülük + kaya bolluğu kriterleri** | DPPS-STP (D2) | Rekabet paritesi; veri hazır | Düşük |
| 3 | **Replanning tetikleyici taksonomisi** | ESA ADE/ADAM (B6) | i-SAIRAS bildirisi ücretsiz; kurumsal referans | Düşük |
| 4 | **Karo piramidi (tile pyramid) hiyerarşisi** | DPPS-STP (D2), multi-level map (D4) | [08](08_global_local_rotalama_yuku.md)'deki ölçek probleminin kanıtlanmış çözümü | Orta |
| 5 | **Güneş-senkron planlama kavramı** | Sun-Synchronous (D3) | Kutup için doğru zaman modeli | Orta |
| 6 | **Bekleme kenarı + kaynak-kısıtlı formülasyon** | Sensors 24(3) 844 (D4) | Zaman ekseninin somut kurulumu | Orta |
| 7 | **Yerel yay-örnekleme planlayıcı** | Stanford NavLab (A2) | Katman 2'nin referans implementasyonu, açık kod | Orta |
| 8 | **ROS 2 + Gazebo hizalaması** | VIPER yer araçları (B4) | Hedef misyonun fiili standardı | Orta |
| 9 | **MMGIS'e eklenti konumlandırması** | NASA AMMOS (A3) | *Use History* + entegrasyon iddiası | Orta |
| 10 | **Şans kısıtlı / stokastik erişilebilirlik** | Lamarre vd. (D1) | Alanın en ileri formülasyonu; yayın hedefi | Yüksek |

---

## I. Atıf listesi (yayın/rapor yazarken)

LunaPath'in bir rapor veya yayında **mutlaka** referans vermesi gerekenler:

1. Lamarre, Malhotra & Kelly (2024) — arXiv 2401.08558 — *en yakın komşu*
2. Richter vd. (2024) — arXiv 2406.16376 — *açık kaynak muadil*
3. Remote Sensing 17(5), 924 (2025) — *çok faktörlü güvenlik haritası*
4. Remote Sensing 17(9), 1589 (2025) — *güneş-senkron planlama*
5. Remote Sensing 17(11), 1924 (2025) — *alan derlemesi*
6. Sensors 24(3), 844 (2024) — *zaman-değişken kısıtlar + bekleme*
7. arXiv 2404.18721 — *global+local hibrit, saha testi*
8. Paige vd. (2010), Science 330, 479 — *Diviner*
9. Hayne vd. (2017), JGR Planets — *termofiziksel özellikler*
10. Barker vd. (2023), PSJ — *LOLA güney kutbu / PSR*

---

## Kaynaklar (bu belgede kullanılan tüm bağlantılar)

**Açık kaynak depolar**
- [leggedrobotics/lunar_planner](https://github.com/leggedrobotics/lunar_planner)
- [Stanford-NavLab/lunar_autonomy_challenge](https://github.com/Stanford-NavLab/lunar_autonomy_challenge)
- [NASA-AMMOS/MMGIS](https://github.com/NASA-AMMOS/MMGIS)
- [jasmeet0915/artemis_mission_simulator](https://github.com/jasmeet0915/artemis_mission_simulator)
- [rakshanda33/Lunar-Navigation-Path-Planner](https://github.com/rakshanda33/Lunar-Navigation-Path-Planner)
- [alessioborgi/MoonBot-Navigation](https://github.com/alessioborgi/MoonBot-Navigation)
- [knamatame0729/ORBSLAM3-Semantic-Mapping](https://github.com/knamatame0729/ORBSLAM3-Semantic-Mapping)
- [space-ros](https://github.com/space-ros) · [space.ros.org FAQ](https://space.ros.org/pages/faq.html)
- [OmniLRS](https://github.com/OmniLRS/OmniLRS) · [LunarSim](https://github.com/PUTvision/LunarSim)
- [NeoGeographyToolkit/StereoPipeline](https://github.com/NeoGeographyToolkit/StereoPipeline)
- [zqyu9/LuSNAR-dataset](https://github.com/zqyu9/LuSNAR-dataset)
- [AndrejOrsula/awesome-space-robotics](https://github.com/AndrejOrsula/awesome-space-robotics)
- [phayne/heat1d](https://github.com/phayne/heat1d)
- [GitHub topic: lunar-exploration](https://github.com/topics/lunar-exploration)
- [MATLAB Central: lunar-rover-path-planning](https://www.mathworks.com/matlabcentral/fileexchange/128759-lunar-rover-path-planning)

**Kurum araçları**
- [NASA Moon Trek](https://trek.nasa.gov/moon/) · [Moon Trek EGU 2023 (ADS)](https://ui.adsabs.harvard.edu/abs/2023EGUGA..25..969L/abstract)
- [NASA Ames xGDS](https://ti.arc.nasa.gov/tech/asr/groups/intelligent-robotics/xgds/) · [xGDS Overview (NTRS)](https://ntrs.nasa.gov/api/citations/20190025706/downloads/20190025706.pdf) · [Acta Astronautica 90:268](https://www.sciencedirect.com/science/article/pii/S0094576512000057)
- [JPL RSVP for MSL](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-science-laboratory/rsvp-msl/) · [RSVP Mars 2020](https://www-robotics.jpl.nasa.gov/what-we-do/flight-projects/mars-2020-rover/rsvp-mars-2020/)
- [MIT Tech Review: VIPER open-source software](https://www.technologyreview.com/2021/04/12/1022420/nasa-lunar-rover-viper-open-source-software/)
- [Space ROS SciTech (NTRS)](https://ntrs.nasa.gov/api/citations/20220017761/downloads/Space_ROS_SciTech.pdf) · [AIAA 2023-2709](https://arc.aiaa.org/doi/10.2514/6.2023-2709) · [Robot Report: Open Robotics + Blue Origin + NASA](https://www.therobotreport.com/open-robotics-developing-space-ros/)
- [Artemis Geospatial Data Team Capabilities (NTRS)](https://ntrs.nasa.gov/api/citations/20230006633/downloads/Artemis%20Geospatial%20Data%20Team%20Capabilities%20-%20Strives%20(final).pdf)
- [ESA ADE (GMV)](https://h2020-ade.gmv.com/) · [ADE DFKI](https://robotik.dfki-bremen.de/en/research/projects/ade-og10.html) · [ADE i-SAIRAS 2020](https://www.hou.usra.edu/meetings/isairas2020fullpapers/pdf/5033.pdf) · [CORDIS 821988](https://cordis.europa.eu/project/id/821988)
- [Space Applications LUVMI-X](https://www.spaceapplications.com/products/lunar-rover-luvmi-x) · [Yeni rover girişimleri](https://www.spaceapplications.com/news/space-applications-services-expands-lunar-rover-development-with-new-commercial-and-esa-funded-missions)
- [European Moon Rover System (arXiv 2411.13978)](https://arxiv.org/pdf/2411.13978)

**Ticari**
- [NASASpaceflight: Lunar Outpost MAPP](https://www.nasaspaceflight.com/2025/12/lunar-outpost-mapp/) · [MAPP](https://www.lunaroutpost.com/mapp) · [Lunar Voyage 1 Update](https://www.lunaroutpost.com/post/lunar-voyage-1-update) · [Space.com mission control](https://www.space.com/astronomy/moon/we-are-ready-to-drive-take-a-look-inside-lunar-outposts-moon-rover-mission-control-photos) · [Wikipedia: Lunar Outpost](https://en.wikipedia.org/wiki/Lunar_Outpost_(company))
- [CMU RI: MoonRanger NASA review](https://www.ri.cmu.edu/moonranger-passes-key-nasa-review-ahead-of-lunar-mission/) · [Astrobotic MoonRanger production](https://www.astrobotic.com/astrobotics-moonranger-moves-into-final-production/) · [Astrobotic $5.6M](https://www.astrobotic.com/astrobotic-awarded-5-6-million-nasa-contract-to-deliver-autonomous-moon-rover/)
- [Payload Field Guide: Lunar Rovers](https://payloadspace.com/payload-field-guide-lunar-rovers/) · [SpaceNews: lunar ground transportation](https://spacenews.com/companies-race-to-win-ground-transportation-contracts-for-the-moon/)
- [ispace + Toyota](https://ispace-inc.com/news-en/?p=7983) · [Toyota Lunar Cruiser](https://global.toyota/en/mobility/technology/lunarcruiser/index.html) · [ispace Mission 2 status](https://ispace-inc.com/news-en/?p=7664)
- [JPL CADRE](https://www.jpl.nasa.gov/missions/cadre/)

**Akademik**
- [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) · [arXiv 2406.16376](https://arxiv.org/html/2406.16376v1) · [arXiv 2404.18721](https://arxiv.org/html/2404.18721v1) · [arXiv 2603.17232](https://arxiv.org/html/2603.17232v1) · [arXiv 2409.00641](https://arxiv.org/pdf/2409.00641) · [arXiv 2506.16940](https://arxiv.org/pdf/2506.16940) · [arXiv 2603.17229](https://arxiv.org/pdf/2603.17229) · [arXiv 2510.23329](https://arxiv.org/pdf/2510.23329) · [arXiv 2311.03122](https://arxiv.org/pdf/2311.03122)
- [Remote Sensing 17(5), 924](https://www.mdpi.com/2072-4292/17/5/924) · [17(9), 1589](https://www.mdpi.com/2072-4292/17/9/1589) · [17(11), 1924](https://www.mdpi.com/2072-4292/17/11/1924) · [Sensors 24(3), 844](https://www.mdpi.com/1424-8220/24/3/844)
- [SciEngine: Spatiotemporal constraints review](https://www.sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012) · [Chinese J. Aeronautics: multi-level map](https://www.sciencedirect.com/science/article/pii/S1000936124005442) · [PMC7866010](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/)

**Yarışma**
- [Lunar Autonomy Challenge](https://lunar-autonomy-challenge.jhuapl.edu/) · [Dokümantasyon](https://lunar-autonomy-challenge.jhuapl.edu/Challenge-Documentation/index.php) · [NASA STMD seçilen takımlar](https://www.nasa.gov/directorates/stmd/lunar-autonomy-challenge-selected-teams)
