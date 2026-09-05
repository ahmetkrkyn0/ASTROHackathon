"""The roughness criterion on the cost path (C4): the fifth weight key, the
scalar/grid parity of f_roughness, compute_cost_grid with and without the
layer (the four-term formula stays bit for bit), the cost map layer, the
4-D cube's block-max coarsening and the rover-grid adaptation. Synthetic
grids only."""

from __future__ import annotations

import numpy as np
import pytest

from app import constants as C
from app.constants import get_rover, rover_catalog, rover_default_weights
from app.cost_engine import (
    _WEIGHT_KEYS,
    COST_MODEL_ID,
    compute_cost_grid,
    default_weights,
    f_roughness,
    resolve_weights,
)
from app.cost_vec import (
    f_energy_cell_grid,
    f_roughness_grid,
    f_shadow_cell_grid,
    f_slope_grid,
    f_thermal_grid,
)
from app.roughness import RoughnessScale
from app.scenarios import MISSION_PROFILES

SHAPE = (12, 12)
RES_M = 5.0


def _scale() -> RoughnessScale:
    knots = np.linspace(0.05, 3.0, 51)
    probs = np.linspace(0.0, 1.0, 51) ** 0.8
    return RoughnessScale.from_meta({"knots": knots.tolist(), "probs": probs.tolist(), "source": "test"})


def _inputs(seed: int = 0):
    rng = np.random.default_rng(seed)
    slope = rng.uniform(0.0, 30.0, SHAPE)  # some cells above every rover's limit
    thermal = rng.uniform(-80.0, -30.0, SHAPE)
    thermal_min = thermal - rng.uniform(20.0, 80.0, SHAPE)
    shadow = rng.uniform(0.0, 1.0, SHAPE)
    traversable = np.ones(SHAPE, dtype=bool)
    traversable[0, 0] = False
    roughness = np.exp(rng.normal(-0.3, 0.5, SHAPE))  # log-normal metres, 0.2..3
    return slope, thermal, shadow, thermal_min, traversable, roughness


def _four_term_sum(slope, thermal, shadow, thermal_min, rover, weights) -> np.ndarray:
    """The unclamped four-term weighted sum, operation for operation."""
    w = resolve_weights(weights, rover)
    with np.errstate(invalid="ignore"):
        return (
            w["w_slope"] * f_slope_grid(slope, rover)
            + w["w_energy"] * f_energy_cell_grid(slope, rover, shadow)
            + w["w_shadow"] * f_shadow_cell_grid(shadow)
            + w["w_thermal"] * f_thermal_grid(thermal, rover, thermal_min)
        )


def _finish(combined, slope, thermal, shadow, thermal_min, traversable) -> np.ndarray:
    """compute_cost_grid's clamp and invalid mask."""
    cost = np.maximum(combined, 0.01)
    invalid = ~traversable | np.isnan(slope) | np.isnan(thermal) | np.isnan(shadow) | np.isnan(thermal_min)
    cost[invalid] = np.inf
    return cost


def _four_terms(slope, thermal, shadow, thermal_min, traversable, rover, weights) -> np.ndarray:
    """compute_cost_grid's pre-C4 body, operation for operation."""
    combined = _four_term_sum(slope, thermal, shadow, thermal_min, rover, weights)
    return _finish(combined, slope, thermal, shadow, thermal_min, traversable)


# ── the fifth weight ────────────────────────────────────────────────────────


def test_w_roughness_is_the_fifth_weight_key_everywhere():
    assert "w_roughness" in _WEIGHT_KEYS and len(_WEIGHT_KEYS) == 5
    assert "w_roughness" in C.MODELLED_FIELDS
    assert C.W_ROUGHNESS == 0.15
    for rover_id in C.ROVERS:
        rover = get_rover(rover_id)
        assert default_weights(rover)["w_roughness"] == 0.15
        assert rover_default_weights(rover_id)["w_roughness"] == 0.15
    for entry in rover_catalog():
        assert entry["default_weights"]["w_roughness"] == 0.15


