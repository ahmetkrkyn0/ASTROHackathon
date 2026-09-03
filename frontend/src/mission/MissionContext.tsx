import { createContext, useContext, type ReactNode } from 'react'
import type { FocusTelemetry, MissionValue } from './types'

/**
 * The mission a feature may read.
 *
 * Two contexts, not one, and the split is the point. The stable half changes
 * only when a mission value actually changes; the volatile half changes as the
 * pointer moves and as the route plays back, thirty times a second. A feature
 * that reads the stable half is not dragged into that churn, and -- more
 * importantly -- nothing in the stable half can be mistaken for a value that
 * tracks the mouse.
 */
const MissionContext = createContext<MissionValue | null>(null)
const FocusTelemetryContext = createContext<FocusTelemetry | null>(null)

export function MissionProvider({
  value,
  focusTelemetry,
  children,
}: {
  value: MissionValue
  focusTelemetry: FocusTelemetry
  children: ReactNode
}) {
  return (
    <MissionContext.Provider value={value}>
      <FocusTelemetryContext.Provider value={focusTelemetry}>
        {children}
      </FocusTelemetryContext.Provider>
    </MissionContext.Provider>
  )
}

/**
 * The cockpit's current mission state, read-only.
 *
 * Throws outside a provider rather than handing back a plausible empty
 * mission: a feature rendered outside the shell is a wiring mistake, and a
 * default value would let it render "no route planned" forever instead.
 */
export function useMission(): MissionValue {
  const value = useContext(MissionContext)
  if (!value) {
    throw new Error('useMission must be called inside <MissionProvider>')
  }
  return value
}

/**
 * The map's coordinate readout: latitude, longitude, altitude, temperature.
 *
 * This is NOT the telemetry of `mission.selectedCell`, and the two routinely
 * disagree. It follows `hoverPoint ?? goal ?? start`, and during route playback
 * it follows the waypoint being animated instead -- a new value every 33 ms.
 * It is what the scale line and the LAT/LON/ALT/TMP block display, nothing
 * more.
 *
 * A feature that needs the telemetry of a particular cell should fetch that
 * cell: `fetchCellTelemetry(row, col)`.
 */
export function useFocusTelemetry(): FocusTelemetry {
  const value = useContext(FocusTelemetryContext)
  if (!value) {
    throw new Error('useFocusTelemetry must be called inside <MissionProvider>')
  }
  return value
}
