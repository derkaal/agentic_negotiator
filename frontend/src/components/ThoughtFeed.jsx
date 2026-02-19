/**
 * ThoughtFeed — streaming terminal showing the Agent Inner Monologue.
 *
 * Each thought entry has a tag:
 *   [STRATEGY]    — agent decides on approach  (purple)
 *   [TOOL_CALL]   — agent invokes a grounding tool (cyan)
 *   [MATH_RESULT] — tool returns structured data  (yellow)
 *   [DECISION]    — agent acts on the result       (green / red)
 *
 * The feed auto-scrolls to the latest entry.
 */

import React, { useEffect, useRef } from 'react'
import clsx from 'clsx'

const TAG_STYLES = {
  STRATEGY:    'bg-purple-900/50 text-purple-300 border border-purple-700/50',
  TOOL_CALL:   'bg-cyan-900/50  text-cyan-300   border border-cyan-700/50',
  MATH_RESULT: 'bg-yellow-900/40 text-yellow-300 border border-yellow-700/50',
  DECISION:    'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50',
}

const ACTOR_COLORS = {
  PURCHASER:  'text-cyan-400',
  PROVIDER_1: 'text-purple-400',
  PROVIDER_2: 'text-pink-400',
  PROVIDER_3: 'text-orange-400',
}

function actorColor(actor) {
  return ACTOR_COLORS[actor] ?? 'text-gray-400'
}

function actorLabel(actor) {
  const map = {
    PURCHASER:  'PURCHASER',
    PROVIDER_1: 'NOVA KICKS',
    PROVIDER_2: 'SOLEMASTER',
    PROVIDER_3: 'QUICKSHOE',
  }
  return map[actor] ?? actor
}

function ThoughtEntry({ thought }) {
  const isJson =
    thought.tag === 'MATH_RESULT' && thought.content.trim().startsWith('{')

  let displayContent = thought.content
  if (isJson) {
    try {
      displayContent = JSON.stringify(JSON.parse(thought.content), null, 2)
    } catch {
      /* keep as-is */
    }
  }

  const isVeto = thought.content.includes('VETO')
  const isAccept = thought.content.startsWith('ACCEPT')

  return (
    <div className="animate-fade-in border-b border-war-border/40 pb-3 mb-3 last:border-0">
      {/* Header row */}
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <span className={clsx('text-xs font-bold', actorColor(thought.actor))}>
          {actorLabel(thought.actor)}
        </span>
        <span
          className={clsx(
            'text-xs font-bold px-1.5 py-0.5 rounded',
            TAG_STYLES[thought.tag] ?? 'bg-gray-800 text-gray-400'
          )}
        >
          [{thought.tag}]
        </span>
        {isVeto && (
          <span className="text-xs font-bold text-war-red animate-pulse">
            ⚠ VETO
          </span>
        )}
        {isAccept && (
          <span className="text-xs font-bold text-war-green">✓ DEAL</span>
        )}
      </div>

      {/* Content */}
      {isJson ? (
        <pre className="text-xs text-gray-400 bg-black/30 rounded p-2 overflow-x-auto whitespace-pre-wrap leading-relaxed border border-war-border/50">
          {displayContent}
        </pre>
      ) : (
        <p
          className={clsx(
            'text-xs leading-relaxed font-mono',
            isVeto
              ? 'text-red-300'
              : isAccept
              ? 'text-emerald-300'
              : 'text-gray-300'
          )}
        >
          {displayContent}
        </p>
      )}
    </div>
  )
}

export default function ThoughtFeed({ thoughts = [] }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thoughts.length])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-war-green animate-pulse" />
        <h2 className="text-war-accent text-xs font-bold uppercase tracking-widest">
          Agent Thought Feed
        </h2>
        <span className="ml-auto text-gray-600 text-xs">{thoughts.length} events</span>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 pr-1">
        {thoughts.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-600 text-xs text-center">
              Start a negotiation to see agent reasoning…
            </p>
          </div>
        ) : (
          <>
            {thoughts.map((t) => (
              <ThoughtEntry key={t.id} thought={t} />
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>
    </div>
  )
}
