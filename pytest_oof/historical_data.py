"""Functions for generating historical test data."""
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

from pytest_oof.db import (
    add_session,
    add_test_result,
    update_session_stats,
    init_db,
    db_connection,
)

# Available SUT IDs and their metadata
SUTS = [
    {
        "id": "qa-ref-azulprimejdk17",
        "type": "reference",
        "versions": ["17.0.1", "17.0.2", "17.0.3"],
        "envs": ["dev", "staging", "prod"],
    },
    {
        "id": "qa-ref-python311",
        "type": "reference",
        "versions": ["3.11.0", "3.11.1", "3.11.2"],
        "envs": ["dev", "staging", "prod"],
    },
]

# Test templates with possible outcomes and error types
TEST_TEMPLATES = [
    {
        "id": "test_basic_functionality",
        "outcomes": ["passed", "failed"],
        "error_types": ["AssertionError", "ValueError"],
        "duration_base": 0.5,
    },
    {
        "id": "test_advanced_features",
        "outcomes": ["passed", "failed", "skipped"],
        "error_types": ["TypeError", "NotImplementedError"],
        "duration_base": 1.2,
    },
    {
        "id": "test_performance",
        "outcomes": ["passed", "failed"],
        "error_types": ["TimeoutError"],
        "duration_base": 2.0,
    },
    {
        "id": "test_expected_failure",
        "outcomes": ["xfailed", "xpassed"],
        "error_types": ["AssertionError"],
        "duration_base": 0.3,
    },
    {
        "id": "test_optional_feature",
        "outcomes": ["passed", "skipped"],
        "error_types": [],
        "duration_base": 0.8,
    },
]

def vary_number(original: float, variance_pct: float = 0.1) -> float:
    """Vary a number by up to variance_pct percent."""
    variance = original * variance_pct
    return original + random.uniform(-variance, variance)

def generate_rerun_outcome(initial_outcome: str, rerun_count: int) -> List[str]:
    """Generate realistic rerun outcomes based on initial failure type."""
    if initial_outcome in ["passed", "skipped", "xfailed", "xpassed"]:
        return []
    
    outcomes = []
    recovery_chance = {
        "TimeoutError": 0.7,  # Timeouts often succeed on retry
        "AssertionError": 0.4,  # Sometimes recovers
        "ValueError": 0.3,
        "TypeError": 0.2,
        "SyntaxError": 0.0,  # Never recovers
        "NotImplementedError": 0.0,
    }.get(initial_outcome, 0.3)
    
    for _ in range(rerun_count):
        if random.random() < recovery_chance:
            outcomes.append("passed")
            break
        outcomes.append("failed")
    
    return outcomes

def generate_test_result(
    session_id: str,
    test_id: str,
    timestamp: datetime,
    sut_env: Dict[str, Any],
    error_types: List[str],
    base_failure_rate: float = 0.2,
) -> Dict[str, Any]:
    """Generate a single test result with realistic rerun behavior."""
    template = next(t for t in TEST_TEMPLATES if t["id"] == test_id)
    
    # Adjust failure rate based on environment
    if sut_env["env"] == "staging":
        base_failure_rate *= 1.5
    elif sut_env["env"] == "prod":
        base_failure_rate *= 0.5
    
    # Version-specific failures
    if sut_env["version"].endswith(".0"):  # Initial versions more likely to fail
        base_failure_rate *= 1.3
    
    outcome = random.choices(
        template["outcomes"],
        weights=[1 - base_failure_rate, base_failure_rate],
        k=1
    )[0]
    
    duration = vary_number(template["duration_base"])
    error_data = None
    
    if outcome == "failed":
        error_type = random.choice(error_types or ["AssertionError"])
        error_data = {
            "type": error_type,
            "message": f"Test {test_id} failed with {error_type}",
        }
    
    rerun_count = 2 if outcome == "failed" and random.random() < 0.3 else 0
    rerun_outcomes = generate_rerun_outcome(
        error_data["type"] if error_data else outcome,
        rerun_count
    )
    
    return {
        "session_id": session_id,
        "test_id": test_id,
        "outcome": outcome,
        "duration": duration,
        "error_data": error_data,
        "timestamp": timestamp,
        "rerun_count": rerun_count,
        "rerun_outcomes": rerun_outcomes,
    }

def generate_test_results(
    session_id: str,
    num_tests: int,
    base_time: datetime,
    sut_env: Dict[str, Any],
    base_failure_rate: float = 0.2,
) -> List[Dict[str, Any]]:
    """Generate test results for a session."""
    results = []
    templates = random.sample(TEST_TEMPLATES, num_tests)
    
    for i, template in enumerate(templates):
        timestamp = base_time + timedelta(seconds=i * 2)
        result = generate_test_result(
            session_id=session_id,
            test_id=template["id"],
            timestamp=timestamp,
            sut_env=sut_env,
            error_types=template["error_types"],
            base_failure_rate=base_failure_rate,
        )
        results.append(result)
    
    return results

