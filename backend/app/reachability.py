"""Energy-reachability isochrones: where can this rover still get to (D6)?

``/api/plan-4d`` answers "can I get from A to B". The operator's question
before that one is "where can I get AT ALL, from here, now, on this charge"
-- and, because the shadow moves, "and where could I get if I left in six
hours instead". That is a REACHABILITY problem, not a shortest-path one, and
the difference is not cosmetic.

Why this is not Dijkstra
------------------------
The 12-factor research note proposed "multi-source Dijkstra over the cost
cube (energy budgeted)". That does not work in this repo, and the reason is
measured rather than argued:

* ``cost_engine.move_battery_drain_wh`` is SIGNED. Its own docstring says so:
  "Positive drains, negative charges ... NOT floored at zero". On a flat, lit
  cell LPR-1's array outproduces the drive by 0.245 Wh per metre, and the
  break-even shadow ratio is 0.3908 (NASA VIPER 0.2400).
* On Site11 at coarsen 4 that is not a corner case. At epoch
  2026-09-05T00:00:00, over 48 slices and eight directions, 1 080 811 of
  3 734 496 drive edges are negative (28.94 %, worst -5.735 Wh) and 295 017
  of 547 296 wait edges are (53.9 %). At a fully dark epoch (2026-09-01) the
  count is exactly zero -- which is the trap: a Dijkstra would look correct
  on the epoch the test suite happens to use and be silently wrong on the
  next one.

The other floored twin, ``cost_engine.net_energy_per_metre_wh``, is
``max(0, ...)``. Using it here would make every drive cost the battery
something, i.e. "you can never gain range by driving in sunlight" -- false in
this very energy model, and wrong in one direction only, which is the worst
kind of conservative.

That a label-setting shortest-path algorithm is unsound on negative edges is
an ordinary fact about Dijkstra, and it is OURS to assert, not Tompkins'.
What Tompkins (CMU 2005, TEMPEST) -- the method source the research note
cites -- contributes is the FORMULATION: section 3.1.5 classes RECHARGEABLE
battery energy as a NON-MONOTONIC RESOURCE PARAMETER, a state variable (a
DPARM), not a cost; and his saturation rule ``e_{i+1} = max(e_i + de,
e_min)`` with rejection when ``e_{i+1} > e_max`` is the backward-search
mirror of what ``pathfinder_4d.astar_4d`` already does forward,
``min(e_cap_wh, battery_wh - drain_wh)`` with a reserve floor. His section
3.1.7 warning -- "Non-monotonic parameters cannot be optimized directly using
the incremental search approach. ... In cases where negative cost arcs are
consistently reachable, the search will never terminate" -- is about his own
incremental, D*-like heuristic search, NOT about Dijkstra's label-setting
optimality, and it is not quoted here as though it were.

Read first-hand on 16 September 2026, from the published PDF: TEMPEST's
search is ISE, "similar to A*" with D*-style incremental repair, and the
string "Dijkstra" does not occur once in the 192-page thesis. That is a
measurement of the DOCUMENT, not a number of Tompkins' and not a number of
ours; it lives in ``REACHABILITY_CORRECTIONS`` rather than in the quoted
table or in any measurement table.

So charge is a STATE. This module carries it as one.

What is computed
----------------
A forward sweep over the TIME-EXPANDED coarse grid -- the planner's own grid,
its own edges, its own slice clock. Two fields per ``(slice, block)``:

``best_soc_wh``  the MAXIMUM battery charge reachable there at that slice;
``min_dark_h``   the MINIMUM continuous-darkness hours reachable there then.

A ``(slice, block)`` is LIVE when the first is at or above the reserve and
the second at or below the endurance -- the two envelope rules
``astar_4d.envelope_after`` enforces. Propagation runs only from live states,
sweeping slices in increasing order.

Two properties, and the whole design rests on them:

**Exactness, per field.** Every edge advances the clock by at least one slice
(``dt = max(1, ceil(travel_h / slice_hours))`` for a move, exactly one for a
wait), so the time-expanded graph is a DAG ordered by slice. The transfer
``b -> min(cap, b - drain)`` is non-decreasing in ``b`` and the test
``b' >= reserve`` is monotone in ``b``; the dark transfer is non-decreasing
in the incoming dark hours (the reset to zero is a constant, which is
non-decreasing trivially) and its test is monotone too. A forward sweep in
slice order that keeps the maximum charge and the minimum dark hours is
therefore EXACT for each field -- no priority queue, no charge bins, no
fixed point. The negative edges that break Dijkstra are harmless precisely
because the sweep has no priority order to corrupt.

**Superset, jointly.** The two fields are optimised INDEPENDENTLY: the
charge-maximising predecessor and the dark-minimising predecessor of a block
need not be the same block. The live set is therefore a RELAXATION of the
true set of feasible labels. By induction over slices, for any route the
planner could actually fly, ``best_soc >= its charge`` and
``min_dark <= its dark hours`` at every step, so the relaxed state is live
whenever a true label is. Hence

    the live set CONTAINS what /api/plan-4d would accept, at the same
    coarsen, slice length, epoch and horizon, with every optional
    constraint off.

and the only claim that runs the safe way is the negative one: **a block
outside the set is one this energy model says the rover cannot reach.** A
block inside it is a candidate, not a promise. ``sampled_agreement`` in the
report replays the planner on sampled blocks and measures how often the
relaxation is loose; it is never assumed tight.

That containment is against the planner's DEFAULT CONFIGURATION, and the
distinction is not pedantry. ``astar_4d``'s optional flags split in two:

* CONSTRAINTS (``require_earth_visibility``, ``require_safe_haven``,
  ``require_continuous_illumination``, ``require_thermal_dwell``,
  ``max_failure_probability``) only ever SHRINK what the planner accepts, so
  leaving them off keeps the sweep an upper bound;
* CAPABILITIES (``allow_hibernate``, ``battery_model``,
  ``heater_power_model``, ``panel_model``) can ENLARGE it. A hibernation is
  a third edge family: it drains at ``p_hibernate_w`` instead of
  housekeeping and it resets the continuous-darkness clock to zero on waking
  (``pathfinder_4d`` line 1625). A planner run with ``allow_hibernate=True``
  can therefore legally reach blocks this sweep calls unreachable, and the
  negative claim would be false in the unsafe direction.

So the claim is stated WITH the configuration, the response echoes it, and
the sweep models none of the capabilities.

The planner's charge-recovery exception (``astar_4d`` lets a transition end
below the reserve when it CHARGES, ``new_battery < battery_wh``) would break
the monotone test, so the endpoint refuses a start charge under the rover's
own ``soc_min_pct``. With that refused the exception cannot fire and the two
rules coincide exactly.

What is NOT computed
--------------------
No cost cube, so no weight vector is read and ``astar_4d``'s
``cost_infinite`` gate is not replayed -- reachability under this model is
decided by the hard gates and the battery, and the criterion weights only
price how UNPLEASANT a drive is. That omission is one more reason the set is
a superset, and ``reachable_block`` reports it rather than hiding it.

No contour smoothing and no ``skimage``. The research note proposed
``skimage.measure.find_contours``; scikit-image is not in
``backend/requirements.txt`` and adding a dependency to draw a prettier line
around a block lattice is not a trade this repo makes. Bands are published as
a per-block band index plus the boundary blocks of each band, found with
numpy alone. The boundary of a block mask is a STAIRCASE at
``effective_resolution_m`` and the response says so; smoothing it would draw
a line through terrain the model never evaluated.
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .cost_cube import coarsen_grid
from .survival import OFFSETS, DirectionTables, direction_tables

# ── identity, claim, references ──────────────────────────────────────────────

REACHABILITY_MODEL_ID: str = "time_expanded_energy_reachability_v1"
REACHABILITY_VALIDITY: str = "MODEL"

#: The band ladder used when the caller names none: equal slices of the
#: horizon. Arbitrary, and stated as such -- there is no natural isochrone
#: spacing for a rover whose speed depends on the slope under it.
DEFAULT_BAND_COUNT: int = 6
MAX_BAND_EDGES: int = 12

#: Blocks the sweep will cover. 125 x 125 (coarsen 4 on the production grid)
#: is 15 625; this leaves room for coarsen 2 (62 500) and refuses the fine
#: grid, where a per-block response would be a quarter of a million numbers.
MAX_REACHABLE_BLOCKS: int = 70_000
#: Slices the sweep will run, matching the 4-D planner's own ceiling so a
#: horizon this endpoint accepts is one the planner could also be asked for.
MAX_REACHABLE_SLICES: int = 1_000
#: The rolling charge/dark window plus the coarse shadow cube, in bytes.
MAX_REACHABLE_CUBE_BYTES: int = 512 * 1024 * 1024
#: Boundary blocks published per band before the list is truncated (and the
#: truncation reported).
MAX_BOUNDARY_CELLS: int = 4_000
#: Blocks the planner is replayed on when the caller asks for the agreement
#: probe. Each one is a full 4-D search.
MAX_AGREEMENT_SAMPLES: int = 24

#: Fine snapshots built per call while extending the shadow series. A fine
#: 500 x 500 snapshot is 2 MB, so a long horizon at a short slice must never
#: be materialised at full resolution all at once. Same constant and same
#: reason as ``main._SHADOW_EXTENSION_CHUNK``.
SHADOW_CHUNK_SLICES: int = 64

#: The /api/plan-4d configuration the containment claim is stated against.
#: Echoed on every response: a planner run under a DIFFERENT configuration is
#: not the one this set contains, and hibernation in particular can legally
#: reach blocks the sweep calls unreachable.
PLANNER_CONFIGURATION: dict[str, Any] = {
    "allow_hibernate": False,
    "battery_model": "constant",
    "heater_power_model": "constant",
    "panel_model": "sun_pointed",
    "require_earth_visibility": False,
    "require_safe_haven": False,
    "require_continuous_illumination": False,
    "require_thermal_dwell": False,
    "max_failure_probability": None,
    "risk_alpha": None,
}

#: Which of astar_4d's per-edge rules this sweep actually replays, and which
#: it does not -- with the direction each omission pushes the set, so a
#: reader never has to infer it. Published as a field, not as a footnote.
GATES_REPLAYED: tuple[str, ...] = (
    "passability",
    "corner_cut",
    "step_slope",
    "lateral_slope",
    "travel_time_finite",
    "soc_floor",
    "shadow_endurance",
    "horizon",
)

GATES_NOT_REPLAYED: tuple[dict[str, str], ...] = (
    {
        "gate": "cost_infinite",
        "why": (
            "no cost cube is built: reachability is decided by the hard gates and the "
            "battery, and the criterion weights only price how unpleasant a drive is"
        ),
        "direction": "enlarges the set",
    },
    {
        "gate": "earth_visibility",
        "why": "VIPER's teleoperation rule is off in the configuration claimed against",
        "direction": "enlarges the set",
    },
    {
        "gate": "safe_haven_deadline",
        "why": "VIPER's leg rule is off in the configuration claimed against",
        "direction": "enlarges the set",
    },
    {
        "gate": "continuous_illumination",
        "why": "CMU's corridor rule is off in the configuration claimed against",
        "direction": "enlarges the set",
    },
    {
        "gate": "thermal_dwell",
        "why": "C6's envelope is off in the configuration claimed against",
        "direction": "enlarges the set",
    },
    {
        "gate": "failure_probability",
        "why": "B1's chance constraint is off in the configuration claimed against",
        "direction": "enlarges the set",
    },
)

#: Which way each published field errs. The two headline fields err in
#: OPPOSITE directions -- the set too large, the clock too late -- and they
#: do not cancel, because they point at opposite operational decisions.
CONSERVATISM: dict[str, str] = {
    "reachable": (
        "OPTIMISTIC (too large): the two envelope fields are optimised independently "
        "and six planner gates are not replayed"
    ),
    "earliest_hours": (
        "PESSIMISTIC (too late): a move costs ceil(travel_h / slice_hours) whole "
        "slices, so an arrival is quantised UP by as much as one slice per move -- "
        "the planner's own convention, and the quantum is published as "
        "time.slice_hours"
    ),
    "soc_at_arrival_pct_upper": "OPTIMISTIC: the maximum over predecessors, not a trajectory's charge",
    "best_soc_pct_upper": "OPTIMISTIC: the maximum over predecessors and over slices",
    "hours_to_reserve_upper": "OPTIMISTIC: integrated from the optimistic arrival charge",
    "hours_to_zero_upper": "OPTIMISTIC, and below the reserve this model has no transitions at all",
    "hours_to_endurance_upper": "OPTIMISTIC: integrated from the MINIMUM darkness hours at arrival",
}

#: Corrections to the research note and to our own earlier reading, found by
#: reading the sources first-hand. Not quotes and not measurements of the
#: terrain -- the same slot pareto.py and contrastive.py use for this.
REACHABILITY_CORRECTIONS: tuple[dict[str, str], ...] = (
    {
        "claim": (
            "12-factor research note, D6: '/api/reachable: multi-source Dijkstra "
            "(energy budgeted) over the cost_cube'."
        ),
        "correction": (
            "Dijkstra is unsound here. The battery edge is signed and on Site11 at a "
            "lit epoch 28.94 % of drive edges and 53.9 % of wait edges are negative "
            "(measured; see negative_edges). At a fully dark epoch the count is zero, "
            "which is how such a solver would pass a test suite and be wrong in "
            "operation."
        ),
        "read": "2026-09-16",
    },
    {
        "claim": (
            "The note offers Tompkins (CMU 2005) as the method source for that "
            "Dijkstra."
        ),
        "correction": (
            "The thesis contains no Dijkstra: its search is ISE, 'similar to A*' with "
            "D*-style incremental repair, and the string 'Dijkstra' occurs 0 times in "
            "192 pages. Section 3.1.5 classes rechargeable energy as a non-monotonic "
            "RESOURCE PARAMETER -- a state variable -- which is the opposite of "
            "putting it in the objective. Section 3.1.7's 'the search will never "
            "terminate' is about his own incremental heuristic search, not about "
            "Dijkstra's label-setting optimality, and is not cited here as though it "
            "were."
        ),
        "read": "2026-09-16, publications.ri.cmu.edu PDF, full text",
    },
    {
        "claim": "The note attributes a Fast Marching energy map to Sakayori & Ishigami 2021.",
        "correction": (
            "Unverified. The full text is paywalled (HTTP 403 from tandfonline and "
            "researchgate); the indexed abstract names a power-consumption model "
            "approximated from a dynamic simulation, with solar-array generation taken "
            "into account, and no Fast Marching. D6 cites it for context only and "
            "claims nothing about its algorithm."
        ),
        "read": "2026-09-16, abstract via Semantic Scholar; full text not obtained",
    },
    {
        "claim": (
            "The note describes arXiv 2509.15062 as 'instantaneous power constraint "
            "P_cons <= P_avail (softplus penalty), SCP + NMPC'."
        ),
        "correction": (
            "Confirmed against the paper's HTML: section III-E is 'Smooth Power-Limit "
            "Penalty', the hinge is a softplus, section III-F solves by SCP with "
            "augmented-Lagrangian inequalities and section IV is NMPC tracking. The "
            "note is right. What it does not say is that the paper computes no "
            "reachable set at all, so it is context here rather than method."
        ),
        "read": "2026-09-16, arxiv.org/html/2509.15062v1",
    },
)

REACHABILITY_SCOPE: str = (
    "state (time slice, coarse block); actions: the 4-D planner's eight moves and a "
    "one-slice wait; a state is live when the maximum charge reachable there is at or "
    "above soc_min_pct * e_cap_wh AND the minimum continuous-darkness hours reachable "
    "there is at or below h_max_shadow_h. Energy is cost_engine's, through the "
    "arithmetic astar_4d inlines: traction, housekeeping with the shadow-scaled heater, "
    "solar income at p_solar_w * (1 - exposure). The darkness clock is astar_4d's, and "
    "it is EXPOSURE-WEIGHTED travel hours, not elapsed hours: a block at exposure 0.5 "
    "charges the clock at half speed, so on a driving rover the endurance rule is far "
    "weaker than 'hours in the dark' suggests. NOT state variables here: the thermal "
    "envelope, the panel's cos-i gain, the cold-battery derating, hibernation, Earth "
    "visibility, the safe-haven deadline, the illumination corridor and the fault "
    "model. The constraints among those can only shrink the reachable set; the "
    "CAPABILITIES among them (hibernation above all) can enlarge it, which is why the "
    "containment claim names the planner configuration it holds against."
)

REACHABILITY_CLAIM: str = (
    "MODEL: a forward reachability sweep over a coarsened grid and a coarsened time "
    "axis, under THIS repo's energy model. The two envelope fields are optimised "
    "independently, so the published set is a RELAXATION: it CONTAINS what "
    "/api/plan-4d would accept at the same coarsen, slice length, epoch and horizon "
    "AND under the planner configuration echoed in planner_configuration -- not under "
    "every configuration: allow_hibernate=True adds an edge family that drains at "
    "p_hibernate_w and resets the darkness clock, and a plan using it can legally "
    "reach blocks this set excludes. Within that configuration the only claim that "
    "runs the safe way is the negative one: a block outside the set is one this energy "
    "model says the rover cannot reach. A block inside it is a candidate, and no "
    "single trajectory need realise the charge and darkness published for it -- they "
    "come from different predecessors. The looseness is MEASURED by replaying the "
    "planner on sampled blocks (docs/research/reachability_report.md), never assumed. "
    "Charge is carried as a state and not as a cost because it is non-monotonic on "
    "this terrain -- measured, see negative_edges. Whether the ENERGY rules bind at "
    "all is a property of the horizon, not of the feature: refusals reports how many "
    "transitions each rule actually refused, and energy_binds is false when the answer "
    "is that the frontier was the clock. Isochrones are not a rover capability: slip, "
    "DEM error, the thermal envelope and localisation drift all move this boundary, "
    "every one of them IS modelled elsewhere in this backend, and none of them is "
    "propagated here. No number is published for how much they move it."
)

REACHABILITY_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "tompkins_cmu_2005",
        "title": (
            "Tompkins -- Mission-Directed Path Planning for Planetary Rover "
            "Exploration (CMU-RI-TR-05-20, PhD thesis, 2005; TEMPEST/ISE)"
        ),
        "url": (
            "https://publications.ri.cmu.edu/storage/publications/pub_files/pub4/"
            "tompkins_paul_2005_1/tompkins_paul_2005_1.pdf"
        ),
        "used_for": (
            "METHOD: charge as a non-monotonic RESOURCE PARAMETER carried in the state "
            "(sect. 3.1.5), the saturation rule e_{i+1} = max(e_i + de, e_min) with "
            "rejection above e_max (eq. 3-1/3-2), the warning that a non-monotonic "
            "quantity cannot be optimised directly by incremental search (sect. 3.1.7), "
            "and resolution-equivalence / state dominance as the pruning mechanisms "
            "(sect. 3.2.2-3.2.3). NOT used for: any number, and not for isochrones -- "
            "the thesis computes none."
        ),
    },
    {
        "id": "hu_arxiv_2509_15062",
        "title": (
            "Hu, Guo, Liu, Xu, Qian, Chen, Yuan, Xie -- Energy-Constrained Navigation "
            "for Planetary Rovers under Hybrid RTG-Solar Power (arXiv:2509.15062)"
        ),
        "url": "https://arxiv.org/abs/2509.15062",
        "used_for": (
            "CONTEXT: the instantaneous-power view of energy feasibility "
            "(P_cons <= P_avail through a softplus hinge, SCP with an augmented "
            "Lagrangian, NMPC tracking). A trajectory-optimisation paper, not a "
            "reachability one -- it computes no reachable set -- so nothing here is "
            "an implementation of it. Its numbers are in REACHABILITY_QUOTED."
        ),
    },
    {
        "id": "sakayori_ishigami_2021",
        "title": (
            "Sakayori, Ishigami -- Energy-aware trajectory planning for planetary "
            "rovers (Advanced Robotics 35(21-22), 2021, 1302-1316)"
        ),
        "url": "https://doi.org/10.1080/01691864.2021.1959396",
        "used_for": (
            "CONTEXT ONLY, and with a correction: the research note attributes a Fast "
            "Marching energy map to this paper. The full text is paywalled (HTTP 403) "
            "and could NOT be read here; its abstract names no Fast Marching -- it "
            "describes a power-consumption model approximated from a dynamic "
            "simulation, with solar-array generation taken into account. D6 therefore "
            "does not cite it as a method source and claims nothing about its "
            "algorithm."
        ),
    },
)

#: Other people's numbers. Quoted, never put in the same table as a Site11
#: measurement. Same rule as pareto.PARETO_QUOTED and
#: contrastive.CONTRASTIVE_QUOTED.
REACHABILITY_QUOTED: dict[str, Any] = {
    "tompkins_cmu_2005": {
        "search": (
            "'In an initial search, ISE results are similar to those from A*. ... ISE, "
            "like D*, can repair the search graph in the area of the changes.' "
            "(sect. 3.3) -- verbatim; that the thesis names no Dijkstra is OUR reading "
            "of it and sits in REACHABILITY_CORRECTIONS, not here."
        ),
        "non_monotonic_resources": (
            "'Rechargeable energy, thermal load, available computer memory or "
            "communications bandwidth are all examples of non-monotonic resources.' "
            "(sect. 3.1.5)"
        ),
        "why_not_a_cost": (
            "'Non-monotonic parameters cannot be optimized directly using the "
            "incremental search approach. ... In cases where negative cost arcs are "
            "consistently reachable, the search will never terminate.' (sect. 3.1.7)"
        ),
        "approach_comparison": (
            "Tompkins' own experiment between energy-in-the-state (Approach 1, 4-D "
            "BESTDPARMS) and energy-in-the-objective with the nK correction "
            "(Approach 2, 3-D BESTPCOST), on randomly generated maps with time costs "
            "U(5, 20) and energy costs U(-35, 40): Approach 2 several times faster; "
            "Approach 2 gave a lower mean minimum required charge (16.3 vs 25.9 units) "
            "and a smaller peak requirement (91 vs 99 units); path 158 steps against "
            "272; durations 5150 vs 4864 time units. Pentium 4, 2.99 GHz, 1 GB RAM."
        ),
        "no_reachability_map": (
            "TEMPEST's 'Reachable State Space' (Fig. 4-6b) is a distance-versus-time "
            "wedge bounded by the maximum-speed line -- a scalar goal-arrival time "
            "interval, not a map. Nothing in the thesis is a spatial reachability "
            "product, so the isochrone here is not an implementation of Tompkins."
        ),
        "not_ours": (
            "None of these numbers is a LunaPath measurement and none is comparable "
            "with one: they come from randomly generated cost maps in a toy domain."
        ),
    },
    "hu_arxiv_2509_15062": {
        "peak_power": (
            "'our planner generates trajectories with peak power within 0.55 percent "
            "of the prescribed limit, while existing methods exceed limits by over 17 "
            "percent' -- 198.9 W planned against a 200 W limit; baselines 235.8 W "
            "(17.9 % over) and 234.7 W (17.4 % over); the tracked trajectory reached "
            "202.52 W (1.26 % over)."
        ),
        "not_ours": (
            "Simulation on lunar-like terrain with an RTG-plus-solar hybrid bus. "
            "LunaPath models no RTG and enforces no instantaneous power limit, so "
            "these numbers cannot be compared with anything measured here."
        ),
    },
    "sakayori_ishigami_2021": {
        "result": (
            "'one result indicated that the energy margin could be improved by 4.1 kJ, "
            "13.9 at maximum' (abstract as indexed; the percent sign is missing in the "
            "indexed text and the full text is paywalled, so the unit of 13.9 is NOT "
            "verified here)."
        ),
        "not_ours": "A different rover, a different terrain and a different objective.",
    },
}

#: What this backend DOES model and this sweep does not propagate. Named
#: individually, with where each one lives, because "uncertainty is not
#: modelled" would be false here and would read as a limit of the physics
#: rather than a switch this endpoint leaves off.
UNCERTAINTY_NOT_PROPAGATED: tuple[dict[str, Any], ...] = (
    {
        "source": "wheel slip",
        "modelled_in": "app.slip_model (C3), already inside edge_travel_time_s",
        "not_propagated": "its SPREAD (sigma); the sweep runs at the curve's mean",
        "effect": "travel hours, hence the slice a move lands on and its drain",
        "direction": "a slower tail shrinks the extent",
    },
    {
        "source": "DEM error",
        "modelled_in": "app.uncertainty, NASA's PGDA clone ensemble (B3)",
        "not_propagated": "the clones; one nominal slope grid builds the gates",
        "effect": "the step-slope and cross-slope gates that decide which edges exist",
        "direction": "both ways",
    },
    {
        "source": "battery temperature",
        "modelled_in": "app.battery.deliverable_wh (C2)",
        "not_propagated": "the derating; the sweep is battery_model='constant'",
        "effect": "the reserve floor and the darkness endurance",
        "direction": "a cold battery shrinks the extent",
    },
    {
        "source": "localisation drift",
        "modelled_in": "app.localization, app.localization_budget",
        "not_propagated": "entirely; the start block is taken as known",
        "effect": "which block the rover is actually in when the sweep starts",
        "direction": "both ways",
    },
)

#: Exposure at or above which a slice counts as dark. The planner's own
#: threshold (``pathfinder_4d._DARK_RATIO_THRESHOLD``), repeated here by
#: value so the two cannot drift apart silently -- ``test_reachability``
#: asserts they are equal.
DARK_RATIO_THRESHOLD: float = 0.5

#: astar_4d refuses only when the darkness clock passes the endurance by more
#: than this (``pathfinder_4d`` line 1351). Repeated exactly: without it the
#: sweep would kill at ``h_max + 5e-10`` a state the planner keeps, and the
#: published negative claim would be false at the hairline.
ENDURANCE_SLACK_H: float = 1e-9

#: Ceiling on ``n_slices * (direction, span) groups``, the sweep's real unit
#: of work. The span of a move is ``ceil(travel_h / slice_hours)``, so a
#: caller who pins a very short slice multiplies the group count without
#: changing anything else a validator looks at: at the auto slice Site11 has
#: 14 distinct spans and 92 non-empty groups, at ``slice_hours=1e-4`` it has
#: thousands. Bound the work, not one of its factors.
#:
#: Sized from the measurement, not from a guess: Site11 at coarsen 4, 669
#: slices and 92 groups took 19.0 s, i.e. about 0.31 ms per group-step, so
#: 150 000 is roughly 45 s of one sweep and 90 s with the later-start
#: comparison. At the auto slice the 1 000-slice cap binds first (92 000
#: steps); this one only fires for a pinned slice short enough to multiply
#: the work without changing the answer.
MAX_REACHABLE_GROUP_STEPS: int = 150_000


# ── the shadow cube ──────────────────────────────────────────────────────────


def coarse_shadow_cube(
    base_shadow: np.ndarray,
    metadata: Mapping[str, Any],
    coarsen: int,
    n_slices: int,
    slice_hours: float,
    start_utc: str | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """``(T, H', W')`` block-mean shadow, built in chunks, plus provenance.

    ``illumination_series.build_shadow_series`` returns FINE snapshots, and a
    500 x 500 float64 snapshot is 2 MB: a 300-slice horizon at the auto slice
    length would hold 600 MB of them at once. Built here a chunk at a time
    and coarsened immediately, the peak is one chunk.

    ``main._survival_field_for_plan`` does the same thing inline; it is a loop
    inside a function rather than a function, so it is repeated here rather
    than refactored -- moving it would touch the B1 path, and D6 is meant to
    be pure addition.
    """
    from .illumination_series import build_shadow_series

    base = np.asarray(base_shadow, dtype=np.float64)
    total = int(n_slices)
    chunks: list[np.ndarray] = []
    first_provenance: dict[str, Any] | None = None
    done = 0
    while done < total:
        take = min(SHADOW_CHUNK_SLICES, total - done)
        epoch = start_utc
        if start_utc is not None and done:
            epoch = shift_epoch(start_utc, float(slice_hours) * done)
        series, provenance = build_shadow_series(
            base, dict(metadata), take, float(slice_hours), epoch
        )
        # The FIRST chunk's, always. Later chunks carry their own shifted
        # epoch, and reporting the last one would put the end of the horizon
        # in a field the caller reads as "when this started".
        if first_provenance is None:
            first_provenance = dict(provenance)
        chunks.extend(coarsen_grid(snapshot, coarsen) for snapshot in series)
        if not provenance.get("time_varying"):
            # A static series is the same grid at every slice: fill the rest
            # without re-deriving it, and keep the reason.
            still = total - len(chunks)
            if still > 0:
                chunks.extend([chunks[-1]] * still)
            break
        done += take
    cube = np.stack(chunks[:total], axis=0)
    out = dict(first_provenance or {})
    out["chunks"] = int(math.ceil(total / SHADOW_CHUNK_SLICES)) if out.get("time_varying") else 1
    return cube, out


def shift_epoch(start_utc: str, hours: float) -> str:
    """``start_utc`` advanced by *hours*, in the format the series builder
    parses. The "N hours later" comparison and the chunked cube both need it;
    ``main._shift_utc`` is the same operation on the FastAPI side, and
    ``test_reachability`` checks the two agree."""
    from datetime import datetime, timedelta, timezone

    moment = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (moment + timedelta(hours=float(hours))).strftime("%Y-%m-%dT%H:%M:%S")


# ── the sweep ────────────────────────────────────────────────────────────────


@dataclass
class ReachabilityField:
    """What one sweep found, on the coarse planner grid.

    Every 2-D field is indexed by coarse block. ``first_slice`` is -1 where
    the block was never live, and the float fields carry ``nan`` there.
    """

    #: (H, W) int32: earliest slice the block was live, -1 if never.
    first_slice: np.ndarray
    #: (H, W) float64: charge at that earliest arrival, Wh.
    soc_at_first_wh: np.ndarray
    #: (H, W) float64: continuous-darkness hours at that earliest arrival.
    dark_at_first_h: np.ndarray
    #: (H, W) float64: the best charge reachable at the block at ANY slice.
    best_soc_wh: np.ndarray
    #: (H, W) bool: live at some slice.
    reachable: np.ndarray
    #: (T,) int64: live blocks per slice -- the growth curve.
    live_per_slice: np.ndarray
    #: Bookkeeping.
    n_slices: int
    slice_hours: float
    e_cap_wh: float
    reserve_wh: float
    endurance_h: float
    elapsed_s: float
    #: Edges relaxed, and how many of them charged the battery.
    edges_relaxed: int
    negative_edges: int
    #: How many transitions each rule actually refused. Without this a reader
    #: cannot tell an ENERGY isochrone from a gated distance transform: on a
    #: short horizon with a full battery neither energy rule ever fires and
    #: the frontier is the clock alone.
    refusals: dict[str, int]
    #: ``dt * slice_hours - travel_h`` over the usable edges: the wall-clock a
    #: move occupies but is NOT charged for, because astar_4d charges power
    #: over the edge's own hours and advances the clock in whole slices. The
    #: sweep inherits that convention deliberately; publishing the size of it
    #: is the alternative to hiding it.
    unpaid_idle_mean_h: float
    unpaid_idle_max_h: float
    #: ``(direction, span)`` groups the sweep updated per slice.
    edge_groups: int
    #: Traversable blocks whose exposure at the first slice is strictly
    #: between 0 and 1 -- i.e. blocks where the published exposure is a block
    #: AVERAGE of a binary mask and the rover standing there is really either
    #: lit or not. How much of the frontier was decided by an average.
    partially_lit_first_slice: int

    @property
    def energy_binds(self) -> bool:
        """Did either envelope rule refuse anything at all?

        False means the reachable set is a gated distance transform under
        this horizon and this start charge -- a true statement about the
        request, and one an "energy isochrone" must not leave implicit.
        """
        return bool(self.refusals.get("soc_floor", 0) or self.refusals.get("shadow_endurance", 0))

    @property
    def earliest_hours(self) -> np.ndarray:
        """(H, W) float64: ``first_slice * slice_hours``, ``nan`` if never.

        The slice index IS the clock: a move takes ``ceil(travel / slice)``
        slices, so an arrival is never reported earlier than the planner
        would reach it.
        """
        out = np.where(
            self.first_slice >= 0,
            self.first_slice.astype(np.float64) * float(self.slice_hours),
            np.nan,
        )
        return out


def edge_group_count(tables: DirectionTables, slice_hours: float, n_slices: int) -> int:
    """How many ``(direction, span)`` groups :func:`sweep` would update per slice.

    The sweep's work is ``n_slices`` times this. The span of a move is
    ``ceil(travel_h / slice_hours)``, so a caller who pins a very short slice
    multiplies the group count without changing the answer -- and without
    tripping any cap written in slices, blocks or bytes. Callers bound the
    product with this; the endpoint refuses above
    ``MAX_REACHABLE_GROUP_STEPS``.
    """
    step_h = float(slice_hours)
    total = 0
    for d in range(len(OFFSETS)):
        allowed = np.asarray(tables.allowed[d], dtype=bool)
        travel = np.asarray(tables.travel_h[d], dtype=np.float64)
        finite = allowed & np.isfinite(travel)
        if not finite.any():
            continue
        spans = np.maximum(1, np.ceil(travel[finite] / step_h).astype(np.int64))
        total += int((np.unique(spans) < int(n_slices)).sum())
    return total


def _dark_after(exposure: np.ndarray, dark_h: np.ndarray, hours: np.ndarray | float) -> np.ndarray:
    """The planner's continuous-darkness rule, on arrays.

    ``astar_4d.envelope_after``: the clock advances by ``hours * exposure``
    while the exposure is at or above the threshold and RESETS to zero below
    it. Same threshold, same product, same order.
    """
    return np.where(exposure >= DARK_RATIO_THRESHOLD, dark_h + hours * exposure, 0.0)


def sweep(
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any],
    shadow_cube: np.ndarray,
    slice_hours: float,
    start: tuple[int, int],
    initial_soc_frac: float,
    tables: DirectionTables | None = None,
) -> ReachabilityField:
    """Forward energy-reachability over the time-expanded coarse grid.

    *shadow_cube* is ``(T, H, W)`` block exposure on the SAME grid as
    *traversable* -- the planner's ``shadow`` array, built the same way.
    *start* is a coarse block, *initial_soc_frac* a fraction of ``e_cap_wh``.

    Rolling window, not a cube: a move lands at most ``max(dt)`` slices ahead
    (14 on Site11 at coarsen 4, measured), so only that many slices of charge
    and darkness have to be alive at once. Memory is the shadow cube.

    The per-edge arithmetic is ``astar_4d``'s, in ``astar_4d``'s operation
    order -- ``(traction + (p_idle + e * shadow_extra) - p_solar * (1 - e)) *
    travel_h`` -- not a re-derivation, because a difference in the last ulp
    would let this module call a block reachable on an edge the planner
    rounds the other way. ``test_reachability`` replays the scalar expression
    per edge and requires exact equality.
    """
    started = time.perf_counter()
    passable = np.asarray(traversable, dtype=bool)
    height, width = passable.shape
    shadow = np.asarray(shadow_cube, dtype=np.float64)
    if shadow.ndim != 3 or shadow.shape[1:] != passable.shape:
        raise ValueError(
            f"shadow_cube {shadow.shape} does not match the grid {passable.shape}"
        )
    n_slices = int(shadow.shape[0])
    if n_slices < 2:
        raise ValueError("a reachability sweep needs at least two slices")
    step_h = float(slice_hours)
    if not (step_h > 0.0):
        raise ValueError("slice_hours must be positive")

    if tables is None:
        tables = direction_tables(passable, elevation, slope, resolution_m, rover)

    e_cap_wh = float(rover["e_cap_wh"])
    reserve_wh = e_cap_wh * float(rover.get("soc_min_pct") or 0.0)
    h_max_shadow = float(rover.get("h_max_shadow_h") or math.inf)
    endurance_h = h_max_shadow if math.isfinite(h_max_shadow) and h_max_shadow > 0 else math.inf
    battery0 = min(1.0, max(0.0, float(initial_soc_frac))) * e_cap_wh

    # The power law, in the planner's own terms (pathfinder_4d, lines ~1216).
    p_idle_w = float(rover["p_idle_w"])
    p_shadow_w = rover.get("p_shadow_w")
    shadow_extra_w = (
        max(0.0, float(p_shadow_w) - p_idle_w)
        if p_shadow_w is not None
        else float(rover.get("p_heater_w") or 0.0)
    )
    p_solar_w = float(rover.get("p_solar_w") or 0.0)

    # ── per-direction edge plan, grouped by the number of slices the move
    # spans. dt depends on the terrain alone, so the grouping is computed
    # once and reused at every slice; on Site11 at coarsen 4 there are 14
    # distinct values (measured), so this is ~112 vectorised updates per
    # slice rather than a scatter over a million edges.
    plan: list[tuple[int, tuple, tuple, np.ndarray, np.ndarray, np.ndarray]] = []
    max_dt = 1
    unpaid_sum = 0.0
    unpaid_count = 0
    unpaid_max = 0.0
    for d, (d_row, d_col, diagonal) in enumerate(OFFSETS):
        r0, r1 = max(0, -d_row), height - max(0, d_row)
        c0, c1 = max(0, -d_col), width - max(0, d_col)
        if r1 <= r0 or c1 <= c0:
            continue
        src = (slice(r0, r1), slice(c0, c1))
        dst = (slice(r0 + d_row, r1 + d_row), slice(c0 + d_col, c1 + d_col))
        allowed = tables.allowed[d][src]
        if not allowed.any():
            continue
        travel_h = tables.travel_h[d][src]
        traction_w = tables.traction_w[d][src]
        finite = allowed & np.isfinite(travel_h)
        steps = np.zeros(allowed.shape, dtype=np.int64)
        steps[finite] = np.maximum(
            1, np.ceil(travel_h[finite] / step_h).astype(np.int64)
        )
        for value in np.unique(steps[finite]):
            span = int(value)
            # A move that lands at or past the horizon is refused at every
            # slice (``arrival >= n_slices``), exactly as astar_4d refuses it
            # with rejections["horizon"]. Dropping it here keeps the rolling
            # window from being sized by an edge no slice can ever use.
            if span >= n_slices:
                continue
            mask = finite & (steps == span)
            if not mask.any():
                continue
            max_dt = max(max_dt, span)
            # Zeroed off the mask so no ``inf`` reaches the arithmetic below:
            # an unusable edge carries ``travel_h = inf``, and ``inf * 0`` or
            # ``-inf - -inf`` would raise invalid-value warnings while
            # producing values the mask discards anyway. On the masked cells
            # these are the table's own numbers, bit for bit.
            travel_ok = np.where(mask, travel_h, 0.0)
            traction_ok = np.where(mask, traction_w, 0.0)
            plan.append((span, src, dst, mask, travel_ok, traction_ok))
            idle = span * step_h - travel_h[mask]
            unpaid_sum += float(idle.sum())
            unpaid_count += int(idle.size)
            unpaid_max = max(unpaid_max, float(idle.max()))

    # The DAG argument rests on every edge advancing the clock, so check it
    # rather than trust it: an ``inf`` travel time cast to int64 becomes
    # INT64_MIN, which would make ``arrival`` negative, wrap the shadow index
    # and write backwards into a finalised slice. The ``finite`` mask above
    # prevents that; this is the assertion that says so out loud.
    if any(span < 1 for span, *_ in plan):
        raise ValueError("a move edge must advance the clock by at least one slice")

    ring = max_dt + 1
    best = np.full((ring, height, width), -np.inf, dtype=np.float64)
    dark = np.full((ring, height, width), np.inf, dtype=np.float64)
    start_row, start_col = int(start[0]), int(start[1])
    best[0, start_row, start_col] = battery0
    dark[0, start_row, start_col] = 0.0

    first_slice = np.full((height, width), -1, dtype=np.int32)
    soc_at_first = np.full((height, width), np.nan, dtype=np.float64)
    dark_at_first = np.full((height, width), np.nan, dtype=np.float64)
    best_soc = np.full((height, width), -np.inf, dtype=np.float64)
    live_per_slice = np.zeros(n_slices, dtype=np.int64)
    edges_relaxed = 0
    negative_edges = 0
    # astar_4d's own rejection keys, so a refusal counted here means the same
    # thing it means in a plan's ``metrics.rejections``.
    refusals = {"soc_floor": 0, "shadow_endurance": 0, "horizon": 0}
    # astar_4d refuses only ABOVE the endurance plus its slack; matching it
    # exactly is what keeps a hairline state from being killed here and kept
    # there.
    endurance_limit = endurance_h + ENDURANCE_SLACK_H if math.isfinite(endurance_h) else endurance_h

    for index in range(n_slices):
        cur = index % ring
        soc_now = best[cur]
        dark_now = dark[cur]
        live = passable & (soc_now >= reserve_wh) & (dark_now <= endurance_limit)
        live_per_slice[index] = int(live.sum())
        fresh = live & (first_slice < 0)
        if fresh.any():
            first_slice[fresh] = index
            soc_at_first[fresh] = soc_now[fresh]
            dark_at_first[fresh] = dark_now[fresh]
        np.maximum(best_soc, np.where(live, soc_now, -np.inf), out=best_soc)

        if not live.any():
            best[cur].fill(-np.inf)
            dark[cur].fill(np.inf)
            continue

        if index + 1 >= n_slices:
            # The last slice relaxes nothing, but every move out of it IS
            # refused by the horizon and has to be counted: without this the
            # tally would under-report exactly the rule that most often
            # bounds a short sweep.
            for span, src, _dst, mask, _travel, _traction in plan:
                refusals["horizon"] += int((mask & live[src]).sum())
            best[cur].fill(-np.inf)
            dark[cur].fill(np.inf)
            continue

        # WAIT: one slice in place, at this slice's exposure.
        exposure = shadow[index]
        # == cost_engine.wait_battery_drain_wh(exposure, slice_hours, rover)
        wait_drain = (p_idle_w + exposure * shadow_extra_w - p_solar_w * (1.0 - exposure)) * step_h
        wait_soc = np.minimum(e_cap_wh, soc_now - wait_drain)
        wait_dark = _dark_after(exposure, dark_now, step_h)
        wait_soc_ok = wait_soc >= reserve_wh
        wait_dark_ok = wait_dark <= endurance_limit
        wait_ok = live & wait_soc_ok & wait_dark_ok
        nxt = (index + 1) % ring
        np.maximum(best[nxt], np.where(wait_ok, wait_soc, -np.inf), out=best[nxt])
        np.minimum(dark[nxt], np.where(wait_ok, wait_dark, np.inf), out=dark[nxt])
        edges_relaxed += int(wait_ok.sum())
        negative_edges += int((live & (wait_drain < 0.0)).sum())
        refusals["soc_floor"] += int((live & ~wait_soc_ok).sum())
        refusals["shadow_endurance"] += int((live & wait_soc_ok & ~wait_dark_ok).sum())

        # MOVE: eight neighbours, each landing ``span`` slices ahead.
        for span, src, dst, mask, travel_h, traction_w in plan:
            live_src = live[src]
            arrival = index + span
            if arrival >= n_slices:
                # astar_4d's rejections["horizon"], same test, same meaning.
                refusals["horizon"] += int((mask & live_src).sum())
                continue
            if not live_src.any():
                continue
            e_dep = shadow[index][src]
            e_arr = shadow[arrival][dst]
            mean_exposure = 0.5 * (e_dep + e_arr)
            # == pathfinder_4d.astar_4d's inlined move drain, operation for
            # operation. NOT cost_engine.move_battery_drain_wh: that one is
            # the same model and a DIFFERENT float -- it routes the draw
            # through gross_energy_per_metre_wh (per-metre time times
            # distance) and subtracts the solar term after multiplying rather
            # than before. D6 claims to contain the PLANNER, so it copies the
            # planner; test_reachability asserts `==` against the planner's
            # expression and only `approx` against cost_engine's.
            drain = (
                traction_w
                + (p_idle_w + mean_exposure * shadow_extra_w)
                - p_solar_w * (1.0 - mean_exposure)
            ) * travel_h
            # The -inf of a dead source would make ``-inf - drain`` a NaN when
            # drain is itself infinite; the mask discards those cells, so the
            # source charge is neutralised rather than propagated.
            soc_src = np.where(live_src, best[cur][src], 0.0)
            dark_src = np.where(live_src, dark[cur][src], 0.0)
            move_soc = np.minimum(e_cap_wh, soc_src - drain)
            move_dark = _dark_after(e_arr, dark_src, travel_h)
            usable = mask & live_src
            soc_ok = move_soc >= reserve_wh
            dark_ok = move_dark <= endurance_limit
            ok = usable & soc_ok & dark_ok
            refusals["soc_floor"] += int((usable & ~soc_ok).sum())
            refusals["shadow_endurance"] += int((usable & soc_ok & ~dark_ok).sum())
            negative_edges += int((usable & (drain < 0.0)).sum())
            if not ok.any():
                continue
            slot = arrival % ring
            np.maximum(
                best[slot][dst], np.where(ok, move_soc, -np.inf), out=best[slot][dst]
            )
            np.minimum(
                dark[slot][dst], np.where(ok, move_dark, np.inf), out=dark[slot][dst]
            )
            edges_relaxed += int(ok.sum())

        best[cur].fill(-np.inf)
        dark[cur].fill(np.inf)

    reachable = first_slice >= 0
    best_soc = np.where(reachable, best_soc, np.nan)
    return ReachabilityField(
        first_slice=first_slice,
        soc_at_first_wh=soc_at_first,
        dark_at_first_h=dark_at_first,
        best_soc_wh=best_soc,
        reachable=reachable,
        live_per_slice=live_per_slice,
        n_slices=n_slices,
        slice_hours=step_h,
        e_cap_wh=e_cap_wh,
        reserve_wh=reserve_wh,
        endurance_h=endurance_h,
        elapsed_s=time.perf_counter() - started,
        edges_relaxed=edges_relaxed,
        negative_edges=negative_edges,
        refusals=refusals,
        unpaid_idle_mean_h=(unpaid_sum / unpaid_count) if unpaid_count else 0.0,
        unpaid_idle_max_h=unpaid_max,
        edge_groups=len(plan),
        partially_lit_first_slice=int(
            (passable & (shadow[0] > 0.0) & (shadow[0] < 1.0)).sum()
        ),
    )


# ── time to 0 SOC, per block ─────────────────────────────────────────────────


#: Default step for the hold integral. A stationary rover's drain changes
#: only with the Sun, so it does not need the drive clock's resolution --
#: and it must not use it: the drive slice is sized to one cell crossing
#: (0.0359 h on Site11 at coarsen 4), which would put a 100-hour hold at
#: 2 785 slices of a full shadow cube.
DEFAULT_HOLD_SLICE_HOURS: float = 0.5
#: How far past the drive horizon the hold clock runs when the caller names
#: nothing: twice the rover's published continuous-darkness endurance, so
#: the endurance clock has room to actually fire.
DEFAULT_HOLD_ENDURANCE_MULTIPLE: float = 2.0
MAX_HOLD_HORIZON_HOURS: float = 720.0


def default_hold_horizon_hours(rover: Mapping[str, Any], drive_horizon_hours: float) -> float:
    """How long to run the hold clock for, absent a caller's choice.

    A 3-hour drive horizon censored every hold time on Site11 (measured:
    2 086 of 2 086 blocks) because LPR-1 sits for tens of hours on a full
    battery. The hold has to outlast the drive or the field is all nulls.
    """
    endurance = float(rover.get("h_max_shadow_h") or 0.0)
    want = max(
        float(drive_horizon_hours),
        endurance * DEFAULT_HOLD_ENDURANCE_MULTIPLE if endurance > 0 else 24.0,
    )
    return min(MAX_HOLD_HORIZON_HOURS, want)


@dataclass
class HoldTimes:
    """How long the rover could STAND at each reachable block (SHERPA's
    ``time-to-0-SOC``, given a place to stand in).

    Three clocks, all measured from the block's earliest arrival and all
    censored at the end of the HOLD horizon rather than extrapolated:

    ``to_reserve_h``  until the charge first falls under ``soc_min_pct``;
    ``to_zero_h``     until it first reaches zero;
    ``to_endurance_h`` until the continuous-darkness clock passes
                      ``h_max_shadow_h`` -- the OTHER way a stationary rover
                      runs out, and the one a pure energy number hides.

    ``nan`` where the clock never ran out inside that horizon; the matching
    ``*_censored`` mask says which those are, so "long" is never confused
    with "unknown".
    """

    to_reserve_h: np.ndarray
    to_zero_h: np.ndarray
    to_endurance_h: np.ndarray
    reserve_censored: np.ndarray
    zero_censored: np.ndarray
    endurance_censored: np.ndarray
    horizon_h: float
    slice_hours: float
    arrival_resolution_h: float


def hold_times(
    field: ReachabilityField,
    hold_shadow_cube: np.ndarray,
    rover: Mapping[str, Any],
    hold_slice_hours: float = DEFAULT_HOLD_SLICE_HOURS,
) -> HoldTimes:
    """Integrate the WAIT drain forward from each block's earliest arrival.

    The rover is held in place, so this is ``wait_battery_drain_wh`` applied
    slice by slice at the block's own exposure -- the same expression the
    sweep's wait edge uses. Holding is not otherwise constrained: a hold that
    would break the continuous-darkness rule is still integrated, because the
    point is to report BOTH clocks and let the operator see which one fires
    first. The sweep's live set already enforces the rule; this does not.

    *hold_shadow_cube* runs on its OWN clock, from the same epoch as the
    sweep but at *hold_slice_hours* and usually much further: the drive
    horizon is sized by how far the rover can DRIVE, and a rover that
    arrives somewhere in two hours can stand there for sixty. A block's hold
    therefore begins at hold-slice ``floor(earliest_hours / hold_slice)``,
    which places the start of the hold within one hold slice of the real
    arrival; ``arrival_resolution_h`` publishes that error rather than
    hiding it.
    """
    shadow = np.asarray(hold_shadow_cube, dtype=np.float64)
    n_slices, height, width = shadow.shape
    step_h = float(hold_slice_hours)
    if not (step_h > 0.0):
        raise ValueError("hold_slice_hours must be positive")
    if (height, width) != field.first_slice.shape:
        raise ValueError("the hold cube must be on the sweep's grid")
    e_cap_wh = float(rover["e_cap_wh"])
    reserve_wh = e_cap_wh * float(rover.get("soc_min_pct") or 0.0)
    endurance_h = field.endurance_h
    p_idle_w = float(rover["p_idle_w"])
    p_shadow_w = rover.get("p_shadow_w")
    shadow_extra_w = (
        max(0.0, float(p_shadow_w) - p_idle_w)
        if p_shadow_w is not None
        else float(rover.get("p_heater_w") or 0.0)
    )
    p_solar_w = float(rover.get("p_solar_w") or 0.0)

    charge = np.where(field.reachable, field.soc_at_first_wh, np.nan)
    dark = np.where(field.reachable, field.dark_at_first_h, np.nan)
    to_reserve = np.full((height, width), np.nan, dtype=np.float64)
    to_zero = np.full((height, width), np.nan, dtype=np.float64)
    to_endurance = np.full((height, width), np.nan, dtype=np.float64)
    # The block's arrival, mapped onto the hold clock. The hold runs on its
    # own, coarser slice, so a block that arrives mid-slice begins its hold at
    # the slice it arrives IN; the error is under one hold slice and is
    # published as arrival_resolution_h rather than smoothed away.
    arrival = field.earliest_hours
    with np.errstate(invalid="ignore"):
        start_index = np.where(
            field.reachable,
            np.minimum(n_slices - 1, np.floor(np.nan_to_num(arrival, nan=0.0) / step_h)),
            -1,
        ).astype(np.int64)

    for index in range(n_slices):
        holding = field.reachable & (start_index <= index) & (index + 1 < n_slices)
        if not holding.any():
            continue
        exposure = shadow[index]
        # == cost_engine.wait_battery_drain_wh(exposure, hold_slice, rover),
        # and the same expression the sweep's own wait edge uses.
        drain = (p_idle_w + exposure * shadow_extra_w - p_solar_w * (1.0 - exposure)) * step_h
        stepped = np.minimum(e_cap_wh, charge - drain)
        charge = np.where(holding, stepped, charge)
        dark_next = _dark_after(exposure, dark, step_h)
        dark = np.where(holding, dark_next, dark)
        elapsed = (index + 1 - start_index).astype(np.float64) * step_h
        hit = holding & np.isnan(to_reserve) & (charge < reserve_wh)
        to_reserve[hit] = elapsed[hit]
        hit = holding & np.isnan(to_zero) & (charge <= 0.0)
        to_zero[hit] = elapsed[hit]
        if math.isfinite(endurance_h):
            hit = holding & np.isnan(to_endurance) & (dark > endurance_h + ENDURANCE_SLACK_H)
            to_endurance[hit] = elapsed[hit]

    horizon_h = (n_slices - 1) * step_h
    return HoldTimes(
        to_reserve_h=to_reserve,
        to_zero_h=to_zero,
        to_endurance_h=to_endurance,
        reserve_censored=field.reachable & np.isnan(to_reserve),
        zero_censored=field.reachable & np.isnan(to_zero),
        endurance_censored=field.reachable & np.isnan(to_endurance),
        horizon_h=horizon_h,
        slice_hours=step_h,
        arrival_resolution_h=step_h,
    )


def hold_limit(holds: HoldTimes, reachable: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``(hours, limited_by)``: which clock actually ends the hold.

    The energy number alone is the wrong headline. Stationary LPR-1 in full
    darkness reaches its reserve at 66.7 h and zero at 83.4 h, but its
    published continuous-darkness endurance is 50 h -- so the shadow clock
    binds first and a "time to 0 SOC" of 83.4 h describes a state the rest of
    this API calls mission failure. ``hold_limit`` is the minimum of the
    reserve clock and the endurance clock, with the winner named:
    ``0`` reserve, ``1`` shadow_endurance, ``2`` censored (neither ran out
    inside the hold horizon), ``-1`` the block was never reachable.

    ``to_zero_h`` is deliberately NOT in the minimum: below the reserve this
    model has no transitions at all, so it is a battery-physics number and
    never an operating margin.
    """
    live = np.asarray(reachable, dtype=bool)
    reserve = np.where(np.isnan(holds.to_reserve_h), np.inf, holds.to_reserve_h)
    endurance = np.where(np.isnan(holds.to_endurance_h), np.inf, holds.to_endurance_h)
    limit = np.minimum(reserve, endurance)
    code = np.where(endurance < reserve, 1, 0).astype(np.int8)
    code = np.where(np.isinf(limit), 2, code).astype(np.int8)
    code = np.where(live, code, -1).astype(np.int8)
    hours = np.where(live & np.isfinite(limit), limit, np.nan)
    return hours, code


