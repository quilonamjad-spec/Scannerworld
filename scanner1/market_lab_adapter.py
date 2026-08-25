"""
Market Lab adapter for Scanner One.

IMPORTANT:
- This file is an integration layer only.
- It does NOT replace app.py.
- It does NOT change Scanner One's existing scan logic.
- The existing Scanner One Streamlit app remains untouched.

Purpose:
    Give Market Lab a clean, structured interface to Scanner One.

Input:
    symbols
    as_of
    lookback
    batch_size

Output:
    JSON-serialisable dictionary containing:
        - scan timestamp
        - number scanned
        - candidates
        - ranked results

Usage from Python:

    from market_lab_adapter import run_market_lab_scan

    result = run_market_lab_scan(
        symbols=["INFY.NS", "TCS.NS"],
        as_of="2026-08-21 13:55",
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


def _normalise_timestamp(as_of: Any) -> datetime:
    """Convert common timestamp inputs into a datetime."""
    if isinstance(as_of, datetime):
        return as_of

    if hasattr(as_of, "to_pydatetime"):
        return as_of.to_pydatetime()

    if isinstance(as_of, str):
        value = as_of.strip()

        # Support the timestamp format used by Market Lab.
        for fmt in (
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                pass

    raise ValueError(
        "Invalid as_of timestamp. "
        "Use datetime or 'YYYY-MM-DD HH:MM'."
    )


def _json_safe(value: Any) -> Any:
    """Convert common pandas/numpy values into JSON-safe Python values."""

    if value is None:
        return None

    # pandas Timestamp
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


def _records_from_result(result: Any) -> list[dict]:
    """
    Convert the Scanner One result into a list of dictionaries.

    The scanner may return a pandas DataFrame or a list-like structure.
    We deliberately keep this adapter tolerant so the underlying scanner
    does not need to be rewritten.
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
                output.append({"value": _json_safe(item)})

        return output

    # Single dictionary
    if isinstance(result, dict):
        return [
            {
                str(k): _json_safe(v)
                for k, v in result.items()
            }
        ]

    return [{"value": _json_safe(result)}]


def _find_pipeline_function():
    """
    Locate Scanner One's existing pipeline function.

    We import the existing scanner module rather than copying its logic.
    """

    try:
        from scan_pipeline import run_scan_pipeline

        return run_scan_pipeline

    except ImportError as exc:
        raise ImportError(
            "Could not import Scanner One's scan_pipeline.py. "
            "Make sure market_lab_adapter.py is inside scanner1/"
            "and that the existing Scanner One modules are present."
        ) from exc


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
        Iterable of ticker symbols, e.g.
        ["INFY.NS", "TCS.NS", "RELIANCE.NS"]

    as_of:
        datetime or string such as:
        "2026-08-21 13:55"

    lookback:
        Number of historical candles required by Scanner One.

    batch_size:
        Existing Scanner One batch size.

    Returns
    -------
    dict
        JSON-serialisable Market Lab result.
    """

    timestamp = _normalise_timestamp(as_of)

    clean_symbols = [
        str(symbol).strip()
        for symbol in symbols
        if symbol and str(symbol).strip()
    ]

    if not clean_symbols:
        return {
            "status": "empty",
            "scanner": "scanner1",
            "as_of": timestamp.isoformat(),
            "symbols_requested": 0,
            "results": [],
        }

    run_scan_pipeline = _find_pipeline_function()

    # IMPORTANT:
    # We call Scanner One's existing pipeline.
    # No indicator or ranking logic is duplicated here.
    result = run_scan_pipeline(
        clean_symbols,
        as_of=timestamp,
        lookback_days=lookback,
        batch_size=batch_size,
        show_progress=False,
    )

    records = _records_from_result(result)

    return {
        "status": "ok",
        "scanner": "scanner1",
        "as_of": timestamp.isoformat(),
        "symbols_requested": len(clean_symbols),
        "results_count": len(records),
        "results": records,
    }


def get_scanner1_health() -> dict:
    """
    Lightweight health check.

    This lets Market Lab verify that Scanner One can be imported
    without running a full NSE 500 scan.
    """

    try:
        pipeline = _find_pipeline_function()

        return {
            "status": "ok",
            "scanner": "scanner1",
            "pipeline_available": callable(pipeline),
        }

    except Exception as exc:
        return {
            "status": "error",
            "scanner": "scanner1",
            "pipeline_available": False,
            "error": str(exc),
        }


if __name__ == "__main__":
    # Simple local test.
    print(get_scanner1_health())

    # Uncomment this only when you want to perform a real scan:
    #
    # result = run_market_lab_scan(
    #     symbols=["INFY.NS", "TCS.NS"],
    #     as_of="2026-08-21 13:55",
    # )
    #
    # import json
    # print(json.dumps(result, indent=2, default=str))
