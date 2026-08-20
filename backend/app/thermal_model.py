"""Surface thermal model adapters.

LunaPath consumes surface temperature as a (H, W) float32 grid in degrees
Celsius. Where that grid comes from is a swappable decision:

- ``SyntheticModel``  -- the original elevation/aspect heuristic (validity SYNTHETIC)
- ``Heat1DModel``     -- Hayne's 1-D regolith diffusion model  (validity MODEL)

Keeping both behind one protocol means an unavailable or API-drifted heat1d
release degrades to the synthetic baseline instead of blocking the pipeline.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from .thermal_grid import generate_thermal_grid


@runtime_checkable
class SurfaceThermalModel(Protocol):
    """Produces surface temperature in degrees Celsius."""

    name: str
    validity: str  # "MEASURED" | "DERIVED" | "MODEL" | "SYNTHETIC"

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray: ...


class SyntheticModel:
    """Legacy elevation + aspect heuristic. Kept as an explicit baseline."""

    name = "synthetic-elevation-aspect"
    validity = "SYNTHETIC"

    def __init__(self, elevation: np.ndarray, resolution_m: float) -> None:
        self._elevation = np.asarray(elevation, dtype=np.float64)
        self._resolution_m = float(resolution_m)

    def surface_temperature_c(
        self,
        slope_deg: np.ndarray,
        aspect_deg: np.ndarray,
        lat_deg: float,
    ) -> np.ndarray:
        # lat_deg is unused: the synthetic heuristic has no latitude term.
        return generate_thermal_grid(
            self._elevation,
            np.asarray(slope_deg, dtype=np.float64),
            np.asarray(aspect_deg, dtype=np.float64),
            self._resolution_m,
        )


def build_thermal_grid(
    model: SurfaceThermalModel,
    slope_grid: np.ndarray,
    aspect_grid: np.ndarray,
    lat_deg: float,
) -> np.ndarray:
    """Run *model* and normalise its output to (H, W) float32 Celsius."""
    out = model.surface_temperature_c(slope_grid, aspect_grid, lat_deg)
    out = np.asarray(out, dtype=np.float32)
    if out.shape != np.asarray(slope_grid).shape:
        raise ValueError(
            f"{model.name} returned shape {out.shape}, "
            f"expected {np.asarray(slope_grid).shape}"
        )
    return out
