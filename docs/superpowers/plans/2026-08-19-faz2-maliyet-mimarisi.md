# Faz 2 — Maliyet Mimarisi ve Koridor Sözleşmesi Implementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maliyet motorunu Nav2'nin costmap katman desenine çevirip hücre bazında açıklanabilir hâle getirmek, ve yerel katmana giden `Corridor` sözleşmesini üretmek.

**Architecture:** `compute_cost_grid`'in tek parça hesabı, her biri kendi ağırlığını ve provenance etiketini taşıyan `CostLayer`'lara bölünüyor. Katmanlar `CostMap` içinde toplanıyor; `explain()` bir hücrenin maliyetine hangi katmanın ne kadar katkı yaptığını döndürüyor. Ayrı bir `corridor.py`, rota + geçilebilirlik maskesinden `Corridor` sözleşmesini üretiyor — bu, Faz 4 (ROS 2) ve Faz 5 (LiDAR) arasındaki tek arayüz. `replan_triggers.py` sözleşmenin ters yönünü tanımlıyor.

**Tech Stack:** Python 3.11+ · NumPy 2.2.1 · SciPy 1.15.0 · FastAPI 0.115.6 · pydantic · pytest

**Spec:** [`docs/research/ENTEGRASYON_TEKNOLOJILERI.md`](../../research/ENTEGRASYON_TEKNOLOJILERI.md) §2.5, §2.6, §2.7, §3.3

**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md) — **Global Constraints bölümü bu planın her görevi için geçerlidir.**

**Önkoşul:** Faz 1 tamamlanmış olmalı (`f_shadow_cell` mevcut olmalı — Task 2 onu kullanıyor).

---

## Faz kapsamı

| Görev | Ne | Süre |
|---|---|---|
| 1 | `costmap.py` — `PlanContext`, `CostLayer`, `CostMap`, `explain()` | 1 gün |
| 2 | Dört kriteri katmana taşı + eski çıktıyla bit-yakın eşitlik testi | 1 gün |
| 3 | `/api/cell-telemetry` → `cost_breakdown` alanı | 0.5 gün |
| 4 | `schemas.py` + `corridor.py` — `Corridor` üretimi | 1 gün |
| 5 | `/api/plan` → `corridor` alanı | 0.5 gün |
| 6 | `replan_triggers.py` + `/api/replan` | 1 gün |

---

### Task 1: `costmap.py` — katman protokolü ve `CostMap`

**Files:**
- Create: `backend/app/costmap.py`
- Test: `backend/test_costmap.py` (create)

**Interfaces:**
- Consumes: NumPy; `app.constants.get_rover`
- Produces:
  - `PlanContext` dataclass: `slope`, `thermal`, `shadow_ratio`, `traversable` (hepsi `np.ndarray`), `resolution_m: float`, `rover: Mapping[str, Any]`
  - `CostLayer` protokolü: `name: str`, `validity: str`, `weight: float`, `contribution(ctx: PlanContext) -> np.ndarray`
  - `CostMap(layers: list[CostLayer])` — `total(ctx) -> np.ndarray`, `explain(row, col, ctx) -> dict[str, float]`
  - Task 2 bu protokolü implemente eden dört somut katman ekler

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_costmap.py` oluştur:

```python
"""CostMap layer container tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.costmap import CostMap, PlanContext

SHAPE = (3, 3)


class _ConstantLayer:
    """Minimal CostLayer stub returning a fixed value everywhere."""

    def __init__(self, name: str, weight: float, value: float) -> None:
        self.name = name
        self.validity = "MODEL"
        self.weight = weight
        self._value = value

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return np.full(ctx.slope.shape, self._value, dtype=np.float64)


def _context(traversable_value: bool = True) -> PlanContext:
    return PlanContext(
        slope=np.zeros(SHAPE),
        thermal=np.full(SHAPE, -50.0),
        shadow_ratio=np.zeros(SHAPE),
        traversable=np.full(SHAPE, traversable_value, dtype=bool),
        resolution_m=80.0,
        rover=get_rover(),
    )


def test_total_is_weighted_sum_of_layers():
    cost_map = CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("b", 0.5, 0.6)])
    total = cost_map.total(_context())
    assert total == pytest.approx(np.full(SHAPE, 0.5 * 0.4 + 0.5 * 0.6))


def test_total_clamps_to_minimum_cost():
    cost_map = CostMap([_ConstantLayer("a", 1.0, 0.0)])
    total = cost_map.total(_context())
    assert total == pytest.approx(np.full(SHAPE, 0.01))


def test_blocked_cells_are_infinite():
    cost_map = CostMap([_ConstantLayer("a", 1.0, 0.5)])
    total = cost_map.total(_context(traversable_value=False))
    assert np.isinf(total).all()


def test_nan_inputs_produce_infinite_cost():
    cost_map = CostMap([_ConstantLayer("a", 1.0, 0.5)])
    ctx = _context()
    ctx.thermal[1, 1] = np.nan
    total = cost_map.total(ctx)
    assert np.isinf(total[1, 1])
    assert np.isfinite(total[0, 0])


def test_explain_returns_per_layer_weighted_contributions():
    cost_map = CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("b", 0.5, 0.6)])
    breakdown = cost_map.explain(1, 1, _context())
    assert breakdown["a"] == pytest.approx(0.2)
    assert breakdown["b"] == pytest.approx(0.3)
    assert breakdown["total"] == pytest.approx(0.5)


def test_explain_reports_blocked_cells():
    cost_map = CostMap([_ConstantLayer("a", 1.0, 0.5)])
    breakdown = cost_map.explain(0, 0, _context(traversable_value=False))
    assert np.isinf(breakdown["total"])


def test_layer_names_are_exposed():
    cost_map = CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("b", 0.5, 0.6)])
    assert cost_map.layer_names() == ["a", "b"]


def test_duplicate_layer_names_are_rejected():
    with pytest.raises(ValueError):
        CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("a", 0.5, 0.6)])
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_costmap.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.costmap'`

- [ ] **Step 3: `costmap.py`'yi uygula**

`backend/app/costmap.py` oluştur:

```python
"""Layered cost map.

