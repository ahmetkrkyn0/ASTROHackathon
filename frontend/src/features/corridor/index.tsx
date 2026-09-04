import { useEffect, useMemo } from 'react'
import { useOverlays } from '../../overlay/useOverlays'
import { CorridorPanel } from './CorridorPanel'
import { corridorOverlays } from './overlays'
import { useCorridor } from './useCorridor'

const OVERLAY_ID = 'corridor'

export function CorridorFeature() {
  const { corridor, frame, segments, error } = useCorridor()
  const overlays = useOverlays()

  // MEMOISED: register takes the array's identity, so rebuilding it every
  // render would re-run the effect forever.
  const commands = useMemo(() => corridorOverlays(corridor, frame), [corridor, frame])

  // register returns its own cleanup; the canonical registry has no
  // unregister, because a feature owns exactly its own entry.
  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Corridor</p>
      <CorridorPanel corridor={corridor} segments={segments} error={error} />
    </section>
  )
}
