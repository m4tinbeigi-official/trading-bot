"""
Mission Control Asynchronous Web Server (v7.50 Quantum Edition)
Built with FastAPI & WebSockets for real-time telemetry, position monitoring,
latency heartbeat watchdog, broker execution auditing, and emergency panic controls.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure root trading-bot dir is on path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from latency_heartbeat_watchdog import HeartbeatWatchdog
from broker_execution_auditor import BrokerExecutionAuditor
from treasury_manager import AutonomousTreasuryManager
from config import config

logger = logging.getLogger("MissionControl")

app = FastAPI(title="Mission Control Quant Suite (v7.50)")

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

def verify_control_auth(request: Request):
    """Enforces authentication token if TRADING_CONTROL_TOKEN is set in environment."""
    required_token = config.CONTROL_TOKEN
    if required_token:
        auth_header = request.headers.get("Authorization", "")
        token = request.headers.get("X-Control-Token")
        if not token and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        if token != required_token:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing control token.")

watchdog = HeartbeatWatchdog(check_interval_s=15)
watchdog.start_background_monitoring()

auditor = BrokerExecutionAuditor()
treasury = AutonomousTreasuryManager()

bot_context: Dict[str, Any] = {
    "engine": None,
    "bridge": None,
    "risk_manager": None,
    "active_clients": set(),
    "bot_running": True,
    "panic_triggered": False
}

def set_bot_context(engine, bridge, risk_manager):
    bot_context["engine"] = engine
    bot_context["bridge"] = bridge
    bot_context["risk_manager"] = risk_manager

@app.get("/")
async def get_index():
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(static_path)

@app.get("/api/mission_control")
async def get_mission_control():
    bridge = bot_context.get("bridge")
    rm = bot_context.get("risk_manager")
    acc = bridge.get_account_info() if bridge else {"balance": 10000.0, "equity": 10000.0, "free_margin": 10000.0, "leverage": 100}
    positions = bridge.get_positions() if bridge else []
    history = bridge.simulator.closed_trades if (bridge and hasattr(bridge, "simulator")) else []

    watchdog_status = watchdog.check_health_cycle()
    treasury_stats = treasury.state

    return {
        "status": "ONLINE",
        "bot_running": bot_context.get("bot_running", True),
        "panic_state": bot_context.get("panic_triggered", False),
        "heartbeat": watchdog_status,
        "treasury": {
            "opex_balance_usd": treasury_stats.get("opex_balance_usd", 0.0),
            "monthly_burn_rate_usd": treasury_stats.get("monthly_burn_rate_usd", 38.0),
            "runway_days": round((treasury_stats.get("opex_balance_usd", 0.0) / (treasury_stats.get("monthly_burn_rate_usd", 38.0) / 30.0)), 1) if treasury_stats.get("monthly_burn_rate_usd", 38.0) > 0 else 0.0,
            "total_reinvested_capital_usd": treasury_stats.get("total_reinvested_capital_usd", 0.0)
        },
        "slippage_auditor": {
            "recent_samples": len(auditor.history),
            "eurusd_stats": auditor.get_symbol_slippage_stats("EURUSD")
        },
        "account": acc,
        "positions": positions,
        "closed_trades": history[-15:]
    }

@app.post("/api/panic", dependencies=[Depends(verify_control_auth)])
async def panic_close_all():
    """Emergency Panic Button: Immediately liquidates all open positions and pauses bot."""
    bridge = bot_context.get("bridge")
    bot_context["bot_running"] = False
    bot_context["panic_triggered"] = True
    closed = []
    if bridge:
        closed = bridge.close_all(reason="MISSION_CONTROL_PANIC_BUTTON")
    logger.warning("🚨 PANIC BUTTON ACTIVATED: Liquidated all positions and paused trading.")
    return {"status": "SUCCESS", "message": "All positions closed. Trading locked.", "closed_positions": len(closed)}

@app.post("/api/resume", dependencies=[Depends(verify_control_auth)])
async def resume_bot():
    bot_context["bot_running"] = True
    bot_context["panic_triggered"] = False
    return {"status": "SUCCESS", "message": "System re-armed and operational."}

@app.post("/api/toggle", dependencies=[Depends(verify_control_auth)])
async def toggle_bot():
    bot_context["bot_running"] = not bot_context.get("bot_running", True)
    state = "RESUMED" if bot_context["bot_running"] else "PAUSED"
    return {"status": "SUCCESS", "bot_running": bot_context["bot_running"]}

@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    bot_context["active_clients"].add(websocket)
    try:
        while True:
            bridge = bot_context.get("bridge")
            rm = bot_context.get("risk_manager")
            acc = bridge.get_account_info() if bridge else {"balance": 10000.0, "equity": 10000.0, "free_margin": 10000.0, "leverage": 100}
            positions = bridge.get_positions() if bridge else []
            history = bridge.simulator.closed_trades if (bridge and hasattr(bridge, "simulator")) else []

            quotes = {}
            if bridge:
                for s in config.SYMBOLS:
                    quotes[s] = bridge.get_symbol_price(s)

            watchdog_status = watchdog.last_status
            treasury_stats = treasury.state
            runway = round((treasury_stats.get("opex_balance_usd", 0.0) / (treasury_stats.get("monthly_burn_rate_usd", 38.0) / 30.0)), 1) if treasury_stats.get("monthly_burn_rate_usd", 38.0) > 0 else 0.0

            payload = {
                "type": "TELEMETRY",
                "bot_running": bot_context.get("bot_running", True),
                "panic_triggered": bot_context.get("panic_triggered", False),
                "execution_mode": bridge.active_mode if bridge else "QUANT_V7_MISSION_CONTROL",
                "account": acc,
                "positions": positions,
                "closed_trades": history[-15:],
                "quotes": quotes,
                "heartbeat": watchdog_status,
                "treasury": {
                    "opex_balance": treasury_stats.get("opex_balance_usd", 0.0),
                    "runway_days": runway
                },
                "circuit_breaker": rm.circuit_breaker_tripped if rm else False,
                "circuit_breaker_reason": rm.circuit_breaker_reason if rm else ""
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        bot_context["active_clients"].remove(websocket)
    except Exception as e:
        if websocket in bot_context["active_clients"]:
            bot_context["active_clients"].remove(websocket)

# Mount static files (CSS, JS)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
