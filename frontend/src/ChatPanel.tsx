import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ApiError,
  MAX_AI_MESSAGE_CHARS,
  postAiChat,
  type AiChatMessage,
  type AiChatResponse,
  type ExplanationLevel,
} from './api'
import { windowMessages, type AiMissionSnapshot } from './aiContext'

interface ChatTurn {
  id: number
  role: 'user' | 'assistant'
  content: string
  evidence?: AiChatResponse['evidence']
  limitations?: AiChatResponse['limitations']
  warnings?: AiChatResponse['warnings']
  comparisonUsed?: boolean
  groundingStatus?: AiChatResponse['groundingStatus']
  errorCode?: string | null
  /** The request never reached a verdict, so no contract fields exist for it. */
  transportFailure?: boolean
}

/** Which analysis the operator asked for, when that is actually knowable. */
type PendingIntent = 'generic' | 'cell' | 'compare'

interface Suggestion {
  id: string
  label: string
  query: string
  intent: PendingIntent
  note?: string
}

const PEDIGREE_LABEL: Record<string, string> = {
  measurement: 'Ölçüm',
  model: 'Model',
  demo: 'Demo',
}

/** Derived from the evidence source, never asked of the model. */
const CONTEXT_LABEL: Record<string, string> = {
  'current-plan': 'Mevcut rota',
  'cell-telemetry': 'Hücre telemetrisi',
  'profile-comparison': 'Profil karşılaştırması',
}

// Severity is spelled out as well as coloured, so it is never carried by
// colour alone.
const SEVERITY_LABEL: Record<string, string> = {
  info: 'Bilgi',
  caution: 'Dikkat',
  critical: 'Kritik',
}

// An explicit choice, never inferred from what the operator types. Nothing is
// sent until one of these is confirmed, so a visual default never passes for a
// decision the operator made.
const LEVELS: Array<{ id: ExplanationLevel; label: string; hint: string }> = [
  { id: 'L1', label: 'Basit', hint: 'Sade dil, en fazla üç büyüklük' },
  { id: 'L2', label: 'Mühendislik', hint: 'İlgili büyüklükler ve gerekçe' },
  { id: 'L3', label: 'Teknik', hint: 'Veri yoğun, provenance ayrıntılı' },
]

// A comparison is measured at ~21 s. The note appears only where a comparison
// is actually implicated -- on its own suggestion, and while one is known to be
// running -- because attaching it to every request would advertise a
// computation that usually does not happen.
const COMPARE_NOTE = 'Profil karşılaştırmaları yaklaşık 20 saniye sürebilir.'

const PENDING_STAGE: Record<PendingIntent, string> = {
  generic: 'Görev verileri inceleniyor…',
  cell: 'Seçili nokta analiz ediliyor…',
  compare: 'Görev profilleri karşılaştırılıyor…',
}

/**
 * Operator-facing copy for the semantic outcomes the endpoint reports.
 *
 * The server's own Turkish message is rendered underneath rather than instead:
 * it is the more specific of the two -- a missing-context refusal names what is
 * missing -- while this line says what kind of answer the operator just got.
 */
const ERROR_COPY: Record<string, string> = {
  'E-SCOPE':
    'Bu asistan yalnızca mevcut LunaPath görev analiziyle ilgili soruları yanıtlıyor.',
  'E-UNSUPPORTED': 'Bu analiz mevcut sürümde desteklenmiyor.',
  'E-CONTEXT': 'Bu soru için önce gerekli görev bağlamını oluştur.',
  'E-BUDGET': 'Bu istek mevcut analiz bütçesini aşıyor.',
}

// Deliberately says nothing about which service failed. Provider configuration
// and unloaded grid data both answer 503, the two are indistinguishable from
// here, and the raw detail can name a server environment variable.
const TRANSPORT_TITLE = 'Analiz asistanı şu anda kullanılamıyor.'
const TRANSPORT_HINT =
  'Bu istek tamamlanamadı; ana görev ekranı açık kalmaya devam ediyor.'

// Roughly five lines, after which the composer scrolls instead of growing.
const COMPOSER_MAX_PX = 122

// Far enough from the cap to be actionable, close enough to stay out of the way.
const COUNTER_THRESHOLD = 3600

// Below this distance from the bottom the operator is following the
// conversation; above it they have scrolled back to read and must not be yanked.
const NEAR_BOTTOM_PX = 48

