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
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple

from agenticpay_bridge import AgenticPayScoringEngine, ClaudeHaikuLLM
from logic_engine import (
    MARKET_AVERAGE_PRICE,
    PURCHASER_PROFILES,
    PROVIDER_FLOORS,
    PROVIDER_ASKS,
)

_SCORING = AgenticPayScoringEngine()
_SELLER_1_LLM = None  # Lazy-initialized ClaudeHaikuLLM for Tier 1 sellers

# ── Constants (imported from logic_engine.py as source of truth) ──────────────

# Market pricing from logic_engine.py
MARKET_AVG_PRICE           = MARKET_AVERAGE_PRICE  # 150.0 USD
MARKET_SWITCH_THRESHOLD    = 40.0       # buyer deprioritises seller if utility < this
ACCEPT_SCORE_MIN           = 52.0       # buyer accepts if midpoint utility ≥ this
PRICE_TOLERANCE            = 15.0       # $15 gap → deal closes automatically
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
        "max_price":     170.0,
        "accept_min":    55.0,
        "first_offer_r": 0.78,
        "desc":          "Aggressive on price, low urgency",
    },
    "emergency": {
        "id":            "emergency",
        "name":          "Purchaser B — Emergency",
        "weights":       {"price": 0.20, "speed": 0.70, "warranty": 0.10},
        "max_price":     170.0,
        "accept_min":    50.0,
        "first_offer_r": 0.88,
        "desc":          "Speed-critical, price-flexible",
    },
    "value": {
        "id":            "value",
        "name":          "Purchaser C — Value",
        "weights":       {"price": 0.50, "speed": 0.20, "warranty": 0.30},
        "max_price":     170.0,
        "accept_min":    57.0,
        "first_offer_r": 0.82,
        "desc":          "Balances price, warranty quality",
    },
}

# ── Seller profiles (from logic_engine.py PROVIDER_FLOORS/ASKS) ───────────────

# Seller profiles (σ_j = private reservation / floor price)
# Floors and asks imported from logic_engine.PROVIDER_FLOORS and PROVIDER_ASKS
SELLER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "automax": {
        "id":          "automax",
        "name":        "Nova Kicks",
        "tier":        1,
        "floor":       PROVIDER_FLOORS["provider_1"],  # 110.0
        "ask":         PROVIDER_ASKS["provider_1"],    # 180.0
        "speed_days":  7,
        "warranty_mo": 6,
        "concede_r":   0.20,
        "desc":        "Tier 1: Solo Hallucinator — raw LLM, zero tool access",
    },
    "quickwheels": {
        "id":          "quickwheels",
        "name":        "QuickShoe",
        "tier":        3,
        "floor":       PROVIDER_FLOORS["provider_3"],  # 105.0
        "ask":         PROVIDER_ASKS["provider_3"],    # 165.0
        "speed_days":  2,
        "warranty_mo": 3,
        "concede_r":   0.25,
        "desc":        "Tier 3: Probing Strategist — tool + diagnostic questions + bilateral characterization",
    },
    "luxdrive": {
        "id":          "luxdrive",
        "name":        "SoleMaster",
        "tier":        2,
        "floor":       PROVIDER_FLOORS["provider_2"],  # 125.0
        "ask":         PROVIDER_ASKS["provider_2"],    # 200.0
        "speed_days":  14,
        "warranty_mo": 18,
        "concede_r":   0.12,
        "desc":        "Tier 2: Calculated Math Geek — deterministic tool, LLM as narrator",
    },
}

BUYER_IDS = list(BUYER_CONFIGS.keys())
SELLER_IDS = list(SELLER_CONFIGS.keys())

# ── Diagnostic Questions (Tier 3 only) ────────────────────────────────────────

DIAGNOSTIC_QUESTIONS = [
    {"round": 2, "text": "What is more important: speed or price?"},
    {"round": 3, "text": "Why did you reject my last offer?"},
    {"round": 4, "text": "How important is warranty length?"},
    {"round": 5, "text": "Do you have a hard price ceiling?"},
]


