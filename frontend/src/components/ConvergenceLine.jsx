/**
 * ConvergenceLine — tracks the Price Gap between Buyer and Sellers.
 *
 * X-axis: negotiation round.
 * Y-axis: gap = provider_price − purchaser_target.
 *
 * Gap > 0 → still above target (red zone).
 * Gap ≤ 0 → below target (deal territory, green zone).
 */

import React from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-war-panel border border-war-border rounded px-3 py-2 text-xs space-y-1">
      <div className="text-war-accent font-bold">Round {label}</div>
      <div className="text-gray-300">
        <span className="text-gray-500">Provider: </span>
        {d.provider_name}
      </div>
      <div className="text-gray-300">
        <span className="text-gray-500">Price: </span>${d.price?.toFixed(2)}
      </div>
      <div className="text-gray-300">
        <span className="text-gray-500">Target: </span>${d.purchaser_target?.toFixed(2)}
      </div>
      <div className={d.gap <= 0 ? 'text-war-green font-bold' : 'text-war-red font-bold'}>
        Gap: {d.gap > 0 ? '+' : ''}${d.gap?.toFixed(2)}
      </div>
    </div>
  )
}

export default function ConvergenceLine({ history = [] }) {
  const data = history.map((h) => ({ ...h, round: `R${h.round}` }))
  const hasData = data.length > 0
  const lastGap = hasData ? data[data.length - 1].gap : null

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-war-accent text-xs font-bold uppercase tracking-widest">
          Price Convergence
        </h2>
        {lastGap !== null && (
          <span
            className={`text-xs font-bold ${
              lastGap <= 0 ? 'text-war-green' : 'text-war-red'
            }`}
          >
            Gap: {lastGap > 0 ? '+' : ''}${lastGap.toFixed(2)}
          </span>
        )}
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={hasData ? data : [{ round: 'R0', gap: 0 }]}
            margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
            <XAxis
              dataKey="round"
              tick={{ fill: '#6b7280', fontSize: 10 }}
              axisLine={{ stroke: '#374151' }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 10 }}
              axisLine={{ stroke: '#374151' }}
              tickLine={false}
              tickFormatter={(v) => `$${v}`}
            />
            <ReferenceLine
              y={0}
              stroke="#10b981"
              strokeDasharray="6 3"
              label={{
                value: 'Deal Zone',
                position: 'insideRight',
                fill: '#10b981',
                fontSize: 9,
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="gap"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={{ fill: '#f59e0b', r: 4, strokeWidth: 0 }}
              activeDot={{ r: 6, fill: '#fbbf24' }}
              animationDuration={500}
              isAnimationActive={true}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {!hasData && (
        <p className="text-center text-gray-600 text-xs mt-2">
          Awaiting first offer…
        </p>
      )}
    </div>
  )
}
