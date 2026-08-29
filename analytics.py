import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from config import Config

DB_PATH = os.path.join(Config.DATA_DIR, "arb_bot.db")


def get_trades():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY timestamp")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def calculate_sharpe(returns, risk_free=0.0):
    if len(returns) < 2:
        return 0.0
    avg = sum(returns) / len(returns)
    var = sum((r - avg) ** 2 for r in returns) / len(returns)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    return ((avg - risk_free) / std) * math.sqrt(365)


def calculate_max_drawdown(trades):
    if not trades:
        return 0.0
    balance = Config.STARTING_BALANCE_USD
    peak = balance
    max_dd = 0.0
    for trade in trades:
        profit = trade.get("profit_usd", 0) or 0
        balance += profit
        if balance > peak:
            peak = balance
        dd = (peak - balance) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


def calculate_win_rate(trades):
    total = len(trades)
    if total == 0:
        return {"win_rate": 0, "total": 0}
    wins = sum(1 for t in trades if (t.get("profit_usd") or 0) > 0)
    return {"win_rate": round(wins / total * 100, 2), "total": total, "wins": wins}


def calculate_profit_factor(trades):
    gp = sum(t.get("profit_usd", 0) for t in trades if (t.get("profit_usd") or 0) > 0)
    gl = abs(sum(t.get("profit_usd", 0) for t in trades if (t.get("profit_usd") or 0) < 0))
    return gp / gl if gl > 0 else float('inf') if gp > 0 else 0.0


def generate_report():
    trades = get_trades()
    if not trades:
        return {"status": "no_data", "message": "No trades yet. Start the bot!"}
    returns = [(t.get("profit_usd", 0) or 0) / (t.get("trade_size_usd", 100) or 100) * 100 for t in trades]
    wr = calculate_win_rate(trades)
    max_dd = calculate_max_drawdown(trades)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "status": "ok", "overview": wr, "profit": {
            "total": round(sum(t.get("profit_usd", 0) for t in trades), 4), "avg_per_trade": round(sum(t.get("profit_usd", 0) for t in trades) / len(trades), 4), "profit_factor": round(calculate_profit_factor(trades), 2), }, "risk": {
            "sharpe": round(calculate_sharpe(returns), 3), "max_drawdown_pct": round(max_dd, 2), }, }


def print_report():
    report = generate_report()
    if report.get("status") == "no_data":
        print(f"\n📭 {report['message']}")
        return
    print("\n" + "=" * 70)
    print("📊 PERFORMANCE REPORT")
    print("=" * 70)
    print(f"Generated: {report['generated_at'][:19]}")
    print("-" * 70)
    o = report["overview"]
    print(f"\n📈 Trades: {o['total']} | Wins: {o['wins']} | Win Rate: {o['win_rate']}%")
    p = report["profit"]
    print(f"\n💰 Total: ${p['total']:+.4f} | Avg: ${p['avg_per_trade']:+.4f}")
    print(f"💰 Profit Factor: {p['profit_factor']}")
    r = report["risk"]
    print(f"\n⚠️ Sharpe: {r['sharpe']} | Max DD: {r['max_drawdown_pct']}%")
    print("\n" + "=" * 70)
    print("🎯 LIVE TRADING READINESS")
    print("-" * 40)
    sharpe = r["sharpe"]
    max_dd = r["max_drawdown_pct"]
    if sharpe > 1.0 and max_dd < 20:
        print("✅ READY FOR LIVE!")
    elif sharpe > 0.5 and max_dd < 30:
        print("🟡 PROMISING — Continue paper trading")
    else:
        print("🔴 NOT READY — Needs improvement")
    print("=" * 70)


if __name__ == "__main__":
    print_report()
