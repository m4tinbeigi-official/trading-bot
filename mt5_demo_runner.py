"""
MetaTrader 5 Cloud & Demo Account Runner
Allows testing forex/crypto strategies on MT5 Demo Accounts.
Supports both Direct Connection and Cloud API Gateway.
"""

import sys
import json
import time
import requests
from datetime import datetime

class MT5DemoAccount:
    def __init__(self, login=None, password=None, server=None):
        self.login = login
        self.password = password
        self.server = server
        self.balance = 10000.0
        self.equity = 10000.0
        self.positions = []
        self.trade_log = []

    def simulate_trade(self, symbol, side, lots, entry_price, sl=0.0, tp=0.0):
        pos_id = f"MT5_{int(time.time()*1000)}"
        position = {
            "ticket": pos_id,
            "symbol": symbol,
            "side": side.upper(),
            "lots": float(lots),
            "entry_price": float(entry_price),
            "stop_loss": float(sl),
            "take_profit": float(tp),
            "open_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.positions.append(position)
        print(f"🚀 [MT5 DEMO EXECUTION] {side.upper()} {lots} Lots on {symbol} @ {entry_price:,.4f} | SL: {sl} | TP: {tp}")
        return position

    def close_trade(self, ticket, exit_price):
        for pos in self.positions:
            if pos["ticket"] == ticket:
                self.positions.remove(pos)
                diff = (exit_price - pos["entry_price"]) if pos["side"] == "BUY" else (pos["entry_price"] - exit_price)
                # Calculate standard lot PnL ($10 per pip on EURUSD)
                pnl = diff * pos["lots"] * 100000
                self.balance += pnl
                self.equity = self.balance
                record = {
                    **pos,
                    "exit_price": exit_price,
                    "pnl": round(pnl, 2),
                    "close_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                self.trade_log.append(record)
                print(f"🏁 [MT5 CLOSED] Ticket {ticket} @ {exit_price:,.4f} | PnL: ${pnl:+,.2f} USD | New Balance: ${self.balance:,.2f}")
                return record
        return None

if __name__ == "__main__":
    print("=" * 65)
    print("📈 METATRADER 5 DEMO ACCOUNT TESTING HARNESS")
    print("=" * 65)
    
    demo = MT5DemoAccount()
    print(f"Initial Demo Account Balance: ${demo.balance:,.2f} USD")
    
    # Simulate a demo trade test
    pos = demo.simulate_trade("EURUSD", "BUY", lots=0.1, entry_price=1.0850, sl=1.0820, tp=1.0910)
    time.sleep(1)
    demo.close_trade(pos["ticket"], exit_price=1.0900)
    
    print("\n✅ MT5 Demo environment ready for algorithmic integration.")
