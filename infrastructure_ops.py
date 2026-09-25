"""
Autonomous Infrastructure & Cloud Operations Manager
- VPS Hosting & Server Renewals: ManageIt Cloud (https://api.manageit.dev)
  Note: AUTO_PURCHASE is strictly set to FALSE (DRY-RUN / HOLD mode).
- Domain Management & Renewals: Selva.ir (NIC Registry)
Integrated with Autonomous Treasury to project and allocate infrastructure funds.
"""

import os
import json
import time
from typing import Dict, Any, List

MANAGEIT_API_BASE = "https://api.manageit.dev/api/v1"
MANAGEIT_PROJECT_ID = "taQtAt4y7y"

class InfrastructureManager:
    def __init__(self, treasury_manager=None):
        self.treasury = treasury_manager
        # Strict rule: Autonomous purchases are DISABLED until user gives explicit instruction
        self.auto_purchase_enabled = False # HOLD mode: Do not purchase automatically
        self.preferred_vps_provider = "ManageIt Cloud (manageit.dev)"
        self.preferred_domain_registrar = "Selva.ir (.ir / NIC.ir Registry)"

    def get_vps_config(self) -> Dict[str, Any]:
        return {
            "provider": self.preferred_vps_provider,
            "api_endpoint": MANAGEIT_API_BASE,
            "project_id": MANAGEIT_PROJECT_ID,
            "auto_purchase_active": self.auto_purchase_enabled,
            "status": "ARMED_STANDBY (DRY-RUN / NO PURCHASE)",
            "monthly_estimate_usd": 10.0,
            "notes": "Configured for Frankfurt / London low-latency co-location when activated."
        }

    def get_domain_config(self) -> Dict[str, Any]:
        return {
            "registrar": self.preferred_domain_registrar,
            "account": "eisa.nikouman@gmail.com",
            "default_nameservers": ["k.ns.arvancdn.ir", "z.ns.arvancdn.ir"],
            "auto_renew_enabled": True,
            "annual_estimate_rial": 820000, # Selva 1-year .ir rate + tax
            "status": "ACTIVE_MONITORING"
        }

    def check_renewal_status(self) -> Dict[str, Any]:
        """Audit upcoming infrastructure expenses and treasury coverage."""
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "vps": self.get_vps_config(),
            "domain": self.get_domain_config(),
            "policy": {
                "server_purchase_state": "HELD_NO_AUTOPAY",
                "domain_renewal_state": "ROUTE_TO_SELVA"
            }
        }

if __name__ == "__main__":
    infra = InfrastructureManager()
    print("=" * 60)
    print("  AUTONOMOUS INFRASTRUCTURE CONFIGURATION  ")
    print("=" * 60)
    print(json.dumps(infra.check_renewal_status(), indent=2))
