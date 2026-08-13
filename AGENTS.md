# TwoComms Agent Rules

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
