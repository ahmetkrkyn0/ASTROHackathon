# Kurtarma politikası ve şans-kısıtlı 4-B planlama (B1) — LunaPath raporu

Üretildi: 2026-09-05T13:49:35+00:00 (`scripts/recovery_policy_report.py`, toplam 2 957 s). Site11 (500 × 500 × 5 m), coarsen 4; Monte Carlo 1 000 koşum, tohum 0. Arıza modeli: α ∈ {0,0, 0,2, 0,5} 1/km, R = 10 h (**varsayım**: assumption: Lamarre, Malhotra, Kelly -- Recovery Policies for Safe Exploration of Lunar PSRs (Acta Astronautica 2023, arXiv 2307.16786) experiment 3 and Safe Mission-Level Path Planning (IEEE AERO 2024, arXiv 2401.08558) Table II: Poisson faults at 1 per 5 000 m driven, 36 000 s to recover; no rover profile in this catalogue publishes either number).

**İddia sınırı:** MODEL: a reach-avoid value iteration under an ASSUMED Poisson fault model (rate and recovery time are Lamarre et al.'s experiment values, not a rover specification) on a coarsened grid with a coarsened time axis; P_safe is the success probability of the best policy the discretised model can express: the charge is read by linear interpolation between SOC bin centres (Lamarre's 'interpolation map', unbiased in expectation -- his conservative lower-bin map charges a whole bin per 20 m move here and is unusable), the time by the worse of the two neighbouring bins, and every action takes at least one bin (the field's clock is slower than the rover's). Conservativeness is therefore EMPIRICAL, checked against a Monte Carlo of the policy in continuous time, never assumed; P_safe is never a measured rate. The default safe set (goal or haven) is NOT Lamarre's haven-only set: on Site11 LPR-1 has no haven at any probed epoch. Lamarre's numbers (41.5 M states, beta 2 percent -> 1.5 percent realised, +0.5 km and +2 h for the risk-bounded plan) are quoted from the papers, not reproduced.

## 1. Formülasyon ve Lamarre ile farklar

Durum `x = (zaman kutusu, kaba blok, SOC kutusu)`; eylemler planlayıcının 8 hamlesi + bir kutu bekle; `V_k(x) = 1_{X\O}(x) + 1_{O\S}(x) · min_a max_φ Σ_o p_o · V_{k+1}(φ(f_o(x,a)))` (başarısızlık olasılığı; güvenli 0, başarısız 1); `P_safe = 1 − V`. Arıza: Poisson α/km, sürüş iki yarı, üç sonuç (`e^{−αρ}`, `1 − e^{−αρ/2}` kaynakta, `e^{−αρ/2} − e^{−αρ}` hedefte), R saat bekleme ev-içi güçte. Planlayıcı her etikette yürütme hayatta-kalma çarpanı taşır (`surv' = surv · (p0 + p1·P_safe(f1) + p2·P_safe(f2))`) ve `1 − surv > β` olan hamleyi reddeder.

