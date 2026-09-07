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

from .pose import SLIP_CHECKABLE_SOURCES, PoseEstimate
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


def project_onto_corridor(
    pose: PoseEstimate,
    corridor: Corridor,
    previous_segment_index: int | None = None,
    search_window_m: float = 250.0,
    previous_along_track_m: float | None = None,
) -> CorridorFix:
    """Locate *pose* against *corridor*.

    Picks the segment whose centreline the pose is closest to. Ties (a
    pose exactly equidistant from two segments, which happens at a corner)
    resolve to the earlier segment, so the answer is deterministic rather
    than dependent on floating-point noise.

    *previous_along_track_m* (preferred) or *previous_segment_index* says
    where the rover was at the last update. Given either, only positions
    within *search_window_m* along the route are considered, which stops
    a lookalike far segment (the outbound leg of a switchback) from
    capturing a pose that is still on its own leg. Omit both for a
    standalone fix with no history -- the search is then global and a
    switchback can mis-snap, which is what these parameters exist to
    prevent.

    The default window is generous: at LPR-1's 0.2 m/s top speed, 250 m
    is over 20 minutes of continuous driving, so it constrains only jumps
    no rover could have made between two pose updates.
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

    # Segment search window. Without a prior, the globally nearest segment
    # wins -- which on a switchback (the standard shape for climbing a
    # lunar slope) snaps a pose on the return leg onto the outbound leg
    # running a few tens of metres alongside, even while the pose is
    # comfortably INSIDE its own segment's corridor. along_track_m then
    # collapses by half the route and the slip check, which divides it by
    # the odometer's claim, fires on a rover that is not slipping.
    #
    # The window is measured in ALONG-TRACK METRES, not in segment count:
    # corridors carry one segment per pixel step, so a segment-count
    # window is a different physical distance on every grid resolution --
    # and on a short corridor it silently spans the whole route, leaving
    # the prior doing nothing. Metres bound what the rover could actually
    # have driven between two updates. (Round 2 review, M-4.)
    n_segments = len(waypoints) - 1
    segment_starts: list[float] = []
    running = 0.0
    for length in segment_lengths:
        segment_starts.append(running)
        running += length

    # The anchor is the previous along-track POSITION, not the previous
    # segment's start: a single segment can be longer than the window, so
    # anchoring at its start would exclude the rover's own current
    # location further along it.
    anchor_along: float | None = None
    if previous_along_track_m is not None:
        anchor_along = float(previous_along_track_m)
    elif previous_segment_index is not None:
        anchor = min(max(int(previous_segment_index), 0), n_segments - 1)
        # Midpoint: the best guess for "somewhere on that segment" when
        # only the index is known.
        anchor_along = segment_starts[anchor] + segment_lengths[anchor] / 2.0

    best_index = 0
    best_t = 0.0
    best_distance = float("inf")
    for i, ((ax, ay), (bx, by)) in enumerate(zip(waypoints[:-1], waypoints[1:])):
        t, distance = _project_point_on_segment(pose.x_m, pose.y_m, ax, ay, bx, by)
        if anchor_along is not None:
            along_here = segment_starts[i] + t * segment_lengths[i]
            if abs(along_here - anchor_along) > float(search_window_m):
                continue
        if distance < best_distance:
            best_index, best_t, best_distance = i, t, distance

    if best_distance == float("inf"):
        # Every segment fell outside the window -- the pose jumped further
        # along the route than the window allows (a genuine teleport, a
        # stale prior, or a corridor swapped underneath the caller).
        # Fall back to the global search rather than returning nothing:
        # a possibly-wrong fix that says where the rover is beats no fix.
        for i, ((ax, ay), (bx, by)) in enumerate(
            zip(waypoints[:-1], waypoints[1:])
        ):
            t, distance = _project_point_on_segment(
                pose.x_m, pose.y_m, ax, ay, bx, by
            )
            if distance < best_distance:
                best_index, best_t, best_distance = i, t, distance

    # segment_starts already holds the cumulative length at each segment, so
    # re-summing the prefix was O(n) work for a value sitting in a list.
    # (Round 3 review, L-18.)
    along_track_m = (
        segment_starts[best_index] + best_t * segment_lengths[best_index]
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
    fix: CorridorFix | None = None,
) -> dict[str, Any]:
    """Build the telemetry mapping ``evaluate_triggers`` consumes.

    *plan_state* carries the keys this module cannot know (battery,
    temperatures, comms) and is merged underneath, so the pose-derived
    values win for the keys they own. Passing the fix's own numbers here
    is the whole point of Phase 7: ``corridor_violation`` and
    ``localization_uncertainty`` stop being hand-fed constants.

    *fix* lets a caller that has already projected pass the result in,
    rather than paying for a second identical projection -- and, more
    importantly, guarantees the state describes the SAME fix the caller
    is reporting. (Round 2 review, L-7.)
    """
    if fix is None:
        fix = project_onto_corridor(pose, corridor)
    state: dict[str, Any] = dict(plan_state or {})
    state.update(
        {
            "lateral_offset_m": fix.lateral_offset_m,
            "half_width_m": fix.half_width_at_pose_m,
            "localization_covariance_m": pose.covariance_m,
        }
    )
    # Slip inputs travel in the SAME state mapping as every other trigger's,
    # so evaluate_triggers_detailed owns the whole enumeration and
    # POST /api/replan sees the trigger too. They are supplied only for a
    # source whose distance claim is a wheel measurement -- see
    # pose.SLIP_CHECKABLE_SOURCES. For any other source the keys are absent,
    # which the evaluator reports as skipped rather than silently clear.
    # (Round 3 review, M-4 and L-10.)
    if pose.source in SLIP_CHECKABLE_SOURCES and pose.distance_travelled_m > 0.0:
        state["map_progress_m"] = fix.along_track_m
        state["odometer_claim_m"] = pose.distance_travelled_m
        # The corridor's own length, so the slip check can tell an odometer
        # that was never reset from a rover that is genuinely slipping.
        # (Round 4 review, L-6.)
        state["corridor_length_m"] = corridor_length_m(corridor)
    return state


def corridor_length_m(corridor: Corridor) -> float:
    """Total polyline length of a corridor's centreline, in metres."""
    return float(
        sum(
            math.hypot(bx - ax, by - ay)
            for (ax, ay), (bx, by) in zip(
                corridor.waypoints[:-1], corridor.waypoints[1:]
            )
        )
    )


