/**
 * The analysis rasters, as a table.
 *
 * These are deliberately NOT view modes. `layer-picker` is a seven-way radio
 * over what the base map *is* -- surface, slope, cost -- and exactly one can
 * be showing. An analysis raster is a different kind of thing: it sits on top
 * of whichever base layer the operator chose, several can be on at once, and
 * turning one on does not take anything away.
 *
 * That distinction is load-bearing for PSR in particular. A permanently
 * shadowed region is measured evidence, not a forbidden zone, and it is
 * checked *against* our own shadow model -- so it has to be drawable over the
 * shadow layer. A radio button would have made that impossible and, in doing
 * so, would have quietly claimed PSR is a planning constraint.
 *
 * Adding a layer is one entry here plus, for a coarse product, nothing at all:
 * the renderer takes the field's own rows and cols and never stretches it.
 */

import {
  EARTH_VISIBILITY_STOPS,
  P_TRAVERSABLE_STOPS,
  PSR_MASK_RGB,
  ROUGHNESS_STOPS,
  SIGMA_STOPS,
  type RGB,
} from '../../colormap'

export type AnalysisLayerId =
  | 'roughness'
  | 'psr'
  | 'earth_visibility'
  | 'p_traversable'
  | 'slope_sigma'
  | 'elevation_sigma'
  | 'slope_sigma_nasa'

/** How a field's numbers become colour. */
export type AnalysisRender =
  /** A scalar ramp between the layer's own measured min and max. */
  | { mode: 'ramp'; stops: RGB[] }
  /** A boolean mask: cells at or above `threshold` painted, the rest untouched. */
  | { mode: 'mask'; color: RGB; threshold: number }

export interface AnalysisLayerSpec {
  readonly id: AnalysisLayerId
  /** The backend layer name. Not a view-mode id -- see mission/types.ts. */
  readonly layerName: string
  readonly label: string
  /** One line, in the operator's terms. What the numbers mean. */
  readonly blurb: string
  /**
   * What the layer does NOT claim.
   *
   * Every one of these three is routinely over-read, and the panel shows this
   * line beside the toggle rather than burying it in a tooltip. Roughness is a
   * 100 m block statistic being drawn on 5 m cells; PSR is evidence rather
   * than a no-go area; Earth visibility is geometry rather than link budget.
   */
  readonly limit: string
  readonly render: AnalysisRender
  readonly opacity: number
  /**
   * Fine cells per fetched cell. All three Tier-1 rasters are served on the
   * fine grid, so this is the transport budget rather than a scale decision:
   * 250 000 f32 values is 1 MB per layer and three of them may be on at once.
   */
  readonly downsample: number
}

export const ANALYSIS_LAYERS: readonly AnalysisLayerSpec[] = [
  {
    id: 'roughness',
    layerName: 'roughness',
    label: 'Roughness',
    blurb: 'LOLA LDRM height-residual spread, in metres.',
    limit: 'A 100 m block statistic shown on 5 m cells, not each cell’s own roughness.',
    render: { mode: 'ramp', stops: ROUGHNESS_STOPS },
    opacity: 0.62,
    downsample: 2,
  },
  {
    id: 'psr',
    layerName: 'psr',
    label: 'PSR mask',
    blurb: 'NASA PGDA permanently shadowed regions, 20 m product.',
    limit: 'Measured evidence and a check on our shadow model. Not a forbidden region.',
    render: { mode: 'mask', color: PSR_MASK_RGB, threshold: 0.5 },
    opacity: 0.55,
    downsample: 2,
  },
  {
    id: 'earth_visibility',
    layerName: 'earth_visibility',
    label: 'Earth visibility',
    blurb: 'Fraction of the sampled span with the Earth above the local horizon.',
    limit: 'Line-of-sight geometry only. Says nothing about link budget or antenna pointing.',
    render: { mode: 'ramp', stops: EARTH_VISIBILITY_STOPS },
    opacity: 0.58,
    downsample: 2,
  },

  /*
   * B3 -- what NASA's 100 statistical DEM clones disagree about.
   *
   * Four layers and deliberately not one. The first two are OUR ensemble over
   * the clones (DERIVED); the last two are NASA's own published error model
   * (MODEL). Those are different kinds of claim -- a spread we measured versus
   * a spread somebody else modelled -- and folding them under one label would
   * be the provenance flattening the whole layer-provenance feature exists to
   * prevent. The badge beside each is what says which is which.
   */
  {
    id: 'p_traversable',
    layerName: 'p_traversable',
    label: 'P(traversable)',
    blurb: 'Share of NASA’s DEM clones that call this cell passable for this rover.',
    limit:
      'Depends on the selected rover’s slope limit. 0 and 1 are both certain; only 0.05–0.95 is disagreement.',
    render: { mode: 'ramp', stops: P_TRAVERSABLE_STOPS },
    opacity: 0.6,
    downsample: 2,
  },
  {
    id: 'slope_sigma',
    layerName: 'slope_sigma',
    label: 'Slope σ (ours)',
    blurb: 'Standard deviation of slope across the clone ensemble, in degrees.',
    limit: 'Our own spread over NASA’s clones, computed with np.gradient. DERIVED, not measured.',
    render: { mode: 'ramp', stops: SIGMA_STOPS },
    opacity: 0.58,
    downsample: 2,
  },
  {
    id: 'elevation_sigma',
    layerName: 'elevation_sigma',
    label: 'Elevation σ (NASA)',
    blurb: 'NASA’s published total height uncertainty, in metres.',
    limit: 'NASA’s error MODEL (toterr), not a measurement and not our ensemble.',
    render: { mode: 'ramp', stops: SIGMA_STOPS },
    opacity: 0.58,
    downsample: 2,
  },
  {
    id: 'slope_sigma_nasa',
    layerName: 'slope_sigma_nasa',
    label: 'Slope σ (NASA)',
    blurb: 'NASA’s published slope uncertainty, in degrees.',
    limit:
      'NASA’s error MODEL (slperr). Ranges about three times wider than our ensemble — not the same quantity.',
    render: { mode: 'ramp', stops: SIGMA_STOPS },
    opacity: 0.58,
    downsample: 2,
  },
]

export function analysisLayerById(id: AnalysisLayerId): AnalysisLayerSpec {
  const spec = ANALYSIS_LAYERS.find((entry) => entry.id === id)
  if (!spec) throw new Error(`unknown analysis layer: ${id}`)
  return spec
}
