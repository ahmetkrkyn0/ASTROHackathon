# Dış Referans Doğrulamaları — Kendi Hesabımızı Başkasının Ölçümüyle Sınamak

**Kodda:** `backend/app/visibility_validation.py`, `backend/app/thermal_validation.py`, `backend/app/mission_reference.py`

---

## Nedir?

Üç küçük ama kavramsal olarak önemli modül. Hepsi aynı işi yapıyor: **LunaPath'in ürettiği bir sayıyı, LunaPath'in üretmediği bir sayıyla karşılaştırmak.**

| Modül | Neyi doğruluyor | Durum |
|---|---|---|
| `visibility_validation.py` | Dünya görünürlüğü ← NASA LOLA ürünü | ✅ **Çalıştı** |
| `thermal_validation.py` | Yüzey sıcaklığı ← NASA Diviner | ⏳ Altyapı hazır, veri yok |
| `mission_reference.py` | Mesafe/performans ← gerçek misyon kilometre taşları | ✅ Kayıtlı |

---

## Hangi problemi çözüyor?

Bir sistem kendi içinde mükemmel tutarlı olabilir ve **tamamen yanlış** olabilir.

Testleriniz geçer, kod temizdir, sayılar birbirini tutar — ama sistem 40 kilometre ötedeki bir arazi için plan yapıyordur.

**Bu tam olarak başımıza geldi** ve bir dış doğrulama yakaladı. Detay aşağıda.

---

## Analoji: Terazi ve standart ağırlık

Mutfak terazinizin doğru tarttığını nereden biliyorsunuz?

Aynı şeyi iki kez tartıp aynı sonucu almanız **hiçbir şey kanıtlamaz** — tutarlı ama yanlış olabilir.

Doğru cevap: **bilinen ağırlıkta bir standart** koymak. 1 kilogramlık sertifikalı ağırlık koyun; terazi 1 000 g diyorsa doğru, 1 040 g diyorsa %4 sapma var.

Dış referans doğrulaması budur. Ve bu projede **sertifikalı ağırlığı NASA sağlıyor.**

---

## 1. Dünya görünürlüğü doğrulaması ✅

**Referans:** LOLA "Average Earth Visibility" ürünü (PGDA 69; Mazarico vd. 2011) — 18,6 yıllık saatlik Dünya görünürlüğü, 85–90° Güney için 60 m/piksel.

**Yöntem:** İki eş-kayıtlı (H, W) oran grid'i [0,1] alınıyor, hata istatistikleri çıkarılıyor.

**Tasarım:** Modül **saf**. Dosya çekme, yeniden projeksiyon ve blok ortalama alma işi `scripts/earth_visibility_validation.py`'nin. Böylece karşılaştırmanın kendisi, NASA'nın dosyası diskte olmadan test edilebiliyor.

*(Aynı ayrımı `thermal_validation` Diviner için yapıyor.)*

**Sonuç:**

| Ölçüm | Değer |
|---|---|
| Örnek sayısı | 163 162 |
| **RMSE** | **0,087** |
| **Pearson r** | **0,960** |
| 0,5 eşiğinde uyuşmazlık | %9,4 (1 681 hücre) |

> *"Bu, projedeki modellenmiş bir katmanı yayınlanmış, ölçülmüş-topografyalı bir ürüne bağlayan ilk sayıdır."*

### Ve bulduğu iki hata

**Hata 1 — 40 km kayma.** İlk koşum RMSE 0,665 ve Pearson r **−0,16** verdi. Yani korelasyon yok, hatta hafif negatif.

Sebep: işlenmiş grid'ler yanlış DEM penceresinden üretilmişti. Pencere merkezi ve kuzey dönüşü **40 kilometre kaymıştı.**

DEM yeniden indirildi, veri hattı yeniden koşuldu, `metadata.json` byte-eşit çıktı, RMSE 0,087'ye düştü.

**Bu hata iç tutarlılık testleriyle asla bulunamazdı.** Sistem kendi içinde tutarlıydı — sadece yanlış yerdeydi.

**Hata 2 — Işın menzili yetersiz.** Krater kenarından ufuk 10 km içinde 20° düşüyor ve karşı krater duvarı hiç görülmüyordu.

`build_horizon_cache.py` artık LOLA'nın 40 m kutup DEM'ini 10–150 km arasında da tarıyor. Etkisi: uzak alan çiftlerinin **%27,5'inde ufuk 4,2° yükseldi**, ışıklı oran zirvesi ~%47'ye çıktı, **terminatör tarihleri kaydı.**

Bu ikincisi sadece Dünya görünürlüğünü değil, **bütün gölge hesabını** düzeltti.

Detay: [Dünya görünürlüğü (A4)](../03-konum-ve-iletisim/dunya-gorunurlugu-dte.md)

---

## 2. Termal doğrulama ⏳

**Referans:** NASA Diviner — LRO'nun termal radyometresi, gerçek yüzey sıcaklığı ölçümü.

**Ne ölçüyor:**

| Metrik | Anlamı |
|---|---|
| RMSE | Ortalama karesel hata |
| MAE | Ortalama mutlak hata |
| Bias | Sistematik sapma |
| **`misclassified_traversable_pct`** | **İki grid'in "bu hücre −150 °C'nin üstünde mi" konusunda anlaşmadığı hücre oranı** |

