/**
 * Which layers this deployment actually has, discovered from the manifest.
 *
 * Spec 5.1: capability is discovered, never assumed. `GET /api/terrain` lists
 * only the layers that are loaded -- `roughness` and `psr` are simply absent
 * from `layers` on a machine that never ran `build_roughness_cache.py` -- so
 * the manifest is the cheapest and most honest answer to "can this cockpit
 * show X", and it is one request the shell already makes.
 *
 * A feature asks this rather than the analysis-layers feature, because a
 * feature reaching into another feature's internals is the coupling the shell
 * contract forbids. The manifest belongs to the mission layer; both of them
 * read it from here.
 */

import { useMemo } from 'react'

import type { PlanWeights } from '../api'
import type { LayerManifestEntry, Validity } from '../net/types'
import { useTerrainManifest } from './useTerrainManifest'

export interface LayerAvailability {
  /** True only when the manifest lists this layer. Absent means not loaded. */
  has: (layerName: string) => boolean
  /** The manifest entry, for units, range and provenance. Null when absent. */
  entry: (layerName: string) => LayerManifestEntry | null
  /** The layer's provenance label, or null when it carries none. */
  validity: (layerName: string) => Validity | null
  /** True while the manifest is still in flight -- neither present nor absent. */
  loading: boolean
  error: string | null
}

export function useLayerAvailability(
  roverId: string,
  weights: PlanWeights,
): LayerAvailability {
  const { manifest, loading, error } = useTerrainManifest(roverId, weights)

  return useMemo(() => {
    const layers = manifest?.layers ?? null
    const entry = (name: string) => layers?.[name] ?? null
    return {
      // `loading` deliberately does not make this true. A layer is not
      // available until we have been told it is, and a control that flickers
      // on during load then disappears is worse than one that appears late.
      has: (name: string) => entry(name) !== null,
      entry,
      validity: (name: string) => entry(name)?.validity ?? null,
      loading,
      error,
    }
  }, [manifest, loading, error])
}
