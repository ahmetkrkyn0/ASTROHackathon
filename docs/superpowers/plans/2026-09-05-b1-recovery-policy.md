# B1 — Stokastik reach-avoid kurtarma politikası ve şans-kısıtlı 4-B planlama — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Kaba grid + gölge serisi + `cost_engine` fiziği üzerinde (t, hücre, SOC kutusu) durum
uzayında Lamarre'nin üç sonuçlu Poisson arıza modeli ve min-max konservatif eşlemesiyle geriye
doğru değer iterasyonu (`P_safe`, politika); `astar_4d`'ye yürütme hayatta-kalma etiketi ve
`max_failure_probability = β` kısıtı; `/api/plan-4d` `survival` bloğu, `/api/cell-telemetry`
`survival`, `/api/replan` `recovery_suggestion`, `GET /api/survival`; SHERPA'ya arıza olayı;
politikayı izleyen Monte Carlo ile konservatiflik denetimi; rapor.

**Architecture:** Yeni `app/survival.py` (sabitler, yön tabloları, DP, `SurvivalField`, rollout,
API blokları); `pathfinder_4d.py` dördüncü etiket ekseni + `failure_probability` reddi (yalnızca
ekleme, alan yokken bit-eşit); `stress_test.py` arıza penceresi; `main.py` istek/yanıt alanları,
alan önbelleği, dört uç; `scripts/recovery_policy_report.py` (`--json` önce, `--from-json`).

**Spec:** [2026-09-05-b1-recovery-policy-design.md](../specs/2026-09-05-b1-recovery-policy-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2 (`take_along_axis`, dilimleme), SciPy 1.15 (Wilson için
`stress_test.wilson_interval`, Poisson `rng.poisson`), FastAPI/pydantic, pytest.

**Commit kuralı:** özellik bitince **tek commit**; ara commit yok; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Sayı uydurma yok: her `P_safe`, β etkisi, uzunluk/süre farkı Site11'de koşturulup okunur;
  Lamarre'nin sayıları `LAMARRE_QUOTED` sözlüğünde "alıntı" olarak durur.
- α ve R **varsayım**: `constants.FAILURE_RATE_PER_KM_ASSUMED = 0.2`, `FAULT_RECOVERY_HOURS_ASSUMED
  = 10.0`, `FAILURE_MODEL_SOURCE` `"assumption: …"` ile başlar; rover profillerine alan eklenmez.
- `max_failure_probability=None` ve `survival_field=None` iken `astar_4d` **bit-eşit**; standart
  4-B rotalar (41 / 116 / 8 hamle) ve 2-B SHA kilitleri değişmez; `report_survival` istenmedikçe
  DP koşmaz.
- Güvenli küme varsayılanı `"leg"` (hedef ∪ haven); `"haven"` seçilebilir; ikisi de yanıtta
  yazılır. DP durumunda karanlık saati yok; termal yok.
- Durum tavanı `MAX_SURVIVAL_STATES = 40_000_000` (m otomatik); ufuk ≤ 168 h; float32/uint8.
- Frontend'e dokunulmaz; sözleşme belgesine yalnızca "B1 eki" (C4 ekinin ardına, "Değişmeyenler"
  öncesine). Mevcut alanlar aynen.
- Gerçek grid / çekirdek gerektiren testler skip-korumalı; yeni dosyalarda ruff temiz; rapor
  betiği `sys.stdout` UTF-8, JSON önce; JSON commit'lenmez; raporda mutlak yol yok.
- Planlayıcıyı tracemalloc altında zamanlama.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/constants.py` | `FAILURE_RATE_PER_KM_ASSUMED`, `FAULT_RECOVERY_HOURS_ASSUMED`, `FAILURE_MODEL_SOURCE` |
| `backend/app/terrain.py` | `LAYER_UNITS`/`LAYER_DESCRIPTIONS`: `survival_probability`, `best_action` (manifeste girmez) |
| `backend/app/survival.py` (yeni) | sabitler/iddia, `fault_outcome_probabilities`, `haven_hibernation_soc_wh`, `safe_soc_requirement`, `DirectionTables`/`direction_tables`, `bin_shadow_series`, `auto_slices_per_bin`, `build_survival_field`, `SurvivalField`, `rollout`, `survival_block`, `recovery_suggestion`, önbellek |
| `backend/app/pathfinder_4d.py` | `surv` ekseni, `failure_probability` reddi, metrikler |
| `backend/app/stress_test.py` | `Perturbations.fault_rate_per_km/fault_recovery_h`, örnekleme, beklemeler, `faults` özeti |
| `backend/app/main.py` | `Plan4DRequest` alanları, `_survival_field_for_plan`, `survival` bloğu, cell-telemetry, replan, `GET /api/survival`, `PerturbationOverrides` |
| `backend/test_survival.py` (yeni) | birim + planlayıcı entegrasyonu (çekirdeksiz) |
| `backend/test_survival_api.py` (yeni) | uçlar (çekirdeksiz TestClient, statik gölge) |
| `backend/test_survival_real_grid.py` (yeni) | skip-korumalı gerçek grid |
| `backend/test_stress_test.py` | arıza olayı testleri (ek) |
| `scripts/recovery_policy_report.py` (yeni) | koşum + JSON + markdown |
| `docs/research/recovery_policy_report.md` | rapor çıktısı |
| `docs/frontend/3b-veri-sozlesmesi.md` | B1 eki |
| `README.md`, `docs/research/12_faktor…md`, spec | satır, ✅ + Yapıldı, ölçümler |

---

### Task 0: Sabitler ve katman etiketleri

**Files:** Modify `backend/app/constants.py` (C3 çapaları bölümünün altı); Modify `backend/app/terrain.py` (`LAYER_UNITS`, `LAYER_DESCRIPTIONS`); Test `backend/test_survival.py`.

**Produces:** `constants.FAILURE_RATE_PER_KM_ASSUMED: float = 0.2`, `constants.FAULT_RECOVERY_HOURS_ASSUMED: float = 10.0`, `constants.FAILURE_MODEL_SOURCE: str` (`"assumption: "` ile başlar); `terrain.LAYER_UNITS["survival_probability"] == "fraction"`, `LAYER_UNITS["best_action"] == "code"`; `"survival_probability" not in TERRAIN_LAYERS`.

- [x] **Adım 1: başarısız test**

```python
def test_failure_model_constants_are_labelled_assumptions():
    from app import constants as C
    assert C.FAILURE_RATE_PER_KM_ASSUMED == 0.2 and C.FAULT_RECOVERY_HOURS_ASSUMED == 10.0
    assert C.FAILURE_MODEL_SOURCE.startswith("assumption:")
    for rover in C.ROVERS.values():
        assert "failure_rate_per_km" not in rover

