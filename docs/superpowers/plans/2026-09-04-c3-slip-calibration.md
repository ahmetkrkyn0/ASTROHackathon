# C3 — Slip kalibrasyonu (Yutu-2 / VIPER çapaları, tek noktadan bağlama) — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** `slip_model.py`'nin "UNCALIBRATED" etiketini kaynaklı çapalarla (VIPER PSJ 2025
15°/%40 tasarım kısıtı; Yutu-2 Nat. Comms 2024 ölçülmüş 0…−0,075, ≤ 8,86°) `"MODEL"`
etiketine taşımak; eğriyi **tek noktadan** (`cost_engine.edge_travel_time_s`, `d → d/(1−s)`)
süre ve enerjiye bağlayıp planlayıcı / simülatör / koridor / Monte Carlo / safe-haven /
koridor dilimleri arasında bit-düzeyi tutarlılığı korumak; `(μ, σ)` kancasını (B2) vermek;
katalog, `/api/rovers`, `/api/plan`, `/api/plan-4d`, `/api/compare` yanıtlarına slip
bloklarını eklemek; standart rotalarda önce/sonra ölçmek.

**Architecture:** `slip_model.py` çapalardan parçalı log-doğrusal eğri derler (skaler +
vektörize, aynı işlem sırası → bit-eşit); `cost_engine.edge_travel_time_s` slip'i tek
noktadan uygular ve `edge_travel_time_s_array` vektörize eşi olur; `safe_haven._gated_edges`
ve `illumination_corridor.edge_tables` vektörize fonksiyonu kullanır; `main.plan_4d`
varsayılan ufku en kısa **süreli** rota (Dijkstra) ile boyutlar; `constants.ROVERS`
`slip_curve` + `regolith` alır; API yalnızca ekleme yapar.

