/**
 * useNegotiationStream
 *
 * Connects to the backend WebSocket and processes all incoming events into
 * structured state for the War Room UI.
 *
 * Modes:  'demo'    → /ws/demo/{type}     (scripted, no LLM key)
 *         'live'    → /ws/live/{type}     (real Claude Haiku tool-calling)
 *         'hostile' → /ws/hostile/{type}  (red-team adversarial simulation)
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
  mode:         'demo',   // 'demo' | 'live' | 'hostile'
  purchaserType: 'tough',
  isHostile:    false,
  threatBrief:  null,

  providers:          {},
  thoughts:           [],   // [{id, actor, tag, content}]
  radarData:          [],   // [{dimension, score}]
  convergenceHistory: [],   // [{round, gap, price, purchaser_target, ...}]

  // Standard veto (margin floor breach)
  veto:        null,
  vetoVisible: false,

  // Adversarial deception alerts
  deceptionAlerts:       [],   // all alerts, accumulate
  latestDeceptionAlert:  null, // most recent — drives the flash overlay
  deceptionFlashVisible: false,

  outcome:      null,
  deal:         null,
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

    switch (event.type) {

      // ── Session start ───────────────────────────────────────────────────
      case 'negotiation_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:        'running',
          mode:          prev.mode,
          purchaserType: event.purchaser_type,
          isHostile:     event.mode === 'hostile',
          threatBrief:   event.threat_brief ?? null,
          providers:     event.providers ?? {},
        }))
        break

      // ── Thought feed ────────────────────────────────────────────────────
      case 'thought':
        setState((prev) => {
          // Parse round number from [Round N] in adversarial or strategy tags
          let newRound = prev.currentRound
          if (
            (event.tag === 'STRATEGY' || event.tag === 'ADVERSARIAL_INTENT') &&
            event.content.includes('[Round')
          ) {
            const m = event.content.match(/\[Round (\d+)/)
            if (m) newRound = parseInt(m[1])
          }
          return {
            ...prev,
            currentRound: newRound,
            thoughts: [
              ...prev.thoughts,
              { id: ++_thoughtId, actor: event.actor, tag: event.tag, content: event.content },
            ],
          }
        })
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

      // ── Margin-floor veto (existing providers) ───────────────────────────
      case 'veto':
        if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
        setState((prev) => ({
          ...prev,
          veto: {
            actor:          event.actor,
            message:        event.message,
            proposed_price: event.proposed_price,
            floor_price:    event.floor_price,
          },
          vetoVisible: true,
        }))
        vetoTimerRef.current = setTimeout(
          () => setState((prev) => ({ ...prev, vetoVisible: false })),
          4000,
        )
        break

      // ── Adversarial deception alert ─────────────────────────────────────
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

        // Auto-hide flash after 5 s for CRITICAL, 3 s for WARNING
        if (event.severity === 'CRITICAL') {
          deceptionTimerRef.current = setTimeout(
            () => setState((prev) => ({ ...prev, deceptionFlashVisible: false })),
            5000,
          )
        }
        break
      }

      // ── Negotiation end ──────────────────────────────────────────────────
      case 'negotiation_end':
        setPartial({ status: 'done', outcome: event.outcome, deal: event.deal })
        break

      case 'error':
        setPartial({ status: 'error' })
        break

      default:
        break
    }
  }, [])

  // ── Connect to the appropriate WebSocket endpoint ────────────────────────
  const connect = useCallback(
    (purchaserType = 'tough', mode = 'demo') => {
      if (wsRef.current) wsRef.current.close()

      setState({ ...INITIAL_STATE, status: 'connecting', purchaserType, mode })

      const url =
        mode === 'hostile' ? `${WS_BASE}/ws/hostile/${purchaserType}` :
        mode === 'live'    ? `${WS_BASE}/ws/live/${purchaserType}`    :
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

  return { ...state, connect, reset }
}
