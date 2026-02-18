# Lab 3 — Continuous Integration (CI/CD)

## 1. Testing framework and test scope

I use `pytest` for this project.
Reason: less boilerplate than `unittest`, good fixtures, and very clean integration with FastAPI `TestClient`.

Tests are in `app_python/tests/test_app.py` and cover:

- `GET /` happy path + response structure checks
- `GET /health` happy path
- `404` for unknown route
- `405` for wrong HTTP method
- forced internal error (`500`) via monkeypatch to verify custom exception handler

So this is not just smoke testing; both normal and failure paths are checked.

## 2. Local checks (same idea as CI)

```bash
uv sync --group test --group lint
uv run ruff format --check
uv run ruff check
uv run pyright
uv run pytest --cov --cov-branch --cov-report=xml
```

Current local result:

- `ruff format --check`: `3 files already formatted`
- `ruff check`: `All checks passed!`
- `pyright`: `0 errors, 0 warnings, 0 informations`
- `pytest`: `6 passed in 0.39s`

## 3. GitHub Actions workflow

Workflow file: `.github/workflows/python-ci.yml`

### Triggers

- `push` to `master` (only if `app_python/**` or workflow file changed)
- `pull_request` to `master` (same path filters)

### Jobs

1. `test`
- setup `uv` + cache
- install deps (`test` + `lint` groups)
- run formatter/linter/type checker
- run pytest with coverage XML
- upload coverage to Codecov

2. `security` (runs only after `test`)
- prepare deps and export `requirements.txt`
- run `snyk test --file=requirements.txt --severity-threshold=low`

3. `docker` (runs only after `security`)
- login to Docker Hub
- build and push image
- create tags from metadata action

This gives a clean pipeline: quality gate -> security gate -> publish.

## 4. Versioning/tag strategy

I used a CalVer-style tag + run number:

- `latest` (for default branch)
- `sha-...` (exact commit)
- `YYYY.MM.<run_number>` with `Europe/Kyiv` timezone


## 5. Notes

- Secrets are used for integrations: `CODECOV_TOKEN`, `SNYK_TOKEN`, `DOCKER_USERNAME`, `DOCKER_TOKEN`.
- Severity threshold decision: `low` (explicitly set in CI).
- Reasoning: fail fast on any known vulnerability before Docker publish