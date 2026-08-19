# LunaPath — Ay Güney Kutbu Rover Rota Planlama: Kapsamlı Domain Araştırması
 
## 0. Bu belge nasıl okunmalı — kapsamın ne OLMADIĞI
 
Bu belge, FEZA ekibinin (Çankaya Üniversitesi) LunaPath aracının (Ay güney kutbu, çok kriterli ağırlıklı A* rota planlayıcı, statik snapshot, TRL~3 karar destek aracı) TUA Astro Hackathon Ulusal Final'e (7-13 Eylül 2026) hazırlığı için hazırlanmış bir domain araştırması ve karar kaydıdır. Bugün 13 Ağustos 2026, özellik dondurma 24 Ağustos 2026, kalan süre 25 gün, ekip 5 kişi.
 
Bu belge NE DEĞİLDİR: (a) bir uçuş yazılımı gereksinim dokümanı değil; (b) gerçek görev doğrulaması içermez; (c) bizim değerlerimizin doğru olduğunu iddia etmez — literatürle karşılaştırır. Kaynağı olmayan hiçbir sayı yazılmamıştır; boş hücreler "kaynakta belirtilmemiş"tir. Öneri ile mevcut durum ayrı tutulmuştur.
 
Kritiklik etiketleri: **[K]** Kritik · **[O]** Önemli · **[B]** Bonus.
 
Açık erişim notu: NTRS, arXiv, PDS, ecss.nl ve standards.nasa.gov açık erişimdir. ScienceDirect/Springer/IEEE/Science çoğunlukla erişim duvarı ardındadır (künye açık).
 
---
 
## 1. Yönetici Özeti — Kilit Bulgular/Kararlar Tablosu
 
| # | Kilit bulgu | Sayı/kaynak | LunaPath'e etkisi | Karar |
|---|---|---|---|---|
| 1 | Kutup rover operasyonunda darboğaz bant genişliği değil, **hareketli gölge + güneş enerjisi + haberleşme penceresi üçlüsü** | VIPER nominal 20 cm/s ama "Speed Made Good" 0.8 cm/s (≈25× Perseverance'tan yavaş), Fong NTRS 20250004148 | Bizim gölge/enerji/termal katmanlarımız doğru problemi hedefliyor | Konumlandırmayı "kutup-spesifik stratejik planlayıcı" olarak sabitle (Domain, 24 Ağu) |
| 2 | Gerçek görevler **stratejik (küresel, yer) + taktik + otonom yerel** katmanlı planlar; bizde yerel tehlike kaçınma yok | VIPER 3 katman; Perseverance AutoNav 17.7 km'nin %88'ini değerlendirdi | "Küresel planlayıcıyız, yerel kaçınma kapsam dışı" ifadesini rapora yaz | Kapsam sınırını açıkça belgele (Domain, 24 Ağu) |
| 3 | Termal modelimiz SABİT OFSET (T_iç=T_yüzey±); literatür lumped-capacitance (zaman sabitli) kullanıyor | — | En büyük fiziksel zayıflık | Sabit ofseti "kaba vekil model" olarak etiketle + duyarlılık analizi ekle (Backend, 22 Ağu) |
| 4 | Ay güney kutbunda klasik 14/14 gün döngüsü DEĞİL; arazi kaynaklı hızlı/uzun gölge dinamiği baskın | Eksen eğikliği 1.5°; VIPER'ın göreceği en yüksek güneş elevasyonu ~6°, NASA/VIPER Andrews 2024 | ZAMAN EKSENİ olmaması en kritik kavramsal eksik | Statik snapshot sınırlamasını yönetici özetinde kabul et (Domain, 24 Ağu) |
| 5 | AHP CR hesabı ve n=4 RI zorunlu; rank reversal bilinen zafiyet | RI(n=4)=0.90; Saaty CR<0.1 (INCOSE: n=4 için CR≤%9) | Savunulabilirlik için CR raporlanmalı + duyarlılık | CR değerini ve RI(4)=0.90'ı rapora ekle (Backend, 20 Ağu) |
| 6 | AYAP-2 rover'ı henüz konsept tasarım; öğrenci takımları ön çalışma yapıyor | TUA/Sabah 8 Şubat 2025 | Projemiz doğrudan milli programla hizalı; güçlü sunum argümanı | Türkiye bağlamını sunuma koy (Domain, 24 Ağu) |
| 7 | Radyasyon robotik rover için rota kriteri DEĞİL (doz görev ömrü kısıtı) | Chang'e-4 LND 13.2±1 µGy/saat Si | Radyasyonu rota kriteri yapmama kararımız doğru | Radyasyonu "kapsam dışı, gerekçeli" olarak yaz (Domain, 24 Ağu) |
 
---
 
## 2. Ana Gövde
 
### 1.1 Gerçek görevler ne yaptı [K]
 
#### 1.1.1 Traverse planlama ve mesafeler [K]
 
**a) Bugün bizde ne var:** 8 yönlü grid üzerinde çok kriterli A*, <2 s hesap, statik snapshot. Planlama döngüsü, ekip rolü, otonomi modellenmemiş.
 
**b) Literatür/sektör:**
 
| Görev | Günlük/toplam mesafe | Otonomi | Kaynak (açık erişim) |
|---|---|---|---|
| Perseverance | Tek sol rekoru 347.7 m; insansız sürüş rekoru 699.9 m; ilk Mars yılı 17.7 km, AutoNav %88 değerlendirdi; ortalama 144.4 m/sol | AutoNav "thinking while driving" | Verma et al., Science Robotics 2023, DOI 10.1126/scirobotics.adi3099 (duvarlı); NASA JPL (açık) |
| Curiosity | Otonom rotalar ~100 m'ye kadar | Sınırlı AutoNav | NASA JPL (açık) |
| VIPER (planlanmış) | ~20 km toplam, >90 gün; SMG 0.8 cm/s (nominal 20 cm/s) | Yer-döngüsü teleoperasyon | Ennico-Smith et al. NTRS 20230004239; Fong NTRS 20250004148 (açık) |
| Yutu-2 | Toplam 1.613 km (7+ yıl); Gün 1: 44.185 m, Gün 2: 75.815 m; ~30 m/lunar gün | Çoğu teleoperasyon; 5. lunar günde 2.7 m otonom (0.5 m'lik 5 segment) | Ding et al. 2022; Planetary Society (açık); Wikipedia |
| Pragyan (Chandrayaan-3) | Toplam 101.4 m, 12 gün | Yer komutlu | ISRO; Wikipedia (açık) |
 
VIPER planlaması: Stratejik plan (tüm görev, L-1 yıl baz, aylık güncelleme, 20 m/piksel LOLA DEM), Taktik plan (1 lunar gün ~10-14 Dünya günü, 1 m/piksel Shape-from-Shading DEM, vardiya başına güncelleme). Mission Science Center'da taktik planlayıcı bilim insanlarıyla yan yana çalışır. VIPER "Speed Made Good" nominal 20 cm/s'nin çok altındadır: Terry Fong (VIPER Lead Rover Driver, NTRS 20250004148, 24 Nisan 2025) "0.8 cm/s Speed Made Good (yaklaşık Perseverance'ın 25 katı yavaş)" belirtir; gölge kenarlarında hız 0.1-1.8 cm/s aralığındadır (VIPER/Andrews 2024).
 
**c) Boşluk:** Bizde planlama döngüsü/ekip rolü/SMG kavramı yok; tek statik çözüm üretiyoruz. Mesafe ölçeğimiz (40×40 km pencere) VIPER'ın ~20 km toplam sürüşüyle uyumlu ama biz zamansal maliyeti modellemiyoruz.
 
