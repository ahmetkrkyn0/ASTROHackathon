"""Mission profiles and scenario management."""

import json
import os

from . import constants as C

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")

MISSION_PROFILES = {
    "balanced": {
        "name": "Dengeli Kesif",
        "description": "Tum riskleri dengeli sekilde dikkate alan standart mod",
        "weights": {
            "w_slope": 0.409,
            "w_energy": 0.259,
            "w_shadow": 0.142,
            "w_thermal": 0.190,
        },
        "constraints": {
            "max_shadow_h": 40,
            "max_slope_deg": 25,
            "max_energy_wh": 4000,
            "min_soc": 0.20,
        },
        "color": "#3B82F6",
    },
    "energy_saver": {
        "name": "Enerji Tasarrufu",
        "description": "Batarya korunmasini maksimize eden mod",
        "weights": {
            "w_slope": 0.250,
            "w_energy": 0.450,
            "w_shadow": 0.150,
            "w_thermal": 0.150,
        },
        "constraints": {
            "max_shadow_h": 30,
            "max_slope_deg": 20,
            "max_energy_wh": 2500,
            "min_soc": 0.35,
        },
        "color": "#22C55E",
    },
    "fast_recon": {
        "name": "Hizli Kesif",
        "description": "Zaman kisitli — en kisa rotayi bul, riskleri tolere et",
        "weights": {
            "w_slope": 0.500,
            "w_energy": 0.150,
            "w_shadow": 0.100,
            "w_thermal": 0.250,
        },
        "constraints": {
            "max_shadow_h": 50,
            "max_slope_deg": 25,
            "max_energy_wh": 5000,
            "min_soc": 0.10,
        },
        "color": "#EF4444",
    },
    "shadow_traverse": {
        "name": "Golge Gecis",
        "description": "Golgeli bolgeden gecmek zorunlu — termal guvenlik kritik",
        "weights": {
            "w_slope": 0.200,
            "w_energy": 0.150,
            "w_shadow": 0.300,
            "w_thermal": 0.350,
        },
        "constraints": {
            "max_shadow_h": 45,
            "max_slope_deg": 25,
            "max_energy_wh": 4000,
            "min_soc": 0.25,
        },
        "color": "#A855F7",
    },
}


def get_profile(profile_id: str) -> dict | None:
    return MISSION_PROFILES.get(profile_id)


def list_profiles() -> dict:
    return MISSION_PROFILES


def load_scenario(scenario_id: str) -> dict | None:
    path = os.path.join(SCENARIOS_DIR, f"{scenario_id}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_scenarios() -> list[str]:
    os.makedirs(SCENARIOS_DIR, exist_ok=True)
    return [
        os.path.splitext(f)[0]
        for f in os.listdir(SCENARIOS_DIR)
        if f.endswith(".json")
    ]


def compare_results(results: list[dict]) -> dict:
    """Given a list of PathResult dicts, produce comparison summary."""
    valid = [r for r in results if not r.get("error")]
    if not valid:
        return {"shortest_profile": None, "safest_profile": None, "most_efficient_profile": None, "recommendation": "No valid paths found"}

    shortest = min(valid, key=lambda r: r["metrics"]["total_distance_m"])
    safest = min(valid, key=lambda r: r["metrics"]["max_slope_deg"] + r["metrics"]["max_thermal_risk"])
    efficient = min(valid, key=lambda r: r["metrics"]["total_energy_wh"])

    return {
        "shortest_profile": shortest.get("profile_id", "?"),
        "safest_profile": safest.get("profile_id", "?"),
        "most_efficient_profile": efficient.get("profile_id", "?"),
        "recommendation": f"Balanced is recommended for general use. Energy saver uses {efficient['metrics']['total_energy_wh']:.0f} Wh.",
    }
