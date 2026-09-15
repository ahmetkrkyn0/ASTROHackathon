# C1 — Güneş paneli geliş açısı (cos i) ve panel geometrisi: Site11 ölçümü

**Üretildi:** 2026-09-15T19:30:15Z · `scripts/panel_cos_i_report.py` · ölçüm süresi 3,1 dk

**Okuma notu:** bu belgedeki her sayı Site11 gridinde ve gerçek NAIF kernel'leriyle koşturuldu. Kaynakların kendi sayıları ayrı bir bölümde, **alıntı** olarak durur ve bizim ölçümlerimizle aynı tabloya konmaz. Model etiketi **MODEL**: bu yalnızca bir geometri çarpanıdır — verim, alan, toz, sıcaklık katsayısı, albedo yok.

## 1. Kaynaklar ne diyor (alıntı) ve modelin NASA'nın iki sayısıyla çapraz kontrolü

Bugünkü model — `p_solar_w × (1 − gölge)` — panelin Güneş'e **her zaman dik** olduğunu varsayar. Bu varsayım literatürde açıkça yazılıdır:

> *"This assumes that any positive amount of solar illumination is adequate to fully power the rover, which is true for rover configurations with two-degree-of-freedom articulated solar arrays that can always point directly at the sun (provided the array is appropriately sized)."* — Otten, Jones, Wettergreen, Whittaker, ICRA 2015 (A2'nin de kaynağı)

> *"we assume that the rover maintains a constant area of solar panels perfectly oriented towards the Sun at all times… We keep the incorporation of more complex power generation models as future work."* — Lamarre, Malhotra, Kelly, IEEE AERO 2024 (B1'in kaynağı)

**Ama LunaPath'in varsayılan rover'ının öyle bir dizisi yok.** `lpr_1`'in 410 W'ı NASA VIPER'ın PIP'inden gelir ve o belge diziyi şöyle tanımlar (5 420 Wh ise PIP'te **yok**; o sayı Bluethmann'ın 2. slaytındaki *"Battery capacity (start of life @ 0C): 5,420 W-hr"*):

> *"three approximate 1 m2 solar arrays (one each on the port, starboard, and aft surfaces), generating 410 (TBR) W of total power"* — VIPER Proposal Information Package (NTRS 20210015009), page 8

> *"Solar arrays: 320W per panel (450W on corner)"* — Bluethmann, LSIC Tech Infusion, 14 November 2024 (NTRS 20240013903), slide 2

> *"Omni-directional driving with sun on corner / Maximizing power generation"* — Bluethmann (NTRS 20240013903), slide 5

Aynı sunumun 7. slaytı gimbal'lerin **yalnızca** yüksek kazançlı antende ve navigasyon kameralarında olduğunu söyler: dizi eklemsizdir. Bu iki NASA sayısı aynı donanımın iki geometrisidir, yani aralarındaki oran saf bir **geometri** ifadesidir — ve çok yüzeyli cos i modeli bu orana **uydurulmadan** onu öngörür:

| Büyüklük | Değer |
|---|---|
| bir yüzey dik gelişte (ham kazanç) | 1,000000 |
| üç yüzey, en iyi başlık (ham kazanç) | 1,414214 (= √2, ψ₀ = 135,00°) |
| modelin oranı | 1,41421 |
| NASA'nın yayımladığı oran (450 / 320) | 1,40625 |
| NASA'nın 320 W'ından modelin öngördüğü köşe gücü | **452,5 W** |
| NASA'nın yayımladığı köşe gücü | **450,0 W** |
| fark | 2,5 W (0,57 %) |

**Okuma:** NASA iki gücü yayımladı, aritmetik bizim. Bu, modelin **geometri teriminin** tutarlılık kontrolüdür; enerji modelimizin doğrulanması DEĞİLDİR ve öyle sunulmaz.

### RoverDevKit'in kendi doğrulaması (ONLARIN sonucu, alıntı)

- Tepe güç: *"The fresh-array rover Pragyan (one lunar day of operation, hence a near-beginning-of-life peak) is predicted at 52 W against a published 50 W band of 40-70 W - a +5% error that stays in-band across the entire cell-efficiency range (0.28-0.32, giving 49-56 W)."*
- Kütle modeli: *"Across the in-class rovers the model predicts total mass to a median absolute error of 13.3 % (mean 14.8 %)."*
- Varsayılan dizi: *"The default array is horizontal; high-latitude runs can pass a fixed tilt, typically min(80 deg, |lambda|), to represent a deployable panel aligned with the low-elevation polar sun."*

Bunlar bizim ölçümümüz değildir ve bizim tablolarımıza karışmaz. Araştırma belgesindeki "MAE %13,3" ifadesi **ortanca** mutlak hatadır (ortalama %14,8); makale 52 W ↔ 50 W için "+5%" yazar (aritmetik +%4) — makale alıntılanır, yeniden hesaplanmaz.

## 2. Site11'in Güneş geometrisi

| Büyüklük | Değer |
|---|---|
| pencere merkezi | -88,9205°, -72,6721° |
| RoverDevKit kutup eğimi min(80°, |λ|) | 80,0° |
| Güneş yüksekliği (bir yıl, 2 h adım) | -2,5903° … 2,5543° |
| Güneş'in ufkun üstünde olduğu saat oranı | %50,8 |
| grid kuzeyi ↔ gerçek kuzey | 287,33° |

## 3. Karşı-olgu geometrileri: "~30 kat" ölçüldüğünde ne çıkıyor

Araştırma belgesi dik ve yatay panel arasındaki farkı **"~30 kat"** diye tahmin ediyordu. Ölçüm, tek bir sayı olmadığını gösteriyor: oran **pencereye** bağlı, çünkü Güneş'in yüksekliği yıl içinde −2,59°…+2,55° arasında salınıyor ve bazı sinodik aylarda hiç doğmuyor. Aşağıdaki kazançlar her dizinin **kendi en iyi geometrisine** normalize edilmiştir (bkz. § 6), ortalamalar yalnız Güneş'in ufkun üstünde olduğu örnekler üzerinde.

| Pencere | 3 yüzey gövde (serbest başlık) | tek levha 80° izleyen | tek levha 80° sabit K | yatay levha | izleyen ÷ yatay |
|---|---|---|---|---|---|
| 28 Eyl 2026 + 48 h (standart gündüz rotasının epoğu) | 0,999528 | 0,989669 | 0,754571 | 0,030675 | **32,3** |
| 28 Eyl 2026 + bir sinodik ay (29,53 gün) | 0,999710 | 0,988180 | 0,316039 | 0,021065 | **46,9** |
| 1 Eyl 2026 + bir yıl | 0,999737 | 0,987903 | 0,446938 | 0,019320 | **51,1** |

**Okuma:** belgenin "~30 kat"ı yalnız kısa bir gündüz penceresi için doğru. Yıl boyu aydınlık saatlerde oran daha büyük. Tek sayı yazılamaz; pencere ile birlikte yazılır.

### Sinodik ay bazında (13 ay)

| Ay başlangıcı | Güneş üstte | 3 yüzey | 80° izleyen | yatay | oran |
|---|---|---|---|---|---|
| 2026-09-01 | %71,5 | 0,999811 | 0,987603 | 0,017173 | 57,5 |
| 2026-09-30 | %100,0 | 0,999685 | 0,988275 | 0,021755 | 45,4 |
| 2026-10-30 | %100,0 | 0,999567 | 0,988984 | 0,026507 | 37,3 |
| 2026-11-28 | %100,0 | 0,999631 | 0,988538 | 0,023574 | 41,9 |
| 2026-12-28 | %74,9 | 0,999741 | 0,987924 | 0,019413 | 50,9 |
| 2027-01-26 | %46,6 | 0,999874 | 0,987021 | 0,013464 | 73,3 |
| 2027-02-25 | %22,3 | 0,999971 | 0,986008 | 0,007079 | 139,3 |
| 2027-03-26 | %0,0 | 0,000000 | 0,000000 | 0,000000 | — |
| 2027-04-25 | %0,0 | 0,000000 | 0,000000 | 0,000000 | — |
| 2027-05-24 | %0,0 | 0,000000 | 0,000000 | 0,000000 | — |
| 2027-06-23 | %24,0 | 0,999987 | 0,985417 | 0,003580 | 275,3 |
| 2027-07-22 | %52,8 | 0,999911 | 0,986774 | 0,011828 | 83,4 |
| 2027-08-21 | %79,7 | 0,999773 | 0,987814 | 0,018602 | 53,1 |

**Okuma:** oran 37 ile 275 kat arasında geziniyor ve Güneş'in hiç doğmadığı aylarda tanımsız (satırlar "—"). Site11 kutuptan 1,08° uzakta olduğu için Güneş'in yüksekliği azimutla birlikte değişiyor; yatay panelin topladığı `sin e` bu yüzden aya göre 7 kat oynuyor.

### Gerçek aydınlanma serisiyle ağırlıklandırılmış (Site11, tüm hücreler)

| Geometri | Σ aydınlanma × kazanç (hücre·saat) | bugünkünün yüzdesi |
|---|---|---|
| Güneş'e dönük 2-DOF dizi (bugünkü model, g ≡ 1) | 54 636,0 | %100,00 |
| VIPER 3 yüzey, serbest başlık (kataloğun LPR-1/VIPER varsayımı) | 54 614,9 | %99,96 |
| tek levha 80°, Güneş izleyen (LUVMI-M/Yutu-2 varsayımı) | 54 048,6 | %98,92 |
| tek levha 80°, sabit kuzeye bakan | 34 016,8 | %62,26 |
| yatay levha (RoverDevKit'in varsayılanı) | 1 516,9 | %2,78 |

**Okuma:** 48 dilim × 0,50 h, 28 Eyl 2026, gölge modeli `spice_horizon`; sitenin ortalama aydınlık kesri bu pencerede %0,91. Kataloğun varsaydığı iki geometri bugünkü modelin **%98,9–%100**'ünü topluyor — yani C1 varsayılan katalogla rotayı neredeyse hiç değiştirmez. Çarpıcı sayı karşı-olgudadır: yatay bir dizi aynı arazide bugünkünün yalnızca küçük bir kesrini toplar.

## 4. Üç standart 4-B rotada kısıtlı/kısıtsız fark

| Rota | Model | hamle | bekleme | toplam maliyet | varış SOC % | düğüm | ort. kazanç |
|---|---|---|---|---|---|---|---|
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | sun_pointed (varsayılan) | 41 | 0 | 3,445393 | 92,64 | 31 219 | — |
|  | cos_incidence | 41 | 0 | 3,445454 | 92,64 | 31 222 | 0,999613 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | sun_pointed (varsayılan) | 116 | 0 | 7,837081 | 67,42 | 171 117 | — |
|  | cos_incidence | 116 | 0 | 7,837081 | 67,42 | 171 117 | 0,000000 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | sun_pointed (varsayılan) — **HTTP 422** | — | — | — | — | — | — |
|  | cos_incidence — **HTTP 422** | — | — | — | — | — | — |

- **VIPER kısa leg, 30 May 2027, (358,494)→(346,462)** her iki modelde de **422**: `start (358, 494) falls in coarse block (89, 123) at coarsen=4, which is not traversable: at least one fine cell inside it exceeds the slope or thermal limit. Lower coarsen or choose a different start.` — bu C1'den ÖNCE de böyleydi (katalog düzeltmesi 4af6989 VIPER'ın `slope_max_deg`'ini 20°→15° indirdi).

**A2'nin dwell kararlarına etkisi:** "bekleme" sütunu 4-B planlayıcının WAIT kenarlarını sayar — A2'nin dwell kararı tam olarak budur. Araştırma belgesi C1'in bu kararları etkileyeceğini söylüyordu; ölçüm yukarıda.

## 5. Başlık kilitli karşı-olgu (yalnız ölçüm, planlayıcı değişmedi)

Gövdeye monte dizide ψ rover'ın **başlığıdır**. VIPER'ın önünde panel yoktur (ön yüzde sondaj ve navigasyon kameraları var), dolayısıyla doğrudan Güneş'e doğru sürmek dizinin hiçbir yüzünü aydınlatmaz. NASA'nın "sun on corner" sürüş kipinin sebebi budur. Aşağıdaki sayılar planlayıcının seçtiği rotanın adımlarına, o adımın gidiş yönü başlık kabul edilerek yeniden fiyatlanmasıyla elde edildi.

| Rota | adım | serbest başlık ort. | kilitli ort. | kilitli en az | kilitli en çok | sıfır kazançlı adım |
|---|---|---|---|---|---|---|
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 41 | 0,999615 | 0,304732 | 0,250895 | 0,656739 | 0 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 116 | 0,000000 | 0,000000 | 0,000000 | 0,000000 | 116 |


## 6. Modelin normalizasyonu, B1 ve B5

**Normalizasyon neden var:** araştırma belgesi `p_solar_w × max(0, cos i)` öneriyordu. Bu geometriyi **iki kez** sayar — kataloğun 410 W'ı üç yüzeyin toplamı, 450 W'ı ise NASA'nın "on corner", yani zaten en iyi geometrideki değeri. C1 bu yüzden kazancı dizinin kendi en iyi ham değerine böler; tek düz levhada bu bölen 1'dir ve kazanç tam olarak `max(0, cos i)`'ye indirgenir, yani belgenin istediği bağıntı bunun özel hâlidir.

**B1 (kurtarma politikası):** `survival._power_terms` `p_solar_w`'yi `base_w` ve `slope_w`'ye **zıt işaretlerle** gömer; DP'nin kapalı formlu drenajını mümkün kılan da budur. Dilim başına kazanç bu çarpanlamayı bozardı, bu yüzden alan ufku boyunca **en küçük** kazanç tek skaler olarak geçirilir: bir güvenlik sınırı şarj konusunda iyimser değil, muhafazakâr olmalıdır.

**B5 (Monte Carlo):** koşumlar sürekli saatte ilerler, dolayısıyla dilim indeksiyle kazanç okunamaz; `RouteSky` kazanç verildiğinde gölgenin kümülatifinin yanında `∫(1−gölge)·g dt` tablosunu da kurar ve güneş terimi bu integralden okunur. Kazanç verilmediğinde tablo kurulmaz ve koşum bit-eşittir.

## 7. İddia sınırı ve sunum cümlesi

- **İddia:** MODEL, uncalibrated: a geometric factor only. No cell efficiency, array area, dust loss, temperature coefficient, albedo or terrain-reflected light is modelled, and no rover publishes a panel measurement in polar regolith. p_solar_w is read as the array's output in its BEST geometry -- NASA publishes VIPER's as '320W per panel (450W on corner)' and the PIP's 410 W as a three-array total -- so the gain is normalised to that best geometry and never multiplies a published peak by a single-plate cosine. Every profile's panel geometry is an ASSUMPTION carrying a source string that starts with 'assumption:'; the tilt of VIPER's arrays is inferred from NASA's 'port, starboard, and aft surfaces' plus 'Radiators (on top)', and NASA never calls them vertical. g = 1 (panel_model='sun_pointed') is the pre-C1 model, which is Otten's and Lamarre's sun-pointed array -- NOT RoverDevKit's default, which is a horizontal array. RoverDevKit's own Pragyan validation is THEIR result and is quoted, never mixed with a LunaPath measurement. FINALLY, AND THIS IS THE LARGEST REMAINING OPTIMISM: a body-mounted array is catalogued with azimuth_mode 'free_heading', so the applied gain is the maximum over body heading -- the rover is assumed free to turn to the best one, which is NASA's own driving mode but is not what a rover does while driving somewhere. On Site11's daytime route the same array locked to its direction of travel collects 0.305 against 0.9996 free to turn, a factor of 3.3, and the near-no-op result this model reports for the catalogue's geometries is an artefact of that assumption rather than a property of the site. The heading-locked counterfactual is measured in the report; the planner does not price it, because its cost cube is per cell and not per direction.

- **Kapsam:** geometry only: g = sum_k area_k * max(0, cos i_k) / raw_ref, with cos i = sin e cos(beta) + cos e sin(beta) cos(alpha_sun - psi) per face and raw_ref the same sum maximised over panel azimuth and Sun elevation; e and alpha_sun are the SPICE Sun elevation and true-north azimuth at the window centre, one pair per time slice; the illuminated fraction (1 - shadow_ratio) plays RoverDevKit's d_s and is unchanged; g = 0 whenever the Sun is at or below the horizon.

- **Doğru cümle:** "Güneş gelirini artık panel geometrisiyle hesaplıyoruz: geliş açısı (cos i), panel eğimi ve azimut kipi kataloğa girdi. Modelin geometri terimi, NASA'nın VIPER için yayımladığı iki gücü (320 W tek panel, 450 W köşede) %0,57 farkla yeniden üretiyor. Bugüne kadarki model, Otten'ın ve Lamarre'ın açıkça yazdığı 'her zaman Güneş'e dönük dizi' varsayımıydı — ve bizim varsayılan rover'ımızın öyle bir dizisi yok."

- **Yanlış cümle:** "panel modelimizi doğruladık" (Pragyan doğrulaması RoverDevKit'in, bizim değil), "dizi gücünü hesaplıyoruz" (verim ve alan katalogda yok; yalnız geometri çarpanı var) ya da "VIPER'ın panelleri dikey" (NASA bu kelimeyi kullanmıyor; eğim 'port, starboard, aft surfaces' + 'Radiators (on top)' ifadelerinden çıkarımdır).

