import { useEffect, useMemo } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { TimeAxisPanel } from './TimeAxisPanel'
import { timeAxisOverlays } from './overlays'
import { useTimeAxis } from './useTimeAxis'

const OVERLAY_ID = 'time-axis'

export function TimeAxis() {
  const state = useTimeAxis()
  const overlays = useOverlays()

  // MEMOISED: register keys off the array's identity, and this one carries a
  // whole converted slice, so rebuilding it every render would be both a loop
  // and a quarter of a million pointless writes.
  const commands = useMemo(
    () =>
      timeAxisOverlays(state.cube, state.sliceIndex, state.field, state.manifest, state.plan4d),
    [state.cube, state.field, state.manifest, state.plan4d, state.sliceIndex],
  )

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return <TimeAxisPanel {...state} />
}
