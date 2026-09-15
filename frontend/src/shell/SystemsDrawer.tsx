import { useEffect } from 'react'
import { FEATURES, selectSystemsFeatures } from '../features/registry'
import { useMission } from '../mission/MissionContext'

interface Props {
  open: boolean
  onClose: () => void
}

/**
 * The "Systems & Evidence" surface: a right-sliding, full-height drawer that
 * holds the panels which prove the stack is real (ROS bridge, reality check,
 * provenance, corridor, pose loop, replan triggers) but are not part of the
 * moment-to-moment task. They used to compete for space in the rails; grouping
 * them here is what lets the default cockpit be task + context and nothing more.
 *
 * Contents come from the registry (group: 'systems'), so adding an evidence
 * panel is still one registry line -- it lands here automatically, in a flat
 * grid rather than a named rail.
 */
export default function SystemsDrawer({ open, onClose }: Props) {
  const { missionMode } = useMission()
  const features = selectSystemsFeatures(FEATURES, missionMode)

  // Esc closes it, matching every other dismissible layer in the cockpit.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  return (
    <>
      <div
        className={`lp-systems-backdrop ${open ? 'is-open' : ''}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside
        className={`lp-systems-drawer ${open ? 'is-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Systems and evidence"
        aria-hidden={!open}
      >
        <header className="lp-systems-header">
          <div className="lp-systems-title-block">
            <span className="lp-meta-label">DIAGNOSTICS &amp; PROOF</span>
            <h2 className="lp-systems-title">Systems &amp; Evidence</h2>
          </div>
          <button
            type="button"
            className="lp-systems-close"
            onClick={onClose}
            aria-label="Close systems and evidence"
          >
            ✕
          </button>
        </header>

        <p className="lp-systems-subtitle">
          The ROS bridge, provenance, reality check, corridor, pose loop and replan triggers behind
          this cockpit. Not part of placing a route — kept one click away.
        </p>

        <div className="lp-systems-grid">
          {/*
            The drawer is visually hidden while closed, but CSS cannot stop
            React effects.  Mounting these optional evidence panels at startup
            made them all query their caches immediately, even though the
            operator had not asked to inspect them.  Besides wasting work it
            produced expected 404/422 cache-missing responses in the browser
            console.  They mount only when their surface is actually opened.
          */}
          {open &&
            features.map(({ id, Component }) => (
              <div key={id} className="lp-systems-cell">
                <Component />
              </div>
            ))}
        </div>
      </aside>
    </>
  )
}
