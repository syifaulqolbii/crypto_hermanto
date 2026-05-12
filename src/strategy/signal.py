from src.models import Candle, Signal
from src.strategy.liquidity import swept_high, swept_low
from src.strategy.order_block import bearish_order_block, bullish_order_block
from src.strategy.structure import last_confirmed_swings, market_bias


def _rr(entry: float, stop: float, target: float, side: str) -> float:
    risk = entry - stop if side == "LONG" else stop - entry
    reward = target - entry if side == "LONG" else entry - target
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def _body_pct(candle: Candle) -> float:
    """Candle body size as % of total range."""
    total = candle.high - candle.low
    if total == 0:
        return 0.0
    return abs(candle.close - candle.open) / total


def _avg_volume(candles: list[Candle], lookback: int = 20) -> float:
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    if not recent:
        return 0.0
    return sum(c.volume for c in recent) / len(recent)


def scan_symbol(
    symbol: str,
    entry_timeframe: str,
    entry_candles: list[Candle],
    bias_candles: dict[str, list[Candle]],
    config: dict,
) -> Signal | None:
    if len(entry_candles) < 50:
        return None

    left = int(config["strategy"].get("swing_left", 3))
    right = int(config["strategy"].get("swing_right", 3))
    lookback = int(config["strategy"].get("order_block_lookback", 12))
    min_rr = float(config["strategy"].get("min_rr", 2.0))
    max_stop_pct_10x = float(config["strategy"].get("max_stop_pct_10x", 1.5))
    min_body_pct = float(config["strategy"].get("min_body_pct", 0.4))
    min_vol_mult = float(config["strategy"].get("min_volume_multiplier", 1.2))

    biases = [market_bias(candles, left, right) for candles in bias_candles.values() if candles]
    bullish_bias = biases and all(bias in {"bullish", "neutral"} for bias in biases) and "bullish" in biases
    bearish_bias = biases and all(bias in {"bearish", "neutral"} for bias in biases) and "bearish" in biases

    high_index, low_index = last_confirmed_swings(entry_candles[:-1], left, right)
    if high_index is None or low_index is None:
        return None

    last = entry_candles[-1]
    previous = entry_candles[-2]
    ts = last.ts

    # Filter 1: displacement candle must have strong body
    if _body_pct(last) < min_body_pct:
        return None

    # Filter 2: displacement candle volume must be above average
    avg_vol = _avg_volume(entry_candles[:-1], 20)
    if avg_vol > 0 and last.volume < avg_vol * min_vol_mult:
        return None

    if bullish_bias and swept_low(last, entry_candles[low_index].low) and last.close > previous.high:
        ob = bullish_order_block(entry_candles, len(entry_candles) - 1, lookback)
        if not ob:
            return None
        entry_low, entry_high = sorted((ob.low, ob.open))
        stop = min(last.low, ob.low)
        tp1 = entry_candles[high_index].high
        tp2 = tp1 + (tp1 - stop)
        entry = (entry_low + entry_high) / 2
        rr = _rr(entry, stop, tp1, "LONG")
        stop_pct = abs(entry - stop) / entry * 100
        if rr < min_rr or stop_pct > max_stop_pct_10x:
            return None
        return Signal(
            symbol=symbol,
            side="LONG",
            timeframe=entry_timeframe,
            bias="/".join(biases),
            setup="liquidity sweep + bullish displacement + demand retest zone",
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop,
            tp1=tp1,
            tp2=tp2,
            rr=rr,
            confidence=75,
            reason=(
                f"Swept low {entry_candles[low_index].low:.4f}, "
                f"closed above prev high. Body: {_body_pct(last):.0%}, "
                f"Vol: {last.volume:.0f} vs avg {avg_vol:.0f}."
            ),
            ts=ts,
        )

    if bearish_bias and swept_high(last, entry_candles[high_index].high) and last.close < previous.low:
        ob = bearish_order_block(entry_candles, len(entry_candles) - 1, lookback)
        if not ob:
            return None
        entry_low, entry_high = sorted((ob.open, ob.high))
        stop = max(last.high, ob.high)
        tp1 = entry_candles[low_index].low
        tp2 = tp1 - (stop - tp1)
        entry = (entry_low + entry_high) / 2
        rr = _rr(entry, stop, tp1, "SHORT")
        stop_pct = abs(stop - entry) / entry * 100
        if rr < min_rr or stop_pct > max_stop_pct_10x:
            return None
        return Signal(
            symbol=symbol,
            side="SHORT",
            timeframe=entry_timeframe,
            bias="/".join(biases),
            setup="liquidity sweep + bearish displacement + supply retest zone",
            entry_low=entry_low,
            entry_high=entry_high,
            stop_loss=stop,
            tp1=tp1,
            tp2=tp2,
            rr=rr,
            confidence=75,
            reason=(
                f"Swept high {entry_candles[high_index].high:.4f}, "
                f"closed below prev low. Body: {_body_pct(last):.0%}, "
                f"Vol: {last.volume:.0f} vs avg {avg_vol:.0f}."
            ),
            ts=ts,
        )

    return None