Borrows the Nav2 ``costmap_2d`` pattern: cost is not one array but a stack
of layers, each owning its weight, its provenance, and its own update. The
payoff is ``CostMap.explain()`` -- a per-cell breakdown of which criterion
drove the cost, which is the technical answer to "why this route?".

Adding a new criterion means adding a CostLayer, not editing a monolith.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

MIN_CELL_COST: float = 0.01


@dataclass
class PlanContext:
    """Everything a layer may read. Layers must not mutate it."""

    slope: np.ndarray
    thermal: np.ndarray
    shadow_ratio: np.ndarray
    traversable: np.ndarray
    resolution_m: float
    rover: Mapping[str, Any]


@runtime_checkable
class CostLayer(Protocol):
    name: str
    validity: str  # "MEASURED" | "DERIVED" | "MODEL" | "SYNTHETIC"
    weight: float

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        """Unweighted MRU [0, 1] penalty per cell (inf where impassable)."""
        ...


class CostMap:
    """Weighted sum of cost layers with a per-cell explanation."""

    def __init__(self, layers: list[CostLayer]) -> None:
        names = [layer.name for layer in layers]
        duplicates = {name for name in names if names.count(name) > 1}
        if duplicates:
            raise ValueError(f"duplicate cost layer names: {sorted(duplicates)}")
        self.layers = list(layers)

    def layer_names(self) -> list[str]:
        return [layer.name for layer in self.layers]

    def _invalid_mask(self, ctx: PlanContext) -> np.ndarray:
        return (
            ~np.asarray(ctx.traversable, dtype=bool)
            | np.isnan(ctx.slope)
            | np.isnan(ctx.thermal)
            | np.isnan(ctx.shadow_ratio)
        )

    def total(self, ctx: PlanContext) -> np.ndarray:
        """(H, W) float64 cost grid. Impassable cells are ``inf``."""
        accumulator = np.zeros(np.asarray(ctx.slope).shape, dtype=np.float64)
        for layer in self.layers:
            accumulator = accumulator + layer.weight * layer.contribution(ctx)

        out = np.maximum(accumulator, MIN_CELL_COST)
        out[self._invalid_mask(ctx)] = np.inf
        return out

    def explain(self, row: int, col: int, ctx: PlanContext) -> dict[str, float]:
        """Weighted contribution of every layer at one cell, plus the total."""
        breakdown: dict[str, float] = {}
        running = 0.0
        for layer in self.layers:
            value = float(layer.weight * layer.contribution(ctx)[row, col])
            breakdown[layer.name] = value
            running += value

        if bool(self._invalid_mask(ctx)[row, col]):
            breakdown["total"] = float("inf")
        else:
            breakdown["total"] = float(max(running, MIN_CELL_COST))
        return breakdown
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_costmap.py -v`

Expected: 8 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/costmap.py backend/test_costmap.py
git commit -m "feat: add layered CostMap with per-cell explain()"
```

---

### Task 2: Dört kriteri `CostLayer`'a taşı

Refaktörün riski, sayıların sessizce kaymasıdır. Bu görevin merkezi testi bir **eşitlik testidir**: `CostMap.total()` mevcut `compute_cost_grid()` ile 1e-9 toleransında aynı olmalı.

**Files:**
- Modify: `backend/app/costmap.py`
- Test: `backend/test_costmap.py` (genişlet)

**Interfaces:**
- Consumes: `app.cost_engine.f_slope`, `f_energy`, `f_shadow_cell`, `f_thermal`; `app.constants.get_rover`
- Produces: `SlopeLayer`, `EnergyLayer`, `ShadowLayer`, `ThermalLayer` sınıfları; `default_cost_map(rover, weights=None) -> CostMap` fabrika fonksiyonu. Task 3 ve Task 5 bunu kullanır.

- [ ] **Step 1: Eşitlik testini yaz**

`backend/test_costmap.py` sonuna ekle:

```python
from app.cost_engine import compute_cost_grid, resolve_weights
from app.costmap import default_cost_map


def _random_context(seed: int = 7, shape=(24, 24)) -> PlanContext:
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0.0, 30.0, size=shape)      # spans the 25 deg limit
    thermal = rng.uniform(-200.0, 40.0, size=shape)  # spans the -150 C limit
    shadow = rng.uniform(0.0, 1.0, size=shape)
    rover = get_rover()
    traversable = (slope <= float(rover["slope_max_deg"])) & (thermal >= -150.0)
    return PlanContext(
        slope=slope,
        thermal=thermal,
        shadow_ratio=shadow,
        traversable=traversable,
        resolution_m=80.0,
        rover=rover,
    )


def test_default_cost_map_matches_compute_cost_grid():
    """The refactor must not move a single number."""
    ctx = _random_context()
    legacy = compute_cost_grid(
        ctx.slope,
        ctx.thermal,
        ctx.shadow_ratio,
        ctx.resolution_m,
        traversable=ctx.traversable,
        rover=ctx.rover,
    )
    layered = default_cost_map(ctx.rover).total(ctx)

    assert legacy.shape == layered.shape
    assert np.array_equal(np.isinf(legacy), np.isinf(layered))
    finite = np.isfinite(legacy)
    assert np.allclose(legacy[finite], layered[finite], rtol=0.0, atol=1e-9)


def test_default_cost_map_honours_weight_overrides():
    ctx = _random_context()
    overrides = {"w_slope": 1.0, "w_energy": 0.0, "w_shadow": 0.0, "w_thermal": 0.0}
    legacy = compute_cost_grid(
        ctx.slope,
        ctx.thermal,
        ctx.shadow_ratio,
        ctx.resolution_m,
        traversable=ctx.traversable,
        weights=overrides,
        rover=ctx.rover,
    )
    layered = default_cost_map(ctx.rover, weights=overrides).total(ctx)
    finite = np.isfinite(legacy)
    assert np.allclose(legacy[finite], layered[finite], rtol=0.0, atol=1e-9)


def test_default_cost_map_layer_names_and_validity():
    cost_map = default_cost_map(get_rover())
    assert cost_map.layer_names() == ["slope", "energy", "shadow", "thermal"]
    assert {layer.validity for layer in cost_map.layers} <= {
        "MEASURED",
        "DERIVED",
        "MODEL",
        "SYNTHETIC",
    }


def test_explain_sums_to_total_on_a_real_cell():
    ctx = _random_context()
    cost_map = default_cost_map(ctx.rover)
    total_grid = cost_map.total(ctx)
    row, col = np.argwhere(np.isfinite(total_grid))[0]
    breakdown = cost_map.explain(int(row), int(col), ctx)
    parts = sum(v for k, v in breakdown.items() if k != "total")
    assert breakdown["total"] == pytest.approx(max(parts, 0.01), abs=1e-9)
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_costmap.py -v`

