import { useEffect } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CorridorPanel } from './CorridorPanel'
import { corridorOverlays } from './overlays'
import { useCorridor } from './useCorridor'

const OVERLAY_ID = 'corridor'

export function CorridorFeature() {
  const { corridor, frame, segments, error } = useCorridor()
  const { register, unregister } = useOverlays()

  useEffect(() => {
    register(OVERLAY_ID, corridorOverlays(corridor, frame))
    return () => unregister(OVERLAY_ID)
  }, [corridor, frame, register, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Corridor</p>
      <CorridorPanel corridor={corridor} segments={segments} error={error} />
    </section>
  )
}
