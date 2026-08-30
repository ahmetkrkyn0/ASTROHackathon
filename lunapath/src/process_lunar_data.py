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

from app.cost_engine import COST_MODEL_ID, compute_cost_grid, resolve_weights  # noqa: E402
from app.horizon import horizon_map  # noqa: E402
from app.illumination import (  # noqa: E402
    illumination_fraction,
    shadow_ratio_from_illumination,
)
from app.thermal_model import (  # noqa: E402
    Heat1DModel,
    SyntheticModel,
    build_thermal_grid,
    couple_shadow_to_thermal,
)
from app.traversability import compute_traversability, weakest_validity  # noqa: E402

# --- Proje dizinleri --------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent          # lunapath/
ASTRO_ROOT = PROJECT_ROOT.parent                               # repo root

RAW_DIR = PROJECT_ROOT / "data" / "raw"
if not RAW_DIR.exists() or not any(RAW_DIR.iterdir()):
    RAW_DIR = ASTRO_ROOT / "data" / "raw"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# --- Dosya ve sabitler -------------------------------------------------------
DEFAULT_WINDOW_SIZE = 500
SLOPE_MAX_DEG = 25.0
HORIZON_N_AZIMUTH = 72
HORIZON_MAX_RANGE_M = 10000.0
HORIZON_MAX_STEPS = 200  # adım sayısı sabit -> hesap yuku cozunurlukten bagimsiz
# Bir Ay gunu boyunca saatlik ornekleme
SUN_TRACK_START_UTC = "2026-11-15T00:00:00"
SUN_TRACK_END_UTC = "2026-12-13T00:00:00"
SUN_TRACK_SAMPLES = 168


def find_dem_file(custom_path: str | None = None) -> Path:
    """Işlenecek DEM dosyasını bulur."""
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Belirtilen DEM dosyasi bulunamadi: {p}")

    candidates = [
        RAW_DIR / "Site01_final_adj_5mpp_surf.tif",
        RAW_DIR / "Site01_final_adj_5mpp_surf.tiff",
        RAW_DIR / "LDEM_80S_80MPP_ADJ.tiff",
        RAW_DIR / "LDEM_80S_80MPP_ADJ.tif",
    ]
    for c in candidates:
        if c.exists():
            return c

    tif_files = sorted(list(RAW_DIR.glob("*.tif")) + list(RAW_DIR.glob("*.tiff")))
    if tif_files:
        return tif_files[0]

    raise FileNotFoundError(f"'{RAW_DIR}' dizininde herhangi bir .tif / .tiff DEM dosyasi bulunamadi!")


# NOTE: backend/app/serializer.py::pixel_to_lonlat had the identical y-axis
# sign convention issue this function's origin_y handling was fixed to avoid
# (Faz 1 Task 8 review). It was later corrected there too, in
# backend/app/corridor.py's C2 fix (Faz 2 review) -- both now subtract the
# row term consistently.
def window_center_latlon(
    origin_x: float,
    origin_y: float,
    resolution_m: float,
    shape: tuple[int, int],
    crs_wkt: str,
) -> tuple[float, float]:
    """Pencerenin merkez noktasinin (lat, lon) WGS84 koordinatlari.

    Sabit bir guney-kutbu varsayimi yerine, hangi DEM yuklenirse
    yuklensin dogru enlem/boylami CRS'ten turetir -- heat1d LUT'u ve
    gunes izi bu deger uzerinden calisir. serializer.py'deki
    pixel_to_lonlat ile ayni pyproj deseni.
    """
    import os

    os.environ.setdefault("PROJ_IGNORE_CELESTIAL_BODY", "YES")
    from pyproj import Transformer

    rows, cols = shape
    center_x = origin_x + 0.5 * cols * resolution_m
    center_y = origin_y - 0.5 * rows * resolution_m
    transformer = Transformer.from_crs(crs_wkt, "EPSG:4326", always_xy=True)
    lon_deg, lat_deg = transformer.transform(center_x, center_y)
    return float(lat_deg), float(lon_deg)


