"""Non-dominated route families from a sweep of the weight simplex (D5).

The planner ranks cells by a weighted sum of criteria -- slope, energy,
shadow, thermal and (C4) roughness -- and every response so far has been
the answer for ONE weight vector. Which vector is right was never settled:
the four numbers in each rover profile are the reference document's
gradient-normalised expert weights (``constants.W_ROUGHNESS_DEFAULT``'s
comment says so out loud, and doc 11 established the "AHP" label was
wrong). This module stops arguing about the vector and measures what the
argument is worth: it plans the same pair under many vectors, de-duplicates
the routes, and reports which of them no other route beats.

What is swept and what is compared are DIFFERENT spaces
-------------------------------------------------------
The WEIGHT space is the cost model's per-cell criterion weights. Every
rover profile in this catalogue puts its first four on the unit simplex
(measured: ``w_slope + w_energy + w_shadow + w_thermal == 1.0`` for all
four profiles) with ``w_roughness`` additive on top and never rescaled, so
the sweep samples the 4-simplex and holds ``w_roughness`` at the rover's
own value. ETH's ``lunar_planner`` sweeps the same way
(``ALPHA + BETA + GAMMA = 1``).

The OBJECTIVE space is route-level outcomes, and each one carries its
DIRECTION explicitly (:data:`PARETO_OBJECTIVES`) rather than relying on a
convention. All four happen to be minimised here, which is exactly why the
direction is stored rather than assumed: the next objective added may not
be, and a silently inverted axis turns the front inside out.

Read this before calling the output a Pareto front
--------------------------------------------------
It is not one, and :data:`PARETO_COMPLETENESS` says so on every response.
Weighted-sum scalarisation reaches only SUPPORTED efficient solutions --
those admitting a supporting hyperplane, i.e. lying on the boundary of the
convex hull of the achievable set (Boyd & Vandenberghe, *Convex
Optimization*, 2004, sect. 4.7.4; Das & Dennis, *Structural Optimization*
14(1):63-69, 1997; the supported/unsupported terminology is Konen &
Stiglmayr, arXiv:2501.13842, Definition 1.11). Unsupported points are
unreachable at ANY sampling density -- a structural limit, not a
resolution problem.

Here the limit is TIGHTER still, and this is the part that is easy to get
wrong. The theorem is about scalarising the OBJECTIVES. These weights do
not scalarise the objectives: they weight per-cell COST CRITERIA, summed
along the path into one g-score, while the objectives (hours, Wh, shadow
exposure, thermal risk) are different functions of the same path. So no
completeness guarantee applies at all -- this sweep may miss points that a
proper weighted sum over the objectives would have found. The response
therefore publishes ``non_dominated``, never ``pareto_front``, and
:data:`PARETO_COMPLETENESS` is ``"no_guarantee"``.

Everything is decided at the API's own reporting precision
----------------------------------------------------------
Each objective arrives already rounded by the function that publishes it
(:data:`OBJECTIVE_QUANTUM`): hours to 1e-4, Wh to 1e-2, shadow exposure to
1e-4, thermal risk to 1e-4. "Distinct" and "dominated" are therefore both
decided on rounded numbers, an epsilon below the quantum means nothing,
and two values one quantum apart are indistinguishable rather than
ordered. :func:`dominance_epsilon` defaults to the quantum for this reason.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
import traceback
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Optional

import numpy as np

from .pathfinder import astar
from .rover_grids import grids_for_rover
from .simulation import simulate_path, summarize_simulation

logger = logging.getLogger(__name__)

#: Identifies the sweep + filter this module implements, the way
#: ``COST_MODEL_ID`` identifies the cost formula. Bump it when the sampler,
#: the objective set or the dominance rule changes shape -- a stored front
#: computed by an older build must be able to tell.
PARETO_METHOD_ID: str = "weight_simplex_sweep_nondominated_v1"

#: What the weights actually scalarise. Named for the criteria, not the
#: objectives, because that distinction is the whole completeness question.
PARETO_METHOD: str = "weighted_sum_scalarisation_over_cost_criteria"

#: Deliberately not "convex_hull_only": that would claim the convex-hull
#: theorem applies, and it does not, because the weights scalarise the
#: CRITERIA rather than the OBJECTIVES (see the module docstring).
PARETO_COMPLETENESS: str = "no_guarantee"

PARETO_COMPLETENESS_NOTE: str = (
    "Weighted-sum scalarisation reaches only supported efficient solutions -- those on "
    "the boundary of the convex hull of the achievable set -- and unsupported ones are "
    "unreachable at any sampling density (Boyd & Vandenberghe 4.7.4; Das & Dennis 1997). "
    "Here the weights scalarise the per-cell COST CRITERIA, not these objectives, so even "
    "that guarantee does not apply: this sweep may miss routes a weighted sum over the "
    "objectives themselves would find. Nothing in this response bounds what was missed."
)

#: The weight keys that sit on the unit simplex. ``w_roughness`` is NOT one
#: of them: C4 added it as a purely additive fifth term and deliberately did
#: not rescale the other four (constants.py, W_ROUGHNESS_DEFAULT comment),
#: and all four catalogue profiles do sum to 1.0 over exactly these keys.
SIMPLEX_WEIGHT_KEYS: tuple[str, ...] = (
    "w_slope",
    "w_energy",
    "w_shadow",
    "w_thermal",
)

#: The objective vector, with each component's SOURCE FIELD and DIRECTION
#: written down rather than implied. ``direction`` is applied by
#: :func:`_oriented` before any comparison, so adding a maximised objective
#: later needs no change to the dominance code.
#:
#: On ``thermal_risk``: the research brief for D5 asked for a thermal
#: MARGIN (bigger better). This repo has no route-level thermal margin --
#: ``max_thermal_risk`` is a PENALTY, the max of ``f_thermal`` along the
#: path (pathfinder._compute_path_metrics). The margin that does exist,
#: ``safety_margins[*].rho`` (D3), is a different quantity on a different
#: signal. The penalty is used, named for what it is, and minimised.
PARETO_OBJECTIVES: tuple[dict[str, Any], ...] = (
    {
        "key": "hours",
        "source": "summary.total_elapsed_hours",
        "unit": "h",
        "direction": "minimize",
        "note": "wall clock including recharge stops",
    },
    {
        "key": "energy_wh",
        "source": "summary.total_energy_consumed_wh",
        "unit": "Wh",
        "direction": "minimize",
        "note": "gross draw; solar income is NOT netted off",
    },
    {
        "key": "shadow_exposure_h",
        "source": "summary.total_shadow_exposure",
        "unit": "h",
        "direction": "minimize",
        "note": (
            "sum(shadow_ratio_i * dt_i) -- shadow-ratio-weighted hours, NOT binary "
            "hours in darkness; the name carries the definition on purpose"
        ),
    },
    {
        "key": "thermal_risk",
        "source": "astar_metrics.max_thermal_risk",
        "unit": "MRU [0,1]",
        "direction": "minimize",
        "note": (
            "a PENALTY (max of f_thermal along the path), not a margin; saturates on "
            "this site and is usually constant across routes"
        ),
    },
)

OBJECTIVE_KEYS: tuple[str, ...] = tuple(o["key"] for o in PARETO_OBJECTIVES)

#: The precision each objective is PUBLISHED at, by the function that
#: publishes it. Dominance is decided on these rounded numbers, so an
#: epsilon finer than the quantum is meaningless and a one-quantum gap is
#: not an ordering. Used as the default epsilon.
OBJECTIVE_QUANTUM: dict[str, float] = {
    "hours": 1e-4,             # simulation.summarize_simulation, round(..., 4)
    "energy_wh": 1e-2,         # simulation.summarize_simulation, round(..., 2)
    "shadow_exposure_h": 1e-4,  # simulation.summarize_simulation, round(..., 4)
    "thermal_risk": 1e-4,      # pathfinder._compute_path_metrics, round(..., 4)
}

PARETO_VALIDITY: str = "MODEL"

PARETO_CLAIM: str = (
    "A non-dominated subset of the routes THIS SWEEP produced, not the Pareto front of "
    "the problem: weighted-sum scalarisation reaches only supported solutions, and these "
    "weights scalarise the cost criteria rather than these objectives, so nothing here "
    "bounds what was missed. Every route is the planner's existing 2-D physics on a "
    "DERIVED cost grid; the sweep changes ranking only and adds no physics. Dominance is "
    "decided at the API's reporting precision (1e-4 h, 1e-2 Wh, 1e-4, 1e-4), so margins "
    "near those quanta are not orderings. Routes are de-duplicated by cell sequence, and "
    "every statistic here runs over DISTINCT routes -- pooling repeated routes would "
    "count the same route twice. The literature's numbers are quoted, never reproduced."
)

#: Read first-hand on 16 September 2026. These are THEIR numbers; ours never
#: go in this dict, and nothing here was reproduced by us.
PARETO_QUOTED: dict[str, Any] = {
    "boyd_vandenberghe": {
        "citation": (
            "Boyd, Vandenberghe -- Convex Optimization, Cambridge University Press, "
            "2004, sect. 4.7.4 'Scalarization', pp. 178-180"
        ),
        "url": "https://web.stanford.edu/~boyd/cvxbook/bv_cvxbook.pdf",
        "limit_quote": (
            "The value f0(x3) is Pareto optimal, but cannot be found by scalarization"
        ),
        "completeness_quote": (
            "for convex problems the method of scalarization yields all Pareto optimal "
            "points"
        ),
        "used_for": "the statement of the limit and of the condition under which it lifts",
    },
    "das_dennis_1997": {
        "citation": (
            "Das, Dennis -- A closer look at drawbacks of minimizing weighted sums of "
            "objectives for Pareto set generation in multicriteria optimization "
            "problems, Structural Optimization 14(1):63-69, 1997"
        ),
        "url": "https://doi.org/10.1007/BF01197559",
        "convexity_quote": (
            "it is well-known that this method succeeds in getting points from all parts "
            "of the Pareto set only when the Pareto curve is convex"
        ),
        "spacing_quote": (
            "even for convex Pareto curves, an evenly distributed set of weights fails to "
            "produce an even distribution of points from all parts of the Pareto set"
        ),
        "used_for": "why denser weight sampling does not fix either problem",
    },
    "konen_stiglmayr_2025": {
        "citation": (
            "Konen, Stiglmayr -- On Supportedness in Multi-Objective Combinatorial "
            "Optimization, arXiv:2501.13842v2, 2025, Definition 1.11"
        ),
        "url": "https://arxiv.org/abs/2501.13842",
        "terminology_quote": (
            "Unsupported efficient solutions are efficient solutions that are not optimal "
            "solutions of P_lambda for any lambda"
        ),
        "consequence_quote": (
            "unsupported non-dominated points cannot be computed through a weighted sum "
            "scalarization"
        ),
        "used_for": (
            "the supported/unsupported terminology; 'duality gap' is NOT the term this "
            "literature uses and is not used here"
        ),
    },
    "eth_lunar_planner": {
        "citation": (
            "Richter, Kolvenbach, Valsecchi, Hutter -- Multi-Objective Global Path "
            "Planning for Lunar Exploration With a Quadruped Robot, iSpaRo 2024, "
            "arXiv:2406.16376"
        ),
        "url": "https://github.com/leggedrobotics/lunar_planner",
        "license": "MIT",
        "method_quote": (
            "We introduce weights between the objectives, which can be adapted to achieve "
            "a variety of optimal paths. In order to find the best of these paths, a tool "
            "for statistical path analysis is presented."
        ),
        "simplex_note": "their setup_file.py fixes ALPHA + BETA + GAMMA = 1, the same simplex",
        "used_for": (
            "the direct precedent: A* on a fixed-weight linear scalarisation, swept over "
            "the simplex and analysed afterwards -- exactly this feature's cheap path"
        ),
    },
    "lavin_2015": {
        "citation": (
            "Lavin -- A Pareto Front-Based Multiobjective Path Planning Algorithm, "
            "arXiv:1505.05947, 2015"
        ),
        "url": "https://arxiv.org/abs/1505.05947",
        "weight_sensitivity_quote": (
            "selection of parameters is difficult because small perturbations in the "
            "weights can lead to very different solutions"
        ),
        "correction": (
            "read first-hand: A*-PO does NOT return a front of paths. It takes the "
            "non-dominated set of the OPEN LIST at each expansion and collapses it to one "
            "node, 'resulting in a single, optimal path'. Cited here for the weight-"
            "sensitivity claim only, which this sweep measures on our own terrain."
        ),
    },
}

PARETO_REFERENCES: tuple[dict[str, str], ...] = tuple(
    {
        "id": key,
        "citation": str(value["citation"]),
        "url": str(value.get("url", "")),
        "used_for": str(value.get("used_for", value.get("correction", ""))),
    }
    for key, value in PARETO_QUOTED.items()
)


# ── the weight simplex ──────────────────────────────────────────────────────


def simplex_samples(
    n: int, seed: int, include_corners: bool = False
) -> list[tuple[str, dict[str, float]]]:
    """*n* weight vectors drawn uniformly from the 4-simplex, labelled.

    Written as normalised standard exponentials rather than
    ``Generator.dirichlet``: the two are identical (asserted in the tests)
    but this form does not depend on numpy's dirichlet internals staying
    put, and a sampler that drifts between numpy releases would turn every
    front assertion into a permanently red test.

    With *include_corners* the 4 simplex vertices and 6 edge midpoints are
    appended. They are not decoration -- a vertex (``w_slope = 1``) was
    measured on the front for the Site11 daytime pair, so a sweep that only
    draws from the interior misses it.
    """
    if n < 0:
        raise ValueError(f"n must not be negative, got {n}")
    rng = np.random.default_rng(int(seed))
    out: list[tuple[str, dict[str, float]]] = []
    if n:
        raw = rng.standard_exponential((int(n), len(SIMPLEX_WEIGHT_KEYS)))
        draws = raw / raw.sum(axis=1, keepdims=True)
        for i, row in enumerate(draws):
            out.append((f"sample{i:03d}", dict(zip(SIMPLEX_WEIGHT_KEYS, map(float, row)))))
    if include_corners:
        k = len(SIMPLEX_WEIGHT_KEYS)
        for i in range(k):
            vector = [0.0] * k
            vector[i] = 1.0
            out.append((f"corner_{SIMPLEX_WEIGHT_KEYS[i]}", dict(zip(SIMPLEX_WEIGHT_KEYS, vector))))
        for i in range(k):
            for j in range(i + 1, k):
                vector = [0.0] * k
                vector[i] = vector[j] = 0.5
                label = f"edge_{SIMPLEX_WEIGHT_KEYS[i][2:]}_{SIMPLEX_WEIGHT_KEYS[j][2:]}"
                out.append((label, dict(zip(SIMPLEX_WEIGHT_KEYS, vector))))
    return out


def route_id(path_pixels: Iterable[Sequence[int]]) -> str:
    """A stable id for the ORDERED cell sequence.

    Routes are de-duplicated by this and never by their objective vector:
    different weight vectors routinely produce the identical cell sequence
    (measured: 211 vectors -> 65 distinct routes on the Site11 daytime
    pair), and without this the same route would appear on the front once
    per weight vector that found it.
    """
    raw = ",".join(f"{int(row)}:{int(col)}" for row, col in path_pixels)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ── dominance ───────────────────────────────────────────────────────────────


def dominance_epsilon(overrides: Mapping[str, float] | None = None) -> dict[str, float]:
    """Per-objective tie tolerance, defaulting to each field's own quantum.

    Defaulting to the publication quantum rather than to zero is the point:
    the objectives arrive already rounded, so two routes separated by less
    than one quantum were never measured apart, and calling that a
    domination would make the front an artefact of the rounding.
    """
    eps = dict(OBJECTIVE_QUANTUM)
    for key, value in (overrides or {}).items():
        if key not in eps:
            raise ValueError(f"unknown objective {key!r}; expected one of {OBJECTIVE_KEYS}")
        if not (float(value) >= 0.0) or not math.isfinite(float(value)):
            raise ValueError(f"epsilon for {key!r} must be finite and >= 0, got {value}")
        eps[key] = float(value)
    return eps


def _oriented(vector: Mapping[str, float]) -> np.ndarray:
    """The objective vector with every component turned into "smaller is better"."""
    return np.array(
        [
            float(vector[o["key"]]) * (-1.0 if o["direction"] == "maximize" else 1.0)
            for o in PARETO_OBJECTIVES
        ],
        dtype=np.float64,
    )


def dominates(
    a: Mapping[str, float], b: Mapping[str, float], epsilon: Mapping[str, float] | None = None
) -> bool:
    """True when *a* dominates *b*: no worse anywhere, better somewhere.

    Both tests carry the epsilon, in opposite directions, so a pair that
    differs by less than the tolerance on every objective dominates in
    neither direction and both stay on the front.
    """
    eps = np.array(
        [dominance_epsilon(epsilon)[o["key"]] for o in PARETO_OBJECTIVES], dtype=np.float64
    )
    x, y = _oriented(a), _oriented(b)
    return bool(np.all(x <= y + eps) and np.any(x < y - eps))


def non_dominated(
    entries: Sequence[Mapping[str, Any]], epsilon: Mapping[str, float] | None = None
) -> list[int]:
    """Indices of the entries no other entry dominates, order preserved."""
    eps = np.array(
        [dominance_epsilon(epsilon)[o["key"]] for o in PARETO_OBJECTIVES], dtype=np.float64
    )
    vectors = [_oriented(entry["objectives"]) for entry in entries]
    out: list[int] = []
    for i, x in enumerate(vectors):
        beaten = False
        for j, y in enumerate(vectors):
            if i == j:
                continue
            if bool(np.all(y <= x + eps) and np.any(y < x - eps)):
                beaten = True
                break
        if not beaten:
            out.append(i)
    return out


# ── solving one weight vector ───────────────────────────────────────────────


def objectives_from(summary: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, float]:
    """The four objectives, each read from the field named in :data:`PARETO_OBJECTIVES`."""
    return {
        "hours": float(summary["total_elapsed_hours"]),
        "energy_wh": float(summary["total_energy_consumed_wh"]),
        "shadow_exposure_h": float(summary["total_shadow_exposure"]),
        "thermal_risk": float(metrics["max_thermal_risk"]),
    }


def solve_weight_vector(
    base_grids: dict,
    start: Sequence[int],
    goal: Sequence[int],
    rover_id: str,
    rover: Mapping[str, Any],
    weights: Mapping[str, float],
    label: str,
) -> dict[str, Any]:
    """One weight vector's route, its objectives and its wall clock.

    Deliberately lighter than ``profile_comparison.solve_profile``: that one
    also runs the D3 safety monitor and the C3 slip block per route, which
    this sweep pays for up to 40 times and never reads. It is also imported
    by the AI tool layer, so widening it to take arbitrary weight vectors
    would put the assistant's only planning path on this code's risk.

    A vector that finds no route is an ``error`` on its own entry, not an
    exception: one refused vector out of forty must not discard the other
    thirty-nine (the contract /api/risk-sweep already publishes).
    """
    started = time.perf_counter()
    entry: dict[str, Any] = {
        "label": label,
        "weights": dict(weights),
        "error": None,
        "route_id": None,
        "path_length_nodes": None,
        "objectives": None,
        "summary": None,
        "stranded": None,
        "plan_ms": None,
    }
    try:
        grids = grids_for_rover(base_grids, rover_id, dict(weights))
        result = astar(grids, tuple(start), tuple(goal), weights=dict(weights), rover=rover)
        if result.get("error"):
            entry["error"] = str(result["error"])
        else:
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
            summary = summarize_simulation(states, rover)
            entry["route_id"] = route_id(result["path_pixels"])
            entry["path_length_nodes"] = len(result["path_pixels"])
            entry["objectives"] = objectives_from(summary, result["metrics"])
            entry["summary"] = summary
            # A stranded route's totals describe only the prefix it managed,
            # so it scores BETTER on every objective the further it fails --
            # it would sit on the front by failing early. Flagged here and
            # excluded from the comparison by sweep().
            entry["stranded"] = bool(summary["stranded"])
    except Exception:  # noqa: BLE001 - reported per entry, never fatal to the sweep
        logger.error("Pareto sample %s failed:\n%s", label, traceback.format_exc())
        entry["error"] = "Internal planning error."
    entry["plan_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
    return entry


# ── the sweep ───────────────────────────────────────────────────────────────


def sweep(
    base_grids: dict,
    start: Sequence[int],
    goal: Sequence[int],
    rover_id: str,
    rover: Mapping[str, Any],
    n_samples: int,
    seed: int,
    include_corners: bool = False,
    epsilon: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Plan the pair under many weight vectors and report what survives.

    The rover's own default weights are always included and marked
    ``is_nominal``, so "is the shipped vector on the front" is a question
    the response answers rather than one the caller has to reconstruct.
    """
    nominal_weights = {key: float(rover[key]) for key in SIMPLEX_WEIGHT_KEYS}
    samples: list[tuple[str, dict[str, float]]] = [("nominal", nominal_weights)]
    samples.extend(simplex_samples(int(n_samples), int(seed), include_corners))

    # w_roughness is not on the simplex (C4 made it additive and did not
    # rescale the other four), so it rides at the rover's own value for
    # every sample and is never swept.
    w_roughness = float(rover["w_roughness"])

    started = time.perf_counter()
    entries: list[dict[str, Any]] = []
    for label, weights in samples:
        full = dict(weights)
        full["w_roughness"] = w_roughness
        entry = solve_weight_vector(
            base_grids, start, goal, rover_id, rover, full, label
        )
        entry["is_nominal"] = label == "nominal"
        entries.append(entry)
    total_ms = round((time.perf_counter() - started) * 1000.0, 3)

    solved = [e for e in entries if e["objectives"] is not None]
    # Stranded routes are excluded rather than merely flagged: their totals
    # cover only the executable prefix, so including them would let a route
    # dominate the front by failing sooner.
    usable = [e for e in solved if not e["stranded"]]

    # De-duplicate by CELL SEQUENCE, keeping the first weight vector that
    # found each route, and record how many vectors landed on it. That count
    # is the direct answer to "how much did the weight argument decide?".
    by_route: dict[str, dict[str, Any]] = {}
    for entry in usable:
        key = entry["route_id"]
        if key in by_route:
            by_route[key]["found_by"].append(entry["label"])
            by_route[key]["is_nominal"] = by_route[key]["is_nominal"] or entry["is_nominal"]
            continue
        by_route[key] = {
            "route_id": key,
            "objectives": entry["objectives"],
            "path_length_nodes": entry["path_length_nodes"],
            "weights": entry["weights"],
            "is_nominal": entry["is_nominal"],
            "found_by": [entry["label"]],
        }
    distinct = list(by_route.values())
    for route in distinct:
        route["weight_vectors"] = len(route["found_by"])

    front_index = non_dominated(distinct, epsilon)
    front_positions = set(front_index)
    front_ids = {distinct[i]["route_id"] for i in front_index}
    for i, route in enumerate(distinct):
        route["non_dominated"] = i in front_positions

    return {
        "objectives": [dict(o) for o in PARETO_OBJECTIVES],
        "epsilon": dominance_epsilon(epsilon),
        "samples": entries,
        "distinct_routes": distinct,
        "non_dominated": [distinct[i] for i in front_index],
        "counts": _counts(entries, solved, usable, distinct, front_ids),
        "diagnostics": diagnostics(distinct),
        "nominal": _nominal_block(distinct, front_ids, epsilon),
        "total_ms": total_ms,
        "seed": int(seed),
        "include_corners": bool(include_corners),
        "swept_weight_keys": list(SIMPLEX_WEIGHT_KEYS),
        "held_weights": {"w_roughness": w_roughness},
        "method": PARETO_METHOD,
        "method_id": PARETO_METHOD_ID,
        "completeness": PARETO_COMPLETENESS,
        "completeness_note": PARETO_COMPLETENESS_NOTE,
        "validity": PARETO_VALIDITY,
        "claim": PARETO_CLAIM,
        "references": [dict(r) for r in PARETO_REFERENCES],
    }


