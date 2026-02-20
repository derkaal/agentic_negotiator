/**
 * ThoughtFeed — streaming terminal showing the Agent Inner Monologue.
 *
 * Standard tags:
 *   [STRATEGY]           — agent approach      (purple)
 *   [TOOL_CALL]          — grounding tool call  (cyan)
 *   [MATH_RESULT]        — tool result data     (yellow)
 *   [DECISION]           — agent act            (green/red)
 *
 * Adversarial tags (hostile mode):
 *   [ADVERSARIAL_INTENT] — QuickShoe's attack plan        (crimson)
 *   [TRICK_ATTEMPT]      — the deceptive offer being made (orange)
 *   [DETECTION]          — shield catches the trick       (amber)
 *   [VETO]               — transaction blocked            (red bold)
 *
 * A/B Test tags (solo/cyborg modes):
 *   [INTERNAL_MATH]      — solo agent's hallucinated estimate   (orange-red)
 *   [SOCIAL_PRESSURE]    — provider pressure tactic detected    (amber)
 *   [HALLUCINATION]      — solo agent accepting bad deal        (red bold italic)
 *   agent_type badge     — shows [SOLO] or [CYBORG] prefix
 */

import React, { useEffect, useRef } from 'react'
import clsx from 'clsx'

const TAG_STYLES = {
  // Standard
  STRATEGY:           'bg-purple-900/50  text-purple-300  border border-purple-700/50',
  TOOL_CALL:          'bg-cyan-900/50    text-cyan-300    border border-cyan-700/50',
  MATH_RESULT:        'bg-yellow-900/40  text-yellow-300  border border-yellow-700/50',
  DECISION:           'bg-emerald-900/50 text-emerald-300 border border-emerald-700/50',
  // Adversarial
  ADVERSARIAL_INTENT: 'bg-red-950/80     text-red-300     border border-red-700/70',
  TRICK_ATTEMPT:      'bg-orange-950/70  text-orange-300  border border-orange-700/60',
  DETECTION:          'bg-amber-900/60   text-amber-300   border border-amber-600/60',
  VETO:               'bg-red-900/80     text-red-200     border border-red-500/80',
  // A/B Test — Solo Agent
  INTERNAL_MATH:      'bg-orange-900/60  text-orange-200  border border-orange-600/60',
  SOCIAL_PRESSURE:    'bg-amber-900/50   text-amber-300   border border-amber-600/50',
  HALLUCINATION:      'bg-red-900/70     text-red-200     border border-red-500/70',
}

const ACTOR_COLORS = {
  PURCHASER:         'text-cyan-400',
  PROVIDER_1:        'text-purple-400',
  PROVIDER_2:        'text-pink-400',
  PROVIDER_3:        'text-orange-400',
  QUICKSHOE:         'text-red-400',
  QUICKSHOE_HOSTILE: 'text-red-400',
}

function actorColor(actor) {
  return ACTOR_COLORS[actor] ?? 'text-gray-400'
}

function actorLabel(actor) {
  const map = {
    PURCHASER:         'PURCHASER',
    PROVIDER_1:        'NOVA KICKS',
    PROVIDER_2:        'SOLEMASTER',
    PROVIDER_3:        'QUICKSHOE',
    QUICKSHOE:         '☠ QUICKSHOE',
    QUICKSHOE_HOSTILE: '☠ QUICKSHOE',
  }
  return map[actor] ?? actor
}

const ADVERSARIAL_TAGS = new Set([
  'ADVERSARIAL_INTENT', 'TRICK_ATTEMPT', 'DETECTION', 'VETO',
])

const SOLO_TAGS = new Set([
  'INTERNAL_MATH', 'SOCIAL_PRESSURE', 'HALLUCINATION',
])

const AGENT_TYPE_BADGES = {
  solo:   { label: 'SOLO',   cls: 'bg-orange-900/60 text-orange-300 border border-orange-700/50' },
  cyborg: { label: 'CYBORG', cls: 'bg-cyan-900/60 text-cyan-300 border border-cyan-700/50' },
}