**Spec:** [2026-09-04-c3-slip-calibration-design.md](../specs/2026-09-04-c3-slip-calibration-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, SciPy 1.15 (`sparse.csgraph.dijkstra`), FastAPI/pydantic, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit mesajında
eş-yazar satırı yok.

---

## Global Constraints

- Etiket `SLIP_MODEL_VALIDITY = "MODEL"`; `"MEASURED"` hiçbir yerde kullanılmaz; her yanıt
  bloğunda `claim` ("literature-anchored MODEL, not a measurement …").
- Kaynağı olmayan çapa yok: `SlipAnchor.source` boş olamaz; aktarılanlar `"assumption: "`
  ile başlar ve `kind == "assumption"`.
- Bağlama tek noktadan: yalnızca `edge_travel_time_s` (ve vektörize eşi) slip okur; enerji
  fonksiyonları süre üzerinden miras alır. Planlayıcının satır içi drain aritmetiği,
  `_gated_edges`, `edge_tables`, `auto_slice_hours` ile mevcut birebirlik testleri geçmeli.
- `MAX_SLIP_RATIO = 0.9` (mevcut kap), işaret simetrisi `|θ|`, ilk çapa 0°.
- Eğrisiz rover (`slip_curve` yok/`None`) → slip 0, `applied: false`; sessiz varsayılan yok.
- `COST_MODEL_ID` → `"weighted_cell_cost_shadow_aware_energy_slip_v4"`.
- Mevcut API alanları aynen; yalnızca ekleme (`slip_model` blokları, `/api/rovers`
  `slip_model`, `declared_only.regolith`).
- Sayı uydurma yok: rapor Site11'de koşar; gerçek grid testleri skip-korumalı; çekirdeksiz
  klonda diğer tüm testler koşar. TDD: her görevde önce başarısız test. `inf`/`NaN` JSON'a sızmaz.
- Frontend koduna dokunulmaz.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/slip_model.py` | `SlipAnchor`, `SlipCurve`, `compile_curve`, `curve_for`, `slip_ratio`, `slip_ratio_array`, `slip_stats`, `effective_distance_m`, `slip_energy_multiplier`, `curve_table`, `rover_slip_block`, `route_slip_summary`, `thermal_inertia_slip_scale`, sabitler (`SLIP_MODEL_VALIDITY`, `SLIP_MODEL_ID`, `MAX_SLIP_RATIO`, `SLIP_CLAIM`, `SLIP_REFERENCES`), `check_slip_accumulation` (aynen) |
| `backend/app/constants.py` | Çapa sabitleri, `_transferred`, `ROVERS[*]["slip_curve"]`, `ROVERS[*]["regolith"]`, `MODELLED_FIELDS` += `slip_curve`, `DECLARED_ONLY_FIELDS` += `regolith`, `rover_catalog()` `slip_model` |
| `backend/app/cost_engine.py` | `edge_travel_time_s` slip; `edge_travel_time_s_array`; `COST_MODEL_ID` v4; docstring'ler |
| `backend/app/safe_haven.py` | `_gated_edges` vektörize süre; `gated_shortest_drive` |
| `backend/app/illumination_corridor.py` | `edge_tables` dilimleri `_gated_edges` saatlerinden |
| `backend/app/main.py` | Varsayılan ufuk (`gated_shortest_drive`); `slip_model` blokları (`plan`, `plan_4d`, `_attach_constraint_check`); `_slip_block_2d` / `_slip_block_4d` yardımcıları |
| `backend/test_slip_model.py` | Yeniden yazılır: eğri, parite, `(μ, σ)`, blok/özet, kanca, tetikleyici |
| `backend/test_cost_engine.py`, `backend/test_safe_haven.py`, `backend/test_illumination_corridor.py`, `backend/test_cost_cube.py` | Eklemeler: vektörize parite, `gated_shortest_drive`, dilim uzaması |
| `backend/test_rover_validation.py`, `backend/test_review3_fixes.py` | Katalog çapa/kaynak/regolit doğrulaması |
| `backend/test_plan_endpoint.py`, `backend/test_plan_4d_endpoint.py`, `backend/test_multi_plan.py` (varsa) | API blokları |
| `backend/test_slip_calibration_real_grid.py` | Skip-korumalı gerçek grid önce/sonra |
| `scripts/slip_calibration_report.py` → `docs/research/slip_calibration_report.md` | Rapor |
| `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec, `README.md` | Belgeler |

---

## Görevler

### Task 0 — Sondalar (yapıldı, spec'te)
- [x] Standart rotalar bugünkü haliyle (`scratch/before.json`): VIPER 7,36 h / SOC %32,1 / B5 %29,6; LPR-1 2,16 h / %96,2 / %100; Ay gecesi 246 dilim, 5,35 h. Site11 ince eğim medyanı ~10°, kaba blok p95 19–22°.
- [x] Eğri adayları ve platform bit-paritesi (`np.exp/cos/log == math.*`, 0 ulp).

### Task 1 — `slip_model.py`: çapalar, eğri, parite, `(μ, σ)`
- [x] `test_slip_model.py` yeniden yaz: `_anchors()` yardımcı (0°/0,0375/σ 0,01875 measured; 15°/0,40/σ 0,20 design_constraint) ve `_rover()` = `dict(get_rover("nasa_viper"))`. Testler: `compile_curve` çapalardan geçer (`slip_ratio(15) == approx(0.40, rel=1e-9)`, `slip_ratio(0) == 0.0375`); `range(0, 31)` monoton artan; `slip_ratio(-15) == slip_ratio(15)`; `slip_ratio(60) == MAX_SLIP_RATIO` ve `slip_ratio(1000) <= MAX`; 3 çapalı (0 / 8,86 / 15) eğri orta çapadan geçer ve 8,86 → 15 arası üstel (`slip_ratio(11.93) == approx(sqrt(0.075*0.40))` — log-orta nokta); ilk çapa 0° değil / eğim artmıyor / `slip >= 0.9` / boş `source` / tek çapa / azalan slip → `ValueError`; `curve_for({"slip_curve": None})` `None` ve `slip_ratio(10, {"slip_curve": None}) == 0.0`; `rover=None` varsayılan rover'ın eğrisi; `slip_ratio_array` 200 000 rastgele `[0, 90)` + çapa noktaları + 20 → `np.array_equal([slip_ratio(x)])` her katalog rover'ı için; `slip_stats(0) == (0.0375, 0.01875)`, `slip_stats(15) == (0.40, 0.20)`, 7,5°'de rel σ = (0,5+0,5)/2 = 0,5 → σ = 0,5·μ; `effective_distance_m(100, 10, rover) == 100/(1−slip_ratio(10, rover))`; `slip_energy_multiplier == effective/100` (0/10/20); çarpan ≥ 1; `SLIP_MODEL_VALIDITY == "MODEL"` ve `!= "MEASURED"`, `"not a measurement" in SLIP_CLAIM.lower()`; `thermal_inertia_slip_scale(np.zeros(3))` → `NotImplementedError` mesajında "Diviner"; tetikleyici testleri aynen (etiket "MODEL" detayda).
- [x] Koştur → içe aktarma hatası / başarısız.
- [x] `slip_model.py` yaz (spec "Bileşenler"): `SlipAnchor` (frozen dataclass; `as_dict`), `SlipCurve`, `compile_curve` (doğrulama + `_COMPILED` `id`-önbelleği `{id: (anchors, curve)}` `is` kontrollü), `curve_for`, `slip_ratio`, `slip_ratio_array`, `slip_stats`, `effective_distance_m`, `slip_energy_multiplier`, sabitler, `thermal_inertia_slip_scale`. Modül docstring'i: ne uygulandı, iddia sınırı, termal atalet notu.
- [x] Koştur → geçer.

### Task 2 — Katalog: çapalar, regolit, `rover_catalog` bloğu
- [x] `test_rover_validation.py` ekle: her `ROVERS` girdisi `slip_curve` tuple, ≥ 2 `SlipAnchor`, ilk 0°, `compile_curve` hatasız; `nasa_viper` çapaları arasında `slope_deg == 15 and slip == 0.40 and kind == "design_constraint" and "PSJ" in source`; `cnsa_yutu_2` ≥ 2 `kind.startswith("measured")` çapa ve `8.86` eğimli çapa `slip == 0.075`; `lpr_1`/`luvmi_m` tüm çapalar `kind == "assumption"` ve `source.startswith("assumption:")`; her rover'da en az bir çapa "Yutu-2" ve bir çapa "VIPER" geçiyor; `"slip_curve" in MODELLED_FIELDS`, `"regolith" in DECLARED_ONLY_FIELDS`; `ROVERS["cnsa_yutu_2"]["regolith"]` = friction 21,5–42,0, cohesion 520–3154, N 0,87–1,0, sinkage 8 (5–15), bearing 4 kPa, `validity` "MEASURED" içerir ve "polar" değil; `nasa_viper` regolith `simulant == "GRC-1"`, relative density 15–20; `lpr_1` `regolith is None`; `rover_catalog()` girdilerinde `slip_model.validity == "MODEL"`, `len(table) == 6`, `table[0]["slope_deg"] == 0`, `table[3]["slip"] == approx(0.40)` (VIPER), `time_energy_factor == approx(1/(1−slip))`, `within_slope_limit` VIPER'da 25°'de `False`; `json.dumps(catalog, allow_nan=False)` geçer; `test_review3_fixes::test_m8_*` geçmeye devam eder.
- [x] Koştur → başarısız.
- [x] `constants.py`: `from .slip_model import SlipAnchor`; `SLIP_ANCHOR_YUTU2_FLAT`, `SLIP_ANCHOR_YUTU2_STEEPEST`, `SLIP_ANCHOR_VIPER_15`, `_transferred(anchor, note)`; `ROVERS[*]["slip_curve"]`, `["regolith"]`; set güncellemeleri; `rover_catalog()` `"slip_model": rover_slip_block(rover)`. `slip_model.py`'ye `curve_table`, `rover_slip_block` (constants'ı içe aktarmaz; `SLIP_REFERENCES` sabit).
  Dairesel içe aktarma: `slip_model` `constants`'ı **içe aktarmaz** (`slip_ratio(rover=None)` `constants.get_rover`'ı fonksiyon içinde geç içe aktarır).
