cmake_minimum_required(VERSION 3.8)
project(lunapath_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)

# Task 3 buraya rosidl_generate_interfaces(...) ekleyecek.

ament_package()
