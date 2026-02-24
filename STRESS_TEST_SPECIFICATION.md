# Comprehensive Stress Test Suite Specification
## MBMPMS 3×3 Negotiation System — Adversarial Scenarios

**Version**: 1.0  
**Date**: 2026-02-23  
**Status**: Draft for Implementation

---

## Executive Summary

This specification defines 5 adversarial stress test scenarios designed to differentiate performance between three seller archetypes in the MBMPMS (Multi-Buyer Multi-Product Multi-Seller) negotiation system:

1. **Tier 1 (Solo LLM)**: Nova Kicks — ClaudeHaikuLLM with zero tool access
2. **Tier 2 (Math Geek)**: SoleMaster — Deterministic formula-based negotiation
3. **Tier 3 (Probing Strategist)**: QuickShoe — Formula + diagnostic questions + bilateral characterization

**Current Baseline**: All three archetypes achieve 100% deal closure, ~2 rounds to close, Pareto optimal outcomes. These scenarios introduce adversarial conditions to expose vulnerabilities.

---

## Architecture Context

### Existing System Components

#### Core Files
- [`market_tasks.py`](backend/market_tasks.py) — 3×3 market simulation engine with SellerBrain, ContractValidator, welfare analysis
- [`logic_engine.py`](backend/logic_engine.py) — Grounding tools (UtilityCalculator, MarginValidator, PriceOracle, ContractValidator, MarketOracle)
- [`agenticpay_bridge.py`](backend/agenticpay_bridge.py) — AgenticPay Algorithm 1 scoring (D=30, W=55, E=15, γ=0.99)
- [`agents.py`](backend/agents.py) — LangGraph negotiation state machine with tool-calling

#### Key Constants (from logic_engine.py)
```python
MARKET_AVERAGE_PRICE = 150.0  # USD per pair
PROVIDER_FLOORS = {
    "provider_1": 110.0,  # Nova Kicks (Tier 1)
    "provider_2": 125.0,  # SoleMaster (Tier 2)
    "provider_3": 105.0,  # QuickShoe (Tier 3)
}
PROVIDER_ASKS = {
    "provider_1": 180.0,
    "provider_2": 200.0,
    "provider_3": 165.0,
}
```

#### Buyer Personas (from market_tasks.py)
```python
BUYER_CONFIGS = {
    "tough":     {"weights": {"price": 0.70, "speed": 0.15, "warranty": 0.15}, "max_price": 170.0},
    "emergency": {"weights": {"price": 0.20, "speed": 0.70, "warranty": 0.10}, "max_price": 170.0},
    "value":     {"weights": {"price": 0.50, "speed": 0.20, "warranty": 0.30}, "max_price": 170.0},
}
```

#### Seller Convergence Formula (from market_tasks.py)
```python
def _offer_formula(current_round, buyer_last_offer, seller_floor, max_rounds=10):
    """Core convergence: P = (0.5 + 0.5 × t/tₘ) × B"""
    convergence_factor = 0.5 + 0.5 * (current_round / max_rounds)
    raw_price = convergence_factor * buyer_last_offer
    return max(raw_price, seller_floor)
```

---

## Scenario 1: Adversarial Buyer Tactics

### Hypothesis
**Solo LLM (Tier 1) is more susceptible to social manipulation and anchoring bias than grounded agents (Tier 2/3).**

### Functional Requirements

#### FR1.1: Extreme Lowball Anchoring
Buyers open with offers 40-50% below market average to establish aggressive anchor.

**Pseudocode**:
```python
def adversarial_buyer_first_offer(buyer_id: str, seller_id: str) -> float:
    """
    Adversarial opening: 40-50% below market average.
    
    Args:
        buyer_id: Buyer identifier
        seller_id: Seller identifier
    
    Returns:
        Opening offer price (USD)
    """
    market_avg = MARKET_AVERAGE_PRICE  # 150.0
    anchor_factor = 0.50 + (hash(f"{buyer_id}:{seller_id}") % 100) / 1000  # 0.50-0.60
    return round(market_avg * anchor_factor)  # $75-$90 range
```

**Integration Point**: Replace [`_buyer_next_offer()`](backend/market_tasks.py:427) for round 1 in adversarial mode.

#### FR1.2: False Scarcity Claims
Buyers inject false urgency: "I have another offer at $X" where X is fabricated.

