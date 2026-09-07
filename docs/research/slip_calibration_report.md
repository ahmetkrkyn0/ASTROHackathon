# Slip kalibrasyonu (C3) — Site11 önce/sonra raporu

Üretim: `scripts/slip_calibration_report.py`, 2026-09-04T21:40:20Z. Model `anchored_loglinear_v1`, etiket `MODEL`, kap 0,9. Monte Carlo 1000 koşum, tohum 0.

**İddia sınırı.** Eğri **ölçülmüş değil, literatüre bağlı bir MODEL**: VIPER'ın PSJ 2025'te yayımlanan mobilite tasarım gereksinimi ("a maximum of 40% slip up a maximum slope of 15°"; GRC-1 simülantı, %15–20 bağıl yoğunluk — bir üst sınır, tipik değer değil) ile Yutu-2'nin Chang'e-4'te ölçülmüş slip oranı (0 … −0,075, ≤ 8,86° eğimlerde, çoğunlukla skid; Nature Communications 2024) çapalardır; çapalar arası ve ötesi üstel biçim ile çapaların diğer rover'lara aktarımı **varsayımdır** ve katalogda `assumption:` ile yazılıdır. Kutup regolitinde ölçülmüş slip yoktur; Diviner termal atalet modülasyonu (Cunningham RSS 2017) yalnızca kancadır.

## 1. Çapalar ve kaynaklar

