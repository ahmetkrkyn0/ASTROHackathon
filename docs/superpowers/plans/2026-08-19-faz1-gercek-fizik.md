# Faz 1 — Gerçek Fizik ve Veri Implementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LunaPath'in iki sentetik katmanını (termal, gölge) gerçek fiziğe bağlamak ve maliyet motorundaki gölge terimi ölçek hatasını düzeltmek.

**Architecture:** Mevcut `backend/app/` çekirdeği bozulmadan genişletiliyor. Termal üretim bir **adaptör protokolü** arkasına alınıyor (`thermal_model.py`) — böylece `heat1d` API'si beklenenden farklı çıkarsa plan bloke olmuyor, sentetik model fallback olarak kalıyor. Gölge, topografik ufuk açısı (`horizon.py`) ile güneş efemerisinin (`ephemeris.py`) birleşiminden (`illumination.py`) üretiliyor; SPICE gerektiren kısım saf geometriden ayrılıyor ki testler çekirdek dosyası olmadan koşabilsin.

**Tech Stack:** Python 3.11+ · NumPy 2.2.1 · SciPy 1.15.0 · rasterio 1.4.3 · pytest · heat1d (MIT) · spiceypy (MIT)

**Spec:** [`docs/research/ENTEGRASYON_TEKNOLOJILERI.md`](../../research/ENTEGRASYON_TEKNOLOJILERI.md) §1.1–1.4, "Kritik notlar → gölge terimi pratikte ölü"

**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md) — **Global Constraints bölümü bu planın her görevi için geçerlidir.**

---

## Faz kapsamı

| Görev | Ne | Süre |
|---|---|---|
| 1 | pytest altyapısı + gölge ölçek hatasını yakalayan başarısız test | 0.5 gün |
| 2 | `f_shadow_cell` + `compute_cost_grid` düzeltmesi | 0.5 gün |
| 3 | `thermal_model.py` — protokol + `SyntheticModel` adaptörü | 0.5 gün |
| 4 | `Heat1DModel` + `thermal_grid.py` delegasyonu | 1.5 gün |
| 5 | `horizon.py` — topografik ufuk açısı haritası | 1.5 gün |
| 6 | `ephemeris.py` — güneş azimut/yükseklik geometrisi | 1 gün |
| 7 | `illumination.py` — `I(x, y, t)` aydınlanma alanı | 0.5 gün |
| 8 | P1 hattı entegrasyonu + `metadata.json` `layer_validity` | 1 gün |

---

### Task 1: pytest altyapısı ve gölge ölçek hatasının kanıtı

Spec'in "Kritik notlar" bölümü, `compute_cost_grid`'in `f_shadow`'a **kümülatif** yerine **tek kenarlık** gölge süresi beslediğini tespit etti. Bu görev o hatayı bir teste dönüştürüyor. Test **başarısız kalacak** — Task 2 onu geçirecek.

**Files:**
- Modify: `backend/requirements.txt`
- Test: `backend/test_shadow_scale.py` (create)

**Interfaces:**
- Consumes: `app.cost_engine.compute_cost_grid`, `app.constants.get_rover` (mevcut)
- Produces: `backend/test_shadow_scale.py::test_fully_shadowed_cell_costs_full_shadow_weight` — Task 2 bunu geçirmek zorunda

- [ ] **Step 1: `pytest`'i bağımlılıklara ekle**

`backend/requirements.txt` dosyasının sonuna ekle:

```
pytest==8.3.4
```

Kur:

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 2: Başarısız testi yaz**

`backend/test_shadow_scale.py` oluştur:

```python
"""Shadow term scale regression tests.

The AHP weight for shadow is 0.142 (LPR-1). A fully shadowed cell must
therefore cost ~0.142 more than an identical fully lit cell. Before the
Task 2 fix, compute_cost_grid fed f_shadow a SINGLE-EDGE duration
(0.111 h) normalised against h_max_shadow_h (50 h), producing a
contribution of ~0.00005 -- i.e. the criterion was effectively dead.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_engine import compute_cost_grid

RESOLUTION_M = 80.0
# -120 C keeps the cell traversable (> -150 C) while making f_thermal ~1.0,
# so the total cost stays well above the max(0.01, cost) clamp.
THERMAL_C = -120.0


def _cost_for_shadow_ratio(ratio: float) -> float:
    shape = (1, 1)
    slope = np.zeros(shape, dtype=np.float64)
    thermal = np.full(shape, THERMAL_C, dtype=np.float64)
    shadow = np.full(shape, ratio, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    grid = compute_cost_grid(
        slope, thermal, shadow, RESOLUTION_M, traversable=traversable
    )
    return float(grid[0, 0])


def test_fully_shadowed_cell_costs_full_shadow_weight():
    """shadow_ratio 0 -> 1 must move the cell cost by ~w_shadow."""
    w_shadow = float(get_rover()["w_shadow"])
    delta = _cost_for_shadow_ratio(1.0) - _cost_for_shadow_ratio(0.0)
    assert delta == pytest.approx(w_shadow, rel=0.05)


def test_shadow_cost_is_monotonic():
    """More shadow must never cost less."""
    costs = [_cost_for_shadow_ratio(r) for r in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert costs == sorted(costs)
    assert costs[-1] > costs[0]
```

- [ ] **Step 3: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_shadow_scale.py -v`

Expected: `test_fully_shadowed_cell_costs_full_shadow_weight` **FAIL** —
`assert 5.0e-05 == 0.142 ± 7.1e-03`. Bu, spec'te tarif edilen hatanın kanıtıdır.
`test_shadow_cost_is_monotonic` geçebilir (fark çok küçük ama pozitif).

- [ ] **Step 4: Mevcut testlerin bozulmadığını doğrula**

Run:

```bash
cd backend && pytest -v --ignore=test_shadow_scale.py
python test_cost_engine.py
python test_traversability.py
```

Expected: pytest tamamı PASS; iki script çıkış kodu 0.

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/test_shadow_scale.py
git commit -m "test: add failing regression test for dead shadow cost term"
```

---

### Task 2: `f_shadow_cell` — gölge terimi ölçek düzeltmesi

`f_shadow(H_hours)` kümülatiftir ve **yola bağlıdır** — doğru yeri statik maliyet grid'i değil, planlayıcının durum bilgili genişletmesidir. Statik grid için ayrı, hücre-yerel bir penaltı fonksiyonu tanımlanıyor. `f_shadow` **değiştirilmiyor** (`total_edge_cost` onu doğru kullanıyor).

**Files:**
- Modify: `backend/app/cost_engine.py` (yeni `f_shadow_cell`; `compute_cost_grid` içindeki çağrı)
- Test: `backend/test_shadow_scale.py` (genişlet)

**Interfaces:**
- Consumes: `_SHADOW_LAMBDA` (mevcut modül sabiti, 3.0)
- Produces: `f_shadow_cell(shadow_ratio: float) -> float` — MRU [0, 1] döner; Faz 2 `ShadowLayer` bunu kullanır

- [ ] **Step 1: `f_shadow_cell` için başarısız testleri yaz**