def test_survival_layers_are_described_but_not_in_the_manifest():
    from app.terrain import LAYER_DESCRIPTIONS, LAYER_UNITS, TERRAIN_LAYERS
    assert LAYER_UNITS["survival_probability"] == "fraction" and LAYER_UNITS["best_action"] == "code"
    assert "survival_probability" in LAYER_DESCRIPTIONS and "survival_probability" not in TERRAIN_LAYERS
```

- [x] **Adım 2: kırmızı** (`python -m pytest test_survival.py -q -p no:cacheprovider`)
- [x] **Adım 3: uygulama** — sabitler + iki katman satırı.
- [x] **Adım 4: yeşil**

### Task 1: `survival.py` — sabitler, arıza olasılıkları, güvenli küme eşiği, yön tabloları, gölge kutulama

**Files:** Create `backend/app/survival.py`; Test `backend/test_survival.py`.

**Produces:**
- `SURVIVAL_MODEL_ID`, `SURVIVAL_VALIDITY = "MODEL"`, `SAFE_SETS`, `ACTION_NAMES`, `ACTION_WAIT = 8`,
  `ACTION_SAFE = 254`, `ACTION_NONE = 255`, `DEFAULT_SOC_BINS = 20`, `MAX_SURVIVAL_STATES`,
  `MAX_SURVIVAL_HORIZON_HOURS = 168.0`, `SURVIVAL_SCOPE`, `SURVIVAL_CLAIM`, `SURVIVAL_REFERENCES`,
  `LAMARRE_QUOTED`, `OFFSETS` (= `pathfinder_4d._OFFSETS`).
- `fault_outcome_probabilities(rate_per_km: float, distance_m: float) -> tuple[float, float, float]`
- `haven_hibernation_soc_wh(rover) -> float`
- `safe_soc_requirement(traversable, haven_mask, goal, rover, safe_set) -> np.ndarray (H, W) float64`
- `DirectionTables(allowed (8,H,W) bool, travel_h (8,H,W), distance_m (8,), traction_w (8,H,W))`;
  `direction_tables(traversable, elevation, slope, resolution_m, rover) -> DirectionTables`
- `bin_shadow_series(series, slices_per_bin) -> np.ndarray (n_bins, H, W)`
- `auto_slices_per_bin(n_slices_needed, n_cells, n_soc_bins, max_states) -> int`

- [x] **Adım 1: testler**

```python
import math, numpy as np, pytest
from app.constants import get_rover
from app import survival as S

def test_fault_outcomes_are_lamarre_eq_2_to_4_and_sum_to_one():
    p0, p1, p2 = S.fault_outcome_probabilities(0.2, 320.0)   # 1 per 5 km, one 320 m block
    rho = 0.2 / 1000.0 * 320.0
    assert p0 == pytest.approx(math.exp(-rho)) and p1 == pytest.approx(1 - math.exp(-rho / 2))
    assert p2 == pytest.approx(math.exp(-rho / 2) - math.exp(-rho)) and p0 + p1 + p2 == pytest.approx(1.0)
    assert S.fault_outcome_probabilities(0.0, 320.0) == (1.0, 0.0, 0.0)

def test_haven_hibernation_soc_is_reserve_plus_dark_housekeeping_over_endurance():
    rover = get_rover("lpr_1")   # 5420 Wh, reserve 20 %, 65 W in shadow, 50 h
    assert S.haven_hibernation_soc_wh(rover) == pytest.approx(min(5420.0, 0.2 * 5420 + 65 * 50))

def test_safe_soc_requirement_leg_and_haven_sets():
    rover = get_rover("lpr_1")
    trav = np.ones((3, 3), dtype=bool); haven = np.zeros((3, 3), dtype=bool); haven[0, 0] = True
    leg = S.safe_soc_requirement(trav, haven, (2, 2), rover, "leg")
    assert leg[2, 2] == pytest.approx(0.2 * 5420) and leg[0, 0] == pytest.approx(S.haven_hibernation_soc_wh(rover))
    assert np.isinf(leg[1, 1])
    only = S.safe_soc_requirement(trav, haven, (2, 2), rover, "haven")
    assert np.isinf(only[2, 2]) and np.isfinite(only[0, 0])
    with pytest.raises(ValueError):
        S.safe_soc_requirement(trav, None, None, rover, "leg")   # leg needs a goal

def test_direction_tables_match_the_gated_edge_graph():
    from app.safe_haven import _gated_edges
    rng = np.random.default_rng(3); rover = get_rover("lpr_1")
    trav = rng.random((12, 12)) > 0.2; elev = rng.random((12, 12)) * 40.0; slope = rng.random((12, 12)) * 20.0
    tables = S.direction_tables(trav, elev, slope, 80.0, rover)
    src, dst, hours = _gated_edges(trav, elev, slope, 80.0, rover)
    expected = {(int(a), int(b)): float(h) for a, b, h in zip(src, dst, hours)}
    expected.update({(b, a): h for (a, b), h in list(expected.items())})   # graph is symmetric
    got = {}
    for d, (dr, dc, _) in enumerate(S.OFFSETS):
        for r, c in zip(*np.nonzero(tables.allowed[d])):
            got[(int(r * 12 + c), int((r + dr) * 12 + c + dc))] = float(tables.travel_h[d, r, c])
    assert got.keys() == expected.keys()
    for key in got: assert got[key] == pytest.approx(expected[key])
    assert tables.distance_m[4] == pytest.approx(80.0 * math.sqrt(2)) and tables.distance_m[0] == 80.0

