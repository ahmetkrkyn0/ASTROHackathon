# Termal Dwell ve Operasyon Zarfı (C6) — "Burada Ne Kadar Durabilirim?"

**Kodda:** `backend/app/thermal_dwell.py`
**API:** `GET /api/thermal-dwell`, `GET /api/thermal-envelope`, `/api/plan-4d` içinde `require_thermal_dwell`, `POST /api/replan` içinde `entrenchment`
**Özellik kodu:** C6

---

## Nedir?

İki soruya cevap veren katman:

1. **Dwell süresi:** Rover şu hücrede, şu andan itibaren **kaç saat** durabilir? (Yani iç sıcaklığı ne zaman batarya zarfının dışına çıkar?)
2. **Operasyon zarfı:** Hangi geometrilerde (Güneş yüksekliği × eğim) park etmiş bir rover **hiç** zarfı terk etmez?

Üstüne bir üçüncü: rover **saplanırsa** (entrenchment), saati ne kadar var?

---

## Hangi problemi çözüyor?

C6'dan önce termal kontrol **statikti**: bir hücrenin sıcaklığı okunur, zarfa karşı kontrol edilir, "içeride" veya "dışarıda" denirdi.

Sonra D3 (formal güvenlik monitörü) devreye girdi ve şunu ölçtü:

> **Site11'deki her gerçek rota LP-R04 ve LP-R05'i ihlal ediyor.**

Yani hiçbir rota termal gereksinimleri geçemiyordu. Sebep:

1. Denge sıcaklığı zaten zarfın dışında
2. Modelin **zaman ekseni yoktu** — "ne kadar süre dışarıda" diye sorulamıyordu
3. Modelin **ısıtıcısı yoktu**

Statik bir kontrol "ihlal" diyor ama ne kadar ciddi bir ihlal olduğunu söyleyemiyor. C6 buna bir **saat** ekledi.

---

## Analoji: Soğuk suya girmek

Buzlu suya girdiğinizde anında ölmezsiniz. Ama bir saatiniz başlar.

- İlk 1-2 dakika: rahatsız ama sorun yok
- 10-15 dakika: hipotermi başlıyor
- 30 dakika+: ölümcül

Şimdi eski modelin ne yaptığını düşünün: "su 4 °C, insan vücudu 37 °C olmalı, **ihlal**." Doğru ama işe yaramaz — çünkü "5 dakika daha dayanırım" ile "şu an ölüyorum" arasındaki farkı söylemiyor.

C6'nın eklediği şey **kronometre**: "bu suda, bu sıcaklıkta, şu andan itibaren 23 dakikanız var."

