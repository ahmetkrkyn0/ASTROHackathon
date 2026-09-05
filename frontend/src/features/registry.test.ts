import { describe, expect, it } from 'vitest'
import {
  FEATURES,
  selectFeatures,
  selectSystemsFeatures,
  type FeatureGroup,
  type FeatureRegistration,
  type FeatureSlot,
} from './registry'
import type { MissionMode } from '../mission/types'

const Stub = () => null

function entry(
  id: string,
  slot: FeatureSlot,
  modes?: readonly MissionMode[],
  group?: FeatureGroup,
): FeatureRegistration {
  return { id, slot, Component: Stub, modes, group }
}

const EVERY_MODE: readonly MissionMode[] = ['plan', 'analyze']

describe('selectFeatures', () => {
  it('keeps only the asked-for slot', () => {
    const features = [entry('a', 'leftRail'), entry('b', 'rightRail')]
    expect(selectFeatures(features, 'leftRail', 'plan').map((f) => f.id)).toEqual(['a'])
  })

  it('treats a missing modes list as every mode', () => {
    // Omitted means "everywhere". This is the common case -- most panels do
    // not care which stage the cockpit is in -- so it has to be the one you
    // get by writing nothing.
    const features = [entry('always', 'bottomDock')]
    for (const mode of EVERY_MODE) {
      expect(selectFeatures(features, 'bottomDock', mode).map((f) => f.id)).toEqual(['always'])
    }
  })

  it('drops a feature whose modes exclude the current one', () => {
    const features = [entry('analyseOnly', 'bottomDock', ['analyze'])]
    expect(selectFeatures(features, 'bottomDock', 'plan')).toEqual([])
    expect(selectFeatures(features, 'bottomDock', 'analyze').map((f) => f.id)).toEqual([
      'analyseOnly',
    ])
  })

  it('hides a feature that lists no modes at all', () => {
    // An empty array is NOT the same as an omitted one, and the difference is
    // load-bearing: nobody means "never show this" by leaving the field off,
    // so the two must not collapse into each other.
    const features = [entry('hidden', 'leftRail', [])]
    for (const mode of EVERY_MODE) {
      expect(selectFeatures(features, 'leftRail', mode)).toEqual([])
    }
  })

  it('preserves registration order within a slot', () => {
    // Order in the array is render order in the rail, which is the only way a
    // registration can say "draw me above that one".
    const features = [
      entry('first', 'rightRail'),
      entry('second', 'rightRail'),
      entry('third', 'rightRail'),
    ]
    expect(selectFeatures(features, 'rightRail', 'plan').map((f) => f.id)).toEqual([
      'first',
      'second',
      'third',
    ])
  })

  it('returns an empty list for a slot nothing registered', () => {
    expect(selectFeatures([entry('a', 'leftRail')], 'canvasOverlay', 'plan')).toEqual([])
  })

  it('defaults to the primary group, so a systems feature never lands in a rail', () => {
    // The rails call selectFeatures without a group argument. A systems
    // feature keeps its slot for ordering but must not render in that rail --
    // that is the whole point of the split.
    const features = [
      entry('task', 'leftRail'),
      entry('evidence', 'leftRail', undefined, 'systems'),
    ]
    expect(selectFeatures(features, 'leftRail', 'plan').map((f) => f.id)).toEqual(['task'])
  })

  it('treats a missing group as primary', () => {
    // Same reasoning as omitted modes: leaving the field off is the common
    // case and must be the one that keeps a panel in the rails.
    const features = [entry('a', 'rightRail')]
    expect(selectFeatures(features, 'rightRail', 'plan', 'primary').map((f) => f.id)).toEqual(['a'])
    expect(selectFeatures(features, 'rightRail', 'plan', 'systems')).toEqual([])
  })
})

describe('selectSystemsFeatures', () => {
  it('collects systems features across slots, ignoring which rail they name', () => {
    const features = [
      entry('task', 'leftRail'),
      entry('ros', 'leftRail', undefined, 'systems'),
      entry('corridor', 'rightRail', undefined, 'systems'),
    ]
    expect(selectSystemsFeatures(features, 'plan').map((f) => f.id)).toEqual(['ros', 'corridor'])
  })

  it('applies the same mode rule as the rails', () => {
    const features = [
      entry('planOnly', 'leftRail', ['plan'], 'systems'),
      entry('always', 'rightRail', undefined, 'systems'),
    ]
    expect(selectSystemsFeatures(features, 'plan').map((f) => f.id)).toEqual(['planOnly', 'always'])
    expect(selectSystemsFeatures(features, 'analyze').map((f) => f.id)).toEqual(['always'])
  })

  it('excludes primary features', () => {
    const features = [entry('task', 'leftRail'), entry('evidence', 'leftRail', undefined, 'systems')]
    expect(selectSystemsFeatures(features, 'plan').map((f) => f.id)).toEqual(['evidence'])
  })
})

describe('FEATURES', () => {
  it('shows mission context in the right rail, in analyze only', () => {
    // It used to run in both modes. Plan now gets the wider map instead, so
    // the guard is that it still reaches analyze -- moving it to another rail
    // or dropping the registration would take the operator's context away
    // from the mode that reads it.
    const missionContext = FEATURES.find((feature) => feature.id === 'mission-context')

    expect(missionContext?.slot).toBe('rightRail')
    expect(selectFeatures(FEATURES, 'rightRail', 'analyze').map((feature) => feature.id)).toContain(
      'mission-context',
    )
    expect(selectFeatures(FEATURES, 'rightRail', 'plan').map((feature) => feature.id)).not.toContain(
      'mission-context',
    )
  })

  it('leaves the right rail empty in plan and filled in analyze', () => {
    // App.tsx renders the <aside> and its grid column only when this is
    // non-empty, so a feature registered for plan's right rail without that
    // being the intent would quietly put the 288px column back.
    expect(selectFeatures(FEATURES, 'rightRail', 'plan')).toHaveLength(0)
    expect(selectFeatures(FEATURES, 'rightRail', 'analyze').length).toBeGreaterThan(0)
  })

  it('shows mission setup in the left rail only during plan mode', () => {
    expect(selectFeatures(FEATURES, 'leftRail', 'plan').map((feature) => feature.id)).toContain(
      'mission-setup',
    )
    expect(selectFeatures(FEATURES, 'leftRail', 'analyze').map((feature) => feature.id)).not.toContain(
      'mission-setup',
    )
  })

  it('shows route analysis in the right rail only during analyze mode', () => {
    expect(selectFeatures(FEATURES, 'rightRail', 'analyze').map((feature) => feature.id)).toContain(
      'route-analysis',
    )
    expect(selectFeatures(FEATURES, 'rightRail', 'plan').map((feature) => feature.id)).not.toContain(
      'route-analysis',
    )
  })

  it('has no duplicate ids', () => {
    // The id is the React key. Two entries sharing one makes React reuse a
    // component instance across two different features, which shows up as a
    // panel keeping the other one's state rather than as an error.
    const ids = FEATURES.map((feature) => feature.id)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
