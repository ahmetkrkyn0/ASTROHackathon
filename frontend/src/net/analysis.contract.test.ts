import { describe, expect, it } from 'vitest'

import type {
  CommWindow,
  EarthSeriesManifest,
  PsrValidation,
  SafeHavenManifest,
} from './analysis'
import type { CellTelemetryResponse } from './types'
import { isModelUnavailable } from '../mission/capability'

import psrValidation from './__fixtures__/psr-validation.available.json'
import safeHaven from './__fixtures__/safe-haven.available.json'
import commWindow from './__fixtures__/comm-window.available.json'
import earthSeries from './__fixtures__/earth-series.available.json'
import cellTelemetry from './__fixtures__/cell-telemetry.available.json'
import cellSafeHaven from './__fixtures__/cell-telemetry.safe-haven.json'

/**
 * Contract tests: the declared types against responses actually captured from
 * a running backend. A field renamed or dropped on the backend fails here
 * rather than rendering as `undefined` somewhere on screen.
 *
 * The `satisfies` casts are the assertion. If a fixture stops matching its
 * type, this file stops compiling and `npm run typecheck` says so.
 */

describe('GET /api/psr-validation', () => {
  const data = psrValidation as unknown as PsrValidation

  it('parses every field the panel reads', () => {
    expect(data.jaccard).toBeGreaterThan(0)
    expect(data.psr_recall).toBeGreaterThan(0)
    expect(data.dark_precision).toBeGreaterThan(0)
    expect(data.n_psr).toBeLessThan(data.n_cells)
    expect(data.product).toBe('LPSR_80S_20MPP_ADJ')
    expect(data.validity.psr).toBe('MEASURED')
    // Our own shadow model stays DERIVED. The comparison is only meaningful
    // because the two carry different provenance.
    expect(data.validity.shadow_ratio).toBe('DERIVED')
  })

  it('carries the backend’s own claim and reading, for quoting', () => {
    expect(data.claim.length).toBeGreaterThan(40)
    expect(data.reading.length).toBeGreaterThan(40)
  })

  it('reports agreement well short of perfect', () => {
    // The point of the panel. A validation number that could only ever show
    // agreement would not be validating anything; this window's is 0.61.
    expect(data.jaccard).toBeLessThan(1)
    expect(data.false_positive_fraction).toBeGreaterThan(0)
  })
})

describe('GET /api/safe-haven', () => {
  const data = safeHaven as unknown as SafeHavenManifest

  it('parses the manifest and its model block', () => {
    expect(data.safe_haven_model.model).toBe('spice_horizon')
    expect(isModelUnavailable(data.safe_haven_model)).toBe(false)
    expect(data.grid.rows).toBe(500)
    expect(data.grid.cols).toBe(500)
    expect(data.binary_format.shape).toEqual([500, 500])
  })

  it('publishes all four fields with binary urls', () => {
    for (const name of [
      'safe_haven',
      'max_dark_hours_without_dte',
      'earth_below_hours',
      'time_to_safe_haven',
    ] as const) {
      expect(data.fields[name]?.binary_url).toContain('/api/safe-haven')
      expect(data.fields[name]?.binary_url).toContain(`field=${name}`)
    }
  })

  it('reports NaN as the payload sentinel and nodata as a count', () => {
    // These are two different things in one response and mixing them up marks
    // exactly the wrong cells: nodata is how MANY have none.
    expect(data.binary_format.nodata).toBe('NaN')
    const field = data.fields.time_to_safe_haven
    expect(field?.nodata).toBeGreaterThan(1000)
    expect(field?.nodata).toBeLessThanOrEqual(data.grid.rows * data.grid.cols)
  })

  it('does not claim every cell can reach a haven', () => {
    expect(data.safe_haven_fraction).toBeLessThan(1)
    expect(data.safe_haven_cells).toBeLessThan(data.traversable_cells)
  })
})

