#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Cevre Analiz Paneli (Dashboard)
===================================================
data/processed/ altindaki 7 grid'i ve metadata'yi yukleyerek
dashboard uretir: 2 satir x 4 panel + altta tam genislikte
DEM Ay yüzeyi (hillshade + regolit renkleri). Ayrica
`lunar_surface_dem.png` ayri kaydedilir.

Calistirma:
    cd lunapath/src
    python visualize_processed_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LightSource, LinearSegmentedColormap

# --- Yollar ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# LRO / regolit görünümüne yakın nötr gri–bej tonlar (terrain yeşili yok)
LUNAR_REGOLITH_CMAP = LinearSegmentedColormap.from_list(
    "lunar_regolith",
    [
        "#050506",
        "#151517",
        "#2a2928",
        "#45423e",
        "#5c5852",
        "#7a746c",
        "#9a9288",
        "#b8afa4",
        "#d4cdc3",
    ],
    N=256,
)


def shaded_moon_dem_rgba(
    elevation_m: np.ndarray,
    resolution_m: float,
    *,
    azimuth_deg: float = 292.0,
    altitude_deg: float = 6.5,
    vertical_exaggeration: float = 2.2,
) -> np.ndarray:
    """DEM'i alçak güneş hillshade + regolit renk haritasıyla RGBA'ya çevirir.

    Ay güney kutbuna uygun düşük güneş açısı ve regolit tonları kullanılır;
    klasik 'terrain' yeşili kullanılmaz.
    """
    z = np.asarray(elevation_m, dtype=np.float64)
    valid = np.isfinite(z)
    med = np.nanmedian(z[valid]) if valid.any() else 0.0
    if not np.isfinite(med):
        med = 0.0
    z_work = np.where(valid, z, med)

    ls = LightSource(azdeg=azimuth_deg, altdeg=altitude_deg)
    rgba = ls.shade(
        z_work,
        cmap=LUNAR_REGOLITH_CMAP,
        blend_mode="soft",
        vert_exag=vertical_exaggeration,
        dx=resolution_m,
        dy=resolution_m,
    )
    if not valid.all():
        rgba = np.array(rgba, copy=True)
        rgba[~valid] = (0.03, 0.03, 0.035, 1.0)
    return rgba


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
    """7-grid + bilgi paneli + DEM Ay yüzeyi (gerçekçi tonlar) dashboard."""

    res = meta["resolution_m"]
    rows, cols = meta["shape"]
    extent = _metre_extent(meta)

    title_color = "#e6edf3"
    label_color = "#8b949e"
    tick_color = "#6e7681"

    # Eşit panel alanı: 4 sütun ve 3 satır aynı oran; constrained_layout
    # başlık / renk çubukları / etiket çakışmalarını azaltır.
    fig = plt.figure(figsize=(28, 20), facecolor="#0e1117", layout="constrained")
    gs = fig.add_gridspec(
        3,
        4,
        width_ratios=[1.0, 1.0, 1.0, 1.0],
        height_ratios=[1.0, 1.0, 1.0],
    )

    fig.suptitle(
        "LUNAPATH v2.0  ·  Ay Guney Kutbu Cevre Analiz Paneli",
        fontsize=18,
        fontweight="bold",
        color=title_color,
    )
    fig.get_layout_engine().set(rect=(0.02, 0.02, 0.96, 0.94))

    # Sabit GridSpec kullanimi, bilgi paneli ve cost panelinin daralmasini engeller.
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    info_ax = fig.add_subplot(gs[0, 3])
    ax4 = fig.add_subplot(gs[1, 0])
    ax5 = fig.add_subplot(gs[1, 1])
    ax6 = fig.add_subplot(gs[1, 2])
    ax7 = fig.add_subplot(gs[1, 3])
    ax_moon = fig.add_subplot(gs[2, :])

    # Renk çubuğu: tüm panellerde aynı shrink/pad → görsel alanlar dengelenir
    _cb_shrink = 0.72
    _cb_pad = 0.045

    for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7]:
        ax.set_facecolor("#161b22")
        ax.tick_params(colors=tick_color, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.set_xlabel("Mesafe (m)", fontsize=8, color=label_color, labelpad=6)
        ax.set_ylabel("Mesafe (m)", fontsize=8, color=label_color, labelpad=6)

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
    cb1 = fig.colorbar(im1, ax=ax1, shrink=_cb_shrink, pad=_cb_pad)
    cb1.set_label("m", fontsize=8, color=label_color)
    cb1.ax.tick_params(colors=tick_color, labelsize=6)
    y_coords = np.linspace(extent[3], extent[2], rows)
    x_coords = np.linspace(extent[0], extent[1], cols)
    X, Y = np.meshgrid(x_coords, y_coords)
    ax1.contour(X, Y, slope, levels=[15, 25],
                colors=["#ffffff55", "#ff444488"], linewidths=0.6, linestyles="dashed")
    ax1.set_title("Yukseklik (kontur: egim)", fontsize=10, color=title_color, pad=10)

    # Panel 2: Egim
    im2 = ax2.imshow(slope, cmap="magma", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb2 = fig.colorbar(im2, ax=ax2, shrink=_cb_shrink, pad=_cb_pad)
    cb2.set_label("derece", fontsize=8, color=label_color)
    cb2.ax.tick_params(colors=tick_color, labelsize=6)
    ax2.set_title("Egim Haritasi", fontsize=10, color=title_color, pad=10)

    # Panel 3: Aspect (Baki Yonu)
    im3 = ax3.imshow(aspect, cmap="hsv", extent=extent, aspect="equal",
                     vmin=0, vmax=360, interpolation="bilinear")
    cb3 = fig.colorbar(im3, ax=ax3, shrink=_cb_shrink, pad=_cb_pad)
    cb3.set_label("derece", fontsize=8, color=label_color)
    cb3.ax.tick_params(colors=tick_color, labelsize=6)
    ax3.set_title("Baki Yonu (0=K, 90=D)", fontsize=10, color=title_color, pad=10)

    # Panel 4: Shadow Ratio
    im4 = ax4.imshow(shadow, cmap="gray_r", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="bilinear")
    cb4 = fig.colorbar(im4, ax=ax4, shrink=_cb_shrink, pad=_cb_pad)
    cb4.set_label("oran", fontsize=8, color=label_color)
    cb4.ax.tick_params(colors=tick_color, labelsize=6)
    ax4.set_title("Golge Orani (1=karanlik)", fontsize=10, color=title_color, pad=10)

    # Panel 5: Thermal
    im5 = ax5.imshow(thermal, cmap="coolwarm", extent=extent, aspect="equal",
                     interpolation="bilinear")
    cb5 = fig.colorbar(im5, ax=ax5, shrink=_cb_shrink, pad=_cb_pad)
    cb5.set_label("C", fontsize=8, color=label_color)
    cb5.ax.tick_params(colors=tick_color, labelsize=6)
    ax5.set_title("Yuzey Sicakligi (C)", fontsize=10, color=title_color, pad=10)

    # Panel 6: Traversability
    im6 = ax6.imshow(trav, cmap="RdYlGn", extent=extent, aspect="equal",
                     vmin=0, vmax=1, interpolation="nearest")
    cb6 = fig.colorbar(im6, ax=ax6, shrink=_cb_shrink, pad=_cb_pad, ticks=[0, 1])
    cb6.ax.set_yticklabels(["Gecilmez", "Gecilir"], fontsize=7, color=label_color)
    cb6.ax.tick_params(colors=tick_color, labelsize=6)
    passable_pct = 100.0 * np.nansum(trav) / trav.size
    ax6.set_title(f"Gecilebilirlik ({passable_pct:.1f}% gecilir)",
                  fontsize=10, color=title_color, pad=10)

    # Panel 7: Weighted cost grid
    masked_cost = np.where(np.isfinite(cost), cost, np.nan)
    im7 = ax7.imshow(masked_cost, cmap="viridis", extent=extent, aspect="equal",
                     interpolation="nearest")
    cb7 = fig.colorbar(im7, ax=ax7, shrink=_cb_shrink, pad=_cb_pad)
    cb7.set_label("cost", fontsize=8, color=label_color)
    cb7.ax.tick_params(colors=tick_color, labelsize=6)
    ax7.set_title("Weighted Cost Grid", fontsize=10, color=title_color, pad=10)

    # --- Panel 8: DEM — Ay yüzeyi (hillshade + regolit renkleri) ------------
    ax_moon.set_facecolor("#161b22")
    ax_moon.tick_params(colors=tick_color, labelsize=7)
    for spine in ax_moon.spines.values():
        spine.set_color("#30363d")
    ax_moon.set_xlabel("Mesafe (m)", fontsize=8, color=label_color, labelpad=6)
    ax_moon.set_ylabel("Mesafe (m)", fontsize=8, color=label_color, labelpad=6)
    moon_rgba = shaded_moon_dem_rgba(elev, res)
    ax_moon.imshow(
        moon_rgba,
        extent=extent,
        aspect="equal",
        origin="upper",
        interpolation="bilinear",
    )
    ax_moon.set_title(
        "DEM — Ay yüzeyi (hillshade, regolit; güney kutbu, düşük güneş)",
        fontsize=10,
        color=title_color,
        pad=10,
    )

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
        0.99,
        "META VERI & AGIRLIKLAR",
        ha="center",
        va="top",
        fontsize=10,
        fontweight="bold",
        color=title_color,
    )
    info_rows = [
        ("Merkez X", f"{origin_x:,.0f} m"),
        ("Merkez Y", f"{origin_y:,.0f} m"),
        ("Cozunurluk", f"{res:.0f} m/px"),
        ("Grid", f"{rows} x {cols}"),
        ("Alan", f"{total_km:.0f} x {total_km:.0f} km"),
        ("Yuk. min", f"{np.nanmin(elev):+.1f} m"),
        ("Yuk. max", f"{np.nanmax(elev):+.1f} m"),
        ("Egim min", f"{np.nanmin(slope):.2f} deg"),
        ("Egim max", f"{np.nanmax(slope):.2f} deg"),
        ("T min", f"{np.nanmin(thermal):+.2f} C"),
        ("T max", f"{np.nanmax(thermal):+.2f} C"),
        ("T ort", f"{np.nanmean(thermal):+.2f} C"),
        ("Cost ort", f"{cost_mean:.4f}"),
        ("Cost max", f"{cost_max:.4f}"),
        ("Gecilir %", f"{passable_pct:.1f}"),
        ("w_slope", f"{weight_info.get('w_slope', float('nan')):.3f}"),
        ("w_energy", f"{weight_info.get('w_energy', float('nan')):.3f}"),
        ("w_shadow", f"{weight_info.get('w_shadow', float('nan')):.3f}"),
        ("w_thermal", f"{weight_info.get('w_thermal', float('nan')):.3f}"),
        ("Projeksiyon", "Moon 2015 Polar Stereog. (S)"),
    ]

    # Tablo: başlık ile çakışmayı önlemek için üstte boşluk; satır yüksekliği scale ile artırılır
    table = info_ax.table(
        cellText=[[k, v] for k, v in info_rows],
        colLabels=["Alan", "Deger"],
        cellLoc="left",
        colLoc="left",
        bbox=[0.04, 0.03, 0.92, 0.78],
        colWidths=[0.36, 0.60],
    )
    table.auto_set_font_size(False)
    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_text_props(color=title_color, weight="bold", fontsize=8)
            cell.set_facecolor("#0d1117")
        else:
            cell.set_text_props(color="#c9d1d9", fontsize=7)
            cell.set_facecolor("#161b22")
        cell.set_edgecolor("#30363d")
        cell.set_linewidth(0.5)
    # Yüksek scale = satırlar arası dikey nefes alanı (iç içe geçmeyi önler)
    table.scale(1.0, 1.72)

    # --- Kaydet & Goster -----------------------------------------------------
    out_path = PROCESSED_DIR / "environment_dashboard.png"
    fig.savefig(
        out_path,
        dpi=180,
        facecolor=fig.get_facecolor(),
        pad_inches=0.2,
    )
    print(f"Dashboard kaydedildi: {out_path}")

    # Ayüstü DEM — ayrı yüksek çözünürlüklü çıktı (sunum / rapor)
    fig_moon, ax_only = plt.subplots(
        figsize=(11, 11),
        facecolor="#0e1117",
        layout="constrained",
    )
    fig_moon.get_layout_engine().set(rect=(0.08, 0.08, 0.90, 0.88))
    ax_only.set_facecolor("#161b22")
    ax_only.imshow(
        moon_rgba,
        extent=extent,
        aspect="equal",
        origin="upper",
        interpolation="bilinear",
    )
    ax_only.set_xlabel("Mesafe (m)", fontsize=10, color=label_color, labelpad=8)
    ax_only.set_ylabel("Mesafe (m)", fontsize=10, color=label_color, labelpad=8)
    ax_only.tick_params(colors=tick_color, labelsize=8)
    for spine in ax_only.spines.values():
        spine.set_color("#30363d")
    ax_only.set_title(
        "LunaPath — LOLA DEM (Ay yüzeyi görünümü)",
        fontsize=13,
        fontweight="bold",
        color=title_color,
        pad=14,
    )
    moon_path = PROCESSED_DIR / "lunar_surface_dem.png"
    fig_moon.savefig(
        moon_path,
        dpi=200,
        facecolor=fig_moon.get_facecolor(),
        bbox_inches="tight",
        pad_inches=0.2,
    )
    print(f"Ay yüzeyi DEM görseli kaydedildi: {moon_path}")
    plt.close(fig_moon)

    plt.show()


def main() -> None:
    grids, meta = load_all()
    print(f"Yuklu grid sayisi: {len(grids)}")
    for name, arr in grids.items():
        print(f"  {name:<25s} {str(arr.shape):<14s} dtype={arr.dtype}")
    build_dashboard(grids, meta)


if __name__ == "__main__":
    main()
