# D5 — Ağırlık simpleksi taraması ve baskın-olmayan rotalar: Site11 ölçümü

**Üretildi:** `scripts/pareto_front_report.py` · pencere 500×500, 5,0 m/px · tohum 20260916 · ölçüm süresi 4,1 dk

*(`--json` ham çıktı, `--from-json` ölçmeden yeniden render.)*

---

## 1. Kaynaklar ne diyor (alıntı)

Aşağıdaki cümleler **onlarındır**; hiçbiri bizim ölçüm tablomuza konmadı ve hiçbiri için "biz doğruladık" denmedi.

> Boyd, Vandenberghe -- Convex Optimization, Cambridge University Press, 2004, sect. 4.7.4 'Scalarization', pp. 178-180
>
> *"The value f0(x3) is Pareto optimal, but cannot be found by scalarization"*
>
> *"for convex problems the method of scalarization yields all Pareto optimal points"*

> Das, Dennis -- A closer look at drawbacks of minimizing weighted sums of objectives for Pareto set generation in multicriteria optimization problems, Structural Optimization 14(1):63-69, 1997
>
> *"it is well-known that this method succeeds in getting points from all parts of the Pareto set only when the Pareto curve is convex"*
>
> *"even for convex Pareto curves, an evenly distributed set of weights fails to produce an even distribution of points from all parts of the Pareto set"*

> Konen, Stiglmayr -- On Supportedness in Multi-Objective Combinatorial Optimization, arXiv:2501.13842v2, 2025, Definition 1.11
>
> *"Unsupported efficient solutions are efficient solutions that are not optimal solutions of P_lambda for any lambda"*
>
> *"unsupported non-dominated points cannot be computed through a weighted sum scalarization"*

**Terminoloji.** Ulaşılabilen çözümlere *supported*, ulaşılamayanlara *unsupported* denir. "Duality gap" bu literatürün terimi **değildir** ve bu raporda kullanılmaz.

> Richter, Kolvenbach, Valsecchi, Hutter -- Multi-Objective Global Path Planning for Lunar Exploration With a Quadruped Robot, iSpaRo 2024, arXiv:2406.16376 (MIT)
>
> *"We introduce weights between the objectives, which can be adapted to achieve a variety of optimal paths. In order to find the best of these paths, a tool for statistical path analysis is presented."*

**Doğrudan emsal.** ETH'nin `setup_file.py`'si ağırlıkları `ALPHA + BETA + GAMMA = 1` ile sabitliyor — bizimkiyle aynı simpleks — ve tek bir skaler üzerinde A* koşuyor. Yani D5'in ucuz yolu ETH'nin yöntemiyle **aynı yöntemdir**, aynı sınırla birlikte.

> Lavin -- A Pareto Front-Based Multiobjective Path Planning Algorithm, arXiv:1505.05947, 2015
>
> *"selection of parameters is difficult because small perturbations in the weights can lead to very different solutions"*

**Kaynakta bulunan uyumsuzluk (birinci elden okundu).** Bu makale, adının aksine, bir **rota cephesi üretmiyor**: her genişletme adımında açık listenin baskın-olmayanlarını hesaplayıp hemen tek düğüme indiriyor ve *"resulting in a single, optimal path"* diyor. Buradaki atıf yalnızca yukarıdaki **ağırlık duyarlılığı** iddiası içindir; o iddiayı da kendi arazimizde biz ölçüyoruz. (Makinece okunan hâli `app.pareto.PARETO_QUOTED['lavin_2015']['correction']`.)

---

## 2. Dört senaryo — kaç ağırlık vektörü, kaç farklı rota, kaç baskın-olmayan

Her senaryoda **24 rastgele ağırlık vektörü + rover'ın kendi varsayılanı**, 4-simpleksten tekdüze çekilmiş (tohum 20260916). Rotalar **hücre dizisine** göre tekilleştirildi; her istatistik **farklı rotalar** üzerinden.

| senaryo | rover | start → goal | vektör | **farklı rota** | **baskın-olmayan** | vektör/rota | ms/örnek |
|---|---|---|---|---|---|---|---|
| LPR-1 gunduz | `lpr_1` | (358,494) → (206,426) | 25 | **17** | **1** | 1,47 | 240 |
| LPR-1 Ay gecesi | `lpr_1` | (186,34) → (494,450) | 25 | **24** | **1** | 1,04 | 1062 |
| VIPER standart | `nasa_viper` | (358,494) → (206,426) | 25 | **21** | **1** | 1,19 | 265 |
| VIPER kisa leg | `nasa_viper` | (358,494) → (346,462) | 25 | **15** | **2** | 1,67 | 193 |

**Senaryolar ayrı ayrı sunuluyor.** Farklı rover profillerini ya da farklı aydınlanma koşullarını tek bir cepheye havuzlamak, karşılaştırılamayan şeyleri karşılaştırmak olurdu.

