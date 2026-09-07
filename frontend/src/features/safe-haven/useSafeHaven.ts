/**
 * A1 -- the safe-haven map, its four fields, and the epoch it needs.
 *
 * A safe haven is a cell where a rover can sit out the dark: the Earth below
 * the horizon, no continuous shadow longer than the rover tolerates, and lit
 * at least once in the window. All three are statements about where the Sun
 * and the Earth are, so none of them means anything without a start epoch --
 * which is why this hook does nothing at all until the mission clock has one,
 * and says so rather than picking `now`.
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
import { fetchSafeHaven, type SafeHavenFieldName, type SafeHavenManifest } from '../../net/analysis'

/**
 * Which of the four fields is drawn. One at a time: they share a grid but not
 * a unit -- a boolean, two spans in hours and a driving time -- so a single
 * legend cannot serve two of them, and stacking them would be four washes over
 * the same cells.
 */
export type SafeHavenView = SafeHavenFieldName

export const SAFE_HAVEN_VIEWS: ReadonlyArray<{
  id: SafeHavenView
  label: string
  blurb: string
}> = [
  {
    id: 'safe_haven',
    label: 'Havens',
    blurb: 'Cells a rover can sit out the dark in.',
  },
  {
    id: 'time_to_safe_haven',
    label: 'Time to haven',
    blurb: 'Driving hours to the nearest one. Blank means none is reachable.',
  },
  {
    id: 'max_dark_hours_without_dte',
    label: 'Longest dark',
    blurb: 'Longest continuous shadow with no link to Earth.',
  },
  {
    id: 'earth_below_hours',
    label: 'Earth below',
    blurb: 'Hours with the Earth under the local horizon.',
  },
]

/**
 * The transport budget, not a scale decision.
 *
 * 500x500 f32 is 1 MB per field. The map draws at 500 px, so a downsample of 2
 * is still one value per two screen pixels and costs a quarter as much.
 */
const DOWNSAMPLE = 2

export interface SafeHavenState {
  readonly enabled: boolean
  setEnabled: (enabled: boolean) => void
  readonly view: SafeHavenView
  setView: (view: SafeHavenView) => void
  readonly manifest: Capability<SafeHavenManifest>
  readonly field: BinaryFieldCapability
  /** True when the mission clock has no epoch, which is why nothing loaded. */
  readonly needsEpoch: boolean
}

export function useSafeHaven(): SafeHavenState {
  const { roverId, missionTime } = useMission()
  const [enabled, setEnabled] = useState(false)
  const [view, setView] = useState<SafeHavenView>('safe_haven')
  const [manifest, setManifest] = useState<Capability<SafeHavenManifest>>(CAPABILITY_IDLE)

  const startUtc = hasMissionEpoch(missionTime) ? missionTime.startUtc : null
  const needsEpoch = startUtc === null

  useEffect(() => {
    if (!enabled || !startUtc) {
      setManifest(CAPABILITY_IDLE)
      return
    }

    const controller = new AbortController()
    setManifest(CAPABILITY_LOADING)

    fetchSafeHaven({ startUtc, roverId, downsample: DOWNSAMPLE }, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return
        // A 200 is not evidence there is data: the model block can say
        // `unavailable` inside a perfectly successful response, and `fields`
        // is then empty.
        setManifest(capabilityFromModel(response.safe_haven_model, response))
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

  // Used exactly as the manifest published it: the URL already carries the
  // epoch, rover, span and downsample this manifest was computed with, and a
  // rebuilt one would fetch a payload describing a different computation.
  const binaryUrl = useMemo(() => {
    const value = capabilityValue(manifest)
    return value?.fields[view]?.binary_url ?? null
  }, [manifest, view])

  const field = useBinaryFieldUrl(view, binaryUrl, { enabled })

  return { enabled, setEnabled, view, setView, manifest, field, needsEpoch }
}
