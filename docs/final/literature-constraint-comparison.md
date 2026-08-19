# Ay Ortamı Modelleme ve Kısıtlar — Literatür Karşılaştırma Raporu
 
**Ekip:** FEZA / LunaPath
**Hedef:** TUA Astro Hackathon Ulusal Final, 7–13 Eylül 2026
**Rapor tarihi:** 12 Ağustos 2026
**Soru:** Gerçek çalışmalar ay ortamını nasıl simüle etmiş, hangi kısıtları uygulamış, biz nerede duruyoruz?
 
---
 
## 0. Neden bu rapor
 
Jüri karşısında en tehlikeli soru şu: *"Bu sayıları nereden aldınız?"*
 
Kendi dokümanımızda 25 bin karakterlik iddia var. Her sayının ya bir kaynağı olmalı ya da "bu bizim varsayımımız" etiketi. Bu rapor, literatürün hangi sayıyı hangi gerekçeyle kullandığını çıkarır ve bizim değerlerimizi onlarla karşılaştırır.
 
**Ana bulgu peşinen:** Literatürde ne yaptığımızın *yanlış* olduğunu gösteren bir şey yok. Ama üç yerde savunmasız duruyoruz ve bunlar §6'da listeli.
 
---
 
## 1. Karşılaştırma tablosu — bir bakışta
 
| Çalışma | Yıl | Durum uzayı | Algoritma | Çözünürlük | Eğim limiti | Enerji modeli | Aydınlanma kaynağı |
|---|---|---|---|---|---|---|---|
| **TEMPEST** (CMU) | 2002–06 | (x, y, t, batarya) | ISE / geri arama | değişken | — | Güneş panelli, tam güç modeli | Analitik güneş konumu |
| **Otten** (CMU) | 2015–18 | (x, y, t) | Bağlı bileşen analizi | LOLA | Geçilebilir eğim | Sürekli aydınlanma kısıtı | LOLA ufuk maskesi |
| **Cunningham** (CMU) | 2017 | (x, y, t) | İleri-zaman A* | LOLA | — | Enerji-farkında | Ön-hesaplı |
| **Lamarre** (UofT/JPL) | 2024 | (x, y, t, SoC, hedef) | Risk-sınırlı TEMPEST + AO | **240 m** | **20°** | Detaylı tablo (§3) | JPL Cabeus veri seti, saatlik |
| **Richter** (ETH) | 2024 | (x, y) | Çok katmanlı A* | LRO türevi | Bacaklı robot | Katman ağırlıkları | Statik |
| **VIPER** (NASA) | 2022–25 | Operasyonel | Stratejik + taktik | 5/10/20 m | **15°** | Güneş + Li-ion | Ufuk yöntemi, 2 saatlik |
| **LunaPath (biz)** | 2026 | (x, y, t) | Zaman-genişletilmiş A* | 20 m | **25°** | %20 SoC rezervi | *Şu an vekil formül* |
 
Boş hücreler kaynakta açıkça belirtilmemiş olanlar; uydurmadım.
 
---
 
## 2. Ay ortamı literatürde nasıl modelleniyor
 
### 2.1 Aydınlanma — herkesin aynı yöntemi kullandığı tek konu
 
Literatürde **fiili standart tek bir yöntem var: ufuk yöntemi (horizon method)**, Mazarico ve ark. (2011).
 
Yöntem şu: her pikselden görünen ufuk yüksekliği, azimutta 0.5° aralıklı 720 görüş hattı boyunca hesaplanıyor. Sonra Güneş'in o andaki konumu bu ufuk profiliyle karşılaştırılıyor.
 
Mazarico'nun kendi doğrulaması dikkat çekici: model çıktısı üç LROC WAC güney kutup mozaiğiyle karşılaştırılmış, uyum görsel olarak mükemmel bulunmuş ve buradan üç sonuç çıkarılmış — 240 m topografya çözünürlüğü yeterli, topografya modeli kutupsal aydınlanmayı doğru tahmin edebiliyor ve ufuk yöntemine güvenle kullanılabilir.
 
**240 m'nin yeterli olduğu bizzat yöntemin yazarı tarafından doğrulanmış durumda.** Bu bizim için önemli: aydınlanma katmanının 20 m olmaması bir eksiklik değil.
 
