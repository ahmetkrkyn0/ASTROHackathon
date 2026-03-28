"""LunaPath FastAPI backend."""

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .data_loader import load_and_preprocess_dem, DATA_DIR

app = FastAPI(title="LunaPath", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory grid store (loaded once)
_grids: dict | None = None


class LoadDEMRequest(BaseModel):
    dem_file: str
    target_resolution_m: float = 50


@app.get("/api/health")
def health():
    loaded = _grids is not None
    shape = _grids["metadata"]["shape"] if loaded else None
    return {"status": "ok", "version": "0.1.0", "dem_loaded": loaded, "grid_shape": shape}


@app.post("/api/load-dem")
def load_dem(req: LoadDEMRequest):
    global _grids
    dem_path = os.path.join(DATA_DIR, "dem", req.dem_file)
    if not os.path.exists(dem_path):
        raise HTTPException(status_code=404, detail=f"DEM file not found: {req.dem_file}")
    _grids = load_and_preprocess_dem(dem_path, req.target_resolution_m)
    meta = _grids["metadata"]
    return {"status": "loaded", "metadata": meta}
