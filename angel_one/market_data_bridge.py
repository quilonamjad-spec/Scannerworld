"""
Unified Angel One market-data bridge.

The bridge separates market-data acquisition from scanner logic. Historical
candles come from the local HistoryStore and today's completed candles can be
fed in by the WebSocket candle builder.

Standard DataFrame contract:
    Datetime | Open | High | Low | Close | Volume

This module deliberately does not modify Scanner 1/2/3/4 logic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from .data_provider import AngelOneProvider
from .history_store import HistoryStore


INTERVAL = "5m"
CANDLE_MINUTES = 5
WEBSOCKET_MODE = 2
EXCHANGE_TYPE = 1
REQUEST_DELAY = 0.5


def clean_symbol(symbol: str) -> str:
    """Return a normal NSE symbol such as TCS."""
    return (
        str(symbol)
        .strip()
        .upper()
        .removesuffix(".NS")
        .removesuffix("-EQ")
    )


def get_market_close() -> pd.Timestamp:
    """Return the most recent NSE 15:30 close timestamp."""
    now = pd.Timestamp.now(tz="Asia/Kolkata")
    date = now.normalize()
    while date.weekday() >= 5:
        date -= pd.Timedelta(days=1)
    return date + pd.Timedelta(hours=15, minutes=30)


def _as_ist(timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        return ts.tz_localize("Asia/Kolkata")
    return ts.tz_convert("Asia/Kolkata")


@dataclass
class CandleBuilder:
    """Build completed 5-minute OHLCV candles from WebSocket ticks."""

    symbol: str
    candle_start: pd.Timestamp | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float = 0.0

    def _candle_start(self, timestamp) -> pd.Timestamp:
        ts = _as_ist(timestamp)
        minute = (ts.minute // CANDLE_MINUTES) * CANDLE_MINUTES
        return ts.replace(minute=minute, second=0, microsecond=0)

    def _finalize(self) -> dict | None:
        if self.candle_start is None:
            return None
        return {
            "Datetime": self.candle_start,
            "Open": self.open,
            "High": self.high,
            "Low": self.low,
            "Close": self.close,
            "Volume": self.volume,
        }

    def update(self, timestamp, price: float, quantity: float = 0.0):
        """Update active candle and return a completed candle when it rolls."""
        candle_start = self._candle_start(timestamp)

        if self.candle_start is None:
            self.candle_start = candle_start
            self.open = price
            self.high = price
            self.low = price
            self.close = price
            self.volume = quantity
            return None

        if candle_start > self.candle_start:
            completed = self._finalize()
            self.candle_start = candle_start
            self.open = price
            self.high = price
            self.low = price
            self.close = price
            self.volume = quantity
            return completed

        if candle_start < self.candle_start:
            return None

        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += quantity
        return None


class AngelOneMarketDataBridge:
    """Unified Angel One market-data interface for the scanner experiment."""

    def __init__(
        self,
        provider: AngelOneProvider | None = None,
        store: HistoryStore | None = None,
    ):
        self.provider = provider or AngelOneProvider()
        self.store = store or HistoryStore()
        self._logged_in = False
        self._instruments: dict[str, dict] = {}

    def login(self):
        """Authenticate once and reuse the provider session."""
        if not self._logged_in:
            self.provider.login()
            self._logged_in = True
        return self.provider.smart_api

    def resolve_symbol(self, symbol: str) -> dict:
        """Resolve normal symbol -> Angel One trading symbol/token."""
        symbol = clean_symbol(symbol)
        if symbol not in self._instruments:
            self.login()
            self._instruments[symbol] = self.provider.resolve_symbol(symbol)
        return self._instruments[symbol]

    def update_symbol(
        self,
        symbol: str,
        market_close: pd.Timestamp | None = None,
    ) -> int:
        """Bring one symbol's local history up to the requested close."""
        symbol = clean_symbol(symbol)
        latest = self.store.get_latest_timestamp(symbol)
        if latest is None:
            raise RuntimeError(
                f"{symbol} has no local history. Run history_bootstrap.py first."
            )

        close = _as_ist(market_close or get_market_close())
        from_datetime = _as_ist(latest) + pd.Timedelta(minutes=5)
        if from_datetime >= close:
            return 0

        self.login()
        df = self.provider.get_candles(
            symbol=symbol,
            interval=INTERVAL,
            from_datetime=from_datetime,
            to_datetime=close,
        )
        if df.empty:
            return 0
        return self.store.save_candles(symbol, df)

    def update_symbols(
        self,
        symbols,
        market_close: pd.Timestamp | None = None,
        delay: float = REQUEST_DELAY,
    ) -> dict[str, int]:
        """Update several symbols and return per-symbol insert counts."""
        self.login()
        results: dict[str, int] = {}
        for raw_symbol in symbols:
            symbol = clean_symbol(raw_symbol)
            try:
                results[symbol] = self.update_symbol(symbol, market_close)
            except Exception:
                results[symbol] = -1
            if delay:
                time.sleep(delay)
        return results

    def get_data(
        self,
        symbol: str,
        from_datetime=None,
        to_datetime=None,
        ensure_history: bool = False,
    ) -> pd.DataFrame:
        """Return the standard OHLCV DataFrame from local history."""
        symbol = clean_symbol(symbol)
        if ensure_history:
            self.update_symbol(symbol, market_close=to_datetime)

        df = self.store.get_candles(
            symbol,
            from_datetime=from_datetime,
            to_datetime=to_datetime,
        )
        if df.empty:
            return df

        columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        df = df[columns].copy()
        df["Datetime"] = pd.to_datetime(df["Datetime"])
        for column in columns[1:]:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        return (
            df.dropna(subset=columns[:5])
            .sort_values("Datetime")
            .reset_index(drop=True)
        )

    def get_data_for_symbols(
        self,
        symbols,
        from_datetime=None,
        to_datetime=None,
        ensure_history: bool = False,
    ) -> dict[str, pd.DataFrame]:
        """Return standard OHLCV frames for several symbols."""
        return {
            clean_symbol(symbol): self.get_data(
                symbol,
                from_datetime=from_datetime,
                to_datetime=to_datetime,
                ensure_history=ensure_history,
            )
            for symbol in symbols
        }

    def start_websocket(
        self,
        symbols,
        on_candle: Callable[[str, dict], None] | None = None,
        correlation_id: str = "market-data-bridge",
    ):
        """Start multi-symbol NSE WebSocket and persist completed 5m candles."""
        symbols = [clean_symbol(s) for s in symbols]
        symbols = list(dict.fromkeys(s for s in symbols if s))
        if not symbols:
            raise ValueError("No symbols supplied to WebSocket")

        self.login()
        feed_token = self.provider.smart_api.getfeedToken()
        auth_token = self.provider.smart_api.access_token
        if not auth_token:
            raise RuntimeError("Angel One access token is unavailable")

        builders = {symbol: CandleBuilder(symbol) for symbol in symbols}
        token_to_symbol = {}
        for symbol in symbols:
            instrument = self.resolve_symbol(symbol)
            token_to_symbol[str(instrument["symboltoken"])] = symbol

        token_list = [{
            "exchangeType": EXCHANGE_TYPE,
            "tokens": list(token_to_symbol),
        }]

        sws = SmartWebSocketV2(
            auth_token,
            self.provider.api_key,
            self.provider.client_id,
            feed_token,
        )

        def handle_open(wsapp):
            print("WEBSOCKET OPEN")
            print("Subscribing to:", ", ".join(symbols))
            sws.subscribe(correlation_id, WEBSOCKET_MODE, token_list)

        def handle_data(wsapp, message):
            try:
                token = str(message.get("token", ""))
                symbol = token_to_symbol.get(token)
                if symbol is None:
                    return

                timestamp_ms = message.get("exchange_timestamp")
                price_raw = message.get("last_traded_price")
                quantity_raw = message.get("last_traded_quantity", 0)
                if timestamp_ms is None or price_raw is None:
                    return

                timestamp = pd.to_datetime(
                    timestamp_ms, unit="ms", utc=True
                ).tz_convert("Asia/Kolkata")
                price = float(price_raw) / 100.0
                quantity = float(quantity_raw or 0)

                completed = builders[symbol].update(timestamp, price, quantity)
                if completed is None:
                    return

                self.store.save_candles(symbol, pd.DataFrame([completed]))
                if on_candle is not None:
                    on_candle(symbol, completed)
            except Exception as exc:
                print("WEBSOCKET CANDLE ERROR:", type(exc).__name__, exc)

        def handle_error(wsapp, error):
            print("WEBSOCKET ERROR")
            print(error)

        def handle_close(wsapp):
            print("WEBSOCKET CLOSED")

        sws.on_open = handle_open
        sws.on_data = handle_data
        sws.on_error = handle_error
        sws.on_close = handle_close

        print("Connecting to Angel One WebSocket...")
        sws.connect()


def main():
    """Smoke-test the bridge without making repeated Angel search calls."""
    symbols = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "ICICIBANK"]
    bridge = AngelOneMarketDataBridge()

    print()
    print("=" * 70)
    print("ANGEL ONE MARKET DATA BRIDGE TEST")
    print("=" * 70)
    print()

    # One login is enough. The smoke test deliberately does NOT call
    # searchScrip() for every stock. Symbol/token resolution belongs to the
    # WebSocket setup and should eventually be backed by a persistent map.
    bridge.login()
    print("Authentication : OK")
    print()
    print("Local history:")

    for symbol in symbols:
        df = bridge.get_data(symbol)
        latest = df["Datetime"].iloc[-1] if not df.empty else None
        print(f"{symbol:12} rows={len(df):5} latest={latest}")

    print()
    print("Bridge history test complete.")


if __name__ == "__main__":
    main()
