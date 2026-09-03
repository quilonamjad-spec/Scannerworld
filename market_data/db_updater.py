"""Standalone Market Lab Candle DB updater.

This script is deliberately separate from the scanner runners.
It updates the shared VM Candle DB using the existing market_data
local_store.update_store() mechanism. Scanner logic is not touched.

Typical use:
    python market_data/db_updater.py --symbols TCS,INFY,RELIANCE

If --symbols is omitted, MARKETLAB_SYMBOLS is used. If that is also
not set, the small Market Lab test universe is used.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from market_data.local_store import store_summary, update_store


DEFAULT_SYMBOLS = ["ADANIPOWER", "TCS"]
DEFAULT_INTERVAL = "5m"
DEFAULT_PERIOD = "5d"


def parse_symbols(value: str) -> list[str]:
    symbols = []
    for item in value.split(","):
        symbol = item.strip().upper()
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update the Market Lab VM Candle DB with the latest candles."
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated NSE symbols. Defaults to MARKETLAB_SYMBOLS or ADANIPOWER,TCS.",
    )
    parser.add_argument(
        "--interval",
        default=DEFAULT_INTERVAL,
        choices=["5m"],
        help="Candle interval. V1 intentionally updates the proven 5m store only.",
    )
    parser.add_argument(
        "--period",
        default=DEFAULT_PERIOD,
        help="History to use if a symbol is missing from the DB (default: 5d).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    configured = args.symbols or os.getenv("MARKETLAB_SYMBOLS", "")
    symbols = parse_symbols(configured) if configured else DEFAULT_SYMBOLS.copy()

    if not symbols:
        print("ERROR: No symbols supplied.")
        return 1

    db_url = os.getenv("MARKETLAB_DB_URL", "").strip()
    if not db_url:
        print("ERROR: MARKETLAB_DB_URL is not set.")
        print("Run: source ./connect_marketlab.sh")
        return 1

    started = datetime.now()

    print("=" * 70)
    print("MARKET LAB — CANDLE DB UPDATER")
    print("=" * 70)
    print(f"Database : {db_url}")
    print(f"Interval : {args.interval}")
    print(f"Symbols  : {', '.join(symbols)}")
    print(f"Started  : {started.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 70)

    try:
        added = update_store(
            tickers=symbols,
            period=args.period,
            interval=args.interval,
        )
        summary = store_summary(interval=args.interval)
    except Exception as exc:
        print("\nDB UPDATE FAILED")
        print(f"Reason: {exc}")
        return 1

    finished = datetime.now()
    elapsed = (finished - started).total_seconds()

    print("-" * 70)
    print("DB UPDATE COMPLETE")
    print(f"New candles added : {added}")
    print(f"Symbols in DB     : {summary.get('symbols_cached', 0)}")
    print(f"Total 5m candles  : {summary.get('total_bars', 0)}")
    print(f"Oldest candle     : {summary.get('oldest_bar')}")
    print(f"Latest candle     : {summary.get('newest_bar')}")
    print(f"Elapsed           : {elapsed:.1f} seconds")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
