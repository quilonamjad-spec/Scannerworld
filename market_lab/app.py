import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, date, time

import pandas as pd
import streamlit as st


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Market Lab",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 MARKET LAB")
st.caption("Four Scanner Intelligence Layer — Machine Reading")


# ============================================================
# TEST CONFIGURATION
# ============================================================
# ------------------------------------------------------------
# TEST CONFIGURATION
# ------------------------------------------------------------

st.subheader("Test Configuration")

col1, col2 = st.columns(2)

with col1:
    ticker_text = st.text_input(
        "Stocks",
        value="ADANIPOWER, TCS",
        help="Enter stock symbols separated by commas.",
    )

with col2:
    as_of_date = st.date_input(
        "As-of Date",
        value=date(2026, 8, 21),
    )

as_of_time = st.time_input(
    "As-of Time",
    value=time(13, 55),
)

# Convert ticker text into a clean symbol list
SYMBOLS = [
    symbol.strip().upper()
    for symbol in ticker_text.split(",")
    if symbol.strip()
]

# Combine date + time into the datetime expected by the scanners
AS_OF = datetime.combine(
    as_of_date,
    as_of_time,
)

st.caption(
    f"Universe: {', '.join(SYMBOLS)}  |  "
    f"As-of: {AS_OF.strftime('%Y-%m-%d %H:%M')}"
)


# ============================================================
# RUN ONE SCANNER IN ITS OWN PROCESS
# ============================================================

def run_isolated_test(script_name, symbols, as_of):
    """
    Run one scanner in its own Python process while passing the
    Market Lab UI configuration explicitly to the child process.

    The scanner test scripts remain generic runners; they do not
    contain a hardcoded stock universe or replay timestamp.
    """

    script_path = ROOT_DIR / script_name

    command = [
        sys.executable,
        str(script_path),
        "--symbols",
        ",".join(symbols),
        "--as-of",
        as_of.strftime("%Y-%m-%d %H:%M"),
    ]

    result = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
    )

    output = result.stdout

    if result.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed:\n\n"
            f"{result.stderr}"
        )

    # --------------------------------------------------------
    # Find JSON object in diagnostic output
    # --------------------------------------------------------

    start = output.find("{")

    if start == -1:
        raise RuntimeError(
            f"{script_name} did not return JSON.\n\n"
            f"Output:\n{output}"
        )

    json_text = output[start:]

    try:
        return json.loads(json_text)

    except json.JSONDecodeError as e:

        raise RuntimeError(
            f"Could not parse JSON from {script_name}.\n\n"
            f"Output:\n{output}"
        ) from e


# ============================================================
# NORMALIZE DIRECTION
# ============================================================

def normalize_direction(scanner_number, result):
    """
    Convert each scanner's native terminology into a common
    Market Lab direction.

    This does NOT change the scanner's actual result.
    It only gives Market Lab a common vocabulary.
    """

    if not result:
        return "No Signal"

    if scanner_number == 1:

        value = str(
            result.get("Phase", "")
        ).lower()

        if value == "bull":
            return "Bullish"

        if value == "bear":
            return "Bearish"

        return "No Signal"

    if scanner_number == 2:

        value = str(
            result.get("Signal", "")
        ).lower()

        if value == "buy":
            return "Bullish"

        if value == "sell":
            return "Bearish"

        return "No Signal"

    if scanner_number == 3:

        value = str(
            result.get("Direction", "")
        ).lower()

        if "bull" in value:
            return "Bullish"

        if "bear" in value:
            return "Bearish"

        return "No Signal"

    if scanner_number == 4:

        value = str(
            result.get("Anchor", "")
        ).lower()

        if "bull" in value:
            return "Bullish"

        if "bear" in value:
            return "Bearish"

        return "No Signal"

    return "No Signal"


# ============================================================
# MACHINE READING
# ============================================================

