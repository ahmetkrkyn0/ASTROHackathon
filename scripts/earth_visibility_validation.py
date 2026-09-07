#!/usr/bin/env python3
"""Compare LunaPath's Earth-visibility layer to NASA's LOLA product.

Reference: PGDA product 69, "Lunar Polar Illumination" -- the file
``AVGVISIB_85S_060M_201608_EARTH.TIF`` (85-90 S, 60 m/px, polar
stereographic on the 1737.4 km sphere, int16 DN with SCALING_FACTOR 4e-5;
Mazarico et al. 2011, Icarus 211). It is public and 25 MB:

    https://pgda.gsfc.nasa.gov/data/MoonIllumination/AVGVISIB_85S_060M_201608_EARTH.TIF

Save it under ``lunapath/data/raw/`` (gitignored, like the DEM). If it is
not there this script says how to get it and exits 0 -- it never fabricates
comparison data.

Model: ``earth_visibility_grid.npy`` from scripts/build_earth_visibility_cache.py,
the same horizon-angle method applied to LunaPath's 5 m DEM window.

Two comparisons are reported:

* **60 m** -- the model block-averaged to the reference's own pixels
  (12 x 12 cells), the reference sampled bilinearly at those block
  centres. This is the fair one: it asks whether the two agree at the
  resolution the reference actually has.
* **5 m** -- the reference interpolated onto the model's cells. Larger
  errors here measure the sub-pixel structure the 5 m DEM adds (and the
  interpolation), not disagreement about the physics.

Writes a Markdown report (default docs/research/earth_visibility_validation.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.warp import Resampling, reproject  # noqa: E402

from app.earth_visibility import (  # noqa: E402
    EARTH_VISIBILITY_CACHE_FILENAME,
    EARTH_VISIBILITY_META_FILENAME,
)
from app.visibility_validation import block_mean, visibility_comparison  # noqa: E402

REFERENCE_URL = (
    "https://pgda.gsfc.nasa.gov/data/MoonIllumination/"
    "AVGVISIB_85S_060M_201608_EARTH.TIF"
)
#: From the PDS label: AVERAGE_VISIBILITY = DN * SCALING_FACTOR + OFFSET.
PDS_SCALING_FACTOR = 0.00004
PDS_OFFSET = 0.0

_HOWTO = f"""
LOLA Earth-visibility referansi bulunamadi: {{path}}

Elde etmek icin (25 MB, herkese acik):
  curl -L -o {{path}} {REFERENCE_URL}

Kaynak: NASA GSFC PGDA urun 69 "Lunar Polar Illumination", Mazarico vd. 2011.
Bu script veri olmadan sahte karsilastirma uretmez.
"""

_NO_MODEL = """
Modellenmis Dunya-gorunurlugu katmani bulunamadi: {path}

