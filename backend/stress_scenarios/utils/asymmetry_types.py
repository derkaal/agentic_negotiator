"""
Information Asymmetry Types Module

Defines different types of hidden information that buyers may possess
during negotiations, and their effects on negotiation dynamics.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import random


@dataclass
class AsymmetryConfig:
    """Configuration for an asymmetry instance"""
    asymmetry_type: str
    severity: float  # 0.0 to 1.0
    parameters: Dict[str, Any]


class AsymmetryType(ABC):
    """Abstract base class for information asymmetries"""
    
    def __init__(self, config: AsymmetryConfig):
        self.config = config
        self.revealed = False
        self.discovery_round: Optional[int] = None
    
    @abstractmethod
    def get_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate impact on negotiation
        
        Args:
            context: Current negotiation context (round, price, etc.)
            
        Returns:
            Effect magnitude (e.g., price premium, urgency multiplier)
        """
        pass
    
    @abstractmethod
    def should_reveal_if_asked(self) -> bool:
        """
        Determine if buyer reveals information when probed
        
        Returns:
            True if buyer discloses, False if they hide
        """
        pass
    
    def mark_revealed(self, round_num: int):
        """Mark asymmetry as discovered"""
        self.revealed = True
        self.discovery_round = round_num
    
    def get_hidden_value(self) -> Any:
        """Get the hidden information value"""
        return self.config.parameters.get("hidden_value")


class HiddenUrgency(AsymmetryType):
    """
    Buyer has a deadline but doesn't disclose it
    
    Effect: Willing to pay premium as deadline approaches
    """
    
    def __init__(self, config: AsymmetryConfig):
        super().__init__(config)
        self.deadline = config.parameters.get("deadline", 5)  # rounds
        self.max_premium = config.parameters.get("max_premium", 0.10)  # 10%
    
    def get_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate urgency premium based on proximity to deadline
        
        Returns:
            Premium multiplier (0.0 to max_premium)
        """
        current_round = context.get("round", 0)
        
        if current_round >= self.deadline:
            # At or past deadline - maximum urgency
            return self.max_premium
        
        # Linear increase in urgency as deadline approaches
        urgency_factor = current_round / self.deadline
        return self.max_premium * urgency_factor
    
    def should_reveal_if_asked(self) -> bool:
        """70% chance to reveal if directly asked about timeline"""
        disclosure_prob = self.config.parameters.get("disclosure_probability", 0.7)
        return random.random() < disclosure_prob
    
    def get_hidden_value(self) -> Dict[str, Any]:
        return {
            "deadline": self.deadline,
            "max_premium": self.max_premium
        }


class HiddenBudget(AsymmetryType):
    """
    Buyer has higher maximum budget than claimed
    
    Effect: Can pay more but anchors seller to lower price
    """
    
    def __init__(self, config: AsymmetryConfig):
        super().__init__(config)
        self.claimed_max = config.parameters.get("claimed_max", 100)
        self.actual_max = config.parameters.get("actual_max", 110)
        self.budget_gap = self.actual_max - self.claimed_max
    
    def get_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate available budget headroom
        
        Returns:
            Additional budget available (absolute value)
        """
        return self.budget_gap
    
    def should_reveal_if_asked(self) -> bool:
        """50% chance to reveal if directly asked about budget"""
        disclosure_prob = self.config.parameters.get("disclosure_probability", 0.5)
        return random.random() < disclosure_prob
    
    def get_hidden_value(self) -> Dict[str, Any]:
        return {
            "claimed_max": self.claimed_max,
            "actual_max": self.actual_max,
            "gap": self.budget_gap
        }


class HiddenAlternatives(AsymmetryType):
    """
    Buyer misrepresents competing offers
    
    Effect: Claims better alternatives to anchor price lower
    """
    
    def __init__(self, config: AsymmetryConfig):
        super().__init__(config)
        self.claimed_alternative = config.parameters.get("claimed_alternative", 90)
        self.actual_alternative = config.parameters.get("actual_alternative", 105)
        self.bluff_magnitude = self.actual_alternative - self.claimed_alternative
    
    def get_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate bluff magnitude
        
        Returns:
            Difference between claimed and actual alternatives
        """
        return self.bluff_magnitude
    
    def should_reveal_if_asked(self) -> bool:
        """30% chance to reveal if asked for proof of alternatives"""
        disclosure_prob = self.config.parameters.get("disclosure_probability", 0.3)
        return random.random() < disclosure_prob
    
    def get_hidden_value(self) -> Dict[str, Any]:
        return {
            "claimed_alternative": self.claimed_alternative,
            "actual_alternative": self.actual_alternative,
            "bluff_magnitude": self.bluff_magnitude
        }


class HiddenQualityPreferences(AsymmetryType):
    """
    Buyer values quality attributes differently than stated
    
    Effect: Willing to pay premium for specific features
    """
    
    def __init__(self, config: AsymmetryConfig):
        super().__init__(config)
        self.stated_preference = config.parameters.get("stated_preference", "price")
        self.actual_preference = config.parameters.get("actual_preference", "quality")
        self.quality_premium = config.parameters.get("quality_premium", 0.15)  # 15%
    
    def get_effect(self, context: Dict[str, Any]) -> float:
        """
        Calculate quality premium buyer is willing to pay
        
        Returns:
            Premium for quality (percentage)
        """
        seller_quality = context.get("seller_quality", "standard")
        
        if seller_quality == "premium" and self.actual_preference == "quality":
            return self.quality_premium
        
        return 0.0
    
    def should_reveal_if_asked(self) -> bool:
        """60% chance to reveal if asked about priorities"""
        disclosure_prob = self.config.parameters.get("disclosure_probability", 0.6)
        return random.random() < disclosure_prob
    
    def get_hidden_value(self) -> Dict[str, Any]:
        return {
            "stated_preference": self.stated_preference,
            "actual_preference": self.actual_preference,
            "quality_premium": self.quality_premium
        }


def create_asymmetry(asymmetry_type: str, **kwargs) -> AsymmetryType:
    """
    Factory function to create asymmetry instances
    
    Args:
        asymmetry_type: Type of asymmetry to create
        **kwargs: Configuration parameters
        
    Returns:
        AsymmetryType instance
    """
    config = AsymmetryConfig(
        asymmetry_type=asymmetry_type,
        severity=kwargs.get("severity", 0.5),
        parameters=kwargs
    )
    
    asymmetry_classes = {
        "urgency": HiddenUrgency,
        "budget": HiddenBudget,
        "alternatives": HiddenAlternatives,
        "quality": HiddenQualityPreferences
    }
    
    asymmetry_class = asymmetry_classes.get(asymmetry_type)
    if not asymmetry_class:
        raise ValueError(f"Unknown asymmetry type: {asymmetry_type}")
    
    return asymmetry_class(config)
