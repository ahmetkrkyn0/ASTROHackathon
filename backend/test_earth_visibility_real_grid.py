"""Direct-to-Earth visibility on the checked-in production grid.

test_earth_visibility.py pins the geometry and the wiring on synthetic
grids with a scripted Earth. This file asks the real question -- with NAIF
kernels, the real horizon cube and the Site11 window, does the field behave
like the Moon's south pole -- and skips, rather than fails, wherever the
gitignored inputs (kernels, horizon_map.npy, the processed grids) are not on
disk. Mirrors test_terrain_real_grid.py's split.
"""

from __future__ import annotations

import json
import os
import pathlib

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.data_loader import _P1_PROCESSED_DIR, load_preprocessed_grids
from app.earth_visibility import (
    EARTH_VISIBILITY_CACHE_FILENAME,
    build_earth_visibility_series,
    comm_window_from_metadata,
    earth_track_for_series,
)
from app.main import app
from app.terrain import BINARY_DTYPE

_KERNELS = pathlib.Path(__file__).resolve().parent.parent / "kernels" / "lunapath.tm"
_HORIZON = os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy")
_EARTH_LAYER = os.path.join(_P1_PROCESSED_DIR, EARTH_VISIBILITY_CACHE_FILENAME)
_METADATA = os.path.join(_P1_PROCESSED_DIR, "metadata.json")

needs_real_inputs = pytest.mark.skipif(
    not (_KERNELS.exists() and os.path.exists(_HORIZON) and os.path.exists(_METADATA)),
    reason="NAIF kernels, horizon_map.npy or the processed grids are not on disk",
)
needs_earth_layer = pytest.mark.skipif(
    not os.path.exists(_EARTH_LAYER),
    reason="earth_visibility_grid.npy not built -- run scripts/build_earth_visibility_cache.py",
)

# One libration cycle at daily steps. The Earth's elevation at the pole
# swings through its full +/-7 deg range in ~27 days, so this window
# contains both the best and the worst link geometry the site ever sees.
_START = "2026-09-07T00:00:00"
_DAYS = 28


@pytest.fixture(scope="module")
def grids():
    return load_preprocessed_grids()


@pytest.fixture()
def client(grids):
    previous = getattr(app.state, "grids", None)
    with TestClient(app) as test_client:
        app.state.grids = grids
        yield test_client
    app.state.grids = previous


@needs_real_inputs
def test_the_earth_stays_within_the_libration_band(grids):
    """Optical libration in latitude is +/-6.9 deg; at a site half a degree
    off the pole the Earth's elevation cannot leave roughly +/-8 deg. A
    value outside that band is a frame error, not astronomy."""
    track = earth_track_for_series(grids["metadata"], _DAYS, 24.0, _START)
    elevations = [entry["elevation_deg"] for entry in track]
    assert -8.5 < min(elevations) < -3.0, elevations
    assert 3.0 < max(elevations) < 8.5, elevations
    # And it actually moves: one cycle spans most of the band.
    assert max(elevations) - min(elevations) > 8.0


@needs_real_inputs
def test_the_series_has_both_linked_and_unlinked_slices(grids):
    series, provenance = build_earth_visibility_series(
        None, grids["metadata"], _DAYS, 24.0, _START
    )
    assert provenance["model"] == "spice_horizon"
    linked = [float(np.mean(snapshot)) for snapshot in series]
    # At the Earth's high point most of the window has a link; at its low
    # point, below the horizontal, the plain does not and only cells with a
    # negative far horizon keep it.
    assert max(linked) > 0.5, linked
    assert min(linked) < max(linked) - 0.2, linked


@needs_real_inputs
def test_comm_window_agrees_with_the_series_at_the_window_centre(grids):
    metadata = grids["metadata"]
    rows, cols = metadata["shape"]
    row, col = int(rows) // 2, int(cols) // 2
    series, _ = build_earth_visibility_series(None, metadata, _DAYS, 24.0, _START)
    from datetime import datetime, timedelta

    start = datetime.fromisoformat(_START)
    for day in (0, 7, 14, 21):
        utc = (start + timedelta(days=day)).strftime("%Y-%m-%dT%H:%M:%S")
        window = comm_window_from_metadata(metadata, row, col, utc, step_minutes=60.0)
        assert window is not None
        assert window["visible_now"] == bool(series[day][row, col] > 0.5), (day, window)
        assert window["trigger_minutes_remaining"] >= 0.0
        if window["visible_now"]:
            assert window["minutes_remaining"] is None or window["minutes_remaining"] > 0
        else:
            assert window["trigger_minutes_remaining"] == 0.0


@needs_real_inputs
@needs_earth_layer
def test_the_long_run_layer_is_loaded_and_plausible(grids):
    layer = grids["earth_visibility"]
    assert layer.shape == tuple(grids["metadata"]["shape"])
    assert grids["metadata"]["layer_validity"]["earth_visibility"] == "DERIVED"
    mean = float(np.nanmean(layer))
    # The Earth is above the horizontal ~56% of the time at the pole; a
    # site's long-run fraction sits within a broad band of that -- higher
    # where the far horizon is negative, lower behind a ridge. Anything
    # outside (0.1, 0.95) means a broken horizon or frame, not a site.
    assert 0.1 < mean < 0.95, mean
    assert float(np.nanmin(layer)) >= 0.0 and float(np.nanmax(layer)) <= 1.0
    provenance = grids["metadata"]["earth_visibility"]
    assert provenance["n_samples"] > 1000
    assert provenance["model"] == "spice_horizon"


