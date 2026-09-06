import { describe, expect, it } from 'vitest'
import type { PlanExecution, PlanResponse, SimSummary, Waypoint } from '../../api'
import {
  ASSISTANT_QUESTION,
  VERDICT_REASON_CODES,
  decideVerdict,
  energySplit,
  milestones,
  riskShares,
  slopeHistogram,
  type Verdict,
  type VerdictReasonCode,
} from './report'
import verdictCases from './verdictCases.json'
import {
  COPY,
  REPORT_LANGS,
  VERDICT_MEANING,
  fmtNum,
  fmtPct,
  reasonText,
} from '../../i18n/reportCopy'

const SUMMARY: SimSummary = {
  total_distance_km: 1,
  total_elapsed_hours: 2,
  final_battery_pct: 80,
  min_battery_pct: 80,
  max_slope_deg: 10,
  max_segment_slope_deg: 9,
  total_energy_consumed_wh: 400,
  total_shadow_exposure: 0.3,
  critical_steps_count: 0,
  high_or_above_steps_count: 0,
  waypoint_count: 3,
  total_recharges: 0,
  stranded: false,
  stranded_at_step: null,
  max_continuous_shadow_h: 1,
  shadow_limit_h: 50,
  shadow_limit_exceeded: false,
  peak_power_exceeded_steps: 0,
}

function wp(step: number, over: Partial<Waypoint> = {}): Waypoint {
  return {
    step,
    row: step,
    col: step,
    lon: 0,
    lat: -89,
    altitude_m: 900 + step,
    battery_pct: 100 - step,
    recharge_count: 0,
    recharged_this_step: false,
    risk_level: 'LOW',
    slope_deg: 3,
    surface_temp_c: -100,
    shadow_ratio: 0,
    node_cost: 1,
    elapsed_hours: step * 0.1,
    distance_m: step * 80,
    step_energy_wh: 3,
    ...over,
  }
}

function plan(summary: Partial<SimSummary>, over: Partial<PlanResponse> = {}): PlanResponse {
  return {
    status: 'success',
    astar_metrics: {} as PlanResponse['astar_metrics'],
    summary: { ...SUMMARY, ...summary },
    geojson: {},
    waypoints: [wp(0), wp(1), wp(2)],
    ...over,
  }
}

describe('decideVerdict', () => {
  it('passes a route that violates nothing', () => {
    expect(decideVerdict(plan({})).verdict).toBe('GO')
  })

  it('blocks a stranded route', () => {
    const result = decideVerdict(plan({ stranded: true, stranded_at_step: 12 }))
    expect(result.verdict).toBe('NO-GO')
    expect(reasonText(result.reasons[0], 'en')).toContain('12')
  })

  it('blocks a breached shadow limit', () => {
    expect(
      decideVerdict(plan({ shadow_limit_exceeded: true, max_continuous_shadow_h: 61 })).verdict,
    ).toBe('NO-GO')
  })

  it('blocks a truncated execution and names the node counts', () => {
    const result = decideVerdict(
      plan({}, { execution: { stranded: false, planned_nodes: 90, executable_nodes: 40, truncated: true, reason: 'battery' } }),
    )
    expect(result.verdict).toBe('NO-GO')
    expect(reasonText(result.reasons[0], 'en')).toContain('40/90')
  })

  // The distinction the whole verdict rests on: a soft finding must not
  // produce NO-GO, or the operator learns to ignore NO-GO.
  it('degrades a low battery trough to GO-WITH-RISK, not NO-GO', () => {
    expect(decideVerdict(plan({ min_battery_pct: 22 })).verdict).toBe('GO-WITH-RISK')
  })

  it('lists blocking reasons before warnings', () => {
    const result = decideVerdict(plan({ stranded: true, total_recharges: 2 }))
    expect(reasonText(result.reasons[0], 'en')).toContain('ran out of energy')
    expect(reasonText(result.reasons[result.reasons.length - 1], 'en')).toContain(
      'recharge',
    )
  })
})

