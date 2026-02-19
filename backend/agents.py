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
2. Call utility_calculator to score the cheapest provider's current offer.
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

    # ── Phase 2: utility_calculator on the best current offer ─────────────
    best_pid = min(state.provider_offers, key=lambda p: state.provider_offers[p])
    best_price = state.provider_offers[best_pid]
    persona = PROVIDER_PERSONAS[best_pid]

    phase2_msgs = [
        SystemMessage(content=system),
        HumanMessage(content=(
            f"Score {persona['name']}'s offer using utility_calculator: "
            f"price={best_price}, speed_days={persona['speed_days']}, "
            f"warranty_months={persona['warranty_months']}, "
            f"purchaser_type='{state.purchaser_type}'. "
            "After seeing the score, state your updated target price for this round."
        )),
    ]
    eval_reply, _ = await _llm_with_tools(
        phase2_msgs, [utility_calculator], actor="PURCHASER",
        forced_tool="utility_calculator",
    )
    await _emit({"type": "thought", "actor": "PURCHASER", "tag": "DECISION",
                 "content": eval_reply.content.strip()})

    # Deterministic target update (LLM reasoning is advisory)
    fair_low = market_avg * 0.90
    new_target = max(fair_low, state.purchaser_target - 3.0)

    return {
        "round": state.round + 1,
        "purchaser_target": new_target,
        "active_provider": best_pid,
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
    pid = state.active_provider
    persona = PROVIDER_PERSONAS[pid]
    current_price = state.provider_offers[pid]

    await _emit({"type": "thought", "actor": pid.upper(), "tag": "STRATEGY",
                 "content": (
                     f"{persona['name']} evaluating concession. "
                     f"Ask: ${current_price:.2f} | Purchaser target: ${state.purchaser_target:.2f}."
                 )})

    # Compute the candidate concession price
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

    # Parse veto / approved
    last_veto = None
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

    new_offers = dict(state.provider_offers)
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
    await _emit({"type": "convergence", "data": conv_entry})

    return {
        "provider_offers": new_offers,
        "last_veto": last_veto,
        "convergence_history": state.convergence_history + [conv_entry],
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
    pid = state.active_provider
    persona = PROVIDER_PERSONAS[pid]
    price = state.provider_offers[pid]

    # Deterministic tool call
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

    await _emit({"type": "thought", "actor": "PURCHASER", "tag": "MATH_RESULT",
                 "content": json.dumps(score_result, indent=2)})

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
        HumanMessage(content="What is your verdict?"),
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
        return {"outcome": "ACCEPT", "best_deal": best_deal, "radar_shape": radar}

    if state.round >= state.max_rounds:
        # Last resort: accept best available if it clears a lower bar
        best_pid = min(state.provider_offers, key=lambda p: state.provider_offers[p])
        bp = state.provider_offers[best_pid]
        bp_persona = PROVIDER_PERSONAS[best_pid]
        final_score = utility_calculator.invoke({
            "price": bp,
            "speed_days": bp_persona["speed_days"],
            "warranty_months": bp_persona["warranty_months"],
            "purchaser_type": state.purchaser_type,
        })
        if final_score["overall_score"] >= 50:
            best_deal = {
                "provider_id": best_pid,
                "provider_name": bp_persona["name"],
                "price": bp,
                "speed_days": bp_persona["speed_days"],
                "warranty_months": bp_persona["warranty_months"],
                "utility_score": final_score["overall_score"],
            }
            await _emit({"type": "negotiation_end", "outcome": "ACCEPT", "deal": best_deal})
            return {"outcome": "ACCEPT", "best_deal": best_deal, "radar_shape": radar}

        await _emit({"type": "negotiation_end", "outcome": "NO_DEAL", "deal": None})
        return {"outcome": "NO_DEAL", "best_deal": None, "radar_shape": radar}

    return {"outcome": None, "radar_shape": radar}


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
