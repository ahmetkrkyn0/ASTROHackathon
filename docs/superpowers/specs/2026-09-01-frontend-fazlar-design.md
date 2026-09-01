# Frontend Faz 1–7 — Tasarım Belgesi

**Tarih:** 1 Eylül 2026
**Branch:** `berke-3d-frontend`
**Kapsam:** yalnızca `frontend/` ve `docs/frontend/`. Backend'e tek satır dokunulmuyor.

---

## Amaç

Backend'de Faz 1'den Faz 7'ye kadar tamamlanmış işin ürettiği veri, frontend'de
şu an **görünmüyor**. Bu belge o veriyi kokpite taşıyan dokuz frontend modülünü
ve bunları taşıyacak modüler iskeleti tanımlar.

Tek cümlelik iddia: **backend'in ürettiği her fizik, koridor, zaman ve poz
bilgisi ekranda bir karşılık bulur — ve hiçbiri olduğundan daha kesin
gösterilmez.**

---

## Mevcut durum

`frontend/src/` şu an sekiz düz dosya, klasör yok:

| Dosya | Satır | Sorumluluk |
|---|---|---|
| `App.tsx` | 1 236 | Tüm state, tüm paneller, tüm yerleşim |
| `App.css` | 1 733 | Tüm stiller |
| `TerrainCanvas3D.tsx` | 705 | three.js 3B arazi |
| `MapCanvas.tsx` | 599 | 2B tuval, katman boyama, rota animasyonu |
| `LandingPage.tsx` | 420 | Giriş ekranı |
| `colormap.ts` | 359 | Renk rampaları |
| `api.ts` | 252 | 7 uç çağrısı |
| `main.tsx` | 9 | Bootstrap |

### Tüketilen ve tüketilmeyen uçlar

Backend 18 uç yayınlıyor. `api.ts` bunların 7'sini çağırıyor.

**Çağrılan:** `/api/health`, `/api/rovers`, `/api/profiles`, `/api/load-preprocessed`,
`/api/layers/{ad}`, `/api/plan`, `/api/cell-telemetry`

**Çağrılmayan — bu belgenin konusu:**

| Uç | Faz | Ne kaybediliyor |
|---|---|---|
| `/api/cell-telemetry` → `cost_breakdown`, `layer_validity` | 1–2 | Çağrılıyor ama yanıtın bu iki alanı atılıyor |
| `/api/plan` → `corridor`, `route_statistics`, `execution` | 2, 6 | Çağrılıyor ama bu üç alan atılıyor |
| `POST /api/replan` | 2 | Tetikleyici → yeniden planlama döngüsü |
| `POST /api/plan-4d` | 3 | BEKLE kararı, 4B planlama |
| `GET /api/illumination-series` | 3 | Zaman serisi gölge/sıcaklık küpü |
| `GET /api/terrain` | 3B hattı | Sahne manifestosu |
| `POST /api/plan-multi`, `POST /api/compare` | 5 | Profil karşılaştırması |
| `GET /api/reference-missions` | 6 | Yutu-2 / Pragyan gerçek misyon verisi |
| `POST /api/pose` | 7 | Poz → sapma → tetikleyici kapalı döngüsü |
| `GET /api/scenarios` | — | Senaryo kataloğu (`backend/data/scenarios/` şu an boş) |

---

## Kararlar

Bu kararlar tasarım öncesi alındı ve aşağıdaki her şeyin gerekçesi.