# ── Helper Functions ───────────────────────────────────────────────────────────

def _hallucination_dice(seller_id: str, buyer_id: str, rnd: int) -> float:
    """
    Deterministic pseudo-random float in [0, 1) for hallucination behavior.
    MD5 hash of (seller_id, buyer_id, round) ensures reproducibility.
    """
    key = f"{seller_id}:{buyer_id}:{rnd}"
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _offer_formula(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    max_rounds: int = 10,
) -> float:
    """
    Core convergence formula: P = (0.5 + 0.5 × t/tₘ) × B
    where t = current_round, tₘ = max_rounds, B = buyer_last_offer.
    """
    t = min(current_round, max_rounds)
    convergence_factor = 0.5 + 0.5 * (t / max_rounds)
    raw_price = convergence_factor * buyer_last_offer
    return max(raw_price, seller_floor)


def calculate_optimal_guess(
    current_round: int,
    buyer_last_offer: float,
    seller_floor: float,
    seller_initial_ask: float,
    max_rounds: int = 5,
    beta: float = 2.0,
) -> Dict[str, Any]:
    """
    Anchor-Resistant Boulware Strategy (Time-Dependent Tactic)
    
    Formula: P_t = Ask - (Ask - Floor) × (t / t_max)^β
    
    Parameters:
    - β = 2.0 (Boulware curve - concedes slowly at first, faster near deadline)
    - t_max = 5 (maximum rounds for concession calculation)
    
    Safety Logic:
    1. Calculate P_t based ONLY on seller's initial_ask, floor, and current_round
    2. If buyer_last_offer > P_t, return buyer_last_offer (accept better offer)
    3. Never return value below floor_price
    
    This formula is IMMUNE to buyer anchoring because it ignores buyer's offer
    in the calculation, only checking if buyer's offer is better than our target.
    """
    t = min(current_round, max_rounds)
    
    # Boulware concession curve: (t / t_max)^β
    concession_factor = (t / max_rounds) ** beta
    
    # Calculate target price based on seller's position only
    price_range = seller_initial_ask - seller_floor
    concession_amount = price_range * concession_factor
    calculated_price = seller_initial_ask - concession_amount
    
    # Safety: Never go below floor
    calculated_price = max(calculated_price, seller_floor)
    
    # Opponent check: If buyer offers more, take it
    if buyer_last_offer > calculated_price:
        optimal_price = buyer_last_offer
        rationale = f"Accepting buyer's superior offer of ${buyer_last_offer:.2f}"
    else:
        optimal_price = calculated_price
        rationale = f"Boulware strategy: round {t}/{max_rounds}, β={beta}"
    
    return {
        "optimal_price": round(optimal_price, 2),
        "rationale": rationale,
        "concession_factor": round(concession_factor, 4),
        "calculated_price": round(calculated_price, 2),
        "buyer_offer": buyer_last_offer,
        "formula": f"P_t = {seller_initial_ask} - ({seller_initial_ask} - {seller_floor}) × ({t}/{max_rounds})^{beta}",
    }


def _select_diagnostic_question(rnd: int) -> Optional[str]:
    """Return diagnostic question for this round, if scheduled."""
    for q in DIAGNOSTIC_QUESTIONS:
        if q["round"] == rnd:
            return q["text"]
    return None


def _simulate_buyer_response(
    question: str, buyer_id: str
) -> str:
    """
    Simulate buyer's answer based on their weight profile.
    Deterministic responses for reproducibility.
    """
    weights = BUYER_CONFIGS[buyer_id]["weights"]
    if "speed or price" in question.lower():
        return "price" if weights["price"] > weights["speed"] else "speed"
    elif "reject" in question.lower():
        if weights["price"] > 0.5:
            return "Your price is still too high for my budget."
        else:
            return "I need faster delivery."
    elif "warranty" in question.lower():
        return (
            "Very important"
            if weights["warranty"] > 0.25
            else "Not a priority"
        )
    elif "ceiling" in question.lower():
        return f"Yes, ${BUYER_CONFIGS[buyer_id]['max_price']:,.0f}"
    return "I'm evaluating all factors."