| | Lamarre vd. (alıntı) | LunaPath B1 (ölçüm) |
|---|---|---|
| Durum sayısı | 2 500 000 (deney 1) / 41 500 000 (deney 3) | Site11 coarsen 4: bkz. § 2 (tavan 100 000 000) |
| Zaman kutusu | 3600 s (deney 3), 1800 s (AERO ROI 1) | plan diliminin `m` katı, otomatik (bkz. § 2) |
| Enerji kutusu | 250 Wh (deney 3), 150 Wh (AERO) | `e_cap / 20` (LPR-1 271 Wh, VIPER katalog) |
| Bekleme eylemi | 5000 s | bir DP kutusu |
| Arıza oranı α | 1/1 000 m (deney 1), 1/5 000 m (deney 3, AERO) | **varsayım** 0,2/km (Lamarre'den), 0 ve 0,5 süpürülür |
| Toparlanma R | 18000 s / 36000 s | **varsayım** 10 h |
| Güvenli küme | haven'da Ay gecesini geçecek SOC (ζ_h(t)) | `leg`: hedef bloğu ≥ rezerv ∪ haven ≥ rezerv + tam-gölge ev-içi × h_max; `haven`: yalnız haven (Lamarre) |
| Zaman / enerji eşlemesi | φ_L/φ_U min-max, alt enerji kutusu; sonsuz ufuk yakınsayana dek | her eylem ≥ 1 kutu (tek geriye geçiş); φ_L/φ_U `floor ≥ 1` hamlelerde ve planlayıcı okumasında; enerji **kutu merkezleri arasında doğrusal ara değer** (Lamarre'nin 'interpolation map'i — alt-kutu eşlemesi 20 m hamlede her karanlık hamleyi tam kutu düşürüyordu, spec) |
| Karanlık saati / termal | durumda yok / yok | durumda yok (yalnız toparlanma beklemesinde R > h_max karanlıkta ölümcül) / yok (C6) |
| Şans kısıtı | yörünge düzeyi, TEMPEST geriye arama, waypoint'ler | tek leg, etiket-koyan A*'da yürütme çarpanı, β başlangıçta optimal politika sınırı |
| Doğrulama | 100 000 MC (deney 3); β = 2 % → gerçekleşen 1,5 % (10 000 deneme) | politika rollout'u ve SHERPA arıza olaylı, 1 000 koşum (bkz. § 4) |
| Risk-sınırlı plan bedeli | +0.5 km, +2.0 h (β = 5 %, 21 km) | bkz. § 3 |

Belgedeki "tahmin %0,4–9,8 / gerçekleşen %0,0–4,6" aralığı makale HTML'inde doğrulanamadı; alıntı olarak belgede kalır. gplanetary-nav deposunda kurtarma politikası kodu yoktur (yalnız harita/graf/güneş kütüphanesi); formülasyon makalelerden alındı.

## 2. Site11'de durum uzayı, süre ve `P_safe` dağılımı (coarsen 4, leg kümesi)

| Çift | α (1/km) | Kutu (h) | m | Kutu sayısı | Ufuk (h) | Durum | MB | DP (s) | plan-4d + alan (s) | Gölge | Haven blok | P_safe ort. (tam SOC) | ≥ 0,95 | ≥ 0,5 | = 0 | Başlangıç P_safe (tam / yarım SOC) | Yürütme riski (rota) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,0 | 0,072 | 2 | 261 | 18,7 | 65 250 000 | 312 | 44,2 | 57,0 | spice_horizon | 0 | 0,981 | 96,5 % | 98,5 % | 1,5 % | 1,0000 / 0,9995 | 0,000 % |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,2 | 0,072 | 2 | 261 | 18,7 | 65 250 000 | 312 | 95,8 | 102,3 | spice_horizon | 0 | 0,880 | 52,0 % | 94,0 % | 1,5 % | 0,9849 / 0,9723 | 1,650 % |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,5 | 0,072 | 2 | 261 | 18,7 | 65 250 000 | 312 | 97,1 | 114,0 | spice_horizon | 0 | 0,720 | 15,7 % | 84,5 % | 0,6 % | 0,9211 / 0,8964 | 9,067 % |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,0 | 0,108 | 3 | 274 | 29,5 | 68 500 000 | 328 | 52,5 | 85,8 | spice_horizon | 0 | 0,980 | 97,0 % | 98,5 % | 1,5 % | 0,9978 / 0,5785 | 0,000 % |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,2 | 0,108 | 3 | 274 | 29,5 | 68 500 000 | 328 | 135,6 | 155,2 | spice_horizon | 0 | 0,921 | 47,6 % | 98,4 % | 1,5 % | 0,8827 / 0,4044 | 11,052 % |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,5 | 0,108 | 3 | 274 | 29,5 | 68 500 000 | 328 | 104,2 | 160,6 | spice_horizon | 0 | 0,765 | 31,8 % | 89,7 % | 0,6 % | 0,5810 / 0,2210 | 43,330 % |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,0 | 0,118 | 1 | 159 | 18,7 | 39 750 000 | 191 | 24,3 | 32,8 | spice_horizon | 862 | 0,724 | 60,1 % | 73,1 % | 8,7 % | 1,0000 / 0,7894 | 0,000 % |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,2 | 0,118 | 1 | 159 | 18,7 | 39 750 000 | 191 | 45,9 | 49,6 | spice_horizon | 862 | 0,647 | 35,5 % | 70,0 % | 8,7 % | 1,0000 / 0,7608 | 0,076 % |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,5 | 0,118 | 1 | 159 | 18,7 | 39 750 000 | 191 | 46,4 | 49,3 | spice_horizon | 862 | 0,562 | 21,5 % | 56,9 % | 0,8 % | 1,0000 / 0,7198 | 0,432 % |

**Katı (Lamarre) güvenli küme — yalnız haven blokları, 24 h ufuk, tam SOC:**

- LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426): A1 haritasında bu epokta kaba haven bloğu yok (katı küme boş, P_safe ≡ 0).
- LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450): A1 haritasında bu epokta kaba haven bloğu yok (katı küme boş, P_safe ≡ 0).
- VIPER kısa leg, 30 May 2027, (358,494)→(346,462): 862 güvenli blok, 51 250 000 durum, DP 64,7 s; P_safe ort. 0,725, ≥ 0,95: 44,4 %, ≥ 0,5: 77,0 %, = 0: 4,1 %.

