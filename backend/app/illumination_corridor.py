"""The continuous-illumination corridor (A2): CMU's x-y-t connected-component
analysis as a pre-filter for the 4-D planner.

Otten, Jones, Wettergreen and Whittaker (ICRA 2015; FSR 2017; Otten's
thesis) plan sun-synchronous polar routes by stacking the illumination
time series over the slope mask into a (t, y, x) volume, flood-filling the
"lit and safely sloped" voxels with a 3x3x3 kernel, and pruning the result
twice -- forward in time to drop roots that the start of the window cannot
reach, backward to drop dead ends that never reach the end of the window.
Whatever survives is a corridor: a rover that stays inside it never enters
shadow, by construction, and A* only has to search that volume.

CMU's graph moves a rover to one of nine neighbours in the NEXT slice
because their cells are 5 m and their slices long. LunaPath's planner works
on 320 m blocks with slices sized to one crossing, so a move takes several
slices (``d = ceil(edge travel / slice)``, exactly as ``astar_4d`` counts
it) and the corridor has to be built on the planner's own edges: the same
gates (``safe_haven._gated_edges``), the same travel time, the same slice
arithmetic. A move (r, c, t) -> (r', c', t + d) is a corridor edge only if
BOTH blocks are lit and passable at every slice from t to t + d -- the
rover is in one of the two the whole time -- and a wait needs both voxels.
The two pruning passes are then plain forward / backward reachability over
that graph, vectorised one slice at a time.

What "lit" means is a request choice (``lit_rule``): ``"all"`` needs every
fine cell of a block lit at the slice (block shadow fraction zero, the
conservative rule the Earth cube and ``coarsen_traversable`` already use);
``"majority"`` needs the block mean under 0.5, the planner's own dark
threshold. Either way a route inside the corridor accrues zero shadow
hours in the planner's accounting.

The claim is about the MODEL: SPICE's Sun, the horizon cube (72 azimuth
bins, two scales), 320 m blocks, sampled slices. NASA's DEM clones (B3)
leave a tenth of the site undecided lit/dark on the epoch this was
measured; ``UNCERTAINTY_NOTE`` travels with every response.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from .cost_cube import coarsen_grid, coarsen_traversable
from .safe_haven import _gated_edges

LIT_RULES: tuple[str, ...] = ("all", "majority")

LIT_RULE_DEFINITIONS: dict[str, str] = {
    "all": (
        "a coarse block is lit only if every fine cell in it is lit at that "
        "slice (block shadow fraction 0)"
    ),
    "majority": (
        "a coarse block is lit if its mean shadow fraction is under 0.5 at "
        "that slice (the planner's own dark threshold)"
    ),
}

# The same eight neighbours, in the same order, as pathfinder_4d._OFFSETS.
OFFSETS: tuple[tuple[int, int], ...] = (
    (-1, 0), (1, 0), (0, -1), (0, 1),
    (-1, -1), (-1, 1), (1, -1), (1, 1),
)

# A fine cell is lit when its shadow value is under this; the SPICE series is
# binary so only the static (long-run fraction) fallback ever sees the
# threshold. Same number as pathfinder_4d._DARK_RATIO_THRESHOLD.
_FINE_LIT_THRESHOLD: float = 0.5


# ── The volume ───────────────────────────────────────────────────────────────


def lit_volume(
    shadow_series: Sequence[np.ndarray] | np.ndarray,
    coarsen: int,
    lit_rule: str = "all",
) -> np.ndarray:
    """``(T, h, w)`` bool: which coarse block is lit at which slice.

    *shadow_series* is the fine-grid series ``build_shadow_series`` returns
    (0 lit, 1 shadow; fractions only in the static fallback).
    """
    if lit_rule not in LIT_RULES:
        raise ValueError(f"unknown lit_rule {lit_rule!r}; expected one of {LIT_RULES}")
    factor = int(coarsen)
    slices: list[np.ndarray] = []
    for snapshot in shadow_series:
        fine = np.asarray(snapshot, dtype=np.float64)
        if lit_rule == "all":
            slices.append(coarsen_traversable(fine < _FINE_LIT_THRESHOLD, factor))
        else:
            with np.errstate(invalid="ignore"):
                slices.append(coarsen_grid(fine, factor) < _FINE_LIT_THRESHOLD)
    if not slices:
        raise ValueError("shadow_series must contain at least one snapshot")
    return np.stack(slices, axis=0).astype(bool)


def lit_run(volume: np.ndarray) -> np.ndarray:
    """``(T, h, w)`` int32: consecutive True slices ENDING at t (0 where False)."""
    vol = np.asarray(volume, dtype=bool)
    run = np.zeros(vol.shape, dtype=np.int32)
    previous = np.zeros(vol.shape[1:], dtype=np.int32)
    for t in range(vol.shape[0]):
        previous = np.where(vol[t], previous + 1, 0).astype(np.int32)
        run[t] = previous
    return run


def forward_run(volume: np.ndarray) -> np.ndarray:
    """``(T, h, w)`` int32: consecutive True slices STARTING at t (0 where False)."""
    vol = np.asarray(volume, dtype=bool)
    run = np.zeros(vol.shape, dtype=np.int32)
    following = np.zeros(vol.shape[1:], dtype=np.int32)
    for t in range(vol.shape[0] - 1, -1, -1):
        following = np.where(vol[t], following + 1, 0).astype(np.int32)
        run[t] = following
    return run


# ── The planner's edges, as per-offset tables ────────────────────────────────


@dataclass(frozen=True)
class EdgeTables:
    """The 4-D planner's MOVE edges, one ``(h, w)`` table per offset.

    ``ok[k][r, c]`` says whether the move from (r, c) in direction
    ``offsets[k]`` passes every hard gate ``astar_4d`` applies (both cells
    passable, no corner cut, step slope, cross-slope, finite travel);
    ``slices[k][r, c]`` is the number of slices that move takes in the
    planner's arithmetic (``max(1, ceil(travel_s / 3600 / slice_hours))``),
    0 where the move is not allowed. Symmetric by construction.
    """

    offsets: tuple[tuple[int, int], ...]
    ok: tuple[np.ndarray, ...]
    slices: tuple[np.ndarray, ...]

    @property
    def max_slices(self) -> int:
        return int(max((int(table.max()) for table in self.slices), default=0))

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(int(v) for v in self.ok[0].shape)  # type: ignore[return-value]


def edge_tables(
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Any,
    slice_hours: float,
) -> EdgeTables:
    """Build :class:`EdgeTables` from ``safe_haven._gated_edges``.

    The gates are the planner's and so are the hours: since C3 the gated
    graph prices every edge with ``cost_engine.edge_travel_time_s_array``,
    the planner's scalar function in the same operation order (slip
    included), so ``hours / slice_hours`` here is the planner's
    ``travel_s / 3600 / slice_hours`` to the bit and a move whose travel is
    exactly one slice long -- every edge at the median slope when the slice
    is auto-sized -- rounds the same way in both places. (Before C3 this
    function recomputed the time in the planner's order because the graph
    used ``d / (v_max cos^2)``.)
    """
    mask = np.asarray(traversable, dtype=bool)
    height, width = mask.shape
    src, dst, hours = _gated_edges(mask, elevation, slope, float(resolution_m), rover)

    ok = [np.zeros(mask.shape, dtype=bool) for _ in OFFSETS]
    slices = [np.zeros(mask.shape, dtype=np.int32) for _ in OFFSETS]
    if src.size == 0:
        return EdgeTables(OFFSETS, tuple(ok), tuple(slices))

    d_row = dst // width - src // width
    d_col = dst % width - src % width
    ratio = hours / float(slice_hours)
    d_slices = np.maximum(1, np.ceil(ratio)).astype(np.int32)

    index = {offset: k for k, offset in enumerate(OFFSETS)}
    for k, (dr, dc) in enumerate(OFFSETS):
        selected = (d_row == dr) & (d_col == dc)
        if not selected.any():
            continue
        back = index[(-dr, -dc)]
        ok[k].ravel()[src[selected]] = True
        slices[k].ravel()[src[selected]] = d_slices[selected]
        ok[back].ravel()[dst[selected]] = True
        slices[back].ravel()[dst[selected]] = d_slices[selected]
    return EdgeTables(OFFSETS, tuple(ok), tuple(slices))


# ── The two pruning passes ───────────────────────────────────────────────────


def _offset_windows(height: int, width: int, offsets: Sequence[tuple[int, int]]):
    """Per offset: the source window, the target window (shifted by the
    offset) and index grids for the source window, or None when the offset
    has no room on the grid."""
    windows = []
    for d_row, d_col in offsets:
        r0, r1 = max(0, -d_row), height - max(0, d_row)
        c0, c1 = max(0, -d_col), width - max(0, d_col)
        if r1 <= r0 or c1 <= c0:
            windows.append(None)
            continue
        src = (slice(r0, r1), slice(c0, c1))
        dst = (slice(r0 + d_row, r1 + d_row), slice(c0 + d_col, c1 + d_col))
        rows, cols = np.meshgrid(np.arange(r0, r1), np.arange(c0, c1), indexing="ij")
        windows.append((src, dst, rows, cols, rows + d_row, cols + d_col))
    return windows


# Per offset, the distinct move lengths are few (one or two slices at the
# auto-sized slice), so the passes gather ``reach[t - d]`` with a plain
# slice per distinct d rather than a fancy index over the time axis. Past
# this many distinct values (a caller-pinned tiny slice) the gather wins.
_MAX_DISTINCT_SLICES: int = 6


def _offset_plan(tables: EdgeTables, windows):
    """Per offset: the window, and either the list of ``(d, mask)`` pairs
    for the slice path or None for the gather path."""
    plan = []
    for k, window in enumerate(windows):
        if window is None:
            plan.append(None)
            continue
        src = window[0]
        ok = tables.ok[k][src]
        d_table = tables.slices[k][src]
        uniques = np.unique(d_table[ok])
        if uniques.size == 0:
            plan.append(None)
            continue
        if uniques.size <= _MAX_DISTINCT_SLICES:
            pairs = [(int(d), ok & (d_table == d)) for d in uniques]
            plan.append((window, ok, d_table, pairs))
        else:
            plan.append((window, ok, d_table, None))
    return plan


def _forward_pass(
    volume: np.ndarray, run: np.ndarray, tables: EdgeTables, sources: np.ndarray | None
) -> np.ndarray:
    n_slices, height, width = volume.shape
    reach = np.zeros(volume.shape, dtype=bool)
    reach[0] = volume[0] if sources is None else (volume[0] & np.asarray(sources, dtype=bool))
    plan = _offset_plan(tables, _offset_windows(height, width, tables.offsets))
    for t in range(1, n_slices):
        # WAIT: the voxel below was reached (so lit) and this one is lit.
        current = reach[t - 1] & volume[t]
        run_t = run[t]
        for item in plan:
            if item is None:
                continue
            (src, dst, rows_src, cols_src, _rows_dst, _cols_dst), ok, d_table, pairs = item
            run_src = run_t[src]
            run_dst = run_t[dst]
            if pairs is not None:
                for d, mask in pairs:
                    if d > t:
                        continue
                    # Both blocks lit and passable from departure to arrival.
                    moved = reach[t - d][src] & mask & (run_src >= d + 1) & (run_dst >= d + 1)
                    current[dst] |= moved
            else:
                allowed = ok & (d_table <= t)
                if not allowed.any():
                    continue
                departure = np.where(allowed, t - d_table, 0)
                moved = reach[departure, rows_src, cols_src] & allowed
                moved &= run_src >= d_table + 1
                moved &= run_dst >= d_table + 1
                current[dst] |= moved
        reach[t] = current
    return reach


def _backward_pass(
    volume: np.ndarray, run: np.ndarray, tables: EdgeTables, sinks: np.ndarray | None
) -> np.ndarray:
    n_slices, height, width = volume.shape
    last = n_slices - 1
    coreach = np.zeros(volume.shape, dtype=bool)
    coreach[last] = volume[last] if sinks is None else (volume[last] & np.asarray(sinks, dtype=bool))
    plan = _offset_plan(tables, _offset_windows(height, width, tables.offsets))
    for t in range(last - 1, -1, -1):
        current = coreach[t + 1] & volume[t]
        for item in plan:
            if item is None:
                continue
            (src, dst, rows_src, cols_src, rows_dst, cols_dst), ok, d_table, pairs = item
            if pairs is not None:
                for d, mask in pairs:
                    if t + d > last:
                        continue
                    run_a = run[t + d]
                    moved = coreach[t + d][dst] & mask & (run_a[src] >= d + 1) & (run_a[dst] >= d + 1)
                    current[src] |= moved
            else:
                allowed = ok & (t + d_table <= last)
                if not allowed.any():
                    continue
                arrival = np.where(allowed, t + d_table, last)
                moved = coreach[arrival, rows_dst, cols_dst] & allowed
                moved &= run[arrival, rows_src, cols_src] >= d_table + 1
                moved &= run[arrival, rows_dst, cols_dst] >= d_table + 1
                current[src] |= moved
        coreach[t] = current
    return coreach


def forward_reach(
    volume: np.ndarray,
    tables: EdgeTables,
    sources: np.ndarray | None = None,
    run: np.ndarray | None = None,
) -> np.ndarray:
    """``(T, h, w)`` bool: voxels reachable from *sources* (an ``(h, w)`` mask
    applied at slice 0; default every lit voxel of slice 0) through corridor
    edges -- CMU's forward pass, which prunes the roots.

    *volume* is the set of voxels a state may occupy; *run* the lit-run cube
    the "both blocks lit throughout the move" condition is checked against
    (default: the run of *volume* itself). They differ when *volume* is an
    already-pruned corridor: a block the rover crosses mid-move must be lit
    then, but need not be a state anyone could occupy.
    """
    vol = np.asarray(volume, dtype=bool)
    return _forward_pass(vol, lit_run(vol) if run is None else np.asarray(run), tables, sources)


def backward_reach(
    volume: np.ndarray,
    tables: EdgeTables,
    sinks: np.ndarray | None = None,
    run: np.ndarray | None = None,
) -> np.ndarray:
    """``(T, h, w)`` bool: voxels from which *sinks* (an ``(h, w)`` mask at
    the last slice; default every lit voxel there) can still be reached --
    CMU's backward pass, which prunes the dead ends. *run* as in
    :func:`forward_reach`."""
    vol = np.asarray(volume, dtype=bool)
    return _backward_pass(vol, lit_run(vol) if run is None else np.asarray(run), tables, sinks)


def prune_corridor(
    volume: np.ndarray,
    tables: EdgeTables,
    sources: np.ndarray | None = None,
    sinks: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """``(forward, backward, corridor)`` -- the two passes and their
    intersection. With the defaults this is CMU's corridor: every voxel
    that lies on some lit path from the first slice to the last. A3 gets
    its goal sub-volume by passing the start as *sources* and the goal
    cell as *sinks*."""
    vol = np.asarray(volume, dtype=bool)
    run = lit_run(vol)
    forward = _forward_pass(vol, run, tables, sources)
    backward = _backward_pass(vol, run, tables, sinks)
    return forward, backward, forward & backward


def reachable_from(
    volume: np.ndarray,
    tables: EdgeTables,
    start: tuple[int, int],
    run: np.ndarray | None = None,
) -> np.ndarray:
    """Forward reach seeded at one cell of slice 0 (*run* as in
    :func:`forward_reach`: pass the lit volume's run when *volume* is a
    pruned corridor)."""
    vol = np.asarray(volume, dtype=bool)
    sources = np.zeros(vol.shape[1:], dtype=bool)
    if 0 <= start[0] < vol.shape[1] and 0 <= start[1] < vol.shape[2]:
        sources[start[0], start[1]] = True
    return forward_reach(vol, tables, sources=sources, run=run)


# ── CMU's flood fill, for comparison ─────────────────────────────────────────


def components(volume: np.ndarray) -> dict[str, Any]:
    """26-neighbourhood connected components of a volume
    (``scipy.ndimage.label`` with a 3x3x3 kernel: the flood fill of the
    ICRA 2015 paper). ``spanning_count`` is how many components touch both
    the first and the last slice -- the ones CMU's pruning could keep."""
    from scipy import ndimage

    vol = np.asarray(volume, dtype=bool)
    labels, count = ndimage.label(vol, structure=np.ones((3, 3, 3)))
    if count == 0:
        return {"count": 0, "largest_voxels": 0, "largest_fraction": None, "spanning_count": 0}
    sizes = np.bincount(labels.ravel())[1:]
    largest = int(sizes.max())
    total = int(vol.sum())
    first = set(np.unique(labels[0]).tolist()) - {0}
    last = set(np.unique(labels[-1]).tolist()) - {0}
    return {
        "count": int(count),
        "largest_voxels": largest,
        "largest_fraction": largest / total if total else None,
        "spanning_count": len(first & last),
    }


