"""Global constants and rover registry for LunaPath."""

from __future__ import annotations

from typing import Any

# Shared environment constants
GRAVITY_MOON = 1.62
LOG_BARRIER_MU = 0.1
DEFAULT_TARGET_RESOLUTION_M = 80
THERMAL_MIN_TRAVERSABLE_C = -150.0

# Multi-rover catalogue
ROVERS: dict[str, dict[str, Any]] = {
    "lpr_1": {
        "name": "LPR-1 (Varsayilan)",
        "mass_kg": 450,
        "v_max_ms": 0.2,
        "p_base_w": 200,
        "p_peak_w": 450,
        "e_cap_wh": 5420,
        "p_idle_w": 40,
        "p_heater_w": 25,
        "p_shadow_w": 65,
        "p_hibernate_w": 108,
        "p_solar_w": 410,
        "regen_efficiency": 0.10,
        "slope_comfortable_deg": 15,
        "slope_max_deg": 25,
        "slope_lateral_max_deg": 18,
        "h_max_shadow_h": 50,
        "h_design_shadow_h": 70,
        "soc_min_pct": 0.20,
        "thermal_tau_s": 7200,
        "thermal_offset_cold": 60,
        "thermal_offset_hot": -40,
        "bat_op_min_c": 0,
        "bat_op_max_c": 35,
        "elec_op_min_c": -10,
        "elec_op_max_c": 40,
        "f_net_n": 210,
        "mu_coeff": 3.471,
        "w_slope": 0.409,
        "w_energy": 0.259,
        "w_shadow": 0.142,
        "w_thermal": 0.190,
    },
    "luvmi_m": {
        "name": "LUVMI-M",
        "mass_kg": 40,
        "v_max_ms": 0.05,
        "p_base_w": 80,
        "p_peak_w": 250,
        "e_cap_wh": 1400,
        "p_idle_w": 30,
        "p_heater_w": 20,
        "p_shadow_w": 50,
        "p_hibernate_w": None,
        "p_solar_w": 140,
        "regen_efficiency": 0.0,
        "slope_comfortable_deg": 15,
        "slope_max_deg": 25,
        "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 4,
        "h_design_shadow_h": 6,
        "soc_min_pct": 0.20,
        "thermal_tau_s": None,
        "thermal_offset_cold": None,
        "thermal_offset_hot": None,
        "bat_op_min_c": -100,
        "bat_op_max_c": 0,
        "elec_op_min_c": None,
        "elec_op_max_c": None,
        "f_net_n": 50,
        "mu_coeff": 1.296,
        "w_slope": 0.40,
        "w_energy": 0.30,
        "w_shadow": 0.30,
        "w_thermal": 0.0,
    },
    "nasa_viper": {
        "name": "NASA VIPER",
        "mass_kg": 450,
        "v_max_ms": 0.06,
        "p_base_w": 250,
        "p_peak_w": 500,
        "e_cap_wh": 4000,
        "p_idle_w": 80,
        "p_heater_w": 50,
        "p_shadow_w": 130,
        "p_hibernate_w": 100,
        "p_solar_w": 450,
        "regen_efficiency": 0.10,
        "slope_comfortable_deg": 15,
        "slope_max_deg": 20,
        "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 96,
        "h_design_shadow_h": 120,
        "soc_min_pct": 0.20,
        "thermal_tau_s": 8000,
        "thermal_offset_cold": 60,
        "thermal_offset_hot": -40,
        "bat_op_min_c": 0,
        "bat_op_max_c": 35,
        "elec_op_min_c": -20,
        "elec_op_max_c": 50,
        "f_net_n": 200,
        "mu_coeff": 3.645,
        "w_slope": 0.35,
        "w_energy": 0.25,
        "w_shadow": 0.20,
        "w_thermal": 0.20,
    },
    "cnsa_yutu_2": {
        "name": "CNSA Yutu-2",
        "mass_kg": 140,
        "v_max_ms": 0.05,
        "p_base_w": 100,
        "p_peak_w": 200,
        "e_cap_wh": 1500,
        "p_idle_w": 40,
        "p_heater_w": 20,
        "p_shadow_w": 60,
        "p_hibernate_w": 5,
        "p_solar_w": 300,
        "regen_efficiency": 0.0,
        "slope_comfortable_deg": 10,
        "slope_max_deg": 20,
        "slope_lateral_max_deg": 15,
        "h_max_shadow_h": 2,
        "h_design_shadow_h": 3,
        "soc_min_pct": 0.30,
        "thermal_tau_s": 5000,
        "thermal_offset_cold": 70,
        "thermal_offset_hot": -30,
        "bat_op_min_c": -10,
        "bat_op_max_c": 30,
        "elec_op_min_c": -40,
        "elec_op_max_c": 55,
        "f_net_n": 80,
        "mu_coeff": 2.835,
        "w_slope": 0.50,
        "w_energy": 0.30,
        "w_shadow": 0.20,
        "w_thermal": 0.0,
    },
}

DEFAULT_ROVER_ID = "lpr_1"

