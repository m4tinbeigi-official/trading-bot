"""
Multi-Strategy Grid Engine:
1. Mean Reversion with Bollinger Bands + RSI Divergence
2. SuperTrend Dynamic Trailing System
3. Parameter Auto-Tuning to find high Sharpe/Profit setups
"""

import math
from backtester import HistoricalDataProvider

class MultiStrategySearch:
    @staticmethod
    def calculate_bollinger_bands(prices, period=20, num_std=2.0):
        upper = [None] * len(prices)
        lower = [None] * len(prices)
        sma = [None] * len(prices)
        
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1 : i + 1]
            avg = sum(window) / period
            variance = sum((x - avg) ** 2 for x in window) / period
            std = math.sqrt(variance)
            sma[i] = avg
            upper[i] = avg + (num_std * std)
            lower[i] = avg - (num_std * std)
        return sma, upper, lower

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
                rsi[i+1] = 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
        return rsi

    def test_bollinger_mean_reversion(self, klines, rsi_oversold=30, bb_std=2.0, tp_ratio=1.5, sl_pct=2.0):
        closes = [k["close"] for k in klines]
        highs = [k["high"] for k in klines]
        lows = [k["low"] for k in klines]
        sma, upper, lower = self.calculate_bollinger_bands(closes, 20, bb_std)
        rsi = self.calculate_rsi(closes, 14)
        
        balance = 1000.0
        positions = []
        trades = []
        fee = 0.0008  # 0.08%
        
        for i in range(25, len(klines)):
            c = closes[i]
            h = highs[i]
            l = lows[i]
            r = rsi[i]
            low_b = lower[i]
            mid_b = sma[i]
            
            # Manage Open Pos
            rem = []
            for pos in positions:
                closed = False
                exit_price = c
                
                # Take profit at middle or upper band or fixed TP
                if h >= pos["tp"]:
                    exit_price = pos["tp"]
                    closed = True
                elif l <= pos["sl"]:
                    exit_price = pos["sl"]
                    closed = True
                elif c >= mid_b and r and r > 55:
                    exit_price = c
                    closed = True
                    
                if closed:
                    pnl = (exit_price - pos["entry"]) * pos["amount"] - (pos["size"] + (pos["amount"] * exit_price)) * fee
                    balance += (pos["size"] + pnl)
                    trades.append(pnl)
                else:
                    rem.append(pos)
            positions = rem
            
            # Entry: Price pierces lower BB and RSI oversold
            if len(positions) == 0 and low_b and r:
                if l <= low_b and r <= rsi_oversold:
                    entry = c
                    sl = entry * (1 - sl_pct / 100.0)
                    tp = entry * (1 + (sl_pct * tp_ratio) / 100.0)
                    size = balance * 0.4
                    amount = size / entry
                    balance -= size
                    positions.append({"entry": entry, "amount": amount, "size": size, "sl": sl, "tp": tp})
                    
        total_pnl = sum(trades)
        wins = [t for t in trades if t > 0]
        winrate = (len(wins) / len(trades) * 100.0) if trades else 0
        return {
            "trades_count": len(trades),
            "win_rate": round(winrate, 1),
            "pnl": round(total_pnl, 2),
            "final_balance": round(balance + sum(p["amount"]*closes[-1] for p in positions), 2)
        }

if __name__ == "__main__":
    provider = HistoricalDataProvider()
    tester = MultiStrategySearch()
    
    print("=" * 70)
    print("⚡ BOLINGER BANDS + RSI MEAN REVERSION BACKTEST (1-HOUR CANDLES)")
    print("=" * 70)
    
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        klines = provider.fetch_coinex_klines(sym, period="1hour", limit=1000)
        # Test multiple settings
        print(f"\n🔍 Tuning {sym}...")
        for rsi_thresh in [28, 32, 35]:
            for bb_std in [2.0, 2.2]:
                for tp_ratio in [1.5, 2.0]:
                    res = tester.test_bollinger_mean_reversion(klines, rsi_oversold=rsi_thresh, bb_std=bb_std, tp_ratio=tp_ratio, sl_pct=2.0)
                    if res["trades_count"] >= 5 and res["pnl"] > 0:
                        print(f"  ✅ [PROFITABLE] RSI<={rsi_thresh}, BB={bb_std}, TP_Ratio={tp_ratio} -> Trades: {res['trades_count']}, WinRate: {res['win_rate']}%, PnL: ${res['pnl']:+,.2f} (Bal: ${res['final_balance']})")
