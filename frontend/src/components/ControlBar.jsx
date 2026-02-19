/**
 * ControlBar — header controls for starting a new negotiation session.
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
  purchaserType,
  currentRound,
  maxRounds = 6,
  onStart,
  onReset,
}) {
  const isRunning = status === 'running' || status === 'connecting'

  return (
    <header className="bg-war-panel border-b border-war-border px-6 py-4">
      <div className="max-w-[1600px] mx-auto flex items-center gap-4 flex-wrap">
        {/* Brand */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="w-8 h-8 bg-war-accent/20 border border-war-accent/40 rounded flex items-center justify-center">
            <span className="text-war-accent text-sm">⚔</span>
          </div>
          <div>
            <h1 className="text-white font-black text-sm tracking-widest uppercase">
              Negotiation War Room
            </h1>
            <p className="text-gray-600 text-xs">Grounded Agents Demo</p>
          </div>
        </div>

        {/* Spacer */}
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

        {/* Purchaser type toggle */}
        <div className="flex rounded-lg overflow-hidden border border-war-border">
          {['tough', 'emergency'].map((type) => (
            <button
              key={type}
              disabled={isRunning}
              onClick={() => !isRunning && onStart(type)}
              className={clsx(
                'px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors',
                purchaserType === type && !isRunning
                  ? 'bg-war-accent text-black'
                  : 'bg-war-panel text-gray-400 hover:bg-war-border disabled:cursor-not-allowed disabled:opacity-50'
              )}
            >
              {type === 'tough' ? '💪 Tough' : '🚨 Emergency'}
            </button>
          ))}
        </div>

        {/* Start / Reset buttons */}
        <button
          onClick={() => onStart(purchaserType)}
          disabled={isRunning}
          className={clsx(
            'px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all',
            isRunning
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-war-green text-black hover:bg-emerald-400 active:scale-95'
          )}
        >
          {isRunning ? 'Running…' : '▶ Start Demo'}
        </button>

        <button
          onClick={onReset}
          className="px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider bg-war-border text-gray-400 hover:text-white hover:bg-gray-600 transition-all active:scale-95"
        >
          ↺ Reset
        </button>
      </div>
    </header>
  )
}