**> KARAR:** SMG (Speed Made Good) kavramını rapora ekle; bizim "hesap süresi <2 s" metriğimizin gerçek görev "sürüş süresi"nden farkını açıkça belirt. (Domain, 22 Ağu)
 
#### 1.1.2 Yer-döngüsü vs otonomi [K]
 
**a) Bizde:** Ne yer-döngüsü ne otonomi modellenmiş; planlayıcı Dünya'da bir kez çalışır.
 
**b) Literatür:** NASA NTRS 20170009822 (Trimble, SpaceOps 2017, açık): Mars gidiş-dönüş ışık süresi ~14-40 dk; Ay için birkaç saniye ama sistem yüküyle toplam komut gecikmesi **6 saniyeden 40+ saniyeye** çıkabilir. "Ay mesafesinde bile gidiş-dönüş ışık süresi + haberleşme yükü joystick sürüşe izin vermez." Perseverance ilk Mars yılında 17.7 km'nin %88'ini AutoNav ile değerlendirdi (Verma et al. 2023: "AutoNav has been used to evaluate 88% of the 17.7-kilometer distance traveled during its first Mars year"); Opportunity 14 yılda toplam 2.4 km otonom (önceki rekor). Asıl darboğaz Ay'da bant genişliği değil; VIPER'da hareketli gölge/güneş penceresi.
 
**c) Boşluk:** Bizim modelimiz "Dünya'da bir kez planla" varsayımıyla örtük olarak yer-döngüsü stratejik planlayıcı; bunu açıkça söylemiyoruz.
 
**> KARAR:** Aracı "yer-tabanlı stratejik/ön-görev planlayıcı" olarak konumlandır; otonom yerel kaçınmayı kapsam dışı ilan et. (Domain, 24 Ağu)
 
#### 1.1.3 Küresel vs yerel katman [K]
 
**a) Bizde:** Sadece küresel grid planlama; yerel tehlike kaçınma yok.
 
**b) Literatür:** GESTALT (MER) rover'ı tek büyük disk olarak modeller — aşırı muhafazakar. ENav (Perseverance için geliştirildi, MER/MSL AutoNav'ın yetersizliği nedeniyle). Perseverance yerel harita: 30 m × 30 m rover merkezli. Pragyan 27 Ağustos 2023'te **3 m ilerideki 4 m çapındaki kraterden** geri çekildi (ISRO: "the Rover came across a 4-meter diameter crater positioned 3 meters ahead of its location. The Rover was commanded to retrace the path", açık) — yerel kaçınmanın somut örneği; bizim 80 m/piksel çözünürlüğümüzün altında kalan ölçek.
 
**c) Boşluk:** 80 m/piksel DEM'de 4 m'lik krater görünmez. Yerel tehlikeler bizim ölçeğimizin altında — bu bir sınır, kusur değil, ama belgelenmeli.
 
**> KARAR:** "80 m/piksel altındaki tehlikeler (küçük krater, kaya) kapsam dışıdır; yerel kaçınma katmanı gelecek iş" ifadesini raporda net yaz. (Domain, 24 Ağu)
 
#### 1.1.4 Başarısız görevler [O]
 
**b) Literatür:**
- **Spirit / "Troy":** 6 Mayıs 2009'da kabuk kırılıp yumuşak kuma saplandı; sağ ön teker 2006'dan beri, sağ arka teker 2009'da arızalı (4 çalışan teker). Kurtarma 17 Kasım 2009'da başladı, 26 Aralık 2009'da (Sol 2126) aşırı batma nedeniyle durdu. Son iletişim 22 Mart 2010; NASA 24 Mayıs 2011'de görevi sonlandırdı. Sebep: eğimli/yan yatık konum + kırık tekerler + kışın panel açısı ayarlanamaması. (NASA JPL, Scientific American, Space.com — açık)
- **Opportunity:** Haziran 2018 küresel toz fırtınasında batarya şarj edilemedi; NASA Şubat 2019'da sonlandırdı. (Space.com)
- **Yutu-2 yapışkan regolit:** Wheel lug'larına regolit topaklanması; Chang'e-4 sahasının regoliti Chang'e-3'ten daha yapışkan (yüksek aglütinat oranı). Öneri: lug yüzeyine anti-adezyon kaplama. (Science Robotics, DOI 10.1126/scirobotics.abj6660; behindtheblack özeti — açık)
**c) Boşluk:** "Neyi yanlış yaparsak rover ölür" cevabı: (1) yumuşak/düşük-tolerans regolite girme (batma), (2) enerji/gölge yanlış hesabı (şarj penceresi kaçırma), (3) yan yatık konumda kalma. Bizim maliyet fonksiyonumuz (1) ve (2)'yi kısmen ele alıyor; (3)'ü (yönelim/güneşe bakış) modellemiyor.
 
**> KARAR:** "Terminal safe-haven'da güneşe bakış/eğim" kısıtını gelecek iş listesine ekle; şimdilik kapsam dışı ilan et. (Domain, 24 Ağu)
 
#### 1.1.5 Ay günü/gece döngüsü ve güney kutbu [O]
 
**b) Literatür:** Sinodik ay 29.53 gün. Klasik ekvatoral: ~14 gün aydınlık / ~14 gün karanlık. **Güney kutbunda farklı:** eksen eğikliği 1.5°; VIPER'ın göreceği en yüksek güneş elevasyonu ~6° (NASA/VIPER Andrews 2024), tipik olarak ufuk üzerinde çok düşük; bu, arazi kaynaklı uzun ve hızlı hareket eden gölgeler üretir (NASA SVS 5228/5027). VIPER Safe Haven'lar: gölge periyodu <50 saat olan yüksek noktalar; kutupta karanlık en fazla ~4 gün (VIPER In Depth, NASA). Kaguya analizi: güney kutbunda sürekli aydınlık en fazla %86 yüzey (ResearchGate).
 
