"""
Configuration and ticker management services.
"""
import json
import os
from backend.utils.logger import logger
from backend.runtime import config_path


def get_top_tickers():
    """Returns a dictionary of top stocks and crypto tickers from config."""
    assets = []
    
    runtime_config = config_path()
    if runtime_config.exists():
        try:
            with open(runtime_config, 'r') as f:
                config = json.load(f)
                assets = config.get('assets', [])
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            
    # Simple heuristic to categorize
    crypto = [t for t in assets if "-USD" in t]
    stocks = [t for t in assets if "-USD" not in t]
    
    return {
        "stocks": stocks,
        "crypto": crypto
    }
