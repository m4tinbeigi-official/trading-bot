"""
Alpari MT5 Broker Integration & Configuration Profile
Specifically tuned for Alpari ECN / Pro.ECN accounts operating from Iran.
Handles symbol mapping, ping latency testing, and proxy configuration.
"""

import socket
import time
from typing import Dict, Any, List

ALPARI_CONFIG = {
    "broker_name": "Alpari International / Forex",
    "official_mirror_domains": [
        "https://alpariforex.com",
        "https://alpari.com/fa",
        "https://alparifx.com"
    ],
    "account_types": {
        "ECN_MT5": {
            "name": "ecn.mt5",
            "spread_type": "FLOATING_FROM_0_PIPS",
            "symbol_suffix": ".ecn", # e.g. EURUSD.ecn
            "execution": "MARKET_IOC",
            "min_deposit": 500.0, # Recommended $500 for low margin risk
            "ideal_for": "Algorithmic EAs, Scalping, Triangular Arbitrage"
        },
        "PRO_ECN_MT5": {
            "name": "pro.ecn.mt5",
            "spread_type": "RAW_INTERBANK_0_PIPS",
            "symbol_suffix": ".pro",
            "execution": "MARKET_DIRECT",
            "min_deposit": 500.0,
            "ideal_for": "Institutional Quant Engines, Low-Slippage HFT"
        },
        "STANDARD_MT5": {
            "name": "standard.mt5",
            "spread_type": "FIXED_MARKUP_1.2_PIPS",
            "symbol_suffix": "", # Standard symbols EURUSD
            "execution": "INSTANT_FOK",
            "min_deposit": 100.0,
            "ideal_for": "Manual swing trading (NOT recommended for EAs)"
        }
    },
    "mt5_servers": {
        "demo": "Alpari-MT5-Demo",
        "live": "Alpari-MT5"
    },
    "recommended_pairs": [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "USDCAD", "USDCHF", "EURJPY", "GBPJPY", "XAUUSD"
    ]
}

def get_alpari_symbols(account_type: str = "ECN_MT5") -> List[str]:
    """Returns resolved symbol names for the selected Alpari account type."""
    suffix = ALPARI_CONFIG["account_types"].get(account_type, {}).get("symbol_suffix", "")
    return [s + suffix for s in ALPARI_CONFIG["recommended_pairs"]]

def test_connection_latency(host: str = "127.0.0.1", port: int = 10808) -> Dict[str, Any]:
    """Tests responsiveness of local SOCKS5 proxy or gateway."""
    t0 = time.time()
    try:
        s = socket.create_connection((host, port), timeout=3)
        latency_ms = (time.time() - t0) * 1000.0
        s.close()
        return {"status": "ONLINE", "latency_ms": round(latency_ms, 2), "host": host, "port": port}
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e), "host": host, "port": port}

if __name__ == "__main__":
    print("=" * 60)
    print("  ALPARI BROKER PROFILE & SYMBOL MATRIX  ")
    print("=" * 60)
    for acct, details in ALPARI_CONFIG["account_types"].items():
        symbols = get_alpari_symbols(acct)
        print(f"\n[{acct}] - {details['name']}")
        print(f" • Spread: {details['spread_type']} | Execution: {details['execution']}")
        print(f" • Sample Symbols: {', '.join(symbols[:4])}")
        print(f" • Recommendation: {details['ideal_for']}")

    print("\n[Local Proxy Check for Iran Access]:")
    print(test_connection_latency())
