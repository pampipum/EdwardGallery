"""
Rate Limiter - Client-side request throttling for API calls.

Implements token bucket algorithm to prevent exceeding API rate limits.
Particularly important for Jupiter API calls which may have tier-based limits.
"""

import json
import os
import threading
import time
from typing import Optional

from backend.utils.logger import logger
from backend.runtime import config_path


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Allows bursts up to bucket capacity while maintaining
    average rate over time.
    """
    
    def __init__(self, requests_per_minute: int = 60, bucket_size: Optional[int] = None):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute
            bucket_size: Maximum burst size (defaults to requests_per_minute)
        """
        self.rate = requests_per_minute / 60.0  # Requests per second
        self.bucket_size = bucket_size or requests_per_minute
        self.tokens = float(self.bucket_size)
        self.last_update = time.time()
        self._lock = threading.Lock()
        
        logger.info(f"Rate limiter initialized ({requests_per_minute} req/min)")
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        self.tokens = min(
            self.bucket_size,
            self.tokens + (elapsed * self.rate)
        )
        self.last_update = now
    
    def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Acquire tokens from the bucket (blocking).
        
        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum seconds to wait
            
        Returns:
            True if tokens acquired, False if timeout
        """
        deadline = time.time() + timeout
        
        while time.time() < deadline:
            with self._lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            # Wait a bit before retrying
            time.sleep(0.1)
        
        logger.warning("Rate limiter: Timeout waiting for tokens")
        return False
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens without blocking.
        
        Args:
            tokens: Number of tokens to acquire
            
        Returns:
            True if tokens acquired, False otherwise
        """
        with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def get_status(self) -> dict:
        """Get current rate limiter status."""
        with self._lock:
            self._refill()
            return {
                "tokens_available": self.tokens,
                "bucket_size": self.bucket_size,
                "rate_per_second": self.rate,
                "requests_per_minute": self.rate * 60
            }


def load_rate_limiter_config() -> dict:
    """Load rate limiter configuration from config.json."""
    try:
        config_file = os.path.normpath(str(config_path()))
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('rate_limiting', {})
    except Exception as e:
        logger.warning(f"Failed to load rate limiting config: {e}")
    
    return {}


# Global rate limiter (shared across all PMs)
_rate_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def get_rate_limiter() -> Optional[RateLimiter]:
    """
    Get the global rate limiter instance.
    
    Returns:
        RateLimiter instance or None if disabled
    """
    global _rate_limiter
    
    with _limiter_lock:
        if _rate_limiter is None:
            config = load_rate_limiter_config()
            
            if not config.get('enabled', True):
                logger.info("Rate limiting disabled")
                return None
            
            requests_per_minute = config.get('requests_per_minute', 60)
            _rate_limiter = RateLimiter(requests_per_minute)
        
        return _rate_limiter