def build_machine_reading(
    symbol,
    r1,
    r2,
    r3,
    r4,
):
    """
    Build a deterministic human-readable explanation from
    the four existing scanner outputs.

    This is an interpretation layer only.

    No new score.
    No weighting.
    No BUY/SELL decision.
    """

    results = [
        ("Scanner 1", r1, normalize_direction(1, r1)),
        ("Scanner 2", r2, normalize_direction(2, r2)),
        ("Scanner 3", r3, normalize_direction(3, r3)),
        ("Scanner 4", r4, normalize_direction(4, r4)),
    ]

    bullish = [
        name
        for name, result, direction in results
        if direction == "Bullish"
    ]

    bearish = [
        name
        for name, result, direction in results
        if direction == "Bearish"
    ]

    no_signal = [
        name
        for name, result, direction in results
        if direction == "No Signal"
    ]

    # ========================================================
    # EVIDENCE COLLECTION
    # ========================================================

    bullish_evidence = []
    bearish_evidence = []

    # --------------------------------------------------------
    # Scanner 1
    # --------------------------------------------------------

    if r1:

        direction = normalize_direction(
            1,
            r1,
        )

        if direction == "Bullish":

            bullish_evidence.append(
                "a Bull phase"
            )

        elif direction == "Bearish":

            bearish_evidence.append(
                "a Bear phase"
            )

    # --------------------------------------------------------
    # Scanner 2
    # --------------------------------------------------------

    if r2:

        direction = normalize_direction(
            2,
            r2,
        )

        breakdown = r2.get(
            "Breakdown",
            {},
        )

        macd = breakdown.get(
            "MACD",
            0,
        )

        ema = breakdown.get(
            "EMA_TREND",
            0,
        )

        adx = breakdown.get(
            "ADX",
            0,
        )

        if direction == "Bullish":

            reasons = []

            if macd > 0:
                reasons.append("positive MACD")

            if ema > 0:
                reasons.append("positive EMA trend")

            if adx > 0:
                reasons.append("trend strength")

            if reasons:

                bullish_evidence.append(
                    "momentum/trend factors "
                    f"({', '.join(reasons)})"
                )

            else:

                bullish_evidence.append(
                    "bullish momentum/trend factors"
                )

        elif direction == "Bearish":

            reasons = []

            if macd < 0:
                reasons.append("bearish MACD")

            if ema < 0:
                reasons.append("bearish EMA trend")

            if adx < 0:
                reasons.append("weak/bearish trend factor")

            if reasons:

                bearish_evidence.append(
                    "momentum/trend factors "
                    f"({', '.join(reasons)})"
                )

            else:

                bearish_evidence.append(
                    "bearish momentum/trend factors"
                )

    # --------------------------------------------------------
    # Scanner 3
    # --------------------------------------------------------

    if r3:

        direction = normalize_direction(
            3,
            r3,
        )

        signals = r3.get(
            "Signals",
            {},
        )

        if direction == "Bullish":

            reasons = []

            if signals.get("Structure") == "Bullish":
                reasons.append("market structure")

            if signals.get("VWAP") == "Bullish":
                reasons.append("VWAP")

            if signals.get("Candle") == "Bullish":
                reasons.append("candle")

            if signals.get("Pattern") == "Bullish":

                pattern = r3.get(
                    "Pattern",
                    "",
                )

                if pattern:
                    reasons.append(
                        f"an emerging {pattern}"
                    )
                else:
                    reasons.append(
                        "bullish pattern evidence"
                    )

            if reasons:

                bullish_evidence.append(
                    ", ".join(reasons)
                )

        elif direction == "Bearish":

            reasons = []

            if signals.get("Structure") == "Bearish":
                reasons.append("market structure")

            if signals.get("VWAP") == "Bearish":
                reasons.append("VWAP")

            if signals.get("Candle") == "Bearish":
                reasons.append("candle")

            if signals.get("Pattern") == "Bearish":

                pattern = r3.get(
                    "Pattern",
                    "",
                )

                if pattern:
                    reasons.append(
                        f"{pattern} pattern"
                    )
                else:
                    reasons.append(
                        "bearish pattern evidence"
                    )

            if reasons:

                bearish_evidence.append(
                    ", ".join(reasons)
                )

    # --------------------------------------------------------
    # Scanner 4
    # --------------------------------------------------------

    if r4:

        direction = normalize_direction(
            4,
            r4,
        )

        chart_pattern = r4.get(
            "Chart Pattern",
            "",
        )

        anchor = r4.get(
            "Anchor",
            "",
        )

        if direction == "Bullish":

            reasons = []

            if anchor:
                reasons.append(
                    f"a {anchor.lower()} anchor"
                )

            if chart_pattern:
                reasons.append(
                    chart_pattern
                )

            if reasons:

                bullish_evidence.append(
                    " and ".join(reasons)
                )

        elif direction == "Bearish":

            reasons = []

            if anchor:
                reasons.append(
                    f"a {anchor.lower()} anchor"
                )

            if chart_pattern:
                reasons.append(
                    chart_pattern
                )

            if reasons:

                bearish_evidence.append(
                    " and ".join(reasons)
                )

    # ========================================================
    # BUILD READING
    # ========================================================

    # --------------------------------------------------------
    # CONFLICT
    # --------------------------------------------------------

    if bullish and bearish:

        opening = (
            "The scanners are showing conflicting evidence."
        )

        bullish_text = ""

        if bullish_evidence:

            bullish_text = (
                f" {', '.join(bullish)} "
                "is bullish based on "
                f"{'; '.join(bullish_evidence)}."
            )

        bearish_text = ""

        if bearish_evidence:

            bearish_text = (
                f" {', '.join(bearish)} "
                "is bearish, supported by "
                f"{'; '.join(bearish_evidence)}."
            )

        no_signal_text = ""

        if no_signal:

            no_signal_text = (
                " "
                + ", ".join(no_signal)
                + " does not produce a directional "
                  "signal because its conditions are "
                  "not fully satisfied."
            )

        reading = (
            opening
            + bullish_text
            + bearish_text
            + no_signal_text
        )

        reading += (
            " The conflict is therefore primarily "
            "between bullish chart/structure evidence "
            "and bearish momentum/pattern evidence."
        )

        return reading

    # --------------------------------------------------------
    # BULLISH CONVERGENCE
    # --------------------------------------------------------

    if bullish and not bearish:

        reading = (
            "The scanners are broadly aligned bullish."
        )

        if bullish_evidence:

            reading += (
                " The agreement is supported by "
                + "; ".join(bullish_evidence)
                + "."
            )

        if no_signal:

            reading += (
                " "
                + ", ".join(no_signal)
                + " does not produce a directional "
                  "signal, so its absence is not treated "
                  "as bearish evidence."
            )

        # Context from Scanner 3
        if r3:

            event = r3.get(
                "Event",
                "",
            )

            sr_location = r3.get(
                "S/R Location",
                "",
            )

            context = []

            if event:
                context.append(
                    event.lower()
                )

            if sr_location:
                context.append(
                    sr_location.lower()
                )

            if context:

                reading += (
                    " Important context: "
                    + " and ".join(context)
                    + "."
                )

        return reading

    # --------------------------------------------------------
    # BEARISH CONVERGENCE
    # --------------------------------------------------------

    if bearish and not bullish:

        reading = (
            "The scanners are broadly aligned bearish."
        )

        if bearish_evidence:

            reading += (
                " The agreement is supported by "
                + "; ".join(bearish_evidence)
                + "."
            )

        if no_signal:

            reading += (
                " "
                + ", ".join(no_signal)
                + " does not produce a directional "
                  "signal, so its absence is not treated "
                  "as bullish evidence."
            )

        if r3:

            event = r3.get(
                "Event",
                "",
            )

            sr_location = r3.get(
                "S/R Location",
                "",
            )

            context = []

            if event:
                context.append(
                    event.lower()
                )

            if sr_location:
                context.append(
                    sr_location.lower()
                )

            if context:

                reading += (
                    " Important context: "
                    + " and ".join(context)
                    + "."
                )

        return reading

    # --------------------------------------------------------
    # NO DIRECTION
    # --------------------------------------------------------

    return (
        "The scanners do not provide sufficient "
        "directional evidence at this point. "
        "The available conditions are either neutral "
        "or have not satisfied the scanners' "
        "directional requirements."
    )


