"""
Session Liquidity & Spread Fluctuation Auditor (Q1 Days 11-20)
Audits institutional session liquidity regimes:
1. Tokyo Open (Asian Session)
2. London Open (European Session)
3. New York Open & London Overlap (Peak Global Liquidity)
4. Rollover / Spread Widening Witching Hour (21:00 - 23:00 UTC)
"""

import time
from typing import Dict, Any, Optional

class SessionLiquidityAuditor:
    def __init__(self, max_allowed_spread_expansion_mult: float = 2.0):
        self.max_spread_mult = max_allowed_spread_expansion_mult

    def get_current_session(self, utc_hour: Optional[int] = None) -> Dict[str, Any]:
        if utc_hour is None:
            utc_hour = time.gmtime().tm_hour

        # Categorize session
        if 21 <= utc_hour or utc_hour < 0:
            return {
                "session": "ROLLOVER_WITCHING_HOUR",
                "liquidity_tier": "CRITICAL_LOW",
                "typical_spread_mult": 3.0,
                "allow_new_entries": False,
                "reason": "Broker spread expansion and low interbank liquidity during rollover"
            }
        elif 0 <= utc_hour < 7:
            return {
                "session": "TOKYO_ASIAN",
                "liquidity_tier": "MODERATE",
                "typical_spread_mult": 1.2,
                "allow_new_entries": True,
                "reason": "Asian session range-bound trading"
            }
        elif 7 <= utc_hour < 12:
            return {
                "session": "LONDON_OPEN",
                "liquidity_tier": "HIGH",
                "typical_spread_mult": 1.0,
                "allow_new_entries": True,
                "reason": "European institutional volume expansion"
            }
        elif 12 <= utc_hour < 16:
            return {
                "session": "LONDON_NY_OVERLAP",
                "liquidity_tier": "PEAK_INSTITUTIONAL",
                "typical_spread_mult": 0.9,
                "allow_new_entries": True,
                "reason": "Highest global liquidity and tightest spreads"
            }
        else: # 16 to 21
            return {
                "session": "NEW_YORK_AFTERNOON",
                "liquidity_tier": "MODERATE_DECLINING",
                "typical_spread_mult": 1.1,
                "allow_new_entries": True,
                "reason": "US afternoon volume tapering"
            }

    def evaluate_entry_spread_suitability(self, symbol: str, current_spread_pips: float, baseline_spread_pips: float = 1.0) -> Dict[str, Any]:
        session_info = self.get_current_session()
        if not session_info["allow_new_entries"]:
            return {
                "approved": False,
                "veto_reason": f"ENTRY_BLOCKED_BY_SESSION: {session_info['session']} ({session_info['reason']})",
                "session_info": session_info
            }

        expansion = current_spread_pips / baseline_spread_pips if baseline_spread_pips > 0 else 1.0
        if expansion > self.max_spread_mult:
            return {
                "approved": False,
                "veto_reason": f"EXCESSIVE_SPREAD_EXPANSION: Current {current_spread_pips:.1f} pips is {expansion:.1f}x baseline",
                "session_info": session_info
            }

        return {
            "approved": True,
            "veto_reason": None,
            "session_info": session_info
        }

if __name__ == "__main__":
    auditor = SessionLiquidityAuditor()
    print("Current Session Status:", auditor.get_current_session())
    # Test London Overlap
    print("London Overlap Check:", auditor.get_current_session(utc_hour=14))
    # Test Rollover hour
    print("Rollover Witching Hour Check:", auditor.get_current_session(utc_hour=22))