## 3. Cephe neden bu kadar küçük

### 3a. Dördüncü eksen ölü

`max_thermal_risk`, doygun bir alanın rota boyunca **maksimumu**. Geçilebilir hücrelerde `f_thermal` ölçümü:

| rover | geçilebilir hücre | `f_thermal ≥ 0,99` | medyan |
|---|---|---|---|
| `lpr_1` | 210 063 | %72,7 | 0,9994 |
| `nasa_viper` | 161 793 | %65,2 | 0,9990 |

Sonuç: hedeflerin biri çoğu senaryoda **tek bir değer** alıyor. Sabit bir eksen hiçbir çifti ayıramaz, yani "dört hedefli cephe" aslında üç hedeflidir. Yanıt bunu `constant_objectives` ve `effective_objectives` ile açıkça söylüyor — bu bir keşif değil, yukarıdaki doygunluğun yeniden ifadesidir.

### 3b. Kalan eksenler aynı sıralamayı veriyor

Spearman, **farklı rotalar** üzerinden (ham örnekler üzerinden hesaplamak, aynı rotayı onu bulan her vektör için bir kez sayardı):

| senaryo | n (farklı rota) | etkin hedef | saat~enerji | saat~gölge | enerji~gölge |
|---|---|---|---|---|---|
| LPR-1 gunduz | 17 | 3 | 0,9994 | 0,7735 | 0,7779 |
| LPR-1 Ay gecesi | 24 | 3 | 0,9954 | 0,6178 | 0,6455 |
| VIPER standart | 21 | 3 | 0,9951 | 0,8886 | 0,9182 |
| VIPER kisa leg | 15 | 4 | 1,0000 | 0,9857 | 0,9857 |

**Bu n'lerde bir korelasyon betimleyicidir, çıkarımsal değildir** ve güven aralığı iddia edilmiyor. D5 burada bir **sonucu** ölçüyor, **sebebini** kurmuyor: depo, katmanların hepsinin tek bir yükseklik gridinden türediğini ve iki kriterin Spearman'ının tam 1,000000 ölçüldüğünü zaten kaydetmişti (`cost_engine.py`). D5 "arazi" ile "bu arazide bu maliyet modeli"ni ayıramaz.

## 4. Yeterince örneklemedik mi? — bütçe eğrisi

Cephenin tek noktaya çöktüğü ilk ölçüm **n = 24**'teydi. Bütçe büyütülünce bu iddia kısmen düştü; düzeltilmiş hâli budur. (LPR-1 gündüz çifti.)

| örnek bütçesi | ağırlık vektörü | farklı rota | **baskın-olmayan** | süre (s) |
|---|---|---|---|---|
| 8 | 9 | 9 | **1** | 2,1 |
| 16 | 17 | 13 | **1** | 3,8 |
| 24 | 25 | 17 | **1** | 5,8 |
| 40 | 41 | 27 | **1** | 9,6 |
| 60 | 61 | 35 | **1** | 14,6 |
| 100 | 101 | 45 | **3** | 24,4 |
| 150 | 151 | 58 | **3** | 36,5 |
| 200 | 201 | 61 | **3** | 48,4 |
| 200 + köşeler | 211 | 65 | **4** | — |

Cephe tek nokta **değil**, ama bütçeden **çok daha yavaş** büyüyor. Simpleksin köşelerini örneklemek ayrıca işe yarıyor: iç bölgeden çekilen vektörler onları hiç bulamaz.

Şimdi asıl sayı. Köşeler dâhil en büyük bütçede (211 vektör, 65 farklı rota, 4 baskın-olmayan) **hayatta kalanların** aralığı, taramanın **ürettiği her şeyin** aralığının yanında:

| hedef | cephe: min | cephe: maks | **cephe genişliği** | tüm rotaların genişliği |
|---|---|---|---|---|
| `hours` | 1,6184 | 1,6213 | **%0,179** | %22,226 |
| `energy_wh` | 593,91 | 595,22 | **%0,221** | %36,734 |
| `shadow_exposure_h` | 0,9165 | 0,9216 | **%0,556** | %21,571 |
| `thermal_risk` | 1,0000 | 1,0000 | **%0,000** | %0,000 |

**İki sütunu karıştırmamak gerekir.** Ağırlık seçimi sonucu geniş bir aralıkta oynatıyor (sağ sütun); ama o aralığın neredeyse tamamı **baskılanmış** rotalardan oluşuyor ve hayatta kalanlar çok dar bir şeride sıkışıyor (sol sütun).

## 5. Cephe kendi gürültüsünün içinde mi?

Yukarıdaki genişlik, **aynı rotaya** B2'nin CVaR slip kuyruğu uygulandığında ortaya çıkan yayılmayla karşılaştırılmalıdır. Bu farklı bir rota değil; modelin o rotanın saatini ne kadar bildiğidir.

