# B5 — Monte Carlo traverse stres testi (SHERPA "Traverse Evaluation") — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → B5](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** A4 (Dünya serisi) ve A1 (safe haven, `route_margins`) — tamamlandı. Ön koşul: 11 no'lu belgenin 3. maddesi (`simulation.py` ↔ `cost_engine` enerji birleştirmesi) — bu belgede kapatılıyor.
**Kapsam:** yalnızca `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

VIPER'ın planlama ekibi (SHERPA; Shirley & Balaban 2022, Balaban vd. 2025) her
stratejik planı **binlerce kez** simüle eder: başlangıç zamanı, batarya, güç
çekişi ve etkin hız kesik Gauss dağılımlarıyla rastgele bozulur, insan
operatörünün yürütme politikası taklit edilir ve sonuçta "tamamlanma oranı,
time-to-sun-shadow, time-to-DSN-shadow, time-to-0-SOC" gibi metriklerin
**dağılımı** raporlanır. LunaPath'te bugün `simulate_path` tek deterministik
koşumdur; 4-B planlayıcı bataryayı ve gölge saatini taşır ama "plan sapınca ne
olur" sorusuna kimse cevap vermez.

Tek cümlelik iddia: **`/api/plan-4d`'nin ürettiği rota, aynı fizik
(`cost_engine`'in çekiş/idare/güneş aritmetiği) ve SHERPA'nın dağılım
parametreleriyle N kez (varsayılan 1.000) vektörize edilerek yürütülür; her
koşum SHERPA'nın "önde iken bekle, geride iken bataryayla geç" politikasını
uygular; çıktı başarı oranı (%95 güven aralığıyla), SHERPA metriklerinin
p5/p50/p95 dağılımları, histogramlar ve rota boyunca batarya/varış zarfıdır.**

## Fizik / kural notu — SHERPA'nın enjekte ettiği belirsizlikler (birebir)

| Değişken | Yön | Ortalama | σ | LunaPath karşılığı |
|---|---|---|---|---|
| Başlangıç zamanı | yalnızca gecikme | planlanan | **2 h** | `start_delay_h ≥ 0`; plan takvimi (`t_i · slice_hours`) sabit kalır, rover geriden başlar |
| Başlangıç bataryası | yalnızca aşağı | `initial_soc_pct` | **%20** | `soc0 = initial_soc · (1 − z·σ)` |
| Güç çekişi | yalnızca yukarı | CBE | **%20** | çekiş **ve** idare gücü `×(1 + z·σ)`; güneş girdisi değişmez |
| Etkin hız (SMG) | yalnızca aşağı | CBE | **%20 / 30 / 40 / 50** | sürüş süresi `÷(1 − z·σ)`; uç nokta `speed_multiplier_floor = 0.25` (4× yavaş) |
| Aktivite süresi | yukarı | CBE | %20 | **uygulanmıyor** — LunaPath rotasında bilim aktivitesi yok (A5 yapılmadı); WAIT'ler aktivite değil, politikanın kendisidir |
| DSN kesintisi | olasılıkla | — | — | koşum başına `p`; süre kesik Gauss (`mean`, `0.5·mean`, ≥ 0); rastgele anda başlar; sürerken rover **yerinde bekler** |
| SEP olayı | olasılıkla | — | — | aynı mekanizma (güvenli mod = yerinde bekleme); ayrı sayaçlar |

Kesik Gauss: `z ~ |N(0,1)|`, `z ≤ z_max` (varsayılan 3; hız ve batarya için
çarpanın tabanına göre daha küçük — çarpan hiçbir zaman negatif olmaz).
Örnekleme `scipy.stats.truncnorm` ile, `numpy.random.default_rng(seed)`
üzerinden; **aynı `seed` aynı sonucu verir**.

DSN kesintisi ve SEP olasılıkları için yayınlanmış bir sayı yok (belge 12
"modellenmiş olasılıkla" diyor); **varsayılan 0**, parametre olarak açık.
Rapor betiği `p = 0,1` duyarlılığını ölçer.

**Yürütme politikası (SHERPA'nın insan operatörü):**
- Plan her durum için bir takvim verir: `p_i = t_i · slice_hours`. Plan, ışığı
  beklemeyi zaten WAIT'ler olarak içerir; politika bu takvimi izler.
- MOVE legi: kalkış `max(clock, p_i)`. Rover **geride** ise (`clock ≥ p_i`)
  hemen sürer — gölgeden bataryayla geçer. **Önde** ise planlanan kalkışa
  kadar bulunduğu hücrede bekler ("önde iken bekle"); planlayıcının varış
  dilimleri yukarı yuvarlandığı için nominal koşum her durumda biraz öndedir
  ve bu kural nominal koşumun plan takvimini birebir yeniden üretmesini sağlar
  (test: nominal koşum = planlayıcının `path_battery_pct`'si).
- WAIT legi (plandaki şarj/ışık bekleme molası): kalkış `max(clock, p_{i+1})`
  — önde ise `p_{i+1}`'e kadar bekler; geride ise mola **atlanır** ("geride
  kalınca şarj molaları kısaltılır").
- Kesinti/SEP: kalkış anı kesinti penceresine düşerse kalkış pencerenin
  sonuna ertelenir (leg başladıysa bitirilir — leg çözünürlüğü).

**Enerji ve gölge saati aritmetiği** planlayıcınınkinin aynısıdır:
- Sürüş: `drain = (P_traction·m_p + P_hk(ε̄)·m_p − P_solar·(1 − ε̄)) · Δt`,
  `ε̄` = sürüş aralığında kalkış ve varış hücrelerinin **zaman-integrali**
  ortalaması (trapez; hücre sütunlarının kümülatif integraliyle kesin).
- Bekleme: `drain = (P_hk(ε̄)·m_p − P_solar·(1 − ε̄)) · w`.
- Batarya kapasitede kırpılır (`min(e_cap, ·)`).
- Gölge saati (planlayıcı kuralı): varış hücresinin varış anındaki maruziyeti
  `≥ 0,5` ise `dark += Δt·ε`, değilse `dark = 0`. Çok dilimli bir bekleme tek
  geçiş sayılır — karanlık **fazla** tahmin edilir, asla eksik.
- Başarısızlık (ilk nedeni kaydedilir): `battery < 0` → `battery_depleted`;
  `dark > h_max_shadow_h` → `shadow_endurance`; koşum uzatılmış ufkun sonunu
  aşarsa → `horizon_exceeded`. Rezervin (`soc_min_pct`) altına inmek
  başarısızlık değil, "tam başarı"yı bozan marj ihlalidir.

**Tanımlar:**
- **Tamamlanma** = hedefe canlı varış.
- **Tam başarı** = tamamlanma ∧ batarya hiç rezervin altına inmedi ∧
  (haven alanları biliniyorsa) hiçbir durumda `tts > Dünya batışına kalan`
  (hedef dahil: haven olmayan bir hedefe Dünya battıktan sonra varmak tam
  başarı değildir).
- Oranlar için **Wilson %95 güven aralığı** (N = 1.000'de ±~1,4 puan).

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Rolü |
|---|---|---|
| `move_battery_drain_wh`, `wait_battery_drain_wh`, `housekeeping_power_w`, `edge_travel_time_s` | `cost_engine.py` | Referans aritmetik; MC bunları vektörize eder, testler eşitliği doğrular |
| `astar_4d` sonucu (`path_states`, `path_battery_pct`) | `pathfinder_4d.py` | Girdi rota; nominal koşum statik gökyüzünde planlayıcı bataryasıyla birebir |
| `body_track_for_series`, `illuminated_mask`, `horizon_cache_path` | `illumination_series.py`, `illumination.py` | Rota-yerel Güneş ve Dünya sütunları |
| `safe_haven_for_grids`, `time_to_safe_haven_hours`, `hours_until_earthset_cube`, `_DARK_RATIO_THRESHOLD` | `safe_haven.py` | Haven süresi ve Dünya batış sütunları |
| `coarsen_grid`, `coarsen_traversable` | `cost_cube.py` | Kaba grid geometrisi |
| `grids_for_rover` | `rover_grids.py` | Rover'a özgü geçilebilirlik |

## Bileşenler

### 0. Enerji birleştirmesi — `simulation.simulate_path` (11 no'lu belge §2.3, madde 3)

Bugün simülatör sürüşte **brüt** çekişi düşer (`gross_energy_per_metre_wh`),
4-B planlayıcı ise güneş girdisini de sayar (`move_battery_drain_wh`): aynı
rota `/api/plan`'da farklı, `/api/plan-4d`'de farklı batarya raporlar.
Değişiklik: sürüş adımında batarya değişimi `move_battery_drain_wh`'nin
işaretli değeri (brüt çekiş − güneş girdisi), kapasitede kırpılır.
`RoverState.step_energy_wh` brüt çekiş olarak kalır (anlamı değişmez), yeni
alan `step_solar_wh`; `summarize_simulation` `total_solar_energy_wh` ekler.
Şarj molası mantığı zaten fiziksel (güneşle, süre alarak) — değişmez. Böylece
planlayıcı, 2-B simülatör ve MC aynı üç fonksiyonu kullanır.

Beklenen etki: güneşli, düz hücrelerde LPR-1'in dizisi (410 W) sürüş çekişini
(240 W) aşar — batarya sürerken dolar; testlerde eski brüt beklentiler net
değerlerle güncellenir (davranış değişikliği bilinçli).

### 1. `app/stress_test.py` — yeni modül (saf, FastAPI'siz)

```python
SHERPA_DEFAULTS = Perturbations(
    start_delay_sigma_h=2.0, initial_soc_sigma=0.20, power_draw_sigma=0.20,
    speed_sigma=0.20, speed_multiplier_floor=0.25, z_max=3.0,
    dsn_outage_probability=0.0, dsn_outage_mean_h=4.0,
    sep_event_probability=0.0, sep_event_mean_h=24.0,
)
sample_perturbations(rng, n_runs, p, initial_soc_frac, planned_end_h) -> dict[str, np.ndarray]
    # start_delay_h, speed_multiplier, power_multiplier, initial_soc_frac,
    # dsn_start_h/dsn_end_h, sep_start_h/sep_end_h (olay yoksa nan)