**c) Boşluk:** Bizim shadow_hours proxy'miz H_max=50 sa ile VIPER Safe Haven eşiği (<50 sa) örtüşüyor — iyi bir hizalanma. Ancak ZAMAN EKSENİ olmadığından gölgenin hareketini modelleyemiyoruz.
 
**> KARAR:** H_max=50 sa değerinin VIPER Safe Haven <50 sa eşiğiyle uyumlu olduğunu raporda vurgula (savunulabilirlik artışı). (Backend, 20 Ağu)
 
---
 
### 1.2 Fiziksel kısıtlar ve eşikler [K]
 
#### 1.2.1 Eğim limitleri [K]
 
**a) Bizde:** f_slope sigmoid, geçiş 15°, θ>25° ⇒ INF; katalogta LPR-1/LUVMI-M 25°, VIPER/Yutu-2 20°.
 
**b) Literatür:**
 
| Rover | Eğim değeri | Tür | Kaynak |
|---|---|---|---|
| Curiosity | 31° (Greenheugh, 6 Mart 2020 Sol 2696, gerçek maks tırmanış); rocker-bogie 45°'ye kadar devrilmeden güvenli | Gerçek/tasarım | NASA (açık) |
| Opportunity | 32° (2016 rekoru) | Gerçek | NASA (açık) |
| VIPER | kaynakta belirtilmemiş | Planlama kısıtı | — |
 
**Statik devrilme mi patinaj mı:** Curiosity örneğinde eğim devrilme değil **patinaj** ile sınırlanır. NASA (Space.com aktarımı): "the second of which tilted the rover 31 degrees — the most the rover has ever tilted on Mars and just shy of the now-inactive Opportunity rover's 32-degree tilt record, set in 2016… Curiosity's rocker-bogie wheel system enables it to tilt up to 45 degrees safely — but the steep drives do cause the wheels to spin in place." Yani rocker-bogie 45° statik devrilme dayanımı verir ama pratik limit patinajdır. Bu, bizim θ>25° INF kuralımızın muhafazakar (güvenli) tarafta olduğunu gösterir.
 
**c) Boşluk:** Bizim 25° hard-limit'imiz patinaj/statik devrilme ayrımı yapmıyor; tek eşik. Slip-tabanlı yumuşak kısıt yok.
 
**> KARAR:** 25° eşiğinin "patinaj-baskın muhafazakar sınır" olduğunu gerekçelendir; rocker-bogie 45° statik limitini karşılaştırma olarak ver. (Backend, 22 Ağu)
 
#### 1.2.2 Batarya SoC / rezerv [K]
 
**a) Bizde:** f_energy μ(θ), v=V_max·cos θ; SoC rezerv politikası, DoD limiti yok.
 
**b) Literatür:** Lamarre et al. (STARS Lab, IEEE Aerospace 2024, arXiv 2401.08558; Acta Astronautica 2023, arXiv 2307.16786 — açık) risk-farkında planlama: batarya deşarjı görevi öldürür; 100.000 Monte Carlo koşumu, %10 risk eşiği, rastgele arıza profilleri. Li-ion uzay bataryası DoD/düşük sıcaklık kapasite kaybı sayıları: kaynakta belirtilmemiş (bu araştırmada bulunamadı).
 
**c) Boşluk:** SoC minimum rezerv ve düşük-sıcaklık kapasite düşüşü modellenmiyor.
 
**> KARAR:** Minimum SoC rezervini "bizim varsayımımız" olarak parametrize et (örn. %20); literatür sayısı bulunamadığı için varsayım etiketi koy. (Backend, 22 Ağu)
 
#### 1.2.3 Termal survival ve zaman sabiti [K]
 
**a) Bizde:** f_thermal=0.6·S_batarya+0.4·S_elektronik; **T_iç=T_yüzey+60(soğuk)/−40(sıcak) SABİT OFSET**; termal grid sentetik.
 
**b) Literatür:** Yutu-2/Chang'e-4 RHU (Radioisotope Heater Unit) ile lunar gece ısıtması (Wikipedia/CNSA). Chang'e-4 LND RTG+RHU katkısı 5.2±0.6 µGy/saat (Zhang et al. 2020). Lumped-capacitance zaman sabiti τ=C/(hA); bu rover boyutu için yayınlanmış τ değeri: kaynakta belirtilmemiş (bu araştırmada bulunamadı).
 
**c) Boşluk:** Sabit ofset, termal ataleti (zaman sabiti) yok sayar — fiziksel olarak en zayıf varsayım. Zaman ekseni olmadığından τ zaten devreye giremez.
 
**> KARAR:** Sabit ofseti "birinci-derece kaba vekil (surrogate)" olarak etiketle; NASA-STD-7009 CAS'te bu faktörün düşük seviye alacağını kabul et. (Backend, 22 Ağu)
 
#### 1.2.4 Regolit mekaniği [O]
 
**a) Bizde:** Terramekanik yok; patinaj/batma modellenmiyor.
 
**b) Literatür:** Bekker p(z)=(k_c/b+k_φ)·z^n. Simülant kohezyon/sürtünme (Mohr-Coulomb):
 
| Simülant | Kohezyon | İçsel sürtünme açısı | Kaynak |
|---|---|---|---|
| JSC-1A | 5.2 kPa (Kobaka 2023) | 42.3° (Kobaka 2023); pik 35.4°–82.7° DEM (düşük gerilimde artıyor) | ASCE J Aerospace Eng 23(3); ResearchGate |
| LMS-1 | 3.2 kPa | 44.2° | Kobaka et al. 2023 |
| LHS-1 | yoğunluğa bağlı (Dotson 2023) | kaynakta belirtilmemiş | LPSC 2024 #1726 (açık) |
 
Vakum/yüksek sıcaklıkta sürtünme +13°, kohezyon +1.1 kPa artabilir (Bromwell/Nelson; ScienceDirect). Slip prediction: Iagnemma & Dubowsky 2004, Ishigami 2007/2008, Ding et al. değişken batma üsteli (task'ta belirtilen; bu araştırmada birincil künye doğrulanmadı — "doğrulanmalı").
 
**c) Boşluk:** Bizim modelimizde regolit taşıma kapasitesi/patinaj yok; Spirit ve Yutu-2 arızalarının temel sebebi tam da bu.
 
**> KARAR:** Terramekaniği "kapsam dışı, en önemli gelecek iş" olarak işaretle; simülant kohezyon/sürtünme tablosunu ek olarak ver. (Domain, 24 Ağu)
 
#### 1.2.5 Toz problemi [O]
 
