import React, { useCallback, useMemo, useState } from 'react'
import { AssistantAskContext, RequestAskContext } from './AssistantAskContext'
import { nextAsk, type AssistantAsk, type AssistantAskOrigin } from './types'

/**
 * Holds the pending ask, and nothing else.
 *
 * `requestAsk` is memoised so a feature may put it in an effect's dependency
 * list, the same guarantee useMissionActions gives.
 */
export const AssistantAskProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [ask, setAsk] = useState<AssistantAsk | null>(null)

  const requestAsk = useCallback((question: string, origin: AssistantAskOrigin) => {
    const trimmed = question.trim()
    if (!trimmed) return
    setAsk((previous) => nextAsk(previous, trimmed, origin))
  }, [])

  const value = useMemo(() => ask, [ask])

  return (
    <AssistantAskContext.Provider value={value}>
      <RequestAskContext.Provider value={requestAsk}>{children}</RequestAskContext.Provider>
    </AssistantAskContext.Provider>
  )
}