describe('riskShares', () => {
  it('prefers the backend breakdown over recounting', () => {
    const shares = riskShares([wp(0), wp(1)], {
      waypoint_count: 2,
      slope_histogram: [],
      risk_breakdown_pct: { LOW: 50, HIGH: 50 },
      min_surface_temp_c: null,
      max_surface_temp_c: null,
    })
    expect(shares).toEqual({ LOW: 50, MEDIUM: 0, HIGH: 50, CRITICAL: 0 })
  })

  it('counts waypoints when no statistics were sent', () => {
    const shares = riskShares([wp(0), wp(1, { risk_level: 'CRITICAL' })], null)
    expect(shares.LOW).toBe(50)
    expect(shares.CRITICAL).toBe(50)
  })
})

describe('slopeHistogram', () => {
  it('bins locally when statistics are absent and the counts sum to the route', () => {
    const waypoints = [wp(0, { slope_deg: 2 }), wp(1, { slope_deg: 12 }), wp(2, { slope_deg: 40 })]
    const bins = slopeHistogram(waypoints, null)
    expect(bins.reduce((sum, b) => sum + b.count, 0)).toBe(3)
    // 40 deg is above the top edge and belongs in the last bin, not dropped.
    expect(bins[bins.length - 1].count).toBe(1)
  })
})

describe('energySplit', () => {
  it('adds payload and heater to the simulated drive energy rather than carving them out', () => {
    expect(energySplit(400, 2, 10, 5)).toEqual({ driveWh: 400, payloadWh: 20, heaterWh: 10 })
  })
})

describe('milestones', () => {
  it('deduplicates a step that is both an extreme and a quarter mark', () => {
    const waypoints = Array.from({ length: 12 }, (_, i) =>
      wp(i, { slope_deg: i === 6 ? 20 : 3, battery_pct: i === 6 ? 10 : 90 }),
    )
    const steps = milestones(waypoints).map((m) => m.step)
    expect(new Set(steps).size).toBe(steps.length)
    expect(steps[0]).toBe(0)
    expect(steps[steps.length - 1]).toBe(11)
  })

  it('returns nothing for an empty route', () => {
    expect(milestones([])).toEqual([])
  })
})

describe('milestones endpoint priority', () => {
  // The common case, not an edge case: a route that drains monotonically has
  // its lowest battery at the last waypoint, and the endpoint must still be
  // the row called GOAL.
  it('keeps GOAL on the last step when it is also the lowest battery', () => {
    const waypoints = Array.from({ length: 20 }, (_, i) => wp(i, { battery_pct: 100 - i }))
    const marks = milestones(waypoints)
    expect(marks[marks.length - 1]).toMatchObject({ title: 'GOAL', step: 19 })
    expect(marks.some((m) => m.title === 'LOWEST BATTERY')).toBe(false)
  })
})


/**
 * The parity fixture, shared with backend/test_report_verdict.py.
 *
 * One cast, at the boundary: the JSON cannot be typed as SimSummary because
 * `absent` cases deliberately omit non-nullable fields, which is the whole
 * reason the fixture exists (JS `undefined < 30` is false, Python `None < 30`
 * raises, and null is neither -- JS coerces it to 0).
 */
interface VerdictCase {
  name: string
  summary: Record<string, unknown>
  execution: PlanExecution | null
  absent: string[]
  verdict: Verdict
  codes: VerdictReasonCode[]
}

const PARITY_CASES = verdictCases.cases as unknown as VerdictCase[]
const PARITY_BASE = verdictCases.base as unknown as Record<string, unknown>

describe('verdict parity cases', () => {
  it('covers every reason code the module can produce', () => {
    const seen = new Set(PARITY_CASES.flatMap((one) => one.codes))
    for (const code of VERDICT_REASON_CODES) expect(seen).toContain(code)
  })

  for (const one of PARITY_CASES) {
    it(one.name, () => {
      const summary: Record<string, unknown> = { ...PARITY_BASE, ...one.summary }
      for (const key of one.absent) delete summary[key]

      const result = decideVerdict({
        status: 'success',
        astar_metrics: {} as PlanResponse['astar_metrics'],
        summary: summary as unknown as SimSummary,
        geojson: {},
        waypoints: [],
        ...(one.execution ? { execution: one.execution } : {}),
      })

      expect(result.verdict).toBe(one.verdict)
      expect(result.reasons.map((reason) => reason.code)).toEqual(one.codes)
    })
  }
})

