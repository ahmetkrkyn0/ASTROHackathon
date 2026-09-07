# C6 — VIPER termal operasyon zarfı ve tolere edilebilir saplanma süresi — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Rover iç sıcaklığının birinci dereceden dinamiğiyle her (dilim, blok) için
`max_dwell_h` küpü; `astar_4d`'ye "hiçbir hücrede dwell'den uzun bekleme" kısıtı
(`require_thermal_dwell`, verilmezse bit-eşit); rota iç sıcaklık izi (D3'ün dinamikle yeniden
ele alınışı); LP-R12; `/api/replan` saplanma geri sayımı (termal + haven, warning/critical/fail);
`GET /api/thermal-dwell`, `GET /api/thermal-envelope` (heat1d transient'inden JSC zarfının bizim
karşılığı); rapor.

**Architecture:** Yeni `app/thermal_dwell.py` (zarf, hedef, kapalı formlu çıkış süresi, vektörize
dwell küpü, ısıtıcı modeli, rota izi, hücre dwell'i, saplanma bloğu, heat1d zarf örnekleyici ve
kutulama, önbellek); `cost_cube.surface_temperature_series` dışa çıkarılır (küp bit-eşit);
`illumination_series.cell_shadow_series`; `pathfinder_4d.py` beşinci etiket ekseni `stay_h` +
`thermal_dwell` reddi (yalnızca ekleme); `safety_monitor.py` LP-R12; `replan_triggers.py`
`entrenchment`; `main.py` istek/yanıt alanları, iki yeni uç; `scripts/build_thermal_envelope_cache.py`,
`scripts/thermal_dwell_report.py`.

**Spec:** [2026-09-05-c6-thermal-dwell-design.md](../specs/2026-09-05-c6-thermal-dwell-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, FastAPI/pydantic, pytest, heat1d GitHub main
(slope/slope_az, crank-nicolson; yalnız önbellek betiğinde), spiceypy (yalnız gerçek grid).

**Commit kuralı:** özellik bitince **tek commit**; ara commit yok; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Sayı uydurma yok: her dwell, zarf kutusu, rota etkisi ve saplanma örneği Site11'de koşturulup
  okunur; JSC'nin sayıları `JSC_QUOTED`'da alıntı olarak durur.
- Termal model `MODEL`, regolit gevşemesi `UNCALIBRATED`; her blokta `validity` ve
  `thermal_lag_validity`. Isıtıcı-sıcaklık bağı yalnız `heater_model="thermostat_assumed"` ile ve
  `"assumption:"` kaynağıyla; varsayılan `"none"`. Kataloğa alan eklenmez.
- `require_thermal_dwell=False` ve `max_dwell_cube` verilmemişken `astar_4d` **bit-eşit**; küp
  verilmiş-kısıt kapalıyken **aynı yol, aynı düğüm sayısı**; standart 4-B rotalar 41 / 116 / 8 hamle,
  2-B SHA kilitleri değişmez. `build_cost_cube(surface_series=…)` bit-eşit.
- `thermal_tau_s` olmayan rover'da dwell "unavailable"; regolit tau'su rover'a uydurulmaz.
- D3'ün `safety_margins` LP-R04/R05 değerleri değişmez; LP-R12 yeni satır (2-B izde
  `applicable: false`).
- Frontend'e dokunulmaz; sözleşme belgesine yalnız "C6 eki" (B1 ekinin ardına, "Değişmeyenler"
  öncesine). Mevcut alanlar aynen.
- Gerçek grid / çekirdek / heat1d gerektiren testler skip-korumalı; yeni dosyalarda ruff temiz;
  rapor betiği `sys.stdout` UTF-8, JSON önce; JSON commit'lenmez; raporda mutlak yol yok.
- Planlayıcıyı tracemalloc altında zamanlama; ağır koşumlar eşzamanlı değil.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/constants.py` | `HEATER_THERMOSTAT_ASSUMPTION_SOURCE` |
| `backend/app/terrain.py` | `LAYER_UNITS`/`LAYER_DESCRIPTIONS`: `max_dwell_h`, `dwell_side` (manifeste girmez) |
| `.gitignore` | `thermal_envelope_meta.json` satırı |
| `backend/app/thermal_dwell.py` (yeni) | sabitler/iddia/alıntı, `rover_envelope`, `nominal_inner_c`, `inner_target_c`, `apply_heater`, `exit_time_h`, `DwellCube`, `build_dwell_cube`, `dwell_unavailable_reason`, `route_dwell_report`, `route_inner_trace`, `cell_dwell`, `thermal_dwell_block`, `entrenchment_block`, `heat1d_envelope_samples`, `bin_envelope`, `envelope_matrix`, önbellek yardımcıları |
| `backend/app/cost_cube.py` | `surface_temperature_series`; `build_cost_cube(surface_series=None)` |
| `backend/app/illumination_series.py` | `cell_shadow_series` |
| `backend/app/pathfinder_4d.py` | `stay` ekseni, `thermal_dwell` reddi, metrikler, gerekçe |
| `backend/app/safety_monitor.py` | LP-R12, `dwell_margin_h` sinyali/örneği, `trace_from_plan4d(path_dwell_margin_h)` |
| `backend/app/replan_triggers.py` | `check_entrenchment`, seviyeler, `_TRIGGER_INPUTS` |
| `backend/app/main.py` | `Plan4DRequest` alanları, plan-4d bloğu, cell-telemetry, replan, `GET /api/thermal-dwell`, `GET /api/thermal-envelope` |
| `backend/test_thermal_dwell.py` (yeni) | birim + planlayıcı + katalog + tetikleyici |
| `backend/test_thermal_dwell_api.py` (yeni) | uçlar (çekirdeksiz) |
| `backend/test_thermal_dwell_real_grid.py` (yeni) | skip-korumalı gerçek grid |
| `backend/test_safety_monitor.py` | `range(1, 13)` |
| `docs/requirements/lunapath.fret.json`, `docs/requirements/README.md` | LP-R12 |
| `scripts/build_thermal_envelope_cache.py` (yeni) | heat1d zarf önbelleği |
| `scripts/thermal_dwell_report.py` (yeni) | koşum + JSON + markdown |
| `docs/research/thermal_dwell_report.md` | rapor |
| `docs/frontend/3b-veri-sozlesmesi.md` | C6 eki |
| `README.md`, `docs/research/12_faktor…md`, spec | satır, ✅ + Yapıldı, ölçümler |

---

### Task 0: Sabitler, katman etiketleri, gitignore

**Files:** Modify `backend/app/constants.py` (B1 arıza modeli bölümünün altı); Modify `backend/app/terrain.py`
(`LAYER_UNITS`, `LAYER_DESCRIPTIONS`); Modify `.gitignore`; Test `backend/test_thermal_dwell.py`.

**Produces:** `constants.HEATER_THERMOSTAT_ASSUMPTION_SOURCE: str` (`"assumption: "` ile başlar);
`terrain.LAYER_UNITS["max_dwell_h"] == "h"`, `LAYER_UNITS["dwell_side"] == "code"`; `"max_dwell_h" not in TERRAIN_LAYERS`.

- [x] **Adım 1: başarısız test**

```python
def test_heater_thermostat_is_a_labelled_assumption_and_no_profile_field():
    from app import constants as C
    assert C.HEATER_THERMOSTAT_ASSUMPTION_SOURCE.startswith("assumption:")
    for rover in C.ROVERS.values():
        assert "heater_k_per_w" not in rover and "thermostat" not in rover

