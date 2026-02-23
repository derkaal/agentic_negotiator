/**
 * MarketOverview — 3×3 MBMPMS Game-Theoretic Market Matrix (v2)
 *
 * Renders a live market view with:
 *   • 3×3 negotiation matrix (buyer-side + seller-side utility, Level-k strategy badge)
 *   • SellerBrain panel (live Level-k strategy per seller)
 *   • Profit Map table (per-deal audit: surplus, margin, Pareto flag, ContractValidator)
 *   • Welfare Split bars (buyer vs seller surplus visualisation)
 *   • Switch log with seller context
 *
 * Props:
 *   buyers           {Array}        buyer config objects
 *   sellers          {Array}        seller config objects
 *   pairMatrix       {Object}       "buyerId:sellerId" → pair snapshot
 *   closedDeals      {Array}        deal_closed event objects (full welfare payload)
 *   dealRate         {number|null}  0-1
 *   marketScore      {Object|null}  {global_score, buyer_score, seller_score}
 *   switchEvents     {Array}        market_switch events
 *   sellerStrategies {Object}       {sellerId: 'normal'|'match_market'|'hold_margin'}
 *   auditTrail       {Array}        per-deal Profit Map rows from market_end
 *   currentRound     {number}
 *   scenario         {string}
 */

// ── Strategy helpers ──────────────────────────────────────────────────────────

const STRATEGY_META = {
  hold_margin:  { label: '🔒 HOLD',  cls: 'bg-amber-900/60 text-amber-300 border-amber-700/60' },
  match_market: { label: '⚡ MATCH', cls: 'bg-blue-900/60  text-blue-300  border-blue-700/60'  },
  normal:       { label: '',          cls: ''                                                    },
}

function strategyBadge(strategy) {
  const m = STRATEGY_META[strategy] ?? STRATEGY_META.normal
  if (!m.label) return null
  return (
    <span className={`text-[8px] border px-1 rounded font-bold ${m.cls}`}>{m.label}</span>
  )
}

// ── Utility helpers ───────────────────────────────────────────────────────────

function utilityColor(u, priority) {
  if (priority === 'closed')  return 'text-emerald-300'
  if (priority === 'leading') return 'text-emerald-400'
  if (priority === 'low')     return 'text-red-400'
  if (u === null || u === undefined) return 'text-war-muted'
  if (u >= 65) return 'text-emerald-400'
  if (u >= 50) return 'text-amber-400'
  return 'text-orange-400'
}

function cellBg(priority) {
  switch (priority) {
    case 'leading': return 'bg-emerald-950/50 border-emerald-500/60 ring-1 ring-emerald-500/40'
    case 'closed':  return 'bg-emerald-950/30 border-emerald-800/50'
    case 'low':     return 'bg-red-950/30 border-red-800/40'
    default:        return 'bg-war-panel border-war-border'
  }
}

