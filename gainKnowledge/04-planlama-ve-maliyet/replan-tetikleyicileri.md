# Yeniden Planlama Tetikleyicileri — "Plan Ne Zaman Geçersiz Olur?"

**Kodda:** `backend/app/replan_triggers.py`
**API:** `POST /api/replan`

---

## Nedir?

Yedi bağımsız kontrol. Her biri tek bir soruyu cevaplıyor: *"Bu belirti, planı yeniden hesaplamayı gerektiriyor mu?"*

Her kontrol **saf bir yüklem** (predicate): girdi alır, `TriggerResult(tetikleyici_id, ateşlendi_mi, açıklama)` döner. Yan etkisi yok.

---

## Hangi problemi çözüyor?

Bir plan, yapıldığı andaki varsayımlara dayanıyor: batarya şu seviyede olacak, rover şu saatte şurada olacak, sıcaklık şu olacak.

Gerçeklik bu varsayımlardan sapar. **Ne kadar sapma, planı geçersiz kılar?**

Bu soruyu net cevaplamazsanız iki hatadan birini yaparsınız:
- **Çok hassas** → sürekli yeniden planlıyorsunuz, rover hiç ilerlemiyor
- **Çok toleranslı** → plan çoktan geçersiz, rover hâlâ onu uyguluyor

---

## Analoji: Arabanın uyarı ışıkları

Arabanızın panelinde ışıklar var: yakıt, motor sıcaklığı, yağ basıncı, lastik basıncı.

Her biri **tek bir şeyi** izliyor ve **kendi eşiği** var. Yakıt ışığı motor sıcaklığını bilmiyor, bilmesine gerek de yok.

Ve şu ayrım kritik: **ışığın yanması, arabayı durdurmak demek değil.** Işık bir *sinyal*; ne yapılacağına sürücü karar veriyor.

Aynı şekilde: bu modül **yeniden planlamıyor.** Sadece "şu koşul oluştu" diyor. Kararı çağıran veriyor.

---

## Yedi tetikleyici

### 1. `check_soc_deviation` — Batarya sapması

**Ateşler:** Gerçek batarya, planlanan bataryanın altında ve fark eşiği aşıyorsa.

**Ateşlemez:** Plandan **iyi** durumdaysanız. (Beklenenden fazla enerjiniz varsa bu bir problem değil.)

**Eşik:** Rover'ın **kendi SOC rezervinin yarısı.**

> Bu bir düzeltme: eskiden tek bir global sabit (%10) vardı. Ama %30 rezerv tutan bir rover, %20 tutandan daha fazla sapmayı emebilir. Eşik artık rover'a göre türetiliyor. ("Round 3 review, L-8")

### 2. `check_inner_temperature` — İç sıcaklık düşüşü

**Ateşler:** Gerçek iç sıcaklık, tahmin edilenin belirli bir eşik kadar altındaysa.

**Eşik:** Rover'ın **batarya zarfının genişliğine** ölçeklenmiş. Varsayılan rover için 5 K.

### 3. `check_time_drift` — Zaman kayması

**Ateşler:** Rover programın 30 dakikadan fazla gerisindeyse.

**Neden bu kadar önemli:** **Aydınlanma zamanın fonksiyonu.** Program dışına kaymak, planın dayandığı bütün gölge hesabını geçersiz kılar. Rover 30 dakika geç kalırsa, "şu saatte burası aydınlık olacak" varsayımı artık doğru değil.

### 4. `check_corridor_violation` — Koridor ihlali

**Ateşler:** Rover koridorun yarı genişliğinin dışına çıkmışsa.

**Girdiler:** `lateral_offset_m` ve `half_width_m` — ikisini de [`localization.py`](../03-konum-ve-iletisim/pose-lokalizasyon-ve-skyline.md) üretiyor.

> Bu tetikleyici uzun süre vardı ama **girdilerini üreten hiçbir şey yoktu** — testlerde elle besleniyordu. `localization.py` o kaynağı sağlamak için yazıldı.

### 5. `check_comm_window` — İletişim penceresi

**Ateşler:** Kalan Dünya linki 15 dakikanın altına düştüğünde.

**Girdi:** `comm_minutes_remaining` — [A4](../03-konum-ve-iletisim/dunya-gorunurlugu-dte.md)'ün `comm_window` fonksiyonu tarafından **geometriden hesaplanıyor.**

> Bu da uzun süre elle beslenen bir girdiydi. A4 onu hesaplanan bir sayıya çevirdi.

### 6. `check_localization_uncertainty` — Konum belirsizliği

**Ateşler:** `2σ` konum hatası koridorun yarı genişliğini aştığında.

**Neden 2σ, 1σ değil:**

| Çarpan | Rover'ın koridor dışında olma ihtimali |
|---|---|
| 1σ | ~üçte bir → **bir güvenlik kontrolü için çok geç** |
| **2σ** | ~yirmide bir → geleneksel mühendislik marjı |

("Round 3 review, L-9")

### 7. `check_entrenchment` — Saplanma (C6)

**Ateşler:** Rover saplanmış (hareket edemiyor) ve geçen süre **tolere edilebilir saplanma süresine** yaklaşıyorsa.

