import { useCallback, useEffect, useRef, useState } from 'react'
import {
  postAiChat,
  type AiChatMessage,
  type AiChatResponse,
  type ExplanationLevel,
} from './api'
import type { AiMissionSnapshot } from './aiContext'

interface ChatTurn {
  id: number
  role: 'user' | 'assistant'
  content: string
  evidence?: AiChatResponse['evidence']
  limitations?: AiChatResponse['limitations']
  warnings?: AiChatResponse['warnings']
  comparisonUsed?: boolean
  grounded?: boolean
}

// The server caps the conversation; matching it here keeps the panel from
// sending a request it knows will be rejected.
const MAX_HISTORY = 12

// A comparison is measured at ~21 s, so the wait is real and worth naming.
// The model may also answer from the current plan alone, so the copy says
// "may" rather than promising a computation that might not happen.
const PENDING_NOTE = 'Analiz ediliyor… profil karşılaştırması gerektiren sorular ~20 sn sürebilir.'

const PEDIGREE_LABEL: Record<string, string> = {
  measurement: 'Ö · ölçüm',
  model: 'M · model',
  demo: 'D · demo',
}

// Explicit choice, never inferred from what the operator types. The contract
// forbids guessing the level, so the panel asks once per session and does not
// remember across reloads.
const LEVELS: Array<{ id: ExplanationLevel; label: string; hint: string }> = [
  { id: 'L1', label: 'Yeniyim', hint: 'Genel hatlarıyla, sade dil' },
  { id: 'L2', label: 'Mühendislik', hint: 'Sayılar ve gerekçeler' },
  { id: 'L3', label: 'Uzman', hint: 'Veri yoğun, ayrıntılı' },
]

interface ChatPanelProps {
  /** A value snapshot. The panel gets no setters, by design. */
  mission: AiMissionSnapshot
}

export default function ChatPanel({ mission }: ChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // L2 is shown as the default, but the operator must confirm a level before
  // the first question so the choice is theirs rather than ours.
  const [level, setLevel] = useState<ExplanationLevel>('L2')
  const [levelChosen, setLevelChosen] = useState(false)

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
    if (!question || pending || !levelChosen) return

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
      const reply = await postAiChat(wire, mission, level, controller.signal)
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
          warnings: reply.warnings,
          comparisonUsed: reply.toolUsage.comparisonUsed,
          grounded: reply.groundingStatus !== 'blocked',
        },
      ])
    } catch (err) {
      if (controller.signal.aborted) return
      setError((err as Error).message)
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setPending(false)
    }
  }, [draft, level, levelChosen, mission, pending, turns])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send()
    }
  }

  const chooseLevel = (next: ExplanationLevel) => {
    setLevel(next)
    setLevelChosen(true)
  }

  return (
    <section className="rail-section chat-panel">
      <div className="rail-section-header">
        <div>
          <p className="panel-kicker">Karar Desteği</p>
          <h2 className="panel-title">Görev Asistanı</h2>
          <p className="panel-description">
            Yanıtlar LunaPath'in kendi hesaplarından gelir. Misyonu okur; rotayı
            hiçbir zaman değiştirmez.
          </p>
        </div>
      </div>

      <div className="chat-level">
        <span className="chat-level-label">
          Nasıl anlatayım?{!levelChosen && <em className="chat-level-flag"> · seç</em>}
        </span>
        <div className="chat-level-options">
          {LEVELS.map((option) => (
            <button
              key={option.id}
              type="button"
              title={option.hint}
              className={`chat-level-option ${
                levelChosen && level === option.id ? 'is-active' : ''
              } ${!levelChosen && option.id === 'L2' ? 'is-suggested' : ''}`}
              onClick={() => chooseLevel(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-log" ref={scrollRef}>
        {turns.length === 0 && !pending && (
          <p className="chat-empty">
            Mevcut rota, belirli bir hücre veya dört görev profilinin
            karşılaştırması hakkında soru sorabilirsin.
          </p>
        )}

        {turns.map((turn) => (
          <div key={turn.id} className={`chat-turn chat-turn--${turn.role}`}>
            <span className="chat-role">{turn.role === 'user' ? 'Sen' : 'Asistan'}</span>

            {/* Mandatory and rendered outside the prose: the model does not get
                to decide whether these appear, and no level hides them. */}
            {turn.warnings && turn.warnings.length > 0 && (
              <ul className="chat-warnings">
                {turn.warnings.map((warning) => (
                  <li key={warning.code} className={`chat-warning is-${warning.severity}`}>
                    {warning.message}
                  </li>
                ))}
              </ul>
            )}

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
                  <span className="chat-chip chat-chip--tool">profil karşılaştırması</span>
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
          placeholder={
            levelChosen ? 'Bu misyon hakkında sor…' : 'Önce anlatım seviyesini seç'
          }
          rows={2}
          maxLength={4000}
          disabled={pending || !levelChosen}
        />
        <button
          type="button"
          className="chat-send"
          onClick={() => void send()}
          disabled={pending || !levelChosen || draft.trim().length === 0}
        >
          {pending ? 'Çalışıyor…' : 'Gönder'}
        </button>
      </div>
    </section>
  )
}
