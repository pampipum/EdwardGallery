import json
import os
from datetime import datetime, timedelta
from typing import Optional
from backend.utils.logger import logger
from backend.runtime import state_dir

PORTFOLIO_DIR = str(state_dir("portfolios"))
LEVERAGE_APR = 0.12  # 12% Annualized Borrow Rate for Margin/Shorts

# Ensure portfolio directory exists
if not os.path.exists(PORTFOLIO_DIR):
    os.makedirs(PORTFOLIO_DIR)


def validate_exit_plan(exit_plan: dict, entry_price: float, is_long: bool, pm_id: str = "") -> dict:
    """
    Validates and sanitizes exit plan values from AI.
    Returns a cleaned exit plan with invalid values removed or corrected.
    """
    if not exit_plan:
        return {}
    
    validated = {}
    prefix = f"[{pm_id}] " if pm_id else ""
    
    # Validate stop_loss
    stop_loss = exit_plan.get("stop_loss")
    if stop_loss:
        if is_long and stop_loss >= entry_price:
            logger.warning(f"{prefix}Invalid stop loss ${stop_loss:.2f} >= entry ${entry_price:.2f} for LONG. Ignoring.")
        elif not is_long and stop_loss <= entry_price:
            logger.warning(f"{prefix}Invalid stop loss ${stop_loss:.2f} <= entry ${entry_price:.2f} for SHORT. Ignoring.")
        else:
            validated["stop_loss"] = stop_loss
    
    # Validate target_price
    target_price = exit_plan.get("target_price")
    if target_price:
        if is_long and target_price <= entry_price:
            logger.warning(f"{prefix}Invalid target ${target_price:.2f} <= entry ${entry_price:.2f} for LONG. Ignoring.")
        elif not is_long and target_price >= entry_price:
            logger.warning(f"{prefix}Invalid target ${target_price:.2f} >= entry ${entry_price:.2f} for SHORT. Ignoring.")
        else:
            validated["target_price"] = target_price
    
    # Validate trailing_stop
    trailing_stop = exit_plan.get("trailing_stop")
    if trailing_stop and isinstance(trailing_stop, dict):
        trail_value = trailing_stop.get("value", 0)
        if trail_value <= 0 or trail_value > 0.50:  # Must be between 0% and 50%
            logger.warning(f"{prefix}Invalid trailing stop value {trail_value:.1%}. Must be 0-50%. Ignoring.")
        else:
            validated["trailing_stop"] = trailing_stop
    
    # Validate partial_targets
    partial_targets = exit_plan.get("partial_targets", [])
    if partial_targets:
        valid_targets = []
        for target in partial_targets:
            price = target.get("price")
            pct = target.get("percentage", 0)
            
            if not price or pct <= 0 or pct > 1:
                continue
                
            if is_long and price <= entry_price:
                logger.warning(f"{prefix}Invalid partial target ${price:.2f} <= entry for LONG. Skipping.")
                continue
            elif not is_long and price >= entry_price:
                logger.warning(f"{prefix}Invalid partial target ${price:.2f} >= entry for SHORT. Skipping.")
                continue
                
            valid_targets.append(target)
        
        if valid_targets:
            validated["partial_targets"] = valid_targets
    
    # Copy through non-validated fields
    if "invalidation_condition" in exit_plan:
        validated["invalidation_condition"] = exit_plan["invalidation_condition"]
    if "time_exit" in exit_plan:
        validated["time_exit"] = exit_plan["time_exit"]
    
    return validated

