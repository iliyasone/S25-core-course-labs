# Lab 6 — Advanced Ansible & CI/CD

## 1. Overview

I extended the Lab 5 Ansible setup in four parts:

- refactored `common` and `docker` roles with blocks and tags
- renamed `app_deploy` to `web_app`
- switched deployment from `docker_container` to Docker Compose v2
- added GitHub Actions deployment with a GitHub-hosted runner and dynamic GCP host discovery

The repository is not tied to a concrete VM address in committed config:

- real runs use `inventory/gcp_compute.yml`
- `inventory/hosts.ini` is left only as a minimal fallback group for syntax-checks
- GitHub Secrets do not store a VM hostname or IP

---

## 2. Blocks & Tags

### `common`

`roles/common/tasks/main.yml` is now split into:

- `packages`
  - apt cache refresh
  - package installation
  - rescue path with `apt-get update --fix-missing`
  - always block that writes `/tmp/ansible-common-role.log`
- `users`
  - managed user creation

### `docker`

`roles/docker/tasks/main.yml` is now split into:

- `docker_install`
  - Docker repository prerequisites
  - Docker repository setup
  - Docker Engine + Compose plugin installation
  - rescue path with 10-second wait and retry
  - always block that ensures Docker is enabled and started
- `docker_config`
  - user membership in the `docker` group

Observed tag list:

```bash
$ uv run ansible-playbook playbooks/provision.yml --list-tags
TASK TAGS: [common, docker, docker_config, docker_install, packages, users]

$ uv run ansible-playbook playbooks/deploy.yml --list-tags
TASK TAGS: [always, app_deploy, compose, docker, docker_config, docker_install, web_app, web_app_wipe]
```

Selective execution works as expected:

```bash
$ uv run ansible-playbook playbooks/provision.yml --tags packages
lab04-vm : ok=4 changed=2 failed=0

$ uv run ansible-playbook playbooks/provision.yml --tags docker_install
lab04-vm : ok=6 changed=0 failed=0
```


## 3. Docker Compose Migration

The role was renamed:

```bash
roles/app_deploy -> roles/web_app
```

`roles/web_app/meta/main.yml` now depends on `docker`, so `playbooks/deploy.yml` is enough.

Deployment is rendered to:

```bash
/opt/devops-python-info-service/docker-compose.yml
```

Observed rendered file:

```yaml
# Compose schema reference: 3.8
services:
  devops-python-info-service:
    image: "iliyasone/devops-python-info-service:latest"
    container_name: "devops-python-info-service"
    ports:
      - "5000:5000"
    environment:
      DEBUG: "false"
      HOST: "0.0.0.0"
      PORT: "5000"
    restart: "unless-stopped"
    networks:
      - web_app

networks:
  web_app:
    name: "devops-python-info-service-network"
```

The first Compose run on the current VM hit a real migration issue: a previously existing standalone container was already using the target container name.
I handled that by checking the existing container labels and removing it only if it is not already Compose-managed.

This keeps the first migration safe and keeps normal reruns idempotent.

Observed deployment:

```bash
$ uv run ansible-playbook playbooks/deploy.yml
lab04-vm : ok=17 changed=2 skipped=5 failed=0 rescued=0

$ uv run ansible-playbook playbooks/deploy.yml
lab04-vm : ok=16 changed=0 skipped=6 failed=0 rescued=0
```

Observed state on the VM:

```bash
$ docker compose ps
NAME                         IMAGE                                         STATUS
devops-python-info-service   iliyasone/devops-python-info-service:latest   Up
```

External health check:

```json
{"status":"healthy","timestamp":"2026-04-23T12:37:26.403284+00:00","uptime_seconds":15}
```

---

## 4. Wipe Logic

Wipe logic lives in:

```bash
roles/web_app/tasks/wipe.yml
```

The safety model is:

- the wipe block itself is tagged `web_app_wipe`
- actual deletion still requires `web_app_wipe=true`
- deployment stays under `always`, so `--tags web_app_wipe` with the variable still `false` does not accidentally turn the whole run into a no-op

Implementation detail:

