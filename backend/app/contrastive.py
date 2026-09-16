"""Contrastive explanation: why this route, and why not that one (D4).

``CostMap.explain()`` and ``cost_breakdown`` already answer "why this cell
costs what it costs". Neither answers the question an operator actually asks
when they disagree with a plan: *why not MINE?* This module answers it in
three parts -- which of the planner's own gates the proposed route trips,
how the two routes' costs differ criterion by criterion, and what would have
to change about the weight vector for the proposed route to stop losing.

Fact and foil, not "route A and route B"
----------------------------------------
The vocabulary is the XAIP literature's and is used deliberately: the
**fact** is the plan the planner produced, the **foil** is the plan the user
asks about instead (Krarup et al. 2019/2021). Our foil is a COMPLETE cell
sequence, which that literature calls the atypical case -- their foils are
normally partial ("why not action a at step 7?") and their taxonomy FQ1-FQ7
is a closed list of questions about actions, orderings and time windows. A
whole-route foil is not one of those questions, and the response says so
rather than implying membership.

The identity everything here rests on
-------------------------------------
A* minimises ``dist * (1 + (cost[u] + cost[v]) / 2 + barrier)`` summed over
the route's edges, and ``cost[cell]`` is
``max(sum_k w_k f_k(cell), MIN_CELL_COST)``. The barrier depends on geometry
and temperature, never on the weights. So for a FIXED route R::

    cost(R, w) = D(R) + sum_k w_k * I_k(R) + B(R)

    D(R)   = sum_e dist_e                           horizontal distance
    I_k(R) = sum_e dist_e * (f_k(u) + f_k(v)) / 2   the criterion's own
                                                    trapezoidal line integral
    B(R)   = sum_e dist_e * barrier_e               weight-independent

i.e. the route cost is AFFINE in the weight vector, which is what makes the
counterfactual a closed form rather than a search. Measured on the Site11
daytime pair the reconstruction reproduces the planner's published
``total_weighted_cost`` to the rounding of the published field itself.

**The identity is conditional and the condition is checked, not assumed.**
``max(..., MIN_CELL_COST)`` makes the true cell cost convex PIECEWISE-affine,
not affine; the linear form is the branch where the clamp does not bind.
``PlanWeights`` permits an all-zero weight vector, and with every weight at
zero 100 percent of passable cells clamp. So the clamp is tested per cell on
BOTH routes at EVERY weight this module evaluates, and no affine or convex
claim is published when it binds (:data:`OUTCOME_CLAMP_BINDS`).

Two regimes, because "the alternative wins" means two different things
----------------------------------------------------------------------
Changing a weight changes the cost grid, which changes the planner's own
optimum. So there are two questions, they have different answers, and
collapsing them is the deepest trap in this feature:

``vs_fact``
    At which weight does the foil cost less than THIS PARTICULAR route?
    Affine, closed form, zero re-plans. This is Krarup et al.'s method at its
    degenerate limit: the hypothetical model is the one whose only plan is
    the foil, so the "re-plan" is a no-op and the explanation is their
    comparison of the original plan against the HPlan.

``vs_replanned``
    At which weight does the planner RETURN the foil? The foil wins only by
    being optimal itself, so this is the question an operator who intends to
    change a setting is really asking.

``vs_replanned`` is NOT a model restriction in Krarup et al.'s sense and this
module does not claim it is: their Definition 4 requires every plan of the
restricted model to be a plan of the original, and reweighting leaves the
plan set untouched while re-pricing it. That is a model REVISION of the
objective. The ICAPS line is cited here for the contrastive framing; the
counterfactual-weight question itself belongs to INVERSE OPTIMISATION
(Burton & Toint 1992; Heuberger's survey), which is where the honest
citation goes.

Why there is no binary search
-----------------------------
``delta_ii(w) = cost_foil(w) - min_R cost_R(w)`` is an affine function minus
a pointwise minimum of affine functions, hence CONVEX, hence its zero set is
an INTERVAL rather than a half-line -- so "does the foil win" is not a
monotone predicate in w and a binary search for a threshold would be
searching for something that need not exist. Measured on Site11 those
intervals are tiny (widths of 0.005 and 0.02 on a [0, 2] axis), which is
also why a latency-capped uniform grid scan is close to blind: this module
publishes the scan step and the width it could have resolved, and never
reports "no weight found" as though it were a negative result.

``delta_ii >= delta_i`` pointwise (the re-planned optimum is never dearer
than the incumbent), so ``vs_fact`` is a provable LOWER BOUND on
``vs_replanned`` -- if ``vs_fact`` finds nothing in bounds, ``vs_replanned``
has nothing either, proved with zero re-plans. Measured, that bound is loose:
on one real pair ``vs_fact`` said 1.313 where ``vs_replanned``'s true
threshold was above 1.98.

What the numbers are about
--------------------------
This module explains OUR COST MODEL. A gate "violation" is the planner's own
rule fired against a loaded 5 m/px elevation raster; it is not a statement
that the surface is impassable, and a 5 m posting cannot resolve the step a
rover with a ~1 m wheelbase drives over. Replaying the same gates over NASA's
own 20 DEM error realisations moves the answer, and the response reports by
how much rather than presenting one raster's verdict as a fact about the Moon.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .constants import THERMAL_MIN_TRAVERSABLE_C
from .cost_engine import cost_criteria_for, lateral_slope_tan, resolve_weights
from .cost_vec import (
    f_energy_cell_grid,
    f_roughness_grid,
    f_shadow_cell_grid,
    f_slope_grid,
    f_thermal_grid,
)
from .costmap import MIN_CELL_COST
from .pareto import OBJECTIVE_QUANTUM, PARETO_OBJECTIVES, dominates, route_id
from .pathfinder import _barrier_table, _geometric_barrier, _thermal_barrier_grid, astar
from .roughness import RoughnessScale
from .rover_grids import grids_for_rover

logger = logging.getLogger(__name__)

#: Identifies the decomposition + inverse-weight method, the way
#: ``COST_MODEL_ID`` identifies the cost formula and ``PARETO_METHOD_ID``
#: identifies D5's sweep. Bump it when the identity, the regime definitions
#: or the outcome vocabulary change shape.
CONTRAST_METHOD_ID: str = "affine_criterion_decomposition_inverse_weight_v1"

#: The weight box ``main.PlanWeights`` enforces. Restated here rather than
#: imported because this module must not import the FastAPI shell; a test
#: asserts the two agree, so they cannot drift.
WEIGHT_MIN: float = 0.0
WEIGHT_MAX: float = 2.0

#: The weight key that scales each cost criterion. Which criteria are
#: actually PRESENT is not hardcoded: :func:`criteria_for_grids` drives that
#: off the same ``cost_criteria_for`` stamp the cost grid carries, so a
#: deployment without the roughness cache prices four criteria here exactly
#: as it does everywhere else.
CRITERION_WEIGHT_KEY: dict[str, str] = {
    "slope": "w_slope",
    "energy": "w_energy",
    "shadow": "w_shadow",
    "thermal": "w_thermal",
    "roughness": "w_roughness",
}

CONTRAST_VALIDITY: str = "MODEL"

# ── outcome vocabulary ──────────────────────────────────────────────────────
#
# Ten labels, not the four the brief asked for. The brief's four are all
# here; the other six are cases measurement showed are reachable and that
# collapsing into the four would have turned into manufactured negatives.
# Each names a DIFFERENT reason the question has no number, and the whole
# point of this feature is that "no" has several meanings.

#: The foil trips a gate the planner enforces. Weights cannot buy that back
#: at any value, so no threshold is computed and none is invented.
OUTCOME_HARD_GATE: str = "hard_gate"

#: The planner itself found no route for this pair, so there is no fact to
#: contrast against and every delta is undefined.
OUTCOME_NO_INCUMBENT: str = "no_incumbent_route"

#: The foil is no cheaper on ANY criterion integral and no cheaper on the
#: weight-independent terms, so ``delta(w) >= 0`` for every w in [0, inf)^5.
#: Proved structurally; never searched.
OUTCOME_DOMINATED: str = "dominated_on_every_criterion"

#: ``dI_k`` is zero to within tolerance: moving this weight across its whole
#: legal range cannot move the comparison, so no threshold exists. Its own
#: case rather than an infinite or missing number.
OUTCOME_NO_LEVERAGE: str = "criterion_has_no_leverage"

#: A threshold exists but lies outside ``PlanWeights``' own [0, 2].
OUTCOME_OUTSIDE_BOUNDS: str = "outside_weight_bounds"

#: A threshold exists inside [0, 2] for ``vs_fact`` ONLY: at that weight the
#: foil is cheaper than the route we showed, but the planner would return a
#: third route. A comparison, never a setting.
OUTCOME_FOUND_VS_FACT: str = "found_vs_fact_only"

#: The scan actually saw the planner return the foil.
OUTCOME_FOUND_REPLANNED: str = "found_returned_by_planner"

#: The scan finished without seeing the foil returned. NOT a negative result:
#: it carries the step and the interval width it could have resolved.
OUTCOME_UNRESOLVED_BY_SCAN: str = "unresolved_by_scan"

#: The ``MIN_CELL_COST`` clamp binds somewhere on one of the routes at the
#: weight in question, so the affine identity -- and everything derived from
#: it -- does not hold there.
OUTCOME_CLAMP_BINDS: str = "clamp_binds"

#: The foil IS the fact -- the same cell sequence, so every difference is
#: exactly zero. Its own label because the alternative is to report it as
#: :data:`OUTCOME_DOMINATED`, which reads as "your route could never win"
#: when what happened is "your route is the one we chose".
OUTCOME_FOIL_IS_THE_FACT: str = "foil_is_the_fact"

CONTRAST_OUTCOMES: tuple[str, ...] = (
    OUTCOME_HARD_GATE,
    OUTCOME_NO_INCUMBENT,
    OUTCOME_DOMINATED,
    OUTCOME_NO_LEVERAGE,
    OUTCOME_OUTSIDE_BOUNDS,
    OUTCOME_FOUND_VS_FACT,
    OUTCOME_FOUND_REPLANNED,
    OUTCOME_UNRESOLVED_BY_SCAN,
    OUTCOME_CLAMP_BINDS,
    OUTCOME_FOIL_IS_THE_FACT,
)

#: The four resolution floors, coarsest last. A verdict that does not name
#: its level is meaningless: measured on Site11 these differ by nine orders
#: of magnitude, and one real gap was 475x the publication floor, 33x the
#: barrier floor and 0.03 sigma of the terrain ensemble -- "resolved",
#: "resolved", "not resolved" for the same number.
RESOLUTION_LEVELS: tuple[dict[str, Any], ...] = (
    {
        "level": "arithmetic",
        "what": "float64 reproducibility of the same code on the same grid",
        "source": "the identity reproduces the planner's own g-score to ~1e-10",
    },
    {
        "level": "publication",
        "what": "rounding of the API's published cost fields",
        "source": (
            "round(.,4) has SPACING 1e-4, i.e. a half-width of 5e-5 per value; a "
            "difference of two carries 1e-4 worst case and 4.08e-5 RSS. Retired here: "
            "this module differences float64 integrals it computed itself and never "
            "subtracts two published rounded numbers."
        ),
    },
    {
        "level": "model_discretisation",
        "what": "pathfinder's 1024-bin barrier lookup table vs the exact log-barrier",
        "source": (
            "computed exactly per pair by evaluating the closed-form barrier alongside "
            "the table on the same edges; the table floors its index so it "
            "systematically under-states the barrier, and the bin width is far coarser "
            "on steep flanks than at the bottom"
        ),
    },
    {
        "level": "terrain_ensemble",
        "what": "NASA's own DEM error realisations of this site",
        "source": (
            "PGDA product 78 clone stack (Barker et al. 2021), re-pricing both fixed "
            "routes on each clone's elevation; the only level that moves the distance "
            "term, the barrier and the gates as well as the criteria"
        ),
    },
)

#: A gap counts as resolved at a level when it clears this many times that
#: level's floor. A convention, not a derivation, and labelled as one.
RESOLUTION_SAFETY_FACTOR: float = 3.0

CONTRAST_CLAIM: str = (
    "An explanation of THIS COST MODEL's ranking, not a statement about the lunar "
    "surface. Gate verdicts are the planner's own rules fired against a loaded 5 m/px "
    "elevation raster and its np.gradient, so they describe the raster and the operator, "
    "not the ground: a 5 m posting cannot resolve wheel-scale geometry, and replaying "
    "the same gates over NASA's DEM error realisations moves the verdict. Cost gaps are "
    "in WEIGHTED METRES, the 2-D planner's ranking scalar, which has no physical "
    "dimension and does not track hours -- a foil can cost more and still be faster, and "
    "the physical_gap block reports that separately rather than converting. The weight "
    "thresholds are one-dimensional sections of an inverse-optimisation problem, one "
    "weight at a time with the others held fixed; they are NOT norm-minimising "
    "adjustments and no norm is claimed. A vs_fact threshold says the foil would be "
    "cheaper than the route shown, NOT that the planner would return it. 2-D only: "
    "pathfinder publishes weighted_metres and pathfinder_4d weighted_hours, and the two "
    "totals are not comparable. The literature's numbers are quoted, never reproduced."
)

#: Read first-hand on 16 September 2026. THEIR numbers and THEIR words; ours
#: never go in this dict, and nothing here was reproduced by us.
CONTRASTIVE_QUOTED: dict[str, Any] = {
    "krarup_2019": {
        "citation": (
            "Krarup, Cashmore, Magazzeni, Miller -- Model-Based Contrastive Explanations "
            "for Explainable Planning, ICAPS 2019 Workshop on Explainable AI Planning "
            "(XAIP)"
        ),
        "url": (
            "https://strathprints.strath.ac.uk/69957/1/Krarup_etal_ICAPS2019_Model_based_"
            "contrastive_explanations_explainable_planning.pdf"
        ),
        "used_for": (
            "the fact/foil framing and the shape of a contrastive answer. NOT used for "
            "the weight counterfactual, which is not in this paper."
        ),
        "correction": (
            "read first-hand: the comparison this paper makes between the original plan "
            "and the hypothetical plan is ONE SCALAR per plan. The per-criterion "
            "decomposition in part (b) is not theirs; the nearest precedent for that is "
            "Sukkerd, Simmons and Garlan's linear-scalarisation contrast."
        ),
    },
    "krarup_2021_restrictions": {
        "citation": (
            "Krarup, Krivic, Magazzeni, Long, Cashmore, Smith -- Contrastive "
            "Explanations of Plans Through Model Restrictions, arXiv:2103.15575, 2021"
        ),
        "url": "https://arxiv.org/pdf/2103.15575",
        "used_for": (
            "the definition of a model restriction, and therefore the reason this "
            "module's vs_replanned regime is explicitly NOT one: reweighting is a "
            "revision of the objective and leaves the plan set untouched."
        ),
        "definition_4_quote": (
            "A constraint operator is defined so that, for a planning model and any "
            "constraint property, it is a model (an HModel), called a model restriction, "
            "satisfying the condition that any plan for [the restricted model] is a plan "
            "for [the original] that also satisfies [the property]"
        ),
        "taxonomy_quote": (
            "The questions in categories FQ1 to FQ7 are of the form \"Why A rather than B?\" "
            "and are clearly contrastive"
        ),
        "taxonomy_note": (
            "read first-hand: all seven are about ACTIONS and TIMES (FQ1 'Why is action A not "
            "used in the plan', FQ7 'Why is action A used at time T'). None is about costs or "
            "weights, and a whole-route foil is not one of them."
        ),
        "restriction_quote": (
            "a model restriction satisfies the condition that any plan for the restricted "
            "model is also a plan for the original model"
        ),
        "why_it_does_not_apply": (
            "changing the weight vector leaves every plan a plan -- it re-prices the set "
            "rather than shrinking it -- so it is a model REVISION of the objective, not a "
            "restriction. Regime vs_fact, by contrast, IS this definition at its degenerate "
            "limit: the constraint property 'the plan is exactly the foil' admits one plan, "
            "so the HPlan is the foil and the re-plan is a no-op."
        ),
    },
    "burton_toint_1992": {
        "citation": (
            "Burton, Toint -- On an instance of the inverse shortest paths problem, "
            "Mathematical Programming 53(1-3):45-61, 1992"
        ),
        "url": "https://doi.org/10.1007/BF01585693",
        "used_for": (
            "the origin of the question part (c) actually asks -- what must the edge "
            "costs become for a given path to be the shortest one -- which is inverse "
            "shortest paths, not XAIP."
        ),
        "priority_quote": (
            "Burton and Toint [9] first investigated an inverse shortest paths problem in "
            "1992. [...] Actually it was the first inverse optimization problem that has "
            "been considered"
        ),
        "quote_source": "quoted via Heuberger's survey, sects. 1 and 5.1",
    },
    "heuberger_inverse_opt": {
        "citation": (
            "Heuberger -- Inverse Combinatorial Optimization: A Survey on Problems, "
            "Methods, and Results, Journal of Combinatorial Optimization 8(3):329-361, "
            "2004"
        ),
        "url": "https://www.math.aau.at/heuberger/publications/pdf/inverseopt.pdf",
        "used_for": (
            "the statement that the inverse problem minimises a NORM over the whole cost "
            "vector under bounds -- precisely what this module's per-criterion sections "
            "do NOT do, named so the difference is legible."
        ),
        "definition_quote": (
            "Given a (combinatorial) optimization problem and a feasible solution to it, "
            "the corresponding inverse optimization problem is to find a minimal adjustment "
            "of the cost function such that the given solution becomes optimum"
        ),
        "bounded_quote": (
            "representing lower and upper bounds for the modified costs. Let ||.|| denote "
            "some vector norm"
        ),
        "why_ours_is_not_that": (
            "this module holds four weights fixed and moves one, so it reports a "
            "one-dimensional SECTION of that problem. No norm is chosen and joint moves are "
            "not searched, so the per-criterion numbers are not minimal adjustments. "
            "l2_minimal_joint_move is the one field that does answer the norm question, in "
            "the vs_fact regime only."
        ),
    },
    "sukkerd_2020": {
        "citation": (
            "Sukkerd, Simmons, Garlan -- Tradeoff-Focused Contrastive Explanation for "
            "MDP Planning, RO-MAN 2020, arXiv:2004.12960"
        ),
        "url": "https://arxiv.org/abs/2004.12960",
        "used_for": (
            "the nearest precedent for part (b): a linearly scalarised multi-objective "
            "planner explained by contrasting PER-ATTRIBUTE gains and losses against "
            "alternatives."
        ),
        "scalarisation_quote": (
            "(MDP) planning with linear scalarization of multiple objective [cost functions]"
        ),
        "contrast_quote": (
            "gains and losses with respect to the QAs by choosing one [policy over another] "
            "[...] describing the gains and the losses quantitatively"
        ),
    },
}

CONTRAST_REFERENCES: tuple[dict[str, str], ...] = tuple(
    {
        "id": key,
        "citation": str(value["citation"]),
        "url": str(value.get("url", "")),
        "used_for": str(value.get("used_for", "")),
    }
    for key, value in CONTRASTIVE_QUOTED.items()
)


class ContrastInputError(ValueError):
    """A foil the contrast cannot be run against.

    Carries the machine-readable *reason* alongside the sentence, so the
    FastAPI shell can turn it into a 422 whose body names the rule rather
    than making the caller parse prose.
    """

    def __init__(self, reason: str, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.detail = detail


# ── the foil's contract ─────────────────────────────────────────────────────


def validate_foil(
    foil: Sequence[Sequence[int]],
    start: Sequence[int],
    goal: Sequence[int],
    shape: Sequence[int],
    max_cells: int,
) -> list[tuple[int, int]]:
    """The foil, normalised -- or :class:`ContrastInputError` saying which rule broke.

    Every rule here exists because breaking it makes the COMPARISON
    meaningless rather than merely odd, so each one is refused at the door
    instead of producing a number nobody can interpret:

    * **Same start and goal as the fact.** Two routes between different
      points have no comparable cost; the difference would be mostly the
      difference in the journey, not in the routing.
    * **8-adjacency.** The planner's edge set is the 8 neighbours. A foil
      that jumps is not a route this planner could ever produce, so its
      "cost" would be an integral over edges the cost model does not define.
    * **In bounds**, before any numpy index -- a negative index silently
      wraps and would price a cell on the far side of the grid.
    * **No repeated cell.** A* paths are simple by construction (``came_from``
      is a tree), and a foil that revisits a cell has no well-defined
      trapezoidal integral over "the" route.

    ``start``/``goal`` are the RESOLVED pixels, so a geo request that lands
    one cell from where the caller clicked is refused with all three of the
    caller's cell, the resolved cell and the coordinate kind named -- the
    off-by-one is the server's convention, and a bare "must share the start"
    would blame the caller for it.
    """
    rows, cols = int(shape[0]), int(shape[1])
    n = len(foil)
    if n < 2:
        raise ContrastInputError(
            "foil_too_short",
            f"the foil needs at least 2 cells to have an edge, got {n}",
            n_cells=n,
        )
    if n > max_cells:
        raise ContrastInputError(
            "foil_too_long",
            (
                f"the foil has {n} cells, above the {max_cells} cap for this "
                f"{rows}x{cols} grid; the cap bounds the response size and the "
                "re-planning budget, not the terrain"
            ),
            n_cells=n,
            max_cells=max_cells,
            grid_shape=[rows, cols],
        )

    cells: list[tuple[int, int]] = []
    for index, point in enumerate(foil):
        if len(point) != 2:
            raise ContrastInputError(
                "foil_cell_malformed",
                f"foil[{index}] must be [row, col], got {list(point)!r}",
                index=index,
            )
        row, col = int(point[0]), int(point[1])
        if not (0 <= row < rows and 0 <= col < cols):
            raise ContrastInputError(
                "foil_out_of_bounds",
                f"foil[{index}] = ({row}, {col}) is outside the {rows}x{cols} grid",
                index=index,
                cell=[row, col],
                grid_shape=[rows, cols],
            )
        cells.append((row, col))

    if cells[0] != (int(start[0]), int(start[1])):
        raise ContrastInputError(
            "foil_start_mismatch",
            (
                f"foil[0] = {list(cells[0])} but the planner's start resolves to "
                f"{[int(start[0]), int(start[1])]}; a contrast between routes with "
                "different endpoints compares the journeys, not the routing. Send the "
                "start as pixels, or begin the foil at the resolved cell."
            ),
            foil_endpoint=list(cells[0]),
            resolved_endpoint=[int(start[0]), int(start[1])],
            which="start",
        )
    if cells[-1] != (int(goal[0]), int(goal[1])):
        raise ContrastInputError(
            "foil_goal_mismatch",
            (
                f"foil[-1] = {list(cells[-1])} but the planner's goal resolves to "
                f"{[int(goal[0]), int(goal[1])]}; a contrast between routes with "
                "different endpoints compares the journeys, not the routing. Send the "
                "goal as pixels, or end the foil at the resolved cell."
            ),
            foil_endpoint=list(cells[-1]),
            resolved_endpoint=[int(goal[0]), int(goal[1])],
            which="goal",
        )

    seen: dict[tuple[int, int], int] = {}
    for index, cell in enumerate(cells):
        if cell in seen:
            raise ContrastInputError(
                "foil_repeats_a_cell",
                (
                    f"foil[{index}] = {list(cell)} repeats foil[{seen[cell]}]; A* paths "
                    "are simple, and a route that revisits a cell has no single "
                    "trapezoidal integral"
                ),
                index=index,
                first_index=seen[cell],
                cell=list(cell),
            )
        seen[cell] = index

    for index in range(1, len(cells)):
        previous, current = cells[index - 1], cells[index]
        step = max(abs(current[0] - previous[0]), abs(current[1] - previous[1]))
        if step != 1:
            raise ContrastInputError(
                "foil_not_8_adjacent",
                (
                    f"foil[{index - 1}] = {list(previous)} and foil[{index}] = "
                    f"{list(current)} are not 8-neighbours; the planner's edge set is "
                    "the 8 neighbours, so a jump is not an edge this cost model prices"
                ),
                index=index,
                from_cell=list(previous),
                to_cell=list(current),
            )
    return cells


# ── the planner's own gates, replayed ───────────────────────────────────────

#: The per-edge refusals of ``pathfinder._astar_core``, IN THE ORDER THAT
#: FUNCTION APPLIES THEM, with the rejection counter each one increments (or
#: ``None`` where the planner refuses the edge silently).
#:
#: The order is load-bearing and was got wrong in the first draft of this
#: module. ``_astar_core`` short-circuits on the FIRST failing rule, so an edge
#: that both cuts a diagonal corner and exceeds the step slope is a
#: ``diagonal_corner_cut`` to the planner and would be a ``step_slope`` to any
#: replay that checked the slopes first. A replay whose labels disagree with
#: the planner's is not a replay, and the whole selling point of this block is
#: that these are the planner's rules rather than a second opinion.
#:
#: Three of ``_astar_core``'s ``continue`` statements are deliberately NOT
#: here. ``bounds`` is enforced by :func:`validate_foil` before any array is
#: indexed. ``closed[n_idx]`` and ``tentative_g >= g_score[n_idx]`` are SEARCH
#: STATE, not constraints: they say the search already has a better way to
#: that cell, which is not a property of the foil and cannot be replayed over
#: a fixed route.
GATE_ORDER: tuple[dict[str, Any], ...] = (
    {
        "rule": "destination_not_traversable",
        "counter": None,
        "source": "traversable mask on the DESTINATION cell (slope, cold-end thermal, NaN)",
    },
    {
        "rule": "diagonal_corner_cut",
        "counter": None,
        "source": "both cardinal neighbours shared by a diagonal step must be traversable",
    },
    {
        "rule": "nan_elevation",
        "counter": None,
        "source": "elevation difference across the step is NaN",
    },
    {
        "rule": "step_slope",
        "counter": "step_slope",
        "source": "abs(dz)/dist on the loaded elevation grid, against tan(slope_max_deg)",
    },
    {
        "rule": "lateral_slope",
        "counter": "lateral_slope",
        "source": (
            "np.gradient of the elevation grid, averaged over the edge and projected "
            "perpendicular to travel, against tan(slope_lateral_max_deg)"
        ),
    },
    {
        "rule": "thermal_barrier",
        "counter": "thermal_barrier",
        "source": "log-barrier on the destination cell's cold-end and peak temperature",
    },
    {
        "rule": "slope_barrier",
        "counter": "slope_barrier",
        "source": "tabulated log-barrier on the step slope (1024 bins, floored index)",
    },
    {
        "rule": "lateral_barrier",
        "counter": "lateral_barrier",
        "source": "tabulated log-barrier on the cross-slope (1024 bins, floored index)",
    },
)

GATE_RULES: tuple[str, ...] = tuple(g["rule"] for g in GATE_ORDER)

_R2: float = 1.0 / math.sqrt(2.0)


def _finite_or_none(value: Any) -> float | None:
    """``None`` for anything Starlette's ``allow_nan=False`` would refuse.

    The gate and barrier machinery produces infinities BY DESIGN -- that is
    how impassability is expressed -- and these dicts are serialised straight
    into an API response, where a bare ``inf`` raises ValueError and turns the
    request into a 500. ``None`` is the convention the rest of this API
    already uses for a value it cannot represent (``main._read_grid_value``,
    ``CostMap.explain``).
    """
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


class EdgeModel:
    """Everything the planner's per-edge rules read, prepared once.

    This is a REPLAY of ``pathfinder._astar_core``'s inner loop, not a shared
    implementation, and that is a deliberate trade rather than an oversight.
    The three pieces round 4 already consolidated are imported and reused
    (:func:`~app.pathfinder._thermal_barrier_grid`,
    :func:`~app.pathfinder._barrier_table`,
    :func:`~app.cost_engine.lateral_slope_tan`); only the loop glue -- the
    offset table, the gradient midpoint and the floored bin index -- is
    restated. Extracting the glue from ``_astar_core`` would put a function
    call inside a loop that runs ~1.6 million times per plan and is hand-
    inlined for exactly that reason, so the planner is left untouched and the
    agreement is pinned by tests instead: the replay must return no violations
    on the planner's own route, and on a synthetic grid its labels must equal
    the planner's own ``edges_rejected`` keys.

    *elevation* overrides the grid's own field, which is how the DEM clone
    ensemble re-runs the same gates over NASA's error realisations.
    """

    def __init__(
        self,
        grids: Mapping[str, Any],
        rover: Mapping[str, Any],
        elevation: np.ndarray | None = None,
    ) -> None:
        self.rover = rover
        self.resolution = float(grids["metadata"]["resolution_m"])
        self.elevation = np.asarray(
            grids["elevation"] if elevation is None else elevation, dtype=np.float64
        )
        self.traversable = np.asarray(grids["traversable"], dtype=bool)
        thermal = np.asarray(grids["thermal"], dtype=np.float64)
        thermal_min = grids.get("thermal_min")
        self.thermal_min = (
            None if thermal_min is None else np.asarray(thermal_min, dtype=np.float64)
        )
        self.thermal_barrier = _thermal_barrier_grid(
            thermal, rover, thermal_min=self.thermal_min
        )

        self.slope_max_deg = float(rover["slope_max_deg"])
        self.lateral_max_deg = float(rover["slope_lateral_max_deg"])
        self.tan_slope_max = math.tan(math.radians(self.slope_max_deg))
        self.tan_lateral_max_sq = math.tan(math.radians(self.lateral_max_deg)) ** 2

        self.slope_table, self.slope_scale = _barrier_table(self.slope_max_deg)
        self.lateral_table, self.lateral_scale = _barrier_table(self.lateral_max_deg)

        # Same estimator, same NaN handling as the planner.
        grad_row, grad_col = np.gradient(self.elevation, self.resolution)
        self.grad_row = np.nan_to_num(grad_row, nan=0.0)
        self.grad_col = np.nan_to_num(grad_col, nan=0.0)

    def edge(self, u: tuple[int, int], v: tuple[int, int]) -> dict[str, Any]:
        """One edge's geometry, barrier and first failing rule (or None)."""
        dr, dc = v[0] - u[0], v[1] - u[1]
        is_diagonal = abs(dr) + abs(dc) == 2
        dist = self.resolution * (math.sqrt(2.0) if is_diagonal else 1.0)
        if is_diagonal:
            unit_r, unit_c = dr * _R2, dc * _R2
        else:
            unit_r, unit_c = float(dr), float(dc)

        out: dict[str, Any] = {
            "dist_m": dist,
            "is_diagonal": is_diagonal,
            "violated": None,
            "grid_value": None,
            "limit": None,
            "exceedance": None,
            "exceedance_pct": None,
            "along_tan": None,
            "lateral_tan": None,
            "barrier": math.inf,
            "barrier_exact": math.inf,
        }

        # 1. destination traversability. The planner checks the DESTINATION
        #    cell only; the source cell is gated by astar()'s start pre-check,
        #    which this endpoint reaches through _validate_start_goal.
        if not bool(self.traversable[v]):
            out["violated"] = "destination_not_traversable"
            return out

        # 2. diagonal corner-cut -- BEFORE the slope gates, as the planner does.
        if is_diagonal and not (
            bool(self.traversable[u[0], v[1]]) and bool(self.traversable[v[0], u[1]])
        ):
            out["violated"] = "diagonal_corner_cut"
            return out

        # 3. NaN elevation
        dz = float(self.elevation[v]) - float(self.elevation[u])
        if not (dz == dz):
            out["violated"] = "nan_elevation"
            return out

        # 4. along-track step slope
        along_tan = abs(dz) / dist
        out["along_tan"] = along_tan
        if along_tan > self.tan_slope_max:
            out["violated"] = "step_slope"
            out["grid_value"] = math.degrees(math.atan(along_tan))
            out["limit"] = self.slope_max_deg
            out["exceedance"] = out["grid_value"] - self.slope_max_deg
            out["exceedance_pct"] = 100.0 * out["exceedance"] / self.slope_max_deg
            return out

        # 5. cross-track (roll-over) slope
        g_row = 0.5 * (float(self.grad_row[u]) + float(self.grad_row[v]))
        g_col = 0.5 * (float(self.grad_col[u]) + float(self.grad_col[v]))
        lateral_tan = lateral_slope_tan(g_row, g_col, unit_r, unit_c)
        out["lateral_tan"] = lateral_tan
        if lateral_tan * lateral_tan > self.tan_lateral_max_sq:
            out["violated"] = "lateral_slope"
            out["grid_value"] = math.degrees(math.atan(lateral_tan))
            out["limit"] = self.lateral_max_deg
            out["exceedance"] = out["grid_value"] - self.lateral_max_deg
            out["exceedance_pct"] = 100.0 * out["exceedance"] / self.lateral_max_deg
            return out

        # 6. thermal barrier on the destination cell
        thermal_barrier = float(self.thermal_barrier[v])
        if not math.isfinite(thermal_barrier):
            out["violated"] = "thermal_barrier"
            out["limit"] = float(THERMAL_MIN_TRAVERSABLE_C)
            return out

        # 7/8. the tabulated geometric barriers. An edge exactly AT the wall
        #      passes the strict > gate above and dies here instead, which is
        #      why these are separate rules rather than one.
        slope_bin = min(int(along_tan * self.slope_scale), len(self.slope_table) - 1)
        slope_barrier = self.slope_table[slope_bin]
        if not math.isfinite(slope_barrier):
            out["violated"] = "slope_barrier"
            out["grid_value"] = math.degrees(math.atan(along_tan))
            out["limit"] = self.slope_max_deg
            return out
        lateral_bin = min(
            int(lateral_tan * self.lateral_scale), len(self.lateral_table) - 1
        )
        lateral_barrier = self.lateral_table[lateral_bin]
        if not math.isfinite(lateral_barrier):
            out["violated"] = "lateral_barrier"
            out["grid_value"] = math.degrees(math.atan(lateral_tan))
            out["limit"] = self.lateral_max_deg
            return out

        out["barrier"] = thermal_barrier + slope_barrier + lateral_barrier
        # The same barrier without the 1024-bin table. The difference between
        # the two is this model's own discretisation floor, measured rather
        # than assumed (RESOLUTION_LEVELS, "model_discretisation").
        out["barrier_exact"] = thermal_barrier + _geometric_barrier(
            math.degrees(math.atan(along_tan)),
            math.degrees(math.atan(lateral_tan)),
            self.slope_max_deg,
            self.lateral_max_deg,
        )
        return out


