import json

from scanner2.market_lab_adapter import run_market_lab_scan


result = run_market_lab_scan(
    symbols=["ADANIPOWER", "TCS"],
    as_of="2026-08-21 13:55",
    interval="5m",
    period="5d",
    batch_size=2,
)


print("=" * 70)
print("MARKET LAB — SCANNER TWO SMALL UNIVERSE TEST")
print("=" * 70)

print(json.dumps(result, indent=2, default=str))
