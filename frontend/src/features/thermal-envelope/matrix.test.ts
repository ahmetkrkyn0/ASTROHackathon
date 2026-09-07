import { describe, expect, it } from 'vitest'

import type { ThermalEnvelope } from '../../net/analysis'
import { describeCell, envelopeMatrix, unsampledFraction } from './matrix'

import envelopeFixture from '../../net/__fixtures__/thermal-envelope.available.json'

const ENVELOPE = envelopeFixture as unknown as ThermalEnvelope

describe('envelopeMatrix', () => {
  it('fills every bin the axes declare', () => {
    const matrix = envelopeMatrix(ENVELOPE)
    expect(matrix.rows).toBe(ENVELOPE.axes.el_deg.edges.length - 1)
    expect(matrix.cols).toBe(ENVELOPE.axes.s_par_deg.edges.length - 1)
    expect(matrix.rows * matrix.cols).toBe(ENVELOPE.cells.length)
    // Every bin present in the response, so nothing is drawn as a hole.
    expect(matrix.missing).toBe(0)
  })

  it('puts the highest Sun elevation in the top row', () => {
    // The response indexes bin 0 at the lowest edge, which is right for an
    // array and wrong for a chart: an operator reads "Sun high" at the top.
    const matrix = envelopeMatrix(ENVELOPE)
    const top = matrix.grid[0].find((cell) => cell !== null)
    const bottom = matrix.grid[matrix.rows - 1].find((cell) => cell !== null)
    expect(top!.el_mid_deg).toBeGreaterThan(bottom!.el_mid_deg)
  })

  it('keeps the slope axis in the response’s order, away to toward', () => {
    const matrix = envelopeMatrix(ENVELOPE)
    const row = matrix.grid[0]
    const first = row[0]!
    const last = row[matrix.cols - 1]!
    expect(first.s_par_mid_deg).toBeLessThan(0)
    expect(last.s_par_mid_deg).toBeGreaterThan(0)
  })

  it('reports a bin the response omitted rather than drawing it blank', () => {
    // A truncated response must not hide as unsampled space.
    const truncated = {
      ...ENVELOPE,
      cells: ENVELOPE.cells.filter((cell) => !(cell.el_bin === 0 && cell.s_par_bin === 0)),
    }
    const matrix = envelopeMatrix(truncated)
    expect(matrix.missing).toBe(1)
  })
})

describe('verdict semantics', () => {
  it('separates "never leaves the envelope" from "never sampled"', () => {
    // Both have a null dwell and both would print as a blank hour. One is the
    // best outcome in the matrix, the other is no outcome at all.
    const unlimited = ENVELOPE.cells.find((c) => c.verdict === 'unlimited')!
    const unsampled = ENVELOPE.cells.find((c) => c.verdict === 'unsampled')!

    expect(unlimited.dwell_h).toBeNull()
    expect(unsampled.dwell_h).toBeNull()
    // What tells them apart in the data:
    expect(unlimited.samples).toBeGreaterThan(0)
    expect(unsampled.samples).toBe(0)
    expect(unlimited.inner_c).not.toBeNull()
    expect(unsampled.inner_c).toBeNull()

    // And in the words:
    expect(describeCell(unlimited)).toContain('stays inside the envelope')
    expect(describeCell(unsampled)).toContain('never reached this geometry')
  })

  it('names the side and the component on a limited bin', () => {
    const cold = ENVELOPE.cells.find((c) => c.verdict === 'cold_limited')!
    expect(cold.side).toBe('cold')
    expect(cold.component).toBeTruthy()
    expect(cold.dwell_h).toBeGreaterThan(0)
    expect(describeCell(cold)).toMatch(/cold limit on the \w+ after [\d.]+ h/)
  })

  it('reports how much of the matrix carries no result', () => {
    // 29% here. A reader taking the coloured part as the whole picture is
    // reading a different chart from the one the data supports.
    const fraction = unsampledFraction(ENVELOPE)
    expect(fraction).toBeGreaterThan(0.2)
    expect(fraction).toBeLessThan(0.5)
    expect(ENVELOPE.counts.unsampled).toBe(
      ENVELOPE.cells.filter((c) => c.verdict === 'unsampled').length,
    )
  })

  it('carries both provenance labels', () => {
    // Every number in the panel is a model output whose lag nobody measured.
    expect(ENVELOPE.validity).toBe('MODEL')
    expect(ENVELOPE.thermal_lag_validity).toBe('UNCALIBRATED')
    expect(ENVELOPE.claim.toLowerCase()).toContain('uncalibrated')
  })

  it('states the envelope it is measuring against', () => {
    expect(ENVELOPE.envelope.lo_c).toBeLessThan(ENVELOPE.envelope.hi_c)
    expect(ENVELOPE.envelope.lo_component).toBeTruthy()
    expect(ENVELOPE.initial_inner_c).toBeGreaterThan(ENVELOPE.envelope.lo_c)
    expect(ENVELOPE.initial_inner_c).toBeLessThan(ENVELOPE.envelope.hi_c)
  })
})
