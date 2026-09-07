/**
 * State for the coarse survival and thermal-dwell fields.
 *
 * One field is shown at a time, unlike the additive analysis rasters. These
 * four share a grid but not a question: `p_safe` and `max_dwell_h` are
 * different quantities in different units, and `best_action` and `side` are
 * categorical with their own legends. Two of them at once would be two legends
 * over one map with no way to tell which colour belonged to which.
 *
 * Both manifests are fetched whenever the panel is open, because the summaries
 * are worth reading on their own -- "28% of blocks can reach no safe set" is a
 * finding whether or not anyone is looking at the map.
 */

import { useEffect, useMemo, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import { hasMissionEpoch } from '../../mission/missionTime'
import { useBinaryFieldUrl, type BinaryFieldCapability } from '../../mission/useBinaryField'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityFromModel,
  capabilityValue,
  type Capability,
} from '../../mission/capability'
import { isDataUnavailable } from '../../net/errors'
import {
  fetchSurvival,
  fetchThermalDwell,
  type SurvivalManifest,
  type ThermalDwellManifest,
} from '../../net/analysis'
import { COARSE_FIELDS, type CoarseFieldId, type CoarseFieldSpec } from './fields'

const COARSEN = 4

export interface CoarseFieldsState {
  readonly enabled: boolean
  setEnabled: (enabled: boolean) => void
  readonly fieldId: CoarseFieldId
  setFieldId: (id: CoarseFieldId) => void
  readonly spec: CoarseFieldSpec
  readonly survival: Capability<SurvivalManifest>
  readonly dwell: Capability<ThermalDwellManifest>
  readonly field: BinaryFieldCapability
  readonly needsEpoch: boolean
  /** True when the survival half is waiting on a goal the operator has not set. */
  readonly needsGoal: boolean
  /** Hours into the mission window these fields were computed for. */
  readonly tHours: number
}

export function useCoarseFields(): CoarseFieldsState {
  const { roverId, missionTime, goal } = useMission()
  const [enabled, setEnabled] = useState(false)
  const [fieldId, setFieldId] = useState<CoarseFieldId>('p_safe')
  const [survival, setSurvival] = useState<Capability<SurvivalManifest>>(CAPABILITY_IDLE)
  const [dwell, setDwell] = useState<Capability<ThermalDwellManifest>>(CAPABILITY_IDLE)

  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null
  /*
   * Both endpoints take `t_hours`, and both are on the same axis as the
   * illumination series, the Earth series and the corridor cube. One clock
   * drives all five: a survival field for hour 0 drawn while the corridor
   * shows hour 18 is two different moments on one map, which looks exactly
   * like one moment.
   *
   * Rounded to two decimals so a clock that moves by seconds does not
   * refetch a field whose slices are hours wide.
   */
  const tHours = Math.round(missionTime.offsetHours * 100) / 100
  const needsEpoch = startUtc === null
  // The `leg` safe set is defined against a goal; without one the backend
  // answers 422 and says so. That is a missing input, not a failure, so the
  // request is not made at all.
  const needsGoal = goal === null

  useEffect(() => {
    if (!enabled || !startUtc || !goal) {
      setSurvival(CAPABILITY_IDLE)
      return
    }
    const controller = new AbortController()
    setSurvival(CAPABILITY_LOADING)
    fetchSurvival(
      {
        startUtc,
        roverId,
        goalRow: goal[0],
        goalCol: goal[1],
        coarsen: COARSEN,
        tHours,
      },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return
        setSurvival(capabilityFromModel(response.survival_model, response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setSurvival(next)
      })
    return () => controller.abort()
  }, [enabled, roverId, startUtc, goal, tHours])

  useEffect(() => {
    if (!enabled || !startUtc) {
      setDwell(CAPABILITY_IDLE)
      return
    }
    const controller = new AbortController()
    setDwell(CAPABILITY_LOADING)
    fetchThermalDwell(
      { startUtc, roverId, coarsen: COARSEN, tHours },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return
        setDwell(capabilityFromModel(response.dwell_model, response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setDwell(next)
      })
    return () => controller.abort()
  }, [enabled, roverId, startUtc, tHours])

  const spec = useMemo(
    () => COARSE_FIELDS.find((entry) => entry.id === fieldId) ?? COARSE_FIELDS[0],
    [fieldId],
  )

  // Used exactly as the manifest published it: the URL carries the epoch,
  // rover, goal, coarsen and state of charge the manifest was computed with.
  const binaryUrl = useMemo(() => {
    if (spec.source === 'survival') {
      const value = capabilityValue(survival)
      return value?.fields[spec.id as 'p_safe' | 'best_action']?.binary_url ?? null
    }
    const value = capabilityValue(dwell)
    return value?.fields[spec.id as 'max_dwell_h' | 'side']?.binary_url ?? null
  }, [dwell, spec, survival])

  const field = useBinaryFieldUrl(spec.id, binaryUrl, { enabled })

  return {
    enabled,
    setEnabled,
    fieldId,
    setFieldId,
    spec,
    survival,
    dwell,
    field,
    needsEpoch,
    needsGoal,
    tHours,
  }
}
