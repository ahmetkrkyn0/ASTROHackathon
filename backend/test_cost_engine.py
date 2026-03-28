"""Cost engine accuracy tests against v3.2 spec validation tables."""

import math
import sys

from app.cost_engine import (
    f_slope,
    f_energy,
    f_shadow,
    f_thermal,
    log_barrier_penalty,
    surface_to_inner,
    total_edge_cost,
)

PASS = 0
FAIL = 0


def check(name: str, got: float, expected: float, tol: float = 0.001):
    global PASS, FAIL
    ok = (math.isinf(got) and math.isinf(expected)) or abs(got - expected) <= tol
    status = "PASS" if ok else "FAIL"
    if not ok:
        FAIL += 1
        print(f"  [{status}] {name}: got {got:.6f}, expected {expected:.6f}")
    else:
        PASS += 1


def check_inf(name: str, got: float):
    global PASS, FAIL
    if math.isinf(got):
        PASS += 1
    else:
        FAIL += 1
        print(f"  [FAIL] {name}: expected inf, got {got}")


# ─────────────────────────────────────────────────────────────────────────────
#  1. f_slope — Spec Table §2.3.1
# ─────────────────────────────────────────────────────────────────────────────
print("=== f_slope ===")
check("f_slope(5)",  f_slope(5),  0.018)
check("f_slope(10)", f_slope(10), 0.119)
check("f_slope(15)", f_slope(15), 0.500)
check("f_slope(20)", f_slope(20), 0.881)
check("f_slope(25)", f_slope(25), 0.982)
check_inf("f_slope(26)", f_slope(26))
check_inf("f_slope(30)", f_slope(30))

# Monotonicity
print("  Monotonicity...", end=" ")
vals = [f_slope(i) for i in range(0, 26)]
mono = all(vals[i] <= vals[i+1] for i in range(len(vals)-1))
if mono:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")

# MRU range
print("  MRU [0,1]...", end=" ")
in_range = all(0.0 <= v <= 1.0 for v in vals)
if in_range:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")


# ─────────────────────────────────────────────────────────────────────────────
#  2. f_energy — Physics consistency §2.3.2
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== f_energy ===")

# Flat terrain, 50m grid → known analytical value
# mu=1.0, v=0.2, L=50, t=250s, E=200*1*250/3600=13.89 Wh, ratio=13.89/5420=0.00256
check("f_energy(0, 50)", f_energy(0, 50), 0.00256, tol=0.0001)

# Steeper = more energy (monotonicity for fixed distance)
print("  Monotonicity (fixed d=50m)...", end=" ")
vals_e = [f_energy(i, 50) for i in range(0, 25)]
mono_e = all(vals_e[i] <= vals_e[i+1] for i in range(len(vals_e)-1))
if mono_e:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")

# Per-edge values should be small (spec note: ~0.003-0.006 for 50m grid)
print("  Per-edge magnitude...", end=" ")
e10 = f_energy(10, 50)
if 0.001 < e10 < 0.02:
    PASS += 1
    print(f"PASS (f_energy(10,50)={e10:.5f})")
else:
    FAIL += 1
    print(f"FAIL (f_energy(10,50)={e10:.5f}, expected 0.001-0.02)")

# MRU: all values in [0, 1]
print("  MRU [0,1]...", end=" ")
in_range_e = all(0.0 <= v <= 1.0 for v in vals_e)
if in_range_e:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")


# ─────────────────────────────────────────────────────────────────────────────
#  3. f_shadow — Spec Table §2.3.3
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== f_shadow ===")
check("f_shadow(0)",  f_shadow(0),  0.000)
check("f_shadow(12)", f_shadow(12), 0.055)
check("f_shadow(25)", f_shadow(25), 0.182)
check("f_shadow(37)", f_shadow(37), 0.430)
check("f_shadow(50)", f_shadow(50), 1.000)

# Monotonicity
print("  Monotonicity...", end=" ")
vals_s = [f_shadow(h) for h in range(0, 51)]
mono_s = all(vals_s[i] <= vals_s[i+1] for i in range(len(vals_s)-1))
if mono_s:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")

# Saturation: beyond 50h stays at 1.0
check("f_shadow(60)", f_shadow(60), 1.000)
check("f_shadow(100)", f_shadow(100), 1.000)


# ─────────────────────────────────────────────────────────────────────────────
#  4. f_thermal — Spec Table §2.3.4
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== f_thermal ===")
check("f_thermal(+60)",  f_thermal(60),   0.011)
check("f_thermal(-30)",  f_thermal(-30),  0.140, tol=0.005)
check("f_thermal(-100)", f_thermal(-100), 1.000, tol=0.001)
check("f_thermal(-180)", f_thermal(-180), 1.000, tol=0.001)

