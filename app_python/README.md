# DevOps Info Service

## 1. Overview

This service reports system information and health status.

## 2. Prerequisites

- Python 3.14
- uv package manager

## 3. Installation

- Clone repo (forked from `inno-devops-labs/DevOps-Core-Course:master`)
  
  ```bash
  git clone https://github.com/iliyasone/S25-core-course-labs.git
  cd S25-core-course-labs
  ```

- Change directory to `python_app`
  ```bash
  cd python_app
  ```

- Install dependencies
  ```bash
  uv sync --frozen
  ```

- [Optional] Include dev, test and lint dependencies 
  ```bash
  uv sync --all-groups
  ```

## 4. Running the Application

### Default configuration (localhost:5000)

```bash
uv run python app.py
```

### Custom configuration via environment variables

```bash
# Custom port
PORT=8080 uv run python app.py

# Custom host and port
HOST=127.0.0.1 PORT=3000 uv run python app.py

# Debug mode
DEBUG=true uv run python app.py
```
### Using environment directly

```bash
source .venv/bin/activate
python app.py
```

### Using uvicorn directly

```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 5000 --reload
```

## 5. API Endpoints

### GET /

Returns comprehensive service and system information.

### GET /health

Simple health check endpoint for Kubernetes probes and monitoring systems.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T14:30:00.000000Z",
  "uptime_seconds": 3600
}
```


## 6. Configuration

Environment variables control application behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Server host address |
| `PORT` | `5000` | Server port |
| `DEBUG` | `False` | Enable debug mode with auto-reload |


## 7. Development

### Code formatting and linting

```bash
uv run pyright
uv run ruff check
uv run ruff format
```
