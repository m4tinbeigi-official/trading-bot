"""
MetaTrader 5 Python Bridge with Seamless Paper Simulator Fallback
Connects to MT5 Terminal over ZeroMQ or falls back to built-in Paper Trading Engine.
Zero heavy dependencies, 100% cross-platform compatible with macOS, Windows & Linux VPS.
"""

import sys
import json
import logging
import zmq
from typing import Dict, Any, List, Optional
from config import config
from paper_simulator import PaperSimulator

logger = logging.getLogger("MT5Bridge")

class MT5Bridge:
    def __init__(self, host: str = config.MT5_HOST, port: int = config.MT5_REQ_PORT):
        self.host = host
        self.port = port
        self.context = zmq.Context()
        self.socket_req = None
        self.is_connected = False
        self.simulator = PaperSimulator(initial_balance=config.INITIAL_BALANCE)
        self.active_mode = "PAPER" # 'MT5' or 'PAPER'

    def connect(self) -> bool:
        """Attempts connection to MetaTrader 5 Expert Advisor via ZeroMQ."""
        if config.EXECUTION_MODE == "PAPER":
            logger.info("ℹ️ Execution mode configured to PAPER. Using local simulator.")
            self.active_mode = "PAPER"
            return True

        try:
            logger.info(f"🔌 Connecting to MT5 ZeroMQ EA at tcp://{self.host}:{self.port}...")
            self.socket_req = self.context.socket(zmq.REQ)
            self.socket_req.setsockopt(zmq.RCVTIMEO, config.MT5_TIMEOUT_MS)
            self.socket_req.setsockopt(zmq.LINGER, 0)
            self.socket_req.connect(f"tcp://{self.host}:{self.port}")
            
            # Send test ping
            reply = self.send_command({"action": "PING"})
            if reply and reply.get("status") == "OK":
                self.is_connected = True
                self.active_mode = "MT5"
                logger.info("✅ Connected to MetaTrader 5 Terminal successfully!")
                return True
            else:
                logger.warning("⚠️ MT5 EA did not reply to PING. Activating fallback Paper Simulator.")
                self.active_mode = "PAPER"
                return False
        except Exception as e:
            logger.warning(f"⚠️ Could not reach MT5 EA ({e}). Defaulting to Paper Simulator mode.")
            self.active_mode = "PAPER"
            return False

    def send_command(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Sends JSON packet to MT5 EA and awaits reply."""
        if self.active_mode == "PAPER" or not self.socket_req:
            return None
        try:
            self.socket_req.send_string(json.dumps(payload))
            msg = self.socket_req.recv_string()
            return json.loads(msg)
        except zmq.Again:
            logger.warning("⚠️ MT5 ZMQ request timed out.")
            return None
        except Exception as e:
            logger.error(f"Error communicating with MT5: {e}")
            return None

    def get_account_info(self) -> Dict[str, Any]:
        """Fetches account details (balance, equity, margin, leverage)."""
        if self.active_mode == "MT5" and self.is_connected:
            res = self.send_command({"action": "ACCOUNT_INFO"})
            if res and "data" in res:
                res["data"]["mode"] = "LIVE_MT5"
                return res["data"]
        return self.simulator.get_account_info()

    def get_symbol_price(self, symbol: str) -> Dict[str, float]:
        """Fetches real-time Bid/Ask quote for a symbol."""
        if self.active_mode == "MT5" and self.is_connected:
            res = self.send_command({"action": "GET_TICK", "symbol": symbol})
            if res and "data" in res:
                return res["data"]
        return self.simulator.simulate_price_step(symbol)

    def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieves list of active open positions."""
        if self.active_mode == "MT5" and self.is_connected:
            res = self.send_command({"action": "GET_POSITIONS"})
            if res and "data" in res:
                return res["data"]
        return self.simulator.get_positions()

    def open_order(self, symbol: str, side: str, volume: float, sl: float = 0.0, tp: float = 0.0, comment: str = "RickSanchezBot") -> Dict[str, Any]:
        """Submits a new market order."""
        if self.active_mode == "MT5" and self.is_connected:
            cmd = {
                "action": "ORDER_OPEN",
                "symbol": symbol,
                "type": side.upper(),
                "volume": float(volume),
                "sl": float(sl),
                "tp": float(tp),
                "comment": comment
            }
            res = self.send_command(cmd)
            if res:
                return res
        return self.simulator.open_order(symbol, side, volume, sl, tp, comment)

    def modify_order(self, ticket: int, sl: float, tp: Optional[float] = None) -> Dict[str, Any]:
        """Updates Stop Loss or Take Profit of an active trade."""
        if self.active_mode == "MT5" and self.is_connected:
            cmd = {"action": "ORDER_MODIFY", "ticket": ticket, "sl": float(sl)}
            if tp is not None:
                cmd["tp"] = float(tp)
            res = self.send_command(cmd)
            if res:
                return res
        return self.simulator.modify_order(ticket, sl, tp)

    def close_order(self, ticket: int, reason: str = "MANUAL") -> Dict[str, Any]:
        """Closes a specific open position."""
        if self.active_mode == "MT5" and self.is_connected:
            res = self.send_command({"action": "ORDER_CLOSE", "ticket": ticket, "reason": reason})
            if res:
                return res
        return self.simulator.close_order(ticket, reason=reason)

    def close_all(self, reason: str = "PANIC_BUTTON") -> List[Dict[str, Any]]:
        """Emergency command: Closes all active open positions."""
        if self.active_mode == "MT5" and self.is_connected:
            res = self.send_command({"action": "ORDER_CLOSE_ALL", "reason": reason})
            if res and "data" in res:
                return res["data"]
        return self.simulator.close_all(reason=reason)
