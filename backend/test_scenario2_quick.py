"""
Quick integration test for Scenario 2 (3 iterations only).
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from stress_scenarios.runner import get_runner
from stress_scenarios.config_loader import load_config
from stress_scenarios.scenarios.information_asymmetry import (
    InformationAsymmetryScenario
)


async def main():
    print("\n" + "=" * 70)
    print("SCENARIO 2 QUICK INTEGRATION TEST (N=3)")
    print("=" * 70)
    print()
    
    # Get runner
    runner = get_runner()
    
    # Register scenario
    print("1. Registering scenario...")
    runner.register_scenario("information_asymmetry",
                            InformationAsymmetryScenario)
    print(f"   Registered: {runner.get_registered_scenarios()}")
    print()
    
    # Load configuration
    print("2. Loading configuration...")
    try:
        config = load_config("information_asymmetry")
        print(f"   Scenario: {config.name}")
        print(f"   Max rounds: {config.max_rounds}")
        print()
    except FileNotFoundError as e:
        print(f"   ERROR: {e}")
        return False
    
    # Run 3 iterations
    print("3. Running 3 iterations...")
    print()
    
    tier1_scores = []
    tier2_scores = []
    tier3_scores = []
    
    tier1_extraction = []
    tier2_extraction = []
    tier3_extraction = []
    
    try:
        for i in range(3):
            result = await runner.run_scenario("information_asymmetry", config)
            
            # Extract scores
            t1_score = result.tier_performance.get(1, {}).get("composite_score", 0)
            t2_score = result.tier_performance.get(2, {}).get("composite_score", 0)
            t3_score = result.tier_performance.get(3, {}).get("composite_score", 0)
            
            tier1_scores.append(t1_score)
            tier2_scores.append(t2_score)
            tier3_scores.append(t3_score)
            
            # Extract extraction rates
            t1_extract = result.tier_performance.get(1, {}).get("extraction_rate", 0)
            t2_extract = result.tier_performance.get(2, {}).get("extraction_rate", 0)
            t3_extract = result.tier_performance.get(3, {}).get("extraction_rate", 0)
            
            tier1_extraction.append(t1_extract)
            tier2_extraction.append(t2_extract)
            tier3_extraction.append(t3_extract)
            
            print(f"   Iteration {i+1}/3:")
            print(f"     T1: {t1_score:.2f}% (extraction={t1_extract:.1f}%)")
            print(f"     T2: {t2_score:.2f}% (extraction={t2_extract:.1f}%)")
            print(f"     T3: {t3_score:.2f}% (extraction={t3_extract:.1f}%)")
            print()
        
        print("=" * 70)
        print("QUICK TEST RESULTS")
        print("=" * 70)
        print()
        
        # Calculate averages
        avg_t1 = sum(tier1_scores) / len(tier1_scores)
        avg_t2 = sum(tier2_scores) / len(tier2_scores)
        avg_t3 = sum(tier3_scores) / len(tier3_scores)
        
        avg_t1_ext = sum(tier1_extraction) / len(tier1_extraction)
        avg_t2_ext = sum(tier2_extraction) / len(tier2_extraction)
        avg_t3_ext = sum(tier3_extraction) / len(tier3_extraction)
        
        print(f"Tier 1 (Solo LLM):   {avg_t1:.2f}% (extraction={avg_t1_ext:.1f}%)")
        print(f"Tier 2 (Math Geek):  {avg_t2:.2f}% (extraction={avg_t2_ext:.1f}%)")
        print(f"Tier 3 (Probing):    {avg_t3:.2f}% (extraction={avg_t3_ext:.1f}%)")
        print()
        
        # Check for non-zero metrics
        has_nonzero = any([
            avg_t1 > 0, avg_t2 > 0, avg_t3 > 0,
            avg_t1_ext > 0, avg_t2_ext > 0, avg_t3_ext > 0
        ])
        
        if has_nonzero:
            print("✅ Integration appears to be working (non-zero metrics detected)")
            print("   Ready to run full N=30 test")
        else:
            print("⚠️  All metrics are 0% - integration may not be complete")
            print("   Check if seller_message events are being emitted")
        
        print()
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(main())
