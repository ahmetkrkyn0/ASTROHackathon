#!/usr/bin/env python3
"""
LunaPath P1 – Ana Veri İşleme Scripti
======================================
NASA 80MPP GeoTIFF dosyalarını okur, hizalar, en aksiyonlu 500×500 bölgeyi
seçer ve P2/P3/P4/P5 birimlerinin tüketeceği standart grid çıktılarını üretir.

Girdiler  : LDEM (yükseklik), LDSM (eğim), HILL (hillshade) – data/raw/
Çıktılar  : elevation_grid.npy, slope_grid.npy, psr_mask.npy,
            thermal_risk_grid.npy, traversability_grid.npy, metadata.json
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import uniform_filter

# ─── Proje kök dizinleri ─────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # lunapath/
ASTRO_ROOT = PROJECT_ROOT.parent                               # ASTROHackathon/

RAW_DIR = PROJECT_ROOT / "data" / "raw"
if not RAW_DIR.exists() or not any(RAW_DIR.iterdir()):
    RAW_DIR = ASTRO_ROOT / "data" / "raw"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ─── Dosya isimleri ──────────────────────────────────────────────────────────
LDEM_FILE = RAW_DIR / "LDEM_80S_80MPP_ADJ.tiff"
LDSM_FILE = RAW_DIR / "LDSM_80S_80MPP_ADJ.tiff"
HILL_FILE = RAW_DIR / "LDEM_80S_80MPP_ADJ_HILL.tiff"

# ─── Sabitler ────────────────────────────────────────────────────────────────
WINDOW_SIZE = 500
RESOLUTION_M = 80.0
SLOPE_TRAVERSABILITY_LIMIT = 35.0  # derece


# ═══════════════════════════════════════════════════════════════════════════════
# 1) VERİ OKUMA & HİZALAMA
# ═══════════════════════════════════════════════════════════════════════════════

def check_alignment(datasets: dict[str, rasterio.DatasetReader]) -> None:
    """CRS ve bounds uyumluluğunu kontrol eder."""
    names = list(datasets.keys())
    ref_name = names[0]
    ref_ds = datasets[ref_name]

    print("─── Hizalama Kontrolü ───")
    for name in names[1:]:
        ds = datasets[name]

        crs_ok = str(ref_ds.crs) == str(ds.crs)
        bounds_ok = ref_ds.bounds == ds.bounds
        res_ok = ref_ds.res == ds.res

        print(f"  {ref_name} vs {name}:")
        print(f"    CRS eşleşme   : {'✓' if crs_ok else '✗  ' + str(ds.crs)}")
        print(f"    Bounds eşleşme : {'✓' if bounds_ok else '✗'}")
        print(f"    Çözünürlük     : {'✓' if res_ok else '✗'}")

        if not crs_ok:
            print(f"    ⚠ UYARI: CRS farklı – {ref_name}={ref_ds.crs}, {name}={ds.crs}")
        if not bounds_ok:
            print(f"    ⚠ UYARI: Bounds farklı – {ref_name}={ref_ds.bounds}, {name}={ds.bounds}")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
# 2) EN AKSİYONLU BÖLGEYİ BUL (500×500)
# ═══════════════════════════════════════════════════════════════════════════════

def find_action_window(
    dem_ds: rasterio.DatasetReader,
    slope_ds: rasterio.DatasetReader,
    window_size: int = WINDOW_SIZE,
    sample_step: int = 100,
) -> Window:
    """Yükseklik farkı × eğim varyansı açısından en yoğun 500×500 bölgeyi bulur.

    Tüm raster'ı yüklemek yerine, bant-1'i düşük çözünürlükte tarayarak
    aday pencereleri puanlar.
    """
    h, w = dem_ds.height, dem_ds.width
    print(f"Raster boyutu: {w}×{h} piksel")

    if h < window_size or w < window_size:
        raise ValueError(
            f"Raster ({w}×{h}) istenen pencere boyutundan ({window_size}) küçük!"
        )

    overview_factor = 4
    ov_h, ov_w = h // overview_factor, w // overview_factor
    dem_overview = dem_ds.read(
        1,
        out_shape=(ov_h, ov_w),
        resampling=rasterio.enums.Resampling.average,
    ).astype(np.float64)

    slope_overview = slope_ds.read(
        1,
        out_shape=(ov_h, ov_w),
        resampling=rasterio.enums.Resampling.average,
    ).astype(np.float64)

    nodata_dem = dem_ds.nodata
    nodata_slope = slope_ds.nodata
    if nodata_dem is not None:
        dem_overview[dem_overview == nodata_dem] = np.nan
    if nodata_slope is not None:
        slope_overview[slope_overview == nodata_slope] = np.nan

    ov_ws = window_size // overview_factor
    step = max(1, sample_step // overview_factor)

    best_score = -np.inf
    best_r, best_c = 0, 0

    for r in range(0, ov_h - ov_ws, step):
        for c in range(0, ov_w - ov_ws, step):
            dem_patch = dem_overview[r : r + ov_ws, c : c + ov_ws]
            slope_patch = slope_overview[r : r + ov_ws, c : c + ov_ws]

            valid_mask = ~np.isnan(dem_patch) & ~np.isnan(slope_patch)
            if valid_mask.sum() < ov_ws * ov_ws * 0.5:
                continue

            elev_range = np.nanmax(dem_patch) - np.nanmin(dem_patch)
            slope_var = np.nanstd(slope_patch)
            score = elev_range * slope_var

            if score > best_score:
                best_score = score
                best_r, best_c = r, c

    row_off = min(best_r * overview_factor, h - window_size)
    col_off = min(best_c * overview_factor, w - window_size)

    win = Window(col_off=col_off, row_off=row_off, width=window_size, height=window_size)
    print(f"Seçilen pencere: row_off={row_off}, col_off={col_off}, "
          f"boyut={window_size}×{window_size}  (skor={best_score:.2f})")
    return win


# ═══════════════════════════════════════════════════════════════════════════════
# 3) GRİD ÜRETİMİ
# ═══════════════════════════════════════════════════════════════════════════════

def make_elevation_grid(dem_ds: rasterio.DatasetReader, win: Window) -> np.ndarray:
    """Metre cinsinden yükseklik grid'i (float64)."""
    data = dem_ds.read(1, window=win).astype(np.float64)
    nodata = dem_ds.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data


