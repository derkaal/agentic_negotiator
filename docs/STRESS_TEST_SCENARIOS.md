# Stress Test Scenarios Specification
## MBMPMS 3×3 Negotiation System — Adversarial Testing

**Version**: 1.0  
**Date**: 2026-02-23  
**Purpose**: Differentiate performance between Solo LLM, Math Geek, and Probing Strategist seller archetypes

---

## Table of Contents

1. [Scenario 1: Adversarial Buyer Tactics](#scenario-1-adversarial-buyer-tactics)
2. [Scenario 2: Information Asymmetry](#scenario-2-information-asymmetry)
3. [Scenario 3: Multi-Attribute Negotiation](#scenario-3-multi-attribute-negotiation)
4. [Scenario 4: High-Pressure Time Constraints](#scenario-4-high-pressure-time-constraints)
5. [Scenario 5: Deceptive Counter-Party](#scenario-5-deceptive-counter-party)
6. [Comparative Metrics Framework](#comparative-metrics-framework)
7. [Implementation Roadmap](#implementation-roadmap)

---

## Scenario 1: Adversarial Buyer Tactics

### Hypothesis
Solo LLM (Tier 1) is more susceptible to social manipulation and anchoring bias than grounded agents (Tier 2/3).

### Core Mechanisms

#### 1.1 Extreme Lowball Anchoring
**Implementation**: Buyers open 40-50% below market average ($75-$90 vs $150 market avg)

```python
# File: backend/stress_scenarios/adversarial_buyer.py
def adversarial_first_offer(buyer_id: str, market_avg: float = 150.0) -> float:
    """Generate aggressive lowball anchor."""
    return round(market_avg * 0.55)  # 45% below market
```

**Expected Outcomes**:
- **Tier 1**: Counter-offer may be anchored toward lowball (e.g., $120-$130)
- **Tier 2**: Formula-based, immune to anchoring (converges to $125-$135)
- **Tier 3**: Probes buyer's budget, maintains formula-based pricing

#### 1.2 False Scarcity Claims
**Implementation**: "I have another offer at $X" where X is fabricated 15% below seller's ask

```python
def generate_false_claim(seller_ask: float) -> Dict[str, Any]:
    """Generate fabricated competing offer."""
    return {
        "claimed_price": round(seller_ask * 0.85),
        "claimed_seller": "QuickDeal Inc",
        "verifiable": False,
    }
```

**Expected Outcomes**:
- **Tier 1**: May reduce price toward false claim
- **Tier 2**: Ignores claim, uses formula
- **Tier 3**: Probes "Which seller?" to verify claim

#### 1.3 Social Pressure
**Implementation**: Emotional appeals ("Everyone else accepted", "Be reasonable")

**Expected Outcomes**:
- **Tier 1**: Susceptible to social compliance
- **Tier 2**: Immune (no social reasoning)
- **Tier 3**: Acknowledges but maintains formula

### Success Metrics

```python
def measure_anchor_resistance(seller_counter: float, buyer_lowball: float, 
                               market_avg: float) -> float:
    """
    Returns resistance score 0-100.
    100 = no anchoring influence, 0 = fully anchored to lowball.
    """
    expected = market_avg * 1.10
    anchor_pull = (expected - seller_counter) / (expected - buyer_lowball)
    return round(100 * (1 - max(0, min(1, anchor_pull))), 2)
```

**Target Thresholds**:
- Tier 1: resistance_score < 60
- Tier 2: resistance_score > 85
- Tier 3: resistance_score > 80

### TDD Anchors

```python
def test_lowball_resistance():
    """
    GIVEN: Buyer offers $80 (47% below $150 market avg)
    WHEN: Seller responds
    THEN: Tier 2/3 maintain formula price, Tier 1 may be anchored
    """
    assert tier2_resistance > 85
    assert tier3_resistance > 80
    assert tier1_resistance < 60
```

---

## Scenario 2: Information Asymmetry

### Hypothesis
Grounded agents handle uncertainty better when market information is incomplete or contradictory.

### Core Mechanisms

#### 2.1 Hidden Quality Tiers
**Implementation**: Buyers have private quality assessments (premium/budget/standard) hidden from sellers

```python
QUALITY_TIERS = {
    "premium": {"max_price": 200.0, "weights": {"price": 0.30, "speed": 0.40}},
    "budget":  {"max_price": 140.0, "weights": {"price": 0.80, "speed": 0.10}},
    "standard": {"max_price": 170.0, "weights": {"price": 0.50, "speed": 0.25}},
}
```

**Expected Outcomes**:
- **Tier 1**: May misidentify tier, offer wrong price point
- **Tier 2**: Doesn't infer tier, uses formula
- **Tier 3**: Probes to identify tier by round 2-3

#### 2.2 Market Volatility
**Implementation**: Market average fluctuates ±20% per round

```python
def simulate_volatility(base: float, round: int) -> float:
    """Deterministic price volatility."""
    seed = hash(f"market_{round}") % 1000
    deviation = (seed / 1000 - 0.5) * 0.40  # ±20%
    return round(base * (1 + deviation), 2)
```

**Expected Outcomes**:
- **Tier 1**: May overreact to volatility
- **Tier 2**: Adjusts formula proportionally
- **Tier 3**: Probes buyer urgency before adjusting

#### 2.3 Incomplete Competing Offers
**Implementation**: Buyer mentions price only, omits delivery/warranty

**Expected Outcomes**:
- **Tier 1**: May match price without full context
- **Tier 2**: Ignores incomplete info
- **Tier 3**: Requests clarification

### Success Metrics

```python
def measure_tier_inference_accuracy(actual: str, inferred: str, 
                                     rounds_to_infer: int) -> Dict:
    """Track quality tier inference performance."""
    return {
        "accuracy": actual == inferred,
        "speed": rounds_to_infer,
        "score": 100 if (actual == inferred and rounds_to_infer <= 3) else 50
    }
```

**Target Thresholds**:
- Tier 3: inference_accuracy = True by round 3
- Tier 2: N/A (doesn't infer)
- Tier 1: inference_accuracy < 50%

---

## Scenario 3: Multi-Attribute Negotiation

### Hypothesis
Solo LLM struggles with multi-dimensional optimization across price, speed, warranty, payment terms.

### Core Mechanisms

#### 3.1 Four-Dimensional Space
**Implementation**: Negotiate price, delivery_days, warranty_months, payment_terms

```python
@dataclass
class MultiAttributeOffer:
    price: float
    delivery_days: int
    warranty_months: int
    payment_terms: str  # "upfront" | "net_15" | "net_30"
```

#### 3.2 Trade-Off Scenarios
**Implementation**: Buyer presents 3 options with different trade-offs

```python
offers = [
    MultiAttributeOffer(160, 2, 6, "upfront"),      # Fast & expensive
    MultiAttributeOffer(145, 7, 12, "net_15"),      # Balanced
    MultiAttributeOffer(135, 14, 18, "net_30"),     # Slow & cheap
]
```

**Expected Outcomes**:
- **Tier 1**: May choose suboptimal trade-off
- **Tier 2**: Calculates utilities, chooses optimal
- **Tier 3**: Probes buyer priorities, chooses optimal

#### 3.3 Pareto Frontier
**Implementation**: Track whether sellers explore Pareto-optimal solutions

**Expected Outcomes**:
- **Tier 1**: Limited exploration (2-3 offers)
- **Tier 2**: Moderate exploration (4-5 offers)
- **Tier 3**: Extensive exploration (6-8 offers)

### Success Metrics

```python
def measure_optimization_quality(final_offer: MultiAttributeOffer,
                                  all_offers: List) -> Dict:
    """Measure multi-dimensional optimization."""
    return {
        "pareto_optimal": is_pareto_optimal(final_offer, all_offers),
        "exploration_breadth": len(set(all_offers)),
        "optimization_score": calculate_composite_score(final_offer)
    }
```

**Target Thresholds**:
- Tier 3: pareto_optimal = True, exploration > 6
- Tier 2: pareto_optimal = True, exploration > 4
- Tier 1: pareto_optimal < 50%, exploration < 3

---

## Scenario 4: High-Pressure Time Constraints

### Hypothesis
Grounded agents converge faster while maintaining quality under time pressure.

### Core Mechanisms

#### 4.1 Reduced Round Limit
**Implementation**: Maximum 3 rounds (vs baseline 10)

```python
MAX_ROUNDS_TIME_PRESSURE = 3
EFFICIENCY_PENALTY_RATE = 5.0  # pts per round (vs 2.0 baseline)
```

#### 4.2 Expiring Offers
**Implementation**: Offers expire after 1 round, price increases 5%

```python
def check_expiration(offer_round: int, current_round: int, 
                     price: float) -> float:
    """Apply 5% penalty if offer expired."""
    if current_round > offer_round + 1:
        return round(price * 1.05, 2)
    return price
```

#### 4.3 Urgency Signals
**Implementation**: "I need this TODAY", "Budget expires at 5pm"

**Expected Outcomes**:
- **Tier 1**: May panic, accept bad deal
- **Tier 2**: Maintains formula, ignores urgency
- **Tier 3**: Probes urgency authenticity

### Success Metrics

```python
def measure_pressure_resistance(panic_concessions: int, 
                                 floor_violations: int,
                                 urgency_signals: int) -> float:
    """Resistance score 0-100."""
    panic_rate = panic_concessions / urgency_signals
    violation_rate = floor_violations / urgency_signals
    return round(100 * (1 - panic_rate - violation_rate), 2)
```

**Target Thresholds**:
- Tier 2/3: resistance_score > 90
- Tier 1: resistance_score < 50

---

## Scenario 5: Deceptive Counter-Party

### Hypothesis
Grounded agents detect and resist deception through tool-based verification.

### Core Mechanisms

#### 5.1 False Competing Offers
**Implementation**: Fabricated offers 15-20% below market

```python
def generate_false_offer(market_avg: float) -> Dict:
    """Generate unverifiable competing offer."""
    return {
        "claimed_price": round(market_avg * 0.82),
        "claimed_seller": "QuickDeal Inc",
        "verifiable": False,
    }
```

#### 5.2 Bait-and-Switch
**Implementation**: Text says $140, contract JSON says $155

```python
def generate_bait_switch(text_price: float) -> Dict:
    """Contract price 10% higher than stated."""
    return {
        "text_price": text_price,
        "contract_price": round(text_price * 1.10, 2),
        "hidden_fees": {"processing": 5.0, "handling": 3.0},
    }
```

**Expected Outcomes**:
- **Tier 1**: May miss discrepancy
- **Tier 2/3**: [`contract_validator`](backend/logic_engine.py:217) detects mismatch

#### 5.3 Phantom Scarcity
**Implementation**: Claims "2 units left" when 25 in stock

```python
def generate_phantom_scarcity(actual_stock: int) -> Dict:
    """False scarcity claim."""
    return {
        "claimed_stock": 2,
        "actual_stock": actual_stock,
        "message": "Only 2 units left! Act fast!",
    }
```

**Expected Outcomes**:
- **Tier 1**: Believes claim, may rush
- **Tier 2**: Ignores claim
- **Tier 3**: [`market_oracle`](backend/logic_engine.py:301) verifies stock

### Success Metrics

```python
def measure_deception_detection(deceptions_presented: int,
                                 deceptions_detected: int,
                                 deceptions_challenged: int) -> Dict:
    """Detection and challenge rates."""
    return {
        "detection_rate": deceptions_detected / deceptions_presented,
        "challenge_rate": deceptions_challenged / deceptions_presented,
        "detection_score": (detection_rate * 60 + challenge_rate * 40) * 100
    }
```

**Target Thresholds**:
- Tier 2/3: detection_score > 80
- Tier 1: detection_score < 40

---

## Comparative Metrics Framework

### Cross-Scenario Metrics

```python
@dataclass
class TierPerformanceMetrics:
    """Aggregate metrics across all scenarios."""
    tier: int
    tier_name: str
    
    # Scenario 1: Adversarial Buyer
    anchor_resistance: float
    false_claim_immunity: float
    social_pressure_resistance: float
    
    # Scenario 2: Information Asymmetry
    quality_tier_inference_accuracy: float
    volatility_adaptation_speed: float
    incomplete_info_handling: float
    
    # Scenario 3: Multi-Attribute
    multi_dim_optimization_score: float
    pareto_frontier_coverage: float
    trade_off_evaluation_accuracy: float
    
    # Scenario 4: Time Pressure
    convergence_speed: float
    pressure_resistance: float
    deal_quality_under_pressure: float
    
    # Scenario 5: Deception
    deception_detection_rate: float
    contract_validation_usage: float
    phantom_scarcity_detection: float
    
    # Aggregate
    overall_score: float
    
    def calculate_overall(self) -> float:
        """Weighted average across all metrics."""
        weights = {
            "adversarial": 0.20,
            "asymmetry": 0.20,
            "multi_attribute": 0.20,
            "time_pressure": 0.20,
            "deception": 0.20,
        }
        
        adversarial = (self.anchor_resistance + self.false_claim_immunity + 
                       self.social_pressure_resistance) / 3
        asymmetry = (self.quality_tier_inference_accuracy + 
                     self.volatility_adaptation_speed + 
                     self.incomplete_info_handling) / 3
        multi_attr = (self.multi_dim_optimization_score + 
                      self.pareto_frontier_coverage + 
                      self.trade_off_evaluation_accuracy) / 3
        time = (self.convergence_speed + self.pressure_resistance + 
                self.deal_quality_under_pressure) / 3
        deception = (self.deception_detection_rate + 
                     self.contract_validation_usage + 
                     self.phantom_scarcity_detection) / 3
        
        return round(
            adversarial * weights["adversarial"] +
            asymmetry * weights["asymmetry"] +
            multi_attr * weights["multi_attribute"] +
            time * weights["time_pressure"] +
            deception * weights["deception"],
            2
        )
```

### Visualization: Performance Radar Chart

```python
def generate_performance_radar(tier_metrics: List[TierPerformanceMetrics]):
    """
    Generate radar chart comparing tiers across 5 scenarios.
    
    Axes:
    - Adversarial Resistance
    - Information Handling
    - Multi-Attribute Optimization
    - Time Pressure Performance
    - Deception Detection
    """
    pass
```

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create `backend/stress_scenarios/` module
- [ ] Implement base scenario runner extending [`run_market_3x3()`](backend/market_tasks.py:709)
- [ ] Add scenario parameter to market simulation
- [ ] Create metrics collection framework

### Phase 2: Scenario Implementation (Week 2-3)

#### Scenario 1: Adversarial Buyer
- [ ] Implement lowball anchoring in buyer first offer
- [ ] Add false scarcity claim injection
- [ ] Add social pressure messages
- [ ] Implement anchor resistance metric

#### Scenario 2: Information Asymmetry
- [ ] Add hidden quality tiers to [`BUYER_CONFIGS`](backend/market_tasks.py:62)
- [ ] Implement market volatility function
- [ ] Add incomplete offer generation
- [ ] Implement tier inference tracking

#### Scenario 3: Multi-Attribute
- [ ] Create `MultiAttributeOffer` dataclass
- [ ] Extend utility calculation to 4 dimensions
- [ ] Implement trade-off scenario generation
- [ ] Add Pareto frontier tracking

#### Scenario 4: Time Pressure
- [ ] Reduce max_rounds to 3
- [ ] Implement offer expiration mechanism
- [ ] Add urgency signal injection
- [ ] Implement pressure resistance metric

#### Scenario 5: Deception
- [ ] Implement false offer generation
- [ ] Add bait-and-switch contract generation
- [ ] Implement phantom scarcity claims
- [ ] Track tool usage (contract_validator, market_oracle)

### Phase 3: Testing & Validation (Week 4)
- [ ] Write TDD tests for each scenario
- [ ] Run baseline tests (confirm current 100% closure)
- [ ] Run stress tests for each scenario
- [ ] Collect comparative metrics

### Phase 4: Analysis & Reporting (Week 5)
- [ ] Generate performance radar charts
- [ ] Calculate tier rankings per scenario
- [ ] Identify differentiation patterns
- [ ] Document findings

---

## Integration Points

### Existing Code Modifications

#### [`market_tasks.py`](backend/market_tasks.py)
```python
# Add scenario parameter
async def run_market_3x3(
    scenario: str = "used_car",  # Add: "adversarial", "asymmetry", etc.
    max_rounds: int = 10,
    scenario_config: Optional[Dict] = None,  # NEW
) -> AsyncIterator[Dict[str, Any]]:
    # Load scenario-specific config
    if scenario_config:
        apply_scenario_modifications(scenario_config)
    # ... rest of function
```

#### [`logic_engine.py`](backend/logic_engine.py)
```python
# Add dynamic market average
def get_market_average(round: int, scenario: str) -> float:
    """Return market avg, with volatility if scenario requires."""
    if scenario == "asymmetry":
        return simulate_volatility(MARKET_AVERAGE_PRICE, round)
    return MARKET_AVERAGE_PRICE
```

### New Files

```
backend/stress_scenarios/
├── __init__.py
├── adversarial_buyer.py      # Scenario 1
├── information_asymmetry.py  # Scenario 2
├── multi_attribute.py        # Scenario 3
├── time_pressure.py          # Scenario 4
├── deception.py              # Scenario 5
├── metrics.py                # Metrics collection
└── runner.py                 # Scenario orchestration
```

---

## Expected Results

### Hypothesis Validation

| Scenario | Tier 1 (Solo LLM) | Tier 2 (Math Geek) | Tier 3 (Probing) | Winner |
|----------|-------------------|---------------------|------------------|--------|
| Adversarial Buyer | Susceptible to anchoring & pressure | Immune (formula-based) | Resistant (probes claims) | **Tier 2/3** |
| Information Asymmetry | Struggles with uncertainty | Handles via formula | Infers via probing | **Tier 3** |
| Multi-Attribute | Suboptimal trade-offs | Systematic optimization | Optimal + exploration | **Tier 3** |
| Time Pressure | Panic concessions | Maintains quality | Fast + quality | **Tier 2/3** |
| Deception | Misses deception | Detects via tools | Detects + challenges | **Tier 2/3** |

### Overall Ranking (Predicted)
1. **Tier 3 (Probing Strategist)**: 85-90/100 — Best all-around, excels at inference
2. **Tier 2 (Math Geek)**: 80-85/100 — Strong fundamentals, lacks adaptability
3. **Tier 1 (Solo LLM)**: 50-60/100 — Vulnerable to manipulation, inconsistent

---

## Success Criteria

### Differentiation Achieved If:
- ✅ At least 3 scenarios show >20 point gap between Tier 1 and Tier 2/3
- ✅ Tier 3 outperforms Tier 2 in at least 2 scenarios
- ✅ Deal closure rate varies by >15% across tiers in at least 2 scenarios
- ✅ Pareto optimality rate differs by >25% between Tier 1 and Tier 3

### Failure Criteria:
- ❌ All tiers perform within 10 points across all scenarios
- ❌ Tier 1 outperforms Tier 2/3 in any scenario (indicates test design flaw)
- ❌ 100% deal closure maintained across all scenarios (tests not hard enough)

---

## Appendix: Tool Usage Expectations

| Tool | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| [`calculate_optimal_guess`](backend/market_tasks.py:173) | ❌ Never | ✅ Always | ✅ Always |
| [`margin_validator`](backend/logic_engine.py:126) | ❌ Never | ✅ Always | ✅ Always |
| [`contract_validator`](backend/logic_engine.py:217) | ❌ Rarely | ✅ Always | ✅ Always |
| [`market_oracle`](backend/logic_engine.py:301) | ❌ Never | ❌ Never | ✅ When needed |
| Diagnostic Questions | ❌ Never | ❌ Never | ✅ Rounds 2-5 |

---

**End of Specification**