@dataclass RouteLegs: cells (K+1,2), slices (K+1,), is_wait (K,), distance_m (K,),
                      travel_h (K,), traction_w (K,), planned_h (K+1,)
route_legs(states, slope, resolution_m, rover, traversable) -> RouteLegs
    # doğrulama: t_0 = 0, t artan, ardışık hücreler 8-komşu veya aynı, hepsi geçilebilir;
    # süre trapez eğimle edge_travel_time_s (planlayıcının aynısı); ValueError

@dataclass RouteSky: shadow (T, K+1), earth (T, K+1) | None, deadline_h (T, K+1) | None,
                     tts_h (K+1,) | None, slice_hours, n_slices
route_sky_columns(horizon, metadata, cells, coarsen, start_utc, n_slices, slice_hours,
                  bodies=("SUN", "EARTH")) -> (shadow (T,K), earth (T,K))
    # Kaba hücrenin f×f ince bloğu: Güneş için blok ORTALAMASI (coarsen_grid "mean"),
    # Dünya için blok VE'si (coarsen_traversable) — plan-4d'nin küpüyle birebir.

simulate_runs(legs, sky, rover, samples, dark_threshold=0.5) -> RunResults
    # (N,) vektörler: reached, first_failure, duration_h, odometry_m, min_battery_wh,
    # final_battery_wh, max_dark_h, min_reserve_ok, tts_sun_min/mean, tts_dsn_min,
    # tts_zero_soc_min, dsn_events, dsn_hours, states_past_deadline,
    # outage_hours_dsn/sep; per-state (K+1, N): arrival_h, battery_wh, alive

