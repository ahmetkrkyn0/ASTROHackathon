#!/usr/bin/env python3
"""Fetch the LRO Diviner Polar Resource Product (south) and cache it.

The product
----------
``LRO-L-DLRE-5-PRP-V2.0``, file ``dlre_prp_south.tab``, from the PDS
Geosciences Node's PDS4 bundle ``urn-nasa-pds-lro_diviner_derived1``. This
is the identity C5 exists to pin down: documents 07 and 11 said "download
Diviner" without naming a product, and the research note's PDS3-style path
(``/lro/lro-l-dlre-5-prp-v2/...``) is a 404 -- the bundle moved.

What it is, in the archive's own words (``catalog/prpds.cat``): "thermal
model fits to first mapping year Diviner polar observations", processing
level CODMAC 5 / NASA 4. So it is DERIVED, not a raw measurement, and
this module labels it that way. Comparing our thermal grid to it is
MODEL vs MODEL-FITTED-TO-OBSERVATION, which is still worth doing and is
not the same claim as "validated against a measurement".

Format, read from ``label/dlre_prp.fmt`` rather than assumed: fixed-length
210-byte records, one 210-byte header record then 2 880 000 data rows, 15
comma-separated ASCII columns. Nine triangle-vertex coordinates (Moon-centred
cartesian, km), the triangle centre's planetocentric lon/lat/altitude, then
``temp_avg`` (annual average, **2 cm below the surface**), ``temp_max``
(annual maximum, **at the surface**) and ``ice_depth`` (modelled, fill
-999). Only ``temp_max`` is the counterpart of our annual peak; the other
two are a different depth and a different kind of quantity.

What this writes
----------------
``lunapath/data/processed/diviner_prp.npz`` -- per-triangle latitude,
longitude, area, facet slope/aspect and both temperatures, for the whole
mesh; plus the vertices of the triangles overlapping the Site11 window, so
the report can project them itself.
``lunapath/data/processed/diviner_prp_meta.json`` -- provenance: source
URLs, SHA-256 and byte count of the raw file, row count, and what each
column means.

Neither file is committed (see .gitignore). If the download fails, this
script writes NOTHING and says why: a thermal validation that invents its
reference is worse than one that does not run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

BUNDLE = (
    "https://pds-geosciences.wustl.edu/lro/"
    "urn-nasa-pds-lro_diviner_derived1/"
)
TAB_URL = BUNDLE + "data_derived_prp/dlre_prp_south.tab"
LBL_URL = BUNDLE + "data_derived_prp/dlre_prp_south.lbl"
FMT_URL = BUNDLE + "label/dlre_prp.fmt"
CAT_URL = BUNDLE + "catalog/prpds.cat"

DATA_SET_ID = "LRO-L-DLRE-5-PRP-V2.0"

#: From the .lbl: RECORD_BYTES = 210, FILE_RECORDS = 2880000, plus one
#: header record. Used to validate what we downloaded before parsing it.
RECORD_BYTES = 210
DATA_ROWS = 2_880_000
EXPECTED_BYTES = RECORD_BYTES * (DATA_ROWS + 1)

#: Moon radius the PRP mesh is referenced to (label: A_AXIS_RADIUS = 1737.4 km).
#: Identical to the sphere in our own grid's CRS, so no datum shift is needed.
MOON_RADIUS_KM = 1737.4

N_COLUMNS = 15
ICE_DEPTH_FILL = -999.0

_HOWTO = """
Diviner PRP indirilemedi: {error}

Urun: {data_set_id}
Adres: {url}

PDS Geosciences dugumu zaman zaman 403/404 dondurur (B3'un PGDA'da gordugu
durum). Adresi tarayicida dogrulayin ve dosyayi elle su yola indirin:

  {raw}

