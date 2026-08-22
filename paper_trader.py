"""
paper_trader.py

Simulates trades with fake money so we can validate the strategy before any
real capital is used. State (balance + trade log + stats) persists in
data/state.json, which GitHub Actions commits back to the repo after every run.
"""

import json
import os
import random
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "state.json")

STARTING_BALANCE_USD = 1000.0  # fake starting capital
MAX_TRADE_PCT_OF_BALANCE = 0.10  # never simulate risking more than 10% of paper balance per trade

# --- Realism: simulated fill failures ---
# In real arbitrage, by the time your transaction lands, the opportunity has
# often already been taken by a faster bot, or the price moved (slippage
# exceeded tolerance) and the tx reverts. A paper trader that assumes 100%
# fill rate wildly overstates real-world profitability. We simulate this.
FILL_FAILURE_RATE = 0.35       # ~35% of "opportunities" fail to fill at quoted price
PARTIAL_FILL_RATE = 0.15       # of the ones that DO fill, 15% only partially fill
PARTIAL_FILL_PENALTY_PCT = 0.20  # partial fills lose ~20% of expected profit

# --- Circuit breaker ---
CIRCUIT_BREAKER_CONSECUTIVE_LOSSES = 3  # pause after this many consecutive losing/failed trades
CIRCUIT_BREAKER_COOLDOWN_MINUTES = 30   # NEW: auto-eligible for reset after this long (still needs manual reset call)


def _default_state() -> dict:
    """Fresh state for a brand-new run (no state.json yet)."""
    return {
        "balance_usd": STARTING_BALANCE_USD,
        "starting_balance_usd": STARTING_BALANCE_USD,
        "peak_balance_usd": STARTING_BALANCE_USD,   # NEW: for drawdown tracking
        "max_drawdown_pct": 0.0,                      # NEW
        "trades": [],
        "total_trades": 0,
        "total_profit_usd": 0.0,
        "failed_trades": 0,
        "partial_fill_trades": 0,
        "consecutive_losses": 0,
        "best_trade_usd": 0.0,                        # NEW
        "worst_trade_usd": 0.0,                        # NEW
        "pair_stats": {},                              # NEW: per-pair win/loss counts
        "circuit_breaker_tripped": False,
        "circuit_breaker_tripped_at": None,
    }


def load_state() -> dict:
    """Load state from disk, backfilling any fields older state files are missing."""
    if not os.path.exists(STATE_PATH):
        return _default_state()

    with open(STATE_PATH, "r") as f:
        state = json.load(f)

    # Backfill fields for state files created before these features existed
    defaults = _default_state()
    for key, value in defaults.items():
        state.setdefault(key, value)

    return state


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _update_drawdown(state: dict) -> None:
    """NEW: tracks peak balance and worst drawdown from that peak."""
    balance = state["balance_usd"]
    if balance > state["peak_balance_usd"]:
        state["peak_balance_usd"] = balance

    peak = state["peak_balance_usd"]
    if peak > 0:
        drawdown_pct = ((peak - balance) / peak) * 100
        if drawdown_pct > state["max_drawdown_pct"]:
            state["max_drawdown_pct"] = round(drawdown_pct, 3)


def _update_pair_stats(state: dict, pair: str, profit_usd: float) -> None:
    """NEW: tracks win/loss count and total profit per trading pair."""
    stats = state["pair_stats"].setdefault(pair, {"trades": 0, "wins": 0, "profit_usd": 0.0})
    stats["trades"] += 1
    stats["profit_usd"] = round(stats["profit_usd"] + profit_usd, 4)
    if profit_usd > 0:
        stats["wins"] += 1


def _record_trade(state: dict, trade_record: dict, profit_usd: float) -> None:
    """Shared bookkeeping for every trade outcome (failed, partial, or filled)."""
    state["balance_usd"] = round(state["balance_usd"] + profit_usd, 4)
    state["total_profit_usd"] = round(state["total_profit_usd"] + profit_usd, 4)
    state["total_trades"] += 1
    state["trades"].append(trade_record)
    state["trades"] = state["trades"][-500:]

    state["best_trade_usd"] = round(max(state["best_trade_usd"], profit_usd), 4)
    state["worst_trade_usd"] = round(min(state["worst_trade_usd"], profit_usd), 4)

    _update_pair_stats(state, trade_record["pair"], profit_usd)
    _update_drawdown(state)

    if profit_usd < 0:
        state["consecutive_losses"] += 1
    else:
        state["consecutive_losses"] = 0