_REQUIRED_FIELDS = ("mass_kg", "p_base_w", "e_cap_wh", "v_max_ms", "f_net_n", "mu_coeff")


def get_rover(rover_id: str | None = None) -> dict[str, Any]:
    """Return a rover config dict by ID."""
    rid = rover_id or DEFAULT_ROVER_ID
    if rid not in ROVERS:
        raise KeyError(f"Unknown rover_id: {rid!r}. Available: {list(ROVERS.keys())}")

    cfg = dict(ROVERS[rid])
    for field in _REQUIRED_FIELDS:
        if cfg.get(field) is None:
            raise ValueError(
                f"Rover {rid!r} has required field {field!r} = None. "
                "Cannot proceed without kinematic or energy parameters."
            )

    cfg["id"] = rid
    return cfg


def list_rovers() -> dict[str, str]:
    """Return {rover_id: display_name} for all registered rovers."""
    return {rid: cfg["name"] for rid, cfg in ROVERS.items()}


def rover_default_weights(rover_id: str | None = None) -> dict[str, float]:
    rover = get_rover(rover_id)
    return {
        "w_slope": float(rover["w_slope"]),
        "w_energy": float(rover["w_energy"]),
        "w_shadow": float(rover["w_shadow"]),
        "w_thermal": float(rover["w_thermal"]),
    }


def rover_catalog() -> list[dict[str, Any]]:
    """Return a frontend-friendly rover catalogue."""
    catalog: list[dict[str, Any]] = []
    for rover_id in ROVERS:
        rover = get_rover(rover_id)
        catalog.append(
            {
                "id": rover_id,
                "name": rover["name"],
                "mass_kg": float(rover["mass_kg"]),
                "v_max_ms": float(rover["v_max_ms"]),
                "e_cap_wh": float(rover["e_cap_wh"]),
                "slope_max_deg": float(rover["slope_max_deg"]),
                "h_max_shadow_h": float(rover["h_max_shadow_h"]),
                "default_weights": rover_default_weights(rover_id),
            }
        )
    return catalog


# Backward-compatible aliases for the default rover. Older modules/tests still
# importing scalar constants continue to work while the planner becomes rover-aware.
_DEFAULT_ROVER = get_rover(DEFAULT_ROVER_ID)

ROVER_MASS_KG = float(_DEFAULT_ROVER["mass_kg"])
V_MAX_MS = float(_DEFAULT_ROVER["v_max_ms"])
P_BASE_W = float(_DEFAULT_ROVER["p_base_w"])
P_PEAK_W = float(_DEFAULT_ROVER["p_peak_w"])
E_CAP_WH = float(_DEFAULT_ROVER["e_cap_wh"])
P_IDLE_W = float(_DEFAULT_ROVER["p_idle_w"])
P_HEATER_W = float(_DEFAULT_ROVER["p_heater_w"])
P_SHADOW_W = float(_DEFAULT_ROVER["p_shadow_w"])
P_HIBERNATE_W = float(_DEFAULT_ROVER["p_hibernate_w"])
P_SOLAR_W = float(_DEFAULT_ROVER["p_solar_w"])
REGEN_EFFICIENCY = float(_DEFAULT_ROVER["regen_efficiency"])
SLOPE_COMFORTABLE_DEG = float(_DEFAULT_ROVER["slope_comfortable_deg"])
SLOPE_MAX_DEG = float(_DEFAULT_ROVER["slope_max_deg"])
SLOPE_LATERAL_MAX_DEG = float(_DEFAULT_ROVER["slope_lateral_max_deg"])
H_MAX_SHADOW_H = float(_DEFAULT_ROVER["h_max_shadow_h"])
H_DESIGN_SHADOW_H = float(_DEFAULT_ROVER["h_design_shadow_h"])
SOC_MIN_PCT = float(_DEFAULT_ROVER["soc_min_pct"])
THERMAL_TAU_S = float(_DEFAULT_ROVER["thermal_tau_s"])
THERMAL_OFFSET_COLD = float(_DEFAULT_ROVER["thermal_offset_cold"])
THERMAL_OFFSET_HOT = float(_DEFAULT_ROVER["thermal_offset_hot"])
BAT_OP_MIN_C = float(_DEFAULT_ROVER["bat_op_min_c"])
BAT_OP_MAX_C = float(_DEFAULT_ROVER["bat_op_max_c"])
ELEC_OP_MIN_C = float(_DEFAULT_ROVER["elec_op_min_c"])
ELEC_OP_MAX_C = float(_DEFAULT_ROVER["elec_op_max_c"])
F_NET_N = float(_DEFAULT_ROVER["f_net_n"])
MU_COEFF = float(_DEFAULT_ROVER["mu_coeff"])
W_SLOPE = float(_DEFAULT_ROVER["w_slope"])
W_ENERGY = float(_DEFAULT_ROVER["w_energy"])
W_SHADOW = float(_DEFAULT_ROVER["w_shadow"])
W_THERMAL = float(_DEFAULT_ROVER["w_thermal"])
