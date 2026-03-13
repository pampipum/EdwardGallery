import pandas as pd
import yfinance as yf
import time
try:
    import pandas_ta as ta
except ImportError:
    try:
        import pandas_ta_classic as ta
    except ImportError:
        import pandas_ta.classic as ta
from backend.services.data_service import fetch_market_data, get_ticker_news, get_macro_data, get_top_tickers, get_crypto_fear_greed, get_current_price
from backend.services.data_fetcher_service import get_binance_candles, normalize_ticker_for_binance

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
    
    # Deduplicate columns if any exist (fix for yfinance returning duplicates)
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    
    # Convert all numeric columns to float64 to prevent isnan errors
    numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
    
    # Forward fill any NaN values that might cause issues
    df = df.ffill().bfill()

    # EMAs
    df['EMA_9'] = ta.ema(df['Close'], length=9)
    df['EMA_20'] = ta.ema(df['Close'], length=20)
    df['EMA_21'] = ta.ema(df['Close'], length=21)
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
    
    # Bollinger Bands
    bbands = ta.bbands(df['Close'], length=20, std=2)
    if bbands is not None:
        # Rename columns to avoid naming variations (e.g. _2.0 vs _2)
        # Expected order: Lower, Mid, Upper, Bandwidth, Percent
        if len(bbands.columns) >= 4:
            bbands.columns = ['BBL', 'BBM', 'BBU', 'BBB', 'BBP']
            df['BBL_20_2.0'] = bbands['BBL']
            df['BBM_20_2.0'] = bbands['BBM']
            df['BBU_20_2.0'] = bbands['BBU']
            df['BBB_20_2.0'] = bbands['BBB'] # Bandwidth
            
    # ADX (Average Directional Index) - 14 periods
    try:
        adx = ta.adx(df['High'], df['Low'], df['Close'], length=14)
        if adx is not None:
             # pandas_ta returns ADX_14, DMP_14, DMN_14
             df['ADX'] = adx['ADX_14']
    except Exception as e:
        print(f"Error calculating ADX: {e}")
        df['ADX'] = 0.0

    # VWAP (Volume Weighted Average Price)
    try:
        # VWAP usually requires a datetime index or 'date' column, handled by pandas_ta if index is datetime
        vwap = ta.vwap(df['High'], df['Low'], df['Close'], df['Volume'])
        if vwap is not None:
            df['VWAP'] = vwap
        else:
            # Fallback for daily data where intra-day VWAP might not apply perfectly, 
            # or if calculation fails. approximate with typical price * volume accum
            df['VWAP'] = (df['High'] + df['Low'] + df['Close']) / 3
    except Exception as e:
        print(f"Error calculating VWAP: {e}")
        # Fallback to simple moving average if VWAP fails
        df['VWAP'] = df['EMA_20']
    
    return df

# ─── Multi-Timeframe Cache ──────────────────────────────────────────────────
# Keyed by ticker. Stores (result_dict, fetch_timestamp).
# TTL: 10 minutes — 15m candles don't change meaningfully more often than that.
_mtf_cache: dict = {}
_MTF_CACHE_TTL_SECONDS = 600  # 10 minutes


def _binance_candles_to_df(candles: list) -> pd.DataFrame:
    """
    Converts the list-of-dicts from get_binance_candles() into a
    pandas DataFrame compatible with calculate_indicators().
    """
    if not candles:
        return pd.DataFrame()
    df = pd.DataFrame(candles)
    df = df.rename(columns={"timestamp": "Datetime", "open": "Open",
                             "high": "High", "low": "Low",
                             "close": "Close", "volume": "Volume"})
    df = df.set_index("Datetime")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df = df.ffill().bfill()
    return df