# ── The corridor object, dwell, and the response block ──────────────────────

CLAIM: str = (
    "Inside the corridor the model's shadow series never shows a dark block: "
    "SPICE Sun position + horizon cube (72 azimuth bins, two scales), coarse "
    "blocks, sampled slices. A statement about the model, not about the real "
    "surface."
)
UNCERTAINTY_NOTE: str = (
    "B3: on 2027-05-30, 10.8 percent of cells are undecided lit/dark across "
    "NASA's 100 Site11 DEM clones (docs/research/dem_uncertainty_report.md); "
    "the corridor is only as certain as the DEM it was cast on."
)
REFERENCE: str = (
    "Otten, Jones, Wettergreen, Whittaker: Planning Routes of Continuous "
    "Illumination and Traversable Slope using Connected Component Analysis "
    "(ICRA 2015); Strategic Autonomy for Reducing Risk of Sun-Synchronous "
    "Lunar Polar Exploration (FSR 2017)"
)
EDGE_RULE: str = (
    "MOVE (r,c,t)->(r',c',t+d) with d = max(1, ceil(edge travel / slice)) as "
    "the planner counts it; both blocks lit and passable at every slice "
    "t..t+d; gates as astar_4d (passable, corner cut, step slope, "
    "cross-slope). WAIT (t->t+1) needs both voxels lit."
)
PRUNING: str = (
    "forward reach from the lit layer at slice 0 AND backward reach from the "
    "lit layer at the last slice: CMU's two-pass root / dead-end pruning, "
    "move-time aware"
)