describe('report copy', () => {
  // Every code, in every language. A reason with no sentence renders as an
  // empty bullet in a PDF -- silent, and only ever seen by whoever the report
  // was exported for.
  it('renders every reason code in both languages', () => {
    const samples = PARITY_CASES.flatMap((one) => {
      const summary: Record<string, unknown> = { ...PARITY_BASE, ...one.summary }
      for (const key of one.absent) delete summary[key]
      return decideVerdict({
        status: 'success',
        astar_metrics: {} as PlanResponse['astar_metrics'],
        summary: summary as unknown as SimSummary,
        geojson: {},
        waypoints: [],
        ...(one.execution ? { execution: one.execution } : {}),
      }).reasons
    })

    const covered = new Set(samples.map((reason) => reason.code))
    for (const code of VERDICT_REASON_CODES) expect(covered).toContain(code)

    for (const lang of REPORT_LANGS) {
      for (const reason of samples) {
        const text = reasonText(reason, lang)
        expect(text.length).toBeGreaterThan(0)
        // A template that lost its value renders the literal word, and that is
        // what a missing interpolation looks like from the outside.
        expect(text).not.toContain('undefined')
        expect(text).not.toContain('NaN')
      }
    }
  })

  it('states what every verdict means, in both languages', () => {
    for (const lang of REPORT_LANGS) {
      const meanings = Object.values(VERDICT_MEANING[lang])
      expect(meanings).toHaveLength(3)
      expect(new Set(meanings).size).toBe(3)
      for (const line of meanings) expect(line.length).toBeGreaterThan(0)
    }
  })

  it('carries the same keys in both languages', () => {
    // Turkish is written by hand beside English; a key added to one and not
    // the other is the failure this catches.
    const walk = (value: unknown, trail: string): string[] => {
      if (typeof value !== 'object' || value === null) return [trail]
      return Object.entries(value).flatMap(([key, inner]) =>
        walk(inner, trail ? `${trail}.${key}` : key),
      )
    }
    expect(walk(COPY.tr, '').sort()).toEqual(walk(COPY.en, '').sort())
  })

  // Turkish moves both separators and puts the percent sign in front. Getting
  // that backwards is the tell that a report was translated word by word.
  it('formats numbers the way each language writes them', () => {
    expect(fmtNum(3.47, 2, 'en')).toBe('3.47')
    expect(fmtNum(3.47, 2, 'tr')).toBe('3,47')
    expect(fmtPct(70, 1, 'en')).toBe('70.0%')
    expect(fmtPct(70, 1, 'tr')).toBe('%70,0')
    // Above a thousand the fraction stops carrying information.
    expect(fmtNum(2665, 1, 'en')).toBe('2,665')
    expect(fmtNum(2665, 1, 'tr')).toBe('2.665')
    expect(fmtNum(Number.NaN, 1, 'en')).toBe('--')
    expect(fmtNum(Number.NaN, 1, 'tr')).toBe('--')
    // Intl prints negative zero as "-0", and a chart axis that opens below the
    // origin lands on exactly that. The battery axis read "-0%" once.
    expect(fmtNum(-0, 0, 'en')).toBe('0')
    expect(fmtPct(-0, 0, 'tr')).toBe('%0')
  })
})

describe('ASSISTANT_QUESTION', () => {
  it('asks a different question per verdict and names the verdict in two of them', () => {
    const questions = Object.values(ASSISTANT_QUESTION)
    expect(new Set(questions).size).toBe(3)
    expect(ASSISTANT_QUESTION['NO-GO']).toContain('NO-GO')
    expect(ASSISTANT_QUESTION['GO-WITH-RISK']).toContain('GO-WITH-RISK')
  })
})
