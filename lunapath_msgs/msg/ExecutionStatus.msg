# Measured execution compared with the currently active plan. Unknown numeric
# quantities use NaN; consumers must inspect the corresponding has_* flag.
std_msgs/Header header
float32 planned_distance_km
float32 planned_energy_wh
float32 planned_elapsed_hours
float32 travelled_distance_m
float32 actual_soc_pct
float32 actual_energy_consumed_wh
bool has_battery_measurement
string status
