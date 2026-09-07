# AHP cost weights. Server-side validation matches PlanWeights in main.py:
# each value must be within [0.0, 2.0]; out-of-range requests are rejected
# with INVALID_PLANNER rather than silently clamped.
float32 w_slope
float32 w_energy
float32 w_shadow
float32 w_thermal
