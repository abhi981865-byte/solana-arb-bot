import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    STARTING_BALANCE_USD = float(os.getenv('STARTING_BALANCE_USD', '1000'))
    POLL_INTERVAL_SECONDS = int(os.getenv('POLL_INTERVAL_SECONDS', '5'))
    MIN_PROFIT_PCT = float(os.getenv('MIN_PROFIT_PCT', '0.50'))
    ESTIMATED_TRADE_SIZE_USD = float(os.getenv('ESTIMATED_TRADE_SIZE_USD', '50'))
    
    PAIRS = [
        ('SOL', 'USDC'),
        ('SOL', 'USDT'),
        ('USDC', 'USDT'),
    ]
    
    TOKEN_MINTS = {
        'SOL': 'So11111111111111111111111111111111111111112',
        'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
        'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
    }

