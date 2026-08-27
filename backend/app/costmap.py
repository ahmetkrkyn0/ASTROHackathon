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
