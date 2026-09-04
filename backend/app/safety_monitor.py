"""Formal safety requirements as an STL robustness monitor (D3).

Three things live here, deliberately in one pure module (no FastAPI, no
ROS) so the API shell and the ROS shell call the same code:

1. **A small STL AST and two robustness engines.** Formulas are built as
   Python objects (``Always(Atom("soc_pct", ">=", 20))``), rendered to
   RTAMT's textual syntax for the RTAMT engine and evaluated directly by
   the built-in engine. Both implement the discrete-time *space*
   robustness of Donze & Maler (2010) with RTAMT 0.3.5's finite-trace
   conventions, measured on 2026-09-04 and pinned in test_safety_monitor:
   a bounded window is clipped to the samples that exist, an empty window
   is vacuous (+inf for always, -inf for eventually), unbounded operators
   run to the end of the trace. When RTAMT is importable every evaluation
   runs on both engines and reports their largest disagreement.

2. **Trace converters.** A 2-D simulation (``simulation.RoverState``), a
   4-D plan (``/api/plan-4d``'s per-state arrays) and a telemetry sample
   list become the same thing: a time axis in hours plus named signals.
   Time-windowed behaviour ("at most H hours of continuous shadow",
   "charging within 6 hours of dropping under the reserve") is folded into
   DERIVED HOUR COUNTERS so every catalogue formula is an unbounded G/F
   whose robustness is in hours, degrees, Celsius or percentage points and
   independent of the sampling step.

3. **The requirement catalogue.** Eleven requirements written in FRETISH
   (NASA FRET's structured natural language; the FRET tool itself was NOT
   used -- the sentences follow its grammar by hand), each translated to
   STL by hand with its threshold read from the rover catalogue. What the
   monitor establishes is that a CONCRETE TRACE satisfies the requirements
   with a quantified margin; it proves nothing about all traces. Every
   response says so.

References: Giannakopoulou et al., "Formal Requirements Elicitation with
FRET" (NASA/TM-2020); Nickovic & Yamaguchi, "RTAMT: Online Robustness
Monitors from STL" (ATVA 2020, arXiv 2005.11827).
"""

from __future__ import annotations

import contextlib
import io
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

# ═══════════════════════════════════════════════════════════════════════
# 1. STL AST
# ═══════════════════════════════════════════════════════════════════════

_COMPARISONS = (">=", "<=", ">", "<")


@dataclass(frozen=True)
class Atom:
    """``signal op threshold``. Strict and non-strict comparisons share a
    robustness (the boundary has measure zero); both spellings are kept so
    the rendered formula reads the way the requirement was written."""

    signal: str
    op: str
    threshold: float

    def __post_init__(self) -> None:
        if self.op not in _COMPARISONS:
            raise ValueError(f"unknown comparison {self.op!r}; use one of {_COMPARISONS}")


@dataclass(frozen=True)
class Not:
    operand: Any


@dataclass(frozen=True)
class And:
    operands: tuple

    def __init__(self, *operands: Any) -> None:
        if len(operands) < 2:
            raise ValueError("And needs at least two operands")
        object.__setattr__(self, "operands", tuple(operands))


@dataclass(frozen=True)
class Or:
    operands: tuple

    def __init__(self, *operands: Any) -> None:
        if len(operands) < 2:
            raise ValueError("Or needs at least two operands")
        object.__setattr__(self, "operands", tuple(operands))


@dataclass(frozen=True)
class Implies:
    antecedent: Any
    consequent: Any


@dataclass(frozen=True)
class Always:
    """``G[lo,hi] operand``; bounds in HOURS, ``hi=None`` for unbounded."""

    operand: Any
    lo: float = 0.0
    hi: float | None = None

    def __post_init__(self) -> None:
        _check_bounds(self.lo, self.hi)


@dataclass(frozen=True)
class Eventually:
    operand: Any
    lo: float = 0.0
    hi: float | None = None

    def __post_init__(self) -> None:
        _check_bounds(self.lo, self.hi)


@dataclass(frozen=True)
class Until:
    left: Any
    right: Any
    lo: float = 0.0
    hi: float | None = None

    def __post_init__(self) -> None:
        _check_bounds(self.lo, self.hi)


Formula = Atom | Not | And | Or | Implies | Always | Eventually | Until


def _check_bounds(lo: float, hi: float | None) -> None:
    if lo < 0.0 or not math.isfinite(lo):
        raise ValueError(f"interval start must be a finite non-negative number, got {lo}")
    if hi is None:
        if lo != 0.0:
            raise ValueError("an unbounded interval must start at 0 (only [0, inf) is supported)")
        return
    if not math.isfinite(hi) or hi < lo:
        raise ValueError(f"interval end must be finite and >= start, got [{lo}, {hi}]")


def _fmt(value: float) -> str:
    """Render a threshold the way a person wrote it: ``20`` not ``20.0``."""
    if float(value).is_integer():
        return str(int(value))
    return repr(float(value))


def _window_samples(lo: float, hi: float | None, dt_h: float | None) -> tuple[int, int | None]:
    """Convert an interval in hours to sample indices; refuse an inexact one."""
    if hi is None:
        return 0, None
    if dt_h is None or not (dt_h > 0.0):
        raise ValueError("a bounded temporal operator needs a positive uniform sampling step dt_h")

    def _to_samples(hours: float) -> int:
        n = hours / dt_h
        if abs(n - round(n)) > 1e-9:
            raise ValueError(f"interval bound {hours} h is not a multiple of dt_h={dt_h} h")
        return int(round(n))

    return _to_samples(lo), _to_samples(hi)


def _interval_text(lo: float, hi: float | None, dt_h: float | None) -> str:
    a, b = _window_samples(lo, hi, dt_h)
    return "" if b is None else f"[{a},{b}]"


def _render(formula: Formula, dt_h: float | None) -> str:
    """Every node parenthesised, so nesting never depends on precedence."""
    if isinstance(formula, Atom):
        return f"({formula.signal} {formula.op} {_fmt(formula.threshold)})"
    if isinstance(formula, Not):
        return f"(not {_render(formula.operand, dt_h)})"
    if isinstance(formula, And):
        return "(" + " and ".join(_render(f, dt_h) for f in formula.operands) + ")"
    if isinstance(formula, Or):
        return "(" + " or ".join(_render(f, dt_h) for f in formula.operands) + ")"
    if isinstance(formula, Implies):
        return f"({_render(formula.antecedent, dt_h)} -> {_render(formula.consequent, dt_h)})"
    if isinstance(formula, Always):
        return f"(always{_interval_text(formula.lo, formula.hi, dt_h)} {_render(formula.operand, dt_h)})"
    if isinstance(formula, Eventually):
        return f"(eventually{_interval_text(formula.lo, formula.hi, dt_h)} {_render(formula.operand, dt_h)})"
    if isinstance(formula, Until):
        return (
            f"({_render(formula.left, dt_h)} until{_interval_text(formula.lo, formula.hi, dt_h)} "
            f"{_render(formula.right, dt_h)})"
        )
    raise TypeError(f"not an STL formula: {formula!r}")


def to_rtamt(formula: Formula, dt_h: float | None = None) -> str:
    """The formula in RTAMT's textual STL, windows in samples of *dt_h*.

    A top-level temporal operator is printed without its outer parentheses
    (``always (soc_pct >= 20)``) -- the way the catalogue reads."""
    text = _render(formula, dt_h)
    if isinstance(formula, (Always, Eventually)):
        return text[1:-1]
    return text


def signals_of(formula: Formula) -> set[str]:
    if isinstance(formula, Atom):
        return {formula.signal}
    if isinstance(formula, Not):
        return signals_of(formula.operand)
    if isinstance(formula, (And, Or)):
        return set().union(*(signals_of(f) for f in formula.operands))
    if isinstance(formula, Implies):
        return signals_of(formula.antecedent) | signals_of(formula.consequent)
    if isinstance(formula, (Always, Eventually)):
        return signals_of(formula.operand)
    if isinstance(formula, Until):
        return signals_of(formula.left) | signals_of(formula.right)
    raise TypeError(f"not an STL formula: {formula!r}")


