from dataclasses import dataclass
from typing import Literal


@dataclass
class BacktestTrade:
    symbol: str
    side: Literal["LONG", "SHORT"]
    timeframe: str
    entry: float
    stop_loss: float
    tp1: float
    tp2: float
    rr: float
    signal_ts: int
    outcome: Literal["tp1", "tp2", "sl", "open"] = "open"
    exit_price: float = 0.0
    exit_ts: int = 0
    pnl_r: float = 0.0  # PnL in R multiples


@dataclass
class BacktestResult:
    symbol: str
    timeframe: str
    total_signals: int
    tp1_count: int
    tp2_count: int
    sl_count: int
    open_count: int
    win_rate: float        # TP1 or TP2 / total closed
    avg_rr: float          # average actual RR on closed trades
    max_drawdown: float    # max consecutive R loss
    trades: list[BacktestTrade]
