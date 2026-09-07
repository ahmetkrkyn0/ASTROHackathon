#!/usr/bin/env python3
"""Fetch the MoonPlanBench occupancy maps (D2) into the local benchmark cache.

MoonPlanBench (Chancán et al., arXiv 2512.21438, Dec 2025) is not inside the
authors' repository: the README links a Google Drive folder with three
sub-folders (MoonPlanBench-10 / -15 / -20, one per slope threshold), each
holding 12 ``.npy`` occupancy maps named after the LOLA polar DEM product
they were derived from. This script

1. lists each sub-folder through Drive's ``embeddedfolderview`` page (no
   API key, no third-party package),
2. downloads every ``.npy`` through ``uc?export=download`` (the files are
   60-230 KB, no virus-scan interstitial),
3. refuses anything that is not a 2-D NumPy array of {0, 1},
4. writes ``moonplanbench_meta.json`` beside the maps: paper, repository
   commit, Drive ids, SHA-256 and size of every file, licence, fetch time.

The data licence is CC BY-NC-SA 4.0 (the paper's licence line; the Drive
folder carries none of its own): the maps stay out of the repository
(``lunapath/data/benchmarks/`` is gitignored). Existing files are kept
unless ``--force``; ``--offline`` only re-hashes what is on disk.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import numpy as np  # noqa: E402

from app.benchmark import (  # noqa: E402
    CODE_LICENSES,
    DATA_LICENSE,
    DOWNSAMPLE_FACTOR,
    DRIVE_ROOT_FOLDER_ID,
    DRIVE_VARIANT_FOLDER_IDS,
    LDEM_NATIVE_M_PER_PX,
    META_FILENAME,
    MOONPLANBENCH_DIR,
    PAPER_ARXIV,
    PAPER_AUTHORS,
    PAPER_DATE,
    PAPER_TITLE,
    PAPER_URL,
    REPO_COMMIT,
    REPO_URL,
    SLOPE_THRESHOLD_DEG,
    VARIANTS,
    cell_size_m,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

USER_AGENT = "Mozilla/5.0 (LunaPath D2 MoonPlanBench fetch)"
EXPECTED_FILES_PER_VARIANT = 12
_ENTRY_RE = re.compile(
    r'<div class="flip-entry" id="entry-([A-Za-z0-9_-]+)".*?<div class="flip-entry-title">(.*?)</div>',
    re.S,
)


def folder_listing_url(folder_id: str) -> str:
    return f"https://drive.google.com/embeddedfolderview?id={folder_id}#list"


def download_url(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def parse_embedded_folder_listing(page: str) -> list[tuple[str, str]]:
    """``[(title, drive_id), ...]`` in page order from an embeddedfolderview page."""
    return [(html.unescape(title).strip(), file_id) for file_id, title in _ENTRY_RE.findall(page)]


def npy_entries(entries: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [entry for entry in entries if entry[0].lower().endswith(".npy")]


def _http_get(url: str, timeout: float = 120.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def validate_npy_bytes(data: bytes) -> np.ndarray:
    """The bytes must be a ``.npy`` holding a 2-D array whose values are all
    0 or 1 -- an occupancy map as ``run.py`` reads it. Anything else (an
    HTML error page, a 3-D array, a value of 2) is refused."""
    if not data.startswith(b"\x93NUMPY"):
        raise ValueError("not a NumPy .npy file (magic bytes missing)")
    arr = np.load(io.BytesIO(data), allow_pickle=False)
    if arr.ndim != 2:
        raise ValueError(f"occupancy map must be 2-D, got shape {arr.shape}")
    values = np.unique(arr)
    if not np.all(np.isin(values, (0, 1))):
        raise ValueError(f"occupancy map must hold only 0 and 1, found {values[:8].tolist()}")
    return arr


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _file_record(path: Path, drive_id: str | None) -> dict:
    data = path.read_bytes()
    arr = validate_npy_bytes(data)
    try:
        cell = cell_size_m(path.stem)
    except ValueError:
        cell = None
    return {
        "name": path.name,
        "drive_id": drive_id,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "shape": [int(arr.shape[0]), int(arr.shape[1])],
        "dtype": str(arr.dtype),
        "free_fraction": float((arr == 0).mean()),
        "native_m_per_px": LDEM_NATIVE_M_PER_PX.get(path.stem),
        "cell_size_m": cell,
    }


def build_meta(data_dir: str | Path, drive_ids: dict[str, dict[str, str]], fetched_utc: str) -> dict:
    """Provenance for what is on disk under *data_dir*. *drive_ids* maps
    variant -> {file name: Drive id} for files fetched this run (or known);
    files present without an id are recorded with ``drive_id: None``."""
    root = Path(data_dir)
    variants: dict[str, dict] = {}
    n_files = 0
    for variant in VARIANTS:
        folder = root / variant
        if not folder.is_dir():
            continue
        ids = drive_ids.get(variant, {})
        files = [_file_record(path, ids.get(path.name)) for path in sorted(folder.glob("*.npy"))]
        if not files:
            continue
        n_files += len(files)
        variants[variant] = {
            "folder_id": DRIVE_VARIANT_FOLDER_IDS.get(variant),
            "slope_threshold_deg": SLOPE_THRESHOLD_DEG.get(variant),
            "n_files": len(files),
            "expected_files": EXPECTED_FILES_PER_VARIANT,
            "files": files,
        }
    return {
        "dataset": "MoonPlanBench",
        "paper": {
            "title": PAPER_TITLE,
            "authors": PAPER_AUTHORS,
            "arxiv": PAPER_ARXIV,
            "url": PAPER_URL,
            "date": PAPER_DATE,
        },
        "repo": {"url": REPO_URL, "commit": REPO_COMMIT},
        "drive_root_folder_id": DRIVE_ROOT_FOLDER_ID,
        "data_license": DATA_LICENSE,
        "code_licenses": CODE_LICENSES,
        "occupancy_convention": "non-zero = occupied (run.py: occ = grid != 0)",
        "cell_size_rule": f"LDEM native metres per pixel x {DOWNSAMPLE_FACTOR} (paper sect. 3.1.2)",
        "n_files": n_files,
        "variants": variants,
        "fetched_utc": fetched_utc,
    }


def write_meta(data_dir: str | Path, meta: dict) -> Path:
    path = Path(data_dir) / META_FILENAME
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def fetch_variant(variant: str, folder_id: str, data_dir: Path, force: bool, log=print) -> dict[str, str]:
    """Download the variant's ``.npy`` files; returns {file name: Drive id}
    for every listed file (fetched or already present)."""
    folder = data_dir / variant
    folder.mkdir(parents=True, exist_ok=True)
    page = _http_get(folder_listing_url(folder_id)).decode("utf-8", "replace")
    entries = npy_entries(parse_embedded_folder_listing(page))
    if len(entries) != EXPECTED_FILES_PER_VARIANT:
        log(f"  ! {variant}: Drive lists {len(entries)} .npy files, expected {EXPECTED_FILES_PER_VARIANT}")
    ids: dict[str, str] = {}
    for name, file_id in entries:
        ids[name] = file_id
        target = folder / name
        if target.exists() and not force:
            continue
        t0 = time.perf_counter()
        data = _http_get(download_url(file_id))
        try:
            arr = validate_npy_bytes(data)
        except ValueError as exc:
            log(f"  ! {variant}/{name}: refused, {exc}")
            continue
        target.write_bytes(data)
        log(f"  {variant}/{name}: {arr.shape[0]}x{arr.shape[1]} {arr.dtype}, {len(data)} B in {time.perf_counter() - t0:.1f}s")
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default=MOONPLANBENCH_DIR)
    parser.add_argument("--variants", default=",".join(VARIANTS), help="comma-separated subset of the three variants")
    parser.add_argument("--force", action="store_true", help="re-download files that already exist")
    parser.add_argument("--offline", action="store_true", help="no network: only hash what is on disk and rewrite the meta")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    unknown = [v for v in variants if v not in DRIVE_VARIANT_FOLDER_IDS]
    if unknown:
        print(f"unknown variant(s) {unknown}; known: {list(DRIVE_VARIANT_FOLDER_IDS)}")
        return 2

    existing = None
    meta_path = data_dir / META_FILENAME
    if meta_path.is_file():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
    drive_ids: dict[str, dict[str, str]] = {}
    if existing:
        for variant, block in existing.get("variants", {}).items():
            drive_ids[variant] = {f["name"]: f["drive_id"] for f in block.get("files", []) if f.get("drive_id")}

    if args.offline:
        fetched = (existing or {}).get("fetched_utc")
        print(f"offline: hashing what is under {data_dir}")
    else:
        fetched = _utc_now()
        for variant in variants:
            print(f"{variant} (Drive folder {DRIVE_VARIANT_FOLDER_IDS[variant]})")
            drive_ids[variant] = fetch_variant(variant, DRIVE_VARIANT_FOLDER_IDS[variant], data_dir, args.force)

    meta = build_meta(data_dir, drive_ids, fetched)
    if meta["n_files"] == 0:
        print(f"no .npy maps under {data_dir}; nothing written")
        return 1
    write_meta(data_dir, meta)
    for variant, block in meta["variants"].items():
        shapes = sorted({tuple(f["shape"]) for f in block["files"]})
        print(f"  {variant}: {block['n_files']} files, shapes {shapes}, "
              f"free {min(f['free_fraction'] for f in block['files']):.2f}-{max(f['free_fraction'] for f in block['files']):.2f}")
        if block["n_files"] != EXPECTED_FILES_PER_VARIANT:
            print(f"  ! {variant}: {block['n_files']} files on disk, expected {EXPECTED_FILES_PER_VARIANT}")
    print(f"wrote {meta_path} ({meta['n_files']} files; licence {DATA_LICENSE.split(' (')[0]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
