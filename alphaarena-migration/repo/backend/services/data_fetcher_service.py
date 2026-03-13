import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from backend.utils.logger import logger
from backend.runtime import state_dir

load_dotenv()

# Determine cache path relative to this file to ensure it's findable
CACHE_PATH = str(state_dir("cache") / "data_cache.json")
MASSIVE_KEY = os.getenv("MASSIVE_API_KEY")

# -----------------------------
#   DEXSCREENER DATA (For New/Meme Coins)
# -----------------------------
def get_dex_price(token_address: str):
    """
    Fetches price from DexScreener for a given token address.
    """
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{token_address}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        pairs = data.get("pairs", [])
        if pairs:
            # Sort by liquidity to get the best price
            pairs.sort(key=lambda x: float(x.get("liquidity", {}).get("usd", 0)), reverse=True)
            best_pair = pairs[0]
            price_usd = float(best_pair.get("priceUsd", 0))
            return price_usd
            
        return None
    except Exception as e:
        logger.warning(f"DexScreener fetch failed for {token_address}: {e}")
        return None


# -----------------------------
#   CACHE HELPERS
# -----------------------------
def save_cache(data):
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save data cache: {e}")

def load_cache():
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load data cache: {e}")
        return {}

# -----------------------------
#   BINANCE DATA
# -----------------------------
def normalize_ticker_for_binance(ticker: str) -> str:
    """Convert Yahoo/standard ticker format to Binance format."""
    # Remove -USD suffix and append USDT
    if ticker.endswith("-USD"):
        base = ticker.replace("-USD", "")
        return f"{base}USDT"
    return ticker

def get_binance_spot_price(ticker: str) -> float:
    """
    Fetches current spot price from Binance.
    Falls back to Futures API if symbol not found on Spot.
    
    Args:
        ticker (str): Ticker in format 'BTC-USD', 'ETH-USD', etc.
        
    Returns:
        float: Current price or None if failed
    """
    try:
        symbol = normalize_ticker_for_binance(ticker)
        
        # Try Spot API first
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {"symbol": symbol}
        
        r = requests.get(url, params=params, timeout=10)
        
        # If 400 (symbol not found on Spot), try Futures
        if r.status_code == 400:
            logger.info(f"{ticker} not on Binance Spot, trying Futures...")
            futures_url = "https://fapi.binance.com/fapi/v1/ticker/price"
            r = requests.get(futures_url, params=params, timeout=10)
        
        r.raise_for_status()
        data = r.json()
        
        return float(data.get("price", 0))
    except Exception as e:
        logger.warning(f"Binance price fetch failed for {ticker}: {e}")
        return None
def get_binance_funding(symbol="BTCUSDT"):
    try:
        # Normalize ticker
        if "-USD" in symbol:
            symbol = normalize_ticker_for_binance(symbol)
        
        url = "https://fapi.binance.com/fapi/v1/fundingRate"
        params = {"symbol": symbol, "limit": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            data = data[0]
            return {
                "symbol": symbol,
                "funding_rate": float(data["fundingRate"]),
                "funding_time": data["fundingTime"]
            }
        return None
    except Exception as e:
        logger.warning(f"Binance funding fetch failed for {symbol}: {e}")
        return None

def get_binance_open_interest(symbol="BTCUSDT"):
    try:
        if "-USD" in symbol:
            symbol = normalize_ticker_for_binance(symbol)

        url = "https://fapi.binance.com/futures/data/openInterestHist"
        # Using 5m period to get recent data
        params = {"symbol": symbol, "period": "5m", "limit": 1}
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data:
            data = data[0]
            return {
                "symbol": symbol,
                "open_interest": float(data["sumOpenInterestValue"])
            }
        return None
    except Exception as e:
        logger.warning(f"Binance OI fetch failed for {symbol}: {e}")
        return None

def get_binance_candles(symbol="BTCUSDT", interval="1h", limit=100):
    """
    Fetches OHLCV candles from Binance Futures.
    
    Args:
        symbol (str): Trading pair (e.g., 'HYPEUSDT')
        interval (str): Timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
        limit (int): Number of candles to fetch
        
    Returns:
        list: List of dictionaries [{'timestamp': ..., 'open': ..., ...}, ...]
    """
    try:
        # Normalize ticker
        if "-USD" in symbol:
            symbol = normalize_ticker_for_binance(symbol)

        url = "https://fapi.binance.com/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # Binance format: [Open Time, Open, High, Low, Close, Volume, ...]
        candles = []
        for c in data:
            candles.append({
                "timestamp": datetime.fromtimestamp(c[0]/1000),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5])
            })
            
        return candles
    except Exception as e:
        logger.warning(f"Binance candle fetch failed for {symbol}: {e}")
        return []

# -----------------------------
#   MASSIVE OPTIONS DATA (EX-POLYGON)
# -----------------------------
def get_massive_options_oi(symbol="AAPL"):
    if not MASSIVE_KEY:
        return {"symbol": symbol, "error": "Missing MASSIVE_API_KEY"}

    try:
        # Using the correct Massive API endpoint as per documentation:
        # GET /v3/reference/options/contracts with underlying_ticker query param
        url = "https://api.massive.com/v3/reference/options/contracts"
        params = {
            "underlying_ticker": symbol,
            "expired": "false",  # Only active contracts
            "limit": 1000,
            "sort": "ticker",
            "order": "asc"
        }
        headers = {"Authorization": f"Bearer {MASSIVE_KEY}"}

        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()

        # Massive API v3 uses `results` array containing contract objects
        options = data.get("results", [])

        if not options:
            return {"symbol": symbol, "options_oi": None}

        # Note: The /v3/reference/options/contracts endpoint returns contract metadata
        # (contract_type, strike_price, expiration_date, etc.) but may not include
        # open_interest directly. If OI data is needed, it may require a different
        # endpoint. For now, we return the contract count as a proxy metric.
        total_contracts = len(options)

        return {
            "symbol": symbol,
            "options_oi": total_contracts,
            "contracts_count": total_contracts
        }
    except Exception as e:
        logger.warning(f"Massive OI fetch failed for {symbol}: {e}")
        return {"symbol": symbol, "options_oi": None, "error": str(e)}

# -----------------------------
#   MAIN FETCH PIPELINE
# -----------------------------
def fetch_all_deep_dive_data(stock_tickers: list, crypto_tickers: list):
    logger.info("Fetching Deep Dive Data (Funding/OI)...")
    
    result = {
        "timestamp": int(time.time()),
        "iso_timestamp": datetime.now().isoformat(),
        "crypto": {},
        "stocks": {}
    }

    # Crypto
    for s in crypto_tickers:
        funding = get_binance_funding(s)
        oi = get_binance_open_interest(s)
        
        result["crypto"][s] = {
            "funding": funding,
            "open_interest": oi
        }

    # Stocks (options OI)
    for s in stock_tickers:
        oi = get_massive_options_oi(s)
        result["stocks"][s] = {
            "options_oi": oi
        }

    # Save
    save_cache(result)
    logger.info("[OK] Deep Dive Data updated.")
    return result

if __name__ == "__main__":
    # Test run
    print(fetch_all_deep_dive_data(["AAPL", "TSLA", "NVDA"], ["BTC-USD", "ETH-USD"]))
