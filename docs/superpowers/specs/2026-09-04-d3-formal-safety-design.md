# D3 — Formal güvenlik gereksinimleri: FRETISH + STL robustness monitörü (RTAMT) — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → D3](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** A4 (`path_earth_visible`, `path_hours_until_earthset`), A1 (`path_time_to_haven_h`, `path_haven_margin_h`), B5 (`/api/stress-test` dağılımları, yalnızca raporda) — tamamlandı. B3 kullanılmıyor.
**Kapsam:** `backend/app/`, `backend/test_*.py`, `backend/requirements.txt`, `lunapath_ros/`, `scripts/`, `docs/`, `README.md`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor.

---

## Amaç

LunaPath'in kısıt denetimi bugün ikili: `check_profile_constraints` bir
kısıtın sağlanıp sağlanmadığını söyler (`satisfied: true/false`), marjı
söylemez; `replan_triggers` eşik karşılaştırmasıdır. Bu özellik güvenlik
gereksinimlerini **NASA FRET'in yapılandırılmış doğal dili FRETISH**
kalıbında yazar, her birini **Sinyal Zamansal Mantığı (STL)** formülüne
elle çevirir ve planlanan rotanın telemetri izini bu formüllere karşı
**nicel robustness** (ρ) ile denetler: ihlale kaç saat / kaç °C / kaç
yüzde puanı / kaç derece kaldı. Değerlendirici AIT'nin RTAMT kütüphanesi
(ayrık-zaman, offline, BSD-3) ve aynı semantiği taşıyan yerleşik bir
motor; ikisi her istekte çapraz kontrol edilir.

