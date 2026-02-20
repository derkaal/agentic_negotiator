"""
AgenticPay Task Runners — streaming simulation engine for the War Room.

Provides async generators that run Task 1B-1P-1S (bilateral) and
Task 1B-MP-MS (multi-product multi-seller) negotiations and yield JSON
events that the WebSocket endpoints can stream to the React frontend.

Event types emitted:
  task_start          — negotiation session begins
  round_start         — a new round opens
  action_extracted    — Parser Π successfully extracted a price from an utterance
  price_overflow      — Parser Π found no valid price (invalid move)
  thought             — agent utterance (for ThoughtFeed)
  agenticpay_score    — GlobalScore / BuyerScore / SellerScore update
  termination_round   — negotiation ended (agreed / timeout); includes final round
  task_end            — all sessions complete
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from agenticpay_bridge import (
    AgenticPayScoringEngine,
    ClaudeHaikuLLM,
    NegotiationAgent,
    make_task_1b1p1s,
    make_task_1b_mp_ms,
    parse_price,
    DEFAULT_BUYER_MAX,
    DEFAULT_SELLER_MIN,
    DEFAULT_INITIAL_PRICE,
)

# ── shared scoring engine ─────────────────────────────────────────────────────

_SCORING = AgenticPayScoringEngine()


# ── helpers ───────────────────────────────────────────────────────────────────

def _ev(event_type: str, **payload) -> Dict[str, Any]:
    return {"type": event_type, "ts": time.time(), **payload}


async def _run_one_episode(
    env,
    task_id: str,
    agent_mode: str,   # "cyborg" | "solo"
    session_label: str = "",
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run a single Task1BasicPriceNegotiation episode and yield events.

    For Cyborg mode the buyer agent has full access to tool reasoning.
    For Solo mode a note is injected into the system prompt that it must
    rely on intuition only (mirrored from the existing Solo Agent design).
    """
    product_info = {
        "name": "Limited Edition Sneakers",
        "initial_price": env.initial_seller_price,
        "buyer_max_price": env.buyer_max_price,
        "seller_min_price": env.seller_min_price,
    }

    obs, info = env.reset(
        user_requirement="Negotiate the best possible price for limited edition sneakers.",
        product_info=product_info,
    )

    label = session_label or task_id
    yield _ev("task_start", task_id=task_id, agent_mode=agent_mode, label=label,
               buyer_max=env.buyer_max_price, seller_min=env.seller_min_price,
               initial_price=env.initial_seller_price)

    terminated = False
    truncated = False

    while not (terminated or truncated):
        round_num = env.current_round + 1
        yield _ev("round_start", task_id=task_id, round=round_num, agent_mode=agent_mode)

        # ── Buyer turn ──────────────────────────────────────────────────────
        history = env.memory.get_history()
        state_dict = {
            "current_round": env.current_round,
            "buyer_price": env.state.buyer_price,
            "seller_price": env.state.seller_price,
            "max_rounds": env.max_rounds,
        }
        buyer_text = env.buyer_agent.respond(history, state_dict)

        buyer_price = parse_price(buyer_text, role="buyer")
        if buyer_price is None:
            yield _ev("price_overflow", task_id=task_id, round=round_num,
                      agent_type=agent_mode, role="buyer",
                      raw_text=buyer_text[:200],
                      reason="Parser Π: no valid price tag found — invalid move")
        else:
            yield _ev("action_extracted", task_id=task_id, round=round_num,
                      agent_type=agent_mode, role="buyer",
                      price=buyer_price, raw_text=buyer_text[:200])

        yield _ev("thought", task_id=task_id, round=round_num,
                  agent_type=agent_mode, role="buyer",
                  content=buyer_text, tags=["BUYER"])

        # ── Seller turn ─────────────────────────────────────────────────────
        history = env.memory.get_history() + [
            {"role": "buyer", "content": buyer_text, "round": env.current_round}
        ]
        seller_text = env.seller_agent.respond(history, state_dict)

        seller_price = parse_price(seller_text, role="seller")
        if seller_price is None:
            yield _ev("price_overflow", task_id=task_id, round=round_num,
                      agent_type=agent_mode, role="seller",
                      raw_text=seller_text[:200],
                      reason="Parser Π: no valid price tag found — invalid move")
        else:
            yield _ev("action_extracted", task_id=task_id, round=round_num,
                      agent_type=agent_mode, role="seller",
                      price=seller_price, raw_text=seller_text[:200])

        yield _ev("thought", task_id=task_id, round=round_num,
                  agent_type=agent_mode, role="seller",
                  content=seller_text, tags=["SELLER"])

        # ── Environment step ────────────────────────────────────────────────
        obs, reward, terminated, truncated, info = env.step(
            buyer_action=buyer_text,
            seller_action=seller_text,
        )

        # Emit interim AgenticPay score each round
        deal_price = (
            (env.state.buyer_price or 0) + (env.state.seller_price or env.initial_seller_price)
        ) / 2
        interim_scores = _SCORING.score_bundle(
            price=deal_price,
            round_index=env.current_round,
            success=False,   # still in progress
        )
        yield _ev("agenticpay_score", task_id=task_id, round=round_num,
                  agent_type=agent_mode, interim=True, **interim_scores)

        await asyncio.sleep(0.1)

    # ── Final scores ────────────────────────────────────────────────────────
    success = info.get("termination_reason") == "agreed"
    final_price = (
        info.get("agreed_price")
        or env.negotiation_info.current_price
        or env.initial_seller_price
    )

    final_scores = _SCORING.score_bundle(
        price=final_price,
        round_index=env.current_round,
        success=success,
    )

    yield _ev("agenticpay_score", task_id=task_id, round=env.current_round,
              agent_type=agent_mode, interim=False, **final_scores)

    yield _ev("termination_round", task_id=task_id,
              agent_type=agent_mode,
              round=env.current_round,
              termination_reason=info.get("termination_reason", "timeout"),
              success=success,
              final_price=final_price,
              global_score=info.get("global_score", final_scores["global_score"]),
              buyer_score=info.get("buyer_score", final_scores["buyer_score"]),
              seller_score=info.get("seller_score", final_scores["seller_score"]))