@dataclass
class IlluminationCorridor:
    """Everything the planner and the response need, on the coarse grid.

    ``lit_safe``, ``forward``, ``backward``, ``corridor`` are ``(T, h, w)``
    bool; ``run`` is ``lit_run(lit_safe)`` (the cube the planner checks a
    move's "lit throughout" against); ``dwell_slices`` is
    ``forward_run(corridor)``.
    """

    lit_safe: np.ndarray
    run: np.ndarray
    forward: np.ndarray
    backward: np.ndarray
    corridor: np.ndarray
    dwell_slices: np.ndarray
    edges: EdgeTables
    traversable: np.ndarray
    lit_rule: str
    slice_hours: float
    n_slices: int
    resolution_m: float
    timings_ms: dict[str, float]

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.lit_safe.shape[1]), int(self.lit_safe.shape[2])


def build_corridor(
    shadow_series: Sequence[np.ndarray] | np.ndarray,
    traversable: np.ndarray,
    elevation: np.ndarray | None,
    slope: np.ndarray | None,
    resolution_m: float,
    rover: Any,
    coarsen: int,
    slice_hours: float,
    lit_rule: str = "all",
) -> IlluminationCorridor:
    """The corridor for a fine shadow series on the planner's coarse grid.

    *traversable*, *elevation* and *slope* are the COARSE grids
    (``main._coarse_geometry``); *resolution_m* the coarse cell size.
    """
    import time

    t0 = time.perf_counter()
    mask = np.asarray(traversable, dtype=bool)
    lit = lit_volume(shadow_series, coarsen, lit_rule)
    if lit.shape[1:] != mask.shape:
        raise ValueError(
            f"lit volume {lit.shape[1:]} does not match the coarse grid {mask.shape}"
        )
    lit_safe = lit & mask[None, :, :]
    t1 = time.perf_counter()
    tables = edge_tables(mask, elevation, slope, resolution_m, rover, slice_hours)
    t2 = time.perf_counter()
    run = lit_run(lit_safe)
    forward = _forward_pass(lit_safe, run, tables, None)
    backward = _backward_pass(lit_safe, run, tables, None)
    corridor = forward & backward
    t3 = time.perf_counter()
    dwell = forward_run(corridor)
    t4 = time.perf_counter()
    return IlluminationCorridor(
        lit_safe=lit_safe,
        run=run,
        forward=forward,
        backward=backward,
        corridor=corridor,
        dwell_slices=dwell,
        edges=tables,
        traversable=mask,
        lit_rule=lit_rule,
        slice_hours=float(slice_hours),
        n_slices=int(lit_safe.shape[0]),
        resolution_m=float(resolution_m),
        timings_ms={
            "lit_volume": round((t1 - t0) * 1000.0, 3),
            "edges": round((t2 - t1) * 1000.0, 3),
            "prune": round((t3 - t2) * 1000.0, 3),
            "dwell": round((t4 - t3) * 1000.0, 3),
            "total": round((t4 - t0) * 1000.0, 3),
        },
    )


