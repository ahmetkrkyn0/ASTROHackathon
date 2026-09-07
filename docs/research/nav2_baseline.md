# Nav2 baseline karsilastirmasi

Start `(150, 150)` -> Goal `(400, 400)`, 5 m/px grid, 500x500.

| Planlayici | waypoints | length_km | max_slope_deg | mean_shadow_ratio | min_thermal_c | time_ms |
|---|---|---|---|---|---|---|
| SmacPlanner2D-equivalent (geometric) | 363 | 2.104 | 25.0 | 0.5295 | -139.24 | 6143.0 |
| LunaPath multi-criteria A* | 409 | 2.475 | 24.22 | 0.5206 | -137.71 | 2395.4 |

**Okuma:** Geometrik baseline en kisa gecilebilir yolu bulur ve arazinin
maliyetini bilmez. LunaPath'in rotasi daha uzun olabilir; karsiliginda
`max_slope_deg` ve `mean_shadow_ratio` degerleri dusuktur. Fark, cok
kriterli maliyet modelinin satin aldigi seydir.

```json
{
  "SmacPlanner2D-equivalent (geometric)": {
    "waypoints": 363,
    "length_km": 2.104,
    "max_slope_deg": 25.0,
    "mean_shadow_ratio": 0.5295,
    "min_thermal_c": -139.24,
    "time_ms": 6143.0
  },
  "LunaPath multi-criteria A*": {
    "waypoints": 409,
    "length_km": 2.475,
    "max_slope_deg": 24.22,
    "mean_shadow_ratio": 0.5206,
    "min_thermal_c": -137.71,
    "time_ms": 2395.4
  }
}
```
