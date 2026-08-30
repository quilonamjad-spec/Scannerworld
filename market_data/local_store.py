"""Shared SQLite candle store with optional VM database bridge.

By default the store uses the local candle_store.db. When MARKETLAB_DB_URL is
set, reads/writes go through the Market Lab DB service over the SSH tunnel.
Yahoo is still used here only to obtain fresh candles; the VM is the
persistent database host.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sqlite3
import urllib.error
import urllib.parse
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
    url = f"{DB_SERVICE_URL}{path}"
    data = None
    headers = {"Accept-Encoding": "gzip"}
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                body = gzip.decompress(body)
            body = body.decode("utf-8")
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
    value = str(symbol).strip().upper()
    return value if value.endswith(".NS") else f"{value}.NS"


def _get_conn(interval: str = "5m") -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    table = _table(interval)
    conn.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        symbol TEXT NOT NULL, ts TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volume REAL,
        PRIMARY KEY (symbol, ts))""")
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
        return get_symbol_max_ts_batch([symbol], interval).get(symbol)
    conn = _get_conn(interval)
    row = conn.execute(f"SELECT MAX(ts) FROM {_table(interval)} WHERE symbol = ?", (symbol,)).fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def get_symbol_max_ts_batch(symbols: list[str], interval: str = "5m") -> dict[str, pd.Timestamp | None]:
    symbols = [_canonical_symbol(s) for s in symbols]
    if not symbols:
        return {}
    if _remote_enabled():
        result = _remote_request("POST", "/latest_batch", {"symbols": symbols, "interval": interval})
        return {s: (None if result.get(s) is None else pd.Timestamp(result[s])) for s in symbols}
    conn = _get_conn(interval)
    table = _table(interval)
    rows = conn.execute(f"SELECT symbol, MAX(ts) FROM {table} WHERE symbol IN ({','.join('?' for _ in symbols)}) GROUP BY symbol", symbols).fetchall()
    conn.close()
    found = {s: (None if ts is None else pd.Timestamp(ts)) for s, ts in rows}
    return {s: found.get(s) for s in symbols}


def get_store_max_ts(interval: str = "5m"):
    if _remote_enabled():
        value = _remote_request("GET", f"/summary?interval={urllib.parse.quote(interval)}").get("newest")
        return None if value is None else pd.Timestamp(value)
    conn = _get_conn(interval)
    row = conn.execute(f"SELECT MAX(ts) FROM {_table(interval)}").fetchone()
    conn.close()
    return None if not row or row[0] is None else pd.Timestamp(row[0])


def upsert_bars(symbol: str, df: pd.DataFrame, interval: str = "5m") -> int:
    return upsert_bars_batch({symbol: df}, interval=interval)


