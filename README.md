# Solana ARB Bot v2.0

## Setup

1. `pip install -r requirements.txt`
2. `cp .env.example .env`
3. `python db_init.py`
4. `python daemon.py`

## Files

- config.py: Configuration
- daemon.py: Main bot loop
- price_scanner.py: Price fetching
- spread_detector.py: Opportunity detection
- paper_trader_v2.py: Trade simulation
