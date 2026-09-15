# LunaPath Backend Envanteri

**Commit:** `fea37ef5d90d998b9a24cc2de6631954028347d0` (`fea37ef`) · **Tarih:** 2026-08-31 16:05:09 +0300 · **Denetleyen:** Claude Code

**Uyarı:** Bu rapor yukarıdaki commit'e aittir. Backend değiştiğinde yeniden üretilmelidir.

**Denetim koşulları.** Çalışma ağacı denetim anında kirliydi, ancak **yalnızca `frontend/` altında** (`App.css`, `App.tsx`, `MapCanvas.tsx`, `api.ts` değişik; `TerrainView3D.tsx` yeni). `backend/` çalışma ağacı temizdi, bu yüzden rapordaki her `backend/...` referansı `fea37ef`'in içeriğine birebir uyar.

**Kapsam.** Yalnızca HTTP yüzeyi: `backend/app/` (34 modül) ve `backend/test_*.py` (49 dosya). `lunapath_ros` kapsam dışı — bkz. §1 notu.

**Yöntem.** Kaynak kodu okuma + `backend/test_*.py` iddiaları + kullanıcının çalıştırdığı `localhost:8000` sunucusuna salt-okunur HTTP sondaları. Canlı gözlemden gelen her değer aşağıda `[canlı sonda]` ile işaretlidir.

**Sondalama dürüstlüğü.** Grid yükleyen üç uç (`/api/load-dem`, `/api/load-preprocessed`, `/api/scenarios/{id}/load`) denetim sırasında **çağrılmadı**. Ancak `POST /api/plan` çağrıldı ve bu uç **süreç içi durum yazıyor**: `app.state.active_corridor`, `active_corridor_id`, `active_corridor_rover_id` ve `app.state.corridors` kayıt defteri (`main.py:722-735`). Yani denetim, sunucunun aktif korridor durumunu değiştirmiştir. Diske veya kalıcı depoya yazılmadı; etki sunucu yeniden başlatılınca kaybolur. `POST /api/compare` çağrıldı ama durum yazmıyor (§E-5).

---

## 0. Özet

1. Tek FastAPI uygulaması, router bölünmesi yok: `backend/app/main.py:91`, `FastAPI(title="LunaPath", version="0.3.0")`. 18 route + 1 exception handler, hepsi `main.py:140`–`1732` arasında.
2. Maliyet fonksiyonu **dört bileşenli**. Kod içindeki birebir adlar: `"slope"`, `"energy"`, `"shadow"`, `"thermal"` (`costmap.py:196,207,226,237`). Ağırlık anahtarları `w_slope`, `w_energy`, `w_shadow`, `w_thermal` (`cost_engine.py:26-31`).
3. **Maliyet ayrıştırma hücre bazında dışa açık.** `CostMap.explain()` katman başına ağırlıklı katkı + toplam döndürüyor (`costmap.py:121-159`), `/api/cell-telemetry` yanıtında `cost_breakdown` olarak yayımlanıyor (`main.py:552,571`). **Rota geneli toplulaştırılmış ayrıştırma yok.**
4. **Kısıt marjları kısmen dışa açık** — ve bu, ön beklentinin tersi. `check_profile_constraints()` her profil kısıtı için `limit` + `actual` + `satisfied` üretiyor (`scenarios.py:99-161`) ve `/api/plan-multi` ile `/api/compare` bunu `constraint_check` alanında yayımlıyor (`main.py:1210,1264,1288`). Marj = `limit − actual` istemci tarafında hesaplanabilir.
5. **Bariyer içi slack değerleri dışa açılmıyor.** `slack_slope`/`slack_lat`/`slack_soc` dört ayrı fonksiyonda yerel değişken olarak hesaplanıp anında `math.log()` içine girip toplanıyor; hiçbiri saklanmıyor (`cost_engine.py:628,633,673,674,705,710,717` ve `589,600`). Dışa açılan tek toplulaştırma `barrier_share` (`pathfinder.py:770`).
6. **Başarısızlık tanısı üretiliyor ama yapılandırılmamış halde kayboluyor.** `_no_path_reason()` hangi kısıtın kaç kenarı reddettiğini **düzyazı cümle** olarak kuruyor (`pathfinder.py:828-865`); `_empty_result` bunu `edges_rejected` sayaçları ve `nodes_expanded` ile birlikte `metrics` içinde taşıyor (`pathfinder.py:812-825`); `main.py:627-628` yalnızca `error` string'ini alıp 404'e koyuyor ve `metrics`'i **atıyor**.
7. **Ağırlık doğrulaması iki uçta tutarsız.** `POST /api/plan` gövdesinde `[0.0, 2.0]` doğrulaması var (`main.py:336-341`), `GET /api/layers/*` sorgu parametrelerinde **hiç yok** (`main.py:1319-1322`). `[canlı sonda]` `w_slope=999` → HTTP 200, `X-Layer-Max: 981.55`; `w_slope=-5` → HTTP 200.
8. **Ağırlıklar normalize edilmiyor.** `resolve_weights()` yalnızca varsayılanların üzerine yazıyor, toplam kontrolü veya ölçekleme yok (`cost_engine.py:51-63`).
9. **Plan düzeyinde önbellek yok.** `[canlı sonda]` aynı girdinin iki koşumu: 2840 ms → 4848 ms duvar süresi; ikinci koşum ucuz değil. Önbellek yalnızca `load_and_preprocess_dem` diskte tutuyor (`data_loader.py:258-262,378-379`), plan yolunda değil.
10. **Köken (provenance) meta verisi güçlü.** Dört basamaklı `SYNTHETIC < DERIVED < MODEL < MEASURED` merdiveni (`traversability.py:98-121`), her katmanda `layer_validity` (`main.py:572`), binary yanıtta `X-Layer-Validity` (`terrain.py:228-229`), `shadow_model`/`thermal_model` sağlayıcı blokları.

---

## 1. Depo haritası

| Dizin | Rol | Kanıt |
|---|---|---|
| `backend/app/` | FastAPI servisi + domain katmanı, 34 modül | `find backend -name "*.py"` |
| `backend/test_*.py` | 49 bağımsız test betiği | aynı |
| `lunapath/` | Offline P1 pipeline (DEM → `.npy` + `metadata.json`) | `lunapath/src/process_lunar_data.py` |
| `frontend/` | Vite + React istemci | `frontend/package.json` |
| `lunapath_ros/`, `lunapath_msgs/` | ROS 2 düğümleri ve mesaj tipleri | `lunapath_ros/package.xml` |
| `scripts/` | Yardımcı betikler (`build_horizon_cache.py` vb.) | `ls scripts/` |
| `docker/` | `ros2-jazzy.Dockerfile` | `ls docker/` |

**Satır sayıları (backend/app):** toplam 21.779. En büyükler: `main.py` 1732, `cost_engine.py` 873, `pathfinder.py` 869, `pathfinder_4d.py` 541, `thermal_model.py` 520, `data_loader.py` 476, `simulation.py` 409.

**Yapısal not — kapsam dışı ama kaydedilmesi gereken.** `lunapath_ros` bir HTTP istemcisi değil; domain katmanını doğrudan import ediyor: `from app.pathfinder import astar`, `app.cost_engine.resolve_weights`, `app.simulation.simulate_path`, `app.data_loader.load_preprocessed_grids`, `app.corridor.build_corridor` (`lunapath_ros/lunapath_ros/planner_node.py:17-23`), `app.localization.evaluate_pose` (`pose_monitor.py:36-38`), `app.data_loader` (`grid_publisher.py:10`). Yani hesaplama çekirdeğinin **iki tüketicisi** var. Bu envanter yalnızca FastAPI tüketicisini kapsar; ROS 2 tarafı denetlenmedi.

**Giriş noktası:** `backend/app/main.py:91`. Router bölünmesi yok — `APIRouter` ve `include_router` depoda hiç geçmiyor.

**Pinlenmiş bağımlılıklar** (`backend/requirements.txt`): `fastapi==0.115.6`, `pydantic==2.9.2`, `uvicorn==0.34.0`, `rasterio==1.4.3`, `numpy==2.2.1`, `scipy==1.15.0`, `pyproj==3.7.2`, `httpx>=0.27.0`, `pytest==8.3.4`, `heat1d @ git+…@6b25d0f01f015ea815704a6cd0a67af3b9fc0fb8#subdirectory=python`, `numba==0.67.0`, `llvmlite==0.49.0`, `astropy==8.0.1`, `spiceypy==6.0.0`. `astropy-iers-data` bilinçli olarak pinlenmemiş.

**Sürüm etiketi:** yok. `git describe --tags --always` → `fea37ef`.

---

## 2. API yüzeyi

18 route, tamamı `backend/app/main.py` içinde.

