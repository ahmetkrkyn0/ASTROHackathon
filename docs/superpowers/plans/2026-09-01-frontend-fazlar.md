# Frontend Faz 1–7 Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend'de tamamlanmış Faz 1–7'nin ürettiği veriyi (koridor, yeniden planlama, 4B zaman ekseni, poz döngüsü, profil karşılaştırması, misyon doğrulaması, katman kökeni) kokpitte görünür kılmak — `App.tsx` refactor edilmeden, dokuz bağımsız modül olarak.

**Architecture:** `App.tsx` yerinde kalır ve faz başına birkaç satır uzar. Paylaşılan durum ince bir read-only context (`MissionContext`) üzerinden yayınlanır; her modül kendi state'ini kendi hook'unda tutar. Tuvale çizim `OverlayLayer` sözleşmesi üzerinden yapılır — modüller `MapCanvas`'a doğrudan dokunmaz, böylece aynı overlay listesi ileride 3B'ye beslenebilir.

**Tech Stack:** React 18 · TypeScript 5.3 · Vite 5 · three.js 0.183 (mevcut) · yeni bağımlılık **yok**

**Spec:** [`docs/superpowers/specs/2026-09-01-frontend-fazlar-design.md`](../specs/2026-09-01-frontend-fazlar-design.md)

---

## Global Constraints

Bu kısıtlar **her görev** için geçerlidir. Görevler bunları tekrar etmez.

- **Yeni npm bağımlılığı eklenmez.** React, TypeScript ve mevcut `three` dışında hiçbir paket kurulmaz.
- **`App.css`'e dokunulmaz.** Her modül kendi CSS dosyasını `features/<modül>/<x>.css` içinde getirir ve tüm sınıf adları `.lp-<modül>-` ön ekiyle başlar.
- **`api.ts`'e dokunulmaz.** Mevcut yedi çağrı yerinde kalır; yeni uçlar `src/api/` altında ayrı dosyalara yazılır. Tek istisna: Görev 2'deki `AstarMetrics` tip düzeltmesi.
- **`App.tsx`'e yapılan her değişiklik kendi commit'idir**, içine başka iş karışmaz.
- **Modül dışa yalnızca `index.tsx`'ini açar.** Başka bir modülün iç dosyası import edilmez.
- **Koordinat birimi:** `OverlayLayer` içindeki her koordinat **fine grid pikselidir** (`{row, col}`). CRS metresi veya coarse piksel `mission/geo.ts` ile çevrilir.
- **Validity sabit yazılmaz.** `SYNTHETIC < DERIVED < MODEL < MEASURED`; değer her zaman `/api/terrain`'den okunur, `null` gelirse "unknown" gösterilir.
- **`null` bir sayı 0 olarak çizilmez.** `cost_breakdown`'da `null` = GEÇİLEMEZ demektir.
- **Değerlendirilemeyen bir kontrol "temiz" gösterilmez.** `skipped` dizisi her zaman görünür kalır.
- **UI dili İngilizce**, kod yorumları ve commit mesajları İngilizce, belgeler Türkçe.
- **Her görev sonunda üçü de temiz olmalı:** `npm run typecheck`, `npm run lint`, `npm run build`.
- **Commit mesajları Conventional Commits** (`feat:`, `fix:`, `refactor:`, `docs:`).

### Doğrulama hakkında

`frontend/package.json` içinde test script'i yok ve bu plan kapsamında test altyapısı **kurulmuyor** (spec, "Kapsam dışı"). Bu yüzden her görevin doğrulama adımları:

1. `npm run typecheck` — tip hatası yok
2. `npm run lint` — `--max-warnings 0` ile temiz
3. `npm run build` — derleniyor
4. **Elle kabul:** çalışan backend'e karşı, görevde yazılı tam adımlar; ne görüldüğü commit mesajına yazılır

Backend'i ayağa kaldırma (her elle kabul adımı bunu varsayar):

```bash
cd backend && uvicorn app.main:app --reload --port 8000
# ayrı terminal
cd frontend && npm run dev
# tarayıcıda uygulamayı aç, giriş ekranından Mission Workspace'e geç
```

---

## File Structure

### Yeni dosyalar

| Dosya | Sorumluluk | Görev |
|---|---|---|
| `src/api/client.ts` | Tek fetch sarmalayıcı: JSON/f32 çözme, hata → `Error`, `AbortSignal` | 1 |
| `src/mission/types.ts` | Backend yanıt tipleri (`TerrainManifest`, `Corridor`, `Plan4DResponse`, `PoseResponse`, …) | 2 |
| `src/mission/geo.ts` | CRS metre ⇄ fine piksel dönüşümünün **tek** kaynağı | 3 |
| `src/overlay/types.ts` | `OverlayLayer`, `OverlayStyle`, `PixelPoint` | 4 |
| `src/overlay/useOverlays.ts` | Overlay kayıt defteri (context) | 4 |
| `src/overlay/draw2d.ts` | `OverlayLayer[]` → 2B canvas çizimi | 4 |
| `src/mission/MissionContext.tsx` | Read-only durum + `setStart`/`setGoal` | 5 |
| `src/mission/slots.tsx` | `LeftRailSlot` · `RightRailSlot` · `BottomDock` · `CanvasOverlaySlot` | 5 |
| `src/api/terrain.ts` | `GET /api/terrain` | 6 |
| `src/features/layer-provenance/*` | F1 — katman kökeni | 6 |
| `src/features/cost-explain/*` | F1–2 — maliyet kırılımı | 7 |
| `src/features/corridor/*` | F2a — koridor | 8 |
| `src/api/replan.ts` · `src/features/replan/*` | F2b — tetikleyiciler | 9 |
| `src/api/series.ts` · `src/api/plan4d.ts` · `src/features/time-axis/*` | F3 — zaman ekseni | 10, 11 |
| `src/api/pose.ts` · `src/features/pose-loop/*` | F7 — poz döngüsü | 12 |
| `src/api/compare.ts` · `src/features/profile-compare/*` | F5 — profil kıyası | 13 |
| `src/api/missions.ts` · `src/features/mission-validation/*` | F6 — misyon doğrulaması | 14 |
| `src/features/ros-showcase/*` | F4 — ROS 2 vitrini | 15 |

### Değiştirilecek mevcut dosyalar

| Dosya | Ne değişiyor | Görev |
|---|---|---|
| `src/api.ts` | `AstarMetrics.total_energy_wh` ve `total_shadow_hours` → `number \| null` | 2 |
| `src/MapCanvas.tsx` | `Props`'a `overlays?: OverlayLayer[]`; çizim sonunda `drawOverlays` | 4 |
| `src/App.tsx` | `MissionProvider` + `OverlayProvider` sarmalayıcı, dört yuva, `overlays` prop'u, ham telemetri | 5 |
| `src/App.tsx` | Faz başına bir satır: modülü yuvasına koymak | 6–15 |

---

## Görev sırası ve bağımlılıklar

```
1 client ──┐
2 types ───┼──► 3 geo ──┐
           │            ├──► 5 context+slots ──► 6 F1 ──► 7 F1-2
           └──► 4 overlay ──┘                      │
                                                   ├──► 8 F2a ──► 9 F2b
                                                   │        └──► 12 F7
                                                   ├──► 10 küp ──► 11 F3
                                                   ├──► 13 F5
                                                   ├──► 14 F6
                                                   └──► 15 F4
```

Görev 1–5 iskelettir ve seri yürütülür. Görev 6'dan sonra 7, 8, 10, 13, 14, 15 birbirinden bağımsızdır — paralel dağıtılabilir. 9 ve 12, 8'in `corridor_id`'sine bağlıdır. 11, 10'a bağlıdır.

---

### Görev 1: `api/client.ts` — tek fetch sarmalayıcı

Her yeni uç çağrısı bunu kullanır. Hata gövdesindeki `detail` alanını okuyup
`Error` mesajına koyar — backend her hatayı `{"detail": "..."}` biçiminde
döndürür (`HTTPException`).

**Files:**
- Create: `frontend/src/api/client.ts`

**Interfaces:**
- Consumes: hiçbir şey (ilk görev)
- Produces:
  - `getJson<T>(path: string, signal?: AbortSignal): Promise<T>`
  - `postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T>`
  - `getFloat32(path: string, signal?: AbortSignal): Promise<{ data: Float32Array; headers: Headers }>`
  - `ApiError` sınıfı, `status: number` alanıyla

- [ ] **Adım 1: Dosyayı oluştur**

```ts
const BASE = '/api'

/** An HTTP failure the backend described in its `detail` field. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/**
 * Every FastAPI failure in this backend arrives as `{"detail": "..."}`
 * (HTTPException). Reading it here means no caller has to, and a caller
 * that only prints `error.message` still shows the real reason instead of
 * a bare status code.
 */
async function failure(response: Response): Promise<ApiError> {
  let detail = response.statusText
  try {
    const body = (await response.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') {
      detail = body.detail
    }
  } catch {
    // Body was not JSON. statusText is the best we have.
  }
  return new ApiError(response.status, detail)
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { signal })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

export async function postJson<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok) throw await failure(response)
  return (await response.json()) as T
}

/**
 * The binary path. Headers come back with the array because the backend's
 * self-description (rows, cols, validity, value range) travels in
 * `X-Layer-*` / `X-Series-*` headers, not in the payload.
 */
export async function getFloat32(
  path: string,
  signal?: AbortSignal,
): Promise<{ data: Float32Array; headers: Headers }> {
  const response = await fetch(`${BASE}${path}`, { signal })
  if (!response.ok) throw await failure(response)
  return {
    data: new Float32Array(await response.arrayBuffer()),
    headers: response.headers,
  }
}
```

- [ ] **Adım 2: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: ikisi de hatasız çıkar (çıkış kodu 0)

- [ ] **Adım 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat(frontend): add a single fetch wrapper that reads FastAPI detail"
```

---

### Görev 2: `mission/types.ts` — backend yanıt tipleri + `AstarMetrics` düzeltmesi

Spec T1: `astar_metrics.total_energy_wh` ve `total_shadow_hours` backend'de
**her zaman `null`** (`pathfinder.py:734-735, 790-791`) ama `api.ts` bunları
`number` diye tipliyor. Bu görev hem yeni tipleri getirir hem o hatayı düzeltir.

**Files:**
- Create: `frontend/src/mission/types.ts`
- Modify: `frontend/src/api.ts:39-51` (`AstarMetrics` arayüzü)

**Interfaces:**
- Consumes: `api.ts`'ten `PlanWeights`
- Produces: `TerrainManifest`, `LayerManifestEntry`, `Corridor`, `CostBreakdown`,
  `ReplanResponse`, `TriggerRef`, `Plan4DResponse`, `SeriesManifest`,
  `PoseResponse`, `CompareResponse`, `ReferenceMissions`, `RouteStatistics`,
  `Validity`

- [ ] **Adım 1: `api.ts`'teki hatalı tipi düzelt**

`frontend/src/api.ts` içinde `AstarMetrics` arayüzünde şu iki satırı bul:

```ts
  total_energy_wh: number
  total_shadow_hours: number
```

Şununla değiştir:

```ts
  // Always null: pathfinder.py:734-735 and 790-791 emit these as None and
  // point at the simulation summary instead. Real energy is
  // summary.total_energy_consumed_wh; real shadow exposure is
  // summary.total_shadow_exposure / summary.max_continuous_shadow_h.
  total_energy_wh: number | null
  total_shadow_hours: number | null
```

- [ ] **Adım 2: `mission/types.ts` dosyasını oluştur**

```ts
import type { PlanWeights } from '../api'

/** Ranked SYNTHETIC < DERIVED < MODEL < MEASURED (traversability.py:109). */
export type Validity = 'SYNTHETIC' | 'DERIVED' | 'MODEL' | 'MEASURED'

export const VALIDITY_RANK: Record<Validity, number> = {
  SYNTHETIC: 0,
  DERIVED: 1,
  MODEL: 2,
  MEASURED: 3,
}

// ── GET /api/terrain ───────────────────────────────────────────────────────

export interface LayerManifestEntry {
  units: string
  description: string
  /** null when the grid metadata carried no label for this layer. */
  validity: Validity | null
  /** null when the layer holds no finite value. */
  min: number | null
  max: number | null
  nodata: number
  binary_url: string
  json_url: string
}

export interface TerrainManifest {
  grid: {
    rows: number
    cols: number
    resolution_m: number
    span_m: [number, number]
    cells: number
  }
  georeference: {
    /** Projected CRS metres of the window's north-west corner. */
    origin: { x: number; y: number } | null
    crs: string | null
    window_offset: { row: number; col: number } | null
    row_axis: 'north-to-south'
    col_axis: 'west-to-east'
  }
  elevation: {
    min_m: number
    max_m: number
    relief_m: number
    vertical_exaggeration_suggested: number
  }
  binary_format: {
    dtype: string
    endian: string
    order: string
    nodata: string
    bytes_per_layer: number
    decode: string
  }
  rover: { id: string; name: string }
  weights: PlanWeights | null
  layers: Record<string, LayerManifestEntry>
}

// ── GET /api/cell-telemetry ────────────────────────────────────────────────

/**
 * Weighted contribution per cost layer, plus the total.
 *
 * null means an INFINITE contribution -- the cell is IMPASSABLE. Starlette
 * renders JSON with allow_nan=False, so costmap.explain() maps inf to null
 * (costmap.py:143-158). It never means "no data".
 */
export interface CostBreakdown {
  slope: number | null
  energy: number | null
  shadow: number | null
  thermal: number | null
  total: number | null
}

export interface CellTelemetryResponse {
  row: number
  col: number
  lon: number
  lat: number
  altitude_m: number | null
  thermal_c: number | null
  thermal_min_c: number | null
  resolution_m: number
  span_km: number
  cost_breakdown: CostBreakdown
  layer_validity: Record<string, Validity>
}

// ── POST /api/plan -> corridor, route_statistics ───────────────────────────

export interface Corridor {
  /** Projected CRS metres (x, y), one per path pixel. */
  waypoints: Array<[number, number]>
  half_width_m: number[]
  max_slope_deg: number[]
  energy_budget_wh: number[]
  thermal_budget_K_s: number[]
  fallback_points: Array<[number, number]>
  crs: string
  corridor_id: string
}

export interface RouteStatistics {
  waypoint_count: number
  slope_histogram: Array<{ from_deg: number; to_deg: number; count: number }>
  risk_breakdown_pct: Record<string, number>
  min_surface_temp_c: number | null
  max_surface_temp_c: number | null
}

// ── POST /api/replan ───────────────────────────────────────────────────────

export type TriggerId =
  | 'soc_deviation'
  | 'inner_temperature'
  | 'time_drift'
  | 'corridor_violation'
  | 'comm_window'
  | 'localization_uncertainty'
  | 'slip_accumulation'

export interface TriggerRef {
  trigger_id: TriggerId
  detail: string
}

export interface ReplanResponse {
  replanned: boolean
  triggers: TriggerRef[]
  /** Trigger ids that WERE evaluated. */
  evaluated: string[]
  /** Trigger ids that could NOT be evaluated -- telemetry fields missing. */
  skipped: string[]
  reason?: string
  plan?: unknown
}

// ── POST /api/plan-4d ──────────────────────────────────────────────────────

export interface Plan4DResponse {
  /** FINE grid pixels -- this is what gets drawn. */
  path_pixels: Array<[number, number]>
  /** COARSE grid pixels, cell size = effective_resolution_m. */
  path_pixels_coarse: Array<[number, number]>
  path_states: Array<[number, number, number]>
  metrics: {
    wait_steps: number
    move_steps: number
    arrival_slice: number | null
    arrival_hours: number | null
    [key: string]: unknown
  }
  shadow_model: ShadowModel
  n_slices: number
  slice_hours: number
  slice_hours_source: string
  horizon_hours: number
  coarsen: number
  effective_resolution_m: number
  rover_id: string
}

export interface ShadowModel {
  /** "static" means the cube did NOT vary with time -- do not animate it. */
  model: string
  time_varying?: boolean
  reason?: string
  horizon_cache?: string
}

// ── GET /api/illumination-series ───────────────────────────────────────────

export interface SunSample {
  index: number
  utc: string
  azimuth_true_deg: number
  azimuth_grid_deg: number
  elevation_deg: number
}

export interface SeriesManifest {
  slices: number
  slice_hours: number
  start_utc: string | null
  grid: { rows: number; cols: number; resolution_m: number; downsample: number }
  shadow_model: ShadowModel
  thermal_model: { recipe: string; tau_s: number; validity: string }
  sun: SunSample[]
  fields: Record<
    'shadow' | 'surface_temp_c',
    { units: string; min: number | null; max: number | null; binary_url: string }
  >
  binary_format: {
    dtype: string
    endian: string
    /** "slice-major, then row-major" */
    order: string
    shape: [number, number, number]
    nodata: string
  }
}

// ── POST /api/pose ─────────────────────────────────────────────────────────

export interface CorridorFix {
  lateral_offset_m: number
  along_track_m: number
  half_width_m: number
  [key: string]: unknown
}

export interface PoseResponse {
  corridor_id: string | null
  corridor_rover_id: string | null
  corridor_fix: CorridorFix
  pose_source: string
  fired_triggers: TriggerRef[]
  evaluated: string[]
  skipped: string[]
  trigger_state: Record<string, number>
  recommended_action: string
}

// ── POST /api/plan-multi, POST /api/compare ────────────────────────────────

export interface ProfileResult {
  profile_id: string
  profile_name: string | null
  color: string
  path_pixels: Array<[number, number]>
  metrics: Record<string, unknown>
  constraint_check?: Record<string, unknown>
  simulation_summary?: Record<string, unknown> | null
  error?: string
}

export interface CompareResponse {
  start: [number, number]
  goal: [number, number]
  results: ProfileResult[]
  comparison: Record<string, unknown>
}

export interface PlanMultiResponse {
  results: ProfileResult[]
}

// ── GET /api/reference-missions ────────────────────────────────────────────

export interface ReferenceMissions {
  note: string
  missions: Array<{
    mission: string
    total_distance_m: number
    as_of: string
    lower_bound_rate_m_per_calendar_day: number
    milestones: Array<Record<string, unknown>>
    [key: string]: unknown
  }>
}
```

- [ ] **Adım 3: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: üçü de hatasız. `AstarMetrics` değişikliği mevcut kodda hata
vermemeli — `App.tsx` bu iki alanı okumuyor.

- [ ] **Adım 4: Commit**

```bash
git add frontend/src/mission/types.ts frontend/src/api.ts
git commit -m "fix(frontend): type the always-null A* energy and shadow metrics honestly

pathfinder.py emits total_energy_wh and total_shadow_hours as None and
points at the simulation summary instead, but api.ts declared both as
number -- so any consumer that trusted the type would have rendered null
as a value. Also adds the response types for the nine endpoints the
cockpit does not read yet."
```

---

### Görev 3: `mission/geo.ts` — koordinat dönüşümü

Koridor CRS metresiyle konuşur, tuval pikselle. Bu dönüşüm **tek bir yerde**
yaşar; spec'in en yüksek riskli maddesi (yanlışsa F2a ve F7 birlikte yanlış olur).

Backend'in kanonik formülü (`serializer.py:152-157`):

```
x_m = origin.x + col * resolution_m
y_m = origin.y - row * resolution_m     # satırlar güneye artar
```

**Files:**
- Create: `frontend/src/mission/geo.ts`

**Interfaces:**
- Consumes: `mission/types.ts`'ten `TerrainManifest`
- Produces:
  - `type GridFrame = { originX: number; originY: number; resolutionM: number; rows: number; cols: number }`
  - `frameFromManifest(manifest: TerrainManifest): GridFrame | null`
  - `metresToPixel(x: number, y: number, frame: GridFrame): PixelPoint`
  - `pixelToMetres(row: number, col: number, frame: GridFrame): { x: number; y: number }`
  - `coarseToFine(row: number, col: number, coarsen: number): PixelPoint`

- [ ] **Adım 1: Dosyayı oluştur**

```ts
import type { TerrainManifest } from './types'

export interface PixelPoint {
  row: number
  col: number
}

/**
 * The grid geometry every pixel/metre conversion needs.
 *
 * Never hard-coded. The shipped grid is 500x500 at 5 m/px today and was
 * 500x500 at 80 m/px before; the backend reads this from
 * lunapath/data/processed/metadata.json at runtime and so does this.
 */
export interface GridFrame {
  originX: number
  originY: number
  resolutionM: number
  rows: number
  cols: number
}

/** null when the manifest carries no georeference (origin can be absent). */
export function frameFromManifest(manifest: TerrainManifest): GridFrame | null {
  const origin = manifest.georeference.origin
  if (!origin) return null
  return {
    originX: origin.x,
    originY: origin.y,
    resolutionM: manifest.grid.resolution_m,
    rows: manifest.grid.rows,
    cols: manifest.grid.cols,
  }
}

/**
 * Projected CRS metres -> fine grid pixel.
 *
 * The y term is SUBTRACTED: origin.y is the window's north edge and rows
 * increase southward. Getting this backwards mirrors the corridor about the
 * middle row, which looks plausible and is wrong. Mirrors
 * serializer.pixel_to_lonlat (serializer.py:152-157).
 */