def route_dwell(
    corridor: IlluminationCorridor,
    path_states: Sequence[Sequence[int]],
    top: int = 3,
) -> dict[str, Any]:
    """CMU's dwell metric along a route: at each state, how long the block
    stays inside the corridor from that slice on. ``horizon_limited`` marks
    a stay that runs into the end of the window -- the number is then a
    lower bound set by the horizon, not by the Sun."""
    if not path_states:
        return {"max_dwell_hours": None, "dwell_horizon_limited": None, "dwell_opportunities": []}
    entries: list[dict[str, Any]] = []
    for index, state in enumerate(path_states):
        r, c, t = (int(v) for v in state)
        slices = int(corridor.dwell_slices[t, r, c])
        entries.append(
            {
                "state": index,
                "row": r,
                "col": c,
                "slice": t,
                "hours": round(slices * corridor.slice_hours, 4),
                "horizon_limited": bool(slices > 0 and t + slices >= corridor.n_slices),
            }
        )
    best = max(entries, key=lambda e: (e["hours"], -e["state"]))
    ranked = sorted(
        (e for e in entries if e["hours"] > 0.0), key=lambda e: (-e["hours"], e["state"])
    )
    return {
        "max_dwell_hours": best["hours"],
        "dwell_horizon_limited": best["horizon_limited"],
        "dwell_opportunities": ranked[: max(0, int(top))],
    }