Nominal rota: **1,6229 saat**.

| α | `hours_factor` | risk-ayarlı saat | Δ% |
|---|---|---|---|
| 0,50 | 1,1690 | 1,8972 | **%16,90** |
| 0,75 | 1,3624 | 2,2112 | **%36,24** |
| 0,90 | 1,5846 | 2,5717 | **%58,46** |
| 0,95 | 1,7395 | 2,8231 | **%73,95** |
| 0,99 | 2,0795 | 3,3749 | **%107,95** |

**Cephenin saat genişliği %0,179; modelin kendi bandı α = 0,5'te %16,90.** Yani cephe, modelin en iyimser belirsizlik bandından yaklaşık **94×** dardır.

Cephe içindeki her "A, B'yi baskılıyor" ifadesi bu gürültünün çok içinde kurulmuştur. Bir farkı kendi bandının içindeyken sonuç diye sunmuyoruz.

## 6. Rover'ın kendi ağırlıkları cephede mi?

| senaryo | nominal cephede mi | baskılayan rota | en büyük kayıp |
|---|---|---|---|
| LPR-1 gunduz | hayır | 2 | %-0,358 |
| LPR-1 Ay gecesi | hayır | 7 | %-4,644 |
| VIPER standart | hayır | 7 | %-2,002 |
| VIPER kisa leg | hayır | 4 | %-0,480 |

**Bu bir bug değil.** Varsayılan ağırlık vektörü **ağırlıklı maliyeti** minimize eder, bu dört hedeften hiçbirini değil; maliyet-optimal rotanın sonuç uzayında baskın olması için bir sebep yoktur. Baskılandığı yerde kaybı **yüzdenin kesirleri** mertebesindedir — yani §5'teki bandın iki mertebe altında. **"Varsayılan ağırlıklar yanlış" cümlesi bu ölçümden çıkmaz** ve kurulmamıştır.

## 7. İddia sınırı

- **Bu bir Pareto cephesi değildir** ve yanıt kendini öyle adlandırmaz (`non_dominated`, `pareto_front` değil). Weighted-sum scalarisation reaches only supported efficient solutions -- those on the boundary of the convex hull of the achievable set -- and unsupported ones are unreachable at any sampling density (Boyd & Vandenberghe 4.7.4; Das & Dennis 1997). Here the weights scalarise the per-cell COST CRITERIA, not these objectives, so even that guarantee does not apply: this sweep may miss routes a weighted sum over the objectives themselves would find. Nothing in this response bounds what was missed.
- **Literatürün sayıları onlarındır.** Boyd & Vandenberghe, Das & Dennis, Könen & Stiglmayr, ETH ve Lavin künyeleriyle alıntılanmıştır; hiçbiri yeniden üretilmemiştir.
- **Bizim olan:** kaç ağırlık vektörü, kaç farklı rota, kaç baskın-olmayan, cephenin genişliği ve gürültü bandı. Her tabloda n yazılı ve her istatistik **farklı rotalar** üzerinden.
- **Baskınlık, API'nin kendi yayın hassasiyetinde karara bağlanır** (1e-4 sa, 1e-2 Wh, 1e-4, 1e-4). Bu kuantumlara yakın farklar bir sıralama değildir.
- **Hiçbir rota sayısı değişmedi.** D5 planlayıcıya dokunmaz; LPR-1'in checked-in v5 maliyet-gridi SHA-256 özeti kıpırdamadı ve `COST_MODEL_ID` `…_v5`'te kaldı.
- **Sebep kurulmadı.** Cephenin darlığı ölçüldü; "arazi" ile "bu arazide bu maliyet modeli" bu ölçümle ayrılamaz.

**Sunum cümlesi.** "Ağırlık tartışması bu arazide iki ayrı sorudur: kötü bir vektör seçmek ölçülebilir bir hatadır, iyi vektörler arasında seçim yapmak ise bu modelin çözemeyeceği bir sorudur — çünkü hayatta kalan rotaların arası, modelin kendi belirsizliğinden iki mertebe dardır."

*Makine tarafından okunan iddia sınırı (`app.pareto.PARETO_CLAIM`):* A non-dominated subset of the routes THIS SWEEP produced, not the Pareto front of the problem: weighted-sum scalarisation reaches only supported solutions, and these weights scalarise the cost criteria rather than these objectives, so nothing here bounds what was missed. Every route is the planner's existing 2-D physics on a DERIVED cost grid; the sweep changes ranking only and adds no physics. Dominance is decided at the API's reporting precision (1e-4 h, 1e-2 Wh, 1e-4, 1e-4), so margins near those quanta are not orderings. Routes are de-duplicated by cell sequence, and every statistic here runs over DISTINCT routes -- pooling repeated routes would count the same route twice. The literature's numbers are quoted, never reproduced.

