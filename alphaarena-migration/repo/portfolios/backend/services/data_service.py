import yfinance as yf
import pandas as pd

# Top 8 Crypto Projects
TOP_STOCKS = [] # User requested only crypto for now

TOP_CRYPTO = [
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", 
    "XRP-USD", "DOGE-USD", "ADA-USD", "AVAX-USD"
]

def get_top_tickers():
    """Returns a dictionary of top stocks and crypto tickers."""
    return {
        "stocks": TOP_STOCKS,
        "crypto": TOP_CRYPTO
    }

def fetch_market_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetches historical market data for a given ticker.
    
    Args:
        ticker (str): The asset symbol (e.g., 'AAPL', 'BTC-USD').
        period (str): Data period to download (default '1y').
        interval (str): Data interval (default '1d').
        
    Returns:
        pd.DataFrame: DataFrame with columns [Open, High, Low, Close, Volume]
    """
    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if data.empty:
            return pd.DataFrame()
        return data
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()

def get_current_price(ticker: str) -> float:
    """Fetches the current price for a ticker."""
    try:
        ticker_obj = yf.Ticker(ticker)
        # Try fast info first, then history
        price = ticker_obj.fast_info.last_price
        if price:
            return price
        
        data = ticker_obj.history(period="1d")
        if not data.empty:
            return data["Close"].iloc[-1]
        return 0.0
    except Exception:
        return 0.0

def get_ticker_news(ticker: str) -> list:
    """
    Fetches recent news for a ticker using yfinance.
    Returns a list of dictionaries with 'title', 'publisher', and 'link'.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        news = ticker_obj.news
        if news:
            pass # Debug print removed
        
        formatted_news = []
        for item in news[:5]: # Limit to top 5 news items
            # Handle new yfinance structure where data is in 'content'
            data = item.get('content', item)
            
            formatted_news.append({
                "title": data.get("title"),
                "publisher": data.get("provider", {}).get("displayName") if isinstance(data.get("provider"), dict) else data.get("publisher"),
                "link": data.get("clickThroughUrl", {}).get("url") if isinstance(data.get("clickThroughUrl"), dict) else data.get("link"),
                "published": data.get("pubDate", data.get("providerPublishTime"))
            })
        return formatted_news
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []

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
        "SP500": "^GSPC"
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
        print(f"Error fetching macro data: {e}")
        return {}