Ve operasyon zarfı şu: "hangi su sıcaklıklarında **sonsuza kadar** kalabilirsiniz?" (mesela 30 °C'lik havuzda süre sınırı yok).

---

## Nasıl çalışıyor?

### Makaleyi gerçekten okumak — üç düzeltme

Bu, projenin metodolojik dürüstlüğünün en iyi örneği. NASA JSC/MSFC'nin VIPER makalesi (ICES-2025-376) referans alındı. Ama makale **gerçekten okunduğunda** projenin kendi araştırma belgesindeki üç hata çıktı:

**Düzeltme 1 — Zarf grafiğinin eksenleri.** Belgede "azimut × yükseklik × eğim" yazıyordu. Gerçekte JSC'nin grafiği **eğim × rover başlığına göre Güneş azimutu**, misyonun **maksimum** Güneş yüksekliğinde: 16 azimut × 6 eğim = 96 kararlı durum vakası, 60+ bileşen, Thermal Desktop yazılımıyla. Yükseklik ekseni makalenin **gelecek işi**.

**Düzeltme 2 — "AFT'nin 12 °C üstü / 77 °C" ne demek?** Bu bir vaka sonucu değil, bir aviyonik kutusu için **AFT normalizasyonu örneği** (AFT = Allowable Flight Temperature, izin verilen uçuş sıcaklığı).

**Düzeltme 3 — "Tolere edilebilir saplanma süresi" termal bir büyüklük değil.** JSC'nin kastettiği şey **haven penceresi**: ay gecesinden önce hedef güvenli limana varmak için kalan süre.

> Bu üç düzeltme araştırma belgesine işlendi. Jüriye anlatılabilecek bir şey: **kaynağı okumadan alıntılamadık.**

### Model: kapalı formda dwell

```
1. Hücrenin yüzey sıcaklığı zaman içinde: surface(t)   ← maliyet küpünün zaten hesapladığı seri
2. Hedef iç sıcaklık:                     surface_to_inner(surface(t))
3. Rover'ın gerçek iç sıcaklığı buna τ zaman sabitiyle gevşiyor
4. exit_time_h = bu eğrinin zarfı terk ettiği an
```

`exit_time_h` üç durumu ayırıyor:
- Zaten dışarıdaysa → **0**
- Hedef zarfın içindeyse → **sınırsız** (hiç çıkmaz)
- Aksi hâlde → `τ · ln(...)` kapalı formu

`build_dwell_cube` bütün başlangıç dilimlerini birlikte ilerletiyor ve bir (başlangıç, blok) çiftini, o bloğun hedefi artık zarftan çıkamaz hâle geldiği anda emekliye ayırıyor. Sonuç:

**`max_dwell_h[t, y, x]`** — üç boyutlu bir "burada kaç saat durabilirim" küpü.

### Bit-eşitlik garantisi

`cost_cube.surface_temperature_series` dışarı çıkarıldı ve maliyet küpü ile dwell küpü **aynı diziyi** kullanıyor. Testle bit-eşit doğrulanıyor.

**Neden önemli:** planlayıcı bir yüzey sıcaklığı serisi görüp dwell hesabı başka bir seri görürse, planlayıcı kendi kısıtını ihlal eden bir rota bulabilir. Tek kaynak, tek gerçek.

---

## En büyük bulgu: kısıt sürede değil, sıcaklıkta

Bu, C6'nın en öğretici kısmı ve jüriye anlatılacak en iyi hikâyelerden biri.

### İlk deneme ve nasıl kandırıldı

İlk sürüm mantıklı görünen şeyi yaptı: **blok başına ardışık hareketsiz saatleri sınırla.** Yani "aynı blokta 0,5 saatten fazla bekleyemezsin."

Planlayıcının bulduğu açık: **iki karanlık blok arasında mekik dokumak.**

Blok A'da 0,4 saat bekle → Blok B'ye geç → orada 0,4 saat bekle → A'ya dön → sayaç sıfırlandı → tekrar.

Rover kuralı hiç ihlal etmedi ve **aynı şekilde dondu.**

> Bunu projenin kendi testi yakaladı. Bu, iyi test tasarımının değerini gösteren bir örnek.

### Düzeltme: kısıtlanan şey iç sıcaklığın kendisi

Çözüm, kuralı sıkılaştırmak değil, **doğru büyüklüğü kısıtlamaktı.**

Artık planlayıcının her etiketi (label) iç sıcaklığı taşıyor:
- **Bekleme hamlesi** → beklenen bloğun sıcaklığı
- **Hareket hamlesi** → varış bloğunun sıcaklığı

Ve rover'ı zarfın dışına çıkaracak **her geçiş** reddediliyor.

Bir bloğun dwell süresini aşan bekleme? O zaten böyle bir geçiş. Yani eski kural yeni kuralın özel hâli — ama mekik dokuma açığı kapandı, çünkü sıcaklık sayaç gibi sıfırlanmıyor, fizik gibi devam ediyor.

**Ders:** Bir kısıtı vekil bir büyüklük üzerinden koyarsanız, optimizasyon vekili kandırmanın yolunu bulur. Gerçek büyüklüğü kısıtlayın.

### Maliyeti

Beşinci baskınlık ekseni (dominance axis) olarak termal marj eklendi. Tolerans, zarf genişliğinin onda biri; on anahtar kutusu.

Denenen alternatif: batarya ekseninin %1'i / 400 kutu → gündüz rotasının kısıtlı araması **2,3 GB ve on dakikayı aştı, bitmedi.** Yani kaba kuantizasyon bir tercih değil, zorunluluk.

---

## Isıtıcı: açık bir varsayım

Bu, dürüstlük tasarımının en net örneklerinden biri.

**Problem:** Katalogda `p_heater_w` (ısıtıcı gücü, watt) var. Ama watt'tan kelvin'e kaynaklı bir bağ **yok** — yani "25 W ısıtıcı iç sıcaklığı kaç derece yükseltir" sorusunun yayınlanmış bir cevabı yok.

**Yapılan:**

| `heater_model` | Davranış |
|---|---|
| `"none"` (varsayılan) | Isıtıcı sadece **enerji** modelinde (eskiden olduğu gibi). Sıcaklık modelinde yok. |
| `"thermostat_assumed"` | Açık bir **varsayım**: hayatta kalma ısıtıcısı zarfın alt sınırını tutar. |

Varsayımın kaynağı kodda bir sabitte yazılı: `constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE`.

**Katalog alanı eklenmedi** — çünkü bu bir rover spesifikasyonu değil, bir varsayım. Katalogda durursa gelecekte biri onu ölçülmüş sanabilir.

**Ve:** `thermal_tau_s` alanı olmayan bir rover (LUVMI-M) dwell hesabı **almıyor** — `unavailable` + gerekçe dönüyor, denge tabanlı eski kararını koruyor.

---

## Site11'de ölçülen gerçek sayılar

### Zarf matrisi (LPR-1)

| Kategori | Kutu sayısı |
|---|---|
| Sınırsız (hiç zarfı terk etmez) | **19** |
| Soğuk-sınırlı | **173** |
| "Sıcak-sınırlı" | 13 |

**13 sıcak kutunun açıklaması:** hepsi yüzey sıcaklığı −23,5 … −0,4 °C olan hücreler. Soğuk dalın +60 K ofseti bunları 35 °C'nin üstüne atıyor. **Ofset modelinin eseri ve öyle etiketli** — gerçek bir sıcak problem değil.

**Ve büyük bulgu:** *"JSC'nin sıcak yanı Site11'de bizim modelimizde yok."* Site11'in problemi tamamen soğuk tarafta.

### Dwell küpü, ilk dilim

| Senaryo | Sınırsız | Soğuk-sınırlı | Sıcak | Sonlu medyan |
|---|---|---|---|---|
| Gündüz rotası | %3,2 | %96,0 | %0,8 | **0,547 sa** |
| Ay gecesi | %0 | %100 | %0 | 0,547 sa |
| VIPER | %17,2 | %73,2 | %9,5 | 0,622 sa |

**Yani ortalama bir hücrede rover yaklaşık yarım saat durabiliyor.**

### D3'ün ihlalini dinamikle yeniden okumak

Üç standart rota da (kısıtsız, 17,5 °C başlangıç, ısıtıcısız):
- Zarfı **0,53–0,70 saat içinde** terk ediyor
- Ve geri dönmüyor
- Gündüz rotası minimum −15,7 °C'ye iniyor; 42 durumun 34'ü zarf dışında

**İhlal duruyor. Ama artık bir süresi var.** Bu, statik modelin veremediği şey.

### Kısıt açıkken

| `heater_model` | Sonuç |
|---|---|
| `"none"` | Üç rotayı da **gerekçeli 404** ile reddediyor (gündüz: 229 435 geçiş reddedildi) |
| `"thermostat_assumed"` | Üçünü de geçiriyor, **rota değişmeden** (41 / 116 / 8 hamle; iç sıcaklık minimumları +5,1 / +0,6 / +6,4 °C) |

**Yorumu:** Soğuk taraf, ısıtıcı olduğunda çözülüyor; sıcak taraf Site11'de hiç bağlamıyor.

### Saplanma (entrenchment)

| Durum | Termal bütçe |
|---|---|
| Ay gecesi başlangıcı | 0,485 sa |
| Rota ortası | 0,420 sa |
| Gündüz başlangıcı | 0,486 sa |

Ama **haven penceresi LPR-1 için her yerde 0 saat** — çünkü A1'in bulgusuna göre Site11'de LPR-1 için ulaşılabilir safe haven yok.

**Sonuç:** genel saplanma seviyesi her durumda "fail". JSC'nin saati, rover daha sıkışmadan dolmuş. Ve rapor bunu tam olarak böyle söylüyor.

---

## API yüzeyi

| Uç / parametre | Ne verir |
|---|---|
| `/api/plan-4d` → `require_thermal_dwell` | Zarf kısıtını arama içinde uygular |
| `/api/plan-4d` → `initial_inner_c`, `heater_model` | Başlangıç sıcaklığı ve ısıtıcı varsayımı |
| `/api/plan-4d` cevabı → `thermal_dwell` bloğu | `path_inner_c`, `path_max_dwell_h`, `path_dwell_margin_h`, `path_stay_hours`, `metrics.min_dwell_margin_h` |
| `GET /api/cell-telemetry?thermal_dwell=true` | Hücre kartı + tolere edilebilir saplanma süresi (termal + haven penceresi) |
| `POST /api/replan` → `state.entrenched_hours` | `entrenchment` bloğu ve tetikleyici (ok / warning %50 / critical %80 / fail) |
| `GET /api/thermal-dwell` | Dwell katmanı |
| `GET /api/thermal-envelope` | heat1d transient'inden Güneş yüksekliği × Güneş'e paralel eğim zarf matrisi (önbelleksiz **422**, asla sentetik matris) |

Güvenlik kataloğuna **LP-R12** gereksinimi eklendi.

---

## İlham kaynağı

**Slusser, Turk, Stewart, Page, Barragan, Mittag** — NASA JSC/MSFC, ICES-2025-376 (International Conference on Environmental Systems, 2025).

VIPER için iki çerçeve:
1. **Unlimited Operations Envelope** — parkta rover'ın asla AFT'yi aşmadığı geometriler
2. **Tolerable Entrenched Time** — hareketsiz kalmış aracın "saati dolmadan" ne kadar durabileceği

C6 ikisini de **LunaPath'in kendi modeliyle** kuruyor. Neyin JSC'ye, neyin bize ait olduğu `THERMAL_DWELL_CLAIM` ve `JSC_QUOTED` sabitlerinde yazılı ve her cevapla gidiyor.

---

## İddia sınırı

- ❌ **Hiçbir termal doğruluk iddiası yok.** Model `MODEL / UNCALIBRATED`, her blok bunu söylüyor. Diviner doğrulaması ayrı bir işin (C5) konusu.
- ⚠️ **Isıtıcı bağı varsayım**, ölçüm değil, ve varsayım olarak etiketli.
- 📎 JSC'nin kendi sayıları `JSC_QUOTED` içinde **alıntı** olarak duruyor, bizim ölçümlerimizle karıştırılmıyor.

---

## Kodda nerede?

```
backend/app/thermal_dwell.py
  exit_time_h()            ← kapalı form zarf terk zamanı
  build_dwell_cube()       ← max_dwell_h[t, y, x]
  route_dwell_report()     ← rota boyunca dwell raporu
  THERMAL_DWELL_CLAIM / JSC_QUOTED

scripts/build_thermal_envelope_cache.py
scripts/thermal_dwell_report.py
docs/research/thermal_dwell_report.md
```
60 yeni test eklendi.

---

## Jüri soruları

**S: "Bu özellik ne kazandırdı?"**
Bir ihlali bir **süreye** çevirdi. Önce sistem "termal gereksinim ihlal edildi" diyordu, bu kadar. Şimdi "0,53 saat içinde zarfı terk ediyor ve geri dönmüyor" diyor. Birincisi bir alarm, ikincisi bir karar dayanağı.

**S: "Planlayıcının kuralı kandırması gerçekten oldu mu?"**
Evet ve kendi testimiz yakaladı. İlk sürüm blok başına bekleme süresini sınırlıyordu; planlayıcı iki karanlık blok arasında mekik dokuyup sayacı sıfırlayarak aynı şekilde dondu. Çözüm kuralı sıkılaştırmak değil, doğru büyüklüğü — iç sıcaklığın kendisini — kısıtlamaktı. Sıcaklık sayaç gibi sıfırlanmıyor.

**S: "Isıtıcıyı neden varsayılan olarak açmadınız?"**
Çünkü watt'tan kelvin'e kaynaklı bir bağ yok. Isıtıcıyı varsayılan yapsak, sistem sessizce daha iyimser sonuçlar verirdi ve bunun bir varsayıma dayandığı görünmezdi. Şimdi operatör bilinçli olarak `"thermostat_assumed"` seçiyor ve cevapta bunun varsayım olduğu yazıyor.

**S: "JSC makalesini gerçekten okudunuz mu?"**
Evet, ve okumak projenin kendi araştırma belgesindeki üç hatayı buldu: zarf grafiğinin eksenleri yanlış yazılmıştı, bir AFT normalizasyon örneği vaka sonucu sanılmıştı, ve "tolere edilebilir saplanma süresi" termal bir büyüklük sanılmıştı (aslında haven penceresi). Üçü de düzeltildi.

**S: "Sonuç iyi mi kötü mü?"**
Dürüst cevap: Site11'de LPR-1 için kötü. Rover ortalama yarım saat durabiliyor, safe haven yok, saplanma senaryosunda saat zaten dolmuş. Ama bunu **bilmek** iyi. Bir planlama aracının işi iyi haber üretmek değil, gerçeği ölçmek.
