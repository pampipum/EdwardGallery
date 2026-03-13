import json
import os
from datetime import datetime

PORTFOLIO_FILE = "portfolio.json"

class PortfolioService:
    def __init__(self):
        self.load_portfolio()

    def load_portfolio(self):
        if os.path.exists(PORTFOLIO_FILE):
            with open(PORTFOLIO_FILE, "r") as f:
                self.data = json.load(f)
                # Ensure new keys exist for older files
                if "manager_log" not in self.data:
                    self.data["manager_log"] = []
                if "trade_log" not in self.data:
                    self.data["trade_log"] = []
            
            # Force stop on startup
            self.data["is_running"] = False
        else:
            self.data = {
                "balance": 0,
                "initial_capital": 0,
                "positions": {}, # {ticker: {qty: float, avg_price: float}}
                "history": [], # [{timestamp, total_value}]
                "trade_log": [], # [{timestamp, ticker, action, price, qty}]
                "manager_log": [], # [{timestamp, message}]
                "ledger": [], # [{timestamp, type, amount, description, running_balance}]
                "is_running": False
            }

    def save_portfolio(self):
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    def start_portfolio(self, capital: float):
        self.data["initial_capital"] = capital
        self.data["balance"] = capital
        self.data["positions"] = {}
        self.data["history"] = [{"timestamp": datetime.now().isoformat(), "total_value": capital}]
        self.data["trade_log"] = []
        self.data["manager_log"] = []
        self.data["ledger"] = []
        self.data["is_running"] = True
        
        # Initial deposit ledger entry
        self.add_ledger_entry("DEPOSIT", capital, f"Initial capital deposit", None)
        
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
        market_value = 0
        for ticker, pos in self.data.get("positions", {}).items():
            current_price = current_prices.get(ticker, pos["avg_price"])
            market_value += pos["qty"] * current_price

        total_value = self.data.get("balance", 0) + market_value
        
        return {
            **self.data,
            "positions": positions_with_pnl,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_value": total_value,
            "current_prices": current_prices
        }

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
            total_value += pos["qty"] * price
            
        self.data["history"].append({
            "timestamp": datetime.now().isoformat(),
            "total_value": total_value
        })
        self.save_portfolio()

    def set_latest_analysis(self, analysis_results):
        self.data["latest_analysis"] = analysis_results
        self.save_portfolio()

    def get_latest_analysis(self):
        return self.data.get("latest_analysis", [])

    def execute_trade(self, ticker: str, action: str, price: float, confidence: float, exit_plan: dict = None, allocation_percentage: float = 0.05) -> str:
        """
        Executes a trade and updates the portfolio.
        Returns a descriptive string of the action taken.
        """
        if self.data["balance"] <= 0 and action == "BUY":
            return "Insufficient Funds"

        # --- RISK MANAGEMENT & SIZING ---
        # 1. Calculate Total Equity (Cash + Market Value of Positions)
        market_value = 0
        for pos_ticker, pos in self.data["positions"].items():
            market_value += pos["qty"] * pos["avg_price"] 
            
        total_equity = self.data["balance"] + market_value
        
        # 2. Determine Target Size with Dynamic Risk Adjustment
        # Base allocation comes from AI (e.g., 0.05, 0.10)
        # We adjust it further by confidence score if needed, but the prompt now handles this.
        # Let's enforce the confidence scaling here as a safety double-check.
        
        # Confidence Scaling:
        # 90-100: 100% of allocation
        # 80-89: 90% of allocation
        # 70-79: 80% of allocation
        # < 70: 0% (Should be filtered by caller, but safety first)
        
        confidence_factor = 1.0
        if confidence < 70:
            confidence_factor = 0.0
        elif confidence < 80:
            confidence_factor = 0.8
        elif confidence < 90:
            confidence_factor = 0.9
            
        adjusted_allocation = allocation_percentage * confidence_factor
        target_size = total_equity * adjusted_allocation
        
        # 3. Apply Safety Limits
        # Limit 1: Max Position Size (Hard cap at 20% of Equity)
        max_position_size = total_equity * 0.20
        
        # If we already hold this position, we need to see how much more we can add
        current_pos_value = 0
        if ticker in self.data["positions"]:
            current_pos_value = abs(self.data["positions"][ticker]["qty"]) * price
            
        remaining_capacity = max_position_size - current_pos_value
        
        if remaining_capacity <= 0 and (action == "BUY" or (action == "SELL" and "Short" in action)): # Adding to position
             return "Max Position Size Reached"
             
        # Limit 2: Cash Buffer (Keep 5% in cash)
        min_cash_buffer = total_equity * 0.05
        available_for_trade = self.data["balance"] - min_cash_buffer
        
        if available_for_trade <= 0 and action == "BUY":
             return "Insufficient Cash (Buffer Protected)"

        # Final Trade Amount Logic
        trade_amount = min(target_size, remaining_capacity, available_for_trade)
        
        # Limit 3: Min Trade Size
        if trade_amount < 10: 
            return "Trade Skipped (Amount too small)"

        if action == "BUY":
            # Check if we are covering a short
            if ticker in self.data["positions"] and self.data["positions"][ticker]["qty"] < 0:
                # COVER SHORT
                short_qty = abs(self.data["positions"][ticker]["qty"])
                avg_price = self.data["positions"][ticker]["avg_price"]
                
                # PnL Calculation: (Entry Price - Exit Price) * Qty
                pnl = (avg_price - price) * short_qty
                
                # Pay to buy back shares
                cost_to_cover = short_qty * price
                self.data["balance"] -= cost_to_cover
                self.add_ledger_entry("TRADE_COST", -cost_to_cover, f"COVER {short_qty:.4f} {ticker} @ ${price:.2f}", ticker)
                
                # Realize P&L
                if pnl != 0:
                    self.add_ledger_entry("REALIZED_PNL", pnl, f"Realized P&L on {ticker} short position", ticker)
                
                del self.data["positions"][ticker]
                self.log_trade(ticker, "BUY (COVER)", price, short_qty, confidence)
                return "Covered Short Position"
            
            # Normal Long Buy
            qty = trade_amount / price
            self.data["balance"] -= trade_amount
            self.add_ledger_entry("TRADE_COST", -trade_amount, f"BUY {qty:.4f} {ticker} @ ${price:.2f}", ticker)
            
            if ticker in self.data["positions"]:
                # Average down/up
                current_qty = self.data["positions"][ticker]["qty"]
                current_avg = self.data["positions"][ticker]["avg_price"]
                new_qty = current_qty + qty
                new_avg = ((current_qty * current_avg) + (qty * price)) / new_qty
                
                # Update position with new qty, avg, and potentially new exit plan
                pos_data = {"qty": new_qty, "avg_price": new_avg}
                if exit_plan:
                    pos_data["exit_plan"] = exit_plan
                else:
                    # Keep existing exit plan if no new one provided
                    pos_data["exit_plan"] = self.data["positions"][ticker].get("exit_plan", {})
                    
                self.data["positions"][ticker] = pos_data
                self.log_trade(ticker, "BUY (ADD)", price, qty, confidence)
                return "Added to Long Position"
            else:
                # New Position
                self.data["positions"][ticker] = {
                    "qty": qty, 
                    "avg_price": price,
                    "exit_plan": exit_plan if exit_plan else {}
                }
                self.log_trade(ticker, "BUY", price, qty, confidence)
                return "Opened Long Position"

        elif action == "SELL":
            if ticker in self.data["positions"]:
                # Close Long Position
                qty = self.data["positions"][ticker]["qty"]
                avg_price = self.data["positions"][ticker]["avg_price"]
                if qty > 0:
                    sale_proceeds = qty * price
                    pnl = (price - avg_price) * qty
                    
                    self.data["balance"] += sale_proceeds
                    self.add_ledger_entry("TRADE_PROCEEDS", sale_proceeds, f"SELL {qty:.4f} {ticker} @ ${price:.2f}", ticker)
                    
                    if pnl != 0:
                        self.add_ledger_entry("REALIZED_PNL", pnl, f"Realized P&L on {ticker} long position", ticker)
                    
                    del self.data["positions"][ticker]
                    self.log_trade(ticker, "SELL", price, qty, confidence)
                    return "Closed Long Position"
                
                # If we are already short, maybe add to short? 
                # For now, let's just hold or ignore.
                return "Already Short (No Action)"
            
            # Open Short Position
            # Margin requirement: We need to have enough balance to cover the trade amount
            if self.data["balance"] < trade_amount:
                return "Insufficient Margin for Short"
                
            # When shorting, we receive cash (proceeds) which increases our cash balance.
            # However, we have a negative position (liability).
            # Total Value = Cash Balance + (Negative Qty * Current Price)
            # This correctly reflects the portfolio value.
            
            qty = trade_amount / price
            proceeds = qty * price
            self.data["balance"] += proceeds # Add proceeds to cash
            self.add_ledger_entry("TRADE_PROCEEDS", proceeds, f"SHORT {qty:.4f} {ticker} @ ${price:.2f}", ticker)
            
            self.data["positions"][ticker] = {
                "qty": -qty, 
                "avg_price": price,
                "exit_plan": exit_plan if exit_plan else {}
            }
            self.log_trade(ticker, "SELL (SHORT)", price, qty, confidence)
            return "Opened Short Position"
            
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

portfolio_service = PortfolioService()
