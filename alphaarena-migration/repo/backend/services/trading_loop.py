import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
import json
import re
import google.generativeai as genai
from datetime import datetime, timedelta
from backend.services.data_service import get_top_tickers, get_current_price
from backend.services.analysis_service import analyze_ticker
from backend.services.portfolio_service import portfolio_manager
from backend.services.pm_strategies import get_strategy, PMStrategy
from backend.utils.logger import logger
from backend.utils.scheduler import get_next_scheduled_run_time, is_market_open_day, ET_TIMEZONE
from backend.runtime import paper_only_mode

# Global dictionary to track running loop tasks
pm_loop_tasks = {}

# Valuation logging throttle (for smoother charts)
VALUATION_LOG_INTERVAL = 300  # 5 minutes in seconds
_last_valuation_log = {}  # {pm_id: timestamp}

def run_risk_check(pm_id: str, strategy: PMStrategy, current_prices: dict = None):
    """
    FAST LOOP: Checks existing positions for Stop Loss / Target hits.
    Runs frequently (e.g., every minute).
    Also logs portfolio valuation every 5 minutes for smoother charts.
    """
    global _last_valuation_log
    
    portfolio_service = portfolio_manager.get_portfolio(pm_id)
    
    # 1. Optimization: Check if we have any positions first
    status = portfolio_service.get_status()
    existing_positions = status.get("positions", {})
    
    # 2. Periodic Valuation Logging (for smoother charts)
    # Log every VALUATION_LOG_INTERVAL seconds, even without positions
    current_time = time.time()
    last_log_time = _last_valuation_log.get(pm_id, 0)
    
    if current_time - last_log_time >= VALUATION_LOG_INTERVAL:
        # Fetch prices if not provided and we have positions
        if existing_positions:
            if current_prices is None:
                held_tickers = list(existing_positions.keys())
                valuation_prices = {t: get_current_price(t) for t in held_tickers}
            else:
                valuation_prices = current_prices.copy()
                # Fetch any missing held tickers
                missing = [t for t in existing_positions.keys() if t not in valuation_prices]
                for t in missing:
                    p = get_current_price(t)
                    if p:
                        valuation_prices[t] = p
        else:
            valuation_prices = {}
        
        portfolio_service.update_valuation(valuation_prices)
        _last_valuation_log[pm_id] = current_time
        logger.debug(f"[{pm_id}] Logged valuation for chart (value: ${status.get('total_value', 0):.2f})")
    
    if not existing_positions:
        return

    # logger.debug(f"[{datetime.now()}] Risk Check ({pm_id}): Monitoring {len(existing_positions)} positions...")

    # 3. Get current prices for held assets only (for risk check)
    held_tickers = list(existing_positions.keys())
    held_prices = {}
    
    if current_prices:
        held_prices = current_prices.copy()
        # Fetch missing prices for held assets if not in current_prices (e.g. not in top list)
        missing_tickers = [t for t in held_tickers if t not in held_prices]
        for t in missing_tickers:
            p = get_current_price(t)
            if p:
                held_prices[t] = p
    else:
        held_prices = {t: get_current_price(t) for t in held_tickers}
    
    for ticker, pos in existing_positions.items():
        current_price = held_prices.get(ticker)
        if not current_price: continue
        
        exit_plan = pos.get("exit_plan", {})
        stop_loss = exit_plan.get("stop_loss")
        target_price = exit_plan.get("target_price")
        qty = pos["qty"]
        
        exit_action = None
        exit_reason = ""
        
        if qty > 0: # LONG
            if stop_loss and current_price <= stop_loss:
                exit_action = "SELL"
                exit_reason = f"Stop Loss Hit ({current_price} <= {stop_loss})"
            elif target_price and current_price >= target_price:
                exit_action = "SELL"
                exit_reason = f"Target Price Hit ({current_price} >= {target_price})"
        elif qty < 0: # SHORT
            if stop_loss and current_price >= stop_loss:
                exit_action = "BUY"
                exit_reason = f"Stop Loss Hit ({current_price} >= {stop_loss})"
            elif target_price and current_price <= target_price:
                exit_action = "BUY"
                exit_reason = f"Target Price Hit ({current_price} <= {target_price})"
        
        if exit_action:
            logger.info(f"[{pm_id}] AUTOMATIC EXIT: {ticker} - {exit_reason}")
            # Execute the trade
            result = portfolio_service.execute_trade(ticker, exit_action, current_price, 10.0) # Max confidence for auto-exit
            
            # Log to Manager Log immediately for visibility
            portfolio_service.log_thought(f"**AUTOMATIC EXIT EXECUTED**\n\nAsset: {ticker}\nAction: {exit_action}\nReason: {exit_reason}\nPrice: ${current_price:.2f}\nResult: {result}")
            
            # Skip remaining checks if position was closed
            continue

        # --- ADVANCED EXIT MECHANISMS ---
        # Only proceed if position still exists (wasn't closed above)
        if ticker not in portfolio_service.data["positions"]:
            continue
        
        # 1. Update Extremes (Highest/Lowest Price)
        update_position_extremes(portfolio_service, ticker, current_price)
        
        # 2. Check Partial Targets
        partial_targets = exit_plan.get("partial_targets", [])
        # Also check strategy defaults if not present? No, stick to specific plan.
        
        if partial_targets:
            check_partial_targets(portfolio_service, ticker, pos, current_price, partial_targets)
            
        # 3. Check Trailing Stop
        trailing_stop_config = exit_plan.get("trailing_stop")
        if trailing_stop_config and trailing_stop_config.get("enabled"):
            check_trailing_stop(portfolio_service, ticker, pos, current_price, trailing_stop_config)
            
        # 4. Check Time-Based Exit
        time_exit_config = exit_plan.get("time_exit")
        if time_exit_config:
            check_time_exit(portfolio_service, ticker, pos, current_price, time_exit_config)

