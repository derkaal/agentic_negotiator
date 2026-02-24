"""
Metrics collection and aggregation for stress test scenarios.

Implements Observer pattern for real-time metrics collection.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import statistics


@dataclass
class MetricValue:
    """
    A single metric measurement.
    
    Attributes:
        name: Metric name
        value: Metric value
        timestamp: When metric was recorded
        metadata: Additional context
    """
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects metrics during scenario execution.
    
    Implements Observer pattern - observes negotiation events and
    records relevant metrics.
    """
    
    def __init__(self, scenario_id: str):
        """
        Initialize metrics collector.
        
        Args:
            scenario_id: Scenario identifier
        """
        self.scenario_id = scenario_id
        self._metrics: List[MetricValue] = []
        self._counters: Dict[str, int] = {}
        self._timers: Dict[str, datetime] = {}
    
    def record(
        self,
        name: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            metadata: Optional metadata
        """
        metric = MetricValue(
            name=name,
            value=value,
            metadata=metadata or {}
        )
        self._metrics.append(metric)
    
    def increment(self, counter_name: str, amount: int = 1):
        """
        Increment a counter.
        
        Args:
            counter_name: Counter name
            amount: Amount to increment
        """
        if counter_name not in self._counters:
            self._counters[counter_name] = 0
        self._counters[counter_name] += amount
    
    def get_counter(self, counter_name: str) -> int:
        """Get current counter value."""
        return self._counters.get(counter_name, 0)
    
    def start_timer(self, timer_name: str):
        """Start a named timer."""
        self._timers[timer_name] = datetime.utcnow()
    
    def stop_timer(self, timer_name: str) -> Optional[float]:
        """
        Stop a timer and return elapsed seconds.
        
        Args:
            timer_name: Timer name
            
        Returns:
            Elapsed seconds or None if timer not started
        """
        if timer_name not in self._timers:
            return None
        
        start_time = self._timers[timer_name]
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        # Record as metric
        self.record(f"{timer_name}_duration", elapsed)
        
        # Clean up timer
        del self._timers[timer_name]
        
        return elapsed
    
    def get_metrics(
        self,
        name_filter: Optional[str] = None
    ) -> List[MetricValue]:
        """
        Get collected metrics, optionally filtered by name.
        
        Args:
            name_filter: Optional metric name to filter by
            
        Returns:
            List of metric values
        """
        if name_filter:
            return [m for m in self._metrics if m.name == name_filter]
        return self._metrics.copy()
    
    def get_all_counters(self) -> Dict[str, int]:
        """Get all counter values."""
        return self._counters.copy()
    
    def clear(self):
        """Clear all collected metrics and counters."""
        self._metrics.clear()
        self._counters.clear()
        self._timers.clear()


class MetricsAggregator:
    """
    Aggregates metrics across multiple executions or tiers.
    
    Calculates statistics like mean, median, min, max, std dev.
    """
    
    def __init__(self):
        """Initialize metrics aggregator."""
        self._data: Dict[str, List[float]] = {}
    
    def add_value(self, metric_name: str, value: float):
        """
        Add a value to a metric.
        
        Args:
            metric_name: Metric name
            value: Value to add
        """
        if metric_name not in self._data:
            self._data[metric_name] = []
        self._data[metric_name].append(value)
    
    def add_metrics(self, metrics: List[MetricValue]):
        """
        Add multiple metrics.
        
        Args:
            metrics: List of metric values
        """
        for metric in metrics:
            self.add_value(metric.name, metric.value)
    
    def get_statistics(
        self,
        metric_name: str
    ) -> Optional[Dict[str, float]]:
        """
        Calculate statistics for a metric.
        
        Args:
            metric_name: Metric name
            
        Returns:
            Dictionary with mean, median, min, max, std_dev, count
            or None if metric not found
        """
        if metric_name not in self._data:
            return None
        
        values = self._data[metric_name]
        if not values:
            return None
        
        stats = {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
        }
        
        # Standard deviation requires at least 2 values
        if len(values) >= 2:
            stats["std_dev"] = statistics.stdev(values)
        else:
            stats["std_dev"] = 0.0
        
        return stats
    
    def get_all_statistics(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics for all metrics.
        
        Returns:
            Dictionary mapping metric name to statistics
        """
        return {
            name: self.get_statistics(name)
            for name in self._data.keys()
            if self.get_statistics(name) is not None
        }
    
    def compare_tiers(
        self,
        metric_name: str,
        tier_values: Dict[int, List[float]]
    ) -> Dict[int, Dict[str, float]]:
        """
        Compare metric across seller tiers.
        
        Args:
            metric_name: Metric to compare
            tier_values: Dictionary mapping tier -> list of values
            
        Returns:
            Dictionary mapping tier -> statistics
        """
        tier_stats = {}
        
        for tier, values in tier_values.items():
            if not values:
                continue
            
            tier_stats[tier] = {
                "count": len(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
            
            if len(values) >= 2:
                tier_stats[tier]["std_dev"] = statistics.stdev(values)
            else:
                tier_stats[tier]["std_dev"] = 0.0
        
        return tier_stats
    
    def calculate_tier_ranking(
        self,
        metric_name: str,
        tier_values: Dict[int, List[float]],
        higher_is_better: bool = True
    ) -> List[int]:
        """
        Rank tiers by metric performance.
        
        Args:
            metric_name: Metric to rank by
            tier_values: Dictionary mapping tier -> list of values
            higher_is_better: Whether higher values are better
            
        Returns:
            List of tiers sorted by performance (best first)
        """
        tier_means = {}
        
        for tier, values in tier_values.items():
            if values:
                tier_means[tier] = statistics.mean(values)
        
        # Sort by mean value
        sorted_tiers = sorted(
            tier_means.keys(),
            key=lambda t: tier_means[t],
            reverse=higher_is_better
        )
        
        return sorted_tiers
    
    def clear(self):
        """Clear all aggregated data."""
        self._data.clear()


def calculate_anchor_resistance(
    seller_counter: float,
    buyer_lowball: float,
    market_avg: float
) -> float:
    """
    Calculate resistance to anchoring bias.
    
    Returns score 0-100 where:
    - 100 = no anchoring influence
    - 0 = fully anchored to lowball
    
    Args:
        seller_counter: Seller's counter-offer
        buyer_lowball: Buyer's lowball anchor
        market_avg: Market average price
        
    Returns:
        Resistance score (0-100)
    """
    expected = market_avg * 1.10  # Expected seller counter
    
    if expected <= buyer_lowball:
        return 100.0  # No room for anchoring
    
    anchor_pull = (expected - seller_counter) / (expected - buyer_lowball)
    resistance = 100 * (1 - max(0, min(1, anchor_pull)))
    
    return round(resistance, 2)


def calculate_deception_detection_score(
    deceptions_presented: int,
    deceptions_detected: int,
    deceptions_challenged: int
) -> Dict[str, float]:
    """
    Calculate deception detection metrics.
    
    Args:
        deceptions_presented: Total deceptions presented
        deceptions_detected: Number detected
        deceptions_challenged: Number challenged
        
    Returns:
        Dictionary with detection_rate, challenge_rate, overall_score
    """
    if deceptions_presented == 0:
        return {
            "detection_rate": 0.0,
            "challenge_rate": 0.0,
            "overall_score": 0.0
        }
    
    detection_rate = deceptions_detected / deceptions_presented
    challenge_rate = deceptions_challenged / deceptions_presented
    
    # Weighted score: 60% detection, 40% challenge
    overall_score = (detection_rate * 60 + challenge_rate * 40)
    
    return {
        "detection_rate": round(detection_rate, 3),
        "challenge_rate": round(challenge_rate, 3),
        "overall_score": round(overall_score, 2)
    }


def calculate_pressure_resistance(
    panic_concessions: int,
    floor_violations: int,
    urgency_signals: int
) -> float:
    """
    Calculate resistance to time pressure.
    
    Returns score 0-100 where:
    - 100 = no panic reactions
    - 0 = panicked on every signal
    
    Args:
        panic_concessions: Number of panic concessions
        floor_violations: Number of floor price violations
        urgency_signals: Total urgency signals presented
        
    Returns:
        Resistance score (0-100)
    """
    if urgency_signals == 0:
        return 100.0
    
    panic_rate = panic_concessions / urgency_signals
    violation_rate = floor_violations / urgency_signals
    
    resistance = 100 * (1 - panic_rate - violation_rate)
    
    return round(max(0, resistance), 2)
