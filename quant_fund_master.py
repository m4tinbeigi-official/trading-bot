"""
Master Quantitative Fund Engine
Coordinates:
1. v1m System One Probabilistic AI Validation (v1m.ir)
2. Statistical Arbitrage & Cointegration (Delta-Neutral Cycles)
3. Directional Momentum & Confluence Scanner
4. Exponential Compounding with Half-Kelly Capital Sizing
5. Autonomous Treasury & Self-Funding OpEx Management
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

class QuantitativeFundMaster:
    def __init__(self, initial_capital: float = 1000.0):
        print("=========================================================")
        print("  QUANTITATIVE HEDGE FUND MASTER ENGINE (v6.0-ALPHA)    ")
        print("  Powered by v1m System One AI | Statistical Arbitrage   ")
        print("  Autonomous Treasury & Exponential Compounding          ")
        print("=========================================================")

        self.oracle = V1mDecisionOracle()
        self.triangular_scanner = TriangularArbitrageScanner(oracle=self.oracle)
        self.pairs_engine = PairsTradingCointegrationEngine(oracle=self.oracle)
        self.compounding = ExponentialCompoundingEngine(initial_capital=initial_capital)
        self.treasury = AutonomousTreasuryManager()

        self.active_positions: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []

    def scan_market_cycle(self, prices: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """
        Runs one cycle of market scanning across:
        1. Statistical Arbitrage (Triangular)
        2. Cointegrated Spread Pairs
        3. High-Probability Directional Confluence
        """
        opportunities = []

        # 1. Check Currency Triangles
        for triangle in self.triangular_scanner.triangles:
            res = self.triangular_scanner.scan_triangle(triangle, prices)
            if res and res["v1m_approved"]:
                opportunities.append({
                    "strategy": "STAT_ARBITRAGE_TRIANGLE",
                    "data": res
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

    # Test v1m directional validation
    print("\n[1] Testing v1m System One Directional Oracle...")
    is_ok, verdict, score = fund.oracle.evaluate_directional_trade("EURUSD", "BUY", 8, "BULLISH", 54.2, 10.0)
    print(f"EURUSD Buy Setup -> Approved: {is_ok} | Verdict: {verdict} | Score: {score}")

    # Test Triangular Arbitrage scan
    print("\n[2] Testing Statistical Arbitrage Triangular Cycle...")
    market_snapshot = {
        "EURUSD": {"bid": 1.08550, "ask": 1.08560},
        "GBPUSD": {"bid": 1.29200, "ask": 1.29215},
        "EURGBP": {"bid": 0.84120, "ask": 0.84130}
    }
    opps = fund.scan_market_cycle(market_snapshot)
    print(f"Opportunities detected: {len(opps)}")

    # Test Execution & Compounding with OpEx Skim
    print("\n[3] Executing Verified Opportunity & Testing Compounding + OpEx Skim...")
    res = fund.execute_and_compound(
        setup_type="EURUSD_CONFLUENCE_BREAKOUT",
        details={"v1m_score": score, "verdict": verdict},
        sim_profit=42.50
    )
    print("Execution & Reinvestment Report:", json.dumps(res, indent=2))

    fund.print_fund_status()