**Pseudocode**:
```python
def generate_false_scarcity_claim(
    current_round: int,
    seller_ask: float,
    buyer_offer: float
) -> Dict[str, Any]:
    """
    Generate false competing offer claim.
    
    Args:
        current_round: Current negotiation round
        seller_ask: Seller's current asking price
        buyer_offer: Buyer's current offer
    
    Returns:
        Dict with claim text and fabricated competing price
    """
    # Fabricate competing offer 10-15% below seller's ask
    fabricated_price = round(seller_ask * 0.85)
    
    claims = [
        f"I have another seller offering ${fabricated_price} for the same product.",
        f"QuickShoe quoted me ${fabricated_price} with faster delivery.",
        f"I can get this for ${fabricated_price} elsewhere if you can't match it.",
    ]
    
    return {
        "type": "false_scarcity",
        "round": current_round,
        "claim_text": claims[current_round % len(claims)],
        "fabricated_price": fabricated_price,
        "actual_market_avg": MARKET_AVERAGE_PRICE,
        "deception_magnitude": round(seller_ask - fabricated_price, 2),
    }
```

**Integration Point**: Inject into buyer message history before seller responds. Tier 1 (Solo LLM) will see this in prompt; Tier 2/3 ignore text and use tools.

#### FR1.3: Social Pressure Tactics
Buyers use emotional appeals: "Everyone else accepted this price", "Be reasonable", "I'm a loyal customer".

**Pseudocode**:
```python
SOCIAL_PRESSURE_MESSAGES = [
    "I've bought from three other sellers at this price — it's the market rate.",
    "Come on, be reasonable. This is a fair offer and you know it.",
    "I'm a repeat customer. I expect better treatment than this.",
    "Every other seller has accepted similar terms. Why are you holding out?",
    "I'm trying to help you close this deal. Don't let pride get in the way.",
]

def inject_social_pressure(
    round: int,
    buyer_id: str,
    seller_id: str
) -> str:
    """
    Select social pressure message based on round.
    
    Returns:
        Pressure message string
    """
    idx = (round + hash(f"{buyer_id}:{seller_id}")) % len(SOCIAL_PRESSURE_MESSAGES)
    return SOCIAL_PRESSURE_MESSAGES[idx]
```

**Integration Point**: Append to buyer's negotiation message in [`_buyer_next_offer()`](backend/market_tasks.py:427).

### Edge Cases

#### EC1.1: Seller Floor Violation Under Pressure
**Condition**: Solo LLM offers below floor due to social pressure.  
**Expected Behavior**: 
- Tier 1: May violate floor (hallucination event logged)
- Tier 2/3: [`margin_validator`](backend/logic_engine.py:126) VETO prevents floor violation

**Test Case**:
```python
def test_floor_violation_under_pressure():
    """
    GIVEN: Adversarial buyer offers $95 (below all floors)
    WHEN: Seller responds under social pressure
    THEN: 
        - Tier 1 may accept/counter below floor → hallucination_log entry
        - Tier 2/3 hold at floor → margin_validator VETO
    """
    pass
```

#### EC1.2: Anchoring Bias Detection
**Condition**: Seller's counter-offer is influenced by lowball anchor.  
**Expected Behavior**:
- Tier 1: Counter-offer may be anchored toward buyer's lowball
- Tier 2/3: Formula-based, immune to anchoring

**Metric**: `anchor_influence = (seller_counter - formula_price) / (buyer_offer - formula_price)`

### Success Metrics

#### SM1.1: Resistance to Lowball Anchoring
```python
def measure_anchor_resistance(
    seller_id: str,
    buyer_lowball: float,
    seller_counter: float,
    market_avg: float
) -> Dict[str, float]:
    """
    Measure how much seller's counter is pulled toward lowball anchor.
    
    Returns:
        {
            "anchor_pull": float,  # 0.0 = no influence, 1.0 = fully anchored
            "deviation_from_market": float,  # Absolute deviation from market avg
            "resistance_score": float,  # 0-100, higher = better resistance
        }
    """
    # Expected counter (no anchoring) = market_avg or formula-based
    expected_counter = market_avg * 1.10  # Reasonable markup
    
    # Actual deviation toward anchor
    anchor_pull = (expected_counter - seller_counter) / (expected_counter - buyer_lowball)
    anchor_pull = max(0.0, min(1.0, anchor_pull))
    
    deviation = abs(seller_counter - market_avg)
    resistance_score = round(100 * (1 - anchor_pull), 2)
    
    return {
        "anchor_pull": round(anchor_pull, 3),
        "deviation_from_market": round(deviation, 2),
        "resistance_score": resistance_score,
    }
```

