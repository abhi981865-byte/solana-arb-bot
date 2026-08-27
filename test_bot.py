from config import Config
from paper_trader_v2 import PaperTraderDB
print('Test 1: Config'); assert Config.STARTING_BALANCE_USD > 0; print('PASS')
print('Test 2: DB'); db = PaperTraderDB(); assert db.get_balance() > 0; print('PASS')
print('All tests passed')
