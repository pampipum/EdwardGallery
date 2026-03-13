import yfinance as yf
from typing import Dict

def get_current_prices(tickers: list) -> Dict[str, float]:
    """
    Fetch current prices for a list of tickers using yfinance.
    
    Args:
        tickers: List of ticker symbols (e.g., ['BTC-USD', 'ETH-USD'])
    
    Returns:
        Dictionary mapping ticker to current price
    """
    prices = {}
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # Get the most recent price
            hist = stock.history(period="1d", interval="1m")
            if not hist.empty:
                prices[ticker] = float(hist['Close'].iloc[-1])
            else:
                # Fallback to daily data if minute data unavailable
                hist = stock.history(period="1d")
                if not hist.empty:
                    prices[ticker] = float(hist['Close'].iloc[-1])
                else:
                    prices[ticker] = 0.0
        except Exception as e:
            print(f"Error fetching price for {ticker}: {e}")
            prices[ticker] = 0.0
    
    return prices
