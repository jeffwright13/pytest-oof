#!/usr/bin/env python3
"""Generate historical test data by back-dating and varying existing results."""
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from pytest_oof.db import init_db


def get_db_path() -> str:
    """Get path to SQLite database."""
    return str(Path("/Users/jwr003/coding/pytest-oof/.oof/oof-results.db"))


def db_connection(db_path: str):
    """Create a database connection with proper settings."""
    conn = sqlite3.connect(db_path, timeout=30.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def drop_tables():
    """Drop existing tables to recreate them."""
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS test_results")
        cursor.execute("DROP TABLE IF EXISTS sessions")
        conn.commit()


def ensure_tables_exist():
    """Create database tables if they don't exist."""
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
        sessions_exists = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='test_results'")
        test_results_exists = cursor.fetchone() is not None

        # Only create tables if they don't exist
        if not sessions_exists:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    sut_id TEXT,
                    sut_type TEXT,
                    sut_version TEXT,
                    sut_env TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration REAL,
                    total_tests INTEGER,
                    passed_tests INTEGER,
                    failed_tests INTEGER,
                    skipped_tests INTEGER,
                    xfailed_tests INTEGER,
                    xpassed_tests INTEGER,
                    warnings INTEGER,
                    errors INTEGER,
                    rerun INTEGER,
                    rerun_outcomes TEXT
                )
                """
            )

        if not test_results_exists:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    test_id TEXT NOT NULL,
                    outcome TEXT,
                    start_time TIMESTAMP,
                    duration REAL,
                    error_message TEXT,
                    error_type TEXT,
                    error_traceback TEXT,
                    has_warning BOOLEAN,
                    longreprtext TEXT,
                    caplog TEXT,
                    capstdout TEXT,
                    capstderr TEXT,
                    rerun_count INTEGER,
                    environment TEXT,
                    warnings TEXT,
                    is_rerun BOOLEAN,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )

        # Check if we need to add new columns to sessions
        cursor.execute("PRAGMA table_info(sessions)")
        columns = {col[1] for col in cursor.fetchall()}

        # Add missing columns if they don't exist
        if "rerun_outcomes" not in columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN rerun_outcomes TEXT DEFAULT '[]'")

        # Check if we need to add new columns to test_results
        cursor.execute("PRAGMA table_info(test_results)")
        columns = {col[1] for col in cursor.fetchall()}

        if "environment" not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN environment TEXT")
        if "warnings" not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN warnings TEXT")
        if "is_rerun" not in columns:
            cursor.execute("ALTER TABLE test_results ADD COLUMN is_rerun BOOLEAN")

        conn.commit()


def get_db_path() -> Path:
    """Get the database path."""
    package_dir = Path(__file__).parent.parent
    db_path = package_dir / ".oof/oof-results.db"
    if not db_path.exists():
        db_path = Path("./.oof/oof-results.db")
        # Initialize the database if it doesn't exist
        db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db(db_path)
    print(f"Using database: {db_path}")
    return db_path


def vary_number(original: int, variance_pct: float = 0.1) -> int:
    """Vary a number by up to variance_pct percent."""
    if original == 0:
        return 0
    variance = int(original * variance_pct)
    if variance == 0:
        variance = 1
    return max(0, original + random.randint(-variance, variance))


# Define available SUT IDs
SUT_IDS = [
    "qa-ref-azulprimejdk17",
    "qa-ref-dist-core-azulprime17",
    "qa-ref-openjdk17",
    "qa-ref-dist-core-openjdk17",
]


def vary_session(session: Dict[Any, Any], base_time: datetime) -> Dict[Any, Any]:
    """Create a varied version of a test session."""
    varied = session.copy()

    # Generate new session ID and random SUT ID
    varied["session_id"] = str(uuid.uuid4())
    varied["sut_id"] = random.choice(SUT_IDS)

    # Vary start time around base time
    start_time = base_time + timedelta(
        minutes=random.randint(-30, 30), seconds=random.randint(-30, 30)
    )
    varied["start_time"] = start_time

    # Vary duration
    duration = vary_number(session["duration"])
    varied["duration"] = duration

    # Calculate stop time based on duration
    varied["end_time"] = start_time + timedelta(seconds=duration)

    # Vary test counts
    varied["total_tests"] = int(vary_number(session["total_tests"]))
    varied["passed_tests"] = int(vary_number(session["passed_tests"]))
    varied["failed_tests"] = int(vary_number(session["failed_tests"]))
    varied["skipped_tests"] = int(vary_number(session["skipped_tests"]))
    varied["xfailed_tests"] = int(vary_number(session["xfailed_tests"]))
    varied["xpassed_tests"] = int(vary_number(session["xpassed_tests"]))

    # Ensure test counts are consistent
    total = varied["total_tests"]
    if total > 0:
        # Calculate percentages of each outcome
        pass_pct = varied["passed_tests"] / total
        fail_pct = varied["failed_tests"] / total
        skip_pct = varied["skipped_tests"] / total
        xfail_pct = varied["xfailed_tests"] / total
        xpass_pct = varied["xpassed_tests"] / total

        # Normalize percentages to sum to 1.0
        total_pct = pass_pct + fail_pct + skip_pct + xfail_pct + xpass_pct
        if total_pct > 0:
            pass_pct /= total_pct
            fail_pct /= total_pct
            skip_pct /= total_pct
            xfail_pct /= total_pct
            xpass_pct /= total_pct

        # Apply percentages to total
        varied["passed_tests"] = int(total * pass_pct)
        varied["failed_tests"] = int(total * fail_pct)
        varied["skipped_tests"] = int(total * skip_pct)
        varied["xfailed_tests"] = int(total * xfail_pct)
        varied["xpassed_tests"] = int(total * xpass_pct)

    return varied


def get_test_templates():
    """Get template test cases and their possible outcomes."""
    templates = {
        "test_login_success": {
            "outcomes": ["passed"],
            "error_message": "",
            "error_type": "",
            "error_traceback": "",
            "longreprtext": "",
            "warnings": [],
            "stdout": [
                "DEBUG: Attempting login with user: test_user",
                "INFO: Login successful",
                "DEBUG: Session token created"
            ],
            "stderr": [],
            "logs": [
                "2025-02-08 15:30:12,123 DEBUG auth.py: Login attempt from IP: 192.168.1.100",
                "2025-02-08 15:30:12,234 INFO auth.py: User test_user authenticated successfully",
                "2025-02-08 15:30:12,345 DEBUG session.py: Created session token: abc123"
            ]
        },
        "test_login_invalid_password": {
            "outcomes": ["failed"],
            "error_message": "AssertionError: Login should have failed with invalid password",
            "error_type": "AssertionError",
            "error_traceback": """
