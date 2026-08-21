"""
paper_trader.py
Simulates trades with fake money so we can validate the strategy before any
real capital is used. State (balance + trade log) persists in data/state.json,
which GitHub Actions commits back to the repo after every run.
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
FILL_FAILURE_RATE = 0.35  # ~35% of "opportunities" fail to fill at quoted price, tune from real observation later
PARTIAL_FILL_RATE = 0.15  # of the ones that DO fill, 15% only partially fill (worse price than quoted)
PARTIAL_FILL_PENALTY_PCT = 0.20  # partial fills lose ~20% of their expected profit to worse execution

# --- Circuit breaker ---
CIRCUIT_BREAKER_CONSECUTIVE_LOSSES = 3  # pause after this many consecutive losing/failed trades


def load_state():
    if not os.path.exists(STATE_PATH):
        return {
            "balance_usd": STARTING_BALANCE_USD,
            "starting_balance_usd": STARTING_BALANCE_USD,
            "trades": [],
            "total_trades": 0,
            "total_profit_usd": 0.0,
            "failed_trades": 0,
            "partial_fill_trades": 0,
            "consecutive_losses": 0,
            "circuit_breaker_tripped": False,
            "circuit_breaker_tripped_at": None,
        }
    with open(STATE_PATH, "r") as f:
        state = json.load(f)
    # Backfill fields for state files created before these features existed
    state.setdefault("failed_trades", 0)
    state.setdefault("partial_fill_trades", 0)
    state.setdefault("consecutive_losses", 0)
    state.setdefault("circuit_breaker_tripped", False)
    state.setdefault("circuit_breaker_tripped_at", None)
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def execute_paper_trade(state, opportunity):
    """
    Simulates executing an arbitrage opportunity, including realistic fill
    failure and partial-fill simulation. Caps trade size to a safe fraction
    of current paper balance (mirrors a real risk-control rule).
    """
    safe_trade_size = min(opportunity["trade_size_usd"], state["balance_usd"] * MAX_TRADE_PCT_OF_BALANCE)
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
        # Failed fill: opportunity vanished before execution (common in real arb —
        # another bot got there first, or price moved past slippage tolerance).
        # Small loss simulated for the wasted gas fee.
        loss_usd = -0.002  # ~gas cost of a reverted/failed tx
        trade_record = {
            **base_trade_record,
            "status": "failed_fill",
            "profit_usd": loss_usd,
        }
        state["balance_usd"] = round(state["balance_usd"] + loss_usd, 4)
        state["total_profit_usd"] = round(state["total_profit_usd"] + loss_usd, 4)
        state["failed_trades"] += 1
        state["total_trades"] += 1
        state["consecutive_losses"] += 1
        state["trades"].append(trade_record)
        state["trades"] = state["trades"][-500:]
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

    state["balance_usd"] = round(state["balance_usd"] + profit_usd, 4)
    state["total_profit_usd"] = round(state["total_profit_usd"] + profit_usd, 4)
    state["total_trades"] += 1
    state["trades"].append(trade_record)
    state["trades"] = state["trades"][-500:]

    # Track consecutive losses for the circuit breaker (a "loss" = negative profit)
    if profit_usd < 0:
        state["consecutive_losses"] += 1
    else:
        state["consecutive_losses"] = 0

    return trade_record


def check_circuit_breaker(state):
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


def reset_circuit_breaker(state):
    """Manually reset the breaker (call this yourself after reviewing what happened)."""
    state["circuit_breaker_tripped"] = False
    state["circuit_breaker_tripped_at"] = None
    state["consecutive_losses"] = 0
    save_state(state)


def process_opportunities(opportunities):
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


def get_summary(state):
    roi_pct = ((state["balance_usd"] - state["starting_balance_usd"]) / state["starting_balance_usd"]) * 100
    total = max(state["total_trades"], 1)
    win_trades = state["total_trades"] - state.get("failed_trades", 0)
    return {
        "balance_usd": state["balance_usd"],
        "total_trades": state["total_trades"],
        "failed_trades": state.get("failed_trades", 0),
        "partial_fill_trades": state.get("partial_fill_trades", 0),
        "fill_success_rate_pct": round((win_trades / total) * 100, 1),
        "total_profit_usd": state["total_profit_usd"],
        "roi_pct": round(roi_pct, 3),
        "circuit_breaker_tripped": state.get("circuit_breaker_tripped", False),
    }