Bu, JSC'nin terimi (ICES-2025-376): hareketsiz kalmış bir aracın "saat dolmadan" durabileceği sonlu süre.

**Dört seviyeli çıktı:**

| Seviye | Koşul |
|---|---|
| `ok` | %50'nin altında |
| `warning` | %50'yi geçti |
| `critical` | %80'i geçti |
| `fail` | Süre doldu |

**Tolere edilebilir süre:** İkisinin **daha sıkı olanı** —
- Bloğun termal dwell'i (iç sıcaklığın zarfı terk etme süresi) — [C6](../02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md)
- Haven penceresi (ay gecesinden önce sığınağa varmak için kalan süre) — [A1](safe-haven.md)

> **Site11'de ölçülen sonuç:** LPR-1 için haven penceresi **her yerde 0 saat** (ulaşılabilir haven yok), dolayısıyla genel seviye her saplanma durumunda **`fail`**. JSC'nin saati rover daha sıkışmadan dolmuş.

---

## Tasarım kararları

### Neden bağımsız ve yan etkisiz?

Her kontrol tek başına çalışabiliyor:
- **Yerde** (Dünya'daki operasyon merkezinde)
- **Rover üstünde** (otonom karar için)
- **Test içinde** (birim testi olarak)

Yan etkisiz olması, aynı kontrolü üç ortamda da aynı sonuçla çalıştırabilmek demek.

### Neden bu enumerasyon var?

**ESA ADE'nin ADAM modülü**, bir tehlike tanındığında nominal planı otonom olarak değiştiriyor. Ama yayınlanmış materyal **tetikleyicileri sıralamıyor** — "tehlike tanındığında" diyor, hangi tehlikeler olduğunu söylemiyor.

Bu modül o enumerasyon: *"yeniden planlama yapıyoruz"* iddiasının somut kanıtı, birim testleriyle birlikte.

### Rover'a göre eşikler

Üç eşik artık rover'dan türetiliyor (SOC sapması, iç sıcaklık, saplanma). Sabitler, **varsayılan rover için o türetmenin ürettiği değer** olarak duruyor — böylece mevcut çağıranlar hiçbir değişiklik görmüyor.

---

## Kodda nerede?

```
backend/app/replan_triggers.py
  check_soc_deviation()
  check_inner_temperature()
  check_time_drift()
  check_corridor_violation()
  check_comm_window()
  check_localization_uncertainty()
  check_entrenchment()

  TriggerResult                       ← (id, ateşlendi_mi, açıklama)
  SOC_DEVIATION_THRESHOLD    = 0.10   ← varsayılan rover için
  INNER_TEMPERATURE_DROP_K   = 5.0
  TIME_DRIFT_MINUTES         = 30.0
  COMM_WINDOW_MINUTES        = 15.0
  LOCALIZATION_SIGMA_MULTIPLIER = 2.0
  ENTRENCHMENT_WARNING_FRAC / CRITICAL_FRAC
```

---

## Jüri soruları

**S: "Yeniden planlama yapıyor musunuz?"**
Evet, ve yedi tetikleyicinin hepsi tek tek adlandırılmış ve birim testli. ESA'nın ADE/ADAM modülü de otonom yeniden planlama yapıyor ama yayınlarında tetikleyiciler sıralanmıyor. Bizim listemiz somut: batarya sapması, iç sıcaklık düşüşü, zaman kayması, koridor ihlali, iletişim penceresi, konum belirsizliği, saplanma.

**S: "Eşikleri nasıl belirlediniz?"**
Çoğu rover'dan türetiliyor, sabit değil. SOC sapma eşiği rover'ın kendi rezervinin yarısı — %30 rezerv tutan bir araç, %20 tutandan fazla sapmayı emebilir. İç sıcaklık eşiği batarya zarfının genişliğine ölçekli. Konum belirsizliğinde 2σ kullanıyoruz çünkü 1σ, rover zaten üçte bir ihtimalle koridor dışındayken ateşliyor — bir güvenlik kontrolü için geç.

**S: "Bu tetikleyiciler gerçekten besleniyor mu, yoksa dekoratif mi?"**
Şimdi besleniyorlar ama bir dönem değillerdi ve bunu saklamıyoruz. `corridor_violation` ve `localization_uncertainty` girdileri testlerde elle besleniyordu; `localization.py` o kaynağı üretmek için yazıldı. `comm_window` girdisi de dışarıdan bekleniyordu; A4 onu geometriden hesaplanan bir sayıya çevirdi.

**S: "Neden bu modül karar vermiyor?"**
Çünkü karar bağlama bağlı. Aynı tetikleyici, yerde operatör gözetimindeyken "bilgilendir", rover üstünde otonom modda "hemen dur" anlamına gelebilir. Modül sinyali üretiyor, politikayı çağıran belirliyor. Bu ayrım aynı kodun hem HTTP hem ROS 2 tarafında kullanılmasını sağlıyor.

**S: "Saplanma tetikleyicisi ne kadar gerçekçi?"**
Site11'de LPR-1 için her zaman `fail` veriyor — çünkü haven penceresi her yerde sıfır (ulaşılabilir safe haven yok). Bu kötü görünüyor ama doğru: o sahada o araçla saplanırsanız kurtulma şansınız zaten yok. Sistem bunu söylüyor, gizlemiyor.
