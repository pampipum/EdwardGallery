"""
Alpha Vantage API services for news and sentiment data.
Includes rate limiting and caching.
"""
import json
import os
import threading
import requests
import yfinance as yf
from datetime import datetime, timedelta
from backend.utils.logger import logger
from backend.runtime import state_dir


class AlphaVantageRateLimiter:
    """
    Rate limiter for Alpha Vantage API to stay within 25 calls per day.
    Tracks calls in a persistent JSON file and resets daily.
    """
    def __init__(self, max_calls_per_day: int = 25):
        self.max_calls = max_calls_per_day
        self.tracker_file = str(state_dir("cache") / "alpha_vantage_calls.json")
        self._lock = threading.RLock()
        
    def _load_tracker(self) -> dict:
        """Load call tracker from file"""
        if os.path.exists(self.tracker_file):
            try:
                with open(self.tracker_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"date": "", "calls_made": 0, "call_log": []}
    
    def _save_tracker(self, tracker: dict):
        """Save call tracker to file"""
        try:
            with open(self.tracker_file, 'w') as f:
                json.dump(tracker, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rate limit tracker: {e}")
    
    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format (UTC)"""
        return datetime.utcnow().strftime("%Y-%m-%d")
    
    def can_make_call(self) -> bool:
        """Check if we can make another API call today"""
        with self._lock:
            tracker = self._load_tracker()
            current_date = self._get_current_date()
            
            # Reset if new day
            if tracker["date"] != current_date:
                return True
            
            return tracker["calls_made"] < self.max_calls
    
    def record_call(self, ticker: str):
        """Record an API call"""
        with self._lock:
            tracker = self._load_tracker()
            current_date = self._get_current_date()
            
            # Reset if new day
            if tracker["date"] != current_date:
                tracker = {"date": current_date, "calls_made": 0, "call_log": []}
            
            # Record call
            tracker["calls_made"] += 1
            tracker["call_log"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "ticker": ticker
            })
            
            self._save_tracker(tracker)
    
    def get_remaining_calls(self) -> int:
        """Get number of remaining calls for today"""
        with self._lock:
            tracker = self._load_tracker()
            current_date = self._get_current_date()
            
            if tracker["date"] != current_date:
                return self.max_calls
            
            return max(0, self.max_calls - tracker["calls_made"])


# Global rate limiter instance
_av_rate_limiter = AlphaVantageRateLimiter()

# Global lock for news cache
_news_cache_lock = threading.Lock()


def _map_ticker_to_alpha_vantage(ticker: str) -> str:
    """
    Maps our ticker format to Alpha Vantage format.
    - Stocks: use as-is (AAPL, TSLA, etc.)
    - Crypto: BTC-USD -> CRYPTO:BTC, ETH-USD -> CRYPTO:ETH
    """
    if "-USD" in ticker:
        # Crypto ticker
        base = ticker.replace("-USD", "")
        return f"CRYPTO:{base}"
    else:
        # Stock ticker - use as-is
        return ticker


def get_alpha_vantage_news(ticker: str) -> list:
    """
    Fetches news from Alpha Vantage News API with rate limiting and caching.
    Returns a list of dictionaries with 'title', 'publisher', 'link', and 'published'.
    """
    # Cache file
    cache_file = str(state_dir("cache") / "alpha_vantage_news_cache.json")
    
    # Check cache first
    with _news_cache_lock:
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                    if ticker in cache:
                        cached_data = cache[ticker]
                        cache_time = datetime.fromisoformat(cached_data['timestamp'])
                        # Use cache if less than 24 hours old
                        if datetime.now() - cache_time < timedelta(hours=24):
                            logger.info(f"   [CACHE HIT] Using cached Alpha Vantage news for {ticker}")
                            return cached_data['news']
            except Exception as e:
                logger.error(f"Error reading news cache: {e}")
    
    # Check rate limit
    if not _av_rate_limiter.can_make_call():
        remaining = _av_rate_limiter.get_remaining_calls()
        logger.warning(f"   [RATE LIMIT] Alpha Vantage daily limit reached ({remaining} calls remaining). Using cached/empty news for {ticker}")
        return []
    
    # Fetch from API
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        logger.error("   [ERROR] ALPHA_VANTAGE_API_KEY not set")
        return []
    
    try:
        # Map ticker to Alpha Vantage format
        av_ticker = _map_ticker_to_alpha_vantage(ticker)
        
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': av_ticker,
            'limit': 10,  # Get top 10 news items
            'apikey': api_key
        }
        
        logger.info(f"   [API CALL] Fetching Alpha Vantage news for {ticker} ({av_ticker})...")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Record the API call
        _av_rate_limiter.record_call(ticker)
        
        # Parse response
        formatted_news = []
        if 'feed' in data:
            for item in data['feed'][:5]:  # Limit to top 5
                formatted_news.append({
                    "title": item.get("title", ""),
                    "publisher": item.get("source", ""),
                    "link": item.get("url", ""),
                    "published": item.get("time_published", "")
                })
        
        # Cache the result
        try:
            with _news_cache_lock:
                cache = {}
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'r') as f:
                            cache = json.load(f)
                    except Exception:
                        pass # Start fresh if read fails
                
                cache[ticker] = {
                    'timestamp': datetime.now().isoformat(),
                    'news': formatted_news
                }
                
                with open(cache_file, 'w') as f:
                    json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error caching news: {e}")
        
        logger.info(f"   [SUCCESS] Fetched {len(formatted_news)} news items for {ticker}. Remaining calls: {_av_rate_limiter.get_remaining_calls()}")
        return formatted_news
        
    except Exception as e:
        logger.error(f"Error fetching Alpha Vantage news for {ticker}: {e}")
        return []


def get_ticker_news(ticker: str) -> list:
    """
    Fetches recent news for a ticker.
    Prioritizes Alpha Vantage, falls back to Yahoo Finance (yfinance) if rate limited or empty.
    """
    # 1. Try Alpha Vantage
    news = get_alpha_vantage_news(ticker)
    if news:
        return news
        
    # 2. Fallback to Yahoo Finance
    try:
        logger.info(f"   [FALLBACK] Fetching news for {ticker} from Yahoo Finance...")
        stock = yf.Ticker(ticker)
        yf_news = stock.news
        
        formatted_news = []
        for item in yf_news:
            # Yahoo news items usually have 'title', 'publisher', 'link', 'providerPublishTime'
            pub_time = item.get('providerPublishTime', 0)
            
            formatted_news.append({
                "title": item.get('title', ''),
                "publisher": item.get('publisher', 'Yahoo Finance'),
                "link": item.get('link', ''),
                "published": datetime.fromtimestamp(pub_time).isoformat() if pub_time else ""
            })
            
        return formatted_news[:5]
    except Exception as e:
        logger.error(f"Error fetching Yahoo Finance news for {ticker}: {e}")
        return []


def get_general_stock_news(limit: int = 50) -> list:
    """
    Fetches general stock market news using Alpha Vantage API.
    Uses cached results if available to conserve API calls.
    """
    # Cache file for general news
    cache_file = str(state_dir("cache") / "general_news_cache.json")
    
    # Check cache first (valid for 6 hours)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cache = json.load(f)
                cache_time = datetime.fromisoformat(cache['timestamp'])
                if datetime.now() - cache_time < timedelta(hours=6):
                    logger.info("[CACHE HIT] Using cached general news")
                    return cache['news'][:limit]
        except Exception as e:
            logger.error(f"Error reading general news cache: {e}")
    
    # Fetch from Alpha Vantage
    api_key = os.getenv('ALPHA_VANTAGE_API_KEY')
    if not api_key:
        logger.warning("ALPHA_VANTAGE_API_KEY not set. Returning empty news.")
        return []
    
    # Check rate limit
    if not _av_rate_limiter.can_make_call():
        logger.warning("Alpha Vantage rate limit reached. Using cached/empty news.")
        return []
    
    try:
        url = "https://www.alphavantage.co/query"
        params = {
            'function': 'NEWS_SENTIMENT',
            'topics': 'financial_markets',
            'limit': min(limit, 50),  # AV max is 50
            'apikey': api_key
        }
        
        logger.info("Fetching general stock news from Alpha Vantage...")
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Record the API call
        _av_rate_limiter.record_call('GENERAL_NEWS')
        
        # Parse response
        formatted_news = []
        if 'feed' in data:
            for item in data['feed'][:limit]:
                formatted_news.append({
                    "title": item.get("title", ""),
                    "publisher": item.get("source", ""),
                    "link": item.get("url", ""),
                    "published": item.get("time_published", ""),
                    "summary": item.get("summary", "")[:200] if item.get("summary") else ""
                })
        
        # Cache the result
        try:
            with open(cache_file, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'news': formatted_news
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Error caching general news: {e}")
        
        logger.info(f"Fetched {len(formatted_news)} general news items. Remaining AV calls: {_av_rate_limiter.get_remaining_calls()}")
        return formatted_news
        
    except Exception as e:
        logger.error(f"Error fetching general stock news: {e}")
        return []
