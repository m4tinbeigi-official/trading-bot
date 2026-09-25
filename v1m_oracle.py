"""
v1m System One Probabilistic Decision Oracle
Connects to https://v1m.ir/v1/systemone to provide sub-10ms calibrated AI evaluations
for trading setups, statistical arbitrage, and portfolio risk management.
"""

import os
import json
import ssl
import urllib.request
from typing import Dict, Any, Tuple

V1M_API_URL = "https://v1m.ir/v1/systemone"
V1M_DEFAULT_KEY = "v1m_live_5aa832d4e501329ad3fcf890e7050661a3738b985690555f"

class V1mDecisionOracle:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("V1M_API_KEY", V1M_DEFAULT_KEY)
        try:
            self.ctx = ssl.create_default_context()
        except Exception:
            # Ponytail: Fallback to unverified context if local CA certs missing on macOS
            self.ctx = ssl._create_unverified_context()
        self.timeout = 8

    def _query_v1m(self, state: str, questions: Dict[str, Any]) -> Dict[str, Any]:
        """Send System One evaluation request to v1m.ir."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "InstitutionalQuantFund/1.0"
        }
        payload = {
            "state": state,
            "questions": questions
        }
        try:
            req = urllib.request.Request(V1M_API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, context=self.ctx, timeout=self.timeout) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            try:
                unverified_ctx = ssl._create_unverified_context()
                req = urllib.request.Request(V1M_API_URL, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, context=unverified_ctx, timeout=self.timeout) as resp:
                    if resp.status == 200:
                        return json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                return {"error": str(e), "fallback": True}
        return {"error": "unknown_failure", "fallback": True}

    def evaluate_directional_trade(self, symbol: str, direction: str, confluence_score: int, 
                                   macro_trend: str, rsi_val: float, spread: float) -> Tuple[bool, str, float]:
        """
        Evaluate directional breakout / confluence setup with v1m.
        Returns: (is_approved, verdict, confidence_score)
        """
        state_desc = (
            f"Symbol: {symbol} | Action: {direction} | Macro Trend: {macro_trend} | "
            f"Confluence Score: {confluence_score}/10 | RSI(14): {rsi_val:.1f} | Spread: {spread:.1f} pts. "
            f"Execution session active with clean breakout structure."
        )

        questions = {
            "trade_quality": {
                "type": "choice",
                "instructions": "Determine trade setup quality and execution probability:",
                "criteria": {
                    "a_plus": "Prime confluence setup, clean trend alignment, minimal fakeout risk",
                    "b_grade": "Acceptable setup with minor divergence or moderate spread",
                    "avoid": "High risk of fakeout, choppy consolidation, or adverse market regime"
                }
            },
            "momentum_confidence": {
                "type": "score",
                "instructions": "Rate institutional continuation confidence (0 to 2):",
                "criteria": [
                    "Weak momentum, likely mean-reverting chop",
                    "Moderate continuation probability",
                    "Strong institutional momentum follow-through"
                ]
            }
        }

        res = self._query_v1m(state_desc, questions)
        if res.get("fallback"):
            # Safe algorithmic fallback
            approved = (confluence_score >= 7 and spread <= 30)
            return approved, "local_rule_fallback", 1.0

        answers = res.get("answers", {})
        choice = answers.get("trade_quality", {}).get("choice", "avoid")
        score = answers.get("momentum_confidence", {}).get("score", 0.0)

        is_approved = (choice in ["a_plus", "b_grade"]) and (score >= 0.8)
        return is_approved, choice, float(score)

    def evaluate_stat_arbitrage(self, triangle_name: str, discrepancy_pct: float, 
                                est_profit_pips: float, current_volatility: str) -> Tuple[bool, str, float]:
        """
        Evaluate statistical or triangular arbitrage opportunity.
        Returns: (should_execute, verdict, safety_score)
        """
        state_desc = (
            f"Statistical Arbitrage Cycle: {triangle_name} | "
            f"Gross Discrepancy: {discrepancy_pct:.4f}% | Est Net Profit: {est_profit_pips:.2f} pips | "
            f"Market Volatility: {current_volatility}. Zero directional exposure."
        )

        questions = {
            "execution_verdict": {
                "type": "choice",
                "instructions": "Decide on arbitrage cycle execution:",
                "criteria": {
                    "execute": "Opportunity is mathematically verified, positive net edge after roundtrip fees",
                    "hold": "Marginal spread, risk of slippage eroding edge",
                    "reject": "Excessive execution risk or stale quote discrepancy"
                }
            },
            "safety_score": {
                "type": "score",
                "instructions": "Rate execution safety (0=Dangerous, 2=Guaranteed Delta Neutral Edge):",
                "criteria": [
                    "High slippage risk, negative net expectancy",
                    "Acceptable edge, moderate execution certainty",
                    "High confidence, verified delta-neutral edge"
                ]
            }
        }

        res = self._query_v1m(state_desc, questions)
        if res.get("fallback"):
            approved = (discrepancy_pct >= 0.05 and est_profit_pips >= 1.0)
            return approved, "local_rule_fallback", 1.0

        answers = res.get("answers", {})
        choice = answers.get("execution_verdict", {}).get("choice", "reject")
        score = answers.get("safety_score", {}).get("score", 0.0)

        should_execute = (choice == "execute") and (score >= 0.8)
        return should_execute, choice, float(score)

if __name__ == "__main__":
    oracle = V1mDecisionOracle()
    approved, choice, score = oracle.evaluate_directional_trade("EURUSD", "BUY", 8, "BULLISH", 56.4, 12.0)
    print(f"Directional Trade Test -> Approved: {approved} | Choice: {choice} | Score: {score}")

    arb_approved, arb_choice, arb_score = oracle.evaluate_stat_arbitrage("EUR/USD-GBP/USD-EUR/GBP", 0.12, 3.4, "LOW_VOLATILITY")
    print(f"Stat Arb Test -> Approved: {arb_approved} | Choice: {arb_choice} | Score: {arb_score}")
