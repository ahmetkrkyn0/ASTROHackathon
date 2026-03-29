# Lunar Data & Thermal Preparation Team

## Genel Tanım

Bu görev paketi, projedeki **1. kişi** ile **2. kişinin** birlikte yürüteceği temel veri ve thermal hazırlık işlerini kapsar.

Bu iki rol, projenin çevresel veri temelini ve thermal-risk mantığını kurar. Çünkü diğer ekip üyelerinin sağlıklı çalışabilmesi için aşağıdaki katmanların güvenilir biçimde hazırlanmış olması gerekir:

- sıcaklık verisi
- gölge / aydınlanma bilgisi
- eğim / yükseklik bilgisi
- analiz edilebilir ortak grid / map yapısı
- thermal tolerance ve risk hesaplamasına uygun model girdileri

Bu ekip iyi çalışmazsa:

- thermal model doğru beslenmez,
- rota planlama güvenilir cost map üretemez,
- backend düzenli veri okuyamaz,
- arayüzde gösterilecek güvenilir çevresel katman oluşmaz.

---

# 1. ve 2. Kişinin Birlikte Üstleneceği Çalışma Alanı

## Ortak Misyon

Ay yüzeyine ait açık verileri toplayıp işlemek, ortak formata getirmek ve bunları thermal-risk analizi ile rota planlama için kullanılabilir çevresel katmanlara dönüştürmek.

Bu ekibin temel işi şu akıştan oluşur:

**ham veri almak → temizlemek → hizalamak → türetilmiş katman üretmek → thermal risk için anlamlı hale getirmek → diğer ekibe hazır çıktı vermek**

---

# Rol Dağılımı

## 1. Kişi — Lunar Data & Preprocessing Engineer

### Ana sorumluluğu

Ay yüzeyine ait açık verileri toplamak, temizlemek, ortak formata getirmek ve sistemin kullanabileceği hazır çevresel katmanlara dönüştürmek.

### Temel görevi

**Ham veriyi almak → işlenmiş harita katmanına çevirmek.**

### Başlıca odak alanları

- veri kaynağı seçimi
- veri indirme ve arşivleme
- ortak grid / koordinat sistemi oluşturma
- veri temizleme ve dönüştürme
- türetilmiş çevresel katman üretimi
- model-ready ve API-ready export hazırlama
- veri dokümantasyonu

---

## 2. Kişi — Thermal Modeling & Hardware Risk Engineer

### Ana sorumluluğu

1. kişinin ürettiği çevresel katmanları kullanarak rover veya sistem bileşenleri için thermal risk değerlendirmesi yapmak ve donanım güvenliğini etkileyen sıcaklık bazlı karar mantığını oluşturmak.

### Temel görevi

**Çevresel veri katmanlarını almak → thermal tolerans ve risk skoruna çevirmek.**

### Başlıca odak alanları

- thermal tolerance aralıklarının tanımlanması
- sıcaklık verisinin risk seviyelerine çevrilmesi
- cold exposure / thermal severity mantığının kurulması
- donanım güvenliği için risk bandı üretimi
- rota planlama için thermal cost girdisi hazırlama
- çevresel katmanlar ile thermal risk çıktılarının eşleştirilmesi
- thermal model varsayımlarının dokümantasyonu

---

# 1. Kişinin Teslim Etmesi Gereken Çıktılar

1. kişinin proje sonunda ekibe şu çıktıları vermesi gerekir:

## Çevresel katmanlar

- **Temperature layer**  
  Hücre bazlı sıcaklık haritası
- **Shadow / illumination layer**  
  Hücre bazlı gölge / aydınlanma bilgisi
- **Elevation / slope layer**  
  Yükseklik ve eğim haritası
- **Hazard-support map**  
  Geçilebilirlik için kullanılacak ön işlenmiş destek katmanları
- **Common grid system**  
  Tüm katmanların aynı çözünürlükte ve aynı koordinat sisteminde hizalanmış hali

## Veri açıklama ve tekrar üretilebilirlik

- **Data dictionary**  
  Hangi dosyanın neyi temsil ettiği, hangi birimde tutulduğu ve nasıl okunacağı
- **Reusable preprocessing pipeline**  
  Yeniden çalıştırılabilir Python script / notebook / pipeline

---

# 2. Kişinin Teslim Etmesi Gereken Çıktılar

2. kişinin proje sonunda ekibe şu çıktıları vermesi gerekir:

- **Thermal risk layer**  
  Hücre bazlı thermal risk skoru
- **Cold exposure score**  
  Uzun süreli soğuk maruziyet etkisini temsil eden skor
- **Thermal severity band**  
  Sıcaklık verisinin düşük / orta / yüksek risk bantlarına çevrilmiş hali
- **Hardware safety thresholds**  
  Donanım için tanımlanmış güvenli çalışma sınırları
