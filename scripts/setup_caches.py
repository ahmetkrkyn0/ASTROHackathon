#!/usr/bin/env python3
"""Build every gitignored artefact the backend needs, in dependency order.

A fresh clone carries the source and the raw DEMs but none of the derived
data: `.npy` grids, horizon cubes and the six feature caches are all
gitignored, so the twelve backend features answer `unavailable` until this
runs. This script is the one command that produces all of them.

Steps 1 and 2 REWRITE `lunapath/data/processed/`. That is deliberate --
the checked-in metadata describes window (2400, 2500) while the current
test suite and reports describe window (1500, 1000), so the grids on a
developer's disk are usually the older region. Pass `--skip-grids` to keep
what is already there and build only the caches on top of it.

Each step is a separate process, so one failure (a download that times out,
a product that moved) does not take the rest down: the step is recorded and
the run continues. The summary at the end says what exists and what does not.

    python scripts/setup_caches.py                 # everything
    python scripts/setup_caches.py --skip-grids    # caches only
    python scripts/setup_caches.py --only roughness,clones
    python scripts/setup_caches.py --list
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _ROOT / "scripts"
_PROCESSED = _ROOT / "lunapath" / "data" / "processed"
_RAW = _ROOT / "lunapath" / "data" / "raw"
_BENCHMARKS = _ROOT / "lunapath" / "data" / "benchmarks"

# The window the current test suite and the measurement reports describe.
# process_lunar_data writes it into metadata.json as window_offset.
_WINDOW_ROW = 1500
_WINDOW_COL = 1000
_SITE_DEM = _RAW / "Site11_final_adj_5mpp_surf.tif"


@dataclass
class Step:
    key: str
    title: str
    argv: list[str]
    produces: list[Path]
    network: bool = False
    destructive: bool = False
    note: str = ""
    needs: list[Path] = field(default_factory=list)


def _steps() -> list[Step]:
    py = sys.executable
    return [
        Step(
            key="grids",
            title="P1 gridleri (pencere satir=%d, sutun=%d)" % (_WINDOW_ROW, _WINDOW_COL),
            argv=[
                py,
                str(_ROOT / "lunapath" / "src" / "process_lunar_data.py"),
                "--dem-path", str(_SITE_DEM),
                "--row-offset", str(_WINDOW_ROW),
                "--col-offset", str(_WINDOW_COL),
            ],
            produces=[
                _PROCESSED / "elevation_grid.npy",
                _PROCESSED / "slope_grid.npy",
                _PROCESSED / "metadata.json",
            ],
            destructive=True,
            needs=[_SITE_DEM],
            note="Mevcut processed/*.npy dosyalarinin uzerine yazar.",
        ),
        Step(
            key="horizon",
            title="Ufuk kubu (horizon_map.npy)",
            argv=[py, str(_SCRIPTS / "build_horizon_cache.py"), "--force"],
            produces=[_PROCESSED / "horizon_map.npy"],
            note="Gridler degistiginde yeniden uretilmek zorunda.",
        ),
        Step(
            key="earth",
            title="A4 - Dunya gorunurlugu onbellegi",
            argv=[py, str(_SCRIPTS / "build_earth_visibility_cache.py"), "--force"],
            produces=[
                _PROCESSED / "earth_visibility_grid.npy",
                _PROCESSED / "earth_visibility_meta.json",
            ],
            needs=[_ROOT / "kernels" / "lunapath.tm"],
            note="SPICE cekirdekleri kernels/ altinda olmali. Indirme yok.",
        ),
        Step(
            key="roughness",
            title="C4 - Puruzluluk (LOLA LDRM) + PSR maskesi",
            argv=[py, str(_SCRIPTS / "build_roughness_cache.py")],
            produces=[
                _PROCESSED / "roughness_grid.npy",
                _PROCESSED / "roughness_meta.json",
                _PROCESSED / "psr_grid.npy",
                _PROCESSED / "psr_meta.json",
            ],
            network=True,
            note="NASA PGDA urun 90, /vsicurl/ ile ~1 MB.",
        ),
        Step(
            key="clones",
            title="B3 - DEM belirsizligi (NASA'nin 100 Site11 klonu)",
            argv=[py, str(_SCRIPTS / "build_dem_clone_cache.py")],
            produces=[
                _PROCESSED / "dem_clones.npy",
                _PROCESSED / "dem_clone_horizons.npy",
                _PROCESSED / "dem_elevation_sigma.npy",
                _PROCESSED / "dem_slope_sigma_nasa.npy",
            ],
            network=True,
            note="NASA PGDA urun 78. En uzun adim: klon basina ~2,5 s + indirme.",
        ),
        Step(
            key="thermal",
            title="C6 - Termal zarf onbellegi (heat1d transient)",
            argv=[py, str(_SCRIPTS / "build_thermal_envelope_cache.py")],
            produces=[
                _PROCESSED / "thermal_envelope_heat1d.npz",
                _PROCESSED / "thermal_envelope_meta.json",
            ],
            note="Indirme yok, tamamen lokal hesap.",
        ),
        Step(
            key="diviner",
            title="C5 - Diviner PRP (termal dogrulama referansi)",
            argv=[py, str(_SCRIPTS / "build_diviner_prp_cache.py")],
            produces=[
                _PROCESSED / "diviner_prp.npz",
                _PROCESSED / "diviner_prp_meta.json",
            ],
            network=True,
            note="PDS Geosciences, LRO-L-DLRE-5-PRP-V2.0. 605 MB ham indirme.",
        ),
        Step(
            key="benchmark",
            title="D2 - MoonPlanBench occupancy haritalari",
            argv=[py, str(_SCRIPTS / "build_moonplanbench_cache.py")],
            produces=[_BENCHMARKS / "moonplanbench"],
            network=True,
            note="Google Drive. Veri lisansi CC BY-NC-SA 4.0 -- ticari kullanim yok.",
        ),
        Step(
            key="rtamt",
            title="D3 - rtamt (STL capraz kontrol motoru, opsiyonel)",
            argv=[py, "-m", "pip", "install", "rtamt==0.3.5"],
            produces=[],
            network=True,
            note=(
                "Kurulmazsa app.safety_monitor kendi yerlesik degerlendiricisine "
                "duser ve calisir; kurulursa her istek iki motorla dogrulanir. "
                "antlr4-python3-runtime==4.7 cekiyor."
            ),
        ),
    ]


def _present(step: Step) -> bool:
    return bool(step.produces) and all(p.exists() for p in step.produces)


def _run(step: Step, index: int, total: int) -> tuple[str, float]:
    print()
    print("=" * 78)
    print(f"[{index}/{total}] {step.title}")
    if step.note:
        print(f"        {step.note}")
    print("=" * 78, flush=True)

    missing = [p for p in step.needs if not p.exists()]
    if missing:
        for p in missing:
            print(f"  ! Onkosul yok: {p}")
        return "atlandi (onkosul)", 0.0

    env = dict(os.environ)
    # The console here is cp1254; without this a single arrow or Turkish
    # character in a child's output raises UnicodeEncodeError and kills a
    # step that had otherwise succeeded.
    env["PYTHONIOENCODING"] = "utf-8"

    started = time.monotonic()
    try:
        completed = subprocess.run(step.argv, cwd=str(_ROOT), env=env)
        code = completed.returncode
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - reported, never fatal
        print(f"  ! Calistirilamadi: {exc}")
        return "hata (baslatilamadi)", time.monotonic() - started
    elapsed = time.monotonic() - started

    if code != 0:
        return f"hata (cikis {code})", elapsed
    if step.produces and not _present(step):
        absent = [p.name for p in step.produces if not p.exists()]
        print(f"  ! Cikis 0 ama uretilmesi beklenen dosya yok: {', '.join(absent)}")
        return "eksik cikti", elapsed
    return "tamam", elapsed


def main() -> int:
    steps = _steps()
    keys = [s.key for s in steps]

    parser = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--list", action="store_true", help="adimlari listele ve cik")
    parser.add_argument("--skip-grids", action="store_true",
                        help="P1 gridlerini ve ufuk kubunu yeniden uretme")
    parser.add_argument("--only", default="", help=f"virgullu alt kume: {','.join(keys)}")
    parser.add_argument("--skip", default="", help="virgullu olarak atlanacaklar")
    parser.add_argument("--offline", action="store_true", help="ag gerektiren adimlari atla")
    parser.add_argument("--force", action="store_true",
                        help="ciktisi zaten duran adimlari da yeniden calistir")
    args = parser.parse_args()

    if args.list:
        for s in steps:
            tags = []
            if s.network:
                tags.append("ag")
            if s.destructive:
                tags.append("UZERINE YAZAR")
            suffix = f"  [{', '.join(tags)}]" if tags else ""
            print(f"  {s.key:<10} {s.title}{suffix}")
        return 0

    selected = set(keys)
    if args.only:
        selected = {k.strip() for k in args.only.split(",") if k.strip()}
        unknown = selected - set(keys)
        if unknown:
            print(f"Bilinmeyen adim: {', '.join(sorted(unknown))}", file=sys.stderr)
            return 2
    if args.skip:
        selected -= {k.strip() for k in args.skip.split(",") if k.strip()}
    if args.skip_grids:
        selected -= {"grids", "horizon"}
    if args.offline:
        selected -= {s.key for s in steps if s.network}

    plan = [s for s in steps if s.key in selected]
    if not args.force:
        plan = [s for s in plan if not _present(s)]

    if not plan:
        print("Yapilacak bir sey yok: secilen adimlarin ciktisi zaten duruyor "
              "(--force ile zorlayabilirsin).")
        return 0

    destructive = [s for s in plan if s.destructive]
    print("Calistirilacak adimlar:")
    for s in plan:
        print(f"  - {s.key:<10} {s.title}")
    if destructive:
        print()
        print("DIKKAT: asagidaki adim mevcut veriyi degistirir:")
        for s in destructive:
            print(f"  - {s.title}: {s.note}")

    results: list[tuple[Step, str, float]] = []
    try:
        for index, step in enumerate(plan, start=1):
            status, elapsed = _run(step, index, len(plan))
            results.append((step, status, elapsed))
    except KeyboardInterrupt:
        print("\nKullanici tarafindan durduruldu.")

    print()
    print("=" * 78)
    print("OZET")
    print("=" * 78)
    for step, status, elapsed in results:
        print(f"  {step.key:<10} {status:<22} {elapsed:7.1f} s   {step.title}")
    skipped = [s for s in plan if s.key not in {r[0].key for r in results}]
    for step in skipped:
        print(f"  {step.key:<10} {'calistirilmadi':<22} {0.0:7.1f} s   {step.title}")

    failed = [s for s, status, _ in results if status != "tamam"]
    if failed:
        print()
        print("Tamamlanamayan adimlar:", ", ".join(s.key for s in failed))
        print("Bunlarin ozelligi calismaz durumda kalir; backend onlari "
              "'unavailable' olarak doner, uydurma uretmez.")
        return 1
    print()
    print("Hepsi tamam.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
