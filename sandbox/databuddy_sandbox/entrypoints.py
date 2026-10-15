"""
Fixed tool entrypoints called from FastAPI via E2B.

These are stubs that define the contract. Real pandas/statsmodels
implementations replace the bodies without changing the JSON shapes.
Official statistics are written only to /output/result.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

INPUT_DIR = Path("/input")
OUTPUT_DIR = Path("/output")


def _load_table(filename: str = "data.csv") -> pd.DataFrame:
    path = INPUT_DIR / filename
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _write_result(payload: dict[str, Any]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / "result.json"
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return out


def profile_table(filename: str = "data.csv") -> dict[str, Any]:
    """Read-only profile for exploratory analysis."""
    df = _load_table(filename)
    columns = []
    for name in df.columns:
        series = df[name]
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "missing": int(series.isna().sum()),
                "n_unique": int(series.nunique(dropna=True)),
            }
        )
    payload = {
        "tool": "profile_table",
        "n_rows": int(len(df)),
        "n_cols": int(df.shape[1]),
        "columns": columns,
    }
    _write_result(payload)
    return payload


def render_chart(
    chart_type: str,
    x: str,
    y: str | None = None,
    group: str | None = None,
    filename: str = "data.csv",
) -> dict[str, Any]:
    """
    Draw a named chart from docs/analytics-spec.md §4.
    Stub: validates columns and records the request. Real matplotlib later.
    """
    df = _load_table(filename)
    for col in (x, y, group):
        if col is not None and col not in df.columns:
            raise ValueError(f"Unknown column: {col}")
    payload = {
        "tool": "render_chart",
        "chart_type": chart_type,
        "x": x,
        "y": y,
        "group": group,
        "image_path": "/output/chart.png",
        "status": "stub_ok",
    }
    _write_result(payload)
    return payload


def run_comparison(method: str, outcome: str, predictor: str, **kwargs: Any) -> dict[str, Any]:
    """Fixed comparison/association tests. Stub records the request only."""
    df = _load_table()
    for col in (outcome, predictor):
        if col not in df.columns:
            raise ValueError(f"Unknown column: {col}")
    payload = {
        "tool": "run_comparison",
        "method": method,
        "outcome": outcome,
        "predictor": predictor,
        "params": kwargs,
        "status": "stub_ok",
        "result": None,
    }
    _write_result(payload)
    return payload


def run_regression(
    method: str,
    outcome: str,
    predictors: list[str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Fixed OLS / logistic. Stub records the request only."""
    df = _load_table()
    for col in [outcome, *predictors]:
        if col not in df.columns:
            raise ValueError(f"Unknown column: {col}")
    payload = {
        "tool": "run_regression",
        "method": method,
        "outcome": outcome,
        "predictors": predictors,
        "params": kwargs,
        "status": "stub_ok",
        "result": None,
    }
    _write_result(payload)
    return payload
