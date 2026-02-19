/**
 * DealRadar — live RadarChart showing the "Shape of the Deal".
 *
 * Renders the three deal dimensions (Price / Speed / Warranty) as a
 * Recharts RadarChart.  The shape morphs in real-time as the negotiation
 * progresses, making it immediately obvious which dimension is dragging
 * down the utility score.
 */

import React from 'react'
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

const EMPTY_DATA = [
  { dimension: 'Price',    score: 0 },
  { dimension: 'Speed',    score: 0 },
  { dimension: 'Warranty', score: 0 },
]

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const { dimension, score } = payload[0].payload
  return (
    <div className="bg-war-panel border border-war-border rounded px-3 py-2 text-xs">
      <span className="text-war-accent font-bold">{dimension}</span>
      <span className="text-gray-300 ml-2">{score.toFixed(1)} / 100</span>
    </div>
  )
}

export default function DealRadar({ data = EMPTY_DATA, provider = '—' }) {
  const hasData = data.some((d) => d.score > 0)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-war-accent text-xs font-bold uppercase tracking-widest">
          Shape of the Deal
        </h2>
        {hasData && (
          <span className="text-gray-500 text-xs">{provider}</span>
        )}
      </div>

      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart
            data={hasData ? data : EMPTY_DATA}
            margin={{ top: 10, right: 20, bottom: 10, left: 20 }}
          >
            <PolarGrid stroke="#1f2937" />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fill: '#9ca3af', fontSize: 11, fontFamily: 'inherit' }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fill: '#4b5563', fontSize: 9 }}
              tickCount={4}
            />
            <Radar
              name="Deal Shape"
              dataKey="score"
              stroke={hasData ? '#06b6d4' : '#1f2937'}
              fill={hasData ? '#06b6d4' : '#1f2937'}
              fillOpacity={hasData ? 0.25 : 0.05}
              strokeWidth={hasData ? 2 : 1}
              dot={{ fill: '#06b6d4', r: 3 }}
              animationBegin={0}
              animationDuration={600}
            />
            <Tooltip content={<CustomTooltip />} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      {!hasData && (
        <p className="text-center text-gray-600 text-xs mt-2">
          Awaiting first evaluation…
        </p>
      )}
    </div>
  )
}
