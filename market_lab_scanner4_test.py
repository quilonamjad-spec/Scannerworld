import argparse
import json

from scanner4.market_lab_adapter import run_market_lab_scan


def parse_args():
    parser = argparse.ArgumentParser(description="Market Lab Scanner 4 runner")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols")
    parser.add_argument("--as-of", required=True, help="Replay timestamp, e.g. 2026-08-21 13:55")
    return parser.parse_args()


args = parse_args()
symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

result = run_market_lab_scan(
    symbols=symbols,
    as_of=args.as_of,
    period_days=5,
    smooth=True,
    chart_lookback=60,
)

print("=" * 70)
print("MARKET LAB — SCANNER FOUR UNIVERSE TEST")
print("=" * 70)

print(json.dumps(result, indent=2, default=str))
