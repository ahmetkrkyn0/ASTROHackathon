"""Mission profiles and scenario management helpers."""

from __future__ import annotations

import json
import os

from . import constants as C

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")

# Weights and constraints frozen at v3.2 spec (docs/lunapath_referans_belgesi_2.md §5.2)
MISSION_PROFILES: dict[str, dict] = {
    "balanced": {
        "name": "Dengeli Kesif",
        "description": "Tum riskleri dengeli sekilde dikkate alan standart mod.",
        "weights": {
            "w_slope": C.W_SLOPE,
            "w_energy": C.W_ENERGY,
            "w_shadow": C.W_SHADOW,
            "w_thermal": C.W_THERMAL,
        },
        "constraints": {
            "max_shadow_h": 40.0,
            "max_slope_deg": 25.0,
            "max_energy_wh": 4000.0,
            "min_soc": 0.20,
        },
        "color": "#3B82F6",
    },
    "energy_saver": {
        "name": "Enerji Tasarrufu",
        "description": "Daha uzun rotalari kabul edip bataryayi korumaya odaklanir.",
        "weights": {
            "w_slope": 0.250,
            "w_energy": 0.450,
            "w_shadow": 0.150,
            "w_thermal": 0.150,
        },
        "constraints": {
            "max_shadow_h": 30.0,
            "max_slope_deg": 20.0,
            "max_energy_wh": 2500.0,
            "min_soc": 0.35,
        },
        "color": "#22C55E",
    },
    "fast_recon": {
        "name": "Hizli Kesif",
        "description": "Daha agresif, daha kisa rota tercih eden profil.",
        "weights": {
            "w_slope": 0.500,
            "w_energy": 0.150,
            "w_shadow": 0.100,
            "w_thermal": 0.250,
        },
        "constraints": {
            "max_shadow_h": 50.0,
            "max_slope_deg": 25.0,
            "max_energy_wh": 5000.0,
            "min_soc": 0.10,
        },
        "color": "#EF4444",
    },
    "shadow_traverse": {
        "name": "Golge Gecis",
        "description": "Golgeli bolgeden gecmek zorunlu — termal guvenlik kritik.",
        "weights": {
            "w_slope": 0.200,
            "w_energy": 0.150,
            "w_shadow": 0.300,
            "w_thermal": 0.350,
        },
        "constraints": {
            "max_shadow_h": 45.0,
            "max_slope_deg": 25.0,
            "max_energy_wh": 4000.0,
            "min_soc": 0.25,
        },
        "color": "#A855F7",
    },
}


# Which constraint keys the PLANNER can enforce during the search, and
# which can only be checked against a simulated route afterwards. Declared
# so /api/profiles can say so instead of publishing four numbers that look
# equally binding. Three of the four steered nothing at all and appeared
# nowhere in the codebase outside this file. (Round 4 review, M-4.)
ENFORCED_CONSTRAINTS: tuple[str, ...] = ("max_slope_deg",)
VERIFIED_CONSTRAINTS: tuple[str, ...] = (
    "max_shadow_h",
    "max_energy_wh",
    "min_soc",
)


def check_profile_constraints(
    profile: dict, summary: dict | None
) -> dict[str, dict]:
    """Verdict per declared constraint, against a simulated route.

    ``max_slope_deg`` is enforced inside the search, so its verdict is
    structural. The other three are path-dependent -- they need a battery
    trace -- so they are checked here, after the fact, and reported with
    ``checked: False`` when no simulation was run rather than silently
    omitted.
    """
    constraints = profile.get("constraints", {})
    verdicts: dict[str, dict] = {
        "max_slope_deg": {
            "limit": constraints.get("max_slope_deg"),
            "enforced_in_search": True,
            "checked": True,
            "actual": None,
            "satisfied": True,
        }
    }

    def entry(limit, actual, satisfied):
        return {
            "limit": limit,
            "enforced_in_search": False,
            "checked": summary is not None and actual is not None,
            "actual": actual,
            "satisfied": satisfied,
        }

    shadow_limit = constraints.get("max_shadow_h")
    shadow_actual = None if summary is None else summary.get("max_continuous_shadow_h")
    verdicts["max_shadow_h"] = entry(
        shadow_limit,
        shadow_actual,
        None
        if shadow_actual is None or shadow_limit is None
        else bool(shadow_actual <= shadow_limit),
    )

    energy_limit = constraints.get("max_energy_wh")
    energy_actual = (
        None if summary is None else summary.get("total_energy_consumed_wh")
    )
    verdicts["max_energy_wh"] = entry(
        energy_limit,
        energy_actual,
        None
        if energy_actual is None or energy_limit is None
        else bool(energy_actual <= energy_limit),
    )

    soc_limit = constraints.get("min_soc")
    soc_actual_pct = None if summary is None else summary.get("min_battery_pct")
    soc_actual = None if soc_actual_pct is None else soc_actual_pct / 100.0
    verdicts["min_soc"] = entry(
        soc_limit,
        None if soc_actual is None else round(soc_actual, 4),
        None
        if soc_actual is None or soc_limit is None
        else bool(soc_actual >= soc_limit),
    )
    return verdicts


