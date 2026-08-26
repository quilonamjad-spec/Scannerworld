"""
Market Lab adapter for Scanner 3 / Chart Reading Machine.

This adapter does NOT modify Scanner 3's reading logic.

It exposes:
    1. Existing Scanner 3 analysis result
    2. Existing Scanner 3 chart data

The chart contains ONLY:
    - Price
    - EMA 9
    - EMA 20
    - VWAP
    - Support zone
    - Support line
    - Resistance zone
    - Resistance line
"""

import sys
from pathlib import Path

import pandas as pd


SCANNER3_DIR = Path(__file__).resolve().parent

if str(SCANNER3_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER3_DIR))


from universe_scanner import analyze_ticker
from data_engine import get_data, add_indicators, level_detail


def _normalise_timestamp(df, selected_timestamp):
    """
    Make the selected timestamp compatible with the Yahoo dataframe
    timezone without changing the actual candle timestamps.
    """

    ts = pd.Timestamp(selected_timestamp)

    try:
        if getattr(df.index, "tz", None) is not None:
            if ts.tzinfo is None:
                ts = ts.tz_localize(df.index.tz)
            else:
                ts = ts.tz_convert(df.index.tz)

        elif ts.tzinfo is not None:
            ts = ts.tz_localize(None)

    except Exception:
        pass

    return ts


def _build_chart_data(ticker, interval, selected_timestamp):
    """
    Build the exact chart data used by Scanner 3.

    No new indicators are introduced here.
    The existing Scanner 3 data_engine functions are used.
    """

    df = get_data(ticker, interval)

    if df is None or df.empty:
        return None

    df = add_indicators(df)

    ts = _normalise_timestamp(df, selected_timestamp)

    context = df[df.index <= ts].copy()

    if context.empty:
        return None

    # Scanner 3 displays the selected session only.
    selected_date = ts.date()

    chart = context[context.index.date == selected_date].copy()

    if chart.empty:
        return None

    # Recalculate VWAP for the visible session exactly as Scanner 3 does.
    chart = add_indicators(chart)

    # S/R comes from the complete context up to the selected timestamp,
    # exactly as Scanner 3 calculates it.
    ld = level_detail(context)

    candles = []

    for timestamp, row in chart.iterrows():

        candles.append(
            {
                "Time": timestamp.isoformat(),
                "Open": float(row["Open"]),
                "High": float(row["High"]),
                "Low": float(row["Low"]),
                "Close": float(row["Close"]),
                "EMA9": float(row["EMA9"]),
                "EMA20": float(row["EMA20"]),
                "VWAP": float(row["VWAP"]),
            }
        )

    return {
        "ticker": ticker,
        "interval": interval,
        "date": str(selected_date),

        "candles": candles,

        # Existing Scanner 3 S/R zone values
        "support": float(ld["support"]),
        "support_low": float(ld["support_low"]),
        "support_high": float(ld["support_high"]),

        "resistance": float(ld["resistance"]),
        "resistance_low": float(ld["resistance_low"]),
        "resistance_high": float(ld["resistance_high"]),
    }


def run_market_lab_scan(
    symbols,
    as_of,
    interval="5m",
):
    """
    Run Scanner 3 for Market Lab.

    Returns both:
        - existing Scanner 3 analysis
        - chart data for Market Lab visualization
    """

    clean_symbols = []

    for symbol in symbols:

        symbol = str(symbol).strip().upper()

        if not symbol:
            continue

        if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
            symbol += ".NS"

        if symbol not in clean_symbols:
            clean_symbols.append(symbol)

    results = []

    for ticker in clean_symbols:

        try:

            # --------------------------------------------------------
            # EXISTING SCANNER 3 ANALYSIS
            # --------------------------------------------------------

            result = analyze_ticker(
                ticker=ticker,
                interval=interval,
                selected_timestamp=as_of,
            )

            if result is None:
                continue

            # --------------------------------------------------------
            # EXISTING SCANNER 3 CHART DATA
            # --------------------------------------------------------

            chart = _build_chart_data(
                ticker=ticker,
                interval=interval,
                selected_timestamp=as_of,
            )

            if chart is not None:
                result["Chart"] = chart

            results.append(result)

        except Exception as exc:

            results.append(
                {
                    "Ticker": ticker,
                    "Error": f"{type(exc).__name__}: {exc}",
                }
            )

    valid_results = [
        r
        for r in results
        if "Error" not in r
    ]

    return {
        "status": "ok",
        "scanner": "scanner3",
        "as_of": str(as_of),
        "interval": interval,
        "symbols_requested": len(clean_symbols),
        "results_count": len(valid_results),
        "results": results,
    }