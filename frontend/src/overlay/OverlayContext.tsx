import { createContext, useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import type { OverlayCommand } from './types'

export interface OverlayRegistry {
  /**
   * Publish this feature's commands, replacing whatever it published before.
   *
   * Returns the cleanup. `commands` must be a memoised array: an array rebuilt
   * on every render makes a registration effect re-run forever.
   */
  register: (featureId: string, commands: OverlayCommand[]) => () => void
}

interface Entry {
  registrationId: number
  commands: OverlayCommand[]
}

/**
 * One shared empty list.
 *
 * Returned by identity whenever nothing is registered, so a renderer can put
 * the command list straight into an effect's dependencies and never redraw for
 * an overlay layer that stayed empty -- which is every frame of the cockpit as
 * it stands today.
 */
export const EMPTY_COMMANDS: readonly OverlayCommand[] = Object.freeze([])

export const OverlayRegistryContext = createContext<OverlayRegistry | null>(null)
export const OverlayCommandsContext =
  createContext<readonly OverlayCommand[]>(EMPTY_COMMANDS)

export function OverlayProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<ReadonlyMap<string, Entry>>(() => new Map())
  const nextRegistrationId = useRef(0)

  const register = useCallback((featureId: string, commands: OverlayCommand[]) => {
    nextRegistrationId.current += 1
    const registrationId = nextRegistrationId.current

    setEntries((current) => {
      const next = new Map(current)
      next.set(featureId, { registrationId, commands })
      return next
    })

    return () => {
      setEntries((current) => {
        // React runs the old effect's cleanup AFTER the new effect body when a
        // dependency changes in a concurrent re-render, so a stale cleanup can
        // arrive once its replacement is already registered. Deleting blindly
        // would erase the live registration and leave the feature invisible
        // until something else re-registered it. The token says whose entry
        // this is.
        if (current.get(featureId)?.registrationId !== registrationId) {
          return current
        }
        const next = new Map(current)
        next.delete(featureId)
        return next
      })
    }
  }, [])

  const registry = useMemo<OverlayRegistry>(() => ({ register }), [register])

  const commands = useMemo<readonly OverlayCommand[]>(() => {
    if (entries.size === 0) {
      return EMPTY_COMMANDS
    }
    // Insertion order, so a feature registered later draws on top.
    const flattened: OverlayCommand[] = []
    for (const entry of entries.values()) {
      flattened.push(...entry.commands)
    }
    return flattened
  }, [entries])

  return (
    <OverlayRegistryContext.Provider value={registry}>
      <OverlayCommandsContext.Provider value={commands}>
        {children}
      </OverlayCommandsContext.Provider>
    </OverlayRegistryContext.Provider>
  )
}
