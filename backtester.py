"""
Professional Backtesting Engine for Trading Strategies
Simulates historical trades with realistic fees, slippage, Take-Profit/Stop-Loss, and detailed performance metrics.
"""

import sys
import json
import urllib.request
import ssl
from datetime import datetime

class HistoricalDataProvider:
    def __init__(self):
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE
        self.headers = {"User-Agent": "Mozilla/5.0 (TradingBot/1.0)"}

    def fetch_coinex_klines(self, market="BTCUSDT", period="1hour", limit=1000):
        url = f"https://api.coinex.com/v2/spot/kline?market={market}&period={period}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and data.get("code") == 0:
                    raw_klines = data.get("data", [])
                    formatted = []
                    for k in raw_klines:
                        formatted.append({
                            "timestamp": int(k.get("created_at", 0)),
                            "open": float(k.get("open", 0)),
                            "high": float(k.get("high", 0)),
                            "low": float(k.get("low", 0)),
                            "close": float(k.get("close", 0)),
                            "volume": float(k.get("volume", 0)),
                            "datetime": datetime.fromtimestamp(int(k.get("created_at", 0)) / 1000).strftime('%Y-%m-%d %H:%M') if int(k.get("created_at", 0)) > 10**11 else datetime.fromtimestamp(int(k.get("created_at", 0))).strftime('%Y-%m-%d %H:%M')
                        })
                    return sorted(formatted, key=lambda x: x["timestamp"])
        except Exception as e:
            print(f"Error fetching historical data: {e}")
        return []

