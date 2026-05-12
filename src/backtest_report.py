"""
Backtest report: print summary table and save CSV.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path

from src.backtest_models import BacktestResult


def print_report(results: list[BacktestResult]) -> None:
    if not results:
        print("No backtest results.")
        return

    print("\n" + "=" * 90)
    print(f"{'SYMBOL':<20} {'TF':<6} {'SIGNALS':>8} {'TP1':>5} {'TP2':>5} {'SL':>5} "
          f"{'OPEN':>5} {'WIN%':>7} {'AVG RR':>8} {'MAX DD':>8}")
    print("-" * 90)

    total_signals = 0
    total_tp1 = 0
    total_tp2 = 0
    total_sl = 0
    total_open = 0
    all_closed_rr: list[float] = []

    for r in sorted(results, key=lambda x: (x.symbol, x.timeframe)):
        print(
            f"{r.symbol:<20} {r.timeframe:<6} {r.total_signals:>8} {r.tp1_count:>5} "
            f"{r.tp2_count:>5} {r.sl_count:>5} {r.open_count:>5} "
            f"{r.win_rate:>6.1f}% {r.avg_rr:>8.2f} {r.max_drawdown:>8.2f}R"
        )
        total_signals += r.total_signals
        total_tp1 += r.tp1_count
        total_tp2 += r.tp2_count
        total_sl += r.sl_count
        total_open += r.open_count
        for t in r.trades:
            if t.outcome != "open":
                all_closed_rr.append(t.pnl_r)

    print("-" * 90)
    total_closed = total_tp1 + total_tp2 + total_sl
    overall_wr = round((total_tp1 + total_tp2) / total_closed * 100, 1) if total_closed else 0.0
    overall_rr = round(sum(all_closed_rr) / len(all_closed_rr), 2) if all_closed_rr else 0.0
    print(
        f"{'TOTAL':<20} {'':6} {total_signals:>8} {total_tp1:>5} {total_tp2:>5} "
        f"{total_sl:>5} {total_open:>5} {overall_wr:>6.1f}% {overall_rr:>8.2f}"
    )
    print("=" * 90)
    print(f"\nTotal signals: {total_signals} | Closed: {total_closed} | "
          f"Win rate: {overall_wr}% | Avg RR: {overall_rr}R")

    # Signal frequency
    if results:
        days = 180
        freq = round(total_signals / (len(set(r.symbol for r in results)) * days), 2)
        print(f"Signal frequency: ~{freq} signals/symbol/day over {days} days")


def save_csv(results: list[BacktestResult], output_dir: str = "logs") -> str:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = Path(output_dir) / f"backtest_{ts}.csv"

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "symbol", "timeframe", "side", "entry", "stop_loss",
            "tp1", "tp2", "rr", "outcome", "exit_price",
            "pnl_r", "signal_ts", "exit_ts",
        ])
        for r in results:
            for t in r.trades:
                writer.writerow([
                    t.symbol, t.timeframe, t.side,
                    t.entry, t.stop_loss, t.tp1, t.tp2, t.rr,
                    t.outcome, t.exit_price, t.pnl_r,
                    t.signal_ts, t.exit_ts,
                ])

    print(f"\nCSV saved: {path}")
    return str(path)
