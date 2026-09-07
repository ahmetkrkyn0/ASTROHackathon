cmake_minimum_required(VERSION 3.8)
project(lunapath_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MissionWeights.msg"
  "msg/PlanMetrics.msg"
  "msg/Corridor.msg"
  "msg/ReplanTrigger.msg"
  "action/PlanTraverse.action"
  DEPENDENCIES builtin_interfaces geometry_msgs nav_msgs
)

ament_package()
