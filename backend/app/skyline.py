"""Absolute position from the skyline, matched against the orbital DEM.

Every odometry source in ``pose.PoseSource`` except the absolute ones
accumulates error without bound: dead reckoning at roughly 10 percent of
distance travelled, visual odometry at 0.2 to 2.5 percent. Something has
to reset that, and on the Moon there is no GNSS and no magnetic field to
reset it against.

What LunaPath does have is ``horizon.horizon_map()``, which already
returns, for every cell and every azimuth bin, the elevation angle of the
horizon seen from that cell. That array is exactly the reference database
a skyline matcher needs. It was written in Phase 1 for shadow
computation, reused in Phase 5 for the virtual LiDAR, and matching
against it here is its third product from the same core.

LunaPath does not extract a skyline from an image -- that is a perception
problem and explicitly out of scope. This module takes an already
extracted horizon profile and answers "which cell does this look like".

What this is and is not
-----------------------
This is an INTERFACE AND FEASIBILITY DEMONSTRATION, not a localization
product. A horizon profile computed from a 5 m/px DEM is a low-pass
filtered version of what a camera actually sees: near-field topography
below the DEM's resolution is absent, and so is anything the ray-march's
``max_range_m`` did not reach. Matching real imagery against it would
need the observation filtered to the same band first.

The failure mode that matters is featureless terrain. On a flat plateau
every cell's horizon looks alike, and a matcher that returns the
best-scoring cell anyway would be reporting confident nonsense. So
``match_skyline`` always returns ``ambiguity_ratio``, and
``SkylineFix.is_confident`` is False when the runner-up scores nearly as
well as the winner. Silent wrong answers are the one outcome this module
is built to prevent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

# Below this margin between best and runner-up, the match is not
# trustworthy. 1.0 would mean the two are tied; the default demands the
# runner-up be at least 15 percent worse.
DEFAULT_AMBIGUITY_LIMIT: float = 0.85


@dataclass(frozen=True)
class SkylineFix:
    """The cell a horizon observation was matched to."""

    row: int
    col: int
    x_m: float
    y_m: float
    score: float
    ambiguity_ratio: float
    confident: bool

    @property
    def is_confident(self) -> bool:
        return self.confident

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def match_skyline(
    observed_horizon_deg: np.ndarray,
    horizon_cube: np.ndarray,
    metadata: dict[str, Any] | None = None,
    search_mask: np.ndarray | None = None,
    ambiguity_limit: float = DEFAULT_AMBIGUITY_LIMIT,
) -> SkylineFix | None:
    """Match an observed horizon profile against the DEM horizon cube.

    Parameters
    ----------
    observed_horizon_deg
        ``(n_azimuth,)`` horizon elevation angles, in the same azimuth
        binning and grid frame as ``horizon_map`` (bin 0 = grid North,
        increasing clockwise).
    horizon_cube
        ``(n_azimuth, H, W)`` from :func:`horizon.horizon_map`.
    metadata
        Grid metadata, used only to report the match in CRS metres. When
        omitted, ``x_m``/``y_m`` are NaN and the row/col are still valid.
    search_mask
        Optional ``(H, W)`` boolean array; only True cells are considered.
        Restricting the search to the corridor neighbourhood both speeds
        the match and removes far-away lookalike cells that would
        otherwise inflate the ambiguity ratio.
    ambiguity_limit
        Confidence cutoff. The fix is confident when the runner-up's
        score exceeds the winner's by more than this factor.

    Returns
    -------
    SkylineFix or None
        None when the search space is empty. A low-confidence match is
        still RETURNED, with ``confident=False`` -- the caller is told
        what the best guess was and that it cannot be relied on, rather
        than being handed silence.
    """
    observed = np.asarray(observed_horizon_deg, dtype=np.float64)
    cube = np.asarray(horizon_cube, dtype=np.float64)

    if cube.ndim != 3:
        raise ValueError(f"horizon_cube must be 3-D (n_azimuth, H, W), got {cube.shape}")
    if observed.ndim != 1:
        raise ValueError(f"observed_horizon_deg must be 1-D, got {observed.shape}")
    if observed.shape[0] != cube.shape[0]:
        raise ValueError(
            f"azimuth bin mismatch: observation has {observed.shape[0]} bins, "
            f"cube has {cube.shape[0]}"
        )

    n_azimuth, height, width = cube.shape

    # Occluded bearings (a mast, the lander, anything in frame) arrive as
    # NaN. A plain SSD propagates one NaN bin into every cell's score, the
    # NaN-to-inf mapping below then finds no finite candidate, and the
    # function returns None -- the value that means "empty search space".
    # A realistic partial observation was therefore unmatchable AND
    # indistinguishable from having nothing to search. Score on the valid
    # bins instead, normalised by how many there were so cells are still
    # comparable. (Round 2 review, L-9.)
    valid_bins = np.isfinite(observed)
    n_valid = int(np.count_nonzero(valid_bins))
    if n_valid == 0:
        raise ValueError(
            "observed_horizon_deg has no finite bins; nothing to match against"
        )

    residual = cube[valid_bins] - observed[valid_bins, None, None]
    scores = np.sum(residual * residual, axis=0) / n_valid

    if search_mask is not None:
        mask = np.asarray(search_mask, dtype=bool)
        if mask.shape != (height, width):
            raise ValueError(
                f"search_mask shape {mask.shape} does not match cube grid "
                f"{(height, width)}"
            )
        if not mask.any():
            return None
        scores = np.where(mask, scores, np.inf)

    # Cells whose horizon is unknown cannot be scored against.
    scores = np.where(np.isfinite(scores), scores, np.inf)
    if not np.isfinite(scores).any():
        return None

    flat_best = int(np.argmin(scores))
    best_row, best_col = divmod(flat_best, width)
    best_score = float(scores[best_row, best_col])

    ambiguity_ratio = _ambiguity_ratio(scores, best_row, best_col, best_score)

    x_m, y_m = _cell_to_metres(best_row, best_col, metadata)

    return SkylineFix(
        row=int(best_row),
        col=int(best_col),
        x_m=x_m,
        y_m=y_m,
        score=best_score,
        ambiguity_ratio=ambiguity_ratio,
        confident=bool(ambiguity_ratio < float(ambiguity_limit)),
    )


def _ambiguity_ratio(
    scores: np.ndarray, best_row: int, best_col: int, best_score: float
) -> float:
    """best / runner-up, where the runner-up excludes the winner's neighbours.

    Adjacent cells see almost the same horizon, so the literal
    second-best cell is nearly always the winner's neighbour and its
    score is nearly identical. Using it would report every match as
    ambiguous, including correct ones. The runner-up is therefore taken
    from outside a 3x3 block around the winner: the question being asked
    is "does somewhere ELSE on the map look like this too", not "does the
    cell next door look similar" (it does, and that is not a problem --
    it means the fix is right to within a pixel).

    Returns 1.0 when there is no runner-up to compare against, i.e. the
    most ambiguous possible answer, because a single candidate cannot
    distinguish itself from anything.
    """
    height, width = scores.shape
    others = scores.copy()
    r0, r1 = max(0, best_row - 1), min(height, best_row + 2)
    c0, c1 = max(0, best_col - 1), min(width, best_col + 2)
    others[r0:r1, c0:c1] = np.inf

    if not np.isfinite(others).any():
        return 1.0

    runner_up = float(np.min(others))
    if runner_up <= 0.0:
        # Another cell matches perfectly too: maximally ambiguous.
        return 1.0
    if not np.isfinite(runner_up):
        return 1.0
    return float(best_score / runner_up)


def _cell_to_metres(
    row: int, col: int, metadata: dict[str, Any] | None
) -> tuple[float, float]:
    if not metadata:
        return float("nan"), float("nan")
    try:
        from .grid_frame import pixel_to_map_xy

        return pixel_to_map_xy(int(row), int(col), metadata)
    except (KeyError, ValueError):
        # Metadata without usable geometry is not a match failure; report
        # the cell and leave the metres unknown rather than raising.
        return float("nan"), float("nan")


def expected_sun_angles(
    timestamp_utc: str,
    lat_deg: float,
    lon_deg: float,
    crs_wkt: str | None = None,
    meta_kernel: str | None = None,
) -> tuple[float, float]:
    """Sun azimuth and elevation LunaPath expects at a time and place.

    This is the ground-truth side of a sun-sensor fix. The Moon has no
    global magnetic field, so a compass heading is not available; absolute
    orientation has to come from a celestial reference, and the Sun is the
    one every flown lunar rover concept uses (MoonRanger's sun compass,
    for instance). Comparing a sun sensor's measured bearing against this
    expected bearing yields absolute heading.

    The azimuth is returned in the GRID frame when *crs_wkt* is given,
    matching ``pose.PoseEstimate.heading_deg`` and ``horizon``'s bins. If
    *crs_wkt* is omitted the azimuth stays true-north referenced -- which
    is a DIFFERENT number, and mixing the two is the Phase 2 bug this
    codebase already paid for once.

    LunaPath does not read a sun sensor. This function only says what one
    ought to read.
    """
    from .ephemeris import (
        DEFAULT_META_KERNEL,
        _ensure_kernels,
        sun_azel_from_vector,
        sun_vector_body,
        true_azimuth_to_grid_azimuth,
        true_north_grid_azimuth,
    )

    try:
        import spiceypy as spice
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "spiceypy is required for ephemeris queries. "
            "Install it and run lunapath/src/fetch_kernels.py first."
        ) from exc

    kernel = meta_kernel or DEFAULT_META_KERNEL
    # furnsh before str2et: converting a UTC string needs the leapsecond
    # kernel loaded, so the order matters on a cold SPICE pool. sun_track
    # does the same for the same reason.
    _ensure_kernels(spice, kernel)
    et = spice.str2et(timestamp_utc)
    sun_vec = sun_vector_body(et, kernel)
    true_az_deg, elevation_deg = sun_azel_from_vector(sun_vec, lat_deg, lon_deg)

    if crs_wkt is None:
        return float(true_az_deg), float(elevation_deg)

    north_grid_az = true_north_grid_azimuth(lat_deg, lon_deg, crs_wkt)
    grid_az = true_azimuth_to_grid_azimuth(true_az_deg, north_grid_az)
    return float(grid_az), float(elevation_deg)
