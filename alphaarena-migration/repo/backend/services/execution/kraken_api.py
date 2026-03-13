"""
Kraken API Handler - Pure Python implementation for Kraken REST API.
Handles authentication, signing, and requests.
"""

import time
import base64
import hashlib
import hmac
import requests
import urllib.parse
import os
from typing import Optional, Dict, Any
from backend.utils.logger import logger

class KrakenAPI:
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or os.getenv('KRAKEN_API_KEY')
        self.api_secret = api_secret or os.getenv('KRAKEN_API_SECRET')
        self.uri = 'https://api.kraken.com'
        self.api_version = '0'

    def _get_kraken_signature(self, urlpath: str, data: dict, secret: str) -> str:
        """Sign the request according to Kraken's requirements."""
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode()
        message = urlpath.encode() + hashlib.sha256(encoded).digest()

        mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
        sigdigest = base64.b64encode(mac.digest())
        return sigdigest.decode()

    def request(self, method: str, path: str, params: dict = None, private: bool = False) -> dict:
        """Send a request to the Kraken API."""
        urlpath = f'/{self.api_version}/{path}'
        headers = {}
        data = params or {}

        if private:
            if not self.api_key or not self.api_secret:
                return {"error": ["API_KEYS_MISSING"], "result": {}}
            
            data['nonce'] = int(time.time() * 1000)
            headers['API-Key'] = self.api_key
            headers['API-Sign'] = self._get_kraken_signature(urlpath, data, self.api_secret)

        try:
            url = self.uri + urlpath
            if method.upper() == 'GET':
                response = requests.get(url, params=data, headers=headers)
            else:
                response = requests.post(url, data=data, headers=headers)
            
            return response.json()
        except Exception as e:
            logger.error(f"Kraken API Request Error: {e}")
            return {"error": [str(e)], "result": {}}

    # --- Public Methods ---
    def get_ticker(self, pair: str):
        return self.request('GET', f'public/Ticker', {'pair': pair})

    # --- Private Methods ---
    def get_balance(self):
        return self.request('POST', 'private/Balance', private=True)

    def get_trade_balance(self, asset: str = 'ZUSD'):
        return self.request('POST', 'private/TradeBalance', {'asset': asset}, private=True)

    def add_order(self, pair: str, side: str, order_type: str, volume: str, price: str = None, extra: dict = None):
        params = {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'volume': volume,
        }
        if price:
            params['price'] = price
        if extra:
            params.update(extra)
        return self.request('POST', 'private/AddOrder', params, private=True)

    def get_earn_positions(self):
        return self.request('POST', 'private/Earn/Positions', private=True)

    def get_earn_allocations(self):
        return self.request('POST', 'private/Earn/Allocations', private=True)

    def get_staking_assets(self):
        return self.request('POST', 'private/Staking/Assets', private=True)
