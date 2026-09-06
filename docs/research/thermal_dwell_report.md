# Termal operasyon zarfı ve tolere edilebilir saplanma süresi — C6 raporu

Üretildi 2026-09-05T19:19:13Z · `python scripts/thermal_dwell_report.py` (Site11, coarsen 4; toplam 8,8 dk). Sayıların hepsi bu makinede koşturulup okundu; JSC'nin sayıları **alıntıdır** ve ayrı tabloda durur.

Okuma notu: termal model MODEL/UNCALIBRATED'dır (heat1d tepe LUT'u + gölge bağlaması, regolit gevşemesi kalibre edilmemiş, iç sıcaklık ofsetleri kataloğun MODELLED alanları). Isıtıcı sıcaklık modeline yalnız `heater_model="thermostat_assumed"` **varsayımıyla** girer; varsayılan `none`. Hiçbir yerde termal doğruluk iddiası yoktur (Diviner karşılaştırması C5'in işi).

## 1. JSC'nin zarfı (alıntı) ve bizim zarf matrisimiz (heat1d, Site11 enlemi)

**Alıntı (ICES-2025-376, Slusser vd. 2025):**

- Kutupta maksimum Güneş yüksekliği **1,5°**; the maximum solar elevation angle at the lunar poles is 1.5 deg, increasing by one degree for every degree in latitude from the pole (Sec. III.D).
- Zarf eksenleri: downslope solar azimuth angle relative to the rover heading (angular, 16 evenly spaced) vs slope angle (radial, 0-15 deg in 3 deg steps); the slope direction is kept parallel to the solar azimuth and the solar elevation is the mission maximum; the rover is parked in its highest continuous power state (Sec. V.G).
- Durum matrisi **96** (16 azimuths x 6 slopes, steady-state; negative (Sun-averted) slopes left out as more benign); more than 60 critical components.
- AFT aşım örneği: an avionics box, AFT 65 °C, model 77 °C → **12 °C aşım** (the normalisation example (Sec. V.G), not a specific slope/elevation case).
- Tolere edilebilir saplanma süresi: the finite time a vehicle may remain static after a mobility fault before it can no longer complete the direct traverse and arrive at the destination safe haven before lunar night; off-nominal thermal transients are bounded by it (Sec. V.H). Kısıtlar: does not take into account state-of-charge variances, transient shadow allowances, or a fault anywhere along a nominal traverse; VIPER's speed means it is always at risk of reaching thermal balance with its environment (Sec. V.H).
- Araç: Thermal Desktop; haven geceleri 50–150 h.

**Bizim matrisimiz:** JSC'nin açısal ekseni rover başlığına göre Güneş azimutudur (rover gövdesi/TMS modeli gerektirir; LunaPath'te yok). Bizim eksenlerimiz **Güneş yüksekliği × Güneş'e paralel eğim bileşeni** (`s_par = atan(tan s · cos(az_Güneş − bakı))`, pozitif = Güneş'e bakan); heat1d transient'i (13 Ay günü, crank-nicolson) her adımda kutulanır, kutu başına **maksimum** yüzey sıcaklığı alınır; iç sıcaklık kataloğun ofsetleriyle, karar en dar zarfa göre. Aynı yöntem, bizim model; karşılaştırma değil.

### LPR-1 (Varsayilan) — `heater_model=none`

heat1d: enlem -88,9205°, eğimler [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0], 235 159 örnek, 205/288 kutu örneklendi, yüzey -232,4…44,5 °C, Güneş yüksekliği -2,62…2,60°, 233,3 s.

Kararlar: **sınırsız 19**, soğuk-sınırlı 173, sıcak-sınırlı 13, örneklenmedi 83. En sıcak yüzey 44,5 °C; 'sıcak-sınırlı' kutuların yüzeyi -23,5…-0,4 °C — hepsi 0 °C altı: ofset modelinin soğuk dalı (+60 K) bu bandı 35 °C üstüne atar; gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok.

