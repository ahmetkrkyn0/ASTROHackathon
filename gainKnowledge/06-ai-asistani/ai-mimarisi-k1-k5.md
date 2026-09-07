# AI Asistanı Mimarisi — K2 → K3 → K1 → K4 → K5

**Kodda:** `backend/app/ai_chat.py`, `ai_router.py`, `ai_analysis.py`, `ai_provider.py`, `ai_prompt.py`, `ai_contract.py`
**API:** `POST /api/ai/chat`

---

## Nedir?

Operatörün Türkçe sorularına cevap veren karar-destek asistanı. Ama **bir agent döngüsü değil** — beş aşamalı, sabit bir boru hattı.

```
K2 (yönlendirici) → K3 (kapı) → K1 (analiz) → K4 (sözelleştirici) → K5 (doğrulayıcı)
```

**En kritik özellik:** Dil modeline tur başına **tam olarak iki soru** soruluyor. Aradaki ve sonraki her şey **deterministik**.

---

## Hangi problemi çözüyor?

Bir operatör *"bu rota neden bu kadar uzun?"* veya *"batarya yeter mi?"* diye sorduğunda, cevabı bulmak için 33 API ucunun hangisini çağıracağını bilmesi ve dönen JSON'u yorumlaması gerekiyor.

AI asistanı bu aracılığı yapıyor.

**Ama:** Bir dil modeli **sayı uydurabilir.** Ve bir uzay misyonu bağlamında uydurulmuş bir sayı, kabul edilemez.

Mimarinin tamamı bu tek problemi çözmek için var.

---

## Analoji: Mahkeme salonu

Bir mahkemede kimse istediğini söyleyemez. Roller katı:

| Mahkeme | LunaPath AI |
|---|---|
| **Kâtip** soruyu kaydeder, karar vermez | **K2 (yönlendirici)** — soruyu yapılandırılmış karara çevirir, cevap yazmaz |
| **Mübaşir** kimin konuşabileceğini denetler | **K3 (kapı)** — hangi aracın çalışabileceğini denetler |
| **Bilirkişi** ölçümü yapar | **K1 (analiz)** — sayıları hesaplar |
| **Avukat** kanıtı anlatır, kanıt üretmez | **K4 (sözelleştirici)** — kanıtı cümleye çevirir, hesap yapmaz |
| **Zabıt kontrolü** her sayının tutanakta olduğunu doğrular | **K5 (doğrulayıcı)** — taslakta hesaplanmamış rakam var mı |

Ve kritik kural: **hiçbir rol başkasının işini yapamaz.** Avukat bilirkişinin ölçümünü değiştiremez, kâtip karar veremez.

Bu mimari, bu ayrımı **yapısal** olarak zorluyor — bir kontrolle değil.

---

## Beş aşama

### K2 — Yönlendirici (`ai_router.py`)

**İşi:** Serbest metni **yapılandırılmış bir karara** çevirmek. Başka hiçbir şey.

**Yapamayacakları:**
- ❌ Düzyazı yazmaz
- ❌ Sayı üretmez
- ❌ Backend uç adı **görmez** — semantik yetenek kodları verilir
- ❌ Koordinat uydurmaz

**Verdiği kararlar:**

| Karar | Ne zaman |
|---|---|
| `answer_from_context` | Soru mevcut plandan cevaplanabiliyorsa (**birincil ve hızlı yol**) |
| `invoke` | Bir analiz çalıştırılması gerekiyorsa |
| `failure` | Cevaplanamıyorsa |

Karar sorularının hepsi `answer_from_context`'e gidiyor: *"bu rota sürülebilir mi", "neden NO-GO", "GO/NO-GO kararı neye dayanıyor"* — çünkü **karar mevcut plandan deterministik olarak okunuyor.** Prompt bunu açıkça söylüyor: *"Karar senin vereceğin bir karar değildir."*

**Yapılandırılmış Çıktı (Structured Outputs)** sağlayıcı destekliyorsa kullanılıyor. Ama cevap **koşulsuz** Pydantic ile doğrulanıyor: *"bir şema bir optimizasyondur, bir garanti değil."*

### K3 — Deterministik kapı (`ai_router.py`)

Her çağrının önündeki kapı. **Hiçbir şey çalıştırmadan** yapılabilecek dört kontrol:

1. **Erişilebilirlik** — bu yetenek şu an var mı?
2. **Şema** — argümanlar doğru biçimde mi?
3. **İzin** — bu araç çağrılabilir mi?
4. **Bütçe** — kota aşıldı mı?