summarize_runs(results, legs, sky, rover, samples, n_bins=20) -> dict   # JSON-hazır
stress_test_route(legs, sky, rover, initial_soc_frac, n_runs, seed, perturbations) -> dict
    # sample + simulate + summarize + nominal (tüm çarpanlar 1, gecikme 0, kesinti yok)
wilson_interval(k, n) -> (lo, hi)
```

Zaman: sürekli saat; gökyüzü sütunları dilim-sabit; kümülatif maruziyet
integrali `E[k, t]` ile aralık ortalamaları kesin; `next_dark[k, t]` geri
taraması time-to-sun-shadow için (uygulamada "aydınlanana kadar bekle"
dalı gereksiz çıktı, bkz. bulgular). Karmaşıklık O(K·N); K ≤ ~400,
N ≤ 20.000.

Uzatılmış ufuk: `T_ext = ceil((planlı_süre / speed_floor + delay_max +
outage_max) / slice_hours) + 1` — rota-yerel sütunlar olduğu için maliyet
`K·f²·T_ext` maske değerlendirmesi (K = 100, f = 4, T = 1.000 → 1,6 M; ms
mertebesi) ve `T_ext` SPICE çağrısı.

### 2. `POST /api/stress-test` — uç

İstek (`StressTestRequest`):

| Alan | Tip | Varsayılan | Anlam |
|---|---|---|---|
| `path_states` | `[[r,c,t], ...]` (≥ 2) | zorunlu | `/api/plan-4d` yanıtındaki kaba durumlar |
| `rover_id`, `coarsen`, `slice_hours`, `start_utc`, `initial_soc_pct` | plan-4d ile aynı | `slice_hours` zorunlu | Ortamı planla aynı kurmak için; `slice_hours` plan yanıtından alınır |
| `n_runs` | int 1..20000 | 1000 | |
| `seed` | int | 0 | Tekrarlanabilirlik |
| `perturbations` | nesne | SHERPA varsayılanları | Yukarıdaki tablo; verilen alanlar üstüne yazılır |
| `label` | str | `null` | Yanıta aynen eklenir (iki rotayı ayırt etmek için) |
| `n_bins` | int 5..100 | 20 | Histogram |

Yanıt:

```json
{
  "label": null, "rover_id": "nasa_viper", "n_runs": 1000, "seed": 0,
  "route": {"n_states": 41, "move_steps": 40, "wait_steps": 0,
            "planned_duration_h": 3.9, "odometry_m": 8600.0,
            "ends_at_safe_haven": true},
  "perturbations": {"...": "kullanılan parametreler", "source": "Shirley & Balaban 2022"},
  "sky_model": {"model": "spice_horizon | static", "time_varying": true,
                "n_slices_extended": 512, "horizon_hours_extended": 49.0},
  "safe_haven_model": {"model": "spice_horizon | unavailable"},
  "rates": {"completion": {"count": 987, "rate": 0.987, "ci95": [0.978, 0.992]},
            "full_success": {}, "reserve_breached": {}},
  "failures": {"battery_depleted": 9, "shadow_endurance": 4, "horizon_exceeded": 0},
  "metrics": {"duration_h": {"mean": 0, "std": 0, "p5": 0, "p50": 0, "p95": 0, "min": 0, "max": 0, "n": 0},
              "duration_normalized": {}, "odometry_m": {}, "min_battery_pct": {},
              "final_battery_pct": {}, "max_continuous_shadow_h": {},
              "time_to_sun_shadow_min_h": {}, "time_to_sun_shadow_mean_h": {},
              "time_to_dsn_shadow_min_h": {}, "time_to_zero_soc_min_h": {},
              "dsn_shadow_events": {}, "dsn_shadow_hours": {},
              "states_past_haven_deadline": {},
              "start_delay_h": {}, "speed_multiplier": {}, "power_multiplier": {},
              "initial_soc_pct": {}},
  "histograms": {"duration_h": {"edges": [], "counts": []}, "min_battery_pct": {}},
  "per_state": {"arrival_h": {"p5": [], "p50": [], "p95": []},
                "battery_pct": {"p5": [], "p50": [], "p95": []},
                "alive_fraction": []},
  "outages": {"dsn": {"runs": 0, "mean_hours": null}, "sep": {"runs": 0, "mean_hours": null}},
  "nominal": {"duration_h": 0, "min_battery_pct": 0, "final_battery_pct": 0,
              "max_continuous_shadow_h": 0, "reached": true},
  "verdict": {"reaches_goal_at_95pct": true, "full_success_at_95pct": true,
              "text": "987/1000 runs reached the goal (95% CI 97.8-99.2%); ..."},
  "timing_ms": {"sky": 410.0, "runs": 180.0, "total": 900.0}
}
```

Metriklerde `null` yalnızca "hiçbir koşumda tanımlı değil" durumunda
(ör. time-to-DSN-shadow Dünya sütunu yokken). Kaba ortam kurulumu:
plan-4d'nin kaba geometri ve haven-tts blokları `_coarse_geometry` ve
`_coarse_time_to_haven` yardımcılarına çıkarılır; `plan_4d` bunları kullanır
(davranış aynı). Dünya batış sütunu, rota-yerel Dünya serisini ufkun 14 gün
(`DEFAULT_EARTHSET_LOOKAHEAD_HOURS`) ötesine uzatarak `hours_until_earthset_cube`
ile bulunur — ayrı ön-bakış fonksiyonuna gerek yok; seri sonunda hâlâ
bağlantı varsa açık uçlu (`inf` → `null`).

Hatalar: grid yüklü değil → 503 (mevcut kalıp); `path_states` doğrulaması
(sınır, komşuluk, geçilebilirlik, dilim sırası) → 422 gerekçeli; `slice_hours`
yok → 422 (pydantic); gökyüzü yoksa `static` etiketli koşum (gecikmenin etkisi
yok, yanıt söyler). Kesinlikle uydurma sayı yok.

`/api/compare`'a bağlama (belge 12 madde 4): **yapılmıyor.** `/api/compare`
zamansız 2-B rotaları kıyaslar; MC 4-B rotaya ihtiyaç duyar. İki rotayı
kıyaslamak = iki `/api/stress-test` çağrısı; yanıttaki `verdict` ve
`rates.full_success.ci95` kıyas anahtarıdır (`label` ile). Sapma olarak
kaydedilir.

### 3. `scripts/stress_test_report.py` → `docs/research/stress_test_report.md`

Gerçek gridde: (a) VIPER haven→haven çifti (A1 sondasından: (89,123)→(51,106),
30 Mayıs 2027), (b) LPR-1 için gün doğumu civarı bir çift (Eylül 2026),
her biri SHERPA hız σ taraması (%20/30/40/50) × N = 1.000, DSN kesinti
duyarlılığı (p = 0,1, 4 h); süreler. Çekirdek/ufuk yoksa açıklayıp 0 ile çıkar.

## Veri akışı

```
plan-4d yanıtı (path_states, slice_hours, coarsen, rover_id, start_utc)
   │
   ▼
