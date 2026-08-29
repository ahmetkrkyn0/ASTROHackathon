"""Traversability grid computation — single source of truth.

Determines which grid cells are passable for a selected rover based on
slope and thermal constraints. Both the P1 data pipeline and the backend
API consume this module.
"""

from __future__ import annotations

import numpy as np

from . import constants as C

# Re-exported so callers can do `from app.traversability import
# THERMAL_MIN_TRAVERSABLE_C` -- this module is the documented single source
# of truth for traversability rules, and test_traversability.py already
# imports the constant from here rather than from app.constants (pre-dates
# Faz 1-3; broken since before this branch, tracked as a Faz 1-3 review
# finding since it's one of the three phases' shared acceptance criteria).
THERMAL_MIN_TRAVERSABLE_C = C.THERMAL_MIN_TRAVERSABLE_C


def compute_traversability(
    slope: np.ndarray,
    thermal: np.ndarray,
    rover: dict | None = None,
) -> np.ndarray:
    """Binary traversability mask.

    A cell is impassable (0.0) if ANY of these hold:
        - slope > rover.slope_max_deg
        - thermal < THERMAL_MIN_TRAVERSABLE_C (-150 C)
        - slope or thermal contains NaN

    Returns float64 array: 1.0 = passable, 0.0 = blocked.
    """
    rover_cfg = C.get_rover() if rover is None else rover
    passable = (
        (slope <= float(rover_cfg["slope_max_deg"]))
        & (thermal >= C.THERMAL_MIN_TRAVERSABLE_C)
        & ~np.isnan(slope)
        & ~np.isnan(thermal)
    )
    return passable.astype(np.float64)


def compute_traversability_bool(
    slope: np.ndarray,
    thermal: np.ndarray,
    elevation: np.ndarray | None = None,
    rover: dict | None = None,
) -> np.ndarray:
    """Boolean traversability mask (used by data_loader cache as uint8).

    Same rules as compute_traversability, plus NaN-elevation check
    when elevation array is provided.
    """
    rover_cfg = C.get_rover() if rover is None else rover
    passable = (
        (slope <= float(rover_cfg["slope_max_deg"]))
        & (thermal >= C.THERMAL_MIN_TRAVERSABLE_C)
        & ~np.isnan(slope)
        & ~np.isnan(thermal)
    )
    if elevation is not None:
        passable = passable & ~np.isnan(elevation)
    return passable


_VALIDITY_RANK: dict[str, int] = {
    "SYNTHETIC": 0,
    "DERIVED": 1,
    "MODEL": 2,
    "MEASURED": 3,
}


def weakest_validity(*validities: str) -> str:
    """The least-trustworthy provenance among the given layer_validity values.

    Ranked SYNTHETIC < DERIVED < MODEL < MEASURED. traversable and cost are
    computed FROM other layers (slope, thermal, shadow_ratio), but were
    labelled unconditionally "DERIVED" regardless of what those inputs
    actually were -- so a SYNTHETIC shadow_ratio (the elevation-proxy
    fallback when SPICE kernels are missing) still produced a cost grid
    that claimed a stronger provenance than its own weakest input. This
    makes the label track the real weakest link. Any value not in the
    known rank is treated as the worst case, not silently ignored.
    (Faz 1-2-3 review, L5.)
    """
    if not validities:
        raise ValueError("weakest_validity requires at least one value")
    return min(validities, key=lambda v: _VALIDITY_RANK.get(v, -1))
