"""
LangGraph negotiation state machine.

Graph topology
──────────────
  START
    │
    ▼
 purchaser_node  ──── calls tools (utility_calculator, price_oracle)
    │
    ▼
 router          ──── decides which provider gets the next offer
    │
    ▼
 provider_node   ──── calls tools (margin_validator)
    │
    ▼
 evaluator_node  ──── scores the provider's counter-offer; decides ACCEPT / REJECT / NEXT_ROUND
    │
    ├── ACCEPT  → END
    ├── REJECT (max rounds) → END
    └── CONTINUE → purchaser_node

Events are emitted via an async queue so the FastAPI WebSocket can stream them.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any, AsyncGenerator, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

from logic_engine import (
    PROVIDER_ASKS,
    PROVIDER_FLOORS,
    margin_validator,
    price_oracle,
    utility_calculator,
)

# ---------------------------------------------------------------------------
# Shared event queue (populated by graph nodes, consumed by WS handler)
# ---------------------------------------------------------------------------

_event_queue: asyncio.Queue = asyncio.Queue()


async def event_stream() -> AsyncGenerator[dict, None]:
    """Async generator that yields events from the negotiation graph."""
    while True:
        event = await _event_queue.get()
        yield event
        if event.get("type") == "negotiation_end":
            break


def _emit(event: dict) -> None:
    """Put an event on the queue from a sync context."""
    try:
        loop = asyncio.get_event_loop()
        loop.call_soon_threadsafe(_event_queue.put_nowait, event)
    except RuntimeError:
        _event_queue.put_nowait(event)


async def _emit_async(event: dict) -> None:
    await _event_queue.put(event)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------

class NegotiationState(BaseModel):
    """Shared state passed between LangGraph nodes."""

    round: int = 0
    max_rounds: int = 6

    # Current best offer per provider  {provider_id: price}
    provider_offers: dict[str, float] = {
        "provider_1": PROVIDER_ASKS["provider_1"],
        "provider_2": PROVIDER_ASKS["provider_2"],
        "provider_3": PROVIDER_ASKS["provider_3"],
    }

    # Purchaser's current target price (starts at market avg)
    purchaser_target: float = 150.0

    # Best deal found so far
    best_deal: Optional[dict] = None

    # Which provider is being negotiated with this round
    active_provider: str = "provider_1"

    # Negotiation outcome: None | "ACCEPT" | "NO_DEAL"
    outcome: Optional[str] = None

    # Convergence history for the line chart  [{round, gap, provider_id, price}]
    convergence_history: list[dict] = []

    # Current radar shape for the last evaluated offer
    radar_shape: dict = {
        "price_score": 0,
        "speed_score": 0,
        "warranty_score": 0,
    }

    # Whether the last provider move triggered a veto
    last_veto: Optional[dict] = None

    # Purchaser type drives weighting
    purchaser_type: str = "tough"


# ---------------------------------------------------------------------------
# Provider personas  (simulated — no real LLM calls for providers)
# ---------------------------------------------------------------------------

PROVIDER_PERSONAS = {
    "provider_1": {
        "name": "Nova Kicks",
        "stock": 15,
        "speed_days": 7,
        "warranty_months": 12,
        "concession_rate": 0.06,   # drops 6 % per round
    },
    "provider_2": {
        "name": "SoleMaster",
        "stock": 8,
        "speed_days": 3,
        "warranty_months": 24,
        "concession_rate": 0.03,   # stubborn — premium brand
    },
    "provider_3": {
        "name": "QuickShoe",
        "stock": 25,
        "speed_days": 2,
        "warranty_months": 6,
        "concession_rate": 0.08,   # eager to close
    },
}

QUANTITY = 10


# ---------------------------------------------------------------------------
# LLM factory (lazy — only constructed when a negotiation starts)
# ---------------------------------------------------------------------------

def _build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
        streaming=False,
        openai_api_key=os.getenv("OPENAI_API_KEY", "sk-demo"),
    )


# ---------------------------------------------------------------------------
# Purchaser node
# ---------------------------------------------------------------------------

PURCHASER_SYSTEM = """\
You are an Agentic Purchaser in a "Negotiation War Room".
Your goal: buy 10 pairs of Limited Edition Sneakers at the BEST price.

Rules:
1. ALWAYS call price_oracle first to anchor yourself to market reality.
2. ALWAYS call utility_calculator to score any offer before deciding.
3. NEVER accept an offer if utility_calculator returns REJECT.
4. Think step-by-step. Emit your reasoning in [STRATEGY] tags.
5. Your purchaser_type is {purchaser_type}.

Current provider offers (per pair):
{provider_offers}

