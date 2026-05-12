from src.models import Candle


def swept_high(candle: Candle, reference_high: float) -> bool:
    return candle.high > reference_high and candle.close < reference_high


def swept_low(candle: Candle, reference_low: float) -> bool:
    return candle.low < reference_low and candle.close > reference_low
