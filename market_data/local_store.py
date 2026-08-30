"""Shared SQLite candle store with optional VM database bridge.

By default the store behaves exactly as before and uses the local
``candle_store.db``.  When ``MARKETLAB_DB_URL`` is set, database reads and
writes are sent to the Market Lab DB service over the SSH tunnel.  Yahoo is
still used here only for obtaining fresh candles; the VM remains the
persistent database host.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from datetime import timedelta

import pandas as pd
import yfinance as yf


DB_PATH = Path(__file__).resolve().parent.parent / "candle_store.db"
RETENTION_DAYS = 20
BACKFILL_SAFETY_DAYS = 1
DB_SERVICE_URL = os.getenv("MARKETLAB_DB_URL", "").strip().rstrip("/")


def _remote_enabled() -> bool:
    return bool(DB_SERVICE_URL)


def _remote_request(method: str, path: str, payload=None, timeout: int = 60):
    """Call the VM DB service through the local SSH tunnel."""
    url = f"{DB_SERVICE_URL}{path}"
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Market Lab DB service unavailable at {DB_SERVICE_URL}: {exc}"
        ) from exc

    result = json.loads(body)
    if isinstance(result, dict) and "error" in result:
        raise RuntimeError(f"Market Lab DB service error: {result['error']}")
    return result


def _table(interval: str) -> str:
    clean = str(interval).lower().strip()
    if not re.fullmatch(r"\d+[mhdw]", clean):
        raise ValueError(f"Unsupported interval: {interval}")
    return "candles" if clean == "5m" else f"candles_{clean}"


def _canonical_symbol(symbol: str) -> str:
    """Use one database/Yahoo symbol convention for NSE equities."""
    value = str(symbol).strip().upper()
    return value if value.endswith(".NS") else f"{value}.NS"


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
    symbol = _canonical_symbol(symbol)

    if _remote_enabled():
        result = _remote_request(
            "GET",
            f"/latest?symbol={urllib.parse.quote(symbol)}&interval={urllib.parse.quote(interval)}",
        )
        value = result.get("latest")
        return None if value is None else pd.Timestamp(value)

    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(
        f"SELECT MAX(ts) FROM {table} WHERE symbol = ?", (symbol,)
    ).fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def get_store_max_ts(interval: str = "5m"):
    if _remote_enabled():
        result = _remote_request(
            "GET", f"/summary?interval={urllib.parse.quote(interval)}"
        )
        value = result.get("newest")
        return None if value is None else pd.Timestamp(value)

    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(f"SELECT MAX(ts) FROM {table}").fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def upsert_bars(symbol: str, df: pd.DataFrame, interval: str = "5m") -> int:
    symbol = _canonical_symbol(symbol)
    df = _normalise(df)
    if df.empty:
        return 0

    if _remote_enabled():
        candles = [
            {
                "ts": ts.isoformat(),
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "Volume": float(row["Volume"]),
            }
            for ts, row in df.iterrows()
        ]
        result = _remote_request(
            "POST",
            "/upsert",
            payload={"symbol": symbol, "interval": interval, "candles": candles},
            timeout=120,
        )
        return int(result.get("inserted", 0))

    conn = _get_conn(interval)
    table = _table(interval)
    rows = [
        (symbol, ts.isoformat(), float(row["Open"]), float(row["High"]),
         float(row["Low"]), float(row["Close"]), float(row["Volume"]))
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
    symbol = _canonical_symbol(symbol)

    if _remote_enabled():
        result = _remote_request(
            "GET",
            f"/candles?symbol={urllib.parse.quote(symbol)}&interval={urllib.parse.quote(interval)}",
            timeout=120,
        )
        rows = result.get("candles", [])
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "ts" not in df.columns:
            return pd.DataFrame()
        df["ts"] = pd.to_datetime(df["ts"])
        df = df.set_index("ts")
        df.index.name = None
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        if df.index.tz is None:
            df.index = df.index.tz_localize("Asia/Kolkata")
        else:
            df.index = df.index.tz_convert("Asia/Kolkata")
        if start is not None:
            df = df[df.index >= pd.Timestamp(start)]
        if end is not None:
            df = df[df.index <= pd.Timestamp(end)]
        return df

    conn = _get_conn(interval)
    table = _table(interval)
    query = f"SELECT ts, open, high, low, close, volume FROM {table} WHERE symbol = ?"
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
    tickers = list(dict.fromkeys(_canonical_symbol(t) for t in tickers))
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
    if _remote_enabled():
        # Remote pruning will be added as a dedicated maintenance endpoint.
        return

    cutoff = (pd.Timestamp.now(tz="Asia/Kolkata") - timedelta(days=retention_days)).isoformat()
    for interval in ("5m", "15m", "30m", "1h"):
        conn = _get_conn(interval)
        table = _table(interval)
        conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
        conn.commit()
        conn.close()


def store_summary(interval: str = "5m") -> dict:
    if _remote_enabled():
        return _remote_request(
            "GET", f"/summary?interval={urllib.parse.quote(interval)}"
        )

    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(
        f"SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(ts), MAX(ts) FROM {table}"
    ).fetchone()
    conn.close()
    return {"interval": interval, "symbols_cached": row[0], "total_bars": row[1],
            "oldest_bar": row[2], "newest_bar": row[3]}
