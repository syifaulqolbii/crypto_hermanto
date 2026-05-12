from src.models import Candle


def bullish_order_block(candles: list[Candle], end_index: int, lookback: int) -> Candle | None:
    start = max(0, end_index - lookback)
    for candle in reversed(candles[start:end_index]):
        if candle.close < candle.open:
            return candle
    return None


def bearish_order_block(candles: list[Candle], end_index: int, lookback: int) -> Candle | None:
    start = max(0, end_index - lookback)
    for candle in reversed(candles[start:end_index]):
        if candle.close > candle.open:
            return candle
    return None
