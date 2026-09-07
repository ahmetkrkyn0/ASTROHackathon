# AI Güvenliği ve Grounding — Modelin Sayı Uydurması Nasıl Engellendi

**Kodda:** `backend/app/ai_grounding.py` (K5), `backend/app/ai_evidence.py` (sanitizasyon)

---

## Nedir?

İki katmanlı bir savunma:

| Katman | Ne belirler | Modül |
|---|---|---|
| **Sanitizasyon** | Modelin **ne görebileceğini** | `ai_evidence.py` |
| **Grounding (K5)** | Operatöre **ne söylenebileceğini** | `ai_grounding.py` |

Sonuç: **Modelin uydurduğu bir sayı operatöre ulaşamaz.**

---

## Hangi problemi çözüyor?

Dil modelleri sayı uydurur. Bu bilinen bir davranış ve bir uzay misyonu bağlamında kabul edilemez.

Operatör *"batarya yeter mi?"* diye soruyor, model *"evet, %34 kalacak"* diyor — ama o %34 hiçbir hesaptan gelmemişse, operatör yanlış bir karara yönlendirilmiş olur.

---

## Analoji: Sınavda hesap makinesi yasağı değil, cevap anahtarı kontrolü

İki farklı yaklaşım düşünün:

**Yaklaşım 1 — Yasak:** *"Öğrenci hesap yapmasın."* Ama nasıl kontrol edeceksiniz? Her sayıyı takip etmeniz gerekir.

**Yaklaşım 2 — Çıkarma:** Öğrencinin kâğıdını alın. Verilmiş olan bütün sayıların üstünü **karalayın**. Sonra bakın: **hâlâ bir rakam görünüyor mu?**

Görünüyorsa, o rakam öğrencinin uydurmasıdır. Ne olduğunu anlamanıza gerek yok — orada olmaması yeterli.

K5'in yaptığı tam olarak bu. Ve incelik şurada: **K5 hiçbir sayının ne anlama geldiğini öğrenmiyor.** Sadece hesabı yapılmamış bir rakamın varlığını fark ediyor.

Bu, "her sayıyı doğrula"dan **kesinlikle daha zayıf** bir gereksinim — ve tam da bu yüzden **yapısal olarak sağlam.**

---

## K5 — çıkarma yoluyla doğrulama

### Üç adım

```
1. Beyaz listedeki her tanımlayıcıyı taslaktan maskele
2. Kayıtlı her gösterim dizesini taslaktan maskele
3. Hiç rakam kalmadığını doğrula
```

Maskeleme işareti: özel kullanım alanındaki bir Unicode kod noktası — gerçek metinde asla geçemez, o yüzden güvenli.

### Neden sayı ayrıştırıcısı yok?

**K5'in hiçbir sayı ayrıştırıcısı yok ve bu tasarımdır.**

Türkçe düzyazıdan rakam çözmeye kalksanız:
- Her çözme yolu bir saldırı yüzeyi olur
- Ve `1.490` sorusunun **güvenli bir cevabı yoktur** (bin dört yüz doksan mı, bir virgül dört dokuz mu?)

**Çözüm kaynakta:** K1 sayıları **binlik ayırıcı olmadan** biçimlendiriyor. Böylece 2. adım **tam dize eşleşmesi** oluyor ve tolerans **sıfır**.

Yuvarlama zaten bir kez, K1'de yapıldı. **Aşağı akışta epsilon eklenmiyor.**

### Rakamla yazılmayan sayılar?

Rakam taraması tek başına yeterli değil — model bir sayıyı **kelimeyle** yazabilir ("iki yüz elli").

Bunun için **sınırlı bir bigram kontrolü** var: K1'in gerçekten saydığı isimlerin hemen öncesindeki sayı kelimelerini kapsıyor.

**Bu küme kasıtlı olarak kapalı.** Kod açıkça söylüyor: *"Bu bir Türkçe NLP ayrıştırıcısı değil ve öyle bir şeye dönüşmemeli."*

### İhlalde ne oluyor? — BLOKLAMA, düzeltme değil

