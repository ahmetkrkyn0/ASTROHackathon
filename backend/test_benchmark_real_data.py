"""D2 on the real MoonPlanBench maps (Chancán et al. 2025, arXiv 2512.21438):
the 36 files are what the meta says they are, the benchmark's own start/goal
rule is reproduced on every map, and the pure-distance Dijkstra under the
benchmark's motion model reproduces the paper's Dijkstra path lengths --
a reproduction lock, not a success claim. Skips without the dataset
(scripts/build_moonplanbench_cache.py).
"""

from __future__ import annotations

import hashlib
import os

import numpy as np
import pytest

from app.benchmark import (
    META_FILENAME,
    MODES,
    MOONPLANBENCH_DIR,
    PAPER_TABLE_1,
    VARIANTS,
    aggregate,
    auto_select_start_goal,
    cell_size_m,
    load_inventory,
    load_meta,
    load_occupancy,
    run_mode,
)

_HAS_DATA = all(os.path.isdir(os.path.join(MOONPLANBENCH_DIR, v)) for v in VARIANTS)
pytestmark = pytest.mark.skipif(not _HAS_DATA, reason="needs lunapath/data/benchmarks/moonplanbench (build_moonplanbench_cache.py)")

# (row, col) start and goal per map, computed on 5 Sept 2026 with the
# benchmark's own adapters/_common.auto_select_start_goal on the files
# fetched that day. The benchmark releases no start/goal list of its own;
# the function IS the definition.
EXPECTED_START_GOAL_RC = {
    "MoonPlanBench-10": {
        "LDEM_45N_100M": ((0, 0), (449, 448)),
        "LDEM_45S_100M": ((0, 0), (449, 449)),
        "LDEM_60N_120M": ((0, 0), (242, 242)),
        "LDEM_60S_120M": ((0, 0), (242, 242)),
        "LDEM_75N_30M": ((0, 0), (476, 476)),
        "LDEM_75S_30M": ((0, 2), (476, 476)),
        "LDEM_80N_20M": ((0, 0), (474, 472)),
        "LDEM_80S_20M": ((0, 88), (474, 474)),
        "LDEM_85N_10M": ((72, 276), (473, 51)),
        "LDEM_85S_10M": ((0, 258), (473, 473)),
        "LDEM_875N_5M": ((0, 280), (451, 1)),
        "LDEM_875S_5M": ((0, 300), (473, 0)),
    },
    "MoonPlanBench-15": {
        "LDEM_45N_100M": ((0, 0), (449, 449)),
        "LDEM_45S_100M": ((0, 0), (449, 449)),
        "LDEM_60N_120M": ((0, 0), (242, 242)),
        "LDEM_60S_120M": ((0, 0), (242, 242)),
        "LDEM_75N_30M": ((0, 0), (476, 476)),
        "LDEM_75S_30M": ((0, 0), (476, 476)),
        "LDEM_80N_20M": ((0, 0), (474, 472)),
        "LDEM_80S_20M": ((0, 0), (474, 474)),
        "LDEM_85N_10M": ((0, 25), (473, 473)),
        "LDEM_85S_10M": ((0, 0), (473, 473)),
        "LDEM_875N_5M": ((0, 14), (473, 473)),
        "LDEM_875S_5M": ((0, 0), (473, 473)),
    },
    "MoonPlanBench-20": {
        "LDEM_45N_100M": ((0, 0), (449, 449)),
        "LDEM_45S_100M": ((0, 0), (449, 449)),
        "LDEM_60N_120M": ((0, 0), (242, 242)),
        "LDEM_60S_120M": ((0, 0), (242, 242)),
        "LDEM_75N_30M": ((0, 0), (476, 476)),
        "LDEM_75S_30M": ((0, 0), (476, 476)),
        "LDEM_80N_20M": ((0, 0), (474, 472)),
        "LDEM_80S_20M": ((0, 0), (474, 474)),
        "LDEM_85N_10M": ((0, 0), (473, 473)),
        "LDEM_85S_10M": ((0, 0), (473, 473)),
        "LDEM_875N_5M": ((0, 0), (473, 473)),
        "LDEM_875S_5M": ((0, 0), (473, 473)),
    },
}
SHAPES = {243, 450, 474, 475, 477}


@pytest.fixture(scope="module")
def inventory():
    return load_inventory(MOONPLANBENCH_DIR)


@pytest.fixture(scope="module")
def maps(inventory):
    """{(variant, stem): (occ, start, goal)} -- the BFS start/goal rule costs
    a few seconds per map, so it runs once per map for the whole module."""
    loaded = {}
    for variant, paths in inventory.items():
        for path in paths:
            occ = load_occupancy(path)
            start, goal = auto_select_start_goal(occ)
            loaded[(variant, path.stem)] = (occ, start, goal)
    return loaded


def test_thirty_six_maps_twelve_per_variant(inventory):
    assert list(inventory) == list(VARIANTS)
    for variant in VARIANTS:
        names = [p.stem for p in inventory[variant]]
        assert names == sorted(EXPECTED_START_GOAL_RC[variant]), variant
    assert sum(len(v) for v in inventory.values()) == 36


def test_maps_are_binary_square_and_partly_free(maps):
    for (variant, stem), (occ, _, _) in maps.items():
        assert occ.shape[0] == occ.shape[1] and occ.shape[0] in SHAPES, (variant, stem)
        free = 1.0 - float(occ.mean())
        assert 0.4 < free < 1.0, (variant, stem, free)
        assert cell_size_m(stem) in {320.0, 640.0, 1280.0, 1920.0, 6400.0, 7680.0}


def test_meta_digests_match_the_files(inventory):
    meta = load_meta(MOONPLANBENCH_DIR)
    if meta is None:
        pytest.skip(f"no {META_FILENAME} beside the maps")
    assert meta["data_license"].startswith("CC BY-NC-SA 4.0")
    assert meta["n_files"] == 36
    for variant, paths in inventory.items():
        recorded = {f["name"]: f for f in meta["variants"][variant]["files"]}
        for path in paths:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert recorded[path.name]["sha256"] == digest, path.name
            assert recorded[path.name]["bytes"] == path.stat().st_size


def test_start_goal_rule_reproduced_on_every_map(maps):
    assert len(maps) == 36
    for (variant, stem), (_, start, goal) in maps.items():
        assert (start, goal) == EXPECTED_START_GOAL_RC[variant][stem], (variant, stem)


@pytest.mark.parametrize("variant", VARIANTS)
def test_benchmark_motion_model_reproduces_the_papers_dijkstra_lengths(maps, variant):
    rows = [
        run_mode("dijkstra_cut", occ, start, goal, cell_size_m(stem))
        for (v, stem), (occ, start, goal) in maps.items()
        if v == variant
    ]
    assert len(rows) == 12
    agg = aggregate(rows)
    assert agg["success_rate_pct"] == 100.0
    # Table 1 of the paper, two decimals: 651.81 / 636.16 / 620.24.
    assert agg["mean_length_cells"] == pytest.approx(PAPER_TABLE_1[variant]["Dijkstra"]["length_cells"], abs=0.01)
    assert agg["mean_dist_left"] == 0.0


def test_all_four_modes_find_a_path_on_the_easiest_map(maps):
    occ, start, goal = maps[("MoonPlanBench-20", "LDEM_45N_100M")]
    for mode in MODES:
        res = run_mode(mode, occ, start, goal, cell_size_m("LDEM_45N_100M"))
        assert res["success"] and not res["timed_out"], (mode, res["error"])
        assert res["dist_left"] == 0.0
    assert np.isfinite(res["length_cells"])
