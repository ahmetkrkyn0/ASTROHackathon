# AYAP-2 Türk Ay Rover'ı — Doküman Analizi ve LunaPath Stratejisi

**Analiz tarihi:** 12 Ağustos 2026
**Kaynak dokümanlar:** `docs/rover_project/AIAC-2023-082.pdf`, `docs/rover_project/IAC-24A3IP180x82320.pdf`
**Amaç:** İki konferans bildirisinin kapsamlı analizi, AYAP-2 misyonunun gereksinimlerinin çıkarılması, dokümanlardaki boşluk ve tutarsızlıkların tespiti, LunaPath projesinin bu misyonla ilişkilendirilmesi.

---

## 0. Yönetici Özeti

İncelenen iki bildiri, **AYAP-2** (Ay Araştırma Programı Faz 2 — yumuşak iniş + rover) için TÜBİTAK UZAY bursiyerleri ve UKET üyeleri tarafından yapılmış **kavramsal rover tasarımını** anlatıyor. Misyon henüz gerçekleştirilmedi; "önümüzdeki on yıl içinde" planlanıyor.

**Üç kritik bulgu:**

**1. Coğrafi uyumsuzluk total.** AYAP-2 iniş bölgesi **Copernicus Krateri güneydoğusu, ~7.7°K** — ekvatora yakın, gündüz operasyonu, aşırı **sıcaklık** problemi. LunaPath'in tamamı **güney kutbu** üzerine kurulu — PSR, kalıcı gölge, **donma** problemi. Termal problem tam anlamıyla ters yönde. Mevcut veri hattı (LDEM_80S, LOLA kutup ürünleri, PSR maskeleri) Copernicus'a **hiç ulaşmıyor**.

**2. Ölçek uyumsuzluğu daha da büyük.** AYAP-2 traversi **0.5 km yarıçaplı bir daire**. LunaPath grid'i **80 m/piksel**. Tüm görev alanı LunaPath'te **~12×12 piksel** eder. Mevcut çözünürlük bu misyon için kullanılamaz.

**3. Ve tam da bu yüzden büyük bir fırsat var: bildirilerde rota planlama algoritması YOK.** Üç örnekleme noktası tanımlanmış, "sırayla git" denmiş, o kadar. Traverse optimizasyonu yok, arazi analizi yok, enerji-per-traverse modeli yok, termal yönlendirme yok. Termal yönetim tamamen **donanım** problemi olarak ele alınmış (MLI, ısı borusu, Peltier) — bir **operasyon/rotalama** problemi olarak değil. LunaPath'in yapmak için var olduğu şey, bu misyonda eksik olan şeydir.

**Stratejik sonuç:** LunaPath'i "güney kutbu rota planlayıcısı"ndan **"misyon-bağımsız Ay yüzeyi traverse planlama altyapısı"na** dönüştürüp AYAP-2'yi ikinci ve *birincil vitrin* senaryosu yapmak. Ulusal finalde "ürünleşme" sorusunun cevabı budur: yayınlanmış, gerçek, milli bir misyon tasarımının eksik katmanını dolduruyorsunuz.

