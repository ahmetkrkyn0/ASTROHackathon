# Diviner PRP termal doğrulama raporu (C5)

*Üretim: `python scripts/validate_thermal.py` (`--json` ham çıktı, `--from-json` ölçmeden yeniden render).*

## Ne neye karşı ölçüldü

**Referans:** `LRO-L-DLRE-5-PRP-V2.0` — Paige et al., LRO DLRE LEVEL 5 PRP V2.0, NASA Planetary Data System, LRO-L-DLRE-5-PRP-V2.0, 2018.

> PDS kataloğu bu ürünü şöyle tanımlıyor: *"thermal model fits to first mapping year Diviner polar observations"*, işlem düzeyi *"PRPs are CODMAC Level 5 (NASA Level 4)"*.

Yani PRP **ham bir ölçüm değil**, Diviner gözlemlerine oturtulmuş bir **modeldir**. Bu karşılaştırma MODEL ↔ MODEL-ÖLÇÜME-OTURTULMUŞ'tur; "ölçüme karşı doğrulandı" ile aynı iddia değildir. Hiçbir katmanın `layer_validity` etiketi bu rapor yüzünden yükselmez.

| | Bizim | Diviner PRP |
|---|---|---|
| Kaynak | LunaPath heat1d LUT (MODEL) | DERIVED |
| Çözünürlük | 5 m/px | ~544 m (üçgen kenarı) |
| Topografya | Site11 5 m LOLA | Kaguya laser altimeter DEM (Araki et al., Science 323, 897, 2009) -- a different topography from our 5 m/px LOLA Site11 grid. |
| İstatistik | yıllık tepe | `temp_max` — *The annual maximum temperature (K), calculated at the surface* |

PRP'nin ikinci sıcaklık sütunu `temp_avg` **yüzeyin 2 cm altında** (*The annual average temperature (K), calculated at a depth of 2 cm below the surface*) hesaplanmıştır; bir yüzey alanı değildir ve bu yüzden karşılaştırmaya girmez. `ice_depth` modellenmiş bir üründür, o da girmez.

Ham dosya: **604,800,210 B**, SHA-256 `393deaa5d8925d45bb2ed608f937a824f5eae029c2558aad1d2da8206b83a62d`, 2,880,000 üçgen, enlem -89.992…-75.901°.

---

## 1. Site11 penceresi

Pencerede **50** PRP üçgeninin merkezi var; kenardan taşanlarla birlikte **71** üçgen bizim hücrelerimizi örtüyor (üçgen başına medyan 5151 hücre; 250,000/250,000 hücre atandı).

**Bu n küçüktür ve öyle okunmalıdır.** 2,5 km × 2,5 km'lik pencerede ~544 m'lik bir ürün bu kadar örnek verir; RMSE'nin %95 güven aralığı aşağıda ayrı sütunda duruyor ve geniştir. Karşılaştırma **kabanın çözünürlüğünde** yapıldı: bizim 5 m'lik gridimiz her üçgenin ayak izinde toplulaştırıldı, PRP 5 m'e interpolasyon **yapılmadı** (yapılsaydı 50 ölçüm 250 000 sahte örneğe dönerdi).

**Kenardan kırpılan fasetler ölçümden çıkarıldı.** Bir Diviner fasetinin `temp_max`'ı **bütün** üçgenini (~0,128 km²) anlatır. Pencere kenarında kırpılan bir faset bize yalnız kendi diliminden görünür ve bizim o dilim üzerindeki ortalamamızı onların tüm üçgen için verdiği değere karşı koymak **benzemeyen şeyleri** karşılaştırmaktır. Ölçüldü: hücrelerimizi örten 71 fasetin **22**'i yarıdan az örtülüyor (en küçüğü %2.0), ve bunları dâhil etmek uyumu **olduğundan iyi** gösteriyor (aşağıdaki duyarlılık tablosu). Bu yüzden ana sayı **örtme ≥ %50** süzgecinden geçen **49** fasetle hesaplandı; süzgeçsiz ve daha sıkı hâlleri de yayımlandı.