def create_global_failure_event(
    base_time: datetime,
    duration_days: int = 1
) -> Tuple[datetime, datetime]:
    """Create a time window where all SUTs will fail."""
    start_time = base_time
    end_time = start_time + timedelta(days=duration_days)
    return start_time, end_time

def create_flaky_pattern(
    base_time: datetime,
    duration_hours: int = 24
) -> List[Tuple[datetime, float]]:
    """Create alternating pass/fail pattern over time."""
    patterns = []
    current_time = base_time
    
    for hour in range(duration_hours):
        # Oscillate between high and low failure rates
        failure_rate = 0.8 if hour % 2 == 0 else 0.2
        patterns.append((current_time, failure_rate))
        current_time += timedelta(hours=1)
    
    return patterns

def apply_performance_trend(
    base_failure_rate: float,
    day_index: int,
    total_days: int
) -> float:
    """Apply a gradual trend to failure rates over time."""
    # Create a slight improvement trend over time
    improvement_factor = 1 - (day_index / total_days * 0.3)
    return base_failure_rate * improvement_factor

def generate_historical_data(
    days: int = 7,
    sessions_per_day: Tuple[int, int] = (3, 8),
    include_patterns: bool = True
) -> None:
    """Generate historical test data with various failure patterns.
    
    Args:
        days: Number of days of historical data to generate
        sessions_per_day: Tuple of (min, max) sessions per day
        include_patterns: Whether to include special failure patterns
    """
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    # Create global failure event (1-day window in the middle)
    if include_patterns:
        global_failure_start, global_failure_end = create_global_failure_event(
            start_time + timedelta(days=days // 2)
        )
        flaky_patterns = create_flaky_pattern(
            start_time + timedelta(days=days // 3)
        )
    
    current_time = start_time
    while current_time < end_time:
        # Generate 3-8 sessions per day
        num_sessions = random.randint(*sessions_per_day)
        
        for _ in range(num_sessions):
            # Select random SUT and metadata
            sut = random.choice(SUTS)
            sut_env = {
                "id": sut["id"],
                "type": sut["type"],
                "version": random.choice(sut["versions"]),
                "env": random.choice(sut["envs"]),
            }
            
            # Create session
            session_time = current_time + timedelta(
                minutes=random.randint(0, 60 * 24)
            )
            session_id = f"session_{session_time.strftime('%Y%m%d_%H%M%S')}"
            
            # Determine base failure rate
            base_failure_rate = 0.2
            
            # Apply patterns if enabled
            if include_patterns:
                # Global failure event
                if global_failure_start <= session_time <= global_failure_end:
                    base_failure_rate = 0.9
                
                # Flaky test pattern
                for pattern_time, pattern_rate in flaky_patterns:
                    if abs((session_time - pattern_time).total_seconds()) < 3600:
                        base_failure_rate = pattern_rate
                
                # Apply gradual improvement trend
                day_index = (session_time - start_time).days
                base_failure_rate = apply_performance_trend(
                    base_failure_rate, day_index, days
                )
            
            # Generate test results
            num_tests = random.randint(3, len(TEST_TEMPLATES))
            results = generate_test_results(
                session_id=session_id,
                num_tests=num_tests,
                base_time=session_time,
                sut_env=sut_env,
                base_failure_rate=base_failure_rate,
            )
            
            # Calculate session duration and stats
            session_duration = sum(r["duration"] for r in results)
            session_end = session_time + timedelta(seconds=session_duration)
            
            # Add session to database
            add_session(
                session_id=session_id,
                start_time=session_time,
                end_time=session_end,
                sut_id=sut_env["id"],
                sut_type=sut_env["type"],
                sut_version=sut_env["version"],
                sut_env=sut_env["env"],
            )
            
            # Add test results
            for result in results:
                error_data = result.get("error_data")
                add_test_result(
                    session_id=session_id,
                    test_id=result["test_id"],
                    outcome=result["outcome"],
                    duration=result["duration"],
                    error_data=error_data,
                    timestamp=result["timestamp"],
                    rerun_count=result["rerun_count"],
                    rerun_outcomes=result["rerun_outcomes"],
                )
            
            # Update session stats
            update_session_stats(session_id)
        
        current_time += timedelta(days=1)

def purge_database() -> None:
    """Purge all data from the database."""
    init_db()  # This will recreate tables
