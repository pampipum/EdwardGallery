import yfinance as yf
from typing import Dict
from datetime import datetime, timedelta

# Simple in-memory cache
_price_cache = {}
_cache_ttl = 60  # Cache prices for 60 seconds

def get_current_prices(tickers: list) -> Dict[str, float]:
    """
    Fetch current prices for a list of tickers using yfinance with caching.
    
    Args:
        tickers: List of ticker symbols (e.g., ['BTC-USD', 'ETH-USD'])
    
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