| Metot | Yol | Amaç | İstek modeli | Yanıt (üst düzey anahtarlar) | dosya:satır |
|---|---|---|---|---|---|
| GET | `/api/health` | Servis + grid yüklü mü | — | `status`, `version`, `dem_loaded`, `grid_shape` | `main.py:448-453` |
| GET | `/api/rovers` | Araç katalogu | — | `default_rover_id`, `rovers[]` | `main.py:456-461` |
| POST | `/api/load-preprocessed` | P1 `.npy` gridlerini yükle **(durum değiştirir)** | `LoadPreprocessedRequest` | `status`, `metadata` | `main.py:464-477` |
| POST | `/api/load-dem` | GeoTIFF'ten grid türet **(durum değiştirir, diske yazar)** | `LoadDEMRequest` | `status`, `metadata` | `main.py:480-495` |
| GET | `/api/cell-telemetry` | Tek hücre sorgusu + maliyet ayrıştırma | query: `row`, `col`, `rover_id?` | `row`,`col`,`lon`,`lat`,`altitude_m`,`thermal_c`,`thermal_min_c`,`resolution_m`,`span_km`,`cost_breakdown`,`layer_validity` | `main.py:498-573` |
| POST | `/api/plan` | Tek rota + simülasyon **(korridor durumu yazar)** | `PlanRequest` | `status`,`astar_metrics`,`summary`,`geojson`,`corridor`,`route_statistics`,`execution`,`rover`,`waypoints` | `main.py:576-737` |
| POST | `/api/replan` | Tetikleyici değerlendirip gerekirse yeniden planla | `ReplanRequest` | `replanned`,`triggers`,`evaluated`,`skipped`,`reason` \| `plan` | `main.py:740-782` |
| POST | `/api/pose` | Pozu korridora karşı değerlendir | `PoseRequest` | BİLİNMİYOR — gövde denetimde okunmadı | `main.py:820-883` |
| POST | `/api/plan-4d` | Zaman-genişletilmiş planlama | `Plan4DRequest` | `path_pixels`,`path_pixels_coarse`,`path_states`,`metrics`,`shadow_model`,`n_slices`,`slice_hours`,`slice_hours_source`,`horizon_hours`,`coarsen`,`effective_resolution_m`,`rover_id` | `main.py:885-1174` |
| POST | `/api/plan-multi` | Seçilen profillerle çoklu plan | `PlanMultiRequest` | `results[]` | `main.py:1232-1266` |
| POST | `/api/compare` | Dört profilin tamamıyla karşılaştırma | `CompareRequest` | `start`,`goal`,`results[]`,`comparison` | `main.py:1269-1295` |
| GET | `/api/layers/{layer_name}` | Grid katmanı (JSON veya f32) | query: `downsample`,`format`,`rover_id`,`w_*` | JSON: `layer`,`shape`,`data`,`metadata`; f32: ham gövde + `X-Layer-*` başlıkları | `main.py:1298-1416` |
| GET | `/api/terrain` | 3-B sahne manifestosu | query: `rover_id`,`w_*` | `grid`,`georeference`,`elevation`,`binary_format`,`rover`,`weights`,`layers` | `main.py:1418-1467` |
| GET | `/api/illumination-series` | Zaman dilimli aydınlanma serisi | query: `start_utc`,`n_slices`,`slice_hours`,`downsample`,`format`,`field` | `slices`,`slice_hours`,`start_utc`,`grid`,`shadow_model`,`thermal_model`,`sun[]`,`fields`,`binary_format` | `main.py:1518-1678` |
| GET | `/api/reference-missions` | Yayımlanmış gerçek görev figürleri | — | `reference_summary()` çıktısı | `main.py:1680-1691` |
| GET | `/api/profiles` | Görev profili katalogu | — | profil id → profil sözlüğü | `main.py:1693-1695` |
| GET | `/api/scenarios` | Senaryo katalogu | — | `scenarios` | `main.py:1697-1700` |
| POST | `/api/scenarios/{scenario_id}/load` | Senaryo yükle **(durum değiştirir)** | path: `scenario_id` | senaryo + `load_status` | `main.py:1703-1732` |

**Exception handler:** `UnknownRoverError` → HTTP 422, gövde `{"detail": str(exc)}` (`main.py:140-145`).

**CORS:** `LUNAPATH_CORS_ORIGINS` ortam değişkeni, varsayılan `*`; `allow_credentials` yalnızca origin listesi `*` değilse `True` (`main.py:115-137`). `expose_headers` = `BINARY_LAYER_HEADERS + SERIES_HEADERS` (`main.py:136`).

---

## 3. Veri modelleri

### `StartGoalPixel` — `main.py:320-322`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `row` | `int` | evet | — | route içinde `0 <= row < rows` (`main.py:591`) | grid satır indeksi (0 = kuzey kenarı, `terrain.py` `row_axis: "north-to-south"`) |
| `col` | `int` | evet | — | route içinde `0 <= col < cols` (`main.py:596`) | grid sütun indeksi (0 = batı kenarı) |

### `StartGoalGeo` — `main.py:325-327`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `lon` | `float` | evet | — | `lonlat_to_pixel` sınır kontrolü (`serializer.py:189-190`) | derece (doğu pozitif) |
| `lat` | `float` | evet | — | aynı; ayrıca `-80°` kuzeyi reddedilir (`serializer.py:106-107,160`) | derece (güney negatif) |

### `PlanWeights` — `main.py:330-341`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `w_slope` | `float` | hayır | `constants.W_SLOPE` | `0.0 <= v <= 2.0`, aksi `ValueError` (`main.py:336-341`) | boyutsuz ağırlık |
| `w_energy` | `float` | hayır | `constants.W_ENERGY` | aynı | boyutsuz ağırlık |
| `w_shadow` | `float` | hayır | `constants.W_SHADOW` | aynı | boyutsuz ağırlık |
| `w_thermal` | `float` | hayır | `constants.W_THERMAL` | aynı | boyutsuz ağırlık |

### `PlanRequest` — `main.py:344-349`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `start` | `StartGoalPixel \| StartGoalGeo` | evet | — | union ayrıştırma; ikisi de tutmazsa 422 | — |
| `goal` | aynı | evet | — | aynı | — |
| `rover_id` | `str` | hayır | `"lpr_1"` (`constants.py:207`) | `get_rover` → `UnknownRoverError` → 422 | — |
| `weights` | `PlanWeights` | hayır | `PlanWeights()` | alan bazında | — |
| `include_simulation` | `bool` | hayır | `True` | — | — |

### `ReplanRequest` — `main.py:374-385`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `current` | `StartGoalPixel \| StartGoalGeo` | evet | — | — | — |
| `goal` | aynı | evet | — | — | — |
| `rover_id` | `str` | hayır | `"lpr_1"` | `get_rover` | — |
| `weights` | `PlanWeights` | hayır | `PlanWeights()` | alan bazında | — |
| `state` | `dict[str, float]` | hayır | `{}` | `_reject_non_finite_telemetry` — NaN/inf reddedilir (`main.py:352-371`) | anahtara göre değişir; §5'teki tetikleyici tablosuna bakın |
| `force` | `bool` | hayır | `False` | — | — |

### `Plan4DRequest` — `main.py:388-415`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `start`, `goal` | union | evet | — | — | — |
| `rover_id` | `str` | hayır | `"lpr_1"` | `get_rover` | — |
| `weights` | `PlanWeights` | hayır | `PlanWeights()` | alan bazında | — |
| `n_slices` | `int \| None` | hayır | `None` | `ge=2, le=MAX_PLAN_4D_SLICES` → `le=1000` (`main.py:395`; sabit `main.py:151`) | dilim sayısı |
| `horizon_hours` | `float \| None` | hayır | `None` | `gt=0.0, le=168.0` | saat |
| `slice_hours` | `float \| None` | hayır | `None` | `gt=0.0, le=24.0` | saat |
| `coarsen` | `int` | hayır | `4` | `ge=1, le=16` | grid kaba indirgeme faktörü |
| `start_utc` | `str \| None` | hayır | `None` | biçim doğrulaması BİLİNMİYOR — Pydantic tipi düz `str` | ISO-8601 UTC |

Ek bütçe kontrolü: `_check_cube_budget` (`main.py:186-203`) — `n_slices * H * W * 8 * 2` baytı `MAX_PLAN_4D_CUBE_BYTES = 512 MiB` (`main.py:157`) ile sınırlar, aşımda 422 ve **sığacak dilim sayısını söyler**.

### `PlanMultiRequest` — `main.py:423-427` / `CompareRequest` — `main.py:430-433`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `start`, `goal` | `conlist(int, min_length=2, max_length=2)` (`main.py:420`) | evet | — | uzunluk tam 2; sınır kontrolü `_validate_pixel_endpoints` (`main.py:1214-1229`) | grid indeksi |
| `profiles` | `list[str]` | evet (yalnız plan-multi) | — | **doğrulanmıyor** — bilinmeyen id sonuç dizisinde `error` alanıyla döner (`main.py:1240-1251`) | — |
| `rover_id` | `str` | hayır | `"lpr_1"` | `get_rover` | — |

Not: bu iki uç **coğrafi koordinat kabul etmiyor** — yalnızca piksel çifti. `/api/plan` union kabul ediyor.

### `LoadDEMRequest` — `main.py:436-440` / `LoadPreprocessedRequest` — `main.py:443-445`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `dem_file` | `str` | evet | — | `_resolve_dem_path` — DEM dizini dışına çıkmayı 422 ile reddeder (`main.py:287-303`) | dosya adı |
| `target_resolution_m` | `float` | hayır | `80` | **doğrulanmıyor** | metre/piksel |
| `use_cache` | `bool` | hayır | `True` | — | — |
| `weights` | `dict[str, float] \| None` | hayır | `None` | **`PlanWeights` değil — aralık doğrulaması yok** | boyutsuz |
| `processed_dir` | `str \| None` | hayır | `None` | **yol kısıtlaması yok** (`_resolve_dem_path` benzeri koruma uygulanmıyor) | dizin yolu |

### `/api/layers/{layer_name}` sorgu parametreleri — `main.py:1298-1327`

| Alan | Tip | Zorunlu | Varsayılan | Doğrulama | Birim |
|---|---|---|---|---|---|
| `layer_name` | path `str` | evet | — | 8 elemanlı beyaz liste, aksi 400 (`main.py:1325-1336`) | — |
| `downsample` | `int` | hayır | `1` | `Query(ge=1, le=50)` (`main.py:1304`) | adım |
| `format` | `str` | hayır | `"json"` | `pattern="^(json\|f32)$"` (`main.py:1310`) | — |
| `rover_id` | `str` | hayır | `DEFAULT_ROVER_ID` | `get_rover` | — |
| `w_slope`, `w_energy`, `w_shadow`, `w_thermal` | `float \| None` | hayır | `None` | **hiçbir doğrulama yok** (`main.py:1319-1322`) | boyutsuz |

---

## 4. Hesaplama çekirdeği

### Algoritma

8-komşulu A*, düz NumPy dizileri üzerinde (`pathfinder._astar_core`, `pathfinder.py:390-639`). Kenar maliyeti trapez ara değerleme, sezgisel oktil. Zaman-genişletilmiş varyant `pathfinder_4d.astar_4d` ayrı bir amaç fonksiyonu minimize ediyor — birimi **ağırlıklı saat**, 2-B planlayıcınınki **ağırlıklı metre**; kod bunu açıkça söylüyor (`pathfinder.py:776-778`, `cost_units: "weighted_metres"`).

### Dört bileşen

`default_cost_map()` dört katmanı bağlıyor (`costmap.py:251-268`):

| Bileşen (`layer.name`) | Sınıf | Ağırlık anahtarı | Varsayılan validity | dosya:satır |
|---|---|---|---|---|
| `"slope"` | `SlopeLayer` | `w_slope` | `metadata.layer_validity["slope"]`, yoksa `"DERIVED"` | `costmap.py:196,264` |
| `"energy"` | `EnergyLayer` | `w_energy` | daima `"MODEL"` — girdi gridi değil fizik formülü | `costmap.py:207,265` |
| `"shadow"` | `ShadowLayer` | `w_shadow` | `layer_validity["shadow_ratio"]`, yoksa `"DERIVED"` | `costmap.py:226,266` |
| `"thermal"` | `ThermalLayer` | `w_thermal` | `layer_validity["thermal"]`, yoksa `"MODEL"` | `costmap.py:237,267` |

