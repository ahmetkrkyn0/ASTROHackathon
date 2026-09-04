# Formal güvenlik gereksinimleri — FRETISH + STL robustness monitörü Site11 rotalarında (D3)

Üretildi: `scripts/safety_monitor_report.py` ile, 2026-09-04. Motor: RTAMT 0.3.5 (ANTLR runtime 4.9.3) + yerleşik değerlendirici, her istekte çapraz kontrol. Gereksinimler `docs/requirements/lunapath.fret.json` (FRETISH, elle STL'e çevrildi; FRET aracı kullanılmadı). Her sonuç **bu rotanın çalışma-zamanı izlemesidir**; hiçbir sonuç model checking ile ispat değildir.

ρ ≥ 0 sağlandı, ρ < 0 ihlal; |ρ| gereksinimin biriminde marj. ρ/ölçek: eşik (tek taraflı), yarı genişlik (aralık), 24 h (Dünya/haven), rota uzunluğu (hedef) ile bölünmüş birimsiz kıyas anahtarı.

Okuma notu: LP-R04/LP-R05'in iç sıcaklığı statik termal katman (`thermal_field: sunlit_peak`, gölgeye bağlı) artı `cost_engine.surface_to_inner`'ın rover ofsetidir (LPR-1/VIPER: soğuk dalda +60 K, sıcak dalda −40 K); ısıtıcı gücü enerji modelinde sayılır ama bu sıcaklık modelinde ısıtma yoktur. Bir termal ihlal, rota kadar bu modelin rover zarfıyla tutarsızlığını da ölçer. LP-R09'da `—` ile `hayır`: sonlu Dünya batışına karşı ulaşılabilir haven yok (sınırsız ihlal).

## 1. 4-B planlar (`/api/plan-4d`)

### VIPER haven->haven, 30 May 2027

Rover `nasa_viper`, epoch `2027-05-30T00:00:00`, (358, 494) → (206, 426), coarsen 4, `require_safe_haven` = true; 40 MOVE, 0 WAIT, varış 7,36 h, dilim 0,0956 h, 41 durum; Dünya modeli `spice_horizon`, haven `spice_horizon`; planlama 10,2 s.

| ID | Gereksinim | ρ | Birim | ρ/ölçek | Sağlandı | Eşik (kaynak) | En kötü nokta | Motor |
|---|---|---|---|---|---|---|---|---|
| LP-R01 | `shadow_endurance` | 91,45 | h | 0,953 | evet | 96 (rover) | #40 @ 7,36 h (51, 106) | rtamt |
| LP-R02 | `soc_reserve` | 12,06 | pct | 0,603 | evet | 20 (rover) | #40 @ 7,36 h (51, 106) | rtamt |
| LP-R03 | `soc_recovery` | 6,00 | h | 1,000 | evet | 6 (catalogue) | #0 @ 0,00 h (89, 123) | rtamt |
| LP-R04 | `electronics_thermal` | -7,96 | degC | -0,227 | **hayır** | -20…50 (rover) | #16 @ 2,77 h (73, 118) | rtamt |
| LP-R05 | `battery_thermal` | -27,96 | degC | -1,598 | **hayır** | 0…35 (rover) | #16 @ 2,77 h (73, 118) | rtamt |
| LP-R06 | `step_slope` | 0,48 | deg | 0,024 | evet | 20 (rover) | #9 @ 1,72 h (80, 118) | rtamt |
| LP-R07 | `cross_slope` | 1,19 | deg | 0,080 | evet | 15 (rover) | #25 @ 4,49 h (64, 118) | rtamt |
| LP-R08 | `dte_while_moving` | 199,93 | h | 8,331 | evet | 0 (fixed) | #8 @ 1,53 h (81, 118) | rtamt |
| LP-R09 | `safe_haven_leg` | 199,80 | h | 8,325 | evet | 0 (fixed) | #8 @ 1,53 h (81, 118) | rtamt |
| LP-R10 | `goal_reached` | 0,00 | m | 0,000 | evet (sınır) | 0 (fixed) | #40 @ 7,36 h (51, 106) | rtamt |
| LP-R11 | `soc_at_goal` | 12,06 | pct | 0,603 | evet | 20 (rover) | #40 @ 7,36 h (51, 106) | builtin |

Karar **violated**; uygulanabilir 11, ihlal 2 (LP-R04, LP-R05); en küçük marj **LP-R05** ρ = -27,96 degC (ρ/ölçek -1,598).
Motor `rtamt` (rtamt 0.3.5), yerleşik motorla en büyük fark 0; iz: 41 örnek, 7,36 h.

### LPR-1, 28 Sep 2026

Rover `lpr_1`, epoch `2026-09-28T00:00:00`, (358, 494) → (206, 426), coarsen 4, `require_safe_haven` = false; 40 MOVE, 0 WAIT, varış 2,16 h, dilim 0,0287 h, 41 durum; Dünya modeli `spice_horizon`, haven `spice_horizon`; planlama 8,5 s.

| ID | Gereksinim | ρ | Birim | ρ/ölçek | Sağlandı | Eşik (kaynak) | En kötü nokta | Motor |
|---|---|---|---|---|---|---|---|---|
| LP-R01 | `shadow_endurance` | 49,79 | h | 0,996 | evet | 50 (rover) | #5 @ 0,29 h (84, 118) | rtamt |
| LP-R02 | `soc_reserve` | 76,16 | pct | 3,808 | evet | 20 (rover) | #34 @ 1,81 h (55, 112) | rtamt |
| LP-R03 | `soc_recovery` | 6,00 | h | 1,000 | evet | 6 (catalogue) | #0 @ 0,00 h (89, 123) | rtamt |
| LP-R04 | `electronics_thermal` | -17,96 | degC | -0,718 | **hayır** | -10…40 (rover) | #16 @ 0,80 h (73, 118) | rtamt |
| LP-R05 | `battery_thermal` | -27,96 | degC | -1,598 | **hayır** | 0…35 (rover) | #16 @ 0,80 h (73, 118) | rtamt |
| LP-R06 | `step_slope` | 5,63 | deg | 0,225 | evet | 25 (rover) | #4 @ 0,23 h (85, 119) | rtamt |
| LP-R07 | `cross_slope` | 4,19 | deg | 0,233 | evet | 18 (rover) | #25 @ 1,29 h (64, 118) | rtamt |
| LP-R08 | `dte_while_moving` | 184,62 | h | 7,692 | evet | 0 (fixed) | #4 @ 0,23 h (85, 119) | rtamt |
| LP-R09 | `safe_haven_leg` | — | h | — | **hayır** | 0 (fixed) | #0 @ 0,00 h (89, 123) | rtamt |
| LP-R10 | `goal_reached` | 0,00 | m | 0,000 | evet (sınır) | 0 (fixed) | #40 @ 2,16 h (51, 106) | rtamt |
| LP-R11 | `soc_at_goal` | 76,26 | pct | 3,813 | evet | 20 (rover) | #40 @ 2,16 h (51, 106) | builtin |

Karar **violated**; uygulanabilir 11, ihlal 3 (LP-R04, LP-R05, LP-R09); en küçük marj **LP-R05** ρ = -27,96 degC (ρ/ölçek -1,598).
Motor `rtamt` (rtamt 0.3.5), yerleşik motorla en büyük fark 0; iz: 41 örnek, 2,16 h.

## 2. SHERPA koşumlarında robustness dağılımı (`/api/stress-test`)

1000 koşum, tohum 0, B5'in varsayılan dağılımları. ρ aritmetikle: LP-R02 = `min_battery_pct − soc_min`, LP-R01 = `h_max_shadow_h − max_continuous_shadow_h` (koşum başına; p5/p50/p95 dağılımdan). LP-R10 = tamamlanma oranı.

| Rota | Plan ρ LP-R02 (pp) | SHERPA ρ LP-R02 p5 / p50 / p95 | Plan ρ LP-R01 (h) | SHERPA ρ LP-R01 p5 / p50 / p95 | Rezerv ihlali | Tamamlanma (LP-R10) | Süre (s) |
|---|---|---|---|---|---|---|---|
| VIPER haven->haven, 30 May 2027 | 12,1 | -20,0 / -20,0 / -4,9 | 91,5 | 89,2 / 90,7 / 92,4 | 98,6 % | 29,6 % (26,9–32,5) | 1,3 |
| LPR-1, 28 Sep 2026 | 76,2 | 32,3 / 58,0 / 72,5 | 49,8 | 48,4 / 49,7 / 49,8 | 0,0 % | 100,0 % (99,6–100,0) | 2,3 |

## 3. 2-B profiller (`/api/compare`): ikili karar vs marj

### Rover `nasa_viper` (0,8 s)

| Profil | Karar | En küçük marj | LP-R01 ρ (h) | `max_shadow_h` ikili | LP-R02 ρ (pp) | `min_soc` ikili | LP-R06 ρ (°) | LP-R07 ρ (°) | LP-R10 | LP-R11 ρ (pp) |
|---|---|---|---|---|---|---|---|---|---|---|
| `balanced` | violated | LP-R05 -46,04 degC | 91,67 | evet (sınır 40.0) | 47,15 | evet (sınır 0.2) | 2,58 | 0,66 | evet | 47,15 |
| `energy_saver` | violated | LP-R05 -46,04 degC | 91,67 | evet (sınır 30.0) | 47,15 | evet (sınır 0.35) | 2,58 | 0,66 | evet | 47,15 |
| `fast_recon` | violated | LP-R05 -46,04 degC | 91,67 | evet (sınır 50.0) | 47,15 | evet (sınır 0.1) | 2,58 | 0,66 | evet | 47,15 |
| `shadow_traverse` | violated | LP-R05 -46,04 degC | 91,67 | evet (sınır 45.0) | 46,93 | evet (sınır 0.25) | 2,58 | 0,66 | evet | 46,93 |

Sıralama (`comparison.safety_margin_ranking`, en güvenli önce): `balanced` (violated, LP-R05 ρ/ölçek -2,631), `energy_saver` (violated, LP-R05 ρ/ölçek -2,631), `fast_recon` (violated, LP-R05 ρ/ölçek -2,631), `shadow_traverse` (violated, LP-R05 ρ/ölçek -2,631). `largest_min_margin_profile`: `balanced`.

### Rover `lpr_1` (0,8 s)

| Profil | Karar | En küçük marj | LP-R01 ρ (h) | `max_shadow_h` ikili | LP-R02 ρ (pp) | `min_soc` ikili | LP-R06 ρ (°) | LP-R07 ρ (°) | LP-R10 | LP-R11 ρ (pp) |
|---|---|---|---|---|---|---|---|---|---|---|
| `balanced` | violated | LP-R05 -46,04 degC | 48,70 | evet (sınır 40.0) | 75,62 | evet (sınır 0.2) | 7,58 | 1,12 | evet | 75,62 |
| `energy_saver` | violated | LP-R05 -46,04 degC | 48,70 | evet (sınır 30.0) | 75,61 | evet (sınır 0.35) | 7,83 | 2,30 | evet | 75,61 |
| `fast_recon` | violated | LP-R05 -46,04 degC | 48,70 | evet (sınır 50.0) | 75,62 | evet (sınır 0.1) | 7,58 | 1,12 | evet | 75,62 |
| `shadow_traverse` | violated | LP-R05 -46,04 degC | 48,70 | evet (sınır 45.0) | 75,57 | evet (sınır 0.25) | 7,58 | 1,12 | evet | 75,57 |

Sıralama (`comparison.safety_margin_ranking`, en güvenli önce): `balanced` (violated, LP-R05 ρ/ölçek -2,631), `energy_saver` (violated, LP-R05 ρ/ölçek -2,631), `fast_recon` (violated, LP-R05 ρ/ölçek -2,631), `shadow_traverse` (violated, LP-R05 ρ/ölçek -2,631). `largest_min_margin_profile`: `balanced`.

## 4. `/api/safety-check` süresi

500 örnekli sentetik telemetri izi, 11 gereksinim:

| Motor | Süre (ms) | Karar | En küçük marj |
|---|---|---|---|
| `builtin` | 13 | satisfied | LP-R05 ρ = 5,00 degC |
| `rtamt` | 28 | satisfied | LP-R05 ρ = 5,00 degC |

Kaynak: NASA FRET (Giannakopoulou vd. 2020), RTAMT (Ničković & Yamaguchi 2020), Donzé & Maler 2010. Tasarım: `docs/superpowers/specs/2026-09-04-d3-formal-safety-design.md`.