Bu betik veri olmadan hicbir sey yazmaz ve sahte bir referans uretmez.
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def download(url: str, destination: Path, timeout: float = 120.0) -> None:
    """Stream *url* to *destination*, via a .part file so an interrupted
    download never looks like a complete one."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "LunaPath/C5"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        with partial.open("wb") as handle:
            while True:
                chunk = response.read(1 << 20)
                if not chunk:
                    break
                handle.write(chunk)
    partial.replace(destination)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def facet_geometry(
    vertices: np.ndarray, lat_deg: np.ndarray, lon_deg: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Area (km^2), slope (deg) and downhill aspect (deg CW from TRUE north).

    *vertices* is (n, 3, 3): triangle, vertex, xyz in km.

    The aspect convention is chosen to match what ``heat1d`` documents for
    its ``slope_az`` parameter -- "clockwise from north (0 = N, pi/2 = E)"
    -- measured against true local north, NOT the grid north that
    ``lunapath/src/process_lunar_data.py:make_aspect_grid`` works in. Those
    two differ by the meridian convergence, which at the Site11 window's
    longitude is about 72.7 degrees. Naming the frame here is the whole
    point: the report measures what that difference is worth rather than
    quietly assuming the two agree.

    For a facet with outward normal ``n``, the steepest-descent direction is
    the horizontal component of ``n`` (for ``z = ax + by`` the normal is
    ``(-a, -b, 1)`` and downhill is ``(-a, -b)``), which is what "aspect"
    conventionally names.
    """
    v1, v2, v3 = vertices[:, 0, :], vertices[:, 1, :], vertices[:, 2, :]
    cross = np.cross(v2 - v1, v3 - v1)
    area = 0.5 * np.linalg.norm(cross, axis=1)

    phi = np.deg2rad(np.asarray(lat_deg, dtype=np.float64))
    lam = np.deg2rad(np.asarray(lon_deg, dtype=np.float64))
    cos_phi, sin_phi = np.cos(phi), np.sin(phi)
    cos_lam, sin_lam = np.cos(lam), np.sin(lam)

    up = np.stack([cos_phi * cos_lam, cos_phi * sin_lam, sin_phi], axis=1)
    north = np.stack([-sin_phi * cos_lam, -sin_phi * sin_lam, cos_phi], axis=1)
    east = np.stack([-sin_lam, cos_lam, np.zeros_like(sin_lam)], axis=1)

    norm = np.linalg.norm(cross, axis=1, keepdims=True)
    unit = np.divide(cross, norm, out=np.zeros_like(cross), where=norm > 0)
    # Orient outward: the archive does not promise a winding order.
    outward = np.sum(unit * up, axis=1, keepdims=True)
    unit = np.where(outward < 0, -unit, unit)

    cos_slope = np.clip(np.sum(unit * up, axis=1), -1.0, 1.0)
    slope = np.degrees(np.arccos(cos_slope))

    horizontal = unit - np.sum(unit * up, axis=1, keepdims=True) * up
    aspect = np.degrees(
        np.arctan2(np.sum(horizontal * east, axis=1), np.sum(horizontal * north, axis=1))
    )
    return area, slope, np.mod(aspect, 360.0)


#: Vertices are kept only for triangles at least this far poleward. The
#: report needs real footprints solely inside the Site11 window (-88.87 to
#: -88.97); keeping all 2.88 M triangles' nine coordinates would add ~104 MB
#: of float32 to the cache to serve about fifty rows.
VERTEX_LAT_DEG = -88.5


