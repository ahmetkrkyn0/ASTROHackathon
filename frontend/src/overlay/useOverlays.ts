import { createContext, useContext } from 'react'
import type { OverlayLayer } from './types'

export interface OverlayRegistry {
  layers: OverlayLayer[]
  register: (id: string, layers: OverlayLayer[]) => void
  unregister: (id: string) => void
}

export const OverlayContext = createContext<OverlayRegistry | null>(null)

const EMPTY: OverlayRegistry = {
  layers: [],
  register: () => undefined,
  unregister: () => undefined,
}

/**
 * Outside an OverlayProvider this returns a no-op registry rather than
 * throwing: a feature module must stay renderable in isolation.
 */
export function useOverlays(): OverlayRegistry {
  const ctx = useContext(OverlayContext)
  return ctx ?? EMPTY
}