- [x] Koştur → geçer; `test_review3_fixes.py`, `test_plan_endpoint.py::test_rovers_returns_catalog` geçer.

### Task 3 — `cost_engine`: tek noktadan bağlama, vektörize eş, `COST_MODEL_ID`
- [x] `test_cost_engine.py` (pytest biçiminde ek bölüm, dosyanın mevcut `check` kalıbını bozmadan en sona): `edge_travel_time_s(10, 320, viper) == approx(320/cos(10°)/(1−slip_ratio(10, viper))/(0.06·cos(10°)))`; eğrisiz rover (`dict(get_rover()); r["slip_curve"] = None`) için slip'siz formül birebir; `edge_travel_time_s_array(np.array([0, 5, 10, 15, 20, 25]), 320.0, viper)` her elemanı skaler ile `np.array_equal` (bit-eşit) — 4 rover × 100 000 rastgele eğim `[0, 89]` ve rastgele mesafe; `theta ≥ 90` → `inf` iki yolda; `edge_energy_wh(10, 100, viper) == approx(edge_energy_wh_slip_free · 1/(1−s))` (eğrisiz kopya ile oran); `move_battery_drain_wh` aynı oranla büyür (gölge 0, güneş 0 olan kopya); `COST_MODEL_ID.endswith("slip_v4")`; `f_energy_cell(0, viper) == 0` ve `f_energy_cell(slope_max, viper, 1.0) == 1` (normalizasyon korunur).
- [x] Koştur → başarısız.
- [x] `cost_engine.py`: içe aktarma `from .slip_model import slip_ratio, slip_ratio_array` (slip_model `cost_engine`'i içe aktarmaz — `route_slip_summary` süre/enerjiyi parametre alır); `edge_travel_time_s` yeni gövde; `edge_travel_time_s_array`; `COST_MODEL_ID`; docstring güncellemeleri (`edge_energy_wh`: "distance/(1−slip) correction enters through edge_travel_time_s (C3)").
- [x] Koştur → geçer. `test_slip_model.py`, `test_simulation.py`, `test_review3_fixes.py`, `test_corridor.py`, `test_stress_test.py`, `test_pathfinder_4d.py` koştur → geçer (satır içi ↔ fonksiyon birebirliği slip'le de tutar).

### Task 4 — `_gated_edges`, `edge_tables`, `gated_shortest_drive`, `auto_slice_hours`
- [x] `test_safe_haven.py` ekle: rastgele 9×9 gridde `_gated_edges` saatleri ↔ `edge_travel_time_s(0.5(slope[src]+slope[dst]), d, rover)/3600` **`np.array_equal`** (bit-eşit); `gated_shortest_drive(passable 1×5, elev 0, slope [0,10,20,10,0], RES, rover, (0,0), (0,4))` → `(Σ edge_travel_time_s(mean slopes)/3600, 4)`; duvar (`elevation[0,2] = 1000`) → `None`; rastgele gridde `gated_shortest_drive(...) is None` ⇔ `gated_move_count(...) is None` her (start, goal) çifti için; `moves ≥ gated_move_count`.
- [x] `test_illumination_corridor.py`: mevcut ceil testi kalır; yeni: `edge_tables` dilimleri ↔ `np.maximum(1, ceil(_gated_edges hours / slice))` rastgele gridde birebir.
- [x] `test_cost_cube.py` ekle: `auto_slice_hours` slip'li rover > eğrisiz kopya (aynı grid), oran `== approx(1/(1−slip_ratio(median, rover)))`.
- [x] Koştur → başarısız.
- [x] `safe_haven.py`: `_gated_edges` `edge_travel_time_s_array`; `gated_shortest_drive` (csgraph `dijkstra(graph, directed=False, indices=[start], return_predecessors=True)`; `distances[goal]` sonlu değilse `None`; hamle sayısı predecessor zincirinden). `illumination_corridor.edge_tables`: `_hours` kullan, docstring güncelle.
- [x] Koştur → geçer; `test_illumination_corridor.py`, `test_safe_haven.py`, `test_cost_cube.py` tam geçer.

### Task 5 — `route_slip_summary`, API blokları, varsayılan ufuk
- [x] `test_slip_model.py` ekle: `route_slip_summary([(0, 320, 1.0, 100.0), (15, 452.5, 2.0, 300.0)], viper)` → `moves 2`, `mean_slip == (320·s0 + 452.5·s15)/772.5`, `max_slip == s15`, `max_slip_slope_deg == 15`, `distance_factor == (320/(1−s0)+452.5/(1−s15))/772.5`, `extra_hours == 1.0·s0 + 2.0·s15`, `extra_drawn_wh == 100·s0 + 300·s15`, `applied True`; `drawn None` içeren kenar → `extra_drawn_wh None`; `inf` saatli kenar atlanır (`skipped_edges 1`); boş → sıfırlar, `applied` eğriye göre; eğrisiz rover → `applied False`, `validity None`.
- [x] `test_plan_4d_endpoint.py` ekle: yanıtta `slip_model.applied is True`, `route.moves == metrics.move_steps`, `extra_hours > 0`, `mean_slip == approx(slip_ratio(3.0, rover), rel=1e-6)` (düz 3° fixture), `json` `NaN`'sız; varsayılan ufuk (`n_slices`/`slice_hours` verilmeden): `n_slices >= ceil(arrival)` ve `n_slices <= moves_min + ceil(hours_min/slice) + 20 + 1` (`gated_shortest_drive` ile hesaplanıp karşılaştırılır); `horizon_hours == n_slices·slice_hours`.
- [x] `test_plan_endpoint.py` ekle (mevcut `check` kalıbı): `/api/plan` yanıtında `slip_model` (`applied`, `route.moves == waypoint_count − 1`, `extra_hours ≥ 0`); `/api/compare` her `results[*]` girdisinde `slip_model`.
- [x] Koştur → başarısız.
- [x] `slip_model.route_slip_summary`; `main.py`: `_slip_block_2d(states, rover)` (adım i>0: `drive = max(slope_deg, segment_slope_deg)`, `d = distance_m[i]−distance_m[i−1]`, `h = elapsed[i]−elapsed[i−1]` — dikkat: şarj duraklarını dışla → `simulate_path`'in `step_time_h`'ı `RoverState`'te yok; `h = edge_travel_time_s(drive, d, rover)/3600` ile yeniden hesapla; `drawn = step_energy_wh`), `_slip_block_4d(result, geometry, shadow_cube, rover)` (hamle: `edge_slope` trapez, `d`, `h = edge_travel_time_s/3600`, `drawn = gross_energy_per_metre_wh(edge_slope, mean_exposure)·d`); `plan` / `plan_4d` / `_attach_constraint_check` bloğu ekler; varsayılan ufuk `gated_shortest_drive` ile (`None` olamaz: `move_count` zaten bağlantıyı doğruladı; savunma amaçlı eski formüle düş).
- [x] Koştur → geçer; `test_plan_endpoint.py`, `test_plan_4d_endpoint.py`, `test_multi_plan*.py`/compare testleri geçer.

### Task 6 — Gerçek grid testi ve rapor
- [x] `test_slip_calibration_real_grid.py` (skip: `metadata.json` + `horizon_map.npy` + çekirdek): VIPER standart rota (`require_safe_haven`) ve LPR-1 rotası → 200, `slip_model.applied`, `route.extra_hours > 0`, `n_slices <= MAX_PLAN_4D_SLICES`; aynı süreçte `monkeypatch.setitem(ROVERS[rid], "slip_curve", None)` + grid yeniden yükleme ile slip'siz koşum → `arrival_hours` slip'li > slip'siz; Ay gecesi rotası varsayılan ufukla 200; toplam < 180 s.
- [x] Koştur → geçer (sayıları oku).
- [x] `scripts/slip_calibration_report.py` → `docs/research/slip_calibration_report.md`: (1) çapalar/kaynaklar tablosu; (2) rover başına eğri tablosu 0/5/10/15/20/25° (`slip`, `σ`, çarpan); (3) standart rotalar önce/sonra (4-B: dilim × saat, hamle/bekleme, varış, en düşük SOC, LP-R01/R02/R06/R07, B5 tamamlanma/tam başarı/nominal min SOC; 2-B: mesafe, süre, tüketim, min SOC; `slip_model.route`); (4) varsayılan ufuk eski formül (sonda) ↔ yeni; (5) planlama süreleri; (6) okuma + sunum cümlesi + iddia sınırı. "Önce" = `ROVERS[*]["slip_curve"] = None` yaması + `load_preprocessed_grids()` yeniden. Koştur, sayıları oku.

### Task 7 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` C3 eki ("## Değişmeyenler" öncesi): `/api/rovers.slip_model` tablo, `declared_only.regolith`, plan yanıtlarının `slip_model` bloğu, ölçülen örnek, iddia sınırı.
- [x] Araştırma belgesinde C3 başlığına ✅ + "Yapıldı" blok alıntısı; README satırı (51. satırdaki UNCALIBRATED cümlesi güncellenir + Veri bölümüne rapor satırı).
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler" (önce/sonra tablosu, sapmalar, test sayıları).
- [x] Tam paket `cd backend && python -m pytest` (arka planda); ruff yeni dosyalarda; tek commit (eş-yazar satırı yok); hafıza dosyası (C3 yapıldı + hash, sıradaki B2).