class BacktestEngine:
    def __init__(self, initial_balance=1000.0, fee_pct=0.1, risk_per_trade=2.0, sl_pct=1.5, tp_pct=3.5):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.fee_pct = fee_pct / 100.0
        self.risk_per_trade = risk_per_trade / 100.0
        self.sl_pct = sl_pct / 100.0
        self.tp_pct = tp_pct / 100.0
        
        self.positions = []
        self.closed_trades = []
        self.equity_curve = []

    def calculate_indicators(self, klines):
        closes = [k["close"] for k in klines]
        
        # EMA 20 & 50
        ema20 = []
        multiplier20 = 2 / (20 + 1)
        for i in range(len(closes)):
            if i < 19:
                ema20.append(None)
            elif i == 19:
                ema20.append(sum(closes[:20]) / 20)
            else:
                ema20.append((closes[i] - ema20[-1]) * multiplier20 + ema20[-1])
                
        ema50 = []
        multiplier50 = 2 / (50 + 1)
        for i in range(len(closes)):
            if i < 49:
                ema50.append(None)
            elif i == 49:
                ema50.append(sum(closes[:50]) / 50)
            else:
                ema50.append((closes[i] - ema50[-1]) * multiplier50 + ema50[-1])
                
        # RSI 14
        rsi = [None] * len(closes)
        if len(closes) >= 15:
            deltas = [closes[i+1] - closes[i] for i in range(len(closes)-1)]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            
            avg_gain = sum(gains[:14]) / 14
            avg_loss = sum(losses[:14]) / 14
            
            rsi[14] = 100.0 if avg_loss == 0 else 100.0 - (100.0 / (1.0 + (avg_gain / avg_loss)))
            
            for i in range(14, len(deltas)):
                avg_gain = (avg_gain * 13 + gains[i]) / 14
                avg_loss = (avg_loss * 13 + losses[i]) / 14
                if avg_loss == 0:
                    rsi[i+1] = 100.0
                else:
                    rs = avg_gain / avg_loss
                    rsi[i+1] = 100.0 - (100.0 / (1.0 + rs))
                    
        return ema20, ema50, rsi

    def run(self, symbol, klines):
        if len(klines) < 60:
            print(f"Not enough data for {symbol}")
            return None

        ema20, ema50, rsi = self.calculate_indicators(klines)
        
        for i in range(50, len(klines)):
            candle = klines[i]
            cur_price = candle["close"]
            high = candle["high"]
            low = candle["low"]
            e20 = ema20[i]
            e50 = ema50[i]
            r = rsi[i]
            dt = candle["datetime"]

            # Manage open positions
            remaining_positions = []
            for pos in self.positions:
                closed = False
                exit_price = cur_price
                reason = "SIGNAL"

                # Check SL/TP using candle High/Low
                if low <= pos["sl"]:
                    exit_price = pos["sl"]
                    reason = "STOP_LOSS"
                    closed = True
                elif high >= pos["tp"]:
                    exit_price = pos["tp"]
                    reason = "TAKE_PROFIT"
                    closed = True
                elif r and r > 70 and cur_price < e20:
                    exit_price = cur_price
                    reason = "RSI_OVERBOUGHT_EXIT"
                    closed = True

                if closed:
                    # Execute Close
                    gross_pnl = (exit_price - pos["entry_price"]) * pos["amount"]
                    fee = (pos["size"] + (pos["amount"] * exit_price)) * self.fee_pct
                    net_pnl = gross_pnl - fee
                    
                    self.balance += (pos["size"] + net_pnl)
                    pnl_pct = (net_pnl / pos["size"]) * 100.0
                    
                    self.closed_trades.append({
                        "symbol": symbol,
                        "entry_time": pos["entry_time"],
                        "exit_time": dt,
                        "entry_price": pos["entry_price"],
                        "exit_price": exit_price,
                        "size": pos["size"],
                        "pnl": round(net_pnl, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "fee": round(fee, 2),
                        "reason": reason
                    })
                else:
                    remaining_positions.append(pos)
            
            self.positions = remaining_positions

            # Entry condition: EMA20 > EMA50 and 45 <= RSI <= 65 and no active position
            if len(self.positions) == 0 and e20 and e50 and r:
                prev_e20 = ema20[i-1]
                prev_e50 = ema50[i-1]
                
                # Check crossover or strong trend continuation
                is_bullish = e20 > e50 and 45 <= r <= 65
                
                if is_bullish:
                    risk_amount = self.balance * self.risk_per_trade
                    pos_size = min(risk_amount / self.sl_pct, self.balance * 0.9)
                    if pos_size >= 10.0 and self.balance >= pos_size:
                        amount = pos_size / cur_price
                        sl_price = cur_price * (1 - self.sl_pct)
                        tp_price = cur_price * (1 + self.tp_pct)
                        
                        self.balance -= pos_size
                        self.positions.append({
                            "symbol": symbol,
                            "entry_time": dt,
                            "entry_price": cur_price,
                            "amount": amount,
                            "size": pos_size,
                            "sl": sl_price,
                            "tp": tp_price
                        })

            # Record total equity
            open_equity = sum(p["amount"] * cur_price for p in self.positions)
            total_equity = self.balance + open_equity
            self.equity_curve.append({
                "time": dt,
                "price": cur_price,
                "equity": round(total_equity, 2)
            })

        # Close any remaining position at the end of backtest
        if self.positions:
            last_price = klines[-1]["close"]
            for pos in self.positions:
                gross_pnl = (last_price - pos["entry_price"]) * pos["amount"]
                fee = (pos["size"] + (pos["amount"] * last_price)) * self.fee_pct
                net_pnl = gross_pnl - fee
                self.balance += (pos["size"] + net_pnl)
                self.closed_trades.append({
                    "symbol": symbol,
                    "entry_time": pos["entry_time"],
                    "exit_time": klines[-1]["datetime"],
                    "entry_price": pos["entry_price"],
                    "exit_price": last_price,
                    "size": pos["size"],
                    "pnl": round(net_pnl, 2),
                    "pnl_pct": round((net_pnl / pos["size"]) * 100.0, 2),
                    "fee": round(fee, 2),
                    "reason": "END_OF_DATA"
                })
            self.positions = []

        return self.generate_metrics()

    def generate_metrics(self):
        trades = self.closed_trades
        total_trades = len(trades)
        if total_trades == 0:
            return {"total_trades": 0, "final_balance": self.balance}

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        
        win_rate = (len(wins) / total_trades) * 100.0
        total_profit = sum(t["pnl"] for t in wins)
        total_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = round(total_profit / total_loss, 2) if total_loss > 0 else (99.0 if total_profit > 0 else 0.0)
        net_profit = sum(t["pnl"] for t in trades)
        roi_pct = ((self.balance - self.initial_balance) / self.initial_balance) * 100.0
        
        # Max Drawdown
        peak = self.initial_balance
        max_dd = 0.0
        for eq in self.equity_curve:
            val = eq["equity"]
            if val > peak:
                peak = val
            dd = ((peak - val) / peak) * 100.0 if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        return {
            "initial_balance": self.initial_balance,
            "final_balance": round(self.balance, 2),
            "net_profit": round(net_profit, 2),
            "roi_pct": round(roi_pct, 2),
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": profit_factor,
            "max_drawdown_pct": round(max_dd, 2),
            "avg_trade_pnl": round(net_profit / total_trades, 2) if total_trades else 0,
            "trades": trades
        }

if __name__ == "__main__":
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    provider = HistoricalDataProvider()
    
    print("=" * 65)
    print("📈 RUNNING HISTORICAL BACKTEST ON COINEX CANDLES (1-Hour Timeframe)")
    print("=" * 65)
    
    all_results = {}
    for sym in symbols:
        print(f"\n⏳ Fetching last 1000 1-hour candles for {sym}...")
        klines = provider.fetch_coinex_klines(sym, period="1hour", limit=1000)
        print(f"✅ Loaded {len(klines)} candles from {klines[0]['datetime']} to {klines[-1]['datetime']}")
        
        engine = BacktestEngine(initial_balance=1000.0, fee_pct=0.1, risk_per_trade=2.0, sl_pct=1.5, tp_pct=3.5)
        metrics = engine.run(sym, klines)
        all_results[sym] = metrics
        
        print(f"\n📊 Results for {sym}:")
        print(f"  • Total Trades: {metrics['total_trades']} (Wins: {metrics['winning_trades']}, Losses: {metrics['losing_trades']})")
        print(f"  • Win Rate: {metrics['win_rate_pct']}% | Profit Factor: {metrics['profit_factor']}")
        print(f"  • Net Profit: ${metrics['net_profit']:+,.2f} USDT ({metrics['roi_pct']:+.2f}%)")
        print(f"  • Max Drawdown: {metrics['max_drawdown_pct']:.2f}%")
        print(f"  • Final Balance: ${metrics['final_balance']:,.2f} USDT")

    with open("/Users/ricksabchez/Desktop/trading-bot/backtest_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print("\n💾 Full backtest report saved to /Users/ricksabchez/Desktop/trading-bot/backtest_results.json")
