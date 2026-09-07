# D2 — Dış benchmark: MoonPlanBench (Chancán vd., Aralık 2025) — Tasarım Belgesi

**Tarih:** 5 Eylül 2026 · **Dal:** `berke-3d-backendEnhance` · **Kaynak madde:**
[12_faktor_backend_ozellik_arastirmasi_2026-09-03.md § D2](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)

**Yol:** mimari (yeni çekirdek modül + iki betik + rapor + dış veri + testler). Kullanıcı onay
kapısını kaldırdı; tasarım otonom kesinleştirildi, ölçümler sondalardan (aşağıda) okunur.

---

## Amaç

LunaPath'in planlayıcısını bağımsız, yayımlanmış bir Ay-kutup benchmark'ında (MoonPlanBench, 36
occupancy haritası) **aynı problem tanımı, aynı başlangıç/hedef kuralı ve aynı metrik tanımlarıyla**
koşturup makalenin tablosunun yanına koymak; sonucun neyi kanıtladığını ve neyi
kanıtlayamadığını (iddia sınırı) açıkça yazmak. Hiçbir sayı uydurulmaz: her başarı oranı, uzunluk,
süre 36 haritada koşturulup okunur; makaleden alınan her sayı "alıntı" etiketiyle durur.

Üç mod koşar:

1. **Saf mesafe Dijkstra — benchmark'ın hareket modeli** (8-komşu, çapraz köşe-kesme serbest):
   benchmark'ın kendi problemi; Dijkstra/A*/Theta* satırlarının **optimal uzunluğunu** verir.
2. **Saf mesafe Dijkstra — LunaPath'in güvenlik kuralı** (köşe-kesme yasak; `nav2_baseline`'ın
   SmacPlanner2D eşdeğeri).
3. **LunaPath A\*** iki ağırlık setiyle: **tek kriter** (`w_slope = 1`, diğerleri 0) ve **çok kriter**
   (LPR-1 varsayılanı 0,409 / 0,259 / 0,142 / 0,190 / 0,15).

İsteğe bağlı dördüncü satır grubu: benchmark'ın kendi PythonRobotics Dijkstra/A\*/Theta\*
uygulamaları **aynı makinede** (kullanıcının yerel klonundan içe aktarılır; depoya kod alınmaz).

## İddia sınırı (raporun her bölümünde)

- MoonPlanBench haritaları **yalnızca eğim (+ pürüzlülük) eşikli occupancy** gridleridir: gölge,
  termal, slip, Dünya görünürlüğü, pürüzlülük katmanı **yok**; ham DEM de yayımlanmamış (Drive'da
  yalnız `.npy`, `Background` klasöründe görsel). Bu yüzden LunaPath'in çok kriterli maliyet gridi bu
  haritalarda **tek değerlidir** (eğim 0, gölge 0, termal sabit → sonda: 1 benzersiz değer 0,190969)
  ve çok kriterli mod en kısa yol aramasına indirgenir. Araştırma belgesindeki "çok kriterli
  maliyetin getirdiği X % gölge azalması" cümlesi **kurulamaz**; rapor bunu söyler.
- Hücre boyutu ürün çözünürlüğü × 64 (makalenin altörnekleme çarpanı): **320 m – 7 680 m**. Bunlar
  bölgesel ölçekli haritalardır (45°N ürünü 2 880 km kenar), rover ölçeğinde değil; başarı
  oranı bir "rota planlama" değil "bağlantılılık + en kısa yol" ölçümüdür.
- Benchmark'ın referans planlayıcıları çapraz hamlede **köşe-kesmeyi yasaklamaz**
  (PythonRobotics `verify_node` yalnız hedef hücreye bakar). LunaPath ve `nav2_baseline` iki dolu
  hücre arasından çapraz geçişi reddeder (Round 2 M-1). Sonda: MoonPlanBench-10'da 12 haritanın
  **8'i yalnız köşe-kesmeyle bağlantılı**; bu kuralla başarı %33,3 / %91,7 / %100. Makalenin
  %100'ü bu modele bağlıdır; raporda iki satır ayrı ayrı gösterilir, biri "makalenin problemi",
  öteki "LunaPath'in problemi" diye etiketlenir.
- Sunum cümlesi: "Bağımsız, yalnızca eğim eşikli bir occupancy benchmark'ında (MoonPlanBench,
  36 harita) makalenin Dijkstra/Theta* yol uzunluklarını üç varyantta da **hücre hücre aynen**
  yeniden ürettik (651,81 / 636,16 / 620,24); LunaPath'in köşe-kesme yasağıyla ise 10° varyantında
  haritaların üçte ikisi bağlantısızdır — makalenin %100'ü sıfır genişlikli çapraz aralıklardan
  geçmeye dayanır."
