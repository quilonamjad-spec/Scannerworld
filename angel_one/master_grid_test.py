import sys
import time
from pathlib import Path

import pandas as pd


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

SCANNER1_DIR = ROOT / "scanner1"
SCANNER2_DIR = ROOT / "scanner2"
SCANNER3_DIR = ROOT / "scanner3"
SCANNER4_DIR = ROOT / "scanner4"

for directory in [
    SCANNER1_DIR,
    SCANNER2_DIR,
    SCANNER3_DIR,
    SCANNER4_DIR,
]:
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


# ============================================================
# EXISTING SCANNER ENGINES
# ============================================================

from indicators import build_result as scanner1_build_result

from indicators import compute_all_indicators as scanner2_indicators
from scoring import (
    DEFAULT_WEIGHTS,
    score_symbol,
    score_trend,
    trend_summary,
)

from universe_scanner import analyze_ticker as scanner3_analyze

from lib import (
    smooth_edges,
    add_indicators as scanner4_indicators,
    detect_pattern,
    PATTERN_INFO,
    detect_chart_pattern,
    get_prev_day_close,
    detect_setups,
    compute_setup_score,
)


from angel_one.data_provider import AngelOneProvider


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

SYMBOLS = [
    "TCS",
    "INFY",
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
]

INTERVAL = "5m"

# We deliberately use a completed historical timestamp
# so the experiment can be run on a non-market day.
AS_OF = pd.Timestamp(
    "2026-08-28 10:00",
    tz="Asia/Kolkata",
)

LOOKBACK_DAYS = 7


# ============================================================
# HELPERS
# ============================================================

def clean_dataframe(df):

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    df["Datetime"] = pd.to_datetime(
        df["Datetime"]
    )

    if df["Datetime"].dt.tz is None:
        df["Datetime"] = (
            df["Datetime"]
            .dt.tz_localize("Asia/Kolkata")
        )
    else:
        df["Datetime"] = (
            df["Datetime"]
            .dt.tz_convert("Asia/Kolkata")
        )

    df = df.sort_values("Datetime")

    df = df.drop_duplicates(
        subset=["Datetime"]
    )

    return df


def context_before(df):

    work = df.copy()

    if "Datetime" in work.columns:
        work = work.set_index("Datetime")

    if work.index.tz is None:
        work.index = work.index.tz_localize(
            "Asia/Kolkata"
        )
    else:
        work.index = work.index.tz_convert(
            "Asia/Kolkata"
        )

    return work[
        work.index <= AS_OF
    ].copy()


# ============================================================
# SCANNER 1
# ============================================================

def run_scanner1(df, symbol):

    context = context_before(df)

    if context.empty:
        return None

    return scanner1_build_result(
        symbol,
        context,
        AS_OF,
    )


# ============================================================
# SCANNER 2
# ============================================================

