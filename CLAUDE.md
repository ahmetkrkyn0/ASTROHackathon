# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: LunaPath

Adaptive route planning system for autonomous lunar rovers that optimizes for thermal safety and energy efficiency. The system uses a multi-criteria weighted A* algorithm over pre-loaded environmental layers (DEM, slope, thermal risk, PSR masks). The core claim: a "longer but thermally safe" route is demonstrably better than the "shortest but risky" route.

Reference document: `docs/lunapath_referans_belgesi.md` — all architecture decisions originate there.

---

## Stack

| Layer | Technology |
|---|---|
| Backend API | Python, FastAPI, uvicorn |
| Core engine | Python, numpy, scipy, heapq (custom A*) |
| Data loading | rasterio, numpy, scipy.ndimage |
| ML module | scikit-learn or PyTorch (scope TBD at hackathon start) |
| Frontend | React, Leaflet.js or deck.gl, Chart.js, Tailwind CSS |

---

## Expected Commands

These commands do not exist yet but should follow these patterns once scaffolded:

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Backend tests
pytest

# Frontend
cd frontend
npm install
npm run dev

# Frontend lint/typecheck
npm run lint
npm run typecheck
```

---

## Directory Layout (planned)

```
/backend
  main.py                  # FastAPI entrypoint
  modules/
    data_layer.py          # Module 1 — DEM/PSR/thermal grid loading
    path_planner.py        # Module 2 — Multi-criteria A*
    thermal_model.py       # Module 3 — Rover thermal risk scoring
    replanning_manager.py  # Module 4 — Event-triggered replan
  rover_profiles/          # JSON rover thermal profiles
/frontend
  src/
    components/
      MapView.tsx
      ControlPanel.tsx
      MetricsPanel.tsx
      EventLog.tsx
      ScenarioSelector.tsx
      ComparisonView.tsx
/data
  dem/                     # LOLA GeoTIFF files (gitignored)
  thermal/                 # Thermal risk layers (gitignored)
  psr/                     # PSR mask files (gitignored)
  scenarios/               # Demo scenario JSON files
/docs
  lunapath_referans_belgesi.md   # Authoritative technical reference
```

---

## Architecture

### Core Engine Modules

**Module 1 — Data Layer** (`data_layer.py`)
Reads raw DEM/PSR/thermal files, normalizes to numpy arrays, computes slope grid via `scipy.ndimage`. Grid resolution: 50–100m/cell. Outputs a single dict: `elevation_grid`, `slope_grid`, `thermal_risk_grid`, `psr_mask`, `traversability_grid`, `metadata`. All other modules consume this output.

**Module 2 — Multi-Criteria A*** (`path_planner.py`)
Custom A* using `heapq`. Cost function per cell:
```
g(n) = Σ [w_dist*dist + w_slope*slope_cost + w_thermal*thermal_risk + w_energy*energy_cost]
h(n) = w_dist * euclidean_distance(n, goal)
```
Hard block: cells with `thermal_risk > 0.9` are closed nodes. Heuristic uses only `w_dist` component to stay admissible. Target grid: ~500×500 cells.

**Module 3 — Thermal Model** (`thermal_model.py`)
Produces per-cell thermal risk scores (0.0–1.0) from temperature estimates and PSR flags. Uses rover profile JSON (`rover_profiles/`). Reference rover: VIPER-simplified. Risk scoring: `>critical_min_C → 1.0`, caution zone → 0.5–0.9 linear interpolation, PSR-but-safe → 0.3, safe → 0.0.

**Module 4 — Replanning Manager** (`replanning_manager.py`)
Event-triggered (not continuous). Receives trigger type (`thermal_spike`, `new_obstacle`, `energy_budget`) and affected node. In Phase 1: replans from trigger node to goal. Outputs old/new segment diff with metrics delta.

**Module 5 — FastAPI Backend**
Endpoints:
- `POST /api/plan` — initial route
- `POST /api/replan` — event-triggered replan
- `POST /api/compare` — safe vs. short route comparison
- `GET /api/layers` — serialized grid metadata for map rendering
- `GET /api/scenarios` — demo scenario list
- `POST /api/scenarios/{id}/apply` — apply scenario to grid state

Requires CORS middleware for React frontend.

**Module 6 — Frontend (React)**
Mission Control Panel. Map renders backend grid via canvas layer or GeoJSON overlay (not standard tile layer). Weight sliders drive `w_thermal`, `w_slope`, `w_energy` parameters sent to `/api/plan`.

**Module 7 — ML/AI Component** (scope to be decided at hackathon start)
Options: traversability scoring (Random Forest on slope + surface features), risk zone classification (sklearn classifier), or cost weight suggestion (rule-based). The framing: "A* decisions supported by an auxiliary AI layer" — not "ML does everything."

---

## Key Constraints

- System is **semi-dynamic / event-triggered**, not real-time.
- No live API data — all environmental layers are pre-loaded at startup.
- Shadow/PSR component is a **static risk mask**, not physics-based shadow calculation.
- Temperature data is static/modelled — no real-time thermal feed.
- `networkx` should be avoided in A* — use `heapq` with custom implementation.
- Grid coordinates are `(row, col)` internally; geographic `(lat, lon)` only in API responses.
- Weights are user-adjustable via frontend sliders (range: 0.0–2.0 each).