# =============================================================================
# 1) PENCERE SECIMI — en aksiyonlu 500x500 bolge
# =============================================================================

def find_action_window(
    dem_ds: rasterio.DatasetReader,
    resolution_m: float,
    window_size: int = DEFAULT_WINDOW_SIZE,
    sample_step: int = 100,
) -> Window:
    """Yukseklik farki x egim varyansi acisindan en yogun window_size x window_size bolgeyi bulur."""
    h, w = dem_ds.height, dem_ds.width
    print(f"Raster boyutu: {w} x {h} piksel | Cozunurluk: {resolution_m:.2f} m/px")

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
    dy, dx = np.gradient(dem_overview, resolution_m * overview_factor)
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

    # Eger NaN pikseller varsa, komsuluk enterpolasyonu ile temizle
    if np.isnan(data).any():
        nan_mask = np.isnan(data)
        if (~nan_mask).any():
            from scipy.ndimage import distance_transform_edt
            indices = distance_transform_edt(nan_mask, return_distances=False, return_indices=True)
            data = data[tuple(indices)]
        else:
            data = np.nan_to_num(data, nan=0.0)

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


def make_shadow_ratio_grid(
    elevation: np.ndarray,
    resolution: float,
    lat_deg: float,
    lon_deg: float,
    crs_wkt: str,
) -> tuple[np.ndarray, str]:
    """Golge orani [0, 1]. 0=aydinlik, 1=karanlik.

    Gercek yol: topografik ufuk haritasi + SPICE gunes izi. SPICE
    cekirdekleri yoksa yukseklik proxy'sine duser ve bunu bildirir.
    lat_deg/lon_deg window_center_latlon()'dan gelir -- sabit degil.
    crs_wkt gercek kuzey -> grid kuzeyi azimut donusumu icin gerekli.

    Donus: (shadow_ratio_grid, validity)
    """
    from app.ephemeris import (
        sun_track,
        true_azimuth_to_grid_azimuth,
        true_north_grid_azimuth,
    )

    try:
        # sun_track first: it's the cheap call and the one that actually
        # raises when SPICE kernels are missing. Failing here first avoids
        # paying for the expensive horizon_map ray-marching only to throw
        # the result away.
        samples = sun_track(
            SUN_TRACK_START_UTC,
            SUN_TRACK_END_UTC,
            SUN_TRACK_SAMPLES,
            lat_deg,
            lon_deg,
        )
        # sun_track's azimuths are TRUE-north referenced; horizon_map's bins
        # are GRID-north referenced (raster row/col directions). They coincide
        # only on the projection's central meridian -- at this window's real
        # longitude the offset is ~110 deg (~22 of 72 bins). Rotate before
        # matching. (Faz 1 final review, finding C1.)
        grid_north_az = true_north_grid_azimuth(lat_deg, lon_deg, crs_wkt)
        grid_samples = [
            (true_azimuth_to_grid_azimuth(az, grid_north_az), elev)
            for az, elev in samples
        ]
        horizon = horizon_map(
            elevation,
            resolution,
            n_azimuth=HORIZON_N_AZIMUTH,
            max_range_m=HORIZON_MAX_RANGE_M,
            max_steps=HORIZON_MAX_STEPS,
            progress=True,
        )
        frac = illumination_fraction(horizon, grid_samples)
        return shadow_ratio_from_illumination(frac).astype(np.float64), "DERIVED"
    except Exception as exc:
        # Deliberately broad: this function's contract is "try real physics,
        # fall back to the synthetic proxy on ANY failure, and say so".
        # spiceypy maps SPICE errors onto assorted builtin exception types
        # (SpiceNOSUCHFILE -> OSError, but out-of-coverage epochs and malformed
        # meta-kernels surface as ValueError/TypeError/KeyError subclasses), so
        # a narrow catch would let those kill the whole pipeline instead of
        # degrading gracefully. (Faz 1 final review, finding I8.)
        print(f"  UYARI: gercek aydinlanma hesaplanamadi ({exc}); proxy kullaniliyor")
        e_min = np.nanmin(elevation)
        e_max = np.nanmax(elevation)
        elev_norm = (elevation - e_min) / (e_max - e_min + 1e-10)
        return (1.0 - elev_norm), "SYNTHETIC"


