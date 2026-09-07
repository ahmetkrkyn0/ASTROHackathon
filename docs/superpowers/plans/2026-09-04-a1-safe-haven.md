# A1 — Safe Haven — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VIPER'ın Safe Haven tanımını (Dünya yokken kesintisiz gölge ≤
`h_max_shadow_h`) rover başına zaman-bağımlı bir harita, saat cinsinden
time-to-safe-haven katmanı, 4-B planlayıcıda "Dünya batmadan SH'a yetiş"
kuralı ve SHERPA marj metrikleri olarak yayınlamak.

**Spec:** [2026-09-04-a1-safe-haven-design.md](../specs/2026-09-04-a1-safe-haven-design.md)

**Tech Stack:** Python 3.11, FastAPI, NumPy, SciPy (csgraph), spiceypy, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Mevcut davranış değişmez: `astar_4d` varsayılanları, `/api/plan-4d` mevcut
  alanları, `/api/cell-telemetry` mevcut alanları, 404/422 metinleri aynen.
- TDD: her görevde önce başarısız test, sonra kod.
- Çekirdeksiz temiz klonda tüm yeni testler koşar (gerçek grid testleri `skip`).
- `inf` JSON'a sızmaz; ikili katmanda `NaN`.

---

## Görevler

### Task 1 — Saf çekirdek: karanlık sayacı ve SH maskesi
- [x] `test_safe_haven.py`: `max_dark_hours_without_dte` yalnızca Dünya-yok adımlarını sayar, Dünya görününce ve aydınlıkta sıfırlanır, en uzun koşuyu verir.
- [x] Test: `safe_haven_mask` eşik, `ever_lit` ve `traversable` ile keser; rover profili değişince küme büzüşür.
- [x] `safe_haven.py` çekirdek fonksiyonları.

### Task 2 — time-to-safe-haven (saat, Dijkstra)
- [x] Test: 1-B koridorda tts = toplam kenar süresi (trapez), SH'da 0, duvar ardında inf.
- [x] Test: rastgele gridde sonlu-tts kümesi = `gated_move_count` ile SH'dan ulaşılabilen küme.
- [x] `time_to_safe_haven_hours` (vektörize kapılar + `csgraph.dijkstra(min_only=True)`).

### Task 3 — Dünya batış küpü ve harita kurucu
- [x] Test: `hours_until_earthset_cube` — görünmüyorsa 0, ilk görünmez dilime kalan saat, ufuk sonuna kadar görünürse `after_end_h` eklenir / yoksa inf.
- [x] Test: `build_safe_haven_map` senaryolu Güneş + Dünya ile (Dünya 0–100 h görünür, sonra yok; sırt sütunu karanlık) — beklenen maske, `info` alanları.
- [x] Test: `earthset_after_horizon_hours` senaryolu Dünya ile.
- [x] Test: `safe_haven_for_grids` ufuk/epoch yokken `unavailable` + reason; aynı anahtar ikinci çağrıda önbellekten.
- [x] Modül tamamlanır.

### Task 4 — Planlayıcı kuralı
- [x] `test_pathfinder_4d.py`: kısıt açıkken SH'a yetişemeyecek MOVE reddedilir (`safe_haven_deadline`), WAIT de denetlenir, `inf` deadline serbest, başlangıç ihlali `_empty` metniyle, kısıt kapalıyken yalnızca rapor (`states_past_haven_deadline`), `path_*` uzunlukları ve `None` kuralı, `ends_at_safe_haven`.
- [x] `pathfinder_4d.astar_4d`, `REJECTION_KEYS`, `no_path_reason_4d`, `_empty`.

### Task 5 — SHERPA marjları
- [x] Test: `route_margins` — time-to-sun-shadow min/ort, time-to-DSN-shadow min, time-to-0-SOC min; `None` kuralları.
- [x] Fonksiyon yazılır.

### Task 6 — Uçlar
- [x] `test_safe_haven_api.py`: `/api/safe-haven` start_utc yokken 422; harita hesaplanamazken `unavailable` ve ikili 404; monkeypatch'li haritayla JSON alanları, dört ikili alan ve `X-Layer-*` başlıkları, downsample.
- [x] `test_cell_telemetry_explain.py`: `start_utc` verilince `safe_haven` nesnesi; verilmeyince `null`.
- [x] `test_plan_4d_endpoint.py`: `require_safe_haven` + harita yokken 422; monkeypatch'li harita ve batış küpüyle kısıt uygulanır (404 metni), rapor alanları, SHERPA metrikleri.
- [x] `main` güncellenir.

### Task 7 — Gerçek grid ve rapor
- [x] `scripts/safe_haven_report.py`; `docs/research/safe_haven_report.md` üretilir.
- [x] `test_safe_haven_real_grid.py` (skip-guarded): profil sıralaması, kesir bandı, plan kısıtı.

### Task 8 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` A1 eki.
- [x] Araştırma belgesinde A1 başlığına ✅ + "Yapıldı" notu; spec'e ölçülen sonuçlar.
- [x] Tam test paketi (837 geçti, 1 atlandı; gerçek grid safe haven testleri +7); tek commit (eş-yazar satırı yok).
