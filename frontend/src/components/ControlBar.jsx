/**
 * ControlBar — header controls for the stress test suite.
 * Simplified to focus only on Market mode.
 */

import React from 'react'
import clsx from 'clsx'

const STATUS_COLORS = {
  idle:       'bg-gray-600',
  connecting: 'bg-yellow-500 animate-pulse',
  running:    'bg-emerald-500 animate-pulse',
  done:       'bg-cyan-500',
  error:      'bg-red-500',
}

const STATUS_LABELS = {
  idle:       'IDLE',
  connecting: 'CONNECTING…',
  running:    'LIVE',
  done:       'COMPLETE',
  error:      'ERROR',
}

export default function ControlBar({
  status,
  mode = 'market',
  currentRound,
  maxRounds = 15,
  onStart,
  onReset,
}) {
  const isRunning = status === 'running' || status === 'connecting'

  return (
    <header className="bg-war-panel border-b border-war-border px-6 py-3">
      <div className="max-w-[1600px] mx-auto space-y-3">

        {/* Row 1: Brand + Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-emerald-500/20 border border-emerald-500/40 rounded flex items-center justify-center">
              <span className="text-emerald-400 text-sm">🏪</span>
            </div>
            <div>
              <h1 className="text-white font-black text-sm tracking-widest uppercase">
                MBMPMS Stress Test Suite
              </h1>
              <p className="text-gray-600 text-xs">3×3 Market · Three Seller Archetypes</p>
            </div>
          </div>

          <div className="flex-1" />

          {/* Status indicator */}
          <div className="flex items-center gap-2">
            <div className={clsx('w-2 h-2 rounded-full', STATUS_COLORS[status] ?? 'bg-gray-600')} />
            <span className="text-xs text-gray-400 font-mono">{STATUS_LABELS[status] ?? status}</span>
            {status === 'running' && (
              <span className="text-xs text-gray-500 font-mono">
                R{currentRound}/{maxRounds}
              </span>
            )}
          </div>
        </div>

        {/* Row 2: Controls */}
        <div className="flex items-center gap-3 flex-wrap">

          {/* Market mode indicator */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className="bg-emerald-900/60 border border-emerald-600/50 text-emerald-300 text-xs font-bold px-2 py-1 rounded font-mono animate-pulse">
              🏪 3×3 MARKET
            </span>
            <span className="text-emerald-400 text-xs font-mono">Parallel · Switch&lt;40</span>
          </div>

          <div className="flex-1" />

          {/* Start button */}
          <button
            onClick={() => onStart('tough', 'market', { scenario: 'used_car' })}
            disabled={isRunning}
            className={clsx(
              'px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all whitespace-nowrap flex-shrink-0',
              isRunning
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-emerald-700 text-white hover:bg-emerald-600 active:scale-95'
            )}
          >
            {isRunning ? 'Running…' : '🏪 Run Market'}
          </button>

          {/* Reset button */}
          <button
            onClick={onReset}
            className="px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider bg-war-border text-gray-400 hover:text-white hover:bg-gray-600 transition-all active:scale-95 flex-shrink-0"
          >
            ↺ Reset
          </button>
        </div>

      </div>
    </header>
  )
}
