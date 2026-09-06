# D2 — MoonPlanBench dış benchmark koşucusu — uygulama planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** LunaPath'in planlayıcısını MoonPlanBench'in 36 occupancy haritasında (12 LOLA kutup
LDEM ürünü × 10°/15°/20° eşik) benchmark'ın kendi başlangıç/hedef kuralı ve PathBench metrik
tanımlarıyla dört modda koşturup (`dijkstra_cut`, `dijkstra_nocut`, `lunapath_single`,
`lunapath_multi`; isteğe bağlı aynı-makine PythonRobotics referansları) makalenin Tablo 1'i ile yan
yana koyan rapor üretmek; iddia sınırını her bölümde yazmak.

**Architecture:** Yeni `app/benchmark.py` (sabitler, occupancy yükleme, benchmark BFS'siyle
başlangıç/hedef, occupancy→grids adaptörü, köşe-kesme parametreli saf Dijkstra, PathBench
metrikleri, `run_mode`/`run_reference_planner`/`aggregate`/`run_benchmark`);
`scripts/build_moonplanbench_cache.py` (Drive `embeddedfolderview` listesi + `uc?export=download`,
`.npy` denetimi, SHA-256, meta JSON); `scripts/moonplanbench_runner.py` (koşum + `--json`/`--from-json`
+ markdown); `nav2_baseline` Dijkstra'yı modülden alır. API ucu yok.

**Spec:** [2026-09-05-d2-moonplanbench-design.md](../specs/2026-09-05-d2-moonplanbench-design.md)

**Tech Stack:** Python 3.11, NumPy 2.2, SciPy 1.15 (`ndimage.distance_transform_edt`), stdlib
`urllib`/`tracemalloc`/`hashlib`, pytest.

**Commit kuralı:** özellik bitince **tek commit**; ara commit yok; push en sonda toplu; commit
mesajında eş-yazar satırı yok.

---

## Global Constraints

- Sayı uydurma yok: her başarı oranı/uzunluk/süre 36 haritada koşturulup okunur; makale sayıları
  `PAPER_TABLE_1` sözlüğünde "alıntı" olarak durur ve raporda öyle etiketlenir.
- Veri depoya girmez: `lunapath/data/benchmarks/` `.gitignore`'da; kod vendor edilmez (referans
  planlayıcılar yalnız `--reference-dir` ile kullanıcının klonundan içe aktarılır).
- Üretim planlayıcısı (`pathfinder`, `cost_engine`) **değişmez**; Site11 SHA kilitleri aynen.
- `traversable = occ == 0` (benchmark tanımı; sıfır olmayan = dolu); rover eğim eşiği devre dışı;
  termal sabit `BENCHMARK_THERMAL_C = 0.0`; `layer_validity`: traversable DERIVED, diğerleri SYNTHETIC.
- Metrik tanımları PathBench `basic_testing.get_results` / `analyzer.__get_results` ile aynı;
  60 s sınırı sonradan uygulanır (`timed_out`), koşu kesilmez.
- Frontend'e, API'ye, sözleşme belgesine dokunulmaz.
- Gerçek veri / klon testleri skip-korumalı; verisiz klonda diğer tüm testler koşar. Yeni dosyalarda
  ruff temiz. Rapor betiği `sys.stdout` UTF-8, JSON markdown'dan önce; JSON commit'lenmez.

---

## Dosya haritası

| Dosya | Sorumluluk |
|---|---|
| `backend/app/benchmark.py` (yeni) | sabitler (`MOONPLANBENCH_DIR`, `META_FILENAME`, `VARIANTS`, `SLOPE_THRESHOLD_DEG`, `LDEM_NATIVE_M_PER_PX`, `DOWNSAMPLE_FACTOR`, `DRIVE_*`, `PAPER_*`, `REPO_*`, `DATA_LICENSE`, `PAPER_TABLE_1`, `TIMEOUT_S`, `BENCHMARK_THERMAL_C`, `MODES`, `REFERENCE_PLANNERS`, `CLAIM`), `cell_size_m`, `load_occupancy`, `auto_select_start_goal`, `shortest_traversable_path`, `bresenham_line`, `rasterize_path`, metrikler, `occupancy_to_grids`, `run_mode`, `run_reference_planner`, `aggregate`, `load_inventory`, `load_meta`, `run_benchmark` |
| `backend/test_benchmark.py` (yeni) | birim testler (elle 5×5–7×7 haritalar, sentetik mini benchmark, klon varsa 36 haritada başlangıç/hedef eşitliği) |
| `backend/test_benchmark_real_data.py` (yeni) | skip-korumalı gerçek veri testleri |
| `scripts/build_moonplanbench_cache.py` (yeni) | indirme + denetim + SHA + meta |
| `scripts/moonplanbench_runner.py` (yeni) | koşum + JSON + markdown |
| `scripts/nav2_baseline.py` | `shortest_traversable_path` içe aktarımı |
| `.gitignore` | `lunapath/data/benchmarks/` |
| `README.md` | Veri bölümüne D2 satırı |
| `docs/research/12_faktor…md` | D2 ✅ + Yapıldı |
| `docs/research/moonplanbench_report.md` | rapor çıktısı |
| spec | "Uygulama sırasında bulunanlar ve ölçümler" |

