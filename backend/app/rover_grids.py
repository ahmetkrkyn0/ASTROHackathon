"""Rover-aware grid adaptation.

Pure core logic: no rclpy, no fastapi. Both shells (the FastAPI backend and
the ROS 2 action server) plan against a *rover-adapted* view of the base
grids, not the raw grids loaded at startup -- different rovers have
different ``slope_max_deg`` (e.g. ``nasa_viper``/``cnsa_yutu_2`` are 20 deg,
``lpr_1`` is 25 deg), so the ``traversable`` mask and ``cost`` grid baked
into the base grids at load time are only correct for the grid's default
rover. This module recomputes both when the requested rover or resolved
weights differ from that default. (Faz 4 final-review finding H1: this used
to live inside ``backend/app/main.py`` -- the FastAPI shell -- so the ROS 2
shell never got the adaptation. It belongs here so both shells call it.)
"""

from __future__ import annotations

from .constants import DEFAULT_ROVER_ID, get_rover
from .cost_engine import compute_cost_grid, resolve_weights
from .traversability import compute_traversability_bool


def grids_for_rover(
    base_grids: dict,
    rover_id: str = DEFAULT_ROVER_ID,
    weights: dict[str, float] | None = None,
) -> dict:
    """Return grids adapted for the selected rover and weights."""
    rover = get_rover(rover_id)
    metadata = dict(base_grids.get("metadata", {}))
    default_rover_id = metadata.get("default_rover_id", DEFAULT_ROVER_ID)
    stored_weights = metadata.get("cost_weights", {})
    resolved_weights = resolve_weights(weights, rover)

    traversable = (
        base_grids["traversable"]
        if rover_id == default_rover_id
        else compute_traversability_bool(
            base_grids["slope"],
            base_grids["thermal"],
            base_grids.get("elevation"),
            rover=rover,
        )
    )

    needs_cost_recompute = rover_id != default_rover_id or resolved_weights != stored_weights
    cost = (
        compute_cost_grid(
            base_grids["slope"],
            base_grids["thermal"],
            base_grids["shadow_ratio"],
            float(metadata["resolution_m"]),
            traversable=traversable,
            weights=resolved_weights,
            rover=rover,
        )
        if needs_cost_recompute
        else base_grids["cost"]
    )

    metadata["cost_weights"] = resolved_weights
    metadata["rover_id"] = rover_id
    metadata["rover_name"] = rover["name"]
    metadata["default_rover_id"] = default_rover_id

    return {
        **base_grids,
        "traversable": traversable,
        "cost": cost,
        "metadata": metadata,
    }