**b) Literatür:** Apollo Lunar Dust Detector (NSSDC): ışınlanmış hücre 2.5%/yıl, kapalı hücre 4.3%/yıl güç düşüşü; açık hücre ilk 4 lunar günde **%33 toplam düşüş**. Ağustos 1972 güneş patlaması açık hücrede ~%9.5 düşüş. Apollo 15 solar hücre çıkışı toz nedeniyle 1 yılda %16 düştü (ScienceDirect). Chang'e-3 lunar dust detector: 0.83 mg/cm² birikimde kısa-devre akım kaybı %16.72.
 
**c) Boşluk:** Toz, rota seçiminden çok görev ömrü/güç bütçesi etkisi; günlük mertebe değil aylık/yıllık. Rota kriteri olarak marjinal.
 
**> KARAR:** Tozu rota kriteri YAPMA; güç bütçesi notu olarak kısa ekle. (Domain, 24 Ağu)
 
---
 
### 1.3 Haberleşme ve operasyon [K]
 
#### 1.3.1 Güney kutbunda DTE / mod ayrımı [K]
 
**b) Literatür:** Güneş elevasyonu tipik olarak çok düşük (VIPER için maks ~6°, Andrews 2024); Dünya librasyonu ±8.16° boylam, ±6.87° enlem (JPL IPN PR 42-176C, açık). En iyi güney kutbu üssünde yıllık DTE %92 (Science.gov özeti). Krater duvarı DTE gölgelemesi yüzdesi (genel): kaynakta belirtilmemiş. Otten tezi CMU-RI-TR-18-21 "denetimli teleoperasyon vs stratejik otonomi" modları: bu araştırmada birincil erişim doğrulanmadı — "doğrulanmalı."
 
**c) Boşluk:** DTE görüş penceresi rota kriterimize girmiyor (shadow proxy elevasyondan türetiliyor, Dünya görüşü değil).
 
**> KARAR:** DTE görüş faktörünü v2 için ayrı katman olarak öner; şu an gölge proxy'sinin sadece güneş gölgesi olduğunu belirt. (Domain, 24 Ağu)
 
#### 1.3.2 Röle uydusu [O]
 
**b) Literatür:** Queqiao-1 (2018, EM-L2 halo, 425 kg, 4.2 m anten, X-band lander/rover, S-band Dünya; ileri link 125 bit/s, dönüş lander 555 kbit/s, rover 285 kbit/s, Dünya'ya 10 Mbit/s — Wikipedia). Queqiao-2 (20 Mart 2024, 1200 kg, 4.2 m anten + 0.6 m Ka, frozen orbit periselene ~254-300 km, aposelene ~16.900 km, eğim ~119°, periyot ~24-26 saat; 4×256 kbps X-band ↔ lander/rover, 2 Mbps S-band ↔ Dünya; 2026 Chang'e-7 için 12 saatlik yörüngeye geçecek — SpaceNews, Gunter's, Wikipedia). AYAP röle: kamuya açık bilgi yok.
 
**> KARAR:** Röle mimarisini "bağlam" olarak sunuma koy; LunaPath röle penceresini modellemiyor — kapsam dışı. (Domain, 24 Ağu)
 
#### 1.3.3 DSN pencereleri [B]
 
**b) Literatür:** VIPER stratejik planları DSN geçişlerini/devir-teslimlerini içerir; DSN arızaları ve SEP olayları plana enjekte edilir (Ennico-Smith 2023). Pencere süreleri: kaynakta belirtilmemiş.
 
**> KARAR:** DSN penceresini kapsam dışı bırak; VIPER'ın DSN'i planına kattığını referans olarak ver. (Domain, 24 Ağu)
 
---
 
### 1.4 Radyasyon [K]
 
#### 1.4.1 Rota kriteri olarak anlamlı mı [K]
 
**NET CEVAP:** Robotik rover için radyasyon rota kriteri DEĞİL. TID birikimi gün mertebesinde rota seçimini değiştirmez (kümülatif, görev ömrü kısıtı). Literatürde radyasyonu rota kriteri yapan çalışmalar ağırlıkla insanlı senaryolar (SPE sığınma). Bizim radyasyonu dışarıda bırakma kararımız savunulabilir.
 
#### 1.4.2 SPE sığınma [K]
 
VIPER planlaması SEP (Solar Energetic Proton) olaylarını plana enjekte eder (Ennico-Smith 2023). Kümülatif doz = görev ömrü yaklaşımı standart.
 
#### 1.4.3 Veri kaynakları [O]
 
Chang'e-4 LND (Zhang et al., Sci Adv 2020, DOI 10.1126/sciadv.aaz1334, açık): Si'de ortalama toplam soğurulan doz hızı **13.2±1 µGy/saat**, nötral parçacık doz hızı 3.1±0.5 µGy/saat; 1 g/cm² eşdeğer ekran arkasında yüklü parçacık doz eşdeğeri **57.1 µSv/saat (500 mSv/yıl)**; soğurulan doz hızı 10.2 µGy/saat (89 mGy/yıl); eşdeğer doz ~60 µSv/saat (Frankfurt-New York uçuşunun 5-10 katı). LRO/CRaTER karşılaştırılabilir değerler verir. Regolit ekranlama g/cm² azaltım tablosu: kaynakta belirtilmemiş (bu araştırmada bulunamadı).
 
**> KARAR:** Radyasyonu rota kriteri YAPMA (gerekçeli); LND sayısını "neden dışarıda" gerekçesi olarak raporda göster. (Domain, 24 Ağu)
 
#### 1.4.4 Rad-hard elektronik [B]
 
RAD750 (BAE, PowerPC 750 tabanlı): 200 krad(Si) TID; 240-300 MIPS @ 133 MHz; ~5 W; 10.4M transistör; 0.25 µm; −55…+125°C; SBC 100 krad. Curiosity/Perseverance/Juno/Europa Clipper kullanır (petervis, ResearchGate, NASA Fandom). Neden derin öğrenme uzayda zor: rad-hard işlemci gücü kısıtı (birkaç yüz MIPS) + doğrulanabilirlik (ECSS kritik yazılım gereksinimleri). Bu, bizim deterministik A* seçimimizi destekler.
 
**> KARAR:** "Deterministik A* seçildi çünkü rad-hard donanımda doğrulanabilir ve düşük işlem gücüne sığar" argümanını sunuma ekle. (Domain, 24 Ağu)
 
---
 
### 1.5 Standartlar ve doğrulama [K]
 
#### 1.5.1 ECSS [K]
 