def make_thermal_grid(
    elevation: np.ndarray,
    slope: np.ndarray,
    aspect: np.ndarray,
    resolution: float,
    lat_deg: float,
    lon_deg: float,
    crs_wkt: str,
) -> tuple[np.ndarray, str]:
    """Yuzey sicaklik grid'i (Celsius) + validity etiketi.

    heat1d kuruluysa gercek termal difuzyon modeli, degilse sentetik
    proxy. lat_deg/lon_deg window_center_latlon()'dan gelir -- sabit degil.
    crs_wkt, Heat1DModel yoluna gonderilen aspect'i grid-kuzeyinden
    gercek-kuzeye cevirmek icin gerekli.

    ``aspect`` grid-kuzeyi referansli (make_aspect_grid konvansiyonu).
    heat1d'nin ``slope_az``'i ise gercek-kuzey referansli (bkz.
    ``heat1d.terrain.slope_incidence_cos`` docstring'i, ``orbits.solarAzimuth``
    ile ayni cerceve). Golge yolu bu donusumu ``true_azimuth_to_grid_azimuth``
    ile Faz 1 final review'da (bulgu C1) uyguladi; termal yol o zaman
    uygulanmadan kalmisti (Faz 1-2-3 review, M1) -- Heat1DModel dalinda
    burada duzeltiliyor. SyntheticModel dali dokunulmadan kaliyor: o,
    grid-kuzeyi aspect uzerinde yazilip test edilmis kendi sezgisel
    formulunu kullaniyor, gercek-kuzey kavramindan bagimsiz.
    """
    if Heat1DModel.available():
        from app.ephemeris import grid_azimuth_to_true_azimuth, true_north_grid_azimuth

        model = Heat1DModel()
        grid_north_az = true_north_grid_azimuth(lat_deg, lon_deg, crs_wkt)
        aspect_for_model = grid_azimuth_to_true_azimuth(aspect, grid_north_az)
    else:
        print("  UYARI: heat1d bulunamadi; sentetik termal model kullaniliyor")
        # Sentetik model'e de gercek gunes yonu veriliyor. Onceden "gunes
        # grid kuzeyinden" varsayimi sabitti; guney kutup stereografik
        # CRS'te ekvator (gunes) yonu pencerenin boylamina gore grid
        # kuzeyinden ~75 derece sapar, yani sirtlarin yanlis yuzu isitiliyordu.
        # (Round 3 review, L-4.)
        from app.ephemeris import true_north_grid_azimuth

        try:
            grid_north_az = true_north_grid_azimuth(lat_deg, lon_deg, crs_wkt)
        except Exception:
            grid_north_az = 0.0
        # Kutupta gunes ekvator yonunde, yani kutuptan disari dogru: true
        # azimut 0 (kuzey) kutup yonu oldugundan gunes true 180'de.
        sun_grid_az = (grid_north_az + 180.0) % 360.0
        model = SyntheticModel(
            elevation=elevation,
            resolution_m=resolution,
            sun_azimuth_grid_deg=sun_grid_az,
        )
        aspect_for_model = aspect

    grid = build_thermal_grid(model, slope, aspect_for_model, lat_deg)
    return grid.astype(np.float64), model.validity


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
    layer_validity: dict[str, str],
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
        # Kod ile diskteki artefaktin ayni formulu tarif ettigini garanti
        # etmek icin sabit yerine COST_MODEL_ID yaziliyor. Elle yazilan
        # string, cost fonksiyonu degistiginde guncellenmedi ve diskteki
        # grid kalici olarak "bayat" damgasi tasidi. (Round 3 review, L-6.)
        "cost_model": COST_MODEL_ID,
        "thermal_shadow_coupled": True,
        "layer_validity": layer_validity,
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

