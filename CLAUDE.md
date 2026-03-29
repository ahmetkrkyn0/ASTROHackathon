# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: LunaPath

Adaptive route planning system for autonomous lunar rovers that optimizes for thermal safety and energy efficiency. The system uses a multi-criteria weighted A* algorithm over pre-loaded environmental layers (DEM, slope, thermal risk, PSR masks). The core claim: a "longer but thermally safe" route is demonstrably better than the "shortest but risky" route.

Authoritative technical reference (math finalized): `docs/lunapath_referans_belgesi_2.md` — all constants, formulas, and weights come from here. Do not deviate from values in that document.

---

## Stack

| Layer | Technology |
|---|---|
| Data pipeline (P1) | Python, rasterio, numpy, scipy, matplotlib |
| Backend API (P2–P5) | Python, FastAPI, uvicorn |
| Core engine (P2) | Python, numpy, heapq (custom A*) |
| Frontend (P6) | React, Leaflet.js or deck.gl, Chart.js, Tailwind CSS |

---

## Commands

```bash
# Install dependencies
cd lunapath
pip install -r requirements.txt

# Phase 1 — Process raw NASA GeoTIFF files into grid arrays
cd lunapath/src
python process_lunar_data.py

# Unit tests for grid logic (no DEM file needed)
cd lunapath/src
python test_grid_logic.py

# Visualize processed grids (requires process_lunar_data.py to have run first)
python test_visualize.py
python visualize_processed_data.py

# Backend server
cd backend
uvicorn app.main:app --reload --port 8000

# Backend tests
cd backend
python test_cost_engine.py
python test_traversability.py
python test_weighted_integration.py

# Frontend (not yet scaffolded)
cd frontend
npm install && npm run dev
npm run lint && npm run typecheck
```

---

## Current State

**Phase 1 (P1) is complete.** Raw NASA 80MPP GeoTIFF files are processed into seven 500x500 numpy arrays saved under `lunapath/data/processed/`:

| File | Description |
|---|---|
| `elevation_grid.npy` | Elevation in metres (float64) |
| `slope_grid.npy` | Slope in degrees via `np.gradient` (float64) |
| `aspect_grid.npy` | Aspect/slope direction 0-360 deg (float64) |
| `shadow_ratio_grid.npy` | Elevation-based shadow proxy [0,1] (float64) |
| `thermal_grid.npy` | Synthetic surface temperature in Celsius (float64) |
| `traversability_grid.npy` | Binary passability mask: 0=blocked, 1=passable (float64) |
| `cost_grid.npy` | Weighted cell-level cost without log-barrier (float64) |
| `metadata.json` | Origin, resolution, CRS, window offset, grid list, cost weights |

Raw input file expected in `lunapath/data/raw/`:
- `LDEM_80S_80MPP_ADJ.tiff` — elevation DEM (single file, LDSM/HILL no longer required)

**Backend (P2–P5) is integrated with P1.** Constants, cost engine (all penalty functions), thermal grid (single source of truth), traversability module, data loader (supports both P1 .npy loading and raw DEM processing), pathfinder (A*), scenarios (4 mission profiles), and FastAPI endpoints are implemented.

**Single pipeline:** P1 generates .npy grids -> backend loads them via `POST /api/load-preprocessed` -> pathfinder/scenarios/API all work on the same data. No duplicate pipelines.

**Canonical modules:** `thermal_grid.py`, `traversability.py`, and `cost_engine.py` in `backend/app/` are the single source of truth. Both P1 and backend delegate to these.

---

## Directory Layout

```
lunapath/
  src/
    process_lunar_data.py   # P1 main — reads GeoTIFFs, writes .npy + metadata
    utils.py                # pixel_to_geo, geo_to_pixel coordinate transforms
    test_visualize.py       # 2x3 subplot validation: all 6 grids + consistency checks
    visualize_processed_data.py  # Dark-themed 6-panel environment dashboard
    test_grid_logic.py      # Unit tests for grid computations (no DEM required)
  data/
    raw/                    # NASA GeoTIFF input files (gitignored)
    processed/              # Output .npy arrays + metadata.json + PNG plots
  requirements.txt          # rasterio, numpy, matplotlib, scipy
docs/
  lunapath_referans_belgesi_2.md  # v2.0 authoritative math reference
```

Backend:

```
backend/
  app/
    __init__.py
    main.py                 # FastAPI entrypoint (all endpoints)
    constants.py            # LPR-1 rover constants (v3.2, frozen)
    cost_engine.py          # f_slope, f_energy, f_shadow, f_thermal, log_barrier, total_edge_cost
    data_loader.py          # P1 .npy loader + DEM pipeline with .npy caching
    thermal_grid.py         # Synthetic thermal grid generation (single source of truth)
    traversability.py       # Canonical traversability logic (single source of truth)
    pathfinder.py           # Multi-criteria A* with heapq (8-directional)
    scenarios.py            # 4 mission profiles (v3.2 frozen weights) + scenario JSON loading
  data/
    dem/                    # Optional: raw DEM files for direct processing
    cache/                  # Cached preprocessed grids
    scenarios/              # Demo scenario JSON files
  test_cost_engine.py       # Cost engine accuracy tests vs v3.2 spec
  test_traversability.py    # Traversability hard-block rule tests
  test_weighted_integration.py  # Integration tests: cost grids + planner weight sensitivity
  requirements.txt
```

