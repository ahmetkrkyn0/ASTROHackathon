# ===== LPR-1 ROVER CONSTANTS (v3.2 Final — Frozen) =====

# Mechanical
ROVER_MASS_KG = 450
GRAVITY_MOON = 1.62              # m/s²
V_MAX_MS = 0.2                   # m/s

# Energy
P_BASE_W = 200                   # W (flat terrain driving power)
P_PEAK_W = 450                   # W (peak power)
E_CAP_WH = 5420                  # Wh (battery capacity @ 0°C start of life)
P_IDLE_W = 40                    # W (shadow idle: electronics + comms)
P_HEATER_W = 25                  # W (Kapton heaters)
P_SHADOW_W = 65                  # W (idle + heater, active shadow driving)
P_HIBERNATE_W = 108              # W (hibernate mode)
P_SOLAR_W = 410                  # W (solar panel, NASA PIP TBR conservative)
REGEN_EFFICIENCY = 0.10          # 10%

# Slope Limits
SLOPE_COMFORTABLE_DEG = 15
SLOPE_MAX_DEG = 25               # Absolute limit (>25° = INF cost)
SLOPE_LATERAL_MAX_DEG = 18       # Rollover limit

# Shadow / Battery
H_MAX_SHADOW_H = 50              # hours (NASA operational limit)
H_DESIGN_SHADOW_H = 70           # hours (safe haven design criterion)
SOC_MIN_PCT = 0.20               # Minimum battery threshold (20%)

# Thermal
THERMAL_TAU_S = 7200             # seconds (thermal time constant)
THERMAL_OFFSET_COLD = 60         # °C (T_surface < 0°C → T_eq = T_surface + 60)
THERMAL_OFFSET_HOT = -40         # °C (T_surface >= 0°C → T_eq = T_surface - 40)
BAT_OP_MIN_C = 0
BAT_OP_MAX_C = 35
ELEC_OP_MIN_C = -10
ELEC_OP_MAX_C = 40

# Energy Model
F_NET_N = 210                    # N (net traction force)
MU_COEFF = 3.471                 # = m * g_M / F_net

# AHP Default Weights (v3.2 gradient-based)
W_SLOPE = 0.409
W_ENERGY = 0.259
W_SHADOW = 0.142
W_THERMAL = 0.190

# Log-Barrier
LOG_BARRIER_MU = 0.1

# Grid
DEFAULT_TARGET_RESOLUTION_M = 80
