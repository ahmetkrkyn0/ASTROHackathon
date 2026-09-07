# Monte Carlo traverse stres testi — SHERPA protokolü Site11 rotalarında (B5)

Üretildi: `scripts/stress_test_report.py` ile, 2026-09-04. Koşum sayısı 1000, tohum 0. Dağılımlar Shirley & Balaban 2022: başlangıç gecikmesi σ 2 h, başlangıç bataryası σ %20 (aşağı), güç çekişi σ %20 (yukarı), etkin hız σ %20/30/40/50 (aşağı, taban 0,25). DSN kesintisi için yayınlanmış oran yok; duyarlılık p = 0.1, ortalama 4.0 h.

Oranlar Wilson %95 güven aralığıyla. `tam başarı` = hedefe varış ∧ batarya hiç rezervin altına inmedi ∧ (haven alanları biliniyorsa) hiçbir durumda Dünya batış süresi aşılmadı.

## VIPER haven->haven, 30 May 2027

Rover `nasa_viper`, epoch `2027-05-30T00:00:00`, başlangıç (358, 494) → hedef (206, 426) (ince piksel), coarsen 4, `require_safe_haven` = true.

Plan: 40 MOVE, 0 WAIT, varış 7,36 h, dilim 0,0956 h, en düşük batarya 32,1 %, haven marjı 199,8 h, DSN marjı 199,9 h, 0-SOC marjı 9,9 h; planlama 10,5 s.

| Varyant | Tamamlanma | Rezerv içinde | Tam başarı | Rezerv ihlali | Batarya / gölge / ufuk | Süre p50 / p95 (h) | Normalize p95 | Min batarya p5 (%) | Maks gölge p95 (h) | DSN marjı min p5 (h) | 0-SOC marjı p5 (h) | Süre (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hız σ 20 % | 29,6 % (26,9–32,5) | 1,4 % (0,8–2,3) | 1,4 % (0,8–2,3) | 98,6 % (97,7–99,2) | 704 / 0 / 0 | 7,12 / 8,82 | 1,20 | 0,0 | 6,81 | 195,6 | 0,0 | 1,4 |
| hız σ 30 % | 22,3 % (19,8–25,0) | 1,0 % (0,5–1,8) | 1,0 % (0,5–1,8) | 99,0 % (98,2–99,5) | 777 / 0 / 0 | 6,94 / 8,88 | 1,21 | 0,0 | 6,71 | 195,3 | 0,0 | 1,1 |
| hız σ 40 % | 17,9 % (15,7–20,4) | 0,9 % (0,5–1,7) | 0,9 % (0,5–1,7) | 99,1 % (98,3–99,5) | 821 / 0 / 0 | 6,88 / 8,99 | 1,22 | 0,0 | 6,69 | 195,1 | 0,0 | 1,1 |
| hız σ 50 % | 15,8 % (13,7–18,2) | 0,9 % (0,5–1,7) | 0,9 % (0,5–1,7) | 99,1 % (98,3–99,5) | 842 / 0 / 0 | 6,84 / 9,01 | 1,22 | 0,0 | 6,64 | 195,0 | 0,0 | 1,0 |
| DSN p = 0.1 (hız σ 20 %) | 28,0 % (25,3–30,9) | 1,4 % (0,8–2,3) | 1,4 % (0,8–2,3) | 98,6 % (97,7–99,2) | 720 / 0 / 0 | 7,27 / 10,02 | 1,36 | 0,0 | 7,89 | 195,0 | 0,0 | 1,1 |

Nominal koşum (tüm çarpanlar 1): süre 7,27 h, en düşük batarya 23,2 %, maks gölge 7,27 h, DSN marjı 199,2 h. Karar: 296/1000 runs reached the goal (95% CI 26.9-32.5%), 14/1000 without touching the reserve; 14/1000 with every margin intact (95% CI 0.8-2.3%). Gökyüzü `spice_horizon`, safe haven `spice_horizon`. Süre dağılımı: gökyüzü 0,79 s, koşumlar 0,51 s.

DSN kesintisi duyarlılığı: 112 koşumda kesinti, ortalama pencere 3,87 h, ortalama bekleme 3,23 h.

## LPR-1, 28 Sep 2026

Rover `lpr_1`, epoch `2026-09-28T00:00:00`, başlangıç (358, 494) → hedef (206, 426) (ince piksel), coarsen 4, `require_safe_haven` = false.

Plan: 40 MOVE, 0 WAIT, varış 2,16 h, dilim 0,0287 h, en düşük batarya 96,2 %, haven marjı - h, DSN marjı 184,6 h, 0-SOC marjı 80,2 h; planlama 8,1 s.

| Varyant | Tamamlanma | Rezerv içinde | Tam başarı | Rezerv ihlali | Batarya / gölge / ufuk | Süre p50 / p95 (h) | Normalize p95 | Min batarya p5 (%) | Maks gölge p95 (h) | DSN marjı min p5 (h) | 0-SOC marjı p5 (h) | Süre (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hız σ 20 % | 100,0 % (99,6–100,0) | 100,0 % (99,6–100,0) | 0,0 % (0,0–0,4) | 0,0 % (0,0–0,4) | 0 / 0 / 0 | 3,10 / 5,52 | 2,56 | 52,3 | 1,59 | 180,4 | 36,8 | 2,4 |
| hız σ 30 % | 100,0 % (99,6–100,0) | 100,0 % (99,6–100,0) | 0,0 % (0,0–0,4) | 0,0 % (0,0–0,4) | 0 / 0 / 0 | 3,33 / 5,96 | 2,77 | 50,3 | 1,95 | 180,4 | 33,5 | 2,5 |
| hız σ 40 % | 100,0 % (99,6–100,0) | 99,9 % (99,4–100,0) | 0,0 % (0,0–0,4) | 0,1 % (0,0–0,6) | 0 / 0 / 0 | 3,50 / 6,31 | 2,93 | 47,4 | 2,48 | 180,3 | 31,9 | 2,5 |
| hız σ 50 % | 100,0 % (99,6–100,0) | 99,8 % (99,3–100,0) | 0,0 % (0,0–0,4) | 0,2 % (0,1–0,7) | 0 / 0 / 0 | 3,63 / 6,54 | 3,03 | 46,0 | 2,74 | 180,3 | 30,9 | 2,7 |
| DSN p = 0.1 (hız σ 20 %) | 100,0 % (99,6–100,0) | 100,0 % (99,6–100,0) | 0,0 % (0,0–0,4) | 0,0 % (0,0–0,4) | 0 / 0 / 0 | 3,29 / 6,99 | 3,24 | 51,0 | 4,89 | 179,2 | 35,4 | 2,5 |

Nominal koşum (tüm çarpanlar 1): süre 2,13 h, en düşük batarya 97,9 %, maks gölge 0,28 h, DSN marjı 184,1 h. Karar: 1000/1000 runs reached the goal (95% CI 99.6-100.0%), 1000/1000 without touching the reserve; 0/1000 with every margin intact (95% CI 0.0-0.4%). No safe haven is reachable from any state of this route on this lunar day, so the haven rule fails every run. Gökyüzü `spice_horizon`, safe haven `spice_horizon`. Süre dağılımı: gökyüzü 2,35 s, koşumlar 0,07 s.

DSN kesintisi duyarlılığı: 112 koşumda kesinti, ortalama pencere 3,87 h, ortalama bekleme 3,08 h.