`backend/test_shadow_scale.py` dosyasının başındaki import satırını değiştir:

```python
from app.cost_engine import compute_cost_grid, f_shadow_cell
```

Dosyanın sonuna ekle:

```python
def test_f_shadow_cell_endpoints():
    """Fully lit -> 0, fully shadowed -> 1 (MRU normalisation)."""
    assert f_shadow_cell(0.0) == pytest.approx(0.0, abs=1e-12)
    assert f_shadow_cell(1.0) == pytest.approx(1.0, abs=1e-12)


def test_f_shadow_cell_midpoint_matches_exponential_shape():
    """Same exponential shape as f_shadow: (e^(3r) - 1) / (e^3 - 1)."""
    assert f_shadow_cell(0.5) == pytest.approx(0.182428, abs=1e-6)


def test_f_shadow_cell_clamps_out_of_range_input():
    assert f_shadow_cell(-0.3) == pytest.approx(0.0, abs=1e-12)
    assert f_shadow_cell(1.7) == pytest.approx(1.0, abs=1e-12)
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_shadow_scale.py -v`

Expected: FAIL — `ImportError: cannot import name 'f_shadow_cell' from 'app.cost_engine'`

- [ ] **Step 3: `f_shadow_cell`'i uygula**

`backend/app/cost_engine.py` içinde, mevcut `f_shadow` fonksiyonunun **hemen altına** ekle:

```python
def f_shadow_cell(shadow_ratio: float) -> float:
    """Cell-level shadow penalty in MRU [0, 1].

    Unlike :func:`f_shadow`, which takes CUMULATIVE shadow hours and is
    therefore path-dependent, this is a per-cell proxy for the static cost
    grid. It applies the same exponential shape directly to the shadow
    ratio so a fully shadowed cell costs 1.0 and a fully lit cell 0.0.

    Feeding f_shadow a single-edge duration (~0.11 h) normalised against
    h_max_shadow_h (50 h) collapsed the term to ~3e-4, which made the
    0.142-weighted shadow criterion irrelevant to planning.
    """
    r = min(1.0, max(0.0, float(shadow_ratio)))
    return (math.exp(_SHADOW_LAMBDA * r) - 1.0) / (math.exp(_SHADOW_LAMBDA) - 1.0)
```

- [ ] **Step 4: `compute_cost_grid`'i yeni fonksiyona bağla**

`backend/app/cost_engine.py` içinde `compute_cost_grid` gövdesindeki döngüde şu üç satırı sil:

```python
        local_shadow_h = edge_shadow_hours(shadow_ratio, float(slope_deg), resolution_m, rover_cfg)
        if math.isinf(local_shadow_h):
            continue
```

ve maliyet ifadesindeki gölge satırını

```python
            + resolved["w_shadow"] * f_shadow(local_shadow_h, rover_cfg)
```

şununla değiştir:

```python
            + resolved["w_shadow"] * f_shadow_cell(shadow_ratio)
```

Aynı fonksiyonun docstring'inde şu satırı:

```
    - the shadow term uses local shadow ratio multiplied by the traversal time
      of one nominal step.
```

şununla değiştir:

```
    - the shadow term uses ``f_shadow_cell`` on the local shadow ratio; the
      cumulative ``f_shadow`` belongs to the path-dependent planner, not to
      this static grid.
```

- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_shadow_scale.py -v`

Expected: 5 test PASS. Özellikle `test_fully_shadowed_cell_costs_full_shadow_weight` artık `delta ≈ 0.142`.

- [ ] **Step 6: Regresyon — tüm suite**

Run:

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
```

Expected: hepsi PASS / çıkış kodu 0. `test_cost_engine.py` `f_shadow`'u doğrudan test ediyor ve o fonksiyon değişmedi, dolayısıyla etkilenmemeli.

- [ ] **Step 7: Commit**

```bash
git add backend/app/cost_engine.py backend/test_shadow_scale.py
git commit -m "fix: use cell-local shadow penalty in static cost grid

f_shadow expects cumulative shadow hours normalised against
h_max_shadow_h (50 h). compute_cost_grid was feeding it a single-edge
duration (~0.11 h), collapsing the term to ~3e-4 and making the
0.142-weighted shadow criterion irrelevant. Adds f_shadow_cell for the
static grid; f_shadow stays unchanged for path-dependent edge costs."
```

---

### Task 3: `thermal_model.py` — adaptör protokolü ve sentetik model

`heat1d`'nin gerçek API'si README ile eşleşmeyebilir (spec §1.1 sürüm tuzağı). Bu görev, termal üretimi bir protokolün arkasına alarak Task 4'ün riskini izole ediyor.

**Files:**
- Create: `backend/app/thermal_model.py`
- Test: `backend/test_thermal_model.py` (create)

**Interfaces:**
- Consumes: `app.thermal_grid.generate_thermal_grid(elevation, slope, aspect, resolution_m) -> np.ndarray` (mevcut, °C)
- Produces:
  - `SurfaceThermalModel` protokolü: `name: str`, `validity: str`, `surface_temperature_c(slope_deg, aspect_deg, lat_deg) -> np.ndarray`
  - `SyntheticModel(elevation, resolution_m)` — mevcut sentetik hesabı sarar, `validity == "SYNTHETIC"`
  - `build_thermal_grid(model, slope_grid, aspect_grid, lat_deg) -> np.ndarray`

- [ ] **Step 1: Başarısız testi yaz**

`backend/test_thermal_model.py` oluştur:

```python
"""Thermal model adapter tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.thermal_model import SyntheticModel, build_thermal_grid


def _fixture_grids():
    rng = np.random.default_rng(42)
    elevation = rng.uniform(-500.0, 500.0, size=(8, 8))
    slope = rng.uniform(0.0, 20.0, size=(8, 8))
    aspect = rng.uniform(0.0, 360.0, size=(8, 8))
    return elevation, slope, aspect


def test_synthetic_model_declares_synthetic_validity():
    elevation, _, _ = _fixture_grids()
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    assert model.validity == "SYNTHETIC"
    assert model.name == "synthetic-elevation-aspect"


def test_build_thermal_grid_returns_celsius_float32_of_matching_shape():
    elevation, slope, aspect = _fixture_grids()
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    out = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert out.shape == slope.shape
    assert out.dtype == np.float32
    # Lunar south-pole surface temperatures live well inside this envelope.
    assert np.nanmin(out) >= -250.0
    assert np.nanmax(out) <= 130.0


def test_synthetic_model_matches_legacy_generate_thermal_grid():
    """The adapter must not change existing numbers."""
    from app.thermal_grid import generate_thermal_grid

    elevation, slope, aspect = _fixture_grids()
    legacy = generate_thermal_grid(elevation, slope, aspect, 80.0)
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    adapted = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert np.allclose(legacy, adapted, equal_nan=True)
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_thermal_model.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.thermal_model'`

- [ ] **Step 3: `thermal_model.py`'yi uygula**

`backend/app/thermal_model.py` oluştur:

```python
"""Surface thermal model adapters.

LunaPath consumes surface temperature as a (H, W) float32 grid in degrees
Celsius. Where that grid comes from is a swappable decision:

- ``SyntheticModel``  -- the original elevation/aspect heuristic (validity SYNTHETIC)
- ``Heat1DModel``     -- Hayne's 1-D regolith diffusion model  (validity MODEL)

Keeping both behind one protocol means an unavailable or API-drifted heat1d
release degrades to the synthetic baseline instead of blocking the pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from .thermal_grid import generate_thermal_grid


@runtime_checkable
class SurfaceThermalModel(Protocol):
    """Produces surface temperature in degrees Celsius."""

    name: str
    validity: str  # "MEASURED" | "DERIVED" | "MODEL" | "SYNTHETIC"

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray: ...


class SyntheticModel:
    """Legacy elevation + aspect heuristic. Kept as an explicit baseline."""

    name = "synthetic-elevation-aspect"
    validity = "SYNTHETIC"

    def __init__(self, elevation: np.ndarray, resolution_m: float) -> None:
        self._elevation = np.asarray(elevation, dtype=np.float64)
        self._resolution_m = float(resolution_m)

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray:
        # lat_deg is unused: the synthetic heuristic has no latitude term.
        return generate_thermal_grid(
            self._elevation,
            np.asarray(slope_deg, dtype=np.float64),
            np.asarray(aspect_deg, dtype=np.float64),
            self._resolution_m,
        )


def build_thermal_grid(
    model: SurfaceThermalModel,
    slope_grid: np.ndarray,
    aspect_grid: np.ndarray,
    lat_deg: float,
) -> np.ndarray:
    """Run *model* and normalise its output to (H, W) float32 Celsius."""
    out = model.surface_temperature_c(slope_grid, aspect_grid, lat_deg)
    out = np.asarray(out, dtype=np.float32)
    if out.shape != np.asarray(slope_grid).shape:
        raise ValueError(
            f"{model.name} returned shape {out.shape}, "
            f"expected {np.asarray(slope_grid).shape}"
        )
    return out
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_thermal_model.py -v`

Expected: 3 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/thermal_model.py backend/test_thermal_model.py
git commit -m "feat: add swappable surface thermal model adapter"
```

---

### Task 4: `Heat1DModel` — gerçek termal fizik

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/thermal_model.py`
- Test: `backend/test_thermal_model.py` (genişlet)

**Interfaces:**
- Consumes: `SurfaceThermalModel` protokolü, `build_thermal_grid` (Task 3)
- Produces: `Heat1DModel(n_slope_bins=13, n_aspect_bins=16)` — `validity == "MODEL"`; `available() -> bool` sınıf metodu; `_lookup_table(lat_deg) -> np.ndarray` (n_slope_bins, n_aspect_bins) °C

- [ ] **Step 1: heat1d'yi kur ve API'sini doğrula**

```bash
pip install heat1d
python -c "import inspect, heat1d; print(inspect.signature(heat1d.Model.__init__))"
```

Çıktıdaki imzada `slope` ve `slope_az` parametreleri **yoksa**, GitHub `main`'den kur:

```bash
pip install --force-reinstall git+https://github.com/phayne/heat1d
python -c "import inspect, heat1d; print(inspect.signature(heat1d.Model.__init__))"
```

İkisi de yoksa: `Heat1DModel.available()` `False` dönecek ve `SyntheticModel` kullanılmaya devam edecek. **Bu bir başarısızlık değil** — Task 8'de `layer_validity` alanı `"SYNTHETIC"` olarak kalır ve durum dürüstçe raporlanır. Bulduğun imzayı bir sonraki adıma not et.

`backend/requirements.txt`'e ekle (imza doğrulandıysa):

```
heat1d==0.3.1
```

*(Eğer GitHub `main` gerekiyorsa satır yerine `heat1d @ git+https://github.com/phayne/heat1d` yaz.)*

- [ ] **Step 2: Başarısız testleri yaz**

`backend/test_thermal_model.py` sonuna ekle:

```python
from app.thermal_model import Heat1DModel


def test_heat1d_model_declares_model_validity():
    model = Heat1DModel()
    assert model.validity == "MODEL"
    assert model.name.startswith("heat1d")


def test_heat1d_lookup_table_shape_and_bounds():
    """A (slope, aspect) temperature table covering the configured bins."""
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    model = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    table = model._lookup_table(lat_deg=-88.5)
    assert table.shape == (4, 4)
    # Lunar polar surface temperatures: PSR floors ~ -250 C, sunlit peaks < 130 C
    assert np.nanmin(table) >= -250.0
    assert np.nanmax(table) <= 130.0


def test_heat1d_binning_is_deterministic_and_covers_grid():
    """Binned lookup must map every cell and be reproducible."""
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    _, slope, aspect = _fixture_grids()
    model = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    first = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    second = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()
```

- [ ] **Step 3: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_thermal_model.py -v`

Expected: FAIL — `ImportError: cannot import name 'Heat1DModel'`

- [ ] **Step 4: `Heat1DModel`'i uygula**

`backend/app/thermal_model.py` sonuna ekle:

```python
_SLOPE_MAX_DEG_FOR_TABLE = 30.0


class Heat1DModel:
    """Hayne (2017) 1-D regolith diffusion model, evaluated on a
    (slope x aspect) lookup table and sampled per cell.

    Running heat1d once per grid cell is wasteful: at the lunar south pole
    latitude is effectively constant across our 40 km window, so surface
    temperature depends almost entirely on local slope and azimuth. A
    coarse table plus nearest-bin lookup captures that at a fraction of the
    cost and is deterministic.
    """

    validity = "MODEL"

    def __init__(self, n_slope_bins: int = 13, n_aspect_bins: int = 16) -> None:
        self.n_slope_bins = int(n_slope_bins)
        self.n_aspect_bins = int(n_aspect_bins)
        self.name = f"heat1d-lut-{self.n_slope_bins}x{self.n_aspect_bins}"
        self._cache: dict[float, np.ndarray] = {}

    @staticmethod
    def available() -> bool:
        """True when heat1d is importable with a slope-capable Model."""
        try:
            import inspect

            import heat1d
        except Exception:
            return False
        try:
            params = inspect.signature(heat1d.Model.__init__).parameters
        except (TypeError, ValueError):
            return False
        return "slope" in params

    def _lookup_table(self, lat_deg: float) -> np.ndarray:
        """(n_slope_bins, n_aspect_bins) peak surface temperature in Celsius."""
        key = round(float(lat_deg), 4)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        import heat1d
        import planets

        slopes = np.linspace(0.0, _SLOPE_MAX_DEG_FOR_TABLE, self.n_slope_bins)
        aspects = np.linspace(0.0, 360.0, self.n_aspect_bins, endpoint=False)
        table = np.empty((self.n_slope_bins, self.n_aspect_bins), dtype=np.float64)

        for i, slope_deg in enumerate(slopes):
            for j, aspect_deg in enumerate(aspects):
                model = heat1d.Model(
                    planet=planets.Moon,
                    lat=np.deg2rad(lat_deg),
                    ndays=1,
                    slope=np.deg2rad(slope_deg),
                    slope_az=np.deg2rad(aspect_deg),
                )
                model.run()
                surface_k = np.asarray(model.T)[:, 0]
                # Peak diurnal surface temperature is the planning-relevant
                # value: it bounds the warmest state the rover must survive.
                table[i, j] = float(np.nanmax(surface_k)) - 273.15

        table = np.clip(table, -250.0, 130.0)
        self._cache[key] = table
        return table

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray:
        table = self._lookup_table(lat_deg)
        slope_arr = np.asarray(slope_deg, dtype=np.float64)
        aspect_arr = np.asarray(aspect_deg, dtype=np.float64)

        slope_clipped = np.clip(
            np.nan_to_num(slope_arr, nan=0.0), 0.0, _SLOPE_MAX_DEG_FOR_TABLE
        )
        si = np.rint(
            slope_clipped / _SLOPE_MAX_DEG_FOR_TABLE * (self.n_slope_bins - 1)
        ).astype(np.int64)

        aspect_wrapped = np.mod(np.nan_to_num(aspect_arr, nan=0.0), 360.0)
        ai = np.mod(
            np.rint(aspect_wrapped / 360.0 * self.n_aspect_bins).astype(np.int64),
            self.n_aspect_bins,
        )

        return table[si, ai]
