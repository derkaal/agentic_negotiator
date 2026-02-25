"""
Integration test runner for Scenario 2: Information Asymmetry.

Runs N=30 iterations and performs statistical analysis.
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
from stress_scenarios.statistical_analysis import (
    calculate_tier_statistics,
    compare_tiers,
    generate_statistical_report
)


async def test_information_asymmetry_scenario():
    """Test Scenario 2: Information Asymmetry with Statistical Analysis."""
    print("=" * 70)
    print("STRESS TEST: Information Asymmetry Scenario (N=30)")
    print("=" * 70)
    print()
    
    # Get runner
    runner = get_runner()
    
    # Register scenario
    print("1. Registering scenario...")
    runner.register_scenario("information_asymmetry",
                            InformationAsymmetryScenario)
    print(f"   Registered scenarios: {runner.get_registered_scenarios()}")
    print()
    
    # Load configuration
    print("2. Loading configuration...")
    try:
        config = load_config("information_asymmetry")
        print(f"   Scenario: {config.name}")
        print(f"   Description: {config.description.strip()}")
        print(f"   Max rounds: {config.max_rounds}")
        print(f"   Market avg: ${config.market_avg}")
        num_iterations = getattr(config, 'num_iterations', 30)
        print(f"   Iterations: {num_iterations}")
        print()
    except FileNotFoundError as e:
        print(f"   ERROR: {e}")
        print("   Make sure information_asymmetry.yaml exists in configs/")
        return False
    
    # Collect results from multiple iterations
    print(f"3. Running {num_iterations} iterations...")
    print("   (This will take several minutes)")
    print()
    
    tier1_scores = []
    tier2_scores = []
    tier3_scores = []
    
    tier1_extraction = []
    tier2_extraction = []
    tier3_extraction = []
    
    try:
        for i in range(num_iterations):
            result = await runner.run_scenario("information_asymmetry",
                                              config)
            
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
            
            # Extract extraction rates
            t1_extract = result.tier_performance.get(1, {}).get(
                "extraction_rate", 0
            )
            t2_extract = result.tier_performance.get(2, {}).get(
                "extraction_rate", 0
            )
            t3_extract = result.tier_performance.get(3, {}).get(
                "extraction_rate", 0
            )
            
            tier1_extraction.append(t1_extract)
            tier2_extraction.append(t2_extract)
            tier3_extraction.append(t3_extract)
            
            print(f"   Iteration {i+1}/{num_iterations}: "
                  f"T1={t1_score:.2f}% (ext={t1_extract:.1f}%), "
                  f"T2={t2_score:.2f}% (ext={t2_extract:.1f}%), "
                  f"T3={t3_score:.2f}% (ext={t3_extract:.1f}%)")
        
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
        
        # Additional analysis for information extraction
        print("\n" + "=" * 70)
        print("INFORMATION EXTRACTION ANALYSIS")
        print("=" * 70)
        print()
        
        stats1_ext = calculate_tier_statistics(tier1_extraction, 1)
        stats2_ext = calculate_tier_statistics(tier2_extraction, 2)
        stats3_ext = calculate_tier_statistics(tier3_extraction, 3)
        
        print("Extraction Rate Statistics:")
        print("-" * 70)
        print(f"\nTier 1 (Solo LLM):")
        print(f"  Mean: {stats1_ext.mean:.2f}%")
        print(f"  Std Dev: {stats1_ext.std:.2f}")
        print(f"  95% CI: [{stats1_ext.ci_95_lower:.2f}, "
              f"{stats1_ext.ci_95_upper:.2f}]")
        
        print(f"\nTier 2 (Math Geek):")
        print(f"  Mean: {stats2_ext.mean:.2f}%")
        print(f"  Std Dev: {stats2_ext.std:.2f}")
        print(f"  95% CI: [{stats2_ext.ci_95_lower:.2f}, "
              f"{stats2_ext.ci_95_upper:.2f}]")
        
        print(f"\nTier 3 (Probing):")
        print(f"  Mean: {stats3_ext.mean:.2f}%")
        print(f"  Std Dev: {stats3_ext.std:.2f}")
        print(f"  95% CI: [{stats3_ext.ci_95_lower:.2f}, "
              f"{stats3_ext.ci_95_upper:.2f}]")
        
        # Hypothesis testing
        print("\n" + "=" * 70)
        print("HYPOTHESIS TESTING")
        print("=" * 70)
        print()
        print("Hypothesis: Tier 3 (Probing) extracts significantly more")
        print("information than Tier 1 (Solo LLM) or Tier 2 (Math Geek)")
        print()
        
        # Compare Tier 3 vs Tier 1
        comp_3_1 = compare_tiers(
            tier3_scores, tier1_scores,
            "Tier 3 (Probing)", "Tier 1 (Solo LLM)"
        )
        
        # Compare Tier 3 vs Tier 2
        comp_3_2 = compare_tiers(
            tier3_scores, tier2_scores,
            "Tier 3 (Probing)", "Tier 2 (Math Geek)"
        )
        
        tier3_mean = sum(tier3_scores) / len(tier3_scores)
        tier1_mean = sum(tier1_scores) / len(tier1_scores)
        tier2_mean = sum(tier2_scores) / len(tier2_scores)
        
        tier3_better_than_1 = (
            tier3_mean > tier1_mean and
            comp_3_1['p_value'] < 0.05
        )
        
        tier3_better_than_2 = (
            tier3_mean > tier2_mean and
            comp_3_2['p_value'] < 0.05
        )
        
        print(f"Tier 3 > Tier 1: {tier3_better_than_1}")
        print(f"  Mean diff: {tier3_mean - tier1_mean:.2f}")
        print(f"  p-value: {comp_3_1['p_value']:.4f}")
        print(f"  Cohen's d: {comp_3_1['cohens_d']:.3f}")
        print(f"  {comp_3_1['interpretation']}")
        print()
        
        print(f"Tier 3 > Tier 2: {tier3_better_than_2}")
        print(f"  Mean diff: {tier3_mean - tier2_mean:.2f}")
        print(f"  p-value: {comp_3_2['p_value']:.4f}")
        print(f"  Cohen's d: {comp_3_2['cohens_d']:.3f}")
        print(f"  {comp_3_2['interpretation']}")
        print()
        
        if tier3_better_than_1 and tier3_better_than_2:
            print("✅ HYPOTHESIS CONFIRMED")
            print("Tier 3 (Probing) significantly outperforms both "
                  "Tier 1 and Tier 2")
        else:
            print("❌ HYPOTHESIS NOT CONFIRMED")
            print("Tier 3 does not significantly outperform all tiers")
            
            # Determine actual ranking
            print("\nActual Performance Ranking:")
            rankings = [
                (1, "Tier 1 (Solo LLM)", tier1_mean),
                (2, "Tier 2 (Math Geek)", tier2_mean),
                (3, "Tier 3 (Probing)", tier3_mean)
            ]
            rankings.sort(key=lambda x: x[2], reverse=True)
            
            for rank, (tier_num, tier_name, score) in enumerate(rankings, 1):
                medal = ["🥇", "🥈", "🥉"][rank-1]
                print(f"  {medal} {tier_name}: {score:.2f}%")
        
        print("\n" + "=" * 70)
        print("TEST COMPLETE")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\nERROR during test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point"""
    try:
        success = asyncio.run(test_information_asymmetry_scenario())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError running test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
