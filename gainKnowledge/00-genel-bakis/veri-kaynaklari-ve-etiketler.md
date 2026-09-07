# Veri Kaynakları ve Güvenilirlik Etiketleri

> Bu, projenin en güçlü savunma hattı. Jüri "bu sayıya nasıl güveniyorsunuz?" diye sorduğunda cevap burada.

---

## Nedir?

LunaPath'in ürettiği her katmanın (harita) bir **güvenilirlik etiketi** var. Bu etiket, o katmanın gerçekten ölçülmüş NASA verisi mi, bir fizik modelinin tahmini mi, yoksa demo amaçlı üretilmiş sahte veri mi olduğunu söyler.

Etiket API cevabının içinde, HTTP başlığında (`X-Layer-Validity`) ve arayüzdeki rozette görünür. Kaybolmaz.

---

## Hangi problemi çözüyor?

Şu senaryoyu düşünün: sistem size "bu hücrenin sıcaklığı −173 °C" diyor. Bu sayıya ne kadar güvenmelisiniz?

- Eğer bu bir termometreyle ölçülmüş değerse → çok güvenirsiniz
- Eğer bir fizik modelinin çıktısıysa → modelin doğruluğu kadar güvenirsiniz
- Eğer "yükseklikten kabaca türetilmiş" bir tahminse → neredeyse hiç güvenmezsiniz

**Sorun şu ki üç durumda da ekranda aynı sayı görünüyor.** Etiket olmadan operatör bu ayrımı yapamaz. Ve daha kötüsü: bir demo verisi, gerçek veriymiş gibi sunum yapılırsa bu doğrudan yanıltmadır.

---

## Analoji: Gıda etiketi

Markette bir ürünün üstünde şunlar yazar: "organik", "doğal aromalı", "aroma benzeri". Üçü de aynı rafta, benzer paketlerde durur ama üçü tamamen farklı şey demektir. Etiket olmasa hepsi aynı görünürdü.

LunaPath'in etiket sistemi tam olarak bu. Dört rütbe var, en zayıftan en güçlüye:

| Etiket | Gıda analojisi | Anlamı | Örnek |
|---|---|---|---|
| `SYNTHETIC` | "aroma benzeri" | Demo için uydurulmuş | Termal grid'in yedek heuristiği |
| `DERIVED` | "doğal aromalı" | Başka veriden türetilmiş | Eğim (yükseklikten hesaplanır) |
| `MODEL` | "doğala yakın" | Bir fizik modelinin çıktısı | heat1d sıcaklık, slip eğrisi |
| `MEASURED` | "organik, sertifikalı" | Gerçekten ölçülmüş | LOLA yükseklik, LDRM pürüzlülük, PSR maskesi |

---

## Nasıl çalışıyor?

### En zayıf halka kuralı

Bir sonuç birden fazla katmandan besleniyorsa, sonucun etiketi **en zayıf girdinin etiketi** olur.

Örnek: maliyet haritası eğimden (`DERIVED`), sıcaklıktan (`MODEL`) ve pürüzlülükten (`MEASURED`) besleniyorsa, maliyet haritasının etiketi `MODEL` olur — çünkü zincir en zayıf halkası kadar güçlüdür.

Kodda bu `traversability.weakest_validity` fonksiyonu.

### Arayüzde üç seviyeye iniyor

Frontend'deki rozet üç seviyeli (NASA-STD-7009B "pedigree" kavramına göre): `measurement` / `model` / `demo`. `DERIVED` ve `MODEL` görüntüde birleşiyor. Ama **arka planda dört rütbe korunuyor** — en zayıf halka hesabı dört rütbe üzerinde yapılıp sonra görüntüye indiriliyor.

### "Hesaplayamadım" da bir cevaptır

En önemli kural: bir katman hesaplanamıyorsa sistem sahte bir varsayılan üretmez.

- Ufuk küpü diskte yoksa → gölge serisi `static` etiketiyle döner, "gerçek zaman değişimi hesaplanamadı" der
- NAIF kernel dosyaları yoksa → güneş konumu hesaplanamaz, ilgili uç `unavailable` döner ve **sebebini yazar**
- NASA klonları yoksa → belirsizlik uçları `None` döner, sahte bir belirsizlik uydurulmaz

Bu davranış kodda tekrar tekrar vurgulanmış: *"Nothing here fabricates a field it cannot compute."*

---

## Gerçek veri kaynakları — tam liste

### Ölçülmüş NASA ürünleri (`MEASURED`)

