/**
 * The address bar as a mirror of which stage is on screen.
 *
 * Not routing. The three stages are not three pages: the shell, the mission
 * context and above all the backdrop clip are mounted once and never remounted
 * between them, which is the whole reason the landing sequence flows into the
 * cockpit without a seam. A router that mounted a component per route would
 * restart the video on every transition -- exactly what SpaceBackdrop was
 * built to avoid.
 *
 * So `phase` stays the single source of truth for what renders, and the URL
 * follows it. What that buys is the three things a single address could not:
 * Back steps through the stages instead of leaving the app, a reload returns
 * to the stage you were on, and a stage can be linked to.
 *
 * The cockpit's two modes are in the address for the same three reasons: PLAN
 * and ANALYZE are where the work is read, and before this an F5 in the middle
 * of reading a route dropped you back into planning it.
 *
 * A query parameter rather than a path, deliberately. `/hangar` needs the host
 * to rewrite unknown paths to index.html, and a static host without that rule
 * answers a hard refresh with a 404 -- a failure that shows up only once the
 * thing is deployed. `?stage=` works anywhere something serves index.html.
 *
 * Mission state -- rover, weights, endpoints, the route -- is deliberately not
 * here. It would need every value to survive a reload to mean anything, and a
 * link carrying half a mission is worse than one carrying none. A reload lands
 * on the stage, with the mission at its defaults.
 */

export type AppPhase = 'landing' | 'fleet' | 'app'

/**
 * The two working modes of the cockpit, mirrored in the address alongside the
 * phase.
 *
 * ANALYZE is not a fourth phase. It renders in the same cockpit, over the same
 * mounted map and mission context, and swaps which panels the rails show --
 * `phase` still decides what is mounted and `mode` decides what it shows. But
 * the three things the stage addresses bought apply to it just as much: Back
 * should step out of the analysis rather than out of the app, a reload should
 * come back to the route you were reading, and an analysis should be linkable.
 *
 * So the address names both. Only the cockpit has modes -- landing and the
 * hangar carry no mode at all rather than a meaningless `mode=plan`.
 */
export type CockpitMode = 'plan' | 'analyze'

/** A phase, plus the mode when the phase is the cockpit. */
export interface AppLocation {
  phase: AppPhase
  mode: CockpitMode
}

/** What each phase is called in an address. Landing is the bare URL. */
const STAGE_PARAM = 'stage'
const PHASE_TO_STAGE: Record<Exclude<AppPhase, 'landing'>, string> = {
  fleet: 'hangar',
  app: 'planner',
}
const STAGE_TO_PHASE: Record<string, AppPhase> = {
  hangar: 'fleet',
  planner: 'app',
}

/**
 * Analysis gets its own stage name rather than a second parameter.
 *
 * `?stage=analysis` reads as one place; `?stage=planner&mode=analyze` reads as
 * a place plus a setting, and would leave `?stage=hangar&mode=analyze`
 * expressible and meaningless. One parameter with one answer keeps every
 * address that parses also being an address that means something.
 */
const ANALYSIS_STAGE = 'analysis'

/**
 * Shortcuts that predate the hangar and still mean "open the cockpit".
 *
 * They were the only way to skip the landing sequence for a long time, and
 * `?app` is written down in docs/superpowers/plans/2026-09-04-kabuk-
 * birlestirme.md. Reading them costs two lines; breaking them costs someone
 * their demo shortcut.
 */
function hasLegacyPlannerFlag(url: URL): boolean {
  return url.searchParams.has('app') || url.hash.includes('planner')
}

/**
 * Which stage and mode an address asks for. Anything unrecognised means
 * landing, in plan -- the mode is only ever read for the cockpit.
 */
export function locationFromHref(href: string): AppLocation {
  let url: URL
  try {
    url = new URL(href)
  } catch {
    return { phase: 'landing', mode: 'plan' }
  }

  const stage = url.searchParams.get(STAGE_PARAM)
  if (stage === ANALYSIS_STAGE) {
    return { phase: 'app', mode: 'analyze' }
  }
  if (stage && stage in STAGE_TO_PHASE) {
    return { phase: STAGE_TO_PHASE[stage], mode: 'plan' }
  }
  if (hasLegacyPlannerFlag(url)) {
    return { phase: 'app', mode: 'plan' }
  }
  return { phase: 'landing', mode: 'plan' }
}

/** Which stage an address asks for, ignoring the mode. */
export function phaseFromHref(href: string): AppPhase {
  return locationFromHref(href).phase
}

/**
 * The address that names a phase, keeping everything else the current one
 * carries. The legacy flags are dropped as they are superseded, so an address
 * never holds two answers to the same question.
 */
export function hrefForLocation(location: AppLocation, currentHref: string): string {
  const { phase, mode } = location
  const url = new URL(currentHref)

  url.searchParams.delete('app')
  if (url.hash.includes('planner')) {
    url.hash = ''
  }

  if (phase === 'landing') {
    url.searchParams.delete(STAGE_PARAM)
  } else if (phase === 'app' && mode === 'analyze') {
    url.searchParams.set(STAGE_PARAM, ANALYSIS_STAGE)
  } else {
    url.searchParams.set(STAGE_PARAM, PHASE_TO_STAGE[phase])
  }

  // URL stringifies an emptied query as a trailing "?", which would make a
  // clean landing address look like it still carried something.
  return url.toString().replace(/\?$/, '')
}

