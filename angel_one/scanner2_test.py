import json

from angel_one.scanner2_adapter import run_angel_scanner2


result = run_angel_scanner2(
    symbols=["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK"],
    as_of="2026-08-28 10:00",
    interval="5m",
)

print("\n")
print("=" * 70)
print("ANGEL ONE → SCANNER 2 EXPERIMENT")
print("=" * 70)

print(
    json.dumps(
        result,
        indent=2,
        default=str,
    )
)
