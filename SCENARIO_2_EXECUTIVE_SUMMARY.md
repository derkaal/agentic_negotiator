# Scenario 2: Information Asymmetry - Executive Summary

**Version**: 1.0  
**Date**: 2026-02-24  
**Status**: ✅ SPECIFICATION COMPLETE - Ready for Architect Mode  
**Author**: Specification Writer Mode (SPARC)

---

## 📋 Document Set

This specification consists of three documents:

1. **SCENARIO_2_INFORMATION_ASYMMETRY_SPEC.md** (Main Specification - 879 lines)
   - Complete technical specification with asymmetry types, metrics, and implementation details
   
2. **SCENARIO_2_APPENDIX.md** (Appendix)
   - Integration points, risk mitigation, roadmap, and code templates
   
3. **SCENARIO_2_EXECUTIVE_SUMMARY.md** (This Document)
   - High-level overview and handoff to architect mode

---

## 🎯 Scenario Objective

Test how sellers perform when buyers possess **hidden information** that creates information asymmetry:

- **Hidden urgency**: Buyer has deadline but doesn't disclose it
- **Hidden budget**: Buyer has higher max price than they claim  
- **Hidden alternatives**: Buyer has/doesn't have competing offers
- **Hidden quality requirements**: Buyer values specific attributes highly

---

## 🔬 Research Hypothesis

**Tier 3 (Probing Strategist) will outperform Tier 2 (Math Geek) in information asymmetry scenarios.**

### Rationale

**Scenario 1 Result**: Tier 2 (Math Geek) dominated with 92.69% ± 0.12 using Boulware Strategy

**Scenario 2 Prediction**: Tier 2's strength (algorithmic consistency) becomes a weakness when information extraction is valuable

**Key Insight**: Boulware Strategy is blind to hidden information. Tier 3's probing capability should extract and exploit asymmetries that Tier 2 cannot access.

---

## 📊 Expected Results (N=30, Medium Asymmetry)

| Tier | Name | Extraction Rate | Premium Capture | Composite Score | Rank |
|------|------|----------------|-----------------|-----------------|------|
| 1 | Solo LLM | 25% ± 8% | 20% ± 10% | **52 ± 6** | 3rd |
| 2 | Math Geek | 5% ± 3% | 8% ± 5% | **62 ± 4** | 2nd |
| 3 | Probing | 78% ± 5% | 68% ± 8% | **82 ± 5** | 🏆 1st |

**Expected Differentiation**: 20-30 point gap between Tier 3 and Tier 2

**Statistical Significance**: p < 0.001, Cohen's d > 3.0 (large effect)

---

## 🏗️ Implementation Architecture

### File Structure

```
backend/stress_scenarios/
├── scenarios/
│   └── information_asymmetry.py          # Main scenario (InformationAsymmetryScenario)
├── utils/
│   ├── asymmetry_types.py                # HiddenUrgency, HiddenBudget, etc.
│   └── information_extraction.py         # Discovery tracking
├── configs/
│   └── information_asymmetry.yaml        # Scenario configuration
└── tests/
    └── test_information_asymmetry.py     # TDD tests
```

### Core Components

1. **Asymmetry Types** (4 types)
   - `HiddenUrgency`: Time-based pressure (deadline → price premium)
   - `HiddenBudget`: Price gap (claimed max < actual max)
   - `HiddenAlternatives`: Competition misrepresentation (bluffing)
   - `HiddenQualityPreferences`: Attribute priorities (hidden premium willingness)

2. **Metrics Framework** (4 primary + 5 secondary)
   - Information Extraction Rate (0-100%)
   - Price Premium Captured (0-100%)
   - Asymmetry Closure Rate (0-100%)
   - Tier Performance Differentiation
   - Plus: Relative Price Achievement, Market-Relative Performance, Absolute Ranking, Efficiency, Composite Score

3. **Discovery Mechanism**
   - Seller probing detection (keyword matching)
   - Buyer response generation (probabilistic disclosure)
   - Discovery tracking (round, type, tier)
   - Exploitation measurement (premium captured)

---

## 🧪 Test Configuration

### Statistical Rigor (Matching Scenario 1)

- **Sample Size**: N=30 per tier (proven effective in Scenario 1)
- **Statistical Tests**: Independent t-tests, Cohen's d effect sizes
- **Significance Level**: α = 0.05
- **Expected Runtime**: ~45 minutes (30 runs × 3 tiers × 30 seconds)

### Asymmetry Distribution (Medium Level)

```yaml
asymmetry_distribution:
  urgency_probability: 0.60      # 60% of buyers
  budget_probability: 0.50       # 50% of buyers
  alternatives_probability: 0.40 # 40% of buyers
  quality_probability: 0.30      # 30% of buyers
```

### Asymmetry Levels