Kutu harfi: S sınırsız, s soğuk-sınırlı, h sıcak-sınırlı, · örneklenmedi; sayı kutunun maks yüzey sıcaklığı (°C); s_par sütunlarının her ikincisi.

| yükseklik \ s_par (°) | -28,8 | -23,8 | -18,8 | -13,8 | -8,8 | -3,8 | 1,2 | 6,2 | 11,2 | 16,2 | 21,2 | 26,2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -2,75 | s -203 | s -205 | s -207 | s -210 | s -214 | s -220 | s -228 | · | · | · | · | · |
| -2,25 | s -200 | s -199 | s -199 | s -202 | s -207 | s -214 | s -226 | · | · | · | · | · |
| -1,75 | s -186 | s -184 | s -187 | s -190 | s -196 | s -201 | s -200 | · | · | · | · | · |
| -1,25 | s -184 | s -186 | s -182 | s -180 | s -179 | s -189 | s -194 | s -195 | s -197 | s -195 | · | · |
| -0,75 | s -187 | s -181 | s -178 | s -180 | s -178 | s -176 | s -172 | s -169 | s -192 | s -191 | s -191 | s -192 |
| -0,25 | s -184 | s -181 | s -181 | s -175 | s -171 | s -165 | s -161 | s -86 | S -51 | s -127 | h -0 | s -189 |
| 0,25 | s -184 | s -181 | s -178 | s -175 | s -173 | s -165 | s -129 | s -81 | S -42 | h -13 | s 10 | s 29 |
| 0,75 | s -184 | s -181 | s -178 | s -175 | s -171 | s -164 | s -121 | s -75 | S -40 | h -13 | s 9 | s 28 |
| 1,25 | · | · | · | s -175 | s -170 | s -162 | s -117 | s -71 | S -35 | h -8 | s 14 | s 32 |
| 1,75 | · | · | · | · | · | · | s -116 | s -68 | S -32 | h -5 | s 16 | s 34 |
| 2,25 | · | · | · | · | · | · | s -112 | s -65 | S -30 | h -4 | s 17 | s 34 |
| 2,75 | · | · | · | · | · | · | s -111 | s -63 | S -29 | · | · | · |

### LPR-1 (Varsayilan) — `heater_model=thermostat_assumed`

heat1d: enlem -88,9205°, eğimler [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0], 235 159 örnek, 205/288 kutu örneklendi, yüzey -232,4…44,5 °C, Güneş yüksekliği -2,62…2,60°, 233,3 s.

Kararlar: **sınırsız 192**, soğuk-sınırlı 0, sıcak-sınırlı 13, örneklenmedi 83. En sıcak yüzey 44,5 °C; 'sıcak-sınırlı' kutuların yüzeyi -23,5…-0,4 °C — hepsi 0 °C altı: ofset modelinin soğuk dalı (+60 K) bu bandı 35 °C üstüne atar; gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok.

Kutu harfi: S sınırsız, s soğuk-sınırlı, h sıcak-sınırlı, · örneklenmedi; sayı kutunun maks yüzey sıcaklığı (°C); s_par sütunlarının her ikincisi.

| yükseklik \ s_par (°) | -28,8 | -23,8 | -18,8 | -13,8 | -8,8 | -3,8 | 1,2 | 6,2 | 11,2 | 16,2 | 21,2 | 26,2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -2,75 | S -203 | S -205 | S -207 | S -210 | S -214 | S -220 | S -228 | · | · | · | · | · |
| -2,25 | S -200 | S -199 | S -199 | S -202 | S -207 | S -214 | S -226 | · | · | · | · | · |
| -1,75 | S -186 | S -184 | S -187 | S -190 | S -196 | S -201 | S -200 | · | · | · | · | · |
| -1,25 | S -184 | S -186 | S -182 | S -180 | S -179 | S -189 | S -194 | S -195 | S -197 | S -195 | · | · |
| -0,75 | S -187 | S -181 | S -178 | S -180 | S -178 | S -176 | S -172 | S -169 | S -192 | S -191 | S -191 | S -192 |
| -0,25 | S -184 | S -181 | S -181 | S -175 | S -171 | S -165 | S -161 | S -86 | S -51 | S -127 | h -0 | S -189 |
| 0,25 | S -184 | S -181 | S -178 | S -175 | S -173 | S -165 | S -129 | S -81 | S -42 | h -13 | S 10 | S 29 |
| 0,75 | S -184 | S -181 | S -178 | S -175 | S -171 | S -164 | S -121 | S -75 | S -40 | h -13 | S 9 | S 28 |
| 1,25 | · | · | · | S -175 | S -170 | S -162 | S -117 | S -71 | S -35 | h -8 | S 14 | S 32 |
| 1,75 | · | · | · | · | · | · | S -116 | S -68 | S -32 | h -5 | S 16 | S 34 |
| 2,25 | · | · | · | · | · | · | S -112 | S -65 | S -30 | h -4 | S 17 | S 34 |
| 2,75 | · | · | · | · | · | · | S -111 | S -63 | S -29 | · | · | · |

