import { ApiError, BASE } from './client'

/**
 * The decision-support assistant's transport.
 *
 * One endpoint family, one file. Nothing here reaches into the legacy api.ts:
 * the shared primitives come from ./client, which is what makes this file the
 * template for api/corridor.ts and the rest rather than a special case.
 */

// Re-exported so assistant code has a single import site for its transport.
export { ApiError }

export interface AiChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/**
 * The server's limits on one request, mirrored so the client can respect them.
 *
 * ChatRequest rejects more than MAX_AI_MESSAGES messages and a message longer
 * than MAX_AI_MESSAGE_CHARS with a 422, which is a validation failure the
 * operator can do nothing about. Both are enforced before the request is built.
 */
export const MAX_AI_MESSAGES = 12
export const MAX_AI_MESSAGE_CHARS = 4000

export interface AiEvidenceItem {
  source: string
  label: string
  rawValidity: string | null
  displayPedigree: string | null
}

export interface AiLimitation {
  code: string
  message: string
}

/**
 * Mandatory and never hidden.
 *
 * Distinct from AiLimitation by meaning, not severity: a warning says the
 * evidence's validity, grounding or constraints are materially affected, and
 * no explanation level may drop one. A limitation says what the feature
 * cannot establish. Nothing ever appears in both arrays.
 */
export interface AiWarning {
  code: string
  severity: 'info' | 'caution' | 'critical'
  message: string
  suppressible: false
}

export type ExplanationLevel = 'L1' | 'L2' | 'L3'

export type GroundingStatus = 'verified' | 'blocked' | 'not_applicable'

export interface AiChatResponse {
  answer: string
  evidence: AiEvidenceItem[]
  limitations: AiLimitation[]
  warnings: AiWarning[]
  toolUsage: {
    comparisonUsed: boolean
    readCalls: number
  }
  errorCode: string | null
  groundingStatus: GroundingStatus
  explanationLevel: ExplanationLevel
}

/**
 * Ask the decision-support assistant one question.
 *
 * There is deliberately no /api/compare client here. The comparison stays
 * behind the server-side tool boundary, where its once-per-question budget is
 * counted somewhere the page cannot raise it -- and where the OpenAI key
 * lives, which is why the browser only ever talks to this one route.
 *
 * `mission` is typed `unknown` on purpose: this transport does not decide what
 * a mission snapshot contains. The assistant feature builds and sanitizes it,
 * and the server sanitizes it again -- see features/assistant/aiContext.ts.
 *
 * A comparison takes ~21 s, so callers should not impose a short timeout.
 */
export async function postAiChat(
  messages: AiChatMessage[],
  mission: unknown,
  explanationLevel: ExplanationLevel,
  signal?: AbortSignal,
): Promise<AiChatResponse> {
  const r = await fetch(`${BASE}/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, mission, explanationLevel }),
    signal,
  })
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }))
    throw new ApiError(
      r.status,
      (err as { detail?: string }).detail ?? 'Chat request failed',
    )
  }
  return r.json() as Promise<AiChatResponse>
}