def fetch_multi_timeframe_data(ticker: str) -> dict:
    """
    Fetches 15m, 1h, 1d, and 1wk data to provide multi-timeframe context.

    Improvements over original:
    - 10-minute in-memory TTL cache per ticker (avoids redundant fetches
      within the same analysis cycle and across back-to-back cycles).
    - Crypto tickers (ending in -USD) use Binance Futures candles for
      the 15m and 1h timeframes — reliable, free, no throttling.
    - yfinance is still used for 1d / 1wk and for all stock tickers.
    """
    global _mtf_cache

    # ── Cache hit check ──────────────────────────────────────────────────────
    now = time.monotonic()
    if ticker in _mtf_cache:
        cached_result, cached_at = _mtf_cache[ticker]
        if (now - cached_at) < _MTF_CACHE_TTL_SECONDS:
            return cached_result

    is_crypto = ticker.endswith("-USD")
    results = {}

    # ── Intraday timeframes (15m, 1h) ─────────────────────────────────────────
    intraday_timeframes = {
        "15m": ("15m", 200),   # Binance interval, candle limit
        "1h":  ("1h",  500),
    }

    for tf_label, (binance_interval, limit) in intraday_timeframes.items():
        df = pd.DataFrame()

        if is_crypto:
            # Primary: Binance Futures (free, reliable, no throttle)
            try:
                candles = get_binance_candles(
                    symbol=ticker,
                    interval=binance_interval,
                    limit=limit
                )
                df = _binance_candles_to_df(candles)
            except Exception as e:
                print(f"[MTF] Binance {tf_label} failed for {ticker}: {e}")

        if df.empty:
            # Fallback (stocks always come here; crypto falls back on Binance error)
            try:
                period = "60d" if tf_label == "15m" else "2y"
                df = fetch_market_data(ticker, period=period, interval=tf_label)
            except Exception as e:
                print(f"[MTF] yfinance {tf_label} failed for {ticker}: {e}")

        if not df.empty:
            try:
                df = calculate_indicators(df)
                current = df.iloc[-1]
                trend = "Neutral"
                if current["Close"] > current["EMA_50"]:
                    trend = "Bullish"
                elif current["Close"] < current["EMA_50"]:
                    trend = "Bearish"
                results[tf_label] = {
                    "trend": trend,
                    "rsi": round(current["RSI"], 2),
                    "close": round(current["Close"], 2)
                }
            except Exception as e:
                print(f"[MTF] Indicator calc failed for {ticker} {tf_label}: {e}")
                results[tf_label] = None
        else:
            results[tf_label] = None

    # ── Daily / Weekly timeframes — always yfinance ───────────────────────────
    higher_tf = {"1d": "2y", "1wk": "5y"}
    for tf_label, period in higher_tf.items():
        try:
            df = fetch_market_data(ticker, period=period, interval=tf_label)
            if not df.empty:
                df = calculate_indicators(df)
                current = df.iloc[-1]
                trend = "Neutral"
                if current["Close"] > current["EMA_50"]:
                    trend = "Bullish"
                elif current["Close"] < current["EMA_50"]:
                    trend = "Bearish"
                results[tf_label] = {
                    "trend": trend,
                    "rsi": round(current["RSI"], 2),
                    "close": round(current["Close"], 2)
                }
            else:
                results[tf_label] = None
        except Exception as e:
            print(f"[MTF] yfinance {tf_label} failed for {ticker}: {e}")
            results[tf_label] = None

    # ── Cache the result ──────────────────────────────────────────────────────
    _mtf_cache[ticker] = (results, now)
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