def gate_violations(
    model: EdgeModel, route: Sequence[tuple[int, int]], max_reported: int = 50
) -> dict[str, Any]:
    """Every edge of *route* the planner would refuse, and why.

    Reports the FIRST failing rule per edge, because that is what
    ``_astar_core`` does -- it ``continue``s on the first match and never
    evaluates the rest.

    ``grid_value`` is deliberately not called a measurement: it is a number
    read off a loaded raster with a named operator, and the ``source`` field
    on every entry says which array and which operator produced it.
    """
    violations: list[dict[str, Any]] = []
    counts = {rule: 0 for rule in GATE_RULES}
    sources = {g["rule"]: g["source"] for g in GATE_ORDER}
    for index in range(1, len(route)):
        u, v = route[index - 1], route[index]
        edge = model.edge(u, v)
        rule = edge["violated"]
        if rule is None:
            continue
        counts[rule] += 1
        if len(violations) < max_reported:
            violations.append(
                {
                    "edge_index": index,
                    "from_cell": [int(u[0]), int(u[1])],
                    "to_cell": [int(v[0]), int(v[1])],
                    "rule": rule,
                    "source": sources[rule],
                    "grid_value": _finite_or_none(edge["grid_value"]),
                    "limit": _finite_or_none(edge["limit"]),
                    "exceedance": _finite_or_none(edge["exceedance"]),
                    "exceedance_pct": _finite_or_none(edge["exceedance_pct"]),
                    "units": "deg" if rule in ("step_slope", "lateral_slope") else None,
                }
            )
    total = sum(counts.values())
    return {
        "n_violations": total,
        "clean": total == 0,
        "by_rule": counts,
        "violations": violations,
        "violations_truncated": total > len(violations),
        "max_reported": max_reported,
        "rule_order": list(GATE_RULES),
        "barrier_table": {
            "source": "pathfinder._barrier_table",
            "bins": len(model.slope_table),
            "quantised": True,
            "note": (
                "the two barrier rules are decided on a tabulated log-barrier with a "
                "floored index, so their verdict within one bin of the wall is the "
                "tabulated one, not the closed form"
            ),
        },
        "claim": (
            "These are the planner's own gates evaluated on the loaded rasters at "
            + f"{model.resolution:g} m/px, not measurements of the surface. A clear gate "
            "is not a statement that the ground is safe, and a tripped one is not a "
            "statement that it is impassable."
        ),
    }


