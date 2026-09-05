"""Global constants and rover registry for LunaPath."""

from __future__ import annotations

from typing import Any

# Shared environment constants
GRAVITY_MOON = 1.62
LOG_BARRIER_MU = 0.1
DEFAULT_TARGET_RESOLUTION_M = 80
THERMAL_MIN_TRAVERSABLE_C = -150.0

# Rover-catalogue fields the model actually reads. Everything registered in
# ROVERS but absent from this set is published for reference only and steers
# nothing -- ``rover_catalog`` says so explicitly rather than letting a
# frontend infer that every listed number is modelled. Seven fields used to
# sit in the catalogue with zero readers anywhere in the codebase; four of
# them are now wired (p_peak_w, p_shadow_w, p_hibernate_w, h_max_shadow_h)
# and the rest are labelled. (Round 3 review, M-8.)
MODELLED_FIELDS: frozenset[str] = frozenset(
    {
        "mass_kg",
        "v_max_ms",
        "p_base_w",
        "p_peak_w",
        "p_idle_w",
        "p_heater_w",
        "p_shadow_w",
        "p_hibernate_w",
        "p_solar_w",
        "e_cap_wh",
        "slope_comfortable_deg",
        "slope_max_deg",
        "slope_lateral_max_deg",
        "h_max_shadow_h",
        "soc_min_pct",
        "thermal_offset_cold",
        "thermal_offset_hot",
        "bat_op_min_c",
        "bat_op_max_c",
        "elec_op_min_c",
        "elec_op_max_c",
        "mu_coeff",
        "w_slope",
        "w_energy",
        "w_shadow",
        "w_thermal",
        "sensor_payload_w",
        "sensor_heater_w",
    }
)

# Published for reference, read by nothing. Kept in the catalogue because
# they are real published rover specifications and a reader comparing
# profiles wants them -- but labelled so nobody mistakes them for inputs.
DECLARED_ONLY_FIELDS: tuple[str, ...] = (
    "f_net_n",
    "regen_efficiency",
    "thermal_tau_s",
    "h_design_shadow_h",
)

# Multi-rover catalogue
ROVERS: dict[str, dict[str, Any]] = {
    "lpr_1": {
        "name": "LPR-1 (Default)",
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
        "sensor_payload_w": None,
        "sensor_heater_w": None,
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
        "sensor_payload_w": None,
        "sensor_heater_w": None,
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
        "sensor_payload_w": None,
        "sensor_heater_w": None,
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
        "sensor_payload_w": None,
        "sensor_heater_w": None,
    },
}

DEFAULT_ROVER_ID = "lpr_1"

_REQUIRED_FIELDS = ("mass_kg", "p_base_w", "e_cap_wh", "v_max_ms", "f_net_n", "mu_coeff")


class UnknownRoverError(KeyError):
    """Raised by get_rover for an unregistered rover_id.

    A plain KeyError from here reached FastAPI unhandled and turned a bad
    ``rover_id`` in a request body into a 500 instead of a 422 -- the
    caller's mistake, not a server error. Subclassing KeyError keeps any
    existing ``except KeyError`` handling working, while giving main.py's
    exception handler an exact type to route to a 422 response.
    (Faz 1-2-3 review, L4.)
    """


def get_rover(rover_id: str | None = None) -> dict[str, Any]:
    """Return a rover config dict by ID."""
    rid = rover_id or DEFAULT_ROVER_ID
    if rid not in ROVERS:
        raise UnknownRoverError(
            f"Unknown rover_id: {rid!r}. Available: {list(ROVERS.keys())}"
        )

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
                # Published because it is now ENFORCED: the planner refuses
                # any edge whose cross-slope exceeds it. It used to appear
                # only in the dead log-barrier. (Round 3 review, H-1.)
                "slope_lateral_max_deg": float(rover["slope_lateral_max_deg"]),
                "soc_min_pct": float(rover["soc_min_pct"]),
                "h_max_shadow_h": float(rover["h_max_shadow_h"]),
                "sensor_payload_w": rover.get("sensor_payload_w"),
                "sensor_heater_w": rover.get("sensor_heater_w"),
                "default_weights": rover_default_weights(rover_id),
                # Real published specifications that no part of the model
                # reads. Separated so a consumer can show them as reference
                # data without implying they drive a route. (Round 3, M-8.)
                "declared_only": {
                    field: rover.get(field) for field in DECLARED_ONLY_FIELDS
                },
            }
        )
    return catalog


# ── Rover-derived replan thresholds ─────────────────────────────────────────
# The replan trigger thresholds were global constants: every rover had to be
# 10 percent behind its energy plan before a replan fired, and every rover
# tolerated the same 5 K temperature drop, regardless of how much reserve or
# how wide a thermal envelope it actually carried. Both are now derived from
# the rover's own declared limits. (Round 3 review, L-8.)

def soc_deviation_threshold(rover: dict[str, Any] | None = None) -> float:
    """SOC shortfall that forces a replan: half the rover's own reserve.

    A rover holding a 30 percent floor (cnsa_yutu_2) has more room to absorb
    a deviation before the plan stops being executable than one holding 20
    percent (lpr_1), so the trigger scales with the reserve rather than
    being fixed. lpr_1 lands on 0.10 -- the previous global constant -- so
    the default profile's behaviour is unchanged.
    """
    cfg = get_rover() if rover is None else rover
    return float(cfg["soc_min_pct"]) / 2.0


def inner_temperature_drop_k(rover: dict[str, Any] | None = None) -> float:
    """Inner-temperature drop below prediction that forces a replan.

    Scaled to the battery's operating envelope: a rover with a 100 K wide
    envelope (luvmi_m) should not replan on the same 5 K excursion as one
    with a 35 K envelope. Floored at 2 K so a hypothetical narrow envelope
    cannot make the trigger hair-fine. lpr_1 lands on 5.25 K against the
    previous global 5.0 K.
    """
    cfg = get_rover() if rover is None else rover
    low = cfg.get("bat_op_min_c")
    high = cfg.get("bat_op_max_c")
    if low is None or high is None:
        return 5.0
    return max(2.0, 0.15 * (float(high) - float(low)))


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