@needs_real_inputs
@needs_earth_layer
def test_the_layer_is_published_to_the_scene(client):
    manifest = client.get("/api/terrain").json()
    entry = manifest["layers"]["earth_visibility"]
    assert entry["validity"] == "DERIVED"
    values = np.frombuffer(client.get(entry["binary_url"]).content, dtype=BINARY_DTYPE)
    assert values.size == manifest["grid"]["cells"]
    assert float(np.nanmax(values)) <= 1.0


@needs_real_inputs
def test_earth_series_endpoint_is_time_varying_on_the_real_grid(client):
    query = f"start_utc={_START}&n_slices={_DAYS}&slice_hours=24&downsample=5"
    manifest = client.get(f"/api/earth-series?{query}").json()
    assert manifest["earth_model"]["model"] == "spice_horizon"
    fractions = [entry["visible_fraction"] for entry in manifest["earth"]]
    assert len(fractions) == _DAYS
    assert max(fractions) - min(fractions) > 0.2, fractions
    cube = np.frombuffer(
        client.get(manifest["fields"]["earth_visible"]["binary_url"]).content,
        dtype=BINARY_DTYPE,
    ).reshape(_DAYS, 100, 100)
    # visible_fraction is computed on the full grid; the binary is the
    # decimated one, so the two agree to within the sampling, not exactly.
    means = [float(np.nanmean(cube[i])) for i in range(_DAYS)]
    assert means == pytest.approx(fractions, abs=0.02)


def _linked_pair(grids, linked_fine: np.ndarray, coarsen: int = 4):
    """A start/goal pair, in fine pixels, that a link-respecting route can
    join: both coarse cells (and every cell of some route between them)
    are traversable AND have the Earth in view. Chosen from the data
    because on this site the long-run visibility is only ~0.28 -- most
    cells never see the Earth, so a pair picked for terrain alone has no
    legal route under the rule however high the Earth stands."""
    from app.constants import get_rover
    from app.cost_cube import coarsen_grid, coarsen_traversable
    from app.pathfinder_4d import gated_move_count
    from app.rover_grids import grids_for_rover

    rover = get_rover("lpr_1")
    for_rover = grids_for_rover(grids, "lpr_1")
    passable = coarsen_traversable(
        np.asarray(for_rover["traversable"], dtype=bool) & linked_fine, coarsen
    )
    elevation = coarsen_grid(for_rover["elevation"], coarsen, how="center")
    resolution_m = float(grids["metadata"]["resolution_m"]) * coarsen
    cells = np.argwhere(passable)
    rng = np.random.default_rng(11)
    best = None
    for _ in range(300):
        a = tuple(int(v) for v in cells[rng.integers(len(cells))])
        b = tuple(int(v) for v in cells[rng.integers(len(cells))])
        moves = gated_move_count(passable, a, b, elevation, resolution_m, rover)
        if moves is not None and moves >= 15 and (best is None or moves > best[2]):
            best = (a, b, moves)
    assert best is not None, "no link-respecting pair of at least 15 moves on this grid"
    offset = coarsen // 2
    to_fine = lambda cell: {"row": cell[0] * coarsen + offset, "col": cell[1] * coarsen + offset}
    return to_fine(best[0]), to_fine(best[1]), best[2]


@needs_real_inputs
def test_plan_4d_enforces_the_link_on_the_real_grid(client):
    """The VIPER rule on real terrain. Between two cells that see the Earth
    at its high point, and are joined by cells that do, the constrained
    plan succeeds with every state in view. The same pair at the Earth's
    low point either still succeeds with no move out of view (a negative
    far horizon keeps the link) or is refused for the stated reason --
    never silently unconstrained."""
    grids = app.state.grids
    metadata = grids["metadata"]
    track = earth_track_for_series(metadata, _DAYS, 24.0, _START)
    high_index = max(range(_DAYS), key=lambda i: track[i]["elevation_deg"])
    low_index = min(range(_DAYS), key=lambda i: track[i]["elevation_deg"])
    high = track[high_index]["utc"].rstrip("Z")
    low = track[low_index]["utc"].rstrip("Z")
    series, _ = build_earth_visibility_series(None, metadata, _DAYS, 24.0, _START)
    start, goal, moves = _linked_pair(grids, np.asarray(series[high_index]) > 0.5)

    body = {
        "start": start,
        "goal": goal,
        "rover_id": "lpr_1",
        "n_slices": 256,
        "coarsen": 4,
        "require_earth_visibility": True,
    }

    response = client.post("/api/plan-4d", json={**body, "start_utc": high})
    assert response.status_code == 200, (moves, response.text)
    payload = response.json()
    assert payload["earth_model"]["model"] == "spice_horizon"
    assert payload["metrics"]["earth_visibility_enforced"] is True
    assert payload["metrics"]["moves_out_of_earth_view"] == 0
    assert all(payload["path_earth_visible"])
    assert payload["metrics"]["move_steps"] >= moves

    response = client.post("/api/plan-4d", json={**body, "start_utc": low})
    if response.status_code == 200:
        assert response.json()["metrics"]["moves_out_of_earth_view"] == 0
    else:
        assert response.status_code == 404
        assert "Earth visibility" in response.json()["detail"]