#: What ``hold_limit``'s second return means, published beside it.
HOLD_LIMIT_CODES: dict[str, int] = {
    "reserve": 0,
    "shadow_endurance": 1,
    "censored": 2,
    "unreachable": -1,
}


# ── isochrone bands ──────────────────────────────────────────────────────────


def default_band_edges(horizon_hours: float, count: int = DEFAULT_BAND_COUNT) -> list[float]:
    """Equal slices of the horizon.

    Arbitrary, and said to be: a rover whose speed follows the slope under it
    has no natural isochrone spacing, so any default is a drawing convention.
    The caller can name its own edges.
    """
    n = max(1, int(count))
    return [round(float(horizon_hours) * (k + 1) / n, 6) for k in range(n)]


def isochrone_bands(
    field: ReachabilityField,
    band_edges: Sequence[float],
    resolution_m: float,
) -> dict[str, Any]:
    """Band index per block plus the band table.

    ``band_index`` is ``-1`` where the block was never live and ``k`` where
    its earliest arrival falls in ``(edges[k-1], edges[k]]``. Blocks reachable
    later than the last edge get the last band only if the edge covers them;
    anything past it is ``len(edges)`` and reported as ``beyond_last_edge``.
    """
    edges = [float(value) for value in band_edges]
    if not edges:
        raise ValueError("at least one band edge is needed")
    if any(b <= a for a, b in zip(edges, edges[1:])):
        raise ValueError("band edges must be strictly increasing")
    if edges[0] <= 0.0:
        raise ValueError("band edges must be positive")

    hours = field.earliest_hours
    index = np.full(hours.shape, -1, dtype=np.int16)
    reachable = field.reachable
    # searchsorted with side="left" puts an arrival exactly ON an edge into
    # that edge's band, which is what "reachable within h hours" means.
    placed = np.searchsorted(np.asarray(edges, dtype=np.float64), hours[reachable], side="left")
    index[reachable] = placed.astype(np.int16)

    cell_area_km2 = (float(resolution_m) ** 2) / 1_000_000.0
    bands: list[dict[str, Any]] = []
    previous = 0.0
    for k, edge in enumerate(edges):
        count = int((index == k).sum())
        bands.append(
            {
                "band": k,
                "from_hours": round(previous, 6),
                "to_hours": round(edge, 6),
                "blocks": count,
                "area_km2": round(count * cell_area_km2, 6),
            }
        )
        previous = edge
    beyond = int((index == len(edges)).sum())
    return {
        "edges_hours": [round(value, 6) for value in edges],
        "bands": bands,
        "beyond_last_edge_blocks": beyond,
        "band_index": index,
        "block_area_km2": round(cell_area_km2, 6),
        "reachable_blocks": int(reachable.sum()),
        "reachable_area_km2": round(int(reachable.sum()) * cell_area_km2, 6),
        "smoothing": (
            "none. A band's boundary is the coarse block lattice's staircase at "
            f"{float(resolution_m):g} m; it is NOT a contour of a continuous field. "
            "Smoothing it (skimage.measure.find_contours, as the research note "
            "proposed) would draw a line through terrain this sweep never evaluated, "
            "and scikit-image is not a dependency of this backend."
        ),
    }


