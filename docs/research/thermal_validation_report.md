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

Bu künye **ölçülen `.npz` ile karşılaştırıldı** (üçgen sayısı ve enlem aralığı); tutmasaydı rapor yazılmaz, `validate_thermal.py` 2 dönerdi. Önceden iki dosya bağımsız açılıyordu ve künye hiç denetlenmiyordu: meta'yı 1 234 B / 7 üçgen / enlem 11–22° yapıp denedik, bütün sayılar doğru kaldı, sahte künye basıldı ve betik 0 döndü. Artık dönmüyor.

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

**Sayılar bunu kısmen doğruluyor, kısmen çürütüyor.** B'nin sıra korelasyonu A'dan belirgin biçimde daha iyi (0.457 ↔ 0.290) — yani gölge eşlemesi hücreleri **doğru sıraya** sokuyor. B'nin bias'ı ise soğuk yönde A'nınkinin iki katına yakın (-23.19 ↔ -10.38 °C); nedeni aşağıdaki PSR tabanıdır.

**RMSE farkı bir ölçüm değil — eşleşmiş test öyle diyor.** A ile B aynı **49** fasette puanlanıyor, yani soru eşleşmiş bir sorudur; iki ayrı marjinal aralığı yan yana okumak onu yanıtlamaz. Fasetler yeniden örneklenip iki RMSE birlikte hesaplandığında fark **+1.99 °C**, %95 aralığı **[-4.05, +7.48]** — **sıfırı içeriyor**, ve yeniden örneklemelerin yalnızca %76'sında B gerçekten daha kötü çıkıyor. Üstelik işaret örtme eşiğiyle **dönüyor** (≥ %90: -0.21 °C).

Bu yüzden rapor "B'nin RMSE'si A'dan daha kötü" **demiyor** ve o farkın üstüne bir neden kurmuyor. Kurulabilecek tek şey şudur: ölçebildiğimiz yerde ikisi arasında **RMSE farkı yok**, sıralama farkı **var**.

**Karar:** karşılaştırmanın doğru tarafı **B**'dir — planlayıcının okuduğu alan odur ve istatistik eşleşmesi odur. Bu karar RMSE sıralamasına değil, **tanım eşleşmesine** dayanıyor: PRP `temp_max` aydınlanma dâhil bir yıllık maksimumdur, bizde karşılığı `annual_peak_c`'dir. A'nın gölgeyi hiç görmemesi onu daha iyi bir model yapmaz; bu pencerede RMSE'sinin küçük çıkması da ayırt edilebilir bir üstünlük değildir.

---

## 1b. PSR tabanı — ilk kez ölçülebilir hâle geldi

`thermal_model.PSR_ANNUAL_MAX_K` = **90 K (-183.15 °C)**. Kaynağı: thermal_model.PSR_ANNUAL_MAX_K -- mid-point of the 80-110 K annual-maximum band Paige et al. (2010) report for large south-polar PSRs. `annual_peak_c` hiç aydınlanmayan her hücreyi buraya sabitler, yani bu sabit B adayının soğuk kuyruğunu tek başına belirliyor. PRP aynı istatistiği (yüzeyde yıllık maksimum) her faset için taşıdığından, taban **ilk kez** doğrudan kontrol edilebiliyor.

| | Değer |
|---|---|
| Bizim tabanımız | 90 K |
| Penceredeki hiç aydınlanmayan hücre sayısı | 16,253 |
| PRP'nin penceredeki en soğuk `temp_max`'ı (**faset**) | 161.5 K |
| Bizim en soğuk fasetimiz (**aynı destek**: aynı hücreler, faset ort.) | 134.8 K |
| PRP'nin enlem şeridindeki en soğuk `temp_max`'ı | 40.2 K |
| PRP'nin 88°S kutup tarafındaki en soğuğu | 28.4 K |
| 88°S kutup tarafında tabanımızın **altında** kalan fasetler | %16.30 |
| 80°S kutup tarafında tabanımızın altında kalanlar | %3.36 |
| 80°S kutup tarafında PRP `temp_max` aralığı | 26.8 – 348.7 K |

