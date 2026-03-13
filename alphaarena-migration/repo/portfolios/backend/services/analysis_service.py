import pandas as pd
try:
    import pandas_ta as ta
except ImportError:
    try:
        import pandas_ta_classic as ta
    except ImportError:
        import pandas_ta.classic as ta
from backend.services.data_service import fetch_market_data, get_ticker_news, get_macro_data, get_top_tickers

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical indicators required for the strategy.
    """
    if df.empty:
        return df
    
    # Ensure we are working with a copy to avoid SettingWithCopyWarning
    df = df.copy()
    
    # Flatten MultiIndex columns if present (yfinance update)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # EMAs
    df['EMA_9'] = ta.ema(df['Close'], length=9)
    df['EMA_20'] = ta.ema(df['Close'], length=20)
    df['EMA_50'] = ta.ema(df['Close'], length=50)
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    
    # RSI
    df['RSI'] = ta.rsi(df['Close'], length=14)
    
    # MACD
    macd = ta.macd(df['Close'])
    df['MACD'] = macd['MACD_12_26_9']
    df['MACD_SIGNAL'] = macd['MACDs_12_26_9']
    df['MACD_HIST'] = macd['MACDh_12_26_9']
    
    # ATR for Stop Loss
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    return df

def fetch_multi_timeframe_data(ticker: str) -> dict:
    """
    Fetches 1h and 1d data to provide multi-timeframe context.
    """
    timeframes = ["1h", "1d"]
    results = {}
    
    for tf in timeframes:
        try:
            period = "7d" if tf == "1h" else "1y"
            df = fetch_market_data(ticker, period=period, interval=tf)
            if not df.empty:
                df = calculate_indicators(df)
                current = df.iloc[-1]
                
                # Determine Trend
                trend = "Neutral"
                if current['Close'] > current['EMA_50']:
                    trend = "Bullish"
                elif current['Close'] < current['EMA_50']:
                    trend = "Bearish"
                    
                results[tf] = {
                    "trend": trend,
                    "rsi": round(current['RSI'], 2),
                    "close": round(current['Close'], 2)
                }
        except Exception as e:
            print(f"Error fetching {tf} data for {ticker}: {e}")
            results[tf] = "Data Unavailable"
            
    return results

def detect_divergence(df: pd.DataFrame) -> str:
    """
    Detects RSI Divergences over the last 15 periods.
    """
    if len(df) < 15:
        return "None"
        
    # Look back 15 candles
    window = df.iloc[-15:]
    
    # Find local peaks/valleys
    # Simplified logic: Compare recent low/high vs previous low/high
    
    current_price_low = window['Low'].iloc[-1]
    current_rsi_low = window['RSI'].iloc[-1]
    
    # Find minimum in the window excluding the last candle
    past_window = window.iloc[:-1]
    
    past_price_low = past_window['Low'].min()
    past_rsi_low = past_window['RSI'].min()
    
    # Bullish Divergence: Lower Low in Price, Higher Low in RSI
    if current_price_low < past_price_low and current_rsi_low > past_rsi_low:
        # Filter for noise: RSI should be somewhat low (<40)
        if current_rsi_low < 40:
            return "Bullish Divergence (Strong)"
            
    # Bearish Divergence: Higher High in Price, Lower High in RSI
    current_price_high = window['High'].iloc[-1]
    current_rsi_high = window['RSI'].iloc[-1]
    
    past_price_high = past_window['High'].max()
    past_rsi_high = past_window['RSI'].max()
    
    if current_price_high > past_price_high and current_rsi_high < past_rsi_high:
        # Filter for noise: RSI should be somewhat high (>60)
        if current_rsi_high > 60:
            return "Bearish Divergence (Strong)"
            
    return "None"

def analyze_volume(df: pd.DataFrame) -> dict:
    """
    Analyzes volume for spikes and anomalies.
    """
    if len(df) < 20:
        return {"status": "Normal", "details": "Insufficient Data"}
        
    current_volume = df['Volume'].iloc[-1]
    # Calculate 20-period Volume SMA
    vol_sma = df['Volume'].rolling(window=20).mean().iloc[-1]
    
    if vol_sma == 0: return {"status": "Normal", "details": "Zero Volume"}
    
    ratio = current_volume / vol_sma
    
    status = "Normal"
    if ratio > 2.0:
        status = "Volume Spike (High)"
    elif ratio > 1.5:
        status = "Volume Elevated"
    elif ratio < 0.5:
        status = "Low Volume"
        
    return {
        "status": status,
        "ratio": round(ratio, 2),
        "current": int(current_volume),
        "average": int(vol_sma)
    }

def analyze_ticker(ticker: str, current_position: str = "None", strategy = None):
    """
    Analyzes a ticker using the Confluence Method.
    """
    df = fetch_market_data(ticker)
    if df.empty or len(df) < 200:
        return {"error": "Insufficient data"}
    
    df = calculate_indicators(df)
    current = df.iloc[-1]
    
    close = current['Close']
    ema_20 = current['EMA_20']
    ema_50 = current['EMA_50']
    ema_200 = current['EMA_200']
    rsi = current['RSI']
    macd = current['MACD']
    macd_signal = current['MACD_SIGNAL']
    atr = current['ATR']
    
    # 1. Trend Alignment
    trend = "Neutral"
    if close > ema_200:
        if close > ema_50 > ema_20:
            trend = "Bullish"
        else:
            trend = "Bullish (Weak)"
    elif close < ema_200:
        if close < ema_50 < ema_20:
            trend = "Bearish"
        else:
            trend = "Bearish (Weak)"
            
    # 2. Confluence Checks
    score = 0
    reasons = []
    
    # Price vs EMA 200
    if trend.startswith("Bullish"):
        score += 2
        reasons.append("Price above 200 EMA")
    elif trend.startswith("Bearish"):
        score += 2
        reasons.append("Price below 200 EMA")
        
    # Momentum (RSI)
    rsi_status = "Neutral"
    if rsi > 70:
        rsi_status = "Overbought"
        if trend.startswith("Bearish"): score += 1
    elif rsi < 30:
        rsi_status = "Oversold"
        if trend.startswith("Bullish"): score += 1
    else:
        # RSI Trend support
        if trend.startswith("Bullish") and rsi > 50: score += 1
        if trend.startswith("Bearish") and rsi < 50: score += 1

    # MACD
    macd_status = "Neutral"
    if macd > macd_signal:
        macd_status = "Bullish Crossover"
    else:
        macd_status = "Bearish Crossover"
        if trend.startswith("Bearish"): score += 2
        
    # --- NEW: Advanced Analysis ---
    divergence = detect_divergence(df)
    volume_analysis = analyze_volume(df)
    multi_tf_data = fetch_multi_timeframe_data(ticker)
    
    # Add score for Divergence
    if "Bullish" in divergence: score += 2
    if "Bearish" in divergence: score += 2
    
    # Decision Logic
    decision = "WAIT"
    setup = None
    
    # BUY Criteria
    if trend.startswith("Bullish") and score >= 5:
        decision = "BUY"
        stop_loss = close - (1.5 * atr)
        risk = close - stop_loss
        target1 = close + (2 * risk)
        target2 = close + (3 * risk)
        
        setup = {
            "entry_zone": f"{close * 0.995:.2f} - {close * 1.005:.2f}",
            "stop_loss": f"{stop_loss:.2f}",
            "target_1": f"{target1:.2f}",
            "target_2": f"{target2:.2f}",
            "risk_reward": "1:2",
            "duration": "3-14 Days"
        }
        
    # SELL Criteria (Shorting)
    elif trend.startswith("Bearish") and score >= 5:
        decision = "SELL"
        stop_loss = close + (1.5 * atr)
        risk = stop_loss - close
        target1 = close - (2 * risk)
        target2 = close - (3 * risk)
        
        setup = {
            "entry_zone": f"{close * 0.995:.2f} - {close * 1.005:.2f}",
            "stop_loss": f"{stop_loss:.2f}",
            "target_1": f"{target1:.2f}",
            "target_2": f"{target2:.2f}",
            "risk_reward": "1:2",
            "duration": "3-14 Days"
        }

    # AI Analysis
    from backend.services.ai_service import get_ai_analysis
    
    # Prepare data for AI
    tech_summary = {
        "trend": trend,
        "score": score,
        "rsi": rsi,
        "macd": macd_status,
        "divergence": divergence,
        "volume_analysis": volume_analysis,
        "multi_timeframe": multi_tf_data,
        "decision": decision,
        "price": close,
        "ema_200": ema_200
    }
    
    # Fetch News for Sentiment
    news = get_ticker_news(ticker)
    
    # Fetch Macro Data
    macro_data = get_macro_data()
    
    ai_insights = get_ai_analysis(ticker, tech_summary, news, macro_data, setup, current_position, strategy)
    
    # OVERRIDE: AI Analyst has the final say
    ai_decision = ai_insights.get("decision", "WAIT").upper()
    ai_action_type = ai_insights.get("action_type", "WAIT").upper()
    
    # --- SAFETY VALIDATION ---
    # Prevent hallucinations where AI tries to close a position it doesn't have
    
    validation_override = False
    validation_reason = ""
    
    if ai_action_type == "CLOSE_LONG":
        if "Long" not in current_position:
            validation_override = True
            validation_reason = "AI tried to CLOSE_LONG but no Long position exists."
            
    elif ai_action_type == "COVER_SHORT":
        if "Short" not in current_position:
            validation_override = True
            validation_reason = "AI tried to COVER_SHORT but no Short position exists."
            
    elif ai_action_type == "OPEN_LONG":
        if "Long" in current_position:
            # Not critical, but technically should be ADD_LONG. We can allow or just log.
            pass 
            
    elif ai_action_type == "OPEN_SHORT":
        if "Short" in current_position:
            # Not critical, but technically should be ADD_SHORT.
            pass
            
    if validation_override:
        print(f"SAFETY OVERRIDE for {ticker}: {validation_reason} -> Forcing WAIT.")
        decision = "WAIT"
        # Ensure reasoning exists before appending
        if "reasoning" in ai_insights:
            ai_insights["reasoning"] += f" [SYSTEM NOTE: Trade blocked. {validation_reason}]"
        else:
            ai_insights["reasoning"] = f"[SYSTEM NOTE: Trade blocked. {validation_reason}]"
    elif ai_decision in ["BUY", "SELL", "WAIT"]:
        decision = ai_decision
        
    # Use AI Confidence if available, otherwise fallback
    ai_confidence = ai_insights.get("confidence")
    if ai_confidence is not None:
        try:
            # Convert 0-100 to 1-10
            final_confidence = round(int(ai_confidence) / 10, 1)
        except:
            final_confidence = min(score + 3, 10)
    else:
        final_confidence = min(score + 3, 10)

    return {
        "ticker": ticker,
        "summary": {
            "current_trend": trend,
            "decision": decision,
            "action_type": ai_action_type,
            "confidence_score": final_confidence,
            "allocation_percentage": ai_insights.get("allocation_percentage", 0.05),
            "turn_probability": ai_insights.get("turn_probability", 0)
        },
        "technical_context": {
            "price_action": f"Price is {close:.2f}. Relation to EMAs: 20({ema_20:.2f}), 50({ema_50:.2f}), 200({ema_200:.2f})",
            "momentum": f"RSI: {rsi:.2f} ({rsi_status}), MACD: {macd_status}",
            "divergence": divergence,
            "volume": f"{volume_analysis['status']} (Ratio: {volume_analysis['ratio']})"
        },
        "trade_setup": setup,
        "exit_plan": ai_insights.get("exit_plan", {}),
        "psychology": {
            "invalidation": "Close below Stop Loss or fundamental news shift.",
            "ai_insight": ai_insights.get("psychology", "AI unavailable"),
            "deep_reasoning": ai_insights.get("reasoning", "AI unavailable")
        }
    }

def get_dashboard_summary():
    """
    Analyzes all top assets and returns a summary for the dashboard.
    """
    tickers = get_top_tickers()
    all_tickers = tickers['stocks'] + tickers['crypto']
    
    results = []
    for ticker in all_tickers:
        try:
            # We can optimize this later to run in parallel
            print(f"Analyzing {ticker}...")
            analysis = analyze_ticker(ticker)
            if "error" not in analysis:
                results.append(analysis)
        except Exception as e:
            print(f"Error analyzing {ticker}: {e}")
            
    return results
