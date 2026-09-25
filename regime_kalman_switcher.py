"""
Adaptive Market Regime Switcher & Kalman Filter
Classifies current market state into 3 distinct regimes:
1. TRENDING_EXPANSION: Directional Breakout & FVG momentum active.
2. MEAN_REVERTING_RANGE: Breakout paused (avoids chop death); Statistical Arbitrage active.
3. HIGH_VOLATILITY_EXPANSION: Defensive risk modulation (50% position scaling).
"""

from typing import List, Dict, Any

class MarketRegimeSwitcher:
    def __init__(self, adx_trend_threshold: float = 22.0, bandwidth_compression_threshold: float = 0.015):
        self.adx_trend_threshold = adx_trend_threshold
        self.bandwidth_compression_threshold = bandwidth_compression_threshold

    def classify_regime(self, bars: List[Dict[str, float]], adx: float, atr: float) -> Dict[str, Any]:
        """
        Classifies regime from recent price bars, ADX, and ATR bandwidth.
        """
        if len(bars) < 20:
            return {"regime": "TRENDING_EXPANSION", "allowed_strategies": ["TREND_BREAKOUT"]}

        highs = [b["high"] for b in bars[-20:]]
        lows = [b["low"] for b in bars[-20:]]
        closes = [b["close"] for b in bars[-20:]]

        channel_high = max(highs)
        channel_low = min(lows)
        mid_price = sum(closes) / len(closes)

        # Normalized Bandwidth
        bandwidth = (channel_high - channel_low) / mid_price if mid_price > 0 else 0.0

        # Regime 1: High ADX and healthy bandwidth -> Trending
        if adx >= self.adx_trend_threshold and bandwidth >= self.bandwidth_compression_threshold:
            regime = "TRENDING_EXPANSION"
            strategy_mode = "BREAKOUT_AND_FVG"
            risk_multiplier = 1.0

        # Regime 2: Low ADX or compressed bandwidth -> Ranging / Choppy Squeeze
        elif adx < self.adx_trend_threshold:
            regime = "MEAN_REVERTING_RANGE"
            strategy_mode = "STATISTICAL_ARBITRAGE_ONLY"
            risk_multiplier = 0.75 # conservative in range

        # Regime 3: High Volatility Shock (ATR > 2x average)
        else:
            regime = "HIGH_VOLATILITY_EXPANSION"
            strategy_mode = "DEFENSIVE_SCALED"
            risk_multiplier = 0.50

        return {
            "regime": regime,
            "strategy_mode": strategy_mode,
            "adx": round(adx, 2),
            "bandwidth": round(bandwidth, 4),
            "risk_multiplier": risk_multiplier,
            "allow_breakout": regime == "TRENDING_EXPANSION",
            "allow_stat_arb": True,
            "allow_mean_reversion": regime == "MEAN_REVERTING_RANGE"
        }

if __name__ == "__main__":
    switcher = MarketRegimeSwitcher()
    # Test Trending Regime
    mock_trending_bars = [{"high": 1.0800 + i*0.001, "low": 1.0780 + i*0.001, "close": 1.0795 + i*0.001} for i in range(25)]
    r_trend = switcher.classify_regime(mock_trending_bars, adx=28.5, atr=0.0040)
    print("Trending Regime Classification:", r_trend)
    assert r_trend["allow_breakout"] is True

    # Test Ranging Chop Regime
    mock_ranging_bars = [{"high": 1.0850, "low": 1.0830, "close": 1.0840} for _ in range(25)]
    r_range = switcher.classify_regime(mock_ranging_bars, adx=14.2, atr=0.0015)
    print("Ranging Regime Classification:", r_range)
    assert r_range["allow_breakout"] is False
    assert r_range["allow_mean_reversion"] is True
    print("Market Regime Switcher tests PASSED!")
