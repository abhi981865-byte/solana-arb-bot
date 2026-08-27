from dotenv import load_dotenv
import os
load_dotenv()
class Config:
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    STARTING_BALANCE_USD = float(os.getenv('STARTING_BALANCE_USD', '1000'))
    POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '2'))
    MIN_PROFIT_PCT = float(os.getenv('MIN_PROFIT_PCT', '0.65'))
    MAX_PRICE_IMPACT_PCT = float(os.getenv('MAX_PRICE_IMPACT_PCT', '0.10'))
    ESTIMATED_TRADE_SIZE_USD = float(os.getenv('ESTIMATED_TRADE_SIZE_USD', '100'))
    DB_PATH = os.getenv('DB_PATH', 'data/arb_trades.db')
    PAIRS = [('SOL', 'USDC'), ('SOL', 'USDT'), ('USDC', 'USDT'), ('BONK', 'USDC'), ('JUP', 'USDC'), ('WIF', 'USDC')]
