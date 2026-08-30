"""Corridor projection tests.

The segment-boundary tests matter most: an unclamped projection is
discontinuous at corners, which would make lateral_offset_m jump as the
rover drives past a waypoint and fire corridor_violation on geometry
alone.
"""

from __future__ import annotations

import pytest

from app.localization import project_onto_corridor, trigger_state_from_pose
from app.pose import PoseEstimate
from app.replan_triggers import evaluate_triggers
from app.schemas import Corridor


def _corridor(waypoints=None, half_widths=None) -> Corridor:
    waypoints = waypoints or [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0)]
    n_segments = len(waypoints) - 1
    half_widths = half_widths or [20.0] * n_segments
    return Corridor(
        waypoints=waypoints,
        half_width_m=half_widths,
        max_slope_deg=[5.0] * n_segments,
        energy_budget_wh=[50.0] * n_segments,
        thermal_budget_K_s=[1000.0] * n_segments,
        fallback_points=[(0.0, 0.0)] * len(waypoints),
        crs="test",
    )


def _pose(x, y, **overrides) -> PoseEstimate:
    base = {
        "x_m": x,
        "y_m": y,
        "heading_deg": 90.0,
        "covariance_m": 2.0,
        "heading_covariance_deg": 1.0,
        "timestamp_utc": "2026-08-30T12:00:00Z",
        "source": "visual_odometry",
        "distance_travelled_m": 50.0,
    }
    base.update(overrides)
    return PoseEstimate(**base)


def test_a_pose_on_the_centreline_has_zero_lateral_offset():
    fix = project_onto_corridor(_pose(50.0, 0.0), _corridor())
    assert fix.lateral_offset_m == pytest.approx(0.0)
    assert fix.inside


def test_lateral_offset_is_the_perpendicular_distance():
    fix = project_onto_corridor(_pose(50.0, 7.0), _corridor())
    assert fix.lateral_offset_m == pytest.approx(7.0)


def test_a_pose_beyond_the_half_width_is_outside():
    fix = project_onto_corridor(_pose(50.0, 25.0), _corridor())
    assert fix.lateral_offset_m == pytest.approx(25.0)
    assert not fix.inside


def test_a_pose_exactly_on_the_half_width_counts_as_inside():
    """The trigger fires on strictly greater-than, so the boundary must
    agree with it or the two disagree by one epsilon at the edge."""
    fix = project_onto_corridor(_pose(50.0, 20.0), _corridor())
    assert fix.inside


def test_the_correct_segment_is_selected():
    fix = project_onto_corridor(_pose(150.0, 3.0), _corridor())
    assert fix.segment_index == 1


def test_along_track_distance_is_measured_along_the_route():
    fix = project_onto_corridor(_pose(150.0, 0.0), _corridor())
    assert fix.along_track_m == pytest.approx(150.0)


def test_progress_fraction_runs_from_zero_to_one():
    corridor = _corridor()
    assert project_onto_corridor(_pose(0.0, 0.0), corridor).progress_fraction == (
        pytest.approx(0.0)
    )
    assert project_onto_corridor(_pose(200.0, 0.0), corridor).progress_fraction == (
        pytest.approx(1.0)
    )
    assert project_onto_corridor(_pose(100.0, 0.0), corridor).progress_fraction == (
        pytest.approx(0.5)
    )


def test_the_half_width_of_the_matched_segment_is_reported():
    corridor = _corridor(half_widths=[30.0, 5.0])
    assert project_onto_corridor(
        _pose(50.0, 0.0), corridor
    ).half_width_at_pose_m == pytest.approx(30.0)
    assert project_onto_corridor(
        _pose(150.0, 0.0), corridor
    ).half_width_at_pose_m == pytest.approx(5.0)


