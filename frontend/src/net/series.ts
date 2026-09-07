import { getFloat32, getJson } from './client'
import type { SeriesManifest } from './types'

export interface SeriesParams {
  /**
   * Without a start epoch the backend cannot vary illumination with time and
   * returns shadow_model.model === 'static' with four identical slices. Pass
   * one whenever the caller intends to animate.
   */
  startUtc?: string
  nSlices?: number
  sliceHours?: number
  downsample?: number
}

export async function fetchSeriesManifest(
  params: SeriesParams = {},
  signal?: AbortSignal,
): Promise<SeriesManifest> {
  const query = new URLSearchParams()
  if (params.startUtc) query.set('start_utc', params.startUtc)
  if (params.nSlices !== undefined) query.set('n_slices', String(params.nSlices))
  if (params.sliceHours !== undefined) query.set('slice_hours', String(params.sliceHours))
  if (params.downsample !== undefined) query.set('downsample', String(params.downsample))
  const suffix = query.toString()
  return getJson<SeriesManifest>(`/illumination-series${suffix ? `?${suffix}` : ''}`, signal)
}

export interface SeriesCube {
  data: Float32Array
  slices: number
  rows: number
  cols: number
  /** A zero-copy view of one time slice. NaN cells are no-data. */
  sliceAt: (index: number) => Float32Array
}

/**
 * Wrap a decoded cube, without touching the network.
 *
 * Layout is slice-major then row-major (binary_format.order), so slice t
 * occupies [t*rows*cols, (t+1)*rows*cols). Split out from the fetch and
 * exported so the index arithmetic is testable: a wrong stride animates a
 * perfectly plausible sequence of the wrong data, and no amount of watching
 * it play reveals that. Asserting the length means a layout change surfaces
 * as an error instead.
 */
export function cubeFrom(
  data: Float32Array,
  expected: { slices: number; rows: number; cols: number },
): SeriesCube {
  const { slices, rows, cols } = expected
  if (data.length !== slices * rows * cols) {
    throw new Error(
      `Series cube: ${data.length} values do not fill ${slices}x${rows}x${cols}`,
    )
  }

  const perSlice = rows * cols
  return {
    data,
    slices,
    rows,
    cols,
    sliceAt: (index: number) => {
      if (index < 0 || index >= slices) {
        throw new RangeError(`Slice ${index} is outside 0..${slices - 1}`)
      }
      return data.subarray(index * perSlice, (index + 1) * perSlice)
    },
  }
}

/**
 * Fetch a time cube from a binary_url the manifest published.
 *
 * The URL is used VERBATIM -- the manifest already encoded start_utc,
 * downsample and field into it, and rebuilding the query by hand is how a
 * "+" in an ISO-8601 offset turns into a space.
 */
export async function fetchSeriesCube(
  binaryUrl: string,
  expected: { slices: number; rows: number; cols: number },
  signal?: AbortSignal,
): Promise<SeriesCube> {
  // binary_url arrives as "/api/illumination-series?..."; getFloat32 prefixes
  // "/api", so the duplicated prefix is stripped.
  const path = binaryUrl.startsWith('/api') ? binaryUrl.slice(4) : binaryUrl
  const { data } = await getFloat32(path, signal)
  return cubeFrom(data, expected)
}
