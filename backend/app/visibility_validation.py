"""Compare a modelled visibility fraction to an external reference.

Pure function: two co-registered (H, W) fraction grids in [0, 1], error
statistics out. Fetching, reprojecting and block-averaging the reference is
``scripts/earth_visibility_validation.py``'s job, kept out of here so the
comparison itself is testable without NASA's file on disk -- the same split
:mod:`app.thermal_validation` makes for Diviner.

The reference this exists for is the LOLA "Average Earth Visibility"
product (PGDA 69; Mazarico et al. 2011): 18.6 years of hourly Earth
visibility from the same horizon method LunaPath uses, at 60 m/px for
85-90 S. Agreement with it is the first number in this project that ties a
modelled layer to a published, measured-topography product.
"""

from __future__ import annotations

import numpy as np


def visibility_comparison(
    model_frac: np.ndarray,
    reference_frac: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, float | int | None]:
    """RMSE / MAE / bias / Pearson r between two visibility-fraction grids.

    Cells where either grid is NaN are excluded. ``disagreement_pct`` is the
    share of compared cells where the two grids fall on opposite sides of
    *threshold* -- one calls the cell mostly linked, the other mostly not --
    which is the disagreement that would change a plan.
    ``pearson_r`` is ``None`` when either grid is constant over the compared
    cells (the correlation is undefined, not zero).
    """
    model = np.asarray(model_frac, dtype=np.float64)
    reference = np.asarray(reference_frac, dtype=np.float64)
    if model.shape != reference.shape:
        raise ValueError(
            f"shape mismatch: model {model.shape} vs reference {reference.shape}"
        )

    valid = np.isfinite(model) & np.isfinite(reference)
    n_compared = int(np.sum(valid))
    if n_compared == 0:
        return {
            "rmse": None,
            "mae": None,
            "bias": None,
            "pearson_r": None,
            "n_compared": 0,
            "disagreement_pct": None,
            "model_mean": None,
            "reference_mean": None,
        }

    m = model[valid]
    r = reference[valid]
    error = m - r
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    pearson: float | None
    if n_compared < 2 or float(np.std(m)) == 0.0 or float(np.std(r)) == 0.0:
        pearson = None
    else:
        pearson = float(np.corrcoef(m, r)[0, 1])

    model_linked = m >= threshold
    reference_linked = r >= threshold
    disagreement = float(100.0 * np.mean(model_linked != reference_linked))

    return {
        "rmse": round(rmse, 6),
        "mae": round(mae, 6),
        "bias": round(bias, 6),
        "pearson_r": None if pearson is None else round(pearson, 6),
        "n_compared": n_compared,
        "disagreement_pct": round(disagreement, 3),
        "model_mean": round(float(np.mean(m)), 6),
        "reference_mean": round(float(np.mean(r)), 6),
    }


def block_mean(grid: np.ndarray, factor: int) -> np.ndarray:
    """NaN-aware mean over ``factor x factor`` blocks; the remainder is dropped.

    Brings a 5 m model grid to the 60 m pixels of the reference product so
    the two are compared at the reference's own resolution rather than the
    reference being interpolated down to structure it never resolved. A
    block that is NaN throughout stays NaN; a block with some NaN averages
    the rest.
    """
    arr = np.asarray(grid, dtype=np.float64)
    factor = int(factor)
    if factor < 1:
        raise ValueError("factor must be >= 1")
    if factor == 1:
        return arr.copy()
    rows = (arr.shape[0] // factor) * factor
    cols = (arr.shape[1] // factor) * factor
    if rows == 0 or cols == 0:
        raise ValueError(f"grid {arr.shape} has no full {factor}x{factor} block")
    blocks = arr[:rows, :cols].reshape(rows // factor, factor, cols // factor, factor)
    with np.errstate(invalid="ignore"):
        return np.nanmean(blocks, axis=(1, 3))