Sonraki çalışmalar iç içe grid yaklaşımı getirmiş: <cite index="107-1">5 m/px LDEM 5 km'den yakın mesafeler için, 80 m/px orijinal LDEM 5–100 km arası, 240 m/px orijinal LDEM daha uzak mesafeler için</cite> — çünkü ufuk çizgisini belirleyen dağ 100 km uzakta olabilir.
 
Bir de incelik var: <cite index="111-1">Güneş nokta kaynak değil disk olarak ele alındığında, aydınlanma haritasındaki her piksel değeri görünen güneş diskinin oranını temsil ediyor; bu haritalar birçok zaman adımı boyunca üst üste konularak her piksel için aydınlanma süresi ve şiddetini tanımlayan tematik haritalar üretilebiliyor.</cite>
 
VIPER de aynı yolu izlemiş: <cite index="177-1">zaman serisi aydınlanma ve haberleşme haritaları üretilirken ufuk yöntemi (Garrick-Bethell ve ark. 2005; Mazarico ve ark. 2011) kullanılmış.</cite>
 
> **Bizim için sonuç:** Ufuk yöntemi tartışmasız standart. Backend'in bunu spiceypy + LOLA ile uygulaması "makul bir seçim" değil, **literatürün tek yolu.** Sunumda böyle söylenmeli.
 
### 2.2 Topografya — hangi çözünürlük nerede
 
VIPER'ın site analizi bizim §2.2'deki Cesium halkalarıyla birebir örtüşüyor: <cite index="177-1">LOLA gridli veri kayıtları mutlak enlem 80°'nin ötesinde 20 m, 85°'nin ötesinde 10 m, 87.5°'nin ötesinde 5 m grid aralığına sahip.</cite>
 
Ve neden bu ölçekler seçilmiş: <cite index="177-1">VIPER görev tasarımı, esas olarak roverın boyutlarıyla (yaklaşık 1.5 m × 1.5 m) ve beklenen iniş aracıyla (ayaklar arası 5 m) ilgili çeşitli uzunluk ölçeklerinde topografik bilgi gerektirdi; aydınlanma ve haberleşme haritaları için ufuk hesabı ise çok daha büyük alanlar üzerinde ama daha uzun ölçeklerde topografik bilgi gerektirdi.</cite>
 
**Bu, iki katmanlı mimarimizin literatürdeki tam karşılığı:** yerel geçilebilirlik rover boyutuyla ölçeklenir, küresel planlama ufuk ölçeğiyle. Aynı harita ikisine birden hizmet etmez.
 
### 2.3 Kutup geometrisi — asıl zorluk burada
 
VIPER'ın Artemis bağlamındaki makalesi problemi net koyuyor: <cite index="176-1">Ay kutuplarına yakın bölgelerde ne Güneş ne de Dünya ufkun çok üzerine çıkıyor; bu da yerel topografik özelliklerin yarattığı geniş ve hızlı hareket eden aydınlanma ve Dünya-ile-doğrudan-haberleşme (DTE) gölgelerine yol açıyor. DSN'e bağımlı olan VIPER, aktif operasyon dönemlerinde DTE haberleşme gölgelerinin dışında kalmak zorunda. Güneş enerjili olduğu için — enerji depolaması lityum-iyon bataryayla — PSR içi operasyon dönemleri hariç gölgede geçirdiği süreyi en aza indirmesi gerekiyor. PSR operasyonları, roverın uygun bir güneşli şarj konumuna dönmeden bataryası bitmeyecek şekilde dikkatle planlanıp zamanlanmalı.</cite>
 
Buradaki üç kısıt bizim üçümüzle aynı: **aydınlanma, DTE görüş hattı, batarya.** Bunu görmek rahatlatıcı — kategori olarak doğru problemleri çözüyoruz.
 
### 2.4 Ne modellenmemiş — dürüstlük için önemli
 
Literatürün ciddi bir kısmı **basitleştirme yaptığını açıkça yazıyor.** Lamarre ve ark. (2024) bunun iyi bir örneği:
 
