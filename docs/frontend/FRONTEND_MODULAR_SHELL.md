# Frontend modular shell — ownership contract

**Status:** in force from `feature/frontend-modular-shell`.
**Companion:** `FRONTEND_YAPISI.md` (team structure note). This document is what
we actually implemented; where the two differ, the differences are listed at the
end with the evidence for each.

This exists for one reason: to stop unrelated features colliding in the same
four files. Everything below is about *where code goes*, not about how the
cockpit looks.

---

## 1. The shared files, and what may still be added to them

| File | Rule |
|---|---|
| `App.tsx` | Shared composition only: providers, the five slot hosts, and the cockpit panels that already live there. No feature state, no feature markup. |
| `MapCanvas.tsx` | Shared renderer plus the one generic overlay seam. No feature-specific drawing, ever. |
| `App.css` | Legacy and global base only. New feature styling goes in the feature's own stylesheet. |
| `api.ts` | Frozen. Existing endpoints keep working; **no new endpoint family is added here**. |
| `shell/shell.css` | Only rules that belong to no single feature and no base style — where two independently-owned things share screen space. Keep it small. |

Adding a feature should touch `features/registry.ts` and nothing else in this
table.

---

## 2. Directory layout

```
frontend/src/
├─ App.tsx            shared composition
├─ App.css            legacy/global base
├─ MapCanvas.tsx      shared 2-D renderer + overlay seam
├─ TerrainView3D.tsx  shared 3-D renderer
├─ api.ts             legacy endpoint client (frozen)
│
├─ mission/           MissionContext.tsx  types.ts  selectors.ts  geo.ts
├─ api/               client.ts  assistant.ts   (one file per endpoint family)
├─ net/               typed fetchers for the newer endpoint families
├─ grid/              grid frame: pixel <-> projected metres
├─ overlay/           types.ts  OverlayContext.tsx  useOverlays.ts  draw2d.ts
├─ intent/            one cross-feature channel -- see §14
├─ shell/             FeatureHost.tsx  slots.tsx  shell.css
└─ features/
   ├─ registry.ts
   └─ assistant/      index.tsx  useAssistant.ts  ChatPanel.tsx  aiContext.ts  assistant.css
```

**Dependency direction is binding.**

```
features  ->  mission, api, net, grid, overlay, intent   (allowed)
shell, registry  ->  feature entrypoints                 (allowed)
App  ->  providers, slots                                (allowed)

mission  ->  features                      FORBIDDEN
overlay  ->  features                      FORBIDDEN
api      ->  features                      FORBIDDEN
intent   ->  features                      FORBIDDEN
```

`net/` and `grid/` were already peers that features import; they are written
down here because the list read as exhaustive and was not.

A feature is imported from outside **only** through its `index.tsx`. Nothing
reaches into `features/<name>/` internals.

---

## 3. Feature ownership

`features/<name>/` belongs to whoever owns that feature. Typical contents:

| File | Required | What |
|---|---|---|
| `index.tsx` | yes | The single exported component |
| `use<Name>.ts` | yes | Feature state and fetches. Not in `App.tsx`. |
| UI components | as needed | |
| `<name>.css` | as needed | Feature-local styling, `.lp-<name>-` prefix for new selectors |
| overlay commands | optional | What it draws on the map |

Reviewers do not rewrite another feature's internals.

**Mission state goes in MissionContext. Feature state stays in the feature.**
Assistant messages, drafts, open/closed state, panel-local UI state — all of
that lives in the feature's own hook. `MissionContext` publishes what `App.tsx`
already owns; it is not a store for new state.

---

## 4. `features/registry.ts` and the five slots

```ts
export const FEATURES: readonly FeatureRegistration[] = [
  { id: 'assistant', slot: 'globalOverlay', Component: Assistant },
]
```

| Slot | Where |
|---|---|
| `leftRail` | Left rail, below the existing controls |
| `rightRail` | Right rail, below Mission Snapshot |
| `bottomDock` | The strip under the map stage |
| `canvasOverlay` | Absolutely-positioned HUD layer over the map |
| `globalOverlay` | Application-level floating utilities |

`FeatureHost` renders a fragment and nothing else, so an **empty slot produces
no element, no wrapper and no height**. That is what lets all five hosts sit in
`App.tsx` permanently without changing the layout.

