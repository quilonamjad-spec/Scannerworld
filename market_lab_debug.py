import sys
from pathlib import Path

SCANNER1_DIR = Path(__file__).resolve().parent / "scanner1"

if str(SCANNER1_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER1_DIR))

from data import fetch_batch
from indicators import build_result

import pandas as pd


SYMBOLS = ["ADANIPOWER.NS", "TCS.NS"]
AS_OF = pd.Timestamp("2026-08-21 13:55", tz="Asia/Kolkata")


print("=" * 70)
print("SCANNER ONE — TWO STOCK DIAGNOSTIC")
print("=" * 70)

print(f"Symbols : {SYMBOLS}")
print(f"As-of   : {AS_OF}")
print()

try:
    df = fetch_batch(
        tuple(SYMBOLS),
        period="60d",
        interval="5m",
    )

    print("DATA FETCH: SUCCESS")
    print("Shape:", df.shape)
    print("Columns:", df.columns)

except Exception as e:
    print("DATA FETCH: FAILED")
    print(type(e).__name__, str(e))
    raise


print()
print("-" * 70)

for symbol in SYMBOLS:

    print(f"\n### {symbol}")

    try:
        if symbol not in df.columns.get_level_values(0):
            print("NOT FOUND in downloaded data")
            continue

        sdf = df[symbol].dropna(how="all")

        print("Rows downloaded:", len(sdf))
        print("First bar:", sdf.index[0] if len(sdf) else None)
        print("Last bar :", sdf.index[-1] if len(sdf) else None)

        if sdf.index.tz is None:
            sdf.index = sdf.index.tz_localize("Asia/Kolkata")
        else:
            sdf.index = sdf.index.tz_convert("Asia/Kolkata")

        before = sdf[sdf.index <= AS_OF]

        print("Rows <= as_of:", len(before))

        if len(before):
            print("Last usable bar:", before.index[-1])

        result = build_result(symbol, sdf, AS_OF)

        if result is None:
            print("BUILD RESULT: No Bull/Bear condition passed")
        else:
            print("BUILD RESULT: MATCH")
            print(result)

    except Exception as e:
        print("EVALUATION ERROR")
        print(type(e).__name__, str(e))

print()
print("=" * 70)
print("DIAGNOSTIC COMPLETE")
print("=" * 70)
