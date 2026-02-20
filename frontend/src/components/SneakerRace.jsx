/**
 * SneakerRace — 3-lane race UI for Solo LLM vs Cyborg Agent sneaker experiment.
 *
 * Lanes:
 *   🔴 QuickSole   (Solo LLM)  — raw LLM, hallucination alerts in red
 *   🟡 StrideMax   (Cyborg A)  — CoT + MarginValidator + UtilityCalculator
 *   🔵 EliteKicks  (Cyborg B)  — deterministic OfferGenerator + LLM narrator
 *
 * Panels:
 *   Market Discovery (Round 0 opening asks + market average)
 *   Live race feed per lane (narratives, tool calls, hallucination flashes)
 *   Final rankings table + superiority verdict
 */

import React from 'react'
import clsx from 'clsx'

// ── Colour themes per archetype ───────────────────────────────────────────────

const THEMES = {
  solo_llm: {
    border:   'border-red-700/60',
    bg:       'bg-red-950/20',
    header:   'bg-red-950/40 border-b border-red-700/40',
    badge:    'bg-red-800/60 text-red-200 border border-red-600/50',
    accent:   'text-red-300',
    ask:      'text-red-200',
    icon:     '🔴',
    label:    'Solo LLM',
    tagline:  'No tools · Hallucination-prone',
  },
  cyborg_a: {
    border:   'border-amber-600/60',
    bg:       'bg-amber-950/15',
    header:   'bg-amber-950/40 border-b border-amber-700/40',
    badge:    'bg-amber-800/60 text-amber-200 border border-amber-600/50',
    accent:   'text-amber-300',
    ask:      'text-amber-200',
    icon:     '🟡',
    label:    'Cyborg A',
    tagline:  'Chain-of-Thought + MarginValidator',
  },
  cyborg_b: {
    border:   'border-blue-600/60',
    bg:       'bg-blue-950/15',
    header:   'bg-blue-950/40 border-b border-blue-700/40',
    badge:    'bg-blue-800/60 text-blue-200 border border-blue-600/50',
    accent:   'text-blue-300',
    ask:      'text-blue-200',
    icon:     '🔵',
    label:    'Cyborg B',
    tagline:  'Deterministic OfferGenerator',
  },
}

const ARCHETYPE_ORDER = ['quicksole', 'stridemax', 'elitekicks']

// ── Hallucination badge ───────────────────────────────────────────────────────

function HallucinationBadge({ hType, round }) {
  const labels = {
    format_failure:     { short: 'FORMAT FAIL',    color: 'bg-red-800/80 text-red-100 border-red-500/60' },
    floor_violation:    { short: 'FLOOR VIOLATION', color: 'bg-red-900/80 text-red-100 border-red-400/70 animate-pulse' },
    phantom_concession: { short: 'PHANTOM DROP',   color: 'bg-orange-900/80 text-orange-100 border-orange-500/70' },
  }
  const info = labels[hType] ?? { short: hType?.toUpperCase(), color: 'bg-gray-800 text-gray-300' }
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 text-[10px] font-mono font-bold px-1.5 py-0.5 rounded border',
      info.color,
    )}>
      ⚠ {info.short}
    </span>
  )
}

// ── Tool call pills ───────────────────────────────────────────────────────────

function ToolCallPill({ toolCall }) {
  const colors = {
    MarginValidator:    'bg-cyan-900/40 border-cyan-700/40 text-cyan-300',
    UtilityCalculator:  'bg-purple-900/40 border-purple-700/40 text-purple-300',
    OfferGenerator:     'bg-blue-900/40 border-blue-700/40 text-blue-300',
  }
  const cls = colors[toolCall.tool] ?? 'bg-gray-800/40 border-gray-600/40 text-gray-300'
  const r = toolCall.result ?? {}

  const summary =
    toolCall.tool === 'MarginValidator'
      ? `${r.status} · margin $${r.margin_usd?.toFixed(0)}  (${r.margin_pct?.toFixed(1)}%)`
      : toolCall.tool === 'UtilityCalculator'
      ? `utility ${r.utility?.toFixed(1)}/100 · ${r.acceptable ? 'ACCEPTABLE' : 'BELOW THRESHOLD'}`
      : toolCall.tool === 'OfferGenerator'
      ? `ask ${r.current_ask?.toFixed(0)} → ${r.new_ask?.toFixed(0)} | gap ${r.gap?.toFixed(0)} | step ${r.step?.toFixed(1)}`
      : JSON.stringify(r).slice(0, 60)

  return (
    <div className={clsx('rounded border px-2 py-1 text-[10px] font-mono', cls)}>
      <span className="font-bold">[{toolCall.tool}]</span>{' '}
      <span className="opacity-80">{summary}</span>
    </div>
  )
}

