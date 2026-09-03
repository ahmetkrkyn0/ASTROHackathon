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