def _counts(
    entries: Sequence[Mapping[str, Any]],
    solved: Sequence[Mapping[str, Any]],
    usable: Sequence[Mapping[str, Any]],
    distinct: Sequence[Mapping[str, Any]],
    front_ids: set[str],
) -> dict[str, Any]:
    """Every n this feature has, named so two of them cannot be confused.

    There are five different "n"s here and they are easy to quote as one
    another: weight vectors tried, vectors that produced a route, routes
    that were usable, DISTINCT routes, and non-dominated routes. Every
    statistic downstream runs over ``distinct_routes`` -- pooling repeated
    routes would count the same route once per weight vector that found it
    and inflate any correlation computed from them.
    """
    return {
        "weight_vectors": len(entries),
        "planned": len(solved),
        "stranded_excluded": len(solved) - len(usable),
        "usable": len(usable),
        "distinct_routes": len(distinct),
        "non_dominated": len(front_ids),
        "weight_vectors_per_distinct_route": (
            round(len(usable) / len(distinct), 4) if distinct else None
        ),
    }


def diagnostics(distinct: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Why the front came out the size it did.

    A front of one or two members is not self-explanatory, and reporting it
    without this block would leave "the front collapsed" looking like a
    discovery when it is usually a consequence of two measurable things: an
    objective that takes the same value on every route, and objectives that
    order the routes almost identically.

    Spearman, not Pearson, and over DISTINCT routes: the repo's other
    collinearity results are Spearman (cost_engine), and correlating over
    raw samples would count duplicated routes repeatedly.
    """
    n = len(distinct)
    spread: dict[str, Any] = {}
    constant: list[str] = []
    for objective in PARETO_OBJECTIVES:
        key = objective["key"]
        values = [float(route["objectives"][key]) for route in distinct]
        quantum = OBJECTIVE_QUANTUM[key]
        if not values:
            spread[key] = None
            continue
        low, high = min(values), max(values)
        distinct_values = len({round(v / quantum) for v in values})
        spread[key] = {
            "min": low,
            "max": high,
            "span": high - low,
            "span_pct_of_min": (
                round(100.0 * (high - low) / abs(low), 4) if low else None
            ),
            "distinct_values_at_reporting_precision": distinct_values,
            "quantum": quantum,
        }
        if distinct_values <= 1:
            constant.append(key)

    correlation: dict[str, float] = {}
    if n >= 3:
        varying = [o["key"] for o in PARETO_OBJECTIVES if o["key"] not in constant]
        for i, a in enumerate(varying):
            for b in varying[i + 1 :]:
                rho = _spearman(
                    [float(r["objectives"][a]) for r in distinct],
                    [float(r["objectives"][b]) for r in distinct],
                )
                if rho is not None:
                    correlation[f"{a}~{b}"] = round(rho, 4)

    return {
        "n_distinct_routes": n,
        "objective_spread": spread,
        "constant_objectives": constant,
        "effective_objectives": len(PARETO_OBJECTIVES) - len(constant),
        "objective_rank_correlation_spearman": correlation,
        "correlation_n": n,
        "note": (
            "A constant objective cannot separate any pair, so a front over k objectives "
            "of which c are constant is really a front over k - c. Correlations are "
            "Spearman over DISTINCT routes; with n this small they are descriptive, not "
            "inferential, and no confidence interval is claimed."
        ),
    }


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Spearman's rho, or None when either side has no spread to rank."""
    x, y = _ranks(a), _ranks(b)
    if x is None or y is None:
        return None
    x = x - x.mean()
    y = y - y.mean()
    denominator = math.sqrt(float(np.dot(x, x)) * float(np.dot(y, y)))
    if denominator <= 0.0:
        return None
    return float(np.dot(x, y) / denominator)


def _ranks(values: Sequence[float]) -> Optional[np.ndarray]:
    """Average ranks, or None when every value is the same."""
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0 or float(array.max() - array.min()) == 0.0:
        return None
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    ranks[order] = np.arange(1, array.size + 1, dtype=np.float64)
    # Ties share their average rank, so a tied objective cannot fake an order.
    _, inverse, counts = np.unique(array, return_inverse=True, return_counts=True)
    for index in np.where(counts > 1)[0]:
        mask = inverse == index
        ranks[mask] = ranks[mask].mean()
    return ranks


def _nominal_block(
    distinct: Sequence[Mapping[str, Any]],
    front_ids: set[str],
    epsilon: Mapping[str, float] | None,
) -> Optional[dict[str, Any]]:
    """Whether the rover's shipped weights survived, and by how much they lost.

    The margins matter as much as the verdict. A nominal route that loses by
    a fraction of a percent has been beaten inside the model's own
    uncertainty, and reporting the verdict without the margin would read as
    "the shipped weights are wrong" when what was measured is "the
    optimiser's arithmetic separates them by less than its own noise".
    """
    nominal = next((route for route in distinct if route["is_nominal"]), None)
    if nominal is None:
        return None
    on_front = nominal["route_id"] in front_ids
    dominators = []
    if not on_front:
        for route in distinct:
            if route["route_id"] == nominal["route_id"]:
                continue
            if dominates(route["objectives"], nominal["objectives"], epsilon):
                margins = {}
                for objective in PARETO_OBJECTIVES:
                    key = objective["key"]
                    mine = float(nominal["objectives"][key])
                    theirs = float(route["objectives"][key])
                    margins[key] = {
                        "delta": round(theirs - mine, 6),
                        "pct": round(100.0 * (theirs - mine) / abs(mine), 4) if mine else None,
                    }
                dominators.append({"route_id": route["route_id"], "margins": margins})
    return {
        "route_id": nominal["route_id"],
        "weights": nominal["weights"],
        "objectives": nominal["objectives"],
        "on_front": on_front,
        "dominated_by": dominators,
        "note": (
            "The nominal vector minimises the WEIGHTED COST, not any of these objectives, "
            "so there is no reason for its route to be non-dominated in outcome space. "
            "Read the margins before reading the verdict: a loss of a fraction of a "
            "percent is inside this model's own spread and is not a case for changing the "
            "catalogue."
        ),
    }