def test_every_mission_profile_carries_w_roughness_without_rescaling_the_others():
    for profile_id, profile in MISSION_PROFILES.items():
        weights = profile["weights"]
        assert weights["w_roughness"] == C.W_ROUGHNESS, profile_id
        # The four existing weights still sum to 1.0: nothing was rescaled.
        four = weights["w_slope"] + weights["w_energy"] + weights["w_shadow"] + weights["w_thermal"]
        assert four == pytest.approx(1.0, abs=1e-9), profile_id


def test_resolve_weights_fills_the_roughness_default():
    assert resolve_weights({"w_slope": 1.0})["w_roughness"] == 0.15
    assert resolve_weights({"w_roughness": 0.3})["w_roughness"] == 0.3
    assert resolve_weights(None)["w_roughness"] == 0.15


def test_cost_model_id_was_bumped_to_v5_for_the_new_criterion():
    assert COST_MODEL_ID.endswith("_v5") and "roughness" in COST_MODEL_ID


# ── f_roughness scalar <-> grid ─────────────────────────────────────────────


def test_f_roughness_scalar_reference_matches_the_grid_form_bit_for_bit():
    scale = _scale()
    rng = np.random.default_rng(1)
    values = rng.uniform(-0.2, 4.0, 5_000)
    values[::50] = np.nan
    grid = f_roughness_grid(values, scale)
    scalar = np.array([f_roughness(float(v), scale) for v in values])
    assert np.array_equal(grid, scalar)
    assert f_roughness(float("nan"), scale) == 0.5
    assert 0.0 <= grid.min() and grid.max() <= 1.0


# ── compute_cost_grid ───────────────────────────────────────────────────────


@pytest.mark.parametrize("rover_id", list(C.ROVERS))
def test_cost_grid_without_roughness_is_the_four_term_formula_bit_for_bit(rover_id):
    slope, thermal, shadow, thermal_min, traversable, _ = _inputs()
    rover = get_rover(rover_id)
    got = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover, thermal_min_grid=thermal_min
    )
    assert np.array_equal(got, _four_terms(slope, thermal, shadow, thermal_min, traversable, rover, None))


@pytest.mark.parametrize("rover_id", list(C.ROVERS))
def test_cost_grid_with_roughness_adds_the_weighted_criterion(rover_id):
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs()
    rover = get_rover(rover_id)
    scale = _scale()
    got = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover,
        thermal_min_grid=thermal_min, roughness_grid=roughness, roughness_scale=scale,
    )
    four = _four_terms(slope, thermal, shadow, thermal_min, traversable, rover, None)
    # The criterion is added BEFORE the 0.01 clamp (a cell whose four terms
    # sit under the floor still pays its roughness), so the reference adds
    # it to the unclamped sum.
    combined = _four_term_sum(slope, thermal, shadow, thermal_min, rover, None)
    expected = _finish(
        combined + 0.15 * f_roughness_grid(roughness, scale),
        slope, thermal, shadow, thermal_min, traversable,
    )
    finite = np.isfinite(four)
    np.testing.assert_allclose(got[finite], expected[finite], atol=1e-12, rtol=0.0)
    assert np.array_equal(np.isinf(got), np.isinf(four))
    assert np.all(got[finite] >= four[finite])


def test_zero_roughness_weight_is_bit_equal_to_no_roughness():
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs()
    rover = get_rover("lpr_1")
    weights = {"w_roughness": 0.0}
    with_layer = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover, weights=weights,
        thermal_min_grid=thermal_min, roughness_grid=roughness, roughness_scale=_scale(),
    )
    without = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover, weights=weights,
        thermal_min_grid=thermal_min,
    )
    assert np.array_equal(with_layer, without)


def test_the_roughness_weight_changes_the_grid():
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs()
    rover = get_rover("lpr_1")
    grids = {
        w: compute_cost_grid(
            slope, thermal, shadow, RES_M, traversable=traversable, rover=rover,
            weights={"w_roughness": w}, thermal_min_grid=thermal_min,
            roughness_grid=roughness, roughness_scale=_scale(),
        )
        for w in (0.15, 0.30)
    }
    finite = np.isfinite(grids[0.15])
    assert not np.array_equal(grids[0.15], grids[0.30])
    assert np.all(grids[0.30][finite] >= grids[0.15][finite])