Son metrik bizim için kritik olan: çünkü **geçilebilirliği belirleyen eşik** o. Sıcaklık tahmininde 5 derece hata yapmak önemsiz olabilir; ama o hata bir hücreyi geçilebilirden geçilemeze çeviriyorsa çok önemli.

**Durum:** Modül hazır ve test edilebilir. **Diviner dosyası yerelde yok.** Bu açıkça ayrı bir işin (C5) kapsamı olarak kayıtlı.

**Ve bu yüzden termal model `MODEL / UNCALIBRATED` etiketli** — doğrulanmadığı için.

---

## 3. Misyon referansları ✅

`mission_reference.py`, **yayınlanmış, tarihli gerçek misyon rakamlarını** tutuyor. Model çıktısı değil.

Örnek — Yutu-2 (Chang'e-4), Ay'ın en uzun ömürlü rover'ı (2019'da indi, hâlâ çalışıyor):

| Tarih | Toplam mesafe | Kaynak |
|---|---|---|
| 17 Eyl 2024 | 1 613 m | space.com |
| 4 Mar 2025 | 1 630 m | friendsofnasa.org |

**Kural:** *"Bir rover sürmeye devam ettiği için bir sayı değişirse, yeni bir alıntıyla yeni bir kilometre taşı ekleyin — mevcut bir kaydı asla sessizce düzenlemeyin."*

**Neden var:** LunaPath'in kendi olgunluk değerlendirmesi (`docs/research/09_olgunluk_kiyaslama.md`), dış gerçeklik kontrolünün eksik olduğunu tespit etmişti. Bu modül o eksiği kapatıyor.

**Ne işe yarıyor:** Bir rover'ın Ay'da **6 yılda 1,6 kilometre** gittiğini bilmek, planlarımızın ölçeğini bağlama oturtuyor. Bizim 2,7 kilometrelik bir rotayı 3 saatte planlamamız, gerçek misyon hızlarıyla karşılaştırıldığında ne anlama geliyor?

---

## Ortak tasarım deseni

Üç modül de aynı ilkeyi izliyor:

> **Karşılaştırma saf bir fonksiyondur. Veri getirme, yeniden projeksiyon ve kırpma, script'lerin işidir.**

**Kazancı:** Karşılaştırma mantığı, NASA'nın gigabaytlık dosyaları diskte olmadan **birim testi edilebiliyor.**

---

## Kodda nerede?

```
backend/app/visibility_validation.py
  ← saf karşılaştırma; scripts/earth_visibility_validation.py veriyi getirir

backend/app/thermal_validation.py
  thermal_comparison()               ← RMSE / MAE / bias / misclassified_traversable_pct
  ← scripts/diviner_validation.py veriyi getirir (dosya yok)

backend/app/mission_reference.py
  DistanceMilestone
  YUTU_2_MILESTONES

docs/research/earth_visibility_validation.md
docs/research/09_olgunluk_kiyaslama.md
```

---

## Jüri soruları

**S: "Sisteminizi doğruladınız mı?"**
Bir katmanı tam olarak doğruladık: Dünya görünürlüğü, NASA'nın 18,6 yıllık LOLA ürünüyle 163 162 örnek üzerinde. RMSE 0,087, Pearson r 0,960. Termal doğrulama altyapısı hazır ama Diviner verisi yerelde yok — o yüzden termal model `UNCALIBRATED` etiketli.

**S: "Doğrulama size ne kazandırdı?"**
İki büyük hata buldu. Birincisi grid'lerimizin 40 kilometre kaymış bir pencereden üretilmiş olması — RMSE 0,665, korelasyon −0,16 çıkınca anlaşıldı. Bu hata iç testlerle **asla bulunamazdı**, çünkü sistem kendi içinde tutarlıydı, sadece yanlış yerdeydi. İkincisi ışın menzilimizin 10 km'de kesilmesi; 150 km'ye çıkarınca uzak alan çiftlerinin %27,5'inde ufuk 4,2 derece yükseldi ve terminatör tarihleri kaydı.

**S: "Neden termal doğrulama yapmadınız?"**
Yapamadık — Diviner dosyası yerelde yok. Ama altyapı hazır ve test edilebilir durumda: iki eş-kayıtlı sıcaklık grid'i alıp RMSE, MAE, bias ve en önemlisi "geçilebilirlik eşiğinde kaç hücrede anlaşmıyoruz" oranını veriyor. Veri geldiğinde tek bir script koşumu yeterli.

**S: "Misyon referansları ne işe yarıyor?"**
Ölçek duygusu. Yutu-2 Ay'da 6 yılda 1 630 metre gitti. Bizim 2,7 kilometrelik bir rotayı 3 saatte planlamamız, bu bağlamda okununca farklı bir anlam kazanıyor. Ayrıca kural katı: bir rakam değişirse yeni bir alıntıyla yeni bir kilometre taşı ekleniyor, eskisi sessizce düzenlenmiyor.

**S: "Neden karşılaştırma ve veri getirme ayrı?"**
Çünkü karşılaştırma mantığının NASA'nın gigabaytlık dosyaları olmadan test edilebilmesi gerekiyor. Saf fonksiyon iki dizi alıyor, istatistik veriyor. Dosyayı indirmek, yeniden projekte etmek ve kırpmak script'in işi. Bu ayrım üç doğrulama modülünde de aynı.