def update_position_extremes(portfolio_service, ticker, current_price):
    """Updates the highest/lowest price seen since entry."""
    pos = portfolio_service.data["positions"].get(ticker)
    if not pos: return
    
    changed = False
    if "highest_price" not in pos:
        pos["highest_price"] = pos["avg_price"]
        changed = True
    if "lowest_price" not in pos:
        pos["lowest_price"] = pos["avg_price"]
        changed = True
        
    if current_price > pos["highest_price"]:
        pos["highest_price"] = current_price
        changed = True
    if current_price < pos["lowest_price"]:
        pos["lowest_price"] = current_price
        changed = True
        
    if changed:
        portfolio_service.save_portfolio()

def check_partial_targets(portfolio_service, ticker, pos, current_price, targets):
    """Checks and executes partial profit taking."""
    qty = pos["qty"]
    avg_price = pos["avg_price"]
    
    # Filter targets that haven't been hit yet
    # We need a way to track which targets are hit. 
    # We can check if we have enough partial_fills matching this target?
    # Or simpler: Modify the target in the exit_plan to mark it as 'filled'.
    # Since we can't easily modify the deep dict in the loop without saving, 
    # we'll read, modify, save.
    
    exit_plan = pos.get("exit_plan", {})
    updated_targets = False
    
    for target in targets:
        if target.get("filled"):
            continue
            
        target_price = target.get("price")
        percentage = target.get("percentage")
        
        hit = False
        if qty > 0: # LONG
            if current_price >= target_price:
                hit = True
        elif qty < 0: # SHORT
            if current_price <= target_price:
                hit = True
                
        if hit:
            logger.info(f"PARTIAL TARGET HIT for {ticker} at {current_price}")
            reason = f"Partial Target: {target.get('reasoning', 'Target Hit')}"
            result = portfolio_service.execute_partial_close(ticker, percentage, current_price, reason)
            
            # Only mark as filled if execution was successful
            if result and "Executed" in result:
                target["filled"] = True
                updated_targets = True
                
                # Log to manager_log for visibility
                pnl_pct = ((current_price - avg_price) / avg_price * 100) if qty > 0 else ((avg_price - current_price) / avg_price * 100)
                portfolio_service.log_thought(
                    f"**PARTIAL PROFIT TAKEN**\n\n"
                    f"Asset: {ticker}\n"
                    f"Target: ${target_price:.2f} | Current: ${current_price:.2f}\n"
                    f"Sold: {percentage:.0%} of position\n"
                    f"P&L: {pnl_pct:+.2f}%\n"
                    f"Reason: {target.get('reasoning', 'Target reached')}"
                )
            else:
                logger.warning(f"Partial close failed for {ticker}: {result}")
            
    if updated_targets:
        # Save the updated filled status
        portfolio_service.data["positions"][ticker]["exit_plan"]["partial_targets"] = targets
        portfolio_service.save_portfolio()

def check_trailing_stop(portfolio_service, ticker, pos, current_price, config):
    """Checks and executes trailing stop loss."""
    qty = pos["qty"]
    avg_price = pos["avg_price"]
    highest = pos.get("highest_price", avg_price)
    lowest = pos.get("lowest_price", avg_price)
    
    trail_type = config.get("type", "percentage")
    trail_value = config.get("value", 0.05) # e.g. 0.05 for 5%
    activation_profit = config.get("activation_profit", 0.0) # Only start trailing after X% profit
    
    # Calculate current profit pct
    profit_pct = 0
    if qty > 0:
        profit_pct = (current_price - avg_price) / avg_price
    else:
        profit_pct = (avg_price - current_price) / avg_price
        
    # Check activation
    if profit_pct < activation_profit:
        return
        
    # Calculate Dynamic Stop Price
    stop_price = 0
    if qty > 0: # LONG
        # Stop is X% below HIGHEST price seen
        stop_price = highest * (1 - trail_value)
        
        if current_price <= stop_price:
            logger.info(f"TRAILING STOP HIT for {ticker} at {current_price} (High: {highest}, Stop: {stop_price})")
            result = portfolio_service.execute_trade(ticker, "SELL", current_price, 10.0, reason="Trailing Stop Hit")
            
            # Log to manager_log for visibility
            pnl_pct = (current_price - avg_price) / avg_price * 100
            portfolio_service.log_thought(
                f"**TRAILING STOP HIT**\n\n"
                f"Asset: {ticker}\n"
                f"Entry: ${avg_price:.2f} | Exit: ${current_price:.2f}\n"
                f"High Water Mark: ${highest:.2f}\n"
                f"Trail: {trail_value:.1%} below high\n"
                f"Stop Triggered: ${stop_price:.2f}\n"
                f"P&L: {pnl_pct:+.2f}%\n"
                f"Result: {result}"
            )
            
    else: # SHORT
        # Stop is X% above LOWEST price seen
        stop_price = lowest * (1 + trail_value)
        
        if current_price >= stop_price:
            logger.info(f"TRAILING STOP HIT for {ticker} at {current_price} (Low: {lowest}, Stop: {stop_price})")
            result = portfolio_service.execute_trade(ticker, "BUY", current_price, 10.0, reason="Trailing Stop Hit")
            
            # Log to manager_log for visibility
            pnl_pct = (avg_price - current_price) / avg_price * 100
            portfolio_service.log_thought(
                f"**TRAILING STOP HIT (SHORT)**\n\n"
                f"Asset: {ticker}\n"
                f"Entry: ${avg_price:.2f} | Exit: ${current_price:.2f}\n"
                f"Low Water Mark: ${lowest:.2f}\n"
                f"Trail: {trail_value:.1%} above low\n"
                f"Stop Triggered: ${stop_price:.2f}\n"
                f"P&L: {pnl_pct:+.2f}%\n"
                f"Result: {result}"
            )