PRP `temp_max` penceredeki aralık: -111.66 … 16.96 °C (medyan -41.12).

### Ortalama toplulaştırma (**dürüst eşdeğer**) — örtme ≥ %50

| Aday | RMSE (°C) | RMSE %95 GA | Bias (°C) | MAE (°C) | Spearman | n |
|---|---|---|---|---|---|---|
| `A_thermal_sunlit_peak` | 37.44 | 31.3 – 46.7 | -10.38 | 30.73 | 0.290 | 49 |
| `B_thermal_annual_peak` | 39.43 | 32.9 – 49.1 | -23.19 | 32.20 | 0.457 | 49 |
| `C_thermal_min_equilibrium` | 72.11 | 60.2 – 89.9 | -66.36 | 66.71 | 0.467 | 49 |

### Maksimum toplulaştırma (karşılaştırma için) — örtme ≥ %50

| Aday | RMSE (°C) | RMSE %95 GA | Bias (°C) | MAE (°C) | Spearman | n |
|---|---|---|---|---|---|---|
| `A_thermal_sunlit_peak` | 70.78 | 59.1 – 88.2 | 63.49 | 63.49 | 0.147 | 49 |
| `B_thermal_annual_peak` | 69.58 | 58.1 – 86.7 | 61.69 | 61.69 | 0.131 | 49 |
| `C_thermal_min_equilibrium` | 28.86 | 24.1 – 36.0 | -2.54 | 24.26 | 0.291 | 49 |

### Örtme eşiğine duyarlılık (ortalama toplulaştırma)

| Eşik | Aday | RMSE (°C) | Bias (°C) | Spearman | n |
|---|---|---|---|---|---|
| ≥ %0 | `A_thermal_sunlit_peak` | 34.00 | -10.39 | 0.488 | 71 |
| ≥ %0 | `B_thermal_annual_peak` | 35.52 | -19.23 | 0.629 | 71 |
| ≥ %0 | `C_thermal_min_equilibrium` | 68.40 | -63.12 | 0.646 | 71 |
| ≥ %50 **←** | `A_thermal_sunlit_peak` | 37.44 | -10.38 | 0.290 | 49 |
| ≥ %50 **←** | `B_thermal_annual_peak` | 39.43 | -23.19 | 0.457 | 49 |
| ≥ %50 **←** | `C_thermal_min_equilibrium` | 72.11 | -66.36 | 0.467 | 49 |
| ≥ %90 | `A_thermal_sunlit_peak` | 40.35 | -14.22 | 0.271 | 38 |
| ≥ %90 | `B_thermal_annual_peak` | 40.14 | -23.42 | 0.423 | 38 |
| ≥ %90 | `C_thermal_min_equilibrium` | 73.33 | -67.38 | 0.448 | 38 |

**Toplulaştırma neden ortalama?** PRP'nin üçgen değeri tek bir **fasetin** (tek eğim, tek bakı) modellenmiş yıllık maksimumudur — faset içindeki topografyanın maksimumu değil. Bizim 5 m hücrelerimizin ortalaması bu tanımın karşılığıdır; maksimum toplulaştırma karşılaştırma için verilmiştir.

**Üç aday ne demek:**

- `A_thermal_sunlit_peak` — `thermal_grid.npy`, olduğu gibi: yalnız geometri, gölge görmez.
- `B_thermal_annual_peak` — `annual_peak_c(sunlit_peak, shadow_ratio)`: gölge eşlenmiş yıllık tepe, **planlayıcının gerçekten kullandığı alan**.
- `C_thermal_min_equilibrium` — soğuk uç **dengesi**; bir maksimum değildir, PRP `temp_max`'ın karşılığı olması beklenmez ve tam da bu yüzden ölçülmüştür.

### Hangisi doğru eşleşme? (gerekçesiyle)

**Kavramsal olarak B.** PRP `temp_max` gerçek bir topografya üzerinde, aydınlanma dâhil hesaplanmış yıllık maksimumdur; bizde bunun karşılığı gölge eşlenmiş `annual_peak_c`'dir, yani B. A gölgeyi hiç görmez, C ise bir maksimum bile değildir.

