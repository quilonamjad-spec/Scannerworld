"""
Market Lab adapter for Scanner One.

IMPORTANT:
- This file is an integration layer only.
- It does NOT replace app.py.
- It does NOT change Scanner One's existing scan logic.
- The existing Scanner One Streamlit app remains untouched.

Purpose:
    Give Market Lab a clean, structured interface to Scanner One.

Flow:
    Market Lab
        ↓
    Scanner One Stage 1
        ↓
    Existing Quality Gate
        ↓
    Existing Ranking
        ↓
    Market Lab

The adapter does not calculate a new score.
It exposes the Rank / Rank Score already produced by Scanner One's
existing gate_rank.py logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


# --------------------------------------------------------------------------
# Timestamp handling
# --------------------------------------------------------------------------

def _normalise_timestamp(as_of: Any) -> datetime:
    """Convert common timestamp inputs into a timezone-aware IST datetime."""

    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")

    if isinstance(as_of, datetime):
        dt = as_of

    elif hasattr(as_of, "to_pydatetime"):
        dt = as_of.to_pydatetime()

    elif isinstance(as_of, str):
        value = as_of.strip()

        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                dt = None
        else:
            dt = None

        if dt is None:
            raise ValueError(
                "Invalid as_of timestamp. "
                "Use datetime or 'YYYY-MM-DD HH:MM'."
            )

    else:
        raise ValueError(
            "Invalid as_of timestamp. "
            "Use datetime or 'YYYY-MM-DD HH:MM'."
        )

    # Scanner One data is timezone-aware IST.
    # Interpret naive timestamps as IST.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)

    return dt


# --------------------------------------------------------------------------
# JSON conversion
# --------------------------------------------------------------------------

def _json_safe(value: Any) -> Any:
    """Convert common pandas/numpy values into JSON-safe Python values."""

    if value is None:
        return None

    # pandas Timestamp / datetime-like
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    # numpy scalar
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass

    # dictionaries
    if isinstance(value, dict):
        return {
            str(k): _json_safe(v)
            for k, v in value.items()
        }

    # lists / tuples
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]

    return value


# --------------------------------------------------------------------------
# DataFrame / result conversion
# --------------------------------------------------------------------------

def _records_from_result(result: Any) -> list[dict]:
    """
    Convert a Scanner One result into a list of dictionaries.

    The scanner normally returns a pandas DataFrame.
    This remains tolerant of list/dict results so the adapter does not
    unnecessarily constrain the underlying scanner.
    """

    if result is None:
        return []

    # pandas DataFrame
    if hasattr(result, "to_dict"):
        try:
            records = result.to_dict(orient="records")

            return [
                {
                    str(k): _json_safe(v)
                    for k, v in record.items()
                }
                for record in records
            ]

        except TypeError:
            pass

    # list of dictionaries
    if isinstance(result, list):
        output = []

        for item in result:
            if isinstance(item, dict):
                output.append(
                    {
                        str(k): _json_safe(v)
                        for k, v in item.items()
                    }
                )
            else:
                output.append(
                    {
                        "value": _json_safe(item)
                    }
                )

        return output

    # Single dictionary
    if isinstance(result, dict):
        return [
            {
                str(k): _json_safe(v)
                for k, v in result.items()
            }
        ]

    return [
        {
            "value": _json_safe(result)
        }
    ]


# --------------------------------------------------------------------------
# Scanner One imports
# --------------------------------------------------------------------------

def _find_scanner_functions():
    """
    Locate Scanner One's existing pipeline, quality gate and ranking
    functions.

    Scanner One's internal modules use direct imports such as:

        from config import ...
        from data import ...
        from gate_rank import ...

    Therefore scanner1/ must temporarily be on sys.path when Market Lab
    imports this adapter from the repository root.
    """

    import sys
    from pathlib import Path

    scanner_dir = Path(__file__).resolve().parent

    if str(scanner_dir) not in sys.path:
        sys.path.insert(0, str(scanner_dir))

    try:
        from scan_pipeline import run_scan_pipeline
        from gate_rank import quality_gate, rank_results
        from config import DEFAULT_WEIGHTS

        return (
            run_scan_pipeline,
            quality_gate,
            rank_results,
            DEFAULT_WEIGHTS,
        )

    except ImportError as exc:
        raise ImportError(
            "Could not import Scanner One's existing pipeline/gate/ranking "
            f"modules. Original error: {exc}"
        ) from exc


# --------------------------------------------------------------------------
# Market Lab entry point
# --------------------------------------------------------------------------

def run_market_lab_scan(
    symbols: Iterable[str],
    as_of: Any,
    lookback: int = 300,
    batch_size: int = 20,
) -> dict:
    """
    Run Scanner One through the Market Lab integration layer.

    Parameters
    ----------
    symbols:
        Iterable of ticker symbols, for example:

            ["INFY", "TCS", "RELIANCE"]

        Market Lab uses bare NSE symbols.

    as_of:
        datetime or string such as:

            "2026-08-21 13:55"

    lookback:
        Historical lookback value passed to Scanner One.

    batch_size:
        Existing Scanner One batch size.

    Returns
    -------
    dict
        JSON-serialisable Market Lab result containing:

        - Stage 1 results
        - Quality Gate rejected results
        - Quality Gate passed/ranked results
        - existing Rank
        - existing Rank Score
    """

    timestamp = _normalise_timestamp(as_of)

    # ------------------------------------------------------------------
    # Market Lab uses bare NSE symbols:
    #
    #     ADANIPOWER
    #     TCS
    #
    # Scanner One's existing pipeline expects Yahoo/NSE symbols:
    #
    #     ADANIPOWER.NS
    #     TCS.NS
    #
    # Normalize only at this integration boundary.
    # ------------------------------------------------------------------

    clean_symbols = []

    for symbol in symbols:
        value = str(symbol).strip().upper()

        if not value:
            continue

        if not value.endswith(".NS") and not value.endswith(".BO"):
            value = f"{value}.NS"

        if value not in clean_symbols:
            clean_symbols.append(value)

    if not clean_symbols:
        return {
            "status": "empty",
            "scanner": "scanner1",
            "as_of": timestamp.isoformat(),
            "symbols_requested": 0,
            "results": [],
            "ranked_results": [],
            "rejected_results": [],
        }

    # ------------------------------------------------------------------
    # Load Scanner One's EXISTING functions.
    #
    # No Scanner One calculation is duplicated here.
    # ------------------------------------------------------------------

    (
        run_scan_pipeline,
        quality_gate,
        rank_results,
        default_weights,
    ) = _find_scanner_functions()

    # ------------------------------------------------------------------
    # STAGE 1
    #
    # This is Scanner One's existing Stage-1 pipeline.
    # ------------------------------------------------------------------

    stage1_result = run_scan_pipeline(
        clean_symbols,
        as_of=timestamp,
        lookback_days=lookback,
        batch_size=batch_size,
        show_progress=False,
    )

    # Keep the original Stage-1 result exactly as Scanner One produced it.
    stage1_records = _records_from_result(stage1_result)

    # ------------------------------------------------------------------
    # QUALITY GATE
    #
    # These are the existing default gate values used by Scanner One's
    # own app when the user has not changed the sidebar settings.
    #
    # We are NOT creating new gate logic.
    # We are simply calling Scanner One's existing quality_gate().
    # ------------------------------------------------------------------

    gate_params = {
        "max_extension_atr": 2.5,
        "max_consecutive_bars": 6,
        "rsi_bull_min": 50,
        "rsi_bull_max": 78,
    }

    passed_df, rejected_df = quality_gate(
        stage1_result,
        gate_params,
    )

    # ------------------------------------------------------------------
    # RANKING
    #
    # This is Scanner One's EXISTING rank_results().
    #
    # We do not calculate Rank Score ourselves.
    # Rank Score comes directly from Scanner One.
    # ------------------------------------------------------------------

    if passed_df.empty:
        ranked_df = passed_df.copy()
    else:
        ranked_df = rank_results(
            passed_df,
            default_weights,
        )

    ranked_records = _records_from_result(ranked_df)
    rejected_records = _records_from_result(rejected_df)

    # ------------------------------------------------------------------
    # Normalize Symbol back to Market Lab's bare-symbol format.
    #
    # Scanner One may return:
    #
    #     ADANIPOWER.NS
    #
    # Market Lab indexes:
    #
    #     ADANIPOWER
    #
    # This changes only the display/index key, not Scanner One's logic.
    # ------------------------------------------------------------------

    def normalize_market_lab_symbol(record: dict) -> None:
        if not isinstance(record, dict):
            return

        symbol = record.get("Symbol")

        if not symbol:
            return

        record["Symbol"] = (
            str(symbol)
            .strip()
            .upper()
            .removesuffix(".NS")
            .removesuffix(".BO")
        )

    for record in stage1_records:
        normalize_market_lab_symbol(record)

    for record in ranked_records:
        normalize_market_lab_symbol(record)

    for record in rejected_records:
        normalize_market_lab_symbol(record)

    # ------------------------------------------------------------------
    # RETURN
    #
    # "results" remains the original Stage-1 output.
    #
    # "ranked_results" contains Scanner One's EXISTING ranking output,
    # including:
    #
    #     Rank
    #     Rank Score
    #
    # No new score is created here.
    # ------------------------------------------------------------------

    return {
        "status": "ok",
        "scanner": "scanner1",
        "as_of": timestamp.isoformat(),
        "symbols_requested": len(clean_symbols),

        # Existing Scanner One Stage-1 output
        "results_count": len(stage1_records),
        "results": stage1_records,

        # Existing Scanner One Stage-2 output
        "ranked_results_count": len(ranked_records),
        "ranked_results": ranked_records,

        # Existing Scanner One Quality Gate rejection output
        "rejected_results_count": len(rejected_records),
        "rejected_results": rejected_records,
    }


# --------------------------------------------------------------------------
# Health check
# --------------------------------------------------------------------------

def get_scanner1_health() -> dict:
    """
    Lightweight health check.

    Verifies that Scanner One's existing pipeline, quality gate and
    ranking functions can be imported without running a full scan.
    """

    try:
        (
            pipeline,
            quality_gate,
            rank_results,
            default_weights,
        ) = _find_scanner_functions()

        return {
            "status": "ok",
            "scanner": "scanner1",
            "pipeline_available": callable(pipeline),
            "quality_gate_available": callable(quality_gate),
            "ranking_available": callable(rank_results),
            "default_weights_available": bool(default_weights),
        }

    except Exception as exc:
        return {
            "status": "error",
            "scanner": "scanner1",
            "pipeline_available": False,
            "quality_gate_available": False,
            "ranking_available": False,
            "default_weights_available": False,
            "error": str(exc),
        }


# --------------------------------------------------------------------------
# Local test
# --------------------------------------------------------------------------

if __name__ == "__main__":
    print(get_scanner1_health())

    # Uncomment only when you want to perform a real scan:
    #
    # result = run_market_lab_scan(
    #     symbols=["ADANIPOWER"],
    #     as_of="2026-08-21 13:55",
    # )
    #
    # import json
    # print(json.dumps(result, indent=2, default=str))
