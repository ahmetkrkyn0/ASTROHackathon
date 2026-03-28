#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Cevre Analiz Paneli (Dashboard)
===================================================
data/processed/ altindaki 6 grid'i ve metadata'yi yukleyerek
profesyonel bir 2x3 subplot dashboard uretir.

Calistirma:
    cd lunapath/src
    python visualize_processed_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# --- Yollar ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def load_all() -> tuple[dict[str, np.ndarray], dict]:
    """Grid'leri ve metadata'yi yukler."""
    grid_names = [
        "elevation_grid",
        "slope_grid",
        "aspect_grid",
        "shadow_ratio_grid",
        "thermal_grid",
        "traversability_grid",
    ]
    grids = {}
    for name in grid_names:
        p = PROCESSED_DIR / f"{name}.npy"
        if not p.exists():
            raise FileNotFoundError(
                f"{p} bulunamadi — once process_lunar_data.py calistirin."
            )
        grids[name] = np.load(p, allow_pickle=False)

    with open(PROCESSED_DIR / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)

    return grids, meta


def _metre_extent(meta: dict) -> list[float]:
    """imshow extent: [x_min, x_max, y_max, y_min] metre cinsinden."""
    rows, cols = meta["shape"]
    res = meta["resolution_m"]
    return [0, cols * res, rows * res, 0]