**b) Literatür:** ECSS-E-ST-40C güncel revizyon **Rev.1, 30 Nisan 2025** (ecss.nl, açık); önceki baseline 6 Mart 2009. ECSS-Q-ST-80C yazılım ürün güvencesi. Kritiklik kategorileri A/B/C/D, en kritik fonksiyona göre atanır (ECSS-Q-ST-40C Rev.1, 15 Şubat 2017; ECSS-Q-ST-30C). Kod kapsamı (ECSS-E-ST-40C §5.8.3.5b): Kategori A için statement %100, decision %100, MC/DC %100; Kategori B statement/decision %100; C/D "AM" (müşteriyle mutabık). Tailoring: Annex R (kritikliğe göre) normatiftir. shall-ifadesi, ID şeması, gerekçe ve doğrulama alanı: DRD ekleri (Annex D SRS vb.).
 
**c) Boşluk:** Bizim yazılım bir karar destek aracı (uçuş kritik değil) → muhtemelen Kategori C/D; tam tailoring yapılmadı.
 
**> KARAR:** LunaPath'i ECSS Kategori C/D olarak sınıfla (uçuş dışı karar destek); gereksinimleri shall-formatına çevir. (Backend, 23 Ağu)
 
#### 1.5.2 Doğrulama yöntemleri [K]
 
A/T/I/R (Analysis/Test/Inspection/Review of Design): her gereksinim için doğrulama yöntemi belirtilir. Bizde 9 test dosyası var, validation (ölçümle karşılaştırma) yok.
 
**> KARAR:** Her gereksinime A/T/I/R yöntemi ata; RTM'ye kolon ekle. (Backend, 23 Ağu)
 
#### 1.5.3 TRL [O]
 
NASA/ISO 16290:2013: TRL 3 = analitik ve deneysel kritik fonksiyon/kavram kanıtı (lab); TRL 4 = bileşen/breadboard lab ortamında doğrulama. TRL 3→4 için gereken: bileşenlerin lab ortamında entegre doğrulaması (arXiv 2212.03686, iso.org, NASA — açık). Biz TRL~3'üz.
 
**> KARAR:** TRL 3→4 için "sentetik yerine gerçek DEM+termal ile lab doğrulaması" kanıt gereksinimini yol haritasına yaz. (Domain, 24 Ağu)
 
#### 1.5.4 RTM [O]
 
Gereksinim izlenebilirlik matrisi: gereksinim ID, kaynak, tasarım öğesi, doğrulama yöntemi, doğrulama durumu kolonları. VIPER ve ECSS DRD'leri izlenebilirliği zorunlu kılar.
 
**> KARAR:** Basit bir RTM şablonu (ID|metin|kaynak|kod modülü|A/T/I/R|durum) oluştur. (Backend, 23 Ağu)
 
#### 1.5.5 NASA-STD-7009 Credibility Assessment Scale [K]
 
**b) Literatür (standards.nasa.gov, açık; NASA-STD-7009A 13 Temmuz 2016, w/Change 1 7 Aralık 2016; güncel Rev B 5 Mart 2024):** CAS 8 faktör, 3 kategori. Faktör isimleri standartta birebir şöyledir:
- **M&S Development:** (1) Verification, (2) Validation
- **M&S Operations:** (3) Input Pedigree, (4) Results Uncertainty, (5) Results Robustness
- **Supporting Evidence:** (6) Use History, (7) M&S Management, (8) People Qualifications
Standart tanımı (verbatim): *"This CAS consists of eight factors grouped into three categories."* İlk beş faktör (Development + Operations) her biri bir "Evidence" ve bir "Technical Review" alt-faktörü taşır.
 
Seviyeler 0-4 (Appendix B, Table 1'den):
- **0** = yetersiz kanıt (insufficient evidence)
- **1** = kavramsal/matematik model doğrulanmış, nitel tahmin, resmi olmayan dokümantasyona izlenebilir, mühendislik/bilim derecesi
- **2** = birim problem/deneysel-uzman görüşü ile uyum, resmi dokümantasyona izlenebilir, deterministik analiz
- **3** = deneysel veriyle uyum, non-deterministik analiz, önceki tahminler görev verisiyle doğrulanmış
- **4** = gerçek sistem gerçek ortamda doğrulama; ancak operasyon fazındaki sistem için mümkün
Toplam skor = 8 faktörün minimumu. Standart hangi seviyenin gerekli olduğunu dayatmaz; sadece erişilen seviyenin belirlenip raporlanmasını ister (sorumlu taraf "sufficiency threshold" belirler).
 
**Vekil (sentetik termal grid) modele uygulama:** Bizim termal ve gölge proxy'lerimiz Level 0-1 (yetersiz kanıt / nitel tahmin) alır; DEM Level 2 (LOLA'ya izlenebilir) olabilir.
 
**> KARAR:** Öz-değerlendirme CAS tablosu üret (8 faktör × seviyemiz); zayıf faktörleri (termal Level 0-1) dürüstçe raporla. (Domain+Backend, 23 Ağu)
 
---
 
### 1.6 Türkiye bağlamı [K]
 
#### 1.6.1 AYAP durumu [K]
 
**b) Literatür (AA 2023; Sabah/Sözcü/AHaber Şubat 2025 — açık):** AYAP-1: Dünya yörüngesinden milli hibrit itki (HIS) ile Ay'a **sert iniş, 2026 hedefi**; riskler tanımlandı, ön tasarım tamam, kritik tasarım (CDR) devam; yer istasyonu kiralama/fırlatma hizmeti görüşülüyor; araç aynı zamanda lander konseptine göre tasarlanıyor. AYAP-2: milli fırlatma aracıyla yumuşak iniş + rover; şu an **konsept/ön tasarım**. TUA/Sabah (8 Şubat 2025) verbatim: *"ikinci faz içinde olması planlanan gezen araç (Rover) misyonu kapsamında öğrenci takımları başta olmak üzere çeşitli ön çalışmalar yürütülüyor. Uzay Destek Sistemleri Merkezi (UZDES) ise 2027 yılında tamamlanacak."* Rover parametreleri (kütle/güç/ömür): kamuya açık bilgi yok.
 
**> KARAR:** LunaPath'i "AYAP-2 rover ön çalışmaları" bağlamına açıkça yerleştir — jüri için güçlü hizalanma argümanı. (Domain, 24 Ağu)
 
#### 1.6.2 TÜBİTAK UZAY / TUA [O]
 
Görüntü destekli seyrüsefer sistemi AYAP kapsamında geliştiriliyor (AA 2023). Spesifik yayın künyeleri: bu araştırmada doğrulanmadı — "doğrulanmalı."
 
**> KARAR:** Görüntü destekli seyrüsefer çalışmasını referans olarak an; spesifik künye "doğrulanmalı" işaretle. (Domain, 24 Ağu)
 
#### 1.6.3 Türkiye akademik yayınları [K]
 
Ay rover navigasyonu/gezegen robotiği alanında Türkiye kaynaklı spesifik yayın künyesi: bu araştırmada doğrulanmadı — "doğrulanmalı."
 
