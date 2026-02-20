/**
 * useNegotiationStream
 *
 * Connects to the backend WebSocket and processes all incoming events into
 * structured state for the War Room UI.
 *
 * Modes:
 *   'demo'    → /ws/demo/{type}      (scripted, no LLM key)
 *   'live'    → /ws/live/{type}      (real Claude Haiku tool-calling)
 *   'hostile' → /ws/hostile/{type}   (red-team adversarial simulation)
 *   'solo'    → /ws/solo/{type}      (ungrounded LLM — Anchor OFF)
 *   'ab-test' → /ws/ab-test/{type}   (scripted Solo vs Cyborg comparison)
 *
 * A/B Test anchor toggle:
 *   anchorEnabled = true  → Cyborg mode  (tools active, grounded)
 *   anchorEnabled = false → Solo mode    (no tools, susceptible to pressure)
 *
 * New event types handled:
 *   ab_test_start      — metadata for the A/B test session
 *   social_pressure    — provider pressure tactic breakdown
 *   internal_math      — solo agent's hallucinated calculation + ground truth
 *   tool_comparison    — side-by-side hallucination delta
 */

import { useCallback, useEffect, useRef, useState } from 'react'

const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
    (window.location.host.includes('localhost')
      ? 'localhost:8000'
      : window.location.host)

const INITIAL_STATE = {
  status:       'idle',   // idle | connecting | running | done | error
  mode:         'demo',   // 'demo' | 'live' | 'hostile' | 'solo' | 'ab-test'
  purchaserType: 'tough',

  // Existing mode flags
  isHostile:    false,
  threatBrief:  null,

  // A/B Test mode flags
  isAbTest:     false,
  isSolo:       false,
  anchorEnabled: true,  // true = Cyborg (tools ON), false = Solo (tools OFF)
  abTestDescription: null,

  // Standard feeds (shared/cyborg)
  providers:          {},
  thoughts:           [],   // [{id, actor, tag, content, agentType?}]
  radarData:          [],
  convergenceHistory: [],

  // A/B Test split feeds
  soloThoughts:    [],  // thought events tagged agent_type: "solo"
  cyborgThoughts:  [],  // thought events tagged agent_type: "cyborg"

  // Hallucination monitor events
  internalMathEvents:    [],  // internal_math events from solo agent
  socialPressureEvents:  [],  // social_pressure events (from either agent)
  toolComparisonEvents:  [],  // tool_comparison events (the "smoking gun")

  // Standard veto (margin floor breach)
  veto:        null,
  vetoVisible: false,

  // Adversarial deception alerts
  deceptionAlerts:       [],
  latestDeceptionAlert:  null,
  deceptionFlashVisible: false,

  // Final outcomes — solo and cyborg may have different outcomes in ab-test
  outcome:      null,
  deal:         null,
  soloOutcome:  null,
  soloDeal:     null,
  cyborgOutcome: null,
  cyborgDeal:   null,
  currentRound: 0,
}

let _thoughtId = 0

