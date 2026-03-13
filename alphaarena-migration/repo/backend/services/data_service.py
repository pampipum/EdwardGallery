"""
Data Service - Backward Compatibility Layer

This module re-exports all data fetching functions from the new modular structure
in backend/services/data/ for backward compatibility with existing code.

The codebase has been modularized into:
- config_service.py: Ticker configuration
- yahoo_service.py: yfinance market data and technicals
- alpha_vantage_service.py: News and rate limiting
- fmp_service.py: FMP API (disclosures, movers, charts)
- sentiment_service.py: Macro data and crypto fear/greed
"""

# Re-export everything from the new modular structure
from backend.services.data import (
    # Config
    get_top_tickers,
    
    # Yahoo/yfinance
    fetch_market_data,
    get_current_price,
    get_technical_summary,
    get_analyst_recommendations,
    _fetch_yahoo_screener,
    _fetch_yahoo_custom_screener,
    get_stock_screener,
    
    # Alpha Vantage
    AlphaVantageRateLimiter,
    get_alpha_vantage_news,
    get_ticker_news,
    get_general_stock_news,
    _av_rate_limiter,
    
    # FMP
    get_senate_disclosures,
    get_insider_trading,
    get_fmp_technical_indicators,
    get_market_actives,
    get_market_gainers,
    get_market_losers,
    get_earnings_calendar,
    get_pre_market_gainers,
    get_after_hours_gainers,
    get_intraday_chart,
    
    # Sentiment/Macro
    get_macro_data,
    get_crypto_fear_greed,
)

# Expose all for backward compatibility
__all__ = [
    'get_top_tickers',
    'fetch_market_data',
    'get_current_price',
    'get_technical_summary',
    'get_analyst_recommendations',
    '_fetch_yahoo_screener',
    '_fetch_yahoo_custom_screener',
    'get_stock_screener',
    'AlphaVantageRateLimiter',
    'get_alpha_vantage_news',
    'get_ticker_news',
    'get_general_stock_news',
    '_av_rate_limiter',
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
    'get_macro_data',
    'get_crypto_fear_greed',
]