The registry is deliberately boring: a static array, evaluated at module load.
No dynamic discovery, no manifests, no lazy-loading framework, no service
locator. Keep it that way.

`globalOverlay` is our addition. A floating, application-level utility is
neither a rail panel nor a layer on the map, and forcing one into either is how
the assistant ended up wired directly into `App.tsx` in the first place.

---

## 5. `useMission()` — the published mission

```ts
{
  gridMeta:        { rows, cols, resolutionM } | null
  roverId:         string
  weights:         { w_slope, w_energy, w_shadow, w_thermal }
  start:           [row, col] | null
  goal:            [row, col] | null
  planResult:      PlanResponse | null      // raw, uncropped
  selectedCell:    [row, col] | null        // always null today - see below
  activeViewMode:  ViewModeId               // a UI id, NOT a layer name
  dimension:       '2d' | '3d'
}
```

Read-only. No setter crosses this boundary in this pass — see §10.

`gridMeta` comes from the bootstrap elevation layer's `X-Layer-Resolution-M`,
which is the *effective* pitch of the returned grid and is unconditional. It is
memoised on the three numbers, so its identity survives unrelated renders.

### `selectedCell` is null, on purpose

This cockpit has no control that selects a cell **as a cell**. Start and goal
are placed by mode-scoped clicks and mean "route from here" / "route to here".
The hover cell is a pointer position that clears on mouse-leave.

Publishing either one as "the cell the operator selected" would tell every
future feature that a generic selection exists when none does. When a real
selection control is built, this field carries it.

A feature that wants the analysis focus the assistant uses asks for it by name:

```ts
import { selectStableAnalysisCell } from '../../mission/selectors'
const focus = selectStableAnalysisCell(mission.start, mission.goal)  // goal, then start, else null
```

**Never the hover cell.** A suggestion chip that appears and vanishes under the
operator's hand is worse than no chip, and an answer that depends on where the
mouse happened to rest is not an answer. This rule was paid for once already.

### `useFocusTelemetry()` is a separate hook, and not the selected cell

```ts
useFocusTelemetry(): { row, col, lat, lon, altitudeM, thermalC, resolutionM, spanKm }
```

This is the map's LAT/LON/ALT/TMP readout. It follows `hoverPoint ?? goal ??
start`, and during route playback it follows the animating waypoint — a new
value every 33 ms. It is **not** the telemetry of any stable selection, and it
is a separate context so that reading the mission does not drag a feature into
that churn.

A feature that needs a specific cell's telemetry fetches that cell:
`fetchCellTelemetry(row, col)`.

### `activeViewMode` is not a layer name

Three of the seven ids differ from what `fetchLayer` wants:

| `activeViewMode` | backend layer |
|---|---|
| `surface` | `elevation` |
| `shadow` | `shadow_ratio` |
| `traversability` | `traversable` |

Passing the published value to `fetchLayer` gets a 404 or, worse, a plausible
different grid. The mapping stays private to `App.tsx`. If a shared mapper is
ever needed, add a typed one explicitly — never let a feature pass
`activeViewMode` straight through.

---

## 6. Overlay contract

Features do not draw on `MapCanvas`. They publish commands.

```tsx
const overlays = useOverlays()

// MEMOISED. An array rebuilt every render re-runs the effect forever.
const commands = useMemo<OverlayCommand[]>(() => [
  { kind: 'polyline', id: 'route', points: cells, style: { color: '#38bdf8', widthPx: 3 } },
], [cells])