## 3. β süpürmesi — `/api/plan-4d` `max_failure_probability` (α = 0,2/km, R = 10 h)

| Çift | β | Durum | Hamle | Bekle | Varış (h) | Min SOC | Yürütme riski | Min P_safe | Başlangıç P_safe | Reddedilen hamle | Nominalle örtüşme | Düğüm | plan-4d (s) ilk / önbellekli alan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | yok (alan yok) | 200 | 41 | 0 | 2,979 | 92,5 % | — | — | — | — | 100 % | 31 219 | 7,0 / — |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | yok (alan var) | 200 | 41 | 0 | 2,979 | 92,5 % | 1,650 % | 0,9849 | 0,9849 | 0 | 100 % | 31 219 | 97,5 / 11,2 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,1 | 200 | 41 | 0 | 2,979 | 92,5 % | 1,650 % | 0,9849 | 0,9849 | 0 | 100 % | 31 234 | 10,7 / 10,7 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,05 | 200 | 41 | 0 | 2,979 | 92,5 % | 1,650 % | 0,9849 | 0,9849 | 0 | 100 % | 31 234 | 10,7 / 10,8 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 0,02 | 200 | 41 | 0 | 2,979 | 92,5 % | 1,650 % | 0,9849 | 0,9849 | 13 811 | 100 % | 30 179 | 10,4 / 10,3 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | yok (alan yok) | 200 | 116 | 0 | 6,749 | 67,4 % | — | — | — | — | 100 % | 171 117 | 21,6 / — |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | yok (alan var) | 200 | 116 | 0 | 6,749 | 67,4 % | 11,052 % | 0,8827 | 0,8827 | 0 | 100 % | 171 117 | 144,9 / 42,8 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,1 | 404 | — | — | — | — | — | — | — | — | — | — | 5,6 — Start (46, 8) cannot satisfy max_failure_probability=0.1: even the optimal recovery policy from there fails with probability 0.1173 (P_safe 0.8827 at 100 percent charge), and no plan can do better than the optimal policy |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,05 | 404 | — | — | — | — | — | — | — | — | — | — | 7,1 — Start (46, 8) cannot satisfy max_failure_probability=0.05: even the optimal recovery policy from there fails with probability 0.1173 (P_safe 0.8827 at 100 percent charge), and no plan can do better than the optimal polic |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 0,02 | 404 | — | — | — | — | — | — | — | — | — | — | 6,3 — Start (46, 8) cannot satisfy max_failure_probability=0.02: even the optimal recovery policy from there fails with probability 0.1173 (P_safe 0.8827 at 100 percent charge), and no plan can do better than the optimal polic |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | yok (alan yok) | 200 | 8 | 0 | 2,235 | 72,3 % | — | — | — | — | 100 % | 1 635 | 2,9 / — |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | yok (alan var) | 200 | 8 | 0 | 2,235 | 72,3 % | 0,076 % | 0,9993 | 1,0000 | 0 | 100 % | 1 635 | 48,3 / 3,1 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,1 | 200 | 8 | 0 | 2,235 | 72,3 % | 0,076 % | 0,9993 | 1,0000 | 0 | 100 % | 1 635 | 3,1 / 3,1 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,05 | 200 | 8 | 0 | 2,235 | 72,3 % | 0,076 % | 0,9993 | 1,0000 | 0 | 100 % | 1 635 | 3,1 / 3,2 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 0,02 | 200 | 8 | 0 | 2,235 | 72,3 % | 0,076 % | 0,9993 | 1,0000 | 0 | 100 % | 1 635 | 3,4 / 3,3 |

## 4. Tahmin edilen vs gerçekleşen risk (α = 0,2/km, R = 10 h)

Politika rollout'u (`survival.rollout`, sürekli saat/SOC, 1 000 koşum, Wilson %95): (a) başlangıçtan yalnız politika — DP'nin `V(start)`'ı ile; (b) önce kısıtsız plan, arızadan sonra politika — planlayıcının yürütme riski ile; (c) β planı varsa aynı. SHERPA (B5, 1 000 koşum): sabit rota, arıza olayı eklenmiş (rota değişmez; planlayıcının tahmini optimal kurtarma varsayar, bire bir karşılaştırılmaz).

