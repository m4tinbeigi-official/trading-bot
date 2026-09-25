"""
Smart Money Concepts (SMC) & Liquidity Imbalance Engine
1. Fair Value Gap (FVG) / Imbalance Detection: Identifies institutional displacement candles.
2. Liquidity Sweep Detection: Identifies Turtle Soup / Stop Hunts above/below key highs and lows.
3. Volume Surge Validator: Confirms institutional participation vs retail fakeouts.
"""

from typing import List, Dict, Any, Optional, Tuple

class SMCLiquidityEngine:
    def __init__(self, volume_surge_mult: float = 1.25):
        self.volume_surge_mult = volume_surge_mult

    def detect_fvg(self, bars: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Detects Fair Value Gap on the latest 3-4 closed bars.
        Bullish FVG: Low of bar[1] > High of bar[3]
        Bearish FVG: High of bar[1] < Low of bar[3]
        """
        if len(bars) < 4:
            return {"bullish_fvg": False, "bearish_fvg": False, "gap_size": 0.0}

        b1 = bars[-1] # latest closed bar
        b3 = bars[-3] # 2 bars prior

        bullish_fvg = b1["low"] > b3["high"]
        bearish_fvg = b1["high"] < b3["low"]

        gap_size = 0.0
        if bullish_fvg:
            gap_size = b1["low"] - b3["high"]
        elif bearish_fvg:
            gap_size = b3["low"] - b1["high"]

        return {
            "bullish_fvg": bullish_fvg,
            "bearish_fvg": bearish_fvg,
            "gap_size": round(gap_size, 5)
        }

    def detect_liquidity_sweep(self, bars: List[Dict[str, float]], lookback: int = 24) -> Dict[str, Any]:
        """
        Detects Stop Run / Turtle Soup:
        Price wicks above high / below low of the lookback range, but closes back inside.
        """
        if len(bars) < lookback + 2:
            return {"sweep_high": False, "sweep_low": False}

        range_bars = bars[-(lookback + 2):-2]
        curr_bar = bars[-2] # most recent finished candle

        range_high = max(b["high"] for b in range_bars)
        range_low = min(b["low"] for b in range_bars)

        # Bullish sweep: Wicked below range_low, but closed back above range_low
        sweep_low = (curr_bar["low"] < range_low) and (curr_bar["close"] > range_low)
        # Bearish sweep: Wicked above range_high, but closed back below range_high
        sweep_high = (curr_bar["high"] > range_high) and (curr_bar["close"] < range_high)

        return {
            "sweep_high": sweep_high,
            "sweep_low": sweep_low,
            "range_high": range_high,
            "range_low": range_low
        }

    def validate_volume_surge(self, bars: List[Dict[str, float]], period: int = 20) -> Dict[str, Any]:
        """Validates if tick volume on the breakout candle exceeds the moving average."""
        if len(bars) < period + 1:
            return {"has_surge": True, "ratio": 1.0}

        vols = [b.get("volume", b.get("tick_volume", 1.0)) for b in bars[-(period + 1):-1]]
        avg_vol = sum(vols) / len(vols) if len(vols) > 0 else 1.0
        curr_vol = bars[-1].get("volume", bars[-1].get("tick_volume", 1.0))

        ratio = curr_vol / avg_vol if avg_vol > 0 else 1.0
        return {
            "has_surge": ratio >= self.volume_surge_mult,
            "ratio": round(ratio, 2)
        }

    def evaluate_smc_setup(self, bars: List[Dict[str, float]]) -> Dict[str, Any]:
        fvg = self.detect_fvg(bars)
        sweep = self.detect_liquidity_sweep(bars)
        vol = self.validate_volume_surge(bars)

        score = 0
        direction = "NEUTRAL"

        if fvg["bullish_fvg"]:
            score += 3
            direction = "BUY"
        elif fvg["bearish_fvg"]:
            score += 3
            direction = "SELL"

        if sweep["sweep_low"]:
            score += 4
            direction = "BUY"
        elif sweep["sweep_high"]:
            score += 4
            direction = "SELL"

        if vol["has_surge"]:
            score += 2

        return {
            "direction": direction,
            "smc_score": score,
            "fvg": fvg,
            "sweep": sweep,
            "volume_surge": vol
        }

if __name__ == "__main__":
    engine = SMCLiquidityEngine()
    mock_bars = [
        {"open": 1.0800, "high": 1.0820, "low": 1.0790, "close": 1.0815, "volume": 120},
        {"open": 1.0815, "high": 1.0830, "low": 1.0810, "close": 1.0825, "volume": 130},
        {"open": 1.0825, "high": 1.0870, "low": 1.0820, "close": 1.0865, "volume": 280}, # Big displacement
        {"open": 1.0865, "high": 1.0895, "low": 1.0850, "close": 1.0890, "volume": 310}  # FVG created (low 1.0850 > high 1.0830)
    ]
    res = engine.evaluate_smc_setup(mock_bars)
    print("SMC Liquidity Evaluation:", res)
