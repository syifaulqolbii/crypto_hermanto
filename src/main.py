import argparse
import time

from src.config import load_config
from src.data.okx import OkxClient
from src.notifier.console import ConsoleNotifier
from src.notifier.telegram import TelegramNotifier
from src.storage import SignalStore
from src.strategy.signal import scan_symbol


def run_once(config: dict) -> int:
    client = OkxClient(config["data"].get("base_url", "https://www.okx.com"))
    console = ConsoleNotifier()
    telegram = TelegramNotifier()
    cooldown = int(config["strategy"].get("signal_cooldown_minutes", 180))
    store = SignalStore(config["output"].get("log_file", "logs/signals.jsonl"), cooldown)

    symbols = config["scanner"].get("symbols", [])
    bias_timeframes = config["scanner"].get("timeframes", {}).get("bias", ["4H", "1H"])
    entry_timeframes = config["scanner"].get("timeframes", {}).get("entry", ["15m", "5m"])
    limit = int(config["scanner"].get("candle_limit", 200))
    print_no_signal = bool(config["output"].get("print_no_signal", False))

    emitted = 0
    for symbol in symbols:
        try:
            bias_candles = {tf: client.fetch_candles(symbol, tf, limit) for tf in bias_timeframes}
            for timeframe in entry_timeframes:
                candles = client.fetch_candles(symbol, timeframe, limit)
                signal = scan_symbol(symbol, timeframe, candles, bias_candles, config)
                if not signal:
                    if print_no_signal:
                        print(f"No signal: {symbol} {timeframe}")
                    continue
                if store.should_emit(signal):
                    store.save(signal)
                    console.send(signal)
                    telegram.send(signal)
                    emitted += 1
        except Exception as exc:
            print(f"Error scanning {symbol}: {exc}")
    return emitted


def main() -> None:
    parser = argparse.ArgumentParser(description="OKX SMC futures signal bot")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.once:
        emitted = run_once(config)
        print(f"Scan complete. Signals: {emitted}")
        return

    poll_seconds = int(config["scanner"].get("poll_seconds", 60))
    while True:
        emitted = run_once(config)
        print(f"Scan complete. Signals: {emitted}. Sleeping {poll_seconds}s.")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