Tek cümlelik iddia: **"Güvenlik gereksinimlerimiz FRETISH kalıbında yazıldı,
STL'e elle çevrildi ve her planlanan rota bu gereksinimlere karşı RTAMT ile
çalışma-zamanı izleme (runtime monitoring) yoluyla nicel marjla denetleniyor."**
Söylenmeyen: "FRET aracıyla üretildi" (araç kurulmadı; gramerine göre elle
yazıldı) ve "model checking ile ispatlandı" (yalnızca somut izler
denetleniyor; araştırma belgesi Bölüm 5'teki ayrım).

## Formal yöntem notu

### STL sözdizimi (kullanılan alt küme)

```
φ ::= sig ≥ c | sig ≤ c | ¬φ | φ ∧ φ | φ ∨ φ | φ → φ
    | G φ | F φ | G[a,b] φ | F[a,b] φ | φ U[a,b] φ
```

`sig` bir gerçel sinyaldir (izdeki örnek dizisi), `c` bir eşiktir. `>`
ve `<`, `≥` ve `≤` ile aynı robustness'a sahiptir (sınır ölçü-sıfır).

### Robustness (uzamsal, Donzé & Maler 2010; RTAMT'nin ayrık-zaman offline semantiği)

Bir iz `w = (t_0, x_0), …, (t_{n−1}, x_{n−1})` için ρ(φ, w, i):

| Formül | ρ |
|---|---|
| `sig ≥ c` | `x_i[sig] − c` |
| `sig ≤ c` | `c − x_i[sig]` |
| `¬φ` | `−ρ(φ, i)` |
| `φ ∧ ψ` / `φ ∨ ψ` | `min` / `max` |
| `φ → ψ` | `max(−ρ(φ, i), ρ(ψ, i))` |
| `G φ` (sınırsız) | `min_{j ≥ i} ρ(φ, j)` — izin sonuna kadar |
| `F φ` (sınırsız) | `max_{j ≥ i} ρ(φ, j)` |
| `G[a,b] φ`, `F[a,b] φ` | pencere `[i+a, i+b]` **∩ mevcut örnekler** üzerinde min / max (RTAMT 0.3.5 ile 4 Eylül 2026'da ölçüldü: iz sonunda pencere kırpılır, örn. `always[0,3] (x ≥ 0)` `x = [1,2,3,4,5]` → `[1,2,3,4,5]`) |
| `φ U[a,b] ψ` | `max_{j ∈ [i+a, i+b]} min(ρ(ψ, j), min_{i ≤ k < j} ρ(φ, k))` |

Rapor edilen değer `ρ(φ, w, 0)`: izin başından bakılan tüm-iz kararı.
`ρ ≥ 0` sağlandı, `ρ < 0` ihlal; `|ρ|` gereksinimin biriminde marj/ihlal
büyüklüğü. `ρ = 0` sınır (sağlandı sayılır; yanıtta `boundary: true`).

**Sonlu iz semantiği (bilinçli seçim):** Katalogdaki her formül sınırsız
`G`/`F` ile, zaman pencereli davranışı **türetilmiş zaman sinyallerine**
gömerek yazılır (aşağıda). Böylece ρ örnekleme adımından bağımsızdır (min /
max her örneği görür), birimi saattir ve düzensiz örnekleme (`elapsed_hours`)
yeniden örneklenmeden verilebilir. Yerleşik motor pencereli operatörleri de
uygular (örnek sayısı cinsinden, düzgün `dt_h` gerektirir); bunlar
RTAMT'ye karşı çapraz-kontrol testlerinde ve isteğe bağlı çevrimiçi kullanımda
kullanılır, katalogda kullanılmaz.

**Kapsam (FRET `scope`):** "In moving mode …", "Upon at_goal …" gibi
kapsamlı gereksinimler `G(scope → φ)` biçimindedir. Boole kapsam
göstergesinin ±sabit robustness'ı ihlal büyüklüğünü kırpacağından (klasik
STL sorunu), kapsam **örnek maskesi** olarak uygulanır: formül yalnızca
kapsamın tuttuğu örneklerden oluşan alt-izde değerlendirilir. Kataloğun
kapsamlı gereksinimleri anlık yüklemler olduğundan bu, `G(scope → φ)` ile
birebir aynı ρ'yu verir; kapsam hiç tutmuyorsa gereksinim `uygulanamaz`
(`applicable: false`, nedeniyle) — boşlukla "sağlandı" denmez.

### FRETISH → STL eşlemesi

FRETISH cümlesi `[scope] [condition] component shall [timing] [response]`
(Giannakopoulou vd. 2020). Kullanılan kalıplar:

| FRETISH kalıbı | Zamansal formül | Katalogda |
|---|---|---|
| `component shall always satisfy R` | `G R` | R01, R02, R04–R07 |
| `upon C component shall within N hours satisfy R` | `G (C → F[0,N] R)` | R03 (izlenen biçimi türetilmiş `hours_below_reserve_h ≤ N`) |
| `in M mode component shall always satisfy R` | `G (M → R)` | R08, R11 (kapsam maskesi) |
| `component shall always satisfy A ≤ B` | `G (B − A ≥ 0)` | R09 (`haven_margin_h`) |
| `component shall eventually satisfy R` | `F R` | R10 |

### Gereksinim kataloğu

Eşikler **rover'dan** (`constants.ROVERS`) okunur; bir rover'da alan `None`
ise gereksinim o rover için `uygulanamaz` olarak raporlanır (LUVMI-M'nin
`elec_op_*`'ı gibi). Yalnızca R03'ün 6 saatlik son tarihi rover kataloğunda
yoktur: araştırma belgesindeki örnekten alınan katalog sabiti
`RECHARGE_DEADLINE_H = 6.0`, `/api/safety-check` ile değiştirilebilir ve
yanıtta `threshold_source: "catalogue"` olarak işaretlenir.

| ID | Ad | Sınıf | FRETISH (özet) | İzlenen STL | Sinyal | Birim | Rover parametresi |
|---|---|---|---|---|---|---|---|
| LP-R01 | shadow_endurance | safety | The rover shall always satisfy shadow_continuous_h ≤ h_max_shadow_h | `G (shadow_continuous_h ≤ H)` (boole eşdeğeri `G F[0,H] lit`) | kesintisiz gölge saati (koşan sayaç; gölge = `shadow_ratio > 0,2`, `simulation._shadow_and_power_checks` ile aynı) | h | `h_max_shadow_h` |
| LP-R02 | soc_reserve | safety | The rover shall always satisfy soc_pct ≥ soc_min | `G (soc_pct ≥ S)` | SOC (2-B: `battery_low_pct` — şarj molası öncesi dip; 4-B: `path_battery_pct`) | yüzde puanı | `soc_min_pct`×100 |
| LP-R03 | soc_recovery | safety | Upon soc_pct < soc_min the rover shall within 6 hours satisfy charging | ders kitabı `G ((soc<S) → F[0,6h] charging)`; izlenen `G (hours_below_reserve_h ≤ 6)` | rezerv altında şarj başlamadan geçen saat (nedensel sayaç: `soc ≥ S` ya da `charging` görülen son andan beri) | h | katalog sabiti 6 h |
| LP-R04 | electronics_thermal | safety | The rover shall always satisfy elec_op_min ≤ inner_temp_c ≤ elec_op_max | `G (T ≥ Tmin ∧ T ≤ Tmax)` | iç sıcaklık `surface_to_inner(surface_temp_c, rover)` | °C | `elec_op_min_c/max_c` |
| LP-R05 | battery_thermal | safety | … bat_op_min ≤ inner_temp_c ≤ bat_op_max | aynı | aynı iç sıcaklık modeli (ayrı batarya termal modeli yok; belgelenir) | °C | `bat_op_min_c/max_c` |
| LP-R06 | step_slope | safety | The rover shall always satisfy drive_slope_deg ≤ slope_max | `G (drive_slope ≤ θmax)` | sürüş eğimi = max(hücre eğimi, adım eğimi) — `simulate_path`'in kullandığı büyüklük | ° | `slope_max_deg` |
| LP-R07 | cross_slope | safety | … lateral_slope_deg ≤ slope_lateral_max | `G (lateral ≤ θlat)` | kenarın yanal eğimi, planlayıcıların formülü (`cost_engine.lateral_slope_tan`, iki hücre gradyanının ortalaması × yön birim vektörü) | ° | `slope_lateral_max_deg` |
| LP-R08 | dte_while_moving | safety | In moving mode the rover shall always satisfy earth_visible | `G (moving → earth_link_h > 0)` | Dünya bağlantısına kalan saat (`path_hours_until_earthset`; görünmüyorsa −(o hamlenin süresi): bağlantısız sürülen saat) — zaman-robustness vekili | h | — (4-B, A4/A1 alanları) |
| LP-R09 | safe_haven_leg | safety | The rover shall always satisfy time_to_haven_h ≤ hours_until_earthset | `G (haven_margin_h ≥ 0)` | `path_haven_margin_h` (A1) | h | — (4-B) |
| LP-R10 | goal_reached | mission | The rover shall eventually satisfy at_goal | `F (dist_to_goal_m ≤ 0)` | hedefe kalan rota mesafesi | m | — |
| LP-R11 | soc_at_goal | safety | In at_goal mode the rover shall always satisfy soc_pct ≥ soc_min | `G (at_goal → soc ≥ S)` (kapsam maskesi) | varıştaki SOC (şarj molası öncesi) | yüzde puanı | `soc_min_pct`×100 |

R08/R09 yalnızca zamanlı (4-B veya telemetri) izlerde uygulanabilir; 2-B izde
`applicable: false, reason: "no time axis / no Earth field"`. Açık uçlu
değerler (`hours_until_earthset = None`: 14 günlük ön-bakışta batış yok)
ρ = +∞ → JSON'da `rho: null, open_ended: true, satisfied: true`.

**Bilinen iyimserlikler (B3/B5'ten, D3 kapsamı dışı, yanıtta `notes`):**
4-B planlayıcı hareket süresini dilime yukarı yuvarlarken enerjiyi yalnızca
sürüş için düşer (batarya iyimser); termal alan statik uzun-dönem katman
(`thermal_source: "static_layer"`); DEM'in en-iyi-tahmin eğimleri klonlara
göre %6–10 iyimser.

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

| Yetenek | Kod | Rolü |
|---|---|---|
| `simulate_path` → `RoverState` | `simulation.py` | 2-B iz: `elapsed_hours`, `battery_low_pct`, `slope_deg`, `segment_slope_deg`, `surface_temp_c`, `shadow_ratio`, `step_energy_wh`, `step_solar_wh`, `recharged_this_step`, `stranded`, `distance_m` |
| `MAX_RECHARGE_HOURS` | `simulation.py` | Mahsur kalan izin uzatma süresi (bir Ay günü) |
| `surface_to_inner` | `cost_engine.py` | İç sıcaklık |
| `lateral_slope_tan` | `cost_engine.py` | Yanal eğim (planlayıcılarla aynı) |
| `coarsen_grid`, `coarsen_traversable` | `cost_cube.py` | 4-B kaba geometri (`_coarse_geometry` ile aynı kural: eğim max, yükseklik merkez, termal ortalama) |
| `/api/plan-4d` yanıt alanları | `main.py`, `pathfinder_4d.py` | `path_states`, `path_battery_pct`, `path_dark_hours`, `path_earth_visible`, `path_hours_until_earthset`, `path_time_to_haven_h`, `path_haven_margin_h`, `slice_hours` |
| `_attach_constraint_check` | `main.py` | `/api/compare` profil başına simülasyon — aynı `states` ile marj bloğu |
| `check_profile_constraints` | `scenarios.py` | Değişmez; raporda "ikili karar vs marj" kıyası |
| `ReplanTrigger` | `lunapath_msgs` | ROS düğümünün yayınladığı mesaj |
| `stress_test` dağılımları | `/api/stress-test` | Raporda ρ dağılımı (R01/R02/R10 SHERPA koşumlarından aritmetikle) |

## Bileşenler

### 1. `app/safety_monitor.py` — saf modül (FastAPI'siz)

```python
RECHARGE_DEADLINE_H = 6.0; SHADOW_THRESHOLD = 0.2; STRANDED_EXTENSION_H = MAX_RECHARGE_HOURS

# STL AST (dondurulmuş dataclass'lar) ve iki motor
Atom(signal, op, threshold); Not(f); And(*fs); Or(*fs); Implies(a, b)
Always(f, lo=0.0, hi=None); Eventually(f, lo, hi); Until(a, b, lo, hi)     # lo/hi saat
to_rtamt(formula, dt_h=None) -> str          # pencereler örnek sayısına çevrilir
signals_of(formula) -> set[str]
robustness_builtin(formula, signals, dt_h=None) -> np.ndarray (T,)
robustness_rtamt(formula, signals, dt_h=None) -> np.ndarray   # ImportError yoksa
rtamt_available() -> bool; rtamt_version() -> str | None
robustness(formula, signals, dt_h=None, engine="auto") -> (rho, engine_used)

# İz
@dataclass Trace: kind ("2d"|"4d"|"telemetry"), t_h (S,), signals {ad: (S,) float}, index (S,), cells | None,
                  complete: bool, stranded: bool, extended_h: float | None, notes: dict
trace_from_states(states, planned_pixels, elevation, resolution_m, rover) -> Trace
trace_from_plan4d(path_states, path_battery_pct, path_dark_hours, path_earth_visible,
                  path_hours_until_earthset, path_haven_margin_h, slice_hours,
                  coarse_slope, coarse_elevation, coarse_thermal, resolution_m, rover) -> Trace
trace_from_samples(samples, rover, complete=True, stranded=False) -> Trace   # telemetri sözlükleri
continuous_shadow_hours(t_h, in_shadow) ; hours_below_reserve(t_h, soc_pct, floor, charging)
path_lateral_slopes(cells, elevation, resolution_m) ; path_step_slopes(cells, elevation, resolution_m)

# Katalog
@dataclass Requirement: id, name, cls, fretish, rationale, scope, signal, unit, rover_parameter,
                        threshold(rover) -> float | tuple | None, formula(threshold) -> Formula,
                        stl_text, ft_ltl, normalizer, trace_kinds
REQUIREMENTS: tuple[Requirement, ...]
bind_catalogue(rover, recharge_deadline_h=...) -> list[BoundRequirement]
evaluate_catalogue(trace, rover, engine="auto", recharge_deadline_h=...) -> dict   # safety_margins bloğu
rank_by_margin(items: list[tuple[label, block]]) -> list[dict]
fret_export() -> dict                     # docs/requirements/lunapath.fret.json içeriği

# Çevrimiçi (ROS) oturumu
class SafetyMonitorSession: __init__(rover, engine="auto"); push(sample) -> dict  # prefix izini değerlendirir,
                            # complete=False; liveness "pending"; newly_violated kenar-tetiklemeli
```

**İz → sinyal çevirisi:**

| Sinyal | 2-B (`RoverState`) | 4-B (`plan-4d` yanıtı) | telemetri (`samples`) |
|---|---|---|---|
| `t_h` | `elapsed_hours` | `slice × slice_hours` | `t_h` |
| `soc_pct` | `battery_low_pct` | `path_battery_pct` | `soc_pct` |
| `charging` | `recharged_this_step` ∨ `step_solar_wh > step_energy_wh` | batarya öncekinden yükseldi | `charging` ∨ SOC yükseldi |
| `shadow_continuous_h` | koşan sayaç (adım süresi × `shadow_ratio > 0,2`) | `path_dark_hours` | sayaç (`in_shadow` ya da `shadow_ratio`) |
| `hours_below_reserve_h` | nedensel sayaç | aynı | aynı |
| `inner_temp_c` | `surface_to_inner(surface_temp_c)` | `surface_to_inner(kaba ortalama termal)` | `inner_temp_c` ya da `surface_to_inner(surface_temp_c)` |
| `drive_slope_deg` | `max(slope_deg, segment_slope_deg)` | `max(kaba maks eğim[hücre], merkez yükseklik adım eğimi)` | `slope_deg` |
| `lateral_slope_deg` | gradyan + yön (planlayıcı formülü) | aynı, kaba merkez yükseklikte | `lateral_slope_deg` |
| `moving` | adım > 0 | hücre değişti | `moving` |
| `earth_link_h` | — | görünür → `hours_until_earthset` (None → +∞); değil → −(hamle süresi) | `earth_link_h` |
| `haven_margin_h` | — | `path_haven_margin_h` (None → +∞) | `haven_margin_h` |
| `dist_to_goal_m` | planlanan uzunluk − `distance_m` | aynı (kaba çözünürlük, köşegen √2) | `dist_to_goal_m` |
| `at_goal` | `dist_to_goal_m ≤ 0` | son durum | `at_goal` ya da `dist ≤ 0` |

**Mahsur kalan iz:** `stranded` ise iz `STRANDED_EXTENSION_H − son adım
süresi` kadar uzatılır (bir örnek: değerler tutulur, `charging = 0`, sayaçlar
ilerler; `extended_h` yanıtta). Gerekçe simülatörün kendi kararıdır: rover
bir Ay günü içinde şarj olamıyor — dolayısıyla R03'ün cevabı "hiç" ve R01'in
gölge sayacı büyümeye devam eder. Uydurma değil, `simulate_path`'in
`MAX_RECHARGE_HOURS` sınırı.

**Motor seçimi:** `auto` → `rtamt` içe aktarılabiliyorsa RTAMT, yoksa
`builtin`. RTAMT kullanıldığında **her istekte** yerleşik motor da koşar ve
`cross_check.max_abs_diff` raporlanır (11 formül, milisaniye). RTAMT'nin
ANTLR sürüm uyarısı (`4.9.3 != 4.7.2`, aşağıda) `parse()` sırasında stdout'a
yazılır; bastırılır.

**`safety_margins` bloğu:**

```json
{"monitor": {"engine": "rtamt", "rtamt_version": "0.3.5",
             "cross_check": {"engine": "builtin", "max_abs_diff": 0.0},
             "semantics": "discrete-time offline STL, space robustness; unbounded G/F over the finite trace",
             "trace": {"kind": "4d", "n_samples": 41, "duration_h": 7.36, "complete": true,
                       "stranded": false, "extended_h": null, "thermal_source": "static_layer"},
             "claim": "checked by runtime monitoring of the planned trace; not proven by model checking",
             "requirements_file": "docs/requirements/lunapath.fret.json"},
 "requirements": [
   {"id": "LP-R01", "name": "shadow_endurance", "class": "safety", "applicable": true, "reason": null,
    "rho": 88.64, "unit": "h", "rho_normalized": 0.923, "satisfied": true, "boundary": false, "open_ended": false,
    "threshold": 96.0, "rover_parameter": "h_max_shadow_h", "threshold_source": "rover",
    "signal": "shadow_continuous_h", "worst_at": {"index": 40, "hours": 7.36, "row": 51, "col": 106},
    "fretish": "The rover shall always satisfy shadow_continuous_h <= h_max_shadow_h",
    "stl": "always (shadow_continuous_h <= 96)"}, "..."],
 "min_margin": {"id": "LP-R02", "rho": 12.1, "unit": "pct", "rho_normalized": 0.605},
 "n_applicable": 9, "n_violated": 0, "violated": [], "verdict": "satisfied"}
```

`rho_normalized = ρ / ölçek` (ölçek: tek taraflı eşiklerde eşik, aralıklarda
yarı genişlik, R08/R09'da 24 h, R10'da rota uzunluğu) yalnızca **birimsiz
kıyas anahtarı**; ham ρ ve birim her zaman yanında. `min_margin`
uygulanabilir, sonlu ρ'lu, `safety` sınıfı gereksinimler üzerinden en küçük
`rho_normalized`. `verdict`: `violated` (uygulanabilir bir ρ < 0),
`satisfied`, `not_evaluated` (hiç uygulanabilir yok), `pending`
(çevrimiçi izde henüz karar yok).

### 2. API (`main.py`, yalnızca ekleme)

- **`POST /api/plan`**: `safety_margins` (2-B iz; `states` ve `astar_result["path_pixels"]` zaten var). Mevcut alanlar aynen.
- **`POST /api/plan-4d`**: `safety_margins` (4-B iz; `geometry` kaba eğim/yükseklik, `coarsen_grid(thermal, coarsen, "mean")`).
- **`POST /api/compare`** (ve `/api/plan-multi`): sonuç başına `safety_margins` (`_attach_constraint_check` içindeki `states` ile; simülasyon yoksa alan yok), `comparison`'a `safety_margin_ranking` (profil başına `{profile_id, verdict, n_violated, min_margin}`, en büyük min-marj önce, ihlalliler sonda) ve `largest_min_margin_profile`. Mevcut `comparison` anahtarları aynen.
- **`POST /api/safety-check`**: `{rover_id, samples: [{t_h, soc_pct?, surface_temp_c?|inner_temp_c?, shadow_ratio?|in_shadow?, slope_deg?, lateral_slope_deg?, moving?, charging?, earth_link_h?, haven_margin_h?, dist_to_goal_m?, at_goal?}, …], complete=true, stranded=false, engine="auto", recharge_deadline_h=6.0}` → aynı blok + `signals_present`, `ignored_keys`. 422: `t_h` artmayan / sonlu olmayan değer / boş liste / bilinmeyen `engine`; `engine="rtamt"` kurulu değilse 422 (sessizce düşmez).

### 3. ROS 2 — `lunapath_ros/lunapath_ros/safety_monitor_node.py`

`pose_monitor.py` kalıbı: yalnızca abonelik tesisatı, karar `app.safety_monitor.SafetyMonitorSession`'da.
Parametreler `rover_id`, `period_s` (10), `battery_topic` (`sensor_msgs/BatteryState` → `soc_pct = percentage×100`, `charging = POWER_SUPPLY_STATUS_CHARGING`), `temperature_topic` (`sensor_msgs/Temperature` → `inner_temp_c`), `shadow_topic` (`std_msgs/Float32` → `shadow_ratio`), `odom_topic` (`nav_msgs/Odometry` → `moving = |v| > 1 mm/s`). Zamanlayıcıda örnek → `push` → **yeni** ihlal olan her gereksinim için bir `ReplanTrigger` (`trigger_id = "safety:LP-R02"`, `detail = "soc_reserve: rho=-3.2 pct …"`, `recommended_action = "replan"`). `setup.py`'ye giriş noktası. Test `backend/test_safety_monitor_ros.py`: `pytest.importorskip("rclpy")`, düğüm sınıfı içe aktarılır ve örnek çevirisi denetlenir; oturum mantığı ROS'suz `test_safety_monitor.py`'de.

### 4. Gereksinim dosyası — `docs/requirements/lunapath.fret.json` + `README.md`

`fret_export()` çıktısı, FRET'in dışa aktarım alanlarına yakın: `project`,
`provenance` (**"written by hand in FRETISH; not exported from the FRET tool"**),
`requirements[]`: `reqid`, `fulltext` (FRETISH), `rationale`, `semantics`
(`scope`, `condition`, `component`, `timing`, `response`, `ftLTL`, `stl`,
`monitored_stl`), `monitor` (`signal`, `unit`, `rover_parameter`,
`threshold_source`, `thresholds_by_rover`, `trace_kinds`, `class`).
`scripts/export_fret_requirements.py` dosyayı yazar; bir test dosyanın
`fret_export()` ile birebir olduğunu doğrular (belge kodla sürüklenemez).
README: FRETISH grameri, iddia sınırı, tablo, yeniden üretme komutu.

### 5. `scripts/safety_monitor_report.py` → `docs/research/safety_monitor_report.md`

Gerçek gridde (çekirdek/ufuk yoksa açıklayıp 0 ile çıkar): (a) motor ve
çapraz kontrol; (b) B5/B3'ün iki `plan-4d` rotası (VIPER haven→haven
30 May 2027 `require_safe_haven`; LPR-1 28 Eyl 2026) gereksinim başına ρ
tablosu, en küçük marj, ihlal varsa nerede; (c) `/api/compare`'ın profilleri
(VIPER ve LPR-1, aynı start/goal) gereksinim başına ρ + `safety_margin_ranking`
+ `check_profile_constraints` ikili kararıyla yan yana; (d) B5 `/api/stress-test`
(1 000 koşum, seed 0) dağılımlarından ρ dağılımı: R02 = `min_battery_pct − S`
(p5/p50/p95), R01 = `H − max_continuous_shadow_h`, R10 tamamlanma oranı; (e)
`/api/safety-check` bir 2-B izle (yanıt süreleri). Sayılar yalnızca koşudan.

## Veri akışı

```
/api/plan     ─ simulate_path → RoverState[] ─┐
/api/compare  ─ _attach_constraint_check ─────┤─ trace_from_states ──┐
/api/plan-4d  ─ astar_4d result + kaba grid ──── trace_from_plan4d ──┤─ evaluate_catalogue(rover) ─► safety_margins
/api/safety-check ─ samples ───────────────────── trace_from_samples ─┤        │ builtin ρ  ⇄ RTAMT ρ (cross_check)
ROS: BatteryState/Temperature/Float32/Odometry ─ SafetyMonitorSession ┘        └ ReplanTrigger (yeni ihlal)
REQUIREMENTS ─ fret_export ─► docs/requirements/lunapath.fret.json (test: birebir)
```

## Test stratejisi

- `test_safety_monitor.py` (saf, sentetik, çekirdeksiz):
  - AST → RTAMT metni (`always[0,60] (x >= 20)` vb.; pencere saat → örnek).
  - Yerleşik motor: atom, ¬/∧/∨/→, sınırsız G/F, pencereli G/F (iz sonunda kırpma — RTAMT ölçümüyle aynı), U; elle hesaplanmış ρ.
  - RTAMT çapraz kontrol (`importorskip`): rastgele izlerde 6 formül ailesi, `max |Δρ| < 1e-9`; +∞ değerli sinyal.
  - Türetilmiş sinyaller: gölge sayacı düzensiz adımlarda (elle), rezerv-altı sayacı (şarjla sıfırlanma), yanal eğim planlayıcı formülüyle (eğik düzlemde yönle), adım eğimi.
  - `trace_from_states` (elle kurulan `RoverState` listesi; mahsur uzatma), `trace_from_plan4d` (sentetik sonuç sözlüğü), `trace_from_samples` (eksik sinyal → uygulanamaz).
  - Katalog: rover başına eşikler (VIPER 96 h / 20 pp / 20° / 15°; LUVMI-M `elec_op` → uygulanamaz; Yutu-2 %30); `evaluate_catalogue` bilinen ρ'lar: sağlama / ihlal / sınır / açık uçlu / kapsam boş; `worst_at`; `min_margin`, `rho_normalized`, `verdict`; JSON güvenliği (`inf`/`NaN` yok).
  - `rank_by_margin` sırası; `fret_export()` == depodaki JSON.
  - `SafetyMonitorSession`: kararlar monoton; liveness `pending`; `newly_violated` yalnızca ilk kez.
- `test_safety_monitor_api.py` (sentetik grid): `/api/plan` bloğu (motor alanı, R08/R09 uygulanamaz, mevcut anahtarlar aynen); `/api/plan-4d` bloğu (Dünya/haven sahteleriyle R08/R09 uygulanabilir ve `metrics.min_haven_margin_h` ile tutarlı); `/api/compare` sonuç blokları + sıralama + mevcut `comparison` anahtarları; `/api/safety-check` 200 / 422'ler / `engine="builtin"`.
- `test_safety_monitor_real_grid.py` (skip-guarded): VIPER rotası `safety_margins`: R01 ρ = H − max(`path_dark_hours`), R02 ρ = min(`path_battery_pct`) − 20, R09 ρ = `metrics.min_haven_margin_h`; `/api/plan` VIPER: R01 ρ = H − `summary.max_continuous_shadow_h` (aynı 0,2 eşiği); çapraz kontrol farkı 0; süre.
- `test_safety_monitor_ros.py`: `rclpy`/`lunapath_msgs` yoksa skip.

## Hata davranışı

- RTAMT yok → `builtin`, `rtamt_version: null`, `cross_check: null`; hiçbir uç 500 vermez.
- Sinyal yok (ör. 2-B'de Dünya) → gereksinim `applicable: false` + `reason`; `n_applicable` düşer.
- Kapsam boş (hedefe varılmadı) → R11 uygulanamaz; R10 ihlal (ρ = −kalan m).
- Açık uçlu marj → `rho: null, open_ended: true`.
- `inf`/`NaN` JSON'a sızmaz; aynı iz aynı ρ (deterministik).
- `_attach_constraint_check` simülasyonu düşerse `safety_margins` alanı yok (mevcut `simulation_summary: null` davranışı gibi).

## Kapsam dışı (bilinçli)

- FRET aracının kurulması / FRET'in kendi dışa aktarımı (elle FRETISH).
- Model checking / ispat; yalnızca somut iz denetimi.
- Yoğun-zaman (dense-time) STL; zaman-robustness (Donzé); çevrimiçi RTAMT (`rtamt4ros`) — ROS düğümü çevrimdışı motoru prefix üzerinde çağırır.
- API'den özel formül kabulü (`/api/safety-check` yalnızca kataloğu değerlendirir).
- Ayrı batarya termal modeli (R05 aynı iç sıcaklık modelini kullanır).
- Planlayıcının robustness'ı maliyete katması (B2/B1 konusu).
- `/api/stress-test` yanıtına ρ dağılımı (raporda aritmetikle; sapma olarak not).

## Uygulama sırasında bulunanlar ve ölçümler (4 Eylül 2026)

**RTAMT kurulumu ve ANTLR.** `pip install rtamt` (0.3.5)
`antlr4-python3-runtime`'ı 4.7'ye düşürdü ve ortamdaki omegaconf/hydra-core
(4.9.* ister) ile çakıştı. 4.9.3 çalışma zamanına geri dönüldü: RTAMT'nin
üretilmiş ayrıştırıcısı "ANTLR runtime and generated code versions disagree:
4.9.3!=4.7.2" uyarısıyla **doğru** çalışıyor (sonda ve çapraz-kontrol
testleri). Uyarı `parse()` sırasında stdout'a yazıldığından
`robustness_rtamt` stdout/stderr'i bastırıyor. `requirements.txt` rtamt'ı
pinliyor (temiz kurulumda 4.7 gelir; yorumda ikisi de yazılı).

**RTAMT sonlu-iz semantiği (ölçüldü ve testlere sabitlendi).** Veri kümesi
`{'time': [0,1,…], 'x': […]}` biçiminde olmalı (liste verilince `TypeError`);
`always[a,b]`/`eventually[a,b]` pencereyi mevcut örneklere kırpar, **boş
pencere** `always` için `+inf`, `eventually` için `-inf`; `until[a,b]`'de sol
taraf `[i, j)` üzerinden; sınırsız `always`/`eventually` sonek min/max;
`not a or b and c` = `(not a) or (b and c)`. Ayrık-zaman offline yorumlayıcı
**tek örnekli** izde `UnboundLocalError: duration` veriyor → tek örnekli
kapsamda (LP-R11'in `at_goal` maskesi) gereksinim yerleşik motorla
değerlendirilir ve girdide `engine: "builtin"` söylenir (`monitor.engine`
istek düzeyinde kalır).

**Planlayıcının `path_haven_margin_h: None`'ı iki anlamlı.** A1
`_finite_or_none(deadline − tts)` yazar: Dünya ön-bakışta batmıyorsa
`+∞ → None`, sonlu batışa karşı ulaşılabilir haven yoksa `−∞ → None`. İlk
rapor koşusu LPR-1'in 28 Eyl 2026 rotasında LP-R09'u "açık uçlu, sağlandı"
saymıştı; oysa bağlantı 184,6 h sonra bitiyor ve o Ay gününde haven yok (B5
bulgusu). `trace_from_plan4d` artık `path_time_to_haven_h` ile ayrıştırıyor:
batış `None` → +∞, batış sonlu ve `tts None` → −∞ → `satisfied: false, rho:
null, reason: "unbounded violation"`; `haven_unreachable_states` iz
notunda. Skip-korumalı gerçek-grid testi bunu LPR-1 rotasında doğruluyor.

**Termal zarf gereksinimleri her rotada ihlal.** LP-R04/LP-R05 iç sıcaklığı
statik `sunlit_peak` termal katmanı (gölgeye bağlı) + `surface_to_inner`
ofseti (LPR-1/VIPER soğuk dalda +60 K, sıcak dalda −40 K): VIPER 4-B
rotasında en soğuk durum #16 (hücre (73,118), yüzey −88 °C) → iç −28 °C,
batarya zarfı 0…35 °C'nin **27,96 °C** dışında, elektronik zarfı −20…50'nin
7,96 °C dışında; 2-B profillerde −46 °C. Katmanın p50'si −55 °C (iç +4,5
°C) ama p5'i −183 °C ve p95'i +11 °C (sıcak dal −40 → iç −29 °C: ofset
modeli monoton değil). Ne planlayıcı ne `check_profile_constraints` termali
denetliyordu; ısıtıcı gücü (`p_heater_w`, gölge idaresi) enerji modelinde
sayılıyor ama sıcaklık modelinde ısıtma yok. Bu D3'ün amaçlanan çıktısı:
gereksinim ile model arasındaki tutarsızlığı sayıyla göstermek. Gereksinim
yumuşatılmadı; C6 (termal operasyon zarfı) için açık madde olarak
raporlandı.

**Boole kapsam ve ±inf.** Kapsamı `G(scope → φ)` olarak RTAMT'ye vermek
Boole göstergenin ±0,5 robustness'ıyla ihlal büyüklüğünü kırpacaktı;
alt-iz maskesi tasarımdaki gibi uygulandı ve iki motor aynı ρ'yu veriyor.
`inf − inf` çapraz kontrolde `nan` uyarısı veriyordu → aynı işaretli
sonsuzlar eşit sayılır.

**Ölçümler (Site11, 4 Eylül 2026; `scripts/safety_monitor_report.py` →
[safety_monitor_report.md](../../research/safety_monitor_report.md)):**

| Ölçüm | Değer |
|---|---|
| Motor | RTAMT 0.3.5 (ANTLR 4.9.3) + yerleşik; her gerçek rotada `cross_check.max_abs_diff = 0`; rastgele 20 izde 6 formül ailesi (pencereli G/F, →, U, iç içe) `< 1e-9` |
| VIPER haven→haven 30 May 2027 (41 durum, 7,36 h) | LP-R01 91,45 h; LP-R02 12,06 pp; LP-R03 6,00 h; **LP-R04 −7,96 °C; LP-R05 −27,96 °C** (#16, (73,118), 2,77 h); LP-R06 0,48°; LP-R07 1,19°; LP-R08 199,93 h; LP-R09 199,80 h (= `metrics.min_haven_margin_h`); LP-R10 0 m (sınır); LP-R11 12,06 pp — karar `violated` (2) |
| LPR-1 28 Eyl 2026 (41 durum, 2,16 h) | LP-R01 49,79 h; LP-R02 76,16 pp; LP-R04 −17,96 °C; LP-R05 −27,96 °C; LP-R06 5,63°; LP-R07 4,19°; LP-R08 184,62 h; **LP-R09 sınırsız ihlal** (haven yok); LP-R11 76,26 pp — karar `violated` (3) |
| SHERPA (1.000 koşum, tohum 0) → ρ dağılımı | VIPER LP-R02 plan 12,1 pp, koşumlar p5/p50/p95 **−20,0 / −20,0 / −4,9 pp** (rezerv ihlali %98,6, tamamlanma %29,6); LP-R01 89,2 / 90,7 / 92,4 h. LPR-1 LP-R02 32,3 / 58,0 / 72,5 pp; LP-R01 48,4 / 49,7 / 49,8 h; tamamlanma %100 |
| `/api/compare` VIPER, 4 profil (0,8–1,0 s) | LP-R01 91,67 h, LP-R02 47,15 pp (shadow_traverse 46,93), LP-R06 2,58°, LP-R07 0,66°, LP-R05 −46,04 °C; `constraint_check` dört profilde de `max_shadow_h` (30–50 h) ve `min_soc` "sağlandı" — termali hiç sormuyordu |
| `/api/compare` LPR-1 | LP-R01 48,70 h, LP-R02 75,6 pp, LP-R06 7,58–7,83°, LP-R07 1,12–2,30°, LP-R05 −46,04 °C |
| `/api/safety-check` (500 örnek, 11 gereksinim) | yerleşik 12–15 ms, RTAMT 28–48 ms |
| Plan içindeki maliyet | milisaniye (plan-4d 10–12 s, compare 0,8–1,0 s toplam) |
| Testler | 57 birim (`test_safety_monitor.py`), 17 API, 4 skip-korumalı gerçek grid, 3 ROS (rclpy yoksa atlanır) |

**Sapmalar (tasarımdan):**
- `trace_from_plan4d` `path_time_to_haven_h` parametresi aldı (yukarıdaki iki anlamlılık); `Trace.notes.haven_unreachable_states`.
- Gereksinim girdisinde `engine` alanı (tek örnekli kapsam → `builtin`).
- `_safety_margins_2d/4d` istisnayı yakalar: monitör hatası planı düşürmez, blok yok ve hata günlüğe (tasarımdaki "500 yok" ilkesi).
- `fret_export()`'a `formula_by_rover` ve `monitored_stl` (lpr_1'in somut formülü) eklendi; `semantics.variables` listesi.
- `SafetyMonitorSession.push` örneği önce doğrular (geri giden zaman oturumu bozmaz); `finish(stranded=)`.
- ROS düğümü `sensor_msgs/Temperature`'ı **iç** sıcaklık sayar (yüzey değil); `BatteryState.percentage` NaN ise SOC yok.
- `/api/stress-test` yanıtı değişmedi; ρ dağılımı raporda B5 dağılımlarından aritmetikle.
- RTAMT ortamda ANTLR 4.9.3 ile; `requirements.txt` rtamt'ın kendi 4.7 pinini taşır.