def test_bin_shadow_series_is_the_block_mean_over_slices():
    series = [np.full((2, 2), v) for v in (0.0, 1.0, 1.0, 0.5, 0.2)]
    binned = S.bin_shadow_series(series, 2)
    assert binned.shape == (3, 2, 2) and binned[0, 0, 0] == 0.5 and binned[1, 0, 0] == 0.75 and binned[2, 0, 0] == 0.2

def test_auto_slices_per_bin_respects_the_state_cap():
    assert S.auto_slices_per_bin(100, 15625, 20, 40_000_000) == 1
    assert S.auto_slices_per_bin(460, 15625, 20, 40_000_000) == 4
```

- [x] **Adım 2: kırmızı** (`ImportError`)
- [x] **Adım 3: uygulama** — `direction_tables` `_gated_edges` ile aynı kapılar, yön başına tam
  grid maskesi (kaynak hücrede indekslenir; `np.zeros((8,H,W))` üzerine dilimleme ile yazılır),
  `travel_h = edge_travel_time_s_array(½(θ_c + θ_c'), d) / 3600`, `traction_w = p_base ·
  (1 + μ sin(max(0, θ_edge)))`. `auto_slices_per_bin = max(1, ceil(n_slices_needed · n_cells ·
  K / max_states))`.
- [x] **Adım 4: yeşil**; `ruff check backend/app/survival.py`.

### Task 2: `survival.py` — geriye doğru değer iterasyonu ve `SurvivalField`

**Files:** Modify `backend/app/survival.py`; Test `backend/test_survival.py`.

**Produces:**
```python
@dataclass
class SurvivalField:
    p_safe: np.ndarray            # (T, H, W, K) float32, 1 - V
    policy: np.ndarray            # (T, H, W, K) uint8
    step_hours: float; slices_per_bin: int; n_bins: int; n_soc_bins: int
    soc_bin_wh: float; e_cap_wh: float; reserve_wh: float
    exposure: np.ndarray          # (T, H, W) mean shadow per bin
    cumulative: np.ndarray        # (T + 1, H, W) shadow-hours up to bin start
    rate_per_km: float; recovery_h: float; safe_set: str
    safe_soc_min_wh: np.ndarray   # (H, W)
    tables: DirectionTables; rover: Mapping; provenance: dict; compute_s: float
    def soc_bin(self, wh) -> int
    def bins_of_hours(self, hours) -> tuple[int, int]      # floor/ceil, clipped to n_bins (== n_bins -> beyond)
    def p_safe_at(self, slice_index, r, c, wh) -> float     # min over the two bins, floor soc; 0 beyond horizon
    def recovery_drain_wh(self, r, c, from_h) -> float      # inf beyond horizon
    def move_survival_factor(self, slice_index, r, c, nr, nc, wh, travel_h, distance_m, drain_wh) -> tuple[float, float, float, float, float]
    def best_action(self, slice_index, r, c, wh) -> dict
    @property n_states -> int; nbytes -> int
    def info(self) -> dict
build_survival_field(traversable, elevation, slope, resolution_m, rover, shadow_bins, step_hours,
                     slices_per_bin, safe_soc_min_wh, n_soc_bins=20, failure_rate_per_km=0.2,
                     recovery_hours=10.0, provenance=None) -> SurvivalField
```

- [x] **Adım 1: testler** (küçük gridler; `_rover()` = `dict(get_rover("lpr_1"))` üzerine
  `p_solar_w=0, p_idle_w=100, p_heater_w=0, p_shadow_w=100, p_base_w=200, mu_coeff=0, e_cap_wh=1000,
  soc_min_pct=0.0, v_max_ms=1.0, slope_max_deg=90, slope_lateral_max_deg=90, slip_curve=None` — kapalı formu
  elle hesaplanabilir kılar)

```python
def _field(trav, safe_req, rover, n_bins=3, step=1.0, K=4, rate=0.0, recovery=1.0, shadow=None, res=3600.0):
    H, W = trav.shape
    shadow_bins = np.zeros((n_bins, H, W)) if shadow is None else shadow
    return S.build_survival_field(trav, None, None, res, rover, shadow_bins, step, 1, safe_req, K, rate, recovery)

def test_a_safe_cell_has_p_safe_one_and_the_safe_action():
    rover = _rover(); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover)
    assert f.p_safe[:, 0, 2, :].min() == 1.0 and (f.policy[:, 0, 2, :] == S.ACTION_SAFE).all()

def test_deterministic_reach_within_horizon_is_one_and_zero_beyond():
    # 1 x 3 strip, goal at column 2, one move per bin (res 3600 m at 1 m/s = 1 h), no drain (p_base 0)
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover, n_bins=3)
    assert f.p_safe[0, 0, 0, 3] == 1.0 and f.policy[0, 0, 0, 3] == 3      # E at bin 0 from col 0 (2 moves, bins 0->1->2)
    assert f.p_safe[1, 0, 0, 3] == 0.0                                    # only one bin left: cannot reach
    assert f.p_safe[1, 0, 1, 3] == 1.0

def test_battery_floor_bins_are_failures_and_drain_uses_the_lower_edge():
    rover = _rover(soc_min_pct=0.5)   # reserve 500 Wh of 1000 -> bins 0,1 (of 4) failed
    trav = np.ones((1, 2), dtype=bool); req = np.full((1, 2), np.inf); req[0, 1] = 0.0
    f = _field(trav, req, rover, n_bins=2, K=4)     # a move costs (200 + 100) W * 1 h = 300 Wh -> 2 bins (ceil(300/250))
    assert (f.p_safe[0, 0, 0, :2] == 0.0).all()
    assert f.p_safe[0, 0, 0, 3] == 1.0 and f.p_safe[0, 0, 0, 2] == 0.0   # 500-750 -> lower edge 500 - 300 = 200 < reserve

