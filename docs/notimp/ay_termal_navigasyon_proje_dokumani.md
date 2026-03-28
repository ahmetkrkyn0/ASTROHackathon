# Ay Yüzeyinde Termal Güvenlik Odaklı Otonom Navigasyon Sistemi
## Detaylı Proje Dokümanı

---

## 1. Belgenin amacı

Bu belge, projenin mevcut fikrini tek yerde düzenli ve profesyonel biçimde toplamak için hazırlanmıştır. Amaç; proje fikrini, hedefini, teknik modüllerini, ekip içi görev dağılımını, veri ihtiyaçlarını, risklerini ve henüz bilerek açık bırakılan karar alanlarını net şekilde ortaya koymaktır.

Bu belge özellikle şu ihtiyaca cevap verir:
- ekipte herkesin aynı projeyi düşündüğünden emin olmak,
- proje başvurusunda, sunumda ve teknik raporda aynı çerçeveyi korumak,
- henüz kesinleştirilmemiş noktaları “çelişki” gibi değil, “netleştirilmesi gereken alanlar” olarak kayıt altına almak.

---

## 2. Projenin genel tanımı

### 2.1 Proje adı
**Ay Yüzeyi İçin Termal Güvenlik Odaklı Otonom Rota Optimizasyonu**

### 2.2 Projenin özeti
Bu proje, Ay yüzeyinde özellikle sürekli gölgeli bölgelerde, derin kraterlerde ve aşırı düşük sıcaklık rejimlerinde görev yapan otonom keşif araçları için geliştirilen yapay zeka destekli bir navigasyon ve rota karar sistemidir.

Sistem; yüzey sıcaklığı, gölge/aydınlanma durumu, topoğrafya, eğim, araç termal toleransları ve enerji durumu gibi parametreleri birlikte değerlendirerek yalnızca en kısa rotayı değil, **araç donanım sağlığını koruyan, enerji verimliliğini gözeten ve görev başarısını artıran en güvenli rotayı** üretmeyi hedefler.

Bu yaklaşım, klasik rota planlamadan farklıdır. Çünkü bu projede amaç yalnızca hedefe ulaşmak değildir. Asıl amaç, hedefe giderken rover’ın kritik termal eşiklere girmemesini, gölgede tehlikeli süreler boyunca kalmamasını, batarya ve donanım açısından görev dışı kalmamasını sağlamaktır.

---

## 3. Projenin temel amacı

Bu projenin temel amacı, Ay’ın riskli bölgelerinde görev yapan otonom araçların:
- aşırı soğuk nedeniyle donanım arızası yaşama riskini azaltmak,
- sıcaklık ve gölge koşullarını hesaba katarak güvenli karar vermesini sağlamak,
- enerji verimliliği ile güvenlik arasında dengeli bir rota üretmek,
- değişen çevresel koşullarda yeniden planlama yapabilmek,
- görev sürdürülebilirliğini artırmaktır.

Kısacası proje, “en kısa rotayı bulma” problemini “**termal güvenlik ve görev sürdürülebilirliği odaklı rota planlama**” problemine dönüştürmektedir.

---

## 4. Problemin tanımı

Ay yüzeyinde, özellikle kutup bölgelerinde:
- sürekli gölgeli bölgeler vardır,
- bazı krater tabanları çok düşük sıcaklıklara maruz kalır,
- düşük güneş açısı nedeniyle aydınlanma çok düzensizdir,
- topoğrafya, eğim ve krater kenarları geçişi zorlaştırır,
- enerji toplama ve güvenli ilerleme arasında çatışma oluşabilir.

Bu nedenle şu gerçek ortaya çıkar:

> En kısa rota her zaman en güvenli rota değildir.

Bir rota mekanik olarak geçilebilir olsa bile:
- çok uzun süre gölgede kalabilir,
- termal eşik ihlali yaratabilir,
- batarya tüketimini artırabilir,
- güvenli toparlanma alanlarından uzak kalabilir,
- görevin erken sonlanmasına neden olabilir.

Bu proje, tam olarak bu problemi çözmek için tasarlanmaktadır.