Skaler referans formülleri: `f_slope` (`cost_engine.py:68`), `f_energy_cell` (`:170`), `f_shadow_cell` (`:247`), `f_thermal` (`:390`).

### Ağırlıkların kaynağı

`resolve_weights(weights, rover)` (`cost_engine.py:51-63`): rover'ın kendi AHP varsayılanları (`default_weights`, `:40-49`) üzerine yalnızca `_WEIGHT_KEYS`'te (`:26-31`) bulunan anahtarlar yazılır. **Normalizasyon yok, toplam kontrolü yok.**

Üç katmanlı zincir:
1. Rover varsayılanı — `constants.ROVERS[rover_id]` (`constants.py:64`).
2. İstek override'ı — `PlanWeights` gövdesi veya `/api/layers` sorgu parametreleri.
3. Görev profili — `scenarios.MISSION_PROFILES[id]["weights"]`, `/api/plan-multi` ve `/api/compare` tarafından geçilir (`main.py:1257,1281`).

Birleşme noktası `grids_for_rover()` (`rover_grids.py`). Traversability **her çağrıda koşulsuz yeniden hesaplanıyor** çünkü `default_rover_id` yalnızca bir etiket ve maskeyle uyuşmayabilir (`rover_grids.py:36-54`). Maliyet gridi ise beş koşuldan biri sağlanırsa yeniden hesaplanıyor: rover farklı, ağırlıklar farklı, maske eşleşmiyor, `cost` yok, ya da `cost_model` bu build'inkinden farklı (`rover_grids.py:75-81`).

### Ara değerlerin akıbeti

Kenar başına hesaplanan cezalar toplanıp atılıyor. Yol boyunca saklanan tek toplulaştırma `_compute_path_metrics()` çıktısı (`pathfinder.py:667-783`) ve `simulation.RoverState` başına telemetri. Bileşen bazında **rota toplamı** hiçbir yerde biriktirilmiyor — `cost_breakdown` yalnızca tek hücre için var.

---

## 5. Kısıtlar

### Sert kısıtlar (kenarı tamamen reddeder)

`_astar_core` içinde kenar başına uygulanıyor (`pathfinder.py:582-618`). Sayaç anahtarları `pathfinder.py:524-530`:

| Sayaç anahtarı | Limit kaynağı | Birim | İhlalde | Uygulama yeri |
|---|---|---|---|---|
| `step_slope` | `rover["slope_max_deg"]` veya profil `max_slope_deg` (daha küçüğü) | derece | kenar atlanır | `pathfinder.py:588` |
| `lateral_slope` | `rover["slope_lateral_max_deg"]` | derece | kenar atlanır | `pathfinder.py:599` |
| `thermal_barrier` | termal zarf | °C | kenar atlanır | `pathfinder.py:604` |
| `slope_barrier` | `geometric_barrier_terms` `-inf` döndürünce | derece | kenar atlanır | `pathfinder.py:611` |
| `lateral_barrier` | aynı | derece | kenar atlanır | `pathfinder.py:618` |

Ayrıca hücre düzeyinde `traversable` maskesi: geçilemez hücre `cost = inf`. Başlangıç veya hedef geçilemezse **HTTP 422**, mesajda rover adı ve sebep sınıfı (`main.py:602-618`). `[canlı sonda]` `{"start":{"row":195,"col":33},…}` → `422 {"detail":"start (195, 33) is not traversable for LPR-1 (Varsayilan) (slope limit or extreme thermal)."}`

`constraints_applied` her başarılı planda dışa açılıyor: `max_slope_deg`, `slope_lateral_max_deg`, `source` ∈ {`"profile"`,`"rover"`} (`pathfinder.py:173-181`).

### Yumuşak cezalar

Log-bariyer: `-mu * sum(log(slack))`, `mu = LOG_BARRIER_MU = 0.1` (`constants.py:9`). Üç ayrı uygulama:

- `edge_barrier_penalty()` — planlayıcının kullandığı; eğim + yanal (`cost_engine.py:605-643`).
- `geometric_barrier_terms()` — ortak yardımcı, profil ceilingi de kabul eder (`cost_engine.py:646-677`).
- `log_barrier_penalty()` — tam spec formu, SoC terimi dahil; `total_edge_cost()` kullanır (`cost_engine.py:680-737`).
- `thermal_barrier_terms()` — soğuk/sıcak duvar (`cost_engine.py:538-602`).

Hücre maliyeti tabanı `MIN_CELL_COST = 0.01` (`costmap.py:19,94,156`). Gölge cezası üsteli `_SHADOW_LAMBDA = 3.0` (`cost_engine.py:233`).

### Profil kısıtları — simülasyon sonrası doğrulanan

`check_profile_constraints()` (`scenarios.py:99-161`). `[canlı sonda]` `/api/compare` `balanced` profili:

| Kısıt anahtarı | Limit | Birim | Sert mi | `enforced_in_search` | Nasıl doğrulanıyor |
|---|---|---|---|---|---|
| `max_slope_deg` | 25.0 | derece | **sert** | `true` | aramada uygulanır; `actual` daima `null` (yapısal) |
| `max_shadow_h` | 40.0 | saat | yumuşak | `false` | `summary.max_continuous_shadow_h` ile karşılaştırılır (`scenarios.py:130-138`) |
| `max_energy_wh` | 4000.0 | Wh | yumuşak | `false` | `summary.total_energy_consumed_wh` (`scenarios.py:139-149`) |
| `min_soc` | 0.2 | kesir (0–1) | yumuşak | `false` | `summary.min_battery_pct / 100` (`scenarios.py:151-160`) |

Bu kısıtlar **istek gövdesinden değiştirilemez** — yalnızca profil katalogundan gelirler. `/api/plan` bu kontrolü hiç çalıştırmaz.

---

## 6. Kataloglar ve sabitler

### Araç katalogu — 4 kayıt

`constants.ROVERS` (`constants.py:64`), varsayılan `DEFAULT_ROVER_ID = "lpr_1"` (`constants.py:207`). `[canlı sonda]` `/api/rovers`:

| `id` (birebir) | `name` | `mass_kg` | `v_max_ms` | `e_cap_wh` | `slope_max_deg` | `slope_lateral_max_deg` | `soc_min_pct` | `h_max_shadow_h` | varsayılan ağırlıklar (slope/energy/shadow/thermal) |
|---|---|---|---|---|---|---|---|---|---|
| `lpr_1` | `LPR-1 (Varsayilan)` | 450.0 | 0.2 | 5420.0 | 25.0 | 18.0 | 0.2 | 50.0 | 0.409 / 0.259 / 0.142 / 0.19 |
| `luvmi_m` | `LUVMI-M` | 40.0 | 0.05 | 1400.0 | 25.0 | 15.0 | 0.2 | 4.0 | 0.4 / 0.3 / 0.3 / 0.0 |
| `nasa_viper` | `NASA VIPER` | 447.0 | 0.20 | 5420.0 | 15.0 | 15.0 | 0.2 | 50.0 | 0.35 / 0.25 / 0.2 / 0.2 |
| `cnsa_yutu_2` | `CNSA Yutu-2` | 135.0 | 0.0556 | 1500.0* | 20.0 | 15.0 | 0.3 | 2.0 | 0.5 / 0.3 / 0.2 / 0.0 |

Her kayıtta ayrıca `sensor_payload_w` ve `sensor_heater_w` (dördünde de `null`) ve bir `declared_only` bloğu var: `f_net_n`, `regen_efficiency`, `thermal_tau_s`, `h_design_shadow_h`. **`declared_only` adı, bu değerlerin beyan edildiğini ama hesaplamada kullanılmadığını ima ediyor; bu iddia denetimde kod üzerinden doğrulanmadı — BİLİNMİYOR.**

\* Yutu-2'nin Wh cinsinden uçuş batarya kapasitesi kamuya açık teknik belgelerde yayımlanmadığından, 1.500 Wh simülasyon varsayımıdır; doğrulanmış araç spesifikasyonu değildir.

### Görev profili katalogu — 4 kayıt

`scenarios.MISSION_PROFILES` (`scenarios.py:14`). `id` string'leri birebir: `balanced`, `energy_saver`, `fast_recon`, `shadow_traverse` (`scenarios.py:15,32,49,66`). **Varsayılan profil kavramı yok** — `/api/plan` profil almaz, `/api/compare` dördünü birden koşar.

| `id` | `name` | ağırlıklar (slope/energy/shadow/thermal) | `max_shadow_h` | `max_slope_deg` | `max_energy_wh` | `min_soc` | `color` |
|---|---|---|---|---|---|---|---|
| `balanced` | Dengeli Kesif | 0.409 / 0.259 / 0.142 / 0.19 | 40.0 | 25.0 | 4000.0 | 0.2 | `#3B82F6` |
| `energy_saver` | Enerji Tasarrufu | 0.25 / 0.45 / 0.15 / 0.15 | 30.0 | 20.0 | 2500.0 | 0.35 | `#22C55E` |
| `fast_recon` | Hizli Kesif | 0.5 / 0.15 / 0.1 / 0.25 | 50.0 | 25.0 | 5000.0 | 0.1 | `#EF4444` |
| `shadow_traverse` | Golge Gecis | 0.2 / 0.15 / 0.3 / 0.35 | 45.0 | 25.0 | 4000.0 | 0.25 | `#A855F7` |

Her profil ayrıca `constraint_handling` sözlüğü yayımlıyor: `max_slope_deg → "enforced_in_search"`, diğer üçü `"verified_after_simulation"`.

### Yeniden planlama tetikleyicileri — 7 kayıt

`_TRIGGER_INPUTS` (`replan_triggers.py:144-157`). Anahtarlar ve gerektirdikleri `state` alanları:

| `trigger_id` | Gerekli `state` anahtarları | Opsiyonel |
|---|---|---|
| `soc_deviation` | `actual_soc`, `planned_soc` | — |
| `inner_temperature` | `actual_inner_c`, `predicted_inner_c` | — |
| `time_drift` | `drift_minutes` | — |
| `corridor_violation` | `lateral_offset_m`, `half_width_m` | — |
| `comm_window` | `comm_minutes_remaining` | — |
| `localization_uncertainty` | `localization_covariance_m`, `half_width_m` | — |
| `slip_accumulation` | `map_progress_m`, `odometer_claim_m` | `corridor_length_m` (`replan_triggers.py:161-163`) |

