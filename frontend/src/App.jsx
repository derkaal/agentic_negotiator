/**
 * Negotiation War Room — main layout.
 *
 * Standard layout (demo / live):
 *   ControlBar → ProviderBoard → Charts → ThoughtFeed → DealSummary
 *
 * Hostile layout adds:
 *   ThreatBrief banner → Attack Monitor panel (alongside ThoughtFeed)
 *   DeceptionFlash overlay on every CRITICAL alert
 *
 * Solo layout adds (Anchor: OFF):
 *   UngroundedBanner → HallucinationMonitor panel (alongside ThoughtFeed)
 *
 * A/B Test layout:
 *   Side-by-side: Solo ThoughtFeed | Cyborg ThoughtFeed
 *   Hallucination Monitor below (tool_comparison events)
 *   A/B outcome cards showing both results
 */

import React, { useCallback, useState } from 'react'
import clsx from 'clsx'
import ControlBar from './components/ControlBar'
import ConvergenceLine from './components/ConvergenceLine'
import DealRadar from './components/DealRadar'
import DealSummary from './components/DealSummary'
import DeceptionAlertLog, { DeceptionFlash } from './components/DeceptionAlert'
import HallucinationMonitor, { UngroundedBanner } from './components/HallucinationMonitor'
import MarketOverview from './components/MarketOverview'
import PriceOverflowAlert from './components/PriceOverflowAlert'
import ProviderBoard from './components/ProviderBoard'
import ScorePanel from './components/ScorePanel'
import ThoughtFeed from './components/ThoughtFeed'
import VetoFlash from './components/VetoFlash'
import { useNegotiationStream } from './hooks/useNegotiationStream'

