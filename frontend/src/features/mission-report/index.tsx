import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { REPORT_LAUNCHER_SLOT_ID } from '../../components/TopBar/TopBar'
import { Icon } from '../../components/Fleet/SpecIcons'
import { COPY, readLang } from '../../i18n/reportCopy'
import { useAskAssistant } from '../../intent/AssistantAskContext'
import { useMission } from '../../mission/MissionContext'
import { useMissionRuntime } from '../../mission/MissionRuntimeContext'
import { useTerrainManifest } from '../../mission/useTerrainManifest'
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
  const { planResult, roverId, weights } = useMission()
  const { routePlaybackStep, payloadW, heaterW } = useMissionRuntime()
  const { isOpen, isWaiting, open, close } = useMissionReport(planResult, routePlaybackStep)
  const requestAsk = useAskAssistant()

  /**
   * The region the route was planned over.
   *
   * From the manifest, because that is the only place the extent and the
   * resolution are measured rather than assumed -- never hard-coded, and never
   * a site name, which this system does not record anywhere.
   *
   * The hook shares one in-flight request across every consumer, so asking for
   * it here costs nothing the 3-D view and the corridor were not already
   * paying.
   */
  const { manifest } = useTerrainManifest(roverId, weights)
  const region = useMemo(() => {
    if (!manifest) return null
    const { rows, cols, resolution_m } = manifest.grid
    // Measurements, not a sentence: the modal owns the language, so it owns
    // the separators too.
    return {
      widthKm: (cols * resolution_m) / 1000,
      heightKm: (rows * resolution_m) / 1000,
      resolutionM: resolution_m,
    }
  }, [manifest])

  /**
   * The launcher's own language.
   *
   * Read at mount rather than shared with the modal: the button lives in the
   * top bar and the modal owns the switch, so a context spanning the two would
   * exist for one string. Whatever the operator last chose is what the button
   * says next time the cockpit loads.
   */
  const [launcherCopy] = useState(() => COPY[readLang()])

  /**
   * The bar's anchor, found after it has mounted.
   *
   * Read in an effect rather than during render: this feature and the top bar
   * are siblings under .app-shell, and on the first pass the node may not
   * exist yet. State rather than a ref because finding it has to cause the
   * re-render that actually paints the button.
   */
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  useEffect(() => {
    setSlot(document.getElementById(REPORT_LAUNCHER_SLOT_ID))
  }, [])

  /**
   * Hand the question to the assistant and get out of its way.
   *
   * Closing is not a courtesy: the report is registered after the assistant in
   * the same globalOverlay slot, registration order is paint order, so a
   * full-screen report covers the panel the question just landed in.
   *
   * Nothing is sent. The channel writes the composer; the operator still picks
   * an explanation level and presses send.
   */
  const askAssistant = useCallback(
    (question: string) => {
      requestAsk(question, 'mission-report')
      close()
    },
    [close, requestAsk],
  )

  if (!planResult) return null

  const launcher = !isOpen && (
    <button
      type="button"
      className={`lp-report-launcher ${isWaiting ? 'is-waiting' : ''}`}
      onClick={open}
      title={launcherCopy.launcherTitle}
    >
      <Icon name="report" className="lp-report-launcher-icon" />
      {launcherCopy.launcher}
    </button>
  )

  return (
    <>
      {/* Into the bar when its anchor is there, and in place if it is not --
          a missing anchor should cost the button its position, not its
          existence. */}
      {slot && launcher ? createPortal(launcher, slot) : launcher}
      {isOpen && (
        <MissionReportModal
          plan={planResult}
          payloadW={payloadW}
          heaterW={heaterW}
          onClose={close}
          onAskAssistant={askAssistant}
          region={region}
        />
      )}
    </>
  )
}
