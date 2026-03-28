#!/usr/bin/env python3
"""
LunaPath P1 v2.0 — Veri Isleme Hatti
=====================================
Tek bir NASA DEM dosyasindan 7 fiziksel olarak baglantili grid uretir.

Girdiler  : LDEM (yukseklik) — data/raw/
Ciktilar  : elevation_grid.npy, slope_grid.npy, aspect_grid.npy,
            shadow_ratio_grid.npy, thermal_grid.npy, traversability_grid.npy,
            cost_grid.npy, metadata.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window

# Backend traversability module — canonical source of truth
_BACKEND_ROOT = str(Path(__file__).resolve().parent.parent.parent / "backend")
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.cost_engine import compute_cost_grid, resolve_weights  # noqa: E402
from app.traversability import compute_traversability  # noqa: E402

# --- Proje dizinleri --------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # lunapath/
ASTRO_ROOT = PROJECT_ROOT.parent                               # repo root

RAW_DIR = PROJECT_ROOT / "data" / "raw"
if not RAW_DIR.exists() or not any(RAW_DIR.iterdir()):
    RAW_DIR = ASTRO_ROOT / "data" / "raw"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# --- Dosya ve sabitler -------------------------------------------------------
LDEM_FILE = RAW_DIR / "LDEM_80S_80MPP_ADJ.tiff"

WINDOW_SIZE = 500
RESOLUTION_M = 80.0
SLOPE_MAX_DEG = 25.0


# =============================================================================
# 1) PENCERE SECIMI — en aksiyonlu 500x500 bolge
# =============================================================================

def find_action_window(
    dem_ds: rasterio.DatasetReader,
    window_size: int = WINDOW_SIZE,
    sample_step: int = 100,
) -> Window:
    """Yukseklik farki x egim varyansi acisindan en yogun 500x500 bolgeyi bulur."""
    h, w = dem_ds.height, dem_ds.width
    print(f"Raster boyutu: {w} x {h} piksel")

    if h < window_size or w < window_size:
        raise ValueError(
            f"Raster ({w} x {h}) istenen pencere boyutundan ({window_size}) kucuk!"
        )

    overview_factor = 4
    ov_h, ov_w = h // overview_factor, w // overview_factor
    dem_overview = dem_ds.read(
        1,
        out_shape=(ov_h, ov_w),
        resampling=rasterio.enums.Resampling.average,
    ).astype(np.float64)

    nodata = dem_ds.nodata
    if nodata is not None:
        dem_overview[dem_overview == nodata] = np.nan

    # Dusuk cozunurluklu egim tahmini (pencere secimi icin yeterli)
    dy, dx = np.gradient(dem_overview, RESOLUTION_M * overview_factor)
    slope_overview = np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))

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

    win = Window(col_off=col_off, row_off=row_off,
                 width=window_size, height=window_size)
    print(f"Secilen pencere: row_off={row_off}, col_off={col_off}, "
          f"boyut={window_size} x {window_size}  (skor={best_score:.2f})")
    return win


# =============================================================================
# 2) GRID URETIMI — 7 katman
# =============================================================================

def make_elevation_grid(dem_ds: rasterio.DatasetReader, win: Window) -> np.ndarray:
    """Metre cinsinden yukseklik grid'i (float64)."""
    data = dem_ds.read(1, window=win).astype(np.float64)
    nodata = dem_ds.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data


def make_slope_grid(elevation: np.ndarray, resolution: float) -> np.ndarray:
    """np.gradient ile egim hesaplar (derece)."""
    dy, dx = np.gradient(elevation, resolution)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    return np.degrees(slope_rad)


def make_aspect_grid(elevation: np.ndarray, resolution: float) -> np.ndarray:
    """Yamac yonu hesaplar (0-360 derece, 0=Kuzey, 90=Dogu)."""
    dy, dx = np.gradient(elevation, resolution)
    aspect = np.degrees(np.arctan2(-dx, dy))
    # [-180, 180] -> [0, 360]
    aspect = np.mod(aspect, 360.0)
    return aspect


