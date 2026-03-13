import requests
import yfinance as yf
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import random

def get_yf_session():
    """
    Returns a requests Session with robust retry logic and browser-like headers
    to avoid 401/429 errors from Yahoo Finance.
    """
    session = requests.Session()
    
    # Browser-like headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })

    # Robust retry strategy
    retry_strategy = Retry(
        total=5,
        backoff_factor=random.uniform(1, 3), # Randomize backoff to prevent thundering herd
        status_forcelist=[429, 500, 502, 503, 504, 401], # Retry on 401s too as they might be transient session issues
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    return session

def configure_yfinance():
    """
    Configures yfinance to use the robust session globally (where possible)
    or returns the session for manual usage.
    """
    # Unfortunately yfinance doesn't have a global session setter, 
    # but we can monkeypatch or just return the session to be passed to Ticker/download
    return get_yf_session()
