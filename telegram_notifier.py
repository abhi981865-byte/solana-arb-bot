"""
telegram_notifier.py
Sends alerts to Telegram via bot API. Reads credentials from environment
variables (set as GitHub Actions secrets — never hardcode these).

Setup (one-time, do this from your phone):
1. Open Telegram, search "BotFather", send /newbot, follow prompts -> get a bot token
2. Send any message to your new bot
3. Visit https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates in a browser
   to find your chat_id in the JSON response
4. Add both as GitHub repo secrets: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""

import os
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_message(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("[telegram_notifier] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID env vars — skipping send.")
        print(f"[telegram_notifier] Message was:\n{text}")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"[telegram_notifier] Failed to send: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as e:
        print(f"[telegram_notifier] Request error: {e}")
        return False


def format_opportunity_alert(trade):
    return (
        f"🔍 <b>Paper Trade Executed</b>\n"
        f"Pair: {trade['pair']}\n"
        f"Buy on {trade['buy_dex']} @ {trade['buy_price']:.4f}\n"
        f"Sell on {trade['sell_dex']} @ {trade['sell_price']:.4f}\n"
        f"Size: ${trade['trade_size_usd']}\n"
        f"Net spread: {trade['net_spread_pct']}%\n"
        f"Simulated profit: ${trade['profit_usd']}"
    )


def format_summary(summary):
    breaker_line = "\n🔴 CIRCUIT BREAKER TRIPPED — bot paused, review needed" if summary.get("circuit_breaker_tripped") else ""
    return (
        f"📊 <b>Paper Trading Summary</b>\n"
        f"Balance: ${summary['balance_usd']:.2f}\n"
        f"Total trades: {summary['total_trades']}\n"
        f"Fill success rate: {summary.get('fill_success_rate_pct', '—')}%\n"
        f"Failed fills: {summary.get('failed_trades', 0)}\n"
        f"Total profit: ${summary['total_profit_usd']:.2f}\n"
        f"ROI: {summary['roi_pct']}%"
        f"{breaker_line}"
    )


def format_weekly_report(state):
    """
    Deeper weekly breakdown: best/worst trade, per-pair performance,
    win rate trend. Called once a week from main.py.
    """
    trades = state.get("trades", [])
    if not trades:
        return "📅 <b>Weekly Report</b>\nNo trades recorded this period."

    recent = trades[-500:]  # everything we have (trade log is capped at 500)
    profits = [t["profit_usd"] for t in recent]
    best = max(recent, key=lambda t: t["profit_usd"])
    worst = min(recent, key=lambda t: t["profit_usd"])

    per_pair = {}
    for t in recent:
        per_pair.setdefault(t["pair"], {"count": 0, "profit": 0.0})
        per_pair[t["pair"]]["count"] += 1
        per_pair[t["pair"]]["profit"] += t["profit_usd"]

    pair_lines = "\n".join(
        f"  {pair}: {d['count']} trades, ${d['profit']:.3f}"
        for pair, d in sorted(per_pair.items(), key=lambda x: -x[1]["profit"])
    )

    return (
        f"📅 <b>Weekly Report</b>\n"
        f"Trades this period: {len(recent)}\n"
        f"Net profit: ${sum(profits):.3f}\n\n"
        f"Best trade: {best['pair']} +${best['profit_usd']:.4f}\n"
        f"Worst trade: {worst['pair']} ${worst['profit_usd']:.4f}\n\n"
        f"<b>By pair:</b>\n{pair_lines}"
    )
def get_updates(offset=None):
    """Polls Telegram for new incoming messages sent to the bot."""
    if not BOT_TOKEN:
        return []
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = {"timeout": 0}
    if offset is not None:
        params["offset"] = offset
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"[telegram_notifier] Failed to get updates: {resp.status_code} {resp.text[:200]}")
            return []
        return resp.json().get("result", [])
    except requests.RequestException as e:
        print(f"[telegram_notifier] Request error (get_updates): {e}")
        return []


def check_for_reset_command(last_update_id):
    """
    Checks Telegram for a /reset command sent by the authorized chat.
    Returns (reset_requested, newest_update_id) so the caller can save
    the offset and never reprocess the same message twice.
    """
    offset = (last_update_id + 1) if last_update_id else None
    updates = get_updates(offset=offset)
    reset_requested = False
    newest_id = last_update_id
    for update in updates:
        newest_id = max(newest_id, update["update_id"])
        message = update.get("message", {})
        text = message.get("text", "").strip().lower()
        sender_id = str(message.get("chat", {}).get("id", ""))
        if text == "/reset" and sender_id == str(CHAT_ID):
            reset_requested = True
    return reset_requested, newest_id