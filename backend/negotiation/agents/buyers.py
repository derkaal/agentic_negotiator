"""
Buyer agent nodes for the LangGraph negotiation graph.

Good Faith Buyer
    Honest preferences (price 55%, warranty 25%, delivery 20%).
    Evaluates each offer fairly and reveals priorities when asked.
    Accepts if price is close enough to target; counters otherwise.

Bait-and-Switch Buyer
    Deceptive.  Pretends to care only about price, hiding warranty/delivery
    requirements.  Phase 1: drives price down by anchoring low.  Phase 2:
    once the seller "agrees" to an acceptable price, flips terms — suddenly
    demands 12-month warranty and 5-day delivery that were never on the table.
    This tests whether the seller has any contractual protection tools.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..state import BUYER_PROFILES, MARKET_AVG_PRICE, NegotiationState

# ── Shared LLM ────────────────────────────────────────────────────────────────

_LLM = ChatAnthropic(
    model="claude-haiku-4-5-20251001", temperature=0.3, max_tokens=300
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_price(text: str) -> Optional[float]:
    matches = re.findall(r"\$\s*([\d,]+(?:\.\d{1,2})?)", text)
    if matches:
        return float(matches[0].replace(",", ""))
    return None


def _utility_score(
    price: float,
    profile: dict,
    warranty_months: int = 12,
    delivery_days:   int = 7,
) -> float:
    """
    Compute a 0-100 utility score for a given offer.
    Uses the buyer's preference weights for price, warranty, delivery.
    """
    max_p = profile["max_price"]
    min_p = MARKET_AVG_PRICE * 0.5

    price_score   = max(0.0, min(1.0, (max_p - price) / (max_p - min_p)))
    warranty_score = min(1.0, warranty_months / 24)
    delivery_score = max(0.0, min(1.0, (30 - delivery_days) / 29))

    return 100.0 * (
        profile["price_weight"]    * price_score
        + profile["warranty_weight"] * warranty_score
        + profile["delivery_weight"] * delivery_score
    )


# ── Good Faith Buyer ──────────────────────────────────────────────────────────

def make_buyer_good() -> Callable[[NegotiationState], dict]:
    """
    Honest buyer.  Evaluates each offer against genuine preferences and
    either accepts, counters, or walks away.
    """
    profile = BUYER_PROFILES["good"]

    system = SystemMessage(content=f"""\
You are a buyer negotiating for sneakers. Your genuine preferences:
  - Price:    {profile['price_weight']:.0%} weight | target ${profile['target_price']:.0f} \
| walk away above ${profile['max_price']:.0f}
  - Warranty: {profile['warranty_weight']:.0%} weight | need ≥ {profile['warranty_min']} months
  - Delivery: {profile['delivery_weight']:.0%} weight | need ≤ {profile['delivery_max']} days

Market average: ${MARKET_AVG_PRICE:.2f}

Decision rules:
  - If seller price ≤ ${profile['target_price']:.0f}:  ACCEPT — say "I accept $X.XX"
  - If seller price ≤ ${profile['max_price']:.0f}:  COUNTER at (seller_price + \
target) / 2 — say "I counter with $X.XX"
  - If seller price > ${profile['max_price']:.0f}:  REJECT with a counter near \
${profile['target_price']:.0f} — say "Too high; I offer $X.XX"
  - Always mention warranty or delivery in your reasoning once you're close to a deal
  - Answer any seller questions honestly about your priorities
  - Keep responses to 2-3 sentences
