# LunaPath — Frontend / Görselleştirme / Simülasyon Ortamı Özellikleri Araştırması
*FEZA Ekibi (Çankaya Üniversitesi) · TUA Astro Hackathon Ulusal Final, 7–13 Eylül 2026 · Belge tarihi: 13 Ağustos 2026*
 
## TL;DR (Üç Madde)
- **En yüksek getirili üç iş nettir:** (1) SPICE/SpiceyPy ile gerçek zamanlı güneş konumu + radyatif denge termal modeli (F2), (2) zaman kaydırağı (temporal scrubbing), (3) AHP duyarlılık kaydırağı. Bu üçü **gerçek fiziğe dayanır**, 25 günde yapılır ve LunaPath'in en büyük eksiği olan "zaman ekseni yok" sorununu tek hamlede çözer.
- **Ekibin 5 fikrinin kararı:** F2 (gerçek yapılabilir, çok yüksek demo), F3-Cesium/three.js DEM (gerçek yapılabilir), F5-kenar bazlı risk (gerçek yapılabilir), F1-göksel yön (kısmen gerçek: güneş+eğimölçer hesabı gerçek, yıldız izleyici mock), F4-operatör kontrolü (kısmen gerçek: arayüz gerçek, uçuş-yazılımı-in-the-loop yapılamaz).
- **Mock kaçınılmaz ama meşru:** Yıldız izleyici, birinci-şahıs kamera, olasılıksal chance-constrained çözüm ve ML tehlike tespiti 25 günde gerçek yapılamaz. NASA-STD-7009B ruhuna uygun olarak bunları "notional/simulated" etiketiyle sunmak güvenilirlik kaybı değil, olgunluk göstergesidir — etiketlenmemiş mock ise güvenilirlik kaybettirir.
---
 
## Bölüm 0 — Bu belge nasıl okunmalı + kapsamın ne OLMADIĞI
 
Bu rapor bir akademik tarama değil, **mühendislik karar belgesidir**. Her özellik için dört soru cevaplanır: (i) gerçek görevlerde durumu, (ii) literatür/yöntem, (iii) boşluk, (iv) 25 gün / 5 kişi / 24 Ağustos özellik dondurma kısıtında yapılabilirlik. Kaynak bulunamayan iddialar için açıkça **"kaynakta bulunamadı"** yazılmıştır. Hiçbir araç, sayı veya makale uydurulmamıştır.
 
**Kapsamın NE OLMADIĞI:** Rover donanım tasarımı, uçuş yazılımı geliştirme, gerçek görev sertifikasyonu, algoritmaların matematiksel ispatı kapsam dışıdır. Özellik dondurma 24 Ağustos olduğundan pratikte ~11 günlük aktif geliştirme + entegrasyon/test penceresi vardır; "yapılabilir" tablosu buna göre kurgulanmıştır.
 
---
 
## Bölüm 1 — Yönetici Özeti: Ekibin 5 Fikri İçin Karar Tablosu
 
| # | Fikir | Karar | Gerçeklik payı | Demo gücü |
|---|-------|-------|----------------|-----------|
| **F1** | Yıldız/güneş/Dünya'dan konum ve yön bulma | **Kısmen gerçek** (güneş+eğimölçer yön hesabı gerçek; yıldız izleyici mock) | Orta | Yüksek |
| **F2** | Gerçek zamanlı güneş konumu → termal sıcaklık | **Gerçek yapılabilir** (efemeris + radyatif denge gerçek; termal atalet basitleştirilmiş) | Yüksek | Çok yüksek |
| **F3** | Yüksek çözünürlüklü DEM'in Cesium ile görselleştirilmesi | **Gerçek yapılabilir** | Yüksek | Çok yüksek |
| **F4** | Operatör kontrolü / paylaşımlı otonomi | **Kısmen gerçek** (arayüz gerçek; uçuş yazılımı simülasyonu mock) | Orta | Yüksek |
| **F5** | Her durum geçişi için risk skoru | **Gerçek yapılabilir** (ağırlıklı indeks gerçek; olasılıksal/chance-constrained mock) | Orta-Yüksek | Yüksek |
 
---
 
## Bölüm 2 — Ekibin 5 Fikri (Detaylı)
 
### F1. Yıldızlardan / Gök Cisimlerinden Konum ve Yön Bulma
 
**(a) Gerçek görevlerde durumu.** Ay ve Mars rover'larında mutlak yön (heading) belirleme; **güneş sensörü + eğimölçer (inclinometer) + saat + efemeris** kombinasyonuyla yapılır. Bu yöntem Lunokhod, Sojourner, MER (Spirit/Opportunity), Curiosity ve Yutu üzerinde kullanılmıştır (Ali-Dib/Furgale referanslı rover navigasyon karşılaştırması, ResearchGate 224296744). Ay'da GPS yoktur ve kullanılabilir küresel manyetik alan yoktur; bu yüzden mutlak yön için gökyüzü referansı (güneş) zorunludur — manyetik pusula işlemez.
 
**(b) Literatür/yöntem.** Ana yöntem: güneş sensörüyle güneş yönü, eğimölçerle yerçekimi (level) yönü ölçülür, efemerisle birleştirilip **QUEST (quaternion estimation)** ile (SCPO algoritması, Yang vd., ScienceDirect S1270963811001118) veya **dual-EKF** ile (Xie vd. 2012, Wiley 10.1155/2012/578719) çözülür. Enlem/boylam çıkarımı da mümkündür (celestial localization). Kaynaklar rover heading hatasını **"birkaç derece" (a few degrees)** mertebesinde bildirir; belirtilen ana hata kaynağı eğimölçerdir (star tracker localization çalışması, ResearchGate 224296744). Yıldız izleyici (star tracker) yüzeyde de modellenmiştir; ancak PSR (kalıcı gölge) ortamlarında ufuk çizgisi doğrudan görünmez ve yıldız alanının örtülmesinden (occlusion) çıkarım gerekir — bu, doğruluğu düşürür (aynı kaynak).
 
