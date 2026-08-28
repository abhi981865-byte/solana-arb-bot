import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    RPC_PRIMARY = os.getenv('HELIUS_RPC_URL', 'https://api.mainnet-beta.solana.com')
    RPC_SECONDARY = os.getenv('QUICKNODE_RPC_URL', '')
    RPC_FALLBACK = 'https://api.mainnet-beta.solana.com'
    SOLANA_RPC_URL = RPC_PRIMARY if RPC_PRIMARY else RPC_FALLBACK
    
    POLL_INTERVAL_SECONDS = float(os.getenv('POLL_INTERVAL_SECONDS', '0.5'))
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
    MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '50'))
    PRICE_CACHE_TTL_SECONDS = float(os.getenv('PRICE_CACHE_TTL', '1.0'))
    
    STARTING_BALANCE_USD = float(os.getenv('STARTING_BALANCE_USD', '1000'))
    MIN_PROFIT_PCT = float(os.getenv('MIN_PROFIT_PCT', '0.30'))
    ESTIMATED_TRADE_SIZE_USD = float(os.getenv('ESTIMATED_TRADE_SIZE_USD', '50'))
    MAX_TRADE_PCT_OF_BALANCE = 0.10
    
    TOKEN_MINTS = {
        'SOL': 'So11111111111111111111111111111111111111112',
        'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
        'JUP': 'JUPyiwrYJFskUPiHa7hkeR8QnkzJBmUtrEQAPcSW3tV',
        'WIF': 'EKpQGSAhxJLCCXiNnxV2UoLmmb9yExp5z6gNS5GKEPE',
        'BONK': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
        'RAY': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
    }
    
    TOKEN_DECIMALS = {'SOL': 9, 'USDC': 6, 'USDT': 6, 'JUP': 6, 'WIF': 6, 'BONK': 5, 'RAY': 6}
    
    PAIRS = [
        ('SOL', 'USDC'), ('SOL', 'USDT'), ('USDC', 'USDT'),
        ('JUP', 'USDC'), ('WIF', 'USDC'), ('JUP', 'SOL'),
        ('WIF', 'SOL'), ('BONK', 'USDC'), ('RAY', 'USDC'),
        ('BONK', 'SOL'), ('JUP', 'USDT'), ('WIF', 'USDT'),
    ]
    
    FILL_FAILURE_RATE = float(os.getenv('FILL_FAILURE_RATE', '0.35'))
    PARTIAL_FILL_RATE = float(os.getenv('PARTIAL_FILL_RATE', '0.15'))
    PARTIAL_FILL_PENALTY_PCT = float(os.getenv('PARTIAL_FILL_PENALTY_PCT', '0.20'))
    CIRCUIT_BREAKER_LOSSES = int(os.getenv('CIRCUIT_BREAKER_LOSSES', '3'))
    
    GAS_LAMPORTS = 5000
    SOL_PRICE_USD = float(os.getenv('SOL_PRICE_USD', '180'))
    
    @staticmethod
    def get_gas_cost_usd():
        return (Config.GAS_LAMPORTS / 1e9) * Config.SOL_PRICE_USD
    
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
    
    DATA_DIR = 'data'
    STATE_FILE = os.path.join(DATA_DIR, 'state.json')
    POOLS_FILE = os.path.join(DATA_DIR, 'pools.json')
    RUNS_LOG = os.path.join(DATA_DIR, 'runs.jsonl')


def validate_config():
    errors = []
    if not Config.SOLANA_RPC_URL:
        errors.append("SOLANA_RPC_URL not set")
    if Config.MIN_PROFIT_PCT < 0.1:
        errors.append("MIN_PROFIT_PCT < 0.1%")
    if len(Config.PAIRS) == 0:
        errors.append("No trading pairs")
    if errors:
        print("Config Warnings:")
        for e in errors:
            print(f"  {e}")
        return False
    return True
