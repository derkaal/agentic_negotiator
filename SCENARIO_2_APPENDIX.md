# Scenario 2: Information Asymmetry - Appendix

**Companion Document to**: SCENARIO_2_INFORMATION_ASYMMETRY_SPEC.md  
**Version**: 1.0  
**Date**: 2026-02-24

---

## Integration Points (Continued)

### Seller Probing Detection

```python
# File: backend/market_tasks.py

def detect_seller_probing(
    seller_message: str,
    buyer_id: str
) -> Optional[str]:
    """
    Detect if seller is probing for information.
    
    Returns:
        Asymmetry type if probing detected, None otherwise
    """
    message_lower = seller_message.lower()
    
    # Urgency probes
    urgency_keywords = ["timeline", "deadline", "when", "urgency", "rush", "time"]
    if any(keyword in message_lower for keyword in urgency_keywords):
        return "urgency"
    
    # Budget probes
    budget_keywords = ["budget", "maximum", "flexibility", "constraint", "afford"]
    if any(keyword in message_lower for keyword in budget_keywords):
        return "budget"
    
    # Alternatives probes
    alternatives_keywords = ["alternative", "competing", "other offer", "comparison", "options"]
    if any(keyword in message_lower for keyword in alternatives_keywords):
        return "alternatives"
    
    # Quality preference probes
    quality_keywords = ["priority", "important", "matter most", "preference", "value"]
    if any(keyword in message_lower for keyword in quality_keywords):
        return "quality"
    
    return None
```

### Buyer Response Generation

```python
# File: backend/market_tasks.py

def generate_buyer_response_to_probe(
    buyer_id: str,
    probe_type: str,
    asymmetries: Dict[str, Any]
) -> str:
    """
    Generate buyer response to seller probing question.
    
    Args:
        buyer_id: Buyer identifier
        probe_type: Type of probe (urgency, budget, alternatives, quality)
        asymmetries: Buyer's hidden information
        
    Returns:
        Buyer's response message
    """
    import random
    
    if probe_type == "urgency" and "urgency" in asymmetries:
        urgency = asymmetries["urgency"]
        
        # 70% chance to reveal if asked directly
        if random.random() < 0.70:
            urgency.disclosed = True
            if urgency.urgency_level == "high":
                return "I need this within the next few days. It's quite urgent."
            elif urgency.urgency_level == "medium":
                return "I'd like to finalize this within a week or so."
            else:
                return "No major rush, but sooner is better."
        else:
            return "Just looking to get a good deal whenever it works out."
    
    elif probe_type == "budget" and "budget" in asymmetries:
        budget = asymmetries["budget"]
        
        # 60% chance to reveal some flexibility
        if random.random() < 0.60:
            budget.disclosed = True
            return f"My budget is around ${budget.claimed_max:.0f}, but I might have some flexibility for the right offer."
        else:
            return f"My maximum is ${budget.claimed_max:.0f}. That's firm."
    
    elif probe_type == "alternatives" and "alternatives" in asymmetries:
        alternatives = asymmetries["alternatives"]
        
        if alternatives.should_reveal_if_asked():
            alternatives.disclosed = True
            if alternatives.has_alternatives:
                return f"I do have another offer at ${alternatives.alternative_price:.0f}."
            else:
                return "Actually, I don't have other offers right now."
        else:
            # Maintain bluff or concealment
            if alternatives.claims_alternatives:
                return "Yes, I have a competitive offer I'm considering."
            else:
                return "This is my only option at the moment."
    
    elif probe_type == "quality" and "quality" in asymmetries:
        quality = asymmetries["quality"]
        
        # 65% chance to reveal true priorities
        if random.random() < 0.65:
            quality.disclosed = True
            if quality.hidden_premium_attribute:
                return f"Honestly, {quality.hidden_premium_attribute} is really important to me."
            else:
                return "Price is my main concern, but I care about overall value."
        else:
            # Give stated priorities
            top_priority = max(quality.stated_priorities.items(), key=lambda x: x[1])
            return f"{top_priority[0].replace('_', ' ').title()} is most important to me."
    
    # Default response
    return "That's a good question. Let me think about that."
```

---

## Success Criteria

### Differentiation Achieved If:

