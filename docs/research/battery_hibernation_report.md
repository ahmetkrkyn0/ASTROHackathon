# C2 — Batarya soğuk davranışı, hibernasyon ve karanlık dayanımı: ölçüm raporu

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Saha:** Site11, pencere (2400, 2500), 210 063 geçilebilir hücre

**Etiket: MODEL, kalibre edilmemiş.** Bu katalogdaki hiçbir rover sıcaklığa bağlı kapasite eğrisi, ısıtıcı iletkenliği, ışıma alanı, termostat set noktası ya da hibernasyon dayanımı yayımlamıyor. Aşağıdaki her katsayı ya doğrudan bir katalog alanından okundu ya da `"assumption:"` ile başlayan kendi kaynak dizesini taşıyor. NASA Glenn'in, ISRO'nun ve NASA JSC'nin sayıları **onlarındır**; alıntı olarak durur, bizim ölçümümüzle karıştırılmaz.

---

## 1. Kaynaklar ne diyor (alıntı), ve JSC'nin sayısının çapraz kontrolü

**NASA Glenn (Oeftering, Bennett vd., 2021 Space Power Workshop, NTRS 20210011101) — alıntı:**

- *"At T<200K (-70°C) electrolyte freezes"* · *"Cell voltage drops to zero"* · *"Voltage recovers when warmed above 200K"*
- Vakumda: *"4 of 4 cell trials in vacuum were successful"* (~70 mtorr, kriyosoğutucu ~100 K)
- 1 atm LN2'de: 3 of 5 recovered without problems; 2 of 5 safety device trips (1 atm, LN2); soğuk daldırma 80 K
- ISRO: 3 manufacturers of 18650 Li-ion cells, -160 °C'de 14 gün — *"Cells recovered charge capacity with no apparent damage or degradation"*
- Surveyor: *"Surveyor 1 operated fully/partially for 6 lunar cycles"*
- Diviner grafiğinde NASA'nın kendi etiketi: *"<- Li-Ion Battery Approx. Freeze Temperature"*

**NASA JSC / Jacobs (Slusser, Wilcox, Hernandez, TFAWS23-PT-52) — alıntı:**

- Yasa: `Q_rad = eps * sigma * A * (T_obj^4 - T_env^4)`
- *"the desired temperature for an object is a significant driver of the amount heater power needed as the temperature of the object is weighted to the 4th power"*
- *"Decreasing a component's survival temperature from 270K to 250K, for example, decreases heater power requirements by 26%"*
- *"One early LTV proposal aiming for a total vehicle mass of 500 kg found that >400 kg of battery mass was required to survive the night."*
- Karşı görüş (hibernasyona): *"The variety of failure types precludes the ability to simply let some electrical components fully hibernate during a night and sink to low temperatures -- once exposed to a low enough temperature, many components simply will not operate when brought up to a more reasonable environment"*

**Çapraz kontrol (bizim aritmetiğimiz, onların yasası ve onların sayısı üstünde):**

| T_env | `1 − (250⁴−T_env⁴)/(270⁴−T_env⁴)` |
|---|---|
| 0 K | %26.50 |
| 25 K | %26.50 |
| 40 K | %26.51 |
| 100 K | %27.01 |

JSC'nin yayımladığı **%26**'ya karşı bizim okumamız **%26.50**; fark **0.50** puan. Isıtıcı katsayısı bu oranda sadeleşiyor, yani bu **yasanın** kontrolüdür, bizim kalibrasyonumuzun değil. C1'in `viper_corner_check`'i ne yapıyorsa bu da onu yapıyor.

## 2. Katalog kalibrasyonu: tek katsayı, `p_heater_w`'den okunuyor

JSC'nin denklemi `εσA` üçlüsünü tek bir çarpım olarak taşıyor, ve modele giren de o tek çarpım: hiçbir yerde ε ya da A ayrı ayrı uydurulmuyor. Çarpım, ısıtıcının modelin geçilebilir saydığı en soğuk yüzeyde (-150 °C) set noktasını tam tutacak kadar büyük olduğu **varsayımından** okunuyor.

| Profil | `p_heater_w` | set noktası | `kA` (W/K) | `εσA` (W/K⁴) | ε=1'de ima edilen A |
|---|---|---|---|---|---|
| LPR-1 (Default) | 25 W | 0.0 °C (battery) | 0.166667 | 4.6845e-09 | 0.0826 m² |
| LUVMI-M | 20 W | -100.0 °C (battery) | 0.400000 | 2.9902e-08 | 0.5273 m² |
| NASA VIPER | 50 W | 0.0 °C (battery) | 0.333333 | 9.3689e-09 | 0.1652 m² |
| CNSA Yutu-2 | 20 W | -10.0 °C (battery) | 0.142857 | 4.3809e-09 | 0.0773 m² |

