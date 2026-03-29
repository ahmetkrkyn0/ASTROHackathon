"""Mission profiles and scenario management helpers."""

from __future__ import annotations

import json
import os

from .constants import get_rover

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")


def _build_profiles(rover_config: dict | None = None) -> dict[str, dict]:
    """Build mission profiles using the given rover's default weights."""
    rc = rover_config or get_rover()
    return {
        "balanced": {
            "name": "Dengeli Kesif",
            "description": "Tum riskleri dengeli sekilde dikkate alan standart mod.",
            "weights": {
                "w_slope": rc["w_slope"],
                "w_energy": rc["w_energy"],
                "w_shadow": rc["w_shadow"],
                "w_thermal": rc["w_thermal"],
            },
            "constraints": {
                "max_shadow_h": 40.0,
                "max_slope_deg": rc["slope_max_deg"],
                "max_energy_wh": rc["e_cap_wh"] * 0.74,
                "min_soc": rc["soc_min_pct"],
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
                "max_slope_deg": rc["slope_max_deg"] - 5,
                "max_energy_wh": rc["e_cap_wh"] * 0.46,
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
                "max_slope_deg": rc["slope_max_deg"],
                "max_energy_wh": rc["e_cap_wh"] * 0.92,
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
                "max_slope_deg": rc["slope_max_deg"],
                "max_energy_wh": rc["e_cap_wh"] * 0.74,
                "min_soc": 0.25,
            },
            "color": "#A855F7",
        },
    }


# Default profiles for backward compatibility (LPR-1)
MISSION_PROFILES: dict[str, dict] = _build_profiles()


def get_profiles(rover_config: dict | None = None) -> dict[str, dict]:
    """Return mission profiles for a given rover."""
    if rover_config is None:
        return MISSION_PROFILES
    return _build_profiles(rover_config)


def get_profile(profile_id: str, rover_config: dict | None = None) -> dict | None:
    profiles = get_profiles(rover_config)
    return profiles.get(profile_id)


def list_profiles(rover_config: dict | None = None) -> dict[str, dict]:
    return get_profiles(rover_config)


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


def compare_results(results: list[dict]) -> dict:
    """Return a lightweight comparison summary for multiple paths."""
    valid = [result for result in results if not result.get("error")]
    if not valid:
        return {
            "shortest_profile": None,
            "safest_profile": None,
            "most_efficient_profile": None,
            "recommendation": "No valid weighted paths found.",
        }

    shortest = min(valid, key=lambda result: result["metrics"]["total_distance_m"])
    safest = min(
        valid,
        key=lambda result: (
            result["metrics"]["total_shadow_hours"]
            + result["metrics"]["max_thermal_risk"]
            + result["metrics"]["max_slope_deg"] / 25.0
        ),
    )
    efficient = min(valid, key=lambda result: result["metrics"]["total_energy_wh"])

    return {
        "shortest_profile": shortest.get("profile_id"),
        "safest_profile": safest.get("profile_id"),
        "most_efficient_profile": efficient.get("profile_id"),
        "recommendation": (
            f"{safest.get('profile_id')} minimizes the weighted safety envelope; "
            f"{efficient.get('profile_id')} uses the least energy."
        ),
    }
