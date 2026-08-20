#!/usr/bin/env python3
"""Download the NAIF SPICE kernels LunaPath needs.

Kernels total a few hundred MB and are deliberately NOT committed.
Run once:  python lunapath/src/fetch_kernels.py
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels"

KERNELS: tuple[tuple[str, str], ...] = (
    (f"{NAIF}/lsk/naif0012.tls", "naif0012.tls"),
    (f"{NAIF}/spk/planets/de440s.bsp", "de440s.bsp"),
    (f"{NAIF}/pck/moon_pa_de440_200625.bpc", "moon_pa_de440_200625.bpc"),
    (f"{NAIF}/fk/satellites/moon_de440_220930.tf", "moon_de440_220930.tf"),
)

META_KERNEL_TEMPLATE = """\\begindata
PATH_VALUES  = ( '{kernel_dir}' )
PATH_SYMBOLS = ( 'K' )
KERNELS_TO_LOAD = (
{entries}
)
\\begintext
"""


def main() -> None:
    kernel_dir = Path(__file__).resolve().parent.parent.parent / "kernels"
    kernel_dir.mkdir(parents=True, exist_ok=True)

    for url, name in KERNELS:
        target = kernel_dir / name
        if target.exists():
            print(f"  skip (exists): {name}")
            continue
        print(f"  downloading: {name} ...", flush=True)
        urllib.request.urlretrieve(url, target)
        print(f"  done: {name} ({target.stat().st_size / 1e6:.1f} MB)")

    entries = "\n".join(f"    '$K/{name}'" for _, name in KERNELS)
    meta = META_KERNEL_TEMPLATE.format(
        kernel_dir=str(kernel_dir).replace("\\", "/"), entries=entries
    )
    meta_path = kernel_dir / "lunapath.tm"
    meta_path.write_text(meta, encoding="utf-8")
    print(f"\n  meta-kernel written: {meta_path}")


if __name__ == "__main__":
    main()