- **Thermal cost map input**  
  Rota planlama için kullanılacak thermal maliyet girdisi
- **Thermal modeling notes**  
  Varsayımlar, limitler, formüller ve kullanılan eşikler

---

# 1. Kişinin Teknik Görevleri

## Görev 1 — Veri kaynaklarını belirleme

### Amaç
Projede hangi açık veri setlerinin kullanılacağını netleştirmek.

### Bulması gereken veri tipleri

- Ay yüzey sıcaklığı
- yükseklik / topografya
- eğim türetmek için DEM
- illumination / shadow bilgisi
- mümkünse PSR maskesi

---

## Görev 2 — Veri indirme ve arşivleme

### Amaç
Tüm veri kaynaklarını organize biçimde toplamak.

### Yapması gerekenler

- verileri indir
- sürümle
- klasörle
- dosya isimlerini standardize et

---

## Görev 3 — Ortak koordinat ve grid standardı belirleme

### Amaç
Farklı veri kaynaklarını aynı sistemde kullanabilmek.

### Karar vermesi gerekenler

- hangi bölge seçilecek
- grid resolution ne olacak
- dosya formatı ne olacak
- tüm katmanlar aynı shape’e nasıl getirilecek

---

## Görev 4 — Temizlik ve dönüştürme

### Amaç
Ham veriyi kullanılabilir hale getirmek.

### Yapması gerekenler

- eksik değerleri işle
- crop yap
- normalize et
- yeniden örnekle
- aynı grid yapısına oturt

---

## Görev 5 — Türetilmiş katman üretimi

### Amaç
Ham veriden ek analiz katmanları çıkarmak.

### Örnekler

- elevation → slope
- illumination → shadow duration score
- sıcaklık → thermal severity band için uygun giriş
- krater kenarı yakınlığı → hazard-support layer

---

## Görev 6 — Ekip için API-ready / model-ready veri üretimi

### Amaç
Diğer kişilerin direkt kullanabileceği çıktılar hazırlamak.

### Olası çıktı formatları

- `.npy`
- `.csv`
- `.json` metadata
- `.tif`
- gerekiyorsa tile map

---

## Görev 7 — Dokümantasyon ve teslim

### Amaç
Ekip bu veriyi açınca ne olduğunu anlasın.

### Hazırlaması gerekenler

- `README.md`
- data schema
- unit açıklamaları
- preprocessing steps
- known limitations

---

# 2. Kişinin Teknik Görevleri

## Görev 1 — Thermal tolerans gereksinimlerini belirleme

### Amaç
Araç veya donanımın hangi sıcaklık koşullarında güvenli / riskli çalışacağını tanımlamak.

### Yapması gerekenler

- güvenli sıcaklık aralığını belirle
- kritik eşikleri tanımla
- düşük sıcaklık kaynaklı risk senaryolarını listele
- varsayımları yaz

---

## Görev 2 — Sıcaklık katmanını thermal risk girdisine çevirme

### Amaç
1. kişinin temperature layer çıktısını risk açısından kullanılabilir hale getirmek.

### Yapması gerekenler

- sıcaklık değerlerini thermal risk ölçeğine çevir
- threshold tabanlı veya skorlu yaklaşım belirle
- risk bandı üret
- gerektiğinde normalize edilmiş risk katmanı oluştur

---

## Görev 3 — Shadow / cold exposure etkisini modelleme

### Amaç
Uzun süre gölgede kalmanın thermal güvenliğe etkisini hesaba katmak.

### Yapması gerekenler

- shadow duration veya illumination verisini yorumla
- cold exposure score üret
- gerekirse temperature ile birleştir
- thermal severity mantığını güçlendir

---

## Görev 4 — Thermal cost map girdisi oluşturma

### Amaç
Rota planlama modülünün kullanabileceği thermal maliyet girdisini hazırlamak.

### Yapması gerekenler

- thermal risk katmanını sayısal cost yapısına dönüştür
- forbidden / high-risk zone mantığını tanımla
- rota motoruna uygun formatta export ver

---

## Görev 5 — Donanım güvenliği odaklı risk açıklaması hazırlama

### Amaç
Modelin neden bu risk skorunu verdiğinin açıklanabilir olması.

### Hazırlaması gerekenler

- risk seviyesi açıklamaları
- thermal severity band tanımı
- hangi katmanların nasıl birleştiği
- bilinen varsayımlar ve limitler

---

## Görev 6 — Dokümantasyon ve teslim

### Amaç
Thermal model çıktılarının ekip tarafından doğru yorumlanması.

### Hazırlaması gerekenler

- `thermal_model_notes.md`
- threshold tablosu
- unit açıklamaları
- risk score açıklaması
- known limitations

---

# 1. ve 2. Kişinin Ortak Çalışma Noktaları

