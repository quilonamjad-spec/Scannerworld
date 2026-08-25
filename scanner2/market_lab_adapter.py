"""
Market Lab adapter for Scanner 2.

This file does NOT modify or import app_v1.py.
It directly calls Scanner 2's existing data, indicator and scoring modules.
"""

import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------
# Make Scanner 2's own modules importable when this adapter is called
# from the repository root.
# ---------------------------------------------------------------------

SCANNER2_DIR = Path(__file__).resolve().parent

if str(SCANNER2_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER2_DIR))


from data_fetch import fetch_batch
from indicators import compute_all_indicators
from scoring import (
    DEFAULT_WEIGHTS,
    score_symbol,
    score_trend,
    trend_summary,
)
from backtest import split_at_cutoff


# Scanner 2's active indicators match app_v1.py:
# everything ON except VWAP.
DEFAULT_ACTIVE_INDICATORS = {
    "RSI": True,
    "MACD": True,
    "ADX": True,
    "BOLLINGER": True,
    "VOLUME": True,
    "EMA_TREND": True,
    "EXTENSION": True,
    "VWAP": False,
    "CANDLESTICK": True,
}


def run_market_lab_scan(
    symbols,
    as_of,
    interval="5m",
    period="5d",
    batch_size=50,
    active_indicators=None,
    weights=None,
):
    """
    Run Scanner 2 independently of Streamlit.

    Parameters
    ----------
    symbols:
        NSE symbols without .NS, e.g. ["ADANIPOWER", "TCS"]

    as_of:
        Timestamp such as "2026-08-21 13:55"

    interval:
        Scanner timeframe. Default = 5m.

    period:
        Yahoo history period. Default = 5d for 5m,
        matching Scanner 2's app configuration.

    Returns
    -------
    dict
        Structured Market Lab result.
    """

    if not symbols:
        return {
            "status": "error",
            "scanner": "scanner2",
            "message": "No symbols supplied.",
            "results": [],
        }

    # Normalise symbols.
    clean_symbols = [
        str(s).strip().upper().removesuffix(".NS")
        for s in symbols
        if str(s).strip()
    ]

    # Convert the requested timestamp.
    cutoff = pd.Timestamp(as_of)

    # Scanner 2's historical cutoff logic expects date + time.
    cutoff_date = cutoff.date()
    cutoff_time = cutoff.time()

    active = (
        dict(DEFAULT_ACTIVE_INDICATORS)
        if active_indicators is None
        else dict(active_indicators)
    )

    scoring_weights = (
        dict(DEFAULT_WEIGHTS)
        if weights is None
        else dict(weights)
    )

    # ---------------------------------------------------------------
    # Fetch data using Scanner 2's own data_fetch.py
    # ---------------------------------------------------------------

    data_map = fetch_batch(
        clean_symbols,
        interval=interval,
        period=period,
        batch_size=batch_size,
    )

    results = []

    # ---------------------------------------------------------------
    # Reproduce Scanner 2's historical scoring path
    #
    # app_v1.py:
    #   split_at_cutoff()
    #   compute_all_indicators()
    #   score_symbol()
    #   score_trend()
    #   trend_summary()
    # ---------------------------------------------------------------

    for symbol in clean_symbols:

        df = data_map.get(symbol)

        if df is None or df.empty:
            continue

        try:
            # Remove candles after the requested timestamp.
            df_before, _df_after = split_at_cutoff(
                df,
                cutoff_date,
                cutoff_time,
            )

            if df_before.empty:
                continue

            # IMPORTANT:
            # Indicators are calculated AFTER the cutoff split.
            # This prevents future candles leaking into the result.
            df_ind = compute_all_indicators(df_before)

            # Current Scanner 2 score.
            result = score_symbol(
                df_ind,
                active,
                scoring_weights,
            )

            if result is None:
                continue

            if result.get("signal_label") == "No Data":
                continue

            # Scanner 2's last-five-candle trend.
            trend = score_trend(
                df_ind,
                active,
                scoring_weights,
                lookback=5,
            )

            trend_sequence, trend_conviction = trend_summary(trend)

            results.append(
                {
                    "Symbol": symbol,
                    "Entry Price": result.get("close"),
                    "Trade Score": result.get("trade_score"),
                    "Confidence": result.get("confidence"),
                    "Signal": result.get("signal_label"),
                    "Trend (last 5)": trend_sequence,
                    "Trend Conviction": trend_conviction,
                    "RSI": result.get("rsi"),
                    "ADX": result.get("adx"),
                    "Extension (ATR)": result.get("extension_atr"),
                    "VWAP %": result.get("vwap_pct"),
                    "Patterns": ", ".join(
                        result.get("patterns", [])
                    ) or "-",
                    "Breakdown": result.get("breakdown", {}),
                    "Bar Time": (
                        df_before.index[-1].strftime("%Y-%m-%d %H:%M")
                        if hasattr(df_before.index[-1], "strftime")
                        else str(df_before.index[-1])
                    ),
                }
            )

        except Exception as exc:
            results.append(
                {
                    "Symbol": symbol,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "status": "ok",
        "scanner": "scanner2",
        "as_of": cutoff.isoformat(),
        "interval": interval,
        "symbols_requested": len(clean_symbols),
        "symbols_downloaded": len(data_map),
        "results_count": len(
            [r for r in results if "error" not in r]
        ),
        "results": results,
    }