**Bulgu.** İma edilen alanlar çok küçük — LPR-1 için 450 kg'lık bir araçta 0.0826 m². Bu, katalogdaki `p_heater_w`'nin bir **gece-hayatta-kalma** ısıtıcısı değil bir **idame** ısıtıcısı olduğunu söylüyor ve JSC'nin 500 kg'lık araç için ">400 kg batarya" bulgusuyla aynı yöne işaret ediyor. Katalog değiştirilmedi; bulgu yazıldı.

### İki yasanın gerçek yüzey sıcaklıklarındaki farkı (W)

| Yüzey | LPR-1 `delta_t` | LPR-1 `radiative` | VIPER `delta_t` | VIPER `radiative` | Yutu-2 `delta_t` | Yutu-2 `radiative` |
|---|---|---|---|---|---|---|
| -150 °C | 25.00 | 25.00 | 50.00 | 50.00 | 20.00 | 20.00 |
| -130 °C | 21.67 | 24.11 | 43.33 | 48.22 | 17.14 | 19.17 |
| -110 °C | 18.33 | 22.76 | 36.67 | 45.52 | 14.29 | 17.90 |
| -90 °C | 15.00 | 20.81 | 30.00 | 41.61 | 11.43 | 16.08 |
| -70 °C | 11.67 | 18.10 | 23.33 | 36.20 | 8.57 | 13.55 |
| -50 °C | 8.33 | 14.46 | 16.67 | 28.92 | 5.71 | 10.14 |
| -30 °C | 5.00 | 9.70 | 10.00 | 19.41 | 2.86 | 5.69 |
| -10 °C | 1.67 | 3.61 | 3.33 | 7.23 | 0.00 | 0.00 |
| 0 °C | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

İkisi boyutlandırma noktasında **tam olarak** eşit (varsayım öyle kuruyor); başka her yerde dördüncü kuvvet doğrusal formun üstünde kalıyor. Araştırma belgesi doğrusal formu istedi; belgenin kendi gösterdiği kaynak T⁴'ü yazıyor. İkisi de sunuluyor.

## 3. "Karanlık = soğuk" Site11'de doğru mu? Hayır.

Bugünkü ısıtıcı terimi gölge oranıyla ölçekleniyor, yani karanlığın soğukluğun vekili olduğunu varsayıyor. Gönderilen pencerede ölçüldü:

| Büyüklük | min | medyan | maks |
|---|---|---|---|
| yüzey sıcaklığı (sunlit_peak) | -146.37 °C | -47.22 °C | 28.17 °C |
| gölge oranı | 0.1012 | 0.5952 | 0.9762 |

**Spearman(gölge oranı, yüzey sıcaklığı) = -0.0014.**

Yani bu alanda gölge oranı, yüzey sıcaklığı hakkında **hiçbir şey** söylemiyor — yaklaşık olarak değil, sıfır. Aydınlık ama soğuk cepler var:

| Gölge oranı < | Yüzey < | hücre | oran |
|---|---|---|---|
| 0.2 | -100 °C | 103 | %0.05 |
| 0.3 | -80 °C | 273 | %0.13 |
| 0.5 | -50 °C | 4 922 | %2.34 |

> **Uyarı, çünkü bu istatistik meselesidir:** buradaki yüzey alanı uzun vadeli `sunlit_peak` istatistiğidir. 4-B hattının okuduğu dilim başına seri farklı bir alandır ve korelasyonu farklı olabilir. Ölçüm burada yazılı olan alanındır.

## 4. Üç ısıtıcı modelinin işaretli farkı (tüm geçilebilir hücreler)

İlk taslak "yeni model her zaman ≤ eski model" diye bir sınır iddia ediyordu. Ölçüm çürüttü ve iddia **geri çekildi**: iki model sıralanabilir değil, biri maruz kalmayı öbürü sıcaklığı okuyor.