| # | Karar | Gerekçe |
|---|---|---|
| K1 | **Sıfırdan yazılır.** `origin/frontend` ve `origin/cesium` branch'lerindeki hazır paneller (`CorridorPanel`, `Plan4DPanel`, `ReplanPanel`, `CostBreakdownPanel`, `MissionTimeline`, `layerCatalog.ts`, `useLayers.ts`) **kullanılmaz** | O branch'ler `daf4039`'dan ayrılmış; bu branch aynı noktadan 63 commit ileride (Faz 4–7 dahil). Eski şemaya göre yazılmış kodu doğrulamak, yeniden yazmaktan pahalıya gelebilir ve karışık bir taban bırakır |
| K2 | **`App.tsx` refactor edilmez.** Kademeli parçalama | Arkadaşlar aynı dosyada çalışıyor; büyük bir yeniden düzenleme her açık dalı kırar. `App.tsx` bugünkü boyutunda kalır, faz başına birkaç satır uzar |
| K3 | **İnce read-only context + faz-sahipli state** | State'i yukarı taşımak K2'ye aykırı; global store yeni bağımlılık demek. `App.tsx`'in *zaten sahip olduğu* değerler paylaşılır, gerisi modülün kendi hook'unda kalır |
| K4 | **Önce 2B; 3B aynı overlay sözleşmesinden beslenir** | Her faz 2B'de kesin çalışır. Çizim mantığı tuvalden bağımsız yazılırsa 3B'ye geçiş faz modüllerini hiç değiştirmez |
| K5 | **Faz 4 statik vitrindir** | `lunapath_ros` içinde rosbridge/websocket yok — ROS 2'nin frontend'e açılan HTTP yüzeyi yok. Canlı bağlantı iddiası dürüst olmaz. rosbridge "sonra yapılacak" olarak kaydedilir |
| K6 | **Demo etkisi sırası** | Her adım tek başına gösterilebilir bir şey bırakır |
| K7 | **UI dili İngilizce, belgeler Türkçe** | Mevcut arayüz İngilizce (`Mission Workspace`, `Route Analytics`); belgeler ve plan Türkçe |

---

## Mimari

### Klasör düzeni

```
frontend/src/
├─ App.tsx                    ← ~8 satır eklenir; içeriği taşınmaz
├─ MapCanvas.tsx              ← overlays prop'u eklenir (~5 satır)
├─ TerrainCanvas3D.tsx        ← F0'da dokunulmaz
├─ api.ts                     ← dokunulmaz; eski çağrılar yerinde kalır
│
├─ mission/
│   ├─ MissionContext.tsx     ← read-only durum + iki eylem
│   ├─ slots.tsx              ← LeftRailSlot · RightRailSlot · BottomDock · CanvasOverlaySlot
│   ├─ geo.ts                 ← CRS metre ⇄ fine piksel dönüşümünün TEK kaynağı
│   └─ types.ts               ← backend yanıt tipleri (Corridor, Plan4D, PoseFix, …)
│
├─ api/
│   ├─ client.ts              ← tek fetch sarmalayıcı
│   ├─ plan.ts  replan.ts  plan4d.ts  pose.ts
│   ├─ terrain.ts  series.ts  compare.ts  missions.ts
│
├─ overlay/
│   ├─ types.ts               ← OverlayLayer
│   ├─ useOverlays.ts         ← kayıt defteri
│   ├─ draw2d.ts              ← OverlayLayer → MapCanvas
│   └─ draw3d.ts              ← (sonra) OverlayLayer → three.js
│
└─ features/
    ├─ layer-provenance/      F1
    ├─ cost-explain/          F1–2
    ├─ corridor/              F2
    ├─ replan/                F2
    ├─ time-axis/             F3
    ├─ pose-loop/             F7
    ├─ profile-compare/       F5
    ├─ mission-validation/    F6
    └─ ros-showcase/          F4
```

### `MissionContext` — paylaşılan okuma modeli

`App.tsx`'in **zaten sahip olduğu** değerler, olduğu gibi yayınlanır. Buraya yeni
state eklenmez.

```ts
interface MissionState {
  gridMeta:      { rows: number; cols: number; resolutionM: number } | null
  roverId:       string
  weights:       PlanWeights
  start:         [number, number] | null
  goal:          [number, number] | null
  planResult:    PlanResponse | null
  selectedCell:  [number, number] | null
  cellTelemetry: CellTelemetryResponse | null   // HAM yanıt, kırpılmamış
  activeLayer:   MapViewMode
  dimension:     '2d' | '3d'
}

interface MissionActions {
  setStart(cell: [number, number] | null): void
  setGoal(cell: [number, number] | null): void
}
```

`cellTelemetry` ham yanıttır. `App.tsx` bugün `mapFocusTelemetryResponse` ile
yanıtın dört alanını alıp `cost_breakdown` ve `layer_validity`'yi atıyor;
context ham yanıtı da tutar, böylece F1 ve F1–2 ikinci bir ağ isteği yapmaz.
**Bu, `App.tsx`'e yapılan tek içerik değişikliğidir** (bir `setState` çağrısı).

### Yuva mekanizması

`App.tsx` dört yuva bileşeni yerleştirir; her yuva kendisine kayıtlı modülleri
sırayla render eder:

