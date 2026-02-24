"""
Scenario runner orchestrator.

Coordinates scenario execution and wraps run_market_3x3().
"""

from typing import Any, AsyncIterator, Dict, List, Optional
import asyncio

from .base import BaseScenario, ScenarioConfig, ScenarioResult
from .metrics import MetricsCollector, MetricsAggregator


class ScenarioRunner:
    """
    Orchestrates stress test scenario execution.
    
    Wraps run_market_3x3() without modifying it, using Decorator pattern
    to inject scenario-specific behaviors.
    """
    
    def __init__(self):
        """Initialize scenario runner."""
        self._scenarios: Dict[str, type] = {}
        self._results: List[ScenarioResult] = []
    
    def register_scenario(
        self,
        scenario_id: str,
        scenario_class: type
    ):
        """
        Register a scenario class.
        
        Args:
            scenario_id: Unique scenario identifier
            scenario_class: Scenario class (subclass of BaseScenario)
        """
        if not issubclass(scenario_class, BaseScenario):
            raise ValueError(
                f"{scenario_class} must be subclass of BaseScenario"
            )
        self._scenarios[scenario_id] = scenario_class
    
    def get_registered_scenarios(self) -> List[str]:
        """Get list of registered scenario IDs."""
        return list(self._scenarios.keys())
    
    async def run_scenario(
        self,
        scenario_id: str,
        config: Optional[ScenarioConfig] = None
    ) -> ScenarioResult:
        """
        Run a specific scenario.
        
        Args:
            scenario_id: Scenario to run
            config: Optional scenario configuration
            
        Returns:
            ScenarioResult with metrics and performance data
            
        Raises:
            ValueError: If scenario not registered
        """
        if scenario_id not in self._scenarios:
            raise ValueError(
                f"Scenario '{scenario_id}' not registered. "
                f"Available: {self.get_registered_scenarios()}"
            )
        
        # Create config if not provided
        if config is None:
            config = ScenarioConfig(
                scenario_id=scenario_id,
                name=scenario_id.replace("_", " ").title(),
                description=f"Stress test scenario: {scenario_id}"
            )
        
        # Instantiate scenario
        scenario_class = self._scenarios[scenario_id]
        scenario = scenario_class(config)
        
        # Execute scenario
        result = await scenario.execute()
        
        # Store result
        self._results.append(result)
        
        return result
    
    async def run_scenario_stream(
        self,
        scenario_id: str,
        config: Optional[ScenarioConfig] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Run scenario and stream events.
        
        Args:
            scenario_id: Scenario to run
            config: Optional scenario configuration
            
        Yields:
            Event dictionaries from scenario execution
            
        Raises:
            ValueError: If scenario not registered
        """
        if scenario_id not in self._scenarios:
            raise ValueError(
                f"Scenario '{scenario_id}' not registered. "
                f"Available: {self.get_registered_scenarios()}"
            )
        
        # Create config if not provided
        if config is None:
            config = ScenarioConfig(
                scenario_id=scenario_id,
                name=scenario_id.replace("_", " ").title(),
                description=f"Stress test scenario: {scenario_id}"
            )
        
        # Instantiate scenario
        scenario_class = self._scenarios[scenario_id]
        scenario = scenario_class(config)
        
        # Yield initial event
        yield {
            "type": "scenario_start",
            "scenario_id": scenario_id,
            "config": {
                "name": config.name,
                "description": config.description,
                "max_rounds": config.max_rounds
            }
        }
        
        # Execute scenario (this will be implemented by subclasses
        # to stream events from run_market_3x3)
        try:
            result = await scenario.execute()
            
            # Yield completion event
            yield {
                "type": "scenario_complete",
                "scenario_id": scenario_id,
                "success": result.success,
                "metrics": result.metrics,
                "tier_performance": result.tier_performance,
                "duration_seconds": result.duration_seconds
            }
            
            # Store result
            self._results.append(result)
            
        except Exception as e:
            yield {
                "type": "scenario_error",
                "scenario_id": scenario_id,
                "error": str(e)
            }
            raise
    
    def get_results(
        self,
        scenario_id: Optional[str] = None
    ) -> List[ScenarioResult]:
        """
        Get scenario results.
        
        Args:
            scenario_id: Optional filter by scenario ID
            
        Returns:
            List of scenario results
        """
        if scenario_id:
            return [r for r in self._results if r.scenario_id == scenario_id]
        return self._results.copy()
    
    def get_latest_result(
        self,
        scenario_id: str
    ) -> Optional[ScenarioResult]:
        """
        Get most recent result for a scenario.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            Latest result or None
        """
        results = self.get_results(scenario_id)
        if results:
            return results[-1]
        return None
    
    def compare_tiers(
        self,
        scenario_id: str,
        metric_name: str
    ) -> Dict[int, Dict[str, float]]:
        """
        Compare tier performance for a metric.
        
        Args:
            scenario_id: Scenario to analyze
            metric_name: Metric to compare
            
        Returns:
            Dictionary mapping tier -> statistics
        """
        results = self.get_results(scenario_id)
        if not results:
            return {}
        
        # Aggregate values by tier
        tier_values: Dict[int, List[float]] = {1: [], 2: [], 3: []}
        
        for result in results:
            for tier, perf in result.tier_performance.items():
                if metric_name in perf:
                    tier_values[tier].append(perf[metric_name])
        
        # Calculate statistics
        aggregator = MetricsAggregator()
        return aggregator.compare_tiers(metric_name, tier_values)
    
    def clear_results(self):
        """Clear all stored results."""
        self._results.clear()


# Global runner instance
_runner = ScenarioRunner()


def get_runner() -> ScenarioRunner:
    """Get the global scenario runner instance."""
    return _runner


def register_scenario(scenario_id: str, scenario_class: type):
    """
    Register a scenario with the global runner.
    
    Args:
        scenario_id: Unique scenario identifier
        scenario_class: Scenario class
    """
    _runner.register_scenario(scenario_id, scenario_class)
