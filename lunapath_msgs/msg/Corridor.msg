# Contract handed to a local (LiDAR/stereo) planner.
# Mirrors backend/app/schemas.py::Corridor field for field.
# NOTE: the core field is thermal_budget_K_s (capital K); ROS IDL field names
# must be lower snake_case, so it is thermal_budget_k_s here. conversions.py
# owns that one-line mapping.
string crs
geometry_msgs/Point[] waypoints          # projected CRS metres; z unused
float32[] half_width_m                   # len(waypoints) - 1
float32[] max_slope_deg                  # len(waypoints) - 1
float32[] energy_budget_wh               # len(waypoints) - 1
float32[] thermal_budget_k_s             # len(waypoints) - 1
geometry_msgs/Point[] fallback_points    # len(waypoints)
