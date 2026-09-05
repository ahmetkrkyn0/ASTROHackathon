# CVaR risk iştahı (B2) — Site11 α taraması raporu

Üretildi: 2026-09-05T01:20:39Z (`scripts/risk_sweep_report.py`). Ölçü `cvar_normal_closed_form_v1`: normal dağılım için `CVaR_α = μ + σ·φ(z_α)/(1−α)`. α yalnızca **sıralama maliyetine** girer (eğim kriteri `min(slope_max, θ + σ_θ·m_α)`, enerji kriteri `CVaR_α(slip)`); süre, batarya, D3 marjları ve B5 Monte Carlo **ortalama** slip fiziğidir. `risk_alpha` verilmemişse (None) grid bugünkü v4 gridiyle bit-eşittir; **α = 0,5 ortalama değildir** (μ + 0,798σ). Monte Carlo 1000 koşum, tohum 0.

**İddia sınırı:** CVaR of MODEL-labelled distributions, not a measured risk: the slip sigma is Yutu-2's measured range read as +-2 sigma and a transferred relative spread of 0.5 elsewhere (assumptions, see each anchor's source); the slope sigma is derived from NASA's DEM clones (B3) where cached; the thermal field has no published sigma and is not tail-adjusted. Alpha changes the ranking cost only -- every hour, Wh and margin in this response is the mean-slip physics. Endo et al.'s success-rate figures are from their synthetic experiments, not from this site.

## 1. Kapalı form ve eğri

| α | z_α | m_α = φ(z_α)/(1−α) |
|---|---|---|
| 0,5 | 0,000 | **0,798** |
| 0,9 | 1,282 | **1,755** |
| 0,99 | 2,326 | **2,665** |
| 0,999 | 3,090 | **3,367** |

LPR-1/VIPER eğrisi (2 çapa) α'da; C3 σ yalnız ve C3 ⊕ B3 (medyan σ_θ = 1,54°, delta yöntemi); kap 0,9:

| θ (°) | μ | σ_C3 | s_0,5 | s_0,9 | s_0,99 | s_0,5 (⊕B3) | s_0,9 (⊕B3) | s_0,99 (⊕B3) |
|---|---|---|---|---|---|---|---|---|
| 0 | 0,037 | 0,019 | 0,052 | 0,070 | 0,087 | 0,054 | 0,074 | 0,093 |
| 5 | 0,083 | 0,041 | 0,115 | 0,155 | 0,193 | 0,119 | 0,163 | 0,205 |
| 10 | 0,182 | 0,091 | 0,254 | 0,341 | 0,424 | 0,262 | 0,359 | 0,451 |
| 15 | 0,400 | 0,200 | 0,560 | 0,751 | 0,900 | 0,577 | 0,790 | 0,900 |
| 20 | 0,881 | 0,440 | 0,900 | 0,900 | 0,900 | 0,900 | 0,900 | 0,900 |

## 2. Site11 ince gridi (500×500): kuyruklar ve maliyet sıralaması

### LPR-1 (Varsayilan) (`lpr_1`, eğim sınırı 25°; geçilebilir hücre 210 063)

- Eğim σ_θ (B3, 100 klon, `nasa_pgda_clones`): medyan **1,54°**, p95 1,99°.
- Slip μ medyanı 0,199; μ kapıda %5,2; enerji kriteri 1,0'da doymuş %14,6 (nominal).

| α | m_α | CVaR slip medyanı (C3 / ⊕B3) | slip kapıda | eğim kuyruğu sınırda | Spearman (maliyet ↔ nominal) | maliyet ort. / maks bağıl değişim | enerji doymuş |
|---|---|---|---|---|---|---|---|
| 0,50 | 0,798 | 0,279 / 0,288 | %10,8 | %0,9 | 0,9983 | +%8,4 / +%38,5 | %23,6 |
| 0,90 | 1,755 | 0,374 / 0,395 | %18,8 | %2,3 | 0,9929 | +%19,1 / +%74,7 | %32,9 |
| 0,99 | 2,665 | 0,465 / 0,497 | %26,6 | %4,1 | 0,9848 | +%29,9 / +%103,1 | %40,3 |

