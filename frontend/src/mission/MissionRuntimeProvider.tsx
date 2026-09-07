import type { ReactNode } from 'react'
import { MissionRuntimeContext } from './MissionRuntimeContext'
import type { MissionRuntime } from './types'

/** Publishes runtime-only values without widening the mission snapshot. */
export function MissionRuntimeProvider({
  value,
  children,
}: {
  value: MissionRuntime
  children: ReactNode
}) {
  return <MissionRuntimeContext.Provider value={value}>{children}</MissionRuntimeContext.Provider>
}