function ThoughtEntry({ thought }) {
  const isJson =
    thought.tag === 'MATH_RESULT' && thought.content?.trim().startsWith('{')
  const isAdversarial = ADVERSARIAL_TAGS.has(thought.tag)
  const isSoloTag     = SOLO_TAGS.has(thought.tag)
  const agentBadge    = thought.agentType ? AGENT_TYPE_BADGES[thought.agentType] : null

  let displayContent = thought.content ?? ''
  if (isJson) {
    try {
      displayContent = JSON.stringify(JSON.parse(thought.content), null, 2)
    } catch { /* keep as-is */ }
  }

  const isVeto   = thought.tag === 'VETO' || displayContent.includes('HALTED') || displayContent.includes('CYBORG VETO')
  const isAccept = displayContent.startsWith('ACCEPT') || displayContent.includes('DEAL CLOSED')
  const isHallucination = thought.tag === 'INTERNAL_MATH' || thought.tag === 'HALLUCINATION'

  return (
    <div className={clsx(
      'animate-fade-in border-b pb-3 mb-3 last:border-0',
      isAdversarial  ? 'border-red-900/50'    :
      isSoloTag      ? 'border-orange-900/40' :
                       'border-war-border/40',
    )}>
      {/* Header row */}
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        {/* Agent type badge (A/B test only) */}
        {agentBadge && (
          <span className={clsx('text-xs font-black px-1.5 py-0.5 rounded', agentBadge.cls)}>
            [{agentBadge.label}]
          </span>
        )}
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
            🚨 BLOCKED
          </span>
        )}
        {isAccept && (
          <span className="text-xs font-bold text-war-green">✓ DEAL</span>
        )}
        {isHallucination && (
          <span className="text-xs font-bold text-orange-400 animate-pulse">
            ⚠️ UNGROUNDED
          </span>
        )}
      </div>

      {/* Content */}
      {isJson ? (
        <pre className={clsx(
          'text-xs rounded p-2 overflow-x-auto whitespace-pre-wrap leading-relaxed border',
          isAdversarial
            ? 'text-red-300 bg-red-950/30 border-red-800/50'
            : 'text-gray-400 bg-black/30 border-war-border/50',
        )}>
          {displayContent}
        </pre>
      ) : (
        <p className={clsx(
          'text-xs leading-relaxed font-mono',
          thought.tag === 'ADVERSARIAL_INTENT' ? 'text-red-300 italic'           :
          thought.tag === 'TRICK_ATTEMPT'      ? 'text-orange-300'               :
          thought.tag === 'DETECTION'          ? 'text-amber-300 font-semibold'  :
          thought.tag === 'INTERNAL_MATH'      ? 'text-orange-200/80 italic'     :
          thought.tag === 'SOCIAL_PRESSURE'    ? 'text-amber-300'                :
          thought.tag === 'HALLUCINATION'      ? 'text-red-200 font-bold italic' :
          isVeto                               ? 'text-red-200 font-bold'        :
          isAccept                             ? 'text-emerald-300'              :
                                                 'text-gray-300'
        )}>
          {displayContent}
        </p>
      )}
    </div>
  )
}

export default function ThoughtFeed({ thoughts = [], label = 'Agent Thought Feed', agentMode = null }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [thoughts.length])

  const headerColor =
    agentMode === 'solo'   ? 'text-orange-400' :
    agentMode === 'cyborg' ? 'text-cyan-400'   :
                             'text-war-accent'

  const dotColor =
    agentMode === 'solo'   ? 'bg-orange-400' :
    agentMode === 'cyborg' ? 'bg-cyan-400'   :
                             'bg-war-green'

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 mb-3">
        <div className={clsx('w-2 h-2 rounded-full animate-pulse', dotColor)} />
        <h2 className={clsx('text-xs font-bold uppercase tracking-widest', headerColor)}>
          {label}
        </h2>
        {agentMode === 'solo' && (
          <span className="text-orange-500 text-xs font-mono">[NO ANCHOR]</span>
        )}
        {agentMode === 'cyborg' && (
          <span className="text-cyan-600 text-xs font-mono">[GROUNDED]</span>
        )}
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
