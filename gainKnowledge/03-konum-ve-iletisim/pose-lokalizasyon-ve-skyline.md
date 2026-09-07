# Poz, Lokalizasyon ve Skyline Eşleme — "Rover Şu An Tam Olarak Nerede?"

**Kodda:** `backend/app/pose.py`, `backend/app/localization.py`, `backend/app/localization_budget.py`, `backend/app/skyline.py`
**API:** `POST /api/pose`

---

## Nedir?

Dört parçalı bir katman:

1. **`pose.py`** — Rover'dan gelen konum tahmininin sözleşmesi. Ne kabul edilir, ne reddedilir.
2. **`localization.py`** — O konumu koridora göre yerleştirir: yolun neresindeyim, merkez çizgiden ne kadar saptım?
3. **`localization_budget.py`** — "Konum tahminim koridordan taşmadan önce kaç metre sürebilirim?"
4. **`skyline.py`** — Ufuk çizgisine bakarak mutlak konum bulma denemesi (GPS'siz dünyada tek sıfırlama yolu).

---

## Hangi problemi çözüyor?

Ay'da **GPS yok, pusula yok** (manyetik alan yok). Rover konumunu şöyle tahmin ediyor: "başlangıçta buradaydım, tekerleklerim şu kadar döndü, dolayısıyla şu kadar ilerledim."

Buna **ölü hesaplama (dead reckoning)** deniyor ve tek bir kusuru var: **hata birikir ve asla düzelmez.**

| Yöntem | Kayma (kat edilen mesafenin yüzdesi) |
|---|---|
| Ölü hesaplama (tekerlek + IMU) | **~%10** |
| Görsel odometri (VO) | **%0,5** (yayınlanmış aralık: %0,22–2,45) |
| VO + skyline sıfırlaması | Sıfırlamalar arası birikiyor, ama her sıfırlama sınırlıyor |

%10 kayma demek: **1 kilometre sürdükten sonra nerede olduğunuzu 100 metre hatayla biliyorsunuz.** Koridorunuzun yarı genişliği 50 metre ise, çoktan dışına çıkmışsınız ve haberiniz yok.

---

## Analoji: Gözü kapalı yürümek

Bir odada durun, çevrenize bakın, sonra gözlerinizi kapatın ve karşı duvara doğru yürüyün.

İlk birkaç adım gayet iyi. Ama 20 adım sonra? Muhtemelen düşündüğünüz yerden yarım metre sağdasınız. 100 adım sonra? Tamamen kaybolmuşsunuz.

Şimdi kritik soru: **gözlerinizi ne zaman açmalısınız?**

- Çok sık açarsanız → zaman kaybı (rover için: enerji ve süre kaybı)
- Çok geç açarsanız → koridorun dışına çıkmışsınızdır ve düzeltmek pahalı

`localization_budget.py` tam olarak bu sorunun cevabını veriyor: **"Ne kadar mesafede bir kez gözünüzü açmanız gerekiyor?"**

Ve `skyline.py` şu soruyu soruyor: **"Gözümü açtığımda ne göreceğim, ve o manzaradan nerede olduğumu anlayabilir miyim?"**

---

## 1. Poz sözleşmesi (`pose.py`)

### LunaPath odometri üretmiyor

Bu net bir sınır: LunaPath başkasının yazılım yığınının ürettiği odometriyi **tüketiyor** — tekerlek enkoderi, görsel odometri, LiDAR odometrisi. Bu modülde hiçbir şey poz tahmin etmiyor; sadece bir tahminin **kullanılabilir olması için neye benzemesi gerektiğini** söylüyor ve olmayanları reddediyor.

`schemas.Corridor` dışa giden sözleşme, `PoseEstimate` içeri gelen sözleşme. Simetrik bir çift, o yüzden ayrı dosyalar.

### Mesafe epoch'u — ince ama kritik

`distance_travelled_m` **koridorun başından** sayılıyor ve **her yeni planda sıfırlanıyor.**

**Neden:** Kayma kontrolü, koridor boyunca ilerlemeyi bu iddiaya bölüyor. Eğer rover açılıştan beri biriken toplam mesafeyi gönderirse, taze planlanmış bir koridora karşı bu "büyük iddiaya karşılık sıfıra yakın ilerleme" gibi okunuyor ve **kayma alarmı döngüye giriyor.**

ROS monitörü sıfırlamayı kendisi uyguluyor (yeni koridor integralini sıfırlıyor); HTTP çağıranlarının aynısını yapması gerekiyor. ("Round 2 review, M-6")

### Başlık konvansiyonu

`heading_deg` bir **grid azimutu**: 0 = satır azalan (grid Kuzey), 90 = sütun artan (grid Doğu), saat yönünde artıyor.

**Bu gerçek kuzeye göre DEĞİL.** Gerçek kuzeye göre bir başlık tutan bir tüketici (güneş sensörü, yıldız izleyici) önce `ephemeris.true_azimuth_to_grid_azimuth` ile döndürmeli. İki çerçeve sadece projeksiyonun merkez meridyeninde çakışıyor.

> Faz 2'de tam bu karışıklıktan bir bug çıktı. Konvansiyon şimdi modül başında yazılı, testlerde iddia ediliyor ve dönüşüm tek bir yerde yapılıyor.

---

## 2. Koridora yerleştirme (`localization.py`)

Bir pozu koridora göre projekte ediyor ve şunları söylüyor:

| Alan | Anlamı |
|---|---|
| `segment_index` | Koridorun kaçıncı parçasındayım |
| `lateral_offset_m` | Merkez çizgiden ne kadar saptım |
| `along_track_m` | Rota boyunca ne kadar ilerledim |
| `progress_fraction` | Yüzde kaçını tamamladım |
| `half_width_at_pose_m` | Burada izin verilen sapma ne kadar |
| `inside` | Koridorun içinde miyim |

**Bu modül hiçbir karar vermiyor.** Sadece geometri. Yeniden planlama kararı `replan_triggers`'a ait; bu modül onu `trigger_state_from_pose` ile besliyor.

> Bu modül var olmadan önce `replan_triggers` `corridor_violation` ve `localization_uncertainty` kontrollerini yapabiliyordu ama **girdilerini üreten hiçbir şey yoktu** — testlerde elle besleniyordu, üretimde kaynağı yoktu.

---

## 3. Lokalizasyon bütçesi (`localization_budget.py`)

### Model kasıtlı olarak en basit hâli

```
sigma(d) = sigma_0 + kayma_oranı × d
```

Yani 1-sigma yatay hata, kat edilen mesafeyle **doğrusal** büyüyor.

**Neden bu kadar basit?** Gerçek hata büyümesi daha karmaşık (araziye bağlı, kısmen stokastik, yönle korele). Ama yayınlanmış misyon rakamları **"kat edilen mesafenin yüzdesi"** olarak geliyor — ki bu zaten doğrusal bir oran. Doğrusal model, o rakamların dürüst kabıdır. Daha süslü bir model, girdilerin taşımadığı bir hassasiyet iddia ederdi.

### Bütçe nasıl hesaplanıyor?

`check_localization_uncertainty` tetikleyicisi, kovaryans koridorun yarı genişliğini aştığında ateşleniyor.

`sigma(d)` = yarı genişlik denklemini `d` için çözerseniz: **her şey nominal çalışsa bile o tetikleyicinin kesin olarak ateşleneceği mesafeyi** buluyorsunuz. Bu, iki mutlak konum düzeltmesi arasındaki mesafe bütçesi.

`scripts/localization_budget.py` bunu her odometri kaynağı için gerçek bir koridorun genişliklerine karşı tablolaştırıyor.

### Kayma oranları ve kaynakları

| Kaynak | Oran | Referans |
|---|---|---|
| Ölü hesaplama (tekerlek + IMU) | %10 | MER sınıfı — Maimone vd., *Two years of Visual Odometry on the Mars Exploration Rovers* |
| Görsel odometri | %0,5 | M2020 sınıfı VO için yayınlanmış %0,22–2,45 ATE bandının içinde |
| VO + skyline sıfırlaması | Sıfırlamalar arası birikir | Her güvenli eşleşme sınırlar |

### Sigma çarpanı — bir düzeltme

Tetikleyici eskiden **1 sigma**'yı yarı genişlikle karşılaştırıyordu. Bu, rover'ın koridor **dışında** olma ihtimali zaten üçte bire yaklaştığında ateşliyor demek — bir güvenlik kontrolü için geç.

**2 sigma**'ya çıkarıldı: bu ihtimali yirmide bire indiriyor, geleneksel mühendislik marjı. ("Round 3 review, L-9")

---

## 4. Skyline eşleme (`skyline.py`)

### Fikir

Ay'da GPS yok, manyetik alan yok. Peki biriken hatayı ne sıfırlayacak?

**Cevap: manzara.** Bulunduğunuz noktadan görünen ufuk çizgisi (skyline), o noktaya özgü bir imzadır — tıpkı parmak izi gibi.

Ve LunaPath'in elinde zaten `horizon.horizon_map()` var: her hücre ve her azimut için ufuk yüksekliği. **Bu dizi, bir skyline eşleyicinin ihtiyaç duyduğu referans veritabanının ta kendisi.**

> Bu dizi Faz 1'de gölge hesabı için yazıldı, Faz 5'te sanal LiDAR için tekrar kullanıldı, burada üçüncü kez kullanılıyor. **Aynı çekirdekten üç ürün.**

### Kapsam sınırı — net

LunaPath görüntüden skyline **çıkarmıyor**. O bir algılama (perception) problemi ve açıkça kapsam dışı. Bu modül, **zaten çıkarılmış** bir ufuk profilini alıp "bu hangi hücreye benziyor" sorusunu cevaplıyor.

### Bu bir ürün değil, bir fizibilite gösterimi

Kod bunu açıkça söylüyor. Sebebi:

5 m/piksel DEM'den hesaplanan bir ufuk profili, kameranın gerçekte gördüğünün **alçak geçiren filtrelenmiş** hâli:
- DEM'in çözünürlüğünün altındaki yakın topografya yok
- Işın yürüyüşünün menzilinin ötesindeki hiçbir şey yok

Gerçek görüntüyü buna karşı eşlemek için önce gözlemin aynı banda filtrelenmesi gerekir.

### Önemli olan başarısızlık modu: özelliksiz arazi

Düz bir platoda **her hücrenin ufku birbirine benzer.** En yüksek skorlu hücreyi döndüren bir eşleyici, kendinden emin bir saçmalık raporlar.

Bu yüzden `match_skyline` **her zaman `ambiguity_ratio` döndürüyor** ve `SkylineFix.is_confident`, ikinci sıradaki aday kazananla neredeyse aynı skoru aldığında **False** oluyor.

> *"Sessizce yanlış cevaplar, bu modülün önlemek için var olduğu tek sonuçtur."*

---

## Kodda nerede?

```
backend/app/pose.py
  PoseEstimate               ← içeri gelen sözleşme
  SLIP_CHECKABLE_SOURCES
  heading_deg konvansiyonu

backend/app/localization.py
  CorridorFix                ← koridora göre konum
  trigger_state_from_pose()  ← replan_triggers'a köprü

backend/app/localization_budget.py
  DRIFT_RATES                ← kaynaklı kayma oranları
  sigma(d) = sigma_0 + rate × d

backend/app/skyline.py
  match_skyline()            ← ufuk profili → hücre adayı
  SkylineFix.is_confident    ← belirsizlik koruması

scripts/localization_budget.py ← bütçe tablosu
```

---

## Jüri soruları

**S: "Rover konumunu nasıl biliyor?"**
Bilmiyor — tahmin ediyor, ve tahmini zamanla bozuluyor. LunaPath odometri üretmiyor; başkasının ürettiğini tüketiyor ve sahip olduğu yörünge DEM'ine karşı kontrol ediyor. Kritik katkımız hatanın *ne zaman* kabul edilemez hâle geleceğini hesaplamak.

**S: "GPS olmadan nasıl düzeltiyorsunuz?"**
Skyline eşlemeyle — ufuk çizgisinin her noktada benzersiz bir imza olması fikri. Ama bunu bir ürün olarak sunmuyoruz, bir arayüz ve fizibilite gösterimi olarak sunuyoruz. Görüntüden skyline çıkarma işi bizde değil.

**S: "%10 kayma çok fazla değil mi?"**
Çok fazla ve o yüzden ölçüyoruz. Bu sayı MER (Mars Exploration Rovers) misyonlarının yayınlanmış ölü hesaplama performansı. Görsel odometri %0,5'e indiriyor. Bizim kattığımız şey, bu oranların gerçek bir koridorun gerçek genişliklerine karşı ne anlama geldiğini tablolaştırmak: "şu odometriyle şu koridorda X metrede bir mutlak düzeltme lazım."

**S: "Skyline eşleme çalışıyor mu?"**
Düz platoda çalışmıyor ve bunu **kendisi söylüyor**. Her eşleşme bir belirsizlik oranıyla dönüyor; ikinci aday kazananla yakın skor aldığında sonuç "güvenli değil" işaretleniyor. Sessizce yanlış cevap vermek, bu modülün önlemek için tasarlandığı tek şey.

**S: "Model neden bu kadar basit?"**
Çünkü girdiler basit. Yayınlanmış misyon rakamları "mesafenin yüzdesi" formunda geliyor — bu zaten doğrusal bir oran. Doğrusal model o rakamların dürüst kabı. Daha karmaşık bir model, verinin taşımadığı bir hassasiyet iddia ederdi.
