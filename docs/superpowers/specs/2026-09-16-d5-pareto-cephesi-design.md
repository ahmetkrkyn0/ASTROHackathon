# D5 — Ağırlık simpleksi taraması ve baskın-olmayan rota ailesi — Tasarım Belgesi

**Tarih:** 16 Eylül 2026 · **Dal:** `tuna/backendEnhance`
· **Kaynak madde:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § D5](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
· **Bağımlılık:** B2 (`/api/risk-sweep` deseni), C4/C5 (v5 maliyet gridi ve SHA kilidi)

**Yol:** Var olan 2-B planlayıcıyı ağırlık simpleksinden çekilmiş çok sayıda vektörle koşturmak,
rotaları **hücre dizisine** göre tekilleştirmek, dört hedefli baskınlık süzgecinden geçirmek ve
**hayatta kalan kümenin ne kadar dar olduğunu** ölçülmüş sayılarla yayımlamak.

**Kapsam:** Yeni `backend/app/pareto.py`, yeni `POST /api/pareto` (yalnızca ekleme), rapor betiği,
testler, sözleşme eki. **Yeni fizik yok, yeni dış veri yok, planlayıcıya dokunulmuyor.**

---

## D5 bir ARAMA + SUNUM özelliğidir

C1/C2 birer model özelliğiydi (yeni fizik). C5 bir doğrulama özelliğiydi (dış veriye karşı sayı).
D5 ikisi de değil. Sonucu: **bit-eşitlik burada "nominal rota değişmedi" demektir** — varsayılan
ağırlıklarla üretilen rota D5'ten önce ne ise o kalır, LPR-1'in checked-in v5 maliyet-gridi
SHA-256 özeti kıpırdamaz, `COST_MODEL_ID` `…_v5`'te kalır.

---

## Ağırlık uzayı ile hedef uzayı AYRI şeylerdir

### Ağırlık uzayı (girdi) — hücre başı maliyet kriterlerinin ağırlıkları

**Ölçüldü (`get_rover` üzerinden doğrudan):** katalogdaki dört rover profilinin de **ilk dört
ağırlığı tam olarak 1,0 topluyor**; `w_roughness = 0,15` üstüne **toplanan** bir terim ve yeniden
ölçeklenmiyor (`constants.py:208-217` bunu açıkça yazıyor).

| rover | w_slope | w_energy | w_shadow | w_thermal | ilk dördün toplamı |
|---|---|---|---|---|---|
| `lpr_1` (varsayılan) | 0,409 | 0,259 | 0,142 | 0,190 | **1,0000** |
| `nasa_viper` | 0,35 | 0,25 | 0,20 | 0,20 | **1,0000** |
| `luvmi_m` | 0,40 | 0,30 | 0,30 | 0,0 | **1,0000** |
| `cnsa_yutu_2` | 0,50 | 0,30 | 0,20 | 0,0 | **1,0000** |

Tarama bu yüzden **4-simpleks** üzerinde yapılır, `w_roughness` rover varsayılanında tutulur.
Simpleks deponun kendi kuralıdır, D5'in icadı değil. (ETH `lunar_planner` de aynı: `α+β+γ = 1`.)

### Hedef uzayı (çıktı) — rota düzeyi sonuçlar

Her hedefin **yönü açıkça saklanır** (`direction`), varsayılmaz. Dördü de küçük-iyi:

| hedef | kaynak alan | birim | yön | yayın kuantumu |
|---|---|---|---|---|
| `hours` | `summary["total_elapsed_hours"]` | saat | `minimize` | 1e-4 |
| `energy_wh` | `summary["total_energy_consumed_wh"]` | Wh (brüt çekim) | `minimize` | 1e-2 |
| `shadow_exposure_h` | `summary["total_shadow_exposure"]` | saat (gölge-oranı ağırlıklı) | `minimize` | 1e-4 |
| `thermal_risk` | `astar_metrics["max_thermal_risk"]` | MRU [0,1] | `minimize` | 1e-4 |

**Görev tanımının öncülü tutmadı ve düzeltildi.** Brief dördüncü hedefi "termal **marj**, büyük
iyi" diye tarif ediyordu. Bu depoda rota düzeyinde böyle bir marj **yok**: olan şey
`max_thermal_risk`, `f_thermal`'in rota boyunca **maksimumu**, bir **ceza**
(`pathfinder.py:767`). Marj yalnızca `safety_margins[*].rho` (D3) bloğunda ve o ayrı bir
büyüklük. D5 cezayı kullanır, adını `thermal_risk` koyar, yönünü `minimize` yazar.

**`shadow_exposure_h` bilerek "gölge saati" değil.** Alan `Σ shadow_ratio_i · Δt_i`
(`simulation.py:405-410`) — ikili gölge saati değil, oran-ağırlıklı bir integral; ad tanımı taşıyor.

**Her şey API'nin kendi yayın hassasiyetinde karara bağlanır.** Hedefler onları yayımlayan
fonksiyon tarafından zaten yuvarlanmış geliyor, dolayısıyla "farklı" da "baskılanmış" da yuvarlanmış
sayılar üzerinden karar. Kuantumun altındaki bir epsilon anlamsızdır ve tek kuantumluk bir fark
sıralama değildir; bu yüzden varsayılan epsilon **alanın kendi kuantumudur**.

---

## Belgenin dayattığı üç soru (ve cevapları)

### (a) `profile_comparison.py` bugün ne yapıyor; D5 onu genişletiyor mu, yerine mi geçiyor?

**Ne genişletiyor ne de yerine geçiyor — dokunulmuyor.** O modül **adlandırılmış** mission
profillerini çözer: `solve_profile` bir profil sözlüğü ister (`weights`, `constraints`, `name`,
`color`) ve her rotaya `attach_constraint_check` ile simülasyon + D3 güvenlik monitörü + C3 slip
bloğu takar. D5'in ihtiyacı bunun aksi: **isimsiz, keyfi** ağırlık vektörleri ve örnek başına
mümkün olan en ucuz çözüm.

Kesin sebep: `profile_comparison` **`ai_tools.py:34` tarafından import ediliyor** — asistanın
çalıştırmasına izin verilen tek planlama yolu. Onu keyfi ağırlık alacak şekilde genişletmek o yolu
riske atardı. Ayrıca güvenlik monitörü örnek başına ödenecek ve D5'in okumadığı bir maliyet.

Karar: **yeni `backend/app/pareto.py`**, `/api/risk-sweep`'in kendi gövdesinde yaptığı gibi
`astar` + `simulate_path` + `summarize_simulation` çağırır.

### (b) `/api/risk-sweep` ile `/api/pareto` arasındaki sınır ne?

| | `/api/risk-sweep` (B2) | `/api/pareto` (D5) |
|---|---|---|
| taranan | `risk_alpha`, ≤ 6 değer | ağırlık simpleksi, ≤ 40 vektör |
| ağırlıklar | **sabit** (istekteki tek vektör) | **taranan şey** |
| neyi değiştirir | sıralama maliyetinin **kuyruğu** | sıralama maliyetinin **karışımı** |
| çıktı | her α'nın rotası + `risk_matrix` (rota × α) | **baskın-olmayan** alt küme + dejenerasyon teşhisi |
| referans | nominal rota | yok; kıyas kümenin kendisi |

Tek uçta toplanmamalı: B2 her rotayı her α'da **yeniden fiyatlandırır** (kuyruk sorusu), D5 ise
rotaları **hedef uzayında** sıralar (baskınlık sorusu). Birleştirmek iki farklı soruyu tek yanıtta
karıştırırdı.

### (c) Hedef vektörünün dört bileşeni hangi alanlardan geliyor?

Üçü `summary`'den, biri `astar_metrics`'ten — yukarıdaki tabloda tek tek yazılı. **Hiçbiri
türetilmiyor.** Türetilen tek şey baskınlık ilişkisinin kendisi.

---

## Yöntemin sınırı — ve brief'in terminolojisinin düzeltilmesi

Ulaşılabilen çözümlere **supported**, ulaşılamayanlara **unsupported** denir.
**Brief'in önerdiği "duality gap" bu literatürün terimi değildir ve yazıya girmedi.**

Birinci elden okunan kaynaklar: **Boyd & Vandenberghe §4.7.4** (*"The value f₀(x₃) is Pareto
optimal, but cannot be found by scalarization"*; tamlık ancak problem dışbükeyse),
**Das & Dennis 1997** (*"succeeds in getting points from all parts of the Pareto set only when the
Pareto curve is convex"*), **Könen & Stiglmayr arXiv:2501.13842 Tanım 1.11** (terminolojinin
kendisi), **Miettinen'in kendi slaytı** (*"Nonconvex problems: some of the PO solutions may fail to
be found"*).

### Bu depoda sınır daha da dardır

Kritik incelik: buradaki ağırlıklar **hedefleri** skalerleştirmiyor, **hücre başı maliyet
kriterlerini** ağırlıklandırıyor; bunlar yol boyunca toplanıp tek bir g-skoruna dönüşüyor. Rota
düzeyi hedefler ise yolun **başka** fonksiyonları. Dolayısıyla:

> Dışbükeylik teoremi "**hedeflerin** ağırlıklı toplamını minimize edersen desteklenen bir etkin
> nokta bulursun" der. Burada **kriterlerin** ağırlıklı toplamı minimize ediliyor. Bu yüzden
> **hiçbir tamlık garantisi geçerli değildir** — durum "yalnız dışbükey kabuk"tan da zayıftır.

Yanıt alanları bu yüzden: `method: "weighted_sum_scalarisation_over_cost_criteria"`,
`completeness: "no_guarantee"` (+ `completeness_note`). Üretilen kümenin adı **`non_dominated`**;
yanıt `pareto_front` anahtarını **taşımaz**.

### `pymoo` / NSGA-II — kapsam dışı, gerekçesiyle

`backend/requirements.txt`'te her şey `==` ile pinli ve `pymoo` **yok** (doğrulandı). Yeni bağımlılık
ayrı bir karardır; C5'te aynı durumla `pandas` için karşılaşıldı (10× hızlıydı) ve **eklenmedi**.

---

## ÖLÇÜLENLER (gerçek Site11 gridi, 16 Eylül 2026)

Pencere (2400, 2500), 500×500, 5 m/px. Örnekleyici: normalize edilmiş `standard_exponential`
(= Dirichlet(1,1,1,1)), tohum 20260916. Rapor:
[`docs/research/pareto_front_report.md`](../../research/pareto_front_report.md).

### Dört senaryo, senaryo başına 25 ağırlık vektörü (24 rastgele + rover varsayılanı)

| senaryo | rover | vektör | **farklı rota** | **baskın-olmayan** | vektör/rota | ms/örnek |
|---|---|---|---|---|---|---|
| LPR-1 gündüz | `lpr_1` | 25 | 17 | **1** | 1,47 | ~330 |
| LPR-1 Ay gecesi | `lpr_1` | 25 | 24 | **1** | 1,04 | ~1 370 |
| VIPER standart | `nasa_viper` | 25 | 21 | **1** | 1,19 | ~337 |
| VIPER kısa leg | `nasa_viper` | 25 | 15 | **2** | 1,67 | ~322 |

**Senaryolar ayrı ayrı sunuluyor**, tek cepheye havuzlanmıyor (C5'in havuzlama dersi).

### Dördüncü eksen ölü

`f_thermal`, geçilebilir hücrelerde: `lpr_1` 210 063 hücrenin **%72,7'sinde ≥ 0,99**
(medyan 0,9994); `nasa_viper` 161 793 hücrenin **%65,2'sinde** (medyan 0,9990).
`max_thermal_risk` doygun bir alanın maksimumu olduğu için dört senaryonun üçünde **tek değer**
alıyor. **Bu bir keşif değil**, doygunluğun yeniden ifadesi — ve sabit bir eksen hiçbir çifti
ayıramayacağı için "dört hedefli cephe" aslında **üç** hedeflidir. Yanıt bunu
`constant_objectives` / `effective_objectives` ile söylüyor.

### Kalan eksenler aynı sıralamayı veriyor (Spearman, **farklı rotalar** üzerinden)

| senaryo | n | etkin hedef | saat~enerji | saat~gölge | enerji~gölge |
|---|---|---|---|---|---|
| LPR-1 gündüz | 17 | 3 | 0,9994 | 0,7735 | 0,7779 |
| LPR-1 Ay gecesi | 24 | 3 | 0,9954 | 0,6178 | 0,6455 |
| VIPER standart | 21 | 3 | 0,9951 | 0,8886 | 0,9182 |
| VIPER kısa leg | 15 | 4 | 1,0000 | 0,9857 | 0,9857 |

Pearson değil Spearman, ve **ham örnekler değil farklı rotalar** üzerinden: ham örnekler aynı
rotayı onu bulan her vektör için bir kez sayar ve katsayıyı şişirir. Bu n'lerde korelasyon
**betimleyicidir**, güven aralığı iddia edilmiyor.

### Bütçe eğrisi — ilk manşetin düzeltilmesi

İlk ölçüm (n=24) "cephe tek noktaya çöküyor" diyordu; **bütçe büyütülünce bu iddia kısmen düştü**
ve düzeltilmiş hâli yayımlandı (LPR-1 gündüz):

| n | ağırlık vektörü | farklı rota | **baskın-olmayan** |
|---|---|---|---|
| 8 | 9 | 9 | 1 |
| 24 | 25 | 17 | 1 |
| 60 | 61 | 35 | 1 |
| 100 | 101 | 45 | **3** |
| 200 | 201 | 61 | **3** |
| 200 + köşeler | 211 | 65 | **4** |

Tek nokta **değil**, ama bütçeden çok daha yavaş büyüyor. Simpleksin bir **köşesi**
(`w_slope = 1`) cephede: iç bölgeden çekilen vektörler onu hiç bulamaz, bu yüzden
`include_corners` var.

### Manşet: hayatta kalanlar kendi gürültülerinin içinde

| hedef | **cephe genişliği** | tüm rotaların genişliği |
|---|---|---|
| `hours` | **%0,179** | %22,226 |
| `energy_wh` | **%0,221** | %36,734 |
| `shadow_exposure_h` | **%0,556** | %21,571 |

Aynı rotaya B2'nin CVaR slip kuyruğu (farklı rota değil; modelin o rotayı ne kadar bildiği):
α = 0,5 → **+%16,90**; α = 0,9 → +%58,46; α = 0,99 → **+%107,95**.

**Cephe, modelin en iyimser belirsizlik bandından ~94× dardır.** Cephe içindeki her "A, B'yi
baskılıyor" ifadesi bu gürültünün çok içinde kurulmuştur.

### Nominal rota cephede mi? — Hayır, ve bu bir bug değil

Gündüz çiftinde rover varsayılanının rotası baskılanıyor: kazanan üç hedefte daha iyi,
`thermal_risk`'te **berabere** (sabit eksen). Kayıp **%0,14 / %0,34 / %0,29** — yani yukarıdaki
bandın iki mertebe altında. Bug değil: varsayılan vektör **ağırlıklı maliyeti** minimize eder, bu
dört hedeften hiçbirini değil. **"Varsayılan ağırlıklar yanlış" cümlesi bu ölçümden çıkmaz.**
("Dört hedefte de katı biçimde baskılanıyor" demek **yanlış olurdu**; dördüncüde eşitlik var.)

---

## Manşet bulgu (yayımlanan hâliyle)

Ağırlık tartışması bu arazide **iki ayrı sorudur**:

1. **Kötü bir vektör seçmek ölçülebilir bir hatadır** — örneklenen aralık saatte %22,2 geniş.
2. **İyi vektörler arasında seçim yapmak bu modelin çözemeyeceği bir sorudur** — hayatta kalanların
   arası %0,18, modelin kendi bandının ~1/94'ü.

Cephenin asıl faydası "operatör cepheden seçsin" değil, **bu arazide seçilecek bir şey olmadığını
ölçüyle göstermek**tir.

**Sebep kurulmadı.** Darlık ölçüldü; "arazi" ile "bu arazide bu maliyet modeli" bu ölçümle
ayrılamaz. Depo zaten katmanların tek bir yükseklik gridinden türediğini ve iki kriterin
Spearman'ının tam 1,000000 ölçüldüğünü (`cost_engine.py`) kaydetmişti — D5 bunun **sonucunu**
ölçüyor, keşfetmiyor.

---

## Dominans, kimlik, epsilon

**a, b'yi baskılar** ⇔ her i için `a_i ≤ b_i + ε_i` **ve** bir j için `a_j < b_j − ε_j`
(yönler uygulandıktan sonra).

- **Epsilon:** hedef başına, varsayılanı **alanın kendi yayın kuantumu**. Sıfır olsaydı cephe
  yuvarlamanın bir artefaktı olurdu.
- **Rota kimliği:** sıralı `(row, col)` dizisinin SHA-256'sı. Hedef vektörüne göre değil — farklı
  vektörler aynı diziyi üretiyor (ölçüldü: 211 vektör → 65 rota).
- **Mahsur rotalar dışlanır**, yalnız işaretlenmez: totalleri yalnız yürüyebildiği öneki anlatır,
  yani **erken başarısız olarak** cepheye girerdi.

---

## Örnekleyici

`default_rng(seed).standard_exponential((n,4))` satır toplamına bölünür — Dirichlet(1,1,1,1)'in ta
kendisi, ama akış `dirichlet`'in iç uygulamasına bağlı değil. **Ölçüldü:** ikisi numpy 2.2.1'de
en fazla **1,11e-16** (1 ULP) ayrılıyor, 128 bileşenin 28'inde son bitte — yani **bit-eşit
değiller**. 1 ULP'lik bir kayma iki yakın vektörü yeniden sıralayıp rotayı oynatmaya yeter; bu
yüzden testin dayandığı çekiliş bizimkidir.

---

## Ölçek ve süre kararı

- **Uç nokta `n_samples` ≤ 40** (varsayılan 24). En kötü hâl (Ay gecesi, ~1,37 s/örnek) ≈ **55 s**,
  tek senkron istekte. `total_ms` ve örnek başına `plan_ms` döndürülüyor.
- **Modül API'sinin tavanı yok**; rapor betiği n=200 ile çevrimdışı koşuyor. Ağır tarama HTTP'ye
  sokulmuyor.
- **4-B kapsam dışı**: örnek başına 6-17 s; 24 örnek ~7 dakika. B2 de `/api/risk-sweep`'i 2-B ile
  sınırladı.
- **Önbellek patlaması yok** (ölçüldü): `grids_for_rover` hiç memoizasyon içermiyor. `data_loader`'ın
  ağırlığı anahtarına katan **disk** önbelleği yalnız `load_grids(use_cache=True)` yolundan
  erişiliyor; `/api/pareto` o yolu çağırmaz (yüklü `base_grids` üzerinden çalışır).

---

## Bit-eşitlik

- LPR-1 v5 maliyet-gridi SHA-256 `55e1bb3c…893db` kıpırdamayacak (testte).
- `COST_MODEL_ID` `…_v5`'te kalacak (testte).
- Nominal örneğin rotası, ağırlık verilmeden çağrılan `astar`'ın rotasıyla **aynı** (testte).
- Kilit **LPR-1'e** kurulu; `nasa_viper`'ın özeti 4af6989'dan beri tutmuyor ve D5'ten önce de
  tutmuyordu — bayat kilide iddia bağlanmaz.

---

## Bayat etiket düzeltmesi (C2/C5 deseni)

`constants.py:208-215` ağırlıkların **"gradient-normalised expert weights, not AHP"** olduğunu
yazarken kod **7 yerde** hâlâ "AHP" diyordu: `costmap.py:342`, `cost_engine.py:98/267/371/378/1166`,
`pathfinder.py:5/69`. 11 no'lu belge bu etiketin yanlış olduğunu zaten söylemişti ve D5'in araştırma
maddesi tam bu tartışmayı kapatmak için açılmıştı. D5 düzeltti; **yalnızca yorum ve docstring**
değişti, tek bir ifade değişmedi.

---

## Hata davranışı ve 422'ler

`/api/risk-sweep`'in sözleşmesi kopyalanıyor: bir örneğin rota bulamaması **hata değil**, o girdinin
`error` alanı (HTTP 200). 422'ler: `n_samples` aralık dışı, `seed` negatif, bilinmeyen hedef adı ya
da negatif `epsilon`, bilinmeyen `rover_id`, grid dışı ya da geçilemez start/goal. Grid yüklü
değilse 503.

---

## Kapsam dışı (ve nedeni)

- **`pymoo` / NSGA-II** — yeni pinli bağımlılık, ayrı karar (C5'in `pandas` emsali).
- **4-B tarama** — örnek başına 6-17 s; HTTP'ye sığmaz.
- **Frontend çizimi** — frontend koduna dokunulmuyor; yalnız sözleşme eki. "Operatör cepheden seçer"
  bir **arayüz** iddiasıdır.
- **Hipervolüm** — cephe 1-4 elemanlı ve kendi gürültüsünün içinde; tek bir hipervolüm sayısı bu
  darlığı gizlerdi. Genişlik ve gürültü bandı doğrudan yayımlanıyor.
- **Termal marjın hedefe çevrilmesi** — `safety_margins.rho` ayrı bir büyüklük (D3'ün bloğu).
- **Sebebin kurulması** — kriter eşdoğrusallığı ayrı bir çalışma.

---

## Uygulama sırasında bulunanlar ve ölçümler

### Ne ölçüldü

| bölüm | n | sonuç |
|---|---|---|
| Dört senaryo | 25 vektör/senaryo | 15-24 farklı rota → **1-2** baskın-olmayan |
| Bütçe eğrisi | 9 → 211 vektör | cephe **1 → 4**; farklı rota 9 → 65 |
| Cephe genişliği | 4 baskın-olmayan | saat **%0,179** ↔ tüm rotalar %22,226 |
| Model bandı (B2 CVaR) | aynı rota | α=0,5 **+%16,90** … α=0,99 **+%107,95** |
| `f_thermal` doygunluğu | 210 063 / 161 793 hücre | %72,7 / %65,2 ≥ 0,99 |

### Beklenmedik 1: ilk manşet kendi ölçümümde düştü

n=24'te cephe **1** elemandı ve "cephe tek noktaya çöküyor" yazılacaktı. n=100'de **3**, köşelerle
**4** oldu. Yayımlanan iddia düzeltildi: cephe tek nokta değil, **bütçeden çok daha yavaş büyüyor**.
Küçük bir bütçeyle ölçüp genellemek bu özellikte en kolay hatadır.

### Beklenmedik 2: raporun kendisi yanlış sütunu basıyordu

İlk üretilen raporda "cephenin genişliği" tablosu aslında **tüm rotaların** genişliğini (%22,2)
basıyordu, cephenin değil (%0,18) — `diagnostics` bloğu tüm rotalar üzerinden hesaplanmıştı.
§5'teki oran da bundan yanlış çıkıyordu. Düzeltildi; rapor artık iki sütunu **yan yana** basıyor,
çünkü asıl bulgu ikisinin **oranı**.

### Beklenmedik 3: örnekleyici numpy'ın `dirichlet`'iyle bit-eşit değil

Test bunu yakaladı: fark **1 ULP** (1,11e-16), 128 bileşenin 28'inde. `array_equal` iddiası
`allclose` + "bilerek bit-eşit değil" iddiasına çevrildi.

### Düşmanca incelemenin düzelttikleri

Kod yazılmadan önce beş bağımsız lens tasarıma saldırdı; şunlar **yayımlanmadan** düzeltildi:
- "Dört hedefte de **katı** biçimde baskılanıyor" → dördüncüde **eşitlik** var (sabit eksen).
- Pearson → **Spearman**, ve **farklı rotalar** üzerinden (ham örnekler pseudo-replikasyon).
- "ρ ≥ 0,998" → gece çiftinde **0,62-0,65**; iddia olduğu gibi yanlıştı.
- "Dejenerasyon **arazinin**" → D5 sebebi **kuramaz**; depo zaten eşdoğrusallığı kaydetmişti.
- Kuantizasyon tuzağı → epsilon varsayılanı alanın **kendi kuantumu** yapıldı.
- Probe 3 tablosundaki ölçülmemiş hücre dolduruldu (sonuç değişmedi: 1/17, 1/24).

### Sapmalar (plandan)

- `include_corners` tasarımda yoktu; köşe ölçümü onu gerektirdi (varsayılan `False`).
- Mahsur rotalar yalnız işaretlenecekti; **dışlandılar** — erken başarısızlık cepheye girerdi.
- Hedef sayısı "dört" diye duyurulmayacak: `effective_objectives` sabit eksenleri düşüyor.

### Doğrulama

- Temiz HEAD (a627b05) referansı **kendim ölçüldü**: **25 failed / 2 318 passed / 5 skipped
  (32 dk 25 s)**; 25'inin hepsi `*_real_grid.py`'de ve hepsi önceden vardı (pencere kayması).
- Tam paket, D5 ile: **25 failed / 2 384 passed / 5 skipped (26 dk 59 s)**.
  2 318 + 66 = **2 384** — eklenen testlerin tamamı geçti.
- **FAILED listeleri `comm` ile karşılaştırıldı: birebir aynı.** Ne yeni kırmızı var, ne de
  D5'in tesadüfen düzelttiği bir test. Sıfır regresyon.
- `ruff check backend/app` → **12** (değişmedi); yeni dosyalar (`pareto.py`, üç test,
  rapor betiği) → **0**.
- D5'in 66 testi son kodla ayrıca koşuldu: **66 passed (14,3 s)**.
- Rapor `--from-json` ile **birebir** yeniden üretiliyor (iki kez doğrulandı).
