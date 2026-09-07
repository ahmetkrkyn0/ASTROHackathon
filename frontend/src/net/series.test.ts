import { describe, expect, it } from 'vitest'
import { cubeFrom } from './series'

// 2 slices of a 2x3 grid, each cell numbered so its slice, row and column
// are readable from the value itself: slice*100 + row*10 + col.
const DATA = new Float32Array([
  0, 1, 2, 10, 11, 12,
  100, 101, 102, 110, 111, 112,
])

describe('cubeFrom', () => {
  it('reads slices slice-major, then row-major', () => {
    const cube = cubeFrom(DATA, { slices: 2, rows: 2, cols: 3 })
    expect(Array.from(cube.sliceAt(0))).toEqual([0, 1, 2, 10, 11, 12])
    expect(Array.from(cube.sliceAt(1))).toEqual([100, 101, 102, 110, 111, 112])
  })

  it('indexes a cell inside a slice as row * cols + col', () => {
    // The layout drawField and the time axis both assume. Transposing rows
    // and cols here would still fill the canvas -- with the map's mirror.
    const cube = cubeFrom(DATA, { slices: 2, rows: 2, cols: 3 })
    const slice = cube.sliceAt(1)
    expect(slice[1 * 3 + 2]).toBe(112)
  })

  it('rejects a payload that does not fill the declared shape', () => {
    // A downsample the caller forgot to pass through would land here rather
    // than animate a cube read at the wrong stride.
    expect(() => cubeFrom(DATA, { slices: 3, rows: 2, cols: 3 })).toThrow(
      /do not fill 3x2x3/,
    )
  })

  it('rejects a slice index outside the cube', () => {
    const cube = cubeFrom(DATA, { slices: 2, rows: 2, cols: 3 })
    // subarray silently returns an empty view past the end, which renders as
    // a blank frame that looks like night rather than like a bug.
    expect(() => cube.sliceAt(2)).toThrow(RangeError)
    expect(() => cube.sliceAt(-1)).toThrow(RangeError)
  })

  it('returns a view, not a copy, so a slice costs nothing per frame', () => {
    // The time axis reads one slice per frame off a cube that is 250x250xN.
    // A copy here would allocate a megabyte a frame while the slider moves.
    const cube = cubeFrom(DATA, { slices: 2, rows: 2, cols: 3 })
    expect(cube.sliceAt(1).buffer).toBe(DATA.buffer)
  })
})
