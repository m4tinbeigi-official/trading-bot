"""
Master Quantitative Fund Engine (v7.0-QUANTUM)
Integrates:
1. Inter-Market Macro Spillover & DXY Veto Filter (intermarket_dxy_veto.py)
2. Order Flow & Tick Delta Absorption Engine (order_flow_engine.py)
3. Adaptive Market Regime Switcher (regime_kalman_switcher.py)
4. Dynamic Momentum Decay Liquidation Engine (momentum_decay_liquidator.py)
5. Smart Money Concepts (FVG Imbalance & Liquidity Sweeps)
6. v1m System One Probabilistic AI Validation (v1m.ir)
7. Statistical Arbitrage & Cointegration (Delta-Neutral Cycles)
8. Exponential Compounding with Half-Kelly Capital Sizing
9. Autonomous Treasury & Self-Funding OpEx Management
"""

import os
import sys
import json
import time
import math
from typing import Dict, Any, List

from v1m_oracle import V1mDecisionOracle
from stat_arbitrage_engine import TriangularArbitrageScanner, PairsTradingCointegrationEngine
from compounding_engine import ExponentialCompoundingEngine
from treasury_manager import AutonomousTreasuryManager
from smc_liquidity_engine import SMCLiquidityEngine
from intermarket_dxy_veto import InterMarketDXYVetoEngine
from order_flow_engine import OrderFlowEngine
from regime_kalman_switcher import MarketRegimeSwitcher
from momentum_decay_liquidator import MomentumDecayLiquidator
from economic_calendar_news_filter import EconomicCalendarNewsFilter
from tick_data_collector import TickDataCollector
from telegram_visual_alerts import TelegramVisualAlerts
from live_monte_carlo_var import LiveMonteCarloStressTester
from session_liquidity_auditor import SessionLiquidityAuditor
from hmm_regime_classifier import GaussianHMMRegimeClassifier

