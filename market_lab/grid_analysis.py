"""
Market Lab - Grid Analysis

Phase 1A:
    Stock cards + existing scanner direction.

This module is presentation-only.

It does NOT:
    - run scanners
    - fetch data
    - calculate scores
    - modify scanner results
    - create new trading logic
"""

import streamlit as st


# ============================================================
# VISUAL HELPERS
# ============================================================

def _direction_color(direction):
    """Return the visual color for an existing Market Lab direction."""

    if direction == "Bullish":
        return "#22C55E"

    if direction == "Bearish":
        return "#EF4444"

    return "#94A3B8"


def _direction_symbol(direction):
    """Return a compact visual indicator."""

    if direction == "Bullish":
        return "🟢"

    if direction == "Bearish":
        return "🔴"

    return "⚪"


def _overall_state(directions):
    """
    Simple visual summary of the four existing scanner directions.

    This is NOT a new score or trading decision.

    All bullish  -> Bullish
    All bearish  -> Bearish
    Otherwise    -> Mixed
    No signals   -> Neutral
    """

    bullish = directions.count("Bullish")
    bearish = directions.count("Bearish")

    if bullish == 4:
        return "Bullish"

    if bearish == 4:
        return "Bearish"

    if bullish == 0 and bearish == 0:
        return "Neutral"

    return "Mixed"


def _overall_html(state):
    if state == "Bullish":
        return (
            '<span style="color:#4ADE80;'
            'font-weight:800;">🟢 BULLISH</span>'
        )

    if state == "Bearish":
        return (
            '<span style="color:#FF6B6B;'
            'font-weight:800;">🔴 BEARISH</span>'
        )

    if state == "Mixed":
        return (
            '<span style="color:#FACC15;'
            'font-weight:800;">🟡 MIXED</span>'
        )

    return (
        '<span style="color:#CBD5E1;'
        'font-weight:800;">⚪ NEUTRAL</span>'
    )


# ============================================================
# STOCK CARD
# ============================================================

def _render_stock_card(
    symbol,
    directions,
    column,
    card_number,
):
    """Render one Phase-1A stock card."""

    overall = _overall_state(directions)

    with column:

        st.markdown(
            f"""
            <div style="
                border:1px solid #303642;
                border-radius:12px;
                padding:16px;
                background:#11161F;
                min-height:245px;
                margin-bottom:8px;
            ">

                <div style="
                    font-size:20px;
                    font-weight:800;
                    color:#F8FAFC;
                    margin-bottom:10px;
                ">
                    {symbol}
                </div>

                <div style="
                    margin-bottom:14px;
                    font-size:14px;
                ">
                    {_overall_html(overall)}
                </div>

                <div style="
                    border-top:1px solid #252B35;
                    padding-top:8px;
                ">
            """,
            unsafe_allow_html=True,
        )

        for scanner_number, direction in enumerate(
            directions,
            start=1,
        ):
            color = _direction_color(direction)
            icon = _direction_symbol(direction)

            st.markdown(
                f"""
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    padding:6px 0;
                    font-size:13px;
                ">
                    <span style="color:#CBD5E1;">
                        Scanner {scanner_number}
                    </span>

                    <span style="
                        color:{color};
                        font-weight:700;
                    ">
                        {icon} {direction}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            """
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Workspace connection will be added later.
        if st.button(
            "🔎 Open Workspace",
            key=f"grid_workspace_{symbol}_{card_number}",
            use_container_width=True,
        ):
            st.session_state["grid_selected_symbol"] = symbol

            st.info(
                f"Workspace selected: **{symbol}**"
            )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def render_grid_analysis(
    symbols,
    scanner1,
    scanner2,
    scanner3,
    scanner4,
):
    """
    Render Market Lab Grid Analysis.

    Parameters are the already-computed Market Lab results.

    No scanner is executed here.
    """

    st.subheader("📊 Grid Analysis")

    if not symbols:
        st.info("No stocks selected.")
        return

    # --------------------------------------------------------
    # Build directions using the SAME Market Lab vocabulary.
    #
    # The normalize_direction function remains in app.py
    # because it is part of the existing Market Lab logic.
    # --------------------------------------------------------

    # We receive pre-normalized directions from app.py.
    #
    # Expected structure:
    #
    # {
    #     "ADANIPOWER": [
    #         "Bullish",
    #         "Bearish",
    #         "Bullish",
    #         "No Signal",
    #     ],
    #     ...
    # }

    stock_directions = symbols

    # --------------------------------------------------------
    # Grid
    # --------------------------------------------------------

    columns_per_row = 3

    for start in range(
        0,
        len(stock_directions),
        columns_per_row,
    ):

        row = stock_directions[
            start:start + columns_per_row
        ]

        columns = st.columns(
            columns_per_row
        )

        for offset, item in enumerate(row):

            symbol = item["symbol"]
            directions = item["directions"]

            _render_stock_card(
                symbol=symbol,
                directions=directions,
                column=columns[offset],
                card_number=start + offset,
            )
