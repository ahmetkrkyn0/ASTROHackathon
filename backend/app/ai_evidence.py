"""The only path from raw LunaPath data to the language model.

Nothing reaches the model as a raw backend dict. Every field it sees passed
through an allow-list here, because the prompt is not a security boundary:
a field that arrives is a field the model can build a sentence around, and
several of this backend's fields are traps that read as facts.

Three of them are load-bearing:

* ``astar_metrics.total_energy_wh`` and ``total_shadow_hours`` are always
  ``None`` -- a fast-mode design decision -- while the simulation sitting
  beside them in the same response has the real totals.
* ``summary.total_shadow_exposure`` has no unit anywhere in the codebase, and
  a number whose unit nobody can name cannot be stated.
* ``comparison.recommendation`` still announces that energy and shadow are
  untracked, in responses that carry both.

See docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 4 and 9.
"""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Optional

from pydantic import BaseModel, Field, field_validator

# ── provenance ───────────────────────────────────────────────────────────────

# Weakest first. The backend publishes this four-rung ladder in
# metadata["layer_validity"] and in the X-Layer-Validity header.
_VALIDITY_ORDER: tuple[str, ...] = ("SYNTHETIC", "DERIVED", "MODEL", "MEASURED")

# The frontend badge has three levels (NASA-STD-7009B pedigree), so DERIVED
# and MODEL share one. The collapse happens only for display: the weakest
# input is computed on the four-rung ladder first, which is the whole point
# of keeping the raw value alongside.
_DISPLAY_PEDIGREE: dict[str, str] = {
    "MEASURED": "measurement",
    "MODEL": "model",
    "DERIVED": "model",
    "SYNTHETIC": "demo",
}


def weakest_validity(validities: Iterable[Any]) -> Optional[str]:
    """The lowest rung among *validities*, or None if that cannot be decided.

    An unrecognised label yields None rather than being skipped. A layer
    whose provenance we cannot read is not evidence that the data is good,
    and quietly dropping it would let one unknown layer inherit the
    confidence of its neighbours.
    """
    ranks: list[int] = []
    for validity in validities:
        if validity not in _VALIDITY_ORDER:
            return None
        ranks.append(_VALIDITY_ORDER.index(str(validity)))
    if not ranks:
        return None
    return _VALIDITY_ORDER[min(ranks)]


def display_pedigree(validity: Optional[str]) -> Optional[str]:
    """Map one raw ladder rung onto the three-level UI badge."""
    if validity is None:
        return None
    return _DISPLAY_PEDIGREE.get(str(validity))


def provenance_block(layer_validity: Mapping[str, Any] | None) -> dict[str, Any]:
    """Raw weakest-input rung plus its display label, both or neither."""
    raw = weakest_validity((layer_validity or {}).values())
    return {"rawValidity": raw, "displayPedigree": display_pedigree(raw)}


# ── quantities ───────────────────────────────────────────────────────────────

class Quantity(BaseModel):
    """A number the assistant is allowed to say out loud.

    The unit is mandatory and is never inferred. This is what keeps
    ``total_shadow_exposure`` out of the contract on its own: its unit is not
    stated anywhere in the backend, so it cannot be constructed here, so the
    assistant cannot quote it.
    """

    value: float
    unit: str = Field(min_length=1)

    @field_validator("value")
    @classmethod
    def _must_be_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("a non-finite value is not a measurement")
        return v