Bu iki rol doğrudan birbirine bağlıdır. Bu nedenle bazı kararlar birlikte alınmalıdır.

## Birlikte karar vermeleri gerekenler

- hedef çalışma bölgesi
- grid çözünürlüğü
- ortak dosya formatları
- sıcaklık birimi
- thermal risk hesaplamasında kullanılacak sıcaklık yorumu
- export isimlendirme standardı
- demo için kullanılacak hafif veri paketi

## 1. kişinin 2. kişiye vereceği girdiler

- temperature grid
- shadow duration / cold exposure için kullanılacak katman
- terrain condition input
- elevation ve slope katmanları
- hazard-support map
- metadata ve schema

## 2. kişinin 1. kişiden beklediği şeyler

- tüm katmanların aynı shape’te olması
- birimlerin net yazılmış olması
- missing value stratejisinin belirtilmiş olması
- dosyaların kolay yüklenebilir olması
- thermal model için doğrudan kullanılabilir export hazırlanması

## 2. kişinin 1. kişiye geri vereceği bilgiler

- hangi temperature aralıklarının kritik olduğu
- hangi shadow bilgisinin daha anlamlı olduğu
- thermal cost map için hangi sayısal aralıkların gerektiği
- hangi katmanların nihai risk hesabında kullanılacağı

---

# 1. Kişinin Diğer Ekip Üyeleriyle Bağlantısı

## 3. kişi ile bağlantı

Ona verecekleri:

- cost map girdileri
- forbidden zone mask
- slope / hazard katmanları
- thermal cost bileşenleri

## 4. kişi ile bağlantı

Ona verecekleri:

- backend’in okuyacağı düzenli veri formatı
- metadata ve schema
- örnek veri yükleme yapısı

## 5. kişi ile bağlantı

Ona verecekleri:

- görselleştirilebilir hafif veri
- renk skalası / legend önerisi
- örnek görseller
- demo için optimize edilmiş katmanlar

---

# 1. Kişinin Yapması Gereken İşlerin Daha Küçük Parçalara Bölünmüş Hali

## A. Veri araştırma alt işleri

- kullanılabilir veri kaynaklarını listele
- her kaynak için format, çözünürlük ve kapsama alanını yaz
- hangi veri setinin kullanılacağını seç
- veri erişim yöntemini belirle
- lisans / açık erişim durumunu kontrol et

## B. Veri indirme alt işleri

- ham veri klasörlerini oluştur
- dosya isim standardı belirle
- örnek dosyaları indir
- indirme komutlarını belgeye yaz
- dosya boyutlarını kaydet

## C. Veri işleme alt işleri

- target region seç
- crop işlemi yap
- grid size belirle
- reproject / resample yap
- NaN / missing value yönetimini uygula

## D. Türetilmiş veri alt işleri

- slope map hesapla
- shadow mask çıkar
- thermal modeling için uygun severity input üret
- basit traversability support map üret

## E. Doğrulama alt işleri

- katman boyutları eşit mi kontrol et
- min / max değerleri mantıklı mı bak
- 2D görsel kontrol yap
- 1 örnek rota alanında değerleri incele
- ekibe test dosyası gönder

## F. Teslim alt işleri

- `README.md` yaz
- `data_dictionary.md` hazırla
- export script yaz
- demo paketi oluştur
- final teslim klasörünü düzenle

---

# 2. Kişinin Yapması Gereken İşlerin Daha Küçük Parçalara Bölünmüş Hali

## A. Thermal analiz alt işleri

- thermal tolerance aralıklarını listele
- kritik sıcaklık eşiklerini belirle
- güvenli / riskli / kritik sınıfları tanımla
- varsayım tablosu oluştur

## B. Risk üretim alt işleri

- temperature layer’ı oku
- eşik tabanlı thermal risk skoru hesapla
- normalize edilmiş risk katmanı üret
- thermal severity band oluştur

## C. Shadow ve exposure alt işleri

- illumination / shadow layer’ı oku
- cold exposure score tasarla
- temperature ile birleştirilecek mantığı belirle
- exposure etkisini risk skoruna yansıt

## D. Rota entegrasyon alt işleri

- thermal risk’i cost map biçimine çevir
- forbidden zone tanımı yap
- rota planlama için hafif export üret

## E. Doğrulama alt işleri

- risk skorlarının beklenen aralıkta olup olmadığını kontrol et
- birkaç örnek hücre üzerinde manuel kontrol yap
- sıcaklık ve risk ilişkisinin mantıklı olup olmadığını incele
- 1. kişi ile birlikte çıktı tutarlılığını kontrol et

## F. Teslim alt işleri

- `thermal_model_notes.md` yaz
- `risk_dictionary.md` hazırla
- `export_thermal_layers.py` veya notebook hazırla
- demo thermal katmanlarını düzenle

