# A2 — Sürekli-aydınlık koridoru: 3-B (x, y, t) bağlı-bileşen budaması (CMU / Otten–Whittaker) — Tasarım Belgesi

**Tarih:** 4 Eylül 2026
**Branch:** `berke-3d-backendEnhance`
**Kaynak:** [12_faktor_backend_ozellik_arastirmasi_2026-09-03.md → A2](../../research/12_faktor_backend_ozellik_arastirmasi_2026-09-03.md)
**Bağımlılık:** Aydınlanma serisi (`illumination_series.build_shadow_series`, ufuk küpü + NAIF çekirdekleri), 4-B planlayıcı (`pathfinder_4d.astar_4d`), A1'in kapılı kenar grafı (`safe_haven._gated_edges`), D3'ün `safety_margins` bloğu (yalnızca tutarlılık testi ve raporda). A3 (hedef alt-hacmi, zaman sıkıştırma) bu özelliğe bağımlıdır; burada yalnızca çıkarılabilir bırakılır.
**Kapsam:** `backend/app/`, `backend/test_*.py`, `scripts/`, `docs/`. Frontend koduna dokunulmuyor; `docs/frontend/3b-veri-sozlesmesi.md`'ye ek bölüm yazılıyor. 3-B koridor görselleştirmesi frontend ekibinin.

---

## Amaç

CMU'nun (Otten, Jones, Wettergreen, Whittaker; ICRA 2015, FSR 2017, Otten'in
tezi) Güneş-eşzamanlı (sun-synchronous) rota planlama yaklaşımı: aydınlanma
zaman serisi ile eğim maskesi **x-y-t hacminde** birleştirilir, "sürekli
aydınlık ve güvenli eğimli" bağlı bileşenler bulunur, başlangıç zamanına
ulaşmayan kökler ile bitiş zamanına ulaşmayan çıkmaz dallar iki geçişle
budanır ve rota bu hacim içinde ileri-zamanlı A* ile aranır. LunaPath'te
bugün `pathfinder_4d` yalnızca **uzamsal** bileşeni kontrol ediyor
(`gated_move_count`: kapılı grafta en büyük bileşen %76,4); zamansal bileşen
yok, A* tüm küpte arıyor.

Bu özellik o hacmi üretir (`illumination_corridor.py`), planlayıcıya
`require_continuous_illumination` seçeneğiyle ön-filtre olarak verir,
her `/api/plan-4d` yanıtına `illumination_corridor` bloğu ekler ve CMU'nun
"dwell" metriğini (`max_dwell_hours`) getirir.

Tek cümlelik iddia: **"Sun-synchronous yaklaşımını (CMU, NIAC) 4-B
planlayıcımızın ön-filtresi olarak uyguladık: `require_continuous_illumination`
ile bulunan rota, modelin gölge serisinde tanım gereği hiç karanlık
göstermez (`path_dark_hours` her durumda 0, D3 LP-R01 ρ = `h_max_shadow_h`)."**

**İddia sınırı (her yanıtta ve belgede):** "Koridor içinde kaldığı sürece
rover asla gölgeye girmez" garantisi **modelin aydınlanma serisi** içindir:
SPICE Güneş konumu + ufuk küpü (72 azimut kutusu, iki ölçekli, 150 km'ye
kadar), 320 m kaba bloklar, örneklenmiş dilim anları. B3'ün bulgusu uyarı
olarak taşınır: 30 Mayıs 2027'de hücrelerin **%10,8'i** NASA'nın 100 DEM
klonu arasında aydınlık/karanlık olarak kararsız. "Gerçekte asla gölgeye
girmez" **denmez**.

## Yöntem notu — CMU'nun tanımı ve uyarlamamız

### CMU (ICRA 2015)

- Girdi: 5 m DEM + ray-tracing aydınlanma görüntüsü → eşikle ikili
  aydınlık/gölge haritası; eğim maskesi. Hacim `lit_and_safe[t, y, x]`.
- **3×3×3 çekirdekle (26-komşuluk) flood-fill** (`scipy.ndimage.label`
  eşdeğeri); en büyük bileşen seçilir.
- **İki geçişli budama:** zamanda ileri geçişle "başlangıç zamanına
  ulaşmayan" kökler, zamanı ters çevirip tekrarlayarak "bitiş zamanına
  ulaşmayan" çıkmaz dallar atılır.
- Graf: her voksel düğüm, kenarlar yalnızca **bir sonraki dilimdeki 9
  komşuya** (ileri zaman: 8 komşu + yerinde kalma). A* Öklid mesafeyle.
- Sonuç: rota bileşen içinde kaldıkça asla gölgeye girmez; dwell fırsatı
  (Malapert 45 h, Shackleton 226 h).

### Ölçek uyuşmazlığı ve uyarlama

