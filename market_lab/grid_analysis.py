"""
Market Lab — Grid Analysis
===========================

Presentation-only module for the Market Lab four-scanner output.

Design goals:
- Two stocks per row.
- Preserve the native scanner values.
- Do not invent, normalize, weight, or calculate new scanner scores.
- Blank fields when a scanner does not provide that value.
- Bullish = green, Bearish = red, No Signal = neutral.
- Mini chart = candles + EMA 9 + VWAP only.
- "Open Workspace" opens the existing stock-level analysis in an expander.

Expected inputs:
    render_grid_analysis(
        symbols,
        s1, s2, s3, s4,
        render_workspace=None,
    )

Where s1..s4 are dictionaries indexed by symbol, exactly as the
Market Lab app already builds them.
"""

from __future__ import annotations

from typing import Callable, Dict, Mapping, Optional, Sequence, Any

import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ---------------------------------------------------------------------
# COMMON HELPERS
# ---------------------------------------------------------------------

BLANK = ""


def _value(result: Optional[Mapping[str, Any]], key: str) -> str:
    """Return a native scanner value or blank when unavailable."""
    if not result:
        return BLANK

    value = result.get(key, BLANK)

    if value is None:
        return BLANK

    if isinstance(value, str) and value.strip() in {"—", "-", "None"}:
        return BLANK

    return str(value)


def _number(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _direction(scanner_number: int, result: Optional[Mapping[str, Any]]) -> str:
    """
    Same direction vocabulary already used by Market Lab.

    This is only a vocabulary mapping; it does not alter scanner logic.
    """
    if not result:
        return "No Signal"

    if scanner_number == 1:
        value = str(result.get("Phase", "")).lower()
        if value == "bull":
            return "Bullish"
        if value == "bear":
            return "Bearish"
        return "No Signal"

    if scanner_number == 2:
        value = str(result.get("Signal", "")).lower()
        if value == "buy":
            return "Bullish"
        if value == "sell":
            return "Bearish"
        return "No Signal"

    if scanner_number == 3:
        value = str(result.get("Direction", "")).lower()
        if "bull" in value:
            return "Bullish"
        if "bear" in value:
            return "Bearish"
        return "No Signal"

    if scanner_number == 4:
        value = str(result.get("Anchor", "")).lower()
        if "bull" in value:
            return "Bullish"
        if "bear" in value:
            return "Bearish"
        return "No Signal"

    return "No Signal"


def _direction_color(direction: str) -> str:
    if direction == "Bullish":
        return "#22C55E"
    if direction == "Bearish":
        return "#FF3B4B"
    return "#D8C7E8"



def _score_for(scanner_number: int, result: Optional[Mapping[str, Any]]) -> str:
    if not result:
        return ""

    if scanner_number == 1:
        return _value(result, "Score")
    if scanner_number == 2:
        return _value(result, "Trade Score")
    if scanner_number == 3:
        return _value(result, "Score")
    if scanner_number == 4:
        return _value(result, "Total Score")

    return ""


def _confidence_consensus(
    scanner_number: int,
    result: Optional[Mapping[str, Any]],
) -> str:
    """
    Only show values actually supplied by the scanners.

    Scanner 1: no invented value.
    Scanner 2: native Confidence.
    Scanner 3: native Consensus.
    Scanner 4: no invented value.
    """
    if not result:
        return ""

    if scanner_number == 2:
        return _value(result, "Confidence")

    if scanner_number == 3:
        return _value(result, "Consensus")

    return ""


def _volume_rsi(
    scanner_number: int,
    result: Optional[Mapping[str, Any]],
) -> tuple[str, str]:
    """
    Compact scanner-native volume / RSI display.

    No new metric is calculated here.
    """
    if not result:
        return "", ""

    if scanner_number == 1:
        return (
            _value(result, "Volume_strength"),
            _value(result, "RSI14"),
        )

    if scanner_number == 2:
        volume = ""
        breakdown = result.get("Breakdown", {})
        if isinstance(breakdown, Mapping):
            raw = breakdown.get("VOLUME", "")
            if raw is not None:
                volume = str(raw)

        return volume, _value(result, "RSI")

    if scanner_number == 3:
        return _value(result, "Volume"), _value(result, "RSI")

    if scanner_number == 4:
        vol = _value(result, "Vol x Avg")
        if vol:
            vol = f"{vol}x avg"
        return vol, _value(result, "RSI")

    return "", ""


def _confidence_label(value: str) -> tuple[str, str]:
    """
    Display the native confidence/consensus value with a visual label.

    No threshold changes the underlying value. This only improves display.
    """
    number = _number(value)

    if number is None:
        return value, "#A7B0C0"

    if number >= 70:
        return "High", "#22C55E"
    if number >= 50:
        return "Medium", "#FACC15"
    return "Low", "#FF3B4B"



def _get_chart(result: Optional[Mapping[str, Any]]) -> Optional[Mapping[str, Any]]:
    if not result:
        return None

    chart = result.get("Chart")
    if isinstance(chart, Mapping):
        return chart

    return None


def _render_mini_chart(
    chart_data: Optional[Mapping[str, Any]],
    chart_key: str,
) -> None:
    """
    Render only:
        Candles + EMA 9 + VWAP

    S/R zones, EMA20 and other Scanner 3 chart elements intentionally stay
    in the full Stock Selector workspace, not in this compressed grid.
    """
    if not chart_data:
        st.info("Chart data unavailable")
        return

    candles = chart_data.get("candles", [])
    if not candles:
        st.info("No chart candles available")
        return

    df = pd.DataFrame(candles).copy()

    required = {"Time", "Open", "High", "Low", "Close"}
    if not required.issubset(df.columns):
        st.info("Chart fields unavailable")
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
            name="Candles",
            increasing=dict(
                line=dict(color="#4ADE80"),
                fillcolor="#22C55E",
            ),
            decreasing=dict(
                line=dict(color="#FF6B6B"),
                fillcolor="#FF3B4B",
            ),
        )
    )

    if "EMA9" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Time"],
                y=df["EMA9"],
                mode="lines",
                name="EMA 9",
                line=dict(color="#3B82F6", width=1.6),
            )
        )

    if "VWAP" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["Time"],
                y=df["VWAP"],
                mode="lines",
                name="VWAP",
                line=dict(color="#FACC15", width=1.6),
            )
        )

    fig.update_layout(
        height=245,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            rangeslider_visible=False,
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            fixedrange=True,
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.03,
            xanchor="center",
            x=0.5,
            font=dict(size=11, color="#D7DFEA"),
        ),
        hovermode=False,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
            "staticPlot": False,
            "scrollZoom": False,
        },
        key=chart_key,
    )