# Surface-to-inner conversion
check("inner(+60)", surface_to_inner(60), 20.0)
check("inner(-30)", surface_to_inner(-30), 30.0)
check("inner(-100)", surface_to_inner(-100), -40.0)

# Ideal zone should have low penalty
print("  Ideal zone (T_surface=+60 → T_inner=+20)...", end=" ")
if f_thermal(60) < 0.05:
    PASS += 1
    print(f"PASS ({f_thermal(60):.4f})")
else:
    FAIL += 1
    print(f"FAIL ({f_thermal(60):.4f})")

# Extreme cold = saturated
print("  Extreme cold saturation...", end=" ")
if f_thermal(-200) > 0.99:
    PASS += 1
    print("PASS")
else:
    FAIL += 1
    print("FAIL")


# ─────────────────────────────────────────────────────────────────────────────
#  5. log_barrier_penalty — §2.3.5
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== log_barrier_penalty ===")

# Safe operating point → finite positive value
safe = log_barrier_penalty(theta_along=10, theta_lateral=5, soc=0.8, T_inner=20)
print(f"  Safe point (10°, 5°, 80% SOC, 20°C)...", end=" ")
if 0 < safe < 5:
    PASS += 1
    print(f"PASS ({safe:.4f})")
else:
    FAIL += 1
    print(f"FAIL ({safe:.4f})")

# At slope limit → INF
check_inf("slope=25", log_barrier_penalty(25, 5, 0.8, 20))

# At lateral limit → INF
check_inf("lateral=18", log_barrier_penalty(10, 18, 0.8, 20))

# SOC at minimum → INF
check_inf("soc=0.20", log_barrier_penalty(10, 5, 0.20, 20))

# SOC below minimum → INF
check_inf("soc=0.15", log_barrier_penalty(10, 5, 0.15, 20))

# T_inner at cold limit → INF
check_inf("T_inner=-20", log_barrier_penalty(10, 5, 0.8, -20))

# T_inner at hot limit → INF
check_inf("T_inner=95", log_barrier_penalty(10, 5, 0.8, 95))

# Approaching limits → cost increases (gradient check)
print("  Gradient: cost rises near slope limit...", end=" ")
b1 = log_barrier_penalty(15, 5, 0.8, 20)
b2 = log_barrier_penalty(20, 5, 0.8, 20)
b3 = log_barrier_penalty(24, 5, 0.8, 20)
if b1 < b2 < b3:
    PASS += 1
    print(f"PASS ({b1:.3f} < {b2:.3f} < {b3:.3f})")
else:
    FAIL += 1
    print(f"FAIL ({b1:.3f}, {b2:.3f}, {b3:.3f})")


# ─────────────────────────────────────────────────────────────────────────────
#  6. total_edge_cost — Combined §2.2
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== total_edge_cost ===")

# >25° → INF
check_inf("slope>25", total_edge_cost(26, 50, 0, 60))

# Normal operating point → finite > 0.01
c = total_edge_cost(10, 50, 5, 60)
print(f"  Normal point (10°, 50m, 5h shadow, 60°C)...", end=" ")
if 0.01 <= c < 100:
    PASS += 1
    print(f"PASS ({c:.4f})")
else:
    FAIL += 1
    print(f"FAIL ({c:.4f})")

# Weight sensitivity: higher w_slope → slope-dominated cost
c_high_slope = total_edge_cost(20, 50, 5, 60, weights={"w_slope": 0.8, "w_energy": 0.1, "w_shadow": 0.05, "w_thermal": 0.05})
c_low_slope = total_edge_cost(20, 50, 5, 60, weights={"w_slope": 0.1, "w_energy": 0.1, "w_shadow": 0.4, "w_thermal": 0.4})
print(f"  Weight sensitivity (high vs low w_slope at 20°)...", end=" ")
if c_high_slope > c_low_slope:
    PASS += 1
    print(f"PASS ({c_high_slope:.3f} > {c_low_slope:.3f})")
else:
    FAIL += 1
    print(f"FAIL ({c_high_slope:.3f} vs {c_low_slope:.3f})")

# AHP weights sum to 1.0
from app.constants import W_SLOPE, W_ENERGY, W_SHADOW, W_THERMAL
wsum = W_SLOPE + W_ENERGY + W_SHADOW + W_THERMAL
check("AHP weight sum", wsum, 1.000)


# ─────────────────────────────────────────────────────────────────────────────
#  Summary
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"  PASSED: {PASS}")
print(f"  FAILED: {FAIL}")
print(f"  TOTAL:  {PASS + FAIL}")
print(f"{'='*50}")

sys.exit(1 if FAIL > 0 else 0)