- "Öğrenme tabanlı planlayıcı kullanmama kararımızın literatür kanıtı" **alıntı** olarak kalır
  (makale § 3.3 ve § 4.2.3: WPN dışında öğrenilmiş modeller Radish'te yol bulamadı; WPN 10× yavaş;
  Ay/Mars tablolarında öğrenilmiş model satırı yok). Biz öğrenilmiş model koşturmadık.
- Süre karşılaştırması makineler arası **yapılmaz**: makalenin süresi PathBench `Timer`'ıyla
  adaptör + PathBench tekrar-oynatma (`DenseMap.move`, her adımda engel listesi taraması) toplamıdır;
  bizimki planlayıcı çağrısının duvar saatidir. Aynı-makine referans satırları (isteğe bağlı) bu
  farkı gösterir.
- Bellek: makale MoonPlanBench için bellek sayısı vermiyor (yalnız Radish şekli); PathBench'in
  ölçümü `tracemalloc` tepe değeri **simülatör dahil**. Bizimki planlayıcı çağrısı etrafında;
  yalnız kendi içimizde karşılaştırılır.

## Kaynak / yöntem notu (5 Eylül 2026'da doğrulandı)

- **Makale:** M. Chancán, A. Banerjee, G. Nikolakopoulos, *Planetary Terrain Datasets and
  Benchmarks for Rover Path Planning*, arXiv:2512.21438v1 (24 Aralık 2025), Luleå University of
  Technology. arXiv HTML'de lisans satırı **CC BY-NC-SA 4.0**. § 3.1.2: "36 planar occupancy grids
  from the Moon's north and south poles … from DEMs of LOLA … slope and roughness thresholds of 10°,
  15° and 20° … down-sample original DEMs by a factor of 64 … average 400 × 400 cells, varying
  spatial resolutions". § 4.1.2: başlangıç/hedef "as far as possible from each other", yayımlanır.
  § 4.1.3: i7-1355U, Python 3.8, **60 s** sınır; metrikler SR %, yol uzunluğu (hücre), süre (s),
  hedefe kalan mesafe (hücre). **Tablo 1** (alıntı; aşağıda). Tablo başlığı "each variant comprises
  36 occupancy maps" der; Drive listesi ve metin 12 harita/varyant × 3 = 36 verir ve tablodaki tüm
  başarı oranları 1/12'nin katıdır (91 ≈ 11/12, 83 = 10/12, 8 = 1/12, 42 = 5/12, 50 = 6/12,
  25 = 3/12) → **12 harita/varyant**. Araştırma belgesindeki "36 harita, üç varyant" doğru.
