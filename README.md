# Solana Arbitrage Bot

**⚠️ PAPER TRADING BY DEFAULT.** Real trading exists as a module
(`real_trader.py`) but is off unless you explicitly configure it — see
"Going live" at the bottom. Read that section fully before touching it.

## What it does
- Every 5 minutes: checks SOL/USDC, SOL/USDT, USDC/USDT, BONK/USDC,
  JUP/USDC, WIF/USDC prices across Raydium, Orca, Meteora (via Jupiter's
  free `lite-api.jup.ag` endpoint)
- Detects arbitrage spreads that are still profitable after estimated fees,
  slippage, and a realistic **35% simulated fill-failure rate** (real
  arbitrage often loses the opportunity to faster bots — pretending
  otherwise would give you fake confidence)
- Tests each opportunity at three trade sizes ($50/$100/$500) to see if the
  edge survives at larger size or only exists for tiny trades
- Tracks API latency per scan, so you can tell if you're too slow to
  realistically compete
- **Circuit breaker**: after 3 consecutive losing/failed trades, the bot
  pauses itself and messages you — it will NOT auto-resume, you have to
  reset it manually after reviewing what happened
- Sends Telegram alerts per trade, a daily summary, and a **weekly
  deep-dive report** (best/worst trade, per-pair breakdown)
- A **live dashboard** (GitHub Pages) shows balance, ROI, fill success
  rate, and recent trade history — viewable from your phone anytime
- Tracks a fake $1000 starting balance; all history in `data/state.json`

## One-time setup (from your phone)

### 1. Create a GitHub repo
Create a new **private** repo (e.g. `solana-arb-bot`), upload all these
files preserving folder structure (GitHub mobile app or web uploader).

### 2. Create a Telegram bot
1. Message **@BotFather** on Telegram → `/newbot` → get a **bot token**
2. Send any message to your new bot
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
   → find `"chat":{"id": ...}` → that's your **chat ID**

### 3. Add secrets to GitHub
Repo → **Settings → Secrets and variables → Actions → New repository secret**:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### 4. Enable Actions and GitHub Pages
- **Actions tab** → enable workflows if prompted
- **Settings → Pages** → Source: "Deploy from a branch" → Branch: `main`,
  folder: `/docs` → Save. Your dashboard will be live at
  `https://<your-username>.github.io/<repo-name>/` within a few minutes

### 5. Test it manually
Actions tab → "Solana Arb Paper Trading Scanner" → **Run workflow**.
Check Telegram for a message, and check the dashboard URL.

## Checking results
- **Telegram**: per-trade alerts, daily summary (9 AM IST), weekly report
  (Monday 9:15 AM IST)
- **Dashboard**: balance, ROI, fill success rate, recent trades — bookmark
  the Pages URL on your phone
- **`data/state.json`**: raw data, viewable in the GitHub mobile app

## If something breaks
Every run is wrapped in error handling, so failures are never silent:
- **One or two pairs fail** (e.g. temporary API hiccup) → logged as a
  warning, bot continues with the rest, no alert spam
- **All pairs fail** (Jupiter API down, or their request format changed) →
  Telegram alert "🔴 Scanner Error", run exits cleanly
- **Anything else crashes** (unexpected bug) → Telegram alert "🔴 Bot
  Crashed" with the error, AND the GitHub Actions run shows as failed
  (red ❌ in the Actions tab) so you'll notice even without checking
  Telegram — check that tab's logs for the full error detail

## If the circuit breaker trips
You'll get a Telegram message saying so. The bot will keep sending
"still paused" messages every 5 minutes until you reset it. To reset,
run this once (e.g. via GitHub Codespaces, or ask Claude to do it and
push the change):
```python
from paper_trader import load_state, reset_circuit_breaker
state = load_state()
reset_circuit_breaker(state)
```
Look at the last few trades in `data/state.json` first — understand why
it tripped before resetting, don't just reset reflexively.

## Tuning
- `spread_detector.py` — `SWAP_FEE_PCT`, `SLIPPAGE_BUFFER_PCT`,
  `TEST_TRADE_SIZES_USD`
- `paper_trader.py` — `STARTING_BALANCE_USD`, `MAX_TRADE_PCT_OF_BALANCE`,
  `FILL_FAILURE_RATE`, `PARTIAL_FILL_RATE`,
  `CIRCUIT_BREAKER_CONSECUTIVE_LOSSES`
- `main.py` — `TRADE_SIZE_USD`
- `price_scanner.py` — `PAIRS`, `DEXES`

## Known limitations (read before trusting results)
- Uses Jupiter's free `lite-api.jup.ag` endpoint (no API key needed). If
  Jupiter fully retires this tier, switch `JUPITER_QUOTE_URL` in
  `price_scanner.py` to `https://api.jup.ag/swap/v1/quote` and get a free
  API key from https://portal.jup.ag (send as `x-api-key` header)
- DEX filter labels (`"Raydium"`, `"Orca Whirlpool"`, `"Meteora DLMM"`) were
  verified against Jupiter's `/program-id-to-label` endpoint — if quotes
  start silently returning empty for one DEX, Jupiter may have renamed it;
  recheck that endpoint
- The 35% fill-failure rate is an *estimate*, not measured from real data —
  treat paper trading results as directional, not a guarantee
- Real arbitrage bots compete against well-funded, low-latency
  infrastructure (co-located servers, MEV bundles). A GitHub Actions
  cron job running every 5 minutes is not fast enough to reliably win
  against them — expect this to mostly show "no opportunity" or "failed
  fill" in practice. That's realistic, not a bug.
- If the bot crashes for any reason (API format change, network issue,
  bug), you'll get a Telegram alert AND the GitHub Actions run will show
  as failed (red X) in the Actions tab — check there for the full error

## Going live (real money) — read this fully first

`real_trader.py` exists but does **not** execute real trades — calling it
always raises `NotImplementedError` on purpose. Enabling real trading
requires:

1. **Weeks of paper trading first.** If `data/state.json` doesn't show
   consistent profit after the realistic failure simulation, real money
   will do worse, not better.
2. **A dedicated wallet** funded with only what you can fully afford to
   lose. Never your main wallet.
3. **GitHub secrets**: `ENABLE_LIVE_TRADING=true`, `SOLANA_PRIVATE_KEY`,
   `MAX_TRADE_SIZE_USD`, `MAX_DAILY_LOSS_USD` — all required, all
   independently enforced in code.
4. **Implementing `execute_real_trade()` yourself (with help)** — signing
   and broadcasting real transactions via solana-py. This is the
   security-sensitive part and is left unimplemented deliberately, so it
   only gets built once you're actually ready, not by accident.
5. Even once implemented, the **first live trade is hard-capped at $5**
   regardless of other settings, purely to confirm the pipeline works
   before trusting it with more.

There is currently **no MEV/front-running protection** (e.g. Jito
bundles). Without it, real trades are likely to lose the race to faster
bots more often than paper trading suggests. This is a real gap to solve
before scaling up real capital, not just a nice-to-have.
