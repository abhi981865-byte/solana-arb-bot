#!/usr/bin/env python3
"""
Solana DEX Arbitrage Bot - Configuration Module
COMPLETE VERSION with all missing parameters
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central Configuration Class for Solana DEX Arbitrage Bot"""

    # ============================================================================
    # 1. RUNTIME & ENGINE SETTINGS
    # ============================================================================
    CHECK_INTERVAL: float = float(os.getenv("CHECK_INTERVAL", "2.0"))
    MAX_TRADES_PER_CYCLE: int = int(os.getenv("MAX_TRADES_PER_CYCLE", "3"))
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "True").lower() in ("true", "1", "yes")

    # ============================================================================
    # 2. FINANCIAL & TRADING PARAMETERS
    # ============================================================================
    STARTING_BALANCE: float = float(os.getenv("STARTING_BALANCE_USD", "1000.0"))
    MIN_PROFIT_PERCENT: float = float(os.getenv("MIN_PROFIT_PERCENT", "0.5"))
    TRADE_SIZE_USD: float = float(os.getenv("ESTIMATED_TRADE_SIZE_USD", "100.0"))
    MAX_TRADE_PCT_OF_BALANCE: float = 0.10

    # ============================================================================
    # 3. PRICE SCANNER PARAMETERS (NEW - WAS MISSING!)
    # ============================================================================
    PRICE_CACHE_TTL_SECONDS: float = float(os.getenv("PRICE_CACHE_TTL_SECONDS", "60.0"))
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))
    MAX_CONNECTIONS: int = int(os.getenv("MAX_CONNECTIONS", "50"))

    # ============================================================================
    # 4. TOKEN CONFIGURATION
    # ============================================================================
    TOKEN_MINTS: Dict[str, str] = {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoPcTEG6nUeBMevmHVB",
        "JUP": "JUPyiwrYJFskUPiHa7hkeR8VnkzcBWzTrEUQPs5wStV",
        "WIF": "EKpQGSJtjUID1Lq4Q2X3yUbe1qyA9vEqEu6gNS56KEPE",
        "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    }

    TOKEN_DECIMALS: Dict[str, int] = {
        "SOL": 9, "USDC": 6, "USDT": 6, "JUP": 6, "WIF": 6, "RAY": 6, "BONK": 5
    }

    # ============================================================================
    # 5. TRADING PAIRS (NEW - WAS MISSING!)
    # ============================================================================
    PAIRS: List[Tuple[str, str]] = [
        ("SOL", "USDC"), ("SOL", "USDT"), ("USDC", "USDT"),
        ("JUP", "USDC"), ("JUP", "SOL"), ("WIF", "USDC"),
        ("WIF", "SOL"), ("RAY", "USDC"), ("BONK", "SOL")
    ]

    # ============================================================================
    # 6. DEX CONFIGURATION
    # ============================================================================
    DEX_PROGRAMS: Dict[str, str] = {
        "Raydium": "675kPX9MHTjS2zt1qfr1NYpt8j3EamBgK2iJSeBFgpzP",
        "Orca": "9W959DqEETiGZJCQ2d3V1sUaVJiXfEAsA9gKXZPineBJ",
        "Meteora": "LBUZKhRxPF3XUpBCepzV7CFWeWmYbgZcRzxSK6KAZF7"
    }

    # ============================================================================
    # 7. GAS & COST ESTIMATION
    # ============================================================================
    GAS_LAMPORTS: int = 5000
    SOL_PRICE_USD: float = float(os.getenv("SOL_PRICE_USD", "180.0"))

    @staticmethod
    def get_gas_cost_usd() -> float:
        """Calculate gas cost in USD (WAS MISSING METHOD!)"""
        gas_sol = Config.GAS_LAMPORTS / (10 ** 9)
        return gas_sol * Config.SOL_PRICE_USD

    # ============================================================================
    # 8. PAPER TRADING SIMULATION PARAMETERS
    # ============================================================================
    FILL_FAILURE_RATE: float = float(os.getenv("FILL_FAILURE_RATE", "0.35"))
    PARTIAL_FILL_RATE: float = float(os.getenv("PARTIAL_FILL_RATE", "0.15"))
    PARTIAL_FILL_PENALTY_PCT: float = float(os.getenv("PARTIAL_FILL_PENALTY_PCT", "0.20"))
    CIRCUIT_BREAKER_CONSECUTIVE_LOSSES: int = int(os.getenv("CIRCUIT_BREAKER_LOSSES", "3"))

    # ============================================================================
    # 9. DATA PATHS (NEW - WAS MISSING!)
    # ============================================================================
    DATA_DIR: str = "data"
    STATE_FILE: str = os.path.join(DATA_DIR, "state.json")
    DB_PATH: str = os.path.join(DATA_DIR, "arb_bot.db")

    # ============================================================================
    # 10. NETWORK & RPC ENDPOINTS
    # ============================================================================
    RPC_PRIMARY: str = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    RPC_SECONDARY: str = os.getenv("QUICKNODE_RPC_URL", "https://api.mainnet-beta.solana.com")
    SOLANA_RPC_URL: str = RPC_PRIMARY if RPC_PRIMARY else RPC_SECONDARY

    # ============================================================================
    # 11. NOTIFICATIONS
    # ============================================================================
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # ============================================================================
    # 12. BACKWARD COMPATIBILITY ALIASES
    # ============================================================================
    POLL_INTERVAL_SECONDS = CHECK_INTERVAL
    MIN_PROFIT_PCT = MIN_PROFIT_PERCENT
    STARTING_BALANCE_USD = STARTING_BALANCE
    ESTIMATED_TRADE_SIZE_USD = TRADE_SIZE_USD
    MAX_TRADE_PCT = MAX_TRADE_PCT_OF_BALANCE

    @classmethod
    def validate_config(cls) -> bool:
        """Validate crucial parameters on startup"""
        errors = []

        if not cls.SOLANA_RPC_URL:
            errors.append("❌ SOLANA_RPC_URL missing")
        if cls.MIN_PROFIT_PERCENT <= 0:
            errors.append(f"❌ MIN_PROFIT_PERCENT must be > 0")
        if cls.TRADE_SIZE_USD <= 0:
            errors.append(f"❌ TRADE_SIZE_USD must be > 0")
        if cls.STARTING_BALANCE <= 0:
            errors.append(f"❌ STARTING_BALANCE must be > 0")
        if not cls.PAIRS:
            errors.append("❌ PAIRS list cannot be empty")
        if not cls.TOKEN_DECIMALS:
            errors.append("❌ TOKEN_DECIMALS dict cannot be empty")

        if errors:
            print("\n⚠️  CONFIG VALIDATION ERRORS:")
            for err in errors:
                print(f"   {err}")
            return False

        print("\n✅ CONFIG VALIDATION PASSED")
        return True

    @classmethod
    def print_summary(cls) -> None:
        """Print config summary"""
        print("\n" + "="*70)
        print("📊 BOT CONFIGURATION SUMMARY")
        print("="*70)
        print(f"RPC URL:              {cls.SOLANA_RPC_URL[:50]}...")
        print(f"Starting Balance:     ${cls.STARTING_BALANCE}")
        print(f"Min Profit Threshold: {cls.MIN_PROFIT_PERCENT}%")
        print(f"Trade Size:           ${cls.TRADE_SIZE_USD}")
        print(f"Trading Pairs:        {len(cls.PAIRS)} pairs")
        print(f"Token Decimals:       {len(cls.TOKEN_DECIMALS)} tokens")
        print(f"Gas Cost (USD):       ${cls.get_gas_cost_usd():.6f}")
        print(f"Paper Trading:        YES ✅")
        print(f"Circuit Breaker:      After {cls.CIRCUIT_BREAKER_CONSECUTIVE_LOSSES} losses")
        print("="*70 + "\n")


def validate_config() -> bool:
    """Module-level wrapper function"""
    return Config.validate_config()