# ── the criterion integrals ─────────────────────────────────────────────────


def criteria_for_grids(grids: Mapping[str, Any]) -> list[str]:
    """Which criteria this deployment actually prices, in the canonical order.

    Five is a property of THIS DISK, not of the code: without the roughness
    cache the cost grid sums FOUR criteria and ``metadata["cost_criteria"]``
    says so. Hardcoding a five-tuple here would either invent a roughness term
    that steered nothing or crash, because ``f_roughness_grid`` refuses a
    missing scale rather than returning zero. The list comes from the same
    ``cost_criteria_for`` stamp the cost grid carries, so this module and the
    grid can never disagree about what was summed.
    """
    stamped = (grids.get("metadata") or {}).get("cost_criteria")
    if stamped:
        return [str(name) for name in stamped]
    return cost_criteria_for(grids.get("roughness") is not None)


def _roughness_scale(grids: Mapping[str, Any]) -> RoughnessScale | None:
    meta = (grids.get("metadata") or {}).get("roughness") or {}
    return RoughnessScale.from_meta(meta.get("scale"))


def criterion_penalties(
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    cells: Sequence[tuple[int, int]],
    risk_alpha: float | None = None,
) -> dict[str, np.ndarray]:
    """The UNWEIGHTED penalty f_k at each cell of *cells*, per criterion.

    Evaluated on the route's cells only rather than on the whole grid: these
    are the same array forms ``compute_cost_grid`` calls, so the values are
    bit-identical to the ones in the cost grid (asserted on the real grid),
    and slicing first keeps this O(len(route)) instead of O(H*W).

    Unweighted on purpose. ``CostMap.explain`` returns WEIGHTED contributions
    and ``None`` for non-finite ones, which is right for a cell card and wrong
    here: the whole point is to vary w_k, so the f_k must be held separately
    from the weight that scales them, and w_k = 0 is a legal weight whose
    product would erase the criterion's integral.
    """
    rows = np.array([c[0] for c in cells], dtype=np.intp)
    cols = np.array([c[1] for c in cells], dtype=np.intp)
    slope = np.asarray(grids["slope"], dtype=np.float64)[rows, cols]
    thermal = np.asarray(grids["thermal"], dtype=np.float64)[rows, cols]
    shadow = np.asarray(grids["shadow_ratio"], dtype=np.float64)[rows, cols]
    thermal_min_grid = grids.get("thermal_min")
    thermal_min = (
        None
        if thermal_min_grid is None
        else np.asarray(thermal_min_grid, dtype=np.float64)[rows, cols]
    )
    slope_sigma_grid = grids.get("slope_sigma")
    slope_sigma = (
        None
        if slope_sigma_grid is None or risk_alpha is None
        else np.asarray(slope_sigma_grid, dtype=np.float64)[rows, cols]
    )

    out: dict[str, np.ndarray] = {}
    for name in criteria_for_grids(grids):
        if name == "slope":
            out[name] = f_slope_grid(
                slope, rover, risk_alpha=risk_alpha, slope_sigma=slope_sigma
            )
        elif name == "energy":
            out[name] = f_energy_cell_grid(
                slope, rover, shadow, risk_alpha=risk_alpha, slope_sigma=slope_sigma
            )
        elif name == "shadow":
            out[name] = f_shadow_cell_grid(shadow)
        elif name == "thermal":
            out[name] = f_thermal_grid(thermal, rover, thermal_min)
        elif name == "roughness":
            roughness_grid = grids.get("roughness")
            scale = _roughness_scale(grids)
            if roughness_grid is None or scale is None:
                raise ValueError(
                    "the cost grid is stamped with a roughness criterion but the grids "
                    "carry no roughness layer or no scale; rebuild the cache"
                )
            out[name] = f_roughness_grid(
                np.asarray(roughness_grid, dtype=np.float64)[rows, cols], scale
            )
        else:
            raise ValueError(f"unknown cost criterion {name!r}")
    return out


