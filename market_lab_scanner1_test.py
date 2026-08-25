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


# ------------------------------------------------------------
# Market Lab test
# ------------------------------------------------------------

result = run_market_lab_scan(
    symbols=["ADANIPOWER.NS", "TCS.NS"],
    as_of="2026-08-21 13:55",
    lookback=55,
    batch_size=20,
)

print(json.dumps(result, indent=2, default=str))
