import time
from config import Config
from paper_trader_v2 import PaperTraderDB, get_summary
print('Bot Daemon Started')
db = PaperTraderDB()
for i in range(3): print(f'Scan {i+1}'); time.sleep(Config.POLL_INTERVAL_SECONDS)