>       assert not auth.login(username="test_user", password="wrong_pass")
E       AssertionError: Login should have failed with invalid password
E
E       During handling of the above exception, another exception occurred:
E
E       auth.AuthenticationError: Invalid credentials provided
E
test_login.py:45: AssertionError
            """.strip(),
            "longreprtext": "Expected login to fail but it succeeded",
            "warnings": [
                "UserWarning: Multiple failed login attempts detected"
            ],
            "stdout": [
                "DEBUG: Attempting login with user: test_user",
                "ERROR: Login failed - invalid credentials"
            ],
            "stderr": [
                "AuthenticationError: Invalid credentials provided"
            ],
            "logs": [
                "2025-02-08 15:30:12,123 DEBUG auth.py: Login attempt from IP: 192.168.1.100",
                "2025-02-08 15:30:12,234 WARNING auth.py: Failed login attempt for user: test_user",
                "2025-02-08 15:30:12,345 ERROR auth.py: Authentication failed: Invalid credentials"
            ]
        },
        "test_database_connection": {
            "outcomes": ["passed", "failed", "error"],
            "error_message": "ConnectionError: Could not connect to database",
            "error_type": "ConnectionError",
            "error_traceback": """
def test_database_connection():
>       with db.connect() as conn:
E       ConnectionError: Could not connect to database
E
E       The above exception was the direct cause of the following exception:
E
E       ConnectionError: Database connection failed after 3 retries
E
E       Detailed error: Connection timed out after 30000ms
E
test_db.py:25: ConnectionError
            """.strip(),
            "longreprtext": "Database connection timed out after multiple retries",
            "warnings": [
                "ResourceWarning: Database connection not properly closed",
                "DeprecationWarning: Legacy connection method used"
            ],
            "stdout": [
                "INFO: Attempting database connection",
                "DEBUG: Using connection parameters: host=localhost, port=5432",
                "ERROR: Connection attempt 1 failed",
                "ERROR: Connection attempt 2 failed",
                "ERROR: Connection attempt 3 failed"
            ],
            "stderr": [
                "psycopg2.OperationalError: could not connect to server",
                "FATAL: connection timeout"
            ],
            "logs": [
                "2025-02-08 15:30:12,123 INFO db.py: Initializing database connection",
                "2025-02-08 15:30:13,234 ERROR db.py: Connection attempt failed: Timeout",
                "2025-02-08 15:30:14,345 ERROR db.py: Retry 1 failed",
                "2025-02-08 15:30:15,456 ERROR db.py: Retry 2 failed",
                "2025-02-08 15:30:16,567 CRITICAL db.py: All connection attempts failed"
            ]
        },
        "test_api_performance": {
            "outcomes": ["passed", "failed", "skipped"],
            "error_message": "PerformanceError: Response time exceeded threshold",
            "error_type": "PerformanceError",
            "error_traceback": """