export default function App() {
  const [activePurchaserType, setActivePurchaserType] = useState('tough')
  const [activeMode, setActiveMode]                   = useState('demo')

  const {
    status, mode,
    isHostile, threatBrief,
    isAbTest, isSolo, anchorEnabled,
    abTestDescription,
    providers, thoughts, radarData, convergenceHistory,
    soloThoughts, cyborgThoughts,
    internalMathEvents, socialPressureEvents, toolComparisonEvents,
    veto, vetoVisible,
    deceptionAlerts, latestDeceptionAlert, deceptionFlashVisible,
    outcome, deal,
    soloOutcome, soloDeal, cyborgOutcome, cyborgDeal,
    currentRound,
    // AgenticPay task mode
    taskId, agentMode,
    agenticpayScore, overflowEvents, actionEvents, terminationEvent,
    // N-to-N Market
    isMarket,
    marketScenario, marketBuyers, marketSellers,
    pairMatrix, closedDeals, switchEvents, dealRate, marketScore,
    sellerStrategies, auditTrail, marketEnd,
    connect, reset, setAnchorEnabled,
  } = useNegotiationStream()

  const isTask = mode === 'task'

  const handleStart = useCallback((type, m, taskOptions) => {
    const resolvedMode = m ?? activeMode
    setActivePurchaserType(type)
    setActiveMode(resolvedMode)
    connect(type, resolvedMode, taskOptions ?? {})
  }, [connect, activeMode])

  const handleModeChange = useCallback((m) => {
    setActiveMode(m)
    if (m === 'solo') {
      setAnchorEnabled(false)
    } else if (m !== 'ab-test' && m !== 'task' && m !== 'market') {
      setAnchorEnabled(true)
    }
  }, [setAnchorEnabled])

  const handleAnchorToggle = useCallback((enabled) => {
    setAnchorEnabled(enabled)
    // Switching anchor toggles between live and solo mode
    const newMode = enabled ? 'live' : 'solo'
    setActiveMode(newMode)
  }, [setAnchorEnabled])

  const handleReset = useCallback(() => {
    reset()
    setActivePurchaserType('tough')
  }, [reset])

  const lastRadarProvider =
    convergenceHistory.length > 0
      ? convergenceHistory[convergenceHistory.length - 1].provider_name
      : undefined

  const maxRounds = isHostile ? 3 : isAbTest ? 3 : isTask ? 10 : isMarket ? 15 : 6

  // ── Shield explainer cards ─────────────────────────────────────────────
  const STANDARD_SHIELDS = [
    { icon: '🔮', title: 'PriceOracle',      color: 'border-cyan-500/30 bg-cyan-900/10',
      desc: 'Anchors the Purchaser to market reality ($150 avg) before any offer is evaluated. Prevents the "friendly price" hallucination trap.' },
    { icon: '🧮', title: 'UtilityCalculator', color: 'border-purple-500/30 bg-purple-900/10',
      desc: 'Scores every deal 0–100 using hidden buyer weights. An offer that LOOKS good may SCORE badly — the Cyborg won\'t be fooled.' },
    { icon: '🚫', title: 'MarginValidator',   color: 'border-red-500/30 bg-red-900/10',
      desc: 'Guards Providers from their own desperation. If a concession would breach the floor, the offer is HARD VETOED.' },
  ]
  const HOSTILE_SHIELDS = [
    { icon: '📋', title: 'ContractValidator', color: 'border-red-500/40 bg-red-950/20',
      desc: 'Compares the seller\'s text price to the contract JSON. Even a $0.01 discrepancy triggers a BAIT-AND-SWITCH halt. Also scans metadata for injected fees.' },
    { icon: '📡', title: 'MarketOracle',      color: 'border-amber-500/40 bg-amber-950/20',
      desc: 'Enforces a strict 5% above-market ceiling. Also cross-checks seller stock claims against verified inventory to expose Phantom Scarcity.' },
    { icon: '🧮', title: 'UtilityCalculator', color: 'border-purple-500/30 bg-purple-900/10',
      desc: 'Threshold raised to 60 in hostile mode. The Purchaser demands higher merit because the environment is adversarial.' },
  ]
  const AB_TEST_SHIELDS = [
    { icon: '🧠', title: 'Solo Agent (No Anchor)', color: 'border-orange-500/40 bg-orange-950/20',
      desc: 'No grounding tools. Relies on intuition and "common sense." Accepted $170 — 13.3% above market — because social pressure tactics felt convincing.' },
    { icon: '🤖', title: 'Cyborg Agent (Anchored)', color: 'border-cyan-500/30 bg-cyan-900/10',
      desc: 'PriceOracle + UtilityCalculator anchored every decision. Scored $170 at 44.17/100 (REJECT threshold: 55). Walked away.' },
    { icon: '🔬', title: 'Hallucination Gap', color: 'border-violet-500/40 bg-violet-950/20',
      desc: 'Solo Agent guessed 72/100. Tool-verified score: 44.17/100. Δ 27.83 points of error — entirely driven by social pressure and phantom scarcity claims.' },
  ]

  const TASK_SHIELDS = [
    { icon: '⚖', title: 'Algorithm 1 (AgenticPay)', color: 'border-cyan-500/30 bg-cyan-900/10',
      desc: 'GlobalScore = D·γᵗ + W·Q·γᵗ + E·γᵗ where Q=4·u_b·u_s. Penalises longer negotiations via temporal discounting (γ=0.99). D=30, W=55, E=15.' },
    { icon: '⚡', title: 'Parser Π (Price Extractor)', color: 'border-amber-500/30 bg-amber-900/10',
      desc: '3-priority regex pipeline: ### BUYER_PRICE($X) ### → ### $X ### → fallback ($X / "X dollars"). Missing price = Price Overflow — flagged as invalid move.' },
    { icon: '📉', title: 'Temporal Discount (γ=0.99)', color: 'border-violet-500/30 bg-violet-900/10',
      desc: 'Every additional round costs discount = γ^t points. A deal at round 1 scores 0.99× full, at round 10 scores 0.90× — incentivising fast convergence.' },
  ]

  const MARKET_SHIELDS = [
    { icon: '🏪', title: 'Parallel Interaction (MBMPMS)', color: 'border-emerald-500/30 bg-emerald-900/10',
      desc: 'All 9 buyer-seller pairs negotiate simultaneously every round. Sellers compete — driving prices down faster than any 1-on-1 session.' },
    { icon: '⇢', title: 'Market Switching (<40 utility)', color: 'border-amber-500/30 bg-amber-900/10',
      desc: 'When utility drops below 40, the Cyborg deprioritises that seller and pivots budget-share to higher-scoring negotiations. Rational resource allocation.' },
    { icon: '⚖', title: 'GlobalScore (Market Welfare)', color: 'border-cyan-500/30 bg-cyan-900/10',
      desc: 'AgenticPay Algorithm 1 aggregated across all closed deals. Higher deal rate + faster convergence = higher market welfare score (D=30, W=55, E=15, γ=0.99).' },
  ]

  const shields = isMarket ? MARKET_SHIELDS : isTask ? TASK_SHIELDS : isAbTest ? AB_TEST_SHIELDS : isHostile ? HOSTILE_SHIELDS : STANDARD_SHIELDS

  return (
    <div className="min-h-screen bg-war-bg text-gray-200 flex flex-col">
      {/* ── Overlays ──────────────────────────────────────────────────── */}
      <VetoFlash veto={veto} visible={vetoVisible} />
      <DeceptionFlash alert={latestDeceptionAlert} visible={deceptionFlashVisible} />

      {/* ── Header ────────────────────────────────────────────────────── */}
      <ControlBar
        status={status}
        mode={activeMode}
        purchaserType={activePurchaserType}
        currentRound={currentRound}
        maxRounds={maxRounds}
        anchorEnabled={anchorEnabled}
        onStart={handleStart}
        onReset={handleReset}
        onModeChange={handleModeChange}
        onAnchorToggle={handleAnchorToggle}
      />

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 py-6 space-y-6">

        {/* ── Idle splash ───────────────────────────────────────────── */}
        {status === 'idle' && (
          <div className="border border-war-border rounded-xl bg-war-panel/50 px-8 py-10 text-center space-y-3">
            <p className="text-4xl mb-2">⚔️</p>
            <h2 className="text-white font-black text-xl tracking-wide">
              Negotiation War Room
            </h2>
            <p className="text-gray-400 text-sm max-w-2xl mx-auto leading-relaxed">
              Powered by{' '}
              <span className="text-war-accent font-bold">Claude Haiku 4.5</span> + AgenticPay Algorithm 1.
              The <span className="text-emerald-400 font-bold">🏪 Market</span> mode runs a{' '}
              <span className="font-semibold text-white">3-Buyer × 3-Seller</span> MBMPMS market
              with parallel negotiation and market-switching — go beyond the 1-on-1 baseline.
            </p>

            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6 text-left max-w-5xl mx-auto">
              {[
                { mode: 'demo',    icon: '🎬', title: 'Demo',
                  desc: 'Scripted 1-on-1. No API key.',
                  cls: 'border-war-purple/40 hover:border-war-purple' },
                { mode: 'live',    icon: '🤖', title: 'Live LLM',
                  desc: 'Claude Haiku 4.5 + tools.',
                  cls: 'border-war-green/40 hover:border-war-green' },
                { mode: 'hostile', icon: '☠',  title: 'Red Team',
                  desc: 'Adversarial attacks.',
                  cls: 'border-war-red/40 hover:border-war-red' },
                { mode: 'solo',    icon: '🧠', title: 'Solo',
                  desc: 'Anchor OFF — gets fooled.',
                  cls: 'border-orange-500/40 hover:border-orange-500' },
                { mode: 'ab-test', icon: '⚗️', title: 'A/B Test',
                  desc: 'Solo vs Cyborg comparison.',
                  cls: 'border-violet-500/40 hover:border-violet-500' },
                { mode: 'market',  icon: '🏪', title: 'Market',
                  desc: '3×3 MBMPMS — parallel + switching.',
                  cls: 'border-emerald-600/50 hover:border-emerald-500',
                  taskOptions: { scenario: 'used_car' } },
              ].map(({ mode: m, icon, title, desc, cls, taskOptions }) => (
                <button
                  key={m}
                  onClick={() => handleStart('tough', m, taskOptions)}
                  className={clsx(
                    'rounded-xl border-2 bg-war-panel/60 p-4 text-left transition-all active:scale-95',
                    cls,
                  )}
                >
                  <div className="text-2xl mb-2">{icon}</div>
                  <div className="text-white font-bold text-sm mb-1">{title}</div>
                  <div className="text-gray-400 text-xs leading-relaxed">{desc}</div>
                </button>
              ))}
            </div>

            {/* AgenticPay task shortcuts */}
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              {[
                { taskId: '1B-1P-1S', am: 'cyborg', label: '⚖ 1B·1P·1S Cyborg', cls: 'border-cyan-700/50 text-cyan-300 hover:border-cyan-500' },
                { taskId: '1B-1P-1S', am: 'solo',   label: '⚖ 1B·1P·1S Solo',   cls: 'border-orange-700/50 text-orange-300 hover:border-orange-500' },
                { taskId: '1B-MP-MS', am: 'cyborg', label: '🏪 1B·MP·MS Cyborg', cls: 'border-cyan-700/50 text-cyan-300 hover:border-cyan-500' },
                { taskId: '1B-MP-MS', am: 'solo',   label: '🏪 1B·MP·MS Solo',   cls: 'border-orange-700/50 text-orange-300 hover:border-orange-500' },
              ].map(({ taskId: tid, am, label, cls }) => (
                <button
                  key={`${tid}-${am}`}
                  onClick={() => handleStart('tough', 'task', { taskId: tid, agentMode: am })}
                  className={clsx(
                    'rounded-lg border bg-war-panel/60 px-4 py-2 text-xs font-mono font-bold transition-all active:scale-95',
                    cls,
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-war-muted/60 mt-2">
              ⚖ AgenticPay Algorithm 1 · D=30 W=55 E=15 γ=0.99
            </p>
          </div>
        )}

        {/* ── Solo mode ungrounded banner ────────────────────────────── */}
        {(isSolo || (!anchorEnabled && status !== 'idle')) && !isAbTest && (
          <UngroundedBanner visible />
        )}

        {/* ── A/B Test description banner ────────────────────────────── */}
        {isAbTest && abTestDescription && status !== 'idle' && (
          <div className="rounded-xl border border-violet-600/50 bg-violet-950/20 px-5 py-3 flex gap-3 items-start animate-fade-in">
            <span className="text-xl flex-shrink-0">⚗️</span>
            <div>
              <p className="text-violet-300 font-black text-xs uppercase tracking-widest mb-0.5">
                A/B Test — Solo vs Cyborg
              </p>
              <p className="text-violet-200/70 text-xs font-mono">{abTestDescription}</p>
            </div>
            <div className="ml-auto flex-shrink-0 flex gap-2">
              <span className="bg-orange-900/60 border border-orange-700/50 text-orange-300 text-xs font-bold px-2 py-1 rounded font-mono">
                SOLO: NO ANCHOR
              </span>
              <span className="bg-cyan-900/60 border border-cyan-700/50 text-cyan-300 text-xs font-bold px-2 py-1 rounded font-mono">
                CYBORG: GROUNDED
              </span>
            </div>
          </div>
        )}

        {/* ── Threat brief (hostile mode only) ──────────────────────── */}
        {isHostile && threatBrief && (
          <div className="rounded-xl border-2 border-red-600/60 bg-red-950/30 px-6 py-4 flex gap-4 items-start animate-fade-in">
            <span className="text-2xl flex-shrink-0">☠</span>
            <div>
              <p className="text-red-300 font-black text-xs uppercase tracking-widest mb-1">
                Threat Intelligence Brief
              </p>
              <p className="text-red-200 text-xs font-mono leading-relaxed">{threatBrief}</p>
            </div>
            <div className="ml-auto flex-shrink-0 flex flex-col items-end gap-1">
              <span className="bg-red-700 text-white text-xs font-bold px-2 py-0.5 rounded">
                RED TEAM ACTIVE
              </span>
              <span className="text-red-400 text-xs font-mono">
                {deceptionAlerts.filter(a => a.severity === 'CRITICAL').length} BLOCKED
              </span>
            </div>
          </div>
        )}

        {/* ── Provider board ─────────────────────────────────────────── */}
        {Object.keys(providers).length > 0 && (
          <div className={clsx(
            'border rounded-xl p-5 scanlines relative',
            isHostile
              ? 'bg-red-950/20 border-red-800/40'
              : isSolo || (!anchorEnabled && !isAbTest)
              ? 'bg-orange-950/20 border-orange-800/40'
              : isAbTest
              ? 'bg-violet-950/10 border-violet-800/30'
              : 'bg-war-panel border-war-border',
          )}>
            <ProviderBoard providers={providers} convergenceHistory={convergenceHistory} />
          </div>
        )}

        {/* ── Charts row (not shown in A/B Test, Task, or Market) ───────── */}
        {!isAbTest && !isTask && !isMarket && (status !== 'idle' || radarData.length > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className={clsx(
              'border rounded-xl p-5 h-72',
              isHostile
                ? 'bg-red-950/20 border-red-800/40'
                : isSolo ? 'bg-orange-950/20 border-orange-800/40'
                : 'bg-war-panel border-war-border',
            )}>
              <DealRadar data={radarData} provider={lastRadarProvider} />
            </div>
            <div className={clsx(
              'border rounded-xl p-5 h-72',
              isHostile
                ? 'bg-red-950/20 border-red-800/40'
                : isSolo ? 'bg-orange-950/20 border-orange-800/40'
                : 'bg-war-panel border-war-border',
            )}>
              <ConvergenceLine history={convergenceHistory} />
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════
            N-to-N MARKET LAYOUT (MBMPMS)
            Full-width MarketOverview 3×3 matrix + final summary card
            ════════════════════════════════════════════════════════════ */}
        {isMarket && (marketBuyers.length > 0 || Object.keys(pairMatrix).length > 0 || marketEnd) && (
          <>
            {/* Market header */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-widest text-emerald-400 px-3 py-1 rounded border border-emerald-700/60 bg-emerald-950/30 font-mono">
                🏪 MBMPMS · 3 Buyers × 3 Sellers
              </span>
              <span className="text-xs text-war-muted font-mono">
                {marketScenario === 'used_car' ? 'Honda Civic 2021 · Used Car Market' : marketScenario}
              </span>
              <span className="text-[10px] text-war-muted/60 font-mono">
                Parallel Interaction · Market Switch &lt;40 · AgenticPay Algorithm 1
              </span>
            </div>

            {/* Market Overview panel */}
            <div className="bg-war-card border border-emerald-800/40 rounded-xl p-5">
              <MarketOverview
                buyers={marketBuyers}
                sellers={marketSellers}
                pairMatrix={pairMatrix}
                closedDeals={closedDeals}
                dealRate={dealRate}
                marketScore={marketScore}
                switchEvents={switchEvents}
                sellerStrategies={sellerStrategies}
                auditTrail={auditTrail}
                marketEnd={marketEnd}
                currentRound={currentRound}
                scenario={marketScenario}
              />
            </div>

            {/* Market end summary */}
            {marketEnd && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 animate-fade-in">
                {/* Overall result */}
                <div className={clsx(
                  'rounded-xl border-2 p-5',
                  marketEnd.closed >= 3
                    ? 'border-emerald-500/60 bg-emerald-950/30'
                    : marketEnd.closed > 0
                    ? 'border-amber-600/50 bg-amber-950/20'
                    : 'border-red-700/50 bg-red-950/20',
                )}>
                  <div className="text-xs font-bold uppercase tracking-widest text-emerald-400 mb-3">
                    ◼ Market Result
                  </div>
                  <div className="text-3xl font-mono font-black text-white mb-1">
                    {marketEnd.closed}/{marketEnd.possible}
                  </div>
                  <div className="text-sm text-emerald-300 mb-3">
                    deals closed — {Math.round((marketEnd.deal_rate ?? 0) * 100)}% liquidity
                  </div>
                  <div className="space-y-1 text-xs font-mono">
                    <div className="flex justify-between">
                      <span className="text-war-muted">Avg deal price</span>
                      <span className="text-white font-bold">
                        ${marketEnd.avg_deal_price?.toLocaleString() ?? '—'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-war-muted">Avg rounds to deal</span>
                      <span className="text-white">{marketEnd.avg_rounds_to_deal ?? '—'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-war-muted">Market switches</span>
                      <span className="text-amber-400">{marketEnd.market_switches ?? 0}</span>
                    </div>
                  </div>
                </div>

                {/* AgenticPay scores */}
                <div className="rounded-xl border border-cyan-700/50 bg-cyan-950/20 p-5">
                  <div className="text-xs font-bold uppercase tracking-widest text-cyan-400 mb-3">
                    ⚖ AgenticPay Scores
                  </div>
                  {[
                    { label: 'GlobalScore', v: marketEnd.global_score },
                    { label: 'BuyerScore',  v: marketEnd.buyer_score  },
                    { label: 'SellerScore', v: marketEnd.seller_score },
                  ].map(({ label, v }) => (
                    <div key={label} className="flex justify-between items-center mb-2">
                      <span className="text-xs text-war-muted">{label}</span>
                      <span className={clsx(
                        'font-mono font-bold text-sm',
                        v == null ? 'text-war-muted'
                          : v >= 70 ? 'text-emerald-400'
                          : v >= 50 ? 'text-amber-400'
                          : 'text-red-400'
                      )}>
                        {v != null ? v.toFixed(3) : '—'}
                      </span>
                    </div>
                  ))}
                  <div className="text-[10px] text-war-muted/60 mt-2 font-mono">
                    Avg across closed deals · D=30 W=55 E=15 γ=0.99
                  </div>
                </div>

                {/* Competitive note */}
                <div className="rounded-xl border border-violet-700/40 bg-violet-950/20 p-5">
                  <div className="text-xs font-bold uppercase tracking-widest text-violet-400 mb-3">
                    📊 vs 1-on-1 Baseline
                  </div>
                  <div className="text-xs text-war-muted leading-relaxed font-mono">
                    {marketEnd.note}
                  </div>
                  {(marketEnd.deals ?? []).map((d, i) => (
                    <div key={i} className="mt-2 bg-war-panel rounded px-2 py-1.5 flex justify-between text-[11px] font-mono">
                      <span className="text-emerald-300">
                        {d.buyer_name?.split(' ')[0]} × {d.seller_name}
                      </span>
                      <span className="text-white font-bold">${d.deal_price?.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* ══════════════════════════════════════════════════════════════
            AGENTICPAY TASK LAYOUT
            Two-column: ThoughtFeed | ScorePanel + PriceOverflowAlert
            ════════════════════════════════════════════════════════════ */}
        {isTask && (thoughts.length > 0 || agenticpayScore || overflowEvents.length > 0) && (
          <>
            {/* Task header badge */}
            <div className="flex items-center gap-3 flex-wrap">
              <span className={clsx(
                'text-xs font-bold uppercase tracking-widest px-3 py-1 rounded border font-mono',
                agentMode === 'solo'
                  ? 'text-orange-300 border-orange-700/60 bg-orange-950/30'
                  : 'text-cyan-300 border-cyan-700/60 bg-cyan-950/30',
              )}>
                {agentMode === 'solo' ? '🧠 Solo Mode' : '🤖 Cyborg Mode'}
              </span>
              <span className="text-xs text-war-muted font-mono">
                Task {taskId ?? '—'}
              </span>
              <span className="text-xs text-war-muted/60 font-mono">
                AgenticPay · Algorithm 1 · D=30 W=55 E=15 γ=0.99
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Thought Feed — takes 2/3 */}
              <div className={clsx(
                'lg:col-span-2 border rounded-xl p-5 h-[520px]',
                agentMode === 'solo'
                  ? 'bg-orange-950/10 border-orange-800/40'
                  : 'bg-cyan-950/10 border-cyan-800/40',
              )}>
                <ThoughtFeed
                  thoughts={thoughts}
                  label={`AgenticPay ${taskId} — ${agentMode === 'solo' ? 'Solo' : 'Cyborg'}`}
                  agentMode={agentMode}
                />
              </div>

              {/* Score + Parser Π panel */}
              <div className="space-y-4">
                <ScorePanel
                  globalScore={agenticpayScore?.globalScore ?? null}
                  buyerScore={agenticpayScore?.buyerScore ?? null}
                  sellerScore={agenticpayScore?.sellerScore ?? null}
                  discount={agenticpayScore?.discount ?? null}
                  roundIndex={agenticpayScore?.roundIndex ?? currentRound}
                  success={agenticpayScore?.success ?? null}
                  agentMode={agentMode}
                  taskId={taskId}
                  interim={agenticpayScore?.interim ?? true}
                />
                <PriceOverflowAlert
                  overflowEvents={overflowEvents}
                  terminationEvent={terminationEvent}
                  actionEvents={actionEvents}
                  agentMode={agentMode}
                />
              </div>
            </div>
          </>
        )}

        {/* ══════════════════════════════════════════════════════════════
            A/B TEST LAYOUT — three-column: Solo | Cyborg | HalMon
            ════════════════════════════════════════════════════════════ */}
        {isAbTest && (soloThoughts.length > 0 || cyborgThoughts.length > 0 || internalMathEvents.length > 0) && (
          <>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Solo Agent feed */}
              <div className="bg-orange-950/15 border border-orange-800/40 rounded-xl p-5 h-[520px]">
                <ThoughtFeed
                  thoughts={soloThoughts}
                  label="Solo Agent — Anchor OFF"
                  agentMode="solo"
                />
              </div>

              {/* Cyborg Agent feed */}
              <div className="bg-cyan-950/15 border border-cyan-800/40 rounded-xl p-5 h-[520px]">
                <ThoughtFeed
                  thoughts={cyborgThoughts}
                  label="Cyborg Agent — Grounded"
                  agentMode="cyborg"
                />
              </div>

              {/* Hallucination Monitor */}
              <div className="bg-war-panel border border-war-border rounded-xl p-5 h-[520px]">
                <HallucinationMonitor
                  isAbTest
                  internalMathEvents={internalMathEvents}
                  socialPressureEvents={socialPressureEvents}
                  toolComparisonEvents={toolComparisonEvents}
                />
              </div>
            </div>

            {/* A/B Test outcome comparison */}
            {(soloOutcome || cyborgOutcome) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Solo outcome */}
                {soloOutcome && (
                  <div className={clsx(
                    'rounded-xl border-2 p-5 animate-fade-in',
                    soloOutcome === 'ACCEPT'
                      ? 'border-orange-500/60 bg-orange-950/30'
                      : 'border-gray-600/60 bg-gray-900/30',
                  )}>
                    <div className="flex items-center gap-3 mb-3">
                      <span className="text-2xl">🧠</span>
                      <div>
                        <p className="text-orange-300 font-black text-xs uppercase tracking-widest">
                          Solo Agent — Anchor OFF
                        </p>
                        <p className={clsx(
                          'font-black text-lg',
                          soloOutcome === 'ACCEPT' ? 'text-orange-300' : 'text-gray-400',
                        )}>
                          {soloOutcome === 'ACCEPT' ? '✓ ACCEPTED' : '✗ NO DEAL'}
                        </p>
                      </div>
                    </div>
                    {soloDeal && (
                      <div className="space-y-1.5 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Provider</span>
                          <span className="text-orange-300">{soloDeal.provider_name}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Accepted price</span>
                          <span className="text-orange-300 font-bold">${soloDeal.price?.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Solo estimate</span>
                          <span className="text-orange-300">{soloDeal.hallucinated_score ?? '?'}/100</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Actual score</span>
                          <span className="text-red-400 font-bold">{soloDeal.actual_score ?? '?'}/100</span>
                        </div>
                        <div className="flex justify-between border-t border-orange-800/40 pt-1.5 mt-1.5">
                          <span className="text-gray-500">Overpaid vs market</span>
                          <span className="text-red-400 font-bold">
                            +${((soloDeal.price ?? 0) - 150).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    )}
                    <p className="text-orange-500/70 text-xs font-mono mt-3 italic">
                      Accepted due to social pressure + phantom scarcity
                    </p>
                  </div>
                )}

                {/* Cyborg outcome */}
                {cyborgOutcome && (
                  <div className={clsx(
                    'rounded-xl border-2 p-5 animate-fade-in',
                    cyborgOutcome === 'ACCEPT'
                      ? 'border-emerald-500/60 bg-emerald-950/30'
                      : 'border-cyan-700/60 bg-cyan-950/30',
                  )}>
                    <div className="flex items-center gap-3 mb-3">
                      <span className="text-2xl">🤖</span>
                      <div>
                        <p className="text-cyan-300 font-black text-xs uppercase tracking-widest">
                          Cyborg Agent — Grounded
                        </p>
                        <p className={clsx(
                          'font-black text-lg',
                          cyborgOutcome === 'ACCEPT' ? 'text-emerald-300' : 'text-cyan-300',
                        )}>
                          {cyborgOutcome === 'ACCEPT' ? '✓ ACCEPTED' : '✗ NO DEAL (VETO)'}
                        </p>
                      </div>
                    </div>
                    {cyborgOutcome === 'NO_DEAL' && (
                      <div className="space-y-1.5 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Provider offer</span>
                          <span className="text-cyan-300">$170.00</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Tool score</span>
                          <span className="text-red-400 font-bold">44.17/100</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Threshold</span>
                          <span className="text-cyan-400">≥ 55 required</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Above market</span>
                          <span className="text-red-400 font-bold">+13.3%</span>
                        </div>
                        <div className="flex justify-between border-t border-cyan-800/40 pt-1.5 mt-1.5">
                          <span className="text-gray-500">Decision</span>
                          <span className="text-cyan-400 font-bold">VETO — math wins</span>
                        </div>
                      </div>
                    )}
                    <p className="text-cyan-600/70 text-xs font-mono mt-3 italic">
                      All pressure tactics identified and neutralised by grounding tools
                    </p>
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ══════════════════════════════════════════════════════════════
            STANDARD / SOLO FEED ROW
            ════════════════════════════════════════════════════════════ */}
        {!isAbTest && !isTask && !isMarket && thoughts.length > 0 && (
          <div className={clsx(
            'grid gap-6',
            isHostile || isSolo ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1',
          )}>
            {/* Thought Feed */}
            <div className={clsx(
              'border rounded-xl p-5 h-[480px]',
              isHostile
                ? 'bg-red-950/10 border-red-900/50'
                : isSolo
                ? 'bg-orange-950/10 border-orange-900/40'
                : 'bg-war-panel border-war-border',
            )}>
              <ThoughtFeed
                thoughts={thoughts}
                agentMode={isSolo ? 'solo' : undefined}
              />
            </div>

            {/* Attack Monitor — hostile only */}
            {isHostile && (
              <div className="bg-war-panel border border-war-border rounded-xl p-5 h-[480px]">
                <DeceptionAlertLog alerts={deceptionAlerts} />
              </div>
            )}

            {/* Hallucination Monitor — solo mode */}
            {isSolo && (
              <div className="bg-war-panel border border-war-border rounded-xl p-5 h-[480px]">
                <HallucinationMonitor
                  isSolo
                  internalMathEvents={internalMathEvents}
                  socialPressureEvents={socialPressureEvents}
                  toolComparisonEvents={toolComparisonEvents}
                />
              </div>
            )}
          </div>
        )}

        {/* ── Deal summary (standard / solo modes) ───────────────────── */}
        {!isAbTest && !isTask && !isMarket && outcome && (
          <DealSummary
            outcome={outcome}
            deal={deal}
            hostile={isHostile}
          />
        )}

        {/* ── Shield explainer ───────────────────────────────────────── */}
        {status === 'done' && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-6">
            {shields.map(({ icon, title, desc, color }) => (
              <div key={title} className={`rounded-xl border p-5 ${color} animate-fade-in`}>
                <div className="text-2xl mb-2">{icon}</div>
                <h3 className="text-white font-bold text-sm mb-2">{title}</h3>
                <p className="text-gray-400 text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
