import { useEffect, useRef, useState } from 'react'
import type { PlanResponse } from '../../api'

/**
 * Whether the report has already introduced itself in this session.
 *
 * Module scope, not component state: the point is to survive the feature
 * unmounting and remounting as the operator moves between plan and analyze.
 */
let hasAutoOpenedOnce = false

export interface MissionReportState {
  isOpen: boolean
  open: () => void
  close: () => void
}

/**
 * When the report shows itself.
 *
 * The rule is "the rover arrived", not "a route exists": the report opens on
 * the playback head REACHING the last waypoint, so a plan that has been solved
 * but not driven leaves the map alone. PlaybackBar already stops the timer at
 * the last step, so that transition happens exactly once per run.
 *
 * Closing it must stick. Without the dismissal flag the head is still parked
 * on the last step, and any re-render that re-ran the effect would reopen the
 * modal the operator just dismissed. The flag resets when the plan changes,
 * because a newly driven route is a new arrival and deserves its own report.
 */
export function useMissionReport(
  plan: PlanResponse | null,
  playbackStep: number | null,
): MissionReportState {
  const [isOpen, setIsOpen] = useState(false)
  const dismissedRef = useRef(false)
  const prevStepRef = useRef<number | null>(null)
  const prevPlanRef = useRef<PlanResponse | null>(null)

  useEffect(() => {
    if (prevPlanRef.current !== plan) {
      prevPlanRef.current = plan
      dismissedRef.current = false
      prevStepRef.current = null
      setIsOpen(false)
      return
    }

    const total = plan?.waypoints.length ?? 0
    const last = total - 1
    const prev = prevStepRef.current
    prevStepRef.current = playbackStep

    // Needs a real crossing: a previous step that was short of the end, and a
    // current one at it. Opening on `playbackStep === last` alone would fire
    // for a one-waypoint route and for a head dragged straight to the end
    // before anything was driven.
    if (
      total > 1 &&
      !dismissedRef.current &&
      prev !== null &&
      prev < last &&
      playbackStep === last
    ) {
      // Only the FIRST arrival takes the screen. After that the operator knows
      // the report exists and the launcher is enough: someone replaying a
      // specific segment for the fifth time is being interrupted, not helped,
      // by a modal that covers the map they are watching.
      if (!hasAutoOpenedOnce) {
        hasAutoOpenedOnce = true
        setIsOpen(true)
      }
    }
  }, [plan, playbackStep])

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => {
      dismissedRef.current = true
      setIsOpen(false)
    },
  }
}