class RouteTerms:
    """One route's weight-independent decomposition.

    ``D`` (distance), ``I`` (per-criterion trapezoidal integrals) and ``B``
    (barrier) are all independent of the weight vector, so they are computed
    once and then every weight question is arithmetic on them.
    """

    def __init__(
        self,
        cells: Sequence[tuple[int, int]],
        dist: np.ndarray,
        penalties: Mapping[str, np.ndarray],
        barrier_total: float,
        barrier_total_exact: float,
        gates: Mapping[str, Any],
    ) -> None:
        self.cells = list(cells)
        self.dist = dist
        self.penalties = dict(penalties)
        self.D = float(dist.sum())
        self.B = float(barrier_total)
        self.B_exact = float(barrier_total_exact)
        self.gates = dict(gates)
        # The trapezoidal line integral of each unweighted penalty. Summing
        # the CELL values instead would be a different and wrong quantity:
        # the cost is a line integral, its edge term is the mean of the two
        # endpoints times the step length, and diagonal steps are sqrt(2)
        # longer than cardinal ones.
        self.I = {
            name: float(np.sum(dist * 0.5 * (values[:-1] + values[1:])))
            for name, values in self.penalties.items()
        }

    @property
    def criteria(self) -> list[str]:
        return list(self.I.keys())

    def weighted_sum_per_cell(self, weights: Mapping[str, float]) -> np.ndarray:
        """``sum_k w_k f_k`` at every cell -- the pre-clamp cell cost."""
        total = np.zeros(len(self.cells), dtype=np.float64)
        for name, values in self.penalties.items():
            total = total + float(weights[CRITERION_WEIGHT_KEY[name]]) * values
        return total

    def clamp_margin(self, weights: Mapping[str, float]) -> float:
        """How far the cheapest route cell sits above ``MIN_CELL_COST``.

        Below 1.0 the clamp binds and the affine identity -- with everything
        derived from it -- stops holding on this route at this weight.
        """
        raw = self.weighted_sum_per_cell(weights)
        return float(raw.min()) / MIN_CELL_COST if raw.size else math.inf

    def clamped_cells(self, weights: Mapping[str, float]) -> int:
        raw = self.weighted_sum_per_cell(weights)
        return int(np.sum(raw < MIN_CELL_COST))

    def affine_cost(self, weights: Mapping[str, float]) -> float:
        """``D + sum_k w_k I_k + B`` -- valid only where the clamp is clear."""
        return (
            self.D
            + sum(
                float(weights[CRITERION_WEIGHT_KEY[name]]) * value
                for name, value in self.I.items()
            )
            + self.B
        )

    def exact_cost(self, weights: Mapping[str, float]) -> float:
        """The route's g-score WITH the clamp applied, valid at every weight.

        Used to check the affine form rather than to replace it: the affine
        form is what makes the counterfactual a closed form, and this is how
        the module knows when that form has stopped being true.
        """
        cell = np.maximum(self.weighted_sum_per_cell(weights), MIN_CELL_COST)
        return float(np.sum(self.dist * (1.0 + 0.5 * (cell[:-1] + cell[1:])))) + self.B