### NASA VIPER — `heater_model=none`

heat1d: enlem -88,9205°, eğimler [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0], 235 159 örnek, 205/288 kutu örneklendi, yüzey -232,4…44,5 °C, Güneş yüksekliği -2,62…2,60°, 233,3 s.

Kararlar: **sınırsız 19**, soğuk-sınırlı 173, sıcak-sınırlı 13, örneklenmedi 83. En sıcak yüzey 44,5 °C; 'sıcak-sınırlı' kutuların yüzeyi -23,5…-0,4 °C — hepsi 0 °C altı: ofset modelinin soğuk dalı (+60 K) bu bandı 35 °C üstüne atar; gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok.

Kutu harfi: S sınırsız, s soğuk-sınırlı, h sıcak-sınırlı, · örneklenmedi; sayı kutunun maks yüzey sıcaklığı (°C); s_par sütunlarının her ikincisi.

| yükseklik \ s_par (°) | -28,8 | -23,8 | -18,8 | -13,8 | -8,8 | -3,8 | 1,2 | 6,2 | 11,2 | 16,2 | 21,2 | 26,2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -2,75 | s -203 | s -205 | s -207 | s -210 | s -214 | s -220 | s -228 | · | · | · | · | · |
| -2,25 | s -200 | s -199 | s -199 | s -202 | s -207 | s -214 | s -226 | · | · | · | · | · |
| -1,75 | s -186 | s -184 | s -187 | s -190 | s -196 | s -201 | s -200 | · | · | · | · | · |
| -1,25 | s -184 | s -186 | s -182 | s -180 | s -179 | s -189 | s -194 | s -195 | s -197 | s -195 | · | · |
| -0,75 | s -187 | s -181 | s -178 | s -180 | s -178 | s -176 | s -172 | s -169 | s -192 | s -191 | s -191 | s -192 |
| -0,25 | s -184 | s -181 | s -181 | s -175 | s -171 | s -165 | s -161 | s -86 | S -51 | s -127 | h -0 | s -189 |
| 0,25 | s -184 | s -181 | s -178 | s -175 | s -173 | s -165 | s -129 | s -81 | S -42 | h -13 | s 10 | s 29 |
| 0,75 | s -184 | s -181 | s -178 | s -175 | s -171 | s -164 | s -121 | s -75 | S -40 | h -13 | s 9 | s 28 |
| 1,25 | · | · | · | s -175 | s -170 | s -162 | s -117 | s -71 | S -35 | h -8 | s 14 | s 32 |
| 1,75 | · | · | · | · | · | · | s -116 | s -68 | S -32 | h -5 | s 16 | s 34 |
| 2,25 | · | · | · | · | · | · | s -112 | s -65 | S -30 | h -4 | s 17 | s 34 |
| 2,75 | · | · | · | · | · | · | s -111 | s -63 | S -29 | · | · | · |

### NASA VIPER — `heater_model=thermostat_assumed`

heat1d: enlem -88,9205°, eğimler [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0, 30.0], 235 159 örnek, 205/288 kutu örneklendi, yüzey -232,4…44,5 °C, Güneş yüksekliği -2,62…2,60°, 233,3 s.

