"""
Live Monte Carlo Stress Testing & Value-at-Risk (VaR) Engine (Q1 Days 46-60)
Simulates thousands of market paths, black-swan shocks, and consecutive loss streaks
to compute exact Value-at-Risk (VaR 99%), Conditional VaR (CVaR / Expected Shortfall),
and Maximum Drawdown distributions on the active multi-asset portfolio.
"""

import time
import math
import random
import json
import os
from typing import Dict, Any, List

STRESS_REPORT_FILE = os.path.join(os.path.dirname(__file__), "live_monte_carlo_var.json")

class LiveMonteCarloStressTester:
    def __init__(self, num_simulations: int = 2500, horizon_days: int = 30):
        self.num_sims = num_simulations
        self.horizon_days = horizon_days

    def run_stress_simulation(
        self,
        current_equity: float,
        win_rate: float = 0.58,
        risk_per_trade_pct: float = 0.75,
        avg_rr_ratio: float = 2.0,
        trades_per_day: float = 2.5,
        black_swan_prob_daily: float = 0.02
    ) -> Dict[str, Any]:
        """
        Runs Monte Carlo iterations with synthetic Geometric Brownian Motion + Jump Diffusion (Black Swan events).
        """
        total_trades = int(self.horizon_days * trades_per_day)
        terminal_equities = []
        max_drawdowns = []

        risk_fraction = risk_per_trade_pct / 100.0

        for _ in range(self.num_sims):
            eq = current_equity
            peak = current_equity
            mdd = 0.0

            for _ in range(total_trades):
                # Normal trade outcome
                is_win = random.random() < win_rate
                risk_amt = eq * risk_fraction

                if is_win:
                    pnl = risk_amt * avg_rr_ratio
                else:
                    pnl = -risk_amt

                # Black-swan shock event injection (e.g. flash crash, liquidity vacuum)
                if random.random() < (black_swan_prob_daily / trades_per_day):
                    shock_mult = random.uniform(2.0, 4.0) # 2x-4x normal loss due to slippage
                    pnl -= risk_amt * shock_mult

                eq = max(eq + pnl, 0.0)
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak if peak > 0 else 0.0
                if dd > mdd:
                    mdd = dd

            terminal_equities.append(eq)
            max_drawdowns.append(mdd)

        terminal_equities.sort()
        max_drawdowns.sort()

        # VaR and CVaR calculations at 95% and 99% confidence
        var_95_idx = int(self.num_sims * 0.05)
        var_99_idx = int(self.num_sims * 0.01)

        equity_var_95 = terminal_equities[var_95_idx]
        equity_var_99 = terminal_equities[var_99_idx]

        loss_var_95_usd = max(current_equity - equity_var_95, 0.0)
        loss_var_99_usd = max(current_equity - equity_var_99, 0.0)

        # Expected Shortfall (CVaR 99% - average loss beyond 99% VaR)
        cvar_99_losses = [max(current_equity - e, 0.0) for e in terminal_equities[:var_99_idx]]
        cvar_99_usd = sum(cvar_99_losses) / len(cvar_99_losses) if cvar_99_losses else loss_var_99_usd

        # Median expected terminal equity and worst-case DD
        median_equity = terminal_equities[int(self.num_sims * 0.50)]
        worst_dd_pct = max_drawdowns[-1] * 100.0
        dd_95_pct = max_drawdowns[int(self.num_sims * 0.95)] * 100.0

        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "initial_equity": current_equity,
            "simulations": self.num_sims,
            "horizon_days": self.horizon_days,
            "median_projected_equity": round(median_equity, 2),
            "projected_profit_pct": round(((median_equity - current_equity) / current_equity) * 100.0, 2),
            "var_95_usd": round(loss_var_95_usd, 2),
            "var_99_usd": round(loss_var_99_usd, 2),
            "cvar_99_usd": round(cvar_99_usd, 2),
            "drawdown_95_pct": round(dd_95_pct, 2),
            "worst_case_drawdown_pct": round(worst_dd_pct, 2),
            "capital_preservation_passed": dd_95_pct <= 12.0
        }

        try:
            with open(STRESS_REPORT_FILE, "w") as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            print("Failed to save Monte Carlo report:", e)

        return report

if __name__ == "__main__":
    tester = LiveMonteCarloStressTester(num_simulations=2000, horizon_days=30)
    rep = tester.run_stress_simulation(current_equity=1000.0, win_rate=0.58, risk_per_trade_pct=0.75, avg_rr_ratio=2.0)
    print("=" * 60)
    print("  LIVE MONTE CARLO VALUE-AT-RISK (VaR) REPORT  ")
    print("=" * 60)
    print(json.dumps(rep, indent=2))
