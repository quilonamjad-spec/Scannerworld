import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# Make Scannerworld root available to Python
# ============================================================

ROOT_DIR = Path(__file__).resolve().parent.parent


def run_isolated_test(script_name):
    """
    Run one scanner in its own Python process.

    This prevents generic module names such as indicators.py,
    config.py, data.py, etc. from colliding between scanners.
    """

    script_path = ROOT_DIR / script_name

    result = subprocess.run(
        [sys.executable, str(script_path)],
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

    # Find the JSON object printed by the diagnostic script.
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


scanner1 = run_isolated_test(
    "market_lab_test.py"
)

scanner2 = run_isolated_test(
    "market_lab_scanner2_test.py"
)

scanner3 = run_isolated_test(
    "market_lab_scanner3_test.py"
)

scanner4 = run_isolated_test(
    "market_lab_scanner4_test.py"
)

# ============================================================
# MARKET LAB
# First visual integration of all four scanners
# ============================================================

st.set_page_config(
    page_title="Market Lab",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 MARKET LAB")
st.caption("Four Scanner Intelligence Layer — First Integration")


# ------------------------------------------------------------
# TEST CONFIGURATION
# ------------------------------------------------------------

SYMBOLS = ["ADANIPOWER", "TCS"]
AS_OF = "2026-08-21 13:55"


st.markdown("### Test Configuration")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("**Universe**\n\nADANIPOWER · TCS")

with col2:
    st.info("**As-of**\n\n21-Aug-2026 · 13:55")

with col3:
    st.info("**Engines**\n\n4 scanners")


st.markdown("")


# ------------------------------------------------------------
# RUN BUTTON
# ------------------------------------------------------------

run_button = st.button(
    "🚀 RUN MARKET LAB",
    type="primary",
    use_container_width=True,
)


if run_button:

    st.divider()

    st.subheader("Running four scanners...")

    progress = st.progress(0)

    # --------------------------------------------------------
    # SCANNER 1
    # --------------------------------------------------------

    with st.spinner("Running Scanner 1..."):
        scanner1 = run_scanner1(
            symbols=SYMBOLS,
            as_of=AS_OF,
        )

    progress.progress(25)

    # --------------------------------------------------------
    # SCANNER 2
    # --------------------------------------------------------

    with st.spinner("Running Scanner 2..."):
        scanner2 = run_scanner2(
            symbols=SYMBOLS,
            as_of=AS_OF,
            interval="5m",
            period="5d",
            batch_size=2,
        )

    progress.progress(50)

    # --------------------------------------------------------
    # SCANNER 3
    # --------------------------------------------------------

    with st.spinner("Running Scanner 3..."):
        scanner3 = run_scanner3(
            symbols=SYMBOLS,
            as_of=AS_OF,
            interval="5m",
        )

    progress.progress(75)

    # --------------------------------------------------------
    # SCANNER 4
    # --------------------------------------------------------

    with st.spinner("Running Scanner 4..."):
        scanner4 = run_scanner4(
            symbols=SYMBOLS,
            as_of=AS_OF,
            period_days=5,
            smooth=True,
            chart_lookback=60,
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
    # DISPLAY ONE STOCK AT A TIME
    # ========================================================

    for symbol in SYMBOLS:

        st.divider()

        st.header(symbol)

        # ----------------------------------------------------
        # Get each scanner's result
        # ----------------------------------------------------

        r1 = s1.get(symbol, {})
        r2 = s2.get(symbol, {})
        r3 = s3.get(symbol, {})
        r4 = s4.get(symbol, {})


        # ====================================================
        # TOP SNAPSHOT
        # ====================================================

        st.markdown("#### Four-Scanner Snapshot")

        c1, c2, c3, c4 = st.columns(4)


        # Scanner 1
        with c1:

            st.markdown("**SCANNER 1**")

            if r1:
                phase = r1.get("Phase", "—")

                st.metric(
                    "Result",
                    phase,
                )

                st.caption(
                    f"LTP: {r1.get('LTP', '—')}"
                )

            else:
                st.metric(
                    "Result",
                    "No result",
                )


        # Scanner 2
        with c2:

            st.markdown("**SCANNER 2**")

            if r2:

                st.metric(
                    "Signal",
                    r2.get(
                        "Signal",
                        "—",
                    ),
                    f"Score {r2.get('Trade Score', '—')}",
                )

                st.caption(
                    f"Confidence: "
                    f"{r2.get('Confidence', '—')}"
                )

            else:
                st.metric(
                    "Signal",
                    "No result",
                )


        # Scanner 3
        with c3:

            st.markdown("**SCANNER 3**")

            if r3:

                st.metric(
                    "Direction",
                    r3.get(
                        "Direction",
                        "—",
                    ),
                    f"Score {r3.get('Score', '—')}",
                )

                st.caption(
                    f"Consensus: "
                    f"{r3.get('Consensus', '—')}"
                )

            else:
                st.metric(
                    "Direction",
                    "No result",
                )


        # Scanner 4
        with c4:

            st.markdown("**SCANNER 4**")

            if r4:

                st.metric(
                    "Anchor",
                    r4.get(
                        "Anchor",
                        "—",
                    ),
                    f"Score {r4.get('Total Score', '—')}",
                )

                st.caption(
                    r4.get(
                        "Score Label",
                        "—",
                    )
                )

            else:
                st.metric(
                    "Anchor",
                    "No result",
                )


        # ====================================================
        # DETAIL TABLE
        # ====================================================

        st.markdown("#### Scanner Details")

        detail_rows = []


        if r1:

            detail_rows.append(
                {
                    "Scanner": "Scanner 1",
                    "Direction / Result": r1.get(
                        "Phase",
                        "—",
                    ),
                    "Score": "—",
                    "Confidence": "—",
                    "Context": (
                        f"RSI {r1.get('RSI14', '—')} | "
                        f"Extension "
                        f"{r1.get('Extension_ATR', '—')}"
                    ),
                }
            )


        if r2:

            detail_rows.append(
                {
                    "Scanner": "Scanner 2",
                    "Direction / Result": r2.get(
                        "Signal",
                        "—",
                    ),
                    "Score": r2.get(
                        "Trade Score",
                        "—",
                    ),
                    "Confidence": r2.get(
                        "Confidence",
                        "—",
                    ),
                    "Context": (
                        f"RSI {r2.get('RSI', '—')} | "
                        f"ADX {r2.get('ADX', '—')}"
                    ),
                }
            )


        if r3:

            detail_rows.append(
                {
                    "Scanner": "Scanner 3",
                    "Direction / Result": r3.get(
                        "Direction",
                        "—",
                    ),
                    "Score": r3.get(
                        "Score",
                        "—",
                    ),
                    "Confidence": r3.get(
                        "Consensus",
                        "—",
                    ),
                    "Context": (
                        f"{r3.get('Pattern', '—')} | "
                        f"{r3.get('Event', '—')}"
                    ),
                }
            )


        if r4:

            detail_rows.append(
                {
                    "Scanner": "Scanner 4",
                    "Direction / Result": r4.get(
                        "Anchor",
                        "—",
                    ),
                    "Score": r4.get(
                        "Total Score",
                        "—",
                    ),
                    "Confidence": "—",
                    "Context": (
                        f"{r4.get('Chart Pattern', '—')} | "
                        f"{r4.get('Score Label', '—')}"
                    ),
                }
            )


        if detail_rows:

            df = pd.DataFrame(detail_rows)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
            )


        # ====================================================
        # NATIVE DETAILS
        # ====================================================

        with st.expander(
            f"🔎 Detailed scanner output — {symbol}"
        ):

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


    # --------------------------------------------------------
    # IMPORTANT: NO MARKET LAB DECISION YET
    # --------------------------------------------------------

    st.divider()

    st.info(
        "Market Lab is currently displaying the four "
        "scanner opinions only. No consensus, ranking, "
        "BUY/SELL decision, or additional scoring is "
        "being applied yet."
    )
