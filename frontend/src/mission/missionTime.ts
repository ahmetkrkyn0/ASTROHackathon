/**
 * The mission clock's origin: one epoch, for everything time-dependent.
 *
 * Section 5.8 of the integration plan asks for a single canonical mission
 * time, and it is not a tidiness request. Before this constant the codebase
 * had three unrelated origins: the time axis took `new Date()` when its module
 * loaded, the 3-D scene had 2026-09-07 hardcoded in a query string, and the
 * planner took whatever `start_utc` each caller happened to pass. The shadows
 * in the 3-D view and the illumination on the time axis were therefore drawn
 * for different moments, and nothing in the code said so.
 *
 * That gets worse, not better, as the new time-dependent products arrive:
 * Earth visibility, the illumination corridor, DEM uncertainty over time,
 * thermal dwell and survival slices are all functions of the same clock, and
 * five sliders disagreeing about what time it is would be five different
 * skies.
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