| Çift | Ölçüm | Tahmin | Gerçekleşen | Wilson %95 | Güvenli / başarısız / ufuk | Ort. arıza | Konservatif? | s |
|---|---|---|---|---|---|---|---|---|
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | (a) yalnız politika | 1,512 % | 1,200 % | 0,69 %–2,09 % | 988 / 0 / 12 | 0,196 | evet | 0,6 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | (b) plan + politika | 1,650 % | 1,000 % | 0,54 %–1,83 % | 990 / 0 / 10 | 0,180 | evet | 0,2 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | (c) β planı + politika (β = 0,05) | 1,650 % | 1,200 % | 0,69 %–2,09 % | 988 / 0 / 12 | 0,187 | evet | — |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | SHERPA, arıza yok | — | 0,000 % | 0,00 %–0,38 % | tamamlanma 100,0 %; başarısızlık yok | 0,000 (0 koşumda) | — | 2,9 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | SHERPA + arıza | — | 0,000 % | 0,00 %–0,38 % | tamamlanma 100,0 %; başarısızlık yok | 0,190 (179 koşumda) | — | 2,2 |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | SHERPA yalnız arıza (σ = 0) | 1,650 % | 0,000 % | 0,00 %–0,38 % | tamamlanma 100,0 %; başarısızlık yok | 0,191 (175 koşumda) | — | — |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | (a) yalnız politika | 11,728 % | 4,600 % | 3,47 %–6,08 % | 954 / 38 / 8 | 0,573 | evet | 1,5 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | (b) plan + politika | 11,052 % | 4,000 % | 2,95 %–5,40 % | 960 / 27 / 13 | 0,570 | evet | 0,6 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | SHERPA, arıza yok | — | 1,200 % | 0,69 %–2,09 % | tamamlanma 98,8 %; battery_depleted 12 | 0,000 (0 koşumda) | — | 3,0 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | SHERPA + arıza | — | 5,900 % | 4,60 %–7,54 % | tamamlanma 94,1 %; battery_depleted 59 | 0,568 (441 koşumda) | — | 2,1 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | SHERPA yalnız arıza (σ = 0) | 11,052 % | 0,000 % | 0,00 %–0,38 % | tamamlanma 100,0 %; başarısızlık yok | 0,559 (430 koşumda) | — | — |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | (a) yalnız politika | 0,000 % | 0,000 % | 0,00 %–0,38 % | 1000 / 0 / 0 | 0,000 | evet | 0,0 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | (b) plan + politika | 0,076 % | 0,000 % | 0,00 %–0,38 % | 1000 / 0 / 0 | 0,000 | evet | 0,0 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | (c) β planı + politika (β = 0,05) | 0,076 % | 0,000 % | 0,00 %–0,38 % | 1000 / 0 / 0 | 0,000 | evet | — |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | SHERPA, arıza yok | — | 0,400 % | 0,16 %–1,02 % | tamamlanma 99,6 %; battery_depleted 4 | 0,000 (0 koşumda) | — | 0,7 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | SHERPA + arıza | — | 1,800 % | 1,14 %–2,83 % | tamamlanma 98,2 %; battery_depleted 18 | 0,048 (48 koşumda) | — | 0,6 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | SHERPA yalnız arıza (σ = 0) | 0,076 % | 0,000 % | 0,00 %–0,38 % | tamamlanma 100,0 %; başarısızlık yok | 0,038 (38 koşumda) | — | — |

## 5. Kurtarma politikası örnekleri

**LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426)**

- `/api/replan` (`recovery_policy: true`, başlangıç, tam SOC): **NW** → blok [88, 122] (piksel [354, 490]); P_safe şimdi 0,9991, sonra 0,9992; SOC 100 %, t = 0,00 h
- Rota ortası durum [68, 118, 41] (SOC 94,9 %): **N** → blok [67, 118] (piksel [270, 474]); P_safe şimdi 0,9960, sonra 0,9963; SOC 95 %, t = 1,47 h
- Aynı durum, yarım batarya: **N** → blok [67, 118] (piksel [270, 474]); P_safe şimdi 0,9950, sonra 0,9956; SOC 50 %, t = 1,47 h
- Aynı blokta 10 h arıza beklemesinden sonra: **N** → blok [67, 118] (piksel [270, 474]); P_safe şimdi 0,9116, sonra 0,9152; SOC 87 %, t = 11,49 h

**LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450)**