def test_a_roughness_grid_without_its_scale_is_refused():
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs()
    with pytest.raises(ValueError, match="scale"):
        compute_cost_grid(
            slope, thermal, shadow, RES_M, traversable=traversable,
            thermal_min_grid=thermal_min, roughness_grid=roughness,
        )


def test_a_roughness_grid_of_the_wrong_shape_is_refused():
    slope, thermal, shadow, thermal_min, traversable, _ = _inputs()
    with pytest.raises(ValueError, match="roughness"):
        compute_cost_grid(
            slope, thermal, shadow, RES_M, traversable=traversable,
            thermal_min_grid=thermal_min, roughness_grid=np.ones((3, 3)), roughness_scale=_scale(),
        )


def test_nan_roughness_reads_the_median_rank_and_never_blocks_a_cell():
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs()
    slope[2, 2] = 3.0  # keep the cell passable for every rover
    roughness[2, 2] = np.nan
    rover = get_rover("lpr_1")
    got = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover,
        thermal_min_grid=thermal_min, roughness_grid=roughness, roughness_scale=_scale(),
    )
    combined = _four_term_sum(slope, thermal, shadow, thermal_min, rover, None)
    assert np.isfinite(got[2, 2])
    assert got[2, 2] == pytest.approx(max(combined[2, 2] + 0.15 * 0.5, 0.01), abs=1e-12)


# ── cost map layer, cube, rover grids, pathfinder ───────────────────────────


def _context(roughness=None, scale=None):
    from app.costmap import PlanContext

    slope, thermal, shadow, thermal_min, traversable, _ = _inputs(2)
    slope = np.clip(slope, 0.0, 18.0)  # every cell passable for every rover
    return PlanContext(
        slope=slope, thermal=thermal, shadow_ratio=shadow, traversable=traversable,
        resolution_m=RES_M, rover=get_rover("lpr_1"), thermal_min=thermal_min,
        roughness=roughness, roughness_scale=scale,
    )


def test_plan_context_carries_roughness_and_its_scale_and_slices_them():
    from app.costmap import CostMap

    _, _, _, _, _, roughness = _inputs(2)
    scale = _scale()
    ctx = _context(roughness, scale)
    cell = CostMap._cell_context(3, 4, ctx)
    assert cell.roughness.shape == (1, 1) and cell.roughness[0, 0] == roughness[3, 4]
    assert cell.roughness_scale is scale
    bare = CostMap._cell_context(0, 0, _context())
    assert bare.roughness is None and bare.roughness_scale is None


def test_roughness_layer_contribution_is_the_scaled_criterion():
    from app.costmap import RoughnessLayer

    _, _, _, _, _, roughness = _inputs(2)
    scale = _scale()
    layer = RoughnessLayer(0.15, scale)
    assert layer.name == "roughness" and layer.validity == "MEASURED" and layer.weight == 0.15
    assert np.array_equal(layer.contribution(_context(roughness, scale)), f_roughness_grid(roughness, scale))


def test_roughness_layer_refuses_a_context_without_roughness():
    from app.costmap import RoughnessLayer

    with pytest.raises(ValueError, match="roughness"):
        RoughnessLayer(0.15, _scale()).contribution(_context())


def test_default_cost_map_adds_the_layer_only_with_a_scale():
    from app.costmap import default_cost_map

    rover = get_rover("lpr_1")
    assert default_cost_map(rover).layer_names() == ["slope", "energy", "shadow", "thermal"]
    with_scale = default_cost_map(rover, roughness_scale=_scale(), layer_validity={"roughness": "MEASURED"})
    assert with_scale.layer_names() == ["slope", "energy", "shadow", "thermal", "roughness"]
    assert with_scale.layers[-1].validity == "MEASURED"