Planned (not yet scaffolded):

```
backend/app/
    replanning_manager.py   # Event-triggered replan
frontend/
  src/components/
    MapView.tsx
    ControlPanel.tsx
    MetricsPanel.tsx
    EventLog.tsx
    ScenarioSelector.tsx
    ComparisonView.tsx
```

---

## Architecture

### P1 — Data Layer (`lunapath/src/`)

`process_lunar_data.py` selects the most "actionable" 500x500 window from the full raster by scoring candidate windows on `elevation_range x slope_variance`. All downstream modules consume the seven `.npy` outputs.

`utils.py` provides coordinate transforms: `pixel_to_geo(row, col, transform)` uses the affine matrix with +0.5 pixel-centre offset. Internal coordinates are always `(row, col)`; geographic `(x, y)` only in metadata/API.

Traversability is computed by `backend/app/traversability.py` (single source of truth). Thermal grid is computed by `backend/app/thermal_grid.py` (single source of truth). Cost grid is computed by `backend/app/cost_engine.py`. `process_lunar_data.py` delegates to all three — do not duplicate logic.

### P2 — Multi-Criteria A* (`backend/app/pathfinder.py`)

Cost function (finalized, do not change):
```
C(a->b) = w1*f_slope(t) + w2*f_energy(t,d) + w3*f_shadow(H) + w4*f_thermal(T) + J_penalty

If t > 25 deg -> C = INF (impassable hard block)
```

AHP default weights (v3.2, gradient-derived):
```python
W_SLOPE   = 0.409
W_ENERGY  = 0.259
W_SHADOW  = 0.142
W_THERMAL = 0.190
```

- `f_slope` and `f_energy` are **edge-based** (depend on transition between two nodes).
- `f_shadow` and `f_thermal` are **node-based** (depend on destination node properties).
- All penalty functions return values in MRU [0,1].
- Heuristic: `w_slope * 0.018 * euclidean_distance` (admissible, ref doc compliant).
- Do not use `networkx` — use `heapq` with a custom implementation.

### P3 — Thermal Model (`backend/app/thermal_grid.py`)

Double-sigmoid thermal penalty using LPR-1 constants. Surface temperature -> internal temperature via offset model (cold: +60C, hot: -40C). Battery (60%) + electronics (40%) weighted composite risk. See 2.3.4 of the reference doc for exact formulas.

### P4 — Replanning Manager (planned: `backend/app/replanning_manager.py`)

Event-triggered, not continuous. Trigger types: `thermal_spike`, `new_obstacle`, `energy_budget`. Replans from trigger node to goal, outputs old/new segment diff with metrics delta.

### P5 — FastAPI Backend (`backend/app/main.py`)

```
POST /api/load-preprocessed # Load P1 .npy grids (preferred)
POST /api/load-dem          # Load raw DEM and process
POST /api/plan              # Single profile route
POST /api/plan-multi        # Multiple profiles
POST /api/compare           # All 4 profiles + comparison
GET  /api/layers/{name}     # Grid layer data (with optional downsample)
GET  /api/profiles          # List mission profiles
GET  /api/scenarios         # Demo scenario list
POST /api/scenarios/{id}/load
GET  /api/health
```

Requires CORS middleware for the React frontend.

### Mission Profiles (v3.2 frozen)

| Profile | w_slope | w_energy | w_shadow | w_thermal |
|---|---|---|---|---|
| balanced | 0.409 | 0.259 | 0.142 | 0.190 |
| energy_saver | 0.250 | 0.450 | 0.150 | 0.150 |
| fast_recon | 0.500 | 0.150 | 0.100 | 0.250 |
| shadow_traverse | 0.200 | 0.150 | 0.300 | 0.350 |

### P6 — Frontend

Map renders backend grid via canvas layer or GeoJSON overlay — not a standard tile layer. Weight sliders control `w_slope`, `w_energy`, `w_shadow`, `w_thermal` (range 0.0-2.0).

---

## Key Constraints

- All math constants are **frozen** at v3.2 values. Do not adjust without explicit instruction.
- `SLOPE_MAX_DEG = 25` — hard impassable threshold (not 35 deg).
- PSR mask is a static elevation+slope proxy, not physics-based shadow calculation.
- Temperature data is synthetic/modelled — no real-time feed.
- ML component is out of scope unless time permits.
- Grid coordinates are `(row, col)` internally; geographic only in API responses.
- Weights are user-adjustable via frontend sliders; AHP defaults are the starting point.
- Traversability hard blocks: `slope > 25 deg` OR `thermal < -150C` -> cell impassable (binary mask, not continuous).
- Grid resolution is 80m (DEM native). `DEFAULT_TARGET_RESOLUTION_M = 80` in constants.py.

---

## Reference Rover: LPR-1 Constants

These are in `backend/app/constants.py` exactly as specified in 2.1 of the reference doc. Key values:

```python
ROVER_MASS_KG = 450
V_MAX_MS = 0.2
E_CAP_WH = 5420
SLOPE_MAX_DEG = 25          # hard impassable limit
SLOPE_COMFORTABLE_DEG = 15
F_NET_N = 210
MU_COEFF = 3.471
H_MAX_SHADOW_H = 50
LOG_BARRIER_MU = 0.1
```