CMU'da bir hamle tam bir dilim sürer (5 m hücre, uzun dilim). Bizde kaba
hücre 320 m (coarsen 4), dilim otomatik (`auto_slice_hours`: VIPER 0,0956 h,
LPR-1 0,0287 h) ve bir hamle **birden çok dilim** sürer:
`d = max(1, ceil(edge_travel_time_s(ortalama eğim, mesafe) / 3600 / slice_hours))`
(ölçüm: iki standart rotada en kötü kenar 2 dilim; kullanıcı `slice_hours`
sabitlerse onlarca olabilir). Bu yüzden koridor grafı **planlayıcının kendi
hamle süresini** kullanır ve budama genel `ndimage.label` ile değil,
ileri/geri erişilebilirlik olarak yapılır:

**Voksel.** `(t, r, c)`, kaba grid. Aydınlık kuralı (`lit_rule`, istek
alanı):
- `"all"` (varsayılan, muhafazakâr): bloktaki **16 ince hücrenin hepsi**
  aydınlık ⇔ kaba gölge kesri = 0. Dünya küpü ve `coarsen_traversable`'ın
  blok-VE kalıbı. Garanti bu kuralla verilir.
- `"majority"` (gevşek): blok ortalaması `shadow_cube[t] < 0,5` — planlayıcının
  kendi `_DARK_RATIO_THRESHOLD` eşiği; `path_dark_hours = 0` için yeter
  koşul, blok içi kısmi gölgeyi kabul eder.

