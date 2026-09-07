import { describe, expect, it } from 'vitest'

import { fieldFromResponse, fieldValues, maskValues } from './layers'

/**
 * Header values copied from a real `GET /api/layers/roughness?format=f32`
 * response. `X-Layer-Nodata: 0` there and `179976` on safe-haven's
 * `time_to_safe_haven` -- a count, in both cases, not a sentinel.
 */
function headersFor(overrides: Record<string, string> = {}): Headers {
  return new Headers({
    'X-Layer-Name': 'roughness',
    'X-Layer-Dtype': 'float32',
    'X-Layer-Rows': '2',
    'X-Layer-Cols': '3',
    'X-Layer-Downsample': '1',
    'X-Layer-Resolution-M': '5.0',
    'X-Layer-Nodata': '0',
    'X-Layer-Min': '0.11939021944999695',
    'X-Layer-Max': '4.6029887199401855',
    'X-Layer-Validity': 'MEASURED',
    ...overrides,
  })
}

describe('fieldFromResponse', () => {
  it('reads the shape, resolution and provenance out of the headers', () => {
    const field = fieldFromResponse(
      'roughness',
      new Float32Array([1, 2, 3, 4, 5, 6]),
      headersFor(),
    )
    expect(field.rows).toBe(2)
    expect(field.cols).toBe(3)
    expect(field.resolutionM).toBe(5)
    expect(field.downsample).toBe(1)
    expect(field.validity).toBe('MEASURED')
    expect(field.min).toBeCloseTo(0.1193902, 6)
    expect(field.max).toBeCloseTo(4.6029887, 6)
  })

  it('keeps a coarse layer coarse', () => {
    // The 320-m-is-not-5-m rule. A layer served at downsample=4 covers the
    // same ground with cells four times wider; drawing it at the fine grid's
    // pitch puts every value in the wrong place.
    const field = fieldFromResponse(
      'survival',
      new Float32Array(4),
      headersFor({
        'X-Layer-Rows': '2',
        'X-Layer-Cols': '2',
        'X-Layer-Downsample': '4',
        'X-Layer-Resolution-M': '20.0',
      }),
    )
    expect(field.downsample).toBe(4)
    expect(field.resolutionM).toBe(20)
  })

  it('reads nodata as a count, not a value', () => {
    const field = fieldFromResponse(
      'time_to_safe_haven',
      new Float32Array(6),
      headersFor({ 'X-Layer-Nodata': '179976' }),
    )
    // 179976 is how many cells have no data, on a grid of 250 000. Comparing
    // values against it would mark exactly the wrong cells.
    expect(field.nodataCount).toBe(179976)
  })

  it('refuses a payload that does not match the declared shape', () => {
    // Silently drawn one cell out of place is the alternative, with no error.
    expect(() =>
      fieldFromResponse('roughness', new Float32Array(5), headersFor()),
    ).toThrow(/5 values but the headers declare 2x3/)
  })

  it('refuses a response that declares no shape', () => {
    const headers = headersFor()
    headers.delete('X-Layer-Rows')
    headers.delete('X-Layer-Cols')
    expect(() => fieldFromResponse('roughness', new Float32Array(6), headers)).toThrow(
      /declared no shape/,
    )
  })

  it('reports an unknown validity as null rather than inventing one', () => {
    const field = fieldFromResponse(
      'roughness',
      new Float32Array(6),
      headersFor({ 'X-Layer-Validity': 'PLAUSIBLE' }),
    )
    expect(field.validity).toBeNull()
  })
})

describe('fieldValues', () => {
  it('turns NaN into null and never into a number', () => {
    // On time_to_safe_haven, NaN means "no reachable Safe Haven". Zero there
    // would read as "a safe haven right here".
    const field = fieldFromResponse(
      'time_to_safe_haven',
      new Float32Array([1, NaN, 3, NaN, 5, 6]),
      headersFor(),
    )
    expect(fieldValues(field)).toEqual([1, null, 3, null, 5, 6])
  })

  it('keeps a real zero', () => {
    const field = fieldFromResponse(
      'time_to_safe_haven',
      new Float32Array([0, NaN, 0, 1, 2, 3]),
      headersFor(),
    )
    // Zero hours to a haven is a fact -- the cell IS a haven. Only NaN is
    // absence, and the two must not collapse into each other.
    expect(fieldValues(field)).toEqual([0, null, 0, 1, 2, 3])
  })
})

describe('maskValues', () => {
  it('paints only what is inside the mask', () => {
    // PSR covers 0.3% of this window. A two-stop ramp would wash the other
    // 99.7% in the ramp's low colour and claim the whole map is data.
    const field = fieldFromResponse(
      'psr',
      new Float32Array([0, 1, 0, 1, 0, 0]),
      headersFor({ 'X-Layer-Name': 'psr' }),
    )
    expect(maskValues(field)).toEqual([null, 1, null, 1, null, null])
  })

  it('leaves NaN unpainted rather than treating it as outside', () => {
    const field = fieldFromResponse(
      'psr',
      new Float32Array([NaN, 1, 0, NaN, 1, 0]),
      headersFor({ 'X-Layer-Name': 'psr' }),
    )
    expect(maskValues(field)).toEqual([null, 1, null, null, 1, null])
  })
})
