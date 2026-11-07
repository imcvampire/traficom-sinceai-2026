"""Derived `analytics.terra_*` tables: one transaction replaces an issue's assessment. Keyed by `ific_no`."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import duckdb

from ific.riia.store import round_floats

OUTCOMES = ("exceeds", "meets", "screened_out", "not_applicable", "not_assessed")
LIST_DROP = ("p1546",)


def _utc(epoch_us: int | None) -> datetime | None:
    return None if epoch_us is None else datetime.fromtimestamp(epoch_us / 1e6, UTC)


def ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.terra_assessment (
            ific_no INTEGER NOT NULL, terrakey BIGINT NOT NULL, model_version VARCHAR NOT NULL,
            adm VARCHAR NOT NULL, outcome VARCHAR NOT NULL, relevant BOOLEAN NOT NULL,
            change VARCHAR NOT NULL, pub_status VARCHAR NOT NULL, criterion_id VARCHAR,
            margin_db DOUBLE,
            k_outcome INTEGER NOT NULL, k_fin INTEGER NOT NULL, k_margin DOUBLE NOT NULL,
            k_change INTEGER NOT NULL, k_pub INTEGER NOT NULL,
            payload JSON NOT NULL,
            PRIMARY KEY (ific_no, terrakey)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.terra_issue (
            ific_no INTEGER PRIMARY KEY, model_version VARCHAR NOT NULL, assessed_at TIMESTAMPTZ NOT NULL,
            assignments INTEGER NOT NULL, relevant INTEGER NOT NULL, outcome_counts JSON NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.terra_job (
            ific_no INTEGER PRIMARY KEY, source VARCHAR NOT NULL, status VARCHAR NOT NULL,
            done INTEGER NOT NULL, total INTEGER NOT NULL, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
            error VARCHAR
        )
        """
    )