**Sayılar bunu kısmen doğruluyor, kısmen çürütüyor.** B'nin sıra korelasyonu A'dan belirgin biçimde daha iyi (0.457 ↔ 0.290) — yani gölge eşlemesi hücreleri **doğru sıraya** sokuyor. Ama B'nin RMSE'si A'dan **daha kötü** (39.43 ↔ 37.44 °C) ve soğuk yönde iki katına yakın bias taşıyor (-23.19 ↔ -10.38 °C). Nedeni aşağıdaki PSR tabanıdır, ve bu bir kusurdur, bir tercih değil.

**Karar:** karşılaştırmanın doğru tarafı **B**'dir — planlayıcının okuduğu alan odur ve istatistik eşleşmesi odur. A'nın daha küçük RMSE'si, gölge eşlemesinin **yönünü** değil, PSR tabanının **değerini** suçlar: gölgeyi hiç uygulamamak, bu pencerede yanlış bir tabanla uygulamaktan tesadüfen daha az hata veriyor. Doğru okuma "A daha iyi model" değil, "B'nin soğuk kuyruğu fazla soğuk"tur.

---

## 1b. PSR tabanı — ilk kez ölçülebilir hâle geldi

`thermal_model.PSR_ANNUAL_MAX_K` = **90 K (-183.15 °C)**. Kaynağı: thermal_model.PSR_ANNUAL_MAX_K -- mid-point of the 80-110 K annual-maximum band Paige et al. (2010) report for large south-polar PSRs. `annual_peak_c` hiç aydınlanmayan her hücreyi buraya sabitler, yani bu sabit B adayının soğuk kuyruğunu tek başına belirliyor. PRP aynı istatistiği (yüzeyde yıllık maksimum) her faset için taşıdığından, taban **ilk kez** doğrudan kontrol edilebiliyor.

| | Değer |
|---|---|
| Bizim tabanımız | 90 K |
| Penceredeki hiç aydınlanmayan hücre sayısı | 16,253 |
| PRP'nin penceredeki en soğuk `temp_max`'ı | 161.5 K |
| PRP'nin enlem şeridindeki en soğuk `temp_max`'ı | 40.2 K |
| PRP'nin 88°S kutup tarafındaki en soğuğu | 28.4 K |
| 88°S kutup tarafında tabanımızın **altında** kalan fasetler | %16.30 |
| 80°S kutup tarafında tabanımızın altında kalanlar | %3.36 |
| 80°S kutup tarafında PRP `temp_max` aralığı | 26.8 – 348.7 K |

**İki yönlü bir bulgu, ve ikisi de yazılmalı:**

1. **Site11 penceresinde taban fazla soğuk.** PRP'nin penceredeki en soğuk faseti 161.5 K; bizim tabanımız 90 K, yani yaklaşık **71 K daha soğuk**. Penceredeki 16,253 hiç-aydınlanmayan hücre bu tabana çakıldığı için B adayının bias'ı A'nınkinin iki katına çıkıyor.
2. **Bölge genelinde taban fazla sıcak.** 88°S'nin kutup tarafındaki fasetlerin **%16.30**'i 90 K'nin altında, en soğuğu 28.4 K. Yani tek bir sabit taban, PRP'nin 27–349 K'lik gerçek yayılımını temsil edemiyor — Paige'in 80–110 K bandının ortası bir **bant ortası**ydı, bir hücre değeri değil.

**C5 bu sabiti DEĞİŞTİRMEZ.** Değiştirmek kalibrasyondur: `annual_peak_c`'nin soğuk kuyruğunu, `THERMAL_MIN_TRAVERSABLE_C` kapısını, maliyet gridini ve her rotayı oynatır. Ölçüldü, yazıldı, dokunulmadı.

---

## 2. LUT'un kendisi (enlem eşlenmiş)

Pencerenin kendi enlem şeridinde (-88.9715° … -88.8685°) tüm boylamlarda **5,010** PRP üçgeni var. Enlemin eşlenmesi zorunlu: −88,9°'de Güneş'in maksimum yüksekliği ~0,5° ve enlemle hızla değişiyor, geniş bir şerit tablomuzu başka bir aydınlanmaya karşı koyardı.

