"""
Information Asymmetry Scenario (Scenario 2).

Tests seller ability to:
1. Detect hidden information
2. Extract information through probing
3. Capture price premiums from discovered asymmetries

Hypothesis: Probing Strategist (Tier 3) extracts significantly more
information than Solo LLM (Tier 1) or Math Geek (Tier 2).
"""

from typing import Any, AsyncIterator, Dict, List, Optional
import sys
import os
import random

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from stress_scenarios.base import BaseScenario, ScenarioConfig
from stress_scenarios.metrics import MetricsCollector
from stress_scenarios.utils.asymmetry_types import (
    AsymmetryType,
    create_asymmetry
)
from stress_scenarios.utils.information_extraction import (
    InformationExtractor,
    Discovery
)
from market_tasks import run_market_3x3


class AsymmetryMetricsCollector:
    """
    Collects and aggregates metrics for information asymmetry scenario
    """
    
    def __init__(self):
        """Initialize metrics collector"""
        # Extraction rates by tier
        self._extraction_rates: Dict[int, List[float]] = {
            1: [], 2: [], 3: []
        }
        
        # Premium captured by tier
        self._premium_captured: Dict[int, List[float]] = {
            1: [], 2: [], 3: []
        }
        
        # Asymmetry closure rates by tier
        self._closure_rates: Dict[int, List[bool]] = {
            1: [], 2: [], 3: []
        }
        
        # Discovery details
        self._discoveries: List[Discovery] = []
    
    def record_extraction(self, tier: int, rate: float):
        """
        Record extraction rate for tier
        
        Args:
            tier: Seller tier (1, 2, or 3)
            rate: Extraction rate (0.0 to 1.0)
        """
        if tier in self._extraction_rates:
            self._extraction_rates[tier].append(rate)
    
    def record_premium(self, tier: int, premium: float):
        """
        Record premium captured for tier
        
        Args:
            tier: Seller tier
            premium: Premium percentage captured
        """
        if tier in self._premium_captured:
            self._premium_captured[tier].append(premium)
    
    def record_closure(self, tier: int, closed: bool):
        """
        Record asymmetry closure for tier
        
        Args:
            tier: Seller tier
            closed: Whether asymmetry was closed
        """
        if tier in self._closure_rates:
            self._closure_rates[tier].append(closed)
    
    def record_discovery(self, discovery: Discovery):
        """Record a discovery event"""
        self._discoveries.append(discovery)
    
    def calculate_tier_metrics(self, tier: int) -> Dict[str, float]:
        """
        Calculate aggregated metrics for tier
        
        Args:
            tier: Seller tier
            
        Returns:
            Dict with mean extraction rate, premium, and closure rate
        """
        extraction_rates = self._extraction_rates.get(tier, [])
        premiums = self._premium_captured.get(tier, [])
        closures = self._closure_rates.get(tier, [])
        
        return {
            "extraction_rate": (
                sum(extraction_rates) / len(extraction_rates)
                if extraction_rates else 0.0
            ),
            "premium_captured": (
                sum(premiums) / len(premiums)
                if premiums else 0.0
            ),
            "closure_rate": (
                sum(closures) / len(closures)
                if closures else 0.0
            ),
            "sample_size": len(extraction_rates)
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all collected metrics"""
        return {
            "tier_1": self.calculate_tier_metrics(1),
            "tier_2": self.calculate_tier_metrics(2),
            "tier_3": self.calculate_tier_metrics(3),
            "total_discoveries": len(self._discoveries)
        }


class InformationAsymmetryScenario(BaseScenario):
    """
    Scenario 2: Information Asymmetry.
    
    Tests seller ability to extract hidden information from buyers
    and capture value from discovered asymmetries.
    """
    
    def __init__(self, config: ScenarioConfig):
        """
        Initialize information asymmetry scenario.
        
        Args:
            config: Scenario configuration
        """
        super().__init__(config)
        
        # Initialize metrics collectors
        self.metrics_collector = MetricsCollector(config.scenario_id)
        self.asymmetry_metrics = AsymmetryMetricsCollector()
        
        # Initialize information extractor
        self.information_extractor = InformationExtractor()
        
        # Track buyer asymmetries
        # Format: {buyer_id: {asymmetry_type: AsymmetryType}}
        self._buyer_asymmetries: Dict[str, Dict[str, AsymmetryType]] = {}
        
        # Track deals
        self._deals: List[Dict[str, Any]] = []
        
        # Initialize asymmetries
        self._initialize_asymmetries()
    
    def _initialize_asymmetries(self):
        """
        Create asymmetries for each buyer.
        
        GUARANTEED: Each buyer gets at least 1 asymmetry to ensure
        meaningful data collection.
        """
        # Get configuration
        asymmetry_probs = self.config.parameters.get(
            "asymmetry_probability", {}
        )
        urgency_config = self.config.parameters.get("urgency_config", {})
        budget_config = self.config.parameters.get("budget_config", {})
        disclosure_prob = self.config.parameters.get(
            "disclosure_probability", 0.7
        )
        
        # Create asymmetries for 3 buyers
        buyer_ids = ["tough", "emergency", "value"]  # Match market_tasks.py
        
        # Define asymmetry types with their probabilities
        asymmetry_types = [
            ("urgency", asymmetry_probs.get("urgency", 0.8)),
            ("budget", asymmetry_probs.get("budget", 0.8)),
            ("alternatives", asymmetry_probs.get("alternatives", 0.5)),
            ("quality", asymmetry_probs.get("quality", 0.5))
        ]
        
        for buyer_id in buyer_ids:
            self._buyer_asymmetries[buyer_id] = {}
            
            # Try to add each asymmetry type based on probability
            for asym_type, prob in asymmetry_types:
                if random.random() < prob:
                    if asym_type == "urgency":
                        deadline_range = urgency_config.get(
                            "deadline_range", [3, 7]
                        )
                        premium_range = urgency_config.get(
                            "premium_range", [0.05, 0.15]
                        )
                        self._buyer_asymmetries[buyer_id]["urgency"] = (
                            create_asymmetry(
                                "urgency",
                                deadline=random.randint(*deadline_range),
                                max_premium=random.uniform(*premium_range),
                                disclosure_probability=disclosure_prob
                            )
                        )
                    
                    elif asym_type == "budget":
                        gap_range = budget_config.get(
                            "gap_range", [0.05, 0.15]
                        )
                        base_budget = self.config.market_avg
                        gap = random.uniform(*gap_range) * base_budget
                        self._buyer_asymmetries[buyer_id]["budget"] = (
                            create_asymmetry(
                                "budget",
                                claimed_max=base_budget,
                                actual_max=base_budget + gap,
                                disclosure_probability=disclosure_prob
                            )
                        )
                    
                    elif asym_type == "alternatives":
                        self._buyer_asymmetries[buyer_id]["alternatives"] = (
                            create_asymmetry(
                                "alternatives",
                                claimed_alternative=(
                                    self.config.market_avg * 0.9
                                ),
                                actual_alternative=(
                                    self.config.market_avg * 1.05
                                ),
                                disclosure_probability=disclosure_prob * 0.5
                            )
                        )
                    
                    elif asym_type == "quality":
                        self._buyer_asymmetries[buyer_id]["quality"] = (
                            create_asymmetry(
                                "quality",
                                stated_preference="price",
                                actual_preference="quality",
                                quality_premium=0.15,
                                disclosure_probability=disclosure_prob
                            )
                        )
            
            # GUARANTEE: If no asymmetries were added, force add budget
            if not self._buyer_asymmetries[buyer_id]:
                gap_range = budget_config.get("gap_range", [0.05, 0.15])
                base_budget = self.config.market_avg
                gap = random.uniform(*gap_range) * base_budget
                self._buyer_asymmetries[buyer_id]["budget"] = (
                    create_asymmetry(
                        "budget",
                        claimed_max=base_budget,
                        actual_max=base_budget + gap,
                        disclosure_probability=disclosure_prob
                    )
                )
                print(f"DEBUG: Forced budget asymmetry for {buyer_id}")
        
        # Debug: Print what asymmetries were created
        print("DEBUG: Asymmetries initialized:")
        for buyer_id, asyms in self._buyer_asymmetries.items():
            print(f"  {buyer_id}: {list(asyms.keys())}")
    
    async def modify_buyer_behavior(self) -> Dict[str, Any]:
        """
        Modify buyer behavior to include hidden information.
        
        Returns:
            Dictionary describing modifications
        """
        modifications = {
            "asymmetries_enabled": True,
            "buyers_with_asymmetries": len(self._buyer_asymmetries),
            "total_asymmetries": sum(
                len(asym) for asym in self._buyer_asymmetries.values()
            )
        }
        
        self._log_event("buyer_modifications", modifications)
        return modifications
    
    async def modify_seller_behavior(self) -> Dict[str, Any]:
        """
        No seller modifications needed (testing their extraction ability).
        
        Returns:
            Empty dictionary
        """
        return {}
    
    async def run_negotiation(self):
        """
        Run market simulation with information asymmetries.
        
        This wraps run_market_3x3() and observes the results.
        """
        self._log_event("negotiation_start", {
            "max_rounds": self.config.max_rounds,
            "scenario": "information_asymmetry",
            "asymmetries": {
                buyer_id: list(asyms.keys())
                for buyer_id, asyms in self._buyer_asymmetries.items()
            }
        })
        
        self.metrics_collector.start_timer("negotiation")
        
        # Run market simulation
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
        
        # Debug: Log all events to trace flow
        if event_type in ["seller_message", "deal_closed"]:
            print(f"DEBUG: Processing event type='{event_type}' with keys: {list(event.keys())}")
        
        if event_type == "market_start":
            self._log_event("market_started", {
                "buyers": len(event.get("buyers", [])),
                "sellers": len(event.get("sellers", []))
            })
        
        elif event_type == "seller_message":
            print(f"DEBUG: seller_message event - seller_tier={event.get('seller_tier')}, buyer_id={event.get('buyer_id')}")
            await self._handle_seller_message(event)
        
        elif event_type == "market_round":
            round_num = event.get("round", 0)
            await self._process_round(round_num, event)
        
        elif event_type == "deal_closed":
            print(f"DEBUG: deal_closed event - buyer_id={event.get('buyer_id')}, seller_id={event.get('seller_id')}, deal_price={event.get('deal_price')}")
            await self._handle_deal_closed(event)
        
        elif event_type == "market_end":
            self._process_market_end(event)
    
    async def _handle_seller_message(self, event: Dict[str, Any]):
        """
        Handle seller message event and detect probing.
        
        Args:
            event: {
                "seller_id": "automax",
                "seller_tier": 1,
                "buyer_id": "tough",
                "message": "Boulware Strategy: ...",
                "round": 2,
                "current_ask": 165.0,
                "current_offer": 135.0
            }
        """
        seller_tier = event.get("seller_tier")
        buyer_id = event.get("buyer_id")
        message = event.get("message", "")
        round_num = event.get("round")
        
        # Debug: Log message content for Tier 3
        if seller_tier == 3:
            print(f"DEBUG T3 message (round {round_num}): '{message[:100]}'")
        
        # Get buyer asymmetries
        buyer_asymmetries = self._buyer_asymmetries.get(buyer_id, {})
        
        if not buyer_asymmetries:
            print(f"DEBUG: No asymmetries for buyer_id='{buyer_id}'")
            return
        
        # Detect probe in message
        probe_type = self.information_extractor.probe_detector.detect(message)
        
        if probe_type:
            print(f"DEBUG: PROBE DETECTED! Type={probe_type}, Tier={seller_tier}")
        
        if probe_type:
            # Check if buyer has this asymmetry
            asymmetry = buyer_asymmetries.get(probe_type)
            
            if asymmetry:
                # Determine if buyer reveals information
                should_reveal = asymmetry.should_reveal_if_asked()
                
                print(f"DEBUG: Asymmetry found! Type={probe_type}, Will reveal={should_reveal}")
                
                if should_reveal:
                    asymmetry.mark_revealed(round_num)
                    
                    # Create discovery
                    discovery = Discovery(
                        asymmetry_type=probe_type,
                        discovered_at_round=round_num,
                        probe_message=message,
                        buyer_response="Revealed",
                        revealed_value=asymmetry.get_hidden_value()
                    )
                    
                    self.information_extractor.discoveries.append(discovery)
                    self.asymmetry_metrics.record_discovery(discovery)
                    
                    # Record extraction for this tier
                    self.asymmetry_metrics.record_extraction(seller_tier, 1.0)
                    
                    print(f"DEBUG: ✅ INFORMATION EXTRACTED! Tier {seller_tier} discovered {probe_type}")
                    
                    self._log_event("information_extracted", {
                        "round": round_num,
                        "buyer": buyer_id,
                        "seller_tier": seller_tier,
                        "asymmetry_type": probe_type,
                        "revealed_value": asymmetry.get_hidden_value()
                    })
                else:
                    # Probe attempted but not revealed
                    self.asymmetry_metrics.record_extraction(seller_tier, 0.0)
                    print(f"DEBUG: ❌ Probe failed - buyer didn't reveal")
            else:
                print(f"DEBUG: Probe type '{probe_type}' not in buyer's asymmetries: {list(buyer_asymmetries.keys())}")
    
    async def _handle_deal_closed(self, event: Dict[str, Any]):
        """
        Handle deal closed event and calculate premium captured.
        
        Args:
            event: {
                "buyer_id": "tough",
                "seller_id": "automax",
                "deal_price": 158.0,
                "round": 2,
                "seller_tier": 1
            }
        """
        buyer_id = event.get("buyer_id")
        seller_id = event.get("seller_id")
        deal_price = event.get("deal_price")
        round_num = event.get("round")
        seller_tier = event.get("seller_tier", self._extract_tier(seller_id))
        
        if not seller_tier:
            return
        
        # Get buyer's asymmetries
        buyer_asymmetries = self._buyer_asymmetries.get(buyer_id, {})
        
        # Calculate baseline price (market average + 5%)
        baseline_price = self.config.market_avg * 1.05
        
        # Calculate maximum extractable premium from revealed asymmetries
        max_premium = 0.0
        
        if "urgency" in buyer_asymmetries:
            urgency = buyer_asymmetries["urgency"]
            if urgency.revealed:
                # Urgency can add 5-15% premium
                max_premium += self.config.market_avg * 0.10
        
        if "budget" in buyer_asymmetries:
            budget = buyer_asymmetries["budget"]
            if budget.revealed:
                # Hidden budget gap
                hidden_value = budget.get_hidden_value()
                gap = hidden_value.get("actual_max", 0) - hidden_value.get("claimed_max", 0)
                max_premium += gap
        
        # Calculate actual premium captured
        actual_premium = deal_price - baseline_price
        
        # Calculate premium capture rate
        if max_premium > 0:
            premium_rate = min(100.0, max(0.0, (actual_premium / max_premium) * 100))
        else:
            premium_rate = 0.0
        
        # Record metrics
        self.asymmetry_metrics.record_premium(seller_tier, premium_rate)
        self.asymmetry_metrics.record_closure(seller_tier, True)
        
        # Store deal for analysis
        self._deals.append({
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "seller_tier": seller_tier,
            "deal_price": deal_price,
            "baseline_price": baseline_price,
            "max_premium": max_premium,
            "premium_captured": premium_rate,
            "asymmetries_discovered": [
                k for k, v in buyer_asymmetries.items() if v.revealed
            ],
            "round": round_num
        })
        
        self._log_event("deal_processed", {
            "buyer": buyer_id,
            "seller": seller_id,
            "tier": seller_tier,
            "premium_rate": premium_rate,
            "asymmetries_revealed": len([v for v in buyer_asymmetries.values() if v.revealed])
        })
    
    async def _process_round(self, round_num: int, event: Dict[str, Any]):
        """
        Process a negotiation round and detect information extraction.
        
        Args:
            round_num: Round number
            event: Round event data
        """
        # Note: Message processing now happens via seller_message events
        # This method is kept for compatibility but most logic moved to
        # _handle_seller_message
        pass
    
    def _simulate_seller_message(self, round_num: int) -> str:
        """
        Simulate seller message for testing.
        
        In production, this would extract actual seller messages.
        
        Args:
            round_num: Current round
            
        Returns:
            Simulated seller message
        """
        # Tier 3 (Probing) asks strategic questions
        # Tier 1/2 focus on price
        
        probe_messages = [
            "What's your timeline for this purchase?",
            "Do you have a deadline you're working with?",
            "What's your maximum budget for this?",
            "Are you comparing other offers?",
            "What features matter most to you?",
            "Is quality or price your priority?"
        ]
        
        # Tier 3 probes more frequently
        if random.random() < 0.7:  # 70% probe rate for Tier 3
            return random.choice(probe_messages)
        
        return "Here's my offer for this round."
    
    def _process_deal(self, event: Dict[str, Any]):
        """
        Process a closed deal.
        
        Args:
            event: Deal event data
        """
        deal = {
            "buyer": event.get("buyer"),
            "seller": event.get("seller"),
            "price": event.get("price"),
            "round": event.get("round")
        }
        
        self._deals.append(deal)
        
        # Calculate premium captured
        market_avg = self.config.market_avg
        premium = (deal["price"] - market_avg) / market_avg
        
        # Determine seller tier (from seller ID)
        seller_tier = self._extract_tier(deal["seller"])
        
        # Record metrics
        if seller_tier:
            self.asymmetry_metrics.record_premium(seller_tier, premium)
            
            # Check if asymmetry was closed
            buyer_id = deal["buyer"]
            buyer_asyms = self._buyer_asymmetries.get(buyer_id, {})
            closed = any(asym.revealed for asym in buyer_asyms.values())
            self.asymmetry_metrics.record_closure(seller_tier, closed)
        
        self._log_event("deal_processed", {
            "deal": deal,
            "premium": premium,
            "tier": seller_tier
        })
    
    def _extract_tier(self, seller_id: str) -> Optional[int]:
        """
        Extract tier number from seller ID.
        
        Args:
            seller_id: Seller identifier
            
        Returns:
            Tier number (1, 2, or 3) or None
        """
        if not seller_id:
            return None
            
        seller_id_lower = seller_id.lower()
        if "tier_1" in seller_id_lower or "solo" in seller_id_lower:
            return 1
        elif "tier_2" in seller_id_lower or "math" in seller_id_lower:
            return 2
        elif "tier_3" in seller_id_lower or "probing" in seller_id_lower:
            return 3
        return None
    
    def _process_market_end(self, event: Dict[str, Any]):
        """
        Process market end event.
        
        Args:
            event: Market end event data
        """
        # DON'T overwrite extraction rates - they're already recorded
        # during _handle_seller_message when probes succeed/fail
        
        # Debug: Print final extraction counts
        print("\nDEBUG: Final extraction data:")
        for tier in [1, 2, 3]:
            metrics = self.asymmetry_metrics.calculate_tier_metrics(tier)
            print(f"  Tier {tier}: {len(self.asymmetry_metrics._extraction_rates[tier])} extractions recorded")
            print(f"    Extraction rate: {metrics['extraction_rate']*100:.2f}%")
        
        self._log_event("market_ended", {
            "total_deals": len(self._deals),
            "extraction_summary": (
                self.information_extractor.get_discovery_summary()
            )
        })
    
    def _calculate_tier_extraction_rate(self, tier: int) -> float:
        """
        Calculate extraction rate for a specific tier.
        
        Args:
            tier: Seller tier
            
        Returns:
            Extraction rate (0.0 to 1.0)
        """
        # Count total asymmetries
        total_asymmetries = sum(
            len(asyms) for asyms in self._buyer_asymmetries.values()
        )
        
        if total_asymmetries == 0:
            return 0.0
        
        # Count discoveries (simplified - in production, track by tier)
        discoveries = len(self.information_extractor.discoveries)
        
        # Simulate tier-specific extraction rates
        # Tier 1: 20-30%, Tier 2: 0-10%, Tier 3: 70-85%
        if tier == 1:
            base_rate = 0.25
        elif tier == 2:
            base_rate = 0.05
        else:  # tier == 3
            base_rate = 0.75
        
        # Add some randomness
        return base_rate + random.uniform(-0.05, 0.05)
    
    async def calculate_scenario_metrics(self) -> Dict[str, Any]:
        """
        Calculate scenario-specific metrics.
        
        Returns:
            Dict with scenario metrics including extraction rates,
            premiums, and closure rates
        """
        return {
            "scenario_type": "information_asymmetry",
            "total_asymmetries": sum(
                len(asyms) for asyms in self._buyer_asymmetries.values()
            ),
            "total_discoveries": len(self.information_extractor.discoveries),
            "discovery_summary": (
                self.information_extractor.get_discovery_summary()
            ),
            "asymmetry_metrics": self.asymmetry_metrics.get_all_metrics(),
            "deals_closed": len(self._deals)
        }
    
    async def calculate_tier_performance(self) -> Dict[int, Dict[str, float]]:
        """
        Override base class to use asymmetry-specific metrics.
        
        Returns:
            Dict mapping tier -> performance metrics
        """
        return self.calculate_tier_scores({})
    
    def calculate_tier_scores(
        self,
        results: Dict[str, Any]
    ) -> Dict[int, Dict[str, float]]:
        """
        Calculate multi-dimensional scores per tier.
        
        Args:
            results: Negotiation results (unused, kept for compatibility)
            
        Returns:
            Dict mapping tier -> metrics dict
        """
        tier_scores = {}
        
        for tier in [1, 2, 3]:
            metrics = self.asymmetry_metrics.calculate_tier_metrics(tier)
            
            # Calculate composite score
            # Weighted: 40% extraction, 30% premium, 30% closure
            composite = (
                0.4 * metrics["extraction_rate"] +
                0.3 * metrics["premium_captured"] +
                0.3 * metrics["closure_rate"]
            )
            
            tier_scores[tier] = {
                "extraction_rate": metrics["extraction_rate"] * 100,
                "premium_captured": metrics["premium_captured"] * 100,
                "closure_rate": metrics["closure_rate"] * 100,
                "composite_score": composite * 100
            }
        
        return tier_scores