def parse_table(
    path: Path,
    chunk_rows: int = 200_000,
    progress: bool = True,
    vertex_lat_deg: float = VERTEX_LAT_DEG,
) -> dict[str, np.ndarray]:
    """One streaming pass over the 605 MB table.

    Returns per-triangle arrays as float32. ``np.fromstring`` in text mode
    (``sep=','``) is the fast path that does not add a dependency: pandas
    would be ~10x quicker but is not in backend/requirements.txt, and a
    validation feature is a poor excuse to add a dependency.
    """
    size = path.stat().st_size
    if size != EXPECTED_BYTES:
        raise ValueError(
            f"{path.name} is {size} bytes, expected {EXPECTED_BYTES} "
            f"({RECORD_BYTES} x ({DATA_ROWS} rows + 1 header)). Re-download it."
        )

    lat_parts, lon_parts, area_parts = [], [], []
    slope_parts, aspect_parts = [], []
    tavg_parts, tmax_parts, ice_parts = [], [], []
    vertex_parts, vertex_index_parts = [], []

    read = 0
    with path.open("rb") as handle:
        header = handle.read(RECORD_BYTES).decode("ascii")
        if "temp_max" not in header:
            raise ValueError(f"unexpected header record: {header[:80]!r}")
        while read < DATA_ROWS:
            want = min(chunk_rows, DATA_ROWS - read)
            raw = handle.read(RECORD_BYTES * want)
            values = np.fromstring(raw.replace(b"\r\n", b","), sep=",")
            if values.size != want * N_COLUMNS:
                raise ValueError(
                    f"row {read}: parsed {values.size} values, "
                    f"expected {want * N_COLUMNS}"
                )
            block = values.reshape(want, N_COLUMNS)
            vertices = block[:, 0:9].reshape(want, 3, 3)
            lon, lat = block[:, 9], block[:, 10]
            area, slope, aspect = facet_geometry(vertices, lat, lon)

            lat_parts.append(lat.astype(np.float32))
            lon_parts.append(lon.astype(np.float32))
            area_parts.append(area.astype(np.float32))
            slope_parts.append(slope.astype(np.float32))
            aspect_parts.append(aspect.astype(np.float32))
            tavg_parts.append(block[:, 12].astype(np.float32))
            tmax_parts.append(block[:, 13].astype(np.float32))
            ice_parts.append(block[:, 14].astype(np.float32))

            keep = np.flatnonzero(lat <= vertex_lat_deg)
            if keep.size:
                vertex_parts.append(vertices[keep].astype(np.float32))
                vertex_index_parts.append((keep + read).astype(np.int64))

            read += want
            if progress:
                print(f"  parsed {read:,}/{DATA_ROWS:,}", end="\r", flush=True)
    if progress:
        print()

    return {
        "lat_deg": np.concatenate(lat_parts),
        "lon_deg": np.concatenate(lon_parts),
        "area_km2": np.concatenate(area_parts),
        "slope_deg": np.concatenate(slope_parts),
        "aspect_true_deg": np.concatenate(aspect_parts),
        "temp_avg_k": np.concatenate(tavg_parts),
        "temp_max_k": np.concatenate(tmax_parts),
        "ice_depth_m": np.concatenate(ice_parts),
        "polar_vertices_km": (
            np.concatenate(vertex_parts)
            if vertex_parts
            else np.zeros((0, 3, 3), dtype=np.float32)
        ),
        "polar_vertex_index": (
            np.concatenate(vertex_index_parts)
            if vertex_index_parts
            else np.zeros((0,), dtype=np.int64)
        ),
        "polar_vertex_lat_deg": np.asarray(vertex_lat_deg, dtype=np.float64),
    }


