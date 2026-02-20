/**
 * useNegotiationStream
 *
 * Connects to the backend WebSocket and processes all incoming events into
 * structured state for the War Room UI.
 *
 * Modes:
 *   'demo'    → /ws/demo/{type}         (scripted, no LLM key)
 *   'live'    → /ws/live/{type}         (real Claude Haiku tool-calling)
 *   'hostile' → /ws/hostile/{type}      (red-team adversarial simulation)
 *   'solo'    → /ws/solo/{type}         (ungrounded LLM — Anchor OFF)
 *   'ab-test' → /ws/ab-test/{type}      (scripted Solo vs Cyborg comparison)
 *   'task'    → /ws/task/{taskId}?agent_mode=cyborg|solo
 *                                       (AgenticPay simulation engine)
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
 *
 * AgenticPay event types:
 *   task_start         — AgenticPay task session begins
 *   round_start        — new negotiation round opens
 *   action_extracted   — Parser Π successfully extracted a price
 *   price_overflow     — Parser Π found no valid price (invalid move)
 *   agenticpay_score   — GlobalScore / BuyerScore / SellerScore update
 *   termination_round  — negotiation ended; includes final scores
 *   task_end           — all task sessions complete
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

  // AgenticPay task mode state
  taskId:        null,       // '1B-1P-1S' | '1B-MP-MS'
  agentMode:     'cyborg',   // 'cyborg' | 'solo'
  agenticpayScore: null,     // latest score bundle {globalScore, buyerScore, sellerScore, ...}
  overflowEvents: [],        // price_overflow events
  actionEvents:   [],        // action_extracted events (Parser Π successes)
  terminationEvent: null,    // termination_round event
  taskSessions:   [],        // aggregated session summaries for 1B-MP-MS

  // N-to-N Market (MBMPMS) state
  isMarket:       false,
  marketScenario: null,          // 'used_car'
  marketBuyers:   [],            // buyer config list from market_start
  marketSellers:  [],            // seller config list from market_start
  pairMatrix:     {},            // "buyerId:sellerId" → latest pair snapshot
  closedDeals:    [],            // deal_closed events
  switchEvents:   [],            // market_switch events
  dealRate:       null,          // 0-1
  marketScore:    null,          // {global_score, buyer_score, seller_score}
  marketEnd:      null,          // market_end event payload
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

      // ── AgenticPay: task session start ───────────────────────────────────
      case 'task_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:    'running',
          mode:      'task',
          taskId:    event.task_id,
          agentMode: event.agent_mode ?? 'cyborg',
          isSolo:    event.agent_mode === 'solo',
          anchorEnabled: event.agent_mode !== 'solo',
        }))
        break

      // ── AgenticPay: Parser Π price extracted ─────────────────────────────
      case 'action_extracted':
        setState((prev) => ({
          ...prev,
          actionEvents: [...prev.actionEvents, event],
          currentRound: event.round ?? prev.currentRound,
        }))
        // Also inject a thought entry so the ThoughtFeed stays populated
        setState((prev) => {
          const entry = {
            id: ++_thoughtId,
            actor: event.role?.toUpperCase() ?? 'AGENT',
            tag: 'PARSER',
            content: `[Parser Π] Extracted price $${event.price?.toFixed(2)} from ${event.role} (Round ${event.round})`,
            agentType: event.agent_type,
          }
          return {
            ...prev,
            thoughts: [...prev.thoughts, entry],
          }
        })
        break

      // ── AgenticPay: Price Overflow (no valid price tag) ───────────────────
      case 'price_overflow':
        setState((prev) => {
          const entry = {
            id: ++_thoughtId,
            actor: event.role?.toUpperCase() ?? 'AGENT',
            tag: 'HALLUCINATION',
            content: `[OVERFLOW] ${event.reason}`,
            agentType: event.agent_type,
          }
          return {
            ...prev,
            overflowEvents: [...prev.overflowEvents, event],
            thoughts: [...prev.thoughts, entry],
          }
        })
        break

      // ── AgenticPay: score update ──────────────────────────────────────────
      case 'agenticpay_score':
        setState((prev) => ({
          ...prev,
          agenticpayScore: {
            globalScore:  event.global_score,
            buyerScore:   event.buyer_score,
            sellerScore:  event.seller_score,
            discount:     event.discount,
            roundIndex:   event.round_index ?? event.round ?? prev.currentRound,
            success:      event.success,
            price:        event.price,
            interim:      event.interim ?? true,
          },
          currentRound: event.round ?? prev.currentRound,
        }))
        break

      // ── AgenticPay: termination round ────────────────────────────────────
      case 'termination_round':
        setState((prev) => ({
          ...prev,
          terminationEvent: event,
          status: 'done',
          outcome: event.success ? 'DEAL' : 'NO_DEAL',
          deal: event.final_price ? { price: event.final_price } : null,
        }))
        break

      // ── AgenticPay: task complete ─────────────────────────────────────────
      case 'task_end':
        setState((prev) => ({
          ...prev,
          status: 'done',
          taskSessions: event.sessions !== undefined
            ? [...prev.taskSessions, { sessions: event.sessions, aggregate: event.aggregate_global_score }]
            : prev.taskSessions,
        }))
        break

      // ── N-to-N Market: session start ──────────────────────────────────────
      case 'market_start':
        setState((prev) => ({
          ...INITIAL_STATE,
          status:        'running',
          mode:          'market',
          isMarket:      true,
          marketScenario: event.scenario,
          marketBuyers:   event.buyers  ?? [],
          marketSellers:  event.sellers ?? [],
          pairMatrix:     {},
          closedDeals:    [],
          switchEvents:   [],
          dealRate:       null,
          marketScore:    null,
          marketEnd:      null,
        }))
        break

      // ── N-to-N Market: round summary (batch update all 9 pairs) ──────────
      case 'market_round':
        setState((prev) => {
          const nextMatrix = { ...prev.pairMatrix }
          for (const p of (event.pairs ?? [])) {
            nextMatrix[`${p.buyer_id}:${p.seller_id}`] = p
          }
          return { ...prev, pairMatrix: nextMatrix, currentRound: event.round ?? prev.currentRound }
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
          status:    'done',
          marketEnd: event,
          outcome:   event.closed > 0 ? 'DEAL' : 'NO_DEAL',
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
    (purchaserType = 'tough', mode = 'demo', taskOptions = {}) => {
      if (wsRef.current) wsRef.current.close()

      const isAbTest = mode === 'ab-test'
      const isSolo   = mode === 'solo' || (mode === 'task' && taskOptions.agentMode === 'solo')
      const isMarket = mode === 'market'

      setState({
        ...INITIAL_STATE,
        status:        'connecting',
        purchaserType,
        mode,
        isAbTest,
        isSolo,
        isMarket,
        anchorEnabled: !isSolo,
        taskId:        taskOptions.taskId ?? null,
        agentMode:     taskOptions.agentMode ?? 'cyborg',
        marketScenario: taskOptions.scenario ?? null,
      })

      let url
      if (mode === 'task') {
        const tid = taskOptions.taskId || '1B-1P-1S'
        const am  = taskOptions.agentMode || 'cyborg'
        url = `${WS_BASE}/ws/task/${tid}?agent_mode=${am}`
      } else if (mode === 'market') {
        const sc = taskOptions.scenario || 'used_car'
        url = `${WS_BASE}/ws/market/${sc}`
      } else {
        url =
          mode === 'hostile'  ? `${WS_BASE}/ws/hostile/${purchaserType}`  :
          mode === 'live'     ? `${WS_BASE}/ws/live/${purchaserType}`     :
          mode === 'solo'     ? `${WS_BASE}/ws/solo/${purchaserType}`     :
          mode === 'ab-test'  ? `${WS_BASE}/ws/ab-test/${purchaserType}` :
                                `${WS_BASE}/ws/demo/${purchaserType}`
      }

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