def test_more_soc_never_lowers_p_safe_and_more_faults_never_raise_it():
    rng = np.random.default_rng(0); rover = _rover()
    trav = rng.random((6, 6)) > 0.15; req = np.full((6, 6), np.inf); req[5, 5] = 0.0; trav[5, 5] = True
    shadow = rng.random((6, 6, 6))
    lo = _field(trav, req, rover, n_bins=6, K=8, rate=0.5, recovery=1.0, shadow=shadow)
    hi = _field(trav, req, rover, n_bins=6, K=8, rate=2.0, recovery=1.0, shadow=shadow)
    assert (np.diff(lo.p_safe, axis=3) >= -1e-6).all()
    assert (hi.p_safe <= lo.p_safe + 1e-6).all()

def test_two_cell_fault_dp_matches_the_closed_form():
    # cells A -> B(goal); 2 bins of 1 h; 1 move = 1 h; fault rate such that rho = 0.5; recovery 1 h
    # From A at bin 0 with full battery: no fault (p0) -> B at bin 1: safe.
    # fault first half (p1) -> A at 0 + 0.5 + 1 = 1.5 h -> bins floor 1 / ceil 2 (2 = beyond -> V 1): worst is 1 -> fail
    # fault second half (p2) -> B at 0 + 1 + 1 = 2 h -> beyond -> fail
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 2), dtype=bool)
    req = np.full((1, 2), np.inf); req[0, 1] = 0.0
    rate = 0.5 / 3.6   # per km: rho = rate/1000 * 3600 m = 0.5
    f = _field(trav, req, rover, n_bins=2, K=2, rate=rate, recovery=1.0)
    p0, p1, p2 = S.fault_outcome_probabilities(rate, 3600.0)
    assert f.p_safe[0, 0, 0, 1] == pytest.approx(p0, abs=1e-6)

def test_min_max_takes_the_worse_time_bin():
    # a move that takes 1.5 bins: floor 1 (lit, safe at bin 1) vs ceil 2 (beyond horizon) -> worst = 0
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0, v_max_ms=1.0); trav = np.ones((1, 2), dtype=bool)
    req = np.full((1, 2), np.inf); req[0, 1] = 0.0
    f = S.build_survival_field(trav, None, None, 5400.0, rover, np.zeros((2, 1, 2)), 1.0, 1, req, 2, 0.0, 1.0)
    assert f.p_safe[0, 0, 0, 1] == 0.0

def test_p_safe_at_reads_the_worse_of_the_neighbouring_bins_and_the_floor_soc():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover, n_bins=3)
    f.slices_per_bin = 2                           # planner slices are half a bin
    assert f.p_safe_at(1, 0, 0, 999.0) == min(f.p_safe[0, 0, 0, 3], f.p_safe[1, 0, 0, 3])
    assert f.p_safe_at(99, 0, 0, 999.0) == 0.0     # beyond the horizon
    assert f.soc_bin(999.0) == 3 and f.soc_bin(1000.0) == 3 and f.soc_bin(-5.0) == 0

def test_best_action_names_the_policy_move_and_its_target():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover)
    best = f.best_action(0, 0, 0, 1000.0)
    assert best["action"] == 3 and best["name"] == "E" and best["target"] == (0, 1) and best["p_safe_now"] == 1.0
    assert f.info()["n_states"] == 3 * 3 * 4 and f.info()["validity"] == "MODEL"
```

- [x] **Adım 2: kırmızı**
- [x] **Adım 3: uygulama** — çekirdek (vektörize, kutu başına):

```python
def build_survival_field(...):
    t0 = time.perf_counter()
    passable = np.asarray(traversable, bool); H, W = passable.shape
    tables = direction_tables(passable, elevation, slope, resolution_m, rover)
    shadow = np.asarray(shadow_bins, np.float64); T = shadow.shape[0]; K = int(n_soc_bins)
    e_cap = float(rover["e_cap_wh"]); reserve = e_cap * float(rover.get("soc_min_pct") or 0.0)
    delta = e_cap / K; lower = np.arange(K) * delta                     # bin lower edges (Wh)
    failed_bin = (lower + delta) <= reserve + 1e-9                       # whole bin under the reserve
    req = np.asarray(safe_soc_min_wh, np.float64)
    safe = (lower[None, None, :] >= req[:, :, None] - 1e-9) & passable[:, :, None] & ~failed_bin[None, None, :]
    idle = float(rover["p_idle_w"]); shadow_extra = ...; p_solar = ...
    net_wait_w = (idle - p_solar) + shadow * (shadow_extra + p_solar)   # (T, H, W) W, signed
    cumulative = np.concatenate([np.zeros((1, H, W)), np.cumsum(shadow, axis=0) * step_hours])  # shadow-hours
    h_max = float(rover.get("h_max_shadow_h") or np.inf)
    V = np.ones((T + 1, H, W, K), np.float32); policy = np.full((T + 1, H, W, K), ACTION_NONE, np.uint8)
    V[T][safe] = 0.0; policy[T][safe] = ACTION_SAFE
    k_index = np.arange(K)[None, None, :]
    def gather(t_bin, rows, cols, shift):  # V at (t_bin, cell, k - shift); k' < 0 -> 1 (failed); k' >= K -> K-1
        ...
    for t in range(T - 1, -1, -1):
        best = np.ones((H, W, K), np.float32); choice = np.full((H, W, K), ACTION_NONE, np.uint8)
        # WAIT: one bin, drain net_wait_w[t] * step
        ...
        for d, (dr, dc, _) in enumerate(OFFSETS):
            allowed = tables.allowed[d]; tau = tables.travel_h[d]; rho = tables.distance_m[d]
            d_lo = np.maximum(1, np.floor(tau / step_hours)); d_hi = np.maximum(1, np.ceil(tau / step_hours))
            # exposure trapezoid uses the arrival bin (clipped) for the destination cell
            ...
            p0, p1, p2 = fault_outcome_probabilities(rate, rho)
            expect = p0 * max(V_nofault_lo, V_nofault_hi) + p1 * max(V_f1_lo, V_f1_hi) + p2 * max(V_f2_lo, V_f2_hi)
            better = allowed[:, :, None] & (expect < best - 1e-9)
            best = np.where(better, expect, best); choice = np.where(better, d, choice)
        best[safe] = 0.0; choice[safe] = ACTION_SAFE
        best[:, :, failed_bin] = 1.0; choice[:, :, failed_bin] = ACTION_NONE
        best[~passable] = 1.0; choice[~passable] = ACTION_NONE
        V[t] = best; policy[t] = choice
    return SurvivalField(p_safe=1 - V[:T], policy=policy[:T], ...)