- `<LeftRailSlot />` — `rail-scroll` içinde, mevcut `rail-section`'ların altında
- `<RightRailSlot />` — Mission Snapshot panelinin altında
- `<BottomDock />` — tuvalin altında yeni bir şerit (zaman ekseni için)
- `<CanvasOverlaySlot />` — tuvalin üstünde mutlak konumlu HUD katmanı

Yeni bir faz eklemek `App.tsx`'te **tek satırdır**: ilgili yuvaya modülün
`index.tsx`'ini koymak.

### Overlay sözleşmesi

Modüller `MapCanvas`'a doğrudan çizmez. `useOverlays().register(id, layers)`
çağırır, `MapCanvas` tek bir `overlays` prop'u alır.

```ts
type PixelPoint = { row: number; col: number }   // HER ZAMAN fine grid pikseli

type OverlayLayer =
  | { kind: 'polyline'; id: string; points: PixelPoint[]; style: OverlayStyle }
  | { kind: 'ribbon';   id: string; center: PixelPoint[]; halfWidthPx: number[]; style: OverlayStyle }
  | { kind: 'points';   id: string; points: PixelPoint[]; style: OverlayStyle }
  | { kind: 'field';    id: string; data: Float32Array; rows: number; cols: number;
                        domain: [number, number]; ramp: RampName; opacity: number }
```

`PixelPoint`'in birimi sözleşmenin kilit noktası: her modül kendi koordinatını
**fine grid pikseline** çevirmekle yükümlü (bunun için `mission/geo.ts`); tuval
başka birim tanımaz. 3B'ye geçiş `draw3d.ts` yazmaktan ibarettir — faz modülleri
değişmez (K4).

### Modül sözleşmesi

Her `features/<x>/` klasörü:

| Dosya | Zorunlu | Sorumluluk |
|---|---|---|
| `index.tsx` | evet | Dışa açılan **tek** bileşen. Dışarıdan başka hiçbir dosya import edilmez |
| `use<X>.ts` | evet | State + fetch. Modülün tüm state'i burada, `App.tsx`'te değil |
| `<X>Panel.tsx` | evet | UI |
| `overlays.ts` | hayır | Tuvale ne çizeceği |
| `<x>.css` | hayır | Modüle özel stil. `App.css`'e dokunulmaz |

---

## Fazlar

Sıra: **F0 → F1 → F1–2 → F2a → F2b → F3 → F7 → F5 → F6 → F4** (K6).

### F0 — İskelet

**Çıktı:** `mission/`, `api/client.ts`, `overlay/` ve dört yuva. Hiçbir panel
taşınmaz, hiçbir davranış değişmez.

**Dokunulan mevcut dosyalar:**
- `App.tsx`: `<MissionProvider>` sarmalayıcı, dört yuva, `MapCanvas`'a `overlays`
  prop'u, `setCellTelemetry(raw)` — toplam ~8 satır ekleme, 0 satır silme
- `MapCanvas.tsx`: `Props`'a `overlays?: OverlayLayer[]`, çizim döngüsünün
  sonunda `drawOverlays(ctx, overlays)` — ~5 satır

**Kabul:** `npm run typecheck`, `npm run lint` ve `npm run build` temiz;
uygulama F0 öncesiyle **birebir aynı** davranıyor; `overlays={[]}` ile hiçbir
görsel fark yok.

---

### F1 — `layer-provenance` · Katman dürüstlüğü

**Uç:** `GET /api/layers/{ad}` yanıt başlıkları + `cell-telemetry.layer_validity`

**Okunan alanlar:** `X-Layer-Validity` (`MEASURED` / `MODELED` / `SYNTHETIC`),
`X-Layer-Min`, `X-Layer-Max`, `X-Layer-Nodata`, `X-Layer-Resolution-M`

**Panel:** Sol ray — katman seçicinin yanında rozet; açılınca kart: bu katman
ölçüm mü model mi, değer aralığı, kaç hücre veri yok, hangi çözünürlükte.

**Overlay:** yok.

**Kabul:** Sekiz katmanın her biri (`elevation`, `slope`, `aspect`, `thermal`,
`thermal_min`, `shadow_ratio`, `cost`, `traversable`) etiketini taşıyor;
`SYNTHETIC` olan görsel olarak ayrışıyor; başlık okunamazsa "bilinmiyor" yazıyor,
`MEASURED` varsayılmıyor.

---

### F1–2 — `cost-explain` · Neden pahalı?

