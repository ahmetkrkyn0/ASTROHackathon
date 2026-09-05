"""Global constants and rover registry for LunaPath."""

from __future__ import annotations

from typing import Any

from .slip_model import SlipAnchor, rover_slip_block

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
        # C4: the fifth criterion's weight (LOLA LDRM roughness).
        "w_roughness",
        "sensor_payload_w",
        "sensor_heater_w",
        # C3: the anchors cost_engine.edge_travel_time_s reads through
        # slip_model.slip_ratio -- every time and energy figure depends on it.
        "slip_curve",
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
    # C3: published regolith / test-bed parameters behind the slip anchors
    # (Yutu-2's Bekker-type ranges, VIPER's GRC-1 test bed). Reference only:
    # no Bekker equation is coded; the slip curve reads its anchors, not this.
    "regolith",
)

# ── C3: slip anchors ─────────────────────────────────────────────────────────
# The two sourced points every slip curve in the catalogue is built from.
# No anchor exists without a source; a profile that has no slip data of its
# own carries these as EXPLICIT assumptions (kind "assumption", source
# starting with "assumption:"), never as a silent default. See
# app/slip_model.py for the claim limits.

SLIP_ANCHOR_YUTU2_FLAT = SlipAnchor(
    slope_deg=0.0,
    slip=0.0375,
    sigma=0.01875,
    kind="measured",
    source=(
        "Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip "
        "ratios are between 0 and -0.075' (skid) on slopes up to 8.86 deg; the "
        "magnitude midpoint of |0..0.075| is taken as the flat-ground value and "
        "sigma = range/4 -- Nature Communications 2024 (PMC11258293), Methods, "
        "'Lunar regolith parameter estimation'"
    ),
)

SLIP_ANCHOR_YUTU2_STEEPEST = SlipAnchor(
    slope_deg=8.86,
    slip=0.075,
    sigma=0.01875,
    kind="measured_bound",
    source=(
        "Yutu-2 (Chang'e-4) measured: the upper end of the |0..0.075| slip "
        "range at the steepest slope driven (8.86 deg, outbound traverse) -- "
        "Nature Communications 2024 (PMC11258293), Results, 'Topographic and "
        "mobility hazards analysis'"
    ),
)

SLIP_ANCHOR_VIPER_15 = SlipAnchor(
    slope_deg=15.0,
    slip=0.40,
    sigma=0.20,
    kind="design_constraint",
    source=(
        "VIPER mobility design requirement: 'a maximum of 40% slip up a maximum "
        "slope of 15 deg' (an upper bound, not a typical value); GRC-1 simulant "
        "at 15-20 percent relative density, MGRU test unit, slip from wheel "
        "rotation rates against Optitrack motion tracking -- PSJ 2025 "
        "(10.3847/PSJ/add13f) sect. 3.5 and 3.2. sigma: assumption, Yutu-2's "
        "relative spread (sigma/mu = 0.5) transferred"
    ),
)


def _transferred(anchor: SlipAnchor, note: str) -> SlipAnchor:
    """The same point, re-labelled as an assumption for a profile it was not
    measured or specified for. The original source travels with it."""
    return SlipAnchor(
        slope_deg=anchor.slope_deg,
        slip=anchor.slip,
        sigma=anchor.sigma,
        kind="assumption",
        source=f"assumption: {note} | {anchor.source}",
    )


_YUTU2_FLAT_TRANSFERRED = _transferred(
    SLIP_ANCHOR_YUTU2_FLAT,
    "flat-ground slip transferred from Yutu-2's Chang'e-4 measurement (flat-"
    "ground slip of a driven wheel is only weakly terrain-dependent); no "
    "published flat-ground slip for this profile",
)
_VIPER_15_TRANSFERRED = _transferred(
    SLIP_ANCHOR_VIPER_15,
    "VIPER's 15 deg design ceiling used as this profile's 15 deg anchor; no "
    "published slip-versus-slope data for this vehicle",
)

# Published regolith / test-bed parameters behind the anchors. Reference
# only ("read_by": "nothing"): no Bekker/Wong equation is coded here.
REGOLITH_YUTU2: dict[str, Any] = {
    "site": "Chang'e-4 landing region, Von Karman crater (lunar far side)",
    "internal_friction_angle_deg": [21.5, 42.0],
    "cohesion_pa": [520, 3154],
    "sinkage_exponent": [0.87, 1.0],
    "mean_wheel_sinkage_mm": 8.0,
    "wheel_sinkage_range_mm": [5.0, 15.0],
    "bearing_strength_kpa": 4.0,
    "max_slope_driven_deg": 8.86,
    "slip_ratio_range": [-0.075, 0.0],
    "validity": "MEASURED at the Chang'e-4 site (far-side mare), not at the pole",
    "source": (
        "Nature Communications 2024 (PMC11258293), Results 'Mechanical property "
        "identification' (Fig. 4) and 'Topographic and mobility hazards "
        "analysis'; Ding et al., Science Robotics 2022 (abj6660)"
    ),
    "read_by": "nothing",
}

