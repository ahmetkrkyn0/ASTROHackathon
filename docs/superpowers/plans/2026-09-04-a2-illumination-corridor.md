# A2 — Sürekli-aydınlık koridoru (3-B bağlı-bileşen budaması, CMU) — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Aydınlanma serisi + kaba geçilebilirlikten `(t, r, c)` ikili
`lit_safe` hacmini çıkarmak; CMU'nun iki geçişli budamasını planlayıcının
hamle süresine ve kapılarına sadık ileri/geri erişilebilirlikle uygulamak;
`astar_4d`'ye `require_continuous_illumination` ön-filtresi vermek; her
`/api/plan-4d` yanıtına `illumination_corridor` bloğu ve `metrics.max_dwell_hours`
eklemek; ölçülmüş hızlanma ve "rota tanım gereği gölgeye girmiyor" kanıtını
(`path_dark_hours = 0`, D3 LP-R01 ρ = `h_max_shadow_h`) raporlamak.

**Architecture:** `app/illumination_corridor.py` (saf, numpy + scipy.ndimage)
hacmi, kenar tablolarını (`safe_haven._gated_edges`'ten), `run` küpünü,
ileri/geri erişilebilirliği, koridoru, dwell'i ve özet bloğunu üretir.
`pathfinder_4d.astar_4d` iki küp (`corridor_cube`, `corridor_lit_run_cube`) ve
bir bayrakla vokselleri açar/reddeder (`continuous_illumination` sayacı).
`main.plan_4d` yalnızca ekleme yapar; isteğe bağlı `GET /api/illumination-corridor`
küpü f32 yayınlar.

**Spec:** [2026-09-04-a2-illumination-corridor-design.md](../specs/2026-09-04-a2-illumination-corridor-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, SciPy 1.15 (`ndimage.label`,
`sparse.csgraph` A1'de zaten var), FastAPI/pydantic, pytest.

**Commit kuralı:** özellik bitince tek commit; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Mevcut `/api/plan-4d` alanları ve davranışı `require_continuous_illumination=False`
  iken aynen; yalnızca ekleme (`illumination_corridor`, `metrics.max_dwell_hours`,
  `metrics.states_outside_corridor`, `metrics.moves_outside_corridor`,
  `metrics.continuous_illumination_enforced`, `edges_rejected.continuous_illumination`).
- Kapılar ve hamle süresi planlayıcıyla **aynı** (`_gated_edges`, `edge_travel_time_s`,
  `d = max(1, ceil(h / slice_hours))`).
- Aydınlık kuralı `lit_rule ∈ {"all", "majority"}`, varsayılan `"all"`.
- İddia sınırı her yanıtta (`provenance.claim`, `uncertainty_note` B3 %10,8).
- Sayı uydurma yok: ölçümler Site11'de koşulur; gerçek grid testleri skip-korumalı.
- TDD: her görevde önce başarısız test. `inf`/`NaN` JSON'a sızmaz.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/illumination_corridor.py` | Yeni: `LIT_RULES`, `lit_volume`, `lit_run`, `forward_run`, `EdgeTables`/`edge_tables`, `forward_reach`, `backward_reach`, `prune_corridor`, `components`, `reachable_from`, `IlluminationCorridor`/`build_corridor`, `route_dwell`, `corridor_summary`, `CLAIM`, `UNCERTAINTY_NOTE` |
| `backend/app/pathfinder_4d.py` | `REJECTION_KEYS` + `continuous_illumination`; `no_path_reason_4d` cümlesi; `astar_4d(corridor_cube, corridor_lit_run_cube, require_continuous_illumination)`; `_empty` alanları |
| `backend/app/main.py` | `Plan4DRequest.require_continuous_illumination`, `lit_rule`; `plan_4d` entegrasyonu (422/404/blok/metrik); `GET /api/illumination-corridor` |
| `backend/test_illumination_corridor.py` | Birim testler (sentetik) |
| `backend/test_pathfinder_4d.py` | Oyuncak küp planlayıcı testleri (ekleme) |
| `backend/test_plan_4d_endpoint.py` | API testleri (monkeypatch gölge serisi) |
| `backend/test_illumination_corridor_real_grid.py` | Skip-korumalı gerçek grid |
| `scripts/illumination_corridor_report.py` → `docs/research/illumination_corridor_report.md` | Rapor |
| `docs/frontend/3b-veri-sozlesmesi.md`, araştırma belgesi, spec, `README.md` | Belgeler |

---

## Görevler

### Task 0 — Sonda (yapıldı, spec'te)
- [x] VIPER / LPR-1 / Ay gecesi epoch'larında kaba `lit & traversable` hacmi iki kuralla ölçüldü: %40,5 / %45,8; %4,8 / %6,5; 0. Standart rotaların başlangıcı t0'da karanlık, VIPER hedefi hiç aydınlık değil → rapor koridor-içi çift seçecek.

### Task 1 — Hacim, run küpleri, kenar tabloları
- [x] `test_illumination_corridor.py`: `lit_volume([snap], coarsen=4, "all"/"majority")` 8×8 ince gridde yarı aydınlık blok → `all` False / `majority` True; tam aydınlık & tam karanlık iki kuralda aynı; çıkış `(T, 2, 2)` bool; bilinmeyen kural `ValueError`.
- [x] Test: `lit_run` `[1,1,0,1,1,1]` → `[1,2,0,1,2,3]`; `forward_run` → `[2,1,0,3,2,1]` (hücre başına, `(T,1,1)` hacim).
- [x] Test: `edge_tables(np.ones((3,3)), None, None, 80.0, rover, slice_hours)`: 8 ofset, merkezden 8 komşu `ok`, kenar hücrelerinde dışa ofsetler kapalı; `slices` = `max(1, ceil(travel_h / slice_hours))` (`slice_hours = kardinal süre` → kardinal 1, köşegen 2); yükseklik duvarı (`elevation[:,1] = 1000`) 1. sütuna giden kenarları kapatır; geçilemez orta hücreye kenar yok ve köşe kesme; simetri `ok[k][r,c] == ok[-k][r+dr, c+dc]`.
- [x] `illumination_corridor.py`: `LIT_RULES`, `lit_volume`, `lit_run`, `forward_run`, `EdgeTables` (dataclass: `offsets`, `ok`, `slices`, `max_slices`), `edge_tables` (`_gated_edges` → iki yön).

### Task 2 — İleri/geri erişilebilirlik, budama, bileşenler
- [x] Test (d ≡ 1, `slice_hours` büyük): `(T=5, 1, 5)` elle hacim — hücre 0 hep aydınlık, hücre 1 `t≥2`'de yanıyor (kök yok: koridor dışı olmalı? Hayır: hücre 0'dan `t=2`'de hamleyle girilebilir → koridorda), hücre 2 `t≤2`'de aydınlık sonra karanlık (çıkmaz: `t=2`'de hücre 3'e geçilemiyorsa dışarı), hücre 3 yalnızca `t=4`, hücre 4 hiç. Beklenen `forward`, `backward`, `corridor` kümeleri elle yazılır.
- [x] Test: kaba kuvvet — `_brute_force_reach(volume, edges, sources, direction)` (voksel grafı BFS) ile tohumlu 20 rastgele `(8, 4, 4)` hacim (`p_lit = 0.6`), rastgele `slices ∈ {1,2}` tablolarıyla `forward_reach`/`backward_reach`/`prune_corridor` birebir; `corridor ⊆ ∪{26-bileşen ilk ve son dilime dokunan}` (`ndimage.label`).
- [x] Test d > 1: `(T=4, 1, 2)`, hamle 2 dilim: hedef yalnızca `t∈{1,2}` aydınlıksa hücre 1'e ulaşılamaz; `t∈{0,1,2}` aydınlıksa `t=2`'de ulaşılır; kaynak `t=1`'de sönerse ulaşılamaz.
- [x] Test: boş hacim → koridor 0, `components` `{count: 0, largest_voxels: 0, spanning_count: 0}`; iki ayrık aydınlık blok → `count 2`, `largest_voxels` doğru, `spanning_count`.
- [x] Test: `reachable_from(corridor, edges, start)` = `forward_reach(sources={start@0})`; başlangıç koridor dışı → tümü False.
- [x] `illumination_corridor.py`: `forward_reach`, `backward_reach`, `prune_corridor`, `components`, `reachable_from`.

### Task 3 — `build_corridor`, dwell, özet bloğu
- [x] Test: `build_corridor(series, traversable, elevation, slope, res, rover, coarsen, slice_hours, lit_rule)` → `IlluminationCorridor` alanları (`lit_safe`, `run`, `forward`, `backward`, `corridor`, `dwell_slices`, `edges`, `lit_rule`, `n_slices`, `slice_hours`); `corridor ⊆ lit_safe`; `dwell_slices == forward_run(corridor)`.
- [x] Test: `route_dwell(corridor_obj, path_states, top=3)` elle rota → `max_dwell_hours`, `dwell_horizon_limited`, `dwell_opportunities` sıralı; boş rota → `None`/`[]`.
- [x] Test: `corridor_summary(corridor_obj, start, goal, path_states, path_dark_hours, provenance, timings, enforced)` anahtarları (spec'teki blok), `voxels.pruned_fraction`, `start.first_corridor_slice`, `goal.reachable_in_corridor`, `route.inside`; `json.dumps(allow_nan=False)` geçer; `path_states=None` → `route` alanları `None`.
- [x] `illumination_corridor.py`: `IlluminationCorridor`, `build_corridor`, `route_dwell`, `corridor_summary`, `CLAIM`, `UNCERTAINTY_NOTE`, `REFERENCE`.

### Task 4 — Planlayıcı kapısı
- [x] `test_pathfinder_4d.py`: `"continuous_illumination" in REJECTION_KEYS`; `no_path_reason_4d({"continuous_illumination": 3})` "corridor" içerir.
- [x] Test: 1×4 küp, koridor hücre 3'ü `t≥3`'te açıyor (`run` uyumlu) → uygulanınca rota her durumda `corridor[t,r,c]`, `metrics.continuous_illumination_enforced True`, `states_outside_corridor 0`; koridor hedefi hiç açmıyor → `error` "corridor" içerir ve `edges_rejected.continuous_illumination > 0`; başlangıç `corridor[0,start]` False → `error` "first slice" içerir; `require` küpsüz → `error`; tek küp → `error`; uygulanmadan koridor verilince `states_outside_corridor` sayılır ve rota değişmez.
- [x] Test: gölge küpü koridorla tutarlı (koridor = `shadow < 0.5`) → uygulanınca `path_dark_hours` tümü 0; hamle 2 dilim sürerken `run` yetersizse hamle reddedilir (elle `run` küpü).
- [x] `pathfinder_4d.py`: anahtar, cümle, parametreler, `_empty` alanları, kapılar, metrikler.

### Task 5 — API: istek alanları, blok, 422/404, metrikler
- [x] `test_plan_4d_endpoint.py`: `_shadow_series_lit_until(k)` yardımcı (monkeypatch `main_module.build_shadow_series`, provenance `spice_horizon`/`time_varying True`); varsayılan istekte `illumination_corridor` var, `enforced False`, `provenance.shadow_model == "static"` (monkeypatch'siz) ve `metrics.max_dwell_hours` anahtarı; `require_continuous_illumination=True` statik seride 422 ("static" içerir); `k=3` ile `require` → 404 detail "corridor" içerir; `k=None` ile → 200, `route.inside True`, `path_dark_hours` tümü 0, `metrics.max_dwell_hours > 0`, `edges_rejected.continuous_illumination == 0`, `metrics.continuous_illumination_enforced True`; `lit_rule="majority"` 200 ve blokta `lit_rule "majority"`; `lit_rule="x"` 422; `require_safe_haven` + `require_continuous_illumination` birlikte (`_fake_safe_haven_map`, `_earth_series_closing_at(None)`, `k=None`) 200.
- [x] `main.py`: `Plan4DRequest` alanları; `plan_4d` entegrasyonu; 404 detail koridor cümlesi; blok; `metrics.max_dwell_hours`.

### Task 6 — Gerçek grid testleri ve rapor
- [x] `test_illumination_corridor_real_grid.py` (skip: gridler + `horizon_map.npy` + çekirdekler): VIPER epoch'unda `build_corridor` hacim > 0, `corridor ⊆ lit_safe`; standart VIPER rotası `require` → 404 ve detail başlangıç bloğunun karanlık olduğunu söyler; koridor-içi çift (`pick_corridor_pair` yardımcı: dilim-0 koridor kesitinde standart başlangıca en yakın hücre → `reachable_from` ile Chebyshev en uzak hücre; kaba → ince blok merkezi) `require` → 200, `path_dark_hours` tümü 0, LP-R01 ρ == 96, `route.inside`; koridorsuz aynı çift 200; Ay gecesi (2026-09-13, LPR-1 `_NIGHT_PAIR`) → `voxels.corridor == 0`, `require` → 404 "no lit"/"dark" içerir; süre < 120 s.
- [x] `scripts/illumination_corridor_report.py` → `docs/research/illumination_corridor_report.md`: üç epoch × iki kural hacim/budama/bileşen tabloları + süreler; standart rotaların reddi (gerekçe); koridor-içi çiftlerde budamalı vs budamasız `computation_time_ms`, `nodes_expanded`, `path_dark_hours` maks, LP-R01 ρ, `max_dwell_hours`; CMU label vs koridor farkı; sunum cümlesi ve iddia sınırı. Koştur, sayıları oku.

### Task 7 — `GET /api/illumination-corridor` (düşük öncelik)
- [x] Test (`test_plan_4d_endpoint.py`, monkeypatch seri): JSON manifest `binary_format.shape == [T, h, w]`, `fields.corridor.binary_url` `format=f32` içerir; f32 `corridor` bayt sayısı `T·h·w·4`, `X-Series-Slices`, `X-Series-Rows`, `X-Series-Resolution-M == 320`, `X-Series-Lit-Rule`; `field=nope` 422; `lit_rule=majority` kabul.
- [x] `main.py`: uç (`start_utc`, `rover_id`, `n_slices`, `slice_hours` (yoksa auto), `coarsen`, `lit_rule`, `format`, `field ∈ corridor|lit_safe|dwell_hours`).

### Task 8 — Belgeler ve kapanış
- [x] `docs/frontend/3b-veri-sozlesmesi.md` A2 eki ("## Değişmeyenler" öncesi): istek alanları, blok tablosu, `GET /api/illumination-corridor`, ölçülen örnek, frontend'in çizebileceği tek paragraf.
- [x] Araştırma belgesinde A2 başlığına ✅ + "Yapıldı" blok alıntısı (ölçümler, bağlantılar, sapmalar); README satırı.
- [x] Spec'e "Uygulama sırasında bulunanlar ve ölçümler" (tablo, sapmalar, test sayıları).
- [x] Tam test paketi `cd backend && python -m pytest` (1 113 passed, 2 skipped, 8:17); tek commit (eş-yazar satırı yok); hafıza dosyası (A2 yapıldı + hash, sıradaki B2).