- <cite index="167-1">Kayma (slip) ve yüzey kaya yoğunluğu (CFA) modelleri bu değerler hesaplanırken kolayca dahil edilebilir olsa da, basitlik adına sabit sürüş hızı ve güç modeli kullanılmış; sürüş süresi ve enerji maliyetleri yalnızca komşu grid hücreleri arasındaki fiziksel mesafeye bağlı.</cite>
- <cite index="167-1">Güneş gücünü tahmin etmek için roverın her zaman Güneş'e mükemmel yönelmiş sabit alanlı güneş paneli koruduğu varsayılmış — pan-tilt platformuna monte panelleri taklit ederek. Tam güneş diski göründüğünde 1367 W/m² sabit ışınım kullanılmış; daha karmaşık güç üretim modelleri gelecek çalışmaya bırakılmış.</cite>
**Bu, JPL ortaklı, IEEE Aerospace'te yayınlanmış bir çalışma.** Ve regolit mekaniğini modellemiyor, sabit hız kullanıyor, panel yönelimini idealize ediyor.
 
> **Bizim için sonuç:** "Regolit/sürtünme hiç modellenmemiş" maddemiz bir zayıflık değil, **alanın normu.** Farkı yaratan modellememek değil, modellemediğini söylememek. Söyleyeceğiz.
 
---
 
## 3. Sayısal kısıtlar — literatür ne kullanmış
 
### 3.1 Eğim limiti
 
| Kaynak | Değer | Not |
|---|---|---|
| VIPER (NASA Ames) | **15°** | <cite index="180-1">15 derece eğim limiti; 10 cm engelleri aşabiliyor</cite> |
| Lamarre ve ark. 2024 | **20°** | <cite index="167-1">Eğim büyüklüğü 20 dereceden fazla olan hücrelerden kaçınılıyor</cite> |
| MER statik devrilme | 45° | Dokümanımızdan |
| Curiosity gerçek max | 31° | Greenheugh Pediment, 2020 |
| **LunaPath** | **25°** | ⚠️ Literatürün üstünde |
 
**25°'yi savunmak zor değil ama savunmak gerekiyor.** İki geçerli yol:
 
1. **Rover profiline bağla.** LPR-1 profilimiz VIPER türevi ise 15° kullanmalıyız. Farklı bir profilse gerekçe yaz.
2. **Duyarlılık analizine çevir.** 15/20/25° için rota nasıl değişiyor, göster. "Bu bir parametre, sabit değil" demek "25 doğrudur" demekten çok daha güçlü.
**İkinci yolu öneriyorum.** Hem literatürle çelişmezsin hem parametrik düşündüğünü göstermiş olursun. Frontend tarafında bu zaten bir kaydıraç.
 
### 3.2 Batarya / SoC — literatürdeki en somut tablo
 
Lamarre ve ark. (2024) iki senaryo için tam parametre seti veriyor. Bu, bulabildiğim **en kullanışlı tek tablo:**
 
**Orta ölçekli görev roveri:** <cite index="167-1">Güneş paneli alanı 1.5 m², panel verimi %30, sürüş hızı 0.05 m/s, sürüş güç çekişi 110 W, arıza giderme güç çekişi 80 W, yerinde bekleme güç çekişi 80 W, hibernasyon güç çekişi 30 W, batarya kapasitesi 7.000 Wh.</cite>
 
**Büyük ölçekli görev roveri:** <cite index="171-1">Güneş paneli alanı 1.5 m², panel verimi %30, sürüş hızı 0.1 m/s, sürüş güç çekişi 300 W, arıza giderme 50 W, bekleme 40 W, hibernasyon 30 W, batarya kapasitesi 30.000 Wh.</cite>
 
Dikkat edilecek üç şey:
 
**a) Güç modları gerçekten ayrı.** Sürüş / bekleme / hibernasyon üç farklı değer. Bizim dokümanımızda bu ayrım [K] olarak soruluyordu — cevap evet, ayrı olmalı ve hibernasyon en düşük (30 W).
 
**b) Minimum SoC yüzde değil, mutlak değer olarak tanımlanmış.** <cite index="167-1">Enerji aralığı 500 Wh–7.000 Wh</cite> — yani alt sınır kapasitenin ~%7'si. Bizim %20 varsayımımız bundan muhafazakâr. Bu iyi, ama nedenini bilerek söylemeliyiz.
 
**c) Güvenlik kriteri sadece SoC değil, "hibernasyonla hayatta kalabilme".** Büyük ölçekli senaryoda: <cite index="171-1">Rover, bir sonraki ay gününe kadar yerinde hibernasyona girip 26 Eylül 2029 17:33'e kadar %50 SoC'ye (15.000 Wh) ulaşabilmeli. Bu, traversi başarıyla ve güvenle bitirmek için roverın ardından gelen ay gecesinden sağ çıkacak kadar enerjiye sahip olması gerektiği anlamına geliyor.</cite>
 
