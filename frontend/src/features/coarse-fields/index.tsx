import { useEffect, useMemo } from 'react'

import { useOverlays } from '../../overlay/useOverlays'
import { capabilityValue } from '../../mission/capability'
import { CoarseFieldsPanel } from './CoarseFieldsPanel'
import { coarseFieldCommands } from './overlays'
import { useCoarseFields } from './useCoarseFields'
import './coarse-fields.css'

const OVERLAY_ID = 'coarse-fields'

export function CoarseFields() {
  const state = useCoarseFields()
  const overlays = useOverlays()

  // MEMOISED: register keys off array identity, and a categorical field emits
  // one converted grid per category.
  const commands = useMemo(() => {
    const field = state.enabled ? capabilityValue(state.field) : null
    return field ? coarseFieldCommands(state.spec, field) : []
  }, [state.enabled, state.field, state.spec])

  useEffect(() => overlays.register(OVERLAY_ID, commands), [overlays, commands])

  return <CoarseFieldsPanel {...state} />
}

export default CoarseFields