---

# Kullanılması Önerilen Araçlar

## Zorunluya yakın araçlar

- Python
- NumPy
- Pandas
- Rasterio
- xarray
- matplotlib
- Jupyter Notebook

## Çok faydalı araçlar

- GDAL
- geopandas
- scipy
- QGIS  
  Görsel kontrol için çok faydalıdır.

---

# Dosya Formatı Önerileri

## Ham veri

- `.tif`
- `.img`
- `.csv`
- `.nc`

## İşlenmiş veri

- `.npy`
- `.csv`
- `.json`
- `.tif`

---

# Önerilen Klasör Yapısı

```text
/data
  /raw
    /temperature
    /elevation
    /illumination
  /processed
    /aligned
    /derived
    /thermal
  /exports
    /demo
    /model_input

/notebooks
  01_data_exploration.ipynb
  02_alignment.ipynb
  03_derived_layers.ipynb
  04_thermal_modeling.ipynb
  05_validation.ipynb

/scripts
  download_data.py
  preprocess_data.py
  build_layers.py
  build_thermal_risk.py
  export_demo_data.py

/docs
  README.md
  data_dictionary.md
  preprocessing_notes.md
  thermal_model_notes.md
  risk_dictionary.md
```

---

# Riskler

## Risk 1 — Veri çok büyük gelir, proje yavaşlar

### Neden olur?
Kaynak veri yüksek çözünürlüklü ve ağır olabilir.

### Çözüm

- küçük çalışma alanı seç
- downsample et
- demo için hafif versiyon üret

---

## Risk 2 — Katmanlar hizalanmaz

### Neden olur?
Farklı kaynaklar farklı grid, çözünürlük veya koordinat yapısında olabilir.

### Çözüm

- baştan ortak grid kararı ver
- her exporttan önce shape kontrolü koy
- alignment doğrulama scripti yaz

---

## Risk 3 — Kaynak veri eksik / bozuk çıkar

### Neden olur?
Açık veri erişiminde eksik dosya, bozuk format veya kapsama eksikliği olabilir.

### Çözüm

- alternatif veri kaynağı planı hazır tut
- missing value stratejisi yaz
- fallback demo dataset bulundur

---

## Risk 4 — Thermal yorum belirsiz olur

### Neden olur?
Sıcaklık katmanı ile donanım toleransı arasında doğrudan ilişki net tanımlanmazsa risk skoru anlamsızlaşır.

### Çözüm

- sıcaklık birimini netleştir
- threshold tablosunu erken dondur
- 1. ve 2. kişi ortak varsayım dokümanı hazırlasın

---

## Risk 5 — Diğer ekip veriyi nasıl kullanacağını anlamaz

### Neden olur?
Dosyalar açıklamasız, birimsiz veya örnek yükleme kodu olmadan paylaşılabilir.

### Çözüm

- JSON metadata kullan
- `README.md` hazırla
- örnek Python load script ver

---

# Teslim Paketi İçeriği

Finalde `docs/` ve veri klasörlerinde aşağıdakilerin hazır olması önerilir:

## Dokümantasyon

- `docs/README.md`
- `docs/data_dictionary.md`
- `docs/preprocessing_notes.md`
- `docs/thermal_model_notes.md`
- `docs/risk_dictionary.md`

## Veri çıktıları

- `temperature_layer.tif` veya `temperature_layer.npy`
- `shadow_layer.tif` veya `shadow_layer.npy`
- `elevation_layer.tif` veya `elevation_layer.npy`
- `slope_layer.tif` veya `slope_layer.npy`
- `hazard_support_layer.npy`
- `thermal_risk_layer.npy`
- `thermal_cost_map.npy`
- `metadata.json`

## Demo paketleri

- düşük boyutlu örnek export
- örnek görselleştirme PNG’leri
- örnek yükleme scripti

---

# GitHub Docs İçin Kısa Özet

Bu doküman, hackathon kapsamında **1. kişi (Lunar Data & Preprocessing Engineer)** ile **2. kişinin (Thermal Modeling & Hardware Risk Engineer)** birlikte yürüteceği veri hazırlama ve thermal-risk üretim işlerini tanımlar.

Amaç; Ay yüzeyi verilerini işleyip hizalanmış çevresel katmanlara dönüştürmek, ardından bunları thermal-risk ve rota planlama için kullanılabilir hale getirmektir.

Bu çalışma paketinin sonunda ekip şu yetenekleri kazanmış olmalıdır:

- çevresel katmanları okuyabilen backend,
- thermal risk üretebilen analiz modülü,
- cost map kullanabilen rota planlama,
- güvenilir veri gösterebilen arayüz.

Bu nedenle bu iki kişinin çıktıları proje için kritik altyapıyı oluşturur.
