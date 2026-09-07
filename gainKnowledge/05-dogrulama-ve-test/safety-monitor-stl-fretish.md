# Formal Güvenlik Monitörü (D3) — "İhlal Var" Yerine "Ne Kadar Marj Var"

**Kodda:** `backend/app/safety_monitor.py`, `lunapath_ros/.../safety_monitor_node.py`
**API:** `POST /api/safety-check`, her plan cevabında `safety_margins` bloğu
**Özellik kodu:** D3

---

## Nedir?

Üç parçalı bir sistem:

1. **12 formal gereksinim** (LP-R01 … LP-R12), **FRETISH** dilinde yazılmış
2. Her birinin **STL**'e (Signal Temporal Logic) elle çevrilmiş hâli
3. Her planlanan rotayı bu gereksinimlere karşı **sayısal marjla** denetleyen bir çalışma zamanı monitörü

Çıktı ikili değil: **"gereksinim sağlandı, marj 12,06 yüzde puanı"** gibi.

---

## Hangi problemi çözüyor?

D3'ten önce kısıt denetimi ikiliydi:

- `check_profile_constraints` marjsız *"satisfied: true"* diyordu
- `replan_triggers` eşik karşılaştırıyordu
- **Ve hiçbiri — planlayıcılar dâhil — termal zarfa bakmıyordu**

İkili bir cevabın iki problemi var:

**Problem 1 — Ne kadar yakınım bilmiyorum.** *"Batarya kısıtı sağlandı"* diyor. Ama %20,1 ile mi sağlandı, %80 ile mi? Birincisi kıl payı, ikincisi rahat. Aynı cevap.

**Problem 2 — Hangi anda, nerede bilmiyorum.** İhlal varsa rotanın neresinde?

---

## Analoji: Sınav notu ve barajlar

Bir öğrenci "geçti" diyorsunuz. Ama 51 ile mi geçti, 95 ile mi?

51 ile geçen öğrenci, bir sonraki sınavda küçük bir aksilikte kalır. 95 ile geçen aynı aksiliği hisseder bile.

Şimdi bir de şu: "geçti/kaldı" cevabı, **hangi soruda zorlandığını** söylemiyor.

STL robustness (dayanıklılık) tam olarak bu iki eksiği kapatıyor:
- **Ne kadar** geçti (ρ değeri, gerçek birimlerde: saat, °C, yüzde puanı, derece, metre)
- **Nerede** en zorlandı (marjın en küçük olduğu an ve hücre)

Bir başka analoji: **uçak kalkış kontrol listesi.** Pilot "yakıt yeterli mi?" diye sormaz, "yakıt ne kadar, gereken ne kadar, fark ne?" diye sorar. Fark negatifse uçmuyorsunuz; fark küçükse uçuyorsunuz ama biliyorsunuz.

---

## FRETISH nedir?

**FRET** = NASA'nın Formal Requirements Elicitation Tool'u. **FRETISH** onun yapılandırılmış doğal dili:

```
[scope] [condition] the rover shall [timing] [response]
```

Yani doğal dile benziyor ama gramerli — bir insan okuyabiliyor, bir makine ayrıştırabiliyor.

⚠️ **Dürüstlük notu:** FRET aracının kendisi **kurulmadı.** Cümleler grameri **elle** izliyor ve dosya bunu açıkça söylüyor.

---

## 12 gereksinim

