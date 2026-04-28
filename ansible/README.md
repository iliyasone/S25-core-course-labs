[![Ansible Deployment](https://github.com/iliyasone/S25-core-course-labs/actions/workflows/ansible-deploy.yml/badge.svg)](https://github.com/iliyasone/S25-core-course-labs/actions/workflows/ansible-deploy.yml)

# Get Ansible Vault

```bash
uv run ansible-vault view group_vars/all.yml
```

# Ansible Automation

This directory contains the infrastructure convergence and deployment logic for Labs 5, 6, and 7.

Main entrypoints:

- `playbooks/provision.yml` — base OS + Docker provisioning
- `playbooks/deploy.yml` — web app and monitoring deployment
- `playbooks/deploy-monitoring.yml` — monitoring-only deployment
- `playbooks/site.yml` — full convergence

GitHub Actions behavior:

- changes in `ansible/**` run `ansible-deploy.yml` directly
- changes in `app_python/**` go through `python-ci.yml`, build/push the image, and then call `ansible-deploy.yml`

This keeps app-triggered redeploys ordered after the Docker image update instead of racing it. The full convergence playbook also deploys Loki, Promtail, and Grafana on every production push.

Grafana listens on port `3000`. After deployment, open `http://<vm-public-ip>:3000` and sign in with the configured Grafana admin credentials.
