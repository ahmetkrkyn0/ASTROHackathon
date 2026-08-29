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

from app.constants import UnknownRoverError, get_rover
from app.corridor import build_corridor
from app.cost_engine import resolve_weights
from app.data_loader import load_preprocessed_grids
from app.pathfinder import astar
from app.simulation import simulate_path, summarize_simulation
from lunapath_msgs.action import PlanTraverse
from lunapath_ros.conversions import (
    corridor_to_msg,
    pixels_to_path,
    pose_to_pixel,
    weights_msg_to_dict,
)

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
        metadata = self._grids["metadata"]
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
            weights = resolve_weights(raw_weights, rover)
        else:
            # An all-zero MissionWeights is the default-constructed message,
            # not a deliberate "everything costs nothing" request.
            weights = resolve_weights(None, rover)

        # -- start / goal ---------------------------------------------------
        try:
            start = pose_to_pixel(request.start, metadata)
        except ValueError as exc:
            return self._fail(goal_handle, result, result.START_OUTSIDE_MAP, str(exc))
        try:
            goal = pose_to_pixel(request.goal, metadata)
        except ValueError as exc:
            return self._fail(goal_handle, result, result.GOAL_OUTSIDE_MAP, str(exc))

        traversable = self._grids["traversable"]
        if not bool(traversable[start]):
            return self._fail(
                goal_handle, result, result.START_OCCUPIED, f"start {start} is not traversable"
            )
        if not bool(traversable[goal]):
            return self._fail(
                goal_handle, result, result.GOAL_OCCUPIED, f"goal {goal} is not traversable"
            )

        feedback = PlanTraverse.Feedback()
        feedback.progress = 0.0
        goal_handle.publish_feedback(feedback)

        # -- plan -----------------------------------------------------------
        plan = astar(self._grids, start, goal, weights=weights, rover=rover)
        if plan.get("error"):
            return self._fail(goal_handle, result, result.NO_VALID_PATH, plan["error"])

        stamp = self.get_clock().now().to_msg()
        result.path = pixels_to_path(
            plan["path_pixels"], metadata, self._frame_id, stamp
        )

        # -- corridor -------------------------------------------------------
        try:
            result.corridor = corridor_to_msg(
                build_corridor(plan["path_pixels"], self._grids, rover).model_dump()
            )
        except (ValueError, KeyError) as exc:
            self.get_logger().warning(f"corridor skipped: {exc}")

        # -- metrics --------------------------------------------------------
        # The physics summary is what PlanMetrics is shaped after; astar's own
        # metrics only carry the two search counters. Reading the summary keys
        # off astar's dict returned zeros for every battery/energy/time field.
        # (Faz 4 revision, R6.)
        search = plan.get("metrics", {})
        try:
            states = simulate_path(
                plan,
                self._grids["cost"],
                self._grids["slope"],
                self._grids["thermal"],
                self._grids["shadow_ratio"],
                rover=rover,
                pixel_size_m=float(metadata["resolution_m"]),
            )
            summary = summarize_simulation(states)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warning(f"simulation skipped: {exc!r}")
            summary = {}

        metrics = result.metrics
        metrics.total_distance_km = float(summary.get("total_distance_km", 0.0))
        metrics.total_elapsed_hours = float(summary.get("total_elapsed_hours", 0.0))
        metrics.final_battery_pct = float(summary.get("final_battery_pct", 0.0))
        metrics.min_battery_pct = float(summary.get("min_battery_pct", 0.0))
        metrics.max_slope_deg = float(
            summary.get("max_slope_deg", search.get("max_slope_deg", 0.0))
        )
        metrics.total_energy_consumed_wh = float(
            summary.get("total_energy_consumed_wh", 0.0)
        )
        metrics.total_shadow_exposure = float(summary.get("total_shadow_exposure", 0.0))
        metrics.waypoint_count = int(
            summary.get("waypoint_count", len(plan["path_pixels"]))
        )
        metrics.total_recharges = int(summary.get("total_recharges", 0))
        metrics.critical_steps_count = int(summary.get("critical_steps_count", 0))
        metrics.high_or_above_steps_count = int(
            summary.get("high_or_above_steps_count", 0)
        )
        metrics.nodes_expanded = int(search.get("nodes_expanded", 0))
        metrics.computation_time_ms = float(search.get("computation_time_ms", 0.0))

        elapsed = time.perf_counter() - started
        result.planning_time.sec = int(elapsed)
        result.planning_time.nanosec = int((elapsed % 1.0) * 1e9)
        result.error_code = result.NONE
        result.error_msg = ""

        feedback.progress = 1.0
        feedback.nodes_expanded = metrics.nodes_expanded
        goal_handle.publish_feedback(feedback)
        goal_handle.succeed()
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
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
