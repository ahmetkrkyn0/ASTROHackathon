# DEM hata yayılımı — NASA'nın Site11 DEM klonlarıyla Monte Carlo (B3)

Üretildi: `scripts/dem_uncertainty_report.py` ile, 2026-09-04. Klon önbelleği: `Site11`, 100 klon (`nasa_pgda_clones`), pencere 500×500 px + 200 px (1000 m) yakın-alan dolgusu, 2026-09-04T15:00:40Z tarihinde 1889 s'de 4 paralel bağlantıyla indirildi. Ürün: https://pgda.gsfc.nasa.gov/products/78.

## 1. Klonlar NASA'nın hata haritalarına karşı

| Nicelik | Ölçülen | NASA'nın yayınladığı (ürün sayfası, tüm siteler) |
|---|---|---|
| `toterr` (Z belirsizliği) medyan / ortalama / p95 | 0,373 / 0,407 / 0,743 m | medyan RMS 0,30–0,50 m |
| `slperr` (eğim belirsizliği) medyan / ortalama / p95 | 1,73 / 1,82 / 2,71° | medyan RMS 1,5–2,5° |
| `klon − surf` ortalama / RMS (100 klon) | -0,0109 / 0,4490 m | RMS(`toterr`) = 0,4490 m |
| Klon başına RMS / RMS(`toterr`) | 0,975 – 1,027 | 1 beklenir |
| Uzamsal korelasyon (klon 1) | 5 m: 0,88, 10 m: 0,69, 25 m: 0,34, 50 m: 0,12, 100 m: -0,00 | — |

Klon dosyaları (`_err.tif`) adlarına rağmen tam yüzey DEM'leridir; hata gerçekleşmesi `klon − surf`'tür ve RMS'i NASA'nın `toterr` haritasının RMS'ine eşittir (klon = `surf + toterr · ξ`, ξ birim varyanslı, ~100 m'de dekorele).

## 2. Eğim belirsizliği: topluluk vs NASA

| | Medyan | p95 |
|---|---|---|
| Bizim topluluk σ (np.gradient, 100 klon) | 1,516° | 1,985° |
| NASA `slperr` | 1,726° | 2,714° |

Medyan oranı 0,878, hücre-hücre korelasyon 0,418; 100 klonun eğimi 0,9 s.

