"""
price_scanner.py
Fetches quote prices from Jupiter Aggregator for a set of token pairs,
requesting quotes via different DEX-only route restrictions (Raydium, Orca,
Meteora) so we can compare effective prices across venues.

Jupiter's quote API already aggregates across all DEXs and finds the best
route by default. To compare *individual* DEX prices (needed for arbitrage
spread detection) we restrict the route with `dexes=` param to force a quote
through a single venue.

Docs: https://station.jup.ag/docs/apis/swap-api
"""

import requests
import time
from datetime import datetime, timezone

JUPITER_QUOTE_URL = "https://lite-api.jup.ag/swap/v1/quote"
# NOTE: The old quote-api.jup.ag/v6/ endpoint was deprecated Oct 2025.
# lite-api.jup.ag is Jupiter's current free tier — no API key needed.
# If Jupiter later fully deprecates lite-api.jup.ag, switch to:
#   https://api.jup.ag/swap/v1/quote  (requires a free API key from
#   https://portal.jup.ag, sent as header x-api-key)

# Mint addresses (mainnet)
MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
}

# Pairs to scan: (base, quote)
# BONK/JUP/WIF added — more volatile, often wider (but riskier) spreads.
PAIRS = [
    ("SOL", "USDC"),
    ("SOL", "USDT"),
    ("USDC", "USDT"),
    ("BONK", "USDC"),
    ("JUP", "USDC"),
    ("WIF", "USDC"),
]

# DEXs to compare individually. These MUST be exact labels from Jupiter's
# /program-id-to-label endpoint (https://lite-api.jup.ag/swap/v1/program-id-to-label)
# — bare names like "Orca" or "Meteora" do NOT match anything and will
# silently return empty routes. Verified exact labels as of this writing:
#   "Raydium"        (Raydium's main AMM)
#   "Orca Whirlpool"  (Orca's concentrated liquidity pools)
#   "Meteora DLMM"    (Meteora's dynamic liquidity pools)
# If quotes start coming back empty for a DEX, re-check the label list at
# the endpoint above — Jupiter renames/adds venues periodically.
DEXES = ["Raydium", "Orca Whirlpool", "Meteora DLMM"]

# Base amount to quote in the *smallest unit* of the input token.
# Verify these against the mint's actual decimals if quotes look wrong —
# BONK=5, JUP=6, WIF=6 are correct as of writing but always double check.
DECIMALS = {"SOL": 9, "USDC": 6, "USDT": 6, "BONK": 5, "JUP": 6, "WIF": 6}

# Quote size varies per token since $ value per unit differs wildly
# (10 SOL ~ $1500, but 10 BONK is a fraction of a cent — need bigger amount)
QUOTE_SIZE_UI_OVERRIDES = {
    "SOL": 10,
    "USDC": 10,
    "USDT": 10,
    "BONK": 5_000_000,   # BONK is worth a tiny fraction of a cent per unit
    "JUP": 50,
    "WIF": 20,
}
QUOTE_SIZE_UI = 10  # fallback default


def get_quote(input_mint, output_mint, amount, dex=None, retries=3):
    """
    Fetch a single quote from Jupiter. Returns (json_or_None, latency_ms).
    Latency is measured even on failure, since slow failures matter too
    (a bot that's "profitable" only because it's too slow to notice failures
    is not actually profitable).
    """
    params = {
        "inputMint": input_mint,
        "outputMint": output_mint,
        "amount": amount,
        "slippageBps": 50,  # 0.5% slippage tolerance for quoting purposes
    }
    if dex:
        params["dexes"] = dex

    for attempt in range(retries):
        start = time.monotonic()
        try:
            resp = requests.get(JUPITER_QUOTE_URL, params=params, timeout=10)
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            if resp.status_code == 200:
                return resp.json(), latency_ms
            else:
                print(f"[price_scanner] HTTP {resp.status_code} for {dex or 'aggregate'} "
                      f"{input_mint[:6]}->{output_mint[:6]}: {resp.text[:200]}")
        except requests.RequestException as e:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            print(f"[price_scanner] Request failed (attempt {attempt+1}/{retries}, {latency_ms}ms): {e}")
        time.sleep(1.5 * (attempt + 1))
    return None, None


def scan_pair(base, quote):
    """
    Get per-DEX prices for a given base/quote pair, plus latency info.
    Returns (prices_dict, latency_info_dict, scan_started_at_iso)
    """
    input_mint = MINTS[base]
    output_mint = MINTS[quote]
    quote_size_ui = QUOTE_SIZE_UI_OVERRIDES.get(base, QUOTE_SIZE_UI)
    amount = int(quote_size_ui * (10 ** DECIMALS[base]))

    scan_started_at = datetime.now(timezone.utc).isoformat()
    scan_start_monotonic = time.monotonic()

    prices = {}
    latencies = {}
    price_impacts = {}
    for dex in DEXES:
        q, latency_ms = get_quote(input_mint, output_mint, amount, dex=dex)
        if latency_ms is not None:
            latencies[dex] = latency_ms
        if q is None or "outAmount" not in q:
            continue
        out_amount = int(q["outAmount"]) / (10 ** DECIMALS[quote])
        price = out_amount / quote_size_ui
        prices[dex] = price
        # priceImpactPct is Jupiter's own estimate of slippage for this quote size —
        # useful reality-check against our own spread math.
        if "priceImpactPct" in q:
            try:
                price_impacts[dex] = float(q["priceImpactPct"])
            except (ValueError, TypeError):
                pass

    # Also grab Jupiter's best aggregate route as a sanity baseline
    q_agg, agg_latency = get_quote(input_mint, output_mint, amount)
    if agg_latency is not None:
        latencies["Jupiter_Aggregate"] = agg_latency
    if q_agg and "outAmount" in q_agg:
        out_amount = int(q_agg["outAmount"]) / (10 ** DECIMALS[quote])
        prices["Jupiter_Aggregate"] = out_amount / quote_size_ui

    total_scan_ms = round((time.monotonic() - scan_start_monotonic) * 1000, 1)
    latency_info = {
        "per_dex_ms": latencies,
        "total_scan_ms": total_scan_ms,
        "scan_started_at": scan_started_at,
        "price_impact_pct": price_impacts,
    }

    return prices, latency_info


def scan_all_pairs():
    """
    Scan every configured pair. Returns:
    {
      "results": { "SOL/USDC": {"Raydium": 152.3, ...}, ... },
      "latency": { "SOL/USDC": {"per_dex_ms": {...}, "total_scan_ms": 812.3, ...}, ... }
    }
    """
    results = {}
    latency = {}
    for base, quote in PAIRS:
        pair_name = f"{base}/{quote}"
        prices, latency_info = scan_pair(base, quote)
        results[pair_name] = prices
        latency[pair_name] = latency_info
        time.sleep(0.5)  # be polite to the API, avoid rate limiting
    return {"results": results, "latency": latency}


if __name__ == "__main__":
    data = scan_all_pairs()
    for pair, prices in data["results"].items():
        print(f"\n{pair}: (scan took {data['latency'][pair]['total_scan_ms']}ms)")
        for dex, price in prices.items():
            print(f"  {dex}: {price:.6f}")
