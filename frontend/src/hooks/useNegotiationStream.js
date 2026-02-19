/**
 * useNegotiationStream
 *
 * Connects to the backend WebSocket (demo mode by default) and processes
 * all incoming events into structured state for the War Room UI.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

const WS_BASE =
  import.meta.env.VITE_WS_URL ||
  (window.location.protocol === 'https:' ? 'wss://' : 'ws://') +
    (window.location.host.includes('localhost')
      ? 'localhost:8000'
      : window.location.host)

const INITIAL_STATE = {
  status: 'idle',          // idle | connecting | running | done | error
  mode: 'demo',            // 'demo' | 'live'
  purchaserType: 'tough',
  providers: {},
  thoughts: [],            // [{id, actor, tag, content}]
  radarData: [],           // [{dimension, score}]
  convergenceHistory: [],  // [{round, gap, price, purchaser_target, provider_name}]
  veto: null,              // {message, proposed_price, floor_price, actor} | null
  vetoVisible: false,
  outcome: null,           // null | 'ACCEPT' | 'NO_DEAL'
  deal: null,
  currentRound: 0,
}

let _thoughtId = 0

export function useNegotiationStream() {
  const [state, setState] = useState(INITIAL_STATE)
  const wsRef = useRef(null)
  const vetoTimerRef = useRef(null)

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
      case 'negotiation_start':
        setPartial({
          status: 'running',
          purchaserType: event.purchaser_type,
          providers: event.providers,
          thoughts: [],
          radarData: [],
          convergenceHistory: [],
          veto: null,
          vetoVisible: false,
          outcome: null,
          deal: null,
          currentRound: 0,
        })
        break

      case 'thought':
        setState((prev) => ({
          ...prev,
          thoughts: [
            ...prev.thoughts,
            {
              id: ++_thoughtId,
              actor: event.actor,
              tag: event.tag,
              content: event.content,
            },
          ],
          currentRound: event.tag === 'STRATEGY' && event.content.includes('[Round')
            ? parseInt(event.content.match(/\[Round (\d+)\]/)?.[1] ?? prev.currentRound)
            : prev.currentRound,
        }))
        break

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

      case 'convergence':
        setState((prev) => ({
          ...prev,
          convergenceHistory: [...prev.convergenceHistory, event.data],
        }))
        break

      case 'veto':
        // Clear any existing veto timer
        if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)

        setState((prev) => ({
          ...prev,
          veto: {
            actor: event.actor,
            message: event.message,
            proposed_price: event.proposed_price,
            floor_price: event.floor_price,
          },
          vetoVisible: true,
        }))

        // Auto-hide after 4 seconds
        vetoTimerRef.current = setTimeout(() => {
          setState((prev) => ({ ...prev, vetoVisible: false }))
        }, 4000)
        break

      case 'negotiation_end':
        setPartial({
          status: 'done',
          outcome: event.outcome,
          deal: event.deal,
        })
        break

      case 'error':
        setPartial({ status: 'error' })
        break

      default:
        break
    }
  }, [])

  const connect = useCallback(
    (purchaserType = 'tough', mode = 'demo') => {
      if (wsRef.current) {
        wsRef.current.close()
      }

      setState({ ...INITIAL_STATE, status: 'connecting', purchaserType, mode })

      const url =
        mode === 'live'
          ? `${WS_BASE}/ws/live/${purchaserType}`
          : `${WS_BASE}/ws/demo/${purchaserType}`

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => setPartial({ status: 'connecting' })
      ws.onmessage = (e) => handleEvent(e.data)
      ws.onerror = () => setPartial({ status: 'error' })
      // Use functional update to read latest status without stale closure
      ws.onclose = () => setState((prev) =>
        prev.status !== 'done' ? { ...prev, status: 'idle' } : prev
      )
    },
    [handleEvent]
  )

  const reset = useCallback(() => {
    if (wsRef.current) wsRef.current.close()
    if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
    setState(INITIAL_STATE)
  }, [])

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (vetoTimerRef.current) clearTimeout(vetoTimerRef.current)
    }
  }, [])

  return { ...state, connect, reset }
}
