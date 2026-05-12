from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    closed: bool = True


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: Literal["LONG", "SHORT"]
    timeframe: str
    bias: str
    setup: str
    entry_low: float
    entry_high: float
    stop_loss: float
    tp1: float
    tp2: float
    rr: float
    confidence: int
    reason: str
    ts: int

    def key(self) -> str:
        zone = f"{self.entry_low:.8f}:{self.entry_high:.8f}"
        return f"{self.symbol}:{self.timeframe}:{self.side}:{zone}"
