/**
 * The one clock every time-dependent layer reads -- spec section 5.8.
 *
 * Six backend products vary over the same axis: the illumination series, the
 * Earth-visibility series, the illumination uncertainty band, the illumination
 * corridor, the thermal dwell slice and the survival slice. Before this
 * existed there was no shared axis at all -- `useTimeAxis` captured
 * `new Date().toISOString()` at module load and kept its own slice index, so a
 * second time-dependent feature would have started a second, silently
 * different clock. Two layers on one map showing two different moments is the
 * kind of wrong that looks right.
 *
 * The shape is an epoch plus an offset rather than a single Date because that
 * is what the endpoints take: `start_utc` fixes the ephemeris and `n_slices` x
 * `slice_hours` spans the window, and the operator scrubs within it. Deriving
 * the epoch back out of a scrubbed instant would lose which window we are in.
 */

export interface MissionTime {
  /**
   * The ISO epoch every series is computed from. Null means no epoch has been
   * chosen, which is a real state: without one, `/api/safe-haven` answers
   * `unavailable` and says so, and `/api/illumination-series` falls back to a
   * static shadow model. Defaulting to "now" would hide that.
   */
  readonly startUtc: string | null
  /** How far into the window the operator has scrubbed, in hours. */
  readonly offsetHours: number
  /** Total span of the window, in hours. Zero when no window is loaded. */
  readonly spanHours: number
  /**
   * Hours per slice of the coarse time axis the series endpoints return.
   *
   * Kept beside the offset because slice-indexed products (the corridor cube,
   * the dwell field) need to convert, and a feature doing that arithmetic
   * itself is a feature that can round differently from its neighbour.
   */
  readonly sliceHours: number
}

export const MISSION_TIME_NONE: MissionTime = Object.freeze({
  startUtc: null,
  offsetHours: 0,
  spanHours: 0,
  sliceHours: 0,
})

/**
 * The mission clock's origin: one epoch, for everything time-dependent.
 *
 * FIXED RATHER THAN WALL CLOCK, deliberately. A demo that opens on the real
 * current time shows a different sky, different shadows and different
 * illumination on every run, which makes a result impossible to reproduce and
 * a screenshot impossible to check. It is also the more fragile choice against
 * this backend: several products are read from caches built for specific
 * epochs, and an arbitrary "now" is exactly how an endpoint comes back
 * unavailable in front of an audience.
 *
 * This is the origin, not a limit. `setMissionTime` moves the clock, and every
 * time-dependent layer is expected to follow it.
 */
export const MISSION_EPOCH_UTC = '2026-09-07T00:00:00Z'

/**
 * Six days from the mission epoch, in six-hour slices.
 *
 * The span is not arbitrary. A lunar day is about 29.5 Earth days, so at this
 * polar site a 24-hour window does not change at all -- the backend reports
 * shadow min and max both exactly 1.0 across every slice of it. Six days is
 * the shortest window over which the illumination this cockpit exists to show
 * actually moves, and it is the window `useTimeAxis` already requests.
 *
 * Anchored to MISSION_EPOCH_UTC rather than to `new Date()`. The wall clock
 * was the first choice here and it was the wrong one: it makes two runs of the
 * same mission incomparable, and it walks off the epochs the preprocessing
 * caches were built for. A second clock anywhere -- a stray `new Date()`, a
 * hardcoded epoch in a query string -- is two layers drawn from two moments,
 * which looks exactly like two layers drawn from one.
 */
export const SESSION_MISSION_TIME: MissionTime = Object.freeze({
  startUtc: MISSION_EPOCH_UTC,
  offsetHours: 0,
  spanHours: 144,
  sliceHours: 6,
})

/**
 * The instant currently selected, as an ISO string, or null without an epoch.
 *
 * This is what `/api/comm-window?utc=` and `/api/cell-telemetry?start_utc=`
 * want. Null propagates rather than becoming "now": a caller that cannot ask
 * the question must not ask a different question instead.
 */
export function missionTimeUtc(time: MissionTime): string | null {
  if (!time.startUtc) return null
  const base = Date.parse(time.startUtc)
  if (!Number.isFinite(base)) return null
  return new Date(base + time.offsetHours * 3_600_000).toISOString()
}

/**
 * Which slice of a series covers the selected instant.
 *
 * Floor, not round: slice `i` covers `[i * sliceHours, (i + 1) * sliceHours)`,
 * so the slice an instant falls **in** is the floor. Rounding would show the
 * next slice's data for the second half of every slice.
 *
 * Categorical and binary fields are never interpolated between slices --
 * section 5.8's last line. Returning an index rather than a fractional
 * position is how that rule is kept: there is no fraction to be tempted by.
 */
export function missionTimeSliceIndex(time: MissionTime, sliceCount: number): number {
  if (sliceCount <= 0) return 0
  const width = time.sliceHours > 0 ? time.sliceHours : 1
  const index = Math.floor(time.offsetHours / width)
  return Math.min(Math.max(index, 0), sliceCount - 1)
}

/** True when an epoch is set, which is what the time-dependent endpoints need. */
export function hasMissionEpoch(time: MissionTime): boolean {
  return typeof time.startUtc === 'string' && Number.isFinite(Date.parse(time.startUtc))
}
