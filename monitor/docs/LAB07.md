# Lab 07 - Observability & Logging

## Application Logging

The Python application in `app_python/app.py` uses Python's standard
`logging` module with a custom `JSONFormatter`.

Each log line is emitted as one JSON object to stdout/stderr so Docker can
collect it and Promtail can forward it to Loki. The common fields are:

```json
{
  "timestamp": "2026-04-27T14:30:00Z",
  "level": "INFO",
  "logger": "devops-python-info-service",
  "app_name": "devops-python-info-service",
  "message": "http_request_finished"
}
```

Logged events:

- `app_startup`: emitted when the app starts, with host, port, debug mode, and
  app version.
- `http_request_started`: emitted before a request is processed, with method,
  path, and client IP.
- `http_request_finished`: emitted after a response is produced, with method,
  path, client IP, status code, and duration in milliseconds.
- `unhandled_exception`: emitted for uncaught exceptions, including exception
  traceback and request context.

Application identity is configured with these environment variables:

| Variable | Default | Used for |
| --- | --- | --- |
| `APP_NAME` | `devops-python-info-service` | API service name and JSON `app_name` field |
| `APP_VERSION` | `2026.04` | API service version and startup log context |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

For Loki, `app_name` is useful inside the JSON body for parsing with LogQL:

```logql
{app="devops-python"} | json | app_name="devops-python-info-service"
```

Promtail/Docker labels should still provide the low-cardinality Loki stream
label, for example `app="devops-python"`. The label is what Loki indexes
efficiently; the JSON `app_name` field is request/log context that can be parsed
after selecting the stream.
