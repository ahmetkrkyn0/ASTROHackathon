"""The contract for pose estimates entering LunaPath.

``schemas.Corridor`` is what LunaPath publishes to a local planner;
``PoseEstimate`` is what a local planner sends back. They are a symmetric
pair, and this module is deliberately separate from ``schemas.py`` for
that reason: one file is the outbound contract, this one is the inbound.

LunaPath does not produce odometry. It consumes odometry produced by
somebody else's stack -- wheel encoders, visual odometry, a LiDAR
odometry node -- and checks it against the orbital DEM it already holds.
Nothing in this module estimates a pose; it only states what an estimate
must look like to be usable, and refuses the ones that are not.

Heading convention
------------------
``heading_deg`` is a GRID azimuth, matching ``app.horizon`` and
``make_aspect_grid``: 0 = decreasing row (grid North), 90 = increasing
column (grid East), increasing clockwise. This is NOT true-north
referenced. A consumer holding a true-north heading (a sun sensor, a
star tracker, anything celestial) must rotate it first with
``ephemeris.true_azimuth_to_grid_azimuth``; the two frames coincide only
on the projection's central meridian. Phase 2 shipped a bug from exactly
this confusion, so the convention is stated here, asserted in the tests,
and converted in exactly one place rather than inline at each call site.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Ordered loosely by how much a fix from that source can be trusted, but
# the ordering is not encoded anywhere -- callers must not infer quality
# from position. What matters is that the field is REQUIRED: a pose from
# dead reckoning and a pose from a skyline fix are not interchangeable,
# and a consumer that cannot tell them apart will treat drift as truth.
# This is the pose-side twin of Phase 1's layer_validity labelling.
PoseSource = Literal[
    "dead_reckoning",
    "visual_odometry",
    "lidar_odometry",
    "skyline_fix",
    "sun_sensor",
]

# Sources whose error does not grow with distance travelled, because they
# fix against an external absolute reference rather than integrating
# motion. localization_budget uses this to decide whether a source resets
# accumulated drift or merely slows it.
ABSOLUTE_SOURCES: frozenset[str] = frozenset({"skyline_fix", "sun_sensor"})


class PoseEstimate(BaseModel):
    """A pose estimate handed to LunaPath by a local navigation stack."""

    x_m: float = Field(description="Projected CRS easting, metres.")
    y_m: float = Field(description="Projected CRS northing, metres.")
    heading_deg: float = Field(
        description=(
            "Grid azimuth: 0 = grid North (decreasing row), 90 = grid East "
            "(increasing column), clockwise. Not true-north referenced."
        )
    )
    covariance_m: float = Field(
        ge=0.0, description="1-sigma horizontal position uncertainty, metres."
    )
    heading_covariance_deg: float = Field(
        ge=0.0, description="1-sigma heading uncertainty, degrees."
    )
    timestamp_utc: str = Field(description="UTC timestamp of the estimate.")
    source: PoseSource = Field(
        description=(
            "Which estimator produced this pose. Required: a dead-reckoned "
            "pose and an absolute fix carry different trust."
        )
    )
    distance_travelled_m: float = Field(
        ge=0.0,
        description=(
            "Distance the estimator CLAIMS to have covered -- odometry's own "
            "measurement, not the commanded distance. The difference between "
            "the two is slip (see app.slip_model)."
        ),
    )

    @field_validator("heading_deg")
    @classmethod
    def _wrap_heading(cls, value: float) -> float:
        """Normalise heading into [0, 360).

        Accepted rather than rejected: -90, 270 and 630 all name the same
        direction, and an odometry node emitting a wrapped or signed angle
        is not making an error. Normalising once here means every consumer
        downstream can compare headings arithmetically.
        """
        return float(value) % 360.0

    @field_validator("covariance_m", "heading_covariance_deg", "distance_travelled_m")
    @classmethod
    def _reject_non_finite(cls, value: float) -> float:
        """NaN and inf must not enter as uncertainty.

        ``ge=0.0`` does not stop NaN -- every comparison against NaN is
        False, so Pydantic's bound check passes it through. A NaN
        covariance then makes ``covariance_m > half_width_m`` False in
        check_localization_uncertainty, so a pose with unknown uncertainty
        reads as a confident one and the trigger silently fails open.
        That is the same fail-open shape backend review #4 found in
        evaluate_triggers, so it is closed here at the boundary.
        """
        value = float(value)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("must be a finite number")
        return value

    @field_validator("x_m", "y_m")
    @classmethod
    def _reject_non_finite_position(cls, value: float) -> float:
        value = float(value)
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError("must be a finite number")
        return value

    @property
    def is_absolute_fix(self) -> bool:
        """True when this source fixes against an external reference.

        Such a pose bounds accumulated drift instead of adding to it.
        """
        return self.source in ABSOLUTE_SOURCES