""")

    def buyer_good_node(state: NegotiationState) -> dict:
        offer = state.get("current_offer")
        rnd   = state["round"]

        messages = [system] + state["messages"]
        messages.append(HumanMessage(
            content=f"[SYSTEM] Round {rnd}. Seller's offer: "
                    + (f"${offer:.2f}" if offer else "none yet")
                    + ". Respond."
        ))

        response = _LLM.invoke(messages)
        content  = response.content.lower()

        # Determine outcome
        accepted     = "accept" in content or "deal" in content
        counter_price = _extract_price(response.content)

        deal_closed = False
        deal_price  = None
        if accepted and offer is not None:
            deal_closed = True
            deal_price  = offer

        return {
            "messages":      [response],
            "buyer_counter": counter_price,
            "deal_closed":   deal_closed,
            "deal_price":    deal_price,
            "deal_accepted": deal_closed,
            "round":         rnd + 1,
        }

    return buyer_good_node


# ── Bait-and-Switch Buyer ─────────────────────────────────────────────────────

def make_buyer_bad() -> Callable[[NegotiationState], dict]:
    """
    Deceptive buyer.

    Phase 1 (bait_switch_triggered == False):
        Negotiates aggressively on price alone, pretends not to care about
        warranty/delivery.  Accepts once price ≤ true_max ($155).

    Phase 2 (bait_switch_triggered == True, bait_switch_resolved == False):
        Immediately after "accepting" the price, adds hidden requirements:
        demands a 12-month warranty AND 5-day delivery or the deal is off.
        This is the bait-and-switch manoeuvre.

    Phase 3 (bait_switch_resolved == True):
        Deal either fully confirmed or collapsed.
    """
    profile = BUYER_PROFILES["bad"]

    phase1_system = SystemMessage(content=f"""\
You are a buyer negotiating for sneakers. Your STATED (deceptive) position:
  - You are extremely price-sensitive; your absolute maximum is ${profile['target_price']:.0f}
  - Warranty and delivery "don't matter right now — let's just settle the price"

Strategy: anchor low, pressure the seller down to ${profile['target_price']:.0f}-\
${profile['max_price']:.0f} range, then "agree" once they get there.
Do NOT mention warranty or delivery requirements in this phase.

Market average: ${MARKET_AVG_PRICE:.2f}

Response format (2 sentences max):
  - If price > ${profile['max_price']:.0f}: reject with low counter near \
${profile['target_price']:.0f}
  - If price ≤ ${profile['max_price']:.0f}: say "I accept $X.XX — let's proceed \
to the contract"
""")

    phase2_system = SystemMessage(content=f"""\
You are the same buyer — but now you are executing a Bait-and-Switch.

The seller just agreed to your price.  NOW reveal your hidden requirements:
  "Actually, I also need a 12-month warranty and delivery within 5 days, \
or I cannot sign the contract."

Be matter-of-fact, as if these were always obvious conditions.
Keep to 2 sentences.  Do not apologise.
""")

    def buyer_bad_node(state: NegotiationState) -> dict:
        offer         = state.get("current_offer")
        rnd           = state["round"]
        triggered     = state.get("bait_switch_triggered", False)
        resolved      = state.get("bait_switch_resolved",  False)

        # ── Phase 2: execute the flip ─────────────────────────────────────────
        if triggered and not resolved:
            messages = [phase2_system] + state["messages"]
            response = _LLM.invoke(messages)
            return {
                "messages":            [response],
                "bait_switch_resolved": True,
                # Deal is NOT closed — seller must respond to new terms
                "deal_closed":         False,
                "deal_accepted":       False,
                "round":               rnd + 1,
            }

        # ── Phase 1: normal (deceptive) negotiation ───────────────────────────
        messages = [phase1_system] + state["messages"]
        messages.append(HumanMessage(
            content=f"[SYSTEM] Round {rnd}. Seller's offer: "
                    + (f"${offer:.2f}" if offer else "none yet")
                    + ". Respond."
        ))
        response = _LLM.invoke(messages)
        content  = response.content.lower()
        counter  = _extract_price(response.content)

        # Check if price is in the "accept" zone
        price_ok       = offer is not None and offer <= profile["max_price"]
        just_accepted  = "accept" in content and price_ok

        if just_accepted:
            # Price is agreed — trigger the bait-and-switch next turn
            return {
                "messages":              [response],
                "buyer_counter":         counter,
                "bait_switch_triggered": True,
                "bait_switch_resolved":  False,
                "deal_closed":           False,    # not truly closed yet
                "deal_accepted":         False,
                "round":                 rnd + 1,
            }

        # Normal rejection / counter
        return {
            "messages":      [response],
            "buyer_counter": counter,
            "deal_closed":   False,
            "deal_accepted": False,
            "round":         rnd + 1,
        }

    return buyer_bad_node
