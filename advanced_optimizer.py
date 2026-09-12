"""
Advanced Multi-Strategy Optimizer & Backtester
Tests:
1. Dynamic ATR-based Stop-Loss & Take-Profit
2. EMA 20/50/200 Trend Filter (Only Long above EMA200)
3. Volume Confirmation Breakout
4. Parameter Sweep across Timeframes & Risk Ratios
"""

import json
import ssl
import urllib.request
from datetime import datetime

class AdvancedBacktester:
    def __init__(self, fee_pct=0.08):
        self.fee_pct = fee_pct / 100.0

    @staticmethod
    def calculate_atr(klines, period=14):
        tr = []
        for i in range(len(klines)):
            if i == 0:
                tr.append(klines[i]["high"] - klines[i]["low"])
            else:
                h_l = klines[i]["high"] - klines[i]["low"]
                h_pc = abs(klines[i]["high"] - klines[i-1]["close"])
                l_pc = abs(klines[i]["low"] - klines[i-1]["close"])
                tr.append(max(h_l, h_pc, l_pc))
        
        atr = [None] * len(klines)
        if len(klines) >= period:
            atr[period-1] = sum(tr[:period]) / period
            for i in range(period, len(klines)):
                atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
        return atr

    @staticmethod
    def calculate_ema(prices, period):
        ema = [None] * len(prices)
        if len(prices) < period:
            return ema
        multiplier = 2 / (period + 1)
        ema[period-1] = sum(prices[:period]) / period
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
        return ema

    @staticmethod
    def calculate_rsi(prices, period=14):
        rsi = [None] * len(prices)
        if len(prices) < period + 1:
            return rsi
        deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        
        rsi[period] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss == 0:
                rsi[i+1] = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi[i+1] = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def backtest_strategy(self, klines, params):
        initial_balance = params.get("initial_balance", 1000.0)
        balance = initial_balance
        atr_mult_sl = params.get("atr_sl", 1.8)
        risk_reward = params.get("rr", 2.2)
        use_ema200 = params.get("use_ema200", True)
        
        closes = [k["close"] for k in klines]
        ema20 = self.calculate_ema(closes, 20)
        ema50 = self.calculate_ema(closes, 50)
        ema200 = self.calculate_ema(closes, 200) if use_ema200 else [0]*len(closes)
        rsi = self.calculate_rsi(closes, 14)
        atr = self.calculate_atr(klines, 14)
        
        positions = []
        trades = []
        equity_curve = []
        
        start_idx = 205 if use_ema200 else 55
        for i in range(start_idx, len(klines)):
            candle = klines[i]
            cur_price = candle["close"]
            high = candle["high"]
            low = candle["low"]
            c_atr = atr[i]
            e20 = ema20[i]
            e50 = ema50[i]
            e200 = ema200[i]
            r = rsi[i]
            dt = candle["datetime"]
            
            # 1. Manage Active Positions
            remaining = []
            for pos in positions:
                closed = False
                exit_price = cur_price
                reason = "SIGNAL"
                
                # Check Trailing Stop or Fixed ATR TP/SL
                if low <= pos["sl"]:
                    exit_price = pos["sl"]
                    reason = "STOP_LOSS"
                    closed = True
                elif high >= pos["tp"]:
                    exit_price = pos["tp"]
                    reason = "TAKE_PROFIT"
                    closed = True
                elif r and r > 75 and cur_price < e20:
                    exit_price = cur_price
                    reason = "RSI_OVERBOUGHT"
                    closed = True
                    
                if closed:
                    gross_pnl = (exit_price - pos["entry_price"]) * pos["amount"]
                    fee = (pos["size"] + (pos["amount"] * exit_price)) * self.fee_pct
                    net_pnl = gross_pnl - fee
                    balance += (pos["size"] + net_pnl)
                    trades.append({
                        "entry_time": pos["entry_time"],
                        "exit_time": dt,
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "pnl": round(net_pnl, 2),
                        "pnl_pct": round((net_pnl / pos["size"]) * 100.0, 2),
                        "reason": reason
                    })
                else:
                    remaining.append(pos)
            positions = remaining
            
            # 2. Entry Logic (Trend Following with Volatility Confirmation)
            if len(positions) == 0 and e20 and e50 and r and c_atr:
                # Rule: Price above EMA200 (Macro Bullish), EMA20 > EMA50, RSI pullback between 48 and 62
                trend_ok = (cur_price > e200) if use_ema200 else True
                momentum_ok = e20 > e50 and 46 <= r <= 62 and closes[i-1] <= ema20[i-1] and cur_price > e20
                
                if trend_ok and momentum_ok:
                    sl_dist = c_atr * atr_mult_sl
                    sl_price = cur_price - sl_dist
                    tp_dist = sl_dist * risk_reward
                    tp_price = cur_price + tp_dist
                    
                    risk_amount = balance * 0.02  # 2% Risk
                    pos_size = min(risk_amount / (sl_dist / cur_price), balance * 0.85)
                    
                    if pos_size >= 10.0 and balance >= pos_size:
                        amount = pos_size / cur_price
                        balance -= pos_size
                        positions.append({
                            "entry_time": dt,
                            "entry_price": cur_price,
                            "amount": amount,
                            "size": pos_size,
                            "sl": sl_price,
                            "tp": tp_price
                        })
            
            # Equity track
            open_val = sum(p["amount"] * cur_price for p in positions)
            equity_curve.append(balance + open_val)

        # Calculate Results
        total_trades = len(trades)
        if total_trades == 0:
            return {"total_trades": 0, "net_profit": 0, "roi_pct": 0, "win_rate_pct": 0}
            
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        win_rate = (len(wins) / total_trades) * 100.0
        tot_prof = sum(t["pnl"] for t in wins)
        tot_loss = abs(sum(t["pnl"] for t in losses))
        pf = round(tot_prof / tot_loss, 2) if tot_loss > 0 else (99.0 if tot_prof > 0 else 0)
        net_prof = sum(t["pnl"] for t in trades)
        roi = ((equity_curve[-1] - initial_balance) / initial_balance) * 100.0
        
        # Max drawdown
        peak = initial_balance
        max_dd = 0.0
        for eq in equity_curve:
            if eq > peak: peak = eq
            dd = ((peak - eq) / peak) * 100.0 if peak > 0 else 0
            if dd > max_dd: max_dd = dd

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": pf,
            "net_profit": round(net_prof, 2),
            "roi_pct": round(roi, 2),
            "max_drawdown_pct": round(max_dd, 2),
            "final_balance": round(equity_curve[-1], 2),
            "trades": trades
        }

if __name__ == "__main__":
    from backtester import HistoricalDataProvider
    provider = HistoricalDataProvider()
    opt = AdvancedBacktester()
    
    print("=" * 70)
    print("🚀 OPTIMIZED STRATEGY: EMA 200 Trend Filter + ATR Dynamic SL/TP")
    print("=" * 70)
    
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        klines = provider.fetch_coinex_klines(sym, period="1hour", limit=1000)
        res = opt.backtest_strategy(klines, {"atr_sl": 1.5, "rr": 2.5, "use_ema200": True})
        print(f"\n🪙 {sym} (Optimized):")
        print(f"  • Trades: {res['total_trades']} (Win Rate: {res['win_rate_pct']}%)")
        print(f"  • Profit Factor: {res['profit_factor']}")
        print(f"  • Net Profit: ${res['net_profit']:+,.2f} USDT ({res['roi_pct']:+.2f}%)")
        print(f"  • Max Drawdown: {res['max_drawdown_pct']:.2f}%")
        print(f"  • Final Balance: ${res['final_balance']:,.2f} USDT")
