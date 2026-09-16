# D4 — Kontrastif açıklama: Site11 ölçümleri

*Üreten: `scripts/contrastive_explanation_report.py`. (`--json` ham çıktı, `--from-json` ölçmeden yeniden render.)*

Grid: **500×500**, 5,0 m/px, pencere ofseti `{'row': 2400, 'col': 2500}`. Bütün sayılar bu pencerede gerçekten koşuldu.

---

## Manşet

**Karşı-olgusal cevabın kendisi kolay; onu ne zaman söylememek gerektiği zor.** Rota maliyeti ağırlık vektöründe **tam olarak afin** olduğu için "hangi ağırlık alternatifi öne geçirir" sorusunun kapalı formu var — arama yok, ikili arama yok, yeniden planlama yok. Ölçülen asıl sonuç bu değil:

1. **Eşiklerin bir kısmı modelin kendi gürültüsünün içinde.** Bantlı 4 vakanın 2 tanesinde maliyet farkı NASA'nın kendi DEM hata gerçeklemelerinin standart sapmasının altında kaldı ve cevap "şu ağırlığı şuraya çek" değil, **`closer_than_the_model_resolves(level=terrain_ensemble)`** oldu.
2. **Bir vakada hangi rotanın ucuz olduğu bile sabit değil.** *Ay gecesi / sapma* çiftinde nominal DEM "planlayıcının rotası 3,6806 ağırlıklı metre ucuz" diyor; NASA'nın 20 klonunun **4 tanesinde işaret ters dönüyor**. Fark (3,6806) ensemble standart sapmasının (4,7982) altında.
3. **VIPER'da arazi bandının kullanılabilir tek üyesi yok.** 15°'lik eğim limitiyle hem planlayıcının rotası hem alternatif, 20 klonun **20'sinde** sert kapıya takılıyor — yani bu senaryoda "bu rota geçilebilir" cümlesi tek bir raster gerçeklemesinin özelliği.
4. **Yeniden-planlanan rejim hiç ateşlemedi.** Ağırlık ekseni boyunca 41 noktalık tam tarama (adım 0,05, aralık [0,0; 2,0]) planlayıcıyı alternatifi **hiçbir** ağırlıkta döndürmedi (0 isabet). Yani "şu ağırlığı değiştir, rotan gelir" cümlesi bu üç çiftte kurulamıyor; kurulabilen tek cümle "şu ağırlıkta senin rotan gösterdiğimizden ucuz olurdu".

---

## Neden kapalı form: maliyet ağırlıklarda afin

Sabit bir rota R ve ağırlık vektörü w için A\*'ın minimize ettiği g-skoru tam olarak:

```
cost(R, w) = D(R) + Σ_k w_k · I_k(R) + B(R)

D(R)   = Σ_e dist_e                                yatay mesafe
I_k(R) = Σ_e dist_e · (f_k(u) + f_k(v)) / 2        kriterin yamuk çizgi integrali
B(R)   = Σ_e dist_e · bariyer_e                    ağırlıktan BAĞIMSIZ
```

Bariyer yalnızca geometri ve sıcaklığa bakar, ağırlıklara bakmaz; bu yüzden maliyet w'de afin ve iki sabit rotanın farkı da afin. "Hangi ağırlık alternatifi öne geçirir" sorusu bu yüzden bir denklem, bir arama değil.

