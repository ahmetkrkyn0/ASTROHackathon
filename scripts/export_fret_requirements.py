#!/usr/bin/env python3
"""Write docs/requirements/lunapath.fret.json from the safety catalogue (D3).

The catalogue in backend/app/safety_monitor.py is the single source of the
requirements; this file is its FRET-style export. A test
(backend/test_safety_monitor.py::test_checked_in_fret_file_matches_the_catalogue)
fails when the two drift, so re-run this after editing the catalogue:

    python scripts/export_fret_requirements.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "backend"))

from app.safety_monitor import fret_export  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--out",
        default=str(_ROOT / "docs" / "requirements" / "lunapath.fret.json"),
        help="output path (default: docs/requirements/lunapath.fret.json)",
    )
    args = parser.parse_args()
    document = fret_export()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(document['requirements'])} requirements to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