### Fiziksel ve yapılandırma sabitleri

| Sabit | Değer | Birim | dosya:satır |
|---|---|---|---|
| `LOG_BARRIER_MU` | 0.1 | boyutsuz | `constants.py:9` |
| `MIN_CELL_COST` | 0.01 | ağırlıklı maliyet | `costmap.py:19` |
| `_SHADOW_LAMBDA` | 3.0 | boyutsuz | `cost_engine.py:233` |
| `SLOPE_COMFORTABLE_DEG` | `_DEFAULT_ROVER["slope_comfortable_deg"]` | derece | `constants.py:344` |
| `MAX_LAYER_CELLS` | 65536 | hücre | `main.py:165` |
| `MAX_SERIES_BYTES` | 64 MiB | bayt | `main.py:172` |
| `MAX_SERIES_WORKING_BYTES` | 512 MiB | bayt | `main.py:183` |
| `MAX_PLAN_4D_SLICES` | 1000 | dilim | `main.py:151` |
| `MAX_PLAN_4D_CUBE_BYTES` | 512 MiB | bayt | `main.py:157` |
| `DEFAULT_HORIZON_WAIT_PAD_SLICES` | 20 | dilim | `main.py:208` |
| `MAX_TRACKED_CORRIDORS` | 32 | korridor | `main.py:106` |
| `_LAT_SOUTH_THRESHOLD` | -80.0 | derece | `serializer.py:107` |
| `REGOLITH_THERMAL_TAU_S` | (bkz. kaynak) | saniye | `thermal_model.py` |

---

## 7. Hata ve başarısızlık yolları

### Gözlemlenen hata gövdeleri `[canlı sonda]`

| Durum | HTTP | Gövde | Kod |
|---|---|---|---|
| Grid yüklü değil | 503 | `{"detail":"Grid data not loaded. Run the P1 pipeline and call POST /api/load-preprocessed, or wait for server startup to complete."}` | `main.py:256-263`, `:271-278` |
| Grid dosyası yok (`/api/load-preprocessed`) | 404 | `FileNotFoundError` metni | `main.py:472-473` |
| Sınır dışı hedef | 422 | `{"detail":"goal (900, 10) is outside the 500x500 grid."}` | `main.py:596-600` |
| Sınır dışı hücre sorgusu | 422 | `{"detail":"(999, 1) is outside the 500x500 grid."}` | `main.py:518-522` |
| Aralık dışı ağırlık (gövde) | 422 | Pydantic dizisi: `{"type":"value_error","loc":["body","weights","w_slope"],"msg":"Value error, weight must be in [0.0, 2.0], got 5.0",…}` | `main.py:336-341` |
| Bilinmeyen rover | 422 | `{"detail":"\"Unknown rover_id: 'nope'. Available: ['lpr_1', 'luvmi_m', 'nasa_viper', 'cnsa_yutu_2']\""}` | `main.py:140-145` |
| Bilinmeyen katman | **400** | `{"detail":"Layer must be one of ('elevation', 'slope', 'aspect', 'thermal', 'thermal_min', 'shadow_ratio', 'cost', 'traversable')"}` | `main.py:1335-1336` |
| Geçilemez başlangıç | 422 | `{"detail":"start (195, 33) is not traversable for LPR-1 (Varsayilan) (slope limit or extreme thermal)."}` | `main.py:602-610` |
| JSON hücre bütçesi aşımı | 422 | `"cost at downsample=1 is 250000 cells, over the 65536-cell response budget. Use downsample=2 or higher."` | `main.py:1391-1403` |

Not: bilinmeyen katman **400** dönerken diğer tüm girdi hataları 422 dönüyor. Tutarsızlık kayda geçirilmiştir.

### Yol bulunamadığında

Zincir:

1. `_astar_core` yol bulamaz → `(None, nodes_expanded, rejections, inf)` (`pathfinder.py:639`).
2. `_no_path_reason(rejections, rover, profile_slope_max)` **düzyazı tanı cümlesi** kurar (`pathfinder.py:828-865`). Sayaçları üç gruba toplar — yanal (`lateral_slope + lateral_barrier`), boyuna (`step_slope + slope_barrier`), termal (`thermal_barrier`) — ve her biri için kaç kenarın hangi limiti aştığını yazar. Hiçbiri sıfırdan büyük değilse düz `"No path found"` döner.
3. `_empty_result(...)` bunu `metrics` ile paketler: `edges_rejected` (dolu sayaç sözlüğü) ve `nodes_expanded` korunur, diğer metrikler `_zero_metrics` sıfır/`None` değerleriyle doldurulur (`pathfinder.py:785-825`).
4. `main.py:627-628`: `if astar_result.get("error"): raise HTTPException(status_code=404, detail=astar_result["error"])`.

**Sonuç: HTTP 404, gövde yalnızca `{"detail": "<düzyazı cümle>"}`. `edges_rejected` sayaçları ve `nodes_expanded` üretilip atılıyor. Kısmi sonuç dönmüyor.**

Denetimde bu yol **canlı olarak tetiklenemedi** — grid %84.0 geçilebilir ve denenen üç zorlu senaryo (`nasa_viper` ve `cnsa_yutu_2` ile (5,5)→(495,495)) yol buldu. Kod yolu okuyarak ve testlerden doğrulandı: `test_pathfinder.py:92` (`test_a_disconnected_goal_reports_no_path`), `test_review3_fixes.py:102` (`assert "roll-over" in result["error"]`), `test_review4_fixes.py:152`.

`/api/plan-multi` ve `/api/compare` farklı davranıyor: bunlar **HTTP 200** döner ve başarısızlık `results[]` içindeki `error` alanında taşınır (`main.py:1240-1251`) — ancak orada `metrics` da yanıtta kalır, yani `edges_rejected` bu iki uçta **görünür**.

### Diğer başarısızlıklar

| Durum | HTTP | Kod |
|---|---|---|
| Simülasyon istisnası | 500, `"Internal simulation error."` (detay loglanır) | `main.py:644-646` |
| Projeksiyon geometriyi reddederse | 422, `ValueError` metni | `main.py:702-709` |
| Serileştirme istisnası | 500, `"Internal serialization error."` | `main.py:710-712` |
| Korridor üretilemezse | istisna yok — `corridor: null`, uyarı loglanır | `main.py:679-682` |
| Senaryo bulunamazsa | 404 | `main.py:1706-1707` |
| Senaryo DEM'i yoksa | 200 + `load_status: "dem_missing"` \| `"no_dem_declared"` | `main.py:1714-1732` |
| 4-B küp bütçesi aşımı | 422, sığacak dilim sayısı mesajda | `main.py:194-203` |

---

## 8. Performans ve durum

### Ölçülen süre

`astar_metrics.computation_time_ms` — `time.perf_counter()` farkı, yalnızca `astar()` çağrısını kapsar (`pathfinder.py:149`, `:780`). `nodes_expanded` de dışa açık (`pathfinder.py:781`).

`[canlı sonda]` `POST /api/plan`, (60,60)→(440,440), `lpr_1`, 500×500 grid:

