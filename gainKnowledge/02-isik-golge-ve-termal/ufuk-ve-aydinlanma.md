# Ufuk Haritası ve Aydınlanma — Gölge Nereden Geliyor?

**Kodda:** `backend/app/horizon.py`, `backend/app/illumination.py`, `backend/app/illumination_series.py`
**API:** `GET /api/illumination-series`, `layers/shadow_ratio`

---

## Nedir?

İki aşamalı bir sistem:

1. **Ufuk haritası (horizon map):** Her hücreden 72 farklı yöne bakıp, "o yönde arazi kaç derece yükseliyor" sorusunun cevabı. Sadece topografyaya bağlı, zamana bağlı değil — bir kez hesaplanır.
2. **Aydınlanma:** Belirli bir anda Güneş'in gökyüzündeki konumu ile ufuk haritasını karşılaştırıp "bu hücre şu an ışık alıyor mu" sorusunun cevabı.

Kural tek satır: **Güneş'in yükseklik açısı, o yöndeki ufuk açısından büyükse hücre aydınlık.**

---

## Hangi problemi çözüyor?

Ay'ın güney kutbunda Güneş **ufka paralel** dolaşıyor — yükseklik açısı bir yıl boyunca sadece −2,59° ile +2,55° arasında değişiyor (Site11'de ölçüldü, enlem −88,92°).

Bunun sonucu dramatik: **10 metrelik bir tepe, kilometrelerce uzun gölge yapar.**

Dünya'da öğle vakti Güneş tepede olduğu için gölgeler kısadır. Ay kutbunda "öğle vakti" diye bir şey yok; Güneş sürekli ufukta. O yüzden gölge haritası Ay kutbunda navigasyonun **en belirleyici** girdisidir.

---

## Analoji: El feneriyle masa üstü

Bir masanın üstüne birkaç kitap koyun. Şimdi el fenerini:

- **Yukarıdan tutun** → kitaplar kendi altlarında küçük gölgeler yapar
- **Masa yüzeyine paralel, neredeyse yatay tutun** → kitapların gölgeleri masanın öbür ucuna kadar uzanır

Ay güney kutbu ikinci durumdur, her zaman.

Şimdi masanın üstündeki her nokta için sorun: "Buradan fenere doğru baktığımda, önümde bir kitap var mı ve o kitap fenerin hizasından yüksekte mi?" İşte ufuk haritası bu sorunun her nokta ve her yön için önceden hesaplanmış cevabıdır.

---

## Nasıl çalışıyor?

### 1. Ufuk haritası: ışın yürüyüşü (ray marching)

Her hücreden, 72 farklı azimut yönünde (5 derecede bir) bir ışın gönderilir. Işın arazi boyunca ilerlerken her adımda sorulur: *"buradan bakınca bu nokta kaç derece yukarıda?"* En büyük açı kaydedilir.

Sonuç: `(72, 500, 500)` boyutunda bir küp. Yani 18 milyon sayı.

**Azimut konvansiyonu:** 0 = Kuzey (satır azalıyor), 90 = Doğu (sütun artıyor). Bu konvansiyon `pose.py`, `ephemeris.py` ve `horizon.py`'de aynı — çünkü bir dönem karıştırıldı ve hata çıktı.

### 2. Örnekleme problemi ve çözümü

Burada gerçek bir performans/doğruluk hikâyesi var:

**Eski hâli:** Işın DEM'in her hücresinde bir adım atıyor ve toplam adım sayısı sınırlıydı. Sonuç: 5 m/piksel çözünürlükte, nominal 10 km'lik arama menzili fiilen **1 km'ye** düşüyordu.

**Neden ölümcül:** Kutup bölgesinde uzun gölgeyi yapan şey tam olarak **uzaktaki sırt**, düşük bir açıyla görünen. 1 km'de kesince o sırtı hiç görmüyorsunuz ve gölgeyi kaçırıyorsunuz.

