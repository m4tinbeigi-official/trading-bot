"""
Base Strategy Interface for Quantitative Trading Algorithms
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class TradeSignal:
    symbol: str
    action: str         # 'BUY', 'SELL', 'HOLD'
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    confidence: float   # 0.0 to 1.0
    reason: str

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, symbol: str, current_price: float, klines: List[Dict[str, float]]) -> Optional[TradeSignal]:
        """Evaluates price data and returns a TradeSignal if an opportunity is found."""
        pass
