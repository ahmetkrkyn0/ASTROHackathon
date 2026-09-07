"""D2: the MoonPlanBench adapter and the PathBench metric definitions, on maps
small enough to check by hand. Everything here runs without the dataset; the
one test that needs the benchmark's own repository (a local clone named by
LUNAPATH_PPB_DIR) is skip-guarded.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from app.benchmark import (
    BENCHMARK_THERMAL_C,
    LDEM_NATIVE_M_PER_PX,
    MODES,
    MOONPLANBENCH_DIR,
    PAPER_TABLE_1,
    REFERENCE_PLANNERS,
    TIMEOUT_S,
    VARIANTS,
    aggregate,
    auto_select_start_goal,
    bresenham_line,
    cell_size_m,
    distance_to_goal,
    load_inventory,
    load_meta,
    load_occupancy,
    obstacle_clearance,
    occupancy_to_grids,
    path_length_cells,
    path_steps,
    rasterize_path,
    run_benchmark,
    run_mode,
    run_reference_planner,
    shortest_traversable_path,
    trajectory_smoothness,
)
from app.cost_engine import compute_cost_grid

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
_PPB_DIR = os.environ.get("LUNAPATH_PPB_DIR")
_HAS_CLONE = bool(_PPB_DIR) and os.path.isdir(os.path.join(_PPB_DIR, "adapters"))
_HAS_DATA = os.path.isdir(os.path.join(MOONPLANBENCH_DIR, "MoonPlanBench-10"))

# True = occupied. The centre is free, the four diagonal cells are free, the
# four cardinal neighbours are walls: (0,0) -> (2,2) only through corner cuts.
DIAG_GAP = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=bool)


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Task 1: constants, cell size, loading, start/goal ─────────────────────


def test_constants_describe_the_dataset():
    assert VARIANTS == ("MoonPlanBench-10", "MoonPlanBench-15", "MoonPlanBench-20")
    assert len(LDEM_NATIVE_M_PER_PX) == 12
    assert MODES == ("dijkstra_cut", "dijkstra_nocut", "lunapath_single", "lunapath_multi")
    assert REFERENCE_PLANNERS == ("Dijkstra", "AStar", "ThetaStar")
    assert TIMEOUT_S == 60
    # Table 1 of arXiv 2512.21438v1, quoted: six planners x three variants.
    assert PAPER_TABLE_1["MoonPlanBench-10"]["Dijkstra"] == {"success_rate_pct": 100, "length_cells": 651.81, "time_s": 23.31, "dist_left": 0}
    assert PAPER_TABLE_1["MoonPlanBench-20"]["RRT Connect"]["success_rate_pct"] == 25
    for variant in VARIANTS:
        assert len(PAPER_TABLE_1[variant]) == 6


def test_cell_size_is_native_resolution_times_64():
    assert cell_size_m("LDEM_875S_5M") == 320.0
    assert cell_size_m("LDEM_60N_120M.npy") == 7680.0
    assert cell_size_m("LDEM_45N_100M") == 6400.0
    with pytest.raises(ValueError):
        cell_size_m("LDEM_99X_1M")


def test_load_occupancy_nonzero_is_occupied(tmp_path):
    np.save(tmp_path / "m.npy", np.array([[0, 1], [2, 0]], dtype=np.uint8))
    occ = load_occupancy(tmp_path / "m.npy")
    assert occ.dtype == bool
    assert occ.tolist() == [[False, True], [True, False]]


def test_load_occupancy_refuses_non_2d(tmp_path):
    np.save(tmp_path / "m.npy", np.zeros((2, 2, 2), dtype=np.uint8))
    with pytest.raises(ValueError):
        load_occupancy(tmp_path / "m.npy")


def test_start_goal_largest_component_lexicographic_start_farthest_goal():
    occ = np.array(
        [
            [0, 0, 1, 0, 0],
            [0, 0, 1, 0, 0],
            [1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0],
            [0, 0, 0, 0, 0],
        ],
        dtype=bool,
    )
    # The 2x2 block top-left is its own component (4 cells); the rest is one
    # component of 16 cells. Start = smallest (row, col) in it = (0, 3);
    # goal = farthest from (0, 3) = (4, 0).
    (sr, sc), (gr, gc) = auto_select_start_goal(occ)
    assert (sr, sc) == (0, 3)
    assert (gr, gc) == (4, 0)


def test_start_goal_tie_is_first_in_bfs_order():
    occ = np.zeros((3, 3), dtype=bool)
    assert auto_select_start_goal(occ) == ((0, 0), (2, 2))


def test_start_goal_refuses_a_map_without_free_cells():
    with pytest.raises(ValueError):
        auto_select_start_goal(np.ones((2, 2), dtype=bool))


# ── Task 2: pure-distance Dijkstra with and without corner cutting ─────────


def test_corner_cutting_refused_by_default():
    path, dist = shortest_traversable_path(~DIAG_GAP, (0, 0), (2, 2), 1.0)
    assert path == []
    assert dist == math.inf


def test_corner_cutting_allowed_is_the_benchmark_motion_model():
    path, dist = shortest_traversable_path(~DIAG_GAP, (0, 0), (2, 2), 1.0, allow_corner_cutting=True)
    assert path == [(0, 0), (1, 1), (2, 2)]
    assert dist == pytest.approx(2 * math.sqrt(2))


def test_resolution_scales_distance_only():
    trav = np.ones((3, 3), dtype=bool)
    p1, d1 = shortest_traversable_path(trav, (0, 0), (0, 2), 1.0)
    p5, d5 = shortest_traversable_path(trav, (0, 0), (0, 2), 5.0)
    assert d1 == 2.0 and d5 == 10.0
    assert p1 == p5 == [(0, 0), (0, 1), (0, 2)]


def test_nav2_baseline_imports_the_shared_dijkstra():
    source = (_SCRIPTS / "nav2_baseline.py").read_text(encoding="utf-8")
    assert "from app.benchmark import shortest_traversable_path" in source
    assert "def shortest_traversable_path" not in source


# ── Task 3: PathBench metric definitions ──────────────────────────────────


def test_length_and_steps():
    p = [(0, 0), (0, 1), (1, 2)]
    assert path_length_cells(p) == pytest.approx(1 + math.sqrt(2))
    assert path_steps(p) == 2
    assert path_length_cells([]) == 0.0
    assert path_steps([]) == 0


def test_smoothness_straight_zero_and_one_right_angle():
    assert trajectory_smoothness([(0, 0), (0, 1), (0, 2)]) == 0.0
    # PathBench: u = (p_{i-1} - p_i)/|.| in (x, y) order, theta = arccos(u_x),
    # sum |theta_i - theta_{i-1}| divided by the number of trace points.
    p = [(0, 0), (0, 1), (1, 1)]  # +x then +y: theta pi -> pi/2
    assert trajectory_smoothness(p) == pytest.approx((math.pi / 2) / 3)
    assert trajectory_smoothness([(0, 0)]) == 0.0


def test_smoothness_is_unsigned_like_pathbench():
    # A left turn and a right turn of the same magnitude read the same
    # (arccos of the x component only) -- the benchmark's definition, kept.
    left = [(0, 0), (0, 1), (-1, 1)]
    right = [(0, 0), (0, 1), (1, 1)]
    assert trajectory_smoothness(left) == pytest.approx(trajectory_smoothness(right))


def test_clearance_matches_brute_force():
    rng = np.random.default_rng(0)
    occ = rng.random((9, 9)) < 0.3
    path = [(r, c) for r in range(9) for c in (0, 4, 8) if not occ[r, c]]
    walls = np.argwhere(occ)
    brute = float(np.mean([np.min(np.linalg.norm(walls - np.array(p), axis=1)) for p in path]))
    assert obstacle_clearance(path, occ) == pytest.approx(brute)


def test_clearance_without_obstacles_is_zero():
    assert obstacle_clearance([(0, 0), (1, 1)], np.zeros((3, 3), dtype=bool)) == 0.0


def test_distance_to_goal_empty_path_is_original_distance():
    assert distance_to_goal([], (0, 0), (3, 4)) == 5.0
    assert distance_to_goal([(0, 0), (3, 4)], (0, 0), (3, 4)) == 0.0
    # a partial path leaves the agent at its last cell (PathBench replays it)
    assert distance_to_goal([(0, 0), (0, 1)], (0, 0), (3, 4)) == pytest.approx(math.hypot(3, 3))


def test_bresenham_and_rasterize():
    assert bresenham_line((0, 0), (2, 2)) == [(0, 0), (1, 1), (2, 2)]
    assert bresenham_line((0, 0), (0, 0)) == [(0, 0)]
    assert bresenham_line((1, 1), (0, 3)) == [(1, 1), (1, 2), (0, 3)] or bresenham_line((1, 1), (0, 3)) == [(1, 1), (0, 2), (0, 3)]
    assert rasterize_path([(0, 0), (0, 3)]) == [(0, 0), (0, 1), (0, 2), (0, 3)]
    assert rasterize_path([(0, 0), (2, 2), (2, 4)]) == [(0, 0), (1, 1), (2, 2), (2, 3), (2, 4)]
    assert rasterize_path([]) == []


# ── Task 4: occupancy -> grids, run_mode ──────────────────────────────────


def test_grids_from_occupancy_shapes_and_validity():
    occ = np.zeros((4, 5), dtype=bool)
    occ[1, 1] = True
    g = occupancy_to_grids(occ, 320.0, variant="MoonPlanBench-10", map_name="LDEM_875S_5M")
    assert g["traversable"].dtype == bool
    assert g["traversable"].tolist() == (~occ).tolist()
    for key in ("elevation", "slope", "shadow_ratio"):
        assert g[key].shape == (4, 5)
        assert not g[key].any()
    assert np.all(g["thermal"] == BENCHMARK_THERMAL_C)
    md = g["metadata"]
    assert md["resolution_m"] == 320.0
    assert md["shape"] == [4, 5]
    assert md["source"] == "moonplanbench"
    assert md["layer_validity"]["traversable"] == "DERIVED"
    assert md["layer_validity"]["slope"] == "SYNTHETIC"
    assert md["layer_validity"]["thermal"] == "SYNTHETIC"
    assert md["benchmark"]["variant"] == "MoonPlanBench-10"
    assert md["benchmark"]["slope_threshold_deg"] == 10
    assert md["benchmark"]["map"] == "LDEM_875S_5M"
    assert md["benchmark"]["native_m_per_px"] == 5
    assert md["benchmark"]["downsample_factor"] == 64


def test_multi_criteria_cost_grid_is_flat_on_occupancy():
    occ = np.zeros((6, 6), dtype=bool)
    occ[2, 2] = True
    g = occupancy_to_grids(occ, 320.0)
    cost = compute_cost_grid(g["slope"], g["thermal"], g["shadow_ratio"], 320.0, traversable=g["traversable"])
    finite = cost[np.isfinite(cost)]
    assert finite.size == 35
    assert np.unique(finite).size == 1
    assert not np.isfinite(cost[2, 2])


@pytest.mark.parametrize("mode", MODES)
def test_run_mode_finds_a_path_on_open_map(mode):
    occ = np.zeros((7, 7), dtype=bool)
    occ[3, 1:6] = True  # a wall with a gap at both ends
    res = run_mode(mode, occ, (0, 0), (6, 0), 320.0)
    assert res["mode"] == mode
    assert res["success"] and not res["timed_out"]
    assert res["error"] is None
    assert res["dist_left"] == 0.0
    assert res["original_distance"] == 6.0
    assert res["path"][0] == (0, 0) and res["path"][-1] == (6, 0)
    assert res["length_m"] == pytest.approx(res["length_cells"] * 320.0)
    assert res["steps"] == len(res["path"]) - 1
    assert res["memory_kb"] is None  # tracemalloc inflates the time; memory is a separate, opt-in pass
    assert res["time_s"] >= 0.0
    traced = run_mode(mode, occ, (0, 0), (6, 0), 320.0, trace_memory=True)
    assert traced["memory_kb"] > 0 and traced["success"]
    assert res["smoothness"] >= 0.0 and res["clearance"] > 0.0
    # every step is a king move over free cells
    for a, b in zip(res["path"][:-1], res["path"][1:]):
        assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) == 1
        assert not occ[b]


def test_run_mode_corner_gap_only_cut_mode_succeeds():
    assert run_mode("dijkstra_cut", DIAG_GAP, (0, 0), (2, 2), 1.0)["success"]
    for mode in ("dijkstra_nocut", "lunapath_single", "lunapath_multi"):
        r = run_mode(mode, DIAG_GAP, (0, 0), (2, 2), 1.0)
        assert not r["success"]
        assert r["path"] == []
        assert r["length_cells"] is None and r["steps"] is None and r["smoothness"] is None
        assert r["dist_left"] == pytest.approx(math.sqrt(8))
        assert r["original_distance"] == pytest.approx(math.sqrt(8))


def test_run_mode_lunapath_reports_nodes_and_single_multi_lengths_agree():
    occ = np.zeros((9, 9), dtype=bool)
    occ[4, 0:7] = True
    single = run_mode("lunapath_single", occ, (0, 0), (8, 0), 320.0)
    multi = run_mode("lunapath_multi", occ, (0, 0), (8, 0), 320.0)
    assert single["nodes_expanded"] > 0 and multi["nodes_expanded"] > 0
    assert single["length_cells"] == pytest.approx(multi["length_cells"])
    cut = run_mode("dijkstra_cut", occ, (0, 0), (8, 0), 320.0)
    assert cut["nodes_expanded"] is None
    assert cut["length_cells"] <= single["length_cells"]


def test_run_mode_unknown_mode_raises():
    with pytest.raises(ValueError):
        run_mode("theta_star", DIAG_GAP, (0, 0), (2, 2), 1.0)


# ── Task 5: aggregate, inventory, reference planners, run_benchmark ───────


def _row(success, length, time_s, memory, dist_left, nodes):
    return {
        "success": success, "timed_out": False,
        "length_cells": length, "length_m": None if length is None else length * 320.0,
        "steps": None if length is None else int(length), "time_s": time_s, "memory_kb": memory,
        "smoothness": None if length is None else 0.1, "clearance": None if length is None else 2.0,
        "dist_left": dist_left, "original_distance": 8.0, "nodes_expanded": nodes,
    }


def test_aggregate_filters_like_pathbench():
    rows = [_row(True, 10.0, 1.0, 5.0, 0.0, 50), _row(False, None, 0.5, 3.0, 8.0, 4)]
    a = aggregate(rows)
    assert a["n_maps"] == 2 and a["n_success"] == 1 and a["n_timed_out"] == 0
    assert a["success_rate_pct"] == 50.0
    # successful runs only, as PathBench's analyzer filters them
    assert a["mean_length_cells"] == 10.0
    assert a["mean_length_m"] == 3200.0
    assert a["mean_steps"] == 10.0
    assert a["mean_time_s"] == 1.0 and a["max_time_s"] == 1.0
    assert a["mean_smoothness"] == 0.1 and a["mean_clearance"] == 2.0
    # all runs
    assert a["mean_dist_left"] == 4.0
    assert a["mean_original_distance"] == 8.0
    assert a["mean_memory_kb"] == 4.0
    assert a["mean_nodes_expanded"] == 27.0


def test_aggregate_of_nothing_is_none_not_nan():
    a = aggregate([])
    assert a["n_maps"] == 0 and a["success_rate_pct"] is None and a["mean_length_cells"] is None


def test_aggregate_counts_timeouts_as_failures():
    row = _row(True, 10.0, 61.0, 5.0, 0.0, 50)
    row["timed_out"] = True
    row["success"] = False
    a = aggregate([row])
    assert a["success_rate_pct"] == 0.0 and a["n_timed_out"] == 1 and a["mean_length_cells"] is None


def _write_mini_benchmark(root: Path) -> None:
    for variant in ("MoonPlanBench-10", "MoonPlanBench-20"):
        d = root / variant
        d.mkdir(parents=True)
        open_map = np.zeros((7, 7), dtype=np.uint8)
        open_map[3, 1:6] = 1
        np.save(d / "LDEM_875S_5M.npy", open_map)
        np.save(d / "LDEM_60N_120M.npy", DIAG_GAP.astype(np.uint8))


def test_load_inventory_lists_variants_in_name_order(tmp_path):
    _write_mini_benchmark(tmp_path)
    inv = load_inventory(tmp_path)
    assert list(inv) == ["MoonPlanBench-10", "MoonPlanBench-20"]
    assert [p.name for p in inv["MoonPlanBench-10"]] == ["LDEM_60N_120M.npy", "LDEM_875S_5M.npy"]
    assert load_meta(tmp_path) is None
    (tmp_path / "moonplanbench_meta.json").write_text(json.dumps({"n_files": 4}), encoding="utf-8")
    assert load_meta(tmp_path) == {"n_files": 4}


def test_run_benchmark_mini_end_to_end(tmp_path):
    _write_mini_benchmark(tmp_path)
    out = run_benchmark(tmp_path)
    assert set(out["variants"]) == {"MoonPlanBench-10", "MoonPlanBench-20"}
    assert out["modes"] == list(MODES) and out["rover_id"] == "lpr_1"
    assert out["meta"] is None
    assert out["reference"]["status"].startswith("not run")
    v = out["variants"]["MoonPlanBench-10"]
    assert [m["map"] for m in v["maps"]] == ["LDEM_60N_120M", "LDEM_875S_5M"]
    gap, open_map = v["maps"]
    assert gap["cell_size_m"] == 7680.0 and open_map["cell_size_m"] == 320.0
    assert gap["start_rc"] == [0, 0] and gap["goal_rc"] == [2, 2]
    assert gap["shape"] == [3, 3] and 0 < gap["free_fraction"] < 1
    assert set(gap["results"]) == set(MODES)
    assert gap["results"]["dijkstra_cut"]["success"] and not gap["results"]["dijkstra_nocut"]["success"]
    assert "path" not in gap["results"]["dijkstra_cut"]  # paths are not serialised
    assert gap["cost_grid_unique_values"] == 1
    assert v["aggregates"]["dijkstra_cut"]["success_rate_pct"] == 100.0
    assert v["aggregates"]["dijkstra_nocut"]["success_rate_pct"] == 50.0
    assert v["aggregates"]["lunapath_multi"]["success_rate_pct"] == 50.0
    assert v["reference_aggregates"] == {}
    json.dumps(out)  # serialisable as it stands


def test_run_benchmark_memory_pass_adds_traced_time_and_memory(tmp_path):
    _write_mini_benchmark(tmp_path)
    plain = run_benchmark(tmp_path, modes=("dijkstra_cut", "lunapath_single"))
    row = plain["variants"]["MoonPlanBench-10"]["maps"][1]["results"]["lunapath_single"]
    assert row["memory_kb"] is None and "time_s_traced" not in row
    assert plain["memory_pass"] is False
    traced = run_benchmark(tmp_path, modes=("dijkstra_cut", "lunapath_single"), memory=True)
    row = traced["variants"]["MoonPlanBench-10"]["maps"][1]["results"]["lunapath_single"]
    assert row["memory_kb"] > 0 and row["time_s_traced"] >= 0.0
    assert traced["memory_pass"] is True
    agg = traced["variants"]["MoonPlanBench-10"]["aggregates"]["lunapath_single"]
    assert agg["mean_memory_kb"] > 0 and agg["mean_time_s_traced"] >= 0.0
    assert plain["variants"]["MoonPlanBench-10"]["aggregates"]["lunapath_single"]["mean_time_s_traced"] is None


def test_run_benchmark_max_maps_and_modes(tmp_path):
    _write_mini_benchmark(tmp_path)
    out = run_benchmark(tmp_path, modes=("dijkstra_cut",), max_maps=1)
    v = out["variants"]["MoonPlanBench-20"]
    assert [m["map"] for m in v["maps"]] == ["LDEM_60N_120M"]
    assert list(v["aggregates"]) == ["dijkstra_cut"]


def test_run_benchmark_empty_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_benchmark(tmp_path)


def test_run_benchmark_progress_callback(tmp_path):
    _write_mini_benchmark(tmp_path)
    seen = []
    run_benchmark(tmp_path, modes=("dijkstra_cut",), progress=lambda msg: seen.append(msg))
    assert len(seen) == 4 and all("LDEM_" in m for m in seen)


def test_reference_planner_without_clone_reports_not_run(tmp_path):
    res = run_reference_planner("Dijkstra", DIAG_GAP, (0, 0), (2, 2), tmp_path)
    assert res["success"] is False
    assert res["error"].startswith("not run")
    assert res["memory_kb"] is None
    with pytest.raises(ValueError):
        run_reference_planner("PRM", DIAG_GAP, (0, 0), (2, 2), tmp_path)


@pytest.mark.skipif(not _HAS_CLONE, reason="needs a local PlanetaryPathBench clone (LUNAPATH_PPB_DIR)")
def test_reference_dijkstra_on_the_corner_gap_cuts_the_corner():
    res = run_reference_planner("Dijkstra", DIAG_GAP, (0, 0), (2, 2), _PPB_DIR)
    assert res["success"]
    assert res["path"][0] == (0, 0) and res["path"][-1] == (2, 2)
    assert res["length_cells"] == pytest.approx(2 * math.sqrt(2))
    assert res["memory_kb"] is None
    theta = run_reference_planner("ThetaStar", DIAG_GAP, (0, 0), (2, 2), _PPB_DIR, trace_memory=True)
    assert theta["success"] and theta["length_cells_raw"] == pytest.approx(2 * math.sqrt(2))
    assert theta["memory_kb"] > 0


@pytest.mark.skipif(not (_HAS_CLONE and _HAS_DATA), reason="needs the clone and the dataset")
def test_start_goal_matches_the_benchmarks_own_function_on_real_maps():
    import sys

    sys.path.insert(0, _PPB_DIR)
    try:
        from adapters._common import auto_select_start_goal as reference
    finally:
        sys.path.remove(_PPB_DIR)
    inv = load_inventory(MOONPLANBENCH_DIR)
    n = 0
    for variant, paths in inv.items():
        for path in paths:
            occ = load_occupancy(path)
            (sx, sy), (gx, gy) = reference(occ.astype(int))
            assert auto_select_start_goal(occ) == ((sy, sx), (gy, gx)), (variant, path.name)
            n += 1
    assert n == 36


# ── Task 6: the cache builder's network-free parts ────────────────────────

_EFV_HTML = (
    '<html><body><div class="flip-entries">'
    '<div class="flip-entry" id="entry-1XZ3CwZkLbhnETQ3xzhAkQB0R7xuSJN1e"><a href="x">'
    '<div class="flip-entry-info"><div class="flip-entry-thumb"></div>'
    '<div class="flip-entry-title">LDEM_45N_100M.npy</div>'
    '<div class="flip-entry-last-modified"><div>Dec 18, 2025</div></div></div></a></div>'
    '<div class="flip-entry" id="entry-1HMVqtBXbBOcMFH7ljJxb2-P2aiSdj6Qf">'
    '<div class="flip-entry-title">LDEM_45S_100M.npy</div></div>'
    '<div class="flip-entry" id="entry-1Nn9wS1VrN0Z5tEJS3zJ9wrsQUe1cGKy0">'
    '<div class="flip-entry-title">Background</div></div>'
    "</div></body></html>"
)


def _npy_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    np.save(buf, arr)
    return buf.getvalue()


def test_cache_builder_parses_the_embedded_folder_listing():
    mod = _load_script("build_moonplanbench_cache")
    entries = mod.parse_embedded_folder_listing(_EFV_HTML)
    assert entries == [
        ("LDEM_45N_100M.npy", "1XZ3CwZkLbhnETQ3xzhAkQB0R7xuSJN1e"),
        ("LDEM_45S_100M.npy", "1HMVqtBXbBOcMFH7ljJxb2-P2aiSdj6Qf"),
        ("Background", "1Nn9wS1VrN0Z5tEJS3zJ9wrsQUe1cGKy0"),
    ]
    assert mod.npy_entries(entries) == entries[:2]
    assert mod.download_url("abc") == "https://drive.google.com/uc?export=download&id=abc"
    assert mod.folder_listing_url("xyz") == "https://drive.google.com/embeddedfolderview?id=xyz#list"


def test_cache_builder_validates_npy_bytes():
    mod = _load_script("build_moonplanbench_cache")
    arr = mod.validate_npy_bytes(_npy_bytes(np.array([[0, 1], [1, 0]], dtype=np.uint8)))
    assert arr.shape == (2, 2)
    with pytest.raises(ValueError):
        mod.validate_npy_bytes(b"<html>not a numpy file")
    with pytest.raises(ValueError):
        mod.validate_npy_bytes(_npy_bytes(np.array([[0, 2]], dtype=np.uint8)))
    with pytest.raises(ValueError):
        mod.validate_npy_bytes(_npy_bytes(np.zeros((2, 2, 2), dtype=np.uint8)))


def test_cache_builder_offline_meta_from_existing_files(tmp_path):
    mod = _load_script("build_moonplanbench_cache")
    _write_mini_benchmark(tmp_path)
    meta = mod.build_meta(tmp_path, drive_ids={}, fetched_utc="2026-09-05T00:00:00+00:00")
    assert meta["data_license"].startswith("CC BY-NC-SA 4.0")
    assert meta["paper"]["arxiv"] == "2512.21438v1"
    assert meta["repo"]["commit"].startswith("86dc4b63")
    assert meta["drive_root_folder_id"] == "15srtIABvwBSbILQESVvAFPHMc3TCzS_R"
    assert meta["n_files"] == 4
    assert set(meta["variants"]) == {"MoonPlanBench-10", "MoonPlanBench-20"}
    files = {e["name"]: e for e in meta["variants"]["MoonPlanBench-10"]["files"]}
    entry = files["LDEM_875S_5M.npy"]
    expected = hashlib.sha256((tmp_path / "MoonPlanBench-10" / "LDEM_875S_5M.npy").read_bytes()).hexdigest()
    assert entry["sha256"] == expected
    assert entry["shape"] == [7, 7] and 0 < entry["free_fraction"] < 1 and entry["bytes"] > 0
    assert entry["drive_id"] is None and entry["cell_size_m"] == 320.0
    assert meta["fetched_utc"] == "2026-09-05T00:00:00+00:00"
    mod.write_meta(tmp_path, meta)
    assert load_meta(tmp_path)["n_files"] == 4


# ── Task 7: the runner's report ───────────────────────────────────────────


def test_runner_renders_every_section_and_quotes_the_paper(tmp_path):
    runner = _load_script("moonplanbench_runner")
    _write_mini_benchmark(tmp_path)
    report = run_benchmark(tmp_path)
    md = runner.render_markdown(report)
    for heading in (
        "## 1. Veri kimliği",
        "## 2. Metrik tablosu",
        "## 3. Başarı oranı farkları",
        "## 4. Çok kriterli mod",
        "## 5. Süre ve bellek",
        "## 6. İddia sınırı",
    ):
        assert heading in md, heading
    assert "651,81" in md and "alıntı" in md  # the paper's Dijkstra row, decimal comma like the other reports
    assert "dijkstra_cut" in md and "dijkstra_nocut" in md
    # the corner-gap map is only connected through corner cuts: named in section 3
    assert "LDEM_60N_120M" in md
    assert "sağlama yok" in md  # no meta beside the mini maps
    assert "koşturulmadı" in md  # reference planners not run
    round_trip = json.loads(json.dumps(report))
    assert runner.render_markdown(round_trip) == md


def test_runner_cli_writes_json_before_markdown_and_rerenders(tmp_path):
    runner = _load_script("moonplanbench_runner")
    _write_mini_benchmark(tmp_path)
    json_path = tmp_path / "out.json"
    md_path = tmp_path / "out.md"
    rc = runner.main(["--data-dir", str(tmp_path), "--json", str(json_path), "--output", str(md_path), "--modes", "dijkstra_cut,dijkstra_nocut"])
    assert rc == 0 and json_path.is_file() and md_path.is_file()
    first = md_path.read_text(encoding="utf-8")
    md_path.unlink()
    rc = runner.main(["--from-json", str(json_path), "--output", str(md_path)])
    assert rc == 0 and md_path.read_text(encoding="utf-8") == first
    assert json.loads(json_path.read_text(encoding="utf-8"))["modes"] == ["dijkstra_cut", "dijkstra_nocut"]


def test_runner_without_data_returns_nonzero(tmp_path):
    runner = _load_script("moonplanbench_runner")
    assert runner.main(["--data-dir", str(tmp_path), "--output", str(tmp_path / "x.md")]) == 1
    assert not (tmp_path / "x.md").exists()
