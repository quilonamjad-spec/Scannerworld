import time

import pandas as pd
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from .data_provider import AngelOneProvider
from .history_store import HistoryStore

SYMBOL = "TCS"

CORRELATION_ID = "scanner2-candle-test"

# Quote mode gives us LTP + traded quantity + day volume.
MODE = 2

# NSE
EXCHANGE_TYPE = 1

CANDLE_MINUTES = 5


class CandleBuilder:

    def __init__(self, symbol):
        self.symbol = symbol

        self.candle_start = None
        self.open = None
        self.high = None
        self.low = None
        self.close = None
        self.volume = 0

        self.last_day_volume = None

    def _candle_start(self, timestamp):
        """
        Convert a tick timestamp into its 5-minute
        candle start time.
        """

        timestamp = pd.Timestamp(timestamp)

        minute = (
            timestamp.minute
            // CANDLE_MINUTES
        ) * CANDLE_MINUTES

        return timestamp.replace(
            minute=minute,
            second=0,
            microsecond=0,
        )

    def _finalize(self):

        if self.candle_start is None:
            return None

        candle = {
            "Datetime": self.candle_start,
            "Open": self.open,
            "High": self.high,
            "Low": self.low,
            "Close": self.close,
            "Volume": self.volume,
        }

        return candle

    def update(self, timestamp, price, quantity):

        candle_start = self._candle_start(timestamp)

        # First tick.
        if self.candle_start is None:

            self.candle_start = candle_start

            self.open = price
            self.high = price
            self.low = price
            self.close = price
            self.volume = quantity

            return None

        # New 5-minute interval.
        if candle_start > self.candle_start:

            completed = self._finalize()

            # Start the new candle.
            self.candle_start = candle_start

            self.open = price
            self.high = price
            self.low = price
            self.close = price
            self.volume = quantity

            return completed

        # Same candle.
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += quantity

        return None


def main():

    print()
    print("=" * 70)
    print("ANGEL ONE → WEBSOCKET → 5-MINUTE CANDLE TEST")
    print("=" * 70)
    print()

    provider = AngelOneProvider()

    print("Logging into Angel One...")
    login_response = provider.login()

    print("Authentication : OK")

    auth_token = login_response["data"]["jwtToken"]
    feed_token = provider.smart_api.getfeedToken()

    instrument = provider.resolve_symbol(SYMBOL)

    print()
    print("Symbol         :", SYMBOL)
    print("Trading symbol :", instrument["tradingsymbol"])
    print("Symbol token   :", instrument["symboltoken"])
    print()

    builder = CandleBuilder(SYMBOL)
    store = HistoryStore()

    sws = SmartWebSocketV2(
        auth_token,
        provider.api_key,
        provider.client_id,
        feed_token,
    )

    token_list = [
        {
            "exchangeType": EXCHANGE_TYPE,
            "tokens": [
                instrument["symboltoken"]
            ],
        }
    ]

    def on_open(wsapp):

        print("WEBSOCKET OPEN")
        print("Subscribing to", SYMBOL)
        print()

        sws.subscribe(
            CORRELATION_ID,
            MODE,
            token_list,
        )

    def on_data(wsapp, message):

        try:

            timestamp_ms = message.get(
                "exchange_timestamp"
            )

            price_raw = message.get(
                "last_traded_price"
            )

            quantity_raw = message.get(
                "last_traded_quantity",
                0,
            )

            if timestamp_ms is None or price_raw is None:
                return

            timestamp = pd.to_datetime(
                timestamp_ms,
                unit="ms",
                utc=True,
            ).tz_convert(
                "Asia/Kolkata"
            )

            price = float(price_raw) / 100.0
            quantity = float(quantity_raw)

            completed = builder.update(
                timestamp,
                price,
                quantity,
            )

            if completed is not None:

                print()
                print("=" * 70)
                print("5-MINUTE CANDLE COMPLETED")
                print("=" * 70)

                for key, value in completed.items():
                    print(
                        f"{key:10}: {value}"
                    )

                candle_df = pd.DataFrame([completed])

                added = store.save_candles(
                    SYMBOL,
                    candle_df,
                )

                print()
                print("Saved to HistoryStore :", added)
                print(
                    "Total stored candles  :",
                    store.count_candles(SYMBOL),
                )

                print("=" * 70)

        except Exception as exc:

            print()
            print(
                "CANDLE ERROR:",
                type(exc).__name__,
                exc,
            )

    def on_error(wsapp, error):

        print()
        print("WEBSOCKET ERROR")
        print(error)

    def on_close(wsapp):

        print()
        print("WEBSOCKET CLOSED")

    sws.on_open = on_open
    sws.on_data = on_data
    sws.on_error = on_error
    sws.on_close = on_close

    print("Connecting to Angel One WebSocket...")
    print()

    sws.connect()


if __name__ == "__main__":
    main()
