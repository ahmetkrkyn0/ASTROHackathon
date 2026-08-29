#!/usr/bin/env bash
# Record one planning run as a rosbag2 for reproducibility.
#
# Every plan is an artefact: the input layers, the request and the resulting
# route are stored with timestamps and can be replayed exactly. (Spec §4.7)
set -euo pipefail

OUT="${1:-bags/plan_$(date -u +%Y%m%dT%H%M%SZ)}"
mkdir -p "$(dirname "$OUT")"

# Verified against a real ROS 2 Jazzy install (Task 7 Step 5): a
# PlanTraverse goal/result exchange is served over two SERVICES --
# /plan_traverse/_action/send_goal and /plan_traverse/_action/get_result
# -- not topics named ".../goal"/".../result"; those exact names don't
# exist anywhere on the graph. Recording service *traffic* additionally
# needs ROS 2 "service introspection" turned on in server or client code
# (rclpy's ActionServer doesn't enable it), so send_goal/get_result stay
# unobservable to rosbag2 without a code change outside this script's
# scope -- not attempted here. /plan_traverse/_action/status already
# carries the full goal lifecycle (ACCEPTED/EXECUTING/SUCCEEDED, with
# goal IDs and timestamps) as the closest available record of each goal.
#
# /plan_traverse/_action/feedback and .../status ARE topics, but ROS 2
# hides any entity with a leading-underscore name segment (here
# "_action") from ros2 bag record's default discovery, so
# --include-hidden-topics is required -- without it these are silently
# never subscribed, with no error, and the bag ends up with 0 messages on
# them forever.
#
# /lunapath/grid_map is published TRANSIENT_LOCAL (latched); verified
# this recorder still receives it correctly (both the retained latched
# sample and every periodic republish) with no extra flags -- this
# ros2/rosbag2 version negotiates a matching durability automatically
# per discovered publisher, so the VOLATILE-default trap some older
# rosbag2 docs warn about did not reproduce here.
ros2 bag record -o "$OUT" \
  --include-hidden-topics \
  --topics /lunapath/grid_map /plan_traverse/_action/feedback /plan_traverse/_action/status /tf_static
