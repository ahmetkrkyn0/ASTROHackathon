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

import numpy as np

from .constants import DEFAULT_ROVER_ID, get_rover
from .cost_engine import COST_MODEL_ID, compute_cost_grid, resolve_weights
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

    # Recomputed unconditionally rather than trusting the stored mask when the
    # ids happen to match. ``default_rover_id`` is only a LABEL in metadata.json
    # -- nothing guarantees the mask on disk was actually built with that
    # rover's slope_max_deg. When the label disagreed with the mask (a P1 run
    # under a different rover, a hand-edited metadata.json), the planner was
    # handed a mask that called 93,762 cells passable for nasa_viper that its
    # 20 deg limit forbids, and routed over them. slope_max_deg is a safety
    # limit, so it is recomputed from the grids every time -- measured at
    # ~0.05 s on the 500x500 production grid, far below the cost of being
    # wrong. (Backend review, #2.)
    traversable = compute_traversability_bool(
        base_grids["slope"],
        base_grids["thermal"],
        base_grids.get("elevation"),
        rover=rover,
    )

    # The stored cost grid carries the same trust problem as the stored mask:
    # it is only reusable if it was built with THIS rover, THESE weights, and
    # a mask matching the one just recomputed. The id/weight check alone let a
    # mislabelled grid through. Comparing the mask itself closes the gap --
    # a cheap array comparison against a grid we already hold. (Review #2.)
    mask_matches_stored = (
        "traversable" in base_grids
        and np.asarray(base_grids["traversable"], dtype=bool).shape == traversable.shape
        and bool(
            np.array_equal(
                np.asarray(base_grids["traversable"], dtype=bool), traversable
            )
        )
    )
    # A grid whose cost_model is not this build's was computed by an older
    # formula. The P1 .npy set on disk is exactly that after review #1
    # changed the energy term, and reusing it would have kept planning on
    # the inert-energy costs the fix was meant to remove. (Review #5.)
    stored_model = metadata.get("cost_model")
    needs_cost_recompute = (
        rover_id != default_rover_id
        or resolved_weights != stored_weights
        or not mask_matches_stored
        or "cost" not in base_grids
        or stored_model != COST_MODEL_ID
    )
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

    if needs_cost_recompute:
        metadata["cost_model"] = COST_MODEL_ID
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