# ═══════════════════════════════════════════════════════════════════════
# 2. Engines
# ═══════════════════════════════════════════════════════════════════════


def _suffix_min(values: np.ndarray) -> np.ndarray:
    return np.minimum.accumulate(values[::-1])[::-1]


def _suffix_max(values: np.ndarray) -> np.ndarray:
    return np.maximum.accumulate(values[::-1])[::-1]


def _windowed(values: np.ndarray, a: int, b: int | None, reduce, empty: float) -> np.ndarray:
    """``out[i] = reduce(values[i+a : i+b+1])`` clipped to the trace; *empty*
    where the window holds no sample (RTAMT's vacuous value)."""
    n = values.shape[0]
    if b is None:
        if a == 0:
            return _suffix_min(values) if reduce is np.min else _suffix_max(values)
        raise ValueError("unbounded windows must start at 0")
    out = np.full(n, empty, dtype=np.float64)
    for i in range(n):
        start, stop = i + a, min(n - 1, i + b)
        if start <= stop:
            out[i] = reduce(values[start : stop + 1])
    return out


def robustness_builtin(
    formula: Formula, signals: Mapping[str, np.ndarray], dt_h: float | None = None
) -> np.ndarray:
    """Robustness of *formula* at every sample of the trace, ``(T,)`` float64.

    *signals* maps a name to a ``(T,)`` array (all the same length); *dt_h*
    is the uniform sampling step, needed only by bounded operators.
    """
    if isinstance(formula, Atom):
        if formula.signal not in signals:
            raise KeyError(f"signal {formula.signal!r} is not in the trace")
        x = np.asarray(signals[formula.signal], dtype=np.float64)
        if formula.op in (">=", ">"):
            return x - float(formula.threshold)
        return float(formula.threshold) - x
    if isinstance(formula, Not):
        return -robustness_builtin(formula.operand, signals, dt_h)
    if isinstance(formula, And):
        return np.minimum.reduce([robustness_builtin(f, signals, dt_h) for f in formula.operands])
    if isinstance(formula, Or):
        return np.maximum.reduce([robustness_builtin(f, signals, dt_h) for f in formula.operands])
    if isinstance(formula, Implies):
        return np.maximum(
            -robustness_builtin(formula.antecedent, signals, dt_h),
            robustness_builtin(formula.consequent, signals, dt_h),
        )
    if isinstance(formula, Always):
        a, b = _window_samples(formula.lo, formula.hi, dt_h)
        return _windowed(robustness_builtin(formula.operand, signals, dt_h), a, b, np.min, math.inf)
    if isinstance(formula, Eventually):
        a, b = _window_samples(formula.lo, formula.hi, dt_h)
        return _windowed(robustness_builtin(formula.operand, signals, dt_h), a, b, np.max, -math.inf)
    if isinstance(formula, Until):
        a, b = _window_samples(formula.lo, formula.hi, dt_h)
        left = robustness_builtin(formula.left, signals, dt_h)
        right = robustness_builtin(formula.right, signals, dt_h)
        n = left.shape[0]
        out = np.full(n, -math.inf, dtype=np.float64)
        for i in range(n):
            stop = n - 1 if b is None else min(n - 1, i + b)
            best = -math.inf
            running_left = math.inf  # min of left over [i, j)
            for j in range(i, stop + 1):
                if j >= i + a:
                    best = max(best, min(right[j], running_left))
                running_left = min(running_left, left[j])
            out[i] = best
        return out
    raise TypeError(f"not an STL formula: {formula!r}")


def _import_rtamt():
    """The rtamt module, or None. Kept as a function so tests can stand in
    for an environment without the package."""
    try:
        import rtamt  # type: ignore
    except Exception:  # noqa: BLE001 - any import failure means "not available"
        return None
    return rtamt


def rtamt_available() -> bool:
    return _import_rtamt() is not None


def rtamt_version() -> str | None:
    if _import_rtamt() is None:
        return None
    try:
        from importlib.metadata import version

        return version("rtamt")
    except Exception:  # noqa: BLE001
        return "unknown"


def robustness_rtamt(
    formula: Formula, signals: Mapping[str, np.ndarray], dt_h: float | None = None
) -> np.ndarray:
    """The same robustness from RTAMT's discrete-time offline monitor.

    RTAMT prints an ANTLR version notice when its parser (generated with
    ANTLR 4.7.2) runs on a newer runtime; it is harmless and silenced here
    so it does not land in the server log on every request.
    """
    rtamt = _import_rtamt()
    if rtamt is None:
        raise ImportError("rtamt is not installed (pip install rtamt==0.3.5)")
    names = sorted(signals_of(formula))
    for name in names:
        if name not in signals:
            raise KeyError(f"signal {name!r} is not in the trace")
    lengths = {int(np.asarray(signals[name]).shape[0]) for name in names}
    if len(lengths) != 1:
        raise ValueError(f"signals have different lengths: {sorted(lengths)}")
    n = lengths.pop()

    spec = rtamt.StlDiscreteTimeSpecification()
    for name in names:
        spec.declare_var(name, "float")
    spec.spec = to_rtamt(formula, dt_h)
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        spec.parse()
        dataset = {"time": list(range(n))}
        for name in names:
            dataset[name] = [float(v) for v in np.asarray(signals[name], dtype=np.float64)]
        result = spec.evaluate(dataset)
    return np.asarray([float(rho) for _t, rho in result], dtype=np.float64)


ENGINES = ("auto", "builtin", "rtamt")


def robustness(
    formula: Formula,
    signals: Mapping[str, np.ndarray],
    dt_h: float | None = None,
    engine: str = "auto",
) -> tuple[np.ndarray, str]:
    """``(rho, engine_used)``. ``auto`` prefers RTAMT when importable."""
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}; use one of {ENGINES}")
    if engine == "rtamt" or (engine == "auto" and rtamt_available()):
        return robustness_rtamt(formula, signals, dt_h), "rtamt"
    return robustness_builtin(formula, signals, dt_h), "builtin"


# ═══════════════════════════════════════════════════════════════════════
# 3. Traces: one time axis in hours, named signals, derived hour counters
# ═══════════════════════════════════════════════════════════════════════

from .constants import get_rover  # noqa: E402
from .cost_engine import lateral_slope_from_gradient, surface_to_inner  # noqa: E402
from .simulation import MAX_RECHARGE_HOURS  # noqa: E402

#: "In shadow" is the same corridor/simulation threshold, so the shadow
#: counter here reproduces simulation.summarize_simulation's
#: max_continuous_shadow_h exactly.
SHADOW_THRESHOLD = 0.2
#: A stranded trace is extended by one lunar day with the rover parked where
#: it stopped: simulate_path's own verdict is that the battery cannot be
#: refilled inside that time, so "charging never begins" is the simulator's
#: statement, not an assumption of the monitor.
STRANDED_EXTENSION_H = float(MAX_RECHARGE_HOURS)

#: Signal names a trace may carry (the catalogue reads these).
SIGNAL_NAMES: tuple[str, ...] = (
    "soc_pct",
    "charging",
    "in_shadow",
    "shadow_continuous_h",
    "hours_below_reserve_h",
    "inner_temp_c",
    "drive_slope_deg",
    "lateral_slope_deg",
    "moving",
    "earth_link_h",
    "haven_margin_h",
    "dist_to_goal_m",
    "at_goal",
)

#: Telemetry keys /api/safety-check and the ROS node understand.
SAMPLE_KEYS: tuple[str, ...] = (
    "t_h",
    "row",
    "col",
    "soc_pct",
    "surface_temp_c",
    "inner_temp_c",
    "shadow_ratio",
    "in_shadow",
    "slope_deg",
    "lateral_slope_deg",
    "moving",
    "charging",
    "earth_link_h",
    "haven_margin_h",
    "dist_to_goal_m",
    "at_goal",
)
_SAMPLE_BOOLEANS = ("in_shadow", "moving", "charging", "at_goal")


