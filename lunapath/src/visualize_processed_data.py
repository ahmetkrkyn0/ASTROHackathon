#!/usr/bin/env python3
"""
LunaPath P1 – Çevre Analiz Paneli (Dashboard)
==============================================
data/processed/ altındaki grid'leri ve metadata'yı yükleyerek
profesyonel bir 2×2 subplot dashboard üretir.

Çalıştırma:
    cd lunapath/src
    python visualize_processed_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from matplotlib.patches import FancyBboxPatch

# ─── Yollar ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def load_all() -> tuple[dict[str, np.ndarray], dict]:
    """Grid'leri ve metadata'yı yükler."""
    grid_names = [
        "elevation_grid",
        "slope_grid",
        "psr_mask",
        "traversability_grid",
    ]
    grids = {}
    for name in grid_names:
        p = PROCESSED_DIR / f"{name}.npy"
        if not p.exists():
            raise FileNotFoundError(f"{p} bulunamadı – önce process_lunar_data.py çalıştırın.")
        grids[name] = np.load(p, allow_pickle=False)

    with open(PROCESSED_DIR / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)

    return grids, meta


def _metre_extent(meta: dict) -> list[float]:
    """imshow extent parametresi: [x_min, x_max, y_max, y_min] metre cinsinden
    lokal 0-40 000 m skalasına dönüştürülmüş."""
    rows, cols = meta["shape"]
    res = meta["resolution_m"]
    return [0, cols * res, rows * res, 0]


def _format_km(val: float, _pos) -> str:
    """Eksen etiketlerini km'ye çevirir (isteğe bağlı)."""
    return f"{val / 1000:.0f}"


