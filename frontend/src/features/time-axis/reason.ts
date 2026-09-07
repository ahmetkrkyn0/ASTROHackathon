/**
 * Trims a backend `shadow_model.reason` down to the part a mission operator
 * should read.
 *
 * The field is honest and worth surfacing -- section 29 of the design doc is
 * explicit that a static shadow model must not be presented as animated, and
 * the reason is how the UI says why. But when the backend fails to load its
 * SPICE kernels the field arrives carrying the whole CSPICE error banner:
 *
 *   real illumination unavailable (
 *   ================================================================
 *   Toolkit version: CSPICE_N0067
 *   SPICE(NOLEAPSECONDS) --
 *   The variable that points to the leapseconds (DELTET/DELTA_AT) could not
 *   be located in the kernel pool. ... str2et_c --> STR2ET --> TTRANS
 *   ================================================================ )
 *
 * which is an environment error, not a mission fact. Rules 7 and 8 of the same
 * section say the UI does not show backend internals or environment errors, so
 * the banner is cut and the human clause in front of it is kept.
 *
 * Deliberately conservative: a reason with no diagnostic banner in it is passed
 * through untouched, because most of them are ordinary prose the operator needs.
 */

/** Markers that mean "everything from here on is a toolkit diagnostic". */
const DIAGNOSTIC_MARKERS = ['====', 'Toolkit version', 'SPICE(', '-->', '→']

const MAX_LENGTH = 160

export function cleanShadowReason(reason: string | null | undefined): string | null {
  if (!reason) return null

  let text = reason.replace(/\s+/g, ' ').trim()

  // Cut at the earliest diagnostic marker, then drop the now-dangling opener
  // the banner was parenthesised by.
  const cut = DIAGNOSTIC_MARKERS.map((m) => text.indexOf(m)).filter((i) => i >= 0)
  if (cut.length > 0) {
    text = text.slice(0, Math.min(...cut))
  }

  text = text
    .replace(/[([{\s]+$/, '')
    .replace(/[,;:.\s]+$/, '')
    .trim()

  if (text.length === 0) return null

  // An ellipsis already ends the clause; a full stop after one reads as a typo.
  if (text.length > MAX_LENGTH) {
    return `${text.slice(0, MAX_LENGTH).trimEnd()}…`
  }

  return text.endsWith('.') ? text : `${text}.`
}
