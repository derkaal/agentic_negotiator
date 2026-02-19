/**
 * VetoFlash — prominent red banner that fires whenever the MarginValidator
 * blocks an LLM's proposed move.
 *
 * Animates in, stays for ~4 seconds, then fades out.
 * The parent controls `visible` via a timer set in useNegotiationStream.
 */

import React from 'react'
import clsx from 'clsx'

export default function VetoFlash({ veto, visible }) {
  if (!veto) return null

  return (
    <div
      className={clsx(
        'fixed inset-x-0 top-0 z-50 transition-all duration-300',
        visible ? 'translate-y-0 opacity-100' : '-translate-y-full opacity-0'
      )}
    >
      {/* Flashing red banner */}
      <div className="bg-war-red/95 backdrop-blur border-b-2 border-red-300 shadow-2xl shadow-red-900/50">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-start gap-4">
          {/* Icon */}
          <div className="flex-shrink-0 animate-pulse-fast">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
              />
            </svg>
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-white font-bold text-sm tracking-wider">
                HARD VETO
              </span>
              <span className="bg-white/20 text-white text-xs px-2 py-0.5 rounded font-mono">
                {veto.actor}
              </span>
            </div>
            <p className="text-red-100 text-xs font-mono leading-relaxed">
              {veto.message}
            </p>
            <div className="flex gap-4 mt-1.5 text-xs text-red-200 font-mono">
              <span>Proposed: <strong className="text-white">${veto.proposed_price?.toFixed(2)}</strong></span>
              <span>Floor: <strong className="text-white">${veto.floor_price?.toFixed(2)}</strong></span>
            </div>
          </div>

          {/* BLOCKED badge */}
          <div className="flex-shrink-0 border-2 border-white/50 rounded px-3 py-1">
            <span className="text-white font-black text-xs tracking-widest">
              BLOCKED
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