export function useNegotiationStream() {
  const [state, setState]         = useState(INITIAL_STATE)
  const wsRef                     = useRef(null)
  const vetoTimerRef              = useRef(null)
  const deceptionTimerRef         = useRef(null)

  const setPartial = (patch) =>
    setState((prev) => ({ ...prev, ...patch }))

  const handleEvent = useCallback((raw) => {
    let event
    try {
      event = typeof raw === 'string' ? JSON.parse(raw) : raw
    } catch {
      return
    }

    const agentType = event.agent_type  // "solo" | "cyborg" | undefined

    switch (event.type) {

      // ── Session start (standard + solo) ─────────────────────────────────
      case 'negotiation_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:        'running',
          mode:          prev.mode,
          anchorEnabled: prev.anchorEnabled,
          purchaserType: event.purchaser_type,
          isHostile:     event.mode === 'hostile',
          isSolo:        event.mode === 'solo' || agentType === 'solo',
          isAbTest:      prev.isAbTest,
          threatBrief:   event.threat_brief ?? null,
          providers:     event.providers ?? {},
        }))
        break

      // ── A/B Test session start ───────────────────────────────────────────
      case 'ab_test_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:            'running',
          mode:              'ab-test',
          anchorEnabled:     prev.anchorEnabled,
          purchaserType:     event.purchaser_type ?? prev.purchaserType,
          isAbTest:          true,
          isSolo:            false,
          providers:         event.providers ?? {},
          abTestDescription: event.description ?? null,
        }))
        break

      // ── Thought feed ─────────────────────────────────────────────────────
      case 'thought':
        setState((prev) => {
          let newRound = prev.currentRound
          if (
            (event.tag === 'STRATEGY' || event.tag === 'ADVERSARIAL_INTENT') &&
            event.content?.includes('[Round')
          ) {
            const m = event.content.match(/\[Round (\d+)/)
            if (m) newRound = parseInt(m[1])
          }

          const thoughtEntry = {
            id:        ++_thoughtId,
            actor:     event.actor,
            tag:       event.tag,
            content:   event.content,
            agentType: agentType,
          }

          const nextThoughts      = [...prev.thoughts, thoughtEntry]
          const nextSoloThoughts  = agentType === 'solo'
            ? [...prev.soloThoughts, thoughtEntry]
            : prev.soloThoughts
          const nextCyborgThoughts = agentType === 'cyborg'
            ? [...prev.cyborgThoughts, thoughtEntry]
            : prev.cyborgThoughts

          return {
            ...prev,
            currentRound:   newRound,
            thoughts:       nextThoughts,
            soloThoughts:   nextSoloThoughts,
            cyborgThoughts: nextCyborgThoughts,
          }
        })
        break

      // ── Social pressure event ────────────────────────────────────────────
      case 'social_pressure':
        setState((prev) => ({
          ...prev,
          socialPressureEvents: [...prev.socialPressureEvents, event],
        }))
        break

      // ── Internal math event (solo hallucination) ─────────────────────────
      case 'internal_math':
        setState((prev) => ({
          ...prev,
          internalMathEvents: [...prev.internalMathEvents, event],
        }))
        break

      // ── Tool comparison event (A/B test smoking gun) ─────────────────────
      case 'tool_comparison':
        setState((prev) => ({
          ...prev,
          toolComparisonEvents: [...prev.toolComparisonEvents, event],
        }))
        break

      // ── Radar chart update ───────────────────────────────────────────────
      case 'radar':
        setState((prev) => ({
          ...prev,
          radarData: [
            { dimension: 'Price',    score: event.data.price_score },
            { dimension: 'Speed',    score: event.data.speed_score },
            { dimension: 'Warranty', score: event.data.warranty_score },
          ],
        }))
        break

      // ── Convergence line update ──────────────────────────────────────────
      case 'convergence':
        setState((prev) => ({
          ...prev,
          convergenceHistory: [...prev.convergenceHistory, event.data],
        }))
        break

      // ── Margin-floor veto ────────────────────────────────────────────────
      case 'veto':
        if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
        setState((prev) => ({
          ...prev,
          veto: {
            actor:          event.actor,
            message:        event.message,
            proposed_price: event.proposed_price,
            floor_price:    event.floor_price,
            agentType:      agentType,
          },
          vetoVisible: true,
        }))
        vetoTimerRef.current = setTimeout(
          () => setState((prev) => ({ ...prev, vetoVisible: false })),
          4000,
        )
        break

      // ── Adversarial deception alert ──────────────────────────────────────
      case 'deception_alert': {
        const alert = {
          tactic:   event.tactic,
          severity: event.severity,
          round:    event.round,
          message:  event.message,
          details:  event.details ?? {},
        }

        if (deceptionTimerRef.current) clearTimeout(deceptionTimerRef.current)

        setState((prev) => ({
          ...prev,
          deceptionAlerts:      [...prev.deceptionAlerts, alert],
          latestDeceptionAlert:  alert,
          deceptionFlashVisible: event.severity === 'CRITICAL',
        }))

        if (event.severity === 'CRITICAL') {
          deceptionTimerRef.current = setTimeout(
            () => setState((prev) => ({ ...prev, deceptionFlashVisible: false })),
            5000,
          )
        }
        break
      }

      // ── Negotiation end ──────────────────────────────────────────────────
      case 'negotiation_end': {
        setState((prev) => {
          // In A/B test mode, track solo and cyborg outcomes separately
          if (prev.isAbTest) {
            if (agentType === 'solo') {
              return {
                ...prev,
                soloOutcome: event.outcome,
                soloDeal:    event.deal,
                // Don't mark 'done' yet — cyborg still coming
              }
            }
            if (agentType === 'cyborg') {
              return {
                ...prev,
                status:        'done',
                cyborgOutcome: event.outcome,
                cyborgDeal:    event.deal,
                outcome:       event.outcome,  // Final session outcome = cyborg
                deal:          event.deal,
              }
            }
          }
          // Standard single-agent end
          return {
            ...prev,
            status:  'done',
            outcome: event.outcome,
            deal:    event.deal,
          }
        })
        break
      }

      case 'error':
        setPartial({ status: 'error' })
        break

      default:
        break
    }
  }, [])

  // ── Connect to the appropriate WebSocket endpoint ─────────────────────────
  const connect = useCallback(
    (purchaserType = 'tough', mode = 'demo') => {
      if (wsRef.current) wsRef.current.close()

      const isAbTest = mode === 'ab-test'
      const isSolo   = mode === 'solo'

      setState({
        ...INITIAL_STATE,
        status:        'connecting',
        purchaserType,
        mode,
        isAbTest,
        isSolo,
        anchorEnabled: !isSolo,  // solo = anchor OFF, everything else = anchor ON
      })

      const url =
        mode === 'hostile'  ? `${WS_BASE}/ws/hostile/${purchaserType}`  :
        mode === 'live'     ? `${WS_BASE}/ws/live/${purchaserType}`     :
        mode === 'solo'     ? `${WS_BASE}/ws/solo/${purchaserType}`     :
        mode === 'ab-test'  ? `${WS_BASE}/ws/ab-test/${purchaserType}` :
                              `${WS_BASE}/ws/demo/${purchaserType}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen    = () => setPartial({ status: 'connecting' })
      ws.onmessage = (e) => handleEvent(e.data)
      ws.onerror   = () => setPartial({ status: 'error' })
      ws.onclose   = () => setState((prev) =>
        prev.status !== 'done' ? { ...prev, status: 'idle' } : prev
      )
    },
    [handleEvent],
  )

  // ── Toggle anchor (Cyborg ↔ Solo) without re-connecting ──────────────────
  const setAnchorEnabled = useCallback((enabled) => {
    setPartial({ anchorEnabled: enabled, isSolo: !enabled })
  }, [])

  const reset = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
    if (deceptionTimerRef.current) clearTimeout(deceptionTimerRef.current)
    setState(INITIAL_STATE)
  }, [])

  useEffect(() => () => {
    if (wsRef.current) wsRef.current.close()
    if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
    if (deceptionTimerRef.current) clearTimeout(deceptionTimerRef.current)
  }, [])

  return { ...state, connect, reset, setAnchorEnabled }
}
