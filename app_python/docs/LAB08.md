# Lab 8 — Metrics & Monitoring with Prometheus

## 1. Task 1: Application Metrics

I used `prometheus-fastapi-instrumentator` instead of hand-written Prometheus
middleware:

```python
Instrumentator(
    should_instrument_requests_inprogress=True,
    inprogress_name="http_requests_in_progress",
).instrument(app).expose(app, include_in_schema=False)
```

This adds `/metrics` and covers the RED method:

| RED part | Metric |
|----------|--------|
| Rate | `http_requests_total` |
| Errors | `http_requests_total{status=~"5xx"}` |
| Duration | `http_request_duration_seconds` / `http_request_duration_highr_seconds` |

It also exposes `http_requests_in_progress` as the active request gauge.

## 2. Metrics Endpoint

```bash
curl http://localhost:5000/metrics
```

Example output:

```text
http_requests_total{handler="/",method="GET",status="2xx"} 1.0
http_request_duration_seconds_bucket{handler="/",method="GET",le="0.1"} 1.0
http_requests_in_progress 1.0
```

The labels stay low-cardinality: route template in `handler`, grouped `status`
values like `2xx`, and HTTP `method`. No user IDs, request IDs, or raw dynamic
paths.

## 3. Local Verification

```bash
cd app_python
uv run ruff format
uv run ruff check
uv run pyright
uv run pytest
```

Current result: `ruff` clean, `pyright` 0 errors, `pytest` 9 passed.