def build_dashboard(grids: dict[str, np.ndarray], meta: dict) -> None:
    """Ana dashboard figürünü oluşturur."""

    res = meta["resolution_m"]
    rows, cols = meta["shape"]
    extent = _metre_extent(meta)

    # ── Figür ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(18, 15), facecolor="#0e1117")
    fig.subplots_adjust(left=0.06, right=0.82, top=0.92, bottom=0.06, wspace=0.22, hspace=0.28)

    title_color = "#e6edf3"
    label_color = "#8b949e"
    tick_color = "#6e7681"

    fig.suptitle(
        "LUNAPATH  ·  Ay Güney Kutbu Çevre Analiz Paneli",
        fontsize=20,
        fontweight="bold",
        color=title_color,
        y=0.97,
    )

    axes = fig.subplots(2, 2)

    for ax in axes.flat:
        ax.set_facecolor("#161b22")
        ax.tick_params(colors=tick_color, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_xlabel("Mesafe (m)", fontsize=9, color=label_color)
        ax.set_ylabel("Mesafe (m)", fontsize=9, color=label_color)

    km_formatter = ticker.FuncFormatter(_format_km)

    # ── Panel 1: Yükseklik + eğim konturları ────────────────────────────────
    ax1 = axes[0, 0]
    elev = grids["elevation_grid"]
    slope = grids["slope_grid"]

    im1 = ax1.imshow(elev, cmap="terrain", extent=extent, aspect="equal", interpolation="bilinear")
    cb1 = fig.colorbar(im1, ax=ax1, shrink=0.82, pad=0.02)
    cb1.set_label("Yükseklik (m)", fontsize=9, color=label_color)
    cb1.ax.tick_params(colors=tick_color, labelsize=7)

    y_coords = np.linspace(extent[3], extent[2], rows)
    x_coords = np.linspace(extent[0], extent[1], cols)
    X, Y = np.meshgrid(x_coords, y_coords)
    ax1.contour(X, Y, slope, levels=[15, 25, 30], colors=["#ffffff55", "#ffaa0066", "#ff444488"],
                linewidths=0.6, linestyles="dashed")

    ax1.set_title("Yükseklik Haritası  (kontur: eğim)", fontsize=12, color=title_color, pad=8)

    # ── Panel 2: Eğim ───────────────────────────────────────────────────────
    ax2 = axes[0, 1]
    im2 = ax2.imshow(slope, cmap="magma", extent=extent, aspect="equal", interpolation="bilinear")
    cb2 = fig.colorbar(im2, ax=ax2, shrink=0.82, pad=0.02)
    cb2.set_label("Eğim (°)", fontsize=9, color=label_color)
    cb2.ax.tick_params(colors=tick_color, labelsize=7)
    ax2.set_title("Eğim Haritası", fontsize=12, color=title_color, pad=8)

    # ── Panel 3: PSR Maskesi ─────────────────────────────────────────────────
    ax3 = axes[1, 0]
    psr = grids["psr_mask"].astype(np.float32)
    im3 = ax3.imshow(psr, cmap="bone", extent=extent, aspect="equal", vmin=0, vmax=1,
                     interpolation="nearest")
    cb3 = fig.colorbar(im3, ax=ax3, shrink=0.82, pad=0.02, ticks=[0, 1])
    cb3.ax.set_yticklabels(["Güvenli", "Gölge"], fontsize=8, color=label_color)
    cb3.ax.tick_params(colors=tick_color, labelsize=7)
    psr_pct = 100.0 * grids["psr_mask"].sum() / grids["psr_mask"].size
    ax3.set_title(f"PSR Gölge Maskesi  ({psr_pct:.1f}% gölge)", fontsize=12, color=title_color, pad=8)

    # ── Panel 4: Geçilebilirlik ──────────────────────────────────────────────
    ax4 = axes[1, 1]
    trav = grids["traversability_grid"]
    im4 = ax4.imshow(trav, cmap="RdYlGn", extent=extent, aspect="equal", vmin=0, vmax=1,
                     interpolation="bilinear")
    cb4 = fig.colorbar(im4, ax=ax4, shrink=0.82, pad=0.02)
    cb4.set_label("Geçilebilirlik Skoru", fontsize=9, color=label_color)
    cb4.ax.tick_params(colors=tick_color, labelsize=7)
    ax4.set_title("Geçilebilirlik  (P2 Path-Planning girdisi)", fontsize=12, color=title_color, pad=8)

    # ── Bilgi Notu (sağ panel) ───────────────────────────────────────────────
    origin_x = meta["origin"]["x"]
    origin_y = meta["origin"]["y"]
    total_km = rows * res / 1000

    info_lines = [
        "─── META VERİ ───",
        "",
        f"Merkez Koordinat",
        f"  X : {origin_x:,.0f} m",
        f"  Y : {origin_y:,.0f} m",
        "",
        f"Çözünürlük : {res:.0f} m/piksel",
        f"Grid Boyutu: {rows} × {cols} piksel",
        f"Toplam Alan: {total_km:.0f} × {total_km:.0f} km",
        "",
        "─── İSTATİSTİKLER ───",
        "",
        f"Yükseklik",
        f"  min : {np.nanmin(elev):>+9.1f} m",
        f"  max : {np.nanmax(elev):>+9.1f} m",
        f"  ort : {np.nanmean(elev):>+9.1f} m",
        "",
        f"Eğim",
        f"  min : {np.nanmin(slope):>7.2f}°",
        f"  max : {np.nanmax(slope):>7.2f}°",
        "",
        f"Geçilebilirlik",
        f"  ort : {np.nanmean(trav):.3f}",
        f"  >0.8: {100*(trav>0.8).sum()/trav.size:.1f}%",
        f"  <0.2: {100*(trav<0.2).sum()/trav.size:.1f}%",
        "",
        f"PSR Gölge : %{psr_pct:.1f}",
        "",
        "─── PROJEKSİYON ───",
        "",
        "Moon 2015 Polar",
        "Stereographic (Güney)",
    ]

    info_text = "\n".join(info_lines)

    fig.text(
        0.84, 0.50,
        info_text,
        fontsize=9,
        fontfamily="monospace",
        color="#c9d1d9",
        verticalalignment="center",
        bbox=dict(
            boxstyle="round,pad=0.8",
            facecolor="#161b22",
            edgecolor="#30363d",
            linewidth=1.5,
        ),
    )

    # ── Kaydet & Göster ──────────────────────────────────────────────────────
    out_path = PROCESSED_DIR / "environment_dashboard.png"
    fig.savefig(out_path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"Dashboard kaydedildi -> {out_path}")
    plt.show()


def main() -> None:
    grids, meta = load_all()
    print(f"Yuklu grid sayisi: {len(grids)}")
    for name, arr in grids.items():
        print(f"  {name:<25s} {str(arr.shape):<14s} dtype={arr.dtype}")
    build_dashboard(grids, meta)


if __name__ == "__main__":
    main()
