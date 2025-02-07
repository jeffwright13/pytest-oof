"""Add SUT environment column to test_sessions table."""
import sqlite3
from pathlib import Path

def migrate(db_path: Path) -> None:
    """Add sut_environment column to test_sessions table."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Add the new column
        cursor.execute(
            """
            ALTER TABLE test_sessions
            ADD COLUMN sut_environment TEXT DEFAULT ''
            """
        )
        
        # Commit the changes
        conn.commit()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python add_sut_environment.py <path_to_db>")
        sys.exit(1)
    
    db_path = Path(sys.argv[1])
    migrate(db_path)
