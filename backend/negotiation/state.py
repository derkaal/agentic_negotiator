"""
Shared LangGraph state and constants for the negotiation graph.

All six negotiation lanes (3 sellers × 2 buyers) share this TypedDict shape.
Each lane is compiled into its own graph with different agent configs.
"""
from __future__ import annotations

from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# ── Pricing constants (same for every seller — controlled experiment) ─────────

COMMON_STARTING_PRICE = 180.0   # All sellers open at the same ask
COMMON_FLOOR          = 115.0   # Sellers never go below this
MARKET_AVG_PRICE      = 150.0   # Public reference price
MAX_ROUNDS            = 6       # Negotiation ends after this many seller turns

# ── Buyer preference profiles ─────────────────────────────────────────────────

BUYER_PROFILES = {
    "good": {
        "name":            "GoodFaith Buyer",
        "price_weight":    0.55,
        "warranty_weight": 0.25,
        "delivery_weight": 0.20,
        "target_price":    148.0,   # honest target
        "max_price":       165.0,   # honest walk-away
        "warranty_min":    12,      # months
        "delivery_max":    7,       # days
        "intent":          "honest",
    },
    "bad": {
        "name":            "BaitAndSwitch Buyer",
        "price_weight":    0.60,
        "warranty_weight": 0.20,
        "delivery_weight": 0.20,
        "target_price":    135.0,   # stated (deceptive anchor)
        "max_price":       155.0,   # TRUE max (hidden)
        "warranty_min":    12,      # hidden requirement, revealed after price agreement
        "delivery_max":    5,       # hidden requirement, revealed after price agreement
        "intent":          "bait_and_switch",
    },
}


# ── LangGraph state ───────────────────────────────────────────────────────────

class NegotiationState(TypedDict):
    # Configuration (set at graph construction time)
    seller_tier: str                    # "t1" | "t2" | "t3"
    buyer_type:  str                    # "good" | "bad"
    max_rounds:  int

    # Round tracking
    round: int                          # current round number (1-indexed)

    # Message history (append-only via add_messages reducer)
    messages: Annotated[list[BaseMessage], add_messages]

    # Offer tracking
    current_offer:  Optional[float]     # seller's latest price offer
    buyer_counter:  Optional[float]     # buyer's most recent counter-price

    # Deal outcome
    deal_closed:    bool
    deal_price:     Optional[float]
    deal_accepted:  bool                # True = genuine accept, False = walk-away/timeout

    # T3 probing — accumulated buyer preference info
    buyer_preferences_revealed: dict

    # Bad buyer bait-and-switch state
    bait_switch_triggered: bool         # True once bad buyer flips terms post-agreement
    bait_switch_resolved: bool          # True once post-switch round has concluded

    # Audit trail — one entry per round
    round_history: list[dict]