def route_terms(
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    cells: Sequence[tuple[int, int]],
    model: EdgeModel,
    max_reported_violations: int = 50,
    risk_alpha: float | None = None,
) -> RouteTerms:
    """Integrate one route: distance, per-criterion penalties, barrier, gates.

    A gated edge has an infinite barrier, so ``B`` is infinite for any route
    that trips a gate -- which is correct (the planner would never take it)
    and is why the caller must read ``gates["clean"]`` before reading any
    cost. Nothing infinite reaches a response: the top level suppresses the
    cost blocks entirely when the gates are dirty.
    """
    penalties = criterion_penalties(grids, rover, cells, risk_alpha=risk_alpha)
    dist = np.empty(len(cells) - 1, dtype=np.float64)
    barrier_total = 0.0
    barrier_total_exact = 0.0
    for index in range(1, len(cells)):
        edge = model.edge(cells[index - 1], cells[index])
        dist[index - 1] = edge["dist_m"]
        barrier_total += edge["dist_m"] * edge["barrier"]
        barrier_total_exact += edge["dist_m"] * edge["barrier_exact"]
    gates = gate_violations(model, cells, max_reported=max_reported_violations)
    return RouteTerms(cells, dist, penalties, barrier_total, barrier_total_exact, gates)


# ── (b) the criterion-by-criterion gap ──────────────────────────────────────


def criterion_gap(
    fact: RouteTerms, foil: RouteTerms, weights: Mapping[str, float]
) -> dict[str, Any]:
    """Where the foil's extra cost actually goes, term by term.

    The decomposition is COMPLETE and exact: ``delta_distance +
    delta_barrier + sum_k w_k * delta_I_k`` is the whole difference in the
    g-score A* minimised, with no residual. The barrier is published as its
    own term rather than folded into the criteria, because it is 12-15
    percent of the objective on this site and it is the one term no weight
    can touch.

    ``total_weighted_cost`` (barrier included), not
    ``total_weighted_cost_cells_only``: the former is what the search
    minimised and therefore what "why did you not pick mine" is about.

    Every number here is a float64 difference of integrals this module
    computed itself. Nothing is obtained by subtracting two of the API's
    published, already-rounded fields, which is what retires the publication
    resolution floor.
    """
    terms: list[dict[str, Any]] = []
    for name in fact.criteria:
        fact_i, foil_i = fact.I[name], foil.I[name]
        weight = float(weights[CRITERION_WEIGHT_KEY[name]])
        delta_i = foil_i - fact_i
        terms.append(
            {
                "criterion": name,
                "weight_key": CRITERION_WEIGHT_KEY[name],
                "weight": weight,
                "fact_integral": fact_i,
                "foil_integral": foil_i,
                "delta_integral": delta_i,
                "delta_weighted": weight * delta_i,
                "foil_is_cheaper": delta_i < 0.0,
                "units": "weighted_metres (unweighted penalty integrated over the route)",
            }
        )
    delta_distance = foil.D - fact.D
    delta_barrier = foil.B - fact.B
    total = delta_distance + delta_barrier + sum(t["delta_weighted"] for t in terms)
    return {
        "criteria": terms,
        "delta_distance": delta_distance,
        "delta_barrier": delta_barrier,
        "delta_total": total,
        "fact_total": fact.affine_cost(weights),
        "foil_total": foil.affine_cost(weights),
        "cost_units": "weighted_metres",
        "basis": "total_weighted_cost",
        "note": (
            "delta_distance + delta_barrier + sum_k w_k * delta_integral_k = delta_total "
            "exactly. The barrier is weight-independent, so no weight change can move "
            "that part of the gap; the distance term is weight-independent too."
        ),
    }


# ── (c) the weight counterfactual ───────────────────────────────────────────


def flip_threshold_vs_fact(
    fact: RouteTerms,
    foil: RouteTerms,
    weights: Mapping[str, float],
    criterion: str,
    leverage_floor: float,
) -> dict[str, Any]:
    """Where one weight must go for the foil to undercut THIS fact.

    Closed form, because the cost is affine in the weights::

        delta(w_k) = delta0 + (w_k - w_k0) * delta_I_k   =>   w_k* = w_k0 - delta0 / delta_I_k

    The sign of ``delta_I_k`` sets the DIRECTION, and getting it wrong sends
    the regime-(ii) scan into the half of the axis that is provably empty:
    ``delta0 >= 0`` (A* optimality), so ``delta_I_k > 0`` -- the foil spends
    MORE of this criterion -- means the weight must come DOWN, and the root
    lies below ``w_k0``; ``delta_I_k < 0`` means it must go UP.

    This is a one-dimensional section of an inverse-optimisation problem, not
    its solution: the other four weights are pinned at their current values
    and no norm is minimised. :func:`l2_minimal_joint_move` gives the honest
    norm-minimiser for the same regime.
    """
    weight_key = CRITERION_WEIGHT_KEY[criterion]
    w0 = float(weights[weight_key])
    delta0 = foil.affine_cost(weights) - fact.affine_cost(weights)
    delta_i = foil.I[criterion] - fact.I[criterion]

    out: dict[str, Any] = {
        "criterion": criterion,
        "weight_key": weight_key,
        "current_weight": w0,
        "delta_integral": delta_i,
        "gap_at_current_weight": delta0,
        "regime": "vs_fact",
        "threshold": None,
        "direction": None,
        "predicate": None,
        "outcome": None,
        "winning_interval": None,
    }

    # No leverage: moving this weight across its entire legal range cannot
    # move the comparison by a publishable amount. Reported as its own case --
    # a bare division here is a ZeroDivisionError or a NaN, and a NaN in the
    # response is a 500 rather than an answer.
    if abs(delta_i) <= leverage_floor:
        out["outcome"] = OUTCOME_NO_LEVERAGE
        out["leverage_floor"] = leverage_floor
        out["note"] = (
            "the two routes integrate this criterion to within the floor, so no value "
            "of this weight changes which one is cheaper"
        )
        return out

    threshold = w0 - delta0 / delta_i
    decrease = delta_i > 0.0
    out["threshold"] = threshold
    out["direction"] = "decrease" if decrease else "increase"
    out["predicate"] = (
        f"{weight_key} <= {threshold:.6g}" if decrease else f"{weight_key} >= {threshold:.6g}"
    )
    # The half-line on which the foil undercuts the fact, clipped to the box
    # PlanWeights allows. This is also the ONLY region regime (ii) can win in,
    # because delta_ii >= delta_i pointwise.
    if decrease:
        out["winning_interval"] = [WEIGHT_MIN, min(threshold, WEIGHT_MAX)]
    else:
        out["winning_interval"] = [max(threshold, WEIGHT_MIN), WEIGHT_MAX]

    if not (WEIGHT_MIN <= threshold <= WEIGHT_MAX):
        out["outcome"] = OUTCOME_OUTSIDE_BOUNDS
        out["winning_interval"] = None
        out["note"] = (
            f"the root lies at {threshold:.6g}, outside PlanWeights' own "
            f"[{WEIGHT_MIN}, {WEIGHT_MAX}]. Because delta_vs_replanned >= delta_vs_fact "
            "everywhere, no weight in bounds makes the planner return the foil either -- "
            "that is proved here, not searched."
        )
        return out

    # The closed form is a statement about the AFFINE branch, so it is only an
    # answer if the clamp is still clear at the weight it points to. Checking
    # it at w0 alone and then reasoning across the whole box would publish a
    # number computed by a formula that had stopped applying.
    trial = dict(weights)
    trial[weight_key] = threshold
    fact_margin = fact.clamp_margin(trial)
    foil_margin = foil.clamp_margin(trial)
    out["clamp_margin_at_threshold"] = min(fact_margin, foil_margin)
    if fact_margin < 1.0 or foil_margin < 1.0:
        out["outcome"] = OUTCOME_CLAMP_BINDS
        out["note"] = (
            "the MIN_CELL_COST clamp binds on at least one route cell at this weight, so "
            "the cost is no longer affine there and the closed-form root is not the "
            "crossing point. No threshold is published."
        )
        return out

    out["outcome"] = OUTCOME_FOUND_VS_FACT
    out["note"] = (
        "at this weight the foil costs LESS THAN THE ROUTE SHOWN. It does not follow "
        "that the planner would return the foil: at that weight it re-ranks every route "
        "and generally returns a third one. See the vs_replanned block."
    )
    return out


