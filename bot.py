import asyncio
import httpx
import sqlite3
import random
import os
import requests
from datetime import datetime

# ========== CONFIG ==========
STARTING_BALANCE = 1000
POLL_INTERVAL = 5
MIN_PROFIT = 0.5
TRADE_SIZE = 50

PAIRS = [
    ("SOL", "USDC"),
    ("SOL", "USDT"),
    ("USDC", "USDT"),
]

MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}

# ========== TELEGRAM CONFIG ==========
# YAHAN APNI DETAILS DALO
TELEGRAM_BOT_TOKEN = ""   # @BotFather se milega
TELEGRAM_CHAT_ID = ""     # getUpdates API se milega

# ========== TELEGRAM FUNCTIONS ==========
def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        requests.post(url, json=data, timeout=5)
    except Exception as e:
        print(f"  [Telegram Error: {e}]")

def send_startup_alert():
    msg = f"""🤖 <b>Solana Arb Bot Started!</b>

💰 Starting Balance: ${STARTING_BALANCE}
⏱️ Scan Interval: {POLL_INTERVAL}s
🎯 Min Profit: {MIN_PROFIT}%
📊 Trade Size: ${TRADE_SIZE}

Bot is now scanning..."""
    send_telegram(msg)

def send_trade_alert(pair, spread, profit, balance):
    msg = f"""💰 <b>Arbitrage Trade!</b>

📊 Pair: {pair}
📈 Spread: {spread:.3f}%
💵 Profit: ${profit:.4f}
💰 Balance: ${balance:.2f}

✅ Paper trade simulated!"""
    send_telegram(msg)

def send_daily_summary(balance, profit, trades, scan_count):
    roi = ((balance - STARTING_BALANCE) / STARTING_BALANCE) * 100
    msg = f"""📊 <b>Daily Summary</b>

💰 Balance: ${balance:.2f}
📈 ROI: {roi:.2f}%
💵 Profit: ${profit:.4f}
🔄 Trades: {trades}
🔍 Scans: {scan_count}

{'🟢 Profitable!' if profit > 0 else '🔴 No profit yet'}"""
    send_telegram(msg)

# ========== DATABASE ==========
os.makedirs("data", exist_ok=True)

def init_db():
    conn = sqlite3.connect("data/arb.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, time TEXT, pair TEXT, spread REAL, profit REAL, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR IGNORE INTO state VALUES ('profit', '0')")
    c.execute("INSERT OR IGNORE INTO state VALUES ('trades', '0')")
    conn.commit()
    conn.close()

def add_trade(pair, spread, profit, status):
    conn = sqlite3.connect("data/arb.db")
    c = conn.cursor()
    c.execute("INSERT INTO trades VALUES (NULL, ?, ?, ?, ?, ?)", (datetime.now().isoformat(), pair, spread, profit, status))
    c.execute("UPDATE state SET value = CAST(value AS REAL) + ? WHERE key = 'profit'", (profit,))
    c.execute("UPDATE state SET value = CAST(value AS INTEGER) + 1 WHERE key = 'trades'")
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("data/arb.db")
    c = conn.cursor()
    c.execute("SELECT value FROM state WHERE key = 'profit'")
    profit = float(c.fetchone()[0])
    c.execute("SELECT value FROM state WHERE key = 'trades'")
    trades = int(c.fetchone()[0])
    conn.close()
    return STARTING_BALANCE + profit, profit, trades

# ========== PRICE SCANNER ==========
async def get_price(client, token_in, token_out, amount_usd=10):
    try:
        mint_in = MINTS.get(token_in, token_in)
        mint_out = MINTS.get(token_out, token_out)
        if token_in in ["USDC", "USDT"]:
            amount_raw = int(amount_usd * 1_000_000)
        else:
            amount_raw = int((amount_usd / 150) * 1_000_000_000)
        resp = await client.get("https://quote-api.jup.ag/v6/quote", params={"inputMint": mint_in, "outputMint": mint_out, "amount": str(amount_raw), "slippageBps": "100"})
        if resp.status_code != 200:
            return None
        data = resp.json()
        in_amt = float(data.get("inAmount", amount_raw))
        out_amt = float(data.get("outAmount", 0))
        if token_in in ["USDC", "USDT"] and token_out in ["USDC", "USDT"]:
            price = (out_amt / 1_000_000) / (in_amt / 1_000_000)
        elif token_in in ["USDC", "USDT"]:
            price = (out_amt / 1_000_000_000) / (in_amt / 1_000_000)
        else:
            price = (out_amt / 1_000_000) / (in_amt / 1_000_000_000)
        return price
    except:
        return None

# ========== MAIN BOT ==========
async def main():
    init_db()
    client = httpx.AsyncClient(timeout=10.0)
    scan_count = 0
    last_summary_time = datetime.now()
    
    print("\n" + "=" * 45)
    print("  SOLANA ARB BOT - WITH TELEGRAM ALERTS")
    print("  Balance: $" + str(STARTING_BALANCE))
    print("=" * 45 + "\n")
    
    send_startup_alert()
    
    while True:
        scan_count += 1
        print(f"[Scan #{scan_count}] {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 45)
        
        for pair in PAIRS:
            a, b = pair
            p1 = await get_price(client, a, b)
            p2 = await get_price(client, b, a)
            
            if p1 and p2 and p1 > 0 and p2 > 0:
                spread = abs(p1 - p2) / min(p1, p2) * 100
                net_spread = spread - 0.6
                
                if net_spread > MIN_PROFIT:
                    if random.random() < 0.30:
                        profit = 0
                        status = "failed"
                    else:
                        profit = round(TRADE_SIZE * (net_spread / 100) * 0.994, 4)
                        status = "simulated"
                    
                    add_trade(f"{a}/{b}", round(net_spread, 3), profit, status)
                    print(f"  {a}/{b} | Spread: {spread:.2f}% | Profit: ${profit} | {status.upper()}")
                    
                    if status == "simulated":
                        balance, _, _ = get_stats()
                        send_trade_alert(f"{a}/{b}", spread, profit, balance)
        
        balance, profit, trades = get_stats()
        print(f"\n  Balance: ${balance:.2f} | Profit: ${profit:.4f} | Trades: {trades}\n")
        
        if (datetime.now() - last_summary_time).total_seconds() > 3600:
            send_daily_summary(balance, profit, trades, scan_count)
            last_summary_time = datetime.now()
        
        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())
TELEGRAM_BOT_TOKEN = "8982586456:AAF8Q-y96A-f_USQDbzNzMXcIMVU4DxVhnE"
TELEGRAM_CHAT_ID = "8855072390"   
