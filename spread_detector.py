import asyncio
import time
from typing import List
from dataclasses import dataclass, asdict

from price_scanner import PriceScanner
from config import Config


@dataclass
class ArbitrageOpportunity:
    pair: str
    buy_dex: str
    sell_dex: str
    buy_price: float
    sell_price: float
    gross_spread_pct: float
    net_spread_pct: float
    trade_size_usd: float
    confidence: float
    timestamp: float

    def to_dict(self):
        return asdict(self)


class SpreadDetector:
    def __init__(self, price_scanner: PriceScanner):
        self.scanner = price_scanner
        self.min_profit_pct = Config.MIN_PROFIT_PCT
        self.gas_cost_usd = Config.get_gas_cost_usd()
        self.opportunities_found = 0

    async def analyze_pair(self, token_a, token_b):
        opportunities = []
        trade_size = Config.ESTIMATED_TRADE_SIZE_USD
        price_ab, price_ba = await asyncio.gather(
            self.scanner.get_pair_price(token_a, token_b, trade_size), self.scanner.get_pair_price(token_b, token_a, trade_size), return_exceptions=True
        )
        if isinstance(price_ab, Exception) or isinstance(price_ba, Exception):
            return opportunities
        if not price_ab or not price_ba:
            return opportunities
        cycle_return = price_ab.price * price_ba.price
        gross_spread_pct = (cycle_return - 1.0) * 100
        total_gas = self.gas_cost_usd * 2
        gas_pct = (total_gas / trade_size) * 100
        net_spread_pct = gross_spread_pct - gas_pct
        if net_spread_pct >= self.min_profit_pct:
            opp = ArbitrageOpportunity(
                f"{token_a}/{token_b}", "jupiter_aggregated", "jupiter_aggregated", price_ba.price, price_ab.price, round(gross_spread_pct, 4), round(net_spread_pct, 4), trade_size, min(price_ab.confidence, price_ba.confidence), time.time()
            )
            opportunities.append(opp)
            self.opportunities_found += 1
        return opportunities

    async def scan_all_pairs(self):
        all_opportunities = []
        print("\n🔍 Scanning for arbitrage opportunities...")
        print("=" * 60)
        tasks = []
        for token_a, token_b in Config.PAIRS:
            tasks.append(self.analyze_pair(token_a, token_b))
        start = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        elapsed = time.time() - start
        for result in results:
            if isinstance(result, Exception):
                continue
            all_opportunities.extend(result)
        print(f"\n📊 Scanned {len(Config.PAIRS)} pairs in {elapsed:.2f}s")
        print(f"📊 Found {len(all_opportunities)} raw opportunities")
        return all_opportunities

    def filter_opportunities(self, opportunities, min_confidence=0.5, max_spread_pct=50.0):
        filtered = []
        for opp in opportunities:
            if opp.confidence < min_confidence:
                continue
            if opp.gross_spread_pct > max_spread_pct:
                print(f"⚠️ Skipping unrealistic: {opp.pair} @ {opp.gross_spread_pct:.2f}%")
                continue
            if opp.net_spread_pct <= 0:
                continue
            filtered.append(opp)
        filtered.sort(key=lambda x: x.net_spread_pct, reverse=True)
        return filtered

    def get_stats(self):
        return {
            "opportunities_found": self.opportunities_found, "min_profit_threshold": self.min_profit_pct, "gas_cost_usd": self.gas_cost_usd, }


def format_opportunity(opp):
    return f"""
┌─────────────────────────────────────────┐
│ 🎯 ARBITRAGE OPPORTUNITY                │
├─────────────────────────────────────────┤
│ Pair:        {opp.pair:<25} │
│ Gross:       {opp.gross_spread_pct:>8.4f}%               │
│ Net:         {opp.net_spread_pct:>8.4f}%               │
│ Size:        ${opp.trade_size_usd:>8.2f}               │
│ Confidence:  {opp.confidence:>8.2%}               │
└─────────────────────────────────────────┘
"""
