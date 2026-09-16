# D4 — Kontrastif açıklama: "neden bu rota, neden şu değil?" — Tasarım Belgesi

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance`
· **Kaynak madde:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § D4](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** D5 (`route_id`, `dominates`, `OBJECTIVE_QUANTUM`, `grids_for_rover` deseni),
B3 (NASA DEM klonları), C4/C5 (v5 maliyet gridi ve SHA kilidi)

**Yol:** Rota maliyetinin ağırlık vektöründe **afin** olduğunu ölçmek, bu kimliği kullanarak
"hangi ağırlık alternatifi öne geçirir" sorusunu **kapalı formda** cevaplamak, ve asıl işi
cevabın **ne zaman söylenmemesi gerektiğine** ayırmak.

**Kapsam:** Yeni `backend/app/contrastive.py`, yeni `POST /api/explain-contrast`
(yalnızca ekleme), rapor betiği, testler, sözleşme eki.
**Yeni fizik yok, yeni dış veri yok, planlayıcıya dokunulmuyor.**

---

## D4 bir AÇIKLAMA özelliğidir

C1/C2 birer model özelliğiydi (yeni fizik). C5 bir doğrulama özelliğiydi (dış veriye karşı sayı).
D5 bir arama + sunum özelliğiydi. D4 bunların hiçbiri: var olan modelin **kendi kararını**
anlatıyor. Sonucu: **bit-eşitlik burada "hiçbir rota, hiçbir maliyet hücresi kıpırdamadı"
demektir** — LPR-1'in checked-in v5 maliyet-gridi SHA-256 özeti sabit kalır, `COST_MODEL_ID`
`…_v5`'te kalır, ve `pathfinder.py` **tek satır** değişmez.

`pathfinder.py`'ye dokunulmamasının ayrı bir gerekçesi var: kapı kuralları
`_astar_core`'un iç döngüsünde **elle inline edilmiş** durumda, çünkü o döngü üretim gridinde
kenar başına ~1,6 milyon kez koşuyor. Kuralları ortak bir fonksiyona çıkarmak döngüye çağrı
koyardı. Bu yüzden `contrastive.py` bir **yeniden oynatma** (replay) barındırıyor ve
uyum testle çivileniyor (§ Kapı sırası).

---

## Kimlik: rota maliyeti ağırlıklarda afin

A\* şunu minimize ediyor:

```
edge(u→v) = dist · (1 + (cost[u] + cost[v]) / 2 + bariyer)
cost[hücre] = max(Σ_k w_k · f_k(hücre), MIN_CELL_COST)
```

Bariyer yalnızca **geometri ve sıcaklığa** bakıyor — ağırlıklara değil. Dolayısıyla sabit bir
rota R için:

```
cost(R, w) = D(R) + Σ_k w_k · I_k(R) + B(R)
```

| terim | tanım | ağırlığa bağlı mı |
|---|---|---|
| `D(R)` | `Σ_e dist_e` — yatay mesafe | hayır |
| `I_k(R)` | `Σ_e dist_e · (f_k(u)+f_k(v))/2` — kriterin **yamuk çizgi integrali** | hayır |
| `B(R)` | `Σ_e dist_e · bariyer_e` | hayır |

**Ölçüldü (Site11, LPR-1, gündüz çifti):** yeniden kurulan toplam, planlayıcının yayımladığı
`total_weighted_cost = 1543,0934` değerini **yayımlanan alanın kendi yuvarlamasına kadar**
(+3,0e-5 hücre terimi, −4,3e-5 bariyer terimi) yeniden üretiyor. `D = 909,6194`,
`B = 188,5102` (`barrier_share = 0,1222`), `I = {slope 120,368, energy 323,222,
shadow 213,920, thermal 885,568, roughness 755,894}`.

### Kimlik KOŞULLU ve koşul varsayılmıyor

`max(·, MIN_CELL_COST)` gerçek hücre maliyetini **parçalı afin** yapıyor; afin dal yalnızca
kelepçenin bağlamadığı bölgede geçerli. `PlanWeights` beş ağırlığın da 0 olmasına izin veriyor
ve o noktada geçilebilir hücrelerin **%100'ü** kelepçeleniyor. Bu yüzden kelepçe payı
**her rotada, her değerlendirilen ağırlıkta** hücre hücre ölçülüyor ve bağladığında
`clamp_binds` sonucu dönüyor — hiçbir afin ya da konveks iddia yayımlanmıyor.

**Ölçüldü:** nominal ağırlıklarda gündüz çiftinde kelepçe payı **37,6×**
(`min Σ w_k f_k = 0,3756` vs `0,01`), kelepçelenen hücre **0**.

---

## Neden iki rejim: hareketli hedef

Bir ağırlığı değiştirmek maliyet gridini, o da planlayıcının **kendi optimumunu** değiştirir.
"Alternatif kazanır" bu yüzden iki farklı önerme ve bunları tek bir sayıya yıkmak bu özellikte
yapılabilecek en sinsi hata:

| rejim | soru | maliyet | yayımlanan ad |
|---|---|---|---|
| (i) | alternatif, **gösterdiğimiz** rotadan ucuz olur mu | kapalı form, **0** yeniden planlama | `vs_fact` |
| (ii) | planlayıcı alternatifi **döndürür** mü | tarama, yineleme başına ölçülen 0,216 s | `vs_replanned` |

**İkisi de yayımlanıyor**, çünkü (i) bedava ve (ii)'yi **kanıtlanabilir biçimde sınırlıyor:
Δ_(ii) ≥ Δ_(i)** her noktada (yeniden planlanan optimum, sabit tutulan rotadan asla pahalı
olamaz). Dolayısıyla (i) [0, 2] içinde bir şey bulamıyorsa (ii) de bulamaz — **kanıtla,
sıfır yeniden planlamayla.**

### İkili arama kullanılmadı, ve sebebi gecikme değil

`Δ_(ii)(w) = cost_alt(w) − min_R cost_R(w)` = afin fonksiyon **eksi** afin fonksiyonların
noktasal minimumu = **konveks**. Konveks ve her yerde ≥ 0 olan bir fonksiyonun sıfır kümesi
bir **aralık**, yarı-doğru değil. Yani "alternatif kazanır mı" **monoton bir yüklem değil**
ve ikili aramanın yakınsayacağı bir eşik yok.

Bu, feasible küme ağırlıktan bağımsız olduğu için geçerli: `compute_traversability_bool`
ağırlık almıyor, ve `CostMap.total` sonsuz katkıları ağırlıklandırmıyor, dolayısıyla geçilmez
hücreler her w için geçilmez kalıyor.

**Konvekslik varsayılmadı, ölçüldü:** `w_thermal` ekseninde 41 noktalık tarama, 39 ayrık
ikinci fark, en küçüğü **−6,8e-13** (float64 gürültüsü). Konvekslik tutuyor.

**Monotonluk ölçümü boş çıktı ve öyle raporlanıyor:** aynı taramada yüklem **0** kez doğru
oldu, geçiş sayısı 0. Sabit-yanlış bir yüklem "monoton" görünür ama bu **vakumda doğrudur**
ve monotonluk hakkında hiçbir şey söylemez. Rapor bunu bu sözlerle yazıyor.

---

## "Minimum ağırlık değişimi" — tanım ve savunma

**Üretilen şeyin adı `per_criterion_flip_threshold`, "minimum" değil.** Hesaplanan, ters
optimizasyon probleminin **tek boyutlu bir kesiti**: bir ağırlık hareket eder, diğer dördü
yerinde durur.

```
Δ(w_k) = Δ₀ + (w_k − w_k⁰) · ΔI_k     ⟹     w_k* = w_k⁰ − Δ₀ / ΔI_k
```

Bu bir **norm minimize etmiyor**. Ters optimizasyon literatürünün (Burton & Toint 1992;
Heuberger'in taraması) sorduğu soru bütün maliyet vektörü üzerinde sınırlı bir norm
minimizasyonu, ve beş ayrı tek-eksenli eşiğin en küçüğü 5 boyutlu kutudaki minimum **değil**.
Bu yüzden dürüst olan yanında yayımlanıyor: **`l2_minimal_joint_move`**, aynı rejimde
ℓ₂-minimal ortak hamle (Δ = 0 hiperdüzlemine dik izdüşüm), kapalı formda ve kutuya kırpıldığında
kırpıldığı işaretlenerek.

### Yön ΔI_k'nın işaretinden gelir

Δ₀ ≥ 0 (A\* optimal). Yani **ΔI_k > 0** ise alternatif o kriterden daha çok harcıyor demektir,
ağırlık **düşmeli**, kök w_k⁰'ın **altında**; **ΔI_k < 0** ise **yükselmeli**. Bunu ters
çevirmek (ii) rejiminin taramasını, Δ_(i) > 0 olan — yani Δ_(ii) ≥ Δ_(i) gereği
**kanıtlanabilir biçimde boş** olan — yarıya gönderir.

### Ağırlığın ne demek olduğu: yeniden normalleştirme YOK

C4 `w_roughness`'ı dört terimli toplama **ekleyerek** getirdi, yeniden ölçeklemedi.
**Ölçüldü (`get_rover` üzerinden, dört profil):** `lpr_1`, `luvmi_m`, `nasa_viper`,
`cnsa_yutu_2` — hepsinin ilk dört ağırlığı tam **1,000000**, `w_roughness = 0,150`,
toplam **1,150**. Bu modül de aynısını yapıyor: tek ağırlığı oynatır, kalanları yeniden
normalleştirmez. Normalleştirmek beş kriteri birden değiştirirdi ve "tek ağırlığı değiştirmek"
cümlesinin anlamı kalmazdı.

---

## Sonuç sözlüğü: dört değil, **on** etiket

Görev tanımı dört kategori istedi; dördü de burada. Diğer altısı, ölçümün erişilebilir olduğunu
gösterdiği ve dörde yıkılsa **uydurma bir olumsuz** üretecek hâller:

| etiket | ne demek | görev tanımının dördü mü |
|---|---|---|
| `hard_gate` | alternatif sert kapı çiğniyor; ağırlık konusu bile değil | ✅ |
| `dominated_on_every_criterion` | ΔI_k ≥ 0 ∀k **ve** ΔD+ΔB ≥ 0 **ve** Δ₀ > 0 ⟹ hiçbir w ∈ [0,∞)⁵ kazandıramaz | ✅ |
| `outside_weight_bounds` | eşik sonlu ama `PlanWeights`'in [0, 2] kutusu dışında | ✅ |
| `found_vs_fact_only` | eşik kutu içinde, ama yalnız (i) rejiminde | ✅ (ama adı düzeltildi) |
| `found_returned_by_planner` | tarama planlayıcıyı alternatifi döndürürken gördü | — |
| `unresolved_by_scan` | tarama bitti, görmedi — **olumsuz sonuç değil**, adımını taşıyor | — |
| `criterion_has_no_leverage` | ΔI_k ≈ 0; bölme yapılmaz, sayı uydurulmaz | — |
| `no_incumbent_route` | planlayıcı bu çifti hiç rotalayamıyor; her fark tanımsız | — |
| `clamp_binds` | kelepçe bağlıyor; afin kimlik orada geçerli değil | — |
| `foil_is_the_fact` | alternatif, seçtiğimiz rotanın ta kendisi | — |

**`found` etiketi bilerek bölündü.** "found: 0,42" cümlesini bir konsolda okuyan operatör
ağırlığı ayarlar ve **üçüncü** bir rota alır. (i) rejiminin cevabı bir **karşılaştırma**,
bir **ayar değil**; yalnız `found_returned_by_planner` ayar cümlesi kurabilir.

**İki kategori planlayıcı-üretimi alternatiflerle erişilemez, ve bu bir teorem:** planlayıcının
bir ağırlık vektöründe döndürdüğü rota tanımı gereği orada optimaldir, dolayısıyla
`dominated_on_every_criterion` olamaz; ve planlayıcı kendi kapısını çiğnemediği için
`hard_gate` da olamaz. Rapor bu yüzden **kasıtlı inşa edilmiş** alternatifler de içeriyor.

---

## (a) Kapı sırası — sıra belirleyicidir

`_astar_core` ilk eşleşen kuralda `continue` ediyor, yani **sıra hükmü belirliyor**. Yeniden
oynatma o sırayı birebir izliyor:

1. `destination_not_traversable` — **yalnız hedef hücre**; kaynak hücre döngü içinde yeniden
   sınanmıyor (baş hücre `astar()`'ın start ön-kontrolüyle, uçta `_validate_start_goal` ile)
2. `diagonal_corner_cut` — **eğim kapılarından ÖNCE**
3. `nan_elevation`
4. `step_slope` · 5. `lateral_slope` · 6. `thermal_barrier` · 7. `slope_barrier` ·
   8. `lateral_barrier`

**İlk taslak bu sırayı yanlış yazmıştı** (köşe kesmeyi beşinci sıraya koymuştu). İki kuralı
birden çiğneyen bir çapraz kenar planlayıcıya göre `diagonal_corner_cut`, eğimi önce bakan bir
kopyaya göre `step_slope` olurdu: **aynı hüküm, yanlış gerekçe** — ve bu bloğun tek satış
noktası gerekçenin planlayıcının kendi gerekçesi olması.

`_astar_core`'un üç `continue`'u **kasıtla** dışarıda: `bounds` (uçta `validate_foil`
hallediyor), `closed[n_idx]` ve `tentative_g >= g_score[n_idx]` — bu ikisi **arama durumu**,
kısıt değil, ve sabit bir rota üzerinde yeniden oynatılamaz. Spec bunu iddia etmiyor.

**Testle çivilendi:** (a) planlayıcının kendi rotası sıfır ihlal vermeli — bu bir
**transkripsiyon kontrolü**, arazi hakkında kanıt değil; (b) sentetik gridde iki kuralı birden
çiğneyen kenarın etiketi planlayıcının etiketine eşit olmalı.

---

## (b) Kriter bazında fark — hangi toplam

Kullanılan temel **`total_weighted_cost`** (bariyer **dahil**), `total_weighted_cost_cells_only`
değil: A\*'ın gerçekten minimize ettiği g-skoru odur ve "neden benimkini seçmedin" sorusu onun
hakkında. İkisi bu sitede **%12–15** ayrışıyor (ölçüldü: `barrier_share` 0,1222 gündüz /
0,1201 gece / 0,1502 VIPER), ve bariyer **hiçbir ağırlığın dokunamadığı** terim olduğu için
ayrı bir satır olarak yayımlanıyor.

Ayrıştırma **tam**: `ΔD + ΔB + Σ_k w_k·ΔI_k` = `Δtotal_weighted_cost`, artık yok (testle).

Her sayı bu modülün kendi float64 integrallerinin farkı. **Yayımlanmış iki yuvarlanmış alan
asla birbirinden çıkarılmıyor** — bu, `publication` çözünürlük tabanını emekliye ayırıyor.

---

## Çözünürlük: tek bir "model çözünürlüğü" yok

Dört taban ölçüldü ve **dokuz mertebe** ayrışıyorlar. Bu yüzden hüküm bir **kelime değil,
vektör**, ve manşet **hangi tabanda** verildiğini adıyla söylüyor:

| taban | ne | ölçülen |
|---|---|---|
| `arithmetic` | aynı kod, aynı grid, float64 | ~1e-10 |
| `publication` | API alanlarının yuvarlanması | 1e-4 en kötü, 4,08e-5 RSS — **emekli** |
| `model_discretisation` | `_barrier_table`'ın 1024 kovası vs kapalı form | çift başına 3,3e-4 – 4,2e-2 ağırlıklı metre |
| `terrain_ensemble` | NASA'nın 20 DEM hata gerçeklemesi | σ = 4,80 – 17,85 ağırlıklı metre |

Bir fark, o tabanın **3×**'ini aşarsa orada "çözülmüş" sayılıyor. **3 bir uzlaşım, türetme
değil**, ve yanında öyle yazıyor.

### `risk_alpha` neden bant DEĞİL

B2'nin α'sı bir belirsizlik değil, operatörün **risk iştahı** — `risk.py` bunu kendi yazıyor
(`RISK_SCOPE`), ve en küçük üyesi bile μ + 0,798σ olduğu için nominali **hiçbir zaman
ortalamaz**: tek taraflı. Üstelik yalnız `f_slope` ve `f_energy`'ye ulaşıyor; mesafe terimi,
bariyer ve gölge/termal/pürüzlülük kriterleri α'dan hiç etkilenmiyor.

**Klon topluluğu ise yükseklik alanını oynatıyor**, dolayısıyla mesafeyi, bariyeri, **kapıları**
ve eğim türevli kriterleri birlikte hareket ettiriyor. Bir girdi belirsizliğinin bu maliyet
üzerindeki gerçek görüntüsü budur. Bandın kapsamadığı da yazılı: termal, gölge ve pürüzlülük
ayrı ürünler ve oynatılmıyor; 20 klon kendi standart sapmasına ~±%16 örnekleme hatası taşıyor.
Bant bu yüzden modelin toplam yayılımının bir **alt sınırı**.

### D5'in "94×" cümlesi tekrarlanmadı

O karşılaştırma saatteki bir **ortak-mod seviye kaymasını** bir **cephe genişliğiyle** yan yana
koyuyordu; ortak mod iki rotanın farkından zaten çıkar. Ayrıca D4'ün farkı **ağırlıklı metrede**,
D5'in bandı **saatte** ve ikisi arasında dönüşüm yok — ölçüldü, işaret bile aynı yöne gitmiyor.
D4 farkı ağırlıklı metrede ölçüp ağırlıklı metredeki banda karşı tartıyor; fiziksel büyüklükler
`objective_gap` bloğunda **ayrıca** ve dönüşüm iddiası olmadan veriliyor.

---

## Kapsam: 2-B yalnız

`pathfinder` `cost_units: "weighted_metres"`, `pathfinder_4d` `"weighted_hours"` yayımlıyor ve
kod bu ikisinin toplamlarının karşılaştırılamayacağını açıkça guard'lıyor. 4-B kontrastı bu
yüzden **kapsam dışı**: bir 2-B alternatifin maliyetini 4-B bir olguyla kıyaslamanın dürüst
bir yolu yok, ve 4-B örnek başına 6–17 s bir taramaya sığmaz. `/api/risk-sweep` ve `/api/pareto`
aynı sınırı zaten taşıyor.

---

## Uçun sözleşmesi

`POST /api/explain-contrast`, `extra="forbid"` ile. Bu uçta `forbid` her yerdekinden önemli:
yazım hatası yapılmış bir ağırlık alanı sessizce düşseydi **bütün cevap, sorulandan başka bir
ağırlık vektörü hakkında** olurdu ve gövdede bunu ele verecek hiçbir şey olmazdı.

`risk_alpha` **kabul ediliyor**: /api/plan'da maliyet gridine ulaşıyor, ve α = 0,9'da planlayıp
"neden şu değil" diye soran bir operatöre nominal rotayı kontrast etmek, ona **hiç görmediği**
bir rotayı anlatmak olurdu.

**422'ler** (hepsi kuralı adıyla söyleyen bir gövdeyle):
`foil_too_short`, `foil_too_long`, `foil_cell_malformed`, `foil_out_of_bounds`,
`foil_start_mismatch`, `foil_goal_mismatch`, `foil_repeats_a_cell`, `foil_not_8_adjacent`,
`start == goal`, ve `_validate_start_goal`'un kendi 422'leri (geçilemez start/goal) —
**/api/plan ile aynı yardımcıdan**, aynı sözlerle.

Start/goal uyuşmazlığı 422'si **üç şeyi birden** yazıyor: çağıranın hücresi, çözümlenen hücre
ve hangi koordinat türünden çözümlendiği. Geo bir nokta tıklanan hücreden bir hücre uzağa
çözülebiliyor ve bu **sunucunun konvansiyonu**; çıplak bir "start'ı paylaşmalı" mesajı
kullanıcıyı sunucunun off-by-one'ı için suçlardı.

**`no_incumbent_route` neden 404 değil 200.** `/api/plan` 404 veriyor çünkü döndüreceği hiçbir
şey yok. Bu uç için durum farklı: alternatifin kapı analizi, mutlak integralleri ve —
A\* tam olduğu için — "bu çiftte hiçbir rota yok" bilgisinin kendisi zaten **açıklamanın
büyük kısmı**. Yanıt ayrıca `inconsistency` bayrağı taşıyor: rota yoksa her yol bir kapı
çiğniyor demektir, dolayısıyla kapı-temiz bir alternatif yeniden oynatmanın planlayıcıyla
çeliştiği anlamına gelir.

---

## Bütçe

Yineleme başına ölçülen maliyet: maliyet gridi **0,1049 s** + A\* **0,1157 s** = **0,2206 s**
(medyan, n=5). Tarama **kriter başına** değil **istek başına** sınırlı: `max_replans` tavanı
**30** (~6,5 s en kötü hâl), `scan_points` ≤ 12. `max_replans=0` taramayı tamamen kapatıyor ve
kapalı formdaki (i) cevabı olduğu gibi bırakıyor.

Klon bandı 20 klon için ~1,4 s; `terrain_band: false` ile kapatılabiliyor, ama kapatıldığında
yanıt arazi tabanının **ölçülmediğini** söylüyor — küçük olduğunu varsaymıyor.

---

## İddia sınırı

- Açıklama **bizim maliyet modelimiz** hakkında. "Bu rota şundan iyi" değil, "bu rota bizim
  maliyet modelimize göre şundan ucuz".
- Kapı hükümleri 5 m/px'lik bir rasterde, adı konmuş operatörlerle (`abs(dz)/dist`,
  `np.gradient`) hesaplanıyor. Alan adı `grid_value`, `measured_value` değil; her girdi
  `source` taşıyor. 5 m örnekleme ~1 m dingil açıklıklı bir aracın aştığı basamağı çözemez.
- XAIP **yöntem** kaynağı. `vs_replanned`, Krarup vd.'nin **model kısıtlaması** tanımına
  girmiyor (Tanım 4 kısıtlı modelin planlarının orijinalinkilerin alt kümesi olmasını ister;
  yeniden ağırlıklandırma plan kümesine dokunmaz, yalnız yeniden fiyatlar) — bu bir model
  **revizyonu** ve modül öyle olduğunu iddia etmiyor. (i) rejimi ise onların yönteminin
  dejenere limiti. (c)'nin asıl evi **ters optimizasyon** (Burton & Toint 1992; Heuberger).
  (b)'nin en yakın öncülü Sukkerd, Simmons & Garlan 2020. Hepsi `CONTRASTIVE_QUOTED`'da,
  bizim sayılarımızla aynı tabloda değil.
- Karşı-olgusal cevap **modelin maliyetine göre kesindir**, gerçeğe dair bir iddia değildir.
- Ağırlık değişimi bulunamıyorsa açıkça söyleniyor; "yaklaşık şu kadar" diye sayı
  uydurulmuyor.

---

## Uygulama sırasında bulunanlar ve ölçümler

**Tasarım, kod yazılmadan önce beş bağımsız düşman merceğe verildi** (matematik, kod tabanı,
XAIP literatürü, API kırıcı, metroloji) ve **beş ölümcül bulgu** geldi. Hepsi ilk taslağı
değiştirdi:

1. **Krarup yanlış atfedilmişti.** İlk taslak `vs_replanned` rejimini Krarup vd.'nin yeniden
   planlama adımı sanıyordu. Tanım 4 birinci elden okununca: model kısıtlaması, kısıtlı modelin
   planlarının orijinalin **alt kümesi** olmasını şart koşuyor; yeniden ağırlıklandırma plan
   kümesine dokunmuyor, yalnız yeniden fiyatlıyor. Bu bir **revizyon**. Düzeltildi ve modül
   docstring'i bunu açıkça yazıyor. Ayrıca doğru eşleşme **ters**miş: Krarup'un yöntemine
   karşılık gelen **(i)** rejimi (φ = "plan tam olarak alternatif" total kısıtlaması).
2. **(c)'nin evi XAIP değil.** Dört kaynağın hiçbirinde ağırlık karşı-olgusalı yok; soru
   **ters kısayol problemi** (Burton & Toint 1992) ve genel olarak **ters optimizasyon**
   (Heuberger). `CONTRASTIVE_QUOTED` buna göre kuruldu.
3. **"Minimum" kelimesi hak edilmiyordu.** Tek-eksenli kesit bir norm minimize etmiyor.
   Alan `per_criterion_flip_threshold` olarak yeniden adlandırıldı ve gerçek ℓ₂-minimizer
   (`l2_minimal_joint_move`) yanına kapalı formda eklendi.
4. **Tarama aralığı işaret körüydü.** İlk taslak her zaman `[w*, üst sınır]` tarıyordu; ΔI_k > 0
   olduğunda kazanan bölge `[0, w*]` ve `[w*, üst]` **kanıtlanabilir biçimde boş**. Yön artık
   ΔI_k'nın işaretinden türetiliyor ve testle çivili.
5. **Kapı sırası yanlıştı** (§ (a)).
6. **Kelepçe tek bir ağırlıkta doğrulanmıştı**, sonra bütün [0,2]⁵ üzerinde akıl yürütülüyordu.
   Artık her değerlendirilen ağırlıkta, her iki rotada ölçülüyor.
7. **`risk_alpha` bant olarak yanlıştı** (§ Çözünürlük). Yerine klon topluluğu kondu.

**Ölçüm (Site11, `scripts/contrastive_explanation_report.py` →
[contrastive_explanation_report.md](../../research/contrastive_explanation_report.md)):**

- **Kimlik tam.** Yeniden kurulan g-skoru üç standart çiftte de yayımlanan
  `total_weighted_cost`'u alanın kendi yuvarlamasına kadar veriyor.
- **Dört kategorinin dördü de çıktı:** 9 vakada `hard_gate` 3 (üç çiftte de **düz çizgi**),
  `dominated_on_every_criterion` 2 (inşa edilmiş sapma), `found_vs_fact_only` 4,
  ve kriter düzeyinde `outside_weight_bounds` bolca.
- **Konvekslik tutuyor** (min ikinci fark −6,8e-13, n=39). **Monotonluk ölçümü boş**: yüklem
  41 noktanın hiçbirinde doğru olmadı, dolayısıyla "monoton" hükmü vakumda doğru ve
  raporlanmıyor.
- **Yeniden-planlanan rejim hiç ateşlemedi.** Üç çiftte de hiçbir tek-eksen ağırlığı
  planlayıcıyı alternatifi döndürmeye ikna etmedi. Kurulabilen tek cümle (i) rejiminin cümlesi.
- **Manşet:** bantlı 4 vakanın **2 tanesinde** fark arazi topluluğunun standart sapmasının
  altında kaldı ve cevap `closer_than_the_model_resolves(level=terrain_ensemble)` oldu.
  *Ay gecesi / sapma* çiftinde nominal DEM "planlayıcının rotası 3,68 ağırlıklı metre ucuz"
  diyor; NASA'nın 20 klonunun **4 tanesinde işaret ters dönüyor**.
- **Kapılar tek bir rasterin özelliği.** Gündüz çiftinde planlayıcının **kendi** rotası
  20 klonun **6'sında**, alternatif **10'unda** sert kapıya takılıyor. VIPER kısa leg'de
  (15° limit) **her iki rota da 20/20 klonda** takılıyor — o senaryoda arazi bandının
  kullanılabilir tek üyesi bile yok.
- **Bütçe:** yineleme 0,2206 s (0,1049 grid + 0,1157 A\*); 41 noktalık tarama 10,0 s.

**Bit-eşitlik:** LPR-1 v5 maliyet-gridi SHA-256 özeti
`55e1bb3cd3b9fb93403140b283cfa38fef8b93836a28512bc95f38db5ed893db` kıpırdamadı,
`COST_MODEL_ID` `…_v5`'te, `pathfinder.py` değişmedi. Testle kilitli.

**Test tabanı:** D4 öncesi ölçülen referans 25 failed / 2 384 passed / 5 skipped (27:44),
25 başarısızın hepsi `*_real_grid.py`'de ve disk penceresi (2400, 2500) ile test paketinin
beklediği (1500, 1000) arasındaki farktan kaynaklanıyor — D4'ün işi değil.
`ruff check backend/app` tabanı 12; D4 bunu artırmadı, yeni dosyalar 0 veriyor.
