"""
spread_detector.py

Given per-DEX prices (and liquidity) for a pair, find the buy-low/sell-high
spread and check if it clears a minimum profit threshold after estimated
costs, plus additional filters aimed at cutting failed/partial fills:
- An EXTRA safety margin on top of fee/slippage costs, so we only act on
  spreads with real room to spare (marginal ones get skipped, not just
  fee-adjusted)
- Both the buy-side and sell-side pool must have enough liquidity relative
  to the trade size, so the pool can actually absorb the trade near the
  quoted price
- Price data must be fresh (not from a stale/delayed scan) — and if it
  ever IS stale, that's logged so it's visible in Actions logs, not a
  silent skip

Also supports DYNAMIC trade sizing: scan_for_dynamic_opportunities() picks
the largest trade size (from a candidate list) that still clears every
filter for each pair — a strong, well-liquidated spread gets sized up; a
marginal one stays small or gets skipped entirely.
"""

from datetime import datetime, timezone

# Estimated round-trip cost assumptions (tune based on real observation):
SWAP_FEE_PCT = 0.25  # per swap, so 0.50% round trip
SLIPPAGE_BUFFER_PCT = 0.15  # baseline safety margin for cost estimation
NETWORK_FEE_USD = 0.001  # ~2 txs worth of SOL gas, converted to USD estimate

# Extra margin ON TOP of the cost buffer above — the "skip marginal
# spreads" filter. Raising this = fewer but safer trades; lower it if too
# few opportunities are being found.
EXTRA_SAFETY_MARGIN_PCT = 0.35

MIN_PROFIT_PCT = SWAP_FEE_PCT * 2 + SLIPPAGE_BUFFER_PCT + EXTRA_SAFETY_MARGIN_PCT
# ~1.00% minimum net spread needed (up from ~0.65%) — filters out the
# thin, noisy spreads that were driving most failed/partial fills.

# A pool's liquidity must be at least this many times the trade size for
# us to trust its price won't move much once we trade against it.
# 20x means a $100 trade needs a $2,000+ liquidity pool.
MIN_LIQUIDITY_MULTIPLE = 20

# Reject a scan's prices if they're older than this (seconds) by the time
# we evaluate them. In a normal run this check never fires (scan-to-check
# gap is 1-2s); it's a safety net for slow/retried scans.
MAX_PRICE_AGE_SECONDS = 45


def _is_fresh(scanned_at_iso):
    if not scanned_at_iso:
        return True
    try:
        scanned_at = datetime.fromisoformat(scanned_at_iso)
    except ValueError:
        return True
    age_seconds = (datetime.now(timezone.utc) - scanned_at).total_seconds()
    is_fresh = age_seconds <= MAX_PRICE_AGE_SECONDS
    if not is_fresh:
        print(f"[spread_detector] Skipping stale price data ({age_seconds:.1f}s old, limit {MAX_PRICE_AGE_SECONDS}s)")
    return is_fresh


def find_opportunity(pair_name, dex_prices, trade_size_usd=100, dex_liquidity=None, scanned_at=None):
    """
    dex_prices: {"Raydium": 152.3, "Meteora": 152.5, ...}
    dex_liquidity: {"Raydium": 45000, ...} USD liquidity per pool (optional)
    scanned_at: ISO timestamp of when these prices were fetched (optional)

    Returns an opportunity dict if profitable after costs AND passes the
    liquidity/freshness filters, else None.
    """
    if scanned_at is not None and not _is_fresh(scanned_at):
        return None

    real_prices = {k: v for k, v in dex_prices.items() if v}
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
        return None

    if dex_liquidity:
        min_required_liquidity = trade_size_usd * MIN_LIQUIDITY_MULTIPLE
        buy_liq = dex_liquidity.get(buy_dex)
        sell_liq = dex_liquidity.get(sell_dex)
        if buy_liq is not None and buy_liq < min_required_liquidity:
            return None
        if sell_liq is not None and sell_liq < min_required_liquidity:
            return None

    est_profit_usd = (net_spread_pct / 100) * trade_size_usd - NETWORK_FEE_USD

    # How big this trade is relative to the smaller of the two pools —
    # a rough slippage-risk proxy used by real_trader.py's extra safety check.
    liquidity_ratio_pct = None
    if dex_liquidity:
        pool_sizes = [dex_liquidity.get(buy_dex), dex_liquidity.get(sell_dex)]
        pool_sizes = [p for p in pool_sizes if p]
        if pool_sizes:
            liquidity_ratio_pct = round((trade_size_usd / min(pool_sizes)) * 100, 3)

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
        "liquidity_ratio_pct": liquidity_ratio_pct,
    }


def scan_for_opportunities(scan_results, trade_size_usd=100, liquidity_info=None):
    """
    Fixed-size scan: tests every pair at a single trade_size_usd.
    Returns a list of profitable opportunity dicts.
    """
    opportunities = []
    liquidity_info = liquidity_info or {}
    for pair_name, dex_prices in scan_results.items():
        pair_info = liquidity_info.get(pair_name, {})
        opp = find_opportunity(
            pair_name, dex_prices, trade_size_usd,
            dex_liquidity=pair_info.get("per_pool_liquidity_usd"),
            scanned_at=pair_info.get("scanned_at"),
        )
        if opp:
            opportunities.append(opp)
    return opportunities


TEST_TRADE_SIZES_USD = [50, 100, 500]


def scan_for_opportunities_multi_size(scan_results, trade_sizes=None, liquidity_info=None):
    """
    Diagnostic helper: runs opportunity detection at multiple trade sizes
    for every pair, returning the full breakdown. Not used in the main
    trading path — see scan_for_dynamic_opportunities() for that.
    """
    trade_sizes = trade_sizes or TEST_TRADE_SIZES_USD
    liquidity_info = liquidity_info or {}
    results = {}
    for pair_name, dex_prices in scan_results.items():
        pair_info = liquidity_info.get(pair_name, {})
        results[pair_name] = {}
        for size in trade_sizes:
            results[pair_name][size] = find_opportunity(
                pair_name, dex_prices, size,
                dex_liquidity=pair_info.get("per_pool_liquidity_usd"),
                scanned_at=pair_info.get("scanned_at"),
            )
    return results


# Sizes to test for dynamic sizing — the LARGEST one that still clears all
# filters is used for that pair's trade.
DYNAMIC_TRADE_SIZES_USD = [50, 100, 250, 500]


def scan_for_dynamic_opportunities(scan_results, trade_sizes=None, liquidity_info=None):
    """
    For each pair, tests multiple trade sizes (largest first) and picks the
    biggest one that still clears the profit + liquidity filters. Returns a
    list of opportunity dicts — one per pair with any viable size, so
    multiple simultaneously-profitable pairs are all included. This is the
    main trading path used by main.py.
    """
    trade_sizes = sorted(trade_sizes or DYNAMIC_TRADE_SIZES_USD, reverse=True)
    liquidity_info = liquidity_info or {}
    opportunities = []
    for pair_name, dex_prices in scan_results.items():
        pair_info = liquidity_info.get(pair_name, {})
        dex_liquidity = pair_info.get("per_pool_liquidity_usd")
        scanned_at = pair_info.get("scanned_at")
        for size in trade_sizes:
            opp = find_opportunity(pair_name, dex_prices, size, dex_liquidity, scanned_at)
            if opp:
                opportunities.append(opp)
                break
    return opportunities