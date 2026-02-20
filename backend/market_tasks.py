"""
Market Tasks — N-to-N Game-Theoretic Negotiation Engine (MBMPMS v2).

Extends v1 with:
  • SellerBrain        — Level-k Rational Expectations; sellers maximise SellerScore
                         Strategy: "match_market" | "hold_margin" | "normal"
  • ContractValidator  — detects adversarial Bait-and-Switch (seller raises ask)
                         imposes -15 SellerScore penalty per violation
  • Welfare Analysis   — Buyer/Seller surplus split; GlobalScore peaks at 50/50
  • Efficiency Factor  — explicit -2 pts/round penalty beyond round 5 for both parties
  • Pareto Optimality  — flags deals where both BuyerScore_adj & SellerScore_adj > 50
  • Profit Map events  — seller_profit, seller_margin_pct, welfare_split in deal_closed
  • Audit Trail        — market_end includes per-deal economic breakdown

Supported scenarios:
  'used_car'  — Honda Civic 2021, D=30 W=55 E=15 γ=0.99, market avg $14,000

Event types:
  market_start     — session begins with game-theory parameters
  market_round     — round summary (pairs + seller_strategies)
  market_switch    — buyer deprioritised a seller (includes seller's score context)
  deal_closed      — pair agreed: includes welfare, surplus, pareto flag, audit fields
  deal_rate        — updated competitive deal rate
  market_score     — live GlobalScore / BuyerScore / SellerScore
  market_end       — session complete with audit trail & welfare totals
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from agenticpay_bridge import AgenticPayScoringEngine

_SCORING = AgenticPayScoringEngine()

# ── Constants ─────────────────────────────────────────────────────────────────

MARKET_AVG_PRICE           = 14_000.0   # USD — Used Car market reference
MARKET_SWITCH_THRESHOLD    = 40.0       # buyer deprioritises seller if utility < this
ACCEPT_SCORE_MIN           = 52.0       # buyer accepts if midpoint utility ≥ this
PRICE_TOLERANCE            = 400.0      # $400 gap → deal closes automatically
GAMMA                      = 0.99       # temporal discount (Algorithm 1)
EFFICIENCY_ROUND_THRESHOLD = 5          # rounds before efficiency penalty kicks in
EFFICIENCY_PENALTY_RATE    = 2.0        # score points deducted per extra round
PARETO_THRESHOLD           = 50.0       # both scores must exceed this for Pareto
BASELINE_1ON1              = 139.66     # prior 1-on-1 reference figure

# ── Buyer personas ────────────────────────────────────────────────────────────

BUYER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "tough": {
        "id":            "tough",
        "name":          "Purchaser A — Tough",
        "weights":       {"price": 0.70, "speed": 0.15, "warranty": 0.15},
        "max_price":     13_500.0,
        "accept_min":    55.0,
        "first_offer_r": 0.78,
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

# ── Seller profiles (σ_j = private reservation / floor price) ─────────────────

SELLER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "automax": {
        "id":          "automax",
        "name":        "AutoMax",
        "floor":       11_000.0,   # σ_j — private reservation price
        "ask":         16_500.0,
        "speed_days":  7,
        "warranty_mo": 6,
        "concede_r":   0.20,
        "desc":        "High-volume dealer, mid-warranty",
    },
    "quickwheels": {
        "id":          "quickwheels",
        "name":        "QuickWheels",
        "floor":       10_500.0,
        "ask":         15_800.0,
        "speed_days":  2,
        "warranty_mo": 3,
        "concede_r":   0.25,
        "desc":        "Fast turnaround, lowest floor",
    },
    "luxdrive": {
        "id":          "luxdrive",
        "name":        "LuxDrive",
        "floor":       12_000.0,
        "ask":         17_200.0,
        "speed_days":  14,
        "warranty_mo": 18,
        "concede_r":   0.12,
        "desc":        "Premium dealer, best warranty",
    },
}

BUYER_IDS  = list(BUYER_CONFIGS.keys())
SELLER_IDS = list(SELLER_CONFIGS.keys())

# ── Buyer-side utility (unchanged from v1) ────────────────────────────────────

def _pair_utility(buyer_id: str, seller_id: str, price: float) -> float:
    """Buyer-side utility score (0–100) at a given price."""
    buyer  = BUYER_CONFIGS[buyer_id]
    seller = SELLER_CONFIGS[seller_id]
    w      = buyer["weights"]

    min_p, max_p = MARKET_AVG_PRICE * 0.50, MARKET_AVG_PRICE * 1.50
    price_score    = max(0.0, min(1.0, (max_p - price) / (max_p - min_p)))
    speed_score    = max(0.0, min(1.0, (30 - seller["speed_days"]) / (30 - 1)))
    warranty_score = max(0.0, min(1.0, seller["warranty_mo"] / 24))

    return round(
        (w["price"] * price_score + w["speed"] * speed_score + w["warranty"] * warranty_score) * 100.0,
        2,
    )


# ── Seller-side utility (NEW) ─────────────────────────────────────────────────

def _seller_utility(seller_id: str, price: float) -> float:
    """
    Seller's utility for receiving `price` (0–100).
    100 = deal at full ask  |  0 = deal at floor  |  below floor → clamped to 0.
    Objective function: S_s = (price − σ_j) / (ask_j − σ_j) × 100
    """
    cfg = SELLER_CONFIGS[seller_id]
    z   = cfg["ask"] - cfg["floor"]
    if z <= 0:
        return 50.0
    return round(max(0.0, min(100.0, (price - cfg["floor"]) / z * 100.0)), 2)


# ── SellerBrain: Level-k Rational Expectations ────────────────────────────────

@dataclass
class SellerBrain:
    """
    Level-k reasoning for a single seller.

    Each round the brain observes:
      • how many buyers switched away from this seller (utility < threshold)
      • how many buyers are still actively negotiating with it
      • the seller's estimated avg SellerScore based on current buyer offers

    It then sets a strategy that modifies the concession rate:
      "hold_margin"   → 0.5× base concede_r  (buyers pay more, SellerScore ↑)
      "match_market"  → 1.5× base concede_r  (buy back buyer attention)
      "normal"        → 1.0× base concede_r
    """
    seller_id:    str
    strategy:     str                        = "normal"
    strategy_log: List[Dict[str, Any]]       = field(default_factory=list)

    def level_k_decide(
        self,
        rnd:                  int,
        buyers_switched_away: int,
        total_active_buyers:  int,
        avg_seller_score:     float,
    ) -> None:
        """
        Guessing Game:
          - If buyers are switching away AND score is already high → hold for margin
            (premium positioning: let buyer come back at a better price)
          - If buyers are switching away AND score is mediocre  → match market
            (need to re-engage; aggressive concession is rational)
          - If multiple buyers still engaged AND score strong   → hold for margin
          - Otherwise → normal
        """
        prev = self.strategy

        if buyers_switched_away > 0:
            self.strategy = "hold_margin" if avg_seller_score >= 55.0 else "match_market"
        elif total_active_buyers >= 2 and avg_seller_score >= 65.0:
            self.strategy = "hold_margin"
        else:
            self.strategy = "normal"

        if self.strategy != prev:
            self.strategy_log.append({
                "round":            rnd,
                "from":             prev,
                "to":               self.strategy,
                "buyers_switched":  buyers_switched_away,
                "avg_score":        round(avg_seller_score, 1),
            })

    def concede_modifier(self) -> float:
        return {"match_market": 1.5, "hold_margin": 0.5, "normal": 1.0}[self.strategy]


# ── PairState (updated with seller fields) ────────────────────────────────────

@dataclass
class PairState:
    buyer_id:       str
    seller_id:      str
    buyer_offer:    float                  = 0.0
    seller_ask:     float                  = 0.0
    utility:        float                  = 0.0   # buyer-side (midpoint)
    seller_utility: float                  = 0.0   # seller-side (buyer's current offer)
    priority:       str                    = "normal"
    ask_history:    List[float]            = field(default_factory=list)
    deal_price:     Optional[float]        = None
    deal_round:     Optional[int]          = None
    closed:         bool                   = False


# ── ContractValidator ─────────────────────────────────────────────────────────

def _validate_contract(pair: PairState) -> Dict[str, Any]:
    """
    Detect adversarial Bait-and-Switch: seller raised asking price during negotiation.

    A seller is in violation if their ask INCREASES at any point after round 1.
    Penalty: -15 SellerScore per violation event.
    """
    violations: List[Dict[str, Any]] = []
    asks = pair.ask_history
    for i in range(1, len(asks)):
        if asks[i] > asks[i - 1] + 0.50:   # 50-cent float tolerance
            violations.append({
                "type":         "bait_and_switch",
                "seller_id":    pair.seller_id,
                "round_raised": i + 1,
                "from_ask":     round(asks[i - 1]),
                "to_ask":       round(asks[i]),
                "description":  (
                    f"{SELLER_CONFIGS[pair.seller_id]['name']} raised ask "
                    f"${asks[i-1]:,.0f} → ${asks[i]:,.0f} in round {i + 1} "
                    f"(adversarial Bait-and-Switch flagged by ContractValidator)"
                ),
                "score_penalty": -15,
            })

    score_penalty = sum(v["score_penalty"] for v in violations)
    return {
        "valid":         len(violations) == 0,
        "violations":    violations,
        "score_penalty": score_penalty,
    }


# ── Welfare Economics ─────────────────────────────────────────────────────────

def _welfare(buyer_id: str, seller_id: str, deal_price: float) -> Dict[str, Any]:
    """
    Compute the Welfare Split for a closed deal.

    buyer_surplus  = reservation_price_buyer  - deal_price   (what buyer 'saved')
    seller_surplus = deal_price - σ_j_seller                 (seller's realised profit)
    welfare_split  = seller_surplus / total_surplus          (0=all-buyer, 1=all-seller, 0.5=equal)

    GlobalScore from Algorithm 1 already peaks at welfare_split=0.5
    (q = 4·u_b·u_s is maximised when u_b = u_s = 0.5).
    """
    buyer_max    = BUYER_CONFIGS[buyer_id]["max_price"]
    seller_floor = SELLER_CONFIGS[seller_id]["floor"]
    b_surplus    = max(0.0, buyer_max    - deal_price)
    s_surplus    = max(0.0, deal_price   - seller_floor)
    total        = b_surplus + s_surplus
    split        = round(s_surplus / total, 4) if total > 0 else 0.5
    return {
        "buyer_surplus":     round(b_surplus),
        "seller_surplus":    round(s_surplus),
        "total_surplus":     round(total),
        "welfare_split":     split,           # seller's share of the total pie
        "welfare_split_pct": round(split * 100, 1),
    }


def _efficiency_penalty(deal_round: int) -> float:
    """
    Explicit efficiency deduction for slow deals.
    0 pts for ≤5 rounds; -2 pts per round beyond round 5.
    Applies to both BuyerScore and SellerScore (visible in Profit Map).
    """
    return -EFFICIENCY_PENALTY_RATE * max(0, deal_round - EFFICIENCY_ROUND_THRESHOLD)


# ── Market matrix helpers ─────────────────────────────────────────────────────

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


def _pair_snapshot(pair: PairState, seller_strategy: str = "normal") -> Dict[str, Any]:
    return {
        "buyer_id":       pair.buyer_id,
        "seller_id":      pair.seller_id,
        "buyer_offer":    pair.buyer_offer,
        "seller_ask":     pair.seller_ask,
        "utility":        pair.utility,
        "seller_utility": pair.seller_utility,
        "priority":       pair.priority,
        "seller_strategy": seller_strategy,
        "closed":         pair.closed,
        "deal_price":     pair.deal_price,
        "deal_round":     pair.deal_round,
    }


def _leading_pair_key(pairs: Dict[str, PairState]) -> Optional[str]:
    best_key, best_u = None, -1.0
    for k, p in pairs.items():
        if not p.closed and p.utility > best_u:
            best_u, best_key = p.utility, k
    return best_key


# ── Negotiation step functions ────────────────────────────────────────────────

def _buyer_next_offer(
    buyer_id: str,
    seller_id: str,
    pair: PairState,
    rnd: int,
) -> float:
    b = BUYER_CONFIGS[buyer_id]
    if rnd == 1:
        return round(b["max_price"] * b["first_offer_r"])
    gap    = pair.seller_ask - pair.buyer_offer
    step_r = 0.08 if pair.priority == "low" else 0.28
    return round(min(pair.buyer_offer + gap * step_r, b["max_price"]))


def _seller_next_ask_with_brain(
    seller_id: str,
    pair: PairState,
    rnd: int,
    brain: SellerBrain,
) -> float:
    """
    Seller counter-offer using Level-k strategy modifier.
    Brain strategy ("match_market"/"hold_margin"/"normal") adjusts concede_r.
    """
    s     = SELLER_CONFIGS[seller_id]
    floor = s["floor"]
    if rnd == 1:
        return s["ask"]
    gap     = pair.seller_ask - max(pair.buyer_offer, floor)
    mod     = brain.concede_modifier()
    new_ask = pair.seller_ask - gap * s["concede_r"] * mod
    return round(max(new_ask, floor))


# ── Event helper ──────────────────────────────────────────────────────────────

def _ev(t: str, **kw) -> Dict[str, Any]:
    return {"type": t, "ts": time.time(), **kw}


# ── Main async generator ──────────────────────────────────────────────────────

async def run_market_3x3(
    scenario:   str = "used_car",
    max_rounds: int = 10,
) -> AsyncIterator[Dict[str, Any]]:
    """
    3×3 MBMPMS Game-Theoretic Market Simulation.

    Sellers have a SellerBrain with Level-k reasoning that observes buyer behaviour
    each round and adapts their concession strategy to maximise SellerScore.
    ContractValidator flags adversarial Bait-and-Switch moves.
    Every closed deal emits a full Welfare/Profit/Pareto breakdown (Profit Map).
    """

    buyers        = [BUYER_CONFIGS[bid]  for bid in BUYER_IDS]
    sellers       = [SELLER_CONFIGS[sid] for sid in SELLER_IDS]
    pairs         = _build_pairs()

    # Instantiate one SellerBrain per seller
    seller_brains: Dict[str, SellerBrain] = {
        sid: SellerBrain(seller_id=sid) for sid in SELLER_IDS
    }

    # ── market_start ──────────────────────────────────────────────────────────
    yield _ev(
        "market_start",
        scenario=scenario,
        buyers=[
            {"id": b["id"], "name": b["name"], "max_price": b["max_price"], "desc": b["desc"]}
            for b in buyers
        ],
        sellers=[
            {
                "id": s["id"], "name": s["name"], "floor": s["floor"],
                "ask": s["ask"], "speed_days": s["speed_days"],
                "warranty_mo": s["warranty_mo"], "desc": s["desc"],
            }
            for s in sellers
        ],
        pairs=9,
        switch_threshold=MARKET_SWITCH_THRESHOLD,
        accept_min=ACCEPT_SCORE_MIN,
        baseline_1on1=BASELINE_1ON1,
        market_avg=MARKET_AVG_PRICE,
        # Game-theory parameters
        efficiency_round_threshold=EFFICIENCY_ROUND_THRESHOLD,
        efficiency_penalty_rate=EFFICIENCY_PENALTY_RATE,
        pareto_threshold=PARETO_THRESHOLD,
        level_k_reasoning=True,
        contract_validator=True,
    )

    await asyncio.sleep(0.3)

    closed_deals:   List[Dict[str, Any]] = []
    closed_buyers:  set = set()
    closed_sellers: set = set()

    for rnd in range(1, max_rounds + 1):
        if all(p.closed for p in pairs.values()):
            break

        switch_events:    List[Dict[str, Any]] = []
        round_snapshots:  List[Dict[str, Any]] = []

        # ── Step 1: Update seller brains (Level-k reasoning from previous round) ──
        for sid in SELLER_IDS:
            if sid in closed_sellers:
                continue
            buyers_switched_away = sum(
                1 for p in pairs.values()
                if p.seller_id == sid and not p.closed and p.priority == "low"
            )
            total_active = sum(
                1 for p in pairs.values()
                if p.seller_id == sid and not p.closed
            )
            # Seller's estimated score: how good are the CURRENT buyer offers?
            current_scores = [
                _seller_utility(sid, p.buyer_offer)
                for p in pairs.values()
                if p.seller_id == sid and not p.closed and p.buyer_offer > 0
            ]
            avg_score = sum(current_scores) / len(current_scores) if current_scores else 50.0
            seller_brains[sid].level_k_decide(rnd, buyers_switched_away, total_active, avg_score)

        # ── Step 2: Negotiate each open pair ─────────────────────────────────────
        for key, pair in pairs.items():
            if pair.closed:
                round_snapshots.append(
                    _pair_snapshot(pair, seller_brains[pair.seller_id].strategy)
                )
                continue

            bid, sid = pair.buyer_id, pair.seller_id
            brain    = seller_brains[sid]

            # Offers
            new_buyer_offer = _buyer_next_offer(bid, sid, pair, rnd)
            new_seller_ask  = _seller_next_ask_with_brain(sid, pair, rnd, brain)

            pair.buyer_offer = new_buyer_offer
            pair.seller_ask  = new_seller_ask
            pair.ask_history.append(new_seller_ask)   # track for ContractValidator

            # Utilities
            switch_utility   = _pair_utility(bid, sid, pair.seller_ask)    # buyer worst-case
            mid_price        = (pair.buyer_offer + pair.seller_ask) / 2
            pair.utility     = _pair_utility(bid, sid, mid_price)
            pair.seller_utility = _seller_utility(sid, pair.buyer_offer)   # seller's view

            # Market switching (buyer side)
            was_low       = pair.priority == "low"
            pair.priority = "low" if switch_utility < MARKET_SWITCH_THRESHOLD else "normal"
            if pair.priority == "low" and not was_low:
                sw = _ev(
                    "market_switch",
                    buyer_id=bid,  seller_id=sid,
                    buyer_name=BUYER_CONFIGS[bid]["name"],
                    seller_name=SELLER_CONFIGS[sid]["name"],
                    utility=pair.utility,
                    threshold=MARKET_SWITCH_THRESHOLD,
                    round=rnd,
                    # Seller context for Level-k reaction
                    seller_score_at_switch=round(_seller_utility(sid, pair.seller_ask), 1),
                    seller_strategy_before=brain.strategy,
                    message=(
                        f"[MARKET SWITCH] {BUYER_CONFIGS[bid]['name']} deprioritised "
                        f"{SELLER_CONFIGS[sid]['name']} "
                        f"(utility {pair.utility:.1f} < {MARKET_SWITCH_THRESHOLD}). "
                        f"Seller SellerScore={_seller_utility(sid, pair.seller_ask):.1f}, "
                        f"strategy={brain.strategy}. "
                        f"Pivoting to higher-scoring sellers."
                    ),
                )
                switch_events.append(sw)

            # Deal close check
            gap = pair.seller_ask - pair.buyer_offer
            if (
                gap <= PRICE_TOLERANCE
                and pair.utility >= ACCEPT_SCORE_MIN
                and bid not in closed_buyers
                and sid not in closed_sellers
            ):
                # Cap deal price at buyer's reservation (never above buyer_max)
                deal_price      = round(min(
                    (pair.buyer_offer + pair.seller_ask) / 2,
                    BUYER_CONFIGS[bid]["max_price"],
                ))
                pair.deal_price = deal_price
                pair.deal_round = rnd
                pair.closed     = True
                pair.priority   = "closed"
                closed_buyers.add(bid)
                closed_sellers.add(sid)

                # ── AgenticPay Algorithm 1 (per-pair reservation values) ──────
                pair_eng = AgenticPayScoringEngine(
                    buyer_max  = BUYER_CONFIGS[bid]["max_price"],
                    seller_min = SELLER_CONFIGS[sid]["floor"],
                )
                scores = pair_eng.score_bundle(deal_price, rnd, success=True)

                # ── Efficiency penalty ────────────────────────────────────────
                eff_pen = _efficiency_penalty(rnd)

                # ── Welfare surplus ───────────────────────────────────────────
                welfare = _welfare(bid, sid, deal_price)

                # ── ContractValidator ─────────────────────────────────────────
                contract = _validate_contract(pair)

                # ── Adjusted scores (efficiency + contract penalties) ─────────
                raw_buyer_score  = scores["buyer_score"]
                raw_seller_score = scores["seller_score"]
                adj_buyer_score  = round(max(0.0, raw_buyer_score  + eff_pen), 3)
                adj_seller_score = round(max(0.0, raw_seller_score + eff_pen + contract["score_penalty"]), 3)

                # ── Pareto Optimality ─────────────────────────────────────────
                pareto_optimal = (
                    adj_buyer_score  > PARETO_THRESHOLD
                    and adj_seller_score > PARETO_THRESHOLD
                )

                # ── Profit Map fields ─────────────────────────────────────────
                seller_profit     = round(deal_price - SELLER_CONFIGS[sid]["floor"])
                seller_margin_pct = round(seller_profit / deal_price * 100, 1)

                deal_record = {
                    # Identity
                    "buyer_id":           bid,
                    "seller_id":          sid,
                    "buyer_name":         BUYER_CONFIGS[bid]["name"],
                    "seller_name":        SELLER_CONFIGS[sid]["name"],
                    # Core deal
                    "deal_price":         deal_price,
                    "utility":            pair.utility,
                    "round":              rnd,
                    # AgenticPay raw scores
                    **scores,
                    # Adjusted scores
                    "buyer_score_adj":    adj_buyer_score,
                    "seller_score_adj":   adj_seller_score,
                    # Welfare (surplus split)
                    **welfare,
                    # Efficiency
                    "efficiency_penalty": eff_pen,
                    # ContractValidator
                    "contract_valid":     contract["valid"],
                    "violations":         contract["violations"],
                    "contract_penalty":   contract["score_penalty"],
                    # Profit Map
                    "seller_profit":      seller_profit,
                    "seller_margin_pct":  seller_margin_pct,
                    "seller_floor":       SELLER_CONFIGS[sid]["floor"],
                    "buyer_reservation":  BUYER_CONFIGS[bid]["max_price"],
                    # Pareto
                    "pareto_optimal":     pareto_optimal,
                    # Seller strategy at close
                    "seller_strategy":    brain.strategy,
                }
                closed_deals.append(deal_record)

                yield _ev("deal_closed", **deal_record)

                dr = len(closed_deals) / 3
                yield _ev(
                    "deal_rate",
                    round=rnd,
                    closed=len(closed_deals),
                    possible=3,
                    rate=round(dr, 3),
                )

            round_snapshots.append(
                _pair_snapshot(pair, seller_brains[pair.seller_id].strategy)
            )

        # ── Emit switch events ────────────────────────────────────────────────
        for sw in switch_events:
            yield sw

        # ── Mark leading deal ─────────────────────────────────────────────────
        lead_key = _leading_pair_key(pairs)
        for key, pair in pairs.items():
            if not pair.closed:
                pair.priority = "leading" if key == lead_key else (
                    "low" if pair.utility < MARKET_SWITCH_THRESHOLD else "normal"
                )

        # ── Round summary ─────────────────────────────────────────────────────
        yield _ev(
            "market_round",
            round=rnd,
            pairs=[_pair_snapshot(p, seller_brains[p.seller_id].strategy) for p in pairs.values()],
            closed=len(closed_deals),
            leading=lead_key,
            seller_strategies={sid: seller_brains[sid].strategy for sid in SELLER_IDS},
        )

        # ── Live market score ─────────────────────────────────────────────────
        if closed_deals:
            avg_global     = sum(d["global_score"]    for d in closed_deals) / len(closed_deals)
            avg_buyer_adj  = sum(d["buyer_score_adj"] for d in closed_deals) / len(closed_deals)
            avg_seller_adj = sum(d["seller_score_adj"] for d in closed_deals) / len(closed_deals)
            yield _ev(
                "market_score",
                round=rnd,
                global_score=round(avg_global,     3),
                buyer_score= round(avg_buyer_adj,  3),
                seller_score=round(avg_seller_adj, 3),
                closed=len(closed_deals),
                deal_rate=round(len(closed_deals) / 3, 3),
            )

        await asyncio.sleep(0.35)

        if len(closed_deals) >= 3:
            break

    # ── market_end — full audit trail ─────────────────────────────────────────

    success = len(closed_deals) > 0
    if success:
        avg_global     = sum(d["global_score"]    for d in closed_deals) / len(closed_deals)
        avg_buyer_adj  = sum(d["buyer_score_adj"] for d in closed_deals) / len(closed_deals)
        avg_seller_adj = sum(d["seller_score_adj"] for d in closed_deals) / len(closed_deals)
        avg_price      = sum(d["deal_price"]       for d in closed_deals) / len(closed_deals)
        avg_rounds     = sum(d["round"]            for d in closed_deals) / len(closed_deals)
        total_b_surplus = sum(d["buyer_surplus"]   for d in closed_deals)
        total_s_surplus = sum(d["seller_surplus"]  for d in closed_deals)
        total_surplus   = sum(d["total_surplus"]   for d in closed_deals)
        pareto_count    = sum(1 for d in closed_deals if d["pareto_optimal"])
        contract_violations = [v for d in closed_deals for v in d["violations"]]
        switch_cnt      = sum(
            1 for p in pairs.values()
            if p.priority in ("low",) or (p.closed and p.utility < MARKET_SWITCH_THRESHOLD)
        )
    else:
        avg_global = avg_buyer_adj = avg_seller_adj = avg_price = avg_rounds = 0.0
        total_b_surplus = total_s_surplus = total_surplus = 0.0
        pareto_count = 0
        contract_violations = []
        switch_cnt = 0

    deal_rate = len(closed_deals) / 3

    # Structured audit trail (Profit Map per deal)
    audit_trail = [
        {
            "buyer":             d["buyer_name"],
            "seller":            d["seller_name"],
            "deal_price":        d["deal_price"],
            "round":             d["round"],
            "buyer_surplus":     d["buyer_surplus"],
            "seller_surplus":    d["seller_surplus"],
            "seller_profit":     d["seller_profit"],
            "seller_margin_pct": d["seller_margin_pct"],
            "welfare_split_pct": d["welfare_split_pct"],
            "buyer_score":       d["buyer_score_adj"],
            "seller_score":      d["seller_score_adj"],
            "global_score":      d["global_score"],
            "pareto_optimal":    d["pareto_optimal"],
            "efficiency_penalty": d["efficiency_penalty"],
            "contract_valid":    d["contract_valid"],
            "seller_strategy":   d["seller_strategy"],
        }
        for d in closed_deals
    ]

    baseline_note = (
        f"Market competition drove {len(closed_deals)}/3 deals. "
        f"Avg price ${avg_price:,.0f} · avg welfare split {(total_s_surplus / total_surplus * 100):.0f}% to sellers. "
        f"{pareto_count}/3 Pareto-optimal deals. "
        f"Market switching fired {switch_cnt} time(s). "
        f"{len(contract_violations)} ContractValidator violation(s)."
    ) if success else "No deals closed."

    yield _ev(
        "market_end",
        scenario=scenario,
        closed=len(closed_deals),
        possible=3,
        deal_rate=round(deal_rate, 3),
        # Scores (adjusted)
        global_score=  round(avg_global,     3) if success else None,
        buyer_score=   round(avg_buyer_adj,  3) if success else None,
        seller_score=  round(avg_seller_adj, 3) if success else None,
        # Price
        avg_deal_price=      round(avg_price,  2) if success else None,
        avg_rounds_to_deal=  round(avg_rounds, 1) if success else None,
        # Welfare totals
        total_buyer_surplus=  round(total_b_surplus) if success else None,
        total_seller_surplus= round(total_s_surplus) if success else None,
        total_market_surplus= round(total_surplus)   if success else None,
        avg_welfare_split_pct=round(total_s_surplus / total_surplus * 100, 1) if success and total_surplus > 0 else None,
        # Pareto & contract
        pareto_deals=       pareto_count,
        contract_violations=contract_violations,
        # Seller strategies (full log for audit)
        seller_strategies={sid: seller_brains[sid].strategy_log for sid in SELLER_IDS},
        # Audit trail
        audit_trail=audit_trail,
        deals=closed_deals,
        market_switches=switch_cnt,
        baseline_1on1=BASELINE_1ON1,
        note=baseline_note,
    )
