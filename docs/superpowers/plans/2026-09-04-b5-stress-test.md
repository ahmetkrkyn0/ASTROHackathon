# B5 — Monte Carlo traverse stres testi — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** `/api/plan-4d` rotasını SHERPA'nın kesik Gauss dağılımları ve
"önde iken bekle, geride iken bataryayla geç" politikasıyla N kez vektörize
yürütüp başarı oranı (Wilson %95 CI), SHERPA metrik dağılımları, histogramlar
ve rota boyunca batarya/varış zarfı yayınlamak; ön koşul olarak 2-B
simülatörün sürüş enerjisini planlayıcıyla birleştirmek.

**Spec:** [2026-09-04-b5-stress-test-design.md](../specs/2026-09-04-b5-stress-test-design.md)

**Tech Stack:** Python 3.11, FastAPI, NumPy, SciPy (`stats.truncnorm`), spiceypy, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- `astar_4d`, `/api/plan-4d` alanları, `/api/plan` alanları aynen; yalnızca
  ekleme (`step_solar_wh`, `total_solar_energy_wh`) ve sürüş düşümünün net
  olması (bilinçli fizik değişikliği, spec §0).
- TDD: her görevde önce başarısız test, sonra kod.
- Çekirdeksiz temiz klonda tüm yeni testler koşar (gerçek grid testleri `skip`).
- `inf`/`NaN` JSON'a sızmaz; aynı `seed` aynı sonuç.

---

## Görevler

### Task 0 — Enerji birleştirmesi (`simulation.simulate_path`)
- [x] `test_simulation.py`: güneşli düz hücrede batarya sürerken artar (kapasitede kırpılır); tam gölgede düşüm brüt çekişe eşit; `step_solar_wh` ve `total_solar_energy_wh` alanları; mevcut brüt beklentiler net değere güncellenir.
- [x] `simulate_path`: sürüş düşümü `move_battery_drain_wh` işaretli; `RoverState.step_solar_wh`; `summarize_simulation.total_solar_energy_wh`.
- [x] `test_simulation.py`, `test_plan_endpoint*.py`, `test_review*` yeşil.

### Task 1 — Örnekleme ve Wilson
- [x] `test_stress_test.py`: `sample_perturbations` yönleri, tabanlar, `z_max`, seed tekrarı, σ = 0 nominal, kesinti pencereleri (p = 0 → nan, p = 1 → hepsi).
- [x] Test: `wilson_interval(0,10)`, `(10,10)`, `(5,10)` bilinen değerler; `(0,0)` → `(0,1)`.
- [x] `stress_test.py`: `Perturbations`, `SHERPA_DEFAULTS`, `_truncated_half_normal`, `sample_perturbations`, `wilson_interval`.

### Task 2 — Rota legleri ve gökyüzü sütunları
- [x] Test: `route_legs` doğrulama (t_0 ≠ 0, azalan t, komşu olmayan hücre, geçilmez hücre, sınır dışı) → `ValueError`; sürelerin `edge_travel_time_s` trapeziyle, çekişin `p_base·(1+μ sin θ)` ile eşitliği; WAIT legi 0 m.
- [x] Test: `RouteSky.from_cubes` (küpten sütun çıkarımı) ve `route_sky_columns` senaryolu gökyüzüyle blok ortalaması (Güneş) / VE'si (Dünya).
- [x] `stress_test.py`: `RouteLegs`, `route_legs`, `RouteSky`, `route_sky_columns`, kümülatif integral + `next_lit`/`next_dark` tabloları.

### Task 3 — Vektörize yürütme
- [x] Test: nominal koşum statik gökyüzünde `astar_4d`'nin `path_battery_pct`'siyle 1e-6 içinde (MOVE + WAIT), varış saatleri `≤ t_i·slice_hours`.
- [x] Test: tek leg elle `move_battery_drain_wh` / `wait_battery_drain_wh`; güç çarpanı yalnız çekiş+idare, hız çarpanı yalnız süre.
- [x] Test: politika — önde + varış hücresi karanlık → aydınlanana kadar bekler (≤ planlı kalkış); geride → WAIT atlanır, gölgeden geçer.
- [x] Test: başarısızlık nedenleri ve ilk-neden kuralı; `horizon_exceeded`.
- [x] Test: kesinti erteleme ve sayaçlar.
- [x] Test: marjlar (time-to-sun-shadow min/mean, DSN min, 0-SOC min, DSN olay sayısı/saati, deadline ihlali) senaryolu sütunlarda beklenen değerlerle.
- [x] `simulate_runs` + `RunResults`.

### Task 4 — Özet ve üst düzey fonksiyon
- [x] Test: `summarize_runs` — oran/CI, yüzdelikler, histogram toplamı = N, per-state uzunlukları, `null` kuralı, `nominal`, `verdict`.
- [x] Test: `stress_test_route` seed tekrarı; `n_runs = 1`.
- [x] `summarize_runs`, `stress_test_route`.

### Task 5 — Uç: `POST /api/stress-test`
- [x] `test_stress_test_api.py`: 200 şeması (statik gökyüzü), `sky_model.static`, `label` yankısı, seed tekrarı, 422 (geçersiz `path_states`, `slice_hours` yok, `n_runs` sınırı), 503 (grid yok).
- [x] `main.py`: `_coarse_geometry` ve `_coarse_time_to_haven` yardımcıları (plan_4d bunları kullanır), `StressTestRequest`, uç; plan-4d testleri yeşil.

### Task 6 — Gerçek grid ve rapor
- [x] `test_stress_test_real_grid.py` (skip-guarded): rota-yerel sütunlar ≡ plan-4d küpünün rota sütunları; VIPER haven→haven çifti N = 1.000 süre ve oranlar; nominal ≈ planlayıcı.
- [x] `scripts/stress_test_report.py` → `docs/research/stress_test_report.md` (σ taraması, kesinti duyarlılığı, süreler).

### Task 7 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` B5 eki (istek/yanıt, ölçülen örnek).
- [x] Araştırma belgesinde B5 başlığına ✅ + "Yapıldı" blok alıntısı (ölçümlerle).
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler".
- [x] Tam test paketi (906 passed, 1 skipped); tek commit (eş-yazar satırı yok).