| Koşum | `w_slope` | Duvar süresi | `computation_time_ms` | `nodes_expanded` | `total_distance_m` |
|---|---|---|---|---|---|
| 1 | 0.409 | 2840.2 ms | 753.1 | 111770 | 3028.34 |
| 2 | 0.459 | 2903.0 ms | 746.6 | 111947 | 3028.32 |
| 3 | 0.509 | 4570.7 ms | 2204.8 | 112107 | 3031.19 |
| 4 | 0.409 (koşum 1'in tekrarı) | 4847.8 ms | 2649.4 | 111770 | 3028.34 |

Duvar süresi ile `computation_time_ms` arasındaki ~2 s'lik fark, ölçülmeyen işi kapsar: `grids_for_rover` yeniden hesaplaması, `simulate_path`, `build_corridor`, `build_plan_response`.

### Önbellek

- **Plan yolunda önbellek yok.** Koşum 4, koşum 1 ile birebir aynı girdiyi kullanıyor ve daha hızlı değil (4847.8 ms vs 2840.2 ms). Sonuç birebir aynı (`3028.34` m, `111770` düğüm) ama yeniden hesaplanıyor.
- **Disk önbelleği yalnızca DEM yolunda.** `load_and_preprocess_dem` `_cache_key(dem_path, target_resolution_m, resolved_weights)` ile `backend/data/cache/` altına `.npy` yazar/okur (`data_loader.py:258-262,378-379,412-459`). `/api/load-preprocessed` bu önbelleği kullanmaz.
- **`grids_for_rover` kısmi yeniden kullanım yapar** ama traversability'yi **her zaman** yeniden hesaplar — bilinçli güvenlik kararı, kaynak yorumunda ~0.05 s olarak ölçülmüş (`rover_grids.py:36-45`).

### Durum yönetimi

Tüm durum `app.state` üzerinde, süreç içi, kalıcı değil:

| Öznitelik | İçerik | Yazan |
|---|---|---|
| `app.state.grids` | Yüklü grid sözlüğü — **tek kaynak** | `_set_grids` (`main.py:217-218`), çağıranlar `main.py:229,238,241,476,494,1721` |
| `app.state.active_corridor` | Son başarılı planın korridoru | `main.py:723` |
| `app.state.active_corridor_id` | 12 haneli hex kimlik | `main.py:724` |
| `app.state.active_corridor_rover_id` | O planın rover'ı | `main.py:725` |
| `app.state.corridors` | id → korridor kayıt defteri, `MAX_TRACKED_CORRIDORS = 32` ile sınırlı, FIFO tahliye | `main.py:726-735` |

Başlangıçta `_startup_load_grids()` P1 gridlerini yüklemeyi dener; başarısızsa uyarı loglar ve `None` bırakır (`main.py:225-241`).

**Eşzamanlılık notu (kod yorumundan):** endpoint'ler `sync def` olduğu için threadpool'da koşuyor; iki eşzamanlı `/api/plan` tek `active_corridor` slotu için yarışıyor. `corridor_id` bu yüzden var (`main.py:98-105`, `:714-721`).

---

## 9. T-1…T-12 cevapları

### T-1 — Analiz yetenekleri

| Soru | Kategori | Cevap | Kanıt |
|---|---|---|---|
| Özet metrikler | **A** | `summary` (18 alan) + `astar_metrics` (18 alan) + `route_statistics` (5 alan) `/api/plan` yanıtında | `serializer.py:310-317`, `simulation.summarize_simulation`, `route_analysis.py:22-34` |
| Maliyet ayrıştırma | **A (hücre) / C (rota)** | Hücre başına `cost_breakdown` `/api/cell-telemetry`'de dışa açık. Rota geneli bileşen toplamı hiçbir yerde biriktirilmiyor. | `costmap.py:121-159`, `main.py:552,571` |
| Konuma özgü sorgu | **A** | `/api/cell-telemetry?row=&col=&rover_id=`; ayrıca `waypoints[]` her adım için 19 alan taşıyor | `main.py:498-573`; `serializer.states_to_waypoints` |
| Kısıt yakınlığı | **A (profil kısıtları) / B (bariyer slack'leri)** | `constraint_check` `limit`+`actual` verir; bariyer içi slack'ler saklanmaz. Ayrıntı T-8. | `scenarios.py:99-161`, `main.py:1210`; karşıt: `cost_engine.py:705,710,717` |
| Alternatif çözüm maliyetleme | **C** | Kullanıcının verdiği bir yolu puanlayan endpoint yok. `total_edge_cost()` var ama hiçbir route çağırmıyor. | `cost_engine.py:742`; `grep` ile main.py'de çağrı yok |
| Parametre değiştirip yeniden koşma | **A** | `/api/plan` her çağrıda `weights` + `rover_id` kabul eder; `/api/plan-multi` profil listesi alır | `main.py:344-349`, `:1232-1266` |
| Başarısızlık analizi | **B (başarısızlıkta) / A (başarıda)** | Başarılı planda `edges_rejected` + `nodes_expanded` `astar_metrics` içinde dışa açık. **Başarısızlıkta** tanı düzyazı olarak 404'e konuyor ve yapılandırılmış sayaçlar atılıyor. Ayrıntı T-11. | `pathfinder.py:172,828-865,812-825`; `main.py:627-628` |
| Çoklu karşılaştırma | **A** | `/api/compare` dört profili koşar + `comparison` bloğu; `/api/plan-multi` seçilen profilleri | `main.py:1269-1295`, `:1232-1266` |

### T-2 — Maliyet bileşenlerinin kimlikleri

**Dört bileşen.** Kod içindeki birebir `layer.name` string'leri: `"slope"`, `"energy"`, `"shadow"`, `"thermal"` (`costmap.py:196,207,226,237`). Bunlar `cost_breakdown` sözlüğünün anahtarları olarak yanıtta aynen görünür — `[canlı sonda]` `{"slope":0.00573,"energy":0.06424,"shadow":0.04561,"thermal":0.19000,"total":0.30557}`.

**Ağırlıklar tek bir sözlükte**, ayrı alanlar değil. Anahtarlar `_WEIGHT_KEYS = ("w_slope","w_energy","w_shadow","w_thermal")` (`cost_engine.py:26-31`). Katman → ağırlık eşlemesi `default_cost_map`'te sabit (`costmap.py:264-267`).

Dikkat: katman adı ile ağırlık anahtarı **birebir aynı değil** — `"shadow"` katmanı `w_shadow` ağırlığını alır, ama grid katmanının adı `shadow_ratio`'dur (`main.py:1331`). AI katmanı üç farklı ad uzayını karıştırmamalı: bileşen adı (`shadow`), ağırlık anahtarı (`w_shadow`), grid katmanı adı (`shadow_ratio`).

**Kategori: A.**

### T-3 — Ağırlık aralığı ve doğrulama

| Yüzey | Aralık | Doğrulama yeri | Sınır dışında |
|---|---|---|---|
| `POST /api/plan`, `/api/replan`, `/api/plan-4d` gövdesi | `[0.0, 2.0]` | `PlanWeights._check_range` field_validator (`main.py:336-341`) | **HTTP 422**, Pydantic hata dizisi, `msg: "Value error, weight must be in [0.0, 2.0], got 5.0"` `[canlı sonda]` |
| `GET /api/layers/*` sorgu parametreleri | **sınırsız** | **yok** (`main.py:1319-1322`) | HTTP 200. `[canlı sonda]` `w_slope=999` → `X-Layer-Max: 981.55`; `w_slope=-5` → HTTP 200 |
| `POST /api/load-dem`, `/api/load-preprocessed` gövdesindeki `weights` | **sınırsız** | **yok** — `dict[str,float]`, `PlanWeights` değil (`main.py:440,445`) | doğrulanmadı (durum değiştiren uç, sondalanmadı) |

**Normalizasyon yok.** `resolve_weights()` yalnızca varsayılanların üzerine yazar; toplamın 1 olması gerekmez ve kontrol edilmez (`cost_engine.py:51-63`).

**Kategori: A** (plan yolu için), fakat `/api/layers` doğrulama boşluğu E-4'te tekrar kaydedildi.

### T-4 — Kısıt anahtarları ve limitleri

§5'teki üç tablo. Özet:

**Sert (aramada uygulanır, kenar reddeder):** `step_slope`, `lateral_slope`, `thermal_barrier`, `slope_barrier`, `lateral_barrier` (`pathfinder.py:524-530`, uygulama `:582-618`). Limitler `rover["slope_max_deg"]`, `rover["slope_lateral_max_deg"]` ve profil `max_slope_deg`; **istek gövdesinden doğrudan değiştirilemez**, yalnızca `rover_id` veya profil seçimiyle.

**Yumuşak (log-bariyer cezası, `mu = 0.1`):** eğim, yanal eğim, SoC, termal soğuk/sıcak duvar (`cost_engine.py:538-737`).

**Profil kısıtları (simülasyon sonrası doğrulanır):** `max_shadow_h` (saat), `max_energy_wh` (Wh), `min_soc` (0–1 kesir), artı yapısal `max_slope_deg` (derece). Yalnızca `/api/plan-multi` ve `/api/compare` yolunda; **istek gövdesinden değiştirilemez**.

**Kategori: A** (limitler `constraints_applied` ve `constraint_check` ile dışa açık).

### T-5 — Katalog kimlikleri

**Rover: 4 kayıt.** `id` string'leri birebir: `lpr_1`, `luvmi_m`, `nasa_viper`, `cnsa_yutu_2`. Varsayılan `lpr_1` (`constants.py:207`, `[canlı sonda]` `default_rover_id: "lpr_1"`).

**Profil: 4 kayıt.** `id` string'leri birebir: `balanced`, `energy_saver`, `fast_recon`, `shadow_traverse` (`scenarios.py:15,32,49,66`). **Varsayılan profil yok** — katalog bir varsayılan bildirmiyor ve `/api/plan` profil parametresi almıyor.

**Senaryo katalogu:** `/api/scenarios` var (`main.py:1697-1700`) ama içeriği denetimde sondalanmadı — **BİLİNMİYOR**.

Tam alan tabloları §6'da. **Kategori: A.**

### T-6 — Koordinat girdisi

**İkisi de — ama endpoint'e göre değişiyor.**

| Endpoint | Piksel | Coğrafi | Alan adları |
|---|---|---|---|
| `/api/plan`, `/api/replan`, `/api/plan-4d` | evet | evet | `{"row":int,"col":int}` veya `{"lon":float,"lat":float}` (`main.py:320-327,345-346`) |
| `/api/plan-multi`, `/api/compare` | evet | **hayır** | `[row, col]` — `conlist(int, 2, 2)` (`main.py:420,424-425`) |
| `/api/cell-telemetry` | evet | hayır | query `row`, `col` (`main.py:500-501`) |

**Dönüşüm fonksiyonları:** `lonlat_to_pixel(lon, lat, metadata)` ve `pixel_to_lonlat(row, col, metadata)` (`serializer.py`), `_to_pixel()` normalizasyonu (`main.py:306-317`).

**Sınır dışında:**
- Coğrafi → piksel dönüşümü grid dışına düşerse `ValueError` (`serializer.py:189-190`) → `_to_pixel` yakalar → **HTTP 422**, `"{label}: {mesaj}"` (`main.py:315-317`).
- Piksel doğrudan sınır dışıysa → **HTTP 422**, `"goal (900, 10) is outside the 500x500 grid."` `[canlı sonda]`.
- Piksel → coğrafi dönüşümü `-80°` kuzeyinde bir enlem üretirse `ValueError` (`serializer.py:106-107,160`) → `/api/plan`'da **HTTP 422** (`main.py:702-709`).

**Kategori: A.**

### T-7 — Veri kökeni (provenance) meta verisi

**Evet, dört basamaklı bir merdiven var:** `SYNTHETIC < DERIVED < MODEL < MEASURED`, `_VALIDITY_RANK` (`traversability.py:98-103`). `weakest_validity()` türetilmiş katmanın etiketini **en zayıf girdisine** çeker (`traversability.py:105-121`).

Dışa açılan noktalar:

| Yer | Alan | Kanıt |
|---|---|---|
| `/api/cell-telemetry` | `layer_validity` — katman → validity sözlüğü | `main.py:572`; `[canlı sonda]` `{"elevation":"MEASURED","slope":"DERIVED",…}` |
| `/api/layers/*` f32 yanıtı | `X-Layer-Validity` başlığı | `terrain.py:228-229`; `[canlı sonda]` `x-layer-validity: DERIVED` |
| `/api/terrain` | her katman için `validity` alanı | `terrain.py:257,268` |
| `/api/plan-4d`, `/api/illumination-series` | `shadow_model` bloğu: `model`, `time_varying`, `reason` | `main.py:1162-1166` |
| `/api/illumination-series` | `thermal_model` bloğu: `recipe`, `tau_s`, `validity` | BİLİNMİYOR — alan adları canlı sondadan, kod satırı doğrulanmadı |
| grid `metadata` | `cost_model` string'i | `rover_grids.py:74`, `COST_MODEL_ID` karşılaştırması `:80` |

**Katman meta verisi de dışa açık:** `resolution_m`, `shape`, `origin`, `crs` (WKT), `window_offset`, `row_axis`, `col_axis` — `/api/terrain` `georeference` bloğu ve `/api/layers` f32 başlıkları (`X-Layer-Rows/Cols/Resolution-M/Min/Max/Nodata/Dtype/Endian/Order`).

**Kaynak DEM dosya adı dışa açılmıyor** — `metadata.json`'da `window_offset` var ama kaynak dosya adı yok. **BİLİNMİYOR / muhtemelen C.**

**Kategori: A.**

### T-8 — Kısıt marj/slack değerleri

Bu maddede iki farklı "marj" kavramı var ve cevapları **zıt**.

#### (a) Profil kısıtı marjları — **A, dışa açık**

`check_profile_constraints(profile, summary)` her kısıt için bir sözlük üretir (`scenarios.py:99-161`):

```
{"limit": <sayı>, "enforced_in_search": <bool>, "checked": <bool>,
 "actual": <sayı|null>, "satisfied": <bool|null>}
```

`main.py:1210` bunu `result["constraint_check"]` altına yazar; `_attach_constraint_check` hem `/api/plan-multi` (`main.py:1264`) hem `/api/compare` (`main.py:1288`) tarafından çağrılır. Marj = `limit − actual` istemcide hesaplanabilir.

`[canlı sonda]` `/api/compare`, `balanced`:

| Kısıt | `limit` | `actual` | `satisfied` | marj |
|---|---|---|---|---|
| `max_slope_deg` | 25.0 | `null` | `true` | hesaplanamaz (yapısal) |
| `max_shadow_h` | 40.0 | 3.3154 | `true` | 36.68 saat |
| `max_energy_wh` | 4000.0 | 1457.53 | `true` | 2542.47 Wh |
| `min_soc` | 0.2 | 0.7311 | `true` | 0.5311 |

**`/api/plan` bu bloğu üretmez** — tek rota planlayan uç profil kısıtı kavramını hiç görmez.

#### (b) Log-bariyer içi slack'ler — **B, hesaplanıyor ama saklanmıyor**

Dört fonksiyonda slack hesaplanıyor ve **hepsinde aynı desen**: hesapla → anında `math.log()` → listeye ekle → topla → skaler döndür. Ara değer hiçbir yere yazılmıyor.

| Fonksiyon | Slack değişkeni | Hesaplandığı satır | Tüketildiği satır | Akıbet |
|---|---|---|---|---|
| `edge_barrier_penalty` (planlayıcının kullandığı) | `slack_slope` | `cost_engine.py:628` | `:631` `terms.append(math.log(min(1.0, slack_slope)))` | atılır |
| aynı | `slack_lat` | `:633` | `:636` | atılır |
| `geometric_barrier_terms` | `slack_slope` | `:673` | `:677` `return [math.log(...), math.log(...)]` | atılır |
| aynı | `slack_lat` | `:674` | `:677` | atılır |
| `log_barrier_penalty` (tam spec formu) | `slack_slope` | `:705` | `:708` | atılır |
| aynı | `slack_lat` | `:710` | `:713` | atılır |
| aynı | `slack_soc` | `:717` | `:720` | atılır |
| `thermal_barrier_terms` | `slack_cold` | `:589` | `:589` (aynı satırda log'lanır) | atılır |
| aynı | `slack_hot` | `:600` | `:600` | atılır |

`log_barrier_penalty` gövdesi satır satır: `terms: list[float] = []` (`:704`) → üç slack sırayla hesaplanıp `terms`'e log'lanarak eklenir → `geometric = -mu * sum(terms)` (`:729`) → termal ön-görüntüler üzerinde en kötüsü seçilip tek `float` döndürülür (`:730-737`). Slack'lerin kendisi fonksiyondan **çıkmaz**.

Slack sıfıra düştüğünde erken çıkış `float("inf")` döndürür (`:707,712,719`) — yani "hangi kısıt kilitledi" bilgisi bile kaybolur, yalnızca sonsuzluk kalır.

#### (c) Dışa açılan tek bariyer toplulaştırması

`barrier_share` (`pathfinder.py:768-773`): `(goal_cost − total_weighted_cost_cells_only) / goal_cost`. Yani bariyerin toplam maliyetteki payı — bileşen ayrımı yok, hangi kısıtın katkı yaptığı bilinmiyor. `[canlı sonda]` `barrier_share: 0.132624`.

**Kategori: karma — A (profil kısıtları, yalnızca plan-multi/compare), B (bariyer slack'leri), A (yalnız toplulaştırılmış `barrier_share`).**

### T-9 — Sonuç metrikleri

`POST /api/plan` yanıtının tam alan listesi. Birimler yalnızca alan adından veya kod yorumundan çıkarılabildiğinde yazılmıştır.

#### `astar_metrics` — `pathfinder.py:726-783`

| Anahtar | Tip | Birim | Nasıl hesaplanıyor |
|---|---|---|---|
| `constraints_applied` | dict \| null | — | `max_slope_deg`, `slope_lateral_max_deg`, `source` (`pathfinder.py:173-181`) |
| `edges_rejected` | dict[str,int] | kenar sayısı | beş sayaç (`pathfinder.py:524-530,172`) |
| `total_distance_m` | float | metre | yol boyunca öklid adım toplamı |
| `total_energy_wh` | **null** | Wh | hesaplanmıyor — `_compute_path_metrics` bunu doldurmuyor `[canlı sonda: null]` |
| `total_shadow_hours` | **null** | saat | aynı `[canlı sonda: null]` |
| `max_slope_deg` | float | derece | — |
| `max_segment_slope_deg` | float | derece | `"elevation difference across each driven step"` (yanıt içi `slope_definitions`) |
| `max_cell_slope_deg` | float | derece | `"np.gradient slope grid, the traversability gate"` |
| `slope_definitions` | dict[str,str] | — | iki eğim tanımının açıklaması |
| `max_thermal_risk` | float | boyutsuz (0–1) | BİLİNMİYOR — hesaplama satırı okunmadı |
| `min_surface_temp_c` | float | °C | yol boyunca minimum |
| `max_surface_temp_c` | float | °C | yol boyunca maksimum |
| `total_weighted_cost` | float | ağırlıklı metre | `goal_cost` (bariyer dahil) (`pathfinder.py:766-767`) |
| `total_weighted_cost_cells_only` | float | ağırlıklı metre | bariyersiz hücre toplamı (`:769`) |
| `barrier_share` | float \| null | kesir | `(goal_cost − cells_only) / goal_cost` (`:770-773`) |
| `cost_units` | str | — | sabit `"weighted_metres"` (`:779`) |
| `path_length_nodes` | int | düğüm | `len(path_pixels)` |
| `computation_time_ms` | float | milisaniye | `perf_counter` farkı, yalnız `astar()` (`pathfinder.py:149,780`) |
| `nodes_expanded` | int | düğüm | A* genişletme sayacı (`:781`) |

#### `summary` — `simulation.summarize_simulation`

| Anahtar | Birim |
|---|---|
| `total_distance_km` | km |
| `total_elapsed_hours` | saat |
| `final_battery_pct` | yüzde (0–100) |
| `min_battery_pct` | yüzde |
| `max_slope_deg` | derece |
| `max_segment_slope_deg` | derece |
| `total_energy_consumed_wh` | Wh |
| `total_shadow_exposure` | BİLİNMİYOR — birim kodda belirtilmemiş; `max_continuous_shadow_h` saat cinsinden ayrı bir alan olduğu için bu **muhtemelen farklı bir büyüklük**, tahmin edilmedi |
| `critical_steps_count` | adım sayısı |
| `high_or_above_steps_count` | adım sayısı |
| `waypoint_count` | adım sayısı |
| `total_recharges` | sayı |
| `stranded` | bool |
| `stranded_at_step` | adım indeksi \| null |
| `max_continuous_shadow_h` | saat |
| `shadow_limit_h` | saat |
| `shadow_limit_exceeded` | bool |
| `peak_power_exceeded_steps` | adım sayısı |

#### `route_statistics` — `route_analysis.py:22-34`

`waypoint_count` (int), `slope_histogram` (liste; her eleman `bin_low_deg`, `bin_high_deg`, `count`, `pct`), `risk_breakdown_pct` (dict, risk seviyesi → yüzde), `min_surface_temp_c`, `max_surface_temp_c` (°C).

#### `execution` — `main.py:658-669`

`stranded` (bool), `planned_nodes` (int), `executable_nodes` (int), `truncated` (bool), `reason` (str \| null).

#### `waypoints[]` — `serializer.states_to_waypoints`

Adım başına: `step`, `row`, `col`, `lon`, `lat`, `altitude_m`, `battery_pct`, `recharge_count`, `recharged_this_step`, `risk_level` (`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`), `slope_deg`, `surface_temp_c`, `shadow_ratio`, `node_cost`, `elapsed_hours`, `distance_m`, `step_energy_wh`. (Alan adları `frontend/src/api.ts:5-22` arayüzünden ve canlı yanıttan; birimler alan adlarından.)

Diğer üst düzey alanlar: `status` (`"success"`), `geojson`, `corridor` (\| null), `rover` (`{id, name}`).

**Kategori: A.** İki alan **C**: `total_energy_wh` ve `total_shadow_hours` `astar_metrics` içinde daima `null` — gerçek enerji yalnızca `summary` üzerinden gelir.

### T-10 — Yeniden hesaplama maliyeti

**Süre ölçen alan var:** `astar_metrics.computation_time_ms` (`pathfinder.py:149,780`) ve `nodes_expanded` (`:781`).

**Önbellek plan yolunda yok.** `[canlı sonda]` §8'deki tablo: aynı girdinin tekrarı (koşum 1 → koşum 4) 2840.2 ms'den 4848.0 ms'ye çıktı — ikinci koşum ucuz değil, hatta bu ölçümde daha yavaş. `nodes_expanded` ve `total_distance_m` birebir aynı (111770 / 3028.34), yani sonuç yeniden üretiliyor, hatırlanmıyor.

**Ölçülen aralık:** duvar süresi 2840–4848 ms, `computation_time_ms` 747–2649 ms, 4 koşum, 500×500 grid, (60,60)→(440,440). Değişkenlik yüksek; sunucu `--reload` altında ve makine başka iş yapıyordu, bu yüzden bu sayılar **bir üst sınır göstergesi, kalibre edilmiş bir benchmark değil**.

Disk önbelleği yalnızca `load_and_preprocess_dem` yolunda (`data_loader.py:258-262,378-379`), `/api/plan` bunu kullanmıyor.

**Kategori: A** (ölçüm alanı dışa açık), **C** (plan önbelleği yok).

### T-11 — Başarısızlık davranışı

| Soru | Cevap |
|---|---|
| HTTP kodu | **404** (`main.py:628`) |
| Gövde | Yalnızca `{"detail": "<düzyazı cümle>"}` — yapılandırılmış alan yok |
| Tanı üretiliyor mu? | **Evet ama yapılandırılmamış.** `_no_path_reason()` hangi kısıtın kaç kenarı reddettiğini cümle içine gömüyor: `"No path found for NASA VIPER: 412 edges exceeded the 15 deg roll-over (cross-slope) limit; 88 edges exceeded the 20 deg step-slope limit. The terrain between these points is steeper than…"` (`pathfinder.py:846-865`) |
| Yapılandırılmış tanı nerede? | `_empty_result` `metrics` içinde `edges_rejected` (beş sayaç) ve `nodes_expanded` taşıyor (`pathfinder.py:812-825`), ama `main.py:627-628` yalnızca `error` alanını okuyup `metrics`'i atıyor |
| Kısmi sonuç? | **Hayır.** `path_pixels: []` (`pathfinder.py:822`) |

**Önemli asimetri:** `edges_rejected` **başarılı** planlarda da dolu ve dışa açık (`pathfinder.py:172`). `[canlı sonda]` başarılı bir `/api/compare` koşumu: `{"step_slope":25,"lateral_slope":4928,"thermal_barrier":0,"slope_barrier":0,"lateral_barrier":0}`. Yani sayaçlar "rota neden dolambaçlı" sorusunu da cevaplayabilir. Kaybolan **yalnızca başarısızlık dalı** — orada `_empty_result` sayaçları üretir ama `main.py:627-628` `metrics`'i hiç okumaz.

**İstisna:** `/api/plan-multi` ve `/api/compare` başarısızlığı 404 yapmaz — HTTP 200 döner ve `results[]` içinde `error` + **dolu `metrics`** taşır (`main.py:1240-1265`). Yani `edges_rejected` bu iki uçta erişilebilir, `/api/plan`'da değil.

Test kanıtı: `test_pathfinder.py:92`, `test_review3_fixes.py:102`, `test_review4_fixes.py:152,188`.

Denetimde canlı 404 tetiklenemedi (grid %84.0 geçilebilir; `nasa_viper` ve `cnsa_yutu_2` ile köşeden köşeye denemeler yol buldu).

**Kategori: B.**

### T-12 — Sürüm ve kimlik

**Sürüm alanı var, commit yok.** `/api/health` `{"version": "0.3.0"}` döndürüyor (`main.py:453`) `[canlı sonda: {"status":"ok","version":"0.3.0","dem_loaded":true,"grid_shape":[500,500]}]`. Bu değer `main.py:453`'te **elle yazılmış bir string literal**; `main.py:91`'deki `FastAPI(version="0.3.0")` ile ayrı bir kopya, yani ikisi bağımsız olarak eskiyebilir.

Commit/build kimliği **hiçbir yanıtta yok**.

Öneri (uygulama değil): `/api/health` yanıtı zaten sürüm taşıyan tek uç ve tüm istemciler onu çağırıyor — commit kimliği için en doğal yer orası. İkinci aday `/api/terrain` manifestosu, çünkü grid içeriğinin hangi kodla üretildiğini bilmek isteyen 3-B istemcisi zaten onu çekiyor.

**Kategori: A** (sürüm), **C** (commit).

---

## 10. Ek sorular E-1…E-5

### E-1 — "Ucuz kazanç" listesi (B kategorisi)

| # | Değer | Nerede hesaplanıyor | Neden dışarıda | İş mertebesi | Ne işe yarar |
|---|---|---|---|---|---|
| 1 | `edges_rejected` + `nodes_expanded`, yol bulunamadığında | `pathfinder.py:812-825` — `_empty_result` bunları `metrics`'e koyar | `main.py:627-628` yalnızca `error` string'ini okur | ~3 satır — `HTTPException(detail=...)` yerine yapılandırılmış gövde | AI katmanı "neden başarısız" sorusuna sayı verebilir, cümle ayrıştırmak zorunda kalmaz |
| 2 | `slack_slope`, `slack_lat`, `slack_soc` | `cost_engine.py:628,633,673,674,705,710,717` | yerel değişken, anında log'lanıp toplanıyor | ~10–15 satır — fonksiyonların bir `dict` de döndürmesi + `_astar_core`'da yol boyunca minimumun izlenmesi | "hangi kısıta ne kadar yaklaşıldı" sorusunun kenar-düzeyi cevabı |
| 3 | `slack_cold`, `slack_hot` | `cost_engine.py:589,600` | aynı | ~5 satır | termal zarfın hangi ucuna yaklaşıldığı |
| 4 | Rota geneli bileşen ayrıştırması | `CostMap.explain()` hücre başına mevcut (`costmap.py:121-159`), rota boyunca çağıran yok | `main.py:552` yalnızca tek hücre için çağırıyor | ~8 satır — waypoint'ler üzerinde döngü + toplam | "toplam maliyetin %X'i eğimden geldi" — T-1'in en çok istenen sorusu |
| 5 | `constraint_check` `/api/plan` üzerinde | `_attach_constraint_check` mevcut (`main.py:1177-1211`) ama yalnız plan-multi/compare çağırıyor | `/api/plan` profil kavramı taşımıyor | ~5 satır — istek gövdesine opsiyonel `profile_id` + mevcut fonksiyonu çağırmak | tek rota için de kısıt marjı |
| 6 | `total_energy_wh`, `total_shadow_hours` (`astar_metrics` içinde daima `null`) | `_compute_path_metrics` doldurmuyor; gerçek değerler `summary`'de var | tasarım gereği "fast mode" | ~0 — zaten `summary`'de mevcut, yalnız isim çakışması kafa karıştırıyor | — (kazanç değil, tuzak: AI katmanı `astar_metrics.total_energy_wh`'ye bağlanmamalı) |

### E-2 — Doküman–kod çelişkileri

`docs/` altındaki dosyalar ve depo kökündeki `CLAUDE.local.md` tarandı.

| # | Doküman iddiası | Kod ne yapıyor |
|---|---|---|
| 1 | `CLAUDE.local.md`: *"`main.py` keeps a module-level `_grids` global **and** `app.state.grids`… Injecting grids into only one of the two makes half the API work."* | Global kaldırılmış. `main.py:210-214` yorumu: *"app.state.grids is the ONE place the loaded grids live. There used to be a module-level `_grids` global alongside it…"* Tek kaynak `_set_grids`/`_current_grids` (`main.py:217-222`). |
| 2 | `CLAUDE.local.md`: *"`/api/plan-multi`, `/api/compare`, `/api/layers/*` read via `_get_grids()` (global only, **400**)"* | `_get_grids()` **503** döndürüyor ve yorumu bunun bilinçli bir birleştirme olduğunu söylüyor (`main.py:244-263`). |
| 3 | `CLAUDE.local.md`: *"`astar(..., constraints=...)` accepts the mission-profile constraints … and **ignores them** — 'kept for API compat'."* | Onurlandırılıyor: `main.py:1258,1282` profil kısıtlarını geçiyor, `pathfinder.py:132-141` `max_slope_deg`'i çıkarıp aramaya sokuyor, yorumu bunu açıkça düzeltme olarak anlatıyor. |
| 4 | `CLAUDE.local.md`: *"`_compute_path_metrics()` reports `total_energy_wh = **0.0**` and `total_shadow_hours = **0.0**`"* | `_zero_metrics` her ikisini de **`None`** yapıyor (`pathfinder.py:790-791`); `[canlı sonda]` yanıtta `null`. |
| 5 | `CLAUDE.local.md`: *"`scenarios.compare_results()` ranks on exactly those fields, so `most_efficient_profile` is always whichever profile happens to be first"* | `[canlı sonda]` `comparison.recommendation` bu sınırlamayı **kendisi bildiriyor**: *"Energy and shadow totals are not tracked in fast mode, so neither ranking is an energy claim."* Sıralamanın hâlâ dejenere olup olmadığı denetimde doğrulanmadı — **BİLİNMİYOR**. |
| 6 | `CLAUDE.local.md`: *"query params on `/api/layers/*`, each **clamped to [0.0, 2.0]**"* | Kırpma **yok**. `main.py:1319-1322` düz `float \| None`. `[canlı sonda]` `w_slope=999` → HTTP 200, `X-Layer-Max: 981.55`. |
| 7 | `CLAUDE.local.md`: *"`thermal` and `shadow_ratio` are **proxies, not physics** — synthetic temperature… no ephemeris, no ray-traced horizon, no time axis."* | Gerçek yol mevcut: `app.ephemeris` SPICE ile güneş izi, `app.horizon` ufuk haritası, `app.illumination_series` zaman ekseni; `/api/illumination-series` `shadow_model.model` `"spice_horizon"` \| `"static"` bildiriyor. Sentetik yol yalnızca **geri düşüş**. |
| 8 | `CLAUDE.local.md`: *"Backend tests are standalone scripts, not a pytest suite"* | `backend/requirements.txt` `pytest==8.3.4` içeriyor. Test dosyalarının pytest ile toplanıp toplanmadığı denetimde **çalıştırılmadı** (Kural 7) — **BİLİNMİYOR**. |
| 9 | `docs/frontend/3b-veri-sozlesmesi.md`: three.js bağlaması `PlaneGeometry(cols * resolution_m, rows * resolution_m, cols - 1, rows - 1)` öneriyor | Bu bir **frontend** snippet'i, backend kodu değil. `cols-1` segment `cols` vertex taşır, yani vertex aralığı `cols*res/(cols-1)` olur — 500×500 @ 5 m'de 5.01 m, %0.2 gerilme. Backend sözleşmesini etkilemiyor; kapsam dışı ama kaydedildi. |

Not: `docs/` altında `README.md` ve `docs/README.md` indeksi denetimde ayrıntılı taranmadı; yukarıdaki liste **eksiksiz değildir**.

### E-3 — Determinizm

**Aynı girdi aynı sonucu veriyor.** `[canlı sonda]` koşum 1 ve koşum 4 birebir aynı gövdeyle: `total_distance_m` 3028.34 (ikisinde de), `nodes_expanded` 111770 (ikisinde de). Yalnızca `computation_time_ms` değişiyor (753.1 → 2649.4) — bu bir duvar-saati ölçümü, sonucun parçası değil.

Determinizmi bozabilecek noktalar:

| Kaynak | Durum | Kanıt |
|---|---|---|
| Rastgelelik | Görülmedi — `random`/`np.random` planlama yolunda taranmadı ama sonuç tekrarlanabilir çıktı | canlı gözlem |
| Zaman bağımlılığı | **`computation_time_ms` her yanıtta farklı.** Ayrıca `/api/plan-4d` ve `/api/illumination-series` `start_utc` alıyor — verilmezse `shadow_model: "static"` (`main.py:407-415`) | `pathfinder.py:149` |
| `uuid4` | **Her başarılı planda yeni `corridor_id`** (`main.py:684`). Yanıt gövdesi bu alan yüzünden asla iki kez aynı olmaz. | `main.py:684-686` |
| Sözlük sıralaması | `MISSION_PROFILES.items()` üzerinde iterasyon (`main.py:1275`) — Python 3.7+ ekleme sırasını korur, yani `/api/compare` sonuç sırası deterministik ama **kaynak dosyadaki tanım sırasına bağlı** | `scenarios.py:15,32,49,66` |
| Kayan nokta birikimi | A* `g_score` düz NumPy dizilerinde birikiyor; ağırlık değişimi 0.409→0.459 mesafeyi 3028.34→3028.32 yaptı — eşit maliyetli yollar arasında seçim ağırlığa duyarlı | canlı gözlem, koşum 1 vs 2 |
| Süreç durumu | `app.state.grids` ve `app.state.corridors` süreç ömrü boyunca birikiyor; `/api/pose` sonucu hangi korridorların hâlâ kayıtlı olduğuna bağlı (32'lik FIFO) | `main.py:726-735` |

**Sonuç: planlama çekirdeği deterministik; yanıt gövdesi `corridor_id` ve `computation_time_ms` yüzünden değil.** AI katmanı iki yanıtı karşılaştırırken bu iki alanı hariç tutmalı.

### E-4 — Girdi doğrulama yüzeyi

**Doğrulananlar:**

| Girdi | Kural | Yer |
|---|---|---|
| `PlanWeights.w_*` | `[0.0, 2.0]` | `main.py:336-341` |
| `start`/`goal` (plan) | grid sınırı | `main.py:591-600` |
| `start`/`goal` (plan-multi, compare) | uzunluk 2 + grid sınırı | `main.py:420`, `:1214-1229` |
| `start`/`goal` geçilebilirlik | traversable maskesi | `main.py:602-618` |
| `rover_id` | katalog üyeliği | `constants.get_rover` → 422 |
| `layer_name` | 8 elemanlı beyaz liste | `main.py:1335-1336` |
| `downsample` | `ge=1, le=50` | `main.py:1304` |
| `format` | `^(json\|f32)$` | `main.py:1310` |
| `n_slices` | `ge=2, le=1000` | `main.py:395` |
| `horizon_hours` | `gt=0.0, le=168.0` | `main.py:396` |
| `slice_hours` | `gt=0.0, le=24.0` | `main.py:401` |
| `coarsen` | `ge=1, le=16` | `main.py:402` |
| `state` telemetrisi | NaN/inf reddi | `main.py:352-371` |
| `dem_file` | dizin kaçışı reddi | `main.py:287-303` |
| Bellek bütçeleri | küp/seri/hücre tavanları | `main.py:186-203`, `:1391-1403` |

**Doğrulanmayanlar — AI katmanının kendi kontrolünü koyması gereken yerler:**

| # | Girdi | Risk |
|---|---|---|
| 1 | `/api/layers/*` `w_slope`/`w_energy`/`w_shadow`/`w_thermal` (`main.py:1319-1322`) | Sınırsız. `[canlı sonda]` `w_slope=999` → 200, cost max 981.55; `w_slope=-5` → 200. Negatif ağırlık maliyet manzarasını tersine çevirir. |
| 1b | `/api/terrain` aynı dört parametre (`main.py:1421-1424`) | Aynı boşluk, aynı imza. Manifest `weights` bloğunu ve her katmanın `min`/`max` değerini bu doğrulanmamış ağırlıklardan üretir, yani 3-B istemcisi renk rampasını çarpık bir aralığa göre ölçekler. |
| 2 | `LoadDEMRequest.weights`, `LoadPreprocessedRequest.weights` — `dict[str,float]`, `PlanWeights` değil (`main.py:440,445`) | Aynı sınırsızlık, üstelik **kalıcı grid durumuna** yazılıyor |
| 3 | `LoadPreprocessedRequest.processed_dir` (`main.py:444`) | `_resolve_dem_path` benzeri yol koruması **yok** — `dem_file` için kapatılan kaçış bu alanda açık görünüyor |
| 4 | `LoadDEMRequest.target_resolution_m` (`main.py:438`) | Aralık yok; 0 veya negatif değerin davranışı BİLİNMİYOR |
| 5 | `PlanMultiRequest.profiles` (`main.py:426`) | Doğrulanmıyor; bilinmeyen id sessizce sonuç dizisinde `error` olur, HTTP 200 |
| 6 | `Plan4DRequest.start_utc` (`main.py:407`) | Düz `str`, biçim doğrulaması yok |
| 7 | `PoseRequest` alanları | Denetimde okunmadı — BİLİNMİYOR |

### E-5 — Yan etkiler

**Durum değiştiren endpoint'ler:**

| Endpoint | Yan etki |
|---|---|
| `POST /api/load-preprocessed` | `app.state.grids` yazar (`main.py:476`) |
| `POST /api/load-dem` | `app.state.grids` yazar (`main.py:494`) **+ diske `.npy` önbelleği yazar** (`data_loader.py:378-379,449-454`) |
| `POST /api/scenarios/{id}/load` | `app.state.grids` yazar (`main.py:1721`), DEM yolundan geçerse disk önbelleği de |
| `POST /api/plan` | `app.state.active_corridor`, `active_corridor_id`, `active_corridor_rover_id` ve `app.state.corridors` kayıt defterini yazar; 32'yi aşınca en eskiyi siler (`main.py:722-735`) |
| `POST /api/replan` | `force` veya tetikleyici ateşlerse `plan()` çağırır → yukarıdaki tüm yan etkiler (`main.py:772`) |

**Saf okuma:**

`GET /api/health`, `/api/rovers`, `/api/cell-telemetry`, `/api/layers/{layer_name}`, `/api/terrain`, `/api/illumination-series`, `/api/reference-missions`, `/api/profiles`, `/api/scenarios`.

**Sınırda:** `POST /api/plan-multi` ve `POST /api/compare` — durum yazmıyorlar (korridor üretmiyorlar, `_set_grids` çağırmıyorlar) ama POST'lar ve ağır hesaplama tetikliyorlar. `grids_for_rover` her profil için yeni grid **türetiyor** ama sonucu `app.state`'e yazmıyor (`main.py:1252,1276`). AI katmanı için **güvenli okuma** sayılabilirler.

`POST /api/pose` — `app.state.corridors` okuyor (`main.py:833,848`); yazıp yazmadığı denetimde doğrulanmadı, **BİLİNMİYOR**.

---

## 11. BİLİNMİYOR listesi

| # | Konu | Neden cevaplanamadı |
|---|---|---|
| 1 | `POST /api/pose` istek/yanıt şeması | `main.py:820-883` denetimde okunmadı; kapsam önceliği plan/analiz yoluna verildi |
| 2 | `/api/pose` yan etkisi var mı | aynı |
| 3 | `summary.total_shadow_exposure` birimi | Kodda birim belirtilmemiş; `max_continuous_shadow_h` ayrı bir saat alanı olduğu için bunun saat olduğu **varsayılamaz** |
| 4 | `astar_metrics.max_thermal_risk` nasıl hesaplanıyor | `_compute_path_metrics` gövdesinin ilgili satırı okunmadı; birim 0–1 boyutsuz görünüyor ama doğrulanmadı |
| 5 | `rover.declared_only` alanlarının hesaplamada kullanılıp kullanılmadığı | Alan adı kullanılmadığını ima ediyor; `f_net_n`, `regen_efficiency`, `thermal_tau_s`, `h_design_shadow_h` için kod içi tüketim aranmadı |
| 6 | `/api/scenarios` katalog içeriği ve senaryo `id` string'leri | Sondalanmadı; `load_scenario` durum değiştirdiği için ilgili uç kapsam dışı bırakıldı |
| 7 | `/api/illumination-series` `thermal_model` bloğunun kod içi kaynağı | Alan adları canlı sondadan görüldü, üretildiği satır doğrulanmadı |
| 8 | Yol bulunamadığında gerçek 404 gövdesi | Canlı tetiklenemedi (grid %84.0 geçilebilir). Kod ve testlerden çıkarıldı, gözlemlenmedi |
| 9 | `compare_results()` sıralamasının dejenere olup olmadığı | `scenarios.compare_results` gövdesi okunmadı; yanıt kendi sınırlamasını bildiriyor ama sıralama mantığı doğrulanmadı |
| 10 | `pytest` ile test toplama çalışıyor mu | Kural 7 — test koşturulmadı |
| 11 | Kaynak DEM dosya adının bir yanıtta dışa açılıp açılmadığı | `metadata` içinde görülmedi, ama tüm yanıt gövdeleri taranmadı |
| 12 | `LoadPreprocessedRequest.processed_dir` için yol koruması gerçekten yok mu | `_resolve_dem_path` benzeri bir çağrı `main.py:464-477`'de görülmedi; `load_preprocessed_grids` içinde bir koruma olup olmadığı `data_loader.py` tarafında doğrulanmadı |
| 13 | `target_resolution_m ≤ 0` davranışı | Doğrulama yok; sonuç denenmedi (durum değiştiren uç) |
| 14 | `docs/` altındaki tüm iddiaların taranması | Yalnızca `CLAUDE.local.md` ve `docs/frontend/3b-veri-sozlesmesi.md` ayrıntılı okundu; §12 listesi eksiksiz değil |

---

## 12. Doküman–kod çelişkileri

Tam liste **E-2**'de, dokuz madde hâlinde. Özet: `CLAUDE.local.md` altı noktada koddan geride — kaldırılmış bir global, değişmiş bir HTTP kodu, artık onurlandırılan bir parametre, `0.0` yerine `None` olan iki alan, var olmayan bir ağırlık kırpması, ve "fizik yok" iddiasının aksine mevcut olan SPICE/ufuk yolu.

**Bu envanterin kendisi için sonuç:** `CLAUDE.local.md` bu backend için güvenilir bir kaynak değil. AI katmanı alan adlarını ondan değil, bu rapordan ve canlı `/api/health` + `/api/terrain` yanıtlarından almalı.