def evaluate_pose(
    pose: PoseEstimate,
    corridor: Corridor,
    plan_state: dict[str, Any] | None = None,
    previous_segment_index: int | None = None,
    previous_along_track_m: float | None = None,
    rover: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The full pose -> deviation -> trigger evaluation, shell-agnostic.

    Both shells -- ``POST /api/pose`` and the ROS 2 pose monitor -- call
    this one function, so the trigger policy cannot drift between them.

    Slip is checked by comparing actual advance along the corridor
    (``along_track_m``, LunaPath's own measurement from the projected
    position) against the distance the estimator claims to have covered.
    On loose regolith the wheels turn further than the ground gained, so
    along-track falling well short of the claim is the slip signature --
    but ONLY when the claim is a wheel measurement. Visual and LiDAR
    odometry estimate body motion from the world and have already
    corrected for slip, so for them the ratio measures path tortuosity
    instead; they are not slip-checked. Absolute fixes carry no travelled
    distance at all. Whenever the check does not run it is reported in
    ``skipped`` with the reason, not silently omitted from both lists.
    (Round 3 review, M-4.)

    *previous_along_track_m* / *previous_segment_index* are passed
    through to the projection as a progress prior; see
    :func:`project_onto_corridor`.

    ``recommended_action`` policy: a fired ``localization_uncertainty``
    outranks everything -- replanning from a pose wider than the corridor
    plans from a lie, so the honest move is to stop and take an absolute
    fix first. Otherwise any fired trigger recommends a replan.
    """
    from .replan_triggers import evaluate_triggers_detailed

    fix = project_onto_corridor(
        pose,
        corridor,
        previous_segment_index=previous_segment_index,
        previous_along_track_m=previous_along_track_m,
    )
    trigger_state = trigger_state_from_pose(pose, corridor, plan_state, fix=fix)
    evaluation = evaluate_triggers_detailed(trigger_state, rover)
    fired = list(evaluation["fired"])
    evaluated = list(evaluation["evaluated"])
    skipped = list(evaluation["skipped"])

    # The evaluator already reports slip_accumulation as skipped when its
    # keys are absent; replace that bare "missing key" entry with the reason
    # the keys are absent, which is what the caller actually needs to know.
    if "slip_accumulation" not in evaluated:
        if pose.is_absolute_fix:
            reason = f"{pose.source} is an absolute fix; no odometry claim"
        elif pose.source not in SLIP_CHECKABLE_SOURCES:
            reason = (
                f"{pose.source} estimates body motion directly, so its "
                "distance already excludes wheel slip; the ratio against "
                "corridor progress would measure path tortuosity instead"
            )
        elif pose.distance_travelled_m <= 0.0:
            reason = "no distance travelled to compare against"
        else:
            reason = "slip inputs unavailable"
        skipped = [
            entry for entry in skipped if entry.get("trigger_id") != "slip_accumulation"
        ]
        skipped.append(
            {
                "trigger_id": "slip_accumulation",
                "missing": ["distance_travelled_m"],
                "reason": reason,
            }
        )

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
        "skipped": skipped,
        "trigger_state": trigger_state,
        "recommended_action": recommended_action,
    }