def _first_true(values: np.ndarray) -> int | None:
    hits = np.flatnonzero(np.asarray(values, dtype=bool))
    return int(hits[0]) if hits.size else None


def corridor_summary(
    corridor: IlluminationCorridor,
    start: tuple[int, int] | None,
    goal: tuple[int, int] | None,
    path_states: Sequence[Sequence[int]] | None = None,
    path_dark_hours: Sequence[float] | None = None,
    provenance: dict[str, Any] | None = None,
    enforced: bool = False,
    top_dwell: int = 3,
) -> dict[str, Any]:
    """The ``illumination_corridor`` block of a /api/plan-4d response (and,
    with *start* and *goal* ``None``, of ``GET /api/illumination-corridor``,
    where there is no pair to place)."""
    import time

    volume = corridor.corridor
    lit_safe = corridor.lit_safe
    n_slices, rows, cols = volume.shape
    n_traversable = int(corridor.traversable.sum())
    n_lit_safe = int(lit_safe.sum())
    n_corridor = int(volume.sum())
    fraction = (n_corridor / n_lit_safe) if n_lit_safe else None

    per_slice = lit_safe.reshape(n_slices, -1).sum(axis=1)
    lit_slices = np.flatnonzero(per_slice > 0)

    t0 = time.perf_counter()
    stats = components(lit_safe)
    t1 = time.perf_counter()

    def in_grid(cell: tuple[int, int]) -> bool:
        return 0 <= int(cell[0]) < rows and 0 <= int(cell[1]) < cols

    start_block: dict[str, Any] | None = None
    goal_block: dict[str, Any] | None = None
    start_column = np.zeros(n_slices, dtype=bool)
    reach_ms = 0.0
    if start is not None:
        start = (int(start[0]), int(start[1]))
        if in_grid(start):
            start_column = volume[:, start[0], start[1]]
        start_block = {
            "cell": [start[0], start[1]],
            "in_corridor_t0": bool(start_column[0]),
            "first_corridor_slice": _first_true(start_column),
        }
    if goal is not None:
        goal = (int(goal[0]), int(goal[1]))
        goal_column = volume[:, goal[0], goal[1]] if in_grid(goal) else np.zeros(n_slices, dtype=bool)
        goal_reach = np.zeros(n_slices, dtype=bool)
        if start is not None and in_grid(start) and in_grid(goal) and bool(start_column[0]):
            t2 = time.perf_counter()
            reach = reachable_from(volume, corridor.edges, start, run=corridor.run)
            goal_reach = reach[:, goal[0], goal[1]]
            reach_ms = (time.perf_counter() - t2) * 1000.0
        goal_block = {
            "cell": [goal[0], goal[1]],
            "corridor_slices": int(goal_column.sum()),
            "reachable_in_corridor": bool(goal_reach.any()),
            "first_reachable_slice": _first_true(goal_reach),
        }

    if path_states:
        inside_flags = [bool(volume[int(t), int(r), int(c)]) for r, c, t in path_states]
        moves_outside = waits_outside = 0
        for previous, current, inside in zip(path_states[:-1], path_states[1:], inside_flags[1:]):
            if inside:
                continue
            if tuple(previous[:2]) == tuple(current[:2]):
                waits_outside += 1
            else:
                moves_outside += 1
        route: dict[str, Any] = {
            "inside": all(inside_flags),
            "states_inside": int(sum(inside_flags)),
            "states_total": len(path_states),
            "moves_outside": moves_outside,
            "waits_outside": waits_outside,
            "path_dark_hours_max": (
                round(float(max(path_dark_hours)), 4) if path_dark_hours else None
            ),
        }
        route.update(route_dwell(corridor, path_states, top=top_dwell))
    else:
        route = {
            "inside": None,
            "states_inside": None,
            "states_total": None,
            "moves_outside": None,
            "waits_outside": None,
            "path_dark_hours_max": None,
            "max_dwell_hours": None,
            "dwell_horizon_limited": None,
            "dwell_opportunities": [],
        }

    prov = dict(provenance or {})
    return {
        "enforced": bool(enforced),
        "lit_rule": corridor.lit_rule,
        "lit_rule_definition": LIT_RULE_DEFINITIONS[corridor.lit_rule],
        "edge_rule": EDGE_RULE,
        "pruning": PRUNING,
        "n_slices": int(n_slices),
        "slice_hours": float(corridor.slice_hours),
        "grid": {"rows": int(rows), "cols": int(cols), "resolution_m": float(corridor.resolution_m)},
        "voxels": {
            "traversable": int(n_slices * n_traversable),
            "lit_safe": n_lit_safe,
            "corridor": n_corridor,
            "corridor_fraction_of_lit_safe": fraction,
            "pruned_fraction": (1.0 - fraction) if fraction is not None else None,
        },
        "slices": {
            "first_lit": int(lit_slices[0]) if lit_slices.size else None,
            "last_lit": int(lit_slices[-1]) if lit_slices.size else None,
            "lit_safe_cells_t0": int(per_slice[0]),
            "corridor_cells_t0": int(volume[0].sum()),
            "corridor_cells_last": int(volume[-1].sum()),
        },
        "components": {
            "method": "scipy.ndimage.label, 26-neighbourhood (CMU's flood fill)",
            **stats,
        },
        "start": start_block,
        "goal": goal_block,
        "route": route,
        "provenance": {
            "shadow_model": prov.get("model"),
            "time_varying": bool(prov.get("time_varying", False)),
            **({"reason": prov["reason"]} if prov.get("reason") else {}),
            **({"start_utc": prov["start_utc"]} if prov.get("start_utc") else {}),
            "claim": CLAIM,
            "uncertainty_note": UNCERTAINTY_NOTE,
            "reference": REFERENCE,
        },
        "timings_ms": {
            **corridor.timings_ms,
            "components_ms": round((t1 - t0) * 1000.0, 3),
            "reach_ms": round(reach_ms, 3),
        },
    }