def make_shadow_ratio_grid(elevation: np.ndarray) -> np.ndarray:
    """Yukseklige bagli golge proxy'si [0, 1]. 0=aydinlik, 1=karanlik."""
    e_min = np.nanmin(elevation)
    e_max = np.nanmax(elevation)
    elev_norm = (elevation - e_min) / (e_max - e_min + 1e-10)
    shadow_ratio = 1.0 - elev_norm
    return shadow_ratio


def make_thermal_grid(
    elevation: np.ndarray,
    slope: np.ndarray,
    aspect: np.ndarray,
    resolution: float,
) -> np.ndarray:
    """Sentetik yuzey sicaklik grid'i (Celsius).

    5 adimli model:
      1. T_base   — yukseklige dayali baz sicaklik [-180, +80]
      2. sun_factor — aspect'e dayali gunes faktoru
      3. slope_weight — normalize egim agirligi
      4. T_aspect_delta — gunes + egim etki terimi
      5. shadow_penalty — kuzey komsu yukseklik farkindan ceza
    """
    e_min = np.nanmin(elevation)
    e_max = np.nanmax(elevation)
    elev_norm = (elevation - e_min) / (e_max - e_min + 1e-10)

    # Adim 1: Baz sicaklik
    T_base = -180.0 + elev_norm * (80.0 - (-180.0))

    # Adim 2: Gunes faktoru (aspect'e dayali)
    sun_factor = np.cos(np.radians(aspect))

    # Adim 3: Egim agirligi
    slope_weight = np.clip(slope / 25.0, 0.0, 1.0)

    # Adim 4: Aspect-egim etki terimi
    T_aspect_delta = sun_factor * slope_weight * 40.0

    # Adim 5: Shadow penalty — kuzey komsu farki
    north_neighbor = np.roll(elevation, 1, axis=0)
    # Ilk satir icin sinir kosulu: kendisiyle ayni (ceza yok)
    north_neighbor[0, :] = elevation[0, :]
    height_diff = north_neighbor - elevation
    height_diff = np.clip(height_diff, 0.0, None)  # sadece pozitif fark
    shadow_penalty = np.clip(height_diff / (resolution * 0.1), 0.0, 1.0) * (-30.0)

    # Final sicaklik
    T_surface = np.clip(
        T_base + T_aspect_delta + shadow_penalty,
        -250.0, 130.0,
    )
    return T_surface


def make_traversability_grid(
    slope: np.ndarray,
    thermal: np.ndarray,
) -> np.ndarray:
    """Ikili gecebilirlik maskesi.

    Hesaplama backend/app/traversability.py modulunden gelir (tek kaynak).
    """
    return compute_traversability(slope, thermal)


def make_cost_grid(
    slope: np.ndarray,
    thermal: np.ndarray,
    shadow_ratio: np.ndarray,
    resolution: float,
    traversability: np.ndarray,
    weights: dict[str, float] | None = None,
) -> np.ndarray:
    """Cell-level weighted cost grid.

    Cost grid planner ile ayni penalty fonksiyonlarini kullanir, fakat
    log-barrier terimini bilerek disarida birakir. Cunku bariyer cezasi
    kume halinde biriken shadow/SOC durumuna baglidir ve yalnizca rota
    uzerinde anlamlidir.
    """
    return compute_cost_grid(
        slope,
        thermal,
        shadow_ratio,
        resolution,
        traversable=traversability.astype(bool),
        weights=weights,
    )


# =============================================================================
# 3) METADATA
# =============================================================================

