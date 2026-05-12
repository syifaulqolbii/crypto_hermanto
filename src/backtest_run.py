"""
CLI entrypoint for running backtest.

Usage:
    python -m src.backtest_run
    python -m src.backtest_run --days 90
    python -m src.backtest_run --days 30 --symbols BTC-USDT-SWAP ETH-USDT-SWAP
    python -m src.backtest_run --no-csv
"""
import argparse

from src.backtest import run_backtest
from src.backtest_report import print_report, save_csv
from src.config import load_config
from src.data.okx import OkxClient


def main() -> None:
    parser = argparse.ArgumentParser(description="OKX SMC backtest runner")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--days", type=int, default=180, help="Days of history to backtest")
    parser.add_argument("--symbols", nargs="*", help="Override symbols from config")
    parser.add_argument("--no-csv", action="store_true", help="Skip CSV export")
    args = parser.parse_args()

    config = load_config(args.config)
    client = OkxClient(config["data"].get("base_url", "https://www.okx.com"))

    symbols = args.symbols or config["scanner"].get("symbols", [])
    print(f"Starting backtest: {len(symbols)} symbols, {args.days} days")
    print("=" * 60)

    all_results = []
    for i, symbol in enumerate(symbols, 1):
        print(f"\n[{i}/{len(symbols)}] {symbol}")
        try:
            results = run_backtest(client, symbol, config, days=args.days)
            all_results.extend(results)
        except Exception as exc:
            print(f"  Error: {exc}")

    print_report(all_results)

    if not args.no_csv:
        save_csv(all_results)


if __name__ == "__main__":
    main()
