import { describe, expect, it } from 'vitest'
import { coarseToFine, metresToPixel, pixelToMetres, type GridFrame } from './geo'

// The shipped Site01 window. Not a fixture invented for the test: these are
// the values the backend reads at runtime.
const FRAME: GridFrame = {
  originX: -32500,
  originY: 11000,
  resolutionM: 5,
  rows: 500,
  cols: 500,
}

describe('metresToPixel', () => {
  it('puts the origin at the north-west corner', () => {
    expect(metresToPixel(-32500, 11000, FRAME)).toEqual({ row: 0, col: 0 })
  })

  it('advances a row SOUTHWARD as y decreases', () => {
    // The whole point. origin.y is the window's north edge and rows increase
    // southward, so a smaller y is a LARGER row. Flipping this sign mirrors
    // the corridor about the middle row -- which looks plausible on screen.
    expect(metresToPixel(-32495, 10995, FRAME)).toEqual({ row: 1, col: 1 })
  })

  it('puts the last cell at the south-east corner', () => {
    expect(metresToPixel(-30005, 8505, FRAME)).toEqual({ row: 499, col: 499 })
  })

  it('never returns a negative row for a point inside the window', () => {
    for (const y of [11000, 10000, 9000, 8505]) {
      expect(metresToPixel(-32500, y, FRAME).row).toBeGreaterThanOrEqual(0)
    }
  })
})

describe('pixelToMetres', () => {
  it('round-trips with metresToPixel', () => {
    for (const [row, col] of [[0, 0], [1, 1], [250, 137], [499, 499]]) {
      const { x, y } = pixelToMetres(row, col, FRAME)
      expect(metresToPixel(x, y, FRAME)).toEqual({ row, col })
    }
  })
})

describe('coarseToFine', () => {
  it('returns the CENTRE CELL of the coarse block', () => {
    // coarsen=4 collapses fine rows 0..3 onto coarse row 0; the cell the
    // backend samples and publishes for it is 0 * 4 + 4 // 2 = 2.
    expect(coarseToFine(0, 0, 4)).toEqual({ row: 2, col: 2 })
    expect(coarseToFine(2, 3, 4)).toEqual({ row: 10, col: 14 })
  })

  it('agrees with the fine pixels /api/plan-4d publishes', () => {
    // main.py:1143-1147 builds path_pixels as r * coarsen + coarsen // 2.
    // Drawing a coarse state at any other offset puts it off the very route
    // the same response drew, so this reproduces that expression exactly.
    for (const coarsen of [1, 2, 3, 4, 5, 8]) {
      const offset = Math.floor(coarsen / 2)
      for (const [row, col] of [[0, 0], [1, 2], [7, 9]]) {
        expect(coarseToFine(row, col, coarsen)).toEqual({
          row: row * coarsen + offset,
          col: col * coarsen + offset,
        })
      }
    }
  })

  it('lands on a whole fine pixel, never a half one', () => {
    // (coarsen - 1) / 2 -- the geometric block centre -- returns 1.5 here.
    // That is half a cell off the elevation the planner solved against, and
    // on a 5 m grid half a cell is 2.5 m of silent lateral error.
    expect(Number.isInteger(coarseToFine(0, 0, 4).row)).toBe(true)
    expect(Number.isInteger(coarseToFine(3, 5, 2).col)).toBe(true)
  })

  it('is the identity at coarsen=1', () => {
    expect(coarseToFine(7, 9, 1)).toEqual({ row: 7, col: 9 })
  })
})
