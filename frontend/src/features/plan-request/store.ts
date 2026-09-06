import { useSyncExternalStore } from 'react'
import { PLAN_REQUEST_CONTRIBUTORS, type ConstraintState } from './contributors'

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

function rebuild(): void {
  const fields: Record<string, unknown> = {}
  for (const contributor of PLAN_REQUEST_CONTRIBUTORS) {
    const current = state.get(contributor.id) ?? { enabled: false }
    const produced = contributor.fields(current)
    if (produced === null) continue
    Object.assign(fields, produced)
  }
  snapshot = fields
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

/** The same object, for anything that must re-render when it changes. */
export function usePlanConstraints(): Record<string, unknown> {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

/** One constraint's own state, for the control that owns it. */
export function useConstraint(id: string): ConstraintState {
  usePlanConstraints()
  return getConstraint(id)
}