---

### Task 1: `app/benchmark.py` — sabitler, `cell_size_m`, `load_occupancy`, `auto_select_start_goal`

**Files:** Create `backend/app/benchmark.py`; Test `backend/test_benchmark.py`.

**Produces:** `cell_size_m(map_name: str) -> float`; `load_occupancy(path) -> np.ndarray[bool]`
(True = dolu); `auto_select_start_goal(occ: np.ndarray[bool]) -> tuple[tuple[int,int], tuple[int,int]]`
((satır, sütun) çiftleri); `VARIANTS`, `SLOPE_THRESHOLD_DEG`, `LDEM_NATIVE_M_PER_PX`,
`DOWNSAMPLE_FACTOR`, `PAPER_TABLE_1`, `MODES`.

- [x] **Adım 1: başarısız testler**

```python
def test_cell_size_is_native_resolution_times_64():
    assert cell_size_m("LDEM_875S_5M") == 320.0
    assert cell_size_m("LDEM_60N_120M.npy") == 7680.0
    with pytest.raises(ValueError):
        cell_size_m("LDEM_99X_1M")

def test_load_occupancy_nonzero_is_occupied(tmp_path):
    np.save(tmp_path / "m.npy", np.array([[0, 1], [2, 0]], dtype=np.uint8))
    occ = load_occupancy(tmp_path / "m.npy")
    assert occ.dtype == bool and occ.tolist() == [[False, True], [True, False]]

def test_start_goal_largest_component_lexicographic_start_farthest_goal():
    occ = np.array([[0,0,1,0,0],[0,0,1,0,0],[1,1,1,0,0],[0,0,0,0,0],[0,0,0,0,0]], dtype=bool)
    # largest component is the right/bottom L (16 cells); start = min (row, col) in it = (0, 3)
    (sr, sc), (gr, gc) = auto_select_start_goal(occ)
    assert (sr, sc) == (0, 3) and (gr, gc) == (4, 0)

def test_start_goal_tie_is_first_in_bfs_order():
    occ = np.zeros((3, 3), dtype=bool)
    assert auto_select_start_goal(occ) == ((0, 0), (2, 2))
```

- [x] **Adım 2: koştur, `ImportError` ile kırmızı**
- [x] **Adım 3: uygulama** — BFS spec'teki sırayla ((1,0),(−1,0),(0,1),(0,−1),(1,1),(1,−1),(−1,1),(−1,−1) (dx,dy)), başlangıç `min(comp, key=(y,x))`, hedef `max(comp, key=(dx²+dy²))`, dönüş (satır, sütun). `PAPER_TABLE_1` spec'teki 18 satır. `MODES = ("dijkstra_cut", "dijkstra_nocut", "lunapath_single", "lunapath_multi")`.
- [x] **Adım 4: yeşil**

### Task 2: `shortest_traversable_path(allow_corner_cutting)` + `nav2_baseline` içe aktarımı

**Files:** Modify `backend/app/benchmark.py`; Modify `scripts/nav2_baseline.py` (yerel tanım silinir); Test `backend/test_benchmark.py`.

**Produces:** `shortest_traversable_path(traversable, start, goal, resolution_m, allow_corner_cutting=False) -> tuple[list[tuple[int,int]], float]`.

- [x] **Adım 1: testler**

