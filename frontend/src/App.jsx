/**
 * Negotiation War Room — main layout.
 *
 * ┌──────────────── ControlBar ─────────────────────────┐
 * │                                                      │
 * │  ┌─ ProviderBoard ──────────────────────────────┐  │
 * │  │  3 provider cards with live prices            │  │
 * │  └──────────────────────────────────────────────┘  │
 * │                                                      │
 * │  ┌─ DealRadar ───┐  ┌─ ConvergenceLine ──────────┐ │
 * │  │  Radar chart  │  │  Gap closing over rounds    │ │
 * │  └───────────────┘  └────────────────────────────┘ │
 * │                                                      │
 * │  ┌─ ThoughtFeed (full width) ─────────────────────┐ │
 * │  │  Streaming [STRATEGY][TOOL_CALL][MATH][DECISION]│ │
 * │  └─────────────────────────────────────────────────┘ │
 * │                                                      │
 * │  ┌─ DealSummary ──────────────────────────────────┐ │
 * │  │  Outcome banner (shown on completion)           │ │
 * │  └─────────────────────────────────────────────────┘ │
 * └──────────────────────────────────────────────────────┘
 *
 * VetoFlash overlays the top of the screen whenever a VETO fires.
 */

import React, { useCallback, useState } from 'react'
import ControlBar from './components/ControlBar'
import ConvergenceLine from './components/ConvergenceLine'
import DealRadar from './components/DealRadar'
import DealSummary from './components/DealSummary'
import ProviderBoard from './components/ProviderBoard'
import ThoughtFeed from './components/ThoughtFeed'
import VetoFlash from './components/VetoFlash'
import { useNegotiationStream } from './hooks/useNegotiationStream'

export default function App() {
  const [activePurchaserType, setActivePurchaserType] = useState('tough')
  const [activeMode, setActiveMode] = useState('demo')

  const {
    status,
    mode,
    purchaserType,
    providers,
    thoughts,
    radarData,
    convergenceHistory,
    veto,
    vetoVisible,
    outcome,
    deal,
    currentRound,
    connect,
    reset,
  } = useNegotiationStream()

  const handleStart = useCallback(
    (type, m) => {
      const resolvedMode = m ?? activeMode
      setActivePurchaserType(type)
      setActiveMode(resolvedMode)
      connect(type, resolvedMode)
    },
    [connect, activeMode]
  )

  const handleModeChange = useCallback((m) => {
    setActiveMode(m)
  }, [])

  const handleReset = useCallback(() => {
    reset()
    setActivePurchaserType('tough')
  }, [reset])

  // Extract last provider name from radar for the chart label
  const lastRadarProvider =
    convergenceHistory.length > 0
      ? convergenceHistory[convergenceHistory.length - 1].provider_name
      : undefined

  return (
    <div className="min-h-screen bg-war-bg text-gray-200 flex flex-col">
      {/* Veto overlay */}
      <VetoFlash veto={veto} visible={vetoVisible} />

      {/* Header */}
      <ControlBar
        status={status}
        mode={activeMode}
        purchaserType={activePurchaserType}
        currentRound={currentRound}
        maxRounds={6}
        onStart={handleStart}
        onReset={handleReset}
        onModeChange={handleModeChange}
      />

      {/* Main content */}
      <main className="flex-1 max-w-[1600px] w-full mx-auto px-4 py-6 space-y-6">

        {/* ── Intro banner (idle state) ───────────────────────────── */}
        {status === 'idle' && (
          <div className="border border-war-border rounded-xl bg-war-panel/50 px-8 py-10 text-center space-y-3">
            <p className="text-4xl mb-2">⚔️</p>
            <h2 className="text-white font-black text-xl tracking-wide">
              Grounded Agents vs. Solo LLMs
            </h2>
            <p className="text-gray-400 text-sm max-w-2xl mx-auto leading-relaxed">
              Watch an Agentic Purchaser use <span className="text-war-accent font-bold">PriceOracle</span>,{' '}
              <span className="text-war-accent font-bold">UtilityCalculator</span>, and{' '}
              <span className="text-war-accent font-bold">MarginValidator</span> to negotiate
              10 pairs of Limited Edition Sneakers — <em>rejecting friendly offers</em> when
              the math doesn't check out.
            </p>
            <div className="flex justify-center gap-4 pt-2 text-xs text-gray-500">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-war-accent" /> Purchaser: Tough Buyer (Price 70%)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-war-red" /> Purchaser: Emergency Buyer (Speed 70%)
              </span>
            </div>
            <div className="flex items-center justify-center gap-3 mt-4">
              <button
                onClick={() => handleStart('tough', 'demo')}
                className="px-6 py-3 rounded-xl bg-war-purple text-white font-black uppercase tracking-widest text-sm hover:bg-purple-500 transition-colors active:scale-95"
              >
                🎬 Play Demo
              </button>
              <button
                onClick={() => handleStart('tough', 'live')}
                className="px-6 py-3 rounded-xl bg-war-green text-black font-black uppercase tracking-widest text-sm hover:bg-emerald-400 transition-colors active:scale-95"
              >
                🤖 Run Live LLM
              </button>
            </div>
          </div>
        )}

        {/* ── Provider board ──────────────────────────────────────── */}
        {Object.keys(providers).length > 0 && (
          <div className="bg-war-panel border border-war-border rounded-xl p-5 scanlines relative">
            <ProviderBoard
              providers={providers}
              convergenceHistory={convergenceHistory}
            />
          </div>
        )}

        {/* ── Charts row ──────────────────────────────────────────── */}
        {(status !== 'idle' || radarData.length > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-war-panel border border-war-border rounded-xl p-5 h-72">
              <DealRadar data={radarData} provider={lastRadarProvider} />
            </div>
            <div className="bg-war-panel border border-war-border rounded-xl p-5 h-72">
              <ConvergenceLine history={convergenceHistory} />
            </div>
          </div>
        )}

        {/* ── Thought feed ────────────────────────────────────────── */}
        {thoughts.length > 0 && (
          <div className="bg-war-panel border border-war-border rounded-xl p-5 h-96">
            <ThoughtFeed thoughts={thoughts} />
          </div>
        )}

        {/* ── Deal summary (on completion) ─────────────────────────── */}
        {outcome && <DealSummary outcome={outcome} deal={deal} />}

        {/* ── Grounding explainer ─────────────────────────────────── */}
        {status === 'done' && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pb-6">
            {[
              {
                icon: '🔮',
                title: 'PriceOracle',
                desc: 'Anchors the Purchaser to market reality ($150 avg) before any offer is evaluated. Prevents the "friendly price" hallucination trap.',
                color: 'border-cyan-500/30 bg-cyan-900/10',
              },
              {
                icon: '🧮',
                title: 'UtilityCalculator',
                desc: 'Scores every proposed deal 0–100 using hidden buyer weights. An offer that LOOKS good may SCORE badly — the agent won\'t be fooled.',
                color: 'border-purple-500/30 bg-purple-900/10',
              },
              {
                icon: '🚫',
                title: 'MarginValidator',
                desc: 'Guards Providers from their own desperation. If a concession would breach the floor price, the offer is HARD VETOED before it reaches the buyer.',
                color: 'border-red-500/30 bg-red-900/10',
              },
            ].map(({ icon, title, desc, color }) => (
              <div
                key={title}
                className={`rounded-xl border p-5 ${color} animate-fade-in`}
              >
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