def test_api_performance():
    start_time = time.time()
>   response = api.get_large_dataset()
E   PerformanceError: Response time (5.2s) exceeded threshold (5.0s)
E
E   Response timing breakdown:
E   - DNS resolution: 0.1s
E   - TCP connection: 0.2s
E   - TLS handshake: 0.3s
E   - Time to first byte: 1.5s
E   - Data transfer: 3.1s
E
test_perf.py:95: PerformanceError
            """.strip(),
            "longreprtext": "API response time exceeded acceptable threshold",
            "warnings": [
                "PerformanceWarning: Response time approaching threshold",
                "ResourceWarning: Large memory allocation detected"
            ],
            "stdout": [
                "INFO: Starting performance test",
                "DEBUG: Request URL: https://api.example.com/large-dataset",
                "DEBUG: Response size: 25MB",
                "ERROR: Performance threshold exceeded"
            ],
            "stderr": [
                "WARNING: High memory usage detected: 1.2GB",
                "ERROR: Response time: 5.2s (threshold: 5.0s)"
            ],
            "logs": [
                "2025-02-08 15:30:12,123 INFO perf.py: Beginning API performance test",
                "2025-02-08 15:30:12,234 DEBUG http.py: Sending request to api.example.com",
                "2025-02-08 15:30:14,345 WARNING perf.py: Response time approaching threshold",
                "2025-02-08 15:30:17,456 ERROR perf.py: Performance test failed: 5.2s > 5.0s"
            ]
        },
        "test_data_validation": {
            "outcomes": ["passed", "xfailed"],
            "error_message": "ValidationError: Invalid data format",
            "error_type": "ValidationError",
            "error_traceback": """
