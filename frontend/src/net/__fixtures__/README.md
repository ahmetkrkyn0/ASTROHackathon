# Captured backend responses

Real responses from a running backend, saved verbatim. Not written by hand and
not derived from the contract document.

The rule they exist to enforce is that no field name is ever guessed. The
contract says a response carries `time_to_safe_haven`; only a captured response
proves whether it also carries `time_to_haven_finite_fraction`, whether an
unreachable cell arrives as `null` or `NaN`, and whether `cost_breakdown.total`
can be null. Every one of those was different from what reading the document
alone would have suggested.

## How they were captured

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file ../.env
```

Then each endpoint was requested and its response written here. Absolute paths
were replaced with `<repo>` -- the only edit made to any of these files, and
only because `horizon_cache` otherwise embeds one developer's drive layout.

Grid window at capture time: `window_offset {row: 1500, col: 1000}`, 500x500 at
5 m/px, `cost_model: weighted_cell_cost_shadow_aware_energy_slip_roughness_v5`.
Layer fixtures use `downsample=50` to stay small; the JSON shape is identical at
any downsample.

## Which endpoints answered, and which did not

Captured in two passes on the same machine. The first was before
`scripts/build_roughness_cache.py` and `build_dem_clone_cache.py` had run, and
is what the `.unavailable` fixtures are. The second, after
`scripts/setup_caches.py` completed all eight steps, is everything marked
available. Every A-track endpoint answers 200 with data in that second state.

| Endpoint | State | Fixture |
|---|---|---|
| `GET /api/terrain` | available, 11 layers | `terrain.available.json` |
| `GET /api/cell-telemetry` | available | `cell-telemetry.available.json` |
| `GET /api/cell-telemetry?start_utc=` | available, safe-haven block filled | `cell-telemetry.safe-haven.json` |
| `GET /api/layers/roughness` | available | `layers-roughness.available.json` |
| `GET /api/layers/psr` | available | `layers-psr.available.json` |
| `GET /api/layers/earth_visibility` | available | `layers-earth_visibility.available.json` |
| `GET /api/earth-series` | available, `spice_horizon` | `earth-series.available.json` |
| `GET /api/comm-window` | available | `comm-window.available.json` |
| `GET /api/safe-haven` | available, `spice_horizon` | `safe-haven.available.json` |
| `GET /api/psr-validation` | available | `psr-validation.available.json` |
| `GET /api/illumination-corridor` | available | `illumination-corridor.available.json` |
| `GET /api/thermal-dwell` | available | `thermal-dwell.available.json` |
| `POST /api/plan` | available | `plan.available.json` |
| `GET /api/uncertainty-series` | **unavailable** at capture -- no `dem_clone_horizons.npy` | `uncertainty-series.unavailable.json` |
| `GET /api/thermal-envelope` | **unavailable** at capture -- no envelope cache (422) | `thermal-envelope.422.json` |
| `GET /api/survival` | needs `goal_row`/`goal_col` (422) | `survival.422-missing-goal.json` |
| `GET /api/survival` with an untraversable goal | mission-infeasible (422) | `survival.422-untraversable-goal.json` |

The three `.unavailable.json` files for roughness and PSR were captured
**before** `scripts/build_roughness_cache.py` had run, so the same endpoint
appears here in both states. That pair is what the absence tests are written
against.

## Four things the fixtures settle that the contract did not

**`uncertainty-series` answers 200, not 404, when it has nothing.** The body
carries `{"model": "unavailable", "reason": ...}` alongside a real `slices` and
`start_utc`. A caller that only checks `response.ok` concludes it has data. This
is why `capabilityFromModel` exists.

**422 covers three unrelated situations.** A missing required parameter
(`survival.422-missing-goal`), a genuinely infeasible request
(`survival.422-untraversable-goal`), and a missing cache
(`thermal-envelope.422`). The status alone cannot tell them apart, which is the
argument for `net/errors.ts` in one file.

**`cost_breakdown` values can be null, and null is not missing data.** On a cell
outside the requested rover's slope limit, `slope`, `energy` and `total` come
back null while `shadow`, `thermal` and `roughness` carry numbers. Null there
means an *infinite* contribution -- the cell is impassable -- because Starlette
serialises with `allow_nan=False` and `costmap.explain()` maps inf to null. A
breakdown chart that renders those as zero states the exact opposite of the
truth: it draws the cheapest possible cell where the backend said impassable.

**`time_to_safe_haven` has two different nodata representations in one
response.** The manifest's `fields.time_to_safe_haven.nodata` is `179976` -- a
*count* of nodata cells, not a sentinel value. The values themselves arrive as
`NaN` in the f32 payload (`binary_format.nodata: "NaN"`), and in
`cell-telemetry` the same fact arrives as `time_to_safe_haven_h: null`. Three
encodings, one meaning: no reachable Safe Haven. None of them is zero hours.

## What the binary payloads settle

Verified against `GET /api/safe-haven?...&field=time_to_safe_haven&downsample=2`
on the built caches, 250x250 at 10 m:

```
X-Layer-Nodata: 20236        exactly the number of NaN values in the payload
NaN cells:      20236 (32.4%)  no reachable safe haven
exact zeros:    1023           cells that ARE havens
finite range:   0.000 .. 39.314 h
```

The header is a count and the payload's sentinel is NaN -- two different things
that both say "nodata", and the manifest's `binary_format.nodata: "NaN"` is the
one that identifies a value. Coercing NaN to zero would merge 20 236 cells with
no reachable haven into the 1 023 that are havens, and the map would claim a
third of the site is safe. That is why `fieldValues` converts NaN to `null` and
the renderer leaves null unpainted.
