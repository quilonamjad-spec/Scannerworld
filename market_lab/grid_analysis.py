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


def _direction_dot(direction: str) -> str:
    color = _direction_color(direction)
    return (
        f'<span style="display:inline-block;width:15px;height:15px;'
        f'border-radius:50%;background:{color};margin-right:8px;'
        f'vertical-align:-2px;box-shadow:0 0 7px {color};"></span>'
    )


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


def _consensus_ring(value: str) -> str:
    """
    Small CSS ring for a native percentage value.

    If the scanner supplies a percentage, the ring visualizes that same
    percentage. If not, it stays blank.
    """
    number = _number(value)

    if number is None:
        return '<div class="ml-empty-ring"></div>'

    number = max(0.0, min(100.0, number))

    if number >= 70:
        color = "#22C55E"
    elif number >= 50:
        color = "#FACC15"
    else:
        color = "#FF3B4B"

    return f"""
    <div class="ml-ring"
         style="--pct:{number}%;--ring:{color};">
        <span>{number:.0f}%</span>
    </div>
    """


# ---------------------------------------------------------------------
# MINI CHART
# ---------------------------------------------------------------------

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
        st.markdown(
            '<div class="ml-chart-empty">Chart data unavailable</div>',
            unsafe_allow_html=True,
        )
        return

    candles = chart_data.get("candles", [])
    if not candles:
        st.markdown(
            '<div class="ml-chart-empty">No chart candles available</div>',
            unsafe_allow_html=True,
        )
        return

    df = pd.DataFrame(candles).copy()

    required = {"Time", "Open", "High", "Low", "Close"}
    if not required.issubset(df.columns):
        st.markdown(
            '<div class="ml-chart-empty">Chart fields unavailable</div>',
            unsafe_allow_html=True,
        )
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

    rows = [
        ("Scanner 1", 1, r1),
        ("Scanner 2", 2, r2),
        ("Scanner 3", 3, r3),
        ("Scanner 4", 4, r4),
    ]

    bias = _overall_direction(r1, r2, r3, r4)
    bias_color = {
        "Bullish": "#22C55E",
        "Bearish": "#FF3B4B",
        "Mixed": "#FACC15",
    }[bias]

    st.markdown(
        f"""
        <div class="ml-card">
            <div class="ml-card-title">{symbol}</div>

            <div style="
                display:flex;
                align-items:center;
                gap:28px;
                padding:6px 0 12px 0;
                margin-bottom:8px;
                border-bottom:1px solid rgba(255,255,255,0.08);
            ">
                <div>
                    <div style="font-size:11px;color:#8F9BAD;letter-spacing:.4px;">
                        RSI
                    </div>
                    <div style="font-size:19px;font-weight:700;color:#E8EDF5;">
                        {_value(r4, "RSI")}
                    </div>
                </div>

                <div>
                    <div style="font-size:11px;color:#8F9BAD;letter-spacing:.4px;">
                        VOLUME
                    </div>
                    <div style="font-size:19px;font-weight:700;color:#E8EDF5;">
                        {_value(r4, "Vol x Avg")}
                    </div>
                </div>
            </div>

            <div class="ml-header-row">
                <div class="ml-header-label"></div>
                <div class="ml-head">Score</div>
                <div class="ml-head">VOL / RSI</div>
                <div class="ml-head">Confidence / Consensus</div>
                <div class="ml-head">Direction</div>
            </div>
        """,
        unsafe_allow_html=True,
    )

    for scanner_name, scanner_number, result in rows:
        cell = _scanner_cell(scanner_number, result)
        direction = cell["direction"]
        direction_color = _direction_color(direction)

        confidence = cell["confidence"]
        confidence_label = ""
        confidence_color = "#A7B0C0"

        if confidence:
            confidence_label, confidence_color = _confidence_label(confidence)

        score = cell["score"]
        volume = cell["volume"]
        rsi = cell["rsi"]

        vol_rsi_html = ""
        if volume or rsi:
            vol_rsi_html = (
                f'<div class="ml-small-value">'
                f'<span>{volume}</span>'
                f'<span>{rsi}</span>'
                f'</div>'
            )

        if confidence:
            confidence_html = f"""
                <div class="ml-confidence-wrap">
                    {_consensus_ring(confidence)}
                    <div class="ml-confidence-text"
                         style="color:{confidence_color};">
                        {confidence_label}
                        <span>{confidence}</span>
                    </div>
                </div>
            """
        else:
            confidence_html = '<div class="ml-blank"></div>'

        st.markdown(
            f"""
            <div class="ml-scanner-row">
                <div class="ml-scanner-name">{scanner_name}</div>

                <div class="ml-score-cell">
                    <div class="ml-score">
                        {score if score else " "}
                    </div>
                    <div class="ml-score-line">
                        <span style="width:0%;"></span>
                    </div>
                </div>

                <div class="ml-vol-cell">
                    {vol_rsi_html}
                </div>

                <div class="ml-confidence-cell">
                    {confidence_html}
                </div>

                <div class="ml-direction"
                     style="color:{direction_color};">
                    {_direction_dot(direction)}
                    {direction}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="ml-bias-row">
            <span>Scanner Direction Summary</span>
            <strong style="color:{bias_color};">{bias}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_data = _get_chart(r3)

    st.markdown('<div class="ml-chart-box">', unsafe_allow_html=True)
    _render_mini_chart(
        chart_data,
        chart_key=f"grid-chart-{card_index}-{symbol}",
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if render_workspace is not None:
        if st.button(
            "🔎  Open Workspace",
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

    st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------

def render_grid_analysis(
    symbols: Sequence[str],
    s1: Mapping[str, Mapping[str, Any]],
    s2: Mapping[str, Mapping[str, Any]],
    s3: Mapping[str, Mapping[str, Any]],
    s4: Mapping[str, Mapping[str, Any]],
    render_workspace: Optional[Callable[..., Any]] = None,
) -> None:
    """
    Render the Market Lab multi-stock Grid Analysis.

    symbols:
        The user-selected universe, in the same order entered.

    s1/s2/s3/s4:
        Existing Market Lab scanner dictionaries indexed by symbol.

    render_workspace:
        Optional callback supplied by app.py. If provided, the button
        opens the existing Stock Selector workspace without duplicating
        that logic here.
    """

    st.markdown(
        """
        <style>
        .ml-card {
            background: linear-gradient(
                145deg,
                #0E1622 0%,
                #0A111B 100%
            );
            border: 1px solid #26364A;
            border-radius: 16px;
            padding: 16px;
            margin-bottom: 20px;
            box-shadow: 0 8px 28px rgba(0,0,0,0.22);
        }

        .ml-card-title {
            font-size: 25px;
            font-weight: 800;
            color: #F8FAFC;
            margin: 0 0 12px 4px;
        }

        .ml-header-row,
        .ml-scanner-row {
            display: grid;
            grid-template-columns:
                1.10fr
                0.90fr
                0.90fr
                1.20fr
                0.95fr;
            align-items: stretch;
        }

        .ml-head {
            background: #163B69;
            border: 1px solid #285A93;
            color: #F8FAFC;
            font-size: 14px;
            font-weight: 700;
            text-align: center;
            padding: 10px 5px;
        }

        .ml-header-label {
            background: transparent;
        }

        .ml-scanner-row {
            min-height: 72px;
            border-left: 1px solid #26364A;
            border-right: 1px solid #26364A;
            border-bottom: 1px solid #26364A;
        }

        .ml-scanner-row > div {
            border-right: 1px solid #26364A;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .ml-scanner-name {
            justify-content: flex-start !important;
            padding-left: 12px;
            color: #E7EEF8;
            font-size: 15px;
            font-weight: 600;
        }

        .ml-score-cell {
            flex-direction: column;
            padding: 6px 10px;
        }

        .ml-score {
            color: #F8FAFC;
            font-size: 20px;
            font-weight: 800;
            line-height: 1.15;
            min-height: 24px;
        }

        .ml-score-line {
            width: 86%;
            height: 5px;
            background: #303A46;
            border-radius: 10px;
            margin-top: 7px;
            overflow: hidden;
        }

        .ml-score-line span {
            display: block;
            height: 100%;
            background: #4ADE80;
            border-radius: 10px;
        }

        .ml-vol-cell {
            padding: 5px;
        }

        .ml-small-value {
            display: flex;
            flex-direction: column;
            gap: 4px;
            color: #D8E2F0;
            font-size: 13px;
            line-height: 1.15;
        }

        .ml-confidence-cell {
            padding: 5px;
        }

        .ml-confidence-wrap {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 7px;
        }

        .ml-ring {
            width: 47px;
            height: 47px;
            border-radius: 50%;
            background:
                conic-gradient(
                    var(--ring) var(--pct),
                    #384352 0
                );
            display: grid;
            place-items: center;
            position: relative;
            flex: 0 0 47px;
        }

        .ml-ring::before {
            content: "";
            position: absolute;
            inset: 5px;
            border-radius: 50%;
            background: #101824;
        }

        .ml-ring span {
            position: relative;
            z-index: 1;
            color: #F8FAFC;
            font-size: 11px;
            font-weight: 800;
        }

        .ml-empty-ring {
            display: none;
        }

        .ml-confidence-text {
            display: flex;
            flex-direction: column;
            font-size: 11px;
            font-weight: 800;
            line-height: 1.15;
        }

        .ml-confidence-text span {
            color: #AAB6C8;
            font-weight: 600;
            margin-top: 2px;
        }

        .ml-direction {
            font-size: 13px;
            font-weight: 800;
            white-space: nowrap;
        }

        .ml-blank {
            min-height: 1px;
        }

        .ml-bias-row {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 18px;
            border: 1px solid #26364A;
            border-radius: 8px;
            margin-top: 8px;
            padding: 9px 12px;
            color: #AEB9C9;
            font-size: 13px;
        }

        .ml-bias-row strong {
            font-size: 15px;
        }

        .ml-chart-box {
            border: 1px solid #26364A;
            border-radius: 10px;
            margin-top: 10px;
            padding: 4px 7px 0 7px;
            background: rgba(5,12,20,0.35);
        }

        .ml-chart-empty {
            height: 245px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #7F8CA0;
            font-size: 13px;
        }

        @media (max-width: 1100px) {
            .ml-header-row,
            .ml-scanner-row {
                grid-template-columns:
                    0.90fr
                    0.80fr
                    0.75fr
                    1.05fr
                    0.85fr;
            }

            .ml-head {
                font-size: 12px;
            }

            .ml-direction {
                font-size: 11px;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="
            margin-bottom:18px;
        ">
            <div style="
                font-size:32px;
                font-weight:800;
                color:#F8FAFC;
            ">
                📊 Grid Analysis
            </div>
            <div style="
                color:#93A4B8;
                font-size:15px;
                margin-top:3px;
            ">
                Real-time multi-scanner intelligence at a glance
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