class PortfolioService:
    def __init__(self, pm_id: str = 'pm1', executor = None):
        """
        Initialize Portfolio Service.
        
        Args:
            pm_id: Portfolio manager ID
            executor: Optional executor for live trading (defaults to factory-created executor)
        """
        self.pm_id = pm_id
        self.portfolio_file = os.path.join(PORTFOLIO_DIR, f"{pm_id}.json")
        
        # Initialize executor (lazy load to avoid circular imports)
        self._executor = executor
        
        self.load_portfolio()
        
        # Auto-sync balance if in LIVE mode
        self.sync_wallet_balance()

    def sync_wallet_balance(self):
        """
        Syncs the portfolio balance with the actual wallet balance if in LIVE mode.
        """
        try:
            # Load executor if not already loaded
            if self._executor is None:
                from backend.services.execution.factory import ExecutorFactory
                self._executor = ExecutorFactory.get_executor(self.pm_id)

            if self._executor.get_mode() == "LIVE":
                logger.info(f"[{self.pm_id}] Syncing wallet balance for LIVE trading...")
                
                # LiveExecutor uses "USDC" or equivalent to get balance
                # We assume the portfolio balance tracks USDC for trading
                wallet_balance = self._executor.get_balance("USDC")
                
                # Only update if we get a valid positive balance (or 0)
                if wallet_balance >= 0:
                    old_balance = self.data["balance"]
                    if abs(old_balance - wallet_balance) > 0.01: # Reduce noise
                        self.data["balance"] = wallet_balance
                        self.add_ledger_entry(
                            "BALANCE_SYNC", 
                            wallet_balance - old_balance, 
                            f"Synced with wallet: {old_balance:.2f} -> {wallet_balance:.2f}", 
                            "USDC"
                        )
                        self.save_portfolio()
                        logger.info(f"[{self.pm_id}] ✅ Balance synced: ${wallet_balance:.2f}")
                else:
                    logger.warning(f"[{self.pm_id}] Got invalid wallet balance: {wallet_balance}")
                    
        except Exception as e:
            logger.error(f"[{self.pm_id}] Failed to sync wallet balance: {e}")


    def load_portfolio(self):
        if os.path.exists(self.portfolio_file):
            with open(self.portfolio_file, "r") as f:
                self.data = json.load(f)
                # Ensure new keys exist for older files
                if "manager_log" not in self.data:
                    self.data["manager_log"] = []
                if "trade_log" not in self.data:
                    self.data["trade_log"] = []
                if "pm_id" not in self.data:
                    self.data["pm_id"] = self.pm_id
                if "active_learnings" not in self.data:
                    self.data["active_learnings"] = []
                if "retired_learnings" not in self.data:
                    self.data["retired_learnings"] = []
        else:
            self.data = {
                "pm_id": self.pm_id,
                "balance": 0,
                "initial_capital": 0,
                "positions": {}, # {ticker: {qty: float, avg_price: float}}
                "history": [], # [{timestamp, total_value}]
                "trade_log": [], # [{timestamp, ticker, action, price, qty}]
                "manager_log": [], # [{timestamp, message}]
                "ledger": [], # [{timestamp, type, amount, description, running_balance}]
                "is_running": False,
                "active_learnings": [],
                "retired_learnings": []
            }

    def save_portfolio(self):
        with open(self.portfolio_file, "w") as f:
            json.dump(self.data, f, indent=4)

    def start_portfolio(self, capital: float):
        # Check if LIVE mode and override capital with actual wallet balance
        if self._executor is None:
            from backend.services.execution.factory import ExecutorFactory
            self._executor = ExecutorFactory.get_executor(self.pm_id)
            
        if self._executor.get_mode() == "LIVE":
            try:
                wallet_balance = self._executor.get_balance("USDC")
                logger.info(f"[{self.pm_id}] LIVE mode detected. Overriding input capital ${capital} with wallet balance ${wallet_balance:.2f}")
                capital = wallet_balance
            except Exception as e:
                logger.error(f"[{self.pm_id}] Failed to fetch wallet balance on start: {e}")

        self.data["initial_capital"] = capital
        self.data["balance"] = capital
        self.data["positions"] = {}
        self.data["history"] = [{"timestamp": datetime.now().isoformat(), "total_value": capital}]
        self.data["trade_log"] = []
        self.data["manager_log"] = []
        self.data["ledger"] = []
        self.data["is_running"] = True
        
        # Reset benchmark tracking so it re-initializes with fresh prices
        for key in ["benchmark_start", "benchmark_return", "portfolio_return", "vs_benchmark", "last_fee_deduction"]:
            if key in self.data:
                del self.data[key]
        
        # Initial deposit ledger entry
        desc = "Initial wallet balance sync" if self._executor.get_mode() == "LIVE" else "Initial capital deposit"
        self.add_ledger_entry("DEPOSIT", capital, desc, None)
        
        self.save_portfolio()
        return self.data
    
    def add_ledger_entry(self, entry_type: str, amount: float, description: str, ticker: str = None):
        """
        Add an entry to the ledger.
        
        Args:
            entry_type: DEPOSIT, TRADE_COST, TRADE_PROCEEDS, REALIZED_PNL
            amount: Amount (positive or negative)
            description: Human-readable description
            ticker: Optional ticker symbol
        """
        if "ledger" not in self.data:
            self.data["ledger"] = []
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": entry_type,
            "amount": amount,
            "description": description,
            "running_balance": self.data["balance"]
        }
        
        if ticker:
            entry["ticker"] = ticker
        
        self.data["ledger"].append(entry)

    def get_status(self):
        """
        Get portfolio status with unrealized P&L calculations.
        """
        from backend.services.market_service import get_current_prices
        
        # Get current prices for all positions
        tickers = list(self.data.get("positions", {}).keys())
        current_prices = {}
        if tickers:
            current_prices = get_current_prices(tickers)
        
        # Calculate unrealized P&L for each position
        positions_with_pnl = {}
        total_unrealized_pnl = 0.0
        
        for ticker, pos in self.data.get("positions", {}).items():
            current_price = current_prices.get(ticker, pos["avg_price"])
            qty = pos["qty"]
            avg_price = pos["avg_price"]
            
            # Calculate unrealized P&L
            if qty > 0:  # LONG position
                unrealized_pnl = (current_price - avg_price) * qty
            else:  # SHORT position
                unrealized_pnl = (avg_price - current_price) * abs(qty)
            
            total_unrealized_pnl += unrealized_pnl
            
            positions_with_pnl[ticker] = {
                **pos,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl
            }
        
        # Calculate total value (Cash + Market Value of Positions)
        # For LONG: market_value = qty * current_price (positive contribution)
        # For SHORT: 
        #   We have:
        #   1. Cash Balance (Includes Collateral)
        #   2. Short Proceeds (Asset, held by broker) -> abs(qty) * avg_price
        #   3. Liability (Debt) -> abs(qty) * current_price
        #   
        #   Net Contribution = Proceeds - Liability
        
        market_value = 0
        locked_collateral = 0.0
        
        for ticker, pos in self.data.get("positions", {}).items():
            current_price = current_prices.get(ticker, pos["avg_price"])
            qty = pos["qty"]
            
            if qty > 0:  # LONG position
                market_value += qty * current_price
            else:  # SHORT position
                initial_proceeds = abs(qty) * pos["avg_price"]
                current_liability = abs(qty) * current_price
                market_value += (initial_proceeds - current_liability)
                
                # Calculate Locked Collateral (100% of initial value)
                locked_collateral += initial_proceeds

        total_value = self.data.get("balance", 0) + market_value
        available_cash = self.data.get("balance", 0) - locked_collateral
        
        # Calculate current leverage usage
        # Total position value = sum of absolute value of all positions
        total_position_value = 0.0
        for ticker, pos in self.data.get("positions", {}).items():
            current_price = current_prices.get(ticker, pos["avg_price"])
            total_position_value += abs(pos["qty"]) * current_price
        
        # Current leverage = total position value / total equity
        current_leverage = total_position_value / total_value if total_value > 0 else 0.0
        
        # Calculate Total Realized P&L from Ledger
        total_realized_pnl = 0.0
        if "ledger" in self.data:
            for entry in self.data["ledger"]:
                if entry.get("type") == "REALIZED_PNL":
                    total_realized_pnl += entry.get("amount", 0)

        # ── Trim heavy arrays before returning ──────────────────────
        # Keep last 5 days of history, downsampled to 500 points max.
        # Full history is preserved in self.data / the JSON file for persistence.
        MAX_HISTORY_RESPONSE = 500
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        history = self.data.get("history", [])
        trimmed_history = [h for h in history if h.get("timestamp", "") >= five_days_ago]
        # Always include at least 2 points so sparklines render
        if len(trimmed_history) < 2:
            trimmed_history = history[-2:] if len(history) >= 2 else history
        # Downsample if still over the cap
        if len(trimmed_history) > MAX_HISTORY_RESPONSE:
            step = len(trimmed_history) // MAX_HISTORY_RESPONSE
            trimmed_history = trimmed_history[::step][-MAX_HISTORY_RESPONSE:]

        # Manager log: last 50 entries only (frontend renders the most recent)
        manager_log = self.data.get("manager_log", [])[-50:]

        # Trade log: last 100 trades — older trades available on /ledger endpoint
        trade_log = self.data.get("trade_log", [])[-100:]

        # Strategy Info
        from backend.services.pm_strategies import get_strategy
        strategy = get_strategy(self.pm_id)
        strategy_info = {
            "name": strategy.name,
            "description": strategy.description,
            "confidence_threshold": strategy.get_confidence_threshold(),
            "max_position_size": strategy.get_max_position_size(),
            "min_cash_buffer": strategy.get_min_cash_buffer(),
            "prompt_modifier": strategy.get_prompt_modifier()
        }

        return {
            # Core scalars
            "pm_id": self.data.get("pm_id"),
            "is_running": self.data.get("is_running", False),
            "initial_capital": self.data.get("initial_capital", 0),
            "balance": self.data.get("balance", 0),
            "available_cash": available_cash,
            "locked_collateral": locked_collateral,
            "total_value": total_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_position_value": total_position_value,
            "current_leverage": current_leverage,
            # Benchmark & return strings
            "benchmark_return": self.data.get("benchmark_return"),
            "portfolio_return": self.data.get("portfolio_return"),
            "vs_benchmark": self.data.get("vs_benchmark"),
            "benchmark_start": self.data.get("benchmark_start"),
            # Live data
            "positions": positions_with_pnl,
            "current_prices": current_prices,
            "latest_analysis": self.data.get("latest_analysis", []),
            "strategy_info": strategy_info,
            # Trimmed arrays
            "history": trimmed_history,
            "manager_log": manager_log,
            "trade_log": trade_log,
            "active_learnings": self.data.get("active_learnings", []),
            "retired_learnings": self.data.get("retired_learnings", [])
        }

    def get_active_learnings(self):
        """Returns only the active strategy overrides."""
        return self.data.get("active_learnings", [])

    def update_valuation(self, current_prices: dict):
        """
        Updates the total portfolio value based on current market prices.
        current_prices: {ticker: price}
        """
        if not self.data["is_running"]:
            return

        total_value = self.data["balance"]
        for ticker, pos in self.data["positions"].items():
            price = current_prices.get(ticker, pos["avg_price"]) # Fallback to avg_price
            qty = pos["qty"]
            
            if qty > 0:  # LONG position
                total_value += qty * price
            else:  # SHORT position
                initial_proceeds = abs(qty) * pos["avg_price"]
                current_liability = abs(qty) * price
                total_value += (initial_proceeds - current_liability)
            
        self.data["history"].append({
            "timestamp": datetime.now().isoformat(),
            "total_value": total_value
        })
        
        # Limit history to ~2000 points (roughly 1 week at 5-min intervals)
        # This prevents unbounded growth of the portfolio JSON file
        MAX_HISTORY_POINTS = 2000
        if len(self.data["history"]) > MAX_HISTORY_POINTS:
            # Keep recent 500 points at full resolution
            # Downsample older history (keep every 3rd point)
            old_history = self.data["history"][:-500]
            recent_history = self.data["history"][-500:]
            downsampled = old_history[::3]
            self.data["history"] = downsampled + recent_history
            
        # --- NEW: Leverage Costs (Borrow Fees) ---
        # Deduct fees if ample time has passed (e.g., every 1 hour to avoid log spam)
        # However, for accuracy in testing/sims, we calculate on every update but only log/deduct if amount > 0.01 or time > 1h.
        
        last_fee_time = datetime.fromisoformat(self.data.get("last_fee_deduction", self.data["history"][0]["timestamp"]))
        now = datetime.now()
        time_delta_hours = (now - last_fee_time).total_seconds() / 3600.0
        
        # Deduct at least every hour or if it's the first run (initialization check handled by get)
        if time_delta_hours >= 1.0:
            borrow_fee = 0.0
            
            # 1. Cash Borrow Fee (Margin Interest)
            # If Balance is negative, we are borrowing cash.
            if self.data["balance"] < 0:
                borrowed_cash = abs(self.data["balance"])
                # Formula: Principal * Rate * (Hours / 24 / 365)
                cash_fee = borrowed_cash * LEVERAGE_APR * (time_delta_hours / 24 / 365)
                borrow_fee += cash_fee
                
            # 2. Asset Borrow Fee (Short Positions)
            # We pay fees on the value of all short positions
            short_value = 0.0
            for ticker, pos in self.data["positions"].items():
                if pos["qty"] < 0:
                    # Use current price for value, fallback to avg_price
                    p = current_prices.get(ticker, pos["avg_price"])
                    short_value += abs(pos["qty"]) * p
            
            if short_value > 0:
                asset_fee = short_value * LEVERAGE_APR * (time_delta_hours / 24 / 365)
                borrow_fee += asset_fee
            
            # Deduct and Log
            if borrow_fee > 0:
                self.data["balance"] -= borrow_fee
                self.add_ledger_entry("FEE_LEVERAGE", -borrow_fee, f"Leverage Cost ({time_delta_hours:.1f}h): ${borrow_fee:.2f}", None)
                
            # Update timestamp
            self.data["last_fee_deduction"] = now.isoformat()
        
        # --- BENCHMARK TRACKING ---
        # Track performance vs a simple 60/40 BTC/ETH buy-and-hold
        # Always fetch BTC and ETH prices for benchmark, regardless of positions held
        btc_price = current_prices.get("BTC-USD")
        eth_price = current_prices.get("ETH-USD")
        
        # Fetch missing prices for benchmark calculation
        if not btc_price or not eth_price:
            from backend.services.market_service import get_current_prices
            benchmark_prices = get_current_prices(["BTC-USD", "ETH-USD"])
            if not btc_price:
                btc_price = benchmark_prices.get("BTC-USD")
            if not eth_price:
                eth_price = benchmark_prices.get("ETH-USD")
        
        if btc_price and eth_price:
            if "benchmark_start" not in self.data:
                # Initialize benchmark on first run with valid prices
                self.data["benchmark_start"] = {
                    "btc_price": btc_price,
                    "eth_price": eth_price,
                    "timestamp": datetime.now().isoformat()
                }
            
            start = self.data["benchmark_start"]
            btc_return = (btc_price - start["btc_price"]) / start["btc_price"]
            eth_return = (eth_price - start["eth_price"]) / start["eth_price"]

            # --- STRATEGY-AWARE BENCHMARK ---
            # PM4 tracks BTC only (leveraged crypto hunter)
            # All others use BTC 60% / ETH 40%
            pm_id = self.data.get("pm_id", "pm1")
            if pm_id == "pm4":
                benchmark_return = btc_return
            else:
                benchmark_return = 0.60 * btc_return + 0.40 * eth_return

            # Calculate portfolio return for comparison
            initial_capital = self.data.get("initial_capital", 100000)
            portfolio_return = (total_value - initial_capital) / initial_capital if initial_capital > 0 else 0

            self.data["benchmark_return"] = f"{benchmark_return:.2%}"
            self.data["portfolio_return"] = f"{portfolio_return:.2%}"
            self.data["vs_benchmark"] = f"{(portfolio_return - benchmark_return):+.2%}"
            
        self.save_portfolio()

    def ingest_learning(self, learning_data: dict):
        """
        Activates a proposed learning into the strategy overrides.
        Hard cap of 7 active learnings.
        """
        if "active_learnings" not in self.data:
            self.data["active_learnings"] = []
            
        # Hard cap: if at capacity, retire the oldest
        if len(self.data["active_learnings"]) >= 7:
            oldest = self.data["active_learnings"].pop(0)
            self.retire_learning(oldest["id"], "CAPACITY_REACHED")

        # Prep the new learning
        status = self.get_status()
        learning_entry = {
            **learning_data,
            "id": f"lr_{self.pm_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "status": "active",
            "ingested_at": datetime.now().isoformat(),
            "starting_portfolio_value": status.get("total_value", 0),
            "performance_since": 0.0
        }
        
        self.data["active_learnings"].append(learning_entry)
        self.save_portfolio()
        logger.info(f"[{self.pm_id}] 🧠 Learning ingested: {learning_entry['id']} - {learning_entry.get('parameter')}")
        return learning_entry

    def revert_learning(self, learning_id: str, reason: str = "MANUAL_REVERT"):
        """Moves an active learning to retired status (Rollback)."""
        active = self.data.get("active_learnings", [])
        learning = next((l for l in active if l["id"] == learning_id), None)
        
        if learning:
            learning["status"] = "retired"
            learning["retired_at"] = datetime.now().isoformat()
            learning["retire_reason"] = reason
            
            self.data["active_learnings"] = [l for l in active if l["id"] != learning_id]
            if "retired_learnings" not in self.data:
                self.data["retired_learnings"] = []
            self.data["retired_learnings"].append(learning)
            
            self.save_portfolio()
            logger.info(f"[{self.pm_id}] ⏪ Learning reverted: {learning_id}")
            return True
        return False

    def graduate_learning(self, learning_id: str):
        """Marks a learning as graduated (Permanently baked into strategy)."""
        active = self.data.get("active_learnings", [])
        learning = next((l for l in active if l["id"] == learning_id), None)
        
        if learning:
            learning["status"] = "graduated"
            learning["graduated_at"] = datetime.now().isoformat()
            
            self.data["active_learnings"] = [l for l in active if l["id"] != learning_id]
            if "retired_learnings" not in self.data:
                self.data["retired_learnings"] = []
            self.data["retired_learnings"].append(learning)
            
            self.save_portfolio()
            logger.info(f"[{self.pm_id}] 🎓 Learning graduated: {learning_id}")
            return True
        return False

    def auto_audit_active_learnings(self):
        """
        Cybernetic Autopilot: Automatically audits active learnings based on performance.
        - Auto-Revert if P&L < -2.5% after 3 trades.
        - Auto-Graduate if P&L > +5% after 15 trades.
        """
        active = self.data.get("active_learnings", [])
        if not active:
            return []

        ledger = self.data.get("ledger", [])
        current_value = self.get_status().get("total_value", 0)
        audit_results = []

        for l in active:
            ingested_at = datetime.fromisoformat(l["ingested_at"])
            starting_val = l.get("starting_portfolio_value", 100000)
            
            # Count trades closed since ingestion
            trades_since = [e for e in ledger if e.get("type") == "REALIZED_PNL" and 
                           datetime.fromisoformat(e["timestamp"][:19]) > ingested_at]
            
            num_trades = len(trades_since)
            pnl_since = (current_value - starting_val) / starting_val if starting_val > 0 else 0
            
            # Update learning record
            l["trades_count_since"] = num_trades
            l["performance_since"] = pnl_since
            
            # --- Decision Logic ---
            
            # 1. AUTO-REVERT (Loss Threshold)
            if num_trades >= 3 and pnl_since <= -0.025:
                self.revert_learning(l["id"], f"AUTO_REVERT: P&L {pnl_since:.2%} after {num_trades} trades")
                audit_results.append({"id": l["id"], "action": "REVERTED", "reason": "Loss threshold hit"})
                continue

            # 2. AUTO-REVERT (Win Rate Decay)
            if num_trades >= 5:
                wins = len([t for t in trades_since if t.get("amount", 0) > 0])
                win_rate = wins / num_trades
                if win_rate < 0.30: # Strategy-agnostic floor
                    self.revert_learning(l["id"], f"AUTO_REVERT: Win rate {win_rate:.1%} is too low")
                    audit_results.append({"id": l["id"], "action": "REVERTED", "reason": "Win rate decay"})
                    continue

            # 3. AUTO-GRADUATE (Success)
            if num_trades >= 15 and pnl_since >= 0.05:
                self.graduate_learning(l["id"])
                audit_results.append({"id": l["id"], "action": "GRADUATED", "reason": "Consistent outperformance"})
                continue
                
        self.save_portfolio()
        return audit_results

    def retire_learning(self, learning_id: str, reason: str):
        """Helper to retire a learning by ID."""
        return self.revert_learning(learning_id, reason)

    def set_latest_analysis(self, analysis_results):
        self.data["latest_analysis"] = analysis_results
        self.save_portfolio()

    def get_latest_analysis(self):
        return self.data.get("latest_analysis", [])

    def execute_partial_close(self, ticker: str, percentage: float, price: float, reason: str) -> str:
        """
        Closes a percentage of the position.
        percentage: 0.0 to 1.0 (e.g. 0.5 for 50%)
        """
        if ticker not in self.data["positions"]:
            return "Position not found"
            
        pos = self.data["positions"][ticker]
        current_qty = pos["qty"]
        avg_price = pos["avg_price"]
        
        # Determine close quantity
        qty_to_close = current_qty * percentage
        remaining_qty = current_qty - qty_to_close
        
        # Calculate P&L and Proceeds
        if current_qty > 0: # LONG
            # Sell 'qty_to_close'
            proceeds = abs(qty_to_close) * price
            cost_basis = abs(qty_to_close) * avg_price
            pnl = proceeds - cost_basis
            
            self.data["balance"] += proceeds
            self.add_ledger_entry("TRADE_PROCEEDS", proceeds, f"PARTIAL SELL {abs(qty_to_close):.4f} {ticker} @ ${price:.2f} ({reason})", ticker)
            
        else: # SHORT
            # Cover 'qty_to_close' (which is negative, so we are buying back abs(qty))
            abs_qty_to_close = abs(qty_to_close)
            
            # Proceeds from original short sale
            original_proceeds = abs_qty_to_close * avg_price
            # Cost to buy back now
            cost_to_cover = abs_qty_to_close * price
            
            pnl = original_proceeds - cost_to_cover
            
            # Return margin/proceeds logic
            self.data["balance"] += original_proceeds # Return collateral/proceeds
            self.add_ledger_entry("TRADE_PROCEEDS", original_proceeds, f"RETURN SHORT PROCEEDS (PARTIAL) {abs_qty_to_close:.4f} {ticker}", ticker)
            
            self.data["balance"] -= cost_to_cover # Pay for buyback
            self.add_ledger_entry("TRADE_COST", -cost_to_cover, f"PARTIAL COVER {abs_qty_to_close:.4f} {ticker} @ ${price:.2f} ({reason})", ticker)

        if pnl != 0:
            self.add_ledger_entry("REALIZED_PNL", pnl, f"Realized P&L on {ticker} partial close", ticker)

        # Update Position
        pos["qty"] = remaining_qty
        
        # Record partial fill
        if "partial_fills" not in pos:
            pos["partial_fills"] = []
        
        pos["partial_fills"].append({
            "timestamp": datetime.now().isoformat(),
            "qty": qty_to_close,
            "price": price,
            "percentage": percentage,
            "reason": reason,
            "pnl": pnl
        })
        
        # Log with specific actions for frontend compatibility
        if current_qty > 0:
            self.log_trade(ticker, "SELL (PARTIAL)", price, abs(qty_to_close), 10.0)
        else:
            self.log_trade(ticker, "BUY (COVER PARTIAL)", price, abs(qty_to_close), 10.0)
        self.save_portfolio()
        
        return f"Executed Partial Close: {percentage:.0%} of {ticker} ({reason})"



    def calculate_atr_position_size(self, atr: float, price: float, strategy) -> tuple[float, str]:
        """
        ATR-Normalized Position Sizing (Python Risk Engine).
        Strips the LLM of sizing authority — the LLM provides direction + conviction only.
        
        Formula:
            Account_Risk_USD  = total_equity * RISK_PER_TRADE_PCT
            Stop_Distance_USD = ATR_STOP_MULTIPLIER * atr
            Position_Size_USD = Account_Risk_USD / Stop_Distance_USD
        
        This guarantees each trade risks exactly RISK_PER_TRADE_PCT of equity,
        regardless of price magnitude or LLM suggestion.
        """
        RISK_PER_TRADE_PCT = 0.01   # Risk 1% of total equity per trade
        ATR_STOP_MULTIPLIER = 1.5   # Stop loss = 1.5 × ATR from entry
        
        if not atr or atr <= 0:
            return 0.0, "ATR unavailable — cannot size position"
        
        # Calculate total equity
        market_value = sum(
            pos["qty"] * pos["avg_price"] if pos["qty"] > 0 else 0
            for pos in self.data["positions"].values()
        )
        total_equity = self.data["balance"] + market_value
        
        if total_equity <= 0:
            return 0.0, "Insufficient equity"
        
        account_risk_usd = total_equity * RISK_PER_TRADE_PCT
        stop_distance_usd = ATR_STOP_MULTIPLIER * atr   # Per-unit stop distance
        
        if stop_distance_usd <= 0:
            return 0.0, "Invalid stop distance"
        
        # Position size in USD
        position_size_usd = account_risk_usd / (stop_distance_usd / price)
        
        # Apply strategy max-position cap as a hard ceiling
        max_pos_pct = strategy.get_max_position_size() if strategy else 0.20
        max_pos_usd = total_equity * max_pos_pct
        position_size_usd = min(position_size_usd, max_pos_usd)
        
        # Respect available cash
        locked_collateral = sum(
            abs(pos["qty"]) * pos["avg_price"]
            for pos in self.data["positions"].values() if pos["qty"] < 0
        )
        available_cash = self.data["balance"] - locked_collateral
        min_cash_buffer = total_equity * (strategy.get_min_cash_buffer() if strategy else 0.05)
        available_for_trade = available_cash - min_cash_buffer
        
        position_size_usd = min(position_size_usd, available_for_trade)
        
        if position_size_usd < 10:
            return 0.0, f"ATR-sized trade too small (${position_size_usd:.2f})"
        
        logger.info(
            f"[{self.pm_id}] ATR Risk Engine: equity=${total_equity:.0f}, "
            f"risk=${account_risk_usd:.0f}, ATR={atr:.4f}, "
            f"stop_dist=${stop_distance_usd:.4f}, size=${position_size_usd:.0f}"
        )
        return position_size_usd, None

    def calculate_position_size(self, ticker: str, action: str, price: float, confidence: float, allocation_percentage: float, strategy) -> tuple[float, str]:
        """
        Calculates the appropriate trade size based on risk parameters, portfolio state, and strategy limits.
        Returns (trade_amount, error_message).
        If trade_amount > 0, error_message is None.
        If trade_amount == 0, error_message contains the reason for skipping.
        """
        
        # 1. Calculate Total Equity (Cash + Market Value of Positions)
        market_value = 0
        locked_collateral = 0.0
        
        for pos_ticker, pos in self.data["positions"].items():
            qty = pos["qty"]
            if qty > 0:
                market_value += qty * pos["avg_price"]
            else:
                market_value += 0
                locked_collateral += abs(qty) * pos["avg_price"]
            
        total_equity = self.data["balance"] + market_value
        
        # Calculate Available Cash (Dynamic)
        available_cash = self.data["balance"] - locked_collateral
        
        # Get leverage ratio from strategy (default 1.0 = no leverage)
        leverage_ratio = 1.0
        if strategy:
            leverage_ratio = strategy.get_leverage_ratio()
        
        # Calculate buying power (equity * leverage)
        buying_power = total_equity * leverage_ratio
        
        # 2. Determine Target Size with Dynamic Risk Adjustment
        confidence_factor = 1.0
        if confidence >= 90:
            confidence_factor = 1.2 # Boost for very high confidence
        elif confidence >= 80:
            confidence_factor = 1.0
        else:
            confidence_factor = 0.9 # Slight reduction for lower confidence
            
        strategy_modifier = 1.0
        if strategy:
            strategy_modifier = strategy.get_allocation_modifier()
            
        adjusted_allocation = allocation_percentage * confidence_factor * strategy_modifier
        target_size = buying_power * adjusted_allocation
        
        # 3. Apply Safety Limits
        
        # Limit 1: Max Position Size (Strategy Defined)
        max_pos_pct = 0.20 # Default
        if strategy:
            max_pos_pct = strategy.get_max_position_size()
            
        max_position_size = total_equity * max_pos_pct
        
        # If we already hold this position, we need to see how much more we can add
        current_pos_value = 0
        if ticker in self.data["positions"]:
            current_pos_value = abs(self.data["positions"][ticker]["qty"]) * price
            
        remaining_capacity = max_position_size - current_pos_value
        
        # Allow closing/reducing regardless of these limits, but if we are adding:
        # NOTE: action is either "BUY" or "SELL" — we gate both since both open/add positions.
        if action in ("BUY", "SELL"):  # Adding to / opening a position
             if remaining_capacity <= 0:
                 return 0.0, "Max Position Size Reached"
             
             # "Fill the Gap" Logic: 
             # If capacity is positive but tiny (less than min trade size), treat as full.
             if remaining_capacity < 10:
                 return 0.0, "Max Position Size Reached (Gap < Min Trade)"
             
        # Limit 2: Cash Buffer (Strategy Defined)
        min_cash_pct = 0.05 # Default
        if strategy:
            min_cash_pct = strategy.get_min_cash_buffer()
            
        min_cash_buffer = total_equity * min_cash_pct
        
        # Slippage Buffer (NEW): Retain extra 0.5% of cash to cover execution fees/slippage
        slippage_buffer_rate = 0.005
        # We apply this buffer to the available cash itself
        buffered_available_cash = available_cash * (1 - slippage_buffer_rate)

        # Use Dynamic Available Cash for checks
        if leverage_ratio > 1.0:
            # LEVERAGE MODE: Use Buying Power
            # Calculate current total exposure (sum of position values)
            # We use avg_price as approximation since we don't have real-time prices for all assets here
            current_total_exposure = sum(abs(pos["qty"]) * pos["avg_price"] for pos in self.data["positions"].values())
            
            total_max_exposure = total_equity * leverage_ratio
            remaining_buying_power = total_max_exposure - current_total_exposure
            
            # We still need SOME cash for fees (buffer), but we don't limit trade size to cash
            # Warning: In LIVE SPOT trading, this will fail if you don't have the cash.
            # This logic assumes Margin/Perps or Paper Mode.
            if buffered_available_cash <= 0:
                 return 0.0, "Insufficient Cash for Fees"
                 
            available_for_trade = remaining_buying_power
        else:
            # SPOT MODE: Limit to Available Cash
            available_for_trade = buffered_available_cash - min_cash_buffer
        
        if available_for_trade <= 0 and action == "BUY":
             return 0.0, "Insufficient Buying Power"

        # Final Trade Amount Logic
        trade_amount = min(target_size, remaining_capacity, available_for_trade)
        
        # Limit 3: Min Trade Size
        if trade_amount < 10: 
            return 0.0, "Trade Skipped (Amount too small)"
        
        # Limit 4: Leverage Limit Check
        # ONLY check leverage if we are INCREASING risk (Opening/Adding Long or Opening/Adding Short)
        
        # Calculate what the leverage would be AFTER this trade
        # CRITICAL: Use each position's avg_price, not the current trade price!
        total_position_value = sum(abs(pos["qty"]) * pos["avg_price"] for pos in self.data["positions"].values())
        proposed_position_value = total_position_value + trade_amount
        proposed_leverage = proposed_position_value / total_equity if total_equity > 0 else 0
        
        max_leverage = leverage_ratio
        if proposed_leverage > max_leverage:
            return 0.0, f"Trade would exceed max leverage ({proposed_leverage:.2f}x > {max_leverage:.1f}x)"
            
        return trade_amount, None

    def execute_trade(self, ticker: str, action: str, price: float, confidence: float, exit_plan: dict = None, allocation_percentage: float = 0.05, strategy = None, reason: str = None, atr: float = None) -> str:
        """
        Executes a trade and updates the portfolio.
        Returns a descriptive string of the action taken.
        
        For LIVE mode: Delegates actual execution to the executor (JupiterExecutor)
        For PAPER mode: Simulates internally via portfolio JSON updates
        """
        if self.data["balance"] <= 0 and action == "BUY":
            return "Insufficient Funds"
        
        # Get executor (lazy load to avoid circular imports)
        if self._executor is None:
            from backend.services.execution.factory import ExecutorFactory
            self._executor = ExecutorFactory.get_executor(self.pm_id)
            logger.info(f"[{self.pm_id}] Loaded executor: {self._executor.get_mode()} mode")

        # --- RISK MANAGEMENT & SIZING ---
        # Determine if this is a risk-reducing trade (Close Long or Cover Short)
        is_risk_reducing = False
        if ticker in self.data["positions"]:
            pos = self.data["positions"][ticker]
            if action == "SELL" and pos["qty"] > 0:
                is_risk_reducing = True
            elif action == "BUY" and pos["qty"] < 0:
                is_risk_reducing = True
        
        trade_amount = 0.0

        if not is_risk_reducing:
            # --- PYTHON RISK ENGINE ---
            # If ATR is provided, use volatility-normalized sizing (strips LLM authority).
            # Otherwise, fall back to the LLM-suggested allocation_percentage.
            if atr is not None and atr > 0:
                trade_amount, error_msg = self.calculate_atr_position_size(atr, price, strategy)
            else:
                trade_amount, error_msg = self.calculate_position_size(ticker, action, price, confidence, allocation_percentage, strategy)
            if error_msg:
                logger.warning(f"[{self.pm_id}] Trade skipped for {ticker} ({action}): {error_msg}")
                return error_msg

        if action == "BUY":
            # Check if we are covering a short
            if ticker in self.data["positions"] and self.data["positions"][ticker]["qty"] < 0:
                # COVER SHORT
                short_qty = abs(self.data["positions"][ticker]["qty"])
                avg_price = self.data["positions"][ticker]["avg_price"]
                
                # PnL Calculation: (Entry Price - Exit Price) * Qty
                pnl = (avg_price - price) * short_qty
                
                # When we shorted, we sold at avg_price (proceeds)
                # Now we buy back at current price (cost)
                original_proceeds = short_qty * avg_price
                cost_to_cover = short_qty * price
                
                # Add back the original proceeds (what we got when we shorted)
                self.data["balance"] += original_proceeds
                self.add_ledger_entry("TRADE_PROCEEDS", original_proceeds, f"RETURN SHORT PROCEEDS {short_qty:.4f} {ticker} @ ${avg_price:.2f}", ticker)
                
                # Pay to buy back shares
                self.data["balance"] -= cost_to_cover
                self.add_ledger_entry("TRADE_COST", -cost_to_cover, f"COVER {short_qty:.4f} {ticker} @ ${price:.2f}", ticker)
                
                # Realize P&L (already captured in the difference above, but log it for clarity)
                if pnl != 0:
                    self.add_ledger_entry("REALIZED_PNL", pnl, f"Realized P&L on {ticker} short position", ticker)
                
                del self.data["positions"][ticker]
                self.log_trade(ticker, "BUY (COVER)", price, short_qty, confidence)
                self.save_portfolio()
                return f"Covered Short Position (Qty: {short_qty:.4f}, Remaining: 0)"
            
            # Normal Long Buy
            # CRITICAL: Delegate to executor for live mode
            if self._executor.get_mode() == "LIVE":
                # Execute via Jupiter (or other live executor)
                from backend.services.execution.base import ExecutionResult
                
                result: ExecutionResult = self._executor.execute_order(
                    ticker=ticker,
                    action="BUY",
                    amount_usd=trade_amount,
                    current_price=price
                )
                
                if not result.success:
                    logger.error(f"[{self.pm_id}] Live trade failed: {result.error}")
                    return f"Trade Failed: {result.error}"
                
                # Use actual executed values from live trade
                qty = result.executed_qty
                actual_price = result.executed_price
                actual_cost = result.requested_amount
                
                # Deduct actual cost from balance
                self.data["balance"] -= actual_cost
                self.add_ledger_entry(
                    "TRADE_COST", 
                    -actual_cost, 
                    f"LIVE BUY {qty:.4f} {ticker} @ ${actual_price:.2f} (TX: {result.tx_hash})", 
                    ticker
                )
                
                # Log fees separately if present
                if result.fee > 0:
                    fee_usd = result.fee * price  # Approximate SOL fee in USD
                    self.data["balance"] -= fee_usd
                    self.add_ledger_entry(
                        "TRADE_COST",
                        -fee_usd,
                        f"Network fee: {result.fee} SOL",
                        ticker
                    )
                
            else:
                # Paper mode - use simulated price
                qty = trade_amount / price
                actual_price = price
                self.data["balance"] -= trade_amount
                self.add_ledger_entry("TRADE_COST", -trade_amount, f"BUY {qty:.4f} {ticker} @ ${price:.2f}", ticker)
            
            if ticker in self.data["positions"]:
                # Average down/up
                current_qty = self.data["positions"][ticker]["qty"]
                current_avg = self.data["positions"][ticker]["avg_price"]
                new_qty = current_qty + qty
                new_avg = ((current_qty * current_avg) + (qty * actual_price)) / new_qty
                
                # Update position with new qty, avg, and potentially new exit plan
                pos_data = {"qty": new_qty, "avg_price": new_avg}
                if exit_plan:
                    pos_data["exit_plan"] = exit_plan
                else:
                    # Keep existing exit plan if no new one provided
                    pos_data["exit_plan"] = self.data["positions"][ticker].get("exit_plan", {})
                    
                self.data["positions"][ticker] = pos_data
                self.log_trade(ticker, "BUY (ADD)", price, qty, confidence)
                self.save_portfolio()
                return f"Added to Long Position (Added: {qty:.4f}, Total: {new_qty:.4f})"
            else:
                # New Position
                # Validate exit plan before storing
                validated_exit_plan = validate_exit_plan(
                    exit_plan if exit_plan else {}, 
                    actual_price, 
                    is_long=True, 
                    pm_id=self.pm_id
                )
                self.data["positions"][ticker] = {
                    "qty": qty, 
                    "avg_price": actual_price,
                    "exit_plan": validated_exit_plan,
                    "entry_timestamp": datetime.utcnow().isoformat(),  # UTC for server-compat
                    "highest_price": actual_price,
                    "lowest_price": actual_price,
                    "partial_fills": []
                }
                self.log_trade(ticker, "BUY", actual_price, qty, confidence)
                self.save_portfolio()
                return f"Opened Long Position (Qty: {qty:.4f})"

        elif action == "SELL":
            if ticker in self.data["positions"]:
                # Close Long Position
                qty = self.data["positions"][ticker]["qty"]
                avg_price = self.data["positions"][ticker]["avg_price"]
                
                # Calculate available cash for margin checks (needed for short logic)
                locked_collateral = sum(
                    abs(p["qty"]) * p["avg_price"] 
                    for p in self.data["positions"].values() if p["qty"] < 0
                )
                available_cash = self.data["balance"] - locked_collateral
                
                if qty > 0:
                    # CRITICAL: Delegate to executor for live mode
                    if self._executor.get_mode() == "LIVE":
                        from backend.services.execution.base import ExecutionResult
                        
                        # Calculate USD value to sell
                        sell_amount_usd = qty * price
                        
                        result: ExecutionResult = self._executor.execute_order(
                            ticker=ticker,
                            action="SELL",
                            amount_usd=sell_amount_usd,
                            current_price=price
                        )
                        
                        if not result.success:
                            logger.error(f"[{self.pm_id}] Live SELL failed: {result.error}")
                            return f"Trade Failed: {result.error}"
                        
                        # Use actual executed values
                        actual_price = result.executed_price
                        sale_proceeds = result.executed_qty * actual_price
                        pnl = (actual_price - avg_price) * result.executed_qty
                        
                        self.data["balance"] += sale_proceeds
                        self.add_ledger_entry(
                            "TRADE_PROCEEDS", 
                            sale_proceeds, 
                            f"LIVE SELL {result.executed_qty:.4f} {ticker} @ ${actual_price:.2f} (TX: {result.tx_hash})", 
                            ticker
                        )
                        
                        # Log fees
                        if result.fee > 0:
                            fee_usd = result.fee * price
                            self.data["balance"] -= fee_usd
                            self.add_ledger_entry(
                                "TRADE_COST",
                                -fee_usd,
                                f"Network fee: {result.fee} SOL",
                                ticker
                            )
                    else:
                        # Paper mode
                        actual_price = price
                        sale_proceeds = qty * price
                        pnl = (price - avg_price) * qty
                        
                        self.data["balance"] += sale_proceeds
                        reason_suffix = f" ({reason})" if reason else ""
                        self.add_ledger_entry("TRADE_PROCEEDS", sale_proceeds, f"SELL {qty:.4f} {ticker} @ ${price:.2f}{reason_suffix}", ticker)
                    
                    if pnl != 0:
                        self.add_ledger_entry("REALIZED_PNL", pnl, f"Realized P&L on {ticker} long position", ticker)
                    
                    del self.data["positions"][ticker]
                    self.log_trade(ticker, "SELL", price, qty, confidence)
                    self.save_portfolio()
                    return f"Closed Long Position (Sold: {qty:.4f}, Remaining: 0)"
                
                # If we are already short, add to short position
                if qty < 0:
                    # Check margin for new amount
                    if available_cash < trade_amount * 0.5:
                         return "Insufficient Margin to Add Short"
                    
                    add_qty = trade_amount / price
                    current_abs_qty = abs(qty)
                    
                    new_abs_qty = current_abs_qty + add_qty
                    new_avg = ((current_abs_qty * avg_price) + (add_qty * price)) / new_abs_qty
                    
                    pos_data = {
                        "qty": -(new_abs_qty),
                        "avg_price": new_avg,
                        "exit_plan": exit_plan if exit_plan else self.data["positions"][ticker].get("exit_plan", {})
                    }
                    
                    self.data["positions"][ticker] = pos_data
                    self.add_ledger_entry("TRADE_SHORT_ADD", 0, f"SHORT (ADD) {add_qty:.4f} {ticker} @ ${price:.2f}", ticker)
                    self.log_trade(ticker, "SELL (ADD SHORT)", price, add_qty, confidence)
                    self.save_portfolio()
                    return f"Added to Short Position (Added: {add_qty:.4f}, Total: {new_abs_qty:.4f})"
                
                return "Error: Position state mismatch"
            
            # Open Short Position
            # When shorting:
            # 1. We borrow and sell the asset (creating a liability)
            # 2. We need margin to cover potential losses
            # 3. Cash balance should NOT increase - we have a liability to buy back later
            # 4. Total Value = Cash Balance + (Negative Qty * Current Price)
            
            # Calculate available cash for margin check
            locked_collateral = sum(
                abs(p["qty"]) * p["avg_price"] 
                for p in self.data["positions"].values() if p["qty"] < 0
            )
            available_cash = self.data["balance"] - locked_collateral
            
            # Check we have enough margin
            if available_cash < trade_amount * 0.5:  # Require 50% margin
                return "Insufficient Margin for Short"
            
            qty = trade_amount / price
            
            # DO NOT deduct from balance (it's collateral, not a cost)
            # But we DO record it in the ledger for tracking
            self.add_ledger_entry("TRADE_SHORT_OPEN", 0, f"SHORT {qty:.4f} {ticker} @ ${price:.2f} (Margin Reserved)", ticker)
            
            # Validate exit plan before storing
            validated_exit_plan = validate_exit_plan(
                exit_plan if exit_plan else {}, 
                price, 
                is_long=False, 
                pm_id=self.pm_id
            )
            self.data["positions"][ticker] = {
                "qty": -qty, 
                "avg_price": price,
                "exit_plan": validated_exit_plan,
                "entry_timestamp": datetime.utcnow().isoformat(),  # UTC for server-compat
                "highest_price": price,
                "lowest_price": price,
                "partial_fills": []
            }
            self.log_trade(ticker, "SELL (SHORT)", price, qty, confidence)
            self.save_portfolio()
            return f"Opened Short Position (Qty: {qty:.4f})"
            
        return "No Action Taken"

    def log_trade(self, ticker, action, price, qty, confidence):
        self.data["trade_log"].append({
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "action": action,
            "price": price,
            "qty": qty,
            "confidence": confidence
        })
        
    def log_thought(self, message):
        self.data["manager_log"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        self.save_portfolio()

# Portfolio Manager - manages multiple PortfolioService instances
class PortfolioManager:
    def __init__(self):
        self.portfolios = {}
    
    def get_portfolio(self, pm_id: str) -> PortfolioService:
        """Get or create a portfolio service for a PM"""
        if pm_id not in self.portfolios:
            self.portfolios[pm_id] = PortfolioService(pm_id)
        return self.portfolios[pm_id]
    
    def get_all_status(self):
        """Get status of all PMs"""
        # Explicitly load all PMs to ensure they all appear
        all_pm_ids = ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']
        return {
            pm_id: self.get_portfolio(pm_id).get_status()
            for pm_id in all_pm_ids
        }

    def get_all_status_lean(self):
        """Lean version of get_all_status for the /api/portfolio/all polling endpoint.

        Only returns what the frontend 'all PMs' view actually needs:
        - history (downsampled to 200 points max — enough for sparklines and comparison chart)
        - scalar financial metrics (total_value, balance, available_cash, P&L, etc.)
        - is_running flag

        Heavy fields (manager_log, latest_analysis, trade_log, ledger, positions detail,
        current_prices, strategy_info) are intentionally omitted — the individual
        /api/portfolio/status/:pm_id endpoint already serves those.
        """
        all_pm_ids = ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']
        result = {}
        
        # Gather all tickers to fetch live prices
        all_tickers = set()
        for pm_id in all_pm_ids:
            portfolio = self.get_portfolio(pm_id)
            all_tickers.update(portfolio.data.get("positions", {}).keys())
            
        current_prices = {}
        if all_tickers:
            try:
                from backend.services.market_service import get_current_prices
                current_prices = get_current_prices(list(all_tickers))
            except Exception as e:
                import logging
                logging.error(f"Failed to fetch live prices in get_all_status_lean: {e}")

        for pm_id in all_pm_ids:
            portfolio = self.get_portfolio(pm_id)
            d = portfolio.data

            market_value = 0
            total_unrealized_pnl = 0.0
            
            for ticker, pos in d.get("positions", {}).items():
                qty = pos.get("qty", 0)
                avg_price = pos.get("avg_price", 0)
                current_price = current_prices.get(ticker, avg_price)
                
                # Market value & PnL contribution
                if qty > 0:  # LONG
                    market_value += qty * current_price
                    total_unrealized_pnl += (current_price - avg_price) * qty
                else:  # SHORT
                    abs_qty = abs(qty)
                    initial_proceeds = abs_qty * avg_price
                    current_liability = abs_qty * current_price
                    market_value += (initial_proceeds - current_liability)
                    total_unrealized_pnl += (avg_price - current_price) * abs_qty

            balance = d.get("balance", 0)
            total_value = balance + market_value
            initial_capital = d.get("initial_capital", 0)

            # Realized P&L from ledger (fast scan, no price lookup)
            total_realized_pnl = sum(
                e.get("amount", 0)
                for e in d.get("ledger", [])
                if e.get("type") == "REALIZED_PNL"
            )

            # Downsample history to 200 points max — plenty for a sparkline
            history = d.get("history", [])
            if len(history) > 200:
                step = len(history) // 200
                history = history[::step][-200:]

            # Locked collateral (for available_cash)
            locked_collateral = sum(
                abs(pos.get("qty", 0)) * pos.get("avg_price", 0)
                for pos in d.get("positions", {}).values()
                if pos.get("qty", 0) < 0
            )
            available_cash = balance - locked_collateral

            result[pm_id] = {
                "pm_id": pm_id,
                "is_running": d.get("is_running", False),
                "initial_capital": initial_capital,
                "balance": balance,
                "available_cash": available_cash,
                "total_value": total_value,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_realized_pnl": total_realized_pnl,
                "benchmark_return": d.get("benchmark_return"),
                "portfolio_return": d.get("portfolio_return"),
                "vs_benchmark": d.get("vs_benchmark"),
                "history": history,
            }
        return result

    def reload_portfolio(self, pm_id: str) -> PortfolioService:
        """Force-reload a portfolio from disk, discarding in-memory cache."""
        if pm_id in self.portfolios:
            del self.portfolios[pm_id]
        return self.get_portfolio(pm_id)

# Global portfolio manager instance
portfolio_manager = PortfolioManager()
