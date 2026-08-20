"""Thermal model adapter tests."""

from __future__ import annotations

import numpy as np
import pytest

from app.thermal_model import Heat1DModel, SyntheticModel, build_thermal_grid


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


def test_heat1d_model_declares_model_validity():
    model = Heat1DModel()
    assert model.validity == "MODEL"
    assert model.name.startswith("heat1d")


def test_heat1d_lookup_table_shape_and_bounds():
    """A (slope, aspect) temperature table covering the configured bins."""
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    model = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    table = model._lookup_table(lat_deg=-88.5)
    assert table.shape == (4, 4)
    # Lunar polar surface temperatures: PSR floors ~ -250 C, sunlit peaks < 130 C
    assert np.nanmin(table) >= -250.0
    assert np.nanmax(table) <= 130.0


def test_heat1d_binning_is_deterministic_and_covers_grid():
    """Binned lookup must map every cell and be reproducible."""
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    _, slope, aspect = _fixture_grids()
    model = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    first = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    second = build_thermal_grid(model, slope, aspect, lat_deg=-88.5)
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()