Expected: FAIL — `ImportError: cannot import name 'default_cost_map'`

- [ ] **Step 3: Somut katmanları uygula**

`backend/app/costmap.py` sonuna ekle:

```python
from .cost_engine import f_energy, f_shadow_cell, f_slope, f_thermal, resolve_weights

# The scalar penalties in cost_engine are the frozen, validated formulas.
# np.vectorize keeps the layered path bit-identical to the legacy loop.
# Optimising this (see spec: precomputation) is explicitly out of scope.
_f_slope_vec = np.vectorize(f_slope, otypes=[np.float64], excluded={1})
_f_energy_vec = np.vectorize(f_energy, otypes=[np.float64], excluded={1, 2})
_f_shadow_cell_vec = np.vectorize(f_shadow_cell, otypes=[np.float64])
_f_thermal_vec = np.vectorize(f_thermal, otypes=[np.float64], excluded={1})


class SlopeLayer:
    name = "slope"
    validity = "DERIVED"

    def __init__(self, weight: float) -> None:
        self.weight = float(weight)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_slope_vec(ctx.slope, ctx.rover)


class EnergyLayer:
    name = "energy"
    validity = "MODEL"

    def __init__(self, weight: float) -> None:
        self.weight = float(weight)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_energy_vec(ctx.slope, ctx.resolution_m, ctx.rover)


class ShadowLayer:
    name = "shadow"
    validity = "DERIVED"

    def __init__(self, weight: float) -> None:
        self.weight = float(weight)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_shadow_cell_vec(ctx.shadow_ratio)


class ThermalLayer:
    name = "thermal"
    validity = "MODEL"

    def __init__(self, weight: float) -> None:
        self.weight = float(weight)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_thermal_vec(ctx.thermal, ctx.rover)


def default_cost_map(
    rover: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
) -> CostMap:
    """The four AHP criteria, wired to the rover's weight profile."""
    resolved = resolve_weights(weights, rover)
    return CostMap(
        [
            SlopeLayer(resolved["w_slope"]),
            EnergyLayer(resolved["w_energy"]),
            ShadowLayer(resolved["w_shadow"]),
            ThermalLayer(resolved["w_thermal"]),
        ]
    )
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_costmap.py -v`

Expected: 12 test PASS. Eşitlik testi geçmezse **katmanları düzelt, testi gevşetme** — bu test refaktörün güvenlik ağıdır.

- [ ] **Step 5: Tam regresyon**

Run:

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
```

Expected: hepsi PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/costmap.py backend/test_costmap.py
git commit -m "feat: express the four AHP criteria as CostLayers

default_cost_map().total() is asserted bit-identical (atol 1e-9) to the
legacy compute_cost_grid(), so the refactor is provably behaviour-preserving."
```

---

### Task 3: `/api/cell-telemetry` → `cost_breakdown`

**Files:**
- Modify: `backend/app/main.py` (`get_cell_telemetry`)
- Test: `backend/test_cell_telemetry_explain.py` (create)

**Interfaces:**
- Consumes: `default_cost_map` (Task 2), `PlanContext` (Task 1)
- Produces: `/api/cell-telemetry` yanıtına `cost_breakdown: dict[str, float]` ve `layer_validity: dict[str, str]` alanları. Mevcut alanların hiçbiri değişmez.

- [ ] **Step 1: Başarısız testi yaz**

`backend/test_cell_telemetry_explain.py` oluştur:

```python
"""cell-telemetry cost breakdown tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (8, 8)


@pytest.fixture()
def client():
    rover = get_rover()
    grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 5.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.5),
        "traversable": np.ones(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
            "layer_validity": {"thermal": "MODEL", "shadow_ratio": "DERIVED"},
        },
    }
    app.state.grids = grids
    with TestClient(app) as test_client:
        yield test_client
    app.state.grids = None


def test_cell_telemetry_returns_cost_breakdown(client):
    response = client.get("/api/cell-telemetry", params={"row": 3, "col": 3})
    assert response.status_code == 200
    payload = response.json()

    breakdown = payload["cost_breakdown"]
    assert set(breakdown) == {"slope", "energy", "shadow", "thermal", "total"}
    parts = sum(v for k, v in breakdown.items() if k != "total")
    assert breakdown["total"] == pytest.approx(max(parts, 0.01), abs=1e-9)


def test_cell_telemetry_keeps_existing_fields(client):
    payload = client.get("/api/cell-telemetry", params={"row": 3, "col": 3}).json()
    for key in ("row", "col", "lon", "lat", "altitude_m", "thermal_c", "resolution_m"):
        assert key in payload


def test_cell_telemetry_exposes_layer_validity(client):
    payload = client.get("/api/cell-telemetry", params={"row": 0, "col": 0}).json()
    assert payload["layer_validity"]["thermal"] == "MODEL"
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_cell_telemetry_explain.py -v`