---

## 5. Projenin çözüm yaklaşımı

Sistem genel olarak şu mantıkla çalışır:

1. Ay yüzeyine ait çevresel veri katmanları toplanır.
2. Rover için termal tolerans ve operasyonel sınırlar tanımlanır.
3. Haritadaki her bölge için sıcaklık, gölge, eğim ve enerji etkisi değerlendirilir.
4. Her hücre veya rota segmenti için bir risk ve maliyet skoru hesaplanır.
5. Rota planlama motoru, yalnızca mesafeye göre değil; güvenlik, enerji ve termal sağlık kriterlerine göre en uygun yolu üretir.
6. Koşullar değişirse sistem yeniden planlama yapar.
7. Sonuçlar harita, rota ve risk metrikleri ile kullanıcıya gösterilir.

Bu nedenle proje üç ana düşünceyi birleştirir:
- çevresel farkındalık,
- araç sağlığı farkındalığı,
- adaptif rota planlama.

---

## 6. Netleştirilmesi gereken yerler

Aşağıdaki maddeler mevcut durumda “çelişki” değil, bilerek açık bırakılmış veya henüz ekip içinde kesin karar verilmemiş alanlardır. Bunların ileride netleştirilmesi gerekir.

### 6.1 Projenin tam konumlandırması
Henüz şu konulardan hangisinin ana çerçeve olacağı kesin değildir:
- görev öncesi planlama aracı,
- simülasyon ve karar destek sistemi,
- rover üzeri otonomi karar modülü,
- bu üçüne yakın hibrit bir prototip.

Şu aşamada bunu kesin bir karara bağlamadan belgelemek daha doğrudur.

### 6.2 Veri akışının karakteri
Henüz net değildir:
- gerçek zamanlı veri mi kullanılacak,
- önceden hazırlanmış veri katmanları mı kullanılacak,
- zaman bağlı senaryo verisi mi oynatılacak.

Bu karar, sistem mimarisini doğrudan etkiler.

### 6.3 Termal riskin davranışı
Henüz netleştirilmesi gereken sorular:
- termal risk bazı bölgeleri tamamen yasaklayacak mı,
- yoksa bu bölgeler yüksek maliyetli ama teorik olarak geçilebilir mi olacak,
- termal ihlal durumunda fail mantığı mı çalışacak,
- yoksa yalnızca risk artışı mı uygulanacak.

### 6.4 Operatör müdahalesi seviyesi
Henüz karar verilmemiş alanlar:
- sistem tam otonom karar mı verecek,
- operatör rota seçenekleri arasından seçim yapabilecek mi,
- sistem yalnızca öneri mi sunacak.

### 6.5 Donanım sağlık modeli ayrıntı seviyesi
Henüz kesin değil:
- tek bir genel health score mu tutulacak,
- bileşen bazlı sağlık skoru mu olacak,
- thermal stress ve battery stress ayrı mı modellenmeli.

### 6.6 Başarı metriği
Henüz ekip içinde netleştirilmesi gereken metrikler:
- en güvenli rota mı,
- en verimli rota mı,
- görev tamamlama başarısı mı,
- batarya tasarrufu mu,
- termal ihlal sayısı mı,
- health score kaybı mı ana değerlendirme kriteri olacak.

### 6.7 Safe haven / recovery logic kapsamı
Henüz açık olan konular:
- sistem güvenli bekleme/toparlanma noktalarını aktif kullanacak mı,
- yoksa bu sadece ileri seviye bir opsiyon mu olacak,
- rota seçimi bu noktaları zorunlu olarak dikkate alacak mı.

### 6.8 Teknoloji seviyesi ve demo sınırı
Henüz kesin değildir:
- tam çalışan web tabanlı sistem mi hedefleniyor,
- script + simülasyon tabanlı demo mu,
- hafif backend ve arayüzlü prototip mi.

Bu başlıkların şimdilik açık kalması normaldir. Bu belgedeki amaç, bu alanları erkenden görünür hale getirmektir.

---

## 7. Proje kapsamı

