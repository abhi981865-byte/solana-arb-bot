from paper_trader_v2 import PaperTraderDB, get_summary
def print_status():
    db = PaperTraderDB()
    s = get_summary(db)
    print(f'Balance: {s["balance_usd"]} ROI: {s["roi_pct"]}%')
if __name__ == '__main__': print_status()
