# Pürüzlülük ve PSR Maskesi (C4) — Kayaları Göremeyen Haritanın Çözümü

**Kodda:** `backend/app/roughness.py`, `scripts/build_roughness_cache.py`
**API:** `GET /api/psr-validation`, `layers/roughness`, `layers/psr`
**Özellik kodu:** C4

---

## Nedir?

İki ayrı NASA ürünü sisteme sokuluyor:

1. **LDRM — LOLA Digital Roughness Map.** Yüzeyin ne kadar "engebeli" olduğunun ölçülmüş haritası. Maliyet motoruna **beşinci kriter** olarak giriyor.
2. **PSR maskesi.** Kalıcı gölgeli bölgelerin (Permanently Shadowed Regions) haritası. Planlamaya **girmiyor** — bizim kendi gölge modelimizi doğrulamak için kullanılıyor.

---

## Hangi problemi çözüyor?

5 metre çözünürlüklü bir yükseklik haritası, **1 metrelik bir kayayı göremez**. O kaya, hücrenin ortalama yüksekliğine karışıp kaybolur. Ama rover için o kaya çok gerçektir — tekerleğe çarpar, aracı devirir, yolu keser.

Yani bu bir "harita çözünürlüğünün altındaki tehlike" problemi. Ve pürüzlülük bunun **istatistiksel vekilidir**: kayanın nerede olduğunu bilmesek de, "bu bölgede kaya olma ihtimali yüksek" diyebiliriz.

İkinci problem: C4'ten önce sistemdeki tek gerçekten ölçülmüş katman yükseklikti. Geri kalan her şey ya ondan türetiliyor ya modelleniyordu. C4 sisteme **ikinci ve üçüncü bağımsız ölçüm** getirdi.

---

## Analoji: Yol yüzeyi ile çukur haritası

Bir yol haritası size yolun nereden geçtiğini ve rakımını söyler. Ama yolun **asfaltı mı yoksa bozuk parke mi** olduğunu söylemez. İkisi de haritada aynı çizgidir; sürüş deneyimi tamamen farklıdır.

Pürüzlülük tam olarak bu: haritada görünmeyen ama sürüşü belirleyen yüzey kalitesi.

PSR maskesi ise başka bir analoji: **kendi hesabınızı hazır bir cevap anahtarıyla kontrol etmek.** Biz gölgeyi kendi ufuk hesabımızla buluyoruz. NASA da kalıcı gölgeli bölgelerin haritasını ayrıca yayınlamış. İkisini üst üste koyup "benim karanlık dediğim yerler NASA'nın karanlık dedikleriyle örtüşüyor mu?" diye bakıyoruz.

---

## Nasıl çalışıyor?

### Pürüzlülük nedir, tam olarak?

NASA'nın kendi tanımı (ürün sayfasından):

> *"LOLA noktalarının, LDEM'e uydurulmuş bir düzlem etrafındaki yükseklik artıklarının yayılımı — çapı M metre olan dairesel bir pencere içinde."*

Türkçesi: bir daire çizin, içine bir düzlem oturtun, gerçek ölçüm noktalarının o düzlemden ne kadar saptığına bakın. Sapma büyükse yüzey engebeli.

**Taban çizgisi (baseline)** dairenin çapı. Biz 100 metrelik tabanı kullanıyoruz.

### Ne yapıldı?

1. NASA'nın 50 m/piksel pürüzlülük ürünü ve 20 m/piksel PSR haritası, `/vsicurl/` ile uzaktan okundu
2. Planlama penceresine (Site11) kırpıldı
3. En yakın komşu (nearest neighbour) yöntemiyle 5 m'lik grid'e ko-registre edildi
4. İşlenmiş grid'lerin yanına önbellek olarak yazıldı

### Yazmadan önce iki kontrol

Bu kısım metodolojik olarak önemli — veriyi körü körüne kabul etmiyoruz:

**Kontrol 1 — Projeksiyon eşleşmesi.** İki ürünün projeksiyon *parametreleri* bizim grid'imizle aynı mı? (Adlar farklı yazıyor: bizimki "unnamed", NASA'nınki "Moon (2015) - Sphere / Ocentric / South Polar" — ama parametreler eşit.)

**Kontrol 2 — Eğim sıralaması.** NASA'nın kendi 100 m düzlem-uyum eğimi, bizim 5 m eğimimizin blok ortalamasıyla aynı sırada mı? Ölçüldü: **2 500 blokta Spearman korelasyonu 0,989**. Kod, bu değer 0,9'un altına düşerse veriyi yazmayı **reddediyor**.

