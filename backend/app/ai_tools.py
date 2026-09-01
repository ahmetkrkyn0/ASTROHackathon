"""The tools the assistant may run, and the ceiling on how often.

This registry is the authorization boundary. The model proposes a function
name and a JSON object; neither is trusted. A name that is not one of the two
approved tools is refused rather than resolved, and the arguments are
re-validated here even when the schema handed to the provider already
described them -- a schema is a hint to the model, not a guarantee from it.

Two properties are structural rather than enforced by a check:

* There is no route-planning tool, so no sequence of model outputs can reach
  ``POST /api/plan``, publish a corridor, or move the route on the user's
  screen.
* ``compare_mission_profiles`` takes its endpoints from the mission snapshot,
  not from the model's arguments, so the assistant cannot quietly answer
  about a different route than the one under discussion.

Contract: docs/ai/LunaPath_AI_Chatbot_Scope_v0.3.md sections 5, 6 and 7.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

import numpy as np

from .ai_contract import AiMissionSnapshot, CellRef
from .ai_evidence import sanitize_cell_telemetry, sanitize_compare
from .constants import UnknownRoverError, get_rover
from .costmap import PlanContext, default_cost_map
from .profile_comparison import compare_all_profiles
from .serializer import pixel_to_lonlat

# One measured comparison is 21.3 s of wall time against a 30 s per-question
# ceiling, so a second one does not fit. This is arithmetic, not policy.
MAX_COMPARE_CALLS = 1
MAX_READ_CALLS = 20
MAX_TOOL_ROUNDS = 4


class AiToolError(Exception):
    """A tool refused. Carries a code the chat loop reports back to the model."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_tool_output(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


@dataclass
class ToolBudget:
    """Per-question spend, counted server-side where the model cannot see it."""

    compare_calls: int = 0
    read_calls: int = 0

    def spend_compare(self) -> None:
        if self.compare_calls >= MAX_COMPARE_CALLS:
            raise AiToolError(
                "BUDGET_EXCEEDED",
                (
                    f"Only {MAX_COMPARE_CALLS} profile comparison is permitted "
                    "per question. Answer from the comparison already run."
                ),
            )
        self.compare_calls += 1

    def spend_read(self) -> None:
        if self.read_calls >= MAX_READ_CALLS:
            raise AiToolError(
                "BUDGET_EXCEEDED",
                f"Only {MAX_READ_CALLS} read calls are permitted per question.",
            )
        self.read_calls += 1


def _require_index(arguments: Mapping[str, Any], key: str) -> int:
    value = arguments.get(key)
    # bool is an int in Python, and True would read as row 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise AiToolError(
            "INVALID_ARGUMENT", f"{key} must be an integer grid index."
        )
    if not math.isfinite(value):
        raise AiToolError("INVALID_ARGUMENT", f"{key} must be finite.")
    return value