def test_dwell_layers_are_described_but_not_in_the_manifest():
    from app.terrain import LAYER_DESCRIPTIONS, LAYER_UNITS, TERRAIN_LAYERS
    assert LAYER_UNITS["max_dwell_h"] == "h" and LAYER_UNITS["dwell_side"] == "code"
    assert "max_dwell_h" in LAYER_DESCRIPTIONS and "max_dwell_h" not in TERRAIN_LAYERS
```

- [x] **Adım 2: kırmızı** (`cd backend && python -m pytest test_thermal_dwell.py -q -p no:cacheprovider`)
- [x] **Adım 3: uygulama** — sabit + iki katman satırı + `.gitignore`'a
  `lunapath/data/processed/thermal_envelope_meta.json`.
- [x] **Adım 4: yeşil**

### Task 1: `thermal_dwell.py` — zarf, hedef, ısıtıcı, kapalı formlu çıkış süresi

**Files:** Create `backend/app/thermal_dwell.py`; Test `backend/test_thermal_dwell.py`.

**Produces:**
- `THERMAL_DWELL_MODEL_ID = "inner_temperature_first_order_lag_v1"`, `THERMAL_DWELL_VALIDITY = "MODEL"`,
  `HEATER_MODELS`, `SIDE_NONE/COLD/HOT`, `COMPONENT_NONE/BATTERY/ELECTRONICS`, `THERMAL_DWELL_SCOPE/CLAIM/REFERENCES`, `JSC_QUOTED`.
- `Envelope(lo, hi, lo_component, hi_component)`; `rover_envelope(rover) -> Envelope | None`; `nominal_inner_c(rover) -> float | None`
- `inner_target_c(surface_c, rover) -> np.ndarray` (float64, `surface_to_inner` vektörize)
- `apply_heater(target, envelope, heater_model) -> np.ndarray`
- `exit_time_h(inner_c, target_c, envelope, tau_s) -> tuple[np.ndarray, np.ndarray, np.ndarray]` (saat/inf, side int8, component int8)
- `dwell_unavailable_reason(rover) -> str | None`

- [x] **Adım 1: testler**

```python
import math, numpy as np, pytest
from app.constants import get_rover
from app.cost_engine import surface_to_inner
from app import thermal_dwell as TD

def test_inner_target_matches_the_scalar_offset_model_for_every_rover():
    surfaces = np.linspace(-200.0, 100.0, 10_001)
    for rid in ("lpr_1", "nasa_viper", "luvmi_m", "cnsa_yutu_2"):
        rover = get_rover(rid)
        expected = np.array([surface_to_inner(float(s), rover) for s in surfaces])
        np.testing.assert_allclose(TD.inner_target_c(surfaces, rover), expected, rtol=0, atol=1e-12)

def test_rover_envelope_is_the_tightest_declared_intersection():
    env = TD.rover_envelope(get_rover("lpr_1"))          # bat [0,35], elec [-10,40]
    assert (env.lo, env.hi) == (0.0, 35.0) and env.lo_component == "battery" and env.hi_component == "battery"
    env = TD.rover_envelope(get_rover("cnsa_yutu_2"))    # bat [-10,30], elec [-40,55]
    assert (env.lo, env.hi) == (-10.0, 30.0)
    env = TD.rover_envelope(get_rover("luvmi_m"))        # bat [-100,0], elec none
    assert (env.lo, env.hi) == (-100.0, 0.0) and env.hi_component == "battery"
    assert TD.nominal_inner_c(get_rover("lpr_1")) == 17.5

def test_exit_time_closed_form_three_cases_and_sides():
    env = TD.Envelope(0.0, 35.0, "battery", "battery"); tau = 7200.0
    hours, side, comp = TD.exit_time_h(np.array([17.5, 17.5, 17.5, 50.0]), np.array([-123.15, 10.0, 60.0, 10.0]), env, tau)
    assert hours[0] == pytest.approx(7200 * math.log((17.5 + 123.15) / 123.15) / 3600)   # cold side
    assert math.isinf(hours[1]) and side[1] == TD.SIDE_NONE                             # target inside -> unlimited
    assert hours[2] == pytest.approx(7200 * math.log((60 - 17.5) / (60 - 35)) / 3600) and side[2] == TD.SIDE_HOT
    assert hours[3] == 0.0 and side[3] == TD.SIDE_HOT                                     # already outside
    assert side[0] == TD.SIDE_COLD and comp[0] == TD.COMPONENT_BATTERY

def test_warmer_cold_target_means_longer_cold_dwell():
    env = TD.rover_envelope(get_rover("lpr_1")); tau = 7200.0
    targets = np.array([-120.0, -80.0, -40.0, -10.0])
    hours, *_ = TD.exit_time_h(np.full(4, 17.5), targets, env, tau)
    assert np.all(np.diff(hours) > 0)

def test_thermostat_heater_holds_the_cold_bound_and_leaves_the_hot_side():
    env = TD.rover_envelope(get_rover("lpr_1"))
    held = TD.apply_heater(np.array([-120.0, 10.0, 60.0]), env, "thermostat_assumed")
    np.testing.assert_allclose(held, [0.0, 10.0, 60.0])
    np.testing.assert_allclose(TD.apply_heater(np.array([-120.0]), env, "none"), [-120.0])
    with pytest.raises(ValueError):
        TD.apply_heater(np.array([0.0]), env, "magic")