def build_dashboard(grids: dict[str, np.ndarray], meta: dict) -> None:
    """6-panelli dashboard figuru olusturur."""

    res = meta["resolution_m"]
    rows, cols = meta["shape"]
    extent = _metre_extent(meta)

    # --- Figur ---------------------------------------------------------------
    fig = plt.figure(figsize=(22, 15), facecolor="#0e1117")
    fig.subplots_adjust(left=0.05, right=0.82, top=0.92, bottom=0.05,
                        wspace=0.25, hspace=0.30)

    title_color = "#e6edf3"
    label_color = "#8b949e"
    tick_color = "#6e7681"

    fig.suptitle(
        "LUNAPATH v2.0  ·  Ay Guney Kutbu Cevre Analiz Paneli",
        fontsize=20, fontweight="bold", color=title_color, y=0.97,
    )

    axes = fig.subplots(2, 3)

    for ax in axes.flat:
        ax.set_facecolor("#161b22")
        ax.tick_params(colors=tick_color, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_xlabel("Mesafe (m)", fontsize=8, color=label_color)
        ax.set_ylabel("Mesafe (m)", fontsize=8, color=label_color)

    elev = grids["elevation_grid"]
    slope = grids["slope_grid"]
    aspect = grids["aspect_grid"]
    shadow = grids["shadow_ratio_grid"]
    thermal = grids["thermal_grid"]
    trav = grids["traversability_grid"]

    # Panel 1: Yukseklik + egim konturlari
    ax1 = axes[0, 0]
    im1 = ax1.imshow(elev, cmap="terrain", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb1 = fig.colorbar(im1, ax=ax1, shrink=0.82, pad=0.02)
    cb1.set_label("m", fontsize=8, color=label_color)
    cb1.ax.tick_params(colors=tick_color, labelsize=6)
    y_coords = np.linspace(extent[3], extent[2], rows)
    x_coords = np.linspace(extent[0], extent[1], cols)
    X, Y = np.meshgrid(x_coords, y_coords)
    ax1.contour(X, Y, slope, levels=[15, 25],
                colors=["#ffffff55", "#ff444488"], linewidths=0.6, linestyles="dashed")
    ax1.set_title("Yukseklik (kontur: egim)", fontsize=11, color=title_color, pad=6)

    # Panel 2: Egim
    ax2 = axes[0, 1]
    im2 = ax2.imshow(slope, cmap="magma", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb2 = fig.colorbar(im2, ax=ax2, shrink=0.82, pad=0.02)
    cb2.set_label("derece", fontsize=8, color=label_color)
    cb2.ax.tick_params(colors=tick_color, labelsize=6)
    ax2.set_title("Egim Haritasi", fontsize=11, color=title_color, pad=6)

    # Panel 3: Aspect (Baki Yonu)
    ax3 = axes[0, 2]
    im3 = ax3.imshow(aspect, cmap="hsv", extent=extent, aspect="equal",
                     vmin=0, vmax=360, interpolation="bilinear")
    cb3 = fig.colorbar(im3, ax=ax3, shrink=0.82, pad=0.02)
    cb3.set_label("derece", fontsize=8, color=label_color)
    cb3.ax.tick_params(colors=tick_color, labelsize=6)
    ax3.set_title("Baki Yonu (0=K, 90=D)", fontsize=11, color=title_color, pad=6)

    # Panel 4: Shadow Ratio
    ax4 = axes[1, 0]
    im4 = ax4.imshow(shadow, cmap="gray_r", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="bilinear")
    cb4 = fig.colorbar(im4, ax=ax4, shrink=0.82, pad=0.02)
    cb4.set_label("oran", fontsize=8, color=label_color)
    cb4.ax.tick_params(colors=tick_color, labelsize=6)
    ax4.set_title("Golge Orani (1=karanlik)", fontsize=11, color=title_color, pad=6)

    # Panel 5: Thermal
    ax5 = axes[1, 1]
    im5 = ax5.imshow(thermal, cmap="coolwarm", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb5 = fig.colorbar(im5, ax=ax5, shrink=0.82, pad=0.02)
    cb5.set_label("C", fontsize=8, color=label_color)
    cb5.ax.tick_params(colors=tick_color, labelsize=6)
    ax5.set_title("Yuzey Sicakligi (C)", fontsize=11, color=title_color, pad=6)

    # Panel 6: Traversability
    ax6 = axes[1, 2]
    im6 = ax6.imshow(trav, cmap="RdYlGn", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="nearest")
    cb6 = fig.colorbar(im6, ax=ax6, shrink=0.82, pad=0.02, ticks=[0, 1])
    cb6.ax.set_yticklabels(["Gecilmez", "Gecilir"], fontsize=7, color=label_color)
    cb6.ax.tick_params(colors=tick_color, labelsize=6)
    passable_pct = 100.0 * np.nansum(trav) / trav.size
    ax6.set_title(f"Gecilebilirlik ({passable_pct:.1f}% gecilir)",
                  fontsize=11, color=title_color, pad=6)

    # --- Bilgi notu (sag panel) ----------------------------------------------
    origin_x = meta["origin"]["x"]
    origin_y = meta["origin"]["y"]
    total_km = rows * res / 1000

    info_lines = [
        "--- META VERI ---",
        "",
        f"Merkez Koordinat",
        f"  X : {origin_x:,.0f} m",
        f"  Y : {origin_y:,.0f} m",
        "",
        f"Cozunurluk : {res:.0f} m/piksel",
        f"Grid Boyutu: {rows} x {cols}",
        f"Toplam Alan: {total_km:.0f} x {total_km:.0f} km",
        "",
        "--- ISTATISTIKLER ---",
        "",
        f"Yukseklik",
        f"  min : {np.nanmin(elev):>+9.1f} m",
        f"  max : {np.nanmax(elev):>+9.1f} m",
        "",
        f"Egim",
        f"  min : {np.nanmin(slope):>7.2f} deg",
        f"  max : {np.nanmax(slope):>7.2f} deg",
        "",
        f"Sicaklik",
        f"  min : {np.nanmin(thermal):>+9.2f} C",
        f"  max : {np.nanmax(thermal):>+9.2f} C",
        f"  ort : {np.nanmean(thermal):>+9.2f} C",
        "",
        f"Gecilebilirlik: %{passable_pct:.1f}",
        "",
        "--- PROJEKSIYON ---",
        "",
        "Moon 2015 Polar",
        "Stereographic (Guney)",
    ]

    fig.text(
        0.84, 0.50,
        "\n".join(info_lines),
        fontsize=8, fontfamily="monospace", color="#c9d1d9",
        verticalalignment="center",
        bbox=dict(boxstyle="round,pad=0.8", facecolor="#161b22",
                  edgecolor="#30363d", linewidth=1.5),
    )

    # --- Kaydet & Goster -----------------------------------------------------
    out_path = PROCESSED_DIR / "environment_dashboard.png"
    fig.savefig(out_path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"Dashboard kaydedildi: {out_path}")
    plt.show()


def main() -> None:
    grids, meta = load_all()
    print(f"Yuklu grid sayisi: {len(grids)}")
    for name, arr in grids.items():
        print(f"  {name:<25s} {str(arr.shape):<14s} dtype={arr.dtype}")
    build_dashboard(grids, meta)


if __name__ == "__main__":
    main()
