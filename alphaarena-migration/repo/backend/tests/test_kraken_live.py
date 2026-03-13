import os
import sys
from dotenv import load_dotenv

# Add parent dir to path to import backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.execution.kraken_api import KrakenAPI

def test_kraken():
    load_dotenv()
    
    key = os.getenv('KRAKEN_API_KEY')
    secret = os.getenv('KRAKEN_API_SECRET')
    
    if not key or not secret:
        print("❌ Error: KRAKEN_API_KEY or KRAKEN_API_SECRET not found in .env")
        return

    print(f"Testing Kraken API with key: {key[:5]}...{key[-5:]}")
    api = KrakenAPI(key, secret)
    
    # Test 1: Public Ticker
    print("\n1. Testing Public API (Ticker SOL/USD)...")
    ticker = api.get_ticker("SOLUSD")
    if ticker.get("error"):
        print(f"❌ Public API Error: {ticker['error']}")
    else:
        price = ticker['result'].get(next(iter(ticker['result'])))['c'][0]
        print(f"✅ Public API Success! SOL Price: ${price}")

    # Test 2: Private Balance
    print("\n2. Testing Private API (Balance)...")
    balance = api.get_balance()
    if balance.get("error"):
        print(f"❌ Private API Error: {balance['error']}")
    else:
        print("✅ Private API Success! Holdings found:")
        results = balance.get("result", {})
        for asset, qty in results.items():
            if float(qty) > 0:
                print(f"   - {asset}: {qty}")
                
    # Test 3: Earn Positions
    print("\n3. Testing Earn API (Staking)...")
    for method_name in ["get_earn_positions", "get_earn_allocations", "get_staking_assets"]:
        print(f"   Trying method: {method_name}...")
        method = getattr(api, method_name)
        res = method()
        if res.get("error"):
            print(f"   ❌ {method_name} Error: {res['error']}")
        else:
            print(f"   ✅ {method_name} Success!")
            print(f"      Result keys: {res.get('result', {}).keys()}")

if __name__ == "__main__":
    test_kraken()