| ID | Ad | FRETISH / STL | Birim |
|---|---|---|---|
| **LP-R01** | `shadow_endurance` | Kesintisiz gölge, rover'ın dayanımını aşmasın | saat |
| **LP-R02** | `soc_reserve` | `G (soc_pct >= soc_min)` | yüzde puanı |
| **LP-R03** | `soc_recovery` | Rezervin altına düşerse **6 saat içinde** şarj olsun | saat |
| **LP-R04** | `electronics_thermal` | İç sıcaklık elektronik zarfında kalsın | °C |
| **LP-R05** | `battery_thermal` | İç sıcaklık batarya zarfında kalsın | °C |
| **LP-R06** | `step_slope` | `G (drive_slope_deg <= slope_max_deg)` | derece |
| **LP-R07** | `cross_slope` | `G (lateral_slope_deg <= slope_lateral_max_deg)` | derece |
| **LP-R08** | `dte_while_moving` | `G (moving -> earth_visible)` | saat/gün |
| **LP-R09** | `safe_haven_leg` | `G (haven_margin_h >= 0)` | saat |
| **LP-R10** | `goal_reached` | `F at_goal` | metre |
| **LP-R11** | `soc_at_goal` | `G (at_goal -> soc_pct >= soc_min)` | yüzde puanı |
| **LP-R12** | `thermal_dwell` | Termal dwell marjı korunsun (C6) | saat |

Her eşik **rover kataloğundan** okunuyor — sabit gömülü değil.

---

## STL nedir ve "space robustness" ne demek?

**STL** = Signal Temporal Logic. Zaman içindeki sinyaller üzerine mantık:

- `G (φ)` = *"her zaman φ"* (Globally)
- `F (φ)` = *"eninde sonunda φ"* (Finally)

**Space robustness** (uzamsal dayanıklılık), Donzé & Maler (2010)'ın kavramı: formülün doğru/yanlış olmasının ötesinde, **ne kadar** doğru olduğunu ölçüyor.

Örnek: `G (soc >= 20)` gereksinimi için, rotanın en düşük SOC'si %32,06 ise → **ρ = 12,06 yüzde puanı.**

Negatif ρ = ihlal, ve büyüklüğü ihlalin şiddetini veriyor.

### Zaman pencereli davranış nasıl ele alındı?

*"En fazla H saat kesintisiz gölge"* veya *"rezervin altına düştükten sonra 6 saat içinde şarj"* gibi zaman pencereli gereksinimler, **türetilmiş saat sayaçlarına** katlanıyor.

**Sonucu:** Her katalog formülü sınırsız bir `G`/`F` oluyor ve robustness'ı **örnekleme adımından bağımsız** — saat, derece, °C veya yüzde puanı cinsinden.

Bu önemli: aksi hâlde daha sık örneklenen bir rota daha güvenli görünürdü.

---

## İki motor, her istekte çapraz kontrol

| Motor | Ne |
|---|---|
| **RTAMT 0.3.5** | AIT'nin ayrık zamanlı çevrimdışı STL kütüphanesi |
| **Yerleşik değerlendirici** | Aynı semantiği uygulayan kendi kodumuz |

RTAMT içe aktarılabilir olduğunda **her değerlendirme iki motorda birden** çalışıyor ve en büyük uyuşmazlık raporlanıyor.

RTAMT'nin sonlu-iz kuralları ölçülüp testlere sabitlendi (2026-09-04'te):
- Sınırlı bir pencere, var olan örneklere kırpılıyor
- Boş pencere vacuous: `always` için +∞, `eventually` için −∞
- Sınırsız operatörler izin sonuna kadar koşuyor

**Ölçülen sonuç:** İki motor gerçek rotalarda **bit düzeyinde aynı** (çapraz kontrol 0). 20 rastgele iz × 6 formül ailesinde **1e-9'a kadar** uyumlu.

---

## Site11'de ölçülen — ve rahatsız edici bulgu

### VIPER haven-haven, 2027-05-30 (41 durum, 7,36 saat)

| Gereksinim | Marj (ρ) |
|---|---|
| Gölge dayanımı (LP-R01) | 91,45 sa ✅ |
| SOC rezervi (LP-R02) | 12,06 puan ✅ |
| **Adım eğimi (LP-R06)** | **0,48°** ⚠️ |
| Yanal eğim (LP-R07) | 1,19° ✅ |
| Dünya linki (LP-R08) | 199,93 sa ✅ |
| Haven marjı (LP-R09) | 199,80 sa ✅ |