- **Low**: 5% gaps, round 8 deadlines, 30% probability
- **Medium**: 10% gaps, round 6 deadlines, 50% probability
- **High**: 15% gaps, round 4 deadlines, 90% probability

---

## ✅ Success Criteria

### Differentiation Achieved If:

✅ Tier 3 outperforms Tier 2 by **>15 points** in composite score  
✅ Information extraction rate differs by **>60 points** between Tier 3 and Tier 2  
✅ Premium capture rate differs by **>50 points** between Tier 3 and Tier 2  
✅ Statistical significance achieved (**p < 0.05**)  
✅ Effect size is large (**Cohen's d > 0.8**)

### Failure Criteria:

❌ Tier 2 outperforms Tier 3 (scenario doesn't test information extraction)  
❌ All tiers perform within 10 points (insufficient differentiation)  
❌ Tier 3 extraction rate < 50% (probing mechanism not working)  
❌ No statistical significance (sample size insufficient)

---

## 🎯 Expected Tier Behaviors

### Tier 1: Solo LLM
- **Strengths**: Occasional probing, natural language
- **Weaknesses**: Inconsistent, may hallucinate, poor integration
- **Expected**: 25% extraction, 20% premium capture, 52 composite score

### Tier 2: Math Geek
- **Strengths**: Boulware Strategy (proven 92.69% in Scenario 1)
- **Weaknesses**: **Zero probing**, blind to asymmetry, cannot leverage hidden info
- **Expected**: 5% extraction, 8% premium capture, 62 composite score
- **Key Insight**: Scenario 1 strength becomes Scenario 2 weakness

### Tier 3: Probing Strategist ⭐
- **Strengths**: Systematic probing (rounds 2-5), tool verification, adaptive pricing
- **Weaknesses**: More complex, slower initial rounds
- **Expected**: 78% extraction, 68% premium capture, 82 composite score
- **Key Insight**: Information extraction drives superior outcomes

---

## 📅 Implementation Roadmap

### Week 1: Core Infrastructure
- Day 1-2: Asymmetry type classes (`HiddenUrgency`, `HiddenBudget`, etc.)
- Day 3-4: Information extraction tracking
- Day 5: Scenario configuration

### Week 2: Scenario Implementation
- Day 1-2: `InformationAsymmetryScenario` class
- Day 3-4: Metrics calculation
- Day 5: Integration with [`market_tasks.py`](backend/market_tasks.py)

### Week 3: Testing & Validation
- Day 1-2: TDD tests (6 core tests)
- Day 3-4: Statistical testing framework
- Day 5: Full N=30 test run

### Week 4: Analysis & Reporting
- Day 1-2: Results analysis
- Day 3-4: Documentation
- Day 5: Presentation

---

## 🔄 Comparison with Scenario 1

| Aspect | Scenario 1 (Adversarial) | Scenario 2 (Asymmetry) |
|--------|-------------------------|------------------------|
| **Focus** | Resistance to manipulation | Information extraction |
| **Buyer Behavior** | Aggressive tactics | Hidden information |
| **Expected Winner** | Tier 2 (Math Geek) ✅ | Tier 3 (Probing) 🎯 |
| **Key Metric** | Anchor resistance | Extraction rate |
| **Tier 2 Advantage** | Boulware immunity | None (blind) |
| **Tier 3 Advantage** | Moderate | Strong (probing) |
| **Differentiation** | 13-16 points | 20-30 points |

### Complementary Insights

**Scenario 1**: Boulware Strategy is highly effective against adversarial tactics  
**Scenario 2**: Boulware's rigidity becomes a weakness when information extraction is valuable

**Combined Insight**: Optimal seller strategy depends on scenario type:
- **Adversarial buyers** → Tier 2 (Boulware)
- **Information asymmetry** → Tier 3 (Probing)
- **Unknown scenario** → Tier 3 (more adaptive)

---

## 🚀 Handoff to Architect Mode

### What's Complete ✅

1. ✅ **Comprehensive specification** (879 lines + appendix)
2. ✅ **Four asymmetry types** fully defined with dataclasses
3. ✅ **Metrics framework** (4 primary + 5 secondary metrics)
4. ✅ **Expected tier behaviors** with predictions
5. ✅ **Test configuration** (N=30, statistical rigor)
6. ✅ **TDD anchors** (6 core tests specified)
7. ✅ **Integration points** identified
8. ✅ **Success criteria** defined
9. ✅ **Implementation roadmap** (4-week plan)
10. ✅ **Risk mitigation** strategies

### What Architect Mode Should Design

1. **System Architecture**
   - Class hierarchy and relationships
   - Data flow diagrams
   - State management approach
   - Event processing pipeline

2. **Module Interfaces**
   - `InformationAsymmetryScenario` API
   - Asymmetry type interfaces
   - Discovery tracking interfaces
   - Metrics calculation interfaces

3. **Integration Strategy**
   - How to inject asymmetries into [`market_tasks.py`](backend/market_tasks.py)
   - How to detect seller probing
   - How to generate buyer responses
   - How to track discoveries

4. **Data Structures**
   - Buyer state with asymmetries
   - Discovery tracking structure
   - Metrics collection structure
   - Result aggregation structure

5. **Testing Strategy**
   - Unit test organization
   - Integration test approach
   - Statistical test framework
   - Validation checkpoints

### Key Design Decisions Needed

1. **Asymmetry Injection**: How to modify buyer state without breaking existing code?
2. **Probing Detection**: Keyword matching vs LLM classification?
3. **Discovery Tracking**: Per-buyer vs global tracking?
4. **Metrics Aggregation**: Real-time vs post-processing?
5. **Statistical Analysis**: Reuse Scenario 1 framework or extend?

### Critical Path Items

1. **Week 1, Day 1**: Asymmetry type classes must be complete for rest of implementation
2. **Week 2, Day 5**: Integration with [`market_tasks.py`](backend/market_tasks.py) is critical path
3. **Week 3, Day 5**: N=30 test run validates entire implementation
4. **Week 4, Day 5**: Results presentation is final deliverable

---

## 📚 Reference Documents

1. **Main Specification**: [`SCENARIO_2_INFORMATION_ASYMMETRY_SPEC.md`](SCENARIO_2_INFORMATION_ASYMMETRY_SPEC.md)
2. **Appendix**: [`SCENARIO_2_APPENDIX.md`](SCENARIO_2_APPENDIX.md)
3. **Scenario 1 Results**: [`STRESS_TEST_FINAL_ANALYSIS.md`](STRESS_TEST_FINAL_ANALYSIS.md)
4. **Boulware Implementation**: [`BOULWARE_IMPLEMENTATION_RESULTS.md`](BOULWARE_IMPLEMENTATION_RESULTS.md)
5. **Statistical Methods**: [`STATISTICAL_ANALYSIS_REPORT.md`](STATISTICAL_ANALYSIS_REPORT.md)
6. **Base Scenarios**: [`docs/STRESS_TEST_SCENARIOS.md`](docs/STRESS_TEST_SCENARIOS.md)

---

## 🎓 Key Learnings from Scenario 1

### What Worked Well

✅ **N=30 sample size** provided statistical rigor  
✅ **Boulware Strategy** (β=2.0) eliminated anchoring vulnerability  
✅ **Multi-dimensional metrics** revealed nuanced performance  
✅ **Statistical analysis** (t-tests, Cohen's d) validated findings  
✅ **Composite scoring** balanced multiple objectives

### What to Replicate

✅ Use same statistical framework  
✅ Use same sample size (N=30)  
✅ Use same metrics infrastructure  
✅ Use same composite scoring approach  
✅ Use same documentation standards

### What to Improve

🔄 **Add information extraction metrics** (new for Scenario 2)  
🔄 **Test adaptive strategies** (Tier 3 should excel here)  
🔄 **Measure discovery timing** (when info is extracted)  
🔄 **Track exploitation effectiveness** (how info is used)

---

## 🎯 Success Definition

**Scenario 2 is successful if:**

1. **Tier 3 outperforms Tier 2** by >15 points (reverses Scenario 1 result)
2. **Information extraction differentiates tiers** (Tier 3 >> Tier 2 >> Tier 1)
3. **Premium capture correlates with extraction** (discovered info → higher prices)
4. **Statistical significance achieved** (p < 0.05, d > 0.8)
5. **Insights complement Scenario 1** (different scenarios favor different strategies)

**Ultimate Goal**: Demonstrate that **optimal seller strategy depends on buyer behavior type**, validating the need for adaptive multi-tier systems.

---

## 📞 Next Steps

### For Architect Mode:

1. Review this executive summary and main specification
2. Design system architecture for information asymmetry scenario
3. Create detailed class diagrams and data flow diagrams
4. Specify module interfaces and integration points
5. Design testing strategy and validation approach
6. Hand off to Code mode for implementation

### For Code Mode (After Architecture):

1. Implement asymmetry type classes
2. Implement `InformationAsymmetryScenario`
3. Integrate with [`market_tasks.py`](backend/market_tasks.py)
4. Write TDD tests
5. Run N=30 statistical validation
6. Document results

---

## ✅ Specification Complete

**Status**: Ready for handoff to Architect Mode

**Confidence Level**: High (based on Scenario 1 success)

**Estimated Implementation Time**: 4 weeks

**Expected Outcome**: Tier 3 (Probing Strategist) outperforms Tier 2 (Math Geek) by 20-30 points, demonstrating the value of information extraction in asymmetric scenarios.

---

**Prepared by**: Specification Writer Mode (SPARC)  
**Date**: 2026-02-24  
**Next Mode**: 🏗️ Architect Mode

---

**End of Executive Summary**
