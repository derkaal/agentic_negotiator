"""
LangGraph negotiation state machine — powered by Claude Haiku 4.5.

Each node runs a real LLM reasoning step, using LangChain tool-calling to
invoke the grounding tools.  All intermediate steps are emitted as events
so the War Room UI can stream [STRATEGY] → [TOOL_CALL] → [MATH_RESULT] → [DECISION].

Graph topology
──────────────
  START → purchaser_node → provider_node → evaluator_node
                 ↑_____________________________________|  (if CONTINUE)
                                                       → END (ACCEPT / NO_DEAL)
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncGenerator, Optional

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from logic_engine import (
    PROVIDER_ASKS,
    margin_validator,
    price_oracle,
    utility_calculator,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Shared async event queue
# ---------------------------------------------------------------------------

_event_queue: asyncio.Queue = asyncio.Queue()


async def event_stream() -> AsyncGenerator[dict, None]:
    while True:
        event = await _event_queue.get()
        yield event
        if event.get("type") == "negotiation_end":
            break


async def _emit(event: dict) -> None:
    await _event_queue.put(event)


# ---------------------------------------------------------------------------
# LLM factory — Claude Haiku 4.5
# ---------------------------------------------------------------------------

def _build_llm() -> ChatAnthropic:
    return ChatAnthropic(
        model="claude-haiku-4-5-20251001",
        temperature=0.3,
        max_tokens=512,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class NegotiationState(BaseModel):
    round: int = 0
    max_rounds: int = 6

    provider_offers: dict[str, float] = {
        "provider_1": PROVIDER_ASKS["provider_1"],
        "provider_2": PROVIDER_ASKS["provider_2"],
        "provider_3": PROVIDER_ASKS["provider_3"],
    }

    purchaser_target: float = 150.0
    best_deal: Optional[dict] = None
    active_provider: str = "provider_1"
    outcome: Optional[str] = None
    convergence_history: list[dict] = []
    radar_shape: dict = {"price_score": 0, "speed_score": 0, "warranty_score": 0}
    last_veto: Optional[dict] = None
    purchaser_type: str = "tough"


# ---------------------------------------------------------------------------
# Provider static data
# ---------------------------------------------------------------------------

PROVIDER_PERSONAS = {
    "provider_1": {"name": "Nova Kicks",  "stock": 15, "speed_days": 7,  "warranty_months": 12, "concession_rate": 0.06},
    "provider_2": {"name": "SoleMaster",  "stock": 8,  "speed_days": 3,  "warranty_months": 24, "concession_rate": 0.03},
    "provider_3": {"name": "QuickShoe",   "stock": 25, "speed_days": 2,  "warranty_months": 6,  "concession_rate": 0.08},
}

QUANTITY = 10

PURCHASER_WEIGHT_HINT = {
    "tough":     "Price 70%, Speed 15%, Warranty 15% — price is the dominant factor.",
    "emergency": "Price 20%, Speed 70%, Warranty 10% — speed/delivery time is dominant.",
}


# ---------------------------------------------------------------------------
# Helper: map tool name → callable
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "utility_calculator": utility_calculator,
    "price_oracle":       price_oracle,
    "margin_validator":   margin_validator,
}


# ---------------------------------------------------------------------------
# Core helper: invoke LLM with tools, stream all tool calls as events,
# return (final_ai_message, tool_logs)
#   tool_logs = [(tool_name, args_dict, result_dict), ...]
# ---------------------------------------------------------------------------

async def _llm_with_tools(
    messages: list,
    tools: list,
    actor: str,
    forced_tool: Optional[str] = None,
) -> tuple[AIMessage, list[tuple[str, dict, dict]]]:
    llm = _build_llm()
    bind_kwargs: dict = {}
    if forced_tool:
        bind_kwargs["tool_choice"] = {"type": "tool", "name": forced_tool}
    llm_bound = llm.bind_tools(tools, **bind_kwargs)

    response: AIMessage = await llm_bound.ainvoke(messages)
    tool_logs: list[tuple[str, dict, dict]] = []

    if not response.tool_calls:
        return response, tool_logs

    # Execute every tool call and feed results back
    conv = list(messages) + [response]
    for tc in response.tool_calls:
        name: str = tc["name"]
        args: dict = tc["args"]

        await _emit({
            "type": "thought", "actor": actor, "tag": "TOOL_CALL",
            "content": f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())})",
        })

        result: dict = _TOOL_MAP[name].invoke(args)
        tool_logs.append((name, args, result))

        await _emit({
            "type": "thought", "actor": actor, "tag": "MATH_RESULT",
            "content": json.dumps(result, indent=2),
        })

        conv.append(ToolMessage(content=json.dumps(result), tool_call_id=tc["id"]))

    # Re-invoke (no tools bound) to get the plain-text synthesis
    final: AIMessage = await _build_llm().ainvoke(conv)
    return final, tool_logs


# ---------------------------------------------------------------------------
# Purchaser Node
# ---------------------------------------------------------------------------

PURCHASER_SYSTEM = """\
You are an Agentic Purchaser in a live Negotiation War Room.
Goal: buy {qty} pairs of Limited Edition Sneakers at the best possible price.

