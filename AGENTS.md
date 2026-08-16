# TwoComms Agent Rules

## Local Django Runtime

For local Django commands, tests, and dependency checks, use the shared
project virtualenv rather than a bare `python` or `python3` from `PATH`. The
required runtime is CPython `3.14.6` with Django `6.1`.

```bash
TWC_PYTHON="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.venv/bin/python"
test -x "$TWC_PYTHON"
"$TWC_PYTHON" -c 'import django, sys; assert sys.version_info[:3] == (3, 14, 6); assert django.get_version() == "6.1"; print(sys.executable, django.get_version())'
```

Use `"$TWC_PYTHON" manage.py ...` for management commands and
`uv pip ... --python "$TWC_PYTHON"` for package inspection. Do not run a bare
`pip` after activating the environment: this uv-managed virtualenv does not
seed pip.

## Production Deployment

For this repository, the supported production deployment path is:

1. Commit the scoped change and push it to GitHub `main`.
2. Pull `main` on the production checkout over SSH using the project's Python
   3.14 virtualenv:

```bash
SSHPASS="$TWOCOMMS_DEPLOY_PASSWORD" sshpass -e ssh \
  -o StrictHostKeyChecking=no qlknpodo@195.191.25.63 \
  "bash -lc 'source /home/qlknpodo/virtualenv/TWC/TwoComms_Site/twocomms/3.14/bin/activate && cd /home/qlknpodo/TWC/TwoComms_Site/twocomms && git pull'"
```

The password must be supplied through the caller's environment and must never
be committed, printed, or copied into project documentation. Do not invoke
`deploy.sh`, `scripts/deploy_release.py`, an alternate release wrapper, SCP
package installation, source builds, or an arbitrary remote checkout mutation
as a deployment substitute unless the user explicitly authorizes a different
procedure. Post-pull checks and runtime verification may be run over SSH.

Production MariaDB is authoritative for live runtime/data checks, but it is
never a disposable test fixture. Local SQLite is only a fast test layer.
