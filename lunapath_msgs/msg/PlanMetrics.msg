# Mirrors app.simulation.summarize_simulation() field for field, plus the
# two search metrics from app.pathfinder.astar(). Keeping the names identical
# means the node can copy values across without a translation table -- and a
# renamed key in the core shows up as a build/attribute error here rather
# than as a silently-zero field. (Faz 4 revision, R6.)
float32 total_distance_km
float32 total_elapsed_hours
float32 final_battery_pct
float32 min_battery_pct
float32 max_slope_deg
float32 total_energy_consumed_wh
float32 total_shadow_exposure
uint32  waypoint_count
uint32  total_recharges
uint32  critical_steps_count
uint32  high_or_above_steps_count
# from app.pathfinder.astar()["metrics"]
uint32  nodes_expanded
float32 computation_time_ms
