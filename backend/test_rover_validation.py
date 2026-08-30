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
