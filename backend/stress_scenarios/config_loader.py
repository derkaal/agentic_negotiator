"""
Configuration loader for stress test scenarios.

Loads scenario configurations from YAML files.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from .base import ScenarioConfig


class ConfigLoader:
    """
    Loads scenario configurations from YAML files.
    
    Supports environment variable substitution and validation.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_dir: Directory containing config files
                       (defaults to stress_scenarios/configs/)
        """
        if config_dir is None:
            # Default to configs/ subdirectory
            current_dir = Path(__file__).parent
            config_dir = current_dir / "configs"
        
        self.config_dir = Path(config_dir)
    
    def load(self, scenario_id: str) -> ScenarioConfig:
        """
        Load configuration for a scenario.
        
        Args:
            scenario_id: Scenario identifier
            
        Returns:
            ScenarioConfig object
            
        Raises:
            FileNotFoundError: If config file not found
            ValueError: If config is invalid
        """
        config_path = self.config_dir / f"{scenario_id}.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}"
            )
        
        # Load YAML
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data:
            raise ValueError(f"Empty config file: {config_path}")
        
        # Substitute environment variables
        data = self._substitute_env_vars(data)
        
        # Create ScenarioConfig
        return self._create_config(scenario_id, data)
    
    def _substitute_env_vars(self, data: Any) -> Any:
        """
        Recursively substitute environment variables in config.
        
        Supports ${VAR_NAME} and ${VAR_NAME:default} syntax.
        
        Args:
            data: Config data (dict, list, or primitive)
            
        Returns:
            Data with environment variables substituted
        """
        if isinstance(data, dict):
            return {
                k: self._substitute_env_vars(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self._substitute_env_vars(item) for item in data]
        elif isinstance(data, str):
            return self._substitute_string(data)
        else:
            return data
    
    def _substitute_string(self, value: str) -> str:
        """
        Substitute environment variables in a string.
        
        Args:
            value: String potentially containing ${VAR} references
            
        Returns:
            String with variables substituted
        """
        import re
        
        # Pattern: ${VAR_NAME} or ${VAR_NAME:default}
        pattern = r'\$\{([^}:]+)(?::([^}]*))?\}'
        
        def replace(match):
            var_name = match.group(1)
            default = match.group(2) if match.group(2) is not None else ""
            return os.getenv(var_name, default)
        
        return re.sub(pattern, replace, value)
    
    def _create_config(
        self,
        scenario_id: str,
        data: Dict[str, Any]
    ) -> ScenarioConfig:
        """
        Create ScenarioConfig from loaded data.
        
        Args:
            scenario_id: Scenario identifier
            data: Loaded YAML data
            
        Returns:
            ScenarioConfig object
        """
        return ScenarioConfig(
            scenario_id=scenario_id,
            name=data.get("name", scenario_id.replace("_", " ").title()),
            description=data.get("description", ""),
            max_rounds=data.get("max_rounds", 10),
            market_avg=data.get("market_avg", 150.0),
            buyer_configs=data.get("buyer_configs", {}),
            seller_configs=data.get("seller_configs", {}),
            metrics_config=data.get("metrics_config", {}),
            parameters=data.get("parameters", {})
        )
    
    def load_all(self) -> Dict[str, ScenarioConfig]:
        """
        Load all scenario configurations from config directory.
        
        Returns:
            Dictionary mapping scenario_id -> ScenarioConfig
        """
        configs = {}
        
        if not self.config_dir.exists():
            return configs
        
        for config_file in self.config_dir.glob("*.yaml"):
            scenario_id = config_file.stem
            try:
                configs[scenario_id] = self.load(scenario_id)
            except Exception as e:
                # Log error but continue loading other configs
                print(f"Error loading {config_file}: {e}")
        
        return configs
    
    def validate_config(self, config: ScenarioConfig) -> bool:
        """
        Validate a scenario configuration.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If configuration is invalid
        """
        # Basic validation (already done in ScenarioConfig.__post_init__)
        if not config.scenario_id:
            raise ValueError("scenario_id is required")
        
        if config.max_rounds < 1:
            raise ValueError("max_rounds must be >= 1")
        
        if config.market_avg <= 0:
            raise ValueError("market_avg must be > 0")
        
        return True


# Global config loader instance
_loader = ConfigLoader()


def get_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    return _loader


def load_config(scenario_id: str) -> ScenarioConfig:
    """
    Load configuration for a scenario using global loader.
    
    Args:
        scenario_id: Scenario identifier
        
    Returns:
        ScenarioConfig object
    """
    return _loader.load(scenario_id)