def l2_minimal_joint_move(
    fact: RouteTerms, foil: RouteTerms, weights: Mapping[str, float]
) -> dict[str, Any]:
    """The smallest joint weight change (in l2) that flips the vs_fact comparison.

    The per-criterion thresholds are five different one-dimensional sections
    and their minimum is NOT the minimum over the weight box: a joint move can
    be strictly smaller than any single-coordinate one. For the affine regime
    the norm-minimiser is exact and one line -- the projection of the current
    weight vector onto the hyperplane ``delta(w) = 0`` -- so it is published
    beside them rather than left as a caveat.

    Reported with the clip to [0, 2] applied and flagged when the clip bites,
    because a clipped projection is no longer the minimiser.
    """
    delta0 = foil.affine_cost(weights) - fact.affine_cost(weights)
    gradient = {name: foil.I[name] - fact.I[name] for name in fact.criteria}
    norm_sq = sum(value * value for value in gradient.values())
    if norm_sq <= 0.0:
        return {
            "available": False,
            "reason": (
                "the two routes integrate every criterion identically, so no weight "
                "vector separates them"
            ),
        }
    step = -delta0 / norm_sq
    move = {name: step * value for name, value in gradient.items()}
    proposed: dict[str, float] = {}
    clipped = False
    for name, offset in move.items():
        key = CRITERION_WEIGHT_KEY[name]
        raw = float(weights[key]) + offset
        bounded = min(max(raw, WEIGHT_MIN), WEIGHT_MAX)
        clipped = clipped or bounded != raw
        proposed[key] = bounded
    return {
        "available": True,
        "l2_distance": abs(step) * math.sqrt(norm_sq),
        "move": {CRITERION_WEIGHT_KEY[k]: v for k, v in move.items()},
        "proposed_weights": proposed,
        "clipped_to_bounds": clipped,
        "note": (
            "the l2-minimal adjustment that makes the foil tie the fact, i.e. the "
            "projection onto the hyperplane delta = 0. Exact only while the "
            "MIN_CELL_COST clamp stays clear; if clipped_to_bounds is true the clipped "
            "vector is no longer the minimiser and generally does not tie."
        ),
    }


def scan_vs_replanned(
    base_grids: Mapping[str, Any],
    rover_id: str,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    start: tuple[int, int],
    goal: tuple[int, int],
    foil: RouteTerms,
    foil_route_id: str,
    model: EdgeModel,
    criterion: str,
    interval: Sequence[float],
    scan_points: int,
    win_tolerance: float,
    budget: list[int],
) -> dict[str, Any]:
    """Does the planner ever RETURN the foil as this one weight moves?

    Scans the interval on which the foil undercuts the fact -- the only region
    where this can happen, since ``delta_vs_replanned >= delta_vs_fact``
    pointwise -- and reports what it saw at every point.

    Not a binary search, and not because of latency. ``delta_vs_replanned`` is
    convex in the weight, so its zero set is an INTERVAL: "does the foil win"
    is not a monotone predicate and there is no threshold for a bisection to
    converge on. Measured on Site11 those intervals can be as narrow as 0.005
    on a [0, 2] axis, so a latency-capped uniform scan is close to blind --
    which is why a scan that sees nothing is published with its step and the
    narrowest interval it could have resolved, and never as a bare negative.

    Both sides of every comparison are integrated by THIS module over the same
    grids, so nothing here differences a reconstructed number against a
    published rounded one.
    """
    weight_key = CRITERION_WEIGHT_KEY[criterion]
    low, high = float(interval[0]), float(interval[1])
    if not (high > low):
        return {
            "regime": "vs_replanned",
            "outcome": OUTCOME_UNRESOLVED_BY_SCAN,
            "reason": "the vs_fact winning interval is empty",
            "points": [],
        }
    step = (high - low) / max(scan_points - 1, 1)
    points: list[dict[str, Any]] = []
    hits: list[float] = []

    for index in range(scan_points):
        if budget[0] <= 0:
            break
        value = low + index * step
        budget[0] -= 1
        trial = dict(weights)
        trial[weight_key] = value
        grids = grids_for_rover(base_grids, rover_id, dict(trial))
        result = astar(grids, start, goal, weights=dict(trial), rover=rover)
        clamp_margin = foil.clamp_margin(trial)
        entry: dict[str, Any] = {
            "weight": value,
            "error": result.get("error"),
            "returned_foil": False,
            "delta_vs_replanned": None,
            "returned_route_id": None,
            "clamp_margin_foil": clamp_margin,
            # Below 1.0 the cost stops being affine here, so the convexity that
            # makes the winning set an interval is not guaranteed at this point
            # and the gap is reported without being counted as a hit.
            "clamp_binds": clamp_margin < 1.0,
        }
        if not result.get("error"):
            cells = [(int(r), int(c)) for r, c in result["path_pixels"]]
            returned = route_id(result["path_pixels"])
            entry["returned_route_id"] = returned
            optimum = route_terms(
                grids, rover, cells, model, max_reported_violations=0
            )
            gap = foil.exact_cost(trial) - optimum.exact_cost(trial)
            entry["delta_vs_replanned"] = gap
            entry["returned_foil"] = bool(
                returned == foil_route_id
                or (gap <= win_tolerance and not entry["clamp_binds"])
            )
            entry["matched_by"] = (
                "route_id" if returned == foil_route_id
                else ("tolerance" if gap <= win_tolerance else None)
            )
        if entry["returned_foil"]:
            hits.append(value)
        points.append(entry)

    out: dict[str, Any] = {
        "regime": "vs_replanned",
        "weight_key": weight_key,
        "scanned_interval": [low, high],
        "scan_points": len(points),
        "scan_step": step,
        "win_tolerance": win_tolerance,
        "points": points,
        "n_replans": len(points),
        "clamped_points": sum(1 for p in points if p.get("clamp_binds")),
    }
    if hits:
        out["outcome"] = OUTCOME_FOUND_REPLANNED
        out["returned_at"] = hits
        out["bounded_interval"] = [min(hits), max(hits)]
        out["note"] = (
            "the planner actually returned the foil at these weights. The interval is "
            "bounded by the scan, not resolved by it: its true edges lie within one "
            "scan step of the outermost hits."
        )
    else:
        out["outcome"] = OUTCOME_UNRESOLVED_BY_SCAN
        out["smallest_resolvable_interval"] = step
        out["note"] = (
            f"the planner did not return the foil at any of {len(points)} points spaced "
            f"{step:.6g} apart. This is NOT a proof that no such weight exists: the "
            "winning set is an interval and one narrower than the scan step would not "
            "be seen. Measured on Site11, real winning intervals have been as narrow as "
            "0.005 on this axis."
        )
    return out


# ── the terrain the numbers are computed on ─────────────────────────────────


def terrain_band(
    base_grids: Mapping[str, Any],
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    fact_cells: Sequence[tuple[int, int]],
    foil_cells: Sequence[tuple[int, int]],
    clones: np.ndarray,
    clone_meta: Mapping[str, Any],
    max_clones: int,
) -> dict[str, Any]:
    """The gap, recomputed on each of NASA's own DEM error realisations.

    This is the band that matters, and it is the reason this feature does not
    publish a bare threshold. ``risk_alpha`` -- the obvious candidate -- is NOT
    an uncertainty: ``risk.py`` calls it the operator's risk APPETITE, its
    smallest admissible member is already mu + 0.798 sigma so it never
    brackets the nominal, and it reaches only the slope and energy criteria,
    which on this site are a small fraction of the objective. The clone
    ensemble perturbs the ELEVATION FIELD, so it moves the barrier, the gates
    and the slope-derived criteria together, which is what an input
    uncertainty on this cost actually looks like.

    What it still does not cover, said out loud: the thermal, shadow and
    roughness layers are separate products and are NOT perturbed here, and a
    20-clone ensemble carries roughly +/-16 percent of sampling error on its
    own standard deviation.
    """
    from .uncertainty import ensemble_slopes

    resolution = float(grids["metadata"]["resolution_m"])
    n_clones = min(int(max_clones), int(clones.shape[0]))
    # The pipeline's own slope operator, so a clone's slope grid is
    # produced exactly the way the nominal one was.
    slopes = ensemble_slopes(np.asarray(clones[:n_clones]), resolution)

    deltas: list[float] = []
    entries: list[dict[str, Any]] = []
    for index in range(n_clones):
        elevation = np.asarray(clones[index], dtype=np.float64)
        clone_grids = dict(grids)
        clone_grids["elevation"] = elevation
        clone_grids["slope"] = np.asarray(slopes[index], dtype=np.float64)
        clone_model = EdgeModel(clone_grids, rover, elevation=elevation)
        fact_terms = route_terms(
            clone_grids, rover, fact_cells, clone_model, max_reported_violations=0
        )
        foil_terms = route_terms(
            clone_grids, rover, foil_cells, clone_model, max_reported_violations=0
        )
        fact_clean = fact_terms.gates["clean"]
        foil_clean = foil_terms.gates["clean"]
        gap: float | None = None
        if fact_clean and foil_clean:
            # exact_cost, not affine_cost: a clone moves the slope grid, so the
            # MIN_CELL_COST margin moves with it and the affine branch is not
            # guaranteed on every realisation.
            gap = foil_terms.exact_cost(weights) - fact_terms.exact_cost(weights)
            deltas.append(gap)
        entries.append(
            {
                "clone": index,
                "delta": gap,
                "fact_gates_clean": fact_clean,
                "foil_gates_clean": foil_clean,
                "fact_violations": fact_terms.gates["n_violations"],
                "foil_violations": foil_terms.gates["n_violations"],
            }
        )

    nominal_gap = None
    try:
        nominal_fact = route_terms(grids, rover, fact_cells, EdgeModel(grids, rover), 0)
        nominal_foil = route_terms(grids, rover, foil_cells, EdgeModel(grids, rover), 0)
        if nominal_fact.gates["clean"] and nominal_foil.gates["clean"]:
            nominal_gap = nominal_foil.exact_cost(weights) - nominal_fact.exact_cost(weights)
    except Exception:  # noqa: BLE001 - the band is context, never fatal
        nominal_gap = None

    array = np.array(deltas, dtype=np.float64)
    summary: dict[str, Any] = {
        "n_clones": n_clones,
        "n_usable": int(array.size),
        "provenance": clone_meta.get("provenance"),
        "product_url": clone_meta.get("product_url"),
        "reference": clone_meta.get("reference"),
        "validity": "MODEL",
        "clones": entries,
        "covers": ["elevation", "slope", "energy", "barrier", "hard_gates", "distance"],
        "does_not_cover": ["thermal", "shadow", "roughness"],
        "note": (
            "Each clone is NASA's surface DEM plus one error realisation, so this band "
            "is the spread the gap inherits from the topography being uncertain. The "
            "thermal, shadow and roughness layers are separate products and are held "
            "fixed. With this many clones the standard deviation carries roughly "
            "+/-16 percent of its own sampling error."
        ),
    }
    summary["nominal_gap"] = nominal_gap
    if array.size:
        summary.update(
            {
                "mean": float(array.mean()),
                "sd": float(array.std(ddof=1)) if array.size > 1 else 0.0,
                "min": float(array.min()),
                "max": float(array.max()),
                "n_negative": int(np.sum(array < 0.0)),
                "n_positive": int(np.sum(array > 0.0)),
            }
        )
        # How often NASA's own error realisations disagree with the nominal
        # DEM about WHICH ROUTE IS CHEAPER. This is the number that decides
        # whether a weight threshold is worth printing as an instruction.
        summary["sign_flips"] = int(min(summary["n_negative"], summary["n_positive"]))
        if nominal_gap is not None:
            summary["clones_disagreeing_with_nominal_sign"] = int(
                np.sum(np.sign(array) != np.sign(nominal_gap))
            )
            summary["nominal_inside_ensemble_range"] = bool(
                summary["min"] <= nominal_gap <= summary["max"]
            )
            summary["nominal_minus_ensemble_mean"] = float(nominal_gap - summary["mean"])
    summary["fact_gate_failures"] = sum(
        0 if entry["fact_gates_clean"] else 1 for entry in entries
    )
    summary["foil_gate_failures"] = sum(
        0 if entry["foil_gates_clean"] else 1 for entry in entries
    )
    return summary