@pytest.mark.xfail(reason="Known issue with UTF-8 handling")
def test_data_validation():
>   result = validate_input({"name": "测试"})
E   ValidationError: Invalid data format
E
E   Validation errors:
E   - Field 'name': Invalid UTF-8 encoding
E   - Field 'age': Required field missing
E   - Field 'email': Invalid email format
E
test_validation.py:112: ValidationError
            """.strip(),
            "longreprtext": "Data validation failed due to encoding issues",
            "warnings": [
                "UnicodeWarning: Invalid UTF-8 detected",
                "DeprecationWarning: Old validation method used"
            ],
            "stdout": [
                "DEBUG: Validating input data",
                "DEBUG: Checking required fields",
                "ERROR: Validation failed"
            ],
            "stderr": [
                "UnicodeEncodeError: 'ascii' codec can't encode characters"
            ],
            "logs": [
                "2025-02-08 15:30:12,123 DEBUG validation.py: Starting data validation",
                "2025-02-08 15:30:12,234 WARNING validation.py: UTF-8 encoding issues detected",
                "2025-02-08 15:30:12,345 ERROR validation.py: Validation failed for field: name"
            ]
        }
    }
    return templates


def generate_test_results(session_id: str, num_tests: int, base_time: datetime):
    """Generate test results for a session."""
    test_results = []
    test_templates = get_test_templates()

    # Track flaky tests to ensure consistent behavior within session
    flaky_tests = {
        "test_database_connection": random.random() < 0.3,  # 30% chance of being flaky in this session
        "test_api_performance": random.random() < 0.2,      # 20% chance of being flaky in this session
    }

    for i in range(num_tests):
        test_template = random.choice(list(test_templates.items()))
        test_id = test_template[0]
        template_data = test_template[1]

        # Handle flaky tests
        if test_id in flaky_tests and flaky_tests[test_id]:
            # If test is flaky in this session, randomly fail some runs
            outcome = random.choice(template_data["outcomes"] + ["failed"] * 2)
        else:
            outcome = random.choice(template_data["outcomes"])

        # Vary the timestamp within 5 minutes of base time
        timestamp = base_time + timedelta(
            minutes=random.randint(0, 5),
            seconds=random.randint(0, 59),
            microseconds=random.randint(0, 999999),
        )

        # Determine if this is a rerun
        is_rerun = random.random() < 0.1  # 10% chance of being a rerun
        rerun_count = random.randint(1, 3) if is_rerun else 0

        # Create test result with rich content
        result = {
            "session_id": session_id,
            "test_id": test_id,
            "outcome": outcome,
            "start_time": timestamp.isoformat(),
            "duration": random.uniform(0.1, 5.0),
            "error_message": template_data["error_message"] if outcome in ["failed", "error"] else "",
            "error_type": template_data["error_type"] if outcome in ["failed", "error"] else "",
            "error_traceback": template_data["error_traceback"] if outcome in ["failed", "error"] else "",
            "has_warning": bool(template_data.get("warnings", [])),
            "longreprtext": template_data["longreprtext"] if outcome in ["failed", "error"] else "",
            "caplog": "\n".join(template_data.get("logs", [])),
            "capstdout": "\n".join(template_data.get("stdout", [])),
            "capstderr": "\n".join(template_data.get("stderr", [])) if outcome in ["failed", "error"] else "",
            "rerun_count": rerun_count,
            "is_rerun": is_rerun,
            "environment": json.dumps({
                "os": random.choice(["Linux", "Darwin"]),
                "python": random.choice(["3.8.12", "3.9.7", "3.10.2"]),
                "pytest": random.choice(["6.2.5", "7.0.1", "7.1.0"]),
                "platform": random.choice([
                    "Linux-5.15.0-x86_64-with-glibc2.31",
                    "Darwin-21.3.0-x86_64-i386-64bit"
                ]),
                "workspace": f"/workspace/project-{random.randint(1000, 9999)}",
                "cpu_count": random.choice([4, 8, 16]),
                "memory_gb": random.choice([8, 16, 32, 64])
            }),
            "warnings": json.dumps(template_data.get("warnings", []))
        }

        test_results.append(result)

    return test_results


def update_session_stats(session_id: str, test_results: List[Dict[str, Any]]) -> Dict[str, int]:
    """Update session stats based on test results."""
    stats = {"num_reruns": 0, "num_rerun_groups": 0}

    # Count reruns
    for result in test_results:
        if result.get("is_rerun", False):
            stats["num_reruns"] += 1

    # Count rerun groups (consecutive reruns)
    in_rerun_group = False
    for result in test_results:
        if result.get("is_rerun", False):
            if not in_rerun_group:
                stats["num_rerun_groups"] += 1
                in_rerun_group = True
        else:
            in_rerun_group = False

    return stats


def create_global_failure_event(base_time: datetime, duration_days: int = 1) -> tuple[datetime, datetime]:
    """Create a time window where all SUTs will fail."""
    end_time = base_time + timedelta(days=duration_days)
    return base_time, end_time


def create_clustered_failures(sut_id: str, base_time: datetime, cluster_size: int = 3) -> list[datetime]:
    """Create a cluster of failures followed by recovery for a specific SUT."""
    failure_times = []
    current_time = base_time
    for _ in range(cluster_size):
        failure_times.append(current_time)
        current_time += timedelta(hours=random.randint(1, 4))
    return failure_times


def create_flaky_pattern(base_time: datetime, duration_hours: int = 24) -> list[tuple[datetime, bool]]:
    """Create alternating pass/fail pattern over time."""
    pattern = []
    current_time = base_time
    while current_time < base_time + timedelta(hours=duration_hours):
        should_fail = random.random() < 0.5  # 50% chance of failure
        pattern.append((current_time, should_fail))
        current_time += timedelta(minutes=random.randint(30, 120))
    return pattern


def get_version_specific_failures(sut_version: str) -> float:
    """Return failure probability for specific versions."""
    version_failure_rates = {
        "1.0.0": 0.8,  # High failure rate for old version
        "1.1.0": 0.5,  # Moderate failure rate
        "2.0.0": 0.2,  # Lower failure rate for newer version
    }
    return version_failure_rates.get(sut_version, 0.1)  # Default to 10% failure rate


def get_environment_failure_probability(sut_env: str) -> float:
    """Return failure probability for specific environments."""
    env_failure_rates = {
        "dev": 0.3,     # Higher failure rate in dev
        "staging": 0.2, # Moderate failure rate in staging
        "prod": 0.05,   # Low failure rate in prod
    }
    return env_failure_rates.get(sut_env, 0.1)


def apply_performance_trend(base_failure_rate: float, day_index: int, total_days: int) -> float:
    """Apply a gradual trend to failure rates over time."""
    if random.random() < 0.5:  # 50% chance of increasing trend
        trend_factor = 1 + (day_index / total_days)  # Gradually increase
    else:
        trend_factor = 1 - (day_index / (2 * total_days))  # Gradually decrease, but not to zero
    return base_failure_rate * trend_factor


def generate_historical_data(
    days: int = 7,
    sessions_per_day: tuple = (3, 8),
    include_patterns: bool = True
):
    """Generate historical test data with various failure patterns.

    Args:
        days: Number of days of historical data to generate
        sessions_per_day: Tuple of (min, max) sessions per day
        include_patterns: Whether to include special failure patterns
    """
    ensure_template_data()
    db_path = get_db_path()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)

    # Create global failure event (1-day window in the middle of the time range)
    global_failure_start, global_failure_end = create_global_failure_event(
        start_time + timedelta(days=days//2),
        duration_days=1
    )

    # Create version-specific failure windows
    version_failure_times = {
        "1.0.0": create_clustered_failures("qa-ref-azulprimejdk17", start_time + timedelta(days=1)),
        "2.0.0": create_clustered_failures("qa-ref-openjdk17", start_time + timedelta(days=3))
    }

    # Generate data for each day
    current_time = start_time
    day_index = 0
    
    while current_time < end_time:
        num_sessions = random.randint(*sessions_per_day)
        
        for _ in range(num_sessions):
            # Create session
            session_id = str(uuid.uuid4())
            session_end_time = current_time + timedelta(minutes=random.randint(20, 40))
            sut_id = random.choice(SUT_IDS)
            sut_version = random.choice(["1.0.0", "1.1.0", "2.0.0"])
            sut_env = random.choice(["dev", "staging", "prod"])
            
            # Generate test results
            num_tests = random.randint(50, 100)
            test_results = generate_test_results(session_id, num_tests, current_time)
            
            if include_patterns:
                # Apply failure patterns based on conditions
                in_global_failure = global_failure_start <= current_time <= global_failure_end
                version_failures = version_failure_times.get(sut_version, [])
                in_version_failure = current_time in version_failures
                
                base_failure_rate = 0.1  # Default failure rate
                
                # Apply various failure patterns
                if in_global_failure:
                    base_failure_rate = 0.9  # 90% failure rate during global failure event
                elif in_version_failure:
                    base_failure_rate = 0.7  # 70% failure rate during version-specific failures
                
                # Apply environment-based failure rates
                env_failure_rate = get_environment_failure_probability(sut_env)
                base_failure_rate = max(base_failure_rate, env_failure_rate)
                
                # Apply performance trend
                final_failure_rate = apply_performance_trend(base_failure_rate, day_index, days)
                
                # Modify test results based on calculated failure rate
                for result in test_results:
                    if random.random() < final_failure_rate:
                        result["outcome"] = "failed"
                        result["error_message"] = "Simulated failure based on pattern"
            
            # Calculate session stats from test results
            passed_tests = sum(1 for r in test_results if r["outcome"].lower() == "passed")
            failed_tests = sum(1 for r in test_results if r["outcome"].lower() == "failed")
            skipped_tests = sum(1 for r in test_results if r["outcome"].lower() == "skipped")
            xfailed_tests = sum(1 for r in test_results if r["outcome"].lower() == "xfailed")
            xpassed_tests = sum(1 for r in test_results if r["outcome"].lower() == "xpassed")
            warnings = sum(1 for r in test_results if r["has_warning"])
            
            # Insert session
            with db_connection(str(db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO sessions (
                        session_id, sut_id, sut_type, sut_version, sut_env,
                        start_time, end_time, duration, total_tests,
                        passed_tests, failed_tests, skipped_tests,
                        xfailed_tests, xpassed_tests, warnings, errors, rerun,
                        rerun_outcomes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        sut_id,
                        "web-service",
                        sut_version,
                        sut_env,
                        current_time.isoformat(),
                        session_end_time.isoformat(),
                        (session_end_time - current_time).total_seconds(),
                        len(test_results),
                        passed_tests,
                        failed_tests,
                        skipped_tests,
                        xfailed_tests,
                        xpassed_tests,
                        warnings,
                        0,  # errors
                        0,  # rerun
                        json.dumps([]),  # rerun_outcomes
                    ),
                )
                
                # Insert test results
                for result in test_results:
                    cursor.execute(
                        """
                        INSERT INTO test_results (
                            session_id, test_id, outcome, start_time,
                            duration, error_message, error_type,
                            error_traceback, has_warning, longreprtext,
                            caplog, capstdout, capstderr, rerun_count,
                            environment, warnings, is_rerun
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result["session_id"],
                            result["test_id"],
                            result["outcome"],
                            result["start_time"],
                            result.get("duration", 0.0),
                            result.get("error_message", ""),
                            result.get("error_type", ""),
                            result.get("error_traceback", ""),
                            result.get("has_warning", False),
                            result.get("longreprtext", ""),
                            result.get("caplog", ""),
                            result.get("capstdout", ""),
                            result.get("capstderr", ""),
                            result.get("rerun_count", 0),
                            result.get("environment", ""),
                            result.get("warnings", ""),
                            result.get("is_rerun", False),
                        ),
                    )
                conn.commit()
            
            current_time += timedelta(minutes=random.randint(60, 180))
        
        day_index += 1
        current_time = start_time + timedelta(days=day_index)


