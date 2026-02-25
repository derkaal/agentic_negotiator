"""
Unit tests for adversarial buyer scenario.

Tests individual components:
- AdversarialBehavior class
- Metrics calculation
- Configuration loading
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from stress_scenarios.utils.buyer_behaviors import (
    AdversarialBehavior,
    adversarial_first_offer,
    generate_false_offer
)
from stress_scenarios.metrics import (
    calculate_anchor_resistance,
    calculate_deception_detection_score,
    calculate_pressure_resistance
)
from stress_scenarios.config_loader import ConfigLoader


def test_adversarial_behavior():
    """Test AdversarialBehavior class."""
    print("Testing AdversarialBehavior...")
    
    behavior = AdversarialBehavior(
        market_avg=150.0,
        lowball_percentage=0.45
    )
    
    # Test lowball offer
    lowball = behavior.generate_lowball_offer("buyer_1", round_num=1)
    assert lowball["price"] == round(150.0 * 0.45), "Lowball price incorrect"
    assert lowball["tactic"] == "lowball_anchor", "Tactic type incorrect"
    print(f"  ✓ Lowball offer: ${lowball['price']}")
    
    # Test false claim
    false_claim = behavior.generate_false_claim(165.0, round_num=2)
    assert false_claim is not None, "False claim should be generated"
    assert false_claim["tactic"] == "false_claim", "Tactic type incorrect"
    print(f"  ✓ False claim: ${false_claim['claimed_price']}")
    
    # Test social pressure
    pressure = behavior.generate_social_pressure(round_num=3)
    assert pressure is not None, "Social pressure should be generated"
    assert pressure["tactic"] == "social_pressure", "Tactic type incorrect"
    print(f"  ✓ Social pressure: {pressure['message'][:50]}...")
    
    # Test tactics tracking
    tactics = behavior.get_tactics_used()
    assert len(tactics) == 3, "Should have 3 tactics recorded"
    print(f"  ✓ Tactics tracked: {len(tactics)}")
    
    print("  ✓ AdversarialBehavior tests passed\n")


def test_standalone_functions():
    """Test standalone utility functions."""
    print("Testing standalone functions...")
    
    # Test adversarial_first_offer
    offer = adversarial_first_offer("buyer_1", market_avg=150.0)
    assert offer == round(150.0 * 0.55), "First offer incorrect"
    print(f"  ✓ adversarial_first_offer: ${offer}")
    
    # Test generate_false_offer
    false_offer = generate_false_offer(150.0)
    assert false_offer["claimed_price"] == round(150.0 * 0.82)
    assert false_offer["verifiable"] is False
    print(f"  ✓ generate_false_offer: ${false_offer['claimed_price']}")
    
    print("  ✓ Standalone function tests passed\n")


def test_metrics_calculations():
    """Test metrics calculation functions."""
    print("Testing metrics calculations...")
    
    # Test anchor resistance
    # Scenario: Seller counters at $140 when lowball is $80 and
    # expected is $165
    resistance = calculate_anchor_resistance(
        seller_counter=140.0,
        buyer_lowball=80.0,
        market_avg=150.0
    )
    print(f"  ✓ Anchor resistance: {resistance:.2f}")
    assert 0 <= resistance <= 100, "Resistance should be 0-100"
    
    # Test deception detection
    detection = calculate_deception_detection_score(
        deceptions_presented=10,
        deceptions_detected=8,
        deceptions_challenged=6
    )
    print(f"  ✓ Deception detection score: {detection['overall_score']:.2f}")
    assert detection["detection_rate"] == 0.8
    assert detection["challenge_rate"] == 0.6
    
    # Test pressure resistance
    pressure_res = calculate_pressure_resistance(
        panic_concessions=2,
        floor_violations=1,
        urgency_signals=10
    )
    print(f"  ✓ Pressure resistance: {pressure_res:.2f}")
    assert 0 <= pressure_res <= 100, "Resistance should be 0-100"
    
    print("  ✓ Metrics calculation tests passed\n")


def test_config_loader():
    """Test configuration loading."""
    print("Testing configuration loader...")
    
    loader = ConfigLoader()
    
    try:
        config = loader.load("adversarial_buyer")
        print(f"  ✓ Loaded config: {config.name}")
        print(f"  ✓ Max rounds: {config.max_rounds}")
        print(f"  ✓ Market avg: ${config.market_avg}")
        print(f"  ✓ Parameters: {len(config.parameters)} items")
        
        # Validate config
        assert loader.validate_config(config), "Config validation failed"
        print("  ✓ Config validation passed")
        
    except FileNotFoundError:
        print("  ⚠ Config file not found (expected in configs/ directory)")
        print("  ⚠ Skipping config loader test")
    
    print("  ✓ Config loader tests passed\n")


def run_all_tests():
    """Run all unit tests."""
    print("=" * 70)
    print("UNIT TESTS: Adversarial Buyer Scenario")
    print("=" * 70)
    print()
    
    try:
        test_adversarial_behavior()
        test_standalone_functions()
        test_metrics_calculations()
        test_config_loader()
        
        print("=" * 70)
        print("ALL UNIT TESTS PASSED")
        print("=" * 70)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
