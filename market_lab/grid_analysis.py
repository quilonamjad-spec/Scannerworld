"""
Market Lab — Grid Analysis
Native Streamlit presentation layer.

Important:
- Uses existing scanner outputs only.
- Does not create or alter trading logic.
- Does not calculate new scores.
- Missing scanner values remain blank.
- Two stocks per row.
- Mini chart: candles + EMA9 + VWAP only.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


# ============================================================
# BASIC HELPERS
# ============================================================

def _get(result: Optional[Mapping[str, Any]], key: str) -> Any:
    if not result:
        return ""
    value = result.get(key, "")
    return "" if value is None else value


def _display(value: Any) -> str:
    if value is None or value == "":
        return ""
    return str(value)


def _direction(scanner: int, result: Optional[Mapping[str, Any]]) -> str:
    if not result:
        return ""

    if scanner == 1:
        value = str(result.get("Phase", "")).lower()
        if value == "bull":
            return "Bullish"
        if value == "bear":
            return "Bearish"
        return "No Signal"

    if scanner == 2:
        value = str(result.get("Signal", "")).lower()
        if value == "buy":
            return "Bullish"
        if value == "sell":
            return "Bearish"
        return "No Signal"

    if scanner == 3:
        value = str(result.get("Direction", "")).lower()
        if "bull" in value:
            return "Bullish"
        if "bear" in value:
            return "Bearish"
        return "No Signal"

    if scanner == 4:
        value = str(result.get("Anchor", "")).lower()
        if "bull" in value:
            return "Bullish"
        if "bear" in value:
            return "Bearish"
        return "No Signal"

    return ""


def _score(scanner: int, result: Optional[Mapping[str, Any]]) -> str:
    if not result:
        return ""

    if scanner == 1:
        return _display(_get(result, "Score"))

    if scanner == 2:
        return _display(_get(result, "Trade Score"))

    if scanner == 3:
        return _display(_get(result, "Score"))

    if scanner == 4:
        return _display(_get(result, "Total Score"))

    return ""


def _secondary(scanner: int, result: Optional[Mapping[str, Any]]) -> tuple[str, str]:
    """
    Return only values that already exist in that scanner.

    Scanner 2 -> Confidence + RSI
    Scanner 3 -> Consensus + RSI
    Scanner 1/4 -> whatever native secondary fields exist,
                   otherwise blank.
    """
    if not result:
        return "", ""

    if scanner == 2:
        return (
            _display(_get(result, "Confidence")),
            _display(_get(result, "RSI")),
        )

    if scanner == 3:
        return (
            _display(_get(result, "Consensus")),
            _display(_get(result, "RSI")),
        )

    if scanner == 1:
        return (
            _display(_get(result, "Confidence")),
            _display(_get(result, "RSI14")),
        )

    if scanner == 4:
        return (
            _display(_get(result, "Confidence")),
            _display(_get(result, "RSI")),
        )

    return "", ""


def _direction_style(direction: str) -> tuple[str, str]:
    if direction == "Bullish":
        return "🟢", "green"

    if direction == "Bearish":
        return "🔴", "red"

    if direction == "No Signal":
        return "⚪", "gray"

    return "", "gray"


# ============================================================
# MINI CHART
# ============================================================

def _chart_from_result(result: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    if not result:
        return None

    chart = result.get("Chart")

    if isinstance(chart, Mapping):
        return chart

    return None


def _render_mini_chart(
    result: Optional[Mapping[str, Any]],
    key: str,
) -> None:

    chart = _chart_from_result(result)

    if not chart:
        st.caption("Chart data unavailable")
        return

    candles = chart.get("candles", [])

    if not candles:
        st.caption("Chart data unavailable")
        return

    df = pd.DataFrame(candles).copy()

    required = {"Time", "Open", "High", "Low", "Close"}

    if not required.issubset(df.columns):
        st.caption("Chart data unavailable")
        return

    df["Time"] = pd.to_datetime(df["Time"])

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["Time"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="Price",
            increasing=dict(
                line=dict(color="#22C55E"),
                fillcolor="#22C55E",
            ),
            decreasing=dict(
                line=dict(color="#EF4444"),
                fillcolor="#EF4444",
            ),
        )
    )

    if "EMA9" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Time"],
                y=df["EMA9"],
                name="EMA 9",
                mode="lines",
                line=dict(
                    color="#3B82F6",
                    width=1.6,
                ),
            )
        )

    if "VWAP" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Time"],
                y=df["VWAP"],
                name="VWAP",
                mode="lines",
                line=dict(
                    color="#FACC15",
                    width=1.6,
                ),
            )
        )

    fig.update_layout(
        height=245,
        margin=dict(
            l=5,
            r=5,
            t=5,
            b=5,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.02,
            xanchor="center",
            x=0.5,
            font=dict(size=10),
        ),
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            rangeslider_visible=False,
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
        ),
        hovermode=False,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "scrollZoom": False,
        },
        key=key,
    )


# ============================================================
# SCANNER ROW
# ============================================================

def _render_scanner_row(
    scanner: int,
    result: Optional[Mapping[str, Any]],
) -> None:

    name = f"Scanner {scanner}"
    direction = _direction(scanner, result)
    score = _score(scanner, result)
    secondary_1, secondary_2 = _secondary(scanner, result)

    icon, colour = _direction_style(direction)

    cols = st.columns(
        [1.25, 1.0, 1.0, 1.2, 1.25],
        vertical_alignment="center",
    )

    with cols[0]:
        st.write(f"**{name}**")

    with cols[1]:
        st.write(score if score else " ")

    with cols[2]:
        if secondary_2:
            st.write(f"RSI  **{secondary_2}**")
        else:
            st.write(" ")

    with cols[3]:
        if secondary_1:
            label = "Confidence" if scanner in (1, 2, 4) else "Consensus"
            st.write(f"{label}  **{secondary_1}**")
        else:
            st.write(" ")

    with cols[4]:
        if direction:
            st.markdown(
                f"<span style='color:{colour}; font-weight:700;'>"
                f"{icon} {direction}"
                f"</span>",
                unsafe_allow_html=True,
            )
        else:
            st.write(" ")


# ============================================================
# STOCK CARD
# ============================================================

def _render_stock_card(
    symbol: str,
    r1: Optional[Mapping[str, Any]],
    r2: Optional[Mapping[str, Any]],
    r3: Optional[Mapping[str, Any]],
    r4: Optional[Mapping[str, Any]],
    index: int,
    render_workspace: Optional[Callable[..., Any]],
) -> None:

    with st.container(border=True):

        st.subheader(symbol)

        header = st.columns(
            [1.25, 1.0, 1.0, 1.2, 1.25],
            vertical_alignment="center",
        )

        labels = [
            "",
            "Score",
            "RSI",
            "Confidence / Consensus",
            "Direction",
        ]

        for col, label in zip(header, labels):
            with col:
                if label:
                    st.caption(label)

        _render_scanner_row(1, r1)
        _render_scanner_row(2, r2)
        _render_scanner_row(3, r3)
        _render_scanner_row(4, r4)

        st.divider()

        # Scanner 3 is the existing source of the detailed chart data.
        _render_mini_chart(
            r3,
            key=f"grid_chart_{index}_{symbol}",
        )

        st.divider()

        if render_workspace is not None:
            if st.button(
                "🔎 Open Workspace",
                key=f"grid_workspace_{index}_{symbol}",
                use_container_width=True,
            ):
                render_workspace(
                    symbol=symbol,
                    r1=r1,
                    r2=r2,
                    r3=r3,
                    r4=r4,
                )


# ============================================================
# PUBLIC FUNCTION
# ============================================================

def render_grid_analysis(
    symbols: Sequence[str],
    s1: Mapping[str, Mapping[str, Any]],
    s2: Mapping[str, Mapping[str, Any]],
    s3: Mapping[str, Mapping[str, Any]],
    s4: Mapping[str, Mapping[str, Any]],
    render_workspace: Optional[Callable[..., Any]] = None,
) -> None:
    """
    Main Grid Analysis renderer.

    symbols:
        Selected stock universe.

    s1/s2/s3/s4:
        Existing scanner results indexed by symbol.

    render_workspace:
        Optional callback to the existing detailed stock workspace.
    """

    st.title("📊 Grid Analysis")

    st.caption(
        "Multi-stock scanner comparison using the existing scanner outputs."
    )

    symbols = list(symbols)

    if not symbols:
        st.info("No stocks selected.")
        return

    # Exactly two stocks per row.
    for start in range(0, len(symbols), 2):

        row = symbols[start:start + 2]

        columns = st.columns(
            2,
            gap="medium",
        )

        for position, symbol in enumerate(row):

            with columns[position]:

                _render_stock_card(
                    symbol=symbol,
                    r1=s1.get(symbol, {}),
                    r2=s2.get(symbol, {}),
                    r3=s3.get(symbol, {}),
                    r4=s4.get(symbol, {}),
                    index=start + position,
                    render_workspace=render_workspace,
                )


__all__ = ["render_grid_analysis"]
