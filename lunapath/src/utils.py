"""
LunaPath P1 v2.0 — Yardimci fonksiyonlar.
Koordinat donusumleri ve dogrulama yardimcilari.
"""

from __future__ import annotations

from typing import Tuple

from affine import Affine


def pixel_to_geo(
    row: int,
    col: int,
    transform: Affine,
) -> Tuple[float, float]:
    """Piksel (row, col) -> cografi (x, y) donusumu.

    Piksel merkezini dondurur (+0.5 offset).
    """
    x, y = transform * (col + 0.5, row + 0.5)
    return x, y


def geo_to_pixel(
    x: float,
    y: float,
    transform: Affine,
) -> Tuple[int, int]:
    """Cografi (x, y) -> piksel (row, col) donusumu."""
    col, row = ~transform * (x, y)
    return int(row), int(col)
