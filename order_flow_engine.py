"""
Order Flow & Tick Imbalance Engine
Analyzes tick-level buying vs selling aggression, Cumulative Volume Delta (CVD),
and identifies Institutional Absorption (passive limit orders absorbing aggressive market orders).
"""

from typing import List, Dict, Any, Tuple

class OrderFlowEngine:
    def __init__(self, absorption_threshold: float = 1.8):
        self.absorption_threshold = absorption_threshold

    @staticmethod
    def calculate_tick_delta(ticks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates aggressive Buy volume vs aggressive Sell volume from raw tick stream.
        Tick with price uptick -> Buy Aggression; Tick with downtick -> Sell Aggression.
        """
        buy_vol = 0.0
        sell_vol = 0.0
        cvd = 0.0

        for i in range(1, len(ticks)):
            prev_price = ticks[i-1]["price"]
            curr_price = ticks[i]["price"]
            vol = ticks[i].get("volume", 1.0)

            if curr_price > prev_price:
                buy_vol += vol
                cvd += vol
            elif curr_price < prev_price:
                sell_vol += vol
                cvd -= vol
            else:
                # Same price - allocate based on tick flag or neutral split
                buy_vol += vol * 0.5
                sell_vol += vol * 0.5

        delta = buy_vol - sell_vol
        total_vol = buy_vol + sell_vol
        delta_ratio = delta / total_vol if total_vol > 0 else 0.0

        return {
            "total_volume": round(total_vol, 2),
            "buy_volume": round(buy_vol, 2),
            "sell_volume": round(sell_vol, 2),
            "delta": round(delta, 2),
            "delta_ratio": round(delta_ratio, 3),
            "cumulative_volume_delta": round(cvd, 2)
        }

    def detect_absorption(self, bars: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detects Institutional Absorption:
        Candle has massive volume (>1.8x average) but very small body and long wick in the direction of the trend.
        Indicates large market maker absorbing retail breakout orders.
        """
        if len(bars) < 10:
            return {"absorption_detected": False, "type": "NONE"}

        recent_bars = bars[-10:-1]
        target_bar = bars[-1]

        avg_vol = sum(b.get("volume", b.get("tick_volume", 1.0)) for b in recent_bars) / len(recent_bars)
        curr_vol = target_bar.get("volume", target_bar.get("tick_volume", 1.0))

        high = target_bar["high"]
        low = target_bar["low"]
        op = target_bar["open"]
        cl = target_bar["close"]
        bar_range = high - low
        body = abs(cl - op)

        if bar_range <= 0:
            return {"absorption_detected": False, "type": "NONE"}

        upper_wick = high - max(op, cl)
        lower_wick = min(op, cl) - low

        is_high_volume = curr_vol >= (avg_vol * self.absorption_threshold)
        is_small_body = (body / bar_range) < 0.35 # small body indicates stalemate

        # Bullish Absorption: High volume pushing down, but long lower wick and small body
        if is_high_volume and is_small_body and (lower_wick / bar_range) > 0.5:
            return {
                "absorption_detected": True,
                "type": "BULLISH_ABSORPTION",
                "bias": "BUY",
                "vol_multiple": round(curr_vol / avg_vol, 2),
                "notes": "Smart money absorbed heavy retail selling at support"
            }

        # Bearish Absorption: High volume pushing up, but long upper wick and small body
        if is_high_volume and is_small_body and (upper_wick / bar_range) > 0.5:
            return {
                "absorption_detected": True,
                "type": "BEARISH_ABSORPTION",
                "bias": "SELL",
                "vol_multiple": round(curr_vol / avg_vol, 2),
                "notes": "Smart money absorbed heavy retail breakout buying at resistance"
            }

        return {"absorption_detected": False, "type": "NONE", "bias": "NEUTRAL"}

if __name__ == "__main__":
    engine = OrderFlowEngine()
    # Mock tick stream
    mock_ticks = [
        {"price": 1.0850, "volume": 10},
        {"price": 1.0852, "volume": 25}, # Buy uptick
        {"price": 1.0854, "volume": 40}, # Buy uptick
        {"price": 1.0853, "volume": 15}, # Sell downtick
        {"price": 1.0856, "volume": 60}, # Buy uptick
    ]
    delta_res = engine.calculate_tick_delta(mock_ticks)
    print("Order Flow Delta Test:", delta_res)
    assert delta_res["delta"] > 0
    print("Order Flow Delta Engine validated successfully!")