def make_slope_grid(slope_ds: rasterio.DatasetReader, win: Window) -> np.ndarray:
    """Derece cinsinden eğim grid'i (float64)."""
    data = slope_ds.read(1, window=win).astype(np.float64)
    nodata = slope_ds.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data


def make_psr_mask(
    elevation: np.ndarray,
    slope: np.ndarray,
    slope_threshold: float = 15.0,
) -> np.ndarray:
    """Permanently Shadowed Region tahmini.

    Yükseklik ortalamanın altında VE eğim eşiğin üzerindeyse → True.
    Gerçek PSR tespiti ışık simülasyonu gerektirir; bu basitleştirilmiş
    bir proxy'dir.
    """
    elev_mean = np.nanmean(elevation)
    mask = (elevation < elev_mean) & (slope > slope_threshold)
    mask[np.isnan(elevation) | np.isnan(slope)] = False
    return mask


def make_traversability_grid(
    slope: np.ndarray,
    max_slope: float = SLOPE_TRAVERSABILITY_LIMIT,
) -> np.ndarray:
    """Eğime dayalı geçilebilirlik matrisi [0.0, 1.0].

    0 derece → 1.0 (kolay), ≥max_slope derece → 0.0 (geçilemez).
    Lineer interpolasyon.
    """
    trav = np.where(
        np.isnan(slope),
        np.nan,
        np.clip(1.0 - slope / max_slope, 0.0, 1.0),
    )
    return trav.astype(np.float64)


def make_thermal_risk_grid(
    elevation: np.ndarray,
    slope: np.ndarray,
    psr: np.ndarray,
) -> np.ndarray:
    """Basitleştirilmiş termal risk grid'i [0.0, 1.0].

    Düşük yükseklik + düşük eğim + PSR bölgeleri → yüksek termal risk.
    P4 termal modülü bunu detaylandıracak; bu ilk tahmin.
    """
    elev_norm = np.where(
        np.isnan(elevation),
        np.nan,
        (elevation - np.nanmin(elevation))
        / (np.nanmax(elevation) - np.nanmin(elevation) + 1e-10),
    )
    slope_norm = np.where(
        np.isnan(slope),
        np.nan,
        slope / (np.nanmax(slope) + 1e-10),
    )

    risk = 1.0 - 0.4 * elev_norm - 0.3 * slope_norm
    risk = np.where(psr, np.clip(risk + 0.2, 0, 1), risk)
    risk = np.clip(risk, 0.0, 1.0).astype(np.float64)
    return risk


