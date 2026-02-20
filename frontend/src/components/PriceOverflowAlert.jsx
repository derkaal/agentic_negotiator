/**
 * PriceOverflowAlert — displays Price Overflow and Termination Round events.
 *
 * Props:
 *   overflowEvents      {Array}  price_overflow event objects
 *   terminationEvent    {Object|null}  termination_round event
 *   actionEvents        {Array}  action_extracted events (parser Π successes)
 *   agentMode           {"cyborg"|"solo"|""}
 */

// ── Price Overflow event card ─────────────────────────────────────────────────

function OverflowCard({ event }) {
  return (
    <div className="bg-red-950/60 border border-red-700/60 rounded p-3 space-y-1">
      <div className="flex items-center gap-2">
        <span className="text-red-400 text-sm">⚠</span>
        <span className="text-red-300 text-xs font-bold uppercase tracking-wide">Price Overflow</span>
        <span className="ml-auto text-[10px] text-red-500/80 font-mono">
          Round {event.round} · {event.role?.toUpperCase()}
        </span>
      </div>
      <div className="text-[11px] text-red-200/80">{event.reason}</div>
      {event.raw_text && (
        <div className="text-[10px] text-red-300/50 font-mono truncate">
          ↳ "{event.raw_text}"
        </div>
      )}
    </div>
  )
}

// ── Parser Π success card ─────────────────────────────────────────────────────

function ActionCard({ event }) {
  return (
    <div className="bg-emerald-950/40 border border-emerald-800/40 rounded px-3 py-2 flex items-center gap-3">
      <span className="text-emerald-400 text-xs">✓</span>
      <div className="flex-1">
        <span className="text-[10px] text-emerald-400/70 uppercase">Parser Π</span>
        <span className="text-[10px] text-war-muted ml-2">Round {event.round} · {event.role}</span>
      </div>
      <span className="text-emerald-300 font-mono text-sm font-bold">
        ${event.price?.toFixed(2)}
      </span>
    </div>
  )
}

// ── Termination summary ───────────────────────────────────────────────────────

function TerminationCard({ event, agentMode }) {
  if (!event) return null

  const agreed = event.success
  const borderColor = agreed
    ? 'border-emerald-600/60 bg-emerald-950/50'
    : 'border-red-700/60 bg-red-950/50'

  const modeColor = agentMode === 'cyborg' ? 'text-cyan-400'
                  : agentMode === 'solo'   ? 'text-orange-400'
                  : 'text-war-accent'

  return (
    <div className={`border rounded-lg p-4 space-y-3 ${borderColor}`}>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-bold uppercase tracking-widest ${modeColor}`}>
          ◼ Termination Round
        </span>
        <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
          agreed
            ? 'bg-emerald-900/60 text-emerald-300 border-emerald-700'
            : 'bg-red-900/60 text-red-300 border-red-700'
        }`}>
          {agreed ? 'AGREED' : event.termination_reason?.toUpperCase() || 'FAILED'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 text-center">
        <div className="bg-war-panel/60 rounded p-2">
          <div className="text-[10px] text-war-muted uppercase">Round</div>
          <div className="text-xl font-mono font-bold text-war-text">{event.round}</div>
        </div>
        <div className="bg-war-panel/60 rounded p-2">
          <div className="text-[10px] text-war-muted uppercase">Final Price</div>
          <div className={`text-xl font-mono font-bold ${agreed ? 'text-emerald-400' : 'text-red-400'}`}>
            {event.final_price ? `$${event.final_price.toFixed(0)}` : '—'}
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <ScoreLine label="GlobalScore" value={event.global_score} agreed={agreed} />
        <ScoreLine label="BuyerScore" value={event.buyer_score} agreed={agreed} />
        <ScoreLine label="SellerScore" value={event.seller_score} agreed={agreed} />
      </div>
    </div>
  )
}

function ScoreLine({ label, value, agreed }) {
  const color = value === undefined || value === null ? 'text-war-muted'
              : agreed && value >= 70 ? 'text-emerald-400'
              : agreed && value >= 45 ? 'text-amber-400'
              : 'text-red-400'
  return (
    <div className="flex justify-between items-center text-xs">
      <span className="text-war-muted">{label}</span>
      <span className={`font-mono font-bold ${color}`}>
        {value !== undefined && value !== null ? value.toFixed(3) : '—'}
      </span>
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function PriceOverflowAlert({
  overflowEvents = [],
  terminationEvent = null,
  actionEvents = [],
  agentMode = '',
}) {
  const hasAny = overflowEvents.length > 0 || actionEvents.length > 0 || terminationEvent

  const modeColor = agentMode === 'cyborg' ? 'text-cyan-400 border-cyan-800/60'
                  : agentMode === 'solo'   ? 'text-orange-400 border-orange-800/60'
                  : 'text-war-accent border-war-border'

  if (!hasAny) return null

  return (
    <div className={`bg-war-card border rounded-lg p-4 space-y-3 ${modeColor}`}>
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className={`text-xs font-bold uppercase tracking-widest ${modeColor.split(' ')[0]}`}>
          ⚡ Parser Π / Events
        </span>
        {overflowEvents.length > 0 && (
          <span className="text-[10px] bg-red-900/60 text-red-300 border border-red-700/60 px-2 py-0.5 rounded font-mono">
            {overflowEvents.length} overflow{overflowEvents.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Successful price extractions */}
      {actionEvents.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-war-muted uppercase tracking-wide">Extracted Prices</div>
          {actionEvents.slice(-6).map((ev, i) => (
            <ActionCard key={i} event={ev} />
          ))}
        </div>
      )}

      {/* Overflow events */}
      {overflowEvents.length > 0 && (
        <div className="space-y-2">
          <div className="text-[10px] text-red-400/80 uppercase tracking-wide">Invalid Moves</div>
          {overflowEvents.slice(-4).map((ev, i) => (
            <OverflowCard key={i} event={ev} />
          ))}
        </div>
      )}

      {/* Termination summary */}
      {terminationEvent && (
        <TerminationCard event={terminationEvent} agentMode={agentMode} />
      )}
    </div>
  )
}