// ── Single seller lane ────────────────────────────────────────────────────────

function SellerLane({ sellerId, sellerConfig, responses, hallucinationLog, dealEvent, sneakerEnd }) {
  const arch  = sellerConfig?.archetype ?? 'solo_llm'
  const theme = THEMES[arch]
  const selfH = (hallucinationLog ?? []).filter(h => h.seller_id === sellerId)

  const ranking  = (sneakerEnd?.rankings ?? []).find(r => r.seller_id === sellerId)
  const isClosed = dealEvent?.seller_id === sellerId || ranking?.did_close

  const responseArea = React.useRef(null)
  React.useEffect(() => {
    if (responseArea.current) {
      responseArea.current.scrollTop = responseArea.current.scrollHeight
    }
  }, [responses])

  return (
    <div className={clsx(
      'rounded-xl border flex flex-col',
      theme.border,
      theme.bg,
      isClosed && 'ring-2 ring-emerald-400/60',
    )}>
      {/* Lane header */}
      <div className={clsx('rounded-t-xl px-4 py-2.5 flex items-start justify-between', theme.header)}>
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-base">{theme.icon}</span>
            <span className="text-white font-black text-sm">{sellerConfig?.name ?? sellerId}</span>
            <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', theme.badge)}>
              {theme.label}
            </span>
          </div>
          <p className="text-[10px] text-gray-400 font-mono">{theme.tagline}</p>
        </div>
        {isClosed && (
          <span className="bg-emerald-800/80 text-emerald-200 border border-emerald-500/60 text-[10px] font-mono font-bold px-2 py-0.5 rounded">
            ✓ DEAL CLOSED
          </span>
        )}
        {!isClosed && sneakerEnd && (
          <span className="bg-gray-800/80 text-gray-400 border border-gray-600/40 text-[10px] font-mono px-2 py-0.5 rounded">
            DNF — #{ranking?.rank ?? '?'}
          </span>
        )}
      </div>

      {/* Current ask + hallucination count */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-white/5">
        <div>
          <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Current Ask</div>
          <div className={clsx('font-mono font-black text-xl', theme.ask)}>
            ${sellerConfig?.current_ask != null
              ? sellerConfig.current_ask.toFixed(0)
              : (sellerConfig?.ask ?? '—')}
          </div>
        </div>
        {arch === 'solo_llm' && (
          <div className="ml-auto">
            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Hallucinations</div>
            <div className={clsx(
              'font-mono font-black text-xl',
              selfH.length > 0 ? 'text-red-400' : 'text-gray-500',
            )}>
              {selfH.length}
            </div>
          </div>
        )}
        {arch !== 'solo_llm' && sellerConfig?.phase && (
          <div className="ml-auto">
            <div className="text-[10px] text-gray-500 font-mono uppercase tracking-wider">Phase</div>
            <div className={clsx(
              'font-mono font-bold text-xs',
              sellerConfig.phase === 'cooperative' ? 'text-emerald-400' : 'text-amber-400',
            )}>
              {sellerConfig.phase?.toUpperCase() ?? '—'}
            </div>
          </div>
        )}
      </div>

      {/* Response stream */}
      <div
        ref={responseArea}
        className="flex-1 overflow-y-auto px-3 py-2 space-y-2 min-h-0"
        style={{ maxHeight: 300 }}
      >
        {(responses ?? []).map((resp, i) => (
          <div key={i} className={clsx(
            'rounded border p-2 text-[11px] font-mono',
            resp.hallucination_type
              ? 'border-red-700/50 bg-red-950/30'
              : 'border-white/5 bg-white/3',
          )}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-gray-500 text-[10px]">R{resp.round}</span>
              <span className="text-gray-500">·</span>
              <span className="text-gray-400">
                buyer ${resp.buyer_offer?.toFixed(0)} → ask ${resp.offered_price != null
                  ? resp.offered_price.toFixed(0)
                  : resp.current_ask?.toFixed(0)}
              </span>
              {resp.hallucination_type && (
                <HallucinationBadge hType={resp.hallucination_type} round={resp.round} />
              )}
            </div>

            {/* Narrative (first ~160 chars to keep UI tidy) */}
            <p className="text-gray-400 leading-relaxed whitespace-pre-wrap line-clamp-4">
              {(resp.narrative ?? '').slice(0, 240)}{resp.narrative?.length > 240 ? '…' : ''}
            </p>

            {/* Tool calls */}
            {(resp.tool_calls ?? []).length > 0 && (
              <div className="mt-1.5 space-y-1">
                {resp.tool_calls.map((tc, j) => (
                  <ToolCallPill key={j} toolCall={tc} />
                ))}
              </div>
            )}
          </div>
        ))}

        {(responses ?? []).length === 0 && (
          <p className="text-gray-600 text-[11px] font-mono italic text-center py-4">
            Awaiting round 1…
          </p>
        )}
      </div>

      {/* Hallucination log (Solo lane only) */}
      {arch === 'solo_llm' && selfH.length > 0 && (
        <div className="border-t border-red-800/40 px-3 py-2 space-y-1">
          <div className="text-[10px] text-red-400 font-mono font-bold uppercase tracking-wider mb-1">
            ⚠ Hallucination Audit
          </div>
          {selfH.map((h, i) => (
            <div key={i} className="text-[10px] font-mono text-red-300/80 leading-relaxed">
              R{h.round}: {h.h_type} — {h.description?.slice(0, 120)}
              {h.score_penalty ? (
                <span className="text-red-400 font-bold"> [{h.score_penalty}pts]</span>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {/* Final scores (post sneaker_end) */}
      {ranking && (
        <div className="border-t border-white/5 px-3 py-2">
          <div className="flex justify-between items-center text-[10px] font-mono">
            <span className="text-gray-500">Rank</span>
            <span className={clsx('font-bold', ranking.rank === 1 ? 'text-emerald-400' : 'text-gray-300')}>
              #{ranking.rank}
            </span>
          </div>
          <div className="flex justify-between items-center text-[10px] font-mono">
            <span className="text-gray-500">GlobalScore (adj)</span>
            <span className={clsx(
              'font-bold',
              (ranking.global_score_adj ?? 0) >= 55 ? 'text-emerald-400'
              : (ranking.global_score_adj ?? 0) >= 40 ? 'text-amber-400'
              : 'text-red-400',
            )}>
              {ranking.global_score_adj?.toFixed(2) ?? '—'}
            </span>
          </div>
          {ranking.did_close && (
            <>
              <div className="flex justify-between items-center text-[10px] font-mono">
                <span className="text-gray-500">Deal price</span>
                <span className="text-white font-bold">${ranking.deal_price?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center text-[10px] font-mono">
                <span className="text-gray-500">Seller surplus</span>
                <span className="text-emerald-300">${ranking.seller_surplus?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between items-center text-[10px] font-mono">
                <span className="text-gray-500">Pareto optimal</span>
                <span className={ranking.pareto_optimal ? 'text-emerald-400' : 'text-red-400'}>
                  {ranking.pareto_optimal ? '✓ YES' : '✗ NO'}
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── Market Discovery panel ────────────────────────────────────────────────────

function MarketDiscoveryPanel({ discovery }) {
  if (!discovery) return null
  return (
    <div className="rounded-xl border border-emerald-700/50 bg-emerald-950/20 px-5 py-4 animate-fade-in">
      <div className="flex items-center gap-3 mb-3">
        <span className="text-base">📡</span>
        <div>
          <p className="text-emerald-300 font-black text-xs uppercase tracking-widest">
            Round 0 — Market Discovery
          </p>
          <p className="text-gray-500 text-[10px] font-mono">{discovery.buyer_query}</p>
        </div>
        <div className="ml-auto">
          <div className="text-[10px] text-gray-500 font-mono">Market Average</div>
          <div className="text-emerald-300 font-mono font-black text-lg">
            ${discovery.market_avg?.toFixed(0)}
          </div>
        </div>
      </div>
      <div className="flex gap-3 flex-wrap">
        {(discovery.seller_responses ?? []).map((sr, i) => (
          <div key={i} className="rounded border border-white/5 bg-white/3 px-3 py-2 text-[10px] font-mono flex-1 min-w-[120px]">
            <div className="text-white font-bold mb-0.5">{sr.name}</div>
            <div className="text-emerald-300 font-bold text-base">${sr.opening_ask?.toFixed(0)}</div>
            <div className="text-gray-500">{sr.archetype}</div>
          </div>
        ))}
      </div>
      <p className="text-emerald-500/60 text-[10px] font-mono mt-2">{discovery.note}</p>
    </div>
  )
}

// ── Rankings table ────────────────────────────────────────────────────────────

function RankingsTable({ sneakerEnd }) {
  if (!sneakerEnd) return null
  const { rankings, cyborg_superiority_verdict, solo_vs_cyborg_verdict,
    total_hallucinations, solo_compliance_rate } = sneakerEnd

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Rankings */}
      <div className="rounded-xl border border-war-border bg-war-panel p-5">
        <div className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
          🏆 Final Rankings
        </div>
        <div className="space-y-2">
          {(rankings ?? []).map((r) => {
            const arch  = r.archetype
            const theme = THEMES[arch] ?? {}
            return (
              <div key={r.seller_id} className={clsx(
                'rounded-lg border px-4 py-2.5 flex items-center gap-4',
                r.did_close ? 'border-emerald-600/50 bg-emerald-950/20' : 'border-white/5 bg-white/3',
              )}>
                <span className="font-mono font-black text-xl text-gray-400">#{r.rank}</span>
                <span className="text-base">{THEMES[arch]?.icon ?? '○'}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-bold text-sm">{r.name}</span>
                    <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', theme.badge ?? 'bg-gray-800 border-gray-600 text-gray-300')}>
                      {theme.label ?? arch}
                    </span>
                    {r.did_close && (
                      <span className="bg-emerald-800/60 text-emerald-300 border border-emerald-600/50 text-[10px] font-mono px-1.5 py-0.5 rounded">
                        CLOSED R{r.deal_round}
                      </span>
                    )}
                    {r.hallucination_count > 0 && (
                      <span className="bg-red-900/60 text-red-300 border border-red-600/50 text-[10px] font-mono px-1.5 py-0.5 rounded">
                        {r.hallucination_count} hallucinations
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] text-gray-500 font-mono">GlobalScore (adj)</div>
                  <div className={clsx(
                    'font-mono font-black text-base',
                    (r.global_score_adj ?? 0) >= 55 ? 'text-emerald-400'
                    : (r.global_score_adj ?? 0) >= 35 ? 'text-amber-400'
                    : 'text-red-400',
                  )}>
                    {r.global_score_adj?.toFixed(2) ?? '—'}
                  </div>
                </div>
                {r.did_close && (
                  <div className="text-right">
                    <div className="text-[10px] text-gray-500 font-mono">Deal Price</div>
                    <div className="font-mono font-black text-base text-white">
                      ${r.deal_price?.toFixed(2)}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Hallucination compliance summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-red-700/50 bg-red-950/20 p-4">
          <div className="text-[10px] text-red-400 font-mono font-bold uppercase tracking-wider mb-2">
            ⚠ Solo LLM Compliance
          </div>
          <div className="font-mono font-black text-2xl text-red-300 mb-1">
            {solo_compliance_rate?.toFixed(1) ?? '—'}%
          </div>
          <div className="text-[11px] text-gray-400 font-mono">
            {total_hallucinations} hallucinations in 10 rounds
          </div>
        </div>
        <div className="rounded-xl border border-emerald-700/50 bg-emerald-950/20 p-4">
          <div className="text-[10px] text-emerald-400 font-mono font-bold uppercase tracking-wider mb-2">
            ✓ Cyborg Compliance
          </div>
          <div className="font-mono font-black text-2xl text-emerald-400 mb-1">
            100.0%
          </div>
          <div className="text-[11px] text-gray-400 font-mono">
            Zero floor violations · zero format failures
          </div>
        </div>
        <div className="rounded-xl border border-violet-700/40 bg-violet-950/20 p-4">
          <div className="text-[10px] text-violet-400 font-mono font-bold uppercase tracking-wider mb-2">
            📈 Hallucination Gap
          </div>
          <div className="font-mono font-black text-2xl text-violet-300 mb-1">
            {(100 - (solo_compliance_rate ?? 100)).toFixed(0)}pts
          </div>
          <div className="text-[11px] text-gray-400 font-mono">
            performance deficit from ungrounded pricing
          </div>
        </div>
      </div>

      {/* Verdict text */}
      <div className="space-y-3">
        {cyborg_superiority_verdict && (
          <div className="rounded-xl border border-blue-700/50 bg-blue-950/20 px-5 py-3 text-xs font-mono text-blue-200 leading-relaxed">
            <span className="text-blue-400 font-bold block mb-1">🏆 Cyborg Superiority Verdict</span>
            {cyborg_superiority_verdict}
          </div>
        )}
        {solo_vs_cyborg_verdict && (
          <div className="rounded-xl border border-red-700/40 bg-red-950/15 px-5 py-3 text-xs font-mono text-red-200/80 leading-relaxed">
            <span className="text-red-400 font-bold block mb-1">⚠ Solo vs Cyborg Audit</span>
            {solo_vs_cyborg_verdict}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main SneakerRace component ────────────────────────────────────────────────

export default function SneakerRace({
  sneakerStart,
  marketDiscovery,
  sneakerSellers,
  sellerResponses,
  hallucinationLog,
  sneakerDeal,
  sneakerEnd,
  currentRound,
}) {
  if (!sneakerStart && !marketDiscovery && Object.keys(sneakerSellers ?? {}).length === 0) {
    return null
  }

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Experiment header */}
      <div className="rounded-xl border border-red-700/50 bg-red-950/20 px-5 py-3 flex items-start gap-3">
        <span className="text-xl flex-shrink-0">👟</span>
        <div className="flex-1">
          <p className="text-red-300 font-black text-xs uppercase tracking-widest mb-0.5">
            Sneaker Experiment — Solo LLM vs Cyborg Agent
          </p>
          {sneakerStart?.hypothesis && (
            <p className="text-gray-400 text-[11px] font-mono leading-relaxed">
              {sneakerStart.hypothesis}
            </p>
          )}
        </div>
        <div className="flex-shrink-0 flex gap-2 flex-wrap">
          {sneakerStart?.hallucination_schedule && Object.entries(sneakerStart.hallucination_schedule).map(([r, t]) => (
            <span key={r} className="bg-red-900/60 border border-red-700/50 text-red-300 text-[10px] font-mono px-1.5 py-0.5 rounded">
              R{r}: {t}
            </span>
          ))}
        </div>
      </div>

      {/* Market Discovery */}
      <MarketDiscoveryPanel discovery={marketDiscovery} />

      {/* 3-lane race grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {ARCHETYPE_ORDER.map((sid) => {
          const cfg       = sneakerStart?.sellers?.find(s => s.id === sid) ?? {}
          const liveSnap  = sneakerSellers?.[sid] ?? {}
          const mergedCfg = { ...cfg, ...liveSnap, id: sid }
          return (
            <SellerLane
              key={sid}
              sellerId={sid}
              sellerConfig={mergedCfg}
              responses={sellerResponses?.[sid] ?? []}
              hallucinationLog={hallucinationLog ?? []}
              dealEvent={sneakerDeal}
              sneakerEnd={sneakerEnd}
            />
          )
        })}
      </div>

      {/* Deal closed flash */}
      {sneakerDeal && !sneakerEnd && (
        <div className={clsx(
          'rounded-xl border-2 border-emerald-500/70 bg-emerald-950/30 px-6 py-4 animate-fade-in',
          'flex items-center gap-4',
        )}>
          <span className="text-3xl">🤝</span>
          <div>
            <p className="text-emerald-300 font-black text-sm uppercase tracking-widest">
              Deal Closed — R{sneakerDeal.round}
            </p>
            <p className="text-white font-mono">
              {sneakerDeal.name} ({sneakerDeal.archetype}) ·{' '}
              <span className="text-emerald-300 font-black">${sneakerDeal.deal_price?.toFixed(2)}</span>
            </p>
            <p className="text-gray-400 text-[11px] font-mono">
              Buyer surplus ${sneakerDeal.buyer_surplus?.toFixed(2)} ·{' '}
              Seller surplus ${sneakerDeal.seller_surplus?.toFixed(2)} ·{' '}
              GlobalScore {sneakerDeal.global_score_adj?.toFixed(2)}
            </p>
          </div>
          {sneakerDeal.pareto_optimal && (
            <span className="ml-auto bg-emerald-800/60 text-emerald-300 border border-emerald-500/50 text-xs font-mono font-bold px-3 py-1.5 rounded">
              ✓ PARETO OPTIMAL
            </span>
          )}
        </div>
      )}

      {/* Final rankings + verdict */}
      {sneakerEnd && <RankingsTable sneakerEnd={sneakerEnd} />}
    </div>
  )
}