Expected: FAIL — `KeyError: 'cost_breakdown'`

- [ ] **Step 3: Endpoint'i genişlet**

`backend/app/main.py` import bloğuna ekle:

```python
from .costmap import PlanContext, default_cost_map
```

`get_cell_telemetry` fonksiyonunda, `return {` satırından **önce** ekle:

```python
    rover = get_rover(metadata.get("rover_id", metadata.get("default_rover_id")))
    context = PlanContext(
        slope=np.asarray(grids["slope"], dtype=np.float64),
        thermal=np.asarray(grids["thermal"], dtype=np.float64),
        shadow_ratio=np.asarray(grids["shadow_ratio"], dtype=np.float64),
        traversable=np.asarray(grids["traversable"], dtype=bool),
        resolution_m=resolution_m,
        rover=rover,
    )
    cost_map = default_cost_map(rover, metadata.get("cost_weights"))
    breakdown = cost_map.explain(row, col, context)
```

ve `return` sözlüğüne iki alan ekle (`"span_km"` satırının altına):

```python
        "cost_breakdown": breakdown,
        "layer_validity": metadata.get("layer_validity", {}),
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `cd backend && pytest test_cell_telemetry_explain.py -v`

Expected: 3 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/test_cell_telemetry_explain.py
git commit -m "feat: expose per-layer cost breakdown from cell-telemetry"
```

---

### Task 4: `schemas.py` + `corridor.py` — koridor sözleşmesi

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/corridor.py`
- Test: `backend/test_corridor.py` (create)

**Interfaces:**
- Consumes: `scipy.ndimage.distance_transform_edt`; `app.cost_engine.edge_energy_wh`, `edge_travel_time_s`, `surface_to_inner`
- Produces:
  - `schemas.Corridor` pydantic modeli (alanlar aşağıda)
  - `corridor.build_corridor(path_pixels, grids, rover, safe_shadow_ratio=0.2, max_half_width_m=400.0) -> Corridor`
  - `corridor.clearance_map(traversable, resolution_m) -> np.ndarray`
  - Faz 4 (`corridor_publisher.py`) ve Faz 5 (sanal LiDAR tüketicisi) bunları kullanır

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_corridor.py` oluştur:

```python
"""Corridor contract tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.corridor import build_corridor, clearance_map
from app.schemas import Corridor

SHAPE = (20, 20)
RES_M = 80.0


def _grids(blocked: tuple[tuple[int, int], ...] = ()) -> dict:
    traversable = np.ones(SHAPE, dtype=bool)
    for r, c in blocked:
        traversable[r, c] = False
    return {
        "slope": np.full(SHAPE, 5.0),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.1),
        "traversable": traversable,
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": RES_M,
            "shape": list(SHAPE),
        },
    }


def test_clearance_map_is_zero_on_blocked_cells():
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[10, 10] = False
    clearance = clearance_map(traversable, RES_M)
    assert clearance[10, 10] == pytest.approx(0.0)
    assert clearance[10, 11] == pytest.approx(RES_M)


def test_clearance_map_scales_with_resolution():
    traversable = np.ones((5, 5), dtype=bool)
    traversable[2, 2] = False
    assert clearance_map(traversable, 10.0)[2, 3] == pytest.approx(10.0)
    assert clearance_map(traversable, 40.0)[2, 3] == pytest.approx(40.0)


def test_build_corridor_returns_one_waypoint_per_path_pixel():
    path = [(2, 2), (3, 3), (4, 4), (5, 5)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert isinstance(corridor, Corridor)
    assert len(corridor.waypoints) == len(path)


def test_segment_arrays_have_one_entry_per_segment():
    path = [(2, 2), (3, 3), (4, 4), (5, 5)]
    corridor = build_corridor(path, _grids(), get_rover())
    n_segments = len(path) - 1
    assert len(corridor.half_width_m) == n_segments
    assert len(corridor.max_slope_deg) == n_segments
    assert len(corridor.energy_budget_wh) == n_segments
    assert len(corridor.thermal_budget_K_s) == n_segments


def test_waypoints_are_projected_metres_not_pixels():
    path = [(0, 0), (0, 1)]
    corridor = build_corridor(path, _grids(), get_rover())
    x0, y0 = corridor.waypoints[0]
    x1, y1 = corridor.waypoints[1]
    assert x0 == pytest.approx(156000.0)
    assert y0 == pytest.approx(28000.0)
    assert x1 - x0 == pytest.approx(RES_M)


def test_half_width_is_capped():
    path = [(5, 5), (6, 6), (7, 7)]
    corridor = build_corridor(path, _grids(), get_rover(), max_half_width_m=120.0)
    assert max(corridor.half_width_m) <= 120.0


def test_half_width_shrinks_near_obstacles():
    path = [(5, 5), (6, 6), (7, 7)]
    open_corridor = build_corridor(path, _grids(), get_rover())
    tight_corridor = build_corridor(
        path, _grids(blocked=((6, 7), (7, 8), (5, 6))), get_rover()
    )
    assert min(tight_corridor.half_width_m) < min(open_corridor.half_width_m)


def test_energy_budget_is_positive_and_finite():
    path = [(2, 2), (3, 3), (4, 4)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert all(0.0 < e < float("inf") for e in corridor.energy_budget_wh)


def test_fallback_points_exist_for_every_waypoint():
    path = [(2, 2), (3, 3), (4, 4)]
    corridor = build_corridor(path, _grids(), get_rover())
    assert len(corridor.fallback_points) == len(path)


def test_short_path_of_one_pixel_is_rejected():
    with pytest.raises(ValueError):
        build_corridor([(1, 1)], _grids(), get_rover())
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_corridor.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.corridor'`

