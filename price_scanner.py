import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass

import httpx
from config import Config


@dataclass
class PriceData:
    token_in: str
    token_out: str
    price: float
    price_usd: float
    source: str
    timestamp: float
    confidence: float


class PriceScanner:
    JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v3"
    JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"

    def __init__(self):
        self.price_cache = {}
        self.cache_ttl = Config.PRICE_CACHE_TTL_SECONDS
        self.client = None
        self.request_count = 0
        self.error_count = 0
        self._semaphore = asyncio.Semaphore(Config.BATCH_SIZE)

    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(8.0, connect=3.0), limits=httpx.Limits(max_connections=Config.MAX_CONNECTIONS, max_keepalive_connections=20), http2=True, )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def _cache_key(self, token_in, token_out, size):
        return f"{token_in}:{token_out}:{size:.0f}"

    def _get_cached(self, key):
        if key in self.price_cache:
            data, cached_at = self.price_cache[key]
            if time.time() - cached_at < self.cache_ttl:
                return data
            del self.price_cache[key]
        return None

    def _set_cache(self, key, data):
        self.price_cache[key] = (data, time.time())
        if len(self.price_cache) > 100:
            oldest = min(self.price_cache, key=lambda k: self.price_cache[k][1])
            del self.price_cache[oldest]

    async def fetch_all_usd_prices(self):
        if not self.client:
            return {}
        mints = list(Config.TOKEN_MINTS.values())
        try:
            async with self._semaphore:
                response = await self.client.get(self.JUPITER_PRICE_URL, params={"ids": ",".join(mints)})
            self.request_count += 1
            if response.status_code != 200:
                self.error_count += 1
                return {}
            data = response.json()
            prices = {}
            for mint, info in data.get("data", {}).items():
                if info and "price" in info:
                    prices[mint] = float(info["price"])
            return prices
        except Exception:
            self.error_count += 1
            return {}

    async def fetch_quote_fast(self, input_mint, output_mint, amount, slippage_bps=50):
        if not self.client:
            return None
        params = {
            "inputMint": input_mint, "outputMint": output_mint, "amount": str(amount), "slippageBps": str(slippage_bps), "restrictIntermediateTokens": "true", }
        try:
            async with self._semaphore:
                response = await self.client.get(self.JUPITER_QUOTE_URL, params=params)
            self.request_count += 1
            if response.status_code == 200:
                return response.json()
            self.error_count += 1
            return None
        except Exception:
            self.error_count += 1
            return None

    async def get_pair_price(self, token_a, token_b, trade_size_usd=50.0):
        cache_key = self._cache_key(token_a, token_b, trade_size_usd)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        mint_a = Config.TOKEN_MINTS.get(token_a)
        mint_b = Config.TOKEN_MINTS.get(token_b)
        if not mint_a or not mint_b:
            return None
        decimals_a = Config.TOKEN_DECIMALS.get(token_a, 9)
        amount = int(trade_size_usd * (10 ** decimals_a))
        quote = await self.fetch_quote_fast(mint_a, mint_b, amount)
        if not quote:
            return None
        out_amount = int(quote.get("outAmount", 0))
        decimals_b = Config.TOKEN_DECIMALS.get(token_b, 6)
        if out_amount == 0:
            return None
        out_human = out_amount / (10 ** decimals_b)
        price = out_human / trade_size_usd if trade_size_usd > 0 else 0
        usd_prices = await self.fetch_all_usd_prices()
        price_usd = usd_prices.get(mint_b, 0.0)
        try:
            impact = float(quote.get("priceImpactPct", "0"))
        except:
            impact = 0.0
        confidence = max(0.0, 1.0 - (impact / 100))
        data = PriceData(token_a, token_b, price, price_usd, "jupiter", time.time(), confidence)
        self._set_cache(cache_key, data)
        return data

    async def scan_all_pairs(self, trade_size_usd=50.0):
        results = {}
        tasks = []
        pair_names = []
        for token_a, token_b in Config.PAIRS:
            tasks.append(self.get_pair_price(token_a, token_b, trade_size_usd))
            pair_names.append(f"{token_a}/{token_b}")
        start = time.time()
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        for name, price_data in zip(pair_names, prices):
            if isinstance(price_data, Exception):
                continue
            if price_data:
                results[name] = price_data
        print(f"   Scanned {len(Config.PAIRS)} pairs in {elapsed:.2f}s")
        return results

    def get_stats(self):
        return {
            "requests": self.request_count, "errors": self.error_count, "error_rate": round(self.error_count / max(self.request_count, 1), 3), "cache_size": len(self.price_cache), }