@dataclass
class ToolRegistry:
    """The two approved tools, bound to one question's grids and snapshot."""

    grids: dict
    snapshot: AiMissionSnapshot
    budget: ToolBudget = field(default_factory=ToolBudget)

    def tool_names(self) -> list[str]:
        return sorted(self._handlers())

    def _handlers(self) -> dict[str, Callable[[Mapping[str, Any]], dict[str, Any]]]:
        return {
            "inspect_cell": self._inspect_cell,
            "compare_mission_profiles": self._compare_mission_profiles,
        }

    def call(self, name: str, arguments: Mapping[str, Any] | None) -> dict[str, Any]:
        handler = self._handlers().get(name)
        if handler is None:
            # Not resolved, not approximated, not looked up anywhere else.
            raise AiToolError(
                "UNKNOWN_TOOL",
                f"{name!r} is not an available tool.",
            )
        return handler(arguments or {})

    # ── inspect_cell ─────────────────────────────────────────────────────────

    def _inspect_cell(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        row = _require_index(arguments, "row")
        col = _require_index(arguments, "col")

        metadata = self.grids["metadata"]
        rows, cols = (int(n) for n in metadata["shape"])
        if not (0 <= row < rows and 0 <= col < cols):
            raise AiToolError(
                "INVALID_ARGUMENT",
                f"({row}, {col}) is outside the {rows}x{cols} grid.",
            )

        try:
            rover = get_rover(self.snapshot.roverId)
        except UnknownRoverError as exc:
            raise AiToolError("INVALID_ARGUMENT", str(exc)) from exc

        self.budget.spend_read()

        resolution_m = float(metadata["resolution_m"])
        lon, lat = pixel_to_lonlat(row, col, metadata)
        thermal_min = self.grids.get("thermal_min")
        context = PlanContext(
            slope=np.asarray(self.grids["slope"], dtype=np.float64),
            thermal=np.asarray(self.grids["thermal"], dtype=np.float64),
            shadow_ratio=np.asarray(self.grids["shadow_ratio"], dtype=np.float64),
            traversable=np.asarray(self.grids["traversable"], dtype=bool),
            resolution_m=resolution_m,
            rover=rover,
            thermal_min=(
                None if thermal_min is None
                else np.asarray(thermal_min, dtype=np.float64)
            ),
        )
        # The grid's stamped weights, exactly as /api/cell-telemetry uses:
        # this endpoint accepts no weight override, which is the whole reason
        # the sanitizer compares them against the plan's.
        grid_weights = metadata.get("cost_weights")
        cost_map = default_cost_map(rover, grid_weights, metadata.get("layer_validity"))

        raw = {
            "row": row,
            "col": col,
            "lon": round(lon, 6),
            "lat": round(lat, 6),
            "altitude_m": _grid_value(self.grids["elevation"], row, col),
            "thermal_c": _grid_value(self.grids["thermal"], row, col),
            "thermal_min_c": (
                None if thermal_min is None
                else _grid_value(thermal_min, row, col)
            ),
            "resolution_m": resolution_m,
            "span_km": round((rows * resolution_m) / 1000.0, 4),
            "cost_breakdown": cost_map.explain(row, col, context),
            "layer_validity": metadata.get("layer_validity", {}),
        }
        return sanitize_cell_telemetry(
            raw,
            plan_weights=self.snapshot.weights.model_dump(),
            grid_weights=grid_weights,
        )

    # ── compare_mission_profiles ─────────────────────────────────────────────

    def _compare_mission_profiles(
        self, arguments: Mapping[str, Any]
    ) -> dict[str, Any]:
        # `arguments` is deliberately ignored. The endpoints come from what
        # the user selected, so the model cannot compare a route the user is
        # not looking at.
        start, goal = self.snapshot.start, self.snapshot.goal
        if start is None or goal is None:
            raise AiToolError(
                "MISSION_INCOMPLETE",
                (
                    "A profile comparison needs a start and a goal. The user "
                    "has not selected both on the map yet."
                ),
            )

        metadata = self.grids["metadata"]
        rows, cols = (int(n) for n in metadata["shape"])
        for label, point in (("start", start), ("goal", goal)):
            if not (0 <= point[0] < rows and 0 <= point[1] < cols):
                raise AiToolError(
                    "INVALID_ARGUMENT",
                    f"{label} {tuple(point)} is outside the {rows}x{cols} grid.",
                )

        try:
            rover = get_rover(self.snapshot.roverId)
        except UnknownRoverError as exc:
            raise AiToolError("INVALID_ARGUMENT", str(exc)) from exc

        self.budget.spend_compare()

        results = compare_all_profiles(
            self.grids, start, goal, self.snapshot.roverId, rover
        )
        # The `comparison` block never enters the sanitizer: its
        # recommendation string contradicts the simulation summaries beside
        # it, and its rankings read as verdicts they are not.
        return sanitize_compare({"start": start, "goal": goal, "results": results})


def _grid_value(grid: Any, row: int, col: int) -> float | None:
    value = np.asarray(grid)[row, col]
    return float(value) if np.isfinite(value) else None


def tool_specifications() -> list[dict[str, Any]]:
    """Function schemas handed to the provider.

    These describe only the two approved tools. No built-in provider tool --
    web search, file search, code execution, shell, computer use -- is
    enabled for this feature, so this list is the model's entire reach.
    """
    return [
        {
            "type": "function",
            "name": "inspect_cell",
            "description": (
                "Read deterministic terrain telemetry for one grid cell: "
                "position, elevation, both ends of its temperature range, and "
                "-- when the loaded grid's cost weights match the plan's -- the "
                "per-criterion cost decomposition. Use it to answer questions "
                "about a specific point on the map."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "row": {"type": "integer", "description": "Grid row index."},
                    "col": {"type": "integer", "description": "Grid column index."},
                },
                "required": ["row", "col"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "compare_mission_profiles",
            "description": (
                "Solve the user's current start and goal under all four mission "
                "profiles and return each one's metrics, simulated energy and "
                "shadow totals, and constraint margins. Side-effect free: it "
                "does not change the route on screen. The endpoints come from "
                "the user's own selection and cannot be chosen here. Takes "
                "about 20 seconds and may be used at most once per question."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    ]


# ── AnalysisProvider (AI-02 section 5.2) ─────────────────────────────────────

# Semantic descriptors. K2 and K3 see these; they never see an endpoint name,
# a function name, or a backend field path -- that binding lives in _DISPATCH
# below and goes no further up the stack.
CAPABILITIES: dict[str, dict[str, Any]] = {
    "C-SUMMARY": {
        "code": "C-SUMMARY",
        "label_tr": "Mevcut planın özeti",
        "available": True,
        "writes": False,
        "cost_class": "free",
        "notes": "Kullanıcının hâlihazırda ürettiği plandan okunur; yeniden hesap yok.",
    },
    "C-POINT": {
        "code": "C-POINT",
        "label_tr": "Tek hücre telemetrisi",
        "available": True,
        "writes": False,
        "cost_class": "read",
        "notes": "Konum, yükseklik, sıcaklık aralığı ve -- ağırlıklar uyuşuyorsa -- maliyet ayrışımı.",
    },
    "C-COMPARE": {
        "code": "C-COMPARE",
        "label_tr": "Dört görev profilinin karşılaştırması",
        "available": True,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Yan etkisiz. Yaklaşık 20 saniye sürer ve soru başına en fazla bir kez kullanılabilir.",
    },
    # Described by the generic contract, absent from the audited backend.
    # Present here so the router can be told they exist and are closed,
    # rather than discovering an unexplained failure.
    "C-DECOMPOSE": {
        "code": "C-DECOMPOSE",
        "label_tr": "Rota geneli maliyet ayrışması",
        "available": False,
        "writes": False,
        "cost_class": "read",
        "notes": "Yalnızca hücre bazında mevcut; rota geneli toplam biriktirilmiyor.",
    },
    "C-BINDING": {
        "code": "C-BINDING",
        "label_tr": "Bağlayıcı kısıt",
        "available": False,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Kısmi: kısıt marjları C-COMPARE yanıtı içinde taşınır.",
    },
    "C-INFEASIBLE": {
        "code": "C-INFEASIBLE",
        "label_tr": "Fizibilitesizlik açıklaması",
        "available": False,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Kısmi: reddedilen kenar sayaçları C-COMPARE yanıtı içinde taşınır.",
    },
    "C-SENSITIVITY": {
        "code": "C-SENSITIVITY",
        "label_tr": "Duyarlılık",
        "available": False,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Yalnızca dört sabit profil üzerinden ayrık; serbest ağırlık perturbasyonu yok.",
    },
    "C-CONTRAST": {
        "code": "C-CONTRAST",
        "label_tr": "Karşıtsal açıklama",
        "available": False,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Kullanıcı yolunu puanlayan bir uç yok.",
    },
    "C-RECOURSE": {
        "code": "C-RECOURSE",
        "label_tr": "Hedef odaklı öneri",
        "available": False,
        "writes": False,
        "cost_class": "expensive",
        "notes": "Ağırlık uzayında arama gerektirir; faz dışı.",
    },
}

# The ONLY place a capability code meets an implementation name.
_DISPATCH: dict[str, str] = {
    "C-POINT": "inspect_cell",
    "C-COMPARE": "compare_mission_profiles",
}

# Params each capability accepts, for K3's schema check.
PARAM_MODELS: dict[str, Optional[type]] = {
    "C-SUMMARY": None,
    "C-POINT": CellRef,
    "C-COMPARE": None,
}


@dataclass
class AnalysisProvider:
    """The AI layer's whole view of the backend.

    An adapter, not a rewrite: ``invoke`` is a dict lookup followed by the
    existing ``ToolRegistry.call``. The two deterministic implementations are
    untouched, and endpoint names stop at this boundary.
    """

    grids: dict
    snapshot: AiMissionSnapshot
    budget: ToolBudget = field(default_factory=ToolBudget)

    def __post_init__(self) -> None:
        self._registry = ToolRegistry(
            grids=self.grids, snapshot=self.snapshot, budget=self.budget
        )

    def get_capabilities(self) -> list[dict[str, Any]]:
        return [dict(spec) for spec in CAPABILITIES.values()]

    def get_context(self) -> dict[str, Any]:
        """What K2 needs to route -- and deliberately no metric values.

        A number here is a number the router could echo into its decision,
        so the context carries shape and presence only.
        """
        metadata = self.grids.get("metadata") or {}
        shape = metadata.get("shape") or []
        return {
            "grid": {
                "rows": int(shape[0]) if len(shape) > 0 else None,
                "cols": int(shape[1]) if len(shape) > 1 else None,
                "resolution_m": metadata.get("resolution_m"),
            },
            "rover_id": self.snapshot.roverId,
            "has_plan": self.snapshot.currentPlan is not None,
            "has_endpoints": self.snapshot.start is not None
            and self.snapshot.goal is not None,
            "has_focused_cell": self.snapshot.focusedCell is not None,
        }

    def invoke(
        self, capability: str, params: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        if capability == "C-SUMMARY":
            # Already sanitized by ai_evidence before it reached the snapshot.
            return {"plan": self.snapshot.currentPlan}
        name = _DISPATCH.get(capability)
        if name is None:
            raise AiToolError(
                "UNKNOWN_TOOL", f"{capability!r} is not an available capability."
            )
        return self._registry.call(name, params or {})
