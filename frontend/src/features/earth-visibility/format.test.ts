import { describe, expect, it } from 'vitest'

import type { CommWindow } from '../../net/analysis'
import { clearsHorizon, readCommWindow } from './format'

import commWindow from '../../net/__fixtures__/comm-window.available.json'

const CAPTURED = commWindow as unknown as CommWindow

function window_(overrides: Partial<CommWindow>): CommWindow {
  return { ...CAPTURED, ...overrides }
}

describe('readCommWindow', () => {
  it('reads the captured response as a link that is down and stays down', () => {
    const reading = readCommWindow(CAPTURED)
    expect(reading.headline).toBe('Earth below the horizon')
    expect(reading.bounded).toBe(true)
    // The horizon and the elevation are the reason, and they are in the text
    // rather than left for the operator to infer from a bare "no signal".
    expect(reading.detail).toContain('18.4')
    expect(reading.detail).toContain('4.8')
  })

  it('never turns an unknown duration into a number', () => {
    // A link that is up with a null minutes_remaining means the search horizon
    // ended before it went down. "0 min" would report an imminent loss of
    // signal that the data does not support.
    const reading = readCommWindow(
      window_({ visible_now: true, minutes_remaining: null, search_limited: true }),
    )
    expect(reading.headline).toBe('Earth in view')
    expect(reading.detail).not.toMatch(/\b0 min\b/)
    expect(reading.detail).toContain('Still in view')
  })

  it('separates a bounded search from a geometric certainty', () => {
    const bounded = readCommWindow(
      window_({ visible_now: true, minutes_remaining: null, search_limited: true }),
    )
    const certain = readCommWindow(
      window_({ visible_now: true, minutes_remaining: null, search_limited: false }),
    )
    expect(bounded.detail).not.toBe(certain.detail)
    expect(bounded.bounded).toBe(true)
    expect(certain.bounded).toBe(false)
    expect(certain.detail).toContain('No loss of signal found')
  })

  it('reports a real countdown when there is one', () => {
    expect(
      readCommWindow(window_({ visible_now: true, minutes_remaining: 45 })).detail,
    ).toContain('45 min')
    expect(
      readCommWindow(window_({ visible_now: true, minutes_remaining: 4380 })).detail,
    ).toContain('3.0 days')
    expect(
      readCommWindow(window_({ visible_now: false, minutes_until_visible: 600 })).detail,
    ).toContain('10.0 h')
  })

  it('distinguishes "no rise in the window" from "never rises"', () => {
    const bounded = readCommWindow(
      window_({ visible_now: false, minutes_until_visible: null, search_limited: true }),
    )
    const never = readCommWindow(
      window_({ visible_now: false, minutes_until_visible: null, search_limited: false }),
    )
    expect(bounded.detail).toContain('No rise inside')
    expect(never.detail).toContain('never clears')
  })
})

describe('clearsHorizon', () => {
  it('explains the captured verdict from the two angles', () => {
    // 4.77 degrees of Earth against an 18.44 degree ridge. The link is not
    // down because the Earth has set; it is down because the terrain is high.
    expect(clearsHorizon(CAPTURED)).toBe(false)
    expect(CAPTURED.visible_now).toBe(false)
  })

  it('agrees with visible_now when the Earth is clear of the terrain', () => {
    expect(
      clearsHorizon(window_({ earth_elevation_deg: 20, horizon_deg: 18.44 })),
    ).toBe(true)
  })
})
