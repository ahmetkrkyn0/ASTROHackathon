import { createContext, useContext } from 'react'
import type { MissionRuntime } from './types'

/**
 * The volatile runtime values consumed by route analysis.
 *
 * The provider lives separately to preserve the Fast Refresh boundary for
 * this hook-only module.
 */
export const MissionRuntimeContext = createContext<MissionRuntime | null>(null)

export function useMissionRuntime(): MissionRuntime {
  const value = useContext(MissionRuntimeContext)
  if (!value) {
    throw new Error('useMissionRuntime must be called inside <MissionRuntimeProvider>')
  }
  return value
}
