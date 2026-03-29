#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Cevre Analiz Paneli (Dashboard)
===================================================
data/processed/ altindaki 7 grid'i ve metadata'yi yukleyerek
profesyonel bir 2x4 subplot dashboard uretir.

Calistirma:
    cd lunapath/src
    python visualize_processed_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
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
        "cost_grid",
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
    """7-grid + bilgi paneli dashboard figuru olusturur."""

    res = meta["resolution_m"]
    rows, cols = meta["shape"]
    extent = _metre_extent(meta)

    # --- Figur ---------------------------------------------------------------
    fig = plt.figure(figsize=(24, 14), facecolor="#0e1117")
    gs = fig.add_gridspec(2, 4, width_ratios=[1.0, 1.0, 1.0, 1.15], wspace=0.24, hspace=0.28)

    title_color = "#e6edf3"
    label_color = "#8b949e"
    tick_color = "#6e7681"

    fig.suptitle(
        "LUNAPATH v2.0  ·  Ay Guney Kutbu Cevre Analiz Paneli",
        fontsize=20, fontweight="bold", color=title_color, y=0.97,
    )

    # Sabit GridSpec kullanimi, bilgi paneli ve cost panelinin daralmasini engeller.
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    info_ax = fig.add_subplot(gs[0, 3])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])
    ax7 = fig.add_subplot(gs[1, 3])

    for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7]:
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
    cost = grids["cost_grid"]

    # Panel 1: Yukseklik + egim konturlari
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
    im2 = ax2.imshow(slope, cmap="magma", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb2 = fig.colorbar(im2, ax=ax2, shrink=0.82, pad=0.02)
    cb2.set_label("derece", fontsize=8, color=label_color)
    cb2.ax.tick_params(colors=tick_color, labelsize=6)
    ax2.set_title("Egim Haritasi", fontsize=11, color=title_color, pad=6)

    # Panel 3: Aspect (Baki Yonu)
    im3 = ax3.imshow(aspect, cmap="hsv", extent=extent, aspect="equal",
                     vmin=0, vmax=360, interpolation="bilinear")
    cb3 = fig.colorbar(im3, ax=ax3, shrink=0.82, pad=0.02)
    cb3.set_label("derece", fontsize=8, color=label_color)
    cb3.ax.tick_params(colors=tick_color, labelsize=6)
    ax3.set_title("Baki Yonu (0=K, 90=D)", fontsize=11, color=title_color, pad=6)

    # Panel 4: Shadow Ratio
    im4 = ax4.imshow(shadow, cmap="gray_r", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="bilinear")
    cb4 = fig.colorbar(im4, ax=ax4, shrink=0.82, pad=0.02)
    cb4.set_label("oran", fontsize=8, color=label_color)
    cb4.ax.tick_params(colors=tick_color, labelsize=6)
    ax4.set_title("Golge Orani (1=karanlik)", fontsize=11, color=title_color, pad=6)

    # Panel 5: Thermal
    im5 = ax5.imshow(thermal, cmap="coolwarm", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb5 = fig.colorbar(im5, ax=ax5, shrink=0.82, pad=0.02)
    cb5.set_label("C", fontsize=8, color=label_color)
    cb5.ax.tick_params(colors=tick_color, labelsize=6)
    ax5.set_title("Yuzey Sicakligi (C)", fontsize=11, color=title_color, pad=6)

    # Panel 6: Traversability
    im6 = ax6.imshow(trav, cmap="RdYlGn", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="nearest")
    cb6 = fig.colorbar(im6, ax=ax6, shrink=0.82, pad=0.02, ticks=[0, 1])
    cb6.ax.set_yticklabels(["Gecilmez", "Gecilir"], fontsize=7, color=label_color)
    cb6.ax.tick_params(colors=tick_color, labelsize=6)
    passable_pct = 100.0 * np.nansum(trav) / trav.size
    ax6.set_title(f"Gecilebilirlik ({passable_pct:.1f}% gecilir)",
                  fontsize=11, color=title_color, pad=6)

    # Panel 7: Weighted cost grid
    masked_cost = np.where(np.isfinite(cost), cost, np.nan)
    im7 = ax7.imshow(masked_cost, cmap="viridis", extent=extent, aspect="auto",
                     interpolation="nearest")
    cb7 = fig.colorbar(im7, ax=ax7, shrink=0.82, pad=0.02)
    cb7.set_label("cost", fontsize=8, color=label_color)
    cb7.ax.tick_params(colors=tick_color, labelsize=6)
    ax7.set_title("Weighted Cost Grid", fontsize=11, color=title_color, pad=6)

    # --- Bilgi notu (ayri panel) ---------------------------------------------
    info_ax.set_facecolor("#161b22")
    info_ax.axis("off")
    origin_x = meta["origin"]["x"]
    origin_y = meta["origin"]["y"]
    total_km = rows * res / 1000
    finite_cost = cost[np.isfinite(cost)]
    cost_mean = float(np.mean(finite_cost)) if finite_cost.size > 0 else float("nan")
    cost_max = float(np.max(finite_cost)) if finite_cost.size > 0 else float("nan")
    weight_info = meta.get("cost_weights", {})

    info_ax.text(
        0.5,
        0.98,
        "META VERI & AGIRLIKLAR",
        ha="center",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=title_color,
    )
    info_rows = [
        ("Merkez X", f"{origin_x:,.0f} m"),
        ("Merkez Y", f"{origin_y:,.0f} m"),
        ("Cozunurluk", f"{res:.0f} m/piksel"),
        ("Grid Boyutu", f"{rows} x {cols}"),
        ("Toplam Alan", f"{total_km:.0f} x {total_km:.0f} km"),
        ("Yukseklik min", f"{np.nanmin(elev):>+9.1f} m"),
        ("Yukseklik max", f"{np.nanmax(elev):>+9.1f} m"),
        ("Egim min", f"{np.nanmin(slope):>7.2f} deg"),
        ("Egim max", f"{np.nanmax(slope):>7.2f} deg"),
        ("Sicaklik min", f"{np.nanmin(thermal):>+9.2f} C"),
        ("Sicaklik max", f"{np.nanmax(thermal):>+9.2f} C"),
        ("Sicaklik ort", f"{np.nanmean(thermal):>+9.2f} C"),
        ("Maliyet ort", f"{cost_mean:>9.4f}"),
        ("Maliyet max", f"{cost_max:>9.4f}"),
        ("Gecilebilirlik", f"%{passable_pct:.1f}"),
        ("w_slope", f"{weight_info.get('w_slope', float('nan')):.3f}"),
        ("w_energy", f"{weight_info.get('w_energy', float('nan')):.3f}"),
        ("w_shadow", f"{weight_info.get('w_shadow', float('nan')):.3f}"),
        ("w_thermal", f"{weight_info.get('w_thermal', float('nan')):.3f}"),
        ("Projeksiyon", "Moon 2015 Polar"),
        ("", "Stereographic (Guney)"),
    ]

    table = info_ax.table(
        cellText=[[k, v] for k, v in info_rows],
        colLabels=["Alan", "Deger"],
        cellLoc="left",
        colLoc="left",
        bbox=[0.02, 0.02, 0.96, 0.90],
        colWidths=[0.42, 0.54],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.0, 1.18)
    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(color=title_color, weight="bold")
            cell.set_facecolor("#0d1117")
        else:
            cell.set_text_props(color="#c9d1d9")
            cell.set_facecolor("#161b22")
        cell.set_edgecolor("#30363d")
        cell.set_linewidth(0.6)

    # --- Kaydet & Goster -----------------------------------------------------
    out_path = PROCESSED_DIR / "environment_dashboard.png"
    fig.savefig(out_path, dpi=180, facecolor=fig.get_facecolor())
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
