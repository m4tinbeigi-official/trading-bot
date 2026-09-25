"""
Autonomous Self-Funding & Treasury Manager
Allocates a designated percentage of net trading profits into an Autonomous OpEx Reserve
to cover infrastructure costs (VPS, proxies, LLM quotas, domain renewals).
Tracks runway, operational burn rate, and crypto settlement ledgers.
"""

import os
import json
import time
from typing import Dict, Any, List

LEDGER_PATH = os.path.expanduser("~/Desktop/trading-bot/treasury_ledger.json")

class AutonomousTreasuryManager:
    def __init__(self, ledger_file: str = LEDGER_PATH, opex_allocation_pct: float = 15.0):
        self.ledger_file = ledger_file
        self.opex_allocation_pct = opex_allocation_pct
        self.state = self._load_ledger()

    def _default_state(self) -> Dict[str, Any]:
        return {
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_gross_profit_usd": 0.0,
            "total_reinvested_capital_usd": 0.0,
            "total_opex_allocated_usd": 0.0,
            "opex_balance_usd": 0.0,
            "monthly_burn_rate_usd": 38.0, # $10 VPS + $8 Proxy + $15 LLM API + $5 Domain
            "expenses": [
                {"category": "Cloud VPS Hosting (ManageIt Cloud)", "monthly_est": 10.0, "status": "HOLD_NO_AUTOPAY"},
                {"category": "SOCKS5 Proxy & Relays", "monthly_est": 8.0, "status": "ACTIVE"},
                {"category": "v1m / 9Router AI Quotas", "monthly_est": 15.0, "status": "ACTIVE"},
                {"category": "Domains & SSL Renewal (Selva.ir)", "monthly_est": 5.0, "status": "ACTIVE"}
            ],
            "settlement_wallets": {
                "USDT_TRC20": "TXYZAutonomousTradingTreasury999",
                "TON": "EQAutonomousFundOperationsReserve001",
                "SOL": "AutonomousFundTreasuryOpsSoL999"
            },
            "payout_history": [],
            "transactions": []
        }

    def _load_ledger(self) -> Dict[str, Any]:
        if os.path.exists(self.ledger_file):
            try:
                with open(self.ledger_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_state()

    def save_ledger(self):
        with open(self.ledger_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def process_closed_trade_pnl(self, net_profit_usd: float, trade_id: str) -> Dict[str, Any]:
        """
        When a trade closes in profit, skim 15% to OpEx Treasury,
        and reinvest 85% into compounding base capital.
        """
        if net_profit_usd <= 0:
            return {"status": "LOSS_NO_OPEX_SKIM", "amount": 0.0}

        opex_cut = net_profit_usd * (self.opex_allocation_pct / 100.0)
        reinvest_cut = net_profit_usd - opex_cut

        self.state["total_gross_profit_usd"] = round(self.state["total_gross_profit_usd"] + net_profit_usd, 2)
        self.state["total_opex_allocated_usd"] = round(self.state["total_opex_allocated_usd"] + opex_cut, 2)
        self.state["opex_balance_usd"] = round(self.state["opex_balance_usd"] + opex_cut, 2)
        self.state["total_reinvested_capital_usd"] = round(self.state["total_reinvested_capital_usd"] + reinvest_cut, 2)

        tx = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "trade_id": trade_id,
            "gross_profit": round(net_profit_usd, 2),
            "opex_allocation": round(opex_cut, 2),
            "reinvested": round(reinvest_cut, 2)
        }
        self.state["transactions"].append(tx)
        self.save_ledger()

        burn_daily = self.state["monthly_burn_rate_usd"] / 30.0
        runway_days = self.state["opex_balance_usd"] / burn_daily if burn_daily > 0 else 999.0

        return {
            "status": "OPEX_FUNDS_ALLOCATED",
            "gross_profit": round(net_profit_usd, 2),
            "opex_skim": round(opex_cut, 2),
            "reinvested": round(reinvest_cut, 2),
            "current_opex_balance": round(self.state["opex_balance_usd"], 2),
            "runway_days": round(runway_days, 1)
        }

    def record_expense_payout(self, amount_usd: float, category: str, wallet: str) -> Dict[str, Any]:
        """Deduct an operating cost payout from treasury."""
        if self.state["opex_balance_usd"] < amount_usd:
            return {"status": "INSUFFICIENT_OPEX_FUNDS", "balance": self.state["opex_balance_usd"]}

        self.state["opex_balance_usd"] = round(self.state["opex_balance_usd"] - amount_usd, 2)
        payout = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "amount_usd": amount_usd,
            "category": category,
            "wallet": wallet
        }
        self.state["payout_history"].append(payout)
        self.save_ledger()
        return {"status": "PAYOUT_COMPLETED", "remaining_balance": self.state["opex_balance_usd"]}

    def get_summary(self) -> str:
        burn_daily = self.state["monthly_burn_rate_usd"] / 30.0
        runway_days = self.state["opex_balance_usd"] / burn_daily if burn_daily > 0 else 999.0

        lines = [
            "🏛️ AUTONOMOUS TREASURY & SELF-FUNDING LEDGER",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• Gross Trading Profit:      ${self.state['total_gross_profit_usd']:.2f} USD",
            f"• Reinvested to Compounding:  ${self.state['total_reinvested_capital_usd']:.2f} USD (85%)",
            f"• OpEx Reserve Allocated:    ${self.state['total_opex_allocated_usd']:.2f} USD (15%)",
            f"• Current OpEx Balance:      ${self.state['opex_balance_usd']:.2f} USD",
            f"• Estimated Monthly Burn:    ${self.state['monthly_burn_rate_usd']:.2f} USD/mo",
            f"• Operations Runway:         {runway_days:.1f} Days Covered",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ]
        return "\n".join(lines)

if __name__ == "__main__":
    treasury = AutonomousTreasuryManager()
    res = treasury.process_closed_trade_pnl(net_profit_usd=85.0, trade_id="TEST_DEAL_001")
    print(res)
    print("\n" + treasury.get_summary())
