"""Detour policy tests that run without ROS or a rover."""

from __future__ import annotations

from lunapath_ros.local_planning import LocalObstacle, MapPoint, plan_local_detour


CORRIDOR = (MapPoint(0.0, 0.0), MapPoint(10.0, 0.0))


def test_clear_corridor_follows_global_reference():
    result = plan_local_detour(MapPoint(1.0, 0.0), CORRIDOR, (3.0,), ())
    assert result.decision == "FOLLOW"


def test_confident_blocker_gets_a_bounded_detour_that_rejoins_the_corridor():
    result = plan_local_detour(
        MapPoint(1.0, 0.0), CORRIDOR, (3.0,),
        (LocalObstacle(MapPoint(5.0, 0.0), 0.5, 0.9),),
    )
    assert result.decision == "LOCAL_DETOUR"
    assert result.waypoints[-1] == CORRIDOR[-1]
    assert abs(result.waypoints[0].y_m) <= 3.0


def test_blocker_too_wide_for_corridor_stops_and_requests_replan():
    result = plan_local_detour(
        MapPoint(1.0, 0.0), CORRIDOR, (1.0,),
        (LocalObstacle(MapPoint(5.0, 0.0), 1.0, 0.9),),
    )
    assert result.decision == "STOP_AND_REPLAN"


def test_low_confidence_return_is_not_promoted_to_an_obstacle():
    result = plan_local_detour(
        MapPoint(1.0, 0.0), CORRIDOR, (3.0,),
        (LocalObstacle(MapPoint(5.0, 0.0), 1.0, 0.2),),
    )
    assert result.decision == "FOLLOW"
