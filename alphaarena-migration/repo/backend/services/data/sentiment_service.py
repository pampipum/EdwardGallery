"""
Sentiment and macro data services.
Handles macro economic indicators and crypto sentiment.
"""
import json
import os
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
from backend.utils.logger import logger
from backend.runtime import state_dir


def get_macro_data() -> dict:
    """
    Fetches macro market proxies:
    - ^TNX: 10-Year Treasury Yield (Interest Rate Proxy)
    - ^VIX: Volatility Index (Fear Gauge)
    - ^GSPC: S&P 500 (General Market Sentiment)
    """
    tickers = {
        "US_10Y_YIELD": "^TNX",
        "VIX": "^VIX",
        "SP500": "^GSPC",
        "DXY": "DX-Y.NYB",
        "GOLD": "GC=F"
    }
    
    macro_data = {}
    try:
        for name, symbol in tickers.items():
            ticker = yf.Ticker(symbol)
            # Try fast info, fallback to history
            price = ticker.fast_info.last_price
            if not price:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist["Close"].iloc[-1]
            
            if price:
                macro_data[name] = round(price, 2)
            else:
                macro_data[name] = "N/A"
                
        return macro_data
    except Exception as e:
        logger.error(f"Error fetching macro data: {e}")
        return {}


def get_crypto_fear_greed() -> dict:
    """
    Fetches the latest Crypto Fear & Greed Index from CoinMarketCap.
    Returns a dictionary with 'value' (0-100) and 'classification' (Fear/Greed/Neutral).
    Caches result for 1 hour to minimize API calls.
    """
    # Simple in-memory cache
    cache_file = str(state_dir("cache") / "fear_greed_cache.json")
    
    # Check cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
                cache_time = datetime.fromisoformat(cache['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=1):
                    return cache['data']
        except Exception:
            pass
    
    # Fetch from API
    cmc_api_key = os.getenv('CMC_API_KEY')
    if not cmc_api_key:
        return {"value": "N/A", "classification": "API Key Missing"}
    
    try:
        url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
        headers = {
            'X-CMC_PRO_API_KEY': cmc_api_key,
            'Accept': 'application/json'
        }
        params = {'limit': 1}  # Only get the latest value
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Handle both string "0" and integer 0 for error_code (API may return either)
        error_code = data.get('status', {}).get('error_code')
        if (error_code == 0 or error_code == "0") and data.get('data'):
            latest = data['data'][0]
            
            # Check data freshness
            timestamp = int(latest['timestamp'])
            # Use timezone-aware datetime for Python 3.12+ compatibility
            data_datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            age_hours = (datetime.now(tz=timezone.utc) - data_datetime).total_seconds() / 3600
            
            result = {
                "value": latest['value'],
                "classification": latest['value_classification'],
                "timestamp": latest['timestamp'],
                "data_age_hours": round(age_hours, 1)
            }
            
            # Warn if data is stale (older than 12 hours)
            if age_hours > 12:
                logger.warning(f"Warning: Fear & Greed Index data is {age_hours:.1f} hours old")
            
            # Cache the result
            try:
                with open(cache_file, 'w') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'data': result
                    }, f)
            except Exception:
                pass
            
            return result
        else:
            return {"value": "N/A", "classification": "API Error"}
            
    except Exception as e:
        logger.error(f"Error fetching CMC Fear & Greed Index: {e}")
        return {"value": "N/A", "classification": "Error"}
