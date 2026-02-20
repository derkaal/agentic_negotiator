/**
 * HallucinationMonitor
 *
 * Renders in two distinct modes:
 *
 * 1. SOLO MODE (anchor OFF, single feed)
 *    — Persistent warning banner: "⚠️ RUNNING UNGROUNDED"
 *    — Per-round internal math vs ground-truth comparison rows
 *
 * 2. A/B TEST MODE (both feeds visible side-by-side)
 *    — tool_comparison events rendered as a "HALLUCINATION DELTA" card
 *    — Shows: Solo guess  |  Cyborg truth  |  Δ gap
 */

import React from 'react'
import clsx from 'clsx'

// ---------------------------------------------------------------------------
// Solo-mode banner — always visible when anchor is OFF
// ---------------------------------------------------------------------------

export function UngroundedBanner({ visible = true }) {
  if (!visible) return null
  return (
    <div className="rounded-xl border-2 border-amber-500/70 bg-amber-950/40 px-5 py-3 flex items-start gap-3 animate-fade-in">
      <span className="text-2xl flex-shrink-0 mt-0.5">⚠️</span>
      <div className="flex-1 min-w-0">
        <p className="text-amber-300 font-black text-xs uppercase tracking-widest mb-0.5">
          Hallucination Monitor — Anchor: OFF
        </p>
        <p className="text-amber-200/80 text-xs font-mono leading-relaxed">
          RUNNING UNGROUNDED: Agent is estimating value without a price anchor.
          All utility scores and market prices below are the agent's <em>guesses</em> —
          not verified data. The Cyborg with tools would have scored this deal at{' '}
          <span className="text-red-300 font-bold">REJECT</span>.
        </p>
      </div>
      <div className="flex-shrink-0">
        <span className="bg-amber-700/60 border border-amber-500/50 text-amber-200 text-xs font-bold px-2 py-1 rounded font-mono">
          NO ANCHOR
        </span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pressure Tactic Badges
// ---------------------------------------------------------------------------

const TACTIC_LABELS = {
  PHANTOM_SCARCITY:    { label: 'Phantom Scarcity',   color: 'bg-red-900/60 text-red-300 border-red-700/50' },
  TIME_PRESSURE:       { label: 'Time Pressure',       color: 'bg-orange-900/60 text-orange-300 border-orange-700/50' },
  SOCIAL_FLATTERY:     { label: 'Social Flattery',     color: 'bg-yellow-900/60 text-yellow-300 border-yellow-700/50' },
  FAKE_COMPETITION:    { label: 'Fake Competition',    color: 'bg-purple-900/60 text-purple-300 border-purple-700/50' },
  FAKE_URGENCY:        { label: 'Fake Urgency',        color: 'bg-orange-900/60 text-orange-300 border-orange-700/50' },
  ANCHOR_MANIPULATION: { label: 'Anchor Manipulation', color: 'bg-rose-900/60 text-rose-300 border-rose-700/50' },
}

function TacticBadge({ tactic }) {
  const cfg = TACTIC_LABELS[tactic] ?? { label: tactic, color: 'bg-gray-800 text-gray-400 border-gray-700' }
  return (
    <span className={clsx('text-xs font-bold px-2 py-0.5 rounded border', cfg.color)}>
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Social pressure event card
// ---------------------------------------------------------------------------

export function SocialPressureCard({ event }) {
  if (!event) return null
  return (
    <div className="rounded-lg border border-amber-600/50 bg-amber-950/30 p-3 animate-fade-in">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="text-amber-400 font-bold text-xs">⚡ PRESSURE TACTIC DETECTED</span>
        <span className="text-xs text-gray-500 font-mono">Round {event.round} · {event.provider}</span>
        <span className="ml-auto text-amber-400 font-bold text-xs font-mono">
          ${event.offer?.toFixed(2)}
        </span>
      </div>
      <p className="text-xs text-amber-200/70 font-mono italic leading-relaxed mb-2">
        "{event.message}"
      </p>
      {event.tactics?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {event.tactics.map((t) => <TacticBadge key={t} tactic={t} />)}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Internal math comparison row (solo internal math vs tool ground truth)
// ---------------------------------------------------------------------------

export function InternalMathCard({ event }) {
  if (!event) return null
  const tool = event.what_tool_would_say
  const hallScore = event.hallucinated_score ?? _extractScore(event.content)
  const realScore = tool?.overall_score
  const delta = hallScore != null && realScore != null
    ? Math.abs(hallScore - realScore).toFixed(2)
    : null

  return (
    <div className="rounded-lg border border-orange-700/50 bg-orange-950/20 p-3 animate-fade-in">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-orange-400 font-bold text-xs">🧠 SOLO INTERNAL MATH</span>
        <span className="text-xs text-gray-500 font-mono">Round {event.round} · ${event.offer_price?.toFixed(2)}</span>
        <span className="ml-auto text-xs font-bold text-orange-300 bg-orange-950/60 border border-orange-700/40 px-2 py-0.5 rounded font-mono">
          HALLUCINATION
        </span>
      </div>

      {/* Solo agent's guess */}
      <div className="mb-2">
        <p className="text-xs text-gray-400 mb-1 font-mono">Agent estimate (no tools):</p>
        <p className="text-xs text-orange-200/80 font-mono leading-relaxed italic">
          {event.content}
        </p>
      </div>

      {/* Ground truth comparison */}
      {tool && (
        <div className="mt-2 pt-2 border-t border-orange-800/40">
          <p className="text-xs text-gray-500 mb-1 font-mono">What utility_calculator WOULD have returned:</p>
          <div className="grid grid-cols-3 gap-2">
            <div className="text-center">
              <div className="text-orange-300 font-bold text-sm">
                {hallScore != null ? `${hallScore}/100` : '?'}
              </div>
              <div className="text-gray-500 text-xs font-mono">Solo guess</div>
            </div>
            <div className="text-center">
              <div className={clsx(
                'font-bold text-sm',
                realScore >= 55 ? 'text-emerald-400' : 'text-red-400',
              )}>
                {realScore != null ? `${realScore}/100` : '?'}
              </div>
              <div className="text-gray-500 text-xs font-mono">Tool truth</div>
            </div>
            <div className="text-center">
              <div className={clsx(
                'font-bold text-sm',
                delta > 15 ? 'text-red-400' : delta > 5 ? 'text-amber-400' : 'text-gray-400',
              )}>
                {delta != null ? `Δ ${delta}` : '—'}
              </div>
              <div className="text-gray-500 text-xs font-mono">Error gap</div>
            </div>
          </div>
          <div className="mt-1.5 flex gap-2 items-center">
            <span className={clsx(
              'text-xs font-bold px-2 py-0.5 rounded',
              tool.verdict === 'ACCEPT'
                ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50'
                : 'bg-red-900/50 text-red-300 border border-red-700/50',
            )}>
              TOOL VERDICT: {tool.verdict}
            </span>
            {tool.verdict === 'REJECT' && (
              <span className="text-xs text-red-400 font-mono">
                ← Solo agent didn't know this
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tool comparison card — the A/B test "smoking gun"
// ---------------------------------------------------------------------------

export function ToolComparisonCard({ event }) {
  if (!event) return null
  const { solo_estimate, cyborg_truth } = event
  const delta = cyborg_truth?.delta?.toFixed(2) ?? '?'

  return (
    <div className="rounded-xl border-2 border-red-500/70 bg-red-950/30 p-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-red-400 text-lg">🔬</span>
        <span className="text-red-300 font-black text-xs uppercase tracking-widest">
          Hallucination Delta — Round {event.round}
        </span>
        <span className="ml-auto text-xs text-gray-500 font-mono">${event.offer_price?.toFixed(2)} offer</span>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Solo column */}
        <div className="rounded-lg border border-orange-700/50 bg-orange-950/30 p-3">
          <div className="text-orange-300 text-xs font-bold mb-2 flex items-center gap-1">
            <span>🧠</span> Solo Agent
            <span className="ml-auto text-orange-500 text-xs font-mono">[NO ANCHOR]</span>
          </div>
          <div className="text-3xl font-black text-orange-300 mb-1">
            {solo_estimate?.score ?? '?'}<span className="text-base text-orange-500">/100</span>
          </div>
          <div className={clsx(
            'text-xs font-bold px-2 py-0.5 rounded inline-block',
            solo_estimate?.verdict === 'ACCEPT'
              ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50'
              : 'bg-red-900/50 text-red-300 border border-red-700/50',
          )}>
            {solo_estimate?.verdict ?? 'UNKNOWN'}
          </div>
          <p className="text-xs text-orange-200/60 font-mono mt-1.5">
            {solo_estimate?.reasoning ?? 'Intuition-based estimate'}
          </p>
        </div>

        {/* Cyborg column */}
        <div className="rounded-lg border border-cyan-700/50 bg-cyan-950/30 p-3">
          <div className="text-cyan-300 text-xs font-bold mb-2 flex items-center gap-1">
            <span>🤖</span> Cyborg Agent
            <span className="ml-auto text-cyan-500 text-xs font-mono">[ANCHORED]</span>
          </div>
          <div className="text-3xl font-black text-cyan-300 mb-1">
            {cyborg_truth?.score ?? '?'}<span className="text-base text-cyan-500">/100</span>
          </div>
          <div className={clsx(
            'text-xs font-bold px-2 py-0.5 rounded inline-block',
            cyborg_truth?.verdict === 'ACCEPT'
              ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50'
              : 'bg-red-900/50 text-red-300 border border-red-700/50',
          )}>
            {cyborg_truth?.verdict ?? 'UNKNOWN'}
          </div>
          <p className="text-xs text-cyan-200/60 font-mono mt-1.5">
            Verified via {cyborg_truth?.tool ?? 'utility_calculator'}
          </p>
        </div>
      </div>

      {/* Delta callout */}
      <div className="rounded-lg border border-red-600/60 bg-red-900/20 p-2.5 flex items-center gap-3">
        <span className="text-red-400 font-black text-xl">{delta}</span>
        <div>
          <p className="text-red-300 font-bold text-xs">point hallucination gap</p>
          <p className="text-red-400/70 text-xs font-mono">{event.message}</p>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Full monitor panel — used in the A/B test side panel
// ---------------------------------------------------------------------------

export default function HallucinationMonitor({
  isSolo = false,
  isAbTest = false,
  internalMathEvents = [],
  socialPressureEvents = [],
  toolComparisonEvents = [],
}) {
  if (!isSolo && !isAbTest) return null

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-amber-400 text-sm">⚠️</span>
        <h2 className="text-amber-400 text-xs font-bold uppercase tracking-widest">
          Hallucination Monitor
        </h2>
        <span className="ml-auto text-gray-600 text-xs">
          {internalMathEvents.length + toolComparisonEvents.length} events
        </span>
      </div>

      {isSolo && !isAbTest && (
        <div className="mb-3">
          <UngroundedBanner visible />
        </div>
      )}

      <div className="flex-1 overflow-y-auto min-h-0 pr-1 space-y-3">
        {[...socialPressureEvents, ...internalMathEvents, ...toolComparisonEvents].length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-xs text-center">
              Run an A/B test or Solo simulation to see hallucination analysis…
            </p>
          </div>
        ) : (
          <>
            {socialPressureEvents.map((e, i) => (
              <SocialPressureCard key={`sp-${i}`} event={e} />
            ))}
            {internalMathEvents.map((e, i) => (
              <InternalMathCard key={`im-${i}`} event={e} />
            ))}
            {toolComparisonEvents.map((e, i) => (
              <ToolComparisonCard key={`tc-${i}`} event={e} />
            ))}
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function _extractScore(text = '') {
  const m = text.match(/(\d+(?:\.\d+)?)\s*\/\s*100/)
  if (m) {
    const v = parseFloat(m[1])
    if (v >= 0 && v <= 100) return v
  }
  return null
}
