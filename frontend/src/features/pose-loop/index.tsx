import { useEffect } from 'react'
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
  const { register, unregister } = useOverlays()
  // The same shared manifest F1 and F2a read (Gorev 6). A pose in CRS metres
  // and the corridor it is judged against must be placed by the SAME frame;
  // two independent fetches could briefly hold two.
  const { frame } = useTerrainManifest(roverId, weights)

  useEffect(() => {
    register(
      OVERLAY_ID,
      poseOverlays(
        { x_m: state.form.x_m, y_m: state.form.y_m },
        state.result,
        state.corridor,
        frame,
      ),
    )
    return () => unregister(OVERLAY_ID)
  }, [frame, register, state.corridor, state.form.x_m, state.form.y_m, state.result, unregister])

  return (
    <section className="rail-section">
      <p className="panel-kicker">Pose Loop</p>
      <PoseLoopPanel {...state} />
    </section>
  )
}