### 7.1 Kapsam dahilinde
Aşağıdaki başlıklar proje kapsamında düşünülmektedir:
- Ay yüzey verilerinin kullanılması,
- termal riskin rota planlamaya dahil edilmesi,
- eğim/topoğrafya etkisinin hesaba katılması,
- enerji verimliliği ve görev güvenliğinin birlikte değerlendirilmesi,
- dinamik rota güncelleme mantığının kurulması,
- riskli bölgelerin işaretlenmesi,
- güvenli rota adaylarının karşılaştırılması,
- demo amaçlı simülasyon/görselleştirme yapılması.

### 7.2 Kapsam dışında
Şu alanlar doğrudan bu projenin hedefi değildir:
- rover donanım tasarımı ve üretimi,
- fırlatma/iniş operasyonları,
- Ay yüzeyinde tam uçuş yazılımı geliştirme,
- bilimsel yük kontrol sistemi,
- gerçek görev kontrol merkezi altyapısı,
- bütün Artemis görev zincirinin modellenmesi.

---

## 8. Yapılacak modüllerin detaylı listesi

## Modül 1 — Veri keşfi ve veri ön işleme modülü
### Amaç
Ay yüzeyine ait gerekli çevresel verileri toplamak ve aynı koordinat/grid yapısında kullanılabilir hale getirmek.

### Sorumluluklar
- veri kaynaklarını bulmak,
- indirilecek ürünleri seçmek,
- hedef bölgeyi belirlemek,
- crop / resample / align işlemlerini yapmak,
- eksik verileri yönetmek,
- ortak metadata yapısı oluşturmak.

### Beklenen çıktılar
- temperature layer,
- elevation layer,
- slope layer,
- illumination/shadow layer,
- PSR mask veya risk mask.

---

## Modül 2 — Çevresel katman üretimi modülü
### Amaç
Ham veriden rota kararında kullanılacak türetilmiş katmanları üretmek.

### Sorumluluklar
- DEM’den slope hesaplamak,
- shadow duration veya illumination score üretmek,
- thermal severity katmanı hazırlamak,
- hazard-support map üretmek,
- geçilemez/yüksek riskli alan maskeleri çıkarmak.

### Beklenen çıktılar
- route planning ve risk motorunun kullanabileceği model-ready harita katmanları.

---

## Modül 3 — Rover termal profil modülü
### Amaç
Araç için güvenli operasyon sınırlarını tanımlamak.

### Sorumluluklar
- minimum ve maksimum güvenli sıcaklık aralığını tanımlamak,
- warning / critical / fail eşiklerini belirlemek,
- maksimum gölgede kalma süresi tanımlamak,
- kritik batarya eşiğini belirlemek,
- eğim limiti gibi görev kısıtlarını tanımlamak.

### Beklenen çıktılar
- rover_profile.json,
- parametre dokümanı,
- varsayımlar listesi.

---

## Modül 4 — Thermal risk ve hardware health modülü
### Amaç
Çevresel koşulların araca etkisini modellemek.

### Sorumluluklar
- thermal stress birikimini modellemek,
- health score güncellemek,
- gölgede kalma süresini izlemek,
- recovery mantığı tanımlamak,
- warning / critical / fail durumlarını üretmek.

### Beklenen çıktılar
- cell-level risk,
- route-level safety score,
- thermal penalty,
- health degradation estimate.

---

## Modül 5 — Risk skorlama ve karar motoru
### Amaç
Rota planlayıcının kullanacağı maliyetleri üretmek.

### Sorumluluklar
- sıcaklık, gölge, enerji ve eğim etkilerini ortak skor haline getirmek,
- hard constraint ve soft penalty mantığını kurmak,
- safe haven uygunluğu üretmek,
- emergency / unsafe flag mantığı tanımlamak.

### Beklenen çıktılar
- cost map,
- unsafe map,
- route evaluation logic,
- replanning trigger kuralları.

---

## Modül 6 — Rota planlama modülü
### Amaç
En güvenli ve en uygun rotayı hesaplamak.