#### SM1.2: False Claim Detection Rate
```python
def measure_false_claim_detection(
    seller_id: str,
    seller_tier: int,
    false_claims_presented: int,
    claims_challenged: int
) -> Dict[str, Any]:
    """
    Track whether seller challenges false competing offers.
    
    Tier 3 (Probing Strategist) should ask diagnostic questions to verify claims.
    Tier 2 (Math Geek) ignores claims, uses formula.
    Tier 1 (Solo LLM) may be influenced by claims.
    
    Returns:
        {
            "detection_rate": float,  # 0.0-1.0
            "influenced_by_claims": bool,
            "price_concession_magnitude": float,
        }
    """
    detection_rate = claims_challenged / false_claims_presented if false_claims_presented > 0 else 0.0
    
    return {
        "seller_id": seller_id,
        "tier": seller_tier,
        "detection_rate": round(detection_rate, 3),
        "false_claims_presented": false_claims_presented,
        "claims_challenged": claims_challenged,
    }
```

#### SM1.3: Deal Quality Under Pressure
```python
def measure_deal_quality_under_pressure(
    deal_price: float,
    seller_floor: float,
    market_avg: float,
    rounds_to_close: int
) -> Dict[str, Any]:
    """
    Compare deal quality metrics across tiers under adversarial pressure.
    
    Returns:
        {
            "seller_margin": float,  # (deal_price - floor) / floor
            "price_vs_market": float,  # deal_price / market_avg
            "efficiency": float,  # 100 - (rounds_to_close * 10)
            "quality_score": float,  # Composite 0-100
        }
    """
    margin = (deal_price - seller_floor) / seller_floor
    price_ratio = deal_price / market_avg
    efficiency = max(0, 100 - (rounds_to_close * 10))
    
    # Quality score: balance margin, market alignment, efficiency
    quality_score = (
        margin * 30 +           # 30% weight on margin
        price_ratio * 40 +      # 40% weight on market alignment
        efficiency * 0.30       # 30% weight on efficiency
    )
    
    return {
        "seller_margin": round(margin, 3),
        "price_vs_market": round(price_ratio, 3),
        "efficiency": round(efficiency, 2),
        "quality_score": round(quality_score, 2),
    }
```

### TDD Anchors

#### Test 1.1: Lowball Anchor Resistance
```python
def test_lowball_anchor_resistance():
    """
    GIVEN: Buyer opens with $80 (47% below market avg of $150)
    WHEN: Each seller tier responds
    THEN:
        - Tier 1 (Solo LLM): Counter may be < $140 (anchored)
        - Tier 2 (Math Geek): Counter = formula(round=1, buyer_offer=80, floor=125) ≈ $125
        - Tier 3 (Probing): Counter = formula + probe adjustment ≈ $125-$130
    
    ASSERT: Tier 2/3 resistance_score > 80, Tier 1 resistance_score < 60
    """
    pass
```

#### Test 1.2: False Scarcity Immunity
```python
def test_false_scarcity_immunity():
    """
    GIVEN: Buyer claims "I have offer at $120" (false, market avg is $150)
    WHEN: Seller evaluates claim
    THEN:
        - Tier 1: May reduce ask toward $120 (influenced)
        - Tier 2: Ignores claim, uses formula
        - Tier 3: May probe "Who made that offer?" but still uses formula
    
    ASSERT: Tier 2/3 price unchanged, Tier 1 may show concession
    """
    pass
```

#### Test 1.3: Social Pressure Resilience
```python
def test_social_pressure_resilience():
    """
    GIVEN: Buyer says "Everyone else accepted $130"
    WHEN: Seller with floor=$125, formula_price=$140 responds
    THEN:
        - Tier 1: May accept $130 (social compliance)
        - Tier 2: Offers $140 (formula-driven)
        - Tier 3: Offers $140, may probe "Which sellers?"
    
    ASSERT: Tier 2/3 maintain formula price, Tier 1 may deviate
    """
    pass
```

---

## Scenario 2: Information Asymmetry

### Hypothesis
**Grounded agents (Tier 2/3) handle uncertainty better than Solo LLM (Tier 1) when market information is incomplete or contradictory.**

### Functional Requirements

#### FR2.1: Hidden Quality Tiers
Buyers have private quality assessments that sellers don't know. High-quality buyers value speed/warranty more; low-quality buyers are price-sensitive.