```python
DIAG_GAP = np.array([[0,1,0],[1,0,1],[0,1,0]], dtype=bool)  # True = occupied; centre free

def test_corner_cutting_refused_by_default():
    trav = ~DIAG_GAP
    path, dist = shortest_traversable_path(trav, (0, 0), (2, 2), 1.0)
    assert path == [] and dist == math.inf

def test_corner_cutting_allowed_is_the_benchmark_motion_model():
    trav = ~DIAG_GAP
    path, dist = shortest_traversable_path(trav, (0, 0), (2, 2), 1.0, allow_corner_cutting=True)
    assert path == [(0, 0), (1, 1), (2, 2)] and dist == pytest.approx(2 * math.sqrt(2))

def test_resolution_scales_distance_only():
    trav = np.ones((3, 3), dtype=bool)
    _, d1 = shortest_traversable_path(trav, (0, 0), (0, 2), 1.0)
    _, d5 = shortest_traversable_path(trav, (0, 0), (0, 2), 5.0)
    assert d1 == 2.0 and d5 == 10.0
```

- [x] **Adım 2: kırmızı** · **Adım 3:** nav2'deki gövde taşınır, `if dr and dc and not allow_corner_cutting and not (trav[r, nc] and trav[nr, c]): continue`; `nav2_baseline.py`: `from app.benchmark import shortest_traversable_path`, `heapq`/`OFFSETS` kaldırılır. · **Adım 4: yeşil**; `python -c "import scripts.nav2_baseline"` yerine `python -m py_compile scripts/nav2_baseline.py`.

### Task 3: PathBench metrikleri + Bresenham

**Files:** Modify `backend/app/benchmark.py`; Test `backend/test_benchmark.py`.

**Produces:** `path_length_cells(path) -> float`; `path_steps(path) -> int` (len−1, boşsa 0);
`trajectory_smoothness(path) -> float`; `obstacle_clearance(path, occ) -> float`;
`distance_to_goal(path, start, goal) -> float` (boş yol → start→goal); `bresenham_line(a, b) -> list`
(a dahil, b dahil); `rasterize_path(points) -> list` (ardışık noktalar arası Bresenham, tekrarsız).

- [x] **Adım 1: testler**

```python
def test_length_and_steps():
    p = [(0, 0), (0, 1), (1, 2)]
    assert path_length_cells(p) == pytest.approx(1 + math.sqrt(2)) and path_steps(p) == 2
    assert path_length_cells([]) == 0.0 and path_steps([]) == 0

def test_smoothness_straight_zero_and_one_right_angle():
    assert trajectory_smoothness([(0, 0), (0, 1), (0, 2)]) == 0.0
    # PathBench: u = (p_{i-1} - p_i)/|.| in (x, y); theta = arccos(u_x); sum |dtheta| / N
    p = [(0, 0), (0, 1), (1, 1)]  # move +x then +y: theta 0 -> pi/2
    assert trajectory_smoothness(p) == pytest.approx((math.pi / 2) / 3)

def test_clearance_matches_brute_force():
    rng = np.random.default_rng(0)
    occ = rng.random((9, 9)) < 0.3
    path = [(r, c) for r in range(9) for c in (0, 4, 8) if not occ[r, c]]
    walls = np.argwhere(occ)
    brute = np.mean([np.min(np.linalg.norm(walls - np.array(p), axis=1)) for p in path])
    assert obstacle_clearance(path, occ) == pytest.approx(brute)
    assert obstacle_clearance(path, np.zeros((9, 9), dtype=bool)) == 0.0

def test_distance_to_goal_empty_path_is_original_distance():
    assert distance_to_goal([], (0, 0), (3, 4)) == 5.0
    assert distance_to_goal([(0, 0), (3, 4)], (0, 0), (3, 4)) == 0.0

def test_bresenham_and_rasterize():
    assert bresenham_line((0, 0), (2, 2)) == [(0, 0), (1, 1), (2, 2)]
    assert rasterize_path([(0, 0), (0, 3)]) == [(0, 0), (0, 1), (0, 2), (0, 3)]
```

- [x] **Adım 2: kırmızı** · **Adım 3:** düzgünlük: her hamle için `ux = (c_prev - c_cur)/norm`, `theta = arccos(clip(ux))`, `|theta-prev|` topla, `/len(path)`; açıklık: `distance_transform_edt(~occ)` ile `mean(edt[rows, cols])`, `occ.any()` değilse 0; Bresenham `pathbench_wrappers._grid_line_sequence` ile aynı adımlama. · **Adım 4: yeşil**

### Task 4: `occupancy_to_grids` + `run_mode`