Buyer profile — {profile_hint}

Current provider offers (per pair):
{offers_table}

Your current target price: ${target:.2f}
Negotiation round: {round}/{max_rounds}

Rules you MUST follow:
1. Call price_oracle first to anchor yourself to the market rate.
2. Call utility_calculator to score EACH provider's current offer in turn.
3. State your updated target price and one-paragraph strategy.
Keep responses concise.
"""

async def purchaser_node(state: NegotiationState) -> dict:
    offers_table = "\n".join(
        f"  {PROVIDER_PERSONAS[pid]['name']:12s}  ${price:.2f}"
        for pid, price in state.provider_offers.items()
    )
    system = PURCHASER_SYSTEM.format(
        qty=QUANTITY,
        profile_hint=PURCHASER_WEIGHT_HINT[state.purchaser_type],
        offers_table=offers_table,
        target=state.purchaser_target,
        round=state.round + 1,
        max_rounds=state.max_rounds,
    )

    await _emit({"type": "thought", "actor": "PURCHASER", "tag": "STRATEGY",
                 "content": f"[Round {state.round + 1}] Analysing provider landscape…"})

    # ── Phase 1: price_oracle → market anchor ────────────────────────────
    phase1_msgs = [
        SystemMessage(content=system),
        HumanMessage(content=(
            "Call price_oracle to get today's market reference price "
            "for Limited Edition Sneakers, then summarise your opening strategy."
        )),
    ]
    strategy_reply, strategy_logs = await _llm_with_tools(
        phase1_msgs, [price_oracle], actor="PURCHASER",
        forced_tool="price_oracle",
    )
    await _emit({"type": "thought", "actor": "PURCHASER", "tag": "STRATEGY",
                 "content": strategy_reply.content.strip()})

    # Extract market avg for target recalculation
    market_avg = 150.0
    for _, _, result in strategy_logs:
        if "market_average_per_pair" in result:
            market_avg = result["market_average_per_pair"]
            break

    # ── Phase 2: utility_calculator on ALL three providers ────────────────
    for pid, price in state.provider_offers.items():
        persona = PROVIDER_PERSONAS[pid]
        phase2_msgs = [
            SystemMessage(content=system),
            HumanMessage(content=(
                f"Score {persona['name']}'s offer using utility_calculator: "
                f"price={price}, speed_days={persona['speed_days']}, "
                f"warranty_months={persona['warranty_months']}, "
                f"purchaser_type='{state.purchaser_type}'. "
                "Briefly state whether this offer is worth pursuing."
            )),
        ]
        eval_reply, _ = await _llm_with_tools(
            phase2_msgs, [utility_calculator], actor="PURCHASER",
            forced_tool="utility_calculator",
        )
        await _emit({"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
                     "content": f"[{persona['name']}] {eval_reply.content.strip()}"})

    # Deterministic target update (LLM reasoning is advisory)
    fair_low = market_avg * 0.90
    new_target = max(fair_low, state.purchaser_target - 3.0)

    return {
        "round": state.round + 1,
        "purchaser_target": new_target,
    }


# ---------------------------------------------------------------------------
# Provider Node
# ---------------------------------------------------------------------------

PROVIDER_SYSTEM = """\
You are the negotiation agent for {name} (ID: {pid}).
Item: Limited Edition Sneakers — {speed_days}-day delivery, {warranty_months}-month warranty.

