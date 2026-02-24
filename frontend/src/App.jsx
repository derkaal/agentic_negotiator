/**
 * Negotiation War Room — Stress Test Suite
 *
 * Focused on 3×3 MBMPMS Market mode with three seller archetypes:
 * - Solo LLM (raw ClaudeHaikuLLM)
 * - Math Geek (deterministic OfferGenerator)
 * - Probing Strategist (competitive-cooperative hybrid)
 */

import React, { useCallback, useState } from 'react'
import clsx from 'clsx'
import ControlBar from './components/ControlBar'
import MarketOverview from './components/MarketOverview'
import { useNegotiationStream } from './hooks/useNegotiationStream'

export default function App() {
  const [activeMode, setActiveMode] = useState('market')

  const {
    status,
    isMarket,
    marketScenario, marketBuyers, marketSellers,
    pairMatrix, closedDeals, switchEvents, dealRate, marketScore,
    sellerStrategies, auditTrail, marketEnd,
    currentRound,
    connect, reset,
  } = useNegotiationStream()

  const handleStart = useCallback((type, m, taskOptions) => {
    connect(type, m ?? 'market', taskOptions ?? { scenario: 'used_car' })
  }, [connect])

  const handleReset = useCallback(() => {
    reset()
  }, [reset])

  const maxRounds = 15

  return (
    <div className="min-h-screen bg-war-bg text-gray-200 flex flex-col">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <ControlBar
        status={status}
        mode={activeMode}
        currentRound={currentRound}
        maxRounds={maxRounds}
        onStart={handleStart}
        onReset={handleReset}
      />

      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 py-6 space-y-6">

        {/* ── Idle splash ───────────────────────────────────────────── */}
        {status === 'idle' && (
          <div className="border border-war-border rounded-xl bg-war-panel/50 px-8 py-10 text-center space-y-3">
            <p className="text-4xl mb-2">🏪</p>
            <h2 className="text-white font-black text-xl tracking-wide">
              MBMPMS Stress Test Suite
            </h2>
            <p className="text-gray-400 text-sm max-w-2xl mx-auto leading-relaxed">
              3-Buyer × 3-Seller market with three seller archetypes:
              <span className="text-red-400 font-bold"> Solo LLM</span>,
              <span className="text-amber-400 font-bold"> Math Geek</span>, and
              <span className="text-blue-400 font-bold"> Probing Strategist</span>.
              Research question: <span className="text-emerald-400 font-bold">Is Solo LLM just as good as grounded agents?</span>
            </p>

            <button
              onClick={() => handleStart('tough', 'market', { scenario: 'used_car' })}
              className="mt-6 px-8 py-3 rounded-lg text-sm font-bold uppercase tracking-wider bg-emerald-700 text-white hover:bg-emerald-600 active:scale-95 transition-all"
            >
              🏪 Run Market Stress Test
            </button>

            <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-4xl mx-auto text-left">
              <div className="rounded-xl border border-red-500/40 bg-red-950/20 p-5">
                <div className="text-2xl mb-2">🔴</div>
                <h3 className="text-white font-bold text-sm mb-2">Solo LLM</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Raw ClaudeHaikuLLM with no tools. Produces format failures, floor violations, and phantom concessions at 3.2× normal rate.
                </p>
              </div>
              <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-5">
                <div className="text-2xl mb-2">🟡</div>
                <h3 className="text-white font-bold text-sm mb-2">Math Geek</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Deterministic OfferGenerator computes price; LLM only narrates. Zero numeric hallucination by design.
                </p>
              </div>
              <div className="rounded-xl border border-blue-500/40 bg-blue-950/20 p-5">
                <div className="text-2xl mb-2">🔵</div>
                <h3 className="text-white font-bold text-sm mb-2">Probing Strategist</h3>
                <p className="text-gray-400 text-xs leading-relaxed">
                  Competitive-cooperative hybrid. Anchors aggressively (8% concession) then switches to cooperative (22%) when gap &lt; $60.
                </p>
              </div>
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
                {marketScenario === 'used_car' ? 'Honda Civic 2021 · Used Car Market' :
                 marketScenario === 'sneaker' ? 'Limited Edition Sneakers · Sneaker Market' :
                 marketScenario}
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

                {/* Seller archetype performance */}
                <div className="rounded-xl border border-violet-700/40 bg-violet-950/20 p-5">
                  <div className="text-xs font-bold uppercase tracking-widest text-violet-400 mb-3">
                    📊 Archetype Performance
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
      </main>
    </div>
  )
}