def check_time_exit(portfolio_service, ticker, pos, current_price, config):
    """Checks if position has exceeded max hold time."""
    entry_time_str = pos.get("entry_timestamp")
    if not entry_time_str:
        return
        
    entry_time = datetime.fromisoformat(entry_time_str)
    max_days = config.get("max_hold_days")
    
    if not max_days:
        return
    
    # Use UTC consistently — entry_timestamp is stored as UTC via datetime.utcnow()
    entry_time_utc = entry_time.replace(tzinfo=None)  # strip any tz info, treat as UTC
    age = datetime.utcnow() - entry_time_utc
    
    if age.days >= max_days:
        logger.info(f"TIME EXIT for {ticker} (Held {age.days} days, Max {max_days})")
        action = "SELL" if pos["qty"] > 0 else "BUY"
        avg_price = pos["avg_price"]
        result = portfolio_service.execute_trade(ticker, action, current_price, 10.0, reason=f"Time Exit: Held > {max_days} days")
        
        # Log to manager_log for visibility
        pnl_pct = ((current_price - avg_price) / avg_price * 100) if pos["qty"] > 0 else ((avg_price - current_price) / avg_price * 100)
        portfolio_service.log_thought(
            f"**TIME-BASED EXIT**\n\n"
            f"Asset: {ticker}\n"
            f"Entry: ${avg_price:.2f} | Exit: ${current_price:.2f}\n"
            f"Holding Period: {age.days} days (max allowed: {max_days})\n"
            f"P&L: {pnl_pct:+.2f}%\n"
            f"Result: {result}"
        )