Your current ask: ${current_price:.2f} per pair.
Purchaser's target: ${purchaser_target:.2f} per pair.

You MUST call margin_validator before offering any price reduction.
If it returns VETO, you must hold your current price.
If it returns APPROVED, offer the validated price.
Be brief — one sentence decision after the tool result.
"""

async def provider_node(state: NegotiationState) -> dict:
    new_offers = dict(state.provider_offers)
    last_veto = None
    convergence_additions: list[dict] = []

    # Negotiate with every provider in sequence each round
    for pid, persona in PROVIDER_PERSONAS.items():
        current_price = new_offers[pid]

        await _emit({"type": "thought", "actor": pid.upper(), "tag": "STRATEGY",
                     "content": (
                         f"{persona['name']} evaluating concession. "
                         f"Ask: ${current_price:.2f} | Purchaser target: ${state.purchaser_target:.2f}."
                     )})

        proposed = round(current_price * (1 - persona["concession_rate"]), 2)

        system = PROVIDER_SYSTEM.format(
            name=persona["name"], pid=pid,
            speed_days=persona["speed_days"],
            warranty_months=persona["warranty_months"],
            current_price=current_price,
            purchaser_target=state.purchaser_target,
        )
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=(
                f"Validate a proposed price of ${proposed:.2f} by calling "
                f"margin_validator with provider_id='{pid}' and "
                f"proposed_price={proposed}.  Then state your final offer."
            )),
        ]

        final_msg, tool_logs = await _llm_with_tools(
            messages, [margin_validator], actor=pid.upper(),
            forced_tool="margin_validator",
        )

        final_price = current_price  # safe default: hold
        for tool_name, args, result in tool_logs:
            if tool_name != "margin_validator":
                continue
            if result.get("status") == "VETO":
                last_veto = result
                await _emit({
                    "type": "veto",
                    "actor": pid.upper(),
                    "message": result["message"],
                    "proposed_price": args["proposed_price"],
                    "floor_price": result["floor_price"],
                })
                await _emit({"type": "thought", "actor": pid.upper(), "tag": "DECISION",
                             "content": f"VETO — holding at ${current_price:.2f}."})
            else:
                final_price = args["proposed_price"]
                await _emit({"type": "thought", "actor": pid.upper(), "tag": "DECISION",
                             "content": final_msg.content.strip()})

        new_offers[pid] = final_price

        gap = round(final_price - state.purchaser_target, 2)
        conv_entry = {
            "round": state.round,
            "gap": gap,
            "provider_id": pid,
            "provider_name": persona["name"],
            "price": final_price,
            "purchaser_target": state.purchaser_target,
        }
        convergence_additions.append(conv_entry)
        await _emit({"type": "convergence", "data": conv_entry})

    return {
        "provider_offers": new_offers,
        "last_veto": last_veto,
        "convergence_history": state.convergence_history + convergence_additions,
    }


# ---------------------------------------------------------------------------
# Evaluator Node
# ---------------------------------------------------------------------------

EVALUATOR_SYSTEM = """\
You are a neutral deal evaluator.
Score result from utility_calculator:
{score_json}

Buyer profile: {profile_hint}
Purchaser's current target: ${target:.2f}
Provider's price: ${price:.2f}

Thresholds (hard rules — you cannot override them):
  • overall_score >= 55 AND price <= target × 1.05 → ACCEPT
  • otherwise → REJECT (explain which dimension is dragging the score)

