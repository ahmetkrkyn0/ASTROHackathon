"""Thermal model adapter tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.thermal_model import SyntheticModel, build_thermal_grid


def _fixture_grids():
    rng = np.random.default_rng(42)
    elevation = rng.uniform(-500.0, 500.0, size=(8, 8))
    slope = rng.uniform(0.0, 20.0, size=(8, 8))
    aspect = rng.uniform(0.0, 360.0, size=(8, 8))
    return elevation, slope, aspect


def test_synthetic_model_declares_synthetic_validity():
    elevation, _, _ = _fixture_grids()
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    assert model.validity == "SYNTHETIC"
    assert model.name == "synthetic-elevation-aspect"


def test_build_thermal_grid_returns_celsius_float32_of_matching_shape():
    elevation, slope, aspect = _fixture_grids()
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    out = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert out.shape == slope.shape
    assert out.dtype == np.float32
    # Lunar south-pole surface temperatures live well inside this envelope.
    assert np.nanmin(out) >= -250.0
    assert np.nanmax(out) <= 130.0


def test_synthetic_model_matches_legacy_generate_thermal_grid():
    """The adapter must not change existing numbers."""
    from app.thermal_grid import generate_thermal_grid

    elevation, slope, aspect = _fixture_grids()
    legacy = generate_thermal_grid(elevation, slope, aspect, 80.0)
    model = SyntheticModel(elevation=elevation, resolution_m=80.0)
    adapted = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert np.allclose(legacy, adapted, equal_nan=True)
