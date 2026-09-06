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
    ask,
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
        {/* The product's own mark, supplied as artwork.

            It replaces a hand-drawn inline SVG of an orbiter. That one was
            currentColor and followed the button's hover state; a raster
            cannot, so hover and focus now read on the border and the
            background alone. The trade is deliberate: this is the mark the
            product is identified by, and the launcher is where an operator
            looks for it.

            The tile it arrived in -- its own dark ground and rounded lavender
            frame -- was cropped away, because the button already is a framed
            tile. What is left is the mark on transparency, so it sits on
            whatever the button's own background happens to be. */}
        <img className="chat-launcher-mark" src="/ui/chatbot_logo.png" alt="" />
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
          ask={ask}
          onMinimize={close}
          onAnswerWhileHidden={markUnread}
          dragHandleProps={handleProps}
          onResetPosition={offset.x || offset.y ? reset : undefined}
        />
      </div>
    </>
  )
}
