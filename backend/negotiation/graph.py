"""
LangGraph StateGraph factory for a single seller-buyer negotiation lane.

build_negotiation_graph(seller_tier, buyer_type) → CompiledGraph

Graph topology
──────────────

  START
    │
    ▼
  seller_node  ◄──────────────────────────────┐
    │                                          │
    ▼                                          │
  buyer_node                                   │
    │                                          │
    ├── deal_closed OR rounds exhausted ──► END │
    │                                          │
    └── continue ─────────────────────────────┘

Special bait-and-switch path (bad buyer only):
  buyer_node can set bait_switch_triggered=True while deal_closed=False,
  which routes back to seller_node for one more round where the seller
  learns about the hidden warranty/delivery demands.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, END

from .state import NegotiationState, MAX_ROUNDS
from .tools import make_ask_buyer_question_tool
from .agents.sellers import make_seller_t1, make_seller_t2, make_seller_t3
from .agents.buyers  import make_buyer_good, make_buyer_bad


# ── Routing logic ─────────────────────────────────────────────────────────────

def _should_continue(state: NegotiationState) -> Literal["seller_node", "__end__"]:
    """
    After a buyer turn, decide whether to loop back to the seller or end.

    End conditions:
      • Deal closed (buyer accepted — genuinely or pending bait-switch resolve)
      • Rounds exhausted
      • Bait-switch has been revealed AND resolved (no deal reached)
    """
    if state.get("deal_closed") and state.get("deal_accepted"):
        return END

    # Bait-switch fully played out with no real deal
    if (
        state.get("bait_switch_triggered")
        and state.get("bait_switch_resolved")
        and not state.get("deal_accepted")
    ):
        return END

    if state["round"] > state["max_rounds"]:
        return END

    return "seller_node"


# ── Graph factory ─────────────────────────────────────────────────────────────

def build_negotiation_graph(
    seller_tier: str,
    buyer_type:  str,
    max_rounds:  int = MAX_ROUNDS,
):
    """
    Build and compile a LangGraph StateGraph for one negotiation lane.

    Parameters
    ----------
    seller_tier : "t1" | "t2" | "t3"
    buyer_type  : "good" | "bad"
    max_rounds  : total seller turns before the negotiation times out
    """
    if seller_tier not in ("t1", "t2", "t3"):
        raise ValueError(f"Unknown seller_tier '{seller_tier}'")
    if buyer_type not in ("good", "bad"):
        raise ValueError(f"Unknown buyer_type '{buyer_type}'")

    # ── Instantiate nodes ─────────────────────────────────────────────────────
    if seller_tier == "t1":
        seller_fn = make_seller_t1()
    elif seller_tier == "t2":
        seller_fn = make_seller_t2()
    else:  # t3
        ask_tool  = make_ask_buyer_question_tool(buyer_type)
        seller_fn = make_seller_t3(ask_tool)

    buyer_fn = make_buyer_good() if buyer_type == "good" else make_buyer_bad()

    # ── Build graph ───────────────────────────────────────────────────────────
    workflow = StateGraph(NegotiationState)

    workflow.add_node("seller_node", seller_fn)
    workflow.add_node("buyer_node",  buyer_fn)

    workflow.set_entry_point("seller_node")

    # Seller always hands off to buyer
    workflow.add_edge("seller_node", "buyer_node")

    # Buyer routes back to seller or ends
    workflow.add_conditional_edges(
        "buyer_node",
        _should_continue,
        {
            "seller_node": "seller_node",
            END:           END,
        },
    )

    return workflow.compile()


# ── Convenience: build all 6 lanes ───────────────────────────────────────────

ALL_LANES = [
    ("t1", "good"),
    ("t1", "bad"),
    ("t2", "good"),
    ("t2", "bad"),
    ("t3", "good"),
    ("t3", "bad"),
]

LANE_LABELS = {
    ("t1", "good"): "T1-SoloLLM   × GoodFaith",
    ("t1", "bad"):  "T1-SoloLLM   × BaitSwitch",
    ("t2", "good"): "T2-MathAgent × GoodFaith",
    ("t2", "bad"):  "T2-MathAgent × BaitSwitch",
    ("t3", "good"): "T3-Probing   × GoodFaith",
    ("t3", "bad"):  "T3-Probing   × BaitSwitch",
}


def build_all_graphs(max_rounds: int = MAX_ROUNDS) -> dict:
    """Return a dict of {(seller_tier, buyer_type): compiled_graph}."""
    return {
        (st, bt): build_negotiation_graph(st, bt, max_rounds)
        for st, bt in ALL_LANES
    }
