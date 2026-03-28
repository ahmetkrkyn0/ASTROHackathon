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

# Visualize processed grids (requires process_lunar_data.py to have run first)
python test_visualize.py
python visualize_processed_data.py

# Backend (not yet scaffolded)
cd backend
uvicorn main:app --reload --port 8000

# Backend tests
pytest

# Frontend (not yet scaffolded)
cd frontend
npm install && npm run dev
npm run lint && npm run typecheck
```

---

## Current State

**Phase 1 (P1) is complete.** Raw NASA 80MPP GeoTIFF files are processed into five 500×500 numpy arrays saved under `lunapath/data/processed/`:

| File | Description |
|---|---|
| `elevation_grid.npy` | Elevation in metres (float64) |
| `slope_grid.npy` | Slope in degrees via `np.gradient` (float64) |
| `aspect_grid.npy` | Aspect/slope direction 0-360 deg (float64) |
| `shadow_ratio_grid.npy` | Elevation-based shadow proxy [0,1] (float64) |
| `thermal_grid.npy` | Synthetic surface temperature in Celsius (float64) |
| `traversability_grid.npy` | Binary passability mask: 0=blocked, 1=passable (float64) |
| `metadata.json` | Origin, resolution, CRS, window offset, grid list |

Raw input file expected in `lunapath/data/raw/`:
- `LDEM_80S_80MPP_ADJ.tiff` — elevation DEM (single file, LDSM/HILL no longer required)

Phases 2–6 (path planner, thermal model, replanning, FastAPI, React) are **not yet scaffolded**.

---

## Directory Layout

```
lunapath/
  src/
    process_lunar_data.py   # P1 main — reads GeoTIFFs, writes .npy + metadata
    utils.py                # pixel_to_geo, geo_to_pixel, save_metadata, report_*
    test_visualize.py       # 2×2 subplot validation: elevation, slope, PSR, traversability
    visualize_processed_data.py  # Dark-themed environment dashboard
  data/
    raw/                    # NASA GeoTIFF input files (gitignored)
    processed/              # Output .npy arrays + metadata.json + PNG plots
  requirements.txt          # rasterio, numpy, matplotlib, scipy
docs/
  lunapath_referans_belgesi_2.md  # v2.0 authoritative math reference
```

Planned layout for upcoming phases:

```
backend/
  main.py                   # FastAPI entrypoint
  modules/
    constants.py            # LPR-1 rover constants (see §2.1 of ref doc)
    data_layer.py           # Loads processed .npy files, exposes grid dict
    path_planner.py         # Multi-criteria A* with heapq
    thermal_model.py        # Per-cell thermal risk scoring
    replanning_manager.py   # Event-triggered replan
  rover_profiles/           # JSON rover thermal profiles
frontend/
  src/components/
    MapView.tsx
    ControlPanel.tsx
    MetricsPanel.tsx
    EventLog.tsx
    ScenarioSelector.tsx
    ComparisonView.tsx
data/
  scenarios/                # Demo scenario JSON files
```

---

## Architecture

### P1 — Data Layer (`lunapath/src/`)

`process_lunar_data.py` selects the most "actionable" 500×500 window from the full raster by scoring candidate windows on `elevation_range × slope_variance`. All downstream modules consume the five `.npy` outputs.

`utils.py` provides coordinate transforms: `pixel_to_geo(row, col, transform)` uses the affine matrix with +0.5 pixel-centre offset. Internal coordinates are always `(row, col)`; geographic `(x, y)` only in metadata/API.

### P2 — Multi-Criteria A* (planned: `backend/modules/path_planner.py`)

Cost function (finalized, do not change):
```
C(a→b) = w₁·f_slope(θ) + w₂·f_energy(θ,d) + w₃·f_shadow(H) + w₄·f_thermal(T) + J_penalty

If θ > 25° → C = INF (impassable hard block)
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
- Heuristic uses only the distance component (`w₁ × euclidean`) to remain admissible.
- Do not use `networkx` — use `heapq` with a custom implementation.

### P3 — Thermal Model (planned: `backend/modules/thermal_model.py`)

Double-sigmoid thermal penalty using LPR-1 constants. Surface temperature → internal temperature via offset model (cold: +60°C, hot: -40°C). Battery (60%) + electronics (40%) weighted composite risk. See §2.3.4 of the reference doc for exact formulas.

### P4 — Replanning Manager (planned: `backend/modules/replanning_manager.py`)

Event-triggered, not continuous. Trigger types: `thermal_spike`, `new_obstacle`, `energy_budget`. Replans from trigger node to goal, outputs old/new segment diff with metrics delta.

### P5 — FastAPI Backend (planned: `backend/main.py`)

```
POST /api/plan              # initial route
POST /api/replan            # event-triggered replan
POST /api/compare           # safe vs. short comparison
GET  /api/layers            # serialized grid metadata for map rendering
GET  /api/scenarios         # demo scenario list
POST /api/scenarios/{id}/apply
```

Requires CORS middleware for the React frontend.

### P6 — Frontend

Map renders backend grid via canvas layer or GeoJSON overlay — not a standard tile layer. Weight sliders control `w_slope`, `w_energy`, `w_shadow`, `w_thermal` (range 0.0–2.0).

---

## Key Constraints

- All math constants are **frozen** at v3.2 values. Do not adjust without explicit instruction.
- `SLOPE_MAX_DEG = 25` — hard impassable threshold (not 35°).
- PSR mask is a static elevation+slope proxy, not physics-based shadow calculation.
- Temperature data is synthetic/modelled — no real-time feed.
- ML component is out of scope unless time permits.
- Grid coordinates are `(row, col)` internally; geographic only in API responses.
- Weights are user-adjustable via frontend sliders; AHP defaults are the starting point.

---

## Reference Rover: LPR-1 Constants

These go in `backend/modules/constants.py` exactly as specified in §2.1 of the reference doc. Key values:

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