def main(
    weights: dict[str, float] | None = None,
    dem_path: str | None = None,
    window_size: int = DEFAULT_WINDOW_SIZE,
    row_offset: int | None = None,
    col_offset: int | None = None,
) -> None:
    print("=" * 60)
    print("  LunaPath P1 v2.0 — Ay Yuzey Verisi Isleme")
    print("=" * 60)

    # -- Dosya bulma ----------------------------------------------------------
    dem_file = find_dem_file(dem_path)
    print(f"\n  DEM Dosyasi: {dem_file.name}")
    print(f"  Ham veri   : {RAW_DIR}")
    print(f"  Cikti      : {PROCESSED_DIR}\n")

    resolved_weights = resolve_weights(weights)
    print("  Cost agirliklari:")
    for key, value in resolved_weights.items():
        print(f"    {key:<10s}= {value:.3f}")

    # -- 1. DEM okuma & Cozunurluk Algilama ------------------------------------
    dem_ds = rasterio.open(dem_file)
    resolution_m = abs(float(dem_ds.transform.a))
    print(f"\nLDEM Bilgisi:")
    print(f"  Boyut      : {dem_ds.width} x {dem_ds.height} piksel")
    print(f"  Cozunurluk : {resolution_m:.2f} metre/piksel")
    print(f"  CRS        : {dem_ds.crs}")

    # -- 2. Pencere secimi ----------------------------------------------------
    if row_offset is not None and col_offset is not None:
        print(f"\n--- Belirtilen Pencere Secildi ({window_size}x{window_size}, row={row_offset}, col={col_offset}) ---")
        win = Window(col_offset, row_offset, window_size, window_size)
    else:
        print(f"\n--- Aksiyonlu Bolge Araniyor ({window_size}x{window_size}) ---")
        win = find_action_window(dem_ds, resolution_m=resolution_m, window_size=window_size)

    win_transform = rasterio.windows.transform(win, dem_ds.transform)
    origin_x, origin_y = win_transform.c, win_transform.f
    lat_deg, lon_deg = window_center_latlon(
        origin_x, origin_y, resolution_m, (window_size, window_size), str(dem_ds.crs)
    )
    print(f"  Pencere merkezi : {lat_deg:.3f} N, {lon_deg:.3f} E (yaklasik)")

    # -- 3. Grid uretimi (7 katman) -------------------------------------------
    print("\n--- Grid Uretimi (7 katman) ---")

    elevation_grid = make_elevation_grid(dem_ds, win)
    print(f"  elevation_grid  : min={np.nanmin(elevation_grid):.1f} m, "
          f"max={np.nanmax(elevation_grid):.1f} m")

    slope_grid = make_slope_grid(elevation_grid, resolution_m)
    print(f"  slope_grid      : min={np.nanmin(slope_grid):.2f} deg, "
          f"max={np.nanmax(slope_grid):.2f} deg")

    aspect_grid = make_aspect_grid(elevation_grid, resolution_m)
    print(f"  aspect_grid     : min={np.nanmin(aspect_grid):.2f} deg, "
          f"max={np.nanmax(aspect_grid):.2f} deg")

    shadow_ratio_grid, shadow_validity = make_shadow_ratio_grid(
        elevation_grid, resolution_m, lat_deg, lon_deg, str(dem_ds.crs)
    )
    print(f"  shadow_ratio    : min={np.nanmin(shadow_ratio_grid):.3f}, "
          f"max={np.nanmax(shadow_ratio_grid):.3f}")

    thermal_grid, thermal_validity = make_thermal_grid(
        elevation_grid, slope_grid, aspect_grid, resolution_m, lat_deg, lon_deg,
        str(dem_ds.crs),
    )
    # Termal katman aydinlanmayi okumuyordu: Heat1DModel bir (egim x baki)
    # lookup tablosu, dolayisiyla kalici golgedeki bir hucre gunesli tepe
    # sicakligini raporluyordu (uretim gridinde +42.6 C'ye kadar) ve -150 C
    # gecilebilirlik kapisi 250 000 hucrenin yalnizca 150'sini kapatiyordu.
    # Stefan-Boltzmann dorduncu-kuvvet harmanlamasiyla iki katman baglaniyor.
    # (Round 3 review, H-3.)
    thermal_grid = np.asarray(
        couple_shadow_to_thermal(thermal_grid, shadow_ratio_grid), dtype=np.float64
    )
    thermal_validity = weakest_validity(thermal_validity, shadow_validity)

    print(f"  thermal validity: {thermal_validity} (shadow-coupled)")
    print(f"  shadow  validity: {shadow_validity}")
    print(f"  thermal_grid    : min={np.nanmin(thermal_grid):.2f} C, "
          f"max={np.nanmax(thermal_grid):.2f} C")

    traversability_grid = make_traversability_grid(slope_grid, thermal_grid)
    passable_pct = 100.0 * np.nansum(traversability_grid) / traversability_grid.size
    print(f"  traversability  : gecilebilir={passable_pct:.1f}%")

    cost_grid = make_cost_grid(
        slope_grid,
        thermal_grid,
        shadow_ratio_grid,
        resolution_m,
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
    save_metadata(
        out_dir=PROCESSED_DIR,
        origin_x=origin_x,
        origin_y=origin_y,
        resolution=resolution_m,
        shape=(window_size, window_size),
        crs=str(dem_ds.crs),
        window_row_off=win.row_off,
        window_col_off=win.col_off,
        cost_weights=resolved_weights,
        layer_validity={
            "elevation": "MEASURED",
            "slope": "DERIVED",
            "aspect": "DERIVED",
            "shadow_ratio": shadow_validity,
            "thermal": thermal_validity,
            # traversable depends only on slope + thermal (see
            # compute_traversability); cost additionally reads shadow_ratio
            # (ShadowLayer) and energy (always MODEL, never the weakest
            # link). Both used to be hardcoded "DERIVED" regardless of what
            # their inputs actually were, so a SYNTHETIC shadow_ratio (SPICE
            # kernels missing) still produced a cost grid claiming a
            # stronger provenance than its own weakest input.
            # (Faz 1-2-3 review, L5.)
            "traversable": weakest_validity("DERIVED", thermal_validity),
            "cost": weakest_validity("DERIVED", shadow_validity, thermal_validity),
        },
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
        "--dem-path",
        type=str,
        default=None,
        help="Islenecek ham DEM GeoTIFF dosyasinin yolu.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help=f"Uretilecek grid pencere boyutu (varsayilan: {DEFAULT_WINDOW_SIZE}).",
    )
    parser.add_argument(
        "--weights-json",
        help=(
            "Opsiyonel agirlik override. "
            "Ornek: '{\"w_slope\":0.7,\"w_energy\":0.1,\"w_shadow\":0.1,\"w_thermal\":0.1}'"
        ),
    )
    parser.add_argument(
        "--row-offset",
        type=int,
        default=None,
        help="DEM uzerinden secilecek pencerenin baslangic satir indeksi (row_off).",
    )
    parser.add_argument(
        "--col-offset",
        type=int,
        default=None,
        help="DEM uzerinden secilecek pencerenin baslangic sutun indeksi (col_off).",
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
    main(
        weights=parse_weight_overrides(args.weights_json),
        dem_path=args.dem_path,
        window_size=args.window_size,
        row_offset=args.row_offset,
        col_offset=args.col_offset,
    )

