# C3 — Slip modelinin uçmuş/yer-test verisiyle kalibrasyonu (Yutu-2, VIPER; termal atalet kancası) — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → C3](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** Enerji/süre modeli (`cost_engine.edge_travel_time_s` ve ondan türeyen `edge_energy_wh`, `gross/net_energy_per_metre_wh`, `move_battery_drain_wh`), 4-B planlayıcı (`pathfinder_4d.astar_4d`, satır içi drain aritmetiği), A1'in kapılı kenar grafı (`safe_haven._gated_edges`), A2'nin kenar tabloları (`illumination_corridor.edge_tables`), `cost_cube.auto_slice_hours`, 2-B simülatör (`simulation.simulate_path`), B5 Monte Carlo (`stress_test.route_legs`), D3 monitörü (yalnızca okuyucu). **B2 (CVaR) bu özelliğe bağımlıdır:** slip artık tek sayı değil, `(μ, σ)` olarak sorulabilir; B2 kapsam dışıdır.
**Kapsam:** `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

`slip_model.py` bugüne kadar **yön** iddiası taşıyordu, **büyüklük** iddiası taşımıyordu:
`SLIP_MODEL_VALIDITY = "UNCALIBRATED"`, `slip_ratio = 0,02·exp(0,11·|θ|)` ("kabaca
literatür biçimli" katsayılar), ve modül docstring'i açıkça "`effective_distance_m` ve
`slip_energy_multiplier` **kasıtlı olarak** maliyet motoru, simülasyon, koridor ve 4-B
planlayıcı tarafından çağrılmıyor; kalibre edilmemiş bir katsayıyı rota seçen sayıya
bağlamak yanlış olur" diyordu (Round 2 review, L-2). Sonuç: üründeki **her** enerji ve
süre sayısı slip'siz, yani sistematik iyimser (05_engel_kacinma.md 3.1; B5'te VIPER
rotasının en düşük bataryası %32 → MC nominalde %23; B3'te sürüş enerjisi %6–10 iyimser).

Bu özellik o engeli **doğru sırayla** kaldırır: önce kaynak ve kalibrasyon, sonra bağlama.

1. Eğri artık **kaynaklı çapalardan** (anchor) geçer: VIPER'ın PSJ 2025'te yayımlanan
   tasarım gereksinimi ("15° eğimde en fazla %40 slip") ve Yutu-2'nin Chang'e-4'te
   **ölçülmüş** slip aralığı (0 … −0,075, en fazla 8,86° eğimde). Kaynağı olmayan hiçbir
   çapa katalogda yoktur; her çapanın `source` alanı zorunludur.
2. Eğri **tek noktadan** modele bağlanır: `edge_travel_time_s` içinde komutlanan mesafe
   etkin tekerlek mesafesine dönüşür (`d → d/(1−s(θ))`). Süre ve enerji birlikte büyür;
   planlayıcı, simülatör, koridor, Monte Carlo, safe-haven süreleri ve koridor dilimleri
   tek bir formülü paylaştığından hepsi tutarlı kalır.
3. Etiket `"UNCALIBRATED"` → `"MODEL"` (literatüre bağlı). **`"MEASURED"` asla değil:**
   kutup regolitinde ölçülmüş slip yok (Diviner de yerelde yok).
4. B2 kancası: `slip_stats(θ, rover) → (μ, σ)`.
5. Termal atalet fikri (Cunningham, Nesnas, Whittaker; RSS 2017) yalnızca **tasarım notu
   ve fonksiyon imzası**: Diviner indirilmeden "termal atalet ile modüle edildi" denmez.

Tek cümlelik iddia (sunum): **"Slip eğrimiz VIPER'ın 15°/%40 tasarım kısıtına ve
Yutu-2'nin ölçülmüş regolit parametrelerine bağlı."**

**İddia sınırı (her yanıtta ve belgede):** Eğri **ölçülmüş değil, literatüre bağlı bir
MODEL**dir. VIPER'ın %40'ı bir **tasarım üst sınırı**dır (GRC-1 simülantı, %15–20 bağıl
yoğunluk, MGRU yer testi), tipik değer değil. Yutu-2'nin 0 … −0,075 slip oranı **ölçülmüş**
ama Chang'e-4 bölgesinde (uzak yüz, mare), ≤ 8,86° eğimlerde ve çoğunlukla **skid**
(negatif) koşulunda; kutup regoliti değil. Çapalar arası ve ötesi biçim (üstel) ve iki
çapanın diğer rover'lara aktarımı **varsayımdır** ve `source` alanında "assumption:" ile
yazılıdır. "Kutup regolitinde ölçüldü" **denmez**.

## Kaynak ve yöntem notu

### Yutu-2 (Chang'e-4) — ölçülmüş (Nature Communications 2024, açık erişim; Science Robotics 2022)

Tri-aspect digital-twin çalışmasından (PMC11258293), doğrulanmış alıntılarla:

- Slip oranı: *"most the wheel slip ratios are between 0 and −0.075 and no less than −0.1"*
  (Methods, "Lunar regolith parameter estimation"). İşaret kuralı: `s > 0` slip,
  `s < 0` skid (Methods, Eq. 8 sonrası). Yani tekerlekler çoğunlukla **skid**
  koşulunda: gövde tekerlekten hızlı. Simülasyon medyanı iç sürtünme açısına göre
  −0,035 … −0,002 (Supp. Fig. 6a).
- Arazi eğimi: giden yolculukta en fazla **8,86°**, sonda 5,38° (Results, "Topographic
  and mobility hazards analysis"). Eğimler krater kenarlarında.
- Regolit: iç sürtünme açısı **21,5–42,0°**, kohezyon **520–3 154 Pa**, batma üssü N
  **0,87–1,0**, ortalama tekerlek batması **~8 mm**, taşıma **~4 kPa** (Results,
  "Mechanical property identification", Fig. 4).

**Modele girişi.** Bu ölçüm bize "0–8,86° eğimlerde |s| ≤ 0,075" der. İki çapa:
`0° → 0,0375` (ölçülen |0 … 0,075| aralığının orta noktası; işaret atıldı — modelimiz
skid'i ayırt etmez, yalnızca kaybedilen ilerlemeyi sayar; `kind: "measured"`) ve
`8,86° → 0,075` (aralığın üst ucu, sürülen en dik eğimde; `kind: "measured_bound"`).
σ = aralık/4 = 0,01875 (aralık ≈ ±2σ varsayımı; `source`'ta yazılı).

### VIPER — tasarım kısıtı, yer testi (Planetary Science Journal 2025)

*"The mobility design requirements of the VIPER mission defined a maximum of 40% slip up
a maximum slope of 15°"* (§3.5). Testler MGRU (Moon Gravity Representation Unit) ile,
**GRC-1** simülantında, **%15–20 bağıl yoğunluk** (gevşek) (§3.2). Slip, tekerlek
dönüş hızlarının ortalaması ile aracın Optitrack hareket-yakalama hızından (§3.2) —
araştırma belgesindeki "enkoder+VO" ifadesi burada düzeltildi. Fig. 9 slip'in eğimle
arttığını gösterir ama metinde sayı yok.

**Modele girişi.** Tek çapa `15° → 0,40` (`kind: "design_constraint"`; üst sınır, tipik
değer değil). σ için yayımlanmış yayılım yok: Yutu-2'nin bağıl yayılımı (σ/μ = 0,5)
**varsayım olarak** aktarılır → σ = 0,20 (`source`'ta "assumption:").

### Çapalar arası biçim: parçalı log-doğrusal (üstel), son parça ötesine uzatma, kap

Eğri iki çapa arasında **log(s)'de doğrusal** (yani üstel) ilerler; bu, mevcut modelin
`I0·exp(K·θ)` biçimiyle ve gevşek zeminde slip-eğim eğrilerinin dışbükey biçimiyle
(MER'in kum üzerindeki slip-eğim ölçümleri, Angelova vd. JFR 2007; terramekanik
modeller, Ishigami vd. JFR 2007) tutarlıdır; **biçim bir varsayımdır** ve öyle etiketlenir.
İlk çapa 0°'de olmalıdır (doğrulama). Son çapanın ötesinde son parçanın log-eğimi devam
eder ve `MAX_SLIP_RATIO = 0,9`'da kesilir (mevcut kap; s → 1 aritmetiği sonsuza götürür).
İşaret simetrisi `|θ|` ile korunur. Parçalı doğrusal alternatif değerlendirildi ve
reddedildi: 0 → 15° arası doğrusal 5°'de %16 verir; Yutu-2'nin 0–8,86°'de ≤ %7,5
ölçümüyle ve dışbükey literatürle çelişir.

Aday tablo (sonda 2, `MAX_SLIP_RATIO = 0,9`):

| Çapa kümesi | 0° | 5° | 8,86° | 10° | 15° | 18° | 20° | 25° | Kap eğimi |
|---|---|---|---|---|---|---|---|---|---|
| 2 çapa (Yutu-2 0° + VIPER 15°) — log-doğrusal | 0,037 | 0,083 | 0,152 | 0,182 | 0,400 | 0,642 | 0,881 | 0,900 | 20,1° |
| 3 çapa (Yutu-2 0° ve 8,86° + VIPER 15°) — log-doğrusal | 0,037 | 0,055 | 0,075 | 0,102 | 0,400 | 0,900 | 0,900 | 0,900 | 18,0° |
| 2 çapa — doğrusal (reddedildi) | 0,037 | 0,158 | 0,252 | 0,279 | 0,400 | 0,473 | 0,521 | 0,642 | — |

Süre/enerji çarpanı `1/(1−s)`: 2 çapa log-doğrusalda 0° ×1,04, 10° ×1,22, 15° ×1,67,
18° ×2,79, 20° ×8,4, ≥ 20,1° ×10.

### Hangi rover hangi çapayı alır

| Rover | Çapalar | Not |
|---|---|---|
| `cnsa_yutu_2` | Yutu-2 0° (measured), Yutu-2 8,86° (measured_bound), VIPER 15° (**assumption**: kendi 15° ölçümü yok; VIPER'ın tasarım tavanı aktarıldı) | Kendi ölçümü 0–8,86°'yi sınırlar |
| `nasa_viper` | Yutu-2 0° (**assumption**: düz zemin slip'i zemin türüne az duyarlı; GRC-1 için yayımlanmış düz-zemin değeri yok), VIPER 15° (design_constraint) | 8,86° çapası **aktarılmaz**: Chang'e-4 mare regoliti ile gevşek GRC-1 (%15–20) farklı zeminler; ikisini birleştirmek 8,86 → 15° arasında kaynaksız bir kırılma üretir |
| `lpr_1`, `luvmi_m` | Yutu-2 0° (assumption), VIPER 15° (assumption) | Yayımlanmış slip verisi yok; VIPER tavanı üst sınır olarak |

### Termal atalet (Cunningham, Nesnas, Whittaker; RSS 2017 / Auton. Robots 2019) — yalnızca kanca

Curiosity verisiyle düşük termal ataletli kumun yüksek slip verdiği gösterildi.
LunaPath karşılığı: Diviner gece sıcaklığı / termal atalet vekili, slip çapalarını
**ölçekler** (önce/sonra çarpanı). Diviner yerelde yok (`scripts/diviner_validation.py`
dosya yoksa 0 ile çıkıyor; `thermal_grid.npy` modelden, `SYNTHETIC`). Bu yüzden
`slip_model.thermal_inertia_slip_scale(thermal_inertia)` yalnızca imzadır:
`NotImplementedError` ile hangi ürünün gerektiğini söyler. Uygulama yok, iddia yok.

## Mevcut durumdan kullanılanlar

- `cost_engine.edge_travel_time_s(θ, d, rover)`: `L = d/cosθ`, `v = v_max·cosθ`, `t = L/v`.
  Tüm süre/enerji fonksiyonları buradan türer; `move_battery_drain_wh` ve
  `wait_battery_drain_wh` planlayıcı, simülatör ve Monte Carlo'nun ortak referansı (B5).
- `pathfinder_4d.astar_4d`: hamle süresi `edge_travel_time_s` (satır 964), drain satır içi
  (`travel_h` üzerinden; `test_battery_profile_matches_the_public_drain_functions`).
- `safe_haven._gated_edges`: vektörize `d/(v_max cos²)/3600` — planlayıcının işlem sırasından
  farklı (A2 notu); `time_to_safe_haven_hours` Dijkstra (SciPy csgraph) bunun üstünde.
- `illumination_corridor.edge_tables`: süreyi planlayıcının sırasıyla yeniden hesaplıyor
  (`(d/cos)/(v_max cos)`, `/3600/slice`, `ceil`); test "slices follow the planner's ceil".
- `cost_cube.auto_slice_hours`: dilim = medyan eğimde bir kaba hücre geçişi (skaler).
- `main.plan_4d` varsayılan ufuk: `move_count × ceil(worst_edge/slice) + 20`,
  `worst_edge = edge_travel_time_s(slope_max, köşegen)`.
- `constants.ROVERS` / `MODELLED_FIELDS` / `DECLARED_ONLY_FIELDS` / `rover_catalog()`;
  `costmap.LayerSpec.validity` etiketleri; `mission_reference.py`'nin "kaynak zorunlu" kalıbı.
- `cost_engine.COST_MODEL_ID` (v3): `f_energy_cell` → `net_energy_per_metre_wh` →
  `edge_travel_time_s(θ, 1)` olduğundan slip **maliyet gridine de** girer → v4.

## Sonda (tasarım öncesi, Site11, bugünkü slip'siz model)

| Rota | Dilim × saat | Hamle/bekleme | Varış (h) | En düşük SOC | LP-R01 / R02 / R06 / R07 ρ | B5 tamamlanma (1 000 koşum) / tam başarı / nominal min SOC | 2-B: mesafe / süre / tüketim / min SOC |
|---|---|---|---|---|---|---|---|
| VIPER 30 May 2027, (358,494)→(206,426), `require_safe_haven` | 100 × 0,0956 | 40 / 0 | 7,36 | %32,1 | 91,45 h / 12,06 pct / **0,48°** / 1,19° | %29,6 / %1,4 / %23,2 | 0,910 km / 4,33 h / 2 156 Wh / %67,2 |
| LPR-1 28 Eyl 2026, aynı çift | 100 × 0,0287 | 40 / 0 | 2,16 | %96,2 | 49,79 / 76,16 / 5,63 / 4,19 | %100 / %0 / %97,9 | 0,910 km / 1,30 h / 469 Wh / %95,6 |
| LPR-1 Ay gecesi 13 Eyl 2026, (186,34)→(494,450) | 246 × 0,0287 | 114 / 0 | 5,35 | %72,7 | 45,97 / 52,68 / 5,38 / 5,47 | — | 2,727 km / 3,85 h / 1 288 Wh / %88,7 |

Bulgular:
- Site11 dik: ince eğim medyanı **10,2–10,6°**, p95 18–20°; kaba blok-maks eğimleri
  p50 12–13°, p95 19–22°, maks 20/25° (rover sınırı). Planlayıcının kenar eğimi iki
  blok-maks'ın ortalaması → çok sayıda 12–19° kenar. VIPER'ın haven→haven rotası
  **19,5°'lik** kenarlar sürüyor (LP-R06 marjı 0,48°). Slip eğrisi bu kenarları ×5–8
  pahalılaştıracak; rota ve marjlar **değişecek** (beklenen ve raporlanacak).
- Varsayılan ufuk formülü slip'le bozulur: `worst_edge` (25°, köşegen) ×10 → LPR-1 Ay
  gecesi 113 hamle × 18 dilim = 2 034 > `MAX_PLAN_4D_SLICES = 1000` → 422; VIPER 40 × 13 =
  520 (bugün 100; küp ×5). Bu yüzden ufuk **en kısa sürüş süresi** sınırıyla boyutlanır
  (aşağıda).
- Bit-parite (bu platform, numpy 2.2.1 / Python 3.11.4, AVX-512): `np.exp`, `np.cos`,
  `np.log` ile `math.*` 1 M rastgele örnekte **0 ulp** farklı → analitik log-doğrusal eğri
  hem skaler hem vektörize yolda **bit-eşit** hesaplanabilir (test sabitler; A2'nin `cos`
  kabulüyle aynı kalıp).

## Bileşenler

### `backend/app/slip_model.py` (yeniden yazım, aynı isimler korunur)

- `SLIP_MODEL_VALIDITY = "MODEL"`, `SLIP_MODEL_ID = "anchored_loglinear_v1"`,
  `MAX_SLIP_RATIO = 0.9` (aynı), `SLIP_CLAIM` (iddia sınırı cümlesi, İngilizce),
  `SLIP_REFERENCES` (üç kaynak; PMC/PSJ/RSS bağlantıları).
- `SlipAnchor` (frozen dataclass, hashable): `slope_deg`, `slip`, `sigma`, `kind ∈
  {"measured", "measured_bound", "design_constraint", "assumption"}`, `source: str`
  (boş olamaz). `as_dict()`.
- `SlipCurve` (derlenmiş): `anchors`, `xs`, `log_ys`, `ks` (parça log-eğimleri),
  `rel_sigmas`; `compile_curve(anchors) → SlipCurve` — doğrulama: ≥ 2 çapa, ilk çapa 0°,
  eğimler kesin artan, `0 ≤ slip < MAX_SLIP_RATIO`, slip azalmıyor, `sigma ≥ 0`, `source`
  dolu. Önbellek: `id(anchors)` + `is` kontrolü (çapalar modül düzeyinde tuple; hot loop'ta
  hash maliyeti yok).
- `curve_for(rover) → SlipCurve | None`: `rover.get("slip_curve")`; `None` → slip yok
  (elle kurulan test sözlükleri ve raporun "önce" varyantı; API `applied: false` der).
- `slip_ratio(slope_deg, rover=None) → float`: `x = |θ|`; parça `i = bisect_right(xs, x) − 1`
  (clamp `[0, n−2]`); `s = exp(log_ys[i] + ks[i]·(x − xs[i]))`; `min(MAX, s)`. `rover=None`
  → varsayılan rover. Eğrisiz rover → 0,0.
- `slip_ratio_array(slope_deg: ndarray, rover) → ndarray`: **aynı işlem sırası**
  (`np.searchsorted(side="right") − 1`, `np.exp(log_ys[i] + ks[i]·(x − xs[i]))`,
  `np.minimum`). Bit-eşitlik testi.
- `slip_stats(slope_deg, rover) → (mu, sigma)`: `σ = μ · rel(θ)`, `rel` çapalar arası
  θ'da doğrusal, uçlarda sabit. **B2 kancası.**
- `effective_distance_m(d, θ, rover)`, `slip_energy_multiplier(θ, rover)` — rover parametresi
  eklenir; semantik aynı.
- `curve_table(rover, slopes=(0,5,10,15,20,25)) → list[dict]`: `slope_deg`, `slip`, `sigma`,
  `time_energy_factor`, `within_slope_limit`.
- `rover_slip_block(rover) → dict`: `/api/rovers` bloğu (`validity`, `model_id`, `claim`,
  `max_slip_ratio`, `anchors`, `table`, `references`).
- `route_slip_summary(legs, rover) → dict`: `legs = [(slope_deg, distance_m, hours, drawn_wh|None)]`
  → `applied`, `validity`, `model_id`, `moves`, `mean_slip` (mesafe ağırlıklı), `max_slip`,
  `max_slip_slope_deg`, `distance_factor` (Σ d/(1−s) / Σ d), `extra_hours` (Σ h·s —
  `t = t0/(1−s)` ⇒ `t − t0 = t·s`), `extra_drawn_wh` (Σ E·s, `None` yoksa), `claim`.
  Boş rota → sıfırlar. `inf`/`NaN` sızmaz.
- `thermal_inertia_slip_scale(thermal_inertia)`: `NotImplementedError` (Diviner gerekli).
- `check_slip_accumulation` aynen (detay etiketi artık "MODEL").

### `backend/app/constants.py`

- `SLIP_ANCHOR_YUTU2_FLAT`, `SLIP_ANCHOR_YUTU2_STEEPEST`, `SLIP_ANCHOR_VIPER_15` modül
  sabitleri (kaynak metinleriyle) + `_transferred(anchor, note) → SlipAnchor` (kind
  `"assumption"`, source `"assumption: " + note + " | " + orijinal`).
- Her rover'a `"slip_curve": (…)` (tuple, hashable, JSON'a `as_dict` ile).
- `REGOLITH_REFERENCE`: `"regolith"` alanı `DECLARED_ONLY_FIELDS`'a eklenir (hiçbir şey
  okumaz; `declared_only.regolith` altında yayımlanır): Yutu-2 için ölçülmüş aralıklar +
  `validity: "MEASURED (Chang'e-4 site, not polar)"`, VIPER için GRC-1 test yatağı +
  `validity: "GROUND_TEST"`, diğerleri `None`. Bekker denklemleri koda girmez (YAGNI).
- `MODELLED_FIELDS` += `"slip_curve"`; `_REQUIRED_FIELDS` **değişmez** (raporun "önce"
  varyantı `slip_curve=None` yamasıyla koşar).
- `rover_catalog()` girdilerine `"slip_model": rover_slip_block(rover)`.

### `backend/app/cost_engine.py`

- `edge_travel_time_s`: `L = d/cos; L_eff = L/(1 − slip_ratio(θ, rover)); return L_eff/v`.
- Yeni `edge_travel_time_s_array(theta_deg, d_m, rover) → ndarray` (saniye; `cos ≤ 0` → `inf`),
  **aynı işlem sırası**. `_gated_edges` ve `edge_tables` bunu kullanır.
- `COST_MODEL_ID = "weighted_cell_cost_shadow_aware_energy_slip_v4"` (disk gridi yeniden
  hesaplanır; `cost_grid.npy` gitignore'da).
- Docstring'ler: slip artık uygulanıyor; `edge_energy_wh` "mesafe/(1−slip) düzeltmesi
  `edge_travel_time_s` üzerinden".

### `backend/app/safe_haven.py`

- `_gated_edges`: `travel_h = edge_travel_time_s_array(edge_slope, distance_m, rover) / 3600.0`.
  A2'nin "işlem sırası farklı" notu kalkar: saatler artık planlayıcıyla bit-eşit.
- Yeni `gated_shortest_drive(traversable, elevation, slope, resolution_m, rover, start, goal)
  → (hours, moves) | None`: `_gated_edges` grafında SciPy Dijkstra (`return_predecessors`),
  en kısa **süreli** rotanın saati ve hamle sayısı; ulaşılamıyorsa `None`.

### `backend/app/illumination_corridor.py`

- `edge_tables`: dilim sayısı `_gated_edges`'in saatlerinden (`ratio = hours / slice_hours`,
  `ceil`) — yeniden hesaplama ve "sıra" açıklaması kalkar; A2 testi geçmeye devam eder.

### `backend/app/main.py`

- Varsayılan ufuk: `hours, moves = gated_shortest_drive(...)`;
  `default_n_slices = ceil(hours/slice) + moves + DEFAULT_HORIZON_WAIT_PAD_SLICES`.
  Kanıt: `Σ ceil(h_e/slice) ≤ ceil(Σ h_e/slice) + n_moves` (her hamlede en fazla bir
  dilimlik yuvarlama) ⇒ en kısa süreli rota ufka sığar. `gated_move_count` bağlantı
  kontrolü ve 404/422 metinleri için kalır. Hata metni `MAX_PLAN_4D_SLICES` aşımında
  yeni sayıları söyler.
- `/api/plan`: `slip_model` bloğu (simülasyon durumlarından: `drive_slope = max(cell, segment)`,
  adım mesafesi, adım saati, `step_energy_wh`).
- `/api/plan-4d`: `slip_model` bloğu (`path_states` + kaba eğim trapezi + `edge_travel_time_s`
  + `gross_energy_per_metre_wh` × mesafe, gölge küpünden ortalama maruziyet).
- `_attach_constraint_check` (compare / plan-multi): sonuç sözlüğüne `slip_model`.
- `/api/rovers`: `rover_catalog()` üzerinden otomatik.

### Yanıt blokları

`/api/rovers` → her rover:
```json
"slip_model": {
  "validity": "MODEL", "model_id": "anchored_loglinear_v1", "max_slip_ratio": 0.9,
  "claim": "Literature-anchored MODEL, not a measurement: ...",
  "anchors": [
    {"slope_deg": 0.0, "slip": 0.0375, "sigma": 0.01875, "kind": "assumption",
     "source": "assumption: transferred from Yutu-2 ... | Yutu-2 (Chang'e-4) measured ..."},
    {"slope_deg": 15.0, "slip": 0.40, "sigma": 0.20, "kind": "design_constraint",
     "source": "VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' (PSJ 2025, sect. 3.5; GRC-1, 15-20 % relative density) ..."}
  ],
  "table": [{"slope_deg": 0, "slip": 0.0375, "sigma": 0.0188, "time_energy_factor": 1.039, "within_slope_limit": true}, ...],
  "references": [...]
}
```
`/api/plan`, `/api/plan-4d`, `/api/compare.results[*]`, `/api/plan-multi.results[*]`:
```json
"slip_model": {
  "applied": true, "validity": "MODEL", "model_id": "anchored_loglinear_v1",
  "route": {"moves": 40, "mean_slip": 0.21, "max_slip": 0.62, "max_slip_slope_deg": 17.8,
            "distance_factor": 1.31, "extra_hours": 1.9, "extra_drawn_wh": 640.0},
  "claim": "..."
}
```

## Veri akışı

```
constants.ROVERS[rid]["slip_curve"] (tuple[SlipAnchor])
   └─ slip_model.curve_for(rover) ── compile_curve (id-önbellekli)
        ├─ slip_ratio(θ, rover)            skaler  ─┐
        └─ slip_ratio_array(θ[], rover)    vektör  ─┤ bit-eşit