### Sorumluluklar
- A*, D* Lite veya benzeri bir yöntemle rota üretmek,
- mesafe + termal risk + enerji + eğim bileşik maliyetini kullanmak,
- alternatif rotaları kıyaslamak,
- gerektiğinde yeniden planlama yapmak.

### Beklenen çıktılar
- primary route,
- alternative route,
- route score,
- route rejection/explanation.

---

## Modül 7 — Backend / entegrasyon modülü
### Amaç
Modüller arasındaki veri akışını ve senaryo çalıştırmayı yönetmek.

### Sorumluluklar
- input/output schema tanımlamak,
- modüller arası veri alışverişini koordine etmek,
- senaryo runner oluşturmak,
- log ve sonuç üretmek,
- frontend için okunabilir çıktı sağlamak.

### Beklenen çıktılar
- çalışan entegrasyon akışı,
- JSON çıktılar,
- senaryo bazlı test koşumu.

---

## Modül 8 — Görselleştirme ve demo modülü
### Amaç
Sistemin ürettiği sonuçları anlaşılır ve etkileyici biçimde sunmak.

### Sorumluluklar
- harita üzerinde rota göstermek,
- risk katmanı göstermek,
- battery/health göstergeleri üretmek,
- “neden bu rota seçildi” açıklamasını göstermek,
- demo akışını hazırlamak.

### Beklenen çıktılar
- demo dashboard,
- harita overlay’leri,
- kıyaslama ekranları,
- sunum ekran görüntüleri.

---

## Modül 9 — Test, doğrulama ve dokümantasyon modülü
### Amaç
Sistemin teknik olarak tutarlı ve anlatılabilir olmasını sağlamak.

### Sorumluluklar
- veri doğrulama kontrol listeleri hazırlamak,
- model test senaryoları tanımlamak,
- edge case testleri çalıştırmak,
- README ve proje özeti hazırlamak,
- sunum ve başvuru metinlerini desteklemek.

### Beklenen çıktılar
- validation checklist,
- example scenarios,
- README,
- teknik rapor / sunum notları.

---

## 9. Projenin genel çalışma akışı

Aşağıdaki zincir projenin uçtan uca mantığını özetler:

```text
Lunar Data Sources
-> Data Preprocessing
-> Environmental Layers
-> Rover Thermal Profile
-> Thermal Risk & Health Engine
-> Path Planning Engine
-> Scenario Runner / Backend
-> Visualization Dashboard
```

Bu yapı sayesinde proje yalnızca bir algoritma değil, tam bir karar verme zinciri haline gelir.

---

## 10. Oluşabilecek risklerin detaylı analizi

## 10.1 Veri kaynaklı riskler

### Risk 1 — Veri boyutlarının çok büyük olması
Ay kutbu verileri yüksek çözünürlükte oldukça büyük olabilir. Bu da indirme, işleme ve hizalama sürelerini uzatır.

**Etkisi:**
- takım yavaşlar,
- ön işleme gecikir,
- diğer modüller beklemek zorunda kalır.

**Azaltma stratejisi:**
- küçük bir hedef bölge seçmek,
- yalnızca gerekli katmanları almak,
- düşük/orta çözünürlüklü MVP veri kullanmak,
- önce sentetik veya küçük demo grid ile geliştirme yapmak.

### Risk 2 — Katman hizasızlığı
Sıcaklık, gölge, eğim ve topoğrafya katmanları aynı grid yapısında değilse risk motoru yanlış çalışır.

**Etkisi:**
- risk hesapları anlamsızlaşır,
- planner yanlış rota seçer,
- demo güvenilmez hale gelir.

**Azaltma stratejisi:**
- ilk aşamada ortak çözünürlük ve metadata standardı belirlemek,
- her exporttan önce shape check yapmak,
- aynı region of interest üzerinde çalışmak.

### Risk 3 — Eksik değerler / bozuk veri
No-data veya eksik hücreler risk motorunu ve rota planlayıcıyı bozabilir.

**Azaltma stratejisi:**
- no-data değeri standardı belirlemek,
- maskeleme yapmak,
- eksik veri durumunda conservative penalty uygulamak.

