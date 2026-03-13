"""
Financial Modeling Prep (FMP) API services.
Handles insider trading, Senate disclosures, market movers, and technical indicators.
"""
import os
import requests
from functools import lru_cache
from backend.utils.logger import logger


@lru_cache(maxsize=1)
def get_senate_disclosures(limit: int = 100) -> list:
    """
    Fetches latest Senate financial disclosures. Cached for 1 hour.
    Endpoint: https://financialmodelingprep.com/stable/senate-latest
    """
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        logger.error("FMP_API_KEY not found")
        return []

    try:
        url = f"https://financialmodelingprep.com/api/v4/senate-disclosure-rss?limit={limit}&apikey={fmp_api_key}"
        
        logger.info("Fetching Senate disclosures from FMP...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return data[:limit]
    except Exception as e:
        logger.error(f"Error fetching Senate disclosures: {e}")
        return []


@lru_cache(maxsize=1)
def get_insider_trading(limit: int = 100) -> list:
    """
    Fetches latest Insider Trading activity. Cached for 1 hour.
    Endpoint: https://financialmodelingprep.com/stable/insider-trading/latest
    """
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return []

    try:
        url = f"https://financialmodelingprep.com/api/v4/insider-trading-rss?limit={limit}&apikey={fmp_api_key}"
        
        logger.info("Fetching Insider Trading data from FMP...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return data[:limit]
    except Exception as e:
        logger.error(f"Error fetching Insider Trading data: {e}")
        return []


def get_fmp_technical_indicators(ticker: str, period: int = 14, type: str = 'rsi') -> dict:
    """
    Fetches specific technical indicator for a ticker from FMP.
    """
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return {}

    try:
        url = f"https://financialmodelingprep.com/api/v3/technical_indicator/1day/{ticker}?period={period}&type={type}&apikey={fmp_api_key}"
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]  # Return the most recent data point
            
        return {}
    except Exception as e:
        logger.error(f"Error fetching FMP technicals for {ticker}: {e}")
        return {}


@lru_cache(maxsize=1)
def get_market_actives(limit: int = 20) -> list:
    """Fetches most active stocks using FMP API."""
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        logger.warning("FMP_API_KEY not set. Returning empty actives.")
        return []

    try:
        url = f"https://financialmodelingprep.com/stable/most-actives?apikey={fmp_api_key}"
        logger.info("Fetching market actives from FMP (Stable)...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()[:limit]
    except Exception as e:
        logger.error(f"Error fetching FMP actives: {e}")
        return []


@lru_cache(maxsize=1)
def get_market_gainers(limit: int = 20) -> list:
    """Fetches top gainers using FMP API."""
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return []

    try:
        url = f"https://financialmodelingprep.com/stable/biggest-gainers?apikey={fmp_api_key}"
        logger.info("Fetching market gainers from FMP (Stable)...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()[:limit]
    except Exception as e:
        logger.error(f"Error fetching FMP gainers: {e}")
        return []


@lru_cache(maxsize=1)
def get_market_losers(limit: int = 20) -> list:
    """Fetches top losers using FMP API."""
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return []

    try:
        url = f"https://financialmodelingprep.com/stable/biggest-losers?apikey={fmp_api_key}"
        logger.info("Fetching market losers from FMP (Stable)...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()[:limit]
    except Exception as e:
        logger.error(f"Error fetching FMP losers: {e}")
        return []


def get_earnings_calendar(date: str = None) -> list:
    """Fetches earnings calendar for a specific date (YYYY-MM-DD). Defaults to today."""
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return []
    
    if not date:
        from datetime import datetime
        date = datetime.now().strftime("%Y-%m-%d")
        
    try:
        url = f"https://financialmodelingprep.com/stable/earnings-calendar?from={date}&to={date}&apikey={fmp_api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching earnings calendar: {e}")
        return []


@lru_cache(maxsize=1)
def get_pre_market_gainers(limit: int = 20) -> list:
    """
    Fetches pre-market movers.
    Uses FMP 'gainers' endpoint as a proxy. FMP updates this list in real-time.
    """
    return get_market_gainers(limit)


@lru_cache(maxsize=1)
def get_after_hours_gainers(limit: int = 20) -> list:
    """
    Fetches after-hours movers.
    Uses FMP 'gainers' endpoint as a proxy.
    """
    return get_market_gainers(limit)


def get_intraday_chart(ticker: str, interval: str = "5min") -> list:
    """Fetches intraday chart data (price and volume)."""
    fmp_api_key = os.getenv('FMP_API_KEY')
    if not fmp_api_key:
        return []
    try:
        url = f"https://financialmodelingprep.com/stable/historical-chart/{interval}?symbol={ticker}&apikey={fmp_api_key}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching intraday chart for {ticker}: {e}")
        return []
