"""
Integration test for stress test scenarios with statistical analysis.

Tests the complete flow:
1. Load configuration
2. Register scenario
3. Run scenario 30 times (N=30 per tier)
4. Collect metrics
5. Perform statistical analysis
6. Generate report
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
from stress_scenarios.statistical_analysis import (
    generate_statistical_report
)


async def test_adversarial_buyer_scenario():
    """Test Scenario 1: Adversarial Buyer with Statistical Analysis."""
    print("=" * 70)
    print("STRESS TEST: Adversarial Buyer Scenario (N=30)")
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
        num_iterations = getattr(config, 'num_iterations', 30)
        print(f"   Iterations: {num_iterations}")
        print()
    except FileNotFoundError as e:
        print(f"   ERROR: {e}")
        print("   Make sure adversarial_buyer.yaml exists in configs/")
        return False
    
    # Collect results from multiple iterations
    print(f"3. Running {num_iterations} iterations...")
    print("   (This will take several minutes)")
    print()
    
    tier1_scores = []
    tier2_scores = []
    tier3_scores = []
    
    try:
        for i in range(num_iterations):
            result = await runner.run_scenario("adversarial_buyer", config)
            
            # Extract composite scores
            t1_score = result.tier_performance.get(1, {}).get(
                "composite_score", 0
            )
            t2_score = result.tier_performance.get(2, {}).get(
                "composite_score", 0
            )
            t3_score = result.tier_performance.get(3, {}).get(
                "composite_score", 0
            )
            
            tier1_scores.append(t1_score)
            tier2_scores.append(t2_score)
            tier3_scores.append(t3_score)
            
            print(f"   Iteration {i+1}/{num_iterations}: "
                  f"T1={t1_score:.2f}%, T2={t2_score:.2f}%, "
                  f"T3={t3_score:.2f}%")
        
        print()
        print("4. All iterations completed!")
        print()
        
        # Generate statistical report
        print("5. Generating statistical analysis...")
        report = generate_statistical_report(
            tier1_scores,
            tier2_scores,
            tier3_scores
        )
        
        print(report)
        
        # Save report to file
        report_path = Path(__file__).parent.parent / \
            "STATISTICAL_ANALYSIS_REPORT.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        print()
        print(f"6. Report saved to: {report_path}")
        print()
        
        # Quick summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Tier 1 (Solo LLM):        Mean = {sum(tier1_scores)/len(tier1_scores):.2f}%")
        print(f"Tier 2 (Math Geek):       Mean = {sum(tier2_scores)/len(tier2_scores):.2f}%")
        print(f"Tier 3 (Probing):         Mean = {sum(tier3_scores)/len(tier3_scores):.2f}%")
        print()
        
        # Determine best performer
        means = {
            "Tier 1 (Solo LLM)": sum(tier1_scores)/len(tier1_scores),
            "Tier 2 (Math Geek)": sum(tier2_scores)/len(tier2_scores),
            "Tier 3 (Probing)": sum(tier3_scores)/len(tier3_scores),
        }
        best = max(means, key=means.get)
        print(f"Best Performer: {best} ({means[best]:.2f}%)")
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
    """Run integration tests with statistical analysis."""
    success = await test_adversarial_buyer_scenario()
    
    if success:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
