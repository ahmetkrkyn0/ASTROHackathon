import { useEffect, useRef, useState } from 'react'
import type { PlanResponse } from '../../api'

export interface MissionReportState {
  isOpen: boolean
  /**
   * A report is ready and has not been looked at.
   *
   * Drives the launcher's attention state, and nothing else. It is deliberately
   * not the same thing as "a plan exists": the button is on screen from the
   * moment a route is solved, and it only asks to be noticed once the rover has
   * actually finished driving the route the report describes.
   */
  isWaiting: boolean
  open: () => void
  close: () => void
}

/**
 * When the report announces itself.
 *
 * It used to open itself on the first arrival of a session. It no longer opens
 * itself at all -- the operator has just watched a rover finish a route and is
 * looking at the map, and a full-screen modal arriving unasked covers exactly
 * what they were watching. The launcher pulses instead, which says the same
 * thing and takes nothing away.
 *
 * The trigger is unchanged: the playback head REACHING the last waypoint, not
 * the mere existence of a plan. PlaybackBar stops the timer at the last step,
 * so that transition happens exactly once per run, and a plan that has been
 * solved but not driven leaves the bar quiet.
 *
 * The pulse resets per plan rather than per session. A newly driven route is a
 * new result and deserves to be noticed again -- the module-scope flag that
 * used to make this a once-ever event went with the auto-open.
 */
export function useMissionReport(
  plan: PlanResponse | null,
  playbackStep: number | null,
): MissionReportState {
  const [isOpen, setIsOpen] = useState(false)
  const [isWaiting, setIsWaiting] = useState(false)
  const prevStepRef = useRef<number | null>(null)
  const prevPlanRef = useRef<PlanResponse | null>(null)

  useEffect(() => {
    if (prevPlanRef.current !== plan) {
      prevPlanRef.current = plan
      prevStepRef.current = null
      setIsOpen(false)
      // A new plan has not been driven yet, so there is nothing to announce
      // until its own arrival comes round.
      setIsWaiting(false)
      return
    }

    const total = plan?.waypoints.length ?? 0
    const last = total - 1
    const prev = prevStepRef.current
    prevStepRef.current = playbackStep

    // Needs a real crossing: a previous step that was short of the end, and a
    // current one at it. Firing on `playbackStep === last` alone would trigger
    // for a one-waypoint route and for a head dragged straight to the end
    // before anything was driven.
    if (total > 1 && prev !== null && prev < last && playbackStep === last) {
      setIsWaiting(true)
    }
  }, [plan, playbackStep])

  return {
    isOpen,
    isWaiting,
    open: () => {
      setIsOpen(true)
      // Opening is looking. The pulse has done its job and must not resume
      // when the report is closed again.
      setIsWaiting(false)
    },
    close: () => setIsOpen(false),
  }
}