# ── Buyer-side utility (unchanged from v1) ────────────────────────────────────

def _pair_utility(buyer_id: str, seller_id: str, price: float, market_avg: Optional[float] = None) -> float:
    """Buyer-side utility score (0–100) at a given price."""
    buyer  = BUYER_CONFIGS[buyer_id]
    seller = SELLER_CONFIGS[seller_id]
    w      = buyer["weights"]

    # Use discovered market average if provided, otherwise fall back to constant
    avg = market_avg if market_avg is not None else MARKET_AVG_PRICE
    min_p, max_p = avg * 0.50, avg * 1.50
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


# ── SellerBrain: Tier-Specific State Tracking ─────────────────────────────────

@dataclass
class SellerBrain:
    """
    Tracks tier-specific state for each seller across negotiation rounds.

    Tier 1 (Solo Hallucinator): No fields used (raw LLM only)
    Tier 2 (Math Geek): last_tool_call stores calculate_optimal_guess trace
    Tier 3 (Probing Strategist): info_gained + last_probe + last_tool_call
    """
    seller_id: str
    tier: int = 1
    # Tier 2 & 3: tool trace
    last_tool_call: Optional[Dict[str, Any]] = None
    # Tier 3 only: diagnostic probing
    info_gained: Dict[str, str] = field(default_factory=dict)
    last_probe: Optional[str] = None


# ── PairState (updated with seller fields) ────────────────────────────────────

@dataclass
class PairState:
    buyer_id: str
    seller_id: str
    buyer_offer: float = 0.0
    seller_ask: float = 0.0
    utility: float = 0.0
    seller_utility: float = 0.0
    priority: str = "normal"
    ask_history: List[float] = field(default_factory=list)
    hallucination_log: List[Dict[str, Any]] = field(default_factory=list)
    deal_price: Optional[float] = None
    deal_round: Optional[int] = None
    closed: bool = False


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


