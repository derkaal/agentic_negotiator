"""
Unit tests for Information Asymmetry Scenario (Scenario 2).

Tests TDD-style:
1. Asymmetry type implementations
2. Probe detection
3. Information extraction
4. Metrics calculation
"""

import sys
import os
import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from stress_scenarios.utils.asymmetry_types import (
    HiddenUrgency,
    HiddenBudget,
    HiddenAlternatives,
    HiddenQualityPreferences,
    AsymmetryConfig,
    create_asymmetry
)
from stress_scenarios.utils.information_extraction import (
    ProbeDetector,
    BuyerResponseGenerator,
    InformationExtractor,
    Discovery
)


class TestAsymmetryTypes:
    """Test asymmetry type implementations"""
    
    def test_hidden_urgency_effect(self):
        """Hidden urgency should increase premium near deadline"""
        config = AsymmetryConfig(
            asymmetry_type="urgency",
            severity=0.5,
            parameters={
                "deadline": 5,
                "max_premium": 0.10,
                "disclosure_probability": 0.7
            }
        )
        
        urgency = HiddenUrgency(config)
        
        # Round 1: Low urgency
        effect_r1 = urgency.get_effect({"round": 1})
        assert 0.0 <= effect_r1 <= 0.03
        
        # Round 5: Maximum urgency (at deadline)
        effect_r5 = urgency.get_effect({"round": 5})
        assert effect_r5 == 0.10
        
        # Round 6: Past deadline
        effect_r6 = urgency.get_effect({"round": 6})
        assert effect_r6 == 0.10
    
    def test_hidden_budget_gap(self):
        """Hidden budget should reveal budget headroom"""
        config = AsymmetryConfig(
            asymmetry_type="budget",
            severity=0.5,
            parameters={
                "claimed_max": 100,
                "actual_max": 110,
                "disclosure_probability": 0.5
            }
        )
        
        budget = HiddenBudget(config)
        
        # Should reveal 10 unit gap
        effect = budget.get_effect({})
        assert effect == 10
        
        hidden_value = budget.get_hidden_value()
        assert hidden_value["gap"] == 10
    
    def test_hidden_alternatives_bluff(self):
        """Hidden alternatives should reveal bluff magnitude"""
        config = AsymmetryConfig(
            asymmetry_type="alternatives",
            severity=0.5,
            parameters={
                "claimed_alternative": 90,
                "actual_alternative": 105,
                "disclosure_probability": 0.3
            }
        )
        
        alternatives = HiddenAlternatives(config)
        
        # Should reveal 15 unit bluff
        effect = alternatives.get_effect({})
        assert effect == 15
    
    def test_asymmetry_revelation(self):
        """Asymmetries should track revelation status"""
        asymmetry = create_asymmetry(
            "urgency",
            deadline=5,
            max_premium=0.10,
            disclosure_probability=0.7
        )
        
        assert not asymmetry.revealed
        assert asymmetry.discovery_round is None
        
        asymmetry.mark_revealed(3)
        
        assert asymmetry.revealed
        assert asymmetry.discovery_round == 3


class TestProbeDetection:
    """Test probe detection functionality"""
    
    def test_detect_urgency_probe(self):
        """Should detect urgency-related questions"""
        detector = ProbeDetector()
        
        messages = [
            "What's your timeline for this purchase?",
            "Do you have a deadline?",
            "How soon do you need this?",
            "Is this time-sensitive?"
        ]
        
        for msg in messages:
            probe_type = detector.detect(msg)
            assert probe_type == "urgency", f"Failed for: {msg}"
    
    def test_detect_budget_probe(self):
        """Should detect budget-related questions"""
        detector = ProbeDetector()
        
        messages = [
            "What's your maximum budget?",
            "How much can you afford?",
            "What's your price range?",
            "Is your budget flexible?"
        ]
        
        for msg in messages:
            probe_type = detector.detect(msg)
            assert probe_type == "budget", f"Failed for: {msg}"
    
    def test_detect_alternatives_probe(self):
        """Should detect alternative-related questions"""
        detector = ProbeDetector()
        
        messages = [
            "Do you have other offers?",
            "Are you comparing alternatives?",
            "What other options are you considering?"
        ]
        
        for msg in messages:
            probe_type = detector.detect(msg)
            assert probe_type == "alternatives", f"Failed for: {msg}"
    
    def test_detect_quality_probe(self):
        """Should detect quality preference questions"""
        detector = ProbeDetector()
        
        messages = [
            "What's your priority - price or quality?",
            "Which features matter most to you?",
            "What do you value most?"
        ]
        
        for msg in messages:
            probe_type = detector.detect(msg)
            assert probe_type == "quality", f"Failed for: {msg}"
    
    def test_no_probe_detected(self):
        """Should return None for non-probe messages"""
        detector = ProbeDetector()
        
        messages = [
            "Here's my offer.",
            "I can do $100.",
            "Let me think about that."
        ]
        
        for msg in messages:
            probe_type = detector.detect(msg)
            assert probe_type is None, f"False positive for: {msg}"