def save_metadata(
    out_dir: Path,
    origin_x: float,
    origin_y: float,
    resolution: float,
    shape: tuple[int, int],
    crs: str,
    window_row_off: int,
    window_col_off: int,
    cost_weights: dict[str, float],
) -> Path:
    """Grid metadata'sini JSON olarak diske yazar."""
    meta = {
        "origin": {"x": origin_x, "y": origin_y},
        "resolution_m": resolution,
        "shape": list(shape),
        "crs": crs,
        "window_offset": {"row": window_row_off, "col": window_col_off},
        "grids": [
            "elevation_grid",
            "slope_grid",
            "aspect_grid",
            "shadow_ratio_grid",
            "thermal_grid",
            "traversability_grid",
            "cost_grid",
        ],
        "cost_weights": cost_weights,
        "cost_model": "weighted_cell_cost_without_barrier",
    }
    path = out_dir / "metadata.json"
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# =============================================================================
# 4) DOGRULAMA KONTROLLERI (v2.0 Belge Bolum 3.3)
# =============================================================================

def print_validation(
    thermal: np.ndarray,
    traversability: np.ndarray,
    cost_grid: np.ndarray,
    grids: dict[str, np.ndarray],
) -> None:
    """Konsola dogrulama istatistiklerini yazdirir."""
    print("\n--- Dogrulama Kontrolleri (v2.0 Bolum 3.3) ---")

    print(f"\n  thermal_grid:")
    print(f"    min  = {np.nanmin(thermal):>+9.2f} C")
    print(f"    max  = {np.nanmax(thermal):>+9.2f} C")
    print(f"    mean = {np.nanmean(thermal):>+9.2f} C")

    total = traversability.size
    passable = int(np.nansum(traversability))
    pct = 100.0 * passable / total
    print(f"\n  traversability_grid:")
    print(f"    Gecilebilir alan = {passable}/{total} piksel ({pct:.1f}%)")

    finite_cost = cost_grid[np.isfinite(cost_grid)]
    if finite_cost.size > 0:
        print(f"\n  cost_grid:")
        print(f"    min  = {np.min(finite_cost):>9.4f}")
        print(f"    max  = {np.max(finite_cost):>9.4f}")
        print(f"    mean = {np.mean(finite_cost):>9.4f}")
    else:
        print(f"\n  cost_grid:")
        print("    UYARI: sonlu maliyet bulunamadi")

    print("\n  Grid boyut ve NaN kontrolu:")
    for name, arr in grids.items():
        if np.issubdtype(arr.dtype, np.floating):
            nan_count = int(np.isnan(arr).sum())
            inf_count = int(np.isinf(arr).sum())
        else:
            nan_count = 0
            inf_count = 0
        if nan_count == 0 and inf_count == 0:
            status = "TEMIZ"
        else:
            status = f"{nan_count} NaN / {inf_count} INF"
        print(f"    {name:<25s} shape={str(arr.shape):<14s} {status}")


# =============================================================================
# 5) ANA ISLEM AKISI
# =============================================================================

