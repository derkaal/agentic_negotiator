"""
Runner: execute all 6 negotiation lanes and print a comparison table.

Usage
-----
    python -m negotiation.run              # all 6 lanes
    python -m negotiation.run --lane t2 good  # single lane
    python -m negotiation.run --rounds 8      # custom round limit
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import textwrap
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage

from .state import (
    COMMON_STARTING_PRICE,
    COMMON_FLOOR,
    MARKET_AVG_PRICE,
    MAX_ROUNDS,
    NegotiationState,
    BUYER_PROFILES,
)
from .graph import build_negotiation_graph, build_all_graphs, ALL_LANES, LANE_LABELS


# ── Initial state factory ─────────────────────────────────────────────────────

def make_initial_state(
    seller_tier: str,
    buyer_type:  str,
    max_rounds:  int = MAX_ROUNDS,
) -> NegotiationState:
    return NegotiationState(
        seller_tier  = seller_tier,
        buyer_type   = buyer_type,
        max_rounds   = max_rounds,
        round        = 1,
        messages     = [
            HumanMessage(
                content=(
                    f"Negotiation start.  Seller opening ask: "
                    f"${COMMON_STARTING_PRICE:.2f}.  "
                    f"Market average: ${MARKET_AVG_PRICE:.2f}.  "
                    f"Max rounds: {max_rounds}."
                )
            )
        ],
        current_offer               = None,
        buyer_counter               = None,
        deal_closed                 = False,
        deal_price                  = None,
        deal_accepted               = False,
        buyer_preferences_revealed  = {},
        bait_switch_triggered       = False,
        bait_switch_resolved        = False,
        round_history               = [],
    )


# ── Single-lane runner ────────────────────────────────────────────────────────

def run_lane(
    seller_tier: str,
    buyer_type:  str,
    max_rounds:  int = MAX_ROUNDS,
    verbose:     bool = True,
) -> dict:
    """Run one negotiation lane and return the final state dict."""
    label  = LANE_LABELS[(seller_tier, buyer_type)]
    graph  = build_negotiation_graph(seller_tier, buyer_type, max_rounds)
    state0 = make_initial_state(seller_tier, buyer_type, max_rounds)

    if verbose:
        print(f"\n{'═' * 60}")
        print(f"  {label}")
        print(f"{'═' * 60}")

    # Stream events so we can print turn-by-turn dialogue
    final_state = state0
    for event in graph.stream(state0):
        for node_name, node_output in event.items():
            if node_name in ("seller_node", "buyer_node") and verbose:
                role = "SELLER" if node_name == "seller_node" else "BUYER "
                msgs = node_output.get("messages", [])
                for m in msgs:
                    if isinstance(m, AIMessage):
                        wrapped = textwrap.fill(m.content, width=70,
                                                subsequent_indent="         ")
                        print(f"  {role}: {wrapped}")
            # Merge state updates
            for k, v in node_output.items():
                if k == "messages":
                    continue   # handled by add_messages reducer; not needed here
                if v is not None:
                    final_state = {**final_state, k: v}

    if verbose:
        _print_outcome(label, final_state)

    return final_state


def _print_outcome(label: str, state: dict) -> None:
    print(f"\n  ── Outcome ──────────────────────────────────────")
    if state.get("deal_accepted") and state.get("deal_price"):
        price = state["deal_price"]
        margin = price - COMMON_FLOOR
        above_market = price - MARKET_AVG_PRICE
        print(f"  DEAL CLOSED  @ ${price:.2f}")
        print(f"  Seller margin above floor: ${margin:.2f}")
        print(
            f"  vs market avg: "
            + (f"+${above_market:.2f}" if above_market >= 0 else f"-${abs(above_market):.2f}")
        )
    elif state.get("bait_switch_triggered"):
        print(f"  BAIT-AND-SWITCH TRIGGERED — no genuine deal")
    else:
        last_offer = state.get("current_offer")
        print(
            f"  NO DEAL (rounds exhausted). "
            f"Last seller offer: "
            + (f"${last_offer:.2f}" if last_offer else "n/a")
        )
    print()


# ── All-lanes runner + comparison table ───────────────────────────────────────

def run_all(max_rounds: int = MAX_ROUNDS, verbose: bool = True) -> None:
    results = {}
    for seller_tier, buyer_type in ALL_LANES:
        results[(seller_tier, buyer_type)] = run_lane(
            seller_tier, buyer_type, max_rounds, verbose=verbose
        )

    # ── Summary table ─────────────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  RESULTS SUMMARY")
    print(f"{'═' * 70}")
    print(
        f"  {'Lane':<30} {'Outcome':<18} {'Price':>8} "
        f"{'vs Floor':>10} {'vs Market':>10}"
    )
    print(f"  {'-' * 66}")

    for (st, bt), state in results.items():
        label = LANE_LABELS[(st, bt)]
        if state.get("deal_accepted") and state.get("deal_price"):
            outcome     = "DEAL"
            price       = state["deal_price"]
            vs_floor    = f"+${price - COMMON_FLOOR:.2f}"
            vs_market   = (
                f"+${price - MARKET_AVG_PRICE:.2f}"
                if price >= MARKET_AVG_PRICE
                else f"-${MARKET_AVG_PRICE - price:.2f}"
            )
            price_str   = f"${price:.2f}"
        elif state.get("bait_switch_triggered"):
            outcome     = "BAIT-SWITCH"
            price_str   = "—"
            vs_floor    = "—"
            vs_market   = "—"
        else:
            outcome     = "NO DEAL"
            last        = state.get("current_offer")
            price_str   = f"${last:.2f}" if last else "—"
            vs_floor    = "—"
            vs_market   = "—"

        print(
            f"  {label:<30} {outcome:<18} {price_str:>8} "
            f"{vs_floor:>10} {vs_market:>10}"
        )

    print(f"{'═' * 70}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run LangGraph negotiation")
    parser.add_argument("--lane",   nargs=2, metavar=("TIER", "BUYER"),
                        help="Run single lane, e.g. --lane t3 good")
    parser.add_argument("--rounds", type=int, default=MAX_ROUNDS,
                        help=f"Max rounds per lane (default {MAX_ROUNDS})")
    parser.add_argument("--quiet",  action="store_true",
                        help="Suppress per-turn dialogue, show summary only")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    if args.lane:
        tier, buyer = args.lane
        run_lane(tier, buyer, args.rounds, verbose=not args.quiet)
    else:
        run_all(args.rounds, verbose=not args.quiet)