**İki yönlü bir bulgu, ve ikisi de yazılmalı:**

1. **Site11 penceresinde taban fazla soğuk — ama aynı destekte, 71 K değil 27 K.** Ham 90 K'yi PRP'nin penceredeki en soğuk fasetiyle (161.5 K) yan yana koymak **benzemeyen şeyleri** karşılaştırmaktır ve bu raporun §1'de kendi koyduğu kuralı çiğner: 90 K bir **5 m hücre** değeri, 161.5 K ise bütün bir **~0.130 km² fasetin** modellenmiş yıllık maksimumu. Ölçüldü: o en soğuk faset, penceredeki hücrelerimizin yalnızca **%0.2**'i kadarında hiç-aydınlanmayan alan içeriyor — yani bir PSR faseti **değil**. Karşılaştırılan fasetlerde hiç-aydınlanmayan oranın medyanı %0.4, yarıdan fazlası karanlık olan faset sayısı 1, tamamı karanlık olan 0. Kendi soğuk kuyruğumuzu **aynı desteğe** indirince (aynı hücreler, aynı fasetler, ortalama) en soğuk fasetimiz **134.8 K** çıkıyor; dürüst fark budur. Penceredeki 16,253 hiç-aydınlanmayan hücre (0.406 km², pencerenin %6.5'i) 90 K'ye çakılı ve B'nin soğuk kuyruğunu belirliyor; ama 161.5 K bunun **ölçüsü değil** — o, 544 m'lik örgünün bu pencerede hiçbir kalıcı gölgeli faset çözemediğini söylüyor.
2. **Bölge genelinde taban fazla sıcak.** 88°S'nin kutup tarafındaki fasetlerin **%16.30**'i 90 K'nin altında, en soğuğu 28.4 K. Yani tek bir sabit taban, PRP'nin 27–349 K'lik gerçek yayılımını temsil edemiyor — Paige'in 80–110 K bandının ortası bir **bant ortası**ydı, bir hücre değeri değil.

**C5 bu sabiti DEĞİŞTİRMEZ.** Değiştirmek kalibrasyondur: `annual_peak_c`'nin soğuk kuyruğunu, `THERMAL_MIN_TRAVERSABLE_C` kapısını, maliyet gridini ve her rotayı oynatır. Ölçüldü, yazıldı, dokunulmadı.

---

## 2. LUT'un kendisi (enlem eşlenmiş)

Pencerenin kendi enlem şeridinde (-88.9715° … -88.8685°) tüm boylamlarda **5,010** PRP üçgeni var. Enlemin eşlenmesi zorunlu: −88,9°'de Güneş'in maksimum yüksekliği ~0,5° ve enlemle hızla değişiyor, geniş bir şerit tablomuzu başka bir aydınlanmaya karşı koyardı.

LUT `thermal_grid.npy`'den geri kazanıldı: 205/208 kutu dolu, düz hücre tepesi **-146.37 °C** (C6'nın heat1d ölçümü −146,4 °C ile uyuşuyor). 0 kutuda birden fazla değer var ve geri kazanılan tablo eğim/bakı gridlerine yeniden uygulandığında hücrelerin **%0.00**'i tutmuyor. Yani gönderilen termal grid, belgelenmiş en-yakın-kutu kuralıyla **bit-eşit olarak yeniden üretiliyor**.

**Bunun için doğru çerçevede binlemek gerekiyor, ve bu bir düzeltmedir.** `make_thermal_grid`, heat1d'e göndermeden önce bakıyı grid kuzeyinden gerçek kuzeye çeviriyor (`ephemeris.grid_azimuth_to_true_azimuth`), yani diskteki hücre değeri `table[eğim, bakı − Δ]`. Bu raporun ilk sürümü tabloyu **ham** `aspect_grid` üzerinde binliyordu; ölçülen fark:

| Binleme çerçevesi | Uyuşmazlık | Çok-değerli kutu |
|---|---|---|
| `aspect_grid` (ilk sürüm) | %22.96 | 182 |
| `aspect_grid − Δ` (Δ = 287.3279°) | **%0.00** | **0** |

İlk sürümün «nedeni **saptanmadı**» dediği %22.96 buydu: hata boru hattında değil, bu betikteydi. Ham çerçevede binlemek her tablo girdisini iki komşu bakı kutusuna yayıyor ve geriye **Δ kadar dönmüş** bir tablo veriyor — sonra o tablo PRP'nin gerçek-kuzey bakısıyla örnekleniyordu, yani §2b iki ayrı çerçeveyi karşılaştırıyordu.

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
| 18.5–20.8° | 212 | 11.92 | 3.71 |
| 20.8–23.1° | 174 | 21.86 | 14.36 |
| 23.1–25.4° | 91 | 30.26 | 24.04 |
| 25.4–27.7° | 38 | 33.89 | 32.65 |
| 27.7–30.0° | 13 | 35.52 | 40.54 |

Eğim kutuları arası Spearman: **1.000**.

### 2b. Bakı çözümlenmiş (çerçeve doğrulanmış)

**Tek satır yayımlanmıyor, çünkü burada iki popülasyon var.** heat1d LUT'u tek bir fasetin eğim/bakısından yıllık tepe üretir; faset içi gölgelenme görmez. Tablonun küresel minimumu **-146.37 °C** (126.8 K), yani bundan soğuk hiçbir fasete model **yapısal olarak** ulaşamaz: oradaki artık kurgu gereği pozitiftir ve modelin başka yerdeki uyumu hakkında hiçbir şey söylemez.

| Popülasyon | RMSE (°C) | RMSE %95 GA¹ | Bias (°C) | MAE (°C) | Spearman | n |
|---|---|---|---|---|---|---|
| havuzlanmış (yalnız bütünlük için) | 53.87 | 52.8 – 55.0 | -4.36 | 39.07 | 0.829 | 4,989 |
| modelin üretebildiği arazi | 29.67 | 29.1 – 30.3 | -23.46 | 26.61 | 0.944 | 4,328 |
| modelin üretemediği arazi | 127.05 | 120.6 – 134.3 | 120.69 | 120.69 | 0.321 | 661 |

Şeritteki fasetlerin **%13.2**'i (661 faset) LUT'un tabanından soğuk ve toplam kare hatanın **%73.7**'i oradan geliyor. İki zıt işaretli bias havuzlandığında -4.36 °C çıkıyor ve bu **"neredeyse yansız"** diye okunur — oysa ölçülen şey şudur: **karşılaştırılabilir arazide model 23.5 °C fazla soğuk**, kalanında ise o değeri üretemiyor. Havuzlanmış satır, okur kendisi hesaplayacağı için duruyor; tek başına **asla** durmuyor.

**¹ Bu sütundaki ki-kare aralığı burada geçersizdir, ve yerine konan ölçülmüştür.** `rmse_ci95` artıkların bağımsız ve normal olmasını şart koşar; `1/√n` daralmasını satın alan şey bağımsızlıktır. Şerit bir halkadır, komşu fasetler aynı araziyi paylaşır: boylam boyunca özilinti lag-1: +0.68, lag-5: +0.73, lag-20: +0.63, lag-50: +0.41, lag-200: +0.04.

| Aralık | 95% GA (°C) | Genişlik |
|---|---|---|
| Ki-kare (`rmse_ci95`) | 52.84 – 54.95 | 2.11 |
| **Hareketli blok bootstrap, 50 blok** | **44.14 – 64.55** | **20.41** |
| Aynısı, 25 blok (daha muhafazakâr) | 41.73 – 66.31 | 24.58 |
| **Kontrol:** aynı bloklama, **karıştırılmış** artıklar | 52.45 – 55.35 | 2.89 |

