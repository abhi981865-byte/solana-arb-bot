#!/usr/bin/env python3
"""
Solana ARB Bot Daemon v2.2 - With Enhanced Telegram Alerts
"""

import time
import logging
import sys
from datetime import datetime, timedelta

from config import Config, validate_config
from paper_trader import load_state, save_state, process_opportunities, get_summary
from telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("SolanaArbBot")


class SolanaBotDaemon:
    """Main arbitrage bot with enhanced Telegram alerts"""

    def __init__(self):
        logger.info("="*70)
        logger.info("🤖 Solana ARB Bot v2.2 Starting...")
        logger.info("="*70)

        if not validate_config():
            logger.error("❌ Config validation failed!")
            sys.exit(1)

        self.config = Config
        self.state = load_state()
        self.running = True
        self.stats = {
            "total_cycles": 0,
            "start_time": time.time(),
            "opportunities_found": 0,
            "trades_executed": 0,
        }
        
        # Initialize Telegram
        self.notifier = TelegramNotifier(
            self.config.TELEGRAM_BOT_TOKEN,
            self.config.TELEGRAM_CHAT_ID
        )
        
        # Startup alert
        if self.notifier.enabled:
            self.notifier.alert_startup(self.state['balance_usd'])

        logger.info("✅ Bot initialized")
        Config.print_summary()

    def run_cycle(self):
        """Run one complete bot cycle"""
        self.stats["total_cycles"] += 1
        cycle_num = self.stats["total_cycles"]

        logger.info(f"\n{'='*70}")
        logger.info(f"📍 CYCLE {cycle_num} - {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*70}")

        try:
            logger.info("🔍 Scanning opportunities...")
            
            # Simulated opportunities
            opportunities = [
                {
                    "pair": "SOL/USDC",
                    "buy_dex": "Raydium",
                    "sell_dex": "Orca",
                    "buy_price": 180.50,
                    "sell_price": 181.00,
                    "trade_size_usd": 100.0,
                    "net_spread_pct": 0.28
                }
            ]

            self.stats["opportunities_found"] += len(opportunities)

            if opportunities:
                logger.info(f"🎯 Found {len(opportunities)} opportunity(ies)!")
                
                # Filter by min profit
                filtered = [opp for opp in opportunities if opp["net_spread_pct"] >= self.config.MIN_PROFIT_PERCENT]
                
                if filtered:
                    logger.info(f"⚡ Executing {len(filtered)} trades...")
                    self.state, executed = process_opportunities(filtered)
                    self.stats["trades_executed"] += len(executed)

                    for trade in executed:
                        logger.info(f"   Trade: {trade['pair']} → ${trade['profit_usd']:+.4f}")
                        
                        # Send trade alert
                        if self.notifier.enabled:
                            self.notifier.alert_trade_executed(
                                pair=trade['pair'],
                                profit=trade['profit_usd'],
                                status=trade['status'],
                                spread=trade['net_spread_pct']
                            )

            self._log_cycle_summary()
            save_state(self.state)

        except Exception as e:
            logger.error(f"❌ Cycle error: {e}", exc_info=True)

    def _log_cycle_summary(self):
        """Log performance after each cycle"""
        summary = get_summary(self.state)
        logger.info(f"\n📊 CYCLE SUMMARY:")
        logger.info(f"   Balance:      ${summary['balance_usd']:.2f}")
        logger.info(f"   ROI:          {summary['roi_pct']:+.3f}%")
        logger.info(f"   Success Rate: {summary['fill_success_rate_pct']:.1f}%")

    def run(self):
        """Main bot loop"""
        logger.info(f"\n🚀 Bot running...")
        logger.info("Press Ctrl+C to stop\n")

        while self.running:
            try:
                self.run_cycle()
                logger.info(f"⏱️  Sleeping for {self.config.CHECK_INTERVAL}s...")
                time.sleep(self.config.CHECK_INTERVAL)
            except KeyboardInterrupt:
                logger.info("\n⛔ Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(5)

        self.shutdown()

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("\n" + "="*70)
        logger.info("🛑 Bot Shutting Down...")
        logger.info("="*70)

        summary = get_summary(self.state)
        uptime = time.time() - self.stats["start_time"]
        uptime_str = str(timedelta(seconds=int(uptime)))

        logger.info(f"\n📊 FINAL STATISTICS:")
        logger.info(f"   Total Cycles:   {self.stats['total_cycles']}")
        logger.info(f"   Uptime:         {uptime_str}")
        logger.info(f"   Final Balance:  ${summary['balance_usd']:.2f}")
        logger.info(f"   ROI:            {summary['roi_pct']:+.3f}%")

        # Send shutdown alert
        if self.notifier.enabled:
            self.notifier.alert_shutdown(summary, uptime_str)

        save_state(self.state)
        logger.info("\n✅ Bot shutdown complete")
        self.running = False


if __name__ == "__main__":
    try:
        bot = SolanaBotDaemon()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