Termal kriter (`f_thermal`, iki uç): geçilebilir hücrelerin **%72,7**'inde ≥ 0,99, %89,8'inde ≥ 0,9 (medyan 0,9994; tepe medyanı -47,2 °C, soğuk uç medyanı -96,0 °C). Aralık/4'ü σ sayan soğuk kuyruk (α = 0,9) doygunluğu **%94,0**'e çıkarır (ortalama değişim +0,025): doygunluk ekler, ayrım eklemez → termal CVaR **uygulanmadı** (kanca, `risk.thermal_cvar_cold_c`).

### NASA VIPER (`nasa_viper`, eğim sınırı 20°; geçilebilir hücre 198 575)

- Eğim σ_θ (B3, 100 klon, `nasa_pgda_clones`): medyan **1,54°**, p95 1,99°.
- Slip μ medyanı 0,187; μ kapıda %0,0; enerji kriteri 1,0'da doymuş %17,0 (nominal).

| α | m_α | CVaR slip medyanı (C3 / ⊕B3) | slip kapıda | eğim kuyruğu sınırda | Spearman (maliyet ↔ nominal) | maliyet ort. / maks bağıl değişim | enerji doymuş |
|---|---|---|---|---|---|---|---|
| 0,50 | 0,798 | 0,262 / 0,271 | %5,6 | %2,8 | 0,9960 | +%7,1 / +%31,3 | %27,2 |
| 0,90 | 1,755 | 0,352 / 0,371 | %14,1 | %7,8 | 0,9854 | +%16,0 / +%63,3 | %37,0 |
| 0,99 | 2,665 | 0,437 / 0,466 | %22,4 | %14,5 | 0,9700 | +%24,5 / +%93,6 | %44,7 |

Termal kriter (`f_thermal`, iki uç): geçilebilir hücrelerin **%54,2**'inde ≥ 0,99, %73,5'inde ≥ 0,9 (medyan 0,9957; tepe medyanı -49,6 °C, soğuk uç medyanı -97,7 °C). Aralık/4'ü σ sayan soğuk kuyruk (α = 0,9) doygunluğu **%81,2**'e çıkarır (ortalama değişim +0,070): doygunluk ekler, ayrım eklemez → termal CVaR **uygulanmadı** (kanca, `risk.thermal_cvar_cold_c`).

## 3. `/api/risk-sweep` — 2-B ince grid, standart çiftler

Her satır kendi rotasının **ortalama-slip fiziği**dir (α süreyi değiştirmez); örtüşme = nominal rotayla hücre Jaccard'ı.

### LPR-1, (358,494)→(206,426) (`lpr_1`)

Eğim σ kaynağı: `dem_clones`; dört plan 0,9 s.

