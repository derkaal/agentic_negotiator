# Scenario 2 Diagnostic Report: Information Asymmetry Testing

**Date**: 2026-02-24  
**Test Type**: Integration Testing with N=30 iterations  
**Status**: ⚠️ IMPLEMENTATION GAP IDENTIFIED

---

## Executive Summary

Scenario 2 (Information Asymmetry) testing revealed a critical implementation gap: while all infrastructure components are correctly implemented and unit tests pass, the scenario is not properly integrated with the actual market simulation system, resulting in zero metrics across all tiers.

---

## Test Results

### Unit Tests: ✅ PASS (17/17)

All unit tests passed successfully:
- ✅ Asymmetry type creation and behavior
- ✅ Probe detection (urgency, budget, alternatives, quality)
- ✅ Information extraction tracking
- ✅ Discovery recording
- ✅ Metrics calculation
- ✅ Tier performance differentiation

**Fix Applied**: Regex pattern for alternatives detection updated to handle plural forms (`offers?` instead of `offer`).

### Integration Test: ⚠️ RUNS BUT NO DATA

**Test Configuration**:
- Iterations: N=30
- Tiers: 3 (Solo LLM, Math Geek, Probing)
- Max Rounds: 10
- Market Average: $100

**Results**:
```
Tier 1 (Solo LLM):   0.00% ± 0.00 (extraction: 0.0%)
Tier 2 (Math Geek):  0.00% ± 0.00 (extraction: 0.0%)
Tier 3 (Probing):    0.00% ± 0.00 (extraction: 0.0%)
```

