import React, { useCallback, useMemo, useState } from 'react'
import { OverlayContext } from './useOverlays'
import type { OverlayLayer } from './types'

/**
 * A file of its own, holding nothing but the component.
 *
 * The provider and the useOverlays hook used to share one file, which costs
 * Fast Refresh: a module that exports both a component and something else
 * cannot be hot-swapped, so every edit here would full-reload the cockpit
 * and drop the loaded grid. Nine feature modules are about to be built
 * against this provider, so the reload would be paid on every one of them.
 * (react-refresh/only-export-components.)
 */
export function OverlayProvider({ children }: { children: React.ReactNode }) {
  const [groups, setGroups] = useState<Record<string, OverlayLayer[]>>({})

  const register = useCallback((id: string, layers: OverlayLayer[]) => {
    setGroups((current) => ({ ...current, [id]: layers }))
  }, [])

  const unregister = useCallback((id: string) => {
    setGroups((current) => {
      if (!(id in current)) return current
      const next = { ...current }
      delete next[id]
      return next
    })
  }, [])

  // Sorted by group id so draw order is stable across re-renders -- object
  // key order would otherwise let a re-registering module jump on top of
  // another module's marks.
  const layers = useMemo(
    () =>
      Object.keys(groups)
        .sort()
        .flatMap((id) => groups[id]),
    [groups],
  )

  const value = useMemo(
    () => ({ layers, register, unregister }),
    [layers, register, unregister],
  )

  return <OverlayContext.Provider value={value}>{children}</OverlayContext.Provider>
}