- `/api/replan` (`recovery_policy: true`, başlangıç, tam SOC): **S** → blok [47, 8] (piksel [190, 34]); P_safe şimdi 0,8827, sonra 0,8845; SOC 100 %, t = 0,00 h
- Rota ortası durum [97, 57, 105] (SOC 82,3 %): **E** → blok [97, 58] (piksel [390, 234]); P_safe şimdi 0,9692, sonra 0,9700; SOC 82 %, t = 3,77 h
- Aynı durum, yarım batarya: **E** → blok [97, 58] (piksel [390, 234]); P_safe şimdi 0,8599, sonra 0,8623; SOC 50 %, t = 3,77 h
- Aynı blokta 10 h arıza beklemesinden sonra: **E** → blok [97, 58] (piksel [390, 234]); P_safe şimdi 0,7625, sonra 0,7656; SOC 70 %, t = 13,78 h

**VIPER kısa leg, 30 May 2027, (358,494)→(346,462)**

- `/api/replan` (`recovery_policy: true`, başlangıç, tam SOC): **safe** → blok None (piksel None); P_safe şimdi 1,0000, sonra 1,0000; SOC 100 %, t = 0,00 h
- Rota ortası durum [86, 119, 11] (SOC 82,4 %): **W** → blok [86, 118] (piksel [346, 474]); P_safe şimdi 0,9998, sonra 0,9999; SOC 82 %, t = 1,29 h
- Aynı durum, yarım batarya: **W** → blok [86, 118] (piksel [346, 474]); P_safe şimdi 0,9847, sonra 0,9881; SOC 50 %, t = 1,29 h
- Aynı blokta 10 h arıza beklemesinden sonra: **W** → blok [86, 118] (piksel [346, 474]); P_safe şimdi 0,9841, sonra 0,9881; SOC 50 %, t = 11,29 h

## 6. İddia sınırı ve sunum cümlesi

- MODEL: a reach-avoid value iteration under an ASSUMED Poisson fault model (rate and recovery time are Lamarre et al.'s experiment values, not a rover specification) on a coarsened grid with a coarsened time axis; P_safe is the success probability of the best policy the discretised model can express: the charge is read by linear interpolation between SOC bin centres (Lamarre's 'interpolation map', unbiased in expectation -- his conservative lower-bin map charges a whole bin per 20 m move here and is unusable), the time by the worse of the two neighbouring bins, and every action takes at least one bin (the field's clock is slower than the rover's). Conservativeness is therefore EMPIRICAL, checked against a Monte Carlo of the policy in continuous time, never assumed; P_safe is never a measured rate. The default safe set (goal or haven) is NOT Lamarre's haven-only set: on Site11 LPR-1 has no haven at any probed epoch. Lamarre's numbers (41.5 M states, beta 2 percent -> 1.5 percent realised, +0.5 km and +2 h for the risk-bounded plan) are quoted from the papers, not reproduced.
- Kapsam: state (time bin, coarse block, SOC bin); actions: the planner's eight moves and a one-bin wait; failure: a SOC bin under the reserve, a fault hold longer than h_max_shadow_h in a dark block, or the horizon running out; the continuous-shadow clock and the thermal envelope are NOT state variables (the planner's own labels still enforce the shadow clock on the plan). Energy is cost_engine's: traction, housekeeping with the heater in shadow, solar income; the fault hold drains at housekeeping power (the catalogue has no fault-resolution power).
- Zaman kutusu plan diliminin katı ve her eylem en az bir kutu sürer: DP'nin saati gerçek saatten **yavaştır** (kötümser); yürütme riski bu yüzden SHERPA'nın sabit-rota gerçekleşmesinden yukarıda çıkabilir ve bu bir hata değil, ayrıklaştırmanın yönüdür. Tersi (tahmin < gerçekleşen) olduğunda satır "konservatif: hayır" der.
- Sayıların tamamı Site11'de bu betikle koşturulup okundu; Lamarre'nin sayıları § 1'de alıntıdır.

**Sunum cümlesi:** "Toronto STARS'ın reach-avoid formülasyonunu LunaPath'in kendi kaba gridi, SPICE gölge serisi ve enerji fiziği üzerinde kurduk: her (zaman, blok, SOC) durumundan güvenli kümeye ulaşma olasılığı ve kurtarma politikası 40 M–70 M durumda 1–2 dakikada hesaplanıyor; 4-B planlayıcı 'görev başarısızlık olasılığı ≤ β' kısıtını taşıyor; tahmin edilen risk politikayı izleyen Monte Carlo ile denetlendi. Arıza oranı bir varsayımdır ve öyle etiketlenir."

