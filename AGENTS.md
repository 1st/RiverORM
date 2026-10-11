# Working with RiverORM

Guidance for AI agents and human contributors working in this repository.
RiverORM is a minimalistic, async-first ORM for Python (3.13+), built on
Pydantic, with PostgreSQL and MySQL backends.

## Repository layout

- `riverorm/` — the library.
  - `models.py` — `Model`, `Field`, query API (`save`, `all`, `filter`,
    `select_related`, etc.). Most feature work lives here.
  - `db/` — backend abstraction: `base.py`, `postgres.py` (asyncpg),
    `mysql.py` (aiomysql), `registry.py` (`DatabaseRegistry`).
  - `config.py`, `constants.py`, `utils.py` — configuration and shared helpers.
- `tests/` — pytest suite. `models.py` holds test models; `conftest.py`
  provides DB fixtures (`db_setup_and_teardown` drops/recreates tables per test).
- `docs/` — longer-form docs. See [DEVELOPMENT.md](docs/DEVELOPMENT.md),
  [USAGE.md](docs/USAGE.md), [INSTALL.md](docs/INSTALL.md),
  [MISSION.md](docs/MISSION.md).
  - `docs/adr/` — Architecture Decision Records (one file per significant
    decision). See `docs/adr/template.md` for the format.
- `.github/` — CI workflows and Dependabot config.

## Environment setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/); the lockfile
`uv.lock` is committed and must stay in sync with `pyproject.toml`.

```bash
make setup            # installs uv, creates .venv, runs `uv sync --all-extras`
# or, if uv is already installed:
uv sync --all-extras
```

The tests need running databases. Start them with Docker:

```bash
make docker-start     # postgres + mysql via docker-compose.yml
make docker-stop
```

Copy `.env.example` to `.env` for connection strings (`POSTGRES_DSN`,
`MYSQL_DSN`, `DB_TYPE`, `DEBUG`). Tests read these via `riverorm.config`.

## Day-to-day commands

| Task            | Command                                              |
| --------------- | ---------------------------------------------------- |
| Run tests       | `make test` (or `uv run pytest -v`)                  |
| Lint            | `uv run ruff check`                                  |
| Format check    | `uv run ruff format --check`                         |
| Type-check      | `uv run mypy .`                                       |
| All checks      | `make lint`                                          |
| Refresh lock    | `uv lock` (commit `uv.lock` when deps change)        |

`pre-commit` runs ruff, mypy, `uv-lock`, pyupgrade, and pytest on commit:

```bash
uv run pre-commit install      # once
uv run pre-commit run --all-files
```

## Conventions

- **Python 3.13+ idioms.** Use modern syntax (`int | None`, pattern matching,
  built-in generics). Type-hint aggressively — `mypy` is enforced in CI.
- **Async by default.** All query/DB methods are `async`; tests use
  `pytest-asyncio`.
- **Line length 100**, ruff rules `E`/`F` (see `pyproject.toml`).
- **Be explicit, no hidden queries.** Related data loads lazily unless eagerly
  requested (e.g. `select_related`); don't introduce implicit N+1 behavior.
- Add or update tests under `tests/` for any behavior change, and keep both
  backends in mind even when only Postgres is exercised in CI today.

## Before opening a PR

Run the full local gate so CI stays green:

```bash
make lint && make test
```

CI (`.github/workflows/tests.yml`, `code_checks.yml`) runs the same checks on
every PR targeting `main`. Dependabot updates are grouped per ecosystem and
auto-merged once checks pass (`.github/dependabot.yml`,
`dependabot-auto-merge.yml`).

## Architecture Decision Records (ADRs)

Every significant design or implementation decision must be captured as an ADR
in `docs/adr/`. "Significant" means a choice that:

- Is non-obvious, has real trade-offs, or could be questioned later.
- Constrains future contributors (e.g. "don't add X, we chose Y instead").
- Resolves a fork in the road that otherwise requires re-research.

**Format** — each ADR is a Markdown file named `NNN-short-slug.md`:

```
docs/adr/
  0001-sql-dialect-abstraction.md
  0002-future-annotations-lazy-rebuild.md
  ...
```

Use the template at `docs/adr/template.md`.  Key fields:

| Field | Content |
| --- | --- |
| **Status** | `accepted` / `superseded by #NNN` / `deprecated` |
| **Context** | What problem or situation prompted this decision? |
| **Decision** | What did we decide, and in one sentence, why? |
| **Consequences** | What becomes easier/harder as a result? |

**When to write one:** before merging the PR that implements the change.
Updating an existing ADR to "superseded by #NNN" is fine; deleting ADRs is not.

## Commit and PR etiquette

- Branch off `main`; the `main` branch ruleset requires a passing review and
  green checks, with linear history (squash merge).
- Write clear, imperative commit subjects describing the change.
- **Do not add a "🤖 Generated with [Claude Code]" line to PR descriptions or
  commit messages, and do not add Claude (or any agent) as a `Co-Authored-By`.**
  Keep authorship to the human contributor(s).
