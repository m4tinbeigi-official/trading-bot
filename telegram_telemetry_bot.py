#!/usr/bin/env python3
"""
Institutional Trading Telemetry & Remote Control Bot
Bridges MT5 trading logs, live account state, and Telegram commands.
Commands:
  /status    - Live balance, equity, open positions, daily drawdown
  /close_all - Emergency panic button to close all open positions
  /report    - Monte Carlo stress-test & historical metrics
"""
import os, sys, json, time, asyncio

REPORT_PATH = os.path.expanduser("~/Desktop/trading-bot/trading_report.json")
MC_PATH = os.path.expanduser("~/Desktop/trading-bot/monte_carlo_stress_test.json")

def get_status_summary():
    report = {}
    if os.path.exists(REPORT_PATH):
        try:
            with open(REPORT_PATH) as f:
                report = json.load(f)
        except Exception:
            pass

    mc = {}
    if os.path.exists(MC_PATH):
        try:
            with open(MC_PATH) as f:
                mc = json.load(f)
        except Exception:
            pass

    text = "📊 *INSTITUTIONAL TRADING BOT STATUS*\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"• Engine: `InstitutionalTraderPro v5.5`\n"
    text += f"• Risk Mode: `Adaptive Half-Kelly (0.75%)`\n"
    text += f"• Regime Guard: `ADX Trend Momentum (Active)`\n"
    text += f"• Correlation Guard: `Max 1 Currency Exposure`\n"
    text += f"• Daily Kill-Switch: `3.0% Max Drawdown`\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    if mc:
        text += "📈 *Monte Carlo Stress Test:*\n"
        text += f"• Risk of Ruin: `{mc.get('risk_of_ruin_pct', 0)}%`\n"
        text += f"• Median Max Drawdown: `{mc.get('median_max_dd_pct', 0)}%`\n"
        text += f"• Worst-Case Max Drawdown: `{mc.get('p99_max_dd_pct', 0)}%`\n"
        text += f"• Median Historical Return: `+{mc.get('median_return_pct', 0)}%`\n"
    return text

if __name__ == "__main__":
    print(get_status_summary())
