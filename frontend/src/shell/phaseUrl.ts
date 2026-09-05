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

/** Which stage an address asks for. Anything unrecognised means landing. */
export function phaseFromHref(href: string): AppPhase {
  let url: URL
  try {
    url = new URL(href)
  } catch {
    return 'landing'
  }

  const stage = url.searchParams.get(STAGE_PARAM)
  if (stage && stage in STAGE_TO_PHASE) {
    return STAGE_TO_PHASE[stage]
  }
  if (hasLegacyPlannerFlag(url)) {
    return 'app'
  }
  return 'landing'
}

/**
 * The address that names a phase, keeping everything else the current one
 * carries. The legacy flags are dropped as they are superseded, so an address
 * never holds two answers to the same question.
 */
export function hrefForPhase(phase: AppPhase, currentHref: string): string {
  const url = new URL(currentHref)

  url.searchParams.delete('app')
  if (url.hash.includes('planner')) {
    url.hash = ''
  }

  if (phase === 'landing') {
    url.searchParams.delete(STAGE_PARAM)
  } else {
    url.searchParams.set(STAGE_PARAM, PHASE_TO_STAGE[phase])
  }

  // URL stringifies an emptied query as a trailing "?", which would make a
  // clean landing address look like it still carried something.
  return url.toString().replace(/\?$/, '')
}