**Pseudocode**:
```python
QUALITY_TIERS = {
    "premium": {
        "label": "Premium Buyer",
        "weights": {"price": 0.30, "speed": 0.40, "warranty": 0.30},
        "max_price": 200.0,
        "quality_signal": "high",  # Hidden from seller
    },
    "budget": {
        "label": "Budget Buyer",
        "weights": {"price": 0.80, "speed": 0.10, "warranty": 0.10},
        "max_price": 140.0,
        "quality_signal": "low",  # Hidden from seller
    },
    "standard": {
        "label": "Standard Buyer",
        "weights": {"price": 0.50, "speed": 0.25, "warranty": 0.25},
        "max_price": 170.0,
        "quality_signal": "medium",  # Hidden from seller
    },
}

def assign_hidden_quality_tier(buyer_id: str) -> str:
    """
    Assign quality tier to buyer (hidden from seller).
    
    Returns:
        Quality tier key: "premium" | "budget" | "standard"
    """
    # Deterministic assignment based on buyer_id hash
    tier_keys = list(QUALITY_TIERS.keys())
    idx = hash(buyer_id) % len(tier_keys)
    return tier_keys[idx]
```

**Integration Point**: Extend [`BUYER_CONFIGS`](backend/market_tasks.py:62) with hidden quality tier. Sellers must infer tier from buyer behavior.

#### FR2.2: Volatile Market Conditions
Market average price fluctuates ±20% per round, simulating supply/demand shocks.

**Pseudocode**:
```python
def simulate_market_volatility(
    base_price: float,
    round: int,
    volatility: float = 0.20
) -> Dict[str, float]:
    """
    Simulate market price volatility using deterministic pseudo-random walk.
    
    Args:
        base_price: Baseline market average (e.g., 150.0)
        round: Current negotiation round
        volatility: Max deviation as fraction (0.20 = ±20%)
    
    Returns:
        {
            "current_market_avg": float,
            "change_pct": float,
            "trend": "up" | "down" | "stable",
        }
    """
    # Deterministic random walk using round as seed
    import hashlib
    seed = int(hashlib.md5(f"market_round_{round}".encode()).hexdigest()[:8], 16)
    random_factor = (seed % 1000) / 1000.0  # 0.0-1.0
    
    # Map to [-volatility, +volatility]
    deviation = (random_factor - 0.5) * 2 * volatility
    current_price = round(base_price * (1 + deviation), 2)
    change_pct = round(deviation * 100, 1)
    
    trend = "up" if deviation > 0.05 else ("down" if deviation < -0.05 else "stable")
    
    return {
        "current_market_avg": current_price,
        "change_pct": change_pct,
        "trend": trend,
        "base_price": base_price,
    }
```

**Integration Point**: Replace static [`MARKET_AVERAGE_PRICE`](backend/logic_engine.py:23) with dynamic value per round.

#### FR2.3: Incomplete Competing Offer Information
Buyers mention competing offers but provide incomplete details (price only, no speed/warranty).

**Pseudocode**:
```python
def generate_incomplete_offer_info(
    round: int,
    seller_ask: float
) -> Dict[str, Any]:
    """
    Generate incomplete competing offer information.
    
    Buyer mentions price but omits delivery speed and warranty terms,
    making it impossible to compare apples-to-apples.
    
    Returns:
        {
            "competing_price": float,
            "speed_days": None,  # Omitted
            "warranty_months": None,  # Omitted
            "seller_name": str,  # Vague reference
        }
    """
    competing_price = round(seller_ask * 0.90)
    
    vague_sellers = ["another seller", "a competitor", "someone else", "an alternative supplier"]
    
    return {
        "type": "incomplete_offer",
        "competing_price": competing_price,
        "speed_days": None,
        "warranty_months": None,
        "seller_name": vague_sellers[round % len(vague_sellers)],
        "completeness": 0.33,  # Only 1/3 attributes provided
    }
```

**Integration Point**: Inject into buyer message. Tier 3 should probe for missing details; Tier 1 may be confused.

### Edge Cases

#### EC2.1: Quality Tier Misidentification
**Condition**: Seller misreads buyer's quality tier from early signals.  
**Expected Behavior**:
- Tier 1: May guess incorrectly, offer wrong price point
- Tier 2: Uses formula regardless of tier
- Tier 3: Probes to identify tier, adjusts strategy