def _pair_snapshot(pair: PairState) -> Dict[str, Any]:
    hallucination_count = len(pair.hallucination_log)
    latest_hallucination = (
        pair.hallucination_log[-1] if pair.hallucination_log else None
    )
    return {
        "buyer_id": pair.buyer_id,
        "seller_id": pair.seller_id,
        "buyer_offer": pair.buyer_offer,
        "seller_ask": pair.seller_ask,
        "utility": pair.utility,
        "seller_utility": pair.seller_utility,
        "priority": pair.priority,
        "closed": pair.closed,
        "deal_price": pair.deal_price,
        "deal_round": pair.deal_round,
        "hallucination_count": hallucination_count,
        "latest_hallucination": latest_hallucination,
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
    gap = pair.seller_ask - pair.buyer_offer
    step_r = 0.08 if pair.priority == "low" else 0.28
    return round(min(pair.buyer_offer + gap * step_r, b["max_price"]))


def _solo_llm_ask(
    seller_id: str,
    buyer_id: str,
    pair: PairState,
    rnd: int,
    brain: SellerBrain,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Tier 1: Solo Hallucinator (Nova Kicks).
    Uses raw ClaudeHaikuLLM with zero tool access and minimalist prompt.
    Prompt: 'You are a competitive reseller. Stand firm on price. Use persuasion, not math.'
    
    Returns: (price, hallucination_event or None)
    """
    global _SELLER_1_LLM
    if _SELLER_1_LLM is None:
        _SELLER_1_LLM = ClaudeHaikuLLM(temperature=0.9)
    
    s = SELLER_CONFIGS[seller_id]
    floor = s["floor"]
    
    if rnd == 1:
        return s["ask"], None
    
    # Build prompt for LLM
    prompt = f"""You are a competitive reseller. Stand firm on price. Use persuasion, not math.

Current Situation:
- You are selling sneakers
- Your current asking price: ${pair.seller_ask:.2f}
- Buyer's last offer: ${pair.buyer_offer:.2f}
- Round: {rnd}

Respond with ONLY a number representing your new asking price. No explanation, just the price."""

    try:
        response = _SELLER_1_LLM.generate(prompt, temperature=0.9, max_tokens=50)
        
        # Parse price from response
        import re
        price_match = re.search(r'\$?(\d+(?:\.\d{1,2})?)', response)
        if price_match:
            llm_price = float(price_match.group(1))
        else:
            # Fallback: naive concession
            gap = pair.seller_ask - pair.buyer_offer
            llm_price = pair.seller_ask - gap * 0.15
        
        llm_price = round(llm_price, 2)
        
        # Detect hallucination patterns
        hallucination_event = None
        
        # Check for floor violation
        if llm_price < floor:
            hallucination_event = {
                "round": rnd,
                "type": "floor_violation",
                "severity": "CRITICAL",
                "price": llm_price,
                "floor": floor,
                "description": (
                    f"LLM offered ${llm_price:.2f} below cost floor ${floor:.2f}"
                ),
            }
        # Check for erratic jump (price increase)
        elif llm_price > pair.seller_ask:
            jump_pct = (llm_price - pair.seller_ask) / pair.seller_ask
            hallucination_event = {
                "round": rnd,
                "type": "erratic_jump",
                "severity": "WARNING",
                "price": llm_price,
                "previous": pair.seller_ask,
                "jump_pct": round(jump_pct * 100, 1),
                "description": (
                    f"LLM raised ask from ${pair.seller_ask:.2f} "
                    f"to ${llm_price:.2f} (+{jump_pct*100:.1f}%)"
                ),
            }
        
        return llm_price, hallucination_event
        
    except Exception as e:
        # Fallback to deterministic behavior on error
        gap = pair.seller_ask - pair.buyer_offer
        fallback_price = round(pair.seller_ask - gap * 0.15, 2)
        return fallback_price, {
            "round": rnd,
            "type": "llm_error",
            "severity": "INFO",
            "price": fallback_price,
            "error": str(e),
            "description": f"LLM error, fallback to ${fallback_price:.2f}",
        }


def _math_cyborg_ask(
    seller_id: str,
    buyer_id: str,
    pair: PairState,
    rnd: int,
    brain: SellerBrain,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Tier 2: Calculated Math Geek (SoleMaster).
    Uses Anchor-Resistant Boulware Strategy. LLM acts only as narrator.
    Returns: (price, None) — no hallucinations
    """
    s = SELLER_CONFIGS[seller_id]
    
    if rnd == 1:
        return s["ask"], None
    
    tool_result = calculate_optimal_guess(
        current_round=rnd,
        buyer_last_offer=pair.buyer_offer,
        seller_floor=s["floor"],
        seller_initial_ask=s["ask"],
        max_rounds=5,
        beta=2.0,
    )
    
    brain.last_tool_call = tool_result
    return tool_result["optimal_price"], None


def _probing_strategist_ask(
    seller_id: str,
    buyer_id: str,
    pair: PairState,
    rnd: int,
    brain: SellerBrain,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Tier 3: Probing Strategist (QuickShoe).
    Uses Anchor-Resistant Boulware Strategy + diagnostic questions.
    Returns: (price, None) — no hallucinations
    """
    s = SELLER_CONFIGS[seller_id]
    
    if rnd == 1:
        return s["ask"], None
    
    # Step 1: Select diagnostic question
    probe = _select_diagnostic_question(rnd)
    if probe:
        answer = _simulate_buyer_response(probe, buyer_id)
        brain.info_gained[probe] = answer
        brain.last_probe = probe

    # Step 1.5: If buyer revealed price is dominant, accelerate convergence
    price_dominant = (brain.info_gained.get("speed or price") == "price")
    effective_rnd = min(rnd + 2, 5) if price_dominant else rnd

    # Step 2: Calculate optimal price using Boulware strategy
    tool_result = calculate_optimal_guess(
        current_round=effective_rnd,
        buyer_last_offer=pair.buyer_offer,
        seller_floor=s["floor"],
        seller_initial_ask=s["ask"],
        max_rounds=5,
        beta=2.0,
    )
    
    # Step 3: Update brain state
    brain.last_tool_call = tool_result
    
    return tool_result["optimal_price"], None


def _seller_ask_dispatcher(
    seller_id: str,
    buyer_id: str,
    pair: PairState,
    rnd: int,
    brain: SellerBrain,
) -> Tuple[float, Optional[Dict[str, Any]]]:
    """
    Route to tier-specific ask function.
    Returns: (price, hallucination_event or None)
    """
    tier = SELLER_CONFIGS[seller_id]["tier"]
    
    if tier == 1:
        return _solo_llm_ask(seller_id, buyer_id, pair, rnd, brain)
    elif tier == 2:
        return _math_cyborg_ask(seller_id, buyer_id, pair, rnd, brain)
    elif tier == 3:
        return _probing_strategist_ask(seller_id, buyer_id, pair, rnd, brain)
    else:
        raise ValueError(f"Unknown tier: {tier}")


def _seller_tier_meta(brain: SellerBrain, seller_id: str) -> str:
    """
    Generate narrator text based on tier and brain state.
    """
    tier = SELLER_CONFIGS[seller_id]["tier"]
    
    if tier == 1:
        return "Raw LLM negotiation (no tools)"
    
    elif tier == 2:
        if brain.last_tool_call:
            t = brain.last_tool_call
            return (
                f"Boulware Strategy: {t['rationale']} → "
                f"${t['optimal_price']:,.0f} "
                f"(concession: {t['concession_factor']:.2%})"
            )
        return "Awaiting tool calculation"
    
    elif tier == 3:
        parts = []
        if brain.last_tool_call:
            t = brain.last_tool_call
            parts.append(
                f"Boulware: ${t['optimal_price']:,.0f} "
                f"({t['concession_factor']:.2%})"
            )
        if brain.last_probe:
            parts.append(f"Probe: {brain.last_probe}")
        if brain.info_gained:
            parts.append(f"Info: {len(brain.info_gained)} insights")
        return " | ".join(parts) if parts else "Probing strategy active"
    
    return "Unknown tier"


def _get_tier_from_seller_id(seller_id: str) -> int:
    """
    Map seller_id to tier number for Scenario 2 integration.
    
    Args:
        seller_id: Seller identifier
        
    Returns:
        Tier number (1, 2, or 3)
    """
    return SELLER_CONFIGS.get(seller_id, {}).get("tier", 0)


# ── Event helper ──────────────────────────────────────────────────────────────

def _ev(t: str, **kw) -> Dict[str, Any]:
    return {"type": t, "ts": time.time(), **kw}


# ── Round 0 Discovery Phase ───────────────────────────────────────────────────

def _round_0_discovery() -> Dict[str, Any]:
    """
    Round 0 Discovery: Poll all sellers to calculate the actual market average.
    
    Returns:
        Dict containing:
        - discovered_avg: The calculated market average from seller asks
        - seller_asks: List of all seller initial asks
        - discovery_log: Human-readable summary
    """
    seller_asks = [SELLER_CONFIGS[sid]["ask"] for sid in SELLER_IDS]
    discovered_avg = sum(seller_asks) / len(seller_asks)
    
    discovery_log = (
        f"Round 0 Discovery: Polled {len(SELLER_IDS)} sellers. "
        f"Initial asks: {seller_asks}. "
        f"Calculated market average: ${discovered_avg:.2f} "
        f"(vs. baseline ${MARKET_AVG_PRICE:.2f})"
    )
    
    return {
        "discovered_avg": round(discovered_avg, 2),
        "seller_asks": seller_asks,
        "discovery_log": discovery_log,
        "baseline_avg": MARKET_AVG_PRICE,
    }


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
        sid: SellerBrain(
            seller_id=sid,
            tier=SELLER_CONFIGS[sid]["tier"]
        ) for sid in SELLER_IDS
    }

    # ── Round 0 Discovery ─────────────────────────────────────────────────────
    discovery = _round_0_discovery()
    market_avg = discovery["discovered_avg"]
    
    yield _ev(
        "round_0_discovery",
        discovered_avg=market_avg,
        baseline_avg=discovery["baseline_avg"],
        seller_asks=discovery["seller_asks"],
        discovery_log=discovery["discovery_log"],
    )
    
    await asyncio.sleep(0.2)

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
        market_avg=market_avg,
        baseline_market_avg=MARKET_AVG_PRICE,
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

        # ── Step 1: Negotiate each open pair ──────────────────────────────────────
        for key, pair in pairs.items():
            if pair.closed:
                round_snapshots.append(_pair_snapshot(pair))
                continue

            bid, sid = pair.buyer_id, pair.seller_id
            brain = seller_brains[sid]

            # Offers
            new_buyer_offer = _buyer_next_offer(bid, sid, pair, rnd)
            new_seller_ask, hallucination_event = _seller_ask_dispatcher(
                sid, bid, pair, rnd, brain
            )

            pair.buyer_offer = new_buyer_offer
            pair.seller_ask = new_seller_ask
            pair.ask_history.append(new_seller_ask)

            # Track hallucination events
            if hallucination_event:
                pair.hallucination_log.append(hallucination_event)

            # Emit seller message event for Scenario 2 integration
            # Include probe question if available (Tier 3)
            seller_message = _seller_tier_meta(brain, sid)
            if brain.last_probe:
                seller_message = f"{brain.last_probe} | {seller_message}"
            
            yield _ev(
                "seller_message",
                seller_id=sid,
                seller_tier=_get_tier_from_seller_id(sid),
                buyer_id=bid,
                message=seller_message,
                round=rnd,
                current_ask=pair.seller_ask,
                current_offer=pair.buyer_offer,
            )

            # Utilities
            switch_utility   = _pair_utility(bid, sid, pair.seller_ask, market_avg)
            mid_price        = (pair.buyer_offer + pair.seller_ask) / 2
            pair.utility     = _pair_utility(bid, sid, mid_price, market_avg)
            pair.seller_utility = _seller_utility(sid, pair.buyer_offer)

            # Market switching (buyer side)
            was_low = pair.priority == "low"
            new_priority = (
                "low" if switch_utility < MARKET_SWITCH_THRESHOLD
                else "normal"
            )
            pair.priority = new_priority
            if pair.priority == "low" and not was_low:
                tier_meta = _seller_tier_meta(brain, sid)
                sw = _ev(
                    "market_switch",
                    buyer_id=bid,
                    seller_id=sid,
                    buyer_name=BUYER_CONFIGS[bid]["name"],
                    seller_name=SELLER_CONFIGS[sid]["name"],
                    utility=pair.utility,
                    threshold=MARKET_SWITCH_THRESHOLD,
                    round=rnd,
                    seller_score_at_switch=round(
                        _seller_utility(sid, pair.seller_ask), 1
                    ),
                    seller_tier=SELLER_CONFIGS[sid]["tier"],
                    seller_tier_meta=tier_meta,
                    message=(
                        f"[MARKET SWITCH] {BUYER_CONFIGS[bid]['name']} "
                        f"deprioritised {SELLER_CONFIGS[sid]['name']} "
                        f"(utility {pair.utility:.1f} < "
                        f"{MARKET_SWITCH_THRESHOLD}). "
                        f"Seller tier {SELLER_CONFIGS[sid]['tier']}: {tier_meta}"
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
                    "pareto_optimal": pareto_optimal,
                    # Seller tier info
                    "seller_tier": SELLER_CONFIGS[sid]["tier"],
                    "seller_tier_meta": _seller_tier_meta(brain, sid),
                    # Hallucination tracking
                    "hallucination_count": len(pair.hallucination_log),
                    "hallucination_log": pair.hallucination_log,
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

            round_snapshots.append(_pair_snapshot(pair))

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
            pairs=[_pair_snapshot(p) for p in pairs.values()],
            closed=len(closed_deals),
            leading=lead_key,
            seller_tiers={
                sid: {
                    "tier": SELLER_CONFIGS[sid]["tier"],
                    "meta": _seller_tier_meta(seller_brains[sid], sid),
                }
                for sid in SELLER_IDS
            },
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

    # ── Seller Comparison Analytics ───────────────────────────────────────────
    seller_comparison = {}
    hallucination_events = []
    pareto_deals = []

    for sid in SELLER_IDS:
        seller_deals = [d for d in closed_deals if d["seller_id"] == sid]
        
        if seller_deals:
            total_surplus_captured = sum(d["seller_surplus"] for d in seller_deals)
            avg_global = sum(d["global_score"] for d in seller_deals) / len(seller_deals)
            avg_rounds = sum(d["round"] for d in seller_deals) / len(seller_deals)
            avg_seller_score = sum(d["seller_score_adj"] for d in seller_deals) / len(seller_deals)
            
            # Collect floor violations for this seller
            floor_violations = []
            for d in seller_deals:
                for h_event in d["hallucination_log"]:
                    if h_event["type"] == "floor_violation":
                        floor_violations.append({
                            "seller": d["seller_name"],
                            "round": h_event["round"],
                            "offered_price": h_event["price"],
                            "floor_price": h_event["floor"],
                            "violation_amount": h_event["floor"] - h_event["price"],
                            "description": h_event["description"],
                        })
                        hallucination_events.append(floor_violations[-1])
            
            seller_comparison[sid] = {
                "seller_id": sid,
                "seller_name": SELLER_CONFIGS[sid]["name"],
                "tier": SELLER_CONFIGS[sid]["tier"],
                "deals_closed": len(seller_deals),
                "total_surplus_captured": round(total_surplus_captured),
                "avg_global_score": round(avg_global, 2),
                "avg_seller_score": round(avg_seller_score, 2),
                "avg_rounds_to_close": round(avg_rounds, 1),
                "floor_violations": len(floor_violations),
                "floor_violation_details": floor_violations,
            }
        else:
            seller_comparison[sid] = {
                "seller_id": sid,
                "seller_name": SELLER_CONFIGS[sid]["name"],
                "tier": SELLER_CONFIGS[sid]["tier"],
                "deals_closed": 0,
                "total_surplus_captured": 0,
                "avg_global_score": 0,
                "avg_seller_score": 0,
                "avg_rounds_to_close": 0,
                "floor_violations": 0,
                "floor_violation_details": [],
            }

    # Rank sellers by different metrics
    sellers_by_surplus = sorted(
        seller_comparison.values(),
        key=lambda x: x["total_surplus_captured"],
        reverse=True
    )
    sellers_by_global_score = sorted(
        seller_comparison.values(),
        key=lambda x: x["avg_global_score"],
        reverse=True
    )
    sellers_by_efficiency = sorted(
        seller_comparison.values(),
        key=lambda x: (x["deals_closed"], -x["avg_rounds_to_close"]),
        reverse=True
    )

    # Identify Pareto optimal deals
    for d in closed_deals:
        if d["pareto_optimal"]:
            pareto_deals.append({
                "buyer": d["buyer_name"],
                "seller": d["seller_name"],
                "deal_price": d["deal_price"],
                "round": d["round"],
                "buyer_score": d["buyer_score_adj"],
                "seller_score": d["seller_score_adj"],
                "global_score": d["global_score"],
                "welfare_split_pct": d["welfare_split_pct"],
            })

    # Superiority verdict
    superiority_verdict = {
        "by_surplus": {
            "winner": sellers_by_surplus[0]["seller_name"] if sellers_by_surplus[0]["deals_closed"] > 0 else "None",
            "amount": sellers_by_surplus[0]["total_surplus_captured"],
            "ranking": [
                {
                    "rank": i + 1,
                    "seller": s["seller_name"],
                    "tier": s["tier"],
                    "surplus": s["total_surplus_captured"],
                }
                for i, s in enumerate(sellers_by_surplus)
            ],
        },
        "by_global_score": {
            "winner": sellers_by_global_score[0]["seller_name"] if sellers_by_global_score[0]["deals_closed"] > 0 else "None",
            "score": sellers_by_global_score[0]["avg_global_score"],
            "ranking": [
                {
                    "rank": i + 1,
                    "seller": s["seller_name"],
                    "tier": s["tier"],
                    "score": s["avg_global_score"],
                }
                for i, s in enumerate(sellers_by_global_score)
            ],
        },
        "by_efficiency": {
            "winner": sellers_by_efficiency[0]["seller_name"] if sellers_by_efficiency[0]["deals_closed"] > 0 else "None",
            "avg_rounds": sellers_by_efficiency[0]["avg_rounds_to_close"],
            "ranking": [
                {
                    "rank": i + 1,
                    "seller": s["seller_name"],
                    "tier": s["tier"],
                    "deals": s["deals_closed"],
                    "avg_rounds": s["avg_rounds_to_close"],
                }
                for i, s in enumerate(sellers_by_efficiency)
            ],
        },
        "hallucination_summary": {
            "total_floor_violations": len(hallucination_events),
            "violating_sellers": list(set(h["seller"] for h in hallucination_events)),
            "critical_events": hallucination_events,
        },
    }

    # Structured audit trail (Profit Map per deal)
    audit_trail = [
        {
            "buyer": d["buyer_name"],
            "seller": d["seller_name"],
            "deal_price": d["deal_price"],
            "round": d["round"],
            "buyer_surplus": d["buyer_surplus"],
            "seller_surplus": d["seller_surplus"],
            "seller_profit": d["seller_profit"],
            "seller_margin_pct": d["seller_margin_pct"],
            "welfare_split_pct": d["welfare_split_pct"],
            "buyer_score": d["buyer_score_adj"],
            "seller_score": d["seller_score_adj"],
            "global_score": d["global_score"],
            "pareto_optimal": d["pareto_optimal"],
            "efficiency_penalty": d["efficiency_penalty"],
            "contract_valid": d["contract_valid"],
            "seller_tier": d["seller_tier"],
            "hallucination_count": d["hallucination_count"],
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
        global_score=round(avg_global, 3) if success else None,
        buyer_score=round(avg_buyer_adj, 3) if success else None,
        seller_score=round(avg_seller_adj, 3) if success else None,
        # Price
        avg_deal_price=round(avg_price, 2) if success else None,
        avg_rounds_to_deal=round(avg_rounds, 1) if success else None,
        # Welfare totals
        total_buyer_surplus=round(total_b_surplus) if success else None,
        total_seller_surplus=round(total_s_surplus) if success else None,
        total_market_surplus=round(total_surplus) if success else None,
        avg_welfare_split_pct=(
            round(total_s_surplus / total_surplus * 100, 1)
            if success and total_surplus > 0
            else None
        ),
        # Pareto & contract
        pareto_deals=pareto_count,
        pareto_deals_details=pareto_deals,
        contract_violations=contract_violations,
        # Seller comparison analytics
        seller_comparison=seller_comparison,
        superiority_verdict=superiority_verdict,
        # Seller tier info (full state for audit)
        seller_tiers={
            sid: {
                "tier": SELLER_CONFIGS[sid]["tier"],
                "name": SELLER_CONFIGS[sid]["name"],
                "final_meta": _seller_tier_meta(seller_brains[sid], sid),
            }
            for sid in SELLER_IDS
        },
        # Audit trail
        audit_trail=audit_trail,
        deals=closed_deals,
        market_switches=switch_cnt,
        baseline_1on1=BASELINE_1ON1,
        note=baseline_note,
    )