LUT `thermal_grid.npy`'den geri kazanıldı: 205/208 kutu dolu, düz hücre tepesi **-146.37 °C** (C6'nın heat1d ölçümü −146,4 °C ile uyuşuyor). 182 kutuda birden fazla değer var: geri kazanılan tablo eğim/bakı gridlerine yeniden uygulandığında hücrelerin **%22.96**'i tutmuyor, en büyük fark **5.89 °C** ve farklar hep **komşu kutu** değerleri. Yani gönderilen termal grid, diskteki eğim/bakı gridlerinden belgelenmiş en-yakın-kutu kuralıyla **bit-eşit olarak yeniden üretilemiyor**. Ölçüldü ve yazıldı; nedeni **saptanmadı** (eğim/bakı gridlerinin termal gridden sonra yeniden üretilmiş olması bu büyüklükle tutarlı olurdu, ama bu bir hipotezdir, ölçüm değil). Aşağıdaki RMSE'lerin yanında bu ≤6 °C'lik kutu-kenarı gürültüsü küçüktür.

PRP faset eğimi: 0.08° … 35.30° (medyan 9.89°); %0.14'i LUT'un 30° tavanının üstünde ve orada kırpılıyor.

### 2a. Bakı marjinalleştirilmiş (referans çerçevesinden bağımsız)

| Eğim aralığı | n | PRP `temp_max` ort. (°C) | Bizim LUT (bakı ort., °C) |
|---|---|---|---|
| 0.0–2.3° | 423 | -124.56 | -146.37 |
| 2.3–4.6° | 556 | -95.06 | -123.79 |
| 4.6–6.9° | 703 | -77.14 | -95.23 |
| 6.9–9.2° | 639 | -72.51 | -72.10 |
| 9.2–11.5° | 638 | -50.50 | -52.67 |
| 11.5–13.8° | 613 | -37.54 | -35.90 |
| 13.8–16.2° | 516 | -19.38 | -21.16 |
| 16.2–18.5° | 387 | -9.57 | -8.06 |
| 18.5–20.8° | 212 | 11.92 | 3.83 |
| 20.8–23.1° | 174 | 21.86 | 14.41 |
| 23.1–25.4° | 91 | 30.26 | 23.99 |
| 25.4–27.7° | 38 | 33.89 | 32.74 |
| 27.7–30.0° | 13 | 35.52 | 40.40 |

Eğim kutuları arası Spearman: **1.000**.

### 2b. Bakı çözümlenmiş (çerçeve varsayımı açık)

| Aday | RMSE (°C) | RMSE %95 GA | Bias (°C) | MAE (°C) | Spearman | n |
|---|---|---|---|---|---|---|
| `heat1d LUT (gölgesiz)` | 55.30 | 54.2 – 56.4 | -4.35 | 40.06 | 0.811 | 5,009 |

**Çerçeve uyarısı — C5'in bulgusu.** heat1d'in `slope_az` parametresi kurulu paketin docstring'inde *"clockwise from north (0 = N, pi/2 = E)"*, yani **gerçek** yerel kuzeye göre tanımlı. Bizim `make_aspect_grid`'imiz (`lunapath/src/process_lunar_data.py:275`) açıyı **grid** koordinatlarında hesaplıyor. Polar stereografik projeksiyonda bu ikisi meridyen yakınsaması kadar ayrışır ve pencere boylamında (−72,67°) bu ~72,7° eder — 22,5°'lik bakı kutularında ~3,2 kutu.

Tanısal tarama (5° adımlarla, bakıya sabit bir ofset eklenip RMSE yeniden hesaplanarak):

| | Ofset | RMSE (°C) |
|---|---|---|
| Ofsetsiz | 0° | 55.30 |
| **Taramanın en iyisi** | **295°** | **53.87** |
| Meridyen yakınsaması, + dalı | 72.7° | — |
| Meridyen yakınsaması, − dalı | 287.3° | — |

