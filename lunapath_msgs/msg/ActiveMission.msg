# Goal retained by the planner so a coordinator can replan from live odometry.
std_msgs/Header header
geometry_msgs/PoseStamped goal
string rover_id
MissionWeights weights
PlanMetrics metrics