Kontrol satırı bu tablonun tek anlamlı satırıdır: aynı değerler, aynı bloklama, bağımsızlık bozulunca genişlik ki-kareye geri dönüyor. Demek ki genişleme **yöntemden değil, gerçek uzamsal bağımlılıktan**. Özilinti ~200 fasette sıfıra indiğine göre bağımsız uzanım sayısı 4,989 değil kabaca 24; `1/√n` daralması o n'e göre okunmalı. Yayımlanan sayı blok bootstrap aralığıdır.

**Çerçeve tanısı — ve bir düzeltmenin kaydı.** Bakıya sabit bir ofset eklenip RMSE yeniden hesaplanıyor (5° adım). Tablo doğru çerçevede geri kazanıldığına göre beklenen sonuç **sıfırda minimum**dur, ve çıkan budur:

| | Ofset | RMSE (°C) |
|---|---|---|
| Ofsetsiz | 0° | 53.873 |
| Taramanın en iyisi | 5° | 53.866 |
| **Kontrol:** ham çerçeveli tablo, taramanın en iyisi | **295°** | 53.866 |
| Çerçeve dönmesi Δ | 287.33° | — |

Minimum bir tarama adımı içinde sıfırda ve dönmenin kazandırdığı 0.007 °C, taramanın 53.9–58.7 °C'lik genliği yanında yoktur. **Kontrol satırı bu bölümün bulgusudur:** ham çerçevede geri kazanılmış tablo taranınca minimum 295°'ye, yani Δ = 287.33°'ye oturuyor. Bu raporun ilk sürümü o minimumu «C5'in bulgusu» diye yayımlamış ve `make_aspect_grid`'in grid-kuzeyi bakısını heat1d'e ham gönderdiğine yormuştu. **Yanlış atıftı:** boru hattı dönüşümü zaten uyguluyor (yukarıdaki %0.00 birebir yeniden üretim bunun kanıtı), tarama ise bu betiğin kendi geri kazanım hatasını ölçüyordu. Sayısal uyum tesadüf değildi — tam olarak Δ'ydı — ama işaret ettiği kusur **doğrulayıcıdaydı**.

Bu bir **tanıdır, bir uydurma değildir**: hiçbir parametre bu sayıya göre değiştirilmemiştir.

**Planlayıcının bakı çerçevesinde düzeltilecek bir şey yok.** Sevk edilen `thermal_grid.npy`, `table[eğim, bakı − Δ]`'dan **birebir** yeniden üretiliyor; yani heat1d gerçek-kuzey bakısını almış. Düzeltilen şey bu raporun kendi geri kazanım çerçevesiydi; hiçbir grid, hiçbir maliyet, hiçbir rota değişmedi.

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
- **Havuzlanmış bir bias tek başına yayımlanmaz.** Modelin üretemeyeceği arazi ayrı satırdadır; §2b'de iki popülasyonu havuzlamak −4,36 °C veriyor ve bu "neredeyse yansız" diye okunurdu.
- **Güven aralıkları yöntemiyle birlikte okunur.** Ki-kare aralığı yalnız bağımsız artıklar için geçerlidir; uzamsal ilintili şeritte hareketli blok bootstrap yayımlanır ve yanına onu doğrulayan **kontrol** konur. İki RMSE aynı örnek üzerindeyse fark **eşleşmiş** testle sınanır, iki marjinal aralık yan yana okunarak değil.
- Termal katmanımız hâlâ **MODEL / UNCALIBRATED**. Bu rapor ona bir hata bandı kazandırır, etiketini yükseltmez.
- Hiçbir rota sayısı değişmedi; C5 planlayıcıya dokunmaz.
- Uyum kötü çıktığı yerde kötü hâliyle yayımlanmıştır; model Diviner'a uydurulmamıştır.

*Ölçüm süresi: 0.1 dk.*
