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
  const { offset, isDragging, handleProps, reset } = useDraggableWindow(isOpen)

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
        className={`chat-launcher ${isOpen ? 'is-open' : ''} ${unread ? 'has-unread' : ''}`}
        aria-label={`Open ${label} (Turkish-language assistant)`}
        title={`Open ${label} — this assistant answers in Turkish`}
        aria-expanded={isOpen}
        aria-controls={CHAT_WINDOW_ID}
        onClick={toggle}
      >
        {/* The mark: a route solved around an obstacle, start to goal.

            LunaPath does not run on the rover -- the README is explicit that
            it is a ground-layer tool planning globally from orbital data, with
            no onboard perception. An antenna talking to a vehicle was the
            wrong metaphor and a speech bubble was no metaphor at all. What
            this product does, in one line, is find a way across a surface
            under competing costs, and the route is what the assistant talks
            about in both of its modes.

            The composition carries the meaning rather than decorating it. The
            crater sits ON the straight line between the two endpoints, so the
            path bending over it reads as a decision the solver made and not as
            an ornamental curve. Endpoints are the map's own vocabulary: start
            a filled node, goal an open ring, distinguished by shape so they do
            not depend on position or colour. The crater is drawn at 45%
            opacity because it is the terrain being reasoned about, not the
            answer.

            Verified by rendering at 22px, the size it is actually drawn: all
            three elements stay separable. */}
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          {/* The obstacle, on the direct line the route cannot take. */}
          <ellipse
            cx="12"
            cy="11.9"
            rx="3.5"
            ry="2.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            opacity="0.45"
          />
          {/* The solved path, bowing clear of it. */}
          <path
            d="M4.4 7.2C8 2.6 17.4 5 19.6 16.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
          {/* Start: filled node. */}
          <circle cx="4.4" cy="7.2" r="2" fill="currentColor" stroke="none" />
          {/* Goal: open ring. */}
          <circle
            cx="19.6"
            cy="16.6"
            r="2.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
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
