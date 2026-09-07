/**
 * State for the analysis overlay toggles.
 *
 * Fixed hook count: `useBinaryLayer` is called once per entry in a table that
 * is a module constant, written out rather than mapped. A `.map()` over the
 * table would read better and would be wrong -- the rules of hooks require a
 * call count that cannot vary between renders, and this project's eslint
 * config treats that as an error precisely because the failure is silent until
 * it is catastrophic.
 *
 * The list is destructured positionally so adding a layer is a compile error
 * here until its hook is added, rather than a layer that quietly never loads.
 */

import { useCallback, useMemo, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import { useBinaryLayer, type BinaryFieldCapability } from '../../mission/useBinaryField'
import { capabilityValue } from '../../mission/capability'
import { ANALYSIS_LAYERS, type AnalysisLayerId, type AnalysisLayerSpec } from './layers'

export interface AnalysisLayerState {
  readonly spec: AnalysisLayerSpec
  readonly enabled: boolean
  readonly capability: BinaryFieldCapability
}

export interface AnalysisLayersState {
  readonly entries: readonly AnalysisLayerState[]
  toggle: (id: AnalysisLayerId) => void
  /** Ids the operator has switched on, whether or not the data arrived. */
  readonly enabledIds: readonly AnalysisLayerId[]
  /**
   * Which layers actually have data, for the plan-request contributors.
   *
   * A toggle left on from a session where the cache existed must not send a
   * constraint flag now: the backend would answer 422 and it would read like
   * a bug rather than like a missing file.
   */
  readonly available: Readonly<Record<string, boolean>>
}

const [ROUGHNESS, PSR, EARTH, P_TRAV, SLOPE_SIGMA, ELEV_SIGMA, SLOPE_SIGMA_NASA] =
  ANALYSIS_LAYERS

export function useAnalysisLayers(): AnalysisLayersState {
  const { roverId } = useMission()
  const [enabled, setEnabled] = useState<Readonly<Record<string, boolean>>>({})

  // One call per layer, written out. Not a loop -- see the file comment.
  const roughness = useBinaryLayer(ROUGHNESS.layerName, {
    enabled: enabled[ROUGHNESS.id] === true,
    downsample: ROUGHNESS.downsample,
    roverId,
  })
  const psr = useBinaryLayer(PSR.layerName, {
    enabled: enabled[PSR.id] === true,
    downsample: PSR.downsample,
    roverId,
  })
  const earth = useBinaryLayer(EARTH.layerName, {
    enabled: enabled[EARTH.id] === true,
    downsample: EARTH.downsample,
    roverId,
  })
  // `p_traversable` is the one layer here that genuinely depends on the rover:
  // the backend picks the slope limit from `rover_id` before counting how many
  // clones call the cell passable. The other six take it only so the binary URL
  // matches the manifest they were described by.
  const pTraversable = useBinaryLayer(P_TRAV.layerName, {
    enabled: enabled[P_TRAV.id] === true,
    downsample: P_TRAV.downsample,
    roverId,
  })
  const slopeSigma = useBinaryLayer(SLOPE_SIGMA.layerName, {
    enabled: enabled[SLOPE_SIGMA.id] === true,
    downsample: SLOPE_SIGMA.downsample,
    roverId,
  })
  const elevationSigma = useBinaryLayer(ELEV_SIGMA.layerName, {
    enabled: enabled[ELEV_SIGMA.id] === true,
    downsample: ELEV_SIGMA.downsample,
    roverId,
  })
  const slopeSigmaNasa = useBinaryLayer(SLOPE_SIGMA_NASA.layerName, {
    enabled: enabled[SLOPE_SIGMA_NASA.id] === true,
    downsample: SLOPE_SIGMA_NASA.downsample,
    roverId,
  })

  const toggle = useCallback((id: AnalysisLayerId) => {
    setEnabled((previous) => ({ ...previous, [id]: !previous[id] }))
  }, [])

  const entries = useMemo<readonly AnalysisLayerState[]>(
    () => [
      { spec: ROUGHNESS, enabled: enabled[ROUGHNESS.id] === true, capability: roughness },
      { spec: PSR, enabled: enabled[PSR.id] === true, capability: psr },
      { spec: EARTH, enabled: enabled[EARTH.id] === true, capability: earth },
      { spec: P_TRAV, enabled: enabled[P_TRAV.id] === true, capability: pTraversable },
      {
        spec: SLOPE_SIGMA,
        enabled: enabled[SLOPE_SIGMA.id] === true,
        capability: slopeSigma,
      },
      {
        spec: ELEV_SIGMA,
        enabled: enabled[ELEV_SIGMA.id] === true,
        capability: elevationSigma,
      },
      {
        spec: SLOPE_SIGMA_NASA,
        enabled: enabled[SLOPE_SIGMA_NASA.id] === true,
        capability: slopeSigmaNasa,
      },
    ],
    [
      earth,
      elevationSigma,
      enabled,
      pTraversable,
      psr,
      roughness,
      slopeSigma,
      slopeSigmaNasa,
    ],
  )

  const enabledIds = useMemo(
    () => entries.filter((entry) => entry.enabled).map((entry) => entry.spec.id),
    [entries],
  )

  const available = useMemo(
    () =>
      Object.fromEntries(
        entries.map((entry) => [entry.spec.id, capabilityValue(entry.capability) !== null]),
      ),
    [entries],
  )

  return { entries, toggle, enabledIds, available }
}