def test_projection_does_not_jump_across_a_segment_boundary():
    """A pose walked through a right-angle corner must not see its offset
    jump. Unclamped projection is discontinuous here and would fire
    corridor_violation on geometry alone."""
    corridor = _corridor(waypoints=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)])
    offsets = [
        project_onto_corridor(_pose(x, 0.0), corridor).lateral_offset_m
        for x in (98.0, 99.0, 100.0, 101.0, 102.0)
    ]
    # Past the corner the pose is genuinely off the route, so the offset
    # grows -- but smoothly, by about a metre per metre, with no jump.
    for previous, current in zip(offsets[:-1], offsets[1:]):
        assert abs(current - previous) <= 1.5


def test_a_pose_before_the_start_projects_onto_the_first_waypoint():
    fix = project_onto_corridor(_pose(-30.0, 0.0), _corridor())
    assert fix.segment_index == 0
    assert fix.along_track_m == pytest.approx(0.0)
    assert fix.lateral_offset_m == pytest.approx(30.0)


def test_a_pose_past_the_end_projects_onto_the_last_waypoint():
    fix = project_onto_corridor(_pose(260.0, 0.0), _corridor())
    assert fix.along_track_m == pytest.approx(200.0)
    assert fix.lateral_offset_m == pytest.approx(60.0)


def test_a_corridor_with_one_waypoint_is_rejected():
    with pytest.raises(ValueError):
        project_onto_corridor(
            _pose(0.0, 0.0),
            Corridor(
                waypoints=[(0.0, 0.0)],
                half_width_m=[],
                max_slope_deg=[],
                energy_budget_wh=[],
                thermal_budget_K_s=[],
                fallback_points=[(0.0, 0.0)],
                crs="test",
            ),
        )


def test_a_corridor_with_mismatched_half_widths_is_rejected():
    """Silently indexing a short half_width list would raise IndexError
    deep in the projection, or worse, read a neighbouring segment's width."""
    corridor = _corridor()
    corridor.half_width_m = [20.0]  # 3 waypoints need 2 half-widths
    with pytest.raises(ValueError):
        project_onto_corridor(_pose(50.0, 0.0), corridor)


def test_a_repeated_waypoint_does_not_divide_by_zero():
    corridor = _corridor(waypoints=[(0.0, 0.0), (0.0, 0.0), (100.0, 0.0)])
    fix = project_onto_corridor(_pose(50.0, 5.0), corridor)
    assert fix.lateral_offset_m == pytest.approx(5.0)


# --- the point of the whole task: real triggers, real inputs ---------------


def test_trigger_state_supplies_the_keys_the_triggers_need():
    state = trigger_state_from_pose(_pose(50.0, 3.0), _corridor())
    for key in ("lateral_offset_m", "half_width_m", "localization_covariance_m"):
        assert key in state


def test_a_pose_leaving_the_corridor_fires_corridor_violation():
    state = trigger_state_from_pose(_pose(50.0, 25.0), _corridor())
    fired = {t.trigger_id for t in evaluate_triggers(state)}
    assert "corridor_violation" in fired


def test_a_pose_inside_the_corridor_does_not_fire_corridor_violation():
    state = trigger_state_from_pose(_pose(50.0, 2.0), _corridor())
    fired = {t.trigger_id for t in evaluate_triggers(state)}
    assert "corridor_violation" not in fired


def test_uncertainty_wider_than_the_corridor_fires_localization_uncertainty():
    state = trigger_state_from_pose(_pose(50.0, 0.0, covariance_m=25.0), _corridor())
    fired = {t.trigger_id for t in evaluate_triggers(state)}
    assert "localization_uncertainty" in fired


def test_plan_state_keys_are_preserved_and_pose_keys_win():
    state = trigger_state_from_pose(
        _pose(50.0, 3.0),
        _corridor(),
        plan_state={"actual_soc": 0.4, "planned_soc": 0.8, "lateral_offset_m": 999.0},
    )
    assert state["actual_soc"] == 0.4
    assert state["lateral_offset_m"] == pytest.approx(3.0)