def test_rover_without_tau_is_unavailable_with_a_reason():
    assert "thermal_tau_s" in TD.dwell_unavailable_reason(get_rover("luvmi_m"))
    assert TD.dwell_unavailable_reason(get_rover("lpr_1")) is None
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama** (modül başlığı + iddia sabitleri + bu fonksiyonlar; `exit_time_h`:
  `inside = (T >= lo) & (T <= hi)`; `out_cold = g < lo`, `out_hot = g > hi`; sonuç dizisi `inf`;
  `~inside → 0`, side işaretle; `inside & out_cold → tau·ln((T−g)/(lo−g))/3600`, side COLD, comp =
  `env.lo_component`; `inside & out_hot → tau·ln((g−T)/(g−hi))/3600`, side HOT.)
- [x] **Adım 4: yeşil**

### Task 2: `cost_cube.surface_temperature_series` ve `build_cost_cube(surface_series=…)` — bit-eşit

**Files:** Modify `backend/app/cost_cube.py` (`build_cost_cube` gövdesi: sunlit/surface_state/relax
döngüsü); Test `backend/test_thermal_dwell.py`.

**Produces:** `surface_temperature_series(base_grids, shadow_ratio_series, coarsen=1, slice_hours=1.0,
tau_s=REGOLITH_THERMAL_TAU_S, couple_thermal=True) -> np.ndarray (T, H', W') float64`;
`build_cost_cube(..., surface_series: np.ndarray | None = None)`.

- [x] **Adım 1: testler**

```python
def _toy_grids():
    rng = np.random.default_rng(7); shape = (16, 16)
    return {
        "elevation": rng.random(shape) * 30.0, "slope": rng.random(shape) * 12.0,
        "thermal": rng.random(shape) * 80.0 - 90.0, "shadow_ratio": rng.random(shape),
        "traversable": np.ones(shape, dtype=bool),
        "metadata": {"resolution_m": 80.0, "shape": list(shape), "thermal_shadow_coupled": True,
                     "cost_weights": {"w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.19}},
    }

def test_surface_series_is_what_the_cube_integrates_bit_for_bit():
    from app.cost_cube import build_cost_cube, surface_temperature_series
    grids = _toy_grids(); rover = get_rover("lpr_1")
    rng = np.random.default_rng(1); series = [rng.random((16, 16)) for _ in range(6)]
    surface = surface_temperature_series(grids, series, coarsen=4, slice_hours=0.5)
    assert surface.shape == (6, 4, 4)
    cube_a = build_cost_cube(grids, series, rover, coarsen=4, slice_hours=0.5)
    cube_b = build_cost_cube(grids, series, rover, coarsen=4, slice_hours=0.5, surface_series=surface)
    np.testing.assert_array_equal(cube_a, cube_b)
    # first slice: one relax step from the long-run equilibrium toward slice 0's equilibrium
    from app.thermal_model import relax_surface_c, shadowed_equilibrium_c, REGOLITH_THERMAL_TAU_S
    from app.cost_cube import coarsen_grid
    sunlit = coarsen_grid(grids["thermal"], 4); base = coarsen_grid(grids["shadow_ratio"], 4)
    state = shadowed_equilibrium_c(sunlit, base)
    expected0 = relax_surface_c(state, shadowed_equilibrium_c(sunlit, coarsen_grid(series[0], 4)), 1800.0, REGOLITH_THERMAL_TAU_S)
    np.testing.assert_array_equal(surface[0], expected0)
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama** — döngüdeki termal kısmı fonksiyona taşı; `build_cost_cube` `surface_series`
  None ise çağırır, verilmişse şekil denetler `(T, H', W')` ve `thermal_slice = surface_series[index]`;
  `couple_thermal=False` iken `thermal_c` tekrarı.
- [x] **Adım 4: yeşil**; ayrıca `python -m pytest test_cost_cube.py test_plan_4d_endpoint.py -q -p no:cacheprovider` yeşil.

### Task 3: `build_dwell_cube`, `DwellCube`, `route_dwell_report`, `route_inner_trace`

**Files:** Modify `backend/app/thermal_dwell.py`; Test `backend/test_thermal_dwell.py`.

**Produces:**
```
@dataclass DwellCube: max_dwell_h (T,H,W) f32; side (T,H,W) i8; component (T,H,W) i8; lookahead_h (T,) f64;
    slice_hours; slices_per_bin; initial_inner_c; heater_model; tau_s; envelope; compute_ms; n_states
    def at(self, t, r, c) -> tuple[float, int, int]      # kutu floor(t/m)
    def summary(self, t=0) -> dict                       # sınırsız/soğuk/sıcak kesirleri, sonlu medyan/p5/p95
build_dwell_cube(surface_series, slice_hours, rover, traversable, initial_inner_c=None, heater_model="none",
                 max_states=DWELL_MAX_STATES) -> DwellCube | None
route_dwell_report(path_states, slice_hours, cube) -> dict   # path_stay_hours, path_max_dwell_h, path_dwell_margin_h, min_dwell_margin_h, states_past_thermal_dwell, max_stay_h
route_inner_trace(path_states, surface_series, slice_hours, rover, initial_inner_c=None, heater_model="none") -> dict
    # path_inner_c, min_c, max_c, states_outside, first_exit_h, side, component, envelope
```

- [x] **Adım 1: testler**

```python
def _constant_series(value, n=8, shape=(3, 3)):
    return np.full((n,) + shape, float(value))

def test_dwell_cube_with_a_constant_target_equals_the_closed_form():
    rover = get_rover("lpr_1"); env = TD.rover_envelope(rover)
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=400), 0.05, rover, np.ones((3, 3), bool))
    expected, *_ = TD.exit_time_h(np.array([17.5]), np.array([-40.0]), env, 7200.0)   # -100 surface -> -40 inner
    assert cube.max_dwell_h[0, 1, 1] == pytest.approx(expected[0], rel=1e-5)
    assert cube.side[0, 1, 1] == TD.SIDE_COLD and cube.component[0, 1, 1] == TD.COMPONENT_BATTERY
    assert np.isinf(cube.max_dwell_h[399, 1, 1]) or cube.max_dwell_h[399, 1, 1] <= cube.lookahead_h[399]