- **Depo:** github.com/mchancan/PlanetaryPathBench, `main` @ `86dc4b63` (18 Aralık 2025, "added
  ack"), 9,9 MB, 542 dosya; **veri depoda değil** (README → Google Drive). Kökte LICENSE **yok**;
  `PathBench/LICENSE` BSD-3 (Toma vd.); README "This code is based on PythonRobotics (MIT) and
  PathBench". Adaptörler/`run.py`/`utils` yazarların; lisansı belirtilmemiş → **vendor edilmez**,
  yalnız kullanıcının yerel klonundan isteğe bağlı içe aktarılır.
- **Veri:** Drive klasörü `15srtIABvwBSbILQESVvAFPHMc3TCzS_R` → `MoonPlanBench-10/-15/-20` + `Background`.
  Her varyantta 12 `.npy`: 12 LOLA kutup LDEM ürünü (`LDEM_45N_100M`, `45S_100M`, `60N_120M`,
  `60S_120M`, `75N_30M`, `75S_30M`, `80N_20M`, `80S_20M`, `85N_10M`, `85S_10M`, `875N_5M`, `875S_5M`).
  uint8, değerler {0, 1}; `run.py`: `occ = (grid != 0)` → **sıfır olmayan = dolu**. Boyutlar 450²
  (45°), 243² (60°), 477² (75°), 475² (80°), 474² (85°, 87,5°). Boş oran: -10 %51–77, -15 %73–90,
  -20 %88–96. Toplam 7,0 MB. Hücre boyutu = ürün çözünürlüğü × 64 (5 m → 320 m … 120 m → 7 680 m);
  bu türetme makalenin "factor of 64" cümlesinden, raporda öyle etiketlenir. Dosya kimlikleri
  `embeddedfolderview` listesinden alınır; `uc?export=download` ile indirilir (60–230 KB,
  virüs-tarama ara sayfası yok). Drive klasöründe lisans dosyası **yok**; veri lisansı olarak
  makalenin CC BY-NC-SA 4.0'ı yazılır (ticari kullanım kısıtı; hackathon/akademik uygun).
- **Başlangıç/hedef** (`adapters/_common.auto_select_start_goal`): en büyük 8-bağlantılı boş bileşen
  (BFS; tarama satır sonra sütun; komşu sırası (1,0),(−1,0),(0,1),(0,−1),(1,1),(1,−1),(−1,1),(−1,−1)
  (dx,dy)); başlangıç = (y, x)'e göre sözlük-sırası en küçük; hedef = başlangıca kare-Öklid en uzak
  (eşitlikte BFS sırasında ilk). Yeniden uygulandı; 36/36 haritada deponun fonksiyonuyla **aynı**.
- **Referans planlayıcılar** (PythonRobotics türevi, `AStar/`, `Dijkstra/`, `ThetaStar/`):
  `occ_map` yolu → `obstacle_map[x][y]`, çözünürlük 1, robot yarıçapı **kullanılmaz**; hareket
  8-komşu (1 / √2); `verify_node` yalnız sınır + hedef hücre dolu mu → **köşe-kesme serbest**.
  Theta*: Bresenham görüş hattı. PathBench ajan yarıçapı 0 → genişletilmiş duvar yok; boş alan
  tam olarak `occ == 0`.
- **Metrikler** (`PathBench/src/algorithms/basic_testing.py::get_results`,
  `analyzer.py::__get_results`; sarmalayıcı `pathbench_wrappers._replay_path` yolu Bresenham ile
  hücre hücre tekrar oynatır, `DenseMap.move` her adımda **hamle öncesi** konumu ize ekler):
  - `goal_found`: ajanın son konumu hedef hücreye **eşit**.
  - `total_steps = len(trace)` — N noktalı yol için N−1 (hedef, `total_distance` hesaplanırken ize
    eklenir).
  - `total_distance`: ardışık iz noktaları arası Öklid toplamı (N nokta, hücre birimi) = makalenin
    "Path length".
  - `smoothness_of_trajectory`: her hamle için `u = (p_{i−1} − p_i)/‖·‖` (x, y = sütun, satır),
    `θ_i = arccos(u_x)`; `Σ |θ_i − θ_{i−1}| / N` (N = iz uzunluğu, hedef dahil). İşaretsiz açı
    (y bileşeni yok) — tanım aynen alınır, tuhaflığı raporda not edilir.
  - `obstacle_clearance`: her iz noktası için en yakın **dolu** hücreye Öklid mesafesi, N nokta
    ortalaması; engel yoksa 0.
  - `distance_to_goal`: ajanın son konumu → hedef (başarısızlıkta ajan başlangıçta kalır →
    başlangıç–hedef düz mesafesi; makalede RRT-Connect'in %0 satırı 554,1 = sondada MPB-10
    ortalama düz mesafe **554,06**).
  - `total_time`: `utility/timer.Timer` duvar saati, `algorithm_start` → `algorithm_done`
    (adaptör + tekrar oynatma).
  - `memory`: `tracemalloc` tepe / 1000 (KB; etiket "KiB"), `Simulator` koşusu etrafında.
  - Toplulaştırma: başarı % = ortalama(goal_found) × 100; adım/uzunluk/düzgünlük/açıklık/süre
    **yalnız başarılı** koşular üzerinden; hedefe mesafe ve bellek **tüm** koşular üzerinden.
  - Zaman sınırı 60 s (`run.py PLANNER_TIMEOUT_SECONDS`, `SIGALRM` — Windows'ta yok).

**Tablo 1 (alıntı, arXiv 2512.21438v1):** başarı % / yol uzunluğu (hücre) / süre (s) / hedefe kalan
(hücre) — MoonPlanBench-10 | -15 | -20:
Dijkstra 100/651,81/23,31/0 | 100/636,16/16,18/0 | 100/620,24/13,77/0;
ThetaStar 100/654,81/31,90/0 | 100/639,14/23,26/0 | 100/623,17/12,36/0;
AStar 91/639,94/30,82/56,1 | 83/621,25/32,45/72,1 | 100/620,24/19,52/0;
RRT 8/554,01/36,32/525,5 | 42/731,14/13,11/385,6 | 100/776,42/6,13/0;
Dynamic RRT 8/589,91/13,49/525,5 | 50/744,75/21,14/333,8 | 100/737,53/7,52/0;
RRT Connect 0/0/0/554,1 | 8/766,27/5,65/554,5 | 25/789,26/5,91/441,9.

## Mevcut durumdan kullanılanlar (yeniden yazılmaz)

- `pathfinder.astar(grids, start, goal, weights, constraints, rover)` → `path_pixels`, `metrics`
  (`computation_time_ms`, `nodes_expanded`, `edges_rejected`), `error`. Köşe-kesme yasağı, adım
  eğimi, yanal eğim, termal bariyer `_astar_core`'da; düz haritada eğim/gradyan 0 → yalnız
  köşe-kesme ve geçilebilirlik etkili.
- `cost_engine.compute_cost_grid`, `resolve_weights`, `_WEIGHT_KEYS`; `constants.get_rover`
  (LPR-1 varsayılan; eğim sınırı düz haritada etkisiz — hangi rover seçildiği raporda yazılır).
- `traversability.compute_traversability_bool` **kullanılmaz**: occupancy doğrudan `traversable`
  olur (benchmark'ın tanımı); rover eğim eşiği devre dışı. Termal sabit 0 °C (kapı −150 °C
  geçilir; `thermal_min` verilmez → soğuk uç = termal).
- `scripts/nav2_baseline.py::shortest_traversable_path` — `app/benchmark.py`'ye taşınır
  (`allow_corner_cutting` parametresiyle), `nav2_baseline` oradan içe aktarır (davranış aynı:
  varsayılan yasak).
- C4 kalıpları: önbellek betiği (indirme + sağlama + meta JSON, `fetched_utc`), rapor betiği
  (`--json` önce, `--from-json`), skip-korumalı gerçek veri testi, `.gitignore` satırı.

## Sondalar (5 Eylül 2026; atılabilir betikler `probe_d2.py`, `probe_ref_timing.py`, sayılar buraya)

- Depo klonu (Windows `core.longpaths`): veri yok; 3 × 12 harita Drive'dan 112 s'de indi (7,0 MB).
- 36 haritada **saf Dijkstra, köşe-kesme serbest**: başarı 100/100/100, ortalama uzunluk
  **651,81 / 636,16 / 620,24** — makalenin Dijkstra satırıyla iki ondalıkta **aynı**; harita başına
  uzunluklar deponun PythonRobotics Dijkstra'sıyla aynı (üç haritada doğrulandı: 363,81, 842,23,
  343,41). MPB-10 başlangıç–hedef düz mesafe ortalaması 554,06 (makale RRT-Connect %0: 554,1).
- **Köşe-kesme yasak** (nav2 baseline, LunaPath tek kriter, LunaPath çok kriter — üçü aynı):
  başarı **33,3 / 91,7 / 100 %**; başarılı haritalarda ortalama uzunluk 720,30 / 658,34 / 631,88.
  MPB-10'da bağlantısız 8 harita: 60S, 75N, 75S, 80S, 85N, 85S, 875N, 875S; MPB-15: 875S.
- Çok kriterli maliyet gridi her haritada **1 benzersiz değer** (0,190969; LPR-1 varsayılan
  ağırlıklar, termal 0 °C, gölge 0, eğim 0). Tek ve çok kriterli mod aynı uzunluğu bulur; yollar
  eşitlik kırma yüzünden hücre hücre farklı olabilir.
- Süre (bu makine, i7 dizüstü, Python 3.11): sondada LunaPath A* harita başına 1,8–24,4 s
  ölçüldü (19–99 160 düğüm) — **ama sonda planlayıcıyı `tracemalloc` açıkken zamanladı**; tam
  koşumda (izlemesiz) aynı haritalar **0,2–0,7 s** (bkz. "Uygulama sırasında bulunanlar"). Saf
  Dijkstra sondada 0,2–1,0 s (izlemesiz), deponun PythonRobotics Dijkstra/A\*/Theta\*'ı 3 haritada
  1,2–2,0 / 0,2–2,9 / 0,4–3,2 s; makale 13–32 s (PathBench tekrar oynatma dahil: `DenseMap.move`
  her hamlede ~47 000 elemanlı engel listesini tarar; ve `Analyzer.__run_simulation` tracemalloc
  açıkken zamanlar). Hiçbir koşu 60 s'yi aşmadı. `tracemalloc` tepe (LunaPath) 13–48 MB.
- Theta* ham (herhangi-açı) uzunluğu Dijkstra'dan kısa (804,66 < 842,23) ama makalede Theta*
  satırı Dijkstra'dan **uzun** (654,81 > 651,81): PathBench yolu Bresenham ile hücrelere
  döktükten sonra ölçer. Aynı-makine referans satırı bunu ölçer (ham ve döşenmiş uzunluk).

## Tasarım kararları

1. **API ucu eklenmez** (YAGNI): frontend'e gösterilecek şey rapordur; sözleşme belgesine
   dokunulmaz, commit mesajında söylenir.
2. **Occupancy → grids adaptörü** `app/benchmark.py::occupancy_to_grids`: `traversable = occ == 0`,
   `elevation`/`slope`/`shadow_ratio` sıfır, `thermal` sabit `BENCHMARK_THERMAL_C = 0.0`,
   `metadata.resolution_m = cell_size_m(name)`, `source = "moonplanbench"`, `layer_validity`:
   `traversable` **DERIVED** (yazarların LOLA'dan eşiklemesi), diğerleri **SYNTHETIC**;
   `metadata.benchmark` bloğu (varyant, eşik, ürün, çözünürlük türetmesi, iddia).
3. **Dört mod** (`MODES`): `dijkstra_cut` (benchmark hareket modeli), `dijkstra_nocut`
   (LunaPath kuralı), `lunapath_single`, `lunapath_multi`. Rover LPR-1. LunaPath'e köşe-kesme
   bayrağı **eklenmez** (üretim planlayıcısı benchmark için değişmez); düz maliyet gridinde
   optimal uzunluk hareket modeline göre tektir, `dijkstra_cut` satırı benchmark probleminin
   optimalini verir.
4. **Metrikler PathBench tanımıyla** (`path_length_cells`, `path_steps`, `trajectory_smoothness`,
   `obstacle_clearance` — SciPy `distance_transform_edt` ile, brute force ile birim testte eşit;
   `distance_to_goal`, `original_distance`), zaman sınırı 60 s **sonradan** uygulanır (koşu
   kesilmez; 60 s üstü başarısız sayılır, `timed_out`), bellek `tracemalloc` tepe (KB, /1000).
5. **Toplulaştırma PathBench ile aynı** (başarılı-koşu filtresi) + bizim ek sütunlar
   (`nodes_expanded`, hücre boyutu, metre cinsinden uzunluk).
6. **Referans planlayıcılar isteğe bağlı** (`--reference-dir <klon>`): `adapters.dijkstra/a_star/
   thetastar.run` içe aktarılır, aynı başlangıç/hedef, süre ölçülür, Theta* için ham ve
   Bresenham-döşenmiş uzunluk. Klon yoksa satırlar "koşturulmadı".
7. **Veri deposu dışında:** `lunapath/data/benchmarks/moonplanbench/<varyant>/<ad>.npy` +
   `moonplanbench_meta.json` (makale, depo commit'i, klasör/dosya kimlikleri, SHA-256, bayt,
   lisans, `fetched_utc`); `.gitignore`'a `lunapath/data/benchmarks/`.
8. **İndirme bağımlılıksız** (`urllib`): `embeddedfolderview` listesi + `uc?export=download`;
   `gdown` eklenmez. Dosya `.npy` başlığı taşımıyorsa yazılmaz.
9. **Rapor** `docs/research/moonplanbench_report.md` (`scripts/moonplanbench_runner.py`,
   `--json` önce, `--from-json`, `--maps N` hızlı mod): (1) veri kimliği/lisans/biçim;
   (2) metrik tablosu — üç varyant × dört mod (+ referans satırları) + makale satırları "alıntı";
   (3) başarı farkları ve nedenleri (köşe-kesme, bağlantısız haritalar listesi); (4) çok kriterli
   modun ne satın aldığı (hiçbir şey; neden); (5) süre/bellek; (6) iddia sınırı + sunum cümlesi.

## Bileşenler

### 1. `backend/app/benchmark.py` — yeni modül

- Sabitler: `MOONPLANBENCH_DIR` (`lunapath/data/benchmarks/moonplanbench`, `_P1_PROCESSED_DIR`
  kalıbı), `META_FILENAME`, `VARIANTS`, `SLOPE_THRESHOLD_DEG`, `LDEM_NATIVE_M_PER_PX` (12 ürün),
  `DOWNSAMPLE_FACTOR = 64`, `DRIVE_ROOT_FOLDER_ID`, `DRIVE_VARIANT_FOLDER_IDS`, `PAPER_ARXIV`,
  `REPO_URL`, `REPO_COMMIT`, `DATA_LICENSE`, `PAPER_TABLE_1` (alıntı sözlüğü), `TIMEOUT_S = 60`,
  `BENCHMARK_THERMAL_C`, `MODES`, `CLAIM`.
- `cell_size_m(map_name) -> float`; `load_occupancy(path) -> np.ndarray[bool]` (True = dolu).
- `auto_select_start_goal(occ) -> ((sr, sc), (gr, gc))` (satır/sütun; benchmark BFS sırası).
- `occupancy_to_grids(occ, cell_size_m, *, variant=None, map_name=None) -> dict`.
- `shortest_traversable_path(traversable, start, goal, resolution_m, allow_corner_cutting=False)`
  (`nav2_baseline`'dan taşınır).
- Metrikler: `path_length_cells`, `path_steps`, `trajectory_smoothness`, `obstacle_clearance`,
  `distance_to_goal`, `rasterize_path` (Bresenham; Theta* için), `bresenham_line`.
- `run_mode(mode, occ, start, goal, cell_size_m, rover=None) -> dict` (`success`, `timed_out`,
  `path`, `length_cells`, `length_m`, `steps`, `time_s`, `memory_kb`, `smoothness`, `clearance`,
  `dist_left`, `original_distance`, `nodes_expanded`, `error`).
- `run_reference_planner(name, occ, start, goal, reference_dir) -> dict` (isteğe bağlı içe aktarma;
  `sys.path` geçici; `rx, ry` → hücreler; Theta* için ham ve döşenmiş).
- `aggregate(results) -> dict` (PathBench toplulaştırması + ek sütunlar).
- `run_benchmark(data_dir, modes, max_maps=None, reference_dir=None, rover_id="lpr_1") -> dict`
  (harita başına satırlar + varyant toplamları + meta).
- `load_inventory(data_dir) -> dict` (varyant → sıralı dosya listesi), `load_meta(data_dir)`.

### 2. `scripts/build_moonplanbench_cache.py`

`--data-dir`, `--force`, `--offline` (varsa yalnız sağlama), `--variants`. Klasör listesi →
dosya kimlikleri → indir → `.npy` başlığı denetimi → `np.load` şekil/dtype/değer kümesi {0,1}
denetimi → SHA-256 → `moonplanbench_meta.json`. 12 × 3 = 36 değilse uyarır ve yazdığı sayıyı
meta'ya koyar (sayı uydurmaz).

### 3. `scripts/moonplanbench_runner.py`

`--data-dir`, `--maps N`, `--modes`, `--reference-dir`, `--rover`, `--json`, `--from-json`,
`--output`. `sys.stdout` UTF-8. JSON'u markdown'dan önce yazar; JSON commit'lenmez.

### 4. `scripts/nav2_baseline.py`

`shortest_traversable_path` yerel tanımı silinir, `from app.benchmark import shortest_traversable_path`.

### 5. `.gitignore`, README (Veri bölümü, C4 satırının altı), araştırma belgesi (✅ + Yapıldı), spec/plan.

## Veri akışı

```
Drive (embeddedfolderview) ──build_moonplanbench_cache──▶ lunapath/data/benchmarks/moonplanbench/*/*.npy + meta.json
        │
        ▼
moonplanbench_runner ─▶ load_inventory ─▶ her harita: load_occupancy → auto_select_start_goal
        ├─ dijkstra_cut / dijkstra_nocut : shortest_traversable_path(allow_corner_cutting)
        ├─ lunapath_single / lunapath_multi : occupancy_to_grids → pathfinder.astar(weights, rover)
        ├─ (isteğe bağlı) referans: adapters.*.run(occ, [sx, sy], [gx, gy])
        └─ metrikler (PathBench tanımı) → aggregate → JSON → markdown rapor
```

## Hata davranışı

- Veri dizini yok / eksik varyant: runner ne bulduğunu söyler ve **yalnız bulunanları** koşturur;
  hiç harita yoksa çıkış kodu 1, rapor yazılmaz.
- Meta yok: rapor "sağlama yok" der, koşar.
- Referans klonu yok / içe aktarılamıyor: referans satırları "koşturulmadı: <neden>".
- Planlayıcı hata döndürürse (`error`): koşu başarısız, `error` metni satırda; istisna yayılmaz.
- Başlangıç/hedef bulunamıyorsa (boş hücre yok): harita "atlandı" olarak listelenir.
- İndirme: `.npy` sihirli baytı yoksa ya da `{0,1}` dışı değer varsa dosya yazılmaz; sağlama
  uyuşmazlığı `--force` olmadan üzerine yazmaz.

## Test stratejisi

- `backend/test_benchmark.py` (birim; verisiz klonda koşar):
  - `cell_size_m` 12 ürün; `load_occupancy` (0/1 uint8 → bool, sıfır olmayan dolu).
  - `auto_select_start_goal`: elle 5×5 haritalar — en büyük bileşen, (satır, sütun) en küçük
    başlangıç, en uzak hedef, eşitlikte BFS sırası; **deponun fonksiyonuyla karşılaştırma**
    referans klonu varsa (skip-korumalı) 36 haritada.
  - `shortest_traversable_path`: çapraz aralık haritasında `allow_corner_cutting=False` → yol yok,
    `True` → yol var; uzunluk 1/√2 toplamları.
  - Metrikler elle: düz yol düzgünlük 0; 90° dönüşlü yol `(π/2)/N`; açıklık brute force ==
    EDT; hedefe mesafe; `rasterize_path` Bresenham.
  - `occupancy_to_grids`: şekiller, `traversable`, sabit termal, metadata; `compute_cost_grid`
    tek benzersiz değer (düzlük testi).
  - `run_mode` dört modda 7×7 haritada yol bulur; `aggregate` başarılı-filtre semantiği
    (başarısız koşuların uzunluğu ortalamaya girmez, hedefe mesafesi girer).
  - `run_benchmark` sentetik mini benchmark: `tmp_path`'e 2 varyant × 2 harita yazılır, uçtan uca;
    `--from-json` yeniden render eşitliği (runner'ın `render_markdown` fonksiyonu içe aktarılarak).
- `backend/test_benchmark_real_data.py` (skip-korumalı: veri dizini + meta):
  36 dosya, şekiller ve boş oranlar (0, 1) içinde, meta SHA'ları dosyayla uyuşur, 36 başlangıç/hedef
  çifti bugün deponun fonksiyonuyla hesaplanan sabit listeyle **aynı**, `dijkstra_cut` üç
  varyantta 12/12 yol bulur ve ortalama uzunluk makalenin Dijkstra satırıyla ±0,01 (bu, sayı
  iddiası değil, yeniden üretim kilididir), en az bir haritada dört mod da yol bulur.
- Tam paket arka planda; benchmark koşumlarıyla eşzamanlı değil.

## Kapsam dışı (bilinçli)

- MarsPlanBench ve Radish; RRT ailesi ve öğrenilmiş modeller (alıntı).
- LunaPath'e köşe-kesme bayrağı; Theta*/LOS yumuşatma (D1).
- Ham LOLA DEM'lerden kendi katmanlarımızı türetmek (5 m ürünler GB ölçeğinde; benchmark'ın
  altörnekleme ve eşikleme kodu depoda yok).
- API ucu, frontend, sözleşme belgesi.
- Performans iyileştirmesi (A3): yalnız ölçülür ve yazılır.

## Uygulama sırasında bulunanlar ve ölçümler (5 Eylül 2026)

**Sapmalar (tasarımdan):**

- **Bellek ve süre ayrı geçişlerde.** İlk uygulama her koşuyu `tracemalloc` açıkken zamanladı; duman
  testinde saf Dijkstra 0,9 s → 4,7 s, PythonRobotics A* 39 s'ye çıktı (tahsis izleme Python'u
  birkaç kat yavaşlatır). `run_mode(trace_memory=False)` varsayılan; `run_benchmark(memory=True)` /
  `--memory` her modu ikinci kez tracemalloc altında koşturup `memory_kb` ve `time_s_traced` yazar,
  `time_s` izlemesiz kalır; referans planlayıcılar hiç izlenmez. Yan bulgu: PathBench
  `Analyzer.__run_simulation` simülasyonu **tracemalloc açıkken** zamanlar — makalenin sürelerinin
  bir kısmı budur (raporun § 5'inde yazılı, sayı olarak bizim iki sütunumuzla gösterilir).
- **Harita sayısı.** Tablo başlığındaki "her varyant 36 harita" yerine 12 harita/varyant (Drive
  listesi `embeddedfolderview` ile doğrulandı; tablodaki tüm başarı oranları 1/12'nin katı).
  `EXPECTED_FILES_PER_VARIANT = 12`; betik farklı sayıda dosya görürse uyarır, yazdığı sayıyı meta'ya koyar.
- **Referans planlayıcılar** `--reference-dir` ile deponun klonundan içe aktarılır; yol
  PythonRobotics'in döndürdüğü hedef→başlangıç sırasından `_orient_path` kuralıyla çevrilir,
  Theta* çıktısı `rasterize_path` (PathBench'in `_grid_line_sequence` Bresenham'ı ile aynı
  adımlama) ile hücrelere döşenir; hem ham hem döşenmiş uzunluk raporlanır.
- **`distance_to_goal`** kısmi yolda son hücreden ölçülür (PathBench tekrar oynatması ajanı oraya
  götürür); başarısız/zaman aşımı koşuda ajan başlangıçta kalır → başlangıç–hedef mesafesi. İlk test
  satırı bunu yanlış varsaymıştı; tanım kazandı.
- **`nav2_baseline.shortest_traversable_path`** `app/benchmark.py`'ye taşındı
  (`allow_corner_cutting=False` varsayılanı = eski davranış); `nav2_baseline` içe aktarır. Mevcut
  `test_review2_fixes` yalnız `--start` varsayılanına bakar, etkilenmedi.
- Gerçek veri testi başlangıç/hedef BFS'sini modül fixture'ında bir kez hesaplar (36 harita ×
  ~2–3 s; ilk sürüm iki testte tekrar hesaplayıp 4 dk 9 s sürdü).
- Rapor sayıları ondalık virgülle (C4 raporu gibi); makale satırları "alıntı" etiketli.

**Doğrulanan yeniden üretimler (36 harita, `test_benchmark_real_data.py` kilitleri):**

- Başlangıç/hedef: 36/36 harita deponun `auto_select_start_goal`'ı ile aynı (sabit liste testte).
- `dijkstra_cut` ortalama uzunluk 651,81 / 636,16 / 620,24 = makale Dijkstra satırı (±0,01 kilit);
  aynı-makine PythonRobotics Dijkstra harita başına aynı uzunluk.
- MPB-10 başlangıç–hedef düz mesafe ortalaması 554,06 = makalede RRT-Connect'in %0 satırı 554,1.
- Theta* döşenmiş uzunluk > Dijkstra > Theta* ham uzunluğu (makaledeki sıralamayla tutarlı;
  duman testi 45N: 669,61 > 664,93 > 646,50).

**Ölçüm özeti (tam koşum 1 715 s, 36 harita, `--reference-dir` + `--memory`; tamamı
[moonplanbench_report.md](../../research/moonplanbench_report.md)):**

| | MPB-10 | MPB-15 | MPB-20 |
|---|---|---|---|
| `dijkstra_cut` başarı / uzunluk | 100 % / 651,81 | 100 % / 636,16 | 100 % / 620,24 |
| makale Dijkstra (alıntı) | 100 % / 651,81 | 100 % / 636,16 | 100 % / 620,24 |
| `dijkstra_nocut` = LunaPath (iki mod) başarı / uzunluk | 33,3 % / 720,30 | 91,7 % / 658,34 | 100 % / 631,88 |
| yalnız köşe-kesmeyle bağlantılı harita | 8/12 | 1/12 | 0/12 |
| maliyet gridi benzersiz değer (36 harita) | 1 | 1 | 1 |
| LunaPath süre ort. / maks (s, izlemesiz) | 0,38 / 0,68 | 0,32 / 0,51 | 0,22 / 0,35 |
| LunaPath süre, tracemalloc açık (s) | 11,7 | 9,6 | 5,9 |
| PythonRobotics Dijkstra / A\* / Theta\* süre ort. (s, bu makine) | 3,3 / 7,8 / 6,5 | 6,4 / 13,5 / 8,1 | 8,2 / 8,4 / 4,7 |
| makale Dijkstra / Theta\* / A\* süre (s, alıntı) | 23,3 / 31,9 / 30,8 | 16,2 / 23,3 / 32,5 | 13,8 / 12,4 / 19,5 |
| Theta\* döşenmiş (ham) ↔ makale | 654,61 (625,04) ↔ 654,81 | 639,14 (617,90) ↔ 639,14 | 623,17 (611,40) ↔ 623,17 |
| LunaPath bellek tepe (MB, izlemeli geçiş) | 43,7 | 44,3 | 43,7–43,9 |

Okuma: sondadaki "LunaPath yavaş (A3)" izlenimi tracemalloc artefaktıydı; izlemesiz LunaPath A\*
aynı makinedeki PythonRobotics planlayıcılardan 10–25 kat hızlı ve makalenin sürelerinin 30–100
katı altında. Makalenin A\* başarısızlıkları (91 / 83 %) burada oluşmadı (36/36, maks 29,7 s);
aynı kodun A\*'ı optimaldir (Dijkstra ile aynı uzunluk), makaledeki eksiklerin 60 s sınırından
geldiğini düşünüyoruz (bizim okumamız, makalede gerekçe yok). MPB-10 Theta\* döşenmiş uzunluk
makaleden 0,20 hücre farklı (bir haritada döşeme farkı; incelenmedi), diğer iki varyant aynı.
