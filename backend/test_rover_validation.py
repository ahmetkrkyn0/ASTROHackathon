"""External reality check: rover constants against flown missions.

Every assertion here is a NECESSARY condition, not a point-accuracy claim
(see the honesty note at the top of the Phase 6 plan). A real mission
achieving distance D over duration T means: no rover profile modelling
that class of hardware may have a top speed physically incapable of
covering D in T. These tests catch a corrupted or fabricated constant;
they do not certify simulation fidelity.
"""

from __future__ import annotations

from app.constants import get_rover
from app.mission_reference import (
    PRAGYAN_MISSION,
    pragyan_active_days,
    pragyan_average_rate_m_per_day,
    yutu2_average_rate_m_per_day,
)

_SECONDS_PER_DAY = 86400.0


def test_yutu2_profile_top_speed_could_physically_average_the_observed_rate():
    """v_max, expressed as m/day, must exceed the real (dormancy-included)
    average rate -- otherwise the profile could not have covered that
    distance even driving nonstop."""
    rover = get_rover("cnsa_yutu_2")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day > yutu2_average_rate_m_per_day()


def test_yutu2_profile_top_speed_is_not_absurdly_faster_than_reality():
    """Upper sanity bound against a mistyped constant (km/h entered as
    m/s would inflate v_max by 3.6x, a decimal slip by 10x).

    The bound is built on Pragyan's rate, not Yutu-2's. Yutu-2's
    0.10 m/day is a calendar-day average across multi-year lunar-night
    dormancy, so it understates driving speed by roughly four orders of
    magnitude -- any ceiling derived from it would either be violated by
    a correct constant or too loose to catch anything. Pragyan's 10.1
    m/day comes from a single continuous ten-day window (see
    PRAGYAN_MISSION), where duty-cycle ambiguity is small enough for the
    ratio to mean something.

    A rover driving at cnsa_yutu_2's v_max covers ~426x Pragyan's daily
    rate, which is the real gap between top speed and operational pace
    (imaging, commanding, ground review). The 1000x ceiling leaves
    headroom above that -- lpr_1, the fastest profile in the catalogue,
    sits at 1704x and is deliberately not covered by this test -- while
    still failing on the smallest unit error worth guarding against: a
    km/h value entered as m/s inflates v_max 3.6x, to 1534x.
    """
    rover = get_rover("cnsa_yutu_2")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day < pragyan_average_rate_m_per_day() * 1e3


def test_cnsa_yutu2_profile_could_physically_cover_pragyans_distance():
    """Cross-mission bound: LunaPath's slow-rover-class profile
    (cnsa_yutu_2), run continuously for Pragyan's real active window,
    must be physically capable of exceeding Pragyan's real distance.
    Real operations always include imaging, commanding and ISRO ground
    review, so actual driving time is well below this ceiling -- this
    test only asserts the ceiling is not already violated."""
    rover = get_rover("cnsa_yutu_2")
    max_possible_m = (
        float(rover["v_max_ms"]) * _SECONDS_PER_DAY * pragyan_active_days()
    )
    assert max_possible_m >= float(PRAGYAN_MISSION["total_distance_m"])


def test_lpr1_default_speed_exceeds_every_referenced_real_mission_rate():
    """LPR-1 is LunaPath's default, higher-capability profile; it should
    not be constant-for-constant slower than any flown mission this
    catalogue references."""
    rover = get_rover("lpr_1")
    top_speed_m_per_day = float(rover["v_max_ms"]) * _SECONDS_PER_DAY
    assert top_speed_m_per_day > yutu2_average_rate_m_per_day()
    assert top_speed_m_per_day > pragyan_average_rate_m_per_day()


def test_all_rover_speeds_are_within_a_physically_plausible_planetary_rover_band():
    """0 < v_max <= 1 m/s covers every flown or proposed lunar/martian
    rover to date (Perseverance's peak is ~0.042 m/s; VIPER's design
    target is a few cm/s); this is a broad corruption guard, not a
    per-rover claim."""
    for rover_id in ("lpr_1", "luvmi_m", "nasa_viper", "cnsa_yutu_2"):
        v_max = float(get_rover(rover_id)["v_max_ms"])
        assert 0.0 < v_max <= 1.0

import pytest  # noqa: E402


# ── C3: slip anchors, their sources and the regolith reference ───────────────
#
# Every anchor in the catalogue must cite where it came from; the two
# sourced points are VIPER's 15 deg / 40 percent design requirement (PSJ
# 2025) and Yutu-2's measured 0..0.075 on slopes up to 8.86 deg (Nature
# Communications 2024). A profile with no slip data of its own carries
# those as explicit assumptions, never as silent defaults.

import json  # noqa: E402

from app.constants import (  # noqa: E402
    DECLARED_ONLY_FIELDS,
    MODELLED_FIELDS,
    ROVERS,
    rover_catalog,
)
from app.slip_model import SlipAnchor, compile_curve, slip_ratio  # noqa: E402


