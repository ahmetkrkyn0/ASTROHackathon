"""The 3-D data path against the checked-in production grid.

test_terrain_api.py asserts the contract on an 8x6 fixture, where the
cell ceiling, the payload budget and the real distribution of no-data never
come near their production values. The claims this file makes -- that the
binary layer is a quarter the size of the JSON preview it replaces, that
~40 000 impassable cells arrive as NaN rather than infinity, that 425.7 m
of relief over 2.5 km wants a modest vertical exaggeration -- are claims
about THIS repository's grid, and are worth nothing on a fixture.

The grid is Site11 (de Gerlache Rim) window row=2400 col=2500, centred on
88.920 S / 287.328 E. It replaced Site01 row=0 col=700, which was measured
to be 94.7% a single tilted plane -- 1064 m of relief that rendered as a
featureless ramp because almost none of it was terrain STRUCTURE. The
window in use is 0.3% planar with five coherent impassable barriers, the
largest 8.6 hectares, so the planner has something real to route around.

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
    not os.path.exists(os.path.join(_P1_PROCESSED_DIR, "elevation_grid.npy")),
    reason="lunapath/data/processed/*.npy not present -- run the P1 pipeline first",
)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
    app.state.grids = None


def test_manifest_describes_the_production_grid(client):
    manifest = client.get("/api/terrain").json()
    assert manifest["grid"]["rows"] == 500
    assert manifest["grid"]["cols"] == 500
    assert manifest["grid"]["resolution_m"] == 5.0
    assert manifest["grid"]["span_m"] == [2500.0, 2500.0]
    assert manifest["binary_format"]["bytes_per_layer"] == 500 * 500 * 4
    assert manifest["georeference"]["crs"]
    assert manifest["georeference"]["window_offset"] == {"row": 2400, "col": 2500}


def test_exaggeration_default_follows_this_site_relief(client):
    """425.7 m of relief over a 2.5 km span is 1:5.9 -- gentler than the
    1:5 ratio at which terrain reads as terrain unaided, so the manifest
    starts the slider slightly above neutral rather than leaving the client
    to guess. (The previous window's 1064 m answered 1.0 here; that number
    was real and still rendered as a ramp, which is why relief alone was
    never the right measure of a site.)"""
    elevation = client.get("/api/terrain").json()["elevation"]
    assert elevation["relief_m"] == pytest.approx(425.7, abs=1.0)
    assert elevation["vertical_exaggeration_suggested"] == 1.5


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
    # The Site11 grid has 39 937; assert the order, not the exact figure,
    # so a legitimate re-run of the pipeline does not fail the suite.
    assert 30_000 < nan_count < 60_000
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


# -- the time-slice series ---------------------------------------------------

SERIES = "/api/illumination-series"

# The span has to cross a terminator, and at a polar site that is a question
# of DAYS, not hours. Measured on this grid: the Sun's grid azimuth sweeps
# only ~3 deg per 6 hours, while the local horizon toward azimuth 300-320 deg
# stands at ~15 deg -- so from 2026-09-01 the site sits at 0% lit for six
# straight days, and the previous 3-day query sampled nothing but that shadow.
# The illumination cycle here is ~12 days lit / ~14 days dark; this window
# starts just before the crossing and walks 0% -> 95% lit over six days,
# which is the behaviour these tests exist to pin.
#
# The lesson generalises past this file: /api/plan-4d's defaults (24 slices
# x 1 h) span a single day, over which nothing about the illumination at a
# polar site changes at all.
_QUERY = "start_utc=2026-09-07T00:00:00&n_slices=12&slice_hours=12&downsample=5"

# The same cycle twelve days on: ~96% lit down to fully dark, -55 C to the
# PSR floor. Both directions are exercised because a sign error in the
# relaxation would survive a test that only ever watched the surface warm.
_COOLING_QUERY = "start_utc=2026-09-19T00:00:00&n_slices=12&slice_hours=12&downsample=5"

_HAS_HORIZON = os.path.exists(os.path.join(_P1_PROCESSED_DIR, "horizon_map.npy"))
needs_horizon = pytest.mark.skipif(
    not _HAS_HORIZON,
    reason="horizon_map.npy not built -- run scripts/build_horizon_cache.py",
)


@needs_horizon
def test_series_is_genuinely_time_varying(client):
    """With an epoch and the horizon cube, illumination must actually move.

    This is the assertion the whole feature rests on. It is also the one
    that caught SPICE(NOLEAPSECONDS): str2et was called before the load that
    populates the kernel pool, so a cold process silently produced a frozen
    series and blamed 'real illumination unavailable'.
    """
    manifest = client.get(f"{SERIES}?{_QUERY}").json()
    assert manifest["shadow_model"]["model"] == "spice_horizon"
    assert manifest["shadow_model"]["time_varying"] is True

    cube = np.frombuffer(
        client.get(f"{SERIES}?{_QUERY}&format=f32&field=shadow").content,
        dtype=BINARY_DTYPE,
    ).reshape(12, 100, 100)
    lit = [float((cube[i] < 0.5).mean()) for i in range(12)]
    assert max(lit) - min(lit) > 0.3, f"illumination barely moves: {lit}"


@needs_horizon
def test_manifest_and_binary_report_the_same_model(client):
    """They are separate requests over process-global SPICE state. When the
    pool load depended on call order, the manifest said 'static' while the
    binary it pointed at was time-varying."""
    manifest = client.get(f"{SERIES}?{_QUERY}").json()
    entry = manifest["fields"]["shadow"]
    binary = client.get(entry["binary_url"])
    assert binary.status_code == 200
    assert int(binary.headers["X-Series-Slices"]) == manifest["slices"]
    cube = np.frombuffer(binary.content, dtype=BINARY_DTYPE).reshape(12, 100, 100)
    varying = float(np.abs(cube[-1] - cube[0]).max()) > 0.0
    assert varying == manifest["shadow_model"]["time_varying"]


def _series_means(client, query: str, field: str) -> list[float]:
    cube = np.frombuffer(
        client.get(f"{SERIES}?{query}&format=f32&field={field}").content,
        dtype=BINARY_DTYPE,
    ).reshape(12, 100, 100)
    return [float(np.nanmean(cube[i])) for i in range(12)]


@needs_horizon
def test_surface_warms_as_the_terminator_arrives(client):
    """Temperature has to follow illumination. _QUERY walks this site from
    fully shadowed into ~95% lit over six days; the surface must come up
    with it."""
    means = _series_means(client, _QUERY, "surface_temp_c")
    assert means[-1] > means[0], f"surface never warms: {means}"
    assert means[0] < -150.0, "did not start from a genuinely dark state"


@needs_horizon
def test_surface_cools_as_the_terrain_falls_into_shadow(client):
    """The other half of the same cycle, twelve days later: ~96% lit down to
    fully dark. Tested separately because a series that only ever warms
    would satisfy a direction-agnostic assertion while a sign error still
    lurked in the relaxation."""
    means = _series_means(client, _COOLING_QUERY, "surface_temp_c")
    assert means[0] > means[-1], f"surface never cools: {means}"
    assert means[-1] > -190.0, "cooled past the PSR floor"


@needs_horizon
def test_surface_lags_illumination_rather_than_tracking_it_instantly(client):
    """The regolith has thermal inertia: the surface relaxes toward each
    slice's equilibrium, it does not jump to it. Round 4 (H-3) removed the
    instant-equilibrium behaviour, and nothing pinned it afterwards.

    An instant model would dump nearly the whole temperature swing into the
    single slice where illumination flips. A lagged one spreads it across
    several, so no single step may carry most of the change.
    """
    means = _series_means(client, _COOLING_QUERY, "surface_temp_c")
    total = abs(means[-1] - means[0])
    assert total > 50.0, f"not enough swing to judge the lag: {means}"
    steps = [abs(b - a) for a, b in zip(means[:-1], means[1:])]
    assert max(steps) < 0.6 * total, (
        f"one slice carries {max(steps) / total:.0%} of the swing -- "
        f"that is an instant jump, not a lag: {means}"
    )


def test_sun_track_sweeps_azimuth_without_climbing(client):
    """The chosen window puts the Sun a degree or so above the horizon
    throughout, which is why azimuth -- not elevation -- is what moves.
    (Round 4 review, H-4.)"""
    sun = client.get(f"{SERIES}?{_QUERY}").json()["sun"]
    if not sun:
        pytest.skip("NAIF kernels unavailable")
    assert len(sun) == 12
    azimuths = [entry["azimuth_grid_deg"] for entry in sun]
    elevations = [entry["elevation_deg"] for entry in sun]
    assert max(azimuths) - min(azimuths) > 20.0
    assert all(-5.0 < e < 5.0 for e in elevations), elevations


def test_series_refuses_an_oversized_request_and_names_the_fix(client):
    response = client.get(f"{SERIES}?n_slices=100&downsample=1&format=f32&field=shadow")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "downsample=" in detail and "MiB" in detail


def test_series_working_set_budget_survives_a_high_downsample_request(client):
    """The response-size check alone passes this request: downsample=50
    shrinks the wire payload to under 1 MiB. What it does not shrink is the
    n_slices full-resolution float64 grids build_shadow_series's real
    (spice_horizon) path builds BEFORE anything downsamples -- on this
    500x500 grid, 1000 slices there is ~1.9 GiB. The working-set budget
    exists to catch exactly this, independent of downsample."""
    response = client.get(
        f"{SERIES}?n_slices=1000&downsample=50&format=f32&field=shadow"
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "MiB" in detail and "downsample does not reduce" in detail
