# Faz 3 — Zaman Ekseni ve BEKLE Kenarı Implementasyon Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Planlayıcıyı statik snapshot'tan zaman-uzay planlayıcısına çevirmek: `(satır, sütun, zaman_dilimi)` durum uzayı ve **BEKLE kenarı** — rover bir hücrede durup güneşin gelmesini bekleyebilsin.

**Architecture:** Mevcut 2B `astar` **değiştirilmiyor**; yanına `pathfinder_4d.astar_4d` konuyor. 4B planlayıcı, önceden hesaplanmış iki küpü tüketiyor: `cost_cube` (zaman dilimi başına maliyet grid'i) ve `wait_cost_cube` (bir dilim beklemenin maliyeti). Bu ayrım kritik — planlayıcı SPICE'a, heat1d'ye veya aydınlanma hattına bağımlı değil, sadece iki NumPy dizisine bağımlı. Böylece tam olarak test edilebilir.

**Tech Stack:** Python 3.11+ · NumPy 2.2.1 · FastAPI 0.115.6 · pytest

**Spec:** [`docs/research/ENTEGRASYON_TEKNOLOJILERI.md`](../../research/ENTEGRASYON_TEKNOLOJILERI.md) §3.1

**Master plan:** [`2026-08-19-lunapath-master-plan.md`](2026-08-19-lunapath-master-plan.md) — **Global Constraints bölümü bu planın her görevi için geçerlidir.**

**Önkoşul:** Faz 1 (`illumination.py`, `ephemeris.py`, `f_shadow_cell`).

> ⚠️ **Ölçek kısıtı (spec §3.1):** 500×500 × 168 dilim = 42 M durum ≈ 1.3 GB. Bu faz **kaba grid + az dilim** ile çalışır: varsayılan `coarsen=4` (→ 125×125) ve `n_slices=24`. Tam ölçek Faz 2'nin dışıdır.

---

## Faz kapsamı

| Görev | Ne | Süre |
|---|---|---|
| 1 | `cost_cube.py` — aydınlanma serisinden zaman dilimli maliyet küpü | 1.5 gün |
| 2 | `wait_cost` — beklemenin enerji/termal maliyeti | 1 gün |
| 3 | `pathfinder_4d.astar_4d` — durum uzayı + BEKLE kenarı | 2 gün |
| 4 | "Planlayıcı beklemeyi seçti" senaryo testi | 0.5 gün |
| 5 | `/api/plan-4d` endpoint'i | 1 gün |

---

### Task 1: `cost_cube.py` — zaman dilimli maliyet küpü

**Files:**
- Create: `backend/app/cost_cube.py`
- Test: `backend/test_cost_cube.py` (create)

**Interfaces:**
- Consumes: `app.costmap.PlanContext`, `default_cost_map` (Faz 2); `app.illumination.shadow_ratio_from_illumination` (Faz 1)
- Produces:
  - `coarsen_grid(grid, factor, how="mean") -> np.ndarray`
  - `build_cost_cube(base_grids, shadow_ratio_series, rover, weights=None, coarsen=1) -> np.ndarray` — `(T, H', W')` float64
  - `coarsen_traversable(traversable, factor) -> np.ndarray` — bool, **tümü geçilebilirse** geçilebilir (konservatif)
  - Task 3 `astar_4d` bunları tüketir

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_cost_cube.py` oluştur:

```python
"""Time-sliced cost cube tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.cost_cube import build_cost_cube, coarsen_grid, coarsen_traversable

SHAPE = (8, 8)


def _base_grids() -> dict:
    return {
        "slope": np.full(SHAPE, 4.0),
        "thermal": np.full(SHAPE, -60.0),
        "traversable": np.ones(SHAPE, dtype=bool),
        "metadata": {"resolution_m": 80.0, "shape": list(SHAPE)},
    }


def test_coarsen_grid_averages_blocks():
    grid = np.arange(16, dtype=np.float64).reshape(4, 4)
    out = coarsen_grid(grid, factor=2)
    assert out.shape == (2, 2)
    assert out[0, 0] == pytest.approx(np.mean([0, 1, 4, 5]))


def test_coarsen_grid_factor_one_is_identity():
    grid = np.arange(9, dtype=np.float64).reshape(3, 3)
    assert np.array_equal(coarsen_grid(grid, factor=1), grid)


def test_coarsen_grid_rejects_non_divisible_shape():
    with pytest.raises(ValueError):
        coarsen_grid(np.zeros((5, 4)), factor=2)


def test_coarsen_traversable_is_conservative():
    """A coarse cell is passable only if every fine cell inside it is."""
    fine = np.ones((4, 4), dtype=bool)
    fine[0, 0] = False
    out = coarsen_traversable(fine, factor=2)
    assert out.shape == (2, 2)
    assert not out[0, 0]
    assert out[1, 1]


def test_cost_cube_has_one_slice_per_shadow_series_entry():
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube.shape == (3, *SHAPE)


def test_cost_cube_is_monotonic_in_shadow():
    """More shadow at a given cell must never make it cheaper."""
    series = [np.full(SHAPE, r) for r in (0.0, 0.5, 1.0)]
    cube = build_cost_cube(_base_grids(), series, get_rover())
    assert cube[0, 4, 4] < cube[1, 4, 4] < cube[2, 4, 4]


def test_cost_cube_applies_coarsening():
    series = [np.zeros(SHAPE), np.ones(SHAPE)]
    cube = build_cost_cube(_base_grids(), series, get_rover(), coarsen=2)
    assert cube.shape == (2, 4, 4)


def test_cost_cube_rejects_empty_series():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [], get_rover())


def test_cost_cube_rejects_shape_mismatch():
    with pytest.raises(ValueError):
        build_cost_cube(_base_grids(), [np.zeros((4, 4))], get_rover())
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_cost_cube.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.cost_cube'`

- [ ] **Step 3: `cost_cube.py`'yi uygula**

`backend/app/cost_cube.py` oluştur:

```python
"""Time-sliced cost cube for the 4-D planner.

Illumination on the lunar pole changes on the scale of hours, so cost is
not one grid but a stack of them -- one per time slice. Cells whose only
time-varying input is shadow get re-costed per slice; slope, energy and
thermal terms are shared.

Coarsening is not an optimisation, it is a scale decision (spec 3.1):
a 500x500 grid across 168 hourly slices is 42 M states / ~1.3 GB. Solving
time on a coarse grid is correct because illumination does not vary at
80 m resolution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .costmap import PlanContext, default_cost_map


def coarsen_grid(grid: np.ndarray, factor: int, how: str = "mean") -> np.ndarray:
    """Block-reduce a 2-D grid by an integer factor."""
    arr = np.asarray(grid, dtype=np.float64)
    factor = int(factor)
    if factor <= 1:
        return arr
    height, width = arr.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {arr.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = arr.reshape(height // factor, factor, width // factor, factor)
    if how == "mean":
        return np.nanmean(blocks, axis=(1, 3))
    if how == "max":
        return np.nanmax(blocks, axis=(1, 3))
    raise ValueError(f"unknown reduction: {how!r}")


def coarsen_traversable(traversable: np.ndarray, factor: int) -> np.ndarray:
    """Conservative: a coarse cell is passable only if all fine cells are."""
    mask = np.asarray(traversable, dtype=bool)
    factor = int(factor)
    if factor <= 1:
        return mask
    height, width = mask.shape
    if height % factor or width % factor:
        raise ValueError(
            f"shape {mask.shape} is not divisible by coarsen factor {factor}"
        )
    blocks = mask.reshape(height // factor, factor, width // factor, factor)
    return blocks.all(axis=(1, 3))


def build_cost_cube(
    base_grids: Mapping[str, Any],
    shadow_ratio_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
) -> np.ndarray:
    """(T, H', W') cost cube, one slice per shadow-ratio snapshot."""
    if len(shadow_ratio_series) == 0:
        raise ValueError("shadow_ratio_series must contain at least one snapshot")

    slope = np.asarray(base_grids["slope"], dtype=np.float64)
    thermal = np.asarray(base_grids["thermal"], dtype=np.float64)
    traversable = np.asarray(base_grids["traversable"], dtype=bool)
    resolution_m = float(base_grids["metadata"]["resolution_m"])

    for index, snapshot in enumerate(shadow_ratio_series):
        if np.asarray(snapshot).shape != slope.shape:
            raise ValueError(
                f"shadow snapshot {index} has shape {np.asarray(snapshot).shape}, "
                f"expected {slope.shape}"
            )

    slope_c = coarsen_grid(slope, coarsen, how="max")       # worst case per block
    thermal_c = coarsen_grid(thermal, coarsen, how="mean")
    traversable_c = coarsen_traversable(traversable, coarsen)
    resolution_c = resolution_m * max(1, int(coarsen))

    cost_map = default_cost_map(rover, weights)
    slices: list[np.ndarray] = []
    for snapshot in shadow_ratio_series:
        shadow_c = coarsen_grid(np.asarray(snapshot, dtype=np.float64), coarsen)
        context = PlanContext(
            slope=slope_c,
            thermal=thermal_c,
            shadow_ratio=shadow_c,
            traversable=traversable_c,
            resolution_m=resolution_c,
            rover=rover,
        )
        slices.append(cost_map.total(context))

    return np.stack(slices, axis=0)
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_cost_cube.py -v`

Expected: 9 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cost_cube.py backend/test_cost_cube.py
git commit -m "feat: build time-sliced cost cube with conservative coarsening"
```

---

### Task 2: `wait_cost` — beklemenin bedeli

Beklemek bedava değildir. Aydınlıkta beklemek SOC'yi **artırır** (şarj); gölgede beklemek hem SOC hem sıcaklık kaybettirir.

**Files:**
- Modify: `backend/app/cost_cube.py`
- Test: `backend/test_cost_cube.py` (genişlet)

**Interfaces:**
- Consumes: rover sabitleri `p_solar_w`, `p_idle_w`, `p_heater_w`, `e_cap_wh`
- Produces:
  - `wait_cost(illum_frac, dt_hours, rover, weights) -> float`
  - `build_wait_cost_cube(illum_frac_series, rover, dt_hours, weights=None, coarsen=1) -> np.ndarray` — `(T, H', W')`
  - Task 3 `astar_4d` bunu tüketir

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_cost_cube.py` sonuna ekle:

```python
from app.cost_cube import build_wait_cost_cube, wait_cost
from app.cost_engine import resolve_weights


def test_waiting_in_full_sun_is_free():
    """Solar input exceeds idle+heater draw -> no energy penalty."""
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(1.0, 1.0, rover, weights) == pytest.approx(0.0, abs=1e-12)


def test_waiting_in_full_shadow_costs_more_than_in_sun():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 1.0, rover, weights) > wait_cost(1.0, 1.0, rover, weights)


def test_wait_cost_grows_with_duration():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    assert wait_cost(0.0, 2.0, rover, weights) > wait_cost(0.0, 1.0, rover, weights)


def test_wait_cost_is_never_negative():
    rover = get_rover()
    weights = resolve_weights(None, rover)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert wait_cost(frac, 1.0, rover, weights) >= 0.0


def test_wait_cost_cube_shape_matches_series_and_coarsening():
    series = [np.ones(SHAPE), np.zeros(SHAPE)]
    cube = build_wait_cost_cube(series, get_rover(), dt_hours=1.0, coarsen=2)
    assert cube.shape == (2, 4, 4)
    assert (cube[1] > cube[0]).all()
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_cost_cube.py -v`

Expected: FAIL — `ImportError: cannot import name 'wait_cost'`

- [ ] **Step 3: `wait_cost` ve küpünü uygula**

`backend/app/cost_cube.py` sonuna ekle:

```python
from .cost_engine import f_shadow_cell, resolve_weights


def wait_cost(
    illum_frac: float,
    dt_hours: float,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
) -> float:
    """Cost of holding position for one time slice.

    Waiting in sunlight recharges the battery and costs nothing on the
    energy axis; waiting in shadow drains state of charge and accumulates
    shadow exposure. Modelling this is what turns "go faster" into
    "stop, let the Sun come, then cross".
    """
    frac = min(1.0, max(0.0, float(illum_frac)))
    dt = max(0.0, float(dt_hours))

    solar_in_w = float(rover["p_solar_w"]) * frac
    idle_w = float(rover["p_idle_w"])
    heater_w = float(rover["p_heater_w"])
    net_w = solar_in_w - idle_w - heater_w

    delta_soc = net_w * dt / float(rover["e_cap_wh"])
    energy_penalty = max(0.0, -delta_soc)
    shadow_penalty = f_shadow_cell(1.0 - frac) * dt

    return float(
        weights["w_energy"] * energy_penalty + weights["w_shadow"] * shadow_penalty
    )


def build_wait_cost_cube(
    illum_frac_series: Sequence[np.ndarray],
    rover: Mapping[str, Any],
    dt_hours: float,
    weights: Mapping[str, float] | None = None,
    coarsen: int = 1,
) -> np.ndarray:
    """(T, H', W') cost of waiting one slice in each cell at each time."""
    if len(illum_frac_series) == 0:
        raise ValueError("illum_frac_series must contain at least one snapshot")

    resolved = resolve_weights(weights, rover)
    wait_cost_vec = np.vectorize(
        lambda frac: wait_cost(frac, dt_hours, rover, resolved),
        otypes=[np.float64],
    )

    slices = [
        wait_cost_vec(coarsen_grid(np.asarray(frac, dtype=np.float64), coarsen))
        for frac in illum_frac_series
    ]
    return np.stack(slices, axis=0)
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_cost_cube.py -v`

Expected: 14 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cost_cube.py backend/test_cost_cube.py
git commit -m "feat: model the cost of waiting a time slice"
```

---

### Task 3: `pathfinder_4d.astar_4d` — durum uzayı ve BEKLE kenarı

**Files:**
- Create: `backend/app/pathfinder_4d.py`
- Test: `backend/test_pathfinder_4d.py` (create)

**Interfaces:**
- Consumes: `cost_cube` ve `wait_cost_cube` (Task 1–2); `app.cost_engine.edge_travel_time_s`
- Produces: `astar_4d(cost_cube, wait_cost_cube, traversable, start, goal, resolution_m, slice_hours, rover, slope_grid=None) -> dict` — anahtarlar: `path_states: list[tuple[int, int, int]]`, `path_pixels: list[tuple[int, int]]`, `metrics: dict`, `error: str | None`. `metrics` içinde `wait_steps`, `move_steps`, `arrival_slice`, `total_cost`, `nodes_expanded`, `computation_time_ms`.

- [ ] **Step 1: Başarısız testleri yaz**

`backend/test_pathfinder_4d.py` oluştur:

```python
"""4-D (row, col, time) A* tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.constants import get_rover
from app.pathfinder_4d import astar_4d

RES_M = 80.0
SLICE_H = 1.0


def _uniform_case(n_slices=6, shape=(1, 4), cost=0.01, wait=0.01):
    cost_cube = np.full((n_slices, *shape), cost, dtype=np.float64)
    wait_cube = np.full((n_slices, *shape), wait, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def _run(cost_cube, wait_cube, traversable, start=(0, 0), goal=(0, 3)):
    return astar_4d(
        cost_cube,
        wait_cube,
        traversable,
        start=start,
        goal=goal,
        resolution_m=RES_M,
        slice_hours=SLICE_H,
        rover=get_rover(),
    )


def test_finds_a_direct_path_on_a_uniform_cube():
    result = _run(*_uniform_case())
    assert result["error"] is None
    assert result["path_pixels"][0] == (0, 0)
    assert result["path_pixels"][-1] == (0, 3)
    assert result["metrics"]["wait_steps"] == 0


def test_path_states_carry_monotonically_increasing_time():
    result = _run(*_uniform_case())
    times = [t for _, _, t in result["path_states"]]
    assert times == sorted(times)
    assert times[0] == 0


def test_blocked_goal_returns_an_error():
    cost_cube, wait_cube, traversable = _uniform_case()
    traversable[0, 3] = False
    result = _run(cost_cube, wait_cube, traversable)
    assert result["error"] is not None
    assert result["path_pixels"] == []


def test_out_of_bounds_start_returns_an_error():
    result = _run(*_uniform_case(), start=(0, 9))
    assert result["error"] is not None


def test_exhausted_time_horizon_returns_an_error():
    """Two slices cannot cover a three-move path."""
    result = _run(*_uniform_case(n_slices=2))
    assert result["error"] is not None


def test_metrics_report_expansion_and_timing():
    result = _run(*_uniform_case())
    assert result["metrics"]["nodes_expanded"] > 0
    assert result["metrics"]["computation_time_ms"] >= 0.0
    assert result["metrics"]["move_steps"] == 3
    assert result["metrics"]["arrival_slice"] >= 3
```

- [ ] **Step 2: Testleri çalıştır, başarısız olduklarını doğrula**

Run: `cd backend && pytest test_pathfinder_4d.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'app.pathfinder_4d'`

- [ ] **Step 3: `pathfinder_4d.py`'yi uygula**

`backend/app/pathfinder_4d.py` oluştur:

```python
"""Time-expanded A*: states are (row, col, time_slice).

Two edge families:

* MOVE  (r, c, t) -> (r', c', t + dt)   dt = ceil(travel_time / slice_hours)
* WAIT  (r, c, t) -> (r,  c,  t + 1)

The WAIT edge is the point of the whole thing. On the lunar pole the right
answer is often "stop, let the Sun come, then cross" -- a decision a static
planner cannot express.

The 2-D ``app.pathfinder.astar`` is untouched; this is an additional
planner, not a replacement.
"""

from __future__ import annotations

import heapq
import math
import time
from collections.abc import Mapping
from typing import Any

import numpy as np

from .cost_engine import edge_travel_time_s

_OFFSETS: tuple[tuple[int, int, bool], ...] = (
    (-1, 0, False), (1, 0, False), (0, -1, False), (0, 1, False),
    (-1, -1, True), (-1, 1, True), (1, -1, True), (1, 1, True),
)


def _empty(error: str, elapsed_ms: float = 0.0) -> dict[str, Any]:
    return {
        "path_states": [],
        "path_pixels": [],
        "metrics": {
            "wait_steps": 0,
            "move_steps": 0,
            "arrival_slice": None,
            "total_cost": float("inf"),
            "nodes_expanded": 0,
            "computation_time_ms": round(elapsed_ms, 3),
        },
        "error": error,
    }


def astar_4d(
    cost_cube: np.ndarray,
    wait_cost_cube: np.ndarray,
    traversable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    resolution_m: float,
    slice_hours: float,
    rover: Mapping[str, Any],
    slope_grid: np.ndarray | None = None,
) -> dict[str, Any]:
    """Plan through space and time. Returns path_states, path_pixels, metrics."""
    t0 = time.perf_counter()

    cost = np.asarray(cost_cube, dtype=np.float64)
    wait = np.asarray(wait_cost_cube, dtype=np.float64)
    passable = np.asarray(traversable, dtype=bool)

    if cost.ndim != 3:
        return _empty("cost_cube must be (T, H, W)")
    if wait.shape != cost.shape:
        return _empty("wait_cost_cube shape must match cost_cube")
    n_slices, height, width = cost.shape
    if passable.shape != (height, width):
        return _empty("traversable shape must match cost_cube slices")

    def in_bounds(r: int, c: int) -> bool:
        return 0 <= r < height and 0 <= c < width

    if not in_bounds(*start):
        return _empty("Start out of bounds")
    if not in_bounds(*goal):
        return _empty("Goal out of bounds")
    if not passable[start]:
        return _empty("Start is not traversable")
    if not passable[goal]:
        return _empty("Goal is not traversable")

    slopes = (
        np.zeros((height, width), dtype=np.float64)
        if slope_grid is None
        else np.asarray(slope_grid, dtype=np.float64)
    )

    finite = cost[np.isfinite(cost)]
    min_cost = float(np.min(finite)) if finite.size else 0.01
    diag_m = resolution_m * math.sqrt(2.0)

    def heuristic(r: int, c: int) -> float:
        dr, dc = abs(r - goal[0]), abs(c - goal[1])
        straight, diagonal = abs(dr - dc), min(dr, dc)
        return (straight * resolution_m + diagonal * diag_m) * (1.0 + min_cost)

    start_state = (start[0], start[1], 0)
    g_score: dict[tuple[int, int, int], float] = {start_state: 0.0}
    came_from: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    closed: set[tuple[int, int, int]] = set()
    counter = 0
    heap: list[tuple[float, float, int, tuple[int, int, int]]] = [
        (heuristic(*start), 0.0, counter, start_state)
    ]
    nodes_expanded = 0
    goal_state: tuple[int, int, int] | None = None

    while heap:
        _f, _h, _n, state = heapq.heappop(heap)
        if state in closed:
            continue
        closed.add(state)
        nodes_expanded += 1

        row, col, slice_index = state
        if (row, col) == goal:
            goal_state = state
            break

        current_g = g_score[state]

        # WAIT edge
        if slice_index + 1 < n_slices:
            wait_state = (row, col, slice_index + 1)
            tentative = current_g + float(wait[slice_index, row, col])
            if math.isfinite(tentative) and tentative < g_score.get(
                wait_state, math.inf
            ):
                g_score[wait_state] = tentative
                came_from[wait_state] = state
                counter += 1
                h = heuristic(row, col)
                heapq.heappush(heap, (tentative + h, h, counter, wait_state))

        # MOVE edges
        for d_row, d_col, diagonal in _OFFSETS:
            nr, nc = row + d_row, col + d_col
            if not in_bounds(nr, nc) or not passable[nr, nc]:
                continue

            distance_m = diag_m if diagonal else resolution_m
            travel_s = edge_travel_time_s(float(slopes[nr, nc]), distance_m, rover)
            if not math.isfinite(travel_s):
                continue
            d_slices = max(1, int(math.ceil(travel_s / 3600.0 / slice_hours)))
            arrival = slice_index + d_slices
            if arrival >= n_slices:
                continue

            from_cost = cost[slice_index, row, col]
            to_cost = cost[arrival, nr, nc]
            if not (math.isfinite(from_cost) and math.isfinite(to_cost)):
                continue

            step = distance_m * (1.0 + 0.5 * (from_cost + to_cost))
            neighbour = (nr, nc, arrival)
            tentative = current_g + step
            if tentative < g_score.get(neighbour, math.inf):
                g_score[neighbour] = tentative
                came_from[neighbour] = state
                counter += 1
                h = heuristic(nr, nc)
                heapq.heappush(heap, (tentative + h, h, counter, neighbour))

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if goal_state is None:
        return _empty("No path found within the time horizon", elapsed_ms)

    states: list[tuple[int, int, int]] = [goal_state]
    while states[-1] in came_from:
        states.append(came_from[states[-1]])
    states.reverse()

    wait_steps = sum(
        1
        for previous, current in zip(states[:-1], states[1:])
        if previous[:2] == current[:2]
    )

    return {
        "path_states": states,
        "path_pixels": [(r, c) for r, c, _ in states],
        "metrics": {
            "wait_steps": wait_steps,
            "move_steps": len(states) - 1 - wait_steps,
            "arrival_slice": goal_state[2],
            "total_cost": round(g_score[goal_state], 6),
            "nodes_expanded": nodes_expanded,
            "computation_time_ms": round(elapsed_ms, 3),
        },
        "error": None,
    }
```

- [ ] **Step 4: Testleri çalıştır, geçtiklerini doğrula**

Run: `cd backend && pytest test_pathfinder_4d.py -v`

Expected: 6 test PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/pathfinder_4d.py backend/test_pathfinder_4d.py
git commit -m "feat: add time-expanded A* with a WAIT edge"
```

---

### Task 4: "Planlayıcı beklemeyi seçti" senaryosu

Spec §3.1'in kabul kriteri: *bir senaryoda planlayıcı beklemeyi seçtiğini gösteriyor*. Bu görev o kanıtı bir teste dönüştürür.

**Files:**
- Test: `backend/test_pathfinder_4d.py` (genişlet)

**Interfaces:**
- Consumes: `astar_4d` (Task 3)
- Produces: yeni kod yok — davranış kanıtı

- [ ] **Step 1: Bekleme senaryosu testini yaz**

`backend/test_pathfinder_4d.py` sonuna ekle:

```python
def _shadow_then_sun_case():
    """A 1x4 corridor whose middle is expensive until slice 3.

    Sitting still at the start is nearly free (lit, charging), so the
    cheapest plan is: wait for the Sun, then cross.
    """
    n_slices, shape = 8, (1, 4)
    cost_cube = np.full((n_slices, *shape), 0.01, dtype=np.float64)
    cost_cube[:3, 0, 1] = 40.0
    cost_cube[:3, 0, 2] = 40.0
    wait_cube = np.full((n_slices, *shape), 0.001, dtype=np.float64)
    traversable = np.ones(shape, dtype=bool)
    return cost_cube, wait_cube, traversable


def test_planner_chooses_to_wait_for_the_sun():
    result = _run(*_shadow_then_sun_case())
    assert result["error"] is None
    assert result["metrics"]["wait_steps"] > 0, "planner should hold for the Sun"
    assert result["path_pixels"][-1] == (0, 3)


def test_waiting_plan_is_cheaper_than_crossing_immediately():
    """Sanity: the wait is an optimisation, not an artefact."""
    cost_cube, wait_cube, traversable = _shadow_then_sun_case()
    waited = _run(cost_cube, wait_cube, traversable)

    # Same cube, but waiting is made prohibitively expensive.
    expensive_wait = np.full_like(wait_cube, 1e6)
    rushed = _run(cost_cube, expensive_wait, traversable)

    assert waited["metrics"]["wait_steps"] > 0
    assert rushed["metrics"]["wait_steps"] == 0
    assert waited["metrics"]["total_cost"] < rushed["metrics"]["total_cost"]


def test_planner_does_not_wait_when_there_is_nothing_to_gain():
    """A uniformly cheap cube must produce a straight, wait-free plan."""
    result = _run(*_uniform_case(n_slices=8))
    assert result["metrics"]["wait_steps"] == 0
```

- [ ] **Step 2: Testleri çalıştır ve geçtiklerini doğrula**

Run: `cd backend && pytest test_pathfinder_4d.py -v`

Expected: 9 test PASS. `test_planner_chooses_to_wait_for_the_sun` geçmezse `astar_4d`'deki BEKLE kenarını incele — bu test fazın **ana çıktısıdır**.

- [ ] **Step 3: Commit**

```bash
git add backend/test_pathfinder_4d.py
git commit -m "test: prove the 4-D planner chooses to wait for illumination"
```

---

### Task 5: `/api/plan-4d` endpoint'i

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/test_plan_4d_endpoint.py` (create)

**Interfaces:**
- Consumes: `build_cost_cube`, `build_wait_cost_cube` (Task 1–2), `astar_4d` (Task 3)
- Produces: `POST /api/plan-4d` — istek `Plan4DRequest`, yanıt `path_pixels`, `path_states`, `metrics`, `n_slices`, `slice_hours`, `coarsen`

- [ ] **Step 1: Başarısız testi yaz**

`backend/test_plan_4d_endpoint.py` oluştur:

```python
"""/api/plan-4d endpoint tests."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.constants import get_rover
from app.main import app

SHAPE = (16, 16)


@pytest.fixture()
def client():
    rover = get_rover()
    app.state.grids = {
        "elevation": np.zeros(SHAPE),
        "slope": np.full(SHAPE, 3.0),
        "aspect": np.zeros(SHAPE),
        "thermal": np.full(SHAPE, -60.0),
        "shadow_ratio": np.full(SHAPE, 0.3),
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


def _body(**overrides) -> dict:
    body = {
        "start": {"row": 0, "col": 0},
        "goal": {"row": 12, "col": 12},
        "n_slices": 24,
        "slice_hours": 1.0,
        "coarsen": 4,
    }
    body.update(overrides)
    return body


def test_plan_4d_returns_a_path(client):
    response = client.post("/api/plan-4d", json=_body())
    assert response.status_code == 200
    payload = response.json()
    assert payload["path_pixels"]
    assert payload["metrics"]["arrival_slice"] is not None


def test_plan_4d_reports_wait_steps(client):
    payload = client.post("/api/plan-4d", json=_body()).json()
    assert "wait_steps" in payload["metrics"]


def test_plan_4d_echoes_time_configuration(client):
    payload = client.post("/api/plan-4d", json=_body(n_slices=12)).json()
    assert payload["n_slices"] == 12
    assert payload["slice_hours"] == 1.0
    assert payload["coarsen"] == 4


def test_plan_4d_rejects_non_divisible_coarsen(client):
    response = client.post("/api/plan-4d", json=_body(coarsen=5))
    assert response.status_code == 422
```

- [ ] **Step 2: Testi çalıştır, başarısız olduğunu doğrula**

Run: `cd backend && pytest test_plan_4d_endpoint.py -v`

Expected: FAIL — 404 Not Found

- [ ] **Step 3: Endpoint'i uygula**

`backend/app/main.py` import bloğuna ekle:

```python
from .cost_cube import build_cost_cube, build_wait_cost_cube, coarsen_grid
from .pathfinder_4d import astar_4d
```

`ReplanRequest` sınıfının altına ekle:

```python
class Plan4DRequest(BaseModel):
    start: Union[StartGoalPixel, StartGoalGeo]
    goal: Union[StartGoalPixel, StartGoalGeo]
    rover_id: str = DEFAULT_ROVER_ID
    weights: PlanWeights = Field(default_factory=PlanWeights)
    n_slices: int = Field(default=24, ge=2, le=168)
    slice_hours: float = Field(default=1.0, gt=0.0, le=24.0)
    coarsen: int = Field(default=4, ge=1, le=16)
```

`replan` endpoint'inin altına ekle:

```python
@app.post("/api/plan-4d")
def plan_4d(req: Plan4DRequest, request: Request):
    """Plan through space AND time, with an explicit WAIT decision."""
    grids = _active_grids(request)
    rover = get_rover(req.rover_id)
    weights_dict = req.weights.model_dump()
    grids_for_plan = _grids_for_rover(grids, req.rover_id, weights_dict)
    metadata = grids_for_plan["metadata"]

    rows, cols = int(metadata["shape"][0]), int(metadata["shape"][1])
    if rows % req.coarsen or cols % req.coarsen:
        raise HTTPException(
            status_code=422,
            detail=f"grid {rows}x{cols} is not divisible by coarsen={req.coarsen}",
        )

    start = _to_pixel(req.start, "start", metadata)
    goal = _to_pixel(req.goal, "goal", metadata)

    # Until the SPICE-driven illumination cube lands, hold shadow constant
    # across slices: the planner machinery is exercised, the physics is not
    # invented. Replace this series with app.illumination output per slice.
    base_shadow = np.asarray(grids_for_plan["shadow_ratio"], dtype=np.float64)
    shadow_series = [base_shadow] * req.n_slices
    illum_series = [1.0 - base_shadow] * req.n_slices

    cost_cube = build_cost_cube(
        grids_for_plan, shadow_series, rover, weights_dict, coarsen=req.coarsen
    )
    wait_cube = build_wait_cost_cube(
        illum_series, rover, req.slice_hours, weights_dict, coarsen=req.coarsen
    )
    from .cost_cube import coarsen_traversable

    result = astar_4d(
        cost_cube,
        wait_cube,
        coarsen_traversable(grids_for_plan["traversable"], req.coarsen),
        start=(start[0] // req.coarsen, start[1] // req.coarsen),
        goal=(goal[0] // req.coarsen, goal[1] // req.coarsen),
        resolution_m=float(metadata["resolution_m"]) * req.coarsen,
        slice_hours=req.slice_hours,
        rover=rover,
        slope_grid=coarsen_grid(grids_for_plan["slope"], req.coarsen, how="max"),
    )
    if result["error"]:
        raise HTTPException(status_code=404, detail=result["error"])

    return {
        "path_pixels": result["path_pixels"],
        "path_states": result["path_states"],
        "metrics": result["metrics"],
        "n_slices": req.n_slices,
        "slice_hours": req.slice_hours,
        "coarsen": req.coarsen,
        "rover_id": req.rover_id,
    }
```

- [ ] **Step 4: Testi çalıştır, geçtiğini doğrula**

Run: `cd backend && pytest test_plan_4d_endpoint.py -v`

Expected: 4 test PASS.

- [ ] **Step 5: Tam regresyon ve commit**

```bash
cd backend && pytest -v
python test_cost_engine.py
python test_traversability.py
git add backend/app/main.py backend/test_plan_4d_endpoint.py
git commit -m "feat: add /api/plan-4d time-expanded planning endpoint"
```

---

## Faz 3 kabul kriterleri

- [ ] `cd backend && pytest` — tüm testler geçiyor
- [ ] `test_planner_chooses_to_wait_for_the_sun` geçiyor — **fazın ana çıktısı**
- [ ] `test_waiting_plan_is_cheaper_than_crossing_immediately` geçiyor (bekleme bir optimizasyon, artefakt değil)
- [ ] `POST /api/plan-4d` çalışıyor ve `metrics.wait_steps` döndürüyor
- [ ] 2B `astar` ve `/api/plan` davranışı **hiç değişmemiş**

## Bilinen sınır

`/api/plan-4d` şu an gölge oranını dilimler boyunca **sabit** tutuyor. Gerçek zaman-değişken aydınlanma için `app.ephemeris.sun_track` + `app.illumination.illumination_fraction` dilim başına çağrılmalı; bu SPICE çekirdekleri gerektirdiği için endpoint'te değil, offline hatta (`process_lunar_data.py`) üretilip `.npy` küpü olarak yüklenmelidir. Planlayıcı tarafı buna hazır — tek eksik veri üretimi.

## Sonraki adım

Faz 6 — [`2026-08-19-faz6-dogrulama.md`](2026-08-19-faz6-dogrulama.md) · veya paralel: Faz 4 / Faz 5
