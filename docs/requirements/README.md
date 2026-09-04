# LunaPath güvenlik gereksinimleri — FRETISH + STL (D3)

`lunapath.fret.json` LunaPath'in 11 güvenlik/görev gereksinimini NASA FRET'in
yapılandırılmış doğal dili **FRETISH** kalıbında, her birinin elle yazılmış
zamansal-mantık çevirisiyle (ftLTL + STL) ve hangi sinyalle, hangi birimde,
hangi rover parametresine karşı denetlendiğiyle taşır. Dosya
`backend/app/safety_monitor.py` içindeki katalogdan üretilir:

```bash
python scripts/export_fret_requirements.py
```

`backend/test_safety_monitor.py::test_checked_in_fret_file_matches_the_catalogue`
dosya ile katalog ayrıştığında başarısız olur; belge kodla sürüklenemez.

## Ne söylenir, ne söylenmez

- **Doğru:** "Gereksinimler FRETISH kalıbında yazıldı, STL'e elle çevrildi ve
  her planlanan rota bu gereksinimlere karşı **çalışma-zamanı izleme**
  (RTAMT 0.3.5 + yerleşik değerlendirici, her istekte çapraz kontrol) ile
  **nicel marjla** denetleniyor."
- **Yanlış:** "FRET aracıyla üretildi" (araç kurulmadı; cümleler FRET'in
  gramerine göre elle yazıldı) ve "model checking ile ispatlandı" (yalnızca
  somut izler denetleniyor; hiçbir sonuç tüm izler için bir ispat değildir).

Her API yanıtı bu sınırı `safety_margins.monitor.claim` alanında tekrar eder.

## FRETISH grameri (Giannakopoulou vd. 2020)

```
[scope] [condition] component shall [timing] [response]
```

| Parça | Kullanılan değerler | Zamansal karşılık |
|---|---|---|
| scope | `In moving mode`, `In at_goal mode` (yoksa küresel) | `G (mode → …)` — monitörde örnek maskesi |
| condition | `upon soc_pct < soc_min` | `G (C → …)` |
| component | `the rover` | — |
| timing | `always`, `eventually`, `within 6 hours` | `G`, `F`, `F[0,6h]` |
| response | `x <= limit`, `lo <= x <= hi`, `charging`, `at_goal` | atom / atom birleşimi |

## Robustness

Ayrık-zaman **uzamsal robustness** (Donzé & Maler 2010; RTAMT'nin offline
semantiği): `ρ(x ≥ c) = x − c`, `¬` işaret değiştirir, `∧`/`∨` min/max,
`G`/`F` iz üzerinde min/max. `ρ ≥ 0` sağlandı, `ρ < 0` ihlal; `|ρ|` gereksinimin
biriminde marj ya da ihlal büyüklüğü. Pencereli davranış (gölge dayanımı,
şarj son tarihi) **türetilmiş saat sayaçlarına** gömüldüğünden her formül
sınırsız `G`/`F`'dir, ρ örnekleme adımından bağımsızdır ve birimi saattir.

## Gereksinimler

Eşikler rover kataloğundan (`backend/app/constants.py`) okunur; `soc_min` =
`soc_min_pct × 100`. Yalnızca LP-R03'ün 6 saatlik son tarihi katalog sabitidir
(`threshold_source: "catalogue"`, istekte değiştirilebilir).

| ID | FRETISH | İzlenen STL | Sinyal (birim) | Rover parametresi | VIPER / LPR-1 / LUVMI-M / Yutu-2 |
|---|---|---|---|---|---|
| LP-R01 | The rover shall always satisfy shadow_continuous_h <= h_max_shadow_h | `always (shadow_continuous_h <= H)` | kesintisiz gölge saati (h) | `h_max_shadow_h` | 96 / 50 / 4 / 2 h |
| LP-R02 | The rover shall always satisfy soc_pct >= soc_min | `always (soc_pct >= S)` | SOC (yüzde puanı) | `soc_min_pct` | 20 / 20 / 20 / 30 |
| LP-R03 | Upon soc_pct < soc_min the rover shall within 6 hours satisfy charging | `always (hours_below_reserve_h <= 6)` (ders kitabı: `G((soc<S) → F[0,6h] charging)`) | rezerv altında şarjsız saat (h) | — (katalog) | 6 h |
| LP-R04 | The rover shall always satisfy elec_op_min_c <= inner_temp_c <= elec_op_max_c | `always ((T >= lo) and (T <= hi))` | iç sıcaklık (°C) | `elec_op_min_c/max_c` | −20…50 / −10…40 / **yok** / −40…55 |
| LP-R05 | The rover shall always satisfy bat_op_min_c <= inner_temp_c <= bat_op_max_c | aynı | iç sıcaklık (°C) | `bat_op_min_c/max_c` | 0…35 / 0…35 / −100…0 / −10…30 |
| LP-R06 | The rover shall always satisfy drive_slope_deg <= slope_max_deg | `always (drive_slope_deg <= θ)` | sürüş eğimi (°) | `slope_max_deg` | 20 / 25 / 25 / 20 |
| LP-R07 | The rover shall always satisfy lateral_slope_deg <= slope_lateral_max_deg | `always (lateral_slope_deg <= θ)` | yanal eğim (°) | `slope_lateral_max_deg` | 15 / 18 / 15 / 15 |
| LP-R08 | In moving mode the rover shall always satisfy earth_visible | `always (moving → (earth_link_h > 0))` | Dünya bağlantısına kalan saat; görünmüyorsa −(hamle süresi) (h) | — | 0 |
| LP-R09 | The rover shall always satisfy time_to_haven_h <= hours_until_earthset | `always (haven_margin_h >= 0)` | haven marjı (h) | — | 0 |
| LP-R10 | The rover shall eventually satisfy at_goal | `eventually (dist_to_goal_m <= 0)` | hedefe kalan mesafe (m) | — | 0 |
| LP-R11 | In at_goal mode the rover shall always satisfy soc_pct >= soc_min | `always (at_goal → (soc_pct >= S))` | varış SOC'si (yüzde puanı) | `soc_min_pct` | 20 / 20 / 20 / 30 |

