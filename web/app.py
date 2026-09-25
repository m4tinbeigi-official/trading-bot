"""
Lightweight Asynchronous Web Dashboard Server for Rick Sanchez Trading Bot
Built with FastAPI & WebSockets for real-time telemetry, position monitoring, and emergency controls.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from config import config

logger = logging.getLogger("WebDashboard")

app = FastAPI(title="Rick Sanchez MT5 Trading Dashboard")

# Global reference to trading bot state
bot_context: Dict[str, Any] = {
    "engine": None,
    "bridge": None,
    "risk_manager": None,
    "active_clients": set(),
    "bot_running": True
}

def set_bot_context(engine, bridge, risk_manager):
    bot_context["engine"] = engine
    bot_context["bridge"] = bridge
    bot_context["risk_manager"] = risk_manager

@app.get("/")
async def get_index():
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(static_path)

@app.get("/api/status")
async def get_status():
    bridge = bot_context.get("bridge")
    rm = bot_context.get("risk_manager")
    if not bridge:
        return {"status": "INITIALIZING"}
        
    acc = bridge.get_account_info()
    positions = bridge.get_positions()
    history = bridge.simulator.closed_trades if hasattr(bridge, "simulator") else []
    
    return {
        "bot_running": bot_context.get("bot_running", True),
        "execution_mode": bridge.active_mode,
        "account": acc,
        "positions": positions,
        "closed_trades": history[-20:],
        "circuit_breaker": rm.circuit_breaker_tripped if rm else False,
        "circuit_breaker_reason": rm.circuit_breaker_reason if rm else ""
    }

@app.post("/api/panic")
async def panic_close_all():
    """Emergency Panic Button: Immediately liquidates all open positions and pauses bot."""
    bridge = bot_context.get("bridge")
    bot_context["bot_running"] = False
    closed = []
    if bridge:
        closed = bridge.close_all(reason="WEB_PANIC_BUTTON")
    logger.warning("🚨 PANIC BUTTON ACTIVATED: Liquidated all positions and paused trading.")
    return {"status": "SUCCESS", "message": "All positions closed. Bot paused.", "closed_positions": len(closed)}

@app.post("/api/toggle")
async def toggle_bot():
    """Toggles bot execution on/off."""
    bot_context["bot_running"] = not bot_context.get("bot_running", True)
    state = "RESUMED" if bot_context["bot_running"] else "PAUSED"
    logger.info(f"⏯️ Bot execution toggled to: {state}")
    return {"status": "SUCCESS", "bot_running": bot_context["bot_running"]}

@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    bot_context["active_clients"].add(websocket)
    try:
        while True:
            bridge = bot_context.get("bridge")
            rm = bot_context.get("risk_manager")
            if bridge and rm:
                acc = bridge.get_account_info()
                positions = bridge.get_positions()
                history = bridge.simulator.closed_trades if hasattr(bridge, "simulator") else []
                
                # Prices of watched symbols
                quotes = {}
                for s in config.SYMBOLS:
                    quotes[s] = bridge.get_symbol_price(s)

                payload = {
                    "type": "TELEMETRY",
                    "bot_running": bot_context.get("bot_running", True),
                    "execution_mode": bridge.active_mode,
                    "account": acc,
                    "positions": positions,
                    "closed_trades": history[-15:],
                    "quotes": quotes,
                    "circuit_breaker": rm.circuit_breaker_tripped,
                    "circuit_breaker_reason": rm.circuit_breaker_reason
                }
                await websocket.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        bot_context["active_clients"].remove(websocket)
    except Exception as e:
        logger.debug(f"WS Exception: {e}")
        if websocket in bot_context["active_clients"]:
            bot_context["active_clients"].remove(websocket)

# Mount static files (CSS, JS)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")
