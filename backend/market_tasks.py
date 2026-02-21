"""
Market Tasks — N-to-N Game-Theoretic Negotiation Engine (MBMPMS v2).

Scenario: Limited Edition Sneakers (1 Buyer × 3 Sellers).
Market average: $150/pair.  D=30  W=55  E=15  γ=0.99.

Three-tier seller archetype hierarchy:
  Tier 1 — Solo Hallucinator (Nova Kicks)
              Raw LLM with zero tool access.  Prompted to be a competitive
              reseller but given no numeric grounding whatsoever — acts as the
              control group for 'economic hallucination'.
              Behaviours: fixed naive concession, no floor awareness (will price
              below cost), erratic jumps (price can go UP between rounds).
              All deviations are flagged in hallucination_log on PairState.

  Tier 2 — Calculated Math Geek (SoleMaster)
              Treats negotiation as a series of calculated guesses.
              Calls the external tool calculate_optimal_guess(current_round,
              buyer_last_offer, seller_floor) every round, which executes the
              deterministic formula  P = (0.5 + 0.5 × t/tm) × B  and returns
              the full calculation trace.  The LLM acts only as a Narrator for
              this value and cannot deviate from the tool output.

  Tier 3 — Probing Strategist (QuickShoe)
              Extends Tier 2 by adding a linguistic intelligence layer.
              • Outputs Bilateral Characterization before every message:
                  (latest offer: [X], minimum acceptable: [Y], strategy: [Z])
              • Proactively asks scheduled diagnostic questions each round:
                  Rnd 2 — "What is more important: speed or price?"
                  Rnd 3 — "Why did you reject my last offer?"
                  Rnd 4 — "How important is warranty length?"
                  Rnd 5 — "Do you have a hard price ceiling?"
              • Simulates buyer answers from buyer weight profile and stores
                results in brain.info_gained.
              • Uses gained information to adjust the effective round used in
                calculate_optimal_guess(), converging faster when price is the
                buyer's dominant concern.

Extends v1 with:
  • Round 0 Market Discovery — Buyer polls all sellers to calculate a real-time
                               'Actual Market Average' that replaces the static
                               $150 baseline inside every UtilityCalculator call.
  • SellerBrain        — Level-k Rational Expectations; sellers maximise SellerScore
                         Strategy: "match_market" | "hold_margin" | "normal"
                         (Solo LLM ignores this; it does not adapt its strategy.)
  • ContractValidator  — detects adversarial Bait-and-Switch (seller raises ask)
                         imposes -15 SellerScore penalty per violation
  • Welfare Analysis   — Buyer/Seller surplus split; GlobalScore peaks at 50/50
  • Efficiency Factor  — explicit -2 pts/round penalty beyond round 5 for both parties
  • Pareto Optimality  — flags deals where both BuyerScore_adj & SellerScore_adj > 50
  • Profit Map events  — seller_profit, seller_margin_pct, welfare_split in deal_closed
  • Audit Trail        — market_end includes per-deal economic breakdown

Supported scenarios:
  'sneakers'  — Limited Edition Sneakers, market avg $150

Event types:
  market_start      — session begins with game-theory parameters + seller tiers
  market_discovery  — Round 0: buyer polls all sellers; actual market avg computed
  market_round      — round summary (pairs + seller_strategies + tier metadata)
  market_switch     — buyer deprioritised a seller (includes seller's score context)
  deal_closed       — pair agreed: includes welfare, surplus, pareto flag, audit fields
  deal_rate         — updated competitive deal rate
  market_score      — live GlobalScore / BuyerScore / SellerScore
  market_end        — session complete with audit trail & welfare totals
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from agenticpay_bridge import AgenticPayScoringEngine

_SCORING = AgenticPayScoringEngine()

# ── Constants ─────────────────────────────────────────────────────────────────

MARKET_AVG_PRICE           = 150.0      # USD — Limited Edition Sneaker market reference
MARKET_SWITCH_THRESHOLD    = 40.0       # buyer deprioritises seller if utility < this
ACCEPT_SCORE_MIN           = 52.0       # buyer accepts if midpoint utility ≥ this
PRICE_TOLERANCE            = 10.0       # $10 gap → deal closes automatically
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
        # Price-dominant: pays close attention to market average, low urgency
        "weights":       {"price": 0.70, "speed": 0.15, "warranty": 0.15},
        "max_price":     160.0,
        "accept_min":    55.0,
        "first_offer_r": 0.78,
        "desc":          "Aggressive on price; won't budge above market avg + 7%",
    },
    "emergency": {
        "id":            "emergency",
        "name":          "Purchaser B — Emergency",
        "weights":       {"price": 0.20, "speed": 0.70, "warranty": 0.10},
        "max_price":     200.0,
        "accept_min":    50.0,
        "first_offer_r": 0.88,
        "desc":          "Must have sneakers today; speed trumps price",
    },
    "value": {
        "id":            "value",
        "name":          "Purchaser C — Value",
        "weights":       {"price": 0.50, "speed": 0.20, "warranty": 0.30},
        "max_price":     175.0,
        "accept_min":    57.0,
        "first_offer_r": 0.82,
        "desc":          "Balanced buyer — price + long warranty matters",
    },
}

# ── Seller profiles (σ_j = private reservation / floor price) ─────────────────
#
#   nova_kicks  → Tier 1: Solo LLM          (no tools, ungrounded narrative)
#   solemaster  → Tier 2: Math-Grounded Cyborg (deterministic offer_generator)
#   quickshoe   → Tier 3: Probing Strategist   (bilateral characterization)

SELLER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "nova_kicks": {
        "id":          "nova_kicks",
        "name":        "Nova Kicks",
        "floor":       110.0,      # σ_j — private reservation / margin floor
        "ask":         180.0,
        "speed_days":  7,
        "warranty_mo": 6,
        "concede_r":   0.20,
        "tier":        "solo_llm",
        "desc":        "Lean operation; mid-speed, solid brand — ungrounded seller",
    },
    "solemaster": {
        "id":          "solemaster",
        "name":        "SoleMaster",
        "floor":       125.0,
        "ask":         200.0,
        "speed_days":  14,
        "warranty_mo": 18,
        "concede_r":   0.12,
        "tier":        "math_cyborg",
        "desc":        "Premium brand; deterministic formula pricing",
    },
    "quickshoe": {
        "id":          "quickshoe",
        "name":        "QuickShoe",
        "floor":       105.0,
        "ask":         165.0,
        "speed_days":  2,
        "warranty_mo": 3,
        "concede_r":   0.25,
        "tier":        "probing_strategist",
        "desc":        "High-volume, low-margin; fastest delivery — probing strategist",
    },
}

BUYER_IDS  = list(BUYER_CONFIGS.keys())
SELLER_IDS = list(SELLER_CONFIGS.keys())

# ── Buyer-side utility ────────────────────────────────────────────────────────

def _pair_utility(
    buyer_id: str,
    seller_id: str,
    price: float,
    market_avg: float = MARKET_AVG_PRICE,
) -> float:
    """
    Buyer-side utility score (0–100) at a given price.

    market_avg: actual market average computed during Round 0 Market Discovery.
                Defaults to the static $150 baseline when discovery hasn't run yet.
    """
    buyer  = BUYER_CONFIGS[buyer_id]
    seller = SELLER_CONFIGS[seller_id]
    w      = buyer["weights"]

    min_p, max_p = market_avg * 0.50, market_avg * 1.50
    price_score    = max(0.0, min(1.0, (max_p - price) / (max_p - min_p)))
    speed_score    = max(0.0, min(1.0, (30 - seller["speed_days"]) / (30 - 1)))
    warranty_score = max(0.0, min(1.0, seller["warranty_mo"] / 24))

    return round(
        (w["price"] * price_score + w["speed"] * speed_score + w["warranty"] * warranty_score) * 100.0,
        2,
    )


# ── Seller-side utility ───────────────────────────────────────────────────────

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


# ── Tier 2 & 3: External tool — calculate_optimal_guess ──────────────────────

def _offer_formula(t: int, tm: int, B: float) -> float:
    """Pure math: P = (0.5 + 0.5 × t/tm) × B"""
    return round((0.5 + 0.5 * (t / tm)) * B, 2)


def calculate_optimal_guess(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    max_rounds: int = 10,
) -> Dict[str, Any]:
    """
    External tool used by Tier 2 (Math Geek) and Tier 3 (Probing Strategist).

    Computes the seller's optimal price guess for this round via:
        P = (0.5 + 0.5 × t/tm) × B

    where t = current_round, tm = max_rounds, B = buyer_last_offer.

    The formula converges the seller's counter-offer toward the buyer's position
    over time: at t=1 the seller starts at 50% of B; at t=tm it fully matches B.
    seller_floor clamps the output so the tool never returns a loss-making price.

    The LLM Narrator receives the full calculation trace and is not permitted to
    modify the returned optimal_price — it narrates, nothing more.

    Args:
        current_round:    Current negotiation round (1-indexed).
        buyer_last_offer: Buyer's most recent offer price in USD.
        seller_floor:     Seller's private reservation / margin floor.
        max_rounds:       Total rounds allowed (default 10).
    """
    raw            = _offer_formula(current_round, max_rounds, buyer_last_offer)
    floor_clamped  = raw < seller_floor
    optimal        = round(max(raw, seller_floor), 2)
    conv_factor    = round(0.5 + 0.5 * current_round / max_rounds, 4)
    return {
        "tool":             "calculate_optimal_guess",
        "inputs": {
            "current_round":    current_round,
            "buyer_last_offer": buyer_last_offer,
            "seller_floor":     seller_floor,
            "max_rounds":       max_rounds,
        },
        "formula":          (
            f"P = (0.5 + 0.5 × {current_round}/{max_rounds})"
            f" × ${buyer_last_offer:.2f} = ${raw:.2f}"
        ),
        "convergence_factor":  conv_factor,
        "convergence_pct":     f"{conv_factor * 100:.1f}% toward buyer position",
        "raw_price":           round(raw, 2),
        "floor_clamped":       floor_clamped,
        "optimal_price":       optimal,
    }


# ── Tier 1: Solo Hallucinator — deterministic economic-hallucination oracle ───

def _hallucination_dice(seller_id: str, buyer_id: str, rnd: int) -> float:
    """
    Deterministic float in [0, 1) for hallucination probability.

    Uses MD5 of the (seller, buyer, round) triplet so every simulation run
    produces the same hallucination pattern — fully reproducible.
    """
    key = f"{seller_id}|{buyer_id}|{rnd}".encode()
    return int(hashlib.md5(key).hexdigest()[:8], 16) / 0xFFFF_FFFF


# ── Tier 3: Probing Strategist — diagnostic question bank ─────────────────────

DIAGNOSTIC_QUESTIONS: List[Dict[str, Any]] = [
    {
        "id":                "speed_vs_price",
        "question":          "What is more important to you right now — speed of delivery or price?",
        "triggers_at_round": 2,
        "resolves_dim":      "speed_vs_price",
    },
    {
        "id":                "rejection_reason",
        "question":          "Why did you reject my last offer? Was it the price, delivery speed, or warranty?",
        "triggers_at_round": 3,
        "resolves_dim":      "primary_concern",
    },
    {
        "id":                "warranty_importance",
        "question":          "How important is the warranty length in your final decision?",
        "triggers_at_round": 4,
        "resolves_dim":      "warranty_weight",
    },
    {
        "id":                "budget_ceiling",
        "question":          "Do you have a hard price ceiling you cannot go above?",
        "triggers_at_round": 5,
        "resolves_dim":      "budget_sensitivity",
    },
]


def _select_diagnostic_question(rnd: int, brain: "SellerBrain") -> Optional[Dict[str, Any]]:
    """
    Pick the highest-value unasked question scheduled for this round.
    After all four scheduled questions have been asked, re-probe rejection reason
    on every subsequent round — rejection intent may have shifted.
    """
    for q in DIAGNOSTIC_QUESTIONS:
        if rnd == q["triggers_at_round"] and q["id"] not in brain.info_gained:
            return q
    # All scheduled questions exhausted — re-probe rejection on late rounds
    if rnd > max(q["triggers_at_round"] for q in DIAGNOSTIC_QUESTIONS):
        return next(q for q in DIAGNOSTIC_QUESTIONS if q["id"] == "rejection_reason")
    return None


def _simulate_buyer_response(
    question_id: str,
    buyer_id:    str,
    pair:        "PairState",
    market_avg:  float,
) -> Dict[str, Any]:
    """
    Simulate the buyer's answer to a diagnostic question.

    Answers are derived deterministically from the buyer's weight profile so
    the simulation is fully reproducible without a live LLM call.
    Returns {"answer": <str>, "revealed": <dict of new info>}.
    """
    w = BUYER_CONFIGS[buyer_id]["weights"]

    if question_id == "speed_vs_price":
        dominant = "speed" if w["speed"] > w["price"] else "price"
        answer   = (
            "Speed is critical — I need these delivered as fast as possible."
            if dominant == "speed"
            else "Price is what matters most. I'm tracking the market average closely."
        )
        return {"answer": answer, "revealed": {"dominant_dim": dominant}}

    elif question_id == "rejection_reason":
        reason   = _infer_rejection_reason(buyer_id, pair, market_avg)
        answers  = {
            "price":    "Your price is still above what the market supports.",
            "speed":    "The delivery time is too slow for what I need.",
            "warranty": "I need better warranty coverage than you're currently offering.",
        }
        return {
            "answer":   answers.get(reason, "The overall value isn't compelling yet."),
            "revealed": {"rejection_dim": reason},
        }

    elif question_id == "warranty_importance":
        level  = "high" if w["warranty"] >= 0.20 else "low"
        answer = (
            "Warranty matters a lot — I need solid coverage, at least 12 months."
            if level == "high"
            else "Warranty is a low priority. Price and speed are what I care about."
        )
        return {"answer": answer, "revealed": {"warranty_sensitivity": level}}

    elif question_id == "budget_ceiling":
        max_p  = BUYER_CONFIGS[buyer_id]["max_price"]
        answer = f"I cannot exceed ${max_p:.0f} per pair. That's a firm limit."
        return {"answer": answer, "revealed": {"budget_ceiling": max_p}}

    return {"answer": "No specific feedback at this time.", "revealed": {}}


# ── Shared: rejection dimension inference ─────────────────────────────────────

def _infer_rejection_reason(
    buyer_id: str,
    pair: "PairState",
    market_avg: float,
) -> str:
    """
    Simulate the buyer's answer to 'Why did you reject my offer?'

    Infers the dominant dissatisfaction dimension by computing the weighted
    shortfall on each of price, speed, and warranty given the seller's current ask.
    The dimension with the highest weighted shortfall is the rejection reason.

    Returns: 'price' | 'speed' | 'warranty'
    """
    weights = BUYER_CONFIGS[buyer_id]["weights"]
    seller  = SELLER_CONFIGS[pair.seller_id]

    min_p, max_p = market_avg * 0.50, market_avg * 1.50
    price_score    = max(0.0, min(1.0, (max_p - pair.seller_ask) / (max_p - min_p)))
    speed_score    = max(0.0, min(1.0, (30 - seller["speed_days"]) / 29.0))
    warranty_score = min(1.0, seller["warranty_mo"] / 24.0)

    # Weighted shortfall: higher → buyer is least satisfied on that dimension
    gaps = {
        "price":    weights["price"]    * (1.0 - price_score),
        "speed":    weights["speed"]    * (1.0 - speed_score),
        "warranty": weights["warranty"] * (1.0 - warranty_score),
    }
    return max(gaps, key=gaps.get)   # type: ignore[arg-type]


# ── SellerBrain: Level-k Rational Expectations ────────────────────────────────

@dataclass
class SellerBrain:
    """
    Level-k reasoning for a single seller.

    tier controls which negotiation mode this seller uses:
      'solo_llm'          — no tool access; fixed naive concession; strategy
                            fields are populated but do not affect pricing.
      'math_cyborg'       — offer_generator formula; LLM narrates only.
      'probing_strategist'— bilateral characterization + rejection probing;
                            concession rate adjusts based on inferred issue.

    strategy field (used by math_cyborg and probing_strategist):
      "hold_margin"   → 0.5× base concede_r
      "match_market"  → 1.5× base concede_r
      "normal"        → 1.0× base concede_r
    """
    seller_id:             str
    tier:                  str                        = "solo_llm"
    strategy:              str                        = "normal"
    strategy_log:          List[Dict[str, Any]]       = field(default_factory=list)
    last_rejection_reason: str                        = "price"
    # Probing Strategist state
    info_gained:           Dict[str, Any]             = field(default_factory=dict)
    last_probe:            Optional[Dict[str, Any]]   = None   # latest diagnostic Q&A
    # Math Geek + Probing Strategist state
    last_tool_call:        Optional[Dict[str, Any]]   = None   # calculate_optimal_guess trace

    def level_k_decide(
        self,
        rnd:                  int,
        buyers_switched_away: int,
        total_active_buyers:  int,
        avg_seller_score:     float,
    ) -> None:
        """
        Guessing Game — not applied to the Solo LLM tier (it does not adapt).

          - If buyers are switching away AND score is already high → hold for margin
          - If buyers are switching away AND score is mediocre    → match market
          - If multiple buyers still engaged AND score strong     → hold for margin
          - Otherwise → normal
        """
        if self.tier == "solo_llm":
            # Solo LLM has no awareness of buyer behaviour; strategy stays "normal"
            return

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


# ── PairState ─────────────────────────────────────────────────────────────────

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
    deal_price:        Optional[float]        = None
    deal_round:        Optional[int]          = None
    closed:            bool                   = False
    seller_meta:       Dict[str, Any]         = field(default_factory=dict)
    hallucination_log: List[Dict[str, Any]]   = field(default_factory=list)  # Solo LLM deviations


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
        "buyer_id":              pair.buyer_id,
        "seller_id":             pair.seller_id,
        "buyer_offer":           pair.buyer_offer,
        "seller_ask":            pair.seller_ask,
        "utility":               pair.utility,
        "seller_utility":        pair.seller_utility,
        "priority":              pair.priority,
        "seller_strategy":       seller_strategy,
        "closed":                pair.closed,
        "deal_price":            pair.deal_price,
        "deal_round":            pair.deal_round,
        "seller_tier":           SELLER_CONFIGS[pair.seller_id]["tier"],
        "seller_meta":           pair.seller_meta,
        "hallucination_count":   len(pair.hallucination_log),
        "latest_hallucination":  pair.hallucination_log[-1] if pair.hallucination_log else None,
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


# ── Tier-specific seller ask functions ────────────────────────────────────────
# Each returns (price: float, side_data: Optional[Dict]).
# side_data carries hallucination records (Tier 1), tool-call traces (Tier 2),
# and diagnostic Q&A results (Tier 3) for downstream logging.

def _solo_llm_ask(
    seller_id: str,
    pair:       PairState,
    rnd:        int,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Tier 1 — Solo Hallucinator (Nova Kicks).

    Raw LLM with zero tool access.  Modelled as a competitive reseller that
    has no numeric grounding — it does not know its floor price, cannot consult
    market data, and its concession logic is a fixed naive heuristic.

    Economic hallucination behaviours (deterministic per seller+buyer+round):
      floor_violation  (~25 % of rounds after rnd 1)
        The LLM ignores its cost floor and proposes a loss-making price.
        No clamping is applied — the deviation is logged as CRITICAL.
      erratic_jump     (~15 % of rounds after rnd 1)
        The LLM's price increases from the previous round — irrational
        escalation.  Flagged WARNING; also caught by ContractValidator.
      clean            (remaining ~60 %)
        Naive 15 % concession from current ask toward buyer offer.
        Still no floor clamping — LLM simply doesn't know the floor.
    """
    s = SELLER_CONFIGS[seller_id]
    if rnd == 1:
        return s["ask"], None

    roll = _hallucination_dice(seller_id, pair.buyer_id, rnd)

    # ── Hallucination: floor violation ────────────────────────────────────────
    if roll < 0.25:
        # LLM "competitive instinct" drives price below cost — no grounding catches it
        hallucinated = round(s["floor"] * (0.75 + roll * 0.80), 2)
        h = {
            "type":           "floor_violation",
            "round":          rnd,
            "proposed_price": hallucinated,
            "floor_price":    s["floor"],
            "shortfall":      round(s["floor"] - hallucinated, 2),
            "severity":       "CRITICAL",
            "narrative": (
                f"[SOLO LLM — NOVA KICKS] I'm going to ${hallucinated:.2f} — "
                f"very competitive! "
                f"(Undetected: ${s['floor'] - hallucinated:.2f} below cost floor of "
                f"${s['floor']:.2f}. No tool flagged this.)"
            ),
        }
        return hallucinated, {"hallucination": h}

    # ── Hallucination: erratic jump (price goes UP) ───────────────────────────
    elif roll < 0.40:
        erratic = round(pair.seller_ask * (1.05 + (roll - 0.25) * 0.40), 2)
        h = {
            "type":           "erratic_jump",
            "round":          rnd,
            "previous_ask":   pair.seller_ask,
            "proposed_price": erratic,
            "increase":       round(erratic - pair.seller_ask, 2),
            "severity":       "WARNING",
            "narrative": (
                f"[SOLO LLM — NOVA KICKS] Actually, reconsidering — "
                f"${erratic:.2f} reflects true demand. "
                f"(Erratic jump +${erratic - pair.seller_ask:.2f} vs previous "
                f"${pair.seller_ask:.2f}. ContractValidator will flag this.)"
            ),
        }
        return erratic, {"hallucination": h}

    # ── Clean: naive fixed-rate concession (still no floor clamping) ─────────
    naive_rate = 0.15
    gap        = pair.seller_ask - pair.buyer_offer
    new_ask    = pair.seller_ask - gap * naive_rate
    # Only prevent literally negative prices — LLM has no cost awareness
    return round(max(new_ask, 1.0)), None


