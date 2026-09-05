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
        {/* A rover antenna sending a beam, not a speech bubble. The bubble is
            the generic web-chat mark and said nothing about what this is; the
            mission speaks to a vehicle on a surface, so the icon is a dish on
            a mast over a horizon, with the transmission arcs rising off it. */}
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          {/* Horizon */}
          <path
            d="M3 19.5h18"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          {/* Mast and dish */}
          <path
            d="M9 19.5l2.4-7.2"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
          <path
            d="M8.4 11.2a3.4 3.4 0 0 1 6.1 1.9l-6.1-1.9z"
            fill="currentColor"
            stroke="none"
          />
          {/* Two transmission arcs */}
          <path
            d="M15.4 8.6a4.2 4.2 0 0 1 1.5 3.2M17.6 6.1a7.2 7.2 0 0 1 2.6 5.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
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
