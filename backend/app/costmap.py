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

    @staticmethod
    def _cell_context(row: int, col: int, ctx: PlanContext) -> PlanContext:
        """A 1x1 view of *ctx* at (row, col).

        Layers vectorise over the whole grid, so evaluating them on the full
        context to read one cell costs O(H*W) -- 1.7 s on the 500x500
        production grid. Slicing first keeps ``explain()`` O(1) in grid size
        without changing the CostLayer protocol. (Faz 2 review, I1.)
        """
        cell = (slice(row, row + 1), slice(col, col + 1))
        return PlanContext(
            slope=np.asarray(ctx.slope)[cell],
            thermal=np.asarray(ctx.thermal)[cell],
            shadow_ratio=np.asarray(ctx.shadow_ratio)[cell],
            traversable=np.asarray(ctx.traversable)[cell],
            resolution_m=ctx.resolution_m,
            rover=ctx.rover,
        )

    def explain(self, row: int, col: int, ctx: PlanContext) -> dict[str, float | None]:
        """Weighted contribution of every layer at one cell, plus the total.

        Non-finite contributions are reported as ``None``, not ``inf``/``nan``:
        this dict is serialised straight into an API response, and Starlette
        renders JSON with ``allow_nan=False``, so a bare ``inf`` raises
        ValueError and turns the whole request into a 500. ``None`` is also
        the convention the rest of this API already uses for unrepresentable
        cell values (see ``main._read_grid_value`` and ``main.get_layer``).
        """
        cell_ctx = self._cell_context(row, col, ctx)

        breakdown: dict[str, float | None] = {}
        running = 0.0
        finite = True
        for layer in self.layers:
            value = float(layer.weight * layer.contribution(cell_ctx)[0, 0])
            if np.isfinite(value):
                breakdown[layer.name] = value
                running += value
            else:
                breakdown[layer.name] = None
                finite = False

        if finite and not bool(self._invalid_mask(cell_ctx)[0, 0]):
            breakdown["total"] = float(max(running, MIN_CELL_COST))
        else:
            breakdown["total"] = None
        return breakdown


from .cost_engine import f_energy_cell, f_shadow_cell, f_slope, f_thermal, resolve_weights

# The scalar penalties in cost_engine are the frozen, validated formulas.
# np.vectorize keeps the layered path bit-identical to the legacy loop.
# Optimising this (see spec: precomputation) is explicitly out of scope.
_f_slope_vec = np.vectorize(f_slope, otypes=[np.float64], excluded={1})
_f_energy_vec = np.vectorize(f_energy_cell, otypes=[np.float64], excluded={1})
_f_shadow_cell_vec = np.vectorize(f_shadow_cell, otypes=[np.float64])
_f_thermal_vec = np.vectorize(f_thermal, otypes=[np.float64], excluded={1})


# Provenance is a property of the DATA, not of the class: the same layer
# reads a real horizon/SPICE grid on the P1 path and an elevation proxy on
# the load-dem path. Hardcoding validity here would let the layer advertise
# physics it did not get -- exactly what layer_validity exists to prevent.
# (Faz 2 review, I2.) The __init__ default preserves the previous behaviour
# when no metadata mapping is passed.


class SlopeLayer:
    name = "slope"

    def __init__(self, weight: float, validity: str = "DERIVED") -> None:
        self.weight = float(weight)
        self.validity = str(validity)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_slope_vec(ctx.slope, ctx.rover)


class EnergyLayer:
    name = "energy"

    def __init__(self, weight: float, validity: str = "MODEL") -> None:
        self.weight = float(weight)
        # Energy's contribution is a physics formula on slope + distance, not
        # an input grid, so it is always MODEL regardless of metadata.
        self.validity = str(validity)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        # Reads slope only: f_energy_cell is a resolution-independent ratio,
        # so the layer no longer rescales with the grid step. (Review #1.)
        return _f_energy_vec(ctx.slope, ctx.rover)


class ShadowLayer:
    name = "shadow"

    def __init__(self, weight: float, validity: str = "DERIVED") -> None:
        self.weight = float(weight)
        self.validity = str(validity)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_shadow_cell_vec(ctx.shadow_ratio)


class ThermalLayer:
    name = "thermal"

    def __init__(self, weight: float, validity: str = "MODEL") -> None:
        self.weight = float(weight)
        self.validity = str(validity)

    def contribution(self, ctx: PlanContext) -> np.ndarray:
        return _f_thermal_vec(ctx.thermal, ctx.rover)


def default_cost_map(
    rover: Mapping[str, Any],
    weights: Mapping[str, float] | None = None,
    layer_validity: Mapping[str, str] | None = None,
) -> CostMap:
    """The four AHP criteria, wired to the rover's weight profile.

    *layer_validity* is the ``metadata["layer_validity"]`` mapping; when
    given, the shadow and thermal layers report the provenance of the grids
    they actually read instead of an optimistic class default.
    """
    resolved = resolve_weights(weights, rover)
    validity = dict(layer_validity or {})
    return CostMap(
        [
            SlopeLayer(resolved["w_slope"], validity.get("slope", "DERIVED")),
            EnergyLayer(resolved["w_energy"], "MODEL"),
            ShadowLayer(resolved["w_shadow"], validity.get("shadow_ratio", "DERIVED")),
            ThermalLayer(resolved["w_thermal"], validity.get("thermal", "MODEL")),
        ]
    )
