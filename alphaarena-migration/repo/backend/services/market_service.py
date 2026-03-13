import yfinance as yf
from typing import Dict
from datetime import datetime, timedelta
import json
import os
from backend.services.data_fetcher_service import get_dex_price, get_binance_spot_price

# Simple in-memory cache
_price_cache = {}
_cache_ttl = 120  # Cache prices for 120 seconds (status is polled every 30s)


def _get_token_address(ticker: str) -> str:
    """Helper to get token address from map."""
    try:
        map_path = os.path.join(os.path.dirname(__file__), 'data', 'token_map.json')
        if not os.path.exists(map_path):
            return None
        with open(map_path, 'r') as f:
            token_map = json.load(f)
        
        # Check crypto
        if ticker in token_map.get("crypto", {}):
            return token_map["crypto"][ticker]
        return None
    except:
        return None

def get_current_prices(tickers: list) -> Dict[str, float]:
    """
    Fetch current prices for a list of tickers with intelligent routing and caching.
    
    - Crypto (ending in -USD): Binance Spot/Futures API
    - Stocks: yfinance
    - Fallback: DexScreener for crypto if Binance fails
    
    Args:
        tickers: List of ticker symbols (e.g., ['BTC-USD', 'TSLA'])
    
    Returns:
        Dictionary mapping ticker to current price
    """
    prices = {}
    now = datetime.now()
    tickers_to_fetch = []
    
    # Check cache first
    for ticker in tickers:
        if ticker in _price_cache:
            cached_price, cached_time = _price_cache[ticker]
            # Use cached price if less than TTL seconds old
            if (now - cached_time).total_seconds() < _cache_ttl:
                prices[ticker] = cached_price
            else:
                tickers_to_fetch.append(ticker)
        else:
            tickers_to_fetch.append(ticker)
    
    # Fetch fresh data for uncached/expired tickers
    if tickers_to_fetch:
        for ticker in tickers_to_fetch:
            try:
                # Route crypto through Binance for better reliability
                if ticker.endswith("-USD"):
                    binance_price = get_binance_spot_price(ticker)
                    if binance_price:
                        prices[ticker] = binance_price
                        _price_cache[ticker] = (binance_price, now)
                        print(f"   [Binance] Fetched price for {ticker}: ${binance_price:.2f}")
                        continue
                    # If Binance fails, try DexScreener as final fallback
                    address = _get_token_address(ticker)
                    if address:
                        dex_price = get_dex_price(address)
                        if dex_price:
                            prices[ticker] = dex_price
                            _price_cache[ticker] = (dex_price, now)
                            print(f"   [DexScreener] Fetched price for {ticker}: ${dex_price}")
                            continue
                    prices[ticker] = 0.0
                else:
                    # Stocks: Use yfinance
                    stock = yf.Ticker(ticker)
                    # Get the most recent price
                    hist = stock.history(period="1d", interval="1m")
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                        prices[ticker] = price
                        _price_cache[ticker] = (price, now)
                    else:
                        # Fallback to daily data if minute data unavailable
                        hist = stock.history(period="1d")
                        if not hist.empty:
                            price = float(hist['Close'].iloc[-1])
                            prices[ticker] = price
                            _price_cache[ticker] = (price, now)
                        else:
                            prices[ticker] = 0.0
            except Exception as e:
                print(f"Error fetching price for {ticker}: {e}")
                prices[ticker] = 0.0
    
    return prices

def clear_price_cache():
    """Clear the entire price cache. Useful for testing or manual refresh."""
    global _price_cache
    _price_cache = {}

def get_deep_dive_data(ticker: str) -> dict:
    """
    Retrieves deep dive data (Funding, OI) from the local cache for a specific ticker.
    """
    from backend.services.data_fetcher_service import load_cache
    
    cache = load_cache()
    if not cache:
        return {}
        
    # Check Crypto
    if ticker in cache.get("crypto", {}):
        return cache["crypto"][ticker]
        
    # Check Stocks
    # Normalize ticker (remove 'xyz:' etc)
    clean_ticker = ticker.split(':')[-1]
    if clean_ticker in cache.get("stocks", {}):
        return cache["stocks"][clean_ticker]
        
    return {}
