#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Grid hesaplama birim testleri.
DEM dosyasi gerektirmez, sentetik veri ile calisir.
"""

from __future__ import annotations

import numpy as np
import sys

# --- Test edilecek fonksiyonlari import et -----------------------------------
from process_lunar_data import (
    make_slope_grid,
    make_aspect_grid,
    make_shadow_ratio_grid,
    make_thermal_grid,
    make_traversability_grid,
    SLOPE_MAX_DEG,
    THERMAL_MIN_TRAVERSABLE_C,
    RESOLUTION_M,
)


def test_slope_grid():
    """Duz zemin -> 0 egim; rampa -> pozitif egim."""
    flat = np.ones((10, 10), dtype=np.float64) * 100.0
    slope = make_slope_grid(flat, 80.0)
    assert np.allclose(slope, 0.0, atol=1e-10), \
        f"Duz zemin egimi 0 olmali, got max={slope.max()}"

    ramp = np.zeros((10, 10), dtype=np.float64)
    for i in range(10):
        ramp[i, :] = i * 80.0 * np.tan(np.radians(10.0))  # ~10 derece rampa
    slope_ramp = make_slope_grid(ramp, 80.0)
    # Kenar pikseller haric ic piksellerde ~10 derece olmali
    inner = slope_ramp[2:-2, 2:-2]
    assert np.all(inner > 5.0) and np.all(inner < 15.0), \
        f"Rampa egimi ~10 deg olmali, got mean={inner.mean():.1f}"

    print("  test_slope_grid PASSED")


def test_aspect_grid():
    """Aspect 0-360 araliginda olmali."""
    elev = np.random.RandomState(42).rand(50, 50).astype(np.float64) * 1000
    aspect = make_aspect_grid(elev, 80.0)
    assert np.all(aspect >= 0.0) and np.all(aspect <= 360.0), \
        f"Aspect [0,360] disinda deger var: min={aspect.min()}, max={aspect.max()}"
    print("  test_aspect_grid PASSED")


def test_shadow_ratio():
    """En yuksek nokta -> 0, en alcak nokta -> 1."""
    elev = np.array([[100, 200], [300, 400]], dtype=np.float64)
    shadow = make_shadow_ratio_grid(elev)
    # 400m -> elev_norm=1.0 -> shadow=0.0
    assert shadow[1, 1] < 0.01, f"En yuksek noktada shadow ~0 olmali, got {shadow[1,1]}"
    # 100m -> elev_norm=0.0 -> shadow=1.0
    assert shadow[0, 0] > 0.99, f"En alcak noktada shadow ~1 olmali, got {shadow[0,0]}"
    print("  test_shadow_ratio PASSED")


def test_thermal_grid_range():
    """Termal grid [-250, 130] araliginda olmali."""
    elev = np.random.RandomState(42).rand(50, 50).astype(np.float64) * 5000 - 3000
    slope = make_slope_grid(elev, 80.0)
    aspect = make_aspect_grid(elev, 80.0)
    thermal = make_thermal_grid(elev, slope, aspect, 80.0)
    assert np.nanmin(thermal) >= -250.0, f"Thermal min < -250: {np.nanmin(thermal)}"
    assert np.nanmax(thermal) <= 130.0, f"Thermal max > 130: {np.nanmax(thermal)}"
    print("  test_thermal_grid_range PASSED")


def test_traversability_slope_block():
    """slope > 25 -> gecilmez."""
    slope = np.array([[10, 30], [5, 26]], dtype=np.float64)
    thermal = np.zeros_like(slope)  # sicaklik ok
    trav = make_traversability_grid(slope, thermal)
    assert trav[0, 0] == 1.0, "10 deg gecilir olmali"
    assert trav[0, 1] == 0.0, "30 deg gecilmez olmali"
    assert trav[1, 0] == 1.0, "5 deg gecilir olmali"
    assert trav[1, 1] == 0.0, "26 deg gecilmez olmali"
    print("  test_traversability_slope_block PASSED")


def test_traversability_thermal_block():
    """thermal < -150 -> gecilmez."""
    slope = np.zeros((2, 2), dtype=np.float64)  # egim ok
    thermal = np.array([[0, -100], [-151, -200]], dtype=np.float64)
    trav = make_traversability_grid(slope, thermal)
    assert trav[0, 0] == 1.0, "0 C gecilir"
    assert trav[0, 1] == 1.0, "-100 C gecilir"
    assert trav[1, 0] == 0.0, "-151 C gecilmez"
    assert trav[1, 1] == 0.0, "-200 C gecilmez"
    print("  test_traversability_thermal_block PASSED")


def main() -> None:
    print("=" * 50)
    print("  LunaPath P1 v2.0 — Birim Testleri")
    print("=" * 50)

    tests = [
        test_slope_grid,
        test_aspect_grid,
        test_shadow_ratio,
        test_thermal_grid_range,
        test_traversability_slope_block,
        test_traversability_thermal_block,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  {t.__name__} FAILED: {e}")
            failed += 1

    print(f"\n  Sonuc: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