# ============================================================
# UNDERLYING DATA TABLE
# ============================================================

def build_underlying_table(
    r1,
    r2,
    r3,
    r4,
):
    """
    Build a common row/column comparison table.

    Scanner-specific raw details remain available below it.
    """

    scanners = {
        "Scanner 1": r1,
        "Scanner 2": r2,
        "Scanner 3": r3,
        "Scanner 4": r4,
    }

    rows = {}

    # --------------------------------------------------------
    # Direction
    # --------------------------------------------------------

    rows["Direction"] = {
        name: normalize_direction(
            i + 1,
            result,
        )
        for i, (name, result) in enumerate(
            scanners.items()
        )
    }

    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    rows["Score"] = {
        "Scanner 1": (
            r1.get("Score", "—")
            if r1
            else "—"
        ),
        "Scanner 2": (
            r2.get("Trade Score", "—")
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Score", "—")
            if r3
            else "—"
        ),
        "Scanner 4": (
            r4.get("Total Score", "—")
            if r4
            else "—"
        ),
    }

    # --------------------------------------------------------
    # Confidence / Consensus
    # --------------------------------------------------------

    rows["Confidence / Consensus"] = {
        "Scanner 1": "—",
        "Scanner 2": (
            r2.get("Confidence", "—")
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Consensus", "—")
            if r3
            else "—"
        ),
        "Scanner 4": "—",
    }

    # --------------------------------------------------------
    # Trend / Structure
    # --------------------------------------------------------

    rows["Trend / Structure"] = {
        "Scanner 1": (
            r1.get("Phase", "—")
            if r1
            else "No Signal"
        ),
        "Scanner 2": (
            r2.get("Trend (last 5)", "—")
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Structure", "—")
            if r3
            else "—"
        ),
        "Scanner 4": (
            r4.get("Anchor", "—")
            if r4
            else "—"
        ),
    }

    # --------------------------------------------------------
    # Momentum
    # --------------------------------------------------------

    rows["Momentum"] = {
        "Scanner 1": (
            f"RSI {r1.get('RSI14', '—')}"
            if r1
            else "—"
        ),
        "Scanner 2": (
            f"RSI {r2.get('RSI', '—')} | "
            f"ADX {r2.get('ADX', '—')}"
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Candle", "—")
            if r3
            else "—"
        ),
        "Scanner 4": (
            f"RSI {r4.get('RSI', '—')}"
            if r4
            else "—"
        ),
    }

    # --------------------------------------------------------
    # Pattern
    # --------------------------------------------------------

    rows["Pattern"] = {
        "Scanner 1": "—",
        "Scanner 2": (
            r2.get("Patterns", "—")
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Pattern", "—")
            if r3
            else "—"
        ),
        "Scanner 4": (
            r4.get("Chart Pattern", "—")
            if r4
            else "—"
        ),
    }

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    rows["Volume"] = {
        "Scanner 1": (
            r1.get("Volume_strength", "—")
            if r1
            else "—"
        ),
        "Scanner 2": (
            r2.get("Breakdown", {}).get(
                "VOLUME",
                "—",
            )
            if r2
            else "—"
        ),
        "Scanner 3": (
            r3.get("Volume", "—")
            if r3
            else "—"
        ),
        "Scanner 4": (
            f"{r4.get('Vol x Avg', '—')}x avg"
            if r4
            else "—"
        ),
    }

    # --------------------------------------------------------
    # Key Context
    # --------------------------------------------------------

    rows["Key Context"] = {
        "Scanner 1": (
            f"VWAP {r1.get('VWAP_strength', '—')} | "
            f"Extension {r1.get('Extension_ATR', '—')} ATR"
            if r1
            else "Bull/Bear gate not passed"
        ),
        "Scanner 2": (
            f"VWAP {r2.get('VWAP %', '—')}% | "
            f"Extension {r2.get('Extension (ATR)', '—')} ATR"
            if r2
            else "—"
        ),
        "Scanner 3": (
            f"{r3.get('Event', '—')} | "
            f"{r3.get('S/R Location', '—')}"
            if r3
            else "—"
        ),
        "Scanner 4": (
            r4.get("Score Label", "—")
            if r4
            else "—"
        ),
    }

    return pd.DataFrame(rows).T


