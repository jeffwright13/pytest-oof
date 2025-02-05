"""Migration script to move from console-based to report-based test tracking."""
import sqlite3
from pathlib import Path


def migrate_database(db_path: Path) -> None:
    """Migrate the database to the new schema."""
    with sqlite3.connect(db_path) as conn:
        c = conn.cursor()

        # Backup old tables
        c.executescript("""
            ALTER TABLE test_sessions RENAME TO test_sessions_old;
            ALTER TABLE test_results RENAME TO test_results_old;
        """)

        # Create new tables with updated schema
        c.executescript("""
            CREATE TABLE test_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                start_time DATETIME NOT NULL,
                end_time DATETIME,
                duration REAL,
                sut_id TEXT,
                sut_type TEXT,
                sut_version TEXT,
                sut_env TEXT,
                sut_metadata TEXT,
                python_version TEXT,
                os_info TEXT,
                pytest_version TEXT,
                command_line TEXT,
                num_tests INTEGER DEFAULT 0,
                num_passes INTEGER DEFAULT 0,
                num_failures INTEGER DEFAULT 0,
                num_errors INTEGER DEFAULT 0,
                num_skips INTEGER DEFAULT 0,
                num_xfails INTEGER DEFAULT 0,
                num_xpasses INTEGER DEFAULT 0,
                num_reruns INTEGER DEFAULT 0,
                num_rerun_groups INTEGER DEFAULT 0,
                num_warnings INTEGER DEFAULT 0,
                num_deselected INTEGER DEFAULT 0
            );

            CREATE TABLE test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                test_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                duration REAL,
                error_message TEXT,
                error_type TEXT,
                error_traceback TEXT,
                has_warning BOOLEAN DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES test_sessions (id)
            );
        """)

        # Migrate data from old tables
        c.execute("""
            INSERT INTO test_sessions (
                id, session_id, start_time, end_time, duration, sut_id, sut_type,
                sut_version, sut_env, python_version, os_info, pytest_version,
                command_line, num_tests, num_passes, num_failures, num_errors,
                num_skips, num_xfails, num_xpasses, num_reruns, num_rerun_groups,
                num_warnings, num_deselected
            )
            SELECT 
                id, '', start_time, end_time, duration, sut_id, sut_type,
                sut_version, sut_env, python_version, os_info, pytest_version,
                command_line, num_tests, num_passes, num_failures, num_errors,
                num_skips, num_xfails, num_xpasses, num_reruns, num_rerun_groups,
                num_warnings, num_deselected
            FROM test_sessions_old;
        """)

        c.execute("""
            INSERT INTO test_results (
                session_id, test_id, outcome, timestamp, duration,
                error_message, error_type, error_traceback, has_warning
            )
            SELECT 
                session_id, test_id, outcome, timestamp, duration,
                error_message, error_type, error_traceback, has_warning
            FROM test_results_old;
        """)

        # Drop old tables
        c.executescript("""
            DROP TABLE test_sessions_old;
            DROP TABLE test_results_old;
            DROP TABLE IF EXISTS console_output;
            DROP TABLE IF EXISTS report_metrics;
            DROP TABLE IF EXISTS resource_metrics;
            DROP TABLE IF EXISTS test_artifacts;
            DROP TABLE IF EXISTS system_state;
            DROP TABLE IF EXISTS fixtures;
            DROP TABLE IF EXISTS test_fixture_usage;
        """)

        conn.commit()


if __name__ == "__main__":
    db_path = Path("oof.db")  # Replace with actual path
    migrate_database(db_path)
