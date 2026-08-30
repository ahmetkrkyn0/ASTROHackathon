"""PoseEstimate contract tests.

The heading-convention tests are the important ones: Phase 2 shipped a
bug from confusing grid azimuth with true azimuth, and the Phase 7 plan
flags a repeat as its highest risk. They assert the convention against
ephemeris.py's converters rather than restating it, so a change to the
canonical frame breaks these tests instead of silently disagreeing.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ephemeris import grid_azimuth_to_true_azimuth, true_azimuth_to_grid_azimuth
from app.pose import ABSOLUTE_SOURCES, PoseEstimate


def _pose(**overrides) -> PoseEstimate:
    base = {
        "x_m": 1000.0,
        "y_m": 2000.0,
        "heading_deg": 90.0,
        "covariance_m": 3.0,
        "heading_covariance_deg": 2.0,
        "timestamp_utc": "2026-08-30T12:00:00Z",
        "source": "visual_odometry",
        "distance_travelled_m": 120.0,
    }
    base.update(overrides)
    return PoseEstimate(**base)


def test_a_well_formed_pose_is_accepted():
    pose = _pose()
    assert pose.x_m == 1000.0
    assert pose.source == "visual_odometry"


def test_source_is_required():
    with pytest.raises(ValidationError):
        PoseEstimate(
            x_m=0.0,
            y_m=0.0,
            heading_deg=0.0,
            covariance_m=1.0,
            heading_covariance_deg=1.0,
            timestamp_utc="2026-08-30T12:00:00Z",
            distance_travelled_m=0.0,
        )


def test_an_unknown_source_is_rejected():
    with pytest.raises(ValidationError):
        _pose(source="magnetic_compass")


def test_a_magnetic_compass_is_not_a_valid_source():
    """Not a style point: the Moon has no global magnetic field, so a
    compass heading is not a thing a lunar rover can produce."""
    with pytest.raises(ValidationError):
        _pose(source="compass")


@pytest.mark.parametrize("field", ["covariance_m", "heading_covariance_deg"])
def test_negative_uncertainty_is_rejected(field):
    with pytest.raises(ValidationError):
        _pose(**{field: -1.0})


def test_negative_distance_travelled_is_rejected():
    with pytest.raises(ValidationError):
        _pose(distance_travelled_m=-5.0)


@pytest.mark.parametrize("field", ["covariance_m", "heading_covariance_deg"])
def test_nan_uncertainty_is_rejected(field):
    """A NaN covariance passes a >= 0 bound (every NaN comparison is
    False) and then reads as certainty in check_localization_uncertainty,
    which fails open. It must not get past the boundary."""
    with pytest.raises(ValidationError):
        _pose(**{field: float("nan")})


@pytest.mark.parametrize("field", ["covariance_m", "x_m", "y_m"])
def test_infinite_values_are_rejected(field):
    with pytest.raises(ValidationError):
        _pose(**{field: float("inf")})


@pytest.mark.parametrize(
    "given,expected",
    [(-90.0, 270.0), (450.0, 90.0), (360.0, 0.0), (0.0, 0.0), (359.9, 359.9)],
)
def test_heading_is_normalised_into_zero_to_360(given, expected):
    assert _pose(heading_deg=given).heading_deg == pytest.approx(expected)


def test_heading_uses_the_grid_convention_not_true_north():
    """A pose heading is a GRID azimuth. Round-tripping it through
    ephemeris.py's converters must return the same angle -- that is what
    makes the two frames explicitly distinct rather than assumed equal."""
    true_north_grid_az = 12.5  # a CRS where grid and true north disagree
    grid_heading = _pose(heading_deg=90.0).heading_deg
    as_true = grid_azimuth_to_true_azimuth(grid_heading, true_north_grid_az)
    back_to_grid = true_azimuth_to_grid_azimuth(as_true, true_north_grid_az)
    assert back_to_grid == pytest.approx(grid_heading)
    # And the two frames are genuinely different, so the test is not vacuous.
    assert as_true != pytest.approx(grid_heading)


def test_absolute_sources_are_flagged_and_relative_ones_are_not():
    assert _pose(source="skyline_fix").is_absolute_fix
    assert _pose(source="sun_sensor").is_absolute_fix
    assert not _pose(source="dead_reckoning").is_absolute_fix
    assert not _pose(source="visual_odometry").is_absolute_fix
    assert not _pose(source="lidar_odometry").is_absolute_fix


def test_absolute_sources_set_is_a_subset_of_the_declared_sources():
    """Guards against a source being renamed in the Literal but left
    behind in ABSOLUTE_SOURCES, where it would silently never match."""
    declared = set(PoseEstimate.model_fields["source"].annotation.__args__)
    assert ABSOLUTE_SOURCES <= declared


def test_zero_uncertainty_is_allowed():
    """0 is a legitimate (if optimistic) covariance; only negatives and
    non-finite values are contract violations."""
    assert _pose(covariance_m=0.0).covariance_m == 0.0