@dataclass
class Trace:
    """A monitored trace: time in hours plus named ``(S,)`` float signals."""

    kind: str  # "2d" | "4d" | "telemetry"
    t_h: np.ndarray
    signals: dict[str, np.ndarray]
    index: np.ndarray  # source state / sample index per sample
    cells: list[tuple[int, int]] | None
    complete: bool = True
    stranded: bool = False
    extended_h: float | None = None
    notes: dict[str, Any] = field(default_factory=dict)

    @property
    def n_samples(self) -> int:
        return int(self.t_h.shape[0])

    @property
    def duration_h(self) -> float:
        return float(self.t_h[-1] - self.t_h[0]) if self.n_samples else 0.0


def continuous_shadow_hours(t_h: np.ndarray, in_shadow: np.ndarray) -> np.ndarray:
    """Running hours in shadow: each sample adds the time since the previous
    sample when it is in shadow and resets the counter when it is lit."""
    t = np.asarray(t_h, dtype=np.float64)
    dark = np.asarray(in_shadow, dtype=bool)
    out = np.zeros(t.shape[0], dtype=np.float64)
    for i in range(1, t.shape[0]):
        out[i] = out[i - 1] + max(0.0, t[i] - t[i - 1]) if dark[i] else 0.0
    return out


def hours_below_reserve(
    t_h: np.ndarray, soc_pct: np.ndarray, floor_pct: float, charging: np.ndarray
) -> np.ndarray:
    """Causal counter: hours since the last sample at which the battery was
    at or above the reserve OR charging was observed. Zero while either
    holds; it never looks ahead, so the same function serves online."""
    t = np.asarray(t_h, dtype=np.float64)
    soc = np.asarray(soc_pct, dtype=np.float64)
    charge = np.asarray(charging, dtype=bool)
    out = np.zeros(t.shape[0], dtype=np.float64)
    reference = t[0] if t.shape[0] else 0.0
    for i in range(t.shape[0]):
        if soc[i] >= float(floor_pct) or charge[i]:
            reference = t[i]
            out[i] = 0.0
        else:
            out[i] = max(0.0, t[i] - reference)
    return out


def _step_distances(cells: Sequence[tuple[int, int]], resolution_m: float) -> np.ndarray:
    """Distance driven INTO each cell (first is 0): the grid step, its
    diagonal, or 0 for a wait in place -- simulate_path's geometry."""
    res = float(resolution_m)
    out = np.zeros(len(cells), dtype=np.float64)
    for i in range(1, len(cells)):
        d_row = abs(int(cells[i][0]) - int(cells[i - 1][0]))
        d_col = abs(int(cells[i][1]) - int(cells[i - 1][1]))
        if d_row == 0 and d_col == 0:
            out[i] = 0.0
        elif d_row + d_col == 2 and d_row == 1:
            out[i] = res * math.sqrt(2.0)
        else:
            out[i] = res * math.hypot(d_row, d_col)
    return out


def path_step_slopes(
    cells: Sequence[tuple[int, int]], elevation: np.ndarray, resolution_m: float
) -> np.ndarray:
    """The grade of each step, ``atan(|dz| / d)`` in degrees (first is 0)."""
    elev = np.asarray(elevation, dtype=np.float64)
    distances = _step_distances(cells, resolution_m)
    out = np.zeros(len(cells), dtype=np.float64)
    for i in range(1, len(cells)):
        if distances[i] <= 0.0:
            continue
        dz = elev[cells[i][0], cells[i][1]] - elev[cells[i - 1][0], cells[i - 1][1]]
        if math.isfinite(dz):
            out[i] = math.degrees(math.atan2(abs(dz), distances[i]))
    return out


def path_lateral_slopes(
    cells: Sequence[tuple[int, int]], elevation: np.ndarray, resolution_m: float
) -> np.ndarray:
    """Cross-slope of each step in degrees, the planners' rule: the mean of
    the two cells' terrain gradients resolved perpendicular to the heading
    (``cost_engine.lateral_slope_tan``). First is 0; a wait is 0."""
    elev = np.asarray(elevation, dtype=np.float64)
    grad_row, grad_col = np.gradient(elev, float(resolution_m))
    grad_row = np.nan_to_num(grad_row, nan=0.0)
    grad_col = np.nan_to_num(grad_col, nan=0.0)
    out = np.zeros(len(cells), dtype=np.float64)
    for i in range(1, len(cells)):
        (r0, c0), (r1, c1) = cells[i - 1], cells[i]
        d_row, d_col = int(r1) - int(r0), int(c1) - int(c0)
        if d_row == 0 and d_col == 0:
            continue
        norm = math.hypot(d_row, d_col)
        g_row = 0.5 * (grad_row[r0, c0] + grad_row[r1, c1])
        g_col = 0.5 * (grad_col[r0, c0] + grad_col[r1, c1])
        out[i] = lateral_slope_from_gradient(g_row, g_col, d_row / norm, d_col / norm)
    return out


def _soc_floor_pct(rover: Mapping[str, Any]) -> float:
    return float(rover.get("soc_min_pct") or 0.0) * 100.0


def _finish_trace(
    kind: str,
    t: list[float],
    columns: dict[str, list[float]],
    index: list[int],
    cells: list[tuple[int, int]] | None,
    rover: Mapping[str, Any],
    *,
    complete: bool,
    stranded: bool,
    notes: dict[str, Any],
    given_shadow_hours: list[float] | None = None,
) -> Trace:
    """Apply the stranded extension, derive the hour counters, pack."""
    extended_h: float | None = None
    if stranded and len(t) >= 1:
        last_step_h = (t[-1] - t[-2]) if len(t) >= 2 else 0.0
        extension = STRANDED_EXTENSION_H - max(0.0, last_step_h)
        if extension > 0.0:
            extended_h = float(extension)
            t.append(t[-1] + extension)
            for name, values in columns.items():
                held = values[-1]
                if name in ("charging", "moving"):
                    held = 0.0
                values.append(held)
            index.append(index[-1])
            if cells is not None:
                cells.append(cells[-1])
            if given_shadow_hours is not None:
                dark = bool(columns.get("in_shadow", [0.0])[-1])
                given_shadow_hours.append(given_shadow_hours[-1] + extension if dark else 0.0)

    t_arr = np.asarray(t, dtype=np.float64)
    signals: dict[str, np.ndarray] = {
        name: np.asarray(values, dtype=np.float64) for name, values in columns.items()
    }
    if given_shadow_hours is not None:
        signals["shadow_continuous_h"] = np.asarray(given_shadow_hours, dtype=np.float64)
    elif "in_shadow" in signals:
        signals["shadow_continuous_h"] = continuous_shadow_hours(t_arr, signals["in_shadow"] > 0.5)
    if "soc_pct" in signals:
        charging = signals.get("charging", np.zeros(t_arr.shape[0])) > 0.5
        signals["hours_below_reserve_h"] = hours_below_reserve(
            t_arr, signals["soc_pct"], _soc_floor_pct(rover), charging
        )
    return Trace(
        kind=kind,
        t_h=t_arr,
        signals=signals,
        index=np.asarray(index, dtype=np.int64),
        cells=cells,
        complete=complete,
        stranded=stranded,
        extended_h=extended_h,
        notes=dict(notes),
    )


