"""
Market Lab adapter for Scanner 4.

Uses Scanner 4's existing lib.py detection engine.
Does NOT modify the Streamlit application.
"""

import sys
from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------
# Make Scanner 4's own modules importable.
# ---------------------------------------------------------------------

SCANNER4_DIR = Path(__file__).resolve().parent

if str(SCANNER4_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER4_DIR))


from lib import (
    fetch_chunk_raw,
    parse_chunk,
    add_indicators,
    smooth_edges,
    detect_pattern,
    PATTERN_INFO,
    detect_chart_pattern,
    get_prev_day_close,
    detect_setups,
    compute_setup_score,
)


def run_market_lab_scan(
    symbols,
    as_of,
    period_days=5,
    smooth=True,
    chart_lookback=60,
):
    """
    Run Scanner 4 independently of its Streamlit UI.

    Parameters
    ----------
    symbols:
        NSE symbols such as ["ADANIPOWER", "TCS"].

    as_of:
        Historical timestamp such as:
        "2026-08-21 13:55"

    period_days:
        History used by Scanner 4.
        Default = 5, matching the Market Scanner UI.

    smooth:
        Smooth first/last three candles.
        Default = True, matching the Market Scanner UI.

    chart_lookback:
        Multi-bar pattern lookback.
        Default = 60, matching the Market Scanner UI.

    Returns
    -------
    dict
        Structured Scanner 4 results.
    """

    # ---------------------------------------------------------------
    # Normalise symbols.
    # ---------------------------------------------------------------

    clean_symbols = []

    for symbol in symbols:
        symbol = str(symbol).strip().upper()

        if not symbol:
            continue

        if not symbol.endswith(".NS"):
            symbol += ".NS"

        if symbol not in clean_symbols:
            clean_symbols.append(symbol)

    if not clean_symbols:
        return {
            "status": "error",
            "scanner": "scanner4",
            "message": "No symbols supplied.",
            "results": [],
        }

    # ---------------------------------------------------------------
    # Parse requested date/time.
    #
    # Scanner 4's UI works with separate date and HH:MM values.
    # We deliberately follow that model.
    # ---------------------------------------------------------------

    cutoff = pd.Timestamp(as_of)

    sel_date = cutoff.date()
    sel_time = cutoff.strftime("%H:%M")

    results = []

    # ---------------------------------------------------------------
    # Use Scanner 4's own batch downloader and parser.
    # ---------------------------------------------------------------

    try:
        raw_data = fetch_chunk_raw(
            tuple(clean_symbols),
            period_days,
        )

        batch_raw = parse_chunk(
            raw_data,
            clean_symbols,
        )

    except Exception as exc:
        return {
            "status": "error",
            "scanner": "scanner4",
            "message": f"{type(exc).__name__}: {exc}",
            "results": [],
        }

    # ---------------------------------------------------------------
    # Reproduce Scanner 4's process_ticker() exactly:
    #
    # smooth_edges
    # add_indicators
    # selected date
    # selected time
    # detect candlestick pattern
    # detect intraday setups
    # detect multi-bar chart pattern
    # compute Setup Score
    # ---------------------------------------------------------------

    for ticker, raw in batch_raw.items():

        try:

            if raw is None or raw.empty:
                continue

            df = smooth_edges(raw, n=3) if smooth else raw

            df = add_indicators(df)

            # Same date filtering used by Market Scanner.
            day_df = df[df.index.date == sel_date]

            if day_df.empty:
                continue

            # Find the latest available bar at or before
            # the requested time.
            times = [
                t.strftime("%H:%M")
                for t in day_df.index
            ]

            candidates = [
                i
                for i, tm in enumerate(times)
                if tm <= sel_time
            ]

            if not candidates:
                continue

            idx = candidates[-1]

            sel_ts = day_df.index[idx]

            row = day_df.iloc[idx]

            # -------------------------------------------------------
            # Candlestick pattern
            # -------------------------------------------------------

            pattern = detect_pattern(
                day_df.reset_index(drop=True),
                idx,
            )

            bias, _ = PATTERN_INFO.get(
                pattern,
                ("Neutral", ""),
            )

            # -------------------------------------------------------
            # Previous-day context + intraday setups
            # -------------------------------------------------------

            prev_close = get_prev_day_close(
                df,
                sel_date,
            )

            setups = detect_setups(
                day_df,
                idx,
                prev_close,
            )

            # -------------------------------------------------------
            # Multi-bar chart pattern
            # -------------------------------------------------------

            window = (
                day_df[
                    day_df.index <= sel_ts
                ]
                .tail(chart_lookback)
            )

            if len(window) >= 15:
                cp = detect_chart_pattern(
                    window.reset_index(drop=True)
                )
            else:
                cp = None

            # -------------------------------------------------------
            # Composite Setup Score
            # -------------------------------------------------------

            score = compute_setup_score(
                pattern,
                bias,
                cp,
                row,
                setups,
            )

            breakdown = {
                item[0]: item[1]
                for item in score["breakdown"]
            }

            # -------------------------------------------------------
            # Volume ratio
            # -------------------------------------------------------

            vol_ma = row.get(
                "VolMA20",
                float("nan"),
            )

            if (
                pd.notna(vol_ma)
                and vol_ma > 0
            ):
                vol_ratio = (
                    row["Volume"] / vol_ma
                )
            else:
                vol_ratio = None

            # -------------------------------------------------------
            # Structured Market Lab result
            # -------------------------------------------------------

            results.append(
                {
                    "Ticker": ticker.replace(".NS", ""),
                    "Close": round(
                        row["Close"],
                        2,
                    ),
                    "Anchor": score["anchor"],
                    "Total Score": score["total"],
                    "Score Label": (
                        score["label"]
                        if score["anchor"] != "Neutral"
                        else "No directional setup"
                    ),
                    "Candle Pattern": pattern,
                    "Candle Score": breakdown.get(
                        "Candle Strength",
                        0,
                    ),
                    "Chart Pattern": (
                        cp["name"]
                        if cp
                        else "None"
                    ),
                    "Chart Score": breakdown.get(
                        "Multi-bar Structure",
                        0,
                    ),
                    "Setup Count": len(setups),
                    "Setups": (
                        ", ".join(
                            s[0]
                            for s in setups
                        )
                        if setups
                        else ""
                    ),
                    "RSI": round(
                        row["RSI"],
                        0,
                    ),
                    "Vol x Avg": (
                        round(vol_ratio, 1)
                        if vol_ratio is not None
                        else None
                    ),
                    "Time": sel_time,
                    "Bar Time": (
                        sel_ts.strftime(
                            "%Y-%m-%d %H:%M"
                        )
                        if hasattr(
                            sel_ts,
                            "strftime",
                        )
                        else str(sel_ts)
                    ),
                    "Breakdown": breakdown,
                }
            )

        except Exception as exc:

            # One bad ticker must not kill the
            # entire Market Lab scan.
            results.append(
                {
                    "Ticker": ticker.replace(
                        ".NS",
                        "",
                    ),
                    "Error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    valid_results = [
        r
        for r in results
        if "Error" not in r
    ]

    return {
        "status": "ok",
        "scanner": "scanner4",
        "as_of": str(as_of),
        "period_days": period_days,
        "smooth": smooth,
        "chart_lookback": chart_lookback,
        "symbols_requested": len(clean_symbols),
        "symbols_downloaded": len(batch_raw),
        "results_count": len(valid_results),
        "results": results,
    }