def test_every_profile_carries_a_valid_sourced_slip_curve():
    for rover_id, cfg in ROVERS.items():
        anchors = cfg["slip_curve"]
        assert isinstance(anchors, tuple) and len(anchors) >= 2, rover_id
        assert all(isinstance(a, SlipAnchor) for a in anchors), rover_id
        assert anchors[0].slope_deg == 0.0, rover_id
        compile_curve(anchors)  # raises on any malformed anchor
        assert all(a.source.strip() for a in anchors), rover_id
        assert any("Yutu-2" in a.source for a in anchors), rover_id
        assert any("VIPER" in a.source for a in anchors), rover_id


def test_viper_carries_its_own_design_constraint_anchor():
    anchors = ROVERS["nasa_viper"]["slip_curve"]
    viper = [a for a in anchors if a.slope_deg == 15.0]
    assert len(viper) == 1
    assert viper[0].slip == 0.40
    assert viper[0].kind == "design_constraint"
    assert "PSJ" in viper[0].source and "40%" in viper[0].source
    assert slip_ratio(15.0, get_rover("nasa_viper")) == pytest.approx(0.40, rel=1e-12)


def test_yutu2_carries_its_own_measured_anchors():
    anchors = ROVERS["cnsa_yutu_2"]["slip_curve"]
    measured = [a for a in anchors if a.kind.startswith("measured")]
    assert len(measured) == 2
    steepest = [a for a in anchors if a.slope_deg == 8.86]
    assert len(steepest) == 1 and steepest[0].slip == 0.075
    assert steepest[0].kind == "measured_bound"
    flat = anchors[0]
    assert flat.kind == "measured" and flat.slip == 0.0375 and flat.sigma == 0.01875
    # Its 15 deg point is VIPER's, transferred -- and says so.
    fifteen = [a for a in anchors if a.slope_deg == 15.0][0]
    assert fifteen.kind == "assumption" and fifteen.source.startswith("assumption:")


def test_profiles_without_slip_data_carry_only_labelled_assumptions():
    for rover_id in ("lpr_1", "luvmi_m"):
        for anchor in ROVERS[rover_id]["slip_curve"]:
            assert anchor.kind == "assumption", (rover_id, anchor)
            assert anchor.source.startswith("assumption:"), (rover_id, anchor)


def test_vipers_flat_anchor_is_a_labelled_transfer_from_yutu2():
    flat = ROVERS["nasa_viper"]["slip_curve"][0]
    assert flat.kind == "assumption"
    assert flat.source.startswith("assumption:") and "Yutu-2" in flat.source


def test_slip_curve_is_modelled_and_regolith_is_declared_only():
    assert "slip_curve" in MODELLED_FIELDS
    assert "regolith" in DECLARED_ONLY_FIELDS
    assert "regolith" not in MODELLED_FIELDS


def test_yutu2_regolith_reference_carries_the_published_ranges():
    regolith = ROVERS["cnsa_yutu_2"]["regolith"]
    assert regolith["internal_friction_angle_deg"] == [21.5, 42.0]
    assert regolith["cohesion_pa"] == [520, 3154]
    assert regolith["sinkage_exponent"] == [0.87, 1.0]
    assert regolith["mean_wheel_sinkage_mm"] == 8.0
    assert regolith["wheel_sinkage_range_mm"] == [5.0, 15.0]
    assert regolith["bearing_strength_kpa"] == 4.0
    assert regolith["max_slope_driven_deg"] == 8.86
    assert "MEASURED" in regolith["validity"] and "polar" not in regolith["validity"].lower()
    assert regolith["source"]
    assert regolith["read_by"] == "nothing"


def test_viper_regolith_reference_names_the_test_bed():
    regolith = ROVERS["nasa_viper"]["regolith"]
    assert regolith["simulant"] == "GRC-1"
    assert regolith["relative_density_pct"] == [15, 20]
    assert "GROUND_TEST" in regolith["validity"]
    assert ROVERS["lpr_1"]["regolith"] is None
    assert ROVERS["luvmi_m"]["regolith"] is None


def test_rover_catalog_publishes_the_slip_model_block():
    catalog = rover_catalog()
    by_id = {entry["id"]: entry for entry in catalog}
    for entry in catalog:
        block = entry["slip_model"]
        assert block["applied"] is True
        assert block["validity"] == "MODEL"
        assert block["model_id"]
        assert "not a measurement" in block["claim"].lower()
        assert len(block["table"]) == 6
        assert [row["slope_deg"] for row in block["table"]] == [0, 5, 10, 15, 20, 25]
        for row in block["table"]:
            assert row["time_energy_factor"] == pytest.approx(1.0 / (1.0 - row["slip"]))
        assert all(a["source"] for a in block["anchors"])
        assert entry["declared_only"]["regolith"] == ROVERS[entry["id"]]["regolith"]
    viper = by_id["nasa_viper"]["slip_model"]
    assert viper["table"][3]["slip"] == pytest.approx(0.40)
    assert viper["table"][5]["within_slope_limit"] is False
    assert viper["table"][3]["within_slope_limit"] is True
    json.dumps(catalog, allow_nan=False)