---

## 10.2 Modelleme riskleri

### Risk 4 — Modelin aşırı karmaşıklaşması
Tam fiziksel termal model kurmaya çalışmak proje hızını düşürür.

**Etkisi:**
- implementasyon gecikir,
- entegrasyon zorlaşır,
- takım teknik olarak dağılır.

**Azaltma stratejisi:**
- physics-inspired ama basitleştirilmiş model kullanmak,
- state-based health yaklaşımını tercih etmek,
- önce çalışan versiyon, sonra geliştirme mantığıyla ilerlemek.

### Risk 5 — Parametrelerin keyfi kalması
Gerçek rover verisi yoksa eşikler fazla varsayımsal kalabilir.

**Etkisi:**
- jüri tarafından sorgulanabilir,
- model güvenilirliği azalabilir.

**Azaltma stratejisi:**
- parametreleri açıkça “assumption-based engineering model” olarak belgelemek,
- tüm eşikleri tek yerde tutmak,
- karşılaştırmalı senaryolarla model davranışını göstermek.

### Risk 6 — Risk fonksiyonu yanlış ağırlıklandırılır
Enerji, güvenlik ve termal ceza arasındaki denge yanlış kurulursa sistem tutarsız davranabilir.

**Azaltma stratejisi:**
- baseline senaryolarla test yapmak,
- shortest path vs safe path farkını ölçmek,
- kritik ağırlıkları config dosyasından yönetmek.

---

## 10.3 Entegrasyon riskleri

### Risk 7 — Modüller birbirini bekler
1. kişi veri hazırlamazsa 2. ve 3. kişi bloklanabilir.

**Azaltma stratejisi:**
- ortak sentetik grid ile erken geliştirme başlatmak,
- arayüzleri baştan dondurmak,
- modüller arası contract yazmak.

### Risk 8 — Path planner ile risk motoru uyumsuz olur
Risk modülü ile rota motoru farklı veri formatı beklerse entegrasyon gecikir.

**Azaltma stratejisi:**
- cell cost, unsafe flag, route score gibi standart field’ler belirlemek,
- fonksiyon imzalarını erken sabitlemek.

### Risk 9 — Backend ve frontend geç devreye girer
Teknik motorlar çalışsa bile sonuç gösterilemezse proje zayıf görünür.

**Azaltma stratejisi:**
- erken aşamada demo formatı belirlemek,
- basit ama etkili görselleştirme planı yapmak.

---

## 10.4 Sunum ve proje anlatımı riskleri

### Risk 10 — Proje çok geniş anlatılır
“Gerçek rover flight software” gibi algılanırsa beklenti çok yükselir.

**Azaltma stratejisi:**
- projeyi açıkça “AI-assisted simulation / decision-support prototype” olarak konumlandırmak.

### Risk 11 — Teknik özgünlük kaybolur
Proje yalnızca rota planlama sistemi gibi görünürse termal sağlık tarafı gölgede kalır.

**Azaltma stratejisi:**
- donanım sağlığı, thermal risk ve recovery mantığını ayrı modül olarak öne çıkarmak,
- demo’da health score ve thermal stress göstermek.

### Risk 12 — Jüri için somut başarı metriği eksik kalır
“İyi rota” ne demek sorusuna net cevap verilmezse anlatım zayıflar.

**Azaltma stratejisi:**
- karşılaştırmalı metrikler göstermek:
  - shortest path vs safe path,
  - toplam risk,
  - termal ihlal sayısı,
  - batarya tüketimi,
  - görev tamamlama oranı.

---

## 11. 5 kişi için detaylı görev dağılımı

## Kişi 1 — Lunar Data & Preprocessing Engineer
### Ana sorumluluğu
Ay yüzeyine ait çevresel verileri toplamak, temizlemek, hizalamak ve diğer modüllerin kullanabileceği hazır katmanlara dönüştürmek.