```

  Gather'lar hedef zaman kutusu `t + d` per-cell değiştiğinden (`d_lo/d_hi` (H, W) tamsayı),
  `V[np.clip(tb, 0, T), rows, cols, kprime]` fancy-index (tb ≥ T → 1). Arıza durumu zamanı
  `t·step + τ/2 + R` → kutu floor/ceil; `D_rec` = `cumulative` ara değeriyle `R·(idle − p_solar) +
  (shadow_extra + p_solar)·(cum(t_a + R) − cum(t_a))`; karanlık hücre (`exposure ≥ 0,5` başlangıç
  kutusunda) ve R > h_max → V = 1.
- [x] **Adım 4: yeşil**; ruff.

### Task 3: `survival.py` — `rollout`, `survival_block`, `recovery_suggestion`, önbellek

**Files:** Modify `backend/app/survival.py`; Test `backend/test_survival.py`.

**Produces:**
- `rollout(field, start, battery_wh, n_runs, seed, start_slice=0, plan_states=None) -> dict`
  (`n_runs, safe, failed, horizon, failure_rate, wilson_low, wilson_high, predicted_failure (V at start)`, `mean_faults`)
- `survival_block(field, result, beta, requested, reason=None, shadow_model=None) -> dict`
- `recovery_suggestion(field, r, c, battery_wh, coarsen, slice_index=0) -> dict`
- `cached_survival_field(key, builder) -> SurvivalField` (2 giriş), `clear_survival_cache()`

- [x] **Adım 1: testler**

```python
def test_rollout_with_no_faults_agrees_with_the_deterministic_dp():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover, n_bins=3)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=50, seed=1)
    assert out["failure_rate"] == 0.0 and out["predicted_failure"] == 0.0 and out["safe"] == 50
    out = S.rollout(f, (0, 0), 1000.0, n_runs=50, seed=1, start_slice=1)
    assert out["failure_rate"] == 1.0 and out["predicted_failure"] == 1.0

def test_rollout_failure_rate_is_near_the_closed_form_and_never_above_the_prediction_by_much():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 2), dtype=bool)
    req = np.full((1, 2), np.inf); req[0, 1] = 0.0
    rate = 0.5 / 3.6; f = _field(trav, req, rover, n_bins=2, K=2, rate=rate, recovery=1.0)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=4000, seed=7)
    p0, _, _ = S.fault_outcome_probabilities(rate, 3600.0)
    assert out["wilson_low"] <= 1 - p0 <= out["wilson_high"]
    assert out["predicted_failure"] == pytest.approx(1 - p0, abs=1e-6)

def test_rollout_can_follow_a_plan_first():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover, n_bins=3)
    out = S.rollout(f, (0, 0), 1000.0, n_runs=10, seed=1, plan_states=[(0, 0, 0), (0, 1, 1), (0, 2, 2)])
    assert out["safe"] == 10 and out["followed_plan"] is True

def test_recovery_suggestion_and_block_shapes():
    rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0); trav = np.ones((1, 3), dtype=bool)
    req = np.full((1, 3), np.inf); req[0, 2] = 0.0
    f = _field(trav, req, rover)
    s = S.recovery_suggestion(f, 0, 0, 1000.0, coarsen=4)
    assert s["action_name"] == "E" and s["target_pixel"] == [2, 6] and s["validity"] == "MODEL"
    block = S.survival_block(None, None, None, requested=False, reason="not requested")
    assert block == {"requested": False, "applied": False, "reason": "not requested", "validity": "MODEL", "model": S.SURVIVAL_MODEL_ID}
    block = S.survival_block(f, {"metrics": {"execution_failure_probability": 0.01, "min_recovery_prob": 0.99, "start_recovery_prob": 1.0}}, 0.05, requested=True)
    assert block["applied"] is True and block["beta"] == 0.05 and block["route"]["execution_failure_probability"] == 0.01
    assert block["field"]["n_states"] == f.n_states and "claim" in block and block["failure_model"]["source"].startswith("assumption:")
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** — rollout: koşu dizileri `clock (h)`, `battery`,
  `row, col`, `alive`, `done`; her adımda politika `policy[bin(clock), row, col, soc_bin(battery)]`;
  `ACTION_SAFE` → done-safe; `ACTION_NONE` → fail; hamle: τ, ρ, drenaj (maruziyet kutu değerleri), üç
  sonuç `rng.random()` ile; `clock ≥ horizon_h` → fail (horizon); rezerv altı → fail; döngü tüm
  koşular bitene ya da adım sayısı `n_bins·(K+9)`'u aşana dek (güvenlik). `plan_states` verilince önce
  plan kenarları (bekleme = bir dilim, hamle = tablodan τ/ρ) aynı arıza örneklemesiyle; arıza sonrası
  politikaya geçer; `followed_plan` bayrağı. Wilson `stress_test.wilson_interval`.
- [x] **Adım 4: yeşil**; ruff.

### Task 4: `pathfinder_4d.py` — `surv` ekseni ve `max_failure_probability`

**Files:** Modify `backend/app/pathfinder_4d.py` (`REJECTION_KEYS`, `no_path_reason_4d`, `_empty`,
`_dominated`, `_insert_label`, `astar_4d`); Test `backend/test_survival.py` (bölüm "planner").

**Interfaces:** Consumes `SurvivalField.p_safe_at`, `move_survival_factor` (duck-typed).
Produces: `astar_4d(..., survival_field=None, max_failure_probability=None)`; yanıt
`path_survival_prob: list[float] | None`, `path_recovery_prob: list[float] | None`;
`metrics.execution_failure_probability`, `min_recovery_prob`, `start_recovery_prob`,
`survival_enforced`, `edges_rejected.failure_probability`.

- [x] **Adım 1: testler**

