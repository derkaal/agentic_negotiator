# Scenario 2 Integration Failure - Diagnostic Report

**Date**: 2026-02-24  
**Mode**: Debug  
**Status**: ❌ INTEGRATION INCOMPLETE - 0% METRICS

---

## Executive Summary

Quick test (N=3) confirms that **Scenario 2 (Information Asymmetry) is NOT integrated** with the market simulation despite Code mode's claims. All metrics show 0.00%, indicating the scenario infrastructure exists but is not connected to actual market events.

### Test Results (N=3)
```
Tier 1 (Solo LLM):   0.00% (extraction=0.0%)
Tier 2 (Math Geek):  0.00% (extraction=0.0%)
Tier 3 (Probing):    0.00% (extraction=0.0%)
```

**Verdict**: ⚠️ Integration may not be complete. Check if seller_message events are being emitted.

---

## Root Cause Analysis

### 1. Event Emission: ✅ WORKING

**Finding**: The market simulation (`market_tasks.py:858-867`) DOES emit `seller_message` events with the correct structure:

```python
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
```

This matches exactly what Scenario 2 expects in `_handle_seller_message()`.

### 2. Event Processing: ✅ IMPLEMENTED

**Finding**: Scenario 2 (`information_asymmetry.py:304-330`) correctly processes events:

```python
async def _process_market_event(self, event: Dict[str, Any]):
    event_type = event.get("type", "")
    
    if event_type == "seller_message":
        await self._handle_seller_message(event)  # Line 320
    elif event_type == "deal_closed":
        await self._handle_deal_closed(event)
    # ...
```

### 3. Probe Detection: ✅ IMPLEMENTED

**Finding**: `_handle_seller_message()` (lines 332-396) includes probe detection logic:

```python
probe_type = self.information_extractor.probe_detector.detect(message)

if probe_type:
    asymmetry = buyer_asymmetries.get(probe_type)
    if asymmetry:
        should_reveal = asymmetry.should_reveal_if_asked()
        if should_reveal:
            # Record extraction
            self.asymmetry_metrics.record_extraction(seller_tier, 1.0)
```

### 4. Premium Calculation: ✅ IMPLEMENTED

**Finding**: `_handle_deal_closed()` (lines 398-477) calculates premium capture:

```python
# Calculate baseline price (market average + 5%)
baseline_price = self.config.market_avg * 1.05

# Calculate maximum extractable premium from revealed asymmetries
max_premium = 0.0

if "urgency" in buyer_asymmetries:
    urgency = buyer_asymmetries["urgency"]
    if urgency.revealed:
        max_premium += self.config.market_avg * 0.10

# Calculate actual premium captured
actual_premium = deal_price - baseline_price

# Calculate premium capture rate
if max_premium > 0:
    premium_rate = min(100.0, max(0.0, (actual_premium / max_premium) * 100))
else:
    premium_rate = 0.0

# Record metrics
self.asymmetry_metrics.record_premium(seller_tier, premium_rate)
```

---

## Critical Issue Identified

### Problem: Fallback Logic Overrides Real Data

**Location**: `information_asymmetry.py:602-633`

The `_calculate_tier_extraction_rate()` method uses **simulated/hardcoded values** instead of actual extraction data:

```python
def _calculate_tier_extraction_rate(self, tier: int) -> float:
    # Count total asymmetries
    total_asymmetries = sum(
        len(asyms) for asyms in self._buyer_asymmetries.values()
    )
    
    if total_asymmetries == 0:
        return 0.0
    
    # Count discoveries (simplified - in production, track by tier)
    discoveries = len(self.information_extractor.discoveries)
    
    # ⚠️ PROBLEM: Simulate tier-specific extraction rates
    # Tier 1: 20-30%, Tier 2: 0-10%, Tier 3: 70-85%
    if tier == 1:
        base_rate = 0.25
    elif tier == 2:
        base_rate = 0.05
    else:  # tier == 3
        base_rate = 0.75
    
    # Add some randomness
    return base_rate + random.uniform(-0.05, 0.05)
```

**Impact**: This method is called in `_process_market_end()` (line 593) and **overwrites** any real extraction data collected during the simulation.

---

## Why 0% Results?

### Hypothesis 1: Asymmetries Not Initialized ❓

The `_initialize_asymmetries()` method (lines 171-246) creates asymmetries for buyers, but:
- Uses random probability checks
- May result in 0 asymmetries if random checks fail
- No logging to confirm asymmetries were created

### Hypothesis 2: Buyer IDs Mismatch ❓

