#!/usr/bin/env python3
"""Compare LunaPath's modelled thermal grid to a real Diviner measurement.

Requires a manually downloaded Diviner Polar Resource Product covering our
south-pole window. LunaPath does not auto-fetch this: MIT Imbrium
(imbrium.mit.edu) and the PDS Geosciences node host these products under
per-mission browse directories that change over time, so pin down the
current URL by hand rather than trust a hardcoded one.

If the reference file is not present, this script explains what to get
and exits 0 -- it must never fabricate comparison data.
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

from app.thermal_validation import thermal_comparison  # noqa: E402

_HOWTO = """
Diviner referans dosyasi bulunamadi: {path}

Elde etmek icin:
  1. https://imbrium.mit.edu/BROWSE/EXTRAS/ILLUMINATION/ (veya guncel PDS
     Geosciences node adresini) ziyaret edin.
  2. LunaPath'in penceresini kapsayan Diviner Polar Resource Product
     (ortalama/maksimum yuzey sicakligi) IMG/GeoTIFF dosyasini indirin.
  3. {path} yoluna kaydedin.

Bu script veri olmadan sahte karsilastirma uretmez.
"""

_NO_MODEL = """
Modellenmis termal grid bulunamadi: {path}

Bu dosya P1 on-isleme hattinin ciktisi. Once hatti calistirin, sonra bu
script'i tekrar cagirin. Referans veri mevcut olsa bile karsilastiracak
bir model ciktisi olmadan devam edilmez.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare the modelled thermal grid against a Diviner raster."
    )
    parser.add_argument(
        "--reference",
        default="lunapath/data/raw/diviner_temperature.tif",
        help="Path to a Diviner surface-temperature raster (Celsius).",
    )
    parser.add_argument(
        "--processed-dir",
        default="lunapath/data/processed",
        help="Directory holding thermal_grid.npy and metadata.json.",
    )
    parser.add_argument("--out", default="docs/research/diviner_validation.md")
    args = parser.parse_args()

    reference_path = Path(args.reference)
    if not reference_path.exists():
        print(_HOWTO.format(path=reference_path))
        return 0

    processed_dir = Path(args.processed_dir)
    model_path = processed_dir / "thermal_grid.npy"
    if not model_path.exists():
        print(_NO_MODEL.format(path=model_path))
        return 0

    model = np.load(model_path)

    # The grid's georeferencing lives in metadata.json, not in a readable
    # raster header: the processed layers are bare .npy arrays. Build the
    # destination transform from the recorded origin and resolution.
    metadata = json.loads(
        (processed_dir / "metadata.json").read_text(encoding="utf-8")
    )
    resolution_m = float(metadata["resolution_m"])
    origin = metadata["origin"]
    rows, cols = metadata["shape"]
    dst_transform = rasterio.transform.from_origin(
        origin["x"], origin["y"] + rows * resolution_m, resolution_m, resolution_m
    )
    dst_crs = metadata["crs"]

    with rasterio.open(reference_path) as reference_ds:
        reference = np.full((rows, cols), np.nan, dtype=np.float64)
        reproject(
            source=rasterio.band(reference_ds, 1),
            destination=reference,
            src_transform=reference_ds.transform,
            src_crs=reference_ds.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
            dst_nodata=np.nan,
        )

    result = thermal_comparison(model, reference)

    lines = [
        "# Diviner dogrulama raporu",
        "",
        f"Referans: `{reference_path}`",
        "",
        "| Metrik | Deger |",
        "|---|---|",
    ]
    for key, value in result.items():
        lines.append(f"| {key} | {value} |")

    lines += [
        "",
        "**Okuma:** `rmse_c` heat1d'nin peak yuzey sicakligi ile Diviner'in",
        "olcumu arasindaki kok-ortalama-kare hatasidir. `misclassified_traversable_pct`,",
        "iki modelin `-150 C` gecilebilirlik esiginde ANLASMADIGI hucrelerin oranidir",
        "-- planlama acisindan en kritik sayi budur.",
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