```python
from app.pathfinder_4d import REJECTION_KEYS, astar_4d

def _toy():
    T, H, W = 6, 1, 4
    cost = np.full((T, H, W), 0.2); wait = np.full((T, H, W), 0.1); trav = np.ones((H, W), dtype=bool)
    return cost, wait, trav

def test_planner_without_a_field_is_unchanged_and_reports_none():
    cost, wait, trav = _toy(); rover = _rover(v_max_ms=1.0)
    before = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover)
    assert before["path_survival_prob"] is None and before["metrics"]["survival_enforced"] is False
    assert "failure_probability" in REJECTION_KEYS and before["metrics"]["edges_rejected"]["failure_probability"] == 0

def test_beta_without_a_field_is_refused():
    cost, wait, trav = _toy(); rover = _rover(v_max_ms=1.0)
    out = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover, max_failure_probability=0.05)
    assert out["error"] and "survival_field" in out["error"]

def test_field_without_beta_reports_execution_risk_and_beta_enforces_it():
    cost, wait, trav = _toy(); rover = _rover(p_base_w=0, p_idle_w=0, p_shadow_w=0, v_max_ms=1.0)
    req = np.full((1, 4), np.inf); req[0, 3] = 0.0
    rate = 0.5 / 3.6
    field = S.build_survival_field(trav, None, None, 3600.0, rover, np.zeros((8, 1, 4)), 1.0, 1, req, 4, rate, 1.0)
    shadow = np.zeros((6, 1, 4))
    reported = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover, shadow_cube=shadow, survival_field=field)
    assert reported["error"] is None and len(reported["path_survival_prob"]) == len(reported["path_states"])
    assert 0.0 < reported["metrics"]["execution_failure_probability"] < 1.0 and reported["metrics"]["survival_enforced"] is False
    tight = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover, shadow_cube=shadow, survival_field=field, max_failure_probability=1e-6)
    assert tight["error"] and "max_failure_probability" in tight["error"]
    loose = astar_4d(cost, wait, trav, (0, 0), (0, 3), 3600.0, 1.0, rover, shadow_cube=shadow, survival_field=field, max_failure_probability=0.9)
    assert loose["error"] is None and loose["metrics"]["survival_enforced"] is True
    assert loose["metrics"]["execution_failure_probability"] <= 0.9
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** — `REJECTION_KEYS += ("failure_probability",)`;
  cephe demetleri `(g, battery, dark, surv)`; `_dominated/_insert_label(…, surv, surv_tol)`;
  `label_of` → `(r, c, t, bkey, dkey, skey)`; `surv_of` sözlüğü; hamlede alan varsa
  `factor, p1, p2, ps1, ps2 = field.move_survival_factor(slice_index, row, col, nr, nc, battery_wh,
  travel_h, distance_m, drain_wh)` (`track` değilse `drain_wh = 0`), `new_surv = surv · factor`;
  `enforce_surv and 1 − new_surv > β + 1e-12` → `rejections["failure_probability"] += 1; continue`.
  Başlangıç: `start_ps = field.p_safe_at(0, *start, battery0)`; β verilip `1 − start_ps > β` →
  `_empty(f"Start … optimal recovery policy fails with probability {1-start_ps:.4f} > β")`.
  Çıktı listeleri `[surv_of[label]]`, `[field.p_safe_at(t, r, c, battery)]`.
- [x] **Adım 4: yeşil**; mevcut `test_pathfinder_4d.py` yeşil (`python -m pytest test_pathfinder_4d.py -q -p no:cacheprovider`).

### Task 5: `stress_test.py` — SHERPA arıza olayı

**Files:** Modify `backend/app/stress_test.py` (`Perturbations`, `sample_perturbations`, `RunResults`,
`simulate_runs`, `summarize_runs`); Modify `backend/app/main.py` (`PerturbationOverrides`); Test
`backend/test_stress_test.py` (ek).

**Produces:** `Perturbations.fault_rate_per_km: float = 0.0`, `fault_recovery_h: float = 10.0`;
`samples["fault_positions_m"] (n, F)` (NaN dolgu), `samples["fault_count"] (n,)`;
`RunResults.fault_count`, `RunResults.fault_hold_h`; özet `faults: {rate_per_km, recovery_h,
runs_with_fault, mean_faults, mean_hold_h, source}` ve `metrics.fault_hold_h`.

- [x] **Adım 1: testler**

```python
def test_no_fault_rate_keeps_sherpa_bit_identical(legs, sky, rover):   # mevcut fixture'lar
    a = stress_test_route(legs, sky, rover, n_runs=200, seed=3)
    b = stress_test_route(legs, sky, rover, n_runs=200, seed=3, perturbations=dataclass_replace(SHERPA_DEFAULTS, fault_rate_per_km=0.0))
    assert a["rates"] == b["rates"] and b["faults"]["runs_with_fault"] == 0

def test_fault_count_is_poisson_in_route_distance(legs, sky, rover):
    p = dataclass_replace(SHERPA_DEFAULTS, fault_rate_per_km=2.0, fault_recovery_h=0.5)
    samples = sample_perturbations(np.random.default_rng(0), 5000, p, 1.0, legs.planned_duration_h, route_distance_m=legs.distance_m.sum())
    expected = 2.0 * legs.distance_m.sum() / 1000.0
    assert samples["fault_count"].mean() == pytest.approx(expected, rel=0.1)
    assert np.nanmax(samples["fault_positions_m"]) <= legs.distance_m.sum()

