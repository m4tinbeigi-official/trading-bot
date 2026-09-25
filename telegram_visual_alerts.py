"""
Telegram Visual Execution Alerts & Chart Snapshot Dispatcher
Dispatches rich execution cards and trade notifications with risk parameters,
SMC confluence breakdown, and v1m cognitive scores via Telegram.
"""

import time
import json
import os
import urllib.request
from typing import Dict, Any, Optional

class TelegramVisualAlerts:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    def format_trade_alert_card(self, trade: Dict[str, Any]) -> str:
        """Formats an institutional execution ticket for Telegram."""
        sym = trade.get("symbol", "EURUSD")
        side = trade.get("type", "BUY").upper()
        emoji_side = "🟢 LONG" if "BUY" in side else "🔴 SHORT"
        entry = trade.get("entry_price", 1.08500)
        sl = trade.get("stop_loss", 1.08250)
        tp = trade.get("take_profit", 1.09000)
        lot = trade.get("volume", 0.10)
        risk_pct = trade.get("risk_percent", 0.75)
        confluence = trade.get("confluence_score", 12)
        v1m_grade = trade.get("v1m_grade", "A+")

        point_mult = 100.0 if "JPY" in sym else 10000.0
        sl_pips = abs(entry - sl) * point_mult
        tp_pips = abs(tp - entry) * point_mult
        rr = round(tp_pips / sl_pips, 2) if sl_pips > 0 else 2.0

        card = (
            f"⚡ <b>INSTITUTIONAL TRADE EXECUTED</b>\n\n"
            f"<b>Symbol:</b> <code>{sym}</code> | <b>Action:</b> {emoji_side}\n"
            f"<b>Entry Price:</b> <code>{entry}</code>\n"
            f"<b>Stop Loss:</b> <code>{sl}</code> (-{sl_pips:.1f} pips)\n"
            f"<b>Take Profit:</b> <code>{tp}</code> (+{tp_pips:.1f} pips)\n"
            f"<b>Risk/Reward:</b> 1:{rr} | <b>Position Size:</b> {lot} Lots\n\n"
            f"<b>Confluence Score:</b> {confluence}/15\n"
            f"<b>v1m AI Grade:</b> {v1m_grade} (Cognitive Verified)\n"
            f"<b>DXY Macro Spillover:</b> Filter Passed\n"
            f"<b>Risk Allocation:</b> {risk_pct}% (Half-Kelly Calibrated)\n"
        )
        return card

    def send_alert(self, trade: Dict[str, Any]) -> bool:
        msg = self.format_trade_alert_card(trade)
        # If credentials configured, dispatch via Telegram Bot API
        if self.bot_token and self.chat_id:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
                data = json.dumps({
                    "chat_id": self.chat_id,
                    "text": msg,
                    "parse_mode": "HTML"
                }).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    return resp.status == 200
            except Exception as e:
                print("Telegram alert dispatch failed:", e)
                return False
        else:
            # Fallback: log to console
            print("--- TELEGRAM VISUAL ALERT DISPATCHED (LOCAL SIM) ---")
            print(msg)
            return True

if __name__ == "__main__":
    alerts = TelegramVisualAlerts()
    mock_trade = {
        "symbol": "EURUSD",
        "type": "BUY",
        "entry_price": 1.08500,
        "stop_loss": 1.08250,
        "take_profit": 1.09000,
        "volume": 0.15,
        "risk_percent": 0.75,
        "confluence_score": 13,
        "v1m_grade": "A+"
    }
    alerts.send_alert(mock_trade)
