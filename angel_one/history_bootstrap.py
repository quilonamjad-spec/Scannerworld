import time

import pandas as pd

from .data_provider import AngelOneProvider
from .history_store import HistoryStore


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

SYMBOLS = [
    "TCS",
    "INFY",
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
]

INTERVAL = "5m"
TRADING_DAYS = 30

# Keep a conservative gap between historical requests.
REQUEST_DELAY = 0.5


# ---------------------------------------------------------
# DATE RANGE
# ---------------------------------------------------------

def get_end_date():
    """
    Use the most recent weekday as the initial end date.

    On Saturday/Sunday this moves back to Friday.
    Angel One will return the available candles within
    the requested range.
    """

    now = pd.Timestamp.now(tz="Asia/Kolkata").normalize()

    while now.weekday() >= 5:
        now -= pd.Timedelta(days=1)

    return now + pd.Timedelta(hours=15, minutes=30)


def get_start_date(end_date):
    """
    Go back far enough to contain approximately
    30 trading sessions.
    """

    return end_date - pd.Timedelta(days=45)


# ---------------------------------------------------------
# BOOTSTRAP
# ---------------------------------------------------------

def main():

    end_date = get_end_date()
    start_date = get_start_date(end_date)

    print()
    print("=" * 70)
    print("ANGEL ONE → HISTORICAL BOOTSTRAP")
    print("=" * 70)
    print()
    print("Interval       :", INTERVAL)
    print("Start          :", start_date)
    print("End            :", end_date)
    print("Trading stocks :", len(SYMBOLS))
    print()

    provider = AngelOneProvider()
    store = HistoryStore()

    print("Logging into Angel One...")
    provider.login()
    print("Authentication : OK")
    print()

    total_added = 0

    for symbol in SYMBOLS:

        print("-" * 70)
        print(f"Fetching {symbol}...")

        try:

            df = provider.get_candles(
                symbol=symbol,
                interval=INTERVAL,
                from_datetime=start_date,
                to_datetime=end_date,
            )

            if df.empty:
                print("  WARNING: No candles returned.")
                continue

            print("  Candles received :", len(df))
            print(
                "  First candle     :",
                df["Datetime"].iloc[0],
            )
            print(
                "  Last candle      :",
                df["Datetime"].iloc[-1],
            )

            added = store.save_candles(
                symbol,
                df,
            )

            total_added += added

            print("  New candles saved :", added)
            print(
                "  Total in database:",
                store.count_candles(symbol),
            )

        except Exception as exc:

            print(
                f"  ERROR: {type(exc).__name__}: {exc}"
            )

        time.sleep(REQUEST_DELAY)

    print()
    print("=" * 70)
    print("BOOTSTRAP COMPLETE")
    print("=" * 70)
    print()
    print("New candles added:", total_added)
    print()

    for symbol in SYMBOLS:
        print(
            f"{symbol:12} "
            f"{store.count_candles(symbol):5} candles"
        )

    print()
    print("Database:")
    print(store.db_path)
    print()


if __name__ == "__main__":
    main()
