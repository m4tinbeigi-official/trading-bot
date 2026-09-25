"""
Centralized Configuration for Rick Sanchez MT5 Trading Bot
Defines asset symbols, prop-firm risk parameters, trading sessions, and connection settings.
"""

from dataclasses import dataclass, field
from typing import List

@dataclass
class TradingConfig:
    # Mode Settings: 'PAPER' (Local Simulation) or 'MT5' (MetaTrader 5 Bridge) or 'AUTO' (Auto-detect MT5, fallback to Paper)
    EXECUTION_MODE: str = "AUTO"
    
    # Target Trading Symbols
    SYMBOLS: List[str] = field(default_factory=lambda: ["XAUUSD", "EURUSD", "GBPUSD", "NAS100"])
    
    # Account & Capital
    INITIAL_BALANCE: float = 100.0  # USD (Demo balance)
    ACCOUNT_CURRENCY: str = "USD"
    DEFAULT_LEVERAGE: int = 100
    MT5_LOGIN: int = 113150386
    MT5_SERVER: str = "MetaQuotes-Demo"
    
    # Prop-Firm & Risk Management Rules
    RISK_PER_TRADE_PCT: float = 1.0       # Risk 1.0% of current equity per trade
    MAX_OPEN_POSITIONS: int = 3          # Max concurrent active trades
    MAX_DAILY_DRAWDOWN_PCT: float = 4.5   # Hard safety stop if daily loss reaches 4.5% (Prop-firm limit is 5%)
    MAX_TOTAL_DRAWDOWN_PCT: float = 8.5  # Hard stop if total loss reaches 8.5% (Prop-firm limit is 10%)
    
    # Trailing Stop & Breakeven Parameters
    ENABLE_BREAKEVEN: bool = True
    BREAKEVEN_TRIGGER_R: float = 1.0     # Move SL to Entry when trade reaches 1.0R in profit
    ENABLE_TRAILING_STOP: bool = True
    TRAILING_STOP_ATR_MULT: float = 1.5  # Trail stop by 1.5 * ATR
    DEFAULT_RISK_REWARD_RATIO: float = 2.0 # Minimum 1:2 Risk to Reward
    
    # Trading Session Windows (UTC Hours)
    # High-volume overlap sessions: London (08:00 - 16:30 UTC), New York (13:00 - 21:00 UTC)
    ENFORCE_SESSION_HOURS: bool = True
    ACTIVE_SESSIONS: dict = field(default_factory=lambda: {
        "LONDON": {"start": 8, "end": 16},
        "NEW_YORK": {"start": 13, "end": 21}
    })
    
    # Indicator Parameters
    EMA_FAST: int = 20
    EMA_SLOW: int = 50
    EMA_TREND: int = 200
    RSI_PERIOD: int = 14
    RSI_BULLISH_THRESHOLD: float = 52.0
    RSI_BEARISH_THRESHOLD: float = 48.0
    ATR_PERIOD: int = 14
    ATR_MULTIPLIER: float = 1.5
    
    # Bridge & Sockets (ZeroMQ / TCP IPC)
    MT5_HOST: str = "127.0.0.1"
    MT5_REQ_PORT: int = 5555
    MT5_SUB_PORT: int = 5556
    MT5_TIMEOUT_MS: int = 3000
    
    # Web Dashboard Settings
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8080

config = TradingConfig()
