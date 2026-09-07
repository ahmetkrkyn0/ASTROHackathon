"""Side-effect-free comparison of one start/goal under every mission profile.

Lifted out of the /api/compare and /api/plan-multi route bodies so the AI
tool layer runs the SAME arithmetic rather than a second implementation of
it. Two implementations of a profile comparison would drift, and the one the
assistant quotes would stop matching the one the map draws.

Nothing here writes application state. Each profile derives its own adapted
grids through ``grids_for_rover``, which returns a new dict and a copied
metadata mapping, so the caller's grids come back untouched -- which is why
the assistant is allowed to run this and is not allowed to run /api/plan.
"""

from __future__ import annotations

import logging
import math
import traceback
from typing import Any, Iterable, Mapping, Optional, Sequence

from .cost_engine import edge_travel_time_s
from .pathfinder import astar
from .rover_grids import grids_for_rover
from .safety_monitor import evaluate_catalogue, trace_from_states
from .scenarios import MISSION_PROFILES, check_profile_constraints, get_profile
from .simulation import simulate_path, summarize_simulation
from .slip_model import route_slip_summary

logger = logging.getLogger(__name__)


def attach_constraint_check(
    result: dict, profile: dict, grids: dict, rover: dict
) -> None:
    """Simulate a profile's route and record which declared limits it met.

    ``max_shadow_h``, ``max_energy_wh`` and ``min_soc`` are path-dependent,
    so they cannot be enforced inside the search -- but they CAN be checked
    against the route that came out, and until round 4 nothing did: three of
    the four constraints every mission profile publishes appeared nowhere
    outside scenarios.py. The simulation is the same one /api/plan runs and
    costs well under a second on the production grid. (Round 4 review, M-4.)
    """
    summary = None
    if not result.get("error") and result.get("path_pixels"):
        try:
            states = simulate_path(
                result,
                grids["cost"],
                grids["slope"],
                grids["thermal"],
                grids["shadow_ratio"],
                rover=rover,
                pixel_size_m=float(grids["metadata"]["resolution_m"]),
                elevation_grid=grids["elevation"],
            )
            summary = summarize_simulation(states, rover)
            # The formal, margin-bearing version of the same verdicts (D3):
            # the boolean constraint_check stays as it was; this adds rho.
            safety_block = _safety_margins(states, result["path_pixels"], grids, rover)
            if safety_block is not None:
                result["safety_margins"] = safety_block
            # And the slip the route paid for (C3).
            result["slip_model"] = _slip_block(states, rover)
        except Exception:
            logger.warning(
                "Constraint check skipped for %s: %s",
                result.get("profile_id"),
                traceback.format_exc(),
            )
            summary = None
    result["constraint_check"] = check_profile_constraints(profile, summary)
    result["simulation_summary"] = summary


def _safety_margins(
    states: list, planned_pixels: list, grids: dict, rover: dict
) -> Optional[dict[str, Any]]:
    """``safety_margins`` for a simulated 2-D route; None (logged) if the
    monitor itself fails -- a monitor bug must not take the comparison down.

    The same block ``/api/plan`` publishes, computed here rather than in the
    FastAPI shell so /api/compare, /api/plan-multi and the assistant's tool
    all get it from the one place that solves a profile.
    """
    try:
        trace = trace_from_states(
            states,
            [(int(r), int(c)) for r, c in planned_pixels],
            grids.get("elevation"),
            float(grids["metadata"]["resolution_m"]),
            rover,
        )
        return evaluate_catalogue(trace, rover)
    except Exception:  # noqa: BLE001 - reported, never fatal
        logger.error("Safety monitor failed on the 2-D trace:\n%s", traceback.format_exc())
        return None


def _slip_block(states: list, rover: Mapping[str, Any]) -> dict[str, Any]:
    """``slip_model`` for a simulated 2-D route (C3): one leg per driven
    step, priced at the grade the simulator drove (the worse of the cell and
    the segment slope) with its own time and drawn energy."""
    legs = []
    for previous, current in zip(states[:-1], states[1:]):
        distance = float(current.distance_m) - float(previous.distance_m)
        if distance <= 0.0:
            continue
        drive_slope = max(float(current.slope_deg), float(current.segment_slope_deg))
        seconds = edge_travel_time_s(drive_slope, distance, rover)
        hours = seconds / 3600.0 if math.isfinite(seconds) else float("inf")
        legs.append((drive_slope, distance, hours, float(current.step_energy_wh)))
    return route_slip_summary(legs, rover)


def solve_profile(
    base_grids: dict,
    start: Sequence[int],
    goal: Sequence[int],
    rover_id: str,
    rover: Mapping[str, Any],
    profile_id: str,
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """One profile's route, its metrics, and its constraint verdicts."""
    grids = grids_for_rover(base_grids, rover_id, profile["weights"])
    result = astar(
        grids,
        tuple(start),
        tuple(goal),
        weights=profile["weights"],
        constraints=profile["constraints"],
        rover=rover,
    )
    result["profile_id"] = profile_id
    result["profile_name"] = profile["name"]
    result["color"] = profile["color"]
    attach_constraint_check(result, profile, grids, rover)
    return result


def compare_all_profiles(
    base_grids: dict,
    start: Sequence[int],
    goal: Sequence[int],
    rover_id: str,
    rover: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Every mission profile solved over the same endpoints.

    Endpoints are assumed already validated: /api/compare answers 422 through
    its own HTTP validator and the AI tool raises its own typed error, so
    neither idiom is imposed on the other.
    """
    return [
        solve_profile(
            base_grids, start, goal, rover_id, rover, profile_id, profile
        )
        for profile_id, profile in MISSION_PROFILES.items()
    ]


def solve_named_profiles(
    base_grids: dict,
    start: Sequence[int],
    goal: Sequence[int],
    rover_id: str,
    rover: Mapping[str, Any],
    profile_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """The caller's chosen profiles, with an unknown id reported in place.

    An unknown id is a result entry carrying an ``error`` rather than an
    exception, because one bad id in a list of four should not discard the
    three that solved.
    """
    results: list[dict[str, Any]] = []
    for profile_id in profile_ids:
        profile: Optional[Mapping[str, Any]] = get_profile(profile_id)
        if profile is None:
            results.append(
                {
                    "profile_id": profile_id,
                    "profile_name": None,
                    "color": "#64748B",
                    "path_pixels": [],
                    "metrics": {},
                    "error": f"Unknown profile: {profile_id}",
                }
            )
            continue
        results.append(
            solve_profile(
                base_grids, start, goal, rover_id, rover, profile_id, profile
            )
        )
    return results
