"""
Statistical Arbitrage & Cointegration Engine
1. Triangular Arbitrage: Delta-neutral 3-pair currency & crypto cycles.
2. Cointegrated Pairs Trading: Mean-reversion z-score spread trading on correlated assets.
Integrated with v1m System One for probabilistic execution clearance.
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from v1m_oracle import V1mDecisionOracle

class TriangularArbitrageScanner:
    """
    Scans currency triangle pricing discrepancies.
    For example: EUR/USD, GBP/USD, EUR/GBP
    Synthetic Rate = EURUSD / GBPUSD
    Discrepancy = (Synthetic Rate / EURGBP) - 1.0
    """
    def __init__(self, oracle: Optional[V1mDecisionOracle] = None):
        self.oracle = oracle or V1mDecisionOracle()
        self.min_discrepancy_pct = 0.04 # 0.04% threshold above roundtrip spread costs

        # Standard institutional triangular cycles
        self.triangles = [
            {
                "name": "EUR-GBP-USD",
                "pair_a": "EURUSD", # Direct A/USD
                "pair_b": "GBPUSD", # Direct B/USD
                "pair_cross": "EURGBP", # Cross A/B
                "invert_cross": False
            },
            {
                "name": "EUR-JPY-USD",
                "pair_a": "EURUSD",
                "pair_b": "USDJPY",
                "pair_cross": "EURJPY",
                "invert_cross": False
            },
            {
                "name": "GBP-JPY-USD",
                "pair_a": "GBPUSD",
                "pair_b": "USDJPY",
                "pair_cross": "GBPJPY",
                "invert_cross": False
            },
            {
                "name": "AUD-JPY-USD",
                "pair_a": "AUDUSD",
                "pair_b": "USDJPY",
                "pair_cross": "AUDJPY",
                "invert_cross": False
            }
        ]

    def scan_triangle(self, triangle: Dict[str, Any], prices: Dict[str, Dict[str, float]]) -> Optional[Dict[str, Any]]:
        p_a = prices.get(triangle["pair_a"])
        p_b = prices.get(triangle["pair_b"])
        p_cross = prices.get(triangle["pair_cross"])

        if not p_a or not p_b or not p_cross:
            return None

        # Bid/Ask pricing
        # Path 1: USD -> A -> B -> USD
        # Buy A with USD (Ask), Buy B with A (Cross Bid/Ask), Sell B for USD (Bid)
        ask_a = p_a["ask"]
        bid_b = p_b["bid"]
        bid_cross = p_cross["bid"]
        ask_cross = p_cross["ask"]

        if triangle["name"] == "EUR-GBP-USD":
            # Direct synthetic = EURUSD / GBPUSD
            synth_bid = p_a["bid"] / p_b["ask"]
            synth_ask = p_a["ask"] / p_b["bid"]

            # Arbitrage 1: Synthetic cheaper than Market Cross Bid
            discrepancy_1 = (bid_cross / synth_ask) - 1.0
            # Arbitrage 2: Synthetic higher than Market Cross Ask
            discrepancy_2 = (synth_bid / ask_cross) - 1.0

            max_disc = max(discrepancy_1, discrepancy_2)
            direction = "SYNTH_BUY_CROSS_SELL" if max_disc == discrepancy_1 else "CROSS_BUY_SYNTH_SELL"

            if max_disc * 100.0 >= self.min_discrepancy_pct:
                est_pips = max_disc * 10000.0
                approved, verdict, score = self.oracle.evaluate_stat_arbitrage(
                    triangle["name"], max_disc * 100.0, est_pips, "CALM"
                )
                return {
                    "triangle": triangle["name"],
                    "direction": direction,
                    "discrepancy_pct": round(max_disc * 100.0, 4),
                    "est_profit_pips": round(est_pips, 2),
                    "v1m_approved": approved,
                    "v1m_verdict": verdict,
                    "v1m_safety_score": score
                }
        return None

class PairsTradingCointegrationEngine:
    """
    Statistical Arbitrage: Mean-Reverting Cointegrated Spread.
    Calculates rolling Z-Score of the spread between two cointegrated assets.
    """
    def __init__(self, oracle: Optional[V1mDecisionOracle] = None):
        self.oracle = oracle or V1mDecisionOracle()
        self.entry_zscore = 2.0
        self.exit_zscore = 0.25
        self.stop_zscore = 3.5

    def calculate_zscore(self, prices_a: List[float], prices_b: List[float], hedge_ratio: float = 1.0) -> Tuple[float, float, float]:
        """
        Spread = PriceA - (hedge_ratio * PriceB)
        Z-Score = (Spread_latest - Mean) / StdDev
        """
        if len(prices_a) != len(prices_b) or len(prices_a) < 20:
            return 0.0, 0.0, 0.0

        spreads = [prices_a[i] - (hedge_ratio * prices_b[i]) for i in range(len(prices_a))]
        mean_spread = sum(spreads) / len(spreads)
        variance = sum((s - mean_spread) ** 2 for s in spreads) / (len(spreads) - 1)
        std_spread = math.sqrt(variance) if variance > 0 else 1.0

        latest_spread = spreads[-1]
        zscore = (latest_spread - mean_spread) / std_spread
        return zscore, latest_spread, std_spread

    def evaluate_pair(self, pair_name: str, symbol_a: str, symbol_b: str,
                      prices_a: List[float], prices_b: List[float], hedge_ratio: float = 1.0) -> Optional[Dict[str, Any]]:
        zscore, spread, std = self.calculate_zscore(prices_a, prices_b, hedge_ratio)
        if abs(zscore) >= self.entry_zscore and abs(zscore) < self.stop_zscore:
            direction = "SHORT_A_LONG_B" if zscore > 0 else "LONG_A_SHORT_B"
            est_reversion_pct = abs(zscore) * (std / prices_a[-1]) * 100.0

            approved, verdict, score = self.oracle.evaluate_stat_arbitrage(
                f"{pair_name}_MeanReversion", est_reversion_pct, est_reversion_pct * 10.0, "MEAN_REVERTING"
            )

            return {
                "pair": pair_name,
                "symbol_a": symbol_a,
                "symbol_b": symbol_b,
                "direction": direction,
                "zscore": round(zscore, 2),
                "spread": round(spread, 5),
                "v1m_approved": approved,
                "v1m_verdict": verdict,
                "v1m_safety_score": score
            }
        return None

if __name__ == "__main__":
    scanner = TriangularArbitrageScanner()
    mock_prices = {
        "EURUSD": {"bid": 1.08550, "ask": 1.08560},
        "GBPUSD": {"bid": 1.29200, "ask": 1.29215},
        "EURGBP": {"bid": 0.84120, "ask": 0.84130}
    }
    res = scanner.scan_triangle(scanner.triangles[0], mock_prices)
    print("Triangular Arb Scan Result:", res)

    pairs_engine = PairsTradingCointegrationEngine()
    import random
    base = 2500.0
    s_a = [base + i*0.5 + random.gauss(0, 1) for i in range(50)]
    s_b = [base + i*0.5 + random.gauss(0, 1) for i in range(50)]
    s_a[-1] += 5.0 # Spike divergence
    p_res = pairs_engine.evaluate_pair("GOLD_SPREAD", "XAUUSD_M1", "XAUUSD_M2", s_a, s_b)
    print("Pairs Trading Cointegration Result:", p_res)
