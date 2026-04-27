# Lab 07 - Observability & Logging

## Architecture

The monitoring stack runs from `monitor/docker-compose.yml`.

```mermaid
flowchart LR
  App[devops-python-info-service] --> Docker[Docker json-file logs]
  Docker --> Promtail[Promtail]
  Promtail --> Loki[Loki 3.0]
  Loki --> Grafana[Grafana]
```

The Python app writes JSON logs to stdout/stderr. Docker stores the container
logs, Promtail discovers selected containers through the Docker socket, attaches
Loki stream labels, and sends the logs to Loki.

## Setup Guide

Start the stack:

```bash
cd monitor
docker compose up -d --build
```

Verify the main services:

```bash
docker compose ps
curl http://localhost:3100/ready
curl http://localhost:9080/targets
curl http://localhost:8000/health
```

Grafana is available at `http://localhost:3000`. For this lab setup, anonymous
admin access is enabled for local testing.

## Loki Configuration

`monitor/loki/config.yml` configures Loki 3.0 as a single-node filesystem
deployment:

```yaml
schema_config:
  configs:
    - store: tsdb
      object_store: filesystem
      schema: v13

limits_config:
  retention_period: 168h
```

Important choices:

- `auth_enabled: false` keeps the lab stack simple.
- `store: tsdb` and `schema: v13` follow the Loki 3.0 recommendation
- `retention_period: 168h` keeps logs for 7 days.
- `compactor.retention_enabled: true` enables deletion of expired logs.

## Promtail Configuration

`monitor/promtail/config.yml` uses Docker service discovery and sends logs to
Loki:

```yaml
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        filters:
          - name: label
            values:
              - logging=promtail
```

Promtail only scrapes containers with `logging=promtail`. The Lab 07 logging
stack services (`loki`, `promtail`, and `grafana`) and the Python app all have
this label so the lab stack can show logs from multiple containers.

The Python app service has these Docker labels in `monitor/docker-compose.yml`:

```yaml
labels:
  logging: "promtail"
  app: "devops-python-info-service"
  environment: "development"
```

Promtail relabels those Docker labels into Loki stream labels:

```yaml
relabel_configs:
  - source_labels:
      - __meta_docker_container_label_app
    target_label: app
  - source_labels:
      - __meta_docker_container_label_environment
    target_label: environment
```

The default app label is `app="devops-python-info-service"`. The compose file
also passes `APP_NAME=devops-python-info-service` to the Python app, so the Loki
stream label and the default JSON `app_name` field match. Loki 3.0 can use the
`app` stream label to derive `service_name`, so service identity stays in the
infrastructure layer.

## Application Logging

The Python application in `app_python/app.py` uses Python's standard `logging`
module with a custom `JSONFormatter`.

Each log line is emitted as one JSON object. The common fields are:

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

Application settings:

| Variable | Default | Used for |
| --- | --- | --- |
| `APP_NAME` | `devops-python-info-service` | API service name and JSON `app_name` field |
| `APP_VERSION` | `2026.04` | API service version and startup log context |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Labels vs Log Records

💡 One thing that clicked for me during this lab is the separation between Loki labels and JSON log fields — they serve different purposes and are owned by different layers.

Loki labels are infrastructure-owned metadata. The `app` and `environment` labels live in Docker Compose, get promoted by Promtail into Loki stream labels, and that's what Loki indexes for fast stream selection. The application has no say in this — it's decided at deployment time.

JSON log fields are application-owned runtime detail. Fields like `method`, `path`, `status_code`, `duration_ms`, and `exception` only exist because the app knows those values at the moment it writes the log line. Loki doesn't index them — they're parsed on the fly with `| json` in LogQL queries.

I keep `APP_NAME` and the Docker label `app` set to the same value (`devops-python-info-service`) by default so that raw JSON logs stay self-describing even outside Grafana, while Loki indexing remains controlled by the infrastructure layer.

## LogQL Examples

All logs from the Python app:

```logql
{app="devops-python-info-service"}
```

Parse JSON and filter request logs:

```logql
{app="devops-python-info-service"} | json | method="GET"
```

Filter by log level:

```logql
{app="devops-python-info-service"} | json | level="INFO"
```

Request/log rate:

```logql
rate({app="devops-python-info-service"}[1m])
```

Error logs:

```logql
{app="devops-python-info-service"} | json | level="ERROR"
```
