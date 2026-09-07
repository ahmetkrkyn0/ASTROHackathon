# LiDAR payload karsilastirmasi

Rover `lpr_1`, start `(150, 150)` -> goal `(400, 400)`.
Ayni rota, ayni rover; tek fark surekli sensor + isitici guc cekisi.

| Profil | total_energy_consumed_wh | sensor_overhead_wh | final_battery_pct | total_elapsed_hours | waypoint_count |
|---|---|---|---|---|---|
| LPR-1 (Varsayilan) (LiDAR yok) | 1760.89 | 0.0 | 67.51 | 3.8076 | 409 |
| LPR-1 (Varsayilan) + LiDAR (12 W + 8 W isitici) | 1837.04 | 76.15 | 66.1 | 3.8076 | 409 |

**Okuma:** `sensor_overhead_wh`, ayni traverse suresi boyunca LiDAR'in
cekmis olacagi enerjidir. `final_battery_pct` bu kadar duser. Bu,
LunaPath'in bir sensor eklemek yerine bir kaynak butcesi kararini
gosterdigi tek yerdir.
