/**
 * Raster layers over the binary path, with the metadata that travels beside
 * them.
 *
 * `api.ts` already has `fetchLayer`, and it stays -- it returns nested JSON
 * that the seven base grids are built from, and `api.ts` is frozen. This is
 * the other representation: `new Float32Array(await r.arrayBuffer())` is the
 * whole decode, and everything the caller needs to interpret those numbers
 * arrives in `X-Layer-*` response headers rather than in the payload.
 *
 * Those headers are the reason this module exists rather than a call site
 * reading them inline. `X-Layer-Resolution-M` and `X-Layer-Downsample` are how
 * a layer says what its cells actually span, and a coarse product that gets
 * stretched to the fine grid because nobody read them is the "320 m is not
 * 5 m" failure the A-track brief names explicitly. Reading them in one place
 * means a new coarse layer cannot be drawn wrong by omission.
 */

import { getFloat32 } from './client'
import type { Validity } from './types'

export interface BinaryField {
  /** Row-major, `rows * cols` long. NaN is nodata and must stay NaN. */
  readonly data: Float32Array
  readonly rows: number
  readonly cols: number
  /**
   * Metres per cell **of this layer**, which is not always the grid's.
   *
   * A layer served at `downsample=4` covers the same ground with cells four
   * times wider. Drawing it at the fine grid's pitch puts every value in the
   * wrong place.
   */
  readonly resolutionM: number
  /** How many fine cells one of this layer's cells spans. 1 for a fine layer. */
  readonly downsample: number
  readonly validity: Validity | null
  /** Finite value range, as the backend measured it. Null when it found none. */
  readonly min: number | null
  readonly max: number | null
  /**
   * The backend's `X-Layer-Nodata`.
   *
   * A **count** of nodata cells, not a sentinel value -- `/api/safe-haven`
   * reports 179976 for `time_to_safe_haven` on a 250 000-cell grid. The
   * sentinel in the payload is NaN. Treating this number as a value to compare
   * against would mark exactly the wrong cells.
   */
  readonly nodataCount: number
  readonly layerName: string
}

function headerNumber(headers: Headers, name: string, fallback: number): number {
  const raw = headers.get(name)
  if (raw === null) return fallback
  const value = Number(raw)
  return Number.isFinite(value) ? value : fallback
}

function headerValidity(headers: Headers): Validity | null {
  const raw = headers.get('X-Layer-Validity')
  if (raw === 'SYNTHETIC' || raw === 'DERIVED' || raw === 'MODEL' || raw === 'MEASURED') {
    return raw
  }
  return null
}

/**
 * Read a binary field out of a response.
 *
 * Exported and separated from the fetch so a fixture-driven test can exercise
 * the header handling without a network. The length check is the one thing
 * this cannot recover from: a payload that does not match the declared shape
 * would be silently drawn shifted, one cell at a time, with no visible error.
 */
export function fieldFromResponse(
  layerName: string,
  data: Float32Array,
  headers: Headers,
): BinaryField {
  const rows = headerNumber(headers, 'X-Layer-Rows', 0)
  const cols = headerNumber(headers, 'X-Layer-Cols', 0)

  if (rows <= 0 || cols <= 0) {
    throw new Error(`${layerName}: response declared no shape (X-Layer-Rows/Cols missing)`)
  }
  if (data.length !== rows * cols) {
    throw new Error(
      `${layerName}: payload is ${data.length} values but the headers declare ${rows}x${cols}`,
    )
  }

  const minRaw = headers.get('X-Layer-Min')
  const maxRaw = headers.get('X-Layer-Max')

  return {
    data,
    rows,
    cols,
    resolutionM: headerNumber(headers, 'X-Layer-Resolution-M', 0),
    downsample: headerNumber(headers, 'X-Layer-Downsample', 1),
    validity: headerValidity(headers),
    min: minRaw !== null && Number.isFinite(Number(minRaw)) ? Number(minRaw) : null,
    max: maxRaw !== null && Number.isFinite(Number(maxRaw)) ? Number(maxRaw) : null,
    nodataCount: headerNumber(headers, 'X-Layer-Nodata', 0),
    layerName: headers.get('X-Layer-Name') ?? layerName,
  }
}

export interface BinaryLayerParams {
  /** Fine cells per returned cell. The backend caps the response by cell count. */
  downsample?: number
  roverId?: string
}

/**
 * `GET /api/layers/{name}?format=f32`.
 *
 * `name` is a **backend layer name**, never a UI view-mode id: `elevation` not
 * `surface`, `shadow_ratio` not `shadow`, `traversable` not `traversability`.
 * Passing a view-mode id here gets a 404 or, worse, a plausible different grid.
 */
export async function fetchBinaryLayer(
  name: string,
  params: BinaryLayerParams = {},
  signal?: AbortSignal,
): Promise<BinaryField> {
  const query = new URLSearchParams({ format: 'f32' })
  if (params.downsample && params.downsample > 1) {
    query.set('downsample', String(params.downsample))
  }
  if (params.roverId) query.set('rover_id', params.roverId)

  const { data, headers } = await getFloat32(`/layers/${name}?${query}`, signal)
  return fieldFromResponse(name, data, headers)
}

/**
 * A field fetched from an endpoint that is not `/api/layers/{name}` --
 * `/api/safe-haven`, `/api/survival`, `/api/thermal-dwell` and the series
 * endpoints all publish a `binary_url` per field and answer on the same
 * `X-Layer-*` contract.
 *
 * The URL is used exactly as given. It already carries the epoch, rover, span
 * and downsample the manifest was computed with, and rebuilding it from parts
 * is how a binary payload ends up describing a different computation than the
 * manifest beside it.
 */
export async function fetchFieldByUrl(
  label: string,
  binaryUrl: string,
  signal?: AbortSignal,
): Promise<BinaryField> {
  // The manifest gives a path under /api; getFloat32 prepends /api itself.
  const path = binaryUrl.startsWith('/api/') ? binaryUrl.slice('/api'.length) : binaryUrl
  const { data, headers } = await getFloat32(path, signal)
  return fieldFromResponse(label, data, headers)
}

/**
 * Turn a field into the `(number | null)[]` an overlay `FieldCommand` wants.
 *
 * NaN becomes null, which the renderer leaves unpainted so the base map shows
 * through. It must never become a number: on `time_to_safe_haven`, NaN means
 * "no reachable Safe Haven", and zero would read as "a safe haven right here".
 */
export function fieldValues(field: BinaryField): (number | null)[] {
  const values: (number | null)[] = new Array(field.data.length)
  for (let index = 0; index < field.data.length; index += 1) {
    const value = field.data[index]
    values[index] = Number.isNaN(value) ? null : value
  }
  return values
}

/**
 * The same, for a mask: cells at or above `threshold` keep a value, the rest
 * are null.
 *
 * A boolean layer drawn through a colour ramp is a ramp with two stops, and
 * the zeros paint a flat wash over the whole map. PSR is the case in point --
 * it covers 0.3% of this window, so the honest rendering is 0.3% painted and
 * 99.7% untouched.
 */
export function maskValues(field: BinaryField, threshold = 0.5): (number | null)[] {
  const values: (number | null)[] = new Array(field.data.length)
  for (let index = 0; index < field.data.length; index += 1) {
    const value = field.data[index]
    values[index] = !Number.isNaN(value) && value >= threshold ? 1 : null
  }
  return values
}
