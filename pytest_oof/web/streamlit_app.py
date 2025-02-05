"""Streamlit dashboard for pytest-oof test analysis."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import pytz
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

# Global Plotly theme settings for larger fonts
PLOTLY_LAYOUT = {
    "font": {"size": 15},  # 25% larger than default (12)
    "title_font_size": 20,
    "legend_font_size": 15,
    "xaxis_title_font_size": 15,
    "yaxis_title_font_size": 15
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
st.markdown("""
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
""", unsafe_allow_html=True)


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
            df = pd.read_sql_query(query, conn, parse_dates=['start_time', 'end_time'])
            
            # Ensure timezone awareness
            if df['start_time'].dt.tz is None:
                df['start_time'] = df['start_time'].dt.tz_localize('UTC')
            if df['end_time'].dt.tz is None:
                df['end_time'] = df['end_time'].dt.tz_localize('UTC')
                
            # Fill NaN/None values and convert to native types
            df['sut_id'] = df['sut_id'].fillna('')
            df['duration'] = df['duration'].fillna(0).astype(float)

            # Convert numeric columns to native Python int
            int_columns = ['num_tests', 'num_passes', 'num_failures', 'num_errors', 'num_skips', 'num_xfails', 'num_xpasses']
            for col in int_columns:
                df[col] = df[col].fillna(0).astype('int32').astype(int)

            # Calculate pass rate as float
            df['pass_rate'] = (df['num_passes'] / df['num_tests'] * 100).fillna(0).astype(float)

            return df
    except Exception as e:
        st.error(f"Error loading session data: {str(e)}")
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
            line=dict(color="#28a745", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_failures"],
            name="Failed",
            line=dict(color="#dc3545", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_errors"],
            name="Errors",
            line=dict(color="#fd7e14", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_skips"],
            name="Skipped",
            line=dict(color="#6c757d", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_xfails"],
            name="Expected Failures",
            line=dict(color="#9932cc", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df_sorted["start_time"],
            y=df_sorted["num_xpasses"],
            name="Unexpected Passes",
            line=dict(color="#ffd700", width=2, shape='spline', smoothing=1.3),
            fill="tonexty",
            mode="lines+markers"
        )
    )

    fig.update_layout(
        title="Test Results Over Time",
        xaxis_title="Date",
        yaxis_title="Number of Tests",
        hovermode="x unified",
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT  # Apply global font settings
    )

    return fig


def plot_sut_pass_fail_trend(df, sut_id):
    """Plot pass/fail rate trend for a specific SUT."""
    df_sut = df[df['sut_id'] == sut_id].sort_values('start_time')
    
    fig = go.Figure()
    
    # Calculate pass rate for each session
    df_sut['pass_rate'] = (df_sut['num_passes'] / df_sut['num_tests'] * 100)
    df_sut['fail_rate'] = 100 - df_sut['pass_rate']
    
    # Add pass rate line
    fig.add_trace(
        go.Scatter(
            x=df_sut['start_time'],
            y=df_sut['pass_rate'],
            name='Pass Rate',
            line=dict(color='#28a745', width=2, shape='spline', smoothing=1.3),
            mode='lines+markers'
        )
    )
    
    # Add fail rate line
    fig.add_trace(
        go.Scatter(
            x=df_sut['start_time'],
            y=df_sut['fail_rate'],
            name='Fail Rate',
            line=dict(color='#dc3545', width=2, shape='spline', smoothing=1.3),
            mode='lines+markers'
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
        **PLOTLY_LAYOUT
    )
    
    return fig


# Sidebar
with st.sidebar:
    st.title("pytest-oof Analysis")
    page = st.radio(
        "Navigation", ["Dashboard", "Session Details", "Compare Sessions", "SUT Analysis", "Trends"]
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
                    "num_xfails",
                    "num_xpasses",
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
            fig.update_traces(line_shape='spline', line_smoothing=1.3)
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
                        st.write("**Expected Failures:**", session["num_xfails"])
                        st.write("**Unexpected Passes:**", session["num_xpasses"])

                # Test results visualization
                st.markdown("### Test Results")

                col1, col2 = st.columns(2)
                with col1:
                    # Pie chart
                    fig_pie = go.Figure(
                        data=[
                            go.Pie(
                                labels=["Passed", "Failed", "Errors", "Skipped", "Expected Failures", "Unexpected Passes"],
                                values=[
                                    session["num_passes"],
                                    session["num_failures"],
                                    session["num_errors"],
                                    session["num_skips"],
                                    session["num_xfails"],
                                    session["num_xpasses"],
                                ],
                                hole=0.3,
                                marker_colors=[
                                    "#28a745",
                                    "#dc3545",
                                    "#fd7e14",
                                    "#6c757d",
                                    "#9932cc",
                                    "#ffd700",
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
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_xfails"]],
                                name="Expected Failures",
                                marker_color="#9932cc",
                            ),
                            go.Bar(
                                x=["Tests"],
                                y=[session["num_xpasses"]],
                                name="Unexpected Passes",
                                marker_color="#ffd700",
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
                
                # Create 4 columns for metrics
                col1, col2, col3, col4 = st.columns(4)
                
                # Column 1: Test counts
                with col1:
                    st.metric("Total Tests", selected_data[0]["num_tests"], delta=int(selected_data[1]["num_tests"] - selected_data[0]["num_tests"]))
                    st.metric("Pass Rate", f"{selected_data[0]['pass_rate']:.1f}%", delta=f"{(selected_data[1]['pass_rate'] - selected_data[0]['pass_rate']):.1f}%")
                    st.metric("Duration", f"{selected_data[0]['duration']:.1f}s", delta=f"{(selected_data[1]['duration'] - selected_data[0]['duration']):.1f}s")
                
                # Column 2: Pass/Fail
                with col2:
                    st.metric("Passes", selected_data[0]["num_passes"], delta=int(selected_data[1]["num_passes"] - selected_data[0]["num_passes"]))
                    st.metric("Failures", selected_data[0]["num_failures"], delta=int(selected_data[1]["num_failures"] - selected_data[0]["num_failures"]))
                    st.metric("Errors", selected_data[0]["num_errors"], delta=int(selected_data[1]["num_errors"] - selected_data[0]["num_errors"]))
                
                # Column 3: Skip/XFail
                with col3:
                    st.metric("Skips", selected_data[0]["num_skips"], delta=int(selected_data[1]["num_skips"] - selected_data[0]["num_skips"]))
                    st.metric("Expected Failures", selected_data[0]["num_xfails"], delta=int(selected_data[1]["num_xfails"] - selected_data[0]["num_xfails"]))
                    st.metric("Unexpected Passes", selected_data[0]["num_xpasses"], delta=int(selected_data[1]["num_xpasses"] - selected_data[0]["num_xpasses"]))
                
                # Column 4: Additional Info
                with col4:
                    st.markdown(f"**Session 1 Details**")
                    st.markdown(f"Start: {selected_data[0]['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    st.markdown(f"SUT: {selected_data[0]['sut_id']}")
                    st.markdown(f"\n**Session 2 Details**")
                    st.markdown(f"Start: {selected_data[1]['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    st.markdown(f"SUT: {selected_data[1]['sut_id']}")

                # Stacked bar comparison
                st.markdown("### Test Results Comparison")

                fig = go.Figure()

                for session in selected_data:
                    fig.add_trace(
                        go.Bar(
                            name=session["session_id"],
                            x=["Passed", "Failed", "Errors", "Skipped", "Expected Failures", "Unexpected Passes"],
                            y=[
                                session["num_passes"],
                                session["num_failures"],
                                session["num_errors"],
                                session["num_skips"],
                                session["num_xfails"],
                                session["num_xpasses"],
                            ],
                            text=[
                                session["num_passes"],
                                session["num_failures"],
                                session["num_errors"],
                                session["num_skips"],
                                session["num_xfails"],
                                session["num_xpasses"],
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

    elif page == "SUT Analysis":
        st.title("System Under Test Analysis")

        # Time window selection
        st.sidebar.markdown("### Time Window")
        window_options = {
            "Last 24 Hours": timedelta(days=1),
            "Last 7 Days": timedelta(days=7),
            "Last 30 Days": timedelta(days=30),
            "All Time": None
        }
        selected_window = st.sidebar.selectbox("Select Time Window", list(window_options.keys()))
        
        # Filter data based on time window
        df = load_session_data()
        if window_options[selected_window]:
            cutoff_time = pd.Timestamp.now(pytz.utc) - window_options[selected_window]
            df = df[df['start_time'] >= cutoff_time]
        
        # Get unique SUTs and add selector
        suts = sorted(df['sut_id'].unique())
        if not suts:
            st.warning("No test data available for the selected time window.")
            st.stop()
            
        selected_sut = st.selectbox(
            "Select System Under Test",
            suts,
            format_func=lambda x: f"SUT: {x}"
        )
        
        # Filter data for selected SUT
        df_sut = df[df['sut_id'] == selected_sut]
        
        # Create two columns for the summary metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Sessions", len(df_sut))
        with col2:
            total_tests = df_sut['num_tests'].sum()
            st.metric("Total Tests", total_tests)
        with col3:
            pass_rate = (df_sut['num_passes'].sum() / total_tests * 100) if total_tests > 0 else 0
            st.metric("Overall Pass Rate", f"{pass_rate:.1f}%")
        with col4:
            avg_duration = df_sut['duration'].mean()
            st.metric("Avg Duration", f"{avg_duration:.1f}s")
        
        # Pass/Fail trend chart
        st.markdown("### Pass/Fail Rate Trend")
        
        # Create trend chart
        fig = go.Figure()
        
        # Add traces
        fig.add_trace(
            go.Scatter(
                x=df_sut['start_time'],
                y=df_sut['pass_rate'],
                name='Pass Rate',
                line=dict(color='#28a745', width=2),
                mode='lines+markers'
            )
        )
        
        # Add test count trace on secondary y-axis
        fig.add_trace(
            go.Scatter(
                x=df_sut['start_time'],
                y=df_sut['num_tests'],
                name='Total Tests',
                line=dict(color='#17a2b8', width=2),
                mode='lines+markers',
                yaxis='y2'
            )
        )

        # Update layout
        fig.update_layout(
            title='Pass Rate and Test Count Trends',
            xaxis=dict(title='Time'),
            yaxis=dict(
                title='Pass Rate (%)',
                range=[0, 100],
                gridcolor='rgba(0,0,0,0.1)'
            ),
            yaxis2=dict(
                title='Total Tests',
                overlaying='y',
                side='right',
                gridcolor='rgba(0,0,0,0.1)'
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            **PLOTLY_LAYOUT
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Create two columns for additional metrics
        col1, col2 = st.columns(2)
        
        with col1:
            # Detailed metrics table
            st.markdown("### Test Result Breakdown")
            metrics_df = df_sut.agg({
                'num_tests': 'sum',
                'num_passes': 'sum',
                'num_failures': 'sum',
                'num_errors': 'sum',
                'num_skips': 'sum',
                'num_xfails': 'sum',
                'num_xpasses': 'sum',
                'duration': 'mean'
            })
            
            # Format values - integers for counts, float for duration
            metrics_table = pd.DataFrame({
                'Metric': [
                    'Total Tests', 'Passes', 'Failures', 'Errors', 'Skips',
                    'Expected Failures', 'Unexpected Passes', 'Avg Duration (s)'
                ],
                'Value': [
                    int(metrics_df['num_tests']),
                    int(metrics_df['num_passes']),
                    int(metrics_df['num_failures']),
                    int(metrics_df['num_errors']),
                    int(metrics_df['num_skips']),
                    int(metrics_df['num_xfails']),
                    int(metrics_df['num_xpasses']),
                    f"{float(metrics_df['duration']):.2f}"
                ]
            })
            st.table(metrics_table)
            
        with col2:
            # Test result distribution pie chart
            st.markdown("### Result Distribution")
            
            # Prepare data
            labels = ["Passed", "Failed", "Errors", "Skipped", "Expected Failures", "Unexpected Passes"]
            values = [
                int(df_sut['num_passes'].sum()),
                int(df_sut['num_failures'].sum()),
                int(df_sut['num_errors'].sum()),
                int(df_sut['num_skips'].sum()),
                int(df_sut['num_xfails'].sum()),
                int(df_sut['num_xpasses'].sum())
            ]
            colors = ["#28a745", "#dc3545", "#fd7e14", "#6c757d", "#9932cc", "#ffd700"]
            
            fig_pie = go.Figure()
            fig_pie.add_trace(go.Pie(
                labels=labels,
                values=values,
                hole=0.3,
                marker_colors=colors,
                texttemplate="%{value} (%{percent})",
                hovertemplate="<b>%{label}</b><br>" +
                            "Count: %{value}<br>" +
                            "Percentage: %{percent}<extra></extra>"
            ))
            
            fig_pie.update_layout(
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                **PLOTLY_LAYOUT
            )
            
            fig_pie.update_traces(textposition='inside')
            st.plotly_chart(fig_pie, use_container_width=True)

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

            # Pass rate trend
            fig_pass_rate = go.Figure()

            fig_pass_rate.add_trace(
                go.Scatter(
                    x=daily_stats["date"],
                    y=daily_stats["pass_rate"],
                    name="Pass Rate",
                    line=dict(color="#28a745", width=2, shape='spline', smoothing=1.3),
                    mode="lines+markers",
                )
            )

            fig_pass_rate.add_trace(
                go.Scatter(
                    x=daily_stats["date"],
                    y=daily_stats["failure_rate"],
                    name="Failure Rate",
                    line=dict(color="#dc3545", width=2, shape='spline', smoothing=1.3),
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
                **PLOTLY_LAYOUT
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
                ("num_xfails", "Expected Failures", "#9932cc"),
                ("num_xpasses", "Unexpected Passes", "#ffd700"),
            ]

            for metric, label, color in metrics:
                fig_volume.add_trace(
                    go.Scatter(
                        x=daily_stats["date"],
                        y=daily_stats[metric],
                        name=label,
                        line=dict(color=color, width=2, shape='spline', smoothing=1.3),
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
                **PLOTLY_LAYOUT
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
                        "num_xfails": "sum",
                        "num_xpasses": "sum",
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
                **PLOTLY_LAYOUT
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