def resolution_report(
    gap: float, model_floor: float, terrain_sd: float | None
) -> dict[str, Any]:
    """Where a gap stands against each of the model's four resolution floors.

    A vector, not a word. Measured on Site11 the floors differ by nine orders
    of magnitude and one real gap was 475x the publication floor, 33x the
    barrier floor and 0.03 sigma of the terrain ensemble -- "resolved",
    "resolved" and "not resolved" for the same number. One verdict cannot
    carry that, so each level gets its own and the headline names its level.
    """
    magnitude = abs(float(gap))
    floors: dict[str, float | None] = {
        "arithmetic": 1e-10,
        "publication": 1e-4,
        "model_discretisation": abs(float(model_floor)),
        "terrain_ensemble": None if terrain_sd is None else abs(float(terrain_sd)),
    }
    levels: list[dict[str, Any]] = []
    coarsest_failed: str | None = None
    for entry in RESOLUTION_LEVELS:
        name = str(entry["level"])
        floor = floors.get(name)
        if floor is None:
            levels.append(
                {
                    "level": name,
                    "floor": None,
                    "ratio": None,
                    "resolved": None,
                    "what": entry["what"],
                    "source": entry["source"],
                }
            )
            continue
        threshold = RESOLUTION_SAFETY_FACTOR * floor
        resolved = magnitude > threshold
        levels.append(
            {
                "level": name,
                "floor": floor,
                "ratio": (magnitude / floor) if floor > 0.0 else None,
                "resolved": resolved,
                "what": entry["what"],
                "source": entry["source"],
            }
        )
        if not resolved:
            coarsest_failed = name
    return {
        "gap": float(gap),
        "gap_abs": magnitude,
        "safety_factor": RESOLUTION_SAFETY_FACTOR,
        "levels": levels,
        "headline": (
            "resolved_at_every_level"
            if coarsest_failed is None
            else f"closer_than_the_model_resolves(level={coarsest_failed})"
        ),
        "actionable": coarsest_failed is None,
        "note": (
            "A gap is called resolved at a level when it exceeds "
            f"{RESOLUTION_SAFETY_FACTOR:g}x that level's floor. The factor is a stated "
            "convention, not a derivation. A weight threshold whose gap is not resolved "
            "at the terrain level is printed but is NOT an operating instruction."
        ),
    }


# ── the route-level outcomes (D5's space, not this module's) ────────────────