Kararlar: **sınırsız 192**, soğuk-sınırlı 0, sıcak-sınırlı 13, örneklenmedi 83. En sıcak yüzey 44,5 °C; 'sıcak-sınırlı' kutuların yüzeyi -23,5…-0,4 °C — hepsi 0 °C altı: ofset modelinin soğuk dalı (+60 K) bu bandı 35 °C üstüne atar; gerçek sıcak dal (yüzey ≥ 40 °C) hiçbir kutuda yok.

Kutu harfi: S sınırsız, s soğuk-sınırlı, h sıcak-sınırlı, · örneklenmedi; sayı kutunun maks yüzey sıcaklığı (°C); s_par sütunlarının her ikincisi.

| yükseklik \ s_par (°) | -28,8 | -23,8 | -18,8 | -13,8 | -8,8 | -3,8 | 1,2 | 6,2 | 11,2 | 16,2 | 21,2 | 26,2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| -2,75 | S -203 | S -205 | S -207 | S -210 | S -214 | S -220 | S -228 | · | · | · | · | · |
| -2,25 | S -200 | S -199 | S -199 | S -202 | S -207 | S -214 | S -226 | · | · | · | · | · |
| -1,75 | S -186 | S -184 | S -187 | S -190 | S -196 | S -201 | S -200 | · | · | · | · | · |
| -1,25 | S -184 | S -186 | S -182 | S -180 | S -179 | S -189 | S -194 | S -195 | S -197 | S -195 | · | · |
| -0,75 | S -187 | S -181 | S -178 | S -180 | S -178 | S -176 | S -172 | S -169 | S -192 | S -191 | S -191 | S -192 |
| -0,25 | S -184 | S -181 | S -181 | S -175 | S -171 | S -165 | S -161 | S -86 | S -51 | S -127 | h -0 | S -189 |
| 0,25 | S -184 | S -181 | S -178 | S -175 | S -173 | S -165 | S -129 | S -81 | S -42 | h -13 | S 10 | S 29 |
| 0,75 | S -184 | S -181 | S -178 | S -175 | S -171 | S -164 | S -121 | S -75 | S -40 | h -13 | S 9 | S 28 |
| 1,25 | · | · | · | S -175 | S -170 | S -162 | S -117 | S -71 | S -35 | h -8 | S 14 | S 32 |
| 1,75 | · | · | · | · | · | · | S -116 | S -68 | S -32 | h -5 | S 16 | S 34 |
| 2,25 | · | · | · | · | · | · | S -112 | S -65 | S -30 | h -4 | S 17 | S 34 |
| 2,75 | · | · | · | · | · | · | S -111 | S -63 | S -29 | · | · | · |

## 2. Site11'de denge iç sıcaklığı ve D3'ün bulgusu dinamikle

Geçilebilir 210 063 ince hücre; yüzey tepe -146,4…28,2 °C (medyan -47,2), soğuk uç -150,0…-28,0 °C (medyan -96,0).

| Rover | Zarf (°C) | τ (s) | T₀ | İç @tepe min / med / maks | Zarf içi @tepe | Zarf içi @soğuk uç | PSR tabanına dwell | Dwell @tepe medyan / sınırsız | 10 h bekleme > dwell (@soğuk uç) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LPR-1 (Varsayilan) | [0, 35] (battery) | 7 200 | 17,5 | -86,4 / 1,9 / 59,0 | 33,6 % (soğuk 48,9 %, sıcak 17,6 %) | 10,4 % | 15,9 dk | 1,22 h / 33,6 % | 89,5 % |
| NASA VIPER | [0, 35] (battery) | 8 000 | 17,5 | -86,4 / 1,9 / 59,0 | 33,6 % (soğuk 48,9 %, sıcak 17,6 %) | 10,4 % | 17,7 dk | 1,35 h / 33,6 % | 89,5 % |
| LUVMI-M | [-100, 0] (battery) | yok | -50,0 | -146,4 / -47,2 / 28,2 | 83,0 % (soğuk 9,2 %, sıcak 7,8 %) | 55,2 % | — | — | — |

