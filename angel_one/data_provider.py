import os

import pandas as pd
import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect


load_dotenv()


class AngelOneProvider:
    """
    Small Angel One market-data wrapper.

    Contract:
        NSE equity symbol in
            ->
        DataFrame with:
            Datetime | Open | High | Low | Close | Volume
    """

    def __init__(self):
        self.api_key = os.getenv("ANGEL_API_KEY")
        self.client_id = os.getenv("ANGEL_CLIENT_ID")
        self.pin = os.getenv("ANGEL_PIN")
        self.totp_secret = os.getenv("ANGEL_TOTP_SECRET")

        self.smart_api = None
        self._tokens = {}

    # ---------------------------------------------------------
    # AUTHENTICATION
    # ---------------------------------------------------------

    def login(self):
        if not all([
            self.api_key,
            self.client_id,
            self.pin,
            self.totp_secret,
        ]):
            raise RuntimeError(
                "Missing Angel One credentials in .env"
            )

        totp = pyotp.TOTP(self.totp_secret).now()

        self.smart_api = SmartConnect(
            api_key=self.api_key
        )

        response = self.smart_api.generateSession(
            self.client_id,
            self.pin,
            totp,
        )

        if response.get("status") is not True:
            raise RuntimeError(
                f"Angel One login failed: {response}"
            )

        return response

    # ---------------------------------------------------------
    # SYMBOL RESOLUTION
    # ---------------------------------------------------------

    def resolve_symbol(self, symbol):
        """
        Resolve a normal NSE equity symbol such as TCS
        to its Angel One trading symbol and token.
        """

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
        )

        if symbol in self._tokens:
            return self._tokens[symbol]

        if self.smart_api is None:
            self.login()

        response = self.smart_api.searchScrip(
            "NSE",
            symbol,
        )

        if not response.get("status"):
            raise RuntimeError(
                f"Symbol search failed for {symbol}: "
                f"{response}"
            )

        matches = response.get("data") or []

        target = next(
            (
                item
                for item in matches
                if item.get("tradingsymbol")
                == f"{symbol}-EQ"
            ),
            None,
        )

        if target is None:
            raise RuntimeError(
                f"NSE equity {symbol}-EQ not found. "
                f"Search results: {matches}"
            )

        resolved = {
            "tradingsymbol": target["tradingsymbol"],
            "symboltoken": target["symboltoken"],
        }

        self._tokens[symbol] = resolved

        return resolved

    # ---------------------------------------------------------
    # CANDLE DATA
    # ---------------------------------------------------------

    def get_candles(
        self,
        symbol,
        interval="5m",
        from_datetime=None,
        to_datetime=None,
    ):
        """
        Return Angel One candles in the standard Market Lab
        DataFrame structure.
        """

        if self.smart_api is None:
            self.login()

        instrument = self.resolve_symbol(symbol)

        interval_map = {
            "1m": "ONE_MINUTE",
            "3m": "THREE_MINUTE",
            "5m": "FIVE_MINUTE",
            "10m": "TEN_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY",
        }

        if interval not in interval_map:
            raise ValueError(
                f"Unsupported interval: {interval}"
            )

        if from_datetime is None or to_datetime is None:
            raise ValueError(
                "from_datetime and to_datetime are required"
            )

        from_ts = pd.Timestamp(from_datetime)
        to_ts = pd.Timestamp(to_datetime)

        params = {
            "exchange": "NSE",
            "symboltoken": instrument["symboltoken"],
            "interval": interval_map[interval],
            "fromdate": from_ts.strftime(
                "%Y-%m-%d %H:%M"
            ),
            "todate": to_ts.strftime(
                "%Y-%m-%d %H:%M"
            ),
        }

        response = self.smart_api.getCandleData(
            params
        )

        if response.get("status") is not True:
            raise RuntimeError(
                f"Angel One candle request failed: "
                f"{response}"
            )

        rows = response.get("data") or []

        df = pd.DataFrame(
            rows,
            columns=[
                "Datetime",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
            ],
        )

        if df.empty:
            return df

        df["Datetime"] = pd.to_datetime(
            df["Datetime"]
        )

        for column in [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

        df = df.dropna(
            subset=[
                "Datetime",
                "Open",
                "High",
                "Low",
                "Close",
            ]
        )

        df = df.sort_values(
            "Datetime"
        ).reset_index(drop=True)

        return df