**Statistical Analysis**: Unable to compute (all values zero, resulting in NaN for t-tests and Cohen's d)

---

## Root Cause Analysis

### Problem Identification

The [`InformationAsymmetryScenario`](backend/stress_scenarios/scenarios/information_asymmetry.py) class:

1. **Correctly implements** all abstract methods from [`BaseScenario`](backend/stress_scenarios/base.py:262)
2. **Correctly initializes** asymmetry types, information extractors, and metrics collectors
3. **Correctly calls** [`run_market_3x3()`](backend/stress_scenarios/scenarios/information_asymmetry.py:293) to run the market simulation

### The Gap

The scenario processes market events but **does not receive actual negotiation data** from the market simulation. Specifically:

#### Issue 1: Event Processing Disconnect
```python
# information_asymmetry.py:293-297
async for event in run_market_3x3(
    scenario="used_car",
    max_rounds=self.config.max_rounds
):
    await self._process_market_event(event)
```

The `run_market_3x3()` function returns events, but these events don't contain:
- Actual seller messages (needed for probe detection)
- Actual buyer responses (needed for information extraction)
- Actual deal data with seller/buyer IDs (needed for tier attribution)

#### Issue 2: Simulated vs. Real Data
```python
# information_asymmetry.py:361-389
def _simulate_seller_message(self, round_num: int) -> str:
    """Simulate seller message for testing."""
    # This generates fake messages instead of using real ones
    probe_messages = [
        "What's your timeline for this purchase?",
        ...
    ]
    return random.choice(probe_messages)
```

The scenario uses **simulated** seller messages instead of extracting real messages from the negotiation.

#### Issue 3: Missing Tier Attribution
```python
# information_asymmetry.py:391-428
def _process_deal(self, event: Dict[str, Any]):
    """Process a closed deal."""
    deal = {
        "buyer": event.get("buyer"),      # Returns None
        "seller": event.get("seller"),    # Returns None
        "price": event.get("price"),      # Returns None
        "round": event.get("round")
    }
```

The deal events don't contain the necessary seller/buyer identification to attribute performance to specific tiers.

---

## What Works

### ✅ Infrastructure Layer
- [`BaseScenario`](backend/stress_scenarios/base.py) abstract class
- [`ScenarioRunner`](backend/stress_scenarios/runner.py) execution engine
- [`ConfigLoader`](backend/stress_scenarios/config_loader.py) YAML configuration
- [`MetricsCollector`](backend/stress_scenarios/metrics.py) data aggregation
- [`StatisticalAnalysis`](backend/stress_scenarios/statistical_analysis.py) t-tests, Cohen's d, reporting

### ✅ Scenario 2 Components
- [`AsymmetryType`](backend/stress_scenarios/utils/asymmetry_types.py) classes (Urgency, Budget, Alternatives, Quality)
- [`ProbeDetector`](backend/stress_scenarios/utils/information_extraction.py:25) regex-based question detection
- [`InformationExtractor`](backend/stress_scenarios/utils/information_extraction.py:220) discovery tracking
- [`AsymmetryMetricsCollector`](backend/stress_scenarios/scenarios/information_asymmetry.py:35) aggregation

### ✅ Test Infrastructure
- [`test_information_asymmetry.py`](backend/stress_scenarios/tests/test_information_asymmetry.py) - 17 unit tests
- [`test_scenario2_runner.py`](backend/test_scenario2_runner.py) - N=30 integration test
- Statistical analysis with confidence intervals

---

## What Needs Implementation

### 1. Market Event Schema Enhancement

**File**: [`market_tasks.py`](backend/market_tasks.py)

The `run_market_3x3()` function needs to emit events with:
```python
{
    "type": "negotiation_message",
    "round": int,
    "seller_id": str,  # e.g., "tier_3_probing"
    "buyer_id": str,   # e.g., "buyer_1"
    "message": str,    # Actual seller message
    "response": str    # Actual buyer response
}

{
    "type": "deal_closed",
    "seller_id": str,  # With tier information
    "buyer_id": str,
    "price": float,
    "round": int
}
```

### 2. Message Extraction Integration

**File**: [`information_asymmetry.py`](backend/stress_scenarios/scenarios/information_asymmetry.py:329)

Replace `_simulate_seller_message()` with real message extraction:
```python
async def _process_round(self, round_num: int, event: Dict[str, Any]):
    # Extract real messages from event
    messages = event.get("messages", [])
    
    for msg in messages:
        seller_message = msg.get("message", "")
        buyer_id = msg.get("buyer_id")
        
        # Process real message
        discovery = self.information_extractor.process_message(
            seller_message,
            self._buyer_asymmetries.get(buyer_id, {}),
            round_num
        )
```

### 3. Tier-Specific Behavior Injection

**File**: [`market_tasks.py`](backend/market_tasks.py) or new `tier_behaviors.py`

Implement tier-specific seller behaviors:
- **Tier 1 (Solo LLM)**: Standard negotiation, minimal probing
- **Tier 2 (Math Geek)**: Formula-driven, no strategic probing
- **Tier 3 (Probing)**: Strategic question asking, information extraction focus

### 4. Asymmetry-Aware Buyer Responses

**File**: New `asymmetric_buyer.py` or enhancement to existing buyer logic

Buyers need to:
- Track their hidden asymmetries
- Respond to probes based on `disclosure_probability`
- Reveal information when asked the right questions
- Adjust their behavior based on revealed information

---

## Comparison with Scenario 1

### Scenario 1 (Adversarial Buyer): ✅ WORKING

**Why it works**:
- Simpler integration point (buyer behavior modification)
- Uses existing market simulation without message-level tracking
- Metrics calculated from final deal outcomes only
- No need for mid-negotiation event processing

**Results**:
```
Tier 2 (Math Geek):  92.69% ± 0.12 🥇
Tier 3 (Probing):    79.46% ± 0.00 🥈
Tier 1 (Solo LLM):   76.33% ± 3.65 🥉
```

### Scenario 2 (Information Asymmetry): ⚠️ NEEDS INTEGRATION

**Why it doesn't work yet**:
- Requires message-level event tracking
- Needs real-time probe detection during negotiation
- Requires tier-specific behavior injection
- Depends on buyer asymmetry awareness

**Current State**: Infrastructure complete, integration pending

---

## Recommendations

### Immediate Actions

1. **Document the Gap**: ✅ DONE (this report)
2. **Preserve Unit Tests**: ✅ All tests passing and valuable
3. **Keep Infrastructure**: ✅ Well-designed, reusable components

### Future Implementation (Estimated 8-12 hours)

#### Phase 1: Event Schema (2-3 hours)
- Enhance `run_market_3x3()` to emit detailed negotiation events
- Add seller_id and buyer_id to all events
- Include message content in round events

#### Phase 2: Message Integration (3-4 hours)
- Replace simulated messages with real message extraction
- Integrate `ProbeDetector` with actual seller messages
- Connect `InformationExtractor` to real buyer responses

#### Phase 3: Behavior Injection (2-3 hours)
- Implement tier-specific seller behaviors
- Add probing strategies to Tier 3
- Ensure Tier 2 remains formula-focused

#### Phase 4: Buyer Asymmetries (2-3 hours)
- Integrate asymmetry types with buyer logic
- Implement disclosure probability mechanics
- Add information revelation tracking

#### Phase 5: Testing & Validation (1-2 hours)
- Run N=30 integration test
- Verify tier differentiation
- Validate hypothesis (Tier 3 > Tier 2 in info asymmetry)

---

## Technical Debt Assessment

### Low Risk (Keep As-Is)
- ✅ Unit test suite
- ✅ Statistical analysis framework
- ✅ Configuration system
- ✅ Metrics collection infrastructure

### Medium Risk (Needs Attention)
- ⚠️ Event schema documentation
- ⚠️ Integration patterns between scenarios and market simulation
- ⚠️ Tier behavior specification

### High Risk (Blocks Progress)
- 🔴 Message-level event tracking (required for Scenario 2)
- 🔴 Tier-specific behavior injection (required for differentiation)
- 🔴 Asymmetry-aware buyer logic (required for information extraction)

---

## Conclusion

**Scenario 2 Status**: Infrastructure ✅ Complete | Integration ⚠️ Pending

The Information Asymmetry scenario has a **solid foundation** with:
- Well-designed asymmetry types
- Robust probe detection
- Comprehensive metrics collection
- Statistical analysis framework

However, it requires **deeper integration** with the market simulation system to:
- Track actual negotiation messages
- Inject tier-specific behaviors
- Implement asymmetry-aware buyer responses

**Recommendation**: Proceed with Scenario 1 analysis (which is fully functional) while planning Scenario 2 integration as a future enhancement.

---

## Files Modified

### Bug Fixes
- [`information_extraction.py`](backend/stress_scenarios/utils/information_extraction.py:53): Fixed regex for plural "offers"
- [`information_asymmetry.py`](backend/stress_scenarios/scenarios/information_asymmetry.py:499): Added `calculate_scenario_metrics()` method
- [`information_asymmetry.py`](backend/stress_scenarios/scenarios/information_asymmetry.py:430): Added null check in `_extract_tier()`

### New Files
- [`test_scenario2_runner.py`](backend/test_scenario2_runner.py): N=30 integration test runner

### Test Results
- Unit Tests: 17/17 passing ✅
- Integration Test: Runs successfully, returns zero metrics ⚠️

---

**Next Steps**: Generate comprehensive analysis report for Scenario 1 (which has real data) and document the integration requirements for Scenario 2.
