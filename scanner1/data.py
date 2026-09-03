"""
data.py
-------
Scanner 1 market-data layer.

Stock 5-minute OHLCV is served read-only through the shared candle store.
Fresh candles are acquired separately by the standalone market-data updater.
Scanner 1 does not download or update stock candles.

Universe, sector mapping, and sector-index calculations remain unchanged.
"""

import io

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from config import (
    NSE500_URL, LOCAL_FALLBACK, IST_TZ, SECTOR_INDICES, SECTOR_PRIORITY,
    DEFAULT_SECTOR, DEFAULT_INDEX_YAHOO,
)

try:
    from market_data.local_store import read_symbol, read_symbols
except ImportError:
    from pathlib import Path
    import sys
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from market_data.local_store import read_symbol, read_symbols


@st.cache_data(ttl=60 * 60 * 24)
def get_nse500_symbols() -> list[str]:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(NSE500_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        symbols = df["Symbol"].astype(str).str.strip().tolist()
    except Exception:
        try:
            df = pd.read_csv(LOCAL_FALLBACK)
            symbols = df["Symbol"].astype(str).str.strip().tolist()
        except Exception:
            st.error(
                "Could not fetch the NSE 500 list from NSE's archive, and no "
                f"local fallback ('{LOCAL_FALLBACK}') was found. Add one to "
                "the repo root with a 'Symbol' column."
            )
            return []
    return [f"{s}.NS" for s in symbols]


@st.cache_data(ttl=60 * 60 * 24)
def get_symbol_sector_map() -> dict:
    mapping: dict = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    for sector in SECTOR_PRIORITY:
        try:
            resp = requests.get(SECTOR_INDICES[sector]["csv"], headers=headers, timeout=10)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            for sym in df["Symbol"].astype(str).str.strip():
                mapping.setdefault(sym, sector)
        except Exception:
            continue
    return mapping


@st.cache_data(ttl=60 * 10, show_spinner=False)
def fetch_index_batch(period: str, interval: str) -> pd.DataFrame:
    tickers = [cfg["yahoo"] for cfg in SECTOR_INDICES.values()] + [DEFAULT_INDEX_YAHOO]
    return yf.download(
        tickers=tickers, period=period, interval=interval,
        group_by="ticker", threads=True, progress=False, auto_adjust=False,
    )


def compute_index_pct_changes(as_of, lookback_days: int) -> dict:
    yahoo_to_sector = {cfg["yahoo"]: name for name, cfg in SECTOR_INDICES.items()}
    yahoo_to_sector[DEFAULT_INDEX_YAHOO] = DEFAULT_SECTOR
    tickers = list(yahoo_to_sector.keys())
    changes = {}
    try:
        batch = fetch_index_batch(period=f"{lookback_days}d", interval="5m")
    except Exception:
        return changes
    for tkr in tickers:
        try:
            idf = batch[tkr].dropna(how="all") if len(tickers) > 1 else batch
            if idf.empty:
                continue
            if idf.index.tz is None:
                idf.index = idf.index.tz_localize(IST_TZ)
            else:
                idf.index = idf.index.tz_convert(IST_TZ)
            data = idf[idf.index <= as_of]
            if data.empty:
                continue
            last = data.iloc[-1]
            same_day = data[data.index.date == last.name.date()]
            day_open = same_day["Open"].iloc[0]
            pct = round((last["Close"] - day_open) / day_open * 100, 2)
            changes[yahoo_to_sector[tkr]] = pct
        except Exception:
            continue
    return changes


# --------------------------------------------------------------------------
# STOCK OHLCV FETCH — READ-ONLY SHARED CANDLE DATABASE
# --------------------------------------------------------------------------
def _normalise_tickers(tickers) -> list[str]:
    return [str(t).strip().upper() for t in tickers]


def _read_batch_from_store(tickers: list[str], start_time=None, end_time=None) -> pd.DataFrame:
    frames = read_symbols(tickers, start=start_time, end=end_time, interval="5m")
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return next(iter(frames.values()))
    return pd.concat(frames, axis=1)


@st.cache_data(ttl=60 * 10, show_spinner=False)
def fetch_batch(tickers: tuple, period: str, interval: str) -> pd.DataFrame:
    """Read stock OHLCV from the shared DB only; never update/download.

    Keep the same effective history window as Scanner 1's former Yahoo
    request by limiting the DB read to the requested period. This avoids
    transferring the entire VM database for every scan batch.
    """
    clean = _normalise_tickers(tickers)
    try:
        days = max(1, int(str(period).rstrip("d")))
    except (TypeError, ValueError):
        days = 15
    start_time = pd.Timestamp.now(tz=IST_TZ) - pd.Timedelta(days=days)
    return _read_batch_from_store(clean, start_time=start_time)


def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


def fetch_symbol_5m_since(symbol_ns: str, start_time, lookback_days: int = 10) -> pd.DataFrame:
    """Read one symbol from the shared DB without updating it."""
    ticker = str(symbol_ns).strip().upper()
    return read_symbol(ticker, start=start_time, interval="5m")


def get_price_at(symbol_ns: str, timestamp, lookback_days: int = 10):
    """Return the last stored close at/before timestamp; DB read-only."""
    ticker = str(symbol_ns).strip().upper()
    df = read_symbol(ticker, end=timestamp, interval="5m")
    if df.empty:
        return None, None
    last = df.iloc[-1]
    return float(last["Close"]), df.index[-1]