**Eğim yanlılığı:** topluluk ortalaması − yüzey eğimi: medyan 0,158°, ortalama 0,179°, p95 1,846° (yüzey eğimi medyanı 10,51°). Sıfır ortalamalı yükseklik gürültüsü gradyanın büyüklüğünü şişirir (|∇(z+ε)| ortalaması |∇z|'den büyüktür); yüzey DEM'i en iyi tahmin, klonlar gerçek arazi kadar pürüzlüdür. Bu yüzden rota bantlarında nominal (yüzey) enerji bandın altında kalır.

## 3. P(geçilebilir) — rover başına ve klon sayısına göre yakınsama

| Rover (eğim sınırı) | Temel geçilebilir | Kesin geçilebilir (P = 1) | Kesin geçilmez (P = 0) | Belirsiz (0,05 < P < 0,95) | Temelde geçilebilir ama P < 0,5 | Süre |
|---|---|---|---|---|---|---|
| `nasa_viper` (20°) | 79,43 % | 68,61 % | 16,87 % | **8,24 %** | 0,905 % | 0,15 s |
| `lpr_1` (25°) | 84,03 % | 80,73 % | 14,55 % | **2,83 %** | 0,364 % | 0,16 s |

Yakınsama (tam topluluğa göre):

| Rover | N | Belirsiz oran | ort. \|P_N − P_tam\| | p95 | maks |
|---|---|---|---|---|---|
| `nasa_viper` | 5 | 6,01 % | 0,0142 | 0,110 | 0,85 |
| `nasa_viper` | 10 | 8,17 % | 0,0099 | 0,070 | 0,56 |
| `nasa_viper` | 20 | 7,24 % | 0,0068 | 0,050 | 0,35 |
| `nasa_viper` | 30 | 8,46 % | 0,0052 | 0,037 | 0,29 |
| `nasa_viper` | 50 | 8,51 % | 0,0034 | 0,020 | 0,18 |
| `nasa_viper` | 75 | 8,71 % | 0,0019 | 0,013 | 0,11 |
| `nasa_viper` | 100 | 8,24 % | 0,0000 | 0,000 | 0,00 |
| `lpr_1` | 5 | 2,05 % | 0,0048 | 0,000 | 0,65 |
| `lpr_1` | 10 | 2,72 % | 0,0033 | 0,000 | 0,57 |
| `lpr_1` | 20 | 2,46 % | 0,0022 | 0,000 | 0,37 |
| `lpr_1` | 30 | 2,86 % | 0,0017 | 0,000 | 0,28 |
| `lpr_1` | 50 | 2,91 % | 0,0011 | 0,000 | 0,21 |
| `lpr_1` | 75 | 2,99 % | 0,0006 | 0,000 | 0,10 |
| `lpr_1` | 100 | 2,83 % | 0,0000 | 0,000 | 0,00 |

## 4. P(aydınlık, t) — klon ufukları

100 klon küpü, stride 4 (plan-4d blok merkezleri), yakın alan 1000 m klonlanmış; uzak alan (yüzey DEM'inin 10 km bağlamı + LOLA 40 m) sabit. Yüzeyin iki-geçişli ufku üretim küpüyle fark 0,000000° (birebir). Klon başına küp 2,52 s. İhmal edilen uzak-alan kayması ≤ 0,0214° (medyan `toterr` / 1 km).

Klon 1 ufku − yüzey ufku: ortalama |Δ| 0,702°, p95 3,12°, maks 24,35°; ufku 2°'nin altındaki (Güneş için belirleyici) hücrelerde ortalama |Δ| 0,273°. 5 m/px'te ufku çoğu zaman komşu hücre belirler; iki komşunun hata farkı ~0,22 m (σ 0,45 m, korelasyon 0,88) 5 m'de 2,5°'dir.

| Epoch | Klon | Belirsiz hücre oranı p50 / p95 / maks (48 h × 1 h) | Ortalama aydınlık p50 | Süre |
|---|---|---|---|---|
| 2027-05-30T00:00:00 | 100 | 10,81 % / 13,21 % / 13,27 % | 35,1 % | 0,3 s |
| 2026-09-28T00:00:00 | 100 | 0,00 % / 2,46 % / 2,52 % | 0,0 % | 0,2 s |

## 5. Rota bantları (B5'in iki rotası)

### VIPER haven->haven, 30 May 2027

Rover `nasa_viper`, epoch `2027-05-30T00:00:00`, coarsen 4: 40 MOVE, 0 WAIT, varış 7,36 h, dilim 0,0956 h, planlayıcı en düşük batarya 32,1 %; plan-4d `uncertainty` bloğu: 100 klon, rota geçilebilir oranı 1,0 %, P min 0,270, P ort. 0,919; planlama 10,0 s.

| Bant | Klon | Rota geçilebilir (Wilson %95) | Varış | Sürüş enerjisi p5/p50/p95 (Wh) | Nominal | Bataryadan çekilen p5/p50/p95 (Wh) | Sürüş saati p5/p50/p95 | Süre p5/p50/p95 (h) | Min batarya p5 (%) | Maks gölge p95 (h) | SHERPA tamamlanma | Süre (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dem | 100 | 1,0 % (0,2 %–5,5 %) | 100,0 % | 2258 / 2293 / 2334 | 2127 | 3203 / 3238 / 3278 | 4,61 / 4,63 / 4,64 | 7,27 / 7,27 / 7,27 | 18,0 | 7,27 | - | 1,8 |
| dem+sherpa | 100 | 1,0 % (0,2 %–5,5 %) | 100,0 % | 2258 / 2293 / 2334 | 2127 | 3203 / 3238 / 3278 | 4,61 / 4,63 / 4,64 | 7,27 / 7,27 / 7,27 | 18,0 | 7,27 | 17,8 % (17,3 %–18,4 %), 20000 koşum | 3,1 |

Gökyüzü `clone_horizon`; süre dağılımı: gökyüzü 0,11 s, koşumlar 1,16 s.

### LPR-1, 28 Sep 2026

Rover `lpr_1`, epoch `2026-09-28T00:00:00`, coarsen 4: 40 MOVE, 0 WAIT, varış 2,16 h, dilim 0,0287 h, planlayıcı en düşük batarya 96,2 %; plan-4d `uncertainty` bloğu: 100 klon, rota geçilebilir oranı 99,0 %, P min 0,990, P ort. 1,000; planlama 7,9 s.

| Bant | Klon | Rota geçilebilir (Wilson %95) | Varış | Sürüş enerjisi p5/p50/p95 (Wh) | Nominal | Bataryadan çekilen p5/p50/p95 (Wh) | Sürüş saati p5/p50/p95 | Süre p5/p50/p95 (h) | Min batarya p5 (%) | Maks gölge p95 (h) | SHERPA tamamlanma | Süre (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dem | 100 | 99,0 % (94,5 %–99,8 %) | 100,0 % | 538 / 546 / 556 | 506 | 129 / 189 / 244 | 1,41 / 1,41 / 1,42 | 2,13 / 2,13 / 2,13 | 94,8 | 0,52 | - | 1,7 |
| dem+sherpa | 100 | 99,0 % (94,5 %–99,8 %) | 100,0 % | 538 / 546 / 556 | 506 | 129 / 189 / 244 | 1,41 / 1,41 / 1,42 | 2,13 / 2,13 / 2,13 | 94,8 | 0,52 | 100,0 % (100,0 %–100,0 %), 20000 koşum | 3,7 |

Gökyüzü `clone_horizon`; süre dağılımı: gökyüzü 0,12 s, koşumlar 1,20 s.

## 6. Süreler

- Klon indirme: 100 klon, 1889 s (4 paralel bağlantı; sunucu tek bağlantıda ~170 KB/s).
- Klon başına ufuk küpü: 2,52 s (stride 4, 114 yakın örnek); uzak alan bir kez.
- 100 klonun eğimi: 0,9 s; rover başına P(geçilebilir): `nasa_viper` 0,1 s, `lpr_1` 0,2 s.
- `/api/uncertainty-series` 2027-05-30T00:00:00, 48 dilim: 0,3 s.
- `/api/uncertainty-series` 2026-09-28T00:00:00, 48 dilim: 0,2 s.
- `/api/dem-uncertainty` VIPER haven->haven, 30 May 2027 [dem]: 1,8 s.
- `/api/dem-uncertainty` VIPER haven->haven, 30 May 2027 [dem+sherpa]: 3,1 s.
- `/api/dem-uncertainty` LPR-1, 28 Sep 2026 [dem]: 1,7 s.
- `/api/dem-uncertainty` LPR-1, 28 Sep 2026 [dem+sherpa]: 3,7 s.
