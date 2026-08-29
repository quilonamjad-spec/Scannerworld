import sqlite3
from pathlib import Path

import pandas as pd


DB_PATH = Path(__file__).resolve().parent / "market_history.db"


class HistoryStore:
    """
    Local SQLite store for normalized OHLCV candles.

    The store knows nothing about Angel One.
    It simply saves and retrieves the standard Market Lab
    DataFrame structure.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self._create_table()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candles (
                    symbol TEXT NOT NULL,
                    datetime TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (symbol, datetime)
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_candles_symbol_datetime
                ON candles(symbol, datetime)
                """
            )

    def save_candles(self, symbol, df):
        """
        Save normalized OHLCV candles.

        Existing candles are left untouched.
        New candles are added.
        """

        if df is None or df.empty:
            return 0

        required = [
            "Datetime",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        missing = [
            column for column in required
            if column not in df.columns
        ]

        if missing:
            raise ValueError(
                f"Missing columns: {missing}"
            )

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
        )

        rows = []

        for _, row in df.iterrows():
            timestamp = pd.Timestamp(
                row["Datetime"]
            ).isoformat()

            rows.append(
                (
                    symbol,
                    timestamp,
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                )
            )

        with self._connect() as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM candles "
                "WHERE symbol = ?",
                (symbol,),
            ).fetchone()[0]

            conn.executemany(
                """
                INSERT OR IGNORE INTO candles
                (symbol, datetime, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )

            after = conn.execute(
                "SELECT COUNT(*) FROM candles "
                "WHERE symbol = ?",
                (symbol,),
            ).fetchone()[0]

        return after - before

    def get_candles(
        self,
        symbol,
        from_datetime=None,
        to_datetime=None,
    ):
        """
        Return candles in the same standard DataFrame structure.
        """

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
        )

        query = """
            SELECT
                datetime AS Datetime,
                open AS Open,
                high AS High,
                low AS Low,
                close AS Close,
                volume AS Volume
            FROM candles
            WHERE symbol = ?
        """

        params = [symbol]

        if from_datetime is not None:
            query += " AND datetime >= ?"
            params.append(
                pd.Timestamp(
                    from_datetime
                ).isoformat()
            )

        if to_datetime is not None:
            query += " AND datetime <= ?"
            params.append(
                pd.Timestamp(
                    to_datetime
                ).isoformat()
            )

        query += " ORDER BY datetime"

        with self._connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params=params,
            )

        if not df.empty:
            df["Datetime"] = pd.to_datetime(
                df["Datetime"]
            )

        return df

    def get_latest_timestamp(self, symbol):
        """
        Return the latest stored candle timestamp
        for a symbol, or None if no data exists.
        """

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
        )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(datetime)
                FROM candles
                WHERE symbol = ?
                """,
                (symbol,),
            ).fetchone()

        if row is None or row[0] is None:
            return None

        return pd.Timestamp(row[0])

    def count_candles(self, symbol):
        """Return number of stored candles for a symbol."""

        symbol = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
        )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM candles
                WHERE symbol = ?
                """,
                (symbol,),
            ).fetchone()

        return row[0]
