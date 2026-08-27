import asyncio
import httpx
import sqlite3
import random
import os
from datetime import datetime

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
    except Exception as e:
        return None

async def main():
    init_db()
    client = httpx.AsyncClient(timeout=10.0)
    scan_count = 0
    print("\n" + "=" * 40)
    print("  SOLANA ARB BOT - MINIMAL")
    print("  Balance: $" + str(STARTING_BALANCE))
    print("=" * 40 + "\n")
    while True:
        scan_count += 1
        print(f"[Scan #{scan_count}] {datetime.now().strftime('%H:%M:%S')}")
        print("-" * 40)
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
        balance, profit, trades = get_stats()
        print(f"\n  Balance: ${balance:.2f} | Profit: ${profit:.4f} | Trades: {trades}\n")
        await asyncio.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    asyncio.run(main())