export function metresToPixel(x: number, y: number, frame: GridFrame): PixelPoint {
  return {
    row: (frame.originY - y) / frame.resolutionM,
    col: (x - frame.originX) / frame.resolutionM,
  }
}

/** Fine grid pixel -> projected CRS metres. Inverse of metresToPixel. */
export function pixelToMetres(
  row: number,
  col: number,
  frame: GridFrame,
): { x: number; y: number } {
  return {
    x: frame.originX + col * frame.resolutionM,
    y: frame.originY - row * frame.resolutionM,
  }
}

/**
 * Coarse planning pixel -> fine pixel, at the block CENTRE.
 *
 * /api/plan-4d coarsens the grid by an integer factor and publishes block
 * centres as waypoints (main.py uses how="center" for the same reason), so
 * the centre is where the geometry a rover meets actually lives.
 */
export function coarseToFine(row: number, col: number, coarsen: number): PixelPoint {
  const half = (coarsen - 1) / 2
  return { row: row * coarsen + half, col: col * coarsen + half }
}
```

- [ ] **Adım 2: Formülü elle doğrula**

`lunapath/data/processed/metadata.json` şu değerleri taşıyor:
`origin = { x: -32500.0, y: 11000.0 }`, `resolution_m = 5.0`, `shape = [500, 500]`.

Bu değerlerle `metresToPixel` şunları vermeli:

| Girdi (metre) | Beklenen piksel |
|---|---|
| `x = -32500, y = 11000` | `{ row: 0, col: 0 }` (kuzey-batı köşesi) |
| `x = -32495, y = 10995` | `{ row: 1, col: 1 }` |
| `x = -30005, y = 8505` | `{ row: 499, col: 499 }` (güney-doğu köşesi) |

Bunu tarayıcı konsolunda doğrula — `npm run dev` çalışırken konsola:

```js
// beklenen: {row: 0, col: 0}
console.log({ row: (11000 - 11000) / 5, col: (-32500 - -32500) / 5 })
// beklenen: {row: 499, col: 499}
console.log({ row: (11000 - 8505) / 5, col: (-30005 - -32500) / 5 })
```

Expected: ikisi de tabloyla birebir. **`row` çıkışı negatifse y terimi ters
çevrilmiştir** — durup düzelt.

- [ ] **Adım 3: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: temiz

- [ ] **Adım 4: Commit**

```bash
git add frontend/src/mission/geo.ts
git commit -m "feat(frontend): one canonical grid metre/pixel conversion

The corridor speaks projected CRS metres and the canvas speaks pixels.
Mirrors serializer.pixel_to_lonlat, subtracted y term included: origin.y
is the window's north edge and rows increase southward, so getting the
sign wrong mirrors the corridor about the middle row -- plausible-looking
and wrong. Verified against metadata.json's corners."
```

---

### Görev 4: `overlay/` — tuval çizim sözleşmesi

Modüller `MapCanvas`'a doğrudan çizmez; overlay kaydeder. Bu, "önce 2B, sonra
3B" kararının (K4) teknik karşılığı — 3B'ye geçiş `draw3d.ts` yazmaktan ibaret
olacak, faz modülleri değişmeyecek.

**Files:**
- Create: `frontend/src/overlay/types.ts`
- Create: `frontend/src/overlay/useOverlays.ts`
- Create: `frontend/src/overlay/draw2d.ts`
- Modify: `frontend/src/MapCanvas.tsx` (Props, `redraw` çağrısı, `redraw` gövdesi)

**Interfaces:**
- Consumes: `mission/geo.ts`'ten `PixelPoint`
- Produces:
  - `OverlayLayer`, `OverlayStyle`, `RampName`
  - `OverlayProvider` bileşeni
  - `useOverlays(): { register(id, layers): void; unregister(id): void; layers: OverlayLayer[] }`
  - `drawOverlays(ctx, layers, gridRows, canvasSize): void`

- [ ] **Adım 1: `overlay/types.ts` oluştur**

```ts
import type { PixelPoint } from '../mission/geo'

export type { PixelPoint }

export type RampName = 'viridis' | 'magma' | 'thermal' | 'grayReverse'

export interface OverlayStyle {
  color: string
  /** Canvas line width in device pixels. Default 2. */
  lineWidth?: number
  /** 0-1. Default 1. */
  opacity?: number
  /** Marker radius for `points`, in device pixels. Default 4. */
  radius?: number
  /** Dash pattern, e.g. [6, 4]. Omit for a solid line. */
  dash?: number[]
}

/**
 * One thing a feature module wants drawn on the map.
 *
 * Every coordinate is a FINE grid pixel ({row, col}). A module holding CRS
 * metres or coarse pixels converts with mission/geo.ts before registering.
 * The canvas knows no other unit, and 3-D will consume this same list.
 */
export type OverlayLayer =
  | { kind: 'polyline'; id: string; points: PixelPoint[]; style: OverlayStyle }
  | {
      kind: 'ribbon'
      id: string
      center: PixelPoint[]
      /** One half-width per centre point, already in FINE PIXELS. */
      halfWidthPx: number[]
      style: OverlayStyle
    }
  | { kind: 'points'; id: string; points: PixelPoint[]; style: OverlayStyle }
  | {
      kind: 'field'
      id: string
      data: Float32Array
      rows: number
      cols: number
      /** [min, max] the ramp maps across. NaN cells are left transparent. */
      domain: [number, number]
      ramp: RampName
      opacity: number
    }
```

- [ ] **Adım 2: `overlay/useOverlays.ts` oluştur**

```tsx
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { OverlayLayer } from './types'

interface OverlayRegistry {
  layers: OverlayLayer[]
  register: (id: string, layers: OverlayLayer[]) => void
  unregister: (id: string) => void
}

const OverlayContext = createContext<OverlayRegistry | null>(null)

export function OverlayProvider({ children }: { children: React.ReactNode }) {
  const [groups, setGroups] = useState<Record<string, OverlayLayer[]>>({})

  const register = useCallback((id: string, layers: OverlayLayer[]) => {
    setGroups((current) => ({ ...current, [id]: layers }))
  }, [])

  const unregister = useCallback((id: string) => {
    setGroups((current) => {
      if (!(id in current)) return current
      const next = { ...current }
      delete next[id]
      return next
    })
  }, [])

  // Sorted by group id so draw order is stable across re-renders -- object
  // key order would otherwise let a re-registering module jump on top of
  // another module's marks.
  const layers = useMemo(
    () =>
      Object.keys(groups)
        .sort()
        .flatMap((id) => groups[id]),
    [groups],
  )

  const value = useMemo(
    () => ({ layers, register, unregister }),
    [layers, register, unregister],
  )

  return <OverlayContext.Provider value={value}>{children}</OverlayContext.Provider>
}

/**
 * Outside an OverlayProvider this returns a no-op registry rather than
 * throwing: a feature module must stay renderable in isolation.
 */
export function useOverlays(): OverlayRegistry {
  const ctx = useContext(OverlayContext)
  return ctx ?? EMPTY
}

const EMPTY: OverlayRegistry = {
  layers: [],
  register: () => undefined,
  unregister: () => undefined,
}
```

- [ ] **Adım 3: `overlay/draw2d.ts` oluştur**

```ts
import { magmaToRgb, thermalToRgb, viridisToRgb, grayReverseToRgb } from '../colormap'
import type { OverlayLayer, PixelPoint, RampName } from './types'

const RAMPS: Record<RampName, (t: number) => [number, number, number]> = {
  viridis: viridisToRgb,
  magma: magmaToRgb,
  thermal: thermalToRgb,
  grayReverse: grayReverseToRgb,
}

/**
 * Draw every registered overlay onto the map canvas.
 *
 * `scale` converts a grid pixel into a canvas pixel. The canvas is a fixed
 * square (CANVAS_SIZE) whatever the grid's size, so a 250-row preview and a
 * 500-row full grid both fill it -- taking the scale from the grid rather
 * than assuming 1:1 keeps a downsampled field aligned with the route.
 */
export function drawOverlays(
  ctx: CanvasRenderingContext2D,
  layers: OverlayLayer[],
  gridRows: number,
  canvasSize: number,
): void {
  if (!layers.length || gridRows <= 0) return
  const scale = canvasSize / gridRows

  for (const layer of layers) {
    ctx.save()
    switch (layer.kind) {
      case 'field':
        drawField(ctx, layer, canvasSize)
        break
      case 'ribbon':
        drawRibbon(ctx, layer, scale)
        break
      case 'polyline':
        drawPolyline(ctx, layer, scale)
        break
      case 'points':
        drawPoints(ctx, layer, scale)
        break
    }
    ctx.restore()
  }
}

function applyStroke(
  ctx: CanvasRenderingContext2D,
  style: { color: string; lineWidth?: number; opacity?: number; dash?: number[] },
): void {
  ctx.globalAlpha = style.opacity ?? 1
  ctx.strokeStyle = style.color
  ctx.lineWidth = style.lineWidth ?? 2
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.setLineDash(style.dash ?? [])
}

function drawPolyline(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'polyline' }>,
  scale: number,
): void {
  if (layer.points.length < 2) return
  applyStroke(ctx, layer.style)
  ctx.beginPath()
  layer.points.forEach((point, index) => {
    const x = (point.col + 0.5) * scale
    const y = (point.row + 0.5) * scale
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  ctx.stroke()
}

function drawPoints(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'points' }>,
  scale: number,
): void {
  ctx.globalAlpha = layer.style.opacity ?? 1
  ctx.fillStyle = layer.style.color
  const radius = layer.style.radius ?? 4
  for (const point of layer.points) {
    ctx.beginPath()
    ctx.arc((point.col + 0.5) * scale, (point.row + 0.5) * scale, radius, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * A corridor is one filled band, not a stack of per-segment quads: drawn
 * segment by segment the shared edges overlap and a translucent fill goes
 * visibly darker at every joint. Walking the left side forward and the
 * right side back closes a single polygon instead.
 */
function drawRibbon(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'ribbon' }>,
  scale: number,
): void {
  const { center, halfWidthPx } = layer
  if (center.length < 2) return

  const left: PixelPoint[] = []
  const right: PixelPoint[] = []

  for (let i = 0; i < center.length; i++) {
    const prev = center[Math.max(0, i - 1)]
    const next = center[Math.min(center.length - 1, i + 1)]
    const dRow = next.row - prev.row
    const dCol = next.col - prev.col
    const length = Math.hypot(dRow, dCol)
    if (length === 0) {
      left.push(center[i])
      right.push(center[i])
      continue
    }
    // Perpendicular in grid space: (dRow, dCol) -> (-dCol, dRow).
    const nRow = -dCol / length
    const nCol = dRow / length
    const w = halfWidthPx[Math.min(i, halfWidthPx.length - 1)] ?? 0
    left.push({ row: center[i].row + nRow * w, col: center[i].col + nCol * w })
    right.push({ row: center[i].row - nRow * w, col: center[i].col - nCol * w })
  }

  ctx.globalAlpha = layer.style.opacity ?? 0.25
  ctx.fillStyle = layer.style.color
  ctx.beginPath()
  left.forEach((point, index) => {
    const x = (point.col + 0.5) * scale
    const y = (point.row + 0.5) * scale
    if (index === 0) ctx.moveTo(x, y)
    else ctx.lineTo(x, y)
  })
  for (let i = right.length - 1; i >= 0; i--) {
    ctx.lineTo((right[i].col + 0.5) * scale, (right[i].row + 0.5) * scale)
  }
  ctx.closePath()
  ctx.fill()
}

/**
 * A scalar field painted over the base map.
 *
 * Built as ImageData at the field's own resolution and blitted through an
 * offscreen canvas, so a 250x250 time slice scales up to the 500 px canvas
 * without the caller resampling anything. NaN is the backend's only
 * no-data value and stays fully transparent.
 */
function drawField(
  ctx: CanvasRenderingContext2D,
  layer: Extract<OverlayLayer, { kind: 'field' }>,
  canvasSize: number,
): void {
  const { data, rows, cols, domain, ramp, opacity } = layer
  if (data.length !== rows * cols) return

  const [min, max] = domain
  const span = max - min
  const toRgb = RAMPS[ramp]
  const image = new ImageData(cols, rows)

  for (let i = 0; i < data.length; i++) {
    const value = data[i]
    const offset = i * 4
    if (Number.isNaN(value)) {
      image.data[offset + 3] = 0
      continue
    }
    const t = span === 0 ? 0 : Math.min(1, Math.max(0, (value - min) / span))
    const [r, g, b] = toRgb(t)
    image.data[offset] = r
    image.data[offset + 1] = g
    image.data[offset + 2] = b
    image.data[offset + 3] = 255
  }

  const scratch = document.createElement('canvas')
  scratch.width = cols
  scratch.height = rows
  const scratchCtx = scratch.getContext('2d')
  if (!scratchCtx) return
  scratchCtx.putImageData(image, 0, 0)

  ctx.globalAlpha = opacity
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(scratch, 0, 0, canvasSize, canvasSize)
}
```

- [ ] **Adım 4: `colormap.ts`'in gerçekten bu dört fonksiyonu dışa açtığını doğrula**

Run: `cd frontend && grep -n "^export function \(viridisToRgb\|magmaToRgb\|thermalToRgb\|grayReverseToRgb\)" src/colormap.ts`
Expected: dört satır da çıkar. Bir tanesi çıkmazsa `draw2d.ts`'teki `RAMPS`
tablosundan o girdiyi ve `RampName`'den o adı çıkar — uydurma isim eklenmez.

Ayrıca dönüş tipini doğrula:

Run: `cd frontend && sed -n "/^export function viridisToRgb/,/^}/p" src/colormap.ts`
Expected: `[number, number, number]` döndüğü görülür. Farklıysa `RAMPS`
tablosunun tipini gerçek imzaya uydur.

- [ ] **Adım 5: `MapCanvas.tsx`'e overlay prop'unu ekle**

`interface Props` içine, `onHoverCellChange` satırının altına ekle:

```ts
  /** Feature-module marks, drawn above the base map. See overlay/types.ts. */
  overlays?: OverlayLayer[]
```

Dosyanın başındaki importlara ekle:

```ts
import type { OverlayLayer } from './overlay/types'
import { drawOverlays } from './overlay/draw2d'
```

Bileşenin destructure listesine `onHoverCellChange`'den sonra `overlays,` ekle.

- [ ] **Adım 6: `redraw`'a overlay'leri geçir**

`MapCanvas.tsx:132` civarındaki çağrıyı bul:

```ts
    redraw(ctx, baseImageRef.current, waypoints, start, goal, animStep, hoverCell)
  }, [animStep, goal, hoverCell, start, waypoints])
```

Şununla değiştir:

```ts
    redraw(ctx, baseImageRef.current, waypoints, start, goal, animStep, hoverCell, overlays)
  }, [animStep, goal, hoverCell, overlays, start, waypoints])
```

- [ ] **Adım 7: `redraw` gövdesini genişlet**

`MapCanvas.tsx:282` civarındaki imzaya son parametreyi ekle:

```ts
function redraw(
  ctx: CanvasRenderingContext2D,
  baseImage: ImageData | null,
  waypoints: Waypoint[] | null,
  start: [number, number] | null,
  goal: [number, number] | null,
  currentStep: number | null,
  hoverCell: [number, number] | null,
  overlays?: OverlayLayer[],
) {
```

Taban görüntü basıldıktan **hemen sonra**, rota çizilmeden **önce** — yani
`ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE)`'ı kapatan `}` ile
`if (waypoints && waypoints.length > 1) {` arasına şunu ekle:

```ts
  // Before the route and the markers: a field overlay is a backdrop, and the
  // planned route must stay readable on top of it.
  if (overlays && overlays.length) {
    drawOverlays(ctx, overlays, CANVAS_SIZE, CANVAS_SIZE)
  }
```

> `gridRows` olarak `CANVAS_SIZE` geçiliyor çünkü `MapCanvas` taban görüntüyü
> zaten tuval çözünürlüğüne ölçekliyor (`cellPx = CANVAS_SIZE / rows`,
> `MapCanvas.tsx:454`) — yani tuval uzayında bir grid pikseli tam olarak bir
> tuval pikselidir. `field` overlay'i kendi `rows`/`cols`'unu taşır ve
> `drawImage` ile ölçeklenir, bu yüzden farklı çözünürlükte bir dilim de doğru
> oturur.

- [ ] **Adım 8: Regresyon olmadığını doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: üçü de temiz.

Elle: uygulamayı aç, bir başlangıç ve hedef seç, rota üret.
Expected: harita, rota, işaretler ve hover **Görev 4 öncesiyle birebir aynı**
görünüyor — hiçbir modül henüz overlay kaydetmediği için `overlays` `undefined`
ve çizim yolu hiç çalışmıyor.

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/overlay/ frontend/src/MapCanvas.tsx
git commit -m "feat(frontend): let feature modules draw on the map without touching it

Modules register OverlayLayers instead of reaching into MapCanvas, so nine
upcoming panels share one drawing path and none of them edits the canvas.
Every overlay coordinate is a fine grid pixel, which is also what a 3-D
renderer will want -- moving to three.js becomes writing draw3d.ts, not
rewriting the modules. Ribbons close a single polygon rather than stacking
per-segment quads, which would darken every joint."
```

---

### Görev 5: `mission/` — context, yuvalar ve `App.tsx` bağlantısı

Bu, `App.tsx`'e dokunan **tek içerik değişikliği** (ham telemetri) ve tek
yapısal değişiklik (sarmalayıcılar + dört yuva). Görev 6'dan sonra `App.tsx`'e
faz başına yalnızca bir satır eklenecek.

**Files:**
- Create: `frontend/src/mission/MissionContext.tsx`
- Create: `frontend/src/mission/slots.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `mission/types.ts`, `overlay/useOverlays.ts`
- Produces:
  - `MissionProvider` bileşeni (`value: MissionState & MissionActions`)
  - `useMission(): MissionState & MissionActions`
  - `LeftRailSlot`, `RightRailSlot`, `BottomDock`, `CanvasOverlaySlot` bileşenleri

- [ ] **Adım 1: `mission/MissionContext.tsx` oluştur**

```tsx
import React, { createContext, useContext } from 'react'
import type { PlanResponse, PlanWeights } from '../api'
import type { CellTelemetryResponse } from './types'

export type MapViewMode =
  | 'surface'
  | 'thermal'
  | 'cost'
  | 'shadow'
  | 'traversability'
  | 'slope'
  | 'aspect'

/**
 * What App.tsx ALREADY owns, published read-only.
 *
 * Nothing new lives here. A feature module keeps its own state in its own
 * hook; this exists so nine modules can read the cockpit's current
 * selection without App.tsx growing nine more useStates.
 */
export interface MissionState {
  gridMeta: { rows: number; cols: number; resolutionM: number } | null
  roverId: string
  weights: PlanWeights
  start: [number, number] | null
  goal: [number, number] | null
  /** The FULL /api/plan response -- corridor, route_statistics and execution included. */
  planResult: PlanResponse | null
  selectedCell: [number, number] | null
  /** The RAW /api/cell-telemetry response, cost_breakdown and layer_validity included. */
  cellTelemetry: CellTelemetryResponse | null
  activeLayer: MapViewMode
  dimension: '2d' | '3d'
}

export interface MissionActions {
  setStart: (cell: [number, number] | null) => void
  setGoal: (cell: [number, number] | null) => void
}

export type MissionValue = MissionState & MissionActions

const MissionContext = createContext<MissionValue | null>(null)

export function MissionProvider({
  value,
  children,
}: {
  value: MissionValue
  children: React.ReactNode
}) {
  return <MissionContext.Provider value={value}>{children}</MissionContext.Provider>
}

export function useMission(): MissionValue {
  const ctx = useContext(MissionContext)
  if (!ctx) {
    throw new Error('useMission must be used inside <MissionProvider>')
  }
  return ctx
}
```

- [ ] **Adım 2: `mission/slots.tsx` oluştur**

```tsx
import React from 'react'

/**
 * Mount points for feature modules.
 *
 * They are deliberately plain wrappers: adding a phase to the cockpit is
 * putting its <Module /> inside one of these, which is a one-line diff in
 * App.tsx and therefore a one-line merge conflict at worst.
 */

export function LeftRailSlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-left">{children}</div>
}

export function RightRailSlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-right">{children}</div>
}