def execute_mirror_strategy(target_pm_id: str, source_pm_id: str):
    """
    Syncs target_pm to match source_pm's position allocations exactly.
    """
    target_portfolio = portfolio_manager.get_portfolio(target_pm_id)
    source_portfolio = portfolio_manager.get_portfolio(source_pm_id)
    
    source_status = source_portfolio.get_status()
    target_status = target_portfolio.get_status()
    
    source_total_value = source_status.get("total_value", 1.0) # Avoid div by zero
    target_total_value = target_status.get("total_value", 0.0)
    
    if source_total_value <= 0 or target_total_value <= 0:
        logger.warning(f"[{target_pm_id}] Cannot mirror {source_pm_id}: Invalid portfolio value.")
        return

    logger.info(f"[{target_pm_id}] MIRROR SYNC: Matching {source_pm_id}...")
    
    # 1. Map Source Allocations
    # {ticker: target_weight}
    target_allocations = {}
    
    source_positions = source_status.get("positions", {})
    for ticker, pos in source_positions.items():
        # Calculate weight in source portfolio
        # Value = qty * current_price (or avg if current missing)
        p = pos.get("current_price", pos["avg_price"])
        val = abs(pos["qty"]) * p # Absolute exposure weight
        
        # Use SIGNED weight to handle shorts? 
        # Easier to carry over the sign of qty to know if we want Long or Short
        weight = val / source_total_value
        if pos["qty"] < 0:
            weight = -weight
            
        target_allocations[ticker] = weight
        
    # 2. Sync Target Positions
    # First, handle assets waiting to be synced (Target doesn't have, or has wrong amount)
    
    # Get all tickers involved (Union of both portfolios)
    target_positions = target_status.get("positions", {})
    all_tickers = set(target_allocations.keys()).union(set(target_positions.keys()))
    
    current_prices = source_status.get("current_prices", {})
    if not current_prices:
        # Fetch if missing (unlikely if source just updated)
         from backend.services.market_service import get_current_prices
         current_prices = get_current_prices(list(all_tickers))

    for ticker in all_tickers:
        # Desired weight (0 if not in source)
        desired_weight = target_allocations.get(ticker, 0.0)
        
        # Current status
        current_pos = target_positions.get(ticker)
        current_qty = current_pos["qty"] if current_pos else 0.0
        
        price = current_prices.get(ticker)
        if not price and current_pos: price = current_pos["avg_price"]
        if not price: 
            logger.warning(f"[{target_pm_id}] Skipping {ticker} - No price found.")
            continue
            
        current_val = abs(current_qty) * price
        current_weight = current_val / target_total_value
        if current_qty < 0: current_weight = -current_weight
        
        # Threshold for action (reduce noise)
        # If weight difference is < 1%, skip
        if abs(desired_weight - current_weight) < 0.01:
            continue
            
        # Calculate Action
        # Desired Value = desired_weight * target_total_value
        # (Using absolute total value for sizing base)
        desired_value_usd = abs(desired_weight) * target_total_value
        
        # Determine direction
        target_is_long = desired_weight > 0
        target_is_short = desired_weight < 0
        
        # Execute
        
        # CASE 1: CLOSE / REDUCE
        # If we have it but don't want it (or want less/opposite)
        if current_qty != 0:
            # Check if we need to flip side (Long -> Short or Short -> Long)
            # OR if we just need to zero it out
            if (current_qty > 0 and not target_is_long) or (current_qty < 0 and not target_is_short):
                # Close entire position first
                action = "SELL" if current_qty > 0 else "BUY"
                amt = 10.0 # meaningless for close
                res = target_portfolio.execute_trade(ticker, action, price, 10.0, allocation_percentage=0.0) # Allocation 0 means close all usually? No, update execute_trade logic if needed.
                # Actually execute_trade "SELL" on Long closes all if we don't specify valid size? 
                # Wait, execute_trade "SELL" closes all if we pass logic correctly?
                # Let's use the explicit `execute_trade` logic:
                # To close all: we need to pass the right params or loop?
                # `execute_trade` logic: 
                # if action="SELL" and existing Long: checks amount.
                # If we want to CLOSE ALL, we should probably check `portfolio_service.execute_trade` details.
                # It doesn't have a "Close All" flag. It takes `allocation_percentage`. 
                # Re-reading `execute_trade` in `portfolio_service.py`:
                # It calculates amount based on percentage of EQUITY.
                # To close specific amount: "SELL" logic handles `trade_amount`.
                # Wait, `execute_trade` calls `calculate_position_size` which returns amount to ADD.
                # But for CLOSING, `execute_trade` (L708) calculates `qty = ...`.
                # Wait, `execute_trade` L721: "if qty > 0: ... sell_amount_usd = qty * price". 
                # It seems `execute_trade` closes the ENTIRE position if action is SELL and it's Long?
                # L711: `qty = positions[ticker]["qty"]`. 
                # Yes, it looks like `execute_trade` with "SELL" defaults to closing the whole position.
                
                target_portfolio.execute_trade(ticker, action, price, 10.0, reason="Mirror Sync: Close")
                current_qty = 0 # Updated
            
            # If we match side but need to reduce
            # (Logic for reducing is missing in simple `execute_trade` - it usually closes all)
            # For Mirroring V1: Simplification -> If weight mismatch > 5%, Close and Re-open? 
            # Or assume `execute_trade` only supports "Add" or "Close All".
            # The current `execute_trade` implementation is "All or Nothing" for exits based on my brief read. 
            # (L776 `del self.data["positions"][ticker]`).
            # SO: If we need to adjustment size, we CLOSE ALL then OPEN NEW.
            # Inefficient but accurate.
            
            if current_qty != 0 and abs(current_weight) > abs(desired_weight) * 1.05:
                 # We have too much. Close all and re-enter.
                 action = "SELL" if current_qty > 0 else "BUY"
                 target_portfolio.execute_trade(ticker, action, price, 10.0, reason="Mirror Sync: Rebalancing (Too Large)")
                 current_qty = 0
                 
        # CASE 2: OPEN / ADD
        if current_qty == 0 and desired_weight != 0:
            # Open new position
            action = "BUY" if target_is_long else "SELL" # SELL for Short Open
            # Allocation is |desired_weight|
            alloc_pct = abs(desired_weight)
            
            # Override strategy params potentially? 
            # We pass `strategy=None` to avoid "Max Position" checks? 
            # No, keep checks for safety. But PM7 should have same limits as PM1 ideally.
            
            target_portfolio.execute_trade(ticker, action, price, 10.0, allocation_percentage=alloc_pct, reason="Mirror Sync: Open")

    logger.info(f"[{target_pm_id}] Mirror Sync Complete.")

def generate_analyst_report_for_asset(ticker: str, portfolio_service, strategy, portfolio_snapshot: dict = None) -> dict:
    """
    Generate analyst report for a single asset (to be run in parallel).
    Accepts an optional pre-computed portfolio_snapshot to avoid redundant
    get_status() calls from within the thread pool workers.
    """
    try:
        # Get current price
        price = get_current_price(ticker)

        # Use pre-computed snapshot if available (avoids N get_status() calls)
        if portfolio_snapshot is not None:
            positions = portfolio_snapshot.get("positions", {})
        else:
            positions = portfolio_service.get_status().get("positions", {})

        current_pos_data = positions.get(ticker)
        
        current_pos_str = "None"
        if current_pos_data:
            qty = current_pos_data["qty"]
            if qty > 0:
                current_pos_str = f"Long ({qty:.4f} units)"
            elif qty < 0:
                current_pos_str = f"Short ({abs(qty):.4f} units)"
        
        logger.info(f"[{strategy.name}] Analyzing {ticker} (Holding: {current_pos_str})...")
        
        # This will use the analyst cache if available
        analysis = analyze_ticker(ticker, current_position=current_pos_str, strategy=strategy, skip_pm=True)
        
        if "error" in analysis:
            return None
            
        return {
            "ticker": ticker,
            "price": price,
            "analysis": analysis,
            "current_position": current_pos_str
        }
    except Exception as e:
        logger.error(f"Error analyzing {ticker}: {e}")
        return None

