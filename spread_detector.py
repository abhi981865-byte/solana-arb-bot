"""
spread_detector.py
Given per-DEX prices for a pair, find the buy-low/sell-high spread and check
if it clears a minimum profit threshold after estimated costs.
"""

# Estimated round-trip cost assumptions (tune these based on real observation):
# - Solana network fee: negligible (~$0.00025/tx) but 2 txs needed (buy + sell)
# - DEX swap fee: ~0.25% typical (varies by pool, 0.01%-1%)
# - Slippage buffer: extra safety margin since real fill may be worse than quote
SWAP_FEE_PCT = 0.25       # per swap, so 0.50% round trip
SLIPPAGE_BUFFER_PCT = 0.15  # extra safety margin
NETWORK_FEE_USD = 0.001    # ~2 txs worth of SOL gas, converted to USD estimate

MIN_PROFIT_PCT = SWAP_FEE_PCT * 2 + SLIPPAGE_BUFFER_PCT  # ~0.65% minimum spread needed


def find_opportunity(pair_name, dex_prices, trade_size_usd=100):
    """
    dex_prices: {"Raydium": 152.3, "Orca": 152.1, "Meteora": 152.5, "Jupiter_Aggregate": 152.2}
    Returns an opportunity dict if profitable after costs, else None.
    """
    # Only compare actual DEX prices, not the aggregate baseline
    real_prices = {k: v for k, v in dex_prices.items() if k != "Jupiter_Aggregate" and v}
    if len(real_prices) < 2:
        return None

    buy_dex = min(real_prices, key=real_prices.get)
    sell_dex = max(real_prices, key=real_prices.get)
    buy_price = real_prices[buy_dex]
    sell_price = real_prices[sell_dex]

    if buy_dex == sell_dex or buy_price <= 0:
        return None

    raw_spread_pct = ((sell_price - buy_price) / buy_price) * 100
    net_spread_pct = raw_spread_pct - MIN_PROFIT_PCT

    if net_spread_pct <= 0:
        return None  # not profitable after costs

    est_profit_usd = (net_spread_pct / 100) * trade_size_usd - NETWORK_FEE_USD

    return {
        "pair": pair_name,
        "buy_dex": buy_dex,
        "buy_price": buy_price,
        "sell_dex": sell_dex,
        "sell_price": sell_price,
        "raw_spread_pct": round(raw_spread_pct, 4),
        "net_spread_pct": round(net_spread_pct, 4),
        "trade_size_usd": trade_size_usd,
        "est_profit_usd": round(est_profit_usd, 4),
    }


def scan_for_opportunities(scan_results, trade_size_usd=100):
    """
    scan_results: the "results" dict from price_scanner.scan_all_pairs()
    (i.e. scan_all_pairs()["results"])
    Returns a list of profitable opportunity dicts.
    """
    opportunities = []
    for pair_name, dex_prices in scan_results.items():
        opp = find_opportunity(pair_name, dex_prices, trade_size_usd)
        if opp:
            opportunities.append(opp)
    return opportunities


# Trade sizes to test in parallel. Larger trades often eat into the available
# liquidity at a DEX, meaning the effective price gets worse the bigger you
# trade — so a "spread" that looks profitable at $50 might vanish at $500.
# Jupiter's quote already reflects some of this (quotes are size-aware), but
# testing multiple sizes side-by-side is how we notice at what size the edge
# disappears.
TEST_TRADE_SIZES_USD = [50, 100, 500]


def scan_for_opportunities_multi_size(scan_results, trade_sizes=None):
    """
    Runs opportunity detection at multiple trade sizes for every pair.
    Returns: { "SOL/USDC": {50: opp_or_None, 100: opp_or_None, 500: opp_or_None}, ... }
    Useful for seeing how spread/profitability changes with size.
    """
    trade_sizes = trade_sizes or TEST_TRADE_SIZES_USD
    results = {}
    for pair_name, dex_prices in scan_results.items():
        results[pair_name] = {}
        for size in trade_sizes:
            results[pair_name][size] = find_opportunity(pair_name, dex_prices, size)
    return results
