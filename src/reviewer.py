from src.data.okx import OkxClient
from src.models import Candle, Signal
from src.notifier.console import ConsoleNotifier, format_signal
from src.notifier.telegram import TelegramNotifier
from src.strategy.signal import scan_symbol
from src.strategy.structure import market_bias
from src.tracker import ActiveSignal, SignalTracker


def _current_price(candles: list[Candle]) -> float:
    return candles[-1].close if candles else 0.0


def _format_invalidation_alert(old: ActiveSignal, new_signal: Signal | None, reason: str) -> str:
    sig = old.signal
    lines = [
        "⚠️ *SIGNAL INVALIDATED*",
        "",
        f"*Pair:* {sig.symbol}",
        f"*Side:* {sig.side}",
        f"*Timeframe:* {sig.timeframe}",
        f"*Original Entry:* {sig.entry_low:g} - {sig.entry_high:g}",
        f"*Original SL:* {sig.stop_loss:g}",
        f"*Original TP1:* {sig.tp1:g} | TP2: {sig.tp2:g}",
        "",
        f"*Reason:* {reason}",
        "",
        "🔴 *ACTION: CUTLOSS / EXIT POSITION NOW*",
    ]
    if new_signal:
        lines += [
            "",
            "─" * 30,
            "🔄 *NEW SIGNAL DETECTED*",
            "",
            f"```",
            format_signal(new_signal),
            f"```",
        ]
    return "\n".join(lines)


def _format_sl_hit_alert(entry: ActiveSignal) -> str:
    sig = entry.signal
    return (
        f"🔴 *SL HIT*\n\n"
        f"*Pair:* {sig.symbol}\n"
        f"*Side:* {sig.side} {sig.timeframe}\n"
        f"*SL:* {sig.stop_loss:g}\n"
        f"*Entry was:* {sig.entry_low:g} - {sig.entry_high:g}\n\n"
        f"Position closed at stop loss."
    )


def _format_tp_hit_alert(entry: ActiveSignal, level: str) -> str:
    sig = entry.signal
    target = sig.tp1 if level == "tp1_hit" else sig.tp2
    emoji = "🟡" if level == "tp1_hit" else "✅"
    label = "TP1" if level == "tp1_hit" else "TP2 (FULL TARGET)"
    return (
        f"{emoji} *{label} HIT*\n\n"
        f"*Pair:* {sig.symbol}\n"
        f"*Side:* {sig.side} {sig.timeframe}\n"
        f"*Target:* {target:g}\n"
        f"*Entry was:* {sig.entry_low:g} - {sig.entry_high:g}\n"
        f"*RR achieved:* {sig.rr}"
    )


class SignalReviewer:
    def __init__(
        self,
        client: OkxClient,
        tracker: SignalTracker,
        config: dict,
    ) -> None:
        self.client = client
        self.tracker = tracker
        self.config = config
        self.console = ConsoleNotifier()
        self.telegram = TelegramNotifier()
        self._last_1h_review: float = 0.0
        self._last_4h_review: float = 0.0

    def _send(self, signal: Signal | None, text: str) -> None:
        print("\n" + "=" * 60)
        print(text)
        print("=" * 60 + "\n")
        self.telegram._send_text(text)

    def review_sl(self) -> None:
        import time
        now = time.time()
        if now - self._last_1h_review < 3600:
            return
        self._last_1h_review = now

        print("[Reviewer] Running 1H SL check...")
        active = self.tracker.get_all_active()
        limit = int(self.config["scanner"].get("candle_limit", 200))

        for entry in active:
            symbol = entry.signal.symbol
            try:
                candles = self.client.fetch_candles(symbol, "1H", 5)
                price = _current_price(candles)
                if not price:
                    continue
                hit = self.tracker.check_price_hit(entry, price)
                if hit == "sl_hit":
                    self.tracker.mark(entry.signal.key(), "sl_hit")
                    text = _format_sl_hit_alert(entry)
                    self._send(None, text)
                elif hit in ("tp1_hit", "tp2_hit"):
                    self.tracker.mark(entry.signal.key(), hit)
                    text = _format_tp_hit_alert(entry, hit)
                    self._send(None, text)
            except Exception as exc:
                print(f"[Reviewer] SL check error {symbol}: {exc}")

    def review_structure(self) -> None:
        import time
        now = time.time()
        if now - self._last_4h_review < 14400:
            return
        self._last_4h_review = now

        print("[Reviewer] Running 4H structure check...")
        active = self.tracker.get_all_active()
        bias_tfs = self.config["scanner"].get("timeframes", {}).get("bias", ["4H", "1H"])
        entry_tfs = self.config["scanner"].get("timeframes", {}).get("entry", ["15m", "5m"])
        limit = int(self.config["scanner"].get("candle_limit", 200))
        left = int(self.config["strategy"].get("swing_left", 3))
        right = int(self.config["strategy"].get("swing_right", 3))

        for entry in active:
            symbol = entry.signal.symbol
            side = entry.signal.side
            try:
                bias_candles_4h = self.client.fetch_candles(symbol, "4H", limit)
                bias_candles_1h = self.client.fetch_candles(symbol, "1H", limit)
                bias_4h = market_bias(bias_candles_4h, left, right)
                bias_1h = market_bias(bias_candles_1h, left, right)

                structure_ok = (
                    (side == "LONG" and bias_4h in ("bullish", "neutral") and bias_1h in ("bullish", "neutral"))
                    or (side == "SHORT" and bias_4h in ("bearish", "neutral") and bias_1h in ("bearish", "neutral"))
                )

                if not structure_ok:
                    reason = (
                        f"4H bias: {bias_4h}, 1H bias: {bias_1h} — "
                        f"structure no longer supports {side} direction."
                    )
                    self.tracker.mark(entry.signal.key(), "invalidated")

                    new_signal = None
                    for tf in entry_tfs:
                        try:
                            entry_candles = self.client.fetch_candles(symbol, tf, limit)
                            bias_map = {"4H": bias_candles_4h, "1H": bias_candles_1h}
                            new_signal = scan_symbol(symbol, tf, entry_candles, bias_map, self.config)
                            if new_signal:
                                self.tracker.add(new_signal)
                                break
                        except Exception:
                            continue

                    text = _format_invalidation_alert(entry, new_signal, reason)
                    self._send(new_signal, text)

            except Exception as exc:
                print(f"[Reviewer] Structure check error {symbol}: {exc}")

    def run(self) -> None:
        self.review_sl()
        self.review_structure()
