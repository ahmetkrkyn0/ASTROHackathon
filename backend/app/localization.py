"""Where the rover is inside its corridor.

``replan_triggers`` has always been able to check ``corridor_violation``
and ``localization_uncertainty``, but nothing produced their inputs --
``lateral_offset_m`` and ``half_width_m`` were hand-fed in tests and had
no source in production. This module is that source: it projects a
PoseEstimate onto a Corridor and reports where on the route the pose
sits, how far off the centreline it is, and which segment's half-width
applies there.

Geometry only. Nothing here decides whether to replan -- that stays in
replan_triggers, which this module feeds via ``trigger_state_from_pose``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Any

from .pose import PoseEstimate
from .schemas import Corridor


@dataclass(frozen=True)
class CorridorFix:
    """A pose located against a corridor."""

    segment_index: int
    lateral_offset_m: float
    along_track_m: float
    progress_fraction: float
    half_width_at_pose_m: float
    inside: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _project_point_on_segment(
    px: float, py: float, ax: float, ay: float, bx: float, by: float
) -> tuple[float, float]:
    """Project P onto segment AB.

    Returns ``(t, distance)`` where ``t`` is the clamped position along
    AB in [0, 1] and ``distance`` is the perpendicular distance from P to
    that clamped point.

    Clamping is what makes the projection continuous at segment joins: an
    unclamped projection would place a pose near a corner beyond the end
    of one segment and before the start of the next, and the minimum over
    segments would jump. With clamping, a pose past the end of segment i
    projects onto its endpoint -- the same point segment i+1 starts from --
    so the reported offset is identical whichever segment wins.
    """
    abx, aby = bx - ax, by - ay
    length_sq = abx * abx + aby * aby
    if length_sq == 0.0:
        # Degenerate segment (repeated waypoint): the whole segment is one
        # point, so every pose projects onto it at t = 0.
        return 0.0, math.hypot(px - ax, py - ay)

    t = ((px - ax) * abx + (py - ay) * aby) / length_sq
    t = min(1.0, max(0.0, t))
    cx, cy = ax + t * abx, ay + t * aby
    return t, math.hypot(px - cx, py - cy)


def project_onto_corridor(pose: PoseEstimate, corridor: Corridor) -> CorridorFix:
    """Locate *pose* against *corridor*.

    Picks the segment whose centreline the pose is closest to. Ties (a
    pose exactly equidistant from two segments, which happens at a corner)
    resolve to the earlier segment, so the answer is deterministic rather
    than dependent on floating-point noise.
    """
    waypoints = corridor.waypoints
    if len(waypoints) < 2:
        raise ValueError("a corridor needs at least two waypoints to project onto")
    if len(corridor.half_width_m) != len(waypoints) - 1:
        raise ValueError(
            f"corridor has {len(waypoints)} waypoints but "
            f"{len(corridor.half_width_m)} half-widths; expected "
            f"{len(waypoints) - 1}"
        )

    # Cumulative arc length at the start of each segment, so along_track_m
    # is measured along the route rather than as straight-line distance.
    segment_lengths: list[float] = []
    for (ax, ay), (bx, by) in zip(waypoints[:-1], waypoints[1:]):
        segment_lengths.append(math.hypot(bx - ax, by - ay))
    total_length = sum(segment_lengths)

    best_index = 0
    best_t = 0.0
    best_distance = float("inf")
    for i, ((ax, ay), (bx, by)) in enumerate(zip(waypoints[:-1], waypoints[1:])):
        t, distance = _project_point_on_segment(pose.x_m, pose.y_m, ax, ay, bx, by)
        if distance < best_distance:
            best_index, best_t, best_distance = i, t, distance

    along_track_m = (
        sum(segment_lengths[:best_index]) + best_t * segment_lengths[best_index]
    )
    progress_fraction = (
        along_track_m / total_length if total_length > 0.0 else 0.0
    )
    half_width = float(corridor.half_width_m[best_index])

    return CorridorFix(
        segment_index=best_index,
        lateral_offset_m=float(best_distance),
        along_track_m=float(along_track_m),
        progress_fraction=float(min(1.0, max(0.0, progress_fraction))),
        half_width_at_pose_m=half_width,
        inside=bool(best_distance <= half_width),
    )


def trigger_state_from_pose(
    pose: PoseEstimate,
    corridor: Corridor,
    plan_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the telemetry mapping ``evaluate_triggers`` consumes.

    *plan_state* carries the keys this module cannot know (battery,
    temperatures, comms) and is merged underneath, so the pose-derived
    values win for the keys they own. Passing the fix's own numbers here
    is the whole point of Phase 7: ``corridor_violation`` and
    ``localization_uncertainty`` stop being hand-fed constants.
    """
    fix = project_onto_corridor(pose, corridor)
    state: dict[str, Any] = dict(plan_state or {})
    state.update(
        {
            "lateral_offset_m": fix.lateral_offset_m,
            "half_width_m": fix.half_width_at_pose_m,
            "localization_covariance_m": pose.covariance_m,
        }
    )
    return state


def evaluate_pose(
    pose: PoseEstimate,
    corridor: Corridor,
    plan_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The full pose -> deviation -> trigger evaluation, shell-agnostic.

    Both shells -- ``POST /api/pose`` and the ROS 2 pose monitor -- call
    this one function, so the trigger policy cannot drift between them.

    Slip is checked by comparing actual advance along the corridor
    (``along_track_m``, LunaPath's own measurement from the projected
    position) against the distance the estimator claims to have covered.
    On loose regolith the wheels turn further than the ground gained, so
    along-track falling well short of the claim is the slip signature.
    Absolute fixes carry no travelled distance to compare, so they are
    not slip-checked.

    ``recommended_action`` policy: a fired ``localization_uncertainty``
    outranks everything -- replanning from a pose wider than the corridor
    plans from a lie, so the honest move is to stop and take an absolute
    fix first. Otherwise any fired trigger recommends a replan.
    """
    from .replan_triggers import evaluate_triggers_detailed
    from .slip_model import check_slip_accumulation

    fix = project_onto_corridor(pose, corridor)
    trigger_state = trigger_state_from_pose(pose, corridor, plan_state)
    evaluation = evaluate_triggers_detailed(trigger_state)
    fired = list(evaluation["fired"])
    evaluated = list(evaluation["evaluated"])

    if not pose.is_absolute_fix and pose.distance_travelled_m > 0.0:
        slip = check_slip_accumulation(
            travelled_m=fix.along_track_m,
            commanded_m=pose.distance_travelled_m,
        )
        evaluated.append(slip.trigger_id)
        if slip.triggered:
            fired.append(slip)

    fired_ids = {t.trigger_id for t in fired}
    if "localization_uncertainty" in fired_ids:
        recommended_action = "stop_and_localize"
    elif fired_ids:
        recommended_action = "replan"
    else:
        recommended_action = "continue"

    return {
        "corridor_fix": fix,
        "fired": fired,
        "evaluated": evaluated,
        "skipped": evaluation["skipped"],
        "trigger_state": trigger_state,
        "recommended_action": recommended_action,
    }