Okuma: D3 statik katmanla LP-R04/R05'i her rotada ihlal buldu (VIPER 30 May 2027 elektronik −7,96 °C, batarya −27,96 °C; LPR-1 28 Eyl 2026 −17,96 / −27,96 °C — D3 raporundan). Dinamikle soru "ne kadar sonra" olur: aşağıdaki tablo standart rotalarda iç sıcaklığın rota boyunca entegrasyonunu verir (başlangıç T₀ nominal, hedef varılan bloğun yüzeyi).

| Rota | Hamle / varış / durum | İç min / maks (°C) | İlk zarf çıkışı | Zarf dışı durum | Varışta iç (°C) | D3 ρ (statik) R04 / R05; R12 (dwell marjı, h) |
| --- | --- | --- | --- | --- | --- | --- |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 41 / 2,979 h / 42 | -15,66 / 17,50 | 0,666 h (cold, battery) | 34 / 42 | -10,90 | R04 -17,96 / R05 -27,96 / R12 0,31 |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 116 / 6,749 h / 117 | -115,87 / 17,50 | 0,530 h (cold, battery) | 109 / 117 | -115,87 | R04 -53,20 / R05 -63,20 / R12 0,27 |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 8 / 2,235 h / 9 | -49,51 / 17,50 | 0,697 h (cold, battery) | 7 / 9 | -49,51 | R04 9,23 / R05 -5,77 / R12 0,32 |

## 3. max_dwell küpü: üç rota, dilim 0

| Rota | Dilim | Durum (t₀ × blok) | Küp süresi | Blok | Sınırsız | Soğuk-sınırlı | Sıcak-sınırlı | Sonlu dwell medyanı | B1'in 10 h beklemesi > dwell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | 120 × 0,0359 h | 937 500 | 1 263 ms | 11 402 | 3,2 % | 96,0 % | 0,8 % | 0,547 h (p5 0,395, p95 0,826) | 100,0 % (12 h katman, 0,4 s) |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | 270 × 0,0359 h | 843 750 | 1 098 ms | 11 402 | 0,0 % | 100,0 % | 0,0 % | 0,547 h (p5 0,395, p95 0,777) | 100,0 % (12 h katman, 0,8 s) |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | 43 × 0,1176 h | 671 875 | 942 ms | 10 314 | 17,2 % | 73,2 % | 9,5 % | 0,622 h (p5 0,434, p95 3,519) | 84,1 % (12 h katman, 1,3 s) |

Okuma: 'sınırsız' = hedef iç sıcaklık zarf içinde (ufuk boyunca çıkmıyor); soğuk-sınırlı = gölge/soğuk yüzey; sıcak-sınırlı = ofset modelinin −25…0 °C yüzey bandı. Son sütun B1'in 10 saatlik arıza beklemesinin (varsayım) termal olarak dayanılamayacak blok kesridir — B1'in DP'sine bağlanmadı (B1 spec'i), yalnız sayı verildi.

## 4. Kısıt: `require_thermal_dwell` iki ısıtıcı modelinde