def test_dwell_cube_lit_then_dark_is_the_hand_solved_two_piece_answer():
    rover = get_rover("lpr_1"); env = TD.rover_envelope(rover); tau = 7200.0
    series = np.concatenate([_constant_series(-40.0, n=4), _constant_series(-140.0, n=200)])  # inner 20 then -80
    cube = TD.build_dwell_cube(series, 0.25, rover, np.ones((3, 3), bool))
    T_after_lit = 20.0 + (17.5 - 20.0) * math.exp(-4 * 0.25 * 3600 / tau)
    t_cold = tau * math.log((T_after_lit + 80.0) / 80.0) / 3600
    assert cube.max_dwell_h[0, 0, 0] == pytest.approx(1.0 + t_cold, rel=1e-6)
    assert cube.max_dwell_h[4, 0, 0] == pytest.approx(tau * math.log((17.5 + 80.0) / 80.0) / 3600, rel=1e-6)

def test_dwell_cube_open_ended_where_the_target_stays_inside():
    cube = TD.build_dwell_cube(_constant_series(-40.0, n=10), 0.5, get_rover("lpr_1"), np.ones((3, 3), bool))
    assert np.all(np.isinf(cube.max_dwell_h[:, 1, 1])) and cube.lookahead_h[0] == pytest.approx(5.0)
    assert np.isnan(TD.build_dwell_cube(_constant_series(-40.0), 0.5, get_rover("lpr_1"), np.zeros((3, 3), bool)).max_dwell_h).all()

def test_thermostat_makes_the_cold_side_open_ended_only():
    cube = TD.build_dwell_cube(_constant_series(-140.0, n=10), 0.5, get_rover("lpr_1"), np.ones((3, 3), bool), heater_model="thermostat_assumed")
    assert np.all(np.isinf(cube.max_dwell_h))
    hot = TD.build_dwell_cube(_constant_series(-10.0, n=10), 0.5, get_rover("lpr_1"), np.ones((3, 3), bool), heater_model="thermostat_assumed")
    assert np.all(np.isfinite(hot.max_dwell_h[0])) and hot.side[0, 0, 0] == TD.SIDE_HOT     # -10 surface -> +50 inner

def test_dwell_cube_is_none_without_tau_and_bins_start_slices_over_budget():
    assert TD.build_dwell_cube(_constant_series(-100.0), 0.5, get_rover("luvmi_m"), np.ones((3, 3), bool)) is None
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=40), 0.1, get_rover("lpr_1"), np.ones((3, 3), bool), max_states=100)
    assert cube.slices_per_bin == 4 and cube.max_dwell_h.shape[0] == 10 and cube.at(7, 0, 0)[0] == cube.max_dwell_h[1, 0, 0]

def test_route_dwell_report_counts_consecutive_stays_against_the_arrival_budget():
    rover = get_rover("lpr_1")
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=12), 0.25, rover, np.ones((3, 3), bool))
    states = [(0, 0, 0), (0, 0, 1), (0, 0, 2), (0, 1, 3), (0, 1, 4)]     # two waits, a move, one wait
    rep = TD.route_dwell_report(states, 0.25, cube)
    assert rep["path_stay_hours"] == [0.0, 0.25, 0.5, 0.0, 0.25]
    assert rep["path_max_dwell_h"][2] == pytest.approx(float(cube.max_dwell_h[0, 0, 0]))
    assert rep["path_dwell_margin_h"][2] == pytest.approx(float(cube.max_dwell_h[0, 0, 0]) - 0.5)
    assert rep["max_stay_h"] == 0.5 and rep["min_dwell_margin_h"] == pytest.approx(min(rep["path_dwell_margin_h"]))

def test_route_inner_trace_follows_the_arrival_cell_and_reports_the_first_exit():
    rover = get_rover("lpr_1"); tau = 7200.0
    series = _constant_series(-140.0, n=10)          # inner target -80 everywhere
    states = [(0, 0, 0), (0, 1, 2), (0, 2, 4)]
    trace = TD.route_inner_trace(states, series, 0.5, rover)
    T1 = -80.0 + (17.5 + 80.0) * math.exp(-2 * 0.5 * 3600 / tau)
    assert trace["path_inner_c"][0] == 17.5 and trace["path_inner_c"][1] == pytest.approx(T1)
    assert trace["states_outside"] == 2 and trace["side"] == "cold" and trace["component"] == "battery"
    assert trace["first_exit_h"] == pytest.approx(tau * math.log(97.5 / 80.0) / 3600)
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama** — `build_dwell_cube`: `g = apply_heater(inner_target_c(surface), env, heater)`
  `(T, HW)`; `m = ceil(T·HW/max_states)`; `starts = range(0, T, m)`; `F` ileri geçiş (`F[0]=g[0]·(1−d)`,
  `F[t] = g[t] + (F[t−1] − g[t])·d`, `d = e^{−Δ/τ}` — dikkat: `T(t; t0) = g_t + (T(t0+k−1)−g_t)·d`
  yinelemesi doğrusal olduğundan `T_k = F_k + d^k·(T0 − F_{t0})` yerine doğrudan 2-B dizi
  `state[t0]` = T0 başlangıçlı yineleme kullan, daha az kayan-nokta farkı: her adım `k`: aktif
  satırlar `t0 + k < T`; `g_k = g[t0+k]`; `hours, side, comp = exit_time_h(state, g_k, env, tau)`;
  `hit = hours < Δ` → `dwell = kΔ + hours`, kaydet, pasifleştir; `state = g_k + (state − g_k)·d`
  (kalanlar); döngü aktif kalmayınca biter; kalanlar `inf`, `side/comp` 0). Geçilmez blok NaN.
  `lookahead_h[t0] = (T − t0)·Δ`. `route_dwell_report`: ardışık aynı hücre → `stay += Δ`, aksi 0;
  bütçe `cube.at(t_arr, r, c)`; `∞ → None`. `route_inner_trace`: durum başına hedef varılan
  hücrenin `surface[t_i]`… hedefi `t_{i−1}..t_i` dilimlerinde varılan hücrenin yüzey serisi ile
  dilim dilim gevşet (`relax_surface_c` skaler); zarf dışı ilk an: dilim içinde kapalı form.
- [x] **Adım 4: yeşil**

### Task 4: `pathfinder_4d.astar_4d(max_dwell_cube, require_thermal_dwell)` — yalnızca ekleme

