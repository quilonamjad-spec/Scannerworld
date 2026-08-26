import argparse
import json
import sys
from pathlib import Path

# ------------------------------------------------------------
# Make Scanner 1's own modules importable
# ------------------------------------------------------------

SCANNER1_DIR = Path(__file__).resolve().parent / "scanner1"

if str(SCANNER1_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER1_DIR))

from market_lab_adapter import run_market_lab_scan


def parse_args():
    parser = argparse.ArgumentParser(description="Market Lab Scanner 1 runner")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols")
    parser.add_argument("--as-of", required=True, help="Replay timestamp, e.g. 2026-08-21 13:55")
    return parser.parse_args()


args = parse_args()
symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

result = run_market_lab_scan(
    symbols=symbols,
    as_of=args.as_of,
    lookback=55,
    batch_size=20,
)

print(json.dumps(result, indent=2, default=str))
