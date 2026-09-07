# B2 — CVaR tabanlı risk-farkında maliyet (slip ve eğim dağılımlarından; termal kanca) — Tasarım Belgesi

**Tarih:** 5 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → B2](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** C3'ün `(μ, σ)` kancası (`slip_model.slip_stats`, eğri parçalarının log-eğimleri `SlipCurve.ks`), B3'ün hücre başına eğim belirsizliği (`uncertainty.uncertainty_layers_for_grids → slope_sigma`, NASA'nın 100 Site11 klonundan DERIVED), maliyet yolu (`cost_engine.compute_cost_grid` skaler referans ↔ `cost_vec` vektörize; `costmap.default_cost_map`; `cost_cube.build_cost_cube`; `rover_grids.grids_for_rover` önbelleği), 2-B ve 4-B planlayıcılar (yalnızca maliyet gridini/küpünü okurlar; değişmezler), B5 stres testi (ölçüm için).
**Kapsam:** `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

Bugün bir hücrenin maliyeti tek bir sayıdır: slip `μ(θ)` (C3) ve DEM'in en iyi tahmin eğimi `θ`
ile hesaplanan dört kriterin ağırlıklı toplamı. Oysa iki girdinin de bir **dağılımı** var:
C3 her çapaya bir `σ` koydu (`slip_stats(θ, rover) → (μ, σ)`), B3 her hücreye NASA'nın 100
klonundan bir eğim belirsizliği `σ_θ` üretti. B2 bu dağılımların **en kötü (1−α)'lık
kuyruğunun ortalamasını** (Conditional Value-at-Risk) sıralama maliyetine bağlar; `α`
operatörün risk iştahıdır ve isteğe bağlı bir alan olarak `/api/plan` ve `/api/plan-4d`'ye
girer. Yeni bir uç, `/api/risk-sweep`, aynı çift için birkaç `α`'yı yan yana planlayıp
karşılaştırır ("risk iştahı sürgüsü").

Tek cümlelik iddia (sunum): **"Risk iştahı α'yı JPL'in STEP ve Keio'nun CVaR yaklaşımıyla
maliyete bağladık: α arttıkça planlayıcı slip ve eğim kuyruğu geniş hücrelerden kaçar;
etkisi Site11'de B5 stres testiyle ölçüldü."** (Sayılar raporda; aşağıdaki sondalar
ve "Uygulama sırasında bulunanlar" bölümü.)

**İddia sınırı (her yanıtta ve belgede):** CVaR, **MODEL etiketli** dağılımların bir
dönüşümüdür, ölçülmüş risk değildir. Slip `σ`'sı Yutu-2'nin ölçülmüş aralığının 1/4'ü ve
VIPER için aktarılmış bağıl yayılım 0,5'tir (her ikisi de `SlipAnchor.source`'ta yazılı
**varsayım**); eğim `σ_θ` NASA klonlarından türetilmiştir (DERIVED, B3); termal `σ`'nın
kaynağı **yoktur** ve termal CVaR bu yüzden uygulanmaz (aşağıda). Yanıtlardaki risk sayıları
`validity: "MODEL"` taşır; "ölçülmüş risk" **denmez**. Endo vd.'nin "%11 → %95 başarı, maks
slip %92,9 → %63,7" sayıları **onların sentetik deneylerinden** alıntıdır; bizim etkimiz
Site11'de ölçülür ve olduğu gibi yazılır (küçükse küçük).

## Kaynak ve yöntem notu

### CVaR ve iki referans

- **STEP** (Fan, Otsu, Kitahara, Zhang, Agha-mohammadi, RSS 2021, arXiv 2103.02828;
  genişletilmiş 2303.01614): geçilebilirlik risklerini (çarpışma, basamak, eğim, slip)
  dağılım olarak modelleyip her birinin CVaR_α'sını birleştirerek MPC maliyetine koyar;
  DARPA SubT'de sahada kullanıldı. Bizim karşılığımız: hücre kriterlerinin dağılım
  girdileri (slip, eğim) CVaR_α ile deterministik maliyete çevrilir; A* aynen kalır.
- **Endo vd.** (Keio, ICRA 2023, arXiv 2303.01169): slip `s ~ p(s | eğim, arazi sınıfı)`;
  sınıf belirsizliği ile GP belirsizliği karıştırılır; `CVaR_α(slip)` → seyahat süresi/enerji
  maliyeti. Bizim karşılığımız: C3 çapalarının `σ`'sı (Endo'nun GP yayılımı) ⊕ B3 eğim
  `σ_θ`'sının delta yöntemiyle slip'e taşınması (Endo'nun sınıf belirsizliği; bizde sınıf
  yok, DEM hatası var).

### Tanım ve kapalı form

`X ~ N(μ, σ²)` için `CVaR_α(X) = E[X | X ≥ VaR_α] = μ + σ·φ(z_α)/(1−α)`, `z_α = Φ⁻¹(α)`,
`φ` standart normal yoğunluğu. Çarpan `m_α = φ(z_α)/(1−α)`:

| α | z_α | m_α |
|---|---|---|
| 0,5 | 0 | **0,798** (ortalama DEĞİL) |
| 0,9 | 1,282 | 1,755 |
| 0,99 | 2,326 | 2,665 |
| 0,999 | 3,090 | 3,367 |

**Dikkat:** `CVaR_0,5 = μ + 0,798σ`; "α = 0,5 nominal" demek yanlıştır. Nominal davranış
`risk_alpha = None`'dır (bugünkü grid, bit-eşit). `α → 1`'de `m_α` sonlu ama büyür;
`risk_alpha ∈ [0,5, 0,999]` sınırı ve slip kapı `MAX_SLIP_RATIO = 0,9` / eğim kapı
`slope_max_deg` her şeyi sonlu tutar. Kapalı form Monte Carlo ile doğrulanır (test).

### Nereye girer: yalnızca sıralama maliyeti

`α` **iki kriterin girdisini** değiştirir, fiziği değil:

1. **Enerji kriteri** (`f_energy_cell`, w = 0,259): hücrenin enerjisi `μ` yerine
   `s_α = min(0,9, CVaR_α(slip))` ile hesaplanır. Ölçek (slip'siz best/worst, C3 kararı)
   aynen.
2. **Eğim kriteri** (`f_slope`, w = 0,409): sigmoid `θ` yerine
   `θ_α = min(slope_max, θ + σ_θ·m_α)` okur; `θ > slope_max → inf` kapısı **nominal**
   `θ`'da kalır (geçilebilirlik değişmez, 4-B'nin "kaba hücre geçilebilirse maliyeti sonlu"
   kabulü korunur). `σ_θ` yoksa (klon önbelleği yok) `θ_α = θ` ve yanıt bunu söyler.

Süre, batarya, D3 marjları, B5 nominali, koridor bütçeleri, safe-haven süreleri **μ'da
kalır**. Gerekçe: α'yı fiziğe de sokmak nominali α'ya bağımlı kılar (aynı rota iki α'da iki
farklı "varış saati" verir) ve B5'in kendi hız/güç dağılımlarıyla çifte sayım yapar.
Alternatif (fiziğe de α) **reddedildi**. Yanıt ayrıca "risk-ayarlı süre/enerji" raporlar:
`t_α = t·(1−μ)/(1−s_α)` (çünkü `t = t0/(1−s)`), `E_α = E·(1−μ)/(1−s_α)` — kararın kuyrukta
ne kadar zaman/enerji satın aldığını gösterir, planlayıcının saatini değiştirmez.

### σ kaynakları

- **Slip (C3):** `σ_slip = μ·rel(θ)` (`slip_stats`); katalogda her çapada `σ/μ = 0,5` olduğundan
  bugün her yerde 0,5 (Yutu-2 aralık/4; VIPER'a aktarım — varsayım).
- **Eğim → slip (B3, delta yöntemi):** parçalı log-doğrusal eğride `ds/dθ = k_i·s` (`k_i`
  parçanın log-eğimi; kapıda ve eğrisiz profilde 0) ⇒ `σ_total² = σ_slip² + (k·s·σ_θ)²`.
  Birinci derece; `μ` düzeltilmez (dışbükeylik kaynaklı `E[s(θ+ε)] > s(θ)` ihmal — not).
  `σ_θ` sonlu değilse 0 sayılır (genişletme yok, dürüst geri dönüş).
- **Eğim (B3):** `σ_θ` doğrudan `slope_sigma` katmanı (100 klon, üretimle aynı eğim
  operatörü). NASA'nın kendi `slope_sigma_nasa` ürünü kullanılmaz (farklı operatör; B3
  raporu oran 0,88).
- **Termal:** `thermal`…`thermal_min` aralığı bir σ değil; "aralık = ±2σ" vekili
  kaynaksız bir varsayım olurdu. **Ölçüldü (sonda 2):** `f_thermal` Site11'de LPR-1 için
  geçilebilir hücrelerin %72,7'sinde, VIPER için %54,2'sinde zaten ≥ 0,99 (medyan 0,9994 /
  0,9957); aralık/4 vekiliyle α = 0,9 soğuk kuyruğu bu oranı %94,0 / %81,2'ye çıkarır
  (ortalama değişim +0,025 / +0,070) — **doygunluk ekler, ayrım eklemez** (D3'ün termal
  zarf bulgusunun aynısı; C6'ya). Karar: `risk.thermal_cvar_cold_c` yalnızca **imza**;
  `NotImplementedError` ile hangi ürünün gerektiğini ve ölçülen doygunluğu söyler. C3'ün
  termal atalet kararıyla aynı kalıp.

## Mevcut durumdan kullanılanlar

- `slip_model.slip_stats(θ, rover)`, `curve_for`, `SlipCurve.ks/rel_sigmas/xs` ve `_array`
  eşleri; `slip_ratio_array` ile bit-parite kalıbı (`np.searchsorted(side="right") − 1`).
- `cost_engine.edge_travel_time_s(θ, d, rover)` — slip'in tek bağlama noktası;
  `net_energy_per_metre_wh` → `f_energy_cell`; `f_slope`; `compute_cost_grid` (skaler
  referans, `cost_vec` içe aktarır); `COST_MODEL_ID` v4; `slip_free_view`.
- `cost_vec.f_slope_grid`, `f_energy_cell_grid`, `_energy_per_metre_wh_grid`,
  `edge_travel_time_s_array`.
- `costmap.PlanContext` / `SlopeLayer` / `EnergyLayer` / `default_cost_map` / `explain`.
- `cost_cube.build_cost_cube(base_grids, series, rover, weights, coarsen, couple_thermal,
  slice_hours, tau_s)`; eğim `how="max"` ile kabalaştırılır.
- `rover_grids.grids_for_rover(base, rover_id, weights)`: `rover_id / weights / maske /
  cost_model` değişince yeniden hesap; `metadata["cost_weights"]`, `["cost_model"]`.
- `uncertainty.uncertainty_layers_for_grids(grids, rover_id) → (layers | None, info)`;
  `layers["slope_sigma"]` float32 (500×500), `info["model"]` ("pgda_clones" vb.),
  `info["n_clones"]`; küçük önbellek (1,5–1,7 s ilk çağrı, sonra anında).
- `main.PlanRequest`, `Plan4DRequest`, `_slip_block_2d/_4d` (leg kurma kalıbı),
  `_attach_constraint_check`, `_coarse_geometry`; yanıt blokları kalıbı (`slip_model`,
  `safety_margins`, `uncertainty`, `illumination_corridor`).
- B5 `/api/stress-test`, rapor betiği kalıbı (`scripts/slip_calibration_report.py`:
  `--json` önce, `--from-json` yeniden render).

## Sondalar (tasarım öncesi, Site11, 5 Eylül 2026; atılabilir yamalarla)

**Sonda 1 — ince grid (500×500; geçilebilir hücre LPR-1 210 063, VIPER 198 575).**
B3 `σ_θ` (100 klon): medyan **1,54°**, p95 1,99°. LPR-1: slip μ medyanı 0,199; C3 σ
medyanı 0,100; B3 delta payı medyanı 0,043 (toplam σ'nın %43'ü); μ kapıda %5,2. CVaR slip
(C3 ⊕ B3) medyanı ve kapıya dayanan hücre oranı:

| α | m_α | LPR-1 medyan / kap | VIPER medyan / kap | Maliyet gridi Spearman (yalnız enerji / enerji + eğim), LPR-1 | Ort. bağıl değişim (enerji / +eğim) | Eğim kapısına dayanan (LPR-1 / VIPER) |
|---|---|---|---|---|---|---|
| 0,5 | 0,798 | 0,288 / %10,8 | 0,271 / %5,6 | 0,9998 / 0,9983 | +%3,2 / +%8,4 | %0,9 / %2,8 |
| 0,9 | 1,755 | 0,395 / %18,8 | 0,371 / %14,1 | 0,9994 / 0,9929 | +%6,7 / +%19,1 | %2,3 / %7,8 |
| 0,99 | 2,665 | 0,497 / %26,6 | 0,466 / %22,4 | 0,9986 / 0,9848 | +%9,6 / +%29,9 | %4,1 / %14,5 |

Enerji kriterinin 1,0'da doyduğu hücre oranı: nominal %14,6 (LPR-1) / %17,0 (VIPER) →
α = 0,99'da **%40,3 / %44,7** (C3'ün slip'siz ölçek kararının kaçınılmaz sonucu; kuyruk
dik hücreleri zaten dolu olan uca iter). Yalnız enerji kriterine giren α sıralamayı
neredeyse değiştirmiyor (Spearman ≥ 0,9986); eğim kriterine de girince Spearman 0,985'e
(VIPER 0,970) düşüyor — sürgünün tutuşu buradan geliyor.

**Sonda 2 — termal doygunluk:** yukarıda ("σ kaynakları → Termal").

**Sonda 3 — rotalar, 4-B (coarsen 4) + B5 (1 000 koşum):** LPR-1 28 Eyl 2026
(358,494)→(206,426): nominal 41 hamle, 2,98 h, min SOC %92,5, rota ort. slip 0,326 (maks
0,537), B5 tamamlanma %100 / rezerv içinde %99,8 / nominal min SOC %94,5. α ∈ {0,5, 0,9,
0,99} (yalnız enerji ve enerji + eğim varyantları **aynı** rotayı verdi): 42 hamle, 2,98 h
(dilim yuvarlaması), min SOC **%93,1**, ort. slip **0,313**, maks 0,537, nominal rotayla
örtüşme %54,5, B5 %100 / %99,8 / %95,0. VIPER kısa leg: her α'da rota **aynı** (8 hamle).
Kaba 125×125 gridde alternatif az; α tek bir "geçiş" yaptırıyor.

**Sonda 3c — 2-B ince grid (`/api/plan`), enerji + eğim:**

| Çift | α | Mesafe (km) | Süre (h) | Tüketim (Wh) | Min SOC | Ort. / maks slip | Nominalle örtüşme |
|---|---|---|---|---|---|---|---|
| LPR-1 28 Eyl | None / 0,5 / 0,9 / 0,99 | 0,910 (hepsi) | 1,624 / 1,621 / 1,622 / 1,617 | 597 / 596 / 596 / 593 | 94,3 / 94,3 / 94,3 / 94,4 | 0,175 / 0,586 → 0,173 / 0,563 | 1 / 0,81 / 0,79 / 0,49 |
| LPR-1 Ay gecesi | None / 0,5 / 0,9 / 0,99 | 2,727 / 2,733 / 2,736 / 2,744 | 4,366 / 4,353 / 4,349 / 4,344 | 1 466 / 1 454 / 1 448 / **1 440** | 87,1 / 87,3 / 87,4 / 87,5 | 0,115 / 0,395 → 0,108 / 0,395 | 1 / 0,79 / 0,57 / 0,52 |
| VIPER standart | None / 0,5 / 0,9 / 0,99 | 0,910 (hepsi) | 5,403 / 5,400 / 5,392 / 5,377 | 2 742 / 2 739 / 2 730 / **2 713** | 57,6 / 57,7 / 57,9 / 58,2 | 0,174 / 0,586 → 0,170 / 0,586 | 1 / 0,87 / 0,66 / 0,48 |
| VIPER kısa leg | None / 0,5 / 0,9 / 0,99 | 0,185 (hepsi) | 1,551 / 1,551 / 1,540 / 1,540 | 920 / 920 / 914 / 914 | 84,6 (hepsi) | 0,392 / 0,594 → 0,393 / **0,627** | 1 / 0,94 / 0,03 / 0,03 |

Okuma: ince gridde α rotayı **gerçekten değiştiriyor** (α = 0,99'da örtüşme ~%50), nominal
fizikte kazanç **küçük** (enerji −%0,7 … −%1,8, ort. slip −%2 … −%7, mesafe +%0 … +%0,6);
VIPER kısa leg'de α rotası nominal maks slip'i **yükseltiyor** (0,594 → 0,627): kuyruk
kriterinin seçtiği rota nominal ölçütte her zaman "daha güvenli" değildir — rapor bunu
olduğu gibi yazar. Bu sondalar tasarımı belirledi: α eğim kriterine de girer (tutuş), fizik
μ'da kalır, termal kanca.

## Bileşenler

### `backend/app/risk.py` (yeni; B2'nin modülü — C3'ün `slip_model.py` kalıbı)

- Sabitler: `RISK_MEASURE_ID = "cvar_normal_closed_form_v1"`, `RISK_VALIDITY = "MODEL"`,
  `RISK_ALPHA_MIN = 0.5`, `RISK_ALPHA_MAX = 0.999`, `RISK_CLAIM` (İngilizce iddia sınırı:
  MODEL dağılımların dönüşümü, ölçülmüş risk değil; slip σ varsayım; eğim σ NASA klonları;
  termal uygulanmadı; yalnızca sıralama maliyeti), `RISK_REFERENCES` (STEP RSS 2021 +
  2303.01614; Endo ICRA 2023; Rockafellar & Uryasev 2000 kapalı form).
- `cvar_multiplier(alpha) → float`: `φ(Φ⁻¹(α))/(1−α)` (`scipy.special.ndtri`, `math.exp`);
  `alpha ∉ [MIN, MAX]` → `ValueError`.
- `cvar_normal(mu, sigma, alpha) → float`: `mu + sigma·m_α`; `sigma < 0` → `ValueError`.
- `slip_sensitivity(θ, rover) → float` ve `slip_sensitivity_array`: `ds/dθ = k_i·s`
  (derece başına); kapıda / eğrisiz 0; parça indeksi `slip_model._segment_index` ile aynı
  (`bisect_right − 1`, uçlarda kenetlenmiş).
- `slip_stats_array(θ, rover) → (mu, sigma)`: `slip_stats`'ın vektörize eşi (aynı işlem
  sırası; bit-parite testi).
- `slip_cvar(θ, alpha, rover=None, slope_sigma=None) → float` ve
  `slip_cvar_array(θ, alpha, rover, slope_sigma=None)`: `σ_total = sqrt(σ_slip² + (k·μ·σ_θ)²)`
  (σ_θ `None`/NaN/inf → 0), `min(MAX_SLIP_RATIO, μ + σ_total·m_α)`; `θ` NaN → NaN.
  Skaler ↔ dizi `np.array_equal` (aynı işlem sırası; `math.sqrt`/`np.sqrt` bit-eşit).
- `slope_cvar(θ, alpha, slope_sigma, rover=None) → float` ve `slope_cvar_array`:
  `σ_θ` `None`/sonlu değil → `θ`; aksi hâlde `min(slope_max_deg, θ + σ_θ·m_α)`; `θ` NaN → NaN.
- `route_risk_summary(legs, rover, alpha) → dict`: `legs = [(slope_deg, distance_m, hours,
  drawn_wh | None, slope_sigma | None)]` → `moves`, `skipped_edges`, `mean_slip_mu`,
  `mean_slip_cvar` (mesafe ağırlıklı), `max_slip_cvar`, `max_slip_cvar_slope_deg`,
  `max_slope_cvar_deg` (eğim kuyruğu maksimumu; σ yoksa nominal maks), `hours`,
  `risk_adjusted_hours` (`Σ h·(1−μ)/(1−s_α)`), `hours_factor`, `drawn_wh`,
  `risk_adjusted_drawn_wh` (herhangi bir leg `None` → `None`), `slope_sigma_known_fraction`.
  `alpha=None` → `applied: False`, `route: None`.
- `risk_block(alpha, sigma_sources, route=None) → dict`: yanıtın `risk` bloğu (aşağıda).
- `sigma_sources(rover, slope_sigma_info) → dict`.
- `thermal_cvar_cold_c(t_peak_c, t_min_c, alpha)`: **imza**; `NotImplementedError`
  (mesaj: termal σ'nın kaynağı yok; ölçülen doygunluk oranları; C5/C6'ya işaret).

### `backend/app/cost_engine.py`

- `edge_travel_time_s(θ, d, rover, slip=None)` ve `edge_travel_time_s_array(…, slip=None)`:
  `s = slip_ratio(θ, rover) if slip is None else float(slip)`; `L_wheel = L/(1−s)` —
  `slip=None` yolu **aynı işlemler**, bit-eşit. Slip hâlâ tek noktadan girer; `slip`
  parametresi yalnızca "bu değeri kullan" der.
- `net_energy_per_metre_wh(θ, shadow, rover, slip=None)` pass-through.
- `f_slope(θ, rover, risk_alpha=None, slope_sigma=None)`: `risk_alpha None` → eski gövde;
  aksi hâlde `inf` kapısı nominal `θ`'da, sigmoid `slope_cvar(...)`'da.
- `f_energy_cell(θ, rover, shadow, risk_alpha=None, slope_sigma=None)`: `slip =
  slip_cvar(θ, α, rover, σ_θ)` yalnızca α verilince; `here_wh = net_energy_per_metre_wh(…,
  slip=slip)`; ölçek aynen.
- `compute_cost_grid(…, risk_alpha=None, slope_sigma_grid=None)`: `f_slope_grid` ve
  `f_energy_cell_grid`'e geçirir; `slope_sigma_grid` şekli uymazsa `ValueError`.
- `COST_MODEL_ID` **v4 kalır** (None yolu değişmiyor); `RISK_MEASURE_ID` `risk.py`'de.

### `backend/app/cost_vec.py`

- `f_slope_grid(slope, rover, risk_alpha=None, slope_sigma=None)`,
  `f_energy_cell_grid(slope, rover, shadow, risk_alpha=None, slope_sigma=None)`,
  `_energy_per_metre_wh_grid(θ, shadow, rover, slip=None)`; α yolu `risk.*_array`.

### `backend/app/costmap.py`

- `PlanContext.slope_sigma: np.ndarray | None = None` (`_cell_context` dilimler).
- `SlopeLayer(weight, validity, risk_alpha=None)`, `EnergyLayer(weight, validity,
  risk_alpha=None)`: `contribution` α ve `ctx.slope_sigma`'yı geçirir; `risk_alpha` niteliği
  raporlanabilir.
- `default_cost_map(rover, weights, layer_validity, risk_alpha=None)`.

### `backend/app/cost_cube.py`

- `build_cost_cube(…, risk_alpha=None, slope_sigma=None)`: `slope_sigma` ince grid,
  `coarsen_grid(how="max")` ile kabalaştırılır (eğim de max — tutucu eşleşme; belgelenir);
  `PlanContext(slope_sigma=…)`; `default_cost_map(rover, weights, risk_alpha=…)`.

### `backend/app/rover_grids.py`

- `grids_for_rover(base, rover_id, weights, risk_alpha=None)`: α verilince
  `uncertainty_layers_for_grids(base, rover_id)` → `slope_sigma` (yoksa `None`, kaynak
  `"none"`); yeniden hesap koşuluna `stored_alpha != alpha` eklenir (`metadata.get
  ("risk_alpha")`, yoksa `None`); α'lı gridde `metadata["risk_alpha"] = α`,
  `metadata["risk"] = {"alpha", "measure", "slope_sigma_source", "n_clones"}` ve çıktıya
  `out["slope_sigma"]` eklenir; `α None` → bu anahtarlar **yazılmaz** (girdi taşıyorsa
  silinir), grid v4 ile bit-eşit (regresyon testi). `COST_MODEL_ID` damgası aynen.

### `backend/app/main.py`

- `PlanRequest.risk_alpha: Optional[float] = Field(None, ge=0.5, le=0.999)`; aynı alan
  `Plan4DRequest`'te. `/api/compare`, `/api/plan-multi` **aynen** (α yok).
- `/api/plan`: `grids_for_rover(…, risk_alpha=req.risk_alpha)`; yanıta `risk` bloğu
  (`_risk_block_2d(states, grids_for_plan, rover, α)`: `_slip_block_2d` ile aynı leg'ler +
  hücrenin `slope_sigma`'sı).
- `/api/plan-4d`: `build_cost_cube(…, risk_alpha=req.risk_alpha,
  slope_sigma=grids_for_plan.get("slope_sigma"))`; yanıta `risk` bloğu (`_risk_block_4d`:
  `_slip_block_4d` leg'leri + kaba σ_θ trapezi).
- Yeni `RiskSweepRequest(start, goal, rover_id, weights, alphas: list[float] = [0.5, 0.9,
  0.99] (1–6 eleman, her biri [0,5, 0,999]), include_nominal: bool = True)` →
  `POST /api/risk-sweep`: 2-B planlayıcı (`astar` + `simulate_path`) her α için (None
  dahil); `results[]` (`risk_alpha`, `waypoints`, `summary`, `astar_metrics`, `slip_model`,
  `risk`, `overlap_with_nominal`, `plan_ms`), `risk_matrix` (her rota × her α:
  `risk_adjusted_hours`, `mean_slip_cvar`, `max_slope_cvar_deg`), `comparison`
  (nominale göre Δ: mesafe, saat, Wh, min SOC, ort./maks slip; en düşük CVaR-saatli rota),
  `planner: "2d"`, `validity`, `claim`. 4-B için `/api/plan-4d.risk_alpha` kullanılır
  (yanıt belgesinde söylenir). 422: geçersiz α, boş liste, grid dışı uç.
- `/api/rovers`: değişmez (risk rover'a değil isteğe bağlı).

### Yanıt blokları

`/api/plan`, `/api/plan-4d` (ve `/api/risk-sweep.results[*]`):
```json
"risk": {
  "alpha": 0.9,
  "applied": true,
  "validity": "MODEL",
  "measure": "cvar_normal_closed_form_v1",
  "multiplier": 1.755,
  "scope": "ranking cost only: the slope criterion reads min(slope_max, slope + sigma*m) and the energy criterion's slip is CVaR_alpha(slip); travel time, battery, safety margins and the Monte Carlo use the mean",
  "criteria": {"slope": "cvar", "energy": "cvar"},
  "sigma_sources": {
    "slip": {"source": "C3 anchors: relative spread per anchor (Yutu-2 range/4; transferred as an assumption elsewhere)", "validity": "MODEL"},
    "slope": {"source": "dem_clones", "model": "pgda_clones", "n_clones": 100, "validity": "DERIVED"}
  },
  "route": {
    "moves": 41, "skipped_edges": 0,
    "mean_slip_mu": 0.326, "mean_slip_cvar": 0.51, "max_slip_cvar": 0.9, "max_slip_cvar_slope_deg": 16.9,
    "max_slope_cvar_deg": 19.6, "slope_sigma_known_fraction": 1.0,
    "hours": 2.23, "risk_adjusted_hours": 3.4, "hours_factor": 1.52,
    "drawn_wh": 970.0, "risk_adjusted_drawn_wh": 1480.0
  },
  "claim": "CVaR of MODEL-labelled distributions, not a measured risk: ..."
}
```
`risk_alpha` verilmemişse: `{"alpha": null, "applied": false, "validity": "MODEL",
"measure": …, "scope": …, "criteria": {"slope": "nominal", "energy": "nominal"},
"sigma_sources": …, "route": null, "claim": …}` — `slope_sigma` kaynağı burada da
raporlanır (klon var/yok). Eğim σ yokken α'lı yanıtta `criteria.slope: "nominal"` ve
`sigma_sources.slope.source: "none"`.

`/api/risk-sweep`:
```json
{
  "start": [358, 494], "goal": [206, 426], "rover_id": "lpr_1", "planner": "2d",
  "alphas": [null, 0.5, 0.9, 0.99],
  "results": [{"risk_alpha": null, "waypoints": [...], "summary": {...}, "astar_metrics": {...},
               "slip_model": {...}, "risk": {...}, "overlap_with_nominal": 1.0, "plan_ms": 420.0}, ...],
  "risk_matrix": {"route_alphas": [null, 0.5, 0.9, 0.99], "eval_alphas": [0.5, 0.9, 0.99],
                  "risk_adjusted_hours": [[...], ...], "mean_slip_cvar": [[...], ...], "max_slope_cvar_deg": [[...], ...]},
  "comparison": {"nominal": {"distance_km", "hours", "energy_wh", "min_battery_pct", "mean_slip", "max_slip"},
                 "deltas": [{"risk_alpha": 0.5, "distance_km": +0.006, "hours": -0.013, "energy_wh": -12.2, "min_battery_pct": +0.17, "mean_slip": -0.003, "max_slip": 0.0, "overlap_with_nominal": 0.79}, ...],
                 "lowest_risk_adjusted_hours_alpha": 0.99},
  "validity": "MODEL", "measure": "...", "claim": "..."
}
```

## Veri akışı

```
istek risk_alpha (None | [0.5, 0.999])
  └─ rover_grids.grids_for_rover(base, rover_id, weights, risk_alpha)
       ├─ α None → compute_cost_grid(…)  (v4, bit-eşit; metadata'da risk anahtarı yok)
       └─ α → uncertainty_layers_for_grids → slope_sigma (| None)
              compute_cost_grid(…, risk_alpha, slope_sigma_grid)
                ├─ cost_vec.f_slope_grid(…, α, σ_θ)      ← risk.slope_cvar_array
                └─ cost_vec.f_energy_cell_grid(…, α, σ_θ) ← risk.slip_cvar_array
                       └─ _energy_per_metre_wh_grid(…, slip=s_α) ← edge_travel_time_s_array(…, slip=s_α)
              out["slope_sigma"], metadata["risk_alpha"], metadata["risk"]
  ├─ 2-B: pathfinder.astar(grids["cost"]) → simulate_path (μ) → risk.route_risk_summary → yanıt "risk"
  └─ 4-B: cost_cube.build_cost_cube(…, risk_alpha, slope_sigma) → costmap.default_cost_map(risk_alpha)
            → SlopeLayer/EnergyLayer(α) → astar_4d (fizik μ) → _risk_block_4d → yanıt "risk"
/api/risk-sweep: α listesi × (grids_for_rover → astar → simulate) → results + risk_matrix + comparison
skaler referans: cost_engine.f_slope / f_energy_cell(…, α, σ_θ) ← risk.slope_cvar / slip_cvar  (grid ↔ skaler 1e-12)
```

## Test stratejisi

- **Birim (`test_risk.py`, yeni):** `cvar_multiplier` tablosu (0,5 → 0,79788, 0,9 → 1,75498,
  0,99 → 2,66521, rel 1e-5); sınır dışı α → `ValueError`; `cvar_normal(μ, σ, α)` ↔ Monte
  Carlo (2 M normal örnek, tohum 0, α ∈ {0,5, 0,9, 0,99}: kuyruk ortalaması, abs tol
  1e-2·σ); `CVaR_0,5 = μ + 0,798σ ≠ μ`; α artınca `cvar_normal` azalmaz; α = 0,999 sonlu;
  `slip_sensitivity` ↔ sayısal türev (`(s(θ+h) − s(θ−h))/2h`, rel 1e-6, parça içi noktalar)
  ve kapıda 0, eğrisiz 0; `slip_cvar` ≥ μ, kap 0,9, `slope_sigma` ile ≥ `slope_sigma`'sız,
  NaN σ → σ'sız ile eşit, θ NaN → NaN; `slope_cvar` kapı `slope_max`, σ None → θ;
  `slip_stats_array` ↔ `slip_stats`, `slip_cvar_array` ↔ `slip_cvar`, `slope_cvar_array` ↔
  `slope_cvar`, `slip_sensitivity_array` ↔ skaler: her katalog rover'ı için 100 000 rastgele
  θ ∈ [0, 90) + çapa noktaları, `np.array_equal`; `route_risk_summary` elle iki leg
  (`risk_adjusted_hours = Σ h(1−μ)/(1−s_α)`), `drawn None` → `None`, `inf` saat atlanır,
  α None → `applied False`; `thermal_cvar_cold_c` → `NotImplementedError` (mesajda "thermal"
  ve "no source"); `RISK_VALIDITY == "MODEL"`, claim "not a measured risk" içerir.
- **Maliyet yolu (`test_risk_cost.py`, yeni):** `f_slope`/`f_energy_cell` skaler ↔
  `f_slope_grid`/`f_energy_cell_grid` α'lı, her rover × 17 eğim × 5 gölge × 3 σ_θ × 3 α,
  `abs=1e-12` (H-4 kalıbı); α None yolu: `f_energy_cell_grid(s, r, sh)` ↔
  `f_energy_cell_grid(s, r, sh, risk_alpha=None, slope_sigma=σ)` `np.array_equal`;
  `edge_travel_time_s(θ, d, r)` ↔ `edge_travel_time_s(θ, d, r, slip=None)` bit-eşit, `slip=s`
  ↔ `d/cos/(1−s)/(v cos)`; `compute_cost_grid` rastgele 40×40 gridde: α None ↔ argümansız
  `np.array_equal`; α artınca hiçbir sonlu hücre ucuzlamaz (None ≤ 0,5 ≤ 0,9 ≤ 0,99) ve
  `inf` deseni değişmez; `slope_sigma_grid` şekil hatası → `ValueError`; `default_cost_map
  (risk_alpha)` `explain` katman adları aynı ve `energy`/`slope` katkısı α ile ≥ nominal;
  `build_cost_cube(risk_alpha, slope_sigma)` ≥ nominal küp, None yolu `np.array_equal`;
  `grids_for_rover`: α → `metadata["risk_alpha"]`, `slope_sigma` klon yoksa yok ve
  `metadata["risk"]["slope_sigma_source"] == "none"`, α None çıktısı argümansız çıktıyla
  bit-eşit ve `risk_alpha` anahtarı yok, girdi metadata'sında `risk_alpha` varken α None →
  yeniden hesap ve anahtar silinir, α değişince yeniden hesap (`cost_model` damgası aynı).
- **API (`test_risk_api.py`, yeni; 16×16 çekirdeksiz, `test_slip_api` fixture'ı):**
  `/api/plan` `risk_alpha=0.9` → 200, `risk.applied True`, `alpha 0.9`, `criteria.slope
  "nominal"` (klon yok) ve `sigma_sources.slope.source "none"`, `route.moves ==
  waypoint_count − 1`, `risk_adjusted_hours ≥ hours`, `mean_slip_cvar ≥ mean_slip_mu`,
  mevcut alanlar (`summary`, `slip_model`, `geojson`) aynen; α'sız istekte `risk.applied
  False`, `alpha null`, `route null`; `risk_alpha` 0,3 / 1,0 / "x" → 422; `/api/plan-4d`
  aynı iddialar (`route.moves == move_steps`); `/api/risk-sweep` varsayılan → `alphas ==
  [None, 0.5, 0.9, 0.99]`, 4 sonuç, `risk_matrix` 4×3, `comparison.deltas` 3 satır,
  `overlap_with_nominal` ∈ [0, 1], nominal satırın Δ'sı yok; `include_nominal False` → 3
  sonuç; `alphas: []` / 7 eleman / 0,2 → 422; `json.dumps(allow_nan=False)`.
- **Gerçek grid (`test_risk_sweep_real_grid.py`, skip-korumalı):** (1) v4 kilidi: LPR-1 ve
  VIPER için `grids_for_rover(load_preprocessed_grids(), rid)["cost"]` SHA-256'sı sondada
  ölçülen değerle eşit (`0e74607d…`, `8788936c…`) ve `risk_alpha=None` ile de eşit; (2)
  LPR-1 28 Eyl ve VIPER kısa leg `/api/plan-4d` α ∈ {None, 0,9, 0,99} → 200, `risk.applied`,
  `sigma_sources.slope.source == "dem_clones"`, `criteria.slope == "cvar"`,
  `risk_adjusted_hours ≥ hours`; (3) `/api/risk-sweep` LPR-1 standart çift → 200, 4 sonuç,
  `plan_ms` < 5 000; toplam < 240 s.
- Mevcut testler: `test_review3_fixes::test_h4_*`, `test_review_fixes`, `test_cost_vec`,
  `test_costmap`, `test_cost_cube`, `test_rover_grids`, `test_slip_api`, `test_plan_*`
  değişmeden geçmeli (None yolu bit-eşit).

## Hata davranışı

- `risk_alpha` sınır dışı / sayı değil → pydantic 422; `alphas` boş / > 6 / sınır dışı → 422.
- `cvar_multiplier` / `cvar_normal` kütüphane çağrısında sınır dışı α → `ValueError`
  (API'ye ulaşmaz).
- Klon önbelleği yok → eğim kriteri nominal, slip CVaR yalnız C3 σ; yanıt
  `sigma_sources.slope.source: "none"` ve `criteria.slope: "nominal"`; 200.
- `slope_sigma` şekli grid'e uymuyor → `compute_cost_grid` `ValueError`; `grids_for_rover`
  bunu önlemek için `uncertainty_layers_for_grids`'in şekil kontrolünü kullanır.
- `σ_θ` NaN/inf → 0 (genişletme yok); `θ` NaN → NaN → mevcut maske `inf` yapar.
- `route_risk_summary` `inf` süreli kenarı atlar ve sayar; `drawn None` → `risk_adjusted_
  drawn_wh None`. `inf`/`NaN` JSON'a sızmaz.
- `thermal_cvar_cold_c` → `NotImplementedError`.

## Kapsam dışı (bilinçli)

- Termal CVaR'ın uygulanması (kanca; C5/C6 sonrası).
- α'nın fiziğe (süre/batarya/marj/Monte Carlo) girmesi (reddedildi; gerekçe yukarıda).
- 4-B planlayıcının amaç fonksiyonunda CVaR-saat (STEP'in doğrudan risk maliyeti; astar_4d
  hot loop'unda süreyi ikiye ayırmak gerekir — A3/B1 adayı).
- Gölge kriterine α (B3 `p_illuminated` var ama ayrı özellik; A2/B3 raporlarında).
- Rover başına varsayılan α ya da görev profillerine α (`/api/compare` aynen).
- Endo'nun karışım modeli (arazi sınıfı yok); `μ`'nun delta düzeltmesi (ikinci derece).
- Slip σ'nın kalibrasyonu (C3 varsayımı aynen).
- Bilinen iyimserlikler (dokunulmadı, not): hamle süresi dilime yuvarlanırken enerji
  yalnızca sürüş için (B5); `horizon_map` `np.rint`; termal model rover zarfıyla tutarsız
  (D3 → C6); A2 budaması %0,2; slip'li yüzeyde planlayıcı yavaş (A3); enerji kriterinin
  slip'siz ölçeği α'da doygunluğu artırıyor (%14,6 → %40,3; C3 kararı korunuyor).

## Uygulama sırasında bulunanlar ve ölçümler (5 Eylül 2026)

**v4 kilidi ve sondanın kirlenmesi.** Sonda 1'in ilk koşumunda VIPER'ın nominal maliyet
gridi, LPR-1 döngüsünden kalan yamalı `f_energy_cell_grid` ile hesaplanmıştı; spec'e giren
SHA-256 (`590b25a1…`) bu kirli griddendi. İkinci koşum ve B2 öncesi ağaçta (`git stash`)
yeniden hesap aynı `8788936c…` özetini verdi; test, spec ve plan düzeltildi. LPR-1
(`0e74607d…`) ilk koşumda da doğruydu. `risk_alpha=None` yolu her iki rover'da bit-eşit
(`test_risk_sweep_real_grid.py::test_the_nominal_cost_grid_is_the_v4_grid_bit_for_bit`).

**Tasarım kararı: α eğim kriterine de girdi (sapma).** Sonda 3 (yalnız enerji kriteri):
4-B rotaları α'dan bağımsız aynı tek "geçiş"i yapıyordu, Spearman ≥ 0,9986, VIPER kısa leg
hiç değişmiyordu. Eğim kriterinin `min(slope_max, θ + σ_θ·m_α)` okuması (B3 σ_θ) sürgüye
tutuş verdi (Spearman 0,985 / 0,970; maliyet ortalama +%30 / +%25) ve 2-B ince gridde rotayı
belirgin biçimde değiştirdi (örtüşme ~%50). `inf` kapısı nominal θ'da kaldı; geçilebilirlik
maskesi ve 4-B'nin "kaba hücre geçilebilirse sonlu maliyet" kabulü korundu (testte).

**Ölçümler (Site11; `scripts/risk_sweep_report.py --json` →
[risk_sweep_report.md](../../research/risk_sweep_report.md)):**

| Ölçüm | Değer |
|---|---|
| Kapalı form | m_α: 0,5 → 0,798; 0,9 → 1,755; 0,99 → 2,665; 0,999 → 3,367 (2 M örnekli Monte Carlo ile 1e-2 içinde) |
| Eğri (LPR-1/VIPER, C3 ⊕ B3 medyan σ_θ 1,54°) | 10°: μ 0,182 → s_0,9 0,359 / s_0,99 0,451; 15°: 0,400 → 0,790 / 0,900 (kap); 20°: kap |
| Grid, LPR-1 (210 063 hücre) | α = 0,5 / 0,9 / 0,99: CVaR slip medyanı 0,288 / 0,395 / 0,497 (μ 0,199); kapıda %10,8 / %18,8 / %26,6; eğim kuyruğu sınırda %0,9 / %2,3 / %4,1; Spearman 0,9983 / 0,9929 / 0,9848; maliyet ort. +%8,4 / +%19,1 / +%29,9 (maks +%38 / +%75 / +%103); enerji doygunluğu %14,6 → %23,6 / %32,9 / %40,3 |
| Grid, VIPER (198 575 hücre) | CVaR slip medyanı 0,271 / 0,371 / 0,466 (μ 0,187); kapıda %5,6 / %14,1 / %22,4; eğim kuyruğu sınırda %2,8 / %7,8 / %14,5; Spearman 0,9960 / 0,9854 / 0,9700; maliyet ort. +%7,1 / +%16,0 / +%24,5 |
| Termal doygunluk (`f_thermal` ≥ 0,99) | LPR-1 %72,7 (≥ 0,9: %89,8; medyan 0,9994), VIPER %54,2 (%73,5; 0,9957); aralık/4 soğuk kuyruğu α = 0,9 → %94,0 / %81,2 → kanca |
| 2-B `/api/risk-sweep`, LPR-1 (358,494)→(206,426) | None / 0,5 / 0,9 / 0,99: 597,2 / 595,8 / 596,4 / **592,7 Wh**; 1,623 / 1,621 / 1,622 / 1,617 h; min SOC 94,31 → 94,38; maks slip 0,586 → 0,563; örtüşme 1 / 0,81 / 0,79 / **0,49**; risk matrisi α = 0,99: nominal rota **3,375 h**, α = 0,99 rotası 3,696 h |
| 2-B, LPR-1 Ay gecesi çifti | 1 465,7 → 1 453,5 / 1 448,4 / **1 439,5 Wh** (−%1,8); 2,727 → 2,744 km; min SOC 87,10 → 87,49; ort. slip 0,115 → 0,108; örtüşme 0,79 / 0,57 / 0,52; risk matrisi α = 0,99: α rotası **5,528 h** < nominal 5,563 h |
| 2-B, VIPER standart | 2 741,8 → 2 739,3 / 2 729,6 / **2 713,0 Wh**; min SOC 57,64 → 58,22; örtüşme 0,87 / 0,66 / 0,48; risk matrisi α = 0,99: nominal 11,45 h < α rotası 12,20 h |
| 2-B, VIPER kısa leg | 920,3 → 914,2 Wh; maks slip **0,594 → 0,627** (α = 0,9 ve 0,99, aynı rota; örtüşme 0,03); kuyrukta nominal 6,27 h < 7,74 h |
| 4-B + B5, LPR-1 28 Eyl | None: 41 hamle, 2,979 h, min SOC %92,5, ort. slip 0,326, B5 %100 / %99,8 / %0 (haven kuralı), MC nominal min SOC 94,5; α = 0,5 / 0,9 / 0,99: **aynı** 42 hamlelik rota (örtüşme 0,55), 2,979 h, %93,1, ort. slip 0,313, B5 %100 / %99,8 / %0, MC 95,0; ort. CVaR slip 0,462 / 0,614 / 0,705, sürüş 2,18 h → risk-ayarlı 3,19 / 6,31 / 8,19 h; plan 12,0 s (nominal, ilk çağrı) / 7,0 / 6,2 / 6,5 s; düğüm 23 177 / 24 171 / 24 279 / 23 318 |
| 4-B + B5, LPR-1 Ay gecesi | 116 hamle, 6,749 h, SOC %67,4, B5 %98,8 / %88,8 / %0 — her α'da aynı (rota α'da %84 / %80 / %80 örtüşüyor, metrikler aynı); risk-ayarlı sürüş 4,80 → 5,27 / 6,06 / 7,37 h; plan 20,2 / 17,3 / 18,6 / 21,3 s; düğüm 146 705 → 190 931 |
| 4-B + B5, VIPER kısa leg (haven kuralı) | 8 hamle, 2,235 h, SOC %72,3, B5 %99,6 / %95,0 / %95,0 — her α'da aynı rota; CVaR slip 0,693 / 0,856 / 0,900; risk-ayarlı sürüş 1,76 → 3,34 / 7,63 / 9,25 h; plan 6,9 / 3,2 / 3,0 / 3,1 s |
| Tarama süresi | 2-B dört plan 0,7–3,4 s (plan başına 56–878 ms); rapor toplamı `total_seconds` JSON'da |

**Bulgular:**
- **Etki küçük ve dürüstçe küçük.** 2-B ince gridde α = 0,99 rotayı yarı yarıya değiştiriyor
  ama nominal fizikte kazanç −0,7 … −1,8 % enerji, +0 … +0,6 % mesafe, +0,07 … +0,58 pt
  min SOC. 4-B kaba gridde (125×125) α ya tek bir geçiş yaptırıyor (LPR-1 gündüz: 41 → 42
  hamle, min SOC +0,6 pt, B5 aynı) ya da hiç (VIPER kısa leg, Ay gecesi metrikleri).
  Endo'nun sentetik "%11 → %95" sayılarıyla karşılaştırılamaz; öyle sunulmaz.
- **α rotası kuyrukta her zaman kazanmıyor.** Risk matrisi iki standart çiftte nominal
  rotanın α = 0,99'daki risk-ayarlı sürüş saatini α rotasınınkinden düşük buluyor:
  ağırlıklı kriterler (enerji kriteri 1,0'da doyuyor, eğim kriteri sigmoid) kuyruk
  süresini minimize etmiyor; CVaR'ın doğrudan amaç fonksiyonuna (STEP'in yaptığı gibi
  risk-saat) girmesi ayrı bir özellik (kapsam dışı, A3/B1). VIPER kısa leg'de α rotası
  nominal maks slip'i yükseltiyor (0,594 → 0,627): kuyruk kriterinin seçtiği rota nominal
  ölçütte "daha güvenli" olmak zorunda değil.
- **Enerji kriterinin doygunluğu α ile büyüyor** (%14,6 → %40,3): C3'ün slip'siz ölçek
  kararı bilinçli; α'da ayrımı eğim kriteri taşıyor.
- **Termal kuyruk anlamsız:** kriter zaten doymuş; kanca bırakıldı (C5/C6).
- 4-B'de α'lı planlar nominalden hızlı görünüyor (6–7 s vs 12 s) — ilk çağrının önbelleksiz
  ufuk/klon maliyeti; düğüm sayıları benzer (23–25 k), gerçek bir hızlanma değil.

**Sapmalar (tasarımdan):** α eğim kriterine de girdi (yukarıda); `/api/risk-sweep` yalnız
2-B (4-B için `/api/plan-4d.risk_alpha`; spec böyle yazıldı, teyit); `sigma_sources`'a
`relative_spread_at_anchors` eklendi; `risk_block` `multiplier` alanı taşıyor; sweep yanıtına
`note`, `references`, `sigma_sources` üst düzeyde eklendi; `comparison`'a
`evaluated_at_alpha` ve `lowest_risk_adjusted_hours`; `grids_for_rover` α'lı gridler tekrar
uyarlanınca eski damgayı ve `slope_sigma`'yı temizliyor; `_validate_start_goal` yardımcı
(`/api/plan`'ın satır içi kontrolleri aynen kaldı); rapor betiği Ay gecesi rotasında da B5
koşturuyor (C3 koşturmuyordu); v4 SHA kilidinin VIPER değeri düzeltildi. `COST_MODEL_ID` v4.

**Testler:** 40 birim (`test_risk.py`: çarpan tablosu, Monte Carlo, `CVaR_0,5 ≠ μ`,
monotonluk, türev ↔ sayısal, kap, 4 × 4 rover parite, rota özeti, blok, termal kanca) +
16 maliyet yolu (`test_risk_cost.py`: `slip=` bit-eşit, skaler ↔ grid 1e-12 4 rover × 17 × 5
× 3 × 3, None yolu `np.array_equal`, monotonluk/`inf` deseni/şekil hatası, katman
explain, küp, önbellek anahtarı, klon σ) + 13 API (`test_risk_api.py`) + 5 gerçek grid
(`test_risk_sweep_real_grid.py`). Ruff: yeni dosyalar temiz; `cost_cube`/`costmap` E402'ler
önceden vardı. Tam paket: **1 250 passed, 2 skipped** (12 dk 33 s; tek uyarı `test_visibility_validation`'ın, önceden var).
