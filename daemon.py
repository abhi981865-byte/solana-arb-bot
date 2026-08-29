#!/usr/bin/env python3
"""
Solana DEX Arbitrage Bot - Main Daemon
Advanced arbitrage bot with real-time monitoring, error handling, and comprehensive logging
"""

import time
import json
import logging
import asyncio
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
import signal

# Local imports
from config import Config, validate_config

# ============================================================================
# LOGGING SETUP - Professional Grade
# ============================================================================

def setup_logging(log_level=logging.INFO):
    """Setup comprehensive logging"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create logger
    logger = logging.getLogger("SolanaBot")
    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)

    # File handler
    file_handler = logging.FileHandler(
        log_dir / f"bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

# ============================================================================
# DATA MODELS - Type Safety
# ============================================================================

@dataclass
class Price:
    """Price data for a trading pair"""
    token_pair: str
    dex: str
    price: float
    timestamp: float
    confidence: float = 0.95

    def to_dict(self):
        return asdict(self)


@dataclass
class TradeOpportunity:
    """Detected arbitrage opportunity"""
    buy_dex: str
    sell_dex: str
    token_pair: str
    buy_price: float
    sell_price: float
    spread_percent: float
    profit_amount: float
    timestamp: float
    status: str = "pending"

    def to_dict(self):
        return asdict(self)


@dataclass
class TradeResult:
    """Result of executed trade"""
    opportunity_id: str
    status: str  # "success", "partial", "failed"
    buy_amount: float
    sell_amount: float
    profit: float
    fees: float
    timestamp: float
    error: Optional[str] = None

    def to_dict(self):
        return asdict(self)


# ============================================================================
# STATE MANAGER - Persistent Storage
# ============================================================================

class StateManager:
    """Manages bot state persistence"""

    def __init__(self, state_file: str = "data/state.json"):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        """Load state from file"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")
                return self._default_state()
        return self._default_state()

    def _default_state(self) -> Dict:
        """Get default state"""
        return {
            "balance_usd": Config.STARTING_BALANCE, "total_trades": 0, "successful_trades": 0, "failed_trades": 0, "total_profit": 0.0, "circuit_breaker_losses": 0, "last_trade_time": None, "opportunities_found": 0, "last_update": datetime.now().isoformat()
        }

    def save(self):
        """Save state to file"""
        try:
            self.state["last_update"] = datetime.now().isoformat()
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            logger.debug("State saved successfully")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def update(self, key: str, value):
        """Update state value"""
        self.state[key] = value
        self.save()

    def get(self, key: str, default=None):
        """Get state value"""
        return self.state.get(key, default)


# ============================================================================
# PRICE SCANNER - Real-time Price Monitoring
# ============================================================================

class PriceScanner:
    """Scans DEX prices in real-time"""

    def __init__(self, config: Config):
        self.config = config
        self.prices: Dict[str, List[Price]] = {}
        self.last_scan_time = None
        logger.info("✅ Price Scanner initialized")

    async def scan_prices(self) -> Dict[str, List[Price]]:
        """Scan all DEX prices"""
        logger.info("🔍 Scanning DEX prices...")

        try:
            # Simulate price scanning from different DEXs
            self.prices = await self._fetch_prices()
            self.last_scan_time = time.time()
            logger.info(f"✅ Scanned {len(self.prices)} token pairs")
            return self.prices
        except Exception as e:
            logger.error(f"❌ Price scan failed: {e}")
            return {}

    async def _fetch_prices(self) -> Dict[str, List[Price]]:
        """Fetch prices from DEXs (placeholder)"""
        prices = {}

        # Simulated price data
        for pair in Config.TOKEN_PAIRS:
            prices[pair] = [
                Price(
                    token_pair=pair, dex="Raydium", price=100.0 + (hash(pair) % 50), timestamp=time.time()
                ), Price(
                    token_pair=pair, dex="Orca", price=100.0 + (hash(pair) % 50) + (hash(pair) % 5), timestamp=time.time()
                ), Price(
                    token_pair=pair, dex="Meteora", price=100.0 + (hash(pair) % 50) - (hash(pair) % 3), timestamp=time.time()
                )
            ]

        # Add realistic delay
        await asyncio.sleep(0.5)
        return prices

    def get_latest_prices(self, pair: str) -> List[Price]:
        """Get latest prices for a pair"""
        return self.prices.get(pair, [])


# ============================================================================
# SPREAD DETECTOR - Arbitrage Opportunity Detection
# ============================================================================