| Profil | Model | yeni > eski | oran | en büyük fazla | en büyük eksik | ortalama |
|---|---|---|---|---|---|---|
| lpr_1 | `delta_t` | 29 173 | %13.89 | 21.87 W | -24.40 W | -6.943 W |
| lpr_1 | `radiative` | 92 771 | %44.16 | 22.34 W | -24.40 W | -2.320 W |
| nasa_viper | `delta_t` | 29 173 | %13.89 | 43.73 W | -48.81 W | -13.885 W |
| nasa_viper | `radiative` | 92 771 | %44.16 | 44.68 W | -48.81 W | -4.640 W |
| cnsa_yutu_2 | `delta_t` | 23 126 | %11.01 | 17.46 W | -19.52 W | -6.344 W |
| cnsa_yutu_2 | `radiative` | 76 883 | %36.60 | 17.85 W | -19.52 W | -3.102 W |

Başarısızlık sınıfı **soğuk ama aydınlık** hücrelerdir: bugünkü terim orada ısıtıcıyı hiç çalıştırmıyor, sıcaklık tabanlı terim çalıştırıyor.

## 5. Teslim edilebilir kapasite eğrisi ve kaynaksız şeklinin süpürülmesi

Soğuk uç -73.15 °C (200 K, NASA Glenn'den **alıntı**, bir rover bataryasına taşınması etiketli varsayım). Sıcak uç profilin kendi beyan ettiği `bat_op_min_c`'si — LPR-1 ve VIPER'da **tam olarak 0 °C**, yani NASA'nın 5 420 Wh'ı verdiği sıcaklıkla çakışıyor. Aradaki **şeklin hiçbir kaynağı yok**; varsayılan doğrusal ve aşağıda süpürülüyor, ayarlanmıyor.

| Üs | f(−10 °C) | f(−20 °C) | f(−40 °C) | dayanım(−20 °C) | dayanım(−40 °C) |
|---|---|---|---|---|---|
| 0.50 | 0.9291 | 0.8524 | 0.6732 | 40.78 s | 29.57 s |
| 0.75 | 0.8956 | 0.7870 | 0.5523 | 36.69 s | 22.02 s |
| 1.00 | 0.8633 | 0.7266 | 0.4532 | 32.91 s | 15.82 s |
| 1.50 | 0.8021 | 0.6193 | 0.3051 | 26.21 s | 6.57 s |
| 2.00 | 0.7453 | 0.5279 | 0.2054 | 20.50 s | 0.34 s |
| 3.00 | 0.6434 | 0.3836 | 0.0931 | 11.47 s | 0.00 s |

**Araştırma belgesinin "0 °C'de ~%85" tahmini kullanılmadı.** Kaynağı yok, ve `e_cap_wh` zaten 0 °C'de verilmiş bir kapasite olduğu için 0 °C'de %85 demek aynı iskontoyu ikinci kez uygulamak olurdu.

> **Sınır:** yayımlanmış COTS 18650 deşarj eğrileri düz değil dışbükeydir, yani doğrusal varsayım karamsar olmaktan çok **iyimser** olabilir. Bu bir yön beyanıdır, ölçülmüş bir sayı değil; ölçmediğimiz için tablo üssü süpürüyor.

## 6. Dayanım: katalogun kendi tutarsızlığı

| Profil | kapasite | rezerv | tam-gölge W | **ima edilen** dayanım | **yayımlanan** `h_max_shadow_h` |
|---|---|---|---|---|---|
| LPR-1 (Default) | 5 420 Wh | 1 084 Wh | 65 W | 66.71 s | **50.0 s** |
| LUVMI-M | 1 400 Wh | 280 Wh | 50 W | 22.40 s | **4.0 s** |
| NASA VIPER | 5 420 Wh | 1 084 Wh | 130 W | 33.35 s | **50.0 s** |
| CNSA Yutu-2 | 1 500 Wh | 450 Wh | 60 W | 17.50 s | **2.0 s** |

**NASA VIPER'ın kataloğu kendi içinde tutarsız:** 50 s × 130 W = 6 500 Wh, 5 420 Wh'lik paketi rezervsiz bile aşıyor. Açıklama, NASA'nın 50 saatinin **min-power modunda** olması (Shirley & Balaban: gölgede matkapla 9.5 s, min-power modda 50 s), `p_shadow_w`'nin ise normal gölge çekişi olması: iki farklı mod, iki farklı sayı.

Bu yüzden dinamik dayanım `min(yayımlanan, ima edilen)` **değildir**. O biçim VIPER'ın dayanımını bayrak açılır açılmaz %33 kısar ve "tam şarjda yayımlanan sabiti verir" iddiasını yanlışlardı. Model **oransal**: yayımlanan dayanımı, bu durumun rezervin üstünde hâlâ teslim edebildiği kesirle ölçekler — dört profilde de tam şarj + rating sıcaklığında **tam olarak** yayımlanan sabiti verir. Tutarsızlık düzeltilmedi, **ölçüm olarak** buraya yazıldı.

## 7. Hibernasyon

| Profil | `p_hibernate_w` | `p_shadow_w` | oran (karanlık saati hızı) | uygulanabilir mi |
|---|---|---|---|---|
| LPR-1 (Default) | 108 W | 65 W | 1.6615 | evet |
| LUVMI-M | - | 50 W | - | hayır — `p_hibernate_w` beyan edilmemiş |
| NASA VIPER | 100 W | 130 W | 0.7692 | evet |
| CNSA Yutu-2 | 5 W | 60 W | 0.0833 | evet |

**LPR-1'in "hibernasyonu" ısıtıcılarını çalıştırmaktan pahalı** (108 W'a karşı 65 W). Bu bir veri hatası değil, tanım farkı: proje referans belgesi modu "idle + heater + termal yönetim" diye tanımlıyor, yani bu bir **idame** modu. NASA Glenn'in *pasif* hibernasyonunda yükler kapanır ve batarya izole edilir; çekiş neredeyse sıfırdır. Model katalogdaki modu uygular ve farkı söyler; katalog düzeltilmedi.