useEffect(() => overlays.register('corridor', commands), [overlays, commands])
```

`register` has a stable identity and returns its cleanup; returning it from the
effect is what removes the commands on unmount. A feature owns its own entry and
no other. Registrations are token-scoped internally, so a stale cleanup arriving
after a re-registration cannot erase the live entry.

Four kinds: `polyline`, `ribbon` (variable-width band), `points`, `field`
(scalar over the grid). `field` takes a **data ramp**, not a `colorFor`
callback — a function property is a new identity every render, which is exactly
what makes the registration effect loop.

**Coordinates are always fine-grid `{row, col}`.** Not CRS metres, not coarse
pixels, not canvas pixels. This is what will let the same command list feed a
3-D renderer later without features changing.

`null` in a `field` is left unpainted. It is never rendered as zero.

---

## 7. Coordinates

`mission/geo.ts` is the fine-grid ↔ canvas-pixel boundary, and the only place
that arithmetic is written down. Cells map to their **centre**, not their corner.

The 3-D world transform is **not** here: `cellToWorldXZ` in `TerrainView3D.tsx`
stays where the row-axis reasoning sits beside the mesh it applies to. There is
no second implementation of either conversion — that is the rule, not "all
conversions live in geo.ts".

---

## 8. API families

```
api/client.ts       BASE, ApiError            <- shared primitives
api/assistant.ts    the AI chat endpoint      <- one family, one file
api.ts              legacy endpoints          <- frozen
```

New families go in `api/<family>.ts` and import `api/client.ts`. They must not
import `api.ts`, or "do not add to api.ts" becomes a rule nobody can follow.
Planned: `api/corridor.ts`, `api/replan.ts`, `api/timeAxis.ts`,
`api/profileCompare.ts`.

One fetch implementation. Do not add a second client, a wrapper layer, or a
request framework.

---

## 9. The AI evidence boundary

`MissionContext` publishes the raw `PlanResponse` because deterministic features
need it whole. **The assistant must never send it that way.**

```
useMission()
    -> features/assistant/aiContext.ts   (AiMissionSnapshot, sanitizePlanForAi)
    -> POST /api/ai/chat
    -> backend K1 sanitizer / AnalysisEnvelope
    -> K4
