/**
 * ScorePanel — displays AgenticPay Algorithm 1 scores in real-time.
 *
 * Shows GlobalScore, BuyerScore, SellerScore as animated gauges with
 * temporal discount visualization.
 *
 * Props:
 *   globalScore    {number|null}
 *   buyerScore     {number|null}
 *   sellerScore    {number|null}
 *   discount       {number|null}   γ^round_index
 *   roundIndex     {number}
 *   success        {boolean|null}  null = in-progress
 *   agentMode      {"cyborg"|"solo"|""}
 *   taskId         {string}        e.g. "1B-1P-1S"
 *   interim        {boolean}       true while negotiation is ongoing
 */

const MAX_SCORE = 100  // D + W + E = 100

// ── Helpers ──────────────────────────────────────────────────────────────────

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v))
}

function scoreColor(val, success) {
  if (success === false) return 'text-red-400'
  if (val === null || val === undefined) return 'text-war-muted'
  if (val >= 70) return 'text-emerald-400'
  if (val >= 45) return 'text-amber-400'
  return 'text-red-400'
}

function barColor(val, success) {
  if (success === false) return 'bg-red-700'
  if (val === null || val === undefined) return 'bg-war-muted/30'
  if (val >= 70) return 'bg-emerald-500'
  if (val >= 45) return 'bg-amber-500'
  return 'bg-red-600'
}

// ── Score bar ─────────────────────────────────────────────────────────────────

function ScoreBar({ label, value, success, maxVal = MAX_SCORE, sublabel = '' }) {
  const pct = value === null ? 0 : clamp((value / maxVal) * 100, 0, 100)
  const color = barColor(value, success)
  const textColor = scoreColor(value, success)

  return (
    <div className="space-y-1">
      <div className="flex justify-between items-baseline">
        <span className="text-xs text-war-muted uppercase tracking-wider">{label}</span>
        <span className={`text-sm font-mono font-bold ${textColor}`}>
          {value === null ? '—' : value.toFixed(2)}
          {sublabel && <span className="text-xs text-war-muted ml-1">{sublabel}</span>}
        </span>
      </div>
      <div className="h-2 bg-war-panel rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ── Discount ring ─────────────────────────────────────────────────────────────

function DiscountRing({ discount, roundIndex }) {
  if (discount === null) return null
  const pct = clamp(discount * 100, 0, 100)
  const r = 20
  const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="56" height="56" className="rotate-[-90deg]">
        <circle cx="28" cy="28" r={r} fill="none" stroke="#1e293b" strokeWidth="4" />
        <circle
          cx="28" cy="28" r={r}
          fill="none"
          stroke={discount > 0.9 ? '#10b981' : discount > 0.75 ? '#f59e0b' : '#ef4444'}
          strokeWidth="4"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          className="transition-all duration-700"
        />
      </svg>
      <div className="text-center -mt-1">
        <div className="text-xs font-mono font-bold text-war-accent">{(discount * 100).toFixed(1)}%</div>
        <div className="text-[10px] text-war-muted">γ^{roundIndex}</div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ScorePanel({
  globalScore = null,
  buyerScore = null,
  sellerScore = null,
  discount = null,
  roundIndex = 0,
  success = null,
  agentMode = '',
  taskId = '',
  interim = true,
}) {
  const modeColor = agentMode === 'cyborg' ? 'text-cyan-400 border-cyan-800/60'
                  : agentMode === 'solo'   ? 'text-orange-400 border-orange-800/60'
                  : 'text-war-accent border-war-border'

  const statusBadge = success === null
    ? { text: interim ? 'LIVE' : 'PENDING', cls: 'bg-blue-900/60 text-blue-300 border border-blue-700/60 animate-pulse' }
    : success
      ? { text: 'AGREED', cls: 'bg-emerald-900/60 text-emerald-300 border border-emerald-700' }
      : { text: 'FAILED', cls: 'bg-red-900/60 text-red-300 border border-red-700' }

  return (
    <div className={`bg-war-card border rounded-lg p-4 space-y-4 ${modeColor}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className={`text-xs font-bold uppercase tracking-widest ${modeColor.split(' ')[0]}`}>
            ⚖ AgenticPay Score
          </div>
          {taskId && (
            <div className="text-[10px] text-war-muted mt-0.5">Task {taskId}</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-2 py-0.5 rounded font-mono ${statusBadge.cls}`}>
            {statusBadge.text}
          </span>
          {agentMode && (
            <span className={`text-[10px] px-2 py-0.5 rounded border font-mono uppercase ${modeColor}`}>
              {agentMode}
            </span>
          )}
        </div>
      </div>

      {/* Discount ring + round */}
      <div className="flex items-center gap-4">
        <DiscountRing discount={discount} roundIndex={roundIndex} />
        <div className="flex-1 space-y-1">
          <div className="text-xs text-war-muted">Round</div>
          <div className="text-2xl font-mono font-bold text-war-text">{roundIndex}</div>
          <div className="text-[10px] text-war-muted">discount = γ^t (γ=0.99)</div>
        </div>
      </div>

      {/* Score bars */}
      <div className="space-y-3">
        <ScoreBar
          label="GlobalScore"
          value={globalScore}
          success={success}
          maxVal={MAX_SCORE}
          sublabel="/100"
        />
        <ScoreBar
          label="BuyerScore"
          value={buyerScore}
          success={success}
          maxVal={MAX_SCORE}
          sublabel="/100"
        />
        <ScoreBar
          label="SellerScore"
          value={sellerScore}
          success={success}
          maxVal={MAX_SCORE}
          sublabel="/100"
        />
      </div>

      {/* Formula footnote */}
      <div className="text-[10px] text-war-muted border-t border-war-border pt-2 space-y-0.5">
        <div>GlobalScore = D·γᵗ + W·Q·γᵗ + E·γᵗ</div>
        <div className="text-war-muted/60">D=30, W=55, E=15, γ=0.99, Q=4·u_b·u_s</div>
      </div>
    </div>
  )
}
