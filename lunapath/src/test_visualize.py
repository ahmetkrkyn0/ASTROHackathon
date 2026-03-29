#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Gorsel Dogrulama
====================================
Uretilen 7 grid'i yukleyip 2x4 subplot ile gorsellestirerek
verinin tutarliligini dogrular.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# --- Yollar ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

GRID_NAMES = [
    "elevation_grid",
    "slope_grid",
    "aspect_grid",
    "shadow_ratio_grid",
    "thermal_grid",
    "traversability_grid",
    "cost_grid",
]


def load_grids() -> dict[str, np.ndarray]:
    """Islenmis grid dosyalarini yukler."""
    grids = {}
    for name in GRID_NAMES:
        path = PROCESSED_DIR / f"{name}.npy"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} bulunamadi. Once process_lunar_data.py calistirin."
            )
        grids[name] = np.load(path, allow_pickle=False)
    return grids


def plot_all_grids(grids: dict[str, np.ndarray]) -> None:
    """7 grid'i 2x4 subplot ile cizer."""
    fig, axes = plt.subplots(2, 4, figsize=(22, 12))
    fig.suptitle("LunaPath P1 v2.0 — Veri Dogrulama", fontsize=16, fontweight="bold")

    configs = [
        ("elevation_grid",      "Yukseklik (m)",           "terrain", None),
        ("slope_grid",          "Egim (derece)",           "YlOrRd",  None),
        ("aspect_grid",         "Baki Yonu (derece)",      "hsv",     (0, 360)),
        ("shadow_ratio_grid",   "Golge Orani",             "gray_r",  (0, 1)),
        ("thermal_grid",        "Yuzey Sicakligi (C)",     "coolwarm", None),
        ("traversability_grid", "Gecilebilirlik (0/1)",    "RdYlGn",  (0, 1)),
        ("cost_grid",           "Weighted Cost",           "viridis", None),
    ]

    flat_axes = axes.flatten()

    for ax, (name, title, cmap, vlim) in zip(flat_axes, configs):
        data = grids[name]
        if name == "cost_grid":
            data = np.where(np.isfinite(data), data, np.nan)
        kwargs = {"cmap": cmap, "aspect": "equal"}
        if vlim is not None:
            kwargs["vmin"], kwargs["vmax"] = vlim
        im = ax.imshow(data, **kwargs)
        ax.set_title(title)
        fig.colorbar(im, ax=ax, shrink=0.8)

    for ax in flat_axes[len(configs):]:
        ax.axis("off")

    plt.tight_layout()
    out_path = PROCESSED_DIR / "validation_plot.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"Gorsel kaydedildi: {out_path}")
    plt.show()


def print_consistency_checks(grids: dict[str, np.ndarray]) -> None:
    """Temel tutarlilik kontrollerini yazdirir."""
    slope = grids["slope_grid"]
    trav = grids["traversability_grid"]
    thermal = grids["thermal_grid"]
    cost = grids["cost_grid"]

    # Dik yamaclarda gecilebilirlik 0 olmali
    steep_mask = slope > 25.0
    if steep_mask.any():
        trav_at_steep = np.nanmean(trav[steep_mask])
        print(f"\n--- Tutarlilik Kontrolu ---")
        print(f"  Dik (>25 deg) bolgelerde ort. gecilebilirlik: {trav_at_steep:.3f}")
        if trav_at_steep < 0.01:
            print("  DOGRU: Dik yamaclar gecilmez olarak isaretlenmis.")
        else:
            print("  UYARI: Dik yamac tutarsizligi!")

    # Cok soguk bolgelerde gecilebilirlik 0 olmali
    cold_mask = thermal < -150.0
    if cold_mask.any():
        trav_at_cold = np.nanmean(trav[cold_mask])
        print(f"  Soguk (<-150 C) bolgelerde ort. gecilebilirlik: {trav_at_cold:.3f}")
        if trav_at_cold < 0.01:
            print("  DOGRU: Soguk bolgeler gecilmez olarak isaretlenmis.")
        else:
            print("  UYARI: Soguk bolge tutarsizligi!")

    blocked = trav < 0.5
    if blocked.any():
        blocked_cost = cost[blocked]
        inf_ratio = np.mean(np.isinf(blocked_cost))
        print(f"  Bloklu hucrelerde INF cost orani: {inf_ratio:.3f}")
        if inf_ratio > 0.99:
            print("  DOGRU: Hard-block mask ile cost grid ayrik tutuluyor.")
        else:
            print("  UYARI: Bloklu hucrelerde cost beklenenden farkli.")


def main() -> None:
    print("=" * 60)
    print("  LunaPath P1 v2.0 — Gorsel Dogrulama")
    print("=" * 60)

    grids = load_grids()
    print(f"\n  {len(grids)} grid yuklendi.\n")

    for name, arr in grids.items():
        print(f"  {name:<25s} shape={str(arr.shape):<14s} dtype={arr.dtype}")

    print_consistency_checks(grids)
    plot_all_grids(grids)

    print("\nDogrulama tamamlandi.")


if __name__ == "__main__":
    main()
