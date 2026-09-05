import { createContext, useContext } from 'react'
import type { AssistantAsk, AssistantAskOrigin } from './types'

/**
 * The ask channel, published as two contexts rather than one.
 *
 * The split is the same one MissionValue/MissionActions makes, for the same
 * reason: the reader gets a value and the writer gets a function, and neither
 * gets the other. The assistant can see an ask and cannot raise one; the report
 * can raise one and cannot read, clear, or replay the channel.
 *
 * The provider lives in its own file to keep the Fast Refresh boundary for this
 * hook-only module.
 */
export type RequestAsk = (question: string, origin: AssistantAskOrigin) => void

export const AssistantAskContext = createContext<AssistantAsk | null | undefined>(
  undefined,
)
export const RequestAskContext = createContext<RequestAsk | null>(null)

/**
 * The pending ask, or null when there is none.
 *
 * `undefined` is the "no provider" state and null is the real empty value, so
 * calling this outside the shell throws instead of looking like a channel that
 * never delivers.
 */
export function useAssistantAsk(): AssistantAsk | null {
  const value = useContext(AssistantAskContext)
  if (value === undefined) {
    throw new Error('useAssistantAsk must be called inside <AssistantAskProvider>')
  }
  return value
}

export function useAskAssistant(): RequestAsk {
  const request = useContext(RequestAskContext)
  if (!request) {
    throw new Error('useAskAssistant must be called inside <AssistantAskProvider>')
  }
  return request
}
