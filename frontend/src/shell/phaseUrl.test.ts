import { describe, expect, it } from 'vitest'
import { hrefForLocation, locationFromHref, phaseFromHref } from './phaseUrl'

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

describe('hrefForLocation, on the phases alone', () => {
  it('leaves the landing address bare', () => {
    // Landing is the canonical entry, so it carries no parameter at all --
    // otherwise every first visit would rewrite a clean URL into a noisy one.
    expect(hrefForLocation({ phase: 'landing', mode: 'plan' }, `${AT}/`)).toBe(`${AT}/`)
  })

  it('names the stage for the other two', () => {
    expect(hrefForLocation({ phase: 'fleet', mode: 'plan' }, `${AT}/`)).toBe(`${AT}/?stage=hangar`)
    expect(hrefForLocation({ phase: 'app', mode: 'plan' }, `${AT}/`)).toBe(`${AT}/?stage=planner`)
  })

  it('replaces a stage already in the address instead of appending one', () => {
    expect(hrefForLocation({ phase: 'app', mode: 'plan' }, `${AT}/?stage=hangar`)).toBe(`${AT}/?stage=planner`)
    expect(hrefForLocation({ phase: 'landing', mode: 'plan' }, `${AT}/?stage=planner`)).toBe(`${AT}/`)
  })

  it('keeps unrelated parameters', () => {
    expect(hrefForLocation({ phase: 'fleet', mode: 'plan' }, `${AT}/?utm_source=demo`)).toBe(
      `${AT}/?utm_source=demo&stage=hangar`,
    )
  })

  it('clears the legacy shortcuts it has just superseded', () => {
    // Leaving ?app in place next to stage=hangar would put two answers in one
    // address, and phaseFromHref would have to pick a winner on every read.
    expect(hrefForLocation({ phase: 'fleet', mode: 'plan' }, `${AT}/?app`)).toBe(`${AT}/?stage=hangar`)
    expect(hrefForLocation({ phase: 'landing', mode: 'plan' }, `${AT}/#planner`)).toBe(`${AT}/`)
  })

  it('round-trips every phase', () => {
    for (const phase of ['landing', 'fleet', 'app'] as const) {
      expect(phaseFromHref(hrefForLocation({ phase, mode: 'plan' }, `${AT}/`))).toBe(phase)
    }
  })
})

describe('locationFromHref', () => {
  it('reads the analysis stage as the cockpit in analyze', () => {
    expect(locationFromHref(`${AT}/?stage=analysis`)).toEqual({
      phase: 'app',
      mode: 'analyze',
    })
  })

  it('reads every other stage in plan', () => {
    // Only the cockpit has modes. The hangar and the landing sequence are not
    // "in plan" so much as they have nothing a mode could describe, and plan
    // is the value that means "no analysis on screen".
    expect(locationFromHref(`${AT}/`)).toEqual({ phase: 'landing', mode: 'plan' })
    expect(locationFromHref(`${AT}/?stage=hangar`)).toEqual({ phase: 'fleet', mode: 'plan' })
    expect(locationFromHref(`${AT}/?stage=planner`)).toEqual({ phase: 'app', mode: 'plan' })
  })

  it('reads the legacy shortcuts as the cockpit in plan', () => {
    expect(locationFromHref(`${AT}/?app`)).toEqual({ phase: 'app', mode: 'plan' })
    expect(locationFromHref(`${AT}/#planner`)).toEqual({ phase: 'app', mode: 'plan' })
  })

  it('does not invent a mode for an unknown stage', () => {
    expect(locationFromHref(`${AT}/?stage=cockpit`)).toEqual({
      phase: 'landing',
      mode: 'plan',
    })
  })
})

describe('hrefForLocation', () => {
  it('names the analysis stage for the cockpit in analyze', () => {
    expect(hrefForLocation({ phase: 'app', mode: 'analyze' }, `${AT}/`)).toBe(
      `${AT}/?stage=analysis`,
    )
  })

  it('moves between the two cockpit modes in place', () => {
    expect(hrefForLocation({ phase: 'app', mode: 'analyze' }, `${AT}/?stage=planner`)).toBe(
      `${AT}/?stage=analysis`,
    )
    expect(hrefForLocation({ phase: 'app', mode: 'plan' }, `${AT}/?stage=analysis`)).toBe(
      `${AT}/?stage=planner`,
    )
  })

  it('ignores the mode outside the cockpit', () => {
    // An analyze mode on the hangar is not a thing that can be on screen, so
    // it must not be a thing the address can say.
    expect(hrefForLocation({ phase: 'fleet', mode: 'analyze' }, `${AT}/`)).toBe(
      `${AT}/?stage=hangar`,
    )
    expect(hrefForLocation({ phase: 'landing', mode: 'analyze' }, `${AT}/`)).toBe(`${AT}/`)
  })

  it('round-trips every location that can be on screen', () => {
    const locations = [
      { phase: 'landing', mode: 'plan' },
      { phase: 'fleet', mode: 'plan' },
      { phase: 'app', mode: 'plan' },
      { phase: 'app', mode: 'analyze' },
    ] as const

    for (const location of locations) {
      expect(locationFromHref(hrefForLocation(location, `${AT}/`))).toEqual(location)
    }
  })

  it('keeps unrelated parameters when naming the analysis stage', () => {
    expect(hrefForLocation({ phase: 'app', mode: 'analyze' }, `${AT}/?utm_source=demo`)).toBe(
      `${AT}/?utm_source=demo&stage=analysis`,
    )
  })

  it('clears the legacy shortcuts on the way into analysis', () => {
    expect(hrefForLocation({ phase: 'app', mode: 'analyze' }, `${AT}/?app`)).toBe(
      `${AT}/?stage=analysis`,
    )
  })
})

describe('phaseFromHref, which asks only which stage', () => {
  it('reads the cockpit out of an analysis address', () => {
    // App.tsx seeds `phase` with this, and analysis is the cockpit.
    expect(phaseFromHref(`${AT}/?stage=analysis`)).toBe('app')
  })
})