Güvenli: `lit_safe = lit & coarse_traversable` (blok-VE geçilebilirlik = eğim
sınırı + termal kapı; CMU'nun "traversable slope"u).

**Kenar (hamle-süresi farkında).** Kapılar `astar_4d`'ninkiyle **aynı**
(`safe_haven._gated_edges` yeniden kullanılır: iki hücre geçilebilir, köşe
kesme yok, adım eğimi ≤ `slope_max_deg`, yanal eğim ≤ `slope_lateral_max_deg`,
sonlu seyahat süresi; süre trapez ortalama eğimle `d / (v_max cos²θ)`).
- MOVE `(r,c,t) → (r',c',t+d)` koridor kenarıdır ⇔ **iki blok da `t..t+d`
  dilimlerinin hepsinde `lit_safe`** ("kalkıştan varışa kadar işgal edilen
  her voksel aydınlık ve güvenli"). Rover hamle boyunca iki bloktan birinde
  olduğundan, ara dilimlerde de modelin gölge serisi karanlık göstermez;
  planlayıcının trapez enerji hesabında ortalama gölge maruziyeti 0 olur.
- WAIT `(r,c,t) → (r,c,t+1)` ⇔ iki voksel de `lit_safe`.

Uygulama için `run[t, r, c]` = `t` ile biten kesintisiz `lit_safe` dilim sayısı
(ileri kümülatif, dilim başına vektörize); kenar koşulu
`run[t+d, src] ≥ d+1 ∧ run[t+d, dst] ≥ d+1 ∧ gate[src→dst]`.

**İki geçişli budama (CMU'nun kökler/çıkmazlar tanımı).**
- `forward_reach[t]`: kaynaklardan (varsayılan: dilim 0'daki tüm `lit_safe`
  vokseller) koridor kenarlarıyla ulaşılabilen vokseller; dilim dilim
  `reach[t] = lit_safe[t] ∧ (reach[t−1] ∨ ⋃_k shift_k(reach[t−d_k] ∧ kenar_k))`.
  Her ofset için `d_k` hücreye göre değiştiğinden `reach[t − d_k[src], src]`
  zaman ekseninde fancy-index ile toplanır (8 ofset × T dilim × H·W bool).
- `backward_reach[t]`: hedeflerden (varsayılan: son dilimdeki tüm `lit_safe`
  vokseller) geriye aynı kenarlarla; `coreach[t] = lit_safe[t] ∧ (coreach[t+1] ∨ ⋃_k shift_k⁻¹(coreach[t+d_k] ∧ kenar_k))`.
- `corridor = forward_reach ∧ backward_reach`. Anlamı: koridordaki her
  vokselden pencerenin sonuna kadar aydınlıkta kalınabilecek bir devam var ve
  o voksele pencerenin başından aydınlıkta gelinebilir.

`sources`/`sinks` parametreleri genel tutulur: A3 aynı fonksiyonu
`sources = {başlangıç @ 0}`, `sinks = {hedef @ her t}` ile çağırarak "hedefe
ulaşan alt-hacmi" çıkarır. A2 bunu planlayıcıya vermez; yalnızca
`start`'tan ileri erişilebilirliği hesaplayıp `goal_reachable_in_corridor`
ve 404 gerekçesi için kullanır.

**CMU çapraz kontrolü.** `components(lit_safe)`: `scipy.ndimage.label(...,
structure=ones((3,3,3)))` (26-komşuluk, yönsüz, 1 dilimlik komşuluk, kapısız)
→ bileşen sayısı ve en büyük hacim; yanıtta ve raporda "CMU'nun label'ı"
olarak koridorun yanında verilir. Birim testte: `slice_hours` her kenar
süresinden uzun (d ≡ 1) ve kapılar açıkken ileri/geri geçişimiz CMU'nun
9-komşu grafındaki kesin budamaya indirgenir ve açık voksel grafı üzerinde
kaba kuvvet BFS ile birebir karşılaştırılır; koridor ⊆ (hem ilk hem son
dilime dokunan 26-bileşenlerin birleşimi) kapsaması da sınanır.

**Dwell.** `dwell_slices[t, r, c]` = `t`'den itibaren hücrenin kesintisiz
koridorda kaldığı dilim sayısı (ardışık koridor voksellerinde WAIT kenarı
her zaman geçerlidir). `dwell_hours = dwell_slices × slice_hours`. Rota dwell'i:
her durum `(r,c,t)` için `dwell_hours[t,r,c]`; `max_dwell_hours` en büyüğü,
`dwell_opportunities` en iyi 3 durum; ufka dayananlar `horizon_limited: true`
(varsayılan ufuk kısa — VIPER rotasında 9,6 h — CMU'nun 59 günlük
pencereleriyle kıyaslanamaz, sayı dürüstçe ufka bağlı raporlanır). Dwell
"hücrede o kadar saat aydınlıkta beklenebilir" demektir; "rotanın kalanı o
gecikmeyle hâlâ geçerli" demez (belgede söylenir).

## Mevcut durumdan kullanılanlar

| Bileşen | Kullanım |
|---|---|
| `illumination_series.build_shadow_series` | Dilim başına ikili gölge kesitleri + provenance (`spice_horizon` / `static`) — zaten `plan_4d` üretiyor |
| `cost_cube.coarsen_grid`, `coarsen_traversable` | `"majority"` (blok ortalaması) ve `"all"` (blok-VE) kuralları |
| `main._coarse_geometry`, `_CoarseGeometry` | Kaba geçilebilirlik / eğim (blok-maks) / yükseklik (blok-merkez) |
| `safe_haven._gated_edges` | Planlayıcıyla aynı kapılar ve seyahat saati, vektörize; ofset başına `(ok, d)` tablolarına çevrilir |
| `pathfinder_4d.astar_4d`, `REJECTION_KEYS`, `no_path_reason_4d`, `_empty` | Yeni ret anahtarı `continuous_illumination`, yeni parametreler |
| `main.plan_4d`, `Plan4DRequest` | İstek alanları, yanıt bloğu, 404 gerekçesi (`_no_path_reason` kalıbı) |
| `main.illumination_series` (uç) | `GET /api/illumination-corridor`'ın `X-Series-*` / `binary_format` kalıbı |
| `safety_monitor.trace_from_plan4d` | LP-R01 ρ = `h_max − max(path_dark_hours)` → koridor içinde `= h_max` (gerçek-grid tutarlılık testi) |
| B3 raporu | Uyarı metni: 30 May 2027'de hücrelerin %10,8'i klonlar arasında kararsız |

## Bileşenler

### `backend/app/illumination_corridor.py` (saf, yeni)

```
LIT_RULES = ("all", "majority")

lit_volume(shadow_series, coarsen, lit_rule) -> (T, h, w) bool
    "all": coarsen_traversable(snapshot < 0.5, coarsen) — her ince hücre aydınlık
    "majority": coarsen_grid(snapshot, coarsen) < 0.5
    (ince kesit ikili; statik seride uzun-dönem kesir — provenance söyler)

lit_run(volume) -> (T, h, w) int32      t ile biten ardışık True sayısı
forward_run(volume) -> (T, h, w) int32  t'den başlayan ardışık True sayısı (dwell)

@dataclass EdgeTables: offsets (8), ok[k] (h, w) bool, slices[k] (h, w) int32
edge_tables(traversable, elevation, slope, resolution_m, rover, slice_hours) -> EdgeTables
    safe_haven._gated_edges → iki yöne açılır; d = max(1, ceil(hours / slice_hours))

forward_reach(lit_safe, edges, sources=None) -> (T, h, w) bool
backward_reach(lit_safe, edges, sinks=None) -> (T, h, w) bool
prune_corridor(lit_safe, edges, sources=None, sinks=None) -> (forward, backward, corridor)

@dataclass IlluminationCorridor:
    lit_safe, corridor, run (lit_run(lit_safe)), forward (dilim-0 kaynaklı),
    backward, dwell_slices, lit_rule, slice_hours, n_slices, edges
build_corridor(shadow_series, coarse_traversable, elevation, slope,
               resolution_m, rover, coarsen, slice_hours, lit_rule) -> IlluminationCorridor

components(lit_safe) -> dict   # ndimage.label 26-komşuluk: count, largest_voxels,
                               # largest_fraction, spanning_count (ilk ve son dilime dokunan)
reachable_from(corridor, edges, start) -> (T, h, w) bool  # forward_reach(sources={start@0})
route_dwell(corridor, path_states, slice_hours, top=3) -> dict
    max_dwell_hours, dwell_horizon_limited, dwell_opportunities[{state, row, col, slice, hours, horizon_limited}]
corridor_summary(corridor, start, goal, path_states|None, provenance, timings) -> dict  # yanıt bloğu
```

Bellek: bool küpler `T·h·w` bayt; `run`/`dwell` int32. 1 000 dilim × 125²
= 15,6 M voksel → ~16 MB + 2 × 62 MB; iki maliyet küpü (250 MB) bütçesinin
altında. Kaba kuvvet BFS yalnızca testte.

### `backend/app/pathfinder_4d.py` (ekleme)

- `REJECTION_KEYS += ("continuous_illumination",)`; `no_path_reason_4d`
  cümlesi: "N transitions would have taken the rover out of the
  continuous-illumination corridor (require_continuous_illumination: every
  block the rover occupies must be lit in the shadow series)".
- `astar_4d(..., corridor_cube=None, corridor_lit_run_cube=None,
  require_continuous_illumination=False)`:
  - iki küp birlikte verilir (`(T, H, W)`; biri eksikse `_empty` hatası);
    `require_continuous_illumination=True` küpsüz → `_empty` hatası.
  - Uygulanıyorsa: `corridor[0, start]` değilse `_empty("Start ... is not
    inside the continuous-illumination corridor at the first slice ...")`.
  - WAIT: `corridor[t+1, r, c]` değilse ret `continuous_illumination`.
  - MOVE: `corridor[arrival, nr, nc] ∧ run[arrival, r, c] ≥ d+1 ∧ run[arrival, nr, nc] ≥ d+1`
    değilse ret. Kapı sırası: ufuk → DTE → haven → koridor → maliyet → zarf
    (koridor ucuz bir bool, zarf aritmetiğinden önce).
  - Uygulanmıyorsa küpler yalnızca **raporlanır**: `metrics.states_outside_corridor`
    (rota durumlarından koridor dışında kalan sayı), `metrics.moves_outside_corridor`.
  - `metrics.continuous_illumination_enforced` (bool, `_empty`'de de).
- Sezgisel ve maliyet değişmez: koridor yalnızca kenar siler → optimallik
  koridor-içi rotalar arasında korunur.

### `backend/app/main.py` (ekleme)

- `Plan4DRequest.require_continuous_illumination: bool = False`;
  `Plan4DRequest.lit_rule: Literal["all", "majority"] = "all"`.
- `plan_4d`: `shadow_cube` kurulduktan sonra `build_corridor(...)`
  (`shadow_series`, `geometry`, rover, `slice_hours`, `req.lit_rule`);
  `require_continuous_illumination` ve `shadow_provenance.time_varying`
  değilse **422** ("needs time-varying illumination; the shadow model is
  static: <reason>"). Planlayıcıya küpler + bayrak. 404 gerekçesine koridor
  cümlesi: voksel sayısı ve `lit_safe` oranı, başlangıç bloğunun koridora ilk
  girdiği dilim (ya da hiç), hedef bloğunun koridorda olduğu dilim sayısı,
  hedefin başlangıçtan koridor içinde ulaşılabilir olup olmadığı, ilk aydınlık
  dilim.
- Yanıt: `illumination_corridor` bloğu (her zaman, gölge serisi statik olsa
  bile — provenance söyler), `metrics.max_dwell_hours` (koridor yoksa `null`).
- `GET /api/illumination-corridor` (düşük öncelik, en sonda):
  `start_utc, rover_id, n_slices, slice_hours (verilmezse auto_slice_hours),
  coarsen=4, lit_rule, format=json|f32, field=corridor|lit_safe|dwell_hours`;
  `downsample` yok (kaba grid zaten küçük).
  JSON: özet bloğu + `fields{}.binary_url` + `binary_format {shape [T, h, w]}`;
  f32: `X-Series-*` başlıkları (`X-Series-Resolution-M` = ince × coarsen,
  `X-Series-Field`, `X-Series-Lit-Rule`, `X-Series-Coarsen`). Statik seride
  f32 için 404 değil — küp yine üretilir, JSON'daki provenance `static` der
  (Dünya serisi kalıbı: dürüst etiket, sessiz sıfır değil).

### Yanıt bloğu `illumination_corridor`

```json
{
  "enforced": false,
  "lit_rule": "all",
  "lit_rule_definition": "a coarse block is lit only if every fine cell in it is lit at that slice (block shadow fraction 0)",
  "edge_rule": "MOVE (r,c,t)->(r',c',t+d), d = ceil(edge travel / slice) as the planner; both blocks lit and passable at every slice t..t+d; gates as astar_4d (step slope, cross-slope, corner cut)",
  "pruning": "forward reach from the lit layer at slice 0 AND backward reach from the lit layer at the last slice (CMU's two-pass root / dead-end pruning, move-time aware)",
  "n_slices": 100, "slice_hours": 0.0956, "grid": {"rows": 125, "cols": 125, "resolution_m": 320.0},
  "voxels": {"traversable": 1031400, "lit_safe": 417294, "corridor": 0, "corridor_fraction_of_lit_safe": 0.0, "pruned_fraction": 1.0},
  "slices": {"first_lit": 0, "last_lit": 99, "lit_safe_cells_t0": 4160, "corridor_cells_t0": 0, "corridor_cells_last": 0},
  "components": {"method": "scipy.ndimage.label, 26-neighbourhood (CMU's flood fill)", "count": 12, "largest_voxels": 400000, "largest_fraction_of_lit_safe": 0.96, "spanning_count": 3},
  "start": {"cell": [89, 123], "in_corridor_t0": false, "first_corridor_slice": null},
  "goal": {"cell": [51, 106], "corridor_slices": 0, "reachable_in_corridor": false, "first_reachable_slice": null},
  "route": {"inside": null, "states_inside": null, "states_total": null, "moves_outside": null, "waits_outside": null,
            "path_dark_hours_max": null, "max_dwell_hours": null, "dwell_horizon_limited": null, "dwell_opportunities": []},
  "provenance": {"shadow_model": "spice_horizon", "time_varying": true,
                 "claim": "inside the corridor the model's shadow series never shows a dark block: SPICE Sun + horizon cube (72 azimuth bins, two-scale), 320 m blocks, sampled slices. Not a claim about the real surface.",
                 "uncertainty_note": "B3: on 2027-05-30 10.8 percent of cells are undecided lit/dark across NASA's 100 DEM clones (dem_uncertainty_report.md)",
                 "reference": "Otten, Jones, Wettergreen, Whittaker, ICRA 2015; FSR 2017"},
  "timings_ms": {"lit_volume": 250.0, "edges": 20.0, "prune": 300.0, "components": 60.0, "total": 640.0}
}
```

Sayılar örnektir; gerçek değerler uygulama sonunda ölçülür (aşağıda).

## Veri akışı

```
plan_4d
  ├─ geometry = _coarse_geometry(...)                       (mevcut)
  ├─ shadow_series, prov = build_shadow_series(...)         (mevcut)
  ├─ shadow_cube = stack(coarsen_grid(...))                 (mevcut)
  ├─ corridor = build_corridor(shadow_series, geometry.traversable, geometry.elevation,
  │             geometry.slope, geometry.resolution_m, rover, coarsen, slice_hours, lit_rule)
  │     lit_safe = lit_volume(...) & traversable
  │     edges = edge_tables(...)           ← safe_haven._gated_edges
  │     run = lit_run(lit_safe)
  │     forward, backward, corridor = prune_corridor(lit_safe, edges)
  │     dwell = forward_run(corridor)
  ├─ (require_continuous_illumination ∧ ¬time_varying) → 422
  ├─ result = astar_4d(..., corridor_cube=corridor.corridor, corridor_lit_run_cube=corridor.run,
  │                    require_continuous_illumination=req.require_continuous_illumination)
  ├─ hata → 404 detail += corridor cümlesi (reachable_from(start) dahil)
  └─ yanıt: illumination_corridor = corridor_summary(...) + route_dwell(...); metrics.max_dwell_hours
```

## Test stratejisi

- `test_illumination_corridor.py` (sentetik, çekirdeksiz):
  - `lit_volume`: 8×8 ince grid, coarsen 4, yarı aydınlık blok → `"all"` False,
    `"majority"` True; tam aydınlık/tam karanlık bloklar iki kuralda aynı.
  - `lit_run` / `forward_run` elle: `[1,1,0,1,1,1]` → `[1,2,0,1,2,3]` / `[2,1,0,3,2,1]`.
  - `edge_tables`: düz 3×3 grid → 8 ofset açık, `d = ceil(travel/slice)`
    kardinal 1 / köşegen (slice küçükse) 2; eğim duvarı (yükseklik atlaması)
    kenarı kapatır; geçilemez hücre ve köşe kesme kuralı; simetri
    (`ok[k][src] == ok[−k][dst]`).
  - `forward_reach` / `backward_reach` / `prune_corridor`, d ≡ 1: 1×5 hücre × 5
    dilim elle kurulan hacimde kökler ve çıkmazlar budanır (bilinen voksel
    kümesi); yalıtık geç yanan hücre (`t ≥ 2`) koridora giremez; erken sönen
    hücre koridorda kalmaz.
  - Kaba kuvvet çapraz kontrol: tohumlu rastgele 4×4×8 hacimler, açık voksel
    grafı üzerinde BFS (ileri/geri) ile `prune_corridor` birebir; ayrıca
    `corridor ⊆ ∪{26-bileşen: ilk ve son dilime dokunan}`.
  - d > 1: 1×2 hücre, hamle 2 dilim; hedef hücre yalnızca 2 ardışık dilim
    aydınlıksa kenar yok (3 gerekir), 3 dilimse var; kaynak hücrenin hamle
    boyunca aydınlık kalması da gerekir.
  - Boş koridor: tümü karanlık → hacim 0; `components` count 0; `route_dwell`
    boş rota.
  - `components`: iki ayrık blok → count 2, en büyük doğru; `spanning_count`.
  - `reachable_from`, `route_dwell` (elle rota: max ve `horizon_limited`),
    `corridor_summary` anahtarları ve JSON güvenliği (`allow_nan=False`).
- `test_pathfinder_4d.py` (oyuncak küpler): koridorla `astar_4d` rotayı
  koridor içinde tutar (her durum `corridor[t,r,c]`), `edges_rejected.
  continuous_illumination > 0` kapanan yolda, başlangıç dışarıda → hata
  cümlesi, küpsüz `require` → hata, tek küp → hata; uygulanmadan
  `states_outside_corridor` sayılır; `path_dark_hours` uygulanınca hep 0
  (gölge küpü koridorla tutarlı); `REJECTION_KEYS` yeni anahtar.
- `test_plan_4d_endpoint.py` (sentetik 16×16, `build_shadow_series`
  monkeypatch — `_earth_series_closing_at` kalıbı ile `_shadow_series_lit_until(k)`):
  blok varsayılan olarak var ve `enforced: false`; statik seride blok
  provenance `static` ve `require` → 422; koridor `k=3`'te kapanınca `require`
  → 404 ve detail "corridor" içerir; hep aydınlıkta → 200, `route.inside`,
  `path_dark_hours` tümü 0, `metrics.max_dwell_hours > 0`,
  `edges_rejected.continuous_illumination` anahtarı; `lit_rule="majority"`
  kabul, `lit_rule="x"` 422; `require_safe_haven` sahteleriyle birlikte 200;
  `GET /api/illumination-corridor` JSON (`binary_format.shape == [T,h,w]`) ve
  f32 (bayt sayısı `T·h·w·4`, `X-Series-*` başlıkları), `field=nope` 422.
- `test_illumination_corridor_real_grid.py` (skip-korumalı: gridler +
  `horizon_map.npy` + çekirdekler):
  - VIPER epoch'unda `build_corridor`: `corridor ⊆ lit_safe`, hacim > 0,
    `components` sayılabilir; standart VIPER rotası `require` → 404 ve detail
    başlangıç bloğunun karanlık olduğunu söyler.
  - Koridor-içi çift (modülün `reachable_from` ile seçtiği: koridorun
    dilim-0 kesitinde standart başlangıca en yakın hücre → ileri erişilebilir
    en uzak hücre): `require` → 200, `path_dark_hours` tümü 0,
    `safety_margins` LP-R01 ρ == `h_max_shadow_h`, `route.inside`, koridorsuz
    aynı çift 200 (süre/`nodes_expanded` kaydı); toplam süre sınırı.
  - Ay gecesi epoch'u (2026-09-13, LPR-1): `voxels.corridor == 0`, `require`
    → 404 ve detail "no lit" der.

## Hata davranışı

- `require_continuous_illumination` + statik gölge modeli → 422, sebep
  provenance'tan.
- `require_continuous_illumination` + koridor boş / başlangıç dışarıda /
  hedef koridor içinde ulaşılamaz → planlayıcı reddi → 404; detail
  koridor sayılarını ve ilk aydınlık dilimi söyler (`_no_path_reason` kalıbı).
- `lit_rule` geçersiz → 422 (pydantic).
- Koridor uygulanmıyorsa hiçbir mevcut davranış değişmez: aynı rota, aynı
  metrikler; yalnızca ek alanlar (`illumination_corridor`,
  `metrics.max_dwell_hours`, `metrics.states_outside_corridor`,
  `metrics.moves_outside_corridor`, `metrics.continuous_illumination_enforced`,
  `edges_rejected.continuous_illumination`).
- `inf`/`NaN` JSON'a sızmaz (dwell sonlu; oranlar 0 bölme korumalı).
- Bellek: küpler bool/int32; `_check_cube_budget` mevcut sınırı korur.

## Kapsam dışı (bilinçli)

- A3: hedef alt-hacmiyle planlayıcı budaması, zaman sıkıştırma, statik
  Dijkstra sezgiseli (`prune_corridor(sources, sinks)` bunun için hazır).
- Frontend 3-B koridor çizimi (veri sözleşmesine alanlar yazılır).
- İnce (80 m / 5 m) gridde koridor; ray-tracing aydınlanma; LRO WAC doğrulaması.
- FSR 2017 "strategic autonomy" (iletişimsiz kısa otonom sürüş).
- Olasılıksal koridor (B3 klon topluluğundan `p_illuminated ≥ p` kuralı) —
  gelecek işi olarak not.
- Bilinen iyimserliklere dokunulmaz (not edilir): planlayıcı hamle süresini
  dilime yukarı yuvarlarken enerjiyi yalnızca sürüş için düşüyor;
  `horizon_map` `np.rint` eşitlik kırılması; klon eğimleri %6–10 iyimser;
  termal model rover zarfıyla tutarsız (D3 → C6).

## Uygulama sırasında bulunanlar ve ölçümler (4 Eylül 2026)

**Sonda (tasarım öncesi, Site11, coarsen 4, varsayılan ufuk).**
`build_shadow_series` + iki aydınlık kuralı, `lit & coarse_traversable`:

| Epoch / rota | Dilim | Dilim (h) | Ufuk (h) | Kaba geçilebilir | `"all"` hacim | `"majority"` hacim | Başlangıç t0 aydınlık | Hedef aydınlık dilim |
|---|---|---|---|---|---|---|---|---|
| VIPER 2027-05-30, (358,494)→(206,426) | 100 | 0,0956 | 9,6 | 10 314 | 417 294 / 1 031 400 (%40,5) | 472 207 (%45,8) | hayır | 0 / 100 |
| LPR-1 2026-09-28, aynı çift | 100 | 0,0287 | 2,9 | 11 402 | 55 150 / 1 140 200 (%4,8) | 74 144 (%6,5) | hayır | 100 / 100 |
| LPR-1 Ay gecesi 2026-09-13, (186,34)→(494,450) | 246 | 0,0287 | 7,1 | 11 402 | 0 | 0 | hayır | 0 |

Bulgu: **standart iki rotanın başlangıç bloğu (89,123) iki epoch'ta da t0'da
karanlık; VIPER'ın hedef bloğu (51,106) hiçbir dilimde aydınlık değil** (D3'ün
ölçtüğü 4,55 h kesintisiz gölge bununla tutarlı). Yani `require_continuous_
illumination` standart rotaları tanım gereği reddeder; hızlanma ve "rota
gölgeye girmiyor" kanıtı koridor-içi çiftlerde ölçülür (rapor betiği çifti
koridordan seçer). Ay gecesi epoch'u boş koridorun gerçek örneği. Seri
üretimi 100 dilimde 0,1 s, blok kuralları 0,25 s.

**Koridor üyeliği ≠ "hamle boyunca aydınlık".** Elle kurulan 1×5 örnekte
ortaya çıktı: hücre 1 `t=2`'de aydınlanıyor ama `t=2`'de hiçbir durum orada
olamıyor (girmek için `t=1`'de de aydınlık gerekir); `t=3`'e giriş yine de
geçerli, çünkü hamle boyunca geçilen `(hücre 1, t=2)` vokseli aydınlıktır.
Yani koridor bir **durum** kümesidir, "hamle boyunca aydınlık" koşulu ise
budama öncesi `lit_safe` hacminin `run` küpüne bakar. `forward_reach` /
`backward_reach` / `reachable_from` bu yüzden ayrı `run` parametresi aldı;
planlayıcı da iki küp alıyor (`corridor_cube` üyelik, `corridor_lit_run_cube`
hamle koşulu). Koridorun kendi run'ıyla denetlemek geçerli girişleri reddeder
(testte sabitlendi).

**Geçişlerin hızı.** İlk sürüm `reach[t − d[src], src]` toplamasını zaman
ekseninde fancy-index ile yapıyordu: 100 dilimde budama 591 ms, 246 dilimde
1,7 s — her plan-4d çağrısına binen maliyet. Otomatik dilimde ofset başına
yalnızca 1–2 farklı `d` var; ayrık `d` değerleri üzerinde düz dilimleme
(`reach[t − d][src] & (d_tablosu == d)`) budamayı **56 ms**'ye indirdi
(×10). Gather yolu > 6 farklı değer için yedek; iki yol gerçek VIPER
koridorunda voksel voksel eşit (416 646 / 471 426) ve rastgele hacimlerde
testle sabit.

**Ad çakışması.** `main.py` 2-B `corridor.build_corridor`'ı zaten içe
aktarıyordu; koridor modülünün aynı adlı fonksiyonu `build_illumination_corridor`
/ `illumination_corridor_summary` takma adlarıyla alındı (üç mevcut test
bunu yakaladı).

**Ölçümler (Site11, 4 Eylül 2026; `scripts/illumination_corridor_report.py` →
[illumination_corridor_report.md](../../research/illumination_corridor_report.md)):**

| Ölçüm | Değer |
|---|---|
| VIPER 30 May 2027, varsayılan ufuk (100 × 0,0956 h, 125×125 @ 320 m) | geçilebilir 1 031 400 voksel; aydınlık-güvenli `all` 417 294 (%40,5) → koridor 416 646 (budanan %0,2); `majority` 472 207 (%45,8) → 471 426; CMU label `all` 50 bileşen / en büyük 379 720 (%91) / 44 iki ucu tutan |
| Standart çift (358,494)→(206,426) | başlangıç (89,123) hiçbir dilimde koridorda değil; hedef (51,106) 0/100; rota 0/41 durum içeride, `path_dark_hours` maks 4,55 h; `require` → 404 |
| Koridor-içi çift, VIPER, 8 h / 0,1 h | (105,89)→(94,27), Chebyshev 62 blok, 1 977 ulaşılabilir blok; budamasız **452 ms / 7 233 düğüm**, `all` **417 ms / 6 467** (×1,08 / ×1,12), `majority` 453 ms / 6 721 (×1,00 / ×1,08); üçünde de 62 hamle / 0 bekleme, 7,90 h, maliyet 7,547, `path_dark_hours` 0, LP-R01 ρ **96,00 h** (= `h_max_shadow_h`), SOC min %93,6, dwell 8,0 h (ufka dayalı); koridor reddi 1 342 (`all`) / 524 (`majority`) |
| LPR-1 28 Eyl 2026 | varsayılan 2,9 h ufuk: aydınlık %4,8 (55 150) → koridor 54 984; hedef 100/100 koridorda, başlangıç karanlık; rota 16/41 (`majority` 28/41) içeride, gölge 0,21 h; 8 h ufuk: aydınlık 20 566, **koridor 0** |
| LPR-1 Ay gecesi 13 Eyl 2026 (246 × 0,0287 h) | aydınlık 0, koridor 0, bileşen 0; `require` 404 "no block is lit at any of the 246 slices (7.1 h)" |
| Koridor kurulumu (ms, 100 dilim) | `all`: hacim 69, kenarlar 6, budama 56, dwell 4, toplam 135; `majority`: 217 / 5 / 62 / 4 / 287 (`coarsen_grid` nanmean); 246 dilim: 309 / 695; `components` 25–40; `reachable_from` ~155 (ilk sürüm) |
| Testler | 59 birim (`test_illumination_corridor.py`: hacim kuralları, run sayaçları, kenar tabloları ve simetri, elle 1×5 budama, 20 + 6 tohumlu kaba-kuvvet BFS çapraz kontrolü, `ndimage.label` kapsaması, d > 1, bileşenler, `reachable_from`, `build_corridor`, dwell, özet, `corridor_pair`, dilim/gather eşitliği), 8 planlayıcı (`test_pathfinder_4d.py`), 12 API (`test_plan_4d_endpoint.py`: blok, 422, 404, koridor içinde 0 gölge, hedef ulaşılamaz, `lit_rule`, haven birleşimi, GET manifest/f32/dwell/doğrulama/statik), 3 skip-korumalı gerçek grid (63 s) |

**Bulgular:**
- Standart iki rotanın başlangıç bloğu her iki epoch'ta karanlık; VIPER'ın
  hedefi hiç aydınlık değil → `require_continuous_illumination` onları tanım
  gereği reddeder. Bu, D3'ün ölçtüğü 4,55 h gölgeyle tutarlı.
- 10 saatlik ufukta budama neredeyse hiçbir şey silmez (%0,2): kutup
  aydınlanması bu ölçekte durağan; CMU'nun budaması 59 günlük pencerelerde
  anlamlı. Koridorun bu ufuktaki değeri budama değil, garanti.
- Hızlanma mütevazı (×1,08 süre, ×1,12 düğüm): maliyet küpü gölgeyi
  fiyatladığından budamasız A* zaten koridorda kalıyor. "22 s → X s" kazancı
  ölçülmedi; A3'ün hedef alt-hacmi (`prune_corridor(sources, sinks)`) rotaya
  özgü budama için hazır.
- LPR-1 28 Eyl'de 8 saatlik Güneş-eşzamanlı koridor yok (ada büzülüyor).

**Sapmalar (tasarımdan):**
- `forward_reach` / `backward_reach` / `reachable_from` `run` parametresi
  (üyelik ile hamle koşulu ayrımı).
- Geçişler ayrık `d` değerleri üzerinde dilimleme; gather yolu yedek
  (`_MAX_DISTINCT_SLICES = 6`).
- `corridor_pair` yardımcı fonksiyonu (spec'te yoktu).
- `corridor_summary(start=None, goal=None)` GET ucu için.
- `main.py` takma adları (`build_illumination_corridor`,
  `illumination_corridor_summary`).
- Rapor koridor-içi çifti uçtaki varsayılan ufukta değil, sabit 8 h / 0,1 h
  ufukta seçiyor (varsayılan ufuk çifte bağlı).
- `metrics.max_dwell_hours` planlayıcıda değil `main.plan_4d`'de
  (`route_dwell`) hesaplanıyor; planlayıcı `states_outside_corridor` /
  `moves_outside_corridor` raporluyor.
