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
    """Everything a layer may read. Layers must not mutate it.

    *thermal* is the cell's annual PEAK surface temperature and
    *thermal_min* its cold-end equilibrium -- the two ends of the range the
    cell spans (see :mod:`app.thermal_model`). ``thermal_min`` defaults to
    None, in which case every consumer falls back to the peak, which is what
    the whole codebase did before round 4.
    """

    slope: np.ndarray
    thermal: np.ndarray
    shadow_ratio: np.ndarray
    traversable: np.ndarray
    resolution_m: float
    rover: Mapping[str, Any]
    thermal_min: np.ndarray | None = None


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
        invalid = (
            ~np.asarray(ctx.traversable, dtype=bool)
            | np.isnan(ctx.slope)
            | np.isnan(ctx.thermal)
            | np.isnan(ctx.shadow_ratio)
        )
        if ctx.thermal_min is not None:
            invalid = invalid | np.isnan(ctx.thermal_min)
        return invalid

    def total(self, ctx: PlanContext) -> np.ndarray:
        """(H, W) float64 cost grid. Impassable cells are ``inf``."""
        accumulator = np.zeros(np.asarray(ctx.slope).shape, dtype=np.float64)
        for layer in self.layers:
            contribution = np.asarray(layer.contribution(ctx), dtype=np.float64)
            # An infinite contribution means IMPASSABLE, which is not a
            # matter of degree: `0.0 * inf` is NaN, so a layer given zero
            # weight silently erased its own veto and emitted a
            # "invalid value encountered in multiply" warning on the way.
            # Weighting is applied to finite values only.
            # (Round 3 review, L-1.)
            with np.errstate(invalid="ignore"):
                weighted = layer.weight * contribution
            accumulator = accumulator + np.where(
                np.isinf(contribution), contribution, weighted
            )

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
            thermal_min=(
                None if ctx.thermal_min is None
                else np.asarray(ctx.thermal_min)[cell]
            ),
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
            # Same guard as total(): an infinite contribution means
            # IMPASSABLE, and `0.0 * inf` is NaN, so a zero-weighted layer
            # silently erased its own veto and emitted a RuntimeWarning on
            # the way. Round 3 (L-1) fixed this in total() and left the
            # identical expression here untouched. (Round 4 review, L-1.)
            contribution = float(layer.contribution(cell_ctx)[0, 0])
            value = (
                contribution
                if np.isinf(contribution)
                else layer.weight * contribution
            )
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


from .cost_engine import (  # noqa: F401  (scalar forms are the reference)
    f_energy_cell,
    f_shadow_cell,
    f_slope,
    f_thermal,
    resolve_weights,
)
from .cost_vec import (
    f_energy_cell_grid,
    f_shadow_cell_grid,
    f_slope_grid,
    f_thermal_grid,
)

# The scalar penalties in cost_engine remain the frozen, validated formulas;
# app.cost_vec holds true array forms of the same maths. np.vectorize was
# never vectorisation -- it is a Python loop in a wrapper, and it made the
# 500x500 grid cost ~1.5 s per call on the request path.
# test_review_fixes asserts the two forms agree cell for cell. (Review #8.)
_f_slope_vec = f_slope_grid
_f_energy_vec = f_energy_cell_grid
_f_shadow_cell_vec = f_shadow_cell_grid
_f_thermal_vec = f_thermal_grid


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
        # Reads slope AND shadow. f_energy_cell is a resolution-independent
        # ratio, so the layer does not rescale with the grid step (review
        # #1); the shadow term is what stops it from being a monotone
        # restatement of SlopeLayer -- the two penalties were rank-identical
        # before it, so this layer's 0.259 weight expressed no preference of
        # its own. (Round 3 review, H-4.)
        return _f_energy_vec(ctx.slope, ctx.rover, ctx.shadow_ratio)


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
        # Both ends of the cell's temperature range, not just its peak: a
        # cell is only safe if it is survivable at BOTH. (Round 4, H-3.)
        return _f_thermal_vec(ctx.thermal, ctx.rover, ctx.thermal_min)


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
