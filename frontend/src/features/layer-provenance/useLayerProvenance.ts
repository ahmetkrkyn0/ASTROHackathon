import { useTerrainManifest } from '../../mission/useTerrainManifest'
import { useMission } from '../../mission/MissionContext'
import type { ViewModeId } from '../../mission/types'

/**
 * The map's view modes and the grid layers behind them.
 *
 * 'surface' paints elevation; 'traversability' reads the traversable mask.
 * Kept here rather than guessed in the panel so a renamed view mode fails
 * to compile instead of silently showing the wrong provenance.
 */
export const LAYER_FOR_VIEW: Record<ViewModeId, string> = {
  surface: 'elevation',
  thermal: 'thermal',
  cost: 'cost',
  shadow: 'shadow_ratio',
  traversability: 'traversable',
  slope: 'slope',
  aspect: 'aspect',
}

/**
 * F1 needs nothing this module owns: the manifest is shared with F2a and F7,
 * and cost/traversable provenance already changes with the weights because
 * the shared hook keys on them.
 */
export function useLayerProvenance() {
  const { roverId, weights } = useMission()
  return useTerrainManifest(roverId, weights)
}
