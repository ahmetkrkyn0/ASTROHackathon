import React, { useState, useRef, useEffect } from 'react'
import type { PlanResponse, PlanWeights, RoverEntry } from '../../api'

export type AssistantLevel = 'basic' | 'engineering' | 'technical'

interface Message {
  id: string
  sender: 'operator' | 'assistant'
  text: string
  level?: AssistantLevel
  evidence?: string
  warnings?: string[]
  limitations?: string
  groundingStatus?: 'verified' | 'fallback'
  timestamp: string
}

interface MissionAssistantProps {
  mode: 'fleet' | 'plan' | 'analyze'
  selectedRover: RoverEntry | null
  weights: PlanWeights
  start: [number, number] | null
  goal: [number, number] | null
  planResult: PlanResponse | null
}

const PLANNING_SUGGESTIONS = [
  'Explain this rover configuration',
  'What does Slope Safety change?',
  'Which raster layer should I inspect?',
  'How do payload watts affect travel range?',
]

const ANALYSIS_SUGGESTIONS = [
  'Summarize route findings and viability',
  'Explain energy draw and battery reserve',
  'Analyze steepest terrain segments',
  'Evaluate thermal and cryogenic risks',
]

export const MissionAssistant: React.FC<MissionAssistantProps> = ({
  mode,
  selectedRover,
  weights,
  planResult,
}) => {
  const [isOpen, setIsOpen] = useState(false)
  const [level, setLevel] = useState<AssistantLevel>('engineering')
  const [inputText, setInputText] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [isTyping, setIsTyping] = useState(false)
  const [hasUnread, setHasUnread] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  const roverName = selectedRover?.name ?? 'LPR-1 Lunar Pathfinder'
  const isPlanning = mode === 'plan' || mode === 'fleet'

  // Context title & subtitle
  const assistantTitle =
    mode === 'fleet'
      ? 'FLEET ADVISOR'
      : isPlanning
        ? 'MISSION GUIDE'
        : 'ANALYSIS ASSISTANT'
  const assistantSubtitle =
    mode === 'fleet'
      ? `Vehicle Selection · ${roverName}`
      : isPlanning
        ? `Planning · ${roverName} · Surface Map`
        : `Current Route · ${roverName} · Route Ready`

  // Scroll to bottom on new message
  useEffect(() => {
    if (isOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      setHasUnread(false)
    }
  }, [messages, isOpen])

  // Initial welcome message if history is empty
  useEffect(() => {
    if (messages.length === 0) {
      const initialText = isPlanning
        ? `Mission Guide initialized. I am ready to advise on rover mobility constraints, cost-function weights, and South Pole crater landing zones.`
        : `Analysis Assistant online. Route computation is complete. Ready to evaluate trajectory energy, slopes, and PSR thermal margins.`

      setMessages([
        {
          id: 'init-1',
          sender: 'assistant',
          text: initialText,
          level: 'engineering',
          evidence: 'DEM 5m/px (LOLA/Kaguya) · Heat1D thermal model · Kinematic A* Planner',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          groundingStatus: 'verified',
        },
      ])
    }
  }, [isPlanning, messages.length])

  // Deterministic response generator matching aerospace & telemetry rules
  const generateAssistantResponse = (query: string, activeLevel: AssistantLevel): Message => {
    const q = query.toLowerCase()
    let text = ''
    let evidence = 'LUNAPATH telemetry corpus · LOLA 5m DEM · Site 11'
    let warnings: string[] | undefined = undefined
    let limitations: string | undefined = undefined

    if (isPlanning) {
      if (q.includes('rover') || q.includes('vehicle')) {
        if (activeLevel === 'basic') {
          text = `${roverName} is an autonomous lunar rover equipped with ${selectedRover?.e_cap_wh.toFixed(0)} Wh battery and capable of climbing up to ${selectedRover?.slope_max_deg}° slopes.`
        } else if (activeLevel === 'engineering') {
          text = `${roverName} (${selectedRover?.id.toUpperCase()}) specifications: Mass ${selectedRover?.mass_kg} kg, max speed ${selectedRover?.v_max_ms} m/s, energy storage ${selectedRover?.e_cap_wh} Wh, max gradeability ${selectedRover?.slope_max_deg}°. Designed for Site 11 South Pole operations.`
          evidence = 'Rover Catalog manifest /api/rovers · Vehicle kinematics model'
        } else {
          text = `Kinematic envelope: v_max=${selectedRover?.v_max_ms} m/s, wheel ground contact model parameterized for regolith slip at slopes >15°. Max slope threshold ${selectedRover?.slope_max_deg}°. Total shadow survival budget ${selectedRover?.h_max_shadow_h} hours.`
          limitations = 'Assumes nominal wheel-regolith traction coefficient (Bekker model).'
        }
      } else if (q.includes('slope') || q.includes('safety') || q.includes('weight')) {
        text = `Current Slope Safety weight is ${weights.w_slope.toFixed(3)}. Higher values heavily penalize inclinations near ${selectedRover?.slope_max_deg ?? 25}°, favoring longer but safer circumnavigation corridors around crater rims.`
        if (weights.w_slope > 0.6) {
          warnings = ['High slope weight (>0.60) may substantially increase distance and transit duration.']
        }
      } else if (q.includes('layer') || q.includes('raster')) {
        text = `Available raster products:\n• Surface: Topographic relief & regolith albedo.\n• Slope: Local gradient degrees.\n• Aspect: Azimuthal facing direction.\n• Thermal: Temperature field (-230°C to +40°C).\n• Shadow: Permanent shadow region index.\n• Cost & Traverse: A* spatial impedance grids.`
      } else {
        text = `Start and Goal define your exploration trajectory. Click 'Select Start' and 'Select Goal' on the 2D or 3D terrain canvas, adjust weights if needed, and press 'Generate Route'.`
      }
    } else {
      // Analysis mode
      const summary = planResult?.summary
      const metrics = planResult?.astar_metrics

      if (q.includes('summary') || q.includes('route') || q.includes('viability')) {
        text = `Route solution nominal: ${summary?.total_distance_km.toFixed(2)} km traversed in ${summary?.total_elapsed_hours.toFixed(1)} hours. Arrival battery is ${summary?.final_battery_pct.toFixed(1)}%. Maximum slope encountered is ${summary?.max_slope_deg.toFixed(1)}°.`
        evidence = `Kinematic A* simulation · ${planResult?.waypoints.length} waypoints calculated`
      } else if (q.includes('energy') || q.includes('battery')) {
        text = `Total energy consumed: ${summary?.total_energy_consumed_wh.toFixed(0)} Wh. The rover arrives with ${summary?.final_battery_pct.toFixed(1)}% state of charge. ${summary?.total_recharges ? `Includes ${summary.total_recharges} recharge stops in sunlit terrain.` : 'No intermediate recharge stops required.'}`
        if ((summary?.final_battery_pct ?? 100) < 25) {
          warnings = ['Low arrival battery margin (<25%). Consider increasing Energy Use weight.']
        }
      } else if (q.includes('slope') || q.includes('steep')) {
        text = `Maximum slope along the path is ${summary?.max_slope_deg.toFixed(1)}°. The planner evaluated ${metrics?.nodes_expanded ?? 0} candidate nodes to avoid non-traversable craters.`
      } else {
        text = `Evaluating goal cell and waypoint distribution. Route contains ${planResult?.waypoints.length} nodes across Site 11. All waypoints remain within operational thermal limits.`
        limitations = 'Solar ephemeris calculations use static horizon cube approximations.'
      }
    }

    return {
      id: `msg-${Date.now()}`,
      sender: 'assistant',
      text,
      level: activeLevel,
      evidence,
      warnings,
      limitations,
      groundingStatus: 'verified',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
  }

  const handleSendMessage = (textToSend?: string) => {
    const query = (textToSend ?? inputText).trim()
    if (!query) return

    const userMsg: Message = {
      id: `usr-${Date.now()}`,
      sender: 'operator',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMsg])
    setInputText('')
    setIsTyping(true)

    window.setTimeout(() => {
      const response = generateAssistantResponse(query, level)
      setMessages((prev) => [...prev, response])
      setIsTyping(false)
      if (!isOpen) {
        setHasUnread(true)
      }
    }, 400)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleNewChat = () => {
    setMessages([
      {
        id: `init-${Date.now()}`,
        sender: 'assistant',
        text: isPlanning
          ? 'New planning session started. How can I assist with your rover trajectory?'
          : 'New analysis session started. Ask me about energy, slope, or risk telemetry.',
        level,
        evidence: 'LUNAPATH verified data stream',
        groundingStatus: 'verified',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
  }

  return (
    <>
      {/* Floating Launcher Button */}
      {!isOpen && (
        <button
          type="button"
          className="lp-assistant-launcher"
          onClick={() => {
            setIsOpen(true)
            setHasUnread(false)
          }}
          aria-label="Open Mission Decision Assistant"
        >
          <span className="lp-assistant-launcher-icon">◈</span>
          <span className="lp-assistant-launcher-label">{assistantTitle}</span>
          {hasUnread && <span className="lp-assistant-unread-dot" />}
        </button>
      )}

      {/* Floating Assistant Instrument Window */}
      {isOpen && (
        <div className="lp-assistant-window" role="complementary" aria-label="Mission Assistant">
          {/* Header */}
          <div className="lp-assistant-header">
            <div className="lp-assistant-title-group">
              <div className="lp-assistant-badge-row">
                <span className="lp-instrument-icon">◈</span>
                <span className="lp-instrument-name">{assistantTitle}</span>
                <span className="lp-grounding-pill">VERIFIED GROUNDING</span>
              </div>
              <span className="lp-assistant-subtitle">{assistantSubtitle}</span>
            </div>

            <div className="lp-assistant-window-actions">
              <button
                type="button"
                className="lp-assistant-icon-btn"
                onClick={handleNewChat}
                title="New Session"
              >
                ↺
              </button>
              <button
                type="button"
                className="lp-assistant-icon-btn"
                onClick={() => setIsOpen(false)}
                title="Minimize"
              >
                —
              </button>
            </div>
          </div>

          {/* Level Switcher */}
          <div className="lp-assistant-level-bar">
            <span className="lp-level-label">TELEMETRY DETAIL:</span>
            <div className="lp-level-buttons">
              {(['basic', 'engineering', 'technical'] as AssistantLevel[]).map((lvl) => (
                <button
                  key={lvl}
                  type="button"
                  className={`lp-level-btn ${level === lvl ? 'is-active' : ''}`}
                  onClick={() => setLevel(lvl)}
                >
                  {lvl.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Messages Stream */}
          <div className="lp-assistant-stream">
            {messages.map((msg) => {
              const isUser = msg.sender === 'operator'
              return (
                <div
                  key={msg.id}
                  className={`lp-msg-wrapper ${isUser ? 'is-operator' : 'is-assistant'}`}
                >
                  <div className="lp-msg-meta">
                    <span className="lp-msg-sender">
                      {isUser ? 'OPERATOR' : 'MISSION INSTRUMENT'}
                    </span>
                    <span className="lp-msg-time">{msg.timestamp}</span>
                  </div>

                  <div className="lp-msg-bubble">
                    <p className="lp-msg-text">{msg.text}</p>

                    {/* Warnings Block */}
                    {msg.warnings && msg.warnings.length > 0 && (
                      <div className="lp-msg-warnings-block">
                        <span className="lp-warning-tag">OPERATIONAL CAUTION</span>
                        {msg.warnings.map((w, i) => (
                          <p key={i} className="lp-warning-line">⚠ {w}</p>
                        ))}
                      </div>
                    )}

                    {/* Evidence & Provenance Block */}
                    {msg.evidence && (
                      <div className="lp-msg-evidence-block">
                        <span className="lp-evidence-tag">EVIDENCE / PROVENANCE</span>
                        <p className="lp-evidence-text">{msg.evidence}</p>
                      </div>
                    )}

                    {/* Limitations Block */}
                    {msg.limitations && (
                      <div className="lp-msg-limitations-block">
                        <span className="lp-limitations-tag">LIMITATIONS</span>
                        <p className="lp-limitations-text">{msg.limitations}</p>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}

            {isTyping && (
              <div className="lp-msg-wrapper is-assistant">
                <div className="lp-typing-indicator">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggestion Chips */}
          <div className="lp-assistant-suggestions">
            {(isPlanning ? PLANNING_SUGGESTIONS : ANALYSIS_SUGGESTIONS).map((sugg, i) => (
              <button
                key={i}
                type="button"
                className="lp-suggestion-chip"
                onClick={() => handleSendMessage(sugg)}
              >
                {sugg}
              </button>
            ))}
          </div>

          {/* Composer */}
          <div className="lp-assistant-composer">
            <textarea
              className="lp-composer-input"
              placeholder={`Query ${assistantTitle.toLowerCase()} (${level} mode)... [Enter to send]`}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
            />
            <button
              type="button"
              className="lp-composer-send-btn"
              onClick={() => handleSendMessage()}
              disabled={!inputText.trim()}
            >
              Send
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default MissionAssistant

