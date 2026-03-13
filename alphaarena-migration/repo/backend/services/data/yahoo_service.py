"""
Yahoo Finance data services using yfinance.
Handles market data, prices, technical indicators, and screeners.
"""
import yfinance as yf
import pandas as pd
import requests
from backend.utils.logger import logger
from backend.services.data_fetcher_service import get_binance_candles


# ============================================================================
# Yahoo Finance Free API Functions (No API Key Required)
# ============================================================================

def _fetch_yahoo_screener(screener_name: str, limit: int = 20) -> list:
    """
    Fetches data from Yahoo Finance predefined screeners.
    Available screeners: day_gainers, day_losers, most_actives, 
                         pre_market_gainers, after_hours_gainers
    """
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?formatted=false&lang=en-US&region=US&scrIds={screener_name}&count={limit}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse Yahoo response format
        quotes = []
        if 'finance' in data and 'result' in data['finance']:
            results = data['finance']['result']
            if results and len(results) > 0 and 'quotes' in results[0]:
                for quote in results[0]['quotes'][:limit]:
                    quotes.append({
                        'symbol': quote.get('symbol', ''),
                        'name': quote.get('shortName', quote.get('longName', '')),
                        'price': quote.get('regularMarketPrice', 0),
                        'changesPercentage': quote.get('regularMarketChangePercent', 0),
                        'change': quote.get('regularMarketChange', 0),
                        'volume': quote.get('regularMarketVolume', 0),
                        'marketCap': quote.get('marketCap', 0),
                    })
        
        return quotes
        
    except Exception as e:
        logger.error(f"Error fetching Yahoo screener '{screener_name}': {e}")
        return []


