"""
Broker Execution & Slippage Auditor Engine (v7.50 Mission Control)
Tracks and logs:
1. Exact Price Requested vs Exact Price Filled by Broker (Alpari MT5)
2. Asymmetric Negative Slippage Detection (Broker Dealing Desk Manipulation)
3. Execution Latency (Request to OrderFill Round-Trip)
4. Auto-Quarantine of Abusive Symbols
"""

import time
import json
import os
from typing import Dict, Any, List

AUDIT_LOG_FILE = os.path.join(os.path.dirname(__file__), "slippage_audit.json")

class BrokerExecutionAuditor:
    def __init__(self, max_allowed_negative_slippage_pips: float = 1.5):
        self.max_slippage_pips = max_allowed_negative_slippage_pips
        self.history: List[Dict[str, Any]] = self._load_audit_log()

    def _load_audit_log(self) -> List[Dict[str, Any]]:
        if os.path.exists(AUDIT_LOG_FILE):
            try:
                with open(AUDIT_LOG_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_audit_log(self):
        try:
            with open(AUDIT_LOG_FILE, "w") as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print("Failed to save slippage audit log:", e)

    def record_execution(self, symbol: str, order_type: str, requested_price: float, filled_price: float, execution_ms: float, volume_lot: float) -> Dict[str, Any]:
        """
        Calculates slippage:
        For BUY: Slippage = Filled Price - Requested Price (Positive is BAD/negative slippage)
        For SELL: Slippage = Requested Price - Filled Price (Positive is BAD/negative slippage)
        """
        is_buy = order_type.upper() in ["BUY", "ORDER_TYPE_BUY"]
        point_multiplier = 100.0 if "JPY" in symbol.upper() else 10000.0

        if is_buy:
            raw_diff = filled_price - requested_price
        else:
            raw_diff = requested_price - filled_price

        slippage_pips = round(raw_diff * point_multiplier, 2)
        is_harmful = slippage_pips > self.max_slippage_pips

        entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
            "symbol": symbol,
            "order_type": order_type,
            "volume_lot": volume_lot,
            "requested_price": requested_price,
            "filled_price": filled_price,
            "slippage_pips": slippage_pips,
            "slippage_type": "NEGATIVE (BAD)" if slippage_pips > 0 else "POSITIVE (FAVORABLE)",
            "execution_ms": round(execution_ms, 1),
            "flagged_harmful": is_harmful
        }

        self.history.append(entry)
        self._save_audit_log()

        return entry

    def get_symbol_slippage_stats(self, symbol: str, lookback: int = 20) -> Dict[str, Any]:
        sym_records = [r for r in self.history if r["symbol"].upper() == symbol.upper()][-lookback:]
        if not sym_records:
            return {"symbol": symbol, "samples": 0, "avg_slippage_pips": 0.0, "status": "CLEAN"}

        avg_slip = sum(r["slippage_pips"] for r in sym_records) / len(sym_records)
        harmful_count = sum(1 for r in sym_records if r["flagged_harmful"])

        status = "NORMAL"
        if avg_slip > 1.2 or (harmful_count / len(sym_records)) >= 0.4:
            status = "SUSPICIOUS_BROKER_DEALING_DESK"

        return {
            "symbol": symbol,
            "samples": len(sym_records),
            "avg_slippage_pips": round(avg_slip, 2),
            "harmful_executions": harmful_count,
            "status": status,
            "quarantine_recommended": status == "SUSPICIOUS_BROKER_DEALING_DESK"
        }

if __name__ == "__main__":
    auditor = BrokerExecutionAuditor(max_allowed_negative_slippage_pips=1.5)
    rec1 = auditor.record_execution("EURUSD", "BUY", 1.08500, 1.08502, execution_ms=88.5, volume_lot=0.10)
    print("Execution Logged:", rec1)
    stats = auditor.get_symbol_slippage_stats("EURUSD")
    print("EURUSD Slippage Audit Stats:", stats)