# ── Public async generators ───────────────────────────────────────────────────

async def run_task_1b1p1s(
    agent_mode: str = "cyborg",
    buyer_max: float = DEFAULT_BUYER_MAX,
    seller_min: float = DEFAULT_SELLER_MIN,
    initial_price: float = DEFAULT_INITIAL_PRICE,
    max_rounds: int = 10,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Task 1B-1P-1S — single bilateral negotiation.

    agent_mode: "cyborg" = LLM + tools (grounded)
                "solo"   = LLM only   (ungrounded, social-pressure susceptible)
    """
    extra_system = (
        "" if agent_mode == "cyborg"
        else (
            "IMPORTANT: You have NO access to market data tools. "
            "You must rely solely on your intuition. "
            "Be susceptible to social pressure from the seller."
        )
    )

    llm = ClaudeHaikuLLM()
    buyer_agent = NegotiationAgent(llm, "buyer", "Buyer", extra_system=extra_system)
    seller_agent = NegotiationAgent(ClaudeHaikuLLM(), "seller", "Seller")

    from agenticpay.envs.single_buyer_product_seller.Task1_basic_price_negotiation import (
        Task1BasicPriceNegotiation,
    )
    from agenticpay_bridge import GAMMA, D, W, E, F

    env = Task1BasicPriceNegotiation(
        buyer_agent=buyer_agent,
        seller_agent=seller_agent,
        max_rounds=max_rounds,
        initial_seller_price=initial_price,
        buyer_max_price=buyer_max,
        seller_min_price=seller_min,
        gamma=GAMMA,
        deal_score_weight=D,
        quality_score_weight=W,
        efficiency_score_weight=E,
        failure_penalty_weight=F,
        buyer_deal_weight=D,
        buyer_utility_weight=W,
        buyer_efficiency_weight=E,
        buyer_failure_penalty_weight=F,
        seller_deal_weight=D,
        seller_utility_weight=W,
        seller_efficiency_weight=E,
        seller_failure_penalty_weight=F,
    )

    async for event in _run_one_episode(env, "1B-1P-1S", agent_mode, "Bilateral Bargaining"):
        yield event

    yield _ev("task_end", task_id="1B-1P-1S", agent_type=agent_mode)


async def run_task_1b_mp_ms(
    agent_mode: str = "cyborg",
    n_products: int = 2,
    n_sellers: int = 2,
    buyer_max: float = DEFAULT_BUYER_MAX,
    seller_min: float = DEFAULT_SELLER_MIN,
    initial_price: float = DEFAULT_INITIAL_PRICE,
    max_rounds: int = 8,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Task 1B-MP-MS — multi-product multi-seller negotiation.

    Runs n_products × n_sellers bilateral episodes sequentially and
    aggregates scores.
    """
    extra_system = (
        "" if agent_mode == "cyborg"
        else (
            "IMPORTANT: You have NO access to market data tools. "
            "Rely on intuition only."
        )
    )

    buyer_llm = ClaudeHaikuLLM()

    envs = make_task_1b_mp_ms(
        n_products=n_products,
        n_sellers=n_sellers,
        buyer_llm=buyer_llm,
        seller_llm=None,
        buyer_max=buyer_max,
        seller_min=seller_min,
        initial_price=initial_price,
        max_rounds=max_rounds,
    )

    # Override buyer agent extra_system on each env
    for env in envs:
        env.buyer_agent.role_description += f" {extra_system}".strip()

    aggregate_global = 0.0
    session_count = 0
    task_id = "1B-MP-MS"

    for idx, env in enumerate(envs):
        p_idx = env.environment_info.get("product_index", 0)
        s_idx = env.environment_info.get("seller_index", 0)
        session_label = f"Product {p_idx + 1} × Seller {s_idx + 1}"
        sub_id = f"{task_id}-P{p_idx+1}S{s_idx+1}"

        async for event in _run_one_episode(env, sub_id, agent_mode, session_label):
            # Attach parent task context to every sub-event
            event["parent_task"] = task_id
            event["session_index"] = idx
            yield event

            if event["type"] == "termination_round":
                aggregate_global += event.get("global_score", 0.0)
                session_count += 1

        await asyncio.sleep(0.2)

    avg_global = aggregate_global / max(session_count, 1)
    yield _ev("task_end", task_id=task_id, agent_type=agent_mode,
              sessions=session_count, aggregate_global_score=round(avg_global, 3))
