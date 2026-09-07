# A4 — DTE katmanı — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dünya görünürlüğünü (Direct-to-Earth) katman, zaman serisi, planlayıcı
kısıtı ve replan girdisi olarak yayınlamak; NASA PGDA ürünüyle doğrulamak.

**Spec:** [2026-09-03-a4-dte-katmani-design.md](../specs/2026-09-03-a4-dte-katmani-design.md)

**Tech Stack:** Python 3.11, FastAPI, NumPy, spiceypy, rasterio, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu.

---

## Global Constraints

- Mevcut davranış değişmez: `sun_track_for_series` çıktısı, `/api/illumination-series`
  sözleşmesi, `astar_4d` varsayılan davranışı, 404/422 metinleri aynen.
- TDD: her görevde önce başarısız test, sonra kod.
- Çekirdeksiz temiz klonda tüm yeni testler koşar (gerçek grid testleri `skip`).

---

## Görevler

### Task 1 — Gövde parametreli efemeris ve iz
- [x] `test_ephemeris.py`: `earth_vector_body` `spkpos`'u `"EARTH"` ile çağırır (sahte spiceypy).
- [x] `test_ephemeris.py`: `sun_vector_body` hâlâ `"SUN"` ile çağırır.
- [x] `ephemeris.body_vector_body`, `earth_vector_body`; `sun_vector_body` delege.
- [x] `test_earth_visibility.py`: `earth_track_for_series` senaryolu vektörden az/el üretir; `sun_track_for_series` çıktısı değişmedi.
- [x] `illumination_series.body_track_for_series`, `_grid_north_azimuth`; `sun_track_for_series` delege.

### Task 2 — `earth_visibility.py`: seri, uzun dönem, comm_window
- [x] Test: `build_earth_visibility_series` epoch + geçici ufuk küpü ile `spice_horizon`, dilimler değişiyor.
- [x] Test: ufuk yokken `base_fraction` ile `static` + reason; ikisi de yokken `unavailable` + boş seri.
- [x] Test: `long_run_earth_visibility` örnek fraksiyonu doğru sayar.
- [x] Test: `comm_window` görünürken batışa kalan dakikayı, görünmezken 0 ve doğuşa kalanı verir; arama sınırı işaretlenir.
- [x] Modül yazılır.

### Task 3 — Katman: loader + terrain + `/api/layers`
- [x] `test_layer_validity.py`: `earth_visibility_grid.npy` varsa katman ve `DERIVED`; yoksa anahtar yok.
- [x] `test_terrain_api.py`: katman gridde varsa `/api/terrain` manifestinde ve `/api/layers/earth_visibility` ikili döner; yoksa 404 ve script işaret edilir.
- [x] `data_loader`, `terrain`, `main.get_layer` güncellenir.

### Task 4 — `/api/earth-series`
- [x] `test_terrain_api.py`: manifest alanları; `unavailable` iken `fields` boş ve ikili 404; monkeypatch'li seri ile ikili küp dilim sırası.
- [x] `main._check_series_budget` ortak yardımcı; uç yazılır.

### Task 5 — Planlayıcı kısıtı
- [x] `test_pathfinder_4d.py`: kısıt açıkken Dünya'yı görmeyen hücreye MOVE reddedilir (`earth_visibility` sayacı), WAIT serbest; kısıt kapalıyken sadece raporlanır; `path_earth_visible` uzunluğu.
- [x] `test_plan_4d_endpoint.py`: `require_earth_visibility` + seri yokken 422; monkeypatch'li seri ile yanıt alanları.
- [x] `pathfinder_4d`, `main.plan_4d` güncellenir.

### Task 6 — Replan girdisi
- [x] `test_replan_triggers.py`: `/api/replan` `utc` ile `comm_minutes_remaining` doldurur (monkeypatch `comm_window_from_metadata`); verilen değer ezilmez.
- [x] `test_pose_endpoint.py`: `/api/pose` aynı doldurma; `/api/comm-window` 409 ve 200.
- [x] `main` güncellenir.

### Task 7 — Doğrulama

> **Uygulama sırasında eklendi (bulgu):** ilk karşılaştırma iki ön koşul hatası
> ortaya çıkardı; her ikisi de bu görevin içinde kapatıldı. (1) Yerel işlenmiş
> gridler Site01 (satır 0, sütun 700) iken izlenen `metadata.json` Site11
> konumunu gösteriyordu — Site11 DEM'i indirilip P1 hattı yeniden koşturuldu;
> `build_horizon_cache.py` artık ham DEM'in pencereyi gerçekten içerdiğini
> doğruluyor. (2) 10 km ışın menzili uzak ufku kesiyordu — `horizon_map` `min_range_m`
> aldı, ufuk küpü LOLA 40 m kutup DEM'i ile 10–150 km arası ikinci geçişle
> iki ölçekli kuruluyor.
- [x] `horizon.py`: `min_range_m` (test önce); `build_horizon_cache.py`: `--far-dem`, ham DEM eşleşme kontrolü, `horizon_map_meta.json`.
- [x] `test_visibility_validation.py`: `visibility_comparison` sentetik gridde beklenen RMSE/r.
- [x] `visibility_validation.py`; `scripts/build_earth_visibility_cache.py`; `scripts/earth_visibility_validation.py`.
- [x] Gerçek grid: cache üretilir, PGDA TIF indirilir, script koşar, `docs/research/earth_visibility_validation.md` yazılır.
- [x] `test_earth_visibility_real_grid.py` (skip-guarded).

### Task 8 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` A4 eki.
- [x] Araştırma belgesinde A4 başlığına ✅.
- [x] Tam test paketi; tek commit (791 geçti, 1 atlandı).
