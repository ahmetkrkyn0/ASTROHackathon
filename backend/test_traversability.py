"""Traversability module tests — verifies canonical hard-block rules."""

import sys
import math

import numpy as np

from app.traversability import (
    compute_traversability,
    compute_traversability_bool,
    THERMAL_MIN_TRAVERSABLE_C,
)
from app.constants import SLOPE_MAX_DEG

PASS = 0
FAIL = 0


def check(name: str, condition: bool):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name}")


# ── 1. Slope hard block ────────────────────────────────────────────────────
print("=== Traversability: slope hard block ===")

slope = np.array([[10, 30], [5, 26]], dtype=np.float64)
thermal = np.zeros_like(slope)
trav = compute_traversability(slope, thermal)

check("10 deg passable", trav[0, 0] == 1.0)
check("30 deg blocked", trav[0, 1] == 0.0)
check("5 deg passable", trav[1, 0] == 1.0)
check("26 deg blocked (>25)", trav[1, 1] == 0.0)
check("25 deg boundary passable",
      compute_traversability(
          np.array([[25.0]]), np.array([[0.0]])
      )[0, 0] == 1.0)


# ── 2. Thermal hard block ──────────────────────────────────────────────────
print("\n=== Traversability: thermal hard block ===")

slope2 = np.zeros((2, 2), dtype=np.float64)
thermal2 = np.array([[0, -100], [-151, -200]], dtype=np.float64)
trav2 = compute_traversability(slope2, thermal2)

check("0 C passable", trav2[0, 0] == 1.0)
check("-100 C passable", trav2[0, 1] == 1.0)
check("-151 C blocked", trav2[1, 0] == 0.0)
check("-200 C blocked", trav2[1, 1] == 0.0)
check("-150 C boundary passable",
      compute_traversability(
          np.array([[0.0]]), np.array([[-150.0]])
      )[0, 0] == 1.0)


# ── 3. NaN handling ────────────────────────────────────────────────────────
print("\n=== Traversability: NaN handling ===")

slope_nan = np.array([[float("nan"), 10.0]], dtype=np.float64)
thermal_nan = np.array([[0.0, float("nan")]], dtype=np.float64)
trav_nan = compute_traversability(slope_nan, thermal_nan)

check("NaN slope blocked", trav_nan[0, 0] == 0.0)
check("NaN thermal blocked", trav_nan[0, 1] == 0.0)


# ── 4. Bool variant with elevation ─────────────────────────────────────────
print("\n=== Traversability: bool variant + elevation NaN ===")

slope3 = np.array([[10.0, 10.0]], dtype=np.float64)
thermal3 = np.array([[0.0, 0.0]], dtype=np.float64)
elev3 = np.array([[100.0, float("nan")]], dtype=np.float64)
trav_bool = compute_traversability_bool(slope3, thermal3, elev3)

check("Valid elevation passable", trav_bool[0, 0] == True)
check("NaN elevation blocked", trav_bool[0, 1] == False)


# ── 5. Output dtype ────────────────────────────────────────────────────────
print("\n=== Traversability: output properties ===")

trav_f = compute_traversability(
    np.array([[10.0, 30.0]]), np.array([[0.0, 0.0]])
)
check("float64 dtype", trav_f.dtype == np.float64)
check("Values are 0 or 1 only",
      set(np.unique(trav_f).tolist()).issubset({0.0, 1.0}))


# ── 6. Constants consistency ───────────────────────────────────────────────
print("\n=== Constants consistency ===")

check("SLOPE_MAX_DEG == 25", SLOPE_MAX_DEG == 25)
check("THERMAL_MIN == -150", THERMAL_MIN_TRAVERSABLE_C == -150.0)


# ── Summary ────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  PASSED: {PASS}")
print(f"  FAILED: {FAIL}")
print(f"  TOTAL:  {PASS + FAIL}")
print(f"{'='*50}")

sys.exit(1 if FAIL > 0 else 0)