---
 
### 1.7 Değerlendirme metodolojisi [K]
 
#### 1.7.1 Benchmark protokolü [K]
 
**b) Literatür:** Baseline seçenekleri: düz A*/Dijkstra, en kısa yol, düz hat. Metrikler: yol uzunluğu, enerji, hesap süresi, ihlal sayısı, gölge maruziyeti, görev tamamlama oranı. Lamarre 2024: 100.000 Monte Carlo, rastgele arıza profili. Senaryo sayısı standardı: kaynakta net sayı yok; Monte Carlo mertebesi 10^4-10^5.
 
**> KARAR:** En az 3 baseline (düz hat, Dijkstra/düz A*, elle rota) ile karşılaştır; 6 metriği raporla. (Backend, 22 Ağu)
 
#### 1.7.2 AHP metodolojisi ve eleştirileri [K]
 
**a) Bizde:** AHP ağırlıkları [0.409, 0.259, 0.142, 0.190]; CR raporlanmıyor.
 
**b) Literatür:** CI=(λmax−n)/(n−1), CR=CI/RI; **RI(n=4)=0.90** (Saaty tablosu: n=3→0.58, n=4→0.90, n=5→1.12); CR<0.1 kabul (Saaty 1980); INCOSE n=4 için CR≤%9 önerir. Çoklu uzman: geometrik ortalama (Aczél & Saaty 1983, J Math Psychol 27:93-102). Rank reversal: Belton & Gear 1983 (Omega 11:228-230), Dyer 1990 (Manag Sci 36(3):249-258), Wang & Luo 2009. Alternatifler: TOPSIS, ELECTRE, PROMETHEE, entropi. Hibrit AHP+entropi literatürde var.
 
**> KARAR:** CR değerimizi hesapla ve raporla; RI(4)=0.90 ile göster; rank reversal'ı bilinen sınır olarak kabul et. (Backend, 20 Ağu)
 
#### 1.7.3 Duyarlılık analizi [O]
 
Triantaphyllou & Sánchez 1997 kritik kriter; OAT vs global (Sobol). "Ağırlık şu aralıkta oynasa da rota değişmiyor" için ağırlık pertürbasyonu + rota kararlılığı raporlanır.
 
**> KARAR:** AHP ağırlıklarına ±%20 OAT pertürbasyonu uygula; rota değişmezliğini göster. (Backend, 22 Ağu)
 
#### 1.7.4 Monte Carlo doğrulama [O]
 
Lamarre et al. 2024 (arXiv 2401.08558) / 2023 (arXiv 2307.16786): 100.000 koşum, %10 risk eşiği, rastgele arıza profilleri; başlangıç durumu, iniş zamanı, güç çekişi, hız randomize. Task'taki "Poisson 1/5000 m, 10 saat kurtarma" arıza modeli: bu araştırmada birincil künyede doğrulanmadı — "doğrulanmalı."
 
**> KARAR:** ≥1000 koşumlu Monte Carlo yap (başlangıç SoC, iniş zamanı, güç çekişi, hız randomize); tamamlama oranı raporla. (Backend, 23 Ağu)
 
---
 
## 3. Sayısal Kısıt Tablosu
 
| Parametre | Literatür değeri | Kaynak | Bizim değerimiz | Fark/not |
|---|---|---|---|---|
| Maks tırmanış eğimi | 31° (Curiosity gerçek) | NASA 2020 | 25° INF | Muhafazakar, güvenli |
| Rocker-bogie devrilme | 45° | NASA 2020 | — | Modellenmedi |
| Devrilme rekoru | 32° (Opportunity 2016) | NASA | 25° | — |
| Gölge safe-haven eşiği | <50 saat | Ennico-Smith 2023 | H_max=50 sa | Uyumlu |
| Kutupta maks karanlık | ~4 gün (safe haven) | VIPER In Depth | — | Zaman ekseni yok |
| Güneş elevasyonu (kutup, VIPER maks) | ~6° | NASA/VIPER Andrews 2024 | — | Modellenmedi |
| VIPER SMG | 0.8 cm/s (nom 20 cm/s) | Fong NTRS 20250004148 | V_max profil | Sürüş süresi yok |
| Perseverance AutoNav | %88 / 17.7 km | Verma et al. 2023 | — | Yerel kaçınma yok |
| Yutu-2 toplam | 1.613 km / 7+ yıl | Wikipedia/CLEP | — | — |
| Pragyan toplam | 101.4 m | Wikipedia/ISRO | — | — |
| Pragyan krater kaçınma | 4 m çap, 3 m ileri | ISRO 2023 | — | Ölçeğimizin altı |
| JSC-1A kohezyon/sürtünme | 5.2 kPa / 42.3° | Kobaka 2023 | — | Terramekanik yok |
| LMS-1 kohezyon/sürtünme | 3.2 kPa / 44.2° | Kobaka 2023 | — | — |
| Vakumda sürtünme artışı | +13°, +1.1 kPa | Bromwell/Nelson | — | — |
| Toz güç kaybı (Apollo açık hücre) | %33 / ilk 4 lunar gün | NSSDC | — | Rota kriteri değil |
| Toz güç kaybı (Apollo 15) | %16 / yıl | ScienceDirect | — | — |
| Chang'e-3 akım kaybı | %16.72 @ 0.83 mg/cm² | ScienceDirect | — | — |
| LND doz hızı (Si) | 13.2±1 µGy/saat | Zhang 2020 | — | Rota kriteri değil |
| LND nötral doz hızı | 3.1±0.5 µGy/saat | Zhang 2020 | — | — |
| LND doz eşdeğeri | 57.1 µSv/saat (500 mSv/yıl) | Zhang 2020 | — | — |
| Ay gidiş-dönüş komut gecikmesi | 6–40+ s | NTRS 20170009822 | — | Otonomi yok |
| RAD750 | 200 krad, 240-300 MIPS, ~5 W | BAE/petervis | — | Deterministik seçim gerekçesi |
| RI (n=4) | 0.90 | Saaty | AHP CR hesaplanmalı | CR raporlanmıyor |
| AHP ağırlıkları | — | — | [0.409,0.259,0.142,0.190] | Bizim |
| Queqiao-2 | 1200 kg, 4.2 m, ~24-26 sa frozen | Wikipedia/SpaceNews | — | Röle modellenmedi |
| Sinodik ay | 29.53 gün | genel | — | Zaman ekseni yok |
| DTE (en iyi kutup üssü) | %92/yıl | Science.gov | — | DTE katmanı yok |
 
*Boş hücreler kaynakta belirtilmemiş olanlar veya bizim modelimizde bulunmayanlardır.*
 
---
 
## 4. Çelişki Haritası
 
