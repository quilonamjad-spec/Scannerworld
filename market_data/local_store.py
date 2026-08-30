"""Shared local SQLite cache for intraday OHLCV candles.

The same database is shared by all scanners. Each interval has its own table
so Scanner 1's 5-minute candles cannot be confused with Scanner 2's
15-minute candles.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from datetime import timedelta

import pandas as pd
import yfinance as yf


DB_PATH = Path(__file__).resolve().parent.parent / "candle_store.db"
RETENTION_DAYS = 20
BACKFILL_SAFETY_DAYS = 1


def _table(interval: str) -> str:
    """Return a safe table name for a Yahoo interval such as 5m/15m."""
    clean = str(interval).lower().strip()
    if not re.fullmatch(r"\d+[mhdw]", clean):
        raise ValueError(f"Unsupported interval: {interval}")
    return "candles" if clean == "5m" else f"candles_{clean}"


def _get_conn(interval: str = "5m") -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    table = _table(interval)
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table} (
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


def get_symbol_max_ts(symbol: str, interval: str = "5m"):
    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(
        f"SELECT MAX(ts) FROM {table} WHERE symbol = ?", (symbol,)
    ).fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def get_store_max_ts(interval: str = "5m"):
    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(f"SELECT MAX(ts) FROM {table}").fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def upsert_bars(symbol: str, df: pd.DataFrame, interval: str = "5m") -> int:
    df = _normalise(df)
    if df.empty:
        return 0
    conn = _get_conn(interval)
    table = _table(interval)
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
        f"INSERT OR IGNORE INTO {table} "
        "(symbol, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    inserted = conn.total_changes - before
    conn.close()
    return inserted


def read_symbol(symbol: str, start=None, end=None, interval: str = "5m") -> pd.DataFrame:
    conn = _get_conn(interval)
    table = _table(interval)
    query = (
        f"SELECT ts, open, high, low, close, volume "
        f"FROM {table} WHERE symbol = ?"
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
    """Seed missing symbols and incrementally update existing symbols."""
    tickers = list(dict.fromkeys(str(t) for t in tickers))
    if not tickers:
        return 0

    latest = {t: get_symbol_max_ts(t, interval=interval) for t in tickers}
    missing = [t for t in tickers if latest[t] is None]

    if missing:
        print(
            f"[local_store] BACKFILL {interval} — {len(missing)} symbol(s) missing; "
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
            f"[local_store] INCREMENTAL {interval} — oldest stored bar is "
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
        print(f"[local_store] Yahoo returned nothing for {interval}; store unchanged.")
        return 0

    total = 0
    for ticker, frame in _split_fresh_by_ticker(tickers, fresh).items():
        total += upsert_bars(ticker, frame, interval=interval)

    print(f"[local_store] {total} new {interval} bars added.")
    return total


def prune_old(retention_days: int = RETENTION_DAYS) -> None:
    cutoff = (
        pd.Timestamp.now(tz="Asia/Kolkata") - timedelta(days=retention_days)
    ).isoformat()
    conn = _get_conn("5m")
    for interval in ("5m", "15m", "30m", "1h"):
        table = _table(interval)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM candles WHERE 0") if interval != "5m" else None
        conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
    conn.commit()
    conn.close()


def store_summary(interval: str = "5m") -> dict:
    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(ts), MAX(ts) FROM {table}"
    ).fetchone()
    conn.close()
    return {
        "interval": interval,
        "symbols_cached": row[0],
        "total_bars": row[1],
        "oldest_bar": row[2],
        "newest_bar": row[3],
    }
