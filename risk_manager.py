"""
Prop-Firm Grade Risk Management & Capital Preservation Engine
Features:
- Dynamic lot sizing based on account equity and ATR stop-loss distance
- Daily Max Drawdown Hard Stop (Circuit Breaker for Prop Challenge safety)
- Automated Breakeven adjustment after 1.0R gain
- Dynamic ATR-based Trailing Stop Loss
- Exposure and maximum open positions guard
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
from config import config

logger = logging.getLogger("RiskManager")

class RiskManager:
    def __init__(self, initial_balance: float = config.INITIAL_BALANCE):
        self.initial_balance = initial_balance
        self.peak_equity = initial_balance
        self.daily_start_equity = initial_balance
        self.current_day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.circuit_breaker_tripped = False
        self.circuit_breaker_reason = ""
        
        # Contract sizes & point values per standard lot (1.0 lot)
        self.asset_specs = {
            "XAUUSD": {"contract_size": 100.0, "tick_size": 0.01, "val_per_dollar_move": 100.0, "min_lot": 0.01, "max_lot": 20.0},
            "EURUSD": {"contract_size": 100000.0, "tick_size": 0.00001, "val_per_dollar_move": 100000.0, "min_lot": 0.01, "max_lot": 50.0},
            "GBPUSD": {"contract_size": 100000.0, "tick_size": 0.00001, "val_per_dollar_move": 100000.0, "min_lot": 0.01, "max_lot": 50.0},
            "NAS100": {"contract_size": 1.0, "tick_size": 0.1, "val_per_dollar_move": 1.0, "min_lot": 0.1, "max_lot": 50.0},
        }

    def update_daily_equity(self, current_equity: float):
        """Resets daily equity baseline at 00:00 UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.current_day:
            self.current_day = today
            self.daily_start_equity = current_equity
            self.circuit_breaker_tripped = False
            self.circuit_breaker_reason = ""
            logger.info(f"🔄 New trading day ({today}) initialized. Daily baseline equity: ${current_equity:,.2f}")
            
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

    def check_drawdown_limits(self, current_equity: float) -> Tuple[bool, str]:
        """
        Validates equity against Prop-Firm daily and overall drawdown limits.
        Returns: (is_safe, reason_message)
        """
        self.update_daily_equity(current_equity)
        
        # 1. Daily Drawdown calculation:
        daily_loss = self.daily_start_equity - current_equity
        daily_dd_pct = (daily_loss / self.daily_start_equity) * 100.0 if self.daily_start_equity > 0 else 0.0
        
        # 2. Total Drawdown calculation:
        total_loss = self.initial_balance - current_equity
        total_dd_pct = (total_loss / self.initial_balance) * 100.0 if self.initial_balance > 0 else 0.0
        
        if daily_dd_pct >= config.MAX_DAILY_DRAWDOWN_PCT:
            self.circuit_breaker_tripped = True
            self.circuit_breaker_reason = f"🚨 Daily Drawdown limit hit: {daily_dd_pct:.2f}% (Limit: {config.MAX_DAILY_DRAWDOWN_PCT}%)"
            logger.error(self.circuit_breaker_reason)
            return False, self.circuit_breaker_reason
            
        if total_dd_pct >= config.MAX_TOTAL_DRAWDOWN_PCT:
            self.circuit_breaker_tripped = True
            self.circuit_breaker_reason = f"🚨 Maximum Total Drawdown limit hit: {total_dd_pct:.2f}% (Limit: {config.MAX_TOTAL_DRAWDOWN_PCT}%)"
            logger.error(self.circuit_breaker_reason)
            return False, self.circuit_breaker_reason
            
        return True, "SAFE"

    def calculate_lot_size(self, symbol: str, entry_price: float, stop_loss: float, equity: float) -> float:
        """
        Calculates safe position lot size based on exact risk percentage of equity.
        Formula: Lot Size = (Equity * Risk%) / (SL_Distance * Dollar_Per_Unit)
        """
        spec = self.asset_specs.get(symbol.upper(), {
            "contract_size": 100000.0,
            "val_per_dollar_move": 100000.0,
            "min_lot": 0.01,
            "max_lot": 10.0
        })
        
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance <= 0:
            return spec["min_lot"]
            
        risk_capital = equity * (config.RISK_PER_TRADE_PCT / 100.0)
        dollar_risk_per_standard_lot = sl_distance * spec["val_per_dollar_move"]
        
        if dollar_risk_per_standard_lot <= 0:
            return spec["min_lot"]
            
        raw_lot = risk_capital / dollar_risk_per_standard_lot
        rounded_lot = round(raw_lot, 2)
        
        # Enforce boundaries
        lot_size = max(spec["min_lot"], min(rounded_lot, spec["max_lot"]))
        logger.info(f"📊 Lot Calc for {symbol}: Risk=${risk_capital:,.2f} ({config.RISK_PER_TRADE_PCT}%) | SL Dist={sl_distance:.4f} -> {lot_size} Lots")
        return lot_size

    def evaluate_trailing_and_breakeven(self, pos: Dict[str, Any], current_price: float, atr: float) -> Optional[Dict[str, Any]]:
        """
        Checks if Breakeven or Trailing Stop should be updated for an active position.
        Returns modification dict if an update is needed, else None.
        """
        side = pos.get("side", "BUY").upper()
        entry_price = float(pos.get("entry_price", 0.0))
        current_sl = float(pos.get("stop_loss", 0.0))
        initial_risk = abs(entry_price - float(pos.get("initial_sl", current_sl)))
        
        if initial_risk <= 0:
            initial_risk = atr * 1.5
            
        new_sl = current_sl
        modified = False
        action_type = ""
        
        if side == "BUY":
            profit_distance = current_price - entry_price
            # Breakeven Check
            if config.ENABLE_BREAKEVEN and profit_distance >= (initial_risk * config.BREAKEVEN_TRIGGER_R):
                # Move SL to entry + small buffer (e.g., 0.1 * ATR) to cover commissions
                be_level = entry_price + (atr * 0.1)
                if current_sl < be_level:
                    new_sl = round(be_level, 4)
                    modified = True
                    action_type = "BREAKEVEN"
                    
            # Trailing Stop Check
            if config.ENABLE_TRAILING_STOP:
                trail_level = round(current_price - (atr * config.TRAILING_STOP_ATR_MULT), 4)
                if trail_level > new_sl:
                    new_sl = trail_level
                    modified = True
                    action_type = "TRAILING_STOP"
                    
        elif side == "SELL":
            profit_distance = entry_price - current_price
            # Breakeven Check
            if config.ENABLE_BREAKEVEN and profit_distance >= (initial_risk * config.BREAKEVEN_TRIGGER_R):
                be_level = entry_price - (atr * 0.1)
                if current_sl > be_level:
                    new_sl = round(be_level, 4)
                    modified = True
                    action_type = "BREAKEVEN"
                    
            # Trailing Stop Check
            if config.ENABLE_TRAILING_STOP:
                trail_level = round(current_price + (atr * config.TRAILING_STOP_ATR_MULT), 4)
                if trail_level < new_sl or new_sl == 0.0:
                    new_sl = trail_level
                    modified = True
                    action_type = "TRAILING_STOP"
                    
        if modified and new_sl != current_sl:
            return {
                "symbol": pos["symbol"],
                "ticket": pos.get("ticket", 0),
                "action": action_type,
                "old_sl": current_sl,
                "new_sl": new_sl,
                "current_price": current_price
            }
        return None