> Bu kontrol bir hata da yakaladı: metadata orijininin hücre (0,0)'ın *sol üst köşesi* olduğu doğrulandı — A4'ün yardımcı fonksiyonu hücre *merkezi* varsayıyordu. İki ürün için de 2,5 m'lik alt-piksel kayması düzeltildi.

### Maliyete nasıl giriyor?

```
maliyet = (eğim×0.409 + enerji×0.259 + gölge×0.142 + termal×0.190)  ← dört terimli gövde
        + pürüzlülük × 0.15                                          ← C4'ün eklediği
```

Kritik tasarım: beşinci terim dört terimli toplamdan **sonra** ekleniyor. Yani pürüzlülük katmanı diskte yoksa, gövde eski v4 formülünün **işlem-işlem aynısı** olarak çalışıyor. Bu SHA-256 ile kilitli: katman kaldırıldığında eski özet değerleri byte-byte geri geliyor.

`COST_MODEL_ID` v4'ten **v5**'e yükseltildi.

### Pürüzlülüğü 0-1 arasına çevirme

Ham pürüzlülük metre cinsinden (0,4 m ile 4,87 m arası). Maliyet kriteri 0-1 arası olmalı. Çeviri: hücrenin **80–90° Güney bölgesindeki yüzdelik sırası**. Yani "bu hücre bölgedeki hücrelerin yüzde kaçından daha pürüzlü?"

Bu ölçek `MODEL` etiketli — çünkü ham veri ölçüm ama bu eşleme bizim seçimimiz.

---

## Site11'de ölçülen gerçek sayılar

| Ölçüm | Değer |
|---|---|
| Pürüzlülük medyanı (100 m taban) | **0,83 m** (p5: 0,40 · p95: 1,78 · maks: 4,87) |
| 200 / 400 / 800 / 1600 m tabanlarda medyan | 1,69 / 3,30 / 7,80 / 23,6 m |
| Hurst üsteli medyanı | 0,92 |
| Bölge medyanı (karşılaştırma için) | 0,57 m |
| `f_roughness` yayılımı Site11'de | p5 0,23 – p95 0,98 |

### Pürüzlülük eğimin tekrarı değil — kanıt

Bu önemli bir soru: "pürüzlülük zaten eğimle aynı şeyi mi ölçüyor?" Cevap hayır ve ölçüldü:

| Karşılaştırma | Spearman |
|---|---|
| Pürüzlülük ↔ eğim (5 m) | **0,213** |
| Pürüzlülük ↔ blok ortalama eğim | 0,227 |
| Pürüzlülük ↔ blok maksimum eğim | 0,321 |

0,2 civarı korelasyon, "birbirinden büyük ölçüde bağımsız" demek. Yani beşinci kriter gerçekten yeni bilgi taşıyor.

Zayıf bir eğilim var: medyan pürüzlülük 0–5° kuşağından >20° kuşağına 0,72 → 1,08 m yükseliyor. Bu, literatürün (PSJ 2025) beklediği yön.

### PSR doğrulaması — kendi gölgemizi test ettik

| Ölçüm | Sonuç |
|---|---|
| PSR ↔ bizim `shadow_ratio ≥ 0,99` | **Jaccard 0,830** |
| PSR hücrelerinin karanlık dediğimiz oranı | %98,3 |
| Bizim karanlık dediklerimizin PSR olma oranı | %84,2 |
| Ürünün kendi 20 m bloklarında Jaccard | 0,912 |
| PSR maskesi içinde ortalama gölge | 0,998 |
| PSR maskesi içinde medyan soğuk uç sıcaklık | −183,15 °C |

**Bu, projedeki en güçlü doğrulamalardan biri:** kendi ufuk hesabımızdan çıkan gölge haritası, NASA'nın bağımsız PSR ürünüyle %83 örtüşüyor.

### Rotaya etkisi

LPR-1 ay gecesi rotası, `w_roughness = 0,15`'te:
- Rota pürüzlülüğü 0,75 → **0,66 m** düştü
- Mesafe aynı kaldı: 2,727 km
- Enerji 1 465,7 → **1 519,4 Wh** (+%3,7) yükseldi

**Yorumu:** daha düz zemin **enerjiyle satın alınıyor**. Rover daha pürüzsüz ama biraz daha uzun/dik bir yol seçiyor.

VIPER standart rotası ise `w = 0,20`'ye kadar hiç değişmiyor.

---

## PSR neden planlamaya girmiyor? (Kasıtlı karar)

