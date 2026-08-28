import asyncio
import json
import os
import signal
import sys
import time
import traceback
from datetime import datetime, timezone

from config import Config, validate_config
from price_scanner import PriceScanner
from spread_detector import SpreadDetector
from paper_trader import process_opportunities, get_summary, load_state


class ArbBotDaemon:
    def __init__(self):
        self.running = False
        self.scanner = None
        self.detector = None
        self.loop_count = 0
        self.start_time = time.time()
        self.last_summary_time = 0
        self.summary_interval = 300
        self.stats = {
            "loops_completed": 0, "opportunities_found": 0,
            "trades_executed": 0, "errors": 0,
            "start_time": datetime.now(timezone.utc).isoformat(),
        }
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        print(f"\n🛑 Signal {signum} received, shutting down...")
        self.running = False
        
    async def initialize(self):
        print("\n" + "=" * 60)
        print("🤖 SOLANA ARB BOT v2.0 — ULTRA MODE")
        print("=" * 60)
        if not validate_config():
            print("❌ Config validation failed.")
            sys.exit(1)
        state = load_state()
        print(f"💰 Paper Balance: ${state['balance_usd']:.2f}")
        print(f"📊 Total Trades: {state['total_trades']}")
        if state.get("circuit_breaker_tripped"):
            print("⚠️ CIRCUIT BREAKER TRIPPED!")
        self.scanner = PriceScanner()
        await self.scanner.__aenter__()
        self.detector = SpreadDetector(self.scanner)
        print("\n✅ Bot initialized!")
        print(f"⏱️ Poll: {Config.POLL_INTERVAL_SECONDS}s")
        print(f"🎯 Min Profit: {Config.MIN_PROFIT_PCT}%")
        print(f"⛽ Gas: ${Config.get_gas_cost_usd():.4f}")
        print("=" * 60 + "\n")
        
    async def run_single_loop(self):
        self.loop_count += 1
        loop_start = time.time()
        try:
            state = load_state()
            if state.get("circuit_breaker_tripped"):
                print("\n🔒 Circuit breaker active. Waiting...")
                return False
            print(f"\n🔄 Loop #{self.loop_count} | {datetime.now(timezone.utc).strftime('%H:%M:%S')}")
            prices = await self.scanner.scan_all_pairs(Config.ESTIMATED_TRADE_SIZE_USD)
            if not prices:
                print("⚠️ No prices fetched.")
                return True
            opportunities = await self.detector.scan_all_pairs()
            if not opportunities:
                print("ℹ️ No opportunities.")
                self.stats["loops_completed"] += 1
                return True
            filtered = self.detector.filter_opportunities(opportunities)
            self.stats["opportunities_found"] += len(filtered)
            if not filtered:
                print("ℹ️ Opportunities filtered out.")
                return True
            trade_opportunities = []
            for opp in filtered:
                trade_opportunities.append({
                    "pair": opp.pair, "buy_dex": opp.buy_dex, "sell_dex": opp.sell_dex,
                    "buy_price": opp.buy_price, "sell_price": opp.sell_price,
                    "net_spread_pct": opp.net_spread_pct, "trade_size_usd": opp.trade_size_usd,
                })
            print(f"\n💸 Executing {len(trade_opportunities)} paper trade(s)...")
            state, executed = process_opportunities(trade_opportunities)
            if executed:
                self.stats["trades_executed"] += len(executed)
                for trade in executed:
                    emoji = "✅" if trade["status"] == "filled" else "⚠️" if trade["status"] == "partial_fill" else "❌"
                    print(f"   {emoji} {trade['pair']}: ${trade['profit_usd']:+.4f}")
            if time.time() - self.last_summary_time > self.summary_interval:
                self._print_summary(state)
                self.last_summary_time = time.time()
            self.stats["loops_completed"] += 1
            loop_duration = time.time() - loop_start
            print(f"⏱️ Loop: {loop_duration:.2f}s")
            return True
        except Exception as e:
            self.stats["errors"] += 1
            print(f"\n❌ Error: {e}")
            traceback.print_exc()
            return True
            
    def _print_summary(self, state):
        summary = get_summary(state)
        uptime = time.time() - self.start_time
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"⏱️ Uptime: {uptime/60:.1f}m")
        print(f"💰 Balance: ${summary['balance_usd']:.4f}")
        print(f"📈 ROI: {summary['roi_pct']:+.3f}%")
        print(f"📊 Trades: {summary['total_trades']} | ❌ Failed: {summary['failed_trades']}")
        print(f"📉 Fill Rate: {summary['fill_success_rate_pct']}%")
        print(f"🔒 Breaker: {'TRIPPED' if summary['circuit_breaker_tripped'] else 'OK'}")
        print(f"🔄 Loops: {self.stats['loops_completed']} | 🎯 Opps: {self.stats['opportunities_found']}")
        print("=" * 60)
        
    async def run(self):
        await self.initialize()
        self.running = True
        print("\n🚀 Bot running! Press Ctrl+C to stop.\n")
        while self.running:
            success = await self.run_single_loop()
            if not success:
                for _ in range(60):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
            else:
                for _ in range(int(Config.POLL_INTERVAL_SECONDS)):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
        await self not self.running:
                        break
                    await asyncio.sleep(1)
            else:
                for _ in range(int(Config.POLL_INTERVAL_SECONDS)):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
        await self.shutdown()
        
    async def shutdown(self):
        print("\n🛑 Shutting down...")
        if self.scanner:
            await self.scanner.__aexit__(None, None, None)
        state = load_state()
        self._print_summary(state)
        stats_path = os.path.join(Config.DATA_DIR, "bot_stats.json")
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        with open(stats_path, "w") as f:
            json.dump(self.stats, f, indent=2)
        print("\n✅ Bot stopped. Stats saved.")
        print("=" * 60)


def main():
    daemon = ArbBotDaemon()
    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"\n💥 Fatal: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
