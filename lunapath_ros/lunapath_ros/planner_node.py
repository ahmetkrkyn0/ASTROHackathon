"""PlanTraverse action server.

Deliberately thin: every computation lives in backend/app. If you find
yourself writing planning logic in this file, it belongs in the core.
"""

from __future__ import annotations

import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from nav_msgs.msg import Path

from app.constants import UnknownRoverError, get_rover
from app.corridor import build_corridor
from app.cost_engine import resolve_weights
from app.data_loader import load_preprocessed_grids
from app.pathfinder import astar
from app.rover_grids import grids_for_rover
from app.simulation import simulate_path, summarize_simulation
from lunapath_msgs.action import PlanTraverse
from lunapath_msgs.msg import ActiveMission, Corridor as CorridorMsg
from lunapath_ros.conversions import (
    corridor_to_msg,
    pixels_to_path,
    pose_to_pixel,
    weights_msg_to_dict,
)
from lunapath_ros.observed_obstacle_grid import with_observed_obstacles

WEIGHT_MIN, WEIGHT_MAX = 0.0, 2.0


class LunaPathPlanner(Node):
    def __init__(self) -> None:
        super().__init__("lunapath_planner")
        self.declare_parameter("frame_id", "moon_map")
        self.declare_parameter("processed_dir", "")

        processed_dir = self.get_parameter("processed_dir").value or None
        self._grids = load_preprocessed_grids(processed_dir=processed_dir)
        self._frame_id = self.get_parameter("frame_id").value

        # A plan is a synchronous, seconds-long numpy call. On the default
        # single-threaded executor it blocks everything -- feedback cannot be
        # delivered and a cancel request is never serviced. A reentrant group
        # on a MultiThreadedExecutor keeps the node responsive.
        # (Faz 4 revision, R8.)
        self._server = ActionServer(
            self,
            PlanTraverse,
            "plan_traverse",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=ReentrantCallbackGroup(),
        )
        # Latched so the pose monitor receives the active corridor even if
        # it starts after the plan was made (see pose_monitor.LATCHED_QOS,
        # the subscribing side of the same profile).
        from lunapath_ros.pose_monitor import LATCHED_QOS

        self._corridor_pub = self.create_publisher(
            CorridorMsg, "corridor", LATCHED_QOS
        )
        self._path_pub = self.create_publisher(
            Path, "global_path", LATCHED_QOS
        )
        self._active_mission_pub = self.create_publisher(
            ActiveMission, "active_mission", LATCHED_QOS
        )
        self.get_logger().info("PlanTraverse action server ready on /plan_traverse")

    # ── Goal admission ──────────────────────────────────────────────────

    def goal_callback(self, goal_request) -> GoalResponse:
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle) -> CancelResponse:
        # astar() is a single uninterruptible call, so a cancel can only be
        # honoured before it starts. Accepting is still correct: the client
        # gets a definite answer instead of a timeout.
        return CancelResponse.ACCEPT

    # ── Execution ───────────────────────────────────────────────────────

    def execute_callback(self, goal_handle):
        result = PlanTraverse.Result()
        try:
            return self._plan(goal_handle, result)
        except Exception as exc:  # noqa: BLE001 - the boundary of the shell
            # Nothing may escape an action callback: an uncaught exception
            # leaves the client hanging with no result at all. Nav2 reserves
            # UNKNOWN=200 for exactly this. (Faz 4 revision, R7.)
            self.get_logger().error(f"PlanTraverse crashed: {exc!r}")
            return self._fail(goal_handle, result, result.UNKNOWN, repr(exc))

    def _plan(self, goal_handle, result):
        request = goal_handle.request
        started = time.perf_counter()

        # -- contract fields this phase does not implement (Task 3 note) ----
        if not request.use_start:
            return self._fail(
                goal_handle,
                result,
                result.TF_ERROR,
                "use_start=false needs a robot pose from TF; this node has no "
                "TF source. Send use_start=true with an explicit start pose.",
            )
        if request.epoch.sec or request.epoch.nanosec:
            return self._fail(
                goal_handle,
                result,
                result.INVALID_PLANNER,
                "epoch is reserved for the 4-D planner and is not served by "
                "this action; send epoch=0 for the 2-D plan.",
            )

        # -- rover and weights ---------------------------------------------
        try:
            rover = get_rover(request.rover_id or None)
        except UnknownRoverError as exc:
            return self._fail(goal_handle, result, result.INVALID_PLANNER, str(exc))

        raw_weights = weights_msg_to_dict(request.weights)
        if any(v for v in raw_weights.values()):
            out_of_range = {
                k: v
                for k, v in raw_weights.items()
                if not (WEIGHT_MIN <= v <= WEIGHT_MAX)
            }
            if out_of_range:
                return self._fail(
                    goal_handle,
                    result,
                    result.INVALID_PLANNER,
                    f"weights outside [{WEIGHT_MIN}, {WEIGHT_MAX}]: {out_of_range}",
                )
            weights_input = raw_weights
        else:
            # An all-zero MissionWeights is the default-constructed message,
            # not a deliberate "everything costs nothing" request.
            weights_input = None
        weights = resolve_weights(weights_input, rover)

        # -- rover-adapted grids ---------------------------------------------
        # self._grids is only the base grids loaded once at startup, baked in
        # under the default rover. Different rovers have different
        # slope_max_deg (e.g. nasa_viper/cnsa_yutu_2 are 20 deg, lpr_1 is
        # 25 deg), so a cell that is traversable for the default rover may
        # not be for this request's rover -- grids_for_rover recomputes the
        # traversable mask and cost grid for this rover/weights combination
        # the same way the FastAPI shell's /api/plan does. Everything below
        # this point plans against `grids`, not `self._grids`. (Faz 4
        # final-review finding H1.)
        grids = grids_for_rover(self._grids, request.rover_id or None, weights_input)
        metadata = grids["metadata"]

        # -- start / goal ---------------------------------------------------
        try:
            start = pose_to_pixel(request.start, metadata)
        except ValueError as exc:
            return self._fail(goal_handle, result, result.START_OUTSIDE_MAP, str(exc))
        try:
            goal = pose_to_pixel(request.goal, metadata)
        except ValueError as exc:
            return self._fail(goal_handle, result, result.GOAL_OUTSIDE_MAP, str(exc))

        traversable = grids["traversable"]
        if not bool(traversable[start]):
            return self._fail(
                goal_handle, result, result.START_OCCUPIED, f"start {start} is not traversable"
            )
        if not bool(traversable[goal]):
            return self._fail(
                goal_handle, result, result.GOAL_OCCUPIED, f"goal {goal} is not traversable"
            )

        # The initial action has no observations. A replan coordinator may
        # supply only LiDAR-originated, confidence-qualified obstacle records;
        # this is deliberately after the base start validation so an observed
        # rock under the stationary rover cannot invalidate its own start.
        grids, accepted_observations = with_observed_obstacles(
            grids, request.observed_obstacles, start
        )

        feedback = PlanTraverse.Feedback()
        feedback.progress = 0.0
        goal_handle.publish_feedback(feedback)

        # -- plan -----------------------------------------------------------
        plan = astar(grids, start, goal, weights=weights, rover=rover)
        if plan.get("error"):
            return self._fail(goal_handle, result, result.NO_VALID_PATH, plan["error"])

        stamp = self.get_clock().now().to_msg()
        result.path = pixels_to_path(
            plan["path_pixels"], metadata, self._frame_id, stamp
        )
        self._path_pub.publish(result.path)

        # -- corridor -------------------------------------------------------
        # error_code stays NONE on a corridor failure (the path itself is
        # still valid) but the client needs an in-band signal instead of only
        # a server-side log line it can never see, else "start == goal" (a
        # realistic ValueError from build_corridor) produces a "successful"
        # plan with a silently empty corridor. (Faz 4 review follow-up.)
        corridor_err = None
        try:
            result.corridor = corridor_to_msg(
                build_corridor(plan["path_pixels"], grids, rover).model_dump()
            )
            # Also published latched: the action result reaches only the
            # requesting client, but the pose monitor (Faz 7) needs the
            # active corridor too, whenever it happens to start.
            self._corridor_pub.publish(result.corridor)
        except (ValueError, KeyError) as exc:
            corridor_err = f"corridor skipped: {exc}"
            self.get_logger().warning(corridor_err)

        # -- metrics --------------------------------------------------------
        # The physics summary is what PlanMetrics is shaped after; astar's own
        # metrics only carry the two search counters. Reading the summary keys
        # off astar's dict returned zeros for every battery/energy/time field.
        # (Faz 4 revision, R6.)
        search = plan.get("metrics", {})
        metrics = result.metrics
        sim_err = None
        try:
            states = simulate_path(
                plan,
                grids["cost"],
                grids["slope"],
                grids["thermal"],
                grids["shadow_ratio"],
                rover=rover,
                pixel_size_m=float(metadata["resolution_m"]),
            )
            # The rover is passed so the shadow-exposure and peak-power
            # checks are measured against ITS limits, not the default
            # rover's. (Round 3 review, M-8.)
            summary = summarize_simulation(states, rover)
            # Direct indexing (not .get(key, 0.0)) so a genuinely renamed or
            # missing key in the core surfaces here as a KeyError -- caught
            # below and reported via error_msg -- rather than as a silently
            # zero field. This is PlanMetrics.msg's own stated contract: "a
            # renamed key in the core shows up as a build/attribute error
            # here rather than as a silently-zero field." (Faz 4 review
            # follow-up to R6.)
            metrics.total_distance_km = float(summary["total_distance_km"])
            metrics.total_elapsed_hours = float(summary["total_elapsed_hours"])
            metrics.final_battery_pct = float(summary["final_battery_pct"])
            metrics.min_battery_pct = float(summary["min_battery_pct"])
            metrics.max_slope_deg = float(summary["max_slope_deg"])
            metrics.total_energy_consumed_wh = float(
                summary["total_energy_consumed_wh"]
            )
            metrics.total_shadow_exposure = float(summary["total_shadow_exposure"])
            metrics.waypoint_count = int(summary["waypoint_count"])
            metrics.total_recharges = int(summary["total_recharges"])
            metrics.critical_steps_count = int(summary["critical_steps_count"])
            metrics.high_or_above_steps_count = int(
                summary["high_or_above_steps_count"]
            )
        except Exception as exc:  # noqa: BLE001
            # error_code stays NONE: a simulation failure shouldn't
            # necessarily invalidate an otherwise-valid path. But leaving
            # every summary-derived field at its zero-initialized default
            # while reporting success is exactly the "plan looks successful,
            # metrics are silently all-zero" failure mode R6 exists to
            # prevent -- so say so in error_msg instead of only logging it
            # server-side. (Faz 4 review follow-up to R6.)
            sim_err = f"simulation skipped: {exc!r}"
            self.get_logger().warning(sim_err)
            metrics.max_slope_deg = float(search.get("max_slope_deg", 0.0))
            metrics.waypoint_count = len(plan["path_pixels"])

        metrics.nodes_expanded = int(search.get("nodes_expanded", 0))
        metrics.computation_time_ms = float(search.get("computation_time_ms", 0.0))

        elapsed = time.perf_counter() - started
        result.planning_time.sec = int(elapsed)
        result.planning_time.nanosec = int((elapsed % 1.0) * 1e9)
        result.error_code = result.NONE
        messages = [m for m in (corridor_err, sim_err) if m]
        if accepted_observations:
            messages.append(f"replan used {accepted_observations} confirmed LiDAR obstacle(s)")
        result.error_msg = "; ".join(messages)

        feedback.progress = 1.0
        feedback.nodes_expanded = metrics.nodes_expanded
        goal_handle.publish_feedback(feedback)
        goal_handle.succeed()
        active = ActiveMission()
        active.header.frame_id = self._frame_id
        active.header.stamp = stamp
        active.goal = request.goal
        active.rover_id = request.rover_id
        active.weights = request.weights
        active.metrics = result.metrics
        self._active_mission_pub.publish(active)
        return result

    def _fail(self, goal_handle, result, code: int, message: str):
        self.get_logger().warning(f"PlanTraverse failed ({code}): {message}")
        result.error_code = code
        result.error_msg = message
        goal_handle.abort()
        return result


def main() -> None:
    rclpy.init()
    node = LunaPathPlanner()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            executor.shutdown()
            node.destroy_node()
        except KeyboardInterrupt:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
