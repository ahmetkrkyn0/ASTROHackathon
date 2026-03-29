"""Traversability grid computation — single source of truth.

Determines which grid cells are passable based on rover-specific slope
and thermal constraints. Both the P1 data pipeline and the backend API
consume this module.
"""

from __future__ import annotations

import numpy as np

from .constants import get_rover

# Hard-block thresholds (from v3.2 spec)
THERMAL_MIN_TRAVERSABLE_C = -150.0


def compute_traversability(
    slope: np.ndarray,
    thermal: np.ndarray,
    rover_config: dict | None = None,
) -> np.ndarray:
    """Binary traversability mask.

    A cell is impassable (0.0) if ANY of these hold:
        - slope > rover's slope_max_deg
        - thermal < THERMAL_MIN_TRAVERSABLE_C (-150 C)
        - slope or thermal contains NaN

    Returns float64 array: 1.0 = passable, 0.0 = blocked.
    """
    rc = rover_config or get_rover()
    passable = (
        (slope <= rc["slope_max_deg"])
        & (thermal >= THERMAL_MIN_TRAVERSABLE_C)
        & ~np.isnan(slope)
        & ~np.isnan(thermal)
    )
    return passable.astype(np.float64)


def compute_traversability_bool(
    slope: np.ndarray,
    thermal: np.ndarray,
    elevation: np.ndarray | None = None,
    rover_config: dict | None = None,
) -> np.ndarray:
    """Boolean traversability mask (used by data_loader cache as uint8).

    Same rules as compute_traversability, plus NaN-elevation check
    when elevation array is provided.
    """
    rc = rover_config or get_rover()
    passable = (
        (slope <= rc["slope_max_deg"])
        & (thermal >= THERMAL_MIN_TRAVERSABLE_C)
        & ~np.isnan(slope)
        & ~np.isnan(thermal)
    )
    if elevation is not None:
        passable = passable & ~np.isnan(elevation)
    return passable
