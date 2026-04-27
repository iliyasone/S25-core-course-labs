# AGENTS.md

This file is a live operating guide for agents working in this repository. It
contains durable instructions, recurring user requirements, and current working
practices that future agents must remember.

## Live Library Rules

Agents may update this file when the user provides a new requirement that should
always be applied, or when a repeated current practice becomes important enough
to preserve.

Keep this file short and operational. Do not use it for:

- design decisions or feature documentation, because code and lab docs already
  contain that context
- repository file structure
- feature lists
- one-off task notes

## Main Service

`app_python` is the main service for now. Run Python service commands from that
directory unless the user explicitly asks for another project.

Use `uv`; do not switch to raw `pip`, global Python environments, Poetry, or
manual virtualenv commands for this service.

## Code Style

### Prefer Deep Methods, Avoid Shallow Private Methods

Avoid creating shallow helper or dunder methods. Just do the job inline.

Use existing helpers when they fit, but be cautious about introducing new ones.

Avoid nested functions. Prefer top-level functions with clear names and inputs.

### Avoid Shallow Functions

Prefer code that carries its own weight. Tiny wrappers and convenience functions
often make code harder to read, not easier.

Do not introduce a function that only forwards to another function with renamed
parameters, fixed defaults, or a tiny amount of glue unless it adds clear domain
meaning or isolates real complexity.

Every new function increases API surface and indirection. If a reader must jump
to the helper just to learn that it delegates to an existing API, keep the logic
inline instead.

Be especially strict for public or widely reused interfaces. Internal
convenience can be tolerable in rare cases; exported convenience wrappers tend
to linger and make the system harder to change.

Small functions are still fine when they encapsulate unique logic, capture real
knowledge, or create a clearer domain abstraction.

### Architecture

Avoid substantial architectural changes without explicit approval.

Stick to the existing code style.

## Python Style

Never use `from __future__ import annotations`; Python 3.14 already has lazy
annotations.

Never use `Optional`; use `T | None`.

Never use string over type when dealing with lazy annotations.

Prefer `Annotated` dependencies instead of default-value `Depends(...)`
parameters in FastAPI.

Never cast to `Any`. If typing gets in the way of a valid statement, use a
narrow `pyright: ignore[...]` comment on that line instead.

## Logging Practices

The Python service currently emits JSON logs only. Keep `JSONFormatter` based on
the standard `logging` module unless the user asks for another logging package.

`JSONFormatter.empty_record` is the baseline for filtering standard
`logging.LogRecord` attributes. Do not reintroduce a hand-maintained reserved
attribute list for formatter serialization.

Application log records should include runtime facts the app knows when it logs:
request method, path, status code, duration, client IP, exceptions, and similar
context.

Infrastructure labels belong outside the app. For Loki, Docker Compose and
Promtail own indexed stream labels such as `app` and `environment`. The default
Python `APP_NAME` value and the default Loki `app` label should stay equal:
`devops-python-info-service`.

## Execution

You can use `git diff`. It is the user's responsibility to ensure a clean git
state; you will see only your changes from the current or previous session.

After changing code in `app_python`, run all checks before finishing:

```bash
cd app_python
uv run ruff format
uv run ruff check
uv run pyright
uv run pytest
```

For a read-only verification pass, `uv run ruff format --check` is acceptable,
but after edits prefer `uv run ruff format`.

If `pyproject.toml` changes, also run:

```bash
uv lock --check
```
