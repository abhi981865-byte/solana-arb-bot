import os
import sqlite3
import sys
from datetime import datetime, timezone
from config import Config
from paper_trader import load_state, get_summary

DB_PATH = os.path.join(Config.DATA_DIR, "arb_bot.db")


def get_bot_status():
    state = load_state()
    summary = get_summary(state)
    pid_file = os.path.join(Config.DATA_DIR, "daemon.pid")
    return {
        "running": os.path.exists(pid_file),
        "balance_usd": summary["balance_usd"],
        "roi_pct": summary["roi_pct"],
        "total_trades": summary["total_trades"],
        "failed_trades": summary["failed_trades"],
        "fill_success_rate": summary["fill_success_rate_pct"],
        "circuit_breaker_tripped": summary["circuit_breaker_tripped"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def print_status():
    status = get_bot_status()
    print("\n" + "=" * 60)
    print("🤖 BOT STATUS")
    print("=" * 60)
    print(f"🟢 Status: {'RUNNING' if status['running'] else 'STOPPED'}")
    print(f"💰 Balance: ${status['balance_usd']:.4f}")
    print(f"📈 ROI: {status['roi_pct']:+.3f}%")
    print(f"📊 Trades: {status['total_trades']} | ❌ Failed: {status['failed_trades']}")
    print(f"📉 Fill Rate: {status['fill_success_rate']}%")
    print(f"🔒 Breaker: {'TRIPPED ⚠️' if status['circuit_breaker_tripped'] else 'OK ✅'}")
    print(f"🕐 Updated: {status['timestamp'][:19]}")
    print("=" * 60)


def print_recent_trades(limit=10):
    if not os.path.exists(DB_PATH):
        print("❌ DB not found. Run: python db_init.py")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("\n📭 No trades yet.")
        return
    print("\n" + "=" * 80)
    print(f"📊 RECENT TRADES (Last {limit})")
    print("=" * 80)
    print(f"{'Time':<20} {'Pair':<12} {'Status':<12} {'Profit':>12}")
    print("-" * 80)
    for row in rows:
        ts = row['timestamp'][:19] if row['timestamp'] else 'N/A'
        emoji = "✅" if row['status'] == 'filled' else "⚠️" if row['status'] == 'partial_fill' else "❌"
        profit = f"${row['profit_usd']:+.4f}" if row['profit_usd'] else "N/A"
        print(f"{ts:<20} {row['pair']:<12} {emoji} {row['status']:<10} {profit:>12}")
    print("=" * 80)


def print_daily_stats():
    if not os.path.exists(DB_PATH):
        print("❌ DB not found.")
        return
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(timestamp) as day, COUNT(*) as total,
         SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) as success,
         SUM(CASE WHEN status='failed_fill' THEN 1 ELSE 0 END) as failed,
         SUM(profit_usd) as total_profit
        FROM trades GROUP BY date(timestamp) ORDER BY day DESC LIMIT 14
    """)
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print("\n📭 No daily stats.")
        return
    print("\n" + "=" * 80)
    print("📅 DAILY PERFORMANCE")
    print("=" * 80)
    print(f"{'Date':<12} {'Trades':>8} {'Success':>8} {'Failed':>8} {'Total $':>12}")
    print("-" * 80)
    for row in rows:
        tp = f"${row['total_profit']:+.4f}" if row['total_profit'] else "$0.0000"
        print(f"{row['day']:<12} {row['total']:>8} {row['success']:>8} {row['failed']:>8} {tp:>12}")
    print("=" * 80)


def main():
    if len(sys.argv) < 2:
        print("""
Usage: python monitoring.py <command>

Commands:
    status       Show bot status
    trades [n]   Recent trades (default 10)
    daily        Daily stats
        """)
        return
    cmd = sys.argv[1].lower()
    if cmd == "status":
        print_status()
    elif cmd == "trades":
        print_recent_trades(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif cmd == "daily":
        print_daily_stats()
    else:
        print(f"❌ Unknown: {cmd}")


if __name__ == "__main__":
    main()
