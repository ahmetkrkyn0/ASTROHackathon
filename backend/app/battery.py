"""The battery in the cold, and hibernation through the dark (C2).

LunaPath's energy model has always known how much light a cell gets and never
how cold it is. Three consequences, all of them wrong in the same direction:

* battery capacity is a constant -- ``e_cap_wh`` is the same number at 0 C and
  at -60 C, although the catalogue's own 5 420 Wh is quoted *at 0 C*;
* the survival heater is a constant power scaled by SHADOW RATIO
  (``cost_engine.housekeeping_power_w``), so a cell that is lit but cold pays
  nothing for heating. On Site11 that assumption is not approximately wrong,
  it is uninformative: the measured Spearman correlation between shadow ratio
  and surface temperature over the 210 063 traversable cells is **-0.0014**;
* ``h_max_shadow_h`` is one scalar per rover, the same at full charge and at
  the reserve, the same warm and frozen.

And ``p_hibernate_w`` sat in the catalogue with no reader anywhere in the
codebase -- a whole vehicle power state the model could not express.

This module supplies the three missing pieces and wires that field:

* :func:`usable_fraction` -- what fraction of the stored charge the pack can
  actually deliver at a given inner temperature;
* :func:`heater_power_w` -- the survival heater's power from the TEMPERATURE
  DIFFERENCE, using NASA JSC's own Stefan-Boltzmann form, calibrated against
  the catalogue's published ``p_heater_w``;
* :func:`shadow_endurance_h`, :func:`hibernation_available`,
  :func:`dawn_preheat` -- the dark endurance as a function of state, and
  hibernation as something the 4-D planner can actually choose.

What is NASA's and what is ours is stated in :data:`BATTERY_CLAIM`,
:data:`NASA_GLENN_QUOTED` and :data:`JSC_QUOTED`; every response carries all
three. Nothing here is a rover specification: no profile in this catalogue
publishes a capacity-versus-temperature curve, a heater conductance, a
radiating area or a hibernation endurance. Every value that is not read
straight from the catalogue carries a source string beginning ``assumption:``.

Two sources in this module disagree with each other, and the disagreement is
reported rather than resolved. NASA Glenn (low-cost robotic landers) argues
that common 18650 cells survive and recover from the lunar night. NASA JSC /
Jacobs (a crewed Lunar Terrain Vehicle) warns that "fully turning off the
vehicle in a cold environment would certainly jeopardize its ability to
return to operation in the future". Glenn's evidence is about CELLS; JSC's
caution is about AVIONICS. :func:`components_past_operating_limit` names which
component's declared limit a hibernation crosses, so a reader can see both.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from . import constants as C
from .thermal_dwell import Envelope, rover_envelope

# ── identity, claim, references, quotations ─────────────────────────────────

BATTERY_MODEL_ID: str = "cold_capacity_radiative_heater_hibernation_v1"
BATTERY_VALIDITY: str = "MODEL"

#: How the battery's capacity enters the model. ``constant``: it does not --
#: ``e_cap_wh`` is the same number at every temperature, the pre-C2 model.
#: ``temperature_derated``: the stored charge is converted to DELIVERABLE
#: charge through :func:`usable_fraction`.
BATTERY_MODELS: tuple[str, ...] = ("constant", "temperature_derated")

#: How the survival heater's POWER is priced. ``constant``: the pre-C2 term,
#: ``shadow_ratio * (p_shadow_w - p_idle_w)`` -- exposure, not temperature.
#: ``delta_t``: the linear form the research document asked for,
#: ``kA * (T_set - T_surface)``. ``radiative``: NASA JSC's own Stefan-Boltzmann
#: law, ``esA * (T_set^4 - T_surface^4)``, which is what that document's own
#: cited source actually writes down.
HEATER_POWER_MODELS: tuple[str, ...] = ("constant", "delta_t", "radiative")

#: The temperature at which the cited measurement puts 18650 Li-ion
#: electrolyte freezing, in kelvin. NASA Glenn writes "(-70 C)" beside it,
#: which is 200 K rounded; the exact conversion is used here.
BATTERY_FREEZE_K: float = 200.0
BATTERY_FREEZE_C: float = BATTERY_FREEZE_K - 273.15   # -73.15 C

STEFAN_BOLTZMANN: float = 5.670374419e-8              # W m^-2 K^-4

BATTERY_SCOPE: str = (
    "usable_fraction(T) = the fraction of stored charge the pack delivers at inner "
    "temperature T: 1.0 at and above the profile's declared battery operating minimum "
    "(bat_op_min_c), 0.0 at and below the cited electrolyte freeze point (200 K), a "
    "labelled shape in between; heater_power_w(surface) = esA * (T_set^4 - T_surface^4) "
    "clipped to [0, p_heater_w], with esA calibrated so the published p_heater_w exactly "
    "holds the set point at the coldest surface the traversability gate admits; "
    "shadow_endurance_h(charge, T) = the published h_max_shadow_h scaled by the fraction "
    "of the deliverable charge above the reserve that this state still has; hibernation = "
    "a dormant state at the catalogue's p_hibernate_w, entered in darkness, left at first "
    "illumination after a dawn pre-heat paid out of the solar array."
)

BATTERY_CLAIM: str = (
    "MODEL, uncalibrated. No rover in this catalogue publishes a capacity-versus-"
    "temperature curve, a heater conductance k, a radiating area A, a hibernation "
    "endurance or a thermostat set point, so every coefficient here is either read "
    "straight from a declared catalogue field or carries a source string beginning "
    "'assumption:'. The 200 K freeze point is a MEASUREMENT ON 18650 CELLS by NASA Glenn "
    "and ISRO -- not on any vehicle in this catalogue -- and transferring it to a rover "
    "battery is an explicit assumption. The curve's SHAPE between the freeze point and "
    "the rating temperature has no source at all: the default is linear and the report "
    "sweeps the exponent. The research document's '85 percent at 0 C, 60 percent at "
    "-20 C' is NOT used: it has no source, and 85 percent at 0 C would discount a second "
    "time a capacity already quoted at 0 C. The heater law is NASA JSC's Stefan-Boltzmann "
    "form; its coefficient is OURS, calibrated from p_heater_w under a stated sizing "
    "assumption. Charge-side cold limits, internal resistance, ageing, cycle life and "
    "cell balancing are NOT modelled and their absence is stated. An operating bound "
    "(bat_op_min_c) and a survival bound (200 K) are different things and are never used "
    "interchangeably. NASA's and ISRO's figures are quoted, never mixed with a measurement."
)

BATTERY_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "oeftering_spw_2021",
        "title": (
            "Oeftering, Bennett, Vankeuls, Uguccini -- Battery Hibernation for Surviving "
            "the Lunar Night (2021 Space Power Workshop, 19 April 2021), NASA Glenn "
            "Research Center"
        ),
        "url": "https://ntrs.nasa.gov/api/citations/20210011101",
        "used_for": (
            "the 200 K electrolyte freeze point and full recovery above it; the vacuum "
            "and LN2 cell trials; ISRO's -160 C / 14 day result; Surveyor 1's six lunar "
            "cycles; the dawn-mode power architecture in which the pre-heat runs on solar "
            "array power with the battery isolated"
        ),
    },
    {
        "id": "oeftering_leef_2021",
        "title": (
            "Oeftering -- Lunar Power Hibernation for Surviving the Lunar Night (Lunar "
            "Extreme Environments Forum, 28 July 2021), NASA Glenn Research Center"
        ),
        "url": "https://ntrs.nasa.gov/api/citations/20210019184",
        "used_for": (
            "200 K labelled on Diviner's chart as the Li-ion battery freeze temperature; "
            "'Voltage dropped to zero below 200K'; the polar dusk-dawn cadence; the "
            "statement that arrays survive and generate at lunar dawn"
        ),
    },
    {
        "id": "nandini_jes_2018",
        "title": (
            "Nandini, Usha, Srinivasan, Pramod, Satyanarayana, Sankaran (ISRO Satellite "
            "Centre) -- Study on survivability of 18650 Lithium-ion cells at cryogenic "
            "temperatures, Journal of Energy Storage 17 (2018) 409-416"
        ),
        "url": "https://doi.org/10.1016/j.est.2018.03.021",
        "used_for": "the primary source behind NASA Glenn's quotation of the ISRO result",
    },
    {
        "id": "slusser_tfaws_2023",
        "title": (
            "Slusser, Wilcox (Jacobs Technology Inc.), Hernandez (NASA Johnson Space "
            "Center) -- Surviving Night at the Lunar South Pole: Exploring Viability of "
            "Radioisotope Power Systems for a Crewed Rover (TFAWS 2023, TFAWS23-PT-52)"
        ),
        "url": "https://tfaws.nasa.gov/wp-content/uploads/TFAWS23-PT-52-Paper.pdf",
        "used_for": (
            "the Stefan-Boltzmann heater law and the T^4 weighting; the 270 K -> 250 K / "
            "26 percent cross-check; the >400 kg battery finding; the caution against "
            "hibernating avionics. NOT the same paper as C6's ICES-2025-376, which shares "
            "only its first author"
        ),
    },
    {
        "id": "shirley_balaban_2022",
        "title": "Shirley, Balaban -- Overview of Mission Planning for the VIPER Rover (2022)",
        "url": "https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf",
        "used_for": "VIPER's quoted 9.5 h drilling-in-shadow and 50 h min-power shadow endurance",
    },
)

#: NASA Glenn's and ISRO's own figures, read verbatim from the two NTRS PDFs on
#: 16 September 2026. Every one of them is THEIRS. None is a LunaPath result and
#: none is combined with one.
NASA_GLENN_QUOTED: dict[str, Any] = {
    "freeze_k": 200.0,
    "freeze_quote": "At T<200K (-70°C) electrolyte freezes",
    "voltage_quote": "Cell voltage drops to zero",
    "recovery_quote": "Voltage recovers when warmed above 200K",
    "diviner_label": "<- Li-Ion Battery Approx. Freeze Temperature",
    "ln2_cold_soak_k": 80.0,
    "ln2_trials": "3 of 5 recovered without problems; 2 of 5 safety device trips (1 atm, LN2)",
    "vacuum_chamber_mtorr": 70.0,
    "vacuum_hold_k": 100.0,
    "vacuum_trials": "4 of 4 cell trials in vacuum were successful",
    "isro_cells": "3 manufacturers of 18650 Li-ion cells",
    "isro_temperature_c": -160.0,
    "isro_days": 14,
    "isro_result": "Cells recovered charge capacity with no apparent damage or degradation",
    "surveyor_1": "Surveyor 1 operated fully/partially for 6 lunar cycles",
    "night_surface_k": "Night temperatures fall within a 50-100K range regardless of latitude",
    "dawn_mode": (
        "Lunar Dusk: Point Arrays toward Dawn, Shut-Down Loads, Isolate Battery, Wait for "
        "Dawn. Lunar Dawn (first illumination, coldest temperature): Solar Array output "
        "triggers a 'Dawn Mode' within the Main Bus Controller; MBC in Dawn Mode operates "
        "on Solar Array power alone (Battery still Isolated); MBC manages thermal "
        "conditioning (Pre-Heaters) for battery and avionics; on reaching safe temperatures "
        "BMS performs battery pre-charge"
    ),
}

#: NASA JSC / Jacobs' own figures, read verbatim from TFAWS23-PT-52 on
#: 16 September 2026. Theirs, not ours.
JSC_QUOTED: dict[str, Any] = {
    "law": "Q_rad = eps * sigma * A * (T_obj^4 - T_env^4)",
    "t4_quote": (
        "the desired temperature for an object is a significant driver of the amount "
        "heater power needed as the temperature of the object is weighted to the 4th power"
    ),
    "survival_temperature_quote": (
        "Decreasing a component's survival temperature from 270K to 250K, for example, "
        "decreases heater power requirements by 26%"
    ),
    "survival_temperature_from_k": 270.0,
    "survival_temperature_to_k": 250.0,
    "survival_temperature_reduction_pct": 26.0,
    "battery_mass_quote": (
        "One early LTV proposal aiming for a total vehicle mass of 500 kg found that "
        ">400 kg of battery mass was required to survive the night."
    ),
    "ltv_night_sizing_h": 125.0,
    "psr_floor_k": 25.0,
    "hibernation_caution": (
        "The variety of failure types precludes the ability to simply let some electrical "
        "components fully hibernate during a night and sink to low temperatures -- once "
        "exposed to a low enough temperature, many components simply will not operate when "
        "brought up to a more reasonable environment"
    ),
}

#: VIPER's quoted shadow endurances, for the report's comparison only.
VIPER_QUOTED: dict[str, Any] = {
    "drilling_in_shadow_h": 9.5,
    "min_power_shadow_h": 50.0,
    "source": "Shirley & Balaban 2022, Overview of Mission Planning for the VIPER Rover",
}

# ── the assumption strings ──────────────────────────────────────────────────

BATTERY_FREEZE_SOURCE: str = (
    "assumption: the 200 K electrolyte freeze point measured on 18650 Li-ion CELLS is "
    "transferred to this profile's battery. NASA Glenn: 'At T<200K (-70 C) electrolyte "
    "freezes', 'Cell voltage drops to zero', 'Voltage recovers when warmed above 200K' "
    "(4 of 4 vacuum trials; 3 of 5 at 1 atm in LN2), and the same 200 K is labelled "
    "'Li-Ion Battery Approx. Freeze Temperature' on their Diviner chart (NTRS 20210011101 "
    "slides 7 and 9; NTRS 20210019184 slides 4 and 8); ISRO held three manufacturers' "
    "18650 cells at -160 C for a 14 day lunar night in vacuum and saw no capacity loss "
    "(Nandini et al., J. Energy Storage 17 (2018) 409-416, as quoted by NASA Glenn). No "
    "profile in this catalogue publishes its cell format, chemistry or freeze point, so "
    "the transfer is an assumption in exactly the sense C3's transferred slip anchors are. "
    "Not a rover specification"
)

USABLE_FRACTION_SHAPE_SOURCE: str = (
    "assumption: between the freeze point (0.0) and the profile's declared battery "
    "operating minimum (1.0) the deliverable fraction is interpolated with a power law, "
    "exponent 1.0 by default, which is a straight line. NOTHING sources this shape. The "
    "two endpoints are anchored -- the cold one by NASA Glenn's measurement, the warm one "
    "by the catalogue's own bat_op_min_c, which for LPR-1 and NASA VIPER is 0 C and "
    "therefore coincides with the temperature NASA quotes their 5 420 Wh at ('beginning-of-"
    "life capacity at 0 C') -- but the path between them does not. The research document's "
    "'85 percent at 0 C, 60 percent at -20 C' is deliberately NOT used: it carries no "
    "source, and 85 percent at 0 C would discount for a second time a capacity that is "
    "already quoted at 0 C. Published COTS 18650 discharge curves are convex rather than "
    "straight, so the linear default is more likely optimistic than pessimistic; the "
    "exponent is swept in docs/research/battery_hibernation_report.md rather than tuned. "
    "Not a rover specification"
)

HEATER_SIZING_SOURCE: str = (
    "assumption: the catalogue's published survival-heater power p_heater_w is taken to be "
    "sized to hold the inner temperature at the lower bound of the tightest declared "
    "operating envelope against the coldest surface this model lets the rover stand on "
    "(constants.THERMAL_MIN_TRAVERSABLE_C = -150 C, the traversability gate's own floor). "
    "That single premise fixes the one coefficient the heater law needs -- the product "
    "eps*sigma*A in NASA JSC's Q_rad = eps*sigma*A*(T_obj^4 - T_env^4) (Slusser, Wilcox, "
    "Hernandez, TFAWS23-PT-52 p. 3) -- so no emissivity and no area is ever invented "
    "separately; only their product is read, and it is read out of a number the catalogue "
    "publishes. What is NOT sourced is the premise: no profile states a heater sizing "
    "case, and p_heater_w equals p_shadow_w - p_idle_w in all four profiles, which is a "
    "bookkeeping identity rather than a thermal design point. The implied areas are small "
    "(0.08 m^2 for LPR-1 at emissivity 1), which says the catalogue's heater is a "
    "keep-alive trickle rather than a lunar-night survival heater -- consistent with NASA "
    "JSC finding that a 500 kg vehicle needed >400 kg of battery to survive a night. "
    "Not a rover specification"
)

HIBERNATION_POWER_SOURCE: str = (
    "assumption: the catalogue's p_hibernate_w is read as the vehicle's dormant keep-alive "
    "draw. No profile publishes one as a vehicle specification: LPR-1's 108 W comes from "
    "this project's own reference document (docs/archive/lunapath_referans_belgesi_2.md, "
    "'hibernate mod: idle + heater + termal yonetim') and is LARGER than its 65 W shadow "
    "housekeeping, so it is not NASA Glenn's passive hibernation at all -- in that "
    "architecture the loads are shut down and the battery is isolated, and the draw is "
    "essentially zero. This model prices the catalogue's mode, states the difference, and "
    "measures what passive hibernation would give as a counterfactual in the report. "
    "LUVMI-M declares None and therefore has no hibernation here, rather than an invented "
    "one. Not a rover specification"
)

HIBERNATION_ENDURANCE_SOURCE: str = (
    "assumption: h_max_shadow_h is read as an endurance AT SHADOW HOUSEKEEPING POWER, so a "
    "dormant state at p_hibernate_w spends the same budget at the rate "
    "p_hibernate_w / p_shadow_w. The catalogue states h_max_shadow_h as a bare scalar and "
    "publishes no hibernation endurance, so this re-reading is ours. It is chosen over the "
    "alternative -- stopping the clock during hibernation -- because stopping it makes "
    "metrics.max_continuous_shadow_h stop meaning continuous darkness and lets D3's LP-R01 "
    "('shadow_continuous_h <= h_max_shadow_h') pass on a number nobody measured: on this "
    "catalogue a stopped clock would turn Yutu-2's 2 h endurance into 210 h. Not a rover "
    "specification"
)

#: How far the cited evidence actually reaches. A hibernation colder or longer
#: than this is still planned, but the response says it has left the evidence.
HIBERNATION_EVIDENCE_LIMIT: dict[str, Any] = {
    "coldest_cited_k": 80.0,
    "coldest_cited_c": 80.0 - 273.15,
    "longest_cited_h": 14.0 * 24.0,
    "note": (
        "NASA Glenn cold-soaked cells to 80 K (-193 C) overnight at 1 atm and held them "
        "near 100 K in vacuum; ISRO held cells at -160 C for 14 days. Colder or longer "
        "than this is outside everything either source measured"
    ),
}


# ── the deliverable fraction ────────────────────────────────────────────────


def battery_rating_c(rover: Mapping[str, Any]) -> float | None:
    """The temperature at and above which ``e_cap_wh`` is taken to be the full
    capacity: the profile's own declared battery operating minimum.

    No new catalogue field is invented for this. ``bat_op_min_c`` already says
    "the coldest temperature at which this vehicle claims to operate its
    battery", and for LPR-1 and NASA VIPER it is 0 C -- exactly the
    temperature NASA quotes their 5 420 Wh at ("beginning-of-life capacity at
    0 C"). The catalogue and the source point at the same place independently,
    which is the strongest anchor available here.
    """
    value = rover.get("bat_op_min_c")
    return None if value is None else float(value)


def usable_fraction_unavailable_reason(rover: Mapping[str, Any]) -> str | None:
    """Why no deliverable fraction can be computed for *rover*, or None.

    LUVMI-M declares ``bat_op_min_c = -100 C``, 27 K BELOW the temperature the
    cited measurement puts the electrolyte's freeze point at. The two anchors
    cross and the curve is not defined. Rather than invent a rating point for
    it -- the same sin the research document's unsourced "85 percent" commits
    -- the model refuses, exactly as C6 refuses a dwell for the same profile's
    missing ``thermal_tau_s``.
    """
    rating = battery_rating_c(rover)
    if rating is None:
        return (
            "rover declares no bat_op_min_c: there is no temperature at which its "
            "capacity is claimed to be the catalogue's e_cap_wh"
        )
    if rating <= BATTERY_FREEZE_C:
        return (
            f"rover declares a battery operating minimum of {rating:g} C, at or below the "
            f"{BATTERY_FREEZE_C:.2f} C ({BATTERY_FREEZE_K:g} K) electrolyte freeze point the "
            "cited measurement reports; the declared operating range and the cited freeze "
            "point cannot both hold, and no rating temperature is invented to reconcile them"
        )
    return None


def usable_fraction(
    inner_c: float, rover: Mapping[str, Any], exponent: float = 1.0
) -> float | None:
    """Fraction of STORED charge the pack delivers at inner temperature *inner_c*.

    1.0 at and above :func:`battery_rating_c`, 0.0 at and below
    :data:`BATTERY_FREEZE_C`, and ``((T - freeze) / (rating - freeze)) **
    exponent`` in between -- a straight line at the default exponent 1.0.
    ``None`` when the profile's own anchors contradict each other
    (:func:`usable_fraction_unavailable_reason`).

    The two endpoints are anchored and the path between them is not; see
    :data:`USABLE_FRACTION_SHAPE_SOURCE` for why, and why the research
    document's "85 percent at 0 C" is not used.
    """
    if usable_fraction_unavailable_reason(rover) is not None:
        return None
    rating = float(battery_rating_c(rover))  # not None past the guard
    value = float(inner_c)
    if value >= rating:
        return 1.0
    if value <= BATTERY_FREEZE_C:
        return 0.0
    span = rating - BATTERY_FREEZE_C
    return float(((value - BATTERY_FREEZE_C) / span) ** max(1e-6, float(exponent)))


def usable_fraction_grid(
    inner_c: np.ndarray, rover: Mapping[str, Any], exponent: float = 1.0
) -> np.ndarray | None:
    """Array form of :func:`usable_fraction`, same anchors and same shape."""
    if usable_fraction_unavailable_reason(rover) is not None:
        return None
    rating = float(battery_rating_c(rover))
    values = np.asarray(inner_c, dtype=np.float64)
    span = rating - BATTERY_FREEZE_C
    scaled = np.clip((values - BATTERY_FREEZE_C) / span, 0.0, 1.0)
    return np.power(scaled, max(1e-6, float(exponent)))


def deliverable_wh(
    stored_wh: float,
    inner_c: float,
    rover: Mapping[str, Any],
    exponent: float = 1.0,
) -> float:
    """Stored charge seen as DELIVERABLE charge at *inner_c*.

    This is the one place the derating enters a state, and what it converts is
    named on purpose. ``stored_wh`` is chemical energy in the pack and does not
    change with temperature; what changes is how much of it comes back out.
    The reserve is a DELIVERABLE-energy floor -- "the energy kept for survival
    heating" (``safety_monitor``) -- so in the cold the STORED charge needed to
    meet it goes up. That is one hedge against cold, applied once.

    Deliberately NOT derated, and stated rather than left implicit: the charge
    ceiling stays ``e_cap_wh`` (cold Li-ion charging is more constrained than
    discharging, and neither the catalogue nor the cited sources give a number
    for it), the cost grid's normalisation scale stays nominal, and the
    planner's battery dominance bin stays nominal.
    """
    fraction = usable_fraction(inner_c, rover, exponent)
    if fraction is None:
        return float(stored_wh)
    return float(stored_wh) * fraction


# ── the heater ──────────────────────────────────────────────────────────────


class HeaterCoefficients:
    """The one coefficient each heater law needs, read from the catalogue.

    ``k_a`` is the linear conductance the research document asked for (W/K);
    ``es_a`` is the product ``eps * sigma * A`` in NASA JSC's Stefan-Boltzmann
    law (W/K^4). Neither emissivity nor area is ever known separately and
    neither is invented: only the product is, and it is read out of
    ``p_heater_w`` under :data:`HEATER_SIZING_SOURCE`.
    """

    __slots__ = ("k_a", "es_a", "set_point_c", "sizing_surface_c", "p_max_w", "component")

    def __init__(
        self,
        k_a: float,
        es_a: float,
        set_point_c: float,
        sizing_surface_c: float,
        p_max_w: float,
        component: str,
    ) -> None:
        self.k_a = k_a
        self.es_a = es_a
        self.set_point_c = set_point_c
        self.sizing_surface_c = sizing_surface_c
        self.p_max_w = p_max_w
        self.component = component

    def as_dict(self) -> dict[str, Any]:
        return {
            "k_a_w_per_k": self.k_a,
            "es_a_w_per_k4": self.es_a,
            "implied_area_m2_at_emissivity_1": self.es_a / STEFAN_BOLTZMANN,
            "set_point_c": self.set_point_c,
            "set_point_component": self.component,
            "sizing_surface_c": self.sizing_surface_c,
            "p_heater_w": self.p_max_w,
            "source": HEATER_SIZING_SOURCE,
        }


def heater_unavailable_reason(rover: Mapping[str, Any]) -> str | None:
    """Why no heater coefficient can be calibrated for *rover*, or None."""
    if rover.get("p_heater_w") is None or not float(rover["p_heater_w"]) > 0.0:
        return "rover declares no p_heater_w: there is no published power to calibrate against"
    if rover_envelope(rover) is None:
        return "rover declares no thermal envelope (bat_op_*/elec_op_*): the heater has no set point"
    env = rover_envelope(rover)
    if env is not None and env.lo <= C.THERMAL_MIN_TRAVERSABLE_C:
        return (
            f"rover's envelope floor {env.lo:g} C is at or below the coldest traversable "
            f"surface {C.THERMAL_MIN_TRAVERSABLE_C:g} C: the sizing case is degenerate"
        )
    return None


def heater_coefficients(rover: Mapping[str, Any]) -> HeaterCoefficients | None:
    """Calibrate ``kA`` and ``esA`` from the catalogue, or None.

    The sizing premise is :data:`HEATER_SIZING_SOURCE`: ``p_heater_w`` exactly
    holds the envelope's lower bound against a ``THERMAL_MIN_TRAVERSABLE_C``
    surface. Both laws therefore agree at that one point by construction and
    diverge everywhere else, which is what makes comparing them meaningful.

    The environment is the SURFACE temperature, not the offset-mapped inner
    target. That is deliberate and it is the difference between a working model
    and a broken one: ``cost_engine.surface_to_inner`` is piecewise on the SIGN
    of the surface and jumps by ``offset_cold - offset_hot`` (100 K for LPR-1)
    across zero, so a heater driven off the inner target turns ON as the ground
    gets WARMER -- measured for LPR-1: 0 W at a -0.1 C surface and 11.1 W at
    +0.1 C. C6 is unharmed by that map because ``apply_heater`` only ever
    CLAMPS a temperature and clamping is monotone-safe; turning the same
    non-monotone target into a POWER is not. NASA JSC's ``T_env`` is the
    environment, and the environment is the surface.
    """
    if heater_unavailable_reason(rover) is not None:
        return None
    env = rover_envelope(rover)
    assert env is not None  # guarded above
    p_max = float(rover["p_heater_w"])
    set_point = float(env.lo)
    sizing_surface = float(C.THERMAL_MIN_TRAVERSABLE_C)
    k_a = p_max / (set_point - sizing_surface)
    set_k = set_point + 273.15
    sizing_k = sizing_surface + 273.15
    es_a = p_max / (set_k**4 - sizing_k**4)
    return HeaterCoefficients(k_a, es_a, set_point, sizing_surface, p_max, env.lo_component)


def heater_power_w(
    surface_c: float, rover: Mapping[str, Any], model: str = "radiative"
) -> float:
    """Survival-heater power at a *surface_c* environment, in watts.

    ``delta_t`` is the linear law the research document asked for; ``radiative``
    is the Stefan-Boltzmann law that document's own cited source writes down
    (NASA JSC: "the temperature of the object is weighted to the 4th power").
    Both are clipped to ``[0, p_heater_w]`` -- the catalogue's heater cannot
    draw more than it has, and it does not run at all once the environment is
    at or above the set point.

    ``constant`` is not handled here: it is not a function of temperature at
    all, and ``cost_engine.housekeeping_power_w`` keeps computing it from the
    shadow ratio exactly as it did before C2.
    """
    if model not in HEATER_POWER_MODELS:
        raise ValueError(f"unknown heater_power_model {model!r}; expected one of {HEATER_POWER_MODELS}")
    if model == "constant":
        raise ValueError(
            "heater_power_model='constant' is the pre-C2 exposure term, not a temperature "
            "law; cost_engine.housekeeping_power_w computes it"
        )
    coefficients = heater_coefficients(rover)
    if coefficients is None:
        raise ValueError(heater_unavailable_reason(rover) or "no heater coefficients")
    surface = float(surface_c)
    if not math.isfinite(surface):
        return 0.0
    if model == "delta_t":
        raw = coefficients.k_a * (coefficients.set_point_c - surface)
    else:
        set_k = coefficients.set_point_c + 273.15
        env_k = max(0.0, surface + 273.15)
        raw = coefficients.es_a * (set_k**4 - env_k**4)
    return float(min(coefficients.p_max_w, max(0.0, raw)))


def heater_power_w_grid(
    surface_c: np.ndarray, rover: Mapping[str, Any], model: str = "radiative"
) -> np.ndarray:
    """Array form of :func:`heater_power_w`, same clip and same coefficients."""
    if model not in HEATER_POWER_MODELS or model == "constant":
        raise ValueError(
            f"heater_power_w_grid needs a temperature law, not {model!r}; "
            f"expected one of {HEATER_POWER_MODELS[1:]}"
        )
    coefficients = heater_coefficients(rover)
    if coefficients is None:
        raise ValueError(heater_unavailable_reason(rover) or "no heater coefficients")
    surface = np.asarray(surface_c, dtype=np.float64)
    if model == "delta_t":
        raw = coefficients.k_a * (coefficients.set_point_c - surface)
    else:
        set_k = coefficients.set_point_c + 273.15
        env_k = np.maximum(0.0, surface + 273.15)
        raw = coefficients.es_a * (set_k**4 - env_k**4)
    out = np.clip(raw, 0.0, coefficients.p_max_w)
    return np.where(np.isnan(surface), 0.0, out)


def heated_equilibrium_c(
    surface_c: float,
    rover: Mapping[str, Any],
    available_w: float | None = None,
    model: str = "radiative",
) -> float | None:
    """Inner temperature the heater alone can hold against a *surface_c* environment.

    The inverse of :func:`heater_power_w`: given the power actually available
    (``p_heater_w`` by default, less when the array cannot supply it), the
    temperature at which output balances loss. At the sizing surface with full
    power this returns the set point exactly, by construction, under both laws.
    """
    coefficients = heater_coefficients(rover)
    if coefficients is None:
        return None
    power = coefficients.p_max_w if available_w is None else max(0.0, float(available_w))
    surface = float(surface_c)
    if not math.isfinite(surface):
        return None
    if model == "delta_t":
        if coefficients.k_a <= 0.0:
            return None
        return surface + power / coefficients.k_a
    env_k = max(0.0, surface + 273.15)
    if coefficients.es_a <= 0.0:
        return None
    return float((env_k**4 + power / coefficients.es_a) ** 0.25 - 273.15)


def jsc_survival_temperature_check() -> dict[str, Any]:
    """Reproduce NASA JSC's published 26 percent from their own law.

    JSC: "Decreasing a component's survival temperature from 270K to 250K, for
    example, decreases heater power requirements by 26%". Under
    ``Q = esA (T^4 - T_env^4)`` the reduction is ``1 - (250^4 - T_env^4) /
    (270^4 - T_env^4)``, which is 26.50 percent for any environment near the
    polar floor. The coefficient cancels, so this checks the LAW rather than
    our calibration of it.

    This is the same kind of cross-check as C1's ``panel.viper_corner_check``:
    a published number reproduced with our formula, with the difference stated.
    It is NOT a measurement of ours, and the 26 percent is not ours either.
    """
    hot_k = float(JSC_QUOTED["survival_temperature_from_k"])
    cold_k = float(JSC_QUOTED["survival_temperature_to_k"])
    rows: list[dict[str, float]] = []
    for env_k in (0.0, JSC_QUOTED["psr_floor_k"], 40.0, 100.0):
        env = float(env_k)
        predicted = 100.0 * (1.0 - (cold_k**4 - env**4) / (hot_k**4 - env**4))
        rows.append({"t_env_k": env, "predicted_reduction_pct": predicted})
    at_psr = next(r for r in rows if r["t_env_k"] == float(JSC_QUOTED["psr_floor_k"]))
    quoted = float(JSC_QUOTED["survival_temperature_reduction_pct"])
    return {
        "quoted_pct": quoted,
        "quoted_text": JSC_QUOTED["survival_temperature_quote"],
        "predicted_pct": at_psr["predicted_reduction_pct"],
        "difference_pct_points": at_psr["predicted_reduction_pct"] - quoted,
        "by_environment": rows,
        "note": (
            "JSC's figure is theirs; the prediction is the Stefan-Boltzmann law they "
            "themselves write down, evaluated at their own quoted PSR floor. The heater "
            "coefficient cancels, so this tests the law, not our calibration of it"
        ),
    }


# ── the dark endurance ──────────────────────────────────────────────────────


def shadow_endurance_h(
    stored_wh: float,
    inner_c: float,
    rover: Mapping[str, Any],
    exponent: float = 1.0,
) -> float:
    """The rover's continuous-darkness endurance FROM THIS STATE, in hours.

    The published ``h_max_shadow_h`` scaled by the fraction of the deliverable
    charge above the reserve this state still has::

        h(charge, T) = h_published * clamp01( max(0, charge*f(T) - reserve)
                                              / (e_cap - reserve) )

    At full charge and at the rating temperature the numerator and the
    denominator are the same number, the ratio is exactly 1.0, and the result
    is the published constant -- for every profile in the catalogue, bit for
    bit. That is the whole reason this is a RATIO and not
    ``min(published, derived)``.

    The ``min`` form was tried first and withdrawn. Measured on this catalogue,
    ``(e_cap - reserve) / p_shadow_w`` is 66.71 h for LPR-1, 22.40 h for
    LUVMI-M and 17.50 h for Yutu-2 -- all above their published endurances, so
    ``min`` would be the identity -- but 33.35 h for NASA VIPER, BELOW its
    published 50 h. VIPER's catalogue is internally inconsistent: 50 h at
    130 W is 6 500 Wh against a 5 420 Wh pack. The explanation is that NASA's
    50 h is a MIN-POWER mode while ``p_shadow_w`` is the normal shadow draw --
    two different modes, two different numbers. Under ``min`` that
    inconsistency would silently cut VIPER's endurance by a third the moment
    the flag was set. It is reported in
    docs/research/battery_hibernation_report.md instead, and the catalogue is
    left alone.
    """
    published = float(rover.get("h_max_shadow_h") or 0.0)
    if not math.isfinite(published) or published <= 0.0:
        return published
    e_cap = float(rover["e_cap_wh"])
    reserve = e_cap * float(rover.get("soc_min_pct") or 0.0)
    span = e_cap - reserve
    if span <= 0.0:
        return 0.0
    above = max(0.0, deliverable_wh(stored_wh, inner_c, rover, exponent) - reserve)
    return published * min(1.0, above / span)


# ── hibernation ─────────────────────────────────────────────────────────────


def hibernation_unavailable_reason(rover: Mapping[str, Any]) -> str | None:
    """Why *rover* cannot hibernate in this model, or None when it can."""
    if rover.get("p_hibernate_w") is None:
        return (
            "rover declares no p_hibernate_w: hibernation is undefined for this profile and "
            "no draw is invented for it"
        )
    if rover.get("thermal_tau_s") is None or not float(rover["thermal_tau_s"]) > 0.0:
        return (
            "rover declares no thermal_tau_s: the dawn pre-heat cannot be timed (no regolith "
            "constant is substituted for the vehicle's)"
        )
    if rover_envelope(rover) is None:
        return "rover declares no thermal envelope (bat_op_*/elec_op_*)"
    reason = usable_fraction_unavailable_reason(rover)
    if reason is not None:
        return f"hibernation needs the cold-capacity curve, which is unavailable: {reason}"
    return heater_unavailable_reason(rover)


def hibernation_available(rover: Mapping[str, Any]) -> tuple[bool, str | None]:
    """``(available, reason)`` -- reason is None exactly when available."""
    reason = hibernation_unavailable_reason(rover)
    return (reason is None, reason)


def hibernate_dark_rate(rover: Mapping[str, Any]) -> float:
    """How fast a dormant hour spends the continuous-darkness budget.

    ``p_hibernate_w / p_shadow_w``: ``h_max_shadow_h`` is read as an endurance
    AT SHADOW HOUSEKEEPING POWER (:data:`HIBERNATION_ENDURANCE_SOURCE`), so a
    state that draws a different power spends the same budget at a different
    rate. Measured on this catalogue: LPR-1 1.662 (its "hibernation" costs MORE
    than running its heaters), NASA VIPER 0.769, Yutu-2 0.083.

    The alternative -- stopping the clock -- was rejected. It would make
    ``metrics.max_continuous_shadow_h`` stop meaning continuous darkness, let
    D3's LP-R01 pass on a number nobody measured, and turn Yutu-2's 2 h
    endurance into 210 h of dormancy against a constraint that no longer binds.
    """
    hibernate_w = rover.get("p_hibernate_w")
    if hibernate_w is None:
        return 1.0
    shadow_w = rover.get("p_shadow_w")
    if shadow_w is None:
        shadow_w = float(rover["p_idle_w"]) + float(rover.get("p_heater_w") or 0.0)
    shadow_w = float(shadow_w)
    if shadow_w <= 0.0:
        return 1.0
    return float(hibernate_w) / shadow_w


def survival_envelope(rover: Mapping[str, Any]) -> Envelope | None:
    """The envelope that binds a HIBERNATING rover, wider than the operating one.

    An operating bound and a survival bound are different things and C2 never
    uses one for the other. While the rover is driving or waiting, the tightest
    declared OPERATING envelope binds (``thermal_dwell.rover_envelope``). While
    it is dormant, the binding cold limit is the cited SURVIVAL floor -- the
    200 K freeze point, below which the pack delivers nothing. The hot end is
    unchanged: nothing in either source says a dormant rover may overheat.

    Wider is not unbounded. This is why hibernation does not "suspend" the
    thermal constraint: suspending it would reopen, in a new costume, exactly
    the loophole C6 closed by constraining the temperature rather than the stay.
    """
    env = rover_envelope(rover)
    if env is None:
        return None
    return Envelope(
        lo=BATTERY_FREEZE_C,
        hi=env.hi,
        lo_component="battery",
        hi_component=env.hi_component,
    )


def components_past_operating_limit(inner_c: float, rover: Mapping[str, Any]) -> list[str]:
    """Which declared operating minima a hibernating *inner_c* has gone below.

    NASA Glenn's evidence is about CELLS; NASA JSC's caution is about
    AVIONICS. When a hibernation takes the rover below its electronics
    minimum as well as its battery minimum, the response says so rather than
    reporting one envelope and letting the reader assume the other was met.
    """
    crossed: list[str] = []
    for name, key in (("battery", "bat_op_min_c"), ("electronics", "elec_op_min_c")):
        low = rover.get(key)
        if low is not None and float(inner_c) < float(low):
            crossed.append(name)
    return crossed


def dawn_preheat(
    inner_c: float,
    surface_c: float,
    solar_w: float,
    rover: Mapping[str, Any],
    model: str = "radiative",
) -> tuple[float | None, float | None, str | None]:
    """``(hours, exit_inner_c, reason)`` for waking out of hibernation.

    NASA Glenn's dawn mode, as they describe it: "Solar Array output triggers a
    'Dawn Mode' within the Main Bus Controller", "MBC in Dawn Mode operates on
    Solar Array power alone (Battery still Isolated)", "MBC manages thermal
    conditioning (Pre-Heaters) for battery and avionics", "On reaching safe
    temperatures BMS performs battery pre-charge".

    Three consequences the model takes straight from that description:

    * the pre-heat costs TIME and SOLAR income, not battery charge -- the pack
      is isolated, so it neither drains nor charges while warming;
    * the power available is what the ARRAY delivers at that moment, capped by
      the published heater power (the only heater sizing the catalogue gives);
    * waking needs light. A rover cannot pre-heat in the dark, which is why the
      planner may only leave hibernation into an illuminated slice.

    The time is the warming branch of the same first-order lag
    ``thermal_dwell.exit_time_h`` already solves, in HOURS::

        t = tau_s * ln((T_eq - T_hib) / (T_eq - T_lo)) / 3600

    When ``T_eq <= T_lo`` the heater is saturated and the rover can never reach
    its operating envelope in that cell: the logarithm's argument is not
    positive and the honest answer is a refusal with a reason, not a NaN and
    not an infinity quietly dropped by a heap comparison. At the sizing surface
    exactly, ``T_eq == T_lo`` and the approach is asymptotic -- so the model
    refuses to hibernate in the very coldest cells it admits, which is the
    conservative direction.
    """
    reason = hibernation_unavailable_reason(rover)
    if reason is not None:
        return None, None, reason
    env = rover_envelope(rover)
    coefficients = heater_coefficients(rover)
    assert env is not None and coefficients is not None  # guarded above
    available_w = min(coefficients.p_max_w, max(0.0, float(solar_w)))
    if available_w <= 0.0:
        return None, None, (
            "no array power at this slice: NASA Glenn's dawn mode runs the pre-heaters on "
            "solar array power alone, so a rover cannot wake in the dark"
        )
    equilibrium = heated_equilibrium_c(surface_c, rover, available_w, model)
    if equilibrium is None or not math.isfinite(equilibrium):
        return None, None, "the heated equilibrium temperature could not be computed"
    target_c = float(env.lo)
    start_c = float(inner_c)
    if start_c >= target_c:
        return 0.0, start_c, None
    if equilibrium <= target_c:
        return None, None, (
            f"the heater saturates at {available_w:.1f} W against a {float(surface_c):.1f} C "
            f"surface and settles at {equilibrium:.1f} C, at or below the {target_c:g} C "
            "envelope floor: the rover could not be warmed back into its operating envelope "
            "here, so it must not hibernate here"
        )
    tau_s = float(rover["thermal_tau_s"])
    hours = tau_s * math.log((equilibrium - start_c) / (equilibrium - target_c)) / 3600.0
    return float(hours), target_c, None


def hibernation_beyond_evidence(
    coldest_inner_c: float, hours: float
) -> tuple[bool, str | None]:
    """Whether a hibernation has left the range either source actually measured."""
    limits = HIBERNATION_EVIDENCE_LIMIT
    notes: list[str] = []
    if float(coldest_inner_c) < float(limits["coldest_cited_c"]):
        notes.append(
            f"{float(coldest_inner_c):.1f} C is colder than the {float(limits['coldest_cited_c']):.1f} C "
            "(80 K) coldest cold soak NASA Glenn reports"
        )
    if float(hours) > float(limits["longest_cited_h"]):
        notes.append(
            f"{float(hours):.1f} h is longer than the {float(limits['longest_cited_h']):.0f} h "
            "(14 day) hold ISRO reports"
        )
    if not notes:
        return False, None
    return True, "; ".join(notes) + " -- outside the cited evidence, planned but not supported by it"


# ── the response blocks ─────────────────────────────────────────────────────


def rover_battery_block(rover: Mapping[str, Any] | None) -> dict[str, Any]:
    """The ``battery_model`` block ``constants.rover_catalog`` publishes.

    Says, per profile, whether each of the three models can be applied at all
    and why not when it cannot -- so a reader comparing profiles sees that
    LUVMI-M has no cold curve, no hibernation and no dwell, rather than seeing
    numbers invented to fill the gaps.
    """
    if rover is None:
        return {"available": False, "reason": "no rover"}
    coefficients = heater_coefficients(rover)
    hibernate_ok, hibernate_reason = hibernation_available(rover)
    fraction_reason = usable_fraction_unavailable_reason(rover)
    rating = battery_rating_c(rover)
    return {
        "model_id": BATTERY_MODEL_ID,
        "validity": BATTERY_VALIDITY,
        "cold_capacity": {
            "available": fraction_reason is None,
            "reason": fraction_reason,
            "rating_c": rating,
            "freeze_c": BATTERY_FREEZE_C,
            "freeze_k": BATTERY_FREEZE_K,
            "freeze_source": BATTERY_FREEZE_SOURCE,
            "shape_source": USABLE_FRACTION_SHAPE_SOURCE,
        },
        "heater": (
            {"available": False, "reason": heater_unavailable_reason(rover)}
            if coefficients is None
            else {"available": True, "reason": None, **coefficients.as_dict()}
        ),
        "hibernation": {
            "available": hibernate_ok,
            "reason": hibernate_reason,
            "p_hibernate_w": rover.get("p_hibernate_w"),
            "dark_rate": None if not hibernate_ok else hibernate_dark_rate(rover),
            "power_source": HIBERNATION_POWER_SOURCE,
            "endurance_source": HIBERNATION_ENDURANCE_SOURCE,
            "evidence_limit": dict(HIBERNATION_EVIDENCE_LIMIT),
        },
        "published_shadow_endurance_h": float(rover["h_max_shadow_h"]),
    }


def battery_block(
    rover: Mapping[str, Any] | None,
    battery_model: str,
    heater_power_model: str,
    allow_hibernate: bool,
    applied: bool,
    reason: str | None = None,
    exponent: float = 1.0,
    route: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``battery`` block every C2-aware response carries.

    Always reported; ``applied`` is true only when the caller asked for a model
    that is not the pre-C2 one AND it could actually be applied -- the same
    ``bool(requested and artefact is not None)`` rule A1, A2, B1, C6 and C1 use.
    """
    requested = (
        battery_model != "constant"
        or heater_power_model != "constant"
        or bool(allow_hibernate)
    )
    block: dict[str, Any] = {
        "model_id": BATTERY_MODEL_ID,
        "validity": BATTERY_VALIDITY,
        "scope": BATTERY_SCOPE,
        "claim": BATTERY_CLAIM,
        "requested": {
            "battery_model": battery_model,
            "heater_power_model": heater_power_model,
            "allow_hibernate": bool(allow_hibernate),
        },
        "applied": bool(requested and applied),
        "reason": reason,
        "shape_exponent": float(exponent),
        "catalogue": rover_battery_block(rover),
        "jsc_survival_temperature_check": jsc_survival_temperature_check(),
        "nasa_glenn_quoted": dict(NASA_GLENN_QUOTED),
        "jsc_quoted": dict(JSC_QUOTED),
        "viper_quoted": dict(VIPER_QUOTED),
        "references": [dict(reference) for reference in BATTERY_REFERENCES],
    }
    block["route"] = None if route is None else dict(route)
    return block
