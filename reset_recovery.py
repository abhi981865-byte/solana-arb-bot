from paper_trader_v2 import PaperTraderDB
def reset_circuit(): db = PaperTraderDB(); db.set_state('circuit_breaker', 'False'); print('Reset')
if __name__ == '__main__': reset_circuit()