function UtilityBar({ value, priority, color }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value))
  const barColor = color ?? (
    priority === 'leading' || priority === 'closed' ? 'bg-emerald-500'
    : priority === 'low'                            ? 'bg-red-700'
    : pct >= 65                                     ? 'bg-emerald-500'
    : pct >= 50                                     ? 'bg-amber-500'
    : 'bg-orange-600'
  )
  return (
    <div className="h-1 bg-war-bg rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-700 ${barColor}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── PairCell — dual utility (buyer + seller) ──────────────────────────────────

function PairCell({ pair, sellerStrategy }) {
  if (!pair) return (
    <div className="border rounded-lg p-3 bg-war-panel border-war-border opacity-30 h-32" />
  )

  const { utility, seller_utility, buyer_offer, seller_ask, deal_price, priority, closed, deal_round } = pair
  const isLeading  = priority === 'leading'
  const isLow      = priority === 'low'
  const isClosed   = priority === 'closed' || closed
  const stratMeta  = STRATEGY_META[sellerStrategy ?? 'normal'] ?? STRATEGY_META.normal

  return (
    <div className={`border rounded-lg p-2 transition-all duration-500 ${cellBg(priority)}`}>
      {/* Badges row */}
      <div className="flex items-center justify-between mb-1 gap-0.5">
        {isLeading && (
          <span className="text-[8px] bg-emerald-900/80 text-emerald-300 border border-emerald-700/60 px-1 rounded font-bold">★ LEAD</span>
        )}
        {isClosed && (
          <span className="text-[8px] bg-emerald-900/60 text-emerald-400 border border-emerald-700/60 px-1 rounded font-bold">✓ DEAL</span>
        )}
        {isLow && !isClosed && (
          <span className="text-[8px] bg-red-950/80 text-red-400 border border-red-800/60 px-1 rounded font-bold">⇢ SWITCH</span>
        )}
        {!isLeading && !isClosed && !isLow && <span />}
        {stratMeta.label && (
          <span className={`text-[8px] border px-1 rounded font-bold ${stratMeta.cls}`}>{stratMeta.label}</span>
        )}
      </div>

      {/* Buyer utility score */}
      <div className={`text-lg font-mono font-black leading-none ${utilityColor(utility, priority)}`}>
        {utility !== null && utility !== undefined ? utility.toFixed(1) : '—'}
        <span className="text-[9px] font-normal text-war-muted ml-0.5">B</span>
      </div>
      <UtilityBar value={utility} priority={priority} />

      {/* Seller utility score */}
      {!isClosed && (
        <div className="mt-1">
          <div className="text-[11px] font-mono text-amber-300/80 leading-none">
            {seller_utility !== null && seller_utility !== undefined ? seller_utility.toFixed(1) : '—'}
            <span className="text-[9px] font-normal text-war-muted ml-0.5">S</span>
          </div>
          <UtilityBar value={seller_utility} priority="normal" color="bg-amber-600" />
        </div>
      )}

      {/* Prices */}
      <div className="mt-1.5 space-y-0.5 text-[10px] font-mono">
        {isClosed ? (
          <div className="text-emerald-300 font-bold">
            ⚑ ${deal_price?.toLocaleString()} (R{deal_round})
          </div>
        ) : (
          <>
            <div className="flex justify-between">
              <span className="text-blue-400/70">B:</span>
              <span className="text-blue-300">{buyer_offer ? `$${buyer_offer.toLocaleString()}` : '—'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-orange-400/70">S:</span>
              <span className="text-orange-300">{seller_ask ? `$${seller_ask.toLocaleString()}` : '—'}</span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// ── SellerBrain panel ─────────────────────────────────────────────────────────

function SellerBrainPanel({ sellers, sellerStrategies }) {
  if (!sellers || sellers.length === 0) return null
  return (
    <div className="space-y-2">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        Seller Brain — Level-k Strategy
      </div>
      <div className="grid grid-cols-3 gap-2">
        {sellers.map((s) => {
          const strat = sellerStrategies?.[s.id] ?? 'normal'
          const meta  = STRATEGY_META[strat] ?? STRATEGY_META.normal
          return (
            <div
              key={s.id}
              className={`rounded-lg border p-2 text-center transition-all duration-500 ${
                strat === 'hold_margin'  ? 'bg-amber-950/30 border-amber-700/40'
                : strat === 'match_market' ? 'bg-blue-950/30 border-blue-700/40'
                : 'bg-war-panel border-war-border'
              }`}
            >
              <div className="text-[10px] font-bold text-war-text uppercase truncate">{s.name}</div>
              <div className={`text-[10px] font-bold mt-0.5 ${
                strat === 'hold_margin'  ? 'text-amber-400'
                : strat === 'match_market' ? 'text-blue-400'
                : 'text-war-muted'
              }`}>
                {strat === 'hold_margin'  ? '🔒 Hold Margin'
                 : strat === 'match_market' ? '⚡ Match Market'
                 : '— Normal'}
              </div>
              <div className="text-[9px] text-war-muted mt-0.5">
                {strat === 'hold_margin'  ? '0.5× concede rate'
                 : strat === 'match_market' ? '1.5× concede rate'
                 : '1.0× concede rate'}
              </div>
              <div className="text-[9px] text-war-muted/60 mt-0.5">σ_j=${s.floor?.toLocaleString()}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Welfare Split bar ─────────────────────────────────────────────────────────

function WelfareSplitBar({ buyerSurplus, sellerSurplus, total }) {
  if (!total || total <= 0) return null
  const buyerPct  = Math.round((buyerSurplus  / total) * 100)
  const sellerPct = 100 - buyerPct

  return (
    <div className="space-y-0.5">
      <div className="h-2.5 rounded-full overflow-hidden flex">
        <div
          className="h-full bg-blue-600 transition-all duration-700"
          style={{ width: `${buyerPct}%` }}
          title={`Buyer surplus: $${buyerSurplus?.toLocaleString()}`}
        />
        <div
          className="h-full bg-orange-600 transition-all duration-700"
          style={{ width: `${sellerPct}%` }}
          title={`Seller surplus: $${sellerSurplus?.toLocaleString()}`}
        />
      </div>
      <div className="flex justify-between text-[9px] font-mono text-war-muted">
        <span className="text-blue-400">{buyerPct}% buyer</span>
        <span className="text-orange-400">{sellerPct}% seller</span>
      </div>
    </div>
  )
}

// ── Profit Map table ──────────────────────────────────────────────────────────

function ProfitMap({ deals }) {
  if (!deals || deals.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        📊 Profit Map — Seller Outcome Audit
      </div>
      <div className="space-y-2">
        {deals.map((d, i) => {
          const pareto    = d.pareto_optimal
          const violation = !d.contract_valid
          const effPen    = d.efficiency_penalty ?? 0
          const bname     = d.buyer_name?.split('—').pop()?.trim() ?? d.buyer_name
          const eff_label = effPen < 0 ? `${effPen.toFixed(0)}pts` : 'on time'

          return (
            <div
              key={i}
              className={`rounded-lg border p-3 transition-all duration-300 ${
                violation  ? 'border-red-600/70 bg-red-950/20'
                : pareto   ? 'border-yellow-500/60 bg-yellow-950/10 ring-1 ring-yellow-500/20'
                : 'border-war-border bg-war-panel'
              }`}
            >
              {/* Header row */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-bold text-war-text font-mono">
                    {bname} × {d.seller_name}
                  </span>
                  {pareto && (
                    <span className="text-[9px] bg-yellow-900/60 text-yellow-300 border border-yellow-700/60 px-1.5 py-0.5 rounded font-bold">
                      ★ PARETO OPTIMAL
                    </span>
                  )}
                  {violation && (
                    <span className="text-[9px] bg-red-900/60 text-red-300 border border-red-700/60 px-1.5 py-0.5 rounded font-bold">
                      ⚠ BAIT-SWITCH
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 text-[10px] font-mono">
                  <span className="text-war-muted">R{d.round}</span>
                  <span className={effPen < 0 ? 'text-orange-400' : 'text-emerald-400'}>
                    {effPen < 0 ? `⏱ eff ${eff_label}` : '✓ efficient'}
                  </span>
                </div>
              </div>

              {/* Deal price */}
              <div className="text-lg font-mono font-black text-emerald-300 mb-2">
                ${d.deal_price?.toLocaleString()}
              </div>

              {/* Two-column: Buyer side / Seller side */}
              <div className="grid grid-cols-2 gap-3 text-[10px] font-mono">
                {/* Buyer */}
                <div className="space-y-1">
                  <div className="text-[9px] text-blue-400/70 uppercase font-bold tracking-wide">Buyer</div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">Reservation</span>
                    <span className="text-blue-300">${d.buyer_reservation?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">Surplus saved</span>
                    <span className={d.buyer_surplus > 0 ? 'text-emerald-400 font-bold' : 'text-war-muted'}>
                      ${d.buyer_surplus?.toLocaleString() ?? 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">BuyerScore</span>
                    <span className={
                      d.buyer_score_adj > 50 ? 'text-emerald-400 font-bold' : 'text-amber-400'
                    }>
                      {d.buyer_score_adj?.toFixed(1)}/100
                    </span>
                  </div>
                </div>

                {/* Seller */}
                <div className="space-y-1">
                  <div className="text-[9px] text-orange-400/70 uppercase font-bold tracking-wide">
                    Seller — {d.seller_strategy ?? 'normal'}
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">Floor (σ_j)</span>
                    <span className="text-orange-300/70">${d.seller_floor?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">Profit</span>
                    <span className="text-orange-300 font-bold">${d.seller_profit?.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">Margin</span>
                    <span className="text-orange-300">{d.seller_margin_pct?.toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-war-muted">SellerScore</span>
                    <span className={
                      d.seller_score_adj > 50 ? 'text-orange-300 font-bold' : 'text-red-400'
                    }>
                      {d.seller_score_adj?.toFixed(1)}/100
                    </span>
                  </div>
                </div>
              </div>

              {/* Welfare split bar */}
              <div className="mt-2.5">
                <div className="text-[9px] text-war-muted mb-1">
                  Welfare split — total surplus ${d.total_surplus?.toLocaleString()}
                </div>
                <WelfareSplitBar
                  buyerSurplus={d.buyer_surplus}
                  sellerSurplus={d.seller_surplus}
                  total={d.total_surplus}
                />
              </div>

              {/* GlobalScore + contract status */}
              <div className="mt-2 flex items-center justify-between text-[10px] font-mono">
                <div>
                  <span className="text-war-muted">GlobalScore: </span>
                  <span className={d.global_score >= 70 ? 'text-emerald-400 font-bold' : d.global_score >= 50 ? 'text-amber-400' : 'text-red-400'}>
                    {d.global_score?.toFixed(2)}/100
                  </span>
                </div>
                <div className={d.contract_valid ? 'text-emerald-500' : 'text-red-400'}>
                  {d.contract_valid ? '✓ ContractValidator: CLEAN' : '⚠ ContractValidator: VIOLATION'}
                </div>
              </div>

              {/* Violation details */}
              {violation && d.violations?.length > 0 && (
                <div className="mt-1.5 space-y-0.5">
                  {d.violations.map((v, vi) => (
                    <div key={vi} className="text-[9px] text-red-300 bg-red-950/30 rounded px-2 py-1 font-mono">
                      {v.description}  (penalty: {v.score_penalty}pts)
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Welfare totals summary ────────────────────────────────────────────────────

function WelfareSummary({ marketEnd }) {
  if (!marketEnd || !marketEnd.total_market_surplus) return null
  const { total_buyer_surplus, total_seller_surplus, total_market_surplus,
          avg_welfare_split_pct, pareto_deals, contract_violations } = marketEnd

  return (
    <div className="rounded-lg border border-war-border bg-war-panel p-3 space-y-2">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        Total Welfare (S_g) — Market Aggregate
      </div>
      <div className="grid grid-cols-3 gap-2 text-center text-[10px] font-mono">
        <div>
          <div className="text-war-muted">Total Surplus</div>
          <div className="text-white font-bold text-sm">${total_market_surplus?.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-blue-400/70">Buyer Captured</div>
          <div className="text-blue-300 font-bold text-sm">${total_buyer_surplus?.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-orange-400/70">Seller Captured</div>
          <div className="text-orange-300 font-bold text-sm">${total_seller_surplus?.toLocaleString()}</div>
        </div>
      </div>
      <WelfareSplitBar
        buyerSurplus={total_buyer_surplus}
        sellerSurplus={total_seller_surplus}
        total={total_market_surplus}
      />
      <div className="flex items-center justify-between text-[10px] font-mono pt-1 border-t border-war-border">
        <span>
          <span className="text-war-muted">Avg welfare split: </span>
          <span className="text-orange-300 font-bold">{avg_welfare_split_pct}% to sellers</span>
        </span>
        <span>
          <span className="text-yellow-400 font-bold">{pareto_deals}/3</span>
          <span className="text-war-muted"> Pareto-optimal</span>
        </span>
        <span>
          <span className={contract_violations?.length > 0 ? 'text-red-400' : 'text-emerald-500'}>
            {contract_violations?.length > 0
              ? `⚠ ${contract_violations.length} violation(s)`
              : '✓ No violations'}
          </span>
        </span>
      </div>
    </div>
  )
}

// ── Deal Rate bar ─────────────────────────────────────────────────────────────

function DealRateBar({ rate, closed, possible }) {
  const pct = Math.round((rate ?? 0) * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-war-muted uppercase tracking-wide font-bold">Deal Rate</span>
        <span className="font-mono font-bold text-emerald-400">{closed}/{possible} — {pct}%</span>
      </div>
      <div className="h-2 bg-war-panel rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 rounded-full transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ── Market Score summary (adjusted scores) ────────────────────────────────────

function MarketScoreSummary({ score }) {
  if (!score) return null
  const { global_score, buyer_score, seller_score } = score
  const v = (n) => (n !== null && n !== undefined ? n.toFixed(2) : '—')
  const c = (n) => n >= 70 ? 'text-emerald-400' : n >= 50 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="grid grid-cols-3 gap-2 text-center">
      {[
        { label: 'GlobalScore', v: global_score, sub: 'D=30 W=55 E=15' },
        { label: 'BuyerScore',  v: buyer_score,  sub: 'adj for efficiency' },
        { label: 'SellerScore', v: seller_score, sub: 'adj + contract' },
      ].map(({ label, v: val, sub }) => (
        <div key={label} className="bg-war-panel rounded-lg p-2 border border-war-border">
          <div className="text-[10px] text-war-muted uppercase tracking-wide">{label}</div>
          <div className={`text-lg font-mono font-black ${c(val)}`}>{v(val)}</div>
          <div className="text-[9px] text-war-muted/60">{sub}</div>
        </div>
      ))}
    </div>
  )
}

// ── Switch log (with seller context) ─────────────────────────────────────────

function SwitchLog({ switches }) {
  if (!switches || switches.length === 0) return null
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        Market Switches ({switches.length})
      </div>
      <div className="space-y-1 max-h-28 overflow-y-auto">
        {switches.map((sw, i) => (
          <div
            key={i}
            className="bg-red-950/30 border border-red-800/40 rounded px-2 py-1 text-[10px] text-red-300 font-mono"
          >
            R{sw.round} ⇢ {sw.buyer_id} away from {sw.seller_id}
            {' '}(u={sw.utility?.toFixed(1)}, S_s={sw.seller_score_at_switch?.toFixed(1)})
            {sw.seller_strategy_before && sw.seller_strategy_before !== 'normal' && (
              <span className="text-amber-400 ml-1">→ was {sw.seller_strategy_before}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function MarketOverview({
  buyers            = [],
  sellers           = [],
  pairMatrix        = {},
  closedDeals       = [],
  dealRate          = null,
  marketScore       = null,
  switchEvents      = [],
  sellerStrategies  = {},
  auditTrail        = [],
  currentRound      = 0,
  scenario          = 'used_car',
  marketEnd         = null,
}) {
  const totalPairs = buyers.length * sellers.length

  // Determine leading pair
  let leadKey = null, leadUtil = -1
  Object.entries(pairMatrix).forEach(([k, p]) => {
    if (!p.closed && (p.utility ?? -1) > leadUtil) {
      leadUtil = p.utility; leadKey = k
    }
  })

  const annotated = Object.fromEntries(
    Object.entries(pairMatrix).map(([k, p]) => [
      k,
      { ...p, priority: p.closed ? 'closed' : k === leadKey ? 'leading' : p.priority },
    ])
  )

  // Use auditTrail if available (post-market), else live closedDeals
  const profitMapData = auditTrail.length > 0 ? auditTrail : closedDeals
  const scenarioLabel = scenario === 'used_car' ? '🚗 Used Car Market — Honda Civic 2021' :
                        scenario === 'sneaker' ? '👟 Sneaker Market — Limited Edition Sneakers' :
                        scenario

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-emerald-400">
            🏪 Market Overview — Game-Theoretic MBMPMS v2
          </div>
          <div className="text-[10px] text-war-muted mt-0.5">{scenarioLabel}</div>
        </div>
        <div className="flex items-center gap-2">
          {currentRound > 0 && (
            <span className="text-[10px] text-war-muted font-mono">Round {currentRound}</span>
          )}
          <span className="text-[10px] bg-war-panel border border-war-border text-war-muted px-2 py-0.5 rounded font-mono">
            {totalPairs} pairs
          </span>
          {closedDeals.length > 0 && (
            <span className="text-[10px] bg-emerald-900/60 border border-emerald-700/60 text-emerald-300 px-2 py-0.5 rounded font-mono">
              {closedDeals.length} closed
            </span>
          )}
        </div>
      </div>

      {/* Deal Rate */}
      {(dealRate !== null || closedDeals.length > 0) && (
        <DealRateBar
          rate={dealRate ?? closedDeals.length / 3}
          closed={closedDeals.length}
          possible={Math.min(buyers.length, sellers.length)}
        />
      )}

      {/* SellerBrain level-k strategy panel */}
      {sellers.length > 0 && (
        <SellerBrainPanel sellers={sellers} sellerStrategies={sellerStrategies} />
      )}

      {/* 3×3 Grid — dual utility cells (buyer + seller) */}
      {buyers.length > 0 && sellers.length > 0 && (
        <div className="space-y-2">
          {/* Column headers (sellers) */}
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `76px repeat(${sellers.length}, 1fr)` }}
          >
            <div />
            {sellers.map((s) => (
              <div key={s.id} className="text-center">
                <div className="text-[10px] font-bold text-war-accent uppercase truncate">{s.name}</div>
                <div className="text-[9px] text-war-muted">{s.speed_days}d · {s.warranty_mo}mo</div>
                <div className="text-[9px] text-orange-400/70 font-mono">σ=${(s.floor/1000).toFixed(1)}k</div>
              </div>
            ))}
          </div>

          {/* Rows (buyers) */}
          {buyers.map((b) => (
            <div
              key={b.id}
              className="grid gap-2 items-start"
              style={{ gridTemplateColumns: `76px repeat(${sellers.length}, 1fr)` }}
            >
              <div className="text-right pr-2 pt-1">
                <div className="text-[10px] font-bold text-war-text uppercase leading-tight">
                  {b.name?.split('—').pop()?.trim().split(' ')[0] ?? b.id}
                </div>
                <div className="text-[9px] text-war-muted capitalize">{b.id}</div>
                <div className="text-[9px] text-blue-400 font-mono">≤${(b.max_price/1000).toFixed(0)}k</div>
              </div>
              {sellers.map((s) => {
                const key  = `${b.id}:${s.id}`
                const pair = annotated[key] ?? null
                return (
                  <PairCell
                    key={key}
                    pair={pair}
                    sellerStrategy={pair?.seller_strategy ?? sellerStrategies[s.id] ?? 'normal'}
                  />
                )
              })}
            </div>
          ))}
        </div>
      )}

      {/* Grid legend */}
      <div className="flex items-center gap-3 text-[9px] text-war-muted font-mono">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" /> Buyer util (B)</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-600 inline-block" /> Seller util (S)</span>
        <span className="flex items-center gap-1"><span className="text-amber-300">🔒 HOLD</span> = 0.5× concede</span>
        <span className="flex items-center gap-1"><span className="text-blue-300">⚡ MATCH</span> = 1.5× concede</span>
      </div>

      {/* Market Score (adjusted) */}
      <MarketScoreSummary score={marketScore} />

      {/* Welfare aggregate (post-market) */}
      {marketEnd && <WelfareSummary marketEnd={marketEnd} />}

      {/* Profit Map — per-deal audit */}
      {profitMapData.length > 0 && (
        <ProfitMap deals={profitMapData} />
      )}

      {/* Switch log */}
      <SwitchLog switches={switchEvents} />

      {/* Algorithm footnote */}
      <div className="text-[9px] text-war-muted/60 border-t border-war-border pt-2 leading-relaxed">
        MBMPMS v2 · SellerBrain Level-k · ContractValidator (Bait-and-Switch) · Welfare S_g peaks at 50/50 split · Efficiency penalty −2pts/round &gt;5 · Pareto = both scores &gt;50
      </div>
    </div>
  )
}
