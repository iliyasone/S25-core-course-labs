# Lab 8 — Application Metrics

## Application Instrumentation

The FastAPI service exposes Prometheus metrics at `/metrics`.

I used `prometheus-fastapi-instrumentator` for HTTP RED metrics:

```python
Instrumentator(
    should_instrument_requests_inprogress=True,
    inprogress_name="http_requests_in_progress",
).instrument(app).expose(app, include_in_schema=False)
```

The service also defines two application-specific metrics:

| Metric | Type | Purpose |
|--------|------|---------|
| `devops_info_endpoint_calls_total` | Counter | Counts business endpoint usage for `/` and `/health` |
| `devops_info_system_collection_seconds` | Histogram | Measures how long the system info endpoint spends collecting data |

## RED Metrics

| RED part | Metric |
|----------|--------|
| Rate | `sum by (handler) (rate(http_requests_total[5m]))` |
| Errors | `sum(rate(http_requests_total{status=~"5..|5xx"}[5m]))` |
| Duration | `histogram_quantile(0.95, sum by (le, handler) (rate(http_request_duration_seconds_bucket[5m])))` |

The labels stay low-cardinality: route template in `handler`, grouped `status`
values such as `2xx`, and HTTP `method`. No user IDs, request IDs, or raw
dynamic paths are used as metric labels.

## Local Verification

```bash
cd app_python
uv run ruff format
uv run ruff check
uv run pyright
uv run pytest
```

Example metrics check:

```bash
curl http://localhost:5000/metrics
```

Expected metric families include:

```text
http_requests_total{handler="/",method="GET",status="2xx"}
http_request_duration_seconds_bucket{handler="/",method="GET",le="0.1"}
http_requests_in_progress
devops_info_endpoint_calls_total{endpoint="/"}
devops_info_system_collection_seconds_bucket
```
