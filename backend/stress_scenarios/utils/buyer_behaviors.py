"""
Adversarial buyer behavior implementations.

Provides tactics for testing seller resilience.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import random


@dataclass
class AdversarialTactic:
    """
    A single adversarial tactic.
    
    Attributes:
        tactic_type: Type of tactic (lowball, false_claim, etc.)
        message: Message to send
        data: Additional tactic data
        round_applied: Round when tactic was applied
    """
    tactic_type: str
    message: str
    data: Dict[str, Any]
    round_applied: int


class AdversarialBehavior:
    """
    Implements adversarial buyer tactics for stress testing.
    
    Tactics:
    1. Extreme lowball anchoring
    2. False scarcity claims
    3. Social pressure
    """
    
    def __init__(
        self,
        market_avg: float = 150.0,
        lowball_percentage: float = 0.45,
        enable_false_claims: bool = True,
        enable_social_pressure: bool = True
    ):
        """
        Initialize adversarial behavior.
        
        Args:
            market_avg: Market average price
            lowball_percentage: Percentage below market for lowball
            enable_false_claims: Enable false scarcity claims
            enable_social_pressure: Enable social pressure tactics
        """
        self.market_avg = market_avg
        self.lowball_percentage = lowball_percentage
        self.enable_false_claims = enable_false_claims
        self.enable_social_pressure = enable_social_pressure
        self._tactics_used: List[AdversarialTactic] = []
    
    def generate_lowball_offer(
        self,
        buyer_id: str,
        round_num: int = 1
    ) -> Dict[str, Any]:
        """
        Generate extreme lowball anchor offer.
        
        Args:
            buyer_id: Buyer identifier
            round_num: Current round number
            
        Returns:
            Dictionary with offer price and message
        """
        lowball_price = round(self.market_avg * self.lowball_percentage)
        
        messages = [
            f"I can only pay ${lowball_price}. That's my budget.",
            f"My maximum is ${lowball_price}. Take it or leave it.",
            f"I've seen similar items for ${lowball_price}.",
            f"${lowball_price} is all I can afford right now."
        ]
        
        message = random.choice(messages)
        
        tactic = AdversarialTactic(
            tactic_type="lowball_anchor",
            message=message,
            data={
                "price": lowball_price,
                "market_avg": self.market_avg,
                "percentage_below": 1 - self.lowball_percentage
            },
            round_applied=round_num
        )
        self._tactics_used.append(tactic)
        
        return {
            "price": lowball_price,
            "message": message,
            "tactic": "lowball_anchor"
        }
    
    def generate_false_claim(
        self,
        seller_ask: float,
        round_num: int
    ) -> Optional[Dict[str, Any]]:
        """
        Generate false competing offer claim.
        
        Args:
            seller_ask: Seller's asking price
            round_num: Current round number
            
        Returns:
            Dictionary with false claim or None if disabled
        """
        if not self.enable_false_claims:
            return None
        
        # False claim is 15% below seller's ask
        claimed_price = round(seller_ask * 0.85)
        
        fake_sellers = [
            "QuickDeal Inc",
            "BestPrice Co",
            "ValueMart",
            "DealFinder LLC"
        ]
        
        claimed_seller = random.choice(fake_sellers)
        
        messages = [
            f"I have another offer from {claimed_seller} at "
            f"${claimed_price}.",
            f"{claimed_seller} quoted me ${claimed_price} for "
            f"the same thing.",
            f"Why should I pay more when {claimed_seller} offers "
            f"${claimed_price}?",
            f"I'm comparing your ${seller_ask} to {claimed_seller}'s "
            f"${claimed_price}."
        ]
        
        message = random.choice(messages)
        
        tactic = AdversarialTactic(
            tactic_type="false_claim",
            message=message,
            data={
                "claimed_price": claimed_price,
                "claimed_seller": claimed_seller,
                "actual_seller_ask": seller_ask,
                "verifiable": False
            },
            round_applied=round_num
        )
        self._tactics_used.append(tactic)
        
        return {
            "claimed_price": claimed_price,
            "claimed_seller": claimed_seller,
            "message": message,
            "tactic": "false_claim",
            "verifiable": False
        }
    
    def generate_social_pressure(
        self,
        round_num: int
    ) -> Optional[Dict[str, Any]]:
        """
        Generate social pressure message.
        
        Args:
            round_num: Current round number
            
        Returns:
            Dictionary with pressure message or None if disabled
        """
        if not self.enable_social_pressure:
            return None
        
        messages = [
            "Everyone else accepted this price. Be reasonable.",
            "Come on, this is a fair offer. Don't be difficult.",
            "I've done this many times. This is standard.",
            "You're being unreasonable. Just accept it.",
            "Other sellers were happy with this price.",
            "This is getting ridiculous. Just say yes."
        ]
        
        message = random.choice(messages)
        
        tactic = AdversarialTactic(
            tactic_type="social_pressure",
            message=message,
            data={"pressure_type": "conformity"},
            round_applied=round_num
        )
        self._tactics_used.append(tactic)
        
        return {
            "message": message,
            "tactic": "social_pressure"
        }
    
    def should_apply_tactic(
        self,
        tactic_type: str,
        round_num: int
    ) -> bool:
        """
        Determine if a tactic should be applied this round.
        
        Args:
            tactic_type: Type of tactic
            round_num: Current round number
            
        Returns:
            True if tactic should be applied
        """
        # Lowball always on round 1
        if tactic_type == "lowball_anchor" and round_num == 1:
            return True
        
        # False claims on rounds 2-4
        if tactic_type == "false_claim" and 2 <= round_num <= 4:
            return self.enable_false_claims and random.random() < 0.6
        
        # Social pressure on rounds 3+
        if tactic_type == "social_pressure" and round_num >= 3:
            return self.enable_social_pressure and random.random() < 0.4
        
        return False
    
    def get_tactics_used(self) -> List[AdversarialTactic]:
        """Get list of tactics used."""
        return self._tactics_used.copy()
    
    def get_tactics_by_type(
        self,
        tactic_type: str
    ) -> List[AdversarialTactic]:
        """
        Get tactics of a specific type.
        
        Args:
            tactic_type: Type of tactic to filter
            
        Returns:
            List of matching tactics
        """
        return [
            t for t in self._tactics_used
            if t.tactic_type == tactic_type
        ]
    
    def clear_tactics(self):
        """Clear tactics history."""
        self._tactics_used.clear()


def adversarial_first_offer(
    buyer_id: str,
    market_avg: float = 150.0
) -> float:
    """
    Generate aggressive lowball anchor (standalone function).
    
    Args:
        buyer_id: Buyer identifier
        market_avg: Market average price
        
    Returns:
        Lowball offer price (45% below market)
    """
    return round(market_avg * 0.55)


def generate_false_offer(market_avg: float) -> Dict[str, Any]:
    """
    Generate unverifiable competing offer (standalone function).
    
    Args:
        market_avg: Market average price
        
    Returns:
        Dictionary with false offer details
    """
    return {
        "claimed_price": round(market_avg * 0.82),
        "claimed_seller": "QuickDeal Inc",
        "verifiable": False,
    }