**Çözüm — geometrik aralıklı yürüyüş:** Yakın alanda (400 m'ye kadar) her hücre ziyaret ediliyor, ötesinde adımlar logaritmik olarak açılıyor.

**Mantığı:** Uzaklaştıkça bir sırt daha az hücre kaplar. 5 km ötedeki bir sırtı 5 metrelik adımlarla taramak, hiçbir işe yaramayan çözünürlük satın almaktır.

**Ölçülen sonuç:** Yeni yöntem 10 km'ye, eskisinin 1 km için harcadığından daha az örnekle ulaştı — **117 saniyeye karşı 188 saniye**. Yani hem daha doğru hem daha hızlı.

### 3. Aydınlanma maskesi

```
aydınlık(hücre) = Güneş_yükseklik_açısı > ufuk_açısı[Güneş_azimut_kutusu][hücre]
```

### 4. Sentinel değeri — sessiz hatanın önlenmesi

Bir ışın DEM'in kenarından çıkıp hiç engel bulamazsa, oraya **−90 derece** yazılır. Bu bir "veri yok" işareti, "düz zemin" işareti değil.

**Neden önemli:** Eğer bu ayrım yapılmazsa, Güneş açıkça ufkun altındayken (−20°) o hücre aydınlık görünür — çünkü `−20 > −90`. Yani sistem geceyi gündüz sanır. ("Faz 1 final review, M1")

### 5. Zaman serisi — ve dürüstlük kuralı

4-D planlayıcının işe yaraması için maliyetin zaman içinde **değişmesi** gerekiyor. Değişmiyorsa "bekle, Güneş dönsün" kararı hiçbir şey kazandırmaz.

`build_shadow_series` gerçek seriyi üretmek için iki şeye ihtiyaç duyar:
1. Ufuk küpü (`horizon_map.npy` önbelleği)
2. NAIF SPICE kernelleri (Güneş'in nerede olduğunu bilmek için)

İkisinden biri yoksa, fonksiyon **statik** bir seri döndürür ve bunu `static` etiketiyle açıkça söyler.

> **Gerçek hata hikâyesi:** Bir dönem `main.plan_4d` seriyi `[temel_gölge] * dilim_sayısı` diye kuruyordu — yani aynı fotoğrafın T kopyası. Maliyet küpünün "hangi katmanlar zamanla değişiyor" testi doğru şekilde "gölge değişiyor" diyordu, sonra eline aynı görüntünün T kopyası veriliyordu. Beklemek hiçbir şey kazandırmıyordu ve `wait_steps` metriği araziyle ilgisi olmayan bir sebeple hep sıfır çıkıyordu. ("Round 3 review, M-1")

---

## Aynı çekirdek, üç ürün

Ufuk haritası projede üç kez kullanılıyor ve bu, iyi mimarinin göstergesi:

| Kullanım | Nasıl |
|---|---|
| **Gölge hesabı** (Faz 1) | Güneş açısı ufuk açısıyla karşılaştırılır |
| **Sanal LiDAR** (Faz 5) | Aynı ışın yürüyüşü çekirdeği tarama simülasyonunda |
| **Skyline eşleme** (konumlandırma) | Ufuk küpü, "bu manzara hangi hücreye benziyor" için referans veritabanı |

Ve dördüncüsü: aynı geometri Dünya için çalıştırılınca [Dünya görünürlüğü (A4)](../03-konum-ve-iletisim/dunya-gorunurlugu-dte.md) çıkıyor.

---

## İlham kaynağı

**Mazarico vd. 2011** — NASA'nın LOLA tabanlı aydınlanma ve Dünya görünürlüğü ürünlerinin arkasındaki yöntem. Ufuk açısı hesaplayıp gökcismi yüksekliğiyle karşılaştırma yaklaşımı buradan.

Bu, P1 veri hattındaki `1 − normalize(yükseklik)` gölge vekilinin yerini aldı — yani "yüksek yerler aydınlık, alçak yerler karanlık" gibi kaba bir tahminin yerine **gerçek ışın izleme geometrisi** kondu.

---

## Kodda nerede?

```
backend/app/horizon.py
  horizon_map()              ← (72, H, W) ufuk küpü
  march_distances_cells()    ← geometrik aralıklı yürüyüş
  DEFAULT_DENSE_RANGE_M      ← 400 m yakın alan
  _NO_HORIZON_DEG            ← −90 sentinel

backend/app/illumination.py
  illuminated_mask()         ← tek anlık maske

backend/app/illumination_series.py
  build_shadow_series()      ← zaman serisi (veya dürüst 'static')
  HORIZON_CACHE_FILENAME     ← horizon_map.npy

scripts/build_horizon_cache.py   ← küpü bir kez üretir
```

---

## Jüri soruları

**S: "Gölgeyi nasıl hesaplıyorsunuz?"**
Işın izlemeyle. Her hücreden 72 yöne ışın atıp arazi silüetinin açısını buluyoruz, sonra SPICE'tan gelen gerçek Güneş konumuyla karşılaştırıyoruz. Bu, NASA'nın LOLA aydınlanma ürünlerinde kullandığı yöntemin aynısı.

**S: "Neden 72 yön?"**
5 derecelik azimut çözünürlüğü. Güneş kutupta saatte yaklaşık 0,009 derece yükselirken azimutta daha hızlı dönüyor; 5 derece, gölge sınırının hassasiyeti ile 18 milyon sayılık küpün maliyeti arasındaki denge.

**S: "Ne kadar uzağa bakıyorsunuz?"**
10 km. Ve bu önemli — bir dönem kod 1 km'de kesiyordu ve kutupta uzun gölgeyi yapan tam da uzaktaki sırtlar. Geometrik aralıklı örneklemeyle 10 km'ye çıktık ve üstelik daha hızlı olduk (117 s / 188 s).

**S: "Güneş konumunu nereden alıyorsunuz?"**
NASA NAIF'in SPICE kernellerinden — gerçek efemeris verisi, gerçek tarih ve saat için. Kerneller yoksa sistem sahte bir Güneş uydurmuyor, `unavailable` diyor.

**S: "Aydınlanma haritanız doğru mu?"**
Bağımsız olarak doğrulandı: NASA'nın PSR (kalıcı gölgeli bölge) ürünüyle karşılaştırdık. Bizim `shadow_ratio ≥ 0,99` dediğimiz hücrelerle NASA'nın PSR'leri **Jaccard 0,830** ile örtüşüyor; PSR hücrelerinin %98,3'üne biz de karanlık diyoruz. Detay: [pürüzlülük ve PSR](../01-arazi-ve-veri/puruzluluk-ve-psr.md).

**S: "Belirsizlik var mı?"**
Var ve ölçüldü: NASA'nın 100 DEM klonuyla çalıştırdığımızda, 2027-05-30 tarihinde hücrelerin **%10,8'i** ışıklı mı karanlık mı olduğu söylenemiyor. Bu sayı her aydınlanma iddiasının yanında dolaşıyor.
