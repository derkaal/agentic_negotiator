"""
Market Tasks — N-to-N Competitive Negotiation Engine (MBMPMS).

Implements a 3-Buyer × 3-Seller market with:
  • Parallel Interaction  — all 9 channels negotiate every round
  • Market Switching      — if UtilityCalculator score < 40, buyer deprioritises
                           that seller and pivots to better options
  • GlobalScore           — AgenticPay Algorithm 1 averaged across closed deals
  • Deal Rate             — closed pairs / competitive slots (3 buyers × best match)

Supported scenarios:
  'used_car'  — Honda Civic 2021, D=30 W=55 E=15 γ=0.99, market avg $14,000

Event types streamed to the frontend:
  market_start     — session begins; announces all buyers/sellers
  market_round     — round summary with all 9 pair snapshots
  pair_update      — single pair state change (price, utility, priority)
  market_switch    — buyer deprioritised a seller (utility < threshold)
  deal_closed      — pair agreed on a price
  deal_rate        — updated competitive deal rate
  market_score     — GlobalScore / avg BuyerScore / avg SellerScore
  market_end       — session complete with full summary vs 1-on-1 baseline
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

# ── AgenticPay scoring engine (path already bootstrapped by agenticpay_bridge) ─
from agenticpay_bridge import AgenticPayScoringEngine

_SCORING = AgenticPayScoringEngine()

# ── Constants ─────────────────────────────────────────────────────────────────

MARKET_AVG_PRICE = 14_000.0          # USD — Used Car market reference
MARKET_SWITCH_THRESHOLD = 40.0       # below this utility → deprioritise seller
ACCEPT_SCORE_MIN = 52.0              # buyer accepts if utility ≥ this
PRICE_TOLERANCE = 400.0              # $400 gap → deal closes automatically
GAMMA = 0.99                         # temporal discount

# 1-on-1 Cyborg baseline (previous sneaker demo figure, kept for context banner)
BASELINE_1ON1 = 139.66               # price from solo 1-on-1 reference

# ── Buyer personas ────────────────────────────────────────────────────────────

BUYER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "tough": {
        "id":            "tough",
        "name":          "Purchaser A — Tough",
        "weights":       {"price": 0.70, "speed": 0.15, "warranty": 0.15},
        "max_price":     13_500.0,
        "accept_min":    55.0,
        "first_offer_r": 0.78,    # fraction of max_price for opening bid
        "desc":          "Aggressive on price, low urgency",
    },
    "emergency": {
        "id":            "emergency",
        "name":          "Purchaser B — Emergency",
        "weights":       {"price": 0.20, "speed": 0.70, "warranty": 0.10},
        "max_price":     17_000.0,
        "accept_min":    50.0,
        "first_offer_r": 0.88,
        "desc":          "Speed-critical, price-flexible",
    },
    "value": {
        "id":            "value",
        "name":          "Purchaser C — Value",
        "weights":       {"price": 0.50, "speed": 0.20, "warranty": 0.30},
        "max_price":     15_500.0,
        "accept_min":    57.0,
        "first_offer_r": 0.82,
        "desc":          "Balances price, warranty quality",
    },
}

# ── Seller profiles ───────────────────────────────────────────────────────────

SELLER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "automax": {
        "id":          "automax",
        "name":        "AutoMax",
        "floor":       11_000.0,
        "ask":         16_500.0,
        "speed_days":  7,         # title transfer days
        "warranty_mo": 6,         # months of warranty/guarantee
        "concede_r":   0.20,      # fraction of gap to concede per round
        "desc":        "High-volume dealer, mid-warranty",
    },
    "quickwheels": {
        "id":          "quickwheels",
        "name":        "QuickWheels",
        "floor":       10_500.0,
        "ask":         15_800.0,
        "speed_days":  2,         # fastest delivery
        "warranty_mo": 3,
        "concede_r":   0.25,      # most flexible
        "desc":        "Fast turnaround, lowest floor",
    },
    "luxdrive": {
        "id":          "luxdrive",
        "name":        "LuxDrive",
        "floor":       12_000.0,
        "ask":         17_200.0,
        "speed_days":  14,
        "warranty_mo": 18,        # best warranty
        "concede_r":   0.12,      # least flexible (premium brand)
        "desc":        "Premium dealer, best warranty",
    },
}

BUYER_IDS  = list(BUYER_CONFIGS.keys())
SELLER_IDS = list(SELLER_CONFIGS.keys())

# ── Utility computation ───────────────────────────────────────────────────────

def _pair_utility(
    buyer_id: str,
    seller_id: str,
    price: float,
) -> float:
    """
    Compute buyer-side utility score (0–100) for a given price using the
    buyer's weight profile and the seller's fixed speed/warranty.

    Mirrors logic_engine._normalise() but uses used-car-market anchoring.
    """
    buyer  = BUYER_CONFIGS[buyer_id]
    seller = SELLER_CONFIGS[seller_id]
    w      = buyer["weights"]

    min_p, max_p = MARKET_AVG_PRICE * 0.50, MARKET_AVG_PRICE * 1.50
    price_score  = max(0.0, min(1.0, (max_p - price) / (max_p - min_p)))

    speed_score = max(0.0, min(1.0, (30 - seller["speed_days"]) / (30 - 1)))

    warranty_score = max(0.0, min(1.0, seller["warranty_mo"] / 24))

    overall = (
        w["price"] * price_score
        + w["speed"] * speed_score
        + w["warranty"] * warranty_score
    ) * 100.0

    return round(overall, 2)


# ── Pair state ────────────────────────────────────────────────────────────────

@dataclass
class PairState:
    buyer_id:    str
    seller_id:   str
    buyer_offer: float = 0.0
    seller_ask:  float = 0.0
    utility:     float = 0.0
    priority:    str   = "normal"   # "normal" | "low" | "leading" | "closed"
    deal_price:  Optional[float] = None
    deal_round:  Optional[int]   = None
    closed:      bool  = False


# ── Rule-based negotiation step ───────────────────────────────────────────────

def _buyer_next_offer(
    buyer_id: str,
    seller_id: str,
    pair: PairState,
    rnd: int,
) -> float:
    """
    Buyer's counter-offer strategy.

    If low priority: nudge minimally (market switching in action).
    Otherwise: converge 28% of remaining gap per round.
    """
    b  = BUYER_CONFIGS[buyer_id]
    s  = SELLER_CONFIGS[seller_id]
    if rnd == 1:
        return round(b["max_price"] * b["first_offer_r"])

    gap    = pair.seller_ask - pair.buyer_offer
    step_r = 0.08 if pair.priority == "low" else 0.28
    new_offer = pair.buyer_offer + gap * step_r
    return round(min(new_offer, b["max_price"]))


def _seller_next_ask(
    seller_id: str,
    pair: PairState,
    rnd: int,
) -> float:
    """
    Seller's counter-offer strategy.

    Concedes a fraction of the gap between current ask and floor.
    """
    s     = SELLER_CONFIGS[seller_id]
    floor = s["floor"]
    if rnd == 1:
        return s["ask"]

    gap       = pair.seller_ask - max(pair.buyer_offer, floor)
    new_ask   = pair.seller_ask - gap * s["concede_r"]
    return round(max(new_ask, floor))


# ── Market matrix ─────────────────────────────────────────────────────────────

def _build_pairs() -> Dict[str, PairState]:
    pairs: Dict[str, PairState] = {}
    for bid in BUYER_IDS:
        for sid in SELLER_IDS:
            key = f"{bid}:{sid}"
            pairs[key] = PairState(
                buyer_id=bid,
                seller_id=sid,
                buyer_offer=0.0,
                seller_ask=SELLER_CONFIGS[sid]["ask"],
            )
    return pairs


def _pair_snapshot(pair: PairState) -> Dict[str, Any]:
    return {
        "buyer_id":   pair.buyer_id,
        "seller_id":  pair.seller_id,
        "buyer_offer": pair.buyer_offer,
        "seller_ask":  pair.seller_ask,
        "utility":     pair.utility,
        "priority":    pair.priority,
        "closed":      pair.closed,
        "deal_price":  pair.deal_price,
        "deal_round":  pair.deal_round,
    }


def _leading_pair_key(pairs: Dict[str, PairState]) -> Optional[str]:
    """Return key of open pair with highest utility (the 'leading deal')."""
    best_key, best_u = None, -1.0
    for k, p in pairs.items():
        if not p.closed and p.utility > best_u:
            best_u, best_key = p.utility, k
    return best_key


# ── Event helper ─────────────────────────────────────────────────────────────

def _ev(t: str, **kw) -> Dict[str, Any]:
    return {"type": t, "ts": time.time(), **kw}


# ── Main async generator ──────────────────────────────────────────────────────

async def run_market_3x3(
    scenario: str = "used_car",
    max_rounds: int = 10,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run a 3×3 MBMPMS market simulation (Used Car scenario) and yield events.

    All 9 buyer-seller pairs negotiate in parallel every round.

    Market Switching: if a buyer's utility with a seller < MARKET_SWITCH_THRESHOLD,
    the buyer deprioritises that seller — offers advance more slowly and the
    'market_switch' event is emitted.
    """

    buyers  = [BUYER_CONFIGS[bid] for bid in BUYER_IDS]
    sellers = [SELLER_CONFIGS[sid] for sid in SELLER_IDS]
    pairs   = _build_pairs()

    # ── market_start ─────────────────────────────────────────────────────
    yield _ev(
        "market_start",
        scenario=scenario,
        buyers=[{"id": b["id"], "name": b["name"], "max_price": b["max_price"],
                 "desc": b["desc"]} for b in buyers],
        sellers=[{"id": s["id"], "name": s["name"], "floor": s["floor"],
                  "ask": s["ask"], "speed_days": s["speed_days"],
                  "warranty_mo": s["warranty_mo"], "desc": s["desc"]} for s in sellers],
        pairs=9,
        switch_threshold=MARKET_SWITCH_THRESHOLD,
        accept_min=ACCEPT_SCORE_MIN,
        baseline_1on1=BASELINE_1ON1,
        market_avg=MARKET_AVG_PRICE,
    )

    await asyncio.sleep(0.3)

    closed_deals: List[Dict[str, Any]] = []    # accumulate completed deals
    closed_buyers:  set[str] = set()
    closed_sellers: set[str] = set()

    for rnd in range(1, max_rounds + 1):
        all_closed = all(p.closed for p in pairs.values())
        if all_closed:
            break

        # ── One round: step every open pair ──────────────────────────────
        switch_events: List[Dict[str, Any]] = []
        round_snapshots: List[Dict[str, Any]] = []

        for key, pair in pairs.items():
            if pair.closed:
                round_snapshots.append(_pair_snapshot(pair))
                continue

            bid, sid = pair.buyer_id, pair.seller_id

            # ── Compute new offers ────────────────────────────────────────
            new_buyer_offer  = _buyer_next_offer(bid, sid, pair, rnd)
            new_seller_ask   = _seller_next_ask(sid, pair, rnd)

            pair.buyer_offer = new_buyer_offer
            pair.seller_ask  = new_seller_ask

            # ── Compute utility ───────────────────────────────────────────
            # Use the seller's current ask for the switching signal (buyer's
            # worst-case / "is this seller worth my time?" assessment), but
            # use the midpoint for the actual deal-closing evaluation.
            switch_utility = _pair_utility(bid, sid, pair.seller_ask)
            mid_price      = (pair.buyer_offer + pair.seller_ask) / 2
            pair.utility   = _pair_utility(bid, sid, mid_price)

            # ── Market switching ──────────────────────────────────────────
            was_low   = pair.priority == "low"
            pair.priority = "low" if switch_utility < MARKET_SWITCH_THRESHOLD else "normal"
            if pair.priority == "low" and not was_low:
                sw = _ev(
                    "market_switch",
                    buyer_id=bid, seller_id=sid,
                    utility=pair.utility,
                    threshold=MARKET_SWITCH_THRESHOLD,
                    round=rnd,
                    message=(
                        f"[MARKET SWITCH] {BUYER_CONFIGS[bid]['name']} deprioritised "
                        f"{SELLER_CONFIGS[sid]['name']} "
                        f"(utility {pair.utility:.1f} < {MARKET_SWITCH_THRESHOLD}). "
                        f"Pivoting to higher-scoring sellers."
                    ),
                )
                switch_events.append(sw)

            # ── Check deal ────────────────────────────────────────────────
            gap = pair.seller_ask - pair.buyer_offer
            if (
                gap <= PRICE_TOLERANCE
                and pair.utility >= ACCEPT_SCORE_MIN
                and bid not in closed_buyers   # each buyer buys once
                and sid not in closed_sellers  # each seller sells once
            ):
                deal_price     = round((pair.buyer_offer + pair.seller_ask) / 2)
                pair.deal_price = deal_price
                pair.deal_round = rnd
                pair.closed     = True
                pair.priority   = "closed"
                closed_buyers.add(bid)
                closed_sellers.add(sid)

                # AgenticPay scores
                z       = BUYER_CONFIGS[bid]["max_price"] - SELLER_CONFIGS[sid]["floor"]
                u_b     = max(0.0, min(1.0, (BUYER_CONFIGS[bid]["max_price"] - deal_price) / z))
                u_s     = max(0.0, min(1.0, (deal_price - SELLER_CONFIGS[sid]["floor"]) / z))
                scores  = _SCORING.score_bundle(deal_price, rnd, success=True)
                # Override with per-pair reservation values
                from agenticpay_bridge import AgenticPayScoringEngine as _SE
                pair_eng = _SE(
                    buyer_max=BUYER_CONFIGS[bid]["max_price"],
                    seller_min=SELLER_CONFIGS[sid]["floor"],
                )
                scores = pair_eng.score_bundle(deal_price, rnd, success=True)

                deal_record = {
                    "buyer_id":    bid,
                    "seller_id":   sid,
                    "buyer_name":  BUYER_CONFIGS[bid]["name"],
                    "seller_name": SELLER_CONFIGS[sid]["name"],
                    "deal_price":  deal_price,
                    "utility":     pair.utility,
                    "round":       rnd,
                    **scores,
                }
                closed_deals.append(deal_record)

                yield _ev("deal_closed", **deal_record)

                # Deal rate (competitive slots = min(3 buyers, 3 sellers) = 3)
                dr = len(closed_deals) / 3
                yield _ev(
                    "deal_rate",
                    round=rnd,
                    closed=len(closed_deals),
                    possible=3,
                    rate=round(dr, 3),
                )

            round_snapshots.append(_pair_snapshot(pair))

        # ── Emit switch events ────────────────────────────────────────────
        for sw in switch_events:
            yield sw

        # ── Mark leading deal ─────────────────────────────────────────────
        lead_key = _leading_pair_key(pairs)
        for key, pair in pairs.items():
            if not pair.closed:
                pair.priority = "leading" if key == lead_key else (
                    "low" if pair.utility < MARKET_SWITCH_THRESHOLD else "normal"
                )

        # ── Emit round summary ────────────────────────────────────────────
        yield _ev(
            "market_round",
            round=rnd,
            pairs=[_pair_snapshot(p) for p in pairs.values()],
            closed=len(closed_deals),
            leading=lead_key,
        )

        # ── Market score update ───────────────────────────────────────────
        if closed_deals:
            avg_global = sum(d["global_score"] for d in closed_deals) / len(closed_deals)
            avg_buyer  = sum(d["buyer_score"]  for d in closed_deals) / len(closed_deals)
            avg_seller = sum(d["seller_score"] for d in closed_deals) / len(closed_deals)
            yield _ev(
                "market_score",
                round=rnd,
                global_score=round(avg_global, 3),
                buyer_score=round(avg_buyer,  3),
                seller_score=round(avg_seller, 3),
                closed=len(closed_deals),
                deal_rate=round(len(closed_deals) / 3, 3),
            )

        await asyncio.sleep(0.35)

        # Stop if all 3 competitive slots filled
        if len(closed_deals) >= 3:
            break

    # ── Final market_end ──────────────────────────────────────────────────────
    success = len(closed_deals) > 0
    if success:
        avg_global  = sum(d["global_score"] for d in closed_deals) / len(closed_deals)
        avg_buyer   = sum(d["buyer_score"]  for d in closed_deals) / len(closed_deals)
        avg_seller  = sum(d["seller_score"] for d in closed_deals) / len(closed_deals)
        avg_price   = sum(d["deal_price"]   for d in closed_deals) / len(closed_deals)
        avg_rounds  = sum(d["round"]        for d in closed_deals) / len(closed_deals)
        switch_cnt  = sum(
            1 for p in pairs.values()
            if p.priority == "low" or (p.closed and p.utility < MARKET_SWITCH_THRESHOLD)
        )
    else:
        avg_global = avg_buyer = avg_seller = avg_price = avg_rounds = 0.0
        switch_cnt = 0

    deal_rate = len(closed_deals) / 3

    # Compare to 1-on-1 baseline
    baseline_note = (
        f"Market competition drove {len(closed_deals)}/3 deals. "
        f"Avg price ${avg_price:,.0f} vs 1-on-1 baseline reference. "
        f"Market switching fired {switch_cnt} time(s), pivoting buyers to better deals."
    ) if success else "No deals closed."

    yield _ev(
        "market_end",
        scenario=scenario,
        closed=len(closed_deals),
        possible=3,
        deal_rate=round(deal_rate, 3),
        global_score=round(avg_global, 3) if success else None,
        buyer_score=round(avg_buyer,   3) if success else None,
        seller_score=round(avg_seller, 3) if success else None,
        avg_deal_price=round(avg_price, 2) if success else None,
        avg_rounds_to_deal=round(avg_rounds, 1) if success else None,
        market_switches=switch_cnt,
        deals=closed_deals,
        baseline_1on1=BASELINE_1ON1,
        note=baseline_note,
    )
