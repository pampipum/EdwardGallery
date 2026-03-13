"""
Paper Executor - Simulates trade execution for paper trading mode.

This executor does not make any external API calls. It simulates fills
instantly at the provided price, allowing for safe strategy testing.
"""

from .base import BaseExecutor, ExecutionResult
from backend.utils.logger import logger


class PaperExecutor(BaseExecutor):
    """
    Paper trading executor - simulates trades without real execution.
    
    All trades are assumed to fill immediately at the requested price.
    No fees, no slippage, no network delays.
    """
    
    def __init__(self, pm_id: str):
        super().__init__(pm_id)
        logger.info(f"[{pm_id}] Initialized PaperExecutor (PAPER mode)")
    
    def execute_order(
        self, 
        ticker: str, 
        action: str, 
        amount_usd: float, 
        current_price: float,
        slippage_bps: int = 50
    ) -> ExecutionResult:
        """
        Simulate a trade execution.
        
        In paper mode, trades always succeed with perfect fills.
        The slippage_bps parameter is ignored for paper trading.
        """
        if current_price <= 0:
            return ExecutionResult(
                success=False,
                action=action,
                ticker=ticker,
                requested_amount=amount_usd,
                executed_qty=0.0,
                executed_price=0.0,
                error="Invalid price"
            )
        
        # Calculate quantity from USD amount
        qty = amount_usd / current_price
        
        logger.info(
            f"[{self.pm_id}] PAPER {action}: {qty:.6f} {ticker} @ ${current_price:.2f} "
            f"(${amount_usd:.2f})"
        )
        
        return ExecutionResult(
            success=True,
            action=action,
            ticker=ticker,
            requested_amount=amount_usd,
            executed_qty=qty,
            executed_price=current_price,
            fee=0.0,  # No fees in paper trading
            tx_hash=None  # No on-chain transaction
        )
    
    def get_balance(self, ticker: str) -> float:
        """
        In paper mode, balance is tracked by PortfolioService JSON.
        This method returns 0 as the executor doesn't track state.
        """
        # Paper executor doesn't track balances - PortfolioService handles this
        return 0.0
    
    def get_mode(self) -> str:
        return "PAPER"
