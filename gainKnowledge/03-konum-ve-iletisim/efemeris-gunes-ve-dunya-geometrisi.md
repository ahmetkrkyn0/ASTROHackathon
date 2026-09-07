# Efemeris — Güneş ve Dünya Gökyüzünde Nerede?

**Kodda:** `backend/app/ephemeris.py`
**Bağımlılık:** NASA NAIF SPICE kernelleri (`kernels/lunapath.tm`)

---

## Nedir?

Efemeris = gökcisimlerinin konum tablosu. Bu modül, **belirli bir tarih ve saatte, Ay yüzeyindeki belirli bir noktadan bakıldığında Güneş'in ve Dünya'nın gökyüzünde nerede olduğunu** hesaplıyor.

Çıktı iki sayı: **azimut** (hangi yönde, 0–360°) ve **yükseklik** (ufuktan kaç derece yukarıda).

---

## Hangi problemi çözüyor?

Gölge hesabı ve iletişim hesabı, ikisi de "gökcismi nerede" bilgisine muhtaç:

- **Gölge:** Güneş'in yükseklik açısı, o yöndeki arazi ufkundan büyük mü? → aydınlık
- **İletişim:** Dünya'nın yükseklik açısı, o yöndeki arazi ufkundan büyük mü? → radyo linki var

Yani ufuk haritası tek başına hiçbir şey söylemez. Onu anlamlı kılan, **gerçek bir tarihte gökcisminin gerçek konumu.**

---

## Analoji: Güneş saatinin tersi

Bir güneş saati, gölgeye bakıp saati söyler. Efemeris tam tersini yapar: **saate bakıp gölgenin nerede olacağını söyler.**

Ve şunu doğru yapması gerekir: 2027-05-30 saat 14:00'te, Ay'ın güney kutbunda −88,92° enleminde duruyorsanız, Güneş tam olarak hangi yönde ve kaç derece yukarıda? Bu, gezegenlerin ve Ay'ın yörünge mekaniğini gerektiren bir hesap — tahmin edilemez, hesaplanması gerekir.

---

## Nasıl çalışıyor?

### Bilinçli ikiye bölünme

Modül kasıtlı olarak iki parçaya ayrılmış:

| Parça | Ne yapar | Dış veri gerekir mi? | Test edilebilir mi? |
|---|---|---|---|
| **Saf geometri** (`sun_azel_from_vector`) | Bir vektörü azimut/yükseklik açısına çevirir | Hayır | Evet, doğrudan |
| **SPICE destekli** (`body_vector_body`, `sun_track`) | Gökcismi vektörünü gerçek zamanda hesaplar | Evet, NAIF kernelleri | Sadece sahte spiceypy ile |

**Neden bu ayrım:** Matematik kısmı kerneller olmadan test edilebiliyor. Kernel gerektiren kısım ise sadece "doğru kütüphaneyi doğru çağırıyor muyum" sorusu.

### SPICE nedir?

**SPICE**, NASA'nın NAIF (Navigation and Ancillary Information Facility) grubunun ürettiği, uzay misyonlarının standart geometri kütüphanesi. Gerçek yörünge verisiyle beslenmiş "kernel" dosyaları var; bunlar sayesinde herhangi bir tarih için gökcismi konumu hesaplanabiliyor.

Kerneller `lunapath/src/fetch_kernels.py` ile indiriliyor ve repo kökündeki `kernels/` klasörüne yazılıyor.

### Azimut konvansiyonu

`horizon.py` ile aynı: **0 = Kuzey, 90 = Doğu, aralık [0, 360).**

Ayrıca `true_azimuth_to_grid_azimuth` fonksiyonu var: gerçek kuzeye göre bir açıyı grid kuzeyine çeviriyor. İkisi sadece projeksiyonun merkez meridyeninde çakışıyor.

> **Gerçek hata hikâyesi:** Faz 2'de tam olarak bu karışıklıktan bir bug çıktı. Şimdi konvansiyon modül dokümanında yazılı, testlerde iddia ediliyor ve çeviri tek bir yerde yapılıyor — her çağrı yerinde satır içinde değil.

### Türkçe karakter hatası — güzel bir detay

Bu, gerçek dünya yazılımının nasıl olduğunu gösteren bir örnek:

