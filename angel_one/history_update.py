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

# Angel One request pacing.
REQUEST_DELAY = 0.5

# NSE market close.
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30


# ---------------------------------------------------------
# TIME HELPERS
# ---------------------------------------------------------

def get_market_close():
    """
    Return the most recent NSE market-close timestamp.

    If run on Saturday/Sunday, this points to the
    previous Friday.
    """

    now = pd.Timestamp.now(tz="Asia/Kolkata")

    # Move backwards to the most recent weekday.
    date = now.normalize()

    while date.weekday() >= 5:
        date -= pd.Timedelta(days=1)

    return date + pd.Timedelta(
        hours=MARKET_CLOSE_HOUR,
        minutes=MARKET_CLOSE_MINUTE,
    )


# ---------------------------------------------------------
# INCREMENTAL UPDATE
# ---------------------------------------------------------

def update_symbol(provider, store, symbol):

    latest = store.get_latest_timestamp(symbol)

    if latest is None:
        print(
            f"  WARNING: {symbol} has no history. "
            f"Run history_bootstrap.py first."
        )
        return 0

    # The next 5-minute candle after the latest stored candle.
    from_datetime = latest + pd.Timedelta(minutes=5)

    market_close = get_market_close()

    # Nothing to request if our history is already current.
    if from_datetime >= market_close:
        print("  Already up to date.")
        return 0

    print("  Latest stored :", latest)
    print("  Fetching from :", from_datetime)
    print("  Fetching to   :", market_close)

    df = provider.get_candles(
        symbol=symbol,
        interval=INTERVAL,
        from_datetime=from_datetime,
        to_datetime=market_close,
    )

    if df.empty:
        print("  No new candles returned.")
        return 0

    print("  Candles received :", len(df))

    added = store.save_candles(
        symbol,
        df,
    )

    print("  New candles saved:", added)
    print(
        "  Total in database:",
        store.count_candles(symbol),
    )

    return added


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main():

    print()
    print("=" * 70)
    print("ANGEL ONE → INCREMENTAL HISTORY UPDATE")
    print("=" * 70)
    print()

    print("Interval       :", INTERVAL)
    print("Stocks         :", len(SYMBOLS))
    print("Target close   :", get_market_close())
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
        print(f"Updating {symbol}...")

        try:

            added = update_symbol(
                provider,
                store,
                symbol,
            )

            total_added += added

        except Exception as exc:

            print(
                f"  ERROR: {type(exc).__name__}: {exc}"
            )

        time.sleep(REQUEST_DELAY)

    print()
    print("=" * 70)
    print("INCREMENTAL UPDATE COMPLETE")
    print("=" * 70)
    print()

    print("New candles added:", total_added)
    print()

    for symbol in SYMBOLS:
        print(
            f"{symbol:12} "
            f"{store.count_candles(symbol):5} candles "
            f"latest = {store.get_latest_timestamp(symbol)}"
        )

    print()
    print("Database:")
    print(store.db_path)
    print()


if __name__ == "__main__":
    main()
