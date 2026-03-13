import asyncio
import time
import json
import google.generativeai as genai
from datetime import datetime
from backend.services.data_service import get_top_tickers, get_current_price
from backend.services.analysis_service import analyze_ticker
from backend.services.portfolio_service import portfolio_service

# Two-Speed Architecture Configuration
RISK_CHECK_INTERVAL = 60        # 1 Minute (Fast Loop)
ANALYSIS_INTERVAL = 43200       # 12 Hours (Slow Loop)

def run_risk_check():
    """
    FAST LOOP: Checks existing positions for Stop Loss / Target hits.
    Runs frequently (e.g., every minute).
    """
    # 1. Optimization: Check if we have any positions first
    status = portfolio_service.get_status()
    existing_positions = status.get("positions", {})
    
    if not existing_positions:
        # No positions to monitor, skip API calls
        # print(f"[{datetime.now()}] Risk Check: No positions, skipping.")
        return

    print(f"[{datetime.now()}] Risk Check: Monitoring {len(existing_positions)} positions...")

    # 2. Get current prices for held assets only
    held_tickers = list(existing_positions.keys())
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
            print(f"AUTOMATIC EXIT: {ticker} - {exit_reason}")
            # Execute the trade
            result = portfolio_service.execute_trade(ticker, exit_action, current_price, 10.0) # Max confidence for auto-exit
            
            # Log to Manager Log immediately for visibility
            portfolio_service.log_thought(f"**AUTOMATIC EXIT EXECUTED**\n\nAsset: {ticker}\nAction: {exit_action}\nReason: {exit_reason}\nPrice: ${current_price:.2f}\nResult: {result}")

def run_market_analysis():
    """
    SLOW LOOP: Performs deep AI analysis, reads news, and makes strategic decisions.
    Runs infrequently (e.g., every 12 hours).
    """
    print(f"[{datetime.now()}] Starting Market Analysis (Slow Loop)...")
    
    tickers = get_top_tickers()
    target_assets = tickers['crypto']
    
    current_prices = {}
    all_analyses = []
    decisions = [] 
    
    for ticker in target_assets:
        try:
            # 1. Get Current Price for Valuation
            price = get_current_price(ticker)
            current_prices[ticker] = price
            
            # 2. Get Current Position Context
            portfolio_status = portfolio_service.get_status()
            positions = portfolio_status.get("positions", {})
            current_pos_data = positions.get(ticker)
            
            current_pos_str = "None"
            if current_pos_data:
                qty = current_pos_data["qty"]
                if qty > 0:
                    current_pos_str = f"Long ({qty:.4f} units)"
                elif qty < 0:
                    current_pos_str = f"Short ({abs(qty):.4f} units)"
            
            # 3. Analyze Ticker (with context)
            print(f"Analyzing {ticker} (Holding: {current_pos_str})...")
            analysis = analyze_ticker(ticker, current_position=current_pos_str)
            
            if "error" in analysis:
                continue
            
            all_analyses.append(analysis)
                
            decision = analysis["summary"]["decision"]
            action_type = analysis["summary"].get("action_type", "WAIT")
            confidence = analysis["summary"]["confidence_score"]
            
            # 4. Execute Trade Logic
            action_result = "Wait"
            exit_plan = analysis.get("exit_plan", {})
            allocation_percentage = analysis["summary"].get("allocation_percentage", 0.05)
            
            if decision == "BUY" and confidence >= 70.0:
                print(f"{action_type} SIGNAL: {ticker} (Conf: {confidence}, Alloc: {allocation_percentage:.1%})")
                action_result = portfolio_service.execute_trade(ticker, "BUY", price, confidence, exit_plan, allocation_percentage)
                decisions.append({
                    "ticker": ticker, 
                    "decision": "BUY", 
                    "action_type": action_type,
                    "confidence": confidence, 
                    "price": price, 
                    "action_taken": action_result
                })
                
            elif decision == "SELL" and confidence >= 70.0:
                print(f"{action_type} SIGNAL: {ticker} (Conf: {confidence}, Alloc: {allocation_percentage:.1%})")
                action_result = portfolio_service.execute_trade(ticker, "SELL", price, confidence, exit_plan, allocation_percentage)
                decisions.append({
                    "ticker": ticker, 
                    "decision": "SELL", 
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
                    "action_taken": "Wait"
                })
                
        except Exception as e:
            print(f"Error processing {ticker}: {e}")
            
    # Save full analysis results for Dashboard Cache
    portfolio_service.set_latest_analysis(all_analyses) 

    # 5. Generate Manager's Summary
    final_status = portfolio_service.get_status()
    
    summary_prompt = f"""
    You are the Senior Portfolio Manager. You just analyzed {len(target_assets)} crypto assets.
    
    PORTFOLIO STATE:
    - Balance: ${final_status.get('balance', 0):.2f}
    - Positions: {json.dumps(final_status.get('positions', {}), indent=2)}
    
    DECISIONS MADE:
    {json.dumps(decisions, indent=2)}
    
    Write a concise "Manager's Log" entry (max 150 words).
    - Summarize the overall market sentiment based on your analysis.
    - Mention key macro factors or news if relevant.
    - Explain your biggest move (or why you did nothing).
    - Be professional but insightful.
    """
    
    try:
        model = genai.GenerativeModel('gemini-2.5-pro')
        response = model.generate_content(summary_prompt)
        manager_thought = response.text.strip()
        portfolio_service.log_thought(manager_thought)
    except Exception as e:
        print(f"Error generating manager summary: {e}")
        portfolio_service.log_thought("Market analysis complete. No significant comments.")

    # 6. Update Valuation
    portfolio_service.update_valuation(current_prices)
    print(f"[{datetime.now()}] Market Analysis Complete.")

async def risk_loop():
    """Background task for the fast risk loop."""
    while True:
        try:
            status = portfolio_service.get_status()
            if status["is_running"]:
                await asyncio.to_thread(run_risk_check)
        except Exception as e:
            print(f"[{datetime.now()}] Error in Risk Loop: {e}")
        
        await asyncio.sleep(RISK_CHECK_INTERVAL)

async def analysis_loop():
    """Background task for the slow analysis loop."""
    while True:
        try:
            status = portfolio_service.get_status()
            if status["is_running"]:
                await asyncio.to_thread(run_market_analysis)
        except Exception as e:
            print(f"[{datetime.now()}] Error in Analysis Loop: {e}")
            
        await asyncio.sleep(ANALYSIS_INTERVAL)

async def start_trading_loop():
    """
    Starts both trading loops concurrently.
    """
    print("Starting Two-Speed Trading Engine...")
    await asyncio.gather(
        risk_loop(),
        analysis_loop()
    )