```yaml
- name: Determine whether this run is wipe-only
  ansible.builtin.set_fact:
    web_app_wipe_only: "{{ web_app_wipe | bool and 'web_app_wipe' in (ansible_run_tags | default([])) }}"

- name: Deploy application with Docker Compose
  when: not web_app_wipe_only | bool
  tags:
    - always
```

I also verified the actual Ansible tag context:

```bash
$ ansible_run_tags without --tags => ["all"]
$ ansible_run_tags with --tags web_app_wipe => ["web_app_wipe"]
```

So there was no reason to invent `default(['all'])` in the playbook. I removed that.

Observed scenarios:

Normal deploy:

```bash
$ uv run ansible-playbook playbooks/deploy.yml
lab04-vm : ok=17 changed=2 skipped=5 failed=0
```

Wipe only:

```bash
$ uv run ansible-playbook playbooks/deploy.yml -e web_app_wipe=true --tags web_app_wipe
lab04-vm : ok=8 changed=3 skipped=9 failed=0
```

After wipe only:

```bash
$ curl http://34.133.113.246:5000/health
curl: (7) Failed to connect to 34.133.113.246 port 5000: Connection refused
```

Safety case, tag only and variable false:

```bash
$ uv run ansible-playbook playbooks/deploy.yml --tags web_app_wipe
lab04-vm : ok=11 changed=0 skipped=6 failed=0
```

Clean reinstall:

```bash
$ uv run ansible-playbook playbooks/deploy.yml -e web_app_wipe=true
lab04-vm : ok=20 changed=3 skipped=4 failed=0
```

---

## 5. GitHub Actions

Added workflow:

```bash
.github/workflows/ansible-deploy.yml
```

And added the required badge to:

```bash
ansible/README.md
```

Trigger model:

- changes in `ansible/**` run `ansible-deploy.yml` directly
- changes in `app_python/**` go through `python-ci.yml`
- after tests, security scan, and Docker push succeed, `python-ci.yml` calls `ansible-deploy.yml` as a reusable workflow

This matters because a plain `paths: app_python/**` trigger inside `ansible-deploy.yml` would allow Ansible deploy to race the Docker image push.

The deployment workflow uses:

- `GCP_SERVICE_ACCOUNT_JSON` to query GCP inventory dynamically
- `SSH_PRIVATE_KEY` for SSH access from the GitHub-hosted runner
- `ANSIBLE_VAULT_PASSWORD` to decrypt Vault data

No secret contains the VM hostname.

The runner resolves the target host at runtime with `gcloud`:

```bash
gcloud compute instances list --project s25-devops-retake --filter 'status=RUNNING AND name=lab04-vm'
```

Then it writes a temporary runtime inventory and runs:

```bash
uv run ansible-playbook -i "$ANSIBLE_RUNTIME_INVENTORY" playbooks/site.yml
```

Observed local convergence run for the same path:

```bash
$ uv run ansible-playbook playbooks/site.yml
lab04-vm : ok=28 changed=0 skipped=6 failed=0
```

Required GitHub secrets for the Ansible workflow:

- `GCP_SERVICE_ACCOUNT_JSON`
- `SSH_PRIVATE_KEY`
- `ANSIBLE_VAULT_PASSWORD`

The existing Python workflow still also needs:

- `DOCKER_USERNAME`
- `DOCKER_TOKEN`
- `SNYK_TOKEN`
- `CODECOV_TOKEN`

---

## 6. Validation

Lint and syntax checks:

```bash
$ uv run --with ansible-lint ansible-lint playbooks/*.yml roles
Passed: 0 failure(s), 0 warning(s)

$ uv run ansible-playbook -i inventory/hosts.ini --syntax-check playbooks/provision.yml
$ uv run ansible-playbook -i inventory/hosts.ini --syntax-check playbooks/deploy.yml
$ uv run ansible-playbook -i inventory/hosts.ini --syntax-check playbooks/site.yml
```

Current application check:

```bash
$ curl http://34.133.113.246:5000/health
{"status":"healthy", ...}
```

---

## 7. Final Notes

- The role itself is idempotent, so rerunning full convergence is safe. Tags are there for practical selectivity, not because a full rerun would be unsafe.
- Blocks are for grouping tasks inside a role. They are not a grouping mechanism for sets of roles.
