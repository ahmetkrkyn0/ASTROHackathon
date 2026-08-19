# LunaPath — Kaynak Haritası

**Derlenme tarihi:** 12 Ağustos 2026
**Amaç:** Toplanan araştırma kaynaklarını konuya göre gruplamak; hangi başlıkta neye bakılacağını, her kaynağın hangi iş paketine (WP) hizmet ettiğini ve okuma önceliğini netleştirmek.

## Öncelik göstergeleri

| İşaret | Anlam |
|---|---|
| 🔴 | **Önce bunu oku.** Projenin yönünü doğrudan etkiliyor. |
| 🟠 | Önemli, ilgili WP'ye başlamadan önce oku. |
| 🟡 | Referans / gerektiğinde bak. |
| ⚪ | Bağlam, arka plan. Zaman kalırsa. |

**İş paketleri** (bkz. yol haritası): **WP-0** model hijyeni · **WP-1** veri hattı · **WP-2** ufuk & aydınlanma fiziği · **WP-3** ThermalNet · **WP-4** 4B planlayıcı · **WP-5** doğrulama & sunum

---

## ⚠️ ÖNCE OKU: Dört kritik kaynak

Bu dördü diğerlerinden önce gelir. İkisi projenin özgünlük iddiasını doğrudan etkiliyor.

### 1. 🔴 Sun-Synchronous Path Planning (Remote Sensing 2025)

> **"A Spatiotemporal U-Net-Based Data Preprocessing Pipeline for Sun-Synchronous Path Planning in Lunar South Polar Exploration"**
> https://www.mdpi.com/2072-4292/17/9/1589 · [doi:10.3390/rs17091589](https://doi.org/10.3390/rs17091589)

**Bunu neden ilk okumalısın:** Bu makale, bizim **ThermalNet + 4B planlayıcı** olarak tasarladığımız şeye çok yakın. Uzay-zamansal U-Net ile ön işleme + güneş-senkron rota planlama + güney kutbu. Yani:

- **Tehdit:** Özgünlük iddianın bir kısmı zaten literatürde. "Biz ilkiz" diyemezsin.
- **Fırsat:** Yaklaşımın **doğrulanmış** demektir; hakemli bir dergide yayımlanmış. Ayrıca sana bir **baseline ve atıf** veriyor — "X'in yaklaşımını temel aldık, şu noktada farklılaşıyoruz" demek, hiç bilmemekten kat kat güçlü.

**Cevaplaman gereken soru:** Bizim katkımız bunun neresinde duruyor? Muhtemel farklılaşma eksenleri: (a) AYAP-2 / Copernicus ekvator senaryosu — onlar güney kutbu, (b) çok noktalı tur optimizasyonu, (c) rover-spesifik kısıtlar ve çoklu rover profili, (d) BEKLE kenarı.

**Bunu okumadan yol haritası spec'ini kesinleştirme.**

### 2. 🔴 leggedrobotics/lunar_planner — ETH Zürih

> https://github.com/leggedrobotics/lunar_planner · MIT · Python 3.8+
> Atıf: *"Multi-Objective Global Path Planning for Lunar Exploration"*

**LunaPath'in en yakın akrabası.** Çok amaçlı global rota planlama, Ay yüzeyi, GUI + CLI, Linux/macOS/Windows. Örnek haritalar: Aristarchus Irregular Mare Patch, Aristarchus Central Peak, Herodotus Mons (hepsi **ekvatora yakın** — AYAP-2 senaryosuyla aynı rejim).

**Neden kritik:** Jüri "bunun benzeri var mı?" diye sorarsa cevabın hazır olmalı. Ayrıca MIT lisanslı — maliyet formülasyonlarını **karşılaştırma baseline'ı** olarak kullanabilirsin.

**Cevaplaman gereken sorular:** Hangi kriterleri kullanıyor? Aydınlanmayı nasıl ele alıyor (repo açıklamasında belirtilmemiş — koda bakılmalı)? Zaman boyutu var mı? Bizim log-barrier + AHP yaklaşımımızdan farkı ne?