def _quantity(value: Any, unit: str) -> Optional[dict[str, Any]]:
    """``{value, unit}`` when *value* is a real number, else None.

    None means the field is omitted entirely rather than reported as zero:
    the backend uses None for "no value here" throughout, and a zero would
    be a claim.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return Quantity(value=number, unit=unit).model_dump()


def _put(target: dict[str, Any], key: str, quantity: Optional[dict[str, Any]]) -> None:
    if quantity is not None:
        target[key] = quantity


# ── current plan ─────────────────────────────────────────────────────────────

# Copied verbatim from the plan's astar_metrics. Deliberately excludes
# total_energy_wh and total_shadow_hours (always null), computation_time_ms
# (nondeterministic noise) and max_thermal_risk, whose derivation the
# assistant is not equipped to explain.
_PLAN_METRIC_FIELDS: tuple[str, ...] = (
    "max_segment_slope_deg",
    "max_cell_slope_deg",
    "min_surface_temp_c",
    "max_surface_temp_c",
    "total_weighted_cost",
    "total_weighted_cost_cells_only",
    "barrier_share",
    "cost_units",
    "path_length_nodes",
    "nodes_expanded",
)


def sanitize_current_plan(plan: Mapping[str, Any] | None) -> Optional[dict[str, Any]]:
    """The user's own plan result, reduced to what the assistant may state.

    The route geometry is not included. The waypoint array is 495 objects on
    a production route and the geojson repeats it; neither answers a question
    the first-cut capabilities can ask, and both are pure token burn.
    """
    if not plan:
        return None

    summary = plan.get("summary") or {}
    metrics = plan.get("astar_metrics") or {}

    out: dict[str, Any] = {}

    _put(out, "distance", _quantity(summary.get("total_distance_km"), "km"))
    # summary.total_energy_consumed_wh, never astar_metrics.total_energy_wh.
    _put(out, "energy", _quantity(summary.get("total_energy_consumed_wh"), "Wh"))
    # summary.max_continuous_shadow_h, never astar_metrics.total_shadow_hours
    # and never summary.total_shadow_exposure, whose unit is unknown.
    _put(
        out,
        "max_continuous_shadow",
        _quantity(summary.get("max_continuous_shadow_h"), "h"),
    )
    _put(out, "min_battery", _quantity(summary.get("min_battery_pct"), "%"))
    _put(out, "final_battery", _quantity(summary.get("final_battery_pct"), "%"))
    _put(out, "elapsed", _quantity(summary.get("total_elapsed_hours"), "h"))
    _put(out, "max_slope", _quantity(summary.get("max_slope_deg"), "deg"))

    for key in ("waypoint_count", "total_recharges", "critical_steps_count",
                "high_or_above_steps_count", "peak_power_exceeded_steps"):
        if isinstance(summary.get(key), int):
            out[key] = summary[key]

    for key in ("stranded", "shadow_limit_exceeded"):
        if isinstance(summary.get(key), bool):
            out[key] = summary[key]
    if summary.get("stranded_at_step") is not None:
        out["stranded_at_step"] = summary["stranded_at_step"]
    _put(out, "shadow_limit", _quantity(summary.get("shadow_limit_h"), "h"))

    plan_metrics: dict[str, Any] = {}
    for key in _PLAN_METRIC_FIELDS:
        value = metrics.get(key)
        if value is not None:
            plan_metrics[key] = value
    if plan_metrics:
        out["metrics"] = plan_metrics

    # The five rejection counters are populated on SUCCESSFUL runs too, which
    # is what makes "why is the route winding?" answerable at all.
    rejected = metrics.get("edges_rejected")
    if isinstance(rejected, Mapping) and rejected:
        out["edges_rejected"] = dict(rejected)

    execution = plan.get("execution")
    if isinstance(execution, Mapping):
        out["execution"] = {
            key: execution.get(key)
            for key in ("stranded", "truncated", "reason")
            if execution.get(key) is not None
        }

    route_statistics = plan.get("route_statistics")
    if isinstance(route_statistics, Mapping) and route_statistics:
        out["route_statistics"] = dict(route_statistics)

    return out


# ── cell telemetry ───────────────────────────────────────────────────────────

CELL_COST_BREAKDOWN_WEIGHT_MISMATCH = "CELL_COST_BREAKDOWN_WEIGHT_MISMATCH"

_WEIGHT_KEYS: tuple[str, ...] = ("w_slope", "w_energy", "w_shadow", "w_thermal")

# Weights are floats that made a round trip through JSON; an exact comparison
# would report a mismatch that does not exist.
_WEIGHT_TOLERANCE = 1e-9


def _weights_agree(
    plan_weights: Mapping[str, Any] | None,
    grid_weights: Mapping[str, Any] | None,
) -> bool:
    if not plan_weights or not grid_weights:
        # Unknown on either side is not agreement.
        return False
    for key in _WEIGHT_KEYS:
        left, right = plan_weights.get(key), grid_weights.get(key)
        if left is None or right is None:
            return False
        if abs(float(left) - float(right)) > _WEIGHT_TOLERANCE:
            return False
    return True


def sanitize_cell_telemetry(
    cell: Mapping[str, Any],
    plan_weights: Mapping[str, Any] | None,
    grid_weights: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """One cell's telemetry, with the decomposition gated on weight agreement.

    ``/api/cell-telemetry`` accepts no weight override: its ``cost_breakdown``
    is always computed with ``metadata["cost_weights"]``. When the user's plan
    ran on different weights, that decomposition explains a different cost
    landscape than the route was drawn through -- so it is withheld and a
    structured limitation says why. The assistant is told; it is not left to
    work it out.
    """
    out: dict[str, Any] = {"row": cell.get("row"), "col": cell.get("col")}
    limitations: list[dict[str, str]] = []

    _put(out, "lon", _quantity(cell.get("lon"), "deg"))
    _put(out, "lat", _quantity(cell.get("lat"), "deg"))
    _put(out, "altitude", _quantity(cell.get("altitude_m"), "m"))
    _put(out, "thermal", _quantity(cell.get("thermal_c"), "degC"))
    _put(out, "thermal_min", _quantity(cell.get("thermal_min_c"), "degC"))
    _put(out, "resolution", _quantity(cell.get("resolution_m"), "m"))
    _put(out, "span", _quantity(cell.get("span_km"), "km"))

    breakdown = cell.get("cost_breakdown")
    if isinstance(breakdown, Mapping) and breakdown:
        if _weights_agree(plan_weights, grid_weights):
            out["cost_breakdown"] = dict(breakdown)
        else:
            limitations.append(
                {
                    "code": CELL_COST_BREAKDOWN_WEIGHT_MISMATCH,
                    "message": (
                        "The per-cell cost decomposition is computed with the "
                        "loaded grid's cost weights, and this route was planned "
                        "with different ones. It would describe a different cost "
                        "landscape than the route was drawn through, so it is not "
                        "reported for this cell."
                    ),
                }
            )

    layer_validity = cell.get("layer_validity")
    if isinstance(layer_validity, Mapping) and layer_validity:
        out["layer_validity"] = dict(layer_validity)
        out["provenance"] = provenance_block(layer_validity)

    out["limitations"] = limitations
    return out


# ── compare ──────────────────────────────────────────────────────────────────

# Excludes total_energy_wh / total_shadow_hours (always null),
# computation_time_ms (noise), and slope_definitions / constraints_applied,
# which are prose the assistant does not need to reason numerically.
_COMPARE_METRIC_FIELDS: tuple[str, ...] = (
    "total_distance_m",
    "max_segment_slope_deg",
    "max_cell_slope_deg",
    "min_surface_temp_c",
    "max_surface_temp_c",
    "total_weighted_cost",
    "total_weighted_cost_cells_only",
    "barrier_share",
    "cost_units",
    "path_length_nodes",
    "nodes_expanded",
)

# Excludes total_shadow_exposure: unit unknown, so it cannot be stated.
_COMPARE_SIMULATION_FIELDS: tuple[str, ...] = (
    "total_distance_km",
    "total_elapsed_hours",
    "final_battery_pct",
    "min_battery_pct",
    "max_slope_deg",
    "max_segment_slope_deg",
    "total_energy_consumed_wh",
    "critical_steps_count",
    "high_or_above_steps_count",
    "waypoint_count",
    "total_recharges",
    "stranded",
    "stranded_at_step",
    "max_continuous_shadow_h",
    "shadow_limit_h",
    "shadow_limit_exceeded",
    "peak_power_exceeded_steps",
)


def _profile_weight_table() -> dict[str, Mapping[str, float]]:
    """Each mission profile's four weights, read from the live catalogue.

    Imported lazily so this module stays importable without the planning
    stack, which its unit tests rely on.
    """
    from .scenarios import MISSION_PROFILES

    return {
        profile_id: profile.get("weights", {})
        for profile_id, profile in MISSION_PROFILES.items()
    }


def sanitize_compare(
    compare: Mapping[str, Any],
    profile_weights: Mapping[str, Mapping[str, float]] | None = None,
) -> dict[str, Any]:
    """Four profile results, reduced to comparable numbers.

    The ``comparison`` block is dropped whole. Its ``recommendation`` string
    asserts that energy and shadow totals are not tracked, which was true of
    astar_metrics and is false of this response: every profile beside it
    carries a full simulation summary. Its three ranking keys are omitted with
    it, because ``most_efficient_profile`` ranks on total_weighted_cost and
    reads, from its name alone, as an energy verdict.

    Route geometry is dropped for the same reason as in the plan sanitizer.
    """
    if profile_weights is None:
        profile_weights = _profile_weight_table()

    out: dict[str, Any] = {
        "start": list(compare.get("start") or []),
        "goal": list(compare.get("goal") or []),
        "profiles": [],
    }

    for result in compare.get("results") or []:
        profile_id = result.get("profile_id")
        entry: dict[str, Any] = {
            "profile_id": profile_id,
            "profile_name": result.get("profile_name"),
        }

        if result.get("error"):
            entry["error"] = result["error"]

        # Every profile moves all four weights at once, so a difference
        # between two runs is never attributable to one of them. Publishing
        # the weights is what lets the assistant say so.
        weights = (profile_weights or {}).get(profile_id)
        if weights:
            entry["weights"] = {
                key: float(weights[key]) for key in _WEIGHT_KEYS if key in weights
            }

        metrics = result.get("metrics") or {}
        picked = {
            key: metrics[key]
            for key in _COMPARE_METRIC_FIELDS
            if metrics.get(key) is not None
        }
        rejected = metrics.get("edges_rejected")
        if isinstance(rejected, Mapping) and rejected:
            picked["edges_rejected"] = dict(rejected)
        if picked:
            entry["metrics"] = picked

        simulation = result.get("simulation_summary")
        if isinstance(simulation, Mapping):
            entry["simulation_summary"] = {
                key: simulation[key]
                for key in _COMPARE_SIMULATION_FIELDS
                if simulation.get(key) is not None
            }

        constraint_check = result.get("constraint_check")
        if isinstance(constraint_check, Mapping) and constraint_check:
            entry["constraint_check"] = {
                name: dict(verdict)
                for name, verdict in constraint_check.items()
                if isinstance(verdict, Mapping)
            }

        out["profiles"].append(entry)

    return out
