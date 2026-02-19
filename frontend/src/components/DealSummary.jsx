/**
 * DealSummary — shown when negotiation ends (ACCEPT or NO_DEAL).
 */

import React from 'react'
import clsx from 'clsx'

export default function DealSummary({ outcome, deal, hostile = false }) {
  if (!outcome) return null

  const accepted = outcome === 'ACCEPT'

  const subtitle = hostile
    ? accepted
      ? `Cyborg Purchaser survived ${deal?.deception_attempts ?? 0} adversarial attack(s) and closed a clean deal.`
      : 'All 3 rounds were adversarially tainted. Cyborg walked away — buyer protected.'
    : accepted
    ? 'Grounded Agent secured the best available offer.'
    : "Math didn't check out — agent protected the buyer."

  return (
    <div
      className={clsx(
        'rounded-xl border-2 p-5 animate-fade-in',
        hostile
          ? accepted
            ? 'border-war-green/60 bg-emerald-950/30'
            : 'border-war-red/60 bg-red-950/30'
          : accepted
          ? 'border-war-green/60 bg-emerald-900/20'
          : 'border-war-red/60 bg-red-900/20'
      )}
    >
      <div className="flex items-center gap-3 mb-4">
        <span className="text-2xl">{accepted ? (hostile ? '🛡' : '✅') : '❌'}</span>
        <div>
          <h3 className={clsx('font-black text-lg tracking-wide', accepted ? 'text-war-green' : 'text-war-red')}>
            {hostile
              ? accepted ? 'SHIELD HELD — DEAL SECURED' : 'NO DEAL — ADVERSARY BLOCKED'
              : accepted ? 'DEAL CLOSED'                 : 'NO DEAL — WALKED AWAY'}
          </h3>
          <p className="text-gray-400 text-xs">{subtitle}</p>
        </div>

        {/* Hostile badge */}
        {hostile && deal?.deception_attempts != null && (
          <div className="ml-auto text-right">
            <div className="text-xs font-bold text-red-400 font-mono">
              {deal.deception_attempts} ATTACK{deal.deception_attempts !== 1 ? 'S' : ''} BLOCKED
            </div>
            <div className="text-xs text-gray-500 font-mono">
              Clean offer: Round {deal.clean_after_round}
            </div>
          </div>
        )}
      </div>

      {accepted && deal && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: 'Provider',     value: deal.provider_name },
            { label: 'Price / Pair', value: `$${deal.price?.toFixed(2)}` },
            { label: 'Delivery',     value: `${deal.speed_days} days` },
            { label: 'Warranty',     value: `${deal.warranty_months} months` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-black/30 rounded-lg p-3 border border-war-border/50">
              <p className="text-gray-500 text-xs mb-1">{label}</p>
              <p className="text-white font-bold text-sm">{value}</p>
            </div>
          ))}
        </div>
      )}

      {accepted && deal && (
        <div className="mt-3 flex items-center gap-2">
          <div className="h-2 rounded-full bg-war-border flex-1">
            <div
              className="h-2 rounded-full bg-war-green transition-all duration-1000"
              style={{ width: `${Math.min(deal.utility_score, 100)}%` }}
            />
          </div>
          <span className="text-war-green text-xs font-bold w-16 text-right">
            {deal.utility_score?.toFixed(1)} / 100
          </span>
          <span className="text-gray-500 text-xs">Utility {hostile ? '(threshold: 60)' : ''}</span>
        </div>
      )}
    </div>
  )
}