class SpreadDetector:
    """Detects arbitrage opportunities"""

    def __init__(self, config: Config):
        self.config = config
        self.opportunities: List[TradeOpportunity] = []
        logger.info("✅ Spread Detector initialized")

    def detect_spreads(self, prices: Dict[str, List[Price]]) -> List[TradeOpportunity]:
        """Detect profitable spreads"""
        logger.info("🔍 Detecting arbitrage opportunities...")

        opportunities = []

        for pair, price_list in prices.items():
            if len(price_list) < 2:
                continue

            # Sort by price
            sorted_prices = sorted(price_list, key=lambda p: p.price)

            for i, buy_price_obj in enumerate(sorted_prices):
                for sell_price_obj in sorted_prices[i+1:]:
                    spread_percent = (
                        (sell_price_obj.price - buy_price_obj.price) /
                        buy_price_obj.price * 100
                    )

                    # Check if spread meets minimum profit threshold
                    if spread_percent >= self.config.MIN_PROFIT_PERCENT:
                        profit = spread_percent * self.config.TRADE_SIZE_USD / 100

                        opp = TradeOpportunity(
                            buy_dex=buy_price_obj.dex, sell_dex=sell_price_obj.dex, token_pair=pair, buy_price=buy_price_obj.price, sell_price=sell_price_obj.price, spread_percent=spread_percent, profit_amount=profit, timestamp=time.time()
                        )

                        opportunities.append(opp)
                        logger.info(
                            f"💡 Opportunity found: {pair} | "
                            f"{buy_price_obj.dex}→{sell_price_obj.dex} | "
                            f"Spread: {spread_percent:.2f}% | "
                            f"Profit: ${profit:.2f}"
                        )

        self.opportunities = opportunities
        return opportunities


# ============================================================================
# EXECUTION ENGINE - Trade Execution
# ============================================================================

class ExecutionEngine:
    """Executes trades"""

    def __init__(self, config: Config, state: StateManager):
        self.config = config
        self.state = state
        self.executed_trades: List[TradeResult] = []
        logger.info("✅ Execution Engine initialized")

    async def execute_opportunity(self, opportunity: TradeOpportunity) -> TradeResult:
        """Execute a single opportunity"""
        logger.info(
            f"⚡ Executing trade: {opportunity.token_pair} "
            f"{opportunity.buy_dex}→{opportunity.sell_dex}"
        )

        try:
            # Simulate trade execution
            if self.config.PAPER_TRADING:
                result = await self._simulate_trade(opportunity)
            else:
                result = await self._execute_live_trade(opportunity)

            # Update state
            self._update_state(result)
            self.executed_trades.append(result)

            return result

        except Exception as e:
            logger.error(f"❌ Trade execution failed: {e}")
            return TradeResult(
                opportunity_id=str(opportunity.timestamp), status="failed", buy_amount=0, sell_amount=0, profit=0, fees=0, timestamp=time.time(), error=str(e)
            )

    async def _simulate_trade(self, opp: TradeOpportunity) -> TradeResult:
        """Simulate paper trade"""
        logger.info("📄 Running paper trade simulation...")

        # Realistic simulation with fees and slippage
        buy_amount = self.config.TRADE_SIZE_USD / opp.buy_price
        sell_amount = buy_amount * opp.sell_price
        fees = sell_amount * 0.002  # 0.2% fees
        profit = sell_amount - self.config.TRADE_SIZE_USD - fees

        await asyncio.sleep(0.1)  # Simulate execution delay

        return TradeResult(
            opportunity_id=str(opp.timestamp), status="success" if profit > 0 else "partial", buy_amount=buy_amount, sell_amount=sell_amount, profit=profit, fees=fees, timestamp=time.time()
        )

    async def _execute_live_trade(self, opp: TradeOpportunity) -> TradeResult:
        """Execute live trade (placeholder)"""
        logger.warning("⚠️ Live trading not implemented yet")
        return await self._simulate_trade(opp)

    def _update_state(self, result: TradeResult):
        """Update bot state with trade result"""
        self.state.update("total_trades", self.state.get("total_trades", 0) + 1)

        if result.status == "success":
            self.state.update("successful_trades", self.state.get("successful_trades", 0) + 1)
            profit = self.state.get("total_profit", 0) + result.profit
            self.state.update("total_profit", profit)

            logger.info(f"✅ Trade successful! Profit: ${result.profit:.2f}")
        else:
            self.state.update("failed_trades", self.state.get("failed_trades", 0) + 1)
            logger.warning(f"⚠️ Trade failed or partial")


# ============================================================================
# CIRCUIT BREAKER - Risk Management
# ============================================================================

class CircuitBreaker:
    """Prevents death spiral after consecutive losses"""

    def __init__(self, max_losses: int = 3):
        self.max_losses = max_losses
        self.consecutive_losses = 0
        self.is_active = False
        logger.info(f"✅ Circuit Breaker initialized (max losses: {max_losses})")

    def record_loss(self):
        """Record a losing trade"""
        self.consecutive_losses += 1

        if self.consecutive_losses >= self.max_losses:
            self.is_active = True
            logger.critical(
                f"🛑 CIRCUIT BREAKER ACTIVATED! "
                f"{self.consecutive_losses} consecutive losses"
            )

    def record_win(self):
        """Record a winning trade"""
        self.consecutive_losses = 0
        self.is_active = False
        logger.info("✅ Circuit breaker reset")

    def should_trade(self) -> bool:
        """Check if trading should continue"""
        return not self.is_active