Yakınsamanın **büyüklüğü** geometriden öngörülüyor (72.67°); **işareti** CRS'in eksen konvansiyonuna bağlı olduğu için iki dal da yazıldı ve hangisi olduğunu taramanın söylemesine izin verildi. Minimum 287.3° dalına **7.7°** uzakta (öteki dala 137.7°), yani LUT'un 22,5°'lik bakı kutusundan daha yakın. Çerçeve uyuşmazlığı **gerçek ve öngörülen büyüklükte**. Ama kazanç küçük: 55.30 → 53.87 °C (%2.6), ve tüm tarama yalnızca 53.9–58.7 °C arasında geziniyor. Toplam uyuşmazlığın çoğunu bakı çerçevesi **açıklamıyor** (gölgeleme, topografya ve model farkları duruyor).

Bu bir **tanıdır, bir uydurma değildir**: hiçbir parametre bu sayıya göre değiştirilmemiştir.

**C5 bunu düzeltmez.** Düzeltmek `aspect_grid`'i, dolayısıyla `thermal_grid`'i, dolayısıyla maliyet gridini ve her rotayı değiştirir; bu bir kalibrasyon/hata düzeltmesidir ve ayrı bir özelliktir. C5 ölçer, adlandırır, yazar.

---

## 3. Soğuk tuzak alanı — yayımlanmış bir sayının yeniden türetilmesi

> Williams, Greenhagen, Paige, Schorghofer, Sefton-Nash, Hayne, Lucey, Siegler, Aye, Seasonal Polar Temperatures on the Moon, JGR Planets 124, 2019, doi 10.1029/2019JE006028
>
> *"real cold traps poleward of 80S total 1.3e4 km2 (peak T < 110 K)"*

PRP her üçgenin üç köşesini de taşıdığı için alan `½|(v₂−v₁)×(v₃−v₁)|` ile doğrudan hesaplanabilir. Yani hedef sayı onların, **aritmetik bizim**.

| | Değer |
|---|---|
| Williams'ın yayımladığı (ONLARIN) | 13,000 km² |
| PRP v2'den bizim türettiğimiz | **14,749.1 km²** |
| Fark | **13.4 %** |
| Soğuk üçgen sayısı | 112,757 |
| 80°S'nin kutup tarafındaki üçgen sayısı | 2,261,956 |
| 80°S'nin kutup tarafındaki toplam alan | 292,387 km² |
| Ölçüt | `temp_max` < 110 K, enlem ≤ -80° |

**Künye farkı:** Williams' figure is theirs, from their 240 m/px seasonal maps. The derived figure sums PRP v2 triangle areas (Paige 2010 model on a ~544 m Kaguya mesh). Two different published products, so a difference is informative about the products, not an error of ours.

---

## 4. Gece minimumu (Williams 240 m/px)

**Durum: `unavailable`.**

Williams et al. (2019) 240 m/px seasonal min maps are not on disk. The Diviner PRP cannot stand in: its columns are an annual MAXIMUM at the surface and an annual AVERAGE at 2 cm depth, neither of which is a seasonal minimum.

**İstatistik boşluğu:** Williams 'min' = seasonal minimum of surface temperature; our thermal_min = radiative equilibrium under time-averaged insolation; heat1d's nightly transient floor is a third quantity again. Naming which is compared is a precondition for a number, not a caveat on one.

---

## İddia sınırı

- PRP'nin ve Williams'ın sayıları **onlarındır**; bu raporda alıntı olarak, künyeleriyle durur.
- RMSE / bias / Spearman **bizimdir**; hangi alan, hangi çözünürlük, hangi n ile hesaplandığı her tabloda yazılıdır.
- Termal katmanımız hâlâ **MODEL / UNCALIBRATED**. Bu rapor ona bir hata bandı kazandırır, etiketini yükseltmez.
- Hiçbir rota sayısı değişmedi; C5 planlayıcıya dokunmaz.
- Uyum kötü çıktığı yerde kötü hâliyle yayımlanmıştır; model Diviner'a uydurulmamıştır.

*Ölçüm süresi: 0.1 dk.*
