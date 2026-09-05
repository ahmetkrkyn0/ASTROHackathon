import { useMission } from '../../mission/MissionContext'
import ChatPanel from './ChatPanel'
import { useAssistant } from './useAssistant'
import { useDraggableWindow } from './useDraggableWindow'
import './assistant.css'

/**
 * Stable, because the launcher's aria-controls has to point at it, and because
 * shell.css keys the toast stack off `.chat-window.is-open`.
 */
const CHAT_WINDOW_ID = 'analysis-assistant-window'

/**
 * The decision-support assistant, mounted in the globalOverlay slot.
 *
 * The assistant floats above the mission rather than sitting inside it. Both
 * parts stay mounted: hiding the window is a CSS state, so the conversation,
 * the chosen level, a half-typed draft and a request still in flight all
 * survive being minimized.
 */
export function Assistant() {
  const mission = useMission()
  const {
    isOpen,
    unread,
    mode,
    launcherRef,
    toggle,
    close,
    markUnread,
    missionSnapshot,
  } = useAssistant(mission)

  // Only draggable while it is open; a hidden window has nothing to move.
  const { offset, isDragging, handleProps, reset } = useDraggableWindow(isOpen, {
    moves: '.chat-window',
  })

  /**
   * The launcher moves too, and is its own handle.
   *
   * Enabled while it is CLOSED, which is the only time it is on screen. It is
   * a button as well as a handle, so the hook's threshold decides which a
   * press was: under 4px of travel the click goes through and opens the
   * assistant, past it the button moves and the click is suppressed below.
   */
  const launcherDrag = useDraggableWindow(!isOpen)

  // The window id and its class names are published contracts and do NOT vary
  // with mode: shell.css keys the toast stack off `.chat-window.is-open`, and
  // the launcher's aria-controls points at the id. Only the accessible name
  // follows the mode.
  // The cockpit is English and the assistant is Turkish, which is a real
  // inconsistency (HCI review F8). It is not fixed by swapping strings: the
  // grounding layer that blocks fabricated numbers matches Turkish morphology
  // (backend/app/ai_grounding.py -- suffix patterns, Turkish numeral words,
  // `yüzde`), and 182 test lines pin that behaviour. Translating the surface
  // alone would leave that guard matching a language the model no longer
  // speaks, and it would fail open and silently.
  //
  // Until the AI layer is converted as one piece, the language is at least
  // declared rather than sprung on the operator.
  const label = mode === 'planning' ? 'Görev Rehberi' : 'Analiz Asistanı'

  return (
    <>
      {/* Hidden while the window is open. The launcher is how you reach the
          assistant, and once it is on screen the window has its own minimize
          control -- leaving the button there kept a lit toggle underneath a
          panel it could no longer be seen to control, and it crowded the
          Mission Report button beside it. Kept mounted rather than unmounted
          so close() can still return focus to it. */}
      <button
        type="button"
        ref={launcherRef}
        className={`chat-launcher ${isOpen ? 'is-open' : ''} ${unread ? 'has-unread' : ''} ${
          launcherDrag.isDragging ? 'is-dragging' : ''
        }`}
        aria-label={`Open ${label} (Turkish-language assistant)`}
        title={`Open ${label} — this assistant answers in Turkish. Drag to move it.`}
        aria-expanded={isOpen}
        aria-controls={CHAT_WINDOW_ID}
        style={
          launcherDrag.offset.x || launcherDrag.offset.y
            ? {
                transform: `translate(${launcherDrag.offset.x}px, ${launcherDrag.offset.y}px)`,
              }
            : undefined
        }
        {...launcherDrag.handleProps}
        onClick={() => {
          // A drag ends with a click event the browser fires anyway. Opening
          // the assistant because the operator moved its button would be a
          // second thing happening for one gesture.
          if (launcherDrag.didDragRef.current) {
            launcherDrag.didDragRef.current = false
            return
          }
          toggle()
        }}
      >
        {/* The mark: an orbiter surveying the lunar surface.

            LunaPath plans from ORBITAL data and does not run on the rover --
            the README's scope section is explicit that there is no onboard
            perception, and that LiDAR enters only as a line in the energy
            budget. So the spacecraft in the mark is the one the product
            actually depends on: a satellite over the limb of the Moon with
            its sensor footprint on the surface below. That beam is where the
            DEM this entire cockpit reasons about comes from.

            The silhouette is built to survive 22px, which is where it is
            actually drawn. The panels are TALLER than the bus and separated
            from it by a mast gap: an earlier pass had them the same height
            and butted against the body, and bus, masts and panels merged into
            one horizontal bar with no satellite in it. Stepping the height is
            what puts notches in the outline. The beam is open at the bottom
            so it reads as a footprint rather than a closed triangle, and the
            limb is at 42% because it is the thing being surveyed, not the
            subject.

            Verified by rendering at 22px: bus, both masts, both panels, the
            beam and the limb all stay separable. */}
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          {/* The lunar limb. */}
          <path
            d="M2.2 18.6a9.8 3.4 0 0 1 19.6 0"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            opacity="0.42"
          />
          {/* Sensor footprint, widening to the surface. */}
          <path
            d="M12 7.8L7.8 16.6M12 7.8l4.2 8.8"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.3"
            strokeLinecap="round"
          />
          {/* Bus. */}
          <rect x="10.85" y="4.8" width="2.3" height="3" fill="currentColor" />
          {/* Masts, holding the panels off the body. */}
          <path
            d="M10.85 6.3H8.9M13.15 6.3h1.95"
            stroke="currentColor"
            strokeWidth="1.1"
            strokeLinecap="round"
          />
          {/* Solar panels, taller than the bus so the outline steps. */}
          <rect
            x="6.5"
            y="4"
            width="2.4"
            height="4.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          />
          <rect
            x="15.1"
            y="4"
            width="2.4"
            height="4.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.2"
          />
        </svg>
        {unread && <span className="chat-launcher-dot" aria-hidden="true" />}
      </button>

      {/* The drag offset is a transform on top of whatever assistant.css has
          positioned: the stylesheet keeps owning where the window rests, and
          this only says how far the operator has moved it from there. */}
      <div
        id={CHAT_WINDOW_ID}
        className={`chat-window ${isOpen ? 'is-open' : ''} ${isDragging ? 'is-dragging' : ''}`}
        role="dialog"
        aria-label={label}
        style={
          offset.x || offset.y
            ? { transform: `translate(${offset.x}px, ${offset.y}px)` }
            : undefined
        }
      >
        <ChatPanel
          mission={missionSnapshot}
          mode={mode}
          isVisible={isOpen}
          onMinimize={close}
          onAnswerWhileHidden={markUnread}
          dragHandleProps={handleProps}
          onResetPosition={offset.x || offset.y ? reset : undefined}
        />
      </div>
    </>
  )
}
