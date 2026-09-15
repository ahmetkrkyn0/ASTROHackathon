import { useSyncExternalStore } from 'react'
import {
  PLAN_REQUEST_CONTRIBUTORS,
  mergeContributedFields,
  type ConstraintState,
} from './contributors'

/**
 * Where advanced constraint state lives, which is deliberately not App.tsx.
 *
 * App builds the mission snapshot every render from a fixed list of fields;
 * adding a constraint there would mean editing that file for each of the seven
 * the backend now accepts, and every reader of the mission would re-render
 * when a slider moved. This is a module store instead: the panels write to it,
 * App reads it at plan time, and the identity hook subscribes.
 *
 * useSyncExternalStore rather than a context, because there is no tree to
 * scope this to -- the constraints belong to the mission, not to a subtree --
 * and because App needs a plain synchronous read at the moment it issues the
 * request, which a context cannot give it.
 */

const state = new Map<string, ConstraintState>()
const listeners = new Set<() => void>()

/**
 * Cached so getSnapshot returns a stable reference between changes.
 * useSyncExternalStore compares snapshots by identity and would loop forever
 * on a fresh object each call.
 */
let snapshot: Record<string, unknown> = {}

/**
 * The same caching rule for the by-constraintKey view.
 *
 * Rebuilt in `rebuild()` rather than computed per call: `useSyncExternalStore`
 * compares snapshots by identity, so a getter that returned a fresh object
 * would re-render forever. Same hazard the overlay contract documents for
 * `register(featureId, commands)`.
 */
let keySnapshot: Record<string, unknown> = {}

function rebuild(): void {
  let fields: Record<string, unknown> = {}
  for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
    const current = state.get(contributor.id) ?? { enabled: false }
    // No context: this is the 2-D path. Every contributor whose field the
    // 2-D planner would accept and then ignore returns null here, which is
    // where that guard actually bites.
    const produced = contributor.fields(current)
    if (produced === null) continue
    // mergeContributedFields, not Object.assign. A contributor may nest under
    // `weights`, and a flat assign would replace the four weights the cockpit
    // has always sent with a one-key object -- re-planning the route on a
    // single criterion while the sliders still read four.
    fields = mergeContributedFields(fields, produced)
  }
  snapshot = fields
  keySnapshot = buildConstraintKeys()
}

export function setConstraint(id: string, next: ConstraintState): void {
  state.set(id, next)
  rebuild()
  for (const listener of listeners) listener()
}

export function getConstraint(id: string): ConstraintState {
  const held = state.get(id)
  if (held && held.value !== undefined) return held
  // A constraint with no value of its own falls back to the control's
  // starting point, whether or not anything has been stored for it. Doing
  // this only for an absent entry would lose the default the first time
  // something wrote `{ enabled: false }` on its own, and switching the
  // constraint on afterwards would hand the backend an undefined where a
  // number belongs.
  const control = PLAN_REQUEST_CONTRIBUTORS.find((entry) => entry.id === id)?.control
  const initial =
    control?.kind === 'number' || control?.kind === 'choice' ? control.initial : undefined
  return { enabled: held?.enabled ?? false, value: initial }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function getSnapshot(): Record<string, unknown> {
  return snapshot
}

/**
 * The fields to merge into a plan request. Empty when every constraint is off,
 * which is the whole point: the body is then byte-for-byte the old one.
 */
export function readPlanConstraints(): Record<string, unknown> {
  return snapshot
}

/**
 * The same state, addressed the way the 4-D builder addresses it.
 *
 * `readPlanConstraints` returns finished request FIELDS for the 2-D path --
 * `risk_alpha`, `weights` -- because the store is that path's builder. The
 * 4-D path has its own builder (`applyPlanRequestContributors`) and wants the
 * layer below: the operator's raw settings keyed by `constraintKey`, which it
 * then folds in itself.
 *
 * The two must not become two stores. Before this, 4-D constraints lived in a
 * `useState` inside the time-axis hook while 2-D constraints lived here, so
 * `risk` was settable in one place and read in the other, and the value never
 * crossed. One store, two readers.
 *
 * A constraint that is OFF produces NO KEY -- not `false`, not the control's
 * initial value. `constraintStateFrom` reads absence as off, so this is the
 * same non-regression rule as everywhere else, restated at the one seam that
 * could break it.
 */
export function readConstraintKeys(): Record<string, unknown> {
  return keySnapshot
}

/** The same object, for anything that must re-render when it changes. */
export function useConstraintKeys(): Record<string, unknown> {
  return useSyncExternalStore(subscribe, readConstraintKeys, readConstraintKeys)
}

function buildConstraintKeys(): Record<string, unknown> {
  const keys: Record<string, unknown> = {}
  for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
    const held = state.get(contributor.id)
    if (!held?.enabled) continue
    // A toggle carries no value of its own; its key IS the statement. The
    // other two carry the control's value, falling back to its initial so a
    // switched-on slider that was never dragged still sends the number the
    // panel is displaying rather than an undefined.
    if (contributor.control.kind === 'toggle') {
      keys[contributor.constraintKey] = true
      continue
    }
    keys[contributor.constraintKey] = held.value ?? contributor.control.initial
  }
  return keys
}

/** The same object, for anything that must re-render when it changes. */
export function usePlanConstraints(): Record<string, unknown> {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

/** One constraint's own state, for the control that owns it. */
export function useConstraint(id: string): ConstraintState {
  usePlanConstraints()
  return getConstraint(id)
}
