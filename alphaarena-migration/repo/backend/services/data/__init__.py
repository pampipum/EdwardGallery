# Data Service Modules
# This package contains modularized data fetching services.

from backend.services.data.yahoo_service import (
    fetch_market_data,
    get_current_price,
    get_technical_summary,
    get_analyst_recommendations,
    _fetch_yahoo_screener,
    _fetch_yahoo_custom_screener,
    get_stock_screener
)

from backend.services.data.alpha_vantage_service import (
    AlphaVantageRateLimiter,
    get_alpha_vantage_news,
    get_ticker_news,
    get_general_stock_news,
    _av_rate_limiter
)

from backend.services.data.fmp_service import (
    get_senate_disclosures,
    get_insider_trading,
    get_fmp_technical_indicators,
    get_market_actives,
    get_market_gainers,
    get_market_losers,
    get_earnings_calendar,
    get_pre_market_gainers,
    get_after_hours_gainers,
    get_intraday_chart
)

from backend.services.data.sentiment_service import (
    get_macro_data,
    get_crypto_fear_greed
)

from backend.services.data.config_service import (
    get_top_tickers
)

__all__ = [
    # Yahoo/yfinance
    'fetch_market_data',
    'get_current_price',
    'get_technical_summary',
    'get_analyst_recommendations',
    '_fetch_yahoo_screener',
    '_fetch_yahoo_custom_screener',
    'get_stock_screener',
    
    # Alpha Vantage
    'AlphaVantageRateLimiter',
    'get_alpha_vantage_news',
    'get_ticker_news',
    'get_general_stock_news',
    '_av_rate_limiter',
    
    # FMP
    'get_senate_disclosures',
    'get_insider_trading',
    'get_fmp_technical_indicators',
    'get_market_actives',
    'get_market_gainers',
    'get_market_losers',
    'get_earnings_calendar',
    'get_pre_market_gainers',
    'get_after_hours_gainers',
    'get_intraday_chart',
    
    # Sentiment/Macro
    'get_macro_data',
    'get_crypto_fear_greed',
    
    # Config
    'get_top_tickers',
]