**Kasıtlı olarak yapılmayanlar:** Aralık ve bağlam kontrolü. Çünkü mevcut araç uygulamaları zaten grid metadata'sına karşı sınır kontrolü yapıyor ve eksik bir misyonu zaten reddediyor. **İkinci bir kopya birincisinden ayrışırdı.** K3 onların tipli hatalarını semantik taksonomiye eşliyor.

### K1 — Analiz çekirdeği (`ai_analysis.py`)

Deterministik kanıt seçimi. Ve **sayı biçimlendirmesinin tek yeri**.

**En yük taşıyan karar: binlik ayırıcı YOK.**

Neden: `1.490,23` gibi bir gösterim sistemden kaynağında kaldırılıyor. Böylece K5'in *"`1.490` bin dört yüz doksan mı, bir virgül dört dokuz mu?"* sorusuna cevap vermesi hiç gerekmiyor.

**K5'in hiç sayı ayrıştırıcısı yok — tasarım gereği.**

Yuvarlama **tam olarak bir kez**, burada, `precision`'a göre yapılıyor. Bu yüzden K5'in toleransı **sıfır**: büyüklükleri değil, **dizeleri** karşılaştırıyor.

> *"Aşağı akışta hiçbir yere epsilon eklemeyin."*

### K4 — Sözelleştirici (`ai_prompt.py`)

Kanıtı Türkçe cümleye çeviriyor.

**Gördüğü şey:** Etiketleri, birimleri ve **kanonik gösterim dizeleri** olan metrikler. Ham backend alan yolu **görmüyor**.

**Yapamayacağı:** Hesap yapmak. Sadece K1'in `display` dizesini **birebir kopyalıyor**.

Faz-1 kullanıcı dili **Türkçe**. Yönlendirici başka dilde sorulan soruyu anlayabilir; sözelleştirici **her hâlükârda Türkçe** cevap veriyor.

### K5 — Doğrulayıcı (`ai_grounding.py`)

Taslakta hesaplanmamış rakam var mı? Detaylı anlatım: [AI güvenliği ve grounding](ai-guvenlik-ve-grounding.md)

---

## Neden agent döngüsü değil?

Bu, mimarinin en önemli tercihi.

**Agent döngüsü:** Model düşünür, araç çağırır, sonucu görür, tekrar düşünür, tekrar araç çağırır... İstediği kadar tur.

**LunaPath:** Model **tam olarak iki kez** konuşuyor — *"ne çalışmalı"* ve *"sonucu nasıl söylemeli"*. Aradaki ve sonraki her şey deterministik.

**Kazancı:** *"Bu şekil, garantileri kontrol edilebilir kılan şeydir."*

| Rol | Yapamayacağı |
|---|---|
| Yönlendirici | **Cevap veremez** |
| Kapı | **Yorumlayamaz** |
| Sözelleştirici | **Hesaplayamaz** |
| Doğrulayıcı | **Yeniden yazamaz** |

Bir agent döngüsünde bu ayrımların hiçbiri yapısal değildir — model her turda her şeyi yapabilir.

---

## İki savunma katmanı, üst üste

> *"İki savunma birbirinin yerine geçmez, üst üste yığılır."*

| Katman | Ne belirler |
|---|---|
| **Sanitizasyon** (`ai_evidence.py`) | Modelin **ne görebileceğini** |
| **Grounding** (`ai_grounding.py`) | Operatöre **ne söylenebileceğini** |

**Sonucu:**
- Yukarıda çıkarılmış bir alan **asla alıntılanamaz**
- Aşağıda uydurulmuş bir sayı **asla hayatta kalamaz**

---

## Sağlayıcı sınırı (`ai_provider.py`)

**Kasıtlı olarak küçük.** Agent framework'ü yok, eklenti sistemi yok, zincir yok.

> *"Model soruyu anlıyor, onaylı iki araçtan birini seçiyor ve LunaPath'in zaten hesapladığı kanıtı ifade ediyor. İşin tamamı bu, ve bir framework modelin çıktısı ile onu güvenli kılan kontroller arasına dolaylılık koyardı."*

**Yerleşik araçların hiçbiri açık değil:** web araması, dosya araması, kod yorumlayıcı, bilgisayar kullanımı, kabuk — hiçbiri.

> *"Modelin bütün erişimi, `ai_tools.tool_specifications()` tarafından ona verilen iki şemadır."*

**Yapılandırma:** Süreç ortamından okunuyor. Bu modülün hiçbiri frontend tarafından içe aktarılamıyor. API anahtarı **hiçbir zaman** loglanmıyor, bir hatada yankılanmıyor veya `repr`'e dâhil edilmiyor.