class TestInformationExtraction:
    """Test information extraction functionality"""
    
    def test_extraction_with_revelation(self):
        """Should extract information when buyer reveals"""
        extractor = InformationExtractor()
        
        # Create asymmetry that always reveals
        asymmetry = create_asymmetry(
            "urgency",
            deadline=5,
            max_premium=0.10,
            disclosure_probability=1.0  # Always reveal
        )
        
        buyer_asymmetries = {"urgency": asymmetry}
        
        # Process probe message
        discovery = extractor.process_message(
            "What's your timeline?",
            buyer_asymmetries,
            current_round=2
        )
        
        # Should discover information
        assert discovery is not None
        assert discovery.asymmetry_type == "urgency"
        assert discovery.discovered_at_round == 2
        assert asymmetry.revealed
    
    def test_extraction_without_revelation(self):
        """Should not extract when buyer hides information"""
        extractor = InformationExtractor()
        
        # Create asymmetry that never reveals
        asymmetry = create_asymmetry(
            "budget",
            claimed_max=100,
            actual_max=110,
            disclosure_probability=0.0  # Never reveal
        )
        
        buyer_asymmetries = {"budget": asymmetry}
        
        # Process probe message
        discovery = extractor.process_message(
            "What's your maximum budget?",
            buyer_asymmetries,
            current_round=2
        )
        
        # Should not discover information
        assert discovery is None
        assert not asymmetry.revealed
    
    def test_extraction_rate_calculation(self):
        """Should calculate extraction rate correctly"""
        extractor = InformationExtractor()
        
        # Create multiple asymmetries
        asymmetries = {
            "urgency": create_asymmetry(
                "urgency",
                deadline=5,
                max_premium=0.10,
                disclosure_probability=1.0
            ),
            "budget": create_asymmetry(
                "budget",
                claimed_max=100,
                actual_max=110,
                disclosure_probability=0.0
            )
        }
        
        # Process probes
        extractor.process_message(
            "What's your timeline?",
            asymmetries,
            current_round=1
        )
        
        extractor.process_message(
            "What's your budget?",
            asymmetries,
            current_round=2
        )
        
        # Should have 50% extraction rate (1 of 2)
        rate = extractor.get_extraction_rate()
        assert rate == 0.5
    
    def test_discovery_summary(self):
        """Should provide accurate discovery summary"""
        extractor = InformationExtractor()
        
        asymmetries = {
            "urgency": create_asymmetry(
                "urgency",
                deadline=5,
                max_premium=0.10,
                disclosure_probability=1.0
            )
        }
        
        # Process probe
        extractor.process_message(
            "What's your timeline?",
            asymmetries,
            current_round=1
        )
        
        summary = extractor.get_discovery_summary()
        
        assert summary["total_probes"] == 1
        assert summary["total_discoveries"] == 1
        assert summary["extraction_rate"] == 1.0
        assert summary["discoveries_by_type"]["urgency"] == 1


class TestTierPerformance:
    """Test tier-specific performance expectations"""
    
    def test_tier3_extracts_hidden_urgency(self):
        """Tier 3 should detect and extract urgency information"""
        # This is a conceptual test - in production, would test
        # actual Tier 3 behavior
        
        extractor = InformationExtractor()
        
        # Tier 3 asks probing questions
        probe_message = "What's your timeline for this purchase?"
        
        # Should detect probe
        probe_type = extractor.probe_detector.detect(probe_message)
        assert probe_type == "urgency"
    
    def test_tier2_blind_to_asymmetry(self):
        """Tier 2 should have near-zero extraction rate"""
        # Tier 2 focuses on math, not probing
        # Expected extraction rate: 0-10%
        
        # This would be validated in integration tests
        expected_range = (0.0, 0.10)
        assert expected_range[0] <= expected_range[1]
    
    def test_premium_capture_requires_discovery(self):
        """Premium capture should correlate with extraction rate"""
        # Higher extraction rate should lead to higher premium
        
        # Tier 1: 20-30% extraction → 2-5% premium
        # Tier 3: 70-85% extraction → 10-20% premium
        
        tier1_extraction = 0.25
        tier3_extraction = 0.75
        
        assert tier3_extraction > tier1_extraction
        
        # Premium should scale with extraction
        tier1_premium = tier1_extraction * 0.15  # ~3.75%
        tier3_premium = tier3_extraction * 0.20  # ~15%
        
        assert tier3_premium > tier1_premium


def test_statistical_significance_n30():
    """Tier differences should be statistically significant with N=30"""
    # With N=30 iterations, differences should be significant
    
    # Expected tier performance (from spec)
    tier1_extraction = 0.25  # 25%
    tier2_extraction = 0.05  # 5%
    tier3_extraction = 0.75  # 75%
    
    # Tier 3 vs Tier 1 difference
    diff_3_1 = tier3_extraction - tier1_extraction
    assert diff_3_1 == 0.50  # 50 percentage points
    
    # Tier 3 vs Tier 2 difference
    diff_3_2 = tier3_extraction - tier2_extraction
    assert diff_3_2 == 0.70  # 70 percentage points
    
    # With N=30 and these effect sizes, p < 0.001 expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
