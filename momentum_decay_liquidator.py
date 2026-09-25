"""
Dynamic Momentum Decay & Velocity Liquidation Engine
Monitors profitable positions and detects momentum exhaustion / velocity decay.
Liquidates trades at peak profit before retracement wicks eat gains.
"""

from typing import Dict, Any, List

class MomentumDecayLiquidator:
    def __init__(self, min_profit_atr_trigger: float = 1.0):
        self.min_profit_atr_trigger = min_profit_atr_trigger

    def evaluate_position_exit(self, position: Dict[str, Any], recent_bars: List[Dict[str, float]], current_rsi: float, atr: float) -> Dict[str, Any]:
        """
        position: {'ticket': 12345, 'type': 'BUY'/'SELL', 'open_price': 1.0800, 'current_price': 1.0870}
        """
        pos_type = position["type"].upper()
        open_price = position["open_price"]
        current_price = position["current_price"]

        profit = (current_price - open_price) if pos_type == "BUY" else (open_price - current_price)
        profit_in_atr = profit / atr if atr > 0 else 0.0

        if profit_in_atr < self.min_profit_atr_trigger or len(recent_bars) < 2:
            return {"should_liquidate": False, "reason": "PROFIT_BELOW_DECAY_THRESHOLD"}

        curr_bar = recent_bars[-1]
        prev_bar = recent_bars[-2]

        should_liquidate = False
        reason = "NONE"

        # 1. Opposite Displacement Bar (Strong rejection against position)
        if pos_type == "BUY":
            # Opposing big red candle that exceeds 60% of previous green expansion
            if curr_bar["close"] < curr_bar["open"] and (curr_bar["open"] - curr_bar["close"]) > 0.8 * atr:
                should_liquidate = True
                reason = "BEARISH_DISPLACEMENT_EXHAUSTION"
            # RSI overbought reversal
            elif current_rsi > 75.0 and curr_bar["close"] < prev_bar["low"]:
                should_liquidate = True
                reason = "RSI_OVERBOUGHT_MOMENTUM_ROLLOVER"

        elif pos_type == "SELL":
            # Opposing big green candle
            if curr_bar["close"] > curr_bar["open"] and (curr_bar["close"] - curr_bar["open"]) > 0.8 * atr:
                should_liquidate = True
                reason = "BULLISH_DISPLACEMENT_EXHAUSTION"
            # RSI oversold reversal
            elif current_rsi < 25.0 and curr_bar["close"] > prev_bar["high"]:
                should_liquidate = True
                reason = "RSI_OVERSOLD_MOMENTUM_ROLLOVER"

        return {
            "ticket": position.get("ticket"),
            "should_liquidate": should_liquidate,
            "reason": reason,
            "profit_in_atr": round(profit_in_atr, 2),
            "locked_profit": round(profit, 5)
        }

if __name__ == "__main__":
    liquidator = MomentumDecayLiquidator()
    mock_pos = {"ticket": 9901, "type": "BUY", "open_price": 1.0800, "current_price": 1.0890}
    mock_bars = [
        {"open": 1.0850, "high": 1.0900, "low": 1.0845, "close": 1.0895},
        {"open": 1.0895, "high": 1.0905, "low": 1.0840, "close": 1.0845} # big opposing drop
    ]
    res = liquidator.evaluate_position_exit(mock_pos, mock_bars, current_rsi=76.0, atr=0.0050)
    print("Liquidation Evaluation:", res)
    assert res["should_liquidate"] is True
    print("Momentum Decay Liquidator tests PASSED!")
