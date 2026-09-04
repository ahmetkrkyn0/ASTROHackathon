import { describe, expect, it } from 'vitest'
import { FEATURES, selectFeatures, type FeatureRegistration, type FeatureSlot } from './registry'
import type { MissionMode } from '../mission/types'

const Stub = () => null

function entry(
  id: string,
  slot: FeatureSlot,
  modes?: readonly MissionMode[],
): FeatureRegistration {
  return { id, slot, Component: Stub, modes }
}

const EVERY_MODE: readonly MissionMode[] = ['fleet', 'plan', 'analyze']

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
})

describe('FEATURES', () => {
  it('shows mission context in the right rail during both cockpit modes', () => {
    // Removing this registration, giving it a mode list, or putting it in a
    // different rail silently takes the operator's context away from one of
    // the two modes that need it.
    const missionContext = FEATURES.find((feature) => feature.id === 'mission-context')

    expect(missionContext?.slot).toBe('rightRail')
    expect(Object.prototype.hasOwnProperty.call(missionContext ?? {}, 'modes')).toBe(false)
    expect(selectFeatures(FEATURES, 'rightRail', 'plan').map((feature) => feature.id)).toContain(
      'mission-context',
    )
    expect(selectFeatures(FEATURES, 'rightRail', 'analyze').map((feature) => feature.id)).toContain(
      'mission-context',
    )
  })

  it('shows mission setup in the left rail only during plan mode', () => {
    expect(selectFeatures(FEATURES, 'leftRail', 'plan').map((feature) => feature.id)).toContain(
      'mission-setup',
    )
    expect(selectFeatures(FEATURES, 'leftRail', 'fleet').map((feature) => feature.id)).not.toContain(
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
    expect(selectFeatures(FEATURES, 'rightRail', 'fleet').map((feature) => feature.id)).not.toContain(
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
