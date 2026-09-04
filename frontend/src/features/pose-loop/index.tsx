import { useEffect, useMemo } from 'react'
import { useMission } from '../../mission/MissionContext'
import { useTerrainManifest } from '../../mission/useTerrainManifest'
import { useOverlays } from '../../overlay/useOverlays'
import { PoseLoopPanel } from './PoseLoopPanel'
import { poseOverlays } from './overlays'
import { usePoseLoop } from './usePoseLoop'

const OVERLAY_ID = 'pose-loop'

export function PoseLoop() {
  const { roverId, weights } = useMission()
  const state = usePoseLoop()
  const overlays = useOverlays()
  // The same shared manifest F1 and F2a read (Gorev 6). A pose in CRS metres
  // and the corridor it is judged against must be placed by the SAME frame;
  // two independent fetches could briefly hold two.
  const { frame } = useTerrainManifest(roverId, weights)

  // MEMOISED: register keys off the array's identity, so a list rebuilt on
  // every render would re-run the effect forever.
  const commands = useMemo(
    () =>
      poseOverlays(
        { x_m: state.form.x_m, y_m: state.form.y_m },
        state.result,
        state.corridor,
        frame,
      ),
    [frame, state.corridor, state.form.x_m, state.form.y_m, state.result],
  )

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Pose Loop</p>
      <PoseLoopPanel {...state} />
    </section>
  )
}
