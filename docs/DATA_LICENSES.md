# Third-Party Dependency Licenses

Dependencies added during Faz 1 (real physics integration). All verified MIT or BSD —
no GPL. Verify licenses again before adding further dependencies (project is MIT-licensed;
GPL dependencies would create a distribution conflict per the master plan's Global Constraints).

| Package | License | Why |
|---|---|---|
| `pytest` | MIT | Test runner |
| `heat1d` | MIT | Regolith thermal diffusion physics (installed from a pinned GitHub commit — PyPI's release lacks slope/aspect support; see backend/app/thermal_model.py) |
| `numba` | BSD-2-Clause | heat1d transitive dependency (JIT) |
| `llvmlite` | BSD-2-Clause + Apache-2.0-WITH-LLVM-exception | numba transitive dependency |
| `astropy` | BSD-3-Clause | heat1d transitive dependency |
| `spiceypy` | MIT | NAIF SPICE Python bindings (ephemeris/geometry) |

## Bundled data sets

Data shipped inside the build, as opposed to code depended on at runtime. The
same rule applies: the project is MIT-licensed, so a share-alike data set would
create the same distribution conflict a GPL dependency would.

| Data | License | Why |
|---|---|---|
| Yale Bright Star Catalogue (BSC5) | Public domain | The 3-D sky. 9096 naked-eye stars at their J2000 positions with visual magnitude and B-V colour, so the starfield is the real sky rather than random points. Hoffleit & Warren (1991), Yale University Observatory, distributed by the Astronomical Data Center. Packed to `frontend/public/data/bsc5.bin` by `scripts/build_star_catalogue.py`, which records the source URL. |

Considered and rejected: the HYG database, which is the more convenient star
catalogue and carries far more stars, but is CC BY-SA — share-alike, and so the
same conflict as GPL. BSC5 covers everything visible to the eye, which is all a
sky needs.
