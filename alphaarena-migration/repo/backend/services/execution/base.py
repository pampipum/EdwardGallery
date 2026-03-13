"""
Base Executor Interface - Abstract base class for trade execution strategies.

All executors (Paper, Jupiter) must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class ExecutionResult:
    """Result of a trade execution attempt."""
    success: bool
    action: str  # BUY, SELL
    ticker: str
    requested_amount: float  # USD value requested
    executed_qty: float  # Actual quantity filled
    executed_price: float  # Fill price
    fee: float = 0.0  # Network/exchange fee (SOL for Jupiter)
    tx_hash: Optional[str] = None  # On-chain transaction hash (live only)
    confirmed: bool = False  # Whether transaction was confirmed on-chain
    error: Optional[str] = None  # Error message if failed
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class BaseExecutor(ABC):
    """
    Abstract base class for trade executors.
    
    Implementations:
    - PaperExecutor: Simulates trades locally
    - JupiterExecutor: Executes real trades via Jupiter API
    """
    
    def __init__(self, pm_id: str):
        self.pm_id = pm_id
    
    @abstractmethod
    def execute_order(
        self, 
        ticker: str, 
        action: str,  # "BUY" or "SELL" 
        amount_usd: float, 
        current_price: float,
        slippage_bps: int = 50  # Slippage tolerance in basis points (default 0.5%)
    ) -> ExecutionResult:
        """
        Execute a trade order.
        
        Args:
            ticker: Asset ticker (e.g., "SOL-USD", "BTC-USD")
            action: "BUY" or "SELL"
            amount_usd: Dollar amount to trade
            current_price: Current market price for reference
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)
            
        Returns:
            ExecutionResult with fill details
        """
        pass
    
    @abstractmethod
    def get_balance(self, ticker: str) -> float:
        """
        Get the current balance of an asset.
        
        Args:
            ticker: Asset ticker
            
        Returns:
            Balance quantity (not USD value)
        """
        pass
    
    @abstractmethod
    def get_mode(self) -> str:
        """
        Returns the executor mode ("PAPER" or "LIVE").
        """
        pass
