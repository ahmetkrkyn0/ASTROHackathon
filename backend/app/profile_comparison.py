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
import traceback
from typing import Any, Iterable, Mapping, Optional, Sequence

from .pathfinder import astar
from .rover_grids import grids_for_rover
from .scenarios import MISSION_PROFILES, check_profile_constraints, get_profile
from .simulation import simulate_path, summarize_simulation

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
        except Exception:
            logger.warning(
                "Constraint check skipped for %s: %s",
                result.get("profile_id"),
                traceback.format_exc(),
            )
            summary = None
    result["constraint_check"] = check_profile_constraints(profile, summary)
    result["simulation_summary"] = summary


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
