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
    assert breakdown["total"] is None


def test_layer_names_are_exposed():
    cost_map = CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("b", 0.5, 0.6)])
    assert cost_map.layer_names() == ["a", "b"]


def test_duplicate_layer_names_are_rejected():
    with pytest.raises(ValueError):
        CostMap([_ConstantLayer("a", 0.5, 0.4), _ConstantLayer("a", 0.5, 0.6)])


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


# ── Faz 2 review fix: C1 -- non-finite contributions must not reach JSON ──


def test_explain_reports_none_instead_of_infinity():
    """inf is not valid JSON; explain must emit None so the API can serialise."""
    ctx = _context(traversable_value=False)
    breakdown = default_cost_map(ctx.rover).explain(0, 0, ctx)
    assert breakdown["total"] is None
    assert all(v is None or np.isfinite(v) for v in breakdown.values())


def test_explain_reports_none_for_nan_inputs():
    ctx = _context()
    ctx.thermal[1, 1] = np.nan
    breakdown = default_cost_map(ctx.rover).explain(1, 1, ctx)
    assert breakdown["thermal"] is None
    assert breakdown["total"] is None


def test_explain_over_slope_limit_is_none_not_inf():
    """f_slope returns inf above slope_max; that must not reach the response."""
    ctx = _context()
    ctx.slope[0, 0] = 40.0  # over the 25 deg limit
    breakdown = default_cost_map(ctx.rover).explain(0, 0, ctx)
    assert breakdown["slope"] is None
    assert breakdown["total"] is None


def test_explain_still_sums_correctly_on_finite_cells():
    """The None path must not disturb ordinary cells."""
    ctx = _random_context()
    cost_map = default_cost_map(ctx.rover)
    row, col = np.argwhere(np.isfinite(cost_map.total(ctx)))[0]
    breakdown = cost_map.explain(int(row), int(col), ctx)
    parts = sum(v for k, v in breakdown.items() if k != "total")
    assert breakdown["total"] == pytest.approx(max(parts, 0.01), abs=1e-9)


# ── Faz 2 review fix: I1 -- explain() must be O(1) in grid size ──


def test_explain_does_not_evaluate_the_whole_grid():
    """explain() must be O(1) in grid size, not O(H*W)."""
    rover = get_rover()
    calls: list[tuple[int, ...]] = []

    class _CountingLayer:
        name = "counting"
        validity = "MODEL"
        weight = 1.0

        def contribution(self, ctx: PlanContext) -> np.ndarray:
            calls.append(np.asarray(ctx.slope).shape)
            return np.zeros(np.asarray(ctx.slope).shape, dtype=np.float64)

    shape = (200, 200)
    ctx = PlanContext(
        slope=np.full(shape, 5.0),
        thermal=np.full(shape, -60.0),
        shadow_ratio=np.full(shape, 0.3),
        traversable=np.ones(shape, dtype=bool),
        resolution_m=5.0,
        rover=rover,
    )
    CostMap([_CountingLayer()]).explain(100, 100, ctx)
    assert calls == [(1, 1)], f"layer saw {calls}, expected a single 1x1 slice"


def test_explain_matches_full_grid_result():
    """The 1x1 shortcut must not change any number."""
    ctx = _random_context()
    cost_map = default_cost_map(ctx.rover)
    total_grid = cost_map.total(ctx)
    for row, col in np.argwhere(np.isfinite(total_grid))[:5]:
        breakdown = cost_map.explain(int(row), int(col), ctx)
        assert breakdown["total"] == pytest.approx(
            float(total_grid[row, col]), abs=1e-9
        )


# ── Faz 2 review fix: I2 -- layer validity must follow the data, not the class ──


def test_layer_validity_follows_metadata_when_supplied():
    """A SYNTHETIC input layer must not be advertised as DERIVED/MODEL."""
    cost_map = default_cost_map(
        get_rover(),
        layer_validity={"shadow_ratio": "SYNTHETIC", "thermal": "SYNTHETIC"},
    )
    by_name = {layer.name: layer.validity for layer in cost_map.layers}
    assert by_name["shadow"] == "SYNTHETIC"
    assert by_name["thermal"] == "SYNTHETIC"


def test_layer_validity_defaults_are_unchanged_without_metadata():
    """Omitting the mapping keeps the previous behaviour."""
    by_name = {l.name: l.validity for l in default_cost_map(get_rover()).layers}
    assert by_name == {
        "slope": "DERIVED",
        "energy": "MODEL",
        "shadow": "DERIVED",
        "thermal": "MODEL",
    }
