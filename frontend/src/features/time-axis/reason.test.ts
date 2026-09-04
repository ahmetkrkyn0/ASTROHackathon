import { describe, expect, it } from 'vitest'
import { cleanShadowReason } from './reason'

describe('cleanShadowReason', () => {
  it('keeps an ordinary reason as it is', () => {
    // The common case. Most reasons are one honest clause and must survive
    // untouched -- this is how the UI says a shadow model is static.
    expect(cleanShadowReason('the request carried no epoch')).toBe(
      'the request carried no epoch.',
    )
  })

  it('does not double the full stop', () => {
    expect(cleanShadowReason('the request carried no epoch.')).toBe(
      'the request carried no epoch.',
    )
  })

  it('cuts the CSPICE banner and keeps the human clause', () => {
    // The real payload observed from the backend with no leapseconds kernel
    // loaded. Everything from the rule of equals signs on is a toolkit dump.
    const raw = `real illumination unavailable (
================================================================================
Toolkit version: CSPICE_N0067

SPICE(NOLEAPSECONDS) --

The variable that points to the leapseconds (DELTET/DELTA_AT) could not be
located in the kernel pool. It is likely that the leapseconds kernel has not
been loaded. str2et_c --> STR2ET --> TTRANS
================================================================================
)`
    expect(cleanShadowReason(raw)).toBe('real illumination unavailable.')
  })

  it('cuts at a bare SPICE error code with no banner rule', () => {
    expect(cleanShadowReason('illumination unavailable: SPICE(NOLEAPSECONDS) --')).toBe(
      'illumination unavailable.',
    )
  })

  it('returns null when nothing readable survives the cut', () => {
    // A reason that is only a diagnostic has nothing to tell an operator, and
    // an empty clause appended to the sentence would read as a bug.
    expect(cleanShadowReason('==== Toolkit version: CSPICE_N0067 ====')).toBeNull()
  })

  it('returns null for absent reasons', () => {
    expect(cleanShadowReason(null)).toBeNull()
    expect(cleanShadowReason(undefined)).toBeNull()
    expect(cleanShadowReason('   ')).toBeNull()
  })

  it('truncates a long clause rather than filling the dock with prose', () => {
    const long = 'x'.repeat(400)
    const out = cleanShadowReason(long)
    expect(out).not.toBeNull()
    expect(out!.length).toBeLessThanOrEqual(162)
    expect(out!.endsWith('…')).toBe(true)
  })

  it('collapses the newlines a multi-line reason arrives with', () => {
    expect(cleanShadowReason('static cube\n  for this\n  request')).toBe(
      'static cube for this request.',
    )
  })
})