**Bu, bizim modelimizde olmayan bir kısıt ve eklemesi ucuz.** "Rota bitti" ≠ "görev başarılı". Rover, rotayı bitirdiği yerde ay gecesini atlatabilmeli. Tek satırlık bir son-durum kontrolü, ama görev tanımını tamamen değiştiriyor.
 
### 3.3 Güvenli bölge (safe haven) kavramı
 
Literatürde bizim modelimizde hiç olmayan bir yapı var:
 
<cite index="164-1">H ⊂ C, roverın traversini bitirmesine izin verilen "güvenli sığınaklar" kümesi. Güneş enerjili mobilite bağlamında güvenli sığınaklar genellikle ortalama olarak yüksek miktarda güneş ışığı alan konumlar. Bir sığınağa vardığında rover, ancak ve ancak önceden belirlenmiş bir t̄ zamanına kadar yerinde hibernasyona girip minimum ¯b şarj seviyesine ulaşabiliyorsa 'güvenli' sayılıyor.</cite>
 
Ve görev başarısızlığının tanımı: <cite index="163-1">Rover traversini önceden belirlenmiş güvenli bölgenin dışında, belirtilen zaman sınırının ötesinde veya uzun vadeli hayatta kalmayı garantileyecek enerji olmadan sonlandırırsa görev başarısızlığı gerçekleşir.</cite>
 
> **Bu, benchmark protokolümüz için doğrudan kullanılabilir.** Dokümanda "başarı/başarısızlık tanımı (sert kısıt ihlali)" diye bir [K] madde var. İşte hakemli, alıntılanabilir bir tanım.
 
### 3.4 Zaman ve enerji ayrıklaştırma
 
Sürekli değişkenleri A*'a sokarken sınıflara bölmek gerekiyor. Literatürdeki değerler:
 
| Ölçek | Zaman sınıfı | Enerji sınıfı |
|---|---|---|
| Orta ölçek | <cite index="169-1">1.800 s (30 dk)</cite> | <cite index="169-1">150 Wh</cite> |
| Büyük ölçek | <cite index="173-1">3.600 s (1 saat)</cite> | <cite index="173-1">250 Wh</cite> |
 
**Bizim 6 saatlik kovamız çok kaba.** Literatür 30 dk – 1 saat kullanıyor; biz 6–12 kat daha iri dilimliyoruz.
 
Bu savunulabilir mi? Evet, ama şöyle: *"Kutup aydınlanması saat mertebesinde değişiyor, biz stratejik ölçekte planlıyoruz."* Yine de **1 saatlik dilime inmeyi denemeye değer** — durum uzayı 6 katına çıkar ama literatürle hizalanırsın ve muhtemelen daha iyi rotalar bulursun. Backend'e sorulacak bir soru.
 
Bir de budama stratejisi belirtilmiş: <cite index="169-1">Çözünürlük-eşdeğerlik budaması: düşük enerji daha iyi; durum baskınlığı budaması: yok.</cite> Yani iki yakın durum aynı sınıfa düşerse düşük enerji gerektiren tutulmuş.
 
### 3.5 Hareket modeli
 
<cite index="167-1">Hareket, yörünge haritalarındaki piksel gridine göre sekiz-komşulu grid desenine kısıtlanmış.</cite>
 
