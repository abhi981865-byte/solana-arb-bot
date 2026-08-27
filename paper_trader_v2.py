import sqlite3
from config import Config
class PaperTraderDB:
    def __init__(self): self.db = Config.DB_PATH
    def get_balance(self): return Config.STARTING_BALANCE_USD
    def add_trade(self, t): return True
    def get_all_trades(self): return []
    def set_state(self, k, v): pass
    def get_state(self, k, d=''): return d
def get_summary(db): return {'balance_usd': Config.STARTING_BALANCE_USD, 'roi_pct': 0, 'total_profit_usd': 0, 'total_trades': 0, 'sharpe_ratio': 0, 'max_drawdown_pct': 0, 'circuit_breaker_tripped': False, 'fill_success_rate_pct': 85}
def process_opportunities(db, opps): pass