**Files:** Modify `backend/app/pathfinder_4d.py` (`REJECTION_KEYS`, `_dominated`, `_insert_label`, `_empty`,
`astar_4d` imzası/docstring, `label_of`, `push`, WAIT dalı, MOVE `push`, dönüş sözlüğü, `no_path_reason_4d`);
Test `backend/test_thermal_dwell.py`.

**Produces:** `astar_4d(..., max_dwell_cube: Any | None = None, require_thermal_dwell: bool = False)`;
`REJECTION_KEYS` sonuna `"thermal_dwell"`; dönüşte `path_stay_hours`, `path_max_dwell_h`,
`path_dwell_margin_h` (küp yokken None) ve `metrics.min_dwell_margin_h`, `states_past_thermal_dwell`,
`max_stay_h`, `thermal_dwell_enforced`.

- [x] **Adım 1: testler**

```python
def _open_field(n=8, slices=40):
    cost = np.full((slices, n, n), 0.3); wait = np.full((slices, n, n), 0.01)
    return cost, wait, np.ones((n, n), bool)

def test_planner_without_a_cube_and_with_an_unenforced_cube_expand_the_same_nodes():
    from app.pathfinder_4d import astar_4d
    rover = get_rover("lpr_1"); cost, wait, trav = _open_field()
    shadow = np.zeros_like(cost); shadow[:, 4:, :] = 1.0
    base = astar_4d(cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, rover, shadow_cube=shadow)
    cube = TD.build_dwell_cube(np.full(cost.shape, -140.0), 0.25, rover, trav)
    reported = astar_4d(cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, rover, shadow_cube=shadow, max_dwell_cube=cube)
    assert reported["path_states"] == base["path_states"]
    assert reported["metrics"]["nodes_expanded"] == base["metrics"]["nodes_expanded"]
    assert base["path_dwell_margin_h"] is None and reported["path_dwell_margin_h"] is not None
    assert base["metrics"]["thermal_dwell_enforced"] is False and reported["metrics"]["edges_rejected"]["thermal_dwell"] == 0

def test_enforced_dwell_refuses_waits_longer_than_the_cell_budget():
    from app.pathfinder_4d import astar_4d, no_path_reason_4d
    rover = get_rover("lpr_1"); n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3); cost[:20, :, 2:] = np.inf   # the right half opens at slice 20: a wait pays
    wait = np.full((slices, n, n), 0.001); trav = np.ones((n, n), bool)
    free = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover)
    assert free["metrics"]["wait_steps"] >= 10
    cube = TD.build_dwell_cube(np.full(cost.shape, -140.0), 0.25, rover, trav)   # ~0.27 h budget: one wait at most
    bound = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True)
    assert bound["error"] is not None and bound["metrics"]["edges_rejected"]["thermal_dwell"] > 0
    assert "thermal dwell" in no_path_reason_4d(bound["metrics"]["edges_rejected"], rover, slices, 0.25)
    assert bound["metrics"]["thermal_dwell_enforced"] is True

def test_enforced_dwell_lets_short_waits_through_and_reports_zero_past():
    from app.pathfinder_4d import astar_4d
    rover = get_rover("lpr_1"); n, slices = 4, 30
    cost = np.full((slices, n, n), 0.3); cost[:2, :, 2:] = np.inf
    wait = np.full((slices, n, n), 0.001); trav = np.ones((n, n), bool)
    cube = TD.build_dwell_cube(np.full(cost.shape, -60.0), 0.25, rover, trav)   # -60 -> inner 0: boundary, unlimited
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 80.0, 0.25, rover, max_dwell_cube=cube, require_thermal_dwell=True)
    assert out["error"] is None and out["metrics"]["states_past_thermal_dwell"] == 0

def test_require_without_a_cube_is_refused_with_a_reason():
    from app.pathfinder_4d import astar_4d
    cost, wait, trav = _open_field()
    out = astar_4d(cost, wait, trav, (0, 0), (7, 7), 80.0, 0.25, get_rover("lpr_1"), require_thermal_dwell=True)
    assert out["error"] and "require_thermal_dwell" in out["error"]
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama** — cephe demetleri 5'li (`stay`), `stay_tol = slice_hours if enforce_dwell else inf`,
  `stay_key = int(stay/Δ) if enforce_dwell else 0`; `stay_of` sözlüğü; WAIT: `new_stay = stay + Δ`;
  `enforce_dwell`: `t_arr = slice_index − int(round(stay/Δ))`; `budget = cube.at(t_arr, row, col)[0]`;
  `new_stay > budget + 1e-9 → rejections["thermal_dwell"] += 1` (küp NaN → reddetme yok: geçilmez
  hücre zaten yok). MOVE: `stay = 0`. Dönüşte küp varsa `route_dwell_report(states, Δ, cube)`.
- [x] **Adım 4: yeşil**; `python -m pytest test_pathfinder_4d.py test_survival.py -q -p no:cacheprovider` yeşil.

### Task 5: LP-R12 ve `dwell_margin_h` sinyali

**Files:** Modify `backend/app/safety_monitor.py` (`SIGNAL_NAMES`, `SAMPLE_KEYS`, `REQUIREMENTS`, `trace_from_plan4d`,
`trace_from_samples`); Modify `backend/test_safety_monitor.py` (`range(1, 13)`); Modify
`docs/requirements/README.md`; Regenerate `docs/requirements/lunapath.fret.json`; Test `backend/test_thermal_dwell.py`.

- [x] **Adım 1: testler**

```python
def test_lp_r12_is_in_the_catalogue_and_its_export():
    from app import safety_monitor as sm
    req = next(r for r in sm.REQUIREMENTS if r.id == "LP-R12")
    assert req.name == "thermal_dwell" and req.signal == "dwell_margin_h" and req.kind == "lower"
    assert req.fretish == "The rover shall always satisfy stay_h <= max_dwell_h"
    doc = sm.fret_export()
    r12 = next(r for r in doc["requirements"] if r["reqid"] == "LP-R12")
    assert r12["monitor"]["formula_by_rover"]["lpr_1"] == "always (dwell_margin_h >= 0)"

