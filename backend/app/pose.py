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

Distance epoch
--------------
``distance_travelled_m`` is counted from the start of the corridor the
pose is being judged against, and resets on every new plan. The slip
check divides advance along that corridor by this claim, so cumulative
since-boot odometry against a freshly replanned corridor reads as near
zero progress over a large claim and fires slip in a loop. The ROS
monitor enforces the reset itself (a new corridor zeroes its integral);
HTTP callers must do the same. (Round 2 review, M-6.)

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

import math
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

# Sources whose ``distance_travelled_m`` is a WHEEL measurement, and whose
# divergence from ground actually gained is therefore slip.
#
# Visual and LiDAR odometry estimate body motion from the world, so they
# have already corrected for slip: the wheels turning further than the rover
# advanced does not appear in their distance at all. Comparing their claim
# against along-track progress measures how much the rover WEAVED inside its
# corridor -- ordinary obstacle avoidance -- and a rover taking 33 percent
# extra path length would trip a trigger named "slip" while slipping not at
# all. The ROS monitor makes this concrete: it integrates the distance from
# the very pose stream it then projects, so both sides of the ratio come
# from one estimator and genuine wheel slip is invisible by construction.
# (Round 3 review, M-4.)
SLIP_CHECKABLE_SOURCES: frozenset[str] = frozenset({"dead_reckoning"})


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
            "Distance the estimator CLAIMS to have covered, measured FROM "
            "THE START OF THE ACTIVE CORRIDOR -- reset it whenever a new "
            "plan is issued. Odometry's own measurement, not a commanded "
            "distance; the gap between it and actual advance along the "
            "corridor is slip (see app.slip_model)."
        ),
    )

    @field_validator("heading_deg")
    @classmethod
    def _wrap_heading(cls, value: float) -> float:
        """Normalise heading into [0, 360).

        Wrapping is accepted rather than rejected: -90, 270 and 630 all
        name the same direction, and an odometry node emitting a wrapped
        or signed angle is not making an error. Normalising once here
        means every consumer downstream can compare headings
        arithmetically.

        Non-finite values are rejected first. ``nan % 360`` is nan and
        ``inf % 360`` is also nan, so without this check a non-finite
        heading was accepted and stored as NaN -- inside the one module
        that promises NaN is stopped at the boundary. Nothing consumes
        heading yet, so it would have slept in a "validated" object until
        the first consumer inherited a silent fail-open.
        (Round 2 review, M-3.)
        """
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value % 360.0

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
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    @field_validator("x_m", "y_m")
    @classmethod
    def _reject_non_finite_position(cls, value: float) -> float:
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    @property
    def is_absolute_fix(self) -> bool:
        """True when this source fixes against an external reference.

        Such a pose bounds accumulated drift instead of adding to it.
        """
        return self.source in ABSOLUTE_SOURCES


def quaternion_to_grid_heading_deg(
    qx: float, qy: float, qz: float, qw: float
) -> float:
    """ROS orientation quaternion -> grid heading in degrees.

    This is the single place the two conventions meet, kept in the
    backend so it is pytest-tested without a ROS installation
    (``lunapath_ros.conversions`` wraps it, following the grid_frame
    pattern).

    ROS REP-103: yaw is measured counter-clockwise from +x, and in the
    map frame +x is East, +y is North. Grid heading (this module's
    convention, above): 0 = grid North, clockwise positive. Both frames
    have +y as north as long as the map frame is aligned with the
    projected CRS -- which is how grid_frame.pixel_to_map_xy defines it --
    so the conversion is the standard compass identity
    ``heading = 90 - yaw``.

    An unnormalised quaternion is accepted. The denominator is written as
    ``qw^2 + qx^2 - qy^2 - qz^2`` rather than the textbook
    ``1 - 2(qy^2 + qz^2)``: the two are equal only at unit norm, and the
    first form scales with |q|^2 exactly as the numerator does, so atan2
    cancels the norm and a publisher whose normalisation drifted still
    yields the right heading.
    """
    yaw_rad = math.atan2(
        2.0 * (qw * qz + qx * qy),
        qw * qw + qx * qx - qy * qy - qz * qz,
    )
    return (90.0 - math.degrees(yaw_rad)) % 360.0