**Adım eğimi 0,48 derece:** Rota, eğim limitine **yapışıyor**. Yarım derecelik bir hata rotayı geçersiz kılar. Ve bu, [B3'ün DEM klonlarıyla bulduğu](../01-arazi-ve-veri/dem-belirsizligi-100-klon.md) sonuçla birebir örtüşüyor: rota 100 klonun sadece 1'inde geçilebilir kalıyor.

**İki bağımsız yöntem, aynı sonuca varıyor.**

### LP-R04 ve LP-R05 İHLAL

| Gereksinim | Değer | Zarf |
|---|---|---|
| Elektronik iç sıcaklık | **−7,96 °C** | −20 … 50 °C ✅ sınırda |
| **Batarya iç sıcaklık** | **−27,96 °C** | **0 … 35 °C** ❌ İHLAL |

Durum 16, hücre (73,118).

**Teşhis:** Statik `sunlit_peak` termal katmanı artı `surface_to_inner` ofsetleri, bataryayı zarfının **28 K altına** koyuyor. Isıtıcı gücü enerji modelinde ücretlendiriliyor ama **sıcaklık modelinde hiçbir şey ısıtmıyor.** Ve mevcut hiçbir denetim buraya bakmamıştı.

> **Bu bulgu yumuşatılmadan raporlandı — ve [C6'nın](../02-isik-golge-ve-termal/termal-dwell-ve-operasyon-zarfi.md) doğrudan girdisi oldu.**

Bu, bir doğrulama katmanının değerinin en net kanıtı: D3 bir problemi ölçtü, C6 o problemi çözmek için yazıldı.

### LPR-1, 2026-09-28

| Gereksinim | Marj |
|---|---|
| Gölge | 49,79 sa |
| SOC | 76,16 puan |
| Termal | −17,96 / −27,96 °C ❌ |
| **Haven leg kuralı** | **Sınırsız ihlal** — link 184,6 saat sonra bitiyor, o ay gününde ulaşılabilir haven yok |

### SHERPA bozulmaları altında (1 000 koşum)

VIPER'ın SOC marjı, plandaki **12,1 puandan** şuraya düşüyor:

| Persentil | Marj |
|---|---|
| p5 | **−20,0 puan** |
| p50 | **−20,0 puan** |
| p95 | −4,9 puan |

**Rezerv koşumların %98,6'sında delinmiş.**

Yani deterministik planda 12 puan marjla geçen gereksinim, gerçekçi bozulmalar altında neredeyse her zaman ihlal ediliyor.

### İkili kontrolün neyi kaçırdığı

`/api/compare` dört profilde batarya iç sıcaklığını **−46,04 °C** gösterirken, ikili `constraint_check` **dördü için de "satisfied"** diyor.

**Bu, D3'ün var oluş sebebinin tek cümlelik özeti.**

---

## Tasarım detayları

### Monitör bir planı asla düşürmez

Monitör hatası loglanıyor ve `safety_margins` bloğu atlanıyor — ama plan cevabı yine dönüyor.

**Neden:** Bir güvenlik monitörü, ölçtüğü sistemi bozmamalı.

### Sessiz geri düşüş yok

`POST /api/safety-check` şu durumlarda **422** dönüyor:
- Zamanın geri gitmesi
- NaN değer
- Bilinmeyen motor
- `engine=rtamt` istenip RTAMT paketi yoksa

Sessizce başka bir motora düşmüyor. Çünkü hangi motorun çalıştığını bilmeden marja güvenemezsiniz.

### ROS tarafı

`safety_monitor_node.py` telemetriden **ihlal başına bir `ReplanTrigger`** üretiyor: `trigger_id = "safety:LP-R02"` gibi.

### Gereksinim kataloğu dışa aktarılıyor

`scripts/export_fret_requirements.py` → `docs/requirements/lunapath.fret.json`

Ve bu dosyanın **katalogla eşitliği testle kilitli** — yani doküman koddan ayrışamıyor.

---

## Maliyet

| İşlem | Süre |
|---|---|
| Plan içinde | milisaniye |
| `/api/safety-check`, 500 örnek, yerleşik motor | 12–15 ms |
| Aynısı, RTAMT | 28–48 ms |

---

## İlham kaynağı

- **NASA FRET** — Formal Requirements Elicitation Tool ve FRETISH dili
- **Donzé & Maler (2010)** — STL space robustness
- **RTAMT 0.3.5** — AIT Austrian Institute of Technology

---

## İddia sınırı — çok önemli

✅ **Doğru:** *"Gereksinimler FRETISH'te yazıldı, STL'e çevrildi ve her rota **çalışma zamanı izleme** (runtime monitoring) ile nicel marjla denetleniyor."*

❌ **YANLIŞ:** *"FRET aracıyla üretildi."* — Araç kurulmadı, cümleler grameri elle izliyor.

❌ **YANLIŞ:** *"Model checking ile ispatlandı."* — Yalnız **somut izler** denetleniyor. Monitör, bir izin gereksinimleri nicel marjla sağladığını gösteriyor; **bütün izler hakkında hiçbir şey ispatlamıyor.**

Bu sınır her cevapta `safety_margins.monitor.claim` alanında tekrarlanıyor.

---

## Kodda nerede?

```
backend/app/safety_monitor.py
  STL AST + iki robustness motoru
  iz dönüştürücüler (2-D simülasyon / 4-D plan / telemetri)
  REQUIREMENTS katalogu (LP-R01 … LP-R12)
  evaluate_catalogue() / trace_from_states()

lunapath_ros/lunapath_ros/safety_monitor_node.py
scripts/export_fret_requirements.py
scripts/safety_monitor_report.py
docs/requirements/README.md + lunapath.fret.json
docs/research/safety_monitor_report.md
```
81 yeni test.

---

## Jüri soruları

**S: "Formal doğrulama mı yapıyorsunuz?"**
Hayır, **formal çalışma zamanı izleme** yapıyoruz ve bu ayrımı her cevapta belirtiyoruz. Model checking, bir sistemin bütün olası davranışlarının bir özelliği sağladığını ispatlar. Biz **belirli bir rotanın** gereksinimleri sağladığını, sayısal marjla ölçüyoruz. Bu daha zayıf ama uygulanabilir bir iddia.

**S: "FRET kullandınız mı?"**
Aracın kendisini kurmadık. Gereksinimleri FRETISH gramerini **elle** izleyerek yazdık ve dosya bunu açıkça söylüyor. Cümleler makine tarafından üretilmedi.

**S: "İkili kontrol yerine marj ne kazandırdı?"**
En net örnek: `/api/compare` dört profilde batarya iç sıcaklığını −46 °C gösterirken ikili kontrol dördü için de "sağlandı" diyordu. Marj tabanlı monitör aynı rotalarda LP-R05'in 28 K ile ihlal edildiğini buldu. Ve bu bulgu C6 özelliğinin yazılmasını tetikledi.

**S: "İki motor kullanmak abartı değil mi?"**
Değil, çünkü STL semantiğinde sonlu iz kuralları incelikli (boş pencere ne döner, sınırlı pencere nasıl kırpılır). Tek motorla o kuralları yanlış anladığınızı fark edemezsiniz. İki motor gerçek rotalarda bit düzeyinde aynı sonucu veriyor, 20 rastgele izde 1e-9'a kadar uyumlu.

**S: "Sonuçlar iyi mi?"**
Hayır ve bu doğru olan. VIPER rotası adım eğimi limitine 0,48 derece marjla yapışıyor — B3'ün DEM klonlarıyla bulduğu "100 klonun sadece 1'inde geçilebilir" sonucuyla birebir örtüşüyor. Termal gereksinimler ihlal ediliyor. SHERPA bozulmaları altında SOC rezervi koşumların %98,6'sında deliniyor. Bunları yumuşatmadık; biri (termal) doğrudan yeni bir özelliğin (C6) gerekçesi oldu.

**S: "Monitör bir planı reddedebiliyor mu?"**
Hayır, bilinçli olarak. Monitör hatası olursa blok atlanıyor ama plan yine dönüyor. Bir güvenlik monitörü ölçtüğü sistemi bozmamalı. Karar operatörün.
