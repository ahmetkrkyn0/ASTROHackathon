# A validated obstacle observation, never a simulator mesh identity.
# `header.frame_id` names the world/map frame of `center`.
std_msgs/Header header
geometry_msgs/Point center
float32 radius_m
float32 confidence
builtin_interfaces/Time observed_at
string source                   # currently "lidar"