### Yapacağı işler
- veri kaynaklarını bulmak,
- gerekli veri setlerini indirmek,
- hedef bölgeyi seçmek,
- sıcaklık, yükseklik, gölge verilerini ortak gridde hizalamak,
- slope ve türetilmiş çevresel katmanları üretmek,
- metadata ve veri sözlüğü hazırlamak.

### Teslimleri
- processed layers,
- preprocessing scripts,
- data dictionary,
- model input export files.

---

## Kişi 2 — Thermal Risk & Hardware Health Engineer
### Ana sorumluluğu
Çevresel koşulların rover üzerindeki etkisini modellemek ve araç güvenlik skorunu üretmek.

### Yapacağı işler
- rover thermal profile oluşturmak,
- thermal stress model kurmak,
- health score üretmek,
- shadow exposure takibi yapmak,
- recovery ve safe haven mantığı geliştirmek,
- planner için thermal cost üretmek.

### Teslimleri
- rover_profile.json,
- risk functions,
- health model,
- route safety evaluator.

---

## Kişi 3 — Path Planning & AI Navigation Engineer
### Ana sorumluluğu
Termal ve çevresel maliyetleri kullanarak güvenli rota planlayıcısını geliştirmek.

### Yapacağı işler
- A* / D* Lite tabanlı path planner kurmak,
- composite cost function uygulamak,
- alternative route comparison yapmak,
- replanning logic eklemek,
- unsafe route rejection mantığı eklemek.

### Teslimleri
- route planner,
- replan logic,
- route comparison outputs.

---

## Kişi 4 — Backend / Integration / Scenario Engine Engineer
### Ana sorumluluğu
Tüm modülleri bir araya getirip çalışan senaryo altyapısını kurmak.

### Yapacağı işler
- modüller arası veri alışverişini yönetmek,
- scenario runner yazmak,
- API veya komut tabanlı entegrasyon yapmak,
- log ve response şemaları hazırlamak,
- test senaryolarını koşturmak.

### Teslimleri
- entegre servis,
- senaryo koşucu,
- API/JSON outputs,
- log outputs.

---

## Kişi 5 — Frontend / Visualization / Demo / Documentation Lead
### Ana sorumluluğu
Projeyi görünür, anlaşılır ve jüriye etkili biçimde sunmak.

### Yapacağı işler
- dashboard geliştirmek,
- harita, rota, risk katmanlarını görselleştirmek,
- metrik kartları ve kıyas ekranları hazırlamak,
- sunum, README, demo video, başvuru metni oluşturmak.

### Teslimleri
- demo arayüzü,
- sunum,
- proje özeti,
- başvuru belgeleri,
- ekran görüntüleri ve anlatım akışı.

---

## 12. Ekipler arası bağımlılık yapısı

En önemli veri ve iş bağımlılıkları şunlardır:

- **Kişi 1 -> Kişi 2:** sıcaklık, eğim, gölge katmanları
- **Kişi 1 -> Kişi 3:** cost map için çevresel girdiler
- **Kişi 2 -> Kişi 3:** thermal penalty, unsafe thresholds, health/risk outputs
- **Kişi 3 -> Kişi 4:** route outputs ve planner logic
- **Kişi 4 -> Kişi 5:** senaryo sonuçları ve sistem çıktıları
- **Kişi 1,2,3,4 -> Kişi 5:** görselleştirilecek veri ve anlatım materyali

Bu nedenle erken sabitlenmesi gerekenler:
- ortak bölge,
- ortak grid,
- ortak dosya isimlendirmesi,
- ortak JSON şeması,
- birim standardı,
- no-data değeri,
- senaryo tanım formatı.

---

## 13. Gerekli veri setlerinin örnek başlıkları

Aşağıdaki başlıklar proje için kullanılabilecek güçlü veri seti örnekleridir. Bunlar doğrudan veri seçim kararı değildir; ekip için aday başlıklar ve referans omurgasıdır.

## 13.1 Sıcaklık verileri
Örnek başlıklar:
- Diviner Lunar Radiometer Experiment Surface Temperature Maps
- Diviner Global and Polar Temperature Maps
- Seasonal Polar Temperatures on the Moon
- Lunar Surface Day/Night Temperature Products