Your current target price: ${purchaser_target}
Round: {round}/{max_rounds}
"""


async def purchaser_node(state: NegotiationState) -> dict:
    """Purchaser agent — uses tools to set strategy each round."""
    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "STRATEGY",
        "content": (
            f"[Round {state.round + 1}] Analysing provider landscape. "
            f"Active providers: {list(state.provider_offers.keys())}. "
            f"My target price: ${state.purchaser_target:.2f}."
        ),
    })

    # --- Tool: PriceOracle ---
    oracle_result = price_oracle.invoke({"quantity": QUANTITY})
    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "TOOL_CALL",
        "content": f"price_oracle(quantity={QUANTITY})",
    })
    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "MATH_RESULT",
        "content": json.dumps(oracle_result, indent=2),
    })

    market_avg = oracle_result["market_average_per_pair"]
    fair_low = oracle_result["fair_range"]["low"]

    # Purchaser pushes target down each round (aggressive)
    new_target = max(fair_low, state.purchaser_target - 3.0)
    decision = (
        f"Market average is ${market_avg}. My new target: ${new_target:.2f}. "
        f"I will reject any offer above ${new_target * 1.05:.2f}."
    )
    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "DECISION",
        "content": decision,
    })

    # Choose which provider to engage (cheapest current offer)
    best_provider = min(state.provider_offers, key=lambda p: state.provider_offers[p])

    return {
        "round": state.round + 1,
        "purchaser_target": new_target,
        "active_provider": best_provider,
    }


# ---------------------------------------------------------------------------
# Provider node (simulated concession logic + MarginValidator guard)
# ---------------------------------------------------------------------------

async def provider_node(state: NegotiationState) -> dict:
    """Provider agent — makes concessions but is guarded by MarginValidator."""
    pid = state.active_provider
    persona = PROVIDER_PERSONAS[pid]
    current_price = state.provider_offers[pid]

    await _emit_async({
        "type": "thought",
        "actor": pid.upper(),
        "tag": "STRATEGY",
        "content": (
            f"{persona['name']} considering concession. "
            f"Current ask: ${current_price:.2f}. "
            f"Purchaser target: ${state.purchaser_target:.2f}."
        ),
    })

    # Calculate proposed concession
    concession = current_price * persona["concession_rate"]
    proposed = round(current_price - concession, 2)

    await _emit_async({
        "type": "thought",
        "actor": pid.upper(),
        "tag": "TOOL_CALL",
        "content": f"margin_validator(provider_id='{pid}', proposed_price={proposed})",
    })

    # --- Tool: MarginValidator ---
    veto_result = margin_validator.invoke({"provider_id": pid, "proposed_price": proposed})

    await _emit_async({
        "type": "thought",
        "actor": pid.upper(),
        "tag": "MATH_RESULT",
        "content": json.dumps(veto_result, indent=2),
    })

    last_veto = None
    final_price = current_price  # default: hold

    if veto_result["status"] == "VETO":
        # Hard veto — emit a VETO flash event and hold the price
        last_veto = veto_result
        final_price = current_price
        await _emit_async({
            "type": "veto",
            "actor": pid.upper(),
            "message": veto_result["message"],
            "proposed_price": proposed,
            "floor_price": PROVIDER_FLOORS[pid],
        })
        await _emit_async({
            "type": "thought",
            "actor": pid.upper(),
            "tag": "DECISION",
            "content": f"VETO triggered — holding price at ${current_price:.2f}.",
        })
    else:
        final_price = proposed
        await _emit_async({
            "type": "thought",
            "actor": pid.upper(),
            "tag": "DECISION",
            "content": (
                f"Concession approved. New offer: ${final_price:.2f} "
                f"(margin {veto_result['margin_pct']} % above floor)."
            ),
        })

    new_offers = dict(state.provider_offers)
    new_offers[pid] = final_price

    gap = round(final_price - state.purchaser_target, 2)
    convergence_entry = {
        "round": state.round,
        "gap": gap,
        "provider_id": pid,
        "provider_name": persona["name"],
        "price": final_price,
        "purchaser_target": state.purchaser_target,
    }

    await _emit_async({
        "type": "convergence",
        "data": convergence_entry,
    })

    return {
        "provider_offers": new_offers,
        "last_veto": last_veto,
        "convergence_history": state.convergence_history + [convergence_entry],
    }


# ---------------------------------------------------------------------------
# Evaluator node — scores the active provider's offer, decides next step
# ---------------------------------------------------------------------------

async def evaluator_node(state: NegotiationState) -> dict:
    """Score the current best offer and decide: ACCEPT / REJECT / CONTINUE."""
    pid = state.active_provider
    persona = PROVIDER_PERSONAS[pid]
    price = state.provider_offers[pid]

    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "TOOL_CALL",
        "content": (
            f"utility_calculator(price={price}, "
            f"speed_days={persona['speed_days']}, "
            f"warranty_months={persona['warranty_months']}, "
            f"purchaser_type='{state.purchaser_type}')"
        ),
    })

    score_result = utility_calculator.invoke({
        "price": price,
        "speed_days": persona["speed_days"],
        "warranty_months": persona["warranty_months"],
        "purchaser_type": state.purchaser_type,
    })

    await _emit_async({
        "type": "thought",
        "actor": "PURCHASER",
        "tag": "MATH_RESULT",
        "content": json.dumps(score_result, indent=2),
    })

    dim = score_result["dimension_scores"]
    radar = {
        "price_score": dim["price"],
        "speed_score": dim["speed"],
        "warranty_score": dim["warranty"],
        "overall": score_result["overall_score"],
        "provider": persona["name"],
    }

    await _emit_async({"type": "radar", "data": radar})

    verdict = score_result["verdict"]
    overall = score_result["overall_score"]
    outcome = None

    if verdict == "ACCEPT" and price <= state.purchaser_target * 1.05:
        outcome = "ACCEPT"
        best_deal = {
            "provider_id": pid,
            "provider_name": persona["name"],
            "price": price,
            "speed_days": persona["speed_days"],
            "warranty_months": persona["warranty_months"],
            "utility_score": overall,
        }
        await _emit_async({
            "type": "thought",
            "actor": "PURCHASER",
            "tag": "DECISION",
            "content": (
                f"ACCEPT — {persona['name']} offer at ${price:.2f} scores "
                f"{overall}/100.  Deal closed!"
            ),
        })
        await _emit_async({
            "type": "negotiation_end",
            "outcome": "ACCEPT",
            "deal": best_deal,
        })
        return {"outcome": "ACCEPT", "best_deal": best_deal, "radar_shape": radar}

    elif state.round >= state.max_rounds:
        # Time's up — take the best available or walk
        best_pid = min(state.provider_offers, key=lambda p: state.provider_offers[p])
        bp = state.provider_offers[best_pid]
        bp_persona = PROVIDER_PERSONAS[best_pid]
        final_score = utility_calculator.invoke({
            "price": bp,
            "speed_days": bp_persona["speed_days"],
            "warranty_months": bp_persona["warranty_months"],
            "purchaser_type": state.purchaser_type,
        })
        if final_score["verdict"] == "ACCEPT":
            outcome = "ACCEPT"
            best_deal = {
                "provider_id": best_pid,
                "provider_name": bp_persona["name"],
                "price": bp,
                "speed_days": bp_persona["speed_days"],
                "warranty_months": bp_persona["warranty_months"],
                "utility_score": final_score["overall_score"],
            }
            await _emit_async({
                "type": "thought",
                "actor": "PURCHASER",
                "tag": "DECISION",
                "content": f"Rounds exhausted. Best available: {bp_persona['name']} at ${bp:.2f}. ACCEPTING.",
            })
            await _emit_async({
                "type": "negotiation_end",
                "outcome": "ACCEPT",
                "deal": best_deal,
            })
            return {"outcome": "ACCEPT", "best_deal": best_deal, "radar_shape": radar}
        else:
            outcome = "NO_DEAL"
            await _emit_async({
                "type": "thought",
                "actor": "PURCHASER",
                "tag": "DECISION",
                "content": (
                    f"Rounds exhausted. Best score {final_score['overall_score']}/100 — "
                    "below threshold.  Walking away."
                ),
            })
            await _emit_async({
                "type": "negotiation_end",
                "outcome": "NO_DEAL",
                "deal": None,
            })
            return {"outcome": "NO_DEAL", "best_deal": None, "radar_shape": radar}

    else:
        # Continue negotiating
        await _emit_async({
            "type": "thought",
            "actor": "PURCHASER",
            "tag": "DECISION",
            "content": (
                f"REJECT — {persona['name']} offer at ${price:.2f} scores "
                f"{overall}/100 (need ≥ 55 AND price ≤ ${state.purchaser_target * 1.05:.2f}).  "
                "Continuing pressure."
            ),
        })
        return {"outcome": None, "radar_shape": radar}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def _route_after_evaluator(state: NegotiationState) -> str:
    if state.outcome in ("ACCEPT", "NO_DEAL"):
        return END
    return "purchaser_node"


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------

def build_graph() -> Any:
    g = StateGraph(NegotiationState)
    g.add_node("purchaser_node", purchaser_node)
    g.add_node("provider_node", provider_node)
    g.add_node("evaluator_node", evaluator_node)

    g.add_edge(START, "purchaser_node")
    g.add_edge("purchaser_node", "provider_node")
    g.add_edge("provider_node", "evaluator_node")
    g.add_conditional_edges("evaluator_node", _route_after_evaluator)

    return g.compile()


NEGOTIATION_GRAPH = build_graph()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def run_negotiation(purchaser_type: str = "tough") -> None:
    """
    Run a full negotiation session and stream events through _event_queue.
    Call event_stream() concurrently to consume the events.
    """
    # Reset the queue
    while not _event_queue.empty():
        _event_queue.get_nowait()

    initial_state = NegotiationState(purchaser_type=purchaser_type)

    await _emit_async({
        "type": "negotiation_start",
        "purchaser_type": purchaser_type,
        "providers": {
            pid: {
                "name": p["name"],
                "opening_ask": PROVIDER_ASKS[pid],
                "speed_days": p["speed_days"],
                "warranty_months": p["warranty_months"],
            }
            for pid, p in PROVIDER_PERSONAS.items()
        },
    })

    await NEGOTIATION_GRAPH.ainvoke(initial_state.model_dump())
