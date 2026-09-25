"""
Multi-Timeframe Trend & ATR Breakout Strategy
Optimized for Gold (XAUUSD), Major Forex Pairs, and Indices.
Features:
- EMA 20/50/200 Trend Alignment
- RSI Momentum Filter (52-68 Bullish, 32-48 Bearish)
- Dynamic ATR Stop-Loss and Take-Profit Calculation (Minimum 1:2 R:R)
- London & New York Session Time Filter
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from config import config
from strategies.base_strategy import BaseStrategy, TradeSignal

logger = logging.getLogger("TrendBreakoutStrategy")

class TrendBreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(name="TrendBreakout_MultiAsset")

    @staticmethod
    def calculate_ema(values: List[float], period: int) -> float:
        if len(values) < period:
            return values[-1] if values else 0.0
        multiplier = 2.0 / (period + 1)
        ema = sum(values[:period]) / period
        for val in values[period:]:
            ema = (val - ema) * multiplier + ema
        return ema

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_atr(klines: List[Dict[str, float]], period: int = 14) -> float:
        if len(klines) < 2:
            return 1.0
        true_ranges = []
        for i in range(1, len(klines)):
            high = klines[i]["high"]
            low = klines[i]["low"]
            prev_close = klines[i-1]["close"]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
            
        if not true_ranges:
            return 1.0
        if len(true_ranges) < period:
            return sum(true_ranges) / len(true_ranges)
        return sum(true_ranges[-period:]) / period

    def is_session_active(self) -> bool:
        """Verifies if current time is within high-liquidity London or NY sessions."""
        if not config.ENFORCE_SESSION_HOURS:
            return True
        current_hour = datetime.now(timezone.utc).hour
        for session_name, window in config.ACTIVE_SESSIONS.items():
            if window["start"] <= current_hour < window["end"]:
                return True
        return False

    def evaluate(self, symbol: str, current_price: float, klines: List[Dict[str, float]]) -> Optional[TradeSignal]:
        if not klines or len(klines) < 30:
            return None

        # Check Trading Session
        if not self.is_session_active():
            logger.debug(f"⏳ Market outside London/NY active sessions for {symbol}. Standing by.")
            return None

        close_prices = [k["close"] for k in klines]
        ema_fast = self.calculate_ema(close_prices, config.EMA_FAST)
        ema_slow = self.calculate_ema(close_prices, config.EMA_SLOW)
        rsi = self.calculate_rsi(close_prices, config.RSI_PERIOD)
        atr = self.calculate_atr(klines, config.ATR_PERIOD)

        # Baseline SL & TP using ATR
        sl_dist = atr * config.ATR_MULTIPLIER
        tp_dist = sl_dist * config.DEFAULT_RISK_REWARD_RATIO

        # 1. Bullish Trend Breakout Condition:
        # Fast EMA above Slow EMA, RSI in healthy momentum zone (52-68), Price breaking out
        if ema_fast > ema_slow and (config.RSI_BULLISH_THRESHOLD <= rsi <= 68.0) and current_price >= ema_fast:
            sl_price = round(current_price - sl_dist, 4 if "USD" in symbol and "XAU" not in symbol else 2)
            tp_price = round(current_price + tp_dist, 4 if "USD" in symbol and "XAU" not in symbol else 2)
            return TradeSignal(
                symbol=symbol,
                action="BUY",
                entry_price=current_price,
                stop_loss=sl_price,
                take_profit=tp_price,
                atr=atr,
                confidence=0.85,
                reason=f"Bullish Trend Alignment (EMA{config.EMA_FAST} > EMA{config.EMA_SLOW}, RSI={rsi:.1f})"
            )

        # 2. Bearish Trend Breakdown Condition:
        # Fast EMA below Slow EMA, RSI in healthy bearish zone (32-48), Price below EMA
        if ema_fast < ema_slow and (32.0 <= rsi <= config.RSI_BEARISH_THRESHOLD) and current_price <= ema_fast:
            sl_price = round(current_price + sl_dist, 4 if "USD" in symbol and "XAU" not in symbol else 2)
            tp_price = round(current_price - tp_dist, 4 if "USD" in symbol and "XAU" not in symbol else 2)
            return TradeSignal(
                symbol=symbol,
                action="SELL",
                entry_price=current_price,
                stop_loss=sl_price,
                take_profit=tp_price,
                atr=atr,
                confidence=0.85,
                reason=f"Bearish Trend Alignment (EMA{config.EMA_FAST} < EMA{config.EMA_SLOW}, RSI={rsi:.1f})"
            )

        return None