> **K5 ihlalde BLOKLAR. Taslağı asla düzenlemez.**
>
> *"Sessiz bir düzeltme, görünmez hâle gelmiş bir halüsinasyondur."*

Bu, projedeki en keskin tasarım cümlelerinden biri. Eğer K5 yanlış sayıyı düzeltseydi:
- Operatör doğru cevabı görürdü ✅
- Ama modelin uydurduğunu **hiç kimse bilmezdi** ❌
- Ve bir sonraki sefer düzeltilemeyen bir uydurma geçerdi

Bloklamak, hatayı **görünür** kılıyor.

---

## Sanitizasyon — modelin gördüğü her alan beyaz listeden geçiyor

> *"Hiçbir şey modele ham backend sözlüğü olarak ulaşmaz."*
>
> *"Çünkü prompt bir güvenlik sınırı değildir: ulaşan bir alan, modelin etrafında cümle kurabileceği bir alandır."*

### Üç tuzak alan

Bu backend'in birkaç alanı **gerçekmiş gibi okunuyor ama değil.** Üçü yük taşıyor:

#### Tuzak 1: `astar_metrics.total_energy_wh` ve `total_shadow_hours`

**Her zaman `None`** — hızlı-mod tasarım kararı. Ama **aynı cevabın içinde**, hemen yanında duran simülasyonda **gerçek toplamlar var.**

Model bunu görse: *"toplam enerji bilinmiyor"* derdi. Yanlış — biliniyor, sadece o alanda değil.

#### Tuzak 2: `summary.total_shadow_exposure`

**Kod tabanının hiçbir yerinde birimi yok.**

> *"Birimini kimsenin adlandıramadığı bir sayı ifade edilemez."*

#### Tuzak 3: `comparison.recommendation`

Metin hâlâ *"enerji ve gölge takip edilmiyor"* diye duyuruyor — **ikisini de taşıyan cevaplarda.** Yani metin eskimiş ve yanlış.

**Üçü de modele hiç gösterilmiyor.**

### Soyağacı (provenance) modele taşınıyor

Sanitizasyon, [güvenilirlik etiketlerini](../00-genel-bakis/veri-kaynaklari-ve-etiketler.md) de aktarıyor:

```
_VALIDITY_ORDER = ("SYNTHETIC", "DERIVED", "MODEL", "MEASURED")   ← zayıftan güçlüye
```

Görüntü için üç seviyeye iniyor (`measurement` / `model` / `demo`, NASA-STD-7009B soyağacı) ama **en zayıf girdi önce dört basamaklı merdivende hesaplanıyor.**

---

## Sayı biçimlendirmenin tekliği (K1)

Her sayının tek bir kanonik gösterimi var: `format_display(value, unit, precision)`.

**Saf ve total bir fonksiyon.** Aynı girdi her zaman aynı dizeyi veriyor.

Birim başına varsayılan ondalık basamak sayısı tanımlı (Wh: 2, km: 3, m: 1, h: 2 …). Bir metrik bunu geçersiz kılabilir ama **varsayılan var olmak zorunda** — çünkü aynı değerin iki farklı gösterimi ikisi de "kayıtlı" olurdu ve bu maskeyi zayıflatırdı.

Boyutsuz bir büyüklük çıplak yazılıyor: `0,13215`, `0,13215 dimensionless` değil.

---

## Neyi ispatlamıyoruz — dürüst sınır

`ai_guide.py` bunu açıkça söylüyor:

> *"K5 kayıtlı sayıları ve yasak iddia kurallarını doğrular. K4'ün yazdığı bir cümlenin, geldiği gerçeğe **anlamsal olarak eşdeğer** olduğunu ispatlamaz ve bu modül öyle bir iddiada bulunacak bir doğrulayıcı eklemez."*

**Çeviri:** Model *"batarya %34,2'ye iniyor"* yerine *"batarya %34,2'ye çıkıyor"* yazarsa, K5 bunu yakalamaz — sayı doğru ve kayıtlı.

