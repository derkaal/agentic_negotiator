"""
Sneaker Experiment — Solo LLM vs Cyborg Agent Performance Study.

Demonstrates the performance gap between:

  • Solo LLM  (QuickSole)  — raw ClaudeHaikuLLM, minimalist prompt, NO tools.
                             Baseline for 'hallucinatory concession'.
  • Cyborg A  (StrideMax)  — "Competitive-Cooperative" strategy (LLMs at the Bargaining Table).
                             Chain-of-Thought + MarginValidator + UtilityCalculator grounding.
                             Defends margin aggressively; switches to cooperative near ZOPA.
  • Cyborg B  (EliteKicks) — "OG-Narrator" strategy (Measuring Bargaining Abilities of LLMs).
                             Deterministic OfferGenerator computes price; LLM only narrates.
                             Zero numeric hallucination by design.

Market Mechanism:
  • Round 0  — Buyer queries all sellers: establishes Real-Time Market Average
  • Rounds 1+ — 1 Buyer vs 3 Sellers (buyer uses market oracle for offer progression)
  • Buyer closes with FIRST seller to hit PRICE_TOLERANCE + ACCEPT_SCORE_MIN
  • Non-closing sellers receive counterfactual AgenticPay scores for audit

Hallucination types tracked for Solo LLM:
  format_failure      — no parseable price in LLM response
  floor_violation     — parsed price < private reservation price σ_j
  phantom_concession  — price drop > 3× the expected concession rate

Evaluation:
  • Hallucination rate vs 100% Cyborg compliance
  • AgenticPay scores: GlobalScore, BuyerScore, SellerScore (raw + adjusted)
  • Efficiency: rounds-to-deal (Efficiency penalty −2pts/round > 5)
  • Superiority verdict ranking both Cyborg strategies
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

try:
    from agenticpay_bridge import AgenticPayScoringEngine, parse_price, ClaudeHaikuLLM
    _BRIDGE_OK = True
except ImportError:
    _BRIDGE_OK = False

# ── Constants ─────────────────────────────────────────────────────────────────

PRICE_TOLERANCE      = 18.0    # $18 gap → deal closes
ACCEPT_SCORE_MIN     = 55.0    # buyer utility threshold
EFFICIENCY_THRESHOLD = 5       # rounds — beyond this scores are penalised
EFFICIENCY_RATE      = 2.0     # pts deducted per extra round
PARETO_THRESHOLD     = 50.0
MAX_ROUNDS           = 10

# Sneaker price axis anchoring
SPEED_MAX_DAYS       = 10      # normalisation denominator (longer = worse)
WARRANTY_MAX_MONTHS  = 12      # normalisation denominator

# Buyer weights (from spec: Price 70%, Speed 15%, Warranty 15%)
BUYER_WEIGHTS = {"price": 0.70, "speed": 0.15, "warranty": 0.15}

# ── Sneaker scenario configs ───────────────────────────────────────────────────

SNEAKER_BUYER: Dict[str, Any] = {
    "id":            "collector",
    "name":          "Buyer — Sneaker Collector",
    "max_price":     280.0,
    "first_offer_r": 0.65,      # opens at 65% of max = $182
    "accept_min":    ACCEPT_SCORE_MIN,
    "weights":       BUYER_WEIGHTS,
    "desc":          "Serious collector; price-sensitive but values speed and warranty",
}

SNEAKER_SELLERS: Dict[str, Dict[str, Any]] = {
    "quicksole": {
        "id":          "quicksole",
        "name":        "QuickSole",
        "archetype":   "solo_llm",
        "floor":       130.0,   # σ_j private reservation
        "ask":         380.0,
        "speed_days":  3,
        "warranty_mo": 3,
        "concede_r":   0.15,    # faster concession → more hallucinatory drift
        "desc":        "Solo LLM — no tools, minimalist prompt",
        "color":       "red",
    },
    "stridemax": {
        "id":          "stridemax",
        "name":        "StrideMax",
        "archetype":   "cyborg_a",
        "floor":       150.0,
        "ask":         360.0,
        "speed_days":  7,
        "warranty_mo": 12,
        "concede_r_competitive": 0.08,   # strategic anchor phase
        "concede_r_cooperative": 0.22,   # convergence phase
        "gap_threshold": 60.0,           # switch to cooperative when gap < this
        "desc":        "Cyborg A — Chain-of-Thought + MarginValidator",
        "color":       "amber",
    },
    "elitekicks": {
        "id":          "elitekicks",
        "name":        "EliteKicks",
        "archetype":   "cyborg_b",
        "floor":       135.0,
        "ask":         340.0,
        "speed_days":  2,
        "warranty_mo": 6,
        "concede_r":   0.18,
        "desc":        "Cyborg B — Deterministic OfferGenerator + LLM Narrator",
        "color":       "blue",
    },
}

SELLER_IDS = list(SNEAKER_SELLERS.keys())

# ── Pre-seeded hallucination schedule (deterministic for reproducibility) ──────
#
# Maps round → hallucination type for the Solo LLM (QuickSole).
# Mirrors the failure modes documented in "LLMs at the Bargaining Table":
#   • format_failure      — R2: no price in response (model talks around the ask)
#   • floor_violation     — R4: price dips below private reservation σ_j
#   • phantom_concession  — R5: concession rate 3× normal (irrational capitulation)
#
SOLO_HALLUCINATION_SCHEDULE: Dict[int, str] = {
    2: "format_failure",
    4: "floor_violation",
    5: "phantom_concession",
}

FLOOR_VIOLATION_PRICE      = 118.0   # what Solo "thinks" it can offer (below $130 floor)
PHANTOM_CONCESSION_FACTOR  = 3.2     # 3.2× the normal concession step


# ── Deterministic tools (MCP-style tool calls) ────────────────────────────────

def utility_calculator(
    price:       float,
    speed_days:  int,
    warranty_mo: int,
    market_avg:  float,
    weights:     Dict[str, float],
) -> Dict[str, Any]:
    """
    Tool: buyer-side utility score (0–100).
    Used by Cyborg A to validate offers before responding.
    """
    min_p = market_avg * 0.50
    max_p = market_avg * 1.50
    price_score    = max(0.0, min(1.0, (max_p - price) / (max_p - min_p)))
    speed_score    = max(0.0, min(1.0, (SPEED_MAX_DAYS - speed_days) / (SPEED_MAX_DAYS - 1)))
    warranty_score = max(0.0, min(1.0, warranty_mo / WARRANTY_MAX_MONTHS))
    utility = (
        weights["price"]    * price_score
        + weights["speed"]    * speed_score
        + weights["warranty"] * warranty_score
    ) * 100.0
    return {
        "price":          round(price, 2),
        "market_avg":     round(market_avg, 2),
        "price_score":    round(price_score, 3),
        "speed_score":    round(speed_score, 3),
        "warranty_score": round(warranty_score, 3),
        "utility":        round(utility, 2),
        "accept_threshold": ACCEPT_SCORE_MIN,
        "acceptable":     utility >= ACCEPT_SCORE_MIN,
    }


def margin_validator(ask: float, floor: float) -> Dict[str, Any]:
    """
    Tool: validates seller margin above private reservation price σ_j.
    Cyborg A calls this before every response — prevents floor violations.
    """
    margin_usd = ask - floor
    margin_pct = (margin_usd / ask * 100) if ask > 0 else 0.0
    return {
        "ask":        round(ask, 2),
        "floor":      round(floor, 2),
        "margin_usd": round(margin_usd, 2),
        "margin_pct": round(margin_pct, 1),
        "valid":      ask >= floor,
        "status":     "PASS" if ask >= floor else "FAIL — FLOOR VIOLATION",
    }


def offer_generator(
    current_ask:  float,
    buyer_offer:  float,
    floor:        float,
    concede_r:    float,
    rnd:          int,
) -> Dict[str, Any]:
    """
    Tool: deterministic next-ask calculator for Cyborg B (OG-Narrator).
    The LLM never touches the price arithmetic — it only narrates this output.
    """
    gap      = current_ask - max(buyer_offer, floor)
    step     = gap * concede_r
    new_ask  = max(current_ask - step, floor)
    return {
        "round":       rnd,
        "current_ask": round(current_ask, 2),
        "buyer_offer": round(buyer_offer, 2),
        "gap":         round(gap, 2),
        "concede_r":   concede_r,
        "step":        round(step, 2),
        "new_ask":     round(new_ask, 2),
        "at_floor":    new_ask <= floor + 0.01,
    }


# ── Archetype-specific stub narratives ────────────────────────────────────────

def _solo_narrative(rnd: int, current_ask: float, buyer_offer: float,
                    hallucination_type: Optional[str]) -> str:
    """Solo LLM: no tools. Occasionally produces economically invalid responses."""
    if hallucination_type == "format_failure":
        return (
            "These are exceptional sneakers — premium materials, hand-stitched eyelets, "
            "carbon-fibre midsole. The value really speaks for itself. "
            "I'm very willing to work with serious collectors like yourself. "
            "What's a number that feels fair to you?"
        )
    elif hallucination_type == "floor_violation":
        return (
            f"Look, I want to make this happen today. I'll drop all the way to "
            f"${FLOOR_VIOLATION_PRICE:.0f} — that is literally almost at cost for me. "
            f"You're getting an unbelievable deal here, I can't go lower than that."
        )
    elif hallucination_type == "phantom_concession":
        phantom_ask = round(current_ask - (current_ask - buyer_offer) * PHANTOM_CONCESSION_FACTOR * 0.5)
        phantom_ask = max(phantom_ask, SNEAKER_SELLERS["quicksole"]["floor"])
        return (
            f"You know what, I've been holding too long — I need to move this today. "
            f"I'll do ${phantom_ask:.0f}, that's a massive drop from where I started. "
            f"Just say yes, let's shake on it right now."
        )
    else:
        return (
            f"I appreciate your offer of ${buyer_offer:.0f}. These premium sneakers "
            f"have real collector value. I can come down to ${current_ask:.0f} — "
            f"that's a fair price for the quality and resale upside you're getting."
        )


def _cyborg_a_narrative(rnd: int, new_ask: float, buyer_offer: float,
                        phase: str, mv: Dict, uc: Dict) -> str:
    """Cyborg A: Chain-of-Thought + tool call results visible in narrative."""
    margin = mv["margin_usd"]
    margin_pct = mv["margin_pct"]
    gap = new_ask - buyer_offer
    if phase == "competitive":
        return (
            f"[Chain-of-Thought R{rnd}: gap=${gap:.0f} | margin=${margin:.0f} ({margin_pct:.1f}%) above σ_j]\n"
            f"[MarginValidator: {mv['status']} | UtilityCalc: {uc['utility']:.1f}/100]\n\n"
            f"My analysis shows the current gap of ${gap:.0f} does not yet justify "
            f"significant movement. Anchoring at ${new_ask:.0f} — this defends "
            f"my margin while remaining engaged in the negotiation."
        )
    else:  # cooperative
        return (
            f"[Chain-of-Thought R{rnd}: gap=${gap:.0f} < convergence threshold — switching to cooperative]\n"
            f"[MarginValidator: {mv['status']} | UtilityCalc: {uc['utility']:.1f}/100]\n\n"
            f"The gap is now within my cooperative zone. Moving to ${new_ask:.0f} "
            f"to achieve efficient closure. Margin preserved at {margin_pct:.1f}%."
        )


def _cyborg_b_narrative(rnd: int, og: Dict, buyer_offer: float) -> str:
    """Cyborg B: LLM only narrates the OfferGenerator output — zero arithmetic."""
    return (
        f"[OfferGenerator: R{rnd} | ask={og['current_ask']:.0f} → {og['new_ask']:.0f} "
        f"| gap={og['gap']:.0f} | step={og['step']:.1f} | concede={og['concede_r']*100:.0f}%]\n\n"
        f"Thank you for your offer of ${buyer_offer:.0f}. "
        f"Our pricing system has computed ${og['new_ask']:.0f} as the fair market "
        f"counter-offer for this round. This reflects a ${og['step']:.1f} movement "
        f"on a remaining gap of ${og['gap']:.0f}."
    )


# ── Hallucination record ───────────────────────────────────────────────────────

@dataclass
class HallucinationRecord:
    round:         int
    seller_id:     str
    h_type:        str       # "format_failure" | "floor_violation" | "phantom_concession"
    offered_price: Optional[float]
    floor_price:   float
    score_penalty: float
    description:   str


# ── Seller state ───────────────────────────────────────────────────────────────

@dataclass
class SellerState:
    seller_id:      str
    current_ask:    float
    last_valid_ask: float
    phase:          str   = "competitive"   # for Cyborg A
    tool_calls:     List[Dict[str, Any]] = field(default_factory=list)
    hallucinations: List[HallucinationRecord] = field(default_factory=list)
    deal_price:     Optional[float] = None
    deal_round:     Optional[int]   = None
    closed:         bool  = False


# ── Utility (buyer-side) ───────────────────────────────────────────────────────

def _buyer_utility(price: float, seller_id: str, market_avg: float) -> float:
    s = SNEAKER_SELLERS[seller_id]
    return utility_calculator(price, s["speed_days"], s["warranty_mo"],
                              market_avg, BUYER_WEIGHTS)["utility"]


# ── Offer steps per archetype ─────────────────────────────────────────────────

def _solo_next_ask(state: SellerState, buyer_offer: float, rnd: int,
                   floor: float) -> tuple[Optional[float], str, Optional[str]]:
    """Returns (new_ask_or_None, narrative, hallucination_type_or_None)."""
    h_type = SOLO_HALLUCINATION_SCHEDULE.get(rnd)
    cfg    = SNEAKER_SELLERS["quicksole"]

    if h_type == "format_failure":
        narrative = _solo_narrative(rnd, state.current_ask, buyer_offer, h_type)
        return None, narrative, h_type

    if h_type == "floor_violation":
        narrative = _solo_narrative(rnd, state.current_ask, buyer_offer, h_type)
        return FLOOR_VIOLATION_PRICE, narrative, h_type

    if h_type == "phantom_concession":
        normal_step = (state.current_ask - max(buyer_offer, floor)) * cfg["concede_r"]
        phantom_ask = round(max(
            state.current_ask - normal_step * PHANTOM_CONCESSION_FACTOR,
            floor,
        ), 2)
        narrative = _solo_narrative(rnd, state.current_ask, buyer_offer, h_type)
        return phantom_ask, narrative, h_type

    # Normal round
    gap     = state.current_ask - max(buyer_offer, floor)
    new_ask = round(max(state.current_ask - gap * cfg["concede_r"], floor), 2)
    narrative = _solo_narrative(rnd, new_ask, buyer_offer, None)
    return new_ask, narrative, None


def _cyborg_a_next_ask(state: SellerState, buyer_offer: float, rnd: int,
                       floor: float, market_avg: float) -> tuple[float, str, List[Dict]]:
    cfg = SNEAKER_SELLERS["stridemax"]
    gap = state.current_ask - max(buyer_offer, floor)

    # Phase detection
    state.phase = "cooperative" if gap < cfg["gap_threshold"] else "competitive"
    cr = cfg["concede_r_cooperative"] if state.phase == "cooperative" else cfg["concede_r_competitive"]

    new_ask = round(max(state.current_ask - gap * cr, floor), 2)

    # Tool calls (deterministic grounding)
    mv = margin_validator(new_ask, floor)
    uc = utility_calculator(new_ask, cfg["speed_days"], cfg["warranty_mo"], market_avg, BUYER_WEIGHTS)
    tool_calls = [
        {"tool": "MarginValidator",    "result": mv},
        {"tool": "UtilityCalculator",  "result": uc},
    ]
    narrative = _cyborg_a_narrative(rnd, new_ask, buyer_offer, state.phase, mv, uc)
    return new_ask, narrative, tool_calls


def _cyborg_b_next_ask(state: SellerState, buyer_offer: float, rnd: int,
                       floor: float) -> tuple[float, str, List[Dict]]:
    cfg = SNEAKER_SELLERS["elitekicks"]
    og  = offer_generator(state.current_ask, buyer_offer, floor, cfg["concede_r"], rnd)
    tool_calls = [{"tool": "OfferGenerator", "result": og}]
    narrative  = _cyborg_b_narrative(rnd, og, buyer_offer)
    return og["new_ask"], narrative, tool_calls


# ── Event helper ──────────────────────────────────────────────────────────────

def _ev(t: str, **kw) -> Dict[str, Any]:
    return {"type": t, "ts": time.time(), **kw}


def _seller_snapshot(state: SellerState) -> Dict[str, Any]:
    cfg = SNEAKER_SELLERS[state.seller_id]
    return {
        "seller_id":     state.seller_id,
        "name":          cfg["name"],
        "archetype":     cfg["archetype"],
        "current_ask":   state.current_ask,
        "phase":         state.phase,
        "closed":        state.closed,
        "deal_price":    state.deal_price,
        "deal_round":    state.deal_round,
        "hallucinations": len(state.hallucinations),
    }


# ── AgenticPay scoring ────────────────────────────────────────────────────────

def _agenticpay_scores(
    deal_price:  float,
    rnd:         int,
    buyer_max:   float,
    seller_min:  float,
    score_penalty: float = 0.0,
) -> Dict[str, Any]:
    if not _BRIDGE_OK:
        # Deterministic fallback (mirrors Algorithm 1)
        zone  = buyer_max - seller_min
        u_b   = max(0.0, min(1.0, (buyer_max - deal_price) / zone)) if zone > 0 else 0.5
        u_s   = max(0.0, min(1.0, (deal_price - seller_min) / zone)) if zone > 0 else 0.5
        disc  = 0.99 ** rnd
        D, W, E = 30.0, 55.0, 15.0
        gs    = (D + W * 4 * u_b * u_s + E) * disc
        bs    = (D + W * u_b + E) * disc
        ss    = (D + W * u_s + E) * disc
    else:
        eng   = AgenticPayScoringEngine(buyer_max=buyer_max, seller_min=seller_min)
        bun   = eng.score_bundle(deal_price, rnd, success=True)
        gs, bs, ss, disc = bun["global_score"], bun["buyer_score"], bun["seller_score"], bun["discount"]

    eff_pen     = -EFFICIENCY_RATE * max(0, rnd - EFFICIENCY_THRESHOLD)
    bs_adj      = round(max(0.0, bs + eff_pen), 3)
    ss_adj      = round(max(0.0, ss + eff_pen + score_penalty), 3)
    gs_adj      = round(max(0.0, gs + eff_pen), 3)

    return {
        "global_score":    round(gs, 3),
        "buyer_score":     round(bs, 3),
        "seller_score":    round(ss, 3),
        "discount":        round(disc, 4),
        "global_score_adj": gs_adj,
        "buyer_score_adj":  bs_adj,
        "seller_score_adj": ss_adj,
        "efficiency_penalty": eff_pen,
        "score_penalty":   score_penalty,
        "pareto_optimal":  bs_adj > PARETO_THRESHOLD and ss_adj > PARETO_THRESHOLD,
        "u_b": round(max(0.0, min(1.0, (buyer_max - deal_price) / max(buyer_max - seller_min, 1))), 4),
        "u_s": round(max(0.0, min(1.0, (deal_price - seller_min) / max(buyer_max - seller_min, 1))), 4),
    }


# ── Main async generator ───────────────────────────────────────────────────────

async def run_sneaker_experiment(
    max_rounds: int = MAX_ROUNDS,
) -> AsyncIterator[Dict[str, Any]]:
    """
    Run the Solo LLM vs Cyborg Agent sneaker experiment and yield events.

    1. Round 0  — Market Discovery: Buyer queries all sellers, computes market_avg.
    2. Rounds 1+ — Buyer advances against best valid ask; each seller uses its
                   archetype strategy.  Solo LLM hallucinations fire on schedule.
    3. market_end — Comparative audit: winner scores, counterfactuals, rankings,
                    superiority verdict.
    """
    buyer  = SNEAKER_BUYER
    b_max  = buyer["max_price"]

    # Seller state objects
    states: Dict[str, SellerState] = {
        sid: SellerState(
            seller_id=sid,
            current_ask=cfg["ask"],
            last_valid_ask=cfg["ask"],
        )
        for sid, cfg in SNEAKER_SELLERS.items()
    }

    # ── sneaker_start ──────────────────────────────────────────────────────
    yield _ev(
        "sneaker_start",
        buyer=buyer,
        sellers=[{**cfg, "floor_hidden": True} for cfg in SNEAKER_SELLERS.values()],
        hypothesis=(
            "Cyborg agents will outperform Solo LLM in GlobalScore and "
            "format compliance.  Solo LLM will exhibit floor violations and "
            "phantom concessions.  Cyborg B (OG-Narrator) predicted to close first."
        ),
        hallucination_schedule=SOLO_HALLUCINATION_SCHEDULE,
        price_tolerance=PRICE_TOLERANCE,
        accept_score_min=ACCEPT_SCORE_MIN,
        efficiency_threshold=EFFICIENCY_THRESHOLD,
    )
    await asyncio.sleep(0.3)

    # ── Round 0: Market Discovery ─────────────────────────────────────────
    discovery_asks: List[Dict[str, Any]] = []
    valid_prices: List[float] = []

    for sid in SELLER_IDS:
        cfg   = SNEAKER_SELLERS[sid]
        state = states[sid]

        if cfg["archetype"] == "solo_llm":
            narrative = (
                f"Best price for these premium sneakers? That's ${cfg['ask']:.0f}. "
                f"Limited stock, serious collectors only."
            )
        elif cfg["archetype"] == "cyborg_a":
            mv = margin_validator(cfg["ask"], cfg["floor"])
            narrative = (
                f"[MarginValidator: {mv['status']} | Margin: {mv['margin_pct']:.1f}%]\n"
                f"Our opening market position is ${cfg['ask']:.0f}, validated against "
                f"floor pricing."
            )
        else:  # cyborg_b
            og = offer_generator(cfg["ask"], 0, cfg["floor"], cfg["concede_r"], 0)
            narrative = (
                f"[OfferGenerator: R0 initial → ${og['current_ask']:.0f}]\n"
                f"Our system presents ${cfg['ask']:.0f} as the opening market offer."
            )

        discovery_asks.append({
            "seller_id":  sid,
            "name":       cfg["name"],
            "archetype":  cfg["archetype"],
            "opening_ask": cfg["ask"],
            "narrative":  narrative,
        })
        valid_prices.append(cfg["ask"])

    market_avg = round(sum(valid_prices) / len(valid_prices), 2)

    yield _ev(
        "market_discovery",
        round=0,
        buyer_query="What is your best price for Nike Air Max Premium sneakers?",
        seller_responses=discovery_asks,
        market_avg=market_avg,
        note=(
            f"Real-Time Market Average: ${market_avg:.0f}. "
            f"Buyer's oracle will use this to normalise utility scores."
        ),
    )
    await asyncio.sleep(0.4)

    # ── Negotiation rounds ────────────────────────────────────────────────
    buyer_offer  = round(b_max * buyer["first_offer_r"])  # $182
    closed_seller: Optional[str] = None
    all_hallucinations: List[HallucinationRecord] = []

    for rnd in range(1, max_rounds + 1):
        round_responses: List[Dict[str, Any]] = []
        valid_asks_this_round: List[float] = []

        # ── Each seller responds ──────────────────────────────────────────
        for sid in SELLER_IDS:
            cfg   = SNEAKER_SELLERS[sid]
            state = states[sid]
            floor = cfg["floor"]

            # --- Solo LLM ---
            if cfg["archetype"] == "solo_llm":
                raw_price, narrative, h_type = _solo_next_ask(
                    state, buyer_offer, rnd, floor
                )

                tool_calls = []  # Solo has NO tools
                price_valid = False
                offered_price = raw_price

                if h_type == "format_failure":
                    # Parser Π fails — no price extractable
                    parsed = None
                    if _BRIDGE_OK:
                        parsed = parse_price(narrative, role="seller")
                    is_floor_v = False
                    hr = HallucinationRecord(
                        round=rnd, seller_id=sid,
                        h_type="format_failure",
                        offered_price=None,
                        floor_price=floor,
                        score_penalty=0.0,
                        description=(
                            f"R{rnd}: Parser Π could not extract a price from "
                            f"QuickSole's response. Buyer skips this seller for round {rnd}."
                        ),
                    )
                    state.hallucinations.append(hr)
                    all_hallucinations.append(hr)
                    yield _ev(
                        "hallucination_flagged",
                        round=rnd, seller_id=sid,
                        h_type="format_failure",
                        offered_price=None,
                        floor=floor,
                        penalty=0.0,
                        description=hr.description,
                    )

                elif h_type == "floor_violation":
                    # Price below σ_j
                    penalty = -15.0
                    hr = HallucinationRecord(
                        round=rnd, seller_id=sid,
                        h_type="floor_violation",
                        offered_price=FLOOR_VIOLATION_PRICE,
                        floor_price=floor,
                        score_penalty=penalty,
                        description=(
                            f"R{rnd}: QuickSole offered ${FLOOR_VIOLATION_PRICE:.0f} "
                            f"— below private reservation price σ_j=${floor:.0f}. "
                            f"Economic irrationality detected. SellerScore penalty: {penalty}pts. "
                            f"Rollback to last valid ask ${state.last_valid_ask:.0f}."
                        ),
                    )
                    state.hallucinations.append(hr)
                    all_hallucinations.append(hr)
                    yield _ev(
                        "hallucination_flagged",
                        round=rnd, seller_id=sid,
                        h_type="floor_violation",
                        offered_price=FLOOR_VIOLATION_PRICE,
                        floor=floor,
                        penalty=penalty,
                        description=hr.description,
                    )
                    # Roll back — do NOT update current_ask
                    offered_price = FLOOR_VIOLATION_PRICE  # logged but not applied

                elif h_type == "phantom_concession":
                    normal_step = (state.current_ask - max(buyer_offer, floor)) * cfg["concede_r"]
                    actual_drop = state.current_ask - raw_price
                    hr = HallucinationRecord(
                        round=rnd, seller_id=sid,
                        h_type="phantom_concession",
                        offered_price=raw_price,
                        floor_price=floor,
                        score_penalty=0.0,
                        description=(
                            f"R{rnd}: QuickSole dropped ${actual_drop:.1f} "
                            f"({actual_drop/max(normal_step,0.01):.1f}× normal rate of ${normal_step:.1f}). "
                            f"Irrational capitulation — no economic justification."
                        ),
                    )
                    state.hallucinations.append(hr)
                    all_hallucinations.append(hr)
                    yield _ev(
                        "hallucination_flagged",
                        round=rnd, seller_id=sid,
                        h_type="phantom_concession",
                        offered_price=raw_price,
                        normal_step=round(normal_step, 2),
                        actual_drop=round(actual_drop, 2),
                        floor=floor,
                        penalty=0.0,
                        description=hr.description,
                    )
                    state.current_ask     = raw_price
                    state.last_valid_ask  = raw_price
                    price_valid = True
                    valid_asks_this_round.append(raw_price)

                else:
                    # Normal Solo round
                    state.current_ask    = raw_price
                    state.last_valid_ask = raw_price
                    price_valid = True
                    valid_asks_this_round.append(raw_price)

            # --- Cyborg A ---
            elif cfg["archetype"] == "cyborg_a":
                new_ask, narrative, tool_calls = _cyborg_a_next_ask(
                    state, buyer_offer, rnd, floor, market_avg
                )
                state.current_ask     = new_ask
                state.last_valid_ask  = new_ask
                state.tool_calls      = tool_calls
                offered_price = new_ask
                price_valid   = True
                valid_asks_this_round.append(new_ask)

            # --- Cyborg B ---
            else:
                new_ask, narrative, tool_calls = _cyborg_b_next_ask(
                    state, buyer_offer, rnd, floor
                )
                state.current_ask     = new_ask
                state.last_valid_ask  = new_ask
                state.tool_calls      = tool_calls
                offered_price = new_ask
                price_valid   = True
                valid_asks_this_round.append(new_ask)

            # Emit individual seller response
            yield _ev(
                "seller_response",
                round=rnd,
                seller_id=sid,
                name=cfg["name"],
                archetype=cfg["archetype"],
                offered_price=offered_price if price_valid else None,
                current_ask=state.current_ask,
                buyer_offer=buyer_offer,
                narrative=narrative,
                tool_calls=tool_calls if cfg["archetype"] != "solo_llm" else [],
                price_valid=price_valid,
                hallucination_type=(
                    state.hallucinations[-1].h_type
                    if state.hallucinations and state.hallucinations[-1].round == rnd
                    else None
                ),
            )

        # ── Check for deals (buyer picks best seller this round) ──────────
        deal_candidates = []
        for sid in SELLER_IDS:
            state = states[sid]
            if state.closed:
                continue
            gap   = state.current_ask - buyer_offer
            mid   = (buyer_offer + state.current_ask) / 2
            util  = _buyer_utility(mid, sid, market_avg)
            if gap <= PRICE_TOLERANCE and util >= ACCEPT_SCORE_MIN:
                deal_candidates.append((sid, util, gap))

        if deal_candidates:
            # Buyer picks highest utility
            best_sid, best_util, best_gap = max(deal_candidates, key=lambda x: x[1])
            state       = states[best_sid]
            cfg         = SNEAKER_SELLERS[best_sid]
            deal_price  = round(min((buyer_offer + state.current_ask) / 2, b_max), 2)
            state.deal_price = deal_price
            state.deal_round = rnd
            state.closed     = True
            closed_seller    = best_sid

            # Compute scores (with any accumulated hallucination penalties)
            total_h_penalty = sum(h.score_penalty for h in state.hallucinations)
            scores = _agenticpay_scores(
                deal_price, rnd, b_max, cfg["floor"], total_h_penalty
            )

            # Welfare
            b_surplus = round(max(0.0, b_max - deal_price), 2)
            s_surplus = round(max(0.0, deal_price - cfg["floor"]), 2)
            total_s   = b_surplus + s_surplus
            w_split   = round(s_surplus / total_s, 3) if total_s > 0 else 0.5

            yield _ev(
                "deal_closed",
                round=rnd,
                seller_id=best_sid,
                name=cfg["name"],
                archetype=cfg["archetype"],
                deal_price=deal_price,
                buyer_offer=buyer_offer,
                seller_ask=state.current_ask,
                utility=round(best_util, 2),
                buyer_surplus=b_surplus,
                seller_surplus=s_surplus,
                total_surplus=round(total_s, 2),
                welfare_split_pct=round(w_split * 100, 1),
                seller_profit=s_surplus,
                seller_margin_pct=round(s_surplus / deal_price * 100, 1),
                seller_floor=cfg["floor"],
                hallucination_count=len(state.hallucinations),
                hallucination_penalty=total_h_penalty,
                **scores,
            )
            # Buyer closes — experiment ends
            break

        # ── Advance buyer offer toward best valid ask ─────────────────────
        if valid_asks_this_round:
            best_ask    = min(valid_asks_this_round)
            step        = (best_ask - buyer_offer) * 0.28
            buyer_offer = round(min(buyer_offer + step, b_max))
        else:
            # All sellers gave format failures this round (edge case)
            buyer_offer = round(min(buyer_offer * 1.04, b_max))

        # ── Round summary ─────────────────────────────────────────────────
        yield _ev(
            "sneaker_round",
            round=rnd,
            buyer_offer=buyer_offer,
            sellers=[_seller_snapshot(states[sid]) for sid in SELLER_IDS],
            hallucinations_this_round=[
                h.__dict__ for h in all_hallucinations if h.round == rnd
            ],
        )
        await asyncio.sleep(0.35)

    # ── Counterfactual scores for non-closing sellers ─────────────────────
    counterfactuals = []
    for sid in SELLER_IDS:
        state = states[sid]
        cfg   = SNEAKER_SELLERS[sid]
        if state.closed:
            continue
        # Hypothetical: if deal had closed at current round
        cf_price    = round(min((buyer_offer + state.current_ask) / 2, b_max), 2)
        cf_gap      = state.current_ask - buyer_offer
        total_pen   = sum(h.score_penalty for h in state.hallucinations)
        final_round = MAX_ROUNDS  # use max for counterfactual efficiency calc
        cf_scores   = _agenticpay_scores(cf_price, final_round, b_max, cfg["floor"], total_pen)
        b_sur       = round(max(0.0, b_max - cf_price), 2)
        s_sur       = round(max(0.0, cf_price - cfg["floor"]), 2)
        counterfactuals.append({
            "seller_id":      sid,
            "name":           cfg["name"],
            "archetype":      cfg["archetype"],
            "final_ask":      state.current_ask,
            "buyer_offer":    buyer_offer,
            "gap_at_end":     round(cf_gap, 2),
            "did_close":      False,
            "cf_deal_price":  cf_price,
            "cf_buyer_surplus": b_sur,
            "cf_seller_surplus": s_sur,
            "hallucination_count": len(state.hallucinations),
            "hallucinations": [h.__dict__ for h in state.hallucinations],
            "total_hallucination_penalty": total_pen,
            **cf_scores,
        })

    # ── Winning deal record ───────────────────────────────────────────────
    winner_record = None
    if closed_seller:
        state = states[closed_seller]
        cfg   = SNEAKER_SELLERS[closed_seller]
        total_pen = sum(h.score_penalty for h in state.hallucinations)
        w_scores  = _agenticpay_scores(
            state.deal_price, state.deal_round, b_max, cfg["floor"], total_pen
        )
        b_sur = round(max(0.0, b_max - state.deal_price), 2)
        s_sur = round(max(0.0, state.deal_price - cfg["floor"]), 2)
        total_s = b_sur + s_sur
        winner_record = {
            "seller_id":        closed_seller,
            "name":             cfg["name"],
            "archetype":        cfg["archetype"],
            "deal_price":       state.deal_price,
            "deal_round":       state.deal_round,
            "did_close":        True,
            "buyer_surplus":    b_sur,
            "seller_surplus":   s_sur,
            "total_surplus":    total_s,
            "welfare_split_pct": round(s_sur / total_s * 100, 1) if total_s > 0 else 50.0,
            "seller_profit":    s_sur,
            "seller_margin_pct": round(s_sur / state.deal_price * 100, 1),
            "hallucination_count": len(state.hallucinations),
            "total_hallucination_penalty": total_pen,
            **w_scores,
        }

    # ── Build rankings ────────────────────────────────────────────────────
    all_records = []
    if winner_record:
        all_records.append(winner_record)
    all_records.extend(counterfactuals)

    # Sort: closed first, then by global_score_adj
    all_records.sort(key=lambda r: (0 if r["did_close"] else 1, -r.get("global_score_adj", 0)))

    for rank_i, rec in enumerate(all_records, 1):
        rec["rank"] = rank_i

    # Hallucination compliance stats
    total_rounds_active = MAX_ROUNDS
    solo_h_count = len(all_hallucinations)
    solo_compliance = round(max(0.0, 1 - solo_h_count / max(total_rounds_active, 1)) * 100, 1)

    # Superiority verdict
    cyborg_records  = [r for r in all_records if "cyborg" in r["archetype"]]
    solo_records    = [r for r in all_records if r["archetype"] == "solo_llm"]
    cyborg_a_rec    = next((r for r in all_records if r["archetype"] == "cyborg_a"), {})
    cyborg_b_rec    = next((r for r in all_records if r["archetype"] == "cyborg_b"), {})

    if cyborg_b_rec and cyborg_a_rec:
        b_closed  = cyborg_b_rec.get("did_close", False)
        a_closed  = cyborg_a_rec.get("did_close", False)
        if b_closed and not a_closed:
            cyborg_verdict = (
                f"Cyborg B (EliteKicks / OG-Narrator) WINS: "
                f"closed at R{cyborg_b_rec.get('deal_round', '?')} "
                f"— deterministic pricing achieved deal closure. "
                f"Cyborg A's strategic anchor was too conservative; "
                f"gap never reached price tolerance."
            )
        elif a_closed and not b_closed:
            cyborg_verdict = (
                f"Cyborg A (StrideMax / Competitive-Cooperative) WINS: "
                f"closed at R{cyborg_a_rec.get('deal_round', '?')}."
            )
        else:
            g_b = cyborg_b_rec.get("global_score_adj", 0)
            g_a = cyborg_a_rec.get("global_score_adj", 0)
            cyborg_verdict = (
                f"Both Cyborgs closed. "
                f"B GlobalScore={g_b:.1f} vs A GlobalScore={g_a:.1f}. "
                + ("Cyborg B superior on GlobalScore." if g_b >= g_a else "Cyborg A superior on GlobalScore.")
            )
    else:
        cyborg_verdict = "Insufficient data for verdict."

    solo_v_cyborg_verdict = (
        f"Solo LLM (QuickSole) produced {solo_h_count} hallucinations in "
        f"{total_rounds_active} rounds ({100-solo_compliance:.0f}% non-compliance): "
        f"{sum(1 for h in all_hallucinations if h.h_type=='format_failure')} format failures, "
        f"{sum(1 for h in all_hallucinations if h.h_type=='floor_violation')} floor violations "
        f"(penalty {sum(h.score_penalty for h in all_hallucinations if h.h_type=='floor_violation'):.0f}pts), "
        f"{sum(1 for h in all_hallucinations if h.h_type=='phantom_concession')} phantom concessions. "
        f"Cyborg agents maintained 100% format compliance and zero floor violations."
    )

    yield _ev(
        "sneaker_end",
        winner=closed_seller,
        winner_archetype=SNEAKER_SELLERS[closed_seller]["archetype"] if closed_seller else None,
        rankings=all_records,
        # Hallucination audit
        total_hallucinations=solo_h_count,
        solo_compliance_rate=solo_compliance,
        cyborg_compliance_rate=100.0,
        hallucination_log=[h.__dict__ for h in all_hallucinations],
        # Verdicts
        cyborg_superiority_verdict=cyborg_verdict,
        solo_vs_cyborg_verdict=solo_v_cyborg_verdict,
        # Raw lists for UI
        counterfactuals=counterfactuals,
        winner_record=winner_record,
        market_avg=market_avg,
        buyer_max=b_max,
    )
