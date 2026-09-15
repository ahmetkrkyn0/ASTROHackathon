"""The solar array's incidence angle and panel geometry (C1).

LunaPath's solar income has always been one product: ``p_solar_w * (1 -
shadow_ratio)``. That says the array collects its full rated power wherever
the Sun is above the local horizon, no matter where the Sun actually is --
which is the same as saying the array is always face-on to it.

The assumption is not hidden; the literature this planner is built on states
it outright. Otten, Jones, Wettergreen and Whittaker (ICRA 2015), whose
connected-component corridor is LunaPath's A2, set their illumination
threshold to zero and justify it so:

    "This assumes that any positive amount of solar illumination is adequate
    to fully power the rover, which is true for rover configurations with
    two-degree-of-freedom articulated solar arrays that can always point
    directly at the sun (provided the array is appropriately sized)."

Lamarre, Malhotra and Kelly (IEEE AERO 2024), whose reach-avoid formulation
is LunaPath's B1, assume "a constant area of solar panels perfectly oriented
towards the Sun at all times, mimicking panels mounted on a pan-tilt
platform", and close with "We keep the incorporation of more complex power
generation models as future work."

LunaPath's own default rover has no such array. The ``lpr_1`` profile's
410 W is NASA's VIPER Proposal Information Package's, which describes the
hardware as "three approximate 1 m2 solar arrays (one each on the port,
starboard, and aft surfaces)"; its 5 420 Wh is Bluethmann's ("Battery
capacity (start of life @ 0C): 5,420 W-hr"), NOT the PIP's -- that document
carries no battery figure at all. VIPER's gimbals are on the high-gain
antenna and the navigation cameras, not on the arrays.

This module supplies the missing geometry, following RoverDevKit (arXiv
2606.21755, Duke University) section 3.4:

    cos i = sin e cos(beta) + cos e sin(beta) cos(alpha_sun - psi)
    P_solar = S_0 * A_s * eta_s * d_s * max(0, cos i)

with one correction the catalogue forces. ``p_solar_w`` is NOT a flat-plate
nameplate: 410 W is the PIP's three-array TOTAL and 450 W is NASA's
"450W on corner" peak (Bluethmann, LSIC 2024: "Solar arrays: 320W per panel
(450W on corner)"). Multiplying either by a single-plate ``max(0, cos i)``
would apply the geometry twice. So the gain here is a NORMALISED sum over
the array's faces,

    g = sum_k w_k max(0, cos i_k) / raw_ref

where ``raw_ref`` is the same sum maximised over panel azimuth and Sun
elevation -- the array's own best geometry, which is what a published peak
power describes. For a single flat plate ``raw_ref`` is 1 and ``g`` reduces
exactly to ``max(0, cos i)``, the expression the research note asked for.

Claim limits, restated in :data:`PANEL_CLAIM` and carried on every response:

* MODEL. No rover publishes a panel measurement in polar regolith. This is
  geometry only -- no cell efficiency, no array area, no dust loss, no
  temperature coefficient, no albedo or terrain-reflected light.
* The catalogue's panel geometry is an ASSUMPTION for every profile; each
  carries a ``panel_geometry_source`` beginning with "assumption:".
* ``g = 1`` (``panel_model="sun_pointed"``) is NOT RoverDevKit's default --
  that paper's default array is horizontal. ``g = 1`` is Otten's and
  Lamarre's sun-pointed array, i.e. exactly what LunaPath does today, and
  it is the default here so that every existing number stays bit-identical.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

# ── identity, claim, references, quotations ─────────────────────────────────

PANEL_MODEL_ID: str = "multi_face_cos_incidence_v1"
PANEL_VALIDITY: str = "MODEL"

#: How the solar income is computed. ``sun_pointed``: the array is treated as
#: always face-on to the Sun (the pre-C1 model, Otten's 2-DOF assumption);
#: ``cos_incidence``: the catalogue's panel geometry against the SPICE Sun
#: track. The default is ``sun_pointed`` because it is bit-for-bit today.
PANEL_MODELS: tuple[str, ...] = ("sun_pointed", "cos_incidence")

#: How the array's reference azimuth is chosen at each slice.
#: ``sun_tracking`` -- the array points at the Sun in azimuth (an articulated
#: or pan-tilt array; psi = alpha_sun).
#: ``free_heading`` -- the rover turns the whole body to the azimuth that
#: maximises the sum over faces. NASA lists exactly this as a VIPER driving
#: mode: "Omni-directional driving with sun on corner / Maximizing power
#: generation".
#: ``fixed`` -- a declared true-north azimuth that never changes.
#: ``heading_locked`` -- psi is the rover's heading, supplied per sample.
#: Reporting only: the 4-D cost cube is per cell, not per direction, so the
#: planner never prices a heading-dependent gain.
AZIMUTH_MODES: tuple[str, ...] = (
    "sun_tracking",
    "free_heading",
    "fixed",
    "heading_locked",
)

#: How the array's tilt is chosen. ``fixed`` -- each face keeps its declared
#: tilt (every real body-mounted array, and a deployable panel set once).
#: ``sun_tracking`` -- the face normal follows the Sun in elevation as well,
#: which together with ``azimuth_mode="sun_tracking"`` is the two-degree-of-
#: freedom array Otten and Lamarre assume and therefore reproduces LunaPath's
#: pre-C1 income exactly (cos i == 1 whenever the Sun is up). Only meaningful
#: for a single face.
TILT_MODES: tuple[str, ...] = ("fixed", "sun_tracking")

#: RoverDevKit's polar convention. The paper's words: "The default array is
#: horizontal; high-latitude runs can pass a fixed tilt, typically
#: min(80 deg, |lambda|), to represent a deployable panel aligned with the
#: low-elevation polar sun." A convention that may be passed in, not a law.
POLAR_TILT_CAP_DEG: float = 80.0

PANEL_SCOPE: str = (
    "geometry only: g = sum_k area_k * max(0, cos i_k) / raw_ref, with "
    "cos i = sin e cos(beta) + cos e sin(beta) cos(alpha_sun - psi) per face and raw_ref "
    "the same sum maximised over panel azimuth and Sun elevation; e and alpha_sun are the "
    "SPICE Sun elevation and true-north azimuth at the window centre, one pair per time "
    "slice; the illuminated fraction (1 - shadow_ratio) plays RoverDevKit's d_s and is "
    "unchanged; g = 0 whenever the Sun is at or below the horizon."
)

PANEL_CLAIM: str = (
    "MODEL, uncalibrated: a geometric factor only. No cell efficiency, array area, dust "
    "loss, temperature coefficient, albedo or terrain-reflected light is modelled, and no "
    "rover publishes a panel measurement in polar regolith. p_solar_w is read as the "
    "array's output in its BEST geometry -- NASA publishes VIPER's as '320W per panel "
    "(450W on corner)' and the PIP's 410 W as a three-array total -- so the gain is "
    "normalised to that best geometry and never multiplies a published peak by a "
    "single-plate cosine. Every profile's panel geometry is an ASSUMPTION carrying a "
    "source string that starts with 'assumption:'; the tilt of VIPER's arrays is inferred "
    "from NASA's 'port, starboard, and aft surfaces' plus 'Radiators (on top)', and NASA "
    "never calls them vertical. g = 1 (panel_model='sun_pointed') is the pre-C1 model, "
    "which is Otten's and Lamarre's sun-pointed array -- NOT RoverDevKit's default, which "
    "is a horizontal array. RoverDevKit's own Pragyan validation is THEIR result and is "
    "quoted, never mixed with a LunaPath measurement. FINALLY, AND THIS IS THE LARGEST "
    "REMAINING OPTIMISM: a body-mounted array is catalogued with azimuth_mode "
    "'free_heading', so the applied gain is the maximum over body heading -- the rover is "
    "assumed free to turn to the best one, which is NASA's own driving mode but is not "
    "what a rover does while driving somewhere. On Site11's daytime route the same array "
    "locked to its direction of travel collects 0.305 against 0.9996 free to turn, a "
    "factor of 3.3, and the near-no-op result this model reports for the catalogue's "
    "geometries is an artefact of that assumption rather than a property of the site. The "
    "heading-locked counterfactual is measured in the report; the planner does not price "
    "it, because its cost cube is per cell and not per direction."
)

PANEL_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "roverdevkit_2026",
        "title": (
            "Jon Reifschneider (Duke University) -- RoverDevKit: a design and simulation "
            "toolkit for planetary rovers (arXiv 2606.21755, 2026); code archived at "
            "Zenodo 10.5281/zenodo.20754999"
        ),
        "url": "https://arxiv.org/abs/2606.21755",
        "used_for": (
            "section 3.4 eq (16) cos i = sin e cos(beta) + cos e sin(beta) "
            "cos(alpha_sun - psi) and eq (17) P_solar = S_0 A_s eta_s d_s max(0, cos i); "
            "the polar tilt convention min(80 deg, |lambda|)"
        ),
    },
    {
        "id": "viper_pip_2021",
        "title": "VIPER Proposal Information Package (Colaprete et al., NTRS 20210015009)",
        "url": "https://ntrs.nasa.gov/citations/20210015009",
        "used_for": (
            "page 8: 'three approximate 1 m2 solar arrays (one each on the port, "
            "starboard, and aft surfaces), generating 410 (TBR) W of total power' -- the "
            "array geometry, and the origin of this catalogue's 410 W. NOT the source of "
            "the 5 420 Wh: this document carries no battery figure (checked against NASA's "
            "own fulltext); that number is Bluethmann's, below"
        ),
    },
    {
        "id": "bluethmann_lsic_2024",
        "title": (
            "Bill Bluethmann -- VIPER Rover Overview and Mobility and Hardware "
            "(LSIC Tech Infusion, 14 November 2024, NTRS 20240013903)"
        ),
        "url": "https://ntrs.nasa.gov/citations/20240013903",
        "used_for": (
            "slide 2 'Solar arrays: 320W per panel (450W on corner)' and 'Battery "
            "capacity (start of life @ 0C): 5,420 W-hr' (the real source of this "
            "catalogue's 5 420 Wh); slide 3 'Solar Array (3-sides)' and 'Radiators (on "
            "top)'; slide 5 'Omni-directional driving with sun on corner / Maximizing "
            "power generation'; slide 7 gimbals on the high-gain antenna and navigation "
            "cameras only"
        ),
    },
    {
        "id": "otten_icra_2015",
        "title": (
            "Otten, Jones, Wettergreen, Whittaker -- Planning Routes of Continuous "
            "Illumination and Traversable Slope using Connected Component Analysis "
            "(ICRA 2015)"
        ),
        "url": "https://publications.ri.cmu.edu/resolve/2018/01/ICRA2015_Otten_3109.pdf",
        "used_for": (
            "the sourced statement of what a zero illumination threshold assumes: "
            "'two-degree-of-freedom articulated solar arrays that can always point "
            "directly at the sun'"
        ),
    },
    {
        "id": "lamarre_aero_2024",
        "title": (
            "Lamarre, Malhotra, Kelly -- Safe Mission-Level Path Planning for Exploration "
            "of Lunar Shadowed Regions by a Solar-Powered Rover (IEEE AERO 2024)"
        ),
        "url": "https://arxiv.org/abs/2401.08558",
        "used_for": (
            "'panels perfectly oriented towards the Sun at all times' and 'We keep the "
            "incorporation of more complex power generation models as future work' -- the "
            "same gap in B1's own source"
        ),
    },
)

#: NASA's published VIPER power numbers, kept as QUOTATIONS. They are the
#: input to :func:`viper_corner_check`, which is OUR arithmetic on THEIR two
#: numbers -- not a NASA validation of this model.
VIPER_QUOTED: dict[str, Any] = {
    "per_panel_w": 320.0,
    "on_corner_w": 450.0,
    "quote": "Solar arrays: 320W per panel (450W on corner)",
    "source": "Bluethmann, LSIC Tech Infusion, 14 November 2024 (NTRS 20240013903), slide 2",
    "array_quote": (
        "three approximate 1 m2 solar arrays (one each on the port, starboard, and aft "
        "surfaces), generating 410 (TBR) W of total power"
    ),
    "array_source": "VIPER Proposal Information Package (NTRS 20210015009), page 8",
    "battery_quote": "Battery capacity (start of life @ 0C): 5,420 W-hr",
    "battery_source": "Bluethmann (NTRS 20240013903), slide 2 -- NOT the PIP, which has no battery figure",
    "driving_mode_quote": (
        "Omni-directional driving with sun on corner / Maximizing power generation"
    ),
    "driving_mode_source": "Bluethmann (NTRS 20240013903), slide 5",
}

#: RoverDevKit's own validation. THEIRS, quoted in the paper's words -- the
#: arithmetic is not restated (the paper writes +5% where 52/50 is +4%).
ROVERDEVKIT_QUOTED: dict[str, str] = {
    "peak_power": (
        "The fresh-array rover Pragyan (one lunar day of operation, hence a "
        "near-beginning-of-life peak) is predicted at 52 W against a published 50 W band "
        "of 40-70 W - a +5% error that stays in-band across the entire cell-efficiency "
        "range (0.28-0.32, giving 49-56 W)."
    ),
    "mass_model": (
        "Across the in-class rovers the model predicts total mass to a median absolute "
        "error of 13.3 % (mean 14.8 %)."
    ),
    "default_array": (
        "The default array is horizontal; high-latitude runs can pass a fixed tilt, "
        "typically min(80 deg, |lambda|), to represent a deployable panel aligned with "
        "the low-elevation polar sun."
    ),
    "scope": (
        "The model captures the latitude-driven sun-angle penalty but does not account "
        "for terrain horizon masking or site shadowing."
    ),
    "note": (
        "RoverDevKit's results, quoted. They are not a LunaPath measurement and never "
        "appear in the same table as one."
    ),
}


# ── geometry ────────────────────────────────────────────────────────────────


def polar_tilt_deg(lat_deg: float) -> float:
    """RoverDevKit's polar tilt convention: ``min(80 deg, |latitude|)``.

    The paper's symbol is lambda (latitude), and the rule is offered as a
    typical value a high-latitude run may pass in, not as a law. Site11's
    window centre is -88.92 deg, so this returns 80.0 there.
    """
    return float(min(POLAR_TILT_CAP_DEG, abs(float(lat_deg))))


def cos_incidence(
    elevation_deg: float,
    azimuth_deg: float,
    tilt_deg: float,
    panel_azimuth_deg: float,
) -> float:
    """RoverDevKit eq (16), unclamped.

    ``tilt_deg`` is the angle of the face normal from the local vertical:
    0 is a horizontal, up-facing plate (for which this reduces to
    ``sin(elevation)``) and 90 is a vertical, side-facing one.

    Both azimuths must be in the SAME frame; only their difference is used,
    so the frame cancels. LunaPath carries two frames that differ by the
    meridian convergence (true north and grid north, see
    :func:`app.ephemeris.true_azimuth_to_grid_azimuth`), and at this site
    that difference is not a rounding error -- so callers pass the true-north
    pair, which is what ``sun_track_for_series`` publishes as
    ``azimuth_true_deg``.
    """
    e = math.radians(float(elevation_deg))
    b = math.radians(float(tilt_deg))
    d = math.radians(float(azimuth_deg) - float(panel_azimuth_deg))
    return math.sin(e) * math.cos(b) + math.cos(e) * math.sin(b) * math.cos(d)


@dataclass(frozen=True)
class PanelFace:
    """One planar face of the array.

    *tilt_deg* from the local vertical, *azimuth_offset_deg* from the array's
    reference azimuth (for a body-mounted array, from the rover's heading:
    VIPER's port/starboard/aft are +90, -90 and 180). *area_weight* is a
    relative area, so a face twice the size of another counts twice; it is
    relative only, because the gain is normalised.
    """

    tilt_deg: float
    azimuth_offset_deg: float
    area_weight: float = 1.0


@dataclass(frozen=True)
class PanelArray:
    """An array of faces plus how its reference azimuth is chosen.

    ``kind`` and ``source`` follow C3's anchor convention: a geometry with no
    published specification carries ``kind="assumption"`` and a source string
    that starts with ``"assumption:"``.
    """

    faces: tuple[PanelFace, ...]
    azimuth_mode: str
    azimuth_deg: float | None
    kind: str
    source: str
    tilt_mode: str = "fixed"

    def __post_init__(self) -> None:
        if not self.faces:
            raise ValueError("a panel array needs at least one face")
        if self.azimuth_mode not in AZIMUTH_MODES:
            raise ValueError(
                f"azimuth_mode must be one of {AZIMUTH_MODES}, got {self.azimuth_mode!r}"
            )
        if self.tilt_mode not in TILT_MODES:
            raise ValueError(
                f"tilt_mode must be one of {TILT_MODES}, got {self.tilt_mode!r}"
            )
        if self.tilt_mode == "sun_tracking" and len(self.faces) != 1:
            raise ValueError(
                "tilt_mode='sun_tracking' is a two-axis array and is only defined "
                "for a single face"
            )
        if self.azimuth_mode == "fixed" and self.azimuth_deg is None:
            raise ValueError("azimuth_mode='fixed' needs an azimuth_deg")
        for face in self.faces:
            if not 0.0 <= float(face.tilt_deg) <= 90.0:
                raise ValueError(
                    f"face tilt must be in [0, 90] degrees, got {face.tilt_deg}"
                )
            if float(face.area_weight) <= 0.0:
                raise ValueError("face area_weight must be positive")

    @property
    def n_faces(self) -> int:
        return len(self.faces)

    def raw(self, elevation_deg: float, azimuth_deg: float, reference_azimuth_deg: float) -> float:
        """``sum_k area_k * max(0, cos i_k)`` -- unnormalised, unclamped by elevation.

        Under ``tilt_mode="sun_tracking"`` the single face's normal is raised
        to the Sun's own elevation, so the tilt is ``90 - e`` rather than the
        declared one.
        """
        total = 0.0
        for face in self.faces:
            tilt = (
                90.0 - float(elevation_deg)
                if self.tilt_mode == "sun_tracking"
                else float(face.tilt_deg)
            )
            ci = cos_incidence(
                elevation_deg,
                azimuth_deg,
                tilt,
                float(reference_azimuth_deg) + float(face.azimuth_offset_deg),
            )
            if ci > 0.0:
                total += float(face.area_weight) * ci
        return total

    def reference_raw(self) -> float:
        """The array's own best :meth:`raw`, over reference azimuth AND Sun elevation.

        This is the geometry a published peak power describes, so dividing by
        it turns ``p_solar_w`` into "power at the best geometry" and makes
        ``g <= 1``. For a single flat plate it is exactly 1.0, so
        :func:`panel_gain` reduces to ``max(0, cos i)``; for VIPER's three
        vertical faces it is sqrt(2), the Sun on a corner between two of them.
        """
        return _reference_raw(self)

    def as_dict(self) -> dict[str, Any]:
        return {
            "faces": [
                {
                    "tilt_deg": float(f.tilt_deg),
                    "azimuth_offset_deg": float(f.azimuth_offset_deg),
                    "area_weight": float(f.area_weight),
                }
                for f in self.faces
            ],
            "n_faces": self.n_faces,
            "azimuth_mode": self.azimuth_mode,
            "tilt_mode": self.tilt_mode,
            "azimuth_deg": None if self.azimuth_deg is None else float(self.azimuth_deg),
            "reference_raw": float(self.reference_raw()),
            "kind": self.kind,
            "source": self.source,
        }


# The reference and the free-heading optimum are 1-D maximisations of a
# smooth, piecewise-sinusoidal function. A three-pass refining scan is exact
# to well under a microdegree and, unlike a solver, is deterministic and
# dependency-free -- which matters because these numbers are published. The
# scan is vectorised over the grid: a per-slice free-heading gain is
# evaluated once per plan slice, and a Python loop over 2 163 points made
# that the slowest thing in the module.
_SCAN_PASSES: int = 3
_SCAN_POINTS: int = 720


def _raw_over(
    array: "PanelArray", elevation_deg: float, azimuth_deg: float, psi: np.ndarray
) -> np.ndarray:
    """:meth:`PanelArray.raw` evaluated over a whole grid of reference azimuths."""
    e = math.radians(float(elevation_deg))
    sin_e, cos_e = math.sin(e), math.cos(e)
    total = np.zeros_like(psi)
    for face in array.faces:
        tilt = (
            90.0 - float(elevation_deg)
            if array.tilt_mode == "sun_tracking"
            else float(face.tilt_deg)
        )
        b = math.radians(tilt)
        delta = np.radians(
            float(azimuth_deg) - (psi + float(face.azimuth_offset_deg))
        )
        ci = sin_e * math.cos(b) + cos_e * math.sin(b) * np.cos(delta)
        total += float(face.area_weight) * np.maximum(0.0, ci)
    return total


def _scan_max_vec(fn, low: float, high: float) -> tuple[float, float]:
    """Maximise *fn* (an ndarray -> ndarray map) on [low, high] by a refining
    scan. Returns (arg, value)."""
    best_x, best_y = low, float(fn(np.array([low]))[0])
    for _ in range(_SCAN_PASSES):
        grid = np.linspace(low, high, _SCAN_POINTS + 1)
        values = fn(grid)
        index = int(np.argmax(values))
        if float(values[index]) > best_y:
            best_x, best_y = float(grid[index]), float(values[index])
        step = (high - low) / _SCAN_POINTS
        low, high = best_x - step, best_x + step
    return best_x, best_y


_REFERENCE_CACHE: dict[tuple, float] = {}


def _reference_raw(array: PanelArray) -> float:
    key = (
        tuple((f.tilt_deg, f.azimuth_offset_deg, f.area_weight) for f in array.faces),
        array.tilt_mode,
    )
    cached = _REFERENCE_CACHE.get(key)
    if cached is not None:
        return cached
    # The Sun azimuth is arbitrary here: the raw sum depends on
    # (azimuth - reference), so fixing the Sun at 0 and scanning the
    # reference covers every relative geometry.
    def at_elevation(elevations: np.ndarray) -> np.ndarray:
        return np.array(
            [
                _scan_max_vec(
                    lambda psi, e=float(elev): _raw_over(array, e, 0.0, psi), 0.0, 360.0
                )[1]
                for elev in elevations
            ]
        )

    value = _scan_max_vec(at_elevation, 0.0, 90.0)[1]
    if not (value > 0.0):  # pragma: no cover - defensive; __post_init__ forbids it
        raise ValueError("panel array has no positive reference gain")
    _REFERENCE_CACHE[key] = float(value)
    return float(value)


def best_reference_azimuth(
    elevation_deg: float, azimuth_deg: float, array: PanelArray
) -> tuple[float, float]:
    """The reference azimuth that maximises :meth:`PanelArray.raw`, and that raw value.

    For a body-mounted array this is the rover heading NASA's "sun on corner"
    driving mode seeks.
    """
    psi, value = _scan_max_vec(
        lambda p: _raw_over(array, elevation_deg, azimuth_deg, p), 0.0, 360.0
    )
    return float(psi % 360.0), float(value)


def reference_azimuth_for(
    elevation_deg: float,
    azimuth_deg: float,
    array: PanelArray,
    heading_deg: float | None = None,
) -> float:
    """The reference azimuth this array uses at this instant, by its mode."""
    mode = array.azimuth_mode
    if mode == "sun_tracking":
        return float(azimuth_deg)
    if mode == "free_heading":
        return best_reference_azimuth(elevation_deg, azimuth_deg, array)[0]
    if mode == "fixed":
        return float(array.azimuth_deg or 0.0)
    if heading_deg is None:
        raise ValueError("azimuth_mode='heading_locked' needs a heading_deg")
    return float(heading_deg)


def panel_gain(
    elevation_deg: float,
    azimuth_deg: float,
    array: PanelArray,
    heading_deg: float | None = None,
) -> float:
    """The normalised gain g in [0, 1] that multiplies ``p_solar_w``.

    Zero whenever the Sun is at or below the horizon. The cosine alone does
    not give that: a tilted face has a positive ``cos i`` for a Sun a degree
    BELOW the horizon, which is not light the rover can collect. The
    illumination series already returns ``illum_frac = 0`` there, but it does
    not on the static/degraded path, so the clamp is explicit here.
    """
    if float(elevation_deg) <= 0.0:
        return 0.0
    psi = reference_azimuth_for(elevation_deg, azimuth_deg, array, heading_deg)
    raw = array.raw(elevation_deg, azimuth_deg, psi)
    gain = raw / array.reference_raw()
    return float(min(1.0, max(0.0, gain)))


def gain_series(
    sun_track: Sequence[Mapping[str, Any]],
    array: PanelArray,
    headings_deg: Sequence[float] | None = None,
) -> np.ndarray:
    """``g`` for each slice of a Sun track, as a (T,) float64 array.

    *sun_track* is what :func:`app.illumination_series.sun_track_for_series`
    returns: the TRUE-north azimuth is used, so a ``fixed`` panel azimuth is
    also true-north referenced.

    The gain is site-wide per slice. The window is 2.5 km across and the Sun's
    azimuth and elevation do not vary meaningfully over it -- the same
    approximation ``_spice_shadow_series`` already makes when it takes one
    (azimuth, elevation) pair at the window centre per slice.
    """
    if headings_deg is not None and len(headings_deg) != len(sun_track):
        raise ValueError("headings_deg must be the same length as sun_track")
    out = np.empty(len(sun_track), dtype=np.float64)
    for i, sample in enumerate(sun_track):
        heading = None if headings_deg is None else float(headings_deg[i])
        out[i] = panel_gain(
            float(sample["elevation_deg"]),
            float(sample["azimuth_true_deg"]),
            array,
            heading,
        )
    return out


# ── the catalogue ───────────────────────────────────────────────────────────


def array_for_rover(rover: Mapping[str, Any] | None) -> PanelArray | None:
    """Build the rover's :class:`PanelArray`, or ``None`` if it declares none.

    A profile without panel geometry gets no invented one: the caller reports
    the gain as unavailable and says why, exactly as C6 does for a rover with
    no ``thermal_tau_s``.
    """
    if rover is None:
        return None
    tilt = rover.get("panel_tilt_deg")
    offsets = rover.get("panel_face_azimuths_deg")
    mode = rover.get("panel_azimuth_mode")
    if tilt is None or offsets is None or mode is None:
        return None
    return PanelArray(
        faces=tuple(
            PanelFace(tilt_deg=float(tilt), azimuth_offset_deg=float(offset))
            for offset in offsets
        ),
        azimuth_mode=str(mode),
        azimuth_deg=(
            None
            if rover.get("panel_azimuth_deg") is None
            else float(rover["panel_azimuth_deg"])
        ),
        kind="assumption",
        source=str(rover.get("panel_geometry_source") or ""),
    )


def rover_panel_block(rover: Mapping[str, Any] | None) -> dict[str, Any]:
    """The catalogue's panel geometry, for ``GET /api/rovers`` (C3's pattern)."""
    array = array_for_rover(rover)
    if array is None:
        return {
            "declared": False,
            "reason": "this profile declares no panel geometry",
            "model_id": PANEL_MODEL_ID,
            "validity": PANEL_VALIDITY,
            "claim": PANEL_CLAIM,
        }
    block = array.as_dict()
    block.update(
        {
            "declared": True,
            "tilt_deg": float(rover["panel_tilt_deg"]),  # type: ignore[index]
            "model_id": PANEL_MODEL_ID,
            "validity": PANEL_VALIDITY,
            "claim": PANEL_CLAIM,
        }
    )
    return block


# ── NASA's two numbers, our arithmetic ──────────────────────────────────────


def viper_corner_check() -> dict[str, float | str]:
    """What this geometry model says about NASA's "320W per panel (450W on corner)".

    Both numbers describe the same hardware in two geometries, so the ratio
    between them is a pure geometry statement -- and this model predicts it
    without being fitted to it. With the Sun on the horizon, one vertical face
    at normal incidence gives raw 1; turning the body until the Sun sits
    between two faces gives raw sqrt(2).

    OURS, not NASA's: NASA published the two powers, this function does the
    arithmetic. It is a consistency check on the geometry term, not a
    validation of LunaPath's energy model, and it is never presented as one.
    """
    array = _VIPER_BODY_ARRAY
    one_face = PanelArray(
        faces=(PanelFace(tilt_deg=90.0, azimuth_offset_deg=0.0),),
        azimuth_mode="sun_tracking",
        azimuth_deg=None,
        kind="assumption",
        source="assumption: one face of the three, held normal to the Sun",
    ).raw(0.0, 0.0, 0.0)
    psi, corner = best_reference_azimuth(0.0, 0.0, array)
    per_panel_w = float(VIPER_QUOTED["per_panel_w"])
    published_w = float(VIPER_QUOTED["on_corner_w"])
    predicted_w = per_panel_w * corner / one_face
    return {
        "one_face_raw": float(one_face),
        "corner_raw": float(corner),
        "corner_reference_azimuth_deg": float(psi),
        "model_ratio": float(corner / one_face),
        "published_ratio": published_w / per_panel_w,
        "per_panel_w": per_panel_w,
        "predicted_on_corner_w": float(predicted_w),
        "published_on_corner_w": published_w,
        "difference_w": float(predicted_w - published_w),
        "difference_pct": float((predicted_w / published_w - 1.0) * 100.0),
        "quote": str(VIPER_QUOTED["quote"]),
        "source": str(VIPER_QUOTED["source"]),
        "note": (
            "OURS: NASA published the two powers, this is our arithmetic on them. A "
            "consistency check on the geometry term, not a validation of the energy model."
        ),
    }


# ── counterfactual geometries, for the report and every response ────────────

#: The counterfactual arrays every panel block reports beside the rover's own.
#: They bound the model risk of an unpublished geometry; none of them is a
#: claim about any vehicle.
def _named_arrays(tilt_deg: float) -> dict[str, PanelArray]:
    def build(faces, mode, azimuth=None, note="", tilt_mode="fixed"):
        return PanelArray(
            faces=faces,
            azimuth_mode=mode,
            azimuth_deg=azimuth,
            kind="counterfactual",
            source=f"counterfactual: {note}",
            tilt_mode=tilt_mode,
        )

    return {
        "sun_pointed": build(
            (PanelFace(tilt_deg=0.0, azimuth_offset_deg=0.0),),
            "sun_tracking",
            tilt_mode="sun_tracking",
            note=(
                "the pre-C1 model -- a plate always face-on to the Sun (Otten's 2-DOF "
                "articulated array); g == 1 wherever the Sun is up"
            ),
        ),
        "horizontal": build(
            (PanelFace(tilt_deg=0.0, azimuth_offset_deg=0.0),),
            "fixed",
            azimuth=0.0,
            note="RoverDevKit's default array, flat on the rover deck: cos i = sin e",
        ),
        "polar_tracking": build(
            (PanelFace(tilt_deg=tilt_deg, azimuth_offset_deg=0.0),),
            "sun_tracking",
            note=(
                f"one plate at RoverDevKit's polar tilt ({tilt_deg:g} deg), free to turn "
                "in azimuth"
            ),
        ),
        "polar_fixed_north": build(
            (PanelFace(tilt_deg=tilt_deg, azimuth_offset_deg=0.0),),
            "fixed",
            azimuth=0.0,
            note=f"the same plate bolted down facing true north at {tilt_deg:g} deg tilt",
        ),
        "body_three_face": build(
            _VIPER_FACES,
            "free_heading",
            note=(
                "VIPER's three body faces (port, starboard, aft), the rover free to turn "
                "to the best heading"
            ),
        ),
    }


_VIPER_FACES: tuple[PanelFace, ...] = (
    PanelFace(tilt_deg=90.0, azimuth_offset_deg=90.0),
    PanelFace(tilt_deg=90.0, azimuth_offset_deg=-90.0),
    PanelFace(tilt_deg=90.0, azimuth_offset_deg=180.0),
)

_VIPER_BODY_ARRAY: PanelArray = PanelArray(
    faces=_VIPER_FACES,
    azimuth_mode="free_heading",
    azimuth_deg=None,
    kind="assumption",
    source="assumption: VIPER's three body faces, used for the corner cross-check",
)


def counterfactual_gains(
    sun_track: Sequence[Mapping[str, Any]], tilt_deg: float = POLAR_TILT_CAP_DEG
) -> dict[str, dict[str, Any]]:
    """Mean/min/max gain of each named geometry over a Sun track.

    Reported beside the rover's own geometry so a reader can see how much of
    the answer is the assumption rather than the site.
    """
    # "When lit" means the SUN IS UP, not "this panel happened to face it".
    # Averaging a fixed panel only over the slices where it collects anything
    # would quietly drop its worst hours and flatter it against a tracking
    # array -- which is the comparison this table exists to make.
    elevations = np.array(
        [float(sample["elevation_deg"]) for sample in sun_track], dtype=np.float64
    )
    sun_up = elevations > 0.0
    out: dict[str, dict[str, Any]] = {}
    for name, array in _named_arrays(tilt_deg).items():
        gains = gain_series(sun_track, array)
        out[name] = {
            "mean": float(gains.mean()) if gains.size else 0.0,
            "mean_when_sun_up": (
                float(gains[sun_up].mean()) if bool(sun_up.any()) else 0.0
            ),
            "min": float(gains.min()) if gains.size else 0.0,
            "max": float(gains.max()) if gains.size else 0.0,
            "sun_up_fraction": float(sun_up.mean()) if gains.size else 0.0,
            # How often this geometry collects anything at all. For a
            # tracking array this equals sun_up_fraction; for a fixed one it
            # is smaller, and the gap is the cost of not being able to turn.
            "positive_fraction": float((gains > 0.0).mean()) if gains.size else 0.0,
            "source": array.source,
        }
    return out


# ── the response block ──────────────────────────────────────────────────────


def conservative_gain(gains: np.ndarray) -> float:
    """One scalar standing in for a whole gain series, for a SAFETY bound.

    The worst POINTING loss the array suffers while there IS light -- not the
    smallest number in the series. :func:`panel_gain` returns exactly 0
    whenever the Sun is below the horizon, so a plain minimum over a horizon
    that runs into the night collapses to 0, and a consumer that folds one
    scalar into its power law (``survival._power_terms``) would then model a
    rover whose array produces nothing even in a fully lit cell at a fully
    lit time. That is not conservatism, it is double-counting darkness: the
    consumer's own exposure term already carries it.

    An all-dark series has no pointing question to answer and returns 1.0;
    the income is zero through the exposure term either way.
    """
    values = np.asarray(gains, dtype=np.float64).reshape(-1)
    lit = values[values > 0.0]
    return float(np.min(lit)) if lit.size else 1.0


def gain_stats(gains: np.ndarray | None) -> dict[str, Any]:
    if gains is None or gains.size == 0:
        return {"min": None, "mean": None, "max": None, "n_slices": 0}
    return {
        "min": float(np.min(gains)),
        "mean": float(np.mean(gains)),
        "max": float(np.max(gains)),
        "n_slices": int(gains.size),
    }


def panel_block(
    rover: Mapping[str, Any] | None,
    gains: np.ndarray | None,
    requested: bool,
    reason: str | None = None,
    sun_track: Sequence[Mapping[str, Any]] | None = None,
    tilt_deg: float = POLAR_TILT_CAP_DEG,
) -> dict[str, Any]:
    """The ``panel`` block every C1-aware response carries.

    Always reported; ``applied`` is true only when the caller asked for the
    cos i model AND a gain series could actually be built, which is the same
    ``bool(requested and artefact is not None)`` rule A1, A2, B1 and C6 use.
    """
    array = array_for_rover(rover)
    applied = bool(requested and gains is not None)
    block: dict[str, Any] = {
        "model": "cos_incidence" if applied else "sun_pointed",
        "requested": "cos_incidence" if requested else "sun_pointed",
        "applied": applied,
        "reason": reason,
        "model_id": PANEL_MODEL_ID,
        "validity": PANEL_VALIDITY,
        "scope": PANEL_SCOPE,
        "claim": PANEL_CLAIM,
        "geometry": None if array is None else array.as_dict(),
        "gain": gain_stats(gains),
        "gain_series": None if gains is None else [float(g) for g in gains],
        "viper_corner_check": viper_corner_check(),
        "roverdevkit_quoted": dict(ROVERDEVKIT_QUOTED),
    }
    if sun_track:
        block["counterfactuals"] = counterfactual_gains(sun_track, tilt_deg)
        block["sun_elevation_deg"] = {
            "min": float(min(s["elevation_deg"] for s in sun_track)),
            "max": float(max(s["elevation_deg"] for s in sun_track)),
        }
    else:
        block["counterfactuals"] = None
        block["sun_elevation_deg"] = None
    return block
