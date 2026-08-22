"""
brain.py

Gives the bot a "brain" — lets you chat with it on Telegram in plain
English/Hindi and ask things like "why did the circuit breaker trip?" or
"how are we doing this week?". Runs as part of the existing 5-minute
scanner cycle: it reads any new messages sent to the bot, handles known
COMMANDS directly (reset, status), and sends everything else to the model
for a conversational answer using the current paper-trading state as
context. Powered by Groq (free, no credit card).

Requires these GitHub Actions secrets:
  - TELEGRAM_BOT_TOKEN   (you already have this)
  - TELEGRAM_CHAT_ID     (you already have this)
  - GROQ_API_KEY         (free key from console.groq.com)
"""

import os
import json
import requests

from paper_trader import reset_circuit_breaker, get_summary

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are the "brain" of a Solana DEX arbitrage PAPER trading bot \
(no real money — this is a learning/validation project). You have access to the \
bot's current state and recent trades below. Answer the user's question clearly, \
in a friendly and direct tone. Use Hindi+English (Hinglish) if the user writes in \
Hinglish, otherwise match their language. Keep answers concise (a few sentences), \
unless they ask for detail. Never claim the bot trades real money — it's paper \
trading only unless the state explicitly says otherwise. If asked for financial \
advice, note you can explain what's happening but can't tell them what to do with \
real money."""

# --- Known commands: these bypass the LLM entirely and act directly on the bot ---
# Match is case-insensitive and ignores a leading "/". Add more here as needed.
RESET_COMMANDS = {"reset", "resume", "unpause"}
STATUS_COMMANDS = {"status", "balance", "summary"}


def fetch_new_messages(last_update_id: int) -> list:
    """Poll Telegram for any messages sent since the last processed update."""
    if not TELEGRAM_BOT_TOKEN:
        return []
    resp = requests.get(
        f"{TELEGRAM_API}/getUpdates",
        params={"offset": last_update_id + 1, "timeout": 5},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
        timeout=15,
    )


def build_context(state: dict, summary: dict) -> str:
    """Turns the bot's current state into a compact text block the model can read."""
    recent_trades = state.get("trades", [])[-10:]
    return (
        f"CURRENT SUMMARY:\n{json.dumps(summary, indent=2)}\n\n"
        f"LAST 10 TRADES:\n{json.dumps(recent_trades, indent=2)}"
    )


def ask_brain(question: str, context: str) -> str:
    if not GROQ_API_KEY:
        return "Brain abhi set up nahi hai — GROQ_API_KEY secret add karo GitHub mein."

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"BOT STATE CONTEXT:\n{context}\n\nUSER QUESTION:\n{question}",
                },
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def try_handle_command(state: dict, text: str) -> str | None:
    """
    Checks if the message is a known command and, if so, executes it directly
    and returns the reply text. Returns None if the message isn't a command
    (in which case the caller should fall through to the LLM).
    """
    normalized = text.strip().lower().lstrip("/")

    if normalized in RESET_COMMANDS:
        if not state.get("circuit_breaker_tripped"):
            return "Circuit breaker already OFF hai — bot normally chal raha hai, reset karne ki zaroorat nahi thi."
        reset_circuit_breaker(state)  # this also saves state internally
        return "✅ Circuit breaker reset kar diya. Bot agle scheduled run se phir se scan/trade karega."

    if normalized in STATUS_COMMANDS:
        summary = get_summary(state)
        breaker = "🔴 TRIPPED (paused)" if summary["circuit_breaker_tripped"] else "🟢 OK (running)"
        return (
            f"📊 Status:\n"
            f"Balance: ${summary['balance_usd']}\n"
            f"Total trades: {summary['total_trades']}\n"
            f"Total profit: ${summary['total_profit_usd']}\n"
            f"ROI: {summary['roi_pct']}%\n"
            f"Circuit breaker: {breaker}"
        )

    return None  # not a command — let the LLM handle it


def handle_telegram_messages(state: dict, summary: dict) -> dict:
    """
    Checks for new Telegram messages. Known commands (reset, status, etc.)
    are executed directly; everything else is answered by the LLM using the
    current state as context. Returns the updated state (with
    telegram_last_update_id bumped forward, and possibly circuit breaker
    reset if that command was used).
    """
    last_update_id = state.get("telegram_last_update_id", 0)
    context = build_context(state, summary)

    try:
        updates = fetch_new_messages(last_update_id)
    except requests.RequestException as e:
        print(f"[brain] Failed to fetch Telegram messages: {e}")
        return state

    for update in updates:
        state["telegram_last_update_id"] = update["update_id"]
        message = update.get("message", {})
        text = message.get("text", "").strip()
        if not text:
            continue

        command_reply = try_handle_command(state, text)
        if command_reply is not None:
            send_telegram_message(command_reply)
            continue

        try:
            answer = ask_brain(text, context)
        except requests.RequestException as e:
            answer = f"Brain se jawab lene mein error aa gaya: {e}"

        send_telegram_message(answer)

    return state
