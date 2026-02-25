/**
 * useNegotiationStream
 *
 * Simplified hook for MBMPMS Market mode only.
 * Connects to /ws/market/{scenario} and processes market events.
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
  mode:         'market',

  // N-to-N Market (MBMPMS) state
  isMarket:           true,
  marketScenario:     null,      // 'used_car'
  marketBuyers:       [],        // buyer config list from market_start
  marketSellers:      [],        // seller config list from market_start
  pairMatrix:         {},        // "buyerId:sellerId" → latest pair snapshot
  closedDeals:        [],        // deal_closed events
  switchEvents:       [],        // market_switch events
  dealRate:           null,      // 0-1
  marketScore:        null,      // {global_score, buyer_score, seller_score}
  sellerStrategies:   {},        // {sellerId: 'normal'|'match_market'|'hold_margin'}
  auditTrail:         [],        // per-deal Profit Map rows from market_end
  marketEnd:          null,      // full market_end payload
  currentRound:       0,
}

export function useNegotiationStream() {
  const [state, setState] = useState(INITIAL_STATE)
  const wsRef = useRef(null)

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

      // ── N-to-N Market: session start ──────────────────────────────────────
      case 'market_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:           'running',
          mode:             'market',
          isMarket:         true,
          marketScenario:   event.scenario,
          marketBuyers:     event.buyers   ?? [],
          marketSellers:    event.sellers  ?? [],
          pairMatrix:       {},
          closedDeals:      [],
          switchEvents:     [],
          dealRate:         null,
          marketScore:      null,
          sellerStrategies: {},
          auditTrail:       [],
          marketEnd:        null,
        }))
        break

      // ── N-to-N Market: round summary (batch update all 9 pairs) ──────────
      case 'market_round':
        setState((prev) => {
          const nextMatrix = { ...prev.pairMatrix }
          for (const p of (event.pairs ?? [])) {
            nextMatrix[`${p.buyer_id}:${p.seller_id}`] = p
          }
          return {
            ...prev,
            pairMatrix:       nextMatrix,
            currentRound:     event.round ?? prev.currentRound,
            sellerStrategies: event.seller_strategies ?? prev.sellerStrategies,
          }
        })
        break

      // ── N-to-N Market: market switch ──────────────────────────────────────
      case 'market_switch':
        setState((prev) => ({
          ...prev,
          switchEvents: [...prev.switchEvents, event],
        }))
        break

      // ── N-to-N Market: deal closed ────────────────────────────────────────
      case 'deal_closed':
        setState((prev) => ({
          ...prev,
          closedDeals: [...prev.closedDeals, event],
        }))
        break

      // ── N-to-N Market: deal rate update ───────────────────────────────────
      case 'deal_rate':
        setState((prev) => ({ ...prev, dealRate: event.rate ?? prev.dealRate }))
        break

      // ── N-to-N Market: market score ───────────────────────────────────────
      case 'market_score':
        setState((prev) => ({
          ...prev,
          marketScore: {
            global_score: event.global_score,
            buyer_score:  event.buyer_score,
            seller_score: event.seller_score,
          },
        }))
        break

      // ── N-to-N Market: session end ────────────────────────────────────────
      case 'market_end':
        setState((prev) => ({
          ...prev,
          status:     'done',
          marketEnd:  event,
          auditTrail: event.audit_trail ?? [],
        }))
        break

      case 'error':
        setPartial({ status: 'error' })
        break

      default:
        break
    }
  }, [])

  // ── Connect to the market WebSocket endpoint ──────────────────────────────
  const connect = useCallback(
    (purchaserType = 'tough', mode = 'market', taskOptions = {}) => {
      if (wsRef.current) wsRef.current.close()

      setState({
        ...INITIAL_STATE,
        status:        'connecting',
        mode:          'market',
        isMarket:      true,
        marketScenario: taskOptions.scenario ?? 'used_car',
      })

      const scenario = taskOptions.scenario || 'used_car'
      const url = `${WS_BASE}/ws/market/${scenario}`

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
    setState(INITIAL_STATE)
  }, [])

  useEffect(() => () => {
    if (wsRef.current) wsRef.current.close()
  }, [])

  return { ...state, connect, reset }
}