# ============================================================
# TEST CONFIGURATION DISPLAY
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:
    st.info(
        "**Universe**\n\n"
        + (" · ".join(SYMBOLS) if SYMBOLS else "—")
    )

with col2:
    st.info(
        "**As-of**\n\n"
        + AS_OF.strftime("%d-%b-%Y · %H:%M")
    )

with col3:
    st.info(
        "**Engines**\n\n"
        "4 scanners"
    )


# ============================================================
# RUN BUTTON
# ============================================================

run_button = st.button(
    "🚀 RUN MARKET LAB",
    type="primary",
    use_container_width=True,
)

if run_button and not SYMBOLS:
    st.error("Please enter at least one stock symbol.")
    st.stop()

if run_button:

    st.divider()

    st.subheader("Running four scanners...")

    progress = st.progress(0)

    # --------------------------------------------------------
    # SCANNER 1
    # --------------------------------------------------------

    with st.spinner("Running Scanner 1..."):
        scanner1 = run_isolated_test(
            "market_lab_scanner1_test.py",
            SYMBOLS,
            AS_OF,
        )

    progress.progress(25)

    # --------------------------------------------------------
    # SCANNER 2
    # --------------------------------------------------------

    with st.spinner("Running Scanner 2..."):
        scanner2 = run_isolated_test(
            "market_lab_scanner2_test.py",
            SYMBOLS,
            AS_OF,
        )

    progress.progress(50)

    # --------------------------------------------------------
    # SCANNER 3
    # --------------------------------------------------------

    with st.spinner("Running Scanner 3..."):
        scanner3 = run_isolated_test(
            "market_lab_scanner3_test.py",
            SYMBOLS,
            AS_OF,
        )

    progress.progress(75)

    # --------------------------------------------------------
    # SCANNER 4
    # --------------------------------------------------------

    with st.spinner("Running Scanner 4..."):
        scanner4 = run_isolated_test(
            "market_lab_scanner4_test.py",
            SYMBOLS,
            AS_OF,
        )

    progress.progress(100)

    st.success("All four scanners completed.")

    # ========================================================
    # INDEX RESULTS BY SYMBOL
    # ========================================================

    s1 = {
        r.get("Symbol"): r
        for r in scanner1.get("results", [])
        if "error" not in r
    }

    s2 = {
        r.get("Symbol"): r
        for r in scanner2.get("results", [])
        if "error" not in r
    }

    s3 = {
        r.get("Ticker", "").replace(".NS", ""): r
        for r in scanner3.get("results", [])
        if "Error" not in r
    }

    s4 = {
        r.get("Ticker"): r
        for r in scanner4.get("results", [])
        if "Error" not in r
    }

    # ========================================================
    # STOCK RESULTS
    # ========================================================

    for symbol in SYMBOLS:

        st.divider()

        st.header(symbol)

        # ----------------------------------------------------
        # Get scanner results
        # ----------------------------------------------------

        r1 = s1.get(symbol, {})
        r2 = s2.get(symbol, {})
        r3 = s3.get(symbol, {})
        r4 = s4.get(symbol, {})

        # ====================================================
        # MACHINE READING
        # ====================================================

        st.markdown("### 🧠 Machine Reading")

        reading = build_machine_reading(
            symbol,
            r1,
            r2,
            r3,
            r4,
        )

        st.info(reading)

        # ====================================================
        # UNDERLYING DATA
        # ====================================================

        with st.expander(
            f"🔎 Underlying Scanner Data — {symbol}",
            expanded=False,
        ):

            st.markdown(
                "#### Four-Scanner Comparison"
            )

            comparison_df = build_underlying_table(
                r1,
                r2,
                r3,
                r4,
            )

            st.dataframe(
                comparison_df,
                use_container_width=True,
            )

            st.markdown(
                "#### Native Scanner Output"
            )

            tab1, tab2, tab3, tab4 = st.tabs(
                [
                    "Scanner 1",
                    "Scanner 2",
                    "Scanner 3",
                    "Scanner 4",
                ]
            )

            with tab1:
                st.json(r1)

            with tab2:
                st.json(r2)

            with tab3:
                st.json(r3)

            with tab4:
                st.json(r4)


    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        "Market Lab currently observes and explains the "
        "four scanner outputs. No consensus score, ranking, "
        "BUY/SELL decision, or additional trading logic "
        "is applied."
    )