export function BottomDock({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return <div className="lp-slot lp-slot-dock">{children}</div>
}

export function CanvasOverlaySlot({ children }: { children?: React.ReactNode }) {
  if (!children) return null
  return (
    <div
      className="lp-slot lp-slot-canvas"
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
    >
      {children}
    </div>
  )
}
```

- [ ] **Adım 3: `App.tsx` — ham telemetriyi sakla**

`App.tsx:145` civarındaki `focusTelemetry` state'inin **yanına** ekle
(mevcut satır silinmez):

```ts
  const [rawCellTelemetry, setRawCellTelemetry] = useState<CellTelemetryResponse | null>(null)
```

Importlara ekle:

```ts
import type { CellTelemetryResponse } from './mission/types'
```

`fetchCellTelemetry` yanıtının işlendiği yerde (`mapFocusTelemetryResponse`
çağrısının hemen yanında) ham yanıtı da sakla:

```ts
        setRawCellTelemetry(response)
```

> `mapFocusTelemetryResponse` çağrısı **silinmez** — mevcut telemetri kuyusu
> aynen çalışmaya devam eder. Bu satır sadece yanıtın atılan kısmını da tutar.

- [ ] **Adım 4: `App.tsx` — sağlayıcıları ve yuvaları yerleştir**

Importlara ekle:

```ts
import { MissionProvider } from './mission/MissionContext'
import type { MissionValue } from './mission/MissionContext'
import { OverlayProvider, useOverlays } from './overlay/useOverlays'
import { LeftRailSlot, RightRailSlot, BottomDock, CanvasOverlaySlot } from './mission/slots'
```

`return (` satırından hemen önce context değerini kur:

```ts
  const missionValue: MissionValue = {
    gridMeta: elevationLayer
      ? {
          rows: elevationLayer.shape[0],
          cols: elevationLayer.shape[1],
          resolutionM: focusTelemetry.resolutionM,
        }
      : null,
    roverId: selectedRoverId,
    weights,
    start,
    goal,
    planResult,
    selectedCell: hoverPoint,
    cellTelemetry: rawCellTelemetry,
    activeLayer: viewMode,
    dimension,
    setStart,
    setGoal,
  }
```

> `selectedRoverId` ve `focusTelemetry.resolutionM` adları `App.tsx`'te zaten
> var; farklı adlandırılmışlarsa gerçek adı kullan, yeni state ekleme.

`return (` içindeki en dış `<>` fragment'ının **hemen içine** sarmalayıcıları
al — yani mevcut ağacın tamamı bunların içinde kalacak:

```tsx
  return (
    <MissionProvider value={missionValue}>
      <OverlayProvider>
        {/* ... mevcut ağacın tamamı, olduğu gibi ... */}
      </OverlayProvider>
    </MissionProvider>
  )
```

- [ ] **Adım 5: `App.tsx` — dört yuvayı yerleştir**

- `<LeftRailSlot />` — `rail-scroll` içindeki son `</section>`'dan sonra
- `<RightRailSlot />` — sağ raydaki Route Analytics bölümünden sonra
- `<BottomDock />` — `<MapCanvas ... />`'ı saran kabın hemen altında
- `<CanvasOverlaySlot />` — `<MapCanvas ... />` ile aynı `position: relative`
  kabın içinde, canvas'tan sonra

Dördü de şimdilik boş (`children` yok) — `slots.tsx` `children` yoksa `null`
döndüğü için DOM'a hiçbir şey eklenmez.

- [ ] **Adım 6: `App.tsx` — overlay'leri tuvale bağla**

`MapCanvas`'ı render eden JSX'in bulunduğu bileşen `OverlayProvider`'ın
**içinde** olmalı ki `useOverlays()` çalışsın. `App` bileşeni sağlayıcıyı kendi
render'ında kurduğu için `useOverlays()`'i doğrudan `App` içinde çağıramazsın.
Bu yüzden tuvali saran küçük bir iç bileşen ekle — `App.tsx`'in **sonuna**:

```tsx
/**
 * Reads the overlay registry and hands it to the canvas.
 *
 * A separate component because App renders OverlayProvider itself, so App's
 * own body is outside that provider and useOverlays() there would always
 * see the empty registry.
 */
function MapCanvasWithOverlays(
  props: React.ComponentProps<typeof MapCanvas> & { canvasRef: React.Ref<MapCanvasHandle> },
) {
  const { canvasRef, ...rest } = props
  const { layers } = useOverlays()
  return <MapCanvas ref={canvasRef} {...rest} overlays={layers} />
}
```

Mevcut `<MapCanvas ref={mapRef} ... />` kullanımını `<MapCanvasWithOverlays
canvasRef={mapRef} ... />` ile değiştir; diğer prop'lar aynen kalır.

- [ ] **Adım 7: Regresyon olmadığını doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: üçü de temiz.

Elle kabul — sırayla:
1. Uygulamayı aç, giriş ekranından Mission Workspace'e geç → **açılıyor**
2. Katman değiştir (Surface → Thermal → Cost) → **harita değişiyor**
3. Haritada gezin → **telemetri kuyusu güncelleniyor**
4. Başlangıç ve hedef seç, rota üret → **rota çiziliyor, analitik dolduruyor**
5. Rota animasyonunu oynat → **çalışıyor**
6. Tarayıcı konsolu → **hata yok**

Expected: altısı da Görev 5 öncesiyle **birebir aynı**. Tek fark: DOM'da dört
boş yuva sarmalayıcısı var ama hiçbiri render etmiyor.

- [ ] **Adım 8: Commit**

```bash
git add frontend/src/mission/ frontend/src/App.tsx
git commit -m "feat(frontend): publish the cockpit's state and open four mount points

Nine phase modules are coming and App.tsx is 1236 lines that three people
edit. Rather than move state out -- which would break every open branch --
this publishes what App already owns read-only and opens four slots, so
each phase is a one-line diff here and keeps its own state in its own hook.
The one content change: /api/cell-telemetry's response is kept whole
instead of trimmed to four fields, because cost_breakdown and
layer_validity were being fetched and thrown away."
```

---

### Görev 6: F1 — `layer-provenance` · Katman kökeni

Kokpit yedi katmanı boyuyor ama hiçbirinin **nereden geldiğini** söylemiyor.
Aynı gri tonlarla çizilen `elevation` ölçülmüş bir DEM, `shadow_ratio` ise
türetilmiş (ham DEM yolunda tamamen sentetik) — kullanıcı ikisini ayırt edemiyor.

`/api/terrain` bunun tamamını **tek çağrıda** veriyor: katman başına `units`,
`description`, `validity`, `min`, `max`, `nodata` (`terrain.py:258-271`).
Mevcut katman fetch'lerine hiç dokunulmuyor.

**Files:**
- Create: `frontend/src/api/terrain.ts`
- Create: `frontend/src/features/layer-provenance/index.tsx`
- Create: `frontend/src/features/layer-provenance/useLayerProvenance.ts`
- Create: `frontend/src/features/layer-provenance/LayerProvenancePanel.tsx`
- Create: `frontend/src/features/layer-provenance/layer-provenance.css`
- Modify: `frontend/src/App.tsx` (bir satır: `<LeftRailSlot>` içine modül)

**Interfaces:**
- Consumes: `api/client.ts`'ten `getJson`; `mission/types.ts`'ten `TerrainManifest`, `Validity`, `VALIDITY_RANK`; `mission/MissionContext`'ten `useMission`
- Produces:
  - `fetchTerrain(params, signal): Promise<TerrainManifest>`
  - `useLayerProvenance(): { manifest, loading, error }`
  - `LAYER_FOR_VIEW: Record<MapViewMode, string>` — görünüm adı → katman adı eşlemesi

- [ ] **Adım 1: `api/terrain.ts` oluştur**

```ts
import { getJson } from './client'
import type { PlanWeights } from '../api'
import type { TerrainManifest } from '../mission/types'

/**
 * The scene manifest: units, provenance and value range for every layer,
 * plus the georeference, in one call.
 *
 * cost and traversable depend on the rover and the weights, so those travel
 * as query parameters and the manifest bakes them into each binary_url.
 */
export async function fetchTerrain(
  params: { roverId?: string; weights?: PlanWeights } = {},
  signal?: AbortSignal,
): Promise<TerrainManifest> {
  const query = new URLSearchParams()
  if (params.roverId) query.set('rover_id', params.roverId)
  if (params.weights) {
    query.set('w_slope', String(params.weights.w_slope))
    query.set('w_energy', String(params.weights.w_energy))
    query.set('w_shadow', String(params.weights.w_shadow))
    query.set('w_thermal', String(params.weights.w_thermal))
  }
  const suffix = query.toString()
  return getJson<TerrainManifest>(`/terrain${suffix ? `?${suffix}` : ''}`, signal)
}
```

- [ ] **Adım 2: `useLayerProvenance.ts` oluştur**

```ts
import { useEffect, useState } from 'react'
import { fetchTerrain } from '../../api/terrain'
import { useMission } from '../../mission/MissionContext'
import type { MapViewMode } from '../../mission/MissionContext'
import type { TerrainManifest } from '../../mission/types'

/**
 * The map's view modes and the grid layers behind them.
 *
 * 'surface' paints elevation; 'traversability' reads the traversable mask.
 * Kept here rather than guessed in the panel so a renamed view mode fails
 * to compile instead of silently showing the wrong provenance.
 */
export const LAYER_FOR_VIEW: Record<MapViewMode, string> = {
  surface: 'elevation',
  thermal: 'thermal',
  cost: 'cost',
  shadow: 'shadow_ratio',
  traversability: 'traversable',
  slope: 'slope',
  aspect: 'aspect',
}

export function useLayerProvenance() {
  const { roverId, weights } = useMission()
  const [manifest, setManifest] = useState<TerrainManifest | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)

    fetchTerrain({ roverId, weights }, controller.signal)
      .then((next) => {
        setManifest(next)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Terrain manifest unavailable')
        setLoading(false)
      })

    return () => controller.abort()
    // cost and traversable are weight-dependent, so their range and
    // provenance change when the weights do.
  }, [roverId, weights])

  return { manifest, loading, error }
}
```

- [ ] **Adım 3: `LayerProvenancePanel.tsx` oluştur**

```tsx
import type { LayerManifestEntry, Validity } from '../../mission/types'
import './layer-provenance.css'

const LABEL: Record<Validity, string> = {
  MEASURED: 'Measured',
  MODEL: 'Modelled',
  DERIVED: 'Derived',
  SYNTHETIC: 'Synthetic',
}

const EXPLANATION: Record<Validity, string> = {
  MEASURED: 'Instrument data. This layer is observation, not inference.',
  MODEL: 'Produced by a physical model fitted to this site.',
  DERIVED: 'Computed from a measured layer. Inherits its errors.',
  SYNTHETIC: 'Stand-in values. Not tied to this site’s real conditions.',
}

function formatRange(entry: LayerManifestEntry): string {
  // min and max are null when the layer holds no finite value
  // (terrain.py:262-266). An empty range is reported as unknown, never 0.
  if (entry.min === null || entry.max === null) return 'unknown'
  const units = entry.units ? ` ${entry.units}` : ''
  return `${entry.min.toFixed(2)} – ${entry.max.toFixed(2)}${units}`
}

export function LayerProvenancePanel({
  layerName,
  entry,
  loading,
  error,
}: {
  layerName: string
  entry: LayerManifestEntry | null
  loading: boolean
  error: string | null
}) {
  if (loading) {
    return <p className="lp-provenance-note">Reading layer provenance…</p>
  }
  if (error) {
    return <p className="lp-provenance-note lp-provenance-warn">{error}</p>
  }
  if (!entry) {
    return (
      <p className="lp-provenance-note">
        No manifest entry for <code>{layerName}</code>.
      </p>
    )
  }

  // validity is null when the grid metadata carried no label. Saying
  // "unknown" is the honest answer; assuming MEASURED would be a claim.
  const validity = entry.validity
  const tone = validity ? validity.toLowerCase() : 'unknown'

  return (
    <div className="lp-provenance-card">
      <div className="lp-provenance-head">
        <code className="lp-provenance-name">{layerName}</code>
        <span className={`lp-provenance-badge lp-provenance-${tone}`}>
          {validity ? LABEL[validity] : 'Unknown'}
        </span>
      </div>

      <p className="lp-provenance-why">
        {validity ? EXPLANATION[validity] : 'This layer carries no provenance label.'}
      </p>

      {entry.description ? (
        <p className="lp-provenance-desc">{entry.description}</p>
      ) : null}

      <dl className="lp-provenance-facts">
        <div>
          <dt>Range</dt>
          <dd>{formatRange(entry)}</dd>
        </div>
        <div>
          <dt>No-data cells</dt>
          <dd>{entry.nodata.toLocaleString()}</dd>
        </div>
      </dl>
    </div>
  )
}
```

- [ ] **Adım 4: `layer-provenance.css` oluştur**

Tüm sınıflar `.lp-provenance-` ön ekli. `App.css`'e dokunulmuyor.

```css
.lp-provenance-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.45);
}

.lp-provenance-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.lp-provenance-name {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: #cbd5f5;
}

.lp-provenance-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid currentColor;
}

/* Ranked weakest to strongest, and coloured that way on purpose: a
   synthetic layer should be the one that catches the eye. */