```

- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_thermal_model.py -v`

Expected: 6 test PASS (heat1d yoksa 3'ü SKIP — bu kabul edilebilir sonuçtur).

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/thermal_model.py backend/test_thermal_model.py
git commit -m "feat: add heat1d-backed surface thermal model with slope/aspect LUT"
```

---

### Task 5: `horizon.py` — topografik ufuk açısı haritası

**Files:**
- Create: `backend/app/horizon.py`
- Test: `backend/test_horizon.py` (create)

**Interfaces:**
- Consumes: yalnızca NumPy
- Produces: `horizon_map(elevation, resolution_m, n_azimuth=72, max_range_m=10000.0, moon_radius_m=1737400.0, curvature=True) -> np.ndarray` — `(n_azimuth, H, W)` float32, **derece**. Azimut konvansiyonu: indeks `i` → `360 * i / n_azimuth` derece, **0 = Kuzey (satır azalan yön), 90 = Doğu (sütun artan yön)** — `make_aspect_grid` ile aynı. Task 7 bunu tüketir.

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_horizon.py` oluştur:

```python
"""Topographic horizon map tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.horizon import horizon_map

RES_M = 80.0


def test_flat_terrain_without_curvature_has_zero_horizon():
    elevation = np.zeros((12, 12), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=400.0, curvature=False)
    assert hz.shape == (4, 12, 12)
    interior = hz[:, 2:-2, 2:-2]
    assert np.allclose(interior, 0.0, atol=1e-6)


def test_flat_terrain_with_curvature_has_negative_horizon():
    """Sphere curvature drops distant ground below the local horizontal."""
    elevation = np.zeros((12, 12), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=True)
    interior = hz[:, 2:-2, 2:-2]
    assert (interior < 0.0).all()


def test_east_facing_ramp_gives_ten_degree_horizon_to_the_east():
    """elev = col * res * tan(10 deg) -> looking east, horizon is 10 deg."""
    cols = np.arange(16, dtype=np.float64)
    elevation = np.tile(cols * RES_M * np.tan(np.radians(10.0)), (16, 1))
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=False)
    # n_azimuth=4 -> index 1 is 90 deg = East
    east = hz[1, 4:12, 2:10]
    assert east == pytest.approx(10.0, abs=0.05)


def test_east_facing_ramp_gives_negative_horizon_to_the_west():
    cols = np.arange(16, dtype=np.float64)
    elevation = np.tile(cols * RES_M * np.tan(np.radians(10.0)), (16, 1))
    hz = horizon_map(elevation, RES_M, n_azimuth=4, max_range_m=800.0, curvature=False)
    # index 3 is 270 deg = West (downhill)
    west = hz[3, 4:12, 6:14]
    assert (west < 0.0).all()


def test_azimuth_count_defines_first_axis():
    elevation = np.zeros((8, 8), dtype=np.float64)
    hz = horizon_map(elevation, RES_M, n_azimuth=12, max_range_m=240.0)
    assert hz.shape[0] == 12
    assert hz.dtype == np.float32
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_horizon.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.horizon'`

- [ ] **Step 3: `horizon.py`'yi uygula**

`backend/app/horizon.py` oluştur:

```python
"""Topographic horizon angles from a DEM.

For every cell and every azimuth, the maximum elevation angle of the
terrain silhouette. Computed once from topography; a cell is shadowed at
time t when the Sun's elevation angle is below the horizon angle in the
Sun's azimuth (see :mod:`app.illumination`).

Azimuth convention matches ``make_aspect_grid``: index i is
``360 * i / n_azimuth`` degrees, 0 = North (decreasing row),
90 = East (increasing column).

The same ray-marching kernel backs the virtual LiDAR scan in Phase 5.
"""

from __future__ import annotations

import numpy as np

MOON_RADIUS_M: float = 1737400.0
_NO_HORIZON_DEG: float = -90.0


def horizon_map(
    elevation: np.ndarray,
    resolution_m: float,
    n_azimuth: int = 72,
    max_range_m: float = 10000.0,
    moon_radius_m: float = MOON_RADIUS_M,
    curvature: bool = True,
    progress: bool = False,
) -> np.ndarray:
    """Return (n_azimuth, H, W) float32 horizon elevation angles in degrees.

    Runtime scales as ``n_azimuth * (max_range_m / resolution_m) * H * W``.
    For the 500x500 / 80 m production grid with the defaults this is a
    one-time offline computation of roughly 3-10 minutes; cache the result
    as ``horizon_map.npy``.
    """
    elev = np.asarray(elevation, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError(f"elevation must be 2-D, got shape {elev.shape}")
    height, width = elev.shape

    n_steps = max(1, int(round(float(max_range_m) / float(resolution_m))))
    rows = np.arange(height, dtype=np.float64)[:, None]
    cols = np.arange(width, dtype=np.float64)[None, :]

    out = np.empty((n_azimuth, height, width), dtype=np.float32)

    for a_i in range(n_azimuth):
        az_rad = 2.0 * np.pi * a_i / n_azimuth
        d_row = -np.cos(az_rad)   # azimuth 0 = North = decreasing row
        d_col = np.sin(az_rad)    # azimuth 90 = East = increasing column

        best = np.full((height, width), -np.inf, dtype=np.float64)

        for step in range(1, n_steps + 1):
            rr = np.rint(rows + d_row * step).astype(np.int64)
            cc = np.rint(cols + d_col * step).astype(np.int64)
            inside = (rr >= 0) & (rr < height) & (cc >= 0) & (cc < width)
            rr_safe = np.clip(rr, 0, height - 1)
            cc_safe = np.clip(cc, 0, width - 1)

            distance_m = step * float(resolution_m)
            dz = elev[rr_safe, cc_safe] - elev
            if curvature:
                dz = dz - (distance_m * distance_m) / (2.0 * float(moon_radius_m))

            angle = np.degrees(np.arctan2(dz, distance_m))
            angle = np.where(inside & np.isfinite(angle), angle, -np.inf)
            np.maximum(best, angle, out=best)

        out[a_i] = np.where(np.isfinite(best), best, _NO_HORIZON_DEG).astype(np.float32)

        if progress:
            print(f"  horizon: azimuth {a_i + 1}/{n_azimuth}", flush=True)

    return out
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_horizon.py -v`

Expected: 5 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/horizon.py backend/test_horizon.py
git commit -m "feat: add topographic horizon angle map via ray marching"
```

---

### Task 6: `ephemeris.py` — güneş azimut/yükseklik geometrisi

SPICE çekirdekleri birkaç yüz MB ve repoya girmiyor. Bu yüzden modül ikiye ayrılıyor: **saf geometri** (test edilir) ve **SPICE kabuğu** (test edilmez, çekirdek gerektirir).

**Files:**
- Create: `backend/app/ephemeris.py`
- Create: `lunapath/src/fetch_kernels.py`
- Modify: `backend/requirements.txt`
- Modify: `.gitignore`
- Test: `backend/test_ephemeris.py` (create)

**Interfaces:**
- Consumes: yalnızca NumPy (saf kısım); `spiceypy` (kabuk)
- Produces:
  - `sun_azel_from_vector(sun_vec_body, lat_deg, lon_deg) -> tuple[float, float]` — `(azimuth_deg, elevation_deg)`; azimut 0=Kuzey, 90=Doğu, [0, 360)
  - `sun_vector_body(et: float) -> np.ndarray` — SPICE gerektirir
  - `sun_track(utc_start, utc_end, n_samples, lat_deg, lon_deg) -> list[tuple[float, float]]` — SPICE gerektirir; Task 7 ve Faz 3 tüketir

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_ephemeris.py` oluştur:

```python
"""Sun azimuth/elevation geometry tests (no SPICE kernels required)."""

from __future__ import annotations

import numpy as np
import pytest

from app.ephemeris import sun_azel_from_vector


def test_sun_overhead_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(90.0, abs=1e-6)


def test_sun_due_east_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(90.0, abs=1e-6)


def test_sun_due_north_at_equator_prime_meridian():
    az, el = sun_azel_from_vector(np.array([0.0, 0.0, 1.0]), lat_deg=0.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_at_south_pole_body_x_axis_is_local_north():
    """At lat=-90 the +X body direction lies on the local horizon, due North."""
    az, el = sun_azel_from_vector(np.array([1.0, 0.0, 0.0]), lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(0.0, abs=1e-6)
    assert az == pytest.approx(0.0, abs=1e-6)


def test_south_pole_sun_is_low_not_overhead():
    """A Sun vector 1.5 deg above the local horizon at the south pole."""
    elev_rad = np.radians(1.5)
    vec = np.array([np.cos(elev_rad), 0.0, -np.sin(elev_rad)])
    az, el = sun_azel_from_vector(vec, lat_deg=-90.0, lon_deg=0.0)
    assert el == pytest.approx(1.5, abs=1e-6)


def test_azimuth_is_normalised_to_zero_360():
    az, _ = sun_azel_from_vector(np.array([0.0, -1.0, 0.0]), lat_deg=0.0, lon_deg=0.0)
    assert 0.0 <= az < 360.0
    assert az == pytest.approx(270.0, abs=1e-6)


def test_zero_vector_is_rejected():
    with pytest.raises(ValueError):
        sun_azel_from_vector(np.zeros(3), lat_deg=-88.0, lon_deg=0.0)
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_ephemeris.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ephemeris'`

- [ ] **Step 3: `ephemeris.py`'yi uygula**

`backend/app/ephemeris.py` oluştur:

```python
"""Sun geometry for the lunar surface.

Split deliberately in two:

* pure geometry (``sun_azel_from_vector``) -- no external data, unit tested
* SPICE-backed ephemeris (``sun_vector_body``, ``sun_track``) -- needs NAIF
  kernels fetched by ``lunapath/src/fetch_kernels.py``; not unit tested

Azimuth convention matches :mod:`app.horizon`: 0 = North, 90 = East,
range [0, 360).
"""

from __future__ import annotations

import numpy as np

DEFAULT_META_KERNEL = "kernels/lunapath.tm"
_MOON_BODY_FRAME = "MOON_ME"


def sun_azel_from_vector(
    sun_vec_body: np.ndarray,
    lat_deg: float,
    lon_deg: float,
) -> tuple[float, float]:
    """Convert a Moon-body-fixed Sun vector to local azimuth/elevation.

    Parameters
    ----------
    sun_vec_body:
        Sun position in the Moon body-fixed frame (MOON_ME). Magnitude is
        irrelevant; only direction is used.
    lat_deg, lon_deg:
        Sub-observer point on the lunar surface, degrees.

    Returns
    -------
    (azimuth_deg, elevation_deg)
    """
    vec = np.asarray(sun_vec_body, dtype=np.float64).reshape(3)
    norm = float(np.linalg.norm(vec))
    if norm == 0.0 or not np.isfinite(norm):
        raise ValueError("sun_vec_body must be a finite non-zero 3-vector")
    unit = vec / norm

    lat = np.radians(float(lat_deg))
    lon = np.radians(float(lon_deg))

    up = np.array(
        [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    )
    east = np.array([-np.sin(lon), np.cos(lon), 0.0])
    north = np.array(
        [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)]
    )

    u = float(np.dot(unit, up))
    e = float(np.dot(unit, east))
    n = float(np.dot(unit, north))

    elevation_deg = float(np.degrees(np.arcsin(np.clip(u, -1.0, 1.0))))
    azimuth_deg = float(np.degrees(np.arctan2(e, n)) % 360.0)
    return azimuth_deg, elevation_deg


def sun_vector_body(et: float, meta_kernel: str = DEFAULT_META_KERNEL) -> np.ndarray:
    """Sun position in MOON_ME at ephemeris time *et*. Requires NAIF kernels."""
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    spice.furnsh(meta_kernel)
    position, _light_time = spice.spkpos("SUN", et, _MOON_BODY_FRAME, "LT+S", "MOON")
    return np.asarray(position, dtype=np.float64)


def sun_track(
    utc_start: str,
    utc_end: str,
    n_samples: int,
    lat_deg: float,
    lon_deg: float,
    meta_kernel: str = DEFAULT_META_KERNEL,
) -> list[tuple[float, float]]:
    """Sample (azimuth_deg, elevation_deg) between two UTC instants.

    Requires NAIF kernels. Output feeds ``app.illumination`` and the
    Phase 3 time-expanded planner.
    """
    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    spice.furnsh(meta_kernel)
    et0 = spice.str2et(utc_start)
    et1 = spice.str2et(utc_end)
    ets = np.linspace(et0, et1, int(n_samples))
    return [
        sun_azel_from_vector(sun_vector_body(float(et), meta_kernel), lat_deg, lon_deg)
        for et in ets
    ]
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_ephemeris.py -v`

Expected: 7 test PASS.

- [ ] **Step 5: Çekirdek indirme script'ini yaz**

`lunapath/src/fetch_kernels.py` oluştur:

```python
#!/usr/bin/env python3
"""Download the NAIF SPICE kernels LunaPath needs.

Kernels total a few hundred MB and are deliberately NOT committed.
Run once:  python lunapath/src/fetch_kernels.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"

KERNELS: tuple[tuple[str, str], ...] = (
    (f"{NAIF}/lsk/naif0012.tls", "naif0012.tls"),
    (f"{NAIF}/spk/planets/de440s.bsp", "de440s.bsp"),
    (f"{NAIF}/pck/moon_pa_de440_200625.bpc", "moon_pa_de440_200625.bpc"),
    (f"{NAIF}/fk/satellites/moon_de440_220930.tf", "moon_de440_220930.tf"),
)

META_KERNEL_TEMPLATE = """\\begindata
PATH_VALUES  = ( '{kernel_dir}' )
PATH_SYMBOLS = ( 'K' )
KERNELS_TO_LOAD = (
{entries}
)
\\begintext
"""


def main() -> None:
    kernel_dir = Path(__file__).resolve().parent.parent.parent / "kernels"
    kernel_dir.mkdir(parents=True, exist_ok=True)

    for url, name in KERNELS:
        target = kernel_dir / name
        if target.exists():
            print(f"  skip (exists): {name}")
            continue
        print(f"  downloading: {name} ...", flush=True)
        urllib.request.urlretrieve(url, target)
        print(f"  done: {name} ({target.stat().st_size / 1e6:.1f} MB)")

    entries = "\n".join(f"    '$K/{name}'" for _, name in KERNELS)
    meta = META_KERNEL_TEMPLATE.format(
        kernel_dir=str(kernel_dir).replace("\\", "/"), entries=entries
    )
    meta_path = kernel_dir / "lunapath.tm"
    meta_path.write_text(meta, encoding="utf-8")
    print(f"\n  meta-kernel written: {meta_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Bağımlılığı ve gitignore'u güncelle**

`backend/requirements.txt`'e ekle:

```
spiceypy==6.0.0
```

`.gitignore` sonuna ekle:

```
# NAIF SPICE kernels (hundreds of MB, fetched by lunapath/src/fetch_kernels.py)
kernels/
```

- [ ] **Step 7: Kurulum ve indirmeyi doğrula**

```bash
pip install -r backend/requirements.txt
python lunapath/src/fetch_kernels.py
python -c "from app.ephemeris import sun_track; print(sun_track('2026-11-15T00:00:00','2026-11-15T12:00:00',3,-88.5,0.0))"
```

*(Son komut `backend/` dizininden çalıştırılır ve `kernels/lunapath.tm` yolu için `meta_kernel` argümanı gerekebilir — indirme çıktısındaki yolu kullan.)*

Expected: üç `(azimuth, elevation)` çifti; güney kutbunda elevation değerleri ~0–2° bandında.

- [ ] **Step 8: Commit**

```bash
git add backend/app/ephemeris.py backend/test_ephemeris.py \
        lunapath/src/fetch_kernels.py backend/requirements.txt .gitignore
git commit -m "feat: add SPICE-backed sun geometry with pure-math core"
```

---

### Task 7: `illumination.py` — `I(x, y, t)` aydınlanma alanı

**Files:**
- Create: `backend/app/illumination.py`
- Test: `backend/test_illumination.py` (create)

**Interfaces:**
- Consumes: `horizon_map` çıktısı `(n_azimuth, H, W)` (Task 5); `sun_track` çıktısı `list[(az, el)]` (Task 6)
- Produces:
  - `illuminated_mask(horizon_deg, sun_az_deg, sun_elev_deg) -> np.ndarray` — `(H, W)` bool
  - `illumination_fraction(horizon_deg, sun_samples) -> np.ndarray` — `(H, W)` float32 [0, 1]
  - `shadow_ratio_from_illumination(illum_frac) -> np.ndarray` — `1 - illum_frac`; Task 8 ve Faz 3 tüketir

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_illumination.py` oluştur:

```python
"""Illumination field tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.illumination import (
    illuminated_mask,
    illumination_fraction,
    shadow_ratio_from_illumination,
)

N_AZ = 8
SHAPE = (5, 5)


def _flat_horizon(value_deg: float = 0.0) -> np.ndarray:
    return np.full((N_AZ, *SHAPE), value_deg, dtype=np.float32)


def test_sun_above_flat_horizon_lights_everything():
    mask = illuminated_mask(_flat_horizon(0.0), sun_az_deg=90.0, sun_elev_deg=5.0)
    assert mask.shape == SHAPE
    assert mask.all()


def test_sun_below_flat_horizon_darkens_everything():
    mask = illuminated_mask(_flat_horizon(0.0), sun_az_deg=90.0, sun_elev_deg=-5.0)
    assert not mask.any()


def test_only_the_matching_azimuth_bin_blocks():
    """A ridge in one azimuth must not shadow the Sun coming from another."""
    horizon = _flat_horizon(0.0)
    horizon[2] = 10.0  # index 2 of 8 bins -> 90 deg = East
    blocked = illuminated_mask(horizon, sun_az_deg=90.0, sun_elev_deg=5.0)
    clear = illuminated_mask(horizon, sun_az_deg=0.0, sun_elev_deg=5.0)
    assert not blocked.any()
    assert clear.all()


def test_azimuth_snaps_to_nearest_bin_and_wraps():
    horizon = _flat_horizon(0.0)
    horizon[0] = 10.0  # 0 deg = North
    assert not illuminated_mask(horizon, 359.0, 5.0).any()
    assert not illuminated_mask(horizon, 361.0, 5.0).any()


def test_illumination_fraction_averages_over_samples():
    horizon = _flat_horizon(0.0)
    samples = [(90.0, 5.0), (90.0, -5.0), (90.0, 5.0), (90.0, -5.0)]
    frac = illumination_fraction(horizon, samples)
    assert frac.shape == SHAPE
    assert frac.dtype == np.float32
    assert frac == pytest.approx(0.5)


def test_illumination_fraction_rejects_empty_sample_list():
    with pytest.raises(ValueError):
        illumination_fraction(_flat_horizon(0.0), [])


def test_shadow_ratio_is_complement_of_illumination():
    frac = np.array([[0.0, 0.25, 1.0]], dtype=np.float32)
    ratio = shadow_ratio_from_illumination(frac)
    assert ratio == pytest.approx(np.array([[1.0, 0.75, 0.0]], dtype=np.float32))
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_illumination.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.illumination'`

- [ ] **Step 3: `illumination.py`'yi uygula**

`backend/app/illumination.py` oluştur:

```python
"""Illumination field I(x, y, t) from horizon geometry and Sun ephemeris.

A cell is lit when the Sun's elevation angle exceeds the terrain horizon
angle in the Sun's azimuth. This replaces the ``1 - normalize(elevation)``
shadow proxy in the P1 pipeline with real ray-cast geometry.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def _azimuth_bin(sun_az_deg: float, n_azimuth: int) -> int:
    """Nearest horizon azimuth bin for a Sun azimuth in degrees."""
    normalised = float(sun_az_deg) % 360.0
    return int(round(normalised / 360.0 * n_azimuth)) % n_azimuth


def illuminated_mask(
    horizon_deg: np.ndarray,
    sun_az_deg: float,
    sun_elev_deg: float,
) -> np.ndarray:
    """(H, W) boolean mask: True where the Sun clears the local horizon."""
    horizon = np.asarray(horizon_deg)
    if horizon.ndim != 3:
        raise ValueError(
            f"horizon_deg must be (n_azimuth, H, W), got shape {horizon.shape}"
        )
    bin_index = _azimuth_bin(sun_az_deg, horizon.shape[0])
    return float(sun_elev_deg) > horizon[bin_index]


def illumination_fraction(
    horizon_deg: np.ndarray,
    sun_samples: Sequence[tuple[float, float]],
) -> np.ndarray:
    """(H, W) float32 in [0, 1]: fraction of samples in which a cell is lit.

    *sun_samples* is a sequence of ``(azimuth_deg, elevation_deg)`` pairs,
    typically from :func:`app.ephemeris.sun_track`.
    """
    if len(sun_samples) == 0:
        raise ValueError("sun_samples must contain at least one (az, elev) pair")

    horizon = np.asarray(horizon_deg)
    accumulator = np.zeros(horizon.shape[1:], dtype=np.float64)
    for az_deg, elev_deg in sun_samples:
        accumulator += illuminated_mask(horizon, az_deg, elev_deg)

    return (accumulator / float(len(sun_samples))).astype(np.float32)


def shadow_ratio_from_illumination(illum_frac: np.ndarray) -> np.ndarray:
    """Convert illumination fraction to the shadow ratio the cost engine wants.

    ``shadow_ratio`` is 0 for fully lit and 1 for fully shadowed, matching
    ``app.cost_engine.f_shadow_cell``.
    """
    frac = np.asarray(illum_frac, dtype=np.float32)
    return (1.0 - np.clip(frac, 0.0, 1.0)).astype(np.float32)
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_illumination.py -v`

Expected: 7 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/illumination.py backend/test_illumination.py
git commit -m "feat: derive illumination field from horizon map and sun track"
```

---

### Task 8: P1 hattı entegrasyonu ve `layer_validity`

Yeni fizik modüllerini offline hatta bağlar ve her katmanın kökenini makine-okunur hâle getirir.

**Files:**
- Modify: `lunapath/src/process_lunar_data.py`
- Modify: `backend/app/data_loader.py`
- Test: `backend/test_layer_validity.py` (create)

**Interfaces:**
- Consumes: `horizon_map` (Task 5), `sun_track` (Task 6), `illumination_fraction` / `shadow_ratio_from_illumination` (Task 7), `Heat1DModel` / `SyntheticModel` / `build_thermal_grid` (Task 3–4)
- Produces: `metadata.json` içinde `layer_validity: dict[str, str]`; `load_preprocessed_grids` çıktısının `metadata` sözlüğünde aynı anahtar

- [ ] **Step 1: Başarısız testi yaz**

`backend/test_layer_validity.py` oluştur:

```python
"""Layer provenance (validity) plumbing tests."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.data_loader import load_preprocessed_grids

_VALID = {"MEASURED", "DERIVED", "MODEL", "SYNTHETIC"}
_LAYERS = (
    "elevation",
    "slope",
    "aspect",
    "shadow_ratio",
    "thermal",
    "traversable",
    "cost",
)


def _write_fake_processed_dir(tmp_path):
    shape = (4, 4)
    arrays = {
        "elevation_grid": np.zeros(shape),
        "slope_grid": np.zeros(shape),
        "aspect_grid": np.zeros(shape),
        "shadow_ratio_grid": np.zeros(shape),
        "thermal_grid": np.full(shape, -50.0),
        "traversability_grid": np.ones(shape),
        "cost_grid": np.full(shape, 0.5),
    }
    for name, arr in arrays.items():
        np.save(tmp_path / f"{name}.npy", arr)

    metadata = {
        "origin": {"x": 156000.0, "y": 28000.0},
        "resolution_m": 80.0,
        "shape": list(shape),
        "crs": "test",
        "cost_weights": {
            "w_slope": 0.409,
            "w_energy": 0.259,
            "w_shadow": 0.142,
            "w_thermal": 0.19,
        },
        "layer_validity": {
            "elevation": "MEASURED",
            "slope": "DERIVED",
            "aspect": "DERIVED",
            "shadow_ratio": "DERIVED",
            "thermal": "MODEL",
            "traversable": "DERIVED",
            "cost": "DERIVED",
        },
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_load_preprocessed_grids_exposes_layer_validity(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    validity = grids["metadata"]["layer_validity"]
    assert set(validity) == set(_LAYERS)
    assert set(validity.values()) <= _VALID


def test_layer_validity_defaults_when_metadata_omits_it(tmp_path):
    """Older metadata.json files must still load, marked UNKNOWN."""
    directory = _write_fake_processed_dir(tmp_path)
    meta_path = directory / "metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    del metadata["layer_validity"]
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    grids = load_preprocessed_grids(processed_dir=str(directory))
    validity = grids["metadata"]["layer_validity"]
    assert set(validity) == set(_LAYERS)
    assert all(value == "UNKNOWN" for value in validity.values())
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_layer_validity.py -v`

Expected: FAIL — `KeyError: 'layer_validity'`

- [ ] **Step 3: `data_loader.py`'yi güncelle**

`backend/app/data_loader.py` içinde, `_GRID_KEYS` tanımının altına ekle:

```python
_VALIDITY_LAYERS: tuple[str, ...] = (
    "elevation",
    "slope",
    "aspect",
    "shadow_ratio",
    "thermal",
    "traversable",
    "cost",
)
```

Aynı dosyada `load_preprocessed_grids` içindeki `result["metadata"] = {` sözlüğüne, `"cost_model"` satırının altına ekle:

```python
        "layer_validity": {
            layer: str(metadata.get("layer_validity", {}).get(layer, "UNKNOWN"))
            for layer in _VALIDITY_LAYERS
        },
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `cd backend && pytest test_layer_validity.py -v`

Expected: 2 test PASS.

- [ ] **Step 5: P1 hattını yeni fizik modüllerine bağla**

`lunapath/src/process_lunar_data.py` içinde import bloğunu şu hâle getir:

```python
from app.cost_engine import compute_cost_grid, resolve_weights  # noqa: E402
from app.horizon import horizon_map  # noqa: E402
from app.illumination import (  # noqa: E402
    illumination_fraction,
    shadow_ratio_from_illumination,
)
from app.thermal_model import (  # noqa: E402
    Heat1DModel,
    SyntheticModel,
    build_thermal_grid,
)
from app.traversability import compute_traversability  # noqa: E402
```

*(`from app.thermal_grid import generate_thermal_grid` satırını kaldır — artık `thermal_model` üzerinden çağrılıyor.)*

Sabitler bloğuna ekle:

```python
# Guney kutbu penceresinin nominal enlemi (heat1d LUT ve gunes izi icin)
NOMINAL_LAT_DEG = -88.5
NOMINAL_LON_DEG = 0.0
HORIZON_N_AZIMUTH = 72
HORIZON_MAX_RANGE_M = 10000.0
# Bir Ay gunu boyunca saatlik ornekleme
SUN_TRACK_START_UTC = "2026-11-15T00:00:00"
SUN_TRACK_END_UTC = "2026-12-13T00:00:00"
SUN_TRACK_SAMPLES = 168
```

`make_shadow_ratio_grid` fonksiyonunun **tamamını** şununla değiştir:

```python
def make_shadow_ratio_grid(elevation: np.ndarray, resolution: float) -> tuple[np.ndarray, str]:
    """Golge orani [0, 1]. 0=aydinlik, 1=karanlik.

    Gercek yol: topografik ufuk haritasi + SPICE gunes izi.
    SPICE cekirdekleri yoksa yukseklik proxy'sine duser ve bunu bildirir.

    Donus: (shadow_ratio_grid, validity)
    """
    from app.ephemeris import sun_track

    try:
        horizon = horizon_map(
            elevation,
            resolution,
            n_azimuth=HORIZON_N_AZIMUTH,
            max_range_m=HORIZON_MAX_RANGE_M,
            progress=True,
        )
        samples = sun_track(
            SUN_TRACK_START_UTC,
            SUN_TRACK_END_UTC,
            SUN_TRACK_SAMPLES,
            NOMINAL_LAT_DEG,
            NOMINAL_LON_DEG,
        )
        frac = illumination_fraction(horizon, samples)
        return shadow_ratio_from_illumination(frac).astype(np.float64), "DERIVED"
    except (RuntimeError, OSError) as exc:
        print(f"  UYARI: gercek aydinlanma hesaplanamadi ({exc}); proxy kullaniliyor")
        e_min = np.nanmin(elevation)
        e_max = np.nanmax(elevation)
        elev_norm = (elevation - e_min) / (e_max - e_min + 1e-10)
        return (1.0 - elev_norm), "SYNTHETIC"
```

`make_thermal_grid` fonksiyonunun **tamamını** şununla değiştir:

```python
def make_thermal_grid(
    elevation: np.ndarray,
    slope: np.ndarray,
    aspect: np.ndarray,
    resolution: float,
) -> tuple[np.ndarray, str]:
    """Yuzey sicaklik grid'i (Celsius) + validity etiketi.

    heat1d kuruluysa gercek termal difuzyon modeli, degilse sentetik proxy.
    """
    if Heat1DModel.available():
        model = Heat1DModel()
    else:
        print("  UYARI: heat1d bulunamadi; sentetik termal model kullaniliyor")
        model = SyntheticModel(elevation=elevation, resolution_m=resolution)

    grid = build_thermal_grid(model, slope, aspect, NOMINAL_LAT_DEG)
    return grid.astype(np.float64), model.validity
```

- [ ] **Step 6: `main()` akışını ve `save_metadata`'yı güncelle**

`main()` içinde şu iki çağrıyı değiştir:

```python
    shadow_ratio_grid = make_shadow_ratio_grid(elevation_grid)
```
→
```python
    shadow_ratio_grid, shadow_validity = make_shadow_ratio_grid(
        elevation_grid, RESOLUTION_M
    )
```

ve

```python
    thermal_grid = make_thermal_grid(
        elevation_grid, slope_grid, aspect_grid, RESOLUTION_M,
    )
```
→
```python
    thermal_grid, thermal_validity = make_thermal_grid(
        elevation_grid, slope_grid, aspect_grid, RESOLUTION_M,
    )
    print(f"  thermal validity: {thermal_validity}")
    print(f"  shadow  validity: {shadow_validity}")
```

`main()` içindeki `save_metadata(...)` çağrısına şu argümanı ekle:

```python
        layer_validity={
            "elevation": "MEASURED",
            "slope": "DERIVED",
            "aspect": "DERIVED",
            "shadow_ratio": shadow_validity,
            "thermal": thermal_validity,
            "traversable": "DERIVED",
            "cost": "DERIVED",
        },
```

`save_metadata` imzasına parametreyi ekle (son parametre olarak):

```python
    layer_validity: dict[str, str],
```

ve `meta` sözlüğüne `"cost_model"` satırının altına ekle:

```python
        "layer_validity": layer_validity,
```

- [ ] **Step 7: Hattı çalıştır ve doğrula**

```bash
cd lunapath/src && python process_lunar_data.py
python -c "import json; m=json.load(open('../data/processed/metadata.json')); print(m['layer_validity'])"
```

Expected: yedi katmanın validity etiketi yazdırılıyor. `thermal` `MODEL` (heat1d kuruluysa) veya `SYNTHETIC`; `shadow_ratio` `DERIVED` (SPICE çekirdekleri varsa) veya `SYNTHETIC`.

*Not: ufuk hesabı 500×500 / 72 azimut / 125 adım için birkaç dakika sürer; `progress=True` ilerlemeyi yazdırır.*

- [ ] **Step 8: Uçtan uca regresyon**

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
uvicorn app.main:app --port 8000 &
sleep 5
curl -s -X POST http://127.0.0.1:8000/api/plan \
  -H "Content-Type: application/json" \
  -d '{"start":{"row":100,"col":100},"goal":{"row":400,"col":400}}' | head -c 400
```

Expected: pytest tamamı PASS; `/api/plan` bir rota döndürüyor (`path_pixels` boş değil).

- [ ] **Step 9: Commit**

```bash
git add lunapath/src/process_lunar_data.py backend/app/data_loader.py \
        backend/test_layer_validity.py
git commit -m "feat: wire heat1d thermal and horizon-based shadow into P1 pipeline

Adds layer_validity provenance to metadata.json so each grid declares
whether it is MEASURED, DERIVED, MODEL or SYNTHETIC. Both new physics
paths degrade gracefully: missing heat1d or missing SPICE kernels fall
back to the synthetic baseline and say so."
```

---

## Faz 1 kabul kriterleri

- [ ] `cd backend && pytest` — tüm testler geçiyor (26+ test)
- [ ] `python test_cost_engine.py` ve `python test_traversability.py` — çıkış kodu 0
- [ ] Tam gölgeli bir hücre, aynı ama aydınlık hücreden **~0.142 daha pahalı** (önce ~0.00005 idi)
- [ ] `metadata.json` yedi katmanın her biri için `layer_validity` taşıyor
- [ ] `thermal_grid.npy` heat1d'den üretiliyor (`layer_validity.thermal == "MODEL"`) **veya** heat1d'nin neden kullanılamadığı hat çıktısında açıkça yazılı
- [ ] `shadow_ratio_grid.npy` ufuk + efemeris hesabından üretiliyor (`layer_validity.shadow_ratio == "DERIVED"`) **veya** SPICE eksikliği açıkça raporlanmış
- [ ] `/api/plan` çalışıyor ve rota döndürüyor

## Sonraki adım

Faz 2 — [`2026-08-19-faz2-maliyet-mimarisi.md`](2026-08-19-faz2-maliyet-mimarisi.md)