def analyze_ticker(ticker: str, current_position: str = "None", strategy = None, skip_pm: bool = False):
    """
    Analyzes a ticker using the Confluence Method.
    """
    df = fetch_market_data(ticker)
    if df.empty or len(df) < 200:
        return {"error": "Insufficient data"}
    
    # --- DATA VALIDATION ---
    try:
        current_price_check = get_current_price(ticker)
        if not df.empty and current_price_check > 0:
            df_price = df['Close'].iloc[-1].item()  # Use .item() to extract scalar safely
            # Check for > 50% deviation (massive error like BTC vs ETH)
            if abs(df_price - current_price_check) / current_price_check > 0.5:
                print(f"CRITICAL DATA ERROR: {ticker} DF Price {df_price} vs FastInfo {current_price_check}")
                return {"error": "Data Integrity Error"}
    except Exception as e:
        print(f"Validation Error: {e}")
    # -----------------------
    
    df = calculate_indicators(df)
    current = df.iloc[-1]
    
    close = current['Close']
    ema_20 = current['EMA_20']
    ema_21 = current['EMA_21']
    ema_50 = current['EMA_50']
    ema_200 = current['EMA_200']
    rsi = current['RSI']
    macd = current['MACD']
    macd_signal = current['MACD_SIGNAL']
    atr = current['ATR']
    adx = current.get('ADX', 0)
    vwap = current.get('VWAP', close)
    
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
    
    # Bollinger Band Analysis
    bb_status = "Normal"
    if 'BBB_20_2.0' in df.columns:
        bandwidth = df['BBB_20_2.0'].iloc[-1]
        # Simple squeeze detection (if bandwidth is in lowest 10% of last 100 periods)
        # This is a simplified check
        if bandwidth < 5.0: # Arbitrary low value, better to compare to history
             bb_status = f"Squeeze (Bandwidth: {bandwidth:.2f})"
        elif close > df['BBU_20_2.0'].iloc[-1]:
             bb_status = "Price above Upper Band"
        elif close < df['BBL_20_2.0'].iloc[-1]:
             bb_status = "Price below Lower Band"
    
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
        "bollinger_bands": bb_status,
        "multi_timeframe": multi_tf_data,
        "decision": decision,
        "price": close,
        "ema_200": ema_200,
        "ema_21": ema_21,
        "adx": adx,
        "vwap": vwap
    }
    
    # Fetch Fundamentals
    fundamentals = {}
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        fundamentals = {
            "market_cap": info.get("marketCap", "N/A"),
            "volume_24h": info.get("volume24Hr", "N/A"),
            "trailing_pe": info.get("trailingPE", "N/A"),
            "forward_pe": info.get("forwardPE", "N/A"),
            "dividend_yield": info.get("dividendYield", "N/A"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh", "N/A"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow", "N/A")
        }
    except Exception as e:
        print(f"Error fetching fundamentals for {ticker}: {e}")
    
    # Fetch News for Sentiment
    news = get_ticker_news(ticker)
    
    # Fetch Macro Data
    macro_data = get_macro_data() or {}

    # Add Crypto Fear & Greed Index for crypto assets
    if "-USD" in ticker:  # Crypto asset
        fear_greed = get_crypto_fear_greed() or {}
        fg_value = fear_greed.get('value', 'N/A')
        fg_class = fear_greed.get('classification', 'Unknown')
        macro_data["CRYPTO_FEAR_GREED"] = f"{fg_value} ({fg_class})"
    
    # --- COST OPTIMIZATION: Pre-AI Filtering ---
    # Only call AI if the asset is "interesting" or if we hold a position
    is_interesting = False
    
    # 0. STRATEGY EXCEPTION: Sentiment Specialist
    # PM3's entire edge is catching news BEFORE technicals confirm.
    if strategy and strategy.name == "Sentiment Specialist":
        # If there is ANY news, we must analyze it
        if news:
            is_interesting = True

    # 1. Always analyze if we hold a position (to manage exits)
    if current_position != "None":
        is_interesting = True
        
    # 2. Analyze if technical score is decent (lowered from 3 to increase AI coverage)
    elif score >= 2:
        is_interesting = True
        
    # 3. Analyze if significant volatility or momentum (widened from ±15 to ±10)
    elif abs(rsi - 50) > 10:  # RSI < 40 or > 60
        is_interesting = True
    elif "Spike" in volume_analysis['status']:
        is_interesting = True
    elif "Divergence" in divergence and divergence != "None":
        is_interesting = True
    elif bb_status != "Normal": # Squeeze or Breakout
        is_interesting = True

    if not is_interesting:
        print(f"   [Cost Saver] Skipping AI for {ticker} (Boring Technicals: Score {score}, RSI {rsi:.1f})")
        
        # Return a skeleton response that mimics the AI output
        return {
            "ticker": ticker,
            "analyst_report": f"**Technical Scan Only**: Asset shows low volatility and neutral momentum (RSI {rsi:.1f}). No significant setup detected. AI analysis skipped to save costs.",
            "summary": {
                "current_trend": trend,
                "decision": "WAIT",
                "action_type": "WAIT",
                "confidence_score": min(score + 3, 10),
                "allocation_percentage": 0.0,
                "turn_probability": 0
            },
            "technical_context": {
                "price_action": f"Price is {close:.2f}. Relation to EMAs: 20({ema_20:.2f}), 50({ema_50:.2f}), 200({ema_200:.2f})",
                "momentum": f"RSI: {rsi:.2f} ({rsi_status}), MACD: {macd_status}",
                "divergence": divergence,
                "bollinger_bands": bb_status,
                "volume": f"{volume_analysis['status']} (Ratio: {volume_analysis['ratio']})"
            },
            "trade_setup": None,
            "exit_plan": {},
            "psychology": {
                "invalidation": "N/A",
                "ai_insight": "Skipped due to low technical interest.",
                "deep_reasoning": "Automated Technical Filter: Market conditions do not meet the minimum threshold for AI analysis (Low Score, Neutral RSI, No Volume). Defaulting to WAIT."
            }
        }

    # Fetch Deep Dive Data (Funding/OI) for crypto assets - used by hybrid analyst prompt
    deep_dive_data = {}
    # Only fetch for crypto assets (they have derivative data available)
    if "-USD" in ticker or "USDT" in ticker:
        from backend.services.market_service import get_deep_dive_data
        from backend.services.data_fetcher_service import get_binance_funding, get_binance_open_interest
        
        # Try to get from cache first
        deep_dive_data = get_deep_dive_data(ticker)
        
        # If cache is empty, fetch real-time data for this ticker
        if not deep_dive_data or (not deep_dive_data.get("funding") and not deep_dive_data.get("open_interest")):
            try:
                funding = get_binance_funding(ticker)
                oi = get_binance_open_interest(ticker)
                if funding or oi:
                    deep_dive_data = {
                        "funding": funding,
                        "open_interest": oi
                    }
                    print(f"   [Derivatives] Fetched real-time data for {ticker}")
            except Exception as e:
                print(f"   [Derivatives] Failed to fetch real-time data for {ticker}: {e}")
        
        if deep_dive_data and (deep_dive_data.get("funding") or deep_dive_data.get("open_interest")):
            print(f"   [Derivatives] Loaded data for {ticker}: Funding={deep_dive_data.get('funding', {}).get('funding_rate', 'N/A')}, OI={deep_dive_data.get('open_interest', {}).get('open_interest', 'N/A')}")

    # Fetch Insider Data (Only for Insider Tracker Strategy - if we still supported it)
    insider_data = {}
    # (Insider Logic Removed or Disabled for now as PM2 is now Deep Dive)

    ai_insights = get_ai_analysis(ticker, tech_summary, news, macro_data, setup, current_position, strategy, fundamentals, insider_data=insider_data, skip_pm=skip_pm, deep_dive_data=deep_dive_data)
    
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
            # AI returns confidence on 0-10 scale, use it directly
            final_confidence = round(float(ai_confidence), 1)
        except:
            final_confidence = min(score + 3, 10)
    else:
        final_confidence = min(score + 3, 10)

    return {
        "ticker": ticker,
        "analyst_report": ai_insights.get("analyst_report"),
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
            "bollinger_bands": bb_status,
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
