"""
Base classes for stress test scenarios.

Implements Strategy and Template Method patterns for scenario execution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime


class ScenarioPhase(Enum):
    """Execution phases for stress test scenarios."""
    SETUP = "setup"
    PRE_NEGOTIATION = "pre_negotiation"
    NEGOTIATION = "negotiation"
    POST_NEGOTIATION = "post_negotiation"
    ANALYSIS = "analysis"
    COMPLETE = "complete"


@dataclass
class ScenarioConfig:
    """
    Configuration for a stress test scenario.
    
    Attributes:
        scenario_id: Unique identifier (e.g., "adversarial_buyer")
        name: Human-readable name
        description: Scenario purpose
        max_rounds: Maximum negotiation rounds
        market_avg: Base market average price
        buyer_configs: Buyer-specific configurations
        seller_configs: Seller-specific configurations
        metrics_config: Metrics collection settings
        parameters: Scenario-specific parameters
    """
    scenario_id: str
    name: str
    description: str
    max_rounds: int = 10
    market_avg: float = 150.0
    buyer_configs: Dict[str, Any] = field(default_factory=dict)
    seller_configs: Dict[str, Any] = field(default_factory=dict)
    metrics_config: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.scenario_id:
            raise ValueError("scenario_id is required")
        if self.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        if self.market_avg <= 0:
            raise ValueError("market_avg must be > 0")


@dataclass
class ScenarioResult:
    """
    Results from a completed scenario execution.
    
    Attributes:
        scenario_id: Scenario identifier
        phase: Final execution phase
        metrics: Collected metrics
        tier_performance: Performance by seller tier
        deals: Completed deals
        events: Event log
        started_at: Execution start time
        completed_at: Execution completion time
        success: Whether scenario completed successfully
        error: Error message if failed
    """
    scenario_id: str
    phase: ScenarioPhase
    metrics: Dict[str, Any] = field(default_factory=dict)
    tier_performance: Dict[int, Dict[str, float]] = field(default_factory=dict)
    deals: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    success: bool = False
    error: Optional[str] = None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate execution duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BaseScenario(ABC):
    """
    Abstract base class for stress test scenarios.
    
    Implements Template Method pattern:
    - setup() -> pre_negotiation() -> run_negotiation() -> post_negotiation() -> analyze()
    
    Subclasses must implement:
    - modify_buyer_behavior()
    - modify_seller_behavior()
    - calculate_scenario_metrics()
    """
    
    def __init__(self, config: ScenarioConfig):
        """
        Initialize scenario with configuration.
        
        Args:
            config: Scenario configuration
        """
        self.config = config
        self.phase = ScenarioPhase.SETUP
        self.result = ScenarioResult(
            scenario_id=config.scenario_id,
            phase=self.phase,
            started_at=datetime.utcnow()
        )
        self._events: List[Dict[str, Any]] = []
        self._metrics: Dict[str, Any] = {}
    
    async def execute(self) -> ScenarioResult:
        """
        Execute scenario using Template Method pattern.
        
        Returns:
            ScenarioResult with metrics and performance data
        """
        try:
            # Phase 1: Setup
            self._transition_phase(ScenarioPhase.SETUP)
            await self.setup()
            
            # Phase 2: Pre-negotiation modifications
            self._transition_phase(ScenarioPhase.PRE_NEGOTIATION)
            await self.pre_negotiation()
            
            # Phase 3: Run negotiation
            self._transition_phase(ScenarioPhase.NEGOTIATION)
            await self.run_negotiation()
            
            # Phase 4: Post-negotiation processing
            self._transition_phase(ScenarioPhase.POST_NEGOTIATION)
            await self.post_negotiation()
            
            # Phase 5: Analysis
            self._transition_phase(ScenarioPhase.ANALYSIS)
            await self.analyze()
            
            # Complete
            self._transition_phase(ScenarioPhase.COMPLETE)
            self.result.success = True
            self.result.completed_at = datetime.utcnow()
            
        except Exception as e:
            self.result.success = False
            self.result.error = str(e)
            self.result.completed_at = datetime.utcnow()
            raise
        
        return self.result
    
    def _transition_phase(self, new_phase: ScenarioPhase):
        """Transition to a new execution phase."""
        self.phase = new_phase
        self.result.phase = new_phase
        self._log_event("phase_transition", {"phase": new_phase.value})
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event during scenario execution."""
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "phase": self.phase.value,
            "data": data
        }
        self._events.append(event)
        self.result.events = self._events
    
    def _record_metric(self, metric_name: str, value: Any):
        """Record a metric value."""
        self._metrics[metric_name] = value
        self.result.metrics = self._metrics
    
    # Template Method steps (can be overridden)
    
    async def setup(self):
        """
        Phase 1: Setup scenario-specific configurations.
        Override to add custom setup logic.
        """
        self._log_event("setup_start", {"config": self.config.scenario_id})
    
    async def pre_negotiation(self):
        """
        Phase 2: Apply pre-negotiation modifications.
        Override to modify buyer/seller behaviors before negotiation.
        """
        buyer_mods = await self.modify_buyer_behavior()
        seller_mods = await self.modify_seller_behavior()
        self._log_event("pre_negotiation", {
            "buyer_modifications": buyer_mods,
            "seller_modifications": seller_mods
        })
    
    @abstractmethod
    async def modify_buyer_behavior(self) -> Dict[str, Any]:
        """
        Modify buyer behavior for this scenario.
        
        Returns:
            Dictionary describing buyer behavior modifications
        """
        pass
    
    @abstractmethod
    async def modify_seller_behavior(self) -> Dict[str, Any]:
        """
        Modify seller behavior for this scenario.
        
        Returns:
            Dictionary describing seller behavior modifications
        """
        pass
    
    @abstractmethod
    async def run_negotiation(self):
        """
        Phase 3: Execute the negotiation.
        Must be implemented by subclasses to run market simulation.
        """
        pass
    
    async def post_negotiation(self):
        """
        Phase 4: Process negotiation results.
        Override to add custom post-processing.
        """
        self._log_event("post_negotiation", {"deals_count": len(self.result.deals)})
    
    async def analyze(self):
        """
        Phase 5: Analyze results and calculate metrics.
        Override to add custom analysis logic.
        """
        metrics = await self.calculate_scenario_metrics()
        tier_performance = await self.calculate_tier_performance()
        
        self.result.metrics.update(metrics)
        self.result.tier_performance = tier_performance
        
        self._log_event("analysis_complete", {
            "metrics_count": len(metrics),
            "tiers_analyzed": list(tier_performance.keys())
        })
    
    @abstractmethod
    async def calculate_scenario_metrics(self) -> Dict[str, Any]:
        """
        Calculate scenario-specific metrics.
        
        Returns:
            Dictionary of metric name -> value
        """
        pass
    
    async def calculate_tier_performance(self) -> Dict[int, Dict[str, float]]:
        """
        Calculate performance metrics by seller tier.
        
        Returns:
            Dictionary mapping tier (1/2/3) to performance metrics
        """
        # Default implementation - can be overridden
        tier_metrics = {1: {}, 2: {}, 3: {}}
        
        for deal in self.result.deals:
            tier = deal.get("seller_tier", 0)
            if tier in tier_metrics:
                if "deal_count" not in tier_metrics[tier]:
                    tier_metrics[tier]["deal_count"] = 0
                    tier_metrics[tier]["total_price"] = 0.0
                
                tier_metrics[tier]["deal_count"] += 1
                tier_metrics[tier]["total_price"] += deal.get("final_price", 0.0)
        
        # Calculate averages
        for tier in tier_metrics:
            if tier_metrics[tier].get("deal_count", 0) > 0:
                tier_metrics[tier]["avg_price"] = (
                    tier_metrics[tier]["total_price"] / tier_metrics[tier]["deal_count"]
                )
        
        return tier_metrics
    
    def get_config_parameter(self, key: str, default: Any = None) -> Any:
        """
        Get a scenario-specific parameter from config.
        
        Args:
            key: Parameter key
            default: Default value if key not found
            
        Returns:
            Parameter value or default
        """
        return self.config.parameters.get(key, default)
