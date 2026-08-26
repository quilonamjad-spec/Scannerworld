"""
Market Lab - Grid Analysis

Phase 1A

Presentation-only module.

This module does NOT:
- run scanners
- fetch market data
- calculate scores
- modify scanner results
- create new trading logic
"""

import streamlit as st


# ============================================================
# VISUAL HELPERS
# ============================================================

def _direction_color(direction):
    if direction == "Bullish":
        return "#22C55E"

    if direction == "Bearish":
        return "#EF4444"

    return "#94A3B8"


def _direction_symbol(direction):
    if direction == "Bullish":
        return "🟢"

    if direction == "Bearish":
        return "🔴"

    return "⚪"


# ============================================================
# STOCK CARD
# ============================================================

def _render_stock_card(
    symbol,
    directions,
    column,
    card_number,
):
    """
    Render one stock card.

    Phase 1A:
    - Stock name
    - Scanner 1 direction
    - Scanner 2 direction
    - Scanner 3 direction
    - Scanner 4 direction
    - Open Workspace button
    """

    with column:

        # ----------------------------------------------------
        # Card HTML
        # ----------------------------------------------------

        scanner_rows = ""

        for scanner_number, direction in enumerate(
            directions,
            start=1,
        ):

            color = _direction_color(direction)
            icon = _direction_symbol(direction)

            scanner_rows += f"""
                <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    padding:7px 0;
                    font-size:13px;
                ">
                    <span style="
                        color:#CBD5E1;
                    ">
                        Scanner {scanner_number}
                    </span>

                    <span style="
                        color:{color};
                        font-weight:700;
                    ">
                        {icon} {direction}
                    </span>
                </div>
            """

        card_html = f"""
        <div style="
            border:1px solid #303642;
            border-radius:12px;
            padding:16px;
            background:#11161F;
            margin-bottom:8px;
        ">

            <div style="
                font-size:20px;
                font-weight:800;
                color:#F8FAFC;
                margin-bottom:14px;
            ">
                {symbol}
            </div>

            <div style="
                border-top:1px solid #252B35;
                padding-top:8px;
            ">
                {scanner_rows}
            </div>

        </div>
        """

        # Streamlit's HTML renderer.
        st.html(card_html)

        # ----------------------------------------------------
        # Workspace button
        # ----------------------------------------------------

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

    Parameters
    ----------
    symbols:
        List of dictionaries:

        [
            {
                "symbol": "RELIANCE",
                "directions": [
                    "No Signal",
                    "Bearish",
                    "Bearish",
                    "Bearish",
                ],
            },
            ...
        ]

    scanner1/scanner2/scanner3/scanner4:
        Existing indexed scanner results.

    These scanner dictionaries are intentionally not modified.
    """

    st.subheader("📊 Grid Analysis")

    if not symbols:
        st.info("No stocks selected.")
        return

    # --------------------------------------------------------
    # Three cards per row
    # --------------------------------------------------------

    columns_per_row = 3

    for start in range(
        0,
        len(symbols),
        columns_per_row,
    ):

        row = symbols[
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
