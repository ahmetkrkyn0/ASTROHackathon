"""Compare a modelled thermal grid to an external reference (e.g. Diviner).

Pure function: takes two co-registered (H, W) Celsius arrays, returns
error statistics. Does not fetch, reproject or crop data -- that is
scripts/diviner_validation.py's job, kept out of this module so the
comparison itself is testable without a real Diviner file.
"""

from __future__ import annotations

import numpy as np


def thermal_comparison(
    model_c: np.ndarray,
    reference_c: np.ndarray,
    traversable_threshold_c: float = -150.0,
) -> dict[str, float | int | None]:
    """RMSE/MAE/bias between a modelled and a reference thermal grid.

    Cells where either grid is NaN are excluded. ``misclassified_traversable_pct``
    is the share of compared cells where the two grids disagree about
    whether ``value >= traversable_threshold_c`` -- the number that
    matters for LunaPath, since that threshold gates traversability.
    """
    model = np.asarray(model_c, dtype=np.float64)
    reference = np.asarray(reference_c, dtype=np.float64)
    if model.shape != reference.shape:
        raise ValueError(
            f"shape mismatch: model {model.shape} vs reference {reference.shape}"
        )

    valid = np.isfinite(model) & np.isfinite(reference)
    n_compared = int(np.sum(valid))
    if n_compared == 0:
        return {
            "rmse_c": None,
            "mae_c": None,
            "bias_c": None,
            "n_compared": 0,
            "misclassified_traversable_pct": None,
        }

    error = model[valid] - reference[valid]
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    bias = float(np.mean(error))

    model_ok = model[valid] >= traversable_threshold_c
    reference_ok = reference[valid] >= traversable_threshold_c
    misclassified_pct = float(100.0 * np.mean(model_ok != reference_ok))

    return {
        "rmse_c": round(rmse, 3),
        "mae_c": round(mae, 3),
        "bias_c": round(bias, 3),
        "n_compared": n_compared,
        "misclassified_traversable_pct": round(misclassified_pct, 3),
    }