def upsert_bars_batch(frames: dict[str, pd.DataFrame], interval: str = "5m") -> int:
    clean_frames = {}
    for symbol, df in frames.items():
        df = _normalise(df)
        if not df.empty:
            clean_frames[_canonical_symbol(symbol)] = df
    if not clean_frames:
        return 0

    if _remote_enabled():
        payload = {"interval": interval, "frames": {
            symbol: [
                {"ts": ts.isoformat(), "Open": float(row["Open"]), "High": float(row["High"]),
                 "Low": float(row["Low"]), "Close": float(row["Close"]), "Volume": float(row["Volume"])}
                for ts, row in df.iterrows()
            ] for symbol, df in clean_frames.items()
        }}
        return int(_remote_request("POST", "/upsert_batch", payload, timeout=120).get("inserted", 0))

    conn = _get_conn(interval)
    table = _table(interval)
    rows = []
    for symbol, df in clean_frames.items():
        rows.extend((symbol, ts.isoformat(), float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"]), float(row["Volume"])) for ts, row in df.iterrows())
    before = conn.total_changes
    conn.executemany(f"INSERT OR IGNORE INTO {table} (symbol, ts, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    inserted = conn.total_changes - before
    conn.close()
    return inserted


def _frame_from_rows(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    if isinstance(rows[0], (list, tuple)) and len(rows[0]) == 6:
        df = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    else:
        df = pd.DataFrame(rows)
        if "ts" not in df.columns:
            return pd.DataFrame()
        df = df[["ts", "Open", "High", "Low", "Close", "Volume"]]
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts")
    df.index.name = None
    if df.index.tz is None:
        df.index = df.index.tz_localize("Asia/Kolkata")
    else:
        df.index = df.index.tz_convert("Asia/Kolkata")
    return df


def read_symbol(symbol: str, start=None, end=None, interval: str = "5m") -> pd.DataFrame:
    symbol = _canonical_symbol(symbol)
    if _remote_enabled():
        frames = read_symbols([symbol], start=start, end=end, interval=interval)
        return frames.get(symbol, pd.DataFrame())
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
    return _frame_from_rows(df.to_dict("records"))


def read_symbols(symbols: list[str], start=None, end=None, interval: str = "5m") -> dict[str, pd.DataFrame]:
    symbols = [_canonical_symbol(s) for s in symbols]
    if not symbols:
        return {}
    if _remote_enabled():
        payload = {"symbols": symbols, "interval": interval}
        if start is not None:
            payload["start"] = pd.Timestamp(start).isoformat()
        if end is not None:
            payload["end"] = pd.Timestamp(end).isoformat()
        result = _remote_request("POST", "/candles_batch", payload, timeout=180)
        frames = {}
        for symbol, rows in result.get("frames", {}).items():
            frame = _frame_from_rows(rows)
            if not frame.empty:
                frames[symbol] = frame
        return frames
    return {s: read_symbol(s, start=start, end=end, interval=interval) for s in symbols}


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
    tickers = list(dict.fromkeys(_canonical_symbol(t) for t in tickers))
    if not tickers:
        return 0

    latest = get_symbol_max_ts_batch(tickers, interval=interval)
    missing = [t for t in tickers if latest[t] is None]

    if missing:
        print(f"[local_store] BACKFILL {interval} — {len(missing)} symbol(s) missing; fetching {period} for {len(tickers)} tickers.")
        fresh = yf.download(tickers=tickers, period=period, interval=interval, group_by="ticker", threads=True, progress=False, auto_adjust=False)
    else:
        oldest_latest = min(latest.values())
        start = (oldest_latest - pd.Timedelta(days=BACKFILL_SAFETY_DAYS)).strftime("%Y-%m-%d")
        print(f"[local_store] INCREMENTAL {interval} — oldest stored bar is {oldest_latest}; fetching Yahoo since {start}.")
        fresh = yf.download(tickers=tickers, start=start, interval=interval, group_by="ticker", threads=True, progress=False, auto_adjust=False)

    if fresh.empty:
        print(f"[local_store] Yahoo returned nothing for {interval}; store unchanged.")
        return 0

    frames = _split_fresh_by_ticker(tickers, fresh)
    total = upsert_bars_batch(frames, interval=interval)
    print(f"[local_store] {total} new {interval} bars added.")
    return total


def prune_old(retention_days: int = RETENTION_DAYS) -> None:
    if _remote_enabled():
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
        result = _remote_request("GET", f"/summary?interval={urllib.parse.quote(interval)}")
        return {
            "interval": interval,
            "symbols_cached": result.get("symbols", 0),
            "total_bars": result.get("candles", 0),
            "oldest_bar": result.get("oldest"),
            "newest_bar": result.get("newest"),
        }

    conn = _get_conn(interval)
    table = _table(interval)
    row = conn.execute(f"SELECT COUNT(DISTINCT symbol), COUNT(*), MIN(ts), MAX(ts) FROM {table}").fetchone()
    conn.close()
    return {
        "interval": interval,
        "symbols_cached": row[0],
        "total_bars": row[1],
        "oldest_bar": row[2],
        "newest_bar": row[3],
    }
