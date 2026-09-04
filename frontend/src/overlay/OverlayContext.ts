import { createContext } from 'react'
import type { OverlayCommand } from './types'

/**
 * The overlay registry a feature writes to.
 *
 * The provider itself lives in ./OverlayProvider so this file exports no
 * component: mixing a component with other exports breaks Fast Refresh for the
 * module, which react-refresh/only-export-components flags and this project
 * treats as an error. Same split, and the same reason, as
 * mission/MissionContext.
 */
export interface OverlayRegistry {
  /**
   * Publish this feature's commands, replacing whatever it published before.
   *
   * Returns the cleanup. `commands` must be a memoised array: an array rebuilt
   * on every render makes a registration effect re-run forever.
   */
  register: (featureId: string, commands: OverlayCommand[]) => () => void
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
