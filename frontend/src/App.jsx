/**
 * Negotiation War Room — main layout.
 *
 * Standard layout (demo / live):
 *   ControlBar → ProviderBoard → Charts → ThoughtFeed → DealSummary
 *
 * Hostile layout adds:
 *   ThreatBrief banner → Attack Monitor panel (alongside ThoughtFeed)
 *   DeceptionFlash overlay on every CRITICAL alert
 */

import React, { useCallback, useState } from 'react'
import clsx from 'clsx'
import ControlBar from './components/ControlBar'
import ConvergenceLine from './components/ConvergenceLine'
import DealRadar from './components/DealRadar'
import DealSummary from './components/DealSummary'
import DeceptionAlertLog, { DeceptionFlash } from './components/DeceptionAlert'
import ProviderBoard from './components/ProviderBoard'
import ThoughtFeed from './components/ThoughtFeed'
import VetoFlash from './components/VetoFlash'
import { useNegotiationStream } from './hooks/useNegotiationStream'

export default function App() {
  const [activePurchaserType, setActivePurchaserType] = useState('tough')
  const [activeMode, setActiveMode]                   = useState('demo')

  const {
    status, mode,
    isHostile, threatBrief,
    providers, thoughts, radarData, convergenceHistory,
    veto, vetoVisible,
    deceptionAlerts, latestDeceptionAlert, deceptionFlashVisible,
    outcome, deal, currentRound,
    connect, reset,
  } = useNegotiationStream()

  const handleStart = useCallback((type, m) => {
    const resolvedMode = m ?? activeMode
    setActivePurchaserType(type)
    setActiveMode(resolvedMode)
    connect(type, resolvedMode)
  }, [connect, activeMode])

  const handleModeChange = useCallback((m) => setActiveMode(m), [])

  const handleReset = useCallback(() => {
    reset()
    setActivePurchaserType('tough')
  }, [reset])

  const lastRadarProvider =
    convergenceHistory.length > 0
      ? convergenceHistory[convergenceHistory.length - 1].provider_name
      : undefined

  const maxRounds = isHostile ? 3 : 6

  // ── Shield explainer cards ────────────────────────────────────────────
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
  const shields = isHostile ? HOSTILE_SHIELDS : STANDARD_SHIELDS

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
        onStart={handleStart}
        onReset={handleReset}
        onModeChange={handleModeChange}
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
              Three scenarios — all powered by{' '}
              <span className="text-war-accent font-bold">Claude Haiku 4.5</span> tool-calling.
              The <span className="text-war-red font-bold">Hostile</span> mode introduces a
              deceptive adversary that Bait-and-Switches, injects fees, and manufactures
              phantom scarcity — then shows the Cyborg Purchaser blocking every attack.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6 text-left max-w-3xl mx-auto">
              {[
                { mode: 'demo',    icon: '🎬', title: 'Scripted Demo',
                  desc: 'Pre-computed negotiation. No API key needed. Shows the core grounding loop.',
                  cls: 'border-war-purple/40 hover:border-war-purple' },
                { mode: 'live',    icon: '🤖', title: 'Live LLM',
                  desc: 'Real Claude Haiku 4.5 reasoning + tool-calling. Each run is unique.',
                  cls: 'border-war-green/40 hover:border-war-green' },
                { mode: 'hostile', icon: '☠',  title: 'Hostile Red Team',
                  desc: '3-round adversarial attack. ContractValidator + MarketOracle shields active.',
                  cls: 'border-war-red/40 hover:border-war-red' },
              ].map(({ mode: m, icon, title, desc, cls }) => (
                <button
                  key={m}
                  onClick={() => handleStart('tough', m)}
                  className={clsx(
                    'rounded-xl border-2 bg-war-panel/60 p-5 text-left transition-all active:scale-95',
                    cls,
                  )}
                >
                  <div className="text-2xl mb-2">{icon}</div>
                  <div className="text-white font-bold text-sm mb-1">{title}</div>
                  <div className="text-gray-400 text-xs leading-relaxed">{desc}</div>
                </button>
              ))}
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
              : 'bg-war-panel border-war-border',
          )}>
            <ProviderBoard providers={providers} convergenceHistory={convergenceHistory} />
          </div>
        )}

        {/* ── Charts row ─────────────────────────────────────────────── */}
        {(status !== 'idle' || radarData.length > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className={clsx(
              'border rounded-xl p-5 h-72',
              isHostile ? 'bg-red-950/20 border-red-800/40' : 'bg-war-panel border-war-border',
            )}>
              <DealRadar data={radarData} provider={lastRadarProvider} />
            </div>
            <div className={clsx(
              'border rounded-xl p-5 h-72',
              isHostile ? 'bg-red-950/20 border-red-800/40' : 'bg-war-panel border-war-border',
            )}>
              <ConvergenceLine history={convergenceHistory} />
            </div>
          </div>
        )}

        {/* ── Feed row: ThoughtFeed + (hostile) Attack Monitor ─────── */}
        {thoughts.length > 0 && (
          <div className={clsx(
            'grid gap-6',
            isHostile ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1',
          )}>
            {/* Thought Feed */}
            <div className={clsx(
              'border rounded-xl p-5 h-[480px]',
              isHostile ? 'bg-red-950/10 border-red-900/50' : 'bg-war-panel border-war-border',
            )}>
              <ThoughtFeed thoughts={thoughts} />
            </div>

            {/* Attack Monitor — hostile only */}
            {isHostile && (
              <div className="bg-war-panel border border-war-border rounded-xl p-5 h-[480px]">
                <DeceptionAlertLog alerts={deceptionAlerts} />
              </div>
            )}
          </div>
        )}

        {/* ── Deal summary ───────────────────────────────────────────── */}
        {outcome && (
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