def generate_test_session(base_time: datetime, template_session_id: str) -> str:
    """Generate a test session with random variations."""
    session_id = str(uuid.uuid4())
    end_time = base_time + timedelta(minutes=random.randint(20, 40))

    # Generate test results first
    num_tests = random.randint(50, 100)
    test_results = generate_test_results(session_id, num_tests, base_time)

    # Calculate session stats from actual test results
    passed_tests = sum(1 for r in test_results if r["outcome"].lower() == "passed")
    failed_tests = sum(1 for r in test_results if r["outcome"].lower() == "failed")
    skipped_tests = sum(1 for r in test_results if r["outcome"].lower() == "skipped")
    xfailed_tests = sum(1 for r in test_results if r["outcome"].lower() == "xfailed")
    xpassed_tests = sum(1 for r in test_results if r["outcome"].lower() == "xpassed")
    warnings = sum(1 for r in test_results if r["has_warning"])

    # Pick a random SUT ID
    sut_id = random.choice(SUT_IDS)

    # Create session with calculated stats
    db_path = get_db_path()
    with db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (
                session_id, sut_id, sut_type, sut_version, sut_env,
                start_time, end_time, duration, total_tests,
                passed_tests, failed_tests, skipped_tests,
                xfailed_tests, xpassed_tests, warnings, errors, rerun,
                rerun_outcomes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                sut_id,
                "web-service",  # sut_type
                "1.0.0",  # sut_version
                "staging",  # sut_env
                base_time.isoformat(),
                end_time.isoformat(),
                (end_time - base_time).total_seconds(),
                len(test_results),  # Use actual number of test results
                passed_tests,
                failed_tests,
                skipped_tests,
                xfailed_tests,
                xpassed_tests,
                warnings,
                0,  # errors
                0,  # rerun
                json.dumps([]),  # rerun_outcomes
            ),
        )
        conn.commit()

    return session_id


