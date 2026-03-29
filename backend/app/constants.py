# ===== LUNAR ROVER REGISTRY (v4.0 - Multi-Rover Config) =====

# Global environment constants (shared across all rovers)
GRAVITY_MOON = 1.62              # m/s²
LOG_BARRIER_MU = 0.1
DEFAULT_TARGET_RESOLUTION_M = 80

# --- ROVER CATALOGUE ---
ROVERS: dict[str, dict] = {
    "lpr_1": {
        "name": "LPR-1 (Varsayilan)",
        "mass_kg": 450, "v_max_ms": 0.2,
        "p_base_w": 200, "p_peak_w": 450, "e_cap_wh": 5420, "p_idle_w": 40,
        "p_heater_w": 25, "p_shadow_w": 65, "p_hibernate_w": 108, "p_solar_w": 410, "regen_efficiency": 0.10,
        "slope_comfortable_deg": 15, "slope_max_deg": 25, "slope_lateral_max_deg": 18,
        "h_max_shadow_h": 50, "h_design_shadow_h": 70, "soc_min_pct": 0.20,
        "thermal_tau_s": 7200, "thermal_offset_cold": 60, "thermal_offset_hot": -40,
        "bat_op_min_c": 0, "bat_op_max_c": 35, "elec_op_min_c": -10, "elec_op_max_c": 40,
        "f_net_n": 210, "mu_coeff": 3.471,
        "w_slope": 0.409, "w_energy": 0.259, "w_shadow": 0.142, "w_thermal": 0.190,
    },
    "luvmi_m": {
        "name": "LUVMI-M",
        "mass_kg": 40, "v_max_ms": 0.05,
        "p_base_w": 80, "p_peak_w": 250, "e_cap_wh": 1400, "p_idle_w": 30,
        "p_heater_w": 20, "p_shadow_w": 50, "p_hibernate_w": None, "p_solar_w": 140, "regen_efficiency": 0.0,
        "slope_comfortable_deg": 15, "slope_max_deg": 25, "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 4, "h_design_shadow_h": 6, "soc_min_pct": 0.20,
        "thermal_tau_s": None, "thermal_offset_cold": None, "thermal_offset_hot": None,
        "bat_op_min_c": -100, "bat_op_max_c": 0, "elec_op_min_c": None, "elec_op_max_c": None,
        "f_net_n": 50, "mu_coeff": 1.296,
        "w_slope": 0.40, "w_energy": 0.30, "w_shadow": 0.30, "w_thermal": 0.0,
    },
    "nasa_viper": {
        "name": "NASA VIPER",
        "mass_kg": 450, "v_max_ms": 0.06,
        "p_base_w": 250, "p_peak_w": 500, "e_cap_wh": 4000, "p_idle_w": 80,
        "p_heater_w": 50, "p_shadow_w": 130, "p_hibernate_w": 100, "p_solar_w": 450, "regen_efficiency": 0.10,
        "slope_comfortable_deg": 15, "slope_max_deg": 20, "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 96, "h_design_shadow_h": 120, "soc_min_pct": 0.20,
        "thermal_tau_s": 8000, "thermal_offset_cold": 60, "thermal_offset_hot": -40,
        "bat_op_min_c": 0, "bat_op_max_c": 35, "elec_op_min_c": -20, "elec_op_max_c": 50,
        "f_net_n": 200, "mu_coeff": 3.645,
        "w_slope": 0.35, "w_energy": 0.25, "w_shadow": 0.20, "w_thermal": 0.20,
    },
    "cnsa_yutu_2": {
        "name": "CNSA Yutu-2",
        "mass_kg": 140, "v_max_ms": 0.05,
        "p_base_w": 100, "p_peak_w": 200, "e_cap_wh": 1500, "p_idle_w": 40,
        "p_heater_w": 20, "p_shadow_w": 60, "p_hibernate_w": 5, "p_solar_w": 300, "regen_efficiency": 0.0,
        "slope_comfortable_deg": 10, "slope_max_deg": 20, "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 2, "h_design_shadow_h": 3, "soc_min_pct": 0.30,
        "thermal_tau_s": 5000, "thermal_offset_cold": 70, "thermal_offset_hot": -30,
        "bat_op_min_c": -10, "bat_op_max_c": 30, "elec_op_min_c": -40, "elec_op_max_c": 55,
        "f_net_n": 80, "mu_coeff": 2.835,
        "w_slope": 0.50, "w_energy": 0.30, "w_shadow": 0.20, "w_thermal": 0.0,
    },
}

DEFAULT_ROVER_ID = "lpr_1"

# Required fields — ValueError if None
_REQUIRED_FIELDS = ("mass_kg", "p_base_w", "e_cap_wh", "v_max_ms", "f_net_n", "mu_coeff")


def get_rover(rover_id: str | None = None) -> dict:
    """Return a rover config dict by ID. Defaults to DEFAULT_ROVER_ID.

    Raises KeyError if rover_id is not in ROVERS.
    Raises ValueError if any required kinematic/energy field is None.
    """
    rid = rover_id or DEFAULT_ROVER_ID
    if rid not in ROVERS:
        raise KeyError(f"Unknown rover_id: {rid!r}. Available: {list(ROVERS.keys())}")
    cfg = ROVERS[rid]
    for field in _REQUIRED_FIELDS:
        if cfg.get(field) is None:
            raise ValueError(
                f"Rover {rid!r} has required field {field!r} = None. "
                "Cannot proceed without kinematic/energy parameters."
            )
    return cfg


def list_rovers() -> dict[str, str]:
    """Return {rover_id: display_name} for all registered rovers."""
    return {rid: cfg["name"] for rid, cfg in ROVERS.items()}
