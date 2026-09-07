# Dünya Görünürlüğü / DTE (A4) — Rover Ne Zaman Komut Alabilir?

**Kodda:** `backend/app/earth_visibility.py`, `backend/app/visibility_validation.py`
**API:** `GET /api/earth-series`, `GET /api/comm-window`, `layers/earth_visibility`, `/api/plan-4d` içinde `require_earth_visibility`
**Özellik kodu:** A4

---

## Nedir?

DTE = **Direct-To-Earth** (Doğrudan Dünya'ya). Rover'ın antenini Dünya'ya doğrultup komut alabildiği durum.

A4, aydınlanma boru hattının **Dünya için çalıştırılmış hâli**: hangi hücreden, hangi anda Dünya görünüyor?

---

## Hangi problemi çözüyor?

**VIPER teleoperasyonla sürülüyor.** Yani rover otonom değil — Dünya'daki bir operatör onu sürüyor. Bunun doğrudan sonucu:

> **Rover sadece Dünya'ya radyo görüş hattı varken hareket eder. Ve her bacak, o linki koruyan bir noktada biter.**
> — Shirley & Balaban 2022

A4'ten önce LunaPath Güneş'i ayrıntılı modelliyordu, Dünya'yı hiç modellemiyordu. `check_comm_window` diye bir tetikleyici vardı ama girdisini dışarıdan bekliyordu — hiçbir yerden gelmiyordu, testlerde elle besleniyordu.

A4 o sayıyı **hesaplanan** bir sayıya çevirdi.

---

## Analoji: Vadideki cep telefonu çekmezliği

Dağda yürüyorsunuz. Telefon bazen çekiyor, bazen çekmiyor. Sebep basit: baz istasyonuyla aranızda bir tepe var mı yok mu.

Ama Ay'daki fark şu: **baz istasyonu hareket ediyor.** Dünya, Ay'ın gökyüzünde sabit durmuyor — librasyon denen bir salınımla ufkun 7 derece üstü ile 7 derece altı arasında, **27 günlük** bir döngüyle gidip geliyor.

Yani: bulunduğunuz noktadan Dünya'yı görüp görmemeniz iki şeye bağlı — (a) önünüzde tepe var mı, (b) Dünya şu anda ufkun üstünde mi.

Ve kritik detay: **Dünya ufkun altına indiğinde hiçbir yerden komut gelmiyor.** Bu iki hafta sürebilir. O iki hafta boyunca rover kendi başına.

---

## Nasıl çalışıyor?

### Aynı geometri, farklı hedef

Güneş için yazılan boru hattı, hedef değiştirilerek Dünya için çalıştırılıyor:

```
SPICE vektörü → yerel azimut/yükseklik → grid azimutu → arazi ufku ile karşılaştır
```

Kural aynı: **hücre bir gökcismini, o cismin yerel yükseklik açısı, cismin azimutundaki arazi ufuk açısını aştığında görür.**

Bu, Mazarico vd. 2011'in yöntemi — NASA'nın LOLA Dünya görünürlüğü ürünlerinin arkasındaki metot.

### Farklı zaman ölçeği — mimari sonuç

| Alan | Değişim ölçeği |
|---|---|
| Güneş görünürlüğü | **Saatler** |
| Dünya görünürlüğü | **Günler** |

Dünya'nın yükseklik açısı ~27 günlük periyotla −7° ile +7° arasında salınıyor. Bu yüzden Dünya alanı Güneş alanı gibi saatlik dilimlenmiyor.

### Üç tüketici

| Ürün | Ne yapar |
|---|---|
| **Uzun dönem oran katmanı** (`earth_visibility_grid.npy`) | LOLA'nın "ortalama Dünya görünürlüğü" ürününün bizim penceremiz için hesaplanmış hâli. `scripts/build_earth_visibility_cache.py` bir kez üretir. |
| **Dilim başına seri** | `/api/earth-series` ve 4-D planlayıcı için |
| **`comm_window`** | Hücre başına **ileri arama**: "bu noktadan link ne kadar süre daha var?" |

`comm_window` sayesinde `check_comm_window` tetikleyicisinin `comm_minutes_remaining` girdisi artık gerçek. Link yoksa **0** dönüyor — çünkü VIPER linksiz sürmez.

### Planlayıcıya nasıl giriyor?

`require_earth_visibility = true` olduğunda:

- **Linki olmayan bir hücreye varan her HAREKET reddediliyor**
- **Bekleme kısıtlanmıyor** — çünkü rover linksiz bir yerde *durabilir*, sadece oraya *süremez*

Çıktılar: `path_earth_visible`, `metrics.moves_out_of_earth_view`.

`/api/replan` ve `/api/pose` de iletişim penceresini artık geometriden dolduruyor.

### Dürüstlük kuralı

`illumination_series.build_shadow_series` gibi, bu modül de hesaplayamadığı bir alanı uydurmuyor:

- Seri kurulamıyorsa → `static` (uzun dönem katmandan) veya `unavailable`
- Her iki durumda da **sebep açıkça yazılıyor**

---

## Doğrulama — projenin en önemli sayısı

A4, projedeki **ilk modellenmiş katmanın ölçülmüş bir NASA ürününe bağlandığı** yer.

**Referans:** LOLA "Average Earth Visibility" ürünü (PGDA 69; Mazarico vd. 2011) — 18,6 yıllık saatlik Dünya görünürlüğü, 85–90° Güney için 60 m/piksel.

**Sonuç:**

| Ölçüm | Değer |
|---|---|
| Örnek sayısı | 163 162 |
| **RMSE** | **0,087** |
| **Pearson r** | **0,960** |
| 0,5 eşiğinde uyuşmazlık | %9,4 (1 681 hücre) |

Yani bizim hesapladığımız Dünya görünürlüğü oranları, NASA'nın 18,6 yıllık ölçümüyle **%96 korelasyonla** örtüşüyor.

---

## Bu doğrulama iki eski hatayı buldu

Bu kısım çok değerli — doğrulamanın neden yapıldığını gösteriyor.

### Hata 1: Grid yanlış pencereden üretilmişti

**Belirti:** İlk koşum RMSE **0,665** ve Pearson r **−0,16** verdi. Yani korelasyon neredeyse sıfır, hatta hafif negatif.

**Sebep:** İşlenmiş grid'ler yanlış DEM penceresinden üretilmişti. Pencere merkezi ve kuzey dönüşü **40 kilometre kaymıştı.**

**Düzeltme:** Site11 DEM'i yeniden indirildi, P1 veri hattı yeniden koşuldu. Sonuç: `metadata.json` byte-eşit çıktı ve RMSE 0,087'ye düştü.

**Ders:** Bu hata olmasaydı, sistem 40 km ötedeki bir arazi için plan yapmaya devam ederdi ve **hiç kimse fark etmezdi**. Dış bir referansla karşılaştırma, iç tutarlılığın yakalayamayacağı hatayı yakalar.

### Hata 2: Işın menzili uzak ufku kesiyordu

**Belirti:** Krater kenarından bakıldığında, ufuk 10 km içinde 20 derece düşüyor ve **karşı krater duvarı hiç görülmüyordu.**

**Sebep:** Işın yürüyüşünün menzili 10 km'de kesiliyordu. Ama kutup kraterleri bundan büyük.

**Düzeltme:** `build_horizon_cache.py` artık LOLA'nın 40 m çözünürlüklü kutup DEM'ini **10–150 km** aralığında da tarıyor.

**Etkisi:**
- Uzak alan (azimut, hücre) çiftlerinin **%27,5'inde** ufuk ortalama **4,2° yükseldi**
- Işıklı oran zirvesi ~**%47'ye** çıktı
- **Terminatör tarihleri kaydı** (yani gündüz/gece geçiş anları değişti)

**Ders:** Bu sadece Dünya görünürlüğünü değil, **gölge hesabını da** düzeltti. Uzak sırt görülmüyorsa gölge de hesaplanamaz.

---

## İlham kaynağı

- **Shirley & Balaban 2022**, *An Overview of Mission Planning for the VIPER Rover* — DTE kısıtının misyon planlamasındaki merkezî rolü
- **Mazarico vd. 2011** — ufuk açısı yöntemi, NASA'nın LOLA Dünya görünürlüğü ürünlerinin temeli
- **PGDA ürün 69** — doğrulama referansı

---

## İddia sınırı

✅ **Söylenebilir:** *"Dünya görünürlüğü katmanımız NASA'nın LOLA ürünüyle doğrulandı; RMSE 0,087, Pearson r 0,960."*

Bu, projede kurabildiğimiz en güçlü doğrulama cümlesi.

---

## Kodda nerede?

```
backend/app/earth_visibility.py
  comm_window()                    ← ileri arama, kalan link süresi
  earth_visibility_grid.npy        ← uzun dönem oran katmanı

backend/app/visibility_validation.py
  ← saf karşılaştırma fonksiyonu (dosya indirme/kırpma dışarıda)

scripts/build_earth_visibility_cache.py
scripts/earth_visibility_validation.py
docs/research/earth_visibility_validation.md
```

---

## Jüri soruları

**S: "Neden Dünya görünürlüğü önemli?"**
Çünkü VIPER teleoperasyonla sürülüyor — yani Dünya'dan komutla. Link yoksa rover hareket edemez. Dünya, Ay gökyüzünde 27 günlük bir salınımla ufkun 7 derece üstü ve altı arasında gidip geliyor; iki hafta boyunca hiç görünmeyebiliyor. O iki hafta rover'ın kendi başına hayatta kalması gereken süre — [safe haven](../04-planlama-ve-maliyet/safe-haven.md) tam da bu problemi çözüyor.

**S: "Bu katmanı doğruladınız mı?"**
Evet ve bu projenin en güçlü doğrulaması: NASA'nın 18,6 yıllık LOLA Dünya görünürlüğü ürünüyle 163 162 örnek üzerinde karşılaştırdık. RMSE 0,087, Pearson r 0,960.

**S: "Doğrulama size ne kazandırdı?"**
İki büyük hata buldu. Birincisi: grid'lerimiz 40 km kaymış bir pencereden üretilmişti — RMSE 0,665, korelasyon −0,16 çıkınca anlaşıldı. İç tutarlılık testleri bunu asla yakalayamazdı, çünkü sistem kendi içinde tutarlıydı, sadece yanlış yerdeydi. İkincisi: ışın menzilimiz 10 km'de kesiliyordu ve krater karşı duvarları görülmüyordu; 150 km'ye çıkarınca uzak alan çiftlerinin %27,5'inde ufuk 4,2 derece yükseldi ve terminatör tarihleri kaydı.

**S: "Bekleme neden kısıtlanmıyor?"**
Çünkü rover linksiz bir yerde durabilir — sadece oraya süremez. Sürüş komut gerektiriyor; durmak gerektirmiyor. Bu ayrım VIPER'ın operasyon konseptinden geliyor.

**S: "Dünya'yı modellemek Güneş'i modellemekten farklı mı?"**
Geometri aynı, zaman ölçeği farklı. Güneş saatlerde değişiyor, Dünya günlerde. Bu yüzden Güneş alanı saatlik dilimlerle örnekleniyor, Dünya alanı için uzun dönem oran katmanı + kaba seri yeterli.