def _fetch_yahoo_custom_screener(filters: dict, limit: int = 20) -> list:
    """
    Fetches stocks from Yahoo Finance using custom screener filters.
    Filters can include: priceMax, volumeMin, marketCapMax, sector, etc.
    """
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/screener"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json'
        }
        
        # Build query based on filters
        query = {
            "size": limit,
            "offset": 0,
            "sortField": "intradaymarketcap",
            "sortType": "DESC",
            "quoteType": "EQUITY",
            "query": {
                "operator": "AND",
                "operands": []
            },
            "userId": "",
            "userIdType": "guid"
        }
        
        # Add filter operands
        operands = query["query"]["operands"]
        
        # Price filter (e.g., price < 5)
        if 'priceLowerThan' in filters:
            operands.append({
                "operator": "LT",
                "operands": ["regularmarketprice", filters['priceLowerThan']]
            })
        if 'priceMoreThan' in filters:
            operands.append({
                "operator": "GT",
                "operands": ["regularmarketprice", filters['priceMoreThan']]
            })
            
        # Volume filter (e.g., volume > 200k)
        if 'volumeMoreThan' in filters:
            operands.append({
                "operator": "GT",
                "operands": ["dayvolume", filters['volumeMoreThan']]
            })
            
        # Market cap filter
        if 'marketCapLowerThan' in filters:
            operands.append({
                "operator": "LT",
                "operands": ["intradaymarketcap", filters['marketCapLowerThan']]
            })
        if 'marketCapMoreThan' in filters:
            operands.append({
                "operator": "GT",
                "operands": ["intradaymarketcap", filters['marketCapMoreThan']]
            })
            
        # Exchange filter
        if 'exchange' in filters:
            exchange_map = {
                'NASDAQ': 'nasdaq',
                'NYSE': 'nyse',
                'AMEX': 'amex'
            }
            exchange = exchange_map.get(filters['exchange'], filters['exchange'].lower())
            operands.append({
                "operator": "EQ",
                "operands": ["exchange", exchange]
            })
            
        # Sector filter
        if 'sector' in filters:
            operands.append({
                "operator": "EQ",
                "operands": ["sector", filters['sector']]
            })
        
        # Ensure at least one operand (default: US equities)
        if not operands:
            operands.append({
                "operator": "EQ",
                "operands": ["region", "us"]
            })
        
        response = requests.post(url, headers=headers, json=query, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse response
        quotes = []
        if 'finance' in data and 'result' in data['finance']:
            results = data['finance']['result']
            if results and len(results) > 0 and 'quotes' in results[0]:
                for quote in results[0]['quotes'][:limit]:
                    quotes.append({
                        'symbol': quote.get('symbol', ''),
                        'name': quote.get('shortName', quote.get('longName', '')),
                        'price': quote.get('regularMarketPrice', 0),
                        'changesPercentage': quote.get('regularMarketChangePercent', 0),
                        'change': quote.get('regularMarketChange', 0),
                        'volume': quote.get('regularMarketVolume', 0),
                        'marketCap': quote.get('marketCap', 0),
                    })
        
        return quotes
        
    except Exception as e:
        logger.error(f"Error fetching Yahoo custom screener: {e}")
        return []


def fetch_market_data(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Fetches historical market data for a given ticker.
    Uses yf.Ticker().history() for stocks, Binance for crypto.
    
    Args:
        ticker (str): The asset symbol (e.g., 'AAPL', 'BTC-USD').
        period (str): Data period to download (default '1y').
        interval (str): Data interval (default '1d').
        
    Returns:
        pd.DataFrame: DataFrame with columns [Open, High, Low, Close, Volume]
    """
    try:
        # Route crypto directly to Binance (skip yfinance to avoid warnings)
        if ticker.endswith("-USD"):
            logger.info(f"Fetching {ticker} (crypto) from Binance...")
            # Map timeframe to Binance interval
            binance_interval = "1d"
            if interval.endswith("m"): binance_interval = interval
            elif interval.endswith("h"): binance_interval = interval
            elif interval == "1d": binance_interval = "1d"
            elif interval == "1wk": binance_interval = "1w"
            
            # Map period to correct candle count per interval
            # Binance max per request is 1000 candles
            if interval == "15m":
                # 60 days * 24h * 4 (15m per hour) = 5760, capped at 1000
                limit = min(60 * 24 * 4, 1000)
            elif interval in ("1h", "60m"):
                # 2 years * 365 * 24h = 17520, capped at 1000
                limit = 1000
            elif interval == "1wk" or interval == "1w":
                limit = min(260, 1000)  # ~5 years of weekly
            else:
                # Daily: 1 year = 365 candles
                limit = 365

            candles = get_binance_candles(ticker, binance_interval, limit)
            if candles:
                # Convert to DataFrame matching yfinance structure
                df = pd.DataFrame(candles)
                df.set_index('timestamp', inplace=True)
                df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                return df
            else:
                logger.warning(f"Binance returned no data for {ticker}")
                return pd.DataFrame()
        
        # Stocks: Use yfinance
        ticker_obj = yf.Ticker(ticker)
        data = ticker_obj.history(period=period, interval=interval, auto_adjust=True)
        
        if data.empty:
            logger.warning(f"No data returned for {ticker}")
            return pd.DataFrame()
        
        # Validate the data makes sense by checking against fast_info
        try:
            fast_price = ticker_obj.fast_info.last_price
            if fast_price and fast_price > 0 and len(data) > 0:
                df_price = data['Close'].iloc[-1]
                # Tightened from 50% to 15% — catches most stale/wrong data
                if abs(df_price - fast_price) / fast_price > 0.15:
                    logger.error(f"Data validation failed for {ticker}: History price {df_price:.2f} vs Fast price {fast_price:.2f} (deviation > 15%)")
                    return pd.DataFrame()
        except Exception:
            pass  # Validation is optional, don't fail if it errors
        
        return data
    except Exception as e:
        logger.error(f"Error fetching data for {ticker}: {e}")
        return pd.DataFrame()


def get_current_price(ticker: str) -> float:
    """Fetches the current price for a ticker."""
    try:
        # Let yfinance handle its own session (newer versions require curl_cffi, not requests.Session)
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


def get_technical_summary(ticker: str) -> dict:
    """
    Calculates key technical indicators using yfinance history.
    Returns:
        {
            "rsi": 55.4,
            "sma_20": 150.2,
            "sma_50": 145.5,
            "sma_200": 130.0,
            "price": 152.0,
            "atr": 2.5,
            "rvol": 1.8, # Relative Volume (Current Vol / 10d Avg Vol)
            "trend": "Bullish" # Simple heuristic
        }
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetch enough data for 200 SMA
        hist = stock.history(period="1y", interval="1d")
        
        if hist.empty or len(hist) < 200:
            # Try to fetch max if 1y is not enough, or return partial
            if hist.empty:
                return {}
        
        close = hist['Close']
        volume = hist['Volume']
        
        # 1. SMA
        sma_20 = close.rolling(window=20).mean().iloc[-1]
        sma_50 = close.rolling(window=50).mean().iloc[-1]
        sma_200 = close.rolling(window=200).mean().iloc[-1] if len(close) >= 200 else 0
        
        # 2. RSI (14)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        # 3. ATR (14)
        high = hist['High']
        low = hist['Low']
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
        
        # 4. RVOL (Relative Volume)
        current_vol = volume.iloc[-1]
        avg_vol_10 = volume.rolling(window=10).mean().iloc[-1]
        rvol = round(current_vol / avg_vol_10, 2) if avg_vol_10 > 0 else 1.0
        
        current_price = close.iloc[-1]
        
        # Simple Trend Heuristic
        trend = "Neutral"
        if current_price > sma_50 and sma_50 > sma_200:
            trend = "Bullish"
        elif current_price < sma_50 and sma_50 < sma_200:
            trend = "Bearish"
            
        return {
            "price": round(current_price, 2),
            "rsi": round(rsi, 2),
            "sma_20": round(sma_20, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "atr": round(atr, 2),
            "rvol": rvol,
            "trend": trend
        }
        
    except Exception as e:
        logger.error(f"Error calculating technicals for {ticker}: {e}")
        return {}


def get_analyst_recommendations(ticker: str) -> list:
    """
    Fetches analyst recommendations for a ticker using yfinance (free).
    Returns a simplified version of analyst data.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Try to get recommendations
        recs = stock.recommendations
        if recs is not None and not recs.empty:
            # Get the most recent recommendation
            latest = recs.tail(5).to_dict('records')
            return latest
        
        # Fallback: try to get basic info with analyst target
        info = stock.info
        if info:
            return [{
                'targetMeanPrice': info.get('targetMeanPrice'),
                'targetHighPrice': info.get('targetHighPrice'),
                'targetLowPrice': info.get('targetLowPrice'),
                'recommendationKey': info.get('recommendationKey'),
                'numberOfAnalystOpinions': info.get('numberOfAnalystOpinions')
            }]
        
        return []
    except Exception as e:
        logger.warning(f"Could not fetch analyst data for {ticker}: {e}")
        return []


def get_stock_screener(filters: dict = None) -> list:
    """
    Fetches stocks for "coiled spring" setups.
    Uses Yahoo predefined screeners since custom POST requires auth.
    """
    limit = 20
    if filters:
        limit = filters.get('limit', 20)
    
    # Use small cap gainers as the best proxy for volatile low-price stocks
    logger.info("Fetching coiled spring candidates from Yahoo Finance...")
    result = _fetch_yahoo_screener("small_cap_gainers", limit)
    if result:
        return result
    
    # Fallback to undervalued growth stocks
    return _fetch_yahoo_screener("undervalued_growth_stocks", limit)