**Problem:** CSPICE bir C kütüphanesi. `furnsh_c` fonksiyonu dosya yolunu **dar bayt dizisi** olarak alıyor. Yani ASCII olmayan karakterli bir yol (mesela Windows'ta `C:/Users/Oğuzhan` gibi bir kullanıcı profili) ona bozuk ulaşıyor ve `SPICE(NOSUCHFILE)` hatası veriyor — diskte açıkça duran bir dosya için.

**Neden çift kafa karıştırıcı:** Hata mesajı bozulmuş yolu yazdırıyor, yani dosya eksikmiş gibi görünüyor, ulaşılamaz olduğu anlaşılmıyor.

**Çözüm:** Windows'ta 8.3 kısa dosya adı kullanmak — tanım gereği ASCII. Diğer her durum (zaten ASCII yollar, Windows olmayan sistemler, 8.3 üretimi kapalı diskler) değişmeden geçiyor.

Fonksiyon: `ascii_safe_path()`

### Yol çözümlemesi

Kernel yolu, çalışma dizinine göre değil `__file__` üzerinden çözülüyor. Sebebi: belgelenmiş veri hattı çağrısı `cd lunapath/src && python process_lunar_data.py` şeklinde ve o dizinde `kernels/lunapath.tm` göreli yolu hiçbir zaman çözülmüyor (çünkü `fetch_kernels.py` **repo köküne** yazıyor).

---

## Site11'de ölçülen

| Ölçüm | Değer |
|---|---|
| Güneş yüksekliği aralığı, bir yıl (−88,92° enlem) | **−2,59° … +2,55°** |
| Güneş'in tırmanma hızı | ~**0,009 °/saat** |
| Dünya'nın yükseklik salınımı (librasyon) | ~**−7° … +7°** |
| Dünya librasyon periyodu | ~**27 gün** |

**Bu sayıların anlamı:**

- Güneş 5 derecelik bir bantta geziniyor → gölgeler çok uzun, çok yavaş hareket ediyor
- Dünya 14 derecelik bir bantta salınıyor ve periyodu 27 gün → **iletişim penceresi saatlerde değil, günlerde değişiyor**

Bu ikinci nokta mimari bir sonuç doğuruyor: Güneş alanı saatlik dilimlerle örnekleniyor, Dünya alanı ise günlerle. İkisi farklı zaman ölçeklerinde yaşıyor.

---

## İlham kaynağı

NASA NAIF SPICE — uzay misyonu geometrisinin fiili standardı. Neredeyse her gezegen misyonu bunu kullanıyor.

---

## Kodda nerede?

```
backend/app/ephemeris.py
  sun_azel_from_vector()          ← saf geometri, kernelsiz test edilir
  body_vector_body()              ← genel gökcismi vektörü
  sun_vector_body()               ← Güneş sarmalayıcısı
  earth_vector_body()             ← Dünya sarmalayıcısı
  sun_track()                     ← zaman serisi
  true_azimuth_to_grid_azimuth()  ← çerçeve dönüşümü, tek yer
  ascii_safe_path()               ← Windows non-ASCII yol düzeltmesi

lunapath/src/fetch_kernels.py     ← kernelleri indirir
kernels/lunapath.tm               ← meta-kernel
```

---

## Jüri soruları

**S: "Güneş konumunu nasıl biliyorsunuz?"**
NASA NAIF'in SPICE kütüphanesi ve gerçek yörünge kernelleriyle. Bu, uzay misyonlarının standart geometri aracı — tahmin veya yaklaşım değil, gerçek efemeris.

**S: "Kerneller yoksa ne oluyor?"**
Sistem sahte bir Güneş uydurmuyor. Aydınlanma zaman serisi `static` etiketiyle dönüyor ("gerçek zaman değişimi hesaplanamadı"), ilgili uçlar `unavailable` diyor ve sebebini yazıyor.

**S: "Dünya'yı da mı modelliyorsunuz?"**
Evet, ve aynı boru hattıyla. Güneş için yazılmış geometri zinciri (SPICE vektörü → yerel azimut/yükseklik → grid azimutu → arazi ufku) hedefi değiştirerek Dünya için de çalışıyor. Detay: [Dünya görünürlüğü (A4)](dunya-gorunurlugu-dte.md).

**S: "Güneş sadece 5 derecelik bir bantta mı geziniyor?"**
Site11'in enleminde (−88,92°) evet: bir yıl boyunca −2,59° ile +2,55° arası. Bu, Ay kutbunun navigasyonu neden bu kadar zorlaştırdığının kökü — Güneş neredeyse hiç yükselmiyor, o yüzden gölgeler kilometrelerce uzuyor ve çok yavaş hareket ediyor.

**S: "Türkçe karakterli klasör yolu hikâyesi nedir?"**
CSPICE bir C kütüphanesi ve dosya yollarını dar bayt dizisi olarak alıyor. Windows'ta `C:/Users/Oğuzhan` gibi bir yol ona bozuk ulaşıp "dosya yok" hatası veriyor — dosya orada olduğu hâlde. 8.3 kısa dosya adına çevirerek çözdük. Türkiye'de geliştirme yapan herkesin başına gelebilecek, gerçek bir taşınabilirlik sorunu.
