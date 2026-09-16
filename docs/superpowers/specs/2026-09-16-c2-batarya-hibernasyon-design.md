# C2 — Batarya soğuk davranışı, hibernasyon ve "karanlık dayanımı" fiziği — Tasarım Belgesi

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § C2](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** C1 (panel kazancı, `solar_gain` deseni ve bit-eşitlik kilidi), C6
(`thermal_dwell` iç sıcaklığı ve zarfı), B1 (`survival` DP'si), B5 (`stress_test`), A1
(`safe_haven`), D3 (`safety_monitor` LP-R gereksinimleri) — hepsi tamamlandı.

**Yol:** yeni çekirdek modül `battery.py`; mevcut enerji fonksiyonlarına tek bir isteğe bağlı
ısıtıcı-gücü parametresi; 4-B planlayıcıya üçüncü bir kenar ailesi (`HIBERNATE`) ve durum
bağımlı dayanım; üç istek bayrağı, her yanıtta `battery` bloğu, bir yeni uç, bir rapor betiği.

**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna
dokunulmaz; `docs/frontend/3b-veri-sozlesmesi.md`'ye "C2 eki" yazılır (yalnızca ekleme).

---

## Amaç

Araştırma belgesi § C2 dört şey istiyor ve LunaPath'te dördü de yok:

| # | İstenen | Bugün |
|---|---|---|
| 1 | `battery_usable_fraction(T_inner)` | batarya sabit kapasite; `e_cap_wh` sıcaklıktan bağımsız |
| 2 | `heater_power = k·A·(T_survive − T_env)` | ısıtıcı sabit güç: `p_idle_w + gölge_oranı × (p_shadow_w − p_idle_w)` |
| 3 | 4-B planlayıcıda `HIBERNATE` eylemi | yok; `p_hibernate_w` katalogda duruyor, **hiçbir şey okumuyor** |
| 4 | `h_max_shadow_h` SOC ve sıcaklığın fonksiyonu | tek sabit eşik, on modülde okunuyor |

Dördünün ortak noktası şu: LunaPath'in enerji modeli **maruz kalmayı** (gölge oranı) biliyor,
**sıcaklığı** bilmiyor. Isıtıcı yükü gölge oranıyla ölçekleniyor — yani "karanlık = soğuk"
varsayımıyla. Site11'de bu varsayım yanlış: gölge oranı ve yüzey sıcaklığı ayrı katmanlar ve
**aydınlık ama soğuk** hücreler var (ölçüm: § Sondalar, sonda 3).

C2 bu dördünü, sıcaklığı zaten hesaplayan C6'nın üstüne kurar ve `p_hibernate_w` ile
`thermal_tau_s`'yi ilk kez gerçekten okur.

---

## İddia sınırı (her blokta, raporun her bölümünde)

Bu özellikte alıntı ile model arasındaki sınır, on üç özelliğin en incesi. Tek tek:

1. **NASA Glenn'in sayıları ONLARIN.** 200 K donma eşiği, gerilimin sıfıra düşmesi, vakumda
   4/4, LN2'de 3/5, ISRO'nun −160 °C / 14 günü, Surveyor 1'in altı Ay döngüsü — hepsi
   **alıntı**. Bizim ölçüm tablomuza konmaz, "biz doğruladık" denmez. `NASA_GLENN_QUOTED` ve
   `JSC_QUOTED` sözlüklerinde, kaynak künyesiyle birlikte, ayrı durur.
2. **200 K bir HÜCRE ölçümüdür, bir rover bataryası değil.** NASA Glenn 18650 hücrelerini
   ölçtü; ISRO üç üreticinin 18650'lerini. Katalogdaki hiçbir profil kendi hücre kimyasını
   yayımlamıyor. Eşiğin bir rover profiline taşınması C3'ün `_transferred` kayma
   çapalarındaki gibi **açık bir varsayımdır** ve `"assumption:"` ile başlayan kendi kaynak
   dizesini taşır.
3. **Kullanılabilir kesrin ŞEKLİ kaynaklı değildir.** İki uç noktası var: rating sıcaklığında
   1,0 (profilin kendi `bat_op_min_c`'si; VIPER'da NASA'nın "5 420 Wh at 0 C"i ile aynı sayı)
   ve donma noktasında 0,0. Aradaki eğri **VARSAYIM**: varsayılan doğrusal, üssü raporda
   0,5–2,0 arasında süpürülüyor. Belgedeki "0 °C'de ~%85, −20 °C'de ~%60" **kullanılmıyor**:
   kaynağı yok ve 0 °C'de %85 demek, zaten 0 °C'de ölçülmüş bir kapasiteyi ikinci kez
   iskonto etmektir (§ Tasarım kararları, K1).
4. **`k` ve `A` katalogda yok ve UYDURULMUYOR.** Ayrı ayrı da türetilmiyor: JSC'nin kendi
   denklemi `Q_rad = εσA(T_obj⁴ − T_env⁴)` üçlüyü tek bir çarpım olarak taşıyor ve modele
   giren de o tek çarpım. `εσA` katalogdaki `p_heater_w`'den, **etiketli bir boyutlandırma
   varsayımıyla** (ısıtıcı, modelin geçilebilir saydığı en soğuk yüzeyde set noktasını tam
   tutacak kadar büyük) okunuyor. Kaynak dizesi `"assumption:"` ile başlıyor ve C6'nın
   `HEATER_THERMOSTAT_ASSUMPTION_SOURCE`'u aynı commit'te bu katsayıyı anacak biçimde
   düzeltiliyor — çünkü o dize bugün "W-to-K katsayısı yok" diyor ve C2 onu yanlışlıyor.
5. **`p_hibernate_w`'nin kendisi kaynaksız.** Katalogdaki dört değerin hiçbiri yayımlanmış bir
   araç özelliği değil; LPR-1'in 108 W'ı proje referans belgesinden geliyor
   (`docs/archive/lunapath_referans_belgesi_2.md:66`, "hibernate mod: idle + heater + termal
   yönetim"). C2 bu alanı ilk kez **okunan bir girdi** hâline getirdiği için, ev kuralı
   gereği okunmadan önce `"assumption:"` kaynak dizesini kazanıyor.
6. **Modelin etiketi MODEL.** Hiçbir rover kutup gecesinde batarya kapasite eğrisi, ısıtıcı
   iletkenliği ya da hibernasyon dayanımı yayımlamıyor. Verim, yaşlanma, iç direnç, şarj
   tarafı soğuk kısıtı, hücre dengeleme ve gerçek bir gövde termal modeli **yok** ve
   yokluğu her blokta yazılıyor.
7. **"Operating" ile "survival" ayrı iki sınırdır ve karıştırılmaz.** `bat_op_min_c` bir
   **çalışma** alt sınırı; 200 K bir **hayatta kalma** eşiği. Hibernasyon tam da ikisinin
   arasında yaşıyor. Model bu ikisini ayrı tutar (§ Tasarım kararları, K6) ve `T_survive`
   gibi ikisini birden ima eden bir ad kullanmaz.
8. **İki kaynak birbiriyle çelişiyor ve çelişki gizlenmiyor.** NASA Glenn (düşük maliyetli
   robotik) hibernasyonu savunur; NASA JSC/Jacobs (mürettebatlı LTV) *"fully turning off the
   vehicle in a cold environment would certainly jeopardize its ability to return to
   operation in the future"* der. Birincisinin kanıtı **hücrelere**, ikincisinin uyarısı
   **aviyoniğe** dair. Model hibernasyonda hangi bileşenin sınırının aşıldığını adlandırır
   (`thermal_dwell.Envelope` zaten `lo_component` taşıyor) ve raporda ikisi yan yana durur.
9. **Alıntılanan kanıtın bir menzili var.** NASA Glenn 80–100 K'ya soğuttu, ISRO 14 gün
   tuttu. Bundan daha soğuk ya da daha uzun bir hibernasyon **alıntılanan kanıtın dışına**
   çıkar; rota bunu `beyond_cited_evidence` bayrağıyla söyler.

---

## Kaynak notu (16 Eylül 2026'da PDF'ler indirilip metni çıkarıldı)

Üç birincil kaynağın tamamı okundu (`PyMuPDF` ile metin çıkarımı; sayfa numaraları PDF
sayfalarıdır).

### 1. Oeftering, Bennett, Vankeuls, Uguccini — *Battery Hibernation for Surviving the Lunar Night*
NASA Glenn Research Center, 2021 Space Power Workshop, 19 Nisan 2021. NTRS 20210011101, 16 sayfa.

| Sayfa | Alıntı (birebir) |
|---|---|
| 7 | "At T<200K (-70°C) electrolyte freezes" · "Cell voltage drops to zero" · "Cold soak to 80K (-193°C) overnight" · "All cells recovered above 200K" · "2 of 5 cells recovered but safety device tripped" · "3 of 5 recovered without problems" (LN2, 1 atm) |
| 9 | "Vacuum chamber pressure at ~70 mtorr" · "Cryocooler chilled and held near 100K" · "Voltage dropped below 200K" · "Voltage recovers when warmed above 200K" · **"4 of 4 cell trials in vacuum were successful"** |
| 6 | "2018 ISRO investigated 18650 Li-ion cell passive lunar night survivability." · "Evaluated 3 manufacturers of 18650 Li-ion cells." · "Subjected them to 14 day lunar night at -160°C (in vacuum)" · "Cells recovered charge capacity with no apparent damage or degradation" |
| 3 | "Surveyor 1 operated fully/partially for 6 lunar cycles" · "Surveyor was not designed for Night Survival" |
| 10 | **Dawn mode:** "Lunar Dusk: Point Arrays toward Dawn, Shut-Down Loads, Isolate Battery, Wait for Dawn" · "Lunar Dawn: (first illumination, coldest temperature)" · "Solar Array output triggers a 'Dawn Mode' within the Main Bus Controller (MBC)" · **"MBC in Dawn Mode operates on Solar Array power alone (Battery still Isolated)"** · "MBC manages thermal conditioning (Pre-Heaters) for battery and avionics" · "On reaching safe temperatures BMS performs battery pre-charge." |
| 5 | "Night temperatures fall within a 50-100K range regardless of latitude." |
| 15 | ISRO'nun birincil kaynağı: Nandini, Usha, Srinivasan, Pramod, Satyanarayana, Sankaran, "Study on survivability of 18650 Lithium-ion cells at cryogenic temperatures", *J. of Energy Storage* 17 (2018) 409-416 |

### 2. Oeftering — *Lunar Power Hibernation for Surviving the Lunar Night*
NASA Glenn, Lunar Extreme Environments Forum, 28 Temmuz 2021. NTRS 20210019184, 26 sayfa.

| Sayfa | Alıntı (birebir) |
|---|---|
| 4 | Diviner grafiğinde işaretli: **"<- Li-Ion Battery Approx. Freeze Temperature"** — 200 K'yı NASA'nın kendisi "batarya donma sıcaklığı" diye adlandırıyor |
| 8 | **"Voltage dropped to zero below 200K"** · "4 of 4 cell trials in vacuum were successful" |
| 9 | "Lowest Temperatures occur just before Lunar Dawn" · **"Polar Regions subject to multiple short (Dusk-Dawn) cycles"** · "Batteries Passively Survive the cold without loss of capability" · "Batteries must be isolated from main bus prior to Dawn" · "Pre-Heating and Pre-Charging are required while isolated" |
| 10 | "Photovoltaic Arrays are tolerant of cryogenic temperatures." · "Solar Arrays expected to Survive and Generate Power at Lunar Dawn." |
| 5 | "Polar Day Time high temps still below battery operating temperatures" |
| 12 | "MBC in Dawn Mode operates on Solar Array power alone (Battery still Isolated)" · "At normal temperature BMS pre-charges battery to match main bus voltage" |

### 3. Slusser, Wilcox (Jacobs Technology Inc.), Hernandez (NASA JSC) — *Surviving Night at the Lunar South Pole: Exploring Viability of Radioisotope Power Systems for a Crewed Rover*
TFAWS 2023, 21–25 Ağustos 2023, TFAWS23-PT-52, 17 sayfa.
**C6'nın kaynağı DEĞİL** — C6 aynı ilk yazarın ICES-2025-376'sını kullanıyor; farklı bildiri,
farklı ortak yazarlar, farklı araç (LTV vs VIPER). Karıştırılmadı.

| Sayfa | Alıntı (birebir) |
|---|---|
| 3 | **`Q_rad = εσA(T_obj⁴ − T_env⁴)`** — "the Stefan-Boltzmann law, which is used to calculate the amount of radiative heat transfer" |
| 3 | "the desired temperature for an object is a significant driver of the amount heater power needed as the temperature of the object is weighted to the 4th power" |
| 3 | **"Decreasing a component's survival temperature from 270K to 250K, for example, decreases heater power requirements by 26%"** — § Sondalar, sonda 1'de yeniden üretiliyor |
| 3 | "One early LTV proposal aiming for a total vehicle mass of 500 kg found that >400 kg of battery mass was required to survive the night." |
| 3 | "another significant driver for heater power is the surface area exposed to cold environments" |
| 2 | "A select amount of landing sites have been identified at the lunar south pole where the maximum length of lunar night local to the site does not exceed 125 hours ... It is this length of time – 125 hours – that engineers are currently using in the process of sizing a lunar terrain vehicle" |
| 2 | "temperatures at the lunar south pole can dip as low as 25K in permanently shadowed regions" |
| 2–3 | **Karşı görüş:** "The variety of failure types precludes the ability to simply let some electrical components fully hibernate during a night and sink to low temperatures – once exposed to a low enough temperature, many components simply will not operate when brought up to a more reasonable environment." · "fully turning off the vehicle in a cold environment would certainly jeopardize its ability to return to operation in the future." |

### Kaynak notunun tasarıma üç doğrudan etkisi

- **Isıtıcı yasası doğrusal değil, T⁴.** Araştırma belgesi `k·A·(T_survive − T_env)` istiyor;
  belgenin kendi gösterdiği kaynak ise Stefan-Boltzmann'ı açıkça yazıyor. Doğrusal biçim
  bunun boyutlandırma noktasındaki birinci mertebe açılımıdır. **İkisi de sunuluyor**
  (`heater_power_model="radiative" | "delta_t"`), farkları raporda ölçülüyor.
- **Dawn pre-heat'in enerjisi BATARYADAN gelmiyor.** "MBC in Dawn Mode operates on Solar
  Array power alone (Battery still Isolated)". Yani uyanma bedeli **zaman** ve **güneş
  geliri**, batarya değil. Bu, tasarımın ilk taslağını (batarya ile ön-ısıtma) doğrudan
  çürüttü.
- **Uyanmak AYDINLIK gerektirir.** "Solar Array output triggers a 'Dawn Mode'". Bu, NASA'nın
  mimarisi — bizim icadımız değil — ve planlayıcıda hibernasyonun en tehlikeli açığını
  (karanlıkta hibernasyona girip karanlıkta çıkarak dayanım kısıtını sonsuza kadar
  sıfırlamak) kaynaklı bir kuralla kapatıyor.

---

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Ne | Nerede | C2 nasıl kullanıyor |
|---|---|---|
| İç sıcaklık = birinci mertebe gecikme | `thermal_dwell.DwellCube.inner_after:386` | hibernasyonda ve derate'te iç sıcaklık kaynağı |
| En dar zarf ve sahibi | `thermal_dwell.rover_envelope:211` (`lo_component`) | çalışma/hayatta kalma ayrımı, hangi bileşenin sınırının aşıldığı |
| Kapalı formlu çıkış süresi | `thermal_dwell.exit_time_h:261` | dawn pre-heat süresi aynı denklemin ısınma dalı |
| Dilim başına yüzey sıcaklığı | `cost_cube.surface_temperature_series:80` | ısıtıcı gücünün gördüğü ortam sıcaklığı |
| Isıtıcı varsayımı ve kaynak dizesi | `constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE:229` | genişletiliyor (W-to-K katsayısını anacak) |
| `solar_gain` deseni ve bit-eşitlik kilidi | C1, `panel.py` + altı imza | üç yeni bayrağın tamamı aynı desende |
| Etiket ekseninin kapatılabilirliği | `pathfinder_4d` `margin_tol=inf` + sabit anahtar | yeni eksen yok, ama aynı desen korunuyor |
| Ölçekli eşik kalıbı | `constants.soc_deviation_threshold:576` | dinamik dayanımın oran biçimi |

---

## Sondalar (16 Eylül 2026, gerçek katalog + gerçek Site11 gridi)

Aşağıdaki sayıların hepsi koşturuldu. Koşmadan hiçbiri yazılmadı.

### Sonda 1 — JSC'nin %26'sı yeniden üretiliyor (çapraz kontrol)

JSC: *"Decreasing a component's survival temperature from 270K to 250K ... decreases heater
power requirements by 26%"*. `Q = εσA(T⁴ − T_env⁴)` ile:

| T_env | `1 − (250⁴−T_env⁴)/(270⁴−T_env⁴)` |
|---|---|
| 0 K | **%26,50** |
| 25 K (JSC'nin PSR tabanı) | %26,50 |
| 40 K | %26,51 |
| 100 K | %27,01 |

JSC'nin yayımladığı **%26**'ya karşı **%26,50**; fark +0,50 puan ve JSC'nin yuvarlamasıyla
uyumlu. C1'in `viper_corner_check`'i ne yapıyorsa bu da onu yapıyor: yayımlanmış bir sayıyı
bizim denklemimizle yeniden üretip farkı yazıyor. **Bu bizim ölçümümüz değil, onların
sayısının bizim modelimizle tutarlılığının kontrolü.**

### Sonda 2 — `εσA` ve `kA` kalibrasyonu (yüzey sıcaklığından, boyutlandırma −150 °C)

Set noktası zarfın alt sınırı, boyutlandırma yüzeyi `THERMAL_MIN_TRAVERSABLE_C = −150 °C`:

| Profil | `p_heater_w` | set noktası | ΔT (K) | `kA` (W/K) | `εσA` (W/K⁴) | ε=1'de ima edilen `A` |
|---|---|---|---|---|---|---|
| lpr_1 | 25 | 0,0 °C (batarya) | 150,0 | 0,166667 | 4,6845e-09 | 0,0826 m² |
| luvmi_m | 20 | −100,0 °C (batarya) | 50,0 | 0,400000 | 2,9902e-08 | 0,5273 m² |
| nasa_viper | 50 | 0,0 °C (batarya) | 150,0 | 0,333333 | 9,3689e-09 | 0,1652 m² |
| cnsa_yutu_2 | 20 | −10,0 °C (batarya) | 140,0 | 0,142857 | 4,3809e-09 | 0,0773 m² |

İma edilen alanlar çok küçük (LPR-1 için 0,083 m², 450 kg'lık bir araç için). Bu, katalogdaki
`p_heater_w`'nin bir **gece-hayatta-kalma** ısıtıcısı değil, bir **idame** ısıtıcısı olduğunu
söylüyor — ve JSC'nin 500 kg'lık araç için ">400 kg batarya" bulgusuyla aynı yöne işaret
ediyor. Raporda yazılıyor; katalog değiştirilmiyor.

### Sonda 3 — "karanlık = soğuk" varsayımı Site11'de yanlış (ölçüldü)

Gönderilen `lunapath/data/processed` penceresinde (Site11, pencere (2400, 2500), 500×500,
`thermal_field = "sunlit_peak"`, `thermal_shadow_coupled = true`), **210 063** geçilebilir
hücre üzerinde:

| Büyüklük | min | medyan | maks |
|---|---|---|---|
| yüzey sıcaklığı | −146,37 °C | −47,22 °C | 28,17 °C |
| gölge oranı | 0,1012 | 0,5952 | 0,9762 |

**Spearman(gölge oranı, yüzey sıcaklığı) = −0,0014.**

Yani bu alanda gölge oranı, yüzey sıcaklığı hakkında **hiçbir şey söylemiyor** — yaklaşık
değil, sıfır. (Dikkat: buradaki yüzey alanı uzun vadeli `sunlit_peak` istatistiğidir; 4-B
hattının okuduğu dilim başına seride korelasyon farklıdır ve rapor ikisini ayrı ölçer.)
Aydınlık ama soğuk hücreler var: gölge < 0,5 **ve** yüzey < −50 °C olan **4 922** hücre
(%2,34), gölge < 0,2 ve yüzey < −100 °C olan 103 hücre (%0,05).

Bugünkü ısıtıcı terimi `gölge_oranı × p_heater_w` bu hücrelerde neredeyse hiç güç çekmiyor.
C2'nin sıcaklık tabanlı ısıtıcısı çekiyor. Ölçülen işaretli fark (LPR-1, tüm geçilebilir
hücreler):

| Model | yeni > eski | yeni < eski | en büyük fazla | en büyük eksik | ortalama |
|---|---|---|---|---|---|
| `delta_t` | 29 173 (%13,89) | 180 890 (%86,11) | +21,87 W | −24,40 W | −6,943 W |
| `radiative` | 92 771 (%44,16) | 117 292 (%55,84) | +22,34 W | −24,40 W | −2,320 W |

İlk taslağın "yeni model her zaman ≤ eski model" iddiası bu yüzden **geri çekildi** (K4): iki
model sıralanabilir değil — biri maruz kalmayı, öbürü sıcaklığı okuyor.

### Sonda 4 — dayanımın katalogla tutarsızlığı

Tam şarjda, `(e_cap − rezerv) / tam-gölge idame gücü`:

| Profil | kullanılabilir Wh | tam-gölge W | türetilen s | yayımlanan `h_max_shadow_h` |
|---|---|---|---|---|
| lpr_1 | 4 336 | 65 | 66,71 | 50 |
| luvmi_m | 1 120 | 50 | 22,40 | 4 |
| nasa_viper | 4 336 | 130 | **33,35** | **50** |
| cnsa_yutu_2 | 1 050 | 60 | 17,50 | 2 |

**NASA VIPER'ın kataloğu kendi içinde tutarsız:** 50 s × 130 W = 6 500 Wh, 5 420 Wh'lik
kapasitesini rezervsiz bile aşıyor. (Depo bunu zaten bir yerde biliyor:
`survival.py:725` "VIPER's hibernation charge ... exceeds its capacity and is capped".)
Gerçek açıklama şu: NASA'nın 50 saati **min-power modunda**, `p_shadow_w = 130 W` ise normal
gölge çekişi — iki farklı mod, iki farklı sayı.

**Tasarım sonucu:** dinamik dayanım `min(yayımlanan, türetilen)` OLAMAZ; o biçim VIPER'ın
dayanımını bayrak açılır açılmaz %33 kısar ve "tam şarjda yayımlanan sabiti verir" iddiasını
yanlışlar. Yerine **oransal** biçim kullanılıyor (§ Tasarım kararları, K5): dört profilde de
tam şarj + rating sıcaklığında tam olarak yayımlanan sabiti verir. Tutarsızlık *düzeltilmiyor*,
raporda **ölçüm olarak** yazılıyor.

### Sonda 5 — hibernasyon gücü sıralaması

| Profil | `p_hibernate_w` | `p_shadow_w` | oran | hibernasyon bekleme'den ucuz mu? |
|---|---|---|---|---|
| lpr_1 | 108 | 65 | 1,662 | **hayır** (%66 daha pahalı) |
| luvmi_m | None | 50 | — | **tanımsız** |
| nasa_viper | 100 | 130 | 0,769 | evet |
| cnsa_yutu_2 | 5 | 60 | 0,083 | evet (12×) |

LPR-1'in "hibernasyonu" idame modundan pahalı — arşiv belgesinin tanımıyla tutarlı
("idle + heater + termal yönetim"). Bu düzeltilmiyor, raporda yazılıyor. Ama iki profilde
hibernasyon *ucuz*, ve bu **planlayıcıda bir tuzak**: bedava bir gündüz şekerlemesi
planlayıcının güneş gelirini çöpe atmasına yol açar. Bu yüzden `HIBERNATE` kenarı karanlık
dilimlere kapılı (§ Tasarım kararları, K7).

---

## Tasarım kararları

### K1 — Kullanılabilir kesrin sıcak ucu `bat_op_min_c`, yeni katalog alanı YOK

Belgedeki "0 °C'de ~%85" kullanılamaz, çünkü `e_cap_wh` **zaten 0 °C'de ölçülmüş bir
kapasite**: NASA'nın Şubat 2025 brifingi VIPER için "5,420 Wh beginning-of-life capacity at
0 C" diyor ve `constants.py:365` bunu yazıyor; LPR-1'in 5 420 Wh'ı da aynı VIPER sayısı
(`constants.py:238`). 0 °C'de %85 demek aynı iskontoyu iki kez uygulamaktır.

Sıcak uç, profilin **kendi beyan ettiği batarya çalışma alt sınırı** `bat_op_min_c` alınıyor:
"profilin tam kapasiteyi iddia ettiği en soğuk sıcaklık". VIPER ve LPR-1'de bu **tam olarak
0 °C**, yani NASA'nın rating sıcaklığıyla çakışıyor — katalogla kaynağın bağımsız olarak
aynı yeri göstermesi tasarımın en güçlü tutamağı. Yutu-2'de −10 °C.

**Bunun bedeli sıfır yeni katalog alanı.** C2'nin okuduğu her şey ya zaten
`MODELLED_FIELDS`'ta, ya modül düzeyinde kaynaklı bir sabit, ya da etiketli bir varsayım.
`test_panel.py:315-322`'deki bölüntü tamlığı testi dokunulmadan yeşil kalır.

### K2 — Soğuk uç 200 K, ve `bat_op_min_c ≤ 200 K` olan profil REDDEDİLİR

`BATTERY_FREEZE_C = 200 K − 273,15 = −73,15 °C`, NASA Glenn'den alıntı, bir rover bataryasına
taşınması `"assumption:"` etiketli.

LUVMI-M `bat_op_min_c = −100 °C` beyan ediyor — donma eşiğinin **27 K altında**. İki uç
çakışıyor, eğri tanımsız. Uydurulmuş bir rating noktası konmuyor: model
`unavailable` + gerekçe döndürüyor ("bu profil, alıntılanan ölçümün elektrolit donma noktasını
koyduğu sıcaklığın altında bir batarya çalışma alt sınırı beyan ediyor; ikisi birden
doğru olamaz"). C6'nın `thermal_tau_s`'siz LUVMI-M için yaptığının aynısı.

Kalan üç profilde eğri uygulanır. Şekil varsayım; raporda üs süpürülür.

### K3 — Isıtıcı, İÇ HEDEFİ değil YÜZEYİ okur

İlk taslak ısıtıcıyı `inner_target_c(surface)` üzerinden sürüyordu. Bu **ölümcül bir
hataydı**: `surface_to_inner` yüzeyin işaretine göre parçalı ve sıfırda
`offset_cold − offset_hot` = 100 K aşağı sıçrıyor (`cost_engine.py:449`). Ölçüldü (LPR-1):
yüzey −0,1 °C → ısıtıcı 0 W, yüzey +0,1 °C → ısıtıcı 11,1 W. Yani **zemin ısınınca ısıtıcı
açılıyor**. C6 bu haritadan zarar görmüyor çünkü `apply_heater` yalnızca bir sıcaklığı
*kırpıyor* ve kırpma monoton; aynı monoton olmayan hedefi bir **güce** çevirmek monoton
değil.

Çözüm, kaynağın kendi denklemine dönmek: JSC'nin `T_env`'i **ortamdır**, yani yüzey. Model
`P = εσA(T_set⁴ − T_yüzey⁴)`, `[0, p_heater_w]` aralığına kırpılmış. Boyutlandırma noktası da
yüzey cinsinden: `THERMAL_MIN_TRAVERSABLE_C = −150 °C`, yani *modelin rover'ı üstünde
durmaya izin verdiği en soğuk yüzey*. Ofset haritası devreden tamamen çıkıyor.

### K4 — "Yeni ısıtıcı her zaman eskisinden küçüktür" iddiası GERİ ÇEKİLDİ

İlk taslak bunu iddia ediyordu. Ölçüm çürüttü (sonda 3): bugünkü terim `gölge_oranı ×
p_heater_w`; sıcaklık tabanlı terimde gölge oranı hiç yok. İki model **sıralanabilir değil**.
Rapor işaretli dağılımı yayımlıyor; kod hiçbir yerde tek yönlü bir sınır iddia etmiyor.

Bu aynı zamanda `housekeeping_power_w(0.0, rover) == p_idle_w` kilidini
(`test_review3_fixes.py:629`) ve `test_cost_cube.py:422`'yi ilgilendirir: **bayrak kapalıyken
ikisi de aynen geçerli kalır**, çünkü yeni terim yalnızca çağıran bir ısıtıcı gücü verdiğinde
devreye girer. Varsayılan yol karakter karakter eskisidir.

### K5 — Dinamik dayanım ORANSAL, `min()` değil

```
teslim_edilebilir(wh, T) = wh × usable_fraction(T)
dayanım_h(wh, T)        = h_yayımlanan × clamp01( max(0, teslim_edilebilir(wh,T) − rezerv)
                                                  / (e_cap − rezerv) )
```

Tam şarj + rating sıcaklığında pay ve payda birebir aynı sayı, oran **tam olarak 1,0**, sonuç
`h_yayımlanan`. Dört profilde de bit-eşit — VIPER dahil. `min()` biçiminin VIPER'ı sessizce
%33 kısması böylece ortadan kalkıyor.

**Rezervin kime ait olduğu adlandırılıyor** (çifte saymayı önleyen tek şey bu): `usable_fraction`
*depolanan* şarjı *teslim edilebilir* şarja çevirir. Rezerv bir **teslim edilebilir enerji
tabanıdır** — "hayatta kalma ısıtması için ayrılan enerji" (`safety_monitor.py:1053`) — yani
soğukta o tabanı karşılamak için gereken *depolanan* şarj artar. Dayanım da aynı teslim
edilebilir büyüklükten okunur. Tek bir hedge, iki kez değil.

Derate'in girmediği yerler de açıkça yazılıyor: şarj tavanı `e_cap_wh` nominal kalır (soğukta
şarj kısıtı için kaynak yok ve uydurulmuyor), maliyet gridinin normalizasyon ölçeği nominal
kalır, `battery_key` böleni nominal kalır. Bu üç seçim de bayrak açıkken bile geçerlidir ve
blokta yazılıdır.

**Binleme yayımlanan sabitte kalır.** `dark_quantum_h`, `dark_tol` ve `endurance_finite`
(`pathfinder_4d.py:974-983`) `h_max_shadow_h`'nin yayımlanan değerinden türetilmeye devam
eder; yalnızca `:1072`'deki **reddetme eşiği** durum bağımlı olur ve **yeni bataryada**
(`new_battery`) değerlendirilir. Dosyanın kendi kuralı bu: *"The CONSTRAINTS are still checked
on the exact values"* (`:424`). `safety_monitor`'ün LP-R01 eşiği de yayımlanan sabit kalır, yani
`test_safety_monitor.py:464` ve `test_illumination_corridor_real_grid.py:146` yeşil kalır.

### K6 — Hibernasyon zarfı ASKIYA ALMAZ, DEĞİŞTİRİR

İlk taslak hibernasyonda C6 zarfını askıya alıyordu. Bu, C6'nın kendi kapattığı açığı
(`pathfinder_4d.py:606`, iki karanlık blok arasında mekik dokuyup saati sıfırlamak) yeni bir
kılıkta geri getiriyordu.

Doğru ayrım, iddia sınırı 7'deki ayrım: **çalışma** zarfı sürerken geçerlidir, **hayatta
kalma** tabanı hibernasyonda. Hibernasyon boyunca iç sıcaklık
`[BATTERY_FREEZE_C, envelope.hi]` aralığında olmak zorunda — daha geniş ama **sonsuz değil** —
ve bu **her ara dilimde** kontrol edilir, yalnızca uçta değil (`DwellCube.inner_after` zaten
dilim dilim ilerliyor; `inside()` bugün yalnızca uçta çağrılıyor).

Hibernasyonda hangi bileşenin çalışma sınırının altına inildiği **adlandırılır**: LPR-1'de
zarfın soğuk ucu bataryanındır (0 °C) ama elektroniğin sınırı da (−10 °C) aşılır. NASA
Glenn'in kanıtı **hücrelere** dair, JSC'nin uyarısı **aviyoniğe** dair; yanıt ikisini de
söyler.

### K7 — `HIBERNATE` atomik, karanlıkta başlar, aydınlıkta biter

**Atomik çok dilimli tek kenar:** `(r,c,t) → (r,c,t+d)`; giriş, uyuklama ve dawn pre-heat tek
fiyatta. Böylece "şu anda hibernasyonda mıyım" diye bir **altıncı etiket ekseni gerekmiyor**;
5'li baskınlık demeti ve 7'li etiket anahtarı olduğu gibi kalıyor, C1/C6'nın bit-eşitlik
kilidi bozulmuyor. Kenarın türü yalnızca `came_from`'da taşınıyor.

**Karanlıkta başlar:** `exposure ≥ _DARK_RATIO_THRESHOLD` olmayan bir dilimden hibernasyona
girilemez. Sonda 5 bunun neden gerektiğini gösteriyor: VIPER ve Yutu-2'de hibernasyon
beklemeden ucuz, ve kapısız bir kenar planlayıcıyı güneşin altında şekerleme yapmaya iter.

**Aydınlıkta biter:** çıkış dilimi aydınlık olmak zorunda. Bu **NASA'nın mimarisi**, bizim
icadımız değil: "Solar Array output triggers a 'Dawn Mode'". Aynı kural, hibernasyonun en
tehlikeli açığını kapatıyor — karanlıkta girip karanlıkta çıkarak dayanım saatini sonsuza
kadar sıfırlamak artık mümkün değil, çünkü uyanmak için Güneş gerekiyor.

**Karanlık saati DURMAZ, hızı değişir:** `dark_h += saat × p_hibernate_w / p_shadow_w`.
Saati dondurmak `max_continuous_shadow_h`'yi kurgu hâline getirirdi ve D3'ün LP-R01'i
("shadow_continuous_h ≤ h_max_shadow_h") ölçmediği bir sayıyı rapor ederdi; ölçüldü ki
Yutu-2'de dondurma 2 saatlik dayanımı 210 saate çıkarıyor (×106). Oran biçimi ekseni tek
birimde tutar: LPR-1 hibernasyonda saati **daha hızlı** yakar (1,66×), Yutu-2 12× yavaş.
Rota ayrıca kaç saatinin hibernasyonda geçtiğini ayrı bir alanda bildirir.

**Batarya hibernasyonda `p_hibernate_w` çeker.** NASA'nın *pasif* hibernasyonunda batarya
izoledir ve çekiş sıfırdır; katalogdaki `p_hibernate_w` ise bir **idame** gücüdür (LPR-1'de
108 W, `p_shadow_w`'den büyük). Model katalogdaki modu uygular, farkı yazar, pasif modun ne
vereceğini raporda karşı-olgu olarak ölçer. Çekiş olduğu için batarya donma noktasının
**üstünde** kalmak zorundadır (`usable_fraction > 0`) — yoksa çekilecek güç yoktur. Bu, ilk
taslaktaki "donmuş batarya 108 W veriyor" çelişkisini kapatan kapıdır.

### K8 — Dawn pre-heat: enerji GÜNEŞTEN, süre kapalı formdan, saat cinsinden

NASA: "MBC in Dawn Mode operates on Solar Array power alone (Battery still Isolated)". Yani
ön-ısıtma **bataryayı boşaltmaz**; o saatlerde batarya izoledir (ne boşalır ne dolar) ve
dizinin ürettiği güç ön-ısıtıcıya gider.

Süre, `exit_time_h`'nin ısınma dalı — aynı denklem, ters yön:

```
P_ön   = min(p_heater_w, dizinin o dilimde ürettiği güç)
T_eq   = ısıtıcı açıkken dengeye gelinen iç sıcaklık
t_saat = tau_s × ln((T_eq − T_hib) / (T_eq − T_zarf_alt)) / 3600
```

`/3600` **kritik**: `tau_s` saniye, model saatle çalışıyor; `exit_time_h:298` de aynı bölmeyi
yapıyor. İlk taslak bunu atlamıştı (3600× hata).

`T_eq ≤ T_zarf_alt` ise logaritmanın argümanı ≤ 0'dır: ısıtıcı doymuştur ve **rover o hücrede
hiç uyanamaz**. Bu bir NaN değil, bir **reddir**: `hibernate_unwakeable` adında kendi sayacı
olan, `REJECTION_KEYS`'e, `no_path_reason_4d`'ye **ve onun baştaki `lead` demetine**
(`:176-179`) eklenen bir ret. Üçüncüsü unutulan edittir; plan onu ayrı bir madde yapıyor.

### K9 — Sıcaklık modelinin kendisi: izlemek ≠ zorlamak

Derate'in okuyacağı bir iç sıcaklık lazım. Bugün `inner_c` yalnızca `require_thermal_dwell`
altında entegre ediliyor; kapalıyken sentinel `inner0 = 0.0` duruyor
(`pathfinder_4d.py:967`). **Ve 0.0, LPR-1/VIPER'ın rating sıcaklığıyla birebir aynı sayı** —
yani derate sessizce 1,0 döner, hata vermez ve *koşmuş gibi görünür*. Bu, özelliğin ölçülmemiş
bir sayı yayımlamasının en olası yoluydu.

Çözüm: **izleme ile zorlamayı ayırmak.** `track_inner = enforce_dwell or derate`. İç sıcaklık
ikisinden biri açıkken entegre edilir; zarf **yalnızca** `enforce_dwell` altında reddeder.
Sentinel artık yalnızca ikisi de kapalıyken kullanılır ve o zaman derate de kapalıdır.
İç sıcaklık üretilemiyorsa (`thermal_tau_s` ya da zarf yok → LUVMI-M) `battery_model=
"temperature_derated"` **422**'dir, sessiz 1,0 değil.

Dürüst sonuç, açıkça yazılıyor: `require_thermal_dwell` **açıkken** LPR-1 ve VIPER'ın iç
sıcaklığı zaten `[0, 35] °C` içinde tutulur, yani `usable_fraction ≡ 1,0` ve derate ölçülebilir
bir etki yapmaz. Derate'in ısırdığı yer tam olarak zarfın zorlanmadığı yer — ve hibernasyon.

### K10 — 2-B maliyet gridi dokunulmaz; sıcaklık yalnızca 4-B hattında

Sıcaklığa bağlı ısıtıcı `compute_cost_grid`'e **girmiyor**. Gerekçe uygunluk değil ilke:
2-B gridin epoch'u yok, dolayısıyla dilim başına yüzey sıcaklığı da yok — C1'in
`/api/plan` üzerindeki panel bloğunun `reason: "the 2-D cost grid has no epoch"` demesiyle
aynı gerekçe. `battery` bloğu `/api/plan`'da aynı cümleyi kurar.

Sonuç: `COST_MODEL_ID` **v5'te kalır**, dört checked-in SHA-256 maliyet-gridi özeti
**kıpırdamaz**, ve `test_cost_engine_slip.py:126`, `test_review3_fixes.py:421`,
`test_risk_cost.py:166`, `test_roughness_cost.py:111` dokunulmadan yeşil kalır. C1'in ürettiği
kanıtın aynısı üretilir.

Skaler/vektörel ikizler ayrılmaz: ikisi de aynı isteğe bağlı `heater_w` argümanını alır, verilmezse
ikisi de eski modeldir. Ayrıca bugün eksik olan kilit ekleniyor —
`test_review_fixes.py:340`'ın ikiz testi **yalnızca eğimi** süpürüyor, `shadow_ratio` iki
tarafta da 0,0'da duruyor, yani idame teriminin gölge yarısını hiç görmüyor. Yeni test dört
rover × dört gölge oranı × ısıtıcı verili/verilmemiş olarak `==` ile süpürür.

### K11 — `heater_power_model` ≠ "constant" ise `heater_model="thermostat_assumed"` ZORUNLU

`kA·ΔT` (ya da `εσA·ΔT⁴`) **tanımı gereği** `T_set`'i tutan bir termostatın kararlı hâl
gücüdür. Bunu `heater_model="none"` ile birlikte kabul etmek, aynı yanıtta "ısıtıcının
sıcaklığa etkisi yok" derken bir termostatın faturasını ödemek olurdu. İkisi bağımsız eksen
değil, tek bir cihaz hakkında iki ifadedir. Uyumsuz bileşim **422**.

Ve `thermostat_assumed` artık **güç sınırlı**: hedef
`min(envelope.lo, inner_target + ulaşılabilir artış)`. C6 bunu yapamadığını söylüyordu çünkü
W-to-K bağlantısı yoktu; C2 o katsayıyı getirdiği için artık yapılabiliyor.
`HEATER_THERMOSTAT_ASSUMPTION_SOURCE` aynı commit'te bunu anacak biçimde düzeltiliyor —
bugünkü hâli "no W-to-K coefficient" diyor ve C2 onu yanlışlıyor.

### K12 — Katalogdaki iki bayat etiket düzeltiliyor

- `constants.py:21`'deki *"four of them are now wired (… p_hibernate_w …)"* **yanlış**:
  `p_hibernate_w`'nin depoda tek okuyucusu yok (doğrulandı: yalnızca `MODELLED_FIELDS`, dört
  profil değeri ve hiç import edilmeyen `P_HIBERNATE_W` aliası). C2 onu gerçekten bağladığı
  için yorum hem düzeltiliyor hem de artık doğru hâle geliyor.
- `thermal_tau_s` `DECLARED_ONLY_FIELDS`'ta duruyor ama C6 onu okuyor
  (`thermal_dwell.py:315, 491, 671, 905, 1183`). `MODELLED_FIELDS`'a taşınıyor. **Ama alan
  API'den kaybolmasın diye** `rover_catalog()`'a üst düzey anahtar olarak ekleniyor — sözleşme
  açısından bu bir **ekleme**. `frontend/src/mission/useThermalDwellCapability.ts:13`'teki
  yorum onu "declared-only olduğu için okumuyorum" diye gerekçelendiriyor; C2 frontend koduna
  dokunmadığı için bu yorum bayatlıyor ve sözleşme ekinde açıkça not ediliyor.

---

## Bileşenler

### `backend/app/battery.py` (yeni)

Kimlik ve iddia: `BATTERY_MODEL_ID`, `BATTERY_VALIDITY = "MODEL"`, `BATTERY_SCOPE`,
`BATTERY_CLAIM`, `BATTERY_REFERENCES`, `NASA_GLENN_QUOTED`, `JSC_QUOTED`.

Sabitler ve kaynak dizeleri: `BATTERY_FREEZE_K = 200.0`, `BATTERY_FREEZE_C`,
`BATTERY_FREEZE_SOURCE` (`"assumption: "` ile başlar), `USABLE_FRACTION_SHAPE_SOURCE`,
`HEATER_SIZING_SOURCE`, `HIBERNATION_POWER_SOURCE`, `HIBERNATION_EVIDENCE_LIMIT`.

Fonksiyonlar:

| İmza | Ne |
|---|---|
| `usable_fraction(inner_c, rover, exponent=1.0)` | teslim edilebilir kesir; `unavailable` profilde `None` |
| `usable_fraction_unavailable_reason(rover)` | neden hesaplanamıyor (LUVMI-M) |
| `deliverable_wh(stored_wh, inner_c, rover)` | depolanan → teslim edilebilir |
| `heater_coefficients(rover)` | `(kA, esA)` kalibrasyonu + boyutlandırma noktası |
| `heater_power_w(surface_c, rover, model)` | `"constant" \| "delta_t" \| "radiative"`, `[0, p_heater_w]`'ye kırpılı; dizi biçimi `heater_power_w_grid` |
| `jsc_survival_temperature_check()` | JSC'nin %26'sını yeniden üretir (C1'in `viper_corner_check`'i gibi) |
| `shadow_endurance_h(stored_wh, inner_c, rover)` | K5'in oransal dayanımı |
| `hibernation_available(rover)` | `(bool, reason)`; LUVMI-M `p_hibernate_w=None` |
| `hibernate_dark_rate(rover)` | `p_hibernate_w / p_shadow_w` |
| `dawn_preheat(inner_c, surface_c, solar_w, rover)` | `(saat, T_çıkış, reason)`; uyanılamıyorsa `reason` |
| `survival_envelope(rover)` | çalışma zarfının hibernasyon karşılığı: `[BATTERY_FREEZE_C, hi]` |
| `battery_block(...)`, `rover_battery_block(rover)` | yanıt ve katalog blokları |

### Dokunulan yerler (hepsi isteğe bağlı parametre, varsayılanı eski davranış)

| Dosya | Ekleme |
|---|---|
| `constants.py` | üç kaynak dizesi, `thermal_tau_s` → `MODELLED_FIELDS`, `rover_catalog()`'a `thermal_tau_s` + `battery_model` bloğu, `:21` yorumu, `HEATER_THERMOSTAT_ASSUMPTION_SOURCE` düzeltmesi |
| `cost_engine.py` | `housekeeping_power_w(..., heater_w=None)` ve onu çağıran üç fonksiyona geçiş |
| `cost_vec.py` | `_housekeeping_power_w_grid(..., heater_w=None)` — aynı işlem sırası |
| `cost_cube.py` | `wait_cost(..., heater_w)`, `build_wait_cost_cube(..., heater_w_series)`, `build_cost_cube(..., heater_w_series)` |
| `pathfinder_4d.py` | `track_inner`, dinamik dayanım eşiği, `HIBERNATE` atomik kenarı, `hibernate_unwakeable`, `path_actions`, hibernasyon metrikleri |
| `survival.py` | `_power_terms(..., heater_w)` (afin yapı korunur: `heater_w` skaler girer) |
| `stress_test.py` | ısıtıcı gücü serisi; `path_actions` okuma |
| `simulation.py` | `simulate_path(..., heater_w)` |
| `safe_haven.py` | `route_margins` teslim edilebilir enerjiyi okur |
| `main.py` | üç bayrak, `battery` bloğu, `GET /api/battery-model`, survival önbellek anahtarı |

### Testler

`test_battery.py` (birim + bit-eşitlik + ikiz süpürmesi), `test_battery_api.py` (API + 422'ler),
`test_battery_real_grid.py` (skip-korumalı Site11).

### Rapor

`scripts/battery_hibernation_report.py` (`--json` / `--from-json` / `--out`) →
`docs/research/battery_hibernation_report.md`.

---

## Veri akışı

```
start_utc ─► illumination_series ─► shadow_series ─┬─► surface_temperature_series (C6, mevcut)
                                                   │            │
                                                   │            ▼
                                                   │   battery.heater_power_w_grid   (K3)
                                                   │            │
                                                   ├────────────┼─► build_cost_cube(heater_w_series)
                                                   ├────────────┼─► build_wait_cost_cube(heater_w_series)
                                                   └────────────┴─► astar_4d(heater_w_series,
                                                                             battery_model,
                                                                             allow_hibernate)
                                                                          │
                              DwellCube.inner_after ──► inner_c ──────────┤ (K9: track_inner)
                                                                          │
                                        battery.usable_fraction ──────────┤ (K1/K2)
                                        battery.shadow_endurance_h ───────┤ (K5)
                                        battery.dawn_preheat ─────────────┘ (K8)
```

---

## Hata davranışı

| Durum | Yanıt |
|---|---|
| `battery_model="temperature_derated"`, iç sıcaklık üretilemiyor | 422, gerekçe (C6'nın `dwell_unavailable_reason` deseni) |
| `battery_model="temperature_derated"`, `bat_op_min_c ≤ 200 K` (LUVMI-M) | 422, K2'nin gerekçesi |
| `heater_power_model ≠ "constant"`, `heater_model="none"` | 422, K11'in gerekçesi |
| `allow_hibernate=true`, `p_hibernate_w=None` (LUVMI-M) | 422, gerekçe |
| Hibernasyon uyanamıyor (ısıtıcı doymuş) | kenar reddi, `hibernate_unwakeable` sayacı, `no_path_reason_4d`'de cümle |
| Hibernasyon alıntılanan kanıtın dışında (< 80 K ya da > 14 gün) | rota kabul, `beyond_cited_evidence: true` + gerekçe |
| Üç bayrak da kapalı | her şey bit-eşit; blok `applied: false` |

---

## Test stratejisi

1. **Bit-eşitlik (en önemli).** Üç bayrak kapalıyken: LPR-1'in iki checked-in SHA-256
   maliyet-gridi özeti kıpırdamaz; standart 4-B rotalar aynı hamle, aynı `nodes_expanded`,
   aynı `total_cost`; `COST_MODEL_ID` v5.
2. **Bayrak-AÇIK kilidi (bit-eşitliğin ayna görüntüsü).** Bir durumda yeni modelin eskisinden
   **ne kadar** ayrıldığı yazılı bir iddia olarak pinlenir. Yazılamıyorsa özelliğin ölçecek
   bir şeyi yok demektir.
3. **İkiz süpürmesi.** Skaler/vektörel ikizler dört rover × dört gölge oranı × ısıtıcı
   verili/verilmemiş, `==` ile.
4. **Dört profilde `unavailable` disiplini.** LUVMI-M üç modelde de gerekçeli reddeder.
5. **Planlayıcı açıkları.** Karanlıkta girip karanlıkta çıkma reddedilir; güneşte hibernasyon
   reddedilir; hibernasyon saati durdurmaz; `max_continuous_shadow_h` hibernasyonlu rotada da
   gerçek sürekli karanlığı bildirir.
6. **Gerçek grid**, skip-korumalı, altı dosyadaki metinle birebir aynı muhafızla.

---

## Kapsam dışı (ve nedeni)

- **Şarj tarafı soğuk kısıtı** — soğukta Li-ion şarjı deşarjdan daha kısıtlıdır ama katalogda
  da kaynaklarda da sayı yok. Şarj tavanı nominal kalır ve bu blokta yazılır.
- **İç direnç / güç tarafı derate** — kapasite derate'i ile güç derate'i farklı şeylerdir;
  ikincisi için kaynak yok.
- **Yaşlanma, çevrim ömrü, hücre dengeleme** — NASA Glenn "Battery Life Testing to demonstrate
  multiple lunar cycles" diyor: *gelecek iş* olarak, sayısız.
- **Gerçek gövde termal modeli** — JSC'nin zarf eksenleri bir gövde modeli gerektiriyor;
  C6 bunu zaten kapsam dışı bıraktı.
- **Pencere kayması** — diskteki grid (2400, 2500), test paketi (1500, 1000) bekliyor.
  Proje düzeyinde ayrı bir karar; C2 pencereye dokunmaz.
- **Frontend kodu** — dokunulmaz; yalnızca sözleşme eki.

---

## Uygulama sırasında bulunanlar ve ölçümler

### Bulunanlar (tasarımdan sapmalar, nedenleriyle)

Tasarım, yazılmadan önce beş bağımsız düşmanca lensle denetlendi (fizik, iddia sınırları,
bit-eşitlik, planlayıcı doğruluğu, kapsam). **İlk taslağın dört iddiası ölçümle çürütüldü ve
geri çekildi;** aşağıdakiler nihai hâlin nedenleridir.

**1. Isıtıcı iç hedefi değil YÜZEYİ okuyor (ölümcül hataydı).** İlk taslak ısıtıcıyı
`inner_target_c(surface)` ile sürüyordu. `cost_engine.surface_to_inner` yüzeyin **işaretine**
göre parçalı ve sıfırda `offset_cold − offset_hot` = 100 K aşağı sıçrıyor. Ölçüldü (LPR-1):
yüzey −0,1 °C → 0 W, yüzey +0,1 °C → 11,1 W. Yani **zemin ısınınca ısıtıcı açılıyordu.** C6 bu
haritadan zarar görmüyor çünkü `apply_heater` yalnızca bir sıcaklığı *kırpıyor* ve kırpma
monoton; aynı hedefi bir **güce** çevirmek monoton değil. JSC'nin `T_env`'i ortamdır, ortam da
yüzeydir. Ofset haritası ısıtıcı yolundan tamamen çıkarıldı; monotonluk testle kilitlendi.

**2. Yasa doğrusal değil T⁴ (kaynak okununca ortaya çıktı).** Araştırma belgesi
`k·A·(T_survive − T_env)` istiyor; belgenin **kendi gösterdiği kaynak** (JSC, TFAWS23-PT-52
s. 3) `Q_rad = εσA(T_obj⁴ − T_env⁴)` yazıyor ve *"weighted to the 4th power"* diyor. İkisi de
sunuldu (`delta_t` / `radiative`) ve farkları ölçüldü. JSC'nin yayımladığı %26, kendi
yasalarından **%26,50** çıkıyor (fark +0,50 puan) — C1'in `viper_corner_check`'inin muadili,
doğrulanabilir bir çapraz kontrol.

**3. "Yeni ısıtıcı ≤ eski ısıtıcı" iddiası GERİ ÇEKİLDİ.** Ölçüldü (LPR-1, 210 063 geçilebilir
hücre): `delta_t` hücrelerin **%13,89**'unda, `radiative` **%44,16**'sında eskisinden **fazla**
çekiyor; en büyük fazla +21,87 / +22,34 W. Sebep sonda 3: gölge oranıyla yüzey sıcaklığı
bağımsız. İki model sıralanabilir değil ve kod hiçbir yerde tek yönlü sınır iddia etmiyor.

**4. Dayanım `min()` değil ORAN (VIPER'ı ölçünce ortaya çıktı).** İlk taslak
`min(yayımlanan, türetilen)` idi ve "tam şarjda yayımlanan sabiti verir" diyordu. Ölçüm:
LPR-1 66,71 s, LUVMI-M 22,40 s, Yutu-2 17,50 s (hepsi yayımlananın üstünde, yani `min` birim),
ama **NASA VIPER 33,35 s** — yayımlanan 50 s'in **altında**. VIPER'ın kataloğu kendi içinde
tutarsız (50 s × 130 W = 6 500 Wh > 5 420 Wh kapasite; NASA'nın 50 saati min-power modunda).
`min` biçimi bayrağı açar açmaz VIPER'ın dayanımını %33 kısardı. Oransal biçim dört profilde de
tam şarj + rating'te **tam olarak** yayımlanan sabiti veriyor; tutarsızlık düzeltilmedi,
raporda ölçüm olarak yazıldı.

**5. Karanlık saati DURMUYOR, hızlanıyor/yavaşlıyor.** İlk taslak hibernasyonda saati
durduruyordu. Ölçüldü: durdurmak Yutu-2'nin 2 saatlik dayanımını **210 saate** çıkarıyor (×106)
ve `max_continuous_shadow_h`'yi kurgu hâline getirip D3'ün LP-R01'ini ölçmediği bir sayı
üzerinde geçirtiyordu. Yerine `p_hibernate_w / p_shadow_w` oranı: LPR-1 1,6615 (hibernasyon
saati **daha hızlı** yakıyor), VIPER 0,7692, Yutu-2 0,0833.

**6. Zarf askıya alınmıyor, DEĞİŞTİRİLİYOR — ve her ara dilimde kontrol ediliyor.** Askıya
almak C6'nın kendi kapattığı mekik açığını yeni kılıkta geri getirirdi. Hibernasyonda
`[BATTERY_FREEZE_C, envelope.hi]` geçerli. Tüm uyku boyunca kontrol, dilim dilim yürümeden
yapılıyor: birinci mertebe gecikme başlangıcı ile hedefleri arasındaki aralığı asla terk etmez,
yani iki uç **her** ara dilimi sınırlar. Ret için ayrı bir sayaç açıldı (`hibernate_too_cold`)
çünkü `thermal_dwell` sayacını kullanmak, `require_thermal_dwell` kapalıyken bile C6'nın
mesajını ürettiriyordu.

**7. Hibernasyon karanlıkta başlar, aydınlıkta biter.** İkincisi NASA'nın kendi mimarisi
(*"Solar Array output triggers a 'Dawn Mode'"*), bizim icadımız değil — ve tam da karanlıkta
girip karanlıkta çıkarak dayanımı sonsuza kadar sıfırlama açığını kapatıyor. Birincisi bir
ölçümün sonucu: hibernasyon dört profilin **ikisinde** beklemeden ucuz (VIPER 100 W ↔ 130 W,
Yutu-2 5 W ↔ 60 W), yani kapısız bir kenar planlayıcıyı güneşin altında şekerleme yapmaya
iterdi.

**8. Dawn pre-heat'in enerjisi BATARYADAN gelmiyor** (kaynak okununca). *"MBC in Dawn Mode
operates on Solar Array power alone (Battery still Isolated)"*. Bedel zaman ve güneş geliri.
Ayrıca süre **saat** cinsinden (`/3600`, `exit_time_h:298` ile aynı); ilk taslak bunu atlamıştı
ve 3600× hata yapıyordu. Isıtıcı doymuşsa logaritmanın argümanı ≤ 0'dır: NaN değil, kendi
sayacı (`hibernate_unwakeable`) olan bir **ret** — ve sayaç `no_path_reason_4d`'nin baştaki
`lead` demetine de eklendi, yoksa hibernasyonla kapanan bir rota kendini "ufuk kısa" diye
bildirirdi.

**9. İzleme ile zorlama ayrıldı — ve sentinel tuzağı kapatıldı.** İç sıcaklık bugüne dek
yalnızca `require_thermal_dwell` altında entegre ediliyordu; kapalıyken sentinel `inner0 = 0.0`
duruyor. **0.0, LPR-1 ve VIPER'ın rating sıcaklığıyla birebir aynı sayı**, yani derate sessizce
1,0 döner, hata vermez ve *koşmuş gibi görünürdü*. Bu, özelliğin ölçülmemiş bir sayı
yayımlamasının en olası yoluydu. Artık `track_inner = enforce_dwell or derate or hibernate` ve
iç sıcaklık üretilemiyorsa **422**. Dürüst sonuç açıkça yazıldı: `require_thermal_dwell`
açıkken LPR-1/VIPER zaten `[0, 35] °C` içinde tutulur, yani derate orada özdeş 1,0'dır — ısırdığı
yer zarfın zorlanmadığı yer ve hibernasyondur.

**10. Yeni katalog alanı yok.** Sıcak uç profilin kendi `bat_op_min_c`'si alındığı için
`battery_rating_c` diye bir alan gerekmedi; LPR-1 ve VIPER'da bu **tam olarak 0 °C**, yani
NASA'nın 5 420 Wh'ı verdiği sıcaklıkla çakışıyor. `test_panel.py:315`'in bölüntü tamlığı testi
dokunulmadan yeşil kaldı.

**11. Sapma — `simulation.simulate_path` ve `safe_haven.route_margins` bağlanmadı.** İkisi de
2-B/nominal yolda: `simulate_path`'in okuyabileceği tek termal alan uzun vadeli yıllık zirvedir
(4-B'nin dilim başına serisi değil) ve `route_margins` nominal şarjla sabit idame gücü
kullanır. Yarım bağlamak yerine sınır **yanıtta** söylendi:
`battery.route.margins_use_nameplate_charge: true`.

**12. `stress_test` üçüncü aileyi öğrendi.** B5 bacakları `path_states`'ten geometrik olarak
türetiyordu ve bir hibernasyonu bekleme sayardı — uykudaki rover'ı idame gücünde modellerdi.
`route_legs(actions=…)` ve `RouteLegs.is_hibernate` eklendi; verilmezse rota C2 öncesi gibi
okunuyor.

**13. Survival önbellek anahtarına bayrak eklendi.** İki istek yalnızca ısıtıcı modelinde
farklıysa, `_CACHE_LIMIT = 2` yüzünden biri öbürünün alanını kullanıyordu — sessiz ve
istekler-arası. B1'in alanı ısıtıcıyı yayımlanan azamisinde çeker (alanın ufku plandan uzun ve
orada yüzey yok; güvenlik sınırı muhafazakâr olabilir, iyimser olamaz).

**15. Şafağın sürmesi şart koşuldu (kodu okurken bulundu, testten sonra).** İlk hâl, ilk
aydınlık dilimi bulup ön-ısıtmayı oradan başlatıyor ve varışta karanlık saatini sıfırlıyordu.
Ama NASA Glenn'in kendi kutup notu *"Polar Regions subject to multiple short (Dusk-Dawn)
cycles"* diyor: ilk ışık, ışığın süreceğinin garantisi değil. Ön-ısıtma ortasında karanlığa
dönen bir şafak, rover'ı ne uykuda ne uyanık bırakır — ve (iyimser olan yarısı) saat gerçekte
aydınlık olmayan bir dilimde sıfırlanırdı. Artık `dawn`'dan varışa kadar **her dilimin** aydınlık
olması şart; olmayan `hibernate_unwakeable` ile reddediliyor.

**16. Isıtıcılı bekleme küpünün tekilleştirmesi bire bir doğrulandı.** Kazanç dilim başına
skalerken ısıtıcı **hücre başına** değişiyor, yani tekilleştirme anahtarı (aydınlık oranı,
ısıtıcı gücü) **çiftine** genişliyor. Üç yolun (C2 öncesi, yalnız C1 kazancı, kazanç + ısıtıcı)
üçü de skaler fonksiyonla `np.array_equal` — testle kilitlendi.

**14. Katalogda iki bayat etiket düzeltildi.** `constants.py:21`'deki "p_hibernate_w now wired"
**yanlıştı** (depoda tek okuyucusu yoktu; doğrulandı) — C2 onu gerçekten bağladı.
`thermal_tau_s` ise `DECLARED_ONLY_FIELDS`'ta duruyordu ama C6 onu gönderildiği günden beri
okuyor; `MODELLED_FIELDS`'a taşındı **ve** `rover_catalog()`'a üst düzey anahtar olarak eklendi,
böylece etiketi düzeltmek sayıyı API'den silmedi. `HEATER_THERMOSTAT_ASSUMPTION_SOURCE`'un
"no W-to-K coefficient" cümlesi C2 ile yanlışlandığı için aynı commit'te değiştirildi.

### Ölçümler (Site11, pencere (2400, 2500), 210 063 geçilebilir hücre; 16 Eylül 2026)

**Bit-eşitlik — kanıt.** `COST_MODEL_ID` **v5'te kaldı**; LPR-1'in iki checked-in SHA-256
maliyet-gridi özeti (v5 `55e1bb3c…`, v4 `0e74607d…`) **bayt-eşit**. NASA VIPER'ınki C2'den
**önce de** eşleşmiyordu (4af6989'un `slope_max_deg` düzeltmesi) ve referans listemde duruyor.
Gerçek gridde: üç anahtar açıkça kapalı verildiğinde rota, maliyet ve `nodes_expanded` hiç
belirtilmemişkiyle **aynı**.

**"Karanlık = soğuk" yanlış.** Spearman(gölge oranı, yüzey sıcaklığı) = **−0,0014**. Yüzey
−146,37 / −47,22 / 28,17 °C (min/medyan/maks), gölge 0,1012 / 0,5952 / 0,9762. Aydınlık ama
soğuk cepler: gölge < 0,5 ∧ yüzey < −50 °C → **4 922** hücre (%2,34).

**Isıtıcı katsayıları** (yüzeyden, boyutlandırma −150 °C): LPR-1 `kA` 0,166667 W/K,
`εσA` 4,6845e-09 W/K⁴ (ε=1'de 0,0826 m²); VIPER 0,333333 / 9,3689e-09 (0,1652 m²);
Yutu-2 0,142857 / 4,3809e-09 (0,0773 m²); LUVMI-M 0,400000 / 2,9902e-08 (0,5273 m²). İma edilen
alanların küçüklüğü, katalogdaki `p_heater_w`'nin bir **idame** ısıtıcısı olduğunu söylüyor.

**Rotalar** (`/api/plan-4d`, varsayılan coarsen):

| Rota | anahtar | hamle | maliyet | düğüm | en düşük SOC |
|---|---|---|---|---|---|
| LPR-1 gündüz (28 Eyl 2026) | varsayılan | 41 | 3,445393 | 31 219 | %92,48 |
| | `radiative` | 41 | 3,451216 | 31 847 | %92,23 |
| | `delta_t` | 41 | 3,447470 | 36 608 | %92,41 |
| | `derated` | 41 | 3,445393 | 49 149 | %92,48 |
| | `hibernate` | 41 | 3,445393 | 49 216 | %92,48 |
| LPR-1 Ay gecesi (13 Eyl 2026) | varsayılan | 116 | 7,837081 | 171 117 | %67,42 |
| | `radiative` | 116 | 7,836790 | 171 145 | %67,43 |
| | `delta_t` | 116 | 7,836174 | 171 228 | %67,45 |
| | **`derated`** | **404** | — | — | — |
| | `hibernate` | 116 | 7,837081 | 172 528 | %67,42 |

Gündüz rotasının varsayılan sayıları (41 hamle, 3,445393) **C1'in raporundakiyle aynı** — yani
C2 gerçek gridde de bit-eşit.

**En önemli ölçüm: gece rotası `derated` altında 404.** *"11 757 edges would have drained the
battery below the 20 percent reserve"*. C2 öncesi model aynı rotada en düşük SOC'yi %67,42
diye bildiriyordu — rahat. Teslim edilebilir şarj fiyatlandığında rota **yapılamaz** hâle
geliyor. Özellik bir sayıyı değil bir **güvenlik hükmünü** değiştiriyor.

**Isıtıcı modelleri rotayı değiştirmiyor, maliyeti ve SOC'yi değiştiriyor** (gündüz +%0,17
maliyet, −0,25 puan SOC). Gece rotasında maliyet hafifçe **düşüyor** — o epokta yüzeyler daha
sıcak olduğu için sıcaklık tabanlı ısıtıcı gölge oranının yüklediğinden az çekiyor.

**Hibernasyon hiçbir standart rotada seçilmedi** (`hibernate_steps = 0`). Dürüst nedeni:
gündüz rotasında bol güneş var, gece rotasında en uzun sürekli karanlık **4,80 s** ve LPR-1'in
dayanımı 50 s — yani hibernasyona hiç *ihtiyaç* yok; üstelik LPR-1'de hibernasyon beklemeden
**pahalı** (108 W ↔ 65 W). Kenarın çalıştığı, sentetik bir gecede testle kilitlendi: Yutu-2
(2 s dayanım, 5 W uyku) 20 saatlik bir karanlığı bekleyerek **geçemiyor**, hibernasyonla
geçiyor; uyku bütçenin 20 × 5/60 = **1,6667 saatini** harcıyor ve en soğuk iç sıcaklık −70 °C
ile donma noktasının (−73,15 °C) üstünde kalıyor.

**Derate ve hibernasyon düğüm sayısını artırıyor** (gündüz 31 219 → 49 149 / 49 216): beşinci
etiket ekseni (termal marj) artık `require_thermal_dwell` olmadan da canlı, çünkü farklı
sıcaklıktaki iki etiket gerçekten farklı şeyler yapabiliyor. Bedel ölçüldü ve yazıldı.

**NASA VIPER kısa leg (30 May 2027) altı anahtarın hepsinde 422** — *"start (358, 494) falls in
coarse block (89, 123) at coarsen=4, which is not traversable"*. C1'in raporu aynı 422'yi
kaydediyor, yani **C2'den önce de** böyleydi.

**Tam paket ve referans.** Referans temiz HEAD'de (719639b) ölçüldü: **24 başarısız / 2 179
geçti / 8 atlandı** (42 dk 36 s). C2 ile: **25 başarısız / 2 280 geçti / 5 atlandı** (28 dk 16 s).
Hepsi `*_real_grid.py` dosyalarında; tek bir birim ya da API testi düşmüyor.

İki FAILED listesi `comm` ile karşılaştırıldı: **24'ü birebir ortak**, referansta olup C2'de
düzelen yok, ve **bir tane yeni** —
`test_uncertainty_real_grid.py::test_vipers_haven_to_haven_route_gets_its_dem_band`.

Bu tek fark **C2'ye ait değil ve bu ölçülerek gösterildi**, varsayılarak değil: C2 stash'lenip
temiz HEAD'de yalnız o test koşuldu ve **aynı hatayla** düştü —
*"start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable"*,
yani öbür 24'ün hepsini düşüren aynı pencere kayması. Referansta neden görünmediği de belli:
test `dem_clone_horizons.npy` önbelleğine kapılı ve o dosya **referans koşusunun kendisi
tarafından** üretildi (zaman damgası 03:04:40, koşum 03:03'te başladı) — `skipif` toplama
anında değerlendirildiği için o koşumda atlandı, ikincisinde koştu. Atlama sayısının 8'den
5'e düşmesinin sebebi de aynı. **Bir test atlanıyorsa geçti sayılmaz**; burada da sayılmadı,
ölçüldü.

**Testler:** 74 birim + 15 API + 10 skip-korumalı gerçek grid = **99**.

**Ruff:** `backend/app` C2 ile ve C2'siz **12 hata** veriyor — C2 hiçbir yeni bulgu eklemedi.
