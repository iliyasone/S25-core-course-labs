[![Ansible Deployment](https://github.com/iliyasone/S25-core-course-labs/actions/workflows/ansible-deploy.yml/badge.svg)](https://github.com/iliyasone/S25-core-course-labs/actions/workflows/ansible-deploy.yml)

# Ansible Automation

This directory contains the infrastructure convergence and deployment logic for Labs 5 and 6.

Main entrypoints:

- `playbooks/provision.yml` — base OS + Docker provisioning
- `playbooks/deploy.yml` — web app deployment
- `playbooks/site.yml` — full convergence

GitHub Actions behavior:

- changes in `ansible/**` run `ansible-deploy.yml` directly
- changes in `app_python/**` go through `python-ci.yml`, build/push the image, and then call `ansible-deploy.yml`

This keeps app-triggered redeploys ordered after the Docker image update instead of racing it.