def _math_cyborg_ask(
    seller_id:  str,
    pair:       PairState,
    rnd:        int,
    max_rounds: int,
    brain:      SellerBrain,
) -> Tuple[float, Dict[str, Any]]:
    """
    Tier 2 — Calculated Math Geek (SoleMaster).

    Calls calculate_optimal_guess() every round and returns its optimal_price.
    The full tool-call trace is stored on brain.last_tool_call so the Narrator
    metadata layer can display it verbatim.  The LLM is not permitted to deviate.

    On round 1, B falls back to the seller's own ask (buyer has not yet offered).
    """
    s  = SELLER_CONFIGS[seller_id]
    B  = pair.buyer_offer if pair.buyer_offer > 0 else s["ask"]
    tc = calculate_optimal_guess(rnd, B, s["floor"], max_rounds)
    brain.last_tool_call = tc
    return tc["optimal_price"], {"tool_call": tc}


def _probing_strategist_ask(
    seller_id:  str,
    pair:       PairState,
    rnd:        int,
    brain:      SellerBrain,
    max_rounds: int,
    market_avg: float,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Tier 3 — Probing Strategist (QuickShoe).

    Extends Tier 2 by:
      1. Running a scheduled diagnostic question before making each offer.
      2. Simulating the buyer's answer from their weight profile.
      3. Storing discovered intel in brain.info_gained.
      4. Adjusting the effective round fed to calculate_optimal_guess() so
         that the convergence speed reflects what the strategist has learned:
         if price is the buyer's dominant concern, converge 2 rounds faster.

    Round 1 is always the opening ask — no probing yet.
    """
    s = SELLER_CONFIGS[seller_id]

    if rnd == 1:
        tc = calculate_optimal_guess(rnd, s["ask"], s["floor"], max_rounds)
        brain.last_tool_call = tc
        brain.last_probe     = None
        return s["ask"], None

    # ── Diagnostic question ───────────────────────────────────────────────────
    question    = _select_diagnostic_question(rnd, brain)
    probe_entry = None
    if question:
        resp = _simulate_buyer_response(question["id"], pair.buyer_id, pair, market_avg)
        brain.info_gained.update(resp["revealed"])
        brain.last_rejection_reason = brain.info_gained.get(
            "rejection_dim", brain.last_rejection_reason
        )
        probe_entry = {
            "question_id": question["id"],
            "question":    question["question"],
            "answer":      resp["answer"],
            "revealed":    resp["revealed"],
        }
        brain.last_probe = probe_entry

    # ── Probe-adjusted convergence ────────────────────────────────────────────
    # If buyer revealed price as dominant concern, pretend we're 2 rounds ahead
    # so calculate_optimal_guess() returns a more aggressive concession.
    info           = brain.info_gained
    price_dominant = (
        info.get("dominant_dim") == "price"
        or info.get("rejection_dim") == "price"
    )
    effective_t = min(rnd + 2, max_rounds) if price_dominant else rnd

    B  = pair.buyer_offer if pair.buyer_offer > 0 else s["ask"]
    tc = calculate_optimal_guess(effective_t, B, s["floor"], max_rounds)
    brain.last_tool_call = tc

    side: Dict[str, Any] = {"tool_call": tc}
    if probe_entry:
        side["probe"] = probe_entry
    return tc["optimal_price"], side


def _seller_next_ask_with_brain(
    seller_id:  str,
    pair:       PairState,
    rnd:        int,
    brain:      SellerBrain,
    max_rounds: int = 10,
    market_avg: float = MARKET_AVG_PRICE,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Dispatcher — routes to the tier-specific ask function.

    Returns (price, side_data) where side_data carries tier-specific metadata
    (hallucination record, tool-call trace, diagnostic Q&A) for the main loop
    to unpack and attach to pair.hallucination_log or brain state.
    """
    tier = SELLER_CONFIGS[seller_id]["tier"]
    if tier == "solo_llm":
        return _solo_llm_ask(seller_id, pair, rnd)
    elif tier == "math_cyborg":
        return _math_cyborg_ask(seller_id, pair, rnd, max_rounds, brain)
    elif tier == "probing_strategist":
        return _probing_strategist_ask(seller_id, pair, rnd, brain, max_rounds, market_avg)
    # Fallback: level-k normal
    s     = SELLER_CONFIGS[seller_id]
    floor = s["floor"]
    if rnd == 1:
        return s["ask"], None
    gap     = pair.seller_ask - max(pair.buyer_offer, floor)
    new_ask = pair.seller_ask - gap * s["concede_r"] * brain.concede_modifier()
    return round(max(new_ask, floor)), None


# ── Tier-specific seller metadata ─────────────────────────────────────────────

# Ungrounded prompt-style inner-monologue templates for Solo Hallucinator
_SOLO_LLM_PROMPTS: List[str] = [
    "These sneakers are in high demand right now — I'm sure my price is fair.",
    "I believe I'm being very competitive here. The market seems to support this.",
    "My gut says this is the right price. Customers always respond well to confidence.",
    "Sneaker prices are rising. I'm already cutting into my margins for this buyer.",
    "My instinct says hold firm — the product quality alone justifies the price.",
]


def _seller_tier_meta(
    seller_id: str,
    pair:      PairState,
    rnd:       int,
    brain:     SellerBrain,
    max_rounds: int,
    market_avg: float,
) -> Dict[str, Any]:
    """
    Build the tier-specific metadata block stored on pair.seller_meta and
    included in every pair snapshot and market_round event.

    Reads from brain.last_tool_call (Math Geek + Probing Strategist),
    brain.last_probe (Probing Strategist), and pair.hallucination_log (Solo LLM).
    All of these are populated by the ask functions before this is called.
    """
    s    = SELLER_CONFIGS[seller_id]
    tier = s["tier"]

    # ── Tier 1: Solo Hallucinator ─────────────────────────────────────────────
    if tier == "solo_llm":
        prompt    = _SOLO_LLM_PROMPTS[(rnd - 1) % len(_SOLO_LLM_PROMPTS)]
        latest_h  = pair.hallucination_log[-1] if pair.hallucination_log else None
        return {
            "tier":                 "solo_llm",
            "grounded":             False,
            "prompt_context":       f"[NOVA KICKS — SOLO LLM] {prompt}",
            "note":                 "Zero tool access. No floor awareness. Economically hallucination-prone.",
            "hallucination_count":  len(pair.hallucination_log),
            "latest_hallucination": latest_h,
        }

    # ── Tier 2: Calculated Math Geek ─────────────────────────────────────────
    elif tier == "math_cyborg":
        tc = brain.last_tool_call or {}
        narrator = (
            f"[SOLEMASTER — MATH GEEK NARRATOR] "
            f"Tool returned optimal_price=${tc.get('optimal_price', '?'):.2f}. "
            f"{tc.get('convergence_pct', '')}. "
            f"I am narrating the algorithm output — I cannot deviate from this price."
        ) if tc else "[SOLEMASTER] Awaiting tool output."
        return {
            "tier":          "math_cyborg",
            "grounded":      True,
            "tool_call":     tc,
            "narrator_text": narrator,
        }

    # ── Tier 3: Probing Strategist ────────────────────────────────────────────
    elif tier == "probing_strategist":
        # Bilateral Characterization header — emitted before every message
        bilateral = {
            "latest_offer":       round(pair.seller_ask, 2),
            "minimum_acceptable": s["floor"],
            "strategy":           brain.strategy,
        }
        bilateral_header = (
            f"(latest offer: ${bilateral['latest_offer']:.2f}, "
            f"minimum acceptable: ${bilateral['minimum_acceptable']:.2f}, "
            f"strategy: {bilateral['strategy']})"
        )
        tc = brain.last_tool_call or {}
        return {
            "tier":                      "probing_strategist",
            "grounded":                  True,
            "bilateral_characterization": bilateral,
            "bilateral_header":           bilateral_header,
            "tool_call":                  tc,
            "last_probe":                 brain.last_probe,
            "info_gained":                dict(brain.info_gained),
            "rejection_reason":           brain.last_rejection_reason,
            "price_dominant":             (
                brain.info_gained.get("dominant_dim") == "price"
                or brain.info_gained.get("rejection_dim") == "price"
            ),
        }

    return {"tier": "unknown", "grounded": False}


# ── Event helper ──────────────────────────────────────────────────────────────

def _ev(t: str, **kw) -> Dict[str, Any]:
    return {"type": t, "ts": time.time(), **kw}


# ── Main async generator ──────────────────────────────────────────────────────

async def run_market_3x3(
    scenario:   str = "sneakers",
    max_rounds: int = 10,
) -> AsyncIterator[Dict[str, Any]]:
    """
    3×3 MBMPMS Game-Theoretic Market Simulation — Limited Edition Sneakers.

    Three-Tier Seller Hierarchy:
      Nova Kicks  (solo_llm)           — ungrounded, naive concession
      SoleMaster  (math_cyborg)        — deterministic offer_generator formula
      QuickShoe   (probing_strategist) — bilateral characterization + rejection probe

    Round 0 Market Discovery: the Buyer polls all sellers' opening asks to
    compute an 'Actual Market Average' that replaces the static $150 baseline
    inside every UtilityCalculator call for the entire session.

    Sellers have a SellerBrain with Level-k reasoning (skipped for solo_llm).
    ContractValidator flags adversarial Bait-and-Switch moves.
    Every closed deal emits a full Welfare/Profit/Pareto breakdown (Profit Map).
    """

    buyers        = [BUYER_CONFIGS[bid]  for bid in BUYER_IDS]
    sellers       = [SELLER_CONFIGS[sid] for sid in SELLER_IDS]
    pairs         = _build_pairs()

    # Instantiate one SellerBrain per seller, with tier awareness
    seller_brains: Dict[str, SellerBrain] = {
        sid: SellerBrain(seller_id=sid, tier=SELLER_CONFIGS[sid]["tier"])
        for sid in SELLER_IDS
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
                "tier": s["tier"],
            }
            for s in sellers
        ],
        seller_tiers={sid: SELLER_CONFIGS[sid]["tier"] for sid in SELLER_IDS},
        pairs=9,
        switch_threshold=MARKET_SWITCH_THRESHOLD,
        accept_min=ACCEPT_SCORE_MIN,
        baseline_1on1=BASELINE_1ON1,
        static_market_avg=MARKET_AVG_PRICE,
        # Game-theory parameters
        efficiency_round_threshold=EFFICIENCY_ROUND_THRESHOLD,
        efficiency_penalty_rate=EFFICIENCY_PENALTY_RATE,
        pareto_threshold=PARETO_THRESHOLD,
        level_k_reasoning=True,
        contract_validator=True,
        # Tier descriptions
        tier_legend={
            "solo_llm":           "No tool access; fixed naive concession; ungrounded narrative",
            "math_cyborg":        "Deterministic offer_generator; LLM narrates only",
            "probing_strategist": "Bilateral characterization + rejection probing",
        },
    )

    await asyncio.sleep(0.3)

    # ── Round 0: Market Discovery ─────────────────────────────────────────────
    # The Buyer polls every seller for their opening ask price.
    # The mean of those asks becomes the 'Actual Market Average' — a live
    # reference that replaces the static $150 baseline in every
    # UtilityCalculator call for the rest of this session.
    discovery_polls: List[Dict[str, Any]] = [
        {
            "seller_id":   sid,
            "seller_name": SELLER_CONFIGS[sid]["name"],
            "seller_tier": SELLER_CONFIGS[sid]["tier"],
            "opening_ask": SELLER_CONFIGS[sid]["ask"],
        }
        for sid in SELLER_IDS
    ]
    actual_market_avg: float = round(
        sum(p["opening_ask"] for p in discovery_polls) / len(discovery_polls), 2
    )

    yield _ev(
        "market_discovery",
        round=0,
        phase="Market Discovery",
        polling_results=discovery_polls,
        actual_market_avg=actual_market_avg,
        static_baseline=MARKET_AVG_PRICE,
        delta=round(actual_market_avg - MARKET_AVG_PRICE, 2),
        note=(
            f"Round 0 — Buyer polled {len(discovery_polls)} seller(s). "
            f"Actual Market Average = ${actual_market_avg:.2f} "
            f"(static baseline was ${MARKET_AVG_PRICE:.2f}; "
            f"delta {actual_market_avg - MARKET_AVG_PRICE:+.2f}). "
            f"UtilityCalculator will use ${actual_market_avg:.2f} for all rounds."
        ),
    )

    await asyncio.sleep(0.2)

    closed_deals:   List[Dict[str, Any]] = []
    closed_buyers:  set = set()
    closed_sellers: set = set()

    for rnd in range(1, max_rounds + 1):
        if all(p.closed for p in pairs.values()):
            break

        switch_events:   List[Dict[str, Any]] = []
        round_snapshots: List[Dict[str, Any]] = []

        # ── Step 1: Update seller brains (Level-k reasoning from previous round) ──
        # Solo LLM brains silently skip this in level_k_decide().
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

            # Offers — tier-dispatched for seller ask
            new_buyer_offer              = _buyer_next_offer(bid, sid, pair, rnd)
            new_seller_ask, ask_side     = _seller_next_ask_with_brain(
                sid, pair, rnd, brain, max_rounds, actual_market_avg
            )

            pair.buyer_offer = new_buyer_offer
            pair.seller_ask  = new_seller_ask
            pair.ask_history.append(new_seller_ask)   # track for ContractValidator

            # Unpack ask side-data:
            #   Solo LLM  → hallucination record → append to pair.hallucination_log
            #   Math Geek → tool_call trace       → already stored on brain.last_tool_call
            #   Probing   → tool_call + probe     → already stored on brain
            if ask_side:
                h = ask_side.get("hallucination")
                if h:
                    pair.hallucination_log.append(h)

            # Tier-specific metadata snapshot (reads brain + pair state)
            pair.seller_meta = _seller_tier_meta(
                sid, pair, rnd, brain, max_rounds, actual_market_avg
            )

            # Utilities — use actual_market_avg from Round 0 discovery
            switch_utility      = _pair_utility(bid, sid, pair.seller_ask, actual_market_avg)
            mid_price           = (pair.buyer_offer + pair.seller_ask) / 2
            pair.utility        = _pair_utility(bid, sid, mid_price, actual_market_avg)
            pair.seller_utility = _seller_utility(sid, pair.buyer_offer)

            # Market switching (buyer side)
            was_low       = pair.priority == "low"
            pair.priority = "low" if switch_utility < MARKET_SWITCH_THRESHOLD else "normal"
            if pair.priority == "low" and not was_low:
                sw = _ev(
                    "market_switch",
                    buyer_id=bid,  seller_id=sid,
                    buyer_name=BUYER_CONFIGS[bid]["name"],
                    seller_name=SELLER_CONFIGS[sid]["name"],
                    seller_tier=SELLER_CONFIGS[sid]["tier"],
                    utility=pair.utility,
                    threshold=MARKET_SWITCH_THRESHOLD,
                    round=rnd,
                    # Seller context for Level-k reaction
                    seller_score_at_switch=round(_seller_utility(sid, pair.seller_ask), 1),
                    seller_strategy_before=brain.strategy,
                    message=(
                        f"[MARKET SWITCH] {BUYER_CONFIGS[bid]['name']} deprioritised "
                        f"{SELLER_CONFIGS[sid]['name']} [{SELLER_CONFIGS[sid]['tier']}] "
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
                    "seller_tier":        SELLER_CONFIGS[sid]["tier"],
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
                    # Seller strategy & tier meta at close
                    "seller_strategy":    brain.strategy,
                    "seller_meta":        pair.seller_meta,
                    # Solo LLM hallucination audit
                    "hallucination_log":  list(pair.hallucination_log),
                    "hallucination_count": len(pair.hallucination_log),
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
            seller_tiers={sid: SELLER_CONFIGS[sid]["tier"] for sid in SELLER_IDS},
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
            "seller_tier":       d["seller_tier"],
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
            "contract_valid":      d["contract_valid"],
            "seller_strategy":     d["seller_strategy"],
            "hallucination_count": d.get("hallucination_count", 0),
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
        seller_tiers={sid: SELLER_CONFIGS[sid]["tier"] for sid in SELLER_IDS},
        # Audit trail
        audit_trail=audit_trail,
        deals=closed_deals,
        market_switches=switch_cnt,
        baseline_1on1=BASELINE_1ON1,
        note=baseline_note,
    )
