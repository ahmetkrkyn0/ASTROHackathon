import React from 'react'
import { MissionContext } from './MissionContext'
import type { MissionValue } from './MissionContext'

/**
 * A file of its own, holding nothing but the component -- same reason as
 * OverlayProvider.tsx. This one wraps the entire cockpit, so a file that
 * cost Fast Refresh here would full-reload the app on every edit to the
 * context's shape. (react-refresh/only-export-components.)
 */
export function MissionProvider({
  value,
  children,
}: {
  value: MissionValue
  children: React.ReactNode
}) {
  return <MissionContext.Provider value={value}>{children}</MissionContext.Provider>
}
