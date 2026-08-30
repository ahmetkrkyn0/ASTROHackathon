"""The 3-D data path against the checked-in production grid.

test_terrain_api.py asserts the contract on an 8x6 fixture, where the
cell ceiling, the payload budget and the real distribution of no-data never
come near their production values. The claims this file makes -- that the
binary layer is a quarter the size of the JSON preview it replaces, that
49 525 impassable cells arrive as NaN rather than infinity, that 1063.8 m
of relief over 2.5 km needs no vertical exaggeration -- are claims about
THIS repository's grid, and are worth nothing on a fixture.

Skips entirely when the P1 pipeline has not been run, matching
test_plan_4d_real_grid.py: the `.npy` artefacts are gitignored, so a fresh
clone has no grid to assert about.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.data_loader import _P1_PROCESSED_DIR
from app.main import app
from app.terrain import BINARY_DTYPE

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(_P1_PROCESSED_DIR, "metadata.json")),
    reason="lunapath/data/processed/metadata.json not present -- run the P1 pipeline first",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_manifest_describes_the_production_grid(client):
    manifest = client.get("/api/terrain").json()
    assert manifest["grid"]["rows"] == 500
    assert manifest["grid"]["cols"] == 500
    assert manifest["grid"]["resolution_m"] == 5.0
    assert manifest["grid"]["span_m"] == [2500.0, 2500.0]
    assert manifest["binary_format"]["bytes_per_layer"] == 500 * 500 * 4
    assert manifest["georeference"]["crs"]
    assert manifest["georeference"]["window_offset"] == {"row": 0, "col": 700}


def test_true_scale_is_the_right_default_for_this_site(client):
    """1063.8 m of relief over a 2.5 km span is 1:2.35. Terrain that steep
    reads as terrain at 1:1 -- the exaggeration slider starts at neutral,
    and the manifest says so rather than leaving the client to guess."""
    elevation = client.get("/api/terrain").json()["elevation"]
    assert elevation["relief_m"] == pytest.approx(1063.8, abs=1.0)
    assert elevation["vertical_exaggeration_suggested"] == 1.0


def test_binary_lifts_the_ceiling_that_caps_the_json_preview(client):
    """250 000 cells is nearly four times MAX_LAYER_CELLS, which is why the
    frontend has always fetched this grid at downsample=2. The same field as
    float32 is 1.00 MB -- smaller than the capped JSON preview it replaces."""
    assert client.get("/api/layers/elevation?downsample=1").status_code == 422

    binary = client.get("/api/layers/elevation?format=f32&downsample=1")
    assert binary.status_code == 200
    assert int(binary.headers["X-Layer-Rows"]) == 500
    assert int(binary.headers["X-Layer-Cols"]) == 500
    assert len(binary.content) == 500 * 500 * 4

    preview = client.get("/api/layers/elevation?downsample=2")
    assert len(binary.content) < len(preview.content)


def test_impassable_cells_arrive_as_nan_not_infinity(client):
    """float32 carries an infinity perfectly well, and a colour ramp or a
    vertex position built from one fails silently."""
    binary = client.get("/api/layers/cost?format=f32")
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE)
    assert not np.isinf(values).any()
    nan_count = int(np.isnan(values).sum())
    # The round-4 grid has 49 525; assert the order, not the exact figure,
    # so a legitimate re-run of the pipeline does not fail the suite.
    assert 40_000 < nan_count < 60_000
    assert int(binary.headers["X-Layer-Nodata"]) == nan_count


def test_binary_and_json_agree_on_the_real_grid(client):
    down = 4
    payload = client.get(f"/api/layers/slope?downsample={down}").json()
    binary = client.get(f"/api/layers/slope?format=f32&downsample={down}")
    rows, cols = payload["shape"]
    values = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(rows, cols)
    expected = np.array(
        [[np.nan if v is None else v for v in row] for row in payload["data"]],
        dtype=np.float32,
    )
    np.testing.assert_allclose(values, expected, rtol=1e-6, equal_nan=True)
    assert float(binary.headers["X-Layer-Resolution-M"]) == pytest.approx(20.0)


def test_every_manifest_url_serves_the_full_grid(client):
    manifest = client.get("/api/terrain").json()
    for name, entry in manifest["layers"].items():
        response = client.get(entry["binary_url"])
        assert response.status_code == 200, name
        assert len(response.content) == 500 * 500 * 4, name
