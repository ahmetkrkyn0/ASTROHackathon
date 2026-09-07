# AI Araçları ve Ürün Rehberi — Asistan Ne Yapabilir, Ne Yapamaz

**Kodda:** `backend/app/ai_tools.py`, `backend/app/ai_guide.py`

---

## Nedir?

İki modül:

1. **`ai_tools.py`** — Asistanın çalıştırabileceği araçların **yetki sınırı** ve ne sıklıkla çalıştırabileceğinin tavanı
2. **`ai_guide.py`** — Ürün yardımı sorularına cevap veren **kapalı bir kanonik ifadeler kaydı**

---

## Hangi problemi çözüyor?

Bir asistanın iki tür soruya cevap vermesi gerekiyor:

| Soru tipi | Örnek | Kanıt türü |
|---|---|---|
| **Rota analizi** | *"Bu rotanın toplam enerjisi ne?"* | Sayılar |
| **Ürün yardımı** | *"Enerji tasarrufu profili ne yapıyor?"* | Cümleler |

İkisi farklı kanıt gerektiriyor ve farklı riskler taşıyor.

---

## Analoji: Otel resepsiyonu ve kasa anahtarı

Bir otel resepsiyonisti size yardım edebilir: oda numaranızı söyler, kahvaltı saatini söyler, taksi çağırır.

Ama **kasayı açamaz.** Ve bu, resepsiyonistin dürüst olup olmamasıyla ilgili değil — **anahtarı yok.** Yapısal bir sınır.

`ai_tools.py`'nin yaptığı şey bu: asistana bazı anahtarlar veriliyor, bazıları verilmiyor. Ve verilmeyenler için "yapma" denmiyor — **ulaşamıyor.**

En önemlisi: **rota planlama aracı yok.** Yani asistan, hangi cümleyi kurarsa kursun, hiçbir model çıktısı dizisi kullanıcının ekranındaki rotayı değiştiremez.

---

## `ai_tools.py` — yetki sınırı

### İki temel yapısal özellik

Bunlar bir kontrolle değil, **mimariyle** sağlanıyor:

#### 1. Rota planlama aracı YOK

> *"Hiçbir model çıktısı dizisi `POST /api/plan`'a ulaşamaz, bir koridor yayınlayamaz veya kullanıcının ekranındaki rotayı hareket ettiremez."*

#### 2. Karşılaştırma uç noktalarını anlık görüntüden alıyor

`compare_mission_profiles` aracı, başlangıç/hedef koordinatlarını **misyon anlık görüntüsünden** alıyor — **modelin argümanlarından değil.**

> *"Böylece asistan, tartışılandan başka bir rota hakkında sessizce cevap veremez."*

Bu ikisi çok güçlü garantiler: kötü niyetli bir prompt bile bu sınırları aşamaz, çünkü aşılacak bir kod yolu yok.

### Kayıt, yetki sınırıdır

> *"Model bir fonksiyon adı ve bir JSON nesnesi önerir; ikisi de güvenilmez."*

- Onaylı iki araçtan biri olmayan bir ad, **çözümlenmek yerine reddediliyor**
- Argümanlar, sağlayıcıya verilen şema onları tanımlamış olsa bile **burada yeniden doğrulanıyor**

> *"Bir şema modele verilen bir ipucudur, modelden gelen bir garanti değil."*

### Bütçe tavanları

| Sabit | Değer | Gerekçe |
|---|---|---|
| `MAX_COMPARE_CALLS` | **1** | Ölçülmüş bir karşılaştırma **21,3 saniye** duvar saati; soru başına 30 saniye tavan var, ikincisi sığmıyor |
| `MAX_READ_CALLS` | 20 | — |
| `MAX_TOOL_ROUNDS` | 4 | — |

> *"Bu aritmetiktir, politika değil."*

Bu cümle önemli: bütçe keyfi bir sayı değil, ölçülmüş bir gerçeğin sonucu.

---

## `ai_guide.py` — ürün rehberi

Ürün yardımı, rota analiziyle **aynı şekilde** cevaplanıyor: K1 deterministik kanıt seçiyor, K4 ifade ediyor, K5 sayıları kontrol ediyor.

**Değişen şey kanıtın türü:** Rota özeti sayılardır; ürün yardımı çoğunlukla cümlelerdir.

### Üç özellik onu bir arada tutuyor

#### 1. Kayıt kapalı

`GUIDE_FACTS` bir **literal tablo**. `_TOPIC_FACTS` hangi konunun hangi girdileri seçtiğini söylüyor.

