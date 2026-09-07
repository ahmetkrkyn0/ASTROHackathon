/**
 * How a comm window reads in words.
 *
 * Pure, and separate from the component, because the interesting cases here
 * are exactly the ones a component test could not reach in this project: a
 * null duration means three different things depending on `visible_now` and
 * `search_limited`, and getting that wrong reports a loss of signal the data
 * never claimed.
 */

import type { CommWindow } from '../../net/analysis'

export interface CommWindowReading {
  /** Link up or down, right now. */
  headline: string
  /** How long that lasts, or why we cannot say. Never a fabricated number. */
  detail: string
  /** True when the answer is bounded by the search horizon, not by geometry. */
  bounded: boolean
}

function hours(minutes: number): string {
  if (minutes < 90) return `${minutes.toFixed(0)} min`
  const h = minutes / 60
  if (h < 48) return `${h.toFixed(1)} h`
  return `${(h / 24).toFixed(1)} days`
}

export function readCommWindow(window: CommWindow): CommWindowReading {
  const bounded = window.search_limited === true
  const horizon = `${(window.searched_hours / 24).toFixed(0)} days`

  if (window.visible_now) {
    if (window.minutes_remaining === null) {
      // Up, and it did not go down inside the searched span. That is not
      // "0 minutes remaining" and it is not "forever" either.
      return {
        headline: 'Earth in view',
        detail: bounded
          ? `Still in view at the end of the searched ${horizon}. No loss of signal within that span.`
          : 'No loss of signal found.',
        bounded,
      }
    }
    return {
      headline: 'Earth in view',
      detail: `Loss of signal in ${hours(window.minutes_remaining)}.`,
      bounded,
    }
  }

  if (window.minutes_until_visible === null) {
    return {
      headline: 'Earth below the horizon',
      detail: bounded
        ? `No rise inside the searched ${horizon}. The terrain horizon here is ${window.horizon_deg.toFixed(1)}°, and the Earth reached ${window.earth_elevation_deg.toFixed(1)}°.`
        : 'The Earth never clears the local horizon here.',
      bounded,
    }
  }

  return {
    headline: 'Earth below the horizon',
    detail: `Acquisition of signal in ${hours(window.minutes_until_visible)}.`,
    bounded,
  }
}

/**
 * Whether the Earth clears the terrain horizon at this cell, from the two
 * angles the response carries.
 *
 * Reported alongside `visible_now` rather than instead of it: the elevation
 * and horizon are why the answer is what it is, and at a polar site with a
 * 18-degree ridge to the north that "why" is the whole story.
 */
export function clearsHorizon(window: CommWindow): boolean {
  return window.earth_elevation_deg > window.horizon_deg
}