| α | nokta | mesafe (km) | süre (h) | tüketim (Wh) | min SOC | ort. / maks slip (μ) | ort. CVaR slip | risk-ayarlı sürüş saati | maks eğim kuyruğu (°) | örtüşme | plan (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 156 | 0,910 | 1,623 | 597,2 | 94,31 | 0,175 / 0,586 | — | — | — | 1,00 | 120 |
| 0,50 | 156 | 0,910 | 1,621 | 595,8 | 94,32 | 0,175 / 0,563 | 0,253 | 1,926 | 18,5 | 0,81 | 227 |
| 0,90 | 156 | 0,910 | 1,622 | 596,4 | 94,32 | 0,175 / 0,563 | 0,343 | 2,815 | 20,0 | 0,79 | 226 |
| 0,99 | 156 | 0,910 | 1,617 | 592,7 | 94,38 | 0,173 / 0,563 | 0,406 | 3,696 | 21,5 | 0,49 | 248 |

Risk matrisi — her rota (satır) her α'da (sütun) yeniden fiyatlandı, risk-ayarlı sürüş saati:

| rota α \ değerlendirme α | 0,50 | 0,90 | 0,99 |
|---|---|---|---|
| None | 1,899 | 2,583 | 3,375 |
| 0,50 | 1,926 | 2,792 | 3,706 |
| 0,90 | 1,929 | 2,815 | 3,711 |
| 0,99 | 1,922 | 2,804 | 3,696 |

Nominale göre Δ: α = 0,50: mesafe +0,000 km, süre -0,003 h, tüketim -1,4 Wh, min SOC +0,01 pt, ort. slip -0,0001, maks slip -0,0229; α = 0,90: mesafe +0,000 km, süre -0,002 h, tüketim -0,8 Wh, min SOC +0,01 pt, ort. slip +0,0002, maks slip -0,0229; α = 0,99: mesafe +0,000 km, süre -0,006 h, tüketim -4,5 Wh, min SOC +0,07 pt, ort. slip -0,0020, maks slip -0,0229. α = 0,99'da en düşük risk-ayarlı sürüş saatini taşıyan rota: **nominal** (α rotaları kuyrukta daha pahalı) (3,375 h).

### LPR-1, Ay gecesi çifti (186,34)→(494,450) (`lpr_1`)

Eğim σ kaynağı: `dem_clones`; dört plan 3,4 s.

| α | nokta | mesafe (km) | süre (h) | tüketim (Wh) | min SOC | ort. / maks slip (μ) | ort. CVaR slip | risk-ayarlı sürüş saati | maks eğim kuyruğu (°) | örtüşme | plan (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 420 | 2,727 | 4,366 | 1465,7 | 87,10 | 0,115 / 0,395 | — | — | — | 1,00 | 707 |
| 0,50 | 422 | 2,732 | 4,353 | 1453,5 | 87,27 | 0,112 / 0,395 | 0,161 | 4,637 | 16,2 | 0,79 | 847 |
| 0,90 | 423 | 2,736 | 4,349 | 1448,4 | 87,36 | 0,110 / 0,395 | 0,218 | 5,052 | 17,8 | 0,57 | 820 |
| 0,99 | 426 | 2,744 | 4,344 | 1439,5 | 87,49 | 0,108 / 0,395 | 0,267 | 5,528 | 19,3 | 0,52 | 878 |

Risk matrisi — her rota (satır) her α'da (sütun) yeniden fiyatlandı, risk-ayarlı sürüş saati:

| rota α \ değerlendirme α | 0,50 | 0,90 | 0,99 |
|---|---|---|---|
| None | 4,633 | 5,029 | 5,563 |
| 0,50 | 4,637 | 5,065 | 5,629 |
| 0,90 | 4,629 | 5,052 | 5,616 |
| 0,99 | 4,612 | 5,010 | 5,528 |

Nominale göre Δ: α = 0,50: mesafe +0,006 km, süre -0,014 h, tüketim -12,2 Wh, min SOC +0,17 pt, ort. slip -0,0033, maks slip +0,0000; α = 0,90: mesafe +0,009 km, süre -0,017 h, tüketim -17,3 Wh, min SOC +0,26 pt, ort. slip -0,0046, maks slip +0,0000; α = 0,99: mesafe +0,018 km, süre -0,022 h, tüketim -26,2 Wh, min SOC +0,39 pt, ort. slip -0,0075, maks slip +0,0000. α = 0,99'da en düşük risk-ayarlı sürüş saatini taşıyan rota: α = 0,99 (5,528 h).

### VIPER, (358,494)→(206,426) (`nasa_viper`)

Eğim σ kaynağı: `dem_clones`; dört plan 0,9 s.

| α | nokta | mesafe (km) | süre (h) | tüketim (Wh) | min SOC | ort. / maks slip (μ) | ort. CVaR slip | risk-ayarlı sürüş saati | maks eğim kuyruğu (°) | örtüşme | plan (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 0,174 / 0,586 | — | — | — | 1,00 | 107 |
| 0,50 | 156 | 0,910 | 5,400 | 2739,3 | 57,70 | 0,174 / 0,586 | 0,252 | 6,469 | 18,6 | 0,87 | 221 |
| 0,90 | 156 | 0,910 | 5,392 | 2729,6 | 57,94 | 0,173 / 0,586 | 0,339 | 9,130 | 20,0 | 0,66 | 220 |
| 0,99 | 156 | 0,910 | 5,377 | 2713,0 | 58,22 | 0,170 / 0,586 | 0,402 | 12,197 | 20,0 | 0,48 | 213 |

Risk matrisi — her rota (satır) her α'da (sütun) yeniden fiyatlandı, risk-ayarlı sürüş saati:

| rota α \ değerlendirme α | 0,50 | 0,90 | 0,99 |
|---|---|---|---|
| None | 6,294 | 8,487 | 11,451 |
| 0,50 | 6,469 | 9,149 | 12,269 |
| 0,90 | 6,456 | 9,130 | 12,241 |
| 0,99 | 6,435 | 9,097 | 12,197 |

Nominale göre Δ: α = 0,50: mesafe +0,000 km, süre -0,003 h, tüketim -2,6 Wh, min SOC +0,06 pt, ort. slip -0,0004, maks slip +0,0000; α = 0,90: mesafe +0,000 km, süre -0,011 h, tüketim -12,3 Wh, min SOC +0,30 pt, ort. slip -0,0016, maks slip +0,0000; α = 0,99: mesafe +0,000 km, süre -0,026 h, tüketim -28,9 Wh, min SOC +0,58 pt, ort. slip -0,0039, maks slip +0,0000. α = 0,99'da en düşük risk-ayarlı sürüş saatini taşıyan rota: **nominal** (α rotaları kuyrukta daha pahalı) (11,451 h).

### VIPER kısa leg (358,494)→(346,462) (`nasa_viper`)

Eğim σ kaynağı: `dem_clones`; dört plan 0,7 s.

| α | nokta | mesafe (km) | süre (h) | tüketim (Wh) | min SOC | ort. / maks slip (μ) | ort. CVaR slip | risk-ayarlı sürüş saati | maks eğim kuyruğu (°) | örtüşme | plan (ms) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 33 | 0,185 | 1,551 | 920,3 | 84,62 | 0,392 / 0,594 | — | — | — | 1,00 | 56 |
| 0,50 | 33 | 0,185 | 1,551 | 920,4 | 84,62 | 0,392 / 0,594 | 0,570 | 2,468 | 18,7 | 0,94 | 168 |
| 0,90 | 33 | 0,185 | 1,540 | 914,2 | 84,59 | 0,393 / 0,627 | 0,755 | 4,738 | 20,0 | 0,03 | 165 |
| 0,99 | 33 | 0,185 | 1,540 | 914,2 | 84,59 | 0,393 / 0,627 | 0,874 | 7,737 | 20,0 | 0,03 | 167 |

Risk matrisi — her rota (satır) her α'da (sütun) yeniden fiyatlandı, risk-ayarlı sürüş saati:

| rota α \ değerlendirme α | 0,50 | 0,90 | 0,99 |
|---|---|---|---|
| None | 2,307 | 4,362 | 6,274 |
| 0,50 | 2,468 | 4,803 | 7,533 |
| 0,90 | 2,403 | 4,738 | 7,737 |
| 0,99 | 2,403 | 4,738 | 7,737 |

Nominale göre Δ: α = 0,50: mesafe +0,000 km, süre +0,000 h, tüketim +0,1 Wh, min SOC +0,00 pt, ort. slip +0,0001, maks slip +0,0000; α = 0,90: mesafe +0,000 km, süre -0,011 h, tüketim -6,1 Wh, min SOC -0,03 pt, ort. slip +0,0010, maks slip +0,0327; α = 0,99: mesafe +0,000 km, süre -0,011 h, tüketim -6,1 Wh, min SOC -0,03 pt, ort. slip +0,0010, maks slip +0,0327. α = 0,99'da en düşük risk-ayarlı sürüş saatini taşıyan rota: **nominal** (α rotaları kuyrukta daha pahalı) (6,274 h).

## 4. `/api/plan-4d` + B5 stres testi (SHERPA) — standart rotalar, coarsen 4

### LPR-1, 28 Eyl 2026, (358,494)→(206,426) (`lpr_1`)

| α | dilim × saat | hamle / bekleme | varış (h) | min SOC | ort. / maks slip (μ) | ort. / maks CVaR slip | maks eğim kuyruğu (°) | sürüş h → risk-ayarlı | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | B5 nominal min SOC | düğüm | plan (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 120 × 0,0359 | 41 / 0 | 2,979 | 92,5 | 0,326 / 0,537 | — / — | — | — → — | 1,00 | %100,0 / %99,8 / %0,0 | 94,5 | 23 177 | 12,0 |
| 0,50 | 120 × 0,0359 | 42 / 0 | 2,979 | 93,1 | 0,313 / 0,537 | 0,462 / 0,798 | 19,0 | 2,18 → 3,19 | 0,55 | %100,0 / %99,8 / %0,0 | 95,0 | 24 171 | 7,0 |
| 0,90 | 120 × 0,0359 | 42 / 0 | 2,979 | 93,1 | 0,313 / 0,537 | 0,614 / 0,900 | 22,0 | 2,18 → 6,31 | 0,55 | %100,0 / %99,8 / %0,0 | 95,0 | 24 279 | 6,2 |
| 0,99 | 120 × 0,0359 | 42 / 0 | 2,979 | 93,1 | 0,313 / 0,537 | 0,705 / 0,900 | 24,8 | 2,18 → 8,19 | 0,55 | %100,0 / %99,8 / %0,0 | 95,0 | 23 318 | 6,5 |

### LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) (`lpr_1`)

| α | dilim × saat | hamle / bekleme | varış (h) | min SOC | ort. / maks slip (μ) | ort. / maks CVaR slip | maks eğim kuyruğu (°) | sürüş h → risk-ayarlı | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | B5 nominal min SOC | düğüm | plan (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 270 × 0,0359 | 116 / 0 | 6,749 | 67,4 | 0,149 / 0,343 | — / — | — | — → — | 1,00 | %98,8 / %88,8 / %0,0 | 65,1 | 146 705 | 20,2 |
| 0,50 | 270 × 0,0359 | 116 / 0 | 6,749 | 67,4 | 0,149 / 0,343 | 0,218 / 0,508 | 15,7 | 4,80 → 5,27 | 0,84 | %98,8 / %88,8 / %0,0 | 65,1 | 156 377 | 17,3 |
| 0,90 | 270 × 0,0359 | 116 / 0 | 6,749 | 67,4 | 0,149 / 0,343 | 0,300 / 0,706 | 17,8 | 4,80 → 6,06 | 0,80 | %98,8 / %88,8 / %0,0 | 65,1 | 171 641 | 18,6 |
| 0,99 | 270 × 0,0359 | 116 / 0 | 6,749 | 67,4 | 0,149 / 0,343 | 0,379 / 0,894 | 19,7 | 4,80 → 7,37 | 0,80 | %98,8 / %88,8 / %0,0 | 65,1 | 190 931 | 21,3 |

### VIPER kısa leg, 30 May 2027, (358,494)→(346,462), haven kuralı (`nasa_viper`)

| α | dilim × saat | hamle / bekleme | varış (h) | min SOC | ort. / maks slip (μ) | ort. / maks CVaR slip | maks eğim kuyruğu (°) | sürüş h → risk-ayarlı | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | B5 nominal min SOC | düğüm | plan (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| None | 43 × 0,1176 | 8 / 0 | 2,235 | 72,3 | 0,465 / 0,532 | — / — | — | — → — | 1,00 | %99,6 / %95,0 / %95,0 | 71,0 | 1 491 | 6,9 |
| 0,50 | 43 × 0,1176 | 8 / 0 | 2,235 | 72,3 | 0,465 / 0,532 | 0,693 / 0,798 | 19,0 | 1,76 → 3,34 | 1,00 | %99,6 / %95,0 / %95,0 | 71,0 | 1 467 | 3,2 |
| 0,90 | 43 × 0,1176 | 8 / 0 | 2,235 | 72,3 | 0,465 / 0,532 | 0,856 / 0,900 | 20,0 | 1,76 → 7,63 | 1,00 | %99,6 / %95,0 / %95,0 | 71,0 | 1 346 | 3,0 |
| 0,99 | 43 × 0,1176 | 8 / 0 | 2,235 | 72,3 | 0,465 / 0,532 | 0,900 / 0,900 | 20,0 | 1,76 → 9,25 | 1,00 | %99,6 / %95,0 / %95,0 | 71,0 | 1 211 | 3,1 |

## 5. Okuma

- **Grid:** α = 0,99'da CVaR slip medyanı 0,199 → 0,497, hücrelerin %26,6'i 0,9 kapısında, eğim kuyruğu hücrelerin %4,1'inde sınıra dayanıyor; maliyet sıralaması nominale Spearman 0,985 (ortalama +%29,9). Enerji kriteri α = 0,99'da hücrelerin %40,3'inde doyuyor (nominal %14,6) — C3'ün slip'siz ölçek kararının bedeli.
- **2-B, LPR-1, (358,494)→(206,426):** α = 0,99 rotası nominalle %49 örtüşüyor; tüketim -4,5 Wh, süre -0,006 h, mesafe +0,000 km, min SOC +0,07 pt, ort. slip -0,0020, maks slip -0,0229. α = 0,99'da en düşük risk-ayarlı sürüş saatini **nominal rota** taşıyor: ağırlıklı kriterler kuyruk süresini minimize etmez.
- **2-B, LPR-1, Ay gecesi çifti (186,34)→(494,450):** α = 0,99 rotası nominalle %52 örtüşüyor; tüketim -26,2 Wh, süre -0,022 h, mesafe +0,018 km, min SOC +0,39 pt, ort. slip -0,0075, maks slip +0,0000. α = 0,99'da en düşük risk-ayarlı sürüş saatini α = 0,99 rotası taşıyor.
- **2-B, VIPER, (358,494)→(206,426):** α = 0,99 rotası nominalle %48 örtüşüyor; tüketim -28,9 Wh, süre -0,026 h, mesafe +0,000 km, min SOC +0,58 pt, ort. slip -0,0039, maks slip +0,0000. α = 0,99'da en düşük risk-ayarlı sürüş saatini **nominal rota** taşıyor: ağırlıklı kriterler kuyruk süresini minimize etmez.
- **2-B, VIPER kısa leg (358,494)→(346,462):** α = 0,99 rotası nominalle %3 örtüşüyor; tüketim -6,1 Wh, süre -0,011 h, mesafe +0,000 km, min SOC -0,03 pt, ort. slip +0,0010, maks slip +0,0327. α = 0,99'da en düşük risk-ayarlı sürüş saatini **nominal rota** taşıyor: ağırlıklı kriterler kuyruk süresini minimize etmez.
- **4-B, LPR-1, 28 Eyl 2026, (358,494)→(206,426):** nominal 41 hamle / 2,98 h / min SOC 92,5; α = 0,99: 42 hamle / 2,98 h / 93,1 (örtüşme 0,55); B5 tamamlanma %100,0 → %100,0, rezerv içinde %99,8 → %99,8, tam başarı %0,0 → %0,0; risk-ayarlı sürüş saati (α = 0,99) 8,19 vs nominal sürüş 2,18.
- **4-B, LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450):** nominal 116 hamle / 6,75 h / min SOC 67,4; α = 0,99: 116 hamle / 6,75 h / 67,4 (örtüşme 0,80); B5 tamamlanma %98,8 → %98,8, rezerv içinde %88,8 → %88,8, tam başarı %0,0 → %0,0; risk-ayarlı sürüş saati (α = 0,99) 7,37 vs nominal sürüş 4,80.
- **4-B, VIPER kısa leg, 30 May 2027, (358,494)→(346,462), haven kuralı:** nominal 8 hamle / 2,23 h / min SOC 72,3; α = 0,99: 8 hamle / 2,23 h / 72,3 (örtüşme 1,00); B5 tamamlanma %99,6 → %99,6, rezerv içinde %95,0 → %95,0, tam başarı %95,0 → %95,0; risk-ayarlı sürüş saati (α = 0,99) 9,25 vs nominal sürüş 1,76.
- **Sunum cümlesi (ölçülene göre doldurulur):** "Risk iştahı α'yı JPL'in STEP ve Keio'nun CVaR yaklaşımıyla maliyete bağladık; α arttıkça planlayıcı slip ve eğim kuyruğu geniş hücrelerden kaçıyor. Site11'de etkisi yukarıdaki tablolardaki kadardır — nominal fizikte kazanç küçük, rota değişimi belirgin; MODEL etiketli dağılımların dönüşümüdür, ölçülmüş risk değildir."

**Kaynaklar:** STEP — Fan, Otsu, Kitahara, Zhang, Agha-mohammadi, RSS 2021 (arXiv 2103.02828; genişletilmiş 2303.01614); Endo, Taniai, Ishigami, ICRA 2023 (arXiv 2303.01169) — *"%11 → %95 başarı, maksimum slip %92,9 → %63,7"* onların **sentetik** deneylerinin sayılarıdır, bu raporun değil; Rockafellar & Uryasev 2000 (kapalı form). Slip σ: C3 çapaları (varsayım); eğim σ: NASA PGDA Site11 DEM klonları (B3, DERIVED); termal σ: kaynak yok.
