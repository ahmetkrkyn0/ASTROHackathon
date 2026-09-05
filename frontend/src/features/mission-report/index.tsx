import { useMission } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'
import { MissionReportModal } from './MissionReportModal'
import { useMissionReport } from './useMissionReport'
import './report.css'

/**
 * The post-drive mission report, mounted in the globalOverlay slot.
 *
 * globalOverlay and not a rail, for the reason the report exists at all: it
 * takes the whole screen once the rover has arrived, so the rail panels are
 * not competing with a question the report already answers. It is also why the
 * modal unmounts on close rather than hiding under a class -- unlike the
 * assistant, it holds no conversation and no draft, and everything it shows is
 * recomputed from the plan in one pass.
 */
export function MissionReport() {
  const { planResult } = useMission()
  const { routePlaybackStep, payloadW, heaterW } = useMissionRuntime()
  const { isOpen, open, close } = useMissionReport(planResult, routePlaybackStep)

  if (!planResult) return null

  return (
    <>
      {!isOpen && (
        <button type="button" className="lp-report-launcher" onClick={open}>
          <span className="lp-report-launcher-icon" aria-hidden="true">
            ▤
          </span>
          Görev Raporu
        </button>
      )}
      {isOpen && (
        <MissionReportModal
          plan={planResult}
          payloadW={payloadW}
          heaterW={heaterW}
          onClose={close}
        />
      )}
    </>
  )
}