def trace_from_states(
    states: Sequence[Any],
    planned_pixels: Sequence[tuple[int, int]],
    elevation: np.ndarray | None,
    resolution_m: float,
    rover: Mapping[str, Any] | None = None,
) -> Trace:
    """A 2-D simulation (``simulation.simulate_path``) as a trace.

    SOC is the step's LOW point (``battery_low_pct``, before any recharge
    stop) -- the level the reserve rule is about. A charging step is one
    that recharged or whose array income exceeded its draw. The drive
    slope is the worse of the cell slope and the step grade, the quantity
    the simulator costed. ``dist_to_goal_m`` is the planned length minus
    the distance covered, so a stranded prefix ends short of zero.
    """
    if not states:
        raise ValueError("states is empty")
    rover_cfg = get_rover() if rover is None else rover
    planned = [(int(r), int(c)) for r, c in planned_pixels]
    planned_length_m = float(_step_distances(planned, resolution_m).sum()) if planned else 0.0
    cells = [(int(s.row), int(s.col)) for s in states]
    t = [float(s.elapsed_hours) for s in states]
    lateral = (
        path_lateral_slopes(cells, elevation, resolution_m)
        if elevation is not None
        else None
    )
    columns: dict[str, list[float]] = {
        "soc_pct": [float(s.battery_low_pct) for s in states],
        "charging": [
            1.0 if (bool(s.recharged_this_step) or float(s.step_solar_wh) > float(s.step_energy_wh)) else 0.0
            for s in states
        ],
        "in_shadow": [1.0 if float(s.shadow_ratio) > SHADOW_THRESHOLD else 0.0 for s in states],
        "inner_temp_c": [float(surface_to_inner(float(s.surface_temp_c), rover_cfg)) for s in states],
        "drive_slope_deg": [max(float(s.slope_deg), float(s.segment_slope_deg)) for s in states],
        "moving": [0.0] + [1.0 if cells[i] != cells[i - 1] else 0.0 for i in range(1, len(cells))],
        "dist_to_goal_m": [max(0.0, planned_length_m - float(s.distance_m)) for s in states],
    }
    if lateral is not None:
        columns["lateral_slope_deg"] = [float(v) for v in lateral]
    columns["at_goal"] = [1.0 if d <= 1e-6 else 0.0 for d in columns["dist_to_goal_m"]]
    return _finish_trace(
        "2d",
        t,
        columns,
        [int(s.step) for s in states],
        cells,
        rover_cfg,
        complete=True,
        stranded=bool(states[-1].stranded),
        notes={
            "thermal_source": "static_layer",
            "soc_signal": "battery_low_pct",
            "shadow_threshold": SHADOW_THRESHOLD,
            "planned_length_m": round(planned_length_m, 3),
        },
    )


def trace_from_plan4d(
    path_states: Sequence[Sequence[int]],
    path_battery_pct: Sequence[float],
    path_dark_hours: Sequence[float],
    path_earth_visible: Sequence[bool] | None,
    path_hours_until_earthset: Sequence[float | None] | None,
    path_haven_margin_h: Sequence[float | None] | None,
    slice_hours: float,
    coarse_slope: np.ndarray,
    coarse_elevation: np.ndarray,
    coarse_thermal: np.ndarray,
    resolution_m: float,
    rover: Mapping[str, Any] | None = None,
    path_time_to_haven_h: Sequence[float | None] | None = None,
) -> Trace:
    """A ``/api/plan-4d`` route as a trace, on the planner's coarse grid.

    Time is the slice clock; the shadow counter is the planner's own
    ``path_dark_hours``; a move whose arrival cell does not see the Earth
    carries a NEGATIVE Earth-link margin equal to its duration (hours driven
    blind); an open-ended Earthset (None) is +inf; a finite Earthset with no
    reachable haven (``path_time_to_haven_h`` None) is -inf, an unbounded
    violation of the leg rule.
    """
    if not path_states:
        raise ValueError("path_states is empty")
    rover_cfg = get_rover() if rover is None else rover
    step = float(slice_hours)
    cells = [(int(s[0]), int(s[1])) for s in path_states]
    t = [float(int(s[2])) * step for s in path_states]
    n = len(cells)
    if len(path_battery_pct) != n or len(path_dark_hours) != n:
        raise ValueError("path_battery_pct and path_dark_hours must match path_states")
    slope_grid = np.asarray(coarse_slope, dtype=np.float64)
    thermal_grid = np.asarray(coarse_thermal, dtype=np.float64)
    step_slopes = path_step_slopes(cells, coarse_elevation, resolution_m)
    lateral = path_lateral_slopes(cells, coarse_elevation, resolution_m)
    distances = _step_distances(cells, resolution_m)
    total = float(distances.sum())
    covered = np.cumsum(distances)
    battery = [float(v) for v in path_battery_pct]
    moving = [0.0] + [1.0 if cells[i] != cells[i - 1] else 0.0 for i in range(1, n)]
    columns: dict[str, list[float]] = {
        "soc_pct": battery,
        "charging": [0.0] + [1.0 if battery[i] > battery[i - 1] + 1e-9 else 0.0 for i in range(1, n)],
        "in_shadow": [1.0 if float(d) > 0.0 else 0.0 for d in path_dark_hours],
        "inner_temp_c": [float(surface_to_inner(float(thermal_grid[r, c]), rover_cfg)) for r, c in cells],
        "drive_slope_deg": [max(float(slope_grid[r, c]), float(step_slopes[i])) for i, (r, c) in enumerate(cells)],
        "lateral_slope_deg": [float(v) for v in lateral],
        "moving": moving,
        "dist_to_goal_m": [max(0.0, total - float(v)) for v in covered],
    }
    columns["at_goal"] = [1.0 if d <= 1e-6 else 0.0 for d in columns["dist_to_goal_m"]]
    notes: dict[str, Any] = {
        "thermal_source": "static_layer",
        "shadow_source": "planner path_dark_hours",
        "soc_signal": "path_battery_pct",
        "slice_hours": step,
        "planned_length_m": round(total, 3),
    }
    if path_earth_visible is not None:
        if len(path_earth_visible) != n:
            raise ValueError("path_earth_visible must match path_states")
        deadlines = path_hours_until_earthset
        notes["earthset_deadline_available"] = deadlines is not None
        link: list[float] = []
        for i in range(n):
            if bool(path_earth_visible[i]):
                value = None if deadlines is None else deadlines[i]
                link.append(math.inf if value is None else float(value))
            else:
                duration = (t[i] - t[i - 1]) if i > 0 else step
                link.append(-max(duration, 0.0))
        columns["earth_link_h"] = link
    if path_haven_margin_h is not None:
        if len(path_haven_margin_h) != n:
            raise ValueError("path_haven_margin_h must match path_states")
        # A None margin is ambiguous in the planner's arrays: it is +inf when
        # the Earth link is open-ended and -inf when a FINITE deadline meets
        # no reachable haven at all (time_to_haven None). Only the second is
        # a violation, so both inputs are consulted when they are given.
        deadlines = path_hours_until_earthset
        reach = path_time_to_haven_h
        margins: list[float] = []
        unreachable = 0
        for i in range(n):
            given = path_haven_margin_h[i]
            if given is not None:
                margins.append(float(given))
                continue
            deadline = None if deadlines is None else deadlines[i]
            tts = None if reach is None else reach[i]
            if reach is not None and tts is None:
                unreachable += 1
            if deadline is None or reach is None:
                margins.append(math.inf)
            elif tts is None:
                margins.append(-math.inf)
            else:
                margins.append(float(deadline) - float(tts))
        columns["haven_margin_h"] = margins
        notes["haven_unreachable_states"] = unreachable
    return _finish_trace(
        "4d",
        t,
        columns,
        list(range(n)),
        cells,
        rover_cfg,
        complete=True,
        stranded=False,
        notes=notes,
        given_shadow_hours=[float(d) for d in path_dark_hours],
    )


def _as_bool(value: Any, key: str, position: int) -> float:
    if isinstance(value, (bool, np.bool_)):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        if float(value) in (0.0, 1.0):
            return float(value)
    raise ValueError(f"sample {position}: {key} must be a boolean (or 0/1), got {value!r}")