| Konu | Çelişki | Değerlendirme |
|---|---|---|
| Eğim limiti | Curiosity gerçek 31°, tasarım 45°, bizim 25° | Farklı roverlar farklı limit; 25° muhafazakar — çelişki değil, seçim |
| Kutup döngüsü | "14/14 gün" (ekvatoral) vs "arazi kaynaklı hızlı gölge" (kutup) | Kutupta klasik döngü YANLIŞ; arazi gölgesi baskın — literatür ekvator/kutup ayrımı yapmalı |
| JSC-1A sürtünme | Üretici vs Kobaka 2023 farklı; DEM'de 35-82° aralık | Ölçüm koşuluna (ön-yük, vakum, yoğunluk) bağlı; tek sayı yok |
| Yutu-2 mesafe | Kaynaklar 1.455 km (2023) / 1.613 km (2024+) | Zamanla artmış; son ~1.613 km |
| Otonomi darboğazı | "Bant genişliği" vs "gölge/güneş penceresi" | Ay kutbunda gölge/güneş baskın (bizim modelle uyumlu) |
| Bizim termal ofset | Literatür zaman sabitli; biz sabit ofset | Bizim en zayıf noktamız — kabul ediliyor |
 
---
 
## 5. Biz Nerede Savunmasızız (ZORUNLU)
 
| # | Risk | Çözüm (25 gün içinde) | Maliyet |
|---|---|---|---|
| 1 | **Termal sabit ofset fiziksel olarak savunulamaz** — jüri "τ nerede?" derse | Sabit ofseti "birinci-derece kaba vekil" etiketle; CAS'te Level 0-1 dürüstçe raporla; sınırlama slaytı | 0.5 gün, Backend |
| 2 | **Zaman ekseni yok** — kutupta gölge hareketi görevin özü, biz statik | "Stratejik ön-görev snapshot planlayıcı" olarak konumlandır; zaman ekseni "gelecek iş #1" | 0.5 gün, Domain |
| 3 | **Sentetik termal grid** — gerçek veri yok | Termal gridin elevasyondan lineer türetildiğini açıkça yaz; gerçek LOLA/Diviner termal öner | 0.5 gün, Backend |
| 4 | **Validation yok** — 9 test var ama ölçümle karşılaştırma yok | Baseline benchmark + Monte Carlo + duyarlılık = "test var, validation yol haritasında" | 3 gün, Backend |
| 5 | **AHP CR raporlanmıyor** — tutarlılık kanıtı yok | CR hesapla, RI(4)=0.90 ile göster; CR<0.1 doğrula | 0.5 gün, Backend |
| 6 | **Rank reversal** — AHP bilinen zafiyet | Belton&Gear/Dyer'ı kabul et; hassasiyet analizi ile "rota değişmiyor" göster | 1 gün, Backend |
| 7 | **80 m/piksel yerel tehlikeleri kaçırır** (Pragyan 4 m krater) | Ölçek sınırını açıkça belgele; yerel kaçınma kapsam dışı | 0.25 gün, Domain |
| 8 | **Terramekanik yok** — Spirit/Yutu-2 ölüm sebebi | Simülant tablosu ver; "en önemli gelecek iş" işaretle | 0.5 gün, Domain |
| 9 | **shadow_hours proxy** elevasyondan türetiliyor, gerçek ışıklandırma simülasyonu değil | Proxy olduğunu belirt; NASA SVS/LOLA ray-tracing öner | 0.25 gün, Backend |
 
### Savunmasız OLMADIĞIMIZ yerler
- **Algoritma seçimi:** Deterministik A* rad-hard donanımda doğrulanabilir + düşük MIPS'e sığar (RAD750 240-300 MIPS) — derin öğrenmeden üstün gerekçe.
- **Gölge/enerji odağı:** VIPER'ın gerçek darboğazı (gölge/güneş penceresi, SMG 0.8 cm/s) ile birebir hizalı; H_max=50 sa VIPER safe-haven <50 sa eşiğiyle uyumlu.
- **Eğim eşiği:** 25° INF, Curiosity gerçek 31° ve rocker-bogie 45°'ye göre muhafazakar/güvenli.
- **Radyasyonu dışarıda bırakma:** Robotik rover için doğru karar (TID kümülatif, rota kriteri değil).
- **Çok kriterli yapı:** VIPER'ın çok-faktörlü planlaması (odometri, gölge süresi, DSN, ISR) ile kavramsal olarak aynı ailede.
- **Türkiye hizası:** AYAP-2 rover ön çalışmaları bağlamında doğrudan ilgili.
---
 
## 6. Yapılabilir / Riskli / Yapılamaz
 
### Yapılabilir (25 gün, 5 kişi)
| İş | Gerekçe |
|---|---|
| AHP CR hesabı + RI(4)=0.90 | Basit hesap, mevcut ağırlıklar |
| ±%20 OAT duyarlılık analizi | Mevcut planlayıcıyı tekrar çalıştırma |
| 3 baseline benchmark | Düz hat/Dijkstra/elle rota kolay |
| Monte Carlo ≥1000 koşum | Randomizasyon mevcut koda eklenebilir |
| CAS öz-değerlendirme tablosu | Dokümantasyon işi |
| RTM + shall-format gereksinimler | Dokümantasyon işi |
| Sınırlama slaytları (termal/zaman/ölçek) | Dürüst kapsam beyanı |
 
### Riskli
| İş | Gerekçe/risk |
|---|---|
| Termal lumped-capacitance (τ) ekleme | Zaman ekseni gerektirir; 25 günde yarım kalabilir |
| Gerçek LOLA/Diviner termal entegrasyonu | Veri erişim + format riski |
| Basit slip/patinaj yumuşak kısıtı | Terramekanik parametre kalibrasyonu zor |
| DTE görüş faktörü katmanı | Libration/horizon mask hesabı zaman alır |
 
### Yapılamaz (BOŞ OLAMAZ)
| İş | Gerekçe |
|---|---|
| Zaman-bağımlı gölge dinamiği simülasyonu | Mimari statik snapshot; 25 günde yeniden yazılamaz |
| Otonom yerel tehlike kaçınma | Algısal katman/sensör modeli yok; kapsam dışı |
| Gerçek ölçümle validation | Uçuş/saha verisi erişimi yok |
| Tam terramekanik (Bekker/Wong-Reece) entegrasyonu | Parametre kalibrasyonu + test yok |
| Haberleşme/röle penceresi modelleme | Yörünge propagasyonu gerekir; kapsam dışı |
| ECSS Kategori A/B tam uyum | Uçuş kritik değil + kaynak yetersiz |
 
---
 
## 7. Aksiyon Listesi
 