Once scripts/build_horizon_cache.py, sonra scripts/build_earth_visibility_cache.py
calistirin; referans veri mevcut olsa bile karsilastiracak bir model ciktisi
olmadan devam edilmez.
"""


def destination_transform(
    origin_x: float, origin_y: float, resolution_m: float
) -> "rasterio.Affine":
    """Affine of a grid whose row-0/col-0 CENTRE is (origin_x, origin_y).

    The P1 metadata records cell centres (``pixel_to_map_xy`` returns
    ``origin.y`` for row 0); ``from_origin`` wants the outer edge, hence the
    half-cell offset -- the registration scripts/diviner_validation.py
    documents (round 2 review, H-3).
    """
    return rasterio.transform.from_origin(
        float(origin_x) - resolution_m / 2.0,
        float(origin_y) + resolution_m / 2.0,
        resolution_m,
        resolution_m,
    )


def sample_reference(
    reference_path: Path,
    dst_crs: str,
    dst_transform: "rasterio.Affine",
    shape: tuple[int, int],
) -> tuple[np.ndarray, dict]:
    """Reference fraction on the destination grid, bilinear, NaN outside."""
    with rasterio.open(reference_path) as ds:
        raw = np.full(shape, np.nan, dtype=np.float64)
        reproject(
            source=rasterio.band(ds, 1),
            destination=raw,
            src_transform=ds.transform,
            src_crs=ds.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
            src_nodata=ds.nodata,
            dst_nodata=np.nan,
        )
        tags = dict(ds.tags())
        info = {
            "crs": ds.crs.to_wkt() if ds.crs else None,
            "resolution_m": float(ds.transform.a),
            "shape": [int(ds.height), int(ds.width)],
            "dtype": str(ds.dtypes[0]),
            "nodata": ds.nodata,
            "product_id": tags.get("PRODUCT_ID"),
            "creation_time": tags.get("PRODUCT_CREATION_TIME"),
            "start_time": tags.get("START_TIME"),
            "stop_time": tags.get("STOP_TIME"),
        }
    fraction = raw * PDS_SCALING_FACTOR + PDS_OFFSET
    fraction = np.where(np.isfinite(fraction), np.clip(fraction, 0.0, 1.0), np.nan)
    return fraction, info


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the Earth-visibility layer against NASA's LOLA product."
    )
    parser.add_argument(
        "--reference",
        default="lunapath/data/raw/AVGVISIB_85S_060M_201608_EARTH.TIF",
        help="Path to the PGDA AVGVISIB ... EARTH GeoTIFF.",
    )
    parser.add_argument(
        "--processed-dir",
        default="lunapath/data/processed",
        help="Directory holding earth_visibility_grid.npy and metadata.json.",
    )
    parser.add_argument("--out", default="docs/research/earth_visibility_validation.md")
    parser.add_argument(
        "--json-out",
        default=None,
        help="Optional path for the raw numbers as JSON (beside the report).",
    )
    args = parser.parse_args()

    reference_path = Path(args.reference)
    if not reference_path.exists():
        print(_HOWTO.format(path=reference_path))
        return 0

    processed_dir = Path(args.processed_dir)
    model_path = processed_dir / EARTH_VISIBILITY_CACHE_FILENAME
    if not model_path.exists():
        print(_NO_MODEL.format(path=model_path))
        return 0

    model = np.load(model_path).astype(np.float64)
    metadata = json.loads((processed_dir / "metadata.json").read_text(encoding="utf-8"))
    model_meta = {}
    meta_path = processed_dir / EARTH_VISIBILITY_META_FILENAME
    if meta_path.exists():
        model_meta = json.loads(meta_path.read_text(encoding="utf-8"))

    rows, cols = model.shape
    resolution_m = float(metadata["resolution_m"])
    origin = metadata["origin"]
    dst_crs = metadata["crs"]

    # 60 m: the reference's own pixels.
    with rasterio.open(reference_path) as ds:
        reference_res = float(ds.transform.a)
    factor = max(1, int(round(reference_res / resolution_m)))
    model_coarse = block_mean(model, factor)
    coarse_res = resolution_m * factor
    # Block (0, 0) spans fine cells 0..factor-1; its centre in map units is
    # the fine origin (a cell centre) shifted by (factor - 1) / 2 cells.
    coarse_origin_x = float(origin["x"]) + resolution_m * (factor - 1) / 2.0
    coarse_origin_y = float(origin["y"]) - resolution_m * (factor - 1) / 2.0
    reference_coarse, reference_info = sample_reference(
        reference_path,
        dst_crs,
        destination_transform(coarse_origin_x, coarse_origin_y, coarse_res),
        model_coarse.shape,
    )
    coarse = visibility_comparison(model_coarse, reference_coarse)

    # 5 m: the reference interpolated onto the model's cells.
    reference_fine, _ = sample_reference(
        reference_path,
        dst_crs,
        destination_transform(float(origin["x"]), float(origin["y"]), resolution_m),
        (rows, cols),
    )
    fine = visibility_comparison(model, reference_fine)

    lines = [
        "# Dunya gorunurlugu (DTE) dogrulama raporu",
        "",
        f"Referans: `{reference_path}` -- NASA GSFC PGDA urun 69, "
        f"`{reference_info.get('product_id')}` (LOLA, {reference_info.get('resolution_m'):g} m/px, "
        f"uretim {reference_info.get('creation_time')}), Mazarico vd. 2011.",
        f"Model: `{model_path}` -- ufuk kupu + SPICE Dunya vektoru, "
        f"{model_meta.get('span_days', '?')} gun / {model_meta.get('step_hours', '?')} saat adim, "
        f"{model_meta.get('n_samples', '?')} ornek, {model_meta.get('start_utc', '?')} -> "
        f"{model_meta.get('end_utc', '?')}.",
        "",
        f"## {coarse_res:g} m karsilastirma (referansin kendi cozunurlugu, {factor}x{factor} blok ortalamasi)",
        "",
        "| Metrik | Deger |",
        "|---|---|",
    ]
    for key, value in coarse.items():
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        f"## {resolution_m:g} m karsilastirma (referans modelin hucrelerine enterpole)",
        "",
        "| Metrik | Deger |",
        "|---|---|",
    ]
    for key, value in fine.items():
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "**Okuma:** `rmse`, `mae` ve `bias` gorunurluk kesri (0-1) birimindedir; `bias > 0`",
        "modelin referanstan daha fazla Dunya gorunurlugu verdigini soyler. `pearson_r`",
        "iki haritanin uzamsal deseninin ne kadar ortustugudur. `disagreement_pct`, iki",
        "haritanin 0,5 esiginde ANLASMADIGI hucrelerin yuzdesidir -- planlama acisindan",
        "en kritik sayi budur (\"cogunlukla baglantili\" / \"cogunlukla degil\").",
        "",
        "Yontem ayni (ufuk acisi vs. gok cismi yuksekligi), girdiler farkli: referans",
        "LOLA 60 m DEM'i ve 18,6 yillik saatlik ornekleme (PGDA urun sayfasi; PDS",
        f"etiketi START/STOP {reference_info.get('start_time')} / {reference_info.get('stop_time')}",
        "yalnizca LOLA veri araligini verir), model ise bu pencerenin 5 m DEM'i, 10 km",
        "isin menzili ve yukaridaki ornekleme. Kalan fark bu girdilerden gelir; 60 m",
        "satiri fizigin, 5 m satiri ise ek yuzey ayrintisinin olcusudur.",
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {
                    "reference": reference_info,
                    "model": model_meta,
                    "coarse_resolution_m": coarse_res,
                    "coarse": coarse,
                    "fine_resolution_m": resolution_m,
                    "fine": fine,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