### 3. 🟠 Path-Planning Algoritmaları Kapsamlı Derlemesi (Remote Sensing 2025)

> **"A Comprehensive Review of Path-Planning Algorithms for Planetary Rover Exploration"**
> https://www.mdpi.com/2072-4292/17/11/1924 · 31 Mayıs 2025

Algoritmaları **kısıt-odaklı** perspektiften sınıflandırıyor: graf arama, potansiyel alan, örnekleme tabanlı, dinamik pencere + biyo-esinli yöntemler (evrimsel, bulanık, ML). Arazi değişkenliği, engeller, **aydınlanma koşulları ve sıcaklık dalgalanmaları** açıkça ele alınıyor.

**Ne için:** Literatürde kendini konumlandırmanın en hızlı yolu. Raporun "İlgili Çalışmalar" bölümünü bundan çıkarabilirsin. Ayrıca A\*'ın neden hâlâ savunulabilir bir seçim olduğunu buradan gerekçelendirirsin.

### 4. 🟠 ESA ADE (OG10) — Very Long Traverses

> https://h2020-ade.gmv.com/ · https://www.dfki.de/en/web/research/projects-and-publications/project/ade-og10

H2020 PERASPERA kümesi. ERGO (OG2) otonomi çerçevesi üzerine kurulu. Hedef: **6 saatte 1 km**'yi aşan otonom traverse; **ADAM** (Autonomous Decision Making Module) fırsatçı bilim veya tehlike tespitinde nominal planı otonom değiştiriyor.

**Neden önemli:** Bizim "rota planla, bitti" modelimizin ötesi. Gerçek bir misyonda plan **yeniden planlanır**. AYAP-2'de 2 günlük traverse penceresi ve sıfır marj olduğu düşünülürse, yeniden planlama yeteneği doğrudan alakalı. Ayrıca Avrupa'nın referans mimarisi — sunumda "endüstri standardı yaklaşım şu, biz şurada duruyoruz" demek için.

---

## A. Rota Planlama — Çok Kriterli ve Kısıt Tabanlı