- [ ] **Step 3: `schemas.py`'yi uygula**

`backend/app/schemas.py` oluştur:

```python
"""Contracts LunaPath publishes to downstream consumers.

The Corridor is the single interface between LunaPath (global planner,
80 m cells, on the ground) and any local layer (LiDAR/stereo, sub-metre,
on the rover). It travels over both shells: FastAPI JSON and, in Phase 4,
the ROS 2 ``lunapath_msgs/Corridor`` message.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Corridor(BaseModel):
    """What the global planner hands the local planner."""

    waypoints: list[tuple[float, float]] = Field(
        description="Projected CRS metres (x, y), one per path pixel."
    )
    half_width_m: list[float] = Field(
        description="Per-segment permitted lateral deviation."
    )
    max_slope_deg: list[float] = Field(
        description="Per-segment slope ceiling observed along the corridor."
    )
    energy_budget_wh: list[float] = Field(
        description="Per-segment energy allowance."
    )
    thermal_budget_K_s: list[float] = Field(
        description=(
            "Per-segment thermal headroom: inner-temperature margin above the "
            "battery minimum, integrated over segment traversal time (K*s)."
        )
    )
    fallback_points: list[tuple[float, float]] = Field(
        description="Nearest safe-haven point for each waypoint, in CRS metres."
    )
    crs: str = Field(description="CRS the waypoint metres are expressed in.")
```

- [ ] **Step 4: `corridor.py`'yi uygula**

`backend/app/corridor.py` oluştur:

```python
"""Build the Corridor contract from a planned path."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.ndimage import distance_transform_edt

from .cost_engine import edge_energy_wh, edge_travel_time_s, surface_to_inner
from .schemas import Corridor

DEFAULT_SAFE_SHADOW_RATIO: float = 0.2
DEFAULT_MAX_HALF_WIDTH_M: float = 400.0


def clearance_map(traversable: np.ndarray, resolution_m: float) -> np.ndarray:
    """Distance in metres from every cell to the nearest impassable cell."""
    mask = np.asarray(traversable, dtype=bool)
    return distance_transform_edt(mask) * float(resolution_m)


def _pixel_to_metres(
    row: int, col: int, origin_x: float, origin_y: float, resolution_m: float
) -> tuple[float, float]:
    return (origin_x + col * resolution_m, origin_y + row * resolution_m)


def _safe_haven_indices(
    traversable: np.ndarray, shadow_ratio: np.ndarray, safe_shadow_ratio: float
) -> np.ndarray:
    """(2, H, W) index array pointing every cell at its nearest safe cell."""
    safe = np.asarray(traversable, dtype=bool) & (
        np.asarray(shadow_ratio) <= safe_shadow_ratio
    )
    if not safe.any():
        # No lit cell anywhere: fall back to nearest traversable cell.
        safe = np.asarray(traversable, dtype=bool)
    _distance, indices = distance_transform_edt(~safe, return_indices=True)
    return indices


def build_corridor(
    path_pixels: Sequence[tuple[int, int]],
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    safe_shadow_ratio: float = DEFAULT_SAFE_SHADOW_RATIO,
    max_half_width_m: float = DEFAULT_MAX_HALF_WIDTH_M,
) -> Corridor:
    """Turn a pixel path into the contract a local planner can execute."""
    path = [(int(r), int(c)) for r, c in path_pixels]
    if len(path) < 2:
        raise ValueError("a corridor needs at least two waypoints")

    metadata = grids["metadata"]
    resolution_m = float(metadata["resolution_m"])
    origin = metadata.get("origin") or {}
    origin_x = float(origin.get("x", 0.0))
    origin_y = float(origin.get("y", 0.0))

    slope = np.asarray(grids["slope"], dtype=np.float64)
    thermal = np.asarray(grids["thermal"], dtype=np.float64)
    shadow_ratio = np.asarray(grids["shadow_ratio"], dtype=np.float64)
    traversable = np.asarray(grids["traversable"], dtype=bool)

    clearance = clearance_map(traversable, resolution_m)
    safe_indices = _safe_haven_indices(traversable, shadow_ratio, safe_shadow_ratio)
    bat_min_c = float(rover["bat_op_min_c"])

    waypoints = [
        _pixel_to_metres(r, c, origin_x, origin_y, resolution_m) for r, c in path
    ]

    fallback_points: list[tuple[float, float]] = []
    for r, c in path:
        safe_r = int(safe_indices[0, r, c])
        safe_c = int(safe_indices[1, r, c])
        fallback_points.append(
            _pixel_to_metres(safe_r, safe_c, origin_x, origin_y, resolution_m)
        )

    half_width_m: list[float] = []
    max_slope_deg: list[float] = []
    energy_budget_wh: list[float] = []
    thermal_budget_K_s: list[float] = []

    for (r0, c0), (r1, c1) in zip(path[:-1], path[1:]):
        diagonal = (r0 != r1) and (c0 != c1)
        distance_m = resolution_m * (math.sqrt(2.0) if diagonal else 1.0)

        half_width_m.append(
            float(min(min(clearance[r0, c0], clearance[r1, c1]), max_half_width_m))
        )

        segment_slope = float(max(slope[r0, c0], slope[r1, c1]))
        max_slope_deg.append(segment_slope)

        energy_budget_wh.append(
            float(edge_energy_wh(segment_slope, distance_m, rover))
        )

        travel_s = edge_travel_time_s(segment_slope, distance_m, rover)
        inner_c = surface_to_inner(float(thermal[r1, c1]), rover)
        margin_k = max(0.0, inner_c - bat_min_c)
        thermal_budget_K_s.append(
            float(margin_k * travel_s) if math.isfinite(travel_s) else 0.0
        )

    return Corridor(
        waypoints=waypoints,
        half_width_m=half_width_m,
        max_slope_deg=max_slope_deg,
        energy_budget_wh=energy_budget_wh,
        thermal_budget_K_s=thermal_budget_K_s,
        fallback_points=fallback_points,
        crs=str(metadata.get("crs", "unknown")),
    )
```

