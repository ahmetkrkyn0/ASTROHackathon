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
