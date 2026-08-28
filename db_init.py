import os
import sqlite3
from datetime import datetime, timezone
from config import Config

DB_PATH = os.path.join(Config.DATA_DIR, "arb_bot.db")


def init_database():
    os.makedirs(Config.DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, pair TEXT NOT NULL,
            buy_dex TEXT, sell_dex TEXT, buy_price REAL, sell_price REAL,
            trade_size_usd REAL, net_spread_pct REAL, status TEXT, profit_usd REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, pair TEXT NOT NULL,
            gross_spread_pct REAL, net_spread_pct REAL,
            trade_size_usd REAL, confidence REAL,
            was_executed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TEXT NOT NULL, end_time TEXT,
            loops_completed INTEGER DEFAULT 0,
            opportunities_found INTEGER DEFAULT 0,
            trades_executed INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            final_balance REAL, roi_pct REAL,
            status TEXT DEFAULT 'running'
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_pair ON trades(pair)")
    conn.commit()
    conn.close()
    print(f"✅ Database ready: {DB_PATH}")


if __name__ == "__main__":
    print("🗄️ Initializing database...")
    init_database()
    print("✅ Done!")