def execute_paper_trade(state: dict, opportunity: dict) -> dict | None:
    """
    Simulates executing an arbitrage opportunity, including realistic fill
    failure and partial-fill simulation. Caps trade size to a safe fraction
    of current paper balance (mirrors a real risk-control rule).
    """
    safe_trade_size = min(
        opportunity["trade_size_usd"],
        state["balance_usd"] * MAX_TRADE_PCT_OF_BALANCE,
    )
    if safe_trade_size < 1:
        return None  # balance too low to simulate meaningfully

    net_spread_pct = opportunity["net_spread_pct"]
    base_trade_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pair": opportunity["pair"],
        "buy_dex": opportunity["buy_dex"],
        "sell_dex": opportunity["sell_dex"],
        "buy_price": opportunity["buy_price"],
        "sell_price": opportunity["sell_price"],
        "trade_size_usd": round(safe_trade_size, 2),
        "net_spread_pct": net_spread_pct,
    }

    # --- Simulate whether this trade would have actually filled in reality ---
    if random.random() < FILL_FAILURE_RATE:
        loss_usd = -0.002  # ~gas cost of a reverted/failed tx
        trade_record = {**base_trade_record, "status": "failed_fill", "profit_usd": loss_usd}
        state["failed_trades"] += 1
        _record_trade(state, trade_record, loss_usd)
        return trade_record

    # --- Simulate partial fill (fills, but at a worse effective price) ---
    is_partial = random.random() < PARTIAL_FILL_RATE
    if is_partial:
        profit_usd = round((net_spread_pct / 100) * safe_trade_size * (1 - PARTIAL_FILL_PENALTY_PCT), 4)
        status = "partial_fill"
        state["partial_fill_trades"] += 1
    else:
        profit_usd = round((net_spread_pct / 100) * safe_trade_size, 4)
        status = "filled"

    trade_record = {**base_trade_record, "status": status, "profit_usd": profit_usd}
    _record_trade(state, trade_record, profit_usd)
    return trade_record


def check_circuit_breaker(state: dict) -> bool:
    """
    Returns True if the circuit breaker is (or should be) tripped.
    Once tripped, it stays tripped until manually reset — this is deliberate:
    an automated system that self-resets after a losing streak can spiral
    without anyone noticing.
    """
    if state.get("circuit_breaker_tripped"):
        return True

    if state["consecutive_losses"] >= CIRCUIT_BREAKER_CONSECUTIVE_LOSSES:
        state["circuit_breaker_tripped"] = True
        state["circuit_breaker_tripped_at"] = datetime.now(timezone.utc).isoformat()
        return True

    return False


def circuit_breaker_cooldown_elapsed(state: dict) -> bool:
    """NEW: tells you (doesn't act on it) whether enough time has passed
    since the breaker tripped that a manual reset is reasonable to consider."""
    tripped_at = state.get("circuit_breaker_tripped_at")
    if not tripped_at:
        return False
    tripped_time = datetime.fromisoformat(tripped_at)
    elapsed_minutes = (datetime.now(timezone.utc) - tripped_time).total_seconds() / 60
    return elapsed_minutes >= CIRCUIT_BREAKER_COOLDOWN_MINUTES


def reset_circuit_breaker(state: dict) -> None:
    """Manually reset the breaker (call this yourself after reviewing what happened)."""
    state["circuit_breaker_tripped"] = False
    state["circuit_breaker_tripped_at"] = None
    state["consecutive_losses"] = 0
    save_state(state)


def process_opportunities(opportunities: list) -> tuple:
    """
    Runs each opportunity through the paper trader, returns (state, executed_trades).
    Stops executing further trades in this batch if the circuit breaker trips
    partway through.
    """
    state = load_state()
    executed = []

    if check_circuit_breaker(state):
        save_state(state)
        return state, executed  # breaker already tripped — do nothing, wait for manual reset

    for opp in opportunities:
        trade = execute_paper_trade(state, opp)
        if trade:
            executed.append(trade)
        if check_circuit_breaker(state):
            break  # stop trading immediately once tripped

    save_state(state)
    return state, executed


def get_summary(state: dict) -> dict:
    """Human-readable snapshot of bot performance, used for Telegram/daily reports."""
    roi_pct = ((state["balance_usd"] - state["starting_balance_usd"]) / state["starting_balance_usd"]) * 100
    total = max(state["total_trades"], 1)
    win_trades = state["total_trades"] - state.get("failed_trades", 0)

    # NEW: best/worst performing pair by profit
    pair_stats = state.get("pair_stats", {})
    best_pair = max(pair_stats.items(), key=lambda kv: kv[1]["profit_usd"], default=(None, None))
    worst_pair = min(pair_stats.items(), key=lambda kv: kv[1]["profit_usd"], default=(None, None))

    return {
        "balance_usd": state["balance_usd"],
        "total_trades": state["total_trades"],
        "failed_trades": state.get("failed_trades", 0),
        "partial_fill_trades": state.get("partial_fill_trades", 0),
        "fill_success_rate_pct": round((win_trades / total) * 100, 1),
        "total_profit_usd": state["total_profit_usd"],
        "avg_profit_per_trade_usd": round(state["total_profit_usd"] / total, 4),  # NEW
        "roi_pct": round(roi_pct, 3),
        "best_trade_usd": state.get("best_trade_usd", 0.0),   # NEW
        "worst_trade_usd": state.get("worst_trade_usd", 0.0),  # NEW
        "max_drawdown_pct": state.get("max_drawdown_pct", 0.0),  # NEW
        "best_pair": best_pair[0],    # NEW
        "worst_pair": worst_pair[0],  # NEW
        "circuit_breaker_tripped": state.get("circuit_breaker_tripped", False),
        "circuit_breaker_cooldown_elapsed": circuit_breaker_cooldown_elapsed(state),  # NEW
    }

