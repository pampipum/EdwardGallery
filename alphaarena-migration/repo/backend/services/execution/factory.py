"""
Executor Factory - Returns the appropriate executor based on configuration.

Safety Logic:
1. If live_trading_enabled is False → Always return PaperExecutor
2. If live_trading_enabled is True AND trading_modes[pm_id] == "LIVE" → Raise NotImplementedError
3. Otherwise → Return PaperExecutor

IMPORTANT: Configuration changes require application restart.
The executor is cached per PM, so changing config.json while running will NOT
take effect until the application is restarted.
"""

import json
import os

from .base import BaseExecutor
from .paper_executor import PaperExecutor
from backend.utils.logger import logger
from backend.runtime import config_path, paper_only_mode


def load_config() -> dict:
    """Load configuration from config.json"""
    try:
        config_file = os.path.normpath(str(config_path()))
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
    return {}


def get_executor_mode(pm_id: str) -> str:
    """
    Determine the execution mode for a PM based on config.
    
    Returns "PAPER" or "LIVE".
    """
    if paper_only_mode():
        return "PAPER"

    config = load_config()
    if not config.get("live_trading_enabled", False):
        return "PAPER"

    # Check individual PM mode
    return config.get("trading_modes", {}).get(pm_id, "PAPER")


class ExecutorFactory:
    """
    Factory for creating trade executors.
    
    Uses configuration to determine whether to return a PaperExecutor
    (for testing) or a LiveExecutor (to be implemented).
    """
    
    _executors: dict = {}  # Cache executors by pm_id
    
    @classmethod
    def get_executor(cls, pm_id: str) -> BaseExecutor:
        """
        Get or create an executor for the given PM.
        
        Args:
            pm_id: Portfolio manager ID (e.g., "pm1", "pm2")
            
        Returns:
            Appropriate executor instance
        """
        mode = get_executor_mode(pm_id)
        
        # Check cache - but invalidate if mode changed
        cache_key = f"{pm_id}_{mode}"
        if cache_key in cls._executors:
            return cls._executors[cache_key]
        
        if mode == "LIVE":
            try:
                from .kraken_executor import KrakenExecutor
                executor = KrakenExecutor(pm_id)
                logger.info(f"[{pm_id}] ✅ Created KrakenExecutor (LIVE mode)")
            except Exception as e:
                logger.error(f"[{pm_id}] Failed to create KrakenExecutor: {e}")
                logger.warning(f"[{pm_id}] Falling back to PaperExecutor")
                executor = PaperExecutor(pm_id)
        else:
            executor = PaperExecutor(pm_id)
            logger.info(f"[{pm_id}] Created PaperExecutor (PAPER mode)")
        
        cls._executors[cache_key] = executor
        return executor
    
    @classmethod
    def clear_cache(cls):
        """Clear the executor cache. Useful for testing or config changes."""
        cls._executors.clear()
