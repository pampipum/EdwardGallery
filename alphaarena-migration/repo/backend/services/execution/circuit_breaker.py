"""
Circuit Breaker - Prevents cascading failures by halting trading after consecutive errors.

Implements the Circuit Breaker pattern to protect against:
- API outages
- Wallet/signing errors
- Network connectivity issues
- Repeated failed transactions

State Machine:
- CLOSED: Normal operation, trades allowed
- OPEN: Trading halted after threshold failures
- HALF_OPEN: Testing recovery with limited trades
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from backend.utils.logger import logger
from backend.runtime import config_path


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Trading halted
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for trade execution.
    
    Tracks failures per PM and opens circuit when threshold is exceeded.
    Auto-resets after cooldown period.
    """
    
    def __init__(self, pm_id: str, failure_threshold: int = 5, cooldown_minutes: int = 15):
        """
        Initialize circuit breaker.
        
        Args:
            pm_id: Portfolio manager ID
            failure_threshold: Number of consecutive failures before opening
            cooldown_minutes: Minutes to wait before attempting recovery
        """
        self.pm_id = pm_id
        self.failure_threshold = failure_threshold
        self.cooldown_minutes = cooldown_minutes
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        
        self._lock = threading.Lock()
        
        logger.info(
            f"[{pm_id}] Circuit breaker initialized "
            f"(threshold={failure_threshold}, cooldown={cooldown_minutes}m)"
        )
    
    def is_closed(self) -> bool:
        """Check if circuit allows trading."""
        with self._lock:
            # Check if we should transition from OPEN to HALF_OPEN
            if self.state == CircuitState.OPEN and self.opened_at:
                cooldown_end = self.opened_at + timedelta(minutes=self.cooldown_minutes)
                if datetime.now() >= cooldown_end:
                    logger.info(f"[{self.pm_id}] Circuit breaker: OPEN → HALF_OPEN (testing recovery)")
                    self.state = CircuitState.HALF_OPEN
                    return True
            
            return self.state != CircuitState.OPEN
    
    def record_success(self):
        """Record successful trade execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"[{self.pm_id}] Circuit breaker: HALF_OPEN → CLOSED (recovery successful)")
                self.state = CircuitState.CLOSED
            
            # Reset failure counter on success
            if self.failure_count > 0:
                logger.info(f"[{self.pm_id}] Circuit breaker: Reset failure count (was {self.failure_count})")
            self.failure_count = 0
            self.last_failure_time = None
    
    def record_failure(self, error: str):
        """
        Record failed trade execution.
        
        Args:
            error: Error message from failed execution
        """
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            logger.warning(
                f"[{self.pm_id}] Circuit breaker: Failure #{self.failure_count} - {error}"
            )
            
            # Check if we should open the circuit
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = datetime.now()
                
                logger.error(
                    f"[{self.pm_id}] 🚨 CIRCUIT BREAKER OPEN - Trading halted! "
                    f"({self.failure_count} consecutive failures). "
                    f"Cooldown: {self.cooldown_minutes} minutes"
                )
    
    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        with self._lock:
            status = {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold,
                "cooldown_minutes": self.cooldown_minutes
            }
            
            if self.last_failure_time:
                status["last_failure_time"] = self.last_failure_time.isoformat()
            
            if self.opened_at:
                status["opened_at"] = self.opened_at.isoformat()
                cooldown_end = self.opened_at + timedelta(minutes=self.cooldown_minutes)
                status["cooldown_ends_at"] = cooldown_end.isoformat()
                remaining = (cooldown_end - datetime.now()).total_seconds() / 60
                status["cooldown_remaining_minutes"] = max(0, remaining)
            
            return status
    
    def reset(self):
        """Manually reset the circuit breaker (for testing/admin)."""
        with self._lock:
            logger.info(f"[{self.pm_id}] Circuit breaker manually reset")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = None
            self.opened_at = None


def load_circuit_breaker_config() -> dict:
    """Load circuit breaker configuration from config.json."""
    try:
        config_file = os.path.normpath(str(config_path()))
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('circuit_breaker', {})
    except Exception as e:
        logger.warning(f"Failed to load circuit breaker config: {e}")
    
    return {}


# Global circuit breakers (one per PM)
_circuit_breakers = {}
_cb_lock = threading.Lock()


def get_circuit_breaker(pm_id: str) -> CircuitBreaker:
    """
    Get or create a circuit breaker for the given PM.
    
    Args:
        pm_id: Portfolio manager ID
        
    Returns:
        CircuitBreaker instance
    """
    with _cb_lock:
        if pm_id not in _circuit_breakers:
            config = load_circuit_breaker_config()
            
            # Only create circuit breaker if enabled
            if not config.get('enabled', True):
                # Return a dummy breaker that's always closed
                class DummyBreaker:
                    def is_closed(self): return True
                    def record_success(self): pass
                    def record_failure(self, error): pass
                    def get_status(self): return {"state": "DISABLED"}
                    def reset(self): pass
                
                return DummyBreaker()
            
            threshold = config.get('failure_threshold', 5)
            cooldown = config.get('cooldown_minutes', 15)
            
            _circuit_breakers[pm_id] = CircuitBreaker(
                pm_id, threshold, cooldown
            )
        
        return _circuit_breakers[pm_id]