```

The snapshot drops the waypoint geometry and carries named quantities with
units. Anything that reaches the model goes through it. Moving files must never
widen this path.

Rules that hold regardless of what the frontend does:

- `astar_metrics.total_energy_wh` and `total_shadow_hours` are **always null**.
  Real energy is `summary.total_energy_consumed_wh`; continuous shadow is
  `summary.max_continuous_shadow_h`. `api.ts` types both as `null`-only, so
  reaching for one is a type error rather than a plausible zero.
- `summary.total_shadow_exposure` is **excluded from the assistant.**
  `simulation.py` accumulates it as `shadow_ratio * step_time_h` — a weighted
  exposure integral, not a duration — and no unit is stated in the contract. A
  number whose unit cannot be stated cannot be stated.
- Cost component `shadow` and grid layer `shadow_ratio` are different things.
- `cost_breakdown` `null` means **impassable**, not "no data".
- Validity is ordered `SYNTHETIC < DERIVED < MODEL < MEASURED`. There is no
  `MODELED`. Unknown stays unknown — never assume `MEASURED`.
- `X-Layer-Min`, `X-Layer-Max` and `X-Layer-Validity` are conditional headers
  and may be absent; `X-Layer-Resolution-M` is not.
- Fetch layers with `format=f32`. The JSON path is capped at 65 536 cells; the
  binary path is not, and 500×500 float32 is 1 MB.
- `plan-4d` `path_pixels` is fine grid; `path_pixels_coarse` is coarse. Draw
  with `path_pixels`.
- `corridor.waypoints` are CRS metres, not pixels. Corridors are held in memory,
  32 at most; an unknown `corridor_id` is a 404.
- Time series needs the horizon cache. Without it `shadow_model.model ===
  "static"` and animating it would be theatre.
- `backend/data/scenarios/` is empty, so `/api/scenarios` returns `[]`.

### Honesty rules

1. A number labelled `UNCALIBRATED` or `SYNTHETIC` is never shown unlabelled.
2. A check that could not run is never shown as clean; `skipped` stays visible.
3. A `null` number is never drawn as 0.
4. A static model is never presented as animated.

---

## 10. Mutation

`MissionContext` exposes no `setStart` / `setGoal` in this pass.

The only start/goal writes today are inside `handleCellClick`, which also
invalidates the plan, the plan error and the playback step. A second mutation
path that reproduced some of that from memory would be a different action
wearing the same name. Nothing consumes these yet; when something does, expose
the real action rather than a copy of its side effects.

---

## 11. Assistant placement

The assistant is a `globalOverlay` feature, not a right-rail panel. It is opened
over the mission and closed again, and it must keep working with both rails
collapsed.

Two cross-file contracts hold it together, both easy to break silently:

1. **`.chat-window` and `.is-open` are published class names.** `shell.css`
   moves the toast stack clear of an open assistant with
   `.chat-window.is-open ~ .toast-stack`. Renaming either class inside
   `assistant.css` breaks toast placement with no type error.
2. **`GlobalOverlaySlot` must stay ahead of `.toast-stack` in `App.tsx`**, as a
   sibling. The general sibling combinator only looks forward.

A sibling combinator rather than `:has()` because vite's target here is the
default `modules` baseline — chrome87, safari14, firefox78 — and `:has()` lands
in chrome105 / safari15.4 / firefox121. It also needs no state in `App.tsx` and
runs no JavaScript.

---

## 12. Differences from `FRONTEND_YAPISI.md`

| # | The note says | We do | Why |
|---|---|---|---|
| 1 | Four slots; mount with `<RightRailSlot><Assistant /></RightRailSlot>`, one line in `App.tsx` per module | Five slots; `features/registry.ts` holds the mounting and the slots take no children | Removes `App.tsx` from the per-feature conflict surface entirely. `globalOverlay` added for floating utilities. |
| 2 | `cellTelemetry` = the selected cell's raw telemetry | Not published. `useFocusTelemetry()` publishes the pointer/playback readout under its own name | The value described does not exist in this app: `focusTelemetry` follows the pointer and the playback head. Publishing it as `cellTelemetry` beside `selectedCell` would be a name that lies. |
| 3 | `selectedCell` = the cell the user clicked | Always `null`; the goal-then-start rule is `selectStableAnalysisCell` | No control selects a cell as a cell. Start and goal are routing endpoints. See §5. |
| 4 | `api.ts` and `App.css` untouched | Both edited **once**, to move assistant code out | The note's rule is about *new* work. After this pass both are frozen exactly as it intends. |
| 5 | Real shadow = `summary.total_shadow_exposure` / `max_continuous_shadow_h` | Assistant excludes `total_shadow_exposure` | `simulation.py:386` accumulates `shadow_ratio * step_time_h`: a weighted integral, not a duration, with no stated unit. See §9. |
| 6 | "`api.ts` types the null metrics wrong" | No change needed | Stale against this branch: `api.ts` already types both as `null`-only. |
| 7 | Slots live under `mission/` | Slots live under `shell/` | `mission/` stays state and coordinates only. |

Not differences: the note defers `draw3d.ts` and the `App.tsx` refactor, and so
do we.

---

## 13. Deliberately left for later

- Existing cockpit panels stay in `App.tsx`. Migrating them feature-by-feature
  is future UI work, not part of establishing the boundary.
- Legacy `api.ts` endpoints are not moved.
- Route, marker and terrain rendering in `MapCanvas.tsx` is unchanged; only
  feature overlays go through the new seam.
- No 3-D overlay renderer. The command contract is designed for one; `draw3d.ts`
  comes when a feature needs it.
- No test framework was added.

---

## 14. Cross-feature intent

One channel, `intent/`, and it exists for one problem: the mission report has to
be able to hand the assistant a question, and every other route was worse.

- **`MissionActions`** publishes writers for mission state. An `askAssistant`
  there would make `mission/` the owner of an inter-feature message bus wearing
  the mission's name, against §12 row 7 ("`mission/` stays state and coordinates
  only").
- **`shell/`** is imported *by* nothing below it: `shell → registry → features`
  is the direction, and a channel there reverses it.
- **A `CustomEvent` or `window` bus** is invisible to the type system, and with
  no jsdom (§13) nothing could test it.

### The contract

`AssistantAsk` carries `{ id, question, origin }` and nothing else. Two hooks,
split the way `useMission()` and `useMissionActions()` are:

| Hook | Who calls it | What it gets |
|---|---|---|
| `useAskAssistant()` | the producing feature | a function taking `(question, origin)` |
| `useAssistantAsk()` | the assistant | the pending ask, or null |

Four properties are load-bearing, and each is pinned by
`backend/test_frontend_ask_assistant_contract.py`:

1. **Text only.** Nothing in `intent/` may fetch, and the assistant's `send()`
   guard (`!question || pending || !levelChosen`) is untouched. A feature can
   suggest a question; only the operator asks it.
2. **One-way.** There is no `consume` or `clear`. The consumer tracks the last
   id it applied, so a producer cannot replay, retract, or observe delivery.
3. **`id`, not text.** The operator asking the same thing twice is two asks.
4. **A closed `origin` union.** A new producer is a deliberate edit to
   `intent/types.ts`.

### The amendment rule

This folder holds **one** ask type. A second channel — a different message, a
different consumer — is an amendment to this section, not another file dropped
in `intent/`. That is what keeps it from becoming the service-locator
`features/registry.ts` refuses to be.
