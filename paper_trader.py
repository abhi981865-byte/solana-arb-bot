import json
import os
import random
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "state.json")
STARTING_BALANCE_USD = 1000.0
MAX_TRADE_PCT_OF_BALANCE = 0.10
FILL_FAILURE_RATE = 0.35
PARTIAL_FILL_RATE = 0.15
PARTIAL_FILL_PENALTY_PCT = 0.20
CIRCUIT_BREAKER_CONSECUTIVE_LOSSES = 3
MAX_LEARNINGS = 50


def _default_state():
    return {
        "balance_usd": STARTING_BALANCE_USD, "starting_balance_usd": STARTING_BALANCE_USD, "trades": [], "total_trades": 0, "total_profit_usd": 0.0, "failed_trades": 0, "partial_fill_trades": 0, "consecutive_losses": 0, "circuit_breaker_tripped": False, "circuit_breaker_tripped_at": None, "telegram_last_update_id": 0, "chat_history": [], "learnings": [], }


def load_state():
    if not os.path.exists(STATE_PATH):
        return _default_state()
    try:
        with open(STATE_PATH, "r") as f:
            content = f.read().strip()
            if not content:
                return _default_state()
            state = json.loads(content)
    except (json.JSONDecodeError, IOError, OSError):
        return _default_state()
    defaults = _default_state()
    for key, val in defaults.items():
        state.setdefault(key, val)
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    temp_path = STATE_PATH + ".tmp"
    with open(temp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(temp_path, STATE_PATH)


def execute_paper_trade(state, opportunity):
    safe_trade_size = min(opportunity["trade_size_usd"], state["balance_usd"] * MAX_TRADE_PCT_OF_BALANCE)
    if safe_trade_size < 1:
        return None
    net_spread_pct = opportunity["net_spread_pct"]
    base_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(), "pair": opportunity["pair"], "buy_dex": opportunity["buy_dex"], "sell_dex": opportunity["sell_dex"], "buy_price": opportunity["buy_price"], "sell_price": opportunity["sell_price"], "trade_size_usd": round(safe_trade_size, 2), "net_spread_pct": net_spread_pct, }
    if random.random() < FILL_FAILURE_RATE:
        loss_usd = -0.002
        trade_record = {**base_record, "status": "failed_fill", "profit_usd": loss_usd}
        state["balance_usd"] = round(state["balance_usd"] + loss_usd, 4)
        state["total_profit_usd"] = round(state["total_profit_usd"] + loss_usd, 4)
        state["failed_trades"] += 1
        state["total_trades"] += 1
        state["consecutive_losses"] += 1
        state["trades"].append(trade_record)
        state["trades"] = state["trades"][-500:]
        return trade_record
    is_partial = random.random() < PARTIAL_FILL_RATE
    if is_partial:
        profit_usd = round((net_spread_pct / 100) * safe_trade_size * (1 - PARTIAL_FILL_PENALTY_PCT), 4)
        status = "partial_fill"
        state["partial_fill_trades"] += 1
    else:
        profit_usd = round((net_spread_pct / 100) * safe_trade_size, 4)
        status = "filled"
    trade_record = {**base_record, "status": status, "profit_usd": profit_usd}
    state["balance_usd"] = round(state["balance_usd"] + profit_usd, 4)
    state["total_profit_usd"] = round(state["total_profit_usd"] + profit_usd, 4)
    state["total_trades"] += 1
    state["trades"].append(trade_record)
    state["trades"] = state["trades"][-500:]
    if profit_usd < 0:
        state["consecutive_losses"] += 1
    else:
        state["consecutive_losses"] = 0
    return trade_record


def check_circuit_breaker(state):
    if state.get("circuit_breaker_tripped"):
        return True
    if state["consecutive_losses"] >= CIRCUIT_BREAKER_CONSECUTIVE_LOSSES:
        state["circuit_breaker_tripped"] = True
        state["circuit_breaker_tripped_at"] = datetime.now(timezone.utc).isoformat()
        return True
    return False


def reset_circuit_breaker(state):
    state["circuit_breaker_tripped"] = False
    state["circuit_breaker_tripped_at"] = None
    state["consecutive_losses"] = 0
    save_state(state)


def record_learning(state, text):
    state.setdefault("learnings", [])
    state["learnings"].append({"at": datetime.now(timezone.utc).isoformat(), "note": text})
    state["learnings"] = state["learnings"][-MAX_LEARNINGS:]
    save_state(state)


def process_opportunities(opportunities):
    state = load_state()
    executed = []
    if check_circuit_breaker(state):
        save_state(state)
        return state, executed
    for opp in opportunities:
        trade = execute_paper_trade(state, opp)
        if trade:
            executed.append(trade)
        if check_circuit_breaker(state):
            break
    save_state(state)
    return state, executed


def get_summary(state):
    roi_pct = ((state["balance_usd"] - state["starting_balance_usd"]) / state["starting_balance_usd"]) * 100
    total = max(state["total_trades"], 1)
    win_trades = state["total_trades"] - state.get("failed_trades", 0)
    return {
        "balance_usd": state["balance_usd"], "total_trades": state["total_trades"], "failed_trades": state.get("failed_trades", 0), "partial_fill_trades": state.get("partial_fill_trades", 0), "fill_success_rate_pct": round((win_trades / total) * 100, 1), "total_profit_usd": state["total_profit_usd"], "roi_pct": round(roi_pct, 3), "circuit_breaker_tripped": state.get("circuit_breaker_tripped", False), }
