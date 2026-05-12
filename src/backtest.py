"""
Backtest engine: replay historical candles, detect SMC signals,
simulate SL/TP outcomes using subsequent candles.
"""
from datetime import datetime, timezone

from src.backtest_models import BacktestResult, BacktestTrade
from src.data.okx import OkxClient
from src.models import Candle, Signal
from src.strategy.signal import scan_symbol


def _fetch_history(client: OkxClient, symbol: str, timeframe: str, days: int) -> list[Candle]:
    """Fetch up to `days` days of candle history by paginating OKX API."""
    all_candles: list[Candle] = []
    # OKX max 300 candles per request; paginate using `after` param (oldest ts)
    limit = 300
    after: int | None = None

    # Estimate how many candles we need
    tf_minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1H": 60, "2H": 120, "4H": 240, "6H": 360, "12H": 720,
        "1D": 1440,
    }
    minutes = tf_minutes.get(timeframe, 15)
    needed = int(days * 24 * 60 / minutes)

    while len(all_candles) < needed:
        params: dict = {"instId": symbol, "bar": timeframe, "limit": limit}
        if after is not None:
            params["after"] = str(after)
        try:
            payload = client.get("/api/v5/market/history-candles", params)
        except Exception:
            # history-candles may not be available on demo; fall back to candles
            payload = client.get("/api/v5/market/candles", params)

        rows = payload.get("data", [])
        if not rows:
            break

        batch = [
            Candle(
                ts=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                closed=True,
            )
            for r in rows
        ]
        # OKX returns newest first; reverse to oldest first
        batch = list(reversed(batch))
        all_candles = batch + all_candles
        after = int(rows[-1][0])  # oldest ts in this batch

        if len(rows) < limit:
            break

    # Sort oldest → newest and deduplicate
    seen: set[int] = set()
    unique: list[Candle] = []
    for c in sorted(all_candles, key=lambda x: x.ts):
        if c.ts not in seen:
            seen.add(c.ts)
            unique.append(c)

    # Trim to requested days
    cutoff_ms = int(
        (datetime.now(timezone.utc).timestamp() - days * 86400) * 1000
    )
    return [c for c in unique if c.ts >= cutoff_ms]


def _simulate_outcome(signal: Signal, future_candles: list[Candle]) -> BacktestTrade:
    trade = BacktestTrade(
        symbol=signal.symbol,
        side=signal.side,
        timeframe=signal.timeframe,
        entry=(signal.entry_low + signal.entry_high) / 2,
        stop_loss=signal.stop_loss,
        tp1=signal.tp1,
        tp2=signal.tp2,
        rr=signal.rr,
        signal_ts=signal.ts,
    )
    risk = abs(trade.entry - trade.stop_loss)
    if risk == 0:
        return trade

    for candle in future_candles:
        if signal.side == "LONG":
            if candle.low <= signal.stop_loss:
                trade.outcome = "sl"
                trade.exit_price = signal.stop_loss
                trade.exit_ts = candle.ts
                trade.pnl_r = -1.0
                return trade
            if candle.high >= signal.tp2:
                trade.outcome = "tp2"
                trade.exit_price = signal.tp2
                trade.exit_ts = candle.ts
                trade.pnl_r = round((signal.tp2 - trade.entry) / risk, 2)
                return trade
            if candle.high >= signal.tp1:
                trade.outcome = "tp1"
                trade.exit_price = signal.tp1
                trade.exit_ts = candle.ts
                trade.pnl_r = round((signal.tp1 - trade.entry) / risk, 2)
                return trade
        else:
            if candle.high >= signal.stop_loss:
                trade.outcome = "sl"
                trade.exit_price = signal.stop_loss
                trade.exit_ts = candle.ts
                trade.pnl_r = -1.0
                return trade
            if candle.low <= signal.tp2:
                trade.outcome = "tp2"
                trade.exit_price = signal.tp2
                trade.exit_ts = candle.ts
                trade.pnl_r = round((trade.entry - signal.tp2) / risk, 2)
                return trade
            if candle.low <= signal.tp1:
                trade.outcome = "tp1"
                trade.exit_price = signal.tp1
                trade.exit_ts = candle.ts
                trade.pnl_r = round((trade.entry - signal.tp1) / risk, 2)
                return trade

    trade.outcome = "open"
    return trade


def _max_drawdown(trades: list[BacktestTrade]) -> float:
    closed = [t for t in trades if t.outcome != "open"]
    if not closed:
        return 0.0
    peak = 0.0
    equity = 0.0
    max_dd = 0.0
    for t in closed:
        equity += t.pnl_r
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 2)


def run_backtest(
    client: OkxClient,
    symbol: str,
    config: dict,
    days: int = 180,
) -> list[BacktestResult]:
    bias_tfs = config["scanner"].get("timeframes", {}).get("bias", ["4H", "1H"])
    entry_tfs = config["scanner"].get("timeframes", {}).get("entry", ["15m", "5m"])
    warmup = int(config["scanner"].get("candle_limit", 200))
    results = []

    for entry_tf in entry_tfs:
        print(f"  [{symbol}] Fetching {entry_tf} history ({days}d)...")
        candles = _fetch_history(client, symbol, entry_tf, days)
        if len(candles) < warmup + 10:
            print(f"  [{symbol}] Not enough candles for {entry_tf}, skipping.")
            continue

        bias_candles: dict[str, list[Candle]] = {}
        for btf in bias_tfs:
            print(f"  [{symbol}] Fetching {btf} bias history...")
            bias_candles[btf] = _fetch_history(client, symbol, btf, days)

        trades: list[BacktestTrade] = []
        # Walk forward: use warmup candles as context, scan each new candle
        for i in range(warmup, len(candles) - 1):
            window = candles[: i + 1]
            bias_window = {
                btf: [c for c in bc if c.ts <= candles[i].ts]
                for btf, bc in bias_candles.items()
            }
            signal = scan_symbol(symbol, entry_tf, window, bias_window, config)
            if signal:
                future = candles[i + 1:]
                trade = _simulate_outcome(signal, future)
                trades.append(trade)
                # Skip forward to avoid overlapping signals from same zone
                # (advance by at least 1 candle after signal)

        closed = [t for t in trades if t.outcome != "open"]
        wins = [t for t in closed if t.outcome in ("tp1", "tp2")]
        win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0.0
        avg_rr = round(sum(t.pnl_r for t in closed) / len(closed), 2) if closed else 0.0

        results.append(
            BacktestResult(
                symbol=symbol,
                timeframe=entry_tf,
                total_signals=len(trades),
                tp1_count=sum(1 for t in trades if t.outcome == "tp1"),
                tp2_count=sum(1 for t in trades if t.outcome == "tp2"),
                sl_count=sum(1 for t in trades if t.outcome == "sl"),
                open_count=sum(1 for t in trades if t.outcome == "open"),
                win_rate=win_rate,
                avg_rr=avg_rr,
                max_drawdown=_max_drawdown(trades),
                trades=trades,
            )
        )

    return results
