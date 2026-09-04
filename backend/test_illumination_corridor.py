"""The continuous-illumination corridor (A2): CMU's x-y-t connected-component
pruning, made move-time aware for the 4-D planner.

Synthetic volumes only; the real Site11 grid is exercised in
test_illumination_corridor_real_grid.py under a skip guard.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from app import illumination_corridor as ic
from app.constants import get_rover
from app.cost_engine import edge_travel_time_s

ROVER = get_rover()
RES_M = 80.0


def _flat_slice_hours(res_m: float = RES_M) -> float:
    """A slice exactly as long as one flat cardinal crossing."""
    return edge_travel_time_s(0.0, res_m, ROVER) / 3600.0


# ── lit_volume ───────────────────────────────────────────────────────────────


def test_lit_volume_all_rule_needs_every_fine_cell_lit():
    snap = np.zeros((8, 8))  # 0 = lit, 1 = shadow
    snap[0, 0:4] = 1.0
    snap[1, 0:3] = 1.0  # 7 of 16 dark in the top-left block
    snap[4:8, 4:8] = 1.0  # bottom-right block fully dark
    volume = ic.lit_volume([snap], coarsen=4, lit_rule="all")
    assert volume.shape == (1, 2, 2) and volume.dtype == bool
    assert volume[0].tolist() == [[False, True], [True, False]]


def test_lit_volume_majority_rule_uses_the_planners_half_threshold():
    snap = np.zeros((8, 8))
    snap[0, 0:4] = 1.0
    snap[1, 0:3] = 1.0  # mean 7/16 < 0.5 -> lit under majority
    snap[4:8, 4:8] = 1.0
    volume = ic.lit_volume([snap], coarsen=4, lit_rule="majority")
    assert volume[0].tolist() == [[True, True], [True, False]]


def test_lit_volume_rules_agree_on_fully_lit_and_fully_dark_blocks():
    lit = np.zeros((4, 4))
    dark = np.ones((4, 4))
    for rule in ic.LIT_RULES:
        assert ic.lit_volume([lit, dark], coarsen=4, lit_rule=rule)[:, 0, 0].tolist() == [True, False]


def test_lit_volume_rejects_an_unknown_rule():
    with pytest.raises(ValueError):
        ic.lit_volume([np.zeros((4, 4))], coarsen=4, lit_rule="mostly")


# ── run counters ─────────────────────────────────────────────────────────────


def test_lit_run_counts_consecutive_lit_slices_ending_at_t():
    volume = np.array([1, 1, 0, 1, 1, 1], dtype=bool).reshape(6, 1, 1)
    assert ic.lit_run(volume)[:, 0, 0].tolist() == [1, 2, 0, 1, 2, 3]


def test_forward_run_counts_consecutive_lit_slices_from_t():
    volume = np.array([1, 1, 0, 1, 1, 1], dtype=bool).reshape(6, 1, 1)
    assert ic.forward_run(volume)[:, 0, 0].tolist() == [2, 1, 0, 3, 2, 1]


# ── edge tables ──────────────────────────────────────────────────────────────


def test_edge_tables_open_all_eight_neighbours_of_the_centre_on_flat_ground():
    tables = ic.edge_tables(np.ones((3, 3), dtype=bool), None, None, RES_M, ROVER, _flat_slice_hours())
    assert len(tables.offsets) == 8
    for k, (d_row, d_col) in enumerate(tables.offsets):
        assert tables.ok[k][1, 1], (d_row, d_col)
        diagonal = d_row != 0 and d_col != 0
        # sqrt(2) crossings at one flat crossing per slice: 2 slices.
        assert tables.slices[k][1, 1] == (2 if diagonal else 1), (d_row, d_col)
    assert tables.max_slices == 2


def test_edge_tables_close_offsets_that_leave_the_grid():
    tables = ic.edge_tables(np.ones((3, 3), dtype=bool), None, None, RES_M, ROVER, _flat_slice_hours())
    up = tables.offsets.index((-1, 0))
    assert not tables.ok[up][0, 1]
    assert tables.ok[up][1, 1]


def test_edge_tables_slices_follow_the_planners_ceil_of_travel_over_slice():
    slope = np.full((3, 3), 10.0)
    tables = ic.edge_tables(np.ones((3, 3), dtype=bool), None, slope, RES_M, ROVER, _flat_slice_hours())
    travel_s = edge_travel_time_s(10.0, RES_M, ROVER)
    expected = max(1, int(math.ceil(travel_s / 3600.0 / _flat_slice_hours())))
    right = tables.offsets.index((0, 1))
    assert tables.slices[right][1, 1] == expected


def test_edge_tables_apply_the_step_slope_gate():
    # One row, so there is no cross-slope to speak of: only the step gate.
    elevation = np.array([[0.0, 1000.0, 1000.0]])
    tables = ic.edge_tables(np.ones((1, 3), dtype=bool), elevation, None, RES_M, ROVER, _flat_slice_hours())
    right = tables.offsets.index((0, 1))
    assert not tables.ok[right][0, 0]  # (0,0) -> (0,1) climbs the wall
    assert tables.ok[right][0, 1]  # (0,1) -> (0,2) along the top: fine


def test_edge_tables_honour_passability_and_the_corner_rule():
    passable = np.ones((3, 3), dtype=bool)
    passable[1, 1] = False
    tables = ic.edge_tables(passable, None, None, RES_M, ROVER, _flat_slice_hours())
    right = tables.offsets.index((0, 1))
    assert not tables.ok[right][1, 0]  # into the blocked centre
    diag = tables.offsets.index((1, 1))
    # (0,0) -> (1,1) blocked; (0,1) -> (1,2) squeezes past the blocked
    # centre: the corner rule needs both (0,2) and (1,1) passable.
    assert not tables.ok[diag][0, 0]
    assert not tables.ok[diag][0, 1]


def test_edge_tables_are_symmetric():
    rng = np.random.default_rng(3)
    passable = rng.random((6, 6)) > 0.2
    elevation = rng.random((6, 6)) * 5.0
    slope = rng.random((6, 6)) * 8.0
    tables = ic.edge_tables(passable, elevation, slope, RES_M, ROVER, _flat_slice_hours())
    for k, (d_row, d_col) in enumerate(tables.offsets):
        back = tables.offsets.index((-d_row, -d_col))
        for r in range(6):
            for c in range(6):
                nr, nc = r + d_row, c + d_col
                if 0 <= nr < 6 and 0 <= nc < 6:
                    assert tables.ok[k][r, c] == tables.ok[back][nr, nc]
                    if tables.ok[k][r, c]:
                        assert tables.slices[k][r, c] == tables.slices[back][nr, nc]
                else:
                    assert not tables.ok[k][r, c]


# ── reachability and pruning ─────────────────────────────────────────────────


def _row_tables(n_cells: int, slice_hours: float = 100.0) -> ic.EdgeTables:
    """A 1 x n flat row; a slice long enough that every move takes one."""
    return ic.edge_tables(np.ones((1, n_cells), dtype=bool), None, None, RES_M, ROVER, slice_hours)


def _hand_built_row():
    """Five cells over five slices, one-slice moves.

    cell 0 lit throughout; cell 1 lit from t=2; cell 2 lit until t=2;
    cell 3 lit only at t=4; cell 4 never.
    """
    volume = np.zeros((5, 1, 5), dtype=bool)
    volume[:, 0, 0] = True
    volume[2:, 0, 1] = True
    volume[:3, 0, 2] = True
    volume[4, 0, 3] = True
    return volume, _row_tables(5)


def _voxels(volume: np.ndarray) -> set[tuple[int, int, int]]:
    return {tuple(int(v) for v in idx) for idx in np.argwhere(volume)}


def test_forward_reach_from_the_first_lit_layer_drops_roots():
    volume, tables = _hand_built_row()
    forward = ic.forward_reach(volume, tables)
    expected = {(t, 0, 0) for t in range(5)} | {(0, 0, 2), (1, 0, 2), (2, 0, 2)} | {(3, 0, 1), (4, 0, 1)}
    assert _voxels(forward) == expected


def test_backward_reach_from_the_last_lit_layer_drops_dead_ends():
    volume, tables = _hand_built_row()
    backward = ic.backward_reach(volume, tables)
    expected = {(t, 0, 0) for t in range(5)} | {(2, 0, 1), (3, 0, 1), (4, 0, 1)} | {(4, 0, 3)}
    assert _voxels(backward) == expected


def test_prune_corridor_is_the_intersection_of_the_two_passes():
    volume, tables = _hand_built_row()
    forward, backward, corridor = ic.prune_corridor(volume, tables)
    assert np.array_equal(corridor, forward & backward)
    expected = {(t, 0, 0) for t in range(5)} | {(3, 0, 1), (4, 0, 1)}
    assert _voxels(corridor) == expected
    # The dead end (cell 2) and the unreachable late cell (cell 3) are gone.
    assert not corridor[:, 0, 2].any() and not corridor[:, 0, 3].any()


def test_prune_corridor_honours_explicit_sources_and_sinks():
    volume, tables = _hand_built_row()
    sources = np.zeros((1, 5), dtype=bool)
    sources[0, 2] = True  # start only in the doomed cell
    forward, _backward, corridor = ic.prune_corridor(volume, tables, sources=sources)
    assert _voxels(forward) == {(0, 0, 2), (1, 0, 2), (2, 0, 2)}
    assert not corridor.any()
    sinks = np.zeros((1, 5), dtype=bool)
    sinks[0, 1] = True  # must end in cell 1
    _forward, backward, corridor = ic.prune_corridor(volume, tables, sinks=sinks)
    assert (4, 0, 3) not in _voxels(backward)
    # Cell 0 at the last slice is not a sink any more, so it drops out; the
    # rest of cell 0 stays because it can still move into cell 1 by t=4.
    assert _voxels(corridor) == {(t, 0, 0) for t in range(4)} | {(3, 0, 1), (4, 0, 1)}


def _brute_force(volume, tables, seeds, direction):
    """BFS over the explicit voxel graph; the reference the vectorised
    passes are held to."""
    n_slices, height, width = volume.shape
    seen = np.zeros(volume.shape, dtype=bool)
    frontier = [(t, r, c) for (t, r, c) in seeds if volume[t, r, c]]
    for voxel in frontier:
        seen[voxel] = True

    def lit_span(cell, t0, t1):
        return bool(volume[t0 : t1 + 1, cell[0], cell[1]].all())

    while frontier:
        t, r, c = frontier.pop()
        candidates = []
        if direction == "forward":
            if t + 1 < n_slices and volume[t + 1, r, c]:
                candidates.append((t + 1, r, c))
            for k, (dr, dc) in enumerate(tables.offsets):
                if not tables.ok[k][r, c]:
                    continue
                d = int(tables.slices[k][r, c])
                nr, nc = r + dr, c + dc
                if t + d < n_slices and lit_span((r, c), t, t + d) and lit_span((nr, nc), t, t + d):
                    candidates.append((t + d, nr, nc))
        else:
            if t - 1 >= 0 and volume[t - 1, r, c]:
                candidates.append((t - 1, r, c))
            for k, (dr, dc) in enumerate(tables.offsets):
                pr, pc = r - dr, c - dc
                if not (0 <= pr < height and 0 <= pc < width) or not tables.ok[k][pr, pc]:
                    continue
                d = int(tables.slices[k][pr, pc])
                if t - d >= 0 and lit_span((pr, pc), t - d, t) and lit_span((r, c), t - d, t):
                    candidates.append((t - d, pr, pc))
        for voxel in candidates:
            if not seen[voxel]:
                seen[voxel] = True
                frontier.append(voxel)
    return seen


def _random_tables(rng, shape, max_slices=2) -> ic.EdgeTables:
    height, width = shape
    ok = [np.zeros(shape, dtype=bool) for _ in ic.OFFSETS]
    slices = [np.zeros(shape, dtype=np.int32) for _ in ic.OFFSETS]
    index = {offset: k for k, offset in enumerate(ic.OFFSETS)}
    for k, (dr, dc) in enumerate(ic.OFFSETS):
        back = index[(-dr, -dc)]
        for r in range(height):
            for c in range(width):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < height and 0 <= nc < width) or ok[k][r, c]:
                    continue
                if rng.random() < 0.7:
                    d = int(rng.integers(1, max_slices + 1))
                    ok[k][r, c] = ok[back][nr, nc] = True
                    slices[k][r, c] = slices[back][nr, nc] = d
    return ic.EdgeTables(ic.OFFSETS, tuple(ok), tuple(slices))


@pytest.mark.parametrize("seed", range(20))
def test_passes_match_a_brute_force_search_over_the_voxel_graph(seed):
    from scipy import ndimage

    rng = np.random.default_rng(seed)
    volume = rng.random((8, 4, 4)) < 0.6
    tables = _random_tables(rng, (4, 4))
    forward, backward, corridor = ic.prune_corridor(volume, tables)
    first = [(0, r, c) for r in range(4) for c in range(4)]
    last = [(7, r, c) for r in range(4) for c in range(4)]
    assert np.array_equal(forward, _brute_force(volume, tables, first, "forward"))
    assert np.array_equal(backward, _brute_force(volume, tables, last, "backward"))
    assert np.array_equal(corridor, forward & backward)
    # CMU's 26-neighbourhood flood fill is a superset: every corridor voxel
    # lies in a component that touches both the first and the last slice.
    labels, count = ndimage.label(volume, structure=np.ones((3, 3, 3)))
    spanning = {int(v) for v in np.unique(labels[0]) if v} & {int(v) for v in np.unique(labels[-1]) if v}
    assert set(np.unique(labels[corridor]).tolist()) <= spanning


def _pair_tables(d: int) -> ic.EdgeTables:
    """Two cells in a row, the move between them taking *d* slices."""
    ok = [np.zeros((1, 2), dtype=bool) for _ in ic.OFFSETS]
    slices = [np.zeros((1, 2), dtype=np.int32) for _ in ic.OFFSETS]
    right, left = ic.OFFSETS.index((0, 1)), ic.OFFSETS.index((0, -1))
    ok[right][0, 0] = ok[left][0, 1] = True
    slices[right][0, 0] = slices[left][0, 1] = d
    return ic.EdgeTables(ic.OFFSETS, tuple(ok), tuple(slices))


def test_a_two_slice_move_needs_the_target_lit_for_three_consecutive_slices():
    tables = _pair_tables(2)
    sources = np.array([[True, False]])
    volume = np.zeros((4, 1, 2), dtype=bool)
    volume[:, 0, 0] = True
    volume[1:3, 0, 1] = True  # lit at t=1,2 only: two slices, not three
    assert not ic.forward_reach(volume, tables, sources=sources)[:, 0, 1].any()
    volume[0:3, 0, 1] = True  # lit at t=0,1,2
    forward = ic.forward_reach(volume, tables, sources=sources)
    assert forward[:, 0, 1].tolist() == [False, False, True, False]


def test_a_two_slice_move_needs_the_source_lit_throughout_the_move():
    tables = _pair_tables(2)
    sources = np.array([[True, False]])
    volume = np.ones((4, 1, 2), dtype=bool)
    volume[1, 0, 0] = False  # the source goes dark mid-move
    forward = ic.forward_reach(volume, tables, sources=sources)
    assert not forward[:, 0, 1].any()
    assert forward[:, 0, 0].tolist() == [True, False, False, False]


# ── components (CMU's flood fill) and reachability from a start ─────────────


def test_components_are_empty_on_a_dark_volume():
    stats = ic.components(np.zeros((3, 4, 4), dtype=bool))
    assert stats == {"count": 0, "largest_voxels": 0, "largest_fraction": None, "spanning_count": 0}


def test_components_count_26_connected_blobs_and_the_spanning_ones():
    volume = np.zeros((3, 4, 4), dtype=bool)
    volume[:, 0:2, 0:2] = True  # A: 12 voxels, every slice
    volume[:, 3, 3] = True  # B: 3 voxels, every slice
    volume[1, 3, 0] = True  # C: one voxel, middle slice only
    stats = ic.components(volume)
    assert stats["count"] == 3
    assert stats["largest_voxels"] == 12
    assert stats["largest_fraction"] == pytest.approx(12 / 16)
    assert stats["spanning_count"] == 2


def test_reachable_from_a_start_is_forward_reach_seeded_at_that_cell():
    """Membership is checked against the corridor, but "lit throughout the
    move" against the lit volume the corridor was pruned from: cell 1 at
    t=2 is lit (so the move 0@2 -> 1@3 is allowed) without being a state
    anyone can occupy."""
    volume, tables = _hand_built_row()
    _f, _b, corridor = ic.prune_corridor(volume, tables)
    run = ic.lit_run(volume)
    reach = ic.reachable_from(corridor, tables, (0, 0), run=run)
    sources = np.zeros((1, 5), dtype=bool)
    sources[0, 0] = True
    assert np.array_equal(reach, ic.forward_reach(corridor, tables, sources=sources, run=run))
    assert reach[3, 0, 1] and not reach[2, 0, 1]
    assert not ic.reachable_from(corridor, tables, (0, 4), run=run).any()
    # Checked against the corridor's own run instead, the t=3 entry is
    # refused (cell 1 is not a corridor voxel at t=2); only 0@3 -> 1@4 is.
    own = ic.reachable_from(corridor, tables, (0, 0))
    assert not own[3, 0, 1] and own[4, 0, 1]


# ── build_corridor, dwell and the response block ─────────────────────────────

COARSE_RES_M = 320.0
LONG_SLICE_H = 100.0  # every move takes one slice


def _block_series(n_slices: int = 6) -> list[np.ndarray]:
    """8x8 fine grid, coarsen 4 -> four blocks A=(0,0) B=(0,1) C=(1,0) D=(1,1).

    A lit throughout, B lit from t=2, C lit until t=3, D never.
    """
    series = []
    for t in range(n_slices):
        snap = np.ones((8, 8))
        snap[0:4, 0:4] = 0.0
        if t >= 2:
            snap[0:4, 4:8] = 0.0
        if t <= 3:
            snap[4:8, 0:4] = 0.0
        series.append(snap)
    return series


def _build(lit_rule: str = "all") -> ic.IlluminationCorridor:
    return ic.build_corridor(
        _block_series(),
        np.ones((2, 2), dtype=bool),
        np.zeros((2, 2)),
        np.zeros((2, 2)),
        COARSE_RES_M,
        ROVER,
        coarsen=4,
        slice_hours=LONG_SLICE_H,
        lit_rule=lit_rule,
    )


def test_build_corridor_carries_the_volumes_and_their_relations():
    corridor = _build()
    assert corridor.lit_safe.shape == (6, 2, 2)
    assert corridor.n_slices == 6 and corridor.slice_hours == LONG_SLICE_H
    assert corridor.lit_rule == "all" and corridor.resolution_m == COARSE_RES_M
    assert not (corridor.corridor & ~corridor.lit_safe).any()
    assert np.array_equal(corridor.run, ic.lit_run(corridor.lit_safe))
    assert np.array_equal(corridor.dwell_slices, ic.forward_run(corridor.corridor))
    assert np.array_equal(corridor.corridor, corridor.forward & corridor.backward)
    assert corridor.edges.max_slices == 1
    assert set(corridor.timings_ms) >= {"lit_volume", "edges", "prune", "dwell", "total"}


def test_build_corridor_prunes_the_late_entry_and_the_early_exit():
    corridor = _build()
    a = corridor.corridor[:, 0, 0].tolist()
    b = corridor.corridor[:, 0, 1].tolist()
    c = corridor.corridor[:, 1, 0].tolist()
    d = corridor.corridor[:, 1, 1].tolist()
    assert a == [True] * 6
    assert b == [False, False, False, True, True, True]  # entered from A at t=3
    assert c == [True, True, True, False, False, False]  # must leave for A by t=3
    assert d == [False] * 6


def test_build_corridor_respects_the_traversable_mask():
    traversable = np.ones((2, 2), dtype=bool)
    traversable[0, 0] = False  # block A impassable: nothing connects
    corridor = ic.build_corridor(
        _block_series(), traversable, np.zeros((2, 2)), np.zeros((2, 2)),
        COARSE_RES_M, ROVER, coarsen=4, slice_hours=LONG_SLICE_H,
    )
    assert not corridor.lit_safe[:, 0, 0].any()
    # C alone (lit until t=3) cannot reach the last slice; B alone cannot
    # be entered from the first: only nothing survives.
    assert not corridor.corridor.any()


def test_route_dwell_reports_the_longest_stay_and_whether_the_horizon_cut_it():
    corridor = _build()
    path = [(1, 0, 0), (1, 0, 1), (0, 0, 2), (0, 1, 3)]
    dwell = ic.route_dwell(corridor, path, top=3)
    assert dwell["max_dwell_hours"] == pytest.approx(4 * LONG_SLICE_H)
    assert dwell["dwell_horizon_limited"] is True
    best = dwell["dwell_opportunities"][0]
    assert best["state"] == 2 and best["row"] == 0 and best["col"] == 0 and best["slice"] == 2
    assert best["hours"] == pytest.approx(400.0) and best["horizon_limited"] is True
    hours = [entry["hours"] for entry in dwell["dwell_opportunities"]]
    assert hours == sorted(hours, reverse=True) and len(hours) == 3
    # C at t=0 stays lit for 3 slices and then goes dark before the window
    # ends: a genuine, not horizon-limited, 300 h opportunity.
    c0 = next(e for e in dwell["dwell_opportunities"] if e["state"] == 0)
    assert c0["hours"] == pytest.approx(300.0) and c0["horizon_limited"] is False


def test_route_dwell_on_an_empty_route_is_empty():
    assert ic.route_dwell(_build(), [], top=3) == {
        "max_dwell_hours": None,
        "dwell_horizon_limited": None,
        "dwell_opportunities": [],
    }


def _provenance():
    return {"model": "spice_horizon", "time_varying": True, "start_utc": "2027-05-30T00:00:00"}


def test_corridor_summary_counts_voxels_slices_start_and_goal():
    corridor = _build()
    block = ic.corridor_summary(corridor, start=(1, 0), goal=(0, 1), provenance=_provenance())
    assert block["enforced"] is False and block["lit_rule"] == "all"
    assert block["n_slices"] == 6 and block["slice_hours"] == LONG_SLICE_H
    assert block["grid"] == {"rows": 2, "cols": 2, "resolution_m": COARSE_RES_M}
    assert block["voxels"]["traversable"] == 24
    assert block["voxels"]["lit_safe"] == 14
    assert block["voxels"]["corridor"] == 12
    assert block["voxels"]["corridor_fraction_of_lit_safe"] == pytest.approx(12 / 14)
    assert block["voxels"]["pruned_fraction"] == pytest.approx(2 / 14)
    assert block["slices"] == {
        "first_lit": 0, "last_lit": 5, "lit_safe_cells_t0": 2, "corridor_cells_t0": 2, "corridor_cells_last": 2,
    }
    assert block["components"]["count"] == 1 and block["components"]["spanning_count"] == 1
    assert block["start"] == {"cell": [1, 0], "in_corridor_t0": True, "first_corridor_slice": 0}
    assert block["goal"] == {
        "cell": [0, 1], "corridor_slices": 3, "reachable_in_corridor": True, "first_reachable_slice": 3,
    }
    assert block["route"]["inside"] is None and block["route"]["dwell_opportunities"] == []
    assert block["provenance"]["shadow_model"] == "spice_horizon"
    assert "model" in block["provenance"]["claim"].lower()
    assert "10.8" in block["provenance"]["uncertainty_note"]
    assert block["lit_rule_definition"] == ic.LIT_RULE_DEFINITIONS["all"]
    assert "components_ms" in block["timings_ms"] and "reach_ms" in block["timings_ms"]


def test_corridor_summary_says_when_start_or_goal_are_outside():
    corridor = _build()
    block = ic.corridor_summary(corridor, start=(1, 1), goal=(1, 1), provenance=_provenance())
    assert block["start"] == {"cell": [1, 1], "in_corridor_t0": False, "first_corridor_slice": None}
    assert block["goal"] == {
        "cell": [1, 1], "corridor_slices": 0, "reachable_in_corridor": False, "first_reachable_slice": None,
    }
    late = ic.corridor_summary(corridor, start=(0, 1), goal=(0, 0), provenance=_provenance())
    assert late["start"]["in_corridor_t0"] is False and late["start"]["first_corridor_slice"] == 3
    assert late["goal"]["reachable_in_corridor"] is False


def test_corridor_summary_describes_the_route_and_is_json_safe():
    corridor = _build()
    path = [(1, 0, 0), (1, 0, 1), (0, 0, 2), (0, 1, 3)]
    block = ic.corridor_summary(
        corridor, start=(1, 0), goal=(0, 1), path_states=path, path_dark_hours=[0.0, 0.0, 0.0, 0.0],
        provenance=_provenance(), enforced=True,
    )
    assert block["enforced"] is True
    route = block["route"]
    assert route["inside"] is True and route["states_inside"] == 4 and route["states_total"] == 4
    assert route["moves_outside"] == 0 and route["waits_outside"] == 0
    assert route["path_dark_hours_max"] == 0.0
    assert route["max_dwell_hours"] == pytest.approx(400.0)
    json.dumps(block, allow_nan=False)
    # A route that leaves the corridor is counted, move and wait apart.
    outside = [(1, 0, 0), (1, 1, 1), (1, 1, 2)]
    block = ic.corridor_summary(corridor, start=(1, 0), goal=(1, 1), path_states=outside, provenance=_provenance())
    assert block["route"]["inside"] is False
    assert block["route"]["states_inside"] == 1
    assert block["route"]["moves_outside"] == 1 and block["route"]["waits_outside"] == 1


# ── picking a pair inside the corridor (report and real-grid tests) ─────────


def test_corridor_pair_starts_at_the_nearest_lit_block_and_ends_as_far_as_it_can():
    corridor = _build()
    pair = ic.corridor_pair(corridor, near=(1, 1))
    assert pair is not None
    start, goal, info = pair
    assert start == (1, 0)  # C: distance 1 from (1,1); A is sqrt(2) away
    assert goal == (0, 0)  # A and B tie at Chebyshev 1; row-major first
    assert info["start_distance_cells"] == pytest.approx(1.0)
    assert info["goal_chebyshev_cells"] == 1
    assert info["goal_first_reachable_slice"] == 1


def test_corridor_pair_is_none_when_nothing_is_lit_at_the_first_slice():
    traversable = np.ones((2, 2), dtype=bool)
    traversable[0, 0] = False
    corridor = ic.build_corridor(
        _block_series(), traversable, np.zeros((2, 2)), np.zeros((2, 2)),
        COARSE_RES_M, ROVER, coarsen=4, slice_hours=LONG_SLICE_H,
    )
    assert ic.corridor_pair(corridor, near=(0, 0)) is None


def test_corridor_summary_without_a_start_or_goal_omits_those_sections():
    corridor = _build()
    block = ic.corridor_summary(corridor, start=None, goal=None, provenance=_provenance())
    assert block["start"] is None and block["goal"] is None
    assert block["route"]["inside"] is None
    assert block["voxels"]["corridor"] == 12
    assert block["timings_ms"]["reach_ms"] == 0.0
    json.dumps(block, allow_nan=False)


@pytest.mark.parametrize("seed", range(6))
def test_the_gather_path_for_many_distinct_move_lengths_matches_brute_force(seed):
    rng = np.random.default_rng(100 + seed)
    volume = rng.random((14, 4, 4)) < 0.7
    tables = _random_tables(rng, (4, 4), max_slices=9)  # more than _MAX_DISTINCT_SLICES
    forward, backward, corridor = ic.prune_corridor(volume, tables)
    first = [(0, r, c) for r in range(4) for c in range(4)]
    last = [(13, r, c) for r in range(4) for c in range(4)]
    assert np.array_equal(forward, _brute_force(volume, tables, first, "forward"))
    assert np.array_equal(backward, _brute_force(volume, tables, last, "backward"))


def test_the_slice_and_gather_paths_agree(monkeypatch):
    rng = np.random.default_rng(7)
    volume = rng.random((10, 5, 5)) < 0.6
    tables = _random_tables(rng, (5, 5), max_slices=3)
    sliced = ic.prune_corridor(volume, tables)
    monkeypatch.setattr(ic, "_MAX_DISTINCT_SLICES", 0)
    gathered = ic.prune_corridor(volume, tables)
    for a, b in zip(sliced, gathered):
        assert np.array_equal(a, b)
