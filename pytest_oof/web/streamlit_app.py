"""Streamlit dashboard for pytest-oof test analysis."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import pytz
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import os

from pytest_oof.db import export_results, init_db

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
    'total': '#4a90e2',      # Blue
    'passed': '#28a745',     # Green
    'failed': '#dc3545',     # Red
    'error': '#ff1493',      # Fuschia
    'skipped': '#6c757d',    # Grey
    'xfailed': '#90EE90',    # Light green
    'xpassed': '#FFE4B5',    # Light yellow
    'warnings': '#ffa500'    # Orange
}

# Define which outcomes should have white text for better contrast
WHITE_TEXT_OUTCOMES = ['failed', 'error', 'total']

# Custom CSS
st.markdown(
    """
<style>
    /* Increase base font size by 25% */
    html {
        font-size: 125%;
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
    .metric-good { color: """ + OUTCOME_COLORS['passed'] + """ !important; }
    .metric-bad { color: """ + OUTCOME_COLORS['failed'] + """ !important; }
    .metric-neutral { color: """ + OUTCOME_COLORS['skipped'] + """ !important; }

    /* Increase font size for specific elements */
    .stMarkdown h1 { font-size: 2.25em !important; }
    .stMarkdown h2 { font-size: 1.875em !important; }
    .stMarkdown h3 { font-size: 1.5em !important; }
    .stMarkdown h4 { font-size: 1.25em !important; }
    .stMarkdown p { font-size: 1.125em !important; }

    /* Adjust dataframe text size and alignment */
    .dataframe {
        font-size: 1.125em !important;
    }
    .dataframe td:not(:first-child) {
        text-align: right !important;
        padding-right: 10px !important;
    }
    .dataframe th:not(:first-child) {
        text-align: right !important;
        padding-right: 10px !important;
    }
    .dataframe td:first-child, .dataframe th:first-child {
        text-align: left !important;
        padding-left: 10px !important;
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
            id, session_id, start_time, end_time, duration,
            sut_id, num_tests, num_passes, num_failures,
            num_errors, num_skips, num_xfails, num_xpasses
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
            df["duration"] = df["duration"].fillna(0).astype(float)

            # Convert numeric columns to native Python int
            int_columns = [
                "num_tests",
                "num_passes",
                "num_failures",
                "num_errors",
                "num_skips",
                "num_xfails",
                "num_xpasses",
            ]
            for col in int_columns:
                df[col] = df[col].fillna(0).astype("int32").astype(int)

            # Calculate pass rate as float
            df["pass_rate"] = (
                (df["num_passes"] / df["num_tests"] * 100).fillna(0).astype(float)
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
            tr.test_id,
            tr.outcome,
            tr.duration,
            tr.error_message,
            tr.error_type,
            ts.id as session_id,
            ts.start_time,
            ts.sut_id
        FROM test_results tr
        JOIN test_sessions ts ON tr.session_id = ts.id
        ORDER BY ts.start_time DESC
    """

    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn, parse_dates=["start_time"])

            if df.empty:
                st.warning("No test results found in the database.")
                return pd.DataFrame(
                    columns=[
                        "test_id",
                        "outcome",
                        "duration",
                        "error_message",
                        "error_type",
                        "session_id",
                        "start_time",
                        "sut_id",
                    ]
                )

            # Ensure timezone awareness
            if df["start_time"].dt.tz is None:
                df["start_time"] = df["start_time"].dt.tz_localize("UTC")

            # Fill NaN/None values
            df["sut_id"] = df["sut_id"].fillna("")
            df["duration"] = df["duration"].fillna(0).astype(float)
            df["outcome"] = df["outcome"].fillna("unknown")
            df["error_message"] = df["error_message"].fillna("")
            df["error_type"] = df["error_type"].fillna("")

            return df
    except Exception as e:
        st.error(f"Error loading test results: {str(e)}")
        return pd.DataFrame(
            columns=[
                "test_id",
                "outcome",
                "duration",
                "error_message",
                "error_type",
                "session_id",
                "start_time",
                "sut_id",
            ]
        )


def plot_test_results_trend(df, viz_settings):
    """Plot test results trend over time."""
    df_sorted = df.sort_values("start_time")

    fig = go.Figure()

    # Add traces for each metric
    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_passes"],
            name="Passed",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['passed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_failures"],
            name="Failed",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['failed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_errors"],
            name="Errors",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['error'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_skips"],
            name="Skipped",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['skipped'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_xfails"],
            name="Expected Failures",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['xfailed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_xpasses"],
            name="Unexpected Passes",
            mode="lines+markers" if viz_settings["show_markers"] else "lines",
            line=dict(
                color=OUTCOME_COLORS['xpassed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.update_layout(
        title="Test Results Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Tests",
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,  # Apply global font settings
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
                color=OUTCOME_COLORS['passed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
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
                color=OUTCOME_COLORS['failed'],
                width=viz_settings["line_width"],
                shape=viz_settings["line_shape"],
                smoothing=viz_settings["smoothing"]
                if viz_settings["line_shape"] == "spline"
                else None,
            ),
        )
    )

    fig.update_layout(
        title=f"Pass/Fail Rate Trend for {sut_id}",
        xaxis_title="Date",
        yaxis_title="Rate (%)",
        yaxis_range=[0, 100],
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


def identify_test_transitions(df, sut_id=None, n_runs=5):
    """Identify tests that have changed state (FAIL→PASS or PASS→FAIL) in recent runs.

    Args:
        df: DataFrame with test results
        sut_id: Optional SUT ID to filter by
        n_runs: Number of previous runs to check for state change

    Returns:
        tuple: (fail_to_pass, pass_to_fail) DataFrames containing test transitions
    """
    if sut_id:
        df = df[df["sut_id"] == sut_id]

    # Get the most recent results for each test
    df = df.sort_values("start_time", ascending=False)
    recent_results = []

    for test_id in df["test_id"].unique():
        test_results = df[df["test_id"] == test_id].head(n_runs + 1)
        if len(test_results) >= n_runs + 1:  # Need at least n_runs + 1 results
            outcomes = test_results["outcome"].tolist()
            latest_outcome = outcomes[0]
            previous_outcomes = outcomes[1 : n_runs + 1]

            # Check for FAIL → PASS transition
            if latest_outcome == "passed" and all(
                o == "failed" for o in previous_outcomes
            ):
                recent_results.append(
                    {
                        "test_id": test_id,
                        "sut_id": test_results.iloc[0]["sut_id"],
                        "transition": "fail_to_pass",
                        "previous_runs": n_runs,
                        "last_run_time": test_results.iloc[0]["start_time"],
                    }
                )

            # Check for PASS → FAIL transition
            elif latest_outcome == "failed" and all(
                o == "passed" for o in previous_outcomes
            ):
                recent_results.append(
                    {
                        "test_id": test_id,
                        "sut_id": test_results.iloc[0]["sut_id"],
                        "transition": "pass_to_fail",
                        "previous_runs": n_runs,
                        "last_run_time": test_results.iloc[0]["start_time"],
                    }
                )

    results_df = pd.DataFrame(recent_results)
    if not results_df.empty:
        fail_to_pass = results_df[results_df["transition"] == "fail_to_pass"]
        pass_to_fail = results_df[results_df["transition"] == "pass_to_fail"]
        return fail_to_pass, pass_to_fail
    return pd.DataFrame(), pd.DataFrame()


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
    for test_id, group in df.groupby("test_id"):
        total_runs = len(group)
        if total_runs < min_runs:
            continue

        # Count different outcomes
        outcome_counts = group["outcome"].value_counts()
        total_outcomes = sum(outcome_counts)

        # Calculate rates for different outcomes
        pass_rate = outcome_counts.get("PASSED", 0) / total_outcomes
        fail_rate = (outcome_counts.get("FAILED", 0) + outcome_counts.get("ERROR", 0)) / total_outcomes

        # A test is considered flaky if it has significant pass AND fail rates
        if pass_rate >= flaky_threshold and fail_rate >= flaky_threshold:
            suts_affected = group["sut_id"].nunique()
            last_seen = group["start_time"].max()
            first_seen = group["start_time"].min()
            duration = (last_seen - first_seen).total_seconds() / 86400  # Convert to days

            flaky_tests.append({
                "test_id": test_id,
                "total_runs": total_runs,
                "pass_rate": pass_rate * 100,  # Convert to percentage
                "fail_rate": fail_rate * 100,  # Convert to percentage
                "suts_affected": suts_affected,
                "last_seen": last_seen,
                "first_seen": first_seen,
                "duration_days": round(duration, 1)
            })

    if not flaky_tests:
        return pd.DataFrame(
            columns=[
                "test_id",
                "total_runs",
                "pass_rate",
                "fail_rate",
                "suts_affected",
                "last_seen",
                "first_seen",
                "duration_days"
            ]
        )

    return pd.DataFrame(flaky_tests).sort_values("total_runs", ascending=False)


def plot_daily_stats(df):
    """Plot daily statistics."""
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
            line=dict(color=OUTCOME_COLORS['passed'], width=2),
        )
    )

    # Add failure rate trace
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["failure_rate"],
            name="Failure Rate",
            mode="lines+markers",
            line=dict(color=OUTCOME_COLORS['failed'], width=2),
        )
    )

    # Add total tests trace on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["num_tests"],
            name="Total Tests",
            mode="lines+markers",
            line=dict(color=OUTCOME_COLORS['total'], width=2),
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

    for metric, label, color in metrics:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df[metric],
                name=label,
                mode="lines+markers",
                line=dict(color=OUTCOME_COLORS[color], width=2),
            )
        )

    fig.update_layout(
        title="Test Metrics Over Time",
        xaxis_title="Date",
        yaxis_title="Count",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT,
    )

    return fig


# Sidebar
with st.sidebar:
    st.markdown("## Settings")

    # Database info - display only once at the top
    db_path = ensure_db_exists()
    st.markdown(f"Using database: `{os.path.basename(db_path)}`")

    st.divider()

    # Page selection
    st.markdown("### Navigation")
    page = st.selectbox(
        "Select Page",
        ["Overview", "Session Details", "Session Comparison", "Test Transitions", "Flaky Tests"],
        key="page_selector"
    )

    st.divider()

    # Time window selection
    st.markdown("### Time Window")
    window_type = st.radio("Select time range type", ["Preset", "Custom"], key="time_window_type")

    if window_type == "Preset":
        window_options = {
            "Last 24 Hours": timedelta(days=1),
            "Last 7 Days": timedelta(days=7),
            "Last 30 Days": timedelta(days=30),
            "All Time": None
        }
        selected_window = st.selectbox("Select Time Window", list(window_options.keys()), key="time_window")
        cutoff_time = pd.Timestamp.now(tz='UTC') - window_options[selected_window] if window_options[selected_window] else None
    else:
        # Get min and max dates from the database for bounds
        df_temp = load_session_data()
        min_date = df_temp['start_time'].min().date() if not df_temp.empty else datetime.now(tz=pytz.UTC).date() - timedelta(days=30)
        max_date = df_temp['start_time'].max().date() if not df_temp.empty else datetime.now(tz=pytz.UTC).date()

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input(
                "Start Date",
                value=max_date - timedelta(days=7),
                min_value=min_date,
                max_value=max_date,
                key="start_date"
            )
        with col2:
            end_date = st.date_input(
                "End Date",
                value=max_date,
                min_value=start_date,
                max_value=max_date,
                key="end_date"
            )

        if start_date > end_date:
            st.error("Start date must be before end date")
            st.stop()

        # Convert dates to timestamps at start/end of day
        cutoff_time = pd.Timestamp(start_date, tz='UTC')
        end_time = pd.Timestamp(end_date, tz='UTC') + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    st.divider()

    # Load and filter data based on time window and page type
    df = load_session_data() if page in ["Overview", "Session Details", "Session Comparison"] else load_test_results()

    if cutoff_time:
        df = df[df['start_time'] >= cutoff_time]
        if window_type == "Custom":
            df = df[df['start_time'] <= end_time]

    # SUT selection
    st.markdown("### System Under Test")
    suts = df["sut_id"].unique()
    suts = sorted([sut for sut in suts if sut])  # Remove empty strings and sort

    if page == "Flaky Tests":
        selected_sut = st.selectbox(
            "Select SUT",
            ["All SUTs"] + suts,
            index=0,
            key="sut_selector"
        )
    else:
        selected_sut = st.selectbox(
            "Select SUT",
            suts,
            key="sut_selector"
        )

    st.divider()

    # Page specific settings
    if page == "Test Transitions":
        st.markdown("### Transition Parameters")
        n_runs = st.slider("Number of previous runs to check", 2, 10, 5, key="transition_runs")
    elif page == "Flaky Tests":
        st.markdown("### Flakiness Parameters")
        col1, col2 = st.columns(2)
        with col1:
            min_runs = st.number_input(
                "Minimum Runs Required",
                min_value=2,
                max_value=50,
                value=5,
                help="Minimum number of test runs required to consider a test for flakiness",
                key="flaky_min_runs"
            )
        with col2:
            flaky_threshold = st.slider(
                "Flaky Threshold (%)",
                min_value=5,
                max_value=50,
                value=20,
                step=5,
                help="Minimum percentage of both passes and fails required to consider a test flaky",
                key="flaky_threshold"
            ) / 100.0  # Convert percentage to decimal

    st.divider()

    # Visualization settings
    st.markdown("### Visualization Settings")
    viz_settings = {
        "line_shape": st.selectbox(
            "Line Shape",
            ["linear", "spline", "hv", "vh", "hvh", "vhv"],
            help="Shape of the line connecting data points",
            key="line_shape"
        ),
        "line_width": st.slider(
            "Line Width",
            1, 5, 2,
            help="Width of the plot lines in pixels",
            key="line_width"
        ),
        "show_markers": st.checkbox(
            "Show Markers",
            True,
            help="Show data point markers on the lines",
            key="show_markers"
        )
    }

    # Add smoothing only if spline is selected
    if viz_settings["line_shape"] == "spline":
        viz_settings["smoothing"] = st.slider(
            "Smoothing Factor",
            0.0, 1.3, 0.5, 0.1,
            help="Higher values make the line smoother (0 = no smoothing, 1.3 = maximum smoothing)",
            key="smoothing"
        )
    else:
        viz_settings["smoothing"] = 0.0

# Main content area
if page == "Overview":
    st.title("📊 Test Results Overview")

    # Filter data for selected SUT
    df_sut = df[df['sut_id'] == selected_sut]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Sessions",
            f"{len(df['session_id'].unique()):,}",
            delta=None,
            help="Number of unique test sessions",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["total"]}; font-weight: bold; text-align: center;">{len(df["session_id"].unique()):,}</p>', unsafe_allow_html=True)

        st.metric(
            "Total Tests",
            f"{df_sut['num_tests'].sum():,}",
            delta=None,
            help="Total number of tests",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["total"]}; font-weight: bold; text-align: center;">{df_sut["num_tests"].sum():,}</p>', unsafe_allow_html=True)

    with col2:
        pass_rate = df_sut['pass_rate'].mean()
        st.metric(
            "Pass Rate",
            f"{pass_rate:.1%}",
            delta=None,
            help="Percentage of tests that passed",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["passed"]}; font-weight: bold; text-align: center;">{pass_rate:.1%}</p>', unsafe_allow_html=True)

        fail_rate = (df_sut['num_failures'].sum() + df_sut['num_errors'].sum()) / df_sut['num_tests'].sum() * 100
        st.metric(
            "Fail Rate",
            f"{fail_rate:.1%}",
            delta=None,
            help="Percentage of tests that failed",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["failed"]}; font-weight: bold; text-align: center;">{fail_rate:.1%}</p>', unsafe_allow_html=True)

    with col3:
        error_rate = df_sut['num_errors'].sum() / df_sut['num_tests'].sum() * 100
        st.metric(
            "Error Rate",
            f"{error_rate:.1%}",
            delta=None,
            help="Percentage of tests with errors",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["error"]}; font-weight: bold; text-align: center;">{error_rate:.1%}</p>', unsafe_allow_html=True)

        skip_rate = df_sut['num_skips'].sum() / df_sut['num_tests'].sum() * 100
        st.metric(
            "Skip Rate",
            f"{skip_rate:.1%}",
            delta=None,
            help="Percentage of skipped tests",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["skipped"]}; font-weight: bold; text-align: center;">{skip_rate:.1%}</p>', unsafe_allow_html=True)

    with col4:
        warning_rate = df_sut['num_xfails'].sum() / df_sut['num_tests'].sum() * 100
        st.metric(
            "Warning Rate",
            f"{warning_rate:.1%}",
            delta=None,
            help="Percentage of tests with warnings",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["warnings"]}; font-weight: bold; text-align: center;">{warning_rate:.1%}</p>', unsafe_allow_html=True)

        xfail_rate = df_sut['num_xpasses'].sum() / df_sut['num_tests'].sum() * 100
        st.metric(
            "XFail Rate",
            f"{xfail_rate:.1%}",
            delta=None,
            help="Percentage of expected failures",
            delta_color="off"
        )
        st.markdown(f'<p style="color: {OUTCOME_COLORS["xfailed"]}; font-weight: bold; text-align: center;">{xfail_rate:.1%}</p>', unsafe_allow_html=True)

    # Pass/fail trend
    st.markdown("### Pass/Fail Trend")
    st.plotly_chart(plot_sut_pass_fail_trend(df_sut, selected_sut, viz_settings), use_container_width=True)

    # Recent sessions
    st.markdown("### Recent Sessions")
    recent_df = df_sut.sort_values('start_time', ascending=False).head(10)
    st.dataframe(recent_df[['session_id', 'start_time', 'num_tests', 'num_passes', 'num_failures', 'num_errors', 'pass_rate']])

elif page == "Session Details":
    st.title("📝 Session Details")

    # Filter data for selected SUT
    df_sut = df[df['sut_id'] == selected_sut]

    # Session selector
    sessions = df_sut.sort_values('start_time', ascending=False)
    session_options = [f"{row['session_id']} - {format_datetime(row['start_time'])}" for _, row in sessions.iterrows()]

    if session_options:
        selected_session = st.selectbox("Select Session", session_options)
        session_id = selected_session.split(" - ")[0]
        session = df_sut[df_sut['session_id'] == session_id].iloc[0]

        # Display session details
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### Session Information")
            st.write("**Session ID:**", session['session_id'])
            st.write("**Start Time:**", format_datetime(session['start_time']))
            st.write("**Duration:**", f"{session['duration']:.2f}s")
            st.write("**SUT ID:**", session['sut_id'])

        with col2:
            st.markdown("### Test Results")
            st.write("**Total Tests:**", session['num_tests'])
            st.write("**Passed:**", session['num_passes'])
            st.write("**Failed:**", session['num_failures'])
            st.write("**Errors:**", session['num_errors'])
            st.write("**Skipped:**", session['num_skips'])
            st.write("**Pass Rate:**", f"{session['pass_rate']:.1f}%")

        # Test results visualization
        st.plotly_chart(plot_test_results_trend(df_sut, viz_settings), use_container_width=True)
    else:
        st.warning("No sessions found for the selected SUT in the current time window.")

elif page == "Session Comparison":
    st.title("🔄 Session Comparison")

    # Load test results and join with session data
    results_df = load_test_results()
    sessions_df = load_session_data()

    # Only show sessions that have test results
    sessions_with_results = results_df['session_id'].unique()
    sessions_df = sessions_df[sessions_df['id'].isin(sessions_with_results)]

    if sessions_df.empty:
        st.error("No sessions with test results found in the database.")
        st.stop()

    # Debug info (collapsed by default)
    with st.expander("Debug Info - Raw Data"):
        st.write("Results DataFrame shape:", results_df.shape)
        st.write("Results DataFrame columns:", results_df.columns.tolist())
        st.write("Sample of results_df:", results_df[['session_id', 'test_id', 'outcome']].head())

        st.write("\nSessions DataFrame shape:", sessions_df.shape)
        st.write("Sessions DataFrame columns:", sessions_df.columns.tolist())
        st.write("Sample of sessions_df:", sessions_df[['id', 'session_id', 'sut_id']].head())

    # Create session info for selection
    sessions_df['session_date'] = sessions_df['start_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
    sessions_df['session_info'] = sessions_df.apply(
        lambda x: f"{x['session_id']} ({x['session_date']} - {x['sut_id']})",
        axis=1
    )

    # Session selection
    st.markdown("### Select Sessions to Compare")
    st.markdown("Choose 2 or more test sessions to compare their results side by side.")

    session_options = sorted(sessions_df['session_info'].unique())
    # with st.expander("Debug - Available Sessions"):
    #     st.write("Number of sessions:", len(session_options))
    #     if len(session_options) > 0:
    #         st.write("First few options:", session_options[:3])
    #         st.write("Sample of sessions data:", sessions_df[['id', 'session_id', 'session_info']].head())

    selected_sessions = st.multiselect(
        "Select Sessions",
        options=session_options,
        help="Select multiple sessions to compare",
        key="session_multiselect"
    )

    if len(selected_sessions) < 2:
        st.warning("Please select at least 2 sessions to compare.")
        st.stop()

    # Extract session IDs from the selection and get corresponding database IDs
    selected_session_names = []
    for session_info in selected_sessions:
        # The session ID is everything up to the first parenthesis
        session_id = session_info.split(" (")[0].strip()
        selected_session_names.append(session_id)

    selected_internal_ids = sessions_df[sessions_df['session_id'].isin(selected_session_names)]['id'].tolist()

    with st.expander("Debug - Selected Sessions"):
        st.write("Selected session info strings:", selected_sessions)
        st.write("Extracted session names:", selected_session_names)
        st.write("Found internal IDs:", selected_internal_ids)
        st.write("\nMatching rows in sessions_df:")
        st.write(sessions_df[sessions_df['session_id'].isin(selected_session_names)][['id', 'session_id', 'session_info']])

    # Filter test results for selected sessions using internal IDs
    results_df = results_df[results_df['session_id'].isin(selected_internal_ids)]
    with st.expander("Debug - Filtered Results"):
        st.write("Filtered results shape:", results_df.shape)
        st.write("All session IDs in results:", results_df['session_id'].unique().tolist())
        if not results_df.empty:
            st.write("Sample of filtered results:")
            st.write(results_df[['session_id', 'test_id', 'outcome']].head())
            matching_sessions = sessions_df[sessions_df['id'].isin(results_df['session_id'].unique())]
            st.write("\nMatching sessions:")
            st.write(matching_sessions[['id', 'session_id', 'sut_id']])

    if results_df.empty:
        st.error("No test results found for the selected sessions.")
        st.stop()

    # Calculate metrics for each session
    metrics_data = []
    session_id_map = sessions_df[['id', 'session_id']].set_index('id')['session_id']

    for internal_id in results_df['session_id'].unique():
        session_results = results_df[results_df['session_id'] == internal_id]
        session_info = sessions_df[sessions_df['id'] == internal_id].iloc[0]

        total_tests = len(session_results)
        metrics = {
            'session_id': session_info['session_id'],  # Use the user-facing session ID
            'sut_id': session_info['sut_id'],
            'start_time': session_info['start_time'],
            'total_tests': total_tests,
            'passed': sum(session_results['outcome'] == 'PASSED'),
            'failed': sum(session_results['outcome'] == 'FAILED'),
            'error': sum(session_results['outcome'] == 'ERROR'),
            'skipped': sum(session_results['outcome'] == 'SKIPPED'),
            'xfailed': sum(session_results['outcome'] == 'XFAILED'),
            'xpassed': sum(session_results['outcome'] == 'XPASSED'),
            'warnings': sum(session_results['outcome'] == 'WARNING')
        }
        metrics_data.append(metrics)

    metrics_df = pd.DataFrame(metrics_data)

    # Create stacked bar chart
    st.markdown("### Test Results Comparison")

    # Prepare data for plotting
    plot_data = []
    categories = ['passed', 'failed', 'error', 'skipped', 'xfailed', 'xpassed', 'warnings']
    colors = {
        'passed': OUTCOME_COLORS['passed'],
        'failed': OUTCOME_COLORS['failed'],
        'error': OUTCOME_COLORS['error'],
        'skipped': OUTCOME_COLORS['skipped'],
        'xfailed': OUTCOME_COLORS['xfailed'],
        'xpassed': OUTCOME_COLORS['xpassed'],
        'warnings': OUTCOME_COLORS['warnings']
    }

    for category in categories:
        for _, row in metrics_df.iterrows():
            session_label = f"{row['session_id']}<br>{row['sut_id']}<br>{row['start_time'].strftime('%Y-%m-%d %H:%M')}"
            plot_data.append({
                'Session': session_label,
                'Count': row[category],
                'Category': category.title(),
                'Percentage': (row[category] / row['total_tests']) * 100 if row['total_tests'] > 0 else 0
            })

    plot_df = pd.DataFrame(plot_data)

    # Create two plots side by side
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Absolute Counts")
        fig1 = px.bar(
            plot_df,
            x='Session',
            y='Count',
            color='Category',
            color_discrete_map=colors,
            title='Test Results by Count',
            labels={'Count': 'Number of Tests', 'Session': ''},
            category_orders={'Category': [c.title() for c in categories]},
        )
        fig1.update_layout(
            barmode='stack',
            showlegend=True,
            xaxis={'tickangle': 45},
            height=500
        )
        st.plotly_chart(fig1, use_container_width=True)

    with col2:
        st.markdown("#### Percentages")
        fig2 = px.bar(
            plot_df,
            x='Session',
            y='Percentage',
            color='Category',
            color_discrete_map=colors,
            title='Test Results by Percentage',
            labels={'Percentage': 'Percentage of Tests', 'Session': ''},
            category_orders={'Category': [c.title() for c in categories]},
        )
        fig2.update_layout(
            barmode='stack',
            showlegend=True,
            xaxis={'tickangle': 45},
            height=500
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Show detailed metrics table
    st.markdown("### Detailed Metrics")

    display_cols = [
        'session_id', 'sut_id', 'start_time', 'total_tests',
        'passed', 'failed', 'error', 'skipped', 'xfailed', 'xpassed', 'warnings'
    ]

    formatted_df = metrics_df[display_cols].copy()
    formatted_df['start_time'] = formatted_df['start_time'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Create style with right-aligned numeric columns
    style = formatted_df.style

    # Get list of numeric columns that exist in the dataframe
    numeric_columns = formatted_df.select_dtypes(include=['int64', 'float64']).columns

    # Center align all columns
    style.set_properties(**{
        'text-align': 'center',
        'padding-left': '10px',
        'padding-right': '10px'
    })

    # Add colors to each column that exists
    for col in formatted_df.columns:
        if col in OUTCOME_COLORS:
            style.set_properties(**{
                'color': 'white' if col in WHITE_TEXT_OUTCOMES else 'black',
                'background-color': OUTCOME_COLORS[col],
                'font-weight': 'bold'
            }, subset=[col])

    # Center align all headers
    style.set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center'), ('padding-left', '10px'), ('padding-right', '10px')]}
    ])

    st.dataframe(
        style,
        use_container_width=True,
        hide_index=True,
    )

elif page == "Test Transitions":
    st.title("↔️ Test Transitions")

    # Filter data for selected SUT
    if selected_sut != "All SUTs":
        df = df[df['sut_id'] == selected_sut]

    # Identify and display transitions
    fail_to_pass, pass_to_fail = identify_test_transitions(df, n_runs=n_runs)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🎉 Fixed Tests (FAIL → PASS)")
        if not fail_to_pass.empty:
            st.dataframe(fail_to_pass[['test_id', 'last_run_time', 'previous_runs']])
        else:
            st.info("No tests have transitioned from FAIL to PASS in the selected time window.")

    with col2:
        st.markdown("### ⚠️ Regression Tests (PASS → FAIL)")
        if not pass_to_fail.empty:
            st.dataframe(pass_to_fail[['test_id', 'last_run_time', 'previous_runs']])
        else:
            st.info("No tests have transitioned from PASS to FAIL in the selected time window.")

elif page == "Flaky Tests":
    st.title("🔄 Flaky Tests")

    # Filter data for selected SUT
    if selected_sut != "All SUTs":
        df = df[df['sut_id'] == selected_sut]

    # Add explanation of flaky test detection
    st.markdown("""
        ### Flaky Test Definition
        A test is considered flaky if it meets these criteria:
        1. Has been run at least N times (minimum runs)
        2. Has at least X% passes AND at least X% failures (flaky threshold)

        Adjust the parameters below to change how flaky tests are detected.
    """)

    # Identify and display flaky tests
    flaky_tests = identify_flaky_tests(df, min_runs=min_runs, flaky_threshold=flaky_threshold)

    if not flaky_tests.empty:
        st.markdown(f"Found {len(flaky_tests)} flaky tests:")
        st.dataframe(flaky_tests[[
            'test_id',
            'total_runs',
            'pass_rate',
            'fail_rate',
            'suts_affected',
            'last_seen',
            'first_seen',
            'duration_days'
        ]])
    else:
        st.info("No flaky tests found with the current parameters.")

    # Display absolute counts
    st.markdown("### Absolute Counts")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["total"]}; font-weight: bold; text-align: center;">Total Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["total"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].sum():,}</p>', unsafe_allow_html=True)

        st.markdown(f'<p style="color: {OUTCOME_COLORS["passed"]}; font-weight: bold; text-align: center;">Passed Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["passed"]}; font-weight: bold; text-align: center;">{flaky_tests["pass_rate"].sum():,}</p>', unsafe_allow_html=True)

    with col2:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["failed"]}; font-weight: bold; text-align: center;">Failed Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["failed"]}; font-weight: bold; text-align: center;">{flaky_tests["fail_rate"].sum():,}</p>', unsafe_allow_html=True)

        st.markdown(f'<p style="color: {OUTCOME_COLORS["error"]}; font-weight: bold; text-align: center;">Error Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["error"]}; font-weight: bold; text-align: center;">{flaky_tests["fail_rate"].sum():,}</p>', unsafe_allow_html=True)

    with col3:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["skipped"]}; font-weight: bold; text-align: center;">Skipped Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["skipped"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].sum():,}</p>', unsafe_allow_html=True)

        st.markdown(f'<p style="color: {OUTCOME_COLORS["xfailed"]}; font-weight: bold; text-align: center;">XFailed Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["xfailed"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].sum():,}</p>', unsafe_allow_html=True)

    with col4:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["xpassed"]}; font-weight: bold; text-align: center;">XPassed Tests</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["xpassed"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].sum():,}</p>', unsafe_allow_html=True)

        st.markdown(f'<p style="color: {OUTCOME_COLORS["warnings"]}; font-weight: bold; text-align: center;">Tests with Warnings</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["warnings"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].sum():,}</p>', unsafe_allow_html=True)

    # Display percentages
    st.markdown("### Percentages")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["passed"]}; font-weight: bold; text-align: center;">Pass Rate</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["passed"]}; font-weight: bold; text-align: center;">{flaky_tests["pass_rate"].mean():.1%}</p>', unsafe_allow_html=True)

    with col2:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["failed"]}; font-weight: bold; text-align: center;">Fail Rate</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["failed"]}; font-weight: bold; text-align: center;">{flaky_tests["fail_rate"].mean():.1%}</p>', unsafe_allow_html=True)

    with col3:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["error"]}; font-weight: bold; text-align: center;">Error Rate</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["error"]}; font-weight: bold; text-align: center;">{flaky_tests["fail_rate"].mean():.1%}</p>', unsafe_allow_html=True)

    with col4:
        st.markdown(f'<p style="color: {OUTCOME_COLORS["skipped"]}; font-weight: bold; text-align: center;">Skip Rate</p>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: {OUTCOME_COLORS["skipped"]}; font-weight: bold; text-align: center;">{flaky_tests["total_runs"].mean():.1%}</p>', unsafe_allow_html=True)