# ============================================================================
# MAIN BOT CLASS - Orchestrator
# ============================================================================

class SolanaBotDaemon:
    """Main arbitrage bot daemon"""

    def __init__(self):
        logger.info("="*60)
        logger.info("🤖 Solana Arbitrage Bot Starting...")
        logger.info("="*60)

        # Initialize components
        self.config = Config()
        self.state = StateManager()
        self.scanner = PriceScanner(self.config)
        self.detector = SpreadDetector(self.config)
        self.executor = ExecutionEngine(self.config, self.state)
        self.breaker = CircuitBreaker()

        self.running = True
        self.stats = {
            "total_cycles": 0, "start_time": time.time(), "total_profit": 0.0
        }

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("✅ Bot initialized successfully")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("⛔ Received shutdown signal...")
        self.running = False
        self.shutdown()

    async def run_cycle(self):
        """Run one bot cycle"""
        self.stats["total_cycles"] += 1
        cycle_num = self.stats["total_cycles"]

        logger.info(f"\n{'='*60}")
        logger.info(f"📍 CYCLE {cycle_num} - {datetime.now().strftime('%H:%M:%S')}")
        logger.info(f"{'='*60}")

        try:
            # Step 1: Scan prices
            prices = await self.scanner.scan_prices()
            if not prices:
                logger.warning("⚠️ No prices available")
                return

            # Step 2: Detect opportunities
            opportunities = self.detector.detect_spreads(prices)
            self.state.update("opportunities_found", self.state.get("opportunities_found", 0) + len(opportunities))

            if not opportunities:
                logger.info("ℹ️ No opportunities found in this cycle")
                return

            logger.info(f"🎯 Found {len(opportunities)} opportunity(ies)")

            # Step 3: Execute trades (circuit breaker check)
            if not self.breaker.should_trade():
                logger.critical("🛑 Circuit breaker active - trading disabled")
                return

            for opp in opportunities[:self.config.MAX_TRADES_PER_CYCLE]:
                result = await self.executor.execute_opportunity(opp)

                # Update circuit breaker
                if result.profit > 0:
                    self.breaker.record_win()
                else:
                    self.breaker.record_loss()

            # Log cycle summary
            self._log_cycle_summary()

        except Exception as e:
            logger.error(f"❌ Cycle error: {e}", exc_info=True)

    def _log_cycle_summary(self):
        """Log performance summary"""
        uptime = time.time() - self.stats["start_time"]
        balance = self.state.get("balance_usd")
        profit = self.state.get("total_profit", 0)
        success_rate = self._calculate_success_rate()

        logger.info(f"\n📊 CYCLE SUMMARY:")
        logger.info(f"   Total Cycles: {self.stats['total_cycles']}")
        logger.info(f"   Uptime: {timedelta(seconds=int(uptime))}")
        logger.info(f"   Balance: ${balance:.2f}")
        logger.info(f"   Total Profit: ${profit:.2f}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   Status: {'🟢 ACTIVE' if self.running else '🔴 STOPPED'}")

    def _calculate_success_rate(self) -> float:
        """Calculate win rate"""
        total = self.state.get("successful_trades", 0) + self.state.get("failed_trades", 0)
        if total == 0:
            return 0.0
        return (self.state.get("successful_trades", 0) / total) * 100

    async def run(self):
        """Main daemon loop"""
        logger.info("🚀 Bot running... Press Ctrl+C to stop\n")

        while self.running:
            try:
                await self.run_cycle()

                # Sleep before next cycle
                logger.info(f"⏱️ Sleeping for {self.config.CHECK_INTERVAL}s...")
                await asyncio.sleep(self.config.CHECK_INTERVAL)

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait before retry

        self.shutdown()

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("\n" + "="*60)
        logger.info("🛑 Bot Shutting Down...")
        logger.info("="*60)

        # Save final state
        self.state.save()

        # Log final stats
        total_profit = self.state.get("total_profit", 0)
        success_rate = self._calculate_success_rate()
        uptime = time.time() - self.stats["start_time"]

        logger.info(f"📊 FINAL STATISTICS:")
        logger.info(f"   Total Cycles: {self.stats['total_cycles']}")
        logger.info(f"   Total Uptime: {timedelta(seconds=int(uptime))}")
        logger.info(f"   Total Trades: {self.state.get('total_trades', 0)}")
        logger.info(f"   Successful: {self.state.get('successful_trades', 0)}")
        logger.info(f"   Failed: {self.state.get('failed_trades', 0)}")
        logger.info(f"   Success Rate: {success_rate:.1f}%")
        logger.info(f"   Total Profit: ${total_profit:.2f}")
        logger.info(f"   ROI: {(total_profit/self.config.STARTING_BALANCE)*100:.2f}%")

        logger.info("✅ Bot shutdown complete")
        logger.info("="*60)

        self.running = False


# ============================================================================
# ENTRY POINT
# ============================================================================

async def main():
    """Main entry point"""
    try:
        validate_config()
        bot = SolanaBotDaemon()
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

