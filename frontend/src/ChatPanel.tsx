import { useCallback, useEffect, useRef, useState } from 'react'
import { postAiChat, type AiChatMessage, type AiChatResponse } from './api'
import type { AiMissionSnapshot } from './aiContext'

interface ChatTurn {
  id: number
  role: 'user' | 'assistant'
  content: string
  evidence?: AiChatResponse['evidence']
  limitations?: AiChatResponse['limitations']
  comparisonUsed?: boolean
}

// The server caps the conversation; matching it here keeps the panel from
// sending a request it knows will be rejected.
const MAX_HISTORY = 12

// A comparison is measured at ~21 s, so the wait is real and worth naming.
// The model may also answer from the current plan alone, so the copy says
// "may" rather than promising a computation that might not happen.
const PENDING_NOTE = 'Analyzing mission… questions that compare mission profiles may take ~20 s.'

const PEDIGREE_LABEL: Record<string, string> = {
  measurement: 'Ö · measurement',
  model: 'M · model',
  demo: 'D · demo',
}

interface ChatPanelProps {
  /** A value snapshot. The panel gets no setters, by design. */
  mission: AiMissionSnapshot
}

export default function ChatPanel({ mission }: ChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const turnIdRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const node = scrollRef.current
    if (node) node.scrollTop = node.scrollHeight
  }, [turns, pending])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  const send = useCallback(async () => {
    const question = draft.trim()
    if (!question || pending) return

    const id = turnIdRef.current + 1
    turnIdRef.current = id
    const history: ChatTurn[] = [...turns, { id, role: 'user', content: question }]

    setTurns(history)
    setDraft('')
    setError(null)
    setPending(true)

    const controller = new AbortController()
    abortRef.current = controller

    // Only user and assistant turns travel; the server rejects any other role.
    const wire: AiChatMessage[] = history
      .slice(-MAX_HISTORY)
      .map((turn) => ({ role: turn.role, content: turn.content }))

    try {
      const reply = await postAiChat(wire, mission, controller.signal)
      const replyId = turnIdRef.current + 1
      turnIdRef.current = replyId
      setTurns((current) => [
        ...current,
        {
          id: replyId,
          role: 'assistant',
          content: reply.answer,
          evidence: reply.evidence,
          limitations: reply.limitations,
          comparisonUsed: reply.toolUsage.comparisonUsed,
        },
      ])
    } catch (err) {
      if (controller.signal.aborted) return
      setError((err as Error).message)
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setPending(false)
    }
  }, [draft, mission, pending, turns])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  return (
    <section className="rail-section chat-panel">
      <div className="rail-section-header">
        <div>
          <p className="panel-kicker">Decision Support</p>
          <h2 className="panel-title">Mission Assistant</h2>
          <p className="panel-description">
            Answers from LunaPath's own calculations. It reads the mission; it never
            changes the route.
          </p>
        </div>
      </div>

      <div className="chat-log" ref={scrollRef}>
        {turns.length === 0 && !pending && (
          <p className="chat-empty">
            Ask about the current route, a specific cell, or how the four mission
            profiles compare.
          </p>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className={`chat-turn chat-turn--${turn.role}`}>
            <span className="chat-role">{turn.role === 'user' ? 'You' : 'Assistant'}</span>
            <p className="chat-text">{turn.content}</p>

            {turn.limitations && turn.limitations.length > 0 && (
              <ul className="chat-limitations">
                {turn.limitations.map((limitation) => (
                  <li key={limitation.code}>{limitation.message}</li>
                ))}
              </ul>
            )}

            {((turn.evidence && turn.evidence.length > 0) || turn.comparisonUsed) && (
              <div className="chat-chips">
                {turn.comparisonUsed && (
                  <span className="chat-chip chat-chip--tool">profile comparison</span>
                )}
                {turn.evidence?.map((item, index) => (
                  <span key={`${item.source}-${index}`} className="chat-chip">
                    {item.label}
                    {item.displayPedigree && (
                      <em className="chat-chip-pedigree">
                        {PEDIGREE_LABEL[item.displayPedigree] ?? item.displayPedigree}
                      </em>
                    )}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {pending && <p className="chat-pending">{PENDING_NOTE}</p>}
        {error && <p className="chat-error">{error}</p>}
      </div>

      <div className="chat-composer">
        <textarea
          className="chat-input"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about this mission…"
          rows={2}
          maxLength={4000}
          disabled={pending}
        />
        <button
          type="button"
          className="chat-send"
          onClick={() => void send()}
          disabled={pending || draft.trim().length === 0}
        >
          {pending ? 'Working…' : 'Send'}
        </button>
      </div>
    </section>
  )
}
