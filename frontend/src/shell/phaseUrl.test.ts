import { describe, expect, it } from 'vitest'
import { hrefForPhase, phaseFromHref } from './phaseUrl'

const AT = 'http://localhost:3000'

describe('phaseFromHref', () => {
  it('reads the bare address as the landing sequence', () => {
    expect(phaseFromHref(`${AT}/`)).toBe('landing')
  })

  it('reads the hangar and the planner', () => {
    expect(phaseFromHref(`${AT}/?stage=hangar`)).toBe('fleet')
    expect(phaseFromHref(`${AT}/?stage=planner`)).toBe('app')
  })

  it('still honours the ?app and #planner shortcuts', () => {
    // Both predate the hangar and are in people's bookmarks and notes. They
    // mean "skip to the cockpit", which is still a phase this can express.
    expect(phaseFromHref(`${AT}/?app`)).toBe('app')
    expect(phaseFromHref(`${AT}/#planner`)).toBe('app')
  })

  it('falls back to landing rather than guessing at a stage it does not know', () => {
    expect(phaseFromHref(`${AT}/?stage=cockpit`)).toBe('landing')
    expect(phaseFromHref(`${AT}/?stage=`)).toBe('landing')
  })

  it('ignores an unrelated query string', () => {
    expect(phaseFromHref(`${AT}/?utm_source=demo`)).toBe('landing')
    expect(phaseFromHref(`${AT}/?utm_source=demo&stage=hangar`)).toBe('fleet')
  })
})

describe('hrefForPhase', () => {
  it('leaves the landing address bare', () => {
    // Landing is the canonical entry, so it carries no parameter at all --
    // otherwise every first visit would rewrite a clean URL into a noisy one.
    expect(hrefForPhase('landing', `${AT}/`)).toBe(`${AT}/`)
  })

  it('names the stage for the other two', () => {
    expect(hrefForPhase('fleet', `${AT}/`)).toBe(`${AT}/?stage=hangar`)
    expect(hrefForPhase('app', `${AT}/`)).toBe(`${AT}/?stage=planner`)
  })

  it('replaces a stage already in the address instead of appending one', () => {
    expect(hrefForPhase('app', `${AT}/?stage=hangar`)).toBe(`${AT}/?stage=planner`)
    expect(hrefForPhase('landing', `${AT}/?stage=planner`)).toBe(`${AT}/`)
  })

  it('keeps unrelated parameters', () => {
    expect(hrefForPhase('fleet', `${AT}/?utm_source=demo`)).toBe(
      `${AT}/?utm_source=demo&stage=hangar`,
    )
  })

  it('clears the legacy shortcuts it has just superseded', () => {
    // Leaving ?app in place next to stage=hangar would put two answers in one
    // address, and phaseFromHref would have to pick a winner on every read.
    expect(hrefForPhase('fleet', `${AT}/?app`)).toBe(`${AT}/?stage=hangar`)
    expect(hrefForPhase('landing', `${AT}/#planner`)).toBe(`${AT}/`)
  })

  it('round-trips every phase', () => {
    for (const phase of ['landing', 'fleet', 'app'] as const) {
      expect(phaseFromHref(hrefForPhase(phase, `${AT}/`))).toBe(phase)
    }
  })
})