✅ **Tier 3 outperforms Tier 2 by >15 points** in composite score  
✅ **Information extraction rate differs by >60 points** between Tier 3 and Tier 2  
✅ **Premium capture rate differs by >50 points** between Tier 3 and Tier 2  
✅ **Statistical significance achieved** (p < 0.05) for Tier 3 vs Tier 2 comparison  
✅ **Effect size is large** (Cohen's d > 0.8) for key metrics

### Failure Criteria:

❌ **Tier 2 outperforms Tier 3** (indicates scenario doesn't test information extraction)  
❌ **All tiers perform within 10 points** (insufficient differentiation)  
❌ **Tier 3 extraction rate < 50%** (probing mechanism not working)  
❌ **No statistical significance** (sample size insufficient or variance too high)

### Validation Checkpoints:

1. **After 10 runs**: Check if trends match predictions (Tier 3 > Tier 2 > Tier 1)
2. **After 20 runs**: Verify extraction rates are differentiating (Tier 3 >> Tier 2)
3. **After 30 runs**: Confirm statistical significance and effect sizes

---

## Implementation Roadmap

### Phase 1: Core Infrastructure (Week 1)

**Day 1-2: Asymmetry Type Classes**
- [ ] Create [`asymmetry_types.py`](backend/stress_scenarios/utils/asymmetry_types.py)
- [ ] Implement `HiddenUrgency` dataclass
- [ ] Implement `HiddenBudget` dataclass
- [ ] Implement `HiddenAlternatives` dataclass
- [ ] Implement `HiddenQualityPreferences` dataclass
- [ ] Write unit tests for each asymmetry type

**Day 3-4: Information Extraction Tracking**
- [ ] Create [`information_extraction.py`](backend/stress_scenarios/utils/information_extraction.py)
- [ ] Implement discovery tracking mechanism
- [ ] Implement probe detection logic
- [ ] Implement buyer response generation
- [ ] Write unit tests for extraction tracking

**Day 5: Scenario Configuration**
- [ ] Create [`information_asymmetry.yaml`](backend/stress_scenarios/configs/information_asymmetry.yaml)
- [ ] Define asymmetry distribution parameters
- [ ] Define level configurations
- [ ] Validate configuration loading

### Phase 2: Scenario Implementation (Week 2)

**Day 1-2: Main Scenario Class**
- [ ] Create [`information_asymmetry.py`](backend/stress_scenarios/scenarios/information_asymmetry.py)
- [ ] Implement `InformationAsymmetryScenario` class
- [ ] Implement asymmetry initialization
- [ ] Implement negotiation event processing
- [ ] Implement discovery detection

**Day 3-4: Metrics Calculation**
- [ ] Implement information extraction metrics
- [ ] Implement premium capture metrics
- [ ] Implement asymmetry closure rate metrics
- [ ] Implement tier differentiation metrics
- [ ] Implement composite score calculation

**Day 5: Integration**
- [ ] Modify [`market_tasks.py`](backend/market_tasks.py) to support asymmetries
- [ ] Implement buyer state management
- [ ] Implement seller probing detection
- [ ] Test end-to-end flow

### Phase 3: Testing & Validation (Week 3)

**Day 1-2: TDD Tests**
- [ ] Write test for urgency extraction
- [ ] Write test for budget gap discovery
- [ ] Write test for alternative verification
- [ ] Write test for quality preference discovery
- [ ] Write test for Tier 2 blindness
- [ ] Write test for tier differentiation

**Day 3-4: Statistical Testing**
- [ ] Create [`test_scenario2_runner.py`](backend/test_scenario2_runner.py)
- [ ] Implement N=30 test runner
- [ ] Integrate with [`StatisticalAnalyzer`](backend/stress_scenarios/statistical_analysis.py)
- [ ] Run pilot tests (N=5 per tier)
- [ ] Validate metrics collection

**Day 5: Full Test Run**
- [ ] Run N=30 per tier (full test)
- [ ] Collect and analyze results
- [ ] Verify statistical significance
- [ ] Document findings

### Phase 4: Analysis & Reporting (Week 4)

**Day 1-2: Results Analysis**
- [ ] Generate performance comparison tables
- [ ] Create visualization charts
- [ ] Calculate effect sizes
- [ ] Identify key insights

**Day 3-4: Documentation**
- [ ] Write results report
- [ ] Document tier behavior patterns
- [ ] Document lessons learned
- [ ] Update main specification with findings

**Day 5: Presentation**
- [ ] Prepare executive summary
- [ ] Create presentation slides
- [ ] Present findings to stakeholders

---

## Risk Mitigation

### Risk 1: Tier 3 Doesn't Outperform Tier 2

**Likelihood**: Medium  
**Impact**: High (invalidates scenario hypothesis)

**Mitigation**:
- Ensure probing questions are actually asked by Tier 3
- Verify buyer response mechanism works correctly
- Check that discovered information is actually used in pricing
- Consider increasing asymmetry intensity if differentiation is low

**Contingency**:
- If Tier 2 still wins, document why (e.g., Boulware is universally superior)
- Adjust hypothesis: "Information extraction doesn't compensate for Boulware's consistency"

### Risk 2: Information Extraction Rate Too Low

**Likelihood**: Medium  
**Impact**: Medium (reduces differentiation)

**Mitigation**:
- Increase buyer disclosure probability (70% → 85%)
- Expand probe keyword detection
- Add more probing rounds (2-5 → 2-6)
- Simplify probe detection logic

**Contingency**:
- Document actual extraction rates achieved
- Adjust expected outcomes based on empirical data

### Risk 3: High Variance in Results

**Likelihood**: Low  
**Impact**: Medium (reduces statistical power)

**Mitigation**:
- Use N=30 (proven in Scenario 1)
- Control random seed for reproducibility
- Standardize asymmetry distribution
- Use consistent buyer/seller configurations

**Contingency**:
- Increase N to 50 if variance is too high
- Use non-parametric tests if normality assumptions violated

### Risk 4: Implementation Complexity

**Likelihood**: Medium  
**Impact**: Medium (delays timeline)

**Mitigation**:
- Reuse Scenario 1 infrastructure
- Start with simplest asymmetry type (urgency)
- Incremental implementation and testing
- Pair programming for complex logic

**Contingency**:
- Reduce scope to 2 asymmetry types if needed
- Extend timeline by 1 week if necessary

---

## Comparison with Scenario 1

### Similarities

| Aspect | Scenario 1 | Scenario 2 |
|--------|-----------|-----------|
| Sample Size | N=30 per tier | N=30 per tier |
| Statistical Analysis | t-tests, Cohen's d | t-tests, Cohen's d |
| Infrastructure | BaseScenario, MetricsCollector | BaseScenario, MetricsCollector |
| Composite Score | Weighted average | Weighted average |
| Max Rounds | 10 | 10 |

### Differences

| Aspect | Scenario 1 | Scenario 2 |
|--------|-----------|-----------|
| **Focus** | Adversarial resistance | Information extraction |
| **Buyer Behavior** | Aggressive tactics | Hidden information |
| **Expected Winner** | Tier 2 (Math Geek) | Tier 3 (Probing) |
| **Key Metric** | Anchor resistance | Extraction rate |
| **Tier 2 Advantage** | Boulware immunity | None (blind to info) |
| **Tier 3 Advantage** | Moderate probing | Strong probing |
| **Differentiation** | 13-16 points | 20-30 points (expected) |

### Complementary Insights

**Scenario 1 Finding**: Tier 2's Boulware Strategy is highly effective against adversarial tactics

**Scenario 2 Hypothesis**: Tier 2's rigidity becomes a weakness when information extraction is valuable

**Combined Insight**: Optimal seller strategy depends on scenario:
- **Adversarial buyers** → Use Tier 2 (Boulware)
- **Information asymmetry** → Use Tier 3 (Probing)
- **Unknown scenario** → Use Tier 3 (more adaptive)

---

## Future Extensions

### Scenario 2.1: Dynamic Information Revelation

Buyers gradually reveal information over time without probing:
- Round 1-3: No information
- Round 4-6: Hints at urgency
- Round 7-9: Reveals budget flexibility

**Tests**: Whether sellers can detect and exploit voluntary information

### Scenario 2.2: Deceptive Information

Buyers provide false information when probed:
- Claim urgency when none exists
- Understate budget to anchor seller
- Fabricate alternatives

**Tests**: Whether sellers can verify information using tools

### Scenario 2.3: Multi-Party Information Asymmetry

Multiple buyers with different hidden information:
- Buyer A: Hidden urgency
- Buyer B: Hidden budget
- Buyer C: No asymmetry

**Tests**: Whether sellers can differentiate and adapt strategy per buyer

### Scenario 2.4: Seller Information Asymmetry

Reverse the asymmetry - sellers have hidden information:
- Hidden inventory levels
- Hidden cost structure
- Hidden competing sellers

**Tests**: Whether buyers can extract seller information

---

## Appendix: Code Templates

### Template 1: Asymmetry Type

```python
@dataclass
class HiddenXYZ:
    """
    Hidden XYZ asymmetry.
    
    Description of what information is hidden.
    """
    # Core attributes
    has_xyz: bool
    xyz_level: str  # "low", "medium", "high"
    xyz_value: float
    
    # Discovery tracking
    disclosed: bool = False
    discovery_round: Optional[int] = None
    
    def get_xyz_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate effect of XYZ on negotiation.
        
        Args:
            context: Negotiation context
            
        Returns:
            Effect value
        """
        if not self.has_xyz:
            return 0.0
        
        # Implementation logic
        pass
    
    def should_reveal_if_asked(self) -> bool:
        """
        Determine if buyer reveals XYZ when questioned.
        
        Returns:
            True if buyer reveals
        """
        import random
        return random.random() < 0.70  # 70% disclosure rate
```

### Template 2: Metric Calculation

```python
def calculate_xyz_metric(
    deals: List[Dict[str, Any]],
    tier: int
) -> Dict[str, float]:
    """
    Calculate XYZ metric for a specific tier.
    
    Args:
        deals: List of completed deals
        tier: Seller tier (1, 2, or 3)
        
    Returns:
        Dictionary with metric values
    """
    tier_deals = [d for d in deals if d.get("seller_tier") == tier]
    
    if not tier_deals:
        return {
            "xyz_rate": 0.0,
            "xyz_avg": 0.0,
            "xyz_count": 0
        }
    
    # Calculate metric
    xyz_values = []
    for deal in tier_deals:
        # Extract XYZ value from deal
        xyz_value = calculate_xyz_for_deal(deal)
        xyz_values.append(xyz_value)
    
    return {
        "xyz_rate": (len(xyz_values) / len(tier_deals)) * 100,
        "xyz_avg": sum(xyz_values) / len(xyz_values) if xyz_values else 0.0,
        "xyz_count": len(xyz_values)
    }
```

### Template 3: TDD Test

```python
@pytest.mark.asyncio
async def test_xyz_behavior():
    """
    GIVEN: Specific asymmetry configuration
    WHEN: Tier X negotiates
    THEN: Expected behavior occurs
    """
    # Arrange
    config = ScenarioConfig(
        scenario_id="test_xyz",
        name="Test XYZ",
        description="Test XYZ behavior",
        parameters={
            "asymmetry_distribution": {
                "xyz_probability": 1.0  # 100% XYZ asymmetry
            }
        }
    )
    
    scenario = InformationAsymmetryScenario(config)
    
    # Act
    result = await scenario.execute()
    
    # Assert
    tier_performance = result.tier_performance.get(TIER_NUMBER, {})
    xyz_metric = tier_performance.get("xyz_metric", 0.0)
    
    assert xyz_metric > EXPECTED_THRESHOLD, f"Expected XYZ > {EXPECTED_THRESHOLD}"
```

---

## Glossary

**Asymmetry**: Imbalance in information between buyer and seller

**BATNA**: Best Alternative To a Negotiated Agreement

**Boulware Strategy**: Concession strategy that starts high and concedes slowly (β=2.0)

**Composite Score**: Weighted average of multiple performance metrics

**Discovery**: Seller learning hidden buyer information through probing

**Extraction Rate**: Percentage of hidden information successfully discovered

**Information Asymmetry**: Situation where one party has more/better information than the other

**Premium Capture**: Additional value extracted by leveraging hidden information

**Probing**: Asking diagnostic questions to extract information

**ZOPA**: Zone of Possible Agreement (range between buyer max and seller min)

---

## References

1. **Scenario 1 Results**: STRESS_TEST_FINAL_ANALYSIS.md
2. **Boulware Implementation**: BOULWARE_IMPLEMENTATION_RESULTS.md
3. **Statistical Methods**: STATISTICAL_ANALYSIS_REPORT.md
4. **Base Specification**: docs/STRESS_TEST_SCENARIOS.md
5. **Infrastructure**: backend/stress_scenarios/base.py

---

**End of Appendix**