| # | İş | Kim | Süre | Öncelik |
|---|---|---|---|---|
| 1 | AHP CR hesabı + RI(4)=0.90 raporu | Backend | 0.5 g | Yüksek |
| 2 | ±%20 OAT duyarlılık analizi | Backend | 1 g | Yüksek |
| 3 | 3 baseline benchmark + 6 metrik | Backend | 2 g | Yüksek |
| 4 | Monte Carlo ≥1000 koşum | Backend | 2 g | Yüksek |
| 5 | CAS 8-faktör öz-değerlendirme tablosu | Domain+Backend | 1 g | Yüksek |
| 6 | RTM + shall-format gereksinim seti | Backend | 1.5 g | Orta |
| 7 | Sınırlama/kapsam slaytları (termal/zaman/ölçek/terramekanik) | Domain | 1 g | Yüksek |
| 8 | Türkiye/AYAP-2 hiza slaytı | Domain | 0.5 g | Orta |
| 9 | Simülant kohezyon/sürtünme + toz + LND tabloları (ek) | Domain | 0.5 g | Orta |
| 10 | Frontend: benchmark/duyarlılık görselleştirme | Frontend | 3 g | Yüksek |
| 11 | Frontend: rota + gölge + eğim katman görselleri | Frontend | 2 g | Orta |
| 12 | ECSS C/D sınıflama + tailoring notu | Backend | 0.5 g | Düşük |
 
---
 
## 8. Diğer Ekiplere Kontrat Talepleri
 
1. **Backend → Domain (18 Ağu):** Mevcut AHP matrisini ham haliyle ver ki CR hesaplanabilsin.
2. **Backend → Frontend (20 Ağu):** Benchmark çıktı formatını (JSON: metrik→değer) sabitle.
3. **Domain → Backend (19 Ağu):** H_max=50 sa ve 25° eşiklerinin gerekçe metnini teslim et.
4. **Frontend → Backend (22 Ağu):** Monte Carlo sonuç şemasını (koşum→tamamlama/enerji) al.
5. **Domain → tüm ekip (24 Ağu, özellik dondurma):** Kapsam sınırı beyanı (kapsam dışı listesi) kesinleşsin.
6. **Backend → Domain (23 Ağu):** CAS öz-değerlendirme için her model bileşeninin veri kökeni (DEM=LOLA, termal=sentetik) listesini teslim et.
---
 
## 9. Kaynakça (kategorili)
 
**Yöntem / Standart (açık erişim):**
- ECSS-E-ST-40C Rev.1, 30 Nisan 2025, Space engineering – Software, ecss.nl
- ECSS-Q-ST-40C Rev.1 (15 Şubat 2017), ECSS-Q-ST-80C, ECSS-Q-ST-30C, ecss.nl
- NASA-STD-7009A w/Change 1 (2016), Rev B (5 Mart 2024), Standard for Models and Simulations, standards.nasa.gov
- ISO 16290:2013, Technology Readiness Levels, iso.org
- Saaty T.L. (1980) AHP; Aczél & Saaty (1983) J Math Psychol 27:93-102; Belton & Gear (1983) Omega 11:228-230; Dyer (1990) Manag Sci 36(3):249-258; Wang & Luo (2009)
- Lamarre et al. (2024) IEEE Aerospace, arXiv 2401.08558; (2023) Acta Astronautica, arXiv 2307.16786 (açık)
**Veri (açık erişim):**
- Zhang et al. (2020) First measurements of radiation dose on lunar surface, Sci Adv 6:eaaz1334, DOI 10.1126/sciadv.aaz1334
- Chang'e-4 LND: Wimmer-Schweingruber et al. (2020) Space Sci Rev 216:104, arXiv 2001.11028
- Apollo Lunar Dust Detector, NASA NSSDC (açık)
- Kaguya/LOLA illumination: JPL IPN PR 42-176C (açık); NASA SVS 5027/5228
- JSC-1A/LMS-1/LHS-1: Kobaka et al. (2023); ASCE J Aerospace Eng 23(3); LPSC 2024 #1726 (açık)
**Kod / Görev (açık erişim NTRS):**
- Ennico-Smith et al. VIPER Traverse Planning, NTRS 20230004239
- Fong, VIPER Software: Rover, Planning, and Ops, NTRS 20240013292 / 20250004148
- Trimble, Key Differences Moon vs Mars, NTRS 20170009822
- Shirley et al. VIPER Traverse Planning, LPSC 2022 #2874
- Verma et al. (2023) Perseverance autonomy, Sci Robotics, DOI 10.1126/scirobotics.adi3099
- Yutu-2: Science Robotics DOI 10.1126/scirobotics.abj6660
**Kurum:**
- TUA/AA (2023) AYAP; Sabah/Sözcü/AHaber (Şubat 2025) AYAP-1 sert iniş 2026
- ISRO (Ağustos 2023) Pragyan krater kaçınma
- CNSA/Queqiao: SpaceNews, Gunter's Space Page, Wikipedia
---
 
## TL;DR
- **LunaPath'in temel yönelimi doğru:** Ay güney kutbunda gerçek darboğaz (hareketli gölge + güneş enerjisi + haberleşme penceresi; VIPER SMG 0.8 cm/s) tam da bizim gölge/enerji/termal katmanlarımızın hedefidir; 25° eğim eşiği (Curiosity gerçek 31°, rocker-bogie 45°'ye göre) muhafazakar-güvenli ve radyasyonu rota kriteri yapmama kararı savunulabilir.
- **En kritik üç zayıflık, 25 günde kapatılmalı olan dokümantasyon/analiz açıklarıdır:** (1) termal SABİT OFSET fiziksel olarak savunulamaz — "kaba vekil" etiketle ve NASA-STD-7009 CAS'te Level 0-1 dürüstçe raporla; (2) ZAMAN EKSENİ yok — aracı "stratejik ön-görev snapshot planlayıcı" olarak konumlandır; (3) validation yok ve AHP CR raporlanmıyor — CR (RI(4)=0.90 ile), ±%20 duyarlılık, ≥1000 koşumlu Monte Carlo ve 3 baseline benchmark ekle.
- **Kazanma argümanı hizalanmadır:** Deterministik A* seçimi rad-hard donanımda (RAD750 240-300 MIPS) doğrulanabilirlik gerekçesiyle savunulur; H_max=50 sa VIPER safe-haven <50 sa eşiğiyle örtüşür; ve proje doğrudan AYAP-2 rover ön çalışmaları (öğrenci takımları, TUA/Sabah Şubat 2025) bağlamına oturur — kapsam sınırlarını (yerel kaçınma, terramekanik, zaman dinamiği kapsam dışı) dürüstçe beyan et.
*Bu belge bir karar kaydıdır. Değişen her karar buraya işlenmeli, tarih düşülmelidir.*