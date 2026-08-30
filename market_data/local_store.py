"""Shared local SQLite cache for 5-minute OHLCV candles.

This is intentionally scanner-agnostic. It stores the common dataframe
contract used by the Market Lab:
    Open, High, Low, Close, Volume
with an IST-aware DatetimeIndex returned by ``read_symbol``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import timedelta

import pandas as pd
import yfinance as yf


DB_PATH = Path(__file__).resolve().parent.parent / "candle_store.db"
RETENTION_DAYS = 20
BACKFILL_SAFETY_DAYS = 1


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS candles (
            symbol TEXT NOT NULL,
            ts TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (symbol, ts)
        )
        """
    )
    return conn


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = out.columns.get_level_values(0)
    if out.index.tz is None:
        out.index = out.index.tz_localize("Asia/Kolkata")
    else:
        out.index = out.index.tz_convert("Asia/Kolkata")
    out.index.name = None
    required = ["Open", "High", "Low", "Close", "Volume"]
    return out[required].dropna(subset=["Open", "High", "Low", "Close"])


def get_symbol_max_ts(symbol: str):
    conn = _get_conn()
    row = conn.execute(
        "SELECT MAX(ts) FROM candles WHERE symbol = ?", (symbol,)
    ).fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def get_store_max_ts():
    conn = _get_conn()
    row = conn.execute("SELECT MAX(ts) FROM candles").fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def upsert_bars(symbol: str, df: pd.DataFrame) -> int:
    df = _normalise(df)
    if df.empty:
        return 0
    conn = _get_conn()
    rows = [
        (
            symbol,
            ts.isoformat(),
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            float(row["Volume"]),
        )
        for ts, row in df.iterrows()
    ]
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO candles "
        "(symbol, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    inserted = conn.total_changes - before
    conn.close()
    return inserted


def read_symbol(symbol: str, start=None, end=None) -> pd.DataFrame:
    conn = _get_conn()
    query = (
        "SELECT ts, open, high, low, close, volume "
        "FROM candles WHERE symbol = ?"
    )
    params = [symbol]
    if start is not None:
        query += " AND ts >= ?"
        params.append(pd.Timestamp(start).isoformat())
    if end is not None:
        query += " AND ts <= ?"
        params.append(pd.Timestamp(end).isoformat())
    query += " ORDER BY ts"
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if df.empty:
        return df
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df.index.name = None
    df.columns = ["Open", "High", "Low", "Close", "Volume"]
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df


def _split_fresh_by_ticker(tickers: list[str], fresh: pd.DataFrame) -> dict[str, pd.DataFrame]:
    frames = {}
    for ticker in tickers:
        try:
            if len(tickers) == 1:
                sdf = fresh
            else:
                if ticker not in fresh.columns.get_level_values(0):
                    continue
                sdf = fresh[ticker].dropna(how="all")
            if not sdf.empty:
                frames[ticker] = _normalise(sdf)
        except Exception:
            continue
    return frames


def update_store(tickers: list[str], period: str, interval: str = "5m") -> int:
    """Seed missing symbols and incrementally update existing symbols.

    A single Yahoo batch is used for the requested ticker set. Existing
    symbols start from their own latest stored candle; missing symbols get
    the full requested period. A one-day overlap makes gaps safe and the
    primary key prevents duplicates.
    """
    tickers = list(dict.fromkeys(str(t) for t in tickers))
    if not tickers:
        return 0

    latest = {t: get_symbol_max_ts(t) for t in tickers}
    missing = [t for t in tickers if latest[t] is None]
    existing = [t for t in tickers if latest[t] is not None]

    # Yahoo's batch API has one start/period for all tickers. If any symbol is
    # missing, use the requested period; otherwise start from the oldest
    # latest timestamp among the requested symbols. This safely catches up
    # every symbol while still avoiding a full re-download once all are seeded.
    if missing:
        print(
            f"[local_store] BACKFILL — {len(missing)} symbol(s) missing; "
            f"fetching {period} for {len(tickers)} tickers."
        )
        fresh = yf.download(
            tickers=tickers,
            period=period,
            interval=interval,
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=False,
        )
    else:
        oldest_latest = min(latest.values())
        start = (oldest_latest - pd.Timedelta(days=BACKFILL_SAFETY_DAYS)).strftime("%Y-%m-%d")
        print(
            f"[local_store] INCREMENTAL — oldest requested symbol bar is "
            f"{oldest_latest}; fetching Yahoo since {start}."
        )
        fresh = yf.download(
            tickers=tickers,
            start=start,
            interval=interval,
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=False,
        )

    if fresh.empty:
        print("[local_store] Yahoo returned nothing; store unchanged.")
        return 0

    total = 0
    for ticker, frame in _split_fresh_by_ticker(tickers, fresh).items():
        # For already-seeded symbols, keep only the incremental portion. The
        # upsert is safe even when the one-day overlap is retained.
        total += upsert_bars(ticker, frame)

    print(f"[local_store] {total} new bars added.")
    return total


def prune_old(retention_days: int = RETENTION_DAYS) -> None:
    cutoff = (
        pd.Timestamp.now(tz="Asia/Kolkata") - timedelta(days=retention_days)
    ).isoformat()
    conn = _get_conn()
    conn.execute("DELETE FROM candles WHERE ts < ?", (cutoff,))
    conn.commit()
    conn.close()


def store_summary() -> dict:
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(ts), MAX(ts) FROM candles"
    ).fetchone()
    conn.close()
    return {
        "symbols_cached": row[0],
        "total_bars": row[1],
        "oldest_bar": row[2],
        "newest_bar": row[3],
    }
