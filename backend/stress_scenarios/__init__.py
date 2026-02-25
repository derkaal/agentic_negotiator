"""
Stress Test Scenarios Module

Provides adversarial testing scenarios for the MBMPMS 3x3 negotiation system.
Tests differentiation between Solo LLM, Math Geek, and Probing Strategist seller tiers.
"""

from .base import BaseScenario, ScenarioConfig, ScenarioPhase
from .metrics import MetricsCollector, MetricsAggregator
from .runner import ScenarioRunner

__all__ = [
    "BaseScenario",
    "ScenarioConfig",
    "ScenarioPhase",
    "MetricsCollector",
    "MetricsAggregator",
    "ScenarioRunner",
]