- [ ] **Step 5: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_corridor.py -v`

Expected: 10 test PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/corridor.py backend/test_corridor.py
git commit -m "feat: build the Corridor contract for local planners"
```

---

### Task 5: `/api/plan` → `corridor` alanı

**Files:**
- Modify: `backend/app/serializer.py` (`build_plan_response`)
- Modify: `backend/app/main.py` (`plan`)
- Test: `backend/test_plan_corridor.py` (create)

**Interfaces:**
- Consumes: `build_corridor` (Task 4)
- Produces: `/api/plan` yanıtına `corridor` alanı (Corridor serileştirilmiş hâli veya `None`). Faz 4 `corridor_publisher.py` bunu tüketir.

- [ ] **Step 1: Başarısız testi yaz**

`backend/test_plan_corridor.py` oluştur:

```python
"""/api/plan corridor field tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (30, 30)


@pytest.fixture()
def client():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.2),
        "traversable": np.ones(SHAPE, dtype=bool),
        "cost": np.full(SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }
    with TestClient(app) as test_client:
        yield test_client
    app.state.grids = None


def _plan(client):
    return client.post(
        "/api/plan",
        json={
            "start": {"row": 2, "col": 2},
            "goal": {"row": 25, "col": 25},
            "include_simulation": True,
        },
    )


def test_plan_response_contains_corridor(client):
    response = _plan(client)
    assert response.status_code == 200
    corridor = response.json()["corridor"]
    assert corridor is not None
    assert len(corridor["waypoints"]) >= 2
    assert len(corridor["half_width_m"]) == len(corridor["waypoints"]) - 1


def test_corridor_waypoints_are_metre_pairs(client):
    corridor = _plan(client).json()["corridor"]
    for point in corridor["waypoints"]:
        assert len(point) == 2
        assert all(isinstance(value, (int, float)) for value in point)


def test_existing_plan_fields_are_untouched(client):
    payload = _plan(client).json()
    for key in ("path_pixels", "metrics"):
        assert key in payload
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_plan_corridor.py -v`

Expected: FAIL — `KeyError: 'corridor'`

- [ ] **Step 3: `build_plan_response`'a parametre ekle**

`backend/app/serializer.py` içinde `build_plan_response` imzasına, son parametre olarak ekle:

```python
    corridor: dict[str, Any] | None = None,
```

ve döndürülen sözlüğe ekle:

```python
        "corridor": corridor,
```

*(Fonksiyonun `return` ifadesindeki mevcut anahtarların hiçbirini değiştirme.)*

- [ ] **Step 4: `main.py`'de koridoru üret**

`backend/app/main.py` import bloğuna ekle:

```python
from .corridor import build_corridor
```

`plan` fonksiyonunda, `return build_plan_response(` çağrısından **önce** ekle:

```python
    try:
        corridor_payload = build_corridor(
            astar_result["path_pixels"], grids_for_plan, rover
        ).model_dump()
    except (ValueError, KeyError) as exc:
        logger.warning("Corridor generation skipped: %s", exc)
        corridor_payload = None
```

ve `build_plan_response(...)` çağrısına son argüman olarak ekle:

```python
            corridor=corridor_payload,
```

- [ ] **Step 5: Testi çalıştır, geçtiğini doğrula**

Run: `cd backend && pytest test_plan_corridor.py test_plan_endpoint.py -v`

Expected: hepsi PASS (mevcut `test_plan_endpoint.py` kırılmamalı).

- [ ] **Step 6: Commit**

```bash
git add backend/app/serializer.py backend/app/main.py backend/test_plan_corridor.py
git commit -m "feat: return the Corridor contract from /api/plan"
```

---

### Task 6: `replan_triggers.py` + `/api/replan`

**Files:**
- Create: `backend/app/replan_triggers.py`
- Modify: `backend/app/main.py`
- Test: `backend/test_replan_triggers.py` (create)

**Interfaces:**
- Consumes: yok (saf fonksiyonlar)
- Produces:
  - `TriggerResult` dataclass: `trigger_id: str`, `triggered: bool`, `detail: str`
  - Altı saf kontrol fonksiyonu (aşağıda)
  - `evaluate_triggers(state: dict) -> list[TriggerResult]`
  - `POST /api/replan` endpoint'i

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_replan_triggers.py` oluştur:

```python
"""Replan trigger taxonomy tests."""

from __future__ import annotations

import pytest

from app.replan_triggers import (
    TriggerResult,
    check_comm_window,
    check_corridor_violation,
    check_inner_temperature,
    check_localization_uncertainty,
    check_soc_deviation,
    check_time_drift,
    evaluate_triggers,
)


def test_soc_deviation_fires_beyond_ten_points():
    assert check_soc_deviation(actual_soc=0.60, planned_soc=0.75).triggered
    assert not check_soc_deviation(actual_soc=0.70, planned_soc=0.75).triggered


def test_soc_deviation_ignores_being_ahead_of_plan():
    assert not check_soc_deviation(actual_soc=0.95, planned_soc=0.75).triggered


