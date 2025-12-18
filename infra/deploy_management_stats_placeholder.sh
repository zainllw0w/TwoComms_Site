#!/usr/bin/env bash
set -euo pipefail

# Safe deploy placeholder for Management статистики.
# - НЕ хардкодьте паролі/sshpass/токени в репозиторій.
# - Використовуйте SSH ключі або секрети в CI/CD.
#
# Required env:
#   SSH_HOST="YOUR_HOST"
#   SSH_USER="YOUR_USER"
#   SSH_PORT="22" (optional)
#   REMOTE_PROJECT_DIR="/path/to/TwoComms/twocomms"
#   REMOTE_VENV_ACTIVATE="/path/to/venv/bin/activate"
#
# Optional:
#   REMOTE_SERVICE_RESTART="systemctl restart gunicorn" (or passenger restart, etc)

SSH_HOST="${SSH_HOST:?set SSH_HOST}"
SSH_USER="${SSH_USER:?set SSH_USER}"
SSH_PORT="${SSH_PORT:-22}"
REMOTE_PROJECT_DIR="${REMOTE_PROJECT_DIR:?set REMOTE_PROJECT_DIR}"
REMOTE_VENV_ACTIVATE="${REMOTE_VENV_ACTIVATE:?set REMOTE_VENV_ACTIVATE}"
REMOTE_SERVICE_RESTART="${REMOTE_SERVICE_RESTART:-}"

echo "Deploy → ${SSH_USER}@${SSH_HOST}:${REMOTE_PROJECT_DIR}"

ssh -p "${SSH_PORT}" "${SSH_USER}@${SSH_HOST}" "bash -lc '
  set -euo pipefail
  source \"${REMOTE_VENV_ACTIVATE}\"
  cd \"${REMOTE_PROJECT_DIR}\"

  git pull

  # Apply DB migrations (new models for activity/follow-ups/advice)
  python manage.py migrate

  # Update static (new css/js for stats page)
  python manage.py collectstatic --noinput

  if [ -n \"${REMOTE_SERVICE_RESTART}\" ]; then
    ${REMOTE_SERVICE_RESTART}
  fi
'"

echo "Done."