**Files:** Modify `backend/app/benchmark.py`; Test `backend/test_benchmark.py`.

**Produces:** `occupancy_to_grids(occ, cell_size_m, *, variant=None, map_name=None) -> dict`;
`run_mode(mode, occ, start, goal, cell_size_m, rover=None) -> dict` (anahtarlar: `mode`, `success`,
`timed_out`, `path`, `length_cells`, `length_m`, `steps`, `time_s`, `memory_kb`, `smoothness`,
`clearance`, `dist_left`, `original_distance`, `nodes_expanded`, `error`).

- [x] **Adım 1: testler**

```python
def test_grids_from_occupancy_shapes_and_validity():
    occ = np.zeros((4, 5), dtype=bool); occ[1, 1] = True
    g = occupancy_to_grids(occ, 320.0, variant="MoonPlanBench-10", map_name="LDEM_875S_5M")
    assert g["traversable"].tolist() == (~occ).tolist()
    for k in ("elevation", "slope", "shadow_ratio"):
        assert g[k].shape == (4, 5) and not g[k].any()
    assert np.all(g["thermal"] == BENCHMARK_THERMAL_C)
    md = g["metadata"]
    assert md["resolution_m"] == 320.0 and md["shape"] == [4, 5] and md["source"] == "moonplanbench"
    assert md["layer_validity"]["traversable"] == "DERIVED" and md["layer_validity"]["slope"] == "SYNTHETIC"
    assert md["benchmark"]["slope_threshold_deg"] == 10

def test_multi_criteria_cost_grid_is_flat_on_occupancy():
    occ = np.zeros((6, 6), dtype=bool); occ[2, 2] = True
    g = occupancy_to_grids(occ, 320.0)
    cost = compute_cost_grid(g["slope"], g["thermal"], g["shadow_ratio"], 320.0, traversable=g["traversable"])
    finite = cost[np.isfinite(cost)]
    assert finite.size == 35 and np.unique(finite).size == 1

@pytest.mark.parametrize("mode", MODES)
def test_run_mode_finds_a_path_on_open_map(mode):
    occ = np.zeros((7, 7), dtype=bool); occ[3, 1:6] = True; occ[3, 6] = False
    res = run_mode(mode, occ, (0, 0), (6, 0), 320.0)
    assert res["success"] and not res["timed_out"] and res["dist_left"] == 0.0
    assert res["path"][0] == (0, 0) and res["path"][-1] == (6, 0)
    assert res["length_m"] == pytest.approx(res["length_cells"] * 320.0)
    assert res["steps"] == len(res["path"]) - 1 and res["memory_kb"] > 0 and res["time_s"] >= 0

def test_run_mode_corner_gap_only_cut_mode_succeeds():
    occ = np.array([[0,1,0],[1,0,1],[0,1,0]], dtype=bool)
    assert run_mode("dijkstra_cut", occ, (0, 0), (2, 2), 1.0)["success"]
    for mode in ("dijkstra_nocut", "lunapath_single", "lunapath_multi"):
        r = run_mode(mode, occ, (0, 0), (2, 2), 1.0)
        assert not r["success"] and r["dist_left"] == pytest.approx(math.sqrt(8)) and r["length_cells"] is None
```

- [x] **Adım 2: kırmızı** · **Adım 3:** `lunapath_single` ağırlıkları `{"w_slope": 1.0, diğer dört 0.0}`; `lunapath_multi` `weights=None`; `tracemalloc.start()/get_traced_memory()/stop()` çağrı etrafında; `time.perf_counter`; `timed_out = time_s > TIMEOUT_S`; `success = bool(path) and path[-1] == goal and not timed_out`. · **Adım 4: yeşil**

### Task 5: `aggregate`, `load_inventory`, `load_meta`, `run_reference_planner`, `run_benchmark`

**Files:** Modify `backend/app/benchmark.py`; Test `backend/test_benchmark.py`.

