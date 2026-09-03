import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { selectStableAnalysisCell } from '../../mission/selectors'
import type { MissionValue } from '../../mission/types'
import { buildMissionSnapshot, type AiMissionSnapshot } from './aiContext'

export interface AssistantShell {
  isOpen: boolean
  unread: boolean
  launcherRef: React.RefObject<HTMLButtonElement>
  toggle: () => void
  close: () => void
  markUnread: () => void
  missionSnapshot: AiMissionSnapshot
}

/**
 * The assistant's shell state, which used to live in App.tsx.
 *
 * Everything here is about the floating window: whether it is open, whether an
 * answer arrived while it was not, and where focus goes when it closes. The
 * conversation itself -- turns, draft, pending request, chosen explanation
 * level -- stays inside ChatPanel, which is never unmounted. This is a move,
 * not a rewrite of that state machine.
 */
export function useAssistant(mission: MissionValue): AssistantShell {
  const [isOpen, setIsOpen] = useState(false)
  const [unread, setUnread] = useState(false)
  const launcherRef = useRef<HTMLButtonElement>(null)

  const open = useCallback(() => {
    setIsOpen(true)
    // Cleared on open, deterministically: the dot means "you have not looked
    // since the answer arrived", and opening is looking.
    setUnread(false)
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
    // The launcher is where the operator came from, so it is where they end up.
    launcherRef.current?.focus()
  }, [])

  const toggle = useCallback(() => {
    if (isOpen) close()
    else open()
  }, [close, isOpen, open])

  const markUnread = useCallback(() => setUnread(true), [])

  /**
   * Escape minimizes the assistant, from anywhere.
   *
   * The window is not modal and does not trap focus, so the operator can click
   * the map with the assistant still open -- at which point a handler bound to
   * the window element would never see the key. The listener is document-wide
   * and installed only while the assistant is open.
   *
   * It minimizes and nothing else. No conversation is ever cleared by a key.
   */
  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || event.defaultPrevented) return
      // Escape during IME composition cancels the composition, not the panel.
      if (event.isComposing || event.keyCode === 229) return
      close()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [close, isOpen])

  /**
   * A value snapshot for the panel.
   *
   * Deliberately built from mission values rather than passed as state: the
   * panel receives what the operator has chosen and no way to change any of it.
   * The raw plan is reduced here, before it can reach the wire -- see
   * sanitizePlanForAi.
   *
   * Memoised on the individual fields rather than on the mission object, so
   * switching map layer or dimension does not rebuild the snapshot and churn
   * the panel's suggestions and send callback for a change the assistant does
   * not see.
   */
  const missionSnapshot = useMemo(
    () =>
      buildMissionSnapshot({
        start: mission.start,
        goal: mission.goal,
        roverId: mission.roverId,
        weights: mission.weights,
        // mission.selectedCell is null by design; the assistant's focus is a
        // policy it names explicitly, and it is never the hover cell.
        focusedCell: selectStableAnalysisCell(mission.start, mission.goal),
        plan: mission.planResult,
      }),
    [mission.goal, mission.planResult, mission.roverId, mission.start, mission.weights],
  )

  return { isOpen, unread, launcherRef, toggle, close, markUnread, missionSnapshot }
}