def test_a_fault_holds_the_rover_for_the_recovery_time(legs, sky, rover):
    p = dataclass_replace(SHERPA_DEFAULTS, start_delay_sigma_h=0.0, initial_soc_sigma=0.0, power_draw_sigma=0.0, speed_sigma=0.0, fault_rate_per_km=50.0, fault_recovery_h=2.0)
    out = stress_test_route(legs, sky, rover, n_runs=20, seed=1, perturbations=p)
    assert out["faults"]["runs_with_fault"] == 20 and out["faults"]["mean_hold_h"] >= 2.0
    assert out["metrics"]["duration_h"]["p50"] >= out["nominal"]["duration_h"] + 2.0
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** — `sample_perturbations(…, route_distance_m=0.0)`:
  `count = rng.poisson(rate/1000 · L)`, `F = max(1, count.max())`, konumlar `rng.uniform(0, L,
  (n, F))` sıralı, `count`'un ötesi NaN. `simulate_runs`: kümülatif mesafe `d0`; hamle ayağında
  `first = Σ (pos ≥ d0) & (pos < d0 + ρ/2)`, `second = Σ (pos ≥ d0 + ρ/2) & (pos < d0 + ρ)`; `first·R`
  kalkış öncesi kaynak hücrede (`depart += hold`, drenaj `housekeeping(exposure_mean) · m_power −
  solar`), `second·R` varış sonrası hedef hücrede; `fault_hold_h` toplanır; karanlık saat kuralı
  bekleme gibi işler. `main.PerturbationOverrides`: `fault_rate_per_km (0–50)`, `fault_recovery_h (0–72)`.
- [x] **Adım 4: yeşil**; `test_stress_test.py` tamamı yeşil.

### Task 6: `main.py` — istek alanları, alan kurucu, dört uç; `test_survival_api.py`

**Files:** Modify `backend/app/main.py`; Create `backend/test_survival_api.py`.

**Produces:**
- `Plan4DRequest`: `max_failure_probability: Optional[float] (gt=0, lt=1)`, `report_survival: bool = False`,
  `failure_rate_per_km: Optional[float] (ge=0, le=50)`, `recovery_hours: Optional[float] (gt=0, le=72)`,
  `survival_soc_bins: int = 20 (8–40)`, `survival_safe_set: str = "leg"` (`^(leg|haven)$`),
  `survival_horizon_hours: Optional[float] (gt=0, le=168)`.
- `_survival_field_for_plan(grids_for_plan, rover_id, rover, geometry, coarsen, start_utc, slice_hours,
  n_slices, shadow_series, shadow_provenance, goal_coarse, fastest_hours, options) -> (SurvivalField | None, info dict)`
- plan-4d yanıtı: `survival` bloğu, `path_survival_prob`, `path_recovery_prob`.
- `ReplanRequest.recovery_policy: bool = False` (+ `survival_horizon_hours`, `failure_rate_per_km`,
  `recovery_hours` isteğe bağlı) → `recovery_suggestion`.
- `GET /api/cell-telemetry?survival=true&goal_row&goal_col&soc_pct&t_hours&survival_horizon_hours&failure_rate_per_km&recovery_hours&safe_set`
  → `survival`, `survival_model`.
- `GET /api/survival` (karar 10).

