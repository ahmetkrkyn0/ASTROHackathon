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
