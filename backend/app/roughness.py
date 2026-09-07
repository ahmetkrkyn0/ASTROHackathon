"""Measured surface roughness (LOLA LDRM) and the PGDA PSR mask (C4).

NASA GSFC's Planetary Geodesy group publishes, for the south pole (PGDA
product 90; Barker et al. 2023, PSJ 4:183; data DOI
10.60903/gsfcpgda-lola-spole), multi-baseline roughness maps computed from
the LOLA spots themselves:

    "LOLA Digital Roughness Map (LDRM, in meters). This is the spread of
    height residuals of individual LOLA spots around a plane fit to the
    LDEM within a circular window whose diameter is equal to a baseline of
    *M meters."                                   -- product page, 5 Sept 2026

and a 20 m/px permanently-shadowed-region map (LPSR; 506 349 features).
``scripts/build_roughness_cache.py`` reads the planning window of the 50 m/px,
100 m-baseline roughness product and of the PSR map over ``/vsicurl/``,
co-registers both to the 5 m grid with nearest-neighbour resampling and
writes them beside the processed grids. This module holds what the backend
needs to read them: the file names, the product constants, the [0, 1] scale
of the roughness criterion, the PSR-vs-shadow overlap statistic and the
response block.

Claim limits
------------
* The roughness LAYER is ``MEASURED`` -- it is NASA's statistic of LOLA spot
  residuals. But it is posted at 50 m/px with a 100 m baseline, and the grid
  is 5 m/px: every 5 m cell carries the value of the 50 m pixel that contains
  it. That is a hectometre-scale block statistic, not the roughness of the
  cell itself, and it is not a rock count (Diviner rock abundance stops at
  80 S and is not used).
* The CRITERION's mapping to [0, 1] is a statistical scale, labelled
  ``MODEL``: the cell's percentile rank among the 80-90 S region's 50 m
  pixels (an empirical CDF sampled from the product itself, stored with the
  layer). No rover in the catalogue declares a sourced roughness tolerance
  (ground clearance, wheel size), so none is invented; the scale is
  rover-independent.
* The PSR mask is a measured product and is NOT a planning input: VIPER's
  science targets are inside PSRs, the cold-end thermal gate already blocks
  almost every PSR cell on Site11, and the shadow and thermal criteria
  already price darkness. It is a layer, a cell-card field and a validation
  of our own ``shadow_ratio``.
* LDRM publishes no per-pixel sigma, so the roughness criterion has no B2
  risk tail: it reads the nominal value at every alpha.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

# ── files beside the processed grids (all gitignored) ───────────────────────
ROUGHNESS_CACHE_FILENAME = "roughness_grid.npy"
ROUGHNESS_META_FILENAME = "roughness_meta.json"
PSR_CACHE_FILENAME = "psr_grid.npy"
PSR_META_FILENAME = "psr_meta.json"
#: Raw 50 m windows of the other baselines, the Hurst exponent and the
#: plane-fit slope -- for the report only; never loaded by the backend.
ROUGHNESS_BASELINES_FILENAME = "roughness_baselines.npz"

# ── the products ────────────────────────────────────────────────────────────
PGDA_PRODUCT_URL = "https://pgda.gsfc.nasa.gov/products/90"
PGDA_DATA_BASE = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/"
PGDA_DATA_DOI = "10.60903/gsfcpgda-lola-spole"
LDRM_RESOLUTION_M = 50
LDRM_BASELINE_M = 100
LDRM_PRODUCT = f"LDRM_80S_{LDRM_RESOLUTION_M}MPP_ADJ_ROUGH_{LDRM_BASELINE_M}M"
LDRM_BASELINES_M: tuple[int, ...] = (100, 200, 400, 800, 1600)
LPSR_RESOLUTION_M = 20
LPSR_PRODUCT = f"LPSR_80S_{LPSR_RESOLUTION_M}MPP_ADJ"
LPSR_FEATURE_COUNT = 506_349  # "All PSRs (N=506349)", product page

ROUGHNESS_LAYER_VALIDITY = "MEASURED"
ROUGHNESS_SCALE_VALIDITY = "MODEL"
PSR_LAYER_VALIDITY = "MEASURED"

#: What a cell with no roughness measurement reads: the regional median rank
#: ("unknown = typical"). It never makes a cell impassable.
NAN_ROUGHNESS_F = 0.5

ROUGHNESS_CLAIM = (
    "LOLA LDRM roughness, MEASURED from LOLA spot residuals around a plane fit "
    f"(NASA GSFC PGDA product 90, Barker et al. 2023), posted at {LDRM_RESOLUTION_M} m/px "
    f"with a {LDRM_BASELINE_M} m baseline. Every 5 m cell carries the statistic of the "
    f"{LDRM_RESOLUTION_M} m pixel that contains it: a hectometre-scale block statistic, "
    "NOT the roughness of the cell itself, and not a rock count (Diviner rock abundance "
    "stops at 80 S and is not used). The [0, 1] criterion is the cell's percentile rank "
    "among the 80-90 S region's 50 m pixels -- a statistical scale (MODEL), not a rover "
    "tolerance; no roughness sigma is published, so the criterion has no risk tail."
)
PSR_CLAIM = (
    f"PGDA {LPSR_PRODUCT}: NASA's MEASURED permanently-shadowed-region map at "
    f"{LPSR_RESOLUTION_M} m/px, nearest-neighbour on the 5 m grid (each 5 m cell carries "
    "the value of the 20 m pixel that contains it). It is NOT a planning input -- VIPER's "
    "science targets are inside PSRs and the thermal gate already blocks them -- but a "
    "layer, a cell-card field and a check of our own shadow_ratio: the overlap numbers are "
    "measured on this window and reported as they come out."
)
ROUGHNESS_REFERENCES: tuple[str, ...] = (
    "Barker, M. K. et al. (2023), A New View of the Lunar South Pole from LOLA, "
    "Planet. Sci. J. 4:183, doi:10.3847/PSJ/acf3e1",
    f"NASA GSFC PGDA product 90 (LDRM roughness, LDSM slope, LPSR PSR maps), {PGDA_PRODUCT_URL}, "
    f"data DOI {PGDA_DATA_DOI}",
    "Large-scale Roughness Properties of the Lunar North and South Polar Regions, "
    "Planet. Sci. J. (2025), doi:10.3847/PSJ/adbc9d",
    "Kreslavsky, M. A. et al. (2013), Lunar topographic roughness maps from LOLA data, Icarus 226",
    "Rosenburg, M. A. et al. (2011), Global surface slopes and roughness of the Moon from LOLA, "
    "JGR 116, E02001",
    "Powell, T. M. et al. (2023), Diviner rock abundance -- coverage limited to +-80 latitude, "
    "JGR Planets 128 (why rock abundance is NOT used here)",
)


def ldrm_url(baseline_m: int = LDRM_BASELINE_M, kind: str = "ROUGH", resolution_m: int = LDRM_RESOLUTION_M) -> str:
    """URL of an LDRM product: ``kind`` ROUGH / SLP / RMSD with a baseline, or H
    (Hurst exponent, no baseline)."""
    stem = f"LDRM_80S_{int(resolution_m)}MPP_ADJ_{kind}"
    if kind != "H":
        stem += f"_{int(baseline_m)}M"
    return f"{PGDA_DATA_BASE}{stem}.TIF"


def lpsr_url() -> str:
    return f"{PGDA_DATA_BASE}{LPSR_PRODUCT}.TIF"


# ── the [0, 1] scale of the criterion ───────────────────────────────────────


@dataclass(frozen=True)
class RoughnessScale:
    """The criterion's mapping from metres to [0, 1]: an empirical CDF given
    as quantile knots. ``f`` is linear between knots (``np.interp``), clamps
    outside them, and reads ``NAN_ROUGHNESS_F`` for a missing value.

    Knots are strictly increasing (equal quantile values -- ties, e.g. many
    zeros -- are merged keeping the LAST probability, which is the
    right-continuous ECDF). ``f`` and ``f_grid`` run the same ``np.interp``
    call on the same array path, so the scalar reference and the grid form
    are bit-equal.
    """

    knots: tuple[float, ...]
    probs: tuple[float, ...]
    kind: str = "regional_ecdf"
    source: str = ""
    n_samples: int | None = None

    @classmethod
    def from_meta(cls, meta: Mapping[str, Any] | None) -> "RoughnessScale":
        if not isinstance(meta, Mapping):
            raise ValueError("roughness scale: metadata block missing or not a mapping")
        knots_raw = meta.get("knots")
        probs_raw = meta.get("probs")
        if knots_raw is None or probs_raw is None:
            raise ValueError("roughness scale: 'knots' and 'probs' are required")
        knots = np.asarray(knots_raw, dtype=np.float64).ravel()
        probs = np.asarray(probs_raw, dtype=np.float64).ravel()
        if knots.shape != probs.shape:
            raise ValueError("roughness scale: knots and probs differ in length")
        if not (np.all(np.isfinite(knots)) and np.all(np.isfinite(probs))):
            raise ValueError("roughness scale: knots and probs must be finite")
        if np.any(np.diff(knots) < 0.0) or np.any(np.diff(probs) < 0.0):
            raise ValueError("roughness scale: knots and probs must be non-decreasing")
        if probs.size and (probs[0] < 0.0 or probs[-1] > 1.0):
            raise ValueError("roughness scale: probs must lie in [0, 1]")
        # Merge ties: keep the last probability of each distinct knot.
        merged_k: list[float] = []
        merged_p: list[float] = []
        for k, p in zip(knots.tolist(), probs.tolist()):
            if merged_k and merged_k[-1] == k:
                merged_p[-1] = p
            else:
                merged_k.append(k)
                merged_p.append(p)
        if len(merged_k) < 2:
            raise ValueError("roughness scale: at least two distinct knots are required")
        n_samples = meta.get("n_samples")
        return cls(
            knots=tuple(merged_k),
            probs=tuple(merged_p),
            kind=str(meta.get("kind", "regional_ecdf")),
            source=str(meta.get("source", "")),
            n_samples=None if n_samples is None else int(n_samples),
        )

    def to_meta(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "validity": ROUGHNESS_SCALE_VALIDITY,
            "knots": list(self.knots),
            "probs": list(self.probs),
            "source": self.source,
            "n_samples": self.n_samples,
        }

    def f_grid(self, roughness_m: np.ndarray) -> np.ndarray:
        """[0, 1] per cell; non-finite input reads ``NAN_ROUGHNESS_F``."""
        arr = np.asarray(roughness_m, dtype=np.float64)
        finite = np.isfinite(arr)
        safe = np.where(finite, arr, self.knots[0])
        out = np.interp(safe, self.knots, self.probs)
        return np.where(finite, out, NAN_ROUGHNESS_F).astype(np.float64)

    def f(self, roughness_m: float | None) -> float:
        """Scalar reference form of :meth:`f_grid` (same array path)."""
        if roughness_m is None:
            return NAN_ROUGHNESS_F
        value = float(roughness_m)
        if not math.isfinite(value):
            return NAN_ROUGHNESS_F
        return float(self.f_grid(np.array([value]))[0])


def ecdf_scale_from_sample(
    sample: np.ndarray,
    n_knots: int = 201,
    source: str = "",
    kind: str = "regional_ecdf",
) -> RoughnessScale:
    """The empirical CDF of a sample of the product, as quantile knots at
    ``p = 0, 1/(n-1), ..., 1``. Non-finite values are dropped; a sample with
    fewer than two distinct finite values has no scale and is refused."""
    values = np.asarray(sample, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    if values.size < 2:
        raise ValueError("roughness scale sample: fewer than two finite values")
    probs = np.linspace(0.0, 1.0, int(n_knots))
    knots = np.quantile(values, probs)
    meta = {
        "kind": kind,
        "knots": knots.tolist(),
        "probs": probs.tolist(),
        "source": source,
        "n_samples": int(values.size),
    }
    try:
        return RoughnessScale.from_meta(meta)
    except ValueError as exc:
        raise ValueError(f"roughness scale sample: {exc}") from exc


# ── projection equality ────────────────────────────────────────────────────

_PROJ_KEYS: tuple[str, ...] = ("proj", "lat_0", "lon_0", "lat_ts", "x_0", "y_0", "k", "k_0", "R", "a", "b")


def same_projection(crs_a: Any, crs_b: Any, tol: float = 1e-6) -> bool:
    """True when two CRS definitions describe the same projection: same
    projection kind and the same numeric parameters (pole, meridian, false
    offsets, sphere radius / ellipsoid axes). Names ("unnamed" vs "Moon
    (2015) - Sphere") are ignored -- a WKT that only differs in naming is the
    same map."""
    from rasterio.crs import CRS

    def params(crs: Any) -> dict[str, Any]:
        obj = crs if isinstance(crs, CRS) else CRS.from_user_input(crs)
        d = obj.to_dict()
        out: dict[str, Any] = {}
        for key in _PROJ_KEYS:
            if key in d:
                out[key] = d[key]
        # A sphere may come as R or as a == b.
        if "R" not in out and "a" in out and "b" in out and abs(float(out["a"]) - float(out["b"])) < tol:
            out["R"] = float(out.pop("a"))
            out.pop("b", None)
        return out

    pa, pb = params(crs_a), params(crs_b)
    if set(pa) != set(pb):
        return False
    for key in pa:
        va, vb = pa[key], pb[key]
        if isinstance(va, str) or isinstance(vb, str):
            if str(va) != str(vb):
                return False
        elif abs(float(va) - float(vb)) > tol:
            return False
    return True


# ── PSR vs our shadow model ────────────────────────────────────────────────


def _mean_or_none(values: np.ndarray) -> float | None:
    return None if values.size == 0 else float(np.mean(values))


def _median_or_none(values: np.ndarray) -> float | None:
    return None if values.size == 0 else float(np.median(values))


def psr_shadow_overlap(
    psr: np.ndarray,
    shadow_ratio: np.ndarray,
    thermal_min: np.ndarray | None = None,
    threshold: float = 0.99,
) -> dict[str, Any]:
    """How NASA's PSR mask and our ``shadow_ratio >= threshold`` cells agree.

    Jaccard of the two sets, the share of PSR cells our model calls dark
    (``psr_recall``), the share of our dark cells that are PSR
    (``dark_precision``; its complement is the false-positive fraction), the
    mean shadow ratio inside and outside the mask and, when given, the
    median cold-end temperature inside and outside. Ratios with an empty
    denominator are ``None``; the Jaccard of two empty sets is 0.0.
    """
    p = np.asarray(psr, dtype=np.float64)
    s = np.asarray(shadow_ratio, dtype=np.float64)
    if p.shape != s.shape:
        raise ValueError(f"psr {p.shape} and shadow_ratio {s.shape} differ in shape")
    t = None
    if thermal_min is not None:
        t = np.asarray(thermal_min, dtype=np.float64)
        if t.shape != p.shape:
            raise ValueError(f"thermal_min {t.shape} and psr {p.shape} differ in shape")

    in_psr = np.isfinite(p) & (p >= 0.5)
    dark = np.isfinite(s) & (s >= float(threshold))
    inter = int(np.count_nonzero(in_psr & dark))
    union = int(np.count_nonzero(in_psr | dark))
    n_psr = int(np.count_nonzero(in_psr))
    n_dark = int(np.count_nonzero(dark))
    precision = None if n_dark == 0 else inter / n_dark
    finite_s = np.isfinite(s)
    return {
        "threshold": float(threshold),
        "n_cells": int(p.size),
        "n_psr": n_psr,
        "psr_fraction": n_psr / p.size if p.size else 0.0,
        "n_dark": n_dark,
        "n_intersection": inter,
        "n_union": union,
        "jaccard": inter / union if union else 0.0,
        "psr_recall": None if n_psr == 0 else inter / n_psr,
        "dark_precision": precision,
        "false_positive_fraction": None if precision is None else 1.0 - precision,
        "mean_shadow_inside_psr": _mean_or_none(s[in_psr & finite_s]),
        "mean_shadow_outside_psr": _mean_or_none(s[~in_psr & finite_s]),
        "thermal_min_median_inside_psr": None if t is None else _median_or_none(t[in_psr & np.isfinite(t)]),
        "thermal_min_median_outside_psr": None if t is None else _median_or_none(t[~in_psr & np.isfinite(t)]),
    }


# ── route summary and response block ───────────────────────────────────────


def route_roughness_summary(
    roughness_m: Sequence[float] | np.ndarray,
    f_roughness: Sequence[float] | np.ndarray,
    in_psr: Sequence[float] | np.ndarray | None,
) -> dict[str, Any]:
    """Per-route statistics of the cells a route visits: mean and max
    roughness (metres, NaN skipped), mean criterion value and the count of
    cells inside the PSR mask (``None`` without the mask)."""
    r = np.asarray(roughness_m, dtype=np.float64).ravel()
    f = np.asarray(f_roughness, dtype=np.float64).ravel()
    finite = r[np.isfinite(r)]
    psr_count: int | None
    if in_psr is None:
        psr_count = None
    else:
        p = np.asarray(in_psr, dtype=np.float64).ravel()
        psr_count = int(np.count_nonzero(np.isfinite(p) & (p >= 0.5)))
    return {
        "n_cells": int(r.size),
        "nan_cells": int(r.size - finite.size),
        "mean_roughness_m": None if finite.size == 0 else float(np.mean(finite)),
        "max_roughness_m": None if finite.size == 0 else float(np.max(finite)),
        "mean_f_roughness": None if f.size == 0 else float(np.mean(f)),
        "cells_in_psr": psr_count,
    }


def roughness_block(
    applied: bool,
    weight: float | None,
    route: Mapping[str, Any] | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """The ``roughness`` block a plan response carries."""
    return {
        "applied": bool(applied),
        "validity": ROUGHNESS_LAYER_VALIDITY,
        "scale_validity": ROUGHNESS_SCALE_VALIDITY,
        "product": LDRM_PRODUCT,
        "baseline_m": LDRM_BASELINE_M,
        "resolution_m": LDRM_RESOLUTION_M,
        "product_url": PGDA_PRODUCT_URL,
        "weight": None if weight is None else float(weight),
        "route": None if (not applied or route is None) else dict(route),
        "reason": None if applied else reason,
        "claim": ROUGHNESS_CLAIM,
        "references": list(ROUGHNESS_REFERENCES),
    }