def run_scanner2(df, symbol):

    context = context_before(df)

    if context.empty:
        return None

    df_ind = scanner2_indicators(
        context
    )

    active = {
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

    result = score_symbol(
        df_ind,
        active,
        DEFAULT_WEIGHTS,
    )

    if result is None:
        return None

    trend = score_trend(
        df_ind,
        active,
        DEFAULT_WEIGHTS,
        lookback=5,
    )

    sequence, conviction = trend_summary(
        trend
    )

    return {
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
        "Trend (last 5)": sequence,
        "Trend Conviction": conviction,
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
        "Bar Time": context.index[-1].strftime(
            "%Y-%m-%d %H:%M"
        ),
        "Data Source": "Angel One",
    }


# ============================================================
# SCANNER 3
# ============================================================

def run_scanner3(df, symbol):

    context = context_before(df)

    if len(context) < 25:
        return None

    # Scanner 3 expects its normal OHLCV
    # dataframe and calculates its own indicators.
    result = scanner3_analyze(
        ticker=symbol + ".NS",
        interval=INTERVAL,
        selected_timestamp=AS_OF,
        df=context,
    )

    if result is None:
        return None

    return result


# ============================================================
# SCANNER 4
# ============================================================

def run_scanner4(df, symbol):

    context = context_before(df)

    if context.empty:
        return None

    # Reproduce Scanner 4's existing processing.
    work = smooth_edges(
        context,
        n=3,
    )

    work = scanner4_indicators(
        work
    )

    selected_date = AS_OF.date()

    day_df = work[
        work.index.date == selected_date
    ]

    if day_df.empty:
        return None

    candidates = [
        i
        for i, timestamp in enumerate(
            day_df.index
        )
        if timestamp <= AS_OF
    ]

    if not candidates:
        return None

    idx = candidates[-1]

    sel_ts = day_df.index[idx]

    row = day_df.iloc[idx]

    # --------------------------------------------------------
    # Candlestick pattern
    # --------------------------------------------------------

    pattern = detect_pattern(
        day_df.reset_index(drop=True),
        idx,
    )

    bias, _ = PATTERN_INFO.get(
        pattern,
        ("Neutral", ""),
    )

    # --------------------------------------------------------
    # Previous-day context
    # --------------------------------------------------------

    prev_close = get_prev_day_close(
        work,
        selected_date,
    )

    setups = detect_setups(
        day_df,
        idx,
        prev_close,
    )

    # --------------------------------------------------------
    # Multi-bar chart pattern
    # --------------------------------------------------------

    window = (
        day_df[
            day_df.index <= sel_ts
        ]
        .tail(60)
    )

    if len(window) >= 15:
        chart_pattern = detect_chart_pattern(
            window.reset_index(drop=True)
        )
    else:
        chart_pattern = None

    # --------------------------------------------------------
    # Existing Scanner 4 score
    # --------------------------------------------------------

    score = compute_setup_score(
        pattern,
        bias,
        chart_pattern,
        row,
        setups,
    )

    breakdown = {
        item[0]: item[1]
        for item in score["breakdown"]
    }

    vol_ma = row.get(
        "VolMA20",
        float("nan"),
    )

    if pd.notna(vol_ma) and vol_ma > 0:
        vol_ratio = (
            row["Volume"] / vol_ma
        )
    else:
        vol_ratio = None

    return {
        "Ticker": symbol,

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
            chart_pattern["name"]
            if chart_pattern
            else "None"
        ),

        "Chart Score": breakdown.get(
            "Multi-bar Structure",
            0,
        ),

        "Setup Count": len(setups),

        "Setups": (
            ", ".join(
                setup[0]
                for setup in setups
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

        "Time": AS_OF.strftime(
            "%H:%M"
        ),

        "Bar Time": sel_ts.strftime(
            "%Y-%m-%d %H:%M"
        ),

        "Breakdown": breakdown,
    }


# ============================================================
# DIRECTION NORMALIZATION
# ============================================================

def direction(scanner, result):

    if not result:
        return "No Signal"

    if scanner == 1:

        value = str(
            result.get("Phase", "")
        ).lower()

        if value == "bull":
            return "Bullish"

        if value == "bear":
            return "Bearish"

    elif scanner == 2:

        value = str(
            result.get("Signal", "")
        ).lower()

        if value == "buy":
            return "Bullish"

        if value == "sell":
            return "Bearish"

    elif scanner == 3:

        value = str(
            result.get("Direction", "")
        ).lower()

        if "bull" in value:
            return "Bullish"

        if "bear" in value:
            return "Bearish"

    elif scanner == 4:

        value = str(
            result.get("Anchor", "")
        ).lower()

        if "bull" in value:
            return "Bullish"

        if "bear" in value:
            return "Bearish"

    return "No Signal"


# ============================================================
# MASTER GRID DISPLAY
# ============================================================

def print_grid(results):

    print()
    print("=" * 100)
    print("ANGEL ONE → MASTER GRID DRY RUN")
    print("=" * 100)
    print()

    print(
        f"As-of : {AS_OF.strftime('%Y-%m-%d %H:%M')}"
    )

    print(
        f"Source: Angel One historical 5-minute data"
    )

    print()

    header = (
        f"{'Symbol':12}"
        f"{'Scanner 1':15}"
        f"{'Scanner 2':15}"
        f"{'Scanner 3':15}"
        f"{'Scanner 4':15}"
    )

    print(header)
    print("-" * len(header))

    for symbol in SYMBOLS:

        r1 = results[symbol]["scanner1"]
        r2 = results[symbol]["scanner2"]
        r3 = results[symbol]["scanner3"]
        r4 = results[symbol]["scanner4"]

        print(
            f"{symbol:12}"
            f"{direction(1, r1):15}"
            f"{direction(2, r2):15}"
            f"{direction(3, r3):15}"
            f"{direction(4, r4):15}"
        )

    print()

    # --------------------------------------------------------
    # Detailed results
    # --------------------------------------------------------

    for symbol in SYMBOLS:

        print()
        print("=" * 100)
        print(symbol)
        print("=" * 100)

        stock = results[symbol]

        for number in range(1, 5):

            result = stock[
                f"scanner{number}"
            ]

            print()
            print(
                f"SCANNER {number}"
            )
            print("-" * 30)

            if result is None:
                print("No directional result.")
                continue

            if "error" in result:
                print(
                    "ERROR:",
                    result["error"],
                )
                continue

            for key, value in result.items():

                print(
                    f"{key:22}: {value}"
                )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 100)
    print("ANGEL ONE → MASTER GRID FIVE-STOCK EXPERIMENT")
    print("=" * 100)
    print()

    print("Stocks :", ", ".join(SYMBOLS))
    print("Interval:", INTERVAL)
    print("As-of  :", AS_OF)
    print()

    provider = AngelOneProvider()

    print("Logging into Angel One...")

    provider.login()

    print("Authentication : OK")
    print()

    all_results = {}

    for number, symbol in enumerate(
        SYMBOLS,
        start=1,
    ):

        print("-" * 100)
        print(
            f"{number}/{len(SYMBOLS)} "
            f"Fetching {symbol}..."
        )

        try:

            df = provider.get_candles(
                symbol=symbol,
                interval=INTERVAL,
                from_datetime=(
                    AS_OF
                    - pd.Timedelta(
                        days=LOOKBACK_DAYS
                    )
                ),
                to_datetime=AS_OF,
            )

            df = clean_dataframe(df)

            print(
                "Candles received:",
                len(df),
            )

            if df.empty:

                all_results[symbol] = {
                    "scanner1": None,
                    "scanner2": None,
                    "scanner3": None,
                    "scanner4": None,
                }

                continue

            results = {}

            # ------------------------------------------------
            # Scanner 1
            # ------------------------------------------------

            try:
                results["scanner1"] = (
                    run_scanner1(
                        df,
                        symbol,
                    )
                )
            except Exception as exc:
                results["scanner1"] = {
                    "error":
                    f"{type(exc).__name__}: {exc}"
                }

            # ------------------------------------------------
            # Scanner 2
            # ------------------------------------------------

            try:
                results["scanner2"] = (
                    run_scanner2(
                        df,
                        symbol,
                    )
                )
            except Exception as exc:
                results["scanner2"] = {
                    "error":
                    f"{type(exc).__name__}: {exc}"
                }

            # ------------------------------------------------
            # Scanner 3
            # ------------------------------------------------

            try:
                results["scanner3"] = (
                    run_scanner3(
                        df,
                        symbol,
                    )
                )
            except Exception as exc:
                results["scanner3"] = {
                    "error":
                    f"{type(exc).__name__}: {exc}"
                }

            # ------------------------------------------------
            # Scanner 4
            # ------------------------------------------------

            try:
                results["scanner4"] = (
                    run_scanner4(
                        df,
                        symbol,
                    )
                )
            except Exception as exc:
                results["scanner4"] = {
                    "error":
                    f"{type(exc).__name__}: {exc}"
                }

            all_results[symbol] = results

        except Exception as exc:

            print(
                "FETCH ERROR:",
                type(exc).__name__,
                exc,
            )

            all_results[symbol] = {
                "scanner1": None,
                "scanner2": None,
                "scanner3": None,
                "scanner4": None,
            }

        # Keep the Angel One request rate conservative.
        if number < len(SYMBOLS):
            time.sleep(2)

    print_grid(
        all_results
    )


if __name__ == "__main__":
    main()
