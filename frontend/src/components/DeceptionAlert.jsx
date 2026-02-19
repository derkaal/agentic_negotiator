/**
 * DeceptionAlert — full-width adversarial warning banner.
 *
 * Displayed whenever ContractValidator or MarketOracle detects a deception
 * tactic.  More persistent than VetoFlash — stays visible and appends to a
 * scrollable history so the user can review all attacks in one panel.
 */

import React from 'react'
import clsx from 'clsx'

const TACTIC_META = {
  BAIT_AND_SWITCH: {
    label: 'Bait-and-Switch',
    icon:  '🎣',
    color: 'border-red-500 bg-red-950/60',
    badge: 'bg-red-600 text-white',
    glow:  'shadow-red-900/50',
  },
  FEE_INJECTION: {
    label: 'Fee Injection',
    icon:  '💉',
    color: 'border-orange-500 bg-orange-950/60',
    badge: 'bg-orange-600 text-white',
    glow:  'shadow-orange-900/50',
  },
  PHANTOM_SCARCITY: {
    label: 'Phantom Scarcity',
    icon:  '👻',
    color: 'border-yellow-500 bg-yellow-950/40',
    badge: 'bg-yellow-600 text-black',
    glow:  'shadow-yellow-900/30',
  },
}

const SEVERITY_LABEL = {
  CRITICAL: { text: 'CRITICAL', cls: 'bg-red-700 text-white' },
  WARNING:  { text: 'WARNING',  cls: 'bg-yellow-600 text-black' },
}

function AlertCard({ alert }) {
  const meta     = TACTIC_META[alert.tactic]     ?? TACTIC_META.BAIT_AND_SWITCH
  const severity = SEVERITY_LABEL[alert.severity] ?? SEVERITY_LABEL.WARNING

  return (
    <div
      className={clsx(
        'rounded-lg border-2 p-4 shadow-lg animate-fade-in',
        meta.color,
        meta.glow,
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-lg">{meta.icon}</span>
        <span className={clsx('text-xs font-black px-2 py-0.5 rounded tracking-widest', meta.badge)}>
          {meta.label.toUpperCase()}
        </span>
        <span className={clsx('text-xs font-bold px-2 py-0.5 rounded', severity.cls)}>
          {severity.text}
        </span>
        <span className="ml-auto text-gray-500 text-xs font-mono">Round {alert.round}</span>
      </div>

      {/* Message */}
      <p className="text-xs font-mono leading-relaxed text-gray-200">
        {alert.message}
      </p>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Flash overlay — fires immediately on new CRITICAL alert
// ---------------------------------------------------------------------------

export function DeceptionFlash({ alert, visible }) {
  if (!alert || alert.severity !== 'CRITICAL') return null

  return (
    <div
      className={clsx(
        'fixed inset-x-0 top-0 z-50 transition-all duration-300',
        visible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0',
      )}
    >
      {/* Animated scan-line overlay */}
      <div className="relative bg-red-950/98 border-b-4 border-red-400 shadow-2xl shadow-red-900">
        {/* Pulsing edge glow */}
        <div className="absolute inset-0 border-2 border-red-400/30 animate-pulse pointer-events-none" />

        <div className="max-w-5xl mx-auto px-6 py-4 flex items-start gap-4">
          {/* Animated warning icon */}
          <div className="flex-shrink-0 mt-0.5 animate-bounce">
            <svg className="w-7 h-7 text-red-300" fill="none" viewBox="0 0 24 24"
              stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0
                   2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898
                   0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-1 flex-wrap">
              <span className="text-red-200 font-black text-base tracking-wider uppercase">
                🚨 ALERT: ADVERSARIAL DISCREPANCY DETECTED. TRANSACTION HALTED.
              </span>
            </div>
            <p className="text-red-300 text-xs font-mono leading-relaxed">
              {alert.message}
            </p>
            <div className="flex gap-3 mt-2 text-xs text-red-400 font-mono">
              <span>Tactic: <strong className="text-red-200">
                {TACTIC_META[alert.tactic]?.label ?? alert.tactic}
              </strong></span>
              <span>Severity: <strong className="text-red-200">{alert.severity}</strong></span>
              <span>Round: <strong className="text-red-200">{alert.round}</strong></span>
            </div>
          </div>

          {/* BLOCKED badge */}
          <div className="flex-shrink-0 border-2 border-red-400 rounded px-3 py-2 text-center">
            <div className="text-red-200 font-black text-xs tracking-widest">CONTRACT</div>
            <div className="text-red-300 font-black text-sm tracking-widest animate-pulse-fast">BLOCKED</div>
          </div>
        </div>
      </div>
    </div>
  )
}


// ---------------------------------------------------------------------------
// Attack Log panel — persistent sidebar / section showing all alerts
// ---------------------------------------------------------------------------

export default function DeceptionAlertLog({ alerts = [] }) {
  if (alerts.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-gray-600" />
          <h2 className="text-war-accent text-xs font-bold uppercase tracking-widest">
            Attack Monitor
          </h2>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <p className="text-gray-600 text-xs text-center">
            No adversarial signals detected yet…
          </p>
        </div>
      </div>
    )
  }

  const criticals = alerts.filter(a => a.severity === 'CRITICAL').length
  const warnings  = alerts.filter(a => a.severity === 'WARNING').length

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-war-red animate-pulse" />
        <h2 className="text-war-red text-xs font-bold uppercase tracking-widest">
          Attack Monitor
        </h2>
        <div className="ml-auto flex gap-2">
          {criticals > 0 && (
            <span className="bg-red-700 text-white text-xs font-bold px-2 py-0.5 rounded">
              {criticals} BLOCKED
            </span>
          )}
          {warnings > 0 && (
            <span className="bg-yellow-600 text-black text-xs font-bold px-2 py-0.5 rounded">
              {warnings} WARNING
            </span>
          )}
        </div>
      </div>

      {/* Alert cards */}
      <div className="flex-1 overflow-y-auto space-y-3 min-h-0 pr-1">
        {alerts.map((alert, i) => (
          <AlertCard key={i} alert={alert} />
        ))}
      </div>
    </div>
  )
}
