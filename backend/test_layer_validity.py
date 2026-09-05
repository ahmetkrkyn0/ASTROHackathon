"""Layer provenance (validity) plumbing tests."""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.data_loader import load_preprocessed_grids

_VALID = {"MEASURED", "DERIVED", "MODEL", "SYNTHETIC"}
_LAYERS = (
    "elevation",
    "slope",
    "aspect",
    "shadow_ratio",
    "thermal",
    # The cold-end equilibrium is its own layer with its own provenance --
    # it mixes the MODEL thermal field with the DERIVED shadow field, so it
    # cannot inherit either one's label. (Round 4 review, H-3.)
    "thermal_min",
    "traversable",
    "cost",
)


def _write_fake_processed_dir(tmp_path):
    shape = (4, 4)
    arrays = {
        "elevation_grid": np.zeros(shape),
        "slope_grid": np.zeros(shape),
        "aspect_grid": np.zeros(shape),
        "shadow_ratio_grid": np.zeros(shape),
        "thermal_grid": np.full(shape, -50.0),
        "traversability_grid": np.ones(shape),
        "cost_grid": np.full(shape, 0.5),
    }
    for name, arr in arrays.items():
        np.save(tmp_path / f"{name}.npy", arr)

    metadata = {
        "origin": {"x": 156000.0, "y": 28000.0},
        "resolution_m": 80.0,
        "shape": list(shape),
        "crs": "test",
        "cost_weights": {
            "w_slope": 0.409,
            "w_energy": 0.259,
            "w_shadow": 0.142,
            "w_thermal": 0.19,
        },
        "layer_validity": {
            "elevation": "MEASURED",
            "slope": "DERIVED",
            "aspect": "DERIVED",
            "shadow_ratio": "DERIVED",
            "thermal": "MODEL",
            "traversable": "DERIVED",
            "cost": "DERIVED",
        },
    }
    (tmp_path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tmp_path


def test_load_preprocessed_grids_exposes_layer_validity(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    validity = grids["metadata"]["layer_validity"]
    assert set(validity) == set(_LAYERS)
    assert set(validity.values()) <= _VALID


def test_layer_validity_defaults_when_metadata_omits_it(tmp_path):
    """Older metadata.json files must still load, marked UNKNOWN."""
    directory = _write_fake_processed_dir(tmp_path)
    meta_path = directory / "metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    del metadata["layer_validity"]
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    grids = load_preprocessed_grids(processed_dir=str(directory))
    validity = grids["metadata"]["layer_validity"]
    assert set(validity) == set(_LAYERS)
    assert all(value == "UNKNOWN" for value in validity.values())


# ── A4: the optional Earth-visibility layer ─────────────────────────────────


def test_earth_visibility_layer_loads_when_its_cache_is_present(tmp_path):
    from app.earth_visibility import (
        EARTH_VISIBILITY_CACHE_FILENAME,
        EARTH_VISIBILITY_META_FILENAME,
    )

    directory = _write_fake_processed_dir(tmp_path)
    fraction = np.full((4, 4), 0.37, dtype=np.float32)
    np.save(directory / EARTH_VISIBILITY_CACHE_FILENAME, fraction)
    (directory / EARTH_VISIBILITY_META_FILENAME).write_text(
        json.dumps({"n_samples": 8766, "span_days": 365.25, "step_hours": 1.0}),
        encoding="utf-8",
    )

    grids = load_preprocessed_grids(processed_dir=str(directory))

    assert grids["earth_visibility"].dtype == np.float64
    np.testing.assert_allclose(grids["earth_visibility"], 0.37, rtol=1e-6)
    assert grids["metadata"]["layer_validity"]["earth_visibility"] == "DERIVED"
    assert grids["metadata"]["earth_visibility"]["n_samples"] == 8766


def test_earth_visibility_layer_is_absent_not_unknown_without_its_cache(tmp_path):
    """No cache means no layer -- not a layer of UNKNOWN provenance."""
    directory = _write_fake_processed_dir(tmp_path)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    assert "earth_visibility" not in grids
    assert "earth_visibility" not in grids["metadata"]["layer_validity"]
    assert "earth_visibility" not in grids["metadata"]


def test_earth_visibility_cache_of_the_wrong_shape_is_refused(tmp_path):
    from app.earth_visibility import EARTH_VISIBILITY_CACHE_FILENAME

    directory = _write_fake_processed_dir(tmp_path)
    np.save(directory / EARTH_VISIBILITY_CACHE_FILENAME, np.zeros((3, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="earth_visibility"):
        load_preprocessed_grids(processed_dir=str(directory))


# ── C4: the optional measured roughness and PSR layers ─────────────────────


def _roughness_meta(with_scale: bool = True) -> dict:
    meta = {"product": "LDRM_80S_50MPP_ADJ_ROUGH_100M", "baseline_m": 100, "resolution_m": 50}
    if with_scale:
        meta["scale"] = {"kind": "regional_ecdf", "knots": [0.1, 0.5, 1.0, 2.0], "probs": [0.0, 0.25, 0.75, 1.0]}
    return meta


def _write_c4_layers(directory, with_scale: bool = True, shape=(4, 4)):
    from app.roughness import (
        PSR_CACHE_FILENAME,
        PSR_META_FILENAME,
        ROUGHNESS_CACHE_FILENAME,
        ROUGHNESS_META_FILENAME,
    )

    np.save(directory / ROUGHNESS_CACHE_FILENAME, np.full(shape, 0.75, dtype=np.float32))
    (directory / ROUGHNESS_META_FILENAME).write_text(json.dumps(_roughness_meta(with_scale)), encoding="utf-8")
    psr = np.zeros(shape, dtype=np.float32)
    psr[0, 0] = 1.0
    np.save(directory / PSR_CACHE_FILENAME, psr)
    (directory / PSR_META_FILENAME).write_text(json.dumps({"product": "LPSR_80S_20MPP_ADJ"}), encoding="utf-8")


def test_roughness_and_psr_layers_load_as_measured_when_cached(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    _write_c4_layers(directory)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    assert grids["roughness"].dtype == np.float64 and grids["psr"].dtype == np.float64
    np.testing.assert_allclose(grids["roughness"], 0.75, rtol=1e-6)
    assert grids["psr"][0, 0] == 1.0 and grids["psr"].sum() == 1.0
    validity = grids["metadata"]["layer_validity"]
    assert validity["roughness"] == "MEASURED" and validity["psr"] == "MEASURED"
    assert validity["cost"] == "DERIVED"  # the weakest input still decides; roughness does not lift it
    assert grids["metadata"]["roughness"]["scale"]["knots"] == [0.1, 0.5, 1.0, 2.0]
    assert grids["metadata"]["psr"]["product"] == "LPSR_80S_20MPP_ADJ"
    assert grids["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal", "roughness"]


def test_the_loaded_cost_grid_includes_the_roughness_criterion(tmp_path):
    from app.cost_engine import compute_cost_grid
    from app.roughness import RoughnessScale

    directory = _write_fake_processed_dir(tmp_path)
    _write_c4_layers(directory)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    reference = compute_cost_grid(
        grids["slope"], grids["thermal"], grids["shadow_ratio"], 80.0, traversable=grids["traversable"],
        thermal_min_grid=grids["thermal_min"], roughness_grid=grids["roughness"],
        roughness_scale=RoughnessScale.from_meta(grids["metadata"]["roughness"]["scale"]),
    )
    assert np.array_equal(grids["cost"], reference)


def test_roughness_and_psr_are_absent_not_unknown_without_their_caches(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    grids = load_preprocessed_grids(processed_dir=str(directory))
    for name in ("roughness", "psr"):
        assert name not in grids
        assert name not in grids["metadata"]["layer_validity"]
        assert name not in grids["metadata"]
    assert grids["metadata"]["cost_criteria"] == ["slope", "energy", "shadow", "thermal"]


def test_roughness_cache_of_the_wrong_shape_is_refused(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    _write_c4_layers(directory, shape=(3, 3))
    with pytest.raises(ValueError, match="roughness"):
        load_preprocessed_grids(processed_dir=str(directory))


def test_psr_cache_of_the_wrong_shape_is_refused(tmp_path):
    from app.roughness import PSR_CACHE_FILENAME

    directory = _write_fake_processed_dir(tmp_path)
    _write_c4_layers(directory)
    np.save(directory / PSR_CACHE_FILENAME, np.zeros((3, 3), dtype=np.float32))
    with pytest.raises(ValueError, match="psr"):
        load_preprocessed_grids(processed_dir=str(directory))


def test_roughness_cache_without_its_scale_is_refused(tmp_path):
    directory = _write_fake_processed_dir(tmp_path)
    _write_c4_layers(directory, with_scale=False)
    with pytest.raises(ValueError, match="scale"):
        load_preprocessed_grids(processed_dir=str(directory))
