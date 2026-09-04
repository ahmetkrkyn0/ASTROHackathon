import type { ReactNode } from 'react'
import { FocusTelemetryContext, MissionActionsContext, MissionContext } from './MissionContext'
import type { FocusTelemetry, MissionActions, MissionValue } from './types'

/**
 * Publishes both halves of the mission to every feature below.
 *
 * A component and nothing else. The contexts and the hooks that read them are
 * in ./MissionContext; keeping them apart is what lets Fast Refresh work on
 * this file, and it is why `react-refresh/only-export-components` stays an
 * error rather than being switched off.
 */
export function MissionProvider({
  value,
  focusTelemetry,
  actions,
  children,
}: {
  value: MissionValue
  focusTelemetry: FocusTelemetry
  actions: MissionActions
  children: ReactNode
}) {
  return (
    <MissionContext.Provider value={value}>
      <MissionActionsContext.Provider value={actions}>
        <FocusTelemetryContext.Provider value={focusTelemetry}>
          {children}
        </FocusTelemetryContext.Provider>
      </MissionActionsContext.Provider>
    </MissionContext.Provider>
  )
}
