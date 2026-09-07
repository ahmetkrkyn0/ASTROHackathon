import { describe, expect, it } from 'vitest'

import type { TerrainManifest } from '../../net/types'
import { ANALYSIS_LAYERS, analysisLayerById } from './layers'

import terrain from '../../net/__fixtures__/terrain.available.json'

const MANIFEST = terrain as unknown as TerrainManifest

/**
 * The overlay table against the real manifest. A layer renamed on the backend
 * fails here rather than showing an empty toggle that never loads.
 */
describe('analysis layer table', () => {
  it('names layers the backend actually publishes', () => {
    for (const spec of ANALYSIS_LAYERS) {
      expect(
        MANIFEST.layers[spec.layerName],
        `${spec.layerName} missing from the manifest`,
      ).toBeDefined()
    }
  })

  it('uses backend layer names, never UI view-mode ids', () => {
    // `surface`/`shadow`/`traversability` are view modes; passing one to
    // fetchLayer gets a 404 or a plausible different grid.
    const viewModeIds = ['surface', 'shadow', 'traversability']
    for (const spec of ANALYSIS_LAYERS) {
      expect(viewModeIds).not.toContain(spec.layerName)
    }
  })

  it('keeps ids and layer names unique', () => {
    expect(new Set(ANALYSIS_LAYERS.map((s) => s.id)).size).toBe(ANALYSIS_LAYERS.length)
    expect(new Set(ANALYSIS_LAYERS.map((s) => s.layerName)).size).toBe(
      ANALYSIS_LAYERS.length,
    )
  })

  it('gives every layer a stated limit', () => {
    // The claim boundary is not optional: each of these is routinely over-read.
    for (const spec of ANALYSIS_LAYERS) {
      expect(spec.limit.length, `${spec.id} has no limit`).toBeGreaterThan(20)
      expect(spec.blurb.length).toBeGreaterThan(10)
    }
  })

  it('draws the boolean layer as a mask, not a ramp', () => {
    expect(analysisLayerById('psr').render.mode).toBe('mask')
  })
})

describe('B3 uncertainty layers', () => {
  it('keeps our ensemble and NASA’s error model on separate entries', () => {
    // Both are "slope sigma" and they are not the same claim: one is a spread
    // we computed over the clones, the other is a spread NASA published.
    // Folding them together would flatten exactly the provenance the
    // layer-provenance feature exists to preserve.
    expect(MANIFEST.layers.slope_sigma.validity).toBe('DERIVED')
    expect(MANIFEST.layers.slope_sigma_nasa.validity).toBe('MODEL')
    expect(MANIFEST.layers.elevation_sigma.validity).toBe('MODEL')
    expect(MANIFEST.layers.p_traversable.validity).toBe('DERIVED')
  })

  it('does not claim they measure the same range', () => {
    const ours = MANIFEST.layers.slope_sigma
    const nasa = MANIFEST.layers.slope_sigma_nasa
    // About three times wider. A shared numeric domain would compress ours to
    // nothing and imply the two are directly comparable.
    expect(nasa.max).not.toBeNull()
    expect(ours.max).not.toBeNull()
    expect(nasa.max as number).toBeGreaterThan((ours.max as number) * 2)
  })

  it('publishes the pedigree, including what the ensemble did not vary', () => {
    const pedigree = MANIFEST.dem_uncertainty
    expect(pedigree).toBeDefined()
    expect(pedigree?.model).toBe('nasa_pgda_clones')
    expect(pedigree?.n_clones).toBeGreaterThan(0)
    // The three limits that make this a terrain band and not a mission band.
    expect(pedigree?.thermal_field_held_fixed).toBe(true)
    expect(pedigree?.far_field_held_fixed).toBe(true)
    expect(pedigree?.earth_visibility_cloned).toBe(false)
  })
})