def get_profile(profile_id: str) -> dict | None:
    return MISSION_PROFILES.get(profile_id)


def list_profiles() -> dict[str, dict]:
    """Mission profiles, with each constraint labelled by how it is applied.

    A profile used to publish four constraints of which the planner applied
    one, with nothing in the payload distinguishing them. (Round 4, M-4.)
    """
    return {
        profile_id: {
            **profile,
            "constraint_handling": {
                key: (
                    "enforced_in_search"
                    if key in ENFORCED_CONSTRAINTS
                    else "verified_after_simulation"
                )
                for key in profile.get("constraints", {})
            },
        }
        for profile_id, profile in MISSION_PROFILES.items()
    }


def load_scenario(scenario_id: str) -> dict | None:
    path = os.path.join(SCENARIOS_DIR, f"{scenario_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_scenarios() -> list[str]:
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    return [
        os.path.splitext(filename)[0]
        for filename in os.listdir(SCENARIOS_DIR)
        if filename.endswith(".json")
    ]


def compare_results(results: list[dict], rover: dict | None = None) -> dict:
    """Return a lightweight comparison summary for multiple paths.

    *rover* supplies the slope limit the safety key normalises against. It
    was hardcoded to 25.0 -- lpr_1's limit -- so a comparison run for
    nasa_viper or cnsa_yutu_2 (both 20 deg) scored their slopes against a
    ceiling neither rover has. (Round 3 review, L-11.)
    """
    slope_limit = float((rover or C.get_rover())["slope_max_deg"])
    valid = [result for result in results if not result.get("error")]
    if not valid:
        return {
            "shortest_profile": None,
            "safest_profile": None,
            "most_efficient_profile": None,
            "recommendation": "No valid weighted paths found.",
        }

    shortest = min(valid, key=lambda result: result["metrics"]["total_distance_m"])
    # total_shadow_hours is deliberately absent from the safety key: like
    # total_energy_wh below, _compute_path_metrics hardcodes it to 0.0 in
    # fast mode, so including it added a constant to every candidate --
    # no ranking effect, but it implied shadow exposure was weighed.
    # Both terms are dimensionless in [0, 1]: max_thermal_risk is already an
    # MRU penalty, and the slope term is normalised by the rover's own limit.
    # Equal weight is a deliberate, stated choice, not an accident of units.
    safest = min(
        valid,
        key=lambda result: (
            result["metrics"]["max_thermal_risk"]
            + result["metrics"]["max_slope_deg"] / slope_limit
        ),
    )
    # Efficiency ranks on total_weighted_cost, the multi-criteria cost the
    # planner actually minimised. It previously ranked on total_energy_wh,
    # which _compute_path_metrics hardcodes to 0.0 for every path ("not
    # tracked in fast mode") -- so min() returned whichever profile came
    # first in the list and the response asserted it "uses the least
    # energy". A fabricated energy claim from a constant-zero metric is
    # exactly what the layer_validity discipline exists to prevent.
    # (Round 2 review, H-2.)
    efficient = min(valid, key=lambda result: result["metrics"]["total_weighted_cost"])

    return {
        "shortest_profile": shortest.get("profile_id"),
        "safest_profile": safest.get("profile_id"),
        "most_efficient_profile": efficient.get("profile_id"),
        "recommendation": (
            f"{safest.get('profile_id')} minimizes the weighted safety envelope; "
            f"{efficient.get('profile_id')} has the lowest weighted traverse cost. "
            "Energy and shadow totals are not tracked in fast mode, so neither "
            "ranking is an energy claim."
        ),
    }