| Rota | Mod | HTTP | Hamle / bekleme | Varış | Min / son SOC | Termal ret | Düğüm / süre | Rota iç min ya da 404 gerekçesi |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | kısıtsız (rapor) | 200 | 41 / 0 | 2,979 h | 92,5 / 92,6 % | 0 | 31 219 / 6,6 s | -15,7 °C |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | kısıt, `none` | 404 | — | — | — | — | 57,5 s | 229435 transitions were refused because LPR-1 (Varsayilan)'s inner temperature would leave its [0, 35] C envelope (heater_model none, start 17.5 C, tau 7200 s); at the first slice 3 percent of the passable blocks allow a |
| LPR-1 gündüz, 28 Eyl 2026, (358,494)→(206,426) | kısıt, `thermostat_assumed` | 200 | 41 / 0 | 2,979 h | 92,5 / 92,6 % | 0 | 35 848 / 10,4 s | 5,1 °C |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | kısıtsız (rapor) | 200 | 116 / 0 | 6,749 h | 67,4 / 67,4 % | 0 | 171 117 / 58,1 s | -115,9 °C |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | kısıt, `none` | 404 | — | — | — | — | 28,5 s | 3014 transitions were refused because LPR-1 (Varsayilan)'s inner temperature would leave its [0, 35] C envelope (heater_model none, start 17.5 C, tau 7200 s); at the first slice 0 percent of the passable blocks allow an  |
| LPR-1 Ay gecesi, 13 Eyl 2026, (186,34)→(494,450) | kısıt, `thermostat_assumed` | 200 | 116 / 0 | 6,749 h | 67,4 / 67,4 % | 0 | 171 117 / 67,3 s | 0,6 °C |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | kısıtsız (rapor) | 200 | 8 / 0 | 2,235 h | 72,3 / 72,3 % | 0 | 1 635 / 0,7 s | -49,5 °C |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | kısıt, `none` | 404 | — | — | — | — | 14,3 s | 303 transitions were refused because NASA VIPER's inner temperature would leave its [0, 35] C envelope (heater_model none, start 17.5 C, tau 8000 s); at the first slice 17 percent of the passable blocks allow an unlimite |
| VIPER kısa leg, 30 May 2027, (358,494)→(346,462) | kısıt, `thermostat_assumed` | 200 | 8 / 0 | 2,235 h | 72,3 / 72,3 % | 0 | 1 635 / 0,9 s | 6,4 °C |

Okuma: kısıt iç sıcaklığın **kendisini** etiket ekseni olarak taşır (kalış süresini değil): ilk sürümdeki 'kalış ≤ dwell' kuralını planlayıcı iki karanlık blok arasında ileri-geri hamleyle boşa çıkarıyordu (testte bulundu); gölgede kıpırdanmak da soğutur. `none` altında Site11'de rota gölgeden geçiyorsa çeyrek saat mertebesinde çıkış kaçınılmazdır; `thermostat_assumed` soğuk yanı ısıtıcıya bırakır (VARSAYIM) ve yalnız sıcak yan kalır.

## 5. Saplanma geri sayımı (`/api/replan`, `state.entrenched_hours`)

