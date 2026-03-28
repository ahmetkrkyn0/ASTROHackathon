"""
LunaPath P1 – Yardımcı fonksiyonlar.
pixel_to_geo: Piksel koordinatlarını coğrafi koordinatlara dönüştürür.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np
from affine import Affine


def pixel_to_geo(
    row: int,
    col: int,
    transform: Affine,
) -> Tuple[float, float]:
    """Piksel (row, col) → coğrafi (x, y) dönüşümü.

    rasterio transform matrisi kullanır.
    Piksel merkezini döndürür (+0.5 offset).
    """
    x, y = transform * (col + 0.5, row + 0.5)
    return x, y


def geo_to_pixel(
    x: float,
    y: float,
    transform: Affine,
) -> Tuple[int, int]:
    """Coğrafi (x, y) → piksel (row, col) dönüşümü."""
    col, row = ~transform * (x, y)
    return int(row), int(col)


def save_metadata(
    out_dir: Path,
    origin_x: float,
    origin_y: float,
    resolution: float,
    shape: Tuple[int, int],
    crs: str,
    window_row_off: int,
    window_col_off: int,
) -> Path:
    """Grid metadata'sını JSON olarak diske yazar."""
    meta = {
        "origin": {"x": origin_x, "y": origin_y},
        "resolution_m": resolution,
        "shape": list(shape),
        "crs": crs,
        "window_offset": {"row": window_row_off, "col": window_col_off},
    }
    path = out_dir / "metadata.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def report_memory(arrays: dict[str, np.ndarray]) -> None:
    """Her matrisin ve toplamın bellek kullanımını ekrana yazdırır."""
    total = 0
    print("\n╔══════════════════════════════════════════════╗")
    print("║          BELLEK KULLANIMI RAPORU             ║")
    print("╠══════════════════════════════════════════════╣")
    for name, arr in arrays.items():
        nbytes = arr.nbytes
        total += nbytes
        print(f"║  {name:<28s} {nbytes / 1024:>8.1f} KB  ║")
    print("╠══════════════════════════════════════════════╣")
    print(f"║  {'TOPLAM':<28s} {total / 1024:>8.1f} KB  ║")
    print(f"║  {'TOPLAM':<28s} {total / (1024**2):>8.2f} MB  ║")
    print("╚══════════════════════════════════════════════╝\n")


def report_nodata(arrays: dict[str, np.ndarray]) -> dict[str, int]:
    """NaN / NoData değerlerini tespit edip raporlar."""
    result: dict[str, int] = {}
    print("\n╔══════════════════════════════════════════════╗")
    print("║         NaN / NoData DOĞRULAMA               ║")
    print("╠══════════════════════════════════════════════╣")
    for name, arr in arrays.items():
        if np.issubdtype(arr.dtype, np.floating):
            nan_count = int(np.isnan(arr).sum())
        elif np.issubdtype(arr.dtype, np.bool_):
            nan_count = 0
        else:
            nan_count = 0
        result[name] = nan_count
        status = "✓ TEMİZ" if nan_count == 0 else f"⚠ {nan_count} NaN"
        print(f"║  {name:<28s} {status:>14s}  ║")
    print("╚══════════════════════════════════════════════╝\n")
    return result