Kullanım amacı:
- yüzey sıcaklığı katmanı üretmek,
- termal severity ve thermal risk hesaplamak,
- rota üzerindeki sıcaklık maruziyetini değerlendirmek.

---

## 13.2 Topografya / yükseklik verileri
Örnek başlıklar:
- LOLA South Pole GDR
- LDEM_85S_10M
- LDEM_85S_20M
- LDEM_875S_10M
- LDEM_875S_5M

Kullanım amacı:
- elevation map üretmek,
- slope çıkarmak,
- topoğrafya bazlı geçilebilirlik analizi yapmak.

---

## 13.3 Sürekli gölgeli bölge (PSR) verileri
Örnek başlıklar:
- Permanently Shadowed Regions Atlas
- PSR List
- PSR Atlas Download
- South Pole PSR Map

Kullanım amacı:
- yüksek termal risk alanlarını işaretlemek,
- rota cezalandırması yapmak,
- safe/unsafe bölge ayrımı üretmek.

---

## 13.4 Aydınlanma / gölge verileri
Örnek başlıklar:
- Illumination at the Moon’s South Pole, 2023 to 2030
- South Pole Sunlight and Shadow Simulation
- Polar Illumination Maps
- Two-hour Interval Lunar South Pole Lighting Products

Kullanım amacı:
- shadow duration veya illumination score üretmek,
- dinamik senaryo bazlı rota güncellemek,
- recovery-friendly alanları tahmin etmek.

---

## 13.5 Yardımcı veya alternatif veri setleri
Örnek başlıklar:
- Kaguya LALT South Polar Topographic Data
- LROC Polar Illumination Maps
- LROC South Pole Mosaic
- Shackleton Region Terrain Products

Kullanım amacı:
- yedek veya tamamlayıcı katman olarak kullanmak,
- görselleştirme ve bağlam desteği vermek,
- veri boşluklarını azaltmak.

---

## 14. Önerilen minimum veri omurgası

Projenin çekirdeğini taşımak için en az şu veri omurgası yeterlidir:

1. sıcaklık haritası,
2. yükseklik / DEM,
3. slope katmanı,
4. shadow/illumination katmanı,
5. PSR maskesi.

Bu beş katman ile:
- thermal risk,
- traversability,
- route cost,
- safe vs unsafe region,
- demo görselleştirmesi
üretilebilir.

---

## 15. Başarı için önerilen temel çıktılar

Bu proje sonunda ortaya çıkması gereken ana ürünler:

### Teknik çıktılar
- hizalanmış veri katmanları,
- rover thermal profile,
- thermal risk & health engine,
- çalışan rota planlayıcı,
- senaryo koşucu,
- görselleştirme arayüzü.

### Dokümantasyon çıktıları
- proje özeti,
- detaylı teknik açıklama,
- risk analizi,
- görev dağılımı,
- veri seti listesi,
- README,
- sunum ve demo materyalleri.

### Demo metrikleri
- shortest path vs safe path,
- total thermal risk,
- thermal violation count,
- battery usage,
- health score,
- replan event,
- safe haven usage.

---

## 16. Sonuç

Bu proje, Ay yüzeyinde özellikle kutup bölgelerinde görev yapan otonom keşif araçları için geliştirilen, **termal güvenlik ve görev sürdürülebilirliğini merkeze alan çok kriterli rota planlama sistemi** olarak tanımlanabilir.

Projeyi güçlü yapan ana fikir şudur:

> Araç yalnızca hedefe giden bir yol bulmaz; o yolda güvenli kalacak şekilde ilerler.

Bu yönüyle proje;
- navigasyon,
- termal risk analizi,
- enerji farkındalığı,
- görev güvenliği,
- yapay zeka destekli karar verme
başlıklarını tek yapıda birleştirir.

Henüz açık bırakılmış bazı karar alanları olsa da bunlar yapısal çelişki değil; doğal tasarım kararlarıdır. Bu belge, hem mevcut ortak zemini hem de ileride netleştirilmesi gereken alanları profesyonel biçimde görünür hale getirmek için hazırlanmıştır.
