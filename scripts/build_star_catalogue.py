#!/usr/bin/env python3
"""Pack the Yale Bright Star Catalogue into the binary the 3-D sky reads.

The scene used to draw 3500 stars at uniformly random points on a sphere, all
the same size, coloured from a six-entry palette by coin flip. That is a noise
field, not a sky: no constellations, no magnitude range, no relation to what is
actually overhead at the lunar south pole. Every other surface in this product
is real measured data, and the sky was the one place making numbers up.

BSC5 is the standard naked-eye catalogue -- 9110 entries, essentially every
star brighter than magnitude 6.5, which is the unaided-eye limit. It carries
what a renderer needs and nothing it does not: J2000 position, visual
magnitude, and B-V colour index.

Source   http://tdc-www.harvard.edu/catalogs/bsc5.dat.gz
         (Hoffleit & Warren 1991, Yale University Observatory; distributed by
         the Astronomical Data Center, in the public domain)

Output   frontend/public/data/bsc5.bin
         A headerless Float32Array, four values per star, little-endian:
             ra_deg    0..360    J2000 right ascension
             dec_deg  -90..90    J2000 declination
             vmag                visual magnitude (lower is brighter)
             bv                  B-V colour index (blue-white .. red)
         Star count is byteLength / 16. Headerless because there is exactly
         one consumer and a magic number it would never disagree with is a
         field that only exists to be checked.

Run once; the catalogue has not changed since 1991 and the output is committed.

    python3 scripts/build_star_catalogue.py
"""

from __future__ import annotations

import gzip
import struct
import sys
import urllib.request
from pathlib import Path

SOURCE = "http://tdc-www.harvard.edu/catalogs/bsc5.dat.gz"
OUT = Path(__file__).resolve().parent.parent / "frontend/public/data/bsc5.bin"

# Fixed-width byte ranges from the catalogue's own documentation, 1-indexed
# inclusive, converted to Python slices. J2000 is bytes 76-90; the B1900
# position sits immediately before it at 61-75, and taking that one by mistake
# would rotate the whole sky by a century of precession -- about 1.4 degrees.
RA_H, RA_M, RA_S = slice(75, 77), slice(77, 79), slice(79, 83)
DE_SIGN, DE_D, DE_M, DE_S = 83, slice(84, 86), slice(86, 88), slice(88, 90)
VMAG, BV = slice(102, 107), slice(109, 114)

# Five stars whose magnitude and colour are known to anyone who has opened an
# observing guide. Parsing a fixed-width catalogue is exactly the kind of job
# that silently produces plausible garbage when an offset is one byte out, so
# the output is checked against them before it is written.
#            name          RA h   RA m    Dec      V      B-V
LANDMARKS = [
    ("Sirius",      6, 45, -16.7, -1.46,  0.00),
    ("Canopus",     6, 24, -52.7, -0.72,  0.15),
    ("Betelgeuse",  5, 55,   7.4,  0.50,  1.85),
    ("Vega",       18, 36,  38.8,  0.03,  0.00),
    ("Alpha Cen",  14, 39, -60.8, -0.01,  0.71),
]


def parse(line: str) -> tuple[float, float, float, float] | None:
    """One catalogue row, or None for the handful that carry no position."""
    try:
        ra_h = int(line[RA_H])
        ra_m = int(line[RA_M])
        ra_s = float(line[RA_S])
        sign = -1.0 if line[DE_SIGN] == "-" else 1.0
        de_d = int(line[DE_D])
        de_m = int(line[DE_M])
        de_s = int(line[DE_S])
        vmag = float(line[VMAG])
    except ValueError:
        # Novae and entries deleted from the catalogue keep their line but
        # blank these fields. Fourteen of 9110.
        return None
    try:
        bv = float(line[BV])
    except ValueError:
        # Missing colour, not a bad row. 0.0 is Vega's own index, so an
        # uncoloured star renders white rather than vanishing.
        bv = 0.0
    return (ra_h + ra_m / 60 + ra_s / 3600) * 15.0, sign * (de_d + de_m / 60 + de_s / 3600), vmag, bv


def main() -> int:
    print(f"fetching {SOURCE}")
    with urllib.request.urlopen(SOURCE, timeout=60) as response:
        raw = gzip.decompress(response.read()).decode("latin-1")

    stars = [parsed for line in raw.splitlines() if (parsed := parse(line))]
    print(f"parsed {len(stars)} stars")

    failures = 0
    for name, ra_h, ra_m, dec, want_v, want_bv in LANDMARKS:
        target_ra = (ra_h + ra_m / 60) * 15
        ra, dc, v, bv = min(stars, key=lambda s: (s[0] - target_ra) ** 2 + (s[1] - dec) ** 2)
        ok = abs(v - want_v) < 0.05 and abs(bv - want_bv) < 0.05
        failures += not ok
        print(f"  {name:11s} V={v:6.2f} B-V={bv:+5.2f}  {'ok' if ok else 'MISMATCH'}")
    if failures:
        print(f"{failures} landmark(s) wrong -- byte offsets are off, nothing written", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("wb") as handle:
        for star in stars:
            handle.write(struct.pack("<4f", *star))
    print(f"wrote {OUT.relative_to(Path.cwd())}  {OUT.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
