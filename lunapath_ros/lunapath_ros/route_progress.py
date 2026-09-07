"""ROS-independent execution accounting for a currently active global path."""

from __future__ import annotations

import math
from typing import Sequence


def polyline_length_m(points: Sequence[tuple[float, float]]) -> float:
    return sum(
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(points, points[1:])
    )


def integrate_displacement_m(
    travelled_m: float,
    previous: tuple[float, float] | None,
    current: tuple[float, float],
) -> tuple[float, tuple[float, float]]:
    """Add finite map-frame odometry displacement without inventing progress."""
    if previous is None:
        return travelled_m, current
    increment = math.hypot(current[0] - previous[0], current[1] - previous[1])
    return travelled_m + increment, current


def energy_used_from_soc_wh(initial_soc_pct: float, current_soc_pct: float, capacity_wh: float) -> float:
    """Estimate consumed energy from two SOC measurements; charging is zero use."""
    return max(0.0, (initial_soc_pct - current_soc_pct) / 100.0 * capacity_wh)
