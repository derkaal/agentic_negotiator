# Scenario 2: Information Asymmetry - Implementation Specification

**Version**: 1.0  
**Date**: 2026-02-24  
**Status**: Ready for Architecture Phase  
**Previous Scenario**: Scenario 1 (Adversarial Buyer) - COMPLETED ✅

---

## Executive Summary

This specification defines the implementation of **Scenario 2: Information Asymmetry**, which tests how sellers perform when buyers possess hidden information that could influence negotiation strategy. Building on the success of Scenario 1 (where Tier 2 Math Geek achieved 92.69% ± 0.12), this scenario is designed to test whether **Tier 3 (Probing Strategist)** can leverage its information extraction capabilities to outperform the pure algorithmic approach.

### Key Hypothesis
**Tier 3 (Probing Strategist) should excel when information asymmetry is present**, as its diagnostic questioning capabilities can extract hidden buyer information that Tier 2 (Math Geek) cannot access through formulas alone.

---

## Table of Contents

1. [Scenario Objective](#scenario-objective)
2. [Information Asymmetry Types](#information-asymmetry-types)
3. [Metrics Framework](#metrics-framework)
4. [Expected Tier Behaviors](#expected-tier-behaviors)
5. [Implementation Architecture](#implementation-architecture)
6. [Test Configuration](#test-configuration)
7. [Expected Outcomes](#expected-outcomes)
8. [TDD Anchors](#tdd-anchors)
9. [Integration Points](#integration-points)
10. [Success Criteria](#success-criteria)

---

## Scenario Objective

Test how sellers perform when buyers have **hidden information** that creates information asymmetry:

- **Hidden urgency**: Buyer has deadline but doesn't disclose it
- **Hidden budget**: Buyer has higher max price than they claim
- **Hidden alternatives**: Buyer has/doesn't have competing offers
- **Hidden quality requirements**: Buyer values specific attributes highly

### Research Question
Can Tier 3 (Probing Strategist) extract hidden information and leverage it to achieve better outcomes than Tier 2 (Math Geek), which relies purely on Boulware Strategy without information gathering?

---

## Information Asymmetry Types

### 2.1 Hidden Urgency (Time-Based Asymmetry)

**Description**: Buyer has an undisclosed deadline that increases their willingness to pay as time runs out.

**Implementation**:
```python
@dataclass
class HiddenUrgency:
    """
    Hidden urgency asymmetry.
    
    Buyer has deadline but doesn't disclose it initially.
    Willingness to pay increases as deadline approaches.
    """
    has_urgency: bool
    deadline_round: int  # Round when urgency becomes critical
    urgency_level: str  # "low", "medium", "high"
    price_premium_at_deadline: float  # Additional % willing to pay
    disclosed: bool = False  # Whether seller discovered it
    discovery_round: Optional[int] = None  # When seller discovered it
    
    def get_urgency_multiplier(self, current_round: int) -> float:
        """
        Calculate urgency multiplier based on proximity to deadline.
        
        Returns:
            Multiplier for buyer's max price (1.0 to 1.0 + premium)
        """
        if not self.has_urgency:
            return 1.0
        
        if current_round >= self.deadline_round:
            return 1.0 + self.price_premium_at_deadline
        
        # Linear increase as deadline approaches
        rounds_to_deadline = self.deadline_round - current_round
        total_rounds = self.deadline_round - 1
        
        if total_rounds <= 0:
            return 1.0 + self.price_premium_at_deadline
        
        urgency_factor = 1 - (rounds_to_deadline / total_rounds)
        return 1.0 + (self.price_premium_at_deadline * urgency_factor)

# Configuration levels
URGENCY_LEVELS = {
    "low": {
        "deadline_round": 8,
        "price_premium": 0.05  # 5% increase
    },
    "medium": {
        "deadline_round": 6,
        "price_premium": 0.10  # 10% increase
    },
    "high": {
        "deadline_round": 4,
        "price_premium": 0.15  # 15% increase
    }
}
```

**Discovery Mechanism**:
- Tier 3 can ask: "What's your timeline for this purchase?"
- If asked, buyer reveals urgency with 70% probability
- Discovery allows seller to adjust strategy (wait vs. close quickly)

**Metrics**:
- `urgency_discovery_rate`: % of hidden urgencies discovered
- `urgency_exploitation_score`: How well seller leveraged discovered urgency
- `price_premium_captured`: Additional value extracted from urgent buyers

---

### 2.2 Hidden Budget (Price-Based Asymmetry)

**Description**: Buyer has higher maximum price than they initially claim or signal.

**Implementation**:
```python
@dataclass
class HiddenBudget:
    """
    Hidden budget asymmetry.
    
    Buyer has higher max price than they claim.
    """
    claimed_max: float  # What buyer says their max is
    actual_max: float  # True maximum price
    budget_gap: float  # actual_max - claimed_max
    gap_percentage: float  # (budget_gap / actual_max) * 100
    disclosed: bool = False
    discovery_round: Optional[int] = None
    
    def get_claimed_reservation(self) -> float:
        """Return the price buyer claims as their maximum."""
        return self.claimed_max
    
    def get_actual_reservation(self) -> float:
        """Return the true maximum price."""
        return self.actual_max
    
    def is_offer_acceptable(self, price: float) -> bool:
        """Check if offer is within actual budget."""
        return price <= self.actual_max
    
    def would_claim_unacceptable(self, price: float) -> bool:
        """Check if buyer would claim offer exceeds budget."""
        return price > self.claimed_max

# Configuration levels
BUDGET_GAP_LEVELS = {
    "low": {
        "gap_percentage": 0.05,  # 5% hidden budget
        "example": "claimed=$150, actual=$157.50"
    },
    "medium": {
        "gap_percentage": 0.10,  # 10% hidden budget
        "example": "claimed=$150, actual=$165"
    },
    "high": {
        "gap_percentage": 0.15,  # 15% hidden budget
        "example": "claimed=$150, actual=$172.50"
    }
}
```

**Discovery Mechanism**:
- Tier 3 can probe: "What's driving your budget constraint?"
- Buyer may reveal flexibility if asked about priorities
- Seller can test with offers slightly above claimed max

**Metrics**:
- `budget_gap_discovery_rate`: % of hidden budgets discovered
- `hidden_budget_extraction`: % of gap captured in final price
- `above_claimed_max_deals`: Deals closed above buyer's claimed maximum

---

### 2.3 Hidden Alternatives (Competition-Based Asymmetry)

**Description**: Buyer has (or doesn't have) competing offers but misrepresents this.

**Implementation**:
```python
@dataclass
class HiddenAlternatives:
    """
    Hidden alternatives asymmetry.
    
    Buyer misrepresents whether they have competing offers.
    """
    has_alternatives: bool  # True state
    claims_alternatives: bool  # What buyer says
    alternative_price: Optional[float]  # Price of alternative if exists
    alternative_quality: str  # "better", "same", "worse"
    is_bluffing: bool  # claims_alternatives != has_alternatives
    disclosed: bool = False
    discovery_round: Optional[int] = None
    
    def get_batna_strength(self) -> float:
        """
        Calculate BATNA strength (0.0 to 1.0).
        
        Returns:
            0.0 = no alternative, 1.0 = strong alternative
        """
        if not self.has_alternatives:
            return 0.0
        
        quality_scores = {
            "better": 1.0,
            "same": 0.7,
            "worse": 0.4
        }
        
        return quality_scores.get(self.alternative_quality, 0.5)
    
    def should_reveal_if_asked(self) -> bool:
        """
        Determine if buyer reveals truth when questioned.
        
        Returns:
            True if buyer reveals truth (80% if has alternative, 60% if bluffing)
        """
        import random
        if self.has_alternatives:
            return random.random() < 0.80  # Usually reveal real alternatives
        else:
            return random.random() < 0.60  # Sometimes admit bluffing

# Configuration scenarios
ALTERNATIVE_SCENARIOS = {
    "no_alternative_honest": {
        "has_alternatives": False,
        "claims_alternatives": False,
        "is_bluffing": False
    },
    "no_alternative_bluffing": {
        "has_alternatives": False,
        "claims_alternatives": True,
        "is_bluffing": True,
        "claimed_price": "market_avg * 0.85"
    },
    "has_alternative_honest": {
        "has_alternatives": True,
        "claims_alternatives": True,
        "is_bluffing": False,
        "alternative_price": "market_avg * 0.90",
        "alternative_quality": "same"
    },
    "has_alternative_concealed": {
        "has_alternatives": True,
        "claims_alternatives": False,
        "is_bluffing": True,
        "alternative_price": "market_avg * 0.92",
        "alternative_quality": "worse"
    }
}
```

**Discovery Mechanism**:
- Tier 3 can ask: "Can you share details about your alternative offer?"
- Tier 2/3 can use [`market_oracle`](backend/logic_engine.py:301) to verify claims
- Bluff detection increases seller's negotiating power

**Metrics**:
- `bluff_detection_rate`: % of false claims detected
- `alternative_verification_rate`: % of claims verified via tools
- `batna_exploitation_score`: How well seller leveraged BATNA knowledge

---

### 2.4 Hidden Quality Requirements (Preference-Based Asymmetry)

**Description**: Buyer values specific attributes (speed, warranty, brand) more than they reveal.

**Implementation**:
```python
@dataclass
class HiddenQualityPreferences:
    """
    Hidden quality preferences asymmetry.
    
    Buyer has strong preferences for specific attributes
    but doesn't disclose them initially.
    """
    stated_priorities: Dict[str, float]  # What buyer claims to value
    actual_priorities: Dict[str, float]  # True attribute weights
    hidden_premium_attribute: str  # Attribute buyer secretly values highly
    premium_willingness: float  # Extra % willing to pay for premium attribute
    disclosed: bool = False
    discovery_round: Optional[int] = None
    
    def get_stated_weights(self) -> Dict[str, float]:
        """Return claimed attribute weights."""
        return self.stated_priorities.copy()
    
    def get_actual_weights(self) -> Dict[str, float]:
        """Return true attribute weights."""
        return self.actual_priorities.copy()
    
    def calculate_utility(
        self,
        offer_attributes: Dict[str, Any],
        use_actual: bool = True
    ) -> float:
        """
        Calculate utility of an offer.
        
        Args:
            offer_attributes: Offer attributes (price, speed, warranty, etc.)
            use_actual: Use actual vs stated preferences
            
        Returns:
            Utility score (0-100)
        """
        weights = self.actual_priorities if use_actual else self.stated_priorities
        
        # Normalize attributes to 0-1 scale
        normalized = self._normalize_attributes(offer_attributes)
        
        # Calculate weighted sum
        utility = sum(
            weights.get(attr, 0) * normalized.get(attr, 0)
            for attr in weights.keys()
        )
        
        return round(utility * 100, 2)
    
    def _normalize_attributes(
        self,
        attributes: Dict[str, Any]
    ) -> Dict[str, float]:
        """Normalize attributes to 0-1 scale."""
        # Implementation depends on attribute types
        # Price: lower is better (inverse normalization)
        # Speed: faster is better
        # Warranty: longer is better
        pass

# Configuration levels
QUALITY_PREFERENCE_SCENARIOS = {
    "speed_focused": {
        "stated_priorities": {
            "price": 0.50,
            "delivery_speed": 0.30,
            "warranty": 0.20
        },
        "actual_priorities": {
            "price": 0.30,
            "delivery_speed": 0.60,  # Hidden premium
            "warranty": 0.10
        },
        "hidden_premium_attribute": "delivery_speed",
        "premium_willingness": 0.12  # 12% more for fast delivery
    },
    "warranty_focused": {
        "stated_priorities": {
            "price": 0.60,
            "delivery_speed": 0.20,
            "warranty": 0.20
        },
        "actual_priorities": {
            "price": 0.30,
            "delivery_speed": 0.15,
            "warranty": 0.55  # Hidden premium
        },
        "hidden_premium_attribute": "warranty",
        "premium_willingness": 0.10  # 10% more for extended warranty
    },
    "price_focused_honest": {
        "stated_priorities": {
            "price": 0.70,
            "delivery_speed": 0.15,
            "warranty": 0.15
        },
        "actual_priorities": {
            "price": 0.70,
            "delivery_speed": 0.15,
            "warranty": 0.15
        },
        "hidden_premium_attribute": None,
        "premium_willingness": 0.0
    }
}
```

**Discovery Mechanism**:
- Tier 3 can ask: "What matters most to you in this purchase?"
- Seller can test with differentiated offers to reveal preferences
- Discovery allows value-based pricing on premium attributes

**Metrics**:
- `preference_discovery_rate`: % of hidden preferences discovered
- `value_based_pricing_score`: How well seller priced based on preferences
- `premium_attribute_exploitation`: Revenue from premium attributes

---

## Metrics Framework

### Primary Metrics (Scenario-Specific)

#### 1. Information Extraction Rate
```python
def calculate_information_extraction_rate(
    total_asymmetries: int,
    asymmetries_discovered: int,
    discovery_rounds: List[int]
) -> Dict[str, float]:
    """
    Measure how effectively seller extracts hidden information.
    
    Args:
        total_asymmetries: Total hidden information items
        asymmetries_discovered: Number discovered
        discovery_rounds: Rounds when discoveries occurred
        
    Returns:
        Dictionary with extraction metrics
    """
    if total_asymmetries == 0:
        return {
            "extraction_rate": 0.0,
            "avg_discovery_round": 0.0,
            "extraction_speed_score": 0.0
        }
    
    extraction_rate = (asymmetries_discovered / total_asymmetries) * 100
    
    # Average discovery round (lower is better)
    avg_discovery_round = (
        sum(discovery_rounds) / len(discovery_rounds)
        if discovery_rounds else 10.0
    )
    
    # Speed score: 100 if discovered in round 1, 0 if round 10
    speed_score = max(0, 100 - (avg_discovery_round - 1) * 11.11)
    
    return {
        "extraction_rate": round(extraction_rate, 2),
        "avg_discovery_round": round(avg_discovery_round, 2),
        "extraction_speed_score": round(speed_score, 2)
    }
```

#### 2. Price Premium Captured
```python
def calculate_price_premium_captured(
    final_price: float,
    baseline_price: float,  # Price without asymmetry knowledge
    max_extractable_premium: float  # Maximum possible premium
) -> Dict[str, float]:
    """
    Measure how much hidden budget/urgency seller captured.
    
    Args:
        final_price: Actual deal price
        baseline_price: Expected price without information
        max_extractable_premium: Maximum additional value available
        
    Returns:
        Dictionary with premium capture metrics
    """
    if max_extractable_premium <= 0:
        return {
            "premium_captured": 0.0,
            "premium_capture_rate": 0.0,
            "premium_efficiency": 0.0
        }
    
    actual_premium = final_price - baseline_price
    premium_capture_rate = (actual_premium / max_extractable_premium) * 100
    
    # Efficiency: premium per round
    # (Higher is better - captured premium quickly)
    
    return {
        "premium_captured": round(actual_premium, 2),
        "premium_capture_rate": round(max(0, min(100, premium_capture_rate)), 2),
        "premium_efficiency": round(actual_premium, 2)
    }
```

#### 3. Deal Closure Rate Under Asymmetry
```python
def calculate_asymmetry_closure_rate(
    deals_with_asymmetry: int,
    total_asymmetry_scenarios: int,
    deals_without_asymmetry: int,
    total_baseline_scenarios: int
) -> Dict[str, float]:
    """
    Compare closure rates with vs without information asymmetry.
    
    Returns:
        Dictionary with closure rate comparison
    """
    asymmetry_closure_rate = (
        (deals_with_asymmetry / total_asymmetry_scenarios) * 100
        if total_asymmetry_scenarios > 0 else 0.0
    )
    
    baseline_closure_rate = (
        (deals_without_asymmetry / total_baseline_scenarios) * 100
        if total_baseline_scenarios > 0 else 0.0
    )
    
    closure_rate_delta = asymmetry_closure_rate - baseline_closure_rate
    
    return {
        "asymmetry_closure_rate": round(asymmetry_closure_rate, 2),
        "baseline_closure_rate": round(baseline_closure_rate, 2),
        "closure_rate_delta": round(closure_rate_delta, 2),
        "asymmetry_resilience": round(asymmetry_closure_rate, 2)
    }
```

#### 4. Tier Performance Differentiation
```python
def calculate_tier_differentiation(
    tier_scores: Dict[int, float]
) -> Dict[str, Any]:
    """
    Measure performance differentiation across tiers.
    
    Args:
        tier_scores: Dictionary mapping tier -> composite score
        
    Returns:
        Differentiation metrics
    """
    scores = list(tier_scores.values())
    
    if len(scores) < 2:
        return {"differentiation_score": 0.0}
    
    # Calculate range and standard deviation
    score_range = max(scores) - min(scores)
    score_std = statistics.stdev(scores) if len(scores) >= 2 else 0.0
    
    # Rank tiers
    ranked_tiers = sorted(
        tier_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    return {
        "score_range": round(score_range, 2),
        "score_std_dev": round(score_std, 2),
        "tier_ranking": [tier for tier, _ in ranked_tiers],
        "best_tier": ranked_tiers[0][0],
        "best_score": round(ranked_tiers[0][1], 2),
        "differentiation_score": round(score_range, 2)
    }
```

### Secondary Metrics (Inherited from Scenario 1)

- **Relative Price Achievement**: Floor-normalized ZOPA score
- **Market-Relative Performance**: Performance vs market average
- **Absolute Price Ranking**: Tier ranking by final price
- **Efficiency Score**: Rounds-to-deal efficiency
- **Composite Score**: Weighted average of all metrics

### Composite Score Calculation (Scenario 2)

```python
def calculate_scenario2_composite_score(
    information_extraction_rate: float,  # 0-100
    price_premium_captured: float,  # 0-100
    asymmetry_closure_rate: float,  # 0-100
    relative_price_achievement: float,  # 0-100 (from Scenario 1)
    efficiency_score: float  # 0-100 (from Scenario 1)
) -> float:
    """
    Calculate weighted composite score for Scenario 2.
    
    Weights:
    - 30% Information Extraction Rate (scenario-specific)
    - 25% Price Premium Captured (scenario-specific)
    - 20% Asymmetry Closure Rate (scenario-specific)
    - 15% Relative Price Achievement (baseline)
    - 10% Efficiency Score (baseline)
    
    Returns:
        Composite score (0-100)
    """
    composite = (
        0.30 * information_extraction_rate +
        0.25 * price_premium_captured +
        0.20 * asymmetry_closure_rate +
        0.15 * relative_price_achievement +
        0.10 * efficiency_score
    )
    
    return round(composite, 2)
```

---

## Expected Tier Behaviors

### Tier 1: Solo LLM (Baseline)

**Strengths**:
- May occasionally ask probing questions
- Can adapt responses based on conversation flow
- Natural language understanding

**Weaknesses**:
- **No systematic information extraction**: Questions are ad-hoc, not strategic
- **May hallucinate buyer information**: Assumes urgency/budget without evidence
- **Inconsistent probing**: Sometimes asks, sometimes doesn't
- **Poor information integration**: Doesn't leverage discovered information effectively

**Expected Performance**:
- Information Extraction Rate: **20-35%** (occasional lucky questions)
- Price Premium Captured: **15-30%** (mostly by chance)
- Asymmetry Closure Rate: **65-75%** (may struggle with hidden constraints)
- **Composite Score: 45-60/100**

**Behavioral Pattern**:
```python
# Tier 1 behavior pseudocode
if random.random() < 0.3:  # 30% chance to probe
    ask_generic_question()  # "What's your timeline?"
    
if buyer_mentions_urgency:
    maybe_adjust_price()  # Inconsistent exploitation
else:
    ignore_information()  # Doesn't integrate well
```

---

### Tier 2: Math Geek (Algorithmic)

**Strengths**:
- **Anchor-Resistant Boulware Strategy**: Proven effective (92.69% in Scenario 1)
- Consistent, formula-based pricing
- Immune to manipulation

**Weaknesses**:
- **Zero information extraction**: No probing questions
- **Blind to asymmetry**: Treats all buyers identically
- **Cannot leverage hidden information**: Even if buyer volunteers info
- **Misses value opportunities**: Doesn't discover premium willingness

**Expected Performance**:
- Information Extraction Rate: **0%** (no probing capability)
- Price Premium Captured: **0-10%** (only if buyer volunteers info)
- Asymmetry Closure Rate: **85-95%** (strong baseline, but misses opportunities)
- **Composite Score: 50-65/100**

**Behavioral Pattern**:
```python
# Tier 2 behavior pseudocode
def make_offer(round_num):
    # Boulware Strategy - no information gathering
    return calculate_boulware_price(
        seller_floor=120,
        target_price=165,
        round=round_num,
        max_rounds=10,
        beta=2.0
    )
    # Never asks questions, never adapts to hidden information
```

**Key Insight**: Tier 2's strength in Scenario 1 (adversarial resistance) becomes a weakness in Scenario 2 (information asymmetry). The same rigidity that protects against anchoring prevents information extraction.

---

### Tier 3: Probing Strategist (Hybrid)

**Strengths**:
- **Systematic information extraction**: Diagnostic questions in rounds 2-5
- **Tool-based verification**: Uses [`market_oracle`](backend/logic_engine.py:301) to verify claims
- **Adaptive strategy**: Adjusts pricing based on discovered information
- **Multi-dimensional probing**: Asks about urgency, budget, alternatives, preferences

**Weaknesses**:
- More complex than Tier 2 (potential for errors)
- Requires buyer cooperation (some info may remain hidden)
- Slower initial rounds (time spent probing)

**Expected Performance**:
- Information Extraction Rate: **70-85%** (systematic probing)
- Price Premium Captured: **60-80%** (leverages discovered information)
- Asymmetry Closure Rate: **80-90%** (adapts to constraints)
- **Composite Score: 75-90/100** ⭐ **EXPECTED WINNER**

**Behavioral Pattern**:
```python
# Tier 3 behavior pseudocode
def make_offer(round_num):
    if round_num in [2, 3, 4]:
        # Information extraction phase
        probe_urgency()
        probe_budget_flexibility()
        probe_alternatives()
        probe_quality_preferences()
    
    # Integrate discovered information
    discovered_info = get_discovered_asymmetries()
    
    if discovered_info.has_urgency and round_num >= discovered_info.deadline_round - 1:
        # Exploit urgency
        return calculate_premium_price(base_price, urgency_premium=0.10)
    
    elif discovered_info.hidden_budget_gap > 0:
        # Test above claimed maximum
        return discovered_info.claimed_max * 1.05
    
    else:
        # Fall back to Boulware
        return calculate_boulware_price(...)
```

---

## Implementation Architecture

### File Structure

```
backend/stress_scenarios/
├── scenarios/
│   ├── information_asymmetry.py          # Main scenario implementation
│   └── __init__.py
├── utils/
│   ├── asymmetry_types.py                # Asymmetry dataclasses
│   ├── information_extraction.py         # Discovery tracking
│   └── __init__.py
├── configs/
│   └── information_asymmetry.yaml        # Scenario configuration
└── tests/
    └── test_information_asymmetry.py     # TDD tests
```

### Core Classes

#### 1. InformationAsymmetryScenario

```python
# File: backend/stress_scenarios/scenarios/information_asymmetry.py

from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from stress_scenarios.base import BaseScenario, ScenarioConfig
from stress_scenarios.metrics import MetricsCollector
from stress_scenarios.utils.asymmetry_types import (
    HiddenUrgency,
    HiddenBudget,
    HiddenAlternatives,
    HiddenQualityPreferences
)

class InformationAsymmetryScenario(BaseScenario):
    """
    Scenario 2: Information Asymmetry.
    
    Tests seller performance when buyers have hidden information:
    - Hidden urgency (deadline pressure)
    - Hidden budget (higher max than claimed)
    - Hidden alternatives (competing offers)
    - Hidden quality preferences (attribute priorities)
    """
    
    def __init__(self, config: ScenarioConfig):
        """Initialize information asymmetry scenario."""
        super().__init__(config)
        
        self.metrics_collector = MetricsCollector(config.scenario_id)
        
        # Initialize asymmetry types for each buyer
        self._buyer_asymmetries: Dict[str, Dict[str, Any]] = {}
        self._initialize_asymmetries()
        
        # Track discoveries
        self._discoveries: Dict[str, List[Dict[str, Any]]] = {}
        self._deals: List[Dict[str, Any]] = []
    
    def _initialize_asymmetries(self):
        """
        Initialize hidden information for each buyer.
        
        Randomly assigns asymmetry types and levels based on config.
        """
        asymmetry_config = self.config.parameters.get("asymmetry_distribution", {})
        
        # For each buyer, assign 1-2 asymmetry types
        buyer_count = self.config.parameters.get("buyer_count", 3)
        
        for buyer_id in range(buyer_count):
            buyer_key = f"buyer_{buyer_id}"
            
            asymmetries = {}
            
            # Assign asymmetry types based on distribution
            if self._should_assign_asymmetry("urgency", asymmetry_config):
                asymmetries["urgency"] = self._create_urgency_asymmetry()
            
            if self._should_assign_asymmetry("budget", asymmetry_config):
                asymmetries["budget"] = self._create_budget_asymmetry()
            
            if self._should_assign_asymmetry("alternatives", asymmetry_config):
                asymmetries["alternatives"] = self._create_alternatives_asymmetry()
            
            if self._should_assign_asymmetry("quality", asymmetry_config):
                asymmetries["quality"] = self._create_quality_asymmetry()
            
            self._buyer_asymmetries[buyer_key] = asymmetries
            self._discoveries[buyer_key] = []
    
    def _should_assign_asymmetry(
        self,
        asymmetry_type: str,
        config: Dict[str, Any]
    ) -> bool:
        """Determine if asymmetry type should be assigned."""
        import random
        probability = config.get(f"{asymmetry_type}_probability", 0.5)
        return random.random() < probability
    
    def _create_urgency_asymmetry(self) -> HiddenUrgency:
        """Create hidden urgency asymmetry."""
        import random
        
        level = random.choice(["low", "medium", "high"])
        level_config = URGENCY_LEVELS[level]
        
        return HiddenUrgency(
            has_urgency=True,
            deadline_round=level_config["deadline_round"],
            urgency_level=level,
            price_premium_at_deadline=level_config["price_premium"]
        )
    
    def _create_budget_asymmetry(self) -> HiddenBudget:
        """Create hidden budget asymmetry."""
        import random
        
        level = random.choice(["low", "medium", "high"])
        gap_percentage = BUDGET_GAP_LEVELS[level]["gap_percentage"]
        
        market_avg = self.config.market_avg
        actual_max = market_avg * 1.10  # 10% above market
        claimed_max = actual_max * (1 - gap_percentage)
        
        return HiddenBudget(
            claimed_max=claimed_max,
            actual_max=actual_max,
            budget_gap=actual_max - claimed_max,
            gap_percentage=gap_percentage * 100
        )
    
    def _create_alternatives_asymmetry(self) -> HiddenAlternatives:
        """Create hidden alternatives asymmetry."""
        import random
        
        scenario = random.choice([
            "no_alternative_honest",
            "no_alternative_bluffing",
            "has_alternative_honest",
            "has_alternative_concealed"
        ])