**(c) Ay yüzeyi navigasyon altyapısı (gelişmekte).** **LuGRE** (Lunar GNSS Receiver Experiment), NASA–İtalyan Uzay Ajansı (ASI) ortak yükü, Firefly **Blue Ghost Mission 1** ile **2 Mart 2025**'te Ay yüzeyine indi (CLPS Task Order 19D; Navigation, J. of ION 73(1)). NASA'nın açıklamasına göre (nasa.gov, "NASA Successfully Acquires GPS Signals on Moon", 4 Mart 2025) sistem, transit sırasında **337.690 km (209.900 mil)** mesafede rekor GNSS sinyal edinimi yaptı ve **Ay yüzeyinde ilk kez ~362.000 km (225.000 mil) mesafeden navigasyon fix'i** elde etti. Ay yörüngesinde konum, Qascom/ASI verisine göre (Inside GNSS) **yaklaşık 1.5 km konum ve ~2 m/s hız hata payıyla** hesaplandı. **LunaNet** çerçevesi (NASA/ESA/JAXA) birlikte çalışabilir PNT sinyalleri tanımlar; **Moonlight** (ESA) bir ay navigasyon takımyıldızı girişimidir.
 
**(d) LunaPath'te nasıl yapılır.** **GERÇEK:** Verilen zaman ve konum için güneşin azimut/yükseklik açısı SPICE/SpiceyPy ile hesaplanır; bir "güneş sensörü + eğimölçer" simülasyonu bu açılardan mutlak heading'i geri-çözer (algoritma gerçek, ölçüm sentetik). **MOCK:** Yıldız izleyici görüntüsü — bir yıldız alanı çizip "yön kilidi" göstermek demonstratiftir. **Öneri:** F1'i F2 ile birleştirin; güneş vektörü zaten hesaplanacak. Arayüzde "güneşten heading çözümü: X° ± birkaç derece" göstergesi yüksek demo gücü verir.
 
### F2. Gerçek Zamanlı Güneş Konumu + Işın Geliş Açısı → Termal Sıcaklık
 
**(a) Gerçek görevlerde durumu.** Ay kutup illüminasyon modellemesi olgun bir alandır. **Mazarico vd. (2011)** horizon-based yöntemi, LOLA DEM ile 240 m çözünürlükte, 18.6 yıllık presesyon döngüsü boyunca 1 saatlik adımlarla illüminasyonu hesaplar (Icarus 10.1016/j.icarus.2010.10.030). **Gläser vd.** 20 m/piksel LOLA DTM'lerle 50×50 km bölgeleri 2017–2037 arasında 1 saatlik adımlarla simüle etti (S0032063317300478). Bu modeller VIPER ve CLPS iniş yeri seçiminde kullanılıyor (Moon Trek, USRA 5080).
 
**(b) Literatür/yöntem.** Ay gündüz yüzeyi radyatif dengede kabul edilir. **Vasavada vd. (2012, AGU 10.1029/2011JE003987)** ve **Bandfield vd. (2015)**: ekvatorda ısı difüzyon modelleri, yerel saat 08–16 arası (geliş açısı <60°) radyatif dengenin **~1 K içinde** sıcaklık öngörür. Vasavada ölçümlerinde en sıcak parlaklık sıcaklıkları ~399 K'e, ortalama ekvator sıcaklığı 215.5 K'e (maks 392.3 K, min 94.3 K) ulaşır. Işın geliş açısı **cos(i)** ile etkin ışınım hesaplanır; yüzey normali eğimden türetilir. Radyatif denge sıcaklığı: **T = ((1−A)·S·cos i / (ε·σ))^(1/4)**. Bu yaklaşım gündüz + düşük geliş açısında iyidir; gün doğumu/batımı ve gece için geçersizdir (termal atalet baskın) — Bandfield vd. bunu açıkça uyarır. **heat1d** (Hayne vd. 2017; açık kaynak, GitHub `phayne/heat1d`) regolitte 1B ısı denklemini çözer; açısal-bağımlı albedo A(θ)=A₀+a(θ/45°)³+b(θ/90°)⁸, geotermal akı 0.018 W/m², ve Apollo 15/17 ısı akışı + Diviner'a karşı doğrulanmıştır.
 
**(c) Boşluk.** LunaPath'in mevcut termal grid'i **SENTETİK**. Radyatif denge formülü, bu grid'i fiziksel temele oturtacak en yüksek getirili iyileştirmedir. Kutupta güneş yükseklik açısı, Ay'ın **1.54° eksen eğikliği** nedeniyle çok düşük kalır; bu, uzun/hızlı hareket eden gölgeleri ve dikey güneş panelinin avantajını açıklar (Gläser vd.).
 
**(d) LunaPath'te nasıl yapılır.** **GERÇEK:** SpiceyPy ile güneş vektörü (azimut/yükseklik); DEM'den yüzey normali; cos(i); radyatif denge sıcaklığı. Güneş paneli gücü: panel normali · güneş vektörü ile kosinüs kaybı. **BASİTLEŞTİRİLMİŞ (etiketlenmeli):** Termal atalet ve gece soğuması tam çözülmez — "gündüz radyatif denge yaklaşımı, yerel saat 08–16 dışında geçersiz" notu eklenmeli. **Performans:** SPICE hesapları sunucuda (Python); tarayıcıda hafif yaklaşım için astronomy-engine (JS). Bu, ekibin **en yüksek getirili gerçek özelliğidir.**
 
### F3. Yüksek Çözünürlüklü DEM'in Cesium ile Görselleştirilmesi
 
**(a) Gerçek görevlerde durumu.** NASA **MMGIS** Cesium tabanlı 3B görselleştirme kullanır (github.com/NASA-AMMOS/MMGIS). **Moon Trek** (trek.nasa.gov/moon) LOLA verileriyle web tabanlı Ay portalıdır. Cesium'un NASA ile içerik işbirlikleri mevcuttur (Cesium Moon asset'i doğrudan LRO/LOLA türevidir).
 