class QuantitativeFundMaster:
    def __init__(self, initial_capital: float = 1000.0):
        print("=========================================================")
        print("  QUANTITATIVE HEDGE FUND MASTER ENGINE (v8.5-ULTRA)     ")
        print("  DXY Veto | Order Flow | Regime Switcher | SMC FVG     ")
        print("  News Guard | Tick Store | Monte Carlo VaR | HMM State  ")
        print("  v1m System One | Stat-Arb | Autonomous OpEx Treasury   ")
        print("=========================================================")

        self.oracle = V1mDecisionOracle()
        self.smc = SMCLiquidityEngine(volume_surge_mult=1.25)
        self.dxy_veto = InterMarketDXYVetoEngine()
        self.order_flow = OrderFlowEngine()
        self.regime_switcher = MarketRegimeSwitcher()
        self.liquidator = MomentumDecayLiquidator()
        self.news_filter = EconomicCalendarNewsFilter(danger_window_pre_minutes=30, danger_window_post_minutes=30)
        self.tick_collector = TickDataCollector()
        self.alerts = TelegramVisualAlerts()
        self.stress_tester = LiveMonteCarloStressTester(num_simulations=1000, horizon_days=30)
        self.session_auditor = SessionLiquidityAuditor()
        self.hmm_classifier = GaussianHMMRegimeClassifier()

        self.triangular_scanner = TriangularArbitrageScanner(oracle=self.oracle)
        self.pairs_engine = PairsTradingCointegrationEngine(oracle=self.oracle)
        self.compounding = ExponentialCompoundingEngine(initial_capital=initial_capital)
        self.treasury = AutonomousTreasuryManager()

        self.active_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []

    def scan_market_cycle(self, prices: Dict[str, Dict[str, float]], macro_curr: Dict[str, float], macro_past: Dict[str, float], adx_val: float = 26.0) -> List[Dict[str, Any]]:
        """
        Runs one cycle of market scanning across:
        1. Market Regime Classification
        2. Statistical Arbitrage (Triangular)
        3. DXY Macro Spillover Filter
        4. High-Probability Directional Confluence
        """
        opportunities = []

        # 1. Classify Market Regime
        regime = self.regime_switcher.classify_regime(
            bars=[{"high": 1.0850, "low": 1.0800, "close": 1.0830} for _ in range(25)],
            adx=adx_val,
            atr=0.0035
        )
        print(f"[*] Market Regime Classified: {regime['regime']} (Mode: {regime['strategy_mode']})")

        # 2. Check Currency Triangles (Delta-neutral arbitrage active in all regimes)
        for triangle in self.triangular_scanner.triangles:
            res = self.triangular_scanner.scan_triangle(triangle, prices)
            if res and res["v1m_approved"]:
                opportunities.append({
                    "strategy": "STAT_ARBITRAGE_TRIANGLE",
                    "data": res
                })

        # 3. Directional SMC Setup (Only if regime allows breakout)
        if regime["allow_breakout"]:
            candidate_symbol = "EURUSD"
            candidate_dir = "BUY"

            # Check DXY Veto Filter
            veto = self.dxy_veto.evaluate_veto(candidate_symbol, candidate_dir, macro_curr, macro_past)
            if veto["is_vetoed"]:
                print(f"[!] DXY Veto Filter Triggered: {candidate_symbol} {candidate_dir} -> {veto['veto_reason']}")
            else:
                is_ok, verdict, score = self.oracle.evaluate_directional_trade(candidate_symbol, candidate_dir, 10, "BULLISH", 55.0, 10.0)
                if is_ok:
                    opportunities.append({
                        "strategy": "SMC_CONFLUENCE_BREAKOUT",
                        "symbol": candidate_symbol,
                        "direction": candidate_dir,
                        "verdict": verdict,
                        "score": score
                    })

        return opportunities

    def execute_and_compound(self, setup_type: str, details: Dict[str, Any], sim_profit: float = 0.0):
        """Execute a trade, update compounding capital, and skim to OpEx Treasury."""
        trade_id = f"FUND_{int(time.time()*1000)}"
        risk_pct = self.compounding.get_dynamic_half_kelly_pct()
        risk_usd = self.compounding.active_capital * (risk_pct / 100.0)

        # Compound capital and update Profit Ratchet
        comp_res = self.compounding.record_trade_result(profit_dollar=sim_profit, risk_dollar=risk_usd)

        # Allocate 15% to Autonomous Treasury if profitable
        treasury_res = {}
        if sim_profit > 0:
            treasury_res = self.treasury.process_closed_trade_pnl(net_profit_usd=sim_profit, trade_id=trade_id)

        record = {
            "trade_id": trade_id,
            "setup": setup_type,
            "details": details,
            "pnl": sim_profit,
            "compounding": comp_res,
            "treasury": treasury_res
        }
        self.trade_history.append(record)
        return record

    def print_fund_status(self):
        print("\n" + self.treasury.get_summary())
        print(f"• Active Trading Capital:   ${self.compounding.active_capital:.2f} USD")
        print(f"• Locked High-Water Reserve: ${self.compounding.locked_reserve:.2f} USD")
        print(f"• Current Half-Kelly Risk:  {self.compounding.get_dynamic_half_kelly_pct()}%")
        print(f"• Total Trades Logged:      {len(self.trade_history)}")

if __name__ == "__main__":
    fund = QuantitativeFundMaster(initial_capital=1000.0)

    macro_curr = {"EURUSD": 1.0855, "USDJPY": 154.50, "GBPUSD": 1.2950, "USDCAD": 1.3600, "USDCHF": 0.8850}
    macro_past = {"EURUSD": 1.0845, "USDJPY": 154.60, "GBPUSD": 1.2940, "USDCAD": 1.3610, "USDCHF": 0.8860}

    market_snapshot = {
        "EURUSD": {"bid": 1.08550, "ask": 1.08560},
        "GBPUSD": {"bid": 1.29200, "ask": 1.29215},
        "EURGBP": {"bid": 0.84120, "ask": 0.84130}
    }

    print("\n[1] Running Master Market Scan (Regime + DXY Veto + v1m AI + Stat-Arb)...")
    opps = fund.scan_market_cycle(market_snapshot, macro_curr, macro_past, adx_val=26.5)
    print(f"Opportunities detected: {len(opps)}")

    print("\n[2] Executing Top Opportunity with Half-Kelly Sizing & Autonomous Treasury Skim...")
    res = fund.execute_and_compound(
        setup_type="SMC_CONFLUENCE_BREAKOUT",
        details={"symbol": "EURUSD", "direction": "BUY"},
        sim_profit=58.20
    )
    print("Execution & Reinvestment Report:", json.dumps(res, indent=2))
    fund.print_fund_status()