route_legs ──── kaba eğim/yükseklik/geçilebilirlik (plan-4d ile aynı yardımcı)
route_sky_columns ── horizon_map.npy + SPICE (rota hücrelerinin ince blokları, T_ext dilim)
tts (kaba, A1) + hours_until_earthset (uzatılmış Dünya sütunu)
   │
   ▼
sample_perturbations(seed) → simulate_runs (K leg × N koşum, NumPy) → summarize_runs
   │
   ▼
JSON: oranlar + CI, dağılımlar, histogramlar, per-state zarf, nominal, verdict
```

## Test stratejisi

- `test_stress_test.py` (saf, sentetik):
  - Örnekleme: yönler (gecikme ≥ 0, hız ≤ 1 ve ≥ taban, güç ≥ 1, SOC ≤ nominal),
    `z_max` kesmesi, seed tekrarlanabilirliği, σ = 0 → tam nominal.
  - `route_legs`: doğrulama hataları; sürelerin `edge_travel_time_s` trapeziyle eşitliği.
  - Nominal koşum statik gökyüzünde `astar_4d`'nin `path_battery_pct`'siyle 1e-6 içinde
    (MOVE ve WAIT içeren rota); sürüş süresi/varış `t_i·slice_hours` sınırında.
  - Tek leg elle: `move_battery_drain_wh` ve `wait_battery_drain_wh` ile eşitlik; güç çarpanı yalnız çekiş+idareyi, hız çarpanı yalnız süreyi ölçekler.
  - Politika: önde + karanlık → aydınlanana kadar bekler (≤ planlı kalkış); geride → WAIT atlanır.
  - Başarısızlık nedenleri: karanlıkta uzun sürüş → `battery_depleted`; `h_max_shadow_h` küçük → `shadow_endurance`; çok yavaş → `horizon_exceeded`; ilk neden.
  - Kesinti: `p = 1`, kalkış pencereye düşünce erteleme; sayaçlar.
  - Marjlar: statik/senaryolu sütunlarda time-to-sun-shadow, DSN, 0-SOC, olay sayısı beklenen değerlerle.
  - `summarize_runs`: yüzdelikler, Wilson CI (bilinen değerler: 0/10, 10/10, 5/10), histogram toplamı = N, per-state uzunluklar, `null` kuralı.
  - `route_sky_columns`: senaryolu gökyüzüyle (A1'deki `_script_ephemeris`) blok ortalaması / VE'si.
- `test_stress_test_api.py`: 200 şeması, `static` etiketi, 422'ler (geçersiz `path_states`), seed tekrarı, `label` yankısı, `n_runs` sınırı.
- `test_simulation.py`: net sürüş düşümü (güneşli düz: batarya artar; gölgeli: brüt), `step_solar_wh`, `total_solar_energy_wh`.
- `test_stress_test_real_grid.py` (skip-guarded): rota-yerel gökyüzü sütunları plan-4d küpünün rota sütunlarıyla birebir; VIPER haven→haven çifti N = 1.000 < 5 s; oranlar ve nominal planlayıcıyla tutarlı.

## Hata davranışı

- `inf` JSON'a sızmaz (`null`); `NaN` yok.
- Gökyüzü/haven yoksa etiketli düşüş, 500 yok.
- Rota doğrulaması 422; ortam kurulamazsa (grid yok) 503.

## Uygulama sırasında bulunanlar ve ölçümler (4 Eylül 2026)

**Politika sadeleşti.** Tasarımdaki "önde iken varış hücresi karanlıksa
aydınlanana kadar bekle" dalı gereksiz çıktı: plan ışığı beklemeyi zaten
WAIT olarak içeriyor ve planlayıcı varış dilimlerini yukarı yuvarladığı için
nominal koşum her durumda biraz öndedir. Kural "kalkış = max(clock, planlanan
kalkış)" olunca nominal koşum plan takvimini birebir izliyor; `next_lit`
tablosu kaldırıldı. Politika bölümü buna göre güncellendi.

**Planlayıcının dilim yuvarlaması enerjide görünüyor.** `astar_4d` bir
hareketin saatini `ceil(travel / slice_hours)` dilim ilerletirken bataryayı
yalnızca `travel_h` için düşüyor; aradaki fark (dilim tamamlanana kadar
bekleme) enerjiye yansımıyor. MC'nin nominal koşumu bu beklemeyi hücrede
idare tüketimi / güneş geliriyle sayınca VIPER'ın haven→haven rotasında en
düşük batarya planlayıcının %32,1'inden **%23,2**'ye iniyor (rezerv %20).
Statik gökyüzünde ve hareket süresi dilime tam bölünen kurgularda iki hesap
birebir eşit (`test_the_nominal_run_matches_astar_4d_on_its_own_static_cube`).
Bu, 4-B planlayıcı için ayrı bir düzeltme maddesidir (yuvarlama artığını
bekleme olarak fiyatlandırmak); B5 kapsamında planlayıcıya dokunulmadı.

**Haven kuralı "tam başarı"yı Ay gününe bağlıyor.** Haven bulunmayan bir Ay
gününde (LPR-1, Eylül 2026; A1) `tts = ∞` olduğu için her durum batış
süresini "aşıyor" ve tam başarı tanım gereği 0. Bu yüzden ara oran
`rates.reached_within_reserve` (varış ∧ rezerv ihlali yok) eklendi ve
`verdict.text` haven kuralının neyi düşürdüğünü söylüyor;
`verdict.haven_rule_known` alanı kuralın denetlenip denetlenemediğini verir.

**Ölçümler (Site11, 1.000 koşum, tohum 0; `scripts/stress_test_report.py`):**

| Rota | Plan | Hız σ | Tamamlanma (Wilson %95) | Rezerv içinde | Tam başarı | Arıza | Süre p50 / p95 |
|---|---|---|---|---|---|---|---|
| VIPER haven→haven, 30 May 2027 | 40 MOVE, 7,36 h, min batarya %32,1 | %20 | **%29,6** (26,9–32,5) | %1,4 | %1,4 | 704 batarya | 7,12 / 8,82 h |
| | | %30 | %22,3 (19,8–25,0) | | %1,0 | | 6,94 / 8,88 h |
| | | %40 | %17,9 (15,7–20,4) | | %0,9 | | 6,88 / 8,99 h |
| | | %50 | %15,8 (13,7–18,2) | | %0,9 | | 6,84 / 9,01 h |
| | | %20 + DSN p 0,1 | %28,0 (25,3–30,9) | | %1,4 | | 7,27 / 10,02 h |
| LPR-1, 28 Eyl 2026 | 40 MOVE, 2,16 h, min batarya %96 | %20 | **%100** (99,6–100) | %100 | %0 (haven yok) | 0 | 3,10 / 5,52 h |
| | | %50 | %100 (99,6–100) | %100 | %0 | 0 | 3,63 / 6,54 h |

VIPER rotası bütünüyle gölgede (nominal `max_continuous_shadow_h` = 7,27 h)
ve bataryayla sürülüyor; güç +%16 ve hız −%16 ortalama sapmaları tüketimi
~1,4 kat artırınca koşumların %70'i bataryayı bitiriyor — planlayıcı
maliyeti en aza indiriyor, tek marj %20 rezerv. Sunumda cümle: "1.000
koşumda %30 hedefe vardı; nominalde uygun görünen plan SHERPA dağılımları
altında kırılgan" — B1/B2'nin (risk-farkında planlama) gerekçesi.

Süreler: gökyüzü sütunları 0,8–2,1 s (rota-yerel; 41 hücre × 16 ince hücre ×
~4.500 dilim), 1.000 koşum 0,06–0,6 s, uç toplam 1,0–2,4 s; plan-4d 8–10 s.
Gerçek grid testi: rota-yerel sütunlar plan-4d küpünün rota sütunlarıyla
1e-12 içinde eşit.

**Enerji birleştirmesi (Task 0):** `simulate_path` artık sürüşte güneş
gelirini sayıyor; tam güneşte düz zeminde LPR-1 (410 W dizi, 240 W çekiş) ve
LUVMI-M (140 W, 110 W) bataryası sürerken dolu kalıyor. Eski "tam güneşte
şarj molası" bekleyen dört test (test_simulation, test_review2/3/_fixes)
yarı gölgeye taşındı — o gölgede sürüş net 44 Wh/adım düşürüyor, mola hâlâ
şarj ediyor.

## Kapsam dışı (bilinçli)

- Bilim aktiviteleri / istasyon sayısı (A5), ISR mesafesi, PSR sayısı (katman yok).
- `/api/compare` değişikliği (yukarıda).
- Kesinti sırasında leg ortasında durma (leg çözünürlüğü).
- DEM belirsizliği (B3), slip dağılımı (B2/C3) — burada yalnızca SHERPA'nın dört operasyonel dağılımı.