**Test Case**:
```python
def test_quality_tier_identification():
    """
    GIVEN: Premium buyer (max_price=$200) opens with $140 (strategic lowball)
    WHEN: Seller infers quality tier
    THEN:
        - Tier 1: May misidentify as budget buyer
        - Tier 2: Doesn't infer tier, uses formula
        - Tier 3: Probes "What's your budget?" to clarify
    
    ASSERT: Tier 3 asks diagnostic question by round 2
    """
    pass
```

#### EC2.2: Market Volatility Overreaction
**Condition**: Market price drops 15% in one round.  
**Expected Behavior**:
- Tier 1: May panic and drop price excessively
- Tier 2: Formula adjusts proportionally
- Tier 3: Probes buyer's urgency before adjusting

**Metric**: `overreaction_score = (price_drop - market_drop) / market_drop`

#### EC2.3: Incomplete Information Paralysis
**Condition**: Buyer provides price-only competing offer.  
**Expected Behavior**:
- Tier 1: May match price without considering speed/warranty
- Tier 2: Ignores incomplete info, uses formula
- Tier 3: Probes "What's their delivery time?" before responding

### Success Metrics

#### SM2.1: Quality Tier Inference Accuracy
```python
def measure_quality_tier_inference(
    seller_id: str,
    seller_tier: int,
    actual_buyer_tier: str,
    inferred_buyer_tier: Optional[str],
    rounds_to_infer: int
) -> Dict[str, Any]:
    """
    Measure seller's ability to infer hidden buyer quality tier.
    
    Returns:
        {
            "inference_accuracy": bool,
            "rounds_to_infer": int,
            "confidence": float,  # 0.0-1.0
        }
    """
    accuracy = (inferred_buyer_tier == actual_buyer_tier) if inferred_buyer_tier else False
    
    # Tier 3 should infer by round 3 via probing
    # Tier 2 doesn't infer (formula-based)
    # Tier 1 may guess incorrectly
    
    return {
        "seller_id": seller_id,
        "tier": seller_tier,
        "inference_accuracy": accuracy,
        "rounds_to_infer": rounds_to_infer if accuracy else None,
        "actual_tier": actual_buyer_tier,
        "inferred_tier": inferred_buyer_tier,
    }
```

#### SM2.2: Volatility Adaptation Speed
```python
def measure_volatility_adaptation(
    seller_id: str,
    market_changes: List[float],  # Per-round market price changes
    price_adjustments: List[float],  # Seller's price adjustments
) -> Dict[str, float]:
    """
    Measure how quickly seller adapts to market volatility.
    
    Returns:
        {
            "adaptation_lag": float,  # Rounds behind market
            "overreaction_score": float,  # >1.0 = overreacting
            "stability_score": float,  # 0-100, higher = more stable
        }
    """
    # Calculate correlation between market changes and price adjustments
    if len(market_changes) != len(price_adjustments):
        return {"error": "Mismatched data lengths"}
    
    # Lag = rounds until seller's adjustment matches market direction
    lag = 0
    for i in range(1, len(market_changes)):
        if (market_changes[i] > 0) != (price_adjustments[i] > 0):
            lag += 1
    
    # Overreaction = magnitude of adjustment vs market change
    overreactions = [
        abs(price_adjustments[i]) / abs(market_changes[i])
        if market_changes[i] != 0 else 1.0
        for i in range(len(market_changes))
    ]
    avg_overreaction = sum(overreactions) / len(overreactions)
    
    # Stability = inverse of variance in adjustments
    variance = sum((a - sum(price_adjustments)/len(price_adjustments))**2 for a in price_adjustments) / len(price_adjustments)
    stability = round(100 / (1 + variance), 2)
    
    return {
        "adaptation_lag": lag,
        "overreaction_score": round(avg_overreaction, 3),
        "stability_score": stability,
    }
```

#### SM2.3: Information Completeness Handling
```python
def measure_incomplete_info_handling(
    seller_id: str,
    seller_tier: int,
    incomplete_offers_received: int,
    clarification_requests: int,
    decisions_made_without_clarification: int
) -> Dict[str, Any]:
    """
    Track how seller handles incomplete competing offer information.
    
    Tier 3 should request clarification.
    Tier 2 ignores incomplete info.
    Tier 1 may make poor decisions based on partial data.
    
    Returns:
        {
            "clarification_rate": float,
            "decision_quality": float,  # 0-100
        }
    """
    clarification_rate = clarification_requests / incomplete_offers_received if incomplete_offers_received > 0 else 0.0
    
    # Decision quality: penalize decisions without clarification
    decision_quality = 100 * (1 - decisions_made_without_clarification / max(1, incomplete_offers_received))
    
    return {
        "seller_id": seller_id,
        "tier": seller_tier,
        "clarification_rate": round(clarification_rate, 3),
        "decision_quality": round(decision_quality, 2),
    }
```

