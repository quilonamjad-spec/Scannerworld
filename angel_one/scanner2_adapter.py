import sys
from pathlib import Path

import pandas as pd
import time

from angel_one.data_provider import AngelOneProvider


# ------------------------------------------------------------
# Make Scanner 2 modules importable.
# We are importing its existing intelligence, NOT modifying it.
# ------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SCANNER2_DIR = REPO_ROOT / "scanner2"

if str(SCANNER2_DIR) not in sys.path:
    sys.path.insert(0, str(SCANNER2_DIR))


from indicators import compute_all_indicators
from scoring import (
    DEFAULT_WEIGHTS,
    score_symbol,
    score_trend,
    trend_summary,
)
from backtest import split_at_cutoff


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


def fetch_angel_history(
    provider,
    symbol,
    cutoff,
    interval="5m",
    lookback_days=7,
):
    """
    Fetch enough Angel One history to allow Scanner 2's
    indicators to calculate normally before the cutoff.
    """

    cutoff = pd.Timestamp(cutoff)

    from_datetime = cutoff - pd.Timedelta(days=lookback_days)

    return provider.get_candles(
        symbol=symbol,
        interval=interval,
        from_datetime=from_datetime,
        to_datetime=cutoff,
    )


def run_angel_scanner2(
    symbols,
    as_of,
    interval="5m",
    active_indicators=None,
    weights=None,
):
    """
    Experimental Scanner 2 runner using Angel One data.

    Scanner 2's indicator/scoring logic is reused unchanged.
    Only the market-data source is replaced.
    """

    if not symbols:
        return {
            "status": "error",
            "scanner": "scanner2",
            "data_source": "angel_one",
            "message": "No symbols supplied.",
            "results": [],
        }

    clean_symbols = [
        str(symbol).strip().upper().removesuffix(".NS")
        for symbol in symbols
        if str(symbol).strip()
    ]

    cutoff = pd.Timestamp(as_of)

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

    provider = AngelOneProvider()

    print("\nANGEL ONE → SCANNER 2")
    print("=====================")

    print("Logging into Angel One...")
    provider.login()
    print("Authentication : OK")

    results = []

    for i, symbol in enumerate(clean_symbols):

        if i > 0:
            time.sleep(2)

        print(f"\nFetching {symbol}...")

        try:
            df = fetch_angel_history(
                provider,
                symbol,
                cutoff,
                interval=interval,
            )

            if df.empty:
                print("  No data")
                continue

            print(f"  Candles received : {len(df)}")

            # Scanner 2's normal cutoff logic.
            cutoff_date = cutoff.date()
            cutoff_time = cutoff.time()

            df_before, _df_after = split_at_cutoff(
                df.set_index("Datetime"),
                cutoff_date,
                cutoff_time,
            )

            if df_before.empty:
                print("  No candles before cutoff")
                continue

            print(
                f"  Candles before cutoff : "
                f"{len(df_before)}"
            )

            # ------------------------------------------------
            # EXISTING SCANNER 2 LOGIC
            # ------------------------------------------------

            df_ind = compute_all_indicators(
                df_before
            )

            result = score_symbol(
                df_ind,
                active,
                scoring_weights,
            )

            if result is None:
                continue

            if result.get("signal_label") == "No Data":
                continue

            trend = score_trend(
                df_ind,
                active,
                scoring_weights,
                lookback=5,
            )

            trend_sequence, trend_conviction = (
                trend_summary(trend)
            )

            results.append(
                {
                    "Symbol": symbol,
                    "Entry Price": result.get("close"),
                    "Trade Score": result.get(
                        "trade_score"
                    ),
                    "Confidence": result.get(
                        "confidence"
                    ),
                    "Signal": result.get(
                        "signal_label"
                    ),
                    "Trend (last 5)": trend_sequence,
                    "Trend Conviction": trend_conviction,
                    "RSI": result.get("rsi"),
                    "ADX": result.get("adx"),
                    "Extension (ATR)": result.get(
                        "extension_atr"
                    ),
                    "VWAP %": result.get(
                        "vwap_pct"
                    ),
                    "Patterns": ", ".join(
                        result.get("patterns", [])
                    ) or "-",
                    "Bar Time": (
                        df_before.index[-1].strftime(
                            "%Y-%m-%d %H:%M"
                        )
                    ),
                    "Data Source": "Angel One",
                }
            )

        except Exception as exc:

            print(
                f"  ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

            results.append(
                {
                    "Symbol": symbol,
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    return {
        "status": "ok",
        "scanner": "scanner2",
        "data_source": "angel_one",
        "as_of": cutoff.isoformat(),
        "interval": interval,
        "symbols_requested": len(clean_symbols),
        "results_count": len(
            [
                r
                for r in results
                if "error" not in r
            ]
        ),
        "results": results,
    }
