import json
import sys
from pathlib import Path

# Make scanner1's modules importable
SCANNER1_DIR = Path(__file__).resolve().parent / "scanner1"

if str(SCANNER1_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER1_DIR))

from market_lab_adapter import get_scanner1_health


print("=" * 50)
print("MARKET LAB — SCANNER ONE CONNECTION TEST")
print("=" * 50)

result = get_scanner1_health()

print(json.dumps(result, indent=2, default=str))

print("=" * 50)

if result.get("status") == "ok":
    print("SUCCESS: Scanner One pipeline is reachable.")
else:
    print("FAILED: Scanner One pipeline could not be reached.")