**(b) Yöntem/teknoloji.** **Cesium Moon (Asset ID 2684829)** küresel bir 3D Tiles tileset'idir. Ay konfigürasyonu (Cesium dokümantasyonundan verbatim): `Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON;` ve `globe:false`. Dokümantasyon uyarıları verbatim: **"2D and Columbus View are not currently supported for global 3D Tiles tilesets"** ve **"Geocoder is not currently supported for lunar locations."** Kendi LOLA GeoTIFF DEM'inizi yüklemek: Cesium ion asset upload veya quantized-mesh üretimi (`CesiumTerrainProvider` quantized-mesh tile'larını destekler; format spesifikasyonu github.com/CesiumGS/quantized-mesh). Lisans/atıf: Cesium ion Terms of Service + Content Usage and Attribution Guide. **React entegrasyonu:** `resium` (npm, **MIT lisanslı**; Viewer, Entity, `Clock`, `ShadowMap` bileşenleri). `Clock` JulianDate ile güneş konumunu senkronize eder; `ShadowMap` sahne gölge haritasıdır.
 
**(c) Alternatifler.** Three.js/react-three-fiber heightmap mesh, deck.gl TerrainLayer, Potree. LunaPath 40×40 km / 500×500 px küçük bir alan olduğundan **three.js ile doğrudan heightmap mesh** de uygundur (250k vertex tek mesh'te sorunsuz, LOD gerekmez) ve Cesium'un ay-globe kısıtlarından kaçınır.
 
**(d) LunaPath'te nasıl yapılır.** **GERÇEK:** LOLA DEM'i three.js heightmap veya Cesium'a yükleme. Cesium Clock ile gölge animasyonu güneş konumuna bağlanabilir; **ANCAK Cesium'un gölgesi kendi güneş modeline dayanır**, F2'deki SPICE hesabıyla birebir örtüşmeyebilir — bu ayrım etiketlenmeli (F2 SPICE = "gerçek", Cesium gölge = "görsel"). **Karar:** Küçük alan için react-three-fiber daha kontrollü ve hızlı; Cesium "vay" etkisi ve hazır ay-arazi için. Mevcut React/TS/Vite stack'ine ikisi de uyar.
 
### F4. Operatör Kontrolü / Manuel Sürüş / Paylaşımlı Otonomi
 
**(a) Gerçek görevlerde durumu.** **RSVP** (Robot Sequencing and Visualization Program) MER, MSL ve Mars 2020'de kullanılır (JPL Robotics; NTRS 20140001459). İki bileşen: **RoSE** (komut sekans editörü, kaynak/güç/sıcaklık yönetimi) ve **HyperDrive** (3B görselleştirme). Mars 2020'de **MobSketch/ArmSketch** komut sekansı üretir; **SSim** (Surface Simulation) uçuş yazılımıyla rover tepkisini simüle eder. **VIPER**, Dünya'dan yakın-gerçek zamanlı, etkileşimli waypoint sürüşüyle işletilecekti (NASA/Ames, Colaprete): rover "operated interactively in near-real time by a NASA team back on Earth… complex and dynamic route planning and waypoint driving" ile ~100 günlük görev planlanmıştı; VIPER **50 saatten fazla sürekli karanlıkta hayatta kalamazdı** (NASA Science, verbatim: "the rover cannot endure more than 50 hours of continuous darkness").
 
**(b) Literatür/yöntem.** "Safeguarded teleoperation," "sliding/adjustable autonomy," "mixed-initiative" planlama literatürde yerleşiktir. Otonomi seviyeleri: manuel → waypoint → otonom. **Ay gecikmesi:** ESA'ya göre (esa.int/esapub/pff, Mauro) verbatim: *"For a Moon mission, the delay time is about 2 seconds for a dedicated system during periods of direct visibility up to 10 seconds if a data relay satellite is used."* ESA'nın 5G/6G Hub emülasyon testinde komut ile yanıt arası gidiş-dönüş gecikmesi **3–4 saniye** ölçülmüştür (esa.int, "ESA's 5G/6G Hub used to simulate lunar connection"). Bu düşük gecikme, Ay'da (Mars'ın aksine) sürekli izleme ve safeguarded teleoperasyonu mümkün kılar. **Coloma vd. (2022, IEEE RA-L 9857576)** proprioseptif sensör + ML ile mobilite riskini gösteren bir GUI (Hazard Information System) önerdi.
 
**(c) Boşluk.** LunaPath'te operatörün planlayıcı önerisini kabul/red/düzenleme akışı ve waypoint sürükleyip yeniden planlatma (interactive replanning) yok.
 
**(d) LunaPath'te nasıl yapılır.** **GERÇEK:** Waypoint sürükle-bırak + yeniden planlama (A* zaten <2 s). Klavye kontrolüyle "manuel sürüş" + adım adım fizik simülasyonu (mevcut). Drive-preview: seçilen segmentin batarya/sıcaklık sonucunu önizleme. **MOCK:** Birinci-şahıs rover kamerası (gerçek kamera yok — DEM'den render edilmiş temsili görüntü); HUD demonstratiftir. **YAPILAMAZ:** Uçuş-yazılımı-in-the-loop (SSim düzeyi) 25 günde yapılamaz.
 
### F5. Her Durum Geçişi İçin Risk Skoru
 
**(a) Gerçek görevlerde durumu.** MER/MSL/M2020'de sürüş riski: slip risk, tip-over (devrilme), entrapment (batma). **Ono vd. (JPL)** MAARS'ta "Risk and Resource-aware AutoNav" geliştirdi. **Skonieczny vd. (2019, J. Field Robotics)** veri-güdümlü mobilite riski öngörüsü yaptı.
 
**(b) Literatür/yöntem.** Risk-farkında planlama: kenar bazlı risk, birikimli risk, **chance-constrained** (şans-kısıtlı) planlama. **Lamarre vd. (2024, IEEE Aerospace, "Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover", arXiv 2401.08558)** güneş enerjili rover için joint chance-constrained planlama + stokastik erişilebilirlik geliştirdi ve **Cabeus Krateri PSR'lerinde** (240 m/piksel saatlik güneş görünürlük veri seti, JPL sağlamıştır) doğruladı. **Ono/Williams** p-Sulu (bounded-risk), **Santana vd.** RAO* (chance-constrained POMDP) mevcuttur. MDP/POMDP yaklaşımları gezegen navigasyonunda kullanılır. Risk niceleme: olasılık × sonuç veya normalize tehlike indeksi.
 
