import plotly.graph_objects as go
import pandas as pd
import streamlit as st
import sqlite3
from pathlib import Path
import json
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from pytest_oof.db import (
    init_sqlite_db,
    get_rerun_patterns,
    get_xfail_trends,
    get_flaky_tests,
)

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

TABS = [
    "Overview",
    "Session View",
    "Test Results",
    "Test Transitions",
    "Daily Stats",
    "Rerun Analysis",
    "Flaky Tests",
    "Flexible Analysis",
    "SUT Comparison Analysis",
    "Test Analysis"
]

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
    db_path = Path("./.oof/oof-results.db")

    try:
        init_sqlite_db(db_path)  # Initialize using SQLite directly
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
            session_id as id,
            start_time,
            end_time,
            duration,
            sut_id,
            sut_type,
            sut_version,
            sut_env,
            total_tests as num_tests,
            total_tests as num_tests_without_rerun,
            total_tests as num_tests_total,
            passed_tests as num_passes,
            failed_tests as num_failures,
            errors as num_errors,
            skipped_tests as num_skips,
            xfailed_tests as num_xfails,
            xpassed_tests as num_xpasses,
            rerun as num_reruns,
            0 as num_rerun_groups,
            warnings as num_warnings,
            warnings as num_warnings_unique,
            0 as num_deselected
        FROM sessions
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
                "num_tests",
                "num_tests_without_rerun",
                "num_tests_total",
                "num_passes",
                "num_failures",
                "num_errors",
                "num_skips",
                "num_xfails",
                "num_xpasses",
                "num_reruns",
                "num_rerun_groups",
                "num_warnings",
                "num_warnings_unique",
                "num_deselected",
            ]
            for col in int_columns:
                df[col] = df[col].fillna(0).astype("int32").astype(int)

            # Calculate metrics
            df["pass_rate"] = (
                (df["num_passes"] / df["num_tests"] * 100).fillna(0).astype(float)
            )
            df["rerun_rate"] = (
                (df["num_reruns"] / df["num_tests"] * 100).fillna(0).astype(float)
            )
            df["warning_rate"] = (
                (df["num_warnings"] / df["num_tests"] * 100).fillna(0).astype(float)
            )

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
            tr.test_id as nodeid,
            tr.outcome,
            tr.start_time,
            tr.duration,
            tr.error_message,
            tr.error_type,
            tr.has_warning,
            tr.rerun_count,
            s.sut_id,
            s.sut_type,
            s.sut_version,
            s.sut_env
        FROM test_results tr
        JOIN sessions s ON tr.session_id = s.session_id
        ORDER BY tr.start_time DESC
    """

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["start_time"])

            # Return empty DataFrame if no results
            if df.empty:
                st.warning("No test results found in the database. Please run some tests first.")
                return pd.DataFrame(columns=["sut_id", "start_time", "outcome", "duration"])

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
        return pd.DataFrame(columns=["sut_id", "start_time", "outcome", "duration"])  # Return empty DataFrame with required columns

def get_db_path():
    """Get the path to the SQLite database."""
    return Path("./.oof/oof-results.db")

def get_unique_sut_ids(db_path):
    """Get unique SUT IDs from the database."""
    try:
        with sqlite3.connect(db_path) as conn:
            query = "SELECT DISTINCT sut_id FROM sessions ORDER BY sut_id"
            df = pd.read_sql_query(query, conn)
            return df['sut_id'].unique()
    except Exception as e:
        st.error(f"Failed to get unique SUT IDs: {str(e)}")
        return []

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
                        mode="lines+markers"
                        if viz_settings["show_markers"]
                        else "lines",
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
    df_sorted["start_time"] = df_sorted["start_time"].dt.tz_localize(
        None
    )  # Remove timezone info
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
# ERROR: Misplaced return - commented out
#         return

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
# ERROR: Misplaced return - commented out
#         return

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
    rerun_df = df[df["rerun_count"] > 0].copy()  # Make a copy to avoid SettingWithCopyWarning
    if rerun_df.empty:
        return None, None

    # Calculate total rerun time (duration * rerun_count)
    rerun_df["total_rerun_time"] = rerun_df["duration"] * rerun_df["rerun_count"]

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

    # Create rerun outcomes figure showing final outcomes for tests with reruns
    outcome_counts = rerun_df["outcome"].value_counts()

    rerun_outcomes_fig = go.Figure()
    rerun_outcomes_fig.add_trace(
        go.Pie(
            labels=outcome_counts.index,
            values=outcome_counts.values,
            hole=0.4,
            marker=dict(colors=[OUTCOME_COLORS.get(o, "#808080") for o in outcome_counts.index])
        )
    )
    rerun_outcomes_fig.update_layout(
        title="Final Outcomes for Tests with Reruns",
        height=400,
        **PLOTLY_LAYOUT
    )

    return rerun_stats_fig, rerun_outcomes_fig


def create_3d_test_surface(df, metric="failures", smoothing=0.0, colorscale="viridis"):
    """Create a 3D surface plot showing test metrics across SUTs and time."""
    if df.empty:
        return None

    # Prepare data based on metric
    daily_stats = df.copy()
    daily_stats["date"] = pd.to_datetime(daily_stats["start_time"]).dt.date

    # Calculate metric values
    if metric == "failures":
        daily_stats["metric_value"] = daily_stats["num_failures"] + daily_stats["num_errors"]
    elif metric == "passes":
        daily_stats["metric_value"] = daily_stats["num_passes"]
    elif metric == "flaky":
        daily_stats["metric_value"] = daily_stats["num_xpasses"] + daily_stats["num_xfails"]

    # Pivot data to create surface
    pivot_df = daily_stats.pivot_table(
        values="metric_value",
        index="sut_id",
        columns="date",
        aggfunc="sum",
        fill_value=0,
    )

    # Create 3D surface plot
    fig = go.Figure(
        data=[
            go.Surface(
                z=pivot_df.values,
                x=pivot_df.columns,
                y=pivot_df.index,
                colorscale=colorscale,
# smoothing=smoothing,  # Removed invalid 'smoothing' parameter
                colorbar=dict(title=metric.capitalize()),
            )
        ]
    )

    fig.update_layout(
        title=f"{metric.capitalize()} Over Time by SUT",
        scene=dict(
            xaxis_title="Date",
            yaxis_title="SUT",
            zaxis_title=metric.capitalize(),
            camera=dict(
                up=dict(x=0, y=0, z=1),
                center=dict(x=0, y=0, z=0),
                eye=dict(x=1.5, y=1.5, z=1.5)
            ),
            aspectmode='manual',
            aspectratio=dict(x=2, y=1, z=1)
        ),
        width=1000,  # Increased width
        height=800,  # Increased height
        margin=dict(l=0, r=0, b=0, t=30),  # Reduced margins
        **PLOTLY_LAYOUT,
    )

    # Add hover template for better tooltips
    fig.data[0].hovertemplate = (
        "Date: %{x}<br>"
        "SUT: %{y}<br>"
        f"{metric.capitalize()}: %{{z:,.0f}}<br>"
        "<extra></extra>"
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


def create_flexible_visualization(
    df, selected_suts, metrics, view_type="line", normalize=False
):
    """Create a flexible visualization that supports multiple SUTs and metrics."""
    # First, resample the data to daily frequency to avoid duplicate timestamps
    df_sorted = df.copy()
    df_sorted["date"] = df_sorted["start_time"].dt.date

    # Ensure all required columns exist
    metrics = [m for m in metrics if m in df_sorted.columns]

    df_sorted = df_sorted.groupby(["date", "sut_id"])[metrics].sum().reset_index()
    df_sorted["start_time"] = pd.to_datetime(df_sorted["date"])
    df_sorted = df_sorted.sort_values("start_time")

    fig = go.Figure()

    # Define metric properties with consistent colors per metric across SUTs
    metric_props = {
        "num_passes": ("Passed", "#2ecc71"),  # Green
        "num_failures": ("Failed", "#e74c3c"),  # Red
        "num_errors": ("Errors", "#c0392b"),  # Dark Red
        "num_skips": ("Skipped", "#95a5a6"),  # Gray
        "num_xfails": ("Expected Failures", "#f1c40f"),  # Yellow
        "num_xpasses": ("Unexpected Passes", "#3498db"),  # Blue
    }

    # Create color variations for different SUTs
    sut_opacities = {
        sut: 0.5 + (i * 0.5 / len(selected_suts))
        for i, sut in enumerate(selected_suts)
    }

    if view_type == "line":
        # Create a subplot for each metric
        fig = make_subplots(
            rows=len(metrics),
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=[metric_props[m][0] for m in metrics]
        )

        for i, metric in enumerate(metrics, 1):
            name, base_color = metric_props[metric]

            for sut_id in selected_suts:
                sut_data = df_sorted[df_sorted["sut_id"] == sut_id]

                if normalize:
                    total = sut_data[metrics].sum(axis=1)
                    y_values = sut_data[metric] / total * 100
                else:
                    y_values = sut_data[metric]

                fig.add_trace(
                    go.Scatter(
                        x=sut_data["start_time"],
                        y=y_values,
                        name=f"{sut_id} - {name}",
                        mode="lines+markers",
                        line=dict(
                            color=base_color,
                            width=2,
                            dash="solid" if i == 1 else "dot",
                        ),
                        opacity=sut_opacities[sut_id],
                        showlegend=i == 1,  # Only show legend for first subplot
                    ),
                    row=i,
                    col=1
                )

    elif view_type == "area":
        for metric in metrics:
            name, base_color = metric_props[metric]

            for sut_id in selected_suts:
                sut_data = df_sorted[df_sorted["sut_id"] == sut_id]

                if normalize:
                    total = sut_data[metrics].sum(axis=1)
                    y_values = sut_data[metric] / total * 100
                else:
                    y_values = sut_data[metric]

                fig.add_trace(
                    go.Scatter(
                        x=sut_data["start_time"],
                        y=y_values,
                        name=f"{sut_id} - {name}",
                        mode="none",
                        fill="tonexty",
                        stackgroup=sut_id,
                        line=dict(color=base_color),
                        opacity=sut_opacities[sut_id],
                    )
                )

    # Update layout
    title = "Test Results Over Time"
    if normalize:
        title += " (Percentage)"
        y_axis_title = "Percentage"
    else:
        y_axis_title = "Count"

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title=y_axis_title,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        height=200 * max(len(metrics), 2),  # Adjust height based on number of metrics
        margin=dict(t=30, l=10, r=10, b=10),
        hovermode="x unified",
        **PLOTLY_LAYOUT
    )

    return fig


def create_sut_comparison_chart(
    df, selected_suts, selected_metrics, start_date=None, end_date=None
):
    """Create a longitudinal comparison chart for multiple SUTs."""
    df = df.copy()

    # Convert start_time to datetime if it isn't already
    df["start_time"] = pd.to_datetime(df["start_time"])

    # Filter by date range if provided
    if start_date and end_date:
        # Convert dates to timezone-aware datetime
        start_datetime = pd.Timestamp(start_date).tz_localize("UTC")
        end_datetime = (
            pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ).tz_localize("UTC")

        # Filter using timezone-aware comparison
        mask = (df["start_time"] >= start_datetime) & (df["start_time"] <= end_datetime)
        df = df[mask]

    # Debug info
    print(f"Data shape after date filter: {df.shape}")
    print(f"Selected SUTs: {selected_suts}")
    print(f"Selected metrics: {selected_metrics}")

    # Prepare the plot
    fig = go.Figure()

    # Define line styles and colors for metrics

    # Create a line for each SUT and metric combination
    for sut_id in selected_suts:
        sut_data = df[df["sut_id"] == sut_id].sort_values("start_time")
        print(f"\nSUT {sut_id} data shape: {sut_data.shape}")

        if len(sut_data) == 0:
            print(f"No data found for SUT {sut_id}")
            continue

        for metric in selected_metrics:
            if metric in sut_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=sut_data["start_time"],
                        y=sut_data[metric],
                        name=f"{sut_id} - {metric}",
                        mode="lines+markers",
                    )
                )
                print(
                    f"Added trace for {sut_id} - {metric} with {len(sut_data)} points"
                )

    # Update layout
    fig.update_layout(
        title="Test Results Comparison Across SUTs",
        xaxis_title="Time",
        yaxis_title="Count",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


# Load data first
df = load_session_data()
test_results_df = load_test_results()

# Initialize session states if they don't exist
if "active_tab" not in st.session_state:
    st.session_state.active_tab = 0
if "viz_type" not in st.session_state:
    st.session_state.viz_type = "line"

# Display database path
db_path = Path("./.oof/oof-results.db").resolve()
st.sidebar.markdown("### Database Location")
st.sidebar.code(str(db_path), language="text")

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
test_results_df_sut = (
    test_results_df
    if selected_sut == "All SUTs"
    else test_results_df[test_results_df["sut_id"] == selected_sut]
)

# # Main content with tabs
# st.title("pytest-oof Test Analysis")

# tab_names = [
#     "Overview",
#     "Session View",
#     "Session Details",
#     "Session Comparison",
#     "Test Stability Analysis",
#     "Rerun Analysis",
#     "3D Visualization",
#     "Flaky Tests",
#     "Flexible Analysis",
#     "SUT Comparison Analysis",
#     "Test Analysis"
# ]

# Create tabs and handle tab selection
tabs = st.tabs(TABS)

# Handle tab changes
for i, tab in enumerate(tabs):
    if tab.id != st.session_state.get("last_tab_id"):
        st.session_state.active_tab = i
        st.session_state.last_tab_id = tab.id
        break

with tabs[st.session_state.active_tab]:
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
        [
            "Overview",
            "Session View",
            "Session Details",
            "Session Comparison",
            "Test Stability Analysis",
            "Rerun Analysis",
            "3D Visualization",
            "Flaky Tests",
            "Flexible Analysis",
            "SUT Comparison Analysis",
            "Test Analysis"
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
            view_type=view_type.lower().replace(" ", "_"),
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
        if not test_results_df_sut.empty:
            st.dataframe(
                test_results_df_sut.sort_values("start_time", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No test data available for the selected SUT.")

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
        st.header("Test Stability Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Test Transitions Settings")
            lookback_window = st.slider(
                "Lookback Window (days)",
                1,
                30,
                7,
                help="Number of days to look back for transitions",
            )
            min_transition_runs = st.slider(
                "Minimum Runs for Transitions",
                2,
                10,
                3,
                help="Minimum number of runs required to consider a transition",
            )
            failure_threshold = st.slider(
                "Failure Threshold (%)",
                50,
                100,
                60,
                help="Percentage of failures required to consider a test as failing",
            )
            success_threshold = st.slider(
                "Success Threshold (%)",
                50,
                100,
                60,
                help="Percentage of successes required to consider a test as passing",
            )

        with col2:
            st.subheader("Flaky Tests Settings")
            min_flaky_runs = st.slider(
                "Minimum Runs for Flaky",
                2,
                10,
                3,
                help="Minimum number of runs required to consider a test flaky",
            )
            flaky_threshold = st.slider(
                "Flaky Threshold (%)",
                10,
                50,
                20,
                help="Minimum percentage of both passes and fails to consider a test flaky",
            )

        # Test Transitions Analysis
        st.subheader("Test Transitions")
        fail_to_pass, pass_to_fail = identify_test_transitions(
            test_results_df_sut,
            lookback_window=lookback_window,
            min_runs=min_transition_runs,
            failure_threshold=failure_threshold / 100,  # Convert to decimal
            success_threshold=success_threshold / 100,  # Convert to decimal
        )

        if not fail_to_pass.empty or not pass_to_fail.empty:
            transitions_fig = plot_test_transitions(fail_to_pass, pass_to_fail)
            if transitions_fig:
                st.plotly_chart(transitions_fig, use_container_width=True)
        else:
            st.info(
                "No test transitions detected with current settings. Try adjusting the thresholds."
            )

        # Flaky Tests Analysis
        st.subheader("Flaky Tests")
        flaky_df = identify_flaky_tests(
            test_results_df_sut,
            min_runs=min_flaky_runs,
            flaky_threshold=flaky_threshold / 100,  # Convert to decimal
        )

        if not flaky_df.empty:
            st.write(f"Found {len(flaky_df)} flaky tests:")
            for _, test in flaky_df.iterrows():
                with st.expander(
                    f"{test['id']} (Pass Rate: {test['pass_rate']:.1f}%, Fail Rate: {test['fail_rate']:.1f}%)"
                ):
                    st.write(f"Total Runs: {test['total_runs']}")
                    st.write(f"SUTs Affected: {test['suts_affected']}")
                    st.write(f"Duration: {test['duration_days']} days")
                    st.write(f"First Seen: {test['first_seen']}")
                    st.write(f"Last Seen: {test['last_seen']}")
        else:
            st.info(
                "No flaky tests identified with current settings. Try adjusting the thresholds."
            )

    with tab6:
        st.header("Rerun Analysis")
        if not test_results_df_sut.empty:
            rerun_stats_fig, rerun_outcomes_fig = analyze_rerun_patterns(
                test_results_df_sut
            )
            if rerun_stats_fig:
                st.plotly_chart(rerun_stats_fig, use_container_width=True)
            if rerun_outcomes_fig:
                st.plotly_chart(rerun_outcomes_fig, use_container_width=True)
        else:
            st.info("No rerun data available for the selected SUT.")

    with tab7:
        st.header("3D Test Result Visualization")

        # Load session data
        daily_stats_df = load_session_data()
        if daily_stats_df is None or daily_stats_df.empty:
            st.warning("No session data available.")
# ERROR: Misplaced return - commented out
#             return

        col1, col2, col3 = st.columns(3)
        with col1:
            metric = st.selectbox(
                "Metric",
                ["failures", "passes", "flaky"],
                key="surface_metric"
            )
        with col2:
            smoothing = st.slider(
                "Surface Smoothing",
                min_value=0.0,
                max_value=1.0,
                value=0.0,
                step=0.1,
                key="surface_smoothing"
            )
        with col3:
            colorscale = st.selectbox(
                "Color Scale",
                ["viridis", "plasma", "inferno", "magma", "RdYlBu"],
                key="surface_colorscale"
            )

        surface_fig = create_3d_test_surface(
            daily_stats_df,
            metric=metric,
            smoothing=smoothing,
            colorscale=colorscale.lower()
        )
        if surface_fig:
            st.plotly_chart(surface_fig, use_container_width=True)

            st.markdown("""
            ### How to Interact with the 3D Plot:
            - **Rotate**: Click and drag
            - **Zoom**: Mouse wheel or pinch gesture
            - **Pan**: Right-click and drag
            - **Reset View**: Double-click
            """)
    with tab8:
        st.header("Flaky Tests")
        if not test_results_df_sut.empty:
            flaky_df = identify_flaky_tests(
                test_results_df_sut,
                min_runs=3,
                flaky_threshold=0.2,
            )
            if not flaky_df.empty:
                st.write(f"Found {len(flaky_df)} flaky tests:")
                for _, test in flaky_df.iterrows():
                    with st.expander(
                        f"{test['id']} (Pass Rate: {test['pass_rate']:.1f}%, Fail Rate: {test['fail_rate']:.1f}%)"
                    ):
                        st.write(f"Total Runs: {test['total_runs']}")
                        st.write(f"SUTs Affected: {test['suts_affected']}")
                        st.write(f"Duration: {test['duration_days']} days")
                        st.write(f"First Seen: {test['first_seen']}")
                        st.write(f"Last Seen: {test['last_seen']}")
            else:
                st.info(
                    "No flaky tests identified with current settings. Try adjusting the thresholds."
                )
        else:
            st.info("No test data available for the selected SUT.")

    with tab9:
        st.header("Flexible Test Analysis")

        # Controls in columns
        col1, col2, col3 = st.columns(3)

        with col1:
            # SUT selection
            all_suts = sorted(df["sut_id"].unique())
            selected_suts = st.multiselect(
                "Select SUTs",
                options=all_suts,
                default=[all_suts[0]] if all_suts else None,
                key="flex_suts",  # Add unique key
                help="Choose one or more SUTs to analyze",
            )

        with col2:
            # Metric selection - only show available metrics
            available_metrics = [
                ("num_passes", "Passes"),
                ("num_failures", "Failures"),
                ("num_errors", "Errors"),
                ("num_skips", "Skipped"),
                ("num_xfails", "Expected Failures"),
                ("num_xpasses", "Unexpected Passes"),
            ]
            # Filter to only show metrics that exist in the DataFrame
            available_metrics = [
                (m, n) for m, n in available_metrics if m in df.columns
            ]

            selected_metrics = st.multiselect(
                "Select Metrics",
                options=[m[0] for m in available_metrics],
                default=[
                    m[0] for m in available_metrics[:2]
                ],  # Select first two available metrics
                format_func=lambda x: dict(available_metrics)[x],
                key="flex_metrics",  # Add unique key
                help="Choose which metrics to display",
            )

        with col3:
            # Visualization options
            view_type = st.selectbox(
                "Visualization Type",
                options=["line", "area", "heatmap"],
                key="flex_viz_type",  # Add unique key
                help="Choose how to display the data",
            )

            normalize = st.checkbox(
                "Show Percentages",
                value=False,
                key="flex_normalize",  # Add unique key
                help="Display values as percentages instead of absolute counts",
            )

        if selected_suts and selected_metrics:
            # Create and display visualization
            fig = create_flexible_visualization(
                df,
                selected_suts=selected_suts,
                metrics=selected_metrics,
                view_type=view_type,
                normalize=normalize,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Please select at least one SUT and one metric to display.")

    with tab10:
        st.header("SUT Comparison Analysis")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Debug info
            st.write("Debug Info:")
            st.write(f"Total records: {len(df_sut)}")
            st.write(f"Available SUTs: {sorted(df_sut['sut_id'].unique())}")
            if "start_time" in df_sut.columns:
                st.write(
                    f"Date range in data: {pd.to_datetime(df_sut['start_time']).min()} to {pd.to_datetime(df_sut['start_time']).max()}"
                )

            # SUT selection
            all_suts = sorted(df_sut["sut_id"].unique())
            selected_suts = st.multiselect(
                "Select SUTs to Compare",
                options=all_suts,
                default=[all_suts[0]] if all_suts else None,
                key="compare_suts",
                help="Choose one or more SUTs to compare",
            )

            # Metric selection
            metric_options = [
                ("num_passes", "Passes"),
                ("num_failures", "Failures"),
                ("num_errors", "Errors"),
                ("num_skips", "Skips"),
                ("num_xfails", "Expected Failures"),
                ("num_xpasses", "Unexpected Passes"),
            ]

            # Show available columns
            st.write("Available columns:", df_sut.columns.tolist())

            # Only show metrics that exist in the data
            metric_options = [(m, n) for m, n in metric_options if m in df_sut.columns]
            st.write("Available metrics:", [n for m, n in metric_options])

            selected_metrics = st.multiselect(
                "Select Metrics to Display",
                options=[m[0] for m in metric_options],
                default=[
                    m[0] for m in metric_options[:3]
                ],  # Default to first 3 metrics
                format_func=lambda x: dict(metric_options)[x],
                key="compare_metrics",
                help="Choose which metrics to display for each SUT",
            )

            st.write("Selected metrics:", selected_metrics)

        with col2:
            # Date range selection
            st.write("Date Range")

            # Get date range
            dates = pd.to_datetime(df_sut["start_time"])
            min_datetime = dates.min()
            max_datetime = dates.max()

            # Show available range
            st.caption(
                f"Data available from {min_datetime:%Y-%m-%d %H:%M %Z} to {max_datetime:%Y-%m-%d %H:%M %Z}"
            )

            # Quick selection options
            date_range_option = st.selectbox(
                "Quick Select",
                options=[
                    "Last hour",
                    "Last 4 hours",
                    "Last 24 hours",
                    "Last 7 days",
                    "Last 30 days",
                    "All time",
                    "Custom range",
                ],
                key="date_range_option",
            )

            from datetime import timedelta

            if date_range_option == "Custom range":
                # Custom date inputs
                start_date_str = st.text_input(
                    "Start Date (YYYY-MM-DD)",
                    value=(max_datetime - timedelta(days=1)).strftime("%Y-%m-%d"),
                    key="start_date_str",
                )
                try:
                    start_date = pd.to_datetime(start_date_str).tz_localize(None).date()
                except:
                    st.error("Please enter date in YYYY-MM-DD format")
                    start_date = (
                        (max_datetime - timedelta(days=1)).tz_localize(None).date()
                    )

                end_date_str = st.text_input(
                    "End Date (YYYY-MM-DD)",
                    value=max_datetime.strftime("%Y-%m-%d"),
                    key="end_date_str",
                )
                try:
                    end_date = pd.to_datetime(end_date_str).tz_localize(None).date()
                except:
                    st.error("Please enter date in YYYY-MM-DD format")
                    end_date = max_datetime.tz_localize(None).date()
            else:
                # Calculate date range based on selection
                end_date = max_datetime.tz_localize(None).date()
                if date_range_option == "Last hour":
                    start_date = (
                        (max_datetime - timedelta(hours=1)).tz_localize(None).date()
                    )
                elif date_range_option == "Last 4 hours":
                    start_date = (
                        (max_datetime - timedelta(hours=4)).tz_localize(None).date()
                    )
                elif date_range_option == "Last 24 hours":
                    start_date = (
                        (max_datetime - timedelta(hours=24)).tz_localize(None).date()
                    )
                elif date_range_option == "Last 7 days":
                    start_date = (
                        (max_datetime - timedelta(days=7)).tz_localize(None).date()
                    )
                elif date_range_option == "Last 30 days":
                    start_date = (
                        (max_datetime - timedelta(days=30)).tz_localize(None).date()
                    )
                else:  # All time
                    start_date = min_datetime.tz_localize(None).date()

            # Ensure dates are within valid range
            start_date = max(
                min_datetime.tz_localize(None).date(),
                min(max_datetime.tz_localize(None).date(), start_date),
            )
            end_date = max(
                start_date, min(max_datetime.tz_localize(None).date(), end_date)
            )

            # Show selected range
            st.caption(f"Selected range: {start_date:%Y-%m-%d} to {end_date:%Y-%m-%d}")

        if selected_suts and selected_metrics:
            fig = create_sut_comparison_chart(
                df_sut,
                selected_suts=selected_suts,
                selected_metrics=selected_metrics,
                start_date=start_date,
                end_date=end_date,
            )
            st.plotly_chart(fig, use_container_width=True)

            st.info(
                "**Interaction Tips:**\n"
                "- Click on legend items to show/hide individual lines\n"
                "- Double-click to isolate a single item\n"
                "- Click on a SUT name to toggle all metrics for that SUT\n"
                "- Drag to zoom, double-click to reset view"
            )
        else:
            st.info("Please select at least one SUT and one metric to display.")

    with tab11:
        def get_rerun_patterns(db_path, days, min_reruns, sut_filter=None):
            """Get rerun patterns from the database.

            Args:
                db_path: Path to the SQLite database
                days: Number of days to look back
                min_reruns: Minimum number of reruns required
                sut_filter: Optional SUT ID to filter by

            Returns:
                dict: Dictionary containing recovery metrics and patterns
            """
            try:
                with sqlite3.connect(db_path) as conn:
                    # Base query to get test results with reruns
                    query = """
                        SELECT
                            tr.test_id,
                            tr.outcome,
                            tr.rerun_outcomes,
                            tr.rerun_count,
                            s.start_time
                        FROM test_results tr
                        JOIN sessions s ON tr.session_id = s.session_id
                        WHERE s.start_time >= datetime('now', ?)
                    """
                    params = [f'-{days} days']

                    if sut_filter:
                        query += " AND s.sut_id = ?"
                        params.append(sut_filter)

                    query += " ORDER BY s.start_time"

                    df = pd.read_sql_query(query, conn, params=params)

                    if df.empty:
                        return {
                            "recovery_rate": 0.0,
                            "avg_attempts": 0.0,
                            "success_patterns": [],
                            "failure_patterns": []
                        }

                    # Process the results
                    success_patterns = defaultdict(int)
                    failure_patterns = defaultdict(int)
                    total_attempts = []

                    for _, row in df.iterrows():
                        test_id = row['test_id']
                        outcome = row['outcome']
                        rerun_outcomes = json.loads(row['rerun_outcomes']) if row['rerun_outcomes'] else []
                        rerun_count = row['rerun_count']

                        if rerun_count >= min_reruns:
                            full_sequence = [outcome] + rerun_outcomes
                            sequence = tuple(full_sequence)
                            if outcome == 'PASSED':
                                success_patterns[sequence] += 1
                            else:
                                failure_patterns[sequence] += 1

                            total_attempts.append(rerun_count)

                    successful_reruns = len([x for x in df['outcome'] if x == 'PASSED'])
                    total_reruns = len(df)

                    return {
                        "success_patterns": sorted(
                            [(list(k), v) for k, v in success_patterns.items()],
                            key=lambda x: x[1],
                            reverse=True
                        )[:5],
                        "failure_patterns": sorted(
                            [(list(k), v) for k, v in failure_patterns.items()],
                            key=lambda x: x[1],
                            reverse=True
                        )[:5],
                        "recovery_rate": (successful_reruns / total_reruns * 100) if total_reruns > 0 else 0.0,
                        "avg_attempts": sum(total_attempts) / len(total_attempts) if total_attempts else 0.0
                    }

            except Exception as e:
                st.error(f"Failed to get rerun patterns: {str(e)}")
                return {
                    "recovery_rate": 0.0,
                    "avg_attempts": 0.0,
                    "success_patterns": [],
                    "failure_patterns": []
                }

        def display_test_analysis():
            """Display test analysis section."""
            # Add filters
            col1, col2, col3 = st.columns(3)
            with col1:
                days = st.number_input("Analysis Period (days)", min_value=1, value=30)
            with col2:
                min_runs = st.number_input("Minimum Runs", min_value=1, value=5)
            with col3:
                sut_id = st.selectbox(
                    "Filter by SUT",
                    options=["All"] + list(get_unique_sut_ids(get_db_path())),
                    index=0
                )

            sut_filter = None if sut_id == "All" else sut_id

            # Create tabs for different analyses
            tab1, tab2, tab3 = st.tabs(["Rerun Analysis", "XFail Trends", "Flaky Tests"])

            with tab1:
                st.subheader("Rerun Pattern Analysis")
                min_reruns = st.number_input("Minimum Reruns", min_value=1, value=3)
                patterns = get_rerun_patterns(get_db_path(), days, min_reruns, sut_filter)

                # Display recovery metrics
                col1, col2 = st.columns(2)
                col1.metric("Recovery Rate", f"{patterns['recovery_rate']:.1f}%")
                col2.metric("Average Attempts", f"{patterns['avg_attempts']:.1f}")

                # Show success patterns
                if patterns["success_patterns"]:
                    st.subheader("Successful Recovery Patterns")
                    for sequence, count in patterns["success_patterns"]:
                        st.write(f"• {' → '.join(sequence)} ({count} occurrences)")

                # Show failure patterns
                if patterns["failure_patterns"]:
                    st.subheader("Failed Recovery Patterns")
                    for sequence, count in patterns["failure_patterns"]:
                        st.write(f"• {' → '.join(sequence)} ({count} occurrences)")

            with tab2:
                st.subheader("XFail/XPass Trends")
                granularity = st.selectbox(
                    "Time Grouping",
                    options=["hour", "day", "week"],
                    index=1
                )

                trends = get_xfail_trends(get_db_path(), days, granularity, sut_filter)
                if trends:
                    # Create DataFrame for plotting
                    df = pd.DataFrame(trends)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])

                    # Plot trends
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df['timestamp'],
                        y=df['xfail_rate'],
                        name='XFail Rate',
                        line=dict(color='orange')
                    ))
                    fig.add_trace(go.Scatter(
                        x=df['timestamp'],
                        y=df['xpass_rate'],
                        name='XPass Rate',
                        line=dict(color='green')
                    ))

                    fig.update_layout(
                        title='XFail/XPass Trends Over Time',
                        xaxis_title='Time',
                        yaxis_title='Rate (%)',
                        height=500
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Show current stats
                    if len(df) > 0:
                        latest = df.iloc[-1]
                        col1, col2 = st.columns(2)
                        col1.metric("Current XFail Rate", f"{latest['xfail_rate']:.1f}%")
                        col2.metric("Current XPass Rate", f"{latest['xpass_rate']:.1f}%")

            with tab3:
                st.subheader("Flaky Test Detection")
                threshold = st.slider(
                    "Flakiness Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.1,
                    step=0.05,
                    help="Minimum ratio of outcome changes to total runs"
                )

                flaky_tests = get_flaky_tests(
                    get_db_path(), days, min_runs, threshold, sut_filter
                )

                if flaky_tests:
                    for test in flaky_tests:
                        with st.expander(
                            f"{test['test_id']} (Score: {test['flakiness_score']:.2f})"
                        ):
                            # Show test details
                            st.write("Run Count:", test['run_count'])
                            st.write("Unique Outcomes:", ", ".join(test['unique_outcomes']))

                            # Create pie chart of outcomes
                            fig = go.Figure(data=[go.Pie(
                                labels=list(test['outcome_counts'].keys()),
                                values=list(test['outcome_counts'].values())
                            )])
                            fig.update_layout(
                                title='Outcome Distribution',
                                height=300
                            )
                            st.plotly_chart(fig, use_container_width=True)

                            # Show common transitions
                            st.write("Common Outcome Transitions:")
                            for (from_outcome, to_outcome), count in test['common_transitions']:
                                st.write(f"• {from_outcome} → {to_outcome} ({count} times)")
                else:
                    st.info("No flaky tests found with the current criteria")

        display_test_analysis()
