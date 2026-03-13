"""
LLM Monitor - Tracks and logs all LLM API requests for cost control and supervision.
"""

import json
import os
import threading
from datetime import datetime
from typing import Optional, Dict, Any

USAGE_FILE = "backend/data/llm_usage.json"

class LLMMonitor:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LLMMonitor, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self):
        self.log_lock = threading.Lock()
        # Ensure data directory exists
        os.makedirs(os.path.dirname(USAGE_FILE), exist_ok=True)
        
        # Load or initialize usage log
        if not os.path.exists(USAGE_FILE):
            self._save_logs([])

    def _load_logs(self) -> list:
        try:
            if os.path.exists(USAGE_FILE):
                with open(USAGE_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_logs(self, logs: list):
        try:
            # Keep only last 500 requests to prevent file bloating
            recent_logs = logs[-500:]
            with open(USAGE_FILE, 'w') as f:
                json.dump(recent_logs, f, indent=2)
        except Exception:
            pass

    def log_request(self, 
                    provider: str, 
                    model: str, 
                    prompt: str, 
                    response: str, 
                    tokens_in: int = 0, 
                    tokens_out: int = 0,
                    purpose: str = "Unknown",
                    pm_id: str = "N/A",
                    duration: float = 0.0):
        """Logs an LLM request with metadata."""
        
        # Estimate cost (approximate OpenRouter rates)
        # Rates per 1M tokens
        rates = {
            "x-ai/grok-4.1-fast": {"in": 2.0, "out": 8.0},
            "minimax/minimax-m2.5": {"in": 0.15, "out": 0.60},
            "anthropic/claude-3.5-sonnet": {"in": 3.0, "out": 15.0},
            "google/gemini-2.0-pro-exp-02-05:free": {"in": 0.0, "out": 0.0},
            "default": {"in": 2.0, "out": 10.0}
        }
        
        rate = rates.get(model, rates.get("default"))
        cost = (tokens_in / 1_000_000 * rate["in"]) + (tokens_out / 1_000_000 * rate["out"])

        entry = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "purpose": purpose,
            "pm_id": pm_id,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": round(cost, 6),
            "duration": round(duration, 2),
            "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "response_preview": response[:200] + "..." if len(response) > 200 else response
        }

        with self.log_lock:
            logs = self._load_logs()
            logs.append(entry)
            self._save_logs(logs)

    def get_logs(self):
        with self.log_lock:
            return self._load_logs()

# Global monitor instance
llm_monitor = LLMMonitor()