def _as_float(value: Any, key: str, position: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError(f"sample {position}: {key} must be a finite number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"sample {position}: {key} must be finite, got {value!r}")
    return number


def trace_from_samples(
    samples: Sequence[Mapping[str, Any]],
    rover: Mapping[str, Any] | None = None,
    complete: bool = True,
    stranded: bool = False,
) -> Trace:
    """A telemetry sample list (``/api/safety-check``, the ROS node) as a
    trace. Only the signals given appear; a requirement whose signal is
    absent is reported as not applicable, never as satisfied.

    Numeric keys must be present in every sample or in none; the boolean
    keys default to False; ``charging`` is also inferred from a rising
    SOC; ``at_goal`` from ``dist_to_goal_m <= 0`` when not given.
    """
    if not samples:
        raise ValueError("samples is empty")
    rover_cfg = get_rover() if rover is None else rover
    ignored: set[str] = set()
    present: set[str] = set()
    for sample in samples:
        for key in sample:
            (present if key in SAMPLE_KEYS else ignored).add(str(key))

    t: list[float] = []
    for i, sample in enumerate(samples):
        if "t_h" not in sample:
            raise ValueError(f"sample {i}: t_h is required")
        t.append(_as_float(sample["t_h"], "t_h", i))
        if i > 0 and t[i] < t[i - 1]:
            raise ValueError(f"sample {i}: t_h must be non-decreasing ({t[i]} < {t[i - 1]})")

    def numeric(key: str) -> list[float] | None:
        if key not in present:
            return None
        values: list[float] = []
        for i, sample in enumerate(samples):
            if key not in sample:
                raise ValueError(f"sample {i}: {key} is missing (given in another sample)")
            values.append(_as_float(sample[key], key, i))
        return values

    def boolean(key: str) -> list[float] | None:
        if key not in present:
            return None
        return [
            _as_bool(sample[key], key, i) if key in sample else 0.0
            for i, sample in enumerate(samples)
        ]

    columns: dict[str, list[float]] = {}
    notes: dict[str, Any] = {"ignored_keys": sorted(ignored)}

    soc = numeric("soc_pct")
    if soc is not None:
        columns["soc_pct"] = soc
        charging = boolean("charging") or [0.0] * len(soc)
        columns["charging"] = [
            1.0 if (charging[i] > 0.5 or (i > 0 and soc[i] > soc[i - 1] + 1e-9)) else 0.0
            for i in range(len(soc))
        ]
    elif boolean("charging") is not None:
        columns["charging"] = boolean("charging")

    inner = numeric("inner_temp_c")
    if inner is None:
        surface = numeric("surface_temp_c")
        if surface is not None:
            inner = [float(surface_to_inner(v, rover_cfg)) for v in surface]
            notes["thermal_source"] = "surface_temp_c via surface_to_inner"
    else:
        notes["thermal_source"] = "inner_temp_c"
    if inner is not None:
        columns["inner_temp_c"] = inner

    in_shadow = boolean("in_shadow")
    if in_shadow is None:
        ratio = numeric("shadow_ratio")
        if ratio is not None:
            in_shadow = [1.0 if v > SHADOW_THRESHOLD else 0.0 for v in ratio]
    if in_shadow is not None:
        columns["in_shadow"] = in_shadow

    slope = numeric("slope_deg")
    if slope is not None:
        columns["drive_slope_deg"] = slope
    for key, name in (
        ("lateral_slope_deg", "lateral_slope_deg"),
        ("earth_link_h", "earth_link_h"),
        ("haven_margin_h", "haven_margin_h"),
        ("dist_to_goal_m", "dist_to_goal_m"),
    ):
        values = numeric(key)
        if values is not None:
            columns[name] = values
    moving = boolean("moving")
    if moving is not None:
        columns["moving"] = moving
    at_goal = boolean("at_goal")
    if at_goal is None and "dist_to_goal_m" in columns:
        at_goal = [1.0 if d <= 1e-6 else 0.0 for d in columns["dist_to_goal_m"]]
    if at_goal is not None:
        columns["at_goal"] = at_goal

    cells: list[tuple[int, int]] | None = None
    rows, cols = numeric("row"), numeric("col")
    if rows is not None and cols is not None:
        cells = [(int(r), int(c)) for r, c in zip(rows, cols)]

    return _finish_trace(
        "telemetry",
        t,
        columns,
        list(range(len(samples))),
        cells,
        rover_cfg,
        complete=complete,
        stranded=stranded,
        notes=notes,
    )


# ═══════════════════════════════════════════════════════════════════════
# 4. The requirement catalogue
# ═══════════════════════════════════════════════════════════════════════

#: The one threshold the rover catalogue does not carry: how soon charging
#: must begin once the battery is under its reserve. Taken from the research
#: document's example requirement; a request may override it and every
#: response labels it threshold_source "catalogue".
RECHARGE_DEADLINE_H = 6.0
#: Scale for the open-ended hour margins (Earth link, haven) when a
#: dimensionless comparison key is needed: one Earth day.
HOURS_SCALE_H = 24.0
CLAIM = (
    "checked by runtime monitoring of the planned trace (STL robustness); "
    "not proven by model checking -- the verdict is about this trace only"
)
SEMANTICS = (
    "discrete-time offline STL, space robustness (Donze & Maler 2010; RTAMT 0.3.5 "
    "conventions): unbounded G/F over the finite trace, FRET scopes as sample masks"
)
REQUIREMENTS_FILE = "docs/requirements/lunapath.fret.json"
COMPONENT = "the rover"


@dataclass(frozen=True)
class Requirement:
    """One FRETISH requirement and its hand-written STL translation.

    ``kind`` says how the threshold enters the formula: ``upper`` (signal
    <= t), ``lower`` (signal >= t), ``range`` (lo <= signal <= hi) or
    ``eventually_upper`` (F signal <= t). ``scope`` names a 0/1 signal used
    as a sample mask (FRET's "in X mode"). ``normalizer`` picks the scale
    that turns rho into the dimensionless comparison key.
    """

    id: str
    name: str
    cls: str
    scope: str | None
    condition: str | None
    timing: str
    response: str
    rationale: str
    signal: str
    unit: str
    kind: str
    rover_parameter: str | None
    ft_ltl: str
    stl_text: str
    normalizer: str
    trace_kinds: tuple[str, ...]
    notes: str = ""

    @property
    def fretish(self) -> str:
        parts: list[str] = []
        if self.scope is not None:
            parts.append(f"In {self.scope} mode")
        if self.condition is not None:
            parts.append(f"upon {self.condition}")
        parts.append(f"{COMPONENT} shall {self.timing} satisfy {self.response}")
        text = " ".join(parts)
        return text[0].upper() + text[1:]


def _rover_value(rover: Mapping[str, Any], key: str) -> float | None:
    value = rover.get(key)
    return None if value is None else float(value)


def _threshold_for(req: Requirement, rover: Mapping[str, Any], recharge_deadline_h: float):
    """``(threshold, source, reason)`` -- threshold None with a reason when
    the rover does not declare the envelope."""
    if req.id == "LP-R01":
        v = _rover_value(rover, "h_max_shadow_h")
        return v, "rover", None if v is not None else "rover declares no h_max_shadow_h"
    if req.id in ("LP-R02", "LP-R11"):
        v = _rover_value(rover, "soc_min_pct")
        return (None if v is None else v * 100.0), "rover", None if v is not None else "rover declares no soc_min_pct"
    if req.id == "LP-R03":
        return float(recharge_deadline_h), "catalogue", None
    if req.id in ("LP-R04", "LP-R05"):
        prefix = "elec_op" if req.id == "LP-R04" else "bat_op"
        lo, hi = _rover_value(rover, f"{prefix}_min_c"), _rover_value(rover, f"{prefix}_max_c")
        if lo is None or hi is None:
            return None, "rover", f"rover declares no {prefix}_min_c/{prefix}_max_c envelope"
        return (lo, hi), "rover", None
    if req.id == "LP-R06":
        v = _rover_value(rover, "slope_max_deg")
        return v, "rover", None if v is not None else "rover declares no slope_max_deg"
    if req.id == "LP-R07":
        v = _rover_value(rover, "slope_lateral_max_deg")
        return v, "rover", None if v is not None else "rover declares no slope_lateral_max_deg"
    return 0.0, "fixed", None


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        id="LP-R01", name="shadow_endurance", cls="safety", scope=None, condition=None, timing="always",
        response="shadow_continuous_h <= h_max_shadow_h",
        rationale="The rover's battery and heaters are sized for at most h_max_shadow_h of continuous darkness (VIPER: 96 h; LPR-1: 50 h). Longer unbroken shadow is loss of the vehicle.",
        signal="shadow_continuous_h", unit="h", kind="upper", rover_parameter="h_max_shadow_h",
        ft_ltl="G (shadow_continuous_h <= h_max_shadow_h)   [boolean form: G (F[0,h_max_shadow_h] lit)]",
        stl_text="always (shadow_continuous_h <= h_max_shadow_h)", normalizer="threshold", trace_kinds=("2d", "4d", "telemetry"),
        notes="shadow_continuous_h is the running count of hours in shadow (shadow_ratio > 0.2, the simulator's threshold), reset when lit; 4-D traces use the planner's path_dark_hours.",
    ),
    Requirement(
        id="LP-R02", name="soc_reserve", cls="safety", scope=None, condition=None, timing="always",
        response="soc_pct >= soc_min",
        rationale="The reserve (soc_min_pct) is the energy kept for survival heating; the plan must never spend it.",
        signal="soc_pct", unit="pct", kind="lower", rover_parameter="soc_min_pct",
        ft_ltl="G (soc_pct >= soc_min)", stl_text="always (soc_pct >= soc_min)", normalizer="threshold",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="2-D traces use battery_low_pct, the step's low point before any recharge stop.",
    ),
    Requirement(
        id="LP-R03", name="soc_recovery", cls="safety", scope=None, condition="soc_pct < soc_min", timing="within 6 hours",
        response="charging",
        rationale="A rover under its reserve must start recovering promptly; the deadline bounds how long it may sit in deficit.",
        signal="hours_below_reserve_h", unit="h", kind="upper", rover_parameter=None,
        ft_ltl="G ((soc_pct < soc_min) -> F[0,6h] charging)",
        stl_text="always (hours_below_reserve_h <= recharge_deadline_h)", normalizer="threshold",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="Monitored through the causal counter hours_below_reserve_h (hours since the battery was last at or above the reserve or charging was observed), so the margin is in hours and needs no bounded window. The 6 h deadline is a catalogue constant, not a rover parameter.",
    ),
    Requirement(
        id="LP-R04", name="electronics_thermal", cls="safety", scope=None, condition=None, timing="always",
        response="elec_op_min_c <= inner_temp_c <= elec_op_max_c",
        rationale="Avionics survive only inside their operating envelope; the inner temperature is the surface temperature plus the rover's thermal offset.",
        signal="inner_temp_c", unit="degC", kind="range", rover_parameter="elec_op_min_c/elec_op_max_c",
        ft_ltl="G (inner_temp_c >= elec_op_min_c & inner_temp_c <= elec_op_max_c)",
        stl_text="always ((inner_temp_c >= elec_op_min_c) and (inner_temp_c <= elec_op_max_c))", normalizer="half_range",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="inner_temp_c = cost_engine.surface_to_inner(surface_temp_c, rover). Rovers without an electronics envelope (LUVMI-M) report this requirement as not applicable.",
    ),
    Requirement(
        id="LP-R05", name="battery_thermal", cls="safety", scope=None, condition=None, timing="always",
        response="bat_op_min_c <= inner_temp_c <= bat_op_max_c",
        rationale="Lithium cells neither charge nor discharge safely outside their envelope.",
        signal="inner_temp_c", unit="degC", kind="range", rover_parameter="bat_op_min_c/bat_op_max_c",
        ft_ltl="G (inner_temp_c >= bat_op_min_c & inner_temp_c <= bat_op_max_c)",
        stl_text="always ((inner_temp_c >= bat_op_min_c) and (inner_temp_c <= bat_op_max_c))", normalizer="half_range",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="Uses the same inner-temperature model as LP-R04; LunaPath has no separate battery thermal model.",
    ),
    Requirement(
        id="LP-R06", name="step_slope", cls="safety", scope=None, condition=None, timing="always",
        response="drive_slope_deg <= slope_max_deg",
        rationale="The traction limit the planners gate every edge on; the simulator costs the worse of the cell slope and the step grade.",
        signal="drive_slope_deg", unit="deg", kind="upper", rover_parameter="slope_max_deg",
        ft_ltl="G (drive_slope_deg <= slope_max_deg)", stl_text="always (drive_slope_deg <= slope_max_deg)",
        normalizer="threshold", trace_kinds=("2d", "4d", "telemetry"),
    ),
    Requirement(
        id="LP-R07", name="cross_slope", cls="safety", scope=None, condition=None, timing="always",
        response="lateral_slope_deg <= slope_lateral_max_deg",
        rationale="Roll-over limit: the terrain gradient resolved perpendicular to the heading (cost_engine.lateral_slope_tan, the planners' rule).",
        signal="lateral_slope_deg", unit="deg", kind="upper", rover_parameter="slope_lateral_max_deg",
        ft_ltl="G (lateral_slope_deg <= slope_lateral_max_deg)", stl_text="always (lateral_slope_deg <= slope_lateral_max_deg)",
        normalizer="threshold", trace_kinds=("2d", "4d", "telemetry"),
    ),
    Requirement(
        id="LP-R08", name="dte_while_moving", cls="safety", scope="moving", condition=None, timing="always",
        response="earth_visible",
        rationale="VIPER's teleoperation rule: the rover does not drive without a direct-to-Earth link (A4).",
        signal="earth_link_h", unit="h", kind="lower", rover_parameter=None,
        ft_ltl="G (moving -> earth_visible)", stl_text="always (moving -> (earth_link_h > 0))", normalizer="hours_per_day",
        trace_kinds=("4d", "telemetry"),
        notes="Time-robustness proxy: earth_link_h is the hours of Earth link left at a state that sees the Earth (path_hours_until_earthset; open-ended = +inf) and minus the move's duration -- hours driven blind -- at one that does not.",
    ),
    Requirement(
        id="LP-R09", name="safe_haven_leg", cls="safety", scope=None, condition=None, timing="always",
        response="time_to_haven_h <= hours_until_earthset",
        rationale="VIPER's leg rule (A1): from every state the rover can reach a safe haven before it loses the Earth link.",
        signal="haven_margin_h", unit="h", kind="lower", rover_parameter=None,
        ft_ltl="G (hours_until_earthset - time_to_haven_h >= 0)", stl_text="always (haven_margin_h >= 0)", normalizer="hours_per_day",
        trace_kinds=("4d", "telemetry"),
        notes="haven_margin_h is path_haven_margin_h from /api/plan-4d (open-ended Earthset = +inf).",
    ),
    Requirement(
        id="LP-R10", name="goal_reached", cls="mission", scope=None, condition=None, timing="eventually",
        response="at_goal",
        rationale="The traverse is a mission only if it ends at the goal; a stranded prefix stops short.",
        signal="dist_to_goal_m", unit="m", kind="eventually_upper", rover_parameter=None,
        ft_ltl="F at_goal", stl_text="eventually (dist_to_goal_m <= 0)", normalizer="path_length",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="Robustness is minus the closest approach in metres: 0 when reached, -(remaining distance) when not.",
    ),
    Requirement(
        id="LP-R11", name="soc_at_goal", cls="safety", scope="at_goal", condition=None, timing="always",
        response="soc_pct >= soc_min",
        rationale="Arriving with the reserve intact is what makes the next leg plannable.",
        signal="soc_pct", unit="pct", kind="lower", rover_parameter="soc_min_pct",
        ft_ltl="G (at_goal -> soc_pct >= soc_min)", stl_text="always (at_goal -> (soc_pct >= soc_min))", normalizer="threshold",
        trace_kinds=("2d", "4d", "telemetry"),
        notes="Scope at_goal is a sample mask; inapplicable when the goal is never reached (LP-R10 reports that).",
    ),
)


