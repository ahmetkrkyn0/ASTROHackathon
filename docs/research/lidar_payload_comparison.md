# LiDAR payload karsilastirmasi

Rover `lpr_1`, start `(150, 150)` -> goal `(400, 400)`.
Ayni rota, ayni rover; tek fark surekli sensor + isitici guc cekisi.

| Profil | total_energy_consumed_wh | sensor_overhead_wh | final_battery_pct | total_elapsed_hours | waypoint_count |
|---|---|---|---|---|---|
| LPR-1 (Varsayilan) (LiDAR yok) | 2165.93 | 0.0 | 60.04 | 4.5941 | 363 |
| LPR-1 (Varsayilan) + LiDAR (12 W + 8 W isitici) | 2257.81 | 91.88 | 58.34 | 4.5941 | 363 |

**Okuma:** `sensor_overhead_wh`, ayni traverse suresi boyunca LiDAR'in
cekmis olacagi enerjidir. `final_battery_pct` bu kadar duser. Bu,
LunaPath'in bir sensor eklemek yerine bir kaynak butcesi kararini
gosterdigi tek yerdir.