| Rover | Eğim | Slip μ | σ | Tür | Kaynak |
|---|---|---|---|---|---|
| `lpr_1` | 0,00° | 0,0375 | 0,0187 | `assumption` | assumption: flat-ground slip transferred from Yutu-2's Chang'e-4 measurement (flat-ground slip of a driven wheel is only weakly terrain-dependent); no published flat-ground slip for this profile | Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip ratios are between 0 and -0.075' (skid) on slopes up to 8.86 deg; the magnitude midpoint of |0..0.075| is taken as the flat-ground value and sigma = range/4 -- Nature Communications 2024 (PMC11258293), Methods, 'Lunar regolith parameter estimation' |
| `lpr_1` | 15,00° | 0,4000 | 0,2000 | `assumption` | assumption: VIPER's 15 deg design ceiling used as this profile's 15 deg anchor; no published slip-versus-slope data for this vehicle | VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' (an upper bound, not a typical value); GRC-1 simulant at 15-20 percent relative density, MGRU test unit, slip from wheel rotation rates against Optitrack motion tracking -- PSJ 2025 (10.3847/PSJ/add13f) sect. 3.5 and 3.2. sigma: assumption, Yutu-2's relative spread (sigma/mu = 0.5) transferred |
| `luvmi_m` | 0,00° | 0,0375 | 0,0187 | `assumption` | assumption: flat-ground slip transferred from Yutu-2's Chang'e-4 measurement (flat-ground slip of a driven wheel is only weakly terrain-dependent); no published flat-ground slip for this profile | Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip ratios are between 0 and -0.075' (skid) on slopes up to 8.86 deg; the magnitude midpoint of |0..0.075| is taken as the flat-ground value and sigma = range/4 -- Nature Communications 2024 (PMC11258293), Methods, 'Lunar regolith parameter estimation' |
| `luvmi_m` | 15,00° | 0,4000 | 0,2000 | `assumption` | assumption: VIPER's 15 deg design ceiling used as this profile's 15 deg anchor; no published slip-versus-slope data for this vehicle | VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' (an upper bound, not a typical value); GRC-1 simulant at 15-20 percent relative density, MGRU test unit, slip from wheel rotation rates against Optitrack motion tracking -- PSJ 2025 (10.3847/PSJ/add13f) sect. 3.5 and 3.2. sigma: assumption, Yutu-2's relative spread (sigma/mu = 0.5) transferred |
| `nasa_viper` | 0,00° | 0,0375 | 0,0187 | `assumption` | assumption: flat-ground slip transferred from Yutu-2's Chang'e-4 measurement (flat-ground slip of a driven wheel is only weakly terrain-dependent); no published flat-ground slip for this profile | Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip ratios are between 0 and -0.075' (skid) on slopes up to 8.86 deg; the magnitude midpoint of |0..0.075| is taken as the flat-ground value and sigma = range/4 -- Nature Communications 2024 (PMC11258293), Methods, 'Lunar regolith parameter estimation' |
| `nasa_viper` | 15,00° | 0,4000 | 0,2000 | `design_constraint` | VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' (an upper bound, not a typical value); GRC-1 simulant at 15-20 percent relative density, MGRU test unit, slip from wheel rotation rates against Optitrack motion tracking -- PSJ 2025 (10.3847/PSJ/add13f) sect. 3.5 and 3.2. sigma: assumption, Yutu-2's relative spread (sigma/mu = 0.5) transferred |
| `cnsa_yutu_2` | 0,00° | 0,0375 | 0,0187 | `measured` | Yutu-2 (Chang'e-4) measured wheel slip ratio: 'most the wheel slip ratios are between 0 and -0.075' (skid) on slopes up to 8.86 deg; the magnitude midpoint of |0..0.075| is taken as the flat-ground value and sigma = range/4 -- Nature Communications 2024 (PMC11258293), Methods, 'Lunar regolith parameter estimation' |
| `cnsa_yutu_2` | 8,86° | 0,0750 | 0,0187 | `measured_bound` | Yutu-2 (Chang'e-4) measured: the upper end of the |0..0.075| slip range at the steepest slope driven (8.86 deg, outbound traverse) -- Nature Communications 2024 (PMC11258293), Results, 'Topographic and mobility hazards analysis' |
| `cnsa_yutu_2` | 15,00° | 0,4000 | 0,2000 | `assumption` | assumption: VIPER's 15 deg design ceiling used as this profile's 15 deg anchor; no published slip-versus-slope data for this vehicle | VIPER mobility design requirement: 'a maximum of 40% slip up a maximum slope of 15 deg' (an upper bound, not a typical value); GRC-1 simulant at 15-20 percent relative density, MGRU test unit, slip from wheel rotation rates against Optitrack motion tracking -- PSJ 2025 (10.3847/PSJ/add13f) sect. 3.5 and 3.2. sigma: assumption, Yutu-2's relative spread (sigma/mu = 0.5) transferred |

## 2. Eğri (0/5/10/15/20/25°): slip μ (σ) · süre/enerji çarpanı 1/(1−μ)

| Eğim | `lpr_1` | `luvmi_m` | `nasa_viper` | `cnsa_yutu_2` |
|---|---|---|---|---|
| 0° | 0,037 (0,019) · ×1,04 | 0,037 (0,019) · ×1,04 | 0,037 (0,019) · ×1,04 | 0,037 (0,019) · ×1,04 |
| 5° | 0,083 (0,041) · ×1,09 | 0,083 (0,041) · ×1,09 | 0,083 (0,041) · ×1,09 | 0,055 (0,020) · ×1,06 |
| 10° | 0,182 (0,091) · ×1,22 | 0,182 (0,091) · ×1,22 | 0,182 (0,091) · ×1,22 | 0,102 (0,030) · ×1,11 |
| 15° | 0,400 (0,200) · ×1,67 | 0,400 (0,200) · ×1,67 | 0,400 (0,200) · ×1,67 | 0,400 (0,200) · ×1,67 |
| 20° | 0,881 (0,440) · ×8,37 | 0,881 (0,440) · ×8,37 | 0,881 (0,440) · ×8,37 | 0,900 (0,450) · ×10,00 |
| 25° | 0,900 (0,450) · ×10,00 | 0,900 (0,450) · ×10,00 | 0,900 (0,450) · ×10,00 (eğim sınırı dışı) | 0,900 (0,450) · ×10,00 (eğim sınırı dışı) |

## 3. Standart rotalar, `/api/plan-4d`: slip'siz → slip'li

| Rota | Varyant | Dilim × saat | Ufuk (h) | Hamle / bekleme | Varış (h) | En düşük SOC (%) | Maks gölge (h) | LP-R01 ρ (h) | LP-R02 ρ (pct) | LP-R06 ρ (°) | LP-R07 ρ (°) | Rota ort. / maks slip | Slip'in eklediği saat / Wh | Mesafe çarpanı | Düğüm | Planlama (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| VIPER haven→haven, 30 May 2027 | slip'siz (önce) | 108 × 0,0956 | 10,32 | 40 / 0 | 7,36 (havende biter) | 32,1 | 4,55 | 91,45 | 12,06 | 0,48 | 1,19 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 29 394 | 5,4 |
| VIPER haven→haven, 30 May 2027 | slip'siz (önce), haven kuralı yok | 108 × 0,0956 | 10,32 | 40 / 0 | 7,36 (havende biter) | 32,1 | 4,55 | 91,45 | 12,06 | 0,48 | 1,19 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 31 806 | 5,2 |
| VIPER haven→haven, 30 May 2027 | slip'siz (önce), 24 h ufuk (güneşte bekleme serbest) | 252 × 0,0956 | 24,09 | 40 / 0 | 7,36 (havende biter) | 32,1 | 4,55 | 91,45 | 12,06 | 0,48 | 1,19 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 29 394 | 7,2 |
| VIPER haven→haven, 30 May 2027 | slip'li (C3) | **404** (51,3 s): No path found for NASA VIPER: 283148 edges would have drained the battery below the 20 percent reserve; 135398 transitions would have left the rover unable to reach a safe haven before the Earth sets (require_safe_haven: 96 h shadow endurance); 151105 edges exceeded the 15 deg roll-over (cross-slope) limit; 33414 edges would have arrived past the last of 123 slices (14.5 h). (the shortest gated coarse route needs at least 40 moves at 123 slices of 0.1176 h) Safe-haven rule: 862 coarse cells are havens for NASA VIPER (96 h endurance); the start block is 0.00 h from the nearest with 253.3 h of Earth link left. | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| VIPER haven→haven, 30 May 2027 | slip'li (C3), haven kuralı yok | **404** (88,2 s): No path found for NASA VIPER: 481271 edges would have drained the battery below the 20 percent reserve; 167769 edges exceeded the 15 deg roll-over (cross-slope) limit; 398039 edges would have arrived past the last of 123 slices (14.5 h). (the shortest gated coarse route needs at least 40 moves at 123 slices of 0.1176 h) | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| VIPER haven→haven, 30 May 2027 | slip'li (C3), 24 h ufuk (güneşte bekleme serbest) | **404** (37,7 s): No path found for NASA VIPER: 394597 edges would have drained the battery below the 20 percent reserve; 155201 transitions would have left the rover unable to reach a safe haven before the Earth sets (require_safe_haven: 96 h shadow endurance); 174150 edges exceeded the 15 deg roll-over (cross-slope) limit; 67 edges would have arrived past the last of 205 slices (24.1 h). (the shortest gated coarse route needs at least 40 moves at 205 slices of 0.1176 h) Safe-haven rule: 862 coarse cells are havens for NASA VIPER (96 h endurance); the start block is 0.00 h from the nearest with 253.0 h of Earth link left. | — | — | — | — | — | — | — | — | — | — | — | — | — | — |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'siz (önce) | 38 × 0,0956 | 3,63 | 8 / 0 | 1,53 (havende biter) | 85,4 | 0,93 | 95,07 | 65,44 | 2,35 | 2,81 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 261 | 2,6 |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'li (C3) | 43 × 0,1176 | 5,06 | 8 / 0 | 2,23 (havende biter) | 72,3 | 1,76 | 94,24 | 52,28 | 2,35 | 2,81 | 0,465 / 0,532 | 0,83 / 526 | 1,896 | 1 491 | 2,8 |
| LPR-1, 28 Eyl 2026 | slip'siz (önce) | 108 × 0,0287 | 3,10 | 40 / 0 | 2,16 (havende bitmez) | 96,2 | 0,21 | 49,79 | 76,16 | 5,63 | 4,19 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 8 799 | 3,9 |
| LPR-1, 28 Eyl 2026 | slip'li (C3) | 120 × 0,0359 | 4,31 | 41 / 0 | 2,98 (havende bitmez) | 92,5 | 0,52 | 49,48 | 72,48 | 7,35 | 2,61 | 0,326 / 0,537 | 0,75 / 321 | 1,532 | 23 177 | 9,8 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'siz (önce) | 273 × 0,0287 | 7,85 | 114 / 0 | 5,35 (havende bitmez) | 72,7 | 4,03 | 45,97 | 52,68 | 5,38 | 5,47 | 0,000 / 0,000 | 0,00 / 0 | 1,000 | 53 365 | 7,4 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'li (C3) | 270 × 0,0359 | 9,69 | 116 / 0 | 6,75 (havende bitmez) | 67,4 | 4,80 | 45,20 | 47,45 | 9,83 | 6,78 | 0,149 / 0,343 | 0,74 / 279 | 1,181 | 146 705 | 20,6 |

## 4. B5 Monte Carlo (SHERPA, 1000 koşum, tohum 0)

| Rota | Varyant | Tamamlanma | Rezerv içinde | Tam başarı | Nominal süre (h) | Nominal en düşük SOC (%) | Karar |
|---|---|---|---|---|---|---|---|
| VIPER haven→haven, 30 May 2027 | slip'siz (önce) | 29,6 % (26,9–32,5) | 1,4 % (0,8–2,3) | 1,4 % (0,8–2,3) | 7,27 | 23,2 | 296/1000 runs reached the goal (95% CI 26.9-32.5%), 14/1000 without touching the reserve; 14/1000 with every margin intact (95% CI 0.8-2.3%). |
| VIPER haven→haven, 30 May 2027 | slip'li (C3) | — | — | — | — | — | No path found for NASA VIPER: 283148 edges would have drained the battery below the 20 percent reserve; 135398 transitions would have left the rover unable to reach a safe haven before the Earth sets (require_safe_haven: 96 h shadow endurance); 151105 edges exceeded the 15 deg roll-over (cross-slope) limit; 33414 edges would have arrived past the last of 123 slices (14.5 h). (the shortest gated coarse route needs at least 40 moves at 123 slices of 0.1176 h) Safe-haven rule: 862 coarse cells are havens for NASA VIPER (96 h endurance); the start block is 0.00 h from the nearest with 253.3 h of Earth link left. |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'siz (önce) | 100,0 % (99,6–100,0) | 99,7 % (99,1–99,9) | 99,7 % (99,1–99,9) | 1,44 | 83,8 | 1000/1000 runs reached the goal (95% CI 99.6-100.0%), 997/1000 without touching the reserve; 997/1000 with every margin intact (95% CI 99.1-99.9%). |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'li (C3) | 99,6 % (99,0–99,8) | 95,0 % (93,5–96,2) | 95,0 % (93,5–96,2) | 2,15 | 71,0 | 996/1000 runs reached the goal (95% CI 99.0-99.8%), 950/1000 without touching the reserve; 950/1000 with every margin intact (95% CI 93.5-96.2%). |
| LPR-1, 28 Eyl 2026 | slip'siz (önce) | 100,0 % (99,6–100,0) | 100,0 % (99,6–100,0) | 0,0 % (0,0–0,4) | 2,13 | 97,9 | 1000/1000 runs reached the goal (95% CI 99.6-100.0%), 1000/1000 without touching the reserve; 0/1000 with every margin intact (95% CI 0.0-0.4%). No safe haven is reachable from any state of this route on this lunar day, so the haven rule fails every run. |
| LPR-1, 28 Eyl 2026 | slip'li (C3) | 100,0 % (99,6–100,0) | 99,8 % (99,3–100,0) | 0,0 % (0,0–0,4) | 2,94 | 94,5 | 1000/1000 runs reached the goal (95% CI 99.6-100.0%), 998/1000 without touching the reserve; 0/1000 with every margin intact (95% CI 0.0-0.4%). No safe haven is reachable from any state of this route on this lunar day, so the haven rule fails every run. |

## 5. Aynı çiftler, `/api/plan` (2-B simülasyon)

| Rota | Varyant | Mesafe (km) | Süre (h) | Tüketim (Wh) | Güneş (Wh) | En düşük SOC (%) | Maks sürüş eğimi (°) | LP-R02 ρ | Rota ort. slip | Slip'in eklediği saat / Wh |
|---|---|---|---|---|---|---|---|---|---|---|
| VIPER haven→haven, 30 May 2027 | slip'siz (önce) | 0,910 | 4,33 | 2156 | 842 | 67,2 | 17,4 | 47,15 | 0,000 | 0,00 / 0 |
| VIPER haven→haven, 30 May 2027 | slip'li (C3) | 0,910 | 5,40 | 2742 | 1047 | 57,6 | 17,4 | 37,64 | 0,174 | 1,08 / 587 |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'siz (önce) | 0,185 | 0,92 | 540 | 180 | 91,0 | 17,5 | 71,00 | 0,000 | 0,00 / 0 |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'li (C3) | 0,185 | 1,55 | 920 | 305 | 84,6 | 17,5 | 64,62 | 0,392 | 0,64 / 380 |
| LPR-1, 28 Eyl 2026 | slip'siz (önce) | 0,910 | 1,30 | 469 | 232 | 95,6 | 17,4 | 75,62 | 0,000 | 0,00 / 0 |
| LPR-1, 28 Eyl 2026 | slip'li (C3) | 0,910 | 1,62 | 597 | 289 | 94,3 | 17,4 | 74,31 | 0,175 | 0,33 / 129 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'siz (önce) | 2,727 | 3,85 | 1288 | 676 | 88,7 | 14,9 | 68,70 | 0,000 | 0,00 / 0 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'li (C3) | 2,727 | 4,37 | 1466 | 767 | 87,1 | 14,9 | 67,10 | 0,115 | 0,52 / 183 |

## 6. Varsayılan ufuk: eski sınır (BFS hamle × en yavaş kenar) ↔ yeni sınır (en hızlı rota); tavan 1000

| Rota | Varyant | BFS hamle | En yavaş kenar (dilim) | Eski sınır (dilim) | En hızlı rota (h / hamle) | Yeni sınır (dilim) | Uçtaki `n_slices` |
|---|---|---|---|---|---|---|---|
| VIPER haven→haven, 30 May 2027 | slip'siz (önce) | 40 | 2 | 100 | 4,55 / 40 | 108 | 108 |
| VIPER haven→haven, 30 May 2027 | slip'li (C3) | 40 | 11 | 460 | 7,23 / 41 | 123 | — (404) |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'siz (önce) | 8 | 2 | 36 | 0,93 / 8 | 38 | 38 |
| VIPER kısa leg (358,494)→(346,462), 30 May 2027 | slip'li (C3) | 8 | 11 | 108 | 1,76 / 8 | 43 | 43 |
| LPR-1, 28 Eyl 2026 | slip'siz (önce) | 40 | 2 | 100 | 1,36 / 40 | 108 | 108 |
| LPR-1, 28 Eyl 2026 | slip'li (C3) | 40 | 14 | 580 | 2,15 / 40 | 120 | 120 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'siz (önce) | 113 | 2 | 246 | 4,02 / 113 | 273 | 273 |
| LPR-1 Ay gecesi, 13 Eyl 2026 | slip'li (C3) | 113 | 14 | 1602 **(tavan üstü)** | 4,80 / 116 | 270 | 270 |

## 7. Okuma

- **VIPER haven→haven, 30 May 2027**: slip'siz 200, slip'li **404**; haven kuralı yok: 404; 24 h ufuk (güneşte bekleme serbest): 404; 2-B: süre 4,33 → 5,40 h, tüketim 2156 → 2742 Wh (×1,27), en düşük SOC %67,2 → %57,6.
- **VIPER kısa leg (358,494)→(346,462), 30 May 2027**: varış 1,53 → 2,23 h (×1,46); en düşük SOC %85,4 → %72,3; hamle 8 → 8, bekleme 0 → 0; rota ortalama slip 0,465 (maks 0,532 @ 16,8°), slip'in eklediği 0,83 h / 526 Wh; LP-R02 ρ 65,44 → 52,28 pct; dilim 38 × 0,0956 h → 43 × 0,1176 h; B5 tamamlanma 100,0 % (99,6–100,0) → 99,6 % (99,0–99,8), tam başarı 99,7 % (99,1–99,9) → 95,0 % (93,5–96,2), nominal en düşük SOC %83,8 → %71,0; 2-B: süre 0,92 → 1,55 h, tüketim 540 → 920 Wh (×1,70), en düşük SOC %91,0 → %84,6.
- **LPR-1, 28 Eyl 2026**: varış 2,16 → 2,98 h (×1,38); en düşük SOC %96,2 → %92,5; hamle 40 → 41, bekleme 0 → 0; rota ortalama slip 0,326 (maks 0,537 @ 16,9°), slip'in eklediği 0,75 h / 321 Wh; LP-R02 ρ 76,16 → 72,48 pct; dilim 108 × 0,0287 h → 120 × 0,0359 h; B5 tamamlanma 100,0 % (99,6–100,0) → 100,0 % (99,6–100,0), tam başarı 0,0 % (0,0–0,4) → 0,0 % (0,0–0,4), nominal en düşük SOC %97,9 → %94,5; 2-B: süre 1,30 → 1,62 h, tüketim 469 → 597 Wh (×1,27), en düşük SOC %95,6 → %94,3.
- **LPR-1 Ay gecesi, 13 Eyl 2026**: varış 5,35 → 6,75 h (×1,26); en düşük SOC %72,7 → %67,4; hamle 114 → 116, bekleme 0 → 0; rota ortalama slip 0,149 (maks 0,343 @ 14,0°), slip'in eklediği 0,74 h / 279 Wh; LP-R02 ρ 52,68 → 47,45 pct; dilim 273 × 0,0287 h → 270 × 0,0359 h; 2-B: süre 3,85 → 4,37 h, tüketim 1288 → 1466 Wh (×1,14), en düşük SOC %88,7 → %87,1.

Sunum cümlesi: **Slip eğrimiz VIPER'ın 15°/%40 tasarım kısıtına ve Yutu-2'nin ölçülmüş regolit parametrelerine bağlı.** Tasarım: `docs/superpowers/specs/2026-09-04-c3-slip-calibration-design.md`.