**Kimlik koşullu ve koşul her ağırlıkta kontrol ediliyor.** `cost[hücre]` aslında `max(Σ_k w_k f_k, MIN_CELL_COST)` — yani parçalı afin. Afin dal yalnızca kelepçe bağlamadığı yerde geçerli, ve `PlanWeights` beş ağırlığın da 0 olmasına izin veriyor (o noktada geçilebilir hücrelerin %100'ü kelepçeleniyor). Modül kelepçe payını her rotada, her ağırlıkta ölçüyor ve bağladığında hiçbir afin iddia yayımlamıyor (`clamp_binds`).

## Dört sonuç kategorisi — hangisi kaç vakada çıktı

Sayılar **oran değil**: 3 çift × 3 alternatif = 9 adlandırılmış vaka, ve alternatiflerin nasıl üretildiği hangi kategorilerin erişilebilir olduğunu belirliyor. Bu bir teorem, arazi hakkında bir bulgu değil:

* Planlayıcının **kendi** ürettiği bir alternatif (`planner_at_weights`) `hard_gate` olamaz — planlayıcı kendi kapısını çiğnemez — ve `dominated_on_every_criterion` de olamaz, çünkü tanımı gereği bir ağırlık vektöründe optimal.
* Bu yüzden rapor kasıtlı olarak **inşa edilmiş** alternatifler de içeriyor: kullanıcının çizeceği **düz çizgi** (`hand_drawn`) ve aynı koridorda kesinlikle daha uzun bir **sapma** (`constructed_detour`).

| sonuç | vaka | nasıl üretilen alternatiflerde |
|---|---|---|
| `found_vs_fact_only` | 4 / 9 | constructed_detour, planner_at_weights |
| `hard_gate` | 3 / 9 | hand_drawn |
| `dominated_on_every_criterion` | 2 / 9 | constructed_detour |

### Vaka vaka

| çift | alternatif | üretim | sonuç | Δmaliyet (ağırlıklı m) | Δ% | çözünürlük |
|---|---|---|---|---|---|---|
| LPR-1 gunduz | duz cizgi | `hand_drawn` | `hard_gate` | — | — | — |
| LPR-1 gunduz | termal-agir rota | `planner_at_weights` | `found_vs_fact_only` | 90,6173 | %5,872 | **eyleme dönük** |
| LPR-1 gunduz | sapma | `constructed_detour` | `dominated_on_every_criterion` | 36,7305 | %2,380 | **eyleme dönük** |
| Ay gecesi | duz cizgi | `hand_drawn` | `hard_gate` | — | — | — |
| Ay gecesi | termal-agir rota | `planner_at_weights` | `found_vs_fact_only` | 9,2246 | %0,212 | **değil** |
| Ay gecesi | sapma | `constructed_detour` | `found_vs_fact_only` | 3,6806 | %0,085 | **değil** |
| VIPER kisa leg | duz cizgi | `hand_drawn` | `hard_gate` | — | — | — |
| VIPER kisa leg | termal-agir rota | `planner_at_weights` | `found_vs_fact_only` | 8,3489 | %0,759 | **eyleme dönük** |
| VIPER kisa leg | sapma | `constructed_detour` | `dominated_on_every_criterion` | 54,4660 | %4,953 | **eyleme dönük** |

## (a) İhlal edilen sert kapılar

Kapılar planlayıcının **kendi sırasıyla** yeniden oynatılıyor — `_astar_core` ilk eşleşen kuralda `continue` ettiği için sıra belirleyici. Çapraz köşe kesme eğim kapılarından **önce** geliyor: iki kuralı birden çiğneyen bir kenar planlayıcıya göre `diagonal_corner_cut`, eğimi önce bakan bir kopyaya göre `step_slope` olurdu — aynı hüküm, yanlış gerekçe.

| çift | alternatif | ihlal | kural dağılımı |
|---|---|---|---|
| LPR-1 gunduz | duz cizgi | 58 | `destination_not_traversable`: 53, `diagonal_corner_cut`: 3, `lateral_slope`: 2 |
| Ay gecesi | duz cizgi | 55 | `destination_not_traversable`: 40, `diagonal_corner_cut`: 15 |
| VIPER kisa leg | duz cizgi | 18 | `destination_not_traversable`: 14, `diagonal_corner_cut`: 2, `step_slope`: 2 |

Düz çizgi üç çiftin **üçünde de** sert kapıya takıldı. Doğru cevap burada "şu ağırlığı değiştir" değil: **hiçbir ağırlık bu rotayı geri alamaz**, çünkü geçilebilirlik, adım eğimi, yanal eğim ve köşe kuralı ağırlıklardan bağımsız. Modül bu durumda (b) ve (c) bloklarını **açıkça bastırıyor** ve uydurma sayı üretmiyor.

## (b) Kriter bazında maliyet farkı

Ayrıştırma **tam**: `Δmesafe + Δbariyer + Σ_k w_k·ΔI_k` farkın tamamı, artık yok. Kullanılan temel `total_weighted_cost` (**bariyer dahil**, A\*'ın gerçekten minimize ettiği g-skoru), `total_weighted_cost_cells_only` değil — ikisi bu sitede %12–15 ayrışıyor ve bariyer hiçbir ağırlığın dokunamadığı terim olduğu için **ayrı bir satır olarak** yayımlanıyor.

**LPR-1 gunduz / termal-agir rota** — `found_vs_fact_only`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | 165,7567 | 67,7945 |
| energy | 142,9373 | 37,0208 |
| shadow | -3,7848 | -0,5374 |
| thermal | -73,1322 | -13,8951 |
| roughness | -92,2000 | -13,8300 |
| *mesafe* | — | 0,0000 |
| *bariyer* | — | 14,0646 |
| **toplam** | | **90,6173** |

**LPR-1 gunduz / sapma** — `dominated_on_every_criterion`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | 28,2229 | 11,5432 |
| energy | 29,6501 | 7,6794 |
| shadow | 1,1748 | 0,1668 |
| thermal | 9,3388 | 1,7744 |
| roughness | 10,4216 | 1,5632 |
| *mesafe* | — | 12,4264 |
| *bariyer* | — | 1,5771 |
| **toplam** | | **36,7305** |

**Ay gecesi / termal-agir rota** — `found_vs_fact_only`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | 22,4691 | 9,1899 |
| energy | 18,7415 | 4,8541 |
| shadow | -2,4344 | -0,3457 |
| thermal | -8,7004 | -1,6531 |
| roughness | -10,8208 | -1,6231 |
| *mesafe* | — | 0,0000 |
| *bariyer* | — | -1,1974 |
| **toplam** | | **9,2246** |

**Ay gecesi / sapma** — `found_vs_fact_only`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | -3,9441 | -1,6131 |
| energy | -8,8315 | -2,2874 |
| shadow | -2,2440 | -0,3186 |
| thermal | 0,3054 | 0,0580 |
| roughness | 37,1144 | 5,5672 |
| *mesafe* | — | 0,0000 |
| *bariyer* | — | 2,2745 |
| **toplam** | | **3,6806** |

**VIPER kisa leg / termal-agir rota** — `found_vs_fact_only`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | 15,2399 | 5,3339 |
| energy | 15,4997 | 3,8749 |
| shadow | -0,8440 | -0,1688 |
| thermal | -24,6115 | -4,9223 |
| roughness | -1,4250 | -0,2138 |
| *mesafe* | — | 0,0000 |
| *bariyer* | — | 4,4449 |
| **toplam** | | **8,3489** |

**VIPER kisa leg / sapma** — `dominated_on_every_criterion`

| terim | ΔI_k | w_k·ΔI_k |
|---|---|---|
| slope | 7,8873 | 2,7606 |
| energy | 24,8885 | 6,2221 |
| shadow | 8,4483 | 1,6897 |
| thermal | 27,0946 | 5,4189 |
| roughness | 7,3920 | 1,1088 |
| *mesafe* | — | 30,0000 |
| *bariyer* | — | 7,2660 |
| **toplam** | | **54,4660** |

## (c) Minimum ağırlık değişimi — ve tanımının savunması

**"Minimum" kelimesi burada bir iddia taşımıyor ve alan adı bunu söylüyor.** Üretilen şey `per_criterion_flip_threshold`: ters problemin **tek boyutlu bir kesiti** — bir ağırlık hareket eder, diğer dördü yerinde tutulur. Bu bir norm minimize etmez; ters optimizasyon literatürünün (Burton & Toint 1992; Heuberger) sorduğu soru bütün maliyet vektörü üzerinde sınırlı bir norm minimizasyonudur. Beş ayrı tek-eksenli eşiğin en küçüğü, 5 boyutlu kutudaki minimum **değildir**.

Bu yüzden dürüst olan da yanında yayımlanıyor: `l2_minimal_joint_move`, aynı rejimde ℓ₂-minimal ortak hamle (Δ = 0 hiperdüzlemine dik izdüşüm), kapalı formda. Ortak hamlenin her vakada en iyi tek-eksenli hamleden küçük olduğu `test_contrastive.py` içinde iddia olarak kilitli.

**Ağırlığın ne demek olduğu.** C4 `w_roughness`'ı dört terimli toplama **ekleyerek** getirdi, yeniden ölçeklemedi: katalogdaki dört rover profilinin de ilk dört ağırlığı tam 1,0 topluyor, `w_roughness = 0,15` üstüne biniyor, toplam 1,15. Bu modül de aynısını yapıyor — tek ağırlığı oynatır, kalanları yeniden normalleştirmez. Yeniden normalleştirmek beş kriterin hepsini birden değiştirirdi ve "tek ağırlığı değiştirmek" cümlesi anlamını yitirirdi.

| çift / alternatif | kriter | sonuç | eşik | yön | ΔI_k |
|---|---|---|---|---|---|
| LPR-1 gunduz / termal-agir rota | slope | `outside_weight_bounds` | -0,13769 | decrease | 165,7567 |
| LPR-1 gunduz / termal-agir rota | energy | `outside_weight_bounds` | -0,37497 | decrease | 142,9373 |
| LPR-1 gunduz / termal-agir rota | shadow | `outside_weight_bounds` | 24,08427 | increase | -3,7848 |
| LPR-1 gunduz / termal-agir rota | thermal | `found_vs_fact_only` | 1,42909 | increase | -73,1322 |
| LPR-1 gunduz / termal-agir rota | roughness | `found_vs_fact_only` | 1,13283 | increase | -92,2000 |
| LPR-1 gunduz / sapma | slope | `outside_weight_bounds` | -0,89244 | decrease | 28,2229 |
| LPR-1 gunduz / sapma | energy | `outside_weight_bounds` | -0,97980 | decrease | 29,6501 |
| LPR-1 gunduz / sapma | shadow | `outside_weight_bounds` | -31,12395 | decrease | 1,1748 |
| LPR-1 gunduz / sapma | thermal | `outside_weight_bounds` | -3,74311 | decrease | 9,3388 |
| LPR-1 gunduz / sapma | roughness | `outside_weight_bounds` | -3,37447 | decrease | 10,4216 |
| Ay gecesi / termal-agir rota | slope | `outside_weight_bounds` | -0,00155 | decrease | 22,4691 |
| Ay gecesi / termal-agir rota | energy | `outside_weight_bounds` | -0,23320 | decrease | 18,7415 |
| Ay gecesi / termal-agir rota | shadow | `outside_weight_bounds` | 3,93123 | increase | -2,4344 |
| Ay gecesi / termal-agir rota | thermal | `found_vs_fact_only` | 1,25025 | increase | -8,7004 |
| Ay gecesi / termal-agir rota | roughness | `found_vs_fact_only` | 1,00249 | increase | -10,8208 |
| Ay gecesi / sapma | slope | `found_vs_fact_only` | 1,34218 | increase | -3,9441 |
| Ay gecesi / sapma | energy | `found_vs_fact_only` | 0,67575 | increase | -8,8315 |
| Ay gecesi / sapma | shadow | `found_vs_fact_only` | 1,78217 | increase | -2,2440 |
| Ay gecesi / sapma | thermal | `outside_weight_bounds` | -11,86134 | decrease | 0,3054 |
| Ay gecesi / sapma | roughness | `found_vs_fact_only` | 0,05083 | decrease | 37,1144 |
| VIPER kisa leg / termal-agir rota | slope | `outside_weight_bounds` | -0,19783 | decrease | 15,2399 |
| VIPER kisa leg / termal-agir rota | energy | `outside_weight_bounds` | -0,28865 | decrease | 15,4997 |
| VIPER kisa leg / termal-agir rota | shadow | `outside_weight_bounds` | 10,09206 | increase | -0,8440 |
| VIPER kisa leg / termal-agir rota | thermal | `found_vs_fact_only` | 0,53923 | increase | -24,6115 |
| VIPER kisa leg / termal-agir rota | roughness | `outside_weight_bounds` | 6,00872 | increase | -1,4250 |
| VIPER kisa leg / sapma | slope | `outside_weight_bounds` | -6,55555 | decrease | 7,8873 |
| VIPER kisa leg / sapma | energy | `outside_weight_bounds` | -1,93840 | decrease | 24,8885 |
| VIPER kisa leg / sapma | shadow | `outside_weight_bounds` | -6,24700 | decrease | 8,4483 |
| VIPER kisa leg / sapma | thermal | `outside_weight_bounds` | -1,81022 | decrease | 27,0946 |
| VIPER kisa leg / sapma | roughness | `outside_weight_bounds` | -7,21825 | decrease | 7,3920 |

**Yön ΔI_k'nın işaretinden geliyor, tahminden değil.** Δ₀ ≥ 0 (A\* optimal), yani ΔI_k > 0 ise — alternatif o kriterden daha çok harcıyor — ağırlık **düşmeli** ve kök w_k⁰'ın altında; ΔI_k < 0 ise **yükselmeli**. Bunu ters çevirmek yeniden-planlama taramasını, kanıtlanabilir biçimde boş olan yarıya gönderir.

**Sınır dışı bir eşik yeniden-planlanan rejimi de kapatıyor — kanıtla, taramayla değil.** Δ_yeniden ≥ Δ_sabit her noktada (yeniden planlanan optimum, sabit tutulan rotadan asla pahalı olamaz), dolayısıyla `vs_fact` [0, 2] içinde bir şey bulamıyorsa `vs_replanned` de bulamaz. Bu vakalarda **sıfır** yeniden planlama harcanıyor.

## Hareketli hedef: iki rejim, iki farklı cevap

Bir ağırlığı değiştirmek maliyet gridini, o da planlayıcının **kendi** optimumunu değiştirir. "Alternatif kazanır" bu yüzden iki ayrı şey demek:

* **`vs_fact`** — alternatif, *gösterdiğimiz* rotadan ucuz olur. Afin, kapalı form, sıfır yeniden planlama. Krarup vd.'nin yönteminin dejenere limiti: hipotetik modelin tek planı alternatifin kendisi olduğu için "yeniden planlama" boş bir işlem ve açıklama onların plan-HPlan karşılaştırması.
* **`vs_replanned`** — planlayıcı alternatifi **döndürür**. Alternatif ancak kendisi optimal olarak kazanabilir. Operatörün gerçekten sorduğu soru bu.

**İkili arama kullanılmadı ve sebebi gecikme değil.** `Δ_yeniden(w) = cost_alt(w) − min_R cost_R(w)` afin bir fonksiyon eksi afin fonksiyonların noktasal minimumu, yani **konveks**; sıfır kümesi bir **aralık**, yarı-doğru değil. Dolayısıyla "alternatif kazanır mı" monoton bir yüklem **değil** ve ikili aramanın yakınsayacağı bir eşik yok.

**Konvekslik varsayılmadı, ölçüldü.** `w_thermal` ekseninde 41 noktalık tarama (0,05 adım), 39 ayrık ikinci fark: en küçüğü **-6.82e-13** — float64 gürültüsü mertebesinde ve negatif değil. Konvekslik tutuyor.

**Monotonluk ölçümü ise boş çıktı ve bu böyle raporlanıyor.** Aynı taramada yüklem 0 kez doğru oldu, yani **hiç**; geçiş sayısı 0. Sabit-yanlış bir yüklemin "monoton" görünmesi **vakumda doğrudur ve monotonluk hakkında hiçbir şey söylemez**. Ölçülen şey şu: bu çiftte `w_thermal`'ı [0; 2] boyunca süpürmek planlayıcıyı alternatifi döndürmeye ikna etmiyor.

**Taramanın maliyeti ve çözünürlüğü.** Bir yineleme = maliyet gridi yeniden hesabı (0,1049 s) + A\* (0,1157 s) = **0,2206 s** (medyan, n=5). 41 noktalık tam tarama 10,0 s sürdü (0,2445 s/nokta). Uç, istek başına toplam yeniden planlamayı **30** ile sınırlıyor (~6,5 s en kötü hâl).

**"Bulunamadı" negatif sonuç olarak yayımlanmıyor.** Kazanan küme bir aralık, ve tarama adımından dar bir aralık görülmez; bu yüzden her `unresolved_by_scan` cevabı kullanılan adımı ve çözebileceği en dar aralığı yanında taşıyor.

## Karşı-olgusal modelin kendi gürültüsünün içinde mi?

Bu sorunun tek bir cevabı yok, çünkü tek bir "model çözünürlüğü" yok. Ölçülen dört taban dokuz mertebe ayrışıyor, ve her hüküm **hangi tabanda** verildiğini söylüyor:

| taban | nedir | ölçülen |
|---|---|---|
| `arithmetic` | aynı kod, aynı grid, float64 | ~1e-10 |
| `publication` | API'nin yayımladığı alanların yuvarlanması | 1e-4 en kötü hâl, 4,08e-5 RSS — **emekli**: bu modül kendi float64 integrallerini farklıyor, iki yuvarlanmış sayıyı çıkarmıyor |
| `model_discretisation` | `_barrier_table`'ın 1024 kovalı araması ile kapalı form arası | çift başına hesaplandı: 0,000331 – 0,042074 ağırlıklı metre |
| `terrain_ensemble` | NASA'nın kendi 20 DEM hata gerçeklemesi (PGDA ürün 78, Barker vd. 2021) | σ = 4,798 – 17,848 ağırlıklı metre |

**Neden `risk_alpha` bant olarak kullanılmadı.** B2'nin α'sı bir **belirsizlik** değil, operatörün **risk iştahı** (`risk.py` bunu kendi yazıyor) — en küçük üyesi bile μ + 0,798σ olduğu için nominali hiçbir zaman ortalamaz, ve yalnızca eğim ile enerji kriterlerine ulaşır. Mesafe terimi, bariyer ve gölge/termal/pürüzlülük kriterleri α'dan hiç etkilenmez. Klon topluluğu ise **yükseklik alanını** oynattığı için mesafeyi, bariyeri, kapıları ve eğim türevli kriterleri birlikte hareket ettiriyor — bir girdi belirsizliğinin bu maliyet üzerindeki gerçek görüntüsü bu.

| çift / alternatif | Δ nominal | ensemble ort. | σ | işaret dönen klon | planlayıcının rotası kapıya takılan klon | alternatif |
|---|---|---|---|---|---|---|
| LPR-1 gunduz / termal-agir rota | 90,6173 | 65,0099 | 17,8483 | 0 / 20 | 6 / 20 | 10 / 20 |
| LPR-1 gunduz / sapma | 36,7305 | 42,2592 | 4,8213 | 0 / 20 | 6 / 20 | 6 / 20 |
| Ay gecesi / termal-agir rota | 9,2246 | 18,9075 | 5,4191 | 0 / 20 | 0 / 20 | 0 / 20 |
| Ay gecesi / sapma | 3,6806 | 4,8475 | 4,7982 | 4 / 20 | 0 / 20 | 0 / 20 |

**Bandın kapsamadığı şey de yazılı.** Termal, gölge ve pürüzlülük katmanları ayrı ürünler ve klonlarla oynatılmıyor; 20 klon kendi standart sapmasına yaklaşık ±%16 örnekleme hatası taşıyor. Bant bu yüzden modelin toplam yayılımının bir **alt sınırı**.

**D5'in "94×" cümlesi D4'te tekrarlanmadı ve tekrarlanmamalı.** O karşılaştırma saatteki bir **ortak-mod seviye kayması** ile bir **cephe genişliğini** yan yana koyuyordu; ortak mod iki rotanın farkından zaten çıkar. D4'ün farkı ağırlıklı metrede, D5'in bandı saatte — ikisi arasında dönüşüm yok. Bu rapor farkı ağırlıklı metrede ölçüyor ve ağırlıklı metredeki banda karşı tartıyor; fiziksel büyüklükler `objective_gap` bloğunda **ayrıca** ve dönüşüm iddiası olmadan veriliyor.

## İddia sınırı

* Bu açıklama **bizim maliyet modelimiz** hakkında. "Bu rota şundan iyi" değil, "bu rota bizim maliyet modelimize göre şundan ucuz".
* Kapı hükümleri 5 m/px'lik bir rasterde, adı konmuş bir operatörle (`abs(dz)/dist`, `np.gradient`) hesaplanıyor. 5 m örnekleme ~1 m dingil açıklıklı bir aracın gerçekten aştığı basamağı çözemez; temiz bir kapı zeminin güvenli olduğu **iddiası değil**. Aynı kapılar klonlarda yeniden oynatıldığında planlayıcının kendi rotası bile takılıyor.
* Maliyet farkları **ağırlıklı metre** — 2-B planlayıcının sıralama skaleri, fiziksel boyutu yok ve saatle aynı yöne gitmek zorunda değil.
* XAIP literatürü **yöntem** kaynağı. Krarup vd. kontrastif çerçeveyi veriyor; `vs_replanned` onların **model kısıtlaması** tanımına girmiyor (Tanım 4 kısıtlı modelin planlarının orijinalin alt kümesi olmasını ister; yeniden ağırlıklandırma plan kümesine dokunmaz, yalnızca yeniden fiyatlar) ve bu modül öyle olduğunu iddia etmiyor. (c)'nin asıl evi **ters optimizasyon**: Burton & Toint 1992, Heuberger'in taraması. Onların sayıları `CONTRASTIVE_QUOTED` sözlüğünde, bizimkiyle aynı tabloda değil.
* 2-B yalnız. `pathfinder` `weighted_metres`, `pathfinder_4d` `weighted_hours` yayımlıyor; iki toplam karşılaştırılamaz.

