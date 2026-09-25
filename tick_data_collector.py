"""
High-Frequency Tick Data Collector & Order Book Imbalance Database
Stores every tick (bid, ask, spread, tick volume, flags, liquidity delta)
into a high-performance local SQLite database for quantitative microstructure analysis.
"""

import sqlite3
import time
import os
from typing import Dict, Any, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "tick_store.db")

class TickDataCollector:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                spread_pips REAL NOT NULL,
                tick_volume INTEGER NOT NULL,
                flags INTEGER DEFAULT 0,
                delta_direction INTEGER DEFAULT 0
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sym_time ON ticks (symbol, timestamp_ms)")
        conn.commit()
        conn.close()

    def insert_tick(self, symbol: str, bid: float, ask: float, tick_volume: int = 1, flags: int = 0) -> Dict[str, Any]:
        ts_ms = int(time.time() * 1000)
        point_mult = 100.0 if "JPY" in symbol.upper() else 10000.0
        spread_pips = round((ask - bid) * point_mult, 2)

        # Delta direction: +1 if trade at Ask (Aggressive Buy), -1 if at Bid (Aggressive Sell)
        # Using MQL5 TICK_FLAG_BUY (32) and TICK_FLAG_SELL (64)
        delta = 0
        if flags & 32:
            delta = 1
        elif flags & 64:
            delta = -1

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ticks (timestamp_ms, symbol, bid, ask, spread_pips, tick_volume, flags, delta_direction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ts_ms, symbol, bid, ask, spread_pips, tick_volume, flags, delta))
        conn.commit()
        conn.close()

        return {
            "symbol": symbol,
            "timestamp_ms": ts_ms,
            "bid": bid,
            "ask": ask,
            "spread_pips": spread_pips,
            "delta": delta
        }

    def get_symbol_microstructure_stats(self, symbol: str, lookback_ticks: int = 100) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT spread_pips, delta_direction, tick_volume
            FROM ticks
            WHERE symbol = ?
            ORDER BY timestamp_ms DESC
            LIMIT ?
        """, (symbol, lookback_ticks))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"symbol": symbol, "samples": 0, "avg_spread_pips": 0.0, "cumulative_delta": 0}

        avg_spread = sum(r[0] for r in rows) / len(rows)
        cum_delta = sum(r[1] * r[2] for r in rows)

        return {
            "symbol": symbol,
            "samples": len(rows),
            "avg_spread_pips": round(avg_spread, 2),
            "cumulative_delta": cum_delta,
            "imbalance_state": "AGGRESSIVE_BUYING" if cum_delta > 15 else ("AGGRESSIVE_SELLING" if cum_delta < -15 else "NEUTRAL")
        }

if __name__ == "__main__":
    collector = TickDataCollector()
    collector.insert_tick("EURUSD", 1.08500, 1.08512, tick_volume=1, flags=32)
    collector.insert_tick("EURUSD", 1.08502, 1.08514, tick_volume=2, flags=32)
    collector.insert_tick("EURUSD", 1.08501, 1.08513, tick_volume=1, flags=64)
    stats = collector.get_symbol_microstructure_stats("EURUSD")
    print("Microstructure Stats:", stats)
