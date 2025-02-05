"""REST API for serving pytest-oof results to Grafana."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="pytest-oof Grafana API")

# Enable CORS for Grafana
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this with your Grafana server URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db_path() -> Path:
    """Get the database path."""
    package_dir = Path(__file__).parent.parent
    db_path = package_dir / "oof/oof-results.db"
    if not db_path.exists():
        db_path = Path("oof/oof-results.db")
    return db_path


@app.get("/search", response_model=List[str])
async def search_metrics():
    """Return available metrics for Grafana."""
    return [
        "total_tests",
        "passed_tests",
        "failed_tests",
        "error_tests",
        "skipped_tests",
        "pass_rate",
        "duration",
    ]


@app.post("/query")
async def query_metrics(body: Dict[str, Any]):
    """Query metrics based on Grafana's JSON data source format."""
    try:
        db_path = get_db_path()
        from_time = datetime.fromisoformat(
            body.get("range", {}).get("from", "").replace("Z", "+00:00")
        )
        to_time = datetime.fromisoformat(
            body.get("range", {}).get("to", "").replace("Z", "+00:00")
        )

        conn = sqlite3.connect(db_path)

        # Base query for test sessions
        query = """
        SELECT
            start_time,
            total_tests,
            num_passes as passed_tests,
            num_failures as failed_tests,
            num_errors as error_tests,
            num_skips as skipped_tests,
            CAST(num_passes AS FLOAT) / NULLIF(total_tests, 0) * 100 as pass_rate,
            duration
        FROM test_sessions
        WHERE start_time BETWEEN ? AND ?
        ORDER BY start_time
        """

        df = pd.read_sql_query(
            query, conn, params=(from_time, to_time), parse_dates=["start_time"]
        )

        # Format response for Grafana
        response = []
        for target in body.get("targets", []):
            metric = target.get("target")
            if metric in df.columns:
                response.append(
                    {
                        "target": metric,
                        "datapoints": [
                            [float(value), int(ts.timestamp() * 1000)]
                            for value, ts in zip(df[metric], df["start_time"])
                        ],
                    }
                )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
