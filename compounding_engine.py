"""
Exponential Compounding & Half-Kelly Capital Growth Engine
Implements:
1. Dynamic Half-Kelly fraction calculation based on empirical rolling trade history.
2. Exponential compounding re-investment of realized profits into base capital.
3. Profit Ratchet: Permanently locks in 15% of new all-time high gains into cold reserve.
"""

from typing import List, Dict, Any, Tuple

class ExponentialCompoundingEngine:
    def __init__(self, initial_capital: float = 1000.0, reserve_ratchet_pct: float = 15.0):
        self.initial_capital = initial_capital
        self.active_capital = initial_capital
        self.high_water_mark = initial_capital
        self.locked_reserve = 0.0
        self.reserve_ratchet_pct = reserve_ratchet_pct # 15% of new ATH gains locked
        self.closed_trades: List[Dict[str, Any]] = []

    def record_trade_result(self, profit_dollar: float, risk_dollar: float) -> Dict[str, Any]:
        """
        Record a closed trade, update equity, check High-Water Mark,
        and apply the Profit Ratchet.
        """
        r_multiple = profit_dollar / risk_dollar if risk_dollar > 0 else 0.0
        self.active_capital += profit_dollar

        trade_info = {
            "pnl": round(profit_dollar, 2),
            "r_multiple": round(r_multiple, 2),
            "active_capital": round(self.active_capital, 2)
        }
        self.closed_trades.append(trade_info)

        # High-Water Mark & Profit Ratchet Logic
        ratchet_locked_this_trade = 0.0
        if self.active_capital > self.high_water_mark:
            gain_above_ath = self.active_capital - self.high_water_mark
            ratchet_amount = gain_above_ath * (self.reserve_ratchet_pct / 100.0)
            
            self.locked_reserve += ratchet_amount
            self.active_capital -= ratchet_amount # Skim to protected cold reserve
            self.high_water_mark = self.active_capital # Reset baseline
            ratchet_locked_this_trade = ratchet_amount

        trade_info["locked_to_reserve"] = round(ratchet_locked_this_trade, 2)
        trade_info["total_locked_reserve"] = round(self.locked_reserve, 2)
        trade_info["net_active_capital"] = round(self.active_capital, 2)
        return trade_info

    def get_dynamic_half_kelly_pct(self, min_risk_pct: float = 0.4, max_risk_pct: float = 1.5) -> float:
        """
        Calculate Half-Kelly fraction f* from rolling last 30 trades:
        f* = (p * b - (1 - p)) / b
        Half-Kelly = 0.5 * f*
        """
        if len(self.closed_trades) < 10:
            return 0.75 # Default calibrated institutional baseline

        recent = self.closed_trades[-30:]
        wins = [t for t in recent if t["pnl"] > 0]
        losses = [t for t in recent if t["pnl"] < 0]

        if not wins or not losses:
            return 0.75

        win_rate = len(wins) / len(recent)
        avg_win = sum(t["pnl"] for t in wins) / len(wins)
        avg_loss = abs(sum(t["pnl"] for t in losses)) / len(losses)

        if avg_loss <= 0:
            return 0.75

        b = avg_win / avg_loss # Payoff ratio
        full_kelly = (win_rate * b - (1.0 - win_rate)) / b
        half_kelly = full_kelly * 0.5 * 100.0 # as percentage

        # Clamp within risk bounds to guarantee capital preservation
        if half_kelly < min_risk_pct:
            return min_risk_pct
        if half_kelly > max_risk_pct:
            return max_risk_pct
        return round(half_kelly, 2)

    def calculate_lot_size(self, stop_loss_points: float, point_value: float,
                           symbol_min_lot: float = 0.01, symbol_max_lot: float = 10.0,
                           symbol_lot_step: float = 0.01) -> Tuple[float, float, float]:
        """
        Dynamically scale lot size based on active compounded capital and Half-Kelly.
        Returns: (normalized_lot, risk_amount_usd, effective_risk_pct)
        """
        risk_pct = self.get_dynamic_half_kelly_pct()
        risk_usd = self.active_capital * (risk_pct / 100.0)

        risk_per_lot = stop_loss_points * point_value
        if risk_per_lot <= 0:
            return symbol_min_lot, risk_usd, risk_pct

        raw_lots = risk_usd / risk_per_lot
        steps = int(raw_lots / symbol_lot_step)
        normalized = steps * symbol_lot_step

        if normalized < symbol_min_lot:
            normalized = symbol_min_lot
        if normalized > symbol_max_lot:
            normalized = symbol_max_lot

        return round(normalized, 2), round(risk_usd, 2), risk_pct

if __name__ == "__main__":
    comp = ExponentialCompoundingEngine(initial_capital=1000.0)
    print("Initial State:", comp.active_capital)
    
    # Simulate a series of 1:2 R:R trades
    res1 = comp.record_trade_result(profit_dollar=15.0, risk_dollar=7.5)
    print("After Win 1:", res1)

    res2 = comp.record_trade_result(profit_dollar=20.0, risk_dollar=10.0)
    print("After Win 2 (ATH Ratchet):", res2)

    res3 = comp.record_trade_result(profit_dollar=-7.5, risk_dollar=7.5)
    print("After Loss 1:", res3)

    lot, risk_usd, risk_pct = comp.calculate_lot_size(stop_loss_points=50, point_value=1.0)
    print(f"Dynamic Sizing -> Lot: {lot} | Risk: ${risk_usd} ({risk_pct}%) | Active Capital: ${comp.active_capital:.2f}")