def objective_gap(
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    fact_cells: Sequence[tuple[int, int]],
    foil_cells: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    """The same pair of routes in D5's four ROUTE-LEVEL objectives.

    A separate block on purpose. The five cost criteria and D5's four
    objectives are different spaces, so ``pareto.dominates()`` does not
    transfer to the criterion-space question this module asks -- but it is
    exactly right for this one, and reusing it keeps one dominance rule and
    one set of quanta in the repo rather than two.

    The boolean alone would hide the thing that matters. ``dominates`` decides
    at each field's publication quantum, so "does not dominate" can mean
    genuinely incomparable OR separated by less than one reporting unit, which
    are opposite findings. Every objective therefore carries its signed
    difference AND its distance in whole quanta, and the epsilon ties are
    named.

    This block is also the only place the gap appears in PHYSICAL units, and
    it is NOT a translation of the weighted-metre gap: measured on Site11 the
    two do not agree even in sign, because the 2-D planner minimises weighted
    metres and a foil can cost more while being faster.
    """
    from .simulation import simulate_path, summarize_simulation

    def summarise(cells: Sequence[tuple[int, int]]) -> dict[str, Any] | None:
        result = {
            "path_pixels": [[int(r), int(c)] for r, c in cells],
            "metrics": {},
            "error": None,
        }
        states = simulate_path(
            result,
            grids["cost"],
            grids["slope"],
            grids["thermal"],
            grids["shadow_ratio"],
            rover=rover,
            pixel_size_m=float(grids["metadata"]["resolution_m"]),
            elevation_grid=grids["elevation"],
        )
        return summarize_simulation(states, rover)

    fact_summary = summarise(fact_cells)
    foil_summary = summarise(foil_cells)

    def vector(summary: Mapping[str, Any]) -> dict[str, float]:
        return {
            "hours": float(summary["total_elapsed_hours"]),
            "energy_wh": float(summary["total_energy_consumed_wh"]),
            "shadow_exposure_h": float(summary["total_shadow_exposure"]),
        }

    fact_vector, foil_vector = vector(fact_summary), vector(foil_summary)
    objectives: list[dict[str, Any]] = []
    for entry in PARETO_OBJECTIVES:
        key = str(entry["key"])
        if key not in fact_vector:
            # thermal_risk comes from the A* metrics, not the simulation
            # summary; it is left out here rather than guessed at.
            continue
        quantum = OBJECTIVE_QUANTUM[key]
        delta = foil_vector[key] - fact_vector[key]
        objectives.append(
            {
                "key": key,
                "unit": entry["unit"],
                "direction": entry["direction"],
                "fact": fact_vector[key],
                "foil": foil_vector[key],
                "delta": delta,
                "quantum": quantum,
                "delta_in_quanta": abs(delta) / quantum if quantum else None,
                "epsilon_tie": abs(delta) <= quantum,
                "foil_is_better": delta < 0.0,
            }
        )
    return {
        "objectives": objectives,
        "fact_stranded": bool(fact_summary["stranded"]),
        "foil_stranded": bool(foil_summary["stranded"]),
        "note": (
            "Route-level outcomes, NOT a conversion of the weighted-metre gap. The 2-D "
            "planner minimises weighted metres, which has no physical dimension, so a "
            "foil that costs more can be faster and that is an expected outcome rather "
            "than a bug. Differences are decided at each field's own publication "
            "quantum, so a margin near one quantum is not an ordering."
        ),
    }


# ── the whole answer ────────────────────────────────────────────────────────


def explain_contrast(
    base_grids: Mapping[str, Any],
    start: tuple[int, int],
    goal: tuple[int, int],
    rover_id: str,
    rover: Mapping[str, Any],
    foil_cells: Sequence[tuple[int, int]],
    weights: Mapping[str, float] | None = None,
    risk_alpha: float | None = None,
    scan_points: int = 6,
    max_replans: int = 30,
    max_reported_violations: int = 50,
    clone_band: bool = True,
    max_clones: int = 20,
    win_tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Why the planner's route, and why not this one.

    Order of business, and each step can end the answer:

    1. Plan the FACT. No route means there is nothing to contrast against and
       every delta is undefined -- reported as :data:`OUTCOME_NO_INCUMBENT`,
       not as a zero.
    2. Replay the planner's gates over the FOIL. A tripped gate makes the
       weight question moot, so parts (b) and (c) are suppressed explicitly
       rather than filled with numbers computed from an infinite barrier.
    3. Decompose both routes and check the clamp. Everything downstream is
       affine arithmetic on those terms.
    4. Answer the counterfactual in both regimes, and measure the gap against
       all four resolution floors.
    """
    started = time.perf_counter()
    resolved = resolve_weights(dict(weights) if weights else None, rover)
    grids = grids_for_rover(base_grids, rover_id, dict(resolved), risk_alpha=risk_alpha)
    model = EdgeModel(grids, rover)

    # Declared up front, in one place, so every exit path -- gated foil, no
    # incumbent, foil-is-the-fact, clamp -- carries the same keys as the full
    # answer with nulls where a block does not apply. A response whose shape
    # depends on its outcome forces the client to guess which keys exist.
    response: dict[str, Any] = {
        "criterion_gap": None,
        "counterfactual": None,
        "dominance": None,
        "clamp": None,
        "terrain_band": None,
        "objective_gap": None,
        "objective_dominance": None,
        "resolution": None,
        "suppressed_because": None,
        "inconsistency": None,
        "method_id": CONTRAST_METHOD_ID,
        "planner": "2d",
        "cost_units": "weighted_metres",
        "rover_id": rover_id,
        "weights": dict(resolved),
        "risk_alpha": None if risk_alpha is None else float(risk_alpha),
        "start": [int(start[0]), int(start[1])],
        "goal": [int(goal[0]), int(goal[1])],
        "criteria": criteria_for_grids(grids),
        "vocabulary": {
            "fact": "the route the planner produced (Krarup et al.: the plan)",
            "foil": (
                "the route supplied instead -- a TOTAL foil (a complete cell "
                "sequence), where the XAIP literature's foils are normally partial "
                "and its FQ1-FQ7 taxonomy asks about single actions. A whole-route "
                "foil is not one of those questions."
            ),
        },
        "validity": CONTRAST_VALIDITY,
        "claim": CONTRAST_CLAIM,
        "references": [dict(r) for r in CONTRAST_REFERENCES],
    }

    # 1. the fact
    fact_result = astar(grids, tuple(start), tuple(goal), weights=dict(resolved), rover=rover)
    if fact_result.get("error"):
        foil_terms = route_terms(
            grids, rover, list(foil_cells), model, max_reported_violations, risk_alpha
        )
        response.update(
            {
                "outcome": OUTCOME_NO_INCUMBENT,
                "fact": {"error": str(fact_result["error"]),
                         "edges_rejected": fact_result["metrics"].get("edges_rejected", {})},
                "foil": {
                    "route_id": route_id([list(c) for c in foil_cells]),
                    "n_cells": len(foil_cells),
                    "gate_violations": foil_terms.gates,
                    "distance_m": foil_terms.D,
                    "criterion_integrals": dict(foil_terms.I),
                    "barrier": _finite_or_none(foil_terms.B),
                },
                "suppressed_because": (
                    "the planner found no route for this pair, so there is no fact to "
                    "contrast against and every difference is undefined"
                ),
                # A* is complete on this graph, so no route means every path from start
                # to goal trips a gate -- and the foil is such a path. A gate-clean foil
                # here would mean the replay and the planner disagree.
                "inconsistency": bool(foil_terms.gates["clean"]),
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
        return response

    fact_cells = [(int(r), int(c)) for r, c in fact_result["path_pixels"]]
    fact_terms = route_terms(grids, rover, fact_cells, model, 0, risk_alpha)
    foil_terms = route_terms(
        grids, rover, list(foil_cells), model, max_reported_violations, risk_alpha
    )
    foil_id = route_id([list(c) for c in foil_cells])

    response["fact"] = {
        "route_id": route_id(fact_result["path_pixels"]),
        "n_cells": len(fact_cells),
        "path_pixels": [[int(r), int(c)] for r, c in fact_cells],
        "total_weighted_cost": fact_result["metrics"]["total_weighted_cost"],
        "gate_violations": fact_terms.gates,
    }
    response["foil"] = {
        "route_id": foil_id,
        "n_cells": len(foil_cells),
        "gate_violations": foil_terms.gates,
        "is_the_fact": foil_id == response["fact"]["route_id"],
    }

    # 2. a tripped gate ends the weight question
    if not foil_terms.gates["clean"]:
        response.update(
            {
                "outcome": OUTCOME_HARD_GATE,
                "suppressed_because": (
                    "the foil trips gates the planner enforces independently of the "
                    "weights, so no weight change can make the planner return it and no "
                    "threshold is computed. The cost difference is undefined as well: a "
                    "gated edge carries an infinite barrier."
                ),
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
        return response

    # 2b. the foil IS the fact: every difference is exactly zero and there is
    #     no counterfactual to answer, so none is manufactured.
    if response["foil"]["is_the_fact"]:
        response.update(
            {
                "outcome": OUTCOME_FOIL_IS_THE_FACT,
                "criterion_gap": criterion_gap(fact_terms, foil_terms, resolved),
                "suppressed_because": (
                    "the foil is the same cell sequence as the fact, so every "
                    "difference is exactly zero and there is no weight question to ask"
                ),
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
        return response

    # 3. the clamp, which is the identity's precondition
    clamp = {
        "min_cell_cost": MIN_CELL_COST,
        "fact_margin": fact_terms.clamp_margin(resolved),
        "foil_margin": foil_terms.clamp_margin(resolved),
        "fact_clamped_cells": fact_terms.clamped_cells(resolved),
        "foil_clamped_cells": foil_terms.clamped_cells(resolved),
        "note": (
            "the affine identity -- and the convexity argument behind the vs_replanned "
            "regime -- hold only where sum_k w_k f_k stays above MIN_CELL_COST on every "
            "route cell. Margin is that minimum divided by MIN_CELL_COST; below 1.0 the "
            "clamp binds and no affine claim is published."
        ),
    }
    clamp["binds"] = bool(clamp["fact_clamped_cells"] or clamp["foil_clamped_cells"])
    response["clamp"] = clamp
    if clamp["binds"]:
        response.update(
            {
                "outcome": OUTCOME_CLAMP_BINDS,
                "suppressed_because": (
                    "the MIN_CELL_COST clamp binds on at least one route cell at these "
                    "weights, so the route cost is not affine in the weights here and "
                    "the closed-form threshold would be wrong"
                ),
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
        return response

    # 4. (b), then (c)
    gap_block = criterion_gap(fact_terms, foil_terms, resolved)
    response["criterion_gap"] = gap_block
    delta0 = gap_block["delta_total"]

    # The structural proof. delta(w) = (dD + dB) + sum_k w_k dI_k, so if the
    # foil is no cheaper on any criterion integral AND no cheaper on the two
    # weight-independent terms, then delta(w) >= 0 for EVERY w in [0, inf)^5 --
    # not just for the single-weight sections below, and not by search.
    deltas = {t["criterion"]: t["delta_integral"] for t in gap_block["criteria"]}
    constant_term = gap_block["delta_distance"] + gap_block["delta_barrier"]
    none_better = all(value >= 0.0 for value in deltas.values())
    all_worse = all(value > 0.0 for value in deltas.values())
    # delta_total > 0 is required, not just "no criterion is better": two
    # identical routes satisfy none_better vacuously, and calling that
    # "dominated on every criterion" would be false.
    dominated = none_better and constant_term >= 0.0 and delta0 > 0.0
    response["dominance"] = {
        "dominated_on_every_criterion": dominated,
        "criteria_all_strictly_worse": all_worse,
        "criteria_none_better": none_better,
        "weight_independent_term": constant_term,
        "strict": dominated and constant_term > 0.0,
        "proof": (
            "delta(w) = (delta_distance + delta_barrier) + sum_k w_k * delta_integral_k. "
            "With every delta_integral_k >= 0 and every w_k >= 0 the sum is >= 0, so "
            "delta(w) >= delta_distance + delta_barrier. When that is also >= 0 the foil "
            "can never be cheaper at any weight vector in [0, inf)^5. Proved, not "
            "searched."
        ),
        "reachability_note": (
            "a foil that the planner itself produced at some legal weight vector can "
            "never land here, because it is optimal somewhere by construction; this "
            "outcome is reachable only for foils built some other way"
        ),
    }

    leverage_floor = win_tolerance / max(WEIGHT_MAX - WEIGHT_MIN, 1e-12)
    budget = [int(max_replans)]
    per_criterion: list[dict[str, Any]] = []
    for name in fact_terms.criteria:
        entry = flip_threshold_vs_fact(fact_terms, foil_terms, resolved, name, leverage_floor)
        if entry["outcome"] == OUTCOME_FOUND_VS_FACT and entry["winning_interval"]:
            entry["vs_replanned"] = scan_vs_replanned(
                base_grids, rover_id, rover, resolved, tuple(start), tuple(goal),
                foil_terms, foil_id, model, name, entry["winning_interval"],
                int(scan_points), float(win_tolerance), budget,
            )
        else:
            entry["vs_replanned"] = {
                "regime": "vs_replanned",
                "outcome": None,
                "skipped_because": (
                    "vs_fact found no in-bounds weight at which the foil undercuts the "
                    "fact, and delta_vs_replanned >= delta_vs_fact everywhere, so no "
                    "weight in bounds makes the planner return the foil either. Proved "
                    "with zero re-plans."
                ) if entry["outcome"] == OUTCOME_OUTSIDE_BOUNDS else (
                    "no threshold exists on this criterion"
                ),
            }
        per_criterion.append(entry)

    response["counterfactual"] = {
        "per_criterion": per_criterion,
        "l2_minimal_joint_move": l2_minimal_joint_move(fact_terms, foil_terms, resolved),
        "weight_bounds": [WEIGHT_MIN, WEIGHT_MAX],
        "replans_used": int(max_replans) - budget[0],
        "method": (
            "a one-dimensional section of an inverse-optimisation problem per criterion: "
            "one weight moves, the other four are pinned. NOT a norm-minimising "
            "adjustment -- see l2_minimal_joint_move for that, in the vs_fact regime."
        ),
    }

    # the gap against every floor the model has
    model_floor = abs(
        (foil_terms.B_exact - foil_terms.B) - (fact_terms.B_exact - fact_terms.B)
    )
    band = None
    terrain_sd = None
    if clone_band:
        band = _terrain_band_if_available(
            base_grids, grids, rover, resolved, fact_cells, list(foil_cells), max_clones
        )
        if band and band.get("sd") is not None:
            terrain_sd = band["sd"]
    response["terrain_band"] = band
    response["resolution"] = resolution_report(delta0, model_floor, terrain_sd)
    response["objective_gap"] = objective_gap(
        grids, rover, resolved, fact_cells, list(foil_cells)
    )
    response["objective_dominance"] = {
        "fact_dominates_foil": _objective_dominates(response["objective_gap"], "fact"),
        "foil_dominates_fact": _objective_dominates(response["objective_gap"], "foil"),
        "note": (
            "D5's dominance rule on D5's four route-level objectives -- a DIFFERENT "
            "space from the five cost criteria above, which is why the criterion-space "
            "result is computed separately rather than reusing this one."
        ),
    }

    outcomes = {entry["outcome"] for entry in per_criterion}
    replanned = {
        entry["vs_replanned"].get("outcome")
        for entry in per_criterion
        if entry.get("vs_replanned")
    }
    if dominated:
        response["outcome"] = OUTCOME_DOMINATED
    elif OUTCOME_FOUND_REPLANNED in replanned:
        response["outcome"] = OUTCOME_FOUND_REPLANNED
    elif OUTCOME_FOUND_VS_FACT in outcomes:
        response["outcome"] = OUTCOME_FOUND_VS_FACT
    elif OUTCOME_OUTSIDE_BOUNDS in outcomes:
        response["outcome"] = OUTCOME_OUTSIDE_BOUNDS
    else:
        response["outcome"] = OUTCOME_NO_LEVERAGE
    response["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return response


def _objective_dominates(block: Mapping[str, Any], who: str) -> bool:
    """``pareto.dominates`` on the objective block, in the named direction."""
    entries = block.get("objectives") or []
    if not entries:
        return False
    fact = {e["key"]: e["fact"] for e in entries}
    foil = {e["key"]: e["foil"] for e in entries}
    # pareto.dominates expects every PARETO_OBJECTIVES key; the ones this
    # block does not carry are held equal so they cannot decide the verdict.
    for entry in PARETO_OBJECTIVES:
        fact.setdefault(str(entry["key"]), 0.0)
        foil.setdefault(str(entry["key"]), 0.0)
    return dominates(fact, foil) if who == "fact" else dominates(foil, fact)


def _terrain_band_if_available(
    base_grids: Mapping[str, Any],
    grids: Mapping[str, Any],
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    fact_cells: Sequence[tuple[int, int]],
    foil_cells: Sequence[tuple[int, int]],
    max_clones: int,
) -> dict[str, Any] | None:
    """The clone band when the cache is beside the grids, else a stated absence.

    The cache location comes from ``metadata["processed_dir"]``, the same
    field ``uncertainty_layers_for_grids`` reads, so this module cannot look
    somewhere else and silently band a different site.
    """
    from .uncertainty import load_dem_clones

    processed_dir = (grids.get("metadata") or {}).get("processed_dir")
    if not processed_dir:
        return {
            "available": False,
            "reason": (
                "the loaded grids carry no processed_dir, so the DEM clone cache cannot "
                "be located and the terrain resolution floor is unmeasured"
            ),
        }
    try:
        shape = tuple(int(v) for v in np.asarray(grids["elevation"]).shape)
        clones = load_dem_clones(str(processed_dir), expected_shape=shape)
    except Exception as exc:  # noqa: BLE001 - an absent or stale cache is not fatal
        logger.info("DEM clone band unavailable: %s", exc)
        return {"available": False, "reason": str(exc)}
    if clones is None:
        return {
            "available": False,
            "reason": (
                "no DEM clone cache beside the processed grids, so the terrain "
                "resolution floor is unmeasured and no verdict is offered at that level"
            ),
        }
    band = terrain_band(
        base_grids, grids, rover, weights, fact_cells, foil_cells,
        clones.window, clones.meta or {}, max_clones,
    )
    band["available"] = True
    return band
