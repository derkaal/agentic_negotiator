/**
 * ProviderBoard — shows the 3 Provider cards with their opening asks and
 * live current offers.  The active provider glows cyan.
 */

import React from 'react'
import clsx from 'clsx'

const PROVIDER_META = {
  provider_1: { emoji: '👟', color: 'border-purple-500/40 bg-purple-900/10' },
  provider_2: { emoji: '👑', color: 'border-pink-500/40 bg-pink-900/10' },
  provider_3: { emoji: '⚡', color: 'border-orange-500/40 bg-orange-900/10' },
}

export default function ProviderBoard({ providers = {}, convergenceHistory = [] }) {
  // Build latest prices from convergence history
  const latestPrices = {}
  convergenceHistory.forEach((h) => {
    latestPrices[h.provider_id] = h.price
  })

  return (
    <div>
      <h2 className="text-war-accent text-xs font-bold uppercase tracking-widest mb-3">
        Provider Positions
      </h2>
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(providers).map(([pid, p]) => {
          const meta = PROVIDER_META[pid] ?? { emoji: '📦', color: 'border-gray-500/40' }
          const current = latestPrices[pid]
          const diff = current != null ? current - p.opening_ask : null

          return (
            <div
              key={pid}
              className={clsx(
                'rounded-lg border p-3 transition-all duration-300',
                meta.color
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{meta.emoji}</span>
                <span className="text-white text-xs font-bold truncate">
                  {p.name}
                </span>
              </div>

              <div className="space-y-1 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-gray-500">Ask</span>
                  <span className="text-gray-300">${p.opening_ask?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Current</span>
                  <span
                    className={clsx(
                      'font-bold',
                      current == null
                        ? 'text-gray-500'
                        : current < p.opening_ask
                        ? 'text-war-green'
                        : 'text-gray-300'
                    )}
                  >
                    {current != null ? `$${current.toFixed(2)}` : '—'}
                  </span>
                </div>
                {diff !== null && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Δ</span>
                    <span
                      className={clsx(
                        'font-bold text-xs',
                        diff < 0 ? 'text-war-green' : 'text-war-red'
                      )}
                    >
                      {diff < 0 ? '' : '+'}${diff.toFixed(2)}
                    </span>
                  </div>
                )}
                <div className="border-t border-war-border/50 pt-1 mt-1 space-y-0.5">
                  <div className="flex justify-between text-gray-600">
                    <span>Speed</span>
                    <span>{p.speed_days}d</span>
                  </div>
                  <div className="flex justify-between text-gray-600">
                    <span>Warranty</span>
                    <span>{p.warranty_months}mo</span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
