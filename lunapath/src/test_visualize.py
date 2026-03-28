#!/usr/bin/env python3
"""
LunaPath P1 – Görsel Doğrulama Scripti
=======================================
process_lunar_data.py tarafından üretilen grid'leri yükler ve
2×2 subplot ile görselleştirerek verinin tutarlılığını doğrular.

Kontrol listesi:
  - Dik yamaçlar düşük traversability veriyor mu?
  - PSR maskesi mantıklı bölgeleri işaretliyor mu?
  - Yükseklik haritası jeolojik olarak tutarlı mı?
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

# ─── Yollar ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def load_grids() -> dict[str, np.ndarray]:
    """İşlenmiş grid dosyalarını yükler."""
    names = [
        "elevation_grid",
        "slope_grid",
        "psr_mask",
        "traversability_grid",
        "thermal_risk_grid",
    ]
    grids = {}
    for name in names:
        path = PROCESSED_DIR / f"{name}.npy"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} bulunamadı. Önce process_lunar_data.py çalıştırın."
            )
        grids[name] = np.load(path, allow_pickle=False)
    return grids


def plot_main_grids(grids: dict[str, np.ndarray]) -> None:
    """Elevation, slope, PSR mask ve traversability'yi 2×2 subplot ile çizer."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    fig.suptitle("LunaPath P1 – Veri Doğrulama Görselleştirmesi", fontsize=16, fontweight="bold")

    # Elevation
    ax = axes[0, 0]
    im = ax.imshow(grids["elevation_grid"], cmap="terrain", aspect="equal")
    ax.set_title("Yükseklik (m)")
    fig.colorbar(im, ax=ax, label="metre", shrink=0.8)

    # Slope
    ax = axes[0, 1]
    im = ax.imshow(grids["slope_grid"], cmap="YlOrRd", aspect="equal")
    ax.set_title("Eğim (derece)")
    fig.colorbar(im, ax=ax, label="derece", shrink=0.8)

    # PSR Mask
    ax = axes[1, 0]
    im = ax.imshow(grids["psr_mask"].astype(np.uint8), cmap="Blues", aspect="equal", vmin=0, vmax=1)
    ax.set_title("PSR Maskesi (mavi = gölge riski)")
    fig.colorbar(im, ax=ax, label="True/False", shrink=0.8)

    # Traversability
    ax = axes[1, 1]
    im = ax.imshow(grids["traversability_grid"], cmap="RdYlGn", aspect="equal", vmin=0, vmax=1)
    ax.set_title("Geçilebilirlik (0=imkansız, 1=kolay)")
    fig.colorbar(im, ax=ax, label="skor", shrink=0.8)

    plt.tight_layout()
    out_path = PROCESSED_DIR / "validation_plot.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"✓ Görsel kaydedildi → {out_path}")
    plt.show()


def plot_thermal_risk(grids: dict[str, np.ndarray]) -> None:
    """Termal risk grid'ini ayrı bir figür olarak çizer."""
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(grids["thermal_risk_grid"], cmap="hot", aspect="equal", vmin=0, vmax=1)
    ax.set_title("Termal Risk Grid (0=düşük, 1=yüksek)", fontsize=14)
    fig.colorbar(im, ax=ax, label="risk skoru", shrink=0.8)
    plt.tight_layout()
    out_path = PROCESSED_DIR / "thermal_risk_plot.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"✓ Termal risk görseli kaydedildi → {out_path}")
    plt.show()


def print_consistency_checks(grids: dict[str, np.ndarray]) -> None:
    """Temel tutarlılık kontrollerini yazdırır."""
    slope = grids["slope_grid"]
    trav = grids["traversability_grid"]

    steep_mask = slope > 30
    if steep_mask.any():
        avg_trav_steep = np.nanmean(trav[steep_mask])
        avg_trav_flat = np.nanmean(trav[~steep_mask & ~np.isnan(slope)])
        print(f"\n─── Tutarlılık Kontrolü ───")
        print(f"  Dik (>30°) bölgelerde ort. geçilebilirlik : {avg_trav_steep:.3f}")
        print(f"  Düz (≤30°) bölgelerde ort. geçilebilirlik : {avg_trav_flat:.3f}")
        if avg_trav_steep < avg_trav_flat:
            print("  ✓ DOĞRU: Dik yamaçlar daha düşük geçilebilirlik veriyor.")
        else:
            print("  ✗ UYARI: Tutarsızlık tespit edildi!")
    else:
        print("  (!) 30° üzeri eğim bulunamadı, kontrol atlanıyor.")

    psr = grids["psr_mask"]
    elev = grids["elevation_grid"]
    if psr.any():
        avg_elev_psr = np.nanmean(elev[psr])
        avg_elev_non = np.nanmean(elev[~psr])
        print(f"  PSR bölgelerinde ort. yükseklik  : {avg_elev_psr:.1f} m")
        print(f"  PSR dışında ort. yükseklik       : {avg_elev_non:.1f} m")
        if avg_elev_psr < avg_elev_non:
            print("  ✓ DOĞRU: PSR bölgeleri daha alçak (beklenen).")
        else:
            print("  ✗ UYARI: PSR yükseklik tutarsızlığı!")


def main() -> None:
    print("=" * 60)
    print("  LunaPath P1 – Görsel Doğrulama")
    print("=" * 60)

    grids = load_grids()
    print(f"\n✓ {len(grids)} grid yüklendi.\n")

    for name, arr in grids.items():
        print(f"  {name:<25s} shape={str(arr.shape):<14s} dtype={arr.dtype}")

    print_consistency_checks(grids)
    plot_main_grids(grids)
    plot_thermal_risk(grids)

    print("\nDoğrulama tamamlandı ✓")


if __name__ == "__main__":
    main()