def band_boundary_cells(
    band_index: np.ndarray, band: int, limit: int = MAX_BOUNDARY_CELLS
) -> tuple[list[list[int]], bool]:
    """``([[row, col], ...], truncated)``: the blocks of *band* that touch a
    later band, an unreachable block or the grid edge.

    4-connected, numpy only. The list is the STAIRCASE outline of the band,
    not a polygon: consecutive entries are not joined and no order is
    implied. Truncation is reported rather than silent.
    """
    index = np.asarray(band_index)
    inside = index == int(band)
    if not inside.any():
        return [], False
    padded = np.pad(index, 1, mode="constant", constant_values=-1)
    outside = np.zeros_like(inside)
    for d_row, d_col in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = padded[
            1 + d_row : 1 + d_row + index.shape[0], 1 + d_col : 1 + d_col + index.shape[1]
        ]
        outside |= shifted != int(band)
    edge = inside & outside
    rows, cols = np.nonzero(edge)
    total = int(rows.size)
    take = min(total, max(0, int(limit)))
    cells = [[int(rows[i]), int(cols[i])] for i in range(take)]
    return cells, take < total


# ── "and in N hours?" ────────────────────────────────────────────────────────


def compare_fields(now: ReachabilityField, later: ReachabilityField, resolution_m: float) -> dict[str, Any]:
    """What moving the epoch does to the reachable set.

    The shadow moves, so the set at ``t`` is not the set at ``t + N``: this
    reports which blocks are gained, which are lost, and the Jaccard overlap.
    Counts only -- the two band maps are published separately, and a
    per-block diff grid would be a third copy of the same information.
    """
    a = np.asarray(now.reachable, dtype=bool)
    b = np.asarray(later.reachable, dtype=bool)
    if a.shape != b.shape:
        raise ValueError("the two fields must be on the same grid")
    union = int((a | b).sum())
    kept = int((a & b).sum())
    cell_area_km2 = (float(resolution_m) ** 2) / 1_000_000.0
    gained = int((~a & b).sum())
    lost = int((a & ~b).sum())
    return {
        "now_blocks": int(a.sum()),
        "later_blocks": int(b.sum()),
        "kept_blocks": kept,
        "gained_by_later_start_blocks": gained,
        "lost_by_later_start_blocks": lost,
        "jaccard": round(kept / union, 6) if union else None,
        "now_area_km2": round(int(a.sum()) * cell_area_km2, 6),
        "later_area_km2": round(int(b.sum()) * cell_area_km2, 6),
        "gained_by_later_start_area_km2": round(gained * cell_area_km2, 6),
        "lost_by_later_start_area_km2": round(lost * cell_area_km2, 6),
        "independent_restart": True,
        "question_answered": (
            "a rover that BEGINS at start_utc + N with the same start block and the "
            "same initial charge -- what the moved shadow does to its reach"
        ),
        "question_not_answered": (
            "a rover that WAITS N hours at the start block. That one is already inside "
            "the base sweep's wait edges, and it arrives at N with less charge than "
            "this comparison gives it, so the two answers differ and the difference is "
            "the whole cost of waiting."
        ),
    }
