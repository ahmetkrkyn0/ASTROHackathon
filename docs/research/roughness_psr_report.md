# Ölçülmüş pürüzlülük (LOLA LDRM) ve PSR maskesi (C4) — Site11 raporu

Üretildi: 2026-09-05T02:39:28Z (`scripts/roughness_psr_report.py`). Beşinci maliyet kriteri `f_roughness` NASA'nın **ölçülmüş** LDRM pürüzlülüğünü (LDRM_80S_50MPP_ADJ_ROUGH_100M, 50 m/px, 100 m taban) okur; katman `MEASURED`, [0, 1] ölçeği bölgesel ECDF sırası (`MODEL`). PSR maskesi (`LPSR_80S_20MPP_ADJ`, 20 m/px) planlamaya girmez; bizim `shadow_ratio`'muza karşı doğrulama olarak ölçülür. "Önce" = `w_roughness = 0` (aynı kod; katman katkısı sıfır → grid v4 ile bit-eşit, SHA kilidi testte). Monte Carlo 1000 koşum, tohum 0.

**İddia sınırı (pürüzlülük):** LOLA LDRM roughness, MEASURED from LOLA spot residuals around a plane fit (NASA GSFC PGDA product 90, Barker et al. 2023), posted at 50 m/px with a 100 m baseline. Every 5 m cell carries the statistic of the 50 m pixel that contains it: a hectometre-scale block statistic, NOT the roughness of the cell itself, and not a rock count (Diviner rock abundance stops at 80 S and is not used). The [0, 1] criterion is the cell's percentile rank among the 80-90 S region's 50 m pixels -- a statistical scale (MODEL), not a rover tolerance; no roughness sigma is published, so the criterion has no risk tail.

**İddia sınırı (PSR):** PGDA LPSR_80S_20MPP_ADJ: NASA's MEASURED permanently-shadowed-region map at 20 m/px, nearest-neighbour on the 5 m grid (each 5 m cell carries the value of the 20 m pixel that contains it). It is NOT a planning input -- VIPER's science targets are inside PSRs and the thermal gate already blocks them -- but a layer, a cell-card field and a check of our own shadow_ratio: the overlap numbers are measured on this window and reported as they come out.

## 1. Ürünler, pencere, ko-registrasyon

| | Pürüzlülük | PSR |
|---|---|---|
| Ürün | `LDRM_80S_50MPP_ADJ_ROUGH_100M` | `LPSR_80S_20MPP_ADJ` |
| Çözünürlük / taban | 50 m/px / 100 m | 20 m/px |
| Pencere (ürün pikseli) | 54×54 (pay 2 px) | 135×135 (pay 5 px) |
| 5 m hücre / ürün pikseli | 100 | 16 |
| İndirme (UTC) | 2026-09-05T02:31:00Z | 2026-09-05T02:31:03Z |
| Yeniden örnekleme | nearest | nearest |
| Projeksiyon | `Moon (2015) - Sphere / Ocentric / South Polar` ≡ grid `unnamed` (parametreler eşit) | aynı |

Tanım (ürün sayfası): *LOLA Digital Roughness Map (LDRM, in meters). This is the spread of height residuals of individual LOLA spots around a plane fit to the LDEM within a circular window whose diameter is equal to a baseline of *M meters.*

**Kayıt sağlaması:** LDRM `SLP_100M` (fit düzleminin eğimi) ↔ bizim 5 m eğimin 50 m blok ortalaması: Spearman **0,989** (2 500 blok; medyanlar bizim 10,4° / NASA 10,1°; eşik 0,9). Hedef transform `metadata.json` origin'ini hücre (0, 0)'ın sol-üst köşesi sayar (Site11 TIF transformuyla doğrulandı).

## 2. Pürüzlülük dağılımı

Pencere (50 m ham pikseller), taban başına:

| Taban (m) | medyan (m) | p95 | maks |
|---|---|---|---|
| 100 | 0,817 | 1,769 | 4,87 |
| 200 | 1,690 | 4,145 | 10,76 |
| 400 | 3,303 | 12,814 | 22,35 |
| 800 | 7,803 | 31,161 | 44,32 |
| 1600 | 23,604 | 33,799 | 43,51 |

