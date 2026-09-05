import { describe, expect, it } from 'vitest'
import type { PlanResponse, Waypoint } from '../../api'
import { csvFilename, waypointsToCsv } from './exportCsv'

function wp(step: number, over: Partial<Waypoint> = {}): Waypoint {
  return {
    step,
    row: 10 + step,
    col: 20 + step,
    lon: -71.5,
    lat: -88.8,
    altitude_m: 900,
    battery_pct: 100 - step,
    recharge_count: 0,
    recharged_this_step: false,
    risk_level: 'LOW',
    slope_deg: 3.5,
    surface_temp_c: -100,
    shadow_ratio: 0,
    node_cost: 1,
    elapsed_hours: step * 0.1,
    distance_m: step * 80,
    step_energy_wh: 3,
    ...over,
  }
}

describe('waypointsToCsv', () => {
  it('emits a header plus one row per waypoint', () => {
    const csv = waypointsToCsv([wp(0), wp(1)])
    const lines = csv.split('\r\n')
    expect(lines).toHaveLength(3)
    expect(lines[0].startsWith('step,row,col,')).toBe(true)
  })

  it('keeps every column aligned with the header', () => {
    const csv = waypointsToCsv([wp(0)])
    const [header, row] = csv.split('\r\n')
    expect(row.split(',')).toHaveLength(header.split(',').length)
  })

  it('writes a missing altitude as an empty cell, not as "null"', () => {
    const csv = waypointsToCsv([wp(0, { altitude_m: null })])
    expect(csv).not.toContain('null')
    expect(csv.split('\r\n')[1]).toContain(',,')
  })

  // A field that starts carrying a separator later would otherwise shift every
  // column after it without any error being raised.
  it('quotes a value containing a comma, a quote or a newline', () => {
    const csv = waypointsToCsv([wp(0, { risk_level: 'A,B"C' as Waypoint['risk_level'] })])
    expect(csv).toContain('"A,B""C"')
  })

  it('produces only a header for an empty route', () => {
    expect(waypointsToCsv([]).split('\r\n')).toHaveLength(1)
  })
})

describe('csvFilename', () => {
  const plan = { rover: { id: 'lpr_1', name: 'LPR-1' } } as PlanResponse

  it('names the rover and the instant', () => {
    expect(csvFilename(plan, new Date('2026-09-05T14:48:00Z'))).toBe(
      'lunapath-lpr_1-2026-09-05-14-48.csv',
    )
  })

  it('strips anything a filesystem would object to', () => {
    const odd = { rover: { id: '../../etc/passwd', name: 'x' } } as PlanResponse
    expect(csvFilename(odd, new Date('2026-09-05T00:00:00Z'))).toBe(
      'lunapath-etcpasswd-2026-09-05-00-00.csv',
    )
  })

  it('falls back when the response carries no rover', () => {
    expect(csvFilename({} as PlanResponse, new Date('2026-09-05T00:00:00Z'))).toContain(
      'lunapath-rover-',
    )
  })
})