REGOLITH_VIPER_TESTBED: dict[str, Any] = {
    "site": "VIPER MGRU mobility test bed (laboratory)",
    "simulant": "GRC-1",
    "relative_density_pct": [15, 20],
    "validity": (
        "GROUND_TEST: loose GRC-1 as a lower-bound strength case for the "
        "south pole; not a measurement of polar regolith"
    ),
    "source": "PSJ 2025 (10.3847/PSJ/add13f), sect. 3.2",
    "read_by": "nothing",
}

# ── C4: the roughness criterion's weight ─────────────────────────────────────
# ASSUMPTION, stated rather than hidden: no rover profile and no mission
# profile has a published weighting for a roughness criterion (the four
# existing weights are the reference document's gradient-normalised expert
# weights, not AHP -- doc 11). The fifth criterion therefore enters every
# profile at one value, of the order of the minor criteria already there
# (shadow 0.10-0.30, thermal 0-0.35), and the other four are NOT rescaled so
# the term stays purely additive. Its sensitivity is swept 0-0.5 in
# docs/research/roughness_psr_report.md; on Site11 the lunar-night route
# moved at 0.05 already, the daytime pair only from 0.15 (probe 3, C4 spec).
W_ROUGHNESS_DEFAULT: float = 0.15

# ── B1: the fault model behind the recovery policy ──────────────────────────
# No rover in this catalogue publishes a mobility fault rate or a recovery
# time, so neither is a profile field: a number without a source does not
# go into the catalogue. The recovery policy (app/survival.py) needs both,
# and takes them as EXPLICIT assumptions -- Lamarre, Malhotra and Kelly's
# large-scale experiment values -- reported with this source string on
# every response that used them, and swept in the report.
FAILURE_RATE_PER_KM_ASSUMED: float = 0.2      # one mobility fault per 5 000 m driven
FAULT_RECOVERY_HOURS_ASSUMED: float = 10.0    # 36 000 s to resolve a fault, holding position
FAILURE_MODEL_SOURCE: str = (
    "assumption: Lamarre, Malhotra, Kelly -- Recovery Policies for Safe Exploration "
    "of Lunar PSRs (Acta Astronautica 2023, arXiv 2307.16786) experiment 3 and Safe "
    "Mission-Level Path Planning (IEEE AERO 2024, arXiv 2401.08558) Table II: Poisson "
    "faults at 1 per 5 000 m driven, 36 000 s to recover; no rover profile in this "
    "catalogue publishes either number"
)

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
        # C3: no published slip data for LPR-1 -- both anchors are transfers.
        "slip_curve": (_YUTU2_FLAT_TRANSFERRED, _VIPER_15_TRANSFERRED),
        "regolith": None,
        "w_slope": 0.409,
        "w_energy": 0.259,
        "w_shadow": 0.142,
        "w_thermal": 0.190,
        "w_roughness": W_ROUGHNESS_DEFAULT,
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
        # C3: no published slip data for LUVMI-M -- both anchors are transfers.
        "slip_curve": (_YUTU2_FLAT_TRANSFERRED, _VIPER_15_TRANSFERRED),
        "regolith": None,
        "w_slope": 0.40,
        "w_energy": 0.30,
        "w_shadow": 0.30,
        "w_thermal": 0.0,
        "w_roughness": W_ROUGHNESS_DEFAULT,
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
        # C3: VIPER's own 15 deg / 40 percent design requirement; the flat-
        # ground point is Yutu-2's, transferred. Yutu-2's 8.86 deg point is
        # NOT transferred: Chang'e-4 mare regolith and loose GRC-1 are
        # different soils, and joining them would put an unsourced kink
        # between 8.86 and 15 deg.
        "slip_curve": (_YUTU2_FLAT_TRANSFERRED, SLIP_ANCHOR_VIPER_15),
        "regolith": REGOLITH_VIPER_TESTBED,
        "w_slope": 0.35,
        "w_energy": 0.25,
        "w_shadow": 0.20,
        "w_thermal": 0.20,
        "w_roughness": W_ROUGHNESS_DEFAULT,
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
        # C3: Yutu-2's own measured points (0 deg, 8.86 deg); beyond its
        # measured slopes VIPER's 15 deg ceiling is transferred.
        "slip_curve": (
            SLIP_ANCHOR_YUTU2_FLAT,
            SLIP_ANCHOR_YUTU2_STEEPEST,
            _VIPER_15_TRANSFERRED,
        ),
        "regolith": REGOLITH_YUTU2,
        "w_slope": 0.50,
        "w_energy": 0.30,
        "w_shadow": 0.20,
        "w_thermal": 0.0,
        "w_roughness": W_ROUGHNESS_DEFAULT,
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
        "w_roughness": float(rover["w_roughness"]),
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
                # C3: the slip curve the model applies, its anchors and their
                # sources, and the claim limit -- a literature-anchored
                # MODEL, never a measurement.
                "slip_model": rover_slip_block(rover),
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
W_ROUGHNESS = float(_DEFAULT_ROVER["w_roughness"])
