"""
Kraken Executor - Hybrid Implementation
Uses Pure Python REST API for Crypto and kraken-cli for Tokenized Assets (Stocks).
"""

import os
import subprocess
import json
from .base import BaseExecutor, ExecutionResult
from .kraken_api import KrakenAPI
from backend.utils.logger import logger

class KrakenExecutor(BaseExecutor):
    """
    Hybrid Executor:
    - Crypto: Handled via Python REST API (Fast, low overhead)
    - Stocks: Handled via kraken-cli (Handles specialized tokenized_asset routing)
    """
    
    def __init__(self, pm_id: str):
        super().__init__(pm_id)
        api_key = os.getenv('KRAKEN_API_KEY')
        api_secret = os.getenv('KRAKEN_API_SECRET')
        
        self.api = KrakenAPI(api_key, api_secret)
        self.cli_path = "/root/.cargo/bin/kraken"
        
        # Define stock list for routing
        self.stocks = [
            "TSLA", "GOOGL", "NVDA", "META", "AMD", "TSM", 
            "ASML", "MU", "MRVL", "ARM", "AVGO", "ALAB", "PLTR", "GOOG"
        ]
        
        logger.info(f"[{self.pm_id}] Hybrid KrakenExecutor initialized. Stocks routed via CLI.")

    def _is_stock(self, ticker: str) -> bool:
        return any(s in ticker for s in self.stocks)

    def _translate_ticker_rest(self, ticker: str) -> str:
        """Translate for Python REST API (Crypto)"""
        clean = ticker.replace("-", "").replace("/", "")
        mapping = {"BTCUSD": "XXBTZUSD", "ETHUSD": "XETHZUSD", "SOLUSD": "SOLUSD"}
        return mapping.get(clean, clean)

    def _translate_ticker_cli(self, ticker: str) -> str:
        """Translate for Kraken CLI (Stocks) - requires 'x' suffix and slash"""
        base = ticker.split("-")[0] if "-" in ticker else ticker
        return f"{base}x/USD"

    def execute_order(
        self, 
        ticker: str, 
        action: str, 
        amount_usd: float, 
        current_price: float,
        slippage_bps: int = 50
    ) -> ExecutionResult:
        """Execute trade using either REST (Crypto) or CLI (Stocks)."""
        
        if self._is_stock(ticker):
            return self._execute_cli_stock(ticker, action, amount_usd, current_price)
        else:
            return self._execute_rest_crypto(ticker, action, amount_usd, current_price)

    def _execute_rest_crypto(self, ticker, action, amount_usd, current_price) -> ExecutionResult:
        kraken_pair = self._translate_rest(ticker) if hasattr(self, '_translate_rest') else self._translate_ticker_rest(ticker)
        side = action.lower()
        volume = amount_usd / current_price
        
        # Get leverage
        leverage_val = None
        try:
            from backend.services.pm_strategies import get_strategy
            strategy = get_strategy(self.pm_id)
            ratio = strategy.get_leverage_ratio()
            if ratio > 1.0: leverage_val = f"{int(ratio)}:1"
        except: pass

        logger.info(f"[{self.pm_id}] REST Crypto {action} {ticker} @ {current_price}")
        
        result = self.api.add_order(
            pair=kraken_pair,
            side=side,
            order_type='market',
            volume=f"{volume:.8f}",
            extra={'leverage': leverage_val} if leverage_val else None
        )
        
        if result.get("error"):
            error_msg = ", ".join(result["error"])
            return ExecutionResult(False, action, ticker, amount_usd, 0, 0, error=error_msg)

        txid = result.get("result", {}).get("txid", ["UNKNOWN"])[0]
        return ExecutionResult(True, action, ticker, amount_usd, volume, current_price, tx_hash=txid, confirmed=True)

    def _execute_cli_stock(self, ticker, action, amount_usd, current_price) -> ExecutionResult:
        kraken_ticker = self._translate_ticker_cli(ticker)
        volume = amount_usd / current_price
        
        # Leverage for stocks (capped at 3x by Kraken)
        leverage = "3" 
        
        logger.info(f"[{self.pm_id}] CLI Stock {action} {kraken_ticker} Vol: {volume:.4f} (Leverage: {leverage}x)")
        
        # Build CLI command
        cmd = [
            self.cli_path, "order", action.lower(), 
            kraken_ticker, f"{volume:.6f}",
            "--type", "market",
            "--asset-class", "tokenized_asset",
            "--leverage", leverage,
            "-o", "json"
        ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                logger.error(f"[{self.pm_id}] CLI Stock Error: {res.stderr}")
                return ExecutionResult(False, action, ticker, amount_usd, 0, 0, error=res.stderr)
            
            data = json.loads(res.stdout)
            txid = data.get("result", {}).get("txid", ["UNKNOWN"])[0]
            return ExecutionResult(True, action, ticker, amount_usd, volume, current_price, tx_hash=txid, confirmed=True)
        except Exception as e:
            return ExecutionResult(False, action, ticker, amount_usd, 0, 0, error=str(e))

    def get_balance(self, ticker: str) -> float:
        """Get combined balance (Main + Earn) via REST API."""
        asset_name = ticker.split("-")[0] if "-" in ticker else ticker
        normalization = {"BTC": "XXBT", "ETH": "XETH", "USD": "ZUSD", "USDC": "USDC"}
        kraken_asset = normalization.get(asset_name, asset_name)
        
        # 1. Main Balance
        result = self.api.get_balance()
        balance = float(result.get("result", {}).get(kraken_asset, 0.0))
        
        # 2. Earn Balance
        earn_result = self.api.get_earn_allocations()
        if not earn_result.get("error"):
            positions = earn_result.get("result", {}).get("items", [])
            for item in positions:
                if item.get("asset") == asset_name or item.get("asset") == kraken_asset:
                    balance += float(item.get("amount", 0.0))

        return float(balance)

    def get_mode(self) -> str:
        return "LIVE"
