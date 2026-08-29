from angel_one.data_provider import AngelOneProvider


provider = AngelOneProvider()

df = provider.get_candles(
    symbol="TCS",
    interval="5m",
    from_datetime="2026-08-28 09:15",
    to_datetime="2026-08-28 10:00",
)

print("\nANGEL ONE PROVIDER TEST")
print("=======================")

print("\nColumns:")
print(list(df.columns))

print("\nRows:", len(df))

print("\nData:")
print(df.to_string(index=False))
