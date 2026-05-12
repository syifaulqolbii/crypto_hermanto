from src.models import Candle


def swing_highs(candles: list[Candle], left: int, right: int) -> list[int]:
    result = []
    for index in range(left, len(candles) - right):
        high = candles[index].high
        if all(high > candles[i].high for i in range(index - left, index)) and all(
            high >= candles[i].high for i in range(index + 1, index + right + 1)
        ):
            result.append(index)
    return result


def swing_lows(candles: list[Candle], left: int, right: int) -> list[int]:
    result = []
    for index in range(left, len(candles) - right):
        low = candles[index].low
        if all(low < candles[i].low for i in range(index - left, index)) and all(
            low <= candles[i].low for i in range(index + 1, index + right + 1)
        ):
            result.append(index)
    return result


def market_bias(candles: list[Candle], left: int, right: int) -> str:
    highs = swing_highs(candles, left, right)
    lows = swing_lows(candles, left, right)
    if len(highs) < 2 or len(lows) < 2:
        return "neutral"

    last_highs = [candles[i].high for i in highs[-2:]]
    last_lows = [candles[i].low for i in lows[-2:]]
    if last_highs[-1] > last_highs[0] and last_lows[-1] > last_lows[0]:
        return "bullish"
    if last_highs[-1] < last_highs[0] and last_lows[-1] < last_lows[0]:
        return "bearish"
    return "neutral"


def last_confirmed_swings(candles: list[Candle], left: int, right: int) -> tuple[int | None, int | None]:
    highs = swing_highs(candles, left, right)
    lows = swing_lows(candles, left, right)
    return (highs[-1] if highs else None, lows[-1] if lows else None)