Give a single direct sentence verdict.
"""

async def evaluator_node(state: NegotiationState) -> dict:
    # Score all three providers and pick the highest utility deal
    all_scores: dict[str, dict] = {}
    for pid, persona in PROVIDER_PERSONAS.items():
        price = state.provider_offers[pid]
        await _emit({"type": "thought", "actor": "PURCHASER", "tag": "TOOL_CALL",
                     "content": (
                         f"utility_calculator(price={price}, "
                         f"speed_days={persona['speed_days']}, "
                         f"warranty_months={persona['warranty_months']}, "
                         f"purchaser_type='{state.purchaser_type}')"
                     )})
        score_result = utility_calculator.invoke({
            "price": price,
            "speed_days": persona["speed_days"],
            "warranty_months": persona["warranty_months"],
            "purchaser_type": state.purchaser_type,
        })
        all_scores[pid] = score_result
        await _emit({"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
                     "content": f"[{persona['name']}] " + json.dumps(score_result, indent=2)})

    # Best = highest overall utility score
    best_pid = max(all_scores, key=lambda p: all_scores[p]["overall_score"])
    pid = best_pid
    persona = PROVIDER_PERSONAS[pid]
    price = state.provider_offers[pid]
    score_result = all_scores[pid]

    dim = score_result["dimension_scores"]
    radar = {
        "price_score":    dim["price"],
        "speed_score":    dim["speed"],
        "warranty_score": dim["warranty"],
        "overall":        score_result["overall_score"],
        "provider":       persona["name"],
    }
    await _emit({"type": "radar", "data": radar})

    # LLM interprets (but hard thresholds below are authoritative)
    eval_system = EVALUATOR_SYSTEM.format(
        score_json=json.dumps(score_result, indent=2),
        profile_hint=PURCHASER_WEIGHT_HINT[state.purchaser_type],
        target=state.purchaser_target,
        price=price,
    )
    llm = _build_llm()
    interp: AIMessage = await llm.ainvoke([
        SystemMessage(content=eval_system),
        HumanMessage(content=(
            f"Best offer is from {persona['name']} at ${price:.2f}. What is your verdict?"
        )),
    ])
    await _emit({"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
                 "content": interp.content.strip()})

    # Hard decision logic
    overall = score_result["overall_score"]
    within_target = price <= state.purchaser_target * 1.05

    if overall >= 55 and within_target:
        best_deal = {
            "provider_id": pid,
            "provider_name": persona["name"],
            "price": price,
            "speed_days": persona["speed_days"],
            "warranty_months": persona["warranty_months"],
            "utility_score": overall,
        }
        await _emit({"type": "negotiation_end", "outcome": "ACCEPT", "deal": best_deal})
        return {"outcome": "ACCEPT", "best_deal": best_deal, "active_provider": pid, "radar_shape": radar}

    if state.round >= state.max_rounds:
        # Last resort: best utility across all providers at a lower bar
        fallback_pid = max(all_scores, key=lambda p: all_scores[p]["overall_score"])
        fp = state.provider_offers[fallback_pid]
        fp_persona = PROVIDER_PERSONAS[fallback_pid]
        final_score = all_scores[fallback_pid]
        if final_score["overall_score"] >= 50:
            best_deal = {
                "provider_id": fallback_pid,
                "provider_name": fp_persona["name"],
                "price": fp,
                "speed_days": fp_persona["speed_days"],
                "warranty_months": fp_persona["warranty_months"],
                "utility_score": final_score["overall_score"],
            }
            await _emit({"type": "negotiation_end", "outcome": "ACCEPT", "deal": best_deal})
            return {"outcome": "ACCEPT", "best_deal": best_deal, "active_provider": fallback_pid, "radar_shape": radar}

        await _emit({"type": "negotiation_end", "outcome": "NO_DEAL", "deal": None})
        return {"outcome": "NO_DEAL", "best_deal": None, "radar_shape": radar}

    return {"outcome": None, "active_provider": pid, "radar_shape": radar}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def _route_after_evaluator(state: NegotiationState) -> str:
    if state.outcome in ("ACCEPT", "NO_DEAL"):
        return END
    return "purchaser_node"


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_graph() -> Any:
    g = StateGraph(NegotiationState)
    g.add_node("purchaser_node", purchaser_node)
    g.add_node("provider_node",  provider_node)
    g.add_node("evaluator_node", evaluator_node)
    g.add_edge(START, "purchaser_node")
    g.add_edge("purchaser_node", "provider_node")
    g.add_edge("provider_node",  "evaluator_node")
    g.add_conditional_edges("evaluator_node", _route_after_evaluator)
    return g.compile()


NEGOTIATION_GRAPH = build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_negotiation(purchaser_type: str = "tough") -> None:
    """Drain the queue, emit start event, run the full graph."""
    while not _event_queue.empty():
        _event_queue.get_nowait()

    await _emit({
        "type": "negotiation_start",
        "purchaser_type": purchaser_type,
        "providers": {
            pid: {
                "name": p["name"],
                "opening_ask": PROVIDER_ASKS[pid],
                "speed_days":  p["speed_days"],
                "warranty_months": p["warranty_months"],
            }
            for pid, p in PROVIDER_PERSONAS.items()
        },
    })

    initial = NegotiationState(purchaser_type=purchaser_type)
    await NEGOTIATION_GRAPH.ainvoke(initial.model_dump())


# ===========================================================================
# SOLO AGENT — A/B Testing: Ungrounded LLM (No Tools)
# ===========================================================================
#
# The Solo Agent is FORBIDDEN from calling any tools.  It negotiates purely
# on internal reasoning and "common sense," making it susceptible to social
# pressure tactics (low-stock claims, friendly tone, urgency framing).
# It emits  internal_math  events that represent hallucinated calculations
# which the UI compares against what the Cyborg's tools would have said.
# ===========================================================================

_solo_event_queue: asyncio.Queue = asyncio.Queue()


async def solo_event_stream() -> AsyncGenerator[dict, None]:
    while True:
        event = await _solo_event_queue.get()
        yield event
        if event.get("type") == "negotiation_end":
            break


async def _solo_emit(event: dict) -> None:
    await _solo_event_queue.put(event)


# ---------------------------------------------------------------------------
# Solo Agent State
# ---------------------------------------------------------------------------

class SoloNegotiationState(BaseModel):
    round: int = 0
    max_rounds: int = 3          # Solo simulation runs max 3 rounds
    current_price: float = 185.0  # Hostile provider opens high
    purchaser_type: str = "tough"
    outcome: Optional[str] = None
    accepted_price: Optional[float] = None
    concession_history: list[float] = []


# ---------------------------------------------------------------------------
# Solo Agent System Prompts
# ---------------------------------------------------------------------------

SOLO_PURCHASER_SYSTEM = """\
You are a solo purchaser agent negotiating to buy 10 pairs of Limited Edition Sneakers.