8-komşu standart. Theta*/açı-kısıtsız yaklaşımlar (CAKIN'in kullandığı) bunu aşmaya çalışıyor ama küresel planlamada 8-komşu hâlâ yaygın.
 
<cite index="164-1">Bekleme aksiyonu da var: rover yerinde önceden belirlenmiş bir δt_wait süresi bekleyebiliyor</cite> — orta ölçekte 30 dk, büyük ölçekte 1 saat. **"Bekle" aksiyonumuz literatürde var, doğru tasarım.**
 
---
 
## 4. Kısıtlar nasıl uygulanıyor — sert mi, maliyet mi?
 
Bu, dokümandaki "MRU (Mission Risk Unit) savunulabilir mi" sorusunun cevabı.
 
**Literatürde net bir ayrım var:**
 
**Sert kısıt (hard constraint) olarak uygulananlar:**
- Eğim limiti — <cite index="167-1">20° üstü hücrelerden kaçınılıyor</cite>, maliyet eklenmiyor, hücre yok sayılıyor
- Minimum SoC — operasyonel aralığın dışına çıkmak doğrudan görev başarısızlığı
- Zaman penceresi — <cite index="164-1">T = [t_min, t_max] aralığı, görevin gerçekleşebileceği en erken ve en geç zamanlar</cite>
- DTE görüş hattı — VIPER'da aktif operasyon sırasında zorunlu
**Maliyet fonksiyonuna giren:**
- Mesafe / süre
- Enerji tüketimi
- Bilimsel değer (ödül olarak)
**Richter ve ark. (2024) farklı bir yol izlemiş** ve bizimkine en yakın olan bu: <cite index="192-1">A* algoritmasına dayalı, farklı maliyet hedefleri için harita verisinin birden fazla katmanını ayrı ayrı değerlendirebilen küresel bir planlayıcı; hedefler arasında ağırlıklar tanımlanıyor ve bunlar çeşitli optimal rotalar elde etmek için uyarlanabiliyor. Bu rotaların en iyisini bulmak için istatistiksel rota analizi aracı sunuluyor.</cite>
 
Ve sonuç: <cite index="192-1">Optimize edilmiş rotalar, aynı alandaki elle planlanmış rotalara kıyasla başarısızlık riskini önemli ölçüde azaltırken daha fazla bilimsel değer üretiyor.</cite>
 
> **Bizim MRU yaklaşımımız Richter'in ağırlıklı çok katmanlı A*'ıyla aynı ailede.** Hakemli ve iSpaRo 2024'te yayınlanmış. Savunulabilir.
>
> **Ama kritik kural:** Eğim ve SoC gibi güvenlik kısıtları **maliyete gömülmemeli, sert kısıt olmalı.** Ağırlıkla oynanan bir eğim limiti, yeterince yüksek ödül karşısında ihlal edilebilir hale gelir. Literatürde hiç kimse bunu yapmıyor. Kodumuzda bu ayrım net mi — **kontrol edilmeli.**
 
---
 
## 5. Belirsizlik ve risk — literatürün gittiği yer
 
Alanın 2024 sonrası yöneldiği yer bu ve bizde hiç yok.
 
Lamarre ve ark. problemi şöyle kuruyor: <cite index="161-1">Mevcut yaklaşımlar, traversi geçici olarak geciktirebilecek tekrarlayan arızalar gibi rastgele bozulmaları öngörülü şekilde hesaba katmıyor. Bu makalede, rastgele arızalardan etkilenen güneş enerjili bir rover tarafından PSR keşfi için şans-kısıtlı bir görev seviyesi planlama problemi formüle ediliyor. Amaç, görev başarısızlığı olasılığına bir üst sınır saygı gösterirken mümkün olduğunca çok bilimsel ilgi noktası ziyaret eden bir politika bulmak.</cite>
 
Arıza modeli somut: <cite index="167-1">Ortalama arıza oranı sürülen her 5.000 metrede 1, arıza kurtarma süresi 36.000 s (10 saat).</cite> Poisson süreci olarak modellenmiş.
 
Ve neden bu önemli: <cite index="161-1">PSR keşfederken bir arızanın öldürücülüğü, gerçekleştiği yere ve zamana bağlı. İyi güneşlenen bir alanda gerçekleşen arıza tehlike oluşturmayabilir. Gölgede gerçekleşen benzer bir arıza ise, gecikme yakın gelecekte kritik bir güneş şarj olayının gerçekleşmesini engellerse roverın kaybına yol açabilir. Stokastik bozulma varlığında deterministik güvenlik kısıtları rover güvenliğini garanti edemez.</cite>
 
Sonuç sayısal olarak çarpıcı — risk-agnostik plan ile risk-sınırlı plan karşılaştırması:
 
| | Risk-agnostik | Risk-sınırlı (%2 sınır) |
|---|---|---|
| Mesafe | <cite index="168-1">7.453 m</cite> | <cite index="168-1">7.933 m</cite> |
| Süre | <cite index="168-1">53.4 saat</cite> | <cite index="169-1">55.9 saat</cite> |
| Maks. başarısızlık olasılığı | <cite index="168-1">%23</cite> | <cite index="169-1">%1.7</cite> |
 
**Yarım kilometre ve iki saat daha uzun bir rota, başarısızlık riskini %23'ten %1.7'ye düşürüyor.**
 
> **Bu tek tablo, bütün projemizin tezini kanıtlıyor:** en kısa rota en iyi rota değildir. Sunuma koy. Kaynak göstererek koy.
 
10.000 Monte Carlo denemesiyle doğrulanmış — bizim dokümandaki Monte Carlo [O] maddesi için hem yöntem hem ölçek referansı.
 
**Bize ne katıyor:** Şans-kısıtlı optimizasyonu 26 günde uygulayamayız. **Ama "gelecek çalışma" slaydında bu makaleyi göstermek, alanın nereye gittiğini bildiğimizi kanıtlar.** Bu, uygulamaktan çok daha ucuz ve neredeyse aynı etkiyi yapar.
 
---
 
## 6. Biz nerede savunmasızız
 
Üç yer. Hepsi kapatılabilir.
 
### ⚠️ 1. Eğim limiti 25°, literatür 15–20°
 
**Risk:** "Neden 25?" sorusuna gerekçe yoksa keyfî görünür.
**Çözüm:** Duyarlılık analizine çevir. 15/20/25° için rota karşılaştırması göster. Frontend'de kaydıraç zaten var.
**Maliyet:** Yarım gün.
 
### ⚠️ 2. Zaman dilimi 6 saat, literatür 30 dk–1 saat
 
**Risk:** "Bu çözünürlükte aydınlanma değişimini yakalayabiliyor musunuz?" — kutupta gölgeler saat mertebesinde hareket ediyor, bu meşru bir soru.
**Çözüm:** 1 saatlik dilim denenmeli. Durum uzayı 6× büyür; hesap süresi ölçülüp raporlanmalı. Yapılamazsa gerekçe yazılmalı.
**Maliyet:** Backend'de yarım gün deneme.
 
### ⚠️ 3. "Görev başarılı" tanımımız eksik
 
**Risk:** Rotanın bitmesi görevin başarısı değil. Literatürde rover, bitiş noktasında ay gecesini atlatabilmek zorunda.
**Çözüm:** Son-durum kontrolü ekle — varış SoC'si + hibernasyon bütçesi ≥ ay gecesi tüketimi. Güvenli sığınak kümesi tanımla.
**Maliyet:** Backend'de birkaç saat. **En yüksek getirili düzeltme bu.**
 
### ✅ Savunmasız OLMADIĞIMIZ yerler
 
Bunları da bilmek önemli, gereksiz savunma yapmamak için:
 
- **Regolit/sürtünme modellenmemiş** → JPL ortaklı çalışma da modellemiyor. Norm.
- **Termal katman sentetik** → Diviner ile değiştirilebilir ama olmaması ölümcül değil.
- **Aydınlanma 240 m** → Yöntemin yazarı bu çözünürlüğü yeterli ilan etmiş.
- **A* çekirdek, RL değil** → Literatürün tamamı A* ailesinde. TEMPEST, Cunningham, Richter, Lamarre — hepsi.
- **Ağırlıklı çok kriterli maliyet** → Richter ve ark. 2024, iSpaRo. Hakemli.
---
 
## 7. Sunumda kullanılacak üç cümle
 
**1. Yöntem meşruiyeti**
> "Aydınlanma hesabımız Mazarico ufuk yöntemini kullanıyor — VIPER'ın kullandığı yöntemin aynısı, aynı toolkit'le (SPICE)."
 
**2. Tezin kanıtı**
> "Lamarre ve ark. 2024, IEEE Aerospace: yarım kilometre daha uzun bir rota, görev başarısızlığı riskini %23'ten %1.7'ye düşürüyor. En kısa rota en iyi rota değildir — projemizin varlık sebebi bu."
 
**3. Olgunluk**
> "Regolit mekaniğini modellemiyoruz. JPL ortaklı hakemli çalışmalar da modellemiyor — sabit hız ve güç modeli kullanıyorlar. Fark, modellememek değil, modellemediğini söylemek."
 
---
 
## 8. Aksiyon listesi
 
| # | İş | Kim | Süre | Öncelik |
|---|---|---|---|---|
| 1 | Son-durum kontrolü: varış SoC + ay gecesi hayatta kalma | Backend | 3 sa | **Yüksek** |
| 2 | Güvenli sığınak kümesi tanımı + benchmark başarı kriteri | Domain + Backend | 4 sa | **Yüksek** |
| 3 | Eğim duyarlılık analizi (15/20/25°) | Backend + Frontend | 1 gün | **Yüksek** |
| 4 | 1 saatlik zaman dilimi denemesi + hesap süresi ölçümü | Backend | 4 sa | Orta |
| 5 | Güç modları ayrımı (sürüş/bekleme/hibernasyon) kontrolü | Backend | 2 sa | Orta |
| 6 | Sert kısıt vs maliyet ayrımının kodda doğrulanması | Backend | 2 sa | Orta |
| 7 | "Gelecek çalışma" slaydı: şans-kısıtlı planlama | Domain | 1 sa | Düşük |
 
---
 
## 9. Kaynakça
 
**Görev seviyesi planlama**
- Tompkins, P., Stentz, A. & Wettergreen, D. (2006). Mission-level path planning and re-planning for rover exploration. *Robotics and Autonomous Systems*, 54(2), 174–183.
- Tompkins, P. (2005). *Mission-directed path planning for planetary rover exploration.* Doktora tezi, Carnegie Mellon University, Robotics Institute.
- Stentz, A. (2002). Incremental Search Engine (ISE).
- Otten, N., Jones, H., Wettergreen, D. & Whittaker, W. (2015). Planning routes of continuous illumination and traversable slope using connected component analysis. *ICRA 2015*, 3953–3958.
- Otten, N., Wettergreen, D. & Whittaker, W. (2018). Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration. *Field and Service Robotics*, Springer, 465–479.
- Cunningham, C., Amato, J., Jones, H. & Whittaker, W. (2017). Accelerating energy-aware spatiotemporal path planning for the lunar poles. *ICRA 2017*, 4399–4406.
**Risk ve belirsizlik**
- Lamarre, O., Malhotra, S. & Kelly, J. (2024). Safe Mission-Level Path Planning for Exploration of Lunar Shadowed Regions by a Solar-Powered Rover. *IEEE Aerospace Conference*. arXiv:2401.08558
- Lamarre, O., Malhotra, S. & Kelly, J. (2023). Recovery policies for safe exploration of lunar permanently shadowed regions by a solar-powered rover. *Acta Astronautica*, 213, 708–724.
- Ono, M., Pavone, M., Kuwata, Y. & Balaram, J. (2015). Chance-constrained dynamic programming with application to risk-aware robotic space exploration. *Autonomous Robots*, 39(4), 555–571.
**Çok kriterli planlama**
- Richter, J., Kolvenbach, H., Valsecchi, G. & Hutter, M. (2024). Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot. *iSpaRo 2024*, IEEE. DOI: 10.1109/iSpaRo60631.2024.10688158 · arXiv:2406.16376 · Kod: github.com/leggedrobotics/lunar_planner (MIT)
**Aydınlanma modelleme**
- Mazarico, E., Neumann, G.A., Smith, D.E., Zuber, M.T. & Torrence, M.H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. *Icarus*, 211(2), 1066–1081.
- Garrick-Bethell, I. ve ark. (2005). Ufuk yöntemi.
- Barker, M.K. ve ark. (2021). Improved LOLA elevation maps for south pole landing sites. *Planetary and Space Science*.
**VIPER**
- Shirley, M. & Balaban, E. (2022). *An Overview of Mission Planning for the VIPER Rover.* NASA Sunum 20220008301.
- Shirley, M. ve ark. (2022). VIPER Traverse Planning. *LPSC 2022*, Abstract 2874.
- Heldmann, J. ve ark. (2026). The Relevance of the VIPER Mission to NASA's Artemis Human Exploration of the Moon. *The Planetary Science Journal.*
- Beyer, R. ve ark. (2025). VIPER Site Analysis. *The Planetary Science Journal.*
**Kod**
- gplanetary-nav (Lamarre): github.com/utiasstars/gplanetary-nav
- lunar_planner (ETH): github.com/leggedrobotics/lunar_planner
---
 
*Bu rapor kısıt karşılaştırmasıdır. Değişen her kısıt değeri buraya işlenmeli, gerekçesi yazılmalıdır.*