def test_plan4d_trace_carries_dwell_margin_only_when_given():
    from app import safety_monitor as sm
    rover = get_rover("lpr_1")
    kwargs = dict(path_states=[(0, 0, 0), (0, 0, 1), (0, 1, 2)], path_battery_pct=[100, 99, 98], path_dark_hours=[0, 0, 0],
                  path_earth_visible=None, path_hours_until_earthset=None, path_haven_margin_h=None, slice_hours=0.5,
                  coarse_slope=np.zeros((2, 2)), coarse_elevation=np.zeros((2, 2)), coarse_thermal=np.full((2, 2), -60.0),
                  resolution_m=80.0, rover=rover)
    plain = sm.trace_from_plan4d(**kwargs)
    assert "dwell_margin_h" not in plain.signals
    block = sm.evaluate_catalogue(plain, rover)
    assert next(e for e in block["requirements"] if e["id"] == "LP-R12")["applicable"] is False
    with_dwell = sm.trace_from_plan4d(**kwargs, path_dwell_margin_h=[None, 0.1, -0.2])
    np.testing.assert_allclose(with_dwell.signals["dwell_margin_h"], [np.inf, 0.1, -0.2])
    entry = next(e for e in sm.evaluate_catalogue(with_dwell, rover)["requirements"] if e["id"] == "LP-R12")
    assert entry["satisfied"] is False and entry["rho"] == pytest.approx(-0.2)

def test_telemetry_samples_accept_dwell_margin():
    from app import safety_monitor as sm
    trace = sm.trace_from_samples([{"t_h": 0, "dwell_margin_h": 1.0}, {"t_h": 1, "dwell_margin_h": 0.5}])
    assert list(trace.signals["dwell_margin_h"]) == [1.0, 0.5]
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama**; `python scripts/export_fret_requirements.py`; README satırı; D3 testi `range(1, 13)`.
- [x] **Adım 4: yeşil**; `python -m pytest test_safety_monitor.py test_safety_monitor_api.py -q -p no:cacheprovider` yeşil.

### Task 6: `replan_triggers.check_entrenchment` ve `thermal_dwell.entrenchment_block`

**Files:** Modify `backend/app/replan_triggers.py`; Modify `backend/app/thermal_dwell.py`; Test `backend/test_thermal_dwell.py`.

**Produces:** `ENTRENCHMENT_WARNING_FRAC = 0.5`, `ENTRENCHMENT_CRITICAL_FRAC = 0.8`, `ENTRENCHMENT_LEVELS =
("ok", "warning", "critical", "fail")`, `entrenchment_level(used_fraction) -> str`,
`check_entrenchment(entrenched_hours, tolerable_hours) -> TriggerResult`; `_TRIGGER_INPUTS["entrenchment"]`;
`thermal_dwell.entrenchment_block(entrenched_h, thermal: dict | None, haven: dict | None) -> dict`
(`thermal.remaining_h/level`, `haven.remaining_h/level`, `overall {tolerable_h, remaining_h, level, limiting}`).

- [x] **Adım 1: testler**

```python
def test_entrenchment_levels_and_trigger():
    from app import replan_triggers as RT
    assert [RT.entrenchment_level(u) for u in (0.0, 0.49, 0.5, 0.79, 0.8, 0.99, 1.0, 3.0)] == \
        ["ok", "ok", "warning", "warning", "critical", "critical", "fail", "fail"]
    assert not RT.check_entrenchment(1.0, 4.0).triggered and "warning" not in RT.check_entrenchment(1.0, 4.0).detail
    assert not RT.check_entrenchment(2.5, 4.0).triggered and "warning" in RT.check_entrenchment(2.5, 4.0).detail
    assert RT.check_entrenchment(3.5, 4.0).triggered and "critical" in RT.check_entrenchment(3.5, 4.0).detail
    assert RT.check_entrenchment(5.0, 4.0).triggered and "fail" in RT.check_entrenchment(5.0, 4.0).detail
    detailed = RT.evaluate_triggers_detailed({"entrenched_hours": 3.5, "tolerable_entrenched_hours": 4.0})
    assert [r.trigger_id for r in detailed["fired"]] == ["entrenchment"]
    assert any(s["trigger_id"] == "entrenchment" for s in RT.evaluate_triggers_detailed({"entrenched_hours": 1.0})["skipped"])

def test_entrenchment_block_takes_the_tighter_countdown():
    block = TD.entrenchment_block(1.0, {"max_dwell_h": 1.5, "side": "cold", "component": "battery"}, {"tolerable_h": 6.0})
    assert block["thermal"]["remaining_h"] == pytest.approx(0.5) and block["thermal"]["level"] == "warning"
    assert block["haven"]["level"] == "ok" and block["overall"]["limiting"] == "thermal" and block["overall"]["level"] == "warning"
    open_block = TD.entrenchment_block(1.0, {"max_dwell_h": None, "side": None, "component": None}, None)
    assert open_block["overall"]["tolerable_h"] is None and open_block["overall"]["level"] == "ok"
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** · **Adım 4: yeşil**; `test_replan_triggers.py` yeşil.

### Task 7: `cell_shadow_series`, `cell_dwell`, `thermal_dwell_block`

**Files:** Modify `backend/app/illumination_series.py`; Modify `backend/app/thermal_dwell.py`; Test `backend/test_thermal_dwell.py`.

**Produces:** `cell_shadow_series(metadata, row, col, n_slices, slice_hours, start_utc, base_value) -> (list[float], dict)`;
`cell_dwell(sunlit_peak_c, base_shadow, shadow_series, slice_hours, rover, initial_inner_c=None, heater_model="none") -> dict`
(`max_dwell_h` (None = açık uçlu), `open_ended`, `side`, `component`, `inner_equilibrium_c {peak, cold_end}` girdiden
hesaplanır: `peak` = `inner_target(sunlit)`, `cold_end` = `inner_target(shadowed_equilibrium(sunlit, base))`,
`envelope_verdict {peak, cold_end}` ∈ {"inside","cold","hot"}, `initial_inner_c`, `lookahead_h`, `surface_c_series` özeti);
`thermal_dwell_block(cube, route, requested, applied, reason, inner_trace, rover, heater_model, initial_inner_c, shadow_model) -> dict`.

- [x] **Adım 1: testler**

```python
def test_cell_shadow_series_is_static_without_an_epoch_or_cube():
    from app.illumination_series import cell_shadow_series
    series, prov = cell_shadow_series({"shape": [4, 4]}, 1, 1, 5, 0.5, None, base_value=0.3)
    assert series == [0.3] * 5 and prov["model"] == "static" and "epoch" in prov["reason"]

