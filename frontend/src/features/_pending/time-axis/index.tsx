import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { TimeAxisPanel } from './TimeAxisPanel'
import { timeAxisOverlays } from './overlays'
import { useTimeAxis } from './useTimeAxis'

const OVERLAY_ID = 'time-axis'

export function TimeAxis() {
  const state = useTimeAxis()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(
      OVERLAY_ID,
      timeAxisOverlays(state.cube, state.sliceIndex, state.field, state.manifest, state.plan4d),
    )
    return () => unregister(OVERLAY_ID)
  }, [
    register,
    state.cube,
    state.field,
    state.manifest,
    state.plan4d,
    state.sliceIndex,
    unregister,
  ])

  return <TimeAxisPanel {...state} />
}