def test_inner_temperature_fires_five_kelvin_below_prediction():
    assert check_inner_temperature(actual_c=-6.0, predicted_c=0.0).triggered
    assert not check_inner_temperature(actual_c=-3.0, predicted_c=0.0).triggered


def test_time_drift_fires_after_thirty_minutes():
    assert check_time_drift(drift_minutes=45.0).triggered
    assert check_time_drift(drift_minutes=-45.0).triggered
    assert not check_time_drift(drift_minutes=10.0).triggered


def test_corridor_violation_fires_outside_half_width():
    assert check_corridor_violation(lateral_offset_m=120.0, half_width_m=100.0).triggered
    assert not check_corridor_violation(lateral_offset_m=80.0, half_width_m=100.0).triggered


def test_comm_window_fires_when_closing():
    assert check_comm_window(minutes_remaining=5.0, threshold_minutes=15.0).triggered
    assert not check_comm_window(minutes_remaining=30.0, threshold_minutes=15.0).triggered


def test_localization_uncertainty_fires_above_half_width():
    assert check_localization_uncertainty(
        covariance_m=150.0, half_width_m=100.0
    ).triggered
    assert not check_localization_uncertainty(
        covariance_m=40.0, half_width_m=100.0
    ).triggered


def test_every_trigger_returns_a_named_result():
    result = check_soc_deviation(actual_soc=0.1, planned_soc=0.9)
    assert isinstance(result, TriggerResult)
    assert result.trigger_id == "soc_deviation"
    assert result.detail


def test_evaluate_triggers_returns_only_fired_triggers():
    fired = evaluate_triggers(
        {
            "actual_soc": 0.50,
            "planned_soc": 0.75,
            "actual_inner_c": 0.0,
            "predicted_inner_c": 0.0,
            "drift_minutes": 2.0,
            "lateral_offset_m": 10.0,
            "half_width_m": 100.0,
            "comm_minutes_remaining": 120.0,
            "localization_covariance_m": 5.0,
        }
    )
    assert [r.trigger_id for r in fired] == ["soc_deviation"]


def test_evaluate_triggers_skips_missing_inputs():
    assert evaluate_triggers({}) == []
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_replan_triggers.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.replan_triggers'`

- [ ] **Step 3: `replan_triggers.py`'yi uygula**

`backend/app/replan_triggers.py` oluştur:

```python
"""Replan trigger taxonomy.

ESA ADE's ADAM module changes a nominal plan autonomously when a hazard is
recognised, but published material does not enumerate the triggers. This
module is that enumeration, as pure predicates with unit tests -- the
concrete evidence behind "we do replanning".

Each check is deliberately independent and side-effect free so it can run
on the ground, on the rover, or inside a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

SOC_DEVIATION_THRESHOLD: float = 0.10        # fraction of capacity
INNER_TEMPERATURE_DROP_K: float = 5.0        # kelvin below prediction
TIME_DRIFT_MINUTES: float = 30.0
COMM_WINDOW_MINUTES: float = 15.0


@dataclass(frozen=True)
class TriggerResult:
    trigger_id: str
    triggered: bool
    detail: str


def check_soc_deviation(actual_soc: float, planned_soc: float) -> TriggerResult:
    """Being behind the energy plan forces a replan; being ahead does not."""
    shortfall = float(planned_soc) - float(actual_soc)
    fired = shortfall > SOC_DEVIATION_THRESHOLD
    return TriggerResult(
        "soc_deviation",
        fired,
        f"SOC {actual_soc:.3f} vs planned {planned_soc:.3f} "
        f"(shortfall {shortfall:.3f}, threshold {SOC_DEVIATION_THRESHOLD})",
    )


def check_inner_temperature(actual_c: float, predicted_c: float) -> TriggerResult:
    drop = float(predicted_c) - float(actual_c)
    fired = drop > INNER_TEMPERATURE_DROP_K
    return TriggerResult(
        "inner_temperature",
        fired,
        f"inner {actual_c:.2f} C vs predicted {predicted_c:.2f} C "
        f"(drop {drop:.2f} K, threshold {INNER_TEMPERATURE_DROP_K} K)",
    )


def check_time_drift(drift_minutes: float) -> TriggerResult:
    """Illumination is a function of time; drifting off schedule invalidates it."""
    fired = abs(float(drift_minutes)) > TIME_DRIFT_MINUTES
    return TriggerResult(
        "time_drift",
        fired,
        f"schedule drift {drift_minutes:.1f} min "
        f"(threshold +/-{TIME_DRIFT_MINUTES} min)",
    )


def check_corridor_violation(
    lateral_offset_m: float, half_width_m: float
) -> TriggerResult:
    fired = float(lateral_offset_m) > float(half_width_m)
    return TriggerResult(
        "corridor_violation",
        fired,
        f"lateral offset {lateral_offset_m:.1f} m exceeds "
        f"corridor half-width {half_width_m:.1f} m",
    )


def check_comm_window(
    minutes_remaining: float, threshold_minutes: float = COMM_WINDOW_MINUTES
) -> TriggerResult:
    fired = float(minutes_remaining) < float(threshold_minutes)
    return TriggerResult(
        "comm_window",
        fired,
        f"{minutes_remaining:.1f} min of Earth visibility left "
        f"(threshold {threshold_minutes} min)",
    )


def check_localization_uncertainty(
    covariance_m: float, half_width_m: float
) -> TriggerResult:
    fired = float(covariance_m) > float(half_width_m)
    return TriggerResult(
        "localization_uncertainty",
        fired,
        f"position covariance {covariance_m:.1f} m exceeds "
        f"corridor half-width {half_width_m:.1f} m",
    )


def evaluate_triggers(state: Mapping[str, Any]) -> list[TriggerResult]:
    """Run every check whose inputs are present; return only fired triggers."""
    results: list[TriggerResult] = []

    if "actual_soc" in state and "planned_soc" in state:
        results.append(check_soc_deviation(state["actual_soc"], state["planned_soc"]))
    if "actual_inner_c" in state and "predicted_inner_c" in state:
        results.append(
            check_inner_temperature(state["actual_inner_c"], state["predicted_inner_c"])
        )
    if "drift_minutes" in state:
        results.append(check_time_drift(state["drift_minutes"]))
    if "lateral_offset_m" in state and "half_width_m" in state:
        results.append(
            check_corridor_violation(state["lateral_offset_m"], state["half_width_m"])
        )
    if "comm_minutes_remaining" in state:
        results.append(check_comm_window(state["comm_minutes_remaining"]))
    if "localization_covariance_m" in state and "half_width_m" in state:
        results.append(
            check_localization_uncertainty(
                state["localization_covariance_m"], state["half_width_m"]
            )
        )

    return [result for result in results if result.triggered]
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_replan_triggers.py -v`