**Produces:** `aggregate(rows: list[dict]) -> dict` (`n_maps`, `n_success`, `success_rate_pct`,
`mean_length_cells`, `mean_length_m`, `mean_steps`, `mean_time_s`, `max_time_s`, `mean_smoothness`,
`mean_clearance`, `mean_dist_left`, `mean_original_distance`, `mean_memory_kb`, `mean_nodes_expanded`,
`n_timed_out`; başarılı filtre PathBench gibi); `load_inventory(data_dir) -> dict[str, list[Path]]`;
`load_meta(data_dir) -> dict | None`; `run_reference_planner(name, occ, start, goal, reference_dir) -> dict`
(`name ∈ REFERENCE_PLANNERS = ("Dijkstra", "AStar", "ThetaStar")`; Theta* için `length_cells_raw` ve
döşenmiş `length_cells`); `run_benchmark(data_dir, modes=MODES, max_maps=None, reference_dir=None, rover_id="lpr_1", progress=None) -> dict`
(`{"generated_utc", "data_dir", "meta", "rover_id", "modes", "reference": {...}, "variants": {variant: {"maps": [...], "aggregates": {mode: {...}}, "reference_aggregates": {...}}}}`).

- [x] **Adım 1: testler**

```python
def test_aggregate_filters_like_pathbench():
    rows = [
        {"success": True, "timed_out": False, "length_cells": 10.0, "length_m": 3200.0, "steps": 9, "time_s": 1.0,
         "memory_kb": 5.0, "smoothness": 0.1, "clearance": 2.0, "dist_left": 0.0, "original_distance": 8.0, "nodes_expanded": 50},
        {"success": False, "timed_out": False, "length_cells": None, "length_m": None, "steps": None, "time_s": 0.5,
         "memory_kb": 3.0, "smoothness": None, "clearance": None, "dist_left": 8.0, "original_distance": 8.0, "nodes_expanded": 4},
    ]
    a = aggregate(rows)
    assert a["n_maps"] == 2 and a["success_rate_pct"] == 50.0
    assert a["mean_length_cells"] == 10.0 and a["mean_time_s"] == 1.0  # successful only
    assert a["mean_dist_left"] == 4.0 and a["mean_memory_kb"] == 4.0   # all runs
    assert aggregate([])["success_rate_pct"] is None

def _write_mini_benchmark(root):
    for variant in ("MoonPlanBench-10", "MoonPlanBench-20"):
        d = root / variant; d.mkdir(parents=True)
        m = np.zeros((7, 7), dtype=np.uint8); m[3, 1:6] = 1
        np.save(d / "LDEM_875S_5M.npy", m)
        g = np.array([[0,1,0],[1,0,1],[0,1,0]] + [[0]*3]*0, dtype=np.uint8)  # 3x3 corner gap
        np.save(d / "LDEM_60N_120M.npy", g)

def test_run_benchmark_mini_end_to_end(tmp_path):
    _write_mini_benchmark(tmp_path)
    out = run_benchmark(tmp_path, max_maps=None)
    assert set(out["variants"]) == {"MoonPlanBench-10", "MoonPlanBench-20"}
    v = out["variants"]["MoonPlanBench-10"]
    assert [m["map"] for m in v["maps"]] == ["LDEM_60N_120M", "LDEM_875S_5M"]
    assert v["aggregates"]["dijkstra_cut"]["success_rate_pct"] == 100.0
    assert v["aggregates"]["dijkstra_nocut"]["success_rate_pct"] == 50.0
    assert v["maps"][1]["cell_size_m"] == 320.0 and v["maps"][1]["start_rc"] == [0, 0]
    assert out["reference"]["status"].startswith("not run")

def test_run_benchmark_empty_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_benchmark(tmp_path)

@pytest.mark.skipif(not _HAS_CLONE, reason="needs a local PlanetaryPathBench clone (LUNAPATH_PPB_DIR)")
def test_start_goal_matches_the_benchmarks_own_function_on_real_maps(): ...
```

- [x] **Adım 2: kırmızı** · **Adım 3:** `run_reference_planner`: `sys.path.insert(0, reference_dir)` geçici (try/finally çıkar), `MPLBACKEND=Agg`, `importlib.import_module("adapters." + {"Dijkstra": "dijkstra", "AStar": "a_star", "ThetaStar": "thetastar"}[name])`, `run(occ.astype(int), [sc, sr], [gc, gr])` → `rx, ry` (x = sütun) → yol `(ry, rx)` ters çevrilir (adaptör hedeften başlangıca döner; `_orient_path` gibi uçlara göre); `stdout` bastırılır ("Find goal"). Referans klonu yoksa `{"status": "not run: ..."}`. · **Adım 4: yeşil**

### Task 6: `scripts/build_moonplanbench_cache.py` + `.gitignore`

**Files:** Create `scripts/build_moonplanbench_cache.py`; Modify `.gitignore`; Test `backend/test_benchmark.py` (parser + meta, ağsız).