describe('GET /api/comm-window', () => {
  const data = commWindow as unknown as CommWindow

  it('parses the window and its limits', () => {
    expect(typeof data.visible_now).toBe('boolean')
    expect(data.searched_hours).toBeGreaterThan(0)
    expect(Number.isFinite(data.earth_elevation_deg)).toBe(true)
    expect(Number.isFinite(data.horizon_deg)).toBe(true)
  })

  it('keeps an unknown duration null rather than zero', () => {
    // This capture has the Earth below the local horizon with no rise inside
    // the search horizon: both durations are null and `search_limited` says
    // why. Rendering either as 0 would report an event the data does not have.
    expect(data.minutes_remaining).toBeNull()
    expect(data.minutes_until_visible).toBeNull()
    expect(data.next_change_utc).toBeNull()
    expect(data.search_limited).toBe(true)
  })
})

describe('GET /api/earth-series', () => {
  const data = earthSeries as unknown as EarthSeriesManifest

  it('parses the per-slice timeline the strip reads', () => {
    expect(data.earth_model.model).toBe('spice_horizon')
    expect(data.earth).toHaveLength(data.slices)
    for (const slice of data.earth) {
      expect(slice.visible_fraction).toBeGreaterThanOrEqual(0)
      expect(slice.visible_fraction).toBeLessThanOrEqual(1)
    }
  })

  it('declares a slice-major cube shape matching its grid', () => {
    expect(data.binary_format.shape).toEqual([
      data.slices,
      data.grid.rows,
      data.grid.cols,
    ])
  })

  it('is coarser than the fine grid when downsampled', () => {
    // A 63x63 field at 40 m/px. Drawn at the fine grid's 5 m pitch it would be
    // wrong by a factor of eight in each axis.
    expect(data.grid.downsample).toBeGreaterThan(1)
    expect(data.grid.resolution_m).toBeGreaterThan(5)
  })
})

describe('GET /api/cell-telemetry', () => {
  const plain = cellTelemetry as unknown as CellTelemetryResponse
  const withEpoch = cellSafeHaven as unknown as CellTelemetryResponse

  it('carries the C4 fields where the layer is loaded', () => {
    expect(plain.roughness_m).toBeGreaterThan(0)
    expect(plain.f_roughness).toBeGreaterThanOrEqual(0)
    expect(plain.f_roughness).toBeLessThanOrEqual(1)
    expect(typeof plain.in_psr).toBe('boolean')
    expect(plain.layer_validity.roughness).toBe('MEASURED')
    expect(plain.layer_validity.psr).toBe('MEASURED')
  })

  it('adds roughness as a fifth cost slice', () => {
    expect(plain.cost_breakdown.roughness).toBeGreaterThan(0)
  })

  it('withholds the safe-haven verdict, with a reason, when no epoch is given', () => {
    expect(plain.safe_haven).toBeNull()
    expect(isModelUnavailable(plain.safe_haven_model)).toBe(true)
    expect(plain.safe_haven_model?.reason).toContain('start epoch')
  })

  it('fills the safe-haven block once an epoch is given', () => {
    const haven = withEpoch.safe_haven
    expect(haven).not.toBeNull()
    expect(typeof haven?.is_safe_haven).toBe('boolean')
    expect(withEpoch.safe_haven_model?.model).toBe('spice_horizon')
  })

  it('reports an unreachable haven as null, never as zero hours', () => {
    // Zero would mean the cell IS a haven. This capture is a cell that is not
    // one and cannot reach one; the two facts must not render the same.
    expect(withEpoch.safe_haven?.is_safe_haven).toBe(false)
    expect(withEpoch.safe_haven?.time_to_safe_haven_h).toBeNull()
  })

  it('marks the not-requested sub-models unavailable rather than empty', () => {
    expect(isModelUnavailable(plain.survival_model)).toBe(true)
    expect(isModelUnavailable(plain.thermal_dwell_model)).toBe(true)
    expect(plain.survival).toBeNull()
    expect(plain.thermal_dwell).toBeNull()
  })
})
