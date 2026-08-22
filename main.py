"""
main.py
Entry point run by GitHub Actions on a schedule. Scans prices, detects
opportunities, executes paper trades, and sends Telegram alerts.

IMPORTANT: Real trading is OFF by default. See real_trader.py for what it
would take to enable it (multiple safety gates, all must be explicitly
configured). This script never calls real_trader unless ENABLE_LIVE_TRADING
is explicitly set — see the bottom of run() for exactly where that happens.
"""

import json
import os
import shutil
from datetime import datetime, timezone

from price_scanner import scan_all_pairs
from spread_detector import scan_for_opportunities, scan_for_opportunities_multi_size
from paper_trader import process_opportunities, get_summary, load_state, check_circuit_breaker, reset_circuit_breaker, save_state
from telegram_notifier import send_message, format_opportunity_alert, format_summary, format_weekly_report , check_for_reset_command
import real_trader

TRADE_SIZE_USD = 100  # primary simulated trade size used for paper trading

DOCS_STATE_PATH = os.path.join(os.path.dirname(__file__), "docs", "state.json")
DATA_STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "state.json")


def sync_dashboard_data():
    """Copies the latest state.json into docs/ so the GitHub Pages dashboard can read it."""
    if os.path.exists(DATA_STATE_PATH):
        os.makedirs(os.path.dirname(DOCS_STATE_PATH), exist_ok=True)
        shutil.copy(DATA_STATE_PATH, DOCS_STATE_PATH)


def run():
    print(f"[main] Run started at {datetime.now(timezone.utc).isoformat()}")

    # --- Check circuit breaker BEFORE scanning — no point burning API calls if paused ---
    existing_state = load_state()
# --- Check Telegram for a /reset command before doing anything else ---
    last_update_id = existing_state.get("telegram_last_update_id", 0)
    reset_requested, new_last_update_id = check_for_reset_command(last_update_id)
    existing_state["telegram_last_update_id"] = new_last_update_id

    if reset_requested and existing_state.get("circuit_breaker_tripped"):
        reset_circuit_breaker(existing_state)
        send_message("✅ Circuit breaker reset via Telegram — bot resuming.")
        existing_state = load_state()
    else:
        save_state(existing_state)
    if check_circuit_breaker(existing_state):
        print("[main] Circuit breaker is tripped. Skipping this run. "
              "Review data/state.json and call reset_circuit_breaker() manually to resume.")
        send_message("🔴 Circuit breaker still tripped — bot is paused. Review trades and reset manually when ready.")
        return

    scan_output = scan_all_pairs()
    scan_results = scan_output["results"]
    latency_info = scan_output["latency"]
    print(f"[main] Scanned {len(scan_results)} pairs")

    # --- Detect total API failure (e.g. Jupiter changed their response format,
    # or dexes= label names changed) — this would otherwise fail SILENTLY as
    # "just no opportunities found", which looks identical to a healthy run
    # with no arbitrage available. We distinguish the two explicitly.
    pairs_with_no_data = [pair for pair, prices in scan_results.items() if not prices]
    if len(pairs_with_no_data) == len(scan_results):
        error_msg = ("🔴 <b>Scanner Error</b>\nGot zero price data for ALL pairs this run. "
                      "Jupiter API may be down, or the request format may need updating. "
                      "Check the Actions log for details.")
        print(f"[main] ERROR: {error_msg}")
        send_message(error_msg)
        sync_dashboard_data()
        return
    elif pairs_with_no_data:
        print(f"[main] WARNING: no price data for: {pairs_with_no_data} (partial API issue, continuing with the rest)")

    # Log latency so we can tell if we're too slow to realistically compete
    for pair, info in latency_info.items():
        print(f"[main] {pair} scan latency: {info['total_scan_ms']}ms, "
              f"price impact: {info.get('price_impact_pct', {})}")

    # --- Multi-size testing: see how spread holds up at $50 / $100 / $500 ---
    multi_size_results = scan_for_opportunities_multi_size(scan_results)
    for pair, by_size in multi_size_results.items():
        sizes_with_opp = [size for size, opp in by_size.items() if opp]
        if sizes_with_opp:
            print(f"[main] {pair}: opportunity holds at sizes {sizes_with_opp}")

    # --- Main paper trading pass at the primary trade size ---
    opportunities = scan_for_opportunities(scan_results, trade_size_usd=TRADE_SIZE_USD)
    print(f"[main] Found {len(opportunities)} profitable opportunities at ${TRADE_SIZE_USD}")

    if not opportunities:
        print("[main] No opportunities this run.")
        sync_dashboard_data()
        return

    state, executed_trades = process_opportunities(opportunities)

    for trade in executed_trades:
        print(f"[main] Paper trade: {trade}")
        send_message(format_opportunity_alert(trade))

    if state.get("circuit_breaker_tripped"):
        send_message("🔴 Circuit breaker just tripped after consecutive losses. "
                      "Bot will pause until manually reset — review data/state.json.")

    summary = get_summary(state)
    print(f"[main] Summary: {summary}")

    # --- Real trading hook (inert unless explicitly enabled — see real_trader.py) ---
    # This ONLY does anything if ENABLE_LIVE_TRADING=true AND SOLANA_PRIVATE_KEY is set
    # AND execute_real_trade() has actually been implemented (it currently raises
    # NotImplementedError on purpose). Until then this block only logs why it declined.
    if real_trader.ENABLE_LIVE_TRADING:
        for opp in opportunities:
            result = real_trader.process_real_opportunity(opp)
            print(f"[main] Real trading attempt: {result}")

    sync_dashboard_data()


def daily_summary():
    """Separate entrypoint for a once-a-day summary message (see workflow)."""
    state = load_state()
    summary = get_summary(state)
    send_message(format_summary(summary))
    sync_dashboard_data()


def weekly_report():
    """Entrypoint for a once-a-week deep-dive report (see workflow)."""
    state = load_state()
    send_message(format_weekly_report(state))


if __name__ == "__main__":
    import sys
    import traceback

    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"

    try:
        if mode == "summary":
            daily_summary()
        elif mode == "weekly":
            weekly_report()
        else:
            run()
    except Exception as e:
        # Catch-all: any unhandled crash anywhere in the pipeline gets reported
        # to Telegram instead of failing silently. GitHub Actions will also show
        # this run as failed (we re-raise after alerting), so it's visible in
        # both places.
        tb = traceback.format_exc()
        print(f"[main] UNHANDLED ERROR:\n{tb}")
        error_summary = f"{type(e).__name__}: {str(e)}"[:300]
        try:
            send_message(f"🔴 <b>Bot Crashed</b>\nMode: {mode}\nError: {error_summary}\n\nCheck GitHub Actions logs for full traceback.")
        except Exception as notify_err:
            print(f"[main] Also failed to send crash alert to Telegram: {notify_err}")
        raise  # re-raise so the GitHub Actions run shows as failed, not green