**Produces:** `parse_embedded_folder_listing(html) -> list[tuple[str, str]]` (ad, id), `download_url(file_id)`,
`validate_npy_bytes(data) -> np.ndarray`, `build_meta(...)`; CLI `--data-dir`, `--force`, `--offline`, `--variants`.

- [x] **Adım 1: testler** — fixture HTML dizesi (`<div class="flip-entry" id="entry-ID">…<div class="flip-entry-title">LDEM_45N_100M.npy</div>`) → liste; `validate_npy_bytes` uint8 {0,1} kabul, `{0,2}` ya da 3-B reddi (`ValueError`); `--offline` ile var olan dosyalar için meta yazımı `tmp_path`'te (SHA, bayt, `fetched_utc` alanları).
- [x] **Adım 2: kırmızı** (betik `scripts/` altında; test `importlib.util.spec_from_file_location` ile yükler) · **Adım 3:** uygulama (`urllib.request`, UA başlığı, 120 s zaman aşımı; dosya varsa ve `--force` yoksa atla; meta: `paper`, `repo`, `repo_commit`, `data_license`, `drive_root_folder_id`, `variants: {variant: {folder_id, files: [{name, id, bytes, sha256, shape, free_fraction}]}}`, `n_files`, `fetched_utc`). `.gitignore`: `# D2: MoonPlanBench occupancy maps (CC BY-NC-SA 4.0) and their provenance` + `lunapath/data/benchmarks/`. · **Adım 4: yeşil**

### Task 7: `scripts/moonplanbench_runner.py`

**Files:** Create `scripts/moonplanbench_runner.py`; Test `backend/test_benchmark.py` (render, ağsız).

**Produces:** `render_markdown(report: dict) -> str`; CLI `--data-dir`, `--maps`, `--modes`,
`--reference-dir`, `--rover`, `--json`, `--from-json`, `--output`.

- [x] **Adım 1: test** — mini benchmark JSON'undan `render_markdown` altı bölüm başlığını, alıntı etiketini ("alıntı"), `dijkstra_cut` satırını ve iddia cümlesini içerir; `--from-json` ile aynı metin.
- [x] **Adım 2: kırmızı** · **Adım 3:** rapor bölümleri spec § Tasarım 9: (1) veri kimliği/lisans/biçim (meta'dan; yoksa "sağlama yok"), (2) metrik tablosu varyant başına (satırlar: dört mod, referans satırları, makale satırları "alıntı"), (3) başarı farkları: bağlantısız harita listesi (`dijkstra_nocut` başarısız / `dijkstra_cut` başarılı), (4) çok kriterli modun ne satın aldığı: maliyet gridi benzersiz değer sayısı (haritadan `occupancy_to_grids` + `compute_cost_grid`), tek/çok uzunluk eşitliği, (5) süre/bellek tablosu (ortalama/maks; `nodes_expanded`), (6) iddia sınırı + sunum cümlesi (`CLAIM`). · **Adım 4: yeşil**

### Task 8: `backend/test_benchmark_real_data.py` (skip-korumalı)

- [x] 36 dosya (varyant başına 12), şekiller {243, 450, 474, 475, 477}², boş oran (0, 1), meta SHA'ları dosyayla uyuşur, 36 başlangıç/hedef çifti sabit listeyle aynı (5 Eylül 2026'da deponun fonksiyonuyla hesaplandı), `dijkstra_cut` 12/12 ve ortalama uzunluk `PAPER_TABLE_1[variant]["Dijkstra"]["length"]` ± 0,01 (yeniden üretim kilidi), `LDEM_45N_100M` MPB-20'de dört mod da yol bulur.

### Task 9: Gerçek koşum

- [x] `python scripts/build_moonplanbench_cache.py` → 36 dosya + meta; `pytest test_benchmark_real_data.py`.
- [x] `python scripts/moonplanbench_runner.py --reference-dir <klon> --json <scratch>/moonplanbench.json` arka planda, tek başına (süre ölçümü); sonra `--from-json` ile render; sayılar okunur.

### Task 10: Belgeler, doğrulama, tek commit, hafıza

- [x] Araştırma belgesi D2 ✅ + "Yapıldı" bloğu; spec ölçüm bölümü; README satırı; ruff yeni dosyalar; `cd backend && python -m pytest` arka planda; tek commit (C4 biçimi); hafıza dosyaları.
