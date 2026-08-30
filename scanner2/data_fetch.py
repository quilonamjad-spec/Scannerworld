"""
data_fetch.py
-------------
Scanner 2 market-data layer.

Stock intraday OHLCV is served through the shared candle store. The common
store can use the VM database service through the SSH tunnel. Yahoo is used
only by update_store() for missing/incremental data.

The Nifty 500 constituent lookup and index-data path remain unchanged.
"""

import io
import os

import pandas as pd
import requests
import yfinance as yf

from market_data.local_store import read_symbols, update_store

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
}

NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
FALLBACK_CSV = os.path.join(os.path.dirname(__file__), "data", "nifty500_fallback.csv")


def get_nifty500_list(timeout: int = 10):
    """
    Returns (df, source_label) where df has columns:
        Company Name, Industry, Symbol, Series, ISIN Code
    source_label is "live" or "fallback" so the UI can warn the user.
    """
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=timeout)
        resp = session.get(NIFTY500_URL, headers=NSE_HEADERS, timeout=timeout)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        if "Symbol" in df.columns and len(df) > 100:
            return df, "live"
    except Exception:
        pass

    if os.path.exists(FALLBACK_CSV):
        df = pd.read_csv(FALLBACK_CSV)
        return df, "fallback"

    raise RuntimeError(
        "Could not fetch the Nifty500 list live from NSE, and no fallback "
        "CSV was found at data/nifty500_fallback.csv."
    )


def to_yf_symbol(nse_symbol: str) -> str:
    """NSE symbols need a .NS suffix for Yahoo Finance."""
    return f"{nse_symbol.strip()}.NS"


def _period_start(period: str) -> pd.Timestamp:
    """Convert the Scanner 2 period argument (e.g. 5d) into a DB read start."""
    text = str(period).strip().lower()
    try:
        if text.endswith("d"):
            days = int(text[:-1])
        elif text.endswith("h"):
            days = max(1, int(text[:-1]) / 24)
        else:
            days = 5
    except ValueError:
        days = 5
    return pd.Timestamp.now(tz="Asia/Kolkata") - pd.Timedelta(days=days)


def fetch_batch(symbols, interval="15m", period="5d", pause=1.0, batch_size=50):
    """Update and read stock candles through the shared database.

    The update checks Yahoo for missing/incremental data, then the VM read is
    limited to the requested period so a full historical database is never
    returned to the Scanner 2 process.
    """
    symbols = [str(s).strip().upper() for s in symbols]
    if not symbols:
        return {}

    update_store(symbols, period=period, interval=interval)
    start = _period_start(period)
    frames = read_symbols(symbols, start=start, interval=interval)

    return {symbol.replace(".NS", ""): df for symbol, df in frames.items() if not df.empty}


def fetch_single(symbol, interval="15m", period="5d"):
    """Update/read one stock from the shared database."""
    symbol = str(symbol).strip().upper()
    update_store([symbol], period=period, interval=interval)
    start = _period_start(period)
    frames = read_symbols([symbol], start=start, interval=interval)
    key = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    return frames.get(key, pd.DataFrame())


def fetch_index(index_symbol="^NSEI", interval="5m", period="5d"):
    """
    Fetch OHLCV for a market index (default: Nifty 50, ^NSEI). Indexes use
    their raw Yahoo ticker directly -- NOT the common equity candle store.
    """
    df = yf.Ticker(index_symbol).history(
        period=period, interval=interval, auto_adjust=False
    )
    return df.dropna(how="all")
