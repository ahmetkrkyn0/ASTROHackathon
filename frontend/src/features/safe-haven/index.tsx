import { useEffect, useMemo } from 'react'

import { useOverlays } from '../../overlay/useOverlays'
import { capabilityValue } from '../../mission/capability'
import { SafeHavenPanel } from './SafeHavenPanel'
import { safeHavenOverlays } from './overlays'
import { useSafeHaven } from './useSafeHaven'
import './safe-haven.css'

const OVERLAY_ID = 'safe-haven'

export function SafeHaven() {
  const state = useSafeHaven()
  const overlays = useOverlays()

  // MEMOISED: register keys off array identity, and the command carries a
  // converted grid.
  const commands = useMemo(
    () =>
      safeHavenOverlays(
        state.view,
        state.enabled ? capabilityValue(state.field) : null,
      ),
    [state.enabled, state.field, state.view],
  )

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return <SafeHavenPanel {...state} />
}

export default SafeHaven
