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


def test_heat1d_lookup_table_reflects_slope_and_aspect_physics():
    """The table must encode real solar geometry, not just its own clip range.

    A bounds-only check (nanmin >= -250, nanmax <= 130) can never fail:
    ``_lookup_table`` clips to exactly that range before returning, so a
    latitude-units bug (e.g. degrees passed where radians are expected,
    producing an absurd equatorial-like peak) would sail through undetected.
    Assert physical ordering instead. At this south-polar latitude the sun
    sits almost exactly on the horizon all year, so:
    - flat ground (slope=0) sees perpetual grazing incidence and is the
      coldest cell in the table;
    - any slope tilted toward the sun's best azimuth of the year gets a much
      higher local incidence angle than flat, so every sloped cell must be
      warmer than flat;
    - a steep sun-facing slope (aspect 0 deg) must be warmer than an equally
      steep pole-facing slope (aspect 180 deg).
    """
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    model = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    table = model._lookup_table(lat_deg=-88.5)
    assert table.shape == (4, 4)
    assert np.isfinite(table).all()

    # slopes = [0, 10, 20, 30] deg (rows); aspects = [0, 90, 180, 270] deg (cols)
    flat = table[0, 0]
    steep_sun_facing = table[-1, 0]  # aspect 0 deg
    steep_pole_facing = table[-1, 2]  # aspect 180 deg

    assert np.all(table[1:, :] > flat), (
        "every sloped cell must be warmer than perpetually grazing flat ground"
    )
    assert steep_sun_facing > steep_pole_facing, (
        "a sun-facing slope must be warmer than an equally steep pole-facing slope"
    )
    assert steep_sun_facing == np.max(table), (
        "the steepest sun-facing cell should be the table's warmest"
    )


def test_heat1d_binning_is_deterministic_and_covers_grid():
    """Binned lookup must map every cell and be reproducible.

    Uses two separate, uncached ``Heat1DModel`` instances rather than
    calling the same instance twice: a single-instance repeat would just
    hit ``self._cache`` on the second call and trivially return the same
    array object, which cannot detect solver nondeterminism.
    """
    if not Heat1DModel.available():
        pytest.skip("heat1d not installed in this environment")
    _, slope, aspect = _fixture_grids()
    model_a = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    model_b = Heat1DModel(n_slope_bins=4, n_aspect_bins=4)
    first = build_thermal_grid(model_a, slope, aspect, lat_deg=-88.5)
    second = build_thermal_grid(model_b, slope, aspect, lat_deg=-88.5)
    assert np.array_equal(first, second)
    assert np.isfinite(first).all()