**Uç:** `GET /api/cell-telemetry` → `cost_breakdown` (context'ten, yeni istek yok)

**Şema:** `{ slope, energy, shadow, thermal, total }` — her değer **ağırlıklı**
katkı. `null` = sonsuz katkı = **GEÇİLEMEZ** (bkz. T3).

**Panel:** Sağ ray — hücre seçilince dört bileşenin katkı çubuğu, toplam, ve
`null` varsa hangi bileşenin hücreyi kapattığı.

**Overlay:** seçili hücre işareti (`points`).

**Kabul:** Geçilebilir bir hücrede dört katkının toplamı `total`'a eşit
(yuvarlama toleransında); geçilemez bir hücrede "GEÇİLEMEZ — <bileşen>" yazıyor
ve sayı uydurulmuyor.

---

### F2a — `corridor` · Koridor sözleşmesi

**Uç:** `POST /api/plan` → `corridor` (context'ten)

**Şema:** `waypoints` (CRS metre `x,y`), `half_width_m`, `max_slope_deg`,
`energy_budget_wh`, `thermal_budget_K_s`, `fallback_points`, `crs`, `corridor_id`

**Panel:** Sağ ray — segment tablosu: yarı genişlik, eğim tavanı, enerji ve
termal bütçe. `corridor_id` görünür (F7 bunu yankılayacak).

**Overlay:** `ribbon` — rota etrafında değişken genişlikli koridor; `points` —
sığınak noktaları (`fallback_points`).

**Kabul:** Koridor rota boyunca daralıp genişliyor; CRS metre → fine piksel
dönüşümü `mission/geo.ts` üzerinden ve `/api/terrain`'in `georeference.origin` +
`resolution_m` değerleriyle yapılıyor, sabit sayı yok; `corridor` `null` dönerse
panel "koridor üretilemedi" diyor.

---

### F2b — `replan` · Tetikleyiciler

**Uç:** `POST /api/replan`

**Yedi tetikleyici ve gerektirdiği telemetri:**

| `trigger_id` | Gerekli alanlar |
|---|---|
| `soc_deviation` | `actual_soc`, `planned_soc` |
| `inner_temperature` | `actual_inner_c`, `predicted_inner_c` |
| `time_drift` | `drift_minutes` |
| `corridor_violation` | `lateral_offset_m`, `half_width_m` |
| `comm_window` | `comm_minutes_remaining` |
| `localization_uncertainty` | `localization_covariance_m`, `half_width_m` |
| `slip_accumulation` | `map_progress_m`, `odometer_claim_m` |

**Panel:** Sol ray — telemetri enjeksiyon formu + yedi tetikleyicinin durumu:
**ateşledi** / **kontrol edildi, temiz** / **kontrol EDİLEMEDİ (eksik alan)**.

**Overlay:** eski rota soluk `polyline`, yeni rota parlak `polyline`.

**Kabul:** Yanıtın `skipped` dizisi ekranda görünüyor — eksik telemetri yüzünden
değerlendirilememiş bir tetikleyici asla "temiz" gösterilmiyor. Ateşleyen her
tetikleyicinin `detail` metni okunuyor.

---

### F3 — `time-axis` · Zaman ekseni ve BEKLE

**Uçlar:** `POST /api/plan-4d`, `GET /api/illumination-series`

**`plan-4d` alanları:** `path_pixels` (fine), `path_pixels_coarse`,
`path_states`, `metrics.wait_steps`, `metrics.move_steps`,
`metrics.arrival_slice`, `metrics.arrival_hours`, `shadow_model`, `n_slices`,
`slice_hours`, `horizon_hours`, `coarsen`, `effective_resolution_m`

**`illumination-series`:** JSON manifest (`sun` dizisi: `azimuth_grid_deg`,
`elevation_deg`; `fields.shadow` / `fields.surface_temp_c` → `binary_url`)
+ f32 küp: `(n_slices, rows, cols)`, slice-major sonra row-major, NaN = veri yok.

**Panel:** Alt dok — zaman kaydırıcısı, oynat/duraklat, Sun track göstergesi,
"planlayıcı N adım bekledi (≈ H saat)" rozeti.

**Overlay:** `field` — seçili t diliminin gölgesi veya yüzey sıcaklığı;
`polyline` — 4B rota (`path_pixels`, fine).

**Kabul:** Kaydırıcı hareket edince tuval değişiyor; `wait_steps > 0` olan bir
senaryoda BEKLE kararı yazıyor; **`shadow_model.model === "static"` ise panel
"zaman serisi yok — ufuk önbelleği üretilmemiş" diyor ve animasyonu sahte
göstermiyor.**

> Ön koşul: `python scripts/build_horizon_cache.py` bir kez çalıştırılmalı
> (`lunapath/data/processed/horizon_map.npy`, 69 MiB, `.gitignore`'da).

---

### F7 — `pose-loop` · Kapalı döngü

**Uç:** `POST /api/pose`

**Alanlar:** `corridor_fix` (`lateral_offset_m`, `along_track_m`, `half_width_m`),
`fired_triggers`, `evaluated`, `skipped`, `trigger_state`, `recommended_action`,
`corridor_id`, `corridor_rover_id`, `pose_source`

**Panel:** Sağ ray — poz girişi, koridora göre sapma, ateşleyen tetikleyiciler ve
`recommended_action`. `stop_and_localize` önerisi `replan`'dan görsel olarak
ayrışır.

**Overlay:** `points` — poz; `polyline` — koridora dik sapma çizgisi.

**Kabul:** F2a'nın verdiği `corridor_id` yankılanıyor; `previous_along_track_m`
bir önceki yanıttan besleniyor; koridor dışı bir poz → `corridor_violation` →
`/api/replan` zinciri ekranda uçtan uca izlenebiliyor. Aktif koridor yokken gelen
409 "önce rota planla" olarak gösteriliyor; bilinmeyen `corridor_id` için gelen
404 "koridor süresi doldu" olarak gösteriliyor.

---

### F5 — `profile-compare` · Profil karşılaştırması

**Uçlar:** `POST /api/plan-multi`, `POST /api/compare`

**Alanlar:** sonuç başına `profile_id`, `profile_name`, `color`, `metrics`,
`constraint_check`, `simulation_summary`; `compare` ayrıca `comparison`

**Panel:** Sağ ray — profil × metrik tablosu; `constraint_check` ihlalleri
işaretli (`max_shadow_h`, `max_energy_wh`, `min_soc`).

**Overlay:** her profilin rotası kendi `color`'ında `polyline`.

**Kabul:** Dört profil aynı başlangıç/hedef için aynı anda çizili; bir profil
`error` döndürürse tabloda hata olarak görünüyor, satır sessizce kaybolmuyor.

---

### F6 — `mission-validation` · Gerçeklik kontrolü

**Uçlar:** `GET /api/reference-missions`, `POST /api/plan` → `route_statistics`

**Alanlar:** `note`, `missions[].mission`, `.total_distance_m`, `.as_of`,
`.lower_bound_rate_m_per_calendar_day`, `.milestones`;
`route_statistics.waypoint_count`, `.slope_histogram`, `.risk_breakdown_pct`,
`.min_surface_temp_c`, `.max_surface_temp_c`

**Panel:** Sağ ray — bizim rota istatistiklerimiz Yutu-2 / Pragyan yayınlanmış
rakamlarının yanında, **kaynak künyeleriyle**.

**Overlay:** yok.

**Kabul:** `note` alanı ekranda ("oranlar Ay gecesi uykusunu içerir, alt
sınırdır") — hız karşılaştırması olduğundan daha iddialı sunulmuyor.

---

### F4 — `ros-showcase` · Entegrasyon vitrini

**Uç:** yok. Statik içerik.

**Panel:** Sol ray "Integration" sekmesi — `grid_map` katmanları, `PlanTraverse`
action arayüzü, `rosbag2` kaydı, `scripts/nav2_baseline.py` çıktısı, RViz görseli.

**Kabul:** Hiçbir yerde canlı ROS 2 bağlantısı iddiası yok; `FRONTEND_YAPISI.md`
rosbridge'i "sonra yapılacak" olarak kaydediyor.

---

## Tuzaklar

Bunlar kaynaktan doğrulandı; her modül bunlara uymak zorunda.

| # | Tuzak | Kural |
|---|---|---|
| T1 | `astar_metrics.total_energy_wh` ve `total_shadow_hours` **her zaman `null`** (`pathfinder.py:734-735, 790-791`). Mevcut `api.ts` bunları `number` olarak tipliyor — hatalı | Enerji için `summary.total_energy_consumed_wh`, gölge için `summary.total_shadow_exposure` / `summary.max_continuous_shadow_h` kullanılır. Tip `number \| null` olarak düzeltilir |
| T2 | Maliyet bileşeninin adı `shadow`, grid katmanının adı `shadow_ratio` | Karıştırılmaz; ikisi ayrı ad uzayı |
| T3 | `cost_breakdown`'da `null` = sonsuz katkı = GEÇİLEMEZ, "veri yok" değil (`costmap.py:143-158`) | `null` asla 0 gibi çizilmez |
| T4 | `plan-4d`: `path_pixels` **fine** grid; `path_pixels_coarse` ve `path_states` **coarse** grid (`effective_resolution_m`) | Tuvale her zaman `path_pixels` çizilir |
| T5 | `corridor.waypoints` **CRS metre**, piksel değil | `mission/geo.ts` üzerinden çevrilir; grid geometrisi asla sabitlenmez |
| T6 | `illumination-series` f32 küpü: slice-major sonra row-major, NaN = veri yok | Sıra varsayılmaz, manifestteki `binary_format.order` okunur |
| T7 | Ufuk önbelleği yoksa `shadow_model.model === "static"` | Animasyon zamanla değişiyormuş gibi gösterilmez |
| T8 | `f32` katman yolunda hücre tavanı yok; JSON yolunda 65 536 hücre tavanı var | Katmanlar `format=f32` ile çekilir (mevcut `fetchLayer` zaten böyle) |
| T9 | Koridorlar yalnızca bellekte ve sınırlı sayıda tutulur; bilinmeyen `corridor_id` → 404 | 404 "koridor süresi doldu, yeniden planla" olarak gösterilir |
| T10 | `backend/data/scenarios/` boş → `/api/scenarios` boş liste döner | Senaryo seçici boş listeyi hata değil "senaryo yok" olarak gösterir |

---

## Dürüstlük kuralları

Backend'in her yerinde taşınan `validity` etiketi disiplini frontend'de de
geçerlidir:

1. **`UNCALIBRATED` / `SYNTHETIC` etiketli hiçbir sayı etiketsiz gösterilmez.**
   Slip modeli, termal gevşeme, sentetik gölge — hepsi kaynağını taşır.
2. **Değerlendirilemeyen bir kontrol "temiz" gösterilmez.** `skipped` her zaman
   görünür.
3. **`null` bir sayı 0 olarak çizilmez.**
4. **Statik bir model animasyonlu gösterilmez.**

---

## Doğrulama

Frontend'de test altyapısı yok (`package.json`'da test script'i yok) ve bu belge
kapsamında kurulmuyor. Her fazın doğrulaması:

- `npm run typecheck` — temiz
- `npm run build` — temiz
- `npm run lint` — `--max-warnings 0` ile temiz
- Fazın kabul kriteri, çalışan backend'e karşı elle doğrulanır ve faz commit'inin
  mesajında ne görüldüğü yazılır

---

## Kapsam dışı

- `App.tsx`'in gerçek refactor'ü (state'in hook'lara, panellerin bileşenlere
  ayrılması) — 7 faz bittikten sonra ayrı bir karar
- rosbridge / canlı ROS 2 bağlantısı — `FRONTEND_YAPISI.md`'ye kayıt düşülür
- 3B overlay çizimi (`draw3d.ts`) — sözleşme F0'da kurulur, uygulaması sonra
- `origin/frontend` ve `origin/cesium` panellerinin port edilmesi (K1)
- Backend'de herhangi bir değişiklik
- Frontend test altyapısı kurulumu
- `App.css`'in yeniden düzenlenmesi — modüller kendi CSS'ini getirir

---

## Riskler

| Risk | Etki | Azaltım |
|---|---|---|
| Ufuk önbelleği üretilmemiş → F3 animasyonu boş | En çarpıcı demo çalışmaz | F3 `shadow_model.model` okur ve dürüstçe söyler; `build_horizon_cache.py` F3 ön koşulu olarak belgelenir |
| CRS metre → piksel dönüşümü yanlış → koridor kayar | F2a ve F7 birlikte yanlış | Dönüşüm tek bir yerde (`mission/geo.ts`), F2a'da bilinen bir waypoint ile elle doğrulanır |
| Arkadaşların dalları `App.tsx`'te çakışır | Merge acısı | Faz başına birkaç satır ve ayrı commit; kural `FRONTEND_YAPISI.md`'de |
| `App.css` sınıf adı çakışması | Görsel bozulma | Modül CSS'i `.lp-<modül>-` ön ekiyle |
| Zaman küpü belleği (24 × 500 × 500 × 4 B ≈ 24 MB) | Tarayıcı yavaşlar | `downsample=2` varsayılan; tam çözünürlük isteğe bağlı |
