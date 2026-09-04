import { useContext } from 'react'
import {
  EMPTY_COMMANDS,
  OverlayCommandsContext,
  OverlayRegistryContext,
  type OverlayRegistry,
} from './OverlayContext'
import type { OverlayCommand } from './types'

/**
 * Register drawing commands for one feature.
 *
 * ```tsx
 * const overlays = useOverlays()
 * // MEMOISED. An array rebuilt every render re-runs the effect forever.
 * const commands = useMemo(() => [{ kind: 'polyline', id: 'route', points, style }], [points])
 * useEffect(() => overlays.register('corridor', commands), [overlays, commands])
 * ```
 *
 * `register` has a stable identity, so it never causes the effect to re-run by
 * itself. Returning its cleanup from the effect is what removes the commands on
 * unmount; a feature owns its own entry and no other.
 */
export function useOverlays(): OverlayRegistry {
  const registry = useContext(OverlayRegistryContext)
  if (!registry) {
    throw new Error('useOverlays must be called inside <OverlayProvider>')
  }
  return registry
}

/**
 * Every registered command, for a renderer.
 *
 * Falls back to the shared empty list outside a provider rather than throwing:
 * MapCanvas is a plain renderer and has to stay usable without the shell around
 * it.
 */
export function useOverlayCommands(): readonly OverlayCommand[] {
  return useContext(OverlayCommandsContext) ?? EMPTY_COMMANDS
}