| Profil | karanlıkta bekleme (birim maliyet) | karanlıkta hibernasyon | hibernasyon daha ucuz mu |
|---|---|---|---|
| lpr_1 | 1.145106 | 1.147161 | hayır |
| nasa_viper | 1.205996 | 1.204613 | evet |
| cnsa_yutu_2 | 1.212000 | 1.201000 | evet |

İki profilde hibernasyon beklemeden **ucuz**. Kapısız bir kenar bu yüzden planlayıcıyı güneşin altında şekerleme yapmaya iterdi; kenar bu nedenle **karanlıkta başlar ve aydınlıkta biter** — ikincisi NASA'nın kendi mimarisi (*"Solar Array output triggers a 'Dawn Mode'"*), bizim icadımız değil.

**Alıntılanan kanıtın menzili:** en soğuk -193.1 °C (80 K), en uzun 336 s (14 gün). Bundan daha soğuk ya da daha uzun bir hibernasyon planlanır ama yanıt `beyond_cited_evidence` ile bunun kanıtın dışına çıktığını söyler.

### Üç standart 4-B rota, her anahtar altında

**LPR-1, gunduz (28 Eyl 2026)**

| Anahtar | durum | hamle | bekleme | hibernasyon | düğüm | maliyet | en düşük SOC | sürekli karanlık | duvar saati (sn) |
|---|---|---|---|---|---|---|---|---|---|
| `default` | 200 | 41 | 0 | 0 | 31 219 | 3.4454 | %92.5 | 0.517 s | 16.3 |
| `radiative` | 200 | 41 | 0 | 0 | 31 847 | 3.4512 | %92.2 | 0.517 s | 11.3 |
| `delta_t` | 200 | 41 | 0 | 0 | 36 608 | 3.4475 | %92.4 | 0.517 s | 11.6 |
| `derated` | 200 | 41 | 0 | 0 | 49 149 | 3.4454 | %92.5 | 0.517 s | 14.5 |
| `hibernate` | 200 | 41 | 0 | 0 | 49 216 | 3.4454 | %92.5 | 0.517 s | 13.1 |
| `all_on` | 200 | 41 | 0 | 0 | 36 891 | 3.4512 | %92.2 | 0.517 s | 13.7 |


**LPR-1, Ay gecesi (13 Eyl 2026)**

| Anahtar | durum | hamle | bekleme | hibernasyon | düğüm | maliyet | en düşük SOC | sürekli karanlık | duvar saati (sn) |
|---|---|---|---|---|---|---|---|---|---|
| `default` | 200 | 116 | 0 | 0 | 171 117 | 7.8371 | %67.4 | 4.802 s | 34.8 |
| `radiative` | 200 | 116 | 0 | 0 | 171 145 | 7.8368 | %67.4 | 4.802 s | 33.2 |
| `delta_t` | 200 | 116 | 0 | 0 | 171 228 | 7.8362 | %67.5 | 4.802 s | 31.8 |
| `derated` | **404** | — | — | — | — | — | — | — | 16.0 |
| `hibernate` | 200 | 116 | 0 | 0 | 172 528 | 7.8371 | %67.4 | 4.802 s | 35.3 |
| `all_on` | 200 | 116 | 0 | 0 | 171 145 | 7.8368 | %67.4 | 4.802 s | 41.5 |

