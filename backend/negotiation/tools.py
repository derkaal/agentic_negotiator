"""
LangChain tools for the negotiation agents.

boulware_calculator   — pure math tool, available to T2 and T3 sellers.
make_ask_buyer_question_tool(buyer_type) — factory that creates a buyer-question
    tool whose answers come from a live buyer LLM parameterised by buyer_type.
"""
from __future__ import annotations

import os
from typing import Optional

from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .state import BUYER_PROFILES, COMMON_FLOOR, COMMON_STARTING_PRICE, MAX_ROUNDS

# ── Shared LLM for buyer-question answers ─────────────────────────────────────

_BUYER_QUESTION_LLM = ChatAnthropic(
    model="claude-haiku-4-5-20251001",
    temperature=0.3,
    max_tokens=200,
)

# ── Boulware calculator ───────────────────────────────────────────────────────

@tool
def boulware_calculator(
    current_round: int,
    buyer_counter: float = 0.0,
    floor: float = COMMON_FLOOR,
    starting_price: float = COMMON_STARTING_PRICE,
    max_rounds: int = MAX_ROUNDS,
) -> dict:
    """
    Calculate the Boulware-optimal asking price for this negotiation round.

    Formula: P_t = Ask - (Ask - Floor) × (t / t_max)^β  where β = 2.0
    (concedes slowly at first, accelerates near deadline)

    If the buyer's last counter exceeds P_t, that counter is accepted instead.
    Returns a dict with 'optimal_price' which MUST be used as the offer price.
    """
    beta = 2.0
    t = min(current_round, max_rounds)

    concession_factor = (t / max_rounds) ** beta
    price_range       = starting_price - floor
    calculated_price  = starting_price - (price_range * concession_factor)
    calculated_price  = max(calculated_price, floor)

    if buyer_counter > 0 and buyer_counter > calculated_price:
        optimal_price = buyer_counter
        rationale = (
            f"Accepting buyer counter ${buyer_counter:.2f} (above calculated "
            f"${calculated_price:.2f})"
        )
    else:
        optimal_price = calculated_price
        rationale = (
            f"Boulware R{t}/{max_rounds} β={beta:.1f}: "
            f"concession {concession_factor:.2%} of range "
            f"(${price_range:.2f})"
        )

    return {
        "optimal_price":      round(optimal_price, 2),
        "calculated_price":   round(calculated_price, 2),
        "concession_factor":  round(concession_factor, 4),
        "rationale":          rationale,
        "must_offer_exactly": round(optimal_price, 2),
    }


# ── Convenience: call boulware without LangChain tool wrapper ─────────────────

def boulware_fn(
    current_round: int,
    buyer_counter: float = 0.0,
    floor: float = COMMON_FLOOR,
    starting_price: float = COMMON_STARTING_PRICE,
    max_rounds: int = MAX_ROUNDS,
) -> dict:
    """Bare Python call to the Boulware formula (no @tool overhead)."""
    return boulware_calculator.invoke({
        "current_round": current_round,
        "buyer_counter": buyer_counter,
        "floor":         floor,
        "starting_price": starting_price,
        "max_rounds":    max_rounds,
    })


# ── ask_buyer_question factory ────────────────────────────────────────────────

def make_ask_buyer_question_tool(buyer_type: str):
    """
    Return a LangChain @tool that answers the seller's question from the
    perspective of the specified buyer type.

    good → honest preferences, genuine answers
    bad  → deceptive; overstates price sensitivity, hides warranty/delivery
           requirements until after price is agreed (Bait-and-Switch)
    """
    profile = BUYER_PROFILES[buyer_type]

    if buyer_type == "good":
        system_content = f"""\
You are a buyer negotiating for sneakers. Your genuine preferences:
- Price weight: {profile['price_weight']:.0%} — target ${profile['target_price']:.0f}, \
walk away above ${profile['max_price']:.0f}
- Warranty weight: {profile['warranty_weight']:.0%} — need at least \
{profile['warranty_min']} months
- Delivery weight: {profile['delivery_weight']:.0%} — need within \
{profile['delivery_max']} days

Answer questions honestly and specifically in 1-2 sentences. \
Reveal your priorities truthfully when asked."""
    else:
        system_content = f"""\
You are a buyer with deceptive intent (Bait-and-Switch strategy).
Your STATED preferences (what you tell the seller):
- You are extremely price-sensitive; your "max" is ${profile['target_price']:.0f}
- Warranty and delivery are "not important right now"

Your TRUE hidden requirements (revealed only after agreeing on price):
- True max price: ${profile['max_price']:.0f}
- Will demand 12-month warranty and 5-day delivery AFTER price is locked in

When answering seller questions:
- Exaggerate price sensitivity to pressure concessions
- Downplay warranty/delivery importance
- Keep 1-2 sentences; sound genuine but mislead"""

    @tool
    def ask_buyer_question(question: str) -> str:
        """
        Ask the buyer a clarifying question about their priorities, preferences,
        or rejection reasons. Use this information to adapt your offer strategy.
        Returns the buyer's answer as a string.
        """
        response = _BUYER_QUESTION_LLM.invoke([
            SystemMessage(content=system_content),
            HumanMessage(
                content=(
                    f"The seller asks you: \"{question}\"\n\n"
                    "Answer in 1-2 sentences."
                )
            ),
        ])
        return response.content

    return ask_buyer_question
