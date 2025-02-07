"""NiceGUI app for visualizing longitudinal test outcomes."""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import random

import nicegui
import pandas as pd
import plotly.graph_objects as go
from nicegui import ui
import sqlite3

from pytest_oof.utils import TestHistory, LongitudinalAnalysis

class LongitudinalView:
    """Interactive view of longitudinal test outcomes."""

    def __init__(self):
        """Initialize the view."""
        self.db_path = Path("/Users/jwr003/coding/pytest-oof/oof/oof-results.db")
        self.sut_histories: Dict[str, TestHistory] = {}
        self.combined_history = TestHistory()
        self.window_size = timedelta(days=7)
        self.max_suts = 4
        self.selected_suts: List[str] = []
        self.plot2d = None
        self.plot3d = None

    def load_sut_data(self, sut_id: str) -> None:
        """Load test history for a specific SUT."""
        try:
            history = TestHistory()
            history.path = self.db_path
            history.load_test_results(sut_id=sut_id)
            self.sut_histories[sut_id] = history

            # Update combined history
            self.combined_history = TestHistory()
            self.combined_history.path = self.db_path
            for sut in self.selected_suts:
                if sut in self.sut_histories:
                    for result in self.sut_histories[sut].results:
                        self.combined_history.results.append(result)
        except sqlite3.OperationalError:
            ui.notify(f"Error loading data for SUT: {sut_id}", type='negative')

    def create_trend_plot(self) -> go.Figure:
        """Create a plotly figure showing test outcome trends."""
        fig = go.Figure()

        # Create a color map for SUTs
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        sut_colors = dict(zip(self.selected_suts, colors))

        # Plot each selected SUT
        for sut_id in self.selected_suts:
            history = self.sut_histories[sut_id]
            analysis = LongitudinalAnalysis(history)
            trend_stats = analysis.get_trend_stats(window_size=self.window_size)

            if not trend_stats:
                continue

            # Convert to pandas for easier plotting
            df = pd.DataFrame(trend_stats)
            if len(df) == 0:
                continue

            # Calculate rates
            df['pass_rate'] = df['num_passes'] / df['num_tests'] * 100
            df['failure_rate'] = df['num_failures'] / df['num_tests'] * 100
            df['error_rate'] = df['num_errors'] / df['num_tests'] * 100

            # Add small jitter to timestamps that are too close together
            df = df.sort_values('window_start')
            time_diffs = df['window_start'].diff()
            min_time_diff = timedelta(minutes=5)  # Minimum time difference to avoid jitter
            
            for i in range(1, len(df)):
                if time_diffs.iloc[i] is not None and time_diffs.iloc[i] < min_time_diff:
                    # Add a small random jitter between 0 and 5 minutes
                    jitter = timedelta(minutes=random.uniform(0, 5))
                    df.loc[df.index[i], 'window_start'] = df.loc[df.index[i], 'window_start'] + jitter

            # Add traces for this SUT
            fig.add_trace(go.Scatter(
                x=df['window_start'],
                y=df['pass_rate'],
                name=f'{sut_id} Pass Rate',
                line=dict(color=sut_colors[sut_id], width=2),
                legendgroup=sut_id
            ))
            fig.add_trace(go.Scatter(
                x=df['window_start'],
                y=df['failure_rate'],
                name=f'{sut_id} Failure Rate',
                line=dict(color=sut_colors[sut_id], width=2, dash='dot'),
                legendgroup=sut_id
            ))
            fig.add_trace(go.Scatter(
                x=df['window_start'],
                y=df['error_rate'],
                name=f'{sut_id} Error Rate',
                line=dict(color=sut_colors[sut_id], width=2, dash='dash'),
                legendgroup=sut_id
            ))

        # Add combined stats if we have multiple SUTs
        if len(self.selected_suts) > 1:
            analysis = LongitudinalAnalysis(self.combined_history)
            trend_stats = analysis.get_trend_stats(window_size=self.window_size)
            if trend_stats:
                df = pd.DataFrame(trend_stats)
                if len(df) > 0:
                    df['pass_rate'] = df['num_passes'] / df['num_tests'] * 100
                    df['failure_rate'] = df['num_failures'] / df['num_tests'] * 100
                    df['error_rate'] = df['num_errors'] / df['num_tests'] * 100

                    fig.add_trace(go.Scatter(
                        x=df['window_start'],
                        y=df['pass_rate'],
                        name='Combined Pass Rate',
                        line=dict(color='black', width=3),
                        legendgroup='combined'
                    ))
                    fig.add_trace(go.Scatter(
                        x=df['window_start'],
                        y=df['failure_rate'],
                        name='Combined Failure Rate',
                        line=dict(color='black', width=3, dash='dot'),
                        legendgroup='combined'
                    ))
                    fig.add_trace(go.Scatter(
                        x=df['window_start'],
                        y=df['error_rate'],
                        name='Combined Error Rate',
                        line=dict(color='black', width=3, dash='dash'),
                        legendgroup='combined'
                    ))

        # Update layout
        fig.update_layout(
            title='Test Outcome Trends by SUT',
            xaxis_title='Time',
            yaxis_title='Rate (%)',
            hovermode='x unified',
            legend=dict(
                groupclick="toggleitem",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )

        return fig

    def create_3d_plot(self) -> go.Figure:
        """Create a 3D plot showing test metrics across SUTs and time."""
        fig = go.Figure()

        # Create a color map for SUTs
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        sut_colors = dict(zip(self.selected_suts, colors))

        # Plot each selected SUT
        for sut_id in self.selected_suts:
            history = self.sut_histories[sut_id]
            analysis = LongitudinalAnalysis(history)
            trend_stats = analysis.get_trend_stats(window_size=self.window_size)

            if not trend_stats:
                continue

            # Convert to pandas for easier plotting
            df = pd.DataFrame(trend_stats)
            if len(df) == 0:
                continue

            # Calculate rates
            df['pass_rate'] = df['num_passes'] / df['num_tests'] * 100
            df['failure_rate'] = df['num_failures'] / df['num_tests'] * 100
            df['error_rate'] = df['num_errors'] / df['num_tests'] * 100

            # Add small jitter to timestamps that are too close together
            df = df.sort_values('window_start')
            time_diffs = df['window_start'].diff()
            min_time_diff = timedelta(minutes=5)  # Minimum time difference to avoid jitter
            
            for i in range(1, len(df)):
                if time_diffs.iloc[i] is not None and time_diffs.iloc[i] < min_time_diff:
                    # Add a small random jitter between 0 and 5 minutes
                    jitter = timedelta(minutes=random.uniform(0, 5))
                    df.loc[df.index[i], 'window_start'] = df.loc[df.index[i], 'window_start'] + jitter

            # Create time index for z-axis
            time_indices = list(range(len(df)))

            # Add 3D scatter plot for each metric
            fig.add_trace(go.Scatter3d(
                x=[sut_id] * len(df),  # SUT ID for x-axis
                y=df['window_start'],  # Time for y-axis
                z=df['pass_rate'],     # Pass rate for z-axis
                name=f'{sut_id} Pass Rate',
                mode='lines+markers',
                line=dict(color=sut_colors[sut_id], width=4),
                marker=dict(size=4),
                legendgroup=sut_id
            ))
            fig.add_trace(go.Scatter3d(
                x=[sut_id] * len(df),
                y=df['window_start'],
                z=df['failure_rate'],
                name=f'{sut_id} Failure Rate',
                mode='lines+markers',
                line=dict(color=sut_colors[sut_id], width=4, dash='dot'),
                marker=dict(size=4),
                legendgroup=sut_id
            ))
            fig.add_trace(go.Scatter3d(
                x=[sut_id] * len(df),
                y=df['window_start'],
                z=df['error_rate'],
                name=f'{sut_id} Error Rate',
                mode='lines+markers',
                line=dict(color=sut_colors[sut_id], width=4, dash='dash'),
                marker=dict(size=4),
                legendgroup=sut_id
            ))

        # Update layout for better 3D visualization
        fig.update_layout(
            scene=dict(
                xaxis_title='SUT ID',
                yaxis_title='Time',
                zaxis_title='Rate (%)',
                camera=dict(
                    eye=dict(x=2, y=2, z=1.5),
                    up=dict(x=0, y=0, z=1)
                )
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            title='3D Test Metrics Visualization',
            showlegend=True,
            legend=dict(
                groupclick="toggleitem"
            )
        )

        return fig

    def update_plot(self) -> None:
        """Update both 2D and 3D plots with current settings."""
        try:
            if self.plot2d and self.plot3d and self.selected_suts:
                fig2d = self.create_trend_plot()
                fig3d = self.create_3d_plot()
                self.plot2d.update_figure(fig2d)
                self.plot3d.update_figure(fig3d)
        except Exception as e:
            ui.notify(f"Error updating plots: {str(e)}", type='negative')

    def on_sut_select(self, e) -> None:
        """Handle SUT selection changes."""
        try:
            # Get the SUT ID from the checkbox text
            sut_id = e.sender.text

            # Add or remove the SUT based on checkbox state
            if e.value and len(self.selected_suts) < self.max_suts:
                if sut_id not in self.selected_suts:
                    self.selected_suts.append(sut_id)
                    self.load_sut_data(sut_id)
            else:
                if sut_id in self.selected_suts:
                    self.selected_suts.remove(sut_id)
                # If unchecking, make sure the checkbox reflects that
                if len(self.selected_suts) >= self.max_suts:
                    e.sender.value = False
                    ui.notify(f'Maximum {self.max_suts} SUTs can be selected', type='warning')

            self.update_plot()
        except Exception as e:
            ui.notify(f"Error handling SUT selection: {str(e)}", type='negative')

    def on_window_change(self, e) -> None:
        """Handle window size changes."""
        try:
            self.window_size = timedelta(days=int(e.value))
            self.update_plot()
        except Exception as e:
            ui.notify(f"Error updating window size: {str(e)}", type='negative')

    def get_available_suts(self) -> List[str]:
        """Get list of available SUTs from the database."""
        try:
            history = TestHistory()
            history.path = self.db_path
            history.load_test_results()
            suts = set()
            for result in history.results:
                if result.session_metadata.sut_id:
                    suts.add(result.session_metadata.sut_id)
            return sorted(list(suts))
        except sqlite3.OperationalError:
            # Database doesn't exist or tables not initialized
            return ["No test data found. Run some tests first!"]

def main():
    """Start the NiceGUI app."""
    view = LongitudinalView()

    # Create header
    with ui.header().classes('items-center justify-between bg-blue-100 p-4'):
        ui.label('Pytest-OOF Longitudinal View').classes('text-2xl')

    # Create compact controls in a horizontal row
    with ui.row().classes('w-full items-center gap-4 p-2 bg-gray-50'):
        # SUT selection
        ui.label('Select SUTs (max 4):').classes('font-bold whitespace-nowrap')
        with ui.row().classes('gap-2 flex-grow'):
            suts = view.get_available_suts()
            for sut in suts:
                with ui.card().classes('p-2 bg-white'):
                    ui.checkbox(
                        text=sut,
                        on_change=view.on_sut_select
                    )

        # Window size selection
        ui.label('Window (days):').classes('font-bold whitespace-nowrap')
        ui.number(
            value=7,
            min=1,
            max=30,
            on_change=view.on_window_change
        ).classes('w-24')

        # Add view toggle
        ui.button('Show 2D View', on_click=lambda: toggle_view()).classes('bg-blue-500 text-white')

    # Create full-width container for plots
    with ui.column().classes('w-full p-2 flex-grow'):
        # Container for 3D plot
        with ui.column().classes('w-full'):
            ui.label('3D Test Metrics Visualization').classes('text-xl font-bold')
            view.plot3d = ui.plotly({}).classes('w-full h-[1800]')

        # Container for 2D plot (hidden initially)
        with ui.column().classes('w-full hidden') as view.plot2d_container:
            ui.label('2D Trend View').classes('text-xl font-bold')
            view.plot2d = ui.plotly({}).classes('w-full h-[1800]')

    def toggle_view():
        """Toggle between 2D and 3D views."""
        if view.plot2d_container.classes('hidden'):
            view.plot2d_container.remove_classes('hidden')
            view.plot3d.parent.add_classes('hidden')
        else:
            view.plot2d_container.add_classes('hidden')
            view.plot3d.parent.remove_classes('hidden')

    # Add some custom CSS to maximize plot space
    ui.add_head_html("""
        <style>
        .nicegui-content {
            padding: 0 !important;
            max-height: 100vh !important;
            display: flex !important;
            flex-direction: column !important;
        }
        </style>
    """)

    ui.run(title='Pytest-OOF Longitudinal View', reload=False)

if __name__ in {"__main__", "__mp_main__"}:
    main()
