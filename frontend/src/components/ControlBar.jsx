/**
 * ControlBar — header controls for starting a new negotiation session.
 *
 * Includes the A/B Test Anchor toggle:
 *   [Anchor: ON]  → Cyborg mode — full LangChain StateGraph with tools
 *   [Anchor: OFF] → Solo mode   — bare LLM, no tools, susceptible to pressure
 */

import React from 'react'
import clsx from 'clsx'

const STATUS_COLORS = {
  idle:       'bg-gray-600',
  connecting: 'bg-yellow-500 animate-pulse',
  running:    'bg-war-green animate-pulse',
  done:       'bg-war-accent',
  error:      'bg-war-red',
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
  mode,
  purchaserType,
  currentRound,
  maxRounds = 6,
  anchorEnabled = true,
  onStart,
  onReset,
  onModeChange,
  onAnchorToggle,
}) {
  const isRunning  = status === 'running' || status === 'connecting'
  const isAbTest   = mode === 'ab-test'
  const isSolo     = mode === 'solo'
  const isTask     = mode === 'task'
  const isMarket   = mode === 'market'
  const isSneaker  = mode === 'sneaker'

  return (
    <header className="bg-war-panel border-b border-war-border px-6 py-3">
      <div className="max-w-[1600px] mx-auto space-y-3">

        {/* Row 1: Brand + Status */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-war-accent/20 border border-war-accent/40 rounded flex items-center justify-center">
              <span className="text-war-accent text-sm">⚔</span>
            </div>
            <div>
              <h1 className="text-white font-black text-sm tracking-widest uppercase">
                Negotiation War Room
              </h1>
              <p className="text-gray-600 text-xs">Grounded Agents — Claude Haiku 4.5</p>
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

        {/* Row 2: All controls */}
        <div className="flex items-center gap-3 flex-wrap">

          {/* Mode toggle */}
          <div className="flex rounded-lg border border-war-border overflow-hidden flex-shrink-0">
            {[
              { id: 'demo',    label: '🎬 Demo',    activeClass: 'bg-war-purple text-white' },
              { id: 'live',    label: '🤖 Live',    activeClass: 'bg-war-green  text-black' },
              { id: 'hostile', label: '☠ Hostile', activeClass: 'bg-war-red    text-white' },
              { id: 'solo',    label: '🧠 Solo',    activeClass: 'bg-orange-600 text-white' },
              { id: 'ab-test', label: '⚗️ A/B Test', activeClass: 'bg-violet-700 text-white' },
              { id: 'task',    label: '⚖ Task',    activeClass: 'bg-cyan-700   text-white' },
              { id: 'market',  label: '🏪 Market',  activeClass: 'bg-emerald-700 text-white' },
              { id: 'sneaker', label: '👟 Sneaker', activeClass: 'bg-red-700    text-white' },
            ].map(({ id, label, activeClass }) => (
              <button
                key={id}
                disabled={isRunning}
                onClick={() => !isRunning && onModeChange(id)}
                className={clsx(
                  'px-3 py-2 text-xs font-bold uppercase tracking-wider transition-colors whitespace-nowrap',
                  mode === id && !isRunning
                    ? activeClass
                    : 'bg-war-panel text-gray-400 hover:bg-war-border disabled:cursor-not-allowed disabled:opacity-50'
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {/* ── Anchor Toggle ── (shown for all modes except hostile, ab-test, task, market, sneaker) */}
          {mode !== 'hostile' && mode !== 'ab-test' && mode !== 'task' && mode !== 'market' && mode !== 'sneaker' && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="text-xs text-gray-500 font-mono">Anchor:</span>
              <button
                disabled={isRunning}
                onClick={() => !isRunning && onAnchorToggle?.(!anchorEnabled)}
                className={clsx(
                  'relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 focus:outline-none flex-shrink-0',
                  anchorEnabled
                    ? 'bg-cyan-600 disabled:opacity-60'
                    : 'bg-orange-700/80 disabled:opacity-60',
                  isRunning && 'cursor-not-allowed',
                )}
                title={anchorEnabled
                  ? 'Anchor ON — Cyborg mode: tools enabled, grounded'
                  : 'Anchor OFF — Solo mode: no tools, susceptible to pressure'}
              >
                <span
                  className={clsx(
                    'inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200',
                    anchorEnabled ? 'translate-x-6' : 'translate-x-1',
                  )}
                />
              </button>
              <span className={clsx(
                'text-xs font-bold font-mono whitespace-nowrap',
                anchorEnabled ? 'text-cyan-400' : 'text-orange-400',
              )}>
                {anchorEnabled ? 'ON (Cyborg)' : 'OFF (Solo)'}
              </span>
            </div>
          )}

          {/* A/B Test indicator (non-interactive) */}
          {isAbTest && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="bg-violet-900/60 border border-violet-600/50 text-violet-300 text-xs font-bold px-2 py-1 rounded font-mono">
                SOLO vs CYBORG
              </span>
              <span className="text-violet-400 text-xs font-mono">comparison active</span>
            </div>
          )}

          {/* Task mode indicator */}
          {isTask && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="bg-cyan-900/60 border border-cyan-600/50 text-cyan-300 text-xs font-bold px-2 py-1 rounded font-mono">
                ⚖ AGENTICPAY
              </span>
              <span className="text-cyan-400 text-xs font-mono">Algorithm 1</span>
            </div>
          )}

          {/* Market mode indicator */}
          {isMarket && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="bg-emerald-900/60 border border-emerald-600/50 text-emerald-300 text-xs font-bold px-2 py-1 rounded font-mono animate-pulse">
                🏪 3×3 MARKET
              </span>
              <span className="text-emerald-400 text-xs font-mono">Parallel · Switch&lt;40</span>
            </div>
          )}

          {/* Sneaker mode indicator */}
          {isSneaker && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <span className="bg-red-900/60 border border-red-600/50 text-red-300 text-xs font-bold px-2 py-1 rounded font-mono animate-pulse">
                👟 SNEAKER RACE
              </span>
              <span className="text-red-400 text-xs font-mono">Solo vs Cyborg A vs Cyborg B</span>
            </div>
          )}

          {/* Solo mode indicator */}
          {isSolo && (
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <span className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
              <span className="text-orange-400 text-xs font-mono font-bold">UNGROUNDED</span>
            </div>
          )}

          {/* Purchaser type toggle (hidden in market/sneaker mode) */}
          {!isMarket && !isSneaker && (
            <div className="flex rounded-lg border border-war-border overflow-hidden flex-shrink-0">
              {['tough', 'emergency'].map((type) => (
                <button
                  key={type}
                  disabled={isRunning}
                  onClick={() => !isRunning && onStart(type, mode)}
                  className={clsx(
                    'px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors whitespace-nowrap',
                    purchaserType === type && !isRunning
                      ? 'bg-war-accent text-black'
                      : 'bg-war-panel text-gray-400 hover:bg-war-border disabled:cursor-not-allowed disabled:opacity-50'
                  )}
                >
                  {type === 'tough' ? '💪 Tough' : '🚨 Emergency'}
                </button>
              ))}
            </div>
          )}

          <div className="flex-1" />

          {/* Start button */}
          <button
            onClick={() => onStart(
              purchaserType, mode,
              isMarket ? { scenario: 'sneaker' } : undefined,
            )}
            disabled={isRunning}
            className={clsx(
              'px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all whitespace-nowrap flex-shrink-0',
              isRunning
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : mode === 'hostile'
                ? 'bg-war-red text-white hover:bg-red-600 active:scale-95'
                : mode === 'live'
                ? 'bg-war-green text-black hover:bg-emerald-400 active:scale-95'
                : mode === 'solo'
                ? 'bg-orange-600 text-white hover:bg-orange-500 active:scale-95'
                : mode === 'ab-test'
                ? 'bg-violet-700 text-white hover:bg-violet-600 active:scale-95'
                : mode === 'task'
                ? 'bg-cyan-700 text-white hover:bg-cyan-600 active:scale-95'
                : mode === 'market'
                ? 'bg-emerald-700 text-white hover:bg-emerald-600 active:scale-95'
                : mode === 'sneaker'
                ? 'bg-red-700 text-white hover:bg-red-600 active:scale-95'
                : 'bg-war-purple text-white hover:bg-purple-500 active:scale-95'
            )}
          >
            {isRunning
              ? 'Running…'
              : mode === 'hostile'
              ? '☠ Launch Attack'
              : mode === 'live'
              ? '▶ Run Live'
              : mode === 'solo'
              ? '🧠 Run Solo'
              : mode === 'ab-test'
              ? '⚗️ Run A/B Test'
              : mode === 'task'
              ? '⚖ Run Task'
              : mode === 'market'
              ? '🏪 Run Market'
              : mode === 'sneaker'
              ? '👟 Run Sneaker'
              : '▶ Play Demo'
            }
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
