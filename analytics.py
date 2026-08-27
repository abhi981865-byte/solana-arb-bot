from paper_trader_v2 import PaperTraderDB, get_summary
def summary(): db = PaperTraderDB(); s = get_summary(db); print(f'Summary: {s}')
if __name__ == '__main__': summary()
