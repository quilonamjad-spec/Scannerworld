"""
Market Lab adapter for Scanner 3 / Chart Reading Machine.

This adapter does NOT modify the existing Scanner 3 app.
It directly uses the scanner's existing universe analysis engine.
"""

import sys
from pathlib import Path


SCANNER3_DIR = Path(__file__).resolve().parent

if str(SCANNER3_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER3_DIR))


from universe_scanner import analyze_ticker


def run_market_lab_scan(
    symbols,
    as_of,
    interval="5m",
):
    """
    Run Scanner 3 independently of its Streamlit UI.

    Parameters
    ----------
    symbols:
        NSE symbols such as ["ADANIPOWER", "TCS"].

    as_of:
        Historical timestamp, e.g.
        "2026-08-21 13:55".

    interval:
        Scanner timeframe. Default = 5m.

    Returns
    -------
    dict
        Structured Scanner 3 results.
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

            result = analyze_ticker(
                ticker=ticker,
                interval=interval,
                selected_timestamp=as_of,
            )

            if result is None:
                continue

            results.append(result)

        except Exception as exc:

            results.append(
                {
                    "Ticker": ticker,
                    "Error": f"{type(exc).__name__}: {exc}",
                }
            )

    valid_results = [
        r for r in results
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