LP-R08 ve LP-R09 yalnızca zamanlı izlerde (4-B plan, telemetri) uygulanabilir;
2-B rotalarda `applicable: false`. LP-R10 görev sınıfıdır (`class: mission`) ve
"en küçük marj" sıralamasına girmez. Bir rover'ın zarfı yoksa (LUVMI-M
`elec_op_*`) gereksinim o rover için uygulanamaz olarak raporlanır; boşlukla
"sağlandı" denmez.

## Sinyaller — iz türüne göre kaynak

| Sinyal | 2-B (`/api/plan`, `/api/compare`) | 4-B (`/api/plan-4d`) | Telemetri (`/api/safety-check`, ROS) |
|---|---|---|---|
| `soc_pct` | `battery_low_pct` (şarj molası öncesi dip) | `path_battery_pct` | `soc_pct` |
| `charging` | şarj molası ∨ güneş geliri > çekiş | batarya yükseldi | `charging` ∨ SOC yükseldi |
| `shadow_continuous_h` | adım süresi × (`shadow_ratio` > 0,2), aydınlıkta sıfırlanır | `path_dark_hours` | `in_shadow` / `shadow_ratio` ile sayaç |
| `hours_below_reserve_h` | nedensel sayaç | aynı | aynı |
| `inner_temp_c` | `surface_to_inner(surface_temp_c)` | `surface_to_inner(kaba ortalama termal)` | `inner_temp_c` ya da `surface_temp_c` |
| `drive_slope_deg` | max(hücre eğimi, adım eğimi) | max(kaba maks eğim, merkez-yükseklik adım eğimi) | `slope_deg` |
| `lateral_slope_deg` | gradyan + yön (planlayıcı formülü) | aynı, kaba gridde | `lateral_slope_deg` |
| `moving` | adım > 0 | hücre değişti | `moving` |
| `earth_link_h` | — | `path_hours_until_earthset` / −süre | `earth_link_h` |
| `haven_margin_h` | — | `path_haven_margin_h` | `haven_margin_h` |
| `dist_to_goal_m` | planlanan uzunluk − katedilen | aynı | `dist_to_goal_m` |
| `at_goal` | `dist_to_goal_m ≤ 0` | son durum | `at_goal` ya da `dist ≤ 0` |

Mahsur kalan 2-B izleri (`stranded`) bir Ay günü (`simulation.MAX_RECHARGE_HOURS`)
uzatılır: simülatörün "bir Ay günü içinde şarj olamaz" kararı, monitörün
varsayımı değil.

## Dosya alanları

`requirements[]`: `reqid`, `fulltext` (FRETISH), `rationale`, `comments`,
`semantics` (`scope`, `condition`, `component`, `timing`, `response`,
`variables`, `ftLTL`, `stl`, `monitored_stl`), `monitor` (`class`, `signal`,
`unit`, `rover_parameter`, `threshold_source`, `thresholds_by_rover`,
`formula_by_rover`, `normalizer`, `trace_kinds`). Üst düzeyde `provenance`
(yöntem, iddia sınırı, kaynaklar), `recharge_deadline_h`, `rovers`.

Kaynaklar: [NASA FRET](https://github.com/NASA-SW-VnV/fret) ·
[Giannakopoulou vd. 2020](https://ntrs.nasa.gov/api/citations/20200001989/downloads/20200001989.pdf) ·
[RTAMT](https://github.com/nickovic/rtamt) · Donzé & Maler, "Robust Satisfaction
of Temporal Logic over Real-Valued Signals" (FORMATS 2010).