Expected: 10 test PASS.

- [ ] **Step 5: `/api/replan` endpoint'ini ekle**

`backend/app/main.py` import bloğuna ekle:

```python
from .replan_triggers import evaluate_triggers
```

`PlanRequest` sınıfının altına ekle:

```python
class ReplanRequest(BaseModel):
    current: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    rover_id: str = DEFAULT_ROVER_ID
    weights: PlanWeights = Field(default_factory=PlanWeights)
    state: dict[str, float] = Field(
        default_factory=dict,
        description="Telemetry snapshot evaluated against the replan triggers.",
    )
    force: bool = False
```

`plan` endpoint'inin altına ekle:

```python
@app.post("/api/replan")
def replan(req: ReplanRequest, request: Request):
    """Re-plan from the rover's current position when a trigger fires."""
    fired = evaluate_triggers(req.state)
    if not fired and not req.force:
        return {
            "replanned": False,
            "triggers": [],
            "reason": "no replan trigger fired",
        }

    plan_request = PlanRequest(
        start=req.current,
        goal=req.goal,
        rover_id=req.rover_id,
        weights=req.weights,
        include_simulation=True,
    )
    payload = plan(plan_request, request)
    return {
        "replanned": True,
        "triggers": [
            {"trigger_id": t.trigger_id, "detail": t.detail} for t in fired
        ],
        "plan": payload,
    }
```

- [ ] **Step 6: Endpoint testini ekle ve çalıştır**

`backend/test_replan_triggers.py` sonuna ekle:

```python
import numpy as np
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

_SHAPE = (30, 30)


@pytest.fixture()
def replan_client():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(_SHAPE),
        "slope": np.full(_SHAPE, 3.0),
        "aspect": np.zeros(_SHAPE),
        "thermal": np.full(_SHAPE, -60.0),
        "shadow_ratio": np.full(_SHAPE, 0.2),
        "traversable": np.ones(_SHAPE, dtype=bool),
        "cost": np.full(_SHAPE, 0.3),
        "metadata": {
            "origin": {"x": 156000.0, "y": 28000.0},
            "resolution_m": 80.0,
            "shape": list(_SHAPE),
            "crs": "test",
            "default_rover_id": rover["id"],
            "cost_weights": {
                "w_slope": 0.409,
                "w_energy": 0.259,
                "w_shadow": 0.142,
                "w_thermal": 0.19,
            },
        },
    }
    with TestClient(app) as test_client:
        yield test_client
    app.state.grids = None


def _body(state: dict) -> dict:
    return {
        "current": {"row": 5, "col": 5},
        "goal": {"row": 25, "col": 25},
        "state": state,
    }


def test_replan_is_a_noop_when_no_trigger_fires(replan_client):
    payload = replan_client.post(
        "/api/replan", json=_body({"actual_soc": 0.8, "planned_soc": 0.82})
    ).json()
    assert payload["replanned"] is False
    assert payload["triggers"] == []


def test_replan_produces_a_new_route_when_a_trigger_fires(replan_client):
    payload = replan_client.post(
        "/api/replan", json=_body({"actual_soc": 0.40, "planned_soc": 0.75})
    ).json()
    assert payload["replanned"] is True
    assert payload["triggers"][0]["trigger_id"] == "soc_deviation"
    assert len(payload["plan"]["path_pixels"]) >= 2
```

Run: `cd backend && pytest test_replan_triggers.py -v`

Expected: 12 test PASS.

- [ ] **Step 7: Tam regresyon ve commit**

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
git add backend/app/replan_triggers.py backend/app/main.py backend/test_replan_triggers.py
git commit -m "feat: add replan trigger taxonomy and /api/replan endpoint"
```

---

## Faz 2 kabul kriterleri

- [ ] `cd backend && pytest` — tüm testler geçiyor
- [ ] `default_cost_map(...).total()` eski `compute_cost_grid()` ile 1e-9 toleransında **aynı** (test kanıtlıyor)
- [ ] `GET /api/cell-telemetry?row=X&col=Y` → `cost_breakdown` dört katmanın katkısını ve toplamı döndürüyor
- [ ] `POST /api/plan` → `corridor` alanı dolu; segment dizileri `len(waypoints) - 1` uzunluğunda
- [ ] `POST /api/replan` tetikleyici yoksa `replanned: false`, tetikleyici varsa yeni rota döndürüyor
- [ ] Altı replan tetikleyicisinin her biri için en az bir birim testi var

## Sonraki adım

Faz 3 — [`2026-08-19-faz3-zaman-ekseni.md`](2026-08-19-faz3-zaman-ekseni.md) · veya paralel: Faz 4 [`2026-08-19-faz4-ros2.md`](2026-08-19-faz4-ros2.md) / Faz 5 [`2026-08-19-faz5-lidar.md`](2026-08-19-faz5-lidar.md)