def run_market_analysis(pm_id: str = 'pm1'):
    """
    SLOW LOOP: Performs deep AI analysis with PARALLEL analyst report generation.
    """
    strategy = get_strategy(pm_id)
    portfolio_service = portfolio_manager.get_portfolio(pm_id)
    
    logger.info(f"[{datetime.now()}] Starting Market Analysis for {strategy.name} ({pm_id})...")
    
    tickers = get_top_tickers()
    
    # Determine which assets to trade based on the day
    # We use the current time in ET to determine the "market day"
    current_et = datetime.now(ET_TIMEZONE)
    is_weekday = is_market_open_day(current_et)
    
    target_assets = tickers['crypto'] # Crypto always trades
    
    if is_weekday:
        target_assets += tickers['stocks']
        logger.info(f"[{pm_id}] Weekday detected: Analyzing Stocks + Crypto")
    else:
        logger.info(f"[{pm_id}] Weekend detected: Analyzing Crypto ONLY")
    
    
    # ===== PHASE 1: Generate ALL Analyst Reports in PARALLEL =====
    logger.info(f"[{pm_id}] Phase 1: Generating analyst reports for {len(target_assets)} assets in parallel...")

    # Snapshot portfolio status ONCE here — avoids N redundant get_status() calls
    # from inside the thread pool (one per ticker worker).
    portfolio_snapshot = portfolio_service.get_status()

    all_reports = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks, passing the snapshot in
        future_to_ticker = {
            executor.submit(
                generate_analyst_report_for_asset, ticker, portfolio_service, strategy, portfolio_snapshot
            ): ticker
            for ticker in target_assets
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result = future.result()
                if result:
                    all_reports.append(result)
            except Exception as e:
                logger.error(f"[{pm_id}] Error processing {ticker}: {e}")
    
    logger.info(f"[{pm_id}] Phase 1 Complete: Generated {len(all_reports)} analyst reports")
    
    # Save all analyses for frontend display
    portfolio_service.set_latest_analysis([r["analysis"] for r in all_reports])

    # Build a compact candidate set for Phase 2 to control token/CLI payload size.
    # Include held assets plus only "interesting" opportunities.
    def _is_interesting(report: dict) -> tuple[bool, int, str]:
        analysis = report.get("analysis", {})
        summary = analysis.get("summary", {})
        technical = analysis.get("technical_context", {})

        ticker = report.get("ticker", "?")
        is_held = bool(report.get("current_position") and report.get("current_position") != "None")

        score = 0
        reasons = []

        # Always prioritize existing holdings for active management.
        if is_held:
            score += 100
            reasons.append("held")

        # PM/analyst summary signals
        action_type = str(summary.get("action_type", "")).upper()
        decision = str(summary.get("decision", "")).upper()
        confidence = float(summary.get("confidence_score", 0) or 0)
        alloc = float(summary.get("allocation_percentage", 0) or 0)
        turn_prob = float(summary.get("turn_probability", 0) or 0)
        trend = str(summary.get("current_trend", ""))

        if action_type and action_type != "WAIT":
            score += 60
            reasons.append(f"action={action_type}")
        if decision and decision != "WAIT":
            score += 40
            reasons.append(f"decision={decision}")
        if confidence >= 7:
            score += 25
            reasons.append(f"conf={confidence:.1f}")
        if alloc > 0:
            score += 20
            reasons.append(f"alloc={alloc:.2f}")
        if turn_prob >= 25:
            score += 20
            reasons.append(f"turn_prob={turn_prob:.0f}")

        # Technical spark detection
        momentum = str(technical.get("momentum", ""))
        volume = str(technical.get("volume", ""))

        rsi = None
        rsi_match = re.search(r"RSI:\s*([\d.]+)", momentum)
        if rsi_match:
            try:
                rsi = float(rsi_match.group(1))
            except Exception:
                rsi = None
        if rsi is not None and (rsi < 30 or rsi > 70):
            score += 20
            reasons.append(f"rsi={rsi:.1f}")

        vol_ratio = None
        vol_match = re.search(r"Ratio:\s*([\d.]+)", volume)
        if vol_match:
            try:
                vol_ratio = float(vol_match.group(1))
            except Exception:
                vol_ratio = None
        if vol_ratio is not None and vol_ratio >= 1.5:
            score += 15
            reasons.append(f"rvol={vol_ratio:.2f}")

        if trend in ("Bullish", "Bearish"):
            score += 10
            reasons.append(f"trend={trend}")

        interesting = score >= 15
        why = ", ".join(reasons) if reasons else "normal"
        return interesting, score, f"{ticker}: {why}"

    ranked_candidates = []
    for report in all_reports:
        interesting, score, reason = _is_interesting(report)
        if interesting:
            ranked_candidates.append((score, report, reason))

    # Fallback: if nothing scores as interesting, keep top-3 by confidence so PM still has context.
    if not ranked_candidates:
        def _confidence(r):
            s = r.get("analysis", {}).get("summary", {})
            try:
                return float(s.get("confidence_score", 0) or 0)
            except Exception:
                return 0.0
        fallback = sorted(all_reports, key=_confidence, reverse=True)[:3]
        ranked_candidates = [(0, r, f"{r.get('ticker')}: fallback_top_conf") for r in fallback]

    # Keep payload bounded and ensure enough context for portfolio-level reasoning.
    MIN_PHASE2_REPORTS = 2
    MAX_PHASE2_REPORTS = 4
    ranked_candidates.sort(key=lambda x: x[0], reverse=True)

    selected = ranked_candidates[:MAX_PHASE2_REPORTS]

    # If too few interesting assets, backfill by confidence from the remaining universe.
    if len(selected) < MIN_PHASE2_REPORTS:
        selected_tickers = {item[1].get("ticker") for item in selected}

        def _confidence(r):
            s = r.get("analysis", {}).get("summary", {})
            try:
                return float(s.get("confidence_score", 0) or 0)
            except Exception:
                return 0.0

        remaining = [r for r in all_reports if r.get("ticker") not in selected_tickers]
        backfill = sorted(remaining, key=_confidence, reverse=True)

        for r in backfill:
            if len(selected) >= MIN_PHASE2_REPORTS:
                break
            selected.append((0, r, f"{r.get('ticker')}: backfill_top_conf"))

    candidate_reports = [item[1] for item in selected]

    logger.info(
        f"[{pm_id}] Phase 2 candidate filter: {len(all_reports)} total -> "
        f"{len(candidate_reports)} selected (target {MIN_PHASE2_REPORTS}-{MAX_PHASE2_REPORTS}) | "
        f"{"; ".join(item[2] for item in selected)}"
    )

    # ===== TECHNICAL SENTINEL GATE (Cost Control) =====
    should_call_llm, gate_reason = strategy.check_sentinel_triggers(all_reports, portfolio_snapshot)

    # Option A: In PAPER mode, do not block Phase 2 portfolio decisions.
    # We still log the sentinel result for observability.
    pm_is_paper = paper_only_mode()
    if pm_is_paper and not should_call_llm:
        logger.info(f"[{pm_id}] 🛡️ Sentinel advisory (PAPER mode bypass): {gate_reason}")
        portfolio_service.log_thought(
            f"🛡️ **SENTINEL ADVISORY (PAPER BYPASS)**: {gate_reason}\n\n"
            f"Continuing to Phase 2 for paper-mode decisioning."
        )

    elif not should_call_llm:
        logger.info(f"[{pm_id}] 🛡️ Sentinel Gate: {gate_reason}")
        # Log to thought history so user knows why no trades happened
        portfolio_service.log_thought(f"🛡️ **SENTINEL GATE ACTIVE**: {gate_reason}\n\nMarket analysis skipped to conserve API resources.")

        # Still run risk check at the end using fresh technical data
        current_prices = {r["ticker"]: r["price"] for r in all_reports}
        portfolio_service.update_valuation(current_prices)
        run_risk_check(pm_id, strategy, current_prices)
        return

    # ===== PHASE 2: PM Makes Portfolio-Level Decisions =====
    logger.info(f"[{pm_id}] Phase 2: PM reviewing all reports and making decisions...")
    
    # Call new portfolio-level decision function
    from backend.services.ai_service import generate_portfolio_decisions
    
    # COMPETITOR INTELLIGENCE (For PM5)
    competitor_data = None
    if pm_id == 'pm5':
        competitor_data = {}
        my_holdings = set(portfolio_service.get_status().get("positions", {}).keys())
        
        # from datetime import datetime, timedelta (Already imported globally)
        
        for rival_id in ['pm1', 'pm2', 'pm3', 'pm4']:
            try:
                rival_portfolio = portfolio_manager.get_portfolio(rival_id)
                rival_status = rival_portfolio.get_status()
                rival_history = rival_portfolio.data.get("history", [])
                
                # Calculate Performance (30D & 90D)
                # Helper to find value X days ago
                def get_past_value(days_ago):
                    target_time = datetime.now() - timedelta(days=days_ago)
                    # Find closest history point
                    closest_val = None
                    if rival_history:
                        # Sort by timestamp just in case
                        # rival_history.sort(key=lambda x: x["timestamp"]) 
                        # Assuming chronological append, we search backwards
                        for point in reversed(rival_history):
                            pt_time = datetime.fromisoformat(point["timestamp"])
                            if pt_time <= target_time:
                                closest_val = point["total_value"]
                                break
                        # If no history old enough, use first point
                        if closest_val is None and rival_history:
                            closest_val = rival_history[0]["total_value"]
                    return closest_val

                current_val = rival_status.get("total_value", 0)
                val_30d = get_past_value(30)
                val_90d = get_past_value(90)
                
                perf_30d = ((current_val - val_30d) / val_30d) if val_30d and val_30d > 0 else 0.0
                perf_90d = ((current_val - val_90d) / val_90d) if val_90d and val_90d > 0 else 0.0
                
                # Calculate Drawdown
                # Max value ever
                max_val = 0
                if rival_history:
                    max_val = max(h["total_value"] for h in rival_history)
                drawdown = ((current_val - max_val) / max_val) if max_val > 0 else 0.0
                
                # Calculate Overlap
                rival_holdings = set(rival_status.get("positions", {}).keys())
                overlap = list(my_holdings.intersection(rival_holdings))
                
                competitor_data[rival_id] = {
                    "total_value": current_val,
                    "positions": list(rival_holdings),
                    "perf_30d": f"{perf_30d:.1%}",
                    "perf_90d": f"{perf_90d:.1%}",
                    "drawdown": f"{drawdown:.1%}",
                    "overlap_assets": overlap,
                    "is_crowded": len(overlap) > 0 # Simple check
                }
            except Exception as e:
                logger.error(f"[{pm_id}] Error analyzing rival {rival_id}: {e}")
                pass
        
        # Calculate SYSTEM CROWDING SCORE for PM5
        # Count how many PMs hold each asset
        asset_counts = {}
        for r_id, r_data in competitor_data.items():
            for asset in r_data.get("positions", []):
                asset_counts[asset] = asset_counts.get(asset, 0) + 1
        
        # Add high-crowding assets to competitor_data summary
        crowded_assets = [asset for asset, count in asset_counts.items() if count >= 2]
        competitor_data["GLOBAL_CROWDING"] = {
            "crowded_assets": crowded_assets,
            "details": "Assets held by 2+ rivals"
        }

        logger.info(f"[{pm_id}] Competitor Intelligence gathered for {len(competitor_data)-1} rivals.")

    pm_decisions = generate_portfolio_decisions(
        all_reports=candidate_reports,
        portfolio_state=portfolio_service.get_status(),
        strategy=strategy,
        competitor_data=competitor_data,
        is_weekend=not is_weekday  # Pass weekend flag to PM prompt
    )
    
    # ===== PHASE 3: Execute Trades in Priority Order =====
    # Handle AI failure gracefully (e.g., 429 quota errors)
    if pm_decisions is None:
        logger.error(f"[{pm_id}] AI failed to generate portfolio decisions. Skipping trade execution.")
        portfolio_service.log_thought("⚠️ AI Analysis failed (quota exceeded or API error). No trades executed this cycle.")
        return

    # Import CRO (lazy to avoid circular imports at module level)
    from backend.services.cro_service import cro_approve_trade

    logger.info(f"[{pm_id}] Phase 3: Executing {len(pm_decisions.get('trades', []))} trades...")

    decisions = []
    for trade in pm_decisions.get("trades", []):
        ticker = trade["ticker"]
        action_type = trade["action"]  # OPEN_LONG, ADD_LONG, etc.
        confidence = trade["confidence"]
        allocation = trade["allocation_percentage"]
        exit_plan = trade.get("exit_plan", {})

        # Map action_type to BUY/SELL
        trade_action = "WAIT"
        if action_type in ["OPEN_LONG", "ADD_LONG", "COVER_SHORT"]:
            trade_action = "BUY"
        elif action_type in ["OPEN_SHORT", "ADD_SHORT", "CLOSE_LONG"]:
            trade_action = "SELL"

        if trade_action == "WAIT":
            continue

        # Find the price from our reports
        price = next((r["price"] for r in all_reports if r["ticker"] == ticker), None)
        if not price:
            price = get_current_price(ticker)

        # --- Extract ATR for the Python Risk Engine ---
        # Reverse-engineer ATR from the analyst-supplied stop_loss level if available.
        atr_value = None
        matching_report = next((r for r in all_reports if r["ticker"] == ticker), None)
        if matching_report and price:
            try:
                setup = matching_report.get("analysis", {}).get("trade_setup")
                if setup and setup.get("stop_loss"):
                    implied_stop_dist = abs(price - float(setup["stop_loss"]))
                    if implied_stop_dist > 0:
                        atr_value = implied_stop_dist / 1.5  # Reverse of stop = 1.5 * ATR
            except Exception:
                pass

        # Check confidence threshold
        if confidence >= strategy.get_confidence_threshold():

            # --- CRO VETO CHECK (only for new position openings) ---
            is_opening = action_type in ["OPEN_LONG", "OPEN_SHORT"]
            if is_opening and price:
                total_val = portfolio_service.get_status().get("total_value", 0)
                estimated_usd = total_val * allocation
                cro_ok, cro_reason = cro_approve_trade(
                    pm_id=pm_id,
                    ticker=ticker,
                    action=trade_action,
                    estimated_usd=estimated_usd,
                    all_portfolios=portfolio_manager
                )
                if not cro_ok:
                    logger.warning(f"[{pm_id}] CRO VETOED {action_type} {ticker}: {cro_reason}")
                    portfolio_service.log_thought(
                        f"🚫 **CRO VETO**: {action_type} {ticker}\n\n"
                        f"**Reason:** {cro_reason}"
                    )
                    decisions.append({
                        "ticker": ticker,
                        "decision": "WAIT",
                        "action_type": action_type,
                        "confidence": confidence,
                        "price": price,
                        "action_taken": f"CRO Vetoed: {cro_reason}"
                    })
                    continue

            logger.info(f"[{pm_id}] Executing: {action_type} ({trade_action}) {ticker} (Conf: {confidence}, Alloc: {allocation:.1%})")

            action_result = portfolio_service.execute_trade(
                ticker, trade_action, price, confidence, exit_plan, allocation,
                strategy=strategy, atr=atr_value
            )

            # Log individual trade reasoning to manager_log
            trade_reasoning = trade.get("reasoning", "No reasoning provided")
            portfolio_service.log_thought(
                f"**{action_type} {ticker}** @ ${price:.2f}\n\n"
                f"**Confidence:** {confidence}/10 | **Allocation:** {allocation:.1%}\n\n"
                f"**Reasoning:** {trade_reasoning}\n\n"
                f"**Result:** {action_result}"
            )

            decisions.append({
                "ticker": ticker,
                "decision": trade_action,
                "action_type": action_type,
                "confidence": confidence,
                "price": price,
                "action_taken": action_result
            })
        else:
            decisions.append({
                "ticker": ticker,
                "decision": "WAIT",
                "action_type": action_type,
                "confidence": confidence,
                "price": price,
                "action_taken": "Below confidence threshold"
            })
    
    # Log PM's overall summary
    portfolio_service.log_thought(pm_decisions.get("manager_summary", "Analysis complete."))
    
    # Update valuation
    current_prices = {r["ticker"]: r["price"] for r in all_reports}
    portfolio_service.update_valuation(current_prices)
    
    # Run Risk Check (Stop Loss / Take Profit) using the fetched prices
    # This ensures we respect exit plans at least twice daily without extra API polling
    run_risk_check(pm_id, strategy, current_prices)
    
    logger.info(f"[{datetime.now()}] Market Analysis Complete for {pm_id}.")

async def pm_loop(pm_id: str):
    """
    Runs the trading loops for a specific Portfolio Manager.
    """
    strategy = get_strategy(pm_id)
    portfolio_service = portfolio_manager.get_portfolio(pm_id)
    
    logger.info(f"Starting loops for {strategy.name} ({pm_id})...")
    
    # Initialize next scheduled run time
    next_run_time = get_next_scheduled_run_time()
    next_sentinel_check = datetime.now(next_run_time.tzinfo) + timedelta(minutes=30)
    logger.info(f"[{pm_id}] Next Market Analysis scheduled for {next_run_time}")

    while True:
        try:
            status = portfolio_service.get_status()

            if status["is_running"]:
                # 1. Run Risk Check (Fast Loop) - Every minute
                await asyncio.to_thread(run_risk_check, pm_id, strategy)

                # 2. Check if it's time for Market Analysis (Slow Loop)
                now = datetime.now(next_run_time.tzinfo)

                # A. Scheduled Hard Trigger (Legacy Windows)
                if now >= next_run_time:
                    logger.info(f"[{pm_id}] Triggering Scheduled Market Analysis...")
                    await asyncio.to_thread(run_market_analysis, pm_id)
                    next_run_time = get_next_scheduled_run_time()
                    next_sentinel_check = now + timedelta(minutes=60)
                    logger.info(f"[{pm_id}] Next Hard Analysis scheduled for {next_run_time}")

                # B. Sentinel High-Frequency Trigger (Every 60 mins)
                elif now >= next_sentinel_check:
                    logger.info(f"[{pm_id}] Sentinel Check: Scanning for volatility sparks...")
                    await asyncio.to_thread(run_market_analysis, pm_id)
                    next_sentinel_check = now + timedelta(minutes=60)

                # Sleep for 60 seconds before next tick
                await asyncio.sleep(60)
            else:
                # If not running, check less frequently to see if it was started
                await asyncio.sleep(10)
                
        except Exception as e:
            logger.error(f"[{datetime.now()}] Error in loop for {pm_id}: {e}")
            await asyncio.sleep(60) # Retry after 1 minute on error

async def start_pm_loop(pm_id: str):
    """
    Start the trading loop for a specific Portfolio Manager.
    Only starts if not already running.
    """
    if pm_id in pm_loop_tasks:
        logger.warning(f"[{pm_id}] Loop already running, skipping start.")
        return
    
    logger.info(f"[{pm_id}] Starting trading loop...")
    task = asyncio.create_task(pm_loop(pm_id))
    pm_loop_tasks[pm_id] = task

async def stop_pm_loop(pm_id: str):
    """
    Stop the trading loop for a specific Portfolio Manager.
    """
    if pm_id not in pm_loop_tasks:
        logger.warning(f"[{pm_id}] Loop not running, nothing to stop.")
        return
    
    logger.info(f"[{pm_id}] Stopping trading loop...")
    pm_loop_tasks[pm_id].cancel()
    try:
        await pm_loop_tasks[pm_id]
    except asyncio.CancelledError:
        pass
    del pm_loop_tasks[pm_id]
    logger.info(f"[{pm_id}] Trading loop stopped.")

async def resume_existing_loops():
    """
    Called on server startup to resume loops for portfolios that already have capital.
    """
    logger.info("Checking for existing portfolios to resume...")
    
    for pm_id in ['pm1', 'pm2', 'pm3', 'pm4', 'pm5', 'pm6']:
        portfolio = portfolio_manager.get_portfolio(pm_id)
        status = portfolio.get_status()
        
        # Resume if portfolio has capital and was running
        if status.get('initial_capital', 0) > 0 and status.get('is_running'):
            logger.info(f"[{pm_id}] Resuming trading loop (initial_capital: ${status['initial_capital']:.2f})")
            await start_pm_loop(pm_id)
        else:
            logger.info(f"[{pm_id}] No active portfolio, loop will remain idle.")
