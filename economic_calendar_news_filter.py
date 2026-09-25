"""
Economic Calendar & High-Impact Macro News Filter
Guards the trading engine against catastrophic slippage, spread blowouts,
and erratic whipsaws during major economic releases (NFP, CPI, FOMC, Rate Hikes).
"""

import time
import json
import os
import urllib.request
from typing import Dict, Any, List

CACHE_FILE = os.path.join(os.path.dirname(__file__), "calendar_events_cache.json")

class EconomicCalendarNewsFilter:
    def __init__(self, danger_window_pre_minutes: int = 30, danger_window_post_minutes: int = 30):
        self.pre_mins = danger_window_pre_minutes
        self.post_mins = danger_window_post_minutes
        self.events: List[Dict[str, Any]] = self._load_events()

    def _load_events(self) -> List[Dict[str, Any]]:
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_events_fixture()

    def _default_events_fixture(self) -> List[Dict[str, Any]]:
        """Pre-loaded high-impact calendar baseline."""
        now = time.time()
        return [
            {
                "title": "US Non-Farm Employment Change (NFP)",
                "currency": "USD",
                "impact": "HIGH",
                "timestamp": now + 7200 # 2 hours from now
            },
            {
                "title": "FOMC Federal Funds Rate Decision",
                "currency": "USD",
                "impact": "HIGH",
                "timestamp": now + 86400
            },
            {
                "title": "ECB Monetary Policy Statement",
                "currency": "EUR",
                "impact": "HIGH",
                "timestamp": now + 43200
            }
        ]

    def evaluate_news_veto(self, symbol: str) -> Dict[str, Any]:
        """
        Checks if symbol contains a currency that has an upcoming or recent High-Impact release.
        """
        now = time.time()
        base_curr = symbol[:3].upper()
        quote_curr = symbol[3:6].upper() if len(symbol) >= 6 else ""

        for ev in self.events:
            if ev.get("impact", "").upper() != "HIGH":
                continue

            ev_curr = ev.get("currency", "").upper()
            if ev_curr in [base_curr, quote_curr] or (ev_curr == "USD" and "XAU" in symbol.upper()):
                diff_sec = ev["timestamp"] - now
                diff_min = diff_sec / 60.0

                # Pre-news window: [0, +pre_mins]
                if 0 <= diff_min <= self.pre_mins:
                    return {
                        "vetoed": True,
                        "reason": f"HIGH_IMPACT_NEWS_PRE_RELEASE: {ev['title']} ({ev_curr}) in {int(diff_min)}m",
                        "event": ev["title"],
                        "currency": ev_curr,
                        "countdown_minutes": round(diff_min, 1)
                    }

                # Post-news window: [-post_mins, 0]
                if -self.post_mins <= diff_min < 0:
                    return {
                        "vetoed": True,
                        "reason": f"HIGH_IMPACT_NEWS_POST_SHOCK: {ev['title']} ({ev_curr}) released {int(abs(diff_min))}m ago",
                        "event": ev["title"],
                        "currency": ev_curr,
                        "countdown_minutes": round(diff_min, 1)
                    }

        return {
            "vetoed": False,
            "reason": "CLEAR_MACRO_WINDOW",
            "countdown_minutes": None
        }

if __name__ == "__main__":
    news_filter = EconomicCalendarNewsFilter(danger_window_pre_minutes=30, danger_window_post_minutes=30)
    # Test with custom event inside danger window
    news_filter.events.append({
        "title": "US CPI Inflation MoM",
        "currency": "USD",
        "impact": "HIGH",
        "timestamp": time.time() + 900 # in 15 mins
    })
    res_eur = news_filter.evaluate_news_veto("EURUSD")
    print("EURUSD News Veto:", res_eur)
    res_chf = news_filter.evaluate_news_veto("GBPCHF")
    print("GBPCHF News Veto:", res_chf)