def test_cost_map_total_and_explain_match_compute_cost_grid_with_roughness():
    from app.costmap import default_cost_map

    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs(2)
    slope = np.clip(slope, 0.0, 18.0)
    rover = get_rover("lpr_1")
    scale = _scale()
    ctx = _context(roughness, scale)
    cost_map = default_cost_map(rover, roughness_scale=scale)
    total = cost_map.total(ctx)
    reference = compute_cost_grid(
        slope, thermal, shadow, RES_M, traversable=traversable, rover=rover,
        thermal_min_grid=thermal_min, roughness_grid=roughness, roughness_scale=scale,
    )
    finite = np.isfinite(reference)
    np.testing.assert_allclose(total[finite], reference[finite], atol=1e-12, rtol=0.0)
    breakdown = cost_map.explain(5, 5, ctx)
    assert set(breakdown) == {"slope", "energy", "shadow", "thermal", "roughness", "total"}
    assert breakdown["roughness"] == pytest.approx(0.15 * f_roughness(float(roughness[5, 5]), scale), abs=1e-12)
    assert breakdown["total"] == pytest.approx(total[5, 5], abs=1e-12)


def test_cost_cube_coarsens_roughness_with_the_block_maximum():
    from app.cost_cube import build_cost_cube, coarsen_grid

    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs(3)
    slope = np.clip(slope, 0.0, 18.0)
    traversable[:] = True
    base = {
        "slope": slope, "thermal": thermal, "shadow_ratio": shadow, "traversable": traversable,
        "thermal_min": thermal_min, "thermal_sunlit_peak": thermal,
        "metadata": {"resolution_m": RES_M, "thermal_shadow_coupled": True},
    }
    rover = get_rover("lpr_1")
    series = [shadow, np.clip(shadow + 0.2, 0.0, 1.0)]
    scale = _scale()
    without = build_cost_cube(base, series, rover, coarsen=2)
    with_layer = build_cost_cube(base, series, rover, coarsen=2, roughness=roughness, roughness_scale=scale)
    assert with_layer.shape == without.shape == (2, 6, 6)
    expected = 0.15 * f_roughness_grid(coarsen_grid(roughness, 2, how="max"), scale)
    for t in range(2):
        finite = np.isfinite(without[t])
        np.testing.assert_allclose((with_layer[t] - without[t])[finite], expected[finite], atol=1e-12, rtol=0.0)
        assert np.array_equal(np.isinf(with_layer[t]), np.isinf(without[t]))
    with pytest.raises(ValueError, match="scale"):
        build_cost_cube(base, series, rover, coarsen=2, roughness=roughness)
    with pytest.raises(ValueError, match="roughness"):
        build_cost_cube(base, series, rover, coarsen=2, roughness=np.ones((3, 3)), roughness_scale=scale)


def _base_grids(with_roughness: bool):
    slope, thermal, shadow, thermal_min, traversable, roughness = _inputs(4)
    slope = np.clip(slope, 0.0, 18.0)
    base = {
        "elevation": np.zeros(SHAPE), "slope": slope, "thermal": thermal, "thermal_min": thermal_min,
        "shadow_ratio": shadow, "traversable": np.ones(SHAPE, dtype=bool),
        "metadata": {
            "resolution_m": RES_M, "shape": list(SHAPE), "default_rover_id": "lpr_1",
            "cost_weights": {}, "layer_validity": {"slope": "DERIVED", "thermal": "MODEL", "shadow_ratio": "DERIVED"},
        },
    }
    if with_roughness:
        base["roughness"] = roughness
        base["metadata"]["roughness"] = {"product": "LDRM_80S_50MPP_ADJ_ROUGH_100M", "scale": _scale().to_meta()}
        base["metadata"]["layer_validity"]["roughness"] = "MEASURED"
    return base


def test_grids_for_rover_puts_the_roughness_layer_into_the_cost_and_says_so():
    from app.rover_grids import grids_for_rover

    base = _base_grids(with_roughness=True)
    adapted = grids_for_rover(base, "nasa_viper", {"w_roughness": 0.3})
    rover = get_rover("nasa_viper")
    reference = compute_cost_grid(
        base["slope"], base["thermal"], base["shadow_ratio"], RES_M, traversable=adapted["traversable"],
        rover=rover, weights={"w_roughness": 0.3}, thermal_min_grid=base["thermal_min"],
        roughness_grid=base["roughness"], roughness_scale=_scale(),
    )
    assert np.array_equal(adapted["cost"], reference)
    assert adapted["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal", "roughness"]
    assert adapted["metadata"]["cost_weights"]["w_roughness"] == 0.3
    assert adapted["metadata"]["cost_model"] == COST_MODEL_ID