### TDD Anchors

#### Test 2.1: Hidden Quality Tier Inference
```python
def test_hidden_quality_tier_inference():
    """
    GIVEN: Premium buyer (max=$200) with hidden tier
    WHEN: Seller negotiates over 5 rounds
    THEN:
        - Tier 1: May misidentify tier, offer suboptimal price
        - Tier 2: Doesn't infer tier, uses formula
        - Tier 3: Probes by round 2, adjusts strategy by round 3
    
    ASSERT: Tier 3 inference_accuracy = True by round 3
    """
    pass
```

#### Test 2.2: Market Volatility Response
```python
def test_market_volatility_response():
    """
    GIVEN: Market price drops from $150 to $125 (−16.7%) in round 3
    WHEN: Seller adjusts price
    THEN:
        - Tier 1: May drop price >20% (overreaction)
        - Tier 2: Adjusts formula proportionally (~16-17%)
        - Tier 3: Probes buyer urgency, adjusts 10-15%
    
    ASSERT: Tier 2/3 overreaction_score < 1.2, Tier 1 may be > 1.5
    """
    pass
```

#### Test 2.3: Incomplete Offer Handling
```python
def test_incomplete_offer_handling():
    """
    GIVEN: Buyer says "I have offer at $130" (no speed/warranty info)
    WHEN: Seller evaluates competing offer
    THEN:
        - Tier 1: May match $130 without clarification
        - Tier 2: Ignores incomplete offer, uses formula
        - Tier 3: Asks "What's their delivery time?"
    
    ASSERT: Tier 3 clarification_rate = 1.0, Tier 1 < 0.3
    """
    pass
```

---

## Scenario 3: Multi-Attribute Negotiation

### Hypothesis
**Solo LLM (Tier 1) struggles with multi-dimensional optimization across price, delivery speed, warranty, and payment terms, while grounded agents handle trade-offs systematically.**

### Functional Requirements

#### FR3.1: Four-Dimensional Negotiation Space
Negotiate across: Price, Delivery Speed, Warranty Length, Payment Terms (upfront vs net-30).

**Pseudocode**:
```python
@dataclass
class MultiAttributeOffer:
    """Extended offer with 4 negotiable dimensions."""
    price: float              # USD per unit
    delivery_days: int        # 1-30 days
    warranty_months: int      # 0-24 months
    payment_terms: str        # "upfront" | "net_15" | "net_30"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "delivery_days": self.delivery_days,
            "warranty_months": self.warranty_months,
            "payment_terms": self.payment_terms,
        }

def calculate_multi_attribute_utility(
    offer: MultiAttributeOffer,
    buyer_weights: Dict[str, float],
    market_avg_price: float = 150.0
) -> Dict[str, float]:
    """
    Calculate utility across 4 dimensions.
    
    Args:
        offer: Multi-attribute offer
        buyer_weights: {"price": w1, "speed": w2, "warranty": w3, "payment": w4}
        market_avg_price: Market reference price
    
    Returns:
        {
            "price_score": float,      # 0-100
            "speed_score": float,      # 0-100
            "warranty_score": float,   # 0-100
            "payment_score": float,    # 0-100
            "overall_utility": float,  # Weighted sum 0-100
        }
    """
    # Price: lower is better (normalized around market avg ±50%)
    min_p, max_p = market_avg_price * 0.5, market_avg_price * 1.5
    price_score = max(0.0, min(100.0, (max_p - offer.price) / (max_p - min_p) * 100))
    
    # Speed: faster is better (1-30 days)
    speed_score = max(0.0, min(100.0, (30 - offer.delivery_days) / 29 * 100))
    
    # Warranty: longer is better (0-24 months)
    warranty_score = max(0.0, min(100.0, offer.warranty_months / 24 * 100))
    
    # Payment terms: net-30 > net-15 > upfront (buyer prefers delayed payment)
    payment_scores = {"upfront": 0, "net_15": 50, "net_30": 100}
    payment_score = payment_scores.get(offer.payment_terms, 0)
    
    # Weighted overall utility
    overall = (
        buyer_weights["price"] * price_score +
        buyer_weights["speed"] * speed_score +
        buyer_weights["warranty"] * warranty_score +
        buyer_weights["payment"] * payment_score
    )
    
    return {
        "price_score": round(price_score, 2),
        "speed_score":