def test_cell_dwell_matches_the_cube_on_the_same_series():
    rover = get_rover("lpr_1")
    card = TD.cell_dwell(-146.0, 0.9, [1.0] * 48, 0.5, rover)      # a polar flat cell, dark for 24 h
    cube = TD.build_dwell_cube(TD.surface_series_for_cell(-146.0, 0.9, [1.0] * 48, 0.5)[:, None, None], 0.5, rover, np.ones((1, 1), bool))
    assert card["max_dwell_h"] == pytest.approx(float(cube.max_dwell_h[0, 0, 0]), rel=1e-9)
    assert card["envelope_verdict"]["cold_end"] == "cold" and card["side"] == "cold"

def test_thermal_dwell_block_has_both_shapes():
    rover = get_rover("lpr_1")
    off = TD.thermal_dwell_block(None, None, requested=False, applied=False, reason="not requested", inner_trace=None, rover=rover)
    assert off["validity"] == "MODEL" and off["thermal_lag_validity"] == "UNCALIBRATED" and off["dwell_model"]["model"] == "unavailable"
    cube = TD.build_dwell_cube(_constant_series(-100.0, n=4), 0.5, rover, np.ones((3, 3), bool))
    on = TD.thermal_dwell_block(cube, TD.route_dwell_report([(0, 0, 0), (0, 0, 1)], 0.5, cube), requested=True, applied=True,
                                reason=None, inner_trace=None, rover=rover)
    assert on["applied"] is True and on["cube"]["fraction_cold_limited"] == 1.0 and on["quoted"]["max_polar_sun_elevation_deg"] == 1.5
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** (`surface_series_for_cell` yardımcı: `shadowed_equilibrium_c`
  skaler + `relax_surface_c` dilim dilim; `cell_dwell` bunun üzerine `build_dwell_cube` (1×1)) · **Adım 4: yeşil**.

### Task 8: `main.py` — plan-4d, cell-telemetry, replan, `GET /api/thermal-dwell`

**Files:** Modify `backend/app/main.py`; Test `backend/test_thermal_dwell_api.py` (yeni; `test_survival_api.py` fixture'ı;
`thermal` fixture −100 → LPR-1 iç −40, soğuk-sınırlı ≈ 0,73 h < 1 h dilim).

- [x] **Adım 1: testler**

```python
def test_plan_4d_reports_thermal_dwell_by_default(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    block = payload["thermal_dwell"]
    assert block["requested"] is False and block["applied"] is False and block["validity"] == "MODEL"
    assert block["dwell_model"]["model"] == TD.THERMAL_DWELL_MODEL_ID and block["heater_model"] == "none"
    assert len(payload["path_max_dwell_h"]) == len(payload["path_states"]) == len(payload["path_inner_c"])
    assert payload["metrics"]["thermal_dwell_enforced"] is False
    assert any(e["id"] == "LP-R12" and e["applicable"] for e in payload["safety_margins"]["requirements"])

def test_plan_4d_require_thermal_dwell_refuses_waits_or_finds_a_waitless_route(client):
    response = client.post("/api/plan-4d", json=_body(require_thermal_dwell=True))
    if response.status_code == 200:
        assert response.json()["metrics"]["wait_steps"] == 0 and response.json()["thermal_dwell"]["applied"] is True
    else:
        assert response.status_code == 404 and "thermal dwell" in response.json()["detail"]

def test_plan_4d_thermostat_and_initial_inner_are_echoed_and_bounded(client):
    payload = client.post("/api/plan-4d", json=_body(heater_model="thermostat_assumed", initial_inner_c=5.0)).json()
    assert payload["thermal_dwell"]["heater_model"] == "thermostat_assumed" and payload["thermal_dwell"]["heater_source"].startswith("assumption:")
    assert payload["thermal_dwell"]["initial_inner_c"] == 5.0
    assert client.post("/api/plan-4d", json=_body(initial_inner_c=500.0)).status_code == 422
    assert client.post("/api/plan-4d", json=_body(rover_id="luvmi_m", require_thermal_dwell=True)).status_code == 422

def test_cell_telemetry_thermal_dwell_card(client):
    off = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    assert off["thermal_dwell"] is None and "not requested" in off["thermal_dwell_model"]["reason"]
    on = client.get("/api/cell-telemetry", params={"row": 3, "col": 3, "thermal_dwell": "true", "start_utc": "2026-09-28T00:00:00"}).json()
    card = on["thermal_dwell"]
    assert card["side"] == "cold" and card["max_dwell_h"] is not None and card["envelope_verdict"]["cold_end"] == "cold"
    assert card["tolerable_entrenched"]["haven"] is None and card["tolerable_entrenched"]["overall"]["limiting"] == "thermal"

def test_replan_entrenchment_countdown_levels(client):
    body = {"current": {"row": 3, "col": 3}, "goal": {"row": 12, "col": 12}, "utc": "2026-09-28T00:00:00",
            "state": {"entrenched_hours": 0.1}}
    r = client.post("/api/replan", json=body).json()
    assert r["entrenchment"]["overall"]["level"] == "ok" and r["replanned"] is False
    body["state"]["entrenched_hours"] = 5.0
    r = client.post("/api/replan", json=body).json()
    assert r["entrenchment"]["overall"]["level"] == "fail" and any(t["trigger_id"] == "entrenchment" for t in r["triggers"])
    r = client.post("/api/replan", json={**body, "utc": None}).json()
    assert r["entrenchment"] is None and "utc" in r["entrenchment_model"]["reason"]

def test_thermal_dwell_layer_json_and_binary(client):
    js = client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "lookahead_hours": 4}).json()
    assert js["grid"]["rows"] == 4 and set(js["fields"]) == {"max_dwell_h", "side", "open_ended"}
    assert js["summary"]["fraction_cold_limited"] == 1.0
    bin_ = client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "lookahead_hours": 4, "format": "f32", "field": "max_dwell_h"})
    assert bin_.headers["X-Layer-Validity"] == "MODEL" and len(bin_.content) == 4 * 4 * 4
    assert client.get("/api/thermal-dwell", params={"start_utc": "2026-09-28T00:00:00", "rover_id": "luvmi_m"}).status_code == 422
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** (spec karar 9–10; `_cell_dwell_card(grids, rover, row, col, utc,
  t_hours, lookahead, initial, heater)` yardımcı; `_haven_countdown(grids, rover_id, row, col, utc)` yardımcı) ·
  **Adım 4: yeşil**; `test_plan_4d_endpoint.py test_survival_api.py test_cell_telemetry_explain.py test_replan_endpoint*.py` yeşil.

### Task 9: Zarf matrisi — heat1d örnekleyici, kutulama, önbellek, `GET /api/thermal-envelope`

**Files:** Modify `backend/app/thermal_dwell.py`; Create `scripts/build_thermal_envelope_cache.py`; Modify `backend/app/main.py`;
Test `backend/test_thermal_dwell.py`, `backend/test_thermal_dwell_api.py`.

**Produces:** `ENVELOPE_EL_EDGES`, `ENVELOPE_SPAR_EDGES`, `ENVELOPE_SLOPES_DEG`, `ENVELOPE_CACHE_FILENAME =
"thermal_envelope_heat1d.npz"`, `ENVELOPE_META_FILENAME = "thermal_envelope_meta.json"`;
`heat1d_envelope_samples(lat_deg, slopes, ndays=13) -> dict[str, np.ndarray]` (`el_deg`, `s_par_deg`, `surface_c`, `slope_deg`);
`bin_envelope(samples, el_edges, sp_edges) -> dict` (`tmax`, `tmean`, `count`); `envelope_cache_path(metadata) -> str | None`;
`save_envelope_cache(path, binned, meta)`, `load_envelope_cache(path) -> dict`;
`envelope_matrix(cache, rover, initial_inner_c=None, heater_model="none") -> dict` (kutu kararı/dwell).

- [x] **Adım 1: testler**

```python
def test_bin_envelope_and_matrix_verdicts_on_synthetic_samples():
    samples = {"el_deg": np.array([0.2, 0.3, 2.0, -1.0]), "s_par_deg": np.array([1.0, 1.0, 20.0, -20.0]),
               "surface_c": np.array([-100.0, -90.0, -20.0, -200.0]), "slope_deg": np.array([1, 1, 20, 20.0])}
    binned = TD.bin_envelope(samples, np.array([-3, 0, 1, 3.0]), np.array([-30, 0, 10, 30.0]))
    assert binned["tmax"][1, 1] == -90.0 and binned["count"][1, 1] == 2 and np.isnan(binned["tmax"][0, 2])
    matrix = TD.envelope_matrix({**binned, "el_edges": np.array([-3, 0, 1, 3.0]), "sp_edges": np.array([-30, 0, 10, 30.0])}, get_rover("lpr_1"))
    cells = {(c["el_bin"], c["s_par_bin"]): c for c in matrix["cells"]}
    assert cells[(1, 1)]["verdict"] == "cold_limited" and cells[(2, 2)]["verdict"] == "hot_limited"   # -20 surface -> +40 inner
    assert cells[(0, 2)]["verdict"] == "unsampled" and matrix["counts"]["hot_limited"] == 1

