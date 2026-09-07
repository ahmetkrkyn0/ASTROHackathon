# Rota Analizi ve Misyon Raporu — GO / GO-WITH-RISK / NO-GO

**Kodda:** `backend/app/route_analysis.py`, `backend/app/report.py`
**Frontend eşi:** `frontend/src/features/mission-report/report.ts`

---

## Nedir?

İki parça:

1. **Rota analizi** — Simüle edilmiş rotanın **dağılım görünümü**: eğim bantları, risk yüzdeleri, termal uçlar
2. **Misyon raporu** — Bütün bunlardan tek bir **karar**: `GO` / `GO-WITH-RISK` / `NO-GO`

---

## Hangi problemi çözüyor?

`summarize_simulation` size toplamları veriyor: toplam süre, toplam enerji, minimum batarya.

Ama toplamlar bir şeyi gizler: **dağılımı.**

İki rota aynı ortalama eğime sahip olabilir — biri baştan sona 10 derece, öbürü çoğunlukla düz ama bir yerde 24 derece. **Aynı ortalama, tamamen farklı risk.**

Ve nihayetinde operatörün ihtiyacı bir sayı değil, bir **karar**.

---

## Analoji: Kan tahlili ve doktorun kararı

Kan tahlili size 30 satır sayı verir: hemoglobin, lökosit, kreatinin...

Ama hasta olarak istediğiniz şey **"iyisin"** veya **"şu konuda dikkat"** veya **"hemen hastaneye"**.

Doktorun yaptığı iki şey:
1. Sayıları **gruplayıp** anlamlı hâle getirir (bu grup normal, bu grup sınırda)
2. Bir **karar** verir ve **gerekçesini** söyler

Ve kritik bir detay var: iyi bir doktor her sınır değer için "hemen hastaneye" demez. Çünkü her seferinde alarm çalarsanız, hasta alarmları dinlemeyi bırakır.

Bu, misyon raporunun en önemli tasarım kararı — aşağıda.

---

## Rota analizi (`route_analysis.py`)

ETH Zürih'in `lunar_planner` projesindeki **PathAnalysis** aracından ilham alınmış.

`simulate_path` zaten adım başına `RoverState` dizisi üretiyor; `summarize_simulation` onu skaler toplamlara indiriyor. Bu modül eksik olan **dağılım görünümünü** ekliyor:

| Çıktı | Ne |
|---|---|
| `slope_histogram` | Rotanın ne kadarı hangi eğim bandında (0-5°, 5-10°, 10-15°, 15-20°, 20-25°) |
| `risk_breakdown_pct` | Adımların yüzde kaçı hangi risk seviyesinde |
| `min_surface_temp_c` / `max_surface_temp_c` | Gerçekten geçilen termal uçlar |
| `waypoint_count` | Yol noktası sayısı |

**Ayrı bir modül olması kasıtlı:** böylece `summarize_simulation`'ın test edilmiş çıktı şekli değişmiyor.

**Bir detay:** Bant aralığının dışına düşen değerler en yakın kenar bandına düşüyor — sessizce kaybolmuyor.

---

## Misyon raporu (`report.py`) — karar mantığı

### Üç sonuç

| Karar | Anlamı |
|---|---|
| **`NO-GO`** | Rover hayatta kalamaz veya rotayı bitiremez |
| **`GO-WITH-RISK`** | Tamamlanabilir ama izlenmesi gereken bulgular var |
| **`GO`** | İhlal yok |

### NO-GO'yu tetikleyen dört şey (bloklayıcı)

| Sebep | Anlamı |
|---|---|
| `stranded` | Rover mahsur kaldı |
| `execution_truncated` | Yürütme yarıda kesildi |
| `shadow_limit_exceeded` | Gölge limiti aşıldı |
| `critical_steps` | Risk modeli en az bir adımı KRİTİK saydı |

### GO-WITH-RISK'e düşüren dört şey (uyarı)

| Sebep | Eşik |
|---|---|
| `high_risk_steps` | Yüksek veya üstü riskli adım var |
| `battery_watch` | Minimum batarya **%30'un** altında |
| `peak_power_exceeded` | Tepe güç aşıldı |
| `recharges_required` | Şarj molası gerekti |

### En önemli tasarım kararı

> **NO-GO, rover'ın hayatta kalamayacağı veya bitiremeyeceği şeyler için ayrılmıştır. Daha yumuşak olan her şey NO-GO yerine GO-WITH-RISK'e düşer.**
>
> **Çünkü %28'lik bir batarya çukuru için NO-GO diyen bir rapor, operatöre onu görmezden gelmeyi öğretir.**

Bu, alarm yorgunluğunun (alarm fatigue) bilinçli olarak tasarıma sokulması. Bir güvenlik sisteminin en büyük düşmanı, kimsenin dinlemediği bir alarmdır.

### İkinci önemli kural: yokluk bulgu değildir

> **"Eksik bir sayaç, eksik bir batarya değeri ve eksik bir `execution` bloğu, hepsi 'raporlanacak bir şey yok' demektir."**

Yani veri yoksa uyarı üretilmiyor. `None`, "kötü" anlamına gelmiyor.

Bu, frontend'in `undefined` karşılaştırmalarıyla da tutarlı.

---

## İki uygulama, testle kilitli