**(c) Boşluk.** LunaPath'te "risk seviyesi" var ama durum-geçişi (edge) bazlı, açıklanabilir risk dökümü yok.
 
**(d) LunaPath'te nasıl yapılır.** **GERÇEK:** Her A* kenarı için ağırlıklı risk indeksi (eğim, slip proxy, gölge/termal, SoC marjı). Renk kodlu segmentler + birikimli risk eğrisi. "Neden bu rota" açıklanabilirliği: AHP kriter katkı dökümü (zaten var) + contrastive explanation (arXiv 2004.12960). **MOCK:** Gerçek olasılıksal chance-constrained çözüm (p-Sulu/RAO*) 25 günde yapılamaz; "olasılık dağılımı" gösterimi demonstratif olur. **Öneri:** Risk indeksini gerçek, olasılık bandını mock (Bölüm 3, belirsizlik bandı) tutun.
 
---
 
## Bölüm 3 — Ek Özellik Önerileri (Öncelik Sıralı)
 
**P1 — Zaman kaydırağı / temporal scrubbing.** Zaman ilerledikçe gölge/güneş/sıcaklık/rota maliyeti canlı değişir. MMGIS'te **TimeControl** plugin'i ("Time-enabled data visualization with temporal queries"), Cesium'da **Clock** (JulianDate), NASA SVS illüminasyon videolarında (2025–2028, 2 saatlik adım, 17.532 kare) mevcuttur. LunaPath'te en yüksek getirili özellik: F2 ile birleşince "zaman ekseni yok" eksikliğini çözer. **GERÇEK. Süre: orta.**
 
**P1 — Enerji/termal zaman çizelgesi.** Rota boyunca SoC, sıcaklık, güç üretim/tüketim grafikleri. **OpenMCT** (NASA, Apache 2.0, github.com/nasa/openmct; VISTA/WARP olarak M2020 ve lunar rover konseptlerinde kullanılıyor) telemetri panellerinde standarttır ("streaming and historical data, imagery, timelines… in one place"). LunaPath'te adım-adım simülasyon verisi zaten var. **GERÇEK. Süre: düşük.**
 
**P1 — Rota kesiti / yükseklik profili.** Güzergâh boyunca eğim/yükseklik/sıcaklık. MMGIS MeasureTool "continuous elevation profiles" destekler. DEM'den doğrudan. **GERÇEK. Süre: düşük.**
 
**P1 — Duyarlılık kaydırağı (AHP).** AHP ağırlıkları değiştikçe rota canlı güncellenir. A* <2 s olduğundan gerçek zamanlı yeniden hesap mümkün. **GERÇEK. Süre: düşük. Çok yüksek demo gücü.**
 
**P2 — Güneş yolu / ufuk panoraması (skyline).** Bir noktadan görülen ufuk profili + güneşin buna göre doğuş/batışı. **Mazarico horizon method** ile doğrudan ilişkili; kutupta güneşin izi analemma benzeri. DEM'den ray-casting ile ufuk açısı. **GERÇEK. Süre: orta.**
 
**P2 — Erişilebilirlik / isochrone haritası.** "Bu SoC ve süreyle nereye kadar?" MMGIS **Isochrone** plugin'i (NASA-AMMOS) "terrain traversability analysis and reachability mapping" yapar. Algoritma: maliyet-sınırlı Dijkstra/BFS. **GERÇEK. Süre: orta.**
 
**P2 — Alternatif rota / Pareto cephesi.** Çok amaçlı optimizasyonda trade-off. **Ganti/Otten vd. (2018, "Globally optimal rover traverse planning in 3D using Dijkstra's algorithm", PSS S0032063318302526)** Pareto cepheleri üretir. Eleme gerekçesi = contrastive explanation (arXiv 2004.12960). Uygulama: birkaç ağırlık setiyle A* çalıştırıp non-dominated çözümleri çiz. **GERÇEK. Süre: orta.**
 
**P2 — Belirsizlik bandı.** Rota maliyeti/SoC güven aralığı, DEM hata haritasından. **PGDA** (pgda.gsfc.nasa.gov/products/90) LOLA ürünleri: `LDEM_..._ERR.TIF` (yükseklik hatası), `LDSM_..._ERR.TIF` (eğim hatası) ve **"100 clones"** (Barker vd. 2021, PSS 10.1016/j.pss.2020.105119; **medyan RMS Z hatası ~0.30–0.50 m, RMS eğim hatası ~1.5–2.5°**; iyileştirilmiş track jeolokasyon belirsizliği ~10–20 cm yatay, ~2–4 cm dikey). Clone'larla Monte Carlo → rota kararlılığı. **GERÇEK ama veri entegrasyonu zaman alır. Süre: orta-yüksek.**
 
**P2 — Traverse oynatma (playback).** Rotanın zamanla animasyonu, hız kontrolü, telemetri senkronu. RSVP playback ("review of both rehearsed rover behavior and downlinked results… simultaneously"), OpenMCT timeline'da var. **GERÇEK. Süre: orta.**
 
**P2 — Rover 3B modeli + eğim/yalpalama.** Arazi üzerinde rover duruşu, devrilme marjı. RSVP HyperDrive ve OmniLRS'de var. DEM normalinden roll/pitch hesaplanır. **GERÇEK (basit glTF + eğim). Süre: orta.**
 
**P3 — Dünya görüş hattı (DTE) / viewshed.** Haberleşme penceresi. MMGIS **Viewshed** (JPL, NPO-51796-1, açık kaynak) "real-time viewshed analysis from a tiled DEM" yapar. VIPER, DTE radyo bağlantısına muhtaçtı ve sinyal engelleyen krater kenarlarından/dağlardan kaçınmalıydı; ayrıca ayın güney kutbu görüşten iki haftalık libration blackout'unda safe haven'da beklerdi (NASA Science). DEM'den Dünya vektörüne line-of-sight. **GERÇEK. Süre: orta.**
 
