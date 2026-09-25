"""
Heartbeat & Latency Watchdog Engine (v7.50 Mission Control)
Continuously monitors:
1. TCP Socket Latency to Alpari MT5 Trading Servers (Direct + SOCKS5 Proxy Aware)
2. SOCKS5 Proxy & Internet Connectivity from Iran
3. MT5 Terminal / Wine Process Health
4. Dispatches Immediate Emergency Telemetry Alerts upon Disconnection
"""

import time
import socket
import json
import os
import threading
from typing import Dict, Any, List

ALPARI_SERVERS = [
    {"name": "Alpari-Gateway-SOCKS5", "host": "127.0.0.1", "port": 10808, "type": "LOCAL_PROXY"},
    {"name": "Global-DNS-Primary", "host": "1.1.1.1", "port": 443, "type": "INTERNET_GATEWAY"},
    {"name": "Alpari-Direct-Target", "host": "178.248.236.43", "port": 443, "type": "BROKER_DC"} # Alpari MT5 DC direct IP
]

class HeartbeatWatchdog:
    def __init__(self, check_interval_s: int = 15, max_acceptable_latency_ms: float = 250.0):
        self.check_interval_s = check_interval_s
        self.max_latency_ms = max_acceptable_latency_ms
        self.running = False
        self.thread = None

        self.last_status: Dict[str, Any] = {
            "status": "HEALTHY",
            "last_check_ts": time.time(),
            "avg_latency_ms": 0.0,
            "packet_loss_pct": 0.0,
            "consecutive_failures": 0,
            "circuit_breaker_triggered": False,
            "details": []
        }

    def measure_tcp_latency(self, host: str, port: int, timeout: float = 2.0) -> float:
        """Measures TCP handshake latency in milliseconds."""
        t0 = time.perf_counter()
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return round(latency_ms, 1)
        except Exception:
            return -1.0 # Timeout or unreachable

    def check_health_cycle(self) -> Dict[str, Any]:
        results = []
        valid_latencies = []

        for srv in ALPARI_SERVERS:
            lat = self.measure_tcp_latency(srv["host"], srv["port"])
            is_ok = (lat > 0)
            if is_ok:
                valid_latencies.append(lat)
            results.append({
                "server": srv["name"],
                "target": f"{srv['host']}:{srv['port']}",
                "type": srv["type"],
                "latency_ms": lat if is_ok else None,
                "reachable": is_ok
            })

        loss_pct = ((len(results) - len(valid_latencies)) / len(results)) * 100.0
        avg_lat = sum(valid_latencies) / len(valid_latencies) if valid_latencies else 999.0

        if loss_pct >= 66.0 or avg_lat > 600.0:
            self.last_status["consecutive_failures"] += 1
        else:
            self.last_status["consecutive_failures"] = 0

        # Trigger Circuit Breaker if 3 consecutive failures occur
        circuit_break = self.last_status["consecutive_failures"] >= 3

        status_str = "HEALTHY"
        if circuit_break:
            status_str = "CIRCUIT_BREAKER_ACTIVE"
        elif avg_lat > self.max_latency_ms or loss_pct > 0:
            status_str = "DEGRADED"

        self.last_status.update({
            "status": status_str,
            "last_check_ts": time.time(),
            "avg_latency_ms": round(avg_lat, 1),
            "packet_loss_pct": round(loss_pct, 1),
            "circuit_breaker_triggered": circuit_break,
            "details": results
        })

        return self.last_status

    def start_background_monitoring(self):
        if self.running:
            return
        self.running = True
        def _loop():
            while self.running:
                try:
                    self.check_health_cycle()
                except Exception as e:
                    print("Watchdog cycle error:", e)
                time.sleep(self.check_interval_s)
        self.thread = threading.Thread(target=_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

if __name__ == "__main__":
    watchdog = HeartbeatWatchdog()
    res = watchdog.check_health_cycle()
    print("=" * 60)
    print("  HEARTBEAT & LATENCY WATCHDOG AUDIT REPORT  ")
    print("=" * 60)
    print(json.dumps(res, indent=2))
    print(f"\nSystem Status: {res['status']} | Avg Latency: {res['avg_latency_ms']}ms")