def test_envelope_endpoint_needs_the_cache_and_serves_it(client, tmp_path, monkeypatch):
    assert client.get("/api/thermal-envelope").status_code == 422
    binned = TD.bin_envelope({"el_deg": np.array([0.5]), "s_par_deg": np.array([5.0]), "surface_c": np.array([-50.0]), "slope_deg": np.array([5.0])},
                             TD.ENVELOPE_EL_EDGES, TD.ENVELOPE_SPAR_EDGES)
    path = tmp_path / TD.ENVELOPE_CACHE_FILENAME
    TD.save_envelope_cache(str(path), binned, {"lat_deg": -88.92, "slopes_deg": [5.0], "ndays": 13})
    monkeypatch.setattr(TD, "envelope_cache_path", lambda metadata: str(path))
    payload = client.get("/api/thermal-envelope", params={"rover_id": "lpr_1"}).json()
    assert payload["counts"]["unlimited"] == 1 and payload["quoted"]["case_matrix"] == 96
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** (heat1d alt sınıfı `_RecordingModel` sondadaki gibi;
  `available()` yoksa `RuntimeError`) · **Adım 4: yeşil**; betiği koştur:
  `python scripts/build_thermal_envelope_cache.py` (≈ 45 s) → `lunapath/data/processed/thermal_envelope_heat1d.npz`.

### Task 10: Gerçek grid testleri (skip-korumalı)

**Files:** Create `backend/test_thermal_dwell_real_grid.py` (`test_survival_real_grid.py` kalıbı).

- [x] **Adım 1: testler** — üç standart rota kısıtsız 41 / 116 / 8 hamle ve `thermal_dwell` bloğu tutarlı
  (`len(path_max_dwell_h) == len(path_states)`, `cube.fraction_unlimited` LPR-1 gündüz dilim 0'da 0,05–0,45);
  `require_thermal_dwell` üç rotada 200 ya da 404 (gerekçede "thermal dwell"); Ay gecesi başlangıcında
  `/api/replan` saplanma bloğu (`thermal.max_dwell_h` sonlu, `haven` null ya da sayı); zarf önbelleği varsa
  `GET /api/thermal-envelope` maks yüzey < 60 °C ve LPR-1'de `hot_limited` kutularının hepsi yüzey < 0.
- [x] **Adım 2: koştur**, süreleri not et.

### Task 11: Rapor betiği ve rapor

**Files:** Create `scripts/thermal_dwell_report.py`; Create `docs/research/thermal_dwell_report.md`.

- [x] **Adım 1:** betik (`--json` önce, `--from-json`, `--skip-envelope`, `--heater`); bölümler spec 15.
- [x] **Adım 2:** koştur (`python scripts/thermal_dwell_report.py --json <scratch>/c6.json`), sayıları oku.

### Task 12: Belgeler, tam paket, tek commit, hafıza

- [x] Araştırma belgesinde C6 başlığına ✅ + "> Yapıldı (…)" bloğu; spec § bulunanlar; README satırı
  (B1 satırının altına); sözleşme "C6 eki" (B1 ekinin ardına); `docs/requirements/README.md`.
- [x] `cd backend && python -m pytest -q -p no:cacheprovider` (arka plan, log dosyasına; **1 502 passed, 5 skipped, 21 dk 25 s**).
- [x] `ruff check` yeni/değişen dosyalar (temiz; `cost_cube.py` E402 ve `test_safety_monitor_api.py` F401 önceden var); `git status --short` başıboş dosya yok.
- [x] Tek commit (B1 biçimi; eş-yazar satırı yok). Hafıza dosyaları.