Üç sebep:

1. **VIPER'ın bilim hedefleri PSR'lerin içinde.** Su buzu orada. PSR'yi yasaklamak, misyonun amacını yasaklamak olur.
2. **Zaten kapalı.** Soğuk uç termal kapısı, Site11'in 14 016 PSR hücresinin **13 933'ünü** LPR-1 için zaten geçilemez yapıyor. Ayrı bir kural gereksiz.
3. **Gölge ve termal kriterleri karanlığı zaten fiyatlıyor.** Üçüncü bir ceza çifte sayım olurdu.

Bunun yerine PSR: bir katman, hücre kartında `in_psr` alanı, rota bloğunda `cells_in_psr` sayacı ve `GET /api/psr-validation` ucu.

---

## İlham kaynağı

**Barker vd. 2023**, *Planetary Science Journal* 4:183 — NASA GSFC Planetary Geodesy grubunun güney kutbu yayını. PGDA ürün 90 (pürüzlülük), PSR haritası (LPSR, 506 349 bölge). Veri DOI: `10.60903/gsfcpgda-lola-spole`.

---

## İddia sınırları — bunları söyleyemeyiz

Bu bölüm jüri için kritik:

- ❌ **"Kaya haritamız var"** — Hayır. Pürüzlülük bir kaya sayımı değil, istatistiksel bir yayılım ölçüsü.
- ❌ **"Her 5 m hücrenin pürüzlülüğünü biliyoruz"** — Hayır. Veri 50 m/pikselde ve 100 m tabanlı. Her 5 m hücre, kendisini kapsayan 50 m pikselin **hektometre ölçekli blok istatistiğini** taşıyor.
- ❌ **"Diviner kaya bolluğu kullanıyoruz"** — Hayır. O ürün 80–90° Güney'i kapsamıyor ve kullanılmadı.
- ⚠️ **`w_roughness = 0,15` bir varsayım.** Raporda 0–0,3 arası süpürüldü. Katalogdaki hiçbir rover kaynaklı bir pürüzlülük toleransı (yer açıklığı, tekerlek çapı) bildirmiyor, o yüzden uydurulmadı — ölçek rover'dan bağımsız.

✅ **Söyleyebileceğimiz:** "Yüzey pürüzlülüğü NASA'nın ölçülmüş LOLA verisiyle beşinci planlama kriteri olarak sisteme girdi ve eğimin tekrarı olmadığı korelasyonla gösterildi."

---

## Kodda nerede?

```
backend/app/roughness.py           ← ürün sabitleri, [0,1] ölçeği, PSR örtüşme istatistiği
scripts/build_roughness_cache.py   ← NASA ürünlerini indirip ko-registre eder
scripts/roughness_psr_report.py    ← ölçüm raporunu üretir
docs/research/roughness_psr_report.md
```
88 yeni test eklendi.

---

## Jüri soruları

**S: "Pürüzlülük ölçülmüş veri mi?"**
Katman evet — NASA'nın LOLA nokta artıklarından hesapladığı istatistik, `MEASURED`. Ama onu 0-1 maliyete çeviren ölçek bizim, o `MODEL`. Bu ayrım kodda açıkça yapılıyor.

**S: "Neden ağırlık 0,15?"**
Varsayım. 0'dan 0,3'e kadar süpürdük ve etkisini ölçtük. Hiçbir rover üreticisi "şu pürüzlülüğe kadar dayanırım" diye bir sayı yayınlamadığı için türetilebilecek bir değer yok — uydurmak yerine varsayım olarak etiketledik.

**S: "PSR verisini planlamada kullanmamak veri israfı değil mi?"**
Hayır, bilinçli. PSR'ler VIPER'ın bilim hedefi — orayı yasaklamak misyonu yasaklamaktır. Üstelik termal kapı zaten PSR hücrelerinin %99,4'ünü kapatıyor. PSR'yi doğrulama aracı olarak kullanmak daha değerli: kendi gölge modelimizin bağımsız ölçümle %83 örtüştüğünü gösteriyoruz.

**S: "Ko-registrasyon doğru yapıldı mı, nereden biliyorsunuz?"**
İki kontrol var ve ikisi de kodda otomatik: projeksiyon parametreleri eşleşmesi, ve NASA'nın kendi eğim ürünüyle bizim eğimimizin sıralama korelasyonu (0,989 ölçüldü; 0,9'un altında kod yazmayı reddediyor). Ayrıca bu kontrol 2,5 m'lik bir alt-piksel hizalama hatası yakaladı ve düzeltti.