# ---------------------------------------------------------------------
# STOCK CARD
# ---------------------------------------------------------------------

def _scanner_cell(
    scanner_number: int,
    result: Optional[Mapping[str, Any]],
) -> dict[str, Any]:
    direction = _direction(scanner_number, result)
    score = _score_for(scanner_number, result)
    confidence = _confidence_consensus(scanner_number, result)
    volume, rsi = _volume_rsi(scanner_number, result)

    return {
        "direction": direction,
        "score": score,
        "confidence": confidence,
        "volume": volume,
        "rsi": rsi,
    }


def _overall_direction(
    r1: Optional[Mapping[str, Any]],
    r2: Optional[Mapping[str, Any]],
    r3: Optional[Mapping[str, Any]],
    r4: Optional[Mapping[str, Any]],
) -> str:
    """
    Display-only bias from the already normalized scanner directions.

    This is not a score and is not used to make a trading decision.
    """
    directions = [
        _direction(1, r1),
        _direction(2, r2),
        _direction(3, r3),
        _direction(4, r4),
    ]

    bullish = directions.count("Bullish")
    bearish = directions.count("Bearish")

    if bullish > bearish:
        return "Bullish"
    if bearish > bullish:
        return "Bearish"
    return "Mixed"


def _render_stock_card(
    symbol: str,
    r1: Optional[Mapping[str, Any]],
    r2: Optional[Mapping[str, Any]],
    r3: Optional[Mapping[str, Any]],
    r4: Optional[Mapping[str, Any]],
    card_index: int,
    render_workspace: Optional[Callable[..., Any]] = None,
) -> None:
    """Render one stock card using Streamlit-native layout primitives.

    No raw HTML is used for the card layout.  The existing scanner values
    and chart are displayed as supplied by the scanner pipeline.
    """

    rows = [
        ("Scanner 1", 1, r1),
        ("Scanner 2", 2, r2),
        ("Scanner 3", 3, r3),
        ("Scanner 4", 4, r4),
    ]

    bias = _overall_direction(r1, r2, r3, r4)

    # Native Streamlit card/container.
    with st.container(border=True):
        st.subheader(symbol)

        # RSI and volume are common context values.  As agreed, take them
        # from Scanner 4 rather than repeating them for every scanner.
        top_left, top_right = st.columns(2)
        with top_left:
            st.metric("RSI", _value(r4, "RSI") or "—")
        with top_right:
            volume = _value(r4, "Vol x Avg")
            st.metric("Volume", volume or "—")

        st.divider()

        # Four-column scanner grid.
        # RSI and Volume are intentionally NOT repeated here because they
        # are already shown once at the top of the stock card from Scanner 4.
        h = st.columns([1.15, 0.95, 1.35, 1.05])
        h[0].caption("Scanner")
        h[1].caption("Score / 10")
        h[2].caption("Confidence / Consensus")
        h[3].caption("Direction")

        for scanner_name, scanner_number, result in rows:
            cell = _scanner_cell(scanner_number, result)
            direction = cell["direction"]
            score = cell["score"]
            confidence = cell["confidence"]

            c = st.columns([1.15, 0.95, 1.35, 1.05])

            with c[0]:
                st.write(scanner_name)

            with c[1]:
                st.write(score if score else "—")

            with c[2]:
                if confidence:
                    label, _ = _confidence_label(confidence)
                    st.write(f"{confidence}")
                    if label:
                        st.caption(label)
                else:
                    st.write("—")

            with c[3]:
                if direction == "Bullish":
                    st.success("🟢 Bullish", icon="🟢")
                elif direction == "Bearish":
                    st.error("🔴 Bearish", icon="🔴")
                else:
                    st.info("⚪ No Signal" if direction == "No Signal" else "🟡 Mixed")

        st.divider()

        if bias == "Bullish":
            st.success(f"Overall Bias: **{bias}**")
        elif bias == "Bearish":
            st.error(f"Overall Bias: **{bias}**")
        else:
            st.warning(f"Overall Bias: **{bias}**")

        chart_data = _get_chart(r3)
        _render_mini_chart(
            chart_data,
            chart_key=f"grid-chart-{card_index}-{symbol}",
        )

        if render_workspace is not None:
            if st.button(
                "🔎 Open Workspace",
                key=f"grid-workspace-{card_index}-{symbol}",
                use_container_width=True,
            ):
                render_workspace(
                    symbol=symbol,
                    r1=r1,
                    r2=r2,
                    r3=r3,
                    r4=r4,
                )


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------

