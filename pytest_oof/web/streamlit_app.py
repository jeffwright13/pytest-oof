"""Streamlit dashboard for pytest-oof test analysis."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pytest_oof.db import export_results, init_db

st.set_page_config(
    page_title="pytest-oof Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

    st.sidebar.info(f"Using database: {db_path}")
    return db_path


def format_datetime(dt):
    """Format datetime handling NaT values."""
    if pd.isna(dt):
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


@st.cache_data(ttl=10)  # Cache data for 10 seconds
def load_session_data():
    """Load test session data into a pandas DataFrame."""
    db_path = ensure_db_exists()

    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            """
            SELECT
                session_id,
                start_time,
                end_time,
                duration,
                sut_id,
                num_tests,
                num_passes,
                num_failures,
                num_errors,
                num_skips
            FROM test_sessions
            ORDER BY start_time DESC
            """,
            conn,
            parse_dates=[
                "start_time",
                "end_time",
            ],  # Explicitly parse these columns as datetime
        )
        conn.close()

        # Fill NaN/None values
        df["sut_id"] = df["sut_id"].fillna("")
        df["duration"] = df["duration"].fillna(0)
        df["num_tests"] = df["num_tests"].fillna(0).astype(int)
        df["num_passes"] = df["num_passes"].fillna(0).astype(int)
        df["num_failures"] = df["num_failures"].fillna(0).astype(int)
        df["num_errors"] = df["num_errors"].fillna(0).astype(int)
        df["num_skips"] = df["num_skips"].fillna(0).astype(int)

        # Calculate pass rate
        df["pass_rate"] = (df["num_passes"] / df["num_tests"] * 100).fillna(0)

        # Ensure datetime columns are properly formatted
        df["start_time"] = pd.to_datetime(df["start_time"])
        df["end_time"] = pd.to_datetime(df["end_time"])

        return df
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error


def plot_test_results_trend(df):
    """Plot test results trend over time."""
    df_sorted = df.sort_values("start_time")

    fig = go.Figure()

    # Add traces for each metric
    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_passes"],
            name="Passed",
            line=dict(color="#28a745", width=2),
            fill="tonexty",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_failures"],
            name="Failed",
            line=dict(color="#dc3545", width=2),
            fill="tonexty",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_errors"],
            name="Errors",
            line=dict(color="#fd7e14", width=2),
            fill="tonexty",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_skips"],
            name="Skipped",
            line=dict(color="#6c757d", width=2),
            fill="tonexty",
        )
    )

    fig.update_layout(
        title="Test Results Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Tests",
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    return fig


# Sidebar
with st.sidebar:
    st.title("pytest-oof Analysis")
    page = st.radio(
        "Navigation", ["Dashboard", "Session Details", "Compare Sessions", "Trends"]
    )

    # Time range filter
    st.subheader("Time Range")
    range_type = st.selectbox(
        "Filter by", ["All Time", "Last N Days", "Date Range"], key="time_range_type"
    )

    if range_type == "Last N Days":
        days = st.number_input("Number of days", min_value=1, value=7)
    elif range_type == "Date Range":
        start_date = st.date_input("Start Date")
        end_date = st.date_input("End Date")

# Load data once
df = load_session_data()

# Apply time range filter
if not df.empty:
    if range_type == "Last N Days":
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df = df[df["start_time"] >= cutoff]
    elif range_type == "Date Range":
        df = df[
            (df["start_time"].dt.date >= start_date)
            & (df["start_time"].dt.date <= end_date)
        ]

if df.empty:
    st.write("## Welcome to pytest-oof Analysis!")
    st.write(
        """
    To get started:
    1. Run some tests with pytest-oof
    2. The results will be automatically stored in `test_results.db`
    3. Come back here to analyze your test results!

    Example:
    ```bash
    pytest --oof  # This will store results in test_results.db
    ```
    """
    )
else:
    if page == "Dashboard":
        st.title("Test Results Dashboard")

        # Summary metrics with color coding
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Total Sessions",
                len(df),
                delta=f"{len(df) - len(df[df.start_time < df.start_time.max() - pd.Timedelta(days=1)])} today",
            )

        total_tests = df["num_tests"].sum()
        with col2:
            st.metric(
                "Total Tests",
                total_tests,
                delta=f"{df[df.start_time >= df.start_time.max() - pd.Timedelta(days=1)].num_tests.sum()} today",
            )

        pass_rate = df["pass_rate"].mean()
        with col3:
            st.metric(
                "Overall Pass Rate",
                f"{pass_rate:.1f}%",
                delta=f"{(df['pass_rate'].mean() - df[df.start_time < df.start_time.max() - pd.Timedelta(days=7)]['pass_rate'].mean()):.1f}pp vs last week",
            )

        failed_tests = df["num_failures"].sum() + df["num_errors"].sum()
        with col4:
            st.metric(
                "Failed Tests",
                failed_tests,
                delta=f"{-1 * (df[df.start_time >= df.start_time.max() - pd.Timedelta(days=1)]['num_failures'].sum() + df[df.start_time >= df.start_time.max() - pd.Timedelta(days=1)]['num_errors'].sum())} today",
                delta_color="inverse",
            )

        # Test results trend
        st.plotly_chart(plot_test_results_trend(df), use_container_width=True)

        # Recent sessions table with enhanced formatting
        st.subheader("Recent Test Sessions")
        recent_df = df.sort_values("start_time", ascending=False).head(10)

        def color_pass_rate(val):
            if val >= 90:
                return "color: #28a745"
            elif val >= 75:
                return "color: #fd7e14"
            return "color: #dc3545"

        styled_df = (
            recent_df[
                [
                    "session_id",
                    "start_time",
                    "num_tests",
                    "num_passes",
                    "num_failures",
                    "num_errors",
                    "num_skips",
                    "pass_rate",
                    "sut_id",
                ]
            ]
            .style.format({"pass_rate": "{:.1f}%", "start_time": format_datetime})
            .map(color_pass_rate, subset=["pass_rate"])
        )

        st.dataframe(styled_df, use_container_width=True)

        # Pass rate trend
        if len(df) > 1:  # Only show trend if we have multiple sessions
            st.subheader("Pass Rate Trend")
            fig = px.line(
                df.sort_values("start_time"),
                x="start_time",
                y="pass_rate",
                title="Test Pass Rate Over Time",
            )
            st.plotly_chart(fig, use_container_width=True)

    elif page == "Session Details":
        st.title("Session Details")

        # Session selector with search
        st.markdown("### Select Test Session")
        search = st.text_input("Search by SUT ID or Session ID", "")

        filtered_df = df
        if search:
            filtered_df = df[
                df["sut_id"].str.contains(search, case=False)
                | df["session_id"].str.contains(search, case=False)
            ]

        session_options = [
            f"{row['session_id']} - {format_datetime(row['start_time'])} ({row['sut_id']})"
            for _, row in filtered_df.sort_values(
                "start_time", ascending=False
            ).iterrows()
        ]

        if not session_options:
            st.warning("No sessions match your search criteria.")
        else:
            selected = st.selectbox("Select Session", session_options)

            if selected:
                session_id = selected.split(" - ")[0]
                session = df[df["session_id"] == session_id].iloc[0]

                # Session info in an expander
                with st.expander("Session Information", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("#### Test Session")
                        st.write("**ID:**", session["session_id"])
                        st.write(
                            "**Start Time:**", format_datetime(session["start_time"])
                        )
                        st.write(
                            "**Duration:**",
                            f"{session['duration']:.2f}s"
                            if pd.notna(session["duration"])
                            else "N/A",
                        )

                    with col2:
                        st.markdown("#### System Under Test")
                        st.write("**SUT ID:**", session["sut_id"])
                        st.write("**SUT Type:**", "N/A")  # Removed session["sut_type"]
                        st.write(
                            "**Python Version:**", "N/A"
                        )  # Removed session["python_version"]

                    with col3:
                        st.markdown("#### Test Results")
                        st.write("**Total Tests:**", session["num_tests"])
                        st.write("**Pass Rate:**", f"{session['pass_rate']:.1f}%")
                        st.write(
                            "**Duration:**",
                            f"{session['duration']:.2f}s"
                            if pd.notna(session["duration"])
                            else "N/A",
                        )

                # Test results visualization
                st.markdown("### Test Results")

                col1, col2 = st.columns(2)
                with col1:
                    # Pie chart
                    fig_pie = go.Figure(
                        data=[
                            go.Pie(
                                labels=["Passed", "Failed", "Errors", "Skipped"],
                                values=[
                                    session["num_passes"],
                                    session["num_failures"],
                                    session["num_errors"],
                                    session["num_skips"],
                                ],
                                hole=0.3,
                                marker_colors=[
                                    "#28a745",
                                    "#dc3545",
                                    "#fd7e14",
                                    "#6c757d",
                                ],
                            )
                        ]
                    )
                    fig_pie.update_layout(title="Test Outcome Distribution")
                    st.plotly_chart(fig_pie, use_container_width=True)

                with col2:
                    # Bar chart
                    fig_bar = go.Figure(
                        data=[
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_passes"]],
                                name="Passed",
                                marker_color="#28a745",
                            ),
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_failures"]],
                                name="Failed",
                                marker_color="#dc3545",
                            ),
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_errors"]],
                                name="Errors",
                                marker_color="#fd7e14",
                            ),
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_skips"]],
                                name="Skipped",
                                marker_color="#6c757d",
                            ),
                        ]
                    )
                    fig_bar.update_layout(
                        barmode="stack", title="Test Results Breakdown", showlegend=True
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

    elif page == "Compare Sessions":
        st.title("Compare Test Sessions")

        if len(df) < 2:
            st.warning("Need at least 2 test sessions to compare. Run more tests!")
        else:
            # Session selection with filters
            st.markdown("### Select Sessions to Compare")

            col1, col2 = st.columns(2)
            with col1:
                sut_filter = st.multiselect(
                    "Filter by SUT ID",
                    options=sorted(df["sut_id"].unique()),
                    default=[],
                )

            with col2:
                date_range = st.date_input(
                    "Filter by Date Range",
                    value=(
                        df["start_time"].min().date(),
                        df["start_time"].max().date(),
                    ),
                )

            # Apply filters
            filtered_df = df
            if sut_filter:
                filtered_df = filtered_df[filtered_df["sut_id"].isin(sut_filter)]

            if isinstance(date_range, tuple):
                start_date, end_date = date_range
                filtered_df = filtered_df[
                    (filtered_df["start_time"].dt.date >= start_date)
                    & (filtered_df["start_time"].dt.date <= end_date)
                ]

            # Session selection
            session_options = [
                f"{row['session_id']} - {format_datetime(row['start_time'])} ({row['sut_id']})"
                for _, row in filtered_df.sort_values(
                    "start_time", ascending=False
                ).iterrows()
            ]

            selected_sessions = st.multiselect(
                "Select Sessions to Compare (2-4)",
                options=session_options,
                max_selections=4,
            )

            if len(selected_sessions) >= 2:
                # Get selected session data
                selected_data = []
                for selected in selected_sessions:
                    session_id = selected.split(" - ")[0]
                    session = df[df["session_id"] == session_id].iloc[0]
                    selected_data.append(session)

                # Comparison visualizations
                st.markdown("### Session Comparison")

                # Metrics comparison
                metrics = [
                    ("num_tests", "Total Tests"),
                    ("num_passes", "Passed Tests"),
                    ("num_failures", "Failed Tests"),
                    ("num_errors", "Test Errors"),
                    ("num_skips", "Skipped Tests"),
                    ("pass_rate", "Pass Rate (%)"),
                ]

                for metric, label in metrics:
                    st.markdown(f"#### {label}")
                    cols = st.columns(len(selected_data))

                    baseline = None
                    for i, (col, session) in enumerate(zip(cols, selected_data)):
                        with col:
                            value = session[metric]
                            if "rate" in metric:
                                formatted_value = f"{value:.1f}%"
                                if i > 0:
                                    delta = value - baseline
                                    st.metric(
                                        session["session_id"],
                                        formatted_value,
                                        f"{delta:+.1f}pp",
                                        delta_color="normal"
                                        if abs(delta) < 1
                                        else "inverse"
                                        if delta < 0
                                        else "normal",
                                    )
                                else:
                                    st.metric(session["session_id"], formatted_value)
                                    baseline = value
                            else:
                                if i > 0:
                                    delta = value - baseline
                                    st.metric(
                                        session["session_id"],
                                        value,
                                        delta,
                                        delta_color="normal"
                                        if abs(delta) < 1
                                        else "inverse"
                                        if delta < 0
                                        else "normal",
                                    )
                                else:
                                    st.metric(session["session_id"], value)
                                    baseline = value

                # Stacked bar comparison
                st.markdown("### Test Results Comparison")

                fig = go.Figure()

                for session in selected_data:
                    fig.add_trace(
                        go.Bar(
                            name=session["session_id"],
                            x=["Passed", "Failed", "Errors", "Skipped"],
                            y=[
                                session["num_passes"],
                                session["num_failures"],
                                session["num_errors"],
                                session["num_skips"],
                            ],
                            text=[
                                session["num_passes"],
                                session["num_failures"],
                                session["num_errors"],
                                session["num_skips"],
                            ],
                            textposition="auto",
                        )
                    )

                fig.update_layout(
                    barmode="group",
                    title="Test Results by Session",
                    xaxis_title="Result Type",
                    yaxis_title="Number of Tests",
                    hovermode="x unified",
                    showlegend=True,
                    legend=dict(
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                    ),
                )

                st.plotly_chart(fig, use_container_width=True)

                # Compare metrics
                for col in [
                    "num_tests",
                    "num_passes",
                    "num_failures",
                    "num_errors",
                    "num_skips",
                ]:
                    with st.container():
                        diff = int(df_compare.iloc[0][col]) - int(
                            df_compare.iloc[1][col]
                        )
                        st.metric(
                            label=col.replace("num_", "").title(),
                            value=int(df_compare.iloc[0][col]),
                            delta=int(diff),
                            delta_color="inverse"
                            if col in ["num_failures", "num_errors", "num_skips"]
                            else "normal",
                        )

                # Compare pass rates
                pass_rate_diff = float(df_compare.iloc[0]["pass_rate"]) - float(
                    df_compare.iloc[1]["pass_rate"]
                )
                st.metric(
                    label="Pass Rate",
                    value=f"{float(df_compare.iloc[0]['pass_rate']):.1f}%",
                    delta=f"{pass_rate_diff:+.1f}%",
                    delta_color="normal",
                )

    else:  # Trends
        st.title("Test Result Trends")

        if len(df) < 2:
            st.warning(
                "Need at least 2 test sessions to analyze trends. Run more tests!"
            )
        else:
            # Time-based analysis
            st.markdown("### Test Results Over Time")

            # Daily aggregation
            df["date"] = df["start_time"].dt.date
            daily_stats = (
                df.groupby("date")
                .agg(
                    {
                        "num_tests": "sum",
                        "num_passes": "sum",
                        "num_failures": "sum",
                        "num_errors": "sum",
                        "num_skips": "sum",
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

            # Pass rate trend
            fig_pass_rate = go.Figure()

            fig_pass_rate.add_trace(
                go.Scatter(
                    x=daily_stats["date"],
                    y=daily_stats["pass_rate"],
                    name="Pass Rate",
                    line=dict(color="#28a745", width=2),
                    mode="lines+markers",
                )
            )

            fig_pass_rate.add_trace(
                go.Scatter(
                    x=daily_stats["date"],
                    y=daily_stats["failure_rate"],
                    name="Failure Rate",
                    line=dict(color="#dc3545", width=2),
                    mode="lines+markers",
                )
            )

            fig_pass_rate.update_layout(
                title="Daily Pass/Failure Rate Trends",
                xaxis_title="Date",
                yaxis_title="Rate (%)",
                hovermode="x unified",
                showlegend=True,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
            )

            st.plotly_chart(fig_pass_rate, use_container_width=True)

            # Test volume analysis
            st.markdown("### Test Volume Analysis")

            fig_volume = go.Figure()

            # Add traces for each metric
            metrics = [
                ("num_tests", "Total Tests", "#17a2b8"),
                ("num_passes", "Passed", "#28a745"),
                ("num_failures", "Failed", "#dc3545"),
                ("num_errors", "Errors", "#fd7e14"),
                ("num_skips", "Skipped", "#6c757d"),
            ]

            for metric, label, color in metrics:
                fig_volume.add_trace(
                    go.Scatter(
                        x=daily_stats["date"],
                        y=daily_stats[metric],
                        name=label,
                        line=dict(color=color, width=2),
                        mode="lines+markers",
                    )
                )

            fig_volume.update_layout(
                title="Daily Test Volume Trends",
                xaxis_title="Date",
                yaxis_title="Number of Tests",
                hovermode="x unified",
                showlegend=True,
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
            )

            st.plotly_chart(fig_volume, use_container_width=True)

            # SUT Analysis
            st.markdown("### System Under Test Analysis")

            sut_stats = (
                df.groupby("sut_id")
                .agg(
                    {
                        "num_tests": "sum",
                        "num_passes": "sum",
                        "num_failures": "sum",
                        "num_errors": "sum",
                        "num_skips": "sum",
                    }
                )
                .reset_index()
            )

            sut_stats["pass_rate"] = (
                sut_stats["num_passes"] / sut_stats["num_tests"] * 100
            )

            # SUT comparison
            fig_sut = go.Figure()

            fig_sut.add_trace(
                go.Bar(
                    x=sut_stats["sut_id"],
                    y=sut_stats["pass_rate"],
                    name="Pass Rate",
                    marker_color="#28a745",
                    text=sut_stats["pass_rate"].round(1).astype(str) + "%",
                    textposition="auto",
                )
            )

            fig_sut.update_layout(
                title="Pass Rate by System Under Test",
                xaxis_title="SUT ID",
                yaxis_title="Pass Rate (%)",
                showlegend=True,
            )

            st.plotly_chart(fig_sut, use_container_width=True)

            # Statistical summary
            st.markdown("### Statistical Summary")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### Pass Rate Statistics")
                stats_df = pd.DataFrame(
                    {
                        "Metric": [
                            "Mean Pass Rate",
                            "Median Pass Rate",
                            "Std Dev",
                            "Min Pass Rate",
                            "Max Pass Rate",
                        ],
                        "Value": [
                            f"{df['pass_rate'].mean():.1f}%",
                            f"{df['pass_rate'].median():.1f}%",
                            f"{df['pass_rate'].std():.1f}%",
                            f"{df['pass_rate'].min():.1f}%",
                            f"{df['pass_rate'].max():.1f}%",
                        ],
                    }
                )
                st.dataframe(stats_df, use_container_width=True)

            with col2:
                st.markdown("#### Test Volume Statistics")
                volume_stats = pd.DataFrame(
                    {
                        "Metric": [
                            "Total Test Runs",
                            "Avg Tests per Run",
                            "Median Tests per Run",
                            "Min Tests per Run",
                            "Max Tests per Run",
                        ],
                        "Value": [
                            len(df),
                            f"{df['num_tests'].mean():.1f}",
                            f"{df['num_tests'].median():.1f}",
                            df["num_tests"].min(),
                            df["num_tests"].max(),
                        ],
                    }
                )
                st.dataframe(volume_stats, use_container_width=True)
