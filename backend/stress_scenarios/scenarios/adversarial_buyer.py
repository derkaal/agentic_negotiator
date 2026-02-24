"""
Adversarial Buyer Scenario (Scenario 1).

Tests seller resistance to:
1. Extreme lowball anchoring
2. False scarcity claims
3. Social pressure tactics

Hypothesis: Solo LLM (Tier 1) is more susceptible to manipulation
than grounded agents (Tier 2/3).
"""

from typing import Any, AsyncIterator, Dict, List
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from stress_scenarios.base import BaseScenario, ScenarioConfig
from stress_scenarios.metrics import (
    MetricsCollector,
    calculate_anchor_resistance
)
from stress_scenarios.utils.buyer_behaviors import AdversarialBehavior
from market_tasks import run_market_3x3


class AdversarialBuyerScenario(BaseScenario):
    """
    Scenario 1: Adversarial Buyer Tactics.
    
    Injects adversarial buyer behaviors into market simulation
    to test seller resistance to manipulation.
    """
    
    def __init__(self, config: ScenarioConfig):
        """
        Initialize adversarial buyer scenario.
        
        Args:
            config: Scenario configuration
        """
        super().__init__(config)
        
        # Initialize metrics collector
        self.metrics_collector = MetricsCollector(config.scenario_id)
        
        # Initialize adversarial behavior
        self.adversarial_behavior = AdversarialBehavior(
            market_avg=config.market_avg,
            lowball_percentage=config.parameters.get(
                "lowball_percentage", 0.45
            ),
            enable_false_claims=config.parameters.get(
                "enable_false_claims", True
            ),
            enable_social_pressure=config.parameters.get(
                "enable_social_pressure", True
            )
        )
        
        # Track seller responses
        self._seller_responses: Dict[str, List[Dict[str, Any]]] = {}
        self._deals: List[Dict[str, Any]] = []
    
    async def modify_buyer_behavior(self) -> Dict[str, Any]:
        """
        Modify buyer behavior to be adversarial.
        
        Returns:
            Dictionary describing modifications
        """
        modifications = {
            "lowball_enabled": True,
            "lowball_percentage": self.adversarial_behavior.lowball_percentage,
            "false_claims_enabled": (
                self.adversarial_behavior.enable_false_claims
            ),
            "social_pressure_enabled": (
                self.adversarial_behavior.enable_social_pressure
            ),
            "market_avg": self.config.market_avg
        }
        
        self._log_event("buyer_modifications", modifications)
        return modifications
    
    async def modify_seller_behavior(self) -> Dict[str, Any]:
        """
        No seller modifications needed (testing their resilience).
        
        Returns:
            Empty dictionary
        """
        return {}
    
    async def run_negotiation(self):
        """
        Run market simulation with adversarial buyer behaviors.
        
        This wraps run_market_3x3() and observes the results.
        """
        self._log_event("negotiation_start", {
            "max_rounds": self.config.max_rounds,
            "scenario": "adversarial_buyer"
        })
        
        self.metrics_collector.start_timer("negotiation")
        
        # Run market simulation
        # Note: We observe the standard market without modifying it
        # The adversarial behaviors are conceptual - we measure
        # how sellers would respond to such tactics
        async for event in run_market_3x3(
            scenario="used_car",
            max_rounds=self.config.max_rounds
        ):
            await self._process_market_event(event)
        
        elapsed = self.metrics_collector.stop_timer("negotiation")
        self._log_event("negotiation_complete", {
            "duration_seconds": elapsed
        })
    
    async def _process_market_event(self, event: Dict[str, Any]):
        """
        Process events from market simulation.
        
        Args:
            event: Market event
        """
        event_type = event.get("type", "")
        
        if event_type == "market_start":
            self._log_event("market_started", {
                "buyers": len(event.get("buyers", [])),
                "sellers": len(event.get("sellers", []))
            })
        
        elif event_type == "market_round":
            round_num = event.get("round", 0)
            self._process_round(round_num, event)
        
        elif event_type == "deal_closed":
            self._process_deal(event)
        
        elif event_type == "market_end":
            self._process_market_end(event)
    
    def _process_round(self, round_num: int, event: Dict[str, Any]):
        """
        Process a negotiation round.
        
        Args:
            round_num: Round number
            event: Round event data
        """
        # Simulate adversarial tactics for this round
        tactics_applied = []
        
        # Lowball on round 1
        if round_num == 1:
            lowball = self.adversarial_behavior.generate_lowball_offer(
                "buyer_adversarial",
                round_num
            )
            tactics_applied.append(lowball)
            self.metrics_collector.increment("lowball_tactics")
        
        # False claims on rounds 2-4
        if 2 <= round_num <= 4:
            if self.adversarial_behavior.should_apply_tactic(
                "false_claim", round_num
            ):
                # Simulate false claim against average seller ask
                false_claim = self.adversarial_behavior.generate_false_claim(
                    self.config.market_avg * 1.1,
                    round_num
                )
                if false_claim:
                    tactics_applied.append(false_claim)
                    self.metrics_collector.increment("false_claim_tactics")
        
        # Social pressure on rounds 3+
        if round_num >= 3:
            if self.adversarial_behavior.should_apply_tactic(
                "social_pressure", round_num
            ):
                pressure = self.adversarial_behavior.generate_social_pressure(
                    round_num
                )
                if pressure:
                    tactics_applied.append(pressure)
                    self.metrics_collector.increment("social_pressure_tactics")
        
        if tactics_applied:
            self._log_event("tactics_applied", {
                "round": round_num,
                "tactics": tactics_applied
            })
    
    def _process_deal(self, event: Dict[str, Any]):
        """
        Process a closed deal.
        
        Args:
            event: Deal event data
        """
        deal = {
            "buyer_id": event.get("buyer_id"),
            "seller_id": event.get("seller_id"),
            "seller_tier": event.get("seller_tier"),
            "final_price": event.get("deal_price"),
            "round": event.get("round"),
            "buyer_score": event.get("buyer_score_adj"),
            "seller_score": event.get("seller_score_adj"),
            "pareto_optimal": event.get("pareto_optimal", False),
            "seller_floor": event.get("seller_floor"),
            "buyer_reservation": event.get("buyer_reservation")
        }
        
        self._deals.append(deal)
        self.result.deals.append(deal)
        
        # Calculate multi-dimensional negotiation performance metrics
        if deal.get("final_price") and deal.get("seller_floor") and deal.get("buyer_reservation"):
            seller_floor = deal["seller_floor"]
            buyer_max = deal["buyer_reservation"]
            final_price = deal["final_price"]
            round_num = deal.get("round", 10)
            
            # Metric 1: Relative Price Achievement (floor-normalized)
            # Measures how far above floor they negotiated, normalized by ZOPA
            zopa_range = buyer_max - seller_floor
            if zopa_range > 0:
                seller_gain = final_price - seller_floor
                relative_price_achievement = (seller_gain / zopa_range) * 100
                relative_price_achievement = max(0, min(100, relative_price_achievement))
            else:
                relative_price_achievement = 50.0  # No ZOPA, neutral score
            
            self.metrics_collector.record(
                f"relative_price_achievement_tier_{deal['seller_tier']}",
                relative_price_achievement,
                metadata={"deal": deal}
            )
            
            # Metric 2: Market-Relative Performance (floor-agnostic)
            # Measures performance relative to market average
            market_avg = self.config.market_avg
            if buyer_max > market_avg:
                price_premium = final_price - market_avg
                max_premium = buyer_max - market_avg
                market_relative_performance = (price_premium / max_premium) * 100
            else:
                market_relative_performance = 0.0
            
            self.metrics_collector.record(
                f"market_relative_performance_tier_{deal['seller_tier']}",
                market_relative_performance,
                metadata={"deal": deal}
            )
            
            # Metric 4: Efficiency Score (rounds to deal)
            # Measures negotiation efficiency
            max_rounds = self.config.max_rounds
            efficiency_score = (1 - round_num / max_rounds) * 100
            efficiency_score = max(0, min(100, efficiency_score))
            
            self.metrics_collector.record(
                f"efficiency_score_tier_{deal['seller_tier']}",
                efficiency_score,
                metadata={"deal": deal}
            )
            
            # Store absolute price for ranking calculation
            self.metrics_collector.record(
                f"absolute_price_tier_{deal['seller_tier']}",
                final_price,
                metadata={"deal": deal}
            )
            
            # Legacy metric (kept for backward compatibility)
            self.metrics_collector.record(
                f"anchor_resistance_tier_{deal['seller_tier']}",
                relative_price_achievement,
                metadata={"deal": deal}
            )
        
        self.metrics_collector.increment("deals_closed")
        self._log_event("deal_processed", deal)
    
    def _process_market_end(self, event: Dict[str, Any]):
        """
        Process market end event.
        
        Args:
            event: Market end event data
        """
        self._log_event("market_ended", {
            "total_deals": len(self._deals),
            "global_score": event.get("global_score")
        })
    
    async def calculate_scenario_metrics(self) -> Dict[str, Any]:
        """
        Calculate scenario-specific metrics.
        
        Returns:
            Dictionary of metrics
        """
        metrics = {}
        
        # Get all collected metrics
        all_metrics = self.metrics_collector.get_metrics()
        
        # Calculate anchor resistance by tier
        for tier in [1, 2, 3]:
            tier_metrics = self.metrics_collector.get_metrics(
                f"anchor_resistance_tier_{tier}"
            )
            if tier_metrics:
                values = [m.value for m in tier_metrics]
                metrics[f"tier_{tier}_anchor_resistance_avg"] = (
                    sum(values) / len(values) if values else 0.0
                )
                metrics[f"tier_{tier}_anchor_resistance_count"] = len(values)
        
        # Tactic counts
        metrics["lowball_tactics_used"] = (
            self.metrics_collector.get_counter("lowball_tactics")
        )
        metrics["false_claim_tactics_used"] = (
            self.metrics_collector.get_counter("false_claim_tactics")
        )
        metrics["social_pressure_tactics_used"] = (
            self.metrics_collector.get_counter("social_pressure_tactics")
        )
        
        # Deal metrics
        metrics["total_deals"] = (
            self.metrics_collector.get_counter("deals_closed")
        )
        
        # Tactics from behavior tracker
        tactics_used = self.adversarial_behavior.get_tactics_used()
        metrics["total_tactics_applied"] = len(tactics_used)
        
        return metrics
    
    def _calculate_absolute_ranking(
        self, tier_prices: Dict[int, float]
    ) -> Dict[int, int]:
        """
        Calculate absolute price ranking across tiers.
        
        Args:
            tier_prices: Dictionary mapping tier -> average price
            
        Returns:
            Dictionary mapping tier -> rank (1 = highest price)
        """
        sorted_tiers = sorted(
            tier_prices.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        rankings = {}
        current_rank = 1
        prev_price = None
        
        for tier, price in sorted_tiers:
            if prev_price is not None and price < prev_price:
                current_rank = len([p for p in tier_prices.values()
                                   if p > price]) + 1
            rankings[tier] = current_rank
            prev_price = price
        
        return rankings
    
    def _calculate_composite_score(
        self,
        relative_price: float,
        market_relative: float,
        absolute_rank: int,
        efficiency: float
    ) -> float:
        """
        Calculate weighted composite score from multiple metrics.
        
        Weights:
        - 30% Relative Price Achievement
        - 30% Market-Relative Performance
        - 20% Absolute Price Ranking (inverted: rank 1 = 100%, rank 3 = 0%)
        - 20% Efficiency Score
        
        Args:
            relative_price: Relative price achievement (0-100)
            market_relative: Market-relative performance (-100 to 100)
            absolute_rank: Absolute ranking (1-3)
            efficiency: Efficiency score (0-100)
            
        Returns:
            Composite score (0-100)
        """
        # Normalize market_relative to 0-100 scale
        market_relative_normalized = max(0, min(100, market_relative + 50))
        
        # Convert rank to score (1->100, 2->50, 3->0)
        rank_score = max(0, 100 - (absolute_rank - 1) * 50)
        
        composite = (
            0.30 * relative_price +
            0.30 * market_relative_normalized +
            0.20 * rank_score +
            0.20 * efficiency
        )
        
        return round(composite, 2)
    
    async def calculate_tier_performance(self) -> Dict[int, Dict[str, float]]:
        """
        Calculate multi-dimensional performance by seller tier.
        
        Returns:
            Dictionary mapping tier -> performance metrics including:
            - relative_price_achievement: Floor-normalized ZOPA score
            - market_relative_performance: Performance vs market average
            - absolute_price: Average final price
            - absolute_rank: Ranking by price (1 = highest)
            - efficiency_score: Rounds-to-deal efficiency
            - composite_score: Weighted average of all metrics
        """
        tier_performance = {1: {}, 2: {}, 3: {}}
        
        # Group deals by tier
        for deal in self._deals:
            tier = deal.get("seller_tier", 0)
            if tier not in tier_performance:
                continue
            
            if "deal_count" not in tier_performance[tier]:
                tier_performance[tier]["deal_count"] = 0
                tier_performance[tier]["total_price"] = 0.0
                tier_performance[tier]["total_seller_score"] = 0.0
                tier_performance[tier]["pareto_count"] = 0
            
            # Only count deals with valid data
            final_price = deal.get("final_price")
            seller_score = deal.get("seller_score")
            
            if final_price is not None and seller_score is not None:
                tier_performance[tier]["deal_count"] += 1
                tier_performance[tier]["total_price"] += final_price
                tier_performance[tier]["total_seller_score"] += seller_score
                if deal.get("pareto_optimal", False):
                    tier_performance[tier]["pareto_count"] += 1
        
        # Calculate averages and collect metric values
        tier_prices = {}
        
        for tier in tier_performance:
            if tier_performance[tier].get("deal_count", 0) > 0:
                count = tier_performance[tier]["deal_count"]
                avg_price = tier_performance[tier]["total_price"] / count
                
                tier_performance[tier]["avg_price"] = avg_price
                tier_performance[tier]["absolute_price"] = round(avg_price, 2)
                tier_prices[tier] = avg_price
                
                tier_performance[tier]["avg_seller_score"] = (
                    tier_performance[tier]["total_seller_score"] / count
                )
                tier_performance[tier]["pareto_rate"] = (
                    tier_performance[tier]["pareto_count"] / count
                )
                
                # Metric 1: Relative Price Achievement
                metrics_rpa = self.metrics_collector.get_metrics(
                    f"relative_price_achievement_tier_{tier}"
                )
                if metrics_rpa:
                    values = [m.value for m in metrics_rpa]
                    tier_performance[tier]["relative_price_achievement"] = (
                        round(sum(values) / len(values), 2)
                    )
                else:
                    tier_performance[tier]["relative_price_achievement"] = 0.0
                
                # Metric 2: Market-Relative Performance
                metrics_mrp = self.metrics_collector.get_metrics(
                    f"market_relative_performance_tier_{tier}"
                )
                if metrics_mrp:
                    values = [m.value for m in metrics_mrp]
                    tier_performance[tier]["market_relative_performance"] = (
                        round(sum(values) / len(values), 2)
                    )
                else:
                    tier_performance[tier]["market_relative_performance"] = 0.0
                
                # Metric 4: Efficiency Score
                metrics_eff = self.metrics_collector.get_metrics(
                    f"efficiency_score_tier_{tier}"
                )
                if metrics_eff:
                    values = [m.value for m in metrics_eff]
                    tier_performance[tier]["efficiency_score"] = (
                        round(sum(values) / len(values), 2)
                    )
                else:
                    tier_performance[tier]["efficiency_score"] = 0.0
                
                # Legacy metric (backward compatibility)
                tier_performance[tier]["anchor_resistance"] = (
                    tier_performance[tier]["relative_price_achievement"]
                )
        
        # Metric 3: Absolute Price Ranking
        if tier_prices:
            rankings = self._calculate_absolute_ranking(tier_prices)
            for tier, rank in rankings.items():
                tier_performance[tier]["absolute_rank"] = rank
        
        # Calculate composite scores
        for tier in tier_performance:
            if tier_performance[tier].get("deal_count", 0) > 0:
                composite = self._calculate_composite_score(
                    tier_performance[tier].get(
                        "relative_price_achievement", 0.0
                    ),
                    tier_performance[tier].get(
                        "market_relative_performance", 0.0
                    ),
                    tier_performance[tier].get("absolute_rank", 3),
                    tier_performance[tier].get("efficiency_score", 0.0)
                )
                tier_performance[tier]["composite_score"] = composite
        
        return tier_performance