> **Yayın durumu notu:** Her iki bildiri de **açık literatürde yayımlanmış** durumda. AIAC-2023-082 ODTÜ AIAC sitesinde ([aiac.ae.metu.edu.tr](http://aiac.ae.metu.edu.tr/paper.php?No=AIAC-2023-082)), her ikisi de ResearchGate'te mevcut. Yani bunları sunumda **açıkça atıf vererek kullanabilirsiniz** — bu bir kısıt değil, avantaj. Gerçekleşmemiş olan şey *misyonun kendisi*, dokümanların gizliliği değil.

---

## 1. Doküman Künyesi

| | **Bildiri 1** | **Bildiri 2** |
|---|---|---|
| **Kod** | AIAC-2023-082 | IAC–24–A3.IP.180 |
| **Başlık** | Conceptual Rover Design for **Future** Turkish Lunar Mission | Conceptual Rover Design for Turkish Lunar Mission |
| **Konferans** | 12. Ankara International Aerospace Conference, 13–15 Eylül 2023 | 75. International Astronautical Congress, Milano, 14–18 Ekim 2024 |
| **Sayfa** | 26 | 14 |
| **Yazarlar** | Boybaşı, Kösoğlu, Altuntaş, Köşker, Yağlıoğlu | Altuntaş, **Baygeldi**, Boybaşı, **Demir**, Kösoğlu, Köşker, Yağlıoğlu |
| **Kurumlar** | Koç Ü., İTÜ, TÜBİTAK UZAY | İTÜ, ODTÜ, Koç Ü., TÜBİTAK UZAY |

**Kurumsal bağlam:** Yazarlar TÜBİTAK UZAY **AYAP-1 bursiyerleri** ve **UKET** (Uzay Keşif Topluluğu) üyeleri. UKET, Türkiye'nin ilk ve tek uluslararası rover yarışması olan **Anatolian Rover Challenge**'ın ana organizatörü. Sorumlu yazar konumundaki Burak Yağlıoğlu TÜBİTAK UZAY Başuzman Araştırmacısı.

**Bu sizin için ne anlama geliyor:** Bu ekip, sizin yarıştığınız ekosistemin merkezinde. Anatolian Rover Challenge organizatörleri ve TÜBİTAK UZAY. Ulusal final jürisinde bu isimlerden biri veya onların çevresinden biri olma ihtimali düşük değil.

---

## 2. AYAP-2 Misyonu — Kapsamlı Türkçe Özet

### 2.1 Program bağlamı

Türkiye Millî Uzay Programı, Türkiye Uzay Ajansı (TUA) tarafından **Şubat 2020**'de açıklandı. Ana sütunlarından biri **Ay Araştırma Programı**, iki fazlı:

- **AYAP-1** — Ay yörünge operasyonları, hibrit itki sistemi, yüzeye **sert iniş**
- **AYAP-2** — **yumuşak iniş** ile yüzeye bir **rover** indirmek

TÜBİTAK UZAY, ilk Türk Ay misyonunun tasarım, geliştirme ve gerçekleştirilmesinden sorumlu. Türkiye'nin belirtilen hedefleri: uzay teknolojisi yetkinliğini artırmak, yerli sistemler için derin uzay mirası biriktirmek, uluslararası iş birliğini teşvik etmek, toplumsal farkındalık oluşturmak.

### 2.2 İniş bölgesi: Copernicus Krateri

**Kraterin kendisi:** Ay'ın **yakın yüzünde**, Oceanus Procellarum'un güneydoğusunda, **9.62°K / 20.08°B**, çapı yaklaşık **93 km**. Copernicus dönemi çarpma kraterlerinin en önemlilerinden; iyi korunmuş yapısı, ışın sistemi, merkezi tepeleri ve tabakalanması Ay'ın jeolojik zaman ölçeğini anlamak için kritik.

**Neden bu bölge:** Copernicus, **PKT** (Procellarum KREEP Terrane) içinde. KREEP = **K**alsiyum/Potasyum, **R**are **E**arth **E**lements (Nadir Toprak Elementleri), **P**hosphorus. Bölge FeO (%17.3), toryum, uranyum, olivin, plajiyoklaz ve piroksen açısından zengin.

**Seçilen nokta:** Kraterin **güneydoğu duvarındaki düz alan**. Gerekçe hem yumuşak iniş uygunluğu hem de element bolluğu — özellikle **toryum 8.15 ppm** ve **uranyum 2.1 ppm**.

> **Dikkat:** Krater *içindeki* element konsantrasyonu krater *dışından daha düşük*. Bildiri bunu çarpma sonrası erozyon, yüzey ve derin katman malzemelerinin karışması ve saçılmasıyla açıklıyor. Bu yüzden iniş noktası kraterin **dış/güneydoğu duvarında**, içinde değil.

### 2.3 Misyon profili

| Parametre | Değer |
|---|---|
| **Süre** | Yarım ay günü = **10–12 Dünya günü**, yalnızca **gündüz** |
| **İniş noktası** | 7.746°K, 19.240°B *(IAC-2024)* |
| **Operasyon alanı** | **0.5 km yarıçaplı** daire |
| **Örnekleme noktası** | 3 adet, önceden belirlenmiş |
| **Rota** | İniş → S1 → S2 → S3 → **lander'a geri dönüş** |
| **Numune toplama süresi** | ~2 gün |
| **Biyomadencilik deneyi** | 8–10 gün |
| **Hız** | **0.12 m/s** |
| **Engel aşma** | **20 cm** |

**Örnekleme noktaları (IAC-2024):**
- S1: 7.739°K, 19.247°B
- S2: 7.755°K, 19.240°B
- S3: 7.739°K, 19.231°B

**Lander'a dönüş gerekçesi:** Karmaşık numune işleme, ek güç, büyük hacimli veri aktarımı için lander kaynaklarının kullanılması. Ayrıca rover'da bir arıza olması hâlinde (örneğin bilimsel deneyler için gereken gücün karşılanamaması) lander yedek kaynak sağlıyor.

### 2.4 Bilimsel misyon: Uzayda biyomadencilik

**Ana hedef:** Ay yüzeyinde **uranyum ve toryumu biyomadencilikle** çıkarmak.
**İkincil hedef:** FeO, Th, U, olivin, piroksen, plajiyoklaz tespiti ve konsantrasyon analizi; krater duvarının radyasyon ortamının haritalanması.

**Özgünlük iddiası:** Daha önce hiçbir rover üzerinde uzay biyomadencilik deneyi yapılmadı. Referans alınan çalışma ESA'nın **BioRock** deneyi (ISS'te, Ay ve Mars analoğu bazalttan nadir toprak elementi biyoliçi).

**Organizma seçimi — iki bildiri arasında değişti:**

| | AIAC-2023 | IAC-2024 |
|---|---|---|
| Organizma | **Bakteri:** *Acidithiobacillus ferrooxidans* + *Pseudomonas aeruginosa* | **Mantar:** *Aspergillus niger* |
| Hedef element | FeO, Th, U | U, Th |

*A. niger* gerekçesi: spor oluşturup metabolik olarak inaktif kalabilme, bakterilerden **daha hızlı liç**, ağır metal direnci, metallerle kompleks yapan sekonder metabolit üretimi (sitrik asit, oksalik asit). Literatürde uranyum geri kazanım oranları: %71.4, %69, %80, %75.5, %71.41. Mezofilik — **25–35°C** çalışma aralığı.

**Deney akışı:** Sporlar kuru/dormant hâlde gönderilir → iniş sonrası azot bileşiğiyle dormansi kırılır → numune toplanırken misel gelişir → kaya numunesi biyoreaktör odasına verilir → 8–10 gün liç → UV-VIS ile OD600 takibi + **lüminesan MOF (JXNU-4)** ile çıkarılan U(VI)/Th iyonlarının tespiti.

**Kontrol tasarımı:** Aynı düzenek Dünya (1g), ISS (mikroyerçekimi) ve Ay (0.17g) için üçlü tekrarla kurulacak; biyolojik olmayan kontroller metal çözünmesinin gerçekten mantar kaynaklı olduğunu doğrulayacak.

### 2.5 Yükler ve enstrümanlar

| Enstrüman | Amaç | Durum |
|---|---|---|
| **Dozimetre** | İyonlaştırıcı radyasyon karakterizasyonu | Her iki bildiride |
| **Biyoreaktör** | Minyatür, 3 odacıklı (kültür ortamı + spor + numune) | Her iki bildiride |
| **UV-VIS spektrofotometre** | OD600 ile mikroorganizma büyümesi | Her iki bildiride |
| **XRF spektrometre** | Element/mineral tespiti (EDXRF) | **AIAC-2023'te var, IAC-2024'te YOK** |
| **Lüminesan MOF (JXNU-4)** | U(VI)/Th iyon tespiti, floresan sönümleme | **Sadece IAC-2024** |

**Kameralar:** Panoramik (ön, geniş açı), Mikroskobik görüntüleyici (alt/yan, yakın çekim), Stereo navigasyon kameraları (ön + arka, 3B harita), HazCam (tehlike tespiti), Bilimsel kameralar.

**Kamera gereksinimleri:** Toz ve radyasyon koruması, enerji verimliliği, veri sıkıştırma ve güvenilir iletim, **yedeklilik**.

### 2.6 Alt sistemler

Ürün ağacı **altı alt sistem**e ayrılmış:

**① Navigasyon ve Mobilite**
- **IMU** — ivme/dönüş, kısa vadeli hassas navigasyon; zamanla **drift** sorunu
- **Star tracker** — mutlak konumlandırma; görüş kısıtlarında sorun
- **Arazi haritalama kameraları** — 3B harita, engel tespiti; **görsel odometri** (aydınlanma değişimi ve yüzey doku farklılıklarından etkilenir)
- Üçünün **sensör füzyonu** ile bireysel zayıflıkların telafi edilmesi öngörülüyor

**② Mobilite / Tekerlek tasarımı**
- **Rocker-bogie** süspansiyon, **6 tekerlek**, her birinde bağımsız **fırçasız DC motor**
- **Skid steering** (Lunokhod tarzı) — tekerlek hızlarını değiştirerek dönüş
- Tekerlek çapı **0.14 m**, genişlik **0.08 m**
- Rocker-bogie tekerlek çapının 1.5 katı engel aşabildiğinden, 20 cm engel için minimum çap 0.133 m
- **Drawbar pull analizi** (Bekker-Wong terramekaniği):
  - Maksimum batma (sinkage) `z = 21.7 mm`
  - Zemin itki kuvveti `H = 40.1 N`
  - Yuvarlanma direnci `Rr = 2.43 N`
  - Zemin sıkıştırma direnci `Rc = 0.0993 N`
  - Yerçekimi direnci `Rg = 4.65 N`
  - **Net çekiş `DP = 33.22 N`**
  - Parametreler: `kc = 1400 N/m²`, `kφ = 8200 N/m²`, `n = 0.8`, `c = 170 N/m²`, `θ = 30°`, Ay'da ağırlık `Ww = 48.6 N`
- Malzeme: alüminyum (~2.125 kg) veya titanyum (~12 kg); karbon fiber jant

**③ Veri İşleme ve Haberleşme**
- Zincir: **Rover → Lander → Yer İstasyonu**
- Lander ara istasyon görevi görüyor (Ay–Dünya mesafesi nedeniyle)
- Veri önceliklendirme ve sıkıştırma; kritik bilimsel veri önce
- Haberleşme seçenekleri değerlendirilmiş: radyo (güvenilir, düşük hız), lazer (yüksek hız, görüş hattı gerekli), uydu (sürekli ama gecikmeli)

**④ Güç Yönetimi**
- **Güneş paneli** — birincil kaynak
- **Şarj edilemeyen (non-rechargeable) yedek batarya**
- RTG değerlendirilmiş ancak **reddedilmiş** (Pu-238 / Am-241; geliştirme süreci çok uzun)
- Güç bütçesi:

| Alt sistem | Tam Mod | Bilimsel Mod | Boşta |
|---|---|---|---|
| Navigasyon ve Mobilite | 12 | 0 | 0 |
| Termal Sistem | 2 | 2 | 2 |
| Güç Yönetimi | 4 | 4 | 4 |
| Haberleşme | 5 | 5 | 2 |
| İşleme | 5 | 5 | 2 |
| Görüntüleme | 9 | 9 | 4 |
| Navigasyon Sistemi | 8 | 0 | 0 |
| Bilim Modülü | 2 | 2 | 0 |
| **TOPLAM** | **47 W** | **27 W** | **14 W** |

- Güneş ışınımı (yakın yüz ortalama): **1356 W/m²**
- Panel verimi %20, alan 0.24 m² → **çıkış 65 W ± %4**
- Güç tasarrufu stratejileri: uyku modu, dinamik güç dağıtımı, seçici sensör aktivasyonu, optimize haberleşme protokolü

**⑤ Termal Yönetim**
- Ay yüzeyinde gündüz-gece farkı **~250°C**
- 45° enlemde: gün doğumundan 0.5 gün sonra **−87.9°C**, öğle vakti **+81.5°C**
- Copernicus 7.7°K'da olduğundan, düşük eksen eğikliği nedeniyle **benzer veya daha yüksek** sıcaklıklar bekleniyor
- Misyon yarım ay günü sürdüğü için termal tasarım **soğuk değil, SICAK ortama** odaklı
- **Şasi hedef aralığı: −5°C ile +45°C** (şarjdaki batarya limiti belirleyici)
- Ekipman limitleri (CubeSat referansı):

| Ekipman | Min | Max |
|---|---|---|
| Motor | −40 | 100 |
| Motor Kontrolcü | −20 | 70 |
| Kameralar | −40 | 85 |
| CPU | −20 | 125 |
| IMU | −40 | 100 |
| Batarya (deşarj) | −20 | 60 |
| Radyo | −40 | 85 |
| Güç Dağıtım Ünitesi | −40 | 85 |
| Ethernet Switch | −40 | 60 |

- Yöntemler: kompozit malzeme entegrasyonu (karbon-karbon), ısı emici / ısı borusu / radyatör, **Peltier** (çift yönlü ısıtma-soğutma), **RHU** (radyoizotop ısıtıcı), **MLI** (çok katmanlı yalıtım)
- **Dış etkenler olarak sayılanlar:** güneş radyasyonu, yüzey albedosu, kızılötesi radyasyon, uzaya ısı kaybı
- **İç etkenler:** termal iletim, sistem içi ısı yayılımı

**⑥ Yapı ve Mekanizmalar**
- Boyut: **65 × 45 × 30 cm** (üst yüzey tamamen güneş paneliyle kaplı)
- Kütle: **~30 kg** (hedef: sonraki iterasyonlarda mikro-rover sınıfına inmek)
- Malzeme: **6061 / 7075 alüminyum alaşım** ana çerçeve ve süspansiyon; **CFRP** ağırlık azaltımı için (jantlar)
- **Numune toplama:** esnek tüp karotlama (flexible tube coring) prensibi, **30 cm derinlik**, perküsif mekanizma ile desteklenmiş
  - Avantaj: az serbestlik derecesi, kavrayıcı kola göre kompakt, rover altında olduğu için radyasyondan korunaklı
  - Dezavantaj: iç içe tüpler arası sürtünme/sürükleme kuvveti, öngörülemeyen zemin dokusu, delme sırasında ısı üretimi

### 2.7 Gereksinimler (IAC-2024, ECSS uyumlu)

**İşlevsel:** Biyomadencilikle element analizi · Radyasyon ölçümü · ~0.12 m/s hız, 20 cm engel aşma · Lander üzerinden Dünya ile haberleşme · Güneş paneli + batarya ile güçlendirme

**Misyon:** Copernicus Krateri'ne konuşlanma · 500 m çaplı dairesel rota · 3 önceden belirlenmiş noktada durup numune alma · 10 gün içinde son konuma dönüş · Sonda bio-rock deneyi

**Çevresel:** Minimum 82°C sıcaklıkta çalışma *(bkz. §4 — muhtemel hata)* · Bilimsel bileşenler için −5°C…+45°C · Engebeli araziye ve titreşime dayanım

**Fiziksel:** ≤30 kg · 25×45×65 cm hacim · Güneş paneli güç çıkışını optimize edecek sabit açıda

**Konfigürasyon:** Rocker-bogie · Delme mekanizması · 6 tekerlek · 1 yedek batarya · 6 fırçasız motor · Anten

---

## 3. İki Bildiri Arasındaki Değişiklikler (2023 → 2024)

Bu tablo tasarımın hangi kısımlarının **hâlâ akışkan** olduğunu gösteriyor — yani sizin katkı yapabileceğiniz alanları.

| Konu | AIAC-2023 | IAC-2024 | Yorum |
|---|---|---|---|
| **İniş koordinatı** | 8.314°K, 340.566°D | **7.746°K, 19.240°B** | ~17 km kaymış. Bölge seçimi rafine edilmiş. |
| **Örnekleme noktaları** | Lander'dan **2.35 km**'ye kadar | Hepsi **0.34 km içinde** | 2023'ün geometrisi kendi 0.5 km yarıçap iddiasını **4.7 kat** aşıyordu; 2024 düzeltmiş. |
| **Organizma** | 2 bakteri türü | **1 mantar türü** (*A. niger*) | Ciddi bilimsel revizyon. |
| **Hedef element** | FeO, Th, U | **U, Th** (FeO düşmüş) | Kapsam daralmış. |
| **Toryum konsantrasyonu** | 5 ppm (bölgesel) | **8.15 ppm** (nokta) | Rafine edilmiş. |
| **XRF spektrometre** | Var | **Yok** | Gerekçesiz kaldırılmış. Kütle/güç baskısı olabilir. |
| **MOF sensör** | Yok | **Var (JXNU-4)** | XRF'in yerini almış görünüyor. |
| **Direksiyon** | Belirtilmemiş | **Skid steering** | Netleşmiş. |
| **Yapı malzemesi** | "alüminyum alaşımlar" | **6061 / 7075** | Netleşmiş. |
| **Gereksinim formatı** | Yok | **ECSS uyumlu, 5 kategori** | Sistem mühendisliği olgunlaşmış. |
| **Sensör envanteri** | Yok | **Tablo 1 — 25+ enstrüman, misyon referanslı** | Önemli ek. |
| **Güç bütçesi birimi** | W | **Wh** *(hatalı — bkz. §4)* | Regresyon. |

---

## 4. Dokümanlardaki Boşluklar, Tutarsızlıklar ve Hatalar

Bu bölüm sizin en değerli kozunuz. Bir konferans bildirisinin sınırlarını eleştirmek değil amaç — **kavramsal tasarım (Faz 0/A) doğası gereği bu boşlukları bırakır.** Ama boşlukları tespit edip doldurmak, tam olarak bir sonraki fazın işidir ve sizin katkı alanınızdır.

### 4.1 En büyük boşluk: Rota planlama diye bir şey yok

Her iki bildiride de:
- **Hiçbir yol planlama algoritması yok.** Üç nokta veriliyor, "sırayla git" deniyor.
- **Traverse optimizasyonu yok.** Sıralamanın (S1→S2→S3) neden bu sıra olduğu gerekçelendirilmemiş.
- **Arazi analizi yok.** "Nispeten düz" ve "eğim gibi fiziksel özellikler" deniyor ama **hiçbir DEM analizi, eğim haritası, geçilebilirlik haritası sunulmuyor.**
- **Enerji-per-traverse modeli yok.** Güç bütçesi mod bazlı (47/27/14 W) ama belirli bir arazide belirli bir mesafeyi katetmenin enerji maliyeti modellenmemiş.
- **Zaman çizelgesi optimizasyonu yok.** Misyon zaman çizelgesi sabit bir Gantt (Gün 0,1,2,3,4,10,12,14). Ne zaman hareket, ne zaman bilim, ne zaman şarj sorusu optimize edilmemiş.
- **Engelden kaçınma algoritması yok.** HazCam var, "engel tespiti" deniyor, ama tespit sonrası ne yapılacağı tanımsız.

> Drawbar pull hesabı **θ = 30° eğim** için yapılmış, ama rover'ın gerçekten hangi eğimlere maruz kalacağı hiç analiz edilmemiş. 33.22 N net çekişin hangi arazi profilinde yeteceği belirsiz.

### 4.2 Termal, bir operasyon problemi olarak hiç ele alınmamış

Termal yönetim tamamen **donanım** çözümleriyle sınırlı: MLI, ısı borusu, Peltier, RHU, kompozit malzeme.

Bildirinin kendi ifadesiyle (AIAC-2023, Termal Yönetim):
> *"...ileri çalışmalarda, termal modelleme yapılırken bu koşullar dikkate alınmalıdır. Dış çevre etkileşimleri için güneş radyasyonu, yüzey albedosu, kızılötesi radyasyon ve uzaya radyasyon ile iç etkileşimler için termal iletim ve iç ısı yayılımı göz önünde bulundurularak **belirli misyon senaryoları çalışılmalıdır**."*

**Bu cümle açıkça gelecek çalışma olarak bırakılmış — ve tam olarak LunaPath'in yaptığı şey.** Rotayı termal yüke göre seçmek, gölgeli bölgelerden geçmek, sıcak saatlerde beklemek: bunların hiçbiri düşünülmemiş.

### 4.3 Yedek batarya fiziksel olarak mümkün görünmüyor

Bildirilerin kendi hesabı:

> `Toplam Gerekli Güç = 40 W/h × 24 h/d × 12 d = 12.520 W`

**Üç sorun var:**

1. **Aritmetik:** 40 × 24 × 12 = **11.520**, 12.520 değil.
2. **Birim:** Sonuç **Wh** (enerji), W (güç) değil. Ayrıca "40 W/h" ifadesi de hatalı; 40 W olmalı.
3. **Fizibilite — en kritiği:** 11.520 Wh = **11.5 kWh** şarj edilemeyen yedek batarya. En iyi uzay-kalifiye Li-ion hücrelerde ~150–250 Wh/kg alırsak bu **46–77 kg** eder. Rover'ın **toplam kütle bütçesi 30 kg**.

**Yani yedek batarya konsepti, tanımlandığı hâliyle kütle bütçesini tek başına 1.5–2.5 katına çıkarıyor.** Bu, kavramsal tasarımda yakalanmamış birinci dereceden bir fizibilite sorunu.

> **Bu sizin en güçlü argümanınız olabilir:** Enerji marjını daraltan bir operasyon planlayıcısı, imkânsız bir bataryaya olan ihtiyacı ortadan kaldırır. LunaPath'in değer önerisi tam olarak budur — donanımı büyütmek yerine operasyonu optimize etmek.

### 4.4 Güç üretimi hesabı kendi geometrisiyle çelişiyor

- Belirtilen panel boyutu: **65 × 45 cm = 0.2925 m²**
- Hesapta kullanılan alan: **40 × 60 cm = 0.24 m²**

0.2925 m² ile: `0.2 × 1356 × 0.2925 = 79.3 W` — 65 W değil. Hesap muhafazakâr yönde hatalı, ama **belgelenen geometriyle tutarsız.**

Ayrıca 1356 W/m² **ortalama** ışınım; gerçek üretim **güneş yükseklik açısına** bağlı ve panel "sabit açıda" olduğu için gün boyunca ciddi değişir. 10–12 günlük misyonda güneş yüksekliği 0°'dan ~82°'ye çıkıp geri iner. **Bu değişim hiç modellenmemiş** — sabit 65 W varsayılmış.

### 4.5 Diğer tutarsızlıklar ve muhtemel hatalar

| # | Bulgu | Nerede |
|---|---|---|
| 1 | **"Minimum 82°C sıcaklıkta çalışma"** — neredeyse kesinlikle *maksimum* olmalı (öğle vakti +81.5°C verisiyle uyumlu). Bir rover'ın minimum 82°C'de çalışması anlamsız. | IAC-2024 §2.3 |
| 2 | **"500 m çaplı" vs "0.5 km yarıçaplı"** — aynı bildiride, gereksinim ile trajektori bölümü arasında **2 kat** fark. Koordinatlar hakemlik ediyor: örnekleme noktaları lander'dan 0.27/0.27/0.34 km uzakta, yani **0.5 km yarıçap doğru, "500 m çap" gereksinimi hatalı** (S3 onu ihlal ederdi). | IAC-2024 §2.2 vs §3.3 |
| 3 | **Hacim sırası tutarsız:** 65×45×30 (Yapı) vs 25×45×65 (Gereksinimler). Üçüncü boyut 30 mu 25 mi? | IAC-2024 §2.4 vs §10 |
| 4 | **Güç bütçesi birimi Wh olarak etiketlenmiş**, ama tablo güç (W) bütçesi. AIAC-2023'te doğru (W), IAC-2024'te bozulmuş. | IAC-2024 Tablo 2 |
| 5 | **XRF gerekçesiz kaldırılmış.** AIAC-2023'te element doğrulamasının temeliydi; IAC-2024'te yok, yerine MOF gelmiş ama geçiş tartışılmamış. | Karşılaştırma |
| 6 | **Termal ve bilimsel gereksinim çakışması:** şasi −5…+45°C, ama *A. niger* **25–35°C** istiyor ve dış ortam **+81.5°C**'ye çıkıyor. Bu üçlünün nasıl aynı anda sağlanacağı gösterilmemiş. | IAC-2024 §12 |
| 7 | **İniş noktası kraterin dışında.** Merkez 9.62°K/20.08°B, iniş 7.746°K/19.240°B → aradaki büyük daire mesafesi **~62 km** (Δlat 56.8 km, Δlon 25.2 km). Krater yarıçapı ~46.5 km. Yani iniş noktası krater kenarının **~16 km dışında**. Metinde "güneydoğu duvarı" deniyor — "duvar" ile "duvar dışındaki ejekta örtüsü" ayrımı netleştirilmemiş. Bilimsel gerekçe açısından bu aslında **tutarlı** (§2.2: element bolluğu krater dışında daha yüksek), ama terminoloji yanıltıcı. | §3.1 vs §3.3 |
| 8 | **Star tracker gündüz operasyonunda.** Misyon tamamen gündüz; Ay'da atmosfer olmadığı için yıldızlar teknik olarak görünür ama güneş parlaması ve düşük güneş açısında star tracker performansı ciddi sorun. Tartışılmamış. | §8.1 |

---

## 5. LunaPath ↔ AYAP-2 Uyum Matrisi

| LunaPath bileşeni | AYAP-2 ile uyum | Ne yapılmalı |
|---|---|---|
| **A\* çok kriterli planlayıcı** | ✅ **Doğrudan transfer** | Değişiklik gerekmiyor |
| **Maliyet motoru mimarisi** (ağırlıklı penaltılar) | ✅ **Doğrudan transfer** | Ağırlıklar yeniden kalibre edilmeli |
| **`f_thermal` çift-sigmoid** (hem alt hem üst limit) | ✅ **Zaten iki yönlü** — sıcak taraf hazır | `thermal_offset_hot` kalibrasyonu |
| **Rover kayıt sistemi** (`constants.py`) | ✅ **Hazır altyapı** | **AYAP-2 profili eklenecek** — en ucuz ve en etkili adım |
| **Eğim / geçilebilirlik hesabı** | ✅ Transfer eder | Çözünürlük değişecek |
| **Simülasyon motoru** | 🟡 Kısmen | Batarya modeli baştan yazılmalı |
| **Güney kutbu DEM hattı** (LDEM_80S) | ❌ **Kullanılamaz** | SLDEM2015 + NAC DTM'e geçiş |
| **80 m/piksel çözünürlük** | ❌ **Kullanılamaz** (1 km görev alanı = 12 px) | ~2–5 m/px gerekli |
| **PSR / kalıcı gölge mantığı** | ❌ **Anlamsız** (7.7°K'da PSR yok) | Yerine güneş yükseklik açısı modeli |
| **Gölge = soğuk varsayımı** | ❌ **Ters** | Gölge burada **iyi bir şey** — soğutma sağlıyor |
| **Isıtıcı enerji tüketimi** (`p_heater_w`) | ❌ **Ters problem** | Yerine **radyatör/soğutma** yükü |
| **Batarya oto-şarj** (mevcut hata) | ❌ Zaten hatalı | Güneş yükseklik açısına bağlı gerçek şarj modeli |

### 5.1 Fizik önceliklerinin tersine dönmesi

**Bu, analizin en önemli teknik çıktısı.** AYAP-2'nin kendi sayılarından türetildi:

**Sürüş enerjisi bağlayıcı kısıt DEĞİL.**
IAC-2024 koordinatlarından hesaplanan kuş uçuşu tur uzunluğu (İniş→S1→S2→S3→İniş): 0.299 + 0.529 + 0.555 + 0.343 = **1.73 km**. Arazi sapmalarıyla ~2–2.5 km. 0.12 m/s hızda **~4–6 saat sürüş**. Tam modda 47 W ile: **~190–280 Wh**. Buna karşılık 12 günlük boşta yük tek başına 14 W × 288 h = **4.032 Wh**. Yani **sürüş, toplam enerji bütçesinin ~%5'i.**

**Bağlayıcı kısıtlar şunlar:**

1. **Termal.** Dış ortam +81.5°C, şasi −5…+45°C, biyoreaktör 25–35°C. Üç iç içe kısıt, dar bant.
2. **Zaman.** Misyon 10–12 gün. Deney 8–10 gün. Traverse için **yalnızca ~2 gün** var. **Sıfır marj.** Traverse'de yaşanacak her gecikme, doğrudan deney süresinden yiyor.

**Sonuç:** AYAP-2 için maliyet fonksiyonu güney kutbundakinin tersine dönmeli:

| Ağırlık | Güney kutbu (mevcut) | AYAP-2 (önerilen) | Gerekçe |
|---|---|---|---|
| `w_energy` | 0.259 | **↓ ~0.10** | Sürüş enerjisi bütçenin %5'i |
| `w_thermal` | 0.190 | **↑ ~0.40** | Birincil bağlayıcı kısıt |
| `w_slope` | 0.409 | ~0.35 | Devrilme ve çekiş hâlâ önemli |
| `w_shadow` | 0.142 | **anlam değişiyor** | Gölge artık **ödül**, ceza değil |
| **`w_time`** | yok | **YENİ ~0.15** | 2 günlük traverse penceresi |

> Gölge teriminin işaretinin ters çevrilmesi (`f_shadow` → `f_cooling_benefit`) tek satırlık bir değişiklik ama kavramsal olarak çok güçlü bir gösterim: *"Aynı planlayıcı, aynı kod, iki misyon — ve fizik kendini tersine çeviriyor."*

### 5.2 Yeni yetenek gereksinimi: Çok noktalı tur optimizasyonu

AYAP-2 rotası **kapalı bir tur**: İniş → S1 → S2 → S3 → İniş.

LunaPath şu anda yalnızca **nokta-nokta** planlama yapıyor. Bu misyon, arazi maliyetli bir **Gezgin Satıcı Problemi** (4 düğüm — kaba kuvvetle bile anlık çözülür).

**Referans (baseline) hesabı — IAC-2024 koordinatlarından, kuş uçuşu:**

| Bacak | Mesafe |
|---|---|
| İniş → S1 | 0.299 km |
| S1 → S2 | 0.529 km |
| S2 → S3 | 0.555 km |
| S3 → İniş | 0.343 km |
| **Bildirideki sıra toplamı** | **1.726 km** |

Alternatif sıralama İniş→S1→S3→S2→İniş: 0.299 + (S1→S3 = 0.485) + 0.555 + (S2→İniş = 0.273) = **1.612 km** → düz mesafede bile **%6.6 kısa.**

**Neden değerli:** Bildiriler sıralamayı **S1→S2→S3 olarak sabitlemiş, gerekçe vermemiş.** Düz mesafede bile daha iyi bir sıra var; **arazi maliyeti ve termal yük eklendiğinde fark büyür.** Bunu sayısal olarak gösterebilirseniz, gerçek bir misyon tasarımına somut ve ölçülebilir bir katkı yapmış olursunuz. Uygulaması ucuz (4 nokta = simetri sonrası 3 permütasyon), etkisi büyük.

> ⚠️ Yukarıdaki rakamlar **küresel kuş uçuşu**; LunaPath'in üreteceği gerçek sayı arazi-maliyetli rota uzunluğu olacak. Baseline'ı bu tabloyla kıyaslayıp farkı raporlayın.

---

## 6. Copernicus için Veri Kaynakları

Güney kutbu için topladığımız kaynakların **hiçbiri 7.7°K'ya ulaşmıyor.** LOLA kutup ürünleri 60°–90° arası, Diviner PCP 10° enlem kepi. Copernicus için tamamen farklı ürünler gerekiyor.

### 6.1 Topografya

| Ürün | Çözünürlük | Kapsam | Erişim |
|---|---|---|---|
| **SLDEM2015** (LOLA + Kaguya TC birleşik) | **512 ppd ≈ 59 m/px**, dikey doğruluk ~3–4 m | ±60° | [pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/](http://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/) · [MIT browse](https://imbrium.mit.edu/BROWSE/SLDEM2015/) · [USGS Astropedia](https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m) |
| **LROC NAC DTM** | **~2–5 m/px** | Nokta bazlı stereo çiftler | [LROC RDR portal](https://wms.lroc.asu.edu/lroc/) |
| SLDEM2015 türev eğim/azimut | 59 m/px | ±60° | [Slope](https://imbrium.mit.edu/BROWSE/SLDEM2015_SLOPE/) · [Azimuth](https://imbrium.mit.edu/BROWSE/SLDEM2015_AZIMUTH/) |

**Copernicus bölgesinde mevcut NAC DTM'ler** (doğrulandı):
- `NAC_DTM_COPERNGRAB` — Copernicus Graben
- `NAC_DTM_COPRNEJCT` / `NAC_DTM_COPRNEJCT01` — Copernicus güneyindeki eriyik akıntısı
- `NAC_DTM_COPERNSEC01` — Copernicus kuzeydoğusundaki ikincil kraterler

> ⚠️ **Bu DTM'lerin hiçbiri tam olarak iniş noktasını (7.746°K, 19.240°B) kapsamıyor.** Hepsi kraterin farklı kenarlarında. İki seçenek: (a) mevcut NAC DTM'lerden birini "temsilî AYAP-2 benzeri arazi" olarak kullanıp bunu dürüstçe belirtmek, (b) iniş bölgesine denk gelen bir NAC **stereo çifti** bulup DTM üretmek (ISIS + ASP gerekir — 1 aya sığmaz).
>
> **Öneri: (a).** Sunumda "AYAP-2 iniş bölgesine coğrafi ve morfolojik olarak en yakın mevcut yüksek çözünürlüklü DTM" diye çerçeveleyin. Dürüst, savunulabilir, ve gerçek NAC verisi kullanmış olursunuz.

### 6.2 Termal

| Ürün | Çözünürlük | Kapsam | Not |
|---|---|---|---|
| **Diviner GDR Level 3** | **32 ppd ≈ 950 m/px** | ±60°, basit silindirik | **Yerel saate göre 1 saatlik dilimlerde** bolometrik sıcaklık haritaları |
| Diviner Global High-Res Mosaics (GHRM) | daha yüksek | global | [ODE GHRM](https://ode.rsl.wustl.edu/) |
| Diviner türev ürünler | — | — | [urn-nasa-pds-lro_diviner_derived1](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/) |

**Kritik gerçek:** Diviner global termal **950 m/piksel**. AYAP-2 görev alanı **1 km çapında**. Yani **tüm görev alanı ≈ 1 piksel.**

**Bu, termal modelleme yaklaşımını belirliyor:**

> Kutup senaryosunda "Diviner'ı 240 m'den 80 m'ye indir" makul bir süper çözünürlük problemiydi. Copernicus'ta **950 m → 2 m** gerekiyor; bu **475 kat** ve saf veri-güdümlü bir yaklaşımla savunulamaz.
>
> **Doğru yaklaşım:** Yüksek çözünürlüklü DEM'den (eğim, bakı, ufuk) + yerel güneş saatinden **fiziksel radyatif denge modeli** kurmak; Diviner'ı 950 m ölçeğinde **doğrulama referansı** olarak kullanmak (modelin 950 m'ye agrege edilmiş hâli Diviner ile uyuşmalı). **Sinir ağı ise bu fizik modelinin hızlı vekili (surrogate) olur** — 4B planlama sırasında her (hücre, zaman) için radyatif denge çözmek imkânsız olduğu için.
>
> Bu, sinir ağını **daha da zorunlu** hâle getiriyor ve doğrulama hikâyesi daha temiz: *"Fizik modelimiz Diviner ile 950 m'de %X uyuşuyor; sinir ağı vekilimiz fizik modelini 2 m'de %Y hatayla, 1000 kat hızlı yeniden üretiyor."*

**Ekvator bölgesinin avantajı:** 7.7°K'da güneş geometrisi çok daha basit. Kutuptaki ufuk-tabanlı ışın izleme kâbusu yok; güneş yüksek açıya çıkıyor, gölgeler yalnızca yerel topografyadan (krater duvarı, kaya) kaynaklanıyor. **Copernicus, kutuptan veri işleme açısından daha kolay.**

### 6.3 Arama arayüzleri

- **ODE (Orbital Data Explorer):** https://ode.rsl.wustl.edu/moon/ — harita üzerinden bölge seçip indirme
- **LROC RDR portalı:** https://wms.lroc.asu.edu/lroc/
- **PDS Geosciences LRO:** https://pds-geosciences.wustl.edu/missions/lro/

---

## 7. Stratejik Öneri

### 7.1 Ana karar: LunaPath'i misyon-bağımsız hâle getirin

Güney kutbu çalışmasını **atmayın**. Onun yerine LunaPath'i şu şekilde yeniden çerçeveleyin:

> **LunaPath — Ay yüzeyi çok kriterli traverse planlama altyapısı.**
> İki referans senaryo ile doğrulanmış:
> **(A) Güney Kutbu** — VIPER sınıfı, gölge/donma baskın
> **(B) Copernicus / AYAP-2** — Türk Ay Rover'ı, sıcaklık/zaman baskın

**Neden bu doğru çerçeve:**
- Mevcut 4 aylık emeği korur
- "Ürünleşme" sorusuna kesin cevap verir: bu bir araç, tek bir demo değil
- **Aynı kod tabanının iki zıt fizik rejiminde çalıştığını göstermek**, tek bir senaryoda çalıştığını göstermekten kat kat güçlü bir mühendislik iddiasıdır
- Millî bir misyona doğrudan bağlanır

### 7.2 En ucuz, en etkili ilk adım

[`backend/app/constants.py`](../../backend/app/constants.py) içindeki `ROVERS` sözlüğüne **AYAP-2 profilini ekleyin.** Altyapı zaten hazır; bu birkaç saatlik iş.

Bildirilerden doğrudan çıkan değerler:

```python
"ayap_2": {
    "name": "AYAP-2 (Türk Ay Rover'ı)",
    "mass_kg": 30,                    # IAC-2024 §2.4
    "v_max_ms": 0.12,                 # IAC-2024 §2.1
    "p_base_w": 12,                   # Navigasyon+Mobilite, Tablo 2
    "e_cap_wh": None,                 # ⚠️ Bildiride tutarsız — bkz. §4.3
    "p_idle_w": 14,                   # Boşta mod toplamı
    "p_solar_w": 65,                  # IAC-2024 §11.2
    "slope_max_deg": ...,             # ⚠️ Bildiride YOK — türetilmeli
    "wheel_diameter_m": 0.14,
    "obstacle_clearance_m": 0.20,
    "bat_op_min_c": -5,               # Şasi alt limit
    "bat_op_max_c": 45,               # Şasi üst limit
    "bio_op_min_c": 25,               # A. niger
    "bio_op_max_c": 35,
    # ...
}
```

**Bu alıştırmanın kendisi bir çıktı üretiyor:** Bildirilerde **eksik olan parametreleri** ortaya çıkarıyor. `slope_max_deg` hiçbir yerde verilmemiş — drawbar pull hesabı 30° için yapılmış ama bu bir *limit* olarak tanımlanmamış. Devrilme limiti (lateral eğim) hiç yok. **Bunları rocker-bogie geometrisi ve kütle merkezinden türetip bildiriye eksik parametre olarak sunmak, tek başına savunulabilir bir katkı.**

### 7.3 Yapılabilecekler — önceliklendirilmiş

**🟢 Yüksek değer / düşük maliyet — mutlaka yapın**

1. **AYAP-2 rover profili** — birkaç saat. Yukarıda.
2. **Eksik parametre türetimi** — `slope_max_deg`, lateral devrilme limiti, gerçekçi batarya boyutu. Bildirilerin bıraktığı boşlukları doldurur.
3. **Batarya fizibilite analizi (§4.3)** — 11.5 kWh vs 30 kg. Tek bir slayt, çok güçlü etki.
4. **Çok noktalı tur optimizasyonu** — 4 düğüm, kaba kuvvet. Sıralamanın önemli olduğunu gösterin.
5. **NAC DTM üzerinde geçilebilirlik haritası** — bildirilerde hiç yok olan arazi analizi.

**🟡 Orta değer / orta maliyet — zaman varsa**

6. **Copernicus termal fizik modeli** — radyatif denge, Diviner ile 950 m'de doğrulanmış
7. **Termal-farkında rotalama** — gölge arayan, sıcak saatte bekleyen rota
8. **Güneş yükseklik açısına bağlı güç modeli** — sabit 65 W varsayımının yerine
9. **ThermalNet surrogate** — fizik modelinin hızlı vekili

**🔴 Yüksek maliyet — 1 aya sığmaz, "Faz 2" olarak sunun**

10. İniş bölgesi için NAC stereo çiftinden özgün DTM üretimi (ISIS + Ames Stereo Pipeline)
11. HazCam görüntülerinden engel segmentasyonu
12. Donanım-in-the-loop testi

### 7.4 Sunum çerçevesi

Ulusal finalde anlatı şu olmalı:

> *"Bölgesel yarışmada güney kutbu için çok kriterli bir rota planlayıcısı geliştirdik. Sonra Türkiye'nin kendi Ay rover tasarımının yayımlanmış dokümanlarını inceledik ve şunu gördük: **AYAP-2'de rota planlama katmanı yok.** Üç nokta belirlenmiş, 'sırayla git' denmiş. Termal yönetim tamamen donanım problemi olarak ele alınmış; bildirinin kendisi 'misyon senaryoları ileride çalışılmalıdır' diyor.*
>
> *Biz o katmanı yaptık. Ve yaparken bildiride yakalanmamış üç şey bulduk: yedek batarya kütle bütçesini tek başına aşıyor, güç üretimi hesabı kendi panel geometrisiyle çelişiyor, ve traverse için ayrılan 2 günlük pencerede sıfır marj var.*
>
> *LunaPath aynı kod tabanıyla iki zıt fizik rejiminde çalışıyor: güney kutbunda gölge cezadır, Copernicus'ta ödüldür. Bu bir demo değil, bir araç."*

Bu anlatı üç şeyi aynı anda yapıyor: teknik derinlik, millî uzay programına doğrudan katkı, ve özgünlük. Sizin hedeflediğiniz üçü.

---

## 8. Revize Yol Haritası Üzerindeki Etkisi

Daha önce kararlaştırılan **Yaklaşım A** (fizik zinciri) geçerliliğini koruyor, ancak hedef değişiyor:

| WP | Önceki (Güney Kutbu) | Revize (AYAP-2 odaklı) |
|---|---|---|
| **WP-0** Model hijyeni | Değişmedi | **Değişmedi** — hâlâ bağımsız ve kritik |
| **WP-1** Veri hattı | Diviner PCP + LOLA kutup | **SLDEM2015 + NAC DTM + Diviner GDR L3** |
| **WP-2** Ufuk/aydınlanma | 720 ışın hattı ufuk hesabı | **Basitleşiyor** — ekvatorda standart güneş geometrisi |
| **WP-3** ThermalNet | 240 m → 80 m süper çözünürlük | **Fizik modelinin hızlı vekili** (daha savunulabilir) |
| **WP-4** 4B planlayıcı | Zaman-genişletilmiş A* | **+ çok noktalı tur** (yeni, ucuz, yüksek etki) |
| **WP-5** Doğrulama | Monte Carlo baseline | **+ AYAP-2 sıralama karşılaştırması** |

**Kritik kapılar aynı kalıyor.** Kapı 1'in içeriği değişiyor: "Diviner PCP indi mi?" yerine **"NAC DTM indi ve iniş bölgesine oturdu mu?"**

---

## 9. Riskler ve Açık Sorular

| # | Risk / Soru | Etki | Azaltma |
|---|---|---|---|
| 1 | İniş noktasını kapsayan NAC DTM yok | Yüksek | Temsilî DTM kullan, dürüstçe belirt (§6.1) |
| 2 | 1 ayda iki senaryoyu birden bitirememe | Yüksek | AYAP-2'yi öncelikle, kutbu "doğrulanmış birinci senaryo" olarak sun |
| 3 | Bildirilerdeki eksik parametreler (slope limiti vb.) | Orta | Türetip **varsayım olarak açıkça etiketle** — bu bir katkıdır, zayıflık değil |
| 4 | Copernicus koordinat belirsizliği (§4.5 #7) | Orta | Her iki bildirinin koordinatını da analiz et, farkı raporla |
| 5 | Jürinin "bu bildiriyi kullanmaya hakkınız var mı?" sorusu | Düşük | Her ikisi de **açık literatürde yayımlanmış**; standart akademik atıf yeterli |
| 6 | AYAP-2 tasarımının bu bildirilerden sonra değişmiş olması | Düşük–Orta | "2024 itibarıyla yayımlanmış tasarıma göre" diye tarihlendirin |

**Cevaplanması gereken açık sorular:**
- `slope_max_deg` ve lateral devrilme limiti bildirilerde yok — rocker-bogie geometrisi ve 30 kg kütleden türetilebilir mi?
- Yedek batarya gerçekte ne kadar? Bildirideki 11.5 kWh imkânsız; gerçekçi bir "kritik yük yedeği" ne olmalı?
- Traverse penceresi gerçekten 2 gün mü? Deney 8–10 gün + traverse 2 gün = 10–12 gün, sıfır marj. Bu kabul edilebilir mi?
- Panel "sabit açıda" — hangi açı? Güç üretimi profilini bu belirliyor.

---

## 10. Kaynakça

**Analiz edilen dokümanlar**
- Boybaşı, B., Kösoğlu, B.T., Altuntaş, N., Köşker, Ö., Yağlıoğlu, B. (2023). *Conceptual Rover Design for Future Turkish Lunar Mission.* AIAC-2023-082, 12th Ankara International Aerospace Conference. — [aiac.ae.metu.edu.tr](http://aiac.ae.metu.edu.tr/paper.php?No=AIAC-2023-082)
- Altuntaş, N., Baygeldi, G., Boybaşı, B., Demir, F.Y., Kösoğlu, B.T., Köşker, Ö., Yağlıoğlu, B. (2024). *Conceptual Rover Design for Turkish Lunar Mission.* IAC–24–A3.IP.180, 75th International Astronautical Congress, Milano.

**Bildirilerin atıf verdiği program dokümanları**
- Baygeldi, A., Bayram, İ., Pehlivan, B., Ayvacıklı, B. (2023). *Moon Research Program of Türkiye.* IEEE RAST 2023.
- Yağlıoğlu, B., İnaltekin, B.B., Gökten, M. (2023). *The First Turkish Lunar Mission Part 1: Programmatic, Mission and System Aspects.* IEEE RAST 2023.

**Veri kaynakları**
- SLDEM2015 — [PDS](http://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/) · [MIT](https://imbrium.mit.edu/BROWSE/SLDEM2015/) · [USGS](https://astrogeology.usgs.gov/search/map/moon_lro_lola_selene_kaguya_tc_dem_merge_60n60s_59m)
- LROC NAC DTM — [wms.lroc.asu.edu](https://wms.lroc.asu.edu/lroc/)
- Diviner GDR L3 — [ODE](https://ode.rsl.wustl.edu/moon/pagehelp/quickstartguide/diviner_gdr_l3.htm)
- Diviner türev ürünler — [PDS Geosciences](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/)
- ODE arama arayüzü — [ode.rsl.wustl.edu/moon](https://ode.rsl.wustl.edu/moon/)

**Bilimsel referanslar (bildirilerden)**
- Cockell, C.S. ve ark. (2020). *Space station biomining experiment demonstrates rare earth element extraction in microgravity and Mars gravity.* Nature Communications 11, 5523.
- Gumulya, Y., Zea, L., Kaksonen, A. (2022). *In situ resource utilisation: The potential for space biomining.* Minerals Engineering 176, 107288.
- Yamashita, N. ve ark. (2010). *Uranium on the Moon: Global distribution and U/Th ratio.* GRL.
- Kaczmarzyk ve ark. (2018). Ay yüzeyi güneş ışınımı değerleri.
- Oikawa ve ark. (2016). Ay yüzeyi sıcaklık profilleri.

---

*Bu analiz, `docs/rover_project/` altındaki iki konferans bildirisinin tam metin okumasına ve bağımsız veri kaynağı doğrulamasına dayanmaktadır. Bildirilerdeki sayısal değerler doğrudan alıntılanmış; hesaplama hataları ve tutarsızlıklar §4'te işaretlenmiştir. Türetilen öneriler ve fizibilite değerlendirmeleri bu analizin kendi katkısıdır ve bildirilerin yazarlarına atfedilemez.*