Karar mantığı **iki yerde** var:

| Yer | Dosya |
|---|---|
| Backend | `backend/app/report.py` |
| Frontend | `frontend/src/features/mission-report/report.ts` |

**Neden iki tane:** Frontend'in kendi rapor ekranı var ve backend'e gitmeden karar gösterebilmeli.

**Neden tehlikeli:** *"Ekranda GO, asistandan NO-GO duyan bir operatör, ikisine de güvenmemekten başka bir şey öğrenmemiştir."*

**Çözüm:** `test_report_verdict.py` ikisini paylaşılan bir fikstüre karşı sabitliyor — tıpkı `test_review_fixes`'in `cost_vec`'i `cost_engine`'e sabitlediği gibi.

`BATTERY_WATCH_PCT = 30.0` sabiti bile parite testiyle kontrol ediliyor: test, frontend dosyasındaki literal değeri çıkarıp backend'inkiyle karşılaştırıyor.

---

## İki şey kasıtlı olarak burada YOK

### 1. Gerekçe metinlerinde rakam yok

Her sebep metni **rakamsız**. Bir test bunu doğruluyor: metinlerde hiç rakam olmamalı.

**Neden:**
- Frontend rakamlarını `toFixed(1)` ile yerleştiriyor → bu, nokta ondalıklı sayı üretiyor
- `ai_grounding` (AI doğrulama katmanı) nokta ondalıklı sayıları **yapısal olarak bloklıyor**
- Yani gerekçeye sızan bir rakam, **aşağıdaki bütün AI cevabını bloklar**

Sayılar ayrı yoldan gidiyor: `ai_analysis.verdict_registry` içinde kayıtlı metrikler olarak.

### 2. Hiçbir AI tipi import edilmiyor

Bu modül *"bu rotanın durumu nedir"* sorusunu cevaplıyor — ki bunu ROS 2 kabuğu ve gelecekteki bir `/api/report` ucu da asistan kadar istiyor.

O yüzden `cost_engine` gibi **framework'süz** kalıyor.

---

## Kodda nerede?

```
backend/app/route_analysis.py
  route_statistics()            ← dağılım görünümü
  DEFAULT_SLOPE_BINS_DEG

backend/app/report.py
  decide_verdict()              ← karar mantığı
  decide_verdict_from_snapshot()
  VerdictReason / VerdictResult
  BATTERY_WATCH_PCT = 30.0
  reason_codes() / verdict_sentence()

frontend/src/features/mission-report/report.ts   ← ikiz, testle kilitli
backend/test_report_verdict.py                   ← parite testi
```

---

## Jüri soruları

**S: "Sistem GO/NO-GO kararı veriyor mu?"**
Evet, üç seviyeli: GO, GO-WITH-RISK, NO-GO. Ve her karar gerekçe listesiyle geliyor — hangi bulgular kararı sürükledi.

**S: "NO-GO ne zaman veriliyor?"**
Sadece dört durumda: rover mahsur kaldı, yürütme kesildi, gölge limiti aşıldı, veya risk modeli bir adımı kritik saydı. Yani "hayatta kalamaz veya bitiremez" durumları. Bunun dışındaki her şey GO-WITH-RISK.

**S: "Neden %28 batarya için NO-GO demiyorsunuz?"**
Bilinçli bir karar ve gerekçesi kodda yazılı: "%28'lik bir batarya çukuru için NO-GO diyen bir rapor, operatöre onu görmezden gelmeyi öğretir." Alarm yorgunluğu gerçek bir güvenlik riski. Sık çalan alarm, çalmayan alarmdan daha tehlikeli olabilir. %30'un altı bir **uyarı** olarak raporlanıyor, karar GO-WITH-RISK oluyor.

**S: "Aynı karar iki yerde var, bu risk değil mi?"**
Risk ve o yüzden testle kilitledik. Frontend kendi rapor ekranını backend'e gitmeden gösterebilmeli, o yüzden mantık iki yerde. Ama `test_report_verdict.py` ikisini paylaşılan bir fikstüre karşı karşılaştırıyor. Hatta %30 eşiği bile parite testiyle kontrol ediliyor — test frontend dosyasındaki literal değeri çıkarıp backend'inkiyle karşılaştırıyor.

**S: "Gerekçe metinlerinde neden rakam yok?"**
Çünkü frontend rakamlarını `toFixed(1)` ile yerleştiriyor, bu nokta ondalıklı sayı üretiyor, ve AI'ın doğrulama katmanı nokta ondalıklıları yapısal olarak bloklıyor. Yani gerekçeye sızan tek bir rakam, aşağıdaki bütün AI cevabını bloklardı. Sayılar ayrı yoldan, kayıtlı metrik olarak gidiyor. Bir test metinlerin rakamsız olduğunu doğruluyor.

**S: "Rota analizi ne kazandırıyor?"**
Dağılımı. Toplamlar bir şeyi gizler: iki rota aynı ortalama eğime sahip olabilir ama biri baştan sona 10 derece, öbürü çoğunlukla düz artı bir yerde 24 derece. Aynı ortalama, tamamen farklı risk. Eğim histogramı ve risk yüzde dağılımı bunu görünür kılıyor. Fikir ETH Zürih'in lunar_planner projesindeki PathAnalysis aracından.
