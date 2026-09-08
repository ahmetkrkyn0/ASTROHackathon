# A bounded, post-perception local navigation decision.
# Waypoints are expressed in header.frame_id and are only meaningful for a
# LOCAL_DETOUR decision. A motion controller must stop for every other value.
std_msgs/Header header
string decision                 # FOLLOW | LOCAL_DETOUR | STOP_AND_REPLAN | STOP_UNCERTAIN
geometry_msgs/Point[] waypoints
ObservedObstacle[] observed_obstacles
float32 nearest_obstacle_m
float32 corridor_deviation_m
string reason