def main(weights: dict[str, float] | None = None) -> None:
    print("=" * 60)
    print("  LunaPath P1 v2.0 — Ay Yuzey Verisi Isleme")
    print("=" * 60)

    # -- Dosya kontrolu -------------------------------------------------------
    if not LDEM_FILE.exists():
        print(f"HATA: DEM dosyasi bulunamadi: {LDEM_FILE}")
        sys.exit(1)
    print(f"\n  Ham veri  : {RAW_DIR}")
    print(f"  Cikti     : {PROCESSED_DIR}\n")

    resolved_weights = resolve_weights(weights)
    print("  Cost agirliklari:")
    for key, value in resolved_weights.items():
        print(f"    {key:<10s}= {value:.3f}")

    # -- 1. DEM okuma ---------------------------------------------------------
    dem_ds = rasterio.open(LDEM_FILE)
    print(f"LDEM: {dem_ds.width} x {dem_ds.height}, "
          f"CRS={dem_ds.crs}, dtype={dem_ds.dtypes[0]}")

    # -- 2. Pencere secimi ----------------------------------------------------
    print("\n--- Aksiyonlu Bolge Araniyor ---")
    win = find_action_window(dem_ds)

    # -- 3. Grid uretimi (7 katman) -------------------------------------------
    print("\n--- Grid Uretimi (7 katman) ---")

    elevation_grid = make_elevation_grid(dem_ds, win)
    print(f"  elevation_grid  : min={np.nanmin(elevation_grid):.1f}, "
          f"max={np.nanmax(elevation_grid):.1f}")

    slope_grid = make_slope_grid(elevation_grid, RESOLUTION_M)
    print(f"  slope_grid      : min={np.nanmin(slope_grid):.2f} deg, "
          f"max={np.nanmax(slope_grid):.2f} deg")

    aspect_grid = make_aspect_grid(elevation_grid, RESOLUTION_M)
    print(f"  aspect_grid     : min={np.nanmin(aspect_grid):.2f} deg, "
          f"max={np.nanmax(aspect_grid):.2f} deg")

    shadow_ratio_grid = make_shadow_ratio_grid(elevation_grid)
    print(f"  shadow_ratio    : min={np.nanmin(shadow_ratio_grid):.3f}, "
          f"max={np.nanmax(shadow_ratio_grid):.3f}")

    thermal_grid = make_thermal_grid(
        elevation_grid, slope_grid, aspect_grid, RESOLUTION_M,
    )
    print(f"  thermal_grid    : min={np.nanmin(thermal_grid):.2f} C, "
          f"max={np.nanmax(thermal_grid):.2f} C")

    traversability_grid = make_traversability_grid(slope_grid, thermal_grid)
    passable_pct = 100.0 * np.nansum(traversability_grid) / traversability_grid.size
    print(f"  traversability  : gecilebilir={passable_pct:.1f}%")

    cost_grid = make_cost_grid(
        slope_grid,
        thermal_grid,
        shadow_ratio_grid,
        RESOLUTION_M,
        traversability_grid,
        resolved_weights,
    )
    finite_cost = cost_grid[np.isfinite(cost_grid)]
    if finite_cost.size > 0:
        print(
            f"  cost_grid       : min={np.min(finite_cost):.4f}, "
            f"max={np.max(finite_cost):.4f}, mean={np.mean(finite_cost):.4f}"
        )
    else:
        print("  cost_grid       : UYARI sonlu maliyet yok")

    # -- 4. Dogrulama ---------------------------------------------------------
    grids = {
        "elevation_grid": elevation_grid,
        "slope_grid": slope_grid,
        "aspect_grid": aspect_grid,
        "shadow_ratio_grid": shadow_ratio_grid,
        "thermal_grid": thermal_grid,
        "traversability_grid": traversability_grid,
        "cost_grid": cost_grid,
    }
    print_validation(thermal_grid, traversability_grid, cost_grid, grids)

    # -- 5. Kaydetme ----------------------------------------------------------
    print("\n--- Ciktilar Diske Yaziliyor ---")
    for name, arr in grids.items():
        np.save(PROCESSED_DIR / f"{name}.npy", arr)
    print(f"  {len(grids)} adet .npy dosyasi kaydedildi")

    # -- 6. Metadata ----------------------------------------------------------
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
        cost_weights=resolved_weights,
    )
    print("  metadata.json kaydedildi")

    # -- Temizlik -------------------------------------------------------------
    dem_ds.close()

    print("\n" + "=" * 60)
    print("  P1 v2.0 veri isleme tamamlandi")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LunaPath weighted grid generator")
    parser.add_argument(
        "--weights-json",
        help=(
            "Opsiyonel agirlik override. "
            "Ornek: '{\"w_slope\":0.7,\"w_energy\":0.1,\"w_shadow\":0.1,\"w_thermal\":0.1}'"
        ),
    )
    return parser.parse_args()


def parse_weight_overrides(raw: str | None) -> dict[str, float] | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Gecersiz --weights-json: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("--weights-json bir JSON obje olmali.")
    return {str(key): float(value) for key, value in payload.items()}


if __name__ == "__main__":
    args = parse_args()
    main(parse_weight_overrides(args.weights_json))