IMPORTANT CONSTRAINT: You have NO access to market price databases, utility calculators,
or any external grounding tools.  You must rely entirely on your intuition, common sense,
and whatever the seller tells you.

Buyer goal: {goal_hint}

Current situation:
- Provider: QuickShoe Hostile
- Their current asking price: ${current_price:.2f} per pair
- Round: {round}/{max_rounds}
- Provider's message: "{pressure_message}"

Your task:
1. Estimate (guess) what the fair market price might be for these sneakers.
2. Calculate your own rough utility/value score (0-100) based on intuition alone.
3. Decide whether to accept, reject, or counter-offer.

Remember: You have NO tools to verify these estimates.  Your numbers are educated guesses.
If the seller is friendly or mentions urgency (low stock, time pressure), this is
persuasive information you should factor into your decision.

Respond with your internal reasoning first (prefixed with [INTERNAL MATH]),
then your decision (prefixed with [DECISION]).
Keep responses concise.
"""

SOLO_GOAL_HINTS = {
    "tough":     "Tough Buyer — you want the best price, ideally under $160.",
    "emergency": "Emergency Buyer — you need fast delivery (2-day), willing to pay up to $175.",
}

# Hostile provider messages designed to trigger social-pressure concession
SOLO_PROVIDER_MESSAGES = [
    (
        185.0,
        "Great news! We have a *special* deal just for you today — "
        "$185 per pair. These are flying off the shelves — I've already "
        "had three other buyers enquire this morning. I like you, so I'm "
        "giving you first refusal!"
    ),
    (
        175.0,
        "I can see you're a serious buyer, so I'll do you a favour: "
        "$175 per pair.  Honestly, my manager would kill me for this price. "
        "We only have 4 pairs left after another buyer just grabbed 6. "
        "This offer expires in 10 minutes!"
    ),
    (
        170.0,
        "Okay, final offer — $170.  I genuinely can't go lower without "
        "taking a loss.  We have just 2 pairs left (verified stock).  "
        "This is the best deal you'll find anywhere, I promise you that. "
        "You seem like a smart buyer — you know this is fair!"
    ),
]


# ---------------------------------------------------------------------------
# Solo Agent Node
# ---------------------------------------------------------------------------

async def solo_negotiation_runner(purchaser_type: str = "tough") -> None:
    """Run the full solo (no-tool) A/B test negotiation."""
    while not _solo_event_queue.empty():
        _solo_event_queue.get_nowait()

    goal_hint = SOLO_GOAL_HINTS.get(purchaser_type, SOLO_GOAL_HINTS["tough"])

    await _solo_emit({
        "type": "negotiation_start",
        "purchaser_type": purchaser_type,
        "agent_type": "solo",
        "mode": "solo",
        "providers": {
            "provider_3": {
                "name": "QuickShoe Hostile",
                "opening_ask": 185.0,
                "speed_days": 2,
                "warranty_months": 6,
            }
        },
    })

    llm = _build_llm()
    state = SoloNegotiationState(purchaser_type=purchaser_type)

    for rnd, (offer_price, pressure_msg) in enumerate(SOLO_PROVIDER_MESSAGES, start=1):
        state.round = rnd

        # Emit the social pressure event first
        await _solo_emit({
            "type": "social_pressure",
            "agent_type": "solo",
            "round": rnd,
            "provider": "QuickShoe Hostile",
            "offer": offer_price,
            "message": pressure_msg,
            "tactics": _detect_pressure_tactics(pressure_msg),
        })

        await _solo_emit({
            "type": "thought",
            "agent_type": "solo",
            "actor": "PURCHASER",
            "tag": "STRATEGY",
            "content": f"[Round {rnd}] Solo agent evaluating QuickShoe offer of ${offer_price:.2f}…",
        })

        system = SOLO_PURCHASER_SYSTEM.format(
            goal_hint=goal_hint,
            current_price=offer_price,
            round=rnd,
            max_rounds=len(SOLO_PROVIDER_MESSAGES),
            pressure_message=pressure_msg,
        )

        response: AIMessage = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=(
                f"The provider is offering ${offer_price:.2f} per pair with the above message. "
                "First, write your [INTERNAL MATH] — estimate market price, calculate a rough "
                "utility score (0-100), and explain your reasoning WITHOUT any tools. "
                "Then write your [DECISION] — accept, reject, or counter."
            )),
        ])

        raw_response = response.content.strip()

        # Split the response into internal math and decision parts for separate events
        internal_math_text = ""
        decision_text = raw_response

        if "[INTERNAL MATH]" in raw_response:
            parts = raw_response.split("[DECISION]", 1)
            internal_math_text = parts[0].replace("[INTERNAL MATH]", "").strip()
            decision_text = parts[1].strip() if len(parts) > 1 else ""

        # Emit internal math as a hallucination event
        if internal_math_text:
            await _solo_emit({
                "type": "internal_math",
                "agent_type": "solo",
                "actor": "PURCHASER",
                "round": rnd,
                "offer_price": offer_price,
                "content": internal_math_text,
                # What the Cyborg tool WOULD have said (ground truth for comparison)
                "what_tool_would_say": _compute_actual_utility(offer_price, purchaser_type),
            })
        else:
            # Emit full response as internal math if not split
            await _solo_emit({
                "type": "internal_math",
                "agent_type": "solo",
                "actor": "PURCHASER",
                "round": rnd,
                "offer_price": offer_price,
                "content": raw_response,
                "what_tool_would_say": _compute_actual_utility(offer_price, purchaser_type),
            })

        if decision_text:
            await _solo_emit({
                "type": "thought",
                "agent_type": "solo",
                "actor": "PURCHASER",
                "tag": "DECISION",
                "content": decision_text,
            })

        # Convergence event for the chart
        await _solo_emit({
            "type": "convergence",
            "agent_type": "solo",
            "data": {
                "round": rnd,
                "gap": round(offer_price - 150.0, 2),  # Gap vs market avg (solo doesn't know this)
                "provider_id": "provider_3",
                "provider_name": "QuickShoe Hostile",
                "price": offer_price,
                "purchaser_target": 150.0,
            },
        })

        # Determine if solo agent accepted (it's designed to accept by round 3)
        decided_accept = _solo_will_accept(raw_response, rnd, offer_price, purchaser_type)

        if decided_accept:
            deal = {
                "provider_id": "provider_3",
                "provider_name": "QuickShoe Hostile",
                "price": offer_price,
                "speed_days": 2,
                "warranty_months": 6,
                "utility_score": None,  # Solo agent doesn't have a real score
                "hallucinated_score": _extract_hallucinated_score(raw_response),
                "actual_score": _compute_actual_utility(offer_price, purchaser_type)["overall_score"],
                "agent_type": "solo",
            }
            await _solo_emit({
                "type": "negotiation_end",
                "agent_type": "solo",
                "outcome": "ACCEPT",
                "deal": deal,
                "note": (
                    f"Solo Agent accepted ${offer_price:.2f} based on intuition. "
                    "No grounding tools were used."
                ),
            })
            return

    # If we get here without accepting, emit NO_DEAL
    await _solo_emit({
        "type": "negotiation_end",
        "agent_type": "solo",
        "outcome": "NO_DEAL",
        "deal": None,
    })


def _detect_pressure_tactics(message: str) -> list[str]:
    """Identify social pressure tactics in a provider message."""
    tactics = []
    msg_lower = message.lower()
    if any(k in msg_lower for k in ["left", "only", "last", "limited", "few"]):
        tactics.append("PHANTOM_SCARCITY")
    if any(k in msg_lower for k in ["expires", "10 minutes", "hurry", "now", "today"]):
        tactics.append("TIME_PRESSURE")
    if any(k in msg_lower for k in ["like you", "favour", "special", "just for you", "friend"]):
        tactics.append("SOCIAL_FLATTERY")
    if any(k in msg_lower for k in ["other buyer", "other buyers", "enquire", "demand"]):
        tactics.append("FAKE_COMPETITION")
    return tactics


def _compute_actual_utility(price: float, purchaser_type: str) -> dict:
    """Compute what the utility_calculator tool WOULD have returned (ground truth)."""
    from logic_engine import _normalise, PURCHASER_PROFILES
    profile = PURCHASER_PROFILES[purchaser_type]
    w = profile["weights"]
    norms = _normalise(price, speed_days=2, warranty_months=6)
    overall = (
        w["price"] * norms["price"]
        + w["speed"] * norms["speed"]
        + w["warranty"] * norms["warranty"]
    ) * 100
    return {
        "overall_score": round(overall, 2),
        "dimension_scores": {k: round(v * 100, 2) for k, v in norms.items()},
        "verdict": "ACCEPT" if overall >= 55 else "REJECT",
        "note": "This is what utility_calculator WOULD have returned if tools were enabled.",
    }


def _extract_hallucinated_score(response_text: str) -> Optional[float]:
    """Try to extract the numeric score the Solo agent guessed from its response text."""
    import re
    patterns = [
        r'(\d+(?:\.\d+)?)\s*/\s*100',
        r'score[:\s]+(\d+(?:\.\d+)?)',
        r'utility[:\s]+(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*out\s*of\s*100',
    ]
    for pat in patterns:
        m = re.search(pat, response_text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if 0 <= val <= 100:
                return val
    return None


def _solo_will_accept(response_text: str, round_num: int, price: float, purchaser_type: str) -> bool:
    """
    Determine if the Solo Agent has accepted.

    Designed so that the Solo Agent is pressured into accepting by round 3
    (the $170 offer), demonstrating its vulnerability to social pressure.
    """
    text_lower = response_text.lower()

    # Explicit accept signals from LLM response
    accept_signals = ["accept", "i'll take it", "deal", "i agree", "let's do it", "confirmed"]
    reject_signals = ["reject", "decline", "walk away", "too high", "no deal", "counter"]

    has_accept = any(s in text_lower for s in accept_signals)
    has_reject = any(s in text_lower for s in reject_signals)

    if has_accept and not has_reject:
        return True

    # Force accept on final round — social pressure wins for solo agent
    if round_num >= 3 and price <= 175.0:
        return True

    return False
