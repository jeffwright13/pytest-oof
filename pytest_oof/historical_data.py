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
    
    # Determine weights for each outcome
    weights = []
    for outcome in template["outcomes"]:
        if outcome == "passed":
            weights.append(1 - base_failure_rate)
        elif outcome == "failed":
            weights.append(base_failure_rate)
        elif outcome == "skipped":
            weights.append(0.1)  # 10% chance of skip
        else:
            weights.append(0.1)  # Default 10% for other outcomes
    
    # Normalize weights to sum to 1
    total = sum(weights)
    weights = [w/total for w in weights]
    
    outcome = random.choices(
        template["outcomes"],
        weights=weights,
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
    include_patterns: bool = True,
    db_path: Optional[str] = None,
) -> None:
    """Generate historical test data with various failure patterns.
    
    Args:
        days: Number of days of historical data to generate
        sessions_per_day: Tuple of (min, max) sessions per day
        include_patterns: Whether to include special failure patterns
        db_path: Path to database file (default: test database)
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
            test_templates = random.sample(TEST_TEMPLATES, k=min(len(TEST_TEMPLATES), num_tests))
            results = generate_test_results(
                session_id=session_id,
                num_tests=len(test_templates),
                base_time=session_time,
                sut_env=sut_env,
                base_failure_rate=base_failure_rate,
            )
            
            # Calculate session duration and stats
            session_duration = sum(r["duration"] for r in results)
            session_end = session_time + timedelta(seconds=session_duration)
            
            # Add session to database
            add_session(
                db_path=db_path,
                session_id=session_id,
                start_time=session_time,
                end_time=session_end,
                duration=int(session_duration),
                sut_id=sut_env["id"],
                sut_type=sut_env["type"],
                sut_version=sut_env["version"],
                sut_env=sut_env["env"],
            )
            
            # Add test results
            for result in results:
                error_data = result.get("error_data")
                add_test_result(
                    db_path=db_path,
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
            update_session_stats(db_path=db_path, session_id=session_id)
        
        current_time += timedelta(days=1)

def purge_database(db_path: Optional[str] = None, force: bool = False) -> None:
    """Purge all data from the database.
    
    Args:
        db_path: Path to database file to purge (default: test database)
        force: Allow purging databases other than the test database
    """
    from pytest_oof.constants import TEST_DB_PATH, DEFAULT_DB_PATH
    import os
    import sqlite3
    import shutil
    
    # Extensive logging
    print(f"[DEBUG] Purge database called with:")
    print(f"  db_path: {db_path}")
    print(f"  force: {force}")
    
    if db_path is None:
        db_path = str(TEST_DB_PATH)
    
    db_path = Path(db_path).resolve()
    
    # Log resolved paths
    print(f"[DEBUG] Resolved paths:")
    print(f"  db_path: {db_path}")
    print(f"  TEST_DB_PATH: {TEST_DB_PATH.resolve()}")
    print(f"  DEFAULT_DB_PATH: {DEFAULT_DB_PATH.resolve()}")
    
    # Safety check
    if not force:
        if db_path.resolve() not in [TEST_DB_PATH.resolve(), DEFAULT_DB_PATH.resolve()]:
            raise ValueError("Can only purge test or production database. Use force=True to override.")
        
        if db_path.resolve() == DEFAULT_DB_PATH.resolve():
            raise ValueError("Refusing to purge production database. Use force=True to override.")
    
    try:
        # Ensure database exists before trying to purge
        if not db_path.exists():
            print(f"[ERROR] No database found at {db_path}. Skipping purge.")
            return
        
        # Detailed connection and purge logging
        print(f"[DEBUG] Attempting to purge database: {db_path}")
        
        # Close any existing connections
        if hasattr(sqlite3, 'close_all_connections'):
            sqlite3.close_all_connections()
        
        # Use sqlite3 directly for more control
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            
            # Get all table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [table[0] for table in cursor.fetchall()]
            
            print(f"[DEBUG] Tables found: {tables}")
            
            # Delete data from all tables
            for table in tables:
                try:
                    print(f"[DEBUG] Deleting from table: {table}")
                    cursor.execute(f"DELETE FROM {table}")
                    print(f"[DEBUG] Deleted from table: {table}")
                except Exception as e:
                    print(f"[WARNING] Could not delete from table {table}: {e}")
            
            # Commit deletions
            conn.commit()
            
            # Vacuum outside of transaction
            conn.isolation_level = None  # Disable transaction
            print("[DEBUG] Running VACUUM")
            conn.execute("VACUUM")
            print("[DEBUG] VACUUM completed")
        except Exception as e:
            print(f"[ERROR] Database purge failed: {e}")
            raise
        finally:
            conn.close()
        
        # Remove WAL and SHM files
        wal_file = db_path.with_suffix(db_path.suffix + '-wal')
        shm_file = db_path.with_suffix(db_path.suffix + '-shm')
        
        for file_path in [wal_file, shm_file, db_path]:
            if file_path.exists():
                try:
                    print(f"[DEBUG] Removing file: {file_path}")
                    if file_path == db_path:
                        # For the main database file, recreate an empty database
                        os.remove(file_path)
                        # Recreate an empty database
                        conn = sqlite3.connect(str(file_path))
                        conn.close()
                    else:
                        os.remove(file_path)
                    print(f"[DEBUG] Removed file: {file_path}")
                except PermissionError:
                    print(f"[WARNING] Could not remove {file_path}. File may be in use.")
                except Exception as e:
                    print(f"[ERROR] Error removing {file_path}: {e}")
        
        print(f"[SUCCESS] Successfully purged database: {db_path}")
    except Exception as e:
        print(f"[CRITICAL ERROR] Purge failed for database {db_path}: {e}")
        raise