def ensure_template_data():
    """Ensure template data exists in database."""
    db_path = get_db_path()
    ensure_tables_exist()  # Create tables if they don't exist
    with db_connection(db_path) as conn:
        cursor = conn.cursor()

        # Get template session
        cursor.execute(
            """
            SELECT
                session_id, start_time, end_time, duration,
                sut_id, sut_type, sut_version, sut_env,
                total_tests, passed_tests, failed_tests,
                skipped_tests, xfailed_tests, xpassed_tests,
                warnings, errors, rerun
            FROM sessions
            ORDER BY start_time DESC
            LIMIT 1
            """
        )
        template = cursor.fetchone()

        if not template:
            # Create a template session
            session_id = str(uuid.uuid4())
            start_time = datetime.now() - timedelta(days=1)
            template_session = {
                "session_id": session_id,
                "start_time": start_time,
                "end_time": start_time + timedelta(minutes=30),
                "duration": 1800.0,
                "sut_id": "qa-ref-dist-core-openjdk17",
                "sut_type": "java",
                "sut_version": "17.0.1",
                "sut_env": "linux",
                "total_tests": 100,
                "passed_tests": 80,
                "failed_tests": 10,
                "skipped_tests": 2,
                "xfailed_tests": 2,
                "xpassed_tests": 1,
                "warnings": 0,
                "errors": 0,
                "rerun": 0,
            }

            # First insert the session
            cursor.execute(
                """
                INSERT INTO sessions (
                    session_id, sut_id, sut_type, sut_version, sut_env,
                    start_time, end_time, duration, total_tests,
                    passed_tests, failed_tests, skipped_tests,
                    xfailed_tests, xpassed_tests, warnings, errors, rerun,
                    rerun_outcomes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    template_session["session_id"],
                    template_session["sut_id"],
                    template_session["sut_type"],
                    template_session["sut_version"],
                    template_session["sut_env"],
                    template_session["start_time"],
                    template_session["end_time"],
                    template_session["duration"],
                    template_session["total_tests"],
                    template_session["passed_tests"],
                    template_session["failed_tests"],
                    template_session["skipped_tests"],
                    template_session["xfailed_tests"],
                    template_session["xpassed_tests"],
                    template_session["warnings"],
                    template_session["errors"],
                    template_session["rerun"],
                    json.dumps([]),  # rerun_outcomes
                ),
            )
            conn.commit()

            # Then generate and insert test results
            test_results = generate_test_results(
                session_id=session_id,
                num_tests=template_session["total_tests"],
                base_time=template_session["start_time"],
            )

            for result in test_results:
                cursor.execute(
                    """
                    INSERT INTO test_results (
                        session_id, test_id, outcome, start_time,
                        duration, error_message, error_type,
                        error_traceback, has_warning, longreprtext,
                        caplog, capstdout, capstderr, rerun_count,
                        environment, warnings, is_rerun
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result["session_id"],
                        result["test_id"],
                        result["outcome"],
                        result["start_time"],
                        result.get("duration", 0.0),
                        result.get("error_message", ""),
                        result.get("error_type", ""),
                        result.get("error_traceback", ""),
                        result.get("has_warning", False),
                        result.get("longreprtext", ""),
                        result.get("caplog", ""),
                        result.get("capstdout", ""),
                        result.get("capstderr", ""),
                        result.get("rerun_count", 0),
                        result.get("environment", ""),
                        result.get("warnings", ""),
                        result.get("is_rerun", False),
                    ),
                )
            conn.commit()

            # Fetch the newly created template
            cursor.execute(
                """
                SELECT
                    session_id, start_time, end_time, duration,
                    sut_id, sut_type, sut_version, sut_env,
                    total_tests, passed_tests, failed_tests,
                    skipped_tests, xfailed_tests, xpassed_tests,
                    warnings, errors, rerun
                FROM sessions
                ORDER BY start_time DESC
                LIMIT 1
                """
            )
            template = cursor.fetchone()

        return template


def purge_database():
    """Purge all data from the database."""
    db_path = get_db_path()
    conn = db_connection(db_path)
    try:
        print("Purging database...")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM test_results")
        cursor.execute("DELETE FROM sessions")
        conn.commit()

        # Get counts after purge
        cursor.execute("SELECT COUNT(*) FROM sessions")
        sessions_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM test_results")
        results_count = cursor.fetchone()[0]

        print(
            f"Database purged. Remaining sessions: {sessions_count}, remaining results: {results_count}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate historical test data")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to generate data for (default: %(default)s)",
    )
    parser.add_argument(
        "--purge",
        action="store_true",
        help="Purge existing data before generating new data",
    )
    args = parser.parse_args()

    if args.purge:
        purge_database()
    else:
        generate_historical_data(
            days=args.days,
            sessions_per_day=(3, 8),
        )
