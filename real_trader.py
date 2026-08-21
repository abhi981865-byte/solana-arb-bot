"""
real_trader.py

⚠️⚠️⚠️ READ THIS BEFORE TOUCHING ANYTHING IN THIS FILE ⚠️⚠️⚠️

This module executes REAL trades with REAL money on Solana mainnet.
It is DISABLED BY DEFAULT and has multiple independent safety gates.
Every gate below must be satisfied or the trade is refused. Do not
remove or bypass any gate "just to test" — that is exactly how real
money gets lost by accident.

WHAT THIS DOES NOT DO (on purpose, for now):
- No automatic key generation or key storage in code — the private key
  must come from an environment variable / GitHub secret, never hardcoded,
  never logged, never committed.
- No MEV/front-running protection (e.g. Jito bundles) — this is a real gap.
  Without it, real trades are highly likely to get front-run by faster,
  better-resourced bots. This is a known limitation, not an oversight.
- No unlimited trading — hard daily loss cap and per-trade cap enforced
  in code, independent of whatever the strategy "wants" to do.

BEFORE ENABLING LIVE TRADING:
1. Run paper trading for at least 2-4 weeks. Look at data/state.json.
   If it's not consistently profitable there (after realistic fill-failure
   simulation), it will not be profitable with real money and real
   competition either.
2. Fund a wallet with ONLY the amount you are fully prepared to lose.
   Never your main wallet, never savings.
3. Set the environment variables below via GitHub Actions secrets:
   - SOLANA_PRIVATE_KEY (base58-encoded, from a dedicated trading wallet)
   - ENABLE_LIVE_TRADING=true (this file refuses to trade otherwise)
   - MAX_TRADE_SIZE_USD (hard per-trade cap, e.g. "10")
   - MAX_DAILY_LOSS_USD (hard daily stop, e.g. "20")
4. The first live trade will be a manual confirmation trade only
   (see FIRST_TRADE_CONFIRMATION_USD) — small, so you can verify the
   whole pipeline actually works before trusting it with more.
"""

import os
import json
from datetime import datetime, timezone, date

STATE_PATH = os.path.join(os.path.dirname(__file__), "data", "live_state.json")

# --- Hard safety gates (all must pass) ---
ENABLE_LIVE_TRADING = os.environ.get("ENABLE_LIVE_TRADING", "false").lower() == "true"
MAX_TRADE_SIZE_USD = float(os.environ.get("MAX_TRADE_SIZE_USD") or "10")
MAX_DAILY_LOSS_USD = float(os.environ.get("MAX_DAILY_LOSS_USD") or "20")
FIRST_TRADE_CONFIRMATION_USD = 5.0  # the very first live trade ever is capped here, regardless of other settings


def load_live_state():
    if not os.path.exists(STATE_PATH):
        return {
            "has_ever_traded_live": False,
            "trades": [],
            "daily_loss_tracker": {"date": str(date.today()), "loss_usd": 0.0},
        }
    with open(STATE_PATH, "r") as f:
        return json.load(f)


def save_live_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def _reset_daily_tracker_if_new_day(state):
    today = str(date.today())
    if state["daily_loss_tracker"]["date"] != today:
        state["daily_loss_tracker"] = {"date": today, "loss_usd": 0.0}


def check_safety_gates(opportunity, state):
    """
    Returns (allowed: bool, reason: str). Every gate is checked explicitly
    and logged — if this refuses a trade, the reason is always visible,
    never a silent no-op.
    """
    if not ENABLE_LIVE_TRADING:
        return False, "ENABLE_LIVE_TRADING is not set to true — live trading is OFF."

    if not os.environ.get("SOLANA_PRIVATE_KEY"):
        return False, "SOLANA_PRIVATE_KEY not set — refusing to trade without wallet credentials."

    _reset_daily_tracker_if_new_day(state)

    if state["daily_loss_tracker"]["loss_usd"] >= MAX_DAILY_LOSS_USD:
        return False, (f"Daily loss cap reached (${state['daily_loss_tracker']['loss_usd']:.2f} >= "
                        f"${MAX_DAILY_LOSS_USD}). No more live trades today.")

    trade_size = opportunity["trade_size_usd"]

    if not state["has_ever_traded_live"]:
        if trade_size > FIRST_TRADE_CONFIRMATION_USD:
            trade_size = FIRST_TRADE_CONFIRMATION_USD  # force-cap the very first trade
        return True, f"FIRST LIVE TRADE — capped to ${trade_size} for confirmation."

    if trade_size > MAX_TRADE_SIZE_USD:
        return False, f"Trade size ${trade_size} exceeds MAX_TRADE_SIZE_USD (${MAX_TRADE_SIZE_USD})."

    return True, "All safety gates passed."


def execute_real_trade(opportunity):
    """
    Placeholder for actual on-chain execution.

    NOT IMPLEMENTED: real swap execution via solana-py / Jupiter swap API.
    This intentionally stops short of wiring up actual transaction signing
    and broadcasting. That is a significant, security-sensitive step
    (handling private keys, building versioned transactions, simulating
    before sending, handling partial fills and retries) that should be
    added deliberately — and reviewed carefully — once paper trading has
    proven the strategy, not bundled in as "one more feature."

    When you're ready for this step, the pieces you'd add here are:
    1. Load keypair from SOLANA_PRIVATE_KEY (never print/log it)
    2. Call Jupiter's /swap endpoint with the quote from price_scanner
    3. Sign and send the transaction via solana-py, with a simulate-first check
    4. Confirm the transaction landed, parse the actual fill price
    5. Record the REAL result (not the quoted estimate) to live_state.json
    """
    raise NotImplementedError(
        "Real execution is not implemented yet. This is deliberate — "
        "wire this up only after paper trading has validated the strategy "
        "and you've reviewed the security implications of automated wallet access."
    )


def process_real_opportunity(opportunity):
    """
    Entry point main.py would call. Checks every gate; only calls
    execute_real_trade if everything passes.
    """
    state = load_live_state()
    allowed, reason = check_safety_gates(opportunity, state)

    print(f"[real_trader] Safety check: {'PASS' if allowed else 'BLOCKED'} — {reason}")

    if not allowed:
        return {"executed": False, "reason": reason}

    # Even when gates pass, execution itself is not implemented yet (see above).
    try:
        result = execute_real_trade(opportunity)
        return {"executed": True, "result": result}
    except NotImplementedError as e:
        return {"executed": False, "reason": str(e)}
