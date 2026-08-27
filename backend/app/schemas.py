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