.lp-provenance-synthetic { color: #fbbf24; }
.lp-provenance-derived   { color: #60a5fa; }
.lp-provenance-model     { color: #a78bfa; }
.lp-provenance-measured  { color: #34d399; }
.lp-provenance-unknown   { color: #94a3b8; }

.lp-provenance-why,
.lp-provenance-desc {
  margin: 0 0 8px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}

.lp-provenance-facts {
  display: flex;
  gap: 18px;
  margin: 0;
}

.lp-provenance-facts div { display: flex; flex-direction: column; gap: 2px; }

.lp-provenance-facts dt {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #64748b;
}

.lp-provenance-facts dd {
  margin: 0;
  font-size: 12px;
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.lp-provenance-note { margin: 0; font-size: 11px; color: #94a3b8; }
.lp-provenance-warn { color: #fbbf24; }
```

- [ ] **Adım 5: `index.tsx` oluştur**

```tsx
import { useMission } from '../../mission/MissionContext'
import { LayerProvenancePanel } from './LayerProvenancePanel'
import { LAYER_FOR_VIEW, useLayerProvenance } from './useLayerProvenance'

export function LayerProvenance() {
  const { activeLayer } = useMission()
  const { manifest, loading, error } = useLayerProvenance()

  const layerName = LAYER_FOR_VIEW[activeLayer]
  const entry = manifest?.layers[layerName] ?? null

  return (
    <section className="rail-section">
      <p className="panel-kicker">Layer Provenance</p>
      <LayerProvenancePanel
        layerName={layerName}
        entry={entry}
        loading={loading}
        error={error}
      />
    </section>
  )
}
```

- [ ] **Adım 6: `App.tsx`'e tek satırla bağla**

`LeftRailSlot`'u doldur:

```tsx
<LeftRailSlot>
  <LayerProvenance />
</LeftRailSlot>
```

Import: `import { LayerProvenance } from './features/layer-provenance'`

> `features/layer-provenance/index.tsx` dışında bu modülden hiçbir şey import
> edilmez.

- [ ] **Adım 7: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: üçü de temiz

- [ ] **Adım 8: Elle kabul**

Backend'i `/api/load-preprocessed` ile yükledikten sonra, sol rayda paneli aç ve
katmanları sırayla değiştir. Beklenen etiketler (`metadata.json`'ın
`layer_validity` alanı):

| Görünüm | Katman | Beklenen rozet |
|---|---|---|
| Surface | `elevation` | **Measured** (yeşil) |
| Slope | `slope` | **Derived** (mavi) |
| Aspect | `aspect` | **Derived** (mavi) |
| Shadow | `shadow_ratio` | **Derived** (mavi) |
| Thermal | `thermal` | **Derived** (mavi) |
| Cost | `cost` | girdilerinin en zayıfı |
| Traversability | `traversable` | girdilerinin en zayıfı |

Ayrıca doğrula:
- Her katmanda **Range** alanı gerçek bir aralık gösteriyor, `0.00 – 0.00` değil
- **No-data cells** sayısı görünüyor
- Ağırlık kaydıraçlarını oynat → `cost` katmanının aralığı **değişiyor**
  (ağırlığa bağlı) ama `elevation`'ınki değişmiyor

Backend kapalıyken sayfayı yenile → panel **sarı bir uyarı** gösteriyor,
"Measured" varsaymıyor ve çökmüyor.

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/api/terrain.ts frontend/src/features/layer-provenance/ frontend/src/App.tsx
git commit -m "feat(frontend): say where each layer's numbers come from

Seven layers were painted in the same palette with nothing to separate a
measured DEM from a derived shadow ratio, and on the raw-DEM load path
that shadow ratio is outright synthetic. /api/terrain already published
units, provenance, range and no-data count per layer in one call; this
reads it. A missing label reads 'Unknown' rather than defaulting to
Measured, and an empty value range reads 'unknown' rather than 0.00-0.00."
```

---

### Görev 7: F1–2 — `cost-explain` · Neden pahalı?

`CostMap.explain()` her hücre için dört bileşenin **ağırlıklı** katkısını
döndürüyor ve `/api/cell-telemetry` bunu zaten yayınlıyor — frontend yanıtı alıp
bu alanı atıyordu. Görev 5 ham yanıtı context'e koydu; bu görev onu okur.
**Yeni ağ isteği yok.**

Kritik davranış (spec T3): `null` bir katkı **sonsuz** demek, yani hücre
GEÇİLEMEZ. `costmap.py:143-158` sonsuzu JSON'a `null` olarak yazıyor çünkü
Starlette `allow_nan=False` ile serileştiriyor. "Veri yok" **değil**.

**Files:**
- Create: `frontend/src/features/cost-explain/index.tsx`
- Create: `frontend/src/features/cost-explain/useCostExplain.ts`
- Create: `frontend/src/features/cost-explain/CostExplainPanel.tsx`
- Create: `frontend/src/features/cost-explain/overlays.ts`
- Create: `frontend/src/features/cost-explain/cost-explain.css`
- Modify: `frontend/src/App.tsx` (bir satır: `<RightRailSlot>`)

**Interfaces:**
- Consumes: `useMission()` (`cellTelemetry`, `selectedCell`, `weights`), `useOverlays()`
- Produces:
  - `useCostExplain(): { rows: CostRow[]; total: number | null; impassableBy: string[]; cell: [number, number] | null }`
  - `type CostRow = { key: 'slope' | 'energy' | 'shadow' | 'thermal'; label: string; value: number | null; share: number; weight: number }`

- [ ] **Adım 1: `useCostExplain.ts` oluştur**

```ts
import { useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'

export type CostKey = 'slope' | 'energy' | 'shadow' | 'thermal'

export interface CostRow {
  key: CostKey
  label: string
  /** null means an INFINITE contribution: this component closes the cell. */
  value: number | null
  /** Fraction of the finite total, 0-1. Zero when the cell is impassable. */
  share: number
  weight: number
}

const LABELS: Record<CostKey, string> = {
  slope: 'Slope',
  energy: 'Energy',
  // The cost component is named `shadow`; the grid layer behind it is named
  // `shadow_ratio`. Two namespaces, not one (spec T2).
  shadow: 'Shadow',
  thermal: 'Thermal',
}

const WEIGHT_KEY: Record<CostKey, 'w_slope' | 'w_energy' | 'w_shadow' | 'w_thermal'> = {
  slope: 'w_slope',
  energy: 'w_energy',
  shadow: 'w_shadow',
  thermal: 'w_thermal',
}

const KEYS: CostKey[] = ['slope', 'energy', 'shadow', 'thermal']

export function useCostExplain() {
  const { cellTelemetry, selectedCell, weights } = useMission()

  return useMemo(() => {
    const breakdown = cellTelemetry?.cost_breakdown ?? null
    if (!breakdown) {
      return { rows: [], total: null, impassableBy: [], cell: selectedCell }
    }

    const impassableBy = KEYS.filter((key) => breakdown[key] === null).map(
      (key) => LABELS[key],
    )

    // Shares are taken against the finite total only. When the cell is
    // impassable there is no meaningful denominator, so every bar reads 0
    // rather than inventing a proportion out of a partial sum.
    const total = breakdown.total
    const denominator = total !== null && total > 0 ? total : 0

    const rows: CostRow[] = KEYS.map((key) => ({
      key,
      label: LABELS[key],
      value: breakdown[key],
      share:
        denominator > 0 && breakdown[key] !== null
          ? (breakdown[key] as number) / denominator
          : 0,
      weight: weights[WEIGHT_KEY[key]],
    }))

    return { rows, total, impassableBy, cell: selectedCell }
  }, [cellTelemetry, selectedCell, weights])
}
```

- [ ] **Adım 2: `overlays.ts` oluştur**

```ts
import type { OverlayLayer } from '../../overlay/types'

/** A ring on the cell whose cost is being explained. */
export function selectedCellOverlay(cell: [number, number] | null): OverlayLayer[] {
  if (!cell) return []
  return [
    {
      kind: 'points',
      id: 'cost-explain-selected',
      points: [{ row: cell[0], col: cell[1] }],
      style: { color: '#f8fafc', radius: 5, opacity: 0.95 },
    },
  ]
}
```

- [ ] **Adım 3: `CostExplainPanel.tsx` oluştur**

```tsx
import type { CostRow } from './useCostExplain'
import './cost-explain.css'

export function CostExplainPanel({
  rows,
  total,
  impassableBy,
  cell,
}: {
  rows: CostRow[]
  total: number | null
  impassableBy: string[]
  cell: [number, number] | null
}) {
  if (!cell || rows.length === 0) {
    return (
      <p className="lp-cost-note">
        Hover a cell on the map to see what makes it expensive.
      </p>
    )
  }

  const impassable = impassableBy.length > 0

  return (
    <div className="lp-cost-card">
      <div className="lp-cost-head">
        <span className="lp-cost-cell">
          row {cell[0]} · col {cell[1]}
        </span>
        {impassable ? (
          <span className="lp-cost-verdict lp-cost-impassable">Impassable</span>
        ) : (
          <span className="lp-cost-verdict">
            {total === null ? 'unknown' : total.toFixed(3)}
          </span>
        )}
      </div>

      {impassable ? (
        <p className="lp-cost-reason">
          Closed by <strong>{impassableBy.join(', ')}</strong>. This cell costs
          infinity — no route can cross it.
        </p>
      ) : null}

      <ul className="lp-cost-bars">
        {rows.map((row) => (
          <li key={row.key} className="lp-cost-bar-row">
            <span className="lp-cost-label">
              {row.label}
              <em className="lp-cost-weight">w {row.weight.toFixed(3)}</em>
            </span>

            <span className="lp-cost-track">
              {/* A null contribution is never drawn as a zero-length bar --
                  infinity is the largest value there is, not the smallest. */}
              {row.value === null ? (
                <span className="lp-cost-fill lp-cost-fill-inf" style={{ width: '100%' }} />
              ) : (
                <span
                  className="lp-cost-fill"
                  style={{ width: `${Math.min(100, row.share * 100)}%` }}
                />
              )}
            </span>

            <span className="lp-cost-value">
              {row.value === null ? '∞' : row.value.toFixed(3)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
```

- [ ] **Adım 4: `cost-explain.css` oluştur**

```css
.lp-cost-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.45);
}

.lp-cost-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.lp-cost-cell {
  font-size: 11px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.lp-cost-verdict {
  font-size: 15px;
  font-weight: 700;
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.lp-cost-impassable {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #f87171;
}

.lp-cost-reason {
  margin: 0 0 10px;
  font-size: 11px;
  line-height: 1.5;
  color: #fca5a5;
}

.lp-cost-bars { list-style: none; margin: 0; padding: 0; display: grid; gap: 7px; }

.lp-cost-bar-row {
  display: grid;
  grid-template-columns: 92px 1fr 56px;
  align-items: center;
  gap: 9px;
}

.lp-cost-label {
  font-size: 11px;
  color: #cbd5f5;
  display: flex;
  flex-direction: column;
}

.lp-cost-weight { font-size: 9px; color: #64748b; font-style: normal; }

.lp-cost-track {
  height: 7px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
  overflow: hidden;
}

.lp-cost-fill { display: block; height: 100%; background: #60a5fa; }
.lp-cost-fill-inf { background: repeating-linear-gradient(
  45deg, #f87171 0 5px, rgba(248, 113, 113, 0.45) 5px 10px); }

.lp-cost-value {
  font-size: 11px;
  text-align: right;
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.lp-cost-note { margin: 0; font-size: 11px; color: #94a3b8; }
```

- [ ] **Adım 5: `index.tsx` oluştur**

```tsx
import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CostExplainPanel } from './CostExplainPanel'
import { selectedCellOverlay } from './overlays'
import { useCostExplain } from './useCostExplain'

const OVERLAY_ID = 'cost-explain'

export function CostExplain() {
  const state = useCostExplain()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, selectedCellOverlay(state.cell))
    return () => unregister(OVERLAY_ID)
  }, [register, state.cell, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Cost Breakdown</p>
      <CostExplainPanel {...state} />
    </section>
  )
}
```

- [ ] **Adım 6: `App.tsx`'e tek satırla bağla**

```tsx
<RightRailSlot>
  <CostExplain />
</RightRailSlot>
```

Import: `import { CostExplain } from './features/cost-explain'`

- [ ] **Adım 7: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 8: Elle kabul**

1. Haritada geçilebilir bir hücrenin üstüne gel → dört çubuk doluyor
2. **Toplamı doğrula:** dört değeri topla, panelin gösterdiği toplama eşit
   olmalı (yuvarlama toleransında). Eşit değilse durup nedenini bul —
   `explain()` `max(running, MIN_CELL_COST)` uyguluyor olabilir, o durumda
   küçük bir alt sınır farkı beklenir ve panel bunu belirtmelidir
3. Traversability katmanına geç, **geçilemez** (koyu) bir hücrenin üstüne gel →
   panel **Impassable** yazıyor, hangi bileşenin kapattığını söylüyor, o
   bileşenin çubuğu **çizgili ve tam dolu** — boş değil
4. Ağırlık kaydıraçlarını oynat → `w` değerleri panelde güncelleniyor
5. Ağ sekmesi → hücre üstünde gezinirken **ek bir `/api/cell-telemetry`
   isteği yok** (App.tsx'in zaten yaptığı istek kullanılıyor)

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/features/cost-explain/ frontend/src/App.tsx
git commit -m "feat(frontend): show why a cell costs what it costs

CostMap.explain() has published the weighted per-layer contribution of
every cell since phase 2 and /api/cell-telemetry carried it, but the
frontend trimmed the response to four fields and dropped it. Reads what
is already fetched -- no extra request.

A null contribution is infinity, not missing data (costmap.py:143-158
maps inf to null because Starlette serialises with allow_nan=False), so
it renders as a full hatched bar reading 'Impassable' with the component
that closed the cell named. A zero-length bar would have said the
opposite of the truth."
```

---

### Görev 8: F2a — `corridor` · Koridor sözleşmesi

`Corridor`, LunaPath'in yerel planlayıcıya verdiği tek arayüz — ve şu ana kadar
`/api/plan` yanıtında gelip atılıyordu. Bu görev onu hem tabloya hem haritaya
koyar.

**Dizi uzunlukları (`corridor.py:109-131`) — ribbon çizimi buna bağlı:**

| Alan | Uzunluk | Neyin başına |
|---|---|---|
| `waypoints` | **N** | her yol pikseli |
| `fallback_points` | **N** | her yol pikseli |
| `half_width_m` | **N − 1** | her **segment** |
| `max_slope_deg` | **N − 1** | her segment |
| `energy_budget_wh` | **N − 1** | her segment |
| `thermal_budget_K_s` | **N − 1** | her segment |

Ribbon `N` merkez noktası ister ama yalnızca `N − 1` genişlik vardır. Köşe
başına genişlik, o köşeye komşu segmentlerin **en darı** alınarak türetilir —
koridoru asla olduğundan geniş göstermemek için.

**Files:**
- Create: `frontend/src/features/corridor/index.tsx`
- Create: `frontend/src/features/corridor/useCorridor.ts`
- Create: `frontend/src/features/corridor/CorridorPanel.tsx`
- Create: `frontend/src/features/corridor/overlays.ts`
- Create: `frontend/src/features/corridor/corridor.css`
- Modify: `frontend/src/App.tsx` (bir satır)

**Interfaces:**
- Consumes: `useMission()` (`planResult`), `useOverlays()`, `api/terrain.ts`'ten `fetchTerrain`, `mission/geo.ts`'ten `frameFromManifest` + `metresToPixel`
- Produces:
  - `useCorridor(): { corridor: Corridor | null; frame: GridFrame | null; segments: SegmentRow[]; error: string | null }`
  - `type SegmentRow = { index: number; halfWidthM: number; maxSlopeDeg: number; energyWh: number; thermalKs: number }`
  - `corridorOverlays(corridor, frame): OverlayLayer[]`

- [ ] **Adım 1: `useCorridor.ts` oluştur**

```ts
import { useEffect, useMemo, useState } from 'react'
import { fetchTerrain } from '../../api/terrain'
import { frameFromManifest, type GridFrame } from '../../mission/geo'
import { useMission } from '../../mission/MissionContext'
import type { Corridor } from '../../mission/types'

export interface SegmentRow {
  index: number
  halfWidthM: number
  maxSlopeDeg: number
  energyWh: number
  thermalKs: number
}

export function useCorridor() {
  const { planResult, roverId, weights } = useMission()
  const [frame, setFrame] = useState<GridFrame | null>(null)
  const [error, setError] = useState<string | null>(null)

  // The georeference, not the layers: the corridor speaks CRS metres and the
  // canvas speaks pixels, and the manifest is where origin/resolution live.
  useEffect(() => {
    const controller = new AbortController()
    fetchTerrain({ roverId, weights }, controller.signal)
      .then((manifest) => {
        const next = frameFromManifest(manifest)
        setFrame(next)
        setError(next ? null : 'Grid has no georeference; corridor cannot be placed.')
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Terrain manifest unavailable')
      })
    return () => controller.abort()
  }, [roverId, weights])

  const corridor = (planResult as { corridor?: Corridor | null } | null)?.corridor ?? null

  const segments = useMemo<SegmentRow[]>(() => {
    if (!corridor) return []
    // All four budget arrays are per-segment and therefore N-1 long
    // (corridor.py:126). half_width_m is the shortest of them by definition
    // of the loop, so its length is the segment count.
    return corridor.half_width_m.map((halfWidth, index) => ({
      index,
      halfWidthM: halfWidth,
      maxSlopeDeg: corridor.max_slope_deg[index] ?? Number.NaN,
      energyWh: corridor.energy_budget_wh[index] ?? Number.NaN,
      thermalKs: corridor.thermal_budget_K_s[index] ?? Number.NaN,
    }))
  }, [corridor])

  return { corridor, frame, segments, error }
}
```

- [ ] **Adım 2: `overlays.ts` oluştur**

```ts
import { metresToPixel, type GridFrame, type PixelPoint } from '../../mission/geo'
import type { OverlayLayer } from '../../overlay/types'
import type { Corridor } from '../../mission/types'

/**
 * Per-vertex half-width from the per-segment array.
 *
 * There are N waypoints but only N-1 segment widths (corridor.py:126). A
 * vertex takes the NARROWER of the segments meeting there: widening a
 * corner to the roomier neighbour would draw permission the planner never
 * granted.
 */
function vertexHalfWidths(halfWidthM: number[], vertexCount: number): number[] {
  const out: number[] = []
  for (let i = 0; i < vertexCount; i++) {
    const before = i > 0 ? halfWidthM[i - 1] : Number.POSITIVE_INFINITY
    const after = i < halfWidthM.length ? halfWidthM[i] : Number.POSITIVE_INFINITY
    const width = Math.min(before, after)
    out.push(Number.isFinite(width) ? width : 0)
  }
  return out
}

export function corridorOverlays(
  corridor: Corridor | null,
  frame: GridFrame | null,
): OverlayLayer[] {
  if (!corridor || !frame || corridor.waypoints.length < 2) return []

  const center: PixelPoint[] = corridor.waypoints.map(([x, y]) =>
    metresToPixel(x, y, frame),
  )
  const widthsM = vertexHalfWidths(corridor.half_width_m, center.length)
  const halfWidthPx = widthsM.map((metres) => metres / frame.resolutionM)

  const fallback: PixelPoint[] = corridor.fallback_points.map(([x, y]) =>
    metresToPixel(x, y, frame),
  )

  return [
    {
      kind: 'ribbon',
      id: 'corridor-band',
      center,
      halfWidthPx,
      style: { color: '#38bdf8', opacity: 0.22 },
    },
    {
      kind: 'points',
      id: 'corridor-havens',
      points: fallback,
      style: { color: '#34d399', radius: 2.5, opacity: 0.7 },
    },
  ]
}
```

- [ ] **Adım 3: `CorridorPanel.tsx` oluştur**

```tsx
import type { Corridor } from '../../mission/types'
import type { SegmentRow } from './useCorridor'
import './corridor.css'

function narrowest(segments: SegmentRow[]): SegmentRow | null {
  return segments.reduce<SegmentRow | null>(
    (best, row) => (best === null || row.halfWidthM < best.halfWidthM ? row : best),
    null,
  )
}

export function CorridorPanel({
  corridor,
  segments,
  error,
}: {
  corridor: Corridor | null
  segments: SegmentRow[]
  error: string | null
}) {
  if (error) return <p className="lp-corridor-note lp-corridor-warn">{error}</p>

  // build_corridor rejects a path shorter than two waypoints, and the plan
  // response carries corridor: null in that case -- say so rather than
  // rendering an empty table that looks like a corridor with no segments.
  if (!corridor) {
    return (
      <p className="lp-corridor-note">
        No corridor. Plan a route first — a corridor needs at least two waypoints.
      </p>
    )
  }

  const tightest = narrowest(segments)

  return (
    <div className="lp-corridor-card">
      <div className="lp-corridor-head">
        <span className="lp-corridor-id" title="Echo this back to /api/pose">
          {corridor.corridor_id}
        </span>
        <span className="lp-corridor-count">{segments.length} segments</span>
      </div>

      {tightest ? (
        <p className="lp-corridor-tight">
          Narrowest point: <strong>{tightest.halfWidthM.toFixed(1)} m</strong> of
          lateral room at segment {tightest.index}
        </p>
      ) : null}

      <div className="lp-corridor-scroll">
        <table className="lp-corridor-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Half-width</th>
              <th>Slope cap</th>
              <th>Energy</th>
              <th>Thermal</th>
            </tr>
          </thead>
          <tbody>
            {segments.map((row) => (
              <tr key={row.index}>
                <td>{row.index}</td>
                <td>{row.halfWidthM.toFixed(1)} m</td>
                <td>{row.maxSlopeDeg.toFixed(1)}°</td>
                <td>{row.energyWh.toFixed(1)} Wh</td>
                <td>{row.thermalKs.toFixed(0)} K·s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Adım 4: `corridor.css` oluştur**

```css
.lp-corridor-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.45);
}

.lp-corridor-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.lp-corridor-id {
  font-family: ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.05em;
  color: #38bdf8;
}

.lp-corridor-count { font-size: 10px; color: #64748b; }

.lp-corridor-tight {
  margin: 0 0 10px;
  font-size: 11px;
  line-height: 1.5;
  color: #94a3b8;
}

.lp-corridor-tight strong { color: #e2e8f0; }

.lp-corridor-scroll { max-height: 210px; overflow-y: auto; overflow-x: auto; }

.lp-corridor-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.lp-corridor-table th {
  position: sticky;
  top: 0;
  background: #0f172a;
  text-align: right;
  font-size: 9px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #64748b;
  padding: 4px 6px;
}

.lp-corridor-table th:first-child,
.lp-corridor-table td:first-child { text-align: left; color: #64748b; }

.lp-corridor-table td {
  text-align: right;
  padding: 3px 6px;
  color: #cbd5f5;
  border-top: 1px solid rgba(148, 163, 184, 0.09);
}

.lp-corridor-note { margin: 0; font-size: 11px; color: #94a3b8; }
.lp-corridor-warn { color: #fbbf24; }
```

- [ ] **Adım 5: `index.tsx` oluştur**

```tsx
import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CorridorPanel } from './CorridorPanel'
import { corridorOverlays } from './overlays'
import { useCorridor } from './useCorridor'

const OVERLAY_ID = 'corridor'

export function CorridorFeature() {
  const { corridor, frame, segments, error } = useCorridor()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, corridorOverlays(corridor, frame))
    return () => unregister(OVERLAY_ID)
  }, [corridor, frame, register, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Corridor</p>
      <CorridorPanel corridor={corridor} segments={segments} error={error} />
    </section>
  )
}
```

- [ ] **Adım 6: `App.tsx`'e tek satırla bağla**

`<RightRailSlot>` içine, `<CostExplain />`'in altına:

```tsx
  <CorridorFeature />
```

Import: `import { CorridorFeature } from './features/corridor'`

- [ ] **Adım 7: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 8: Elle kabul — koordinat dönüşümünü ispatla**

Bu görevin en riskli kısmı `metresToPixel` (spec riski: yanlışsa F2a ve F7
birlikte yanlış). İspat adımları:

1. Rota üret → koridor şeridi çiziliyor
2. **Şerit rotanın üstünde mi?** Şerit rotayı ortalamalı. Şerit haritanın
   *başka bir yerinde* veya **dikey olarak aynalanmışsa**, `metresToPixel`'in
   `y` terimi ters — durup Görev 3'e dön
3. Şerit rota boyunca **daralıp genişliyor** (sabit genişlikte değil)
4. Yeşil sığınak noktaları rotanın yakınında, dağınık değil
5. **Sayısal ispat:** konsolda ilk waypoint'i piksele çevir ve rotanın ilk
   pikseliyle karşılaştır:

```js
// planResult.corridor.waypoints[0] ve planResult.waypoints[0] üzerinden
const [x, y] = corridor.waypoints[0]
const frame = { originX: -32500, originY: 11000, resolutionM: 5 }
console.log({ row: (frame.originY - y) / frame.resolutionM,
              col: (x - frame.originX) / frame.resolutionM })
// beklenen: planResult.waypoints[0].row / .col ile aynı (±1 piksel)
```

Expected: iki değer eşleşiyor. Eşleşmiyorsa **devam etme** — dönüşüm yanlış.

6. Tablo: segment sayısı, waypoint sayısından **bir eksik** olmalı
7. Başlangıç ve hedefi aynı hücreye yakın seç, planlama başarısız olsun →
   panel "No corridor" diyor, boş tablo göstermiyor

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/features/corridor/ frontend/src/App.tsx
git commit -m "feat(frontend): draw the corridor the planner actually hands over

Corridor is the single interface between the global planner and any local
layer, and /api/plan has carried it since phase 2 -- the frontend dropped
the field. Now it is a band on the map whose width follows the real
clearance, with the safe-haven points, and a per-segment budget table.

Vertex widths take the narrower of the two segments meeting at a corner:
there are N waypoints but N-1 segment widths (corridor.py:126), and
widening a corner to the roomier neighbour would draw permission the
planner never granted. Verified the metre-to-pixel transform by matching
corridor.waypoints[0] against the route's own first pixel."
```

---

### Görev 9: F2b — `replan` · Yedi tetikleyici

`/api/replan` bir telemetri paketi alıp yedi tetikleyiciyi değerlendiriyor ve
ateşleyen varsa yeniden planlıyor. Frontend'de hiç yok.

**Bu görevin dürüstlük çekirdeği:** yanıt üç liste taşıyor — `triggers`
(ateşleyen), `evaluated` (bakılan), `skipped` (**bakılamayan**, çünkü telemetri
alanı eksik). Panel üçünü de ayrı gösterir. `skipped`'ı yutmak, %1 batarya ile
"her şey yolunda" demektir — backend bu hatayı bir review'da düzeltmişti
(`main.py:748-763`), frontend aynı hatayı tekrarlamamalı.

**Files:**
- Create: `frontend/src/api/replan.ts`
- Create: `frontend/src/features/replan/index.tsx`
- Create: `frontend/src/features/replan/useReplan.ts`
- Create: `frontend/src/features/replan/ReplanPanel.tsx`
- Create: `frontend/src/mission/triggers.ts`
- Create: `frontend/src/features/replan/replan.css`
- Modify: `frontend/src/App.tsx` (bir satır: `<LeftRailSlot>`)

**Interfaces:**
- Consumes: `postJson`, `useMission()` (`start`, `goal`, `roverId`, `weights`, `planResult`), `useOverlays()`
- Produces:
  - `requestReplan(body, signal): Promise<ReplanResponse>`
  - `TRIGGER_FIELDS: Record<TriggerId, { label: string; fields: TelemetryField[] }>`
  - `useReplan(): { form, setField, submit, result, busy, error, rows }`

- [ ] **Adım 1: `api/replan.ts` oluştur**

```ts
import { postJson } from './client'
import type { PlanWeights } from '../api'
import type { ReplanResponse } from '../mission/types'

export interface ReplanBody {
  current: { row: number; col: number }
  goal: { row: number; col: number }
  rover_id: string
  weights: PlanWeights
  /** Telemetry snapshot. Every value must be finite -- the backend rejects NaN. */
  state: Record<string, number>
  force?: boolean
}

export async function requestReplan(
  body: ReplanBody,
  signal?: AbortSignal,
): Promise<ReplanResponse> {
  return postJson<ReplanResponse>('/replan', body, signal)
}
```

- [ ] **Adım 2: `mission/triggers.ts` oluştur — yedi tetikleyicinin girdileri**

> Bu dosya `features/` altında değil `mission/` altında: hem Görev 9 hem Görev 12
> kullanıyor ve bir modülün başka bir modülün iç dosyasını import etmesi global
> kısıtı çiğnerdi.

Alan adları `replan_triggers.py:144-157`'deki `_TRIGGER_INPUTS` sözlüğüyle
birebir aynıdır. Bir alan adı uydurulursa tetikleyici sessizce `skipped`'a
düşer.

```ts
import type { TriggerId } from './types'

export interface TelemetryField {
  key: string
  label: string
  /** A sensible starting value so the form is usable without guesswork. */
  initial: number
  step: number
}

/**
 * What each trigger needs, mirroring _TRIGGER_INPUTS
 * (replan_triggers.py:144-157). A key that does not match makes the backend
 * report the trigger as skipped -- not as failing.
 */
export const TRIGGER_FIELDS: Record<TriggerId, { label: string; fields: TelemetryField[] }> = {
  soc_deviation: {
    label: 'State of charge deviation',
    fields: [
      { key: 'actual_soc', label: 'Actual SoC', initial: 0.62, step: 0.01 },
      { key: 'planned_soc', label: 'Planned SoC', initial: 0.7, step: 0.01 },
    ],
  },
  inner_temperature: {
    label: 'Inner temperature',
    fields: [
      { key: 'actual_inner_c', label: 'Actual inner °C', initial: -8, step: 1 },
      { key: 'predicted_inner_c', label: 'Predicted inner °C', initial: -5, step: 1 },
    ],
  },
  time_drift: {
    label: 'Schedule drift',
    fields: [{ key: 'drift_minutes', label: 'Drift (min)', initial: 12, step: 1 }],
  },
  corridor_violation: {
    label: 'Corridor violation',
    fields: [
      { key: 'lateral_offset_m', label: 'Lateral offset (m)', initial: 12, step: 1 },
      { key: 'half_width_m', label: 'Corridor half-width (m)', initial: 20, step: 1 },
    ],
  },
  comm_window: {
    label: 'Comm window',
    fields: [
      { key: 'comm_minutes_remaining', label: 'Earth visibility left (min)', initial: 45, step: 5 },
    ],
  },
  localization_uncertainty: {
    label: 'Localization uncertainty',
    fields: [
      { key: 'localization_covariance_m', label: 'Position 1σ (m)', initial: 6, step: 1 },
      { key: 'half_width_m', label: 'Corridor half-width (m)', initial: 20, step: 1 },
    ],
  },
  slip_accumulation: {
    label: 'Slip accumulation',
    fields: [
      { key: 'map_progress_m', label: 'Map progress (m)', initial: 180, step: 10 },
      { key: 'odometer_claim_m', label: 'Odometer claim (m)', initial: 210, step: 10 },
    ],
  },
}

export const TRIGGER_IDS = Object.keys(TRIGGER_FIELDS) as TriggerId[]

/** Every distinct telemetry key, deduplicated -- half_width_m feeds two triggers. */
export function initialTelemetry(): Record<string, number> {
  const out: Record<string, number> = {}
  for (const id of TRIGGER_IDS) {
    for (const field of TRIGGER_FIELDS[id].fields) {
      out[field.key] = field.initial
    }
  }
  return out
}
```

- [ ] **Adım 3: `useReplan.ts` oluştur**

```ts
import { useCallback, useMemo, useState } from 'react'
import { requestReplan } from '../../api/replan'
import { useMission } from '../../mission/MissionContext'
import type { ReplanResponse, TriggerId } from '../../mission/types'
import { TRIGGER_IDS, initialTelemetry } from '../../mission/triggers'

export type TriggerStatus = 'fired' | 'clear' | 'unchecked'

export interface TriggerRow {
  id: TriggerId
  status: TriggerStatus
  detail: string | null
}

export function useReplan() {
  const { start, goal, roverId, weights } = useMission()
  const [form, setForm] = useState<Record<string, number>>(initialTelemetry)
  const [result, setResult] = useState<ReplanResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setField = useCallback((key: string, value: number) => {
    setForm((current) => ({ ...current, [key]: value }))
  }, [])

  const submit = useCallback(
    async (force: boolean) => {
      if (!start || !goal) {
        setError('Pick a start and a goal first — a replan starts from where the rover is.')
        return
      }
      setBusy(true)
      setError(null)
      try {
        const response = await requestReplan({
          current: { row: start[0], col: start[1] },
          goal: { row: goal[0], col: goal[1] },
          rover_id: roverId,
          weights,
          state: form,
          force,
        })
        setResult(response)
      } catch (cause: unknown) {
        setError(cause instanceof Error ? cause.message : 'Replan request failed')
      } finally {
        setBusy(false)
      }
    },
    [form, goal, roverId, start, weights],
  )

  const rows = useMemo<TriggerRow[]>(() => {
    if (!result) return []
    const fired = new Map(result.triggers.map((t) => [t.trigger_id, t.detail]))
    const skipped = new Set(result.skipped)

    return TRIGGER_IDS.map((id) => {
      if (fired.has(id)) {
        return { id, status: 'fired' as const, detail: fired.get(id) ?? null }
      }
      // A trigger the backend could NOT evaluate is never "clear". Missing
      // telemetry once answered "no replan needed" at 1% battery; the
      // backend reports it in `skipped` precisely so a client cannot repeat
      // that (main.py:748-763).
      if (skipped.has(id)) {
        return { id, status: 'unchecked' as const, detail: 'Telemetry field missing' }
      }
      return { id, status: 'clear' as const, detail: null }
    })
  }, [result])

  return { form, setField, submit, result, busy, error, rows }
}
```

- [ ] **Adım 4: `ReplanPanel.tsx` oluştur**

```tsx
import type { ReplanResponse } from '../../mission/types'
import { TRIGGER_FIELDS, TRIGGER_IDS } from '../../mission/triggers'
import type { TriggerRow } from './useReplan'
import './replan.css'

const STATUS_LABEL = {
  fired: 'Fired',
  clear: 'Clear',
  unchecked: 'Not checked',
} as const

export function ReplanPanel({
  form,
  setField,
  submit,
  result,
  busy,
  error,
  rows,
}: {
  form: Record<string, number>
  setField: (key: string, value: number) => void
  submit: (force: boolean) => void
  result: ReplanResponse | null
  busy: boolean
  error: string | null
  rows: TriggerRow[]
}) {
  // Deduplicated: half_width_m feeds both corridor_violation and
  // localization_uncertainty, and two inputs writing one key would fight.
  const seen = new Set<string>()

  return (
    <div className="lp-replan-card">
      <div className="lp-replan-form">
        {TRIGGER_IDS.flatMap((id) =>
          TRIGGER_FIELDS[id].fields
            .filter((field) => {
              if (seen.has(field.key)) return false
              seen.add(field.key)
              return true
            })
            .map((field) => (
              <label key={field.key} className="lp-replan-field">
                <span>{field.label}</span>
                <input
                  type="number"
                  step={field.step}
                  value={form[field.key] ?? 0}
                  onChange={(event) => setField(field.key, Number(event.target.value))}
                />
              </label>
            )),
        )}
      </div>

      <div className="lp-replan-actions">
        <button type="button" disabled={busy} onClick={() => submit(false)}>
          {busy ? 'Evaluating…' : 'Evaluate triggers'}
        </button>
        <button type="button" disabled={busy} onClick={() => submit(true)}>
          Force replan
        </button>
      </div>

      {error ? <p className="lp-replan-note lp-replan-warn">{error}</p> : null}

      {result ? (
        <>
          <p className="lp-replan-verdict">
            {result.replanned
              ? `Replanned — ${result.triggers.length} trigger(s) fired`
              : (result.reason ?? 'No replan trigger fired')}
          </p>

          <ul className="lp-replan-list">
            {rows.map((row) => (
              <li key={row.id} className={`lp-replan-row lp-replan-${row.status}`}>
                <span className="lp-replan-name">{TRIGGER_FIELDS[row.id].label}</span>
                <span className="lp-replan-status">{STATUS_LABEL[row.status]}</span>
                {row.detail ? <span className="lp-replan-detail">{row.detail}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
```

- [ ] **Adım 5: `replan.css` oluştur**

```css
.lp-replan-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.45);
}

.lp-replan-form { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }

.lp-replan-field { display: flex; flex-direction: column; gap: 3px; }

.lp-replan-field span {
  font-size: 9px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #64748b;
}

.lp-replan-field input {
  background: rgba(2, 6, 23, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 6px;
  padding: 4px 7px;
  color: #e2e8f0;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.lp-replan-actions { display: flex; gap: 7px; margin: 11px 0 9px; }

.lp-replan-actions button {
  flex: 1;
  border-radius: 7px;
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
  font-size: 11px;
  padding: 6px 8px;
  cursor: pointer;
}

.lp-replan-actions button:disabled { opacity: 0.5; cursor: default; }

.lp-replan-verdict { margin: 0 0 8px; font-size: 12px; color: #e2e8f0; }

.lp-replan-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }

.lp-replan-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 9px;
  padding: 5px 8px;
  border-radius: 6px;
  border-left: 3px solid transparent;
  background: rgba(148, 163, 184, 0.07);
  font-size: 11px;
}

.lp-replan-fired     { border-left-color: #f87171; }
.lp-replan-clear     { border-left-color: #34d399; }
/* Amber, not green: a trigger that could not be evaluated is an open
   question, not an all-clear. */
.lp-replan-unchecked { border-left-color: #fbbf24; }

.lp-replan-name { color: #cbd5f5; }
.lp-replan-status { color: #94a3b8; font-size: 10px; }

.lp-replan-detail {
  grid-column: 1 / -1;
  color: #94a3b8;
  font-size: 10px;
  line-height: 1.45;
}

.lp-replan-note { margin: 8px 0 0; font-size: 11px; color: #94a3b8; }
.lp-replan-warn { color: #fbbf24; }
```

- [ ] **Adım 6: `index.tsx` oluştur**

```tsx
import { ReplanPanel } from './ReplanPanel'
import { useReplan } from './useReplan'

export function Replan() {
  const state = useReplan()
  return (
    <section className="rail-section">
      <p className="panel-kicker">Replan Triggers</p>
      <ReplanPanel {...state} />
    </section>
  )
}
```

- [ ] **Adım 7: `App.tsx`'e tek satırla bağla**

`<LeftRailSlot>` içine, `<LayerProvenance />`'ın altına `<Replan />`.
Import: `import { Replan } from './features/replan'`

- [ ] **Adım 8: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 9: Elle kabul — üç durumu da ispatla**

1. Rota üret, sonra **Evaluate triggers** → yedi satır listeleniyor
2. **Ateşleme:** `lateral_offset_m` = 40, `half_width_m` = 20 → 
   `corridor_violation` **Fired** (kırmızı) ve `detail` metni gerçek sayıları
   yazıyor ("lateral offset 40.0 m exceeds corridor half-width 20.0 m")
3. **Temiz:** `lateral_offset_m` = 5 → aynı satır **Clear** (yeşil)
4. **Bakılamadı:** `actual_soc` alanını sil (boş bırak veya kaldır) →
   `soc_deviation` satırı **Not checked** (sarı) ve "Telemetry field missing"
   yazıyor. **Yeşil olmamalı** — bu görevin asıl kabul kriteri budur
5. **Force replan** → `replanned: true` ve yeni bir plan dönüyor
6. Başlangıç/hedef seçmeden butona bas → "Pick a start and a goal first"
   uyarısı, çökme yok

- [ ] **Adım 10: Commit**

```bash
git add frontend/src/api/replan.ts frontend/src/features/replan/ frontend/src/App.tsx
git commit -m "feat(frontend): evaluate the seven replan triggers, skips included

/api/replan has evaluated seven triggers against a telemetry snapshot
since phase 2 with nothing in the cockpit to drive it. Injects telemetry
and lists every trigger in one of three states.

The third state is the point: a trigger the backend could not evaluate
reads 'Not checked' in amber, never 'Clear'. Missing telemetry once
answered 'no replan needed' at 1% battery, which is why the backend
reports `skipped` at all (main.py:748-763) -- rendering it as an
all-clear would rebuild the same bug on this side of the wire."
```

---

### Görev 10: `api/series.ts` + `api/plan4d.ts` — zaman küpü istemcisi

Görev 11'in (F3) ihtiyacı olan iki uç. Ayrı bir görev çünkü ikili küp çözümünün
kendi doğrulaması var: `(T, rows, cols)` dizisi **slice-major, sonra row-major**
sıralı ve `NaN` veri yok demek — sıra yanlış varsayılırsa animasyon anlamsız
ama makul görünen bir şey oynatır.

**Files:**
- Create: `frontend/src/api/series.ts`
- Create: `frontend/src/api/plan4d.ts`

**Interfaces:**
- Consumes: `getJson`, `getFloat32`, `postJson`
- Produces:
  - `fetchSeriesManifest(params, signal): Promise<SeriesManifest>`
  - `fetchSeriesCube(binaryUrl, expected, signal): Promise<SeriesCube>`
  - `type SeriesCube = { data: Float32Array; slices: number; rows: number; cols: number; sliceAt(index): Float32Array }`
  - `planRoute4D(body, signal): Promise<Plan4DResponse>`

- [ ] **Adım 1: `api/series.ts` oluştur**

```ts
import { getFloat32, getJson } from './client'
import type { SeriesManifest } from '../mission/types'

export interface SeriesParams {
  startUtc?: string
  nSlices?: number
  sliceHours?: number
  downsample?: number
}

export async function fetchSeriesManifest(
  params: SeriesParams = {},
  signal?: AbortSignal,
): Promise<SeriesManifest> {
  const query = new URLSearchParams()
  if (params.startUtc) query.set('start_utc', params.startUtc)
  if (params.nSlices !== undefined) query.set('n_slices', String(params.nSlices))
  if (params.sliceHours !== undefined) query.set('slice_hours', String(params.sliceHours))
  if (params.downsample !== undefined) query.set('downsample', String(params.downsample))
  const suffix = query.toString()
  return getJson<SeriesManifest>(`/illumination-series${suffix ? `?${suffix}` : ''}`, signal)
}

export interface SeriesCube {
  data: Float32Array
  slices: number
  rows: number
  cols: number
  /** A zero-copy view of one time slice. NaN cells are no-data. */
  sliceAt: (index: number) => Float32Array
}

/**
 * Fetch a time cube from a binary_url the manifest published.
 *
 * The URL is used VERBATIM -- the manifest already encoded start_utc,
 * downsample and field into it, and rebuilding the query by hand is how a
 * "+" in an ISO-8601 offset turns into a space.
 *
 * Layout is slice-major then row-major (binary_format.order), so slice t
 * occupies [t*rows*cols, (t+1)*rows*cols). Asserting the length here means
 * a layout change surfaces as an error rather than as a plausible-looking
 * animation of the wrong thing.
 */
export async function fetchSeriesCube(
  binaryUrl: string,
  expected: { slices: number; rows: number; cols: number },
  signal?: AbortSignal,
): Promise<SeriesCube> {
  // binary_url arrives as "/api/illumination-series?..."; getFloat32 prefixes
  // "/api", so the duplicated prefix is stripped.
  const path = binaryUrl.startsWith('/api') ? binaryUrl.slice(4) : binaryUrl
  const { data } = await getFloat32(path, signal)

  const { slices, rows, cols } = expected
  if (data.length !== slices * rows * cols) {
    throw new Error(
      `Series cube: ${data.length} values do not fill ${slices}x${rows}x${cols}`,
    )
  }

  const perSlice = rows * cols
  return {
    data,
    slices,
    rows,
    cols,
    sliceAt: (index: number) =>
      data.subarray(index * perSlice, (index + 1) * perSlice),
  }
}
```

- [ ] **Adım 2: `api/plan4d.ts` oluştur**

```ts
import { postJson } from './client'
import type { PlanWeights } from '../api'
import type { Plan4DResponse } from '../mission/types'

export interface Plan4DBody {
  start: { row: number; col: number }
  goal: { row: number; col: number }
  rover_id: string
  weights: PlanWeights
  /** State the window as n_slices OR horizon_hours -- not both (main.py:895). */
  n_slices?: number
  horizon_hours?: number
  slice_hours?: number
  coarsen?: number
  start_utc?: string
}

export async function planRoute4D(
  body: Plan4DBody,
  signal?: AbortSignal,
): Promise<Plan4DResponse> {
  return postJson<Plan4DResponse>('/plan-4d', body, signal)
}
```

- [ ] **Adım 3: Küpü elle doğrula**

Backend çalışırken:

```bash
curl -s "http://localhost:8000/api/illumination-series?n_slices=4&slice_hours=1&downsample=10" | head -c 600
```

Expected: JSON manifest dönüyor; `binary_format.shape` `[4, 50, 50]`,
`binary_format.order` `"slice-major, then row-major"`.

```bash
curl -s "http://localhost:8000/api/illumination-series?n_slices=4&slice_hours=1&downsample=10&format=f32&field=shadow" --output /tmp/cube.bin && wc -c /tmp/cube.bin
```

Expected: `40000` bayt (4 × 50 × 50 × 4). Farklıysa `fetchSeriesCube`'un uzunluk
kontrolü doğru çalışıyor demektir — ama şekli manifest'ten okuduğundan emin ol.

`shadow_model.model` alanını da not al:
- `"spice_horizon"` → zaman serisi gerçek, F3 animasyonu anlamlı
- `"static"` → ufuk önbelleği yok; **önce `python scripts/build_horizon_cache.py`
  çalıştır**, yoksa Görev 11'in kabulü yapılamaz

- [ ] **Adım 4: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint`
Expected: temiz

- [ ] **Adım 5: Commit**

```bash
git add frontend/src/api/series.ts frontend/src/api/plan4d.ts
git commit -m "feat(frontend): read the illumination cube and the 4-D planner

The cube is slice-major then row-major with NaN for no-data, so the length
is asserted against the manifest's own shape: a layout that shifted would
otherwise animate something plausible and wrong. binary_url is used
verbatim rather than rebuilt, because the manifest already encoded
start_utc -- and a '+' in an ISO-8601 offset does not survive a hand-built
query string."
```

---

### Görev 11: F3 — `time-axis` · Zaman ekseni ve BEKLE

Faz 3'ün tek cümlelik iddiası: **"planlayıcı beklemeyi seçti"** bir slogan değil
bir karar. Bunu göstermek, bu plandaki en çarpıcı demo.

**Ön koşul:** `python scripts/build_horizon_cache.py` bir kez çalıştırılmış
olmalı (`lunapath/data/processed/horizon_map.npy`). Çalıştırılmamışsa
`shadow_model.model === "static"` döner ve panel bunu **açıkça söyler** —
statik bir küpü animasyonluymuş gibi oynatmak, spec'in dördüncü dürüstlük
kuralının ihlalidir.

**Files:**
- Create: `frontend/src/features/time-axis/index.tsx`
- Create: `frontend/src/features/time-axis/useTimeAxis.ts`
- Create: `frontend/src/features/time-axis/TimeAxisPanel.tsx`
- Create: `frontend/src/features/time-axis/overlays.ts`
- Create: `frontend/src/features/time-axis/time-axis.css`
- Modify: `frontend/src/App.tsx` (bir satır: `<BottomDock>`)

**Interfaces:**
- Consumes: `fetchSeriesManifest`, `fetchSeriesCube`, `planRoute4D`, `useMission()`, `useOverlays()`
- Produces:
  - `useTimeAxis(): { manifest, cube, sliceIndex, setSliceIndex, playing, togglePlay, field, setField, plan4d, planning, runPlan4D, error, timeVarying }`
  - `timeAxisOverlays(cube, sliceIndex, field, manifest, plan4d): OverlayLayer[]`

- [ ] **Adım 1: `useTimeAxis.ts` oluştur**

```ts
import { useCallback, useEffect, useRef, useState } from 'react'
import { planRoute4D } from '../../api/plan4d'
import { fetchSeriesCube, fetchSeriesManifest, type SeriesCube } from '../../api/series'
import { useMission } from '../../mission/MissionContext'
import type { Plan4DResponse, SeriesManifest } from '../../mission/types'

export type SeriesField = 'shadow' | 'surface_temp_c'

const N_SLICES = 24
const SLICE_HOURS = 1
// 24 x 500 x 500 x 4 B is 24 MB per field. Halving each axis makes it 6 MB,
// which is what a slider scrubbing at 10 fps can afford to keep resident.
const DOWNSAMPLE = 2

export function useTimeAxis() {
  const { start, goal, roverId, weights } = useMission()

  const [manifest, setManifest] = useState<SeriesManifest | null>(null)
  const [cube, setCube] = useState<SeriesCube | null>(null)
  const [field, setField] = useState<SeriesField>('shadow')
  const [sliceIndex, setSliceIndex] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [plan4d, setPlan4d] = useState<Plan4DResponse | null>(null)
  const [planning, setPlanning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const timerRef = useRef<number | null>(null)

  // Manifest first, cube second: the manifest publishes the binary_url and
  // the shape the cube must fill, so neither is guessed.
  useEffect(() => {
    const controller = new AbortController()
    setError(null)

    fetchSeriesManifest(
      { nSlices: N_SLICES, sliceHours: SLICE_HOURS, downsample: DOWNSAMPLE },
      controller.signal,
    )
      .then(async (next) => {
        setManifest(next)
        const entry = next.fields[field]
        const loaded = await fetchSeriesCube(
          entry.binary_url,
          { slices: next.slices, rows: next.grid.rows, cols: next.grid.cols },
          controller.signal,
        )
        setCube(loaded)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Illumination series unavailable')
      })

    return () => controller.abort()
  }, [field])

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!playing || !cube) {
      stop()
      return
    }
    timerRef.current = window.setInterval(() => {
      setSliceIndex((current) => (current + 1) % cube.slices)
    }, 120)
    return stop
  }, [cube, playing, stop])

  useEffect(() => stop, [stop])

  const togglePlay = useCallback(() => setPlaying((current) => !current), [])

  const runPlan4D = useCallback(async () => {
    if (!start || !goal) {
      setError('Pick a start and a goal first.')
      return
    }
    setPlanning(true)
    setError(null)
    try {
      const response = await planRoute4D({
        start: { row: start[0], col: start[1] },
        goal: { row: goal[0], col: goal[1] },
        rover_id: roverId,
        weights,
        n_slices: N_SLICES,
        coarsen: 4,
      })
      setPlan4d(response)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : '4-D plan failed')
    } finally {
      setPlanning(false)
    }
  }, [goal, roverId, start, weights])

  // "static" means the cube did NOT vary with time. Playing it would be a
  // lie told at 8 fps (spec T7).
  const timeVarying = manifest?.shadow_model.model !== 'static'

  return {
    manifest,
    cube,
    field,
    setField,
    sliceIndex,
    setSliceIndex,
    playing,
    togglePlay,
    plan4d,
    planning,
    runPlan4D,
    error,
    timeVarying,
  }
}
```

- [ ] **Adım 2: `overlays.ts` oluştur**

```ts
import type { SeriesCube } from '../../api/series'
import type { Plan4DResponse, SeriesManifest } from '../../mission/types'
import type { OverlayLayer } from '../../overlay/types'
import type { SeriesField } from './useTimeAxis'

const RAMP = { shadow: 'grayReverse', surface_temp_c: 'thermal' } as const

export function timeAxisOverlays(
  cube: SeriesCube | null,
  sliceIndex: number,
  field: SeriesField,
  manifest: SeriesManifest | null,
  plan4d: Plan4DResponse | null,
): OverlayLayer[] {
  const layers: OverlayLayer[] = []

  if (cube && manifest) {
    const entry = manifest.fields[field]
    // The manifest's own min/max across the WHOLE cube, not this slice's:
    // a per-slice domain would re-normalise the colours every frame and the
    // animation would show contrast changing rather than illumination.
    const min = entry.min ?? 0
    const max = entry.max ?? 1
    layers.push({
      kind: 'field',
      id: 'time-axis-field',
      data: cube.sliceAt(Math.min(sliceIndex, cube.slices - 1)),
      rows: cube.rows,
      cols: cube.cols,
      domain: [min, max],
      ramp: RAMP[field],
      opacity: 0.6,
    })
  }

  if (plan4d && plan4d.path_pixels.length > 1) {
    // path_pixels, not path_pixels_coarse: the fine array is the one in the
    // same frame as /api/plan and as the canvas (spec T4).
    layers.push({
      kind: 'polyline',
      id: 'time-axis-route',
      points: plan4d.path_pixels.map(([row, col]) => ({ row, col })),
      style: { color: '#facc15', lineWidth: 2.5, opacity: 0.95 },
    })
  }

  return layers
}
```

- [ ] **Adım 3: `TimeAxisPanel.tsx` oluştur**

```tsx
import type { Plan4DResponse, SeriesManifest } from '../../mission/types'
import type { SeriesField } from './useTimeAxis'
import './time-axis.css'

export function TimeAxisPanel({
  manifest,
  field,
  setField,
  sliceIndex,
  setSliceIndex,
  playing,
  togglePlay,
  plan4d,
  planning,
  runPlan4D,
  error,
  timeVarying,
}: {
  manifest: SeriesManifest | null
  field: SeriesField
  setField: (next: SeriesField) => void
  sliceIndex: number
  setSliceIndex: (next: number) => void
  playing: boolean
  togglePlay: () => void
  plan4d: Plan4DResponse | null
  planning: boolean
  runPlan4D: () => void
  error: string | null
  timeVarying: boolean
}) {
  const sun = manifest?.sun[sliceIndex] ?? null
  const hours = manifest ? sliceIndex * manifest.slice_hours : 0

  return (
    <div className="lp-time-card">
      <div className="lp-time-row">
        <button type="button" className="lp-time-play" onClick={togglePlay}
          disabled={!manifest || !timeVarying}>
          {playing ? '❚❚' : '▶'}
        </button>

        <input
          className="lp-time-slider"
          type="range"
          min={0}
          max={manifest ? manifest.slices - 1 : 0}
          value={sliceIndex}
          onChange={(event) => setSliceIndex(Number(event.target.value))}
          disabled={!manifest}
        />

        <span className="lp-time-clock">+{hours.toFixed(1)} h</span>

        <select
          className="lp-time-field"
          value={field}
          onChange={(event) => setField(event.target.value as SeriesField)}
        >
          <option value="shadow">Shadow</option>
          <option value="surface_temp_c">Surface temp</option>
        </select>

        <button type="button" className="lp-time-plan" onClick={runPlan4D} disabled={planning}>
          {planning ? 'Planning…' : 'Plan through time'}
        </button>
      </div>

      {/* The honesty gate. A static cube gets said out loud, not animated. */}
      {manifest && !timeVarying ? (
        <p className="lp-time-note lp-time-warn">
          No time series — the horizon cache has not been built, so this cube does
          not vary with time.
          {manifest.shadow_model.reason ? ` ${manifest.shadow_model.reason}` : ''}
          {' '}Run <code>python scripts/build_horizon_cache.py</code> once.
        </p>
      ) : null}

      {sun ? (
        <p className="lp-time-note">
          Sun: {sun.elevation_deg.toFixed(2)}° elevation ·{' '}
          {sun.azimuth_grid_deg.toFixed(1)}° grid azimuth · {sun.utc}
        </p>
      ) : null}

      {plan4d ? (
        <p className="lp-time-verdict">
          {plan4d.metrics.wait_steps > 0 ? (
            <>
              <strong>The planner chose to wait.</strong> {plan4d.metrics.wait_steps} wait
              step(s), {plan4d.metrics.move_steps} move step(s); arrival at{' '}
              {plan4d.metrics.arrival_hours?.toFixed(1) ?? '—'} h over a{' '}
              {plan4d.horizon_hours.toFixed(0)} h window.
            </>
          ) : (
            <>
              No waiting: {plan4d.metrics.move_steps} move step(s).{' '}
              {plan4d.shadow_model.model === 'static'
                ? 'The cube was static, so waiting could not have helped.'
                : 'Waiting would not have paid off on this route.'}
            </>
          )}
        </p>
      ) : null}

      {error ? <p className="lp-time-note lp-time-warn">{error}</p> : null}
    </div>
  )
}
```

- [ ] **Adım 4: `time-axis.css` oluştur**

```css
.lp-time-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 10px 14px;
  background: rgba(15, 23, 42, 0.6);
}

.lp-time-row { display: flex; align-items: center; gap: 10px; }

.lp-time-play,
.lp-time-plan {
  border-radius: 7px;
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd;
  font-size: 11px;
  padding: 5px 10px;
  cursor: pointer;
}

.lp-time-play:disabled,
.lp-time-plan:disabled { opacity: 0.45; cursor: default; }

.lp-time-slider { flex: 1; accent-color: #38bdf8; }

.lp-time-clock {
  font-size: 12px;
  color: #e2e8f0;
  font-variant-numeric: tabular-nums;
  min-width: 60px;
  text-align: right;
}

.lp-time-field {
  background: rgba(2, 6, 23, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 6px;
  color: #e2e8f0;
  font-size: 11px;
  padding: 4px 6px;
}

.lp-time-note { margin: 8px 0 0; font-size: 11px; line-height: 1.5; color: #94a3b8; }
.lp-time-warn { color: #fbbf24; }
.lp-time-note code { color: #cbd5f5; }

.lp-time-verdict { margin: 8px 0 0; font-size: 12px; line-height: 1.5; color: #e2e8f0; }
.lp-time-verdict strong { color: #facc15; }
```

- [ ] **Adım 5: `index.tsx` oluştur**

```tsx
import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { TimeAxisPanel } from './TimeAxisPanel'
import { timeAxisOverlays } from './overlays'
import { useTimeAxis } from './useTimeAxis'

const OVERLAY_ID = 'time-axis'

export function TimeAxis() {
  const state = useTimeAxis()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(
      OVERLAY_ID,
      timeAxisOverlays(state.cube, state.sliceIndex, state.field, state.manifest, state.plan4d),
    )
    return () => unregister(OVERLAY_ID)
  }, [
    register,
    state.cube,
    state.field,
    state.manifest,
    state.plan4d,
    state.sliceIndex,
    unregister,
  ])

  return <TimeAxisPanel {...state} />
}
```

- [ ] **Adım 6: `App.tsx`'e tek satırla bağla**

```tsx
<BottomDock>
  <TimeAxis />
</BottomDock>
```

Import: `import { TimeAxis } from './features/time-axis'`

- [ ] **Adım 7: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 8: Elle kabul**

Önce ufuk önbelleğini üret:

```bash
python scripts/build_horizon_cache.py
```

Expected: birkaç dakika sürer, `lunapath/data/processed/horizon_map.npy` yazar
(~69 MiB, şekil `(72, 500, 500)`). Backend'i yeniden başlat.

Sonra:
1. Alt dokta kaydırıcıyı sürükle → **harita üzerindeki gölge alanı değişiyor**
2. ▶ bas → animasyon dönüyor; ❚❚ ile duruyor
3. Sun satırı her dilimde farklı bir yükseklik/azimut gösteriyor
4. Alanı **Surface temp**'e çevir → küp yeniden yükleniyor, renk rampası değişiyor
5. Başlangıç/hedef seç, **Plan through time** → sarı 4B rota çiziliyor
6. `wait_steps > 0` olan bir senaryo bul (gölgeli bir bölgeden geçen uzun bir
   rota) → panel **"The planner chose to wait."** yazıyor

**Ufuk önbelleği olmadan da bir kez dene** (dosyayı geçici olarak yeniden
adlandır): panel **sarı uyarı** gösteriyor, ▶ butonu **devre dışı**, animasyon
oynamıyor. Bu görevin dürüstlük kabul kriteri budur.

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/features/time-axis/ frontend/src/App.tsx
git commit -m "feat(frontend): scrub the illumination cube and show the WAIT decision

Phase 3 built a 4-D planner whose whole point is that waiting for the Sun
is a decision, and /api/illumination-series published the cube it reasons
over. Neither reached the cockpit. Adds a time slider over the cube, the
Sun track per slice, and the 4-D route.

The colour domain comes from the manifest's whole-cube min/max rather than
the visible slice: a per-slice domain re-normalises every frame, so the
animation would show contrast moving instead of illumination. And when
shadow_model.model is 'static' the cube did not vary with time -- play is
disabled and the panel says the horizon cache is missing, because
animating a static cube is a lie told at 8 fps."
```

---

### Görev 12: F7 — `pose-loop` · Kapalı döngü

Faz 7'nin iddiası: **LunaPath odometri üretmez, tüketir.** Zincir
`poz → sapma → tetikleyici → replan` backend'de uçtan uca test ediliyor ama
kokpitte hiç görünmüyor.

Karar politikası (`localization.py`): `localization_uncertainty` ateşlediğinde
öneri `replan` **değil** `stop_and_localize` — geniş bir belirsizlikle replan
yapmak, yalan bir pozdan plan yapmaktır. Panel bu iki öneriyi **görsel olarak
ayırır**.

**Files:**
- Create: `frontend/src/api/pose.ts`
- Create: `frontend/src/features/pose-loop/index.tsx`
- Create: `frontend/src/features/pose-loop/usePoseLoop.ts`
- Create: `frontend/src/features/pose-loop/PoseLoopPanel.tsx`
- Create: `frontend/src/features/pose-loop/overlays.ts`
- Create: `frontend/src/features/pose-loop/pose-loop.css`
- Modify: `frontend/src/App.tsx` (bir satır)

**Interfaces:**
- Consumes: `postJson`, `useMission()` (`planResult`), `useOverlays()`, `mission/geo.ts`
- Produces:
  - `submitPose(body, signal): Promise<PoseResponse>`
  - `usePoseLoop(): { form, setField, submit, result, busy, error, rows }`

- [ ] **Adım 1: `api/pose.ts` oluştur**

Alan adları `PoseEstimate` ile birebir (`pose.py:80-113`). **Sekizinin hepsi
zorunludur** — hiçbirinin varsayılanı yok, eksik gönderilen istek 422 döner.

```ts
import { postJson } from './client'
import type { PoseResponse } from '../mission/types'

/**
 * Which estimator produced the pose. Required, and not decorative: a
 * dead-reckoned pose and an absolute fix carry different trust, and
 * localization_budget uses this to decide whether a source resets
 * accumulated drift or merely slows it (pose.py:50-62).
 */
export type PoseSource =
  | 'dead_reckoning'
  | 'visual_odometry'
  | 'lidar_odometry'
  | 'skyline_fix'
  | 'sun_sensor'

/** skyline_fix and sun_sensor fix against an external absolute reference. */
export const ABSOLUTE_SOURCES: PoseSource[] = ['skyline_fix', 'sun_sensor']

export interface PoseEstimateBody {
  /** Projected CRS easting, metres -- the frame the corridor uses. */
  x_m: number
  /** Projected CRS northing, metres. */
  y_m: number
  /** Grid azimuth: 0 = grid north (decreasing row), 90 = grid east, clockwise. */
  heading_deg: number
  /** 1-sigma horizontal position uncertainty, metres. */
  covariance_m: number
  /** 1-sigma heading uncertainty, degrees. */
  heading_covariance_deg: number
  timestamp_utc: string
  source: PoseSource
  /**
   * Distance the estimator CLAIMS to have covered, measured from the start
   * of the ACTIVE corridor -- reset it whenever a new plan is issued. The
   * gap between this and actual advance along the corridor is slip.
   */
  distance_travelled_m: number
}

export interface PoseBody {
  pose: PoseEstimateBody
  /** Telemetry the pose cannot supply -- same shape as ReplanRequest.state. */
  state?: Record<string, number>
  /** Echo corridor_fix.along_track_m from the previous response. */
  previous_along_track_m?: number
  /** Echo the corridor_id from the /api/plan that produced this route. */
  corridor_id?: string
}

export async function submitPose(
  body: PoseBody,
  signal?: AbortSignal,
): Promise<PoseResponse> {
  return postJson<PoseResponse>('/pose', body, signal)
}
```

- [ ] **Adım 2: `usePoseLoop.ts` oluştur**

```ts
import { useCallback, useMemo, useState } from 'react'
import { submitPose, type PoseEstimateBody } from '../../api/pose'
import { useMission } from '../../mission/MissionContext'
import type { Corridor, PoseResponse, TriggerId } from '../../mission/types'
import { TRIGGER_IDS } from '../../mission/triggers'

export type PoseStatus = 'fired' | 'clear' | 'unchecked'

export interface PoseTriggerRow {
  id: TriggerId
  status: PoseStatus
  detail: string | null
}

/** Mirrors PoseEstimateBody. Every field is required by the backend. */
export type PoseForm = PoseEstimateBody

export function usePoseLoop() {
  const { planResult } = useMission()
  const corridor =
    (planResult as { corridor?: Corridor | null } | null)?.corridor ?? null

  const [form, setForm] = useState<PoseForm>({
    x_m: 0,
    y_m: 0,
    heading_deg: 0,
    covariance_m: 3,
    heading_covariance_deg: 5,
    timestamp_utc: new Date().toISOString(),
    source: 'dead_reckoning',
    distance_travelled_m: 0,
  })
  const [result, setResult] = useState<PoseResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setField = useCallback(<K extends keyof PoseForm>(key: K, value: PoseForm[K]) => {
    setForm((current) => ({ ...current, [key]: value }))
  }, [])

  /** Seed the form from a corridor waypoint so the metres are plausible. */
  const seedFromCorridor = useCallback(
    (index: number) => {
      if (!corridor || !corridor.waypoints[index]) return
      const [x, y] = corridor.waypoints[index]
      setForm((current) => ({ ...current, x_m: x, y_m: y }))
    },
    [corridor],
  )

  const submit = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const response = await submitPose({
        // The whole estimate: every PoseEstimate field is required
        // (pose.py:80-113). The timestamp is stamped at send time rather
        // than when the form was first rendered.
        pose: { ...form, timestamp_utc: new Date().toISOString() },
        // Echoing both closes the loop the way the backend documents it:
        // corridor_id pins the judgement to THIS route rather than whichever
        // plan ran last, and along_track_m is the progress prior that stops a
        // switchback's outbound leg from capturing a pose on the return leg.
        corridor_id: corridor?.corridor_id,
        previous_along_track_m: result?.corridor_fix.along_track_m,
      })
      setResult(response)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Pose evaluation failed')
    } finally {
      setBusy(false)
    }
  }, [corridor, form, result])

  const rows = useMemo<PoseTriggerRow[]>(() => {
    if (!result) return []
    const fired = new Map(result.fired_triggers.map((t) => [t.trigger_id, t.detail]))
    const skipped = new Set(result.skipped)

    return TRIGGER_IDS.map((id) => {
      if (fired.has(id)) return { id, status: 'fired' as const, detail: fired.get(id) ?? null }
      if (skipped.has(id)) {
        return { id, status: 'unchecked' as const, detail: 'Telemetry field missing' }
      }
      return { id, status: 'clear' as const, detail: null }
    })
  }, [result])

  return { form, setField, seedFromCorridor, submit, result, busy, error, rows, corridor }
}
```

- [ ] **Adım 3: `overlays.ts` oluştur**

```ts
import { metresToPixel, type GridFrame } from '../../mission/geo'
import type { OverlayLayer } from '../../overlay/types'
import type { Corridor, PoseResponse } from '../../mission/types'

/**
 * The pose, and the line from it to the corridor centreline.
 *
 * along_track_m locates the projection along the corridor; converting it to
 * a waypoint index needs the corridor's own spacing, so the nearest
 * waypoint is found by distance instead -- fewer assumptions, same picture.
 */
export function poseOverlays(
  pose: { x_m: number; y_m: number } | null,
  result: PoseResponse | null,
  corridor: Corridor | null,
  frame: GridFrame | null,
): OverlayLayer[] {
  if (!pose || !frame) return []

  const posePixel = metresToPixel(pose.x_m, pose.y_m, frame)
  const layers: OverlayLayer[] = [
    {
      kind: 'points',
      id: 'pose-current',
      points: [posePixel],
      style: {
        // Red when the pose broke the corridor, amber when localization is
        // too uncertain to trust it, white otherwise.
        color:
          result?.recommended_action === 'stop_and_localize'
            ? '#fbbf24'
            : result && result.fired_triggers.length > 0
              ? '#f87171'
              : '#f8fafc',
        radius: 5,
      },
    },
  ]

  if (corridor && result) {
    let nearest = corridor.waypoints[0]
    let best = Number.POSITIVE_INFINITY
    for (const [x, y] of corridor.waypoints) {
      const distance = Math.hypot(x - pose.x_m, y - pose.y_m)
      if (distance < best) {
        best = distance
        nearest = [x, y]
      }
    }
    layers.push({
      kind: 'polyline',
      id: 'pose-deviation',
      points: [posePixel, metresToPixel(nearest[0], nearest[1], frame)],
      style: { color: '#fbbf24', lineWidth: 1.5, dash: [4, 3], opacity: 0.9 },
    })
  }

  return layers
}
```

- [ ] **Adım 4: `PoseLoopPanel.tsx` oluştur**

```tsx
import type { PoseSource } from '../../api/pose'
import { TRIGGER_FIELDS } from '../../mission/triggers'
import type { Corridor, PoseResponse } from '../../mission/types'
import type { PoseForm, PoseTriggerRow } from './usePoseLoop'
import './pose-loop.css'

const STATUS_LABEL = { fired: 'Fired', clear: 'Clear', unchecked: 'Not checked' } as const

export function PoseLoopPanel({
  form,
  setField,
  seedFromCorridor,
  submit,
  result,
  busy,
  error,
  rows,
  corridor,
}: {
  form: PoseForm
  setField: <K extends keyof PoseForm>(key: K, value: PoseForm[K]) => void
  seedFromCorridor: (index: number) => void
  submit: () => void
  result: PoseResponse | null
  busy: boolean
  error: string | null
  rows: PoseTriggerRow[]
  corridor: Corridor | null
}) {
  const fix = result?.corridor_fix
  const outside = fix ? fix.lateral_offset_m > fix.half_width_m : false

  return (
    <div className="lp-pose-card">
      {!corridor ? (
        <p className="lp-pose-note">
          No active corridor. Plan a route first — a pose is only meaningful
          against the route the rover is driving.
        </p>
      ) : null}

      <div className="lp-pose-form">
        <label className="lp-pose-field">
          <span>Easting x_m</span>
          <input type="number" step={5} value={form.x_m}
            onChange={(e) => setField('x_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Northing y_m</span>
          <input type="number" step={5} value={form.y_m}
            onChange={(e) => setField('y_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Heading (grid °)</span>
          <input type="number" step={5} value={form.heading_deg}
            onChange={(e) => setField('heading_deg', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Position 1σ (m)</span>
          <input type="number" step={1} min={0} value={form.covariance_m}
            onChange={(e) => setField('covariance_m', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Heading 1σ (°)</span>
          <input type="number" step={1} min={0} value={form.heading_covariance_deg}
            onChange={(e) => setField('heading_covariance_deg', Number(e.target.value))} />
        </label>
        <label className="lp-pose-field">
          <span>Odometer claim (m)</span>
          <input type="number" step={10} min={0} value={form.distance_travelled_m}
            onChange={(e) => setField('distance_travelled_m', Number(e.target.value))} />
        </label>

        {/* A free-text source would 422. These five are the whole vocabulary
            (pose.py:50-56), and which one is chosen changes how much the
            backend trusts the fix. */}
        <label className="lp-pose-field lp-pose-wide">
          <span>Source</span>
          <select value={form.source}
            onChange={(e) => setField('source', e.target.value as PoseSource)}>
            <option value="dead_reckoning">dead_reckoning</option>
            <option value="visual_odometry">visual_odometry</option>
            <option value="lidar_odometry">lidar_odometry</option>
            <option value="skyline_fix">skyline_fix (absolute)</option>
            <option value="sun_sensor">sun_sensor (absolute)</option>
          </select>
        </label>
      </div>

      <div className="lp-pose-actions">
        <button type="button" disabled={!corridor}
          onClick={() => seedFromCorridor(Math.floor((corridor?.waypoints.length ?? 1) / 2))}>
          Seed from route
        </button>
        <button type="button" disabled={busy || !corridor} onClick={submit}>
          {busy ? 'Locating…' : 'Evaluate pose'}
        </button>
      </div>

      {error ? <p className="lp-pose-note lp-pose-warn">{error}</p> : null}

      {result && fix ? (
        <>
          <div className={`lp-pose-verdict lp-pose-${result.recommended_action}`}>
            {result.recommended_action.replace(/_/g, ' ')}
          </div>

          <dl className="lp-pose-facts">
            <div>
              <dt>Lateral offset</dt>
              <dd className={outside ? 'lp-pose-bad' : undefined}>
                {fix.lateral_offset_m.toFixed(1)} m
              </dd>
            </div>
            <div>
              <dt>Corridor half-width</dt>
              <dd>{fix.half_width_m.toFixed(1)} m</dd>
            </div>
            <div>
              <dt>Along track</dt>
              <dd>{fix.along_track_m.toFixed(1)} m</dd>
            </div>
          </dl>

          <ul className="lp-pose-list">
            {rows.map((row) => (
              <li key={row.id} className={`lp-pose-row lp-pose-${row.status}`}>
                <span>{TRIGGER_FIELDS[row.id].label}</span>
                <span className="lp-pose-status">{STATUS_LABEL[row.status]}</span>
                {row.detail ? <span className="lp-pose-detail">{row.detail}</span> : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  )
}
```

- [ ] **Adım 5: `pose-loop.css` oluştur**

```css
.lp-pose-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.45);
}

.lp-pose-form { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.lp-pose-field { display: flex; flex-direction: column; gap: 3px; }

.lp-pose-field span {
  font-size: 9px; letter-spacing: 0.06em; text-transform: uppercase; color: #64748b;
}

.lp-pose-wide { grid-column: 1 / -1; }

.lp-pose-field input,
.lp-pose-field select {
  background: rgba(2, 6, 23, 0.65);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 6px; padding: 4px 7px; color: #e2e8f0; font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.lp-pose-actions { display: flex; gap: 7px; margin: 11px 0 9px; }

.lp-pose-actions button {
  flex: 1; border-radius: 7px;
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd; font-size: 11px; padding: 6px 8px; cursor: pointer;
}

.lp-pose-actions button:disabled { opacity: 0.45; cursor: default; }

.lp-pose-verdict {
  border-radius: 7px; padding: 7px 10px; margin-bottom: 9px;
  font-size: 11px; font-weight: 700; letter-spacing: 0.09em; text-transform: uppercase;
  text-align: center;
}

/* stop_and_localize is NOT a replan. Replanning from a pose you do not
   trust is planning from a lie, so the two never share a colour. */
.lp-pose-stop_and_localize { background: rgba(251, 191, 36, 0.16); color: #fbbf24; }
.lp-pose-replan            { background: rgba(248, 113, 113, 0.16); color: #f87171; }
.lp-pose-continue          { background: rgba(52, 211, 153, 0.14); color: #34d399; }

.lp-pose-facts { display: flex; gap: 16px; margin: 0 0 9px; flex-wrap: wrap; }
.lp-pose-facts div { display: flex; flex-direction: column; gap: 2px; }

.lp-pose-facts dt {
  font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: #64748b;
}

.lp-pose-facts dd {
  margin: 0; font-size: 13px; color: #e2e8f0; font-variant-numeric: tabular-nums;
}

.lp-pose-bad { color: #f87171; }

.lp-pose-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }

.lp-pose-row {
  display: grid; grid-template-columns: 1fr auto; gap: 3px 9px;
  padding: 4px 8px; border-radius: 6px; border-left: 3px solid transparent;
  background: rgba(148, 163, 184, 0.07); font-size: 11px; color: #cbd5f5;
}

.lp-pose-fired { border-left-color: #f87171; }
.lp-pose-clear { border-left-color: #34d399; }
.lp-pose-unchecked { border-left-color: #fbbf24; }

.lp-pose-status { color: #94a3b8; font-size: 10px; }
.lp-pose-detail { grid-column: 1 / -1; color: #94a3b8; font-size: 10px; line-height: 1.45; }

.lp-pose-note { margin: 0 0 9px; font-size: 11px; color: #94a3b8; line-height: 1.5; }
.lp-pose-warn { color: #fbbf24; }
```

- [ ] **Adım 6: `index.tsx` oluştur**

```tsx
import { useEffect, useState } from 'react'
import { fetchTerrain } from '../../api/terrain'
import { frameFromManifest, type GridFrame } from '../../mission/geo'
import { useMission } from '../../mission/MissionContext'
import { useOverlays } from '../../overlay/useOverlays'
import { PoseLoopPanel } from './PoseLoopPanel'
import { poseOverlays } from './overlays'
import { usePoseLoop } from './usePoseLoop'

const OVERLAY_ID = 'pose-loop'

export function PoseLoop() {
  const { roverId, weights } = useMission()
  const state = usePoseLoop()
  const { register, unregister } = useOverlays()
  const [frame, setFrame] = useState<GridFrame | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchTerrain({ roverId, weights }, controller.signal)
      .then((manifest) => setFrame(frameFromManifest(manifest)))
      .catch(() => setFrame(null))
    return () => controller.abort()
  }, [roverId, weights])

  useEffect(() => {
    register(
      OVERLAY_ID,
      poseOverlays(
        { x_m: state.form.x_m, y_m: state.form.y_m },
        state.result,
        state.corridor,
        frame,
      ),
    )
    return () => unregister(OVERLAY_ID)
  }, [frame, register, state.corridor, state.form.x_m, state.form.y_m, state.result, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Pose Loop</p>
      <PoseLoopPanel {...state} />
    </section>
  )
}
```

- [ ] **Adım 7: `App.tsx`'e tek satırla bağla**

`<RightRailSlot>` içine `<PoseLoop />`.
Import: `import { PoseLoop } from './features/pose-loop'`

- [ ] **Adım 8: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 9: Elle kabul — kapalı döngüyü ispatla**

1. Rota üret → koridor oluşuyor, `corridor_id` görünüyor
2. **Seed from route** → `x_m`/`y_m` koridorun ortasındaki waypoint'e ayarlanıyor
3. **Evaluate pose** → `lateral_offset_m` ≈ 0, öneri `continue`, poz beyaz
4. **Koridor dışına çık:** `x_m`'e koridorun yarı genişliğinin iki katını ekle →
   `corridor_violation` **Fired**, poz **kırmızı**, kesikli sapma çizgisi
   koridora uzanıyor
5. **Belirsizliği yükselt:** `Position 1σ` = 60 → `localization_uncertainty`
   **Fired** ve öneri **`stop_and_localize`** (sarı) — `replan` **değil**
6. Öneri `stop_and_localize` iken poz işareti **sarı**, kırmızı değil
7. Rota planlamadan **Evaluate pose** → 409 mesajı okunabilir bir uyarı olarak
   görünüyor ("No active corridor…"), çökme yok
8. Arka arkaya iki poz gönder → ikinci istekte `previous_along_track_m`
   gönderiliyor (ağ sekmesinden doğrula)
9. **Süresi dolmuş koridor (spec T9):** 33 kez arka arkaya rota planla —
   koridorlar bellekte ve yalnızca son 32'si tutuluyor (`main.py:106`) — sonra
   ilk `corridor_id` ile poz gönder → 404 detayı okunabilir bir uyarı olarak
   görünüyor ("corridor_id … is not known to this process… re-plan to get a
   fresh one"), çökme yok
10. `source` seçicisini `skyline_fix`'e çevir → istek 422 dönmüyor (enum
    değeri geçerli); serbest metin gönderilmiyor

- [ ] **Adım 10: Commit**

```bash
git add frontend/src/api/pose.ts frontend/src/features/pose-loop/ frontend/src/App.tsx
git commit -m "feat(frontend): close the pose loop in the cockpit

Phase 7's chain -- pose, corridor projection, triggers, replan -- was
tested end to end in the backend and invisible in the UI. Submits a pose
against the active corridor and shows the deviation, the triggers it
fired, and the recommended action.

stop_and_localize never shares a colour with replan: when localization
uncertainty no longer fits inside the corridor, replanning would be
planning from a pose you have just decided not to trust. Echoes
corridor_id so a second concurrent plan cannot capture the judgement, and
previous_along_track_m so a switchback's outbound leg cannot capture a
pose driving the return leg."
```

---

### Görev 13: F5 — `profile-compare` · Dört profil yan yana

`/api/compare` dört misyon profilini (`balanced`, `energy_saver`, `fast_recon`,
`shadow_traverse`) aynı başlangıç/hedef için planlayıp karşılaştırıyor. Hiçbiri
kokpitte yok.

**`constraint_check` üç durumludur** (`scenarios.py:110-128`), iki değil:

| Alan | Anlamı |
|---|---|
| `enforced_in_search: true` | Kısıt aramanın içinde uygulandı (`max_slope_deg`) — yapısal olarak sağlanır |
| `checked: false` | Simülasyon koşmadı; **bu bir "geçti" değil** |
| `satisfied` | Yalnızca `checked: true` iken anlamlı |

Panel `checked: false` olanı **"not checked"** gösterir, "passed" değil.

**Files:**
- Create: `frontend/src/api/compare.ts`
- Create: `frontend/src/features/profile-compare/index.tsx`
- Create: `frontend/src/features/profile-compare/useProfileCompare.ts`
- Create: `frontend/src/features/profile-compare/ProfileComparePanel.tsx`
- Create: `frontend/src/features/profile-compare/overlays.ts`
- Create: `frontend/src/features/profile-compare/profile-compare.css`
- Modify: `frontend/src/App.tsx` (bir satır)

**Interfaces:**
- Consumes: `postJson`, `useMission()` (`start`, `goal`, `roverId`), `useOverlays()`
- Produces:
  - `compareProfiles(body, signal): Promise<CompareResponse>`
  - `useProfileCompare(): { results, comparison, run, busy, error }`
  - `profileOverlays(results): OverlayLayer[]`

- [ ] **Adım 1: `api/compare.ts` oluştur**

```ts
import { postJson } from './client'
import type { CompareResponse, PlanMultiResponse } from '../mission/types'

/** start and goal are PIXEL PAIRS here -- [row, col], not {row, col}
 *  (CompareRequest uses PixelPair, main.py:430-433). */
export interface CompareBody {
  start: [number, number]
  goal: [number, number]
  rover_id: string
}

export async function compareProfiles(
  body: CompareBody,
  signal?: AbortSignal,
): Promise<CompareResponse> {
  return postJson<CompareResponse>('/compare', body, signal)
}

export interface PlanMultiBody extends CompareBody {
  profiles: string[]
}

export async function planMulti(
  body: PlanMultiBody,
  signal?: AbortSignal,
): Promise<PlanMultiResponse> {
  return postJson<PlanMultiResponse>('/plan-multi', body, signal)
}
```

- [ ] **Adım 2: `useProfileCompare.ts` oluştur**

```ts
import { useCallback, useState } from 'react'
import { compareProfiles } from '../../api/compare'
import { useMission } from '../../mission/MissionContext'
import type { ProfileResult } from '../../mission/types'

export interface ConstraintVerdict {
  name: string
  limit: number | null
  actual: number | null
  enforcedInSearch: boolean
  checked: boolean
  satisfied: boolean
}

export function readConstraints(result: ProfileResult): ConstraintVerdict[] {
  const raw = (result.constraint_check ?? {}) as Record<string, Record<string, unknown>>
  return Object.entries(raw).map(([name, entry]) => ({
    name,
    limit: typeof entry.limit === 'number' ? entry.limit : null,
    actual: typeof entry.actual === 'number' ? entry.actual : null,
    enforcedInSearch: entry.enforced_in_search === true,
    // A constraint the backend could not test is not a pass. It reports
    // checked:false precisely so a client does not read silence as success
    // (scenarios.py:104-108).
    checked: entry.checked === true,
    satisfied: entry.satisfied === true,
  }))
}

export function useProfileCompare() {
  const { start, goal, roverId } = useMission()
  const [results, setResults] = useState<ProfileResult[]>([])
  const [comparison, setComparison] = useState<Record<string, unknown> | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async () => {
    if (!start || !goal) {
      setError('Pick a start and a goal first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await compareProfiles({ start, goal, rover_id: roverId })
      setResults(response.results)
      setComparison(response.comparison)
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : 'Profile comparison failed')
    } finally {
      setBusy(false)
    }
  }, [goal, roverId, start])

  return { results, comparison, run, busy, error }
}
```

- [ ] **Adım 3: `overlays.ts` oluştur**

```ts
import type { ProfileResult } from '../../mission/types'
import type { OverlayLayer } from '../../overlay/types'

/** One polyline per profile, in the colour the backend assigned it. */
export function profileOverlays(results: ProfileResult[]): OverlayLayer[] {
  return results
    .filter((result) => !result.error && result.path_pixels.length > 1)
    .map((result) => ({
      kind: 'polyline' as const,
      id: `profile-${result.profile_id}`,
      points: result.path_pixels.map(([row, col]) => ({ row, col })),
      style: { color: result.color, lineWidth: 2, opacity: 0.85 },
    }))
}
```

- [ ] **Adım 4: `ProfileComparePanel.tsx` oluştur**

```tsx
import type { ProfileResult } from '../../mission/types'
import { readConstraints } from './useProfileCompare'
import './profile-compare.css'

function metric(result: ProfileResult, key: string): string {
  const value = result.metrics[key]
  return typeof value === 'number' ? value.toFixed(1) : '—'
}

export function ProfileComparePanel({
  results,
  run,
  busy,
  error,
}: {
  results: ProfileResult[]
  run: () => void
  busy: boolean
  error: string | null
}) {
  return (
    <div className="lp-compare-card">
      <button type="button" className="lp-compare-run" disabled={busy} onClick={run}>
        {busy ? 'Comparing…' : 'Compare all profiles'}
      </button>

      {error ? <p className="lp-compare-note lp-compare-warn">{error}</p> : null}

      {results.map((result) => {
        const constraints = readConstraints(result)
        const violated = constraints.filter((c) => c.checked && !c.satisfied)
        const unchecked = constraints.filter((c) => !c.checked && !c.enforcedInSearch)

        return (
          <div key={result.profile_id} className="lp-compare-row">
            <div className="lp-compare-head">
              <span className="lp-compare-swatch" style={{ background: result.color }} />
              <span className="lp-compare-name">
                {result.profile_name ?? result.profile_id}
              </span>
            </div>

            {/* A profile that failed is shown as failed. Dropping the row
                would make four profiles silently become three. */}
            {result.error ? (
              <p className="lp-compare-error">{result.error}</p>
            ) : (
              <>
                <dl className="lp-compare-metrics">
                  <div><dt>Distance</dt><dd>{metric(result, 'total_distance_m')} m</dd></div>
                  <div><dt>Max slope</dt><dd>{metric(result, 'max_slope_deg')}°</dd></div>
                  <div><dt>Cost</dt><dd>{metric(result, 'total_weighted_cost')}</dd></div>
                  <div><dt>Nodes</dt><dd>{metric(result, 'path_length_nodes')}</dd></div>
                </dl>

                {violated.length > 0 ? (
                  <p className="lp-compare-violated">
                    Violated: {violated.map((c) => c.name).join(', ')}
                  </p>
                ) : null}

                {unchecked.length > 0 ? (
                  <p className="lp-compare-unchecked">
                    Not checked: {unchecked.map((c) => c.name).join(', ')}
                  </p>
                ) : null}
              </>
            )}
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Adım 5: `profile-compare.css` oluştur**

```css
.lp-compare-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px; padding: 12px 14px; background: rgba(15, 23, 42, 0.45);
}

.lp-compare-run {
  width: 100%; border-radius: 7px;
  border: 1px solid rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.12);
  color: #bae6fd; font-size: 11px; padding: 6px 8px; cursor: pointer;
  margin-bottom: 10px;
}

.lp-compare-run:disabled { opacity: 0.45; cursor: default; }

.lp-compare-row {
  padding: 8px 0; border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.lp-compare-head { display: flex; align-items: center; gap: 7px; margin-bottom: 6px; }

.lp-compare-swatch {
  width: 11px; height: 3px; border-radius: 2px; display: inline-block;
}

.lp-compare-name { font-size: 12px; color: #e2e8f0; }

.lp-compare-metrics { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 14px; margin: 0; }
.lp-compare-metrics div { display: flex; justify-content: space-between; gap: 8px; }

.lp-compare-metrics dt {
  font-size: 9px; letter-spacing: 0.07em; text-transform: uppercase; color: #64748b;
}

.lp-compare-metrics dd {
  margin: 0; font-size: 11px; color: #cbd5f5; font-variant-numeric: tabular-nums;
}

.lp-compare-violated { margin: 6px 0 0; font-size: 10px; color: #f87171; }
/* Amber, not silence: a constraint that could not be tested is an open
   question, and the backend says so with checked:false. */
.lp-compare-unchecked { margin: 4px 0 0; font-size: 10px; color: #fbbf24; }
.lp-compare-error { margin: 4px 0 0; font-size: 10px; color: #f87171; }

.lp-compare-note { margin: 8px 0 0; font-size: 11px; color: #94a3b8; }
.lp-compare-warn { color: #fbbf24; }
```

- [ ] **Adım 6: `index.tsx` oluştur**

```tsx
import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { ProfileComparePanel } from './ProfileComparePanel'
import { profileOverlays } from './overlays'
import { useProfileCompare } from './useProfileCompare'

const OVERLAY_ID = 'profile-compare'

export function ProfileCompare() {
  const { results, run, busy, error } = useProfileCompare()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, profileOverlays(results))
    return () => unregister(OVERLAY_ID)
  }, [register, results, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Profile Comparison</p>
      <ProfileComparePanel results={results} run={run} busy={busy} error={error} />
    </section>
  )
}
```

- [ ] **Adım 7: `App.tsx`'e tek satırla bağla**

`<RightRailSlot>` içine `<ProfileCompare />`.
Import: `import { ProfileCompare } from './features/profile-compare'`

- [ ] **Adım 8: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 9: Elle kabul**

1. Başlangıç ve hedef seç → **Compare all profiles**
2. **Dört** profil listeleniyor: Balanced, Energy Saver, Fast Recon,
   Shadow Traverse — her biri kendi rengiyle
3. Haritada **dört ayrı rota** aynı anda çizili, renkleri paneldeki
   örneklerle eşleşiyor
4. Metrikler dolu: mesafe, maksimum eğim, ağırlıklı maliyet, düğüm sayısı
5. Bir profil kısıt ihlal ediyorsa **kırmızı "Violated"** satırı görünüyor
6. Simülasyon koşmayan bir kısıt varsa **sarı "Not checked"** satırı görünüyor
   — yeşil veya sessiz değil
7. Grid dışında bir hedef seçmeye çalış → 422 okunabilir bir hata olarak
   görünüyor

- [ ] **Adım 10: Commit**

```bash
git add frontend/src/api/compare.ts frontend/src/features/profile-compare/ frontend/src/App.tsx
git commit -m "feat(frontend): put four mission profiles side by side

/api/compare planned all four profiles against one start and goal and
nothing consumed it. Draws each route in the colour the backend assigned
and tabulates the metrics.

constraint_check is three-valued, not two: max_slope_deg is enforced
inside the search, the other three are path-dependent and reported with
checked:false when no simulation ran (scenarios.py:104-108). An unchecked
constraint reads amber, never as a pass. A profile that errored keeps its
row rather than vanishing, so four profiles cannot quietly become three."
```

---

### Görev 14: F6 — `mission-validation` · Gerçeklik kontrolü

`app.mission_reference` bütün varlık sebebi "karşılaştırılmak" olan modül ve
`/api/reference-missions` dışında hiçbir tüketicisi yok. Bu görev bizim rota
istatistiklerimizi Yutu-2 ve Pragyan'ın **yayınlanmış** rakamlarının yanına
koyar — künyeleriyle.

**Dürüstlük çekirdeği:** yanıttaki `note` alanı, oranların Ay gecesi uykusunu
içerdiğini ve **alt sınır** olduğunu söylüyor. Bu not ekranda görünmezse
karşılaştırma olduğundan daha iddialı okunur.

**Files:**
- Create: `frontend/src/api/missions.ts`
- Create: `frontend/src/features/mission-validation/index.tsx`
- Create: `frontend/src/features/mission-validation/useMissionValidation.ts`
- Create: `frontend/src/features/mission-validation/MissionValidationPanel.tsx`
- Create: `frontend/src/features/mission-validation/mission-validation.css`
- Modify: `frontend/src/App.tsx` (bir satır)

**Interfaces:**
- Consumes: `getJson`, `useMission()` (`planResult`)
- Produces:
  - `fetchReferenceMissions(signal): Promise<ReferenceMissions>`
  - `useMissionValidation(): { reference, stats, ourRateMPerDay, loading, error }`

- [ ] **Adım 1: `api/missions.ts` oluştur**

```ts
import { getJson } from './client'
import type { ReferenceMissions } from '../mission/types'

export async function fetchReferenceMissions(
  signal?: AbortSignal,
): Promise<ReferenceMissions> {
  return getJson<ReferenceMissions>('/reference-missions', signal)
}
```

- [ ] **Adım 2: `useMissionValidation.ts` oluştur**

```ts
import { useEffect, useState } from 'react'
import { fetchReferenceMissions } from '../../api/missions'
import { useMission } from '../../mission/MissionContext'
import type { ReferenceMissions, RouteStatistics } from '../../mission/types'

export function useMissionValidation() {
  const { planResult } = useMission()
  const [reference, setReference] = useState<ReferenceMissions | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    fetchReferenceMissions(controller.signal)
      .then((next) => {
        setReference(next)
        setLoading(false)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(cause instanceof Error ? cause.message : 'Reference missions unavailable')
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const stats =
    (planResult as { route_statistics?: RouteStatistics | null } | null)
      ?.route_statistics ?? null

  // Our own rate on the same footing as the published ones: metres per
  // calendar day, dormancy included. summary.total_elapsed_hours is the
  // simulated traverse clock, which already spans the waits.
  const summary = planResult?.summary ?? null
  const ourRateMPerDay =
    summary && summary.total_elapsed_hours > 0
      ? (summary.total_distance_km * 1000) / (summary.total_elapsed_hours / 24)
      : null

  return { reference, stats, ourRateMPerDay, loading, error }
}
```

- [ ] **Adım 3: `MissionValidationPanel.tsx` oluştur**

```tsx
import type { ReferenceMissions, RouteStatistics } from '../../mission/types'
import './mission-validation.css'

export function MissionValidationPanel({
  reference,
  stats,
  ourRateMPerDay,
  loading,
  error,
}: {
  reference: ReferenceMissions | null
  stats: RouteStatistics | null
  ourRateMPerDay: number | null
  loading: boolean
  error: string | null
}) {
  if (loading) return <p className="lp-val-note">Loading published mission figures…</p>
  if (error) return <p className="lp-val-note lp-val-warn">{error}</p>
  if (!reference) return null

  return (
    <div className="lp-val-card">
      <table className="lp-val-table">
        <thead>
          <tr>
            <th>Mission</th>
            <th>Distance</th>
            <th>Rate</th>
            <th>As of</th>
          </tr>
        </thead>
        <tbody>
          {reference.missions.map((mission) => (
            <tr key={mission.mission}>
              <td>{mission.mission}</td>
              <td>{(mission.total_distance_m / 1000).toFixed(2)} km</td>
              <td>{mission.lower_bound_rate_m_per_calendar_day.toFixed(1)} m/day</td>
              <td>{mission.as_of}</td>
            </tr>
          ))}
          {stats ? (
            <tr className="lp-val-ours">
              <td>This route</td>
              <td>{stats.waypoint_count} waypoints</td>
              <td>{ourRateMPerDay === null ? '—' : `${ourRateMPerDay.toFixed(1)} m/day`}</td>
              <td>simulated</td>
            </tr>
          ) : null}
        </tbody>
      </table>

      {/* The caveat travels with the numbers. Without it the rate column
          reads as a driving speed, which it is not. */}
      <p className="lp-val-caveat">{reference.note}</p>

      {stats ? (
        <>
          <h4 className="lp-val-subhead">Slope distribution</h4>
          <ul className="lp-val-hist">
            {stats.slope_histogram.map((bin) => {
              const share = stats.waypoint_count > 0 ? bin.count / stats.waypoint_count : 0
              return (
                <li key={`${bin.from_deg}-${bin.to_deg}`}>
                  <span className="lp-val-bin">
                    {bin.from_deg}–{bin.to_deg}°
                  </span>
                  <span className="lp-val-track">
                    <span className="lp-val-fill" style={{ width: `${share * 100}%` }} />
                  </span>
                  <span className="lp-val-count">{bin.count}</span>
                </li>
              )
            })}
          </ul>

          <h4 className="lp-val-subhead">Risk mix</h4>
          <ul className="lp-val-risk">
            {Object.entries(stats.risk_breakdown_pct).map(([level, pct]) => (
              <li key={level}>
                <span>{level}</span>
                <span>{pct.toFixed(1)}%</span>
              </li>
            ))}
          </ul>

          <p className="lp-val-temps">
            Surface temperature along route:{' '}
            {stats.min_surface_temp_c === null || stats.max_surface_temp_c === null
              ? 'unknown'
              : `${stats.min_surface_temp_c.toFixed(1)} °C to ${stats.max_surface_temp_c.toFixed(1)} °C`}
          </p>
        </>
      ) : (
        <p className="lp-val-note">Plan a route to compare it against these missions.</p>
      )}
    </div>
  )
}
```

- [ ] **Adım 4: `mission-validation.css` oluştur**

```css
.lp-val-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px; padding: 12px 14px; background: rgba(15, 23, 42, 0.45);
}

.lp-val-table {
  width: 100%; border-collapse: collapse; font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.lp-val-table th {
  text-align: right; font-size: 9px; letter-spacing: 0.07em;
  text-transform: uppercase; color: #64748b; padding: 3px 5px;
}

.lp-val-table th:first-child, .lp-val-table td:first-child { text-align: left; }

.lp-val-table td {
  text-align: right; padding: 4px 5px; color: #cbd5f5;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
}

.lp-val-ours td { color: #38bdf8; }

.lp-val-caveat {
  margin: 9px 0 0; font-size: 10px; line-height: 1.5; color: #fbbf24;
}

.lp-val-subhead {
  margin: 13px 0 6px; font-size: 9px; letter-spacing: 0.1em;
  text-transform: uppercase; color: #64748b; font-weight: 600;
}

.lp-val-hist { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; }

.lp-val-hist li {
  display: grid; grid-template-columns: 62px 1fr 34px; align-items: center; gap: 8px;
}

.lp-val-bin { font-size: 10px; color: #94a3b8; font-variant-numeric: tabular-nums; }

.lp-val-track {
  height: 6px; border-radius: 999px; background: rgba(148, 163, 184, 0.16); overflow: hidden;
}

.lp-val-fill { display: block; height: 100%; background: #60a5fa; }

.lp-val-count {
  font-size: 10px; text-align: right; color: #cbd5f5; font-variant-numeric: tabular-nums;
}

.lp-val-risk { list-style: none; margin: 0; padding: 0; display: grid; gap: 3px; }

.lp-val-risk li {
  display: flex; justify-content: space-between; font-size: 11px; color: #cbd5f5;
}

.lp-val-temps { margin: 11px 0 0; font-size: 11px; color: #94a3b8; }
.lp-val-note { margin: 9px 0 0; font-size: 11px; color: #94a3b8; }
.lp-val-warn { color: #fbbf24; }
```

- [ ] **Adım 5: `index.tsx` oluştur**

```tsx
import { MissionValidationPanel } from './MissionValidationPanel'
import { useMissionValidation } from './useMissionValidation'

export function MissionValidation() {
  const state = useMissionValidation()
  return (
    <section className="rail-section">
      <p className="panel-kicker">Reality Check</p>
      <MissionValidationPanel {...state} />
    </section>
  )
}
```

- [ ] **Adım 6: `App.tsx`'e tek satırla bağla**

`<RightRailSlot>` içine `<MissionValidation />`.
Import: `import { MissionValidation } from './features/mission-validation'`

- [ ] **Adım 7: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 8: Elle kabul**

1. Panel açıldığında Yutu-2 ve Pragyan satırları görünüyor — mesafe, oran, tarih
2. **`note` metni ekranda** ve sarı: "Published mission figures, not model
   output. Rates include lunar-night dormancy and are lower bounds on driving
   rate." Bu görünmüyorsa görev tamamlanmamıştır
3. Rota üret → "This route" satırı ekleniyor
4. Eğim histogramı çubukları dolu; sayıların toplamı `waypoint_count`'a eşit
5. Risk karışımı yüzdeleri görünüyor
6. Yüzey sıcaklık aralığı görünüyor; `null` ise "unknown" yazıyor, `0.0 °C` değil

- [ ] **Adım 9: Commit**

```bash
git add frontend/src/api/missions.ts frontend/src/features/mission-validation/ frontend/src/App.tsx
git commit -m "feat(frontend): compare this route against flown missions

app.mission_reference exists to be compared against and had no consumer
outside its own tests. Puts Yutu-2's and Pragyan's published distances and
rates beside this route's own statistics, with the as-of dates.

The response's `note` is rendered, not summarised away: those rates
include lunar-night dormancy and are lower bounds on a driving rate, so
without the caveat the column reads as a speed comparison it cannot
support."
```

---

### Görev 15: F4 — `ros-showcase` · Entegrasyon vitrini

Faz 4 gerçek: `lunapath_ros` bir `PlanTraverse` action server, bir `grid_map`
yayıncısı ve bir `pose_monitor` içeriyor. Ama **frontend'e açılan bir HTTP
yüzeyi yok** — rosbridge/websocket kurulu değil. Bu yüzden bu modül canlı
bağlantı iddia etmez; ne inşa edildiğini künyeleriyle gösterir.

**Files:**
- Create: `frontend/src/features/ros-showcase/index.tsx`
- Create: `frontend/src/features/ros-showcase/RosShowcasePanel.tsx`
- Create: `frontend/src/features/ros-showcase/ros-showcase.css`
- Modify: `frontend/src/App.tsx` (bir satır)

**Interfaces:**
- Consumes: hiçbir uç (statik içerik)
- Produces: `RosShowcase` bileşeni

- [ ] **Adım 1: İçeriği kaynaktan doğrula**

Panelde yazacak her şeyin repoda karşılığı olmalı. Şunları çalıştır ve çıktıyı
not al:

```bash
ls lunapath_ros/lunapath_ros/
ls lunapath_msgs/action/ lunapath_msgs/msg/
ls lunapath_ros/launch/ lunapath_ros/config/
ls scripts/nav2_baseline.py scripts/record_plan.sh
```

Expected: `conversions.py`, `grid_publisher.py`, `planner_node.py`,
`pose_monitor.py`; `PlanTraverse.action`; `Corridor.msg`, `PlanMetrics.msg`,
`MissionWeights.msg`, `ReplanTrigger.msg`; `lunapath.launch.py`,
`lunapath.rviz`; iki script.

**Listede olmayan hiçbir şey panele yazılmaz.** Bir dosya yoksa o satırı çıkar.

- [ ] **Adım 2: `RosShowcasePanel.tsx` oluştur**

```tsx
import './ros-showcase.css'

interface Item {
  name: string
  detail: string
  path: string
}

// Every entry names a file that exists in this repository. Verified in
// step 1 -- nothing here is aspirational.
const NODES: Item[] = [
  {
    name: 'PlanTraverse action server',
    detail: 'Thin shell over the same planner /api/plan calls. Nav2 error-code semantics.',
    path: 'lunapath_ros/planner_node.py',
  },
  {
    name: 'grid_map publisher',
    detail: 'Publishes the cost layers as grid_map_msgs/GridMap for RViz.',
    path: 'lunapath_ros/grid_publisher.py',
  },
  {
    name: 'Pose monitor',
    detail: 'Consumes nav_msgs/Odometry and runs the same evaluate_pose the HTTP shell runs.',
    path: 'lunapath_ros/pose_monitor.py',
  },
  {
    name: 'Message assembly',
    detail: 'Message packing only — the geometry lives in app.grid_frame.',
    path: 'lunapath_ros/conversions.py',
  },
]

const INTERFACES: Item[] = [
  { name: 'PlanTraverse.action', detail: 'Goal, feedback and result contract.', path: 'lunapath_msgs/action/' },
  { name: 'Corridor.msg', detail: 'The same corridor this cockpit draws, over ROS.', path: 'lunapath_msgs/msg/' },
  { name: 'PlanMetrics.msg', detail: 'Planner metrics.', path: 'lunapath_msgs/msg/' },
  { name: 'MissionWeights.msg', detail: 'The four cost weights.', path: 'lunapath_msgs/msg/' },
  { name: 'ReplanTrigger.msg', detail: 'Trigger id and detail.', path: 'lunapath_msgs/msg/' },
]

const TOOLING: Item[] = [
  { name: 'Launch + RViz scene', detail: 'One command brings the stack up.', path: 'lunapath_ros/launch/lunapath.launch.py' },
  { name: 'rosbag2 recording', detail: 'Records one plan run.', path: 'scripts/record_plan.sh' },
  { name: 'Nav2 baseline', detail: 'Geometric baseline vs. LunaPath A*.', path: 'scripts/nav2_baseline.py' },
]

function Group({ title, items }: { title: string; items: Item[] }) {
  return (
    <>
      <h4 className="lp-ros-subhead">{title}</h4>
      <ul className="lp-ros-list">
        {items.map((item) => (
          <li key={item.path + item.name}>
            <span className="lp-ros-name">{item.name}</span>
            <span className="lp-ros-detail">{item.detail}</span>
            <code className="lp-ros-path">{item.path}</code>
          </li>
        ))}
      </ul>
    </>
  )
}

export function RosShowcasePanel() {
  return (
    <div className="lp-ros-card">
      {/* Stated first and plainly. The panel describes a real ROS 2 package
          that this browser is not talking to, and pretending otherwise
          would be the one dishonest thing in the cockpit. */}
      <p className="lp-ros-disclaimer">
        Not a live connection. These run in a ROS 2 Jazzy environment beside the
        backend; the browser has no bridge to them.
      </p>

      <Group title="Nodes" items={NODES} />
      <Group title="Interfaces" items={INTERFACES} />
      <Group title="Tooling" items={TOOLING} />

      <p className="lp-ros-note">
        The core is shell-independent: <code>backend/app/</code> imports neither
        rclpy nor fastapi, so the HTTP API and the ROS 2 nodes call the same
        functions and cannot drift apart.
      </p>
    </div>
  )
}
```

- [ ] **Adım 3: `ros-showcase.css` oluştur**

```css
.lp-ros-card {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px; padding: 12px 14px; background: rgba(15, 23, 42, 0.45);
}

.lp-ros-disclaimer {
  margin: 0 0 11px; padding: 7px 9px; border-radius: 7px;
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.28);
  font-size: 10px; line-height: 1.5; color: #fbbf24;
}

.lp-ros-subhead {
  margin: 12px 0 6px; font-size: 9px; letter-spacing: 0.1em;
  text-transform: uppercase; color: #64748b; font-weight: 600;
}

.lp-ros-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }

.lp-ros-list li { display: flex; flex-direction: column; gap: 2px; }

.lp-ros-name { font-size: 11px; color: #e2e8f0; }
.lp-ros-detail { font-size: 10px; line-height: 1.45; color: #94a3b8; }

.lp-ros-path {
  font-family: ui-monospace, monospace; font-size: 9px; color: #64748b;
}

.lp-ros-note {
  margin: 13px 0 0; font-size: 10px; line-height: 1.5; color: #94a3b8;
}

.lp-ros-note code { color: #cbd5f5; }
```

- [ ] **Adım 4: `index.tsx` oluştur**

```tsx
import { RosShowcasePanel } from './RosShowcasePanel'

export function RosShowcase() {
  return (
    <section className="rail-section">
      <p className="panel-kicker">ROS 2 Integration</p>
      <RosShowcasePanel />
    </section>
  )
}
```

- [ ] **Adım 5: `App.tsx`'e tek satırla bağla**

`<LeftRailSlot>` içine `<RosShowcase />`.
Import: `import { RosShowcase } from './features/ros-showcase'`

- [ ] **Adım 6: Derlemeyi doğrula**

Run: `cd frontend && npm run typecheck && npm run lint && npm run build`
Expected: temiz

- [ ] **Adım 7: Elle kabul**

1. Panel açılıyor; **sarı uyarı en üstte** ve "Not a live connection" diyor
2. Listelenen her dosya yolu repoda **gerçekten var** (Adım 1'in çıktısıyla
   karşılaştır)
3. Panelde hiçbir yerde canlı topic, canlı sayı veya bağlantı durumu
   göstergesi **yok**

- [ ] **Adım 8: Commit**

```bash
git add frontend/src/features/ros-showcase/ frontend/src/App.tsx
git commit -m "feat(frontend): show the ROS 2 integration without claiming a live link

lunapath_ros is real -- a PlanTraverse action server, a grid_map publisher
and a pose monitor -- but there is no rosbridge, so the browser cannot
talk to any of it. This names what was built and where it lives, and says
in the first line that it is not a live connection. Every path listed was
checked against the repository; nothing here is aspirational."
```

---

## Spec kapsam denetimi

Spec'in her gereksinimi bir göreve düşüyor mu?

| Spec bölümü | Görev |
|---|---|
| F0 iskelet | 1, 2, 3, 4, 5 |
| F1 `layer-provenance` | 6 |
| F1–2 `cost-explain` | 7 |
| F2a `corridor` | 8 |
| F2b `replan` | 9 |
| F3 `time-axis` | 10, 11 |
| F7 `pose-loop` | 12 |
| F5 `profile-compare` | 13 |
| F6 `mission-validation` | 14 |
| F4 `ros-showcase` | 15 |
| `MissionContext` | 5 |
| Yuva mekanizması | 5 |
| `OverlayLayer` sözleşmesi | 4 |
| `mission/geo.ts` | 3 |
| Modül dosya sözleşmesi | 6–15 (her biri aynı beş dosya deseni) |

Tuzaklar:

| Tuzak | Nerede ele alınıyor |
|---|---|
| T1 — `astar_metrics` enerji/gölge `null` | Görev 2, Adım 1 |
| T2 — `shadow` ≠ `shadow_ratio` | Görev 7, `LABELS` yorumu |
| T3 — `cost_breakdown`'da `null` = GEÇİLEMEZ | Görev 7, Adım 1 ve 3 |
| T4 — `path_pixels` fine, `path_pixels_coarse` coarse | Görev 11, `overlays.ts` |
| T5 — `corridor.waypoints` CRS metre | Görev 3 ve 8 |
| T6 — küp sıralaması slice-major | Görev 10, `fetchSeriesCube` |
| T7 — `shadow_model.model === "static"` | Görev 11, Adım 3 ve 8 |
| T8 — `format=f32` kullan | Mevcut `fetchLayer` zaten böyle; yeni kod `getFloat32` kullanıyor (Görev 1) |
| T9 — koridor 404 | Görev 12, Adım 9 (madde 9) |
| T10 — boş senaryo listesi | Kapsam dışı: hiçbir modül `/api/scenarios` tüketmiyor |
| T11 — validity dört değerli | Görev 6, Adım 3 |
| T12 — koşullu başlıklar/`null` alanlar | Görev 6, `formatRange` ve `validity` dalları |

**Bulunan ve düzeltilen iki hata:**

1. Görev 12'nin `PoseEstimate` alan adları yanlıştı (`x`/`y`/serbest `source`).
   Gerçek şema (`pose.py:80-113`) sekiz **zorunlu** alan taşıyor: `x_m`, `y_m`,
   `heading_deg`, `covariance_m`, `heading_covariance_deg`, `timestamp_utc`,
   `source` (beş değerli enum), `distance_travelled_m`. Eksik alan 422 döndürürdü.
2. Görev 12, `features/replan/triggers.ts`'i import ediyordu — bir modülün başka
   bir modülün iç dosyasına uzanması global kısıtı çiğniyor. Paylaşılan
   tetikleyici künyesi `mission/triggers.ts`'e taşındı.

---

## Yürütme notları

- **Görev 1–5 seri.** İskelet bitmeden hiçbir faz modülü başlayamaz.
- **Görev 6'dan sonra paralel:** 7, 8, 10, 13, 14, 15 birbirinden bağımsız.
  9 ve 12 → 8'e bağlı (`corridor_id`). 11 → 10'a bağlı.
- **Görev 11 ön koşulu:** `python scripts/build_horizon_cache.py` bir kez
  çalıştırılmış olmalı, yoksa kabul kriteri doğrulanamaz.
- **`App.tsx` çakışması:** Görev 6–15'in her biri `App.tsx`'e bir import ve bir
  JSX satırı ekliyor. Paralel yürütülürlerse bu satırlar çakışır — çakışma
  çözümü her iki satırı da tutmaktır, hiçbiri diğerini geçersiz kılmaz.
- **Ekip belgesi:** `docs/frontend/FRONTEND_YAPISI.md` bu yapının dışarıdan
  anlatımı. Görev 5 bittiğinde arkadaşlara gönderilebilir — o noktada yuvalar
  ve `MissionContext` gerçek.