def build_meta(raw: Path, columns: dict[str, np.ndarray]) -> dict:
    lat = columns["lat_deg"]
    area = columns["area_km2"]
    return {
        "layer": "diviner_prp",
        "validity": "DERIVED",
        "validity_note": (
            "PDS catalog prpds.cat: 'thermal model fits to first mapping year "
            "Diviner polar observations', CODMAC level 5 / NASA level 4. A "
            "model constrained by observations, not a raw measurement."
        ),
        "data_set_id": DATA_SET_ID,
        "producer": "David A. Paige, UCLA (LRO_DLRE_TEAM)",
        "citation": (
            "Paige et al., LRO DLRE LEVEL 5 PRP V2.0, NASA Planetary Data "
            "System, LRO-L-DLRE-5-PRP-V2.0, 2018."
        ),
        "model_reference": "Paige et al., Science 330, 497 (2010)",
        "mesh_reference": (
            "Kaguya laser altimeter DEM (Araki et al., Science 323, 897, 2009) "
            "-- a different topography from our 5 m/px LOLA Site11 grid."
        ),
        "tab_url": TAB_URL,
        "lbl_url": LBL_URL,
        "fmt_url": FMT_URL,
        "cat_url": CAT_URL,
        "raw_bytes": int(raw.stat().st_size),
        "raw_sha256": sha256_of(raw),
        "n_triangles": int(lat.size),
        "n_polar_vertices_kept": int(columns["polar_vertex_index"].size),
        "polar_vertex_lat_deg": float(columns["polar_vertex_lat_deg"]),
        "columns": {
            "temp_max_k": "annual MAXIMUM temperature (K), at the SURFACE",
            "temp_avg_k": "annual AVERAGE temperature (K), at 2 cm DEPTH",
            "ice_depth_m": f"modelled ice stability depth (m), fill {ICE_DEPTH_FILL}",
            "slope_deg": "facet slope from the triangle normal",
            "aspect_true_deg": "facet downhill azimuth, CW from TRUE north",
            "area_km2": "triangle area from its own vertices",
        },
        "lat_range_deg": [float(lat.min()), float(lat.max())],
        "area_km2_median": float(np.median(area)),
        "area_km2_total": float(area.sum()),
        "equivalent_edge_m": float(
            np.sqrt(4.0 * np.median(area) / np.sqrt(3.0)) * 1000.0
        ),
        "moon_radius_km": MOON_RADIUS_KM,
        "fetched_utc": _utc_now(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and cache the Diviner Polar Resource Product (south)."
    )
    parser.add_argument("--raw", default="lunapath/data/raw/dlre_prp_south.tab")
    parser.add_argument("--processed-dir", default="lunapath/data/processed")
    parser.add_argument("--url", default=TAB_URL)
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Fail instead of fetching if the raw table is absent.",
    )
    args = parser.parse_args()

    raw = Path(args.raw)
    if raw.exists() and raw.stat().st_size == EXPECTED_BYTES:
        print(f"raw table already present ({raw}), skipping download")
    elif args.no_download:
        print(f"raw table absent and --no-download given: {raw}")
        return 0
    else:
        print(f"downloading {args.url} ({EXPECTED_BYTES / 1e6:.0f} MB)...")
        try:
            download(args.url, raw)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as error:
            print(
                _HOWTO.format(
                    error=error, url=args.url, raw=raw, data_set_id=DATA_SET_ID
                )
            )
            return 0
        try:
            download(LBL_URL, raw.with_suffix(".lbl"))
        except (urllib.error.URLError, urllib.error.HTTPError, OSError):
            pass  # the label is provenance, not data; its absence is not fatal

    print("parsing (one streaming pass)...")
    try:
        columns = parse_table(raw)
    except ValueError as error:
        print(f"refusing to cache a table we could not parse: {error}")
        return 1

    processed = Path(args.processed_dir)
    processed.mkdir(parents=True, exist_ok=True)
    npz_path = processed / "diviner_prp.npz"
    meta_path = processed / "diviner_prp_meta.json"

    print(f"writing {npz_path} ...")
    np.savez_compressed(npz_path, **columns)
    meta = build_meta(raw, columns)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    print(
        f"cached {meta['n_triangles']:,} triangles; "
        f"median area {meta['area_km2_median']:.4f} km^2 "
        f"(~{meta['equivalent_edge_m']:.0f} m edge); "
        f"lat {meta['lat_range_deg'][0]:.3f}..{meta['lat_range_deg'][1]:.3f}"
    )
    print(f"raw sha256 {meta['raw_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
