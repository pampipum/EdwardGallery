import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.services import data_service

def test_predictive_data():
    print("Testing Predictive Data Endpoints...")
    
    # 1. Pre-Market
    print("\n1. Testing Pre-Market Gainers...")
    pre_market = data_service.get_pre_market_gainers(limit=5)
    print(f"   Fetched {len(pre_market)} pre-market items.")
    if pre_market:
        print(f"   Sample: {pre_market[0]}")
        
    # 2. After-Hours
    print("\n2. Testing After-Hours Gainers...")
    after_hours = data_service.get_after_hours_gainers(limit=5)
    print(f"   Fetched {len(after_hours)} after-hours items.")
    if after_hours:
        print(f"   Sample: {after_hours[0]}")
        
    # 3. General News
    print("\n3. Testing General Stock News...")
    news = data_service.get_general_stock_news(limit=5)
    print(f"   Fetched {len(news)} news items.")
    if news:
        print(f"   Sample Title: {news[0].get('title')}")
        
    # 4. Intraday Chart
    print("\n4. Testing Intraday Chart (AAPL)...")
    chart = data_service.get_intraday_chart("AAPL", interval="5min")
    print(f"   Fetched {len(chart)} chart points.")
    if chart:
        print(f"   Sample Point: {chart[0]}")
        
    # 5. Analyst Recs
    print("\n5. Testing Analyst Recs (AAPL)...")
    recs = data_service.get_analyst_recommendations("AAPL")
    print(f"   Fetched Recs: {recs}")

if __name__ == "__main__":
    test_predictive_data()
