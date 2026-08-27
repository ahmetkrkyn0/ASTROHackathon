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
