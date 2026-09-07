"""Reference data integrity tests.

These do not validate the numbers against the outside world (that already
happened when the values were cited) -- they guard the dataset against
being silently edited into nonsense later.
"""

from __future__ import annotations


from app.mission_reference import (
    PRAGYAN_MISSION,
    YUTU_2_MILESTONES,
    pragyan_active_days,
    pragyan_average_rate_m_per_day,
    yutu2_average_rate_m_per_day,
)


def test_yutu2_has_at_least_two_milestones():
    assert len(YUTU_2_MILESTONES) >= 2


def test_yutu2_milestones_are_chronologically_increasing():
    dates = [m.on_date for m in YUTU_2_MILESTONES]
    assert dates == sorted(dates)


def test_yutu2_distance_never_decreases_between_milestones():
    distances = [m.total_distance_m for m in YUTU_2_MILESTONES]
    assert distances == sorted(distances)


def test_every_yutu2_milestone_cites_a_source():
    for milestone in YUTU_2_MILESTONES:
        assert milestone.source.strip() != ""


def test_yutu2_average_rate_is_a_small_positive_number():
    """Sanity band, not a prediction: a rover this size cannot average
    more than a few metres a day even during active lunar days."""
    rate = yutu2_average_rate_m_per_day()
    assert 0.0 < rate < 10.0


def test_pragyan_mission_declares_required_fields():
    for key in ("mission", "landing_date", "sleep_date", "total_distance_m", "source"):
        assert key in PRAGYAN_MISSION


def test_pragyan_active_days_matches_the_known_short_mission_window():
    assert pragyan_active_days() == 10


def test_pragyan_average_rate_is_positive_and_bounded():
    rate = pragyan_average_rate_m_per_day()
    assert 0.0 < rate < 50.0


def test_pragyan_sleep_date_is_after_landing_date():
    assert PRAGYAN_MISSION["sleep_date"] > PRAGYAN_MISSION["landing_date"]