def render_grid_analysis(
    symbols: Sequence[Any],
    s1: Optional[Mapping[str, Mapping[str, Any]]] = None,
    s2: Optional[Mapping[str, Mapping[str, Any]]] = None,
    s3: Optional[Mapping[str, Mapping[str, Any]]] = None,
    s4: Optional[Mapping[str, Mapping[str, Any]]] = None,
    render_workspace: Optional[Callable[..., Any]] = None,
    scanner1: Optional[Mapping[str, Mapping[str, Any]]] = None,
    scanner2: Optional[Mapping[str, Mapping[str, Any]]] = None,
    scanner3: Optional[Mapping[str, Mapping[str, Any]]] = None,
    scanner4: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> None:
    """
    Render the Market Lab multi-stock Grid Analysis.

    symbols:
        The user-selected universe. The normal Market Lab input is a
        sequence of ticker strings. For compatibility, dictionary/list
        entries containing a symbol/ticker/name field are also accepted.

    s1/s2/s3/s4:
        Existing Market Lab scanner dictionaries indexed by symbol.

    scanner1/scanner2/scanner3/scanner4:
        Compatibility aliases for app.py versions that use the longer
        scanner argument names.

    render_workspace:
        Optional callback supplied by app.py. If provided, the button
        opens the existing Stock Selector workspace without duplicating
        that logic here.
    """

    # Accept either the original s1..s4 names or scanner1..scanner4.
    s1 = s1 if s1 is not None else (scanner1 or {})
    s2 = s2 if s2 is not None else (scanner2 or {})
    s3 = s3 if s3 is not None else (scanner3 or {})
    s4 = s4 if s4 is not None else (scanner4 or {})

    # Some app versions pass stock records rather than plain ticker
    # strings. Normalize those records before using them as dictionary
    # keys, preventing "unhashable type: dict".
    if isinstance(symbols, Mapping):
        raw_symbols = list(symbols.keys())
    else:
        raw_symbols = list(symbols)

    normalized_symbols = []
    for item in raw_symbols:
        if isinstance(item, Mapping):
            candidate = (
                item.get("symbol")
                or item.get("Symbol")
                or item.get("ticker")
                or item.get("Ticker")
                or item.get("name")
                or item.get("Name")
            )
            if candidate is not None:
                normalized_symbols.append(str(candidate))
        else:
            normalized_symbols.append(str(item))

    symbols = normalized_symbols

    st.title("📊 Grid Analysis")
    st.caption("Real-time multi-scanner intelligence at a glance")

    symbols = list(symbols)

    if not symbols:
        st.info("No stocks selected.")
        return

    # Exactly two stock cards per row.
    for row_start in range(0, len(symbols), 2):
        row_symbols = symbols[row_start:row_start + 2]

        cols = st.columns(2, gap="medium")

        for col_index, symbol in enumerate(row_symbols):
            with cols[col_index]:
                _render_stock_card(
                    symbol=symbol,
                    r1=s1.get(symbol, {}),
                    r2=s2.get(symbol, {}),
                    r3=s3.get(symbol, {}),
                    r4=s4.get(symbol, {}),
                    card_index=row_start + col_index,
                    render_workspace=render_workspace,
                )

        # Keep an odd final card visually contained.
        if len(row_symbols) == 1:
            with cols[1]:
                st.empty()


__all__ = ["render_grid_analysis"]