Hurst üssü: p5 0,52 / medyan 0,92 / p95 1,29; LDRM 100 m eğimi medyanı 10,6°.

Site11 5 m gridi (100 m taban) ↔ 80–90°S bölgesi (ölçeğin örneği):

| Kantil | Site11 (m) | Bölge (m) |
|---|---|---|
| p5 | 0,402 | 0,267 |
| p25 | 0,601 | 0,416 |
| p50 | 0,827 | 0,572 |
| p75 | 1,138 | 0,794 |
| p95 | 1,775 | 1,359 |
| p99 | 2,496 | 2,177 |

Site11 maks 4,87 m; NaN hücre 0; benzersiz blok 2 500. Bölgesel örnek: 36 tile, 9 437 184 sonlu piksel, 201 kantil düğümü.

**H-4 kontrolü — Spearman(pürüzlülük, eğim):** 5 m hücrelerde **0,213**; 50 m blokta blok-ort. eğimle 0,227, blok-maks ile 0,321. Kriter eğimin yeniden ifadesi değil (H-4'te enerji–eğim 1,000 idi).

Eğim kutuları (PSJ 2025: >10° eğimde 50–200 m tabanda pürüzlülük artıyor):

| Eğim (°) | n | medyan pürüzlülük (m) | p90 |
|---|---|---|---|
| 0–5 | 40 226 | 0,723 | 1,315 |
| 5–10 | 76 914 | 0,760 | 1,407 |
| 10–15 | 68 959 | 0,813 | 1,490 |
| 15–20 | 40 918 | 0,907 | 1,585 |
| 20–… | 22 983 | 1,078 | 1,887 |

`f_roughness` (bölgesel ECDF sırası) Site11'de: p5 0,227 / p25 0,541 / p50 0,775 / p75 0,911 / p95 0,980; ≥ 0,99 olan hücre %2,3, ≤ 0,01 olan %0,2.

### LPR-1 (Varsayilan) (`lpr_1`; geçilebilir hücre 210 063)

Spearman(`f_roughness`, `f_slope`) geçilebilir hücrelerde 0,183.

| w_roughness | Spearman (maliyet ↔ w=0) | maliyet ort. / maks bağıl değişim | kriterin hücre maliyetindeki payı (ort. / p95) |
|---|---|---|---|
| 0,00 | 1,0000 | +%0,0 / +%0,0 | %0,0 / %0,0 |
| 0,05 | 0,9936 | +%8,2 / +%24,5 | %7,4 / %12,8 |
| 0,10 | 0,9783 | +%16,3 / +%49,0 | %13,7 / %22,7 |
| 0,15 | 0,9587 | +%24,5 / +%73,6 | %19,0 / %30,6 |
| 0,20 | 0,9372 | +%32,7 / +%98,1 | %23,7 / %37,0 |
| 0,30 | 0,8924 | +%49,0 / +%147,1 | %31,3 / %46,8 |

### NASA VIPER (`nasa_viper`; geçilebilir hücre 198 575)

Spearman(`f_roughness`, `f_slope`) geçilebilir hücrelerde 0,143.

| w_roughness | Spearman (maliyet ↔ w=0) | maliyet ort. / maks bağıl değişim | kriterin hücre maliyetindeki payı (ort. / p95) |
|---|---|---|---|
| 0,00 | 1,0000 | +%0,0 / +%0,0 | %0,0 / %0,0 |
| 0,05 | 0,9919 | +%7,5 / +%22,9 | %6,9 / %11,2 |
| 0,10 | 0,9717 | +%15,1 / +%45,8 | %12,8 / %20,2 |
| 0,15 | 0,9449 | +%22,6 / +%68,7 | %18,0 / %27,5 |
| 0,20 | 0,9149 | +%30,2 / +%91,6 | %22,4 / %33,6 |
| 0,30 | 0,8528 | +%45,2 / +%137,4 | %29,9 / %43,1 |

## 3. PSR maskesi ↔ bizim gölge modelimiz

PSR hücresi 14 016 (gridin %5,6; ürün pikseli 876). Karanlık = `shadow_ratio ≥ eşik`.

| Eşik | karanlık hücre | Jaccard | PSR'ın yakalanan payı | karanlıkların PSR'da payı | yanlış pozitif |
|---|---|---|---|---|---|
| 0,900 | 20 212 | **0,685** | 0,993 | 0,688 | %31,2 |
| 0,950 | 18 000 | **0,765** | 0,990 | 0,771 | %22,9 |
| 0,980 | 16 835 | **0,810** | 0,985 | 0,820 | %18,0 |
| 0,990 | 16 363 | **0,830** | 0,983 | 0,842 | %15,8 |
| 1,000 | 16 253 | **0,833** | 0,982 | 0,846 | %15,4 |

20 m ürün bloklarında (4×4 blok-ort. gölge): eşik 0,98 → Jaccard **0,890**; eşik 0,99 → Jaccard **0,912**; eşik 1,00 → Jaccard **0,907**.

PSR içinde ort. `shadow_ratio` 0,9981 (p1 0,953, medyan 1,000), dışında 0,629. `thermal_min` medyanı PSR içinde -183,15 °C (90 K PSR tabanı), dışında -98,6 °C; `thermal_min ≤ −180 °C` olan 16 406 hücrenin 13 761'i PSR'da; `shadow_ratio = 1` olan 16 253 hücrenin 13 758'i.

Geçilebilir hücre PSR içinde: LPR-1 (Varsayilan) **83**, NASA VIPER **78** — termal kapı PSR'ı zaten kapatıyor; maske bu yüzden planlamaya sokulmadı.

## 4. Standart 2-B çiftler (`/api/plan`), `w_roughness` taraması

Her satır kendi rotasının simülasyonudur; örtüşme = w = 0 rotasıyla hücre Jaccard'ı; pay = rota hücrelerinde `w·f / maliyet` ortalaması.

### LPR-1 gündüz — `lpr_1`, (358,494)→(206,426)

| w | nokta | km | saat | Wh | min SOC | rota pürüzlülük ort. / maks (m) | ort. f | PSR hücresi | örtüşme | pay | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 156 | 0,910 | 1,623 | 597,2 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %0,0 | 1,61 |
| 0,05 | 156 | 0,910 | 1,623 | 597,2 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %10,8 | 0,30 |
| 0,10 | 156 | 0,910 | 1,623 | 597,2 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %19,4 | 0,26 |
| 0,15 | 156 | 0,910 | 1,623 | 596,9 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 0,97 | %26,4 | 0,17 |
| 0,20 | 156 | 0,910 | 1,623 | 596,9 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 0,97 | %32,2 | 0,27 |
| 0,30 | 156 | 0,910 | 1,623 | 596,9 | 94,31 | 1,04 / 1,96 | 0,83 | 0 | 0,97 | %41,5 | 0,27 |

### LPR-1 Ay gecesi çifti — `lpr_1`, (186,34)→(494,450)

| w | nokta | km | saat | Wh | min SOC | rota pürüzlülük ort. / maks (m) | ort. f | PSR hücresi | örtüşme | pay | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 420 | 2,727 | 4,366 | 1465,7 | 87,10 | 0,75 / 1,76 | 0,60 | 0 | 1,00 | %0,0 | 0,84 |
| 0,05 | 420 | 2,727 | 4,404 | 1501,3 | 86,19 | 0,69 / 1,76 | 0,55 | 0 | 0,20 | %7,8 | 0,92 |
| 0,10 | 420 | 2,727 | 4,430 | 1520,8 | 85,88 | 0,67 / 1,76 | 0,52 | 0 | 0,05 | %13,5 | 0,87 |
| 0,15 | 420 | 2,727 | 4,429 | 1519,4 | 85,91 | 0,66 / 1,76 | 0,51 | 0 | 0,05 | %18,4 | 0,79 |
| 0,20 | 420 | 2,727 | 4,429 | 1519,9 | 85,87 | 0,65 / 1,76 | 0,51 | 0 | 0,04 | %22,7 | 0,90 |
| 0,30 | 420 | 2,727 | 4,427 | 1519,2 | 85,85 | 0,65 / 1,76 | 0,50 | 0 | 0,08 | %30,0 | 1,02 |

### VIPER standart — `nasa_viper`, (358,494)→(206,426)

| w | nokta | km | saat | Wh | min SOC | rota pürüzlülük ort. / maks (m) | ort. f | PSR hücresi | örtüşme | pay | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %0,0 | 1,32 |
| 0,05 | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %9,6 | 0,26 |
| 0,10 | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %17,4 | 0,35 |
| 0,15 | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %24,0 | 0,29 |
| 0,20 | 156 | 0,910 | 5,403 | 2741,8 | 57,64 | 1,04 / 1,96 | 0,83 | 0 | 1,00 | %29,6 | 0,27 |
| 0,30 | 156 | 0,910 | 5,411 | 2747,8 | 57,55 | 1,03 / 1,96 | 0,83 | 0 | 0,87 | %38,5 | 0,26 |

### VIPER kısa leg — `nasa_viper`, (358,494)→(346,462)

| w | nokta | km | saat | Wh | min SOC | rota pürüzlülük ort. / maks (m) | ort. f | PSR hücresi | örtüşme | pay | s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 33 | 0,185 | 1,551 | 920,3 | 84,62 | 0,68 / 1,18 | 0,57 | 0 | 1,00 | %0,0 | 0,20 |
| 0,05 | 33 | 0,185 | 1,551 | 920,3 | 84,62 | 0,68 / 1,18 | 0,57 | 0 | 1,00 | %4,8 | 0,24 |
| 0,10 | 33 | 0,185 | 1,551 | 920,3 | 84,62 | 0,68 / 1,18 | 0,57 | 0 | 1,00 | %9,2 | 0,28 |
| 0,15 | 33 | 0,185 | 1,551 | 920,3 | 84,62 | 0,68 / 1,18 | 0,57 | 0 | 1,00 | %13,1 | 0,19 |
| 0,20 | 33 | 0,185 | 1,551 | 920,8 | 84,61 | 0,66 / 1,18 | 0,56 | 0 | 0,83 | %16,3 | 0,20 |
| 0,30 | 33 | 0,185 | 1,551 | 920,8 | 84,61 | 0,66 / 1,18 | 0,56 | 0 | 0,83 | %22,5 | 0,21 |

## 5. Standart 4-B rotalar (`/api/plan-4d`, coarsen 4) + SHERPA

w ∈ {0, 0,15}; pürüzlülük küpe blok-maks ile girer. Monte Carlo 1000 koşum.

### LPR-1 28 Eyl 2026 — `lpr_1`, (358,494)→(206,426)

| w | hamle / bekleme | varış (h) | min SOC | ort. slip | rota pürüzlülük ort. / maks (m) | ort. f | PSR bloğu | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | plan s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 41 / 0 | 2,979 | %92,5 | 0,326 | 1,10 / 2,31 | 0,84 | 0 | 1,00 | %100,0 / %99,8 / %0,0 | 9,3 |
| 0,15 | 41 / 0 | 2,979 | %92,5 | 0,326 | 1,10 / 2,31 | 0,84 | 0 | 1,00 | %100,0 / %99,8 / %0,0 | 6,1 |

### LPR-1 Ay gecesi 13 Eyl 2026 — `lpr_1`, (186,34)→(494,450)

| w | hamle / bekleme | varış (h) | min SOC | ort. slip | rota pürüzlülük ort. / maks (m) | ort. f | PSR bloğu | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | plan s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 116 / 0 | 6,749 | %67,4 | 0,149 | 0,72 / 1,76 | 0,59 | 0 | 1,00 | %98,8 / %88,8 / %0,0 | 19,8 |
| 0,15 | 116 / 0 | 6,749 | %67,4 | 0,149 | 0,71 / 1,76 | 0,58 | 0 | 0,89 | %98,8 / %88,8 / %0,0 | 18,7 |

### VIPER kısa leg 30 May 2027 (haven kuralı) — `nasa_viper`, (358,494)→(346,462)

| w | hamle / bekleme | varış (h) | min SOC | ort. slip | rota pürüzlülük ort. / maks (m) | ort. f | PSR bloğu | örtüşme | B5 tamamlanma / rezerv içinde / tam başarı | plan s |
|---|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 8 / 0 | 2,235 | %72,3 | 0,465 | 1,00 / 1,18 | 0,83 | 0 | 1,00 | %99,6 / %95,0 / %95,0 | 6,3 |
| 0,15 | 8 / 0 | 2,235 | %72,3 | 0,465 | 1,00 / 1,18 | 0,83 | 0 | 1,00 | %99,6 / %95,0 / %95,0 | 2,9 |

## 6. Okuma

- **Kriter atıl değil, eğimin kopyası da değil:** Spearman(pürüzlülük, eğim) 0,21; `f_roughness` Site11'de p5 0,23 – p95 0,98 arasına yayılıyor (Site11 bölgesel medyanın üstünde: medyan sıra 0,77). Eğim kutularında medyan pürüzlülük 0,72 → 1,08 m (PSJ 2025'in yönü, zayıf).
- **LPR-1 gündüz:** w = 0,15'te örtüşme 0,97, rota ort. pürüzlülük 1,04 → 1,04 m, 597,2 → 596,9 Wh, 1,623 → 1,623 h, min SOC 94,31 → 94,31; kriterin hücre maliyetindeki payı %26,4.
- **LPR-1 Ay gecesi çifti:** w = 0,15'te örtüşme 0,05, rota ort. pürüzlülük 0,75 → 0,66 m, 1465,7 → 1519,4 Wh, 4,366 → 4,429 h, min SOC 87,10 → 85,91; kriterin hücre maliyetindeki payı %18,4.
- **VIPER standart:** w = 0,15'te örtüşme 1,00, rota ort. pürüzlülük 1,04 → 1,04 m, 2741,8 → 2741,8 Wh, 5,403 → 5,403 h, min SOC 57,64 → 57,64; kriterin hücre maliyetindeki payı %24,0.
- **VIPER kısa leg:** w = 0,15'te örtüşme 1,00, rota ort. pürüzlülük 0,68 → 0,68 m, 920,3 → 920,3 Wh, 1,551 → 1,551 h, min SOC 84,62 → 84,62; kriterin hücre maliyetindeki payı %13,1.
- **4-B LPR-1 28 Eyl 2026:** hamle 41 → 41, varış 2,979 → 2,979 h, min SOC %92,5 → %92,5, örtüşme 1,00, rota pürüzlülük 1,10 → 1,10 m, B5 tamamlanma %100,0 → %100,0, rezerv içinde %99,8 → %99,8.
- **4-B LPR-1 Ay gecesi 13 Eyl 2026:** hamle 116 → 116, varış 6,749 → 6,749 h, min SOC %67,4 → %67,4, örtüşme 0,89, rota pürüzlülük 0,72 → 0,71 m, B5 tamamlanma %98,8 → %98,8, rezerv içinde %88,8 → %88,8.
- **4-B VIPER kısa leg 30 May 2027 (haven kuralı):** hamle 8 → 8, varış 2,235 → 2,235 h, min SOC %72,3 → %72,3, örtüşme 1,00, rota pürüzlülük 1,00 → 1,00 m, B5 tamamlanma %99,6 → %99,6, rezerv içinde %95,0 → %95,0.
- **PSR doğrulaması:** PGDA maskesi ile `shadow_ratio ≥ 0,99` hücrelerimiz Jaccard **0,830** (PSR'ın %98,3'i yakalandı, karanlıkların %84,2'i PSR); 20 m ürün bloklarında **0,912**. Kalan fark 20 m ürün pikselinin 5 m hücrelerle kenar uyumsuzluğu ve bizim 18,6 yıllık örneklememizle ürünün tanımı arasındaki fark; hepsi yazıldığı gibi.
- **Sunum cümlesi:** "İki katmanımız artık NASA'nın ölçülmüş ürünleridir: LOLA LDRM hektometre ölçekli pürüzlülüğü beşinci kriter olarak gride girdi (eğimle Spearman 0,21), PGDA PSR maskesi gölge modelimizle Jaccard 0,83 örtüşüyor; kriter Site11'de rotayı çifte göre değiştirdi — sayılar yukarıda."
- **İddia sınırı:** katman MEASURED ama 50 m/px ve 100 m taban — bir 5 m hücre, onu kapsayan pikselin blok istatistiğini taşır, kendi pürüzlülüğünü değil; ölçek istatistiktir (MODEL), rover toleransı değil; `w_roughness = 0,15` varsayımdır (tarama yukarıda); Diviner kaya bolluğu kullanılmadı (kapsam ±80°).