- [x] **Adım 1: testler** (`test_plan_4d_endpoint.py`'nin fixture kalıbı; 16 × 16, coarsen 4)

```python
def test_plan_4d_without_survival_says_not_requested(client):
    r = client.post("/api/plan-4d", json=_body()); assert r.status_code == 200
    s = r.json()["survival"]; assert s["requested"] is False and s["applied"] is False and s["validity"] == "MODEL"
    assert r.json()["path_survival_prob"] is None

def test_plan_4d_reports_survival_when_asked(client):
    r = client.post("/api/plan-4d", json=_body(report_survival=True)); assert r.status_code == 200, r.text
    p = r.json(); s = p["survival"]
    assert s["requested"] and not s["applied"] and s["failure_model"]["rate_per_km"] == 0.2 and s["failure_model"]["source"].startswith("assumption:")
    assert s["safe_set"] == "leg" and s["field"]["n_states"] > 0 and s["shadow_model"]["model"] == "static"
    assert len(p["path_survival_prob"]) == len(p["path_states"]) and 0 <= s["route"]["execution_failure_probability"] <= 1

def test_plan_4d_enforces_beta(client):
    ok = client.post("/api/plan-4d", json=_body(max_failure_probability=0.5)); assert ok.status_code == 200, ok.text
    assert ok.json()["survival"]["applied"] and ok.json()["metrics"]["execution_failure_probability"] <= 0.5
    tight = client.post("/api/plan-4d", json=_body(max_failure_probability=1e-9, failure_rate_per_km=5.0))
    assert tight.status_code == 404 and "max_failure_probability" in tight.json()["detail"]

def test_plan_4d_validates_survival_fields(client):
    for bad in ({"max_failure_probability": 1.0}, {"survival_safe_set": "goal"}, {"survival_horizon_hours": 500}, {"survival_soc_bins": 4}):
        assert client.post("/api/plan-4d", json=_body(**bad)).status_code == 422

def test_cell_telemetry_survival_block(client):
    r = client.get("/api/cell-telemetry", params={"row": 2, "col": 2}); assert r.json()["survival"] is None
    r = client.get("/api/cell-telemetry", params={"row": 2, "col": 2, "start_utc": "2026-09-01T00:00:00", "survival": "true", "goal_row": 13, "goal_col": 13})
    assert r.status_code == 200, r.text; s = r.json()["survival"]
    assert 0.0 <= s["p_safe"] <= 1.0 and s["best_action_name"] in S.ACTION_NAMES + ("safe", "none") and r.json()["survival_model"]["model"] == S.SURVIVAL_MODEL_ID

def test_replan_recovery_suggestion(client):
    body = {"current": {"row": 2, "col": 2}, "goal": {"row": 13, "col": 13}, "state": {"actual_soc": 0.9}, "force": True, "utc": "2026-09-01T00:00:00", "recovery_policy": True}
    r = client.post("/api/replan", json=body); assert r.status_code == 200, r.text
    s = r.json()["recovery_suggestion"]; assert s["action_name"] and s["soc_frac"] == 0.9 and s["validity"] == "MODEL"
    body.pop("recovery_policy"); assert client.post("/api/replan", json=body).json()["recovery_suggestion"] is None

def test_survival_layer_json_and_binary(client):
    params = {"start_utc": "2026-09-01T00:00:00", "goal_row": 13, "goal_col": 13, "horizon_hours": 6}
    r = client.get("/api/survival", params=params); assert r.status_code == 200, r.text
    j = r.json(); assert j["grid"]["rows"] == 4 and "p_safe" in j["fields"] and j["survival_model"]["validity"] == "MODEL"
    b = client.get("/api/survival", params={**params, "format": "f32", "field": "p_safe"})
    assert b.status_code == 200 and b.headers["X-Layer-Validity"] == "MODEL" and len(b.content) == 4 * 4 * 4
    assert client.get("/api/survival", params={"start_utc": "2026-09-01T00:00:00"}).status_code == 422   # leg needs a goal
```

- [x] **Adım 2: kırmızı** · **Adım 3: uygulama** — `_survival_field_for_plan`: DP ufku =
  `survival_horizon_hours` ya da `n_slices·slice + R + max(fastest_hours, slice)`; `m =
  auto_slices_per_bin(ceil(ufuk/slice), H'·W', K, MAX)`; `n_total_slices = n_bins · m`; gölge
  serisi = plan serisi + `build_shadow_series(base, metadata, n_total − n_slices, slice, start +
  n_slices·slice)` (statikse `base` tekrarı); `coarsen_grid` → `bin_shadow_series`; haven maskesi
  `_coarse_time_to_haven`'dan (`coarse_safe`, None olabilir); `safe_soc_requirement`; anahtar
  `(processed_dir|id(grids), rover_id, coarsen, start_utc, slice, m, n_bins, K, goal, safe_set, α, R)`;
  `cached_survival_field`. 404 metnine: `f" Chance constraint: {n} moves were refused because the
  execution failure probability would exceed max_failure_probability={β}; the optimal recovery policy
  from the start block succeeds with probability {p:.4f}."`. cell-telemetry ve replan aynı kurucuyu
  hedefle çağırır (kısa ufuk varsayılanı 24 h); `GET /api/survival` `/api/safe-haven` kalıbı.
- [x] **Adım 4: yeşil**; `test_plan_4d_endpoint.py`, `test_safe_haven.py`, `test_main*.py` yeşil.

### Task 7: `test_survival_real_grid.py` (skip-korumalı)

**Files:** Create `backend/test_survival_real_grid.py`.

- [x] **Adım 1: testler**

```python
needs_real_inputs = pytest.mark.skipif(not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)), reason="…")

@needs_real_inputs
def test_standard_routes_are_unchanged_without_beta(client):
    for body, moves in ((LPR1_DAY, 41), (NIGHT, 116), (VIPER_SHORT, 8)):
        r = client.post("/api/plan-4d", json=body); assert r.status_code == 200, r.text
        assert r.json()["metrics"]["move_steps"] == moves and r.json()["survival"]["requested"] is False

@needs_real_inputs
def test_beta_bounds_the_execution_risk_on_the_day_route(client):
    r = client.post("/api/plan-4d", json={**LPR1_DAY, "max_failure_probability": 0.05})
    assert r.status_code in (200, 404), r.text
    if r.status_code == 200:
        m = r.json()["metrics"]; assert m["execution_failure_probability"] <= 0.05 and m["min_recovery_prob"] >= 0.0
        assert r.json()["survival"]["field"]["n_states"] <= S.MAX_SURVIVAL_STATES

@needs_real_inputs
def test_viper_haven_set_has_positive_p_safe_in_may_2027(client):
    r = client.get("/api/survival", params={"start_utc": "2027-05-30T00:00:00", "rover_id": "nasa_viper", "safe_set": "haven", "horizon_hours": 24, "soc_pct": 1.0})
    assert r.status_code == 200, r.text and r.json()["summary"]["fraction_above_0_5"] > 0.0
```

- [x] **Adım 2: koştur** (`python -m pytest test_survival_real_grid.py -q -p no:cacheprovider`; gerçek girdiler diskte).

### Task 8: `scripts/recovery_policy_report.py` + gerçek koşum

**Files:** Create `scripts/recovery_policy_report.py`; Output `docs/research/recovery_policy_report.md`.

- [x] **Adım 1: betik** — `moonplanbench_runner.py` kalıbı (`_fmt` ondalık virgül, `--json`,
  `--from-json`, `--n-runs 1000`, `--seed 0`, `--skip-sherpa`, `--max-states`, `--betas 0.10,0.05,0.02`,
  `--rates 0,0.2,0.5`). Bölümler: (1) formülasyon + Lamarre farkları (`LAMARRE_QUOTED`); (2) alan
  istatistikleri (üç çift; α süpürmesi; leg/haven; kutu m; süre; `P_safe` dağılımı başlangıç SOC'de);
  (3) β süpürmesi (hamle/varış/min SOC/yürütme riski/örtüşme/ret sayısı; 404 gerekçesi); (4)
  rollout (politika; plan + politika) ve SHERPA arıza olaylı — tahmin vs gerçekleşen, Wilson;
  konservatiflik satırı ("tutuyor/tutmuyor"); (5) kurtarma önerisi örnekleri (Ay gecesi çiftinde
  başlangıçtan ve rotanın ortasındaki bir durumdan, `/api/replan`); (6) iddia sınırı + sunum cümlesi.
- [x] **Adım 2: koşum** (arka planda, `> log 2>&1`; tam paketle eşzamanlı değil):
  `python -u scripts/recovery_policy_report.py --json <scratch>/recovery.json` sonra `--from-json`.
- [x] **Adım 3: raporu oku, sayıları spec'in "Uygulama sırasında bulunanlar" bölümüne yaz.**

### Task 9: Belgeler, doğrulama, tek commit, hafıza

- [x] README satırı (Veri/özellik bölümü, D2 satırının altı).
- [x] Sözleşme eki `docs/frontend/3b-veri-sozlesmesi.md` (C4 ekinin ardı, "Değişmeyenler" öncesi).
- [x] Araştırma belgesi B1 ✅ + "> Yapıldı (…)" bloğu (D2 kalıbı).
- [x] Spec "Uygulama sırasında bulunanlar ve ölçümler".
- [x] `ruff check` yeni dosyalar; tam paket `cd backend && python -m pytest -q -p no:cacheprovider`
  (arka planda, log dosyasına) → sayı commit mesajına.
- [x] Tek commit (mesaj D2 kalıbı; eş-yazar yok); hafıza `feature-matrix-workflow.md` + `MEMORY.md`.