def canonical_json(results: list[dict[str, Any]]) -> str:
    """Stable export: sorted keys, results in terrakey order, floats rounded to 4 decimals."""
    ordered = sorted(results, key=lambda r: r["terrakey"])
    return json.dumps(round_floats(ordered), sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def outcome_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = dict.fromkeys(OUTCOMES, 0)
    for r in results:
        counts[r["outcome"]] += 1
    return counts


def write_results(con: duckdb.DuckDBPyConnection, ific_no: int, results: list[dict[str, Any]]) -> None:
    ensure_tables(con)
    model = results[0]["model_version"] if results else "terra-1"
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute("DELETE FROM analytics.terra_assessment WHERE ific_no = ?", [ific_no])
        rows = []
        for r in results:
            k = r["sort_key"]
            rows.append(
                (
                    ific_no,
                    r["terrakey"],
                    r["model_version"],
                    r["adm"],
                    r["outcome"],
                    r["relevance"]["relevant"],
                    r["change"],
                    r["pub_status"]["status"],
                    r["criterion"]["id"] if r["criterion"] else None,
                    r["margin_db"],
                    k[0],
                    k[1],
                    k[2],
                    k[3],
                    k[4],
                    json.dumps(r, ensure_ascii=False, sort_keys=True),
                )
            )
        if rows:
            con.executemany(
                f"INSERT INTO analytics.terra_assessment VALUES ({', '.join('?' * 16)})",
                rows,
            )
        con.execute(
            "INSERT OR REPLACE INTO analytics.terra_issue VALUES (?, ?, current_timestamp, ?, ?, ?)",
            [
                ific_no,
                model,
                len(results),
                sum(1 for r in results if r["relevance"]["relevant"]),
                json.dumps(outcome_counts(results)),
            ],
        )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def issue_summaries(con: duckdb.DuckDBPyConnection) -> dict[int, dict[str, Any]]:
    ensure_tables(con)
    return {
        r[0]: {
            "model_version": r[1],
            "assessed_at": _utc(r[2]),
            "assignments": r[3],
            "relevant": r[4],
            "outcome_counts": json.loads(r[5]),
        }
        for r in con.execute(
            "SELECT ific_no, model_version, epoch_us(assessed_at), assignments, relevant, outcome_counts "
            "FROM analytics.terra_issue ORDER BY ific_no"
        ).fetchall()
    }


def _slim(r: dict[str, Any]) -> dict[str, Any]:
    h = r["hazard"]
    t2 = h.get("tier2")
    if t2:
        h = {**h, "tier2": {k: v for k, v in t2.items() if k not in LIST_DROP}}
    return {**r, "hazard": h}


def list_assignments(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    *,
    outcome: list[str] | None = None,
    adm: list[str] | None = None,
    change: list[str] | None = None,
    pub_status: list[str] | None = None,
    relevant: bool | None = True,
    criterion: str | None = None,
    q: str | None = None,
    slim: bool = True,
) -> list[dict[str, Any]]:
    """Stored results in the fixed sort order (outcome, FIN COORD REQUIRED, margin, change, status, key)."""
    ensure_tables(con)
    where, params = ["ific_no = ?"], [ific_no]
    for col, values in (("outcome", outcome), ("adm", adm), ("change", change), ("pub_status", pub_status)):
        if values:
            where.append(f"{col} IN ({', '.join('?' * len(values))})")
            params.extend(values)
    if relevant is not None:
        where.append("relevant = ?")
        params.append(relevant)
    if criterion:
        where.append("criterion_id = ?")
        params.append(criterion)
    if q:
        fields = ("lower(payload->>'adm_ref_id')", "lower(payload->'site'->>'name')",
                  "CAST(terrakey AS VARCHAR)", "CAST(payload->>'f_mhz' AS VARCHAR)")  # fmt: skip
        where.append("(" + " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in fields) + ")")
        escaped = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        params.extend([like, like, like, like])
    rows = con.execute(
        f"SELECT payload FROM analytics.terra_assessment WHERE {' AND '.join(where)} "
        "ORDER BY k_outcome, k_fin, k_margin, k_change, k_pub, terrakey",
        params,
    ).fetchall()
    out = [json.loads(r[0]) for r in rows]
    return [_slim(r) for r in out] if slim else out


def get_assignment(con: duckdb.DuckDBPyConnection, ific_no: int, terrakey: int) -> dict[str, Any] | None:
    ensure_tables(con)
    row = con.execute(
        "SELECT payload FROM analytics.terra_assessment WHERE ific_no = ? AND terrakey = ?",
        [ific_no, terrakey],
    ).fetchone()
    return json.loads(row[0]) if row else None


def all_results(con: duckdb.DuckDBPyConnection, ific_no: int) -> list[dict[str, Any]]:
    ensure_tables(con)
    rows = con.execute(
        "SELECT payload FROM analytics.terra_assessment WHERE ific_no = ? ORDER BY terrakey", [ific_no]
    ).fetchall()
    return [json.loads(r[0]) for r in rows]


def save_job(con: duckdb.DuckDBPyConnection, job: dict[str, Any]) -> None:
    ensure_tables(con)
    con.execute(
        "INSERT OR REPLACE INTO analytics.terra_job VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            job["ific_no"],
            job["source"],
            job["status"],
            job["done"],
            job["total"],
            job["started_at"],
            job["finished_at"],
            job["error"],
        ],
    )


def load_jobs(con: duckdb.DuckDBPyConnection, source: str) -> dict[int, dict[str, Any]]:
    ensure_tables(con)
    cols = ("ific_no", "source", "status", "done", "total", "started_at", "finished_at", "error")
    sql_cols = ", ".join(f"epoch_us({c})" if c.endswith("_at") else c for c in cols)
    out = {}
    for r in con.execute(f"SELECT {sql_cols} FROM analytics.terra_job WHERE source = ?", [source]).fetchall():
        job = dict(zip(cols, r, strict=True))
        job["started_at"], job["finished_at"] = _utc(job["started_at"]), _utc(job["finished_at"])
        out[r[0]] = job
    return out
