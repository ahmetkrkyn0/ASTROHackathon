/**
 * A2 -- the illumination corridor cube, bound to the shared mission clock.
 *
 * The cube is `[T, 125, 125]` slice-major on the coarse grid. Which slice is
 * drawn comes from `missionTimeSliceIndex`, so moving the one mission clock
 * moves this layer along with the Earth-visibility timeline and everything
 * else that varies with time -- spec 5.8. A slider of its own would be a
 * second clock.
 *
 * `enforced` is false throughout: this is the layer half of A2. The planner is
 * not gated on the corridor, and the panel says so rather than letting a drawn
 * corridor imply the route respected it. Section 9's rule is that an
 * unfinished tier leaves the read-only layer and never the half-built
 * constraint -- half a constraint produces a wrong route, half a layer just
 * shows less.
 */

import { useEffect, useMemo, useState } from 'react'

import { useMission } from '../../mission/MissionContext'
import { hasMissionEpoch, missionTimeSliceIndex } from '../../mission/missionTime'
import {
  CAPABILITY_IDLE,
  CAPABILITY_LOADING,
  capabilityFromError,
  capabilityFromModel,
  capabilityValue,
  type Capability,
} from '../../mission/capability'
import { isDataUnavailable } from '../../net/errors'
import { fetchIlluminationCorridor, type CorridorFieldName, type CorridorManifest } from '../../net/analysis'
import { cubeFrom, type SeriesCube } from '../../net/series'
import { getFloat32 } from '../../net/client'

/** Eight slices of six hours: two days, which is where the corridor moves. */
const N_SLICES = 8
const SLICE_HOURS = 6
const COARSEN = 4

export interface CorridorState {
  readonly enabled: boolean
  setEnabled: (enabled: boolean) => void
  readonly fieldId: CorridorFieldName
  setFieldId: (id: CorridorFieldName) => void
  readonly manifest: Capability<CorridorManifest>
  readonly cube: SeriesCube | null
  readonly cubeError: string | null
  readonly loadingCube: boolean
  /** Which slice the mission clock is in. */
  readonly sliceIndex: number
  readonly needsEpoch: boolean
}

export function useIlluminationCorridor(): CorridorState {
  const { roverId, missionTime } = useMission()
  const [enabled, setEnabled] = useState(false)
  const [fieldId, setFieldId] = useState<CorridorFieldName>('corridor')
  const [manifest, setManifest] = useState<Capability<CorridorManifest>>(CAPABILITY_IDLE)
  const [cube, setCube] = useState<SeriesCube | null>(null)
  const [cubeError, setCubeError] = useState<string | null>(null)
  const [loadingCube, setLoadingCube] = useState(false)

  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null
  const needsEpoch = startUtc === null

  useEffect(() => {
    if (!enabled || !startUtc) {
      setManifest(CAPABILITY_IDLE)
      return
    }
    const controller = new AbortController()
    setManifest(CAPABILITY_LOADING)
    fetchIlluminationCorridor(
      { startUtc, roverId, nSlices: N_SLICES, sliceHours: SLICE_HOURS, coarsen: COARSEN },
      controller.signal,
    )
      .then((response) => {
        if (controller.signal.aborted) return
        // A static shadow model still returns a cube, and the contract says it
        // carries no guarantee. `capabilityFromModel` keeps `static` as ready
        // and the panel calls it out; only `unavailable` withholds the layer.
        setManifest(capabilityFromModel(response.shadow_model, response))
      })
      .catch((error: unknown) => {
        const next = capabilityFromError(error, {
          isDataUnavailable: isDataUnavailable(error),
          signal: controller.signal,
        })
        if (next) setManifest(next)
      })
    return () => controller.abort()
  }, [enabled, roverId, startUtc])

  const value = capabilityValue(manifest)
  const binaryUrl = value?.fields[fieldId]?.binary_url ?? null
  const shape = value
    ? { slices: value.binary_format.shape[0], rows: value.grid.rows, cols: value.grid.cols }
    : null

  useEffect(() => {
    if (!enabled || !binaryUrl || !shape) {
      setCube(null)
      setCubeError(null)
      return
    }
    const controller = new AbortController()
    setLoadingCube(true)
    setCubeError(null)
    // The URL comes from the manifest and already carries the epoch, rover,
    // slice count and coarsen it was computed with. `getFloat32` prepends
    // /api, so the manifest's own prefix is stripped rather than doubled.
    const path = binaryUrl.startsWith('/api/') ? binaryUrl.slice('/api'.length) : binaryUrl

    getFloat32(path, controller.signal)
      .then(({ data }) => {
        if (controller.signal.aborted) return
        // cubeFrom throws when the payload does not fill the declared shape,
        // which is the only failure that would otherwise draw a real corridor
        // for the wrong hour.
        setCube(cubeFrom(data, shape))
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setCube(null)
        setCubeError(error instanceof Error ? error.message : 'Corridor cube unavailable')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingCube(false)
      })
    return () => controller.abort()
    // shape is rebuilt each render from the manifest, so its three numbers are
    // the dependencies rather than the object holding them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, binaryUrl, shape?.slices, shape?.rows, shape?.cols])

  const sliceIndex = useMemo(
    () => missionTimeSliceIndex(missionTime, value?.n_slices ?? 0),
    [missionTime, value?.n_slices],
  )

  return {
    enabled,
    setEnabled,
    fieldId,
    setFieldId,
    manifest,
    cube,
    cubeError,
    loadingCube,
    sliceIndex,
    needsEpoch,
  }
}
