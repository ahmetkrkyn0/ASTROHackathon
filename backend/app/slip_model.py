"""Wheel slip: the gap between distance commanded and distance covered.

On loose regolith the wheels turn further than the body advances, so the
time and the energy of a traverse are higher than the slip-free
arithmetic says. Until C3 this module refused to put a NUMBER on that
gap: its coefficients were a rough literature-shaped guess, it labelled
itself ``UNCALIBRATED`` and, deliberately, nothing in the product called
it (Round 2 review, L-2) -- so every energy and time figure LunaPath
published was systematically optimistic (05_engel_kacinma.md 3.1; B5's
VIPER route bottomed at 32 percent on the plan and 23 in the Monte Carlo
nominal; B3 put the drive energy 6-10 percent low).

What is wired in now (C3)
-------------------------
``cost_engine.edge_travel_time_s`` -- the ONE function every travel-time
and energy figure derives from (``edge_energy_wh``, the per-metre energies,
``move_battery_drain_wh``, the cost grid's energy criterion, the 4-D
planner's move length, the simulator, the corridor budgets, the Monte
Carlo legs, the safe-haven distances, the corridor slice counts,
``auto_slice_hours``) -- now converts the commanded distance into the
wheel distance actually needed, ``d / (1 - slip_ratio(slope, rover))``.
Time and energy grow together, because the wheels turn (and draw traction
power) for the whole effective distance. There is exactly one binding
point, so every consumer stays consistent with every other; the
vectorised twin ``slip_ratio_array`` is written in the same operation
order and is checked bit-for-bit against the scalar, so the planner's
per-edge arithmetic and the vectorised graphs (``safe_haven._gated_edges``,
``illumination_corridor.edge_tables``) round identically.

Where the numbers come from -- read this before quoting any of them
-------------------------------------------------------------------
The curve is a literature-anchored MODEL, not a measurement, and the label
says so: ``SLIP_MODEL_VALIDITY = "MODEL"``. Never ``"MEASURED"``: nothing
here was measured on polar regolith (no Diviner product is available
locally either).

* **VIPER (design constraint, ground test).** "The mobility design
  requirements of the VIPER mission defined a maximum of 40% slip up a
  maximum slope of 15 deg" -- Planetary Science Journal 2025, sect. 3.5;
  GRC-1 simulant at 15-20 percent relative density (loose), MGRU test
  unit, slip from wheel rotation rates against Optitrack motion tracking.
  An UPPER BOUND the vehicle was designed to, not a typical value.
* **Yutu-2 (measured, Chang'e-4, lunar far side).** "Most the wheel slip
  ratios are between 0 and -0.075" on slopes up to 8.86 deg -- Nature
  Communications 2024 (digital-twin study, open access; see also Ding et
  al., Science Robotics 2022). Negative means SKID (body faster than the
  wheel); this model keeps only the magnitude, the ground the wheel loses.
  Mare regolith, gentle slopes -- not the pole.
* **Shape (assumption).** Log-linear (exponential) between anchors and
  beyond the last one, capped at ``MAX_SLIP_RATIO``: the form the previous
  uncalibrated model used and the convex shape slip-versus-slope curves
  show on loose soil (MER, Angelova et al. JFR 2007; terramechanics,
  Ishigami et al. JFR 2007).
* **Transfers (assumptions).** Yutu-2's flat-ground value and VIPER's
  15 deg ceiling are used for profiles that have no slip data of their own
  (LPR-1, LUVMI-M) and for each other; every such anchor is ``kind ==
  "assumption"`` and its ``source`` starts with "assumption:". No anchor
  exists without a source.
* **Spread (B2 hook).** ``slip_stats`` returns ``(mu, sigma)``: sigma is the
  anchor's own spread (Yutu-2: range/4, i.e. the measured range read as
  +-2 sigma) and, for VIPER's single design value, Yutu-2's relative spread
  transferred as an assumption. The relative spread is interpolated
  linearly in slope between anchors.

Thermal inertia (design note, not applied)
------------------------------------------
Cunningham, Nesnas and Whittaker (RSS 2017; Autonomous Robots 2019) showed
with Curiosity data that low thermal inertia (loose sand) predicts high
slip better than appearance does. LunaPath's counterpart would scale the
anchors by a Diviner-derived thermal-inertia proxy. That product is not
available locally: ``scripts/build_diviner_prp_cache.py`` fetches the PRP,
but that product carries annual max/average temperature, not thermal
inertia. So :func:`thermal_inertia_slip_scale` is a SIGNATURE that refuses
to run, not a factor that looks applied.

The replan trigger
------------------
Slip is also the one odometry signal LunaPath can check without any
perception: commanded distance is something the planner knows, travelled
distance is something ``PoseEstimate`` reports, and a growing divergence
means the wheels are digging in. :func:`check_slip_accumulation` is live
in ``evaluate_pose`` and unchanged by C3.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:  # replan_triggers imports constants, which imports this module
    from .replan_triggers import TriggerResult

SLIP_MODEL_VALIDITY: str = "MODEL"
SLIP_MODEL_ID: str = "anchored_loglinear_v1"

# Slip cannot reach 1.0 -- that is the wheels spinning with the rover
# stationary, where effective distance would divide by zero and energy
# would be infinite. Real vehicles bog down and stop before this; the cap
# keeps the arithmetic finite and the failure legible.
MAX_SLIP_RATIO: float = 0.9

ANCHOR_KINDS: tuple[str, ...] = (
    "measured",
    "measured_bound",
    "design_constraint",
    "assumption",
)

SLIP_CLAIM: str = (
    "Literature-anchored MODEL, not a measurement: the curve passes through "
    "VIPER's mobility design requirement (a maximum of 40 percent slip up a "
    "15 deg slope, GRC-1 simulant at 15-20 percent relative density; PSJ 2025) "
    "and Yutu-2's measured slip ratio (0 to -0.075 on slopes up to 8.86 deg at "
    "the Chang'e-4 site; Nature Communications 2024), is exponential between "
    "and beyond the anchors (an assumption) and is capped at "
    f"{MAX_SLIP_RATIO:g}. Nothing here was measured on polar regolith; anchors "
    "transferred between profiles are labelled 'assumption'."
)

SLIP_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "viper_psj_2025",
        "title": "Investigating the Geotechnical Properties of the Lunar South Pole with NASA VIPER's Mobility System (PSJ 2025)",
        "url": "https://iopscience.iop.org/article/10.3847/PSJ/add13f",
        "used_for": "15 deg / 0.40 anchor (design requirement, sect. 3.5; GRC-1 at 15-20 percent relative density, sect. 3.2)",
    },
    {
        "id": "yutu2_natcomms_2024",
        "title": "Lunar rock investigation and tri-aspect characterization of lunar farside regolith by a digital twin (Nature Communications 2024)",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11258293/",
        "used_for": "0 deg and 8.86 deg anchors (slip 0 to -0.075 on slopes up to 8.86 deg), regolith parameter ranges",
    },
    {
        "id": "yutu2_scirobotics_2022",
        "title": "A 2-year locomotive exploration and scientific investigation of the lunar farside by the Yutu-2 rover (Science Robotics 2022)",
        "url": "https://www.science.org/doi/10.1126/scirobotics.abj6660",
        "used_for": "context: Yutu-2 locomotion record (light slip/skid)",
    },
    {
        "id": "cunningham_rss_2017",
        "title": "Improving Slip Prediction on Mars Using Thermal Inertia Measurements (RSS 2017; Autonomous Robots 2019)",
        "url": "https://roboticsproceedings.org/rss13/p38.pdf",
        "used_for": "thermal-inertia hook only; NOT applied (no Diviner product locally)",
    },
)


@dataclass(frozen=True)
class SlipAnchor:
    """One sourced point of a slip curve.

    ``slip`` is the expected slip ratio at ``slope_deg`` (ground lost as a
    fraction of wheel travel), ``sigma`` its one-sigma spread for B2, ``kind``
    how the number was obtained and ``source`` where -- mandatory, never
    empty, and starting with "assumption:" when the value was transferred
    from another vehicle or terrain.
    """

    slope_deg: float
    slip: float
    sigma: float
    kind: str
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "slope_deg": float(self.slope_deg),
            "slip": float(self.slip),
            "sigma": float(self.sigma),
            "kind": self.kind,
            "source": self.source,
        }


@dataclass(frozen=True, eq=False)
class SlipCurve:
    """A compiled anchor set: log-linear segments ready to evaluate."""

    anchors: tuple[SlipAnchor, ...]
    xs: tuple[float, ...]
    log_ys: tuple[float, ...]
    ks: tuple[float, ...]
    rel_sigmas: tuple[float, ...]
    xs_array: np.ndarray
    log_ys_array: np.ndarray
    ks_array: np.ndarray


def compile_curve(anchors: Iterable[SlipAnchor]) -> SlipCurve:
    """Validate an anchor set and precompute its log-linear segments.

    Raises ``ValueError`` -- naming the fault -- for fewer than two anchors,
    an unknown ``kind``, an empty ``source``, a negative ``sigma``, a slip
    outside ``(0, MAX_SLIP_RATIO)``, slopes that are not strictly
    increasing, a first anchor not at 0 deg, or a slip that decreases with
    slope. A malformed catalogue therefore fails at import, not on a route.
    """
    points = tuple(anchors)
    if len(points) < 2:
        raise ValueError("a slip curve needs at least two anchors")
    for anchor in points:
        if not isinstance(anchor, SlipAnchor):
            raise ValueError(f"slip anchors must be SlipAnchor instances, got {anchor!r}")
        if anchor.kind not in ANCHOR_KINDS:
            raise ValueError(
                f"anchor kind {anchor.kind!r} is not one of {ANCHOR_KINDS}"
            )
        if not str(anchor.source).strip():
            raise ValueError(
                f"the {anchor.slope_deg:g} deg anchor has no source; every anchor must cite one"
            )
        if not (float(anchor.sigma) >= 0.0):
            raise ValueError(f"the {anchor.slope_deg:g} deg anchor has a negative sigma")
        if not (0.0 < float(anchor.slip) < MAX_SLIP_RATIO):
            raise ValueError(
                f"the {anchor.slope_deg:g} deg anchor's slip {anchor.slip!r} must lie "
                f"in (0, MAX_SLIP_RATIO={MAX_SLIP_RATIO:g})"
            )
        if not math.isfinite(float(anchor.slope_deg)):
            raise ValueError("anchor slopes must be finite")
    xs = tuple(float(a.slope_deg) for a in points)
    for left, right in zip(xs[:-1], xs[1:]):
        if not right > left:
            raise ValueError("anchor slopes must be strictly increasing")
    if xs[0] != 0.0:
        raise ValueError("the first anchor must sit at 0 deg (flat ground)")
    ys = tuple(float(a.slip) for a in points)
    for left, right in zip(ys[:-1], ys[1:]):
        if right < left:
            raise ValueError("slip may not decrease with slope")
    log_ys = tuple(math.log(y) for y in ys)
    ks = tuple(
        (log_ys[i + 1] - log_ys[i]) / (xs[i + 1] - xs[i]) for i in range(len(xs) - 1)
    )
    rel_sigmas = tuple(float(a.sigma) / float(a.slip) for a in points)
    return SlipCurve(
        anchors=points,
        xs=xs,
        log_ys=log_ys,
        ks=ks,
        rel_sigmas=rel_sigmas,
        xs_array=np.asarray(xs, dtype=np.float64),
        log_ys_array=np.asarray(log_ys, dtype=np.float64),
        ks_array=np.asarray(ks, dtype=np.float64),
    )


# Compiled curves keyed by the identity of the anchor tuple. The catalogue's
# tuples live for the life of the process, so this is a handful of entries;
# the ``is`` check guards against a recycled id. Identity rather than hash:
# the planner asks for slip on every edge it expands, and hashing a tuple
# of dataclasses per call would cost more than the curve itself.
_COMPILED: dict[int, tuple[Any, SlipCurve]] = {}
_COMPILED_LIMIT = 64


def curve_for(rover: Mapping[str, Any] | None) -> SlipCurve | None:
    """The compiled curve of a rover profile, or ``None`` when it declares
    no ``slip_curve`` -- in which case no correction is applied and every
    consumer reports ``applied: false``. There is no silent default curve."""
    if rover is None:
        return None
    anchors = rover.get("slip_curve")
    if anchors is None:
        return None
    entry = _COMPILED.get(id(anchors))
    if entry is not None and entry[0] is anchors:
        return entry[1]
    if isinstance(anchors, SlipCurve):
        curve = anchors
    else:
        curve = compile_curve(anchors)
    if len(_COMPILED) >= _COMPILED_LIMIT:
        _COMPILED.clear()
    _COMPILED[id(anchors)] = (anchors, curve)
    return curve


def _resolve(rover: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if rover is not None:
        return rover
    from .constants import get_rover  # local: constants imports SlipAnchor from here

    return get_rover()


def _segment_index(curve: SlipCurve, x: float) -> int:
    i = bisect.bisect_right(curve.xs, x) - 1
    last = len(curve.xs) - 2
    if i < 0:
        return 0
    if i > last:
        return last
    return i


def _evaluate(curve: SlipCurve, x: float) -> float:
    if x != x:  # NaN: propagate, as the vectorised path does
        return float("nan")
    i = _segment_index(curve, x)
    s = math.exp(curve.log_ys[i] + curve.ks[i] * (x - curve.xs[i]))
    return min(MAX_SLIP_RATIO, s)


def slip_ratio(slope_deg: float, rover: Mapping[str, Any] | None = None) -> float:
    """Fraction of wheel travel lost to slip on a *slope_deg* incline.

    0 means the rover advances exactly as commanded; 0.4 means it covers
    60 percent of the commanded distance. Symmetric in the slope's sign,
    log-linear between the profile's anchors, capped at ``MAX_SLIP_RATIO``.
    A profile without a ``slip_curve`` gets 0.0. See the module docstring
    for what the anchors are and are not.
    """
    curve = curve_for(_resolve(rover))
    if curve is None:
        return 0.0
    return _evaluate(curve, abs(float(slope_deg)))


def slip_ratio_array(
    slope_deg: np.ndarray, rover: Mapping[str, Any] | None = None
) -> np.ndarray:
    """:func:`slip_ratio` over an array, in the same operation order.

    Bit-for-bit equal to the scalar on this platform (tested), so a graph
    built from this and a planner calling the scalar per edge round a move
    of exactly one slice the same way.
    """
    x = np.abs(np.asarray(slope_deg, dtype=np.float64))
    curve = curve_for(_resolve(rover))
    if curve is None:
        return np.zeros_like(x)
    last = len(curve.xs) - 2
    i = np.clip(np.searchsorted(curve.xs_array, x, side="right") - 1, 0, last)
    s = np.exp(curve.log_ys_array[i] + curve.ks_array[i] * (x - curve.xs_array[i]))
    return np.minimum(MAX_SLIP_RATIO, s)


def slip_stats(
    slope_deg: float, rover: Mapping[str, Any] | None = None
) -> tuple[float, float]:
    """``(mu, sigma)`` of the slip ratio at *slope_deg* -- the B2 hook.

    ``mu`` is :func:`slip_ratio`; ``sigma = mu * rel(slope)`` where ``rel``
    is each anchor's ``sigma / slip`` interpolated linearly in slope and
    held constant beyond the last anchor. ``(0.0, 0.0)`` without a curve.
    """
    curve = curve_for(_resolve(rover))
    if curve is None:
        return 0.0, 0.0
    x = abs(float(slope_deg))
    mu = _evaluate(curve, x)
    i = _segment_index(curve, x)
    span = curve.xs[i + 1] - curve.xs[i]
    t = (x - curve.xs[i]) / span
    t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
    rel = curve.rel_sigmas[i] + t * (curve.rel_sigmas[i + 1] - curve.rel_sigmas[i])
    return mu, mu * rel


def effective_distance_m(
    distance_m: float, slope_deg: float, rover: Mapping[str, Any] | None = None
) -> float:
    """Wheel distance needed to advance *distance_m* over the ground.

    Energy and travel time both scale with this rather than with the
    commanded distance, because the wheels turn the full amount whether
    or not the body keeps up. This is the correction
    ``cost_engine.edge_travel_time_s`` applies.
    """
    return float(distance_m) / (1.0 - slip_ratio(slope_deg, rover))


def slip_energy_multiplier(
    slope_deg: float, rover: Mapping[str, Any] | None = None
) -> float:
    """Factor by which slip raises the energy and time of a traverse.

    ``edge_energy_wh`` is linear in travel time and travel time is linear
    in distance, so a single multiplier covers both.
    """
    return 1.0 / (1.0 - slip_ratio(slope_deg, rover))


def curve_table(
    rover: Mapping[str, Any],
    slopes: tuple[float, ...] = (0.0, 5.0, 10.0, 15.0, 20.0, 25.0),
) -> list[dict[str, Any]]:
    """The curve read at a few slopes, for the catalogue and the report."""
    slope_max = rover.get("slope_max_deg")
    rows = []
    for slope in slopes:
        mu, sigma = slip_stats(slope, rover)
        rows.append(
            {
                "slope_deg": float(slope),
                "slip": mu,
                "sigma": sigma,
                "time_energy_factor": 1.0 / (1.0 - mu),
                "within_slope_limit": (
                    None if slope_max is None else bool(float(slope) <= float(slope_max))
                ),
            }
        )
    return rows


def rover_slip_block(rover: Mapping[str, Any]) -> dict[str, Any]:
    """The ``slip_model`` block ``/api/rovers`` publishes per profile."""
    curve = curve_for(rover)
    if curve is None:
        return {
            "applied": False,
            "validity": None,
            "model_id": SLIP_MODEL_ID,
            "max_slip_ratio": MAX_SLIP_RATIO,
            "claim": "This profile declares no slip_curve: no slip correction is applied to its routes.",
            "anchors": [],
            "table": [],
            "references": list(SLIP_REFERENCES),
        }
    return {
        "applied": True,
        "validity": SLIP_MODEL_VALIDITY,
        "model_id": SLIP_MODEL_ID,
        "max_slip_ratio": MAX_SLIP_RATIO,
        "claim": SLIP_CLAIM,
        "anchors": [anchor.as_dict() for anchor in curve.anchors],
        "table": curve_table(rover),
        "references": list(SLIP_REFERENCES),
    }


def route_slip_summary(
    legs: Iterable[tuple[float, float, float, float | None]],
    rover: Mapping[str, Any],
) -> dict[str, Any]:
    """The ``slip_model`` block a plan response carries for ONE route.

    *legs* are the route's driven edges as ``(slope_deg, distance_m, hours,
    drawn_wh)``: the grade the edge was priced at, its commanded length, the
    slip-inclusive travel time and the energy drawn during it (``None`` when
    a caller has no energy figure). Since ``t = t0 / (1 - s)``, the hours
    slip added are ``t * s`` and, energy being proportional to time, the
    Wh slip added are ``E * s``. Edges with a non-finite time are skipped
    and counted.
    """
    curve = curve_for(rover)
    applied = curve is not None
    moves = 0
    skipped = 0
    distance_sum = 0.0
    effective_sum = 0.0
    weighted_slip = 0.0
    max_slip = 0.0
    max_slip_slope = None
    extra_hours = 0.0
    extra_wh = 0.0
    wh_known = True
    for slope_deg, distance_m, hours, drawn_wh in legs:
        hours = float(hours)
        if not math.isfinite(hours):
            skipped += 1
            continue
        d = float(distance_m)
        s = slip_ratio(slope_deg, rover) if applied else 0.0
        moves += 1
        distance_sum += d
        effective_sum += d / (1.0 - s)
        weighted_slip += d * s
        if s >= max_slip:
            max_slip = s
            max_slip_slope = float(slope_deg)
        extra_hours += hours * s
        if drawn_wh is None or not math.isfinite(float(drawn_wh)):
            wh_known = False
        else:
            extra_wh += float(drawn_wh) * s
    route = {
        "moves": moves,
        "skipped_edges": skipped,
        "mean_slip": (weighted_slip / distance_sum) if distance_sum > 0.0 else 0.0,
        "max_slip": max_slip,
        "max_slip_slope_deg": max_slip_slope,
        "distance_factor": (effective_sum / distance_sum) if distance_sum > 0.0 else 1.0,
        "extra_hours": extra_hours,
        "extra_drawn_wh": extra_wh if (wh_known and moves > 0) else None,
    }
    return {
        "applied": applied,
        "validity": SLIP_MODEL_VALIDITY if applied else None,
        "model_id": SLIP_MODEL_ID,
        "route": route,
        "claim": SLIP_CLAIM if applied else (
            "This profile declares no slip_curve: the route's times and energies are slip-free."
        ),
    }


def thermal_inertia_slip_scale(
    thermal_inertia: np.ndarray, reference_inertia: float | None = None
) -> np.ndarray:
    """Per-cell factor by which a thermal-inertia proxy would scale the slip
    anchors (Cunningham, Nesnas, Whittaker; RSS 2017: low thermal inertia,
    loose sand, high slip).

    A signature, not a model. LunaPath has no thermal-inertia layer at
    all: ``thermal_grid.npy`` holds a Heat1D-modelled sunlit peak (validity
    DERIVED once shadow is folded in -- it is only SYNTHETIC when heat1d is
    unavailable and the fallback runs), and the Diviner PRP C5 caches
    carries annual max/average temperature, not inertia. So this refuses
    rather than return a factor that would read as applied. Fetch the
    Diviner Polar Resource Products
    (``LRO-L-DLRE-5-PRP-V2.0``; see ``scripts/build_diviner_prp_cache.py``),
    derive a night-temperature / thermal-inertia proxy, and implement the
    scaling here with its own validity label.
    """
    raise NotImplementedError(
        "thermal-inertia modulation of slip needs a measured Diviner thermal "
        "inertia (or night temperature) layer; none is available locally. "
        "See scripts/build_diviner_prp_cache.py for the product to fetch "
        "(LRO-L-DLRE-5-PRP-V2.0)."
    )


# ── The replan trigger (unchanged by C3) ─────────────────────────────────────

# Ratio of travelled to commanded distance below which the rover is
# losing so much ground that the plan's distance assumptions no longer
# hold. From the trigger table in 05_engel_kacinma.md.
SLIP_ACCUMULATION_THRESHOLD: float = 0.75

# How far past the corridor's own length an odometry claim may run before
# it is treated as an epoch error rather than as slip. Weaving inside a
# corridor and ordinary obstacle avoidance genuinely add path length; a
# claim of several times the route is not slip, it is a counter that was
# never reset. (Round 4 review, L-6.)
ODOMETER_EPOCH_TOLERANCE: float = 1.5


def check_slip_accumulation(
    map_progress_m: float,
    odometer_claim_m: float,
    threshold: float = SLIP_ACCUMULATION_THRESHOLD,
    corridor_length_m: float | None = None,
) -> TriggerResult:
    """Fire when ground actually gained falls below *threshold* of the
    distance the estimator claims to have covered.

    ``map_progress_m`` is LunaPath's own measurement -- how far along the
    corridor the projected pose has advanced. ``odometer_claim_m`` is
    what the odometry stack says it travelled. Wheels turning further
    than the body advances is exactly slip, so a ratio well under 1 means
    the terrain is costing more than planned and the remaining route's
    energy and time budgets are no longer trustworthy.

    Neither quantity is a COMMANDED distance -- an earlier revision named
    them ``travelled_m``/``commanded_m``, so the evidence string that
    justified a replan described inputs that did not exist and an auditor
    would have gone looking for a commanded distance nothing recorded.
    (Round 2 review, M-5.)
    """
    from .replan_triggers import TriggerResult  # local: avoids an import cycle

    claim = float(odometer_claim_m)
    progress = float(map_progress_m)

    # `distance_travelled_m` is contractually counted FROM THE START OF THE
    # ACTIVE CORRIDOR and reset on every new plan (see app.pose). Nothing
    # enforced that: a caller integrating since boot hands a replanned
    # corridor a near-zero along-track against a large claim, the ratio
    # collapses, slip fires, the response recommends a replan -- which
    # issues another corridor and repeats. Detecting the impossible claim is
    # what breaks the loop. (Round 4 review, L-6.)
    if (
        corridor_length_m is not None
        and float(corridor_length_m) > 0.0
        and claim > ODOMETER_EPOCH_TOLERANCE * float(corridor_length_m)
    ):
        return TriggerResult(
            "slip_accumulation",
            False,
            f"odometry claims {claim:.1f} m against a corridor only "
            f"{float(corridor_length_m):.1f} m long; distance_travelled_m is "
            "counted from the start of the ACTIVE corridor and must be reset "
            "on every new plan, so this claim cannot be compared",
        )

    if claim <= 0.0:
        # Nothing was claimed, so there is no ratio to judge. Report
        # not-fired with the reason stated rather than dividing by zero or
        # returning a fired trigger on a vacuous comparison.
        return TriggerResult(
            "slip_accumulation",
            False,
            "no odometry distance claim to compare against",
        )

    ratio = progress / claim
    fired = ratio < float(threshold)
    return TriggerResult(
        "slip_accumulation",
        fired,
        f"advanced {progress:.1f} m along the corridor while odometry "
        f"claims {claim:.1f} m travelled "
        f"(ratio {ratio:.2f}, threshold {threshold:.2f}); "
        f"slip model is {SLIP_MODEL_VALIDITY}",
    )
