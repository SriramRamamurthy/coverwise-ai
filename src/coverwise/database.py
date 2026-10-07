import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "storage" / "coverwise.db"


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    inputs_json TEXT NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )


def save_analysis(inputs, result, analysis_type):
    analysis_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO analyses (
                    id,
                    created_at,
                    analysis_type,
                    inputs_json,
                    result_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    created_at,
                    analysis_type,
                    json.dumps(inputs),
                    json.dumps(result),
                ),
            )

    return {
        "analysis_id": analysis_id,
        "created_at": created_at,
    }


def list_analyses(limit=20):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row

        rows = connection.execute(
            """
            SELECT id, created_at, analysis_type, result_json
            FROM analyses
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "analysis_id": row["id"],
            "created_at": row["created_at"],
            "analysis_type": row["analysis_type"],
            "predicted_label": json.loads(
                row["result_json"]
            ).get("predicted_label"),
        }
        for row in rows
    ]


def get_analysis(analysis_id):
    with closing(sqlite3.connect(DATABASE_PATH)) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            "SELECT * FROM analyses WHERE id = ?",
            (analysis_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "analysis_id": row["id"],
        "created_at": row["created_at"],
        "analysis_type": row["analysis_type"],
        "inputs": json.loads(row["inputs_json"]),
        "result": json.loads(row["result_json"]),
    }