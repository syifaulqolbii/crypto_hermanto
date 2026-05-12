from src.models import Signal


def format_signal(signal: Signal) -> str:
    return (
        f"{signal.symbol} {signal.side} {signal.timeframe}\n"
        f"Bias: {signal.bias}\n"
        f"Setup: {signal.setup}\n"
        f"Entry: {signal.entry_low:g} - {signal.entry_high:g}\n"
        f"SL: {signal.stop_loss:g}\n"
        f"TP1: {signal.tp1:g}\n"
        f"TP2: {signal.tp2:g}\n"
        f"RR: {signal.rr}\n"
        f"Confidence: {signal.confidence}/100\n"
        f"Leverage note: 10x, invalid if price closes beyond SL.\n"
        f"Reason: {signal.reason}"
    )


class ConsoleNotifier:
    def send(self, signal: Signal) -> None:
        print("\n" + "=" * 60)
        print(format_signal(signal))
        print("=" * 60 + "\n")