**Kontrol nasıl sağlanıyor:** Kapalı kayıt (closed registry). Modelin gördüğü kanıt kümesi sınırlı olduğu için, kurabileceği cümlelerin uzayı da sınırlı.

Bu dürüst bir sınır beyanı ve gizlenmiyor.

---

## Kodda nerede?

```
backend/app/ai_grounding.py
  GroundingViolation
  maskeleme (3 adım)
  bigram kontrolü (kapalı küme)
  _SENTINEL                     ← özel kullanım Unicode

backend/app/ai_evidence.py
  sanitize_cell_telemetry()
  sanitize_compare()
  Quantity
  _VALIDITY_ORDER / _DISPLAY_PEDIGREE

backend/app/ai_analysis.py
  format_display()              ← tek kanonik gösterim
  numeric_registry
  _UNIT_PRECISION
  DIMENSIONLESS
```

---

## Jüri soruları

**S: "AI'ınız sayı uydurabiliyor mu?"**
Uydurabilir ama o cevap operatöre ulaşmaz. K5 doğrulayıcısı taslaktan bütün kayıtlı sayıları maskeliyor; geriye rakam kalırsa cevabı **blokluyor**. Ve düzeltmiyor — çünkü sessiz düzeltme, görünmez hâle gelmiş bir halüsinasyondur.

**S: "K5 nasıl çalışıyor, teknik olarak?"**
Çıkarma yoluyla. Beyaz listedeki tanımlayıcıları ve kayıtlı gösterim dizelerini taslaktan maskeliyor, sonra "hiç rakam kaldı mı" diye bakıyor. K5'in **hiç sayı ayrıştırıcısı yok** — bu kasıtlı. Türkçe düzyazıdan rakam çözmek her seferinde bir saldırı yüzeyi olur ve `1.490` sorusunun güvenli bir cevabı yok.

**S: "Binlik ayırıcı meselesi ne?"**
Sistem hiçbir yerde binlik ayırıcı kullanmıyor. Bu, `1.490,23` gibi gösterimleri kaynağında ortadan kaldırıyor. Sonuç: K5'in dize eşleşmesi tam eşleşme oluyor ve toleransı sıfır. Yuvarlama tam olarak bir kez, K1'de yapılıyor.

**S: "Model hangi verileri görüyor?"**
Sadece beyaz listeden geçmiş alanları. Prompt bir güvenlik sınırı değil — modele ulaşan her alan, etrafında cümle kurabileceği bir alandır. Özellikle üç "tuzak" alanı gizliyoruz: her zaman `None` olan enerji metrikleri, birimi hiç tanımlanmamış bir gölge alanı, ve artık yanlış olan eski bir tavsiye metni.

**S: "Kelimeyle yazılan sayıları yakalıyor musunuz?"**
Sınırlı olarak. K1'in gerçekten saydığı isimlerin hemen öncesindeki sayı kelimeleri için bir bigram kontrolü var. Ama bu küme kapalı ve kod açıkça "bu bir Türkçe NLP ayrıştırıcısı değil ve öyle bir şeye dönüşmemeli" diyor.

**S: "Neyi garanti EDEMİYORSUNUZ?"**
Anlamsal doğruluğu. Model "batarya %34,2'ye iniyor" yerine "çıkıyor" yazarsa K5 yakalamaz — sayı doğru ve kayıtlı. Bunu kodda açıkça yazıyoruz. Kontrol, kapalı kayıt sisteminden geliyor: modelin gördüğü kanıt kümesi sınırlı olduğu için kurabileceği cümlelerin uzayı da sınırlı.

**S: "İki savunma katmanı neden gerekli?"**
Çünkü farklı şeyleri engelliyorlar. Sanitizasyon modelin ne **görebileceğini** belirliyor; grounding operatöre ne **söylenebileceğini**. Yukarıda çıkarılmış bir alan asla alıntılanamaz; aşağıda uydurulmuş bir sayı asla hayatta kalamaz. Biri diğerinin yerine geçmiyor, üst üste yığılıyorlar.
