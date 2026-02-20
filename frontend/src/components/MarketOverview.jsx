/**
 * MarketOverview — 3×3 MBMPMS Market Matrix
 *
 * Renders a live 3-row (buyers) × 3-col (sellers) grid showing utility scores
 * for all 9 buyer-seller pairs.  The leading deal (highest open utility) is
 * highlighted in emerald green.  Closed deals show their final price.
 *
 * Props:
 *   buyers          {Array}       list of buyer config objects
 *   sellers         {Array}       list of seller config objects
 *   pairMatrix      {Object}      keyed "buyerId:sellerId" → pair state snapshot
 *   closedDeals     {Array}       deal_closed event objects
 *   dealRate        {number|null} 0-1
 *   marketScore     {Object|null} {global_score, buyer_score, seller_score}
 *   switches        {number}      total market_switch count
 *   currentRound    {number}
 *   scenario        {string}
 */

// ── Helpers ───────────────────────────────────────────────────────────────────

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

function UtilityBar({ value, priority }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value))
  const barColor =
    priority === 'leading' || priority === 'closed' ? 'bg-emerald-500'
    : priority === 'low'                            ? 'bg-red-700'
    : pct >= 65                                     ? 'bg-emerald-500'
    : pct >= 50                                     ? 'bg-amber-500'
    : 'bg-orange-600'

  return (
    <div className="h-1.5 bg-war-bg rounded-full overflow-hidden mt-1">
      <div
        className={`h-full rounded-full transition-all duration-700 ${barColor}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ── Single pair cell ──────────────────────────────────────────────────────────

function PairCell({ pair, buyerName, sellerName }) {
  if (!pair) {
    return (
      <div className="border rounded-lg p-3 bg-war-panel border-war-border opacity-30 h-28" />
    )
  }

  const { utility, buyer_offer, seller_ask, deal_price, priority, closed, deal_round } = pair
  const isLeading = priority === 'leading'
  const isLow     = priority === 'low'
  const isClosed  = priority === 'closed' || closed

  return (
    <div className={`border rounded-lg p-2.5 transition-all duration-500 ${cellBg(priority)}`}>
      {/* Pair badge */}
      <div className="flex items-center justify-between mb-1">
        <span className="text-[9px] text-war-muted font-mono uppercase truncate">
          {buyerName?.split(' ')[0]} / {sellerName}
        </span>
        {isLeading && (
          <span className="text-[8px] bg-emerald-900/80 text-emerald-300 border border-emerald-700/60 px-1 rounded font-bold">
            ★ LEAD
          </span>
        )}
        {isClosed && (
          <span className="text-[8px] bg-emerald-900/60 text-emerald-400 border border-emerald-700/60 px-1 rounded font-bold">
            ✓ DEAL
          </span>
        )}
        {isLow && !isClosed && (
          <span className="text-[8px] bg-red-950/80 text-red-400 border border-red-800/60 px-1 rounded font-bold">
            ⇢ SWITCH
          </span>
        )}
      </div>

      {/* Utility score */}
      <div className={`text-xl font-mono font-black leading-none ${utilityColor(utility, priority)}`}>
        {utility !== null && utility !== undefined ? utility.toFixed(1) : '—'}
        <span className="text-[10px] font-normal text-war-muted ml-0.5">/100</span>
      </div>

      <UtilityBar value={utility} priority={priority} />

      {/* Prices */}
      <div className="mt-2 space-y-0.5 text-[10px] font-mono">
        {isClosed ? (
          <div className="text-emerald-300 font-bold">
            ⚑ ${deal_price?.toLocaleString()} (R{deal_round})
          </div>
        ) : (
          <>
            <div className="flex justify-between">
              <span className="text-blue-400/70">B:</span>
              <span className="text-blue-300">
                {buyer_offer ? `$${buyer_offer.toLocaleString()}` : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-orange-400/70">S:</span>
              <span className="text-orange-300">
                {seller_ask ? `$${seller_ask.toLocaleString()}` : '—'}
              </span>
            </div>
          </>
        )}
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
        <span className="font-mono font-bold text-emerald-400">
          {closed}/{possible} — {pct}%
        </span>
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

// ── Market Score summary ──────────────────────────────────────────────────────

function MarketScoreSummary({ score }) {
  if (!score) return null
  const { global_score, buyer_score, seller_score } = score

  const v = (n) => (n !== null && n !== undefined ? n.toFixed(2) : '—')
  const c = (n) => n >= 70 ? 'text-emerald-400' : n >= 50 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="grid grid-cols-3 gap-2 text-center">
      {[
        { label: 'GlobalScore', v: global_score },
        { label: 'BuyerScore',  v: buyer_score  },
        { label: 'SellerScore', v: seller_score },
      ].map(({ label, v: val }) => (
        <div key={label} className="bg-war-panel rounded-lg p-2 border border-war-border">
          <div className="text-[10px] text-war-muted uppercase tracking-wide">{label}</div>
          <div className={`text-lg font-mono font-black ${c(val)}`}>{v(val)}</div>
        </div>
      ))}
    </div>
  )
}

// ── Switch log ────────────────────────────────────────────────────────────────

function SwitchLog({ switches }) {
  if (!switches || switches.length === 0) return null
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        Market Switches ({switches.length})
      </div>
      <div className="space-y-1 max-h-24 overflow-y-auto">
        {switches.map((sw, i) => (
          <div
            key={i}
            className="bg-red-950/30 border border-red-800/40 rounded px-2 py-1 text-[10px] text-red-300 font-mono"
          >
            R{sw.round} ⇢ {sw.buyer_id} away from {sw.seller_id} (u={sw.utility?.toFixed(1)})
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Closed Deals summary ──────────────────────────────────────────────────────

function ClosedDealsList({ deals }) {
  if (!deals || deals.length === 0) return null
  return (
    <div className="space-y-1">
      <div className="text-[10px] text-war-muted uppercase tracking-wide font-bold">
        Closed Deals
      </div>
      {deals.map((d, i) => (
        <div
          key={i}
          className="bg-emerald-950/30 border border-emerald-800/40 rounded px-2 py-1.5 flex justify-between items-center text-[11px] font-mono"
        >
          <span className="text-emerald-300">
            {d.buyer_name?.split(' ')[0]} × {d.seller_name}
          </span>
          <div className="text-right">
            <div className="text-emerald-400 font-bold">${d.deal_price?.toLocaleString()}</div>
            <div className="text-emerald-600/70">R{d.round} · {d.utility?.toFixed(1)}/100</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function MarketOverview({
  buyers = [],
  sellers = [],
  pairMatrix = {},
  closedDeals = [],
  dealRate = null,
  marketScore = null,
  switchEvents = [],
  currentRound = 0,
  scenario = 'used_car',
}) {
  const totalPairs = buyers.length * sellers.length

  // Determine leading pair
  let leadKey = null
  let leadUtil = -1
  Object.entries(pairMatrix).forEach(([k, p]) => {
    if (!p.closed && (p.utility ?? -1) > leadUtil) {
      leadUtil = p.utility
      leadKey  = k
    }
  })

  // Annotate leading
  const annotated = Object.fromEntries(
    Object.entries(pairMatrix).map(([k, p]) => [
      k,
      { ...p, priority: p.closed ? 'closed' : k === leadKey ? 'leading' : p.priority },
    ])
  )

  const scenarioLabel = scenario === 'used_car' ? '🚗 Used Car Market — Honda Civic 2021' : scenario

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-emerald-400">
            🏪 Market Overview
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

      {/* 3×3 Grid */}
      {buyers.length > 0 && sellers.length > 0 && (
        <div className="space-y-2">
          {/* Column headers (sellers) */}
          <div
            className="grid gap-2"
            style={{ gridTemplateColumns: `80px repeat(${sellers.length}, 1fr)` }}
          >
            <div /> {/* empty corner */}
            {sellers.map((s) => (
              <div key={s.id} className="text-center">
                <div className="text-[10px] font-bold text-war-accent uppercase truncate">
                  {s.name}
                </div>
                <div className="text-[9px] text-war-muted">{s.speed_days}d · {s.warranty_mo}mo</div>
              </div>
            ))}
          </div>

          {/* Rows (buyers) */}
          {buyers.map((b) => (
            <div
              key={b.id}
              className="grid gap-2 items-center"
              style={{ gridTemplateColumns: `80px repeat(${sellers.length}, 1fr)` }}
            >
              {/* Row header (buyer) */}
              <div className="text-right pr-2">
                <div className="text-[10px] font-bold text-war-text uppercase leading-tight">
                  {b.name?.split(' ')[0]}
                </div>
                <div className="text-[9px] text-war-muted capitalize">{b.id}</div>
                <div className="text-[9px] text-blue-400 font-mono">
                  ≤${(b.max_price / 1000).toFixed(0)}k
                </div>
              </div>

              {/* Cells */}
              {sellers.map((s) => {
                const key  = `${b.id}:${s.id}`
                const pair = annotated[key] ?? null
                return (
                  <PairCell
                    key={key}
                    pair={pair}
                    buyerName={b.name}
                    sellerName={s.name}
                  />
                )
              })}
            </div>
          ))}
        </div>
      )}

      {/* Market Score */}
      <MarketScoreSummary score={marketScore} />

      {/* Closed Deals list */}
      <ClosedDealsList deals={closedDeals} />

      {/* Switch log */}
      <SwitchLog switches={switchEvents} />

      {/* Algorithm footnote */}
      <div className="text-[10px] text-war-muted/60 border-t border-war-border pt-2">
        MBMPMS · Parallel Interaction · Market Switch &lt;{40} · GlobalScore D=30 W=55 E=15 γ=0.99
      </div>
    </div>
  )
}