@dataclass(frozen=True)
class BoundRequirement:
    requirement: Requirement
    threshold: Any
    threshold_source: str
    formula: Any
    applicable: bool
    reason: str | None


def _formula_for(req: Requirement, threshold: Any) -> Formula:
    sig = req.signal
    if req.kind == "upper":
        return Always(Atom(sig, "<=", float(threshold)))
    if req.kind == "lower":
        op = ">" if req.id == "LP-R08" else ">="
        return Always(Atom(sig, op, float(threshold)))
    if req.kind == "range":
        lo, hi = threshold
        return Always(And(Atom(sig, ">=", float(lo)), Atom(sig, "<=", float(hi))))
    if req.kind == "eventually_upper":
        return Eventually(Atom(sig, "<=", float(threshold)))
    raise ValueError(f"unknown requirement kind {req.kind!r}")


def bind_catalogue(
    rover: Mapping[str, Any] | None = None, recharge_deadline_h: float = RECHARGE_DEADLINE_H
) -> list[BoundRequirement]:
    """Every requirement with its threshold read from *rover*."""
    rover_cfg = get_rover() if rover is None else rover
    if not (float(recharge_deadline_h) > 0.0) or not math.isfinite(float(recharge_deadline_h)):
        raise ValueError("recharge_deadline_h must be a positive finite number of hours")
    bound: list[BoundRequirement] = []
    for req in REQUIREMENTS:
        threshold, source, reason = _threshold_for(req, rover_cfg, recharge_deadline_h)
        if threshold is None:
            bound.append(BoundRequirement(req, None, source, None, False, reason))
            continue
        bound.append(BoundRequirement(req, threshold, source, _formula_for(req, threshold), True, None))
    return bound