Okuma: iki geri sayım vardır — bloğun **termal** dwell'i (bu özellik) ve JSC'nin tanımı olan **haven penceresi** (A4 Dünya bağlantısı − A1 en yakın haven'a sürüş). A1'in bulgusu gereği LPR-1'in Site11'de **hiçbir epokta ulaşılabilir haven'ı yok** (Ay gecesi başlangıcında Dünya bağlantısı da yok): haven bütçesi 0 h, yani JSC'nin saati saplanmadan önce dolmuş sayılır ve `overall` her saplanma süresinde **fail** verir. Termal sütun tek başına okunmalı: 0,1 h → ok, 0,25 h → warning (bütçenin ~%50'si), 0,5 h → fail. Seviye eşikleri (%50/%80/%100) bizim seçimimizdir.

### Ay gecesi başlangıcı — piksel (186, 34), 2026-09-13T00:00:00

Gölge serisi: spice_horizon.

| Saplanma | Termal bütçe | Termal kalan | Haven penceresi | Seviye (sınırlayıcı) | Replan | Ateşleyen | Süre |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0,10 h | 0,485 h (cold/battery) | 0,385 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 5,04 s |
| 0,25 h | 0,485 h (cold/battery) | 0,235 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 5,14 s |
| 0,50 h | 0,485 h (cold/battery) | -0,015 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 5,11 s |
| 1,00 h | 0,485 h (cold/battery) | -0,515 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 5,07 s |

### Ay gecesi rota ortası (durum #58, dilim 105) — piksel (390, 230), 2026-09-13T03:46:09

Gölge serisi: spice_horizon.

| Saplanma | Termal bütçe | Termal kalan | Haven penceresi | Seviye (sınırlayıcı) | Replan | Ateşleyen | Süre |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0,10 h | 0,420 h (cold/battery) | 0,320 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 15,38 s |
| 0,25 h | 0,420 h (cold/battery) | 0,170 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 2,01 s |
| 0,50 h | 0,420 h (cold/battery) | -0,080 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 2,07 s |
| 1,00 h | 0,420 h (cold/battery) | -0,580 h | 0,00 h (Dünya 0,0 h − haven — h) | **fail** (haven) | evet | comm_window, entrenchment | 2,29 s |

### LPR-1 gündüz başlangıcı — piksel (358, 494), 2026-09-28T00:00:00

Gölge serisi: spice_horizon.

| Saplanma | Termal bütçe | Termal kalan | Haven penceresi | Seviye (sınırlayıcı) | Replan | Ateşleyen | Süre |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0,10 h | 0,486 h (cold/battery) | 0,386 h | 0,00 h (Dünya 234,0 h − haven — h) | **fail** (haven) | evet | entrenchment | 1,53 s |
| 0,25 h | 0,486 h (cold/battery) | 0,236 h | 0,00 h (Dünya 234,0 h − haven — h) | **fail** (haven) | evet | entrenchment | 1,50 s |
| 0,50 h | 0,486 h (cold/battery) | -0,014 h | 0,00 h (Dünya 234,0 h − haven — h) | **fail** (haven) | evet | entrenchment | 1,45 s |
| 1,00 h | 0,486 h (cold/battery) | -0,514 h | 0,00 h (Dünya 234,0 h − haven — h) | **fail** (haven) | evet | entrenchment | 1,34 s |

## 6. İddia sınırı ve sunum cümlesi

- **İddia:** MODEL, uncalibrated: the surface temperature is heat1d's (slope x aspect) annual peak coupled to the SPICE shadow series with an UNCALIBRATED regolith lag, and the inner temperature is the catalogue's piecewise offset model relaxed with the catalogue's thermal_tau_s; no Diviner comparison is made here (C5). The offsets are piecewise on the surface sign, so the surfaces that map into the LPR-1/VIPER battery envelope are -60..-25 C (cold branch) and 40..75 C (hot branch): a 'hot-limited' verdict on a -25..0 C surface is that offset model, not overheating. The heater has no sourced W-to-K link; heater_model='thermostat_assumed' is an explicit assumption and the default is 'none'. The dwell cube assumes the rover arrives at its nominal inner temperature; the route trace integrates the actual one. JSC's envelope axes (slope x Sun azimuth relative to the rover heading, at the mission's maximum Sun elevation) need a rover body model LunaPath does not have; ours are Sun elevation x Sun-parallel slope from heat1d's transient -- the same method on our model, not a comparison. JSC's numbers are quoted, never mixed with a measurement.
- **Kapsam:** inner temperature = first-order lag with the rover's thermal_tau_s toward surface_to_inner(surface(t)); surface(t) = the cost cube's per-slice regolith state (shadowed equilibrium relaxed with the regolith constant); envelope = the tightest declared battery/electronics operating range; max_dwell_h[t, y, x] = the time that lag takes to leave the envelope when the rover arrives at slice t with the nominal (or given) inner temperature; the heater enters the temperature model only under heater_model='thermostat_assumed'.
- **Doğru cümle:** "NASA JSC'nin VIPER için kullandığı iki çerçeveyi — sınırsız operasyon zarfı ve tolere edilebilir saplanma süresi — LunaPath'in kendi termal modeliyle kurduk: heat1d transient'inden Güneş yüksekliği × Güneş'e paralel eğim zarfı, rover kataloğunun zaman sabitiyle iç sıcaklık dinamiği, her blok için max_dwell, planlayıcıda zarf dışına çıkan geçişleri reddeden kısıt, saplanma anından itibaren termal + haven geri sayımı (warning/critical/fail). Model kalibre edilmemiş; ısıtıcı yalnız etiketli varsayımla girer; JSC'nin sayıları alıntı."
- **Yanlış cümle:** "VIPER'ın termal zarfını yeniden ürettik" (rover gövdesi yok, Thermal Desktop yok, 60+ bileşen yok) ya da "iç sıcaklık tahminimiz doğrulandı" (Diviner karşılaştırması yok; C5).