def test_grids_for_rover_without_the_layer_keeps_the_four_criteria():
    from app.rover_grids import grids_for_rover

    base = _base_grids(with_roughness=False)
    adapted = grids_for_rover(base, "lpr_1")
    reference = compute_cost_grid(
        base["slope"], base["thermal"], base["shadow_ratio"], RES_M, traversable=adapted["traversable"],
        rover=get_rover("lpr_1"), thermal_min_grid=base["thermal_min"],
    )
    assert np.array_equal(adapted["cost"], reference)
    assert adapted["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal"]
    assert "roughness" not in adapted


def test_pathfinder_recompute_carries_the_roughness_layer():
    from app.pathfinder import _resolve_cost_grid

    base = _base_grids(with_roughness=True)
    rover = get_rover("lpr_1")
    traversable = np.ones(SHAPE, dtype=bool)
    got = _resolve_cost_grid(
        base, base["slope"], base["thermal"], base["shadow_ratio"], RES_M, traversable, None, rover
    )
    reference = compute_cost_grid(
        base["slope"], base["thermal"], base["shadow_ratio"], RES_M, traversable=traversable, rover=rover,
        thermal_min_grid=base["thermal_min"], roughness_grid=base["roughness"], roughness_scale=_scale(),
    )
    assert np.array_equal(got, reference)


def test_terrain_lists_the_two_measured_layers():
    from app.terrain import LAYER_DESCRIPTIONS, LAYER_UNITS, TERRAIN_LAYERS

    assert "roughness" in TERRAIN_LAYERS and "psr" in TERRAIN_LAYERS
    assert LAYER_UNITS["roughness"] == "m" and LAYER_UNITS["psr"] == "boolean"
    assert "100 m" in LAYER_DESCRIPTIONS["roughness"] and "not" in LAYER_DESCRIPTIONS["roughness"].lower()
    assert "PSR" in LAYER_DESCRIPTIONS["psr"]


def test_a_stored_cost_grid_is_not_reused_when_the_criteria_it_summed_differ():
    """A cost stamped as five-criterion must not serve a request whose grids
    lack the roughness layer, and vice versa -- rover/weights/mask/model can
    all match while the criteria do not (the default rover on the loaded
    grids). cost_criteria is the stamp that catches it."""
    from app.rover_grids import grids_for_rover

    base = _base_grids(with_roughness=True)
    five = grids_for_rover(base, "lpr_1")
    assert five["metadata"]["cost_criteria"][-1] == "roughness"
    # Now hand back the adapted grids WITHOUT the layer: everything else matches.
    stripped = {k: v for k, v in five.items() if k != "roughness"}
    stripped["metadata"] = {k: v for k, v in five["metadata"].items() if k != "roughness"}
    four = grids_for_rover(stripped, "lpr_1")
    assert four["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal"]
    assert not np.array_equal(four["cost"], five["cost"])
    reference = compute_cost_grid(
        base["slope"], base["thermal"], base["shadow_ratio"], RES_M, traversable=four["traversable"],
        rover=get_rover("lpr_1"), thermal_min_grid=base["thermal_min"],
    )
    assert np.array_equal(four["cost"], reference)
    # And the other way round: a four-criterion stamp with the layer present.
    regrown = dict(four)
    regrown["roughness"] = base["roughness"]
    regrown["metadata"] = {**four["metadata"], "roughness": base["metadata"]["roughness"]}
    again = grids_for_rover(regrown, "lpr_1")
    assert np.array_equal(again["cost"], five["cost"])


def test_pathfinder_does_not_reuse_a_cost_grid_whose_criteria_differ():
    from app.pathfinder import _resolve_cost_grid
    from app.rover_grids import grids_for_rover

    base = _base_grids(with_roughness=True)
    five = grids_for_rover(base, "lpr_1")
    stripped = {k: v for k, v in five.items() if k != "roughness"}
    stripped["metadata"] = {k: v for k, v in five["metadata"].items() if k != "roughness"}
    rover = get_rover("lpr_1")
    got = _resolve_cost_grid(
        stripped, base["slope"], base["thermal"], base["shadow_ratio"], RES_M, five["traversable"], None, rover
    )
    assert not np.array_equal(got, five["cost"])