- `derated` reddi: No path found for LPR-1 (Default): 11757 edges would have drained the battery below the 20 percent reserve; 29027 edges would have kept the rover in continuous shadow beyond what its charge and battery temperature could still sustain (the published 50 h endurance scaled by the deliverable charge above the reserve; battery_model='temperature_derated'); 536 edges exceeded the 18 deg roll-over (cross

**NASA VIPER, kisa leg (30 May 2027)**

| Anahtar | durum | hamle | bekleme | hibernasyon | düğüm | maliyet | en düşük SOC | sürekli karanlık | duvar saati (sn) |
|---|---|---|---|---|---|---|---|---|---|
| `default` | **422** | — | — | — | — | — | — | — | 0.1 |
| `radiative` | **422** | — | — | — | — | — | — | — | 0.1 |
| `delta_t` | **422** | — | — | — | — | — | — | — | 0.1 |
| `derated` | **422** | — | — | — | — | — | — | — | 0.1 |
| `hibernate` | **422** | — | — | — | — | — | — | — | 0.2 |
| `all_on` | **422** | — | — | — | — | — | — | — | 0.1 |

- `default` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.
- `radiative` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.
- `delta_t` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.
- `derated` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.
- `hibernate` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.
- `all_on` reddi: start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.

## 8. İddia sınırı

- **NASA Glenn'in, ISRO'nun, Surveyor'un ve NASA JSC'nin sayıları onlarındır.** Hiçbiri bizim ölçüm tablomuza konmadı ve hiçbiri için "biz doğruladık" denmedi. Tek istisna § 1'deki çapraz kontroldür ve o da **onların yasasının** bizim okumamızla tutarlılığını gösterir, yeni bir ölçüm değildir.
- **200 K bir HÜCRE ölçümüdür.** 18650 hücrelerinde ölçüldü; bu katalogdaki hiçbir profil hücre formatını, kimyasını ya da donma noktasını yayımlamıyor. Bir rover bataryasına taşınması C3'ün taşınmış kayma çapalarındaki gibi etiketli varsayımdır.
- **Eğrinin şekli kaynaksızdır** ve ayarlanmadı; § 5 süpürüyor.
- **`k` ve `A` ayrı ayrı türetilmedi.** Yalnızca `εσA` çarpımı, yalnızca `p_heater_w`'den, yalnızca etiketli bir boyutlandırma varsayımıyla.
- **`p_hibernate_w` kaynaksızdır.** C2 onu ilk kez okunan bir girdi hâline getirdiği için ev kuralı gereği kendi `"assumption:"` dizesini kazandı.
- **LUVMI-M için üç modelin hiçbiri uygulanmıyor** ve nedeni her yanıtta yazılı: beyan ettiği batarya alt sınırı (−100 °C) alıntılanan donma noktasının altında, ve `p_hibernate_w` ile `thermal_tau_s` beyan etmiyor. Değer uydurulmadı.
- **İki kaynak birbiriyle çelişiyor.** NASA Glenn hibernasyonu savunur (kanıtı **hücrelere** dair), NASA JSC uyarır (uyarısı **aviyoniğe** dair). Model hibernasyonda hangi bileşenin sınırının aşıldığını adlandırır; çelişki gizlenmedi.
- **Modellenmeyenler:** şarj tarafı soğuk kısıtı, iç direnç, yaşlanma, çevrim ömrü, hücre dengeleme, gerçek bir gövde termal modeli. Yoklukları burada yazılı.
- **SHERPA marjları** (`safe_haven.route_margins`) nominal şarj ve sabit idame gücü üzerinden hesaplanır, yani derate açıkken planlayıcının kendi sayıları değildir. Yanıttaki `battery.route.margins_use_nameplate_charge` bunu söyler.

**Sunum cümlesi.** "Bataryanın soğukta ne kadarını verebildiğini, ısıtıcının kaç watt çektiğini ve rover'ın gece boyunca uyuyup şafakta uyanmasını modelliyoruz — ısıtıcı yasası NASA JSC'nin kendi Stefan-Boltzmann denklemi, hibernasyon mimarisi NASA Glenn'in 'dawn mode'u, donma eşiği onların 200 K ölçümü. Bizim olan: katalogdan okunan tek katsayı, planlayıcıdaki eylem, ve hepsinin nerede biteceğini söyleyen sınır."

---

*Ölçüm süresi: 4.6 dakika. Üretici betik: [`scripts/battery_hibernation_report.py`](../../scripts/battery_hibernation_report.py) (`--json` ham çıktı, `--from-json` ölçmeden yeniden render).*