**Varsayılan akıl yürütme çabası: `low`.** Gerekçe: *"LunaPath teknik hesabı yapıyor. Modelin işi niyet, araç seçimi ve ifade — hiçbiri derin akıl yürütme gerektirmiyor."*

---

## Misyon anlık görüntüsü bir DEĞERDİR (`ai_contract.py`)

Tarayıcı, kullanıcının zaten seçtiklerini gönderiyor: başlangıç, hedef, rover, ağırlıklar ve çalıştırdığı plan. Sohbet katmanı bunu **okuyor**.

> **Buradan misyon durumuna geri giden hiçbir yol yok: bu sınırı hiçbir setter geçmiyor.**

Ve anlık görüntüyü tüketen araçlar koordinatlarını **ondan** alıyor, **modelden değil.**

**Kabul edilen mesaj rolleri:** yalnız `user` ve `assistant`.

| Reddedilen rol | Neden |
|---|---|
| `system` / `developer` | Sayfanın işletim kurallarını yeniden yazmasına izin verirdi |
| `tool` | Sayfanın, hiçbir aracın üretmediği kanıtı uydurmasına izin verirdi |

Sınırlar: 12 mesaj, mesaj başına 4 000 karakter.

---

## Kodda nerede?

```
backend/app/ai_chat.py       ← K2→K3→K1→K4→K5 boru hattı
backend/app/ai_router.py     ← K2 + K3
backend/app/ai_analysis.py   ← K1, format_display, numeric_registry
backend/app/ai_prompt.py     ← K2 ve K4 promptları
backend/app/ai_provider.py   ← model sınırı, iki uygulama
backend/app/ai_contract.py   ← wire tipleri, misyon anlık görüntüsü
backend/app/ai_grounding.py  ← K5
backend/app/ai_evidence.py   ← sanitizasyon
backend/app/ai_tools.py      ← yetki sınırı
backend/app/ai_guide.py      ← ürün rehberi

docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md   ← sözleşme
```

---

## Jüri soruları

**S: "AI asistanınız nasıl çalışıyor?"**
Beş aşamalı sabit bir boru hattı: yönlendirici, kapı, analiz, sözelleştirici, doğrulayıcı. Dil modeline tur başına **tam olarak iki soru** soruluyor — "ne çalışmalı" ve "sonucu nasıl söylemeli". Aradaki ve sonraki her şey deterministik kod.

**S: "Neden agent framework kullanmadınız?"**
Çünkü framework, modelin çıktısı ile onu güvenli kılan kontroller arasına dolaylılık koyar. Bizim ihtiyacımız olan garanti şu: yönlendirici cevap veremez, kapı yorumlayamaz, sözelleştirici hesaplayamaz, doğrulayıcı yeniden yazamaz. Bu ayrımlar sabit boru hattında **yapısal**; agent döngüsünde değil.

**S: "Model hangi araçlara erişebiliyor?"**
İki taneye. Web araması, dosya araması, kod yorumlayıcı, kabuk — hiçbiri açık değil. Ve rota planlama aracı **yok**, yani hiçbir model çıktısı dizisi `/api/plan`'a ulaşamaz veya kullanıcının ekranındaki rotayı değiştiremez. Bu bir kontrol değil, yapısal bir özellik.

**S: "Model misyon durumunu değiştirebilir mi?"**
Hayır. Misyon anlık görüntüsü bir **değer** — tarayıcıdan geliyor, sohbet katmanı okuyor. Geri giden hiçbir setter yok. Ve araçlar koordinatlarını anlık görüntüden alıyor, modelden değil — yani asistan sessizce başka bir rota hakkında konuşamaz.

**S: "Kullanıcı prompt injection yapabilir mi?"**
Sadece `user` ve `assistant` rolleri kabul ediliyor. `system` veya `developer` turu, sayfanın işletim kurallarını yeniden yazmasına izin verirdi. `tool` turu, hiçbir aracın üretmediği kanıtı uydurmasına izin verirdi. Üçü de reddediliyor. Ve daha derin savunma: model ne görebilirse onu söyleyebilir, o yüzden sanitizasyon katmanı modelin gördüğü her alanı beyaz listeden geçiriyor.

**S: "Neden düşük akıl yürütme çabası?"**
Çünkü teknik hesabı LunaPath yapıyor. Modelin işi niyet anlama, araç seçimi ve ifade — hiçbiri derin akıl yürütme gerektirmiyor. Üstelik bir karşılaştırma çalıştığında soru zaten ~21 saniye sürüyor; 30 saniyelik tavana karşı bütçe dar.
