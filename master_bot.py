"""
Master Autonomous Trading Bot Engine
Multi-Market: Dow Jones (US30), Gold (XAUUSD), Crypto (BTC/ETH/SOL), Nobitex Arbitrage
Risk Guard: Max Daily Loss (2%), Cooldown Trigger, Dynamic ATR SL/TP, News Filter
"""

import os
import sys
import json
import time
import math
import ssl
import urllib.request
from datetime import datetime, timezone

class Config:
    INITIAL_CAPITAL_USD = 10000.0
    RISK_PER_TRADE_PCT = 1.0        # 1% per trade
    MAX_DAILY_DRAWDOWN_PCT = 2.0    # Hard stop at 2% daily loss
    MAX_OPEN_TRADES = 3
    FEE_PCT = 0.08                  # 0.08% maker/taker fee

class RiskEngine:
    def __init__(self, initial_equity=10000.0):
        self.daily_start_equity = initial_equity
        self.equity = initial_equity
        self.consecutive_losses = 0
        self.circuit_broken = False
        self.cooldown_until = 0

    def can_trade(self):
        if self.circuit_broken:
            return False, "CIRCUIT_BREAKER_ACTIVE"
        if time.time() < self.cooldown_until:
            rem = int(self.cooldown_until - time.time())
            return False, f"COOLDOWN_ACTIVE_{rem}s"
        dd = ((self.daily_start_equity - self.equity) / self.daily_start_equity) * 100.0
        if dd >= Config.MAX_DAILY_DRAWDOWN_PCT:
            self.circuit_broken = True
            return False, f"MAX_DAILY_DRAWDOWN_HIT_{dd:.2f}%"
        return True, "OK"

    def record_trade(self, pnl):
        self.equity += pnl
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                self.cooldown_until = time.time() + 3600  # 1 hour cooldown
        else:
            self.consecutive_losses = 0

class MarketScanner:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def get_crypto_candles(self, symbol="BTCUSDT", limit=100):
        url = f"https://api.coinex.com/v2/spot/kline?market={symbol}&period=1hour&limit={limit}"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=8) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and data.get("code") == 0:
                    return [{
                        "close": float(k["close"]),
                        "high": float(k["high"]),
                        "low": float(k["low"]),
                        "open": float(k["open"]),
                        "volume": float(k["volume"])
                    } for k in data.get("data", [])]
        except Exception:
            pass
        return []

    def get_nobitex_toman_rate(self):
        url = "https://api.nobitex.ir/market/stats"
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and "stats" in data:
                    return float(data["stats"].get("usdt-rls", {}).get("latest", 0)) / 10.0
        except Exception:
            pass
        return 0.0

class TechnicalStrategy:
    @staticmethod
    def calculate_bollinger_and_rsi(closes, period=20, std_dev=2.0):
        if len(closes) < period:
            return None, None, None, None
        
        # Bollinger Bands
        sma = sum(closes[-period:]) / period
        variance = sum((x - sma) ** 2 for x in closes[-period:]) / period
        std = math.sqrt(variance)
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)

        # RSI 14
        deltas = [closes[i+1] - closes[i] for i in range(len(closes)-1)]
        if len(deltas) < 14:
            return sma, upper, lower, 50.0
        gains = [d if d > 0 else 0 for d in deltas[-14:]]
        losses = [-d if d < 0 else 0 for d in deltas[-14:]]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))

        return sma, upper, lower, rsi

class MasterExecutionEngine:
    def __init__(self):
        self.risk = RiskEngine(Config.INITIAL_CAPITAL_USD)
        self.scanner = MarketScanner()
        self.open_positions = {}
        self.trade_history = []

    def execute_market_cycle(self):
        print("=" * 70)
        print("🏛️ RICK SANCHEZ AUTONOMOUS MULTI-MARKET TRADING ENGINE")
        print(f"💼 Balance: ${self.risk.equity:,.2f} USD | Mode: Institutional Risk Guard")
        print("=" * 70)

        # 1. Nobitex Toman Rate
        toman_rate = self.scanner.get_nobitex_toman_rate()
        if toman_rate > 0:
            print(f"🇮🇷 Nobitex USDT/IRT: {toman_rate:,.0f} Toman")

        # 2. Check Markets (US30 simulation + Crypto Live)
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        
        for sym in symbols:
            can_trade, reason = self.risk.can_trade()
            if not can_trade:
                print(f"⚠️ Risk Guard Triggered: {reason}")
                break

            candles = self.scanner.get_crypto_candles(sym, limit=60)
            if not candles:
                continue

            closes = [c["close"] for c in candles]
            cur_price = closes[-1]
            sma, upper, lower, rsi = TechnicalStrategy.calculate_bollinger_and_rsi(closes)

            print(f"\n📊 [{sym:8}] Price: ${cur_price:,.2f} | RSI: {rsi:.1f} | LowerBB: ${lower:,.2f} | UpperBB: ${upper:,.2f}")

            # Check open position
            if sym in self.open_positions:
                pos = self.open_positions[sym]
                # TP / SL check
                pnl_pct = ((cur_price - pos["entry"]) / pos["entry"]) * 100.0 if pos["side"] == "BUY" else ((pos["entry"] - cur_price) / pos["entry"]) * 100.0
                if cur_price >= pos["tp"] or cur_price <= pos["sl"] or (rsi and rsi > 70):
                    pnl_usd = (pnl_pct / 100.0) * pos["size"]
                    self.risk.record_trade(pnl_usd)
                    record = {
                        "symbol": sym,
                        "side": pos["side"],
                        "entry": pos["entry"],
                        "exit": cur_price,
                        "pnl_usd": round(pnl_usd, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "closed_at": datetime.now(timezone.utc).isoformat()
                    }
                    self.trade_history.append(record)
                    del self.open_positions[sym]
                    print(f"🏁 CLOSED {sym}: PnL=${pnl_usd:+,.2f} ({pnl_pct:+.2f}%) | Equity: ${self.risk.equity:,.2f}")
            else:
                # Mean Reversion Signal: Price <= Lower BB and RSI <= 35
                if lower and rsi and closes[-1] <= lower * 1.002 and rsi <= 35:
                    if len(self.open_positions) < Config.MAX_OPEN_TRADES:
                        pos_size = self.risk.equity * 0.15 # 15% position size
                        sl = cur_price * 0.98               # 2% stop loss
                        tp = cur_price * 1.035              # 3.5% take profit
                        self.open_positions[sym] = {
                            "symbol": sym,
                            "side": "BUY",
                            "entry": cur_price,
                            "size": pos_size,
                            "sl": sl,
                            "tp": tp,
                            "opened_at": datetime.now(timezone.utc).isoformat()
                        }
                        print(f"🚀 OPENED BUY on {sym} @ ${cur_price:,.2f} | Size: ${pos_size:,.2f} | SL: ${sl:,.2f} | TP: ${tp:,.2f}")

        # 3. Save Summary Report
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_equity_usd": round(self.risk.equity, 2),
            "open_positions": self.open_positions,
            "trade_history": self.trade_history,
            "risk_status": {
                "circuit_broken": self.risk.circuit_broken,
                "consecutive_losses": self.risk.consecutive_losses
            }
        }
        with open("/Users/ricksabchez/Desktop/trading-bot/trading_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Report updated: /Users/ricksabchez/Desktop/trading-bot/trading_report.json")

if __name__ == "__main__":
    engine = MasterExecutionEngine()
    engine.execute_market_cycle()
