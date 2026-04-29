# Lab 10 - Helm Package Manager

## Chart Overview

The Lab 9 `deployment.yml` and `service.yml` manifests were converted into the
Helm chart at `k8s/python-app/`.

Chart structure:

```text
k8s/python-app/
|-- Chart.yaml
|-- values.yaml
|-- values-dev.yaml
|-- values-prod.yaml
`-- templates/
    |-- _helpers.tpl
    |-- deployment.yaml
    |-- hpa.yaml
    |-- httproute.yaml
    |-- ingress.yaml
    |-- NOTES.txt
    |-- service.yaml
    |-- serviceaccount.yaml
    |-- hooks/
    |   |-- pre-install-job.yaml
    |   `-- post-install-job.yaml
    `-- tests/test-connection.yaml
```

Key files:

| File | Purpose |
| ---- | ------- |
| `Chart.yaml` | Chart metadata, chart version, app version, maintainers, source repository |
| `values.yaml` | Default application configuration converted from Lab 9 |
| `values-dev.yaml` | Development overrides: 1 replica, lower resources, NodePort |
| `values-prod.yaml` | Production overrides: 3 replicas, stronger resources, LoadBalancer-ready service |
| `templates/_helpers.tpl` | Shared names, labels, selector labels, and hook names |
| `templates/deployment.yaml` | FastAPI Deployment with image, env, resources, strategy, and probes from values |
| `templates/service.yaml` | Service type, port, and optional NodePort from values |
| `templates/hpa.yaml`, `ingress.yaml`, `httproute.yaml`, `serviceaccount.yaml` | Optional generated chart resources, disabled unless values enable them |
| `templates/hooks/*.yaml` | Pre-install validation and post-install smoke test jobs |

The old root manifests were moved into the chart templates. The app still keeps
readiness, liveness, and startup probes against `/health`; they are configurable
through values and are not commented out.

## Configuration Guide

Important values:

| Value | Purpose |
| ----- | ------- |
| `replicaCount` | Deployment replica count when autoscaling is disabled |
| `image.repository`, `image.tag`, `image.pullPolicy` | Container image configuration |
| `app.containerPort` | FastAPI container port, default `5000` |
| `service.type`, `service.port`, `service.nodePort` | Kubernetes Service exposure |
| `env` | App environment variables such as `APP_VERSION`, `HOST`, `PORT`, and `LOG_LEVEL` |
| `resources` | CPU and memory requests/limits |
| `readinessProbe`, `livenessProbe`, `startupProbe` | Health check settings |
| `strategy` | Rolling update policy, default `maxUnavailable: 0`, `maxSurge: 1` |
| `hooks` | Hook image and post-install smoke test retry behavior |

Environment examples:

```bash
helm install python-app-dev k8s/python-app -f k8s/python-app/values-dev.yaml
helm upgrade python-app-dev k8s/python-app -f k8s/python-app/values-prod.yaml
```

Dev values render one replica, relaxed resources, `DEBUG` logs, and a fixed
`NodePort` of `30080`. Prod values render three replicas, higher resource
requests/limits, `INFO` logs, and a `LoadBalancer` service. The prod file keeps
the image tag at `latest` because that is the tag produced by the current Docker
workflow on the default branch; an immutable CI tag can be supplied with
`--set image.tag=<tag>`.

## Hook Implementation

Implemented hooks:

| Hook | Weight | File | Purpose | Delete policy |
| ---- | ------ | ---- | ------- | ------------- |
| `pre-install` | `-5` | `templates/hooks/pre-install-job.yaml` | Validates required chart values before installing resources | `before-hook-creation,hook-succeeded` |
| `post-install` | `5` | `templates/hooks/post-install-job.yaml` | Calls the service `/health` endpoint from inside the cluster | `before-hook-creation,hook-succeeded` |
| `test` | default | `templates/tests/test-connection.yaml` | Runs `helm test` against `/health` | `before-hook-creation,hook-succeeded` |

The pre-install hook runs first because it has the lower weight. Successful hook
jobs are deleted automatically, which keeps the namespace clean after install and
test runs.

## Installation Evidence

Helm version:

```text
$ helm version --short
v4.1.4+g05fa379
```

Repositories added and updated:

```text
$ helm repo list
NAME                 URL
grafana              https://grafana.github.io/helm-charts
prometheus-community https://prometheus-community.github.io/helm-charts
```

Public chart inspection:

```text
$ helm show chart prometheus-community/prometheus
apiVersion: v2
appVersion: v3.11.3
description: Prometheus is a monitoring system and time series database.
home: https://prometheus.io/
keywords:
- monitoring
- prometheus
name: prometheus
type: application
version: 29.3.0
```

Dev install:

```text
$ helm install python-app-dev k8s/python-app -f k8s/python-app/values-dev.yaml --wait --timeout 5m
NAME: python-app-dev
STATUS: deployed
REVISION: 1
DESCRIPTION: Install complete
```

Hook watch output during install:

```text
NAME                         STATUS     COMPLETIONS   DURATION   AGE
python-app-dev-pre-install   Running    0/1                      0s
python-app-dev-pre-install   Complete   1/1           7s         7s
python-app-dev-post-install  Running    0/1                      0s
python-app-dev-post-install  Complete   1/1           4s         4s
```

Prod upgrade:

```text
$ helm upgrade python-app-dev k8s/python-app -f k8s/python-app/values-prod.yaml
Release "python-app-dev" has been upgraded. Happy Helming!
STATUS: deployed
REVISION: 3
DESCRIPTION: Upgrade complete
```

Release state:

```text
$ helm list
NAME           NAMESPACE REVISION STATUS   CHART            APP VERSION
python-app-dev default   3        deployed python-app-0.1.0 2026.04
```

History:

```text
$ helm history python-app-dev
REVISION UPDATED                  STATUS     CHART            APP VERSION DESCRIPTION
1        Wed Apr 29 06:58:00 2026 superseded python-app-0.1.0 2026.04     Install complete
2        Wed Apr 29 06:59:09 2026 superseded python-app-0.1.0 2026.04     Upgrade complete
3        Wed Apr 29 07:00:31 2026 deployed   python-app-0.1.0 2026.04     Upgrade complete
```

Cluster resources after prod upgrade:

```text
$ kubectl get all -o wide
NAME                                  READY STATUS  AGE IP
pod/python-app-dev-7cfdfb4d44-5wrrw   1/1   Running 22s 10.244.0.18
pod/python-app-dev-7cfdfb4d44-lrdvl   1/1   Running 35s 10.244.0.17
pod/python-app-dev-7cfdfb4d44-zs2lq   1/1   Running 48s 10.244.0.16

NAME                     TYPE           CLUSTER-IP  EXTERNAL-IP PORT(S)
service/python-app-dev   LoadBalancer   10.96.3.245 <pending>   80:30080/TCP

NAME                             READY UP-TO-DATE AVAILABLE
deployment.apps/python-app-dev   3/3   3          3
```

The service is `LoadBalancer` after the prod upgrade. Because this was upgraded
from the dev `NodePort` service, Kubernetes retained the allocated node port;
a fresh prod install does not set a fixed node port in the rendered manifest.

Hook cleanup:

```text
$ kubectl get jobs
No resources found in default namespace.

$ kubectl describe job python-app-dev-pre-install
Error from server (NotFound): jobs.batch "python-app-dev-pre-install" not found

$ kubectl describe job python-app-dev-post-install
Error from server (NotFound): jobs.batch "python-app-dev-post-install" not found
```

Hook event evidence:

```text
Normal SuccessfulCreate job/python-app-dev-pre-install  Created pod: python-app-dev-pre-install-ljvww
Normal Completed        job/python-app-dev-pre-install  Job completed
Normal SuccessfulCreate job/python-app-dev-post-install Created pod: python-app-dev-post-install-xl2qk
Normal Completed        job/python-app-dev-post-install Job completed
```

Application check:

```text
$ curl -fsS http://localhost:30080/health
{"status":"healthy","timestamp":"2026-04-29T04:00:42.093437+00:00","uptime_seconds":86}
```

## Operations

Install dev:

```bash
helm install python-app-dev k8s/python-app -f k8s/python-app/values-dev.yaml
```

Upgrade to prod:

```bash
helm upgrade python-app-dev k8s/python-app -f k8s/python-app/values-prod.yaml
kubectl rollout status deployment/python-app-dev
```

Override one value:

```bash
helm upgrade python-app-dev k8s/python-app \
  -f k8s/python-app/values-prod.yaml \
  --set replicaCount=5
```

Rollback:

```bash
helm history python-app-dev
helm rollback python-app-dev 2
```

Uninstall:

```bash
helm uninstall python-app-dev
```

Run chart test:

```bash
helm test python-app-dev
```

## Testing & Validation

Chart lint:

```text
$ helm lint k8s/python-app
==> Linting k8s/python-app
[INFO] Chart.yaml: icon is recommended

1 chart(s) linted, 0 chart(s) failed
```

Dev render check:

```text
$ helm template python-app-dev k8s/python-app -f k8s/python-app/values-dev.yaml
kind: Service
  type: NodePort
      nodePort: 30080
kind: Deployment
  replicas: 1
              containerPort: 5000
              path: /health
kind: Job
  name: python-app-dev-post-install
    "helm.sh/hook": post-install
kind: Job
  name: python-app-dev-pre-install
    "helm.sh/hook": pre-install
```

Prod render check:

```text
$ helm template python-app-prod k8s/python-app -f k8s/python-app/values-prod.yaml
kind: Service
  type: LoadBalancer
kind: Deployment
  replicas: 3
              containerPort: 5000
              path: /health
kind: Job
  name: python-app-prod-post-install
    "helm.sh/hook": post-install
kind: Job
  name: python-app-prod-pre-install
    "helm.sh/hook": pre-install
```

Client-side dry run:

```text
$ helm install --dry-run=client --debug python-app-dev k8s/python-app -f k8s/python-app/values-dev.yaml
STATUS: pending-install
DESCRIPTION: Dry run complete
HOOKS:
  python-app-dev-post-install
  python-app-dev-pre-install
MANIFEST:
  Service type: NodePort
  Deployment replicas: 1
NOTES:
  curl http://localhost:30080/health
```

Helm test:

```text
$ helm test python-app-dev --timeout 2m
TEST SUITE:     python-app-dev-test-connection
Phase:          Succeeded
```

CI linting was added in `.github/workflows/helm-ci.yml`. It installs Helm 4.1.4,
runs `helm lint`, renders default/dev/prod values, and runs a client-side dry
run on pull requests and pushes that touch the chart.

## Bonus

The library chart bonus was intentionally not implemented.
