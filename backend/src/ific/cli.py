import asyncio
import logging
import time
from datetime import date
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

app = typer.Typer(no_args_is_help=True, help="ITU BR IFIC interference analyser.")
watch_app = typer.Typer(no_args_is_help=True, help="ITU Space IFIC source watcher.")
app.add_typer(watch_app, name="watch")

_LOG_FORMAT = "%(levelname)s:     %(name)s: %(message)s"


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Run the API server."""
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    uvicorn.run("ific.api:app", host=host, port=port, reload=reload)


@watch_app.command("check")
def watch_check() -> None:
    """Run one watcher check now (shares state with the API; skipped if a check is already running)."""
    from ific.config import settings
    from ific.watcher.service import WatcherService

    if not settings.watcher_enabled:
        typer.echo("watcher is disabled by IFIC_WATCHER_ENABLED=false", err=True)
        raise typer.Exit(2)
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    result = asyncio.run(WatcherService(settings).check("cli"))
    typer.echo(
        f"{result.outcome}: new={result.new_count} downloaded={result.downloaded_count} "
        f"failed={result.failed_count}" + (f" ({result.error})" if result.error else "")
    )
    if result.outcome == "error" or result.failed_count:
        raise typer.Exit(1)


Issue = Annotated[str, typer.Argument(help="Issue number or path to ificNNNN.mdb")]


def _connect():
    import duckdb

    from ific import db
    from ific.config import settings

    try:
        return db.connect(settings.db_path, settings.db_storage_version)
    except duckdb.IOException as e:
        typer.echo(
            f"{settings.db_path} is locked, probably by a running API server; stop it first ({e})", err=True
        )
        raise typer.Exit(2) from e


def _resolve_issue(con, issue: str) -> tuple[int, Path | None]:
    from ific import ingest
    from ific.config import settings

    path = Path(issue)
    if path.suffix.lower() == ".mdb":
        no = ingest.issue_no(path)
        if no is None:
            typer.echo(f"cannot read the issue number from {path.name} (expected ificNNNN.mdb)", err=True)
            raise typer.Exit(2)
        return no, path
    if not issue.isdigit():
        typer.echo(f"expected an issue number or an ificNNNN.mdb path, got {issue!r}", err=True)
        raise typer.Exit(2)
    return int(issue), ingest.discover_issues(settings).get(int(issue))


def _ingest(con, issue: str) -> int:
    from ific import ingest

    no, path = _resolve_issue(con, issue)
    if path is None:
        if no in ingest.ingested_issues(con):
            return no
        typer.echo(f"IFIC {no} not found in the download dir or project root", err=True)
        raise typer.Exit(1)
    try:
        status = ingest.ensure_issue(con, no, path)
    except ingest.IngestError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1) from e
    typer.echo(f"ific={no} {status.action} notices={status.notices} ({status.ms} ms)")
    return no


@app.command("ingest")
def ingest_cmd(issue: Issue) -> None:
    """Load a Space IFIC issue into the DuckDB `space` schema (no-op when unchanged)."""
    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    con = _connect()
    try:
        _ingest(con, issue)
    finally:
        con.close()


def _prepare(issue: str):
    from ific import m4, special_interest
    from ific.config import settings

    con = _connect()
    m4.ensure_m4(con, settings)
    special_interest.ensure_special_interest(con, settings)
    return con, _ingest(con, issue)


def _population(source: str):
    from ific.riia.receivers import GenericM4Population, StationsPopulation

    populations = {"generic-m4": GenericM4Population, "stations": StationsPopulation}
    if source not in populations:
        typer.echo(f"unknown receiver source {source!r}; use one of {sorted(populations)}", err=True)
        raise typer.Exit(2)
    return populations[source]()


Source = Annotated[str, typer.Option("--source", help="Receiver source: generic-m4 or stations")]


@app.command()
def assess(
    issue: Issue,
    as_of: Annotated[
        str | None, typer.Option("--as-of", help="Evaluation date YYYY-MM-DD (default: today)")
    ] = None,
    json_path: Annotated[
        Path | None, typer.Option("--json", help="Write a canonical JSON export here")
    ] = None,
    consistency: Annotated[
        Path | None, typer.Option("--consistency", help="Write the consistency report")
    ] = None,
    summary: Annotated[
        Path | None, typer.Option("--summary", help="Write per-notice summaries (JSON)")
    ] = None,
    source: Source = "generic-m4",
) -> None:
    """Assess every notice of an issue (riia-1) against a receiver population and store the results."""
    import json

    from ific.riia import consistency as checks
    from ific.riia import store
    from ific.riia.assess import assess_issue

    logging.basicConfig(level=logging.INFO, format=_LOG_FORMAT)
    day = date.fromisoformat(as_of) if as_of else date.today()
    con, no = _prepare(issue)
    try:
        started = time.perf_counter()
        population = _population(source)

        def progress(done: int, total: int) -> None:
            typer.echo(f"\r{done}/{total} notices", nl=False, err=True)

        stats: dict[str, float] = {}
        results = assess_issue(con, no, day, population, progress=progress, stats_out=stats)
        typer.echo("", err=True)
        store.write_results(con, no, population.name, results)
        if json_path:
            json_path.write_text(store.canonical_json(results), encoding="utf-8")
        if consistency:
            consistency.write_text(checks.report(no, day.isoformat(), results, stats), encoding="utf-8")
        if summary:
            snapshot = store.round_floats(checks.summary_snapshot(results))
            summary.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        worst = {}
        for r in results:
            worst[r["worst_outcome"]] = worst.get(r["worst_outcome"], 0) + 1
        excluded = getattr(population, "excluded", None)
        typer.echo(
            f"ific={no} source={population.name} notices={len(results)} as_of={day} {worst} "
            f"({time.perf_counter() - started:.1f} s)" + (f" excluded={excluded}" if excluded else "")
        )
    finally:
        con.close()


@app.command()
def review(
    issue: Issue,
    as_of: Annotated[str, typer.Option("--as-of", help="Evaluation date YYYY-MM-DD")],
    out: Annotated[
        Path | None, typer.Option("--out", help="Markdown report path (a .csv is written next to it)")
    ] = None,
) -> None:
    """Concern triage for manual review from stored generic-m4 and stations results."""
    from ific.config import PROJECT_ROOT
    from ific.riia import MODEL_VERSION
    from ific.riia import review as triage

    day = date.fromisoformat(as_of)
    con, no = _prepare(issue)
    try:
        rows, excluded = triage.triage(con, no, day)
        out = (
            out
            or PROJECT_ROOT
            / "plans"
            / "reports"
            / f"review-261107-{MODEL_VERSION.replace('-', '')}-{no}-concerns.md"
        )
        out.write_text(triage.report(no, day, rows, excluded), encoding="utf-8")
        out.with_suffix(".csv").write_text(triage.to_csv(rows), encoding="utf-8")
        groups = {g: sum(1 for r in rows if r["group"] == g) for g, _ in triage.GROUPS}
        typer.echo(f"wrote {out} and {out.with_suffix('.csv').name}; groups={groups}")
    finally:
        con.close()


@app.command()
def draft(
    issue: Issue,
    as_of: Annotated[str, typer.Option("--as-of", help="Evaluation date YYYY-MM-DD")],
    ntc: Annotated[
        list[int] | None,
        typer.Option("--ntc", help="Only this notice (repeatable); default: every assessed one"),
    ] = None,
    out: Annotated[
        Path | None,
        typer.Option("--out", help="Output directory (default plans/reports/drafts-ISSUE-AS_OF/)"),
    ] = None,
) -> None:
    """Write a draft letter to the notifying administration for each notice with a concern (no LLM)."""
    from ific.config import PROJECT_ROOT
    from ific.riia import draft as drafts
    from ific.riia import store

    day = date.fromisoformat(as_of)
    con, no = _prepare(issue)
    try:
        ids = ntc or sorted(
            {n["ntc_id"] for source in drafts.SOURCES for n in store.list_notices(con, no, source, day)[0]}
        )
        if not ids:
            typer.echo(f"IFIC {no} has no stored assessment; run `ific assess` first", err=True)
            raise typer.Exit(1)
        out = out or PROJECT_ROOT / "plans" / "reports" / f"drafts-{no}-{day.isoformat()}"
        out.mkdir(parents=True, exist_ok=True)
        kinds: dict[str, int] = {}
        skipped = missing = 0
        for ntc_id in ids:
            d = drafts.build_draft(con, no, ntc_id, day)
            if d is None:
                missing += 1
                typer.echo(f"notice {ntc_id} has not been assessed", err=True)
            elif isinstance(d, drafts.NoConcern):
                skipped += 1
            else:
                (out / f"{ntc_id}-{d.kind}.md").write_text(drafts.to_markdown(d), encoding="utf-8")
                kinds[d.kind] = kinds.get(d.kind, 0) + 1
        typer.echo(
            f"wrote {sum(kinds.values())} drafts to {out}; kinds={dict(sorted(kinds.items()))} "
            f"no_concern={skipped}" + (f" not_assessed={missing}" if missing else "")
        )
    finally:
        con.close()


@app.command("assess-sensitivity")
def assess_sensitivity(
    issue: Issue,
    as_of: Annotated[str, typer.Option("--as-of", help="Evaluation date YYYY-MM-DD")],
    out: Annotated[Path | None, typer.Option("--out", help="Markdown report path")] = None,
) -> None:
    """Move each assumption to the ends of its range and report outcome flips and shifts."""
    from ific.config import PROJECT_ROOT
    from ific.riia import MODEL_VERSION, sensitivity, store
    from ific.riia.receivers import GenericM4Population

    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT)
    day = date.fromisoformat(as_of)
    con, no = _prepare(issue)
    try:
        population = GenericM4Population()
        rows, flips = sensitivity.run(con, no, day, population, log=lambda m: typer.echo(m, err=True))
        store.write_sensitive(con, no, population.name, flips)
        out = (
            out
            or PROJECT_ROOT
            / "plans"
            / "reports"
            / f"sensitivity-261106-{MODEL_VERSION.replace('-', '')}-{no}.md"
        )
        out.write_text(sensitivity.report(no, day, population.name, rows, flips), encoding="utf-8")
        typer.echo(f"wrote {out}; outcome-sensitive: {sorted(k for k, v in flips.items() if v)}")
    finally:
        con.close()


@app.callback()
def _root() -> None:
    pass
