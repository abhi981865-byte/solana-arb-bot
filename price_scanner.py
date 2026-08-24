"""
price_scanner.py

Fetches real, on-chain pool prices from DexScreener for a set of Solana
token pairs, across whichever DEXs currently have pools for those tokens.

Why DexScreener instead of Jupiter's dexes= trick:
- Jupiter's swap-quote API with dexes=<venue> asks "what would a swap look
  like IF routed only through this venue" — an estimate, and getting
  per-DEX prices for one pair meant 4 sequential quote calls (slow, and
  price can move between the 1st and 4th call — a major cause of failed
  and partial fills once a trade was attempted).
- DexScreener returns the REAL, current on-chain price of every pool a
  token trades in, tagged by DEX, in a SINGLE API call per token. Faster
  and more accurate — and no API key needed.

Docs: https://docs.dexscreener.com/api/reference
"""

import requests
import time
from datetime import datetime, timezone

DEXSCREENER_URL = "https://api.dexscreener.com/token-pairs/v1/solana"

# Mint addresses (mainnet)
MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}

# Only trust pools quoted against one of these — filters out noisy/illiquid
# meme-coin pairings that would otherwise show up when we query a token's
# full pool list (e.g. we don't want a stray SOL/RandomMemecoin pool
# affecting SOL's price comparison).
TRUSTED_QUOTE_MINTS = {MINTS["USDC"], MINTS["USDT"], MINTS["SOL"]}

# Pairs to scan: (base, quote). Only `base`'s mint is queried against
# DexScreener — DexScreener normalizes every pool's price to USD
# (priceUsd), so pools can be compared across different quote tokens.
PAIRS = [
    ("SOL", "USDC"),
    ("SOL", "USDT"),
    ("USDC", "USDT"),
    ("BONK", "USDC"),
    ("JUP", "USDC"),
    ("WIF", "USDC"),
]

# Minimum pool liquidity (USD) to trust a price from at all — thin pools
# give attractive-looking prices that can't actually absorb our trade size.
# (See spread_detector.py's MIN_LIQUIDITY_MULTIPLE for a trade-size-
# relative check layered on top of this absolute floor.)
MIN_POOL_LIQUIDITY_USD = 5000


def fetch_token_pairs(mint, retries=3):
    """Fetch every DexScreener-tracked pool for a token mint on Solana."""
    url = f"{DEXSCREENER_URL}/{mint}"
    for attempt in range(retries):
        start = time.monotonic()
        try:
            resp = requests.get(url, timeout=10)
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            if resp.status_code == 200:
                data = resp.json()
                return (data if isinstance(data, list) else []), latency_ms
            else:
                print(f"[price_scanner] HTTP {resp.status_code} for {mint[:6]}: {resp.text[:200]}")
        except requests.RequestException as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            print(f"[price_scanner] Request failed (attempt {attempt+1}/{retries}, {latency_ms}ms): {e}")
        time.sleep(1.0 * (attempt + 1))
    return [], None


def scan_all_pairs():
    """
    Scans every configured pair using DexScreener. Returns:
    {
        "results": { "SOL/USDC": {"Raydium": 152.3, "Meteora": 152.5, ...}, ... },
        "latency": {
            "SOL/USDC": {
                "total_scan_ms": ...,
                "call_latency_ms": ...,
                "per_pool_liquidity_usd": {"Raydium": 45000, ...},
                "scanned_at": "2026-08-24T...",
            }, ...
        }
    }
    Only one DexScreener call is made per unique base token (cached), even
    if it appears in multiple configured pairs (e.g. SOL in both SOL/USDC
    and SOL/USDT).
    """
    results = {}
    latency = {}
    mint_cache = {}

    for base, quote in PAIRS:
        pair_name = f"{base}/{quote}"
        base_mint = MINTS[base]
        scan_start = time.monotonic()

        if base_mint not in mint_cache:
            pools, call_latency_ms = fetch_token_pairs(base_mint)
            mint_cache[base_mint] = pools
        else:
            pools = mint_cache[base_mint]
            call_latency_ms = 0.0  # cached — no new call made

        prices = {}
        pool_liquidity = {}

        for pool in pools:
            dex_id = pool.get("dexId")
            price_usd = pool.get("priceUsd")
            liquidity_usd = (pool.get("liquidity") or {}).get("usd")

            if not dex_id or price_usd is None:
                continue

            base_addr = (pool.get("baseToken") or {}).get("address")
            quote_addr = (pool.get("quoteToken") or {}).get("address")
            other_token = quote_addr if base_addr == base_mint else base_addr
            if other_token not in TRUSTED_QUOTE_MINTS:
                continue  # skip noisy/illiquid meme-coin pairings

            try:
                price_usd = float(price_usd)
            except (TypeError, ValueError):
                continue

            if liquidity_usd is not None and liquidity_usd < MIN_POOL_LIQUIDITY_USD:
                continue  # too thin to trust

            dex_label = dex_id.replace("-", " ").title()

            # Keep the most liquid pool per DEX for this token
            existing_liq = pool_liquidity.get(dex_label, -1)
            if liquidity_usd is not None and liquidity_usd > existing_liq:
                prices[dex_label] = price_usd
                pool_liquidity[dex_label] = liquidity_usd

        total_scan_ms = round((time.monotonic() - scan_start) * 1000, 1)
        results[pair_name] = prices
        latency[pair_name] = {
            "total_scan_ms": total_scan_ms,
            "call_latency_ms": call_latency_ms,
            "per_pool_liquidity_usd": pool_liquidity,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    return {"results": results, "latency": latency}


if __name__ == "__main__":
    data = scan_all_pairs()
    for pair, prices in data["results"].items():
        info = data["latency"][pair]
        print(f"\n{pair}: (scan took {info['total_scan_ms']}ms)")
        for dex, price in prices.items():
            liq = info["per_pool_liquidity_usd"].get(dex, 0)
            print(f"  {dex}: {price:.6f} (liquidity: ${liq:,.0f})")