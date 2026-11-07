# IFIC interference analyser

Analyses ITU BR Space IFIC issues for their interference risk to Finnish spectrum use. The project has two parts:

- `backend/`: a Python 3.12 FastAPI service and `ific` CLI. It ingests IFIC `.mdb` databases into DuckDB, runs
  the risk-informed interference assessment (model `riia-1`), and watches the ITU site for new issues.
- `frontend/`: a React 19 + Vite single-page app that talks to the API through the `/api` proxy.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| [mise](https://mise.jdx.dev) | any recent | Installs and pins the tools below from `mise.toml` |
| Python | 3.12 | Installed by mise. `uv` is configured to use this interpreter only and never downloads its own |
| uv | 0.12.22 | Installed by mise |
| Bun | 1.4.2 | Installed by mise |
| Node | 24.22.2 | Installed by mise |
| mdbtools | any | Provides `mdb-export`, used to read IFIC `.mdb` files. Not managed by mise |

Install mdbtools with your system package manager:

```sh
brew install mdbtools          # macOS
sudo apt install mdbtools      # Debian/Ubuntu
```

## Install

```sh
mise trust                     # allow this repository's mise.toml
mise install                   # Python, uv, Bun, Node
mise run install               # uv sync (backend) + bun install (frontend)
cp .env.example .env           # optional; defaults work without it
```

Without mise, install the pinned versions yourself and run the same commands:
`uv sync --project backend` and `bun install --cwd frontend`.

## Run

```sh
mise run dev                   # API on http://127.0.0.1:8000 and web on http://localhost:5173
```

Or run them separately:

```sh
mise run api                   # cd backend && uv run ific serve --reload
mise run web                   # cd frontend && bun run dev
```

Open http://localhost:5173. The Vite dev server uses a fixed port (`strictPort`), so stop any other process on
5173 instead of letting it pick a new one. The API only allows CORS from `http://localhost:5173` by default
(`IFIC_CORS_ORIGINS`).

On startup the API loads the M4 frequency allocation table and the special-interest frequency list from `data/`
into DuckDB at `var/db/ific.duckdb`, and starts the source watcher.

## Getting IFIC data

The analyser looks for Space IFIC databases in two places, in this order:

1. `data/ific/<ific_no>/ific<no>.mdb`, which is where the watcher saves downloads.
2. `ific<no>.mdb` in the repository root, for files you place there manually. `brific*.mdb` files are terrestrial
   issues and are ignored.

`.mdb` files, `data/ific/` and `var/` are gitignored because they are large and can be downloaded again.

The **source watcher** checks the ITU download page every hour while the API runs. On its first run it downloads
every issue on the newest year page, which is about 25 files and 3–7 GB once extracted. Set
`IFIC_WATCHER_ENABLED=false` in `.env` to turn it off. See [docs/source-watcher.md](docs/source-watcher.md) for its
behaviour and every `IFIC_WATCHER_*` setting.

## CLI

Run the CLI from `backend/` with `uv run ific <command>`, or from anywhere with `uv run --project backend ific`.
`ISSUE` is an issue number or a path to an `ificNNNN.mdb` file.

| Command | Purpose |
|---|---|
| `ific serve [--host] [--port] [--reload]` | Run the API server |
| `ific watch check` | Run one watcher check now |
| `ific ingest ISSUE` | Load an issue into DuckDB (no-op when unchanged) |
| `ific assess ISSUE [--as-of YYYY-MM-DD] [--source generic-m4\|stations] [--json PATH] [--consistency PATH] [--summary PATH]` | Assess every notice of an issue and store the results |
| `ific review ISSUE --as-of YYYY-MM-DD [--out PATH]` | Write a concern-triage report (Markdown and CSV) from stored results |
| `ific assess-sensitivity ISSUE --as-of YYYY-MM-DD [--out PATH]` | Report which outcomes flip when assumptions move within their ranges |

Example:

```sh
cd backend
uv run ific ingest 3074
uv run ific assess 3074 --as-of 2026-11-06
uv run ific review 3074 --as-of 2026-11-06
```

DuckDB allows only one writer, so the commands that write to the database fail while the API server is running.
Stop the server first.

## Configuration

Settings are read from environment variables with the `IFIC_` prefix, or from `.env` in the repository root. Both
the API and the CLI find that file whatever the working directory. `.env.example` lists the watcher settings. Other
settings are:

| Variable | Default | Notes |
|---|---|---|
| `IFIC_DATA_DIR` | `data` | Reference data (M4, special-interest list, ITU reference tables) |
| `IFIC_DB_DIR` | `var/db` | Holds `ific.duckdb` |
| `IFIC_DB_STORAGE_VERSION` | `v1.5.0` | Storage format for new DB files, kept readable by DuckDB 1.x GUI clients |
| `IFIC_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list |

## Development

```sh
mise run test                  # backend tests: uv run pytest -q
mise run lint                  # ruff check, ruff format --check, oxlint
mise run build                 # type-check and build the frontend into frontend/dist
```

Run a single test file with `cd backend && uv run pytest tests/test_m4.py -q`.

## Documentation

- [docs/interference-risk-assessment.md](docs/interference-risk-assessment.md): the assessment method, its sources,
  and what is still unvalidated.
- [docs/source-watcher.md](docs/source-watcher.md): how the IFIC source watcher works and how to configure it.
- [docs/frontend.md](docs/frontend.md): frontend stack, layout and URL parameters.
