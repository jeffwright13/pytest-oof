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
    .metric-good { color: #28a745 !important; }
    .metric-bad { color: #dc3545 !important; }
    .metric-neutral { color: #6c757d !important; }

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
    # Look for the database in the package directory first
    package_dir = Path(__file__).parent.parent
    db_path = package_dir / "oof/oof-results.db"

    # If not found, look in the current directory
    if not db_path.exists():
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
            session_id, start_time, end_time, duration,
            sut_id, num_tests, num_passes, num_failures,
            num_errors, num_skips, num_xfails, num_xpasses
        FROM test_sessions
        ORDER BY start_time DESC
        LIMIT 10000
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
            ts.session_id,
            ts.start_time,
            ts.sut_id
        FROM test_results tr
        JOIN test_sessions ts ON tr.session_id = ts.id
        ORDER BY ts.start_time DESC
        LIMIT 10000
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
                color="#28a745",
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
                color="#dc3545",
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
                color="#fd7e14",
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
                color="#6c757d",
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
                color="#9932cc",
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
                color="#ffd700",
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
                color="#28a745",
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
                color="#dc3545",
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
        flaky_threshold: Threshold for considering a test flaky (0.2 means both pass and fail rates > 20%)

    Returns:
        DataFrame with flaky test information
    """
    flaky_tests = []

    # Group by test_id and analyze patterns
    for test_id, group in df.groupby("test_id"):
        total_runs = len(group)
        if total_runs < min_runs:
            continue

        passes = sum(group["outcome"] == "passed")
        failures = total_runs - passes

        pass_rate = passes / total_runs
        fail_rate = failures / total_runs

        # A test is considered flaky if both its pass and fail rates exceed the threshold
        if min(pass_rate, fail_rate) > flaky_threshold:
            suts_affected = group["sut_id"].nunique()
            last_seen = group["start_time"].max()

            flaky_tests.append(
                {
                    "test_id": test_id,
                    "total_runs": total_runs,
                    "pass_rate": pass_rate,
                    "fail_rate": fail_rate,
                    "suts_affected": suts_affected,
                    "last_seen": last_seen,
                }
            )

    if not flaky_tests:
        return pd.DataFrame(
            columns=[
                "test_id",
                "total_runs",
                "pass_rate",
                "fail_rate",
                "suts_affected",
                "last_seen",
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
            line=dict(color="#28a745", width=2),
        )
    )

    # Add failure rate trace
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["failure_rate"],
            name="Failure Rate",
            mode="lines+markers",
            line=dict(color="#dc3545", width=2),
        )
    )

    # Add total tests trace on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=daily_stats["date"],
            y=daily_stats["num_tests"],
            name="Total Tests",
            mode="lines+markers",
            line=dict(color="#17a2b8", width=2),
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
                line=dict(color=color, width=2),
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
    st.markdown("# pytest-oof analysis\n")

    # Database info - display only once at the top
    db_path = ensure_db_exists()
    st.markdown(f" Using database: `{os.path.basename(db_path)}`")
    
    st.divider()

    # Page selection
    st.markdown("### Navigation")
    page = st.selectbox(
        "Select Page",
        ["Overview", "Session Details", "Session Comparison", "Test Transitions", "Flaky Tests"]
    )

    st.divider()

    # Time window selection
    st.markdown("### Time Window")
    window_options = {
        "Last 24 Hours": timedelta(days=1),
        "Last 7 Days": timedelta(days=7),
        "Last 30 Days": timedelta(days=30),
        "All Time": None
    }
    selected_window = st.selectbox("Select Time Window", list(window_options.keys()))

    # Load and filter data based on time window and page type
    df = load_session_data() if page in ["Overview", "Session Details", "Session Comparison"] else load_test_results()

    if window_options[selected_window]:
        cutoff_time = pd.Timestamp.now(tz='UTC') - window_options[selected_window]
        df = df[df['start_time'] >= cutoff_time]

    # Get unique SUTs and add selector
    suts = sorted(df['sut_id'].unique())
    if not suts:
        st.warning("No test data available for the selected time window.")
        st.stop()

    st.divider()

    st.markdown("### SUT Selection")
    if page == "Flaky Tests":
        suts = ["All SUTs"] + suts
        selected_sut = st.selectbox(
            "Select System Under Test",
            suts,
            format_func=lambda x: x
        )
    else:
        selected_sut = st.selectbox(
            "Select System Under Test",
            suts,
            format_func=lambda x: f"SUT: {x}"
        )

    # Additional settings based on page
    if page in ["Test Transitions", "Flaky Tests"]:
        st.divider()
        
        if page == "Test Transitions":
            st.markdown("### Transition Settings")
            n_runs = st.slider("Number of previous runs to check", 2, 10, 5)
        else:  # Flaky Tests
            st.markdown("### Flakiness Parameters")
            min_runs = st.slider("Minimum runs required", 2, 20, 5)
            flaky_threshold = st.slider(
                "Flakiness threshold",
                0.1, 0.5, 0.2, 0.05,
                help="Minimum ratio of both passes and fails to consider a test flaky"
            )

    st.divider()

    # Visualization settings
    st.markdown("### Visualization Settings")
    viz_settings = {
        "line_shape": st.selectbox(
            "Line Shape",
            ["linear", "spline", "hv", "vh", "hvh", "vhv"],
            help="Shape of the line connecting data points"
        ),
        "line_width": st.slider(
            "Line Width",
            1, 5, 2,
            help="Width of the plot lines in pixels"
        ),
        "show_markers": st.checkbox(
            "Show Markers",
            True,
            help="Show data point markers on the lines"
        )
    }

    # Add smoothing only if spline is selected
    if viz_settings["line_shape"] == "spline":
        viz_settings["smoothing"] = st.slider(
            "Smoothing Factor",
            0.0, 1.3, 0.5, 0.1,
            help="Higher values make the line smoother (0 = no smoothing, 1.3 = maximum smoothing)"
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
            len(df_sut),
            delta=f"{len(df_sut[df_sut.start_time >= df_sut.start_time.max() - pd.Timedelta(days=1)])} today"
        )
    with col2:
        total_tests = df_sut['num_tests'].sum()
        st.metric(
            "Total Tests",
            total_tests,
            delta=f"{df_sut[df_sut.start_time >= df_sut.start_time.max() - pd.Timedelta(days=1)].num_tests.sum()} today"
        )
    with col3:
        pass_rate = df_sut['pass_rate'].mean()
        # Calculate last week's pass rate
        last_week_mask = df_sut.start_time < df_sut.start_time.max() - pd.Timedelta(days=7)
        last_week_rate = df_sut[last_week_mask]['pass_rate'].mean() if df_sut[last_week_mask].shape[0] > 0 else pass_rate
        delta = pass_rate - last_week_rate if not pd.isna(last_week_rate) else None
        delta_str = f"{delta:+.1f}%" if delta is not None else None
        st.metric(
            "Pass Rate",
            f"{pass_rate:.1f}%",
            delta=delta_str
        )
    with col4:
        failed_tests = df_sut['num_failures'].sum() + df_sut['num_errors'].sum()
        st.metric(
            "Failed Tests",
            failed_tests,
            delta=f"{-1 * (df_sut[df_sut.start_time >= df_sut.start_time.max() - pd.Timedelta(days=1)]['num_failures'].sum() + df_sut[df_sut.start_time >= df_sut.start_time.max() - pd.Timedelta(days=1)]['num_errors'].sum())} today",
            delta_color="inverse"
        )

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

    # Filter data for selected SUT
    df_sut = df[df['sut_id'] == selected_sut]

    # Session selector
    sessions = df_sut.sort_values('start_time', ascending=False)
    session_options = [f"{row['session_id']} - {format_datetime(row['start_time'])}" for _, row in sessions.iterrows()]

    if len(session_options) >= 2:
        selected_sessions = st.multiselect(
            "Select Sessions to Compare (2-4)",
            options=session_options,
            max_selections=4
        )

        if len(selected_sessions) >= 2:
            # Get selected session data
            session_ids = [s.split(" - ")[0] for s in selected_sessions]
            comparison_df = df_sut[df_sut['session_id'].isin(session_ids)]

            # Display comparison
            st.plotly_chart(plot_test_results_trend(comparison_df, viz_settings), use_container_width=True)
    else:
        st.warning("Need at least 2 sessions to compare. Run more tests!")

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

    # Identify and display flaky tests
    flaky_tests = identify_flaky_tests(df, min_runs=min_runs, flaky_threshold=flaky_threshold)

    if not flaky_tests.empty:
        st.dataframe(flaky_tests[[
            'test_id',
            'total_runs',
            'pass_rate',
            'fail_rate',
            'suts_affected',
            'last_seen'
        ]])
    else:
        st.info("No flaky tests found with the current parameters.")
