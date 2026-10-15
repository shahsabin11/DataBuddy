"""
Explicit tool surface from docs/analytics-spec.md and docs/threat-model.md.

Fixed tools call preloaded sandbox entrypoints. Free-form tools
(transform_frame, custom_plot) require student approval before execution.
This module only declares schemas; the sandbox runner wires them later.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProfileTableArgs(BaseModel):
    dataset_version_id: str


class ApplyConfirmedCleanArgs(BaseModel):
    dataset_version_id: str
    operation: Literal[
        "trim_whitespace",
        "drop_empty",
        "lossless_numeric_coerce",
        "listwise_delete",
        "impute_median_mode",
        "drop_outliers",
        "recode",
        "filter_rows",
        "drop_duplicates",
        "drop_column",
    ]
    params: dict[str, Any] = Field(default_factory=dict)


class RenderChartArgs(BaseModel):
    dataset_version_id: str
    chart_type: Literal[
        "histogram",
        "boxplot",
        "bar",
        "grouped_bar",
        "heatmap",
        "scatter",
    ]
    x: str
    y: str | None = None
    group: str | None = None


class RunComparisonArgs(BaseModel):
    dataset_version_id: str
    method: Literal[
        "welch_t",
        "student_t",
        "mann_whitney",
        "paired_t",
        "wilcoxon",
        "anova",
        "welch_anova",
        "kruskal",
        "chi_square",
        "fisher",
        "pearson",
        "spearman",
    ]
    outcome: str
    predictor: str
    alpha: float = 0.05
    alternative: Literal["two-sided", "greater", "less"] = "two-sided"


class RunRegressionArgs(BaseModel):
    dataset_version_id: str
    method: Literal["ols", "logistic"]
    outcome: str
    predictors: list[str] = Field(max_length=15)
    interaction: tuple[str, str] | None = None
    use_hc3: bool = False


class TransformFrameArgs(BaseModel):
    """Free-form pandas transform. Source must be student-approved."""

    dataset_version_id: str
    approved_source: str
    approval_id: str


class CustomPlotArgs(BaseModel):
    """Free-form matplotlib plot. Source must be student-approved."""

    dataset_version_id: str
    approved_source: str
    approval_id: str


# Names the LangGraph nodes may call. No open-ended "execute_python".
TOOL_NAMES = (
    "profile_table",
    "apply_confirmed_clean",
    "render_chart",
    "run_comparison",
    "run_regression",
    "transform_frame",
    "custom_plot",
)