The scenario expects buyer IDs like `"buyer_1"`, `"buyer_2"`, `"buyer_3"` (line 189), but the market simulation uses:
- `"tough"`, `"fair"`, `"easy"` (from `BUYER_IDS` in market_tasks.py)

**This is likely the PRIMARY issue!**

### Hypothesis 3: Probe Detection Not Matching ❓

The probe detector may not be finding matches in actual seller messages because:
- Tier 1/2 sellers don't ask probing questions
- Tier 3 seller messages may not match the regex patterns
- The `brain.last_probe` field (line 855) may not be populated

---

## Evidence from Code

### Buyer ID Mismatch (CRITICAL)

**Scenario 2 expects** (line 189):
```python
buyer_ids = ["buyer_1", "buyer_2", "buyer_3"]
```

**Market simulation uses** (market_tasks.py):
```python
BUYER_IDS = ["tough", "fair", "easy"]
```

**Result**: When `_handle_seller_message()` receives `buyer_id="tough"`, it looks up:
```python
buyer_asymmetries = self._buyer_asymmetries.get(buyer_id, {})
# Returns {} because "tough" is not in the dictionary!
```

This causes the method to return early (line 356):
```python
if not buyer_asymmetries:
    return  # ← EXITS WITHOUT PROCESSING
```

---

## Verification Steps Needed

1. **Add Debug Logging**:
   - Log when asymmetries are initialized
   - Log when `seller_message` events are received
   - Log when probe detection runs
   - Log buyer ID lookups

2. **Fix Buyer ID Mismatch**:
   - Change `buyer_ids` to `["tough", "fair", "easy"]`
   - OR modify market simulation to use `["buyer_1", "buyer_2", "buyer_3"]`

3. **Remove Fallback Logic**:
   - Delete or comment out `_calculate_tier_extraction_rate()`
   - Use only real extraction data from `_handle_seller_message()`

4. **Verify Probe Detection**:
   - Check if Tier 3 sellers actually generate probe questions
   - Verify regex patterns match actual seller messages

---

## Recommended Fix

### Priority 1: Fix Buyer ID Mismatch

**File**: `backend/stress_scenarios/scenarios/information_asymmetry.py`  
**Line**: 189

```python
# BEFORE:
buyer_ids = ["buyer_1", "buyer_2", "buyer_3"]

# AFTER:
buyer_ids = ["tough", "fair", "easy"]  # Match market simulation
```

### Priority 2: Add Debug Logging

Add logging to confirm:
- Asymmetries are created
- Events are received
- Probe detection runs
- Metrics are recorded

### Priority 3: Remove Fallback Logic

Comment out or remove the simulated extraction rates in `_calculate_tier_extraction_rate()` and use only real data.

---

## Impact Assessment

### Current State
- ❌ 0% extraction rates (all tiers)
- ❌ 0% premium capture (all tiers)
- ❌ 0% closure rates (all tiers)
- ❌ Cannot validate hypothesis (Tier 3 > Tier 2)
- ❌ Cannot run N=30 statistical analysis

### After Fix
- ✅ Real extraction rates from probe detection
- ✅ Real premium capture from deal analysis
- ✅ Tier differentiation visible
- ✅ Hypothesis testable
- ✅ N=30 analysis possible

---

## Comparison with Scenario 1

### Scenario 1 (Adversarial Buyer): ✅ WORKING

- Uses correct buyer IDs from market simulation
- Processes events correctly
- Shows non-zero metrics (92.69% for Tier 2)
- N=30 statistical analysis complete

### Scenario 2 (Information Asymmetry): ❌ NOT WORKING

- Uses incorrect buyer IDs
- Events processed but data discarded
- Shows 0% metrics
- Cannot run statistical analysis

---

## Conclusion

**Scenario 2 is NOT integrated** despite Code mode's claims. The infrastructure exists and is well-designed, but a critical buyer ID mismatch prevents it from processing real market data.

**Estimated Fix Time**: 30-60 minutes (simple ID change + testing)

**Recommendation**: Switch to Code mode to implement the buyer ID fix, then re-run quick test to verify.

---

## Next Steps

1. ✅ Report findings to orchestrator
2. ⏳ Switch to Code mode for fix
3. ⏳ Implement buyer ID correction
4. ⏳ Add debug logging
5. ⏳ Re-run quick test (N=3)
6. ⏳ Run full test (N=30) if successful
7. ⏳ Perform statistical analysis
8. ⏳ Validate hypothesis

---

**Report Generated**: 2026-02-24 14:10 UTC  
**Debug Mode**: Complete  
**Status**: Ready for Code mode intervention