cost_engine.edge_travel_time_s(θ, d, rover)  = (d/cos) / (1−s) / (v_max cos)   ◄─┘
   ├─ edge_energy_wh, gross/net_energy_per_metre_wh, move_battery_drain_wh (enerji = güç × süre)
   ├─ f_energy_cell → compute_cost_grid (COST_MODEL_ID v4) → 2-B A*, cost_cube
   ├─ pathfinder_4d.astar_4d (hamle süresi + satır içi drain)
   ├─ simulation.simulate_path (2-B), corridor.build_corridor, stress_test.route_legs
   ├─ cost_cube.auto_slice_hours (dilim uzunluğu)
   └─ main.plan_4d worst-edge yerine gated_shortest_drive
cost_engine.edge_travel_time_s_array
   ├─ safe_haven._gated_edges → time_to_safe_haven_hours, gated_shortest_drive
   └─ illumination_corridor.edge_tables (saatler _gated_edges'ten)
slip_model.route_slip_summary ← main.plan / plan_4d / _attach_constraint_check
slip_model.rover_slip_block   ← constants.rover_catalog ← GET /api/rovers
```

## Test stratejisi

- **Birim (`test_slip_model.py`, yeniden yazılır):** eğri her çapadan geçer (rel 1e-9);
  monoton; `|θ|` simetrisi; kap; ilk çapa 0° zorunlu, artan eğim, boş `source`, `slip ≥ MAX`
  → `ValueError`; eğrisiz rover → 0 ve `applied: false`; `slip_stats` çapada `(μ, σ)`
  birebir ve arada doğrusal rel; `effective_distance_m` / `slip_energy_multiplier`
  tutarlılığı (mevcut testler rover parametresiyle); etiket `"MODEL"`, `"MEASURED"` değil,
  claim "not a measurement" içerir; her katalog çapasının `source`'u dolu ve aktarılanlar
  "assumption:" ile başlar; `curve_table` 6 satır; `route_slip_summary` elle 2 kenar;
  `thermal_inertia_slip_scale` `NotImplementedError` ve mesajda "Diviner"; tetikleyici
  testleri aynen.
- **Bit-parite:** her rover için 200 000 rastgele eğim `[0, 90)` (+ çapa noktaları ve
  `slope_max`): `slip_ratio_array == [slip_ratio]` `np.array_equal`; `edge_travel_time_s_array`
  ↔ skaler bit-eşit; `np.exp/np.cos == math.exp/math.cos` platform kabulü ayrı test.
- **Tutarlılık:** `test_pathfinder_4d::test_battery_profile_matches_the_public_drain_functions`
  (satır içi ↔ fonksiyon) değişmeden geçer; `test_illumination_corridor` "slices follow
  the planner's ceil" değişmeden geçer; `test_safe_haven` saat testleri (`edge_travel_time_s`
  ile) geçer; yeni: `_gated_edges` saatleri ↔ `edge_travel_time_s` bit-eşit rastgele gridde;
  `gated_shortest_drive` elle 1×5 koridorda toplanan kenar süresi ve hamle sayısı, duvarla
  `None`, `gated_move_count` ile ulaşılabilirlik uyumu rastgele gridde; slip'in
  `auto_slice_hours`'ı uzattığı (eğrisiz rover ile karşılaştırma).
- **Katalog (`test_rover_validation.py`):** dört rover ≥ 2 çapa, ilk 0°, VIPER'da
  `15°/0,40/design_constraint` ve source "PSJ" içerir, Yutu-2'de iki `measured*` çapa,
  aktarılanlar `assumption`; `regolith` `DECLARED_ONLY_FIELDS`'ta, Yutu-2 aralıkları
  belgedeki sayılar; `MODELLED_FIELDS` ∋ `slip_curve`.
- **API (çekirdeksiz, 16×16):** `/api/rovers` her girdide `slip_model` (validity MODEL,
  anchors source'lu, table 6 satır, `json.dumps(allow_nan=False)`); `/api/plan` ve
  `/api/plan-4d` yanıtında `slip_model.applied True`, `route.moves == move_steps`,
  `extra_hours ≥ 0`, `mean_slip` eğrinin 3° değeriyle uyumlu (düz fixture);
  `/api/compare` sonuçlarında blok; mevcut alanlar aynen; varsayılan ufuk testleri
  (`n_slices` pozitif, `horizon_hours` ile tutarlı) geçer.
- **Gerçek grid (skip-korumalı, yeni `test_slip_calibration_real_grid.py`):** VIPER ve
  LPR-1 standart rotaları slip'li: 200, `slip_model.applied`, `arrival_hours` slip'siz
  koşumdan (aynı süreçte `slip_curve=None` yamasıyla) **büyük**; `extra_hours > 0`;
  varsayılan ufuk `MAX_PLAN_4D_SLICES` altında; süre sınırı.
- Mevcut gerçek-grid testleri (`test_stress_test_real_grid`, `test_safety_monitor_real_grid`,
  `test_plan_4d_real_grid`) rota değişse de özellik iddiaları üzerinden geçmeli; geçmeyen
  varsa nedeni ölçüm bölümüne yazılır ve iddia (rota değil) korunacak biçimde düzeltilir.

## Hata davranışı

- Bozuk çapa kümesi (`slope_deg` artmıyor, ilk 0° değil, `slip ≥ 0,9`, `source` boş) →
  `compile_curve` `ValueError`; katalog testi bunu içe aktarma anında yakalar.
- `slip_curve` yok/`None` → slip 0, `applied: false`; sessiz varsayılan eğri **yok**.
- `θ` `NaN` → `slip_ratio` `NaN` (bugünkü `edge_travel_time_s` davranışıyla aynı: NaN
  yayılır, JSON'a girmeden maskelenir).
- Varsayılan ufuk tavanı aşılırsa 422 metni en kısa sürüş saatini, hamle sayısını ve
  dilimi söyler.
- `route_slip_summary` `inf` süreli kenarı atlar ve `skipped_edges` sayar.
- `thermal_inertia_slip_scale` → `NotImplementedError` (Diviner PRP adıyla).

## Kapsam dışı (bilinçli)

- B2: CVaR maliyeti; burada yalnızca `(μ, σ)` kancası.
- Diviner/termal atalet modülasyonu (kanca + not).
- Bekker/Wong denklemleri, batma → direnç modeli; regolit parametreleri referans.
- İstek düzeyinde `slip` kapatma bayrağı (YAGNI; önce/sonra rapor betiği ve test katalog
  yamasıyla koşar).
- İniş/çıkış asimetrisi (skid vs slip): model `|θ|` simetrik; VIPER Fig. 9'un iniş eğrisi
  sayısal olarak yayımlanmamış.
- Önceki raporların (B5, B3, D3, A2, A1) yeniden üretimi: sayıları slip'siz kalır; C3
  raporu önce/sonra tablosu verir.
- Bilinen iyimserlikler (dokunulmadı, not): hamle süresi dilime yuvarlanırken enerji
  yalnızca sürüş süresi için (B5); `horizon_map` `np.rint`; termal model rover zarfıyla
  tutarsız (D3 → C6); A2 budaması 10 h ufukta %0,2.

## Uygulama sırasında bulunanlar ve ölçümler (4–5 Eylül 2026)

**Kaynak doğrulaması (WebFetch, 4 Eylül 2026).** Nat. Comms 2024 (PMC11258293):
*"most the wheel slip ratios are between 0 and −0.075 and no less than −0.1"*
(Methods); arazi eğimi giden yolculukta en fazla 8,86°, sonda 5,38° (Results);
işaret kuralı `s < 0` skid (Eq. 8 sonrası); regolit aralıkları Fig. 4. PSJ 2025
§3.5: *"The mobility design requirements of the VIPER mission defined a maximum
of 40% slip up a maximum slope of 15°"*; §3.2 GRC-1 %15–20 bağıl yoğunluk, MGRU,
slip tekerlek dönüş hızı ortalaması ↔ Optitrack (araştırma belgesindeki
"enkoder+VO" ifadesi düzeltildi). Science Robotics 2022 sayfası 403 verdi;
yalnızca bağlam kaynağı olarak kaldı.

**Bit-parite.** `np.exp`, `np.cos(np.radians)`, `np.log` ↔ `math.*` 1 M rastgele
örnekte 0 ulp (numpy 2.2.1, Python 3.11.4, AVX-512 mevcut). Bu yüzden eğri
analitik log-doğrusal; tablo yaklaşımı gerekmedi. Test her rover için 100 000
rastgele kenarda `edge_travel_time_s_array == [edge_travel_time_s]`
(`np.array_equal`) ve `slip_ratio_array == [slip_ratio]` (200 000 eğim).
`_gated_edges` saatleri ↔ planlayıcının skaleri rastgele gridde bit-eşit.

**Enerji kriteri ölçeği (sapma).** İlk uygulama `f_energy_cell`'in aralığını
slip'li en kötü hücreye (LPR-1 25°, slip 0,9, ×10) normalize ediyordu: LPR-1'in
karanlık 10° hücresi **0,58 → 0,07**, `test_h4_energy_penalty_depends_on_shadow`
(`dark > lit + 0,1`) düştü — H-4'ün "enerji ≡ eğim sıralaması" çöküşü geri
geliyordu. Karar: hücrenin enerjisi slip'li, **ölçek slip'siz** best/worst
(`cost_engine.slip_free_view`), slip'li enerjisi slip'siz en kötüyü aşan hücre
1,0'da doyar (süresi ve bataryası planlayıcı/simülatörde tam ödenir).
`f_energy_cell_grid` aynı kuralla; `_energy_per_metre_wh_grid` süreyi
`edge_travel_time_s_array`'den alır.

**Varsayılan ufuk (ölçüldü).** Eski sınır "BFS hamle × en yavaş kenar (25°,
köşegen)" slip'le: LPR-1 günü 40 × 14 + 20 = **580**, Ay gecesi 113 × 14 + 20 =
**1 602 > 1 000** (422). Yeni sınır `ceil(en hızlı rota saati / dilim) + hamle + 20`:
120 ve 270; slip'siz 108 / 273 (eskisi 100 / 246; biraz daha cömert).
`gated_shortest_drive` her hamlede en fazla bir dilimlik yuvarlama kaybı
kanıtıyla yeterli.

**Ölçümler (Site11, 5 Eylül 2026; `scripts/slip_calibration_report.py` →
[slip_calibration_report.md](../../research/slip_calibration_report.md);
"önce" = `ROVERS[*]["slip_curve"] = None` yaması + grid yeniden yükleme):**

| Rota | Ölçüm | Slip'siz (önce) | Slip'li (C3) |
|---|---|---|---|
| Eğri (2 çapa, LPR-1/LUVMI-M/VIPER) 0/5/10/15/20/25° | slip | — | 0,037 / 0,083 / 0,182 / 0,400 / 0,881 / 0,900 (×1,04 / 1,09 / 1,22 / 1,67 / 8,4 / 10) |
| Eğri Yutu-2 (3 çapa) | slip | — | 0,037 / 0,055 / 0,075 (8,86°) / 0,102 (10°) / 0,400 / 0,900 |
| LPR-1 28 Eyl 2026, (358,494)→(206,426) | dilim × saat; hamle; varış; min SOC; LP-R02 | 108 × 0,0287; 40; 2,16 h; %96,2; 76,2 | 120 × 0,0359; 41; **2,98 h (×1,38)**; %92,5; 72,5 |
| aynı | `slip_model.route` | — | ort. 0,326, maks 0,537 @ 16,9°, +0,75 h / +321 Wh, mesafe ×1,53 |
| aynı, B5 (1 000 koşum) | tamamlanma / rezerv içinde / nominal min SOC | %100 / %100 / %97,9 | %100 / %99,8 / %94,5 |
| aynı, 2-B | süre / tüketim / min SOC | 1,30 h / 469 Wh / %95,6 | 1,62 h / 597 Wh (×1,27) / %94,3 |
| LPR-1 Ay gecesi 13 Eyl 2026, (186,34)→(494,450) | dilim; hamle; varış; min SOC; LP-R02 | 273 × 0,0287; 114; 5,35 h; %72,7; 52,7 | 270 × 0,0359; 116; **6,75 h (×1,26)**; %67,4; 47,5 |
| aynı, 2-B | süre / tüketim / min SOC | 3,85 h / 1 288 Wh / %88,7 | 4,37 h / 1 466 Wh (×1,14) / %87,1 |
| VIPER haven→haven 30 May 2027, (358,494)→(206,426), leg kuralı | 4-B | 108 × 0,0956; 40 hamle; 7,36 h; %32,1; B5 %29,6 / rezerv içinde %1,4 | **404** (51 s): 283 148 kenar bataryayı %20 rezervin altına düşürürdü; haven kuralsız da 404 (481 271 kenar), 24 h ufukla da 404 (394 597); eski ufuk sınırı 460 dilim, yeni 123 |
| aynı, 2-B | süre / tüketim / min SOC | 4,33 h / 2 156 Wh / %67,2 | 5,40 h / 2 742 Wh (×1,27) / %57,6; ort. slip 0,174, maks 0,586 @ 17,4°, +1,08 h / +587 Wh |
| VIPER kısa leg (358,494)→(346,462) (en yakın uygulanabilir haven→haven, 8 hamle, havende biter) | 4-B; B5 | 38 × 0,0956; 1,53 h; min SOC %85,4; LP-R02 65,4; B5 %100 / rezerv içinde %99,7 / nominal %83,8 | 43 × 0,1176; **2,23 h (×1,46)**; %72,3; 52,3; ort. slip 0,465 (maks 0,532 @ 16,8°), +0,83 h / +526 Wh; B5 %99,6 / %95,0 / nominal %71,0 |
| aynı, 2-B | süre / tüketim / min SOC | 0,92 h / 540 Wh / %91,0 | 1,55 h / 920 Wh (×1,70) / %84,6 |
| Planlama süresi | LPR-1 / Ay gecesi (s) | 3,9 / 7,4 | 9,8 / 20,6 (küp 1,1× / 1,0×; genişletilen düğüm 8 799 → 23 177 / 53 365 → 146 705: slip'li maliyet yüzeyi daha az yönlendirici); VIPER standart leg'in reddi 51 s (283 148 batarya reddi aranıyor) |
| Testler | | | 42 birim + 15 cost-engine + 9 katalog + 5 kapılı graf/Dijkstra + 2 koridor/dilim + 5 API + 4 gerçek grid; uyarlanan: `test_review3_fixes` (v4), `test_simulation` (düz zeminde `edge_travel_time_s`), `test_cost_engine.py` betiği, 6 VIPER gerçek-grid testi (kısa leg); tam paket 1 176 passed, 2 skipped (12:25) |

**Bulgular:**
- Site11 dik (ince eğim medyanı ~10°, kaba blok eğimleri p95 19–22°); eğrinin
  10–17°'deki değerleri (0,18–0,6) rotaların tipik kenarlarına düşüyor, bu
  yüzden süre ×1,26–1,38, sürüş enerjisi ×1,14–1,27.
- **VIPER'ın standart leg'i slip'li modelde uygulanamaz:** slip'siz plan %32
  SOC'de bitiyordu ve B5 koşumların yalnızca %1,4'ünü rezerv içinde buluyordu;
  slip bunu nominal hâle getirir. Modelin dürüst kararı; hata değil. Rapor en
  yakın uygulanabilir leg'i (8 hamle) ölçer; testler ona uyarlandı.
- Planlayıcı slip'li maliyet yüzeyinde 2,6–2,8× daha çok düğüm genişletiyor
  (sezgisel `d / v_max` slip'siz alt sınır olarak geçerli ama gevşedi); A3'ün
  hızlandırma adayı.
- Yutu-2'nin ölçümü 0–8,86°'yi ≤ 0,075 ile sınırlar; iki çapalı eğri 8,86°'de
  0,152 verir — bu yüzden Yutu-2 üç çapalı, diğerlerine aktarılmadı.

**Sapmalar (tasarımdan):** enerji kriterinin ölçeği slip'siz (yukarıda);
`test_cost_engine_slip.py` ayrı dosya; `slip_free_view` (`cost_engine`) yardımcı;
VIPER için raporda "kısa leg" senaryosu ve gevşetme satırları; altı mevcut
gerçek-grid testi VIPER'ın kısa leg'ine taşındı (iddialar korundu; yeni test
standart leg'in reddini kilitler); `route_slip_summary` testleri uygulamadan
sonra yazıldı; 90°'de süre sonsuz değil (mevcut davranış; test 95°'de);
`_transferred` yardımcı ve `SLIP_REFERENCES` sabiti; rapor betiği 4-B 404
olsa da 2-B ve ufuk sınırlarını raporlar.