def _scale_for(req: Requirement, threshold: Any, trace: Trace) -> float | None:
    if req.normalizer == "threshold":
        scale = abs(float(threshold))
    elif req.normalizer == "half_range":
        lo, hi = threshold
        scale = 0.5 * (float(hi) - float(lo))
    elif req.normalizer == "hours_per_day":
        scale = HOURS_SCALE_H
    elif req.normalizer == "path_length":
        planned = trace.notes.get("planned_length_m")
        if planned is None and "dist_to_goal_m" in trace.signals:
            finite = trace.signals["dist_to_goal_m"][np.isfinite(trace.signals["dist_to_goal_m"])]
            planned = float(finite.max()) if finite.size else None
        scale = None if planned is None else float(planned)
    else:
        raise ValueError(f"unknown normalizer {req.normalizer!r}")
    return scale if scale is not None and scale > 0.0 else None


def _operand(formula: Formula) -> Formula:
    return formula.operand if isinstance(formula, (Always, Eventually)) else formula


def _max_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    both_inf = np.isinf(a) & np.isinf(b) & (np.sign(a) == np.sign(b))
    with np.errstate(invalid="ignore"):
        diff = np.abs(a - b)
    diff[both_inf] = 0.0
    return float(np.nanmax(diff)) if diff.size else 0.0


