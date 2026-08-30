# LiDAR payload karsilastirmasi

Rover `lpr_1`, start `(150, 150)` -> goal `(400, 400)`.
Ayni rota, ayni rover; tek fark surekli sensor + isitici guc cekisi.

| Profil | total_energy_consumed_wh | sensor_overhead_wh | final_battery_pct | total_elapsed_hours | waypoint_count |
|---|---|---|---|---|---|
| LPR-1 (Varsayilan) (LiDAR yok) | 2174.42 | 0.0 | 59.88 | 4.604 | 363 |
| LPR-1 (Varsayilan) + LiDAR (12 W + 8 W isitici) | 2266.5 | 92.08 | 58.18 | 4.604 | 363 |

**Okuma:** `sensor_overhead_wh`, ayni traverse suresi boyunca LiDAR'in
cekmis olacagi enerjidir. `final_battery_pct` bu kadar duser. Bu,
LunaPath'in bir sensor eklemek yerine bir kaynak butcesi kararini
gosterdigi tek yerdir.
