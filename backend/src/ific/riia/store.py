"""Derived `analytics.risk_*` tables: one transaction replaces an issue's assessment."""

import json
import math
from datetime import UTC, date, datetime
from typing import Any

import duckdb

from ific.riia.assess import apply_as_of, queue_sort_key, technical_sort_key
from ific.riia.hazards import OUTCOME_RANK

DOMAIN = "space"
_LIST_DROP = ("hazards", "curve_grid_db", "pfd_checks")


def _utc(epoch_us: int | None) -> datetime | None:
    """TIMESTAMPTZ is read as epoch_us: fetching it directly would need pytz."""
    return None if epoch_us is None else datetime.fromtimestamp(epoch_us / 1e6, UTC)


def ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.risk_notice (
            domain VARCHAR NOT NULL, ific_no INTEGER NOT NULL, item_id BIGINT NOT NULL,
            receiver_source VARCHAR NOT NULL,
            model_version VARCHAR NOT NULL, as_of DATE NOT NULL,
            worst_outcome VARCHAR NOT NULL, max_share_violating DOUBLE, max_median_exceedance_db DOUBLE,
            days_left INTEGER, fin_identified BOOLEAN NOT NULL,
            payload JSON NOT NULL, assessed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (domain, ific_no, item_id, receiver_source)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.risk_hazard (
            domain VARCHAR NOT NULL, ific_no INTEGER NOT NULL, item_id BIGINT NOT NULL,
            receiver_source VARCHAR NOT NULL,
            hazard_id VARCHAR NOT NULL, mode VARCHAR NOT NULL, service_class VARCHAR, tier INTEGER NOT NULL,
            outcome VARCHAR NOT NULL, share_violating DOUBLE, worst_case_db DOUBLE, tier2_max_db DOUBLE,
            risk_curves JSON NOT NULL,
            PRIMARY KEY (domain, ific_no, item_id, receiver_source, hazard_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.risk_job (
            ific_no INTEGER NOT NULL, receiver_source VARCHAR NOT NULL, status VARCHAR NOT NULL,
            done INTEGER NOT NULL, total INTEGER NOT NULL, started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
            error VARCHAR, PRIMARY KEY (ific_no, receiver_source)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics.risk_sensitivity (
            ific_no INTEGER NOT NULL, receiver_source VARCHAR NOT NULL, assumption_id VARCHAR NOT NULL,
            flips INTEGER NOT NULL, created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (ific_no, receiver_source, assumption_id)
        )
        """
    )


def round_floats(x: Any, nd: int = 4) -> Any:
    if isinstance(x, float):
        if not math.isfinite(x):
            return None
        r = round(x, nd)
        return 0.0 if r == 0 else r
    if isinstance(x, dict):
        return {k: round_floats(v, nd) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [round_floats(v, nd) for v in x]
    return x


def canonical_json(results: list[dict[str, Any]]) -> str:
    """Stable export: sorted keys, results in ntc_id order, floats rounded to 4 decimals."""
    ordered = sorted(results, key=lambda r: r["ntc_id"])
    return json.dumps(round_floats(ordered), sort_keys=True, ensure_ascii=False, indent=1) + "\n"


def write_results(
    con: duckdb.DuckDBPyConnection, ific_no: int, receiver_source: str, results: list[dict[str, Any]]
) -> None:
    ensure_tables(con)
    key = [DOMAIN, ific_no, receiver_source]
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(
            "DELETE FROM analytics.risk_hazard WHERE domain = ? AND ific_no = ? AND receiver_source = ?", key
        )
        con.execute(
            "DELETE FROM analytics.risk_notice WHERE domain = ? AND ific_no = ? AND receiver_source = ?", key
        )
        notice_rows, hazard_rows = [], []
        for r in results:
            r = round_floats(r, 6)
            notice_rows.append(
                (
                    DOMAIN,
                    ific_no,
                    r["ntc_id"],
                    receiver_source,
                    r["model_version"],
                    r["as_of"],
                    r["worst_outcome"],
                    r["max_share_violating"],
                    r["max_median_exceedance_db"],
                    r["regulatory"]["days_left"],
                    r["regulatory"]["fin_identified"],
                    json.dumps(r, ensure_ascii=False),
                )
            )
            for h in r["hazards"]:
                hazard_rows.append(
                    (
                        DOMAIN,
                        ific_no,
                        r["ntc_id"],
                        receiver_source,
                        h["hazard_id"],
                        h["mode"],
                        h["service_class"],
                        h["tier"],
                        h["outcome"],
                        h["share_violating"],
                        h["worst_case_db"],
                        h["tier2_max_db"],
                        json.dumps(h["risk_curves"]),
                    )
                )
        if notice_rows:
            con.executemany(
                "INSERT INTO analytics.risk_notice VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
                "current_timestamp)",
                notice_rows,
            )
        if hazard_rows:
            con.executemany(
                "INSERT INTO analytics.risk_hazard VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                hazard_rows,
            )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def _table_exists(con: duckdb.DuckDBPyConnection) -> bool:
    return bool(
        con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'analytics' AND table_name = "
            "'risk_notice'"
        ).fetchone()
    )


def issue_summaries(con: duckdb.DuckDBPyConnection, receiver_source: str) -> dict[int, dict[str, Any]]:
    if not _table_exists(con):
        return {}
    out: dict[int, dict[str, Any]] = {}
    for ific_no, model, as_of, assessed_us, outcome, n in con.execute(
        """
        SELECT ific_no, any_value(model_version), any_value(as_of), epoch_us(max(assessed_at)), worst_outcome,
               count(*)
        FROM analytics.risk_notice WHERE domain = ? AND receiver_source = ? GROUP BY ific_no, worst_outcome
        """,
        [DOMAIN, receiver_source],
    ).fetchall():
        assessed_at = _utc(assessed_us)
        s = out.setdefault(
            ific_no,
            {
                "model_version": model,
                "as_of": as_of,
                "assessed_at": assessed_at,
                "outcome_counts": dict.fromkeys(OUTCOME_RANK, 0),
            },
        )
        s["outcome_counts"][outcome] = n
        s["assessed_at"] = max(s["assessed_at"], assessed_at)
    return out


def _payloads(
    con: duckdb.DuckDBPyConnection, ific_no: int, receiver_source: str, ntc_id: int | None = None
) -> list[tuple]:
    sql = (
        "SELECT payload, epoch_us(assessed_at) FROM analytics.risk_notice "
        "WHERE domain = ? AND ific_no = ? AND receiver_source = ?"
    )
    args: list[Any] = [DOMAIN, ific_no, receiver_source]
    if ntc_id is not None:
        sql += " AND item_id = ?"
        args.append(ntc_id)
    if not _table_exists(con):
        return []
    return [(p, _utc(at)) for p, at in con.execute(sql, args).fetchall()]


def _stamp(payload: dict[str, Any], assessed_at: datetime, as_of: date) -> dict[str, Any]:
    out = apply_as_of(payload, as_of)
    out["assessed_at"] = assessed_at.isoformat()
    return out


def list_notices(
    con: duckdb.DuckDBPyConnection, ific_no: int, receiver_source: str, as_of: date, view: str = "technical"
) -> tuple[list[dict[str, Any]], str | None]:
    rows = _payloads(con, ific_no, receiver_source)
    notices = [
        _stamp({k: v for k, v in json.loads(p).items() if k not in _LIST_DROP}, at, as_of) for p, at in rows
    ]
    assessed_at = max((at for _, at in rows), default=None)
    if view == "queue":
        notices = sorted((n for n in notices if n["in_queue"]), key=queue_sort_key)
    else:
        notices.sort(key=technical_sort_key)
    return notices, assessed_at.isoformat() if assessed_at else None


def get_notice(
    con: duckdb.DuckDBPyConnection,
    ific_no: int,
    receiver_source: str,
    ntc_id: int,
    as_of: date,
    sensitive: set[str] | None = None,
) -> dict[str, Any] | None:
    rows = _payloads(con, ific_no, receiver_source, ntc_id)
    if not rows:
        return None
    out = _stamp(json.loads(rows[0][0]), rows[0][1], as_of)
    if sensitive:
        for h in out["hazards"] + (out.get("pfd_checks") or []):
            for a in h["assumptions"]:
                a["sensitive"] = a["id"] in sensitive
    return out


def write_sensitive(
    con: duckdb.DuckDBPyConnection, ific_no: int, receiver_source: str, flips: dict[str, int]
) -> None:
    ensure_tables(con)
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(
            "DELETE FROM analytics.risk_sensitivity WHERE ific_no = ? AND receiver_source = ?",
            [ific_no, receiver_source],
        )
        rows = [(ific_no, receiver_source, k, v) for k, v in sorted(flips.items()) if v > 0]
        if rows:
            con.executemany(
                "INSERT INTO analytics.risk_sensitivity VALUES (?, ?, ?, ?, current_timestamp)", rows
            )
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def sensitive_assumptions(
    con: duckdb.DuckDBPyConnection, ific_no: int | None, receiver_source: str
) -> set[str]:
    ensure_tables(con)
    sql = "SELECT DISTINCT assumption_id FROM analytics.risk_sensitivity WHERE receiver_source = ?"
    args: list[Any] = [receiver_source]
    if ific_no is not None:
        sql += " AND ific_no = ?"
        args.append(ific_no)
    return {r[0] for r in con.execute(sql, args).fetchall()}


def save_job(con: duckdb.DuckDBPyConnection, job: dict[str, Any]) -> None:
    ensure_tables(con)
    con.execute(
        "INSERT OR REPLACE INTO analytics.risk_job VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            job["ific_no"],
            job["receiver_source"],
            job["status"],
            job["done"],
            job["total"],
            job["started_at"],
            job["finished_at"],
            job["error"],
        ],
    )


def load_jobs(con: duckdb.DuckDBPyConnection, receiver_source: str) -> dict[int, dict[str, Any]]:
    ensure_tables(con)
    cols = ("ific_no", "receiver_source", "status", "done", "total", "started_at", "finished_at", "error")
    sql_cols = ", ".join(f"epoch_us({c})" if c.endswith("_at") else c for c in cols)
    out = {}
    for r in con.execute(
        f"SELECT {sql_cols} FROM analytics.risk_job WHERE receiver_source = ?", [receiver_source]
    ).fetchall():
        job = dict(zip(cols, r, strict=True))
        job["started_at"], job["finished_at"] = _utc(job["started_at"]), _utc(job["finished_at"])
        out[r[0]] = job
    return out