# ═══════════════════════════════════════════════════════════════════════════════
# 4) ANA İŞLEM AKIŞI
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 60)
    print("  LunaPath P1 – Ay Yüzey Verisi İşleme")
    print("=" * 60)

    # ── Dosya varlık kontrolü ────────────────────────────────────────────────
    for f in (LDEM_FILE, LDSM_FILE, HILL_FILE):
        if not f.exists():
            print(f"HATA: Dosya bulunamadı → {f}")
            sys.exit(1)
    print(f"\n✓ Ham veri dizini : {RAW_DIR}")
    print(f"✓ Çıktı dizini   : {PROCESSED_DIR}\n")

    # ── 1. Okuma & hizalama ──────────────────────────────────────────────────
    dem_ds = rasterio.open(LDEM_FILE)
    slope_ds = rasterio.open(LDSM_FILE)
    hill_ds = rasterio.open(HILL_FILE)

    print(f"LDEM  : {dem_ds.width}×{dem_ds.height}, CRS={dem_ds.crs}, dtype={dem_ds.dtypes[0]}")
    print(f"LDSM  : {slope_ds.width}×{slope_ds.height}, CRS={slope_ds.crs}, dtype={slope_ds.dtypes[0]}")
    print(f"HILL  : {hill_ds.width}×{hill_ds.height}, CRS={hill_ds.crs}, dtype={hill_ds.dtypes[0]}")
    print()

    check_alignment({"LDEM": dem_ds, "LDSM": slope_ds, "HILL": hill_ds})

    # ── 2. Aksiyonlu pencere seçimi ──────────────────────────────────────────
    print("─── Aksiyonlu Bölge Aranıyor ───")
    win = find_action_window(dem_ds, slope_ds)

    # ── 3. Grid üretimi ─────────────────────────────────────────────────────
    print("\n─── Grid Üretimi ───")
    elevation_grid = make_elevation_grid(dem_ds, win)
    print(f"  elevation_grid  : shape={elevation_grid.shape}, "
          f"min={np.nanmin(elevation_grid):.1f}, max={np.nanmax(elevation_grid):.1f}")

    slope_grid = make_slope_grid(slope_ds, win)
    print(f"  slope_grid      : shape={slope_grid.shape}, "
          f"min={np.nanmin(slope_grid):.2f}°, max={np.nanmax(slope_grid):.2f}°")

    psr_mask = make_psr_mask(elevation_grid, slope_grid)
    psr_pct = 100.0 * psr_mask.sum() / psr_mask.size
    print(f"  psr_mask        : True piksel oranı = {psr_pct:.1f}%")

    traversability_grid = make_traversability_grid(slope_grid)
    print(f"  traversability  : min={np.nanmin(traversability_grid):.3f}, "
          f"max={np.nanmax(traversability_grid):.3f}")

    thermal_risk_grid = make_thermal_risk_grid(elevation_grid, slope_grid, psr_mask)
    print(f"  thermal_risk    : min={np.nanmin(thermal_risk_grid):.3f}, "
          f"max={np.nanmax(thermal_risk_grid):.3f}")

    # ── 4. Doğrulama (Validation) ────────────────────────────────────────────
    from utils import report_nodata, report_memory

    grids = {
        "elevation_grid": elevation_grid,
        "slope_grid": slope_grid,
        "psr_mask": psr_mask,
        "traversability_grid": traversability_grid,
        "thermal_risk_grid": thermal_risk_grid,
    }

    report_nodata(grids)
    report_memory(grids)

    # ── 5. Kaydetme ─────────────────────────────────────────────────────────
    print("─── Çıktılar Diske Yazılıyor ───")
    np.save(PROCESSED_DIR / "elevation_grid.npy", elevation_grid)
    np.save(PROCESSED_DIR / "slope_grid.npy", slope_grid)
    np.save(PROCESSED_DIR / "psr_mask.npy", psr_mask)
    np.save(PROCESSED_DIR / "traversability_grid.npy", traversability_grid)
    np.save(PROCESSED_DIR / "thermal_risk_grid.npy", thermal_risk_grid)
    print("  ✓ .npy dosyaları kaydedildi")

    # ── 6. Metadata ─────────────────────────────────────────────────────────
    from utils import save_metadata

    win_transform = rasterio.windows.transform(win, dem_ds.transform)
    origin_x, origin_y = win_transform.c, win_transform.f

    save_metadata(
        out_dir=PROCESSED_DIR,
        origin_x=origin_x,
        origin_y=origin_y,
        resolution=RESOLUTION_M,
        shape=(WINDOW_SIZE, WINDOW_SIZE),
        crs=str(dem_ds.crs),
        window_row_off=win.row_off,
        window_col_off=win.col_off,
    )
    print("  ✓ metadata.json kaydedildi")

    # ── 7. pixel_to_geo demo ────────────────────────────────────────────────
    from utils import pixel_to_geo

    demo_points = [(0, 0), (0, 499), (249, 249), (499, 499)]
    print("\n─── pixel_to_geo Koordinat Dönüşümü Demo ───")
    for r, c in demo_points:
        x, y = pixel_to_geo(r, c, win_transform)
        print(f"  pixel({r:>3d},{c:>3d}) → geo(x={x:.4f}, y={y:.4f})")

    # ── Temizlik ─────────────────────────────────────────────────────────────
    dem_ds.close()
    slope_ds.close()
    hill_ds.close()

    print("\n" + "=" * 60)
    print("  P1 veri işleme tamamlandı ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
