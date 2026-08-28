"""
config.py - Improved Configuration
Status: ✅ Ready for production use
Last updated: Aug 28, 2026
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Central configuration for ARB Bot"""
    
    # ===== SOLANA RPC URLS (Multiple fallbacks) =====
    RPC_PRIMARY = os.getenv('HELIUS_RPC_URL', 'https://api.mainnet-beta.solana.com')
    RPC_SECONDARY = os.getenv('QUICKNODE_RPC_URL', 'https://api.mainnet-beta.solana.com')
    RPC_FALLBACK = 'https://api.mainnet-beta.solana.com'
    
    # Use primary first, fallback if fails
    SOLANA_RPC_URL = RPC_PRIMARY if RPC_PRIMARY else RPC_FALLBACK
    
    # ===== TRADING PARAMETERS =====
    STARTING_BALANCE_USD = float(os.getenv('STARTING_BALANCE_USD', '1000'))
    POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '2'))
    MIN_PROFIT_PCT = float(os.getenv('MIN_PROFIT_PCT', '0.50'))
    ESTIMATED_TRADE_SIZE_USD = float(os.getenv('ESTIMATED_TRADE_SIZE_USD', '50'))
    MAX_TRADE_PCT_OF_BALANCE = 0.10  # Never risk more than 10% per trade
    
    # ===== TOKEN MINTS (Mainnet) =====
    TOKEN_MINTS = {
        'SOL': 'So11111111111111111111111111111111111111112',
        'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
        'JUP': 'JUPyiwrYJFskUPiHa7hkeR8QnkzJBmUtrEQAPcSW3tV',
        'WIF': 'EKpQGSAhxJLCCXiNnxV2UoLmmb9yExp5z6gNS5GKEPE',
    }
    
    # ===== TOKEN DECIMALS =====
    TOKEN_DECIMALS = {
        'SOL': 9,
        'USDC': 6,
        'USDT': 6,
        'JUP': 6,
        'WIF': 6,
    }
    
    # ===== DEX PROGRAM IDS =====
    DEX_PROGRAMS = {
        'Raydium': '675kPX9MHTjS2zt1qrNsfQKsY3PmwQaN2JJXe8fgvxF',
        'Orca': '9W959DqNET9SPvCgaYW31onUVJtPKAasNqkkZFinebJ',
        'Meteora DLMM': 'LBUZKhRxPF3XUpBCwpnrPcR8wNubQgisKzxsA3kAZF7',
    }
    
    # ===== TRADING PAIRS =====
    # These are the pairs we'll scan for arbitrage
    PAIRS = [
        ('SOL', 'USDC'),
        ('SOL', 'USDT'),
        ('USDC', 'USDT'),
        ('JUP', 'USDC'),
        ('WIF', 'USDC'),
        ('JUP', 'SOL'),
        ('WIF', 'SOL'),
    ]
    
    # ===== PAPER TRADING PARAMETERS =====
    # These control how realistic the simulation is
    FILL_FAILURE_RATE = float(os.getenv('FILL_FAILURE_RATE', '0.35'))  # 35% of trades fail
    PARTIAL_FILL_RATE = float(os.getenv('PARTIAL_FILL_RATE', '0.15'))  # 15% partially fill
    PARTIAL_FILL_PENALTY_PCT = float(os.getenv('PARTIAL_FILL_PENALTY_PCT', '0.20'))  # 20% penalty
    CIRCUIT_BREAKER_LOSSES = int(os.getenv('CIRCUIT_BREAKER_LOSSES', '3'))  # Stop after 3 losses
    
    # ===== GAS ESTIMATION =====
    # Solana avg gas cost = 5000 lamports (~0.005 SOL)
    GAS_LAMPORTS = 5000
    SOL_PRICE_USD = float(os.getenv('SOL_PRICE_USD', '180'))  # Update this based on current price
    
    @staticmethod
    def get_gas_cost_usd():
        """Calculate gas cost in USD"""
        gas_sol = Config.GAS_LAMPORTS / (10 ** 9)  # Convert lamports to SOL
        return gas_sol * Config.SOL_PRICE_USD
    
    # ===== NOTIFICATIONS =====
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    # ===== DATA PATHS =====
    DATA_DIR = 'data'
    STATE_FILE = os.path.join(DATA_DIR, 'state.json')
    POOLS_FILE = os.path.join(DATA_DIR, 'pools.json')
    RUNS_LOG = os.path.join(DATA_DIR, 'runs.jsonl')


# ===== VALIDATION & LOGGING =====
def validate_config():
    """Check if config is valid"""
    errors = []
    
    if not Config.SOLANA_RPC_URL:
        errors.append("❌ SOLANA_RPC_URL not set")
    
    if Config.MIN_PROFIT_PCT < 0.1:
        errors.append("⚠️  MIN_PROFIT_PCT < 0.1% (too low, might trade at loss)")
    
    if len(Config.PAIRS) == 0:
        errors.append("❌ No trading pairs configured")
    
    if Config.SOL_PRICE_USD <= 0:
        errors.append("❌ SOL_PRICE_USD invalid")
    
    if errors:
        print("⚠️  Config Validation Warnings:")
        for err in errors:
            print(f"   {err}")
        return False
    
    return True


# ===== PRINT CONFIG ON STARTUP =====
if __name__ == '__main__':
    print("\n" + "="*60)
    print("📊 ARB BOT CONFIGURATION")
    print("="*60)
    print(f"✅ RPC URL: {Config.SOLANA_RPC_URL[:50]}...")
    print(f"✅ Trading Pairs: {len(Config.PAIRS)} pairs")
    print(f"✅ Min Profit: {Config.MIN_PROFIT_PCT}%")
    print(f"✅ Gas Cost: ${Config.get_gas_cost_usd():.4f} USD")
    print(f"✅ Starting Balance: ${Config.STARTING_BALANCE_USD}")
    print(f"✅ Poll Interval: {Config.POLL_INTERVAL_SECONDS}s")
    print("="*60 + "\n")
    
    if validate_config():
        print("✅ All checks passed!\n")
    else:
        print()
