import sqlite3, os
from config import Config
def init_database():
    os.makedirs(os.path.dirname(Config.DB_PATH), exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, timestamp TEXT, pair TEXT, buy_dex TEXT, sell_dex TEXT, buy_price REAL, sell_price REAL, trade_size_usd REAL, net_spread_pct REAL, profit_usd REAL, status TEXT, created_at TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)')
    cursor.execute('INSERT OR IGNORE INTO state VALUES ("balance_usd", ?)', (str(Config.STARTING_BALANCE_USD),))
    conn.commit()
    conn.close()
    print(f'Database initialized: {Config.DB_PATH}')
if __name__ == '__main__': init_database()
