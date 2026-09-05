import { useMission } from '../../mission/MissionContext'
import ChatPanel from './ChatPanel'
import { useAssistant } from './useAssistant'
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
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <path
            d="M4.5 5.5h15v10h-8.5L6.5 19v-3.5h-2z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
          <path
            d="M9 12.5v-2.5M12 12.5v-4.5M15 12.5v-1.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        {unread && <span className="chat-launcher-dot" aria-hidden="true" />}
      </button>

      <div
        id={CHAT_WINDOW_ID}
        className={`chat-window ${isOpen ? 'is-open' : ''}`}
        role="dialog"
        aria-label={label}
      >
        <ChatPanel
          mission={missionSnapshot}
          mode={mode}
          isVisible={isOpen}
          onMinimize={close}
          onAnswerWhileHidden={markUnread}
        />
      </div>
    </>
  )
}