interface ChatPanelProps {
  /** A value snapshot. The panel gets no setters, by design. */
  mission: AiMissionSnapshot
  /**
   * Whether the panel is on screen.
   *
   * The panel is never unmounted -- the floating shell hides it -- so this is
   * how it learns that it is out of sight. It moves focus when it comes back,
   * and reports an answer that landed while nobody was looking. It changes
   * nothing else: a hidden panel still sends, still waits, still receives.
   */
  isVisible?: boolean
  /** Rendered as a header control when the panel lives in a floating shell. */
  onMinimize?: () => void
  /** A reply arrived while hidden. Used for one dot, nothing more. */
  onAnswerWhileHidden?: () => void
}

export default function ChatPanel({
  mission,
  isVisible = true,
  onMinimize,
  onAnswerWhileHidden,
}: ChatPanelProps) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const [pendingIntent, setPendingIntent] = useState<PendingIntent>('generic')
  const [statusCue, setStatusCue] = useState('')

  const [level, setLevel] = useState<ExplanationLevel>('L2')
  const [levelChosen, setLevelChosen] = useState(false)

  const turnIdRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)
  const lastTurnRef = useRef<HTMLDivElement>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const levelRefs = useRef<Array<HTMLButtonElement | null>>([])
  const nearBottomRef = useRef(true)
  // Bumped by "Yeni sohbet" so a reply still in flight cannot land in a
  // conversation the operator has already cleared.
  const generationRef = useRef(0)
  // Read inside send(), which is created before the reply arrives: visibility
  // can change while the request is in flight, so the flag is read late.
  const visibleRef = useRef(isVisible)

  useEffect(() => {
    visibleRef.current = isVisible
  }, [isVisible])

  useEffect(() => {
    return () => abortRef.current?.abort()
  }, [])

  // Coming back into view: put the caret where the operator will type, unless
  // the level is still unchosen and the composer is therefore disabled.
  useEffect(() => {
    if (!isVisible) return
    const composer = composerRef.current
    if (composer && !composer.disabled) {
      composer.focus()
      return
    }
    levelRefs.current[LEVELS.findIndex((option) => option.id === level)]?.focus()
    // level is deliberately not a dependency: this runs on becoming visible,
    // not every time the operator picks a different level.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isVisible])

  // Auto-grow, and shrink back when the draft is cleared or reset.
  useEffect(() => {
    const node = composerRef.current
    if (!node) return
    node.style.height = 'auto'
    node.style.height = `${Math.min(node.scrollHeight, COMPOSER_MAX_PX)}px`
  }, [draft])

  useEffect(() => {
    const node = scrollRef.current
    if (!node || !nearBottomRef.current) return
    const last = lastTurnRef.current
    // A long answer is revealed from its first line rather than its last.
    if (last && last.offsetHeight > node.clientHeight * 0.75) {
      node.scrollTop = Math.max(0, last.offsetTop - 8)
    } else {
      node.scrollTop = node.scrollHeight
    }
  }, [turns, pending])

  const handleScroll = useCallback(() => {
    const node = scrollRef.current
    if (!node) return
    nearBottomRef.current =
      node.scrollHeight - node.scrollTop - node.clientHeight < NEAR_BOTTOM_PX
  }, [])

  const send = useCallback(
    async (rawQuestion: string, intent: PendingIntent) => {
      const question = rawQuestion.trim()
      if (!question || pending || !levelChosen) return

      const generation = generationRef.current
      const id = turnIdRef.current + 1
      turnIdRef.current = id
      const history: ChatTurn[] = [...turns, { id, role: 'user', content: question }]

      setTurns(history)
      setDraft('')
      setPendingIntent(intent)
      setStatusCue('')
      setPending(true)
      // The operator just spoke, so following their own message is expected.
      nearBottomRef.current = true

      const controller = new AbortController()
      abortRef.current = controller

      // Only user and assistant turns travel; the server rejects any other
      // role, and refuses more messages than it will accept.
      const wire: AiChatMessage[] = windowMessages(
        history.map((turn) => ({ role: turn.role, content: turn.content })),
      )

      try {
        const reply = await postAiChat(wire, mission, level, controller.signal)
        if (controller.signal.aborted || generationRef.current !== generation) return
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
            groundingStatus: reply.groundingStatus,
            errorCode: reply.errorCode,
          },
        ])
        setStatusCue('Yanıt hazır.')
        if (!visibleRef.current) onAnswerWhileHidden?.()
      } catch (err) {
        if (controller.signal.aborted || generationRef.current !== generation) return
        // The detail is never rendered: a 503 from this route can name a server
        // environment variable. It stays in the console, where the operator is
        // not looking and a developer is.
        console.warn(
          'AI chat request failed',
          err instanceof ApiError ? err.status : err,
        )
        const replyId = turnIdRef.current + 1
        turnIdRef.current = replyId
        setTurns((current) => [
          ...current,
          { id: replyId, role: 'assistant', content: '', transportFailure: true },
        ])
        setStatusCue('İstek tamamlanamadı.')
      } finally {
        if (abortRef.current === controller) abortRef.current = null
        if (generationRef.current === generation) setPending(false)
      }
    },
    [level, levelChosen, mission, onAnswerWhileHidden, pending, turns],
  )

  const startNewChat = useCallback(() => {
    generationRef.current += 1
    abortRef.current?.abort()
    abortRef.current = null
    setTurns([])
    setDraft('')
    setPending(false)
    setPendingIntent('generic')
    setStatusCue('')
    nearBottomRef.current = true
    // The chosen explanation level survives, and so does every piece of mission
    // state -- this button owns nothing but the transcript.
  }, [])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void send(draft, 'generic')
    }
  }

  const chooseLevel = (next: ExplanationLevel) => {
    setLevel(next)
    setLevelChosen(true)
  }

  const handleLevelKey = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const delta =
      event.key === 'ArrowRight' || event.key === 'ArrowDown'
        ? 1
        : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
          ? -1
          : 0
    if (delta === 0) return
    event.preventDefault()
    const next = (index + delta + LEVELS.length) % LEVELS.length
    chooseLevel(LEVELS[next].id)
    levelRefs.current[next]?.focus()
  }

  /**
   * Only the analyses the current mission context can actually support.
   *
   * The checks mirror the server-side gate's own presence rules, so a chip is
   * never an offer to run something that will come back refused.
   */
  const suggestions = useMemo<Suggestion[]>(() => {
    const items: Suggestion[] = []
    if (mission.currentPlan !== null) {
      items.push({
        id: 'summary',
        label: 'Rotayı özetle',
        query: 'Mevcut rotayı özetle.',
        intent: 'generic',
      })
      items.push({
        id: 'energy',
        label: 'Enerji ve bataryayı açıkla',
        query: 'Bu rotanın enerji tüketimini ve batarya durumunu açıkla.',
        intent: 'generic',
      })
    }
    if (mission.focusedCell !== null) {
      const { row, col } = mission.focusedCell
      items.push({
        id: 'cell',
        // Named for the cell that is actually in context -- the placed goal or
        // start -- not wherever the pointer last passed.
        label: mission.goal ? 'Hedef hücreyi analiz et' : 'Başlangıç hücresini analiz et',
        // The coordinates are stated rather than left implicit. The server's
        // routing context carries only "a cell is selected", not which one, so
        // an unqualified "analyse the selected cell" has nothing to resolve to.
        // Naming the row and column is the path the contract already supports,
        // and both numbers are the operator's own click, not a computed value.
        query: `Satır ${row}, sütun ${col} hücresini analiz et.`,
        intent: 'cell',
      })
    }
    if (mission.start !== null && mission.goal !== null) {
      items.push({
        id: 'compare',
        label: 'Görev profillerini karşılaştır',
        query: 'Dört görev profilini karşılaştır.',
        intent: 'compare',
        note: COMPARE_NOTE,
      })
    }
    return items
  }, [mission])

  const remaining = MAX_AI_MESSAGE_CHARS - draft.length
  const canSend = levelChosen && !pending && draft.trim().length > 0

  return (
    <section className="rail-section chat-panel" aria-label="Analiz Asistanı">
      <header className="chat-header">
        <div className="chat-identity">
          <p className="panel-kicker">Görev karar desteği</p>
          <h2 className="panel-title">Analiz Asistanı</h2>
        </div>
        <div className="chat-header-actions">
          <span className="chat-readonly" title="Asistan görevi okur; rotayı değiştirmez">
            <span className="chat-readonly-dot" aria-hidden="true" />
            Salt okunur
          </span>
          <button
            type="button"
            className="chat-new"
            onClick={startNewChat}
            disabled={turns.length === 0 && !pending}
          >
            Yeni sohbet
          </button>
        </div>
        {/* Minimize only. Clearing the conversation is "Yeni sohbet", which
            stays its own control -- the two must never be the same button. */}
        {onMinimize && (
          <button
            type="button"
            className="chat-minimize"
            onClick={onMinimize}
            aria-label="Analiz Asistanını Küçült"
            title="Analiz Asistanını Küçült"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
              <path
                d="M4 6.5 8 10.5 12 6.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
      </header>

      <div className="chat-level">
        <span className="chat-level-label" id="chat-level-label">
          Nasıl anlatayım?
          {!levelChosen && <em className="chat-level-flag"> · seçim bekleniyor</em>}
        </span>
        <div className="chat-levels" role="radiogroup" aria-labelledby="chat-level-label">
          {LEVELS.map((option, index) => (
            <button
              key={option.id}
              ref={(node) => {
                levelRefs.current[index] = node
              }}
              type="button"
              role="radio"
              aria-checked={levelChosen && level === option.id}
              tabIndex={level === option.id ? 0 : -1}
              title={option.hint}
              className={`chat-level-option ${
                levelChosen && level === option.id ? 'is-active' : ''
              } ${!levelChosen && option.id === 'L2' ? 'is-suggested' : ''}`}
              onClick={() => chooseLevel(option.id)}
              onKeyDown={(event) => handleLevelKey(event, index)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="chat-log" ref={scrollRef} onScroll={handleScroll}>
        {turns.length === 0 && !pending && (
          <div className="chat-intro">
            <p className="chat-intro-title">Bu görev hakkında ne öğrenmek istiyorsun?</p>
            <p className="chat-intro-copy">
              Mevcut rotayı, seçili arazi noktasını ve görev profillerini
              deterministik LunaPath analizleri üzerinden açıklayabilirim.
            </p>
            {suggestions.length > 0 ? (
              <>
                <div className="chat-suggestions">
                  {suggestions.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="chat-suggestion"
                      title={item.note}
                      disabled={!levelChosen || pending}
                      onClick={() => void send(item.query, item.intent)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                {suggestions.some((item) => item.id === 'compare') && (
                  <p className="chat-intro-note">{COMPARE_NOTE}</p>
                )}
              </>
            ) : (
              <p className="chat-intro-blocked">
                Önce bir rota oluştur veya haritada bir başlangıç/hedef noktası seç.
              </p>
            )}
            {!levelChosen && (
              <p className="chat-intro-blocked">
                Soru göndermeden önce bir anlatım seviyesi seç.
              </p>
            )}
          </div>
        )}

        {turns.map((turn, index) => (
          <div
            key={turn.id}
            ref={index === turns.length - 1 ? lastTurnRef : undefined}
            className={`chat-turn chat-turn--${turn.role}`}
          >
            {turn.role === 'user' ? (
              <>
                <span className="chat-role">Sen</span>
                <p className="chat-text">{turn.content}</p>
              </>
            ) : (
              <AssistantTurn turn={turn} />
            )}
          </div>
        ))}

        {pending && (
          <div className="chat-turn chat-turn--assistant chat-turn--pending">
            <span className="chat-role">LunaPath Analiz Asistanı</span>
            <p className="chat-stage">
              {PENDING_STAGE[pendingIntent]}
              <span className="chat-dots" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
            </p>
            {pendingIntent === 'compare' && (
              <p className="chat-stage-note">{COMPARE_NOTE}</p>
            )}
          </div>
        )}
      </div>

      {/* A small status region, not the whole conversation: the answer prose is
          read where it is, and only the pending stage is announced. */}
      <p className="chat-live" role="status" aria-live="polite">
        {pending ? PENDING_STAGE[pendingIntent] : statusCue}
      </p>

      <div className="chat-composer">
        <textarea
          ref={composerRef}
          className="chat-input"
          aria-label="Görev sorusu"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={levelChosen ? 'Görev hakkında sor…' : 'Önce anlatım seviyesini seç'}
          rows={1}
          maxLength={MAX_AI_MESSAGE_CHARS}
          disabled={pending || !levelChosen}
        />
        <div className="chat-composer-foot">
          <span className="chat-hint">
            {draft.length >= COUNTER_THRESHOLD
              ? `${remaining} karakter kaldı`
              : 'Enter gönder · Shift+Enter yeni satır'}
          </span>
          <button
            type="button"
            className="chat-send"
            onClick={() => void send(draft, 'generic')}
            disabled={!canSend}
          >
            Gönder
          </button>
        </div>
      </div>
    </section>
  )
}

function AssistantTurn({ turn }: { turn: ChatTurn }) {
  if (turn.transportFailure) {
    return (
      <>
        <span className="chat-role">LunaPath Analiz Asistanı</span>
        <div className="chat-notice is-caution">
          <p className="chat-notice-title">{TRANSPORT_TITLE}</p>
          <p className="chat-notice-copy">{TRANSPORT_HINT}</p>
        </div>
      </>
    )
  }

  const blocked = turn.groundingStatus === 'blocked'
  // The banner below states this in full, so the matching warning would say it
  // twice. Every other warning -- scope notes, the weight mismatch, constraint
  // validity -- is rendered untouched.
  const warnings = (turn.warnings ?? []).filter((item) => item.code !== 'E-GROUNDING')
  const semanticError = !blocked && turn.errorCode ? turn.errorCode : null
  // E-SCHEMA, E-RANGE and E-NODATA have no headline of their own. Their server
  // message is then the only text on screen, so it has to be the primary line
  // rather than a subdued follow-up to a headline that never rendered.
  const headline = semanticError ? ERROR_COPY[semanticError] : undefined
  const contextLabel = turn.evidence?.[0]
    ? CONTEXT_LABEL[turn.evidence[0].source]
    : undefined

  return (
    <>
      <div className="chat-assistant-head">
        <span className="chat-role">LunaPath Analiz Asistanı</span>
        {contextLabel && <span className="chat-context">{contextLabel}</span>}
      </div>

      {/* The rejected draft is not here to render: the server already replaced
          it with the deterministic fallback before answering. */}
      {blocked && (
        <div className="chat-notice is-caution">
          <p className="chat-notice-title">Yanıt doğrulama kontrolünden geçmedi.</p>
          <p className="chat-notice-copy">Doğrulanmış analiz sonucu gösteriliyor.</p>
        </div>
      )}

      {/* Mandatory, outside the prose and identical at every explanation level:
          the model does not get to decide whether these appear. */}
      {warnings.length > 0 && (
        <ul className="chat-warnings">
          {warnings.map((warning) => (
            <li key={warning.code} className={`chat-warning is-${warning.severity}`}>
              <span className="chat-warning-tag">
                {SEVERITY_LABEL[warning.severity] ?? warning.severity}
              </span>
              <span className="chat-warning-copy">{warning.message}</span>
            </li>
          ))}
        </ul>
      )}

      {headline && <p className="chat-error-title">{headline}</p>}

      {/* Plain text. No markdown renderer is loaded and no HTML is parsed; the
          answer is rendered exactly as the server sent it. */}
      {turn.content && (
        <p className={`chat-text ${headline ? 'is-secondary' : ''}`}>{turn.content}</p>
      )}

      {turn.limitations && turn.limitations.length > 0 && (
        <div className="chat-limitations">
          <span className="chat-block-title">Sınırlamalar</span>
          <ul>
            {turn.limitations.map((limitation) => (
              <li key={limitation.code}>{limitation.message}</li>
            ))}
          </ul>
        </div>
      )}

      {turn.evidence && turn.evidence.length > 0 && (
        <div className="chat-evidence">
          <span className="chat-block-title">Kanıtlar</span>
          {turn.evidence.map((item, index) => (
            <div key={`${item.source}-${index}`} className="chat-evidence-row">
              <span className="chat-evidence-label">{item.label}</span>
              {item.displayPedigree && (
                <span className={`chat-pedigree is-${item.displayPedigree}`}>
                  {PEDIGREE_LABEL[item.displayPedigree] ?? item.displayPedigree}
                </span>
              )}
            </div>
          ))}
          {turn.comparisonUsed && (
            <div className="chat-evidence-row">
              <span className="chat-evidence-label">
                Profil karşılaştırması çalıştırıldı
              </span>
            </div>
          )}
        </div>
      )}
    </>
  )
}
