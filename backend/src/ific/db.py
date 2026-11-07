from pathlib import Path

import duckdb


def connect(path: Path, storage_version: str) -> duckdb.DuckDBPyConnection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path), config={"storage_compatibility_version": storage_version})
    for schema in ("ref", "space", "terra", "analytics"):
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ref.source (
            source_id VARCHAR PRIMARY KEY,
            path      VARCHAR NOT NULL,
            sha256    VARCHAR NOT NULL,
            bytes     BIGINT  NOT NULL,
            edition   VARCHAR,
            row_count BIGINT  NOT NULL,
            loaded_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    return con
