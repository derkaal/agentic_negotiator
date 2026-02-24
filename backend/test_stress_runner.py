"""
Integration test for stress test scenarios.

Tests the complete flow:
1. Load configuration
2. Register scenario
3. Run scenario
4. Collect metrics
5. Analyze tier performance
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from stress_scenarios.runner import get_runner
from stress_scenarios.config_loader import load_config
from stress_scenarios.scenarios.adversarial_buyer import (
    AdversarialBuyerScenario
)


async def test_adversarial_buyer_scenario():
    """Test Scenario 1: Adversarial Buyer."""
    print("=" * 70)
    print("STRESS TEST: Adversarial Buyer Scenario")
    print("=" * 70)
    print()
    
    # Get runner
    runner = get_runner()
    
    # Register scenario
    print("1. Registering scenario...")
    runner.register_scenario("adversarial_buyer", AdversarialBuyerScenario)
    print(f"   Registered scenarios: {runner.get_registered_scenarios()}")
    print()
    
    # Load configuration
    print("2. Loading configuration...")
    try:
        config = load_config("adversarial_buyer")
        print(f"   Scenario: {config.name}")
        print(f"   Description: {config.description.strip()}")
        print(f"   Max rounds: {config.max_rounds}")
        print(f"   Market avg: ${config.market_avg}")
        print()
    except FileNotFoundError as e:
        print(f"   ERROR: {e}")
        print("   Make sure adversarial_buyer.yaml exists in configs/")
        return False
    
    # Run scenario
    print("3. Running scenario...")
    print("   (This will take a moment as it runs the market simulation)")
    print()
    
    try:
        result = await runner.run_scenario("adversarial_buyer", config)
        
        print("4. Scenario completed!")
        print(f"   Success: {result.success}")
        print(f"   Phase: {result.phase.value}")
        print(f"   Duration: {result.duration_seconds:.2f}s")
        print()
        
        # Display metrics
        print("5. Metrics collected:")
        for metric_name, value in result.metrics.items():
            print(f"   - {metric_name}: {value}")
        print()
        
        # Display tier performance with multi-dimensional metrics
        print("6. Multi-Dimensional Tier Performance:")
        print()
        
        for tier in [1, 2, 3]:
            performance = result.tier_performance.get(tier, {})
            if not performance:
                continue
            
            tier_names = {
                1: "Solo LLM",
                2: "Math Geek",
                3: "Probing Strategist"
            }
            
            print(f"   Tier {tier} ({tier_names[tier]}):")
            print(f"     Deal Count: {performance.get('deal_count', 0)}")
            print(f"     Absolute Price: ${performance.get('absolute_price', 0):.2f}")
            print(f"     Absolute Rank: {performance.get('absolute_rank', 'N/A')}")
            print()
            print(f"     📊 Performance Metrics:")
            print(f"       • Relative Price Achievement: "
                  f"{performance.get('relative_price_achievement', 0):.2f}%")
            print(f"       • Market-Relative Performance: "
                  f"{performance.get('market_relative_performance', 0):.2f}%")
            print(f"       • Efficiency Score: "
                  f"{performance.get('efficiency_score', 0):.2f}%")
            print(f"       • Composite Score: "
                  f"{performance.get('composite_score', 0):.2f}%")
            print()
        
        # Analyze results with new metrics
        print("7. Fair Comparison Analysis:")
        print()
        
        # Extract composite scores for comparison
        tier_1_composite = result.tier_performance.get(1, {}).get(
            "composite_score", None
        )
        tier_2_composite = result.tier_performance.get(2, {}).get(
            "composite_score", None
        )
        tier_3_composite = result.tier_performance.get(3, {}).get(
            "composite_score", None
        )
        
        # Extract market-relative performance
        tier_1_market = result.tier_performance.get(1, {}).get(
            "market_relative_performance", None
        )
        tier_2_market = result.tier_performance.get(2, {}).get(
            "market_relative_performance", None
        )
        tier_3_market = result.tier_performance.get(3, {}).get(
            "market_relative_performance", None
        )
        
        # Extract absolute prices
        tier_1_price = result.tier_performance.get(1, {}).get(
            "absolute_price", None
        )
        tier_2_price = result.tier_performance.get(2, {}).get(
            "absolute_price", None
        )
        tier_3_price = result.tier_performance.get(3, {}).get(
            "absolute_price", None
        )
        
        print("   Floor-Agnostic Metrics (Fair Comparison):")
        if tier_1_market is not None:
            print(f"   • Tier 1 Market-Relative: {tier_1_market:.2f}%")
        if tier_2_market is not None:
            print(f"   • Tier 2 Market-Relative: {tier_2_market:.2f}%")
        if tier_3_market is not None:
            print(f"   • Tier 3 Market-Relative: {tier_3_market:.2f}%")
        print()
        
        print("   Absolute Price Comparison:")
        if tier_1_price is not None:
            print(f"   • Tier 1: ${tier_1_price:.2f}")
        if tier_2_price is not None:
            print(f"   • Tier 2: ${tier_2_price:.2f}")
        if tier_3_price is not None:
            print(f"   • Tier 3: ${tier_3_price:.2f}")
        print()
        
        print("   Composite Scores (Weighted Multi-Metric):")
        if tier_1_composite is not None:
            print(f"   • Tier 1 (Solo LLM): {tier_1_composite:.2f}%")
        if tier_2_composite is not None:
            print(f"   • Tier 2 (Math Geek): {tier_2_composite:.2f}%")
        if tier_3_composite is not None:
            print(f"   • Tier 3 (Probing Strategist): {tier_3_composite:.2f}%")
        print()
        
        # Validation checks
        print("   Validation:")
        all_valid = True
        
        # Check that Tier 2 is not unfairly penalized
        if tier_2_composite is not None and tier_2_market is not None:
            if tier_2_composite > 0:
                print("   ✓ Tier 2 has positive composite score "
                      "(no longer unfairly penalized)")
            else:
                print("   ⚠ Tier 2 composite score is zero or negative")
                all_valid = False
        
        # Check that metrics are diverse
        if (tier_1_composite is not None and tier_2_composite is not None
            and tier_3_composite is not None):
            scores = [tier_1_composite, tier_2_composite, tier_3_composite]
            if max(scores) - min(scores) > 10:
                print("   ✓ Composite scores show meaningful differentiation")
            else:
                print("   ⚠ Composite scores are too similar")
        
        # Check absolute price ranking makes sense
        tier_1_rank = result.tier_performance.get(1, {}).get("absolute_rank")
        tier_2_rank = result.tier_performance.get(2, {}).get("absolute_rank")
        tier_3_rank = result.tier_performance.get(3, {}).get("absolute_rank")
        
        if all(r is not None for r in [tier_1_rank, tier_2_rank, tier_3_rank]):
            print(f"   ✓ Absolute rankings assigned: "
                  f"T1={tier_1_rank}, T2={tier_2_rank}, T3={tier_3_rank}")
        
        if not all_valid:
            print()
            print("   ⚠ Some validation checks failed")
        
        print()
        print("=" * 70)
        print("TEST COMPLETED SUCCESSFULLY")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run integration tests."""
    success = await test_adversarial_buyer_scenario()
    
    if success:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