**Bu başlıkta konuşacağımız:** Maliyet fonksiyonu tasarımı, kısıtların formülasyonu, algoritma seçimi, optimallik garantileri.
**Hizmet ettiği:** WP-4 (planlayıcı), WP-5 (baseline karşılaştırma)

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| A1 | [leggedrobotics/lunar_planner](https://github.com/leggedrobotics/lunar_planner) | 🔴 | En yakın akraba. Maliyet kriterleri, aydınlanma ele alışı, baseline |
| A2 | [Sun-Synchronous Path Planning (RS 2025)](https://www.mdpi.com/2072-4292/17/9/1589) | 🔴 | Uzay-zamansal U-Net + güneş-senkron planlama. Özgünlük konumlandırması |
| A3 | [Path-Planning Derlemesi (RS 2025)](https://www.mdpi.com/2072-4292/17/11/1924) | 🟠 | Literatür haritası, kısıt taksonomisi |
| A4 | [Distributed Safety-Map Path Planning (RS 2025)](https://www.mdpi.com/2072-4292/17/5/924) | 🟠 | Güvenlik haritası kavramı — geçilebilirlik katmanımızı zenginleştirebilir |
| A5 | [Lamarre, Malhotra & Kelly (2024) — Şans kısıtlı PSR keşfi](https://arxiv.org/abs/2401.08558) | 🟠 | **Belirsizlik altında planlama.** Bizim modelimiz deterministik; şans kısıtı (chance constraint) doğal bir sonraki adım |
| A6 | ~~Kısıtlar (ZRHT / 载人航天)~~ | ⚠️ | **Link kırık (404):** `sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012`. DOI'yi doğrulaman gerek |

> **A5 üzerine not:** Şans kısıtlı planlama, "bu rotanın başarı olasılığı %95" demeyi sağlar. AYAP-2'nin sıfır zaman marjı düşünülürse bu çok güçlü bir çerçeve — ama 1 ayda uygulanamaz. **Faz 2 olarak sun.**

---

## B. Aydınlanma, Gölge ve Termal Modelleme

**Bu başlıkta konuşacağımız:** Ufuk açısı hesabı, güneş efemerisi, yüzey sıcaklığı fiziği, zaman boyutunun kaynağı.
**Hizmet ettiği:** WP-1 (veri), WP-2 (fizik), WP-3 (ThermalNet)

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| B1 | [MIT Imbrium — Aydınlanma verisi](https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION/) | 🔴 | Hazır aydınlanma ürünleri. **İndirip ne olduğunu görmek WP-2'nin ilk işi** |
| B2 | [phayne/heat1d](https://github.com/phayne/heat1d) | 🔴 | **1B termal model** (Paul Hayne — Diviner ekibinden). Regolit termal atalet, altyüzey iletim. `thermal_grid.py`'nin yerine geçecek fiziğin referansı |
| B3 | **Ufuk (horizon) hesabı** — yöntem | 🟠 | Her pikselden N azimutta maksimum ufuk yüksekliği. Mazarico yöntemi (720 görüş hattı, 0.5° aralık) |
| B4 | **SpiceyPy — neden kritik** | 🟠 | Güneş konumu (azimut/yükseklik) zamanın fonksiyonu olarak. Zaman boyutunun temeli |
| B5 | [Sun-Synchronous (RS 2025)](https://www.mdpi.com/2072-4292/17/9/1589) | 🔴 | *(A2 ile aynı — hem planlama hem termal başlığına giriyor)* |

> **B2 özellikle değerli:** `heat1d` Paul Hayne'in (Diviner bilim ekibi) 1B termal difüzyon modeli. Bizim "uydurma termal grid" problemimizin doğrudan çözümü. Açık kaynak, Python. **WP-2/WP-3'ün fizik temeli bu olmalı.**
>
> **B3 + B4 birlikte:** Ufuk açısı haritası (topografyadan, bir kez hesaplanır) + güneş konumu (SPICE'tan, zamanın fonksiyonu) → `I(x, y, t)` aydınlanma alanı. Bu ikisi olmadan zaman boyutu yok.

---

## C. Öğrenme Tabanlı Planlama ve Geçilebilirlik

**Bu başlıkta konuşacağımız:** Sinir ağının projede nereye oturacağı, hangi mimari, eğitim verisi nereden, doğrulama nasıl.
**Hizmet ettiği:** WP-3 (ThermalNet), WP-4

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| C1 | [Learning-Based End-to-End Path Planning with Safety Constraints (Sensors 2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC7866010/) | 🟠 | **DRL (PPO) + gerçek DEM + tekerlek kayması + müfredat öğrenmesi.** A\* ile karşılaştırma yapıyor — bizim baseline mantığımızın aynısı |
| C2 | [Deep Probabilistic Traversability with Test-time Adaptation (2024)](https://arxiv.org/abs/2409.00641) | 🟠 | Kayma (slip) dağılımını gözlemden öğrenip **belirsizliği planlamaya sokuyor.** "Belirsizliği kısıt değil rehber olarak kullan" fikri güçlü |
| C3 | [Risk-Aware Coverage Path Planning, Global + Local (2024)](https://arxiv.org/abs/2404.18721) | 🟠 | *(D başlığıyla ortak)* Global veriyi lokal topografik özniteliklerle **hareket maliyetinde birleştiriyor** — bizim iki katmanlı mimarimizin tam karşılığı |

> **Dikkat — C1'in dersi:** Uçtan uca DRL cazip görünür ama 1 ayda eğitilemez ve jüride "neden bu rotayı seçti?" sorusuna cevap veremezsin. **Bizim seçtiğimiz yol (fizik modeli + hızlı sinir ağı vekili) hem açıklanabilir hem eğitilebilir.** C1'i, *neden DRL seçmediğimizi* gerekçelendirmek için oku.

---

## D. İki Katmanlı Mimari — Global + Lokal

**Bu başlıkta konuşacağımız:** 80 m global planlayıcı ile metre-altı lokal algı planlayıcısının nasıl bağlanacağı. (AYAP-2 analizinde tespit edilen çözünürlük uçurumunun cevabı.)
**Hizmet ettiği:** Mimari kararlar, "Faz 2" anlatısı

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| D1 | [Risk-Aware Coverage Path Planning (2024)](https://arxiv.org/abs/2404.18721) | 🟠 | Santra, Uno, Kudo, Yoshida (Tohoku). Mikro-rover, kısıtlı algı/hesap. **Global + lokal maliyet birleştirme** |
| D2 | [ESA ADE (OG10)](https://h2020-ade.gmv.com/) | 🟠 | Yeniden planlama mimarisi, ADAM karar modülü |
| D3 | [CISRU (ASTRA 2023)](https://arxiv.org/abs/2311.03122) | 🟡 | Platformdan bağımsız robotik yazılım paketi. ERGO/ADE mirası. **Yazılım mimarisi** için referans |

---

## E. Algı — Aydınlanma Dayanıklılığı, SLAM, Konumlandırma

**Bu başlıkta konuşacağımız:** Kameradan engel tespiti, aşırı aydınlanma değişimi altında görüş, konum kayması (drift).
**Hizmet ettiği:** **Faz 2** (1 aylık kapsamın dışı — ama sunumda "sonraki adım" olarak anlatılacak)

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| E1 | [Stanford-NavLab/lunar_autonomy_challenge](https://github.com/Stanford-NavLab/lunar_autonomy_challenge) | 🟠 | **SuperPoint + LightGlue** — aşırı aydınlanma değişimine dayanıklı öğrenilmiş öznitelik eşleme. Ay'da neden klasik SIFT/ORB çalışmadığının cevabı |
| E2 | [LunarLoc: Segment-Based Global Localization (2025)](https://arxiv.org/abs/2506.16940) | 🟡 | Kaya (boulder) landmark'larının zero-shot segmentasyonu → graf tabanlı eşleme. **Santimetre-altı** çoklu oturum konumlandırma |
| E3 | [Visual SLAM with DEM Anchoring (2026)](https://arxiv.org/abs/2603.17229) | 🟡 | DEM'den türetilen yükseklik ve yüzey-normali kısıtlarını poz grafiğine sokarak **drift azaltma**. Unreal + Etna analog verisi |

> ⚠️ **Listende `arxiv.org/pdf/2603.17229` iki kez var** — bir kez "no drift", bir kez "hger bok var" etiketiyle. Aynı makale (E3).

> **E1 neden bizim için önemli:** Ay'da gölgeler keskin, ara ton yok, güneş açısı alçak. Klasik öznitelik eşleme çöker. Stanford'un bu seçimi, "aydınlanma sadece enerji problemi değil, **algı problemi**" tezini destekliyor — bu, sunumda aydınlanma vurgunu güçlendiren güzel bir bağlantı.

---

## F. Simülasyon, Dijital İkiz ve Veri Setleri

**Bu başlıkta konuşacağımız:** 3D görselleştirme, sentetik veri üretimi, eğitim verisi kaynakları.
**Hizmet ettiği:** WP-5 (3D görselleştirme), Faz 2 (algı eğitim verisi)

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| F1 | [jasmeet0915/artemis_mission_simulator](https://github.com/jasmeet0915/artemis_mission_simulator) | 🟡 | ROS2 Ay dijital ikiz simülasyonu |
| F2 | [POLAR-Sim (2023/2025)](https://arxiv.org/abs/2309.12397) | 🟡 | NASA POLAR veri seti + **13 senaryonun dijital ikizi**. Kamera/güneş konumu, pozlama, aktif aydınlatma ayarlanabilir. 23.000 etiket (kaya, gölge, krater) |
| F3 | [LuSNAR-dataset](https://github.com/zqyu9/LuSNAR-dataset) | 🟡 | 108 GB, 9 sahne. Stereo (1024², 10 Hz), derinlik, 5 sınıf semantik etiket, 128-ışın LiDAR, IMU + ground truth. MIT (akademik) |

> **F2 + F3, Faz 2'nin eğitim verisi problemi çözülmüş demek.** AYAP-2 analizinde "1 ayda etiketli veri bulamazsın" demiştim — bu iki kaynak o değerlendirmeyi yumuşatıyor. Yine de 1 aya sığmaz, ama "Faz 2'de veri hazır, şunu kullanacağız" demek planı somutlaştırır.

---

## G. Uçmuş Misyonlar ve Referans Sistemler

**Bu başlıkta konuşacağımız:** Gerçekte ne yapıldı, hangi parametreler doğrulandı, rover profillerimizi neye göre kalibre ediyoruz.
**Hizmet ettiği:** WP-0 (rover kayıt sistemi), WP-5 (doğrulama, gerçeklik kontrolü)

| # | Kaynak | Öncelik | Ne için bakacağız |
|---|---|---|---|
| G1 | **Yutu-2** (uçmuş, Chang'e-4) | 🟠 | **Gerçek traverse verisi.** Ay'ın uzak yüzünde 5+ yıl. Gerçek hız, gerçek günlük mesafe, gerçek operasyon kısıtları. `constants.py`'de zaten profili var — **doğrulanmalı** |
| G2 | **Pragyan** (uçmuş, Chandrayaan-3) | 🟠 | Güney kutbuna yakın (69.4°G), 2023. Kısa ömür (1 ay günü), termal sınırlı. AYAP-2'ye benzer profil |
| G3 | [VIPER açık kaynak yazılımı (MIT Tech Review)](https://www.technologyreview.com/2021/04/12/1022420/nasa-lunar-rover-viper-open-source-software/) | 🟡 | NASA'nın rover yazılımını açması. Kutup misyonu operasyon mantığı |
| G4 | [European Moon Rover System — saha testi (2024)](https://arxiv.org/abs/2411.13978) | 🟡 | EMRS prototipi analog saha testi. **Traverse performansı, tekerlek sapması, ulaşım maliyeti** ölçümleri — modüler tasarım. Enerji modelimizi gerçek ölçümle kıyaslamak için |

> **G1 ve G2 en yüksek değerli olanlar** çünkü **gerçekten uçtular.** Sunumda "modelimiz Yutu-2'nin bilinen günlük ilerleme hızını şu hatayla yeniden üretiyor" diyebilmek, herhangi bir simülasyon karşılaştırmasından güçlü. Bu, WP-5'te aradığımız *harici doğrulama*.

---

## H. Tehlike Tespiti ve Engelden Kaçınma

**Bu başlıkta konuşacağımız:** HazCam, kaya/krater tespiti, lokal kaçınma.
**Hizmet ettiği:** **Faz 2** — 1 aylık kapsamın dışında, bilinçli olarak

Bu başlık şu an **boş bir konu etiketi**; altına kaynak toplanmamış. İlgili malzeme başka başlıklarda duruyor:

- Eğitim verisi → **F2 (POLAR-Sim)**, **F3 (LuSNAR)** — kaya/gölge/krater etiketli
- Aydınlanma dayanıklı algı → **E1 (SuperPoint+LightGlue)**
- Güvenlik haritası formülasyonu → **A4 (Distributed Safety-Map)**
- Belirsizlik altında geçilebilirlik → **C2 (Deep Probabilistic Traversability)**

**Karar:** Bu başlık için yeni kaynak toplamayın. AYAP-2 analizinde gerekçelendirildiği gibi, tehlike tespiti **ölçek uyumsuzluğunun** cevabıdır (80 m global planlama vs 0.5–2 m tehlike ölçeği) ve Faz 2'dir. Yukarıdaki dört kaynak, Faz 2 planını somut anlatmaya yeter.

---

## Özet: Hangi başlık hangi WP'ye hizmet ediyor

| WP | Ana başlık | Kritik kaynaklar |
|---|---|---|
| **WP-0** Model hijyeni | G (referans sistemler) | G1 Yutu-2, G2 Pragyan, G4 EMRS |
| **WP-1** Veri hattı | B (aydınlanma/termal) | B1 MIT Imbrium |
| **WP-2** Ufuk & aydınlanma | B | B1, B2 heat1d, B3 ufuk, B4 SpiceyPy |
| **WP-3** ThermalNet | B + C | **A2/B5 Sun-Synchronous** ⚠️, B2 heat1d, C2 |
| **WP-4** 4B planlayıcı | A + D | A1 lunar_planner, A3 derleme, A4, D2 ADE |
| **WP-5** Doğrulama & sunum | A + G + F | A3 derleme, G1/G2 gerçek misyonlar, F1 3D |
| **Faz 2** (sunulacak, yapılmayacak) | E + H + F | E1, E2, E3, F2, F3 |

---

## Önerilen okuma sırası (1 aylık takvime göre)

**Bu hafta — yol haritası kesinleşmeden önce (zorunlu):**
1. 🔴 A2 Sun-Synchronous Path Planning → *özgünlük konumlandırması*
2. 🔴 A1 leggedrobotics/lunar_planner → *en yakın akraba, farkımız ne*

**Hafta 1 — WP-1/WP-2 başlarken:**
3. 🔴 B1 MIT Imbrium aydınlanma → *indir, ne olduğunu gör*
4. 🔴 B2 heat1d → *termal fiziğin temeli*
5. 🟠 B3 + B4 ufuk hesabı + SpiceyPy → *uygulama*

**Hafta 2 — WP-3/WP-4:**
6. 🟠 A3 derleme → *rapor "İlgili Çalışmalar" bölümü buradan*
7. 🟠 A4, A5, C2 → *maliyet ve belirsizlik formülasyonları*
8. 🟠 D1, D2 → *global+lokal mimari, yeniden planlama*

**Hafta 3 — WP-5 doğrulama:**
9. 🟠 G1 Yutu-2, G2 Pragyan → *harici gerçeklik kontrolü*
10. 🟡 G4 EMRS → *enerji modeli kıyası*

**Hafta 4 — sunum hazırlığı, Faz 2 anlatısı:**
11. 🟡 E1, E2, E3, F2, F3 → *"sonraki adım" slaytı için yüzeysel okuma yeterli*

---

## Düzeltilecek notlar

| Konu | Durum |
|---|---|
| `arxiv.org/pdf/2603.17229` listede **iki kez** ("no drift" ve "hger bok var") | Aynı makale = **E3** Visual SLAM with DEM Anchoring |
| `sciengine.com/ZRHT/doi/10.3724/zrht.1674-5825.2026012` | **404 — link kırık.** DOI doğrulanmalı (载人航天 / Manned Spaceflight dergisi) |
| `mdpi.com/2072-4292/17/11/1924` etiketsizdi | = **A3** Path-Planning Algoritmaları Kapsamlı Derlemesi |
| `arxiv.org/pdf/2411.13978` "europe Rover" | = **G4** European Moon Rover System saha testi |
| "Hazard detection" / "Obstacle avoidance" başlıkları | Kaynak toplanmamış — **§H'de gerekçesiyle kapatıldı**, Faz 2 |
| "2.1 SpiceyPy" / "2.2 Ufuk hesabı" | Bunlar bir doküman taslağının bölüm numaraları gibi görünüyor → **B3/B4** olarak yerleştirildi |
