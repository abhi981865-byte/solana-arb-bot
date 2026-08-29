#!/usr/bin/env python3
"""
Solana DEX Arbitrage Bot - Configuration Module
Fully synchronized with daemon.py parameters
"""

import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

# Environment variables load karein
load_dotenv()

class Config:
    """Central Configuration Class for Solana DEX Arbitrage Bot"""

    # ============================================================================
    # 1. RUNTIME & ENGINE SETTINGS (Required by daemon.py)
    # ============================================================================
    CHECK_INTERVAL: float = float(os.getenv("CHECK_INTERVAL", "2.0"))           # Seconds between cycles
    MAX_TRADES_PER_CYCLE: int = int(os.getenv("MAX_TRADES_PER_CYCLE", "3"))     # Max trades per cycle execution
    PAPER_TRADING: bool = os.getenv("PAPER_TRADING", "True").lower() in ("true", "1", "yes")

    # ============================================================================
    # 2. FINANCIAL & TRADING PARAMETERS (Required by daemon.py)
    # ============================================================================
    STARTING_BALANCE: float = float(os.getenv("STARTING_BALANCE", "1000.0"))   # Starting balance in USD
    MIN_PROFIT_PERCENT: float = float(os.getenv("MIN_PROFIT_PERCENT", "0.5"))   # Minimum profit % trigger
    TRADE_SIZE_USD: float = float(os.getenv("TRADE_SIZE_USD", "50.0"))         # Position size per trade

    # ============================================================================
    # 3. TOKEN PAIRS & DEX CONFIGURATION (Required by daemon.py)
    # ============================================================================
    TOKEN_PAIRS: List[str] = [
        "SOL/USDC", "SOL/USDT", "USDC/USDT", "JUP/USDC", "JUP/SOL", "WIF/SOL", "WIF/USDC", "RAY/USDC", "BONK/SOL"
    ]

    # Token Mint Addresses (Solana Mainnet)
    TOKEN_MINTS: Dict[str, str] = {
        "SOL": "So11111111111111111111111111111111111111112", "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoPcTEG6nUeBMevmHVB", "JUP": "JUPyiwrYJFskUPiHa7hkeR8VnkzcBWzTrEUQPs5wStV", "WIF": "EKpQGSJtjUID1Lq4Q2X3yUbe1qyA9vEqEu6gNS56KEPE", "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R", "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    }

    # DEX Program IDs
    DEX_PROGRAMS: Dict[str, str] = {
        "Raydium": "675kPX9MHTjS2zt1qfr1NYpt8j3EamBgK2iJSeBFgpzP", "Orca": "9W959DqEETiGZJCQ2d3V1sUaVJiXfEAsA9gKXZPineBJ", "Meteora": "LBUZKhRxPF3XUpBCepzV7CFWeWmYbgZcRzxSK6KAZF7"
    }

    # ============================================================================
    # 4. NETWORK & RPC ENDPOINTS
    # ============================================================================
    RPC_PRIMARY: str = os.getenv("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
    RPC_SECONDARY: str = os.getenv("QUICKNODE_RPC_URL", "https://api.mainnet-beta.solana.com")
    SOLANA_RPC_URL: str = RPC_PRIMARY if RPC_PRIMARY else RPC_SECONDARY

    # ============================================================================
    # 5. COMPATIBILITY ALIASES (Backward Safety Net)
    # ============================================================================
    POLL_INTERVAL_SECONDS = CHECK_INTERVAL
    MIN_PROFIT_PCT = MIN_PROFIT_PERCENT
    STARTING_BALANCE_USD = STARTING_BALANCE
    ESTIMATED_TRADE_SIZE_USD = TRADE_SIZE_USD

    @classmethod
    def validate_config(cls) -> bool:
        """Validate crucial parameters on startup"""
        errors = []

        if not cls.SOLANA_RPC_URL:
            errors.append("SOLANA_RPC_URL missing hai.")
        if cls.MIN_PROFIT_PERCENT <= 0:
            errors.append(f"MIN_PROFIT_PERCENT ({cls.MIN_PROFIT_PERCENT}) 0 se bada hona chahiye.")
        if cls.TRADE_SIZE_USD <= 0:
            errors.append(f"TRADE_SIZE_USD ({cls.TRADE_SIZE_USD}) 0 se bada hona chahiye.")
        if cls.STARTING_BALANCE <= 0:
            errors.append(f"STARTING_BALANCE ({cls.STARTING_BALANCE}) 0 se bada hona chahiye.")
        if not cls.TOKEN_PAIRS:
            errors.append("TOKEN_PAIRS list khali nahi honi chahiye.")

        if errors:
            print("❌ Config Warnings/Errors:")
            for err in errors:
                print(f"   - {err}")
            return False

        return True


# Direct import wrapper (daemon.py ke `from config import validate_config` ke liye
def validate_config() -> bool:
    """Module-level wrapper function"""
    return Config.validate_config()