K4 yalnız seçilen girdileri alıyor.

> **Sonuç: bu dosyada olmayan bir ürün iddiası, modele kanıt olarak asla ulaşmaz.**

#### 2. Sayılar `NumericRegistry`'de kalıyor

Hiçbir "gerçek" (fact) bir büyüklük taşımıyor.

Rover spesifikasyonları, tıpkı plan metrikleri gibi, kanonik gösterimli **kayıtlı `Metric`** nesneleri — böylece K5 onları maskeliyor ve sıfır toleranslı dize eşleşmesi hâlâ geçerli.

#### 3. Hiçbir şey çalıştırmıyor

Handler yok, araç yok, yazıcı yok. `guide_evidence` rover kataloğunu **okuyor** ve bir sözlük döndürüyor.

> *"Salt-okunur garantisi yapısaldır, unutulabilecek bir kontrol değil."*

### Dürüst sınır

> *"K5 kayıtlı sayıları ve yasak iddia kurallarını doğrular. K4'ün yazdığı bir cümlenin, geldiği gerçeğe anlamsal olarak eşdeğer olduğunu **ispatlamaz**, ve bu modül öyle bir iddiada bulunacak bir doğrulayıcı eklemez."*
>
> *"Kapsama, kapalı kaydın modele verilen ürün ifadelerinin tek kaynağı olmasıdır."*

---

## Kodda nerede?

```
backend/app/ai_tools.py
  CAPABILITIES               ← semantik yetenek kodları (uç adı değil)
  PARAM_MODELS               ← argüman yeniden doğrulaması
  ToolBudget
  AiToolError
  MAX_COMPARE_CALLS = 1      ← 21,3 s ölçüldü, 30 s tavan
  MAX_READ_CALLS    = 20
  MAX_TOOL_ROUNDS   = 4
  tool_specifications()      ← modelin bütün erişimi

backend/app/ai_guide.py
  GUIDE_FACTS                ← kapalı literal tablo
  _TOPIC_FACTS               ← konu → gerçek eşlemesi
  guide_evidence()           ← salt okunur
```

---

## Jüri soruları

**S: "Asistan rotayı değiştirebilir mi?"**
Hayır ve bu bir kural değil, **yapısal bir gerçek**: rota planlama aracı diye bir şey yok. Hiçbir model çıktısı dizisi `/api/plan`'a ulaşamaz, koridor yayınlayamaz veya ekrandaki rotayı hareket ettiremez. Aşılacak bir kod yolu bulunmuyor.

**S: "Asistan yanlış rota hakkında konuşabilir mi?"**
Hayır. Karşılaştırma aracı başlangıç ve hedef koordinatlarını **misyon anlık görüntüsünden** alıyor, modelin verdiği argümanlardan değil. Yani model "aslında şu rotayı karşılaştır" diyemez.

**S: "Model kaç araç çağırabiliyor?"**
İki araç, sınırlı sayıda. Karşılaştırma **tur başına bir kez** — çünkü ölçülmüş bir karşılaştırma 21,3 saniye ve soru başına 30 saniye tavanımız var. İkincisi sığmıyor. Bu bir politika kararı değil, aritmetik.

**S: "Şema doğrulaması yeterli değil mi?"**
Değil. Sağlayıcıya verilen şema, modele bir **ipucu** — modelden gelen bir garanti değil. O yüzden argümanlar araç katmanında **yeniden doğrulanıyor**, şema onları tanımlamış olsa bile. Ve onaylı iki araçtan biri olmayan bir fonksiyon adı çözümlenmek yerine reddediliyor.

**S: "Ürün soruları nasıl cevaplanıyor?"**
Kapalı bir kayıt üzerinden. `GUIDE_FACTS` literal bir tablo; her konu hangi girdileri seçeceğini söylüyor ve model yalnız seçilenleri görüyor. Bu dosyada olmayan bir ürün iddiası modele kanıt olarak asla ulaşmaz. Ve hiçbir "gerçek" sayı taşımıyor — sayılar kayıtlı metrik olarak gidiyor, böylece K5'in sıfır toleranslı kontrolü geçerli kalıyor.

**S: "Rehber modülü bir şey çalıştırabiliyor mu?"**
Hayır — handler yok, araç yok, yazıcı yok. `guide_evidence` sadece rover kataloğunu okuyup bir sözlük döndürüyor. Salt-okunur olması yapısal, unutulabilecek bir kontrol değil.
