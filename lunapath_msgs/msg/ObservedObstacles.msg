# Batch emitted by a LiDAR/perception component after its own validation.
# Consumers must still apply their own confidence/freshness policy.
std_msgs/Header header
ObservedObstacle[] obstacles