# ── A pair inside the corridor (for the report and the real-grid tests) ─────


def corridor_pair(
    corridor: IlluminationCorridor, near: tuple[int, int]
) -> tuple[tuple[int, int], tuple[int, int], dict[str, Any]] | None:
    """A (start, goal) pair the corridor rule can accept: the corridor block
    at slice 0 nearest *near* (Euclidean, in cells), and the block reachable
    from it inside the corridor at the largest Chebyshev distance
    (row-major first on ties). ``None`` when no block is in the corridor at
    the first slice. The report and the real-grid tests use it because the
    standard routes start in the dark and would only ever be refused."""
    first = corridor.corridor[0]
    candidates = np.argwhere(first)
    if candidates.size == 0:
        return None
    offsets = candidates - np.asarray(near, dtype=np.int64)[None, :]
    distances = np.hypot(offsets[:, 0], offsets[:, 1])
    start = tuple(int(v) for v in candidates[int(np.argmin(distances))])

    reach = reachable_from(corridor.corridor, corridor.edges, start, run=corridor.run)
    reached = reach.any(axis=0)
    cells = np.argwhere(reached)
    chebyshev = np.max(np.abs(cells - np.asarray(start)[None, :]), axis=1)
    goal = tuple(int(v) for v in cells[int(np.argmax(chebyshev))])
    return start, goal, {
        "start_distance_cells": float(distances.min()),
        "goal_chebyshev_cells": int(chebyshev.max()),
        "goal_first_reachable_slice": _first_true(reach[:, goal[0], goal[1]]),
        "reachable_cells": int(reached.sum()),
    }