**P3 — Güvenli sığınak (safe haven) yakınlık göstergesi.** VIPER safe haven: Dünya ufkun altındayken minimum süre güneş alan konum (Lamarre vd. arXiv 2401.08558'de VIPER tanımı alıntılanır). "En yakın güvenli noktaya kaç saat" göstergesi. İllüminasyon haritası + mesafe. **GERÇEK. Süre: orta.**
 
**P3 — Acil durum / iptal rotası (abort/walkback).** Herhangi bir noktadan geri dönüş fizibilitesi. **MIT SEXTANT** "walkback" (eve en verimli dönüş) hesaplar; acil operasyonlar için. Ters A*. **GERÇEK. Süre: düşük-orta.**
 
**P3 — Tehlike vurgulama (kaya/krater tespiti).** 80 m grid altı tehlikeler. **DeepMoon** (Silburt vd. 2019, Icarus 10.1016/j.icarus.2018.06.022; U-Net; **MIT lisansı**, GitHub `silburt/DeepMoon`, Zenodo 10.5281/zenodo.1133969): **%92 recall, ~%11 yanlış-pozitif, F1 ~0.67–0.74**, LRO-Kaguya birleşik DEM. **BoulderNet** (Prieur vd. 2023, JGR Planets 10.1029/2023JE008013; Mask R-CNN; açık kaynak, Zenodo): kaya tespiti **AP50 0.52 → 0.58** (YOLO sürümü, Amaro vd. 2026, 10.1029/2024JE008769; tam NAC görüntüsü ~30 dk). **ÖNEMLİ BOŞLUK (literatürde açıkça belirtiliyor):** Otomatik derin öğrenme tehlike overlay'leri iniş GNC'sinde olgun, fakat uçmuş bir görevde otonom rover **rota planlama** için entegre edilmemiştir (Springer MVA 10.1007/s00138-024-01533-3, verbatim: "they focus on safe landing… there is a deficiency in rock and boulder identification during the rover navigation"). LunaPath'te **önceden-hesaplanmış tespit overlay'i = MOCK/demonstratif**. Süre: yüksek (gerçek eğitim yapılamaz).
 
**P3 — Ölü hesap (dead reckoning) sapma görselleştirmesi.** Odometri hatasının zamanla büyümesi + konum belirsizlik elipsi. **Tekerlek/dead-reckoning hatası ~%10 kat edilen mesafe** (Helmick vd. 2004, JPL, verbatim: "wheel odometry accuracy is not better than 10% of distance traveled"); düz arazide en iyi ~%1.2 (DFKI 2017). **Görsel odometri ~%0.1–3**, JPL hedefi/başarımı **<%2.5** (Helmick vd.; Maimone vd. 2007, JFR 10.1002/rob.20184 — MER'de iki yıllık uçuş VO). **Yutu (Chang'e-3) cross-site görsel lokalizasyon ~%1–4** (Wan vd. 2014, ISPRS Archives XL-4:279); **Chang'e-4 (Yutu-2)** DOM-eşleşmeli noktalarda **~%0.5'e** iner, eşleşme noktalarında 0 hata (Di/Wan vd., Science China Info Sci 10.1007/s11432-019-2796-1); Yutu-2 14. ay günü sonunda **367.25 m** kat etti. Belirsizlik = kovaryans → **hata elipsi** olarak çizilir (arXiv 2008.07157 rover planlamada "error ellipse"). Basit model: mesafe × %oran → elips. **GERÇEK. Süre: düşük-orta. Orijinal ve yüksek demo gücü.**
 
**P3 — Senaryo karşılaştırma (diff).** İki koşum arasındaki fark. **GERÇEK. Süre: düşük.**
 
**P3 — Çoklu rover eşzamanlı görünüm.** Aynı harita, farklı profil, senkron zaman. LunaPath'te 4 profil (LPR-1, VIPER, LUVMI-M, Yutu-2) zaten var. **GERÇEK. Süre: orta.**
 
**P4 — Dijital ikiz / telemetri oynatma.** Gerçek görev telemetrisi (Yutu-2, Pragyan). Yutu-2 traverse mesafesi (367.25 m) literatürde var ama **tam telemetri (SoC/sıcaklık zaman serisi) kamuya açık değil — kaynakta bulunamadı.** Kısmen MOCK. Süre: yüksek.
 
**P4 — Rapor içine gömülü 3B ekran görüntüsü.** Otomatik raporda görsel yakalama (canvas.toDataURL / html2canvas). **GERÇEK. Süre: düşük.**
 
**P4 — İşbirlikçi işaretleme / anotasyon.** MMGIS **DrawTool** + WebSocket "live drawing sync" ("real-time collaboration across multiple users"). Çok kullanıcılı backend gerektirir. **GERÇEK. Süre: yüksek.**
 
**Ek özgün öneriler (aynı format):**
- **Güneş-senkron "en iyi kalkış zamanı" bulucu:** Zaman ekseni üzerinde hedefe minimum-risk / maksimum-güneş penceresini otomatik arama (Mazarico "Sunlit pathways" 2023, Acta Astronautica mantığı). **GERÇEK. Orta.**
- **Kümülatif güneş maruziyeti ısı-haritası:** Rota boyunca toplam alınan güneş enerjisi. **GERÇEK. Düşük.**
- **"Ne-olursa" batarya arıza senaryosu:** Kapasite %X düşerse rota fizibilitesi. **GERÇEK. Düşük.**
---
 
## Bölüm 4 — Mock vs Gerçek Ayrımı ve Etiketleme Pratikleri
 
**Standartlar.** **NASA-STD-7009** (Standard for Models and Simulations; güncel sürüm **7009B, 5 Mart 2024**) model kredibilitesi için **sekiz bileşen** tanımlar: Verification, Validation, **Input Pedigree**, Results Uncertainty, Results Robustness, Use History, M&S Management, People Qualifications (NTRS 20160000202). "Input Pedigree" = girdi verisinin kalitesi/kökeni. Standart, sonuçların karar vericilere **kredibilite bilgisiyle birlikte** raporlanmasını ve varsayımların açıkça beyanını ("caveat: an explanation to prevent misinterpretation") ister. Bu, doğrudan görselleştirmeye **veri kökeni (provenance/pedigree) etiketi** olarak yansır. ECSS'in benzer model doğrulama gereksinimleri vardır (**detay kaynakta bulunamadı**).
 
**Etiketleme pratikleri.** Uzay mühendisliği kültüründe demonstratif özellikler "notional," "representative," "illustrative," "simulated" olarak etiketlenir. Gerçek araçlarda "simulated data" vs "flight data" ayrımı yapılır — RSVP'de rehearsed (simüle) ve downlinked (uçuş) sonuçlar karşılaştırma için yan yana gösterilir (NTRS 20140001459).
 
**LunaPath için somut öneri — "pedigree rozeti" sistemi:**
- 🟢 **GERÇEK ÖLÇÜM:** LOLA DEM, PGDA hata haritaları, SPICE efemeris.
- 🟡 **FİZİKSEL MODEL:** radyatif denge sıcaklığı, cos(i) ışınım, A* maliyet, kenar risk indeksi.
- 🔴 **SENTETİK / DEMO:** yıldız izleyici, birinci-şahıs kamera, olasılık bandı, ML tehlike overlay, telemetri oynatma.
**Jüri bağlamı.** Mock özellik göstermek, **açıkça etiketlendiğinde ve fiziksel temeli anlatıldığında kabul edilebilir ve olgunluk gösterir.** Etiketlenmemiş mock ("gerçekmiş gibi" sunulan sentetik veri) güvenilirlik kaybı yaratır — NASA-STD-7009'un özü tam olarak budur (girdi pedigresini en düşük kaliteye göre skorla, karar vericiyi riskten haberdar et). **Sunum stratejisi:** Her özellik için "şu an gerçek / şu an demo, tam sürümde şöyle gerçekleştirilir" ayrımını proaktif yapın.
 
---
 
## Bölüm 5 — Özellik Matrisi (Hangi Özellik Hangi Gerçek Araçta)
 
| Özellik | MMGIS | Moon Trek | OpenMCT | RSVP | Cesium | Lamarre/lunar_planner | gplanetary-nav | OmniLRS | STK |
|---------|-------|-----------|---------|------|--------|----------------------|----------------|---------|-----|
| Zaman kaydırağı | ✔ TimeControl | ✔ | ✔ timeline | ✔ playback | ✔ Clock | ? | ? | ✔ | ✔ |
| Viewshed / DTE | ✔ Viewshed | ✔ | ✖ | ✖ | kısmi | ✔ (görüş) | ? | ✖ | ✔ |
| Isochrone / erişilebilirlik | ✔ Isochrone | ✖ | ✖ | ✖ | ✖ | ✔ reachability | ✔ | ✖ | ? |
| İllüminasyon / gölge | ✔ Shade (SPICE) | ✔ | ✖ | kısmi | ✔ shadow map | ✔ | ? | ✔ ray-tracing | ✔ |
| Termal model | ✖ | ✖ | ✖ | ✖ | ✖ | kısmi | ? | ✔ thermal | ? |
| Risk / chance-constrained | ✖ | ✖ | ✖ | kısmi | ✖ | ✔ | ✔ | ✖ | ✖ |
| Telemetri timeline | ✖ | ✖ | ✔ | ✔ | ✖ | ✖ | ✖ | ✔ Yamcs | ✔ |
| 3B rover / eğim | ✖ | kısmi | ✖ | ✔ HyperDrive | ✔ | ✖ | ? | ✔ | ✔ |
| Anotasyon / çizim | ✔ DrawTool | ✔ | ✖ | ✔ | ✖ | ✖ | ✖ | ✖ | ✔ |
| Hazard tespit (ML) | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ | kısmi | ✖ |
 
("?" = kaynakta doğrulanamadı; STK = ticari, Ansys/AGI.)
 
**Açık kaynak lisansları:** MMGIS (Apache 2.0, NASA-AMMOS), OpenMCT (Apache 2.0, NASA), CesiumJS (Apache 2.0; ion içeriği ayrı ToS), resium (MIT), heat1d (açık kaynak; **lisans kaynakta belirtilmedi**), DeepMoon (MIT), BoulderNet (açık kaynak Zenodo; **lisans kaynakta doğrulanamadı**), OmniLRS (açık kaynak; **lisans kaynakta doğrulanamadı**). Moon Trek / RSVP / STK son-kullanıcı araçlarıdır (RSVP JPL-içi; STK ticari).
 
---
 
## Bölüm 6 — 25 Gün / 5 Kişi Kısıtı: Üç Tablo
 
### (a) YAPILABİLİR
 
| Özellik | Süre | Kişi | Demo gücü | Gerekçe |
|---------|------|------|-----------|---------|
| F2 Gerçek zamanlı güneş + radyatif termal | 5–7 gün | 1–2 | Çok yüksek | SpiceyPy + basit formül; sentetik grid'i fizikselleştirir |
| P1 Zaman kaydırağı | 4–6 gün | 1 | Çok yüksek | F2 ile birleşir; zaman ekseni eksikliğini çözer |
| P1 Enerji/termal timeline | 2–3 gün | 1 | Yüksek | Simülasyon verisi zaten var; grafikleme |
| P1 Rota kesiti / yükseklik profili | 2 gün | 1 | Yüksek | DEM'den doğrudan |
| P1 AHP duyarlılık kaydırağı | 2–3 gün | 1 | Çok yüksek | A* <2 s; canlı yeniden hesap |
| F5 Kenar bazlı risk + renk kodlu segment | 3–4 gün | 1 | Yüksek | Mevcut maliyet fonksiyonuna eklenir |
| F3 DEM 3B (three.js heightmap) | 4–6 gün | 1–2 | Çok yüksek | 40×40 km küçük; heightmap mesh yeterli |
| P2 Alternatif rota / Pareto | 3–4 gün | 1 | Yüksek | Farklı ağırlıklarla A* + non-dominated |
| P2 Isochrone | 3–4 gün | 1 | Yüksek | Maliyet-sınırlı Dijkstra |
| P3 Abort / walkback rotası | 2 gün | 1 | Orta | Ters A* |
| P3 Dead-reckoning belirsizlik elipsi | 3 gün | 1 | Yüksek | Basit hata modeli (mesafe × %oran) + elips |
| P3 Senaryo diff | 2 gün | 1 | Orta | İki koşum karşılaştırma |
| F4 Waypoint sürükle + yeniden planlama | 3–4 gün | 1 | Yüksek | A* hızlı; etkileşimli |
| P2 Güneş yolu / skyline | 3–4 gün | 1 | Orta-yüksek | DEM ray-casting |
| P3 Safe haven yakınlık | 2–3 gün | 1 | Orta | İllüminasyon + mesafe |
| P4 Rapor 3B ekran görüntüsü | 1 gün | 1 | Düşük | canvas.toDataURL |
 
### (b) RİSKLİ (yapılabilir ama zaman/entegrasyon riski yüksek)
 
| Özellik | Süre | Kişi | Demo gücü | Gerekçe |
|---------|------|------|-----------|---------|
| F3 Cesium Moon tam entegrasyon | 6–9 gün | 2 | Çok yüksek | Ay-globe kısıtları (2D/Columbus/Geocoder yok), ion asset / quantized-mesh öğrenme eğrisi |
| P2 Belirsizlik bandı (100 clone Monte Carlo) | 6–8 gün | 1–2 | Yüksek | PGDA clone verisi indirme + işleme + performans |
| P3 Viewshed / DTE | 4–6 gün | 1 | Orta | Line-of-sight doğru ama performans yükü |
| P2 Traverse playback tam senkron | 4–6 gün | 1 | Yüksek | Telemetri senkronu detay ister |
| P3 Rover 3B eğim / roll | 4–6 gün | 1 | Orta | glTF model + doğru duruş |
| P3 Hazard overlay (önceden hesaplanmış) | 5–7 gün | 1–2 | Orta | Gerçek eğitim yok; hazır/mock overlay |
| P4 İşbirlikçi anotasyon | 6+ gün | 1–2 | Orta | WebSocket backend |
 
### (c) YAPILAMAZ (25 gün / 5 kişide)
 
| Özellik | Gerekçe |
|---------|---------|
| F1 Gerçek yıldız izleyici konum belirleme | Yıldız katalog eşleştirme + PSR skyline çıkarımı; yalnızca mock demo mümkün |
| F2 Tam termal atalet (heat1d entegrasyonu) | Gece soğuması / 1B ısı denklemi grid genelinde gerçek zamanlı çözülemez; radyatif denge yaklaşımı yeterli |
| F4 Uçuş-yazılımı-in-the-loop (SSim benzeri) | RSVP SSim düzeyi flight-code simülasyonu kapsam dışı |
| F5 Gerçek chance-constrained (p-Sulu / RAO*) | Olasılıksal çözücü implementasyonu 25 günü aşar |
| Gerçek ML hazard eğitimi (DeepMoon/BoulderNet yeniden eğitimi) | Veri + GPU + doğrulama süresi yetersiz; hazır model çıktısı kullanılabilir |
| Yutu-2 / Pragyan tam telemetri dijital ikiz | Kamuya açık tam telemetri (SoC/sıcaklık zaman serisi) yok — kaynakta bulunamadı |
 
---
 
## Bölüm 7 — Teknik Uygulama Notları
 
**Cesium / React.** `resium` (MIT, npm) React bileşenleri: Viewer, Clock, ShadowMap, Entity. Ay için: `Cesium.Ellipsoid.default = Cesium.Ellipsoid.MOON; new Viewer({globe:false, sceneModePicker:false, baseLayerPicker:false, geocoder:false})`. **Kısıt:** 2D/Columbus View ve Geocoder Ay için desteklenmez (Cesium dokümantasyonu). **Alternatif:** react-three-fiber ile heightmap mesh — 40×40 km küçük alan için daha hafif ve tam kontrol. **Öneri:** Cesium'u "vay" etkisi + hazır ay-arazi + gölge haritası için; three.js'i hız ve kontrol için düşünün. İkisi de mevcut React/TS/Vite stack'ine uyar.
 
**SPICE / efemeris seçimi.** Sunucu tarafı (Python/FastAPI): **SpiceyPy** (NAIF SPICE Python wrapper) en doğru. Gerekli kernel'ler: LSK (leapseconds), SPK (DE421 veya DE440 gezegen efemeris — LunaPath zaten DE421/MOON_ME kullanan PGDA verisiyle uyumlu), PCK (Moon binary/text), FK. **spicedmoon** (PyPI) yüksek seviye ay geometrisi (azimut/zenith) sağlar. Alternatifler: astropy, skyfield, jplephem. Tarayıcı için hafif JS: astronomy-engine. **Öneri:** Güneş vektörü ve termal hesaplar sunucuda SpiceyPy ile; N zaman adımı önceden hesaplanıp (ör. 100 kare) frontend'e zaman-serisi olarak gönderilir — zaman kaydırağı için ideal, gerçek zamanlı SPICE çağrısı gerekmez.
 
**Performans sınırları.** 500×500 = 250k hücre; A* <2 s (mevcut). Zaman kaydırağı: her adımda güneş/gölge/termal yeniden hesap yerine, önceden hesaplanan kareler arasında frontend interpolasyonu. Monte Carlo (100 clone) sunucuda batch/paralel, gerçek zamanlı değil. Cesium tile streaming küçük alan için sorunsuz; three.js 250k vertex tek mesh'te LOD'suz çalışır. **Gölge doğruluğu uyarısı:** Cesium'un kendi güneş modeli SPICE ile birebir örtüşmez — F2 SPICE hesabını "gerçek", Cesium gölgesini "görsel" olarak etiketleyin (Bölüm 4 pedigree sistemi).
 
**DEM veri kaynakları.** PGDA (pgda.gsfc.nasa.gov/products/90): `LDEM_80S_20MPP` (yükseklik), `_ERR` (hata), `LDSM` (eğim) + `_ERR`, hillshade, roughness. 5 m/piksel iniş yeri DEM'leri + 100 clone (products/78, /92). LOLA arşivi: imbrium.mit.edu. Referans çerçeve: south polar stereographic, MOON_ME / DE421 — **LunaPath'in mevcut projeksiyonuyla tam uyumlu.**
 
---
 
## Bölüm 8 — Kaynakça (Kategorili)
 
**Gerçek görev / araç.**
- LuGRE: *NAVIGATION: J. of ION* 73(1), navi.ion.org/content/73/1/navi.756; NASA NTRS 20220002074; NASA "NASA Successfully Acquires GPS Signals on Moon" (4 Mart 2025); Inside GNSS (lunar orbit ~1.5 km doğruluk). Blue Ghost M1 iniş 2 Mart 2025.
- VIPER: NASA Science science.nasa.gov/mission/viper/lunar-operations; CSA asc-csa.gc.ca; Lamarre vd. arXiv 2307.16786 & 2401.08558; Smithsonian (Colaprete, "50 hours").
- RSVP: JPL Robotics www-robotics.jpl.nasa.gov (MER/MSL/M2020); NTRS 20140001459.
- Yutu / Yutu-2: Wan vd. 2014 (ISPRS Archives XL-4:279); Di/Wan vd. (Science China Info Sci 10.1007/s11432-019-2796-1); Ma vd. 2020 (Photogrammetric Record 10.1111/phor.12309); Liu vd. 2015 (Sci China Phys Mech Astron 10.1007/s11433-014-5612-0).
- MMGIS: github.com/NASA-AMMOS/MMGIS (Apache 2.0); Viewshed NPO-51796-1 (software.nasa.gov).
- Moon Trek: trek.nasa.gov/moon; Law & Day (USRA 5080); NASA SVS 5027/5127.
- OpenMCT: github.com/nasa/openmct (Apache 2.0); VISTA/WARP (Open Source Next Gen Visualization).
- OmniLRS: github.com/OmniLRS/OmniLRS; arXiv 2309.08997; Allan vd. 2019 (NTRS 20190027571, Gazebo).
**Yöntem / literatür.**
- Göksel navigasyon: SCPO (Yang vd., ScienceDirect S1270963811001118); dual-EKF (Xie vd. 2012, Wiley 10.1155/2012/578719); star tracker localization (ResearchGate 224296744).
- Termal: Vasavada vd. 2012 (AGU 10.1029/2011JE003987); Bandfield vd. 2015 (Icarus S0019103514006368); heat1d Hayne vd. 2017 (GitHub phayne/heat1d).
- İllüminasyon: Mazarico vd. 2011 (Icarus 10.1016/j.icarus.2010.10.030); Gläser vd. (S0032063317300478); Mazarico vd. 2023 "Sunlit pathways" (Acta Astronautica 204:49–57, S0094576522006956).
- Risk / planlama: Lamarre vd. 2024 (arXiv 2401.08558) & 2023 (Acta Astronautica 213:708); Ono vd. MAARS; MDPI Remote Sensing 17(11):1924 (path-planning review); Pareto/Dijkstra (Ganti vd., PSS S0032063318302526); contrastive explanation (arXiv 2004.12960).
- DEM belirsizlik: Barker vd. 2021 (PSS 10.1016/j.pss.2020.105119); Barker vd. 2023 (PSJ 10.3847/PSJ/acf3e1); PGDA products/78, /90, /92.
- Hazard ML: DeepMoon Silburt vd. 2019 (Icarus 10.1016/j.icarus.2018.06.022, MIT); BoulderNet Prieur vd. 2023 (JGR Planets 10.1029/2023JE008013); Amaro vd. 2026 (10.1029/2024JE008769); Springer MVA 10.1007/s00138-024-01533-3 (rover-nav boşluğu).
- Odometri: Helmick vd. 2004 (JPL, path following/VO); Maimone vd. 2007 (JFR 10.1002/rob.20184); rover uncertainty ellipse (arXiv 2008.07157).
- Teleoperasyon / gecikme: ESA (esa.int/esapub/pff, Mauro); ESA 5G/6G Hub (3–4 s round-trip); Coloma vd. 2022 (IEEE RA-L 9857576).
**Araç / kütüphane.**
- Cesium Moon (Asset 2684829): cesium.com/platform/cesium-ion/content/cesium-moon (CesiumJS Apache 2.0; ion içerik ayrı ToS); quantized-mesh spec github.com/CesiumGS/quantized-mesh.
- resium: npmjs.com/package/resium (MIT); reearth/resium.
- SpiceyPy: spiceypy.readthedocs.io; spicedmoon (PyPI).
- Alternatifler: three.js/react-three-fiber, deck.gl TerrainLayer, Potree.
**Standart.**
- NASA-STD-7009B (5 Mart 2024), standards.nasa.gov/standard/NASA/NASA-STD-7009; NASA-HDBK-7009 (NTRS 20140002378); sekiz kredibilite bileşeni (NTRS 20160000202).
- ECSS model doğrulama gereksinimleri: **detay kaynakta bulunamadı.**
---
 
### Kapanış Değerlendirmesi (Karar Odaklı)
Ekibin en akıllı hamlesi, dağınık özellik listesi yerine **"gerçek fizik omurgası + zaman ekseni"** etrafında yoğunlaşmaktır: **F2 (SPICE + radyatif termal) → P1 zaman kaydırağı → F5 kenar risk → P1 AHP duyarlılık kaydırağı**. Bu dörtlü, LunaPath'in en zayıf noktalarını (statik snapshot, sentetik termal) doğrudan gerçekleştirir, tümü 25 günde biter ve jüriye "gerçek veri + gerçek fizik" mesajı verir. F3'te **three.js heightmap** ile başlayıp zaman kalırsa Cesium'a geçmek en düşük riskli yoldur. Mock özellikleri (yıldız izleyici, birinci-şahıs kamera, ML tehlike overlay) **açık pedigree rozetleriyle** sunun — bu, NASA-STD-7009 kültürüne uygun olup güvenilirliği artırır. **Eşik/karar değiştirici:** 20 Ağustos'a kadar F2+zaman kaydırağı çalışmıyorsa, Cesium tam entegrasyonunu (riskli tablo) iptal edip three.js'e sabitleyin ve kalan bütçeyi risk görselleştirmesi + timeline'a aktarın.