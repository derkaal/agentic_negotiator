"""
Scenario 2 (Information Asymmetry) - Full N=30 Statistical Validation

Tests the hypothesis that Tier 3 (Probing Strategist) can extract more
hidden information than Tier 1 (Solo LLM) or Tier 2 (Math Geek).
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
    generate_statistical_report
)


async def main():
    """Run N=30 validation with statistical analysis."""
    print("\n" + "=" * 70)
    print("SCENARIO 2: INFORMATION ASYMMETRY - N=30 VALIDATION")
    print("=" * 70)
    print("\nHypothesis: Tier 3 (Probing) extracts more info than T1/T2")
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
        num_iterations = 30
        print(f"   Iterations: {num_iterations}")
        print()
    except FileNotFoundError as e:
        print(f"   ERROR: {e}")
        return False
    
    # Collect results
    print(f"3. Running {num_iterations} iterations...")
    print("   (This will take several minutes)")
    print()
    
    tier1_scores = []
    tier2_scores = []
    tier3_scores = []
    
    try:
        for i in range(num_iterations):
            result = await runner.run_scenario("information_asymmetry",
                                              config)
            
            # Extract composite scores
            t1 = result.tier_performance.get(1, {})
            t2 = result.tier_performance.get(2, {})
            t3 = result.tier_performance.get(3, {})
            
            t1_score = t1.get("composite_score", 0)
            t2_score = t2.get("composite_score", 0)
            t3_score = t3.get("composite_score", 0)
            
            tier1_scores.append(t1_score)
            tier2_scores.append(t2_score)
            tier3_scores.append(t3_score)
            
            t1_ext = t1.get("extraction_rate", 0)
            t2_ext = t2.get("extraction_rate", 0)
            t3_ext = t3.get("extraction_rate", 0)
            
            print(f"   Iteration {i+1}/{num_iterations}: "
                  f"T1={t1_score:.1f}% (ext={t1_ext:.0f}%), "
                  f"T2={t2_score:.1f}% (ext={t2_ext:.0f}%), "
                  f"T3={t3_score:.1f}% (ext={t3_ext:.0f}%)")
        
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
        
        # Save report
        report_path = Path(__file__).parent / \
            "SCENARIO_2_STATISTICAL_RESULTS.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n6. Report saved to: {report_path}")
        print()
        
        return True
        
    except Exception as e:
        print(f"\nERROR during execution: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
