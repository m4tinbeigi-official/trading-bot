"""
Master Entry Point for Rick Sanchez MT5 Quant Trading Bot
Concurrently orchestrates:
1. MetaTrader 5 Bridge & Real-Time IPC
2. Prop-Firm Risk Manager (Drawdown Guard, Breakeven, Trailing Stop)
3. Multi-Timeframe Trend & ATR Breakout Strategy
4. Asynchronous High-Speed Web Dashboard & WebSocket Telemetry
"""

import sys
import asyncio
import logging
import uvicorn
from datetime import datetime
from typing import Dict, Any, List

from config import config
from risk_manager import RiskManager
from mt5_bridge import MT5Bridge
from strategies.trend_breakout import TrendBreakoutStrategy
from web.app import app, set_bot_context, bot_context

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("MasterEngine")

class TradingEngine:
    def __init__(self, bridge: MT5Bridge, risk_manager: RiskManager, strategy: TrendBreakoutStrategy):
        self.bridge = bridge
        self.risk_manager = risk_manager
        self.strategy = strategy
        self.kline_buffers: Dict[str, List[Dict[str, float]]] = {}
        
        # Initialize synthetic/live candle buffers for each symbol
        self._init_candle_buffers()

    def _init_candle_buffers(self):
        """Pre-populates candle buffers with historical baseline for indicator warm-up."""
        base_prices = {"XAUUSD": 2680.0, "EURUSD": 1.0530, "GBPUSD": 1.2610, "NAS100": 21400.0}
        volatility = {"XAUUSD": 1.8, "EURUSD": 0.0004, "GBPUSD": 0.0005, "NAS100": 15.0}
        
        for sym in config.SYMBOLS:
            p = base_prices.get(sym, 100.0)
            vol = volatility.get(sym, 0.5)
            self.kline_buffers[sym] = []
            curr = p
            for i in range(60):
                drift = (i % 5 - 2) * (vol * 0.4)
                o = curr
                c = o + drift
                h = max(o, c) + vol * 0.3
                l = min(o, c) - vol * 0.3
                curr = c
                self.kline_buffers[sym].append({
                    "open": o, "high": h, "low": l, "close": c, "volume": 100.0
                })

    async def update_candle(self, symbol: str, current_price: float):
        """Appends/updates rolling candle structure with live ticks."""
        buf = self.kline_buffers[symbol]
        last = buf[-1]
        last["high"] = max(last["high"], current_price)
        last["low"] = min(last["low"], current_price)
        last["close"] = current_price
        
        # Advance candle every 15 updates
        if len(buf) > 80:
            buf.pop(0)

    async def run_strategy_cycle(self):
        """Evaluates all symbols, manages open positions and executes signals."""
        if not bot_context.get("bot_running", True):
            return

        acc = self.bridge.get_account_info()
        equity = acc.get("equity", config.INITIAL_BALANCE)
        
        # 1. Prop-Firm Risk & Drawdown Circuit Breaker check
        is_safe, reason = self.risk_manager.check_drawdown_limits(equity)
        if not is_safe:
            logger.warning(f"🚫 Circuit breaker active: {reason}. Skipping new entries.")
            return

        open_positions = self.bridge.get_positions()
        active_symbols = {p["symbol"] for p in open_positions}

        # 2. Check Trailing Stop & Breakeven for Active Positions
        for pos in open_positions:
            sym = pos["symbol"]
            quote = self.bridge.get_symbol_price(sym)
            curr_price = quote["bid"] if pos["side"] == "BUY" else quote["ask"]
            atr = self.strategy.calculate_atr(self.kline_buffers.get(sym, []))
            
            modification = self.risk_manager.evaluate_trailing_and_breakeven(pos, curr_price, atr)
            if modification:
                logger.info(f"🎯 Applying {modification['action']} on #{modification['ticket']} ({sym}): SL -> {modification['new_sl']}")
                self.bridge.modify_order(modification["ticket"], sl=modification["new_sl"])

        # 3. Evaluate New Trade Signals if max open position limit not reached
        if len(open_positions) < config.MAX_OPEN_POSITIONS:
            for symbol in config.SYMBOLS:
                if symbol in active_symbols:
                    continue  # Already have an open trade on this asset

                quote = self.bridge.get_symbol_price(symbol)
                curr_price = quote["ask"]
                await self.update_candle(symbol, curr_price)
                
                signal = self.strategy.evaluate(symbol, curr_price, self.kline_buffers[symbol])
                if signal and signal.action in ["BUY", "SELL"]:
                    lots = self.risk_manager.calculate_lot_size(symbol, signal.entry_price, signal.stop_loss, equity)
                    logger.info(f"✨ Signal Found on {symbol}: {signal.action} {lots} Lots | Reason: {signal.reason}")
                    self.bridge.open_order(
                        symbol=symbol,
                        side=signal.action,
                        volume=lots,
                        sl=signal.stop_loss,
                        tp=signal.take_profit,
                        comment=f"RickQuant_{signal.action}"
                    )
                    break # Allow one new trade per cycle to prevent overexposure

async def main_trading_loop(engine: TradingEngine):
    """Continuous async loop for quantitative analysis & risk auditing."""
    logger.info("⚡ Trading Strategy & Risk Manager loop initialized.")
    while True:
        try:
            await engine.run_strategy_cycle()
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}", exc_info=True)
        await asyncio.sleep(2.0)

async def start_server():
    """Launches Uvicorn Web Server."""
    server_config = uvicorn.Config(
        app=app,
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        log_level="warning"
    )
    server = uvicorn.Server(server_config)
    await server.serve()

async def main():
    logger.info("=" * 65)
    logger.info("🚀 RICK SANCHEZ MT5 QUANT TRADING SUITE STARTING")
    logger.info("=" * 65)
    
    # 1. Initialize Bridge (Auto-detects MT5, falls back to Paper Simulator)
    bridge = MT5Bridge()
    bridge.connect()
    
    # 2. Initialize Risk Manager & Strategy
    risk_manager = RiskManager(initial_balance=config.INITIAL_BALANCE)
    strategy = TrendBreakoutStrategy()
    
    # 3. Initialize Master Engine
    engine = TradingEngine(bridge, risk_manager, strategy)
    
    # 4. Set global web dashboard context
    set_bot_context(engine, bridge, risk_manager)
    
    logger.info(f"🌐 Web Dashboard live at: http://localhost:{config.WEB_PORT}")
    logger.info(f"📈 Execution Mode: {bridge.active_mode}")
    logger.info(f"🛡️ Risk Per Trade: {config.RISK_PER_TRADE_PCT}% | Daily Max DD: {config.MAX_DAILY_DRAWDOWN_PCT}%")
    logger.info("=" * 65)
    
    # Run trading loop and web server concurrently
    await asyncio.gather(
        start_server(),
        main_trading_loop(engine)
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user.")