| Ürün | Ne veriyor | Kaynak |
|---|---|---|
| **LOLA LDEM** | Yükseklik haritası, 5 m/piksel | NASA LRO Lunar Orbiter Laser Altimeter |
| **LOLA LDRM** | Yüzey pürüzlülüğü, 50 m/piksel, 100 m taban çizgisi | PGDA ürün 90; Barker vd. 2023, *Planetary Science Journal* 4:183 |
| **LPSR (PSR maskesi)** | Kalıcı gölgeli bölgeler, 20 m/piksel, 506 349 bölge | NASA GSFC Planetary Geodesy |
| **PGDA ürün 78** | Z-belirsizliği (`toterr`), eğim belirsizliği, **100 istatistiksel DEM klonu** | Barker, Mazarico vd. |
| **PGDA ürün 69** | Ortalama Dünya görünürlüğü (18,6 yıllık) | Mazarico vd. 2011 |
| **NAIF SPICE kernelleri** | Güneş ve Dünya'nın gökyüzündeki konumu | NASA NAIF |

### Modeller (`MODEL`)

| Model | Ne veriyor | Not |
|---|---|---|
| **heat1d** | Regolit yüzey sıcaklığı, 1-B ısı difüzyonu | Hayne'in modeli. Kalibre edilmemiş. |
| **Slip eğrisi** | Eğime göre tekerlek kayması | Literatürden aktarılmış, kutup regolitinde ölçülmemiş |
| **Pürüzlülük ölçeği** | Pürüzlülüğü 0-1 arası maliyete çeviren eşleme | Bölgesel yüzdelik sıralaması; hiçbir rover pürüzlülük toleransı yayınlamıyor |

### Türetilmiş (`DERIVED`)

Eğim, bakı (aspect), ufuk haritası, gölge oranı — hepsi DEM'den hesaplanıyor.

### Sentetik (`SYNTHETIC`)

`thermal_grid.py` — heat1d kurulu değilse devreye giren yedek sıcaklık heuristiği. Çıktısı gittiği her yerde `SYNTHETIC` etiketli.

---

## Kodda nerede?

- `backend/app/traversability.py` → `weakest_validity` (en zayıf halka kuralı)
- `backend/app/ai_evidence.py` → `_VALIDITY_ORDER`, `_DISPLAY_PEDIGREE`
- `backend/app/roughness.py` → `ROUGHNESS_LAYER_VALIDITY`, `PSR_LAYER_VALIDITY`
- `backend/app/thermal_model.py` → `REGOLITH_LAG_VALIDITY`
- `backend/app/slip_model.py` → `SLIP_MODEL_VALIDITY = "MODEL"`
- HTTP başlığı: `X-Layer-Validity`
- `docs/DATA_LICENSES.md` → veri lisansları

---

## Jüri soruları

**S: "Bu veriler gerçek mi?"**
Yükseklik, pürüzlülük, PSR maskesi, DEM belirsizlik klonları ve gökcismi konumları gerçek NASA ürünleri — hepsinin ürün numarası ve yayın referansı kodda yazılı. Sıcaklık bir model çıktısı, kayma eğrisi literatürden aktarım. Hangisinin hangisi olduğunu sistem kendisi söylüyor.

**S: "Sentetik veri kullanıyor musunuz?"**
Sadece bir yerde: heat1d kütüphanesi kurulu değilse devreye giren yedek sıcaklık heuristiği. O çıktı `SYNTHETIC` etiketiyle dolaşıyor ve etiket API cevabından silinmiyor.

**S: "Neden bu kadar uğraştınız? Etiket olmasa ne olurdu?"**
Çünkü bu bir güvenlik sistemi. Bir operatörün "−173 °C" sayısını görüp de bunun ölçüm mü tahmin mi olduğunu bilmemesi, sistemin kendisinden daha tehlikeli. Ayrıca AI asistanı da bu etiketleri okuyor: hangi sayıyı hangi güvenle söyleyebileceğini etiketten öğreniyor.

**S: "En zayıf halka kuralı çok muhafazakâr değil mi?"**
Evet, kasıtlı olarak öyle. Bir sonuç ölçülmüş verilerle sentetik verinin karışımıysa, o sonucun tamamı sentetik kadar güvenilirdir. Alternatifi (ortalama almak) yanlış bir güven duygusu üretirdi.

**S: "Kalibre edilmemiş model kullanmak sorun değil mi?"**
Sorun, ancak sorun olduğunu söylemediğinizde. Termal modelimiz `MODEL/UNCALIBRATED` etiketli ve bu etiket her cevapta gidiyor. Diviner (NASA'nın gerçek termal ölçüm cihazı) verisiyle karşılaştırma altyapısı da hazır (`thermal_validation.py`) — sadece veri dosyası yerelde yok.
