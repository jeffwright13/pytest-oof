"""Streamlit dashboard for pytest-oof test analysis."""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pytest_oof.db import init_db

st.set_page_config(
    page_title="pytest-oof Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global Plotly theme settings for larger fonts
PLOTLY_LAYOUT = {
    "font": {"size": 15},  # 25% larger than default (12)
    "title_font_size": 20,
    "legend_font_size": 15,
    "xaxis_title_font_size": 15,
    "yaxis_title_font_size": 15,
}

# Global color definitions for test outcomes
OUTCOME_COLORS = {
    "total": "#4a90e2",  # Blue
    "passed": "#28a745",  # Green
    "failed": "#dc3545",  # Red
    "error": "#ff1493",  # Fuschia
    "skipped": "#6c757d",  # Grey
    "xfailed": "#90EE90",  # Light green
    "xpassed": "#FFE4B5",  # Light yellow
    "warnings": "#ffa500",  # Orange
}

# Define which outcomes should have white text for better contrast
WHITE_TEXT_OUTCOMES = ["failed", "error", "total"]

# Custom CSS
st.markdown(
    """
<style>
    /* Increase base font size by 50% */
    html {
        font-size: 150%;
    }

    /* Adjust metric containers */
    .stMetric .metric-container {
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-radius: 8px;
        padding: 10px;
        transition: transform 0.2s;
    }
    .stMetric .metric-container:hover {
        transform: translateY(-2px);
    }
    .metric-good { color: """
    + OUTCOME_COLORS["passed"]
    + """ !important; }
    .metric-bad { color: """
    + OUTCOME_COLORS["failed"]
    + """ !important; }
    .metric-neutral { color: """
    + OUTCOME_COLORS["skipped"]
    + """ !important; }

    /* Increase font size for specific elements */
    .stMarkdown h1 { font-size: 2.25em !important; }
    .stMarkdown h2 { font-size: 1.875em !important; }
    .stMarkdown h3 { font-size: 1.5em !important; }
    .stMarkdown h4 { font-size: 1.25em !important; }
    .stMarkdown p { font-size: 1.125em !important; }

    /* Adjust dataframe text size */
    .dataframe {
        font-size: 1.125em !important;
    }

    /* Adjust metric values */
    .stMetric .metric-value {
        font-size: 1.5em !important;
    }
    .stMetric .metric-label {
        font-size: 1.125em !important;
    }

    /* Adjust sidebar */
    .stSidebar .stMarkdown {
        font-size: 1.125em !important;
    }
    .stSidebar .stSelectbox, .stSidebar .stMultiSelect {
        font-size: 1.125em !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Update Streamlit theme for larger text
st.markdown(
    """
<style>
    .stMarkdown, .stText, .stTable, .stMetric {
        font-size: 1.25rem !important;
    }
    .stMarkdown h1 {
        font-size: 2.5rem !important;
    }
    .stMarkdown h2 {
        font-size: 2rem !important;
    }
    .stMarkdown h3 {
        font-size: 1.75rem !important;
    }
    .stMarkdown h4 {
        font-size: 1.5rem !important;
    }
    .stSelectbox, .stMultiSelect, .stDateInput {
        font-size: 1.25rem !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


def ensure_db_exists():
    """Ensure the database exists and is initialized."""
    db_path = Path("oof/oof-results.db")

    try:
        init_db(db_path)  # Always call init_db to ensure schema is up to date
    except Exception as e:
        st.error(f"Failed to initialize database: {str(e)}")
        raise

    return db_path


def format_datetime(dt):
    """Format datetime handling NaT values."""
    if pd.isna(dt):
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@st.cache_data(ttl=10)  # Cache data for 10 seconds
def load_session_data():
    """Load session data from the database."""
    db_path = ensure_db_exists()
    query = """
        SELECT
            id, start_time, stop_time as end_time, duration,
            sut_id, sut_type, sut_version, sut_env,
            num_tests, num_tests_without_rerun, num_tests_total,
            num_passes, num_failures, num_errors, num_skips,
            num_xfails, num_xpasses, num_reruns,
            num_rerun_groups, num_warnings, num_warnings_unique,
            num_deselected
        FROM test_sessions
        ORDER BY start_time DESC
    """

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["start_time", "end_time"])

            # Ensure timezone awareness
            if df["start_time"].dt.tz is None:
                df["start_time"] = df["start_time"].dt.tz_localize("UTC")
            if df["end_time"].dt.tz is None:
                df["end_time"] = df["end_time"].dt.tz_localize("UTC")

            # Fill NaN/None values and convert to native types
            df["sut_id"] = df["sut_id"].fillna("")
            df["sut_type"] = df["sut_type"].fillna("")
            df["sut_version"] = df["sut_version"].fillna("")
            df["sut_env"] = df["sut_env"].fillna("")
            df["duration"] = df["duration"].fillna(0).astype(float)

            # Convert numeric columns to native Python int
            int_columns = [
                "num_tests", "num_tests_without_rerun", "num_tests_total",
                "num_passes", "num_failures", "num_errors", "num_skips",
                "num_xfails", "num_xpasses", "num_reruns",
                "num_rerun_groups", "num_warnings", "num_warnings_unique",
                "num_deselected"
            ]
            for col in int_columns:
                df[col] = df[col].fillna(0).astype("int32").astype(int)

            # Calculate metrics
            df["pass_rate"] = (df["num_passes"] / df["num_tests"] * 100).fillna(0).astype(float)
            df["rerun_rate"] = (df["num_reruns"] / df["num_tests"] * 100).fillna(0).astype(float)
            df["warning_rate"] = (df["num_warnings"] / df["num_tests"] * 100).fillna(0).astype(float)

            return df
    except Exception as e:
        st.error(f"Error loading session data: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error


@st.cache_data(ttl=10)  # Cache data for 10 seconds
def load_test_results():
    """Load test results data from the database."""
    db_path = ensure_db_exists()
    query = """
        SELECT
            tr.id,
            tr.session_id,
            tr.nodeid,
            tr.outcome,
            tr.start_time,
            tr.duration,
            tr.error_message,
            tr.error_type,
            tr.has_warning,
            tr.rerun_count,
            ts.sut_id,
            ts.sut_type,
            ts.sut_version,
            ts.sut_env
        FROM test_results tr
        JOIN test_sessions ts ON tr.session_id = ts.id
        ORDER BY tr.start_time DESC
    """

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["start_time"])

            # Ensure timezone awareness
            if df["start_time"].dt.tz is None:
                df["start_time"] = df["start_time"].dt.tz_localize("UTC")

            # Fill NaN/None values
            df["sut_id"] = df["sut_id"].fillna("")
            df["sut_type"] = df["sut_type"].fillna("")
            df["sut_version"] = df["sut_version"].fillna("")
            df["sut_env"] = df["sut_env"].fillna("")
            df["error_message"] = df["error_message"].fillna("")
            df["error_type"] = df["error_type"].fillna("")
            df["duration"] = df["duration"].fillna(0).astype(float)
            df["rerun_count"] = df["rerun_count"].fillna(0).astype(int)
            df["has_warning"] = df["has_warning"].fillna(False)

            return df
    except Exception as e:
        st.error(f"Error loading test results: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error


def plot_test_results_trend(df, viz_settings, view_type="aggregate"):
    """Plot test results trend over time."""
    df_sorted = df.sort_values("start_time")
    fig = go.Figure()

    if view_type == "aggregate":
        # Original aggregate view
        metrics = [
            ("num_passes", "Passed", "passed"),
            ("num_failures", "Failed", "failed"),
            ("num_errors", "Errors", "error"),
            ("num_skips", "Skipped", "skipped"),
            ("num_xfails", "Expected Failures", "xfailed"),
            ("num_xpasses", "Unexpected Passes", "xpassed"),
        ]

        for metric, name, color in metrics:
            fig.add_trace(
                go.Scatter(
                    x=df_sorted["start_time"],
                    y=df_sorted[metric],
                    name=name,
                    mode="lines+markers" if viz_settings["show_markers"] else "lines",
                    line=dict(
                        color=OUTCOME_COLORS[color],
                        width=viz_settings["line_width"],
                        shape=viz_settings["line_shape"],
                    ),
                )
            )

    elif view_type == "by_sut":
        # Show each SUT with different line styles
        metrics = [
            ("num_passes", "Passed", "passed"),
            ("num_failures", "Failed", "failed"),
            ("num_errors", "Errors", "error"),
        ]
        line_styles = ["solid", "dot", "dash", "dashdot"]

        for sut_id in sorted(df_sorted["sut_id"].unique()):
            sut_data = df_sorted[df_sorted["sut_id"] == sut_id]
            style_idx = 0
            for metric, name, color in metrics:
                fig.add_trace(
                    go.Scatter(
                        x=sut_data["start_time"],
                        y=sut_data[metric],
                        name=f"{sut_id} - {name}",
                        mode="lines+markers" if viz_settings["show_markers"] else "lines",
                        line=dict(
                            color=OUTCOME_COLORS[color],
                            width=viz_settings["line_width"],
                            dash=line_styles[style_idx % len(line_styles)],
                        ),
                        legendgroup=sut_id,
                    )
                )
            style_idx += 1

    elif view_type == "stacked":
        # Stacked area chart showing contribution of each SUT
        metrics = [
            ("num_passes", "Passed", "passed"),
            ("num_failures", "Failed", "failed"),
            ("num_errors", "Errors", "error"),
        ]

        for metric, name, color in metrics:
            for sut_id in sorted(df_sorted["sut_id"].unique()):
                sut_data = df_sorted[df_sorted["sut_id"] == sut_id]
                fig.add_trace(
                    go.Scatter(
                        x=sut_data["start_time"],
                        y=sut_data[metric],
                        name=f"{sut_id} - {name}",
                        mode="none",
                        stackgroup=name,  # Stack by metric type
                        fillcolor=OUTCOME_COLORS[color],
                        line=dict(width=0),
                        legendgroup=name,
                    )
                )

    # Update layout
    fig.update_layout(
        title="Test Results Trend",
        xaxis_title="Time",
        yaxis_title="Count",
        hovermode="x unified",
        legend=dict(
            groupclick="toggleitem",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        **PLOTLY_LAYOUT,
    )

    return fig


def plot_sut_pass_fail_trend(df, sut_id, viz_settings):
    """Plot pass/fail rate trend for a specific SUT."""
    df_sut = df[df["sut_id"] == sut_id].sort_values("start_time")

    fig = go.Figure()

    # Calculate pass rate for each session
    df_sut["pass_rate"] = df_sut["num_passes"] / df_sut["num_tests"] * 100
    df_sut["fail_rate"] = 100 - df_sut["pass_rate"]

    # Add pass rate line
    fig.add_trace(
        go.Scatter(
            x=df_sut["start_time"],
            y=df_sut["pass_rate"],
            name="Pass Rate",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS["passed"],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
            ),
        )
    )

    # Add fail rate line
    fig.add_trace(
        go.Scatter(
            x=df_sut["start_time"],
            y=df_sut["fail_rate"],
            name="Fail Rate",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS["failed"],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
            ),
        )
    )

    fig.update_layout(
        title=f"Pass/Fail Rate Trend for {sut_id}",
        xaxis_title="Time",
        yaxis_title="Rate (%)",
        yaxis_range=[0, 100],
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


def identify_test_transitions(
    df, lookback_window=7, min_runs=5, failure_threshold=0.8, success_threshold=0.8
):
    """
    Identify tests that have transitioned from failing to passing or vice versa.

    Args:
        df: DataFrame with test results
        lookback_window: Number of days to look back for transitions
        min_runs: Minimum number of runs required to consider a transition
        failure_threshold: Percentage of failures required to consider a test as failing
        success_threshold: Percentage of successes required to consider a test as passing

    Returns:
        tuple: (fail_to_pass_df, pass_to_fail_df) DataFrames containing the transitions
    """
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Convert thresholds to decimals if they're percentages
    failure_threshold = (
        failure_threshold if failure_threshold <= 1 else failure_threshold / 100
    )
    success_threshold = (
        success_threshold if success_threshold <= 1 else success_threshold / 100
    )

    # Calculate the cutoff date
    latest_date = df["start_time"].max()
    cutoff_date = latest_date - pd.Timedelta(days=lookback_window)

    # Filter data within the lookback window
    recent_df = df[df["start_time"] >= cutoff_date].copy()

    # Initialize lists to store transitions
    fail_to_pass = []
    pass_to_fail = []

    # Group by test_id and analyze each test's history
    for test_id in recent_df["id"].unique():
        test_runs = recent_df[recent_df["id"] == test_id].sort_values(
            "start_time", ascending=True
        )

        if len(test_runs) < min_runs:
            continue

        # Get the most recent outcome
        latest_run = test_runs.iloc[-1]
        latest_outcome = latest_run["outcome"]

        # Get previous N runs
        previous_runs = test_runs.iloc[:-1].tail(min_runs)
        if len(previous_runs) < min_runs - 1:
            continue

        # Calculate failure and success rates
        failure_count = len(
            previous_runs[previous_runs["outcome"].isin(["failed", "error"])]
        )
        success_count = len(previous_runs[previous_runs["outcome"] == "passed"])
        total_runs = len(previous_runs)

        failure_rate = failure_count / total_runs
        success_rate = success_count / total_runs

        # Store previous outcomes for visualization
        previous_outcomes = previous_runs["outcome"].tolist()

        # Check for transitions
        if latest_outcome == "passed" and failure_rate >= failure_threshold:
            fail_to_pass.append(
                {
                    "id": test_id,
                    "last_run_time": latest_run["start_time"],
                    "num_previous_runs": total_runs,
                    "previous_fail_rate": failure_rate * 100,
                    "previous_outcomes": str(previous_outcomes),
                }
            )
        elif (
            latest_outcome in ["failed", "error"] and success_rate >= success_threshold
        ):
            pass_to_fail.append(
                {
                    "id": test_id,
                    "last_run_time": latest_run["start_time"],
                    "num_previous_runs": total_runs,
                    "previous_pass_rate": success_rate * 100,
                    "previous_outcomes": str(previous_outcomes),
                }
            )

    # Convert to DataFrames
    fail_to_pass_df = pd.DataFrame(fail_to_pass)
    pass_to_fail_df = pd.DataFrame(pass_to_fail)

    return fail_to_pass_df, pass_to_fail_df


def identify_flaky_tests(df, min_runs=5, flaky_threshold=0.2):
    """
    Identify flaky tests based on their pass/fail patterns.

    Args:
        df: DataFrame with test results
        min_runs: Minimum number of runs required to consider a test
        flaky_threshold: Threshold for considering a test flaky (0.2 means at least 20% passes AND at least 20% fails)

    Returns:
        DataFrame with flaky test information
    """
    flaky_tests = []

    # Group by test_id and analyze patterns
    for test_id, group in df.groupby("id"):
        total_runs = len(group)
        if total_runs < min_runs:
            continue

        # Count different outcomes
        outcome_counts = group["outcome"].value_counts()
        total_outcomes = sum(outcome_counts)

        # Calculate rates for different outcomes
        pass_rate = outcome_counts.get("passed", 0) / total_outcomes
        fail_rate = (
            outcome_counts.get("failed", 0) + outcome_counts.get("error", 0)
        ) / total_outcomes

        # A test is considered flaky if it has significant pass AND fail rates
        if pass_rate >= flaky_threshold and fail_rate >= flaky_threshold:
            suts_affected = group["sut_id"].nunique()
            last_seen = group["start_time"].max()
            first_seen = group["start_time"].min()
            duration = (
                last_seen - first_seen
            ).total_seconds() / 86400  # Convert to days

            flaky_tests.append(
                {
                    "id": test_id,
                    "total_runs": total_runs,
                    "pass_rate": pass_rate * 100,  # Convert to percentage
                    "fail_rate": fail_rate * 100,  # Convert to percentage
                    "suts_affected": suts_affected,
                    "last_seen": last_seen,
                    "first_seen": first_seen,
                    "duration_days": round(duration, 1),
                }
            )

    if not flaky_tests:
        return pd.DataFrame(
            columns=[
                "id",
                "total_runs",
                "pass_rate",
                "fail_rate",
                "suts_affected",
                "last_seen",
                "first_seen",
                "duration_days",
            ]
        )

    return pd.DataFrame(flaky_tests).sort_values("total_runs", ascending=False)


def plot_daily_stats(df):
    """Plot daily statistics."""
    if df.empty:
        return None

    # Create date column from start_time
    df = df.copy()
    df["date"] = df["start_time"].dt.date

    # Calculate daily statistics
    daily_stats = (
        df.groupby("date")
        .agg(
            {
                "num_tests": "sum",
                "num_passes": "sum",
                "num_failures": "sum",
                "num_errors": "sum",
                "num_skips": "sum",
                "num_xfails": "sum",
                "num_xpasses": "sum",
            }
        )
        .reset_index()
    )

    daily_stats["pass_rate"] = (
        daily_stats["num_passes"] / daily_stats["num_tests"] * 100
    )
    daily_stats["failure_rate"] = (
        (daily_stats["num_failures"] + daily_stats["num_errors"])
        / daily_stats["num_tests"]
        * 100
    )

    # Create figure
    fig = go.Figure()

    # Add pass rate trace
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["pass_rate"],
            name="Pass Rate",
            mode="lines+markers",
            line=dict(color=OUTCOME_COLORS["passed"], width=2),
        )
    )

    # Add failure rate trace
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["failure_rate"],
            name="Failure Rate",
            mode="lines+markers",
            line=dict(color=OUTCOME_COLORS["failed"], width=2),
        )
    )

    # Add total tests trace on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["num_tests"],
            name="Total Tests",
            mode="lines+markers",
            line=dict(color=OUTCOME_COLORS["total"], width=2),
            yaxis="y2",
        )
    )

    # Update layout
    fig.update_layout(
        title="Daily Test Statistics",
        xaxis_title="Date",
        yaxis=dict(title="Pass/Fail Rate (%)", range=[0, 100], tickformat=".1f"),
        yaxis2=dict(title="Total Tests", overlaying="y", side="right"),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


def plot_metric_trends(df, metrics):
    """Plot trends for multiple metrics."""
    fig = go.Figure()

    df_sorted = df.sort_values("start_time")
    df_sorted['start_time'] = df_sorted['start_time'].dt.tz_localize(None)  # Remove timezone info
    for metric, label, color in metrics:
        fig.add_trace(
            go.Scatter(
                x=df_sorted["start_time"],
                y=df_sorted[metric],
                name=label,
                mode="lines+markers",
                line=dict(color=OUTCOME_COLORS[color], width=2),
            )
        )

    fig.update_layout(
        title="Test Metrics Over Time",
        xaxis_title="Time",
        yaxis_title="Count",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


def plot_test_transitions(fail_to_pass, pass_to_fail):
    """Create a visualization of test transitions."""
    st.markdown("### Test State Transitions")

    if fail_to_pass.empty and pass_to_fail.empty:
        st.info("No test transitions detected with current settings.")
        return

    # Combine transitions into one dataframe
    transitions = []

    for _, row in fail_to_pass.iterrows():
        transitions.append(
            {
                "id": row["id"],
                "transition": "Fail → Pass",
                "last_run_time": row["last_run_time"],
                "previous_outcomes": row.get("previous_outcomes", []),
                "percentage": row.get("previous_fail_rate", 0),
            }
        )

    for _, row in pass_to_fail.iterrows():
        transitions.append(
            {
                "id": row["id"],
                "transition": "Pass → Fail",
                "last_run_time": row["last_run_time"],
                "previous_outcomes": row.get("previous_outcomes", []),
                "percentage": row.get("previous_pass_rate", 0),
            }
        )

    if not transitions:
        st.info("No test transitions detected with current settings.")
        return

    df = pd.DataFrame(transitions)

    # Create timeline visualization
    fig = px.timeline(
        df,
        x_start="last_run_time",
        x_end="last_run_time",
        y="id",
        color="transition",
        color_discrete_map={
            "Fail → Pass": OUTCOME_COLORS["passed"],
            "Pass → Fail": OUTCOME_COLORS["failed"],
        },
        title="Test Transitions Timeline",
        labels={"id": "Test", "last_run_time": "Transition Time"},
    )

    fig.update_layout(
        showlegend=True,
        xaxis_title="Time",
        yaxis_title="Test ID",
        height=max(300, len(df) * 30),  # Adjust height based on number of tests
    )

    # Add hover text with previous outcomes
    fig.update_traces(
        hovertemplate="<b>%{y}</b><br>"
        + "Time: %{x}<br>"
        + "Transition: %{customdata[0]}<br>"
        + "Previous Outcomes: %{customdata[1]}<br>"
        + "Percentage: %{customdata[2]:.1f}%<extra></extra>",
        customdata=df[["transition", "previous_outcomes", "percentage"]].values,
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show detailed transition information in an expandable section
    with st.expander("View Detailed Transition Information"):
        for t in transitions:
            st.markdown(
                f"""
            **{t['id']}** ({t['transition']})
            - Time: {t['last_run_time']}
            - Previous Outcomes: {', '.join(t['previous_outcomes'])}
            - {'Fail' if 'previous_fail_rate' in t else 'Pass'} Rate: {t['percentage']:.1f}%
            """
            )


def analyze_rerun_patterns(df):
    """
    Analyze test rerun patterns and create visualizations.

    Args:
        df: DataFrame with test results including rerun information

    Returns:
        tuple: (rerun_stats_fig, rerun_outcomes_fig) - Plotly figures for rerun statistics
    """
    if df.empty or "rerun_count" not in df.columns:
        return None, None

    # Calculate rerun statistics
    rerun_df = df[df["rerun_count"] > 0]
    if rerun_df.empty:
        return None, None

    rerun_stats = rerun_df.agg(
        {"rerun_count": ["count", "mean", "max"], "total_rerun_time": ["sum", "mean"]}
    ).round(2)

    # Create rerun stats figure
    rerun_stats_fig = go.Figure()
    rerun_stats_fig.add_trace(
        go.Indicator(
            mode="number",
            value=rerun_stats["rerun_count"]["count"],
            title="Tests with Reruns",
            domain={"row": 0, "column": 0},
        )
    )
    rerun_stats_fig.add_trace(
        go.Indicator(
            mode="number",
            value=rerun_stats["rerun_count"]["mean"],
            title="Avg Reruns per Test",
            number={"valueformat": ".2f"},
            domain={"row": 0, "column": 1},
        )
    )
    rerun_stats_fig.add_trace(
        go.Indicator(
            mode="number",
            value=rerun_stats["total_rerun_time"]["sum"],
            title="Total Rerun Time (s)",
            number={"valueformat": ".2f"},
            domain={"row": 1, "column": 0},
        )
    )
    rerun_stats_fig.add_trace(
        go.Indicator(
            mode="number",
            value=rerun_stats["total_rerun_time"]["mean"],
            title="Avg Rerun Time per Test (s)",
            number={"valueformat": ".2f"},
            domain={"row": 1, "column": 1},
        )
    )

    rerun_stats_fig.update_layout(
        grid={"rows": 2, "columns": 2}, height=400, **PLOTLY_LAYOUT
    )

    # Analyze rerun outcomes
    rerun_outcomes = []
    for _, row in rerun_df.iterrows():
        try:
            if pd.isna(row["rerun_outcomes"]) or row["rerun_outcomes"] == "[]":
                continue
            outcomes = eval(row["rerun_outcomes"])  # Convert string list to actual list
            for i, outcome in enumerate(outcomes, 1):
                rerun_outcomes.append(
                    {"id": row["id"], "rerun_number": i, "outcome": outcome}
                )
        except (ValueError, SyntaxError):
            continue

    rerun_outcomes_df = pd.DataFrame(rerun_outcomes)

    # Create rerun outcomes figure
    if not rerun_outcomes_df.empty:
        outcome_counts = (
            rerun_outcomes_df.groupby(["rerun_number", "outcome"])
            .size()
            .unstack(fill_value=0)
        )

        rerun_outcomes_fig = go.Figure()
        for outcome in outcome_counts.columns:
            rerun_outcomes_fig.add_trace(
                go.Bar(
                    name=outcome,
                    x=outcome_counts.index,
                    y=outcome_counts[outcome],
                    marker_color=OUTCOME_COLORS.get(outcome.lower(), "#808080"),
                )
            )

        rerun_outcomes_fig.update_layout(
            barmode="stack",
            title="Test Outcomes by Rerun Number",
            xaxis_title="Rerun Number",
            yaxis_title="Number of Tests",
            height=400,
            **PLOTLY_LAYOUT,
        )
    else:
        rerun_outcomes_fig = None

    return rerun_stats_fig, rerun_outcomes_fig


def create_3d_test_surface(df, metric="failures", smoothing=0.0, colorscale="viridis"):
    """Create a 3D surface plot showing test metrics across SUTs and time."""
    if df.empty:
        return None

    # Prepare data based on metric
    daily_stats = df.copy()
    daily_stats["date"] = pd.to_datetime(daily_stats["start_time"]).dt.date

    if metric == "failures":
        daily_stats["count"] = daily_stats["num_failures"] + daily_stats["num_errors"]
    elif metric == "passes":
        daily_stats["count"] = daily_stats["num_passes"]
    elif metric == "flaky":
        daily_stats["count"] = daily_stats["num_xpasses"] + daily_stats["num_xfails"]
    else:  # new_failures - this will show total failures for now
        daily_stats["count"] = daily_stats["num_failures"]

    # Group by date and SUT
    daily_stats = daily_stats.groupby(["sut_id", "date"])["count"].sum().reset_index()

    # Create pivot table
    pivot_table = daily_stats.pivot(
        index="date", columns="sut_id", values="count"
    ).fillna(0)

    # Create surface plot
    fig = go.Figure(
        data=[
            go.Surface(
                z=pivot_table.values,
                x=pivot_table.columns,  # SUTs
                y=[str(d) for d in pivot_table.index],  # Dates
                colorscale=colorscale,
            )
        ]
    )

    # Update layout
    fig.update_layout(
        title=f"Test {metric.title()} Surface",
        scene=dict(
            xaxis_title="SUT ID", yaxis_title="Date", zaxis_title=metric.title()
        ),
        **PLOTLY_LAYOUT,
    )

    return fig


def create_test_heatmap(df, metric="failures", colorscale="viridis"):
    """Create a heatmap showing test metrics across SUTs and time."""
    if df.empty:
        return None

    # Prepare data based on metric
    daily_stats = df.copy()
    daily_stats["date"] = pd.to_datetime(daily_stats["start_time"]).dt.date

    if metric == "failures":
        daily_stats["count"] = daily_stats["num_failures"] + daily_stats["num_errors"]
    elif metric == "passes":
        daily_stats["count"] = daily_stats["num_passes"]
    elif metric == "flaky":
        daily_stats["count"] = daily_stats["num_xpasses"] + daily_stats["num_xfails"]
    else:  # new_failures - this will show total failures for now
        daily_stats["count"] = daily_stats["num_failures"]

    # Group by date and SUT
    daily_stats = daily_stats.groupby(["sut_id", "date"])["count"].sum().reset_index()

    # Create pivot table
    pivot_table = daily_stats.pivot(
        index="date", columns="sut_id", values="count"
    ).fillna(0)

    # Create heatmap
    fig = go.Figure(
        data=go.Heatmap(
            z=pivot_table.values,
            x=pivot_table.columns,  # SUTs
            y=[str(d) for d in pivot_table.index],  # Dates
            colorscale=colorscale,
            hoverongaps=False,
        )
    )

    # Update layout
    fig.update_layout(
        title=f"Test {metric.title()} Heatmap",
        xaxis_title="SUT ID",
        yaxis_title="Date",
        **PLOTLY_LAYOUT,
    )

    return fig


def create_test_scatter(df, metric="failures", colorscale="viridis"):
    """Create a 3D scatter plot showing test metrics across SUTs and time."""
    if df.empty:
        return None

    # Prepare data based on metric
    daily_stats = df.copy()
    daily_stats["date"] = pd.to_datetime(daily_stats["start_time"]).dt.date

    if metric == "failures":
        daily_stats["count"] = daily_stats["num_failures"] + daily_stats["num_errors"]
    elif metric == "passes":
        daily_stats["count"] = daily_stats["num_passes"]
    elif metric == "flaky":
        daily_stats["count"] = daily_stats["num_xpasses"] + daily_stats["num_xfails"]
    else:  # new_failures - this will show total failures for now
        daily_stats["count"] = daily_stats["num_failures"]

    # Group by date and SUT
    daily_stats = daily_stats.groupby(["sut_id", "date"])["count"].sum().reset_index()

    # Create 3D scatter plot
    fig = go.Figure(
        data=[
            go.Scatter3d(
                x=daily_stats["sut_id"],
                y=[str(d) for d in daily_stats["date"]],
                z=daily_stats["count"],
                mode="markers",
                marker=dict(
                    size=6,
                    color=daily_stats["count"],
                    colorscale=colorscale,
                    opacity=0.8,
                ),
                hovertemplate="<b>SUT</b>: %{x}<br>"
                + "<b>Date</b>: %{y}<br>"
                + f"<b>{metric.title()}</b>: %{{z}}<br>",
            )
        ]
    )

    # Update layout
    fig.update_layout(
        title=f"Test {metric.title()} 3D Scatter",
        scene=dict(
            xaxis_title="SUT ID", yaxis_title="Date", zaxis_title=metric.title()
        ),
        **PLOTLY_LAYOUT,
    )

    return fig


# Load data first
df = load_session_data()
test_results_df = load_test_results()

# Common settings in sidebar
with st.sidebar:
    st.markdown("### Data Settings")
    selected_sut = st.selectbox(
        "Select SUT",
        ["All SUTs"] + sorted(df["sut_id"].unique().tolist()),
        key="sut_selector",
    )

# Filter data based on selected SUT
df_sut = df if selected_sut == "All SUTs" else df[df["sut_id"] == selected_sut]
test_results_df_sut = test_results_df if selected_sut == "All SUTs" else test_results_df[test_results_df["sut_id"] == selected_sut]

# Main content with tabs
st.title("pytest-oof Test Analysis")
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
    [
        "Overview",
        "Session View",
        "Session Details",
        "Session Comparison",
        "Test Transitions",
        "Rerun Analysis",
        "Flaky Tests",
        "3D Visualization",
    ]
)

with tab1:
    st.header("Overview")

    # Add view type selector
    view_type = st.radio(
        "View Type",
        ["Aggregate Stats", "By SUT", "Stacked Area"],
        horizontal=True,
        help=(
            "Aggregate: Show total stats across all SUTs\n"
            "By SUT: Show each SUT with different line styles\n"
            "Stacked Area: Show contribution of each SUT"
        ),
    )

    st.subheader("Test Results Trend")
    trend_fig = plot_test_results_trend(
        df_sut,
        {"show_markers": True, "line_width": 2, "line_shape": "linear"},
        view_type=view_type.lower().replace(" ", "_")
    )
    if trend_fig:
        st.plotly_chart(trend_fig, use_container_width=True)

with tab2:
    st.header("Session View")
    daily_stats_fig = plot_daily_stats(df_sut)
    if daily_stats_fig:
        st.plotly_chart(daily_stats_fig, use_container_width=True)

with tab3:
    st.header("Session Details")
    if not df_sut.empty:
        st.dataframe(
            df_sut[["start_time", "sut_id", "num_tests", "num_passes", "num_failures", "num_errors", "duration"]],
            use_container_width=True
        )
    else:
        st.info("No session data available for the selected SUT.")

with tab4:
    st.header("Session Comparison")
    if len(df_sut) >= 2:
        # st.write("Debug - DataFrame columns:", df_sut.columns.tolist())
        metrics = [
            ("num_tests", "Total Tests", "total"),
            ("num_passes", "Passes", "passed"),
            ("num_failures", "Failures", "failed"),
            ("num_errors", "Errors", "error"),
        ]
        metric_fig = plot_metric_trends(df_sut, metrics)
        if metric_fig:
            st.plotly_chart(metric_fig, use_container_width=True)
    else:
        st.info("Need at least 2 sessions to compare.")

with tab5:
    st.header("Test Transitions")
    # st.write("Debug - Test Results DataFrame columns:", test_results_df_sut.columns.tolist())
    fail_to_pass, pass_to_fail = identify_test_transitions(test_results_df_sut)
    transitions_fig = plot_test_transitions(fail_to_pass, pass_to_fail)
    if transitions_fig:
        st.plotly_chart(transitions_fig, use_container_width=True)

with tab6:
    st.header("Rerun Analysis")
    if not test_results_df_sut.empty:
        rerun_stats_fig, rerun_outcomes_fig = analyze_rerun_patterns(test_results_df_sut)
        if rerun_stats_fig:
            st.plotly_chart(rerun_stats_fig, use_container_width=True)
        if rerun_outcomes_fig:
            st.plotly_chart(rerun_outcomes_fig, use_container_width=True)
    else:
        st.info("No rerun data available for the selected SUT.")

with tab7:
    st.header("Flaky Tests")
    if not test_results_df_sut.empty:
        flaky_tests = identify_flaky_tests(test_results_df_sut)
        if not flaky_tests.empty:
            st.dataframe(flaky_tests, use_container_width=True)
        else:
            st.info("No flaky tests identified for the selected SUT.")
    else:
        st.info("No test data available for the selected SUT.")

with tab8:
    st.header("3D Test Result Visualization")

    col1, col2 = st.columns(2)
    with col1:
        metric = st.selectbox(
            "Select Metric to Visualize",
            ["failures", "flaky", "new_failures", "passes"],
            help="Choose which test metric to visualize across SUTs and time",
        )

        view_mode = st.selectbox(
            "View Mode",
            ["surface", "heatmap", "scatter"],
            help="Choose how to visualize the data",
        )

    with col2:
        smoothing = st.slider(
            "Smoothing Factor",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.1,
            help="Apply smoothing to the surface (0 = none, 1 = maximum)",
        )

        color_scale = st.selectbox(
            "Color Scale",
            ["Viridis", "Plasma", "Inferno", "Magma", "RdYlBu"],
            help="Choose the color scheme for the visualization",
        )

    # Create date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            value=pd.to_datetime(df["start_time"]).min().date(),
            min_value=pd.to_datetime(df["start_time"]).min().date(),
            max_value=pd.to_datetime(df["start_time"]).max().date(),
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            value=pd.to_datetime(df["start_time"]).max().date(),
            min_value=pd.to_datetime(df["start_time"]).min().date(),
            max_value=pd.to_datetime(df["start_time"]).max().date(),
        )

    # Filter data by date range and add date column
    filtered_df = df.copy()
    filtered_df["date"] = pd.to_datetime(filtered_df["start_time"]).dt.date
    mask = (filtered_df["date"] >= start_date) & (filtered_df["date"] <= end_date)
    filtered_df = filtered_df[mask]

    if not filtered_df.empty:
        # with st.expander("Debug Information", expanded=False):
        #     st.write(f"Total rows: {len(filtered_df)}")
        #     st.write(f"Unique SUTs: {filtered_df['sut_id'].nunique()}")
        #     st.write(
        #         f"Date range: {filtered_df['date'].min()} to {filtered_df['date'].max()}"
        #     )
        #     st.write(f"Selected metric: {metric}")
        #     st.write("DataFrame columns:", filtered_df.columns.tolist())

        #     # Show sample of aggregated data
        #     daily_stats = filtered_df.copy()
        #     if metric == "failures":
        #         daily_stats["count"] = (
        #             daily_stats["num_failures"] + daily_stats["num_errors"]
        #         )
        #     elif metric == "passes":
        #         daily_stats["count"] = daily_stats["num_passes"]
        #     elif metric == "flaky":
        #         daily_stats["count"] = (
        #             daily_stats["num_xpasses"] + daily_stats["num_xfails"]
        #         )
        #     else:  # new_failures - this will show total failures for now
        #         daily_stats["count"] = daily_stats["num_failures"]

        #     daily_stats = (
        #         daily_stats.groupby(["sut_id", "date"])["count"].sum().reset_index()
        #     )
        #     st.write("\nAggregated data sample:")
        #     st.dataframe(daily_stats.head())

        # Create the visualization based on view mode
        if view_mode == "surface":
            fig = create_3d_test_surface(
                filtered_df, metric, smoothing=smoothing, colorscale=color_scale.lower()
            )
        elif view_mode == "heatmap":
            fig = create_test_heatmap(
                filtered_df, metric, colorscale=color_scale.lower()
            )
        else:  # scatter
            fig = create_test_scatter(
                filtered_df, metric, colorscale=color_scale.lower()
            )

        if fig:
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(
                """
            ### How to Interact with the Plot:
            - **Rotate** (3D only): Click and drag
            - **Zoom**: Mouse wheel or pinch gesture
            - **Pan**: Right-click and drag
            - **Reset View**: Double-click

            ### Understanding the Visualization:
            - **X-axis**: Different SUTs (Test Systems)
            - **Y-axis**: Time progression
            - **Z-axis/Color**: Intensity of the selected metric
            """
            )

            # Add statistics table
            st.header("Summary Statistics")
            stats_df = (
                filtered_df.groupby("sut_id")
                .agg(
                    {
                        "num_tests": "sum",
                        "num_passes": lambda x: (
                            x.sum() / filtered_df["num_tests"].sum() * 100
                        ),
                    }
                )
                .round(2)
            )
            stats_df.columns = ["Total Tests", "Pass Rate (%)"]
            st.dataframe(stats_df)
    else:
        st.warning("No data available for the selected date range.")
