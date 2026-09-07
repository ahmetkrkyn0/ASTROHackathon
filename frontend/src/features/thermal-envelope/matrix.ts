/**
 * The envelope matrix, arranged for rendering.
 *
 * Pure so it can be tested: the two things that go wrong here are invisible in
 * the drawn grid. A bin can be missing from `cells` and leave a hole that
 * looks like an `unsampled` bin, and the row order can be inverted so that a
 * Sun below the horizon appears at the top where a reader expects it high.
 */

import type { EnvelopeCell, ThermalEnvelope } from '../../net/analysis'

export interface EnvelopeMatrix {
  /** Sun elevation, HIGH first. Bin 0 is the lowest elevation in the response. */
  readonly rows: number
  /** Sun-parallel slope, negative (away) to positive (toward the Sun). */
  readonly cols: number
  /** `grid[row][col]`, null where the response carried no bin at all. */
  readonly grid: readonly (readonly (EnvelopeCell | null)[])[]
  readonly elEdges: readonly number[]
  readonly sParEdges: readonly number[]
  /** Bins the response never mentioned -- distinct from `unsampled`. */
  readonly missing: number
}

/**
 * Build the matrix from the flat cell list.
 *
 * Rows are reversed so the highest Sun elevation is the top row. The response
 * indexes bin 0 at the lowest edge, which is the natural order for an array
 * and the wrong one for a chart: an operator reads "Sun high" at the top.
 *
 * A bin absent from `cells` becomes null, and `missing` counts them. That is
 * not the same as `unsampled`: unsampled is the backend saying "the trace
 * never went here", missing is the backend not saying anything, and a chart
 * that drew them identically would hide a truncated response.
 */
export function envelopeMatrix(envelope: ThermalEnvelope): EnvelopeMatrix {
  const rows = envelope.axes.el_deg.edges.length - 1
  const cols = envelope.axes.s_par_deg.edges.length - 1

  const byBin = new Map<string, EnvelopeCell>()
  for (const cell of envelope.cells) {
    byBin.set(`${cell.el_bin}:${cell.s_par_bin}`, cell)
  }

  let missing = 0
  const grid: (EnvelopeCell | null)[][] = []
  for (let row = 0; row < rows; row += 1) {
    // Highest elevation first.
    const elBin = rows - 1 - row
    const line: (EnvelopeCell | null)[] = []
    for (let col = 0; col < cols; col += 1) {
      const cell = byBin.get(`${elBin}:${col}`) ?? null
      if (cell === null) missing += 1
      line.push(cell)
    }
    grid.push(line)
  }

  return {
    rows,
    cols,
    grid,
    elEdges: envelope.axes.el_deg.edges,
    sParEdges: envelope.axes.s_par_deg.edges,
    missing,
  }
}

/**
 * What a bin says, in one line, for its tooltip.
 *
 * `unlimited` and `unsampled` are worded so they cannot be confused: one is
 * the best outcome the matrix has, the other is an absence of data. Both would
 * otherwise print as a blank dwell.
 */
export function describeCell(cell: EnvelopeCell | null): string {
  if (cell === null) return 'No bin in the response'
  const geometry = `Sun ${cell.el_mid_deg.toFixed(2)}°, slope ${cell.s_par_mid_deg.toFixed(1)}°`

  if (cell.verdict === 'unsampled') {
    return `${geometry} — not sampled: the heat1d trace never reached this geometry`
  }
  if (cell.verdict === 'unlimited') {
    const inner = cell.inner_c === null ? '' : `, settles at ${cell.inner_c.toFixed(1)} °C`
    return `${geometry} — stays inside the envelope${inner}`
  }
  const hours = cell.dwell_h === null ? 'unknown' : `${cell.dwell_h.toFixed(2)} h`
  return `${geometry} — ${cell.side} limit on the ${cell.component ?? 'rover'} after ${hours}`
}

/**
 * The share of the matrix that carries no result.
 *
 * Published because 29% of this matrix is unsampled, and a reader who takes
 * the coloured 71% as the whole picture is reading a different chart from the
 * one the data supports.
 */
export function unsampledFraction(envelope: ThermalEnvelope): number {
  const total = Object.values(envelope.counts).reduce((sum, n) => sum + n, 0)
  return total > 0 ? envelope.counts.unsampled / total : 0
}