def _float_or_none(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _threshold_json(threshold: Any):
    if threshold is None:
        return None
    if isinstance(threshold, tuple):
        return [float(v) for v in threshold]
    return float(threshold)


def _entry_base(bound: BoundRequirement) -> dict[str, Any]:
    req = bound.requirement
    return {
        "id": req.id,
        "name": req.name,
        "class": req.cls,
        "applicable": True,
        "reason": None,
        "engine": None,
        "rho": None,
        "unit": req.unit,
        "rho_normalized": None,
        "satisfied": None,
        "boundary": False,
        "open_ended": False,
        "pending": False,
        "threshold": _threshold_json(bound.threshold),
        "rover_parameter": req.rover_parameter,
        "threshold_source": bound.threshold_source,
        "signal": req.signal,
        "scope": req.scope,
        "worst_at": None,
        "fretish": req.fretish,
        "stl": None if bound.formula is None else to_rtamt(bound.formula),
    }


def _inapplicable(bound: BoundRequirement, reason: str) -> dict[str, Any]:
    entry = _entry_base(bound)
    entry["applicable"] = False
    entry["reason"] = reason
    return entry


def evaluate_catalogue(
    trace: Trace,
    rover: Mapping[str, Any] | None = None,
    engine: str = "auto",
    recharge_deadline_h: float = RECHARGE_DEADLINE_H,
) -> dict[str, Any]:
    """The ``safety_margins`` block for *trace*: one entry per requirement
    with its robustness, unit, verdict and where along the trace the margin
    is smallest; plus the smallest normalised margin and an overall verdict.

    Raises ImportError when ``engine="rtamt"`` is requested but the package
    is not importable (callers turn that into a client error rather than a
    silent fallback)."""
    rover_cfg = get_rover() if rover is None else rover
    if engine not in ENGINES:
        raise ValueError(f"unknown engine {engine!r}; use one of {ENGINES}")
    use_rtamt = engine == "rtamt" or (engine == "auto" and rtamt_available())
    if engine == "rtamt" and not rtamt_available():
        raise ImportError("rtamt is not installed (pip install rtamt==0.3.5)")
    engine_used = "rtamt" if use_rtamt else "builtin"

    entries: list[dict[str, Any]] = []
    max_diff = 0.0
    for bound in bind_catalogue(rover_cfg, recharge_deadline_h):
        req = bound.requirement
        if not bound.applicable:
            entries.append(_inapplicable(bound, bound.reason or "not applicable for this rover"))
            continue
        if req.signal not in trace.signals:
            entries.append(_inapplicable(bound, f"signal {req.signal} not in trace"))
            continue
        if req.scope is not None and req.scope not in trace.signals:
            entries.append(_inapplicable(bound, f"scope signal {req.scope} not in trace"))
            continue
        if req.scope is not None:
            mask = trace.signals[req.scope] > 0.5
            if not bool(mask.any()):
                entries.append(_inapplicable(bound, f"scope {req.scope} never active in this trace"))
                continue
            picks = np.flatnonzero(mask)
        else:
            picks = np.arange(trace.n_samples)
        signals = {req.signal: np.asarray(trace.signals[req.signal], dtype=np.float64)[picks]}

        # RTAMT's discrete-time offline interpreter needs at least two
        # samples to derive a sampling period; a one-sample scope (the goal
        # state) is evaluated by the built-in engine, and the entry says so.
        entry_engine = "rtamt" if (use_rtamt and picks.size >= 2) else "builtin"
        if entry_engine == "rtamt":
            rho_series = robustness_rtamt(bound.formula, signals)
            check = robustness_builtin(bound.formula, signals)
            max_diff = max(max_diff, _max_abs_diff(rho_series, check))
        else:
            rho_series = robustness_builtin(bound.formula, signals)
        rho0 = float(rho_series[0])
        inner = robustness_builtin(_operand(bound.formula), signals)
        worst_local = int(np.argmax(inner)) if isinstance(bound.formula, Eventually) else int(np.argmin(inner))
        worst_k = int(picks[worst_local])

        entry = _entry_base(bound)
        entry["engine"] = entry_engine
        if math.isinf(rho0) and rho0 > 0.0:
            entry.update(rho=None, open_ended=True, satisfied=True, worst_at=None)
        else:
            satisfied: bool | None = rho0 >= 0.0
            pending = False
            if isinstance(bound.formula, Eventually) and not trace.complete and rho0 < 0.0:
                satisfied, pending = None, True
            scale = _scale_for(req, bound.threshold, trace)
            worst = {"index": int(trace.index[worst_k]), "hours": round(float(trace.t_h[worst_k]), 4)}
            if trace.cells is not None:
                worst["row"], worst["col"] = int(trace.cells[worst_k][0]), int(trace.cells[worst_k][1])
            entry.update(
                rho=_float_or_none(rho0),
                rho_normalized=None if (scale is None or not math.isfinite(rho0)) else round(rho0 / scale, 6),
                satisfied=satisfied,
                boundary=bool(rho0 == 0.0),
                pending=pending,
                worst_at=worst,
            )
            if not math.isfinite(rho0):
                entry["satisfied"] = False
                entry["reason"] = "unbounded violation"
        entries.append(entry)

    applicable = [e for e in entries if e["applicable"]]
    violated = [e["id"] for e in applicable if e["satisfied"] is False]
    pending_any = any(e["pending"] for e in applicable)
    if not applicable:
        verdict = "not_evaluated"
    elif violated:
        verdict = "violated"
    elif pending_any:
        verdict = "pending"
    else:
        verdict = "satisfied"
    candidates = [e for e in applicable if e["class"] == "safety" and e["rho_normalized"] is not None]
    min_margin = None
    if candidates:
        smallest = min(candidates, key=lambda e: e["rho_normalized"])
        min_margin = {
            "id": smallest["id"],
            "rho": smallest["rho"],
            "unit": smallest["unit"],
            "rho_normalized": smallest["rho_normalized"],
        }

    trace_info: dict[str, Any] = {
        "kind": trace.kind,
        "n_samples": trace.n_samples,
        "duration_h": round(trace.duration_h, 4),
        "complete": bool(trace.complete),
        "stranded": bool(trace.stranded),
        "extended_h": _float_or_none(trace.extended_h, 4),
    }
    for key, value in trace.notes.items():
        if key not in trace_info:
            trace_info[key] = value
    return {
        "monitor": {
            "engine": engine_used,
            "rtamt_version": rtamt_version() if use_rtamt else None,
            "cross_check": {"engine": "builtin", "max_abs_diff": round(max_diff, 9)} if use_rtamt else None,
            "semantics": SEMANTICS,
            "trace": trace_info,
            "recharge_deadline_h": float(recharge_deadline_h),
            "claim": CLAIM,
            "requirements_file": REQUIREMENTS_FILE,
        },
        "requirements": entries,
        "min_margin": min_margin,
        "n_applicable": len(applicable),
        "n_violated": len(violated),
        "violated": violated,
        "verdict": verdict,
    }


_VERDICT_ORDER = {"satisfied": 0, "pending": 1, "violated": 2, "not_evaluated": 3}


def rank_by_margin(items: Sequence[tuple[str, Mapping[str, Any]]]) -> list[dict[str, Any]]:
    """Rank ``(label, safety_margins)`` pairs: satisfied routes by largest
    smallest-margin first, then pending, then violated (fewest violations,
    least negative margin), unevaluated last."""

    def key(item: tuple[str, Mapping[str, Any]]):
        block = item[1]
        margin = block.get("min_margin") or {}
        normalized = margin.get("rho_normalized")
        return (
            _VERDICT_ORDER.get(str(block.get("verdict")), 3),
            int(block.get("n_violated") or 0),
            -(normalized if normalized is not None else -math.inf),
        )

    ranked = []
    for label, block in sorted(items, key=key):
        ranked.append(
            {
                "label": label,
                "verdict": block.get("verdict"),
                "n_violated": int(block.get("n_violated") or 0),
                "min_margin": block.get("min_margin"),
            }
        )
    return ranked


# ═══════════════════════════════════════════════════════════════════════
# 5. FRET-style export of the catalogue
# ═══════════════════════════════════════════════════════════════════════

FRET_ROVERS: tuple[str, ...] = ("lpr_1", "luvmi_m", "nasa_viper", "cnsa_yutu_2")
FRET_REFERENCE = (
    "Giannakopoulou, Mavridou, Pressburger, Schumann et al., Formal Requirements "
    "Elicitation with FRET, NASA Ames (github.com/NASA-SW-VnV/fret)"
)
RTAMT_REFERENCE = "Nickovic & Yamaguchi, RTAMT: Online Robustness Monitors from STL (github.com/nickovic/rtamt)"


def fret_export() -> dict[str, Any]:
    """The catalogue as a FRET-like requirement file: FRET's own export
    fields (``reqid``, ``fulltext``, ``rationale``, ``semantics`` with
    scope/condition/component/timing/response and the temporal-logic
    strings) plus a ``monitor`` block saying which signal, unit and rover
    parameter each requirement is checked against. Deterministic (no
    timestamp) so the checked-in file can be tested against it."""
    rovers = {rid: get_rover(rid) for rid in FRET_ROVERS}
    bound = {rid: {b.requirement.id: b for b in bind_catalogue(rover)} for rid, rover in rovers.items()}
    requirements: list[dict[str, Any]] = []
    for req in REQUIREMENTS:
        thresholds = {rid: _threshold_json(bound[rid][req.id].threshold) for rid in rovers}
        formulas = {
            rid: (None if bound[rid][req.id].formula is None else to_rtamt(bound[rid][req.id].formula))
            for rid in rovers
        }
        requirements.append(
            {
                "reqid": req.id,
                "name": req.name,
                "parent_reqid": None,
                "project": "LunaPath",
                "fulltext": req.fretish,
                "rationale": req.rationale,
                "comments": req.notes,
                "semantics": {
                    "type": "nasa",
                    "scope": req.scope,
                    "condition": req.condition,
                    "component": "rover",
                    "timing": req.timing,
                    "response": req.response,
                    "variables": sorted({req.signal} | ({req.scope} if req.scope else set())),
                    "ftLTL": req.ft_ltl,
                    "stl": req.stl_text,
                    "monitored_stl": formulas["lpr_1"],
                },
                "monitor": {
                    "class": req.cls,
                    "signal": req.signal,
                    "unit": req.unit,
                    "rover_parameter": req.rover_parameter,
                    "threshold_source": bound["lpr_1"][req.id].threshold_source,
                    "thresholds_by_rover": thresholds,
                    "formula_by_rover": formulas,
                    "normalizer": req.normalizer,
                    "trace_kinds": list(req.trace_kinds),
                },
            }
        )
    return {
        "project": "LunaPath",
        "schema": (
            "lunapath-fret-export/1 -- fields modelled on FRET's requirement export "
            "(reqid, fulltext, rationale, semantics) plus a monitor block"
        ),
        "provenance": {
            "method": (
                "written by hand in FRETISH following FRET's grammar "
                "([scope] [condition] component shall [timing] [response]); translated to "
                "STL by hand; not exported from the FRET tool"
            ),
            "checked_by": (
                "backend/app/safety_monitor.py -- RTAMT 0.3.5 discrete-time offline monitor "
                "cross-checked by a built-in evaluator, on planned and telemetry traces"
            ),
            "claim": CLAIM,
            "fret_reference": FRET_REFERENCE,
            "rtamt_reference": RTAMT_REFERENCE,
        },
        "component": COMPONENT,
        "recharge_deadline_h": RECHARGE_DEADLINE_H,
        "rovers": {rid: rovers[rid]["name"] for rid in FRET_ROVERS},
        "generated_by": "scripts/export_fret_requirements.py",
        "requirements": requirements,
    }


# ═══════════════════════════════════════════════════════════════════════
# 6. Online session -- the ROS node's decision logic, ROS-free
# ═══════════════════════════════════════════════════════════════════════


class SafetyMonitorSession:
    """Push telemetry samples one at a time and get the catalogue's verdict
    on the prefix flown so far.

    The prefix is re-evaluated in full on every push (the catalogue's
    formulas are unbounded G/F over derived counters, so this is exact and
    a few milliseconds for thousands of samples). Safety verdicts are
    monotone -- once ``always`` is violated on a prefix it stays violated
    -- and each violation is reported in ``newly_violated`` exactly once,
    which is what a node publishing one trigger per event needs. Liveness
    (goal reached) is ``pending`` until :meth:`finish` closes the trace.
    """

    def __init__(
        self,
        rover: Mapping[str, Any] | None = None,
        engine: str = "auto",
        recharge_deadline_h: float = RECHARGE_DEADLINE_H,
    ) -> None:
        if engine not in ENGINES:
            raise ValueError(f"unknown engine {engine!r}; use one of {ENGINES}")
        self.rover = get_rover() if rover is None else rover
        self.engine = engine
        self.recharge_deadline_h = float(recharge_deadline_h)
        self._samples: list[dict[str, Any]] = []
        self._violated: list[str] = []

    @property
    def n_samples(self) -> int:
        return len(self._samples)

    @property
    def violated(self) -> list[str]:
        return list(self._violated)

    def push(self, sample: Mapping[str, Any]) -> dict[str, Any]:
        """Append one sample and evaluate the prefix. A malformed sample
        (time going backwards, non-finite value) raises ValueError and
        leaves the session unchanged."""
        candidate = self._samples + [dict(sample)]
        trace = trace_from_samples(candidate, self.rover, complete=False)
        block = evaluate_catalogue(
            trace, self.rover, engine=self.engine, recharge_deadline_h=self.recharge_deadline_h
        )
        newly = [rid for rid in block["violated"] if rid not in self._violated]
        self._violated.extend(newly)
        self._samples = candidate
        return {
            "n_samples": len(candidate),
            "safety_margins": block,
            "newly_violated": newly,
            "violated": list(self._violated),
        }

    def finish(self, stranded: bool = False) -> dict[str, Any]:
        """The catalogue on the closed trace (liveness decided)."""
        if not self._samples:
            raise ValueError("no samples were pushed")
        trace = trace_from_samples(self._samples, self.rover, complete=True, stranded=stranded)
        return evaluate_catalogue(
            trace, self.rover, engine=self.engine, recharge_deadline_h=self.recharge_deadline_h
        